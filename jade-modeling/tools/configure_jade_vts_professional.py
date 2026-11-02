#!/usr/bin/env python3
"""Build Jade's calibrated VTube Studio configuration from a known-good template.

The template supplies VTube Studio's version-specific schema.  This tool changes
only model references, tracking ranges, physics strength and expression hotkeys,
then writes a new ``Jade.vtube.json`` without overwriting an existing file.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import uuid
from pathlib import Path
from typing import Any, Sequence


MODEL_FILE = "Jade.model3.json"
VTUBE_FILE = "Jade.vtube.json"
ICON_FILE = "icon.jpg"
IDLE_FILE = "Jade_idle.motion3.json"
TRACKING_LOST_FILE = "Jade_tracking_lost.motion3.json"
TRACKING_LOST_DELAY_SECONDS = 1.5

EXPRESSION_HOTKEYS = (
    ("Smile", "Numpad1", False),
    ("Sad", "Numpad2", False),
    ("Angry", "Numpad3", False),
    ("Surprised", "Numpad4", False),
    ("Blink", "Numpad5", True),
    ("WinkL", "Numpad6", True),
    ("WinkR", "Numpad7", True),
)

REQUIRED_PARAMETERS = {
    "ParamAngleX",
    "ParamAngleY",
    "ParamAngleZ",
    "ParamBodyAngleX",
    "ParamBodyAngleY",
    "ParamBodyAngleZ",
    "ParamEyeLOpen",
    "ParamEyeROpen",
    "ParamEyeLSmile",
    "ParamEyeRSmile",
    "ParamEyeBallX",
    "ParamEyeBallY",
    "ParamMouthForm",
    "ParamMouthOpenY",
    "ParamCheek",
    "ParamBrowLY",
    "ParamBrowRY",
    "ParamBrowLForm",
    "ParamBrowRForm",
    "ParamBreath",
}

# Values deliberately stay inside the actual model ranges.  Previous automatic
# setup used 1.9 for EyeOpen and 2.1 for MouthOpen although the model max is 1.
CALIBRATION: dict[str, dict[str, float | int | bool]] = {
    "ParamAngleZ": {
        "OutputRangeLower": -30.0,
        "OutputRangeUpper": 30.0,
        "ClampOutput": True,
        "Smoothing": 25,
    },
    "ParamEyeLOpen": {
        "OutputRangeLower": 0.0,
        "OutputRangeUpper": 1.0,
        "ClampInput": True,
        "ClampOutput": True,
        "Smoothing": 8,
    },
    "ParamEyeROpen": {
        "OutputRangeLower": 0.0,
        "OutputRangeUpper": 1.0,
        "ClampInput": True,
        "ClampOutput": True,
        "Smoothing": 8,
    },
    "ParamMouthForm": {
        "InputRangeLower": 0.0,
        "InputRangeUpper": 1.0,
        "OutputRangeLower": 0.0,
        "OutputRangeUpper": 1.0,
        "ClampInput": True,
        "ClampOutput": True,
        "Smoothing": 4,
    },
    "ParamMouthOpenY": {
        "InputRangeLower": 0.0,
        "InputRangeUpper": 1.0,
        "OutputRangeLower": 0.0,
        "OutputRangeUpper": 1.0,
        "ClampInput": True,
        "ClampOutput": True,
        "Smoothing": 4,
    },
    "ParamCheek": {
        "InputRangeLower": 0.0,
        "InputRangeUpper": 1.0,
        "OutputRangeLower": 0.0,
        "OutputRangeUpper": 1.0,
        "ClampInput": True,
        "ClampOutput": True,
        "Smoothing": 30,
    },
    "ParamBodyAngleZ": {
        "OutputRangeLower": -10.0,
        "OutputRangeUpper": 10.0,
        "ClampOutput": True,
        "Smoothing": 25,
    },
}


class ConfigError(RuntimeError):
    """Raised when the VTube Studio package cannot be patched safely."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ConfigError(message)


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ConfigError(f"cannot read {label}: {path}: {exc}") from exc
    _require(isinstance(value, dict), f"{label} root must be an object")
    return value


