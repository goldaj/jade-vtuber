"""Turn-level traces: short IDE summaries and full local session diagnostics."""
from __future__ import annotations

import json
import logging
import re
import sys

from .session_logging import event, session_file, summary

LOG = logging.getLogger("jade.conversation")
_VOICE_INPUTS = frozenset(("discord_voice", "microphone"))
_VOICE_OUTPUTS = frozenset(("discord_voice", "local_audio", "mobile_audio"))
_TEXT_OUTPUTS = frozenset(("twitch_text", "discord_text", "local_http_text", "mobile_text", "console_text"))


def enable_console_logs(*, enable_latency=False) -> None:
    """Preserve standalone-console compatibility; use root session handlers in live mode."""
    if session_file() is None:
        if not LOG.handlers:
            handler = logging.StreamHandler(sys.stderr)
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
            LOG.addHandler(handler)
        LOG.propagate = False
    else:
        LOG.propagate = True
    LOG.setLevel(logging.INFO)
    if enable_latency:
        latency = logging.getLogger("jade.latency")
        if session_file() is None:
            if not latency.handlers:
                handler = logging.StreamHandler(sys.stderr)
                handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
                latency.addHandler(handler)
            latency.propagate = False
        else:
            latency.propagate = True
        latency.setLevel(logging.INFO)


def _write(payload: dict) -> None:
    LOG.info("%s", json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def _is_private(incoming) -> bool:
    return (incoming.platform in ("mobile", "microphone", "local_http")
            or (incoming.platform == "discord" and incoming.private_channel))


def _input_mode(incoming):
    return ("voice" if incoming.platform in _VOICE_INPUTS or
            (incoming.platform == "mobile" and incoming.input_modality == "voice")
            else "text")


def record_input(turn: int, incoming) -> None:
    """Trace each selected input, including the exact content in the local file."""
    private = _is_private(incoming)
    text = incoming.text
    if re.match(r"^!jade-memoire\s+confirmer(?:\s|$)", text.strip(), re.I):
        text = "!jade-memoire confirmer [code masqué]"
    channel = "[privé]" if private else incoming.channel
    source = {
        "turn": turn, "source_platform": incoming.platform,
        "source_modality": _input_mode(incoming),
        "source_channel": channel,
    }
    summary("input_selected", **source)
    event("input_selected", **source,
          source_author="[privé]" if private else incoming.author,
          source_message_id="[privé]" if private else incoming.message_id,
          source_is_private=private, input_text=text)
    # Preserve original structured log contract for callers outside session mode.
    if session_file() is None:
        _write({"event": "input_selected", **source,
                "source_author": "[privé]" if private else incoming.author,
                "source_message_id": "[privé]" if private else incoming.message_id,
                "input_text": "[contenu privé masqué]" if private else text})


def planned_destinations(reply, *, has_speech=False, audio_output="none",
                         discord_voice=False, twitch_text=False,
                         discord_text=False, local_http=False, mobile=False) -> tuple[str, ...]:
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
    if has_speech and platform == "discord_voice" and discord_voice:
        destinations.append("discord_voice")
    elif has_speech and platform in ("microphone", "console") and audio_output == "ffplay":
        destinations.append("local_audio")
    if not destinations:
        destinations.append("console_text")
    return tuple(destinations)


def record_reply(turn: int, reply, destinations) -> None:
    targets = tuple(destinations)
    modes = [mode for mode, allowed in (("text", _TEXT_OUTPUTS), ("voice", _VOICE_OUTPUTS))
             if any(destination in allowed for destination in targets)]
    data = {
        "turn": turn, "source_platform": reply.source.platform,
        "output_channel": "[privé]" if _is_private(reply.source) else reply.source.channel,
        "output_modalities": modes,
        "output_destinations": list(targets), "intent": reply.intent,
        "delivery_status": "planned_not_confirmed",
    }
    summary("reply_planned", **data)
    event("reply_planned", **data, output_text=reply.text,
          reply_with_intent=f"[INTENT:{reply.intent}] {reply.text}")
    if session_file() is None:
        _write({"event": "reply_planned", **data,
                "reply_with_intent": ("[contenu privé masqué]"
                                      if _is_private(reply.source)
                                      else f"[INTENT:{reply.intent}] {reply.text}")})


def record_delivery(turn: int, status: str, *, destinations=(), reason="") -> None:
    data = {"turn": turn, "delivery_status": status,
            "output_destinations": list(destinations)}
    if reason:
        data["reason"] = reason
    summary("delivery_outcome", **data)
    event("delivery_outcome", **data)


_DELIVERY_PROOFS = {
    ("transport_accepted", "discord_text"): "discord_api",
    ("playback_completed", "discord_voice"): "discord_audio_consumer",
    ("playback_completed", "local_audio"): "ffplay_exit_zero",
}


def record_delivery_evidence(turn: int, stage: str, destination: str, *,
                             proof: str) -> None:
    """Evidence that a *specific* transport action happened, not user receipt.

    A reply planned for a destination, or handed to a callback, is NEVER
    counted as delivered. The only supported stages are explicit positive
    observations from the corresponding transport. No message text or
    personal identity is written into operational evidence.
    """
    if type(turn) is not int or turn < 0 or not isinstance(stage, str) or not isinstance(destination, str):
        raise ValueError("invalid delivery evidence")
    if _DELIVERY_PROOFS.get((stage, destination)) != proof:
        raise ValueError("unsupported delivery proof")
    data = {"turn": turn, "destination": destination,
            "delivery_stage": stage, "evidence": proof}
    summary("delivery_evidence", **data)
    event("delivery_evidence", **data)


def record_outcome(turn: int, outcome: str) -> None:
    if outcome not in ("no_reply", "failed", "cancelled"):
        raise ValueError("invalid outcome")
    summary("turn_outcome", turn=turn, outcome=outcome)
    event("turn_outcome", turn=turn, outcome=outcome)
    if session_file() is None:
        _write({"event": "turn_outcome", "turn": turn, "outcome": outcome})
