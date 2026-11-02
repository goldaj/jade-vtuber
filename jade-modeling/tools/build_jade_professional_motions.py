#!/usr/bin/env python3
"""Build Jade's professional idle and rig-proof Cubism motions.

The target is a runtime directory containing a ``*.model3.json`` file, or the
model3 file itself.  Parameter IDs are read from the CDI referenced by model3.
The tool owns exactly three output files in the runtime root:

* ``Jade_idle.motion3.json`` -- a subtle, seamless 15 second idle;
* ``Jade_tracking_lost.motion3.json`` -- a natural 18 second fallback with
  blinks, used only after face tracking is lost;
* ``Jade_proof.motion3.json`` -- an explicit 12 second rig demonstration.

The model3, VTube Studio configuration and every other runtime file are left
untouched.  Re-running the tool is byte-idempotent.  Secondary-motion outputs
owned by ``physics3`` are deliberately never keyed here: head, body and hair
motion drive the physics inputs without competing with its output evaluation.
Their presence or absence in CDI is still reported.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Sequence


IDLE_FILENAME = "Jade_idle.motion3.json"
TRACKING_LOST_FILENAME = "Jade_tracking_lost.motion3.json"
PROOF_FILENAME = "Jade_proof.motion3.json"
FPS = 30.0

PHYSICS_OUTPUT_PARAMETERS = (
    "ParamHairFront",
    "ParamHairSide",
    "ParamHairBack",
    "ParamHairBackC",
    "ParamHairBackLInner",
    "ParamHairBackLOuter",
    "ParamHairBackRInner",
    "ParamHairBackROuter",
    "ParamEarSwingL",
    "ParamEarSwingR",
    "ParamAhogeSwing",
    "ParamClothSwing",
)

IDLE_REQUIRED = (
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

TRACKING_LOST_REQUIRED = (
    *IDLE_REQUIRED,
    "ParamEyeLOpen",
    "ParamEyeROpen",
)

PROOF_REQUIRED = (
    "ParamAngleX",
    "ParamAngleY",
    "ParamAngleZ",
    "ParamEyeLOpen",
    "ParamEyeROpen",
    "ParamEyeLSmile",
    "ParamEyeRSmile",
    "ParamEyeBallX",
    "ParamEyeBallY",
    "ParamBrowLX",
    "ParamBrowRX",
    "ParamBrowLY",
    "ParamBrowRY",
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
    "ParamEarPoseL",
    "ParamEarPoseR",
)


class MotionBuildError(RuntimeError):
    """Raised when the runtime or a generated motion is unsafe to use."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise MotionBuildError(message)


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MotionBuildError(f"cannot read {label}: {path}: {exc}") from exc
    _require(isinstance(value, dict), f"{label} root must be an object")
    return value


def _resolve_model_path(target: Path) -> Path:
    resolved = target.expanduser().resolve(strict=True)
    if resolved.is_file():
        _require(
            resolved.name.endswith(".model3.json"),
            f"expected a model3 file, got {resolved.name}",
        )
        return resolved

    _require(resolved.is_dir(), f"runtime target is not a directory: {resolved}")
    preferred = resolved / "Jade.model3.json"
    if preferred.is_file():
        return preferred
    candidates = sorted(resolved.glob("*.model3.json"))
    _require(candidates, f"no model3 file found in {resolved}")
    _require(
        len(candidates) == 1,
        "runtime contains multiple model3 files; pass the intended file explicitly",
    )
    return candidates[0]


def _resolve_runtime_reference(
    runtime_dir: Path,
    relative: str,
    label: str,
) -> Path:
    _require(relative and relative.strip() == relative, f"{label} path is invalid")
    portable = Path(*relative.replace("\\", "/").split("/"))
    _require(not portable.is_absolute(), f"{label} path must be relative")
    resolved = (runtime_dir / portable).resolve(strict=False)
    _require(
        resolved.is_relative_to(runtime_dir),
        f"{label} path escapes the runtime directory",
    )
    _require(resolved.is_file(), f"{label} file is missing: {resolved}")
    return resolved


