from fastapi.testclient import TestClient

from backend.app.main import create_app


def test_mvp0_learning_loop_resources(tmp_path):
    client = TestClient(create_app(tmp_path / "mvp0.sqlite3"))

    prospect = client.post(
        "/prospects",
        json={
            "company_name": "Pipeline Systems Co",
            "segment": "REVOPS",
            "founder_name": "Avery Founder",
        },
    ).json()

    client.post(
        f"/prospects/{prospect['id']}/signals",
        json={
            "signal_type": "Founder discusses pipeline",
            "tier": 1,
            "score": 5,
        },
    )

    alpha_signal = client.post(
        "/alpha-signals",
        json={
            "code": "AS-010",
            "name": "Founder ROI Awareness",
            "required_signals": ["Founder discusses pipeline"],
            "bonus_score": 15,
        },
    ).json()

    assignment_response = client.post(
        f"/prospects/{prospect['id']}/alpha-signals/{alpha_signal['id']}",
        json={"notes": "Manual MVP 0 match"},
    )
    assert assignment_response.status_code == 201

    score = client.post(f"/prospects/{prospect['id']}/score?persist=false").json()
    assert score["base_score"] == 15
    assert score["alpha_matches"] == ["AS-010"]
    assert score["alpha_bonus"] == 15
    assert score["final_score"] == 30
    assert score["explanation"][1]["source_type"] == "ALPHA_SIGNAL"

    campaign_batch = client.post(
        "/campaign-batches",
        json={"name": "RevOps MVP Batch 1", "segment": "REVOPS"},
    ).json()

    batch_link = client.post(
        f"/campaign-batches/{campaign_batch['id']}/prospects/{prospect['id']}"
    )
    assert batch_link.status_code == 201

    outcome = client.post(
        "/campaign-outcomes",
        json={
            "campaign_batch_id": campaign_batch["id"],
            "prospect_id": prospect["id"],
            "contacted": True,
            "replied": True,
            "call_booked": True,
            "outcome_notes": "Positive reply from founder",
        },
    ).json()
    assert outcome["replied"] is True

    evidence = client.post(
        "/evidence-entries",
        json={
            "evidence_type": "Campaign Outcome",
            "evidence": "RevOps prospect replied and booked a call.",
            "impact": 1,
            "source": outcome["id"],
        },
    ).json()

    confidence = client.post(
        "/confidence-updates",
        json={
            "evidence_entry_id": evidence["id"],
            "confidence_before": 40,
            "evidence_impact": 2,
            "confidence_after": 42,
            "reason": "Positive reply supports RevOps PDM hypothesis.",
        },
    ).json()
    assert confidence["confidence_after"] == 42


def test_duplicate_alpha_signal_assignment_does_not_double_count_bonus(tmp_path):
    client = TestClient(create_app(tmp_path / "mvp0.sqlite3"))

    prospect = client.post(
        "/prospects",
        json={"company_name": "AI Pipeline Lab", "segment": "AI_AUTOMATION"},
    ).json()
    alpha_signal = client.post(
        "/alpha-signals",
        json={"code": "AS-001", "name": "Growth Pressure", "bonus_score": 15},
    ).json()

    first = client.post(
        f"/prospects/{prospect['id']}/alpha-signals/{alpha_signal['id']}"
    )
    duplicate = client.post(
        f"/prospects/{prospect['id']}/alpha-signals/{alpha_signal['id']}"
    )
    score = client.post(f"/prospects/{prospect['id']}/score?persist=false").json()

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert score["alpha_matches"] == ["AS-001"]
    assert score["alpha_bonus"] == 15


def test_duplicate_campaign_batch_prospect_is_rejected(tmp_path):
    client = TestClient(create_app(tmp_path / "mvp0.sqlite3"))

    prospect = client.post(
        "/prospects",
        json={"company_name": "SEO Proof Co", "segment": "SEO"},
    ).json()
    campaign_batch = client.post(
        "/campaign-batches",
        json={"name": "SEO Batch", "segment": "SEO"},
    ).json()

    first = client.post(
        f"/campaign-batches/{campaign_batch['id']}/prospects/{prospect['id']}"
    )
    duplicate = client.post(
        f"/campaign-batches/{campaign_batch['id']}/prospects/{prospect['id']}"
    )

    assert first.status_code == 201
    assert duplicate.status_code == 409


def test_campaign_batch_prospects_can_be_listed_and_outcome_updated(tmp_path):
    client = TestClient(create_app(tmp_path / "mvp0.sqlite3"))

    prospect = client.post(
        "/prospects",
        json={"company_name": "Outcome Workbench Co", "segment": "AI_AUTOMATION"},
    ).json()
    campaign_batch = client.post(
        "/campaign-batches",
        json={"name": "AI Automation Batch", "segment": "AI_AUTOMATION"},
    ).json()
    client.post(f"/campaign-batches/{campaign_batch['id']}/prospects/{prospect['id']}")

    batch_prospects = client.get(
        f"/campaign-batches/{campaign_batch['id']}/prospects"
    )
    assert batch_prospects.status_code == 200
    assert batch_prospects.json()[0]["prospect_id"] == prospect["id"]

    outcome = client.post(
        "/campaign-outcomes",
        json={
            "campaign_batch_id": campaign_batch["id"],
            "prospect_id": prospect["id"],
            "contacted": True,
        },
    ).json()
    updated = client.put(
        f"/campaign-outcomes/{outcome['id']}",
        json={
            "campaign_batch_id": campaign_batch["id"],
            "prospect_id": prospect["id"],
            "contacted": True,
            "replied": True,
            "call_booked": True,
            "outcome_notes": "Founder replied and booked discovery.",
        },
    )

    assert updated.status_code == 200
    assert updated.json()["replied"] is True
    outcomes = client.get(
        f"/campaign-outcomes?campaign_batch_id={campaign_batch['id']}"
    ).json()
    assert len(outcomes) == 1
    assert outcomes[0]["outcome_notes"] == "Founder replied and booked discovery."


