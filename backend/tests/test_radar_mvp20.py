"""MVP 2.0 Opportunity Radar: portfolio import, watch profiles, matching, review."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.radar import (
    build_queries,
    build_watch_profile,
    extract_company,
    match_headline,
    parse_portfolio,
    segment_words,
)

# --- Pure engine ------------------------------------------------------------


def test_parse_portfolio_handles_lists_csv_and_bad_rows():
    rows, invalid = parse_portfolio("RobotStore.app\nhttps://www.SolarLease.de/path\nrobotstore.app\nnope\n")
    assert [r["domain"] for r in rows] == ["robotstore.app", "solarlease.de"]  # deduped, normalised
    assert invalid == ["nope"]

    rows, _ = parse_portfolio('domain;price;markets;notes\ndronefleet.io;6 500 €;US, DACH;fleet\n')
    assert rows[0]["price"] == 6500.0
    assert rows[0]["markets"] == ["US", "DACH"]
    assert rows[0]["notes"] == "fleet"


def test_watch_profile_from_name_and_ending():
    assert segment_words("robotstore", {"robot", "store"}) == ["robot", "store"]
    profile = build_watch_profile("robotstore.app")
    assert profile["keywords"] == ["robotstore", "robot", "store"]
    assert profile["markets"] == ["GLOBAL"]
    assert profile["origin"] == "AUTO"

    # Offers created elsewhere may keep mixed case; matching is case-insensitive.
    assert build_watch_profile("RobotStore.App")["keywords"] == ["robotstore", "robot", "store"]
    assert match_headline("RobotStore raises seed", "RobotStore.App", profile).match_type == "NAME"
    # Finance words split; generic words help splitting but are not searched.
    assert build_watch_profile("StockExchange.xyz")["keywords"] == ["stockexchange", "stock", "exchange"]
    assert build_watch_profile("bestmortgagerates.com")["keywords"] == ["bestmortgagerates", "mortgage", "rates"]
    assert build_watch_profile("solarlease.de")["markets"] == ["DE"]
    assert build_watch_profile("petinsure.co.uk")["markets"] == ["GB"]
    custom = build_watch_profile("robotstore.app", markets=["DACH", "us"], keywords=["Robotics"])
    assert custom["markets"] == ["DE", "AT", "CH", "US"]
    assert custom["keywords"] == ["robotics"]
    assert custom["origin"] == "MANUAL"
    with pytest.raises(ValueError):
        build_watch_profile("robotstore.app", markets=["MARS"])


def test_queries_follow_market_country_and_language():
    queries = build_queries(build_watch_profile("solarlease.de"))
    assert len(queries) == 1
    assert "sourcecountry:germany" in queries[0]["query"]
    assert "finanzierung" in queries[0]["query"]  # German event words added
    assert "raises" in queries[0]["query"]  # English always included
    assert "sourcecountry" not in build_queries(build_watch_profile("robotstore.app"))[0]["query"]


@pytest.mark.parametrize(
    "title, expected",
    [
        ("RobotStore raises $4M seed to sell warehouse robots", ("NAME", "FUNDING", "RobotStore")),
        ("Robot Store expands into Germany", ("NAME", "EXPANSION", "Robot Store")),
        ("Exclusive: Italian robotics startup Mosaico raises €7.5m - Sifted", ("KEYWORD", "FUNDING", "Mosaico")),
        ("Robotics stocks fall on tariff fears", None),  # topical, no company event
        ("Amazon launches new store format", None),  # weak single keyword
    ],
)
def test_headline_matching(title, expected):
    match = match_headline(title, "robotstore.app", build_watch_profile("robotstore.app"))
    if expected is None:
        assert match is None
    else:
        assert (match.match_type, match.event_type, match.company_name) == expected
        assert match.explanation[-1].startswith("Match score")


def test_name_match_outranks_keyword_match():
    profile = build_watch_profile("robotstore.app")
    name = match_headline("RobotStore raises seed", "robotstore.app", profile)
    keyword = match_headline("Robotics startup Acme raises seed", "robotstore.app", profile)
    assert name.score > keyword.score


def test_extract_company_without_verb_returns_none():
    assert extract_company("Weekly robotics roundup") is None


# --- API --------------------------------------------------------------------

ARTICLES = [
    {"url": "https://news.example/a", "title": "RobotStore raises $4M seed round",
     "source_domain": "news.example", "source_country": "United States", "language": "English",
     "published_at": "2026-11-20T10:00:00+00:00"},
    {"url": "https://news.example/b", "title": "Robotics stocks fall on tariff fears",
     "source_domain": "news.example", "source_country": "United States", "language": "English",
     "published_at": "2026-11-20T11:00:00+00:00"},
]


def _client(tmp_path, articles=ARTICLES, fail=False):
    calls = []

    def fake_fetch(query, *, timespan, max_records):
        calls.append(query)
        if fail:
            raise RuntimeError("GDELT: rate limited")
        return articles

    client = TestClient(create_app(tmp_path / "radar.sqlite3", radar_fetch=fake_fetch, radar_interval=0))
    return client, calls


def test_import_list_and_edit_profile(tmp_path):
    client, _ = _client(tmp_path)
    result = client.post(
        "/portfolio/import",
        json={"text": "domain;price;markets\nrobotstore.app;12000;\nsolarlease.de;;DACH\nbad;;\nx.de;;MARS\n"},
    ).json()
    assert result["created"] == ["robotstore.app", "solarlease.de"]
    assert result["invalid"][0] == "bad" and "MARS" in result["invalid"][1]

    again = client.post("/portfolio/import", json={"text": "robotstore.app"}).json()
    assert again == {"created": [], "updated": ["robotstore.app"], "invalid": []}  # no duplicate

    portfolio = {row["domain"]: row for row in client.get("/portfolio").json()}
    assert portfolio["robotstore.app"]["price"] == 12000
    assert portfolio["solarlease.de"]["markets"] == ["DE", "AT", "CH"]

    oid = portfolio["robotstore.app"]["offer_id"]
    edited = client.put(
        f"/portfolio/{oid}/profile", json={"keywords": ["robot", "warehouse"], "markets": ["US"]}
    ).json()
    assert edited["keywords"] == ["robot", "warehouse"] and edited["markets"] == ["US"]
    assert client.put(f"/portfolio/{oid}/profile", json={"keywords": [" "]}).status_code == 409
    assert client.put(f"/portfolio/{oid}/profile", json={"keywords": ["x1x"], "markets": ["MARS"]}).status_code == 409
    assert client.put("/portfolio/O-MISSING/profile", json={"keywords": ["robot"]}).status_code == 404


def test_scan_creates_only_matching_opportunities_once(tmp_path):
    client, calls = _client(tmp_path)
    client.post("/portfolio/import", json={"text": "robotstore.app"})

    summary = client.post("/radar/scan").json()
    assert summary == {"domains": 1, "queries": 1, "articles": 2, "new_opportunities": 1, "errors": []}
    assert calls and "robotstore" in calls[0]

    opportunities = client.get("/opportunities").json()
    assert len(opportunities) == 1
    opp = opportunities[0]
    assert opp["domain"] == "robotstore.app"
    assert opp["company_name"] == "RobotStore"
    assert opp["match_type"] == "NAME" and opp["event_type"] == "FUNDING"
    assert opp["news"]["url"] == "https://news.example/a"

    assert client.post("/radar/scan").json()["new_opportunities"] == 0  # rescans dedupe
    assert client.get("/portfolio").json()[0]["new_opportunities"] == 1


def test_scan_errors_are_reported_not_fatal(tmp_path):
    client, _ = _client(tmp_path, fail=True)
    client.post("/portfolio/import", json={"text": "robotstore.app\ndronefleet.io"})

    summary = client.post("/radar/scan").json()

    assert summary["domains"] == 2 and summary["new_opportunities"] == 0
    assert len(summary["errors"]) == 2 and "rate limited" in summary["errors"][0]


def test_accept_creates_prospect_signal_and_evidence(tmp_path):
    client, _ = _client(tmp_path)
    client.post("/portfolio/import", json={"text": "robotstore.app"})
    client.post("/radar/scan")
    opp = client.get("/opportunities").json()[0]

    assert client.post(
        f"/opportunities/{opp['id']}/accept", json={"company_name": "RobotStore Inc", "segment": "NOPE"}
    ).status_code == 409
    accepted = client.post(
        f"/opportunities/{opp['id']}/accept",
        json={"company_name": "RobotStore Inc", "segment": "ROBOTICS", "website": "getrobotstore.io"},
    ).json()

    assert accepted["status"] == "ACCEPTED"
    prospect = client.get(f"/prospects/{accepted['prospect_id']}").json()
    assert prospect["company_name"] == "RobotStore Inc" and prospect["segment"] == "ROBOTICS"
    signal = client.get(f"/prospects/{prospect['id']}/signals").json()[0]
    assert signal["tier"] == 1 and signal["score"] == 5
    assert signal["source_url"] == "https://news.example/a"
    evidence = client.get("/evidence-entries", params={"offer_id": opp["offer_id"]}).json()
    assert evidence[0]["source"] == "https://news.example/a"
    # Scored by the existing engine: tier-1 signal 5 x 3 = 15.
    assert client.post(f"/prospects/{prospect['id']}/score").json()["base_score"] == 15

    assert client.post(f"/opportunities/{opp['id']}/dismiss").status_code == 409  # already reviewed
    assert client.get("/opportunities").json() == []
    assert len(client.get("/opportunities", params={"status": "ACCEPTED"}).json()) == 1


def test_accept_reuses_existing_prospect_and_dismiss(tmp_path):
    client, _ = _client(tmp_path)
    existing = client.post("/prospects", json={"company_name": "RobotStore", "segment": "ROBOTICS"}).json()
    client.post("/portfolio/import", json={"text": "robotstore.app"})
    client.post("/radar/scan")
    opp = client.get("/opportunities").json()[0]

    accepted = client.post(
        f"/opportunities/{opp['id']}/accept", json={"company_name": "robotstore", "segment": "ROBOTICS"}
    ).json()
    assert accepted["prospect_id"] == existing["id"]
    assert len(client.get("/prospects").json()) == 1

    assert client.post("/opportunities/OP-MISSING/dismiss").status_code == 404