def _parameter_ids_from_cdi(cdi: dict[str, Any]) -> set[str]:
    rows = cdi.get("Parameters")
    _require(isinstance(rows, list), "cdi3 Parameters must be an array")
    result: set[str] = set()
    for index, row in enumerate(rows):
        _require(isinstance(row, dict), f"invalid cdi3 Parameters[{index}]")
        parameter_id = row.get("Id")
        _require(
            isinstance(parameter_id, str) and parameter_id,
            f"invalid cdi3 parameter ID at index {index}",
        )
        _require(parameter_id not in result, f"duplicate cdi3 ID: {parameter_id}")
        result.add(parameter_id)
    return result


def _runtime_inputs(target: Path) -> tuple[Path, Path, set[str]]:
    model_path = _resolve_model_path(target)
    runtime_dir = model_path.parent
    model = _load_json(model_path, "model3")
    references = model.get("FileReferences")
    _require(isinstance(references, dict), "model3 FileReferences is missing")
    display_info = references.get("DisplayInfo")
    _require(isinstance(display_info, str), "model3 DisplayInfo is missing")
    cdi_path = _resolve_runtime_reference(runtime_dir, display_info, "DisplayInfo")
    cdi = _load_json(cdi_path, "cdi3")
    return model_path, cdi_path, _parameter_ids_from_cdi(cdi)


def _number(value: float) -> float:
    _require(math.isfinite(value), f"non-finite curve value: {value}")
    rounded = round(float(value), 6)
    return 0.0 if rounded == 0.0 else rounded


def _check_keys(
    keys: Sequence[tuple[float, float]],
    duration: float,
    parameter_id: str,
) -> None:
    _require(len(keys) >= 2, f"{parameter_id} needs at least two keys")
    _require(keys[0][0] == 0.0, f"{parameter_id} must begin at t=0")
    _require(keys[-1][0] == duration, f"{parameter_id} must end at duration")
    previous = -math.inf
    for time, value in keys:
        _require(math.isfinite(time), f"{parameter_id} has a non-finite time")
        _require(time > previous, f"{parameter_id} key times are not increasing")
        _number(value)
        previous = time
    _require(
        keys[0][1] == keys[-1][1],
        f"{parameter_id} is not seamless at the loop boundary",
    )


def _bezier_curve(
    parameter_id: str,
    keys: Sequence[tuple[float, float]],
    duration: float,
) -> tuple[dict[str, Any], int, int]:
    """Build restricted cubic ease-in/ease-out segments between every key."""

    _check_keys(keys, duration, parameter_id)
    segments: list[int | float] = [_number(keys[0][0]), _number(keys[0][1])]
    for (time_a, value_a), (time_b, value_b) in zip(keys, keys[1:]):
        third = (time_b - time_a) / 3.0
        segments.extend(
            (
                1,
                _number(time_a + third),
                _number(value_a),
                _number(time_a + 2.0 * third),
                _number(value_b),
                _number(time_b),
                _number(value_b),
            )
        )
    segment_count = len(keys) - 1
    point_count = 1 + 3 * segment_count
    curve = {"Target": "Parameter", "Id": parameter_id, "Segments": segments}
    return curve, segment_count, point_count


def _linear_curve(
    parameter_id: str,
    keys: Sequence[tuple[float, float]],
    duration: float,
) -> tuple[dict[str, Any], int, int]:
    _check_keys(keys, duration, parameter_id)
    segments: list[int | float] = [_number(keys[0][0]), _number(keys[0][1])]
    for time, value in keys[1:]:
        segments.extend((0, _number(time), _number(value)))
    segment_count = len(keys) - 1
    point_count = len(keys)
    curve = {"Target": "Parameter", "Id": parameter_id, "Segments": segments}
    return curve, segment_count, point_count


