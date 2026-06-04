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


class OfferType(StrEnum):
    DOMAIN_NAME = "DOMAIN_NAME"


class OfferStatus(StrEnum):
    DRAFT = "DRAFT"
    PROPOSED = "PROPOSED"
    PROFILED = "PROFILED"
    VALIDATING = "VALIDATING"
    ARCHIVED = "ARCHIVED"


class OfferEvaluationMode(StrEnum):
    DETERMINISTIC = "DETERMINISTIC"
    LLM_ASSISTED = "LLM_ASSISTED"


class OfferProposalStatus(StrEnum):
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class OfferFitDecision(StrEnum):
    STRONG_FIT = "STRONG_FIT"
    POSSIBLE_FIT = "POSSIBLE_FIT"
    WEAK_FIT = "WEAK_FIT"
    DISQUALIFIED = "DISQUALIFIED"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProspectCreate(BaseModel):
    company_name: str = Field(min_length=1)
    website: str | None = None
    segment: str
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
    segment: str | None = None
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
    pdm_code: str | None = None
    offer_id: str | None = None
    campaign_batch_id: str | None = None
    signal_code: str | None = None
    alpha_signal_code: str | None = None


class EvidenceEntry(ApiModel, EvidenceEntryCreate):
    id: str
    created_at: str


class ConfidenceUpdateCreate(BaseModel):
    evidence_entry_id: str | None = None
    confidence_before: float = Field(ge=0, le=100)
    evidence_impact: float
    confidence_after: float = Field(ge=0, le=100)
    reason: str = Field(min_length=1)
    pdm_code: str | None = None
    offer_id: str | None = None
    campaign_batch_id: str | None = None
    signal_code: str | None = None
    alpha_signal_code: str | None = None


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
    replyRateRank: float = 0.0
    callRateRank: float = 0.0
    proposalRateRank: float = 0.0
    pilotRateRank: float = 0.0
    confidenceRank: float = 0.0
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
    replyRateRank: float = 0.0
    callRateRank: float = 0.0
    proposalRateRank: float = 0.0
    pilotRateRank: float = 0.0
    confidenceRank: float = 0.0
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
    replyRateRank: float = 0.0
    callRateRank: float = 0.0
    proposalRateRank: float = 0.0
    pilotRateRank: float = 0.0
    confidenceRank: float = 0.0
    confidence: str
    recommendation: str


class LearningSummaryRead(BaseModel):
    topPerformingSignals: list[SignalPerformanceRead]
    weakSignals: list[SignalPerformanceRead]
    topAlphaSignals: list[AlphaSignalPerformanceRead]
    weakAlphaSignals: list[AlphaSignalPerformanceRead]
    scoreBandValidation: list[ScoreBandValidationRead]
    recommendedRuleChanges: list[str]


class OfferCreate(BaseModel):
    name: str = Field(min_length=1)
    offer_type: OfferType = OfferType.DOMAIN_NAME
    description: str | None = None
    estimated_value: float | None = Field(default=None, ge=0)
    status: OfferStatus = OfferStatus.DRAFT


class Offer(ApiModel, OfferCreate):
    id: str
    created_at: str


class OfferProfile(ApiModel):
    id: str
    offer_id: str
    offer_category: str
    commercial_hypothesis: str
    predicted_value_range: str
    target_segments: list[str] = Field(default_factory=list)
    created_at: str


class OfferBuyerProfile(ApiModel):
    id: str
    offer_id: str
    profile_name: str
    rationale: str
    priority: int
    created_at: str


class OfferSignalProfile(ApiModel):
    id: str
    offer_id: str
    signal_name: str
    tier: Literal[1, 2, 3]
    rationale: str
    created_at: str


class OfferPdm(ApiModel):
    id: str
    offer_id: str
    code: str
    name: str
    summary: str
    target_segments: list[str] = Field(default_factory=list)
    created_at: str


class OfferIntelligenceProfile(BaseModel):
    offer: Offer
    profile: OfferProfile
    buyerProfiles: list[OfferBuyerProfile]
    signalProfiles: list[OfferSignalProfile]
    pdm: OfferPdm


class OfferEvaluationRequest(BaseModel):
    mode: OfferEvaluationMode = OfferEvaluationMode.DETERMINISTIC


class OfferProposalReview(BaseModel):
    review_notes: str | None = None


class OfferEvaluationProposal(ApiModel):
    id: str
    offer_id: str
    provider: str
    model: str | None = None
    mode: OfferEvaluationMode
    raw_domain: str
    normalized_domain: str
    primary_category: str
    confidence_score: float
    confidence_label: str
    reasoning: list[str]
    alternative_categories: list[str]
    proposed_profile_json: dict
    status: OfferProposalStatus
    created_at: str
    reviewed_at: str | None = None
    review_notes: str | None = None


class OfferProspectFit(BaseModel):
    id: str
    offer_id: str
    prospect_id: str
    segment_fit_score: int
    buyer_profile_fit_score: int
    signal_fit_score: int
    total_fit_score: int
    decision: OfferFitDecision
    explanation: list[str]
    created_at: str


class SegmentRegistryCreate(BaseModel):
    code: str = Field(min_length=1)
    label: str = Field(min_length=1)
    pdm_code: str = Field(min_length=1)
    status: str = "ACTIVE"


class SegmentRegistry(ApiModel, SegmentRegistryCreate):
    id: str
    created_at: str


class DecisionMakerCreate(BaseModel):
    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    email: str | None = None
    linkedin: str | None = None
    entry_source: str = "MANUAL"


class DecisionMaker(ApiModel):
    id: str
    prospect_id: str
    name: str
    role: str
    email: str | None
    linkedin: str | None
    authority_score: int
    acquisition_rationale: str | None
    entry_source: str
    created_at: str
    updated_at: str
    contact_paths: list[ContactPath] = []


class ContactPathType(StrEnum):
    EMAIL = "EMAIL"
    LINKEDIN = "LINKEDIN"
    PHONE = "PHONE"
    WEBSITE_FORM = "WEBSITE_FORM"


class ContactPathCreate(BaseModel):
    type: ContactPathType
    value: str = Field(min_length=1)
    source: str = "MANUAL"
    confidence: float = Field(default=100.0, ge=0.0, le=100.0)
    verified: bool = False
    last_verified_at: str | None = None


class ContactPath(ApiModel, ContactPathCreate):
    id: str
    decision_maker_id: str
    created_at: str


