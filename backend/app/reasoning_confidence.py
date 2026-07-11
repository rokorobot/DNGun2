from __future__ import annotations

import re
from datetime import datetime
from typing import Any

# ---------------------------------------------------------------------------
# Deterministic reasoning-confidence rubric (MVP 1.3, ratified ruling 1 and
# remediation rulings R3/R4).
#
# reasoning_confidence measures the strength and completeness of the CURRENT
# supporting evidence. It is computed only from linked evidence — never
# hand-set, never LLM-set, never moved by approval — and every computation
# emits explanation lines sufficient to reconstruct the score.
#
# Evidence-state eligibility (remediation rulings R3/R4):
#   ACTIVE     the only state that contributes positive factors, and the
#              only state subject to the stale / weak-source penalties.
#   ARCHIVED   historically retained but scoring-neutral: no positive
#              factors, no penalties, and it cannot satisfy activation.
#   RETRACTED / INVALIDATED contribute nothing positive; each such link
#              incurs the disqualified-evidence penalty. The penalty
#              reflects reliance on support that was subsequently withdrawn
#              or invalidated — it does NOT assert the evidence disproves
#              the hypothesis. True contradictory-evidence scoring is
#              deferred until evidence polarity is representable.
#
# Duplicate inputs are deduplicated by evidence id before scoring; repeated
# objects can never inflate the result (the repository's unique link
# constraint remains the primary domain guarantee).
#
# Maximum achievable score: 10 + 36 + 18 + 12 + 8 + 6 + 10 = 100.
# ---------------------------------------------------------------------------

BASE_SUPPORT_POINTS = 10

COUNT_WEIGHTS = (12, 9, 7, 5, 3)  # diminishing returns; entries beyond 5 add 0

DIVERSITY_POINTS_PER_TYPE = 6  # per distinct evidence_type beyond the first
DIVERSITY_CAP = 18

RECENCY_WINDOW_DAYS = 90
RECENCY_POINTS_PER_ENTRY = 4
RECENCY_CAP = 12

OFFER_RELEVANCE_POINTS = 8  # any ACTIVE entry references the offer
PROSPECT_RELEVANCE_POINTS = 6  # any ACTIVE entry matches the prospect's PDM

DM_COVERAGE_POINTS = 10  # ACTIVE evidence mentions the decision maker

STALE_AGE_DAYS = 365
STALE_PENALTY_PER_ENTRY = 3
STALE_PENALTY_CAP = 9

WEAK_SOURCE_PENALTY_PER_ENTRY = 2  # ACTIVE entry without a source
WEAK_SOURCE_PENALTY_CAP = 6

DISQUALIFIED_PENALTY_PER_LINK = 8  # RETRACTED / INVALIDATED linked evidence
DISQUALIFIED_PENALTY_CAP = 16

