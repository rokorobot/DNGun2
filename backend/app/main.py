from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from . import models as _models  # noqa: F401 - registers SQLAlchemy models.
from .database import create_session_factory
from .learning import (
    calculate_alpha_signal_performance,
    calculate_learning_summary,
    calculate_signal_performance,
    render_learning_markdown,
)
from .offer_intelligence import generate_offer_hypothesis
from .offer_fit import calculate_offer_prospect_fit
from .offer_llm import DEFAULT_MODEL, generate_llm_offer_evaluation
from .repository import Repository, RepositoryConflictError
from .reporting import (
    build_campaign_intelligence_report,
    render_campaign_intelligence_markdown,
)
from .rules import RuleRegistry, RuleRegistryError
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
    LearningSummaryRead,
    Offer,
    OfferCreate,
    OfferEvaluationMode,
    OfferEvaluationProposal,
    OfferEvaluationRequest,
    OfferIntelligenceProfile,
    OfferProposalReview,
    OfferProspectFit,
    Prospect,
    ProspectAlphaSignal,
    ProspectAlphaSignalCreate,
    ProspectCreate,
    ProspectScore,
    ProspectScoreRead,
    Signal,
    SignalCreate,
    AlphaSignalPerformanceRead,
    SignalPerformanceRead,
    SegmentRegistry,
    SegmentRegistryCreate,
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

    @app.get("/rules")
    def get_rules() -> dict:
        return load_rules().all_rules()

    @app.get("/rules/score-bands")
    def get_score_bands() -> list[dict]:
        return load_rules().score_bands()

    @app.get("/rules/alpha-signals")
    def get_alpha_signal_rules() -> list[dict]:
        return load_rules().alpha_signals()

    @app.get("/rules/signal-taxonomy")
    def get_signal_taxonomy() -> list[dict]:
        return load_rules().signal_taxonomy()

    @app.get("/rules/disqualifiers")
    def get_disqualifiers() -> list[dict]:
        return load_rules().disqualifiers()

    @app.post("/segments", response_model=SegmentRegistry, status_code=201)
    def create_segment(
        data: SegmentRegistryCreate,
        repository: Repository = Depends(get_repository),
    ) -> SegmentRegistry:
        try:
            return repository.create_segment_registry_entry(data)
        except RepositoryConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/segments", response_model=list[SegmentRegistry])
    def list_segments(
        repository: Repository = Depends(get_repository),
    ) -> list[SegmentRegistry]:
        return repository.list_segments()

    @app.post("/prospects", response_model=Prospect, status_code=201)
    def create_prospect(
        data: ProspectCreate,
        repository: Repository = Depends(get_repository),
    ) -> Prospect:
        try:
            return repository.create_prospect(data)
        except RepositoryConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

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

    @app.get(
        "/campaign-batches/{campaign_batch_id}/prospects",
        response_model=list[CampaignBatchProspect],
    )
    def list_campaign_batch_prospects(
        campaign_batch_id: str,
        repository: Repository = Depends(get_repository),
    ) -> list[CampaignBatchProspect]:
        require_campaign_batch(repository, campaign_batch_id)
        return repository.list_campaign_batch_prospects(campaign_batch_id)

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

    @app.put("/campaign-outcomes/{campaign_outcome_id}", response_model=CampaignOutcome)
    def update_campaign_outcome(
        campaign_outcome_id: str,
        data: CampaignOutcomeCreate,
        repository: Repository = Depends(get_repository),
    ) -> CampaignOutcome:
        if repository.get_campaign_outcome(campaign_outcome_id) is None:
            raise HTTPException(status_code=404, detail="Campaign outcome not found")
        require_campaign_batch(repository, data.campaign_batch_id)
        require_prospect(repository, data.prospect_id)
        if not repository.campaign_batch_contains_prospect(
            data.campaign_batch_id, data.prospect_id
        ):
            raise HTTPException(
                status_code=400,
                detail="Prospect must belong to campaign batch before recording outcome",
            )
        outcome = repository.update_campaign_outcome(campaign_outcome_id, data)
        assert outcome is not None
        return outcome

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
        pdm_code: str | None = Query(default=None),
        offer_id: str | None = Query(default=None),
        repository: Repository = Depends(get_repository),
    ) -> list[EvidenceEntry]:
        return repository.list_evidence_entries(pdm_code=pdm_code, offer_id=offer_id)

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
        pdm_code: str | None = Query(default=None),
        offer_id: str | None = Query(default=None),
        repository: Repository = Depends(get_repository),
    ) -> list[ConfidenceUpdate]:
        return repository.list_confidence_updates(pdm_code=pdm_code, offer_id=offer_id)

    @app.get("/reports/campaign-intelligence", response_model=CampaignIntelligenceReport)
    def get_campaign_intelligence_report(
        pdm_code: str | None = Query(default=None),
        offer_id: str | None = Query(default=None),
        session: Session = Depends(get_session),
    ) -> CampaignIntelligenceReport:
        return build_campaign_intelligence_report(session, pdm_code=pdm_code, offer_id=offer_id)

    @app.get("/reports/campaign-intelligence.md", response_class=PlainTextResponse)
    def export_campaign_intelligence_report(
        pdm_code: str | None = Query(default=None),
        offer_id: str | None = Query(default=None),
        session: Session = Depends(get_session),
    ) -> str:
        report = build_campaign_intelligence_report(session, pdm_code=pdm_code, offer_id=offer_id)
        return render_campaign_intelligence_markdown(report)

    @app.get("/learning/signals", response_model=list[SignalPerformanceRead])
    def get_signal_learning(
        pdm_code: str | None = Query(default=None),
        offer_id: str | None = Query(default=None),
        session: Session = Depends(get_session),
    ) -> list[SignalPerformanceRead]:
        return calculate_signal_performance(session, pdm_code=pdm_code, offer_id=offer_id)

    @app.get("/learning/alpha-signals", response_model=list[AlphaSignalPerformanceRead])
    def get_alpha_signal_learning(
        pdm_code: str | None = Query(default=None),
        offer_id: str | None = Query(default=None),
        session: Session = Depends(get_session),
    ) -> list[AlphaSignalPerformanceRead]:
        return calculate_alpha_signal_performance(session, pdm_code=pdm_code, offer_id=offer_id)

    @app.get("/learning/summary", response_model=LearningSummaryRead)
    def get_learning_summary(
        pdm_code: str | None = Query(default=None),
        offer_id: str | None = Query(default=None),
        session: Session = Depends(get_session),
    ) -> LearningSummaryRead:
        return calculate_learning_summary(session, pdm_code=pdm_code, offer_id=offer_id)

    @app.get("/learning/report.md", response_class=PlainTextResponse)
    def export_learning_report(
        pdm_code: str | None = Query(default=None),
        offer_id: str | None = Query(default=None),
        session: Session = Depends(get_session),
    ) -> str:
        return render_learning_markdown(calculate_learning_summary(session, pdm_code=pdm_code, offer_id=offer_id))

    @app.post("/offers", response_model=Offer, status_code=201)
    def create_offer(
        data: OfferCreate,
        repository: Repository = Depends(get_repository),
    ) -> Offer:
        return repository.create_offer(data)

    @app.get("/offers", response_model=list[Offer])
    def list_offers(repository: Repository = Depends(get_repository)) -> list[Offer]:
        return repository.list_offers()

    @app.get("/offers/{offer_id}", response_model=Offer)
    def get_offer(
        offer_id: str,
        repository: Repository = Depends(get_repository),
    ) -> Offer:
        offer = repository.get_offer(offer_id)
        if offer is None:
            raise HTTPException(status_code=404, detail="Offer not found")
        return offer

    @app.post(
        "/offers/{offer_id}/evaluate",
        response_model=OfferEvaluationProposal,
        status_code=201,
    )
    def evaluate_offer(
        offer_id: str,
        data: OfferEvaluationRequest,
        repository: Repository = Depends(get_repository),
    ) -> OfferEvaluationProposal:
        offer = require_offer(repository, offer_id)
        provider = "deterministic"
        model_name = None
        proposal = _deterministic_offer_proposal(offer.name)
        if data.mode == OfferEvaluationMode.LLM_ASSISTED:
            llm_proposal = generate_llm_offer_evaluation(offer.name)
            if llm_proposal:
                proposal = _normalize_llm_offer_proposal(llm_proposal)
                provider = "openai"
                model_name = DEFAULT_MODEL
        return repository.create_offer_evaluation_proposal(
            offer_id=offer.id,
            provider=provider,
            model_name=model_name,
            mode=data.mode.value,
            raw_domain=offer.name,
            normalized_domain=_normalize_domain(offer.name),
            proposal=proposal,
        )

    @app.get(
        "/offers/{offer_id}/proposals",
        response_model=list[OfferEvaluationProposal],
    )
    def list_offer_proposals(
        offer_id: str,
        repository: Repository = Depends(get_repository),
    ) -> list[OfferEvaluationProposal]:
        require_offer(repository, offer_id)
        return repository.list_offer_proposals(offer_id)

    @app.get(
        "/offers/{offer_id}/proposals/{proposal_id}",
        response_model=OfferEvaluationProposal,
    )
    def get_offer_proposal(
        offer_id: str,
        proposal_id: str,
        repository: Repository = Depends(get_repository),
    ) -> OfferEvaluationProposal:
        require_offer(repository, offer_id)
        proposal = repository.get_offer_proposal(offer_id, proposal_id)
        if proposal is None:
            raise HTTPException(status_code=404, detail="Offer proposal not found")
        return proposal

    @app.post(
        "/offers/{offer_id}/proposals/{proposal_id}/approve",
        response_model=OfferIntelligenceProfile,
    )
    def approve_offer_proposal(
        offer_id: str,
        proposal_id: str,
        data: OfferProposalReview | None = None,
        repository: Repository = Depends(get_repository),
    ) -> OfferIntelligenceProfile:
        require_offer(repository, offer_id)
        profile = repository.approve_offer_proposal(
            offer_id, proposal_id, data.review_notes if data else None
        )
        if profile is None:
            raise HTTPException(status_code=409, detail="Offer proposal cannot be approved")
        return profile

    @app.post(
        "/offers/{offer_id}/proposals/{proposal_id}/reject",
        response_model=OfferEvaluationProposal,
    )
    def reject_offer_proposal(
        offer_id: str,
        proposal_id: str,
        data: OfferProposalReview | None = None,
        repository: Repository = Depends(get_repository),
    ) -> OfferEvaluationProposal:
        require_offer(repository, offer_id)
        proposal = repository.reject_offer_proposal(
            offer_id, proposal_id, data.review_notes if data else None
        )
        if proposal is None:
            raise HTTPException(status_code=404, detail="Offer proposal not found")
        return proposal

    @app.get(
        "/offers/{offer_id}/intelligence-profile",
        response_model=OfferIntelligenceProfile,
    )
    def get_offer_intelligence_profile(
        offer_id: str,
        repository: Repository = Depends(get_repository),
    ) -> OfferIntelligenceProfile:
        require_offer(repository, offer_id)
        profile = repository.get_offer_intelligence_profile(offer_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Offer intelligence profile not found")
        return profile

    @app.post(
        "/offers/{offer_id}/fit/prospects",
        response_model=list[OfferProspectFit],
    )
    def calculate_offer_prospect_fits(
        offer_id: str,
        repository: Repository = Depends(get_repository),
    ) -> list[OfferProspectFit]:
        require_offer(repository, offer_id)
        profile = repository.get_offer_intelligence_profile(offer_id)
        if profile is None:
            raise HTTPException(status_code=409, detail="Approved offer profile required")
        rules = load_rules()
        fits = [
            calculate_offer_prospect_fit(
                offer_profile=profile,
                prospect=prospect,
                signals=repository.list_signals(prospect.id),
                rules=rules,
            )
            for prospect in repository.list_prospects()
        ]
        return repository.replace_offer_prospect_fits(offer_id, fits)

    @app.get(
        "/offers/{offer_id}/fit/prospects",
        response_model=list[OfferProspectFit],
    )
    def list_offer_prospect_fits(
        offer_id: str,
        repository: Repository = Depends(get_repository),
    ) -> list[OfferProspectFit]:
        require_offer(repository, offer_id)
        return repository.list_offer_prospect_fits(offer_id)

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


def require_offer(repository: Repository, offer_id: str) -> Offer:
    offer = repository.get_offer(offer_id)
    if offer is None:
        raise HTTPException(status_code=404, detail="Offer not found")
    return offer


def _deterministic_offer_proposal(domain_name: str) -> dict:
    profile = generate_offer_hypothesis(domain_name)
    category = profile["offer_category"]
    return {
        "primary_category": category,
        "confidence_score": 0.72,
        "confidence_label": "MEDIUM",
        "commercial_hypothesis": profile["commercial_hypothesis"],
        "predicted_value_range": profile["predicted_value_range"],
        "target_segments": profile["target_segments"],
        "buyer_profiles": profile["buyer_profiles"],
        "signal_profiles": profile["signal_profiles"],
        "pdm": profile["pdm"],
        "reasoning": [
            f"Domain tokens map to {category}.",
            "Evaluation is deterministic and should be reviewed by a human operator.",
            "No market data, prospect data, scraping, or company-specific claims were used.",
        ],
        "alternative_categories": _alternative_categories(category),
    }


def _normalize_llm_offer_proposal(proposal: dict) -> dict:
    return {
        "primary_category": str(proposal["primary_category"]),
        "confidence_score": float(proposal["confidence_score"]),
        "confidence_label": str(proposal["confidence_label"]),
        "commercial_hypothesis": str(proposal["commercial_hypothesis"]),
        "predicted_value_range": str(proposal["predicted_value_range"]),
        "target_segments": list(proposal.get("target_segments", [])),
        "buyer_profiles": list(proposal.get("buyer_profiles", [])),
        "signal_profiles": list(proposal.get("signal_profiles", [])),
        "pdm": dict(proposal["pdm"]),
        "reasoning": list(proposal.get("reasoning", [])),
        "alternative_categories": list(proposal.get("alternative_categories", [])),
    }


def _normalize_domain(domain_name: str) -> str:
    return domain_name.strip().replace("https://", "").replace("http://", "").split("/")[0]


def _alternative_categories(primary_category: str) -> list[str]:
    categories = [
        "Robotics Marketplace",
        "AI Workflow Product",
        "Digital Asset Portfolio",
        "Knowledge Productivity Tool",
        "Equipment Leasing Platform",
        "Domain-Led Digital Offer",
    ]
    return [category for category in categories if category != primary_category][:3]


def load_rules() -> RuleRegistry:
    try:
        return RuleRegistry()
    except RuleRegistryError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


app = create_app()
