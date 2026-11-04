"""Rank likely buyers for a domain offer from live Google Ads + organic data via treg.

    python backend/scripts/find_domain_buyers.py aiautomation.com --keyword "ai automation"

Needs TREG_TOKEN (read from the environment or the repo-root .env). Read-only:
prints candidates, writes nothing to the DNGun database. Use --dry-run to see the
planned calls and estimated cost without spending anything.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.domain_buyers import estimate_cost, find_domain_buyers, keywords_for_domain  # noqa: E402
from backend.app.treg_client import TregClient, TregError  # noqa: E402


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip().removeprefix("export "), value.strip().strip("'\""))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("domain")
    parser.add_argument("--keyword", action="append", help="search phrase (repeatable); default derives from the domain")
    parser.add_argument("--location", default="United States", help="Google search location")
    parser.add_argument("--country", default="us", help="ISO country for volume/ad-budget data")
    parser.add_argument("--enrich", type=int, default=10, help="look up ad budget for the top N candidates")
    parser.add_argument("--limit", type=int, default=20, help="candidates to print")
    parser.add_argument("--json", action="store_true", help="print the full result as JSON")
    parser.add_argument("--dry-run", action="store_true", help="show planned calls and cost, call nothing")
    args = parser.parse_args(argv)

    keywords = args.keyword or keywords_for_domain(args.domain)
    if not keywords:
        parser.error("could not derive a keyword from the domain; pass --keyword")
    estimate = estimate_cost(len(keywords), args.enrich)
    if args.dry_run:
        print(f"Keywords: {', '.join(keywords)}")
        print(f"Calls: 1 volume + {len(keywords)} SERP + up to {args.enrich} ad-budget lookups")
        print(f"Estimated cost: ~${estimate:.4f}")
        return 0

    load_env(ROOT / ".env")
    try:
        client = TregClient.from_env()
    except TregError as error:
        print(error, file=sys.stderr)
        return 2

    result = find_domain_buyers(client, args.domain, keywords, location=args.location,
                                country=args.country, enrich_top=args.enrich)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_report(result, args.limit)
    return 0 if result["candidates"] or not result["warnings"] else 1


def print_report(result: dict, limit: int) -> None:
    print(f"Domain: {result['domain']}   keywords: {', '.join(result['keywords'])}")
    for keyword, metric in result["keyword_metrics"].items():
        print(f"  '{keyword}': volume {_fmt(metric['volume'])}/mo, CPC ${_fmt(metric['cpc'], 2)}")
    print()
    candidates = result["candidates"][:limit]
    if not candidates:
        print("No candidate buyers found.")
    for rank, candidate in enumerate(candidates, start=1):
        print(f"{rank:>2}. {candidate['domain']:<32} score {candidate['score']}")
        for reason in candidate["reasons"]:
            print(f"      - {reason}")
    for warning in result["warnings"]:
        print(f"warning: {warning}", file=sys.stderr)
    print(f"\n{result['calls']} treg calls, spent ${result['spent_usd']:.4f}")


def _fmt(value, digits: int = 0) -> str:
    return "?" if value is None else f"{value:,.{digits}f}"


if __name__ == "__main__":
    raise SystemExit(main())