def test_campaign_outcome_requires_existing_batch_and_prospect(tmp_path):
    client = TestClient(create_app(tmp_path / "mvp0.sqlite3"))

    response = client.post(
        "/campaign-outcomes",
        json={
            "campaign_batch_id": "CB-MISSING",
            "prospect_id": "P-MISSING",
            "contacted": True,
        },
    )

    assert response.status_code == 404


def test_campaign_outcome_requires_prospect_membership(tmp_path):
    client = TestClient(create_app(tmp_path / "mvp0.sqlite3"))

    prospect = client.post(
        "/prospects",
        json={"company_name": "Webflow Growth Studio", "segment": "WEBFLOW"},
    ).json()
    campaign_batch = client.post(
        "/campaign-batches",
        json={"name": "Webflow Batch", "segment": "WEBFLOW"},
    ).json()

    response = client.post(
        "/campaign-outcomes",
        json={
            "campaign_batch_id": campaign_batch["id"],
            "prospect_id": prospect["id"],
            "contacted": True,
        },
    )

    assert response.status_code == 400


def test_persisted_score_stores_retrievable_explanations(tmp_path):
    client = TestClient(create_app(tmp_path / "mvp0.sqlite3"))

    prospect = client.post(
        "/prospects",
        json={"company_name": "RevOps Signals", "segment": "REVOPS"},
    ).json()
    client.post(
        f"/prospects/{prospect['id']}/signals",
        json={"signal_type": "Founder discusses CAC", "tier": 1, "score": 5},
    )
    alpha_signal = client.post(
        "/alpha-signals",
        json={"code": "AS-010", "name": "Founder ROI Awareness", "bonus_score": 15},
    ).json()
    client.post(f"/prospects/{prospect['id']}/alpha-signals/{alpha_signal['id']}")

    score_response = client.post(f"/prospects/{prospect['id']}/score")
    scores_response = client.get(f"/prospects/{prospect['id']}/scores")

    assert score_response.status_code == 200
    assert scores_response.status_code == 200
    scores = scores_response.json()
    assert len(scores) == 1
    assert scores[0]["id"].startswith("PS-")
    assert scores[0]["base_score"] == 15
    assert scores[0]["alpha_bonus"] == 15
    assert [item["source_type"] for item in scores[0]["explanation"]] == [
        "SIGNAL",
        "ALPHA_SIGNAL",
    ]

    score_by_id = client.get(f"/scores/{scores[0]['id']}")
    assert score_by_id.status_code == 200
    assert score_by_id.json()["explanation"][0]["source_code"] == "Founder discusses CAC"


def test_invalid_inputs_return_422(tmp_path):
    client = TestClient(create_app(tmp_path / "mvp0.sqlite3"))

    prospect = client.post(
        "/prospects",
        json={"company_name": "Bad Input Co", "segment": "SEO"},
    ).json()

    invalid_tier = client.post(
        f"/prospects/{prospect['id']}/signals",
        json={"signal_type": "Invalid tier", "tier": 4, "score": 5},
    )
    invalid_score = client.post(
        f"/prospects/{prospect['id']}/signals",
        json={"signal_type": "Invalid score", "tier": 1, "score": 6},
    )
    invalid_confidence = client.post(
        "/confidence-updates",
        json={
            "confidence_before": 101,
            "evidence_impact": 1,
            "confidence_after": 50,
            "reason": "Out of range",
        },
    )

    assert invalid_tier.status_code == 422
    assert invalid_score.status_code == 422
    assert invalid_confidence.status_code == 422


def test_duplicate_alpha_signal_code_returns_409(tmp_path):
    client = TestClient(create_app(tmp_path / "mvp0.sqlite3"))

    first = client.post(
        "/alpha-signals",
        json={"code": "AS-001", "name": "Growth Pressure", "bonus_score": 15},
    )
    duplicate = client.post(
        "/alpha-signals",
        json={"code": "AS-001", "name": "Duplicate", "bonus_score": 10},
    )

    assert first.status_code == 201
    assert duplicate.status_code == 409


def test_missing_evidence_entry_in_confidence_update_returns_404(tmp_path):
    client = TestClient(create_app(tmp_path / "mvp0.sqlite3"))

    response = client.post(
        "/confidence-updates",
        json={
            "evidence_entry_id": "EV-MISSING",
            "confidence_before": 40,
            "evidence_impact": 1,
            "confidence_after": 41,
            "reason": "Missing evidence should fail",
        },
    )

    assert response.status_code == 404
