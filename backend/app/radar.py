from __future__ import annotations

import csv
import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Opportunity Radar engine (MVP 2.0). Pure functions plus one network call
# (fetch_gdelt). Rules live in rules/radar.yaml.
#
#   domain -> watch profile (keywords + markets) -> news queries
#   headline x profile -> match score with explanation lines
#
# News source: the GDELT DOC 2.0 API (free and open, commercial use allowed;
# one request per 5 seconds). Google News RSS is NOT used: its terms limit
# the feed to personal, non-commercial use.
# ---------------------------------------------------------------------------

RULES_PATH = Path(__file__).resolve().parent / "rules" / "radar.yaml"
GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_MIN_INTERVAL_SECONDS = 5.5
GDELT_RETRY_BACKOFF_SECONDS = (15, 30)  # waits before retrying a rate-limited request
GENERIC_TLD_MARKET = "GLOBAL"
MIN_KEYWORD_LENGTH = 3  # GDELT rejects shorter search terms

_DOMAIN_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$")


@lru_cache(maxsize=1)
def load_radar_rules(path: Path = RULES_PATH) -> dict:
    with path.open(encoding="utf-8") as handle:
        rules = yaml.safe_load(handle)
    for section in ("tld_markets", "markets", "regions", "event_terms", "events", "scoring", "vocabulary"):
        if section not in rules:
            raise ValueError(f"radar.yaml is missing section '{section}'")
    for event in rules["events"]:
        event["regex"] = re.compile(event["pattern"], re.IGNORECASE)
    rules["vocabulary"] = {
        str(word).lower() for word in rules["vocabulary"] + rules.get("vocabulary_extra", [])
    }
    return rules


# --- Portfolio parsing ------------------------------------------------------


def normalize_domain(raw: str) -> str | None:
    value = raw.strip().lower()
    value = re.sub(r"^[a-z]+://", "", value)
    value = value.split("/")[0].split("?")[0].strip(".")
    if value.startswith("www."):
        value = value[4:]
    return value if _DOMAIN_RE.match(value) else None


def _split_multi(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in re.split(r"[|/;,]", value) if part.strip()]


def parse_portfolio(text: str) -> tuple[list[dict], list[str]]:
    """Parse a pasted list or CSV (comma or semicolon). Returns (rows, invalid)."""
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return [], []
    first = lines[0].lower()
    delimiter = ";" if first.count(";") > first.count(",") else ","
    has_header = "domain" in first
    rows: list[dict] = []
    invalid: list[str] = []
    seen: set[str] = set()
    reader = csv.reader(io.StringIO("\n".join(lines)), delimiter=delimiter)
    header = [h.strip().lower() for h in next(reader)] if has_header else ["domain"]
    for record in reader:
        if not record or not record[0].strip():
            continue
        cells = dict(zip(header, record)) if has_header else {"domain": record[0]}
        domain = normalize_domain(cells.get("domain", ""))
        if domain is None:
            invalid.append(cells.get("domain", "").strip() or ",".join(record))
            continue
        if domain in seen:
            continue
        seen.add(domain)
        price_raw = (cells.get("price") or "").strip().replace(" ", "")
        price_raw = re.sub(r"[^0-9.,]", "", price_raw).replace(",", "")
        rows.append(
            {
                "domain": domain,
                "price": float(price_raw) if price_raw else None,
                "markets": _split_multi(cells.get("markets")),
                "keywords": _split_multi(cells.get("keywords")),
                "industry": (cells.get("industry") or "").strip() or None,
                "notes": (cells.get("notes") or "").strip() or None,
            }
        )
    return rows, invalid


# --- Watch profiles ---------------------------------------------------------


def split_tld(domain: str, rules: dict | None = None) -> tuple[str, str]:
    rules = rules or load_radar_rules()
    for tld in sorted(rules["tld_markets"], key=len, reverse=True):
        if domain.endswith("." + tld):
            return domain[: -len(tld) - 1], tld
    stem, _, tld = domain.rpartition(".")
    return stem, tld


def segment_words(stem: str, vocabulary: set[str]) -> list[str]:
    """Split a joined name into vocabulary words; unknown runs stay whole."""
    stem = stem.lower()
    n = len(stem)
    # best[i] = (unknown_chars, word_count, parts) for stem[:i]; fewer unknowns win.
    best: list[tuple[int, int, list[str]] | None] = [None] * (n + 1)
    best[0] = (0, 0, [])
    for i in range(n):
        if best[i] is None:
            continue
        unknown, count, parts = best[i]
        for j in range(i + 1, n + 1):
            piece = stem[i:j]
            known = piece in vocabulary
            candidate = (unknown + (0 if known else len(piece)), count + 1, parts + [piece])
            if best[j] is None or candidate[:2] < best[j][:2]:
                best[j] = candidate
    return best[n][2] if best[n] else [stem]


