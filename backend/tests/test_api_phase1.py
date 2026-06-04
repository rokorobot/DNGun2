from fastapi.testclient import TestClient

from backend.app.main import create_app


def test_phase1_prospect_signal_score_flow(tmp_path):
    client = TestClient(create_app(tmp_path / "test.sqlite3"))

    prospect_response = client.post(
        "/prospects",
        json={
            "company_name": "Northstar Automation",
            "segment": "AI_AUTOMATION",
            "website": "https://example.com",
        },
    )
    assert prospect_response.status_code == 201
    prospect = prospect_response.json()

    signal_response = client.post(
        f"/prospects/{prospect['id']}/signals",
        json={
            "signal_type": "Founder discussing growth",
            "tier": 1,
            "score": 5,
            "notes": "Founder posted about pipeline constraints",
        },
    )
    assert signal_response.status_code == 201

    score_response = client.post(f"/prospects/{prospect['id']}/score?persist=false")
    assert score_response.status_code == 200
    score = score_response.json()

    assert score["prospect_id"] == prospect["id"]
    assert score["base_score"] == 15
    assert score["alpha_matches"] == []
    assert score["final_score"] == 15
    assert score["decision"] == "IGNORE"
    assert score["explanation"][0]["impact"] == 15


def test_missing_prospect_returns_404(tmp_path):
    client = TestClient(create_app(tmp_path / "test.sqlite3"))

    response = client.post(
        "/prospects/P-MISSING/signals",
        json={"signal_type": "Hiring SDR", "tier": 1, "score": 5},
    )

    assert response.status_code == 404
