"""Suggest signals for a prospect from external data (via treg), then approve or reject them.

    python backend/scripts/suggest_signals.py P-123            # look up + store PENDING suggestions
    python backend/scripts/suggest_signals.py P-123 --dry-run  # planned lookups + max cost, no calls
    python backend/scripts/suggest_signals.py --list [P-123]   # pending suggestions
    python backend/scripts/suggest_signals.py --approve SS-1 SS-2
    python backend/scripts/suggest_signals.py --reject SS-3

Approving creates a real signal (it then counts in scoring); rejecting keeps the
suggestion from being proposed again. Needs TREG_TOKEN (env or repo-root .env).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.database import create_session_factory  # noqa: E402
from backend.app.repository import Repository  # noqa: E402
from backend.app.signal_suggestions import (  # noqa: E402
    estimate_cost,
    gather_suggestions,
    list_suggestions,
    planned_lookups,
    review_suggestion,
    save_suggestions,
)
from backend.app.treg_budget import BudgetError, check_budget, record_spend  # noqa: E402
from backend.app.treg_client import TregClient, TregError  # noqa: E402


def main(argv: list[str] | None = None, db_path: Path | None = None, client: TregClient | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("prospect_id", nargs="?")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--list", action="store_true", help="list pending suggestions")
    parser.add_argument("--approve", nargs="+", metavar="ID")
    parser.add_argument("--reject", nargs="+", metavar="ID")
    parser.add_argument("--ignore-budget", action="store_true",
                        help="skip the daily treg budget and per-prospect cooldown checks")
    args = parser.parse_args(argv)

    session = create_session_factory(db_path)()
    try:
        if args.list:
            print_suggestions(list_suggestions(session, args.prospect_id))
            return 0
        if args.approve or args.reject:
            failed = 0
            for ids, approve in ((args.approve or [], True), (args.reject or [], False)):
                for suggestion_id in ids:
                    try:
                        s = review_suggestion(session, suggestion_id, approve)
                        print(f"{s.id}: {s.status}" + (f" → signal {s.signal_id}" if s.signal_id else ""))
                    except ValueError as error:
                        print(error, file=sys.stderr)
                        failed += 1
            return 1 if failed else 0
        if not args.prospect_id:
            parser.error("give a prospect id, or --list / --approve / --reject")

        prospect = Repository(session).get_prospect(args.prospect_id)
        if prospect is None:
            print(f"prospect {args.prospect_id} not found", file=sys.stderr)
            return 2
        if args.dry_run:
            for endpoint, body in planned_lookups(prospect):
                print(f"  {endpoint} {body}")
            print(f"Max cost: ~${estimate_cost(prospect):.3f}")
            return 0

        if not args.ignore_budget:
            try:
                check_budget(session, estimate_cost(prospect), prospect.id)
            except BudgetError as error:
                print(error, file=sys.stderr)
                return 3
        if client is None:
            try:
                client = TregClient.from_env()
            except TregError as error:
                print(error, file=sys.stderr)
                return 2
            client.timeout = 60
        try:
            suggestions, warnings = gather_suggestions(client, prospect)
        finally:
            record_spend(session, "cli.suggest", client.calls, client.spent_usd, prospect.id)
        created = save_suggestions(session, prospect.id, suggestions)
        print(f"{prospect.company_name}: {len(created)} new suggestion(s)"
              f" ({len(suggestions) - len(created)} already known)")
        print_suggestions(created)
        for warning in warnings:
            print(f"warning: {warning}", file=sys.stderr)
        print(f"{client.calls} treg calls, spent ${client.spent_usd:.4f}")
        if created:
            print("Review: --approve <id> ... / --reject <id> ...")
        return 0
    finally:
        session.close()


def print_suggestions(suggestions) -> None:
    if not suggestions:
        print("No pending suggestions.")
    for s in suggestions:
        print(f"{s.id}  [{s.prospect_id}] T{s.tier} {s.signal_type} (score {s.score})")
        print(f"      {s.notes}")
        if s.source_url:
            print(f"      source: {s.source_url}")


if __name__ == "__main__":
    raise SystemExit(main())
