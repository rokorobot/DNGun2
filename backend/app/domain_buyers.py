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
IDEAS_ENDPOINT = "treg.google.keywords.ideas"
# SerpApi returns both the ad units and organic results; litescrape (cheaper) returned no ads in testing.
SERP_ENDPOINT = "serpapi.x.google-ads"
OVERVIEW_ENDPOINT = "spyfu.google.domain.overview"

# Approximate USD from the public treg catalog (2026-11); used for the dry-run estimate only.
# Keyword volume bills per keyword.
EST_USD = {VOLUME_ENDPOINT: 0.0018, IDEAS_ENDPOINT: 0.001, SERP_ENDPOINT: 0.015, OVERVIEW_ENDPOINT: 0.001}
MAX_IDEA_CANDIDATES = 15  # related keywords priced per expansion seed before picking the best
MAX_SPLITS = 12  # two-word splits of an unsegmented stem checked for search volume
DEFAULT_BIG_BUDGET = 100_000  # monthly Google Ads $ above which an advertiser counts as a big brand

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
    names: list[str] = field(default_factory=list)  # advertiser / site names Google shows
    monthly_ad_budget: float | None = None
    monthly_organic_clicks: float | None = None
    score: int = 0
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "name": self.names[0] if self.names else None,
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
    """Offline guess: the domain stem with separators turned into spaces."""
    stem = normalize_domain(domain).split(".")[0]
    phrase = " ".join(part for part in re.split(r"[^a-z0-9]+", stem) if part)
    return [phrase] if phrase else []


def split_keywords(values: list[str] | None) -> list[str]:
    """Accept repeated and comma-separated --keyword values; lowercase and dedupe, keeping order."""
    seen: dict[str, None] = {}
    for value in values or []:
        for part in value.split(","):
            phrase = " ".join(part.lower().split())
            if phrase:
                seen.setdefault(phrase, None)
    return list(seen)


def find_domain_buyers(
    client: TregClient,
    domain: str,
    keywords: list[str] | None = None,
    *,
    location: str = "United States",
    country: str = "us",
    enrich_top: int = 10,
    expand: int = 0,
    big_budget: float | None = None,
) -> dict[str, Any]:
    """Rank buyer candidates. `expand` adds that many related high-value keywords; `big_budget`
    drops advertisers whose monthly Google Ads spend is at or above it (None keeps everyone)."""
    offered = normalize_domain(domain)
    warnings: list[str] = []
    keywords = split_keywords(keywords) or derive_keywords(client, offered, country, warnings)

    ideas: list[str] = []
    if expand > 0:
        for keyword in keywords:
            ideas += [idea for idea in related_keywords(client, keyword, country, warnings)
                      if idea not in keywords and idea not in ideas]
        ideas = ideas[:MAX_IDEA_CANDIDATES]

    metrics: dict[str, dict[str, Any]] = {}
    try:
        metrics = parse_keyword_metrics(
            client.call(VOLUME_ENDPOINT, method="POST",
                        body={"keywords": keywords + ideas, "country": country, "language": "en"})
        )
    except TregError as error:
        warnings.append(str(error))
    expansions = pick_expansions(ideas, metrics, expand)
    searched = keywords + expansions

    candidates: dict[str, Candidate] = {}
    for keyword in searched:
        try:
            serp = client.call(SERP_ENDPOINT, query={"engine": "google_ads", "q": keyword, "location": location,
                                                     "gl": country, "hl": "en"})
        except TregError as error:
            warnings.append(str(error))
            continue
        collect_serp(serp, keyword, offered, candidates)

    ranked = rank_candidates(list(candidates.values()), searched)
    for candidate in ranked[:enrich_top]:
        try:
            overview = client.call(OVERVIEW_ENDPOINT,
                                   query={"domain": candidate.domain, "pastNMonths": 1,
                                          "countryCode": country.upper()})
        except TregError as error:
            warnings.append(str(error))
            continue
        apply_overview(candidate, overview)
    ranked = rank_candidates(ranked, searched)

    excluded = []
    if big_budget is not None:
        excluded = [c for c in ranked if (c.monthly_ad_budget or 0) >= big_budget]
        ranked = [c for c in ranked if c not in excluded]

    return {
        "domain": offered,
        "keywords": keywords,
        "expanded_keywords": expansions,
        "keyword_metrics": {k: metrics[k] for k in searched if k in metrics},
        "candidates": [c.as_dict() for c in ranked],
        "excluded_big_advertisers": [
            {"domain": c.domain, "monthly_ad_budget": c.monthly_ad_budget} for c in excluded],
        "calls": client.calls,
        "spent_usd": round(client.spent_usd, 6),
        "warnings": warnings,
    }


