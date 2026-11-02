#!/usr/bin/env python3
"""Build Jade r20's long-form professional idle motions.

The r20 pass deliberately changes motion data only.  It keeps the validated
r09 eyelid art, r18 hair physics and r19b Surprise-ear art untouched.  VTube
Studio AutoBlink exclusively owns random idle blinking (P2), so these P1
motions deliberately contain no EyeOpen curves.  Normal ear twitches are
authored on the negative side of ParamEarPoseL/R; physics continues to own
ParamEarSwingL/R exclusively.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from build_jade_professional_motions import (
    FPS,
    MotionBuildError,
    _atomic_write_if_changed,
    _bezier_curve,
    _computed_counts,
    _json_bytes,
    _motion_document,
    _runtime_inputs,
    _validate_motion,
)


IDLE_FILENAME = "Jade_idle.motion3.json"
TRACKING_LOST_FILENAME = "Jade_tracking_lost.motion3.json"
REQUIRED_PARAMETERS = frozenset(
    {
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
    }
)


def _build_idle() -> dict[str, Any]:
    duration = 30.0
    curves: list[tuple[dict[str, Any], int, int]] = []

    def smooth(parameter_id: str, keys: Sequence[tuple[float, float]]) -> None:
        curves.append(_bezier_curve(parameter_id, keys, duration))

    # Irregular timing avoids the visible pendulum cadence of the former 15 s
    # loop while keeping the face readable at Twitch crop sizes.
    smooth(
        "ParamAngleX",
        (
            (0, 0),
            (3.30, -2.4),
            (4.10, -2.4),
            (7.40, 1.6),
            (8.10, 1.6),
            (12.00, 2.8),
            (12.80, 2.8),
            (16.50, -1.9),
            (17.30, -1.9),
            (22.30, 1.2),
            (23.00, 1.2),
            (26.70, -1.0),
            (27.50, -1.0),
            (30, 0),
        ),
    )
    smooth(
        "ParamAngleY",
        (
            (0, 0),
            (4.30, 1.0),
            (5.00, 1.0),
            (9.50, -0.7),
            (10.25, -0.7),
            (13.95, 1.3),
            (14.70, 1.3),
            (20.05, -1.0),
            (20.80, -1.0),
            (25.50, 0.55),
            (26.15, 0.55),
            (30, 0),
        ),
    )
    smooth(
        "ParamAngleZ",
        (
            (0, 0),
            (2.80, -0.8),
            (3.55, -0.8),
            (8.55, 1.1),
            (9.25, 1.1),
            (13.35, -1.2),
            (14.10, -1.2),
            (19.25, 0.75),
            (20.00, 0.75),
            (24.75, -0.55),
            (25.45, -0.55),
            (30, 0),
        ),
    )
    smooth(
        "ParamEyeBallX",
        (
            (0, 0),
            (3.70, 0),
            (3.86, -0.10),
            (6.00, -0.10),
            (6.16, 0.14),
            (10.80, 0.14),
            (10.96, -0.06),
            (15.50, -0.06),
            (15.66, 0.05),
            (19.00, 0.05),
            (19.16, 0),
            (23.00, 0),
            (23.16, -0.08),
            (26.80, -0.08),
            (26.98, 0),
            (30, 0),
        ),
    )
    smooth(
        "ParamEyeBallY",
        (
            (0, 0),
            (5.20, 0),
            (5.34, 0.04),
            (9.80, 0.04),
            (9.94, -0.05),
            (14.70, -0.05),
            (14.84, 0.03),
            (20.80, 0.03),
            (20.94, -0.04),
            (25.60, -0.04),
            (25.75, 0.02),
            (27.60, 0.02),
            (27.75, 0),
            (30, 0),
        ),
    )

    # Body follows the head with smaller, delayed arcs.
    smooth(
        "ParamBodyAngleX",
        (
            (0, 0),
            (4.4, -0.62),
            (8.3, 0.42),
            (13.1, 0.85),
            (17.5, -0.58),
            (23.4, 0.36),
            (27.7, -0.30),
            (30, 0),
        ),
    )
    smooth(
        "ParamBodyAngleY",
        (
            (0, 0),
            (5.4, 0.32),
            (10.6, -0.22),
            (15.0, 0.45),
            (21.1, -0.32),
            (26.5, 0.18),
            (30, 0),
        ),
    )
    smooth(
        "ParamBodyAngleZ",
        (
            (0, 0),
            (3.8, -0.40),
            (9.6, 0.55),
            (14.4, -0.60),
            (20.3, 0.38),
            (25.8, -0.28),
            (30, 0),
        ),
    )
    smooth(
        "ParamBreath",
        (
            (0, 0.20),
            (2.50, 0.78),
            (4.95, 0.20),
            (7.40, 0.78),
            (9.90, 0.20),
            (12.45, 0.78),
            (14.95, 0.20),
            (17.35, 0.78),
            (19.80, 0.20),
            (22.30, 0.78),
            (24.90, 0.20),
            (27.40, 0.78),
            (30.00, 0.20),
        ),
    )

    # Negative pose values use only the established neutral-ear art.  The
    # r19b Surprise handoff begins at +0.66 and therefore cannot leak here.
    smooth(
        "ParamEarPoseL",
        (
            (0, 0),
            (8.08, 0),
            (8.18, -0.12),
            (8.26, -0.22),
            (8.36, -0.08),
            (8.50, 0),
            (30, 0),
        ),
    )
    smooth(
        "ParamEarPoseR",
        (
            (0, 0),
            (18.92, 0),
            (19.02, -0.11),
            (19.10, -0.20),
            (19.20, -0.06),
            (19.34, 0),
            (30, 0),
        ),
    )
    return _motion_document(duration, curves, fade=0.8)


def _build_tracking_lost() -> dict[str, Any]:
    duration = 30.0
    curves: list[tuple[dict[str, Any], int, int]] = []

    def smooth(parameter_id: str, keys: Sequence[tuple[float, float]]) -> None:
        curves.append(_bezier_curve(parameter_id, keys, duration))

    smooth(
        "ParamAngleX",
        ((0, 0), (3.75, -3.7), (4.45, -3.7), (8.85, 2.8), (9.55, 2.8), (14.25, 4.0), (15.00, 4.0), (19.75, -3.2), (20.50, -3.2), (25.05, 2.1), (25.75, 2.1), (30, 0)),
    )
    smooth(
        "ParamAngleY",
        ((0, 0), (4.45, 1.7), (5.15, 1.7), (10.05, -1.3), (10.75, -1.3), (15.45, 2.0), (16.20, 2.0), (21.55, -1.5), (22.30, -1.5), (26.35, 0.8), (27.00, 0.8), (30, 0)),
    )
    smooth(
        "ParamAngleZ",
        ((0, 0), (3.35, -1.4), (4.05, -1.4), (9.35, 1.6), (10.05, 1.6), (14.65, -1.8), (15.40, -1.8), (20.85, 1.2), (21.60, 1.2), (26.05, -0.8), (26.70, -0.8), (30, 0)),
    )
    smooth(
        "ParamEyeBallX",
        ((0, 0), (2.90, 0), (3.08, -0.20), (5.80, -0.20), (5.98, 0.24), (10.80, 0.24), (10.98, -0.12), (15.60, -0.12), (15.78, 0.10), (19.80, 0.10), (19.98, -0.08), (23.10, -0.08), (23.28, 0.09), (27.00, 0.09), (27.20, 0), (30, 0)),
    )
    smooth(
        "ParamEyeBallY",
        ((0, 0), (4.00, 0), (4.16, 0.07), (8.70, 0.07), (8.86, -0.09), (13.80, -0.09), (13.96, 0.06), (19.30, 0.06), (19.46, -0.06), (24.70, -0.06), (24.86, 0.04), (27.80, 0.04), (27.96, 0), (30, 0)),
    )
    smooth(
        "ParamBodyAngleX",
        ((0, 0), (4.8, -1.1), (9.9, 0.8), (15.3, 1.35), (20.8, -1.0), (26.1, 0.7), (30, 0)),
    )
    smooth(
        "ParamBodyAngleY",
        ((0, 0), (5.4, 0.55), (11.0, -0.40), (16.5, 0.65), (22.5, -0.50), (27.2, 0.26), (30, 0)),
    )
    smooth(
        "ParamBodyAngleZ",
        ((0, 0), (4.4, -0.72), (10.4, 0.82), (15.7, -0.90), (21.9, 0.62), (27.1, -0.38), (30, 0)),
    )
    smooth(
        "ParamBreath",
        ((0, 0.20), (2.5, 0.80), (5, 0.20), (7.5, 0.80), (10, 0.20), (12.5, 0.80), (15, 0.20), (17.5, 0.80), (20, 0.20), (22.5, 0.80), (25, 0.20), (27.5, 0.80), (30, 0.20)),
    )
    smooth(
        "ParamEarPoseL",
        ((0, 0), (6.24, 0), (6.34, -0.15), (6.43, -0.28), (6.55, -0.09), (6.70, 0), (25.84, 0), (25.94, -0.10), (26.03, -0.18), (26.14, -0.05), (26.28, 0), (30, 0)),
    )
    smooth(
        "ParamEarPoseR",
        ((0, 0), (17.12, 0), (17.22, -0.14), (17.31, -0.26), (17.43, -0.08), (17.58, 0), (30, 0)),
    )
    return _motion_document(duration, curves, fade=0.9)


def _summary(document: dict[str, Any]) -> dict[str, Any]:
    curves = document["Curves"]
    eye_curves = [row for row in curves if row["Id"] in {"ParamEyeLOpen", "ParamEyeROpen"}]
    ear_curves = [row for row in curves if row["Id"] in {"ParamEarPoseL", "ParamEarPoseR"}]
    return {
        "duration": document["Meta"]["Duration"],
        "fps": document["Meta"]["Fps"],
        "loop": document["Meta"]["Loop"],
        "curve_count": document["Meta"]["CurveCount"],
        "segment_count": document["Meta"]["TotalSegmentCount"],
        "point_count": document["Meta"]["TotalPointCount"],
        "parameter_ids": [row["Id"] for row in curves],
        "eye_curve_count": len(eye_curves),
        "ear_pose_curve_count": len(ear_curves),
        "ear_swing_curves": [row["Id"] for row in curves if "EarSwing" in row["Id"]],
    }


def build(target: Path, dry_run: bool = False) -> dict[str, Any]:
    model_path, cdi_path, parameter_ids = _runtime_inputs(target)
    missing = sorted(REQUIRED_PARAMETERS - parameter_ids)
    if missing:
        raise MotionBuildError("runtime lacks r20 idle parameters: " + ", ".join(missing))

    documents = (
        (IDLE_FILENAME, _build_idle()),
        (TRACKING_LOST_FILENAME, _build_tracking_lost()),
    )
    outputs: list[dict[str, Any]] = []
    for filename, document in documents:
        _validate_motion(document, parameter_ids, filename)
        computed = _computed_counts(document)
        if computed != (
            document["Meta"]["CurveCount"],
            document["Meta"]["TotalSegmentCount"],
            document["Meta"]["TotalPointCount"],
        ):
            raise MotionBuildError(f"{filename}: computed count mismatch")
        path = model_path.parent / filename
        payload = _json_bytes(document)
        state = "dry-run" if dry_run else _atomic_write_if_changed(path, payload)
        outputs.append({"file": str(path), "state": state, "bytes": len(payload), **_summary(document)})

    return {
        "schema": "jade.professional-motions-r20.v1",
        "status": "ok",
        "dry_run": dry_run,
        "runtime": str(model_path.parent),
        "model3": str(model_path),
        "cdi3": str(cdi_path),
        "cdi_parameter_count": len(parameter_ids),
        "physics_output_policy": "ParamEarSwingL/R remain exclusively physics-owned",
        "surprise_safety_policy": "idle ParamEarPose values are <= 0; r19b Surprise art starts at +0.66",
        "blink_policy": "VTube Studio AutoBlink P2 exclusively owns idle blinking; motions omit EyeOpen curves",
        "outputs": outputs,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        report = build(args.target, dry_run=args.dry_run)
    except (MotionBuildError, OSError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
