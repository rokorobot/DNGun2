from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models
from .rules import RuleRegistry
from .schemas import CampaignIntelligenceReport, RateSummary


def build_campaign_intelligence_report(
    session: Session,
    rules: RuleRegistry | None = None,
    pdm_code: str | None = None,
    offer_id: str | None = None,
) -> CampaignIntelligenceReport:
    rules = rules or RuleRegistry()
    
    prospect_statement = select(func.count(models.ProspectModel.id))
    if pdm_code:
        segment_codes = session.scalars(
            select(models.SegmentRegistryModel.code).where(models.SegmentRegistryModel.pdm_code == pdm_code)
        ).all()
        prospect_statement = prospect_statement.where(models.ProspectModel.segment.in_(segment_codes))
    elif offer_id:
        prospect_statement = prospect_statement.where(
            models.ProspectModel.id.in_(
                select(models.OfferProspectFitModel.prospect_id).where(models.OfferProspectFitModel.offer_id == offer_id)
            )
        )
    total_prospects = session.scalar(prospect_statement) or 0

    statement = select(models.CampaignOutcomeModel)
    if pdm_code:
        segment_codes = session.scalars(
            select(models.SegmentRegistryModel.code).where(models.SegmentRegistryModel.pdm_code == pdm_code)
        ).all()
        statement = statement.join(models.ProspectModel).where(models.ProspectModel.segment.in_(segment_codes))
    elif offer_id:
        statement = statement.where(
            models.CampaignOutcomeModel.prospect_id.in_(
                select(models.OfferProspectFitModel.prospect_id).where(models.OfferProspectFitModel.offer_id == offer_id)
            )
        )
    outcomes = session.scalars(statement).all()

    latest_scores = _latest_scores_by_prospect(session, pdm_code=pdm_code, offer_id=offer_id)
    alpha_codes = _alpha_codes_by_prospect(session)

    overall = _rate_summary(outcomes)
    score_band_outcomes: dict[str, list[models.CampaignOutcomeModel]] = {
        band["code"]: [] for band in rules.score_bands()
    }
    for outcome in outcomes:
        score = latest_scores.get(outcome.prospect_id)
        if score is None:
            continue
        band = _score_band(score.final_score, rules)
        score_band_outcomes[band].append(outcome)

    alpha_signal_outcomes: dict[str, list[models.CampaignOutcomeModel]] = defaultdict(list)
    for outcome in outcomes:
        for code in alpha_codes.get(outcome.prospect_id, []):
            alpha_signal_outcomes[code].append(outcome)

    evidence_statement = select(func.count(models.EvidenceEntryModel.id))
    if pdm_code:
        evidence_statement = evidence_statement.where(models.EvidenceEntryModel.pdm_code == pdm_code)
    elif offer_id:
        evidence_statement = evidence_statement.where(models.EvidenceEntryModel.offer_id == offer_id)
    evidence_entries_created = session.scalar(evidence_statement) or 0

    confidence_statement = select(models.ConfidenceUpdateModel)
    if pdm_code:
        confidence_statement = confidence_statement.where(models.ConfidenceUpdateModel.pdm_code == pdm_code)
    elif offer_id:
        confidence_statement = confidence_statement.where(models.ConfidenceUpdateModel.offer_id == offer_id)
    confidence_updates = session.scalars(
        confidence_statement.order_by(models.ConfidenceUpdateModel.created_at.asc())
    ).all()
    confidence_before = confidence_updates[0].confidence_before if confidence_updates else None
    confidence_after = confidence_updates[-1].confidence_after if confidence_updates else None
    confidence_delta = (
        confidence_after - confidence_before
        if confidence_before is not None and confidence_after is not None
        else None
    )

    return CampaignIntelligenceReport(
        total_prospects=total_prospects,
        contacted_count=overall.contacted_count,
        reply_rate=overall.reply_rate,
        call_booked_rate=overall.call_booked_rate,
        proposal_requested_rate=overall.proposal_requested_rate,
        paid_pilot_rate=overall.paid_pilot_rate,
        performance_by_score_band={
            band: _rate_summary(rows) for band, rows in score_band_outcomes.items()
        },
        performance_by_alpha_signal={
            code: _rate_summary(rows)
            for code, rows in sorted(alpha_signal_outcomes.items())
        },
        evidence_entries_created=evidence_entries_created,
        confidence_before=confidence_before,
        confidence_after=confidence_after,
        confidence_delta=confidence_delta,
    )