def _motion_document(
    duration: float,
    curves_with_counts: Sequence[tuple[dict[str, Any], int, int]],
    fade: float,
) -> dict[str, Any]:
    curves = [row[0] for row in curves_with_counts]
    segment_count = sum(row[1] for row in curves_with_counts)
    point_count = sum(row[2] for row in curves_with_counts)
    return {
        "Version": 3,
        "Meta": {
            "Duration": duration,
            "Fps": FPS,
            "FadeInTime": fade,
            "FadeOutTime": fade,
            "Loop": True,
            "AreBeziersRestricted": True,
            "CurveCount": len(curves),
            "TotalSegmentCount": segment_count,
            "TotalPointCount": point_count,
            "UserDataCount": 0,
            "TotalUserDataSize": 0,
        },
        "Curves": curves,
    }


def _build_idle() -> dict[str, Any]:
    duration = 15.0
    curves: list[tuple[dict[str, Any], int, int]] = []

    def smooth(parameter_id: str, keys: Sequence[tuple[float, float]]) -> None:
        curves.append(_bezier_curve(parameter_id, keys, duration))

    smooth("ParamAngleX", ((0, 0), (3.2, -2.2), (7.5, 2.6), (11.8, -1.4), (15, 0)))
    smooth("ParamAngleY", ((0, 0), (4.0, 1.1), (9.2, -1.0), (12.7, 0.6), (15, 0)))
    smooth("ParamAngleZ", ((0, 0), (3.75, -1.0), (8.5, 0.8), (11.7, -0.6), (15, 0)))
    smooth("ParamEyeBallX", ((0, 0), (3.0, -0.12), (5.0, -0.12), (8.1, 0.16), (10.0, 0.16), (13.0, -0.05), (15, 0)))
    smooth("ParamEyeBallY", ((0, 0), (4.2, 0.05), (7.2, -0.06), (10.8, 0.04), (15, 0)))

    smooth("ParamBodyAngleX", ((0, 0), (3.8, 0.7), (8.2, -0.8), (12.0, 0.5), (15, 0)))
    smooth("ParamBodyAngleY", ((0, 0), (5.0, 0.35), (10.0, -0.35), (15, 0)))
    smooth("ParamBodyAngleZ", ((0, 0), (4.0, -0.55), (8.0, 0.65), (12.0, -0.4), (15, 0)))
    smooth("ParamBreath", ((0, 0.2), (1.875, 0.82), (3.75, 0.2), (5.625, 0.82), (7.5, 0.2), (9.375, 0.82), (11.25, 0.2), (13.125, 0.82), (15, 0.2)))
    return _motion_document(duration, curves, fade=0.8)


def _build_tracking_lost() -> dict[str, Any]:
    """Build an autonomous fallback without touching expression/physics IDs."""

    duration = 18.0
    curves: list[tuple[dict[str, Any], int, int]] = []

    def smooth(parameter_id: str, keys: Sequence[tuple[float, float]]) -> None:
        curves.append(_bezier_curve(parameter_id, keys, duration))

    # A little more authored than the normal idle, because there is no face
    # signal to take over these P1 curves while tracking is absent.
    smooth(
        "ParamAngleX",
        ((0, 0), (3.4, -4.8), (7.7, 3.8), (12.2, -3.0), (15.4, 2.0), (18, 0)),
    )
    smooth(
        "ParamAngleY",
        ((0, 0), (4.2, 2.0), (8.5, -1.7), (13.0, 1.2), (18, 0)),
    )
    smooth(
        "ParamAngleZ",
        ((0, 0), (3.8, -1.8), (8.2, 1.5), (13.4, -1.1), (18, 0)),
    )
    smooth(
        "ParamEyeBallX",
        (
            (0, 0),
            (2.8, -0.22),
            (5.0, -0.22),
            (8.0, 0.28),
            (10.4, 0.28),
            (14.0, -0.12),
            (16.0, -0.12),
            (18, 0),
        ),
    )
    smooth(
        "ParamEyeBallY",
        ((0, 0), (3.0, 0.08), (7.0, -0.10), (11.4, 0.07), (15.2, -0.04), (18, 0)),
    )

    blink_keys = (
        (0, 1),
        (4.00, 1),
        (4.09, 0.18),
        (4.16, 0),
        (4.31, 1),
        (9.05, 1),
        (9.14, 0.16),
        (9.21, 0),
        (9.36, 1),
        (14.48, 1),
        (14.56, 0.20),
        (14.63, 0),
        (14.78, 1),
        (14.97, 1),
        (15.05, 0.15),
        (15.12, 0),
        (15.27, 1),
        (18, 1),
    )
    smooth("ParamEyeLOpen", blink_keys)
    smooth("ParamEyeROpen", blink_keys)

    smooth(
        "ParamBodyAngleX",
        ((0, 0), (4.0, 1.5), (8.5, -1.3), (13.0, 1.0), (18, 0)),
    )
    smooth(
        "ParamBodyAngleY",
        ((0, 0), (4.5, 0.7), (9.0, -0.6), (13.5, 0.45), (18, 0)),
    )
    smooth(
        "ParamBodyAngleZ",
        ((0, 0), (4.0, -1.1), (8.5, 1.2), (13.0, -0.8), (18, 0)),
    )
    smooth(
        "ParamBreath",
        (
            (0, 0.2),
            (2.25, 0.82),
            (4.5, 0.2),
            (6.75, 0.82),
            (9, 0.2),
            (11.25, 0.82),
            (13.5, 0.2),
            (15.75, 0.82),
            (18, 0.2),
        ),
    )
    return _motion_document(duration, curves, fade=0.9)


