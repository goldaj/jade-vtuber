"""Structured local turn logs. These contain potentially personal text."""
from __future__ import annotations

import json
import logging
import sys

LOG = logging.getLogger("jade.conversation")
_VOICE_INPUTS = frozenset(("discord_voice", "microphone"))
_VOICE_OUTPUTS = frozenset(("discord_voice", "local_audio", "mobile_audio"))
_TEXT_OUTPUTS = frozenset(("twitch_text", "discord_text", "local_http_text", "mobile_text", "console_text"))


def enable_console_logs() -> None:
    """Make selected conversation traces visible in local stderr."""
    if not LOG.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        LOG.addHandler(handler)
    LOG.setLevel(logging.INFO)
    LOG.propagate = False


def _write(payload: dict) -> None:
    # Control characters and newlines stay escaped within a single JSON record.
    LOG.info("%s", json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def record_input(turn: int, incoming) -> None:
    """Selected Runtime inputs only; no passive Discord channel traffic."""
    _write({
        "event": "input_selected", "turn": turn,
        "source_platform": incoming.platform,
        "source_modality": "voice" if incoming.platform in _VOICE_INPUTS or (
            incoming.platform == "mobile" and incoming.input_modality == "voice") else "text",
        "source_channel": incoming.channel,
        "source_author": incoming.author,
        "source_message_id": incoming.message_id,
        "input_text": incoming.text,
    })


def planned_destinations(reply, *, has_speech=False, audio_output="none",
                         discord_voice=False, twitch_text=False,
                         discord_text=False, local_http=False, mobile=False) -> tuple[str, ...]:
    """Classify intended external delivery, not an actual send receipt."""
    destinations = []
    platform = reply.source.platform
    if platform == "twitch" and twitch_text:
        destinations.append("twitch_text")
    if platform == "discord" and discord_text:
        destinations.append("discord_text")
    if platform == "local_http" and local_http:
        destinations.append("local_http_text")
    if platform == "mobile" and mobile:
        destinations.append("mobile_text")
        if reply.source.requested_speech:
            destinations.append("mobile_audio")
    if has_speech and platform != "mobile":
        if reply.spoken:
            if discord_voice and platform not in ("microphone", "local_http", "mobile") and not (
                    platform == "discord" and getattr(reply.source, "private_channel", False)):
                destinations.append("discord_voice")
        else:
            if audio_output == "ffplay":
                destinations.append("local_audio")
            if discord_voice and platform not in ("microphone", "local_http", "mobile") and not (
                    platform == "discord" and getattr(reply.source, "private_channel", False)):
                destinations.append("discord_voice")
    if not destinations:
        destinations.append("console_text")
    return tuple(destinations)


def record_reply(turn: int, reply, destinations) -> None:
    """Reconstruct the canonical intent prefix from parsed metadata."""
    targets = tuple(destinations)
    modes = [mode for mode, allowed in (("text", _TEXT_OUTPUTS), ("voice", _VOICE_OUTPUTS))
             if any(destination in allowed for destination in targets)]
    _write({
        "event": "reply_planned", "turn": turn,
        "reply_with_intent": f"[INTENT:{reply.intent}] {reply.text}",
        "intent": reply.intent,
        "output_modalities": modes,
        "output_destinations": list(targets),
        "delivery_status": "planned_not_confirmed",
    })


def record_outcome(turn: int, outcome: str) -> None:
    if outcome not in ("no_reply", "failed", "cancelled"):
        raise ValueError("invalid outcome")
    _write({"event": "turn_outcome", "turn": turn, "outcome": outcome})
