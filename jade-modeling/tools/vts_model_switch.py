#!/usr/bin/env python3
"""List or load a VTube Studio model through the authenticated local API."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from websockets.asyncio.client import connect

from vts_direct_proof_driver import (
    DEFAULT_CREDENTIALS,
    DEFAULT_ENDPOINT,
    VTSAPIError,
    VTSClient,
    _authenticate,
    _load_credentials,
)


def _public_model(model: dict[str, object]) -> dict[str, object]:
    """Keep the model-list output compact and free of unrelated API data."""
    return {
        key: model.get(key)
        for key in ("modelID", "modelName", "vtsModelName", "modelLoaded")
        if key in model
    }


async def _run(args: argparse.Namespace) -> int:
    credentials = _load_credentials(args.credentials)
    if credentials is None:
        raise SystemExit(
            f"No reusable VTube Studio token found at {args.credentials}."
        )

    async with connect(
        args.endpoint,
        open_timeout=5.0,
        close_timeout=2.0,
        max_size=4 * 1024 * 1024,
    ) as websocket:
        client = VTSClient(websocket)
        await _authenticate(client, credentials)

        if args.proof_frame:
            await client.request(
                "MoveModelRequest",
                {
                    "timeInSeconds": 0.5,
                    "valuesAreRelativeToModel": False,
                    "positionX": 0.0,
                    "positionY": -1.10,
                    "rotation": 0.0,
                    "size": -34.0,
                },
            )
            await asyncio.sleep(0.7)
            response = await client.request("CurrentModelRequest")
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "modelPosition": response.get("data", {}).get("modelPosition"),
                    },
                    indent=2,
                )
            )
            return 0

        if args.broadcast_frame:
            # r20 final-proof framing: both exterior ear tips stay inside a
            # compact 575x620 logical ScreenToGif crop, clear of VTS panels.
            await client.request(
                "MoveModelRequest",
                {
                    "timeInSeconds": 0.5,
                    "valuesAreRelativeToModel": False,
                    "positionX": 0.0,
                    "positionY": -1.02,
                    "rotation": 0.0,
                    "size": -48.0,
                },
            )
            await asyncio.sleep(0.7)
            response = await client.request("CurrentModelRequest")
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "modelPosition": response.get("data", {}).get("modelPosition"),
                    },
                    indent=2,
                )
            )
            return 0

        if args.current:
            response = await client.request("CurrentModelRequest")
            data = response.get("data", {})
            print(
                json.dumps(
                    {
                        key: data.get(key)
                        for key in (
                            "modelLoaded",
                            "modelName",
                            "modelID",
                            "vtsModelName",
                            "modelPosition",
                        )
                    },
                    indent=2,
                )
            )
            return 0

        if args.live2d is not None:
            response = await client.request("Live2DParameterListRequest")
            needle = args.live2d.casefold()
            data = response.get("data", {})
            parameters = data.get("parameters", [])
            data["parameters"] = [
                parameter
                for parameter in parameters
                if needle in json.dumps(parameter, ensure_ascii=False).casefold()
            ]
            print(json.dumps(data, indent=2))
            return 0

        if args.hotkey is not None:
            response = await client.request("HotkeysInCurrentModelRequest")
            hotkeys = response.get("data", {}).get("availableHotkeys", [])
            needle = args.hotkey.casefold()
            matches = [
                hotkey
                for hotkey in hotkeys
                if needle
                in json.dumps(hotkey, ensure_ascii=False, sort_keys=True).casefold()
            ]
            if len(matches) != 1:
                print(json.dumps(matches, indent=2))
                raise SystemExit(
                    f"Expected exactly one hotkey matching {args.hotkey!r}, "
                    f"got {len(matches)}"
                )
            hotkey = matches[0]
            await client.request(
                "HotkeyTriggerRequest", {"hotkeyID": hotkey["hotkeyID"]}
            )
            expression_state = await client.request("ExpressionStateRequest")
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "hotkey": {
                            key: hotkey.get(key)
                            for key in ("name", "type", "file", "hotkeyID")
                        },
                        "expression_state": expression_state.get("data", {}),
                    },
                    indent=2,
                )
            )
            return 0

        if args.model_id is not None:
            loaded = await client.request(
                "ModelLoadRequest", {"modelID": args.model_id}
            )
            current = await client.request("CurrentModelRequest")
            for _ in range(40):
                data = current.get("data", {})
                if data.get("modelLoaded") and data.get("modelID") == args.model_id:
                    break
                await asyncio.sleep(0.25)
                current = await client.request("CurrentModelRequest")
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "load_response": loaded.get("data", {}),
                        "current": {
                            key: current.get("data", {}).get(key)
                            for key in (
                                "modelLoaded",
                                "modelName",
                                "modelID",
                                "vtsModelName",
                                "numberOfLive2DParameters",
                            )
                        },
                    },
                    indent=2,
                )
            )
            return 0

        response = await client.request("AvailableModelsRequest")
        models = response.get("data", {}).get("availableModels", [])
        if not isinstance(models, list):
            raise VTSAPIError("AvailableModelsResponse has no availableModels list")

        if args.match is None:
            print(json.dumps([_public_model(model) for model in models], indent=2))
            return 0

        needle = args.match.casefold()
        matches = [
            model
            for model in models
            if needle in json.dumps(_public_model(model), ensure_ascii=False).casefold()
        ]
        if len(matches) != 1:
            print(json.dumps([_public_model(model) for model in matches], indent=2))
            raise SystemExit(
                f"Expected exactly one model matching {args.match!r}, got {len(matches)}"
            )

        selected = matches[0]
        model_id = str(selected.get("modelID", "")).strip()
        if not model_id:
            raise VTSAPIError("Matched model has no modelID")
        loaded = await client.request("ModelLoadRequest", {"modelID": model_id})
        current = await client.request("CurrentModelRequest")
        print(
            json.dumps(
                {
                    "status": "ok",
                    "selected": _public_model(selected),
                    "load_response": loaded.get("data", {}),
                    "current": {
                        key: current.get("data", {}).get(key)
                        for key in (
                            "modelLoaded",
                            "modelName",
                            "modelID",
                            "vtsModelName",
                        )
                    },
                },
                indent=2,
            )
        )
        return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--credentials", type=Path, default=DEFAULT_CREDENTIALS)
    parser.add_argument(
        "--match",
        help="Unique case-insensitive substring of the API model metadata to load.",
    )
    parser.add_argument(
        "--model-id",
        help="Load a model directly by its exact VTube Studio model ID.",
    )
    parser.add_argument(
        "--hotkey",
        help="Unique name or ID substring of a hotkey on the current model to trigger.",
    )
    parser.add_argument(
        "--live2d",
        help="List current-model Live2D parameter metadata matching this substring.",
    )
    parser.add_argument(
        "--current",
        action="store_true",
        help="Print the current model identity and on-screen transform.",
    )
    parser.add_argument(
        "--proof-frame",
        action="store_true",
        help="Apply the stable r13 hair-proof framing in VTube Studio.",
    )
    parser.add_argument(
        "--broadcast-frame",
        action="store_true",
        help="Apply the compact centered r20 final-proof framing.",
    )
    args = parser.parse_args()
    selected_actions = sum(
        value is not None
        for value in (args.match, args.model_id, args.hotkey, args.live2d)
    )
    selected_actions += int(args.current)
    selected_actions += int(args.proof_frame)
    selected_actions += int(args.broadcast_frame)
    if selected_actions > 1:
        parser.error(
            "--match, --model-id, --hotkey, --live2d, --current and "
            "--proof-frame and --broadcast-frame are mutually exclusive"
        )
    return args


def main() -> int:
    return asyncio.run(_run(_parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
