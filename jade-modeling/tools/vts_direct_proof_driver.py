#!/usr/bin/env python3
"""Drive Jade's nine proof parameters through the official VTube Studio API.

VTube Studio's API injects *tracking inputs*, not Live2D output parameters.
For the proof to move the model, the active ``Jade.vtube.json`` must therefore
contain nine temporary 1:1 mappings whose ``Input`` and ``OutputLive2D`` names
match :data:`PARAMETER_SPECS`.  The script creates those nine custom tracking
inputs, injects the 24-second timeline at a deterministic cadence, restores
neutral values, and (by default) removes the temporary custom inputs.

The first authorization needs one explicit click on ``Allow`` in VTube Studio.
Use ``--request-token --authorize-only`` once; later runs reuse the saved token.
The token is never printed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from websockets.asyncio.client import ClientConnection, connect


API_NAME = "VTubeStudioPublicAPI"
API_VERSION = "1.0"
PLUGIN_NAME = "Jade Proof Driver"
PLUGIN_DEVELOPER = "goldaj"
DEFAULT_ENDPOINT = "ws://127.0.0.1:8001"
DEFAULT_MOTION = (
    Path(__file__).resolve().parents[1]
    / "reports"
    / "vtube_studio"
    / "Jade_professional_r06"
    / "Jade_explicit_proof.motion3.json"
)
DEFAULT_CREDENTIALS = (
    Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    / "JadeVTSProof"
    / "vts_api_credentials.json"
)


@dataclass(frozen=True)
class ParameterSpec:
    minimum: float
    maximum: float
    default: float


PARAMETER_SPECS: dict[str, ParameterSpec] = {
    "ParamEyeLOpen": ParameterSpec(0.0, 1.0, 1.0),
    "ParamEyeROpen": ParameterSpec(0.0, 1.0, 1.0),
    "ParamEarPoseL": ParameterSpec(-1.0, 1.0, 0.0),
    "ParamEarPoseR": ParameterSpec(-1.0, 1.0, 0.0),
    "ParamHairBackC": ParameterSpec(-1.0, 1.0, 0.0),
    "ParamHairBackLInner": ParameterSpec(-1.0, 1.0, 0.0),
    "ParamHairBackLOuter": ParameterSpec(-1.0, 1.0, 0.0),
    "ParamHairBackRInner": ParameterSpec(-1.0, 1.0, 0.0),
    "ParamHairBackROuter": ParameterSpec(-1.0, 1.0, 0.0),
}


class VTSAPIError(RuntimeError):
    """Raised when VTube Studio returns an APIError payload."""


class VTSClient:
    def __init__(self, websocket: ClientConnection) -> None:
        self.websocket = websocket
        self.sequence = 0

    async def request(
        self,
        message_type: str,
        data: dict[str, Any] | None = None,
        *,
        timeout: float = 5.0,
    ) -> dict[str, Any]:
        self.sequence += 1
        request_id = f"jade-proof-{self.sequence}"
        payload: dict[str, Any] = {
            "apiName": API_NAME,
            "apiVersion": API_VERSION,
            "requestID": request_id,
            "messageType": message_type,
        }
        if data is not None:
            payload["data"] = data
        await self.websocket.send(json.dumps(payload, separators=(",", ":")))

        async with asyncio.timeout(timeout):
            while True:
                response = json.loads(await self.websocket.recv())
                if response.get("requestID") != request_id:
                    continue
                if response.get("messageType") == "APIError":
                    details = response.get("data", {})
                    raise VTSAPIError(
                        f"{message_type}: API error {details.get('errorID')}: "
                        f"{details.get('message', 'unknown error')}"
                    )
                return response


@dataclass(frozen=True)
class LinearCurve:
    parameter_id: str
    points: tuple[tuple[float, float], ...]

    def value_at(self, timestamp: float) -> float:
        if timestamp <= self.points[0][0]:
            return self.points[0][1]
        for (left_t, left_v), (right_t, right_v) in zip(self.points, self.points[1:]):
            if timestamp <= right_t:
                span = right_t - left_t
                if span <= 0:
                    return right_v
                ratio = (timestamp - left_t) / span
                return left_v + ratio * (right_v - left_v)
        return self.points[-1][1]


def _load_linear_motion(path: Path) -> tuple[float, dict[str, LinearCurve]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    duration = float(payload["Meta"]["Duration"])
    curves: dict[str, LinearCurve] = {}
    for raw_curve in payload["Curves"]:
        parameter_id = raw_curve.get("Id")
        if raw_curve.get("Target") != "Parameter" or parameter_id not in PARAMETER_SPECS:
            continue
        raw_segments = raw_curve["Segments"]
        points: list[tuple[float, float]] = [
            (float(raw_segments[0]), float(raw_segments[1]))
        ]
        cursor = 2
        while cursor < len(raw_segments):
            segment_type = int(raw_segments[cursor])
            if segment_type != 0:
                raise ValueError(
                    f"{parameter_id}: only linear Cubism segments are supported; "
                    f"found type {segment_type}"
                )
            points.append(
                (float(raw_segments[cursor + 1]), float(raw_segments[cursor + 2]))
            )
            cursor += 3
        curves[parameter_id] = LinearCurve(parameter_id, tuple(points))

    missing = sorted(set(PARAMETER_SPECS) - set(curves))
    if missing:
        raise ValueError(f"Motion is missing required curves: {', '.join(missing)}")
    if abs(duration - 24.0) > 1e-6:
        raise ValueError(f"Proof motion must be 24.0 seconds, got {duration}")
    return duration, curves


def _load_credentials(path: Path) -> tuple[str, str, str] | None:
    environment_token = os.environ.get("VTS_AUTH_TOKEN")
    if environment_token:
        return PLUGIN_NAME, PLUGIN_DEVELOPER, environment_token.strip()
    if not path.is_file():
        return None
    raw = path.read_text(encoding="utf-8-sig").strip()
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return PLUGIN_NAME, PLUGIN_DEVELOPER, raw
    token = str(payload.get("authenticationToken", "")).strip()
    if not token:
        return None
    return (
        str(payload.get("pluginName", PLUGIN_NAME)),
        str(payload.get("pluginDeveloper", PLUGIN_DEVELOPER)),
        token,
    )


def _save_credentials(path: Path, token: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pluginName": PLUGIN_NAME,
        "pluginDeveloper": PLUGIN_DEVELOPER,
        "authenticationToken": token,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


async def _obtain_token(client: VTSClient, path: Path) -> tuple[str, str, str]:
    print(
        "ACTION_UI_REQUIRED: dans VTube Studio, cliquer une fois sur "
        "« Allow » pour Jade Proof Driver.",
        flush=True,
    )
    response = await client.request(
        "AuthenticationTokenRequest",
        {"pluginName": PLUGIN_NAME, "pluginDeveloper": PLUGIN_DEVELOPER},
        timeout=180.0,
    )
    token = str(response.get("data", {}).get("authenticationToken", "")).strip()
    if not token:
        raise VTSAPIError("VTube Studio returned no authentication token")
    _save_credentials(path, token)
    print(f"TOKEN_SAVED={path} (secret masqué)", flush=True)
    return PLUGIN_NAME, PLUGIN_DEVELOPER, token


async def _authenticate(
    client: VTSClient,
    credentials: tuple[str, str, str],
) -> None:
    plugin_name, plugin_developer, token = credentials
    response = await client.request(
        "AuthenticationRequest",
        {
            "pluginName": plugin_name,
            "pluginDeveloper": plugin_developer,
            "authenticationToken": token,
        },
    )
    data = response.get("data", {})
    if not data.get("authenticated"):
        raise VTSAPIError(f"Authentication failed: {data.get('reason', 'unknown reason')}")


async def _create_inputs(client: VTSClient) -> None:
    for parameter_id, spec in PARAMETER_SPECS.items():
        await client.request(
            "ParameterCreationRequest",
            {
                "parameterName": parameter_id,
                "explanation": "Temporary deterministic Jade animation proof input.",
                "min": spec.minimum,
                "max": spec.maximum,
                "defaultValue": spec.default,
            },
        )


async def _delete_inputs(client: VTSClient) -> None:
    for parameter_id in PARAMETER_SPECS:
        try:
            await client.request(
                "ParameterDeletionRequest", {"parameterName": parameter_id}
            )
        except VTSAPIError as error:
            print(f"CLEANUP_WARNING {parameter_id}: {error}", file=sys.stderr)


def _values_payload(values: dict[str, float]) -> dict[str, Any]:
    return {
        # Keep VTS out of its tracking-lost animation while this driver owns
        # the proof inputs.  That animation could otherwise overwrite the
        # same Live2D outputs after the parameter mappings are evaluated.
        "faceFound": True,
        "mode": "set",
        "parameterValues": [
            {"id": parameter_id, "value": float(values[parameter_id]), "weight": 1.0}
            for parameter_id in PARAMETER_SPECS
        ],
    }


async def _inject(client: VTSClient, values: dict[str, float]) -> None:
    await client.request("InjectParameterDataRequest", _values_payload(values), timeout=2.0)


async def _neutral_hold(client: VTSClient, seconds: float, fps: int) -> None:
    neutral = {parameter_id: spec.default for parameter_id, spec in PARAMETER_SPECS.items()}
    frames = max(1, round(seconds * fps))
    start = asyncio.get_running_loop().time()
    for frame in range(frames):
        target = start + frame / fps
        delay = target - asyncio.get_running_loop().time()
        if delay > 0:
            await asyncio.sleep(delay)
        await _inject(client, neutral)


async def _play_timeline(
    client: VTSClient,
    duration: float,
    curves: dict[str, LinearCurve],
    fps: int,
    pre_roll: float,
) -> None:
    await _neutral_hold(client, pre_roll, fps)
    print("PROOF_START", flush=True)
    start = asyncio.get_running_loop().time()
    total_frames = round(duration * fps) + 1
    maximum_lag = 0.0
    sections = ((0.0, "EYES"), (7.5, "EARS"), (13.5, "HAIR_ISOLATED"), (20.5, "HAIR_WAVE"))
    next_section = 0
    for frame in range(total_frames):
        timestamp = min(duration, frame / fps)
        target = start + timestamp
        delay = target - asyncio.get_running_loop().time()
        if delay > 0:
            await asyncio.sleep(delay)
        lag = max(0.0, asyncio.get_running_loop().time() - target)
        maximum_lag = max(maximum_lag, lag)
        while next_section < len(sections) and timestamp >= sections[next_section][0]:
            print(
                f"SECTION {sections[next_section][1]} t={sections[next_section][0]:.1f}",
                flush=True,
            )
            next_section += 1
        values = {
            parameter_id: curves[parameter_id].value_at(timestamp)
            for parameter_id in PARAMETER_SPECS
        }
        await _inject(client, values)
    elapsed = asyncio.get_running_loop().time() - start
    print(
        f"PROOF_END elapsed={elapsed:.3f}s frames={total_frames} "
        f"fps={fps} max_lag_ms={maximum_lag * 1000:.1f}",
        flush=True,
    )


async def _run(args: argparse.Namespace) -> int:
    credentials = _load_credentials(args.credentials)
    try:
        websocket_context = connect(
            args.endpoint,
            open_timeout=5.0,
            close_timeout=2.0,
            max_size=4 * 1024 * 1024,
        )
        async with websocket_context as websocket:
            client = VTSClient(websocket)
            state = await client.request("APIStateRequest")
            if not state.get("data", {}).get("active"):
                raise VTSAPIError("VTube Studio API is connected but not active")

            if credentials is None:
                if not args.request_token:
                    raise SystemExit(
                        "Aucun token VTS existant. Relancer avec --request-token "
                        "(--authorize-only possible), puis cliquer une seule fois sur "
                        "« Allow » dans VTube Studio."
                    )
                credentials = await _obtain_token(client, args.credentials)

            await _authenticate(client, credentials)
            print("AUTHENTICATED token=masked", flush=True)
            if args.authorize_only:
                return 0

            duration, curves = _load_linear_motion(args.motion)
            await _create_inputs(client)
            print("CUSTOM_INPUTS_READY=9", flush=True)

            completed = False
            try:
                await _play_timeline(client, duration, curves, args.fps, args.pre_roll)
                completed = True
            finally:
                try:
                    await _neutral_hold(client, args.neutral_hold, args.fps)
                    print("NEUTRAL_RESTORED=9", flush=True)
                finally:
                    if not args.keep_custom_parameters:
                        await _delete_inputs(client)
                        print("CUSTOM_INPUTS_REMOVED=9", flush=True)
            return 0 if completed else 1
    except (ConnectionError, OSError) as error:
        raise SystemExit(
            f"Connexion impossible à {args.endpoint}: {error}. "
            "Vérifier que VTube Studio est ouvert et que Start API est activé."
        ) from error


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--motion", type=Path, default=DEFAULT_MOTION)
    parser.add_argument("--credentials", type=Path, default=DEFAULT_CREDENTIALS)
    parser.add_argument("--fps", type=int, choices=(30, 60), default=60)
    parser.add_argument(
        "--pre-roll",
        type=float,
        default=2.0,
        help="Neutral seconds before PROOF_START (default: 2.0).",
    )
    parser.add_argument(
        "--neutral-hold",
        type=float,
        default=0.5,
        help="Neutral seconds sent after the timeline (default: 0.5).",
    )
    parser.add_argument(
        "--request-token",
        action="store_true",
        help="Request and save a token if no reusable token exists.",
    )
    parser.add_argument(
        "--authorize-only",
        action="store_true",
        help="Authenticate/save a token, then exit without creating or injecting inputs.",
    )
    parser.add_argument(
        "--keep-custom-parameters",
        action="store_true",
        help="Keep the nine temporary custom inputs after playback.",
    )
    args = parser.parse_args()
    if args.pre_roll < 0 or args.neutral_hold < 0:
        parser.error("--pre-roll and --neutral-hold must be non-negative")
    if args.authorize_only and not args.request_token and not args.credentials.is_file():
        parser.error("--authorize-only requires existing credentials or --request-token")
    return args


def main() -> int:
    started = time.monotonic()
    try:
        return asyncio.run(_run(_parse_args()))
    finally:
        print(f"DRIVER_WALL_SECONDS={time.monotonic() - started:.3f}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
