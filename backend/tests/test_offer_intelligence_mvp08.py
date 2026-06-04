from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app


def test_create_offer(tmp_path):
    client = TestClient(create_app(tmp_path / "offers.sqlite3"))

    response = client.post(
        "/offers",
        json={
            "name": "RobotStore.app",
            "offer_type": "DOMAIN_NAME",
            "estimated_value": 25000,
        },
    )

    assert response.status_code == 201
    offer = response.json()
    assert offer["id"].startswith("O-")
    assert offer["name"] == "RobotStore.app"
    assert offer["status"] == "DRAFT"
    assert "target_segments" not in offer


def test_deterministic_evaluation_creates_proposal(tmp_path):
    client = TestClient(create_app(tmp_path / "offers.sqlite3"))
    offer = _create_offer(client)

    response = client.post(
        f"/offers/{offer['id']}/evaluate",
        json={"mode": "DETERMINISTIC"},
    )

    assert response.status_code == 201
    proposal = response.json()
    assert proposal["provider"] == "deterministic"
    assert proposal["mode"] == "DETERMINISTIC"
    assert proposal["primary_category"] == "Robotics Marketplace"
    assert proposal["status"] == "PENDING_REVIEW"
    assert proposal["proposed_profile_json"]["buyer_profiles"]


def test_llm_unavailable_falls_back_safely(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = TestClient(create_app(tmp_path / "offers.sqlite3"))
    offer = _create_offer(client)

    proposal = client.post(
        f"/offers/{offer['id']}/evaluate",
        json={"mode": "LLM_ASSISTED"},
    ).json()

    assert proposal["provider"] == "deterministic"
    assert proposal["mode"] == "LLM_ASSISTED"
    assert proposal["primary_category"] == "Robotics Marketplace"


def test_intelligence_profile_unavailable_before_approval(tmp_path):
    client = TestClient(create_app(tmp_path / "offers.sqlite3"))
    offer = _create_offer(client)
    client.post(f"/offers/{offer['id']}/evaluate", json={"mode": "DETERMINISTIC"})

    response = client.get(f"/offers/{offer['id']}/intelligence-profile")

    assert response.status_code == 404


def test_approving_proposal_creates_profile_rows_and_profile_is_retrievable(tmp_path):
    client = TestClient(create_app(tmp_path / "offers.sqlite3"))
    offer = _create_offer(client)
    proposal = client.post(
        f"/offers/{offer['id']}/evaluate",
        json={"mode": "DETERMINISTIC"},
    ).json()

    approved = client.post(
        f"/offers/{offer['id']}/proposals/{proposal['id']}/approve",
        json={"review_notes": "Looks commercially plausible."},
    )
    profile_response = client.get(f"/offers/{offer['id']}/intelligence-profile")
    updated_offer = client.get(f"/offers/{offer['id']}").json()

    assert approved.status_code == 200
    profile = approved.json()
    assert profile["profile"]["offer_category"] == "Robotics Marketplace"
    assert profile["profile"]["target_segments"] == ["Robotics", "Automation", "Humanoids"]
    assert len(profile["buyerProfiles"]) >= 3
    assert len(profile["signalProfiles"]) >= 3
    assert profile["pdm"]["code"] == "PDM-ROBOTICS-MARKETPLACE"
    assert profile_response.status_code == 200
    assert updated_offer["status"] == "PROFILED"


def test_rejected_proposal_does_not_create_profile(tmp_path):
    client = TestClient(create_app(tmp_path / "offers.sqlite3"))
    offer = _create_offer(client)
    proposal = client.post(
        f"/offers/{offer['id']}/evaluate",
        json={"mode": "DETERMINISTIC"},
    ).json()

    rejected = client.post(
        f"/offers/{offer['id']}/proposals/{proposal['id']}/reject",
        json={"review_notes": "Wrong category."},
    )
    profile = client.get(f"/offers/{offer['id']}/intelligence-profile")

    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"
    assert profile.status_code == 404


def test_invalid_proposal_approval_returns_controlled_error(tmp_path):
    client = TestClient(create_app(tmp_path / "offers.sqlite3"))
    offer = _create_offer(client)

    response = client.post(
        f"/offers/{offer['id']}/proposals/OEP-MISSING/approve",
        json={"review_notes": "No such proposal."},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Offer proposal cannot be approved"


def test_duplicate_approved_profile_is_handled_safely(tmp_path):
    client = TestClient(create_app(tmp_path / "offers.sqlite3"))
    offer = _create_offer(client)
    first = client.post(f"/offers/{offer['id']}/evaluate", json={"mode": "DETERMINISTIC"}).json()
    second = client.post(f"/offers/{offer['id']}/evaluate", json={"mode": "DETERMINISTIC"}).json()

    first_approval = client.post(f"/offers/{offer['id']}/proposals/{first['id']}/approve")
    second_approval = client.post(f"/offers/{offer['id']}/proposals/{second['id']}/approve")
    repeat_approval = client.post(f"/offers/{offer['id']}/proposals/{second['id']}/approve")
    proposals = client.get(f"/offers/{offer['id']}/proposals").json()

    assert first_approval.status_code == 200
    assert second_approval.status_code == 200
    assert repeat_approval.status_code == 409
    statuses = {proposal["id"]: proposal["status"] for proposal in proposals}
    assert statuses[first["id"]] == "SUPERSEDED"
    assert statuses[second["id"]] == "APPROVED"


def test_offer_intelligence_does_not_modify_rule_files(tmp_path):
    client = TestClient(create_app(tmp_path / "offers.sqlite3"))
    rules_dir = Path("backend/app/rules")
    before = {path.name: path.read_text(encoding="utf-8") for path in rules_dir.glob("*.yaml")}
    offer = _create_offer(client)

    proposal = client.post(f"/offers/{offer['id']}/evaluate", json={"mode": "DETERMINISTIC"}).json()
    client.post(f"/offers/{offer['id']}/proposals/{proposal['id']}/approve")
    client.get(f"/offers/{offer['id']}/intelligence-profile")

    after = {path.name: path.read_text(encoding="utf-8") for path in rules_dir.glob("*.yaml")}
    assert after == before


def _create_offer(client: TestClient) -> dict:
    return client.post(
        "/offers",
        json={"name": "RobotStore.app", "offer_type": "DOMAIN_NAME"},
    ).json()
