from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .rules import RuleRegistry
from .schemas import (
    AlphaSignalPerformanceRead,
    LearningSummaryRead,
    ScoreBandValidationRead,
    SignalPerformanceRead,
)


def calculate_signal_performance(session: Session) -> list[SignalPerformanceRead]:
    outcomes = _latest_outcomes_by_prospect(session)
    signal_prospects: dict[str, set[str]] = defaultdict(set)
    signals = session.scalars(select(models.SignalModel)).all()
    for signal in signals:
        signal_prospects[signal.signal_type].add(signal.prospect_id)

    rows = [
        _signal_row(signal_type, prospect_ids, outcomes)
        for signal_type, prospect_ids in signal_prospects.items()
    ]
    return sorted(rows, key=lambda row: (row.pilotRate, row.replyRate, row.timesSeen), reverse=True)


def calculate_alpha_signal_performance(session: Session) -> list[AlphaSignalPerformanceRead]:
    outcomes = _latest_outcomes_by_prospect(session)
    alpha_prospects: dict[tuple[str, str], set[str]] = defaultdict(set)
    links = session.scalars(select(models.ProspectAlphaSignalModel)).all()
    for link in links:
        alpha_prospects[(link.alpha_signal.code, link.alpha_signal.name)].add(link.prospect_id)

    rows = [
        _alpha_row(code, name, prospect_ids, outcomes)
        for (code, name), prospect_ids in alpha_prospects.items()
    ]
    return sorted(rows, key=lambda row: (row.pilotRate, row.replyRate, row.timesMatched), reverse=True)


def calculate_score_band_validation(
    session: Session, rules: RuleRegistry | None = None
) -> list[ScoreBandValidationRead]:
    rules = rules or RuleRegistry()
    outcomes = _latest_outcomes_by_prospect(session)
    latest_scores = _latest_scores_by_prospect(session)
    band_prospects: dict[str, set[str]] = {
        band["code"]: set() for band in rules.score_bands()
    }
    for prospect_id, score in latest_scores.items():
        band_prospects[_score_band(score.final_score, rules)].add(prospect_id)

    return [
        _score_band_row(band, prospect_ids, outcomes)
        for band, prospect_ids in band_prospects.items()
    ]


def calculate_learning_summary(session: Session) -> LearningSummaryRead:
    signals = calculate_signal_performance(session)
    alpha_signals = calculate_alpha_signal_performance(session)
    score_bands = calculate_score_band_validation(session)

    top_signals = [
        signal
        for signal in signals
        if signal.recommendation in {"INCREASE_WEIGHT", "KEEP"}
    ][:5]
    weak_signals = [
        signal
        for signal in signals
        if signal.recommendation in {"DECREASE_WEIGHT", "RETIRE_OR_REVIEW"}
    ][:5]
    top_alpha = [
        signal
        for signal in alpha_signals
        if signal.recommendation == "VALIDATE"
    ][:5]
    weak_alpha = [
        signal
        for signal in alpha_signals
        if signal.recommendation in {"WEAK_ALPHA_SIGNAL", "REVIEW_BONUS"}
    ][:5]

    return LearningSummaryRead(
        topPerformingSignals=top_signals,
        weakSignals=weak_signals,
        topAlphaSignals=top_alpha,
        weakAlphaSignals=weak_alpha,
        scoreBandValidation=score_bands,
        recommendedRuleChanges=_recommended_rule_changes(
            top_signals, weak_signals, top_alpha, weak_alpha, score_bands
        ),
    )


def render_learning_markdown(summary: LearningSummaryRead) -> str:
    lines = [
        "# DNGun Learning Intelligence Report",
        "",
        "## Top Performing Signals",
        "",
        *_signal_lines(summary.topPerformingSignals),
        "",
        "## Weak Signals",
        "",
        *_signal_lines(summary.weakSignals),
        "",
        "## Top Alpha Signals",
        "",
        *_alpha_lines(summary.topAlphaSignals),
        "",
        "## Weak Alpha Signals",
        "",
        *_alpha_lines(summary.weakAlphaSignals),
        "",
        "## Score Band Validation",
        "",
        *_score_band_lines(summary.scoreBandValidation),
        "",
        "## Recommended Rule Changes",
        "",
        *[f"- {item}" for item in summary.recommendedRuleChanges],
    ]
    return "\n".join(lines) + "\n"


