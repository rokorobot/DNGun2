from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


RULES_DIR = Path(__file__).resolve().parent / "rules"


class RuleRegistryError(Exception):
    pass


class RuleRegistry:
    def __init__(self, rules_dir: Path | None = None):
        self.rules_dir = rules_dir or RULES_DIR
        self._score_bands = self._load_rule_file(
            "score_bands.yaml",
            top_level_key="score_bands",
            required_fields={"code", "label", "decision"},
        )
        self._signal_taxonomy = self._load_rule_file(
            "signal_taxonomy.yaml",
            top_level_key="signals",
            required_fields={"code", "name", "tier", "category"},
        )
        self._alpha_signals = self._load_rule_file(
            "alpha_signals.yaml",
            top_level_key="alpha_signals",
            required_fields={"code", "name", "required_signals", "bonus_score"},
        )
        self._disqualifiers = self._load_rule_file(
            "disqualifiers.yaml",
            top_level_key="disqualifiers",
            required_fields={"code", "name", "signal_type", "reason"},
        )
        
        # Safe authority rules load: fallback to global RULES_DIR if missing in test custom dirs
        auth_filename = "authority_rules.yaml"
        auth_dir = self.rules_dir
        if not (self.rules_dir / auth_filename).exists() and RULES_DIR != self.rules_dir:
            auth_dir = RULES_DIR
            
        if (auth_dir / auth_filename).exists():
            original_dir = self.rules_dir
            self.rules_dir = auth_dir
            try:
                self._authority_rules = self._load_rule_file(
                    auth_filename,
                    top_level_key="authority_rules",
                    required_fields={"role_keywords", "score", "acquisition_rationale"},
                )
            finally:
                self.rules_dir = original_dir
        else:
            self._authority_rules = []
        self._tier_multipliers = self._load_tier_multipliers()

    def all_rules(self) -> dict[str, Any]:
        return {
            "score_bands": self.score_bands(),
            "tier_multipliers": self.tier_multipliers(),
            "signal_taxonomy": self.signal_taxonomy(),
            "alpha_signals": self.alpha_signals(),
            "disqualifiers": self.disqualifiers(),
            "authority_rules": self.authority_rules(),
        }

    def score_bands(self) -> list[dict[str, Any]]:
        return self._score_bands

    def tier_multipliers(self) -> dict[int, int]:
        return self._tier_multipliers

    def signal_taxonomy(self) -> list[dict[str, Any]]:
        return self._signal_taxonomy

    def alpha_signals(self) -> list[dict[str, Any]]:
        return self._alpha_signals

    def disqualifiers(self) -> list[dict[str, Any]]:
        return self._disqualifiers

    def authority_rules(self) -> list[dict[str, Any]]:
        return self._authority_rules

    def decision_for_score(self, score: int) -> str:
        for band in self.score_bands():
            min_score = band.get("min_score")
            max_score = band.get("max_score")
            if min_score is not None and score < min_score:
                continue
            if max_score is not None and score > max_score:
                continue
            return band["decision"]
        raise RuleRegistryError(f"No score band matched score {score}")

    def matching_disqualifier(self, signal_types: list[str]) -> dict[str, Any] | None:
        observed = set(signal_types)
        for disqualifier in self.disqualifiers():
            if disqualifier["signal_type"] in observed:
                return disqualifier
        return None

    def _load_rule_file(
        self,
        filename: str,
        *,
        top_level_key: str,
        required_fields: set[str],
    ) -> list[dict[str, Any]]:
        data = self._load_yaml(filename)
        items = data.get(top_level_key)
        if not isinstance(items, list) or not items:
            raise RuleRegistryError(f"{filename} must define non-empty {top_level_key}")

        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise RuleRegistryError(f"{filename} item {index} must be an object")
            missing = required_fields - set(item)
            if missing:
                missing_fields = ", ".join(sorted(missing))
                raise RuleRegistryError(
                    f"{filename} item {index} missing required fields: {missing_fields}"
                )
        return items

    def _load_tier_multipliers(self) -> dict[int, int]:
        data = self._load_yaml("score_bands.yaml")
        multipliers = data.get("tier_multipliers")
        if not isinstance(multipliers, dict):
            raise RuleRegistryError("score_bands.yaml must define tier_multipliers")

        parsed = {int(tier): int(multiplier) for tier, multiplier in multipliers.items()}
        for tier in (1, 2, 3):
            if tier not in parsed:
                raise RuleRegistryError(f"tier_multipliers missing tier {tier}")
        return parsed

    def _load_yaml(self, filename: str) -> dict[str, Any]:
        path = self.rules_dir / filename
        if not path.exists():
            raise RuleRegistryError(f"Missing rule file: {path}")
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        if not isinstance(data, dict):
            raise RuleRegistryError(f"{filename} must contain a mapping")
        return data
