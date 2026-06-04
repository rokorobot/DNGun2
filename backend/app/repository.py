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
    Prospect,
    ProspectAlphaSignal,
    ProspectAlphaSignalCreate,
    ProspectCreate,
    ProspectScore,
    ProspectScoreRead,
    ScoreExplanationRead,
    Signal,
    SignalCreate,
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

    def list_evidence_entries(self) -> list[EvidenceEntry]:
        rows = self.session.scalars(
            select(models.EvidenceEntryModel).order_by(
                models.EvidenceEntryModel.created_at.desc()
            )
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

    def list_confidence_updates(self) -> list[ConfidenceUpdate]:
        rows = self.session.scalars(
            select(models.ConfidenceUpdateModel).order_by(
                models.ConfidenceUpdateModel.created_at.desc()
            )
        ).all()
        return [ConfidenceUpdate.model_validate(row) for row in rows]

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