def _latest_outcomes_by_prospect(
    session: Session,
) -> dict[str, models.CampaignOutcomeModel]:
    outcomes = session.scalars(
        select(models.CampaignOutcomeModel).order_by(
            models.CampaignOutcomeModel.recorded_at.asc()
        )
    ).all()
    latest: dict[str, models.CampaignOutcomeModel] = {}
    for outcome in outcomes:
        latest[outcome.prospect_id] = outcome
    return latest


def _latest_scores_by_prospect(session: Session) -> dict[str, models.ProspectScoreModel]:
    scores = session.scalars(
        select(models.ProspectScoreModel).order_by(
            models.ProspectScoreModel.calculated_at.asc()
        )
    ).all()
    latest: dict[str, models.ProspectScoreModel] = {}
    for score in scores:
        latest[score.prospect_id] = score
    return latest


def _signal_row(
    signal_type: str,
    prospect_ids: set[str],
    outcomes: dict[str, models.CampaignOutcomeModel],
) -> SignalPerformanceRead:
    metrics = _metrics(prospect_ids, outcomes)
    contacted = int(metrics["contacted"])
    return SignalPerformanceRead(
        signalType=signal_type,
        timesSeen=len(prospect_ids),
        confidence=_confidence(contacted),
        recommendation=_signal_recommendation(contacted, metrics),
        **metrics,
    )


def _alpha_row(
    code: str,
    name: str,
    prospect_ids: set[str],
    outcomes: dict[str, models.CampaignOutcomeModel],
) -> AlphaSignalPerformanceRead:
    metrics = _metrics(prospect_ids, outcomes)
    contacted = int(metrics["contacted"])
    return AlphaSignalPerformanceRead(
        code=code,
        name=name,
        timesMatched=len(prospect_ids),
        confidence=_confidence(contacted),
        recommendation=_alpha_recommendation(contacted, metrics),
        **metrics,
    )


def _score_band_row(
    score_band: str,
    prospect_ids: set[str],
    outcomes: dict[str, models.CampaignOutcomeModel],
) -> ScoreBandValidationRead:
    metrics = _metrics(prospect_ids, outcomes)
    contacted = int(metrics["contacted"])
    return ScoreBandValidationRead(
        scoreBand=score_band,
        prospectsInBand=len(prospect_ids),
        confidence=_confidence(contacted),
        recommendation=_score_band_recommendation(score_band, metrics),
        **metrics,
    )


def _metrics(
    prospect_ids: set[str],
    outcomes: dict[str, models.CampaignOutcomeModel],
) -> dict[str, int | float]:
    prospect_outcomes = [
        outcomes[prospect_id]
        for prospect_id in prospect_ids
        if prospect_id in outcomes
    ]
    contacted = [outcome for outcome in prospect_outcomes if outcome.contacted]
    contacted_count = len(contacted)
    replied = sum(1 for outcome in contacted if outcome.replied)
    call_booked = sum(1 for outcome in contacted if outcome.call_booked)
    proposal_requested = sum(1 for outcome in contacted if outcome.proposal_requested)
    paid_pilot = sum(1 for outcome in contacted if outcome.paid_pilot)
    return {
        "contacted": contacted_count,
        "replied": replied,
        "callBooked": call_booked,
        "proposalRequested": proposal_requested,
        "paidPilot": paid_pilot,
        "replyRate": _rate(replied, contacted_count),
        "callRate": _rate(call_booked, contacted_count),
        "proposalRate": _rate(proposal_requested, contacted_count),
        "pilotRate": _rate(paid_pilot, contacted_count),
    }


def _confidence(observations: int) -> str:
    if observations < 5:
        return "INSUFFICIENT_DATA"
    if observations < 15:
        return "LOW"
    if observations < 40:
        return "MEDIUM"
    return "HIGH"


def _signal_recommendation(contacted: int, metrics: dict[str, int | float]) -> str:
    reply_rate = float(metrics["replyRate"])
    call_rate = float(metrics["callRate"])
    pilot_rate = float(metrics["pilotRate"])
    if contacted < 5:
        return "COLLECT_MORE_DATA"
    if contacted >= 20 and pilot_rate == 0 and reply_rate < 0.10:
        return "RETIRE_OR_REVIEW"
    if pilot_rate >= 0.10 and contacted >= 10:
        return "INCREASE_WEIGHT"
    if reply_rate >= 0.30 and call_rate >= 0.15:
        return "KEEP"
    if contacted >= 10 and reply_rate < 0.05:
        return "DECREASE_WEIGHT"
    return "COLLECT_MORE_DATA"


