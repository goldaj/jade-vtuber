"""Single, versioned, non-LLM visual contract for Jade Live2D renderers.

The first two reactions per intent use ONLY expressions already declared by
r20 Jade.model3.json. They are facial fallbacks, not bespoke motion assets.
Do not send arbitrary model output to renderer commands.
"""
from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path

from .intent_engine import INTENTS, normalize_intent

CONTRACT_PATH = Path(__file__).with_name("mobile_web") / "intent-visuals.json"
EXPRESSIONS = frozenset({"Neutral", "Smile", "Sad", "Angry", "Surprised", "Blink", "WinkL", "WinkR"})

@lru_cache(maxsize=1)
def visual_contract() -> dict:
    data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if data.get("version") != 1 or set(data.get("intents", {})) != INTENTS:
        raise ValueError("Live2D intent visual contract mismatches the dialogue contract")
    for variants in data["intents"].values():
        if not isinstance(variants, list) or len(variants) < 2:
            raise ValueError("Every intent needs two visual reaction variants")
        for variant in variants:
            if (not isinstance(variant, dict)
                    or variant.get("expression") not in EXPRESSIONS
                    or not isinstance(variant.get("text"), str)
                    or not 1 <= len(variant["text"]) <= 80):
                raise ValueError("Invalid Live2D reaction")
    return data

def reaction_for_intent(label: str, index: int = 0) -> dict:
    """Select a bounded expression and text; never execute an untrusted label."""
    intents = visual_contract()["intents"]
    variants = intents[normalize_intent(label)]
    return variants[index % len(variants)]

def public_visual_contract(enabled: bool) -> dict:
    """Return the same canonical palette to the mobile renderer."""
    data = visual_contract()
    return {"version": data["version"], "enabled": bool(enabled), "intents": data["intents"]}