def derive_keywords(client: TregClient, offered: str, country: str, warnings: list[str]) -> list[str]:
    """Turn the domain stem into a search phrase: 'aiautomation' -> 'ai automation'.

    1. Google keyword ideas for the stem; an idea that equals the stem once spaces are removed
       is the segmentation Google itself uses.
    2. Otherwise price every two-word split and keep the one people search most.
    3. Otherwise fall back to the stem with separators replaced by spaces.
    """
    fallback = keywords_for_domain(offered)
    if not fallback:
        return []
    phrase = fallback[0]
    if " " in phrase:
        return fallback
    for idea in related_keywords(client, phrase, country, warnings, on_topic=False):
        if " " in idea and idea.replace(" ", "") == phrase:
            return [idea]
    splits = [f"{phrase[:i]} {phrase[i:]}" for i in range(2, len(phrase) - 1)][:MAX_SPLITS]
    if not splits:
        return fallback
    try:
        metrics = parse_keyword_metrics(client.call(
            VOLUME_ENDPOINT, method="POST",
            body={"keywords": [phrase] + splits, "country": country, "language": "en"}))
    except TregError as error:
        warnings.append(str(error))
        return fallback
    best = max([phrase] + splits, key=lambda k: (metrics.get(k) or {}).get("volume") or 0)
    return [best] if (metrics.get(best) or {}).get("volume") else fallback


def related_keywords(client: TregClient, keyword: str, country: str, warnings: list[str],
                     *, on_topic: bool = True) -> list[str]:
    """Google keyword ideas for a seed. With on_topic, keep only ideas containing every seed word."""
    try:
        payload = client.call(IDEAS_ENDPOINT, method="POST",
                              body={"keyword": keyword, "country": country, "language": "en", "limit": 30})
    except TregError as error:
        warnings.append(str(error))
        return []
    output = payload.get("output") if isinstance(payload, dict) else None
    rows = (output or {}).get("keywords") or []
    words = keyword.lower().split()
    ideas: list[str] = []
    for row in rows:
        idea = row if isinstance(row, str) else (_first(row, "value", "keyword", "phrase", "text")
                                                 if isinstance(row, dict) else None)
        if not isinstance(idea, str):
            continue
        idea = " ".join(idea.lower().split())
        if idea and idea != keyword.lower() and idea not in ideas and (
                not on_topic or all(word in idea.split() for word in words)):
            ideas.append(idea)
    return ideas


def pick_expansions(ideas: list[str], metrics: dict[str, dict[str, Any]], count: int) -> list[str]:
    """Most commercially valuable ideas: monthly volume x CPC, skipping ones nobody pays for."""
    def value(idea: str) -> float:
        metric = metrics.get(idea) or {}
        return (metric.get("volume") or 0) * (metric.get("cpc") or 0)
    return [idea for idea in sorted(ideas, key=value, reverse=True) if value(idea) > 0][:count]


def estimate_cost(keyword_count: int, enrich_top: int, expand: int = 0, derive: bool = False) -> float:
    volume_rows = keyword_count + (MAX_IDEA_CANDIDATES if expand else 0)
    cost = volume_rows * EST_USD[VOLUME_ENDPOINT] + enrich_top * EST_USD[OVERVIEW_ENDPOINT]
    cost += (keyword_count + expand) * EST_USD[SERP_ENDPOINT]
    if expand:
        cost += keyword_count * EST_USD[IDEAS_ENDPOINT]
    if derive:
        cost += EST_USD[IDEAS_ENDPOINT] + (MAX_SPLITS + 1) * EST_USD[VOLUME_ENDPOINT]
    return cost


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
    name = result.get("source")
    if isinstance(name, str) and name.strip() and not name.startswith(("›", "http")) \
            and name not in candidate.names:
        candidate.names.append(name.strip())


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
