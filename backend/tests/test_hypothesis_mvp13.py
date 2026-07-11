from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, select, text, update

from backend.app import models
from backend.app.database import create_session_factory
from backend.app.reasoning_confidence import compute_reasoning_confidence
from backend.app.repository import (
    HypothesisGovernanceError,
    Repository,
    RepositoryConflictError,
    prefixed_id,
)
from backend.app.schemas import ProspectCreate, utc_now_iso
from backend.scripts.migrate_db import migrate

from sqlalchemy.exc import IntegrityError


def _make_offer(session) -> models.OfferModel:
    offer = models.OfferModel(
        id=prefixed_id("O"),
        name="RobotStore.app",
        offer_type="DOMAIN_NAME",
        status="DRAFT",
        created_at=utc_now_iso(),
    )
    session.add(offer)
    session.commit()
    return offer


def _make_prospect(session) -> str:
    prospect = Repository(session).create_prospect(
        ProspectCreate(company_name="Robotics Marketplace Ltd", segment="AI_AUTOMATION")
    )
    return prospect.id


def _make_evidence(session) -> models.EvidenceEntryModel:
    entry = models.EvidenceEntryModel(
        id=prefixed_id("EV"),
        project="DNGun",
        evidence_type="Campaign Outcome",
        evidence="Prospect announced ecommerce expansion.",
        impact=1,
        created_at=utc_now_iso(),
    )
    session.add(entry)
    session.commit()
    return entry


def _make_hypothesis(
    session,
    offer_id: str,
    prospect_id: str,
    *,
    is_active: bool = False,
    status: str = "DRAFT",
) -> models.AcquisitionHypothesisModel:
    now = utc_now_iso()
    hypothesis = models.AcquisitionHypothesisModel(
        id=prefixed_id("AH"),
        offer_id=offer_id,
        prospect_id=prospect_id,
        statement="Expanding from integration services into ecommerce.",
        source="HUMAN",
        status=status,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )
    session.add(hypothesis)
    session.commit()
    return hypothesis


def test_hypothesis_tables_and_active_index_created(tmp_path):
    session_factory = create_session_factory(tmp_path / "schema.sqlite3")
    with session_factory() as session:
        names = set(
            session.execute(
                text("SELECT name FROM sqlite_master WHERE type IN ('table', 'index')")
            ).scalars()
        )
    assert "acquisition_hypotheses" in names
    assert "hypothesis_evidence_links" in names
    assert "hypothesis_audit_events" in names
    assert "uq_active_hypothesis" in names


def test_single_active_hypothesis_per_offer_prospect(tmp_path):
    session_factory = create_session_factory(tmp_path / "active.sqlite3")
    with session_factory() as session:
        offer = _make_offer(session)
        prospect_id = _make_prospect(session)
        _make_hypothesis(session, offer.id, prospect_id, is_active=True)

        # Competing inactive hypotheses for the same pair are allowed.
        _make_hypothesis(session, offer.id, prospect_id, is_active=False)
        _make_hypothesis(session, offer.id, prospect_id, is_active=False)

        # A second active hypothesis for the same pair violates the index.
        with pytest.raises(IntegrityError):
            _make_hypothesis(session, offer.id, prospect_id, is_active=True)
        session.rollback()

        # An active hypothesis for a different prospect is fine.
        other_prospect_id = _make_prospect(session)
        _make_hypothesis(session, offer.id, other_prospect_id, is_active=True)


