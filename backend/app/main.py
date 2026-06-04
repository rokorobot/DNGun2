from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from . import models as _models  # noqa: F401 - registers SQLAlchemy models.
from .database import create_session_factory
from .repository import Repository, RepositoryConflictError
from .reporting import (
    build_campaign_intelligence_report,
    render_campaign_intelligence_markdown,
)
from .schemas import (
    AlphaSignal,
    AlphaSignalCreate,
    CampaignBatch,
    CampaignBatchCreate,
    CampaignBatchProspect,
    CampaignOutcome,
    CampaignOutcomeCreate,
    CampaignIntelligenceReport,
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
    Signal,
    SignalCreate,
)
from .scoring_engine import ScoringEngine


def create_app(db_path: Path | None = None) -> FastAPI:
    app = FastAPI(title="DNGun Prospect Intelligence API", version="0.1.0")
    session_factory = create_session_factory(db_path)

    def get_session() -> Session:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def get_repository(session: Session = Depends(get_session)) -> Repository:
        return Repository(session)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/prospects", response_model=Prospect, status_code=201)
    def create_prospect(
        data: ProspectCreate,
        repository: Repository = Depends(get_repository),
    ) -> Prospect:
        return repository.create_prospect(data)

    @app.get("/prospects", response_model=list[Prospect])
    def list_prospects(repository: Repository = Depends(get_repository)) -> list[Prospect]:
        return repository.list_prospects()

    @app.get("/prospects/{prospect_id}", response_model=Prospect)
    def get_prospect(
        prospect_id: str,
        repository: Repository = Depends(get_repository),
    ) -> Prospect:
        prospect = repository.get_prospect(prospect_id)
        if prospect is None:
            raise HTTPException(status_code=404, detail="Prospect not found")
        return prospect

    @app.post("/prospects/{prospect_id}/signals", response_model=Signal, status_code=201)
    def create_signal(
        prospect_id: str,
        data: SignalCreate,
        repository: Repository = Depends(get_repository),
    ) -> Signal:
        require_prospect(repository, prospect_id)
        return repository.create_signal(prospect_id, data)

    @app.get("/prospects/{prospect_id}/signals", response_model=list[Signal])
    def list_signals(
        prospect_id: str,
        repository: Repository = Depends(get_repository),
    ) -> list[Signal]:
        require_prospect(repository, prospect_id)
        return repository.list_signals(prospect_id)

    @app.post("/alpha-signals", response_model=AlphaSignal, status_code=201)
    def create_alpha_signal(
        data: AlphaSignalCreate,
        repository: Repository = Depends(get_repository),
    ) -> AlphaSignal:
        try:
            return repository.create_alpha_signal(data)
        except RepositoryConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/alpha-signals", response_model=list[AlphaSignal])
    def list_alpha_signals(
        repository: Repository = Depends(get_repository),
    ) -> list[AlphaSignal]:
        return repository.list_alpha_signals()

    @app.post(
        "/prospects/{prospect_id}/alpha-signals/{alpha_signal_id}",
        response_model=ProspectAlphaSignal,
        status_code=201,
    )
    def assign_alpha_signal(
        prospect_id: str,
        alpha_signal_id: str,
        data: ProspectAlphaSignalCreate | None = None,
        repository: Repository = Depends(get_repository),
    ) -> ProspectAlphaSignal:
        require_prospect(repository, prospect_id)
        require_alpha_signal(repository, alpha_signal_id)
        try:
            return repository.assign_alpha_signal(
                prospect_id,
                alpha_signal_id,
                data or ProspectAlphaSignalCreate(),
            )
        except RepositoryConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get(
        "/prospects/{prospect_id}/alpha-signals",
        response_model=list[ProspectAlphaSignal],
    )
    def list_prospect_alpha_signals(
        prospect_id: str,
        repository: Repository = Depends(get_repository),
    ) -> list[ProspectAlphaSignal]:
        require_prospect(repository, prospect_id)
        return repository.list_prospect_alpha_signals(prospect_id)

    @app.post("/prospects/{prospect_id}/score", response_model=ProspectScore)
    def calculate_score(
        prospect_id: str,
        persist: bool = Query(default=True),
        repository: Repository = Depends(get_repository),
    ) -> ProspectScore:
        require_prospect(repository, prospect_id)
        score = ScoringEngine().calculate(
            prospect_id=prospect_id,
            signals=repository.list_signals(prospect_id),
            alpha_signals=repository.list_alpha_signals_for_prospect(prospect_id),
        )
        return repository.save_score(score) if persist else score

    @app.get("/prospects/{prospect_id}/scores", response_model=list[ProspectScoreRead])
    def list_scores(
        prospect_id: str,
        repository: Repository = Depends(get_repository),
    ) -> list[ProspectScoreRead]:
        require_prospect(repository, prospect_id)
        return repository.list_scores(prospect_id)

    @app.get("/scores/{score_id}", response_model=ProspectScoreRead)
    def get_score(
        score_id: str,
        repository: Repository = Depends(get_repository),
    ) -> ProspectScoreRead:
        score = repository.get_score(score_id)
        if score is None:
            raise HTTPException(status_code=404, detail="Score not found")
        return score

    @app.post("/campaign-batches", response_model=CampaignBatch, status_code=201)
    def create_campaign_batch(
        data: CampaignBatchCreate,
        repository: Repository = Depends(get_repository),
    ) -> CampaignBatch:
        return repository.create_campaign_batch(data)

    @app.get("/campaign-batches", response_model=list[CampaignBatch])
    def list_campaign_batches(
        repository: Repository = Depends(get_repository),
    ) -> list[CampaignBatch]:
        return repository.list_campaign_batches()

    @app.post(
        "/campaign-batches/{campaign_batch_id}/prospects/{prospect_id}",
        response_model=CampaignBatchProspect,
        status_code=201,
    )
    def add_prospect_to_campaign_batch(
        campaign_batch_id: str,
        prospect_id: str,
        repository: Repository = Depends(get_repository),
    ) -> CampaignBatchProspect:
        require_campaign_batch(repository, campaign_batch_id)
        require_prospect(repository, prospect_id)
        try:
            return repository.add_prospect_to_campaign_batch(campaign_batch_id, prospect_id)
        except RepositoryConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/campaign-outcomes", response_model=CampaignOutcome, status_code=201)
    def create_campaign_outcome(
        data: CampaignOutcomeCreate,
        repository: Repository = Depends(get_repository),
    ) -> CampaignOutcome:
        require_campaign_batch(repository, data.campaign_batch_id)
        require_prospect(repository, data.prospect_id)
        if not repository.campaign_batch_contains_prospect(
            data.campaign_batch_id, data.prospect_id
        ):
            raise HTTPException(
                status_code=400,
                detail="Prospect must belong to campaign batch before recording outcome",
            )
        return repository.create_campaign_outcome(data)

    @app.get("/campaign-outcomes", response_model=list[CampaignOutcome])
    def list_campaign_outcomes(
        campaign_batch_id: str | None = None,
        repository: Repository = Depends(get_repository),
    ) -> list[CampaignOutcome]:
        if campaign_batch_id:
            require_campaign_batch(repository, campaign_batch_id)
        return repository.list_campaign_outcomes(campaign_batch_id)

    @app.post("/evidence-entries", response_model=EvidenceEntry, status_code=201)
    def create_evidence_entry(
        data: EvidenceEntryCreate,
        repository: Repository = Depends(get_repository),
    ) -> EvidenceEntry:
        return repository.create_evidence_entry(data)

    @app.get("/evidence-entries", response_model=list[EvidenceEntry])
    def list_evidence_entries(
        repository: Repository = Depends(get_repository),
    ) -> list[EvidenceEntry]:
        return repository.list_evidence_entries()

    @app.post("/confidence-updates", response_model=ConfidenceUpdate, status_code=201)
    def create_confidence_update(
        data: ConfidenceUpdateCreate,
        repository: Repository = Depends(get_repository),
    ) -> ConfidenceUpdate:
        if data.evidence_entry_id:
            require_evidence_entry(repository, data.evidence_entry_id)
        return repository.create_confidence_update(data)

    @app.get("/confidence-updates", response_model=list[ConfidenceUpdate])
    def list_confidence_updates(
        repository: Repository = Depends(get_repository),
    ) -> list[ConfidenceUpdate]:
        return repository.list_confidence_updates()

    @app.get("/reports/campaign-intelligence", response_model=CampaignIntelligenceReport)
    def get_campaign_intelligence_report(
        session: Session = Depends(get_session),
    ) -> CampaignIntelligenceReport:
        return build_campaign_intelligence_report(session)

    @app.get("/reports/campaign-intelligence.md", response_class=PlainTextResponse)
    def export_campaign_intelligence_report(
        session: Session = Depends(get_session),
    ) -> str:
        report = build_campaign_intelligence_report(session)
        return render_campaign_intelligence_markdown(report)

    return app


def require_prospect(repository: Repository, prospect_id: str) -> Prospect:
    prospect = repository.get_prospect(prospect_id)
    if prospect is None:
        raise HTTPException(status_code=404, detail="Prospect not found")
    return prospect


def require_alpha_signal(repository: Repository, alpha_signal_id: str) -> AlphaSignal:
    alpha_signal = repository.get_alpha_signal(alpha_signal_id)
    if alpha_signal is None:
        raise HTTPException(status_code=404, detail="Alpha Signal not found")
    return alpha_signal


def require_campaign_batch(repository: Repository, campaign_batch_id: str) -> CampaignBatch:
    campaign_batch = repository.get_campaign_batch(campaign_batch_id)
    if campaign_batch is None:
        raise HTTPException(status_code=404, detail="Campaign batch not found")
    return campaign_batch


def require_evidence_entry(repository: Repository, evidence_entry_id: str) -> EvidenceEntry:
    evidence_entry = repository.get_evidence_entry(evidence_entry_id)
    if evidence_entry is None:
        raise HTTPException(status_code=404, detail="Evidence entry not found")
    return evidence_entry


app = create_app()
