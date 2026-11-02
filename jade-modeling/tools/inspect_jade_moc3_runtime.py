#!/usr/bin/env python3
"""Inspect default CubismCore state for the exported Jade runtime model."""

from __future__ import annotations

import argparse
import ctypes
import json
from pathlib import Path


class Vec2(ctypes.Structure):
    _fields_ = [("x", ctypes.c_float), ("y", ctypes.c_float)]


def _aligned(size: int, alignment: int = 64) -> tuple[ctypes.Array, int]:
    owner = ctypes.create_string_buffer(size + alignment)
    address = (ctypes.addressof(owner) + alignment - 1) & ~(alignment - 1)
    return owner, address


def _ids(pointer: ctypes.POINTER(ctypes.c_char_p), count: int) -> list[str]:
    return [pointer[index].decode("utf-8", errors="replace") for index in range(count)]


def inspect(moc_path: Path, core_path: Path) -> dict[str, object]:
    core = ctypes.CDLL(str(core_path))

    core.csmReviveMocInPlace.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    core.csmReviveMocInPlace.restype = ctypes.c_void_p
    core.csmGetSizeofModel.argtypes = [ctypes.c_void_p]
    core.csmGetSizeofModel.restype = ctypes.c_uint
    core.csmInitializeModelInPlace.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint,
    ]
    core.csmInitializeModelInPlace.restype = ctypes.c_void_p
    core.csmUpdateModel.argtypes = [ctypes.c_void_p]

    for name in ("Parameter", "Part", "Drawable"):
        getattr(core, f"csmGet{name}Count").argtypes = [ctypes.c_void_p]
        getattr(core, f"csmGet{name}Count").restype = ctypes.c_int
        getattr(core, f"csmGet{name}Ids").argtypes = [ctypes.c_void_p]
        getattr(core, f"csmGet{name}Ids").restype = ctypes.POINTER(ctypes.c_char_p)

    float_pointer = ctypes.POINTER(ctypes.c_float)
    int_pointer = ctypes.POINTER(ctypes.c_int)
    for function in (
        "csmGetParameterMinimumValues",
        "csmGetParameterMaximumValues",
        "csmGetParameterDefaultValues",
        "csmGetParameterValues",
        "csmGetPartOpacities",
        "csmGetDrawableOpacities",
    ):
        getattr(core, function).argtypes = [ctypes.c_void_p]
        getattr(core, function).restype = float_pointer
    for function in (
        "csmGetPartParentPartIndices",
        "csmGetDrawableParentPartIndices",
        "csmGetDrawableVertexCounts",
        "csmGetDrawableTextureIndices",
        "csmGetDrawableDrawOrders",
        "csmGetDrawableRenderOrders",
    ):
        getattr(core, function).argtypes = [ctypes.c_void_p]
        getattr(core, function).restype = int_pointer
    for function in ("csmGetDrawableVertexPositions", "csmGetDrawableVertexUvs"):
        getattr(core, function).argtypes = [ctypes.c_void_p]
        getattr(core, function).restype = ctypes.POINTER(ctypes.POINTER(Vec2))

    moc_bytes = moc_path.read_bytes()
    moc_owner, moc_address = _aligned(len(moc_bytes))
    ctypes.memmove(moc_address, moc_bytes, len(moc_bytes))
    moc = core.csmReviveMocInPlace(moc_address, len(moc_bytes))
    if not moc:
        raise RuntimeError("csmReviveMocInPlace failed")
    model_size = core.csmGetSizeofModel(moc)
    model_owner, model_address = _aligned(model_size)
    model = core.csmInitializeModelInPlace(moc, model_address, model_size)
    if not model:
        raise RuntimeError("csmInitializeModelInPlace failed")
    core.csmUpdateModel(model)

    parameter_count = core.csmGetParameterCount(model)
    parameter_ids = _ids(core.csmGetParameterIds(model), parameter_count)
    minimums = core.csmGetParameterMinimumValues(model)
    maximums = core.csmGetParameterMaximumValues(model)
    defaults = core.csmGetParameterDefaultValues(model)
    values = core.csmGetParameterValues(model)
    parameters = [
        {
            "id": parameter_ids[index],
            "min": float(minimums[index]),
            "default": float(defaults[index]),
            "value": float(values[index]),
            "max": float(maximums[index]),
        }
        for index in range(parameter_count)
    ]

    part_count = core.csmGetPartCount(model)
    part_ids = _ids(core.csmGetPartIds(model), part_count)
    part_opacities = core.csmGetPartOpacities(model)
    part_parents = core.csmGetPartParentPartIndices(model)
    parts = [
        {
            "index": index,
            "id": part_ids[index],
            "parent_index": int(part_parents[index]),
            "opacity": float(part_opacities[index]),
        }
        for index in range(part_count)
    ]

    drawable_count = core.csmGetDrawableCount(model)
    drawable_ids = _ids(core.csmGetDrawableIds(model), drawable_count)
    drawable_opacities = core.csmGetDrawableOpacities(model)
    drawable_parents = core.csmGetDrawableParentPartIndices(model)
    vertex_counts = core.csmGetDrawableVertexCounts(model)
    positions = core.csmGetDrawableVertexPositions(model)
    uvs = core.csmGetDrawableVertexUvs(model)
    texture_indices = core.csmGetDrawableTextureIndices(model)
    draw_orders = core.csmGetDrawableDrawOrders(model)
    render_orders = core.csmGetDrawableRenderOrders(model)
    drawables: list[dict[str, object]] = []
    for index in range(drawable_count):
        count = int(vertex_counts[index])
        xy = [positions[index][vertex] for vertex in range(count)]
        uv = [uvs[index][vertex] for vertex in range(count)]
        parent = int(drawable_parents[index])
        drawables.append(
            {
                "index": index,
                "id": drawable_ids[index],
                "parent_part_index": parent,
                "parent_part_id": part_ids[parent] if 0 <= parent < part_count else None,
                "opacity": float(drawable_opacities[index]),
                "texture": int(texture_indices[index]),
                "draw_order": int(draw_orders[index]),
                "render_order": int(render_orders[index]),
                "vertex_count": count,
                "bounds": [
                    min(float(point.x) for point in xy),
                    min(float(point.y) for point in xy),
                    max(float(point.x) for point in xy),
                    max(float(point.y) for point in xy),
                ],
                "uv_bounds": [
                    min(float(point.x) for point in uv),
                    min(float(point.y) for point in uv),
                    max(float(point.x) for point in uv),
                    max(float(point.y) for point in uv),
                ],
            }
        )

    del model_owner, moc_owner
    return {
        "moc": str(moc_path),
        "model_size": model_size,
        "parameters": parameters,
        "parts": parts,
        "drawables": drawables,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("moc", type=Path)
    parser.add_argument("core", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.moc.resolve(), args.core.resolve()), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