def build_watch_profile(
    domain: str,
    *,
    keywords: list[str] | None = None,
    markets: list[str] | None = None,
    industry: str | None = None,
    rules: dict | None = None,
) -> dict:
    """Keywords and markets for one domain; explicit values override the guess."""
    rules = rules or load_radar_rules()
    stem, tld = split_tld(domain.lower(), rules)
    if keywords:
        final_keywords = [k.lower() for k in keywords]
    else:
        parts = [p for chunk in re.split(r"[-.]", stem) for p in segment_words(chunk, rules["vocabulary"])]
        joined = stem.replace("-", "").replace(".", "")
        weak = set(rules.get("weak_words", []))
        final_keywords = [joined] + [p for p in parts if p != joined and p not in weak]
    if industry:
        final_keywords.append(industry.lower())
    final_keywords = list(dict.fromkeys(k for k in final_keywords if len(k) >= MIN_KEYWORD_LENGTH))
    return {
        "keywords": final_keywords or [stem],
        "markets": resolve_markets(markets, tld, rules),
        "industry": industry,
        "origin": "MANUAL" if (keywords or markets or industry) else "AUTO",
    }


def resolve_markets(markets: list[str] | None, tld: str, rules: dict | None = None) -> list[str]:
    rules = rules or load_radar_rules()
    if not markets:
        return [rules["tld_markets"].get(tld, GENERIC_TLD_MARKET)]
    resolved: list[str] = []
    for market in markets:
        code = market.strip().upper()
        if code in ("GLOBAL", "WORLD", "ALL"):
            resolved.append(GENERIC_TLD_MARKET)
        elif code in rules["regions"]:
            resolved.extend(rules["regions"][code])
        elif code in rules["markets"]:
            resolved.append(code)
        else:
            raise ValueError(f"Unknown market '{market}'")
    return list(dict.fromkeys(resolved))


# --- Queries and fetching ---------------------------------------------------


def _quote(term: str) -> str:
    return f'"{term}"' if " " in term else term


def _any_of(terms: list[str]) -> str:
    """GDELT allows parentheses only around OR'd terms, never around one term."""
    quoted = [_quote(t) for t in terms]
    return quoted[0] if len(quoted) == 1 else "(" + " OR ".join(quoted) + ")"


def build_queries(profile: dict, rules: dict | None = None) -> list[dict]:
    """One GDELT query per market: (keywords) (event terms) + source filters."""
    rules = rules or load_radar_rules()
    keyword_part = _any_of(profile["keywords"])
    queries = []
    for market in profile["markets"]:
        info = rules["markets"][market]
        language = info["language"]
        terms = list(dict.fromkeys(rules["event_terms"]["english"] + rules["event_terms"].get(language, [])))
        event_part = _any_of(terms)
        countries = info["countries"]
        country_part = ""
        if len(countries) == 1:
            country_part = f" sourcecountry:{countries[0]}"
        elif countries:
            country_part = " (" + " OR ".join(f"sourcecountry:{c}" for c in countries) + ")"
        queries.append({"market": market, "query": f"{keyword_part} {event_part}{country_part}"})
    return queries


def fetch_gdelt(query: str, *, timespan: str, max_records: int) -> list[dict]:
    params = urllib.parse.urlencode(
        {
            "query": query,
            "mode": "artlist",
            "format": "json",
            "maxrecords": max_records,
            "timespan": timespan,
            "sort": "datedesc",
        }
    )
    request = urllib.request.Request(f"{GDELT_URL}?{params}", headers={"User-Agent": "DNGun-radar/1.0"})
    for attempt, backoff in enumerate((*GDELT_RETRY_BACKOFF_SECONDS, None)):
        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                body = response.read().decode("utf-8", errors="replace").strip()
        except urllib.error.HTTPError as error:
            if error.code == 429 and backoff is not None:
                time.sleep(backoff)
                continue
            raise RuntimeError(f"GDELT HTTP {error.code}" + (" (rate limited, try later)" if error.code == 429 else "")) from error
        if body.startswith("{"):
            break
        # GDELT also answers rate limits and query errors with plain text.
        if "limit requests" in body.lower() and backoff is not None:
            time.sleep(backoff)
            continue
        raise RuntimeError(f"GDELT: {body[:200]}")
    articles = json.loads(body).get("articles", [])
    return [
        {
            "url": a.get("url"),
            "title": (a.get("title") or "").strip(),
            "source_domain": a.get("domain"),
            "source_country": a.get("sourcecountry"),
            "language": a.get("language"),
            "published_at": _gdelt_date(a.get("seendate")),
        }
        for a in articles
        if a.get("url") and a.get("title")
    ]


