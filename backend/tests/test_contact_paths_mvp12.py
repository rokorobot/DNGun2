from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.database import create_session_factory
from backend.app.main import create_app
from backend.app.repository import Repository
from backend.app.schemas import DecisionMakerCreate, ProspectCreate, ContactPathCreate, ContactPathType
from backend.app import models


def test_contact_path_repository_crud(tmp_path):
    db_path = tmp_path / "test_cp.sqlite3"
    session_factory = create_session_factory(db_path)

    with session_factory() as session:
        repository = Repository(session)

        # Create prospect and decision maker
        prospect = repository.create_prospect(
            ProspectCreate(company_name="Test Corp", segment="AI_AUTOMATION")
        )
        dm = repository.create_decision_maker(
            prospect.id,
            DecisionMakerCreate(name="Alice", role="CEO"),
            90,
            "CEO"
        )

        # Create contact path with defaults
        data1 = ContactPathCreate(
            type=ContactPathType.EMAIL,
            value="alice@test.com"
        )
        cp1 = repository.create_contact_path(dm.id, data1)
        assert cp1.type == ContactPathType.EMAIL
        assert cp1.value == "alice@test.com"
        assert cp1.source == "MANUAL"
        assert cp1.confidence == 100.0
        assert cp1.verified is False
        assert cp1.last_verified_at is None

        # Create another contact path with custom values
        data2 = ContactPathCreate(
            type=ContactPathType.LINKEDIN,
            value="linkedin.com/in/alice",
            source="APOLLO",
            confidence=95.0,
            verified=True,
            last_verified_at="2026-06-04T12:00:00Z"
        )
        cp2 = repository.create_contact_path(dm.id, data2)
        assert cp2.type == ContactPathType.LINKEDIN
        assert cp2.source == "APOLLO"
        assert cp2.confidence == 95.0
        assert cp2.verified is True
        assert cp2.last_verified_at == "2026-06-04T12:00:00Z"

        # List contact paths
        paths = repository.list_contact_paths(dm.id)
        assert len(paths) == 2
        assert paths[0].value == "alice@test.com"
        assert paths[1].value == "linkedin.com/in/alice"

        # Update contact path
        data_update = ContactPathCreate(
            type=ContactPathType.EMAIL,
            value="alice.new@test.com",
            verified=True,
            last_verified_at="2026-06-04T22:00:00Z"
        )
        updated = repository.update_contact_path(cp1.id, data_update)
        assert updated.value == "alice.new@test.com"
        assert updated.verified is True
        assert updated.last_verified_at == "2026-06-04T22:00:00Z"

        # Delete contact path
        assert repository.delete_contact_path(cp2.id) is True
        assert len(repository.list_contact_paths(dm.id)) == 1


def test_contact_path_cascading_delete(tmp_path):
    db_path = tmp_path / "test_cp_cascade.sqlite3"
    session_factory = create_session_factory(db_path)

    with session_factory() as session:
        repository = Repository(session)
        prospect = repository.create_prospect(
            ProspectCreate(company_name="Test Corp 2", segment="SEO")
        )
        dm = repository.create_decision_maker(
            prospect.id,
            DecisionMakerCreate(name="Alice", role="CEO"),
            90,
            "CEO"
        )

        data = ContactPathCreate(
            type=ContactPathType.EMAIL,
            value="alice@test.com"
        )
        cp = repository.create_contact_path(dm.id, data)
        assert repository.get_contact_path(cp.id) is not None

        # Delete decision maker
        repository.delete_decision_maker(dm.id)

        # Contact path should be automatically deleted via CASCADE
        assert repository.get_contact_path(cp.id) is None


def test_contact_path_endpoints(tmp_path):
    db_path = tmp_path / "test_cp_endpoints.sqlite3"
    client = TestClient(create_app(db_path))

    # Add dynamic segment and prospect
    client.post("/segments", json={"code": "REVOPS_TEST", "label": "RevOps Test", "pdm_code": "REVOPS-TEST"})
    prospect = client.post(
        "/prospects",
        json={"company_name": "API Corp", "segment": "REVOPS_TEST"},
    ).json()

    # Add decision maker
    dm = client.post(
        f"/prospects/{prospect['id']}/decision-makers",
        json={"name": "Alice API", "role": "Co-Founder"},
    ).json()

    # Add contact path
    response = client.post(
        f"/decision-makers/{dm['id']}/contact-paths",
        json={
            "type": "EMAIL",
            "value": "alice@api.com",
            "source": "LINKEDIN",
            "confidence": 85.0,
            "verified": False
        }
    )
    assert response.status_code == 201
    cp = response.json()
    assert cp["value"] == "alice@api.com"
    assert cp["source"] == "LINKEDIN"
    assert cp["confidence"] == 85.0
    assert cp["verified"] is False
    assert cp["last_verified_at"] is None

    # Get contact paths list
    paths = client.get(f"/decision-makers/{dm['id']}/contact-paths").json()
    assert len(paths) == 1
    assert paths[0]["id"] == cp["id"]

    # Hydrate testing: check if decision makers endpoint returns decision maker WITH contact paths
    dms = client.get(f"/prospects/{prospect['id']}/decision-makers").json()
    assert len(dms) == 1
    assert len(dms[0]["contact_paths"]) == 1
    assert dms[0]["contact_paths"][0]["value"] == "alice@api.com"

    # Put update
    updated = client.put(
        f"/contact-paths/{cp['id']}",
        json={
            "type": "EMAIL",
            "value": "alice.verified@api.com",
            "source": "APOLLO",
            "confidence": 99.0,
            "verified": True,
            "last_verified_at": "2026-06-04T22:00:00+00:00"
        }
    ).json()
    assert updated["value"] == "alice.verified@api.com"
    assert updated["verified"] is True
    assert updated["last_verified_at"] == "2026-06-04T22:00:00+00:00"

    # Delete
    del_resp = client.delete(f"/contact-paths/{cp['id']}")
    assert del_resp.status_code == 204

    # Ensure list is empty now
    paths_empty = client.get(f"/decision-makers/{dm['id']}/contact-paths").json()
    assert len(paths_empty) == 0
