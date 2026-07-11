from __future__ import annotations

import re

from .rules import RuleRegistry


def _tokenize(text: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", text.lower()) if token]


def _contains_phrase(role_tokens: list[str], keyword_tokens: list[str]) -> bool:
    if not keyword_tokens or len(keyword_tokens) > len(role_tokens):
        return False
    span = len(keyword_tokens)
    return any(
        role_tokens[start : start + span] == keyword_tokens
        for start in range(len(role_tokens) - span + 1)
    )


class AuthorityScoringEngine:
    def __init__(self, rules: RuleRegistry | None = None):
        self.rules = rules or RuleRegistry()

    def calculate(self, role: str) -> tuple[int, str]:
        """
        Calculates the AuthorityScore and acquisition_rationale for a given role title.
        Returns a tuple of (score, acquisition_rationale).

        Keywords match whole tokens or contiguous token phrases, never raw
        substrings, so "coo" cannot match inside "coordinator".
        """
        role_tokens = _tokenize(role)
        if not role_tokens:
            return 10, "Role is not specified; baseline authority."

        # Scan dynamic authority rules from the rule registry; first rule wins.
        for rule in self.rules.authority_rules():
            for kw in rule["role_keywords"]:
                if _contains_phrase(role_tokens, _tokenize(kw)):
                    return int(rule["score"]), rule["acquisition_rationale"]

        # Default fallback if no keyword matches
        return 20, "Standard corporate contact."
