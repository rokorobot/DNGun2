from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Deterministic acquisition-hypothesis generator (MVP 1.3A-3).
#
# The default and permanent fallback generation source. It synthesizes a
# candidate DRAFT statement from the approved offer intelligence profile and
# the prospect's segment and signals, and cites evidence by ID only. It may
# cite only evidence entries that exist, are ACTIVE, and are relevant to the
# offer x prospect pair (same offer, or same PDM as the prospect's segment).
#
# Output is always a proposal: the caller stores it as a DRAFT, and it enters
# the same human review gate as any other source. It never sets status,
# activation, or any confidence value.
# ---------------------------------------------------------------------------

MAX_CITED_EVIDENCE = 5  # the confidence rubric's count factor stops at 5
MAX_CITED_SIGNALS = 3

# Recipient framing by whole-word role keyword. First match wins; order matters.
_ROLE_FRAMINGS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("founder", "owner", "ceo", "chief executive", "president"),
     "long-term category ownership and brand equity"),
    (("marketing", "cmo", "growth", "brand"),
     "brand recall and lower customer-acquisition cost"),
    (("revenue", "sales", "cro", "commercial"),
     "pipeline credibility and conversion lift"),
    (("operations", "coo", "cto", "technology", "engineering"),
     "operational continuity and avoided rebranding cost"),
    (("product",), "product positioning and launch clarity"),
)
_DEFAULT_FRAMING = "how the domain supports the company's stated direction"


def select_cited_evidence(
    evidence_entries: list[Any], *, offer_id: str, prospect_pdm_code: str | None
) -> list[Any]:
    """ACTIVE, pair-relevant evidence; offer-specific first, then newest first."""
    relevant = [
        entry
        for entry in evidence_entries
        if entry.status == "ACTIVE"
        and (
            entry.offer_id == offer_id
            or (prospect_pdm_code is not None and entry.pdm_code == prospect_pdm_code)
        )
    ]
    relevant.sort(key=lambda entry: entry.id)
    relevant.sort(key=lambda entry: entry.created_at, reverse=True)
    relevant.sort(key=lambda entry: entry.offer_id != offer_id)
    return relevant[:MAX_CITED_EVIDENCE]


def generate_acquisition_hypothesis(
    *,
    offer_id: str,
    offer_name: str,
    offer_category: str,
    commercial_hypothesis: str,
    company_name: str,
    segment: str,
    signals: list[Any],
    cited_evidence: list[Any],
    decision_maker: Any | None = None,
) -> dict:
    """Return {statement, recipient_framing, evidence_links: [(id, note)]}."""
    top_signals = sorted(signals, key=lambda s: (s.tier, -s.score, s.signal_type, s.id))[
        :MAX_CITED_SIGNALS
    ]
    statement = (
        f"{company_name} ({segment}) may acquire {offer_name} because it fits the "
        f"{offer_category} buyer thesis: {commercial_hypothesis.rstrip('.')}."
    )
    if top_signals:
        observed = "; ".join(f"{s.signal_type} (tier {s.tier})" for s in top_signals)
        statement += f" Observed signals: {observed}."
    else:
        statement += " No prospect signals are recorded yet."
    if not cited_evidence:
        statement += " No supporting evidence is linked yet; attach evidence before review."

    recipient_framing = None
    if decision_maker is not None:
        recipient_framing = (
            f"For {decision_maker.name} ({decision_maker.role}): frame around "
            f"{_framing_for_role(decision_maker.role)}."
        )

    return {
        "statement": statement,
        "recipient_framing": recipient_framing,
        "evidence_links": [
            (
                entry.id,
                f"Cited by deterministic generator: {entry.evidence_type}"
                + (
                    " for this offer."
                    if entry.offer_id == offer_id
                    else f" for PDM {entry.pdm_code}."
                ),
            )
            for entry in cited_evidence
        ],
    }


def _framing_for_role(role: str) -> str:
    words = set(re.findall(r"[a-z]+", role.lower()))
    for keywords, framing in _ROLE_FRAMINGS:
        if any(set(keyword.split()) <= words for keyword in keywords):
            return framing
    return _DEFAULT_FRAMING
