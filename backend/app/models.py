from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class ProspectModel(Base):
    __tablename__ = "prospects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    company_name: Mapped[str] = mapped_column(String, nullable=False)
    website: Mapped[str | None] = mapped_column(String)
    segment: Mapped[str] = mapped_column(String, nullable=False)
    founder_name: Mapped[str | None] = mapped_column(String)
    founder_linkedin: Mapped[str | None] = mapped_column(String)
    team_size: Mapped[int | None] = mapped_column(Integer)
    offer_value_estimate: Mapped[float | None] = mapped_column(Float)
    contact_path: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    signals: Mapped[list[SignalModel]] = relationship(
        back_populates="prospect", cascade="all, delete-orphan"
    )
    alpha_signal_links: Mapped[list[ProspectAlphaSignalModel]] = relationship(
        back_populates="prospect", cascade="all, delete-orphan"
    )
    scores: Mapped[list[ProspectScoreModel]] = relationship(
        back_populates="prospect", cascade="all, delete-orphan"
    )
    decision_makers: Mapped[list[DecisionMakerModel]] = relationship(
        back_populates="prospect", cascade="all, delete-orphan"
    )


class SignalModel(Base):
    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    prospect_id: Mapped[str] = mapped_column(
        ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False
    )
    signal_type: Mapped[str] = mapped_column(String, nullable=False)
    tier: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String)
    observed_at: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    prospect: Mapped[ProspectModel] = relationship(back_populates="signals")


class AlphaSignalModel(Base):
    __tablename__ = "alpha_signals"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    required_signals: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    bonus_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    validation_status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    prospect_links: Mapped[list[ProspectAlphaSignalModel]] = relationship(
        back_populates="alpha_signal", cascade="all, delete-orphan"
    )