def _parameter_ids(cdi: dict[str, Any]) -> set[str]:
    rows = cdi.get("Parameters")
    _require(isinstance(rows, list), "cdi3 Parameters must be an array")
    result: set[str] = set()
    for index, row in enumerate(rows):
        _require(isinstance(row, dict), f"invalid cdi3 parameter row {index}")
        parameter_id = row.get("Id")
        _require(isinstance(parameter_id, str), f"invalid cdi3 parameter ID {index}")
        result.add(parameter_id)
    return result


def _expression_names(model: dict[str, Any]) -> set[str]:
    references = model.get("FileReferences")
    _require(isinstance(references, dict), "model3 FileReferences is missing")
    rows = references.get("Expressions")
    _require(isinstance(rows, list), "model3 Expressions is missing")
    names: set[str] = set()
    for index, row in enumerate(rows):
        _require(isinstance(row, dict), f"invalid expression row {index}")
        name = row.get("Name")
        filename = row.get("File")
        _require(
            isinstance(name, str) and isinstance(filename, str),
            f"invalid expression Name/File at row {index}",
        )
        names.add(name)
    return names


def _calibrate_mappings(config: dict[str, Any]) -> list[str]:
    rows = config.get("ParameterSettings")
    _require(isinstance(rows, list), "template ParameterSettings is missing")
    by_output: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        _require(isinstance(row, dict), f"invalid ParameterSettings row {index}")
        output = row.get("OutputLive2D")
        if isinstance(output, str):
            _require(output not in by_output, f"duplicate VTS mapping for {output}")
            by_output[output] = row
    missing = sorted(REQUIRED_PARAMETERS - set(by_output))
    _require(not missing, "template lacks VTS mappings: " + ", ".join(missing))
    changed: list[str] = []
    for parameter_id, fields in CALIBRATION.items():
        row = by_output[parameter_id]
        for field, value in fields.items():
            row[field] = value
        changed.append(parameter_id)
    return changed


def _build_hotkeys(config: dict[str, Any]) -> list[dict[str, Any]]:
    existing = config.get("Hotkeys")
    _require(isinstance(existing, list) and existing, "template has no hotkey schema")
    prototype = existing[0]
    _require(isinstance(prototype, dict), "template hotkey prototype is invalid")
    result: list[dict[str, Any]] = []
    namespace = uuid.UUID("4a548c8f-6da0-4e1d-a8f7-64002057c49f")
    for name, key, momentary in EXPRESSION_HOTKEYS:
        row = copy.deepcopy(prototype)
        row.update(
            {
                "HotkeyID": uuid.uuid5(namespace, f"jade:{name}").hex,
                "Name": name,
                "Action": "ToggleExpression",
                "File": f"{name}.exp3.json",
                "Folder": "",
                "IsGlobal": True,
                "IsActive": True,
                "DeactivateAfterKeyUp": momentary,
                "FadeSecondsAmount": 0.2,
            }
        )
        triggers = row.get("Triggers")
        _require(isinstance(triggers, dict), "hotkey prototype lacks Triggers")
        triggers.update(
            {
                "Trigger1": "LeftControl",
                "Trigger2": key,
                "Trigger3": "",
                "ScreenButton": -1,
            }
        )
        result.append(row)

    # Expressions can intentionally stack in VTube Studio.  A dedicated
    # neutral hotkey is therefore essential for a live operator: it clears a
    # previous emotional state in one press instead of requiring the streamer
    # to remember which toggles are still active.
    row = copy.deepcopy(prototype)
    row.update(
        {
            "HotkeyID": uuid.uuid5(namespace, "jade:Neutral").hex,
            "Name": "Neutral",
            "Action": "RemoveAllExpressions",
            "File": "",
            "Folder": "",
            "IsGlobal": True,
            "IsActive": True,
            "DeactivateAfterKeyUp": False,
            "FadeSecondsAmount": 0.25,
        }
    )
    triggers = row.get("Triggers")
    _require(isinstance(triggers, dict), "hotkey prototype lacks Triggers")
    triggers.update(
        {
            "Trigger1": "LeftControl",
            "Trigger2": "Numpad8",
            "Trigger3": "",
            "ScreenButton": -1,
        }
    )
    result.append(row)
    return result


