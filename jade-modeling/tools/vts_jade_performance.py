"""Drive Jade's existing VTS model from newline-delimited playback events.

Accepts the renderer's mouth/expression/stop messages. For interruptible speech,
send start with a unique id, then tagged mouth, expression, and end or interrupt
messages. Untagged mouth/expression messages are also accepted for ordered
playback sources. The producer sends levels at playback time.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
from contextlib import AsyncExitStack
from pathlib import Path

from websockets.asyncio.client import connect

from vts_jade_expression import NAMES, set_emotion
from vts_model_switch import DEFAULT_CREDENTIALS, DEFAULT_ENDPOINT, VTSClient, _authenticate, _load_credentials


class Performance:
    """Coalesce input to the latest pose of the active utterance."""

    def __init__(self):
        self.utterance = None
        self.level = 0.0
        self.last_level = None
        self.emotion = "Neutral"
        self.expression_changed = asyncio.Event()
        self.expression_changed.set()
        self.closing = False

    def accept(self, event):
        kind = event["type"]
        token = event.get("id")
        if kind == "stop":
            self.closing = True
        elif kind == "start":
            if not isinstance(token, str) or not token:
                raise ValueError("start requires a unique nonempty id")
            if token == self.utterance:
                return
        elif token is not None and token != self.utterance:
            return
        if kind in ("start", "end", "interrupt", "stop"):
            self.utterance = token if kind == "start" else None
            self.level = 0.0
            self.last_level = asyncio.get_running_loop().time()
            emotion = event.get("expression", "Neutral") if kind == "start" else "Neutral"
        elif kind == "expression":
            emotion = event["value"]
        elif kind == "mouth":
            value = float(event["value"])
            if not math.isfinite(value):
                raise ValueError("mouth requires a finite number")
            self.level = min(1.0, max(0.0, value))
            self.last_level = asyncio.get_running_loop().time()
            return
        else:
            raise ValueError(f"Unknown playback event {kind!r}")
        if emotion not in (*NAMES, "Neutral"):
            raise ValueError(f"Unknown expression {emotion!r}")
        if emotion != self.emotion or self.closing:
            self.emotion = emotion
            self.expression_changed.set()

    async def mouth_worker(self, client, model_id):
        loop = asyncio.get_running_loop()
        previous = loop.time()
        opening = 0.0
        last_sent = None
        while True:
            now = loop.time()
            dt = now - previous
            previous = now
            age = math.inf if self.last_level is None else now - self.last_level
            target = self.level if age < 0.18 else 0.0
            lag = 0.018 if target > opening else 0.028
            opening += (target - opening) * -math.expm1(-dt / lag)
            if abs(target - opening) < 0.003:
                opening = target
            if self.last_level is not None and (age < 0.18 or last_sent != opening):
                current = (await client.request("CurrentModelRequest"))["data"]
                if current.get("modelID") != model_id:
                    raise RuntimeError("The active VTube Studio model changed")
                await client.request("InjectParameterDataRequest", {
                    "mode": "set", "parameterValues": [{"id": "MouthOpen", "value": opening}]
                })
                last_sent = opening
            if self.closing and opening == 0.0:
                return
            await asyncio.sleep(max(0, now + 1 / 60 - loop.time()))

    async def expression_worker(self, client, model_id):
        while True:
            await self.expression_changed.wait()
            self.expression_changed.clear()
            target = self.emotion
            await set_emotion(client, target, model_id=model_id)
            if self.closing and target == self.emotion:
                return


async def perform(events, endpoint=DEFAULT_ENDPOINT, credentials=DEFAULT_CREDENTIALS):
    """Run one model performance. Events use the caller's playback clock."""
    auth = _load_credentials(credentials)
    if not auth:
        raise RuntimeError("No reusable VTube Studio credentials available")
    async with AsyncExitStack() as stack:
        clients = []
        for _ in range(2):
            ws = await stack.enter_async_context(connect(endpoint, open_timeout=5, close_timeout=2))
            client = VTSClient(ws)
            await _authenticate(client, auth)
            clients.append(client)
        mouth, face = clients
        current = (await mouth.request("CurrentModelRequest"))["data"]
        if current.get("modelName") not in ("Jade_r21_v43", "Jade_r21_v44"):
            raise RuntimeError("Load Jade_r21_v43 or Jade_r21_v44 in VTube Studio first")
        model_id = current["modelID"]
        state = Performance()
        async def receive():
            async for event in events:
                state.accept(event)
                if state.closing:
                    return
            state.accept({"type": "stop"})
        try:
            async with asyncio.TaskGroup() as tasks:
                tasks.create_task(state.mouth_worker(mouth, model_id))
                tasks.create_task(state.expression_worker(face, model_id))
                await receive()
        except BaseException:
            # Normal completion already closes both outputs in their workers.
            # Cancellation or malformed input can interrupt them before that.
            if (await mouth.request("CurrentModelRequest"))["data"].get("modelID") == model_id:
                await mouth.request("InjectParameterDataRequest", {
                    "mode": "set", "parameterValues": [{"id": "MouthOpen", "value": 0.0}]
                })
                await set_emotion(face, "Neutral", model_id=model_id)
            raise


async def stdin_events():
    while line := await asyncio.to_thread(sys.stdin.readline):
        if line.strip():
            yield json.loads(line)


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    cli.add_argument("--credentials", type=Path, default=DEFAULT_CREDENTIALS)
    args = cli.parse_args()
    asyncio.run(perform(stdin_events(), args.endpoint, args.credentials))
