from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.database import create_session_factory
from backend.app.main import create_app
from backend.app.authority_engine import AuthorityScoringEngine
from backend.app.repository import Repository
from backend.app.schemas import DecisionMakerCreate, ProspectCreate
from backend.app.rules import RuleRegistry
from backend.app import models
from backend.scripts.migrate_db import migrate
from backend.scripts.recalculate_authority import recalculate_decision_maker_authority


def test_authority_scoring_engine_keyword_rules():
    engine = AuthorityScoringEngine()

    # Test exact and substring role matches
    score, rationale = engine.calculate("Founder")
    assert score == 95
    assert "early-stage company" in rationale

    score, rationale = engine.calculate("Co-Founder & CEO")
    assert score == 95  # co-founder has higher priority keyword match order

    score, rationale = engine.calculate("Chief Executive Officer")
    assert score == 90

    score, rationale = engine.calculate("Growth Marketing Lead")
    assert score == 75

    score, rationale = engine.calculate("Analyst / Unknown Role")
    assert score == 20
    assert "Standard corporate contact" in rationale


def test_authority_scoring_whole_word_matches():
    engine = AuthorityScoringEngine()

    expected = {
        "Founder": 95,
        "Founder & CEO": 95,
        "Co-Founder": 95,
        "CEO": 90,
        "Chief Operating Officer": 55,
        "COO": 55,
        "Head of Growth": 75,
        "VP of Marketing": 75,
    }
    for role, expected_score in expected.items():
        score, _ = engine.calculate(role)
        assert score == expected_score, f"{role!r} scored {score}, expected {expected_score}"


def test_authority_scoring_rejects_embedded_keyword_matches():
    engine = AuthorityScoringEngine()

    # "coo" must not match inside "coordinator": these fall through to the default.
    for role in ["Marketing Coordinator", "Sales Coordinator", "Project Coordinator"]:
        score, rationale = engine.calculate(role)
        assert score == 20, f"{role!r} scored {score}, expected default 20"
        assert "Standard corporate contact" in rationale
        assert "COO" not in rationale


def test_recalculate_decision_maker_authority_fixes_stale_scores(tmp_path):
    db_path = tmp_path / "test_recalc.sqlite3"
    session_factory = create_session_factory(db_path)

    with session_factory() as session:
        repository = Repository(session)
        prospect = repository.create_prospect(
            ProspectCreate(company_name="Recalc Corp", segment="AI_AUTOMATION")
        )
        # Stale record: stored score/rationale predate the matcher fix.
        stale = repository.create_decision_maker(
            prospect.id,
            DecisionMakerCreate(name="Stale Coordinator", role="Marketing Coordinator"),
            55,
            "COO handles operations and corporate domain infrastructure.",
        )
        # Correct record: must not be touched by the recalculation.
        current = repository.create_decision_maker(
            prospect.id,
            DecisionMakerCreate(name="Fresh Founder", role="Founder"),
            95,
            "Founder likely controls branding and domain acquisition decisions for early-stage company.",
        )

    result = recalculate_decision_maker_authority(db_path)
    assert result == {"scanned": 2, "updated": 1}

    with session_factory() as session:
        repository = Repository(session)
        fixed = repository.get_decision_maker(stale.id)
        assert fixed.authority_score == 20
        assert "Standard corporate contact" in fixed.acquisition_rationale
        assert fixed.updated_at != stale.updated_at

        untouched = repository.get_decision_maker(current.id)
        assert untouched.authority_score == 95
        assert untouched.updated_at == current.updated_at

    # Second run is a no-op.
    assert recalculate_decision_maker_authority(db_path) == {"scanned": 2, "updated": 0}


