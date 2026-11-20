from __future__ import annotations

import json
import re
from typing import Any

# ---------------------------------------------------------------------------
# Subscription-friendly AI assist for acquisition hypotheses (MVP 1.3A-4).
#
# The app never calls an AI provider. It builds a prompt the operator pastes
# into their own Claude chat (covered by their subscription), then validates
# the pasted answer. Contract rules still hold (invariant 7, generation
# authority):
#   - the answer only ever becomes a DRAFT, stored as source=LLM_ASSISTED;
#   - it may cite only evidence IDs that were in the prompt's scoped set and
#     are still ACTIVE; any other ID rejects the whole answer;
#   - it can never set status, activation, or any confidence value.
# ---------------------------------------------------------------------------

MAX_PROMPT_EVIDENCE = 20
PROVIDER = "manual-paste"


class AssistResponseError(ValueError):
    """The pasted answer is not valid JSON in the requested shape."""


def build_assist_prompt(
    *,
    offer_name: str,
    offer_category: str,
    commercial_hypothesis: str,
    company_name: str,
    segment: str,
    signals: list[Any],
    evidence: list[Any],
    decision_maker: Any | None = None,
) -> str:
    signal_lines = [
        f"- {s.signal_type} (tier {s.tier}, score {s.score})"
        + (f": {s.notes}" if s.notes else "")
        for s in sorted(signals, key=lambda s: (s.tier, -s.score, s.signal_type, s.id))
    ] or ["- none recorded"]
    evidence_lines = [
        f"- [{e.id}] ({e.evidence_type}"
        + (f", source: {e.source}" if e.source else ", no source")
        + f") {e.evidence}"
        for e in evidence
    ] or ["- none available"]
    recipient = (
        f"Decision maker: {decision_maker.name}, {decision_maker.role}. "
        "Also write a one-sentence recipient_framing: how to present the claim to this person."
        if decision_maker is not None
        else "No decision maker: set recipient_framing to null."
    )
    return "\n".join(
        [
            "You are helping draft an acquisition hypothesis for a domain-name sale.",
            "State one falsifiable reason why this company may acquire this domain.",
            "Use ONLY the evidence listed below. Do not invent facts, companies, numbers, or evidence.",
            "Cite the evidence IDs you relied on. If the evidence is too weak, say so in the statement.",
            "",
            f"Offer: {offer_name}",
            f"Offer category: {offer_category}",
            f"Approved buyer thesis: {commercial_hypothesis}",
            f"Prospect: {company_name} (segment {segment})",
            "",
            "Prospect signals:",
            *signal_lines,
            "",
            "Evidence you may cite (ID in brackets):",
            *evidence_lines,
            "",
            recipient,
            "",
            "Reply with ONLY this JSON object, no other text:",
            '{"statement": "...", "recipient_framing": "..." or null, "evidence_ids": ["EV-..."]}',
        ]
    )


def parse_assist_response(raw: str) -> dict:
    """Extract {statement, recipient_framing, evidence_ids} from a pasted answer."""
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    else:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise AssistResponseError("No JSON object found in the pasted answer")
        text = text[start : end + 1]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise AssistResponseError(f"Pasted answer is not valid JSON: {error.msg}") from error
    if not isinstance(data, dict):
        raise AssistResponseError("Pasted answer must be a JSON object")

    statement = data.get("statement")
    if not isinstance(statement, str) or not statement.strip():
        raise AssistResponseError("Pasted answer needs a non-empty \"statement\"")
    framing = data.get("recipient_framing")
    if framing is not None and not isinstance(framing, str):
        raise AssistResponseError("\"recipient_framing\" must be text or null")
    evidence_ids = data.get("evidence_ids", [])
    if not isinstance(evidence_ids, list) or not all(isinstance(i, str) for i in evidence_ids):
        raise AssistResponseError("\"evidence_ids\" must be a list of evidence IDs")

    unique_ids = list(dict.fromkeys(i.strip() for i in evidence_ids if i.strip()))
    return {
        "statement": statement.strip(),
        "recipient_framing": framing.strip() if framing and framing.strip() else None,
        "evidence_ids": unique_ids,
    }
