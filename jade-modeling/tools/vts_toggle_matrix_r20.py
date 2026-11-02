#!/usr/bin/env python3
"""Exercise Jade r20's complete VTube Studio hotkey contract in one short run."""

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
EXPECTED_HOTKEYS = (
    "Smile",
    "Sad",
    "Angry",
    "Surprised",
    "Blink",
    "WinkL",
    "WinkR",
    "Neutral",
)
EXPRESSION_FILES = {
    "Smile": "Smile.exp3.json",
    "Sad": "Sad.exp3.json",
    "Angry": "Angry.exp3.json",
    "Surprised": "Surprised.exp3.json",
    "Blink": "Blink.exp3.json",
    "WinkL": "WinkL.exp3.json",
    "WinkR": "WinkR.exp3.json",
}
OBSERVED = (
    "ParamEyeLOpen",
    "ParamEyeROpen",
    "ParamEarPoseL",
    "ParamEarPoseR",
    "ParamMouthForm",
    "ParamMouthOpenY",
    "ParamCheek",
    "ParamBrowLAngle",
    "ParamBrowRAngle",
)


async def _hotkeys(client: proof.VTSClient) -> dict[str, dict[str, Any]]:
    response = await client.request("HotkeysInCurrentModelRequest")
    rows = response.get("data", {}).get("availableHotkeys", [])
    result = {
        str(row.get("name")): row
        for row in rows
        if isinstance(row, dict) and row.get("name") in EXPECTED_HOTKEYS
    }
    if set(result) != set(EXPECTED_HOTKEYS):
        missing = sorted(set(EXPECTED_HOTKEYS) - set(result))
        extra = sorted(set(result) - set(EXPECTED_HOTKEYS))
        raise RuntimeError(f"hotkey matrix mismatch; missing={missing}, extra={extra}")
    return result


async def _trigger(
    client: proof.VTSClient,
    hotkeys: dict[str, dict[str, Any]],
    name: str,
) -> None:
    await client.request(
        "HotkeyTriggerRequest",
        {"hotkeyID": hotkeys[name]["hotkeyID"]},
    )


async def _active_files(client: proof.VTSClient) -> list[str]:
    response = await client.request("ExpressionStateRequest")
    rows = response.get("data", {}).get("expressions", [])
    return sorted(
        str(row.get("file"))
        for row in rows
        if isinstance(row, dict) and row.get("active")
    )


async def _values(client: proof.VTSClient) -> dict[str, float]:
    response = await client.request("Live2DParameterListRequest")
    rows = response.get("data", {}).get("parameters", [])
    result = {
        str(row.get("name")): float(row.get("value"))
        for row in rows
        if isinstance(row, dict) and row.get("name") in OBSERVED
    }
    missing = sorted(set(OBSERVED) - set(result))
    if missing:
        raise RuntimeError("runtime parameters missing: " + ", ".join(missing))
    return result


async def _hold_face_open(client: proof.VTSClient) -> None:
    """Keep tracking present and eyes open; P4 expressions still override it."""
    await client.request(
        "InjectParameterDataRequest",
        {
            "faceFound": True,
            "mode": "set",
            "parameterValues": [
                {"id": "EyeOpenLeft", "value": 1.0, "weight": 1.0},
                {"id": "EyeOpenRight", "value": 1.0, "weight": 1.0},
                {"id": "FaceAngleX", "value": 0.0, "weight": 1.0},
                {"id": "FaceAngleY", "value": 0.0, "weight": 1.0},
                {"id": "FaceAngleZ", "value": 0.0, "weight": 1.0},
            ],
        },
        timeout=2.0,
    )


async def _sample_window(
    client: proof.VTSClient,
    duration: float,
    hz: int = 30,
) -> list[dict[str, float]]:
    samples: list[dict[str, float]] = []
    loop = asyncio.get_running_loop()
    start = loop.time()
    frame_count = max(2, round(duration * hz) + 1)
    for frame in range(frame_count):
        target = start + frame / hz
        delay = target - loop.time()
        if delay > 0:
            await asyncio.sleep(delay)
        await _hold_face_open(client)
        samples.append(await _values(client))
    return samples


async def _wait_eyes_open(
    client: proof.VTSClient,
    timeout: float = 1.2,
) -> tuple[bool, float, dict[str, float]]:
    """Ignore a coincident random AutoBlink and confirm the neutral return."""
    loop = asyncio.get_running_loop()
    start = loop.time()
    latest = await _values(client)
    while loop.time() - start <= timeout:
        await _hold_face_open(client)
        latest = await _values(client)
        if min(latest["ParamEyeLOpen"], latest["ParamEyeROpen"]) >= 0.95:
            return True, loop.time() - start, latest
        await asyncio.sleep(0.025)
    return False, loop.time() - start, latest


def _range(samples: list[dict[str, float]], name: str) -> dict[str, float]:
    values = [sample[name] for sample in samples]
    return {
        "min": min(values),
        "max": max(values),
        "final": values[-1],
    }