def test_decision_maker_repository_crud(tmp_path):
    db_path = tmp_path / "test_dm.sqlite3"
    session_factory = create_session_factory(db_path)

    with session_factory() as session:
        repository = Repository(session)

        # Create a prospect using pre-seeded AI_AUTOMATION segment
        prospect = repository.create_prospect(
            ProspectCreate(company_name="Test Corp", segment="AI_AUTOMATION")
        )

        # Create decision maker
        data1 = DecisionMakerCreate(name="Alice", role="Founder")
        rules = RuleRegistry()
        score1, rational1 = AuthorityScoringEngine(rules).calculate(data1.role)
        dm1 = repository.create_decision_maker(prospect.id, data1, score1, rational1)
        assert dm1.name == "Alice"
        assert dm1.authority_score == 95
        assert dm1.entry_source == "MANUAL"

        # Create another decision maker (lower score)
        data2 = DecisionMakerCreate(name="Bob", role="CTO")
        score2, rational2 = AuthorityScoringEngine(rules).calculate(data2.role)
        dm2 = repository.create_decision_maker(prospect.id, data2, score2, rational2)

        # List decision makers - should be sorted by score descending
        dms = repository.list_decision_makers(prospect.id)
        assert len(dms) == 2
        assert dms[0].name == "Alice"  # 95
        assert dms[1].name == "Bob"    # 30

        # Update decision maker
        data_update = DecisionMakerCreate(name="Alice Update", role="CEO")
        score_up, rational_up = AuthorityScoringEngine(rules).calculate(data_update.role)
        updated = repository.update_decision_maker(dm1.id, data_update, score_up, rational_up)
        assert updated.name == "Alice Update"
        assert updated.authority_score == 90
        assert updated.updated_at != updated.created_at

        # Delete decision maker
        assert repository.delete_decision_maker(dm2.id) is True
        assert len(repository.list_decision_makers(prospect.id)) == 1


def test_decision_maker_cascading_delete(tmp_path):
    db_path = tmp_path / "test_dm_cascade.sqlite3"
    session_factory = create_session_factory(db_path)

    with session_factory() as session:
        repository = Repository(session)
        # Use pre-seeded SEO segment
        prospect = repository.create_prospect(
            ProspectCreate(company_name="Test Corp 2", segment="SEO")
        )

        data = DecisionMakerCreate(name="Alice", role="CEO")
        dm = repository.create_decision_maker(prospect.id, data, 90, "CEO")
        assert repository.get_decision_maker(dm.id) is not None

        # Delete prospect
        session.delete(session.get(models.ProspectModel, prospect.id))
        session.commit()

        # Decision maker should be deleted automatically via cascade
        assert repository.get_decision_maker(dm.id) is None


def test_decision_maker_endpoints(tmp_path):
    db_path = tmp_path / "test_dm_endpoints.sqlite3"
    client = TestClient(create_app(db_path))

    # Add dynamic segment
    client.post("/segments", json={"code": "REVOPS_TEST", "label": "RevOps Test", "pdm_code": "REVOPS-TEST"})

    # Create prospect
    prospect = client.post(
        "/prospects",
        json={"company_name": "API Corp", "segment": "REVOPS_TEST"},
    ).json()

    # Add decision maker
    response = client.post(
        f"/prospects/{prospect['id']}/decision-makers",
        json={"name": "Alice API", "role": "Co-Founder"},
    )
    assert response.status_code == 201
    dm = response.json()
    assert dm["name"] == "Alice API"
    assert dm["authority_score"] == 95

    # Get decision makers list
    dms = client.get(f"/prospects/{prospect['id']}/decision-makers").json()
    assert len(dms) == 1
    assert dms[0]["id"] == dm["id"]

    # Put update
    updated = client.put(
        f"/decision-makers/{dm['id']}",
        json={"name": "Alice API Update", "role": "CEO"},
    ).json()
    assert updated["name"] == "Alice API Update"
    assert updated["authority_score"] == 90

    # Delete
    del_resp = client.delete(f"/decision-makers/{dm['id']}")
    assert del_resp.status_code == 204

    # Ensure list is empty now
    dms_empty = client.get(f"/prospects/{prospect['id']}/decision-makers").json()
    assert len(dms_empty) == 0


class SegmentCreateSchema:
    def __init__(self, code: str, label: str, pdm_code: str):
        self.code = code
        self.label = label
        self.pdm_code = pdm_code

    def model_dump(self, mode=None):
        return {"code": self.code, "label": self.label, "pdm_code": self.pdm_code}
