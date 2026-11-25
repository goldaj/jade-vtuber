"""Set Jade's performance expression through her VTube Studio model hotkeys."""

from __future__ import annotations

import argparse
import asyncio
import math
from pathlib import Path


NAMES = ("Smile", "Sad")
MODEL_NAMES = ("Jade_r21_v39", "Jade_r21_v40")

async def set_emotion(client, state, *, model_id):
    """Switch through enabled model hotkeys, preserving independent user expressions."""
    if state not in (*NAMES, "Neutral"):
        raise ValueError(f"Unknown Jade expression {state}")
    target = f"{state}.exp3.json" if state != "Neutral" else None
    result = await client.request("ExpressionStateRequest")
    current = result["data"]
    if not current.get("modelLoaded") or current.get("modelID") != model_id:
        raise RuntimeError("The expected Jade model is not active")

    actions = []
    for name in NAMES:
        filename = f"{name}.exp3.json"
        row, = (expr for expr in current["expressions"] if expr["file"] == filename)
        if row["active"] != (filename == target):
            actions.append((filename == target, filename))
    if not actions:
        return
    hotkeys = (await client.request("HotkeysInCurrentModelRequest"))["data"]
    if hotkeys.get("modelID") != model_id:
        raise RuntimeError("The active VTube Studio model changed")
    triggers = []
    for _, filename in sorted(actions):
        matching = [row["hotkeyID"] for row in hotkeys["availableHotkeys"]
                    if row["type"] == "ToggleExpression" and row["file"] == filename]
        if not matching:
            raise ValueError(f"No enabled hotkey for {filename}")
        triggers.append(matching[0])
    for hotkey_id in triggers:
        await client.request("HotkeyTriggerRequest", {"hotkeyID": hotkey_id})
    expected = {target} if target else set()
    managed = {f"{name}.exp3.json" for name in NAMES}
    for _ in range(20):
        current = (await client.request("ExpressionStateRequest"))["data"]
        if current.get("modelID") != model_id:
            raise RuntimeError("The active VTube Studio model changed")
        active = {row["file"] for row in current["expressions"] if row["active"]}
        if active & managed == expected:
            return
        await asyncio.sleep(0.05)
    raise RuntimeError(f"VTube Studio did not reach the requested expression {state}")


async def release(client, filename, model_id):
    """End only our timed hold, preserving later choices and model changes."""
    state = (await client.request("ExpressionStateRequest"))["data"]
    if not state.get("modelLoaded") or state.get("modelID") != model_id:
        return
    if any(row["file"] == filename and row["active"] for row in state["expressions"]):
        await client.request("ExpressionActivationRequest", {"expressionFile": filename, "active": False})


async def run(args):
    from websockets.asyncio.client import connect
    from vts_model_switch import DEFAULT_CREDENTIALS, DEFAULT_ENDPOINT, VTSClient, _authenticate, _load_credentials

    credentials = _load_credentials(args.credentials or DEFAULT_CREDENTIALS)
    if not credentials:
        raise RuntimeError("Aucun identifiant VTube Studio récupérable.")
    async with connect(args.endpoint or DEFAULT_ENDPOINT, open_timeout=5, close_timeout=2) as websocket:
        client = VTSClient(websocket)
        await _authenticate(client, credentials)
        current = (await client.request("CurrentModelRequest"))["data"]
        if not current.get("modelLoaded") or current.get("modelName") not in MODEL_NAMES:
            raise RuntimeError(f"Le modèle actif doit être {' ou '.join(MODEL_NAMES)}.")
        model_id = current["modelID"]
        if args.seconds is None:
            await set_emotion(client, args.state, model_id=model_id)
            return
        try:
            await set_emotion(client, args.state, model_id=model_id)
            await asyncio.sleep(args.seconds)
        finally:
            await release(client, f"{args.state}.exp3.json", model_id)


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("state", choices=(*NAMES, "Neutral"))
    cli.add_argument("--seconds", type=float, help="hold Smile or Sad for this long, then release it")
    cli.add_argument("--endpoint", help="local VTube Studio API WebSocket URL")
    cli.add_argument("--credentials", type=Path, help="existing private API credentials to reuse")
    args = cli.parse_args()
    if args.seconds is not None and (args.state == "Neutral" or not math.isfinite(args.seconds) or args.seconds <= 0):
        cli.error("--seconds requires Smile or Sad and a positive, finite duration")
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        raise SystemExit(130)
    except (RuntimeError, OSError) as exc:
        cli.exit(1, str(exc) + "\n")
