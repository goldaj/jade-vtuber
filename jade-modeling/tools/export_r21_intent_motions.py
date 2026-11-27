"""Export the editable PSD2Live curves used by the r21 intent motions.

This exporter only writes motion3 files, never a rig or an atlas. The input is
the same list of motion.put payloads used by the existing r21 animation sources.
Bezier handles are normalised in time and relative to their key's value.

Example (from the repository root):
    python jade-modeling/tools/export_r21_intent_motions.py SOURCE.json OUTPUT_DIR
Add --check to compare committed exports without writing anything.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return float(value)


def export_motion(source: dict) -> dict:
    """Convert explicit, restricted Bezier/linear keys to Cubism motion v3."""
    duration = _number(source["duration"], "duration")
    if duration <= 0:
        raise ValueError("duration must be positive")
    curves = []
    ids = set()
    segment_count = point_count = 0
    for curve in source["curves"]:
        parameter = curve["parameter"]
        if not isinstance(parameter, str) or not parameter or parameter in ids:
            raise ValueError("curve parameter IDs must be unique nonempty strings")
        ids.add(parameter)
        keys = curve["keys"]
        if len(keys) < 2:
            raise ValueError(f"{parameter} needs at least two keys")
        times = [_number(key["time"], "key time") for key in keys]
        values = [_number(key["value"], "key value") for key in keys]
        if times[0] != 0 or times[-1] != duration or any(a >= b for a, b in zip(times, times[1:])):
            raise ValueError(f"{parameter} keys must run strictly from zero to duration")
        segments = [times[0], values[0]]
        point_count += 1
        for index, (first, last) in enumerate(zip(keys, keys[1:])):
            t0, t1 = times[index:index + 2]
            v0, v1 = values[index:index + 2]
            interpolation = first.get("interpolation", "LINEAR")
            if interpolation == "LINEAR":
                segments.extend([0, t1, v1])
                point_count += 1
            elif interpolation == "BEZIER":
                out, incoming = first["out"], last["in"]
                if len(out) != 2 or len(incoming) != 2:
                    raise ValueError("Bezier handles must have two components")
                # Cubism's restricted Bezier mode expects control times at
                # one and two thirds of the interval, as in the r21 sources.
                if not math.isclose(_number(out[0], "out time"), 1 / 3, abs_tol=1e-6) or not math.isclose(
                    _number(incoming[0], "in time"), 1 / 3, abs_tol=1e-6
                ):
                    raise ValueError("r21 exports require restricted Bezier handles")
                span = t1 - t0
                segments.extend([
                    1, round(t0 + span / 3, 6), round(v0 + _number(out[1], "out value"), 6),
                    round(t1 - span / 3, 6), round(v1 + _number(incoming[1], "in value"), 6),
                    t1, v1,
                ])
                point_count += 3
            else:
                raise ValueError(f"Unsupported interpolation {interpolation!r}")
            segment_count += 1
        curves.append({"Target": "Parameter", "Id": parameter, "Segments": segments})
    if not curves:
        raise ValueError("a motion needs at least one curve")
    fps = _number(source["fps"], "fps")
    fade_in = _number(source["fade_in"], "fade_in")
    fade_out = _number(source["fade_out"], "fade_out")
    if fps <= 0 or min(fade_in, fade_out) < 0:
        raise ValueError("fps must be positive and fades nonnegative")
    return {
        "Version": 3,
        "Meta": {
            "Duration": duration, "Fps": fps,
            "FadeInTime": fade_in, "FadeOutTime": fade_out,
            "Loop": bool(source.get("loop", False)), "AreBeziersRestricted": True,
            "CurveCount": len(curves), "TotalSegmentCount": segment_count,
            "TotalPointCount": point_count, "UserDataCount": 0, "TotalUserDataSize": 0,
        },
        "Curves": curves,
    }


def export_file(source_file: Path, output_dir: Path, *, check: bool = False) -> list[Path]:
    source = json.loads(source_file.read_text(encoding="utf-8"))
    paths = []
    for motion in source:
        motion_id = motion["id"]
        if not isinstance(motion_id, str) or Path(motion_id).name != motion_id or "\\" in motion_id:
            raise ValueError("motion IDs must be simple file names")
        path = output_dir / f"{motion_id}.motion3.json"
        exported = export_motion(motion)
        if check:
            if not path.is_file() or json.loads(path.read_text(encoding="utf-8")) != exported:
                raise ValueError(f"Export differs from its editable source: {path}")
        else:
            output_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(exported, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        paths.append(path)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    paths = export_file(args.source, args.output_dir, check=args.check)
    print(f"{'Checked' if args.check else 'Exported'} {len(paths)} r21 motions")


if __name__ == "__main__":
    main()
