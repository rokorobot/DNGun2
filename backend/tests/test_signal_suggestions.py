from datetime import datetime, timedelta, timezone

import pytest

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

    def call(self, endpoint_id, *, method="GET", query=None, body=None, **_):
        self.calls += 1
        response = RESPONSES[endpoint_id]
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture(autouse=True)
def relaxed_treg_limits(monkeypatch):
    """Most tests re-run lookups back to back; the guard tests below tighten these."""
    monkeypatch.setenv("DNGUN_TREG_COOLDOWN_MINUTES", "0")
    monkeypatch.setenv("DNGUN_TREG_DAILY_BUDGET_USD", "100")


def _prospect(tmp_path):
    db = tmp_path / "suggest.sqlite3"
    api = TestClient(create_app(db), client=("127.0.0.1", 50000))
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


def test_save_domain_buyers_as_prospects(tmp_path):
    from backend.scripts.find_domain_buyers import main as find_main

    db, api, existing_id = _prospect(tmp_path)  # acme.io already exists
    serp = {"ads": [{"position": 2, "link": "https://acme.io/lp", "source": "Acme"},
                    {"position": 1, "link": "https://ai-automation-pros.com", "source": "AI Automation Pros"}],
            "organic_results": [{"position": 4, "link": "https://acme.io/blog", "title": "Acme blog"}]}

    class BuyerClient(FakeClient):
        def call(self, endpoint_id, *, method="GET", query=None, body=None, **_):
            self.calls += 1
            return {"treg.google.keywords.volume": {"output": {"rows": []}},
                    "serpapi.x.google-ads": serp,
                    "spyfu.google.domain.overview": {"results": [{"monthlyBudget": 1200}]}}[endpoint_id]

    argv = ["aiautomation.com", "-k", "ai automation", "--save", "5", "--segment", "AI_AUTOMATION", "--json"]
    assert find_main(argv, db_path=db, client=BuyerClient()) == 0

    prospects = {p["website"]: p for p in api.get("/prospects").json()}
    assert prospects["https://ai-automation-pros.com"]["company_name"] == "AI Automation Pros"
    assert len(prospects) == 2  # acme.io reused, not duplicated
    rows = _pending(db)
    assert rows["Buys ads on offer keyword"].tier == 1
    assert rows["Ranks for offer keyword"].prospect_id == existing_id
    assert "aiautomation.com" in rows["Brand overlaps offer keyword"].notes

    # Saving again adds no duplicates.
    assert find_main(argv, db_path=db, client=BuyerClient()) == 0
    session = create_session_factory(db)()
    assert session.query(models.SignalSuggestionModel).count() == 4
    session.close()


def test_save_requires_known_segment(tmp_path):
    from backend.scripts.find_domain_buyers import main as find_main

    db, _, _ = _prospect(tmp_path)
    assert find_main(["x.com", "-k", "x", "--save", "1", "--segment", "NOPE"], db_path=db, client=FakeClient()) == 2


def test_suggestion_api_run_list_review(tmp_path, monkeypatch):
    from backend.app import main as main_module

    db, api, prospect_id = _prospect(tmp_path)
    monkeypatch.setattr(main_module.TregClient, "from_env", classmethod(lambda cls: FakeClient()))

    run = api.post(f"/prospects/{prospect_id}/signal-suggestions/run")
    assert run.status_code == 200, run.text
    body = run.json()
    assert len(body["created"]) == 6 and body["already_known"] == 0
    assert any("upstream down" in w for w in body["warnings"])

    pending = api.get(f"/prospects/{prospect_id}/signal-suggestions").json()
    assert len(pending) == 6 and {s["status"] for s in pending} == {"PENDING"}
    hiring = next(s for s in pending if s["signal_type"] == "Hiring SDR")
    size = next(s for s in pending if s["signal_type"] == "Company size fit")

    approved = api.post(f"/signal-suggestions/{hiring['id']}/approve")
    assert approved.status_code == 200 and approved.json()["status"] == "APPROVED"
    assert approved.json()["signal_id"]
    assert api.post(f"/signal-suggestions/{size['id']}/reject").json()["status"] == "REJECTED"
    assert api.post(f"/signal-suggestions/{hiring['id']}/reject").status_code == 409
    assert api.post("/signal-suggestions/SS-missing/approve").status_code == 404

    assert [s["signal_type"] for s in api.get(f"/prospects/{prospect_id}/signals").json()] == ["Hiring SDR"]
    assert len(api.get(f"/prospects/{prospect_id}/signal-suggestions").json()) == 4
    assert len(api.get(f"/prospects/{prospect_id}/signal-suggestions?status=ALL").json()) == 6
    assert api.get("/prospects/P-missing/signal-suggestions").status_code == 404


def test_suggestion_api_run_without_token(tmp_path, monkeypatch):
    from backend.app import main as main_module

    _, api, prospect_id = _prospect(tmp_path)

    def no_token(cls):
        raise TregError("-", None, "TREG_TOKEN is not set")

    monkeypatch.setattr(main_module.TregClient, "from_env", classmethod(no_token))
    response = api.post(f"/prospects/{prospect_id}/signal-suggestions/run")
    assert response.status_code == 503


class PaidClient(FakeClient):
    """FakeClient that reports a spend, like the real client does from X-Treg-Cost-Micro."""
    spent_usd = 0.05


def test_run_guards_local_budget_cooldown_and_ledger(tmp_path, monkeypatch):
    from backend.app import main as main_module

    db, api, prospect_id = _prospect(tmp_path)
    monkeypatch.setattr(main_module.TregClient, "from_env", classmethod(lambda cls: PaidClient()))
    run = f"/prospects/{prospect_id}/signal-suggestions/run"

    # Not from this machine: a remote proxy hop, or a remote direct caller.
    assert api.post(run, headers={"X-Forwarded-For": "203.0.113.9"}).status_code == 403
    remote = TestClient(api.app, client=("203.0.113.9", 50000))
    assert remote.post(run).status_code == 403

    monkeypatch.setenv("DNGUN_TREG_COOLDOWN_MINUTES", "10")
    assert api.post(run, headers={"X-Forwarded-For": "127.0.0.1"}).status_code == 200
    second = api.post(run)
    assert second.status_code == 429 and "wait 10 min" in second.json()["detail"]

    session = create_session_factory(db)()
    ledger = session.query(models.TregSpendModel).all()
    session.close()
    assert [(r.source, r.prospect_id, r.spent_usd) for r in ledger] == [("api.suggest", prospect_id, 0.05)]

    monkeypatch.setenv("DNGUN_TREG_COOLDOWN_MINUTES", "0")
    monkeypatch.setenv("DNGUN_TREG_DAILY_BUDGET_USD", "0.10")  # 0.05 spent + 0.122 worst case > 0.10
    capped = api.post(run)
    assert capped.status_code == 429 and "daily treg budget" in capped.json()["detail"]

    # The CLI shares the same ledger and cap, with an explicit override.
    assert main([prospect_id], db_path=db, client=PaidClient()) == 3
    assert main([prospect_id, "--ignore-budget"], db_path=db, client=PaidClient()) == 0
