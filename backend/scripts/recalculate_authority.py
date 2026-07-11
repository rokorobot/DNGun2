from __future__ import annotations

import sys
from pathlib import Path

# Add backend directory to path so we can resolve config/imports if needed
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app import models
from app.authority_engine import AuthorityScoringEngine
from app.database import create_session_factory
from app.rules import RuleRegistry
from app.schemas import utc_now_iso


def recalculate_decision_maker_authority(db_path: Path | None = None) -> dict[str, int]:
    """
    Recompute authority score and acquisition rationale for every stored
    decision maker from the current rule registry. Scores are persisted at
    write time, so records created before a matcher or rule change may hold
    stale values until re-saved or recalculated here.

    Updates only records whose score or rationale actually changed and
    returns {"scanned": n, "updated": n}. Maintenance utility — never run
    automatically at startup.
    """
    session_factory = create_session_factory(db_path)
    engine = AuthorityScoringEngine(RuleRegistry())
    scanned = 0
    updated = 0
    with session_factory() as session:
        rows = session.scalars(select(models.DecisionMakerModel)).all()
        for row in rows:
            scanned += 1
            score, rationale = engine.calculate(row.role)
            if row.authority_score != score or row.acquisition_rationale != rationale:
                row.authority_score = score
                row.acquisition_rationale = rationale
                row.updated_at = utc_now_iso()
                updated += 1
        session.commit()
    return {"scanned": scanned, "updated": updated}


if __name__ == "__main__":
    result = recalculate_decision_maker_authority()
    print(f"Decision makers scanned: {result['scanned']}")
    print(f"Decision makers updated: {result['updated']}")
