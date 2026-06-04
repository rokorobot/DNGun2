from __future__ import annotations

import json
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .schemas import (
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
    utc_now_iso,
)


def prefixed_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10].upper()}"


class RepositoryConflictError(Exception):
    pass


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
