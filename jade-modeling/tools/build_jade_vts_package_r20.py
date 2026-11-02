#!/usr/bin/env python3
"""Create the copy-on-write Jade r20 VTube Studio package from r19b.

Only the two idle motions and the VTube Studio control configuration may
change.  Compiled art, textures, physics, expressions and the deterministic
proof motion remain byte-identical to the validated r19b package.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Sequence

from build_jade_professional_motions_r20 import build as build_motions


MODEL_ID = uuid.uuid5(
    uuid.UUID("fa3b0e77-4bfd-44ca-afbe-ec65d9b3fd85"),
    "jade-professional-r20-idle-complete",
).hex
CHANGED_FILES = frozenset(
    {
        "Jade_idle.motion3.json",
        "Jade_tracking_lost.motion3.json",
        "Jade.vtube.json",
    }
)
TRANSIENT_HOTKEYS = {
    # 0.20 s started the fade-out before the runtime reached the true r09
    # closed-eye key (~0.135 remained).  0.32 s gives the 0.10 s fade-in
    # enough time to settle at zero while keeping a natural short blink.
    "Blink": 0.32,
    "WinkL": 0.55,
    "WinkR": 0.55,
}


class PackageError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PackageError(message)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PackageError(f"cannot read JSON {path}: {exc}") from exc
    require(isinstance(value, dict), f"JSON root must be an object: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_files(root: Path) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def patch_vtube(path: Path) -> dict[str, Any]:
    document = read_json(path)
    document["Name"] = "Jade Professional r20"
    document["ModelID"] = MODEL_ID
    references = document.get("FileReferences")
    require(isinstance(references, dict), "VTube Studio FileReferences missing")
    references["IdleAnimation"] = "Jade_idle.motion3.json"
    references["IdleAnimationWhenTrackingLost"] = "Jade_tracking_lost.motion3.json"

    physics = document.get("PhysicsSettings")
    require(isinstance(physics, dict), "VTube Studio PhysicsSettings missing")
    physics["Use"] = True
    physics["UseLegacyPhysics"] = False
    physics["PhysicsStrength"] = 65
    physics["WindStrength"] = 0

    general = document.get("GeneralSettings")
    require(isinstance(general, dict), "VTube Studio GeneralSettings missing")
    general["TimeUntilTrackingLostIdleAnimation"] = 2.5
    general["EnableExpressionSaving"] = False
    document["SavedActiveExpressions"] = []

    parameter_settings = document.get("ParameterSettings")
    require(isinstance(parameter_settings, list), "VTube Studio ParameterSettings missing")
    breathing_outputs: list[str] = []
    blinking_outputs: list[str] = []
    for row in parameter_settings:
        require(isinstance(row, dict), "invalid VTube Studio parameter mapping")
        output = row.get("OutputLive2D")
        # Official VTS semantics: Auto-breath ignores the configured input and
        # sweeps the full output range.  It must therefore never be enabled on
        # head, gaze, brow, mouth or body mappings.
        row["UseBreathing"] = output == "ParamBreath"
        row["UseBlinking"] = output in {"ParamEyeLOpen", "ParamEyeROpen"}
        if row["UseBreathing"]:
            row["Input"] = ""
            row["OutputRangeLower"] = 0.20
            row["OutputRangeUpper"] = 0.78
            breathing_outputs.append(str(output))
        if row["UseBlinking"]:
            blinking_outputs.append(str(output))
    require(breathing_outputs == ["ParamBreath"], "Auto-breath must own only ParamBreath")
    require(
        sorted(blinking_outputs) == ["ParamEyeLOpen", "ParamEyeROpen"],
        "Auto-blink must own exactly both eye-open parameters",
    )

    hotkeys = document.get("Hotkeys")
    require(isinstance(hotkeys, list), "VTube Studio Hotkeys missing")
    by_name = {
        row.get("Name"): row
        for row in hotkeys
        if isinstance(row, dict) and isinstance(row.get("Name"), str)
    }
    expected_names = {
        "Smile",
        "Sad",
        "Angry",
        "Surprised",
        "Blink",
        "WinkL",
        "WinkR",
        "Neutral",
    }
    require(set(by_name) == expected_names, "r19b hotkey matrix changed unexpectedly")
    for name, seconds in TRANSIENT_HOTKEYS.items():
        row = by_name[name]
        require(row.get("Action") == "ToggleExpression", f"unexpected {name} action")
        row["DeactivateAfterKeyUp"] = False
        row["DeactivateAfterSeconds"] = True
        row["DeactivateAfterSecondsAmount"] = seconds
    require(by_name["Neutral"].get("Action") == "RemoveAllExpressions", "Neutral action changed")

    write_json(path, document)
    return {
        "name": document["Name"],
        "model_id": document["ModelID"],
        "idle": references["IdleAnimation"],
        "tracking_lost": references["IdleAnimationWhenTrackingLost"],
        "tracking_lost_delay_seconds": general["TimeUntilTrackingLostIdleAnimation"],
        "wind_strength": physics["WindStrength"],
        "saved_active_expressions": document["SavedActiveExpressions"],
        "auto_breath_outputs": breathing_outputs,
        "auto_breath_output_range": [0.20, 0.78],
        "auto_blink_outputs": sorted(blinking_outputs),
        "hotkeys": {
            name: {
                "action": by_name[name].get("Action"),
                "trigger": by_name[name].get("Triggers"),
                "auto_off": by_name[name].get("DeactivateAfterSeconds"),
                "auto_off_seconds": by_name[name].get("DeactivateAfterSecondsAmount"),
            }
            for name in sorted(by_name)
        },
        "emotion_state_contract": "Neutral, then exactly one of Smile/Sad/Angry/Surprised",
    }


def assemble(source: Path, output: Path) -> dict[str, Any]:
    source = source.resolve(strict=True)
    output = output.resolve(strict=False)
    require(source.is_dir(), f"source package missing: {source}")
    require(not output.exists(), f"refusing to overwrite existing output: {output}")

    source_files = relative_files(source)
    required = {
        "Jade.moc3",
        "Jade.cdi3.json",
        "Jade.model3.json",
        "Jade.physics3.json",
        "Jade.vtube.json",
        "Jade_idle.motion3.json",
        "Jade_tracking_lost.motion3.json",
        "Jade_proof.motion3.json",
        "Jade.4096/texture_00.png",
        "Jade.4096/texture_01.png",
    }
    require(required <= set(source_files), "r19b package is incomplete")

    cdi = read_json(source / "Jade.cdi3.json")
    parameters = cdi.get("Parameters")
    require(isinstance(parameters, list) and len(parameters) == 70, "r19b must contain 70 parameters")
    physics = read_json(source / "Jade.physics3.json")
    settings = physics.get("PhysicsSettings")
    require(isinstance(settings, list) and len(settings) == 9, "r19b must contain nine physics settings")
    outputs = [
        row
        for setting in settings
        if isinstance(setting, dict)
        for row in setting.get("Output", [])
        if isinstance(row, dict)
    ]
    require(len(outputs) == 39, "r19b must contain 39 physics outputs")

    temporary = output.with_name(output.name + ".partial")
    require(not temporary.exists(), f"stale partial output exists: {temporary}")
    shutil.copytree(source, temporary)
    try:
        motion_report = build_motions(temporary, dry_run=False)
        require(motion_report.get("status") == "ok", "r20 motion build failed")
        vtube_report = patch_vtube(temporary / "Jade.vtube.json")
        os.replace(temporary, output)
        motion_report["runtime"] = str(output)
        motion_report["model3"] = str(output / "Jade.model3.json")
        motion_report["cdi3"] = str(output / "Jade.cdi3.json")
        for row in motion_report.get("outputs", []):
            if isinstance(row, dict) and isinstance(row.get("file"), str):
                row["file"] = str(output / Path(row["file"]).name)
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise

    output_files = relative_files(output)
    require(set(output_files) == set(source_files), "r20 package file set changed unexpectedly")
    unchanged: dict[str, str] = {}
    changed: dict[str, dict[str, str]] = {}
    for name, source_path in source_files.items():
        source_hash = sha256(source_path)
        output_hash = sha256(output_files[name])
        if name in CHANGED_FILES:
            require(source_hash != output_hash, f"expected r20 file did not change: {name}")
            changed[name] = {"source_sha256": source_hash, "output_sha256": output_hash}
        else:
            require(source_hash == output_hash, f"immutable r19b file changed: {name}")
            unchanged[name] = output_hash

    immutable_core = (
        "Jade.moc3",
        "Jade.cdi3.json",
        "Jade.model3.json",
        "Jade.physics3.json",
        "Jade.4096/texture_00.png",
        "Jade.4096/texture_01.png",
        "Jade_proof.motion3.json",
    )
    for name in immutable_core:
        require(name in unchanged, f"immutable core audit missing {name}")

    return {
        "schema": "jade.vts-package-r20.v1",
        "status": "ok",
        "source": str(source),
        "output": str(output),
        "model_id": MODEL_ID,
        "parameters": len(parameters),
        "physics_settings": len(settings),
        "physics_outputs": len(outputs),
        "changed_files": changed,
        "unchanged_file_count": len(unchanged),
        "immutable_core_hashes": {name: unchanged[name] for name in immutable_core},
        "motions": motion_report,
        "vtube": vtube_report,
        "policies": {
            "copy_on_write": True,
            "r19b_never_overwritten": True,
            "eyes_r09_untouched": True,
            "hair_r18_untouched": True,
            "surprise_ears_r19b_untouched": True,
            "ear_swing_physics_untouched": True,
            "wind_strength": 0,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--audit", type=Path)
    args = parser.parse_args(list(argv) if argv is not None else None)
    report = assemble(args.source, args.output)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.audit:
        audit = args.audit.resolve(strict=False)
        require(not audit.exists(), f"refusing to overwrite audit: {audit}")
        audit.write_text(payload, encoding="utf-8", newline="\n")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PackageError as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
