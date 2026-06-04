from __future__ import annotations

from .rules import RuleRegistry
from .schemas import AlphaSignal, ProspectScore, ScoreDecision, ScoreExplanation, Signal


class ScoringEngine:
    """MVP 0 scoring engine with separate base and Alpha Signal contributions."""

    def __init__(self, rules: RuleRegistry | None = None):
        self.rules = rules or RuleRegistry()

    def calculate(
        self,
        prospect_id: str,
        signals: list[Signal],
        alpha_signals: list[AlphaSignal] | None = None,
    ) -> ProspectScore:
        alpha_signals = alpha_signals or []
        tier_multipliers = self.rules.tier_multipliers()
        tier_totals = {1: 0, 2: 0, 3: 0}
        explanation: list[ScoreExplanation] = []

        for signal in signals:
            tier_totals[signal.tier] += signal.score
            impact = signal.score * tier_multipliers[signal.tier]
            explanation.append(
                ScoreExplanation(
                    source_type="SIGNAL",
                    source_code=signal.signal_type,
                    label=signal.signal_type,
                    tier=signal.tier,
                    impact=impact,
                    notes=signal.notes,
                )
            )

        base_score = sum(
            tier_totals[tier] * multiplier
            for tier, multiplier in tier_multipliers.items()
        )
        alpha_bonus = sum(alpha_signal.bonus_score for alpha_signal in alpha_signals)
        for alpha_signal in alpha_signals:
            explanation.append(
                ScoreExplanation(
                    source_type="ALPHA_SIGNAL",
                    source_code=alpha_signal.code,
                    label=alpha_signal.name,
                    impact=alpha_signal.bonus_score,
                    notes=alpha_signal.description,
                )
            )

        final_score = base_score + alpha_bonus
        disqualifier = self.rules.matching_disqualifier(
            [signal.signal_type for signal in signals]
        )
        decision = self._decision_for(final_score)
        if disqualifier:
            decision = ScoreDecision.DISQUALIFY
            explanation.append(
                ScoreExplanation(
                    source_type="DISQUALIFIER",
                    source_code=disqualifier["code"],
                    label=disqualifier["name"],
                    impact=0,
                    notes=disqualifier["reason"],
                )
            )

        return ProspectScore(
            prospect_id=prospect_id,
            tier1_total=tier_totals[1],
            tier2_total=tier_totals[2],
            tier3_total=tier_totals[3],
            base_score=base_score,
            alpha_matches=[alpha_signal.code for alpha_signal in alpha_signals],
            alpha_bonus=alpha_bonus,
            final_score=final_score,
            decision=decision,
            explanation=explanation,
        )

    def _decision_for(self, final_score: int) -> ScoreDecision:
        return ScoreDecision(self.rules.decision_for_score(final_score))