def render_campaign_intelligence_markdown(report: CampaignIntelligenceReport) -> str:
    lines = [
        "# DNGun Campaign Intelligence Report",
        "",
        f"- Total prospects: {report.total_prospects}",
        f"- Contacted count: {report.contacted_count}",
        f"- Reply rate: {_percent(report.reply_rate)}",
        f"- Call booked rate: {_percent(report.call_booked_rate)}",
        f"- Proposal requested rate: {_percent(report.proposal_requested_rate)}",
        f"- Paid pilot rate: {_percent(report.paid_pilot_rate)}",
        f"- Evidence entries created: {report.evidence_entries_created}",
        "",
        "## Performance By Score Band",
        "",
        "| Score Band | Contacted | Reply Rate | Call Rate | Proposal Rate | Pilot Rate |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for band, summary in report.performance_by_score_band.items():
        lines.append(
            "| "
            f"{band} | {summary.contacted_count} | {_percent(summary.reply_rate)} | "
            f"{_percent(summary.call_booked_rate)} | "
            f"{_percent(summary.proposal_requested_rate)} | "
            f"{_percent(summary.paid_pilot_rate)} |"
        )

    lines.extend(
        [
            "",
            "## Performance By Alpha Signal",
            "",
            "| Alpha Signal | Contacted | Reply Rate | Call Rate | Proposal Rate | Pilot Rate |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for code, summary in report.performance_by_alpha_signal.items():
        lines.append(
            "| "
            f"{code} | {summary.contacted_count} | {_percent(summary.reply_rate)} | "
            f"{_percent(summary.call_booked_rate)} | "
            f"{_percent(summary.proposal_requested_rate)} | "
            f"{_percent(summary.paid_pilot_rate)} |"
        )

    if report.confidence_before is not None and report.confidence_after is not None:
        lines.extend(
            [
                "",
                "## Confidence Summary",
                "",
                f"- Confidence before: {report.confidence_before:g}",
                f"- Confidence after: {report.confidence_after:g}",
                f"- Confidence delta: {report.confidence_delta:g}",
            ]
        )

    return "\n".join(lines) + "\n"


def _latest_scores_by_prospect(
    session: Session, pdm_code: str | None = None, offer_id: str | None = None
) -> dict[str, models.ProspectScoreModel]:
    inner_stmt = select(
        models.ProspectScoreModel.id.label("id"),
        models.ProspectScoreModel.prospect_id.label("prospect_id"),
        func.row_number().over(
            partition_by=models.ProspectScoreModel.prospect_id,
            order_by=models.ProspectScoreModel.calculated_at.desc()
        ).label("rn")
    )

    if pdm_code:
        segment_codes = session.scalars(
            select(models.SegmentRegistryModel.code).where(models.SegmentRegistryModel.pdm_code == pdm_code)
        ).all()
        inner_stmt = inner_stmt.join(
            models.ProspectModel, models.ProspectModel.id == models.ProspectScoreModel.prospect_id
        ).where(models.ProspectModel.segment.in_(segment_codes))
    elif offer_id:
        inner_stmt = inner_stmt.where(
            models.ProspectScoreModel.prospect_id.in_(
                select(models.OfferProspectFitModel.prospect_id).where(models.OfferProspectFitModel.offer_id == offer_id)
            )
        )

    subq = inner_stmt.subquery()

    stmt = select(models.ProspectScoreModel).join(
        subq, models.ProspectScoreModel.id == subq.c.id
    ).where(subq.c.rn == 1)

    rows = session.scalars(stmt).all()
    return {row.prospect_id: row for row in rows}


def _alpha_codes_by_prospect(session: Session) -> dict[str, list[str]]:
    links = session.scalars(select(models.ProspectAlphaSignalModel)).all()
    result: dict[str, list[str]] = defaultdict(list)
    for link in links:
        result[link.prospect_id].append(link.alpha_signal.code)
    return result


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


def _rate_summary(outcomes: list[models.CampaignOutcomeModel]) -> RateSummary:
    contacted = [outcome for outcome in outcomes if outcome.contacted]
    denominator = len(contacted)
    replied_count = sum(1 for outcome in contacted if outcome.replied)
    call_count = sum(1 for outcome in contacted if outcome.call_booked)
    proposal_count = sum(1 for outcome in contacted if outcome.proposal_requested)
    pilot_count = sum(1 for outcome in contacted if outcome.paid_pilot)

    return RateSummary(
        count=len(outcomes),
        contacted_count=denominator,
        replied_count=replied_count,
        call_booked_count=call_count,
        proposal_requested_count=proposal_count,
        paid_pilot_count=pilot_count,
        reply_rate=_rate(replied_count, denominator),
        call_booked_rate=_rate(call_count, denominator),
        proposal_requested_rate=_rate(proposal_count, denominator),
        paid_pilot_rate=_rate(pilot_count, denominator),
    )


def _rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"
