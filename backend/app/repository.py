from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .reasoning_confidence import compute_reasoning_confidence
from .schemas import (
    EvidenceStatus,
    HypothesisSource,
    HypothesisStatus,
    ReviewerAssessment,
    AlphaSignal,
    AlphaSignalCreate,
    CampaignBatch,
    CampaignBatchCreate,
    CampaignBatchProspect,
    CampaignOutcome,
    CampaignOutcomeCreate,
    ConfidenceUpdate,
    ConfidenceUpdateCreate,
    EvidenceEntry,
    EvidenceEntryCreate,
    Offer,
    OfferBuyerProfile,
    OfferCreate,
    OfferEvaluationProposal,
    OfferIntelligenceProfile,
    OfferPdm,
    OfferProspectFit,
    OfferProfile,
    OfferProposalStatus,
    OfferSignalProfile,
    OfferStatus,
    Prospect,
    ProspectAlphaSignal,
    ProspectAlphaSignalCreate,
    ProspectCreate,
    ProspectScore,
    ProspectScoreRead,
    ScoreExplanationRead,
    Signal,
    SignalCreate,
    SegmentRegistry,
    SegmentRegistryCreate,
    DecisionMaker,
    DecisionMakerCreate,
    ContactPath,
    ContactPathCreate,
    utc_now_iso,
)


def prefixed_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10].upper()}"


class RepositoryConflictError(Exception):
    pass


class HypothesisGovernanceError(Exception):
    """A governed hypothesis operation violated the ratified MVP 1.3 contract."""


# Lifecycle transitions implemented in MVP 1.3. VALIDATING / SUPPORTED /
# WEAKENED are dormant until MVP 1.4 outcome integration and are rejected as
# targets from every state (see _transition).
ALLOWED_HYPOTHESIS_TRANSITIONS: dict[str, set[str]] = {
    HypothesisStatus.DRAFT: {HypothesisStatus.PROPOSED},
    HypothesisStatus.PROPOSED: {
        HypothesisStatus.APPROVED,
        HypothesisStatus.REJECTED,
        HypothesisStatus.SUPERSEDED,
    },
    HypothesisStatus.APPROVED: {HypothesisStatus.SUPERSEDED},
    HypothesisStatus.REJECTED: {HypothesisStatus.SUPERSEDED},
    HypothesisStatus.SUPERSEDED: set(),
    HypothesisStatus.VALIDATING: set(),
    HypothesisStatus.SUPPORTED: set(),
    HypothesisStatus.WEAKENED: set(),
}

DORMANT_HYPOTHESIS_STATUSES = {
    HypothesisStatus.VALIDATING,
    HypothesisStatus.SUPPORTED,
    HypothesisStatus.WEAKENED,
}

# Ruling 2: only non-canonical operator metadata may be corrected in place.
CORRECTABLE_HYPOTHESIS_FIELDS = {"review_notes"}

_UNSET = object()