def _build_proof() -> dict[str, Any]:
    duration = 12.0
    curves: list[tuple[dict[str, Any], int, int]] = []

    def smooth(parameter_id: str, keys: Sequence[tuple[float, float]]) -> None:
        curves.append(_bezier_curve(parameter_id, keys, duration))

    def linear(parameter_id: str, keys: Sequence[tuple[float, float]]) -> None:
        curves.append(_linear_curve(parameter_id, keys, duration))

    # Keep the head perfectly still during the slow eye sweep.  The former
    # proof blink lasted only ~170 ms while Angle X/Y/Z moved, which made the
    # eyelid handoff impossible to judge in a ScreenToGif close-up.
    eye_proof = (
        (0, 1),
        (1.0, 1),
        (2.5, 0),
        (3.0, 0),
        (4.5, 1),
        (5.20, 1),
        (5.35, 0),
        (5.55, 1),
        (12, 1),
    )
    linear("ParamEyeLOpen", eye_proof)
    linear("ParamEyeROpen", eye_proof)
    linear("ParamEyeLSmile", ((0, 0), (12, 0)))
    linear("ParamEyeRSmile", ((0, 0), (12, 0)))

    # Lock every other facial control at neutral while the proof runs.  This
    # keeps the eyelid relay readable and prevents VTube Studio tracking or a
    # stale expression from contaminating the recorded reference.
    for parameter_id in (
        "ParamEyeBallX",
        "ParamEyeBallY",
        "ParamBrowLX",
        "ParamBrowLY",
        "ParamBrowLAngle",
        "ParamBrowLForm",
        "ParamBrowRX",
        "ParamBrowRY",
        "ParamBrowRAngle",
        "ParamBrowRForm",
        "ParamMouthForm",
        "ParamMouthOpenY",
        "ParamCheek",
    ):
        linear(parameter_id, ((0, 0), (12, 0)))

    # After the eye gate, exercise the explicit ear poses, then sweep the head
    # so the existing physics chains visibly drive the independent hair locks.
    ear_poses = (
        (0, 0),
        (6.0, 0),
        (6.25, 1),
        (6.65, 1),
        (6.85, 0),
        (7.10, -1),
        (7.50, -1),
        (7.70, 0),
        (12, 0),
    )
    smooth("ParamEarPoseL", ear_poses)
    smooth("ParamEarPoseR", ear_poses)
    smooth("ParamAngleX", ((0, 0), (7.7, 0), (8.35, -22), (9.0, 0), (9.65, 22), (10.3, 0), (12, 0)))
    smooth("ParamAngleY", ((0, 0), (7.7, 0), (8.35, 8), (9.0, 0), (9.65, -8), (10.3, 0), (12, 0)))
    smooth("ParamAngleZ", ((0, 0), (7.7, 0), (8.35, -9), (9.0, 0), (9.65, 9), (10.3, 0), (12, 0)))
    smooth("ParamBodyAngleX", ((0, 0), (7.7, 0), (8.45, -6), (9.1, 0), (9.75, 6), (10.4, 0), (12, 0)))
    smooth("ParamBodyAngleY", ((0, 0), (7.7, 0), (8.45, 3), (9.1, 0), (9.75, -3), (10.4, 0), (12, 0)))
    smooth("ParamBodyAngleZ", ((0, 0), (7.7, 0), (8.45, -4), (9.1, 0), (9.75, 4), (10.4, 0), (12, 0)))
    smooth("ParamBreath", ((0, 0.2), (6, 0.2), (7, 0.8), (8, 0.2), (12, 0.2)))
    return _motion_document(duration, curves, fade=0.1)


