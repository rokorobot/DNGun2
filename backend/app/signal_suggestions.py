"""Suggest prospect signals from external data (via treg) for operator approval.

Each lookup maps a treg capability onto a signal in rules/signal_taxonomy.yaml.
Suggestions are stored as PENDING and become real signals only when approved,
so external data never enters scoring without human review.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import quote_plus

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .domain_buyers import normalize_domain
from .repository import Repository, prefixed_id
from .schemas import Prospect, ProspectCreate, SignalCreate, utc_now_iso
from .treg_client import TregClient, TregError

# Endpoint ids are treg's routed capabilities: treg tries providers cheapest-first.
ENRICH = "treg.companies.enrich"
JOBS = "treg.companies.jobs.search"
NEWS = "treg.companies.news"
POSTS = "treg.linkedin.user.posts"
EMAIL = "treg.people.email.find"
METRICS = "treg.web.url.metrics"
# The email route tries up to ~8 providers in turn and can take minutes; cap it so one slow
# vendor doesn't stall the whole lookup. A timeout is reported as a warning.
EMAIL_TIMEOUT_SECONDS = 30
# Worst-case USD per lookup (most expensive provider in each route), for the estimate only.
MAX_USD = {ENRICH: 0.004, JOBS: 0.04, NEWS: 0.04, POSTS: 0.004, EMAIL: 0.01, METRICS: 0.024}

NEWS_MAX_AGE_DAYS = 120
POST_MAX_AGE_DAYS = 180
SIZE_FIT = ((2, 50, 4), (51, 200, 2))  # (min, max, score) employees for "Company size fit"

SALES_ROLE = re.compile(
    r"\b(sdr|bdr|sales development|business development (rep|representative)|"
    r"account executive|outbound|appointment setter|lead generation specialist)\b", re.I)
LAUNCH = re.compile(
    r"\b(launch(es|ed|ing)?|introduc(es|ed|ing)|unveil(s|ed)?|rolls? out|expands? into|"
    r"new (service|offering|product|practice|division)|announc(es|ed) (a |the )?new)\b", re.I)
FOUNDER_TOPICS = {
    "Founder discusses growth": re.compile(
        r"\b(growth|revenue|new clients?|doubled|tripled|mrr|arr|"
        r"(grow|growing|scale|scaling) (our|the|my) (agency|business|team|company|revenue))\b", re.I),
    "Founder mentions referrals": re.compile(r"\b(referrals?|referred|word[- ]of[- ]mouth)\b", re.I),
    "Founder discusses CAC": re.compile(
        r"\b(cac|customer acquisition cost|cost per (lead|acquisition)|cpl)\b", re.I),
    "Founder discusses pipeline": re.compile(
        r"\b(pipeline|outbound|lead gen(eration)?|booked (calls|meetings)|sales calls?)\b", re.I),
}


def estimate_cost(prospect: Prospect) -> float:
    return sum(MAX_USD[endpoint] for endpoint, _ in planned_lookups(prospect))


def planned_lookups(prospect: Prospect) -> list[tuple[str, dict]]:
    domain = normalize_domain(prospect.website) if prospect.website else None
    plan: list[tuple[str, dict]] = []
    if domain:
        plan += [(ENRICH, {"domain": domain}), (JOBS, {"domain": domain, "limit": 25}),
                 (NEWS, {"domain": domain, "limit": 10}), (METRICS, {"target": domain})]
        if prospect.founder_name:
            plan.append((EMAIL, {"domain": domain, "full_name": prospect.founder_name}))
    if prospect.founder_linkedin and "linkedin.com/" in prospect.founder_linkedin:
        plan.append((POSTS, {"linkedin_url": prospect.founder_linkedin, "limit": 20}))
    return plan


def gather_suggestions(client: TregClient, prospect: Prospect) -> tuple[list[dict], list[str]]:
    """Run every applicable lookup; returns (suggestions, warnings). Never raises on provider errors."""
    parsers: dict[str, Callable[[Any, Prospect], list[dict]]] = {
        ENRICH: suggest_size_fit, JOBS: suggest_hiring, NEWS: suggest_launch,
        METRICS: suggest_website_quality, EMAIL: suggest_contact_path, POSTS: suggest_founder_topics,
    }
    suggestions, warnings = [], []
    plan = planned_lookups(prospect)
    if not plan:
        warnings.append("prospect has no website or founder LinkedIn URL — nothing to look up")
    for endpoint, body in plan:
        try:
            response = client.call(endpoint, method="POST", body=body,
                                   timeout=EMAIL_TIMEOUT_SECONDS if endpoint == EMAIL else None)
        except TregError as error:
            warnings.append(str(error))
            continue
        meta = response.get("_treg") if isinstance(response, dict) else None
        if isinstance(meta, dict) and meta.get("outcome") == "pending":
            warnings.append(f"{endpoint}: provider answered asynchronously; rerun later")
            continue
        output = response.get("output") if isinstance(response, dict) else None
        provider = meta.get("served_by") if isinstance(meta, dict) else None
        for suggestion in parsers[endpoint](output or {}, prospect):
            suggestion["provider"] = provider or endpoint
            suggestions.append(suggestion)
    return suggestions, warnings


# --- lookup → signal mapping -------------------------------------------------------------------

def suggest_size_fit(output: dict, prospect: Prospect) -> list[dict]:
    employees = parse_headcount(output.get("employees"))
    if employees is None:
        return []
    for low, high, score in SIZE_FIT:
        if low <= employees <= high:
            detail = ", ".join(str(v) for v in (output.get("industry"), output.get("location")) if v)
            return [_suggestion("Company size fit", 3, score, prospect.website,
                                f"~{employees} employees ({output.get('employees')})"
                                + (f"; {detail}" if detail else ""))]
    return []


def suggest_hiring(output: dict, prospect: Prospect) -> list[dict]:
    roles = []
    for job in output.get("jobs") or []:
        title = _deep_get(job, "title", "job_title", "normalized_title", "name")
        if isinstance(title, str) and SALES_ROLE.search(title):
            roles.append((title, _deep_get(job, "url", "job_url", "link", "source_url"),
                          _deep_get(job, "first_seen_at", "posted_at", "date_posted", "published_at")))
    if not roles:
        return []
    title, url, posted = roles[0]
    titles = "; ".join(sorted({t for t, _, _ in roles}))[:400]
    return [_suggestion("Hiring SDR", 1, 5 if len(roles) > 1 else 4, url or prospect.website,
                        f"{len(roles)} sales-development role(s): {titles}", observed_at=posted)]


def suggest_launch(output: dict, prospect: Prospect) -> list[dict]:
    for article in output.get("articles") or []:
        if not isinstance(article, dict):
            continue
        published = _deep_get(article, "published_date", "published_at", "date", "found_at")
        if not _recent(published, NEWS_MAX_AGE_DAYS):
            continue
        title = str(_deep_get(article, "title", "headline", "summary") or "")
        summary = str(_deep_get(article, "ai_summary", "summary", "description") or "")
        if LAUNCH.search(title) or LAUNCH.search(summary):
            return [_suggestion("New service launch", 1, 4,
                                _deep_get(article, "url", "link", "source_url") or prospect.website,
                                f"{title} — {summary}"[:500], observed_at=published)]
    return []


def suggest_website_quality(output: dict, prospect: Prospect) -> list[dict]:
    metrics = output.get("metrics") if isinstance(output.get("metrics"), dict) else {}
    authority = _deep_get(metrics, "domain_authority", "domainAuthority", "domain_rating",
                          "domain_inlink_rank", "authority_score")
    try:
        authority = float(authority)
    except (TypeError, ValueError):
        return []
    score = 4 if authority >= 60 else 3 if authority >= 40 else 2 if authority >= 20 else 1
    return [_suggestion("Website quality", 2, score, prospect.website,
                        f"Domain authority ~{authority:.0f}/100 (backlink proxy only — check the site itself)")]


def suggest_contact_path(output: dict, prospect: Prospect) -> list[dict]:
    email = output.get("email")
    if not email:
        return []
    verified = bool(output.get("verified"))
    confidence = output.get("confidence")
    return [_suggestion("Founder contact path visible", 3, 4 if verified else 3, prospect.website,
                        f"Work email found for {prospect.founder_name}: {email}"
                        f" (verified={verified}, confidence={confidence})")]


def suggest_founder_topics(output: dict, prospect: Prospect) -> list[dict]:
    hits: dict[str, list[tuple[str, str | None, str | None]]] = {}
    for post in output.get("posts") or []:
        if not isinstance(post, dict):
            continue
        posted = _deep_get(post, "date", "posted_at", "postedAt", "created_at")
        text = _deep_get(post, "content", "text", "commentary", "post_text")
        if not isinstance(text, str) or not _recent(posted, POST_MAX_AGE_DAYS, default=True):
            continue
        for signal_type, pattern in FOUNDER_TOPICS.items():
            match = pattern.search(text)
            if match:
                hits.setdefault(signal_type, []).append((_excerpt(text, match), _post_url(post), posted))
    suggestions = []
    for signal_type, posts in hits.items():
        excerpt, url, posted = posts[0]
        tier = 1 if signal_type in ("Founder discusses growth", "Founder mentions referrals") else 2
        suggestions.append(_suggestion(signal_type, tier, 4 if len(posts) > 1 else 3,
                                       url or prospect.founder_linkedin,
                                       f"{len(posts)} recent post(s); e.g. “{excerpt}”",
                                       observed_at=posted))
    return suggestions


# --- domain buyers → prospects ----------------------------------------------------------------

def buyer_suggestions(candidate: dict, offered: str) -> list[dict]:
    """Evidence from find_domain_buyers for one candidate, as pending signals."""
    suggestions = []
    budget = candidate.get("monthly_ad_budget")
    budget_note = f"; est. Google Ads budget ${budget:,.0f}/mo" if budget else ""
    if candidate.get("ad_hits"):
        keyword, position = min(candidate["ad_hits"], key=lambda hit: hit[1])
        suggestions.append(_suggestion(
            "Buys ads on offer keyword", 1, 5 if position <= 3 else 4, _google_url(keyword),
            f"Google Ads slot #{position} for '{keyword}' (offer {offered}){budget_note}"))
    if candidate.get("organic_hits"):
        keyword, position = min(candidate["organic_hits"], key=lambda hit: hit[1])
        suggestions.append(_suggestion(
            "Ranks for offer keyword", 2, 5 if position <= 3 else 4 if position <= 10 else 2,
            _google_url(keyword), f"Organic #{position} for '{keyword}' (offer {offered})"))
    for reason in candidate.get("reasons") or []:
        if reason.startswith(("Brand overlaps", "Brand partially")):
            suggestions.append(_suggestion(
                "Brand overlaps offer keyword", 2, 4 if reason.startswith("Brand overlaps") else 2,
                f"https://{candidate['domain']}", f"{reason} (offer {offered})"))
    return suggestions


def save_buyer_prospects(session: Session, result: dict, segment: str, top: int) -> list[dict]:
    """Create the top candidates as prospects (skipping domains already in DNGun) and attach
    their buyer evidence as PENDING suggestions. Returns one summary row per candidate."""
    repository = Repository(session)
    existing = {normalize_domain(p.website): p.id for p in session.scalars(select(models.ProspectModel))
                if p.website}
    rows = []
    for candidate in [c for c in result["candidates"] if c["score"] > 0][:top]:
        domain = candidate["domain"]
        prospect_id = existing.get(domain)
        created = prospect_id is None
        if created:
            prospect_id = repository.create_prospect(ProspectCreate(
                company_name=candidate.get("name") or domain, website=f"https://{domain}",
                segment=segment)).id
            existing[domain] = prospect_id
        saved = save_suggestions(session, prospect_id, buyer_suggestions(candidate, result["domain"]))
        rows.append({"domain": domain, "prospect_id": prospect_id, "created": created,
                     "suggestions": len(saved)})
    return rows


def _google_url(keyword: str) -> str:
    return "https://www.google.com/search?q=" + quote_plus(keyword)


# --- persistence & review ----------------------------------------------------------------------

def save_suggestions(session: Session, prospect_id: str, suggestions: list[dict]) -> list[models.SignalSuggestionModel]:
    """Store new suggestions as PENDING. Skips any (type, source) already suggested — including
    rejected ones, so a rejection sticks — or already recorded as a signal."""
    seen = {(s.signal_type, s.source_url) for s in session.scalars(
        select(models.SignalSuggestionModel).where(models.SignalSuggestionModel.prospect_id == prospect_id))}
    seen |= {(s.signal_type, s.source_url) for s in session.scalars(
        select(models.SignalModel).where(models.SignalModel.prospect_id == prospect_id))}
    created = []
    for suggestion in suggestions:
        if (suggestion["signal_type"], suggestion["source_url"]) in seen:
            continue
        seen.add((suggestion["signal_type"], suggestion["source_url"]))
        model = models.SignalSuggestionModel(
            id=prefixed_id("SS"), prospect_id=prospect_id, status="PENDING",
            created_at=utc_now_iso(), **suggestion)
        session.add(model)
        created.append(model)
    session.commit()
    return created


def list_suggestions(session: Session, prospect_id: str | None = None,
                     status: str | None = "PENDING") -> list[models.SignalSuggestionModel]:
    query = select(models.SignalSuggestionModel).order_by(
        models.SignalSuggestionModel.prospect_id, models.SignalSuggestionModel.tier,
        models.SignalSuggestionModel.created_at)
    if prospect_id:
        query = query.where(models.SignalSuggestionModel.prospect_id == prospect_id)
    if status:
        query = query.where(models.SignalSuggestionModel.status == status)
    return list(session.scalars(query))


def review_suggestion(session: Session, suggestion_id: str, approve: bool) -> models.SignalSuggestionModel:
    suggestion = session.get(models.SignalSuggestionModel, suggestion_id)
    if suggestion is None:
        raise ValueError(f"suggestion {suggestion_id} not found")
    if suggestion.status != "PENDING":
        raise ValueError(f"suggestion {suggestion_id} is already {suggestion.status}")
    if approve:
        signal = Repository(session).create_signal(suggestion.prospect_id, SignalCreate(
            signal_type=suggestion.signal_type, tier=suggestion.tier, score=suggestion.score,
            source_url=suggestion.source_url, observed_at=suggestion.observed_at,
            notes=f"{suggestion.notes} [via treg: {suggestion.provider}]"))
        suggestion.signal_id = signal.id
    suggestion.status = "APPROVED" if approve else "REJECTED"
    suggestion.reviewed_at = utc_now_iso()
    session.commit()
    return suggestion


# --- helpers -----------------------------------------------------------------------------------

def parse_headcount(value: Any) -> int | None:
    if isinstance(value, (int, float)):
        return int(value)
    numbers = [int(n.replace(",", "")) for n in re.findall(r"\d[\d,]*", str(value or ""))]
    if not numbers:
        return None
    return (numbers[0] + numbers[-1]) // 2


def _suggestion(signal_type: str, tier: int, score: int, source_url: str | None, notes: str,
                observed_at: Any = None) -> dict:
    return {"signal_type": signal_type, "tier": tier, "score": score, "source_url": source_url,
            "notes": notes, "observed_at": str(observed_at) if observed_at else utc_now_iso()}


def _deep_get(row: Any, *keys: str) -> Any:
    """First non-empty value for any key, at the top level or one nested dict down (e.g. JSON:API `attributes`)."""
    if not isinstance(row, dict):
        return None
    layers = [row] + [v for v in row.values() if isinstance(v, dict)]
    for key in keys:
        for layer in layers:
            if layer.get(key) not in (None, ""):
                return layer[key]
    return None


def _recent(value: Any, max_age_days: int, default: bool = False) -> bool:
    if not value:
        return default
    try:
        when = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return default
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - when <= timedelta(days=max_age_days)


def _post_url(post: dict) -> str | None:
    # Top level only: nested dicts such as `profile` carry the author's URL, not the post's.
    for key in ("url", "postUrl", "post_url", "shareUrl", "linkedinUrl"):
        url = post.get(key)
        if isinstance(url, str) and url.startswith("http"):
            return url
    urn = post.get("id") or post.get("urn")
    if isinstance(urn, str) and urn.startswith("urn:li:"):
        return f"https://www.linkedin.com/feed/update/{urn}/"
    return None


def _excerpt(text: str, match: re.Match, width: int = 90) -> str:
    start, end = max(0, match.start() - width), min(len(text), match.end() + width)
    snippet = " ".join(text[start:end].split())
    return ("…" if start else "") + snippet + ("…" if end < len(text) else "")
