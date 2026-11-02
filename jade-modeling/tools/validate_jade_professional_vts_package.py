#!/usr/bin/env python3
"""Validate Jade's final professional VTube Studio runtime package.

The validator is intentionally read-only.  It checks the exported Cubism
runtime, the professional physics/expressions/motions and the VTube Studio
configuration, then prints one machine-readable JSON report.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path, PurePosixPath
from typing import Any, Sequence


MODEL_FILE = "Jade.model3.json"
MOC_FILE = "Jade.moc3"
CDI_FILE = "Jade.cdi3.json"
PHYSICS_FILE = "Jade.physics3.json"
VTUBE_FILE = "Jade.vtube.json"
ICON_FILE = "icon.jpg"
IDLE_FILE = "Jade_idle.motion3.json"
TRACKING_LOST_FILE = "Jade_tracking_lost.motion3.json"
PROOF_FILE = "Jade_proof.motion3.json"
TRACKING_LOST_DELAY_SECONDS = 1.5

STANDARD_PARAMETER_IDS = (
    "ParamAngleX",
    "ParamAngleY",
    "ParamAngleZ",
    "ParamEyeLOpen",
    "ParamEyeLSmile",
    "ParamEyeROpen",
    "ParamEyeRSmile",
    "ParamEyeBallX",
    "ParamEyeBallY",
    "ParamBrowLY",
    "ParamBrowRY",
    "ParamBrowLX",
    "ParamBrowRX",
    "ParamBrowLAngle",
    "ParamBrowRAngle",
    "ParamBrowLForm",
    "ParamBrowRForm",
    "ParamMouthForm",
    "ParamMouthOpenY",
    "ParamCheek",
    "ParamBodyAngleX",
    "ParamBodyAngleY",
    "ParamBodyAngleZ",
    "ParamBreath",
    "ParamHairFront",
    "ParamHairSide",
    "ParamHairBack",
)
EXPRESSION_POSE_PARAMETER_IDS = (
    "ParamEarPoseL",
    "ParamEarPoseR",
)
PHYSICS_SECONDARY_PARAMETER_IDS = (
    "ParamEarSwingL",
    "ParamEarSwingR",
    "ParamAhogeSwing",
    "ParamClothSwing",
    "ParamHairBackC",
    "ParamHairBackLInner",
    "ParamHairBackLOuter",
    "ParamHairBackRInner",
    "ParamHairBackROuter",
    "ParamHairBangLOuter",
    "ParamHairBangROuter",
    "ParamHairTempleL",
    "ParamHairTempleR",
)
EXPECTED_PARAMETER_IDS = frozenset(
    (
        *STANDARD_PARAMETER_IDS,
        *EXPRESSION_POSE_PARAMETER_IDS,
        *PHYSICS_SECONDARY_PARAMETER_IDS,
    )
)

EXPRESSION_NAMES = (
    "Smile",
    "Sad",
    "Angry",
    "Surprised",
    "Blink",
    "WinkL",
    "WinkR",
)
MOMENTARY_EXPRESSIONS = frozenset(("Blink", "WinkL", "WinkR"))
HOTKEY_NAMES = (*EXPRESSION_NAMES, "Neutral")
EXPRESSION_EAR_POSES = {
    "Smile": 0.65,
    "Sad": -1.0,
    "Angry": -0.5,
    "Surprised": 0.0,
}

PHYSICS_SETTING_IDS = frozenset(
    (
        "PhysicsHairFront",
        "PhysicsHairSide",
        "PhysicsHairBack",
        "PhysicsEarL",
        "PhysicsEarR",
        "PhysicsAhoge",
        "PhysicsCloth",
        "PhysicsHairBackCDetail",
        "PhysicsHairBackLInnerDetail",
        "PhysicsHairBackLOuterDetail",
        "PhysicsHairBackRInnerDetail",
        "PhysicsHairBackROuterDetail",
        "PhysicsHairBangLOuter",
        "PhysicsHairBangROuter",
        "PhysicsHairTempleL",
        "PhysicsHairTempleR",
    )
)
PHYSICS_DESTINATION_IDS = frozenset(
    (
        "ParamHairFront",
        "ParamHairSide",
        "ParamHairBack",
        *PHYSICS_SECONDARY_PARAMETER_IDS,
    )
)

IDLE_PARAMETER_IDS = frozenset(
    (
        "ParamAngleX",
        "ParamAngleY",
        "ParamAngleZ",
        "ParamEyeBallX",
        "ParamEyeBallY",
        "ParamBodyAngleX",
        "ParamBodyAngleY",
        "ParamBodyAngleZ",
        "ParamBreath",
    )
)
TRACKING_LOST_PARAMETER_IDS = IDLE_PARAMETER_IDS | frozenset(
    ("ParamEyeLOpen", "ParamEyeROpen")
)
# Physics outputs must have one producer, and the idle must not overwrite eye
# tracking or momentary Blink/Wink expressions.
PROOF_PARAMETER_IDS = EXPECTED_PARAMETER_IDS - PHYSICS_DESTINATION_IDS

REQUIRED_VTS_MAPPINGS = frozenset(
    (
        "ParamAngleX",
        "ParamAngleY",
        "ParamAngleZ",
        "ParamBodyAngleX",
        "ParamBodyAngleY",
        "ParamBodyAngleZ",
        "ParamEyeLOpen",
        "ParamEyeROpen",
        "ParamEyeBallX",
        "ParamEyeBallY",
        "ParamBrowLY",
        "ParamBrowRY",
        "ParamBrowLForm",
        "ParamBrowRForm",
        "ParamMouthForm",
        "ParamMouthOpenY",
        "ParamCheek",
        "ParamBreath",
    )
)


class ValidationContext:
    """Collect deterministic diagnostics while continuing after local errors."""

    def __init__(self, runtime: Path) -> None:
        self.runtime = runtime
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.checked: set[Path] = set()

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warning(self, message: str) -> None:
        self.warnings.append(message)

    def json_file(self, path: Path, label: str) -> dict[str, Any] | None:
        self.checked.add(path)
        if not path.is_file():
            self.error(f"{label}: missing file: {path.name}")
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            self.error(f"{label}: unreadable JSON: {exc}")
            return None
        if not isinstance(value, dict):
            self.error(f"{label}: JSON root must be an object")
            return None
        return value

    def reference(self, value: Any, label: str) -> Path | None:
        if not isinstance(value, str) or not value:
            self.error(f"{label}: reference must be a non-empty string")
            return None
        if "\\" in value:
            self.error(f"{label}: reference must use '/' separators: {value}")
            return None
        relative = PurePosixPath(value)
        if relative.is_absolute() or relative.anchor or ".." in relative.parts:
            self.error(f"{label}: unsafe runtime reference: {value}")
            return None
        path = (self.runtime / Path(*relative.parts)).resolve(strict=False)
        try:
            inside = os.path.commonpath((str(self.runtime), str(path))) == str(
                self.runtime
            )
        except ValueError:
            inside = False
        if not inside:
            self.error(f"{label}: reference escapes runtime: {value}")
            return None
        self.checked.add(path)
        if not path.is_file():
            self.error(f"{label}: referenced file is missing: {value}")
            return None
        try:
            if path.stat().st_size <= 0:
                self.error(f"{label}: referenced file is empty: {value}")
        except OSError as exc:
            self.error(f"{label}: cannot stat referenced file: {value}: {exc}")
            return None
        return path


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _duplicates(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    duplicated: set[str] = set()
    for value in values:
        if value in seen:
            duplicated.add(value)
        seen.add(value)
    return sorted(duplicated)


def _set_difference_message(
    label: str,
    observed: set[str],
    expected: frozenset[str],
    context: ValidationContext,
) -> None:
    missing = sorted(expected - observed)
    unexpected = sorted(observed - expected)
    if missing:
        context.error(f"{label}: missing IDs: {', '.join(missing)}")
    if unexpected:
        context.error(f"{label}: unexpected IDs: {', '.join(unexpected)}")


def _validate_texture(path: Path, label: str, context: ValidationContext) -> None:
    if path.suffix.casefold() != ".png":
        context.error(f"{label}: texture must be PNG: {path.name}")
        return
    try:
        signature = path.read_bytes()[:8]
    except OSError as exc:
        context.error(f"{label}: cannot read texture: {exc}")
        return
    if signature != b"\x89PNG\r\n\x1a\n":
        context.error(f"{label}: invalid PNG signature: {path.name}")


def _validate_groups(
    model: dict[str, Any], context: ValidationContext
) -> dict[str, list[str]]:
    rows = model.get("Groups")
    if not isinstance(rows, list):
        context.error("model3.Groups: expected an array")
        return {}
    result: dict[str, list[str]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            context.error(f"model3.Groups[{index}]: expected an object")
            continue
        name = row.get("Name")
        if name not in {"EyeBlink", "LipSync"}:
            continue
        if name in result:
            context.error(f"model3.Groups: duplicate group: {name}")
            continue
        ids = row.get("Ids")
        if row.get("Target") != "Parameter" or not isinstance(ids, list):
            context.error(f"model3.Groups.{name}: invalid Target/Ids")
            continue
        if not all(isinstance(item, str) and item for item in ids):
            context.error(f"model3.Groups.{name}: invalid parameter ID")
            continue
        result[name] = list(ids)
    expected = {
        "EyeBlink": ["ParamEyeLOpen", "ParamEyeROpen"],
        "LipSync": ["ParamMouthOpenY"],
    }
    for name, ids in expected.items():
        if result.get(name) != ids:
            context.error(
                f"model3.Groups.{name}: expected {ids}, got {result.get(name)}"
            )
    return result


def _validate_cdi(
    cdi_path: Path, context: ValidationContext
) -> tuple[set[str], int]:
    cdi = context.json_file(cdi_path, "cdi3")
    if cdi is None:
        return set(), 0
    if cdi.get("Version") != 3:
        context.error("cdi3.Version: expected 3")
    rows = cdi.get("Parameters")
    if not isinstance(rows, list):
        context.error("cdi3.Parameters: expected an array")
        return set(), 0
    values: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            context.error(f"cdi3.Parameters[{index}]: expected an object")
            continue
        parameter_id = row.get("Id")
        if not isinstance(parameter_id, str) or not parameter_id:
            context.error(f"cdi3.Parameters[{index}].Id: invalid ID")
            continue
        values.append(parameter_id)
    for parameter_id in _duplicates(values):
        context.error(f"cdi3.Parameters: duplicate ID: {parameter_id}")
    observed = set(values)
    _set_difference_message(
        "cdi3.Parameters", observed, EXPECTED_PARAMETER_IDS, context
    )
    if len(values) != len(EXPECTED_PARAMETER_IDS):
        context.error(
            "cdi3.Parameters: expected exactly "
            f"{len(EXPECTED_PARAMETER_IDS)} rows, got {len(values)}"
        )
    return observed, len(values)


def _validate_moc(
    moc_path: Path, context: ValidationContext
) -> tuple[set[str], int]:
    context.checked.add(moc_path)
    if not moc_path.is_file():
        context.error(f"moc3: missing file: {MOC_FILE}")
        return set(), 0
    try:
        data = moc_path.read_bytes()
    except OSError as exc:
        context.error(f"moc3: cannot read {MOC_FILE}: {exc}")
        return set(), 0
    if not data.startswith(b"MOC3"):
        context.error("moc3: invalid MOC3 signature")
    if len(data) < 64:
        context.error(f"moc3: implausibly small payload: {len(data)} bytes")
    observed = {
        parameter_id
        for parameter_id in EXPECTED_PARAMETER_IDS
        if parameter_id.encode("ascii") in data
    }
    missing = sorted(EXPECTED_PARAMETER_IDS - observed)
    if missing:
        context.error("moc3: expected parameter IDs absent: " + ", ".join(missing))
    return observed, len(data)


def _validate_expression(
    path: Path,
    name: str,
    parameter_ids: set[str],
    context: ValidationContext,
) -> set[str]:
    document = context.json_file(path, f"expression.{name}")
    if document is None:
        return set()
    if document.get("Type") != "Live2D Expression":
        context.error(f"expression.{name}.Type: expected Live2D Expression")
    for field in ("FadeInTime", "FadeOutTime"):
        value = document.get(field)
        if not _is_number(value) or float(value) < 0:
            context.error(f"expression.{name}.{field}: invalid duration")
    rows = document.get("Parameters")
    if not isinstance(rows, list) or not rows:
        context.error(f"expression.{name}.Parameters: expected a non-empty array")
        return set()
    values: list[str] = []
    rows_by_id: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        label = f"expression.{name}.Parameters[{index}]"
        if not isinstance(row, dict):
            context.error(f"{label}: expected an object")
            continue
        parameter_id = row.get("Id")
        if not isinstance(parameter_id, str) or not parameter_id:
            context.error(f"{label}.Id: invalid ID")
            continue
        values.append(parameter_id)
        rows_by_id.setdefault(parameter_id, row)
        if parameter_id not in parameter_ids:
            context.error(f"{label}.Id: absent from professional model: {parameter_id}")
        if parameter_id in PHYSICS_DESTINATION_IDS:
            context.error(f"{label}.Id: expression must not write a physics output")
        if not _is_number(row.get("Value")):
            context.error(f"{label}.Value: expected a finite number")
        if row.get("Blend") not in {"Add", "Multiply", "Overwrite"}:
            context.error(f"{label}.Blend: invalid blend mode")
    for parameter_id in _duplicates(values):
        context.error(f"expression.{name}: duplicate parameter: {parameter_id}")
    expected_ear_pose = EXPRESSION_EAR_POSES.get(name)
    for parameter_id in EXPRESSION_POSE_PARAMETER_IDS:
        row = rows_by_id.get(parameter_id)
        if expected_ear_pose is None:
            if row is not None:
                context.error(
                    f"expression.{name}: unexpected expressive ear pose {parameter_id}"
                )
            continue
        if row is None:
            context.error(f"expression.{name}: missing ear pose {parameter_id}")
            continue
        value = row.get("Value")
        if not _is_number(value) or not math.isclose(
            float(value), expected_ear_pose, abs_tol=1e-6
        ):
            context.error(
                f"expression.{name}.{parameter_id}: expected {expected_ear_pose}"
            )
        if row.get("Blend") != "Overwrite":
            context.error(
                f"expression.{name}.{parameter_id}: expected Overwrite blend"
            )
    return set(values)


def _validate_expressions(
    references: dict[str, Any],
    parameter_ids: set[str],
    context: ValidationContext,
) -> tuple[dict[str, Path], dict[str, set[str]]]:
    rows = references.get("Expressions")
    if not isinstance(rows, list):
        context.error("model3.Expressions: expected an array")
        return {}, {}
    names: list[str] = []
    files: list[str] = []
    paths: dict[str, Path] = {}
    used_parameters: dict[str, set[str]] = {}
    for index, row in enumerate(rows):
        label = f"model3.Expressions[{index}]"
        if not isinstance(row, dict):
            context.error(f"{label}: expected an object")
            continue
        name = row.get("Name")
        filename = row.get("File")
        if not isinstance(name, str) or not name:
            context.error(f"{label}.Name: invalid name")
            continue
        names.append(name)
        if not isinstance(filename, str) or not filename:
            context.error(f"{label}.File: invalid reference")
            continue
        files.append(filename.casefold())
        expected_file = f"expressions/{name}.exp3.json"
        if filename != expected_file:
            context.error(f"{label}.File: expected {expected_file}, got {filename}")
        path = context.reference(filename, f"{label}.File")
        if path is None:
            continue
        paths[name] = path
        used_parameters[name] = _validate_expression(
            path, name, parameter_ids, context
        )
    for name in _duplicates(names):
        context.error(f"model3.Expressions: duplicate name: {name}")
    for filename in _duplicates(files):
        context.error(f"model3.Expressions: duplicate file: {filename}")
    _set_difference_message(
        "model3.Expressions", set(names), frozenset(EXPRESSION_NAMES), context
    )
    if len(rows) != len(EXPRESSION_NAMES):
        context.error(
            f"model3.Expressions: expected exactly {len(EXPRESSION_NAMES)} entries, "
            f"got {len(rows)}"
        )
    return paths, used_parameters


def _validate_physics(
    path: Path, parameter_ids: set[str], context: ValidationContext
) -> dict[str, Any]:
    document = context.json_file(path, "physics3")
    summary: dict[str, Any] = {"settings": 0, "inputs": 0, "outputs": 0}
    if document is None:
        return summary
    if document.get("Version") != 3:
        context.error("physics3.Version: expected 3")
    meta = document.get("Meta")
    if not isinstance(meta, dict):
        context.error("physics3.Meta: expected an object")
        meta = {}
    settings = document.get("PhysicsSettings")
    if not isinstance(settings, list):
        context.error("physics3.PhysicsSettings: expected an array")
        return summary

    setting_ids: list[str] = []
    destinations: list[str] = []
    total_inputs = 0
    total_outputs = 0
    total_vertices = 0
    for index, setting in enumerate(settings):
        label = f"physics3.PhysicsSettings[{index}]"
        if not isinstance(setting, dict):
            context.error(f"{label}: expected an object")
            continue
        setting_id = setting.get("Id")
        if isinstance(setting_id, str) and setting_id:
            setting_ids.append(setting_id)
        else:
            context.error(f"{label}.Id: invalid ID")

        inputs = setting.get("Input")
        if not isinstance(inputs, list) or not inputs:
            context.error(f"{label}.Input: expected a non-empty array")
            inputs = []
        total_inputs += len(inputs)
        for input_index, row in enumerate(inputs):
            row_label = f"{label}.Input[{input_index}]"
            if not isinstance(row, dict):
                context.error(f"{row_label}: expected an object")
                continue
            source = row.get("Source")
            if not isinstance(source, dict) or source.get("Target") != "Parameter":
                context.error(f"{row_label}.Source: invalid parameter source")
                continue
            parameter_id = source.get("Id")
            if parameter_id not in parameter_ids:
                context.error(
                    f"{row_label}.Source.Id: absent from model: {parameter_id}"
                )

        outputs = setting.get("Output")
        if not isinstance(outputs, list) or len(outputs) != 1:
            context.error(f"{label}.Output: expected exactly one output")
            outputs = [] if not isinstance(outputs, list) else outputs
        total_outputs += len(outputs)
        for output_index, row in enumerate(outputs):
            row_label = f"{label}.Output[{output_index}]"
            if not isinstance(row, dict):
                context.error(f"{row_label}: expected an object")
                continue
            destination = row.get("Destination")
            if (
                not isinstance(destination, dict)
                or destination.get("Target") != "Parameter"
            ):
                context.error(f"{row_label}.Destination: invalid parameter target")
                continue
            parameter_id = destination.get("Id")
            if not isinstance(parameter_id, str):
                context.error(f"{row_label}.Destination.Id: invalid ID")
                continue
            destinations.append(parameter_id)
            if parameter_id not in parameter_ids:
                context.error(
                    f"{row_label}.Destination.Id: absent from model: {parameter_id}"
                )

        vertices = setting.get("Vertices")
        if not isinstance(vertices, list) or len(vertices) < 2:
            context.error(f"{label}.Vertices: expected at least two particles")
            vertices = []
        total_vertices += len(vertices)

    for setting_id in _duplicates(setting_ids):
        context.error(f"physics3: duplicate setting ID: {setting_id}")
    for parameter_id in _duplicates(destinations):
        context.error(f"physics3: duplicate output destination: {parameter_id}")
    _set_difference_message(
        "physics3 settings", set(setting_ids), PHYSICS_SETTING_IDS, context
    )
    _set_difference_message(
        "physics3 outputs", set(destinations), PHYSICS_DESTINATION_IDS, context
    )
    if len(settings) != len(PHYSICS_SETTING_IDS):
        context.error(
            "physics3: expected exactly "
            f"{len(PHYSICS_SETTING_IDS)} settings, got {len(settings)}"
        )
    if total_outputs != len(PHYSICS_DESTINATION_IDS):
        context.error(
            "physics3: expected exactly "
            f"{len(PHYSICS_DESTINATION_IDS)} outputs, got {total_outputs}"
        )

    dictionary = meta.get("PhysicsDictionary")
    dictionary_ids: list[str] = []
    if not isinstance(dictionary, list):
        context.error("physics3.Meta.PhysicsDictionary: expected an array")
    else:
        for index, row in enumerate(dictionary):
            if not isinstance(row, dict) or not isinstance(row.get("Id"), str):
                context.error(
                    f"physics3.Meta.PhysicsDictionary[{index}]: invalid entry"
                )
                continue
            dictionary_ids.append(row["Id"])
        _set_difference_message(
            "physics3.Meta.PhysicsDictionary",
            set(dictionary_ids),
            PHYSICS_SETTING_IDS,
            context,
        )
    expected_meta = {
        "PhysicsSettingCount": len(settings),
        "TotalInputCount": total_inputs,
        "TotalOutputCount": total_outputs,
        "VertexCount": total_vertices,
    }
    for key, expected in expected_meta.items():
        if meta.get(key) != expected:
            context.error(
                f"physics3.Meta.{key}: expected {expected}, got {meta.get(key)}"
            )
    summary.update(
        {
            "settings": len(settings),
            "inputs": total_inputs,
            "outputs": total_outputs,
            "destinations": sorted(set(destinations)),
        }
    )
    return summary


def _motion_segment_counts(
    segments: Any,
    duration: float,
    label: str,
    context: ValidationContext,
) -> tuple[int, int, float | None, float | None]:
    if not isinstance(segments, list) or len(segments) < 2:
        context.error(f"{label}.Segments: expected at least time/value")
        return 0, 0, None, None
    if not all(_is_number(item) for item in segments):
        context.error(f"{label}.Segments: contains a non-finite number")
        return 0, 0, None, None
    first_time = float(segments[0])
    first_value = float(segments[1])
    cursor = 2
    segment_count = 0
    point_count = 1
    previous_time = first_time
    last_value = first_value
    while cursor < len(segments):
        kind = segments[cursor]
        if not isinstance(kind, int) or isinstance(kind, bool) or kind not in {0, 1, 2, 3}:
            context.error(f"{label}.Segments[{cursor}]: invalid segment type: {kind}")
            return segment_count, point_count, first_value, last_value
        width = 7 if kind == 1 else 3
        if cursor + width > len(segments):
            context.error(f"{label}.Segments[{cursor}]: truncated segment")
            return segment_count, point_count, first_value, last_value
        if kind == 1:
            control_1_time = float(segments[cursor + 1])
            control_2_time = float(segments[cursor + 3])
            end_time = float(segments[cursor + 5])
            end_value = float(segments[cursor + 6])
            if not (
                previous_time <= control_1_time <= control_2_time <= end_time
            ):
                context.error(f"{label}.Segments[{cursor}]: non-monotonic Bezier time")
        else:
            end_time = float(segments[cursor + 1])
            end_value = float(segments[cursor + 2])
        if end_time <= previous_time:
            context.error(f"{label}.Segments[{cursor}]: time does not increase")
        previous_time = end_time
        last_value = end_value
        segment_count += 1
        point_count += 3 if kind == 1 else 1
        cursor += width
    if not math.isclose(first_time, 0.0, abs_tol=1e-6):
        context.error(f"{label}: curve must begin at t=0")
    if not math.isclose(previous_time, duration, abs_tol=1e-6):
        context.error(
            f"{label}: curve must end at Duration {duration}, got {previous_time}"
        )
    return segment_count, point_count, first_value, last_value


def _validate_motion(
    path: Path,
    expected_ids: frozenset[str],
    parameter_ids: set[str],
    label: str,
    context: ValidationContext,
) -> dict[str, Any]:
    document = context.json_file(path, label)
    summary: dict[str, Any] = {"curves": 0, "segments": 0, "points": 0}
    if document is None:
        return summary
    if document.get("Version") != 3:
        context.error(f"{label}.Version: expected 3")
    meta = document.get("Meta")
    if not isinstance(meta, dict):
        context.error(f"{label}.Meta: expected an object")
        return summary
    duration = meta.get("Duration")
    if not _is_number(duration) or float(duration) <= 0:
        context.error(f"{label}.Meta.Duration: expected a positive number")
        return summary
    duration_float = float(duration)
    fps = meta.get("Fps")
    if not _is_number(fps) or float(fps) <= 0:
        context.error(f"{label}.Meta.Fps: expected a positive number")
    if meta.get("Loop") is not True:
        context.error(f"{label}.Meta.Loop: expected true")
    if not isinstance(meta.get("AreBeziersRestricted"), bool):
        context.error(f"{label}.Meta.AreBeziersRestricted: expected a boolean")
    for field in ("FadeInTime", "FadeOutTime"):
        if field in meta and (
            not _is_number(meta[field]) or float(meta[field]) < 0
        ):
            context.error(f"{label}.Meta.{field}: invalid duration")

    curves = document.get("Curves")
    if not isinstance(curves, list) or not curves:
        context.error(f"{label}.Curves: expected a non-empty array")
        return summary
    curve_ids: list[str] = []
    total_segments = 0
    total_points = 0
    for index, curve in enumerate(curves):
        curve_label = f"{label}.Curves[{index}]"
        if not isinstance(curve, dict):
            context.error(f"{curve_label}: expected an object")
            continue
        if curve.get("Target") != "Parameter":
            context.error(f"{curve_label}.Target: expected Parameter")
        parameter_id = curve.get("Id")
        if not isinstance(parameter_id, str) or not parameter_id:
            context.error(f"{curve_label}.Id: invalid ID")
        else:
            curve_ids.append(parameter_id)
            if parameter_id not in parameter_ids:
                context.error(f"{curve_label}.Id: absent from model: {parameter_id}")
        segment_count, point_count, first_value, last_value = (
            _motion_segment_counts(
                curve.get("Segments"),
                duration_float,
                curve_label,
                context,
            )
        )
        total_segments += segment_count
        total_points += point_count
        if (
            first_value is not None
            and last_value is not None
            and not math.isclose(first_value, last_value, abs_tol=1e-6)
        ):
            context.error(f"{curve_label}: looping values are discontinuous")
    for parameter_id in _duplicates(curve_ids):
        context.error(f"{label}.Curves: duplicate parameter ID: {parameter_id}")
    _set_difference_message(label + ".Curves", set(curve_ids), expected_ids, context)
    expected_meta = {
        "CurveCount": len(curves),
        "TotalSegmentCount": total_segments,
        "TotalPointCount": total_points,
        "UserDataCount": 0,
        "TotalUserDataSize": 0,
    }
    for key, expected in expected_meta.items():
        if meta.get(key) != expected:
            context.error(f"{label}.Meta.{key}: expected {expected}, got {meta.get(key)}")
    summary.update(
        {
            "duration": duration_float,
            "fps": fps,
            "curves": len(curves),
            "segments": total_segments,
            "points": total_points,
        }
    )
    return summary


def _mapping_by_output(
    config: dict[str, Any], parameter_ids: set[str], context: ValidationContext
) -> dict[str, dict[str, Any]]:
    rows = config.get("ParameterSettings")
    if not isinstance(rows, list):
        context.error("vtube.ParameterSettings: expected an array")
        return {}
    result: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        label = f"vtube.ParameterSettings[{index}]"
        if not isinstance(row, dict):
            context.error(f"{label}: expected an object")
            continue
        parameter_id = row.get("OutputLive2D")
        if not isinstance(parameter_id, str) or not parameter_id:
            context.error(f"{label}.OutputLive2D: invalid ID")
            continue
        if row.get("Input") == "MouthSmile" and parameter_id in {
            "ParamEyeLSmile",
            "ParamEyeRSmile",
        }:
            context.error(
                f"{label}: forbidden mapping MouthSmile -> {parameter_id}"
            )
        if parameter_id in result:
            context.error(f"vtube.ParameterSettings: duplicate mapping: {parameter_id}")
            continue
        result[parameter_id] = row
        if parameter_id not in parameter_ids:
            context.error(f"{label}.OutputLive2D: absent from model: {parameter_id}")
        for field in (
            "InputRangeLower",
            "InputRangeUpper",
            "OutputRangeLower",
            "OutputRangeUpper",
        ):
            if not _is_number(row.get(field)):
                context.error(f"{label}.{field}: expected a finite number")
    missing = sorted(REQUIRED_VTS_MAPPINGS - set(result))
    if missing:
        context.error("vtube.ParameterSettings: missing mappings: " + ", ".join(missing))
    return result


def _require_mapping_calibration(
    mappings: dict[str, dict[str, Any]],
    parameter_id: str,
    lower: float,
    upper: float,
    context: ValidationContext,
) -> None:
    row = mappings.get(parameter_id)
    if row is None:
        return
    observed_lower = row.get("OutputRangeLower")
    observed_upper = row.get("OutputRangeUpper")
    if not _is_number(observed_lower) or not math.isclose(
        float(observed_lower), lower, abs_tol=1e-6
    ):
        context.error(
            f"vtube mapping {parameter_id}: OutputRangeLower must be {lower}"
        )
    if not _is_number(observed_upper) or not math.isclose(
        float(observed_upper), upper, abs_tol=1e-6
    ):
        context.error(
            f"vtube mapping {parameter_id}: OutputRangeUpper must be {upper}"
        )
    if row.get("ClampOutput") is not True:
        context.error(f"vtube mapping {parameter_id}: ClampOutput must be true")


def _validate_hotkeys(
    config: dict[str, Any], expression_paths: dict[str, Path], context: ValidationContext
) -> int:
    rows = config.get("Hotkeys")
    if not isinstance(rows, list):
        context.error("vtube.Hotkeys: expected an array")
        return 0
    names: list[str] = []
    hotkey_ids: list[str] = []
    trigger_sets: list[str] = []
    for index, row in enumerate(rows):
        label = f"vtube.Hotkeys[{index}]"
        if not isinstance(row, dict):
            context.error(f"{label}: expected an object")
            continue
        name = row.get("Name")
        if not isinstance(name, str) or not name:
            context.error(f"{label}.Name: invalid name")
            continue
        names.append(name)
        hotkey_id = row.get("HotkeyID")
        if not isinstance(hotkey_id, str) or not hotkey_id:
            context.error(f"{label}.HotkeyID: invalid ID")
        else:
            hotkey_ids.append(hotkey_id)
        if name == "Neutral":
            if row.get("Action") != "RemoveAllExpressions":
                context.error(f"{label}.Action: expected RemoveAllExpressions")
            if row.get("File") != "":
                context.error(f"{label}.File: expected an empty string")
        else:
            if row.get("Action") != "ToggleExpression":
                context.error(f"{label}.Action: expected ToggleExpression")
            expected_file = f"{name}.exp3.json"
            if row.get("File") != expected_file:
                context.error(f"{label}.File: expected {expected_file}")
            expression_path = context.reference(
                f"expressions/{expected_file}", f"{label}.File"
            )
            registered = expression_paths.get(name)
            if expression_path is not None and registered != expression_path:
                context.error(f"{label}.File: expression is not registered by model3")
        if row.get("IsActive") is not True:
            context.error(f"{label}.IsActive: expected true")
        expected_momentary = name in MOMENTARY_EXPRESSIONS
        if row.get("DeactivateAfterKeyUp") is not expected_momentary:
            context.error(
                f"{label}.DeactivateAfterKeyUp: expected {expected_momentary}"
            )
        triggers = row.get("Triggers")
        if not isinstance(triggers, dict):
            context.error(f"{label}.Triggers: expected an object")
        else:
            trigger = "|".join(
                str(triggers.get(field, ""))
                for field in ("Trigger1", "Trigger2", "Trigger3")
            )
            if trigger == "||":
                context.error(f"{label}.Triggers: no keyboard trigger")
            trigger_sets.append(trigger)
    for name in _duplicates(names):
        context.error(f"vtube.Hotkeys: duplicate name: {name}")
    for hotkey_id in _duplicates(hotkey_ids):
        context.error(f"vtube.Hotkeys: duplicate HotkeyID: {hotkey_id}")
    for trigger in _duplicates(trigger_sets):
        context.error(f"vtube.Hotkeys: duplicate trigger: {trigger}")
    _set_difference_message(
        "vtube.Hotkeys", set(names), frozenset(HOTKEY_NAMES), context
    )
    if len(rows) != len(HOTKEY_NAMES):
        context.error(
            f"vtube.Hotkeys: expected exactly {len(HOTKEY_NAMES)}, got {len(rows)}"
        )
    return len(rows)


def _validate_vtube(
    path: Path,
    parameter_ids: set[str],
    expression_paths: dict[str, Path],
    context: ValidationContext,
) -> dict[str, Any]:
    config = context.json_file(path, "vtube")
    summary: dict[str, Any] = {"mappings": 0, "hotkeys": 0}
    if config is None:
        return summary
    if config.get("Version") != 1:
        context.error("vtube.Version: expected 1")
    if config.get("Name") != "Jade":
        context.error("vtube.Name: expected Jade")
    references = config.get("FileReferences")
    if not isinstance(references, dict):
        context.error("vtube.FileReferences: expected an object")
        references = {}
    expected_references = {
        "Icon": ICON_FILE,
        "Model": MODEL_FILE,
        "IdleAnimation": IDLE_FILE,
        "IdleAnimationWhenTrackingLost": TRACKING_LOST_FILE,
    }
    for key, expected in expected_references.items():
        observed = references.get(key)
        if observed != expected:
            context.error(
                f"vtube.FileReferences.{key}: expected {expected}, got {observed}"
            )
        context.reference(observed, f"vtube.FileReferences.{key}")

    mappings = _mapping_by_output(config, parameter_ids, context)
    for parameter_id in ("ParamEyeLOpen", "ParamEyeROpen"):
        _require_mapping_calibration(mappings, parameter_id, 0.0, 1.0, context)
    for parameter_id in ("ParamMouthForm", "ParamMouthOpenY", "ParamCheek"):
        _require_mapping_calibration(mappings, parameter_id, 0.0, 1.0, context)
        row = mappings.get(parameter_id)
        if row is not None and row.get("ClampInput") is not True:
            context.error(f"vtube mapping {parameter_id}: ClampInput must be true")
    for row in mappings.values():
        for field, forbidden in (
            ("OutputRangeLower", (0.5,)),
            ("OutputRangeUpper", (1.9, 2.1)),
        ):
            value = row.get(field)
            if _is_number(value) and any(
                math.isclose(float(value), item, abs_tol=1e-5)
                for item in forbidden
            ):
                context.error(
                    f"vtube mapping {row.get('OutputLive2D')}: forbidden legacy "
                    f"{field}={value}"
                )

    hotkey_count = _validate_hotkeys(config, expression_paths, context)
    hotkey_settings = config.get("HotkeySettings")
    if not isinstance(hotkey_settings, dict):
        context.error("vtube.HotkeySettings: expected an object")
    elif hotkey_settings.get("UseKeyboardHotkeys") is not True:
        context.error("vtube.HotkeySettings.UseKeyboardHotkeys: expected true")
    general_settings = config.get("GeneralSettings")
    if not isinstance(general_settings, dict):
        context.error("vtube.GeneralSettings: expected an object")
    else:
        delay = general_settings.get("TimeUntilTrackingLostIdleAnimation")
        if not _is_number(delay) or not math.isclose(
            float(delay), TRACKING_LOST_DELAY_SECONDS, abs_tol=1e-6
        ):
            context.error(
                "vtube.GeneralSettings.TimeUntilTrackingLostIdleAnimation: "
                f"expected {TRACKING_LOST_DELAY_SECONDS}"
            )
    physics_settings = config.get("PhysicsSettings")
    if not isinstance(physics_settings, dict):
        context.error("vtube.PhysicsSettings: expected an object")
    else:
        if physics_settings.get("Use") is not True:
            context.error("vtube.PhysicsSettings.Use: expected true")
        if physics_settings.get("UseLegacyPhysics") is not False:
            context.error("vtube.PhysicsSettings.UseLegacyPhysics: expected false")
    summary.update({"mappings": len(mappings), "hotkeys": hotkey_count})
    return summary


def _validate_all_model_references(
    references: dict[str, Any], context: ValidationContext
) -> None:
    singular_keys = {"Moc", "Physics", "Pose", "DisplayInfo", "UserData", "File"}

    def visit(value: Any, label: str, key: str | None = None) -> None:
        if isinstance(value, dict):
            for child_key, child in value.items():
                visit(child, f"{label}.{child_key}", child_key)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{label}[{index}]", key)
        elif isinstance(value, str) and key in singular_keys | {"Textures"}:
            context.reference(value, label)

    visit(references, "model3.FileReferences")


def validate(runtime: Path) -> dict[str, Any]:
    runtime = runtime.expanduser().resolve(strict=False)
    context = ValidationContext(runtime)
    summary: dict[str, Any] = {
        "parameters_expected": len(EXPECTED_PARAMETER_IDS),
        "parameters_cdi": 0,
        "parameters_moc_evidence": 0,
        "moc_bytes": 0,
        "textures": 0,
        "expressions": 0,
        "physics": {"settings": 0, "inputs": 0, "outputs": 0},
        "motions": {},
        "vtube": {"mappings": 0, "hotkeys": 0},
    }
    if not runtime.is_dir():
        context.error(f"runtime: directory is missing: {runtime}")
        return _report(context, summary)

    model_path = runtime / MODEL_FILE
    model = context.json_file(model_path, "model3")
    if model is None:
        return _report(context, summary)
    if model.get("Version") != 3:
        context.error("model3.Version: expected 3")
    references = model.get("FileReferences")
    if not isinstance(references, dict):
        context.error("model3.FileReferences: expected an object")
        references = {}

    expected_fixed_references = {
        "Moc": MOC_FILE,
        "DisplayInfo": CDI_FILE,
        "Physics": PHYSICS_FILE,
    }
    for key, expected in expected_fixed_references.items():
        if references.get(key) != expected:
            context.error(
                f"model3.FileReferences.{key}: expected {expected}, "
                f"got {references.get(key)}"
            )

    moc_path = context.reference(references.get("Moc"), "model3.FileReferences.Moc")
    cdi_path = context.reference(
        references.get("DisplayInfo"), "model3.FileReferences.DisplayInfo"
    )
    physics_path = context.reference(
        references.get("Physics"), "model3.FileReferences.Physics"
    )

    textures = references.get("Textures")
    texture_paths: list[Path] = []
    if not isinstance(textures, list) or not textures:
        context.error("model3.FileReferences.Textures: expected a non-empty array")
    else:
        for index, value in enumerate(textures):
            path = context.reference(
                value, f"model3.FileReferences.Textures[{index}]"
            )
            if path is not None:
                texture_paths.append(path)
                _validate_texture(path, f"texture[{index}]", context)
        folded = [str(path).casefold() for path in texture_paths]
        for duplicate in _duplicates(folded):
            context.error(f"model3.Textures: duplicate reference: {duplicate}")
    summary["textures"] = len(texture_paths)

    _validate_groups(model, context)
    _validate_all_model_references(references, context)

    parameter_ids: set[str] = set()
    if cdi_path is not None:
        parameter_ids, cdi_count = _validate_cdi(cdi_path, context)
        summary["parameters_cdi"] = cdi_count
    if moc_path is not None:
        moc_ids, moc_bytes = _validate_moc(moc_path, context)
        summary["parameters_moc_evidence"] = len(moc_ids)
        summary["moc_bytes"] = moc_bytes

    expression_paths, expression_parameters = _validate_expressions(
        references, parameter_ids, context
    )
    summary["expressions"] = len(expression_paths)
    summary["expression_parameter_ids"] = {
        name: sorted(ids) for name, ids in sorted(expression_parameters.items())
    }
    if physics_path is not None:
        summary["physics"] = _validate_physics(
            physics_path, parameter_ids, context
        )

    summary["motions"] = {
        "idle": _validate_motion(
            runtime / IDLE_FILE,
            IDLE_PARAMETER_IDS,
            parameter_ids,
            "motion.idle",
            context,
        ),
        "tracking_lost": _validate_motion(
            runtime / TRACKING_LOST_FILE,
            TRACKING_LOST_PARAMETER_IDS,
            parameter_ids,
            "motion.tracking_lost",
            context,
        ),
        "proof": _validate_motion(
            runtime / PROOF_FILE,
            PROOF_PARAMETER_IDS,
            parameter_ids,
            "motion.proof",
            context,
        ),
    }
    summary["vtube"] = _validate_vtube(
        runtime / VTUBE_FILE,
        parameter_ids,
        expression_paths,
        context,
    )
    return _report(context, summary)


def _report(context: ValidationContext, summary: dict[str, Any]) -> dict[str, Any]:
    errors = sorted(set(context.errors))
    warnings = sorted(set(context.warnings))
    return {
        "schema": "jade.professional-vts-package-validation.v1",
        "status": "ok" if not errors else "error",
        "runtime": str(context.runtime),
        "summary": summary,
        "errors": errors,
        "warnings": warnings,
        "checked_files": sorted(str(path) for path in context.checked),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runtime", type=Path, help="directory containing Jade.model3.json")
    args = parser.parse_args(list(argv) if argv is not None else None)
    report = validate(args.runtime)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
