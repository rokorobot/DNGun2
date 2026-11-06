"""Rank likely buyers for a domain offer from live Google Ads + organic data via treg.

    python backend/scripts/find_domain_buyers.py aiautomation.com                 # keyword derived: "ai automation"
    python backend/scripts/find_domain_buyers.py aiautomation.com -k "ai automation, ai agents" --expand 3
    python backend/scripts/find_domain_buyers.py aiautomation.com --no-big-advertisers
    python backend/scripts/find_domain_buyers.py aiautomation.com --save 10 --segment AI_AUTOMATION

Keywords: --keyword is repeatable and accepts comma-separated phrases. Without it the
domain is split into words via Google keyword data. --expand N adds the N related
keywords with the highest volume x CPC.

Read-only unless --save, which creates the top candidates as prospects (skipping ones
that exist) with their ad/ranking evidence as PENDING signal suggestions — review them
with backend/scripts/suggest_signals.py --list / --approve / --reject.

Needs TREG_TOKEN (environment or repo-root .env). --dry-run shows the cost estimate.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.domain_buyers import (  # noqa: E402
    DEFAULT_BIG_BUDGET,
    estimate_cost,
    find_domain_buyers,
    keywords_for_domain,
    split_keywords,
)
from backend.app.database import create_session_factory  # noqa: E402
from backend.app.repository import Repository  # noqa: E402
from backend.app.signal_suggestions import save_buyer_prospects  # noqa: E402
from backend.app.treg_budget import BudgetError, check_budget, record_spend  # noqa: E402
from backend.app.treg_client import TregClient, TregError  # noqa: E402



def main(argv: list[str] | None = None, db_path: Path | None = None, client: TregClient | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("domain")
    parser.add_argument("-k", "--keyword", action="append",
                        help="search phrase; repeatable and comma-separated. Default: derived from the domain")
    parser.add_argument("--expand", type=int, default=0, metavar="N",
                        help="also search the N related keywords with the highest volume x CPC")
    parser.add_argument("--big-advertisers", action=argparse.BooleanOptionalAction, default=True,
                        help="keep advertisers spending >= --big-budget/mo (default: keep)")
    parser.add_argument("--big-budget", type=float, default=DEFAULT_BIG_BUDGET, metavar="USD",
                        help=f"monthly Google Ads spend that marks a big advertiser (default {DEFAULT_BIG_BUDGET:,})")
    parser.add_argument("--location", default="United States", help="Google search location")
    parser.add_argument("--country", default="us", help="ISO country for volume/ad-budget data")
    parser.add_argument("--enrich", type=int, default=10, help="look up ad budget for the top N candidates")
    parser.add_argument("--limit", type=int, default=20, help="candidates to print")
    parser.add_argument("--save", type=int, default=0, metavar="N",
                        help="create the top N candidates as prospects with pending signal suggestions")
    parser.add_argument("--segment", help="segment code for saved prospects (required with --save)")
    parser.add_argument("--json", action="store_true", help="print the full result as JSON")
    parser.add_argument("--dry-run", action="store_true", help="show planned calls and cost, call nothing")
    parser.add_argument("--ignore-budget", action="store_true", help="skip the daily treg budget check")
    args = parser.parse_args(argv)

    keywords = split_keywords(args.keyword)
    derive = not keywords
    if derive and not keywords_for_domain(args.domain):
        parser.error("could not derive a keyword from the domain; pass --keyword")
    if args.save and not args.segment:
        parser.error("--save needs --segment (e.g. AI_AUTOMATION)")
    if args.dry_run:
        print(f"Keywords: {', '.join(keywords) if keywords else '(derived from ' + args.domain + ')'}"
              + (f" + up to {args.expand} related" if args.expand else ""))
        print(f"Big advertisers: {'kept' if args.big_advertisers else f'dropped at >= ${args.big_budget:,.0f}/mo'}")
        print(f"Estimated cost: ~${estimate_cost(max(len(keywords), 1), args.enrich, args.expand, derive):.4f}")
        return 0

    session = create_session_factory(db_path)()  # also holds the treg spend ledger
    try:
        if args.save and not Repository(session).get_segment_by_code(args.segment):
            print(f"unknown segment '{args.segment}'", file=sys.stderr)
            return 2
        if not args.ignore_budget:
            try:
                check_budget(session, estimate_cost(max(len(keywords), 1), args.enrich, args.expand, derive))
            except BudgetError as error:
                print(error, file=sys.stderr)
                return 3
        if client is None:
            try:
                client = TregClient.from_env()
            except TregError as error:
                print(error, file=sys.stderr)
                return 2
        try:
            result = find_domain_buyers(client, args.domain, keywords, location=args.location,
                                        country=args.country, enrich_top=args.enrich, expand=args.expand,
                                        big_budget=None if args.big_advertisers else args.big_budget)
        finally:
            record_spend(session, "cli.buyers", client.calls, client.spent_usd)
        if args.save:
            result["saved"] = save_buyer_prospects(session, result, args.segment, args.save)
    finally:
        session.close()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_report(result, args.limit)
    return 0 if result["candidates"] or not result["warnings"] else 1


def print_report(result: dict, limit: int) -> None:
    print(f"Domain: {result['domain']}   keywords: {', '.join(result['keywords'])}")
    if result["expanded_keywords"]:
        print(f"  + related: {', '.join(result['expanded_keywords'])}")
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
    if result["excluded_big_advertisers"]:
        dropped = ", ".join(f"{c['domain']} (${c['monthly_ad_budget']:,.0f}/mo)"
                            for c in result["excluded_big_advertisers"])
        print(f"\nDropped big advertisers: {dropped}")
    for row in result.get("saved", []):
        state = "created" if row["created"] else "exists"
        print(f"saved {row['domain']} -> {row['prospect_id']} ({state}), {row['suggestions']} new suggestion(s)")
    if result.get("saved"):
        print("Review: python backend/scripts/suggest_signals.py --list")
    for warning in result["warnings"]:
        print(f"warning: {warning}", file=sys.stderr)
    print(f"\n{result['calls']} treg calls, spent ${result['spent_usd']:.4f}")


def _fmt(value, digits: int = 0) -> str:
    return "?" if value is None else f"{value:,.{digits}f}"


if __name__ == "__main__":
    raise SystemExit(main())
