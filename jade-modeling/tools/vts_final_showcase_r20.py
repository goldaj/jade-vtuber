#!/usr/bin/env python3
"""Play one continuous final VTube Studio showcase for Jade r20."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
from pathlib import Path
from typing import Any, Sequence

from websockets.asyncio.client import connect


TOOLS_DIR = Path(__file__).resolve(strict=True).parent
sys.path.insert(0, str(TOOLS_DIR))
import vts_direct_proof_driver as proof


EXPECTED_MODEL_ID = "ba8513efdb5b5c8389fa5aa43a663dd5"
SECTIONS = (
    "TRACKING_LOST_IDLE",
    "BLINK",
    "WINK_LEFT",
    "WINK_RIGHT",
    "SMILE",
    "SAD",
    "ANGRY",
    "SURPRISE_EARS_HAIR_PHYSICS",
    "FINAL_NEUTRAL",
)


async def _hotkeys(client: proof.VTSClient) -> dict[str, str]:
    response = await client.request("HotkeysInCurrentModelRequest")
    rows = response.get("data", {}).get("availableHotkeys", [])
    result = {
        str(row.get("name")): str(row.get("hotkeyID"))
        for row in rows
        if isinstance(row, dict) and row.get("name") and row.get("hotkeyID")
    }
    expected = {"Smile", "Sad", "Angry", "Surprised", "Blink", "WinkL", "WinkR", "Neutral"}
    if set(result) != expected:
        raise RuntimeError(f"unexpected hotkey matrix: {sorted(result)}")
    return result


async def _trigger(client: proof.VTSClient, hotkeys: dict[str, str], name: str) -> None:
    await client.request("HotkeyTriggerRequest", {"hotkeyID": hotkeys[name]})


async def _tracking_absent(client: proof.VTSClient) -> None:
    await client.request(
        "InjectParameterDataRequest",
        {
            "faceFound": False,
            "mode": "set",
            "parameterValues": [
                {"id": "FacePositionX", "value": 0.0, "weight": 0.0}
            ],
        },
        timeout=2.0,
    )


async def _tracking_present(
    client: proof.VTSClient,
    *,
    angle_x: float = 0.0,
    angle_y: float = 0.0,
    angle_z: float = 0.0,
) -> None:
    await client.request(
        "InjectParameterDataRequest",
        {
            "faceFound": True,
            "mode": "set",
            "parameterValues": [
                {"id": "EyeOpenLeft", "value": 1.0, "weight": 1.0},
                {"id": "EyeOpenRight", "value": 1.0, "weight": 1.0},
                {"id": "FaceAngleX", "value": angle_x, "weight": 1.0},
                {"id": "FaceAngleY", "value": angle_y, "weight": 1.0},
                {"id": "FaceAngleZ", "value": angle_z, "weight": 1.0},
            ],
        },
        timeout=2.0,
    )


async def _hold(
    client: proof.VTSClient,
    seconds: float,
    fps: int,
    injector,
) -> float:
    loop = asyncio.get_running_loop()
    start = loop.time()
    maximum_lag = 0.0
    frame_count = max(1, round(seconds * fps))
    for frame in range(frame_count):
        target = start + frame / fps
        delay = target - loop.time()
        if delay > 0:
            await asyncio.sleep(delay)
        maximum_lag = max(maximum_lag, max(0.0, loop.time() - target))
        await injector(client)
    final_target = start + seconds
    delay = final_target - loop.time()
    if delay > 0:
        await asyncio.sleep(delay)
    return maximum_lag


def _smoothstep(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def _showcase_head(timestamp: float, duration: float) -> tuple[float, float, float]:
    phase = min(1.0, max(0.0, timestamp / duration))
    envelope = math.sin(math.pi * phase) ** 0.55
    sweep = math.sin(phase * math.tau * 1.75)
    counter = math.sin(phase * math.tau * 1.75 + 0.52)
    return 27.0 * envelope * sweep, 7.0 * envelope * counter, 10.0 * envelope * sweep


async def _head_performance(
    client: proof.VTSClient,
    seconds: float,
    fps: int,
) -> float:
    loop = asyncio.get_running_loop()
    start = loop.time()
    maximum_lag = 0.0
    frame_count = round(seconds * fps) + 1
    for frame in range(frame_count):
        timestamp = min(seconds, frame / fps)
        target = start + timestamp
        delay = target - loop.time()
        if delay > 0:
            await asyncio.sleep(delay)
        maximum_lag = max(maximum_lag, max(0.0, loop.time() - target))
        angle_x, angle_y, angle_z = _showcase_head(timestamp, seconds)
        await _tracking_present(
            client,
            angle_x=angle_x,
            angle_y=angle_y,
            angle_z=angle_z,
        )
    return maximum_lag


async def _active_files(client: proof.VTSClient) -> list[str]:
    response = await client.request("ExpressionStateRequest")
    return sorted(
        str(row.get("file"))
        for row in response.get("data", {}).get("expressions", [])
        if isinstance(row, dict) and row.get("active")
    )


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    credentials = proof._load_credentials(args.credentials)
    if credentials is None:
        raise RuntimeError("VTube Studio credentials are missing")
    timings: dict[str, float] = {}
    maximum_lag = 0.0

    async with connect(
        args.endpoint,
        open_timeout=5.0,
        close_timeout=2.0,
        max_size=4 * 1024 * 1024,
    ) as websocket:
        client = proof.VTSClient(websocket)
        await proof._authenticate(client, credentials)
        current = (await client.request("CurrentModelRequest")).get("data", {})
        if current.get("modelID") != EXPECTED_MODEL_ID:
            raise RuntimeError("Jade r20 is not the active VTube Studio model")
        hotkeys = await _hotkeys(client)

        await _trigger(client, hotkeys, "Neutral")
        print("SECTION TRACKING_LOST_IDLE", flush=True)
        timings["TRACKING_LOST_IDLE"] = 20.8
        maximum_lag = max(
            maximum_lag,
            await _hold(client, timings["TRACKING_LOST_IDLE"], args.fps, _tracking_absent),
        )

        await _hold(client, 0.55, args.fps, _tracking_present)
        for section, hotkey, seconds in (
            ("BLINK", "Blink", 0.75),
            ("WINK_LEFT", "WinkL", 0.95),
            ("WINK_RIGHT", "WinkR", 0.95),
        ):
            print(f"SECTION {section}", flush=True)
            await _trigger(client, hotkeys, hotkey)
            timings[section] = seconds
            maximum_lag = max(
                maximum_lag,
                await _hold(client, seconds, args.fps, _tracking_present),
            )

        for section, hotkey in (("SMILE", "Smile"), ("SAD", "Sad"), ("ANGRY", "Angry")):
            print(f"SECTION {section}", flush=True)
            await _trigger(client, hotkeys, "Neutral")
            await _hold(client, 0.30, args.fps, _tracking_present)
            await _trigger(client, hotkeys, hotkey)
            timings[section] = 0.90
            maximum_lag = max(
                maximum_lag,
                await _hold(client, 0.90, args.fps, _tracking_present),
            )

        print("SECTION SURPRISE_EARS_HAIR_PHYSICS", flush=True)
        await _trigger(client, hotkeys, "Neutral")
        await _hold(client, 0.35, args.fps, _tracking_present)
        await _trigger(client, hotkeys, "Surprised")
        await _hold(client, 0.50, args.fps, _tracking_present)
        timings["SURPRISE_EARS_HAIR_PHYSICS"] = 4.4
        maximum_lag = max(
            maximum_lag,
            await _head_performance(client, 4.4, args.fps),
        )

        print("SECTION FINAL_NEUTRAL", flush=True)
        await _trigger(client, hotkeys, "Neutral")
        timings["FINAL_NEUTRAL"] = 1.2
        maximum_lag = max(
            maximum_lag,
            await _hold(client, 1.2, args.fps, _tracking_present),
        )
        active_files = await _active_files(client)
        final = (await client.request("CurrentModelRequest")).get("data", {})

    return {
        "schema": "jade.vts-final-showcase-r20.v1",
        "status": "ok" if not active_files else "needs_cleanup",
        "model_id": EXPECTED_MODEL_ID,
        "fps": args.fps,
        "sections": list(SECTIONS),
        "timings_seconds": timings,
        "maximum_injection_lag_ms": round(maximum_lag * 1000.0, 3),
        "final_active_expressions": active_files,
        "final_model_position": final.get("modelPosition"),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default=proof.DEFAULT_ENDPOINT)
    parser.add_argument("--credentials", type=Path, default=proof.DEFAULT_CREDENTIALS)
    parser.add_argument("--fps", type=int, choices=(24, 30, 60), default=30)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(list(argv) if argv is not None else None)
    report = asyncio.run(_run(args))
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8", newline="\n")
    print(payload, end="")
    return 0 if report["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
