#!/usr/bin/env python3
"""Measure the actual CubismCore output of every Jade parameter endpoint.

This is a read-only diagnostic: it does not modify the .moc3 model.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import math
from pathlib import Path


class Vec2(ctypes.Structure):
    _fields_ = [("x", ctypes.c_float), ("y", ctypes.c_float)]


def aligned(size: int, alignment: int = 64) -> tuple[ctypes.Array, int]:
    owner = ctypes.create_string_buffer(size + alignment)
    address = (ctypes.addressof(owner) + alignment - 1) & ~(alignment - 1)
    return owner, address


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(fraction * len(ordered)) - 1))
    return ordered[index]


def audit(moc_path: Path, core_path: Path) -> dict[str, object]:
    core = ctypes.CDLL(str(core_path))
    void_p = ctypes.c_void_p
    float_p = ctypes.POINTER(ctypes.c_float)
    int_p = ctypes.POINTER(ctypes.c_int)

    core.csmReviveMocInPlace.argtypes = [void_p, ctypes.c_uint]
    core.csmReviveMocInPlace.restype = void_p
    core.csmGetSizeofModel.argtypes = [void_p]
    core.csmGetSizeofModel.restype = ctypes.c_uint
    core.csmInitializeModelInPlace.argtypes = [void_p, void_p, ctypes.c_uint]
    core.csmInitializeModelInPlace.restype = void_p
    core.csmUpdateModel.argtypes = [void_p]
    core.csmReadCanvasInfo.argtypes = [void_p, ctypes.POINTER(Vec2), ctypes.POINTER(Vec2), float_p]

    for prefix in ("Parameter", "Drawable"):
        getattr(core, f"csmGet{prefix}Count").argtypes = [void_p]
        getattr(core, f"csmGet{prefix}Count").restype = ctypes.c_int
        getattr(core, f"csmGet{prefix}Ids").argtypes = [void_p]
        getattr(core, f"csmGet{prefix}Ids").restype = ctypes.POINTER(ctypes.c_char_p)
    for function in (
        "csmGetParameterMinimumValues",
        "csmGetParameterMaximumValues",
        "csmGetParameterDefaultValues",
        "csmGetParameterValues",
        "csmGetDrawableOpacities",
    ):
        getattr(core, function).argtypes = [void_p]
        getattr(core, function).restype = float_p
    core.csmGetDrawableVertexCounts.argtypes = [void_p]
    core.csmGetDrawableVertexCounts.restype = int_p
    core.csmGetDrawableVertexPositions.argtypes = [void_p]
    core.csmGetDrawableVertexPositions.restype = ctypes.POINTER(ctypes.POINTER(Vec2))

    moc_bytes = moc_path.read_bytes()
    moc_owner, moc_address = aligned(len(moc_bytes))
    ctypes.memmove(moc_address, moc_bytes, len(moc_bytes))
    moc = core.csmReviveMocInPlace(moc_address, len(moc_bytes))
    if not moc:
        raise RuntimeError("csmReviveMocInPlace failed")

    canvas_size = Vec2()
    canvas_origin = Vec2()
    pixels_per_unit = ctypes.c_float()
    model_size = core.csmGetSizeofModel(moc)
    model_owner, model_address = aligned(model_size)
    model = core.csmInitializeModelInPlace(moc, model_address, model_size)
    if not model:
        raise RuntimeError("csmInitializeModelInPlace failed")

    core.csmReadCanvasInfo(
        model,
        ctypes.byref(canvas_size),
        ctypes.byref(canvas_origin),
        ctypes.byref(pixels_per_unit),
    )

    parameter_count = core.csmGetParameterCount(model)
    parameter_ids = [
        core.csmGetParameterIds(model)[i].decode("utf-8", errors="replace")
        for i in range(parameter_count)
    ]
    minimums = core.csmGetParameterMinimumValues(model)
    maximums = core.csmGetParameterMaximumValues(model)
    defaults = core.csmGetParameterDefaultValues(model)
    values = core.csmGetParameterValues(model)

    drawable_count = core.csmGetDrawableCount(model)
    drawable_ids = [
        core.csmGetDrawableIds(model)[i].decode("utf-8", errors="replace")
        for i in range(drawable_count)
    ]
    vertex_counts = core.csmGetDrawableVertexCounts(model)

    def set_defaults() -> None:
        for index in range(parameter_count):
            values[index] = defaults[index]

    def snapshot() -> tuple[list[list[tuple[float, float]]], list[float]]:
        core.csmUpdateModel(model)
        positions = core.csmGetDrawableVertexPositions(model)
        opacities = core.csmGetDrawableOpacities(model)
        return (
            [
                [
                    (float(positions[d][v].x), float(positions[d][v].y))
                    for v in range(int(vertex_counts[d]))
                ]
                for d in range(drawable_count)
            ],
            [float(opacities[d]) for d in range(drawable_count)],
        )

    set_defaults()
    neutral_positions, neutral_opacities = snapshot()
    all_x = [x for drawable in neutral_positions for x, _ in drawable]
    all_y = [y for drawable in neutral_positions for _, y in drawable]
    neutral_bounds = [min(all_x), min(all_y), max(all_x), max(all_y)]
    neutral_width = neutral_bounds[2] - neutral_bounds[0]
    neutral_height = neutral_bounds[3] - neutral_bounds[1]
    ppu = float(pixels_per_unit.value)

    poses: list[dict[str, object]] = []
    for parameter_index, parameter_id in enumerate(parameter_ids):
        endpoints: list[tuple[str, float]] = []
        minimum = float(minimums[parameter_index])
        maximum = float(maximums[parameter_index])
        default = float(defaults[parameter_index])
        if minimum != default:
            endpoints.append(("min", minimum))
        if maximum != default:
            endpoints.append(("max", maximum))
        if not endpoints:
            endpoints.append(("default", default))

        endpoint_results: list[dict[str, object]] = []
        for endpoint_name, endpoint_value in endpoints:
            set_defaults()
            values[parameter_index] = endpoint_value
            pose_positions, pose_opacities = snapshot()
            all_distances_px: list[float] = []
            drawable_results: list[dict[str, object]] = []
            for drawable_index, drawable_id in enumerate(drawable_ids):
                distances_px: list[float] = []
                dx_values_px: list[float] = []
                dy_values_px: list[float] = []
                for neutral, posed in zip(
                    neutral_positions[drawable_index], pose_positions[drawable_index]
                ):
                    dx_px = (posed[0] - neutral[0]) * ppu
                    dy_px = (posed[1] - neutral[1]) * ppu
                    dx_values_px.append(dx_px)
                    dy_values_px.append(dy_px)
                    distances_px.append(math.hypot(dx_px, dy_px))
                all_distances_px.extend(distances_px)
                max_displacement_px = max(distances_px, default=0.0)
                opacity_delta = pose_opacities[drawable_index] - neutral_opacities[drawable_index]
                if max_displacement_px > 0.001 or abs(opacity_delta) > 0.000001:
                    drawable_results.append(
                        {
                            "id": drawable_id,
                            "vertices": len(distances_px),
                            "max_displacement_px": max_displacement_px,
                            "mean_displacement_px": (
                                sum(distances_px) / len(distances_px) if distances_px else 0.0
                            ),
                            "centroid_shift_px": [
                                sum(dx_values_px) / len(dx_values_px) if dx_values_px else 0.0,
                                sum(dy_values_px) / len(dy_values_px) if dy_values_px else 0.0,
                            ],
                            "opacity_neutral": neutral_opacities[drawable_index],
                            "opacity_pose": pose_opacities[drawable_index],
                            "opacity_delta": opacity_delta,
                        }
                    )

            drawable_results.sort(
                key=lambda item: max(
                    float(item["max_displacement_px"]),
                    abs(float(item["opacity_delta"])) * 100.0,
                ),
                reverse=True,
            )
            moved = [value for value in all_distances_px if value > 0.01]
            max_displacement_px = max(all_distances_px, default=0.0)
            endpoint_results.append(
                {
                    "endpoint": endpoint_name,
                    "value": endpoint_value,
                    "affected_drawables": len(drawable_results),
                    "moved_vertices_over_0_01px": len(moved),
                    "total_vertices": len(all_distances_px),
                    "max_displacement_px": max_displacement_px,
                    "max_displacement_percent_model_height": (
                        max_displacement_px / (neutral_height * ppu) * 100.0
                        if neutral_height and ppu
                        else 0.0
                    ),
                    "mean_displacement_all_vertices_px": (
                        sum(all_distances_px) / len(all_distances_px)
                        if all_distances_px
                        else 0.0
                    ),
                    "rms_displacement_all_vertices_px": (
                        math.sqrt(
                            sum(value * value for value in all_distances_px)
                            / len(all_distances_px)
                        )
                        if all_distances_px
                        else 0.0
                    ),
                    "p95_displacement_all_vertices_px": percentile(all_distances_px, 0.95),
                    "max_opacity_delta": max(
                        (
                            abs(pose_opacities[index] - neutral_opacities[index])
                            for index in range(drawable_count)
                        ),
                        default=0.0,
                    ),
                    "top_affected_drawables": drawable_results[:12],
                }
            )
        poses.append(
            {
                "parameter": parameter_id,
                "minimum": minimum,
                "default": default,
                "maximum": maximum,
                "endpoints": endpoint_results,
            }
        )

    return {
        "schema": "jade.cubismcore.runtime-motion-audit.v1",
        "moc": str(moc_path.resolve()),
        "core": str(core_path.resolve()),
        "model_size_bytes": model_size,
        "canvas": {
            "size_px": [float(canvas_size.x), float(canvas_size.y)],
            "origin_px": [float(canvas_origin.x), float(canvas_origin.y)],
            "pixels_per_unit": ppu,
            "neutral_geometry_bounds_units": neutral_bounds,
            "neutral_geometry_size_px": [neutral_width * ppu, neutral_height * ppu],
        },
        "counts": {
            "parameters": parameter_count,
            "drawables": drawable_count,
            "vertices": sum(int(vertex_counts[i]) for i in range(drawable_count)),
        },
        "parameters": poses,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("moc", type=Path)
    parser.add_argument("core", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.moc, args.core), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
