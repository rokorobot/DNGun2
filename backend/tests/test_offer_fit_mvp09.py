from fastapi.testclient import TestClient

from backend.app.main import create_app


def test_no_approved_profile_returns_controlled_error(tmp_path):
    client = TestClient(create_app(tmp_path / "fit.sqlite3"))
    offer = client.post("/offers", json={"name": "RobotStore.app"}).json()

    response = client.post(f"/offers/{offer['id']}/fit/prospects")

    assert response.status_code == 409
    assert response.json()["detail"] == "Approved offer profile required"


def test_fit_calculation_ranks_matching_segment_higher(tmp_path):
    client = TestClient(create_app(tmp_path / "fit.sqlite3"))
    offer = _approved_robotics_offer(client)
    strong = client.post(
        "/prospects",
        json={
            "company_name": "Warehouse Automation Co",
            "segment": "AI_AUTOMATION",
            "contact_path": "Founder LinkedIn",
        },
    ).json()
    weak = client.post(
        "/prospects",
        json={"company_name": "SEO Content Shop", "segment": "SEO"},
    ).json()

    fits = client.post(f"/offers/{offer['id']}/fit/prospects").json()
    ranked = {fit["prospect_id"]: fit for fit in fits}

    assert ranked[strong["id"]]["segment_fit_score"] > ranked[weak["id"]]["segment_fit_score"]
    assert fits[0]["prospect_id"] == strong["id"]


def test_fit_calculation_rewards_matching_signals(tmp_path):
    client = TestClient(create_app(tmp_path / "fit.sqlite3"))
    offer = _approved_robotics_offer(client)
    prospect = client.post(
        "/prospects",
        json={"company_name": "Robot Distributor", "segment": "AI_AUTOMATION"},
    ).json()
    client.post(
        f"/prospects/{prospect['id']}/signals",
        json={"signal_type": "Robotics hiring", "tier": 1, "score": 5},
    )

    fit = client.post(f"/offers/{offer['id']}/fit/prospects").json()[0]

    assert fit["prospect_id"] == prospect["id"]
    assert fit["signal_fit_score"] >= 18
    assert fit["total_fit_score"] >= 40
    assert any("Robotics hiring" in item for item in fit["explanation"])


def test_disqualifier_overrides_decision(tmp_path):
    client = TestClient(create_app(tmp_path / "fit.sqlite3"))
    offer = _approved_robotics_offer(client)
    prospect = client.post(
        "/prospects",
        json={"company_name": "Bad Fit Robotics", "segment": "AI_AUTOMATION"},
    ).json()
    client.post(
        f"/prospects/{prospect['id']}/signals",
        json={"signal_type": "Disqualifier: no budget", "tier": 1, "score": 5},
    )

    fit = client.post(f"/offers/{offer['id']}/fit/prospects").json()[0]

    assert fit["decision"] == "DISQUALIFIED"
    assert fit["total_fit_score"] == 0


def test_get_returns_ranked_fits(tmp_path):
    client = TestClient(create_app(tmp_path / "fit.sqlite3"))
    offer = _approved_robotics_offer(client)
    first = client.post(
        "/prospects",
        json={"company_name": "Robot Distributor", "segment": "AI_AUTOMATION"},
    ).json()
    client.post(
        f"/prospects/{first['id']}/signals",
        json={"signal_type": "Robotics hiring", "tier": 1, "score": 5},
    )
    client.post(
        "/prospects",
        json={"company_name": "General SEO", "segment": "SEO"},
    )

    client.post(f"/offers/{offer['id']}/fit/prospects")
    fits = client.get(f"/offers/{offer['id']}/fit/prospects").json()

    assert len(fits) == 2
    assert fits[0]["total_fit_score"] >= fits[1]["total_fit_score"]
    assert fits[0]["prospect_id"] == first["id"]


def _approved_robotics_offer(client: TestClient) -> dict:
    offer = client.post("/offers", json={"name": "RobotStore.app"}).json()
    proposal = client.post(
        f"/offers/{offer['id']}/evaluate",
        json={"mode": "DETERMINISTIC"},
    ).json()
    client.post(f"/offers/{offer['id']}/proposals/{proposal['id']}/approve")
    return offer
