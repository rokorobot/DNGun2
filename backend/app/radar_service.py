from __future__ import annotations

import json
from typing import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models
from .radar import (
    RateLimiter,
    build_queries,
    build_watch_profile,
    fetch_gdelt,
    load_radar_rules,
    match_headline,
    parse_portfolio,
)
from .repository import prefixed_id
from .schemas import OfferStatus, OfferType, utc_now_iso

Fetcher = Callable[..., list[dict]]


class RadarError(Exception):
    """A radar operation was rejected; the message is shown to the operator."""


class RadarService:
    """Portfolio import, news scanning, and opportunity review (MVP 2.0)."""

    def __init__(
        self,
        session: Session,
        fetch: Fetcher = fetch_gdelt,
        limiter: RateLimiter | None = None,
    ):
        self.session = session
        self.fetch = fetch
        self.limiter = limiter or RateLimiter()
        self.rules = load_radar_rules()

    # --- Portfolio ------------------------------------------------------

    def import_portfolio(self, text: str) -> dict:
        rows, invalid = parse_portfolio(text)
        created, updated = [], []
        for row in rows:
            try:
                profile = build_watch_profile(
                    row["domain"],
                    keywords=row["keywords"] or None,
                    markets=row["markets"] or None,
                    industry=row["industry"],
                    rules=self.rules,
                )
            except ValueError as error:
                invalid.append(f"{row['domain']} ({error})")
                continue
            offer = self._find_domain_offer(row["domain"])
            if offer is None:
                offer = models.OfferModel(
                    id=prefixed_id("O"),
                    name=row["domain"],
                    offer_type=OfferType.DOMAIN_NAME.value,
                    description=row["notes"],
                    estimated_value=row["price"],
                    status=OfferStatus.DRAFT.value,
                    created_at=utc_now_iso(),
                )
                self.session.add(offer)
                self.session.flush()
                self._save_profile(offer.id, profile)
                created.append(row["domain"])
            else:
                if row["price"] is not None:
                    offer.estimated_value = row["price"]
                if row["notes"]:
                    offer.description = row["notes"]
                existing = self.session.get(models.DomainWatchProfileModel, offer.id)
                if existing is None or profile["origin"] == "MANUAL":
                    self._save_profile(offer.id, profile)
                updated.append(row["domain"])
        self.session.commit()
        return {"created": created, "updated": updated, "invalid": invalid}

    def list_portfolio(self) -> list[dict]:
        offers = self.session.scalars(
            select(models.OfferModel)
            .where(models.OfferModel.offer_type == OfferType.DOMAIN_NAME.value)
            .order_by(models.OfferModel.name)
        ).all()
        counts = dict(
            self.session.execute(
                select(models.OpportunityModel.offer_id, func.count())
                .where(models.OpportunityModel.status == "NEW")
                .group_by(models.OpportunityModel.offer_id)
            ).all()
        )
        result = [self._portfolio_row(offer, counts.get(offer.id, 0)) for offer in offers]
        self.session.commit()  # persists profiles created lazily for older offers
        return result

    def update_profile(
        self, offer_id: str, *, keywords: list[str], markets: list[str], industry: str | None
    ) -> dict:
        offer = self._require_offer(offer_id)
        cleaned = [k.strip().lower() for k in keywords if k.strip()]
        if not cleaned:
            raise RadarError("At least one keyword is required")
        try:
            profile = build_watch_profile(
                offer.name, keywords=cleaned, markets=markets or None, industry=industry, rules=self.rules
            )
        except ValueError as error:
            raise RadarError(str(error)) from error
        profile["origin"] = "MANUAL"
        self._save_profile(offer.id, profile)
        self.session.commit()
        return self._portfolio_row(offer, 0)

    # --- Scanning -------------------------------------------------------

    def scan(self, offer_ids: list[str] | None = None) -> dict:
        if offer_ids:
            offers = [self._require_offer(offer_id) for offer_id in offer_ids]
        else:
            offers = self.session.scalars(
                select(models.OfferModel).where(
                    models.OfferModel.offer_type == OfferType.DOMAIN_NAME.value
                )
            ).all()
        scoring = self.rules["scoring"]
        summary = {"domains": 0, "queries": 0, "articles": 0, "new_opportunities": 0, "errors": []}
        for offer in offers:
            profile_model = self._ensure_profile(offer)
            profile = {
                "keywords": json.loads(profile_model.keywords),
                "markets": json.loads(profile_model.markets),
            }
            summary["domains"] += 1
            for query in build_queries(profile, self.rules):
                self.limiter.wait()
                summary["queries"] += 1
                try:
                    articles = self.fetch(
                        query["query"],
                        timespan=scoring["timespan"],
                        max_records=scoring["max_results_per_query"],
                    )
                except Exception as error:  # one bad query must not stop the scan
                    summary["errors"].append(f"{offer.name} [{query['market']}]: {error}")
                    continue
                summary["articles"] += len(articles)
                for article in articles:
                    match = match_headline(article["title"], offer.name, profile, self.rules)
                    if match is None:
                        continue
                    news = self._upsert_news(article)
                    if self._opportunity_exists(offer.id, news.id):
                        continue
                    self.session.add(
                        models.OpportunityModel(
                            id=prefixed_id("OP"),
                            offer_id=offer.id,
                            news_item_id=news.id,
                            company_name=match.company_name,
                            event_type=match.event_type,
                            match_type=match.match_type,
                            score=match.score,
                            explanation=json.dumps(match.explanation),
                            status="NEW",
                            created_at=utc_now_iso(),
                        )
                    )
                    self.session.flush()
                    summary["new_opportunities"] += 1
            profile_model.last_scanned_at = utc_now_iso()
            self.session.commit()
        return summary

    # --- Opportunities --------------------------------------------------

    def list_opportunities(self, status: str | None = None, offer_id: str | None = None) -> list[dict]:
        statement = select(models.OpportunityModel)
        if status:
            statement = statement.where(models.OpportunityModel.status == status)
        if offer_id:
            statement = statement.where(models.OpportunityModel.offer_id == offer_id)
        statement = statement.order_by(
            models.OpportunityModel.score.desc(), models.OpportunityModel.created_at.desc()
        )
        return [self.opportunity_read(o) for o in self.session.scalars(statement).all()]

    def accept(
        self,
        opportunity_id: str,
        *,
        company_name: str,
        segment: str,
        website: str | None = None,
    ) -> dict:
        """Turn an opportunity into a prospect with a news signal and evidence. Atomic."""
        opportunity = self._require_open_opportunity(opportunity_id)
        name = company_name.strip()
        if not name:
            raise RadarError("Company name is required")
        if self.session.scalar(
            select(models.SegmentRegistryModel).where(models.SegmentRegistryModel.code == segment)
        ) is None:
            raise RadarError(f"Segment code '{segment}' is not registered")
        news = opportunity.news_item
        event = next(
            (e for e in self.rules["events"] if e["type"] == opportunity.event_type), None
        )
        now = utc_now_iso()
        try:
            prospect = self.session.scalar(
                select(models.ProspectModel).where(
                    func.lower(models.ProspectModel.company_name) == name.lower()
                )
            )
            if prospect is None:
                prospect = models.ProspectModel(
                    id=prefixed_id("P"),
                    company_name=name,
                    website=(website or "").strip() or None,
                    segment=segment,
                    status="NEW",
                    created_at=now,
                )
                self.session.add(prospect)
                self.session.flush()
            self.session.add(
                models.SignalModel(
                    id=prefixed_id("S"),
                    prospect_id=prospect.id,
                    signal_type=f"{event['label'] if event else 'News mention'} (news)",
                    tier=event["tier"] if event else 3,
                    score=5 if opportunity.match_type == "NAME" else 4,
                    source_url=news.url,
                    observed_at=news.published_at or now,
                    notes=news.title,
                    created_at=now,
                )
            )
            self.session.add(
                models.EvidenceEntryModel(
                    id=prefixed_id("EV"),
                    project="DNGun",
                    evidence_type="News",
                    evidence=f"{news.title} (matched to {opportunity.offer.name})",
                    impact=1,
                    source=news.url,
                    offer_id=opportunity.offer_id,
                    status="ACTIVE",
                    created_at=now,
                )
            )
            opportunity.status = "ACCEPTED"
            opportunity.company_name = name
            opportunity.prospect_id = prospect.id
            opportunity.reviewed_at = now
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return self.opportunity_read(opportunity)

    def dismiss(self, opportunity_id: str) -> dict:
        opportunity = self._require_open_opportunity(opportunity_id)
        opportunity.status = "DISMISSED"
        opportunity.reviewed_at = utc_now_iso()
        self.session.commit()
        return self.opportunity_read(opportunity)

    def opportunity_read(self, opportunity: models.OpportunityModel) -> dict:
        news = opportunity.news_item
        return {
            "id": opportunity.id,
            "offer_id": opportunity.offer_id,
            "domain": opportunity.offer.name,
            "company_name": opportunity.company_name,
            "event_type": opportunity.event_type,
            "match_type": opportunity.match_type,
            "score": opportunity.score,
            "explanation": json.loads(opportunity.explanation),
            "status": opportunity.status,
            "prospect_id": opportunity.prospect_id,
            "created_at": opportunity.created_at,
            "reviewed_at": opportunity.reviewed_at,
            "news": {
                "url": news.url,
                "title": news.title,
                "source_domain": news.source_domain,
                "source_country": news.source_country,
                "published_at": news.published_at,
            },
        }

    # --- Internals ------------------------------------------------------

    def _find_domain_offer(self, domain: str) -> models.OfferModel | None:
        return self.session.scalar(
            select(models.OfferModel).where(
                func.lower(models.OfferModel.name) == domain.lower(),
                models.OfferModel.offer_type == OfferType.DOMAIN_NAME.value,
            )
        )

    def _require_offer(self, offer_id: str) -> models.OfferModel:
        offer = self.session.get(models.OfferModel, offer_id)
        if offer is None:
            raise LookupError("Offer not found")
        return offer

    def _require_open_opportunity(self, opportunity_id: str) -> models.OpportunityModel:
        opportunity = self.session.get(models.OpportunityModel, opportunity_id)
        if opportunity is None:
            raise LookupError("Opportunity not found")
        if opportunity.status != "NEW":
            raise RadarError(f"Opportunity was already {opportunity.status.lower()}")
        return opportunity

    def _save_profile(self, offer_id: str, profile: dict) -> models.DomainWatchProfileModel:
        model = self.session.get(models.DomainWatchProfileModel, offer_id)
        if model is None:
            model = models.DomainWatchProfileModel(offer_id=offer_id, updated_at=utc_now_iso())
            self.session.add(model)
        model.keywords = json.dumps(profile["keywords"])
        model.markets = json.dumps(profile["markets"])
        model.industry = profile.get("industry")
        model.origin = profile["origin"]
        model.updated_at = utc_now_iso()
        return model

    def _ensure_profile(self, offer: models.OfferModel) -> models.DomainWatchProfileModel:
        model = self.session.get(models.DomainWatchProfileModel, offer.id)
        if model is None:
            model = self._save_profile(offer.id, build_watch_profile(offer.name, rules=self.rules))
            self.session.flush()
        return model

    def _portfolio_row(self, offer: models.OfferModel, new_count: int) -> dict:
        profile = self._ensure_profile(offer)
        return {
            "offer_id": offer.id,
            "domain": offer.name,
            "price": offer.estimated_value,
            "notes": offer.description,
            "keywords": json.loads(profile.keywords),
            "markets": json.loads(profile.markets),
            "industry": profile.industry,
            "origin": profile.origin,
            "last_scanned_at": profile.last_scanned_at,
            "new_opportunities": new_count,
        }

    def _upsert_news(self, article: dict) -> models.NewsItemModel:
        news = self.session.scalar(
            select(models.NewsItemModel).where(models.NewsItemModel.url == article["url"])
        )
        if news is None:
            news = models.NewsItemModel(
                id=prefixed_id("NI"),
                url=article["url"],
                title=article["title"],
                source_domain=article.get("source_domain"),
                source_country=article.get("source_country"),
                language=article.get("language"),
                published_at=article.get("published_at"),
                fetched_at=utc_now_iso(),
            )
            self.session.add(news)
            self.session.flush()
        return news

    def _opportunity_exists(self, offer_id: str, news_item_id: str) -> bool:
        return (
            self.session.scalar(
                select(models.OpportunityModel.id).where(
                    models.OpportunityModel.offer_id == offer_id,
                    models.OpportunityModel.news_item_id == news_item_id,
                )
            )
            is not None
        )