def _computed_counts(motion: dict[str, Any]) -> tuple[int, int, int]:
    curves = motion.get("Curves")
    _require(isinstance(curves, list), "motion Curves must be an array")
    total_segments = 0
    total_points = 0
    for curve_index, curve in enumerate(curves):
        _require(isinstance(curve, dict), f"invalid curve {curve_index}")
        segments = curve.get("Segments")
        _require(
            isinstance(segments, list) and len(segments) >= 2,
            f"curve {curve_index} has invalid Segments",
        )
        cursor = 2
        points = 1
        while cursor < len(segments):
            segment_type = segments[cursor]
            _require(
                isinstance(segment_type, int) and segment_type in {0, 1, 2, 3},
                f"curve {curve_index} has invalid segment type at {cursor}",
            )
            width = 7 if segment_type == 1 else 3
            _require(
                cursor + width <= len(segments),
                f"curve {curve_index} has a truncated segment",
            )
            values = segments[cursor + 1 : cursor + width]
            _require(
                all(isinstance(value, (int, float)) and math.isfinite(value) for value in values),
                f"curve {curve_index} has a non-finite segment value",
            )
            total_segments += 1
            points += 3 if segment_type == 1 else 1
            cursor += width
        _require(cursor == len(segments), f"curve {curve_index} has trailing data")
        total_points += points
    return len(curves), total_segments, total_points


def _validate_motion(
    motion: dict[str, Any],
    cdi_parameter_ids: set[str],
    filename: str,
) -> None:
    _require(motion.get("Version") == 3, f"{filename}: Version must be 3")
    meta = motion.get("Meta")
    curves = motion.get("Curves")
    _require(isinstance(meta, dict), f"{filename}: Meta is missing")
    _require(isinstance(curves, list), f"{filename}: Curves is missing")
    duration = meta.get("Duration")
    _require(isinstance(duration, (int, float)), f"{filename}: invalid Duration")
    observed: set[str] = set()
    for curve in curves:
        _require(isinstance(curve, dict), f"{filename}: invalid curve")
        _require(curve.get("Target") == "Parameter", f"{filename}: invalid Target")
        parameter_id = curve.get("Id")
        _require(isinstance(parameter_id, str), f"{filename}: invalid curve ID")
        _require(parameter_id in cdi_parameter_ids, f"{filename}: ID absent from CDI: {parameter_id}")
        _require(parameter_id not in observed, f"{filename}: duplicate curve: {parameter_id}")
        observed.add(parameter_id)
        segments = curve.get("Segments")
        _require(isinstance(segments, list), f"{filename}: invalid Segments")
        _require(segments[0] == 0.0, f"{filename}: {parameter_id} does not start at 0")
        _require(segments[-2] == duration, f"{filename}: {parameter_id} does not end at duration")
        _require(segments[1] == segments[-1], f"{filename}: {parameter_id} loop is discontinuous")
    curve_count, segment_count, point_count = _computed_counts(motion)
    _require(meta.get("CurveCount") == curve_count, f"{filename}: CurveCount mismatch")
    _require(
        meta.get("TotalSegmentCount") == segment_count,
        f"{filename}: TotalSegmentCount mismatch",
    )
    _require(
        meta.get("TotalPointCount") == point_count,
        f"{filename}: TotalPointCount mismatch",
    )
    _require(meta.get("UserDataCount") == 0, f"{filename}: UserDataCount mismatch")
    _require(meta.get("TotalUserDataSize") == 0, f"{filename}: user data mismatch")


