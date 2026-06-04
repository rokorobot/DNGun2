from __future__ import annotations

import json
import os
import sys
import traceback
import urllib.error
import urllib.request


DEFAULT_MODEL = "gpt-4.1-mini"


def generate_llm_offer_evaluation(domain_name: str) -> dict | None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.stderr.write("OPENAI_API_KEY environment variable not set. Skipping LLM evaluation.\n")
        return None

    body = {
        "model": os.environ.get("DNGUN_OFFER_LLM_MODEL", DEFAULT_MODEL),
        "messages": [
            {
                "role": "system",
                "content": (
                    "Evaluate the domain as a sellable domain-name offer. "
                    "Identify likely commercial use cases, buyer profiles who may pay, "
                    "and observable prospect signals. Do not invent specific companies. "
                    "Do not claim market data unless provided. Return only structured JSON "
                    "matching the requested schema. Include uncertainty and alternatives."
                ),
            },
            {"role": "user", "content": _prompt(domain_name)},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "offer_evaluation",
                "schema": _schema(),
                "strict": True,
            }
        },
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        sys.stderr.write(f"HTTP request or connection failed during LLM evaluation of {domain_name}:\n")
        traceback.print_exc(file=sys.stderr)
        return None

    text = _extract_text(payload)
    if not text:
        sys.stderr.write(f"No response text extracted from LLM payload: {json.dumps(payload)}\n")
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"JSON decode failed for assistant content '{text}':\n")
        traceback.print_exc(file=sys.stderr)
        return None


def _extract_text(payload: dict) -> str | None:
    try:
        return payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None


def _prompt(domain_name: str) -> str:
    return (
        f"Domain: {domain_name}\n"
        "Return JSON with primary_category, confidence_score, confidence_label, "
        "commercial_hypothesis, predicted_value_range, target_segments, buyer_profiles, "
        "signal_profiles, pdm, reasoning, and alternative_categories."
    )


def _schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "primary_category",
            "confidence_score",
            "confidence_label",
            "commercial_hypothesis",
            "predicted_value_range",
            "target_segments",
            "buyer_profiles",
            "signal_profiles",
            "pdm",
            "reasoning",
            "alternative_categories",
        ],
        "properties": {
            "primary_category": {"type": "string"},
            "confidence_score": {"type": "number", "minimum": 0, "maximum": 1},
            "confidence_label": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH"]},
            "commercial_hypothesis": {"type": "string"},
            "predicted_value_range": {"type": "string"},
            "target_segments": {"type": "array", "items": {"type": "string"}},
            "buyer_profiles": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["profile_name", "rationale", "priority"],
                    "properties": {
                        "profile_name": {"type": "string"},
                        "rationale": {"type": "string"},
                        "priority": {"type": "integer"},
                    },
                },
            },
            "signal_profiles": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["signal_name", "tier", "rationale"],
                    "properties": {
                        "signal_name": {"type": "string"},
                        "tier": {"type": "integer", "enum": [1, 2, 3]},
                        "rationale": {"type": "string"},
                    },
                },
            },
            "pdm": {
                "type": "object",
                "additionalProperties": False,
                "required": ["code", "name", "summary", "target_segments"],
                "properties": {
                    "code": {"type": "string"},
                    "name": {"type": "string"},
                    "summary": {"type": "string"},
                    "target_segments": {"type": "array", "items": {"type": "string"}},
                },
            },
            "reasoning": {"type": "array", "items": {"type": "string"}},
            "alternative_categories": {"type": "array", "items": {"type": "string"}},
        },
    }
