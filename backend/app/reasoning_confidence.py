from __future__ import annotations

import re
from datetime import datetime
from typing import Any

# ---------------------------------------------------------------------------
# Deterministic reasoning-confidence rubric (MVP 1.3, ratified ruling 1).
#
# reasoning_confidence measures the strength and completeness of the CURRENT
# supporting evidence. It is computed only from linked evidence — never
# hand-set, never LLM-set, never moved by approval — and every computation
# emits explanation lines sufficient to reconstruct the score.
#
# Evidence-state rules:
#   ACTIVE     counts in every positive factor.
#   ARCHIVED   counts in count/diversity/relevance/coverage, never in recency.
#   RETRACTED / INVALIDATED contribute nothing positive; each such link is
#              withdrawn support and draws a penalty.
#
# Maximum achievable score: 10 + 36 + 18 + 12 + 8 + 6 + 10 = 100.
# ---------------------------------------------------------------------------

BASE_SUPPORT_POINTS = 10

COUNT_WEIGHTS = (12, 9, 7, 5, 3)  # diminishing returns; entries beyond 5 add 0

DIVERSITY_POINTS_PER_TYPE = 6  # per distinct evidence_type beyond the first
DIVERSITY_CAP = 18

RECENCY_WINDOW_DAYS = 90
RECENCY_POINTS_PER_ENTRY = 4  # ACTIVE entries only
RECENCY_CAP = 12

OFFER_RELEVANCE_POINTS = 8  # any countable entry references the offer
PROSPECT_RELEVANCE_POINTS = 6  # any countable entry matches the prospect's PDM

DM_COVERAGE_POINTS = 10  # countable evidence mentions the decision maker

STALE_AGE_DAYS = 365
STALE_PENALTY_PER_ENTRY = 3
STALE_PENALTY_CAP = 9

WEAK_SOURCE_PENALTY_PER_ENTRY = 2  # countable entry without a source
WEAK_SOURCE_PENALTY_CAP = 6

WITHDRAWN_PENALTY_PER_LINK = 8  # RETRACTED / INVALIDATED linked evidence
WITHDRAWN_PENALTY_CAP = 16

_COUNTABLE_STATUSES = {"ACTIVE", "ARCHIVED"}
_WITHDRAWN_STATUSES = {"RETRACTED", "INVALIDATED"}
_STOPWORDS = {"a", "an", "and", "at", "for", "in", "of", "on", "or", "the", "to"}


def _tokens(value: str) -> set[str]:
    raw = re.split(r"[^a-z0-9]+", value.lower())
    return {token for token in raw if len(token) >= 2 and token not in _STOPWORDS}


def _age_days(created_at: str, now: datetime) -> int:
    return (now - datetime.fromisoformat(created_at)).days


def compute_reasoning_confidence(
    evidence_entries: list[Any],
    *,
    offer_id: str,
    prospect_pdm_code: str | None,
    decision_maker_text: str | None,
    now: datetime,
) -> tuple[int, list[str]]:
    """
    Compute (score, explanation_lines) for a hypothesis from its linked
    evidence entries. Deterministic: entries are canonically ordered by
    (created_at, id) before any per-entry weighting, so caller iteration
    order never affects the result.
    """
    countable = sorted(
        (entry for entry in evidence_entries if entry.status in _COUNTABLE_STATUSES),
        key=lambda entry: (entry.created_at, entry.id),
    )
    withdrawn = sorted(
        (entry for entry in evidence_entries if entry.status in _WITHDRAWN_STATUSES),
        key=lambda entry: (entry.created_at, entry.id),
    )

    lines: list[str] = []

    base = BASE_SUPPORT_POINTS if countable else 0
    lines.append(f"Base support: {len(countable)} countable evidence link(s) (+{base}).")

    count_points = sum(COUNT_WEIGHTS[: len(countable)])
    lines.append(
        f"Evidence count: {len(countable)} countable link(s), diminishing returns (+{count_points})."
    )

    distinct_types = {entry.evidence_type for entry in countable}
    diversity = min(
        max(len(distinct_types) - 1, 0) * DIVERSITY_POINTS_PER_TYPE, DIVERSITY_CAP
    )
    lines.append(
        f"Type diversity: {len(distinct_types)} distinct evidence type(s) (+{diversity})."
    )

    recent = [
        entry
        for entry in countable
        if entry.status == "ACTIVE" and _age_days(entry.created_at, now) <= RECENCY_WINDOW_DAYS
    ]
    recency = min(len(recent) * RECENCY_POINTS_PER_ENTRY, RECENCY_CAP)
    lines.append(
        f"Recency: {len(recent)} ACTIVE entry(ies) within {RECENCY_WINDOW_DAYS} days (+{recency})."
    )

    offer_relevant = any(entry.offer_id == offer_id for entry in countable if entry.offer_id)
    offer_points = OFFER_RELEVANCE_POINTS if offer_relevant else 0
    lines.append(
        "Offer relevance: linked evidence references this offer"
        f" (+{offer_points})."
        if offer_relevant
        else "Offer relevance: no linked evidence references this offer (+0)."
    )

    prospect_relevant = bool(prospect_pdm_code) and any(
        entry.pdm_code == prospect_pdm_code for entry in countable if entry.pdm_code
    )
    prospect_points = PROSPECT_RELEVANCE_POINTS if prospect_relevant else 0
    lines.append(
        "Prospect relevance: linked evidence matches the prospect's PDM"
        f" (+{prospect_points})."
        if prospect_relevant
        else "Prospect relevance: no linked evidence matches the prospect's PDM (+0)."
    )

    if decision_maker_text is None:
        dm_points = 0
        lines.append("Decision-maker coverage: not applicable, no decision-maker refinement (+0).")
    else:
        dm_tokens = _tokens(decision_maker_text)
        covered = any(
            dm_tokens & _tokens(f"{entry.evidence} {entry.signal_code or ''}")
            for entry in countable
        )
        dm_points = DM_COVERAGE_POINTS if covered else 0
        lines.append(
            f"Decision-maker coverage: countable evidence mentions the decision maker (+{dm_points})."
            if covered
            else "Decision-maker coverage: no countable evidence mentions the decision maker (+0)."
        )

    stale_count = sum(
        1 for entry in countable if _age_days(entry.created_at, now) > STALE_AGE_DAYS
    )
    stale_penalty = min(stale_count * STALE_PENALTY_PER_ENTRY, STALE_PENALTY_CAP)
    lines.append(
        f"Stale-evidence penalty: {stale_count} entry(ies) older than {STALE_AGE_DAYS} days (-{stale_penalty})."
    )

    weak_count = sum(1 for entry in countable if not entry.source)
    weak_penalty = min(weak_count * WEAK_SOURCE_PENALTY_PER_ENTRY, WEAK_SOURCE_PENALTY_CAP)
    lines.append(
        f"Weak-source penalty: {weak_count} entry(ies) without a source (-{weak_penalty})."
    )

    withdrawn_penalty = min(
        len(withdrawn) * WITHDRAWN_PENALTY_PER_LINK, WITHDRAWN_PENALTY_CAP
    )
    lines.append(
        f"Withdrawn-evidence penalty: {len(withdrawn)} RETRACTED/INVALIDATED link(s) (-{withdrawn_penalty})."
    )

    total = (
        base
        + count_points
        + diversity
        + recency
        + offer_points
        + prospect_points
        + dm_points
        - stale_penalty
        - weak_penalty
        - withdrawn_penalty
    )
    score = max(0, min(100, total))
    lines.append(f"Reasoning confidence: {score}/100.")
    return score, lines