def _gdelt_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return None


class RateLimiter:
    def __init__(self, interval: float = GDELT_MIN_INTERVAL_SECONDS):
        self.interval = interval
        self._last = 0.0

    def wait(self) -> None:
        delay = self._last + self.interval - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        self._last = time.monotonic()


# --- Matching ---------------------------------------------------------------


@dataclass
class Match:
    score: int
    match_type: str  # NAME | KEYWORD
    event_type: str | None
    event_label: str | None
    event_tier: int | None
    company_name: str | None
    explanation: list[str] = field(default_factory=list)


_COMPANY_RE = re.compile(
    r"^(?:exclusive:\s*|breaking:\s*)?(?P<subject>.+?)\s+"
    r"(?:raises|raised|secures|closes|lands|bags|nets|launches|unveils|announces|rebrands|expands|"
    r"acquires|hires|appoints|emerges|gets|wins|opens|enters|introduces|debuts)\b",
    re.IGNORECASE,
)


def extract_company(title: str) -> str | None:
    """Best guess at the company a headline is about; the operator can edit it."""
    match = _COMPANY_RE.search(re.sub(r"\s+-\s+[^-]+$", "", title))
    if not match:
        return None
    words = match.group("subject").strip(" '\"‘’“”").split()
    # "Italian robotics startup Mosaico" -> keep the trailing capitalised run.
    tail: list[str] = []
    for word in reversed(words):
        if word[:1].isupper() or word[:1].isdigit():
            tail.insert(0, word)
        else:
            break
    name = " ".join(tail or words[-3:]).strip(",:;'’")
    return name or None


def _title_tokens(title: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", title.lower()) if t]


def match_headline(title: str, domain: str, profile: dict, rules: dict | None = None) -> Match | None:
    rules = rules or load_radar_rules()
    scoring = rules["scoring"]
    tokens = _title_tokens(title)
    stem, _ = split_tld(domain.lower(), rules)
    compact_stem = re.sub(r"[^a-z0-9]", "", stem)
    explanation: list[str] = []
    score = 0

    # A company carrying the domain's name in the headline is the strongest
    # buyer: e.g. "RobotStore raises seed" while we own robotstore.app.
    joined_pairs = {a + b for a, b in zip(tokens, tokens[1:])} | {
        a + b + c for a, b, c in zip(tokens, tokens[1:], tokens[2:])
    }
    name_hit = len(compact_stem) >= 4 and (compact_stem in tokens or compact_stem in joined_pairs)
    if name_hit:
        score += scoring["name_match"]
        explanation.append(f"Headline names a company called '{stem}' (+{scoring['name_match']}).")

    # Keywords only score on their own; with a name hit they would double count.
    keyword_hits = [] if name_hit else [
        k for k in profile["keywords"]
        if k != compact_stem and any(t == k or (len(k) >= 4 and t.startswith(k)) for t in tokens)
    ]
    if keyword_hits:
        points = min(len(keyword_hits) * scoring["keyword_hit"], scoring["keyword_cap"])
        score += points
        explanation.append(f"Domain keywords in headline: {', '.join(keyword_hits)} (+{points}).")

    if not name_hit and not keyword_hits:
        return None

    event = next((e for e in rules["events"] if e["regex"].search(title)), None)
    if event:
        score += event["weight"]
        explanation.append(f"Event: {event['label']} (+{event['weight']}).")
    elif not name_hit:
        return None  # a keyword without a company event is just topical news
    else:
        explanation.append("No company event detected (+0).")

    if score < scoring["min_score"]:
        return None
    explanation.append(f"Match score: {score}.")
    return Match(
        score=score,
        match_type="NAME" if name_hit else "KEYWORD",
        event_type=event["type"] if event else None,
        event_label=event["label"] if event else None,
        event_tier=event["tier"] if event else None,
        company_name=extract_company(title),
        explanation=explanation,
    )
