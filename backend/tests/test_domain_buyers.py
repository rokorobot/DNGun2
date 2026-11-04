from backend.app.domain_buyers import (
    find_domain_buyers,
    keywords_for_domain,
    name_match,
    normalize_domain,
)
from backend.app.treg_client import TregError


class FakeClient:
    calls = 0
    spent_usd = 0.0

    def __init__(self, responses):
        self.responses = responses
        self.requests = []

    def call(self, endpoint_id, *, method="GET", query=None, body=None):
        self.calls += 1
        self.requests.append((endpoint_id, query, body))
        response = self.responses[endpoint_id]
        if isinstance(response, Exception):
            raise response
        return response(query) if callable(response) else response


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
        "treg.google.keywords.volume": {"output": {"rows": [
            {"keyword": "ai automation", "search_volume": 12100, "cpc": 18.5}]}},
        "serpapi.x.google-ads": SERP,
        "spyfu.google.domain.overview": lambda q: {"results": [
            {"monthlyBudget": 25000 if q["domain"] == "bigcorp.com" else 0}]},
    })

    result = find_domain_buyers(client, "aiautomation.com", enrich_top=5)

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