def test_evidence_links_unique_and_delete_restricted(tmp_path):
    session_factory = create_session_factory(tmp_path / "links.sqlite3")
    with session_factory() as session:
        offer = _make_offer(session)
        prospect_id = _make_prospect(session)
        hypothesis = _make_hypothesis(session, offer.id, prospect_id)
        evidence = _make_evidence(session)

        link = models.HypothesisEvidenceLinkModel(
            id=prefixed_id("HEL"),
            hypothesis_id=hypothesis.id,
            evidence_entry_id=evidence.id,
            created_at=utc_now_iso(),
        )
        session.add(link)
        session.commit()

        # Duplicate link for the same pair is rejected.
        with pytest.raises(IntegrityError):
            session.add(
                models.HypothesisEvidenceLinkModel(
                    id=prefixed_id("HEL"),
                    hypothesis_id=hypothesis.id,
                    evidence_entry_id=evidence.id,
                    created_at=utc_now_iso(),
                )
            )
            session.commit()
        session.rollback()

        # Referenced evidence cannot be physically deleted (invariant 9).
        with pytest.raises(IntegrityError):
            session.execute(
                delete(models.EvidenceEntryModel).where(
                    models.EvidenceEntryModel.id == evidence.id
                )
            )
        session.rollback()

        # Deleting the hypothesis cascades its links and audit events.
        session.add(
            models.HypothesisAuditEventModel(
                id=prefixed_id("HAE"),
                hypothesis_id=hypothesis.id,
                event_type="STATUS_CHANGED",
                created_at=utc_now_iso(),
            )
        )
        session.commit()
        session.execute(
            delete(models.AcquisitionHypothesisModel).where(
                models.AcquisitionHypothesisModel.id == hypothesis.id
            )
        )
        session.commit()
        assert (
            session.scalars(select(models.HypothesisEvidenceLinkModel)).all() == []
        )
        assert session.scalars(select(models.HypothesisAuditEventModel)).all() == []

        # With no remaining references the evidence is deletable again.
        session.execute(
            delete(models.EvidenceEntryModel).where(
                models.EvidenceEntryModel.id == evidence.id
            )
        )
        session.commit()


def test_prospect_delete_cascades_hypotheses(tmp_path):
    session_factory = create_session_factory(tmp_path / "cascade.sqlite3")
    with session_factory() as session:
        offer = _make_offer(session)
        prospect_id = _make_prospect(session)
        _make_hypothesis(session, offer.id, prospect_id, is_active=True)

        session.execute(
            delete(models.ProspectModel).where(models.ProspectModel.id == prospect_id)
        )
        session.commit()
        assert (
            session.scalars(select(models.AcquisitionHypothesisModel)).all() == []
        )


def test_new_hypothesis_defaults(tmp_path):
    session_factory = create_session_factory(tmp_path / "defaults.sqlite3")
    with session_factory() as session:
        offer = _make_offer(session)
        prospect_id = _make_prospect(session)
        hypothesis = _make_hypothesis(session, offer.id, prospect_id)

        assert hypothesis.status == "DRAFT"
        assert hypothesis.is_active is False
        assert hypothesis.reasoning_confidence is None
        assert hypothesis.reasoning_confidence_explanation == "[]"
        # Reserved for MVP 1.4 — must stay NULL throughout MVP 1.3.
        assert hypothesis.empirical_confidence is None
        assert hypothesis.reviewer_assessment is None


