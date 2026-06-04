from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    evidence_entry: Mapped[EvidenceEntryModel | None] = relationship()
