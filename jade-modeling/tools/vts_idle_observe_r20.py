#!/usr/bin/env python3
"""Observe one real r20 tracking-lost idle loop through the VTube Studio API."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from websockets.asyncio.client import connect


TOOLS_DIR = Path(__file__).resolve(strict=True).parent
sys.path.insert(0, str(TOOLS_DIR))
import vts_direct_proof_driver as proof


EXPECTED_MODEL_ID = "ba8513efdb5b5c8389fa5aa43a663dd5"
OBSERVED = (
    "ParamAngleX",
    "ParamAngleY",
    "ParamAngleZ",
    "ParamEyeBallX",
    "ParamEyeBallY",
    "ParamEyeLOpen",
    "ParamEyeROpen",
    "ParamBodyAngleX",
    "ParamBodyAngleY",
    "ParamBodyAngleZ",
    "ParamBreath",
    "ParamEarPoseL",
    "ParamEarPoseR",
    "ParamEarSwingL",
    "ParamEarSwingR",
    "ParamHairBangC",
    "ParamHairBangCTip",
    "ParamHairBackC",
    "ParamHairBackCLDetail",
    "ParamHairBackCRDetail",
)


async def _values(client: proof.VTSClient) -> dict[str, float]:
    response = await client.request("Live2DParameterListRequest")
    parameters = response.get("data", {}).get("parameters", [])
    values = {
        str(row.get("name")): float(row.get("value"))
        for row in parameters
        if isinstance(row, dict) and row.get("name") in OBSERVED
    }
    missing = sorted(set(OBSERVED) - set(values))
    if missing:
        raise RuntimeError("runtime parameters missing: " + ", ".join(missing))
    return values


async def _neutral(client: proof.VTSClient) -> None:
    response = await client.request("HotkeysInCurrentModelRequest")
    hotkeys = response.get("data", {}).get("availableHotkeys", [])
    matches = [
        row
        for row in hotkeys
        if isinstance(row, dict) and row.get("name") == "Neutral"
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one Neutral hotkey, got {len(matches)}")
    await client.request("HotkeyTriggerRequest", {"hotkeyID": matches[0]["hotkeyID"]})


async def _tracking_absent(client: proof.VTSClient) -> None:
    await client.request(
        "InjectParameterDataRequest",
        {
            "faceFound": False,
            "mode": "set",
            "parameterValues": [
                # VTube Studio rejects an empty injection payload.  A zero-
                # weight input supplies a valid row without altering the rig.
                # FacePositionX is intentionally not mapped by Jade.  Using it
                # keeps the payload valid without activating a P2 provider on
                # any Live2D output authored by the idle motion.
                {"id": "FacePositionX", "value": 0.0, "weight": 0.0}
            ],
        },
        timeout=2.0,
    )


def _event_count(values: Sequence[float], threshold: float) -> int:
    count = 0
    active = False
    for value in values:
        now = value <= threshold
        if now and not active:
            count += 1
        active = now
    return count


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    credentials = proof._load_credentials(args.credentials)
    if credentials is None:
        raise RuntimeError("VTube Studio credentials are missing")
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
        if int(current.get("numberOfLive2DParameters", -1)) != 70:
            raise RuntimeError("Jade r20 must expose 70 parameters")

        await _neutral(client)
        # Keep faceFound false long enough for the configured 2.5 s fallback
        # delay, then observe slightly more than one complete 30 s loop.
        settle_start = asyncio.get_running_loop().time()
        while asyncio.get_running_loop().time() - settle_start < args.settle:
            await _tracking_absent(client)
            await asyncio.sleep(0.05)

        samples: list[dict[str, float]] = []
        loop = asyncio.get_running_loop()
        start = loop.time()
        frames = round(args.duration * args.hz) + 1
        maximum_lag = 0.0
        for frame in range(frames):
            target = start + frame / args.hz
            delay = target - loop.time()
            if delay > 0:
                await asyncio.sleep(delay)
            maximum_lag = max(maximum_lag, max(0.0, loop.time() - target))
            await _tracking_absent(client)
            samples.append(await _values(client))

        expression_state = await client.request("ExpressionStateRequest")

    ranges = {
        name: {
            "min": min(sample[name] for sample in samples),
            "max": max(sample[name] for sample in samples),
            "span": max(sample[name] for sample in samples) - min(sample[name] for sample in samples),
        }
        for name in OBSERVED
    }
    left = [sample["ParamEarPoseL"] for sample in samples]
    right = [sample["ParamEarPoseR"] for sample in samples]
    active_expressions = [
        row.get("file")
        for row in expression_state.get("data", {}).get("expressions", [])
        if isinstance(row, dict) and row.get("active")
    ]
    criteria = {
        "correct_model_loaded": True,
        # Auto-blink is rendered between API samples.  At 15 Hz, a sampled
        # value <= .12 demonstrates the descent through the r09 handoff; the
        # explicit Blink hotkey is tested separately for exact closure.
        "idle_auto_blink_observed": max(ranges[name]["min"] for name in ("ParamEyeLOpen", "ParamEyeROpen")) <= 0.12,
        "eyes_return_open": min(ranges[name]["max"] for name in ("ParamEyeLOpen", "ParamEyeROpen")) >= 0.97,
        "at_least_one_random_idle_blink": min(_event_count([sample[name] for sample in samples], 0.15) for name in ("ParamEyeLOpen", "ParamEyeROpen")) >= 1,
        "left_twitch_visible_in_runtime": min(left) <= -0.20,
        "right_twitch_visible_in_runtime": min(right) <= -0.18,
        "twitches_are_asymmetric": max(abs(a - b) for a, b in zip(left, right)) >= 0.18,
        "surprise_never_leaks_in_idle": max(max(left), max(right)) <= 0.02,
        "head_is_active": ranges["ParamAngleX"]["span"] >= 5.0,
        "ear_physics_remains_active": min(ranges[name]["span"] for name in ("ParamEarSwingL", "ParamEarSwingR")) >= 0.01,
        "front_and_rear_hair_remain_active": ranges["ParamHairBangC"]["span"] >= 0.01 and ranges["ParamHairBackC"]["span"] >= 0.01,
        "no_expression_left_active": not active_expressions,
    }
    return {
        "schema": "jade.vts-idle-observation-r20.v1",
        "status": "ok" if all(criteria.values()) else "needs_visual_review",
        "model_id": EXPECTED_MODEL_ID,
        "settle_seconds": args.settle,
        "duration_seconds": args.duration,
        "sample_hz": args.hz,
        "sample_count": len(samples),
        "maximum_lag_ms": round(maximum_lag * 1000, 3),
        "criteria": criteria,
        "blink_counts": {
            name: _event_count([sample[name] for sample in samples], 0.15)
            for name in ("ParamEyeLOpen", "ParamEyeROpen")
        },
        "maximum_ear_pose_asymmetry": max(abs(a - b) for a, b in zip(left, right)),
        "ranges": ranges,
        "active_expressions": active_expressions,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default=proof.DEFAULT_ENDPOINT)
    parser.add_argument("--credentials", type=Path, default=proof.DEFAULT_CREDENTIALS)
    parser.add_argument("--settle", type=float, default=3.0)
    parser.add_argument("--duration", type=float, default=31.0)
    parser.add_argument("--hz", type=int, choices=(10, 15, 20), default=15)
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
