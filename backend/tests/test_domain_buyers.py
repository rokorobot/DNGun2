from backend.app.domain_buyers import (
    find_domain_buyers,
    keywords_for_domain,
    split_keywords,
    name_match,
    normalize_domain,
)
from backend.app.treg_client import TregError

IDEAS = {"output": {"keywords": [{"value": "ai automation"}, {"value": "ai automation agency"},
                                 {"value": "ai automation tools"}, {"value": "aiautomation global"},
                                 {"value": "ai automation society"}]}}


class FakeClient:
    calls = 0
    spent_usd = 0.0

    def __init__(self, responses):
        self.responses = responses
        self.requests = []

    def call(self, endpoint_id, *, method="GET", query=None, body=None, **_):
        self.calls += 1
        self.requests.append((endpoint_id, query, body))
        response = self.responses[endpoint_id]
        if isinstance(response, Exception):
            raise response
        return response(query if query is not None else body) if callable(response) else response


SERP = {
    "ads": [
        {"position": 1, "title": "Automate with AI", "link": "https://www.ai-automation-agency.io/lp"},
        {"position": 2, "title": "Big vendor", "link": "https://bigcorp.com/ai"},
    ],
    "organic_results": [
        {"position": 1, "title": "AI automation - Wikipedia", "link": "https://en.wikipedia.org/wiki/x"},
        {"position": 2, "title": "Big vendor", "link": "https://www.bigcorp.com/automation"},
        {"position": 7, "title": "Blog", "link": "https://smallblog.co.uk/post"},
        {"position": 8, "title": "Self", "link": "https://aiautomation.com/"},
    ],
}


def test_helpers():
    assert normalize_domain("https://www.Shop.Example.co.uk/path") == "example.co.uk"
    assert normalize_domain("sub.example.com") == "example.com"
    assert keywords_for_domain("https://ai-automation.com") == ["ai automation"]
    assert name_match("aiautomationhq.io", ["ai automation"]) == "strong"
    assert name_match("automationco.com", ["ai automation"]) == "partial"
    assert name_match("bigcorp.com", ["ai automation"]) is None


def test_ranks_advertisers_and_upgrade_buyers_first():
    client = FakeClient({
        "treg.google.keywords.ideas": IDEAS,
        "treg.google.keywords.volume": {"output": {"rows": [
            {"keyword": "ai automation", "search_volume": 12100, "cpc": 18.5}]}},
        "serpapi.x.google-ads": SERP,
        "spyfu.google.domain.overview": lambda q: {"results": [
            {"monthlyBudget": 25000 if q["domain"] == "bigcorp.com" else 0}]},
    })

    result = find_domain_buyers(client, "aiautomation.com", enrich_top=5)

    assert result["keywords"] == ["ai automation"]  # Google's own segmentation of the stem

    domains = [c["domain"] for c in result["candidates"]]
    assert domains == ["bigcorp.com", "ai-automation-agency.io", "smallblog.co.uk"]
    assert "wikipedia.org" not in domains and "aiautomation.com" not in domains
    top = result["candidates"][0]
    assert top["score"] == 40 + 25 + 20  # advertiser + organic top 3 + $25k budget
    assert result["candidates"][1]["score"] == 40 + 10 + 20  # ad slot #1 + upgrade buyer
    assert result["keyword_metrics"]["ai automation"] == {"volume": 12100.0, "cpc": 18.5, "competition": None}
    assert result["warnings"] == []


def test_provider_errors_become_warnings():
    client = FakeClient({
        "treg.google.keywords.volume": TregError("treg.google.keywords.volume", 402, "out of balance"),
        "serpapi.x.google-ads": SERP,
        "spyfu.google.domain.overview": TregError("spyfu.google.domain.overview", 502, "upstream"),
    })

    result = find_domain_buyers(client, "aiautomation.com", ["ai automation"], enrich_top=1)

    assert result["candidates"]
    assert result["keyword_metrics"] == {}
    assert len(result["warnings"]) == 2


def test_split_keywords():
    assert split_keywords(["AI automation, ai  agents", "ai automation"]) == ["ai automation", "ai agents"]
    assert split_keywords(None) == []


def test_derives_keyword_from_split_volume_when_ideas_miss():
    volumes = {"robotstore": 0, "robot store": 900, "robots tore": 0}
    client = FakeClient({
        "treg.google.keywords.ideas": {"output": {"keywords": [{"value": "robotshop"}]}},
        "treg.google.keywords.volume": lambda body: {"output": {"rows": [
            {"keyword": k, "volume": volumes.get(k, 0)} for k in body["keywords"]]}},
        "serpapi.x.google-ads": {"ads": [], "organic_results": []},
        "spyfu.google.domain.overview": {},
    })

    assert find_domain_buyers(client, "robotstore.com")["keywords"] == ["robot store"]


def test_expand_adds_highest_value_related_keywords():
    rows = {"ai automation": (8100, 5.0), "ai automation agency": (2900, 6.0),
            "ai automation tools": (5000, 1.0), "ai automation society": (900, 0)}
    searched = []
    client = FakeClient({
        "treg.google.keywords.ideas": IDEAS,
        "treg.google.keywords.volume": lambda body: {"output": {"rows": [
            {"keyword": k, "volume": rows[k][0], "cpc": rows[k][1]} for k in body["keywords"] if k in rows]}},
        "serpapi.x.google-ads": lambda q: searched.append(q["q"]) or SERP,
        "spyfu.google.domain.overview": {},
    })

    result = find_domain_buyers(client, "aiautomation.com", ["ai automation"], expand=2, enrich_top=0)

    # value = volume x CPC: agency 17,400 > tools 5,000; society has no CPC; "aiautomation global" is off-topic.
    assert result["expanded_keywords"] == ["ai automation agency", "ai automation tools"]
    assert searched == ["ai automation", "ai automation agency", "ai automation tools"]


def test_big_advertisers_toggle():
    responses = {
        "treg.google.keywords.volume": {"output": {"rows": []}},
        "serpapi.x.google-ads": SERP,
        "spyfu.google.domain.overview": lambda q: {"results": [
            {"monthlyBudget": 2_000_000 if q["domain"] == "bigcorp.com" else 500}]},
    }
    kept = find_domain_buyers(FakeClient(responses), "aiautomation.com", ["ai automation"])
    dropped = find_domain_buyers(FakeClient(responses), "aiautomation.com", ["ai automation"],
                                 big_budget=100_000)

    assert "bigcorp.com" in [c["domain"] for c in kept["candidates"]]
    assert "bigcorp.com" not in [c["domain"] for c in dropped["candidates"]]
    assert dropped["excluded_big_advertisers"] == [{"domain": "bigcorp.com", "monthly_ad_budget": 2_000_000.0}]
