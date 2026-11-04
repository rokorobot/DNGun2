"""Find and rank likely buyers for a domain-name offer using treg data.

Buyer logic: companies already paying for the domain's keyword (Google Ads
advertisers) or competing for it organically are the most likely acquirers,
especially when their own domain only partially matches the keyword.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from .treg_client import TregClient, TregError

VOLUME_ENDPOINT = "treg.google.keywords.volume"
# SerpApi returns both the ad units and organic results; litescrape (cheaper) returned no ads in testing.
SERP_ENDPOINT = "serpapi.x.google-ads"
OVERVIEW_ENDPOINT = "spyfu.google.domain.overview"

# Approximate per-call USD from the public treg catalog (2026-11); used for the dry-run estimate only.
EST_USD = {VOLUME_ENDPOINT: 0.0018, SERP_ENDPOINT: 0.015, OVERVIEW_ENDPOINT: 0.001}

# Platforms that rank for everything and never buy a niche domain.
EXCLUDED_DOMAINS = {
    "google.com", "youtube.com", "wikipedia.org", "reddit.com", "linkedin.com", "facebook.com",
    "instagram.com", "x.com", "twitter.com", "amazon.com", "medium.com", "quora.com",
    "github.com", "apple.com", "microsoft.com", "forbes.com", "tiktok.com", "pinterest.com",
    "yelp.com", "g2.com", "capterra.com", "ibm.com", "gartner.com", "upwork.com", "fiverr.com",
}
_SECOND_LEVEL = {"co", "com", "org", "net", "ac", "gov", "edu"}


@dataclass
class Candidate:
    domain: str
    ad_hits: list[tuple[str, int]] = field(default_factory=list)  # (keyword, ad position)
    organic_hits: list[tuple[str, int]] = field(default_factory=list)  # (keyword, rank)
    titles: list[str] = field(default_factory=list)
    monthly_ad_budget: float | None = None
    monthly_organic_clicks: float | None = None
    score: int = 0
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "score": self.score,
            "reasons": self.reasons,
            "ad_hits": self.ad_hits,
            "organic_hits": self.organic_hits,
            "monthly_ad_budget": self.monthly_ad_budget,
            "monthly_organic_clicks": self.monthly_organic_clicks,
            "title": self.titles[0] if self.titles else None,
        }


def normalize_domain(value: str) -> str:
    value = value.strip().lower()
    host = urlparse(value if "://" in value else f"http://{value}").hostname or ""
    host = host.removeprefix("www.")
    labels = host.split(".")
    if len(labels) >= 3 and labels[-2] in _SECOND_LEVEL and len(labels[-1]) == 2:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:]) if len(labels) >= 2 else host


def keywords_for_domain(domain: str) -> list[str]:
    stem = normalize_domain(domain).split(".")[0]
    phrase = " ".join(part for part in re.split(r"[^a-z0-9]+", stem) if part)
    return [phrase] if phrase else []


def find_domain_buyers(
    client: TregClient,
    domain: str,
    keywords: list[str] | None = None,
    *,
    location: str = "United States",
    country: str = "us",
    enrich_top: int = 10,
) -> dict[str, Any]:
    offered = normalize_domain(domain)
    keywords = keywords or keywords_for_domain(offered)
    warnings: list[str] = []

    metrics: dict[str, dict[str, Any]] = {}
    try:
        metrics = parse_keyword_metrics(
            client.call(VOLUME_ENDPOINT, method="POST",
                        body={"keywords": keywords, "country": country, "language": "en"})
        )
    except TregError as error:
        warnings.append(str(error))

    candidates: dict[str, Candidate] = {}
    for keyword in keywords:
        try:
            serp = client.call(SERP_ENDPOINT, query={"engine": "google_ads", "q": keyword, "location": location,
                                       "gl": country, "hl": "en"})
        except TregError as error:
            warnings.append(str(error))
            continue
        collect_serp(serp, keyword, offered, candidates)

    ranked = rank_candidates(list(candidates.values()), keywords)
    for candidate in ranked[:enrich_top]:
        try:
            overview = client.call(OVERVIEW_ENDPOINT,
                                   query={"domain": candidate.domain, "pastNMonths": 1,
                                          "countryCode": country.upper()})
        except TregError as error:
            warnings.append(str(error))
            continue
        apply_overview(candidate, overview)
    ranked = rank_candidates(ranked, keywords)

    return {
        "domain": offered,
        "keywords": keywords,
        "keyword_metrics": metrics,
        "candidates": [c.as_dict() for c in ranked],
        "calls": client.calls,
        "spent_usd": round(client.spent_usd, 6),
        "warnings": warnings,
    }


def estimate_cost(keyword_count: int, enrich_top: int) -> float:
    return (EST_USD[VOLUME_ENDPOINT] + keyword_count * EST_USD[SERP_ENDPOINT]
            + enrich_top * EST_USD[OVERVIEW_ENDPOINT])


def parse_keyword_metrics(payload: Any) -> dict[str, dict[str, Any]]:
    """treg routed answer is {output: {rows: [...]}, raw, _treg}; row field names vary by provider."""
    rows = []
    if isinstance(payload, dict):
        output = payload.get("output")
        rows = (output.get("rows") if isinstance(output, dict) else None) or payload.get("rows") or []
    metrics = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        keyword = _first(row, "keyword", "key", "phrase", "text")
        if not keyword:
            continue
        metrics[str(keyword).lower()] = {
            "volume": _number(_first(row, "volume", "search_volume", "searchVolume", "avg_monthly_searches")),
            "cpc": _number(_first(row, "cpc", "CPC", "avg_cpc")),
            "competition": _first(row, "competition", "competition_level"),
        }
    return metrics


def collect_serp(serp: Any, keyword: str, offered: str, candidates: dict[str, Candidate]) -> None:
    if not isinstance(serp, dict):
        return
    for block in ("ads", "top_ads", "bottom_ads", "paid_results"):
        for index, ad in enumerate(serp.get(block) or [], start=1):
            domain = _result_domain(ad)
            if _keep(domain, offered):
                hit = candidates.setdefault(domain, Candidate(domain))
                hit.ad_hits.append((keyword, int(ad.get("position") or index)))
                _add_title(hit, ad)
    for index, result in enumerate(serp.get("organic_results") or [], start=1):
        domain = _result_domain(result)
        if _keep(domain, offered):
            hit = candidates.setdefault(domain, Candidate(domain))
            hit.organic_hits.append((keyword, int(result.get("position") or index)))
            _add_title(hit, result)


def apply_overview(candidate: Candidate, payload: Any) -> None:
    row = payload
    if isinstance(payload, dict) and isinstance(payload.get("results"), list):
        row = payload["results"][0] if payload["results"] else {}
    elif isinstance(payload, list):
        row = payload[0] if payload else {}
    if not isinstance(row, dict):
        return
    candidate.monthly_ad_budget = _number(_first(row, "monthlyBudget", "monthly_budget"))
    candidate.monthly_organic_clicks = _number(_first(row, "monthlyOrganicClicks", "monthly_organic_clicks"))


def rank_candidates(candidates: list[Candidate], keywords: list[str]) -> list[Candidate]:
    for candidate in candidates:
        score_candidate(candidate, keywords)
    return sorted(candidates, key=lambda c: (-c.score, c.domain))


def score_candidate(candidate: Candidate, keywords: list[str]) -> None:
    score, reasons = 0, []
    if candidate.ad_hits:
        best = min(position for _, position in candidate.ad_hits)
        score += 40 + (10 if best == 1 else 0)
        reasons.append(f"Buys Google Ads on the keyword (best ad slot #{best})")
    if candidate.organic_hits:
        best = min(position for _, position in candidate.organic_hits)
        score += 25 if best <= 3 else 15 if best <= 10 else 5
        reasons.append(f"Ranks organically for the keyword (#{best})")
    keyword_count = len({k for k, _ in candidate.ad_hits + candidate.organic_hits})
    if keyword_count > 1:
        score += 5 * (keyword_count - 1)
        reasons.append(f"Present on {keyword_count} keywords")

    match = name_match(candidate.domain, keywords)
    if match == "strong":
        score += 20
        reasons.append("Brand overlaps the keyword on a weaker domain — upgrade buyer")
    elif match == "partial":
        score += 8
        reasons.append("Brand partially overlaps the keyword")

    budget = candidate.monthly_ad_budget
    if budget:
        score += 20 if budget >= 10_000 else 10 if budget >= 1_000 else 5
        reasons.append(f"Est. Google Ads budget ${budget:,.0f}/mo")
    candidate.score, candidate.reasons = score, reasons


def name_match(domain: str, keywords: list[str]) -> str | None:
    stem = re.sub(r"[^a-z0-9]", "", domain.split(".")[0])
    best = None
    for keyword in keywords:
        compact = re.sub(r"[^a-z0-9]", "", keyword.lower())
        if compact and compact in stem:
            return "strong"
        if any(len(token) >= 4 and token in stem for token in keyword.lower().split()):
            best = "partial"
    return best


def _result_domain(result: Any) -> str:
    if not isinstance(result, dict):
        return ""
    for key in ("link", "displayed_link", "domain", "tracking_link"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return normalize_domain(value.split(" ")[0])
    return ""


def _keep(domain: str, offered: str) -> bool:
    return bool(domain) and "." in domain and domain != offered and domain not in EXCLUDED_DOMAINS


def _add_title(candidate: Candidate, result: dict) -> None:
    title = result.get("title")
    if isinstance(title, str) and title not in candidate.titles:
        candidate.titles.append(title)


def _first(row: dict, *keys: str) -> Any:
    for key in keys:
        if row.get(key) not in (None, ""):
            return row[key]
    return None


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
