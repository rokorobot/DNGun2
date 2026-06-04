from __future__ import annotations

import re

from .schemas import OfferFitDecision, OfferIntelligenceProfile, OfferProspectFit, Prospect, Signal, utc_now_iso


def calculate_offer_prospect_fit(
    offer_profile: OfferIntelligenceProfile,
    prospect: Prospect,
    signals: list[Signal],
) -> OfferProspectFit:
    explanations: list[str] = []
    if _has_disqualifier(signals):
        return OfferProspectFit(
            id="",
            offer_id=offer_profile.offer.id,
            prospect_id=prospect.id,
            segment_fit_score=0,
            buyer_profile_fit_score=0,
            signal_fit_score=0,
            total_fit_score=0,
            decision=OfferFitDecision.DISQUALIFIED,
            explanation=["Prospect has a disqualifier signal; offer fit overridden."],
            created_at=utc_now_iso(),
        )

    segment_score = _segment_fit(offer_profile, prospect, explanations)
    buyer_score = _buyer_profile_fit(offer_profile, prospect, explanations)
    signal_score = _signal_fit(offer_profile, signals, explanations)
    total = min(segment_score + buyer_score + signal_score, 100)
    return OfferProspectFit(
        id="",
        offer_id=offer_profile.offer.id,
        prospect_id=prospect.id,
        segment_fit_score=segment_score,
        buyer_profile_fit_score=buyer_score,
        signal_fit_score=signal_score,
        total_fit_score=total,
        decision=_decision(total),
        explanation=explanations or ["No strong offer-specific fit evidence found."],
        created_at=utc_now_iso(),
    )


def _segment_fit(
    offer_profile: OfferIntelligenceProfile,
    prospect: Prospect,
    explanations: list[str],
) -> int:
    prospect_tokens = _tokens(prospect.segment)
    target_segments = offer_profile.pdm.target_segments or offer_profile.profile.target_segments
    for segment in target_segments:
        if prospect_tokens & _tokens(segment):
            explanations.append(f"Prospect segment {prospect.segment} matches offer target segment {segment}.")
            return 25
    explanations.append(f"Prospect segment {prospect.segment} does not directly match offer target segments.")
    return 0


def _buyer_profile_fit(
    offer_profile: OfferIntelligenceProfile,
    prospect: Prospect,
    explanations: list[str],
) -> int:
    prospect_text = " ".join(
        str(value or "")
        for value in [
            prospect.company_name,
            prospect.segment,
            prospect.founder_name,
            prospect.contact_path,
            prospect.status,
        ]
    )
    prospect_tokens = _tokens(prospect_text)
    best = 0
    best_profile = ""
    for profile in offer_profile.buyerProfiles:
        overlap = prospect_tokens & _tokens(f"{profile.profile_name} {profile.rationale}")
        score = min(len(overlap) * 8, 25)
        if score > best:
            best = score
            best_profile = profile.profile_name
    if best:
        explanations.append(f"Prospect text overlaps buyer profile {best_profile}.")
    else:
        explanations.append("No direct buyer-profile text overlap found.")
    return best


def _signal_fit(
    offer_profile: OfferIntelligenceProfile,
    signals: list[Signal],
    explanations: list[str],
) -> int:
    prospect_signal_tokens = [_tokens(f"{signal.signal_type} {signal.notes or ''}") for signal in signals]
    if not prospect_signal_tokens:
        explanations.append("Prospect has no signals to compare against offer signal profile.")
        return 0

    total = 0
    matched: list[str] = []
    for offer_signal in offer_profile.signalProfiles:
        offer_tokens = _tokens(f"{offer_signal.signal_name} {offer_signal.rationale}")
        if any(offer_tokens & signal_tokens for signal_tokens in prospect_signal_tokens):
            total += {1: 18, 2: 12, 3: 7}.get(offer_signal.tier, 7)
            matched.append(offer_signal.signal_name)
    if matched:
        explanations.append(f"Prospect signals match offer signals: {', '.join(matched)}.")
    else:
        explanations.append("Prospect signals do not match suggested offer signal profile.")
    return min(total, 50)


def _has_disqualifier(signals: list[Signal]) -> bool:
    return any(
        "disqual" in f"{signal.signal_type} {signal.notes or ''}".lower()
        for signal in signals
    )


def _decision(total: int) -> OfferFitDecision:
    if total >= 70:
        return OfferFitDecision.STRONG_FIT
    if total >= 40:
        return OfferFitDecision.POSSIBLE_FIT
    return OfferFitDecision.WEAK_FIT


def _tokens(value: str) -> set[str]:
    normalized = value.replace("_", " ").lower()
    return {token for token in re.split(r"[^a-z0-9]+", normalized) if token}
