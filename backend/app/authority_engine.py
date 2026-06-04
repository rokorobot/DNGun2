from __future__ import annotations

from .rules import RuleRegistry


class AuthorityScoringEngine:
    def __init__(self, rules: RuleRegistry | None = None):
        self.rules = rules or RuleRegistry()

    def calculate(self, role: str) -> tuple[int, str]:
        """
        Calculates the AuthorityScore and acquisition_rationale for a given role title.
        Returns a tuple of (score, acquisition_rationale).
        """
        cleaned_role = role.strip().lower()
        if not cleaned_role:
            return 10, "Role is not specified; baseline authority."

        # Scan dynamic authority rules from the rule registry
        for rule in self.rules.authority_rules():
            for kw in rule["role_keywords"]:
                # Match keyword as a substring/word in the cleaned role
                if kw in cleaned_role:
                    return int(rule["score"]), rule["acquisition_rationale"]

        # Default fallback if no keyword matches
        return 20, "Standard corporate contact."
