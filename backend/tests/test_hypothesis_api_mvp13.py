"""MVP 1.3A-3: hypothesis API endpoints and the deterministic generator."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.app.database import create_session_factory
from backend.app.hypothesis_generator import (
    MAX_CITED_EVIDENCE,
    generate_acquisition_hypothesis,
    select_cited_evidence,
)
from backend.app.main import create_app
from backend.app.repository import Repository


def _setup(tmp_path, *, approve_profile: bool = True):
    db_path = tmp_path / "hyp_api.sqlite3"
    client = TestClient(create_app(db_path))
    offer = client.post("/offers", json={"name": "RobotStore.app"}).json()
    if approve_profile:
        proposal = client.post(
            f"/offers/{offer['id']}/evaluate", json={"mode": "DETERMINISTIC"}
        ).json()
        client.post(f"/offers/{offer['id']}/proposals/{proposal['id']}/approve")
    prospect = client.post(
        "/prospects",
        json={"company_name": "Robotics Marketplace Ltd", "segment": "AI_AUTOMATION"},
    ).json()
    return client, db_path, offer, prospect


def _evidence(client, **overrides) -> dict:
    body = {
        "evidence_type": "Public Announcement",
        "evidence": "Announced expansion into ecommerce.",
        "impact": 1,
        "source": "https://example.com/news",
    }
    body.update(overrides)
    response = client.post("/evidence-entries", json=body)
    assert response.status_code == 201
    return response.json()


def _hypotheses_url(offer, prospect) -> str:
    return f"/offers/{offer['id']}/prospects/{prospect['id']}/hypotheses"


def _set_evidence_status(db_path, evidence_id: str, status: str) -> None:
    with create_session_factory(db_path)() as session:
        Repository(session).update_evidence_status(evidence_id, status)


# --- Full lifecycle through the API ---------------------------------------


def test_full_loop_create_link_propose_approve_activate_supersede(tmp_path):
    client, _, offer, prospect = _setup(tmp_path)
    evidence = _evidence(client, offer_id=offer["id"])

    created = client.post(
        _hypotheses_url(offer, prospect), json={"statement": "Expanding into ecommerce."}
    )
    assert created.status_code == 201
    hypothesis = created.json()
    assert hypothesis["status"] == "DRAFT"
    assert hypothesis["source"] == "HUMAN"
    assert hypothesis["reasoning_confidence"] is None

    hid = hypothesis["id"]
    linked = client.post(f"/hypotheses/{hid}/evidence/{evidence['id']}", json={"note": "core"})
    assert linked.status_code == 201
    assert linked.json()["evidence_links"][0]["evidence"]["status"] == "ACTIVE"

    proposed = client.post(f"/hypotheses/{hid}/propose").json()
    assert proposed["status"] == "PROPOSED"
    assert proposed["reasoning_confidence"] is not None
    assert proposed["reasoning_confidence_explanation"][-1].startswith("Reasoning confidence:")
    frozen_score = proposed["reasoning_confidence"]

    approved = client.post(
        f"/hypotheses/{hid}/approve",
        json={"reviewer_assessment": "STRONG", "review_notes": "solid"},
    ).json()
    assert approved["status"] == "APPROVED"
    assert approved["reviewer_assessment"] == "STRONG"
    # Invariant 3: approval never moves the computed score; empirical stays NULL.
    assert approved["reasoning_confidence"] == frozen_score
    assert approved["empirical_confidence"] is None

    active = client.post(f"/hypotheses/{hid}/activate").json()
    assert active["is_active"] is True

    successor = client.post(
        f"/hypotheses/{hid}/supersede", json={"statement": "Revised claim."}
    )
    assert successor.status_code == 201
    successor = successor.json()
    assert successor["status"] == "DRAFT"
    assert successor["statement"] == "Revised claim."
    assert successor["evidence_links"] == []  # ruling R2

    predecessor = client.get(f"/hypotheses/{hid}").json()
    assert predecessor["status"] == "SUPERSEDED"
    assert predecessor["is_active"] is False
    assert predecessor["superseded_by_id"] == successor["id"]
    assert [link["evidence_entry_id"] for link in predecessor["evidence_links"]] == [
        evidence["id"]
    ]  # invariant 9
    event_types = [event["event_type"] for event in predecessor["audit_events"]]
    assert "ACTIVATED" in event_types and "DEACTIVATED" in event_types

    listed = client.get(_hypotheses_url(offer, prospect)).json()
    assert [item["id"] for item in listed] == [hid, successor["id"]]


# --- Gates and invariants via HTTP ----------------------------------------


def test_approve_without_evidence_is_rejected(tmp_path):
    client, _, offer, prospect = _setup(tmp_path)
    hid = client.post(_hypotheses_url(offer, prospect), json={"statement": "x"}).json()["id"]
    client.post(f"/hypotheses/{hid}/propose")

    response = client.post(f"/hypotheses/{hid}/approve")

    assert response.status_code == 409  # invariant 1
    assert "without linked evidence" in response.json()["detail"]
    assert client.get(f"/hypotheses/{hid}").json()["status"] == "PROPOSED"


def test_canonical_content_frozen_after_propose(tmp_path):
    client, _, offer, prospect = _setup(tmp_path)
    evidence = _evidence(client)
    other = _evidence(client, evidence="Second item.")
    hid = client.post(_hypotheses_url(offer, prospect), json={"statement": "x"}).json()["id"]
    client.post(f"/hypotheses/{hid}/evidence/{evidence['id']}")

    edited = client.put(f"/hypotheses/{hid}", json={"recipient_framing": "angle"})
    assert edited.status_code == 200 and edited.json()["recipient_framing"] == "angle"
    assert edited.json()["statement"] == "x"  # unset fields are untouched

    client.post(f"/hypotheses/{hid}/propose")
    assert client.put(f"/hypotheses/{hid}", json={"statement": "typo fix"}).status_code == 409
    assert client.post(f"/hypotheses/{hid}/evidence/{other['id']}").status_code == 409
    assert client.delete(f"/hypotheses/{hid}/evidence/{evidence['id']}").status_code == 409


def test_payloads_cannot_set_governed_fields(tmp_path):
    client, _, offer, prospect = _setup(tmp_path)
    url = _hypotheses_url(offer, prospect)
    for field, value in [
        ("status", "APPROVED"),
        ("reasoning_confidence", 99),
        ("is_active", True),
        ("source", "LLM_ASSISTED"),
        ("empirical_confidence", 1.0),
    ]:
        assert client.post(url, json={"statement": "x", field: value}).status_code == 422

    hid = client.post(url, json={"statement": "x"}).json()["id"]
    assert client.put(f"/hypotheses/{hid}", json={"status": "VALIDATING"}).status_code == 422
    assert client.put(f"/hypotheses/{hid}", json={"statement": None}).status_code == 422


def test_reject_is_terminal_and_cannot_be_superseded(tmp_path):
    client, _, offer, prospect = _setup(tmp_path)
    hid = client.post(_hypotheses_url(offer, prospect), json={"statement": "x"}).json()["id"]
    client.post(f"/hypotheses/{hid}/propose")

    rejected = client.post(f"/hypotheses/{hid}/reject", json={"review_notes": "weak"}).json()
    assert rejected["status"] == "REJECTED"
    assert rejected["review_notes"] == "weak"
    assert client.post(f"/hypotheses/{hid}/supersede").status_code == 409  # ruling R1
    assert client.post(f"/hypotheses/{hid}/activate").status_code == 409


def test_activation_swaps_and_requires_active_evidence(tmp_path):
    client, db_path, offer, prospect = _setup(tmp_path)

    def approved_with(evidence_id: str) -> str:
        hid = client.post(_hypotheses_url(offer, prospect), json={"statement": "x"}).json()["id"]
        client.post(f"/hypotheses/{hid}/evidence/{evidence_id}")
        client.post(f"/hypotheses/{hid}/propose")
        client.post(f"/hypotheses/{hid}/approve")
        return hid

    first = approved_with(_evidence(client)["id"])
    archived_evidence = _evidence(client, evidence="Later archived.")
    second = approved_with(archived_evidence["id"])
    _set_evidence_status(db_path, archived_evidence["id"], "ARCHIVED")

    assert client.post(f"/hypotheses/{first}/activate").status_code == 200
    blocked = client.post(f"/hypotheses/{second}/activate")
    assert blocked.status_code == 409
    assert "ACTIVE state" in blocked.json()["detail"]

    third = approved_with(_evidence(client, evidence="Third.")["id"])
    assert client.post(f"/hypotheses/{third}/activate").status_code == 200
    states = {h["id"]: h["is_active"] for h in client.get(_hypotheses_url(offer, prospect)).json()}
    assert states == {first: False, second: False, third: True}  # invariant 4


def test_refinement_requires_parent_and_shows_it(tmp_path):
    client, _, offer, prospect = _setup(tmp_path)
    dm = client.post(
        f"/prospects/{prospect['id']}/decision-makers", json={"name": "Ada", "role": "Founder"}
    ).json()
    url = _hypotheses_url(offer, prospect)

    orphan = client.post(url, json={"statement": "x", "decision_maker_id": dm["id"]})
    assert orphan.status_code == 409  # invariant 5
    assert "refines" in orphan.json()["detail"]

    parent = client.post(url, json={"statement": "Company-level claim."}).json()
    child = client.post(
        url,
        json={
            "statement": "Founder framing.",
            "decision_maker_id": dm["id"],
            "refines_hypothesis_id": parent["id"],
        },
    ).json()
    detail = client.get(f"/hypotheses/{child['id']}").json()
    assert detail["parent"]["statement"] == "Company-level claim."


def test_missing_resources_return_404(tmp_path):
    client, _, offer, prospect = _setup(tmp_path)
    url = _hypotheses_url(offer, prospect)
    hid = client.post(url, json={"statement": "x"}).json()["id"]

    assert client.get("/hypotheses/AH-MISSING").status_code == 404
    assert client.post("/hypotheses/AH-MISSING/propose").status_code == 404
    assert client.post(f"/hypotheses/{hid}/evidence/EV-MISSING").status_code == 404
    assert client.get(f"/offers/O-MISSING/prospects/{prospect['id']}/hypotheses").status_code == 404
    assert client.post(url, json={"statement": "x", "refines_hypothesis_id": "AH-X"}).status_code == 404
    assert client.post(
        url, json={"statement": "x", "decision_maker_id": "DM-X", "refines_hypothesis_id": hid}
    ).status_code == 404


def test_no_route_can_reach_dormant_states(tmp_path):
    client, _, offer, prospect = _setup(tmp_path)
    paths = {route.path for route in client.app.routes}
    for dormant in ("validat", "support", "weaken"):
        assert not any(dormant in path.lower() for path in paths)


# --- Deterministic generator ----------------------------------------------


def test_generate_requires_approved_offer_profile(tmp_path):
    client, _, offer, prospect = _setup(tmp_path, approve_profile=False)

    response = client.post(f"{_hypotheses_url(offer, prospect)}/generate")

    assert response.status_code == 409
    assert response.json()["detail"] == "Approved offer profile required"


def test_generate_cites_only_real_active_relevant_evidence(tmp_path):
    client, db_path, offer, prospect = _setup(tmp_path)
    client.post(
        f"/prospects/{prospect['id']}/signals",
        json={"signal_type": "Robotics hiring", "tier": 1, "score": 5},
    )
    offer_evidence = _evidence(client, offer_id=offer["id"])
    pdm_evidence = _evidence(client, pdm_code="AI-AUTOMATION", evidence_type="Signal")
    _evidence(client, pdm_code="SEO", evidence="Unrelated PDM.")
    _evidence(client, evidence="No offer, no PDM.")
    retracted = _evidence(client, offer_id=offer["id"], evidence="Retracted.")
    _set_evidence_status(db_path, retracted["id"], "RETRACTED")

    response = client.post(f"{_hypotheses_url(offer, prospect)}/generate")

    assert response.status_code == 201
    draft = response.json()
    assert draft["status"] == "DRAFT"
    assert draft["source"] == "DETERMINISTIC"
    assert draft["provider"] == "deterministic"
    assert draft["reasoning_confidence"] is None  # never set by generation
    assert draft["is_active"] is False
    assert "Robotics Marketplace Ltd" in draft["statement"]
    assert "RobotStore.app" in draft["statement"]
    assert "Robotics hiring (tier 1)" in draft["statement"]
    cited = [link["evidence_entry_id"] for link in draft["evidence_links"]]
    assert cited == [offer_evidence["id"], pdm_evidence["id"]]  # offer-specific first
    assert all(link["evidence"]["status"] == "ACTIVE" for link in draft["evidence_links"])

    # The draft enters the ordinary review gate; no automatic approval.
    hid = draft["id"]
    assert client.post(f"/hypotheses/{hid}/activate").status_code == 409
    assert client.post(f"/hypotheses/{hid}/propose").json()["status"] == "PROPOSED"
    assert client.post(f"/hypotheses/{hid}/approve").json()["status"] == "APPROVED"


def test_generate_without_evidence_produces_unapprovable_draft(tmp_path):
    client, _, offer, prospect = _setup(tmp_path)

    draft = client.post(f"{_hypotheses_url(offer, prospect)}/generate").json()

    assert draft["evidence_links"] == []
    assert "attach evidence before review" in draft["statement"]
    client.post(f"/hypotheses/{draft['id']}/propose")
    assert client.post(f"/hypotheses/{draft['id']}/approve").status_code == 409


def test_generate_decision_maker_refinement(tmp_path):
    client, _, offer, prospect = _setup(tmp_path)
    dm = client.post(
        f"/prospects/{prospect['id']}/decision-makers",
        json={"name": "Ada", "role": "Creative Director"},
    ).json()
    url = f"{_hypotheses_url(offer, prospect)}/generate"

    assert client.post(url, json={"decision_maker_id": dm["id"]}).status_code == 409

    parent = client.post(url).json()
    child = client.post(
        url, json={"decision_maker_id": dm["id"], "refines_hypothesis_id": parent["id"]}
    ).json()
    assert child["refines_hypothesis_id"] == parent["id"]
    assert child["parent"]["id"] == parent["id"]
    # "Director" must not match the "cto" keyword: whole-word role matching.
    assert child["recipient_framing"] == (
        "For Ada (Creative Director): frame around how the domain supports "
        "the company's stated direction."
    )


def test_generator_is_deterministic_and_capped():
    entries = [
        SimpleNamespace(
            id=f"EV-{i:02d}",
            status="ACTIVE",
            offer_id="O-1" if i % 2 else None,
            pdm_code="AI-AUTOMATION",
            evidence_type="Signal",
            created_at=f"2026-01-{i + 1:02d}T00:00:00+00:00",
        )
        for i in range(8)
    ]
    first = select_cited_evidence(entries, offer_id="O-1", prospect_pdm_code="AI-AUTOMATION")
    second = select_cited_evidence(
        list(reversed(entries)), offer_id="O-1", prospect_pdm_code="AI-AUTOMATION"
    )
    assert [e.id for e in first] == [e.id for e in second]
    assert len(first) == MAX_CITED_EVIDENCE
    # Offer-specific evidence first (newest first), then PDM-matched evidence.
    assert [e.id for e in first] == ["EV-07", "EV-05", "EV-03", "EV-01", "EV-06"]

    kwargs = dict(
        offer_id="O-1",
        offer_name="RobotStore.app",
        offer_category="Robotics Marketplace",
        commercial_hypothesis="A marketplace domain.",
        company_name="Acme",
        segment="AI_AUTOMATION",
        signals=[],
        cited_evidence=first,
        decision_maker=SimpleNamespace(name="Bo", role="Chief Executive Officer"),
    )
    assert generate_acquisition_hypothesis(**kwargs) == generate_acquisition_hypothesis(**kwargs)
    assert "category ownership" in generate_acquisition_hypothesis(**kwargs)["recipient_framing"]