class ProspectAlphaSignalModel(Base):
    __tablename__ = "prospect_alpha_signals"
    __table_args__ = (
        UniqueConstraint(
            "prospect_id",
            "alpha_signal_id",
            name="uq_prospect_alpha_signal",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    prospect_id: Mapped[str] = mapped_column(
        ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False
    )
    alpha_signal_id: Mapped[str] = mapped_column(
        ForeignKey("alpha_signals.id", ondelete="CASCADE"), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    prospect: Mapped[ProspectModel] = relationship(back_populates="alpha_signal_links")
    alpha_signal: Mapped[AlphaSignalModel] = relationship(back_populates="prospect_links")


class ProspectScoreModel(Base):
    __tablename__ = "prospect_scores"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    prospect_id: Mapped[str] = mapped_column(
        ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False
    )
    tier1_total: Mapped[int] = mapped_column(Integer, nullable=False)
    tier2_total: Mapped[int] = mapped_column(Integer, nullable=False)
    tier3_total: Mapped[int] = mapped_column(Integer, nullable=False)
    base_score: Mapped[int] = mapped_column(Integer, nullable=False)
    alpha_bonus: Mapped[int] = mapped_column(Integer, nullable=False)
    final_score: Mapped[int] = mapped_column(Integer, nullable=False)
    decision: Mapped[str] = mapped_column(String, nullable=False)
    calculated_at: Mapped[str] = mapped_column(String, nullable=False)

    prospect: Mapped[ProspectModel] = relationship(back_populates="scores")
    explanations: Mapped[list[ScoreExplanationModel]] = relationship(
        back_populates="prospect_score", cascade="all, delete-orphan"
    )


class ScoreExplanationModel(Base):
    __tablename__ = "score_explanations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    prospect_score_id: Mapped[str] = mapped_column(
        ForeignKey("prospect_scores.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    source_code: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    tier: Mapped[int | None] = mapped_column(Integer)
    impact: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    prospect_score: Mapped[ProspectScoreModel] = relationship(back_populates="explanations")


class CampaignBatchModel(Base):
    __tablename__ = "campaign_batches"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    segment: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    prospects: Mapped[list[CampaignBatchProspectModel]] = relationship(
        back_populates="campaign_batch", cascade="all, delete-orphan"
    )
    outcomes: Mapped[list[CampaignOutcomeModel]] = relationship(
        back_populates="campaign_batch", cascade="all, delete-orphan"
    )


class CampaignBatchProspectModel(Base):
    __tablename__ = "campaign_batch_prospects"
    __table_args__ = (
        UniqueConstraint(
            "campaign_batch_id",
            "prospect_id",
            name="uq_campaign_batch_prospect",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    campaign_batch_id: Mapped[str] = mapped_column(
        ForeignKey("campaign_batches.id", ondelete="CASCADE"), nullable=False
    )
    prospect_id: Mapped[str] = mapped_column(
        ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    campaign_batch: Mapped[CampaignBatchModel] = relationship(back_populates="prospects")
    prospect: Mapped[ProspectModel] = relationship()


class CampaignOutcomeModel(Base):
    __tablename__ = "campaign_outcomes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    campaign_batch_id: Mapped[str] = mapped_column(
        ForeignKey("campaign_batches.id", ondelete="CASCADE"), nullable=False
    )
    prospect_id: Mapped[str] = mapped_column(
        ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False
    )
    contacted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    replied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    call_booked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    proposal_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    paid_pilot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    lost_deal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    outcome_notes: Mapped[str | None] = mapped_column(Text)
    recorded_at: Mapped[str] = mapped_column(String, nullable=False)

    campaign_batch: Mapped[CampaignBatchModel] = relationship(back_populates="outcomes")
    prospect: Mapped[ProspectModel] = relationship()


class EvidenceEntryModel(Base):
    __tablename__ = "evidence_entries"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project: Mapped[str] = mapped_column(String, nullable=False)
    evidence_type: Mapped[str] = mapped_column(String, nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    impact: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str | None] = mapped_column(String)
    # Lifecycle state (ACTIVE / ARCHIVED / RETRACTED / INVALIDATED); evidence
    # referenced by a hypothesis is never physically deleted (MVP 1.3 ruling 3).
    status: Mapped[str] = mapped_column(String, nullable=False, default="ACTIVE")
    pdm_code: Mapped[str | None] = mapped_column(String)
    offer_id: Mapped[str | None] = mapped_column(
        ForeignKey("offers.id", ondelete="SET NULL")
    )
    campaign_batch_id: Mapped[str | None] = mapped_column(
        ForeignKey("campaign_batches.id", ondelete="SET NULL")
    )
    signal_code: Mapped[str | None] = mapped_column(String)
    alpha_signal_code: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class ConfidenceUpdateModel(Base):
    __tablename__ = "confidence_updates"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    evidence_entry_id: Mapped[str | None] = mapped_column(
        ForeignKey("evidence_entries.id", ondelete="SET NULL")
    )
    confidence_before: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_impact: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_after: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    pdm_code: Mapped[str | None] = mapped_column(String)
    offer_id: Mapped[str | None] = mapped_column(
        ForeignKey("offers.id", ondelete="SET NULL")
    )
    campaign_batch_id: Mapped[str | None] = mapped_column(
        ForeignKey("campaign_batches.id", ondelete="SET NULL")
    )
    signal_code: Mapped[str | None] = mapped_column(String)
    alpha_signal_code: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    evidence_entry: Mapped[EvidenceEntryModel | None] = relationship()


class OfferModel(Base):
    __tablename__ = "offers"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    offer_type: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    estimated_value: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    profile: Mapped[OfferProfileModel | None] = relationship(
        back_populates="offer", cascade="all, delete-orphan"
    )
    buyer_profiles: Mapped[list[OfferBuyerProfileModel]] = relationship(
        back_populates="offer", cascade="all, delete-orphan"
    )
    signal_profiles: Mapped[list[OfferSignalProfileModel]] = relationship(
        back_populates="offer", cascade="all, delete-orphan"
    )
    pdm: Mapped[OfferPdmModel | None] = relationship(
        back_populates="offer", cascade="all, delete-orphan"
    )


class OfferProfileModel(Base):
    __tablename__ = "offer_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    offer_id: Mapped[str] = mapped_column(
        ForeignKey("offers.id", ondelete="CASCADE"), nullable=False
    )
    offer_category: Mapped[str] = mapped_column(String, nullable=False)
    commercial_hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    predicted_value_range: Mapped[str] = mapped_column(String, nullable=False)
    target_segments: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    offer: Mapped[OfferModel] = relationship(back_populates="profile")


class OfferBuyerProfileModel(Base):
    __tablename__ = "offer_buyer_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    offer_id: Mapped[str] = mapped_column(
        ForeignKey("offers.id", ondelete="CASCADE"), nullable=False
    )
    profile_name: Mapped[str] = mapped_column(String, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    offer: Mapped[OfferModel] = relationship(back_populates="buyer_profiles")


class OfferSignalProfileModel(Base):
    __tablename__ = "offer_signal_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    offer_id: Mapped[str] = mapped_column(
        ForeignKey("offers.id", ondelete="CASCADE"), nullable=False
    )
    signal_name: Mapped[str] = mapped_column(String, nullable=False)
    tier: Mapped[int] = mapped_column(Integer, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    offer: Mapped[OfferModel] = relationship(back_populates="signal_profiles")


class OfferPdmModel(Base):
    __tablename__ = "offer_pdms"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    offer_id: Mapped[str] = mapped_column(
        ForeignKey("offers.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    target_segments: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    offer: Mapped[OfferModel] = relationship(back_populates="pdm")


class OfferEvaluationProposalModel(Base):
    __tablename__ = "offer_evaluation_proposals"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    offer_id: Mapped[str] = mapped_column(
        ForeignKey("offers.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str | None] = mapped_column(String)
    mode: Mapped[str] = mapped_column(String, nullable=False)
    raw_domain: Mapped[str] = mapped_column(String, nullable=False)
    normalized_domain: Mapped[str] = mapped_column(String, nullable=False)
    primary_category: Mapped[str] = mapped_column(String, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_label: Mapped[str] = mapped_column(String, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    alternative_categories: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    proposed_profile_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    reviewed_at: Mapped[str | None] = mapped_column(String)
    review_notes: Mapped[str | None] = mapped_column(Text)

    offer: Mapped[OfferModel] = relationship()


class OfferProspectFitModel(Base):
    __tablename__ = "offer_prospect_fits"
    __table_args__ = (
        UniqueConstraint("offer_id", "prospect_id", name="uq_offer_prospect_fit"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    offer_id: Mapped[str] = mapped_column(
        ForeignKey("offers.id", ondelete="CASCADE"), nullable=False
    )
    prospect_id: Mapped[str] = mapped_column(
        ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False
    )
    segment_fit_score: Mapped[int] = mapped_column(Integer, nullable=False)
    buyer_profile_fit_score: Mapped[int] = mapped_column(Integer, nullable=False)
    signal_fit_score: Mapped[int] = mapped_column(Integer, nullable=False)
    total_fit_score: Mapped[int] = mapped_column(Integer, nullable=False)
    decision: Mapped[str] = mapped_column(String, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    offer: Mapped[OfferModel] = relationship()
    prospect: Mapped[ProspectModel] = relationship()


class SegmentRegistryModel(Base):
    __tablename__ = "segments"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    pdm_code: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="ACTIVE")
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class DecisionMakerModel(Base):
    __tablename__ = "decision_makers"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    prospect_id: Mapped[str] = mapped_column(
        ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str | None] = mapped_column(String)
    linkedin: Mapped[str | None] = mapped_column(String)
    authority_score: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    acquisition_rationale: Mapped[str | None] = mapped_column(Text)
    entry_source: Mapped[str] = mapped_column(String, nullable=False, default="MANUAL")
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)

    prospect: Mapped[ProspectModel] = relationship(back_populates="decision_makers")
    contact_paths: Mapped[list[ContactPathModel]] = relationship(
        back_populates="decision_maker", cascade="all, delete-orphan"
    )


class ContactPathModel(Base):
    __tablename__ = "contact_paths"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    decision_maker_id: Mapped[str] = mapped_column(
        ForeignKey("decision_makers.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False, default="MANUAL")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_verified_at: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    decision_maker: Mapped[DecisionMakerModel] = relationship(back_populates="contact_paths")


class AcquisitionHypothesisModel(Base):
    __tablename__ = "acquisition_hypotheses"
    __table_args__ = (
        # Exactly one active outreach hypothesis per offer x prospect pair.
        Index(
            "uq_active_hypothesis",
            "offer_id",
            "prospect_id",
            unique=True,
            sqlite_where=text("is_active = 1"),
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    offer_id: Mapped[str] = mapped_column(
        ForeignKey("offers.id", ondelete="CASCADE"), nullable=False
    )
    prospect_id: Mapped[str] = mapped_column(
        ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False
    )
    decision_maker_id: Mapped[str | None] = mapped_column(
        ForeignKey("decision_makers.id", ondelete="SET NULL")
    )
    refines_hypothesis_id: Mapped[str | None] = mapped_column(
        ForeignKey("acquisition_hypotheses.id", ondelete="SET NULL")
    )
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    recipient_framing: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str | None] = mapped_column(String)
    model: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, nullable=False, default="DRAFT")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reasoning_confidence: Mapped[int | None] = mapped_column(Integer)
    reasoning_confidence_explanation: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]"
    )
    # Reserved for MVP 1.4 outcome integration; must stay NULL in MVP 1.3.
    empirical_confidence: Mapped[float | None] = mapped_column(Float)
    reviewer_assessment: Mapped[str | None] = mapped_column(String)
    superseded_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("acquisition_hypotheses.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[str | None] = mapped_column(String)
    review_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)

    offer: Mapped[OfferModel] = relationship()
    prospect: Mapped[ProspectModel] = relationship()
    decision_maker: Mapped[DecisionMakerModel | None] = relationship()
    evidence_links: Mapped[list[HypothesisEvidenceLinkModel]] = relationship(
        back_populates="hypothesis", cascade="all, delete-orphan"
    )
    audit_events: Mapped[list[HypothesisAuditEventModel]] = relationship(
        back_populates="hypothesis", cascade="all, delete-orphan"
    )


class HypothesisEvidenceLinkModel(Base):
    __tablename__ = "hypothesis_evidence_links"
    __table_args__ = (
        UniqueConstraint(
            "hypothesis_id",
            "evidence_entry_id",
            name="uq_hypothesis_evidence",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    hypothesis_id: Mapped[str] = mapped_column(
        ForeignKey("acquisition_hypotheses.id", ondelete="CASCADE"), nullable=False
    )
    # RESTRICT: referenced evidence is part of the historical decision trail
    # and may transition lifecycle states, but never be physically deleted.
    evidence_entry_id: Mapped[str] = mapped_column(
        ForeignKey("evidence_entries.id", ondelete="RESTRICT"), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    hypothesis: Mapped[AcquisitionHypothesisModel] = relationship(
        back_populates="evidence_links"
    )
    evidence_entry: Mapped[EvidenceEntryModel] = relationship()


class HypothesisAuditEventModel(Base):
    __tablename__ = "hypothesis_audit_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    hypothesis_id: Mapped[str] = mapped_column(
        ForeignKey("acquisition_hypotheses.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    hypothesis: Mapped[AcquisitionHypothesisModel] = relationship(
        back_populates="audit_events"
    )