async def _neutral(
    client: proof.VTSClient,
    hotkeys: dict[str, dict[str, Any]],
    settle: float = 0.45,
) -> tuple[list[str], dict[str, float]]:
    await _trigger(client, hotkeys, "Neutral")
    samples = await _sample_window(client, settle, hz=20)
    return await _active_files(client), samples[-1]


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
        hotkeys = await _hotkeys(client)

        await _neutral(client, hotkeys)
        persistent: dict[str, Any] = {}
        for name in ("Smile", "Sad", "Angry", "Surprised"):
            await _trigger(client, hotkeys, name)
            samples = await _sample_window(client, 0.48, hz=args.hz)
            active = await _active_files(client)
            neutral_active, neutral_values = await _neutral(client, hotkeys)
            persistent[name] = {
                "active_files": active,
                "ear_pose_l": _range(samples, "ParamEarPoseL"),
                "ear_pose_r": _range(samples, "ParamEarPoseR"),
                "mouth_form": _range(samples, "ParamMouthForm"),
                "mouth_open": _range(samples, "ParamMouthOpenY"),
                "neutral_active_files": neutral_active,
                "neutral_ear_pose_l": neutral_values["ParamEarPoseL"],
                "neutral_ear_pose_r": neutral_values["ParamEarPoseR"],
            }

        transient: dict[str, Any] = {}
        for name, duration in (("Blink", 0.70), ("WinkL", 1.0), ("WinkR", 1.0)):
            await _neutral(client, hotkeys, settle=0.25)
            await _trigger(client, hotkeys, name)
            active_initial = await _active_files(client)
            samples = await _sample_window(client, duration, hz=args.hz)
            active_final = await _active_files(client)
            returned_open, returned_open_after, returned_values = await _wait_eyes_open(client)
            transient[name] = {
                "active_files_immediately_after_trigger": active_initial,
                "active_files_after_auto_return": active_final,
                "eye_l": _range(samples, "ParamEyeLOpen"),
                "eye_r": _range(samples, "ParamEyeROpen"),
                "returned_open": returned_open,
                "returned_open_after_seconds": returned_open_after,
                "returned_eye_l": returned_values["ParamEyeLOpen"],
                "returned_eye_r": returned_values["ParamEyeROpen"],
                "maximum_left_minus_right": max(
                    sample["ParamEyeLOpen"] - sample["ParamEyeROpen"]
                    for sample in samples
                ),
                "maximum_right_minus_left": max(
                    sample["ParamEyeROpen"] - sample["ParamEyeLOpen"]
                    for sample in samples
                ),
            }

        final_active, final_values = await _neutral(client, hotkeys, settle=0.50)

    persistent_exact = all(
        data["active_files"] == [EXPRESSION_FILES[name]]
        and not data["neutral_active_files"]
        for name, data in persistent.items()
    )
    criteria = {
        "correct_model_loaded": True,
        "eight_expected_hotkeys_available": set(hotkeys) == set(EXPECTED_HOTKEYS),
        "persistent_expressions_are_exclusive": persistent_exact,
        "neutral_clears_every_expression": not final_active,
        "smile_stays_below_surprise_art_gate": max(
            persistent["Smile"][side]["final"]
            for side in ("ear_pose_l", "ear_pose_r")
        ) < 0.66,
        "sad_lowers_both_ears": max(
            persistent["Sad"][side]["final"]
            for side in ("ear_pose_l", "ear_pose_r")
        ) <= -0.90,
        "angry_lowers_both_ears": max(
            persistent["Angry"][side]["final"]
            for side in ("ear_pose_l", "ear_pose_r")
        ) <= -0.42,
        "surprise_reaches_new_ear_art": min(
            persistent["Surprised"][side]["final"]
            for side in ("ear_pose_l", "ear_pose_r")
        ) >= 0.94,
        "blink_closes_both_eyes": max(
            transient["Blink"][eye]["min"] for eye in ("eye_l", "eye_r")
        ) <= 0.05,
        "blink_auto_returns_open": transient["Blink"]["returned_open"]
        and not transient["Blink"]["active_files_after_auto_return"],
        "wink_l_closes_only_left": transient["WinkL"]["eye_l"]["min"] <= 0.05
        and transient["WinkL"]["maximum_right_minus_left"] >= 0.80,
        "wink_r_closes_only_right": transient["WinkR"]["eye_r"]["min"] <= 0.05
        and transient["WinkR"]["maximum_left_minus_right"] >= 0.80,
        "winks_auto_return_open": all(
            transient[name]["returned_open"]
            and not transient[name]["active_files_after_auto_return"]
            for name in ("WinkL", "WinkR")
        ),
        "final_neutral_has_no_positive_surprise_pose": max(
            final_values["ParamEarPoseL"], final_values["ParamEarPoseR"]
        ) <= 0.02,
    }
    return {
        "schema": "jade.vts-toggle-matrix-r20.v1",
        "status": "ok" if all(criteria.values()) else "needs_tuning",
        "model_id": EXPECTED_MODEL_ID,
        "criteria": criteria,
        "persistent": persistent,
        "transient": transient,
        "final": {
            "active_files": final_active,
            "values": final_values,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default=proof.DEFAULT_ENDPOINT)
    parser.add_argument("--credentials", type=Path, default=proof.DEFAULT_CREDENTIALS)
    parser.add_argument("--hz", type=int, choices=(20, 30, 40), default=30)
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
