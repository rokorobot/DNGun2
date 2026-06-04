from fastapi.testclient import TestClient

from backend.app.database import create_session_factory
from backend.app.main import create_app
from backend.app.seed import seed_mvp0


def seeded_client(tmp_path) -> TestClient:
    db_path = tmp_path / "mvp01.sqlite3"
    session_factory = create_session_factory(db_path)
    with session_factory() as session:
        seed_mvp0(session)
    return TestClient(create_app(db_path))


def test_seed_data_loads(tmp_path):
    client = seeded_client(tmp_path)

    prospects = client.get("/prospects").json()
    alpha_signals = client.get("/alpha-signals").json()
    outcomes = client.get("/campaign-outcomes").json()

    assert len(prospects) == 25
    assert len(alpha_signals) == 3
    assert len(outcomes) == 25


def test_campaign_intelligence_report_computes_expected_rates(tmp_path):
    client = seeded_client(tmp_path)

    report = client.get("/reports/campaign-intelligence").json()

    assert report["total_prospects"] == 25
    assert report["contacted_count"] == 25
    assert report["reply_rate"] == 0.32
    assert report["call_booked_rate"] == 0.16
    assert report["proposal_requested_rate"] == 0.08
    assert report["paid_pilot_rate"] == 0.04
    assert report["evidence_entries_created"] == 2
    assert report["confidence_before"] == 40
    assert report["confidence_after"] == 43
    assert report["confidence_delta"] == 3


def test_score_band_performance_works(tmp_path):
    client = seeded_client(tmp_path)

    score_bands = client.get("/reports/campaign-intelligence").json()[
        "performance_by_score_band"
    ]

    assert score_bands["CONTACT_NOW"]["contacted_count"] == 10
    assert score_bands["CONTACT_NOW"]["reply_rate"] == 0.8
    assert score_bands["CONTACT_NOW"]["call_booked_rate"] == 0.4
    assert score_bands["SECONDARY"]["contacted_count"] == 8
    assert score_bands["SECONDARY"]["reply_rate"] == 0
    assert score_bands["IGNORE"]["contacted_count"] == 7


def test_alpha_signal_performance_works(tmp_path):
    client = seeded_client(tmp_path)

    alpha_signals = client.get("/reports/campaign-intelligence").json()[
        "performance_by_alpha_signal"
    ]

    assert alpha_signals["AS-001"]["contacted_count"] == 10
    assert alpha_signals["AS-001"]["reply_rate"] == 0.8
    assert alpha_signals["AS-004"]["contacted_count"] == 8
    assert alpha_signals["AS-004"]["reply_rate"] == 0
    assert alpha_signals["AS-010"]["contacted_count"] == 4
    assert alpha_signals["AS-010"]["reply_rate"] == 0


def test_markdown_export_contains_key_metrics(tmp_path):
    client = seeded_client(tmp_path)

    response = client.get("/reports/campaign-intelligence.md")

    assert response.status_code == 200
    markdown = response.text
    assert "# DNGun Campaign Intelligence Report" in markdown
    assert "Total prospects: 25" in markdown
    assert "Reply rate: 32.0%" in markdown
    assert "Performance By Score Band" in markdown
    assert "AS-001" in markdown
    assert "Confidence after: 43" in markdown