def test_evidence_status_defaults_active_and_migrates_legacy_db(tmp_path):
    # New entries default to ACTIVE.
    session_factory = create_session_factory(tmp_path / "evidence.sqlite3")
    with session_factory() as session:
        entry = _make_evidence(session)
        assert entry.status == "ACTIVE"

    # A legacy database without the status column gains it via migrate().
    legacy_path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(legacy_path)
    connection.execute(
        """
        CREATE TABLE evidence_entries (
            id TEXT PRIMARY KEY,
            project TEXT NOT NULL,
            evidence_type TEXT NOT NULL,
            evidence TEXT NOT NULL,
            impact INTEGER NOT NULL,
            source TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "INSERT INTO evidence_entries (id, project, evidence_type, evidence, impact, created_at) "
        "VALUES ('EV-LEGACY1', 'DNGun', 'Campaign Outcome', 'Legacy entry', 1, '2026-01-01T00:00:00+00:00')"
    )
    connection.commit()
    connection.close()

    migrate(legacy_path)

    connection = sqlite3.connect(legacy_path)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(evidence_entries)")}
    assert "status" in columns
    status = connection.execute(
        "SELECT status FROM evidence_entries WHERE id = 'EV-LEGACY1'"
    ).fetchone()[0]
    connection.close()
    assert status == "ACTIVE"


# ---------------------------------------------------------------------------
# MVP 1.3A-2 — repository, lifecycle, reasoning confidence, activation
# ---------------------------------------------------------------------------

NOW = datetime(2026, 7, 11, 12, 0, 0, tzinfo=timezone.utc)


def _iso(days_ago: int) -> str:
    return (NOW - timedelta(days=days_ago)).isoformat()


def _entry(
    entry_id: str,
    *,
    status: str = "ACTIVE",
    evidence_type: str = "Campaign Outcome",
    days_ago: int = 10,
    source: str | None = "https://example.com/proof",
    offer_id: str | None = None,
    pdm_code: str | None = None,
    evidence_text: str = "Prospect announced ecommerce expansion.",
    signal_code: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=entry_id,
        status=status,
        evidence_type=evidence_type,
        created_at=_iso(days_ago),
        source=source,
        offer_id=offer_id,
        pdm_code=pdm_code,
        evidence=evidence_text,
        signal_code=signal_code,
    )


def _score(entries, *, offer_id="O-X", pdm=None, dm=None):
    return compute_reasoning_confidence(
        entries,
        offer_id=offer_id,
        prospect_pdm_code=pdm,
        decision_maker_text=dm,
        now=NOW,
    )


def _events(session, hypothesis_id: str) -> list[str]:
    return [
        event.event_type
        for event in Repository(session).list_hypothesis_audit_events(hypothesis_id)
    ]


def _draft_with_evidence(session, *, evidence_count: int = 1):
    repository = Repository(session)
    offer = _make_offer(session)
    prospect_id = _make_prospect(session)
    hypothesis = repository.create_hypothesis(
        offer.id,
        prospect_id,
        "Expanding from integration services into ecommerce.",
        "HUMAN",
    )
    entries = [_make_evidence(session) for _ in range(evidence_count)]
    for entry in entries:
        repository.attach_evidence(hypothesis.id, entry.id)
    return repository, offer, prospect_id, hypothesis, entries


def _approved(session, *, evidence_count: int = 1):
    repository, offer, prospect_id, hypothesis, entries = _draft_with_evidence(
        session, evidence_count=evidence_count
    )
    repository.propose_hypothesis(hypothesis.id)
    repository.approve_hypothesis(hypothesis.id)
    return repository, offer, prospect_id, hypothesis, entries


# --- reasoning-confidence rubric (pure function) ---------------------------


def test_confidence_zero_without_countable_evidence():
    score, lines = _score([])
    assert score == 0
    assert any("Reasoning confidence: 0/100" in line for line in lines)

    # Withdrawn-only support floors at 0, never negative.
    score, _ = _score([_entry("EV-1", status="RETRACTED")])
    assert score == 0


def test_confidence_count_diminishing_returns():
    one, _ = _score([_entry("EV-1")])
    two, _ = _score([_entry("EV-1"), _entry("EV-2")])
    three, _ = _score([_entry("EV-1"), _entry("EV-2"), _entry("EV-3")])
    # Same type, same recency: marginal gain shrinks (12 > 9+4? no —
    # each extra entry adds count weight + recency until caps).
    assert one < two < three
    # Sixth entry adds no count weight and recency is capped at 3 entries.
    five = _score([_entry(f"EV-{i}") for i in range(5)])[0]
    six = _score([_entry(f"EV-{i}") for i in range(6)])[0]
    assert six == five


def test_confidence_diversity_recency_relevance_and_dm_coverage():
    base_entries = [_entry("EV-1"), _entry("EV-2")]
    base, _ = _score(base_entries)

    diverse, _ = _score([_entry("EV-1"), _entry("EV-2", evidence_type="Hiring Signal")])
    assert diverse == base + 6

    stale_recency = _score(
        [_entry("EV-1"), _entry("EV-2", days_ago=120)]
    )[0]
    assert stale_recency == base - 4  # second entry loses its recency points

    offer_relevant, _ = _score(
        [_entry("EV-1", offer_id="O-X"), _entry("EV-2")], offer_id="O-X"
    )
    assert offer_relevant == base + 8

    pdm_relevant, _ = _score(
        [_entry("EV-1", pdm_code="AI-AUTOMATION"), _entry("EV-2")],
        pdm="AI-AUTOMATION",
    )
    assert pdm_relevant == base + 6

    covered, _ = _score(
        [_entry("EV-1", evidence_text="Founder Dana Chen discussed expansion."), _entry("EV-2")],
        dm="Dana Chen Founder & CEO",
    )
    assert covered == base + 10

    uncovered, lines = _score(base_entries, dm="Dana Chen Founder & CEO")
    assert uncovered == base
    assert any("Decision-maker coverage" in line for line in lines)


def test_confidence_penalties():
    base, _ = _score([_entry("EV-1"), _entry("EV-2")])

    stale, _ = _score([_entry("EV-1"), _entry("EV-2", days_ago=400)])
    assert stale == base - 4 - 3  # loses recency, gains stale penalty

    weak, _ = _score([_entry("EV-1"), _entry("EV-2", source=None)])
    assert weak == base - 2

    withdrawn, _ = _score(
        [_entry("EV-1"), _entry("EV-2"), _entry("EV-3", status="RETRACTED")]
    )
    assert withdrawn == base - 8

    invalidated, _ = _score(
        [_entry("EV-1"), _entry("EV-2"), _entry("EV-3", status="INVALIDATED")]
    )
    assert invalidated == base - 8


def test_confidence_archived_counts_but_not_recent():
    active, _ = _score([_entry("EV-1")])
    archived, _ = _score([_entry("EV-1", status="ARCHIVED")])
    assert archived == active - 4  # same count weight, no recency points


def test_confidence_upper_bound_is_100():
    entries = [
        _entry(
            f"EV-{i}",
            evidence_type=f"Type {i}",
            days_ago=5,
            offer_id="O-X",
            pdm_code="AI-AUTOMATION",
            evidence_text="Founder Dana Chen announced marketplace expansion.",
        )
        for i in range(5)
    ]
    score, lines = _score(entries, offer_id="O-X", pdm="AI-AUTOMATION", dm="Dana Chen Founder")
    assert score == 100
    assert any("Reasoning confidence: 100/100" in line for line in lines)


def test_confidence_deterministic_under_reordering():
    entries = [
        _entry("EV-1", evidence_type="Hiring Signal", days_ago=200, source=None),
        _entry("EV-2", offer_id="O-X"),
        _entry("EV-3", status="RETRACTED"),
        _entry("EV-4", status="ARCHIVED", days_ago=400),
    ]
    forward = _score(entries, offer_id="O-X")
    backward = _score(list(reversed(entries)), offer_id="O-X")
    assert forward == backward  # identical score AND explanation lines


# --- repository operations and lifecycle -----------------------------------


def test_create_hypothesis_draft_with_audit(tmp_path):
    session_factory = create_session_factory(tmp_path / "create.sqlite3")
    with session_factory() as session:
        repository, offer, prospect_id, hypothesis, _ = _draft_with_evidence(session)
        assert hypothesis.status == "DRAFT"
        assert hypothesis.is_active is False
        assert hypothesis.reasoning_confidence is None
        assert _events(session, hypothesis.id)[0] == "CREATED"

        listed = repository.list_hypotheses(offer.id, prospect_id)
        assert [item.id for item in listed] == [hypothesis.id]


def test_create_hypothesis_validations(tmp_path):
    session_factory = create_session_factory(tmp_path / "create_val.sqlite3")
    with session_factory() as session:
        repository = Repository(session)
        offer = _make_offer(session)
        prospect_id = _make_prospect(session)

        with pytest.raises(HypothesisGovernanceError):
            repository.create_hypothesis(offer.id, prospect_id, "x", "ORACLE")
        with pytest.raises(HypothesisGovernanceError):
            repository.create_hypothesis("O-MISSING", prospect_id, "x", "HUMAN")
        with pytest.raises(HypothesisGovernanceError):
            repository.create_hypothesis(offer.id, "P-MISSING", "x", "HUMAN")

        # Refinement parent must exist and share the same offer x prospect pair.
        other_prospect = _make_prospect(session)
        parent = repository.create_hypothesis(offer.id, prospect_id, "parent", "HUMAN")
        with pytest.raises(HypothesisGovernanceError):
            repository.create_hypothesis(
                offer.id,
                other_prospect,
                "refinement",
                "HUMAN",
                refines_hypothesis_id=parent.id,
            )

        # A decision maker must belong to the prospect being bound.
        foreign_dm = repository.create_decision_maker(
            other_prospect,
            __import__("backend.app.schemas", fromlist=["DecisionMakerCreate"]).DecisionMakerCreate(
                name="Elsewhere", role="CEO"
            ),
            90,
            "CEO",
        )
        with pytest.raises(HypothesisGovernanceError):
            repository.create_hypothesis(
                offer.id, prospect_id, "x", "HUMAN", decision_maker_id=foreign_dm.id
            )


def test_draft_editing_and_freeze(tmp_path):
    session_factory = create_session_factory(tmp_path / "freeze.sqlite3")
    with session_factory() as session:
        repository, _, _, hypothesis, entries = _draft_with_evidence(session)

        repository.update_draft_hypothesis(hypothesis.id, statement="Refined claim.")
        assert repository.get_hypothesis(hypothesis.id).statement == "Refined claim."
        assert "DRAFT_UPDATED" in _events(session, hypothesis.id)

        repository.propose_hypothesis(hypothesis.id)

        # Canonical content is frozen from PROPOSED onward — even for a typo.
        with pytest.raises(HypothesisGovernanceError):
            repository.update_draft_hypothesis(hypothesis.id, statement="Refined claim (typo fix).")
        with pytest.raises(HypothesisGovernanceError):
            repository.attach_evidence(hypothesis.id, _make_evidence(session).id)
        with pytest.raises(HypothesisGovernanceError):
            repository.detach_evidence(hypothesis.id, entries[0].id)
        with pytest.raises(HypothesisGovernanceError):
            repository.compute_hypothesis_confidence(hypothesis.id)


def test_attach_evidence_rules(tmp_path):
    session_factory = create_session_factory(tmp_path / "attach.sqlite3")
    with session_factory() as session:
        repository, _, _, hypothesis, entries = _draft_with_evidence(session)

        # Duplicate attachment rejected.
        with pytest.raises(RepositoryConflictError):
            repository.attach_evidence(hypothesis.id, entries[0].id)

        # Only ACTIVE evidence may be newly attached.
        retracted = _make_evidence(session)
        repository.update_evidence_status(retracted.id, "RETRACTED")
        with pytest.raises(HypothesisGovernanceError):
            repository.attach_evidence(hypothesis.id, retracted.id)

        # Attach/detach reset any previously computed confidence to NULL.
        repository.compute_hypothesis_confidence(hypothesis.id, now=NOW)
        assert repository.get_hypothesis(hypothesis.id).reasoning_confidence is not None
        extra = _make_evidence(session)
        repository.attach_evidence(hypothesis.id, extra.id)
        assert repository.get_hypothesis(hypothesis.id).reasoning_confidence is None

        repository.compute_hypothesis_confidence(hypothesis.id, now=NOW)
        repository.detach_evidence(hypothesis.id, extra.id)
        assert repository.get_hypothesis(hypothesis.id).reasoning_confidence is None

        events = _events(session, hypothesis.id)
        assert "EVIDENCE_ATTACHED" in events
        assert "EVIDENCE_DETACHED" in events
        assert "CONFIDENCE_COMPUTED" in events
        # Attaching evidence / computing confidence never changes status.
        assert repository.get_hypothesis(hypothesis.id).status == "DRAFT"


def test_propose_computes_and_freezes_confidence(tmp_path):
    session_factory = create_session_factory(tmp_path / "propose.sqlite3")
    with session_factory() as session:
        repository, _, _, hypothesis, _ = _draft_with_evidence(session)
        proposed = repository.propose_hypothesis(hypothesis.id, now=NOW)
        assert proposed.status == "PROPOSED"
        assert proposed.reasoning_confidence is not None
        assert json.loads(proposed.reasoning_confidence_explanation)

        # Proposing with no evidence is allowed (score 0) but unapprovable.
        repository2, _, _, empty, _ = _draft_with_evidence(session, evidence_count=1)
        repository2.detach_evidence(empty.id, repository2.list_hypothesis_evidence_links(empty.id)[0].evidence_entry_id)
        repository2.propose_hypothesis(empty.id, now=NOW)
        assert repository2.get_hypothesis(empty.id).reasoning_confidence == 0
        with pytest.raises(HypothesisGovernanceError):
            repository2.approve_hypothesis(empty.id)  # invariant 1


def test_approve_and_reject_gates(tmp_path):
    session_factory = create_session_factory(tmp_path / "review.sqlite3")
    with session_factory() as session:
        repository, _, _, hypothesis, _ = _draft_with_evidence(session)

        # Approval requires PROPOSED status.
        with pytest.raises(HypothesisGovernanceError):
            repository.approve_hypothesis(hypothesis.id)

        repository.propose_hypothesis(hypothesis.id, now=NOW)
        frozen_score = repository.get_hypothesis(hypothesis.id).reasoning_confidence

        with pytest.raises(HypothesisGovernanceError):
            repository.approve_hypothesis(hypothesis.id, reviewer_assessment="EXCELLENT")

        approved = repository.approve_hypothesis(
            hypothesis.id, reviewer_assessment="STRONG", review_notes="Solid basis."
        )
        assert approved.status == "APPROVED"
        assert approved.reviewer_assessment == "STRONG"
        assert approved.reviewed_at is not None
        # Reviewer assessment and approval never move the computed score.
        assert approved.reasoning_confidence == frozen_score
        assert approved.empirical_confidence is None

        # Reject path, and REJECTED is not re-reviewable.
        repository2, _, _, second, _ = _draft_with_evidence(session)
        repository2.propose_hypothesis(second.id, now=NOW)
        rejected = repository2.reject_hypothesis(second.id, review_notes="Weak.")
        assert rejected.status == "REJECTED"
        with pytest.raises(HypothesisGovernanceError):
            repository2.approve_hypothesis(second.id)
        with pytest.raises(HypothesisGovernanceError):
            repository2.reject_hypothesis(second.id)


def test_activation_preconditions(tmp_path):
    session_factory = create_session_factory(tmp_path / "activate.sqlite3")
    with session_factory() as session:
        repository, offer, prospect_id, hypothesis, entries = _draft_with_evidence(session)

        # Not APPROVED: DRAFT, PROPOSED, REJECTED all rejected.
        with pytest.raises(HypothesisGovernanceError):
            repository.activate_hypothesis(hypothesis.id)
        repository.propose_hypothesis(hypothesis.id, now=NOW)
        with pytest.raises(HypothesisGovernanceError):
            repository.activate_hypothesis(hypothesis.id)

        repository.approve_hypothesis(hypothesis.id)

        # Disqualifying evidence lifecycle state blocks activation...
        repository.update_evidence_status(entries[0].id, "RETRACTED")
        with pytest.raises(HypothesisGovernanceError):
            repository.activate_hypothesis(hypothesis.id)
        # ...but the historical link and audit trail are preserved,
        # and the evidence still cannot be physically deleted.
        assert repository.list_hypothesis_evidence_links(hypothesis.id)
        with pytest.raises(IntegrityError):
            session.execute(
                delete(models.EvidenceEntryModel).where(
                    models.EvidenceEntryModel.id == entries[0].id
                )
            )
        session.rollback()

        repository.update_evidence_status(entries[0].id, "ACTIVE")

        # Simulated drift: APPROVED but confidence never computed → rejected.
        session.execute(
            update(models.AcquisitionHypothesisModel)
            .where(models.AcquisitionHypothesisModel.id == hypothesis.id)
            .values(reasoning_confidence=None)
        )
        session.commit()
        with pytest.raises(HypothesisGovernanceError):
            repository.activate_hypothesis(hypothesis.id)
        session.execute(
            update(models.AcquisitionHypothesisModel)
            .where(models.AcquisitionHypothesisModel.id == hypothesis.id)
            .values(reasoning_confidence=40)
        )
        session.commit()

        activated = repository.activate_hypothesis(hypothesis.id)
        assert activated.is_active is True
        assert repository.get_active_hypothesis(offer.id, prospect_id).id == hypothesis.id
        events = _events(session, hypothesis.id)
        assert "ACTIVATED" in events


def test_activation_requires_approved_parent(tmp_path):
    session_factory = create_session_factory(tmp_path / "parent.sqlite3")
    with session_factory() as session:
        repository, offer, prospect_id, parent, _ = _draft_with_evidence(session)

        refinement = repository.create_hypothesis(
            offer.id,
            prospect_id,
            "Founder-facing refinement.",
            "HUMAN",
            refines_hypothesis_id=parent.id,
            recipient_framing="Category ownership.",
        )
        entry = _make_evidence(session)
        repository.attach_evidence(refinement.id, entry.id)
        repository.propose_hypothesis(refinement.id, now=NOW)
        repository.approve_hypothesis(refinement.id)

        # Parent still DRAFT → refinement cannot activate.
        with pytest.raises(HypothesisGovernanceError):
            repository.activate_hypothesis(refinement.id)

        repository.propose_hypothesis(parent.id, now=NOW)
        repository.approve_hypothesis(parent.id)
        assert repository.activate_hypothesis(refinement.id).is_active is True


def test_activation_swap_keeps_exactly_one_active(tmp_path):
    session_factory = create_session_factory(tmp_path / "swap.sqlite3")
    with session_factory() as session:
        repository, offer, prospect_id, first, _ = _approved(session)
        repository.activate_hypothesis(first.id)

        second = repository.create_hypothesis(
            offer.id, prospect_id, "Competing hypothesis.", "HUMAN"
        )
        repository.attach_evidence(second.id, _make_evidence(session).id)
        repository.propose_hypothesis(second.id, now=NOW)
        repository.approve_hypothesis(second.id)
        repository.activate_hypothesis(second.id)

        actives = session.scalars(
            select(models.AcquisitionHypothesisModel).where(
                models.AcquisitionHypothesisModel.is_active == True  # noqa: E712
            )
        ).all()
        assert [row.id for row in actives] == [second.id]
        # Deactivated hypothesis remains APPROVED and audited.
        assert repository.get_hypothesis(first.id).status == "APPROVED"
        assert "DEACTIVATED" in _events(session, first.id)


def test_supersession_is_atomic_and_preserving(tmp_path):
    session_factory = create_session_factory(tmp_path / "supersede.sqlite3")
    with session_factory() as session:
        repository, offer, prospect_id, hypothesis, entries = _approved(session, evidence_count=2)
        repository.activate_hypothesis(hypothesis.id)

        successor = repository.supersede_hypothesis(
            hypothesis.id, statement="Sharper claim about ecommerce expansion."
        )

        predecessor = repository.get_hypothesis(hypothesis.id)
        assert predecessor.status == "SUPERSEDED"
        assert predecessor.is_active is False
        assert predecessor.superseded_by_id == successor.id
        # Predecessor's evidence trail is fully preserved.
        assert len(repository.list_hypothesis_evidence_links(hypothesis.id)) == 2

        assert successor.status == "DRAFT"
        assert successor.reasoning_confidence is None
        assert successor.offer_id == offer.id and successor.prospect_id == prospect_id
        assert successor.statement == "Sharper claim about ecommerce expansion."
        # Successor starts from the predecessor's evidence set (editable in DRAFT).
        assert len(repository.list_hypothesis_evidence_links(successor.id)) == 2
        # No active hypothesis remains — the successor must earn activation.
        assert repository.get_active_hypothesis(offer.id, prospect_id) is None

        # SUPERSEDED is terminal: no resurrection through any operation.
        for operation in (
            lambda: repository.propose_hypothesis(hypothesis.id),
            lambda: repository.approve_hypothesis(hypothesis.id),
            lambda: repository.activate_hypothesis(hypothesis.id),
            lambda: repository.supersede_hypothesis(hypothesis.id),
            lambda: repository.update_draft_hypothesis(hypothesis.id, statement="zombie"),
        ):
            with pytest.raises(HypothesisGovernanceError):
                operation()

        # DRAFT hypotheses are edited, not superseded.
        with pytest.raises(HypothesisGovernanceError):
            repository.supersede_hypothesis(successor.id)


def test_supersession_rolls_back_atomically(tmp_path, monkeypatch):
    session_factory = create_session_factory(tmp_path / "rollback.sqlite3")
    with session_factory() as session:
        repository, offer, prospect_id, hypothesis, _ = _approved(session)
        repository.activate_hypothesis(hypothesis.id)
        events_before = len(_events(session, hypothesis.id))

        original = Repository._record_hypothesis_audit

        def explode(self, hypothesis_id, event_type, detail):
            if event_type == "CREATED" and hypothesis_id != hypothesis.id:
                raise RuntimeError("simulated failure mid-supersession")
            return original(self, hypothesis_id, event_type, detail)

        monkeypatch.setattr(Repository, "_record_hypothesis_audit", explode)
        with pytest.raises(RuntimeError):
            repository.supersede_hypothesis(hypothesis.id)
        monkeypatch.setattr(Repository, "_record_hypothesis_audit", original)

        # Nothing about the predecessor changed and no successor exists.
        reloaded = repository.get_hypothesis(hypothesis.id)
        assert reloaded.status == "APPROVED"
        assert reloaded.is_active is True
        assert reloaded.superseded_by_id is None
        assert len(repository.list_hypotheses(offer.id, prospect_id)) == 1
        assert len(_events(session, hypothesis.id)) == events_before


def test_corrections_allowlist_and_audit(tmp_path):
    session_factory = create_session_factory(tmp_path / "correct.sqlite3")
    with session_factory() as session:
        repository, _, _, hypothesis, entries = _approved(session)

        # Substantive change disguised as a correction is rejected.
        for field in ("statement", "recipient_framing", "status", "reasoning_confidence"):
            with pytest.raises(HypothesisGovernanceError):
                repository.correct_hypothesis_metadata(
                    hypothesis.id, field, "sneaky", reason="typo"
                )

        repository.correct_hypothesis_metadata(
            hypothesis.id, "review_notes", "Clarified operator note.", reason="typo in note"
        )
        repository.correct_evidence_link_note(
            hypothesis.id, entries[0].id, "Corrected link annotation.", reason="fixed URL label"
        )

        corrections = [
            event
            for event in Repository(session).list_hypothesis_audit_events(hypothesis.id)
            if event.event_type == "METADATA_CORRECTED"
        ]
        assert len(corrections) == 2
        payloads = [json.loads(event.detail) for event in corrections]
        assert all("before" in payload and "after" in payload for payload in payloads)


def test_dormant_states_unreachable(tmp_path):
    session_factory = create_session_factory(tmp_path / "dormant.sqlite3")
    with session_factory() as session:
        repository, _, _, hypothesis, _ = _draft_with_evidence(session)
        model = session.get(models.AcquisitionHypothesisModel, hypothesis.id)

        for dormant in ("VALIDATING", "SUPPORTED", "WEAKENED"):
            with pytest.raises(HypothesisGovernanceError):
                repository._transition(model, dormant)

        # Forbidden transitions across the implemented lifecycle.
        forbidden = [
            ("DRAFT", "APPROVED"),
            ("DRAFT", "REJECTED"),
            ("DRAFT", "SUPERSEDED"),
            ("PROPOSED", "DRAFT"),
            ("APPROVED", "REJECTED"),
            ("APPROVED", "PROPOSED"),
            ("REJECTED", "APPROVED"),
            ("SUPERSEDED", "DRAFT"),
            ("SUPERSEDED", "APPROVED"),
        ]
        for current, target in forbidden:
            model.status = current
            with pytest.raises(HypothesisGovernanceError):
                repository._transition(model, target)
        model.status = "DRAFT"
        session.commit()


def test_empirical_confidence_stays_null_through_lifecycle(tmp_path):
    session_factory = create_session_factory(tmp_path / "empirical.sqlite3")
    with session_factory() as session:
        repository, _, _, hypothesis, _ = _approved(session)
        repository.activate_hypothesis(hypothesis.id)
        successor = repository.supersede_hypothesis(hypothesis.id)
        for hypothesis_id in (hypothesis.id, successor.id):
            assert repository.get_hypothesis(hypothesis_id).empirical_confidence is None


def test_evidence_status_change_preserves_history(tmp_path):
    session_factory = create_session_factory(tmp_path / "ev_history.sqlite3")
    with session_factory() as session:
        repository, _, _, hypothesis, entries = _approved(session)
        events_before = _events(session, hypothesis.id)

        with pytest.raises(HypothesisGovernanceError):
            repository.update_evidence_status(entries[0].id, "DELETED")

        repository.update_evidence_status(entries[0].id, "INVALIDATED")
        # Historical link and audit trail untouched by the state change.
        assert repository.list_hypothesis_evidence_links(hypothesis.id)
        assert _events(session, hypothesis.id) == events_before