def _alpha_recommendation(contacted: int, metrics: dict[str, int | float]) -> str:
    paid_pilot = int(metrics["paidPilot"])
    reply_rate = float(metrics["replyRate"])
    pilot_rate = float(metrics["pilotRate"])
    if contacted < 5:
        return "COLLECT_MORE_DATA"
    if pilot_rate >= 0.10 and contacted >= 10:
        return "VALIDATE"
    if contacted >= 20 and paid_pilot == 0:
        return "REVIEW_BONUS"
    if reply_rate >= 0.30 and pilot_rate < 0.05:
        return "GOOD_ATTENTION_SIGNAL_BAD_BUYER_SIGNAL"
    if contacted >= 15 and reply_rate < 0.10:
        return "WEAK_ALPHA_SIGNAL"
    return "COLLECT_MORE_DATA"


def _score_band_recommendation(
    score_band: str, metrics: dict[str, int | float]
) -> str:
    contacted = int(metrics["contacted"])
    reply_rate = float(metrics["replyRate"])
    pilot_rate = float(metrics["pilotRate"])
    if contacted < 5:
        return "COLLECT_MORE_DATA"
    if score_band == "CONTACT_NOW" and pilot_rate >= 0.10:
        return "VALIDATED_BAND"
    if score_band == "CONTACT_NOW" and contacted >= 10 and reply_rate < 0.10:
        return "REVIEW_SCORE_THRESHOLD"
    if score_band in {"IGNORE", "DISQUALIFY"} and reply_rate >= 0.20:
        return "REVIEW_UNDERRATED_BAND"
    return "MONITOR"


def _score_band(score: int, rules: RuleRegistry) -> str:
    for band in rules.score_bands():
        min_score = band.get("min_score")
        max_score = band.get("max_score")
        if min_score is not None and score < min_score:
            continue
        if max_score is not None and score > max_score:
            continue
        return band["code"]
    return "UNKNOWN"


def _recommended_rule_changes(
    top_signals: list[SignalPerformanceRead],
    weak_signals: list[SignalPerformanceRead],
    top_alpha: list[AlphaSignalPerformanceRead],
    weak_alpha: list[AlphaSignalPerformanceRead],
    score_bands: list[ScoreBandValidationRead],
) -> list[str]:
    changes: list[str] = []
    changes.extend(
        f"Increase or preserve weight for signal '{signal.signalType}' ({signal.recommendation})."
        for signal in top_signals
    )
    changes.extend(
        f"Review weight for weak signal '{signal.signalType}' ({signal.recommendation})."
        for signal in weak_signals
    )
    changes.extend(
        f"Validate Alpha Signal {signal.code} '{signal.name}' before increasing automation reliance."
        for signal in top_alpha
    )
    changes.extend(
        f"Review Alpha Signal {signal.code} '{signal.name}' bonus or required signals ({signal.recommendation})."
        for signal in weak_alpha
    )
    changes.extend(
        f"Review score band {band.scoreBand}: {band.recommendation}."
        for band in score_bands
        if band.recommendation not in {"MONITOR", "COLLECT_MORE_DATA"}
    )
    return changes or ["Collect more campaign outcomes before changing rules."]


def _signal_lines(rows: list[SignalPerformanceRead]) -> list[str]:
    if not rows:
        return ["- No qualifying signals yet."]
    return [
        "- "
        f"{row.signalType}: seen {row.timesSeen}, reply {_percent(row.replyRate)}, "
        f"call {_percent(row.callRate)}, pilot {_percent(row.pilotRate)}, "
        f"{row.confidence}, {row.recommendation}"
        for row in rows
    ]


def _alpha_lines(rows: list[AlphaSignalPerformanceRead]) -> list[str]:
    if not rows:
        return ["- No qualifying Alpha Signals yet."]
    return [
        "- "
        f"{row.code} {row.name}: matched {row.timesMatched}, reply {_percent(row.replyRate)}, "
        f"call {_percent(row.callRate)}, pilot {_percent(row.pilotRate)}, "
        f"{row.confidence}, {row.recommendation}"
        for row in rows
    ]


def _score_band_lines(rows: list[ScoreBandValidationRead]) -> list[str]:
    if not rows:
        return ["- No score bands yet."]
    return [
        "- "
        f"{row.scoreBand}: prospects {row.prospectsInBand}, contacted {row.contacted}, "
        f"reply {_percent(row.replyRate)}, pilot {_percent(row.pilotRate)}, "
        f"{row.confidence}, {row.recommendation}"
        for row in rows
    ]


def _rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"
