from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.app import models
from backend.app.database import create_session_factory
from backend.app.main import create_app
from backend.app.signal_suggestions import parse_headcount
from backend.app.treg_client import TregError
from backend.scripts.suggest_signals import main

RECENT = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
OLD = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()

# Payload shapes captured from live treg responses (crawl4ai, predictleads, akta, fetchinio, seranking).
RESPONSES = {
    "treg.companies.enrich": {"output": {"name": "Acme", "employees": "11-50", "industry": "Marketing"},
                              "_treg": {"served_by": "crawl4ai.companies.enrich", "outcome": "hit"}},
    "treg.companies.jobs.search": {"output": {"jobs": [
        {"type": "job_opening", "attributes": {"title": "Sales Development Representative",
                                               "url": "https://acme.io/jobs/1"}},
        {"attributes": {"title": "Senior Designer", "url": "https://acme.io/jobs/2"}},
    ]}, "_treg": {"served_by": "predictleads.companies.job_openings", "outcome": "hit"}},
    "treg.companies.news": {"output": {"articles": [
        {"title": "Acme launches new AI automation service", "url": "https://news.example/1",
         "published_date": RECENT, "ai_summary": "Acme announced a new offering."},
        {"title": "Acme launches old thing", "url": "https://news.example/0", "published_date": OLD},
    ]}, "_treg": {"served_by": "akta.companies.news", "outcome": "hit"}},
    "treg.linkedin.user.posts": {"output": {"posts": [
        {"id": "urn:li:activity:1", "content": "Most of our clients come from referrals. Time to fix our pipeline.",
         "date": RECENT, "profile": {"url": "https://www.linkedin.com/in/founder"}},
        {"id": "urn:li:activity:2", "content": "We are growing fast — revenue doubled this year.", "date": RECENT},
    ]}, "_treg": {"served_by": "fetchinio.linkedin.user.posts", "outcome": "hit"}},
    "treg.people.email.find": {"output": {"email": None},
                               "_treg": {"served_by": "dropcontact.people.email.find", "outcome": "pending"}},
    "treg.web.url.metrics": TregError("treg.web.url.metrics", 502, "upstream down"),
}


class FakeClient:
    calls = 0
    spent_usd = 0.0

    def call(self, endpoint_id, *, method="GET", query=None, body=None):
        self.calls += 1
        response = RESPONSES[endpoint_id]
        if isinstance(response, Exception):
            raise response
        return response


def _prospect(tmp_path):
    db = tmp_path / "suggest.sqlite3"
    api = TestClient(create_app(db))
    response = api.post("/prospects", json={
        "company_name": "Acme", "website": "https://www.acme.io", "segment": "AI_AUTOMATION",
        "founder_name": "Jane Doe", "founder_linkedin": "https://www.linkedin.com/in/founder"})
    assert response.status_code == 201, response.text
    return db, api, response.json()["id"]


def _pending(db):
    session = create_session_factory(db)()
    rows = {s.signal_type: s for s in session.query(models.SignalSuggestionModel).all()}
    session.close()
    return rows


def test_parse_headcount():
    assert parse_headcount(20) == 20
    assert parse_headcount("11-50") == 30
    assert parse_headcount("1,001-5,000 employees") == 3000
    assert parse_headcount(None) is None


def test_suggest_store_dedupe_and_review(tmp_path, capsys):
    db, api, prospect_id = _prospect(tmp_path)

    assert main([prospect_id], db_path=db, client=FakeClient()) == 0
    rows = _pending(db)
    assert set(rows) == {"Company size fit", "Hiring SDR", "New service launch", "Founder mentions referrals",
                         "Founder discusses pipeline", "Founder discusses growth"}
    assert rows["Hiring SDR"].source_url == "https://acme.io/jobs/1" and rows["Hiring SDR"].tier == 1
    assert rows["New service launch"].source_url == "https://news.example/1"
    assert rows["Founder mentions referrals"].source_url == "https://www.linkedin.com/feed/update/urn:li:activity:1/"
    assert rows["Company size fit"].score == 4
    assert all(r.status == "PENDING" for r in rows.values())
    err = capsys.readouterr().err
    assert "upstream down" in err and "asynchronously" in err
    assert api.get(f"/prospects/{prospect_id}/signals").json() == []  # nothing scored until approved

    # Re-running proposes nothing new.
    assert main([prospect_id], db_path=db, client=FakeClient()) == 0
    assert len(_pending(db)) == 6

    approve_id, reject_id = rows["Hiring SDR"].id, rows["Company size fit"].id
    assert main(["--approve", approve_id], db_path=db) == 0
    assert main(["--reject", reject_id], db_path=db) == 0
    assert main(["--approve", reject_id], db_path=db) == 1  # already reviewed

    signals = api.get(f"/prospects/{prospect_id}/signals").json()
    assert [(s["signal_type"], s["tier"], s["score"]) for s in signals] == [("Hiring SDR", 1, 4)]
    assert "via treg: predictleads.companies.job_openings" in signals[0]["notes"]

    # Rejected and approved suggestions stay out on the next run.
    assert main([prospect_id], db_path=db, client=FakeClient()) == 0
    statuses = {t: r.status for t, r in _pending(db).items()}
    assert statuses["Hiring SDR"] == "APPROVED" and statuses["Company size fit"] == "REJECTED"
    assert len(statuses) == 6
