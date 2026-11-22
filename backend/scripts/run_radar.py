"""Scan the news for every domain in the portfolio (the daily radar job).

    python backend/scripts/run_radar.py            # all domains
    python backend/scripts/run_radar.py robotstore.app solarlease.de

Respects GDELT's limit of one request per 5 seconds, so a large portfolio
takes a few minutes. New matches appear under Radar > Opportunities.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import func, select

from backend.app import models
from backend.app.database import create_session_factory
from backend.app.radar_service import RadarService


def main(domains: list[str]) -> int:
    with create_session_factory()() as session:
        offer_ids = None
        if domains:
            offer_ids = []
            for domain in domains:
                offer = session.scalar(
                    select(models.OfferModel).where(func.lower(models.OfferModel.name) == domain.lower())
                )
                if offer is None:
                    print(f"Not in portfolio: {domain}")
                    return 1
                offer_ids.append(offer.id)
        summary = RadarService(session).scan(offer_ids)
    print(
        f"Scanned {summary['domains']} domain(s), {summary['queries']} query(ies), "
        f"{summary['articles']} article(s): {summary['new_opportunities']} new opportunity(ies)."
    )
    for error in summary["errors"]:
        print(f"  error: {error}")
    return 1 if summary["errors"] and not summary["articles"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
