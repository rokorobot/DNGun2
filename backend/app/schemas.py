from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Segment(StrEnum):
    AI_AUTOMATION = "AI_AUTOMATION"
    REVOPS = "REVOPS"
    SEO = "SEO"
    WEBFLOW = "WEBFLOW"


class ProspectStatus(StrEnum):
    NEW = "NEW"
    SCORING = "SCORING"
    READY_FOR_BATCH = "READY_FOR_BATCH"
    IGNORED = "IGNORED"
    DISQUALIFIED = "DISQUALIFIED"


class ScoreDecision(StrEnum):
    CONTACT_NOW = "CONTACT_NOW"
    SECONDARY = "SECONDARY"
    IGNORE = "IGNORE"
    DISQUALIFY = "DISQUALIFY"


class AlphaSignalValidationStatus(StrEnum):
    HYPOTHESIS = "HYPOTHESIS"
    VALIDATING = "VALIDATING"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"


class CampaignBatchStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProspectCreate(BaseModel):
    company_name: str = Field(min_length=1)
    website: str | None = None
    segment: Segment
    founder_name: str | None = None
    founder_linkedin: str | None = None
    team_size: int | None = Field(default=None, ge=0)
    offer_value_estimate: float | None = Field(default=None, ge=0)
    contact_path: str | None = None
    status: ProspectStatus = ProspectStatus.NEW


class Prospect(ApiModel, ProspectCreate):
    id: str
    created_at: str


class SignalCreate(BaseModel):
    signal_type: str = Field(min_length=1)
    tier: Literal[1, 2, 3]
    score: int = Field(ge=0, le=5)
    source_url: str | None = None
    observed_at: str = Field(default_factory=utc_now_iso)
    notes: str | None = None


class Signal(ApiModel, SignalCreate):
    id: str
    prospect_id: str
    created_at: str


class AlphaSignalCreate(BaseModel):
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str | None = None
    required_signals: list[str] = Field(default_factory=list)
    bonus_score: int = Field(default=0, ge=0)
    validation_status: AlphaSignalValidationStatus = AlphaSignalValidationStatus.HYPOTHESIS


class AlphaSignal(ApiModel, AlphaSignalCreate):
    id: str
    created_at: str


class ProspectAlphaSignalCreate(BaseModel):
    notes: str | None = None


class ProspectAlphaSignal(ApiModel):
    id: str
    prospect_id: str
    alpha_signal_id: str
    alpha_signal_code: str
    alpha_signal_name: str
    bonus_score: int
    notes: str | None = None
    created_at: str


class ScoreExplanation(BaseModel):
    source_type: Literal["SIGNAL", "ALPHA_SIGNAL", "DISQUALIFIER", "SCORE_BAND"]
    source_code: str
    label: str
    tier: int | None = None
    impact: int
    notes: str | None = None


class ScoreExplanationRead(ApiModel, ScoreExplanation):
    id: str
    prospect_score_id: str


class ProspectScore(BaseModel):
    prospect_id: str
    tier1_total: int
    tier2_total: int
    tier3_total: int
    base_score: int
    alpha_matches: list[str] = Field(default_factory=list)
    alpha_bonus: int = 0
    final_score: int
    decision: ScoreDecision
    explanation: list[ScoreExplanation]
    calculated_at: str = Field(default_factory=utc_now_iso)


class ProspectScoreRead(ApiModel, ProspectScore):
    id: str


class CampaignBatchCreate(BaseModel):
    name: str = Field(min_length=1)
    segment: Segment | None = None
    status: CampaignBatchStatus = CampaignBatchStatus.DRAFT
    notes: str | None = None


class CampaignBatch(ApiModel, CampaignBatchCreate):
    id: str
    created_at: str


class CampaignBatchProspect(ApiModel):
    id: str
    campaign_batch_id: str
    prospect_id: str
    created_at: str


class CampaignOutcomeCreate(BaseModel):
    campaign_batch_id: str
    prospect_id: str
    contacted: bool = False
    replied: bool = False
    call_booked: bool = False
    proposal_requested: bool = False
    paid_pilot: bool = False
    lost_deal: bool = False
    outcome_notes: str | None = None
    recorded_at: str = Field(default_factory=utc_now_iso)


class CampaignOutcome(ApiModel, CampaignOutcomeCreate):
    id: str


class EvidenceEntryCreate(BaseModel):
    project: str = Field(default="DNGun", min_length=1)
    evidence_type: str = Field(min_length=1)
    evidence: str = Field(min_length=1)
    impact: int
    source: str | None = None


class EvidenceEntry(ApiModel, EvidenceEntryCreate):
    id: str
    created_at: str


class ConfidenceUpdateCreate(BaseModel):
    evidence_entry_id: str | None = None
    confidence_before: float = Field(ge=0, le=100)
    evidence_impact: float
    confidence_after: float = Field(ge=0, le=100)
    reason: str = Field(min_length=1)


class ConfidenceUpdate(ApiModel, ConfidenceUpdateCreate):
    id: str
    created_at: str


class RateSummary(BaseModel):
    count: int
    contacted_count: int
    replied_count: int
    call_booked_count: int
    proposal_requested_count: int
    paid_pilot_count: int
    reply_rate: float
    call_booked_rate: float
    proposal_requested_rate: float
    paid_pilot_rate: float


class CampaignIntelligenceReport(BaseModel):
    total_prospects: int
    contacted_count: int
    reply_rate: float
    call_booked_rate: float
    proposal_requested_rate: float
    paid_pilot_rate: float
    performance_by_score_band: dict[str, RateSummary]
    performance_by_alpha_signal: dict[str, RateSummary]
    evidence_entries_created: int
    confidence_before: float | None = None
    confidence_after: float | None = None
    confidence_delta: float | None = None


class SignalPerformanceRead(BaseModel):
    signalType: str
    timesSeen: int
    contacted: int
    replied: int
    callBooked: int
    proposalRequested: int
    paidPilot: int
    replyRate: float
    callRate: float
    proposalRate: float
    pilotRate: float
    confidence: str
    recommendation: str


class AlphaSignalPerformanceRead(BaseModel):
    code: str
    name: str
    timesMatched: int
    contacted: int
    replied: int
    callBooked: int
    proposalRequested: int
    paidPilot: int
    replyRate: float
    callRate: float
    proposalRate: float
    pilotRate: float
    confidence: str
    recommendation: str


class ScoreBandValidationRead(BaseModel):
    scoreBand: str
    prospectsInBand: int
    contacted: int
    replied: int
    callBooked: int
    proposalRequested: int
    paidPilot: int
    replyRate: float
    callRate: float
    proposalRate: float
    pilotRate: float
    confidence: str
    recommendation: str


class LearningSummaryRead(BaseModel):
    topPerformingSignals: list[SignalPerformanceRead]
    weakSignals: list[SignalPerformanceRead]
    topAlphaSignals: list[AlphaSignalPerformanceRead]
    weakAlphaSignals: list[AlphaSignalPerformanceRead]
    scoreBandValidation: list[ScoreBandValidationRead]
    recommendedRuleChanges: list[str]