class Repository:
    def __init__(self, session: Session):
        self.session = session

    def create_prospect(self, data: ProspectCreate) -> Prospect:
        segment = self.get_segment_by_code(data.segment)
        if not segment:
            raise RepositoryConflictError(f"Segment code '{data.segment}' is not registered")
        model = models.ProspectModel(
            id=prefixed_id("P"),
            created_at=utc_now_iso(),
            **data.model_dump(mode="json"),
        )
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return Prospect.model_validate(model)

    def list_prospects(self) -> list[Prospect]:
        rows = self.session.scalars(
            select(models.ProspectModel).order_by(models.ProspectModel.created_at.desc())
        ).all()
        return [Prospect.model_validate(row) for row in rows]

    def get_prospect(self, prospect_id: str) -> Prospect | None:
        model = self.session.get(models.ProspectModel, prospect_id)
        return Prospect.model_validate(model) if model else None

    def create_segment_registry_entry(self, data: SegmentRegistryCreate) -> SegmentRegistry:
        existing = self.session.scalar(
            select(models.SegmentRegistryModel).where(models.SegmentRegistryModel.code == data.code)
        )
        if existing:
            raise RepositoryConflictError("Segment code already exists")
        model = models.SegmentRegistryModel(
            id=prefixed_id("SEG"),
            created_at=utc_now_iso(),
            **data.model_dump(mode="json"),
        )
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return SegmentRegistry.model_validate(model)

    def list_segments(self) -> list[SegmentRegistry]:
        rows = self.session.scalars(
            select(models.SegmentRegistryModel).order_by(models.SegmentRegistryModel.code.asc())
        ).all()
        return [SegmentRegistry.model_validate(row) for row in rows]

    def get_segment_by_code(self, code: str) -> SegmentRegistry | None:
        model = self.session.scalar(
            select(models.SegmentRegistryModel).where(models.SegmentRegistryModel.code == code)
        )
        return SegmentRegistry.model_validate(model) if model else None

    def create_signal(self, prospect_id: str, data: SignalCreate) -> Signal:
        model = models.SignalModel(
            id=prefixed_id("S"),
            prospect_id=prospect_id,
            created_at=utc_now_iso(),
            **data.model_dump(mode="json"),
        )
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return Signal.model_validate(model)

    def list_signals(self, prospect_id: str) -> list[Signal]:
        rows = self.session.scalars(
            select(models.SignalModel)
            .where(models.SignalModel.prospect_id == prospect_id)
            .order_by(models.SignalModel.created_at.asc())
        ).all()
        return [Signal.model_validate(row) for row in rows]

    def create_alpha_signal(self, data: AlphaSignalCreate) -> AlphaSignal:
        existing = self.session.scalar(
            select(models.AlphaSignalModel).where(models.AlphaSignalModel.code == data.code)
        )
        if existing:
            raise RepositoryConflictError("Alpha Signal code already exists")

        model = models.AlphaSignalModel(
            id=prefixed_id("AS"),
            code=data.code,
            name=data.name,
            description=data.description,
            required_signals=json.dumps(data.required_signals),
            bonus_score=data.bonus_score,
            validation_status=data.validation_status,
            created_at=utc_now_iso(),
        )
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return self._alpha_signal_from_model(model)

    def list_alpha_signals(self) -> list[AlphaSignal]:
        rows = self.session.scalars(
            select(models.AlphaSignalModel).order_by(models.AlphaSignalModel.code.asc())
        ).all()
        return [self._alpha_signal_from_model(row) for row in rows]

    def get_alpha_signal(self, alpha_signal_id: str) -> AlphaSignal | None:
        model = self.session.get(models.AlphaSignalModel, alpha_signal_id)
        return self._alpha_signal_from_model(model) if model else None

    def assign_alpha_signal(
        self,
        prospect_id: str,
        alpha_signal_id: str,
        data: ProspectAlphaSignalCreate,
    ) -> ProspectAlphaSignal:
        existing = self.session.scalar(
            select(models.ProspectAlphaSignalModel).where(
                models.ProspectAlphaSignalModel.prospect_id == prospect_id,
                models.ProspectAlphaSignalModel.alpha_signal_id == alpha_signal_id,
            )
        )
        if existing:
            raise RepositoryConflictError("Alpha Signal already assigned to prospect")

        model = models.ProspectAlphaSignalModel(
            id=prefixed_id("PAS"),
            prospect_id=prospect_id,
            alpha_signal_id=alpha_signal_id,
            notes=data.notes,
            created_at=utc_now_iso(),
        )
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return self._prospect_alpha_signal_from_model(model)

    def list_prospect_alpha_signals(self, prospect_id: str) -> list[ProspectAlphaSignal]:
        rows = self.session.scalars(
            select(models.ProspectAlphaSignalModel)
            .where(models.ProspectAlphaSignalModel.prospect_id == prospect_id)
            .order_by(models.ProspectAlphaSignalModel.created_at.asc())
        ).all()
        return [self._prospect_alpha_signal_from_model(row) for row in rows]

    def list_alpha_signals_for_prospect(self, prospect_id: str) -> list[AlphaSignal]:
        rows = self.session.scalars(
            select(models.AlphaSignalModel)
            .join(models.ProspectAlphaSignalModel)
            .where(models.ProspectAlphaSignalModel.prospect_id == prospect_id)
        ).all()
        return [self._alpha_signal_from_model(row) for row in rows]

    def save_score(self, score: ProspectScore) -> ProspectScore:
        score_id = prefixed_id("PS")
        model = models.ProspectScoreModel(
            id=score_id,
            prospect_id=score.prospect_id,
            tier1_total=score.tier1_total,
            tier2_total=score.tier2_total,
            tier3_total=score.tier3_total,
            base_score=score.base_score,
            alpha_bonus=score.alpha_bonus,
            final_score=score.final_score,
            decision=score.decision,
            calculated_at=score.calculated_at,
        )
        self.session.add(model)
        for item in score.explanation:
            self.session.add(
                models.ScoreExplanationModel(
                    id=prefixed_id("SE"),
                    prospect_score_id=score_id,
                    **item.model_dump(mode="json"),
                )
            )
        self.session.commit()
        return score

    def list_scores(self, prospect_id: str) -> list[ProspectScoreRead]:
        rows = self.session.scalars(
            select(models.ProspectScoreModel)
            .where(models.ProspectScoreModel.prospect_id == prospect_id)
            .order_by(models.ProspectScoreModel.calculated_at.desc())
        ).all()
        return [self._score_from_model(row) for row in rows]

    def get_score(self, score_id: str) -> ProspectScoreRead | None:
        model = self.session.get(models.ProspectScoreModel, score_id)
        return self._score_from_model(model) if model else None

    def create_campaign_batch(self, data: CampaignBatchCreate) -> CampaignBatch:
        model = models.CampaignBatchModel(
            id=prefixed_id("CB"),
            created_at=utc_now_iso(),
            **data.model_dump(mode="json"),
        )
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return CampaignBatch.model_validate(model)

    def list_campaign_batches(self) -> list[CampaignBatch]:
        rows = self.session.scalars(
            select(models.CampaignBatchModel).order_by(
                models.CampaignBatchModel.created_at.desc()
            )
        ).all()
        return [CampaignBatch.model_validate(row) for row in rows]

    def get_campaign_batch(self, campaign_batch_id: str) -> CampaignBatch | None:
        model = self.session.get(models.CampaignBatchModel, campaign_batch_id)
        return CampaignBatch.model_validate(model) if model else None

    def add_prospect_to_campaign_batch(
        self, campaign_batch_id: str, prospect_id: str
    ) -> CampaignBatchProspect:
        existing = self.session.scalar(
            select(models.CampaignBatchProspectModel).where(
                models.CampaignBatchProspectModel.campaign_batch_id == campaign_batch_id,
                models.CampaignBatchProspectModel.prospect_id == prospect_id,
            )
        )
        if existing:
            raise RepositoryConflictError("Prospect already belongs to campaign batch")

        model = models.CampaignBatchProspectModel(
            id=prefixed_id("CBP"),
            campaign_batch_id=campaign_batch_id,
            prospect_id=prospect_id,
            created_at=utc_now_iso(),
        )
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return CampaignBatchProspect.model_validate(model)

    def campaign_batch_contains_prospect(
        self, campaign_batch_id: str, prospect_id: str
    ) -> bool:
        existing = self.session.scalar(
            select(models.CampaignBatchProspectModel).where(
                models.CampaignBatchProspectModel.campaign_batch_id == campaign_batch_id,
                models.CampaignBatchProspectModel.prospect_id == prospect_id,
            )
        )
        return existing is not None

    def list_campaign_batch_prospects(
        self, campaign_batch_id: str
    ) -> list[CampaignBatchProspect]:
        rows = self.session.scalars(
            select(models.CampaignBatchProspectModel)
            .where(models.CampaignBatchProspectModel.campaign_batch_id == campaign_batch_id)
            .order_by(models.CampaignBatchProspectModel.created_at.asc())
        ).all()
        return [CampaignBatchProspect.model_validate(row) for row in rows]

    def create_campaign_outcome(self, data: CampaignOutcomeCreate) -> CampaignOutcome:
        model = models.CampaignOutcomeModel(
            id=prefixed_id("CO"),
            **data.model_dump(mode="json"),
        )
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return CampaignOutcome.model_validate(model)

    def list_campaign_outcomes(
        self, campaign_batch_id: str | None = None
    ) -> list[CampaignOutcome]:
        statement = select(models.CampaignOutcomeModel)
        if campaign_batch_id:
            statement = statement.where(
                models.CampaignOutcomeModel.campaign_batch_id == campaign_batch_id
            )
        rows = self.session.scalars(
            statement.order_by(models.CampaignOutcomeModel.recorded_at.desc())
        ).all()
        return [CampaignOutcome.model_validate(row) for row in rows]

    def get_campaign_outcome(self, campaign_outcome_id: str) -> CampaignOutcome | None:
        model = self.session.get(models.CampaignOutcomeModel, campaign_outcome_id)
        return CampaignOutcome.model_validate(model) if model else None

    def update_campaign_outcome(
        self, campaign_outcome_id: str, data: CampaignOutcomeCreate
    ) -> CampaignOutcome | None:
        model = self.session.get(models.CampaignOutcomeModel, campaign_outcome_id)
        if model is None:
            return None
        for key, value in data.model_dump(mode="json").items():
            setattr(model, key, value)
        self.session.commit()
        self.session.refresh(model)
        return CampaignOutcome.model_validate(model)

    def create_evidence_entry(self, data: EvidenceEntryCreate) -> EvidenceEntry:
        model = models.EvidenceEntryModel(
            id=prefixed_id("EV"),
            created_at=utc_now_iso(),
            **data.model_dump(mode="json"),
        )
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return EvidenceEntry.model_validate(model)

    def list_evidence_entries(
        self, pdm_code: str | None = None, offer_id: str | None = None
    ) -> list[EvidenceEntry]:
        statement = select(models.EvidenceEntryModel)
        if pdm_code:
            statement = statement.where(models.EvidenceEntryModel.pdm_code == pdm_code)
        if offer_id:
            statement = statement.where(models.EvidenceEntryModel.offer_id == offer_id)
        rows = self.session.scalars(
            statement.order_by(models.EvidenceEntryModel.created_at.desc())
        ).all()
        return [EvidenceEntry.model_validate(row) for row in rows]

    def get_evidence_entry(self, evidence_entry_id: str) -> EvidenceEntry | None:
        model = self.session.get(models.EvidenceEntryModel, evidence_entry_id)
        return EvidenceEntry.model_validate(model) if model else None

    def create_confidence_update(
        self, data: ConfidenceUpdateCreate
    ) -> ConfidenceUpdate:
        model = models.ConfidenceUpdateModel(
            id=prefixed_id("CU"),
            created_at=utc_now_iso(),
            **data.model_dump(mode="json"),
        )
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return ConfidenceUpdate.model_validate(model)

    def list_confidence_updates(
        self, pdm_code: str | None = None, offer_id: str | None = None
    ) -> list[ConfidenceUpdate]:
        statement = select(models.ConfidenceUpdateModel)
        if pdm_code:
            statement = statement.where(models.ConfidenceUpdateModel.pdm_code == pdm_code)
        if offer_id:
            statement = statement.where(models.ConfidenceUpdateModel.offer_id == offer_id)
        rows = self.session.scalars(
            statement.order_by(models.ConfidenceUpdateModel.created_at.desc())
        ).all()
        return [ConfidenceUpdate.model_validate(row) for row in rows]

    def create_offer(self, data: OfferCreate) -> Offer:
        model = models.OfferModel(
            id=prefixed_id("O"),
            created_at=utc_now_iso(),
            **data.model_dump(mode="json"),
        )
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return Offer.model_validate(model)

    def list_offers(self) -> list[Offer]:
        rows = self.session.scalars(
            select(models.OfferModel).order_by(models.OfferModel.created_at.desc())
        ).all()
        return [Offer.model_validate(row) for row in rows]

    def get_offer(self, offer_id: str) -> Offer | None:
        model = self.session.get(models.OfferModel, offer_id)
        return Offer.model_validate(model) if model else None

    def update_offer_status(self, offer_id: str, status: OfferStatus) -> Offer | None:
        model = self.session.get(models.OfferModel, offer_id)
        if model is None:
            return None
        model.status = status.value
        self.session.commit()
        self.session.refresh(model)
        return Offer.model_validate(model)

    def create_offer_evaluation_proposal(
        self,
        offer_id: str,
        provider: str,
        model_name: str | None,
        mode: str,
        raw_domain: str,
        normalized_domain: str,
        proposal: dict,
    ) -> OfferEvaluationProposal:
        model = models.OfferEvaluationProposalModel(
            id=prefixed_id("OEP"),
            offer_id=offer_id,
            provider=provider,
            model=model_name,
            mode=mode,
            raw_domain=raw_domain,
            normalized_domain=normalized_domain,
            primary_category=proposal["primary_category"],
            confidence_score=proposal["confidence_score"],
            confidence_label=proposal["confidence_label"],
            reasoning=json.dumps(proposal.get("reasoning", [])),
            alternative_categories=json.dumps(proposal.get("alternative_categories", [])),
            proposed_profile_json=json.dumps(proposal),
            status=OfferProposalStatus.PENDING_REVIEW.value,
            created_at=utc_now_iso(),
        )
        self.session.add(model)
        offer_model = self.session.get(models.OfferModel, offer_id)
        if offer_model is not None:
            offer_model.status = OfferStatus.PROPOSED.value
        self.session.commit()
        self.session.refresh(model)
        return self._offer_proposal_from_model(model)

    def list_offer_proposals(self, offer_id: str) -> list[OfferEvaluationProposal]:
        rows = self.session.scalars(
            select(models.OfferEvaluationProposalModel)
            .where(models.OfferEvaluationProposalModel.offer_id == offer_id)
            .order_by(models.OfferEvaluationProposalModel.created_at.desc())
        ).all()
        return [self._offer_proposal_from_model(row) for row in rows]

    def get_offer_proposal(
        self, offer_id: str, proposal_id: str
    ) -> OfferEvaluationProposal | None:
        model = self.session.scalar(
            select(models.OfferEvaluationProposalModel).where(
                models.OfferEvaluationProposalModel.offer_id == offer_id,
                models.OfferEvaluationProposalModel.id == proposal_id,
            )
        )
        return self._offer_proposal_from_model(model) if model else None

    def reject_offer_proposal(
        self, offer_id: str, proposal_id: str, review_notes: str | None
    ) -> OfferEvaluationProposal | None:
        model = self.session.scalar(
            select(models.OfferEvaluationProposalModel).where(
                models.OfferEvaluationProposalModel.offer_id == offer_id,
                models.OfferEvaluationProposalModel.id == proposal_id,
            )
        )
        if model is None:
            return None
        model.status = OfferProposalStatus.REJECTED.value
        model.reviewed_at = utc_now_iso()
        model.review_notes = review_notes
        self.session.commit()
        self.session.refresh(model)
        return self._offer_proposal_from_model(model)

    def approve_offer_proposal(
        self, offer_id: str, proposal_id: str, review_notes: str | None
    ) -> OfferIntelligenceProfile | None:
        proposal = self.session.scalar(
            select(models.OfferEvaluationProposalModel).where(
                models.OfferEvaluationProposalModel.offer_id == offer_id,
                models.OfferEvaluationProposalModel.id == proposal_id,
            )
        )
        if proposal is None or proposal.status != OfferProposalStatus.PENDING_REVIEW.value:
            return None

        self._clear_offer_profile_rows(offer_id)
        data = json.loads(proposal.proposed_profile_json)
        profile = models.OfferProfileModel(
            id=prefixed_id("OP"),
            offer_id=offer_id,
            offer_category=data["primary_category"],
            commercial_hypothesis=data["commercial_hypothesis"],
            predicted_value_range=data["predicted_value_range"],
            target_segments=json.dumps(data.get("target_segments", [])),
            created_at=utc_now_iso(),
        )
        self.session.add(profile)
        for buyer in data.get("buyer_profiles", []):
            self.session.add(
                models.OfferBuyerProfileModel(
                    id=prefixed_id("OBP"),
                    offer_id=offer_id,
                    created_at=utc_now_iso(),
                    **buyer,
                )
            )
        for signal in data.get("signal_profiles", []):
            self.session.add(
                models.OfferSignalProfileModel(
                    id=prefixed_id("OSP"),
                    offer_id=offer_id,
                    created_at=utc_now_iso(),
                    **signal,
                )
            )
        pdm = data["pdm"]
        self.session.add(
            models.OfferPdmModel(
                id=prefixed_id("OPDM"),
                offer_id=offer_id,
                code=pdm["code"],
                name=pdm["name"],
                summary=pdm["summary"],
                target_segments=json.dumps(pdm.get("target_segments", [])),
                created_at=utc_now_iso(),
            )
        )
        proposal.status = OfferProposalStatus.APPROVED.value
        proposal.reviewed_at = utc_now_iso()
        proposal.review_notes = review_notes
        for old_proposal in self.session.scalars(
            select(models.OfferEvaluationProposalModel).where(
                models.OfferEvaluationProposalModel.offer_id == offer_id,
                models.OfferEvaluationProposalModel.id != proposal_id,
                models.OfferEvaluationProposalModel.status == OfferProposalStatus.APPROVED.value,
            )
        ).all():
            old_proposal.status = OfferProposalStatus.SUPERSEDED.value
        offer_model = self.session.get(models.OfferModel, offer_id)
        if offer_model is not None:
            offer_model.status = OfferStatus.PROFILED.value
        self.session.commit()
        return self.get_offer_intelligence_profile(offer_id)

    def get_offer_intelligence_profile(
        self, offer_id: str
    ) -> OfferIntelligenceProfile | None:
        offer = self.session.get(models.OfferModel, offer_id)
        profile = self.session.scalar(
            select(models.OfferProfileModel).where(models.OfferProfileModel.offer_id == offer_id)
        )
        pdm = self.session.scalar(
            select(models.OfferPdmModel).where(models.OfferPdmModel.offer_id == offer_id)
        )
        if offer is None or profile is None or pdm is None:
            return None
        buyers = self.session.scalars(
            select(models.OfferBuyerProfileModel)
            .where(models.OfferBuyerProfileModel.offer_id == offer_id)
            .order_by(models.OfferBuyerProfileModel.priority.asc())
        ).all()
        signals = self.session.scalars(
            select(models.OfferSignalProfileModel)
            .where(models.OfferSignalProfileModel.offer_id == offer_id)
            .order_by(models.OfferSignalProfileModel.tier.asc())
        ).all()
        return OfferIntelligenceProfile(
            offer=Offer.model_validate(offer),
            profile=self._offer_profile_from_model(profile),
            buyerProfiles=[OfferBuyerProfile.model_validate(row) for row in buyers],
            signalProfiles=[OfferSignalProfile.model_validate(row) for row in signals],
            pdm=self._offer_pdm_from_model(pdm),
        )

    def replace_offer_prospect_fits(
        self, offer_id: str, fits: list[OfferProspectFit]
    ) -> list[OfferProspectFit]:
        existing = self.session.scalars(
            select(models.OfferProspectFitModel).where(
                models.OfferProspectFitModel.offer_id == offer_id
            )
        ).all()
        for row in existing:
            self.session.delete(row)
        for fit in fits:
            self.session.add(
                models.OfferProspectFitModel(
                    id=prefixed_id("OPF"),
                    offer_id=fit.offer_id,
                    prospect_id=fit.prospect_id,
                    segment_fit_score=fit.segment_fit_score,
                    buyer_profile_fit_score=fit.buyer_profile_fit_score,
                    signal_fit_score=fit.signal_fit_score,
                    total_fit_score=fit.total_fit_score,
                    decision=fit.decision,
                    explanation=json.dumps(fit.explanation),
                    created_at=utc_now_iso(),
                )
            )
        self.session.commit()
        return self.list_offer_prospect_fits(offer_id)

    def list_offer_prospect_fits(self, offer_id: str) -> list[OfferProspectFit]:
        rows = self.session.scalars(
            select(models.OfferProspectFitModel)
            .where(models.OfferProspectFitModel.offer_id == offer_id)
            .order_by(models.OfferProspectFitModel.total_fit_score.desc())
        ).all()
        return [self._offer_fit_from_model(row) for row in rows]

    def create_decision_maker(
        self,
        prospect_id: str,
        data: DecisionMakerCreate,
        authority_score: int,
        rationale: str | None,
    ) -> DecisionMaker:
        now = utc_now_iso()
        model = models.DecisionMakerModel(
            id=prefixed_id("DM"),
            prospect_id=prospect_id,
            name=data.name,
            role=data.role,
            email=data.email,
            linkedin=data.linkedin,
            authority_score=authority_score,
            acquisition_rationale=rationale,
            entry_source=data.entry_source,
            created_at=now,
            updated_at=now,
        )
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return DecisionMaker.model_validate(model)

    def list_decision_makers(self, prospect_id: str) -> list[DecisionMaker]:
        statement = (
            select(models.DecisionMakerModel)
            .where(models.DecisionMakerModel.prospect_id == prospect_id)
            .order_by(models.DecisionMakerModel.authority_score.desc())
        )
        rows = self.session.scalars(statement).all()
        return [DecisionMaker.model_validate(row) for row in rows]

    def get_decision_maker(self, decision_maker_id: str) -> DecisionMaker | None:
        model = self.session.get(models.DecisionMakerModel, decision_maker_id)
        return DecisionMaker.model_validate(model) if model else None

    def update_decision_maker(
        self,
        decision_maker_id: str,
        data: DecisionMakerCreate,
        authority_score: int,
        rationale: str | None,
    ) -> DecisionMaker | None:
        model = self.session.get(models.DecisionMakerModel, decision_maker_id)
        if not model:
            return None
        model.name = data.name
        model.role = data.role
        model.email = data.email
        model.linkedin = data.linkedin
        model.authority_score = authority_score
        model.acquisition_rationale = rationale
        model.entry_source = data.entry_source
        model.updated_at = utc_now_iso()
        self.session.commit()
        self.session.refresh(model)
        return DecisionMaker.model_validate(model)

    def delete_decision_maker(self, decision_maker_id: str) -> bool:
        model = self.session.get(models.DecisionMakerModel, decision_maker_id)
        if not model:
            return False
        self.session.delete(model)
        self.session.commit()
        return True

    def create_contact_path(
        self, decision_maker_id: str, data: ContactPathCreate
    ) -> ContactPath:
        model = models.ContactPathModel(
            id=prefixed_id("CP"),
            decision_maker_id=decision_maker_id,
            created_at=utc_now_iso(),
            **data.model_dump(mode="json"),
        )
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return ContactPath.model_validate(model)

    def list_contact_paths(self, decision_maker_id: str) -> list[ContactPath]:
        rows = self.session.scalars(
            select(models.ContactPathModel)
            .where(models.ContactPathModel.decision_maker_id == decision_maker_id)
            .order_by(models.ContactPathModel.created_at.asc())
        ).all()
        return [ContactPath.model_validate(row) for row in rows]

    def get_contact_path(self, contact_path_id: str) -> ContactPath | None:
        model = self.session.get(models.ContactPathModel, contact_path_id)
        return ContactPath.model_validate(model) if model else None

    def update_contact_path(
        self, contact_path_id: str, data: ContactPathCreate
    ) -> ContactPath | None:
        model = self.session.get(models.ContactPathModel, contact_path_id)
        if not model:
            return None
        for key, value in data.model_dump(mode="json").items():
            setattr(model, key, value)
        self.session.commit()
        self.session.refresh(model)
        return ContactPath.model_validate(model)

    def delete_contact_path(self, contact_path_id: str) -> bool:
        model = self.session.get(models.ContactPathModel, contact_path_id)
        if not model:
            return False
        self.session.delete(model)
        self.session.commit()
        return True

    # ------------------------------------------------------------------
    # Acquisition hypotheses (MVP 1.3A-2) — governed by the ratified
    # contract in docs/MVP13AcquisitionHypothesisScoping.md.
    # ------------------------------------------------------------------

    def create_hypothesis(
        self,
        offer_id: str,
        prospect_id: str,
        statement: str,
        source: str,
        *,
        decision_maker_id: str | None = None,
        refines_hypothesis_id: str | None = None,
        recipient_framing: str | None = None,
        provider: str | None = None,
        model_name: str | None = None,
    ) -> models.AcquisitionHypothesisModel:
        if source not in set(HypothesisSource):
            raise HypothesisGovernanceError(f"Unknown hypothesis source: {source}")
        if not statement or not statement.strip():
            raise HypothesisGovernanceError("Hypothesis statement must not be empty")
        if self.session.get(models.OfferModel, offer_id) is None:
            raise HypothesisGovernanceError(f"Offer not found: {offer_id}")
        if self.session.get(models.ProspectModel, prospect_id) is None:
            raise HypothesisGovernanceError(f"Prospect not found: {prospect_id}")
        if decision_maker_id is not None:
            decision_maker = self.session.get(models.DecisionMakerModel, decision_maker_id)
            if decision_maker is None or decision_maker.prospect_id != prospect_id:
                raise HypothesisGovernanceError(
                    "Decision maker must exist and belong to the bound prospect"
                )
        if refines_hypothesis_id is not None:
            parent = self.session.get(
                models.AcquisitionHypothesisModel, refines_hypothesis_id
            )
            if parent is None or parent.offer_id != offer_id or parent.prospect_id != prospect_id:
                raise HypothesisGovernanceError(
                    "Refined hypothesis must exist and share the same offer and prospect"
                )
        now = utc_now_iso()
        model = models.AcquisitionHypothesisModel(
            id=prefixed_id("AH"),
            offer_id=offer_id,
            prospect_id=prospect_id,
            decision_maker_id=decision_maker_id,
            refines_hypothesis_id=refines_hypothesis_id,
            statement=statement,
            recipient_framing=recipient_framing,
            source=source,
            provider=provider,
            model=model_name,
            status=HypothesisStatus.DRAFT.value,
            is_active=False,
            created_at=now,
            updated_at=now,
        )
        try:
            self.session.add(model)
            self._record_hypothesis_audit(
                model.id, "CREATED", {"source": source, "statement": statement}
            )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        self.session.refresh(model)
        return model

    def get_hypothesis(self, hypothesis_id: str) -> models.AcquisitionHypothesisModel | None:
        return self.session.get(models.AcquisitionHypothesisModel, hypothesis_id)

    def get_active_hypothesis(
        self, offer_id: str, prospect_id: str
    ) -> models.AcquisitionHypothesisModel | None:
        return self.session.scalar(
            select(models.AcquisitionHypothesisModel).where(
                models.AcquisitionHypothesisModel.offer_id == offer_id,
                models.AcquisitionHypothesisModel.prospect_id == prospect_id,
                models.AcquisitionHypothesisModel.is_active == True,  # noqa: E712
            )
        )

    def list_hypotheses(
        self, offer_id: str, prospect_id: str
    ) -> list[models.AcquisitionHypothesisModel]:
        return list(
            self.session.scalars(
                select(models.AcquisitionHypothesisModel)
                .where(
                    models.AcquisitionHypothesisModel.offer_id == offer_id,
                    models.AcquisitionHypothesisModel.prospect_id == prospect_id,
                )
                .order_by(
                    models.AcquisitionHypothesisModel.created_at.asc(),
                    models.AcquisitionHypothesisModel.id.asc(),
                )
            )
        )

    def list_hypothesis_evidence_links(
        self, hypothesis_id: str
    ) -> list[models.HypothesisEvidenceLinkModel]:
        return list(
            self.session.scalars(
                select(models.HypothesisEvidenceLinkModel)
                .where(models.HypothesisEvidenceLinkModel.hypothesis_id == hypothesis_id)
                .order_by(
                    models.HypothesisEvidenceLinkModel.created_at.asc(),
                    models.HypothesisEvidenceLinkModel.id.asc(),
                )
            )
        )

    def list_hypothesis_audit_events(
        self, hypothesis_id: str
    ) -> list[models.HypothesisAuditEventModel]:
        return list(
            self.session.scalars(
                select(models.HypothesisAuditEventModel)
                .where(models.HypothesisAuditEventModel.hypothesis_id == hypothesis_id)
                .order_by(
                    models.HypothesisAuditEventModel.created_at.asc(),
                    models.HypothesisAuditEventModel.id.asc(),
                )
            )
        )

    def update_draft_hypothesis(
        self,
        hypothesis_id: str,
        *,
        statement: object = _UNSET,
        recipient_framing: object = _UNSET,
    ) -> models.AcquisitionHypothesisModel:
        model = self._require_hypothesis(hypothesis_id)
        self._require_draft(model, "Canonical content is frozen once a hypothesis leaves DRAFT")
        changes: dict[str, dict[str, str | None]] = {}
        if statement is not _UNSET:
            if not statement or not str(statement).strip():
                raise HypothesisGovernanceError("Hypothesis statement must not be empty")
            changes["statement"] = {"before": model.statement, "after": str(statement)}
            model.statement = str(statement)
        if recipient_framing is not _UNSET:
            changes["recipient_framing"] = {
                "before": model.recipient_framing,
                "after": recipient_framing if recipient_framing is None else str(recipient_framing),
            }
            model.recipient_framing = (
                recipient_framing if recipient_framing is None else str(recipient_framing)
            )
        if not changes:
            return model
        model.updated_at = utc_now_iso()
        try:
            self._record_hypothesis_audit(model.id, "DRAFT_UPDATED", changes)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return model

    def attach_evidence(
        self, hypothesis_id: str, evidence_entry_id: str, note: str | None = None
    ) -> models.HypothesisEvidenceLinkModel:
        model = self._require_hypothesis(hypothesis_id)
        self._require_draft(model, "Evidence set is frozen once a hypothesis leaves DRAFT")
        evidence = self.session.get(models.EvidenceEntryModel, evidence_entry_id)
        if evidence is None:
            raise HypothesisGovernanceError(f"Evidence entry not found: {evidence_entry_id}")
        if evidence.status != EvidenceStatus.ACTIVE.value:
            raise HypothesisGovernanceError(
                f"Only ACTIVE evidence may be newly attached (status={evidence.status})"
            )
        existing = self.session.scalar(
            select(models.HypothesisEvidenceLinkModel).where(
                models.HypothesisEvidenceLinkModel.hypothesis_id == hypothesis_id,
                models.HypothesisEvidenceLinkModel.evidence_entry_id == evidence_entry_id,
            )
        )
        if existing:
            raise RepositoryConflictError("Evidence already attached to hypothesis")
        link = models.HypothesisEvidenceLinkModel(
            id=prefixed_id("HEL"),
            hypothesis_id=hypothesis_id,
            evidence_entry_id=evidence_entry_id,
            note=note,
            created_at=utc_now_iso(),
        )
        try:
            self.session.add(link)
            self._invalidate_confidence(model)
            self._record_hypothesis_audit(
                model.id,
                "EVIDENCE_ATTACHED",
                {"evidence_entry_id": evidence_entry_id, "note": note},
            )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        self.session.refresh(link)
        return link

    def detach_evidence(self, hypothesis_id: str, evidence_entry_id: str) -> None:
        model = self._require_hypothesis(hypothesis_id)
        self._require_draft(model, "Evidence set is frozen once a hypothesis leaves DRAFT")
        link = self.session.scalar(
            select(models.HypothesisEvidenceLinkModel).where(
                models.HypothesisEvidenceLinkModel.hypothesis_id == hypothesis_id,
                models.HypothesisEvidenceLinkModel.evidence_entry_id == evidence_entry_id,
            )
        )
        if link is None:
            raise HypothesisGovernanceError("Evidence link not found")
        try:
            self.session.delete(link)
            self._invalidate_confidence(model)
            self._record_hypothesis_audit(
                model.id, "EVIDENCE_DETACHED", {"evidence_entry_id": evidence_entry_id}
            )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def compute_hypothesis_confidence(
        self, hypothesis_id: str, now: datetime | None = None
    ) -> models.AcquisitionHypothesisModel:
        model = self._require_hypothesis(hypothesis_id)
        self._require_draft(
            model, "Reasoning confidence is frozen once a hypothesis leaves DRAFT"
        )
        try:
            self._compute_and_store_confidence(model, now)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        self.session.refresh(model)
        return model

    def propose_hypothesis(
        self, hypothesis_id: str, now: datetime | None = None
    ) -> models.AcquisitionHypothesisModel:
        model = self._require_hypothesis(hypothesis_id)
        self._require_draft(model, "Only a DRAFT hypothesis can be proposed")
        try:
            # Freeze point: confidence is computed against the frozen evidence
            # set as part of entering PROPOSED (ratified ruling 1).
            self._compute_and_store_confidence(model, now)
            self._transition(model, HypothesisStatus.PROPOSED.value)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        self.session.refresh(model)
        return model

    def approve_hypothesis(
        self,
        hypothesis_id: str,
        reviewer_assessment: str | None = None,
        review_notes: str | None = None,
    ) -> models.AcquisitionHypothesisModel:
        model = self._require_hypothesis(hypothesis_id)
        if model.status != HypothesisStatus.PROPOSED.value:
            raise HypothesisGovernanceError(
                f"Only a PROPOSED hypothesis can be approved (status={model.status})"
            )
        # Invariant 1: no evidence means no approvable hypothesis.
        if not self.list_hypothesis_evidence_links(hypothesis_id):
            raise HypothesisGovernanceError(
                "A hypothesis without linked evidence cannot be approved"
            )
        if reviewer_assessment is not None and reviewer_assessment not in set(
            ReviewerAssessment
        ):
            raise HypothesisGovernanceError(
                f"Unknown reviewer assessment: {reviewer_assessment}"
            )
        try:
            self._transition(model, HypothesisStatus.APPROVED.value)
            model.reviewer_assessment = reviewer_assessment
            model.review_notes = review_notes
            model.reviewed_at = utc_now_iso()
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        self.session.refresh(model)
        return model

    def reject_hypothesis(
        self, hypothesis_id: str, review_notes: str | None = None
    ) -> models.AcquisitionHypothesisModel:
        model = self._require_hypothesis(hypothesis_id)
        if model.status != HypothesisStatus.PROPOSED.value:
            raise HypothesisGovernanceError(
                f"Only a PROPOSED hypothesis can be rejected (status={model.status})"
            )
        try:
            self._transition(model, HypothesisStatus.REJECTED.value)
            model.review_notes = review_notes
            model.reviewed_at = utc_now_iso()
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        self.session.refresh(model)
        return model

    def activate_hypothesis(self, hypothesis_id: str) -> models.AcquisitionHypothesisModel:
        model = self._require_hypothesis(hypothesis_id)
        if model.is_active:
            return model
        # Ratified activation preconditions — all four, enforced here.
        if model.status != HypothesisStatus.APPROVED.value:
            raise HypothesisGovernanceError(
                f"Only an APPROVED hypothesis can be activated (status={model.status})"
            )
        if model.refines_hypothesis_id is not None:
            parent = self.session.get(
                models.AcquisitionHypothesisModel, model.refines_hypothesis_id
            )
            if parent is None or parent.status != HypothesisStatus.APPROVED.value:
                raise HypothesisGovernanceError(
                    "A refinement cannot be activated while its parent hypothesis is not APPROVED"
                )
        active_evidence = self.session.scalar(
            select(models.HypothesisEvidenceLinkModel)
            .join(
                models.EvidenceEntryModel,
                models.HypothesisEvidenceLinkModel.evidence_entry_id
                == models.EvidenceEntryModel.id,
            )
            .where(
                models.HypothesisEvidenceLinkModel.hypothesis_id == hypothesis_id,
                models.EvidenceEntryModel.status == EvidenceStatus.ACTIVE.value,
            )
        )
        if active_evidence is None:
            raise HypothesisGovernanceError(
                "Activation requires at least one linked evidence entry in ACTIVE state"
            )
        if model.reasoning_confidence is None:
            raise HypothesisGovernanceError(
                "Activation requires a computed reasoning confidence"
            )
        try:
            current = self.session.scalar(
                select(models.AcquisitionHypothesisModel).where(
                    models.AcquisitionHypothesisModel.offer_id == model.offer_id,
                    models.AcquisitionHypothesisModel.prospect_id == model.prospect_id,
                    models.AcquisitionHypothesisModel.is_active == True,  # noqa: E712
                    models.AcquisitionHypothesisModel.id != model.id,
                )
            )
            if current is not None:
                current.is_active = False
                current.updated_at = utc_now_iso()
                self._record_hypothesis_audit(
                    current.id, "DEACTIVATED", {"replaced_by": model.id}
                )
                self.session.flush()
            model.is_active = True
            model.updated_at = utc_now_iso()
            self._record_hypothesis_audit(model.id, "ACTIVATED", {})
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        self.session.refresh(model)
        return model

    def supersede_hypothesis(
        self,
        hypothesis_id: str,
        *,
        statement: str | None = None,
        recipient_framing: str | None = None,
        source: str = HypothesisSource.HUMAN.value,
    ) -> models.AcquisitionHypothesisModel:
        model = self._require_hypothesis(hypothesis_id)
        if model.status == HypothesisStatus.DRAFT.value:
            raise HypothesisGovernanceError(
                "A DRAFT hypothesis is edited directly, not superseded"
            )
        if HypothesisStatus.SUPERSEDED.value not in ALLOWED_HYPOTHESIS_TRANSITIONS.get(
            model.status, set()
        ):
            raise HypothesisGovernanceError(
                f"A {model.status} hypothesis cannot be superseded"
            )
        if source not in set(HypothesisSource):
            raise HypothesisGovernanceError(f"Unknown hypothesis source: {source}")
        try:
            now = utc_now_iso()
            if model.is_active:
                model.is_active = False
                self._record_hypothesis_audit(
                    model.id, "DEACTIVATED", {"reason": "superseded"}
                )
            successor = models.AcquisitionHypothesisModel(
                id=prefixed_id("AH"),
                offer_id=model.offer_id,
                prospect_id=model.prospect_id,
                decision_maker_id=model.decision_maker_id,
                refines_hypothesis_id=model.refines_hypothesis_id,
                statement=statement if statement is not None else model.statement,
                recipient_framing=(
                    recipient_framing
                    if recipient_framing is not None
                    else model.recipient_framing
                ),
                source=source,
                status=HypothesisStatus.DRAFT.value,
                is_active=False,
                created_at=now,
                updated_at=now,
            )
            self.session.add(successor)
            # Flush the successor INSERT before the predecessor UPDATE
            # references it via superseded_by_id (self-referential FK gives
            # the unit of work no ordering edge). Still one transaction.
            self.session.flush()
            # The successor starts from the predecessor's evidence set; it is
            # freely editable while the successor remains DRAFT.
            for link in self.list_hypothesis_evidence_links(model.id):
                self.session.add(
                    models.HypothesisEvidenceLinkModel(
                        id=prefixed_id("HEL"),
                        hypothesis_id=successor.id,
                        evidence_entry_id=link.evidence_entry_id,
                        note=link.note,
                        created_at=now,
                    )
                )
            self._transition(
                model,
                HypothesisStatus.SUPERSEDED.value,
                extra_detail={"successor_id": successor.id},
            )
            model.superseded_by_id = successor.id
            self._record_hypothesis_audit(
                successor.id, "CREATED", {"superseded_from": model.id, "source": source}
            )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        self.session.refresh(successor)
        return successor

    def correct_hypothesis_metadata(
        self, hypothesis_id: str, field: str, value: str | None, reason: str
    ) -> models.AcquisitionHypothesisModel:
        model = self._require_hypothesis(hypothesis_id)
        if field not in CORRECTABLE_HYPOTHESIS_FIELDS:
            raise HypothesisGovernanceError(
                f"Field '{field}' is canonical or ungoverned and cannot be corrected in place;"
                " substantive changes require supersession"
            )
        before = getattr(model, field)
        try:
            setattr(model, field, value)
            model.updated_at = utc_now_iso()
            self._record_hypothesis_audit(
                model.id,
                "METADATA_CORRECTED",
                {"field": field, "before": before, "after": value, "reason": reason},
            )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return model

    def correct_evidence_link_note(
        self, hypothesis_id: str, evidence_entry_id: str, note: str | None, reason: str
    ) -> models.HypothesisEvidenceLinkModel:
        self._require_hypothesis(hypothesis_id)
        link = self.session.scalar(
            select(models.HypothesisEvidenceLinkModel).where(
                models.HypothesisEvidenceLinkModel.hypothesis_id == hypothesis_id,
                models.HypothesisEvidenceLinkModel.evidence_entry_id == evidence_entry_id,
            )
        )
        if link is None:
            raise HypothesisGovernanceError("Evidence link not found")
        before = link.note
        try:
            link.note = note
            self._record_hypothesis_audit(
                hypothesis_id,
                "METADATA_CORRECTED",
                {
                    "field": "evidence_link_note",
                    "evidence_entry_id": evidence_entry_id,
                    "before": before,
                    "after": note,
                    "reason": reason,
                },
            )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return link

    def update_evidence_status(
        self, evidence_entry_id: str, status: str
    ) -> models.EvidenceEntryModel:
        if status not in set(EvidenceStatus):
            raise HypothesisGovernanceError(f"Unknown evidence status: {status}")
        entry = self.session.get(models.EvidenceEntryModel, evidence_entry_id)
        if entry is None:
            raise HypothesisGovernanceError(
                f"Evidence entry not found: {evidence_entry_id}"
            )
        entry.status = status
        self.session.commit()
        return entry

    def _require_hypothesis(self, hypothesis_id: str) -> models.AcquisitionHypothesisModel:
        model = self.session.get(models.AcquisitionHypothesisModel, hypothesis_id)
        if model is None:
            raise HypothesisGovernanceError(f"Hypothesis not found: {hypothesis_id}")
        return model

    @staticmethod
    def _require_draft(model: models.AcquisitionHypothesisModel, message: str) -> None:
        if model.status != HypothesisStatus.DRAFT.value:
            raise HypothesisGovernanceError(f"{message} (status={model.status})")

    def _transition(
        self,
        model: models.AcquisitionHypothesisModel,
        target: str,
        extra_detail: dict | None = None,
    ) -> None:
        """Validate-then-mutate lifecycle transition. Never commits."""
        if target in DORMANT_HYPOTHESIS_STATUSES:
            raise HypothesisGovernanceError(
                f"Status {target} is dormant until MVP 1.4 outcome integration"
            )
        allowed = ALLOWED_HYPOTHESIS_TRANSITIONS.get(model.status, set())
        if target not in allowed:
            raise HypothesisGovernanceError(
                f"Transition {model.status} -> {target} is not permitted"
            )
        detail = {"from": model.status, "to": target}
        if extra_detail:
            detail.update(extra_detail)
        model.status = target
        model.updated_at = utc_now_iso()
        self._record_hypothesis_audit(model.id, "STATUS_CHANGED", detail)

    def _invalidate_confidence(self, model: models.AcquisitionHypothesisModel) -> None:
        """A changed evidence set invalidates any previously computed score."""
        model.reasoning_confidence = None
        model.reasoning_confidence_explanation = "[]"
        model.updated_at = utc_now_iso()

    def _compute_and_store_confidence(
        self, model: models.AcquisitionHypothesisModel, now: datetime | None = None
    ) -> int:
        links = self.list_hypothesis_evidence_links(model.id)
        entries = [
            self.session.get(models.EvidenceEntryModel, link.evidence_entry_id)
            for link in links
        ]
        prospect = self.session.get(models.ProspectModel, model.prospect_id)
        segment = self.session.scalar(
            select(models.SegmentRegistryModel).where(
                models.SegmentRegistryModel.code == prospect.segment
            )
        )
        decision_maker_text = None
        if model.decision_maker_id is not None:
            decision_maker = self.session.get(
                models.DecisionMakerModel, model.decision_maker_id
            )
            if decision_maker is not None:
                decision_maker_text = f"{decision_maker.name} {decision_maker.role}"
        score, lines = compute_reasoning_confidence(
            entries,
            offer_id=model.offer_id,
            prospect_pdm_code=segment.pdm_code if segment else None,
            decision_maker_text=decision_maker_text,
            now=now or datetime.now(timezone.utc),
        )
        model.reasoning_confidence = score
        model.reasoning_confidence_explanation = json.dumps(lines)
        model.updated_at = utc_now_iso()
        self._record_hypothesis_audit(model.id, "CONFIDENCE_COMPUTED", {"score": score})
        return score

    def _record_hypothesis_audit(
        self, hypothesis_id: str, event_type: str, detail: dict
    ) -> None:
        self.session.add(
            models.HypothesisAuditEventModel(
                id=prefixed_id("HAE"),
                hypothesis_id=hypothesis_id,
                event_type=event_type,
                detail=json.dumps(detail, sort_keys=True),
                created_at=utc_now_iso(),
            )
        )

    def _clear_offer_profile_rows(self, offer_id: str) -> None:
        for model_class in [
            models.OfferProfileModel,
            models.OfferBuyerProfileModel,
            models.OfferSignalProfileModel,
            models.OfferPdmModel,
        ]:
            rows = self.session.scalars(
                select(model_class).where(model_class.offer_id == offer_id)
            ).all()
            for row in rows:
                self.session.delete(row)

    @staticmethod
    def _alpha_signal_from_model(model: models.AlphaSignalModel) -> AlphaSignal:
        return AlphaSignal(
            id=model.id,
            code=model.code,
            name=model.name,
            description=model.description,
            required_signals=json.loads(model.required_signals or "[]"),
            bonus_score=model.bonus_score,
            validation_status=model.validation_status,
            created_at=model.created_at,
        )

    @staticmethod
    def _prospect_alpha_signal_from_model(
        model: models.ProspectAlphaSignalModel,
    ) -> ProspectAlphaSignal:
        return ProspectAlphaSignal(
            id=model.id,
            prospect_id=model.prospect_id,
            alpha_signal_id=model.alpha_signal_id,
            alpha_signal_code=model.alpha_signal.code,
            alpha_signal_name=model.alpha_signal.name,
            bonus_score=model.alpha_signal.bonus_score,
            notes=model.notes,
            created_at=model.created_at,
        )

    @staticmethod
    def _score_from_model(model: models.ProspectScoreModel) -> ProspectScoreRead:
        explanations = [
            ScoreExplanationRead.model_validate(explanation)
            for explanation in model.explanations
        ]
        alpha_matches = [
            explanation.source_code
            for explanation in explanations
            if explanation.source_type == "ALPHA_SIGNAL"
        ]
        return ProspectScoreRead(
            id=model.id,
            prospect_id=model.prospect_id,
            tier1_total=model.tier1_total,
            tier2_total=model.tier2_total,
            tier3_total=model.tier3_total,
            base_score=model.base_score,
            alpha_matches=alpha_matches,
            alpha_bonus=model.alpha_bonus,
            final_score=model.final_score,
            decision=model.decision,
            explanation=explanations,
            calculated_at=model.calculated_at,
        )

    @staticmethod
    def _offer_profile_from_model(model: models.OfferProfileModel) -> OfferProfile:
        return OfferProfile(
            id=model.id,
            offer_id=model.offer_id,
            offer_category=model.offer_category,
            commercial_hypothesis=model.commercial_hypothesis,
            predicted_value_range=model.predicted_value_range,
            target_segments=json.loads(model.target_segments or "[]"),
            created_at=model.created_at,
        )

    @staticmethod
    def _offer_pdm_from_model(model: models.OfferPdmModel) -> OfferPdm:
        return OfferPdm(
            id=model.id,
            offer_id=model.offer_id,
            code=model.code,
            name=model.name,
            summary=model.summary,
            target_segments=json.loads(model.target_segments or "[]"),
            created_at=model.created_at,
        )

    @staticmethod
    def _offer_proposal_from_model(
        model: models.OfferEvaluationProposalModel,
    ) -> OfferEvaluationProposal:
        return OfferEvaluationProposal(
            id=model.id,
            offer_id=model.offer_id,
            provider=model.provider,
            model=model.model,
            mode=model.mode,
            raw_domain=model.raw_domain,
            normalized_domain=model.normalized_domain,
            primary_category=model.primary_category,
            confidence_score=model.confidence_score,
            confidence_label=model.confidence_label,
            reasoning=json.loads(model.reasoning or "[]"),
            alternative_categories=json.loads(model.alternative_categories or "[]"),
            proposed_profile_json=json.loads(model.proposed_profile_json),
            status=model.status,
            created_at=model.created_at,
            reviewed_at=model.reviewed_at,
            review_notes=model.review_notes,
        )

    @staticmethod
    def _offer_fit_from_model(model: models.OfferProspectFitModel) -> OfferProspectFit:
        return OfferProspectFit(
            id=model.id,
            offer_id=model.offer_id,
            prospect_id=model.prospect_id,
            segment_fit_score=model.segment_fit_score,
            buyer_profile_fit_score=model.buyer_profile_fit_score,
            signal_fit_score=model.signal_fit_score,
            total_fit_score=model.total_fit_score,
            decision=model.decision,
            explanation=json.loads(model.explanation or "[]"),
            created_at=model.created_at,
        )
