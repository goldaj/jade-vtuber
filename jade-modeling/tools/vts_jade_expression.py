"""Set Jade's performance expression through her VTube Studio model hotkeys."""

from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager, closing
import math
import os
from pathlib import Path
import sqlite3
import tempfile
from uuid import uuid4


NAMES = ("Smile", "Sad")
MODEL_NAMES = ("Jade_r21_v39", "Jade_r21_v40", "Jade_r21_v41", "Jade_r21_v42", "Jade_r21_v43", "Jade_r21_v44")
_STATE_DIR = Path(r"D:\Codex\tmp") if os.name == "nt" and Path("D:/Codex").is_dir() else Path(tempfile.gettempdir())
_STATE_DB = _STATE_DIR / "jade-vts-expression-holds.sqlite3"


@asynccontextmanager
async def _ordered_commands():
    """Serialize short VTS changes from the speech player and separate CLI processes."""
    _STATE_DB.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(_STATE_DB, isolation_level=None, timeout=0)) as db:
        deadline = asyncio.get_running_loop().time() + 6
        while True:
            try:
                db.execute("BEGIN IMMEDIATE")
                break
            except sqlite3.OperationalError as exc:
                if exc.sqlite_errorcode != sqlite3.SQLITE_BUSY or asyncio.get_running_loop().time() >= deadline:
                    raise
                await asyncio.sleep(0.02)
        db.execute("CREATE TABLE IF NOT EXISTS holds (model TEXT PRIMARY KEY, owner TEXT NOT NULL)")
        try:
            yield db
        finally:
            # Once a new command started sending events, a stale timer must
            # never undo it, even if the acknowledgement was lost.
            db.commit()


async def set_emotion(client, state, *, model_id, owner=None):
    """Apply a state and return its hold ID. A newer command supersedes its timer."""
    if state not in (*NAMES, "Neutral"):
        raise ValueError(f"Unknown Jade expression {state}")
    owner = owner or uuid4().hex
    async with _ordered_commands() as db:
        db.execute("INSERT OR REPLACE INTO holds (model, owner) VALUES (?, ?)", (model_id, owner))
        await _switch(client, state, model_id)
    return owner


async def _switch(client, state, model_id):
    """Use model hotkeys so an expression survives its requesting CLI's disconnection."""
    target = f"{state}.exp3.json" if state != "Neutral" else None
    result = await client.request("ExpressionStateRequest", {"details": False})
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
        current = (await client.request("ExpressionStateRequest", {"details": False}))["data"]
        if current.get("modelID") != model_id:
            raise RuntimeError("The active VTube Studio model changed")
        active = {row["file"] for row in current["expressions"] if row["active"]}
        if active & managed == expected:
            return
        await asyncio.sleep(0.05)
    raise RuntimeError(f"VTube Studio did not reach the requested expression {state}")


async def release(client, filename, model_id, *, owner=None):
    """End the matching hold even if the same smile was requested again later."""
    async with _ordered_commands() as db:
        if owner is not None:
            current = db.execute("SELECT owner FROM holds WHERE model = ?", (model_id,)).fetchone()
            if current != (owner,):
                return
        state = (await client.request("ExpressionStateRequest", {"details": False}))["data"]
        if state.get("modelLoaded") and state.get("modelID") == model_id:
            if any(row["file"] == filename and row["active"] for row in state["expressions"]):
                await client.request("ExpressionActivationRequest", {"expressionFile": filename, "active": False})
        if owner is not None:
            db.execute("DELETE FROM holds WHERE model = ? AND owner = ?", (model_id, owner))


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
        owner = uuid4().hex
        try:
            await set_emotion(client, args.state, model_id=model_id, owner=owner)
            await asyncio.sleep(args.seconds)
        finally:
            await release(client, f"{args.state}.exp3.json", model_id, owner=owner)


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