_DISQUALIFIED_STATUSES = {"RETRACTED", "INVALIDATED"}
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
    evidence entries. Deterministic: entries are deduplicated by id and
    canonically ordered by (created_at, id) before any per-entry weighting,
    so caller iteration order and repeated inputs never affect the result.
    """
    seen_ids: set[str] = set()
    unique_entries = []
    for entry in sorted(evidence_entries, key=lambda item: (item.created_at, item.id)):
        if entry.id not in seen_ids:
            seen_ids.add(entry.id)
            unique_entries.append(entry)

    scorable = [entry for entry in unique_entries if entry.status == "ACTIVE"]
    archived = [entry for entry in unique_entries if entry.status == "ARCHIVED"]
    disqualified = [
        entry for entry in unique_entries if entry.status in _DISQUALIFIED_STATUSES
    ]

    lines: list[str] = []

    base = BASE_SUPPORT_POINTS if scorable else 0
    lines.append(f"Base support: {len(scorable)} ACTIVE evidence link(s) (+{base}).")

    count_points = sum(COUNT_WEIGHTS[: len(scorable)])
    lines.append(
        f"Evidence count: {len(scorable)} ACTIVE link(s), diminishing returns (+{count_points})."
    )

    distinct_types = {entry.evidence_type for entry in scorable}
    diversity = min(
        max(len(distinct_types) - 1, 0) * DIVERSITY_POINTS_PER_TYPE, DIVERSITY_CAP
    )
    lines.append(
        f"Type diversity: {len(distinct_types)} distinct evidence type(s) among ACTIVE links (+{diversity})."
    )

    recent = [
        entry
        for entry in scorable
        if _age_days(entry.created_at, now) <= RECENCY_WINDOW_DAYS
    ]
    recency = min(len(recent) * RECENCY_POINTS_PER_ENTRY, RECENCY_CAP)
    lines.append(
        f"Recency: {len(recent)} ACTIVE entry(ies) within {RECENCY_WINDOW_DAYS} days (+{recency})."
    )

    offer_relevant = any(entry.offer_id == offer_id for entry in scorable if entry.offer_id)
    offer_points = OFFER_RELEVANCE_POINTS if offer_relevant else 0
    lines.append(
        f"Offer relevance: ACTIVE evidence references this offer (+{offer_points})."
        if offer_relevant
        else "Offer relevance: no ACTIVE evidence references this offer (+0)."
    )

    prospect_relevant = bool(prospect_pdm_code) and any(
        entry.pdm_code == prospect_pdm_code for entry in scorable if entry.pdm_code
    )
    prospect_points = PROSPECT_RELEVANCE_POINTS if prospect_relevant else 0
    lines.append(
        f"Prospect relevance: ACTIVE evidence matches the prospect's PDM (+{prospect_points})."
        if prospect_relevant
        else "Prospect relevance: no ACTIVE evidence matches the prospect's PDM (+0)."
    )

    if decision_maker_text is None:
        dm_points = 0
        lines.append("Decision-maker coverage: not applicable, no decision-maker refinement (+0).")
    else:
        dm_tokens = _tokens(decision_maker_text)
        covered = any(
            dm_tokens & _tokens(f"{entry.evidence} {entry.signal_code or ''}")
            for entry in scorable
        )
        dm_points = DM_COVERAGE_POINTS if covered else 0
        lines.append(
            f"Decision-maker coverage: ACTIVE evidence mentions the decision maker (+{dm_points})."
            if covered
            else "Decision-maker coverage: no ACTIVE evidence mentions the decision maker (+0)."
        )

    lines.append(
        f"Archived evidence: {len(archived)} link(s), historically retained, scoring-neutral (+0)."
    )

    stale_count = sum(
        1 for entry in scorable if _age_days(entry.created_at, now) > STALE_AGE_DAYS
    )
    stale_penalty = min(stale_count * STALE_PENALTY_PER_ENTRY, STALE_PENALTY_CAP)
    lines.append(
        f"Stale-evidence penalty: {stale_count} ACTIVE entry(ies) older than {STALE_AGE_DAYS} days (-{stale_penalty})."
    )

    weak_count = sum(1 for entry in scorable if not entry.source)
    weak_penalty = min(weak_count * WEAK_SOURCE_PENALTY_PER_ENTRY, WEAK_SOURCE_PENALTY_CAP)
    lines.append(
        f"Weak-source penalty: {weak_count} ACTIVE entry(ies) without a source (-{weak_penalty})."
    )

    disqualified_penalty = min(
        len(disqualified) * DISQUALIFIED_PENALTY_PER_LINK, DISQUALIFIED_PENALTY_CAP
    )
    lines.append(
        f"Disqualified-evidence penalty: {len(disqualified)} RETRACTED/INVALIDATED link(s), "
        f"withdrawn support, not contradiction (-{disqualified_penalty})."
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
        - disqualified_penalty
    )
    score = max(0, min(100, total))
    lines.append(f"Reasoning confidence: {score}/100.")
    return score, lines
