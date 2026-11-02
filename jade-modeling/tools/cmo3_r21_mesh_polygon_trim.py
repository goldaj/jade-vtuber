#!/usr/bin/env python3
"""Trim an ArtMesh against a convex polygon without changing texture pixels.

``trim_source(sourceElement, polygon_xy)`` mutates the source only after a
complete successful in-memory calculation. Polygon points use the source's
immutable original/canvas coordinate system, not keyform-local coordinates.
UVs, every keyform and editable points are barycentrically interpolated.
No model, texture, archive, or other file is read or written by this helper.

The dependency-free Sutherland-Hodgman path accepts convex polygons, in
either winding, with an optional repeated closing point. Concave polygons
are rejected explicitly rather than silently using their convex hull.
"""
from __future__ import annotations

import math
from typing import Any, Sequence

import cmo3_create_deformer_experiment as experiment
import cmo3_hair_art_partition_r16 as partition

EPS = 1e-9


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _cross(a: Sequence[float], b: Sequence[float], c: Sequence[float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _area(points: Sequence[Sequence[float]]) -> float:
    return 0.5 * sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(points, [*points[1:], points[0]]))


def _polygon(polygon_xy: Sequence[Any]) -> list[tuple[float, float]]:
    values = list(polygon_xy)
    _require(bool(values), "polygon is empty")
    if isinstance(values[0], (int, float)):
        _require(len(values) % 2 == 0, "flattened polygon has odd coordinate count")
        values = list(zip(values[0::2], values[1::2]))
    points = [tuple(map(float, point)) for point in values]
    _require(all(len(point) == 2 for point in points), "polygon points must be XY pairs")
    _require(all(math.isfinite(v) for point in points for v in point), "polygon contains nonfinite coordinates")
    cleaned = []
    for point in points:
        if not cleaned or math.dist(cleaned[-1], point) > EPS:
            cleaned.append(point)
    if len(cleaned) > 1 and math.dist(cleaned[0], cleaned[-1]) <= EPS:
        cleaned.pop()
    _require(len(cleaned) >= 3 and abs(_area(cleaned)) > EPS, "polygon has no area")
    if _area(cleaned) < 0:
        cleaned.reverse()
    # Requiring every point on the same side of every edge also rejects
    # self-intersecting inputs; a local-turn-only check is insufficient.
    _require(all(_cross(a, b, point) >= -EPS for a, b in zip(cleaned, [*cleaned[1:], cleaned[0]]) for point in cleaned),
             "polygon must be convex and simple (no automatic hull conversion)")
    return cleaned


def _clip(subject: list[tuple[float, float]], polygon: list[tuple[float, float]]) -> list[tuple[float, float]]:
    output = subject
    for a, b in zip(polygon, [*polygon[1:], polygon[0]]):
        if not output:
            break
        old, output = output, []
        previous = old[-1]
        dp = _cross(a, b, previous)
        for current in old:
            dc = _cross(a, b, current)
            if (dc >= -EPS) != (dp >= -EPS):
                denominator = dp - dc
                _require(abs(denominator) > 0.0, "unstable clipping intersection")
                t = min(1.0, max(0.0, dp / denominator))
                output.append((previous[0] + t * (current[0] - previous[0]),
                               previous[1] + t * (current[1] - previous[1])))
            if dc >= -EPS:
                output.append(current)
            previous, dp = current, dc
        cleaned = []
        for point in output:
            if not cleaned or math.dist(point, cleaned[-1]) > EPS:
                cleaned.append(point)
        if len(cleaned) > 1 and math.dist(cleaned[0], cleaned[-1]) <= EPS:
            cleaned.pop()
        output = cleaned
    return output


def _numbers(node: Any) -> list[float]:
    values = list(map(float, (node.text or "").split()))
    _require(len(values) == int(node.get("count", "-1")), "array count differs")
    _require(all(math.isfinite(value) for value in values), "array contains nonfinite coordinates")
    return values


def _floats(node: Any, values: Sequence[float]) -> None:
    partition._set_tokens(node, [experiment._format_float32(value) for value in values])


def trim_source(source: Any, polygon_xy: Sequence[Any]) -> dict[str, Any]:
    """Intersect every source triangle with a convex polygon in original XY."""
    _require(source.tag == "CArtMeshSource", "source must be a CArtMeshSource")
    polygon = _polygon(polygon_xy)
    direct = lambda tag, name: partition._direct(source, tag, name, "trim source")
    positions_node = direct("float-array", "positions")
    uvs_node = direct("float-array", "uvs")
    indices_node = direct("int-array", "indices")
    originals = _numbers(positions_node)
    uvs = _numbers(uvs_node)
    _require(len(originals) % 2 == 0 and len(uvs) == len(originals), "source/UV array sizes differ")
    vertex_count = len(originals) // 2
    old_indices = [int(value) for value in partition._tokens(indices_node, "trim indices")]
    _require(len(old_indices) % 3 == 0 and all(0 <= i < vertex_count for i in old_indices), "malformed triangle indices")
    forms = direct("carray_list", "keyforms")
    form_nodes = [partition._direct(form, "float-array", "positions", "trim keyform") for form in forms]
    form_values = [_numbers(node) for node in form_nodes]
    _require(form_nodes and all(len(values) == len(originals) for values in form_values), "keyform arrays differ")
    editable = partition._descendant(source, "GEditableMesh2", "editableMesh", "trim source")
    editable_point = partition._direct(editable, "float-array", "point", "trim editable")
    editable_values = _numbers(editable_point)
    _require(len(editable_values) == len(originals), "editable points differ")
    # Keep all arrays together so each new point uses exactly one mapping.
    source_arrays = [originals, uvs, *form_values, editable_values]
    new_arrays: list[list[float]] = [[] for _ in source_arrays]
    vertex_map: dict[tuple[Any, ...], int] = {}
    indices: list[int] = []
    dropped, retained, clipped_count, slivers = 0, 0, 0, 0
    old_area, new_area = 0.0, 0.0

    def add_vertex(point: tuple[float, float], tri: list[int], triangle: list[tuple[float, float]], denominator: float) -> int:
        weights = [_cross(triangle[1], triangle[2], point) / denominator,
                   _cross(triangle[2], triangle[0], point) / denominator,
                   _cross(triangle[0], triangle[1], point) / denominator]
        _require(all(-1e-7 <= weight <= 1.0 + 1e-7 for weight in weights), "intersection escaped its source triangle")
        weights = [0.0 if abs(weight) < 1e-10 else min(1.0, max(0.0, weight)) for weight in weights]
        total = sum(weights)
        weights = [weight / total for weight in weights]
        # A shared source edge has the same sparse barycentric identity on
        # both incident triangles; preserve UV seams on distinct vertices.
        identity = tuple(sorted((old_index, round(weight, 10)) for old_index, weight in zip(tri, weights) if weight > 0))
        if identity not in vertex_map:
            vertex_map[identity] = len(new_arrays[0]) // 2
            for old, new in zip(source_arrays, new_arrays):
                new.extend(sum(weight * old[2 * old_index + axis] for old_index, weight in zip(tri, weights)) for axis in (0, 1))
        return vertex_map[identity]

    for offset in range(0, len(old_indices), 3):
        tri = old_indices[offset:offset + 3]
        triangle = [(originals[2 * i], originals[2 * i + 1]) for i in tri]
        denominator = _cross(*triangle)
        old_area += abs(denominator) * 0.5
        if abs(denominator) <= EPS:
            dropped += 1
            continue
        result = _clip(triangle, polygon)
        if len(result) < 3 or abs(_area(result)) <= EPS:
            dropped += 1
            continue
        if _area(result) * denominator < 0:
            result.reverse()
        retained += 1
        if abs(abs(_area(result)) - abs(denominator) * 0.5) > 1e-7:
            clipped_count += 1
        vertex_ids = [add_vertex(point, tri, triangle, denominator) for point in result]
        for index in range(1, len(result) - 1):
            area2 = _cross(result[0], result[index], result[index + 1])
            if abs(area2) <= EPS:
                slivers += 1
                continue
            _require(area2 * denominator > 0.0, "trim inverted triangle winding")
            indices.extend((vertex_ids[0], vertex_ids[index], vertex_ids[index + 1]))
            new_area += abs(area2) * 0.5
    _require(indices, "trim removes every triangle; source was not modified")
    used = sorted(set(indices))
    remap = {old: new for new, old in enumerate(used)}
    indices = [remap[index] for index in indices]
    new_arrays = [[value for index in used for value in values[2 * index:2 * index + 2]] for values in new_arrays]
    _require(len(used) < 32768, "trim exceeds signed-short editable edge index range")
    edges = sorted({tuple(sorted((a, b))) for offset in range(0, len(indices), 3)
                    for a, b in ((indices[offset], indices[offset + 1]), (indices[offset + 1], indices[offset + 2]), (indices[offset + 2], indices[offset]))})
    # All validation above precedes mutation. The remaining operations only
    # replace mesh arrays, leaving texture, GUIDs, clipping and bindings intact.
    array_nodes = [positions_node, uvs_node, *form_nodes, editable_point]
    for node, values in zip(array_nodes, new_arrays):
        _floats(node, values)
    partition._set_tokens(indices_node, indices)
    editable.set("nextPointUid", str(len(used)))
    for tag, name, values in (
        ("byte-array", "pointPriority", [10] * len(used)),
        ("short-array", "edge", [value for edge in edges for value in edge]),
        ("byte-array", "edgePriority", [30] * len(edges)),
        ("int-array", "pointUid", range(len(used))),
    ):
        partition._set_tokens(partition._direct(editable, tag, name, "trim editable"), values)
    return {"method": "convex_sutherland_hodgman_barycentric", "polygon_xy": polygon,
            "source_vertex_count": vertex_count, "vertex_count": len(used),
            "source_triangle_count": len(old_indices) // 3, "triangle_count": len(indices) // 3,
            "source_triangles_retained": retained, "source_triangles_dropped": dropped,
            "source_triangles_clipped": clipped_count, "zero_area_fan_triangles_skipped": slivers,
            "source_area_px2": old_area, "trimmed_area_px2": new_area,
            "keyform_count": len(form_nodes), "edge_count": len(edges),
            "texture_pixels_unchanged": True}