def _json_bytes(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _atomic_write_if_changed(path: Path, payload: bytes) -> str:
    if path.is_file() and path.read_bytes() == payload:
        return "unchanged"
    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp_path.write_bytes(payload)
        os.replace(temp_path, path)
    except OSError as exc:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise MotionBuildError(f"cannot write {path}: {exc}") from exc
    return "written"


def build(target: Path, dry_run: bool = False) -> dict[str, Any]:
    model_path, cdi_path, parameter_ids = _runtime_inputs(target)
    missing_idle = sorted(set(IDLE_REQUIRED) - parameter_ids)
    missing_tracking_lost = sorted(set(TRACKING_LOST_REQUIRED) - parameter_ids)
    missing_proof = sorted(set(PROOF_REQUIRED) - parameter_ids)
    _require(not missing_idle, "runtime lacks idle parameters: " + ", ".join(missing_idle))
    _require(
        not missing_tracking_lost,
        "runtime lacks tracking-lost parameters: " + ", ".join(missing_tracking_lost),
    )
    _require(not missing_proof, "runtime lacks proof parameters: " + ", ".join(missing_proof))

    physics_outputs_present = set(PHYSICS_OUTPUT_PARAMETERS) & parameter_ids
    physics_outputs_absent = sorted(
        set(PHYSICS_OUTPUT_PARAMETERS) - physics_outputs_present
    )
    idle = _build_idle()
    tracking_lost = _build_tracking_lost()
    proof = _build_proof()
    _validate_motion(idle, parameter_ids, IDLE_FILENAME)
    _validate_motion(
        tracking_lost,
        parameter_ids,
        TRACKING_LOST_FILENAME,
    )
    _validate_motion(proof, parameter_ids, PROOF_FILENAME)

    documents = (
        (IDLE_FILENAME, idle),
        (TRACKING_LOST_FILENAME, tracking_lost),
        (PROOF_FILENAME, proof),
    )
    output_rows: list[dict[str, Any]] = []
    for filename, document in documents:
        output_path = model_path.parent / filename
        payload = _json_bytes(document)
        state = "dry-run" if dry_run else _atomic_write_if_changed(output_path, payload)
        meta = document["Meta"]
        output_rows.append(
            {
                "file": str(output_path),
                "state": state,
                "bytes": len(payload),
                "duration": meta["Duration"],
                "curve_count": meta["CurveCount"],
                "segment_count": meta["TotalSegmentCount"],
                "point_count": meta["TotalPointCount"],
                "parameter_ids": [curve["Id"] for curve in document["Curves"]],
            }
        )

    return {
        "status": "ok",
        "dry_run": dry_run,
        "runtime": str(model_path.parent),
        "model3": str(model_path),
        "cdi3": str(cdi_path),
        "cdi_parameter_count": len(parameter_ids),
        "physics_outputs_present": sorted(physics_outputs_present),
        "physics_outputs_absent": physics_outputs_absent,
        "physics_outputs_omitted_from_motion_curves": sorted(
            physics_outputs_present
        ),
        "physics_output_policy": (
            "physics3 exclusively owns these destinations; motions drive head/body inputs"
        ),
        "outputs": output_rows,
        "runtime_files_modified": [] if dry_run else [row["file"] for row in output_rows if row["state"] == "written"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "target",
        type=Path,
        help="runtime directory or explicit *.model3.json file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and report the generated motions without writing files",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = build(args.target, dry_run=args.dry_run)
    except (MotionBuildError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
