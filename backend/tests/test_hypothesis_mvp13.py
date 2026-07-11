from __future__ import annotations

import sqlite3

import pytest
from sqlalchemy import delete, select, text

from backend.app import models
from backend.app.database import create_session_factory
from backend.app.repository import Repository, prefixed_id
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