def build(template_path: Path, runtime_dir: Path, output_path: Path | None) -> dict[str, Any]:
    template_path = template_path.expanduser().resolve(strict=True)
    runtime_dir = runtime_dir.expanduser().resolve(strict=True)
    _require(runtime_dir.is_dir(), f"runtime directory missing: {runtime_dir}")
    model_path = runtime_dir / MODEL_FILE
    model = _read_json(model_path, "model3")
    _require((runtime_dir / IDLE_FILE).is_file(), f"idle motion is missing: {IDLE_FILE}")
    _require(
        (runtime_dir / TRACKING_LOST_FILE).is_file(),
        f"tracking-lost motion is missing: {TRACKING_LOST_FILE}",
    )
    references = model.get("FileReferences")
    _require(isinstance(references, dict), "model3 FileReferences is missing")
    display_info = references.get("DisplayInfo")
    _require(isinstance(display_info, str), "model3 DisplayInfo is missing")
    cdi_path = runtime_dir / Path(display_info.replace("/", os.sep))
    cdi = _read_json(cdi_path, "cdi3")
    missing_parameters = sorted(REQUIRED_PARAMETERS - _parameter_ids(cdi))
    _require(not missing_parameters, "runtime lacks parameters: " + ", ".join(missing_parameters))

    required_expressions = {name for name, _key, _momentary in EXPRESSION_HOTKEYS}
    missing_expressions = sorted(required_expressions - _expression_names(model))
    _require(not missing_expressions, "runtime lacks expressions: " + ", ".join(missing_expressions))

    config = copy.deepcopy(_read_json(template_path, "VTube Studio template"))
    file_references = config.get("FileReferences")
    _require(isinstance(file_references, dict), "template FileReferences is missing")
    file_references.update(
        {
            "Icon": ICON_FILE,
            "Model": MODEL_FILE,
            "IdleAnimation": IDLE_FILE,
            "IdleAnimationWhenTrackingLost": TRACKING_LOST_FILE,
        }
    )
    changed_mappings = _calibrate_mappings(config)
    config["Hotkeys"] = _build_hotkeys(config)
    hotkey_settings = config.get("HotkeySettings")
    _require(isinstance(hotkey_settings, dict), "template HotkeySettings is missing")
    hotkey_settings["UseKeyboardHotkeys"] = True
    hotkey_settings["UseOnScreenHotkeys"] = False
    general_settings = config.get("GeneralSettings")
    _require(isinstance(general_settings, dict), "template GeneralSettings is missing")
    general_settings["TimeUntilTrackingLostIdleAnimation"] = (
        TRACKING_LOST_DELAY_SECONDS
    )
    config["SavedActiveExpressions"] = []
    physics = config.get("PhysicsSettings")
    _require(isinstance(physics, dict), "template PhysicsSettings is missing")
    physics["Use"] = True
    physics["UseLegacyPhysics"] = False
    physics["PhysicsStrength"] = 65

    output = (output_path or runtime_dir / VTUBE_FILE).expanduser().resolve(strict=False)
    _require(output.parent == runtime_dir, "output must be directly inside runtime directory")
    payload = (json.dumps(config, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if output.exists():
        _require(output.read_bytes() == payload, f"refusing to overwrite differing file: {output}")
        written = False
    else:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        descriptor = os.open(output, flags, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        written = True
    return {
        "status": "ok",
        "output": str(output),
        "written": written,
        "calibrated_mappings": changed_mappings,
        "hotkeys": [
            *[name for name, _key, _momentary in EXPRESSION_HOTKEYS],
            "Neutral",
        ],
        "idle_motion": IDLE_FILE,
        "tracking_lost_motion": TRACKING_LOST_FILE,
        "tracking_lost_delay_seconds": TRACKING_LOST_DELAY_SECONDS,
        "physics_strength": 65,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("template", type=Path, help="known-good Jade.vtube.json")
    parser.add_argument("runtime", type=Path, help="fresh exported Jade runtime directory")
    parser.add_argument("--output", type=Path, help="defaults to runtime/Jade.vtube.json")
    args = parser.parse_args(list(argv) if argv is not None else None)
    print(json.dumps(build(args.template, args.runtime, args.output), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ConfigError as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
