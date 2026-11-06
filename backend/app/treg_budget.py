"""Spend guards for treg: a daily USD cap and a per-prospect cooldown, backed by a ledger.

Settings (environment or .env):
    DNGUN_TREG_DAILY_BUDGET_USD   default 2.00 — max spend per UTC day, UI and scripts combined
    DNGUN_TREG_COOLDOWN_MINUTES   default 10   — min gap between paid lookups of the same prospect
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models
from .repository import prefixed_id
from .schemas import utc_now_iso
from .treg_client import load_env_file


class BudgetError(RuntimeError):
    pass


def daily_budget() -> float:
    load_env_file()
    return float(os.environ.get("DNGUN_TREG_DAILY_BUDGET_USD", "2.0"))


def cooldown_minutes() -> float:
    load_env_file()
    return float(os.environ.get("DNGUN_TREG_COOLDOWN_MINUTES", "10"))


def spent_today(session: Session) -> float:
    day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    total = session.scalar(select(func.sum(models.TregSpendModel.spent_usd))
                           .where(models.TregSpendModel.created_at >= day_start))
    return float(total or 0.0)


def check_budget(session: Session, estimate_usd: float, prospect_id: str | None = None) -> None:
    """Raise BudgetError if this run could push today's spend over the cap, or the prospect was
    looked up within the cooldown. Uses the worst-case estimate, so the cap is never exceeded."""
    budget, spent = daily_budget(), spent_today(session)
    if spent + estimate_usd > budget:
        raise BudgetError(f"daily treg budget reached: spent ${spent:.4f} of ${budget:.2f}, this run may cost "
                          f"up to ${estimate_usd:.4f} (raise DNGUN_TREG_DAILY_BUDGET_USD to allow more)")
    if prospect_id:
        since = (datetime.now(timezone.utc) - timedelta(minutes=cooldown_minutes())).isoformat()
        recent = session.scalar(select(models.TregSpendModel.created_at)
                                .where(models.TregSpendModel.prospect_id == prospect_id,
                                       models.TregSpendModel.created_at >= since)
                                .order_by(models.TregSpendModel.created_at.desc()))
        if recent:
            raise BudgetError(f"prospect {prospect_id} was looked up at {recent[:19]}Z; wait "
                              f"{cooldown_minutes():g} min between lookups (DNGUN_TREG_COOLDOWN_MINUTES)")


def record_spend(session: Session, source: str, calls: int, spent_usd: float,
                 prospect_id: str | None = None) -> None:
    if not calls:
        return
    session.add(models.TregSpendModel(id=prefixed_id("TS"), source=source, prospect_id=prospect_id,
                                      calls=calls, spent_usd=spent_usd, created_at=utc_now_iso()))
    session.commit()
