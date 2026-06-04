from __future__ import annotations

from sqlalchemy.orm import Session

from .repository import Repository
from .rules import RuleRegistry
from .schemas import (
    AlphaSignalCreate,
    CampaignBatchCreate,
    CampaignOutcomeCreate,
    ConfidenceUpdateCreate,
    EvidenceEntryCreate,
    ProspectAlphaSignalCreate,
    ProspectCreate,
    Segment,
    SignalCreate,
)
from .scoring_engine import ScoringEngine


def seed_mvp0(session: Session) -> dict[str, int | str]:
    repository = Repository(session)
    rules = RuleRegistry()

    alpha_signals = {}
    for rule in rules.alpha_signals():
        alpha_signal = repository.create_alpha_signal(AlphaSignalCreate(**rule))
        alpha_signals[alpha_signal.code] = alpha_signal

    campaign_batch = repository.create_campaign_batch(
        CampaignBatchCreate(name="MVP 0 Seed Campaign", segment=Segment.AI_AUTOMATION)
    )

    prospects = []
    outcomes_created = 0
    for index in range(25):
        segment = [Segment.AI_AUTOMATION, Segment.REVOPS, Segment.SEO, Segment.WEBFLOW][
            index % 4
        ]
        prospect = repository.create_prospect(
            ProspectCreate(
                company_name=f"Seed Agency {index + 1:02d}",
                website=f"https://seed-agency-{index + 1:02d}.example.com",
                segment=segment,
                founder_name=f"Founder {index + 1:02d}",
                team_size=3 + (index % 8),
                contact_path="Founder LinkedIn",
            )
        )
        prospects.append(prospect)
        repository.add_prospect_to_campaign_batch(campaign_batch.id, prospect.id)
        _create_seed_signals(repository, prospect.id, index)

        if index < 10:
            repository.assign_alpha_signal(
                prospect.id,
                alpha_signals["AS-001"].id,
                ProspectAlphaSignalCreate(notes="Seed match"),
            )
        elif index < 18:
            repository.assign_alpha_signal(
                prospect.id,
                alpha_signals["AS-004"].id,
                ProspectAlphaSignalCreate(notes="Seed match"),
            )
        elif index < 22:
            repository.assign_alpha_signal(
                prospect.id,
                alpha_signals["AS-010"].id,
                ProspectAlphaSignalCreate(notes="Seed match"),
            )

        score = ScoringEngine().calculate(
            prospect_id=prospect.id,
            signals=repository.list_signals(prospect.id),
            alpha_signals=repository.list_alpha_signals_for_prospect(prospect.id),
        )
        repository.save_score(score)

        outcome = _outcome_for(index)
        repository.create_campaign_outcome(
            CampaignOutcomeCreate(
                campaign_batch_id=campaign_batch.id,
                prospect_id=prospect.id,
                **outcome,
            )
        )
        outcomes_created += 1

    evidence = repository.create_evidence_entry(
        EvidenceEntryCreate(
            evidence_type="Seed Campaign Outcome",
            evidence="Seed campaign created 25 contacted prospects with sample outcomes.",
            impact=1,
            source=campaign_batch.id,
        )
    )
    repository.create_evidence_entry(
        EvidenceEntryCreate(
            evidence_type="Seed Campaign Learning",
            evidence="Seed data includes score bands and Alpha Signal performance samples.",
            impact=1,
            source=campaign_batch.id,
        )
    )
    repository.create_confidence_update(
        ConfidenceUpdateCreate(
            evidence_entry_id=evidence.id,
            confidence_before=40,
            evidence_impact=3,
            confidence_after=43,
            reason="Seed campaign provides initial reportable learning loop.",
        )
    )

    return {
        "prospects": len(prospects),
        "alpha_signals": len(alpha_signals),
        "campaign_batch_id": campaign_batch.id,
        "campaign_outcomes": outcomes_created,
    }


def _create_seed_signals(repository: Repository, prospect_id: str, index: int) -> None:
    if index < 10:
        plan = [
            ("Founder discusses growth", 1, 5),
            ("New service launch", 1, 5),
            ("Hiring SDR", 1, 5),
            ("Recent case study", 1, 5),
            ("Strong case studies", 2, 5),
            ("Founder contact path visible", 3, 5),
        ]
    elif index < 18:
        plan = [
            ("Founder mentions referrals", 1, 5),
            ("Recent case study", 1, 5),
            ("Strong case studies", 2, 5),
            ("No visible sales process", 2, 5),
            ("Founder contact path visible", 3, 5),
        ]
    else:
        plan = [
            ("Website quality", 2, 4),
            ("Founder contact path visible", 3, 4),
            ("Company size fit", 3, 4),
        ]

    for signal_type, tier, score in plan:
        repository.create_signal(
            prospect_id,
            SignalCreate(
                signal_type=signal_type,
                tier=tier,
                score=score,
                notes="Seed signal",
            ),
        )


def _outcome_for(index: int) -> dict[str, bool | str]:
    replied = index < 8
    call_booked = index < 4
    proposal_requested = index < 2
    paid_pilot = index == 0
    return {
        "contacted": True,
        "replied": replied,
        "call_booked": call_booked,
        "proposal_requested": proposal_requested,
        "paid_pilot": paid_pilot,
        "lost_deal": index in {8, 9},
        "outcome_notes": "Seed campaign outcome",
    }
