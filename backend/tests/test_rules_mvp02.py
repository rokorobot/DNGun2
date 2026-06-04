from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.database import create_session_factory
from backend.app.main import create_app
from backend.app.repository import Repository
from backend.app.rules import RuleRegistry, RuleRegistryError
from backend.app.schemas import Signal
from backend.app.seed import seed_mvp0
from backend.app.scoring_engine import ScoringEngine


def test_rules_load_correctly():
    rules = RuleRegistry()

    assert rules.decision_for_score(80) == "CONTACT_NOW"
    assert rules.tier_multipliers() == {1: 3, 2: 2, 3: 1}
    assert {rule["code"] for rule in rules.alpha_signals()} >= {
        "AS-001",
        "AS-004",
        "AS-010",
    }


def test_invalid_rule_file_fails_safely(tmp_path):
    write_rule_file(tmp_path, "score_bands.yaml", "score_bands:\n  - code: BROKEN\n")
    write_rule_file(tmp_path, "signal_taxonomy.yaml", "signals: []\n")
    write_rule_file(tmp_path, "alpha_signals.yaml", "alpha_signals: []\n")
    write_rule_file(tmp_path, "disqualifiers.yaml", "disqualifiers: []\n")

    with pytest.raises(RuleRegistryError, match="missing required fields"):
        RuleRegistry(tmp_path)


def test_rule_endpoints_expose_registry():
    client = TestClient(create_app())

    assert client.get("/rules").status_code == 200
    assert client.get("/rules/score-bands").json()[0]["code"] == "CONTACT_NOW"
    assert client.get("/rules/alpha-signals").json()[0]["code"].startswith("AS-")
    assert client.get("/rules/signal-taxonomy").json()[0]["tier"] == 1
    assert client.get("/rules/disqualifiers").json()[0]["signal_type"]


def test_scoring_uses_score_bands_from_rule_registry(tmp_path):
    write_rule_file(
        tmp_path,
        "score_bands.yaml",
        """
score_bands:
  - code: CONTACT_NOW
    label: Contact Immediately
    decision: CONTACT_NOW
    min_score: 10
  - code: IGNORE
    label: Ignore
    decision: IGNORE
    max_score: 9
tier_multipliers:
  "1": 3
  "2": 2
  "3": 1
""",
    )
    write_rule_file(
        tmp_path,
        "signal_taxonomy.yaml",
        """
signals:
  - code: founder_discusses_growth
    name: Founder discusses growth
    tier: 1
    category: buying_intent
""",
    )
    write_rule_file(
        tmp_path,
        "alpha_signals.yaml",
        """
alpha_signals:
  - code: AS-T
    name: Test Alpha
    required_signals: []
    bonus_score: 0
""",
    )
    write_rule_file(
        tmp_path,
        "disqualifiers.yaml",
        """
disqualifiers:
  - code: test_disqualifier
    name: Test Disqualifier
    signal_type: Test Disqualifier
    reason: Test reason
""",
    )

    signal = Signal(
        id="S-1",
        prospect_id="P-1",
        signal_type="Founder discusses growth",
        tier=1,
        score=5,
        observed_at="2026-06-04T00:00:00+00:00",
        created_at="2026-06-04T00:00:00+00:00",
    )

    score = ScoringEngine(rules=RuleRegistry(tmp_path)).calculate("P-1", [signal])

    assert score.final_score == 15
    assert score.decision == "CONTACT_NOW"


def test_alpha_signal_definitions_can_be_seeded_from_rules(tmp_path):
    db_path = tmp_path / "rules-seed.sqlite3"
    session_factory = create_session_factory(db_path)
    with session_factory() as session:
        seed_mvp0(session)
        alpha_signals = Repository(session).list_alpha_signals()

    rule_codes = {rule["code"] for rule in RuleRegistry().alpha_signals()}
    seeded_codes = {alpha_signal.code for alpha_signal in alpha_signals}
    assert seeded_codes == rule_codes


def write_rule_file(directory: Path, filename: str, content: str) -> None:
    (directory / filename).write_text(content, encoding="utf-8")
