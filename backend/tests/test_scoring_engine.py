from backend.app.schemas import AlphaSignal, Signal
from backend.app.scoring_engine import ScoringEngine


def test_calculates_base_score_from_tiered_signals():
    signals = [
        Signal(
            id="S-1",
            prospect_id="P-1",
            signal_type="Founder discussing growth",
            tier=1,
            score=5,
            observed_at="2026-06-04T00:00:00+00:00",
            created_at="2026-06-04T00:00:00+00:00",
        ),
        Signal(
            id="S-2",
            prospect_id="P-1",
            signal_type="Hiring SDR",
            tier=2,
            score=4,
            observed_at="2026-06-04T00:00:00+00:00",
            created_at="2026-06-04T00:00:00+00:00",
        ),
        Signal(
            id="S-3",
            prospect_id="P-1",
            signal_type="Weak website positioning",
            tier=3,
            score=3,
            observed_at="2026-06-04T00:00:00+00:00",
            created_at="2026-06-04T00:00:00+00:00",
        ),
    ]

    score = ScoringEngine().calculate("P-1", signals)

    assert score.tier1_total == 5
    assert score.tier2_total == 4
    assert score.tier3_total == 3
    assert score.base_score == 26
    assert score.alpha_bonus == 0
    assert score.final_score == 26
    assert score.decision == "IGNORE"


def test_returns_score_provenance_for_each_signal():
    signal = Signal(
        id="S-1",
        prospect_id="P-1",
        signal_type="Recent funding",
        tier=1,
        score=5,
        notes="Seed announcement",
        observed_at="2026-06-04T00:00:00+00:00",
        created_at="2026-06-04T00:00:00+00:00",
    )

    score = ScoringEngine().calculate("P-1", [signal])

    assert score.explanation[0].source_type == "SIGNAL"
    assert score.explanation[0].source_code == "Recent funding"
    assert score.explanation[0].tier == 1
    assert score.explanation[0].impact == 15
    assert score.explanation[0].notes == "Seed announcement"


def test_alpha_signal_bonus_is_separate_and_explainable():
    signal = Signal(
        id="S-1",
        prospect_id="P-1",
        signal_type="Founder discussing growth",
        tier=1,
        score=5,
        observed_at="2026-06-04T00:00:00+00:00",
        created_at="2026-06-04T00:00:00+00:00",
    )
    alpha_signal = AlphaSignal(
        id="AS-1",
        code="AS-001",
        name="Growth Pressure",
        required_signals=[],
        bonus_score=15,
        validation_status="HYPOTHESIS",
        created_at="2026-06-04T00:00:00+00:00",
    )

    score = ScoringEngine().calculate("P-1", [signal], [alpha_signal])

    assert score.base_score == 15
    assert score.alpha_matches == ["AS-001"]
    assert score.alpha_bonus == 15
    assert score.final_score == 30
    assert score.explanation[1].source_type == "ALPHA_SIGNAL"
    assert score.explanation[1].impact == 15


def test_score_thresholds():
    engine = ScoringEngine()

    assert engine._decision_for(59) == "IGNORE"
    assert engine._decision_for(60) == "SECONDARY"
    assert engine._decision_for(79) == "SECONDARY"
    assert engine._decision_for(80) == "CONTACT_NOW"
