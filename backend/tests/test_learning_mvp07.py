from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.database import create_session_factory
from backend.app.main import create_app
from backend.app.seed import seed_mvp0


def seeded_client(tmp_path) -> TestClient:
    db_path = tmp_path / "learning.sqlite3"
    session_factory = create_session_factory(db_path)
    with session_factory() as session:
        seed_mvp0(session)
    return TestClient(create_app(db_path))


def test_signal_performance_aggregates_campaign_outcomes(tmp_path):
    client = seeded_client(tmp_path)

    signals = client.get("/learning/signals").json()
    growth = _by_key(signals, "signalType")["Founder discusses growth"]

    assert growth["timesSeen"] == 10
    assert growth["contacted"] == 10
    assert growth["replied"] == 8
    assert growth["callBooked"] == 4
    assert growth["proposalRequested"] == 2
    assert growth["paidPilot"] == 1
    assert growth["replyRate"] == 0.8
    assert growth["pilotRate"] == 0.1
    assert growth["confidence"] == "LOW"
    assert growth["recommendation"] == "INCREASE_WEIGHT"


def test_alpha_signal_performance_aggregates_campaign_outcomes(tmp_path):
    client = seeded_client(tmp_path)

    alpha_signals = client.get("/learning/alpha-signals").json()
    growth_pressure = _by_key(alpha_signals, "code")["AS-001"]

    assert growth_pressure["name"] == "Growth Pressure"
    assert growth_pressure["timesMatched"] == 10
    assert growth_pressure["contacted"] == 10
    assert growth_pressure["replied"] == 8
    assert growth_pressure["paidPilot"] == 1
    assert growth_pressure["replyRate"] == 0.8
    assert growth_pressure["pilotRate"] == 0.1
    assert growth_pressure["confidence"] == "LOW"
    assert growth_pressure["recommendation"] == "VALIDATE"


def test_confidence_uses_contacted_count_not_times_seen(tmp_path):
    client = TestClient(create_app(tmp_path / "low_contacted.sqlite3"))
    batch = client.post("/campaign-batches", json={"name": "Low Contacted"}).json()

    for index in range(6):
        prospect = client.post(
            "/prospects",
            json={"company_name": f"Low Contact {index}", "segment": "SEO"},
        ).json()
        client.post(
            f"/prospects/{prospect['id']}/signals",
            json={"signal_type": "High seen low contacted", "tier": 1, "score": 5},
        )
        client.post(f"/campaign-batches/{batch['id']}/prospects/{prospect['id']}")
        if index < 3:
            client.post(
                "/campaign-outcomes",
                json={
                    "campaign_batch_id": batch["id"],
                    "prospect_id": prospect["id"],
                    "contacted": True,
                    "replied": True,
                    "call_booked": True,
                },
            )

    signals = client.get("/learning/signals").json()
    row = _by_key(signals, "signalType")["High seen low contacted"]

    assert row["timesSeen"] == 6
    assert row["contacted"] == 3
    assert row["replyRate"] == 1
    assert row["confidence"] == "INSUFFICIENT_DATA"
    assert row["recommendation"] == "COLLECT_MORE_DATA"


def test_score_band_validation_works(tmp_path):
    client = seeded_client(tmp_path)

    summary = client.get("/learning/summary").json()
    bands = _by_key(summary["scoreBandValidation"], "scoreBand")

    assert bands["CONTACT_NOW"]["prospectsInBand"] == 10
    assert bands["CONTACT_NOW"]["contacted"] == 10
    assert bands["CONTACT_NOW"]["replyRate"] == 0.8
    assert bands["CONTACT_NOW"]["pilotRate"] == 0.1
    assert bands["CONTACT_NOW"]["recommendation"] == "VALIDATED_BAND"


def test_learning_summary_recommendations_and_markdown(tmp_path):
    client = seeded_client(tmp_path)

    summary = client.get("/learning/summary").json()
    markdown = client.get("/learning/report.md")

    assert summary["topPerformingSignals"]
    assert summary["topAlphaSignals"]
    assert summary["scoreBandValidation"]
    assert any("Founder discusses growth" in item for item in summary["recommendedRuleChanges"])
    assert markdown.status_code == 200
    assert "# DNGun Learning Intelligence Report" in markdown.text
    assert "Top Performing Signals" in markdown.text
    assert "Weak Signals" in markdown.text
    assert "Top Alpha Signals" in markdown.text
    assert "Weak Alpha Signals" in markdown.text
    assert "Score Band Validation" in markdown.text
    assert "Recommended Rule Changes" in markdown.text


def test_learning_endpoints_do_not_modify_rule_files(tmp_path):
    client = seeded_client(tmp_path)
    rules_dir = Path("backend/app/rules")
    before = {
        path.name: path.read_text(encoding="utf-8")
        for path in rules_dir.glob("*.yaml")
    }

    client.get("/learning/signals")
    client.get("/learning/alpha-signals")
    client.get("/learning/summary")
    client.get("/learning/report.md")

    after = {
        path.name: path.read_text(encoding="utf-8")
        for path in rules_dir.glob("*.yaml")
    }
    assert after == before


def _by_key(rows: list[dict], key: str) -> dict[str, dict]:
    return {row[key]: row for row in rows}


def test_wilson_ranking_and_scoping(tmp_path):
    client = seeded_client(tmp_path)

    # 1. Verify Wilson Rank fields are populated
    signals = client.get("/learning/signals").json()
    assert len(signals) > 0
    first_sig = signals[0]
    assert "replyRateRank" in first_sig
    assert "pilotRateRank" in first_sig
    assert "confidenceRank" in first_sig

    # Assert they are floats
    assert isinstance(first_sig["replyRateRank"], float)
    assert isinstance(first_sig["confidenceRank"], float)

    # Verify sorted order of signals by confidenceRank descending
    ranks = [s["confidenceRank"] for s in signals]
    assert ranks == sorted(ranks, reverse=True)

    # 2. Verify Scoping query params return filtered results
    ai_signals = client.get("/learning/signals?pdm_code=AI-AUTOMATION").json()
    assert isinstance(ai_signals, list)

    # Let's request with a dummy pdm_code that doesn't exist
    empty_signals = client.get("/learning/signals?pdm_code=NON_EXISTENT_PDM").json()
    assert len(empty_signals) == 0

