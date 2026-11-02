#!/usr/bin/env python3
"""Add a first expressive r21 MouthForm x MouthOpenY grid, copy-on-write.

The 4 rectangular OPEN ArtMeshes are uniformly subdivided inside their
existing triangles. Every old corner, UV and six OpenY pose surfaces is
preserved at Form=0 by barycentric interpolation; no texture is modified.
The true painted neutral keeps its original 12-point topology and all six
Form=0 forms byte-exact. Smile/frown are coherent canvas-space curvature
fields applied to all five meshes, with existing handoff opacities unchanged.
"""
from __future__ import annotations

import argparse
import collections
import itertools
import json
import math
import re
from pathlib import Path
from typing import Any

import cmo3_create_deformer_experiment as experiment
import cmo3_eye_closure_professional as eye
import cmo3_face_fx_scaffold as face
import cmo3_reparent_preserve_canvas as canvas
import cmo3_safe_roundtrip as safe
import cmo3_secondary_professional as secondary
import cmo3_r21_mouth_open_first_rig as mouth
from cmo3_r21_restore_eye_r_finite import require, sha, model_from_bytes, nonfinite_objects, raw_source, exclusive

FORM_KEYS = (-1.0, 0.0, 1.0)
SUBDIVISIONS = 6
TOLERANCE = 0.001


class MouthNeutralModel(mouth.CurrentNeutralModel):
    """Allow small mouth poses beyond an affine parent grid's neutral border.

    The stock inverse intentionally only searches cells inside [0,1]. A smile
    can extend a few pixels beyond this imported tight grid. Solve the affine
    mapping exactly, only after proving every grid point follows that mapping.
    Forward evaluation is still the existing bilinear evaluator.
    """
    def _inverse_warp_cell(self, transform, point):
        if transform.name != "D_JAD_MOUTH_OPEN":
            return super()._inverse_warp_cell(transform, point)
        p00 = self._grid_point(transform, 0, 0)
        p10 = self._grid_point(transform, transform.columns, 0)
        p01 = self._grid_point(transform, 0, transform.rows)
        ax, ay = p10[0]-p00[0], p10[1]-p00[1]
        bx, by = p01[0]-p00[0], p01[1]-p00[1]
        for row in range(transform.rows+1):
            for column in range(transform.columns+1):
                u, v = column/transform.columns, row/transform.rows
                observed = self._grid_point(transform, column, row)
                require(math.hypot(observed[0]-p00[0]-u*ax-v*bx,
                                   observed[1]-p00[1]-u*ay-v*by) < 0.001,
                        "Mouth grid is not affine; cannot extrapolate safely")
        det = ax*by-ay*bx
        require(abs(det)>1e-8, "Degenerate mouth parent")
        dx, dy = point[0]-p00[0], point[1]-p00[1]
        u, v = (dx*by-dy*bx)/det, (ax*dy-ay*dx)/det
        require(-.2<u<1.2 and -.2<v<1.2, "Mouth pose exceeds small grid extension")
        return 0.0, u, v


def numbers(node: Any, cast=float) -> tuple:
    values = tuple(cast(token) for token in (node.text or "").split())
    require(len(values) == int(node.get("count")), "array count differs")
    return values


def direct(node: Any, tag: str, name: str) -> Any:
    return canvas._one_direct_named(node, tag, name)


def subdivide(indices: tuple[int, ...], count: int = SUBDIVISIONS) -> tuple[list[tuple[int, ...]], tuple[int, ...]]:
    """Refine triangles without changing their original shared diagonal."""
    require(len(indices) == 6 and set(indices) == set(range(4)), "OPEN must have original 4 vertices / 2 triangles")
    weights = [tuple(count if j == i else 0 for j in range(4)) for i in range(4)]
    lookup = {weight: index for index, weight in enumerate(weights)}
    triangles = []
    for off in (0, 3):
        first, second, third = indices[off:off + 3]
        grid = {}
        for i in range(count + 1):
            for j in range(count + 1 - i):
                weight = [0] * 4
                weight[first], weight[second], weight[third] = count - i - j, i, j
                key = tuple(weight)
                if key not in lookup:
                    lookup[key] = len(weights)
                    weights.append(key)
                grid[i, j] = lookup[key]
        for i in range(count):
            for j in range(count - i):
                triangles.extend((grid[i, j], grid[i + 1, j], grid[i, j + 1]))
                if i + j < count - 1:
                    triangles.extend((grid[i + 1, j], grid[i + 1, j + 1], grid[i, j + 1]))
    require(len(weights) == (count + 1) ** 2 and len(triangles) == 6 * count ** 2,
            "subdivision is incomplete")
    return weights, tuple(triangles)


def interpolate(values: tuple[float, ...], weights: list[tuple[int, ...]]) -> tuple[float, ...]:
    require(len(values) == 8, "expected four source points")
    return tuple(canvas._float32(sum(weight[i] * values[2 * i + axis] for i in range(4)) / SUBDIVISIONS)
                 for weight in weights for axis in (0, 1))


def expression(points: tuple[float, ...], form: float, opening: float) -> tuple[float, ...]:
    """Down-positive canvas, 110px mouth width; softer bend at fully open."""
    if form == 0:
        return points
    width = 1 + 0.04 * form
    bend_scale = 1 - 0.25 * opening
    output = []
    for x, y in zip(points[::2], points[1::2]):
        dx = x - 1921.0
        q = (dx / 55.0) ** 2
        shift = (1.0 - 4.5 * q) * form if form > 0 else (-3.0 + 13.0 * q) * (-form)
        output.extend((1921.0 + dx * width, y + bend_scale * shift))
    return tuple(output)


def replace_array(raw: bytes, tag: str, name: str, values: tuple, integer=False) -> bytes:
    pattern = re.compile(rb"<" + tag.encode() + rb'\b(?=[^>]*\bxs\.n="' + name.encode() + rb'")[^>]*>[^<]*</' + tag.encode() + rb">", re.S)
    found = list(pattern.finditer(raw))
    require(len(found) == 1, name + ": raw array missing or ambiguous")
    tokens = " ".join(str(int(value)) if integer else canvas._format_float32(value) for value in values)
    value = f'<{tag} xs.n="{name}" count="{len(values)}">{tokens}</{tag}>'.encode("ascii")
    match = found[0]
    return raw[:match.start()] + value + raw[match.end():]


def refine_source(raw: bytes, original: tuple, uvs: tuple, indices: tuple) -> bytes:
    """Keep Cubism editable and runtime mesh definitions in agreement."""
    count = len(original) // 2
    pattern = re.compile(rb"<GEditableMesh2\b[^>]*>.*?</GEditableMesh2>", re.S)
    matches = list(pattern.finditer(raw))
    require(len(matches) == 1, "editable mesh missing or ambiguous")
    em = matches[0].group(0)
    em, changed = re.subn(rb'nextPointUid="\d+"', f'nextPointUid="{count}"'.encode(), em)
    require(changed == 1, "editable point uid missing")
    edges = collections.Counter(tuple(sorted((triangle[a], triangle[b])))
                                for off in range(0, len(indices), 3)
                                for triangle in (indices[off:off + 3],)
                                for a, b in ((0, 1), (1, 2), (2, 0)))
    ordered_edges = sorted(edges)
    em = replace_array(em, "float-array", "point", original)
    em = replace_array(em, "byte-array", "pointPriority", tuple(20 if i < 4 else 10 for i in range(count)), True)
    em = replace_array(em, "short-array", "edge", tuple(i for edge in ordered_edges for i in edge), True)
    em = replace_array(em, "byte-array", "edgePriority", tuple(30 if edges[edge] == 1 else 10 for edge in ordered_edges), True)
    em = replace_array(em, "int-array", "pointUid", tuple(range(count)), True)
    match = matches[0]
    current = raw[:match.start()] + em + raw[match.end():]
    current = replace_array(current, "int-array", "indices", indices, True)
    forms, _ = secondary._keyforms(current, b"CArtMeshForm")
    tail = current[forms.end():]
    tail = replace_array(tail, "float-array", "positions", original)
    tail = replace_array(tail, "float-array", "uvs", uvs)
    return current[:forms.end()] + tail


def areas(points: tuple, indices: tuple) -> tuple[float, ...]:
    result = []
    for off in range(0, len(indices), 3):
        a, b, c = indices[off:off + 3]
        ax, ay, bx, by, cx, cy = (*points[2 * a:2 * a + 2], *points[2 * b:2 * b + 2], *points[2 * c:2 * c + 2])
        result.append(((bx - ax) * (cy - ay) - (by - ay) * (cx - ax)) / 2)
    return tuple(result)


def sampled_triangle_gate(pose_map: dict, indices: tuple) -> dict:
    min_area, tested = float("inf"), 0
    for fi in range(2):
        for oi in range(5):
            for fs in range(11):
                for os in range(11):
                    f, o = fs / 10, os / 10
                    corners = [pose_map[fi, oi], pose_map[fi + 1, oi], pose_map[fi, oi + 1], pose_map[fi + 1, oi + 1]]
                    points = tuple((1 - f) * (1 - o) * a + f * (1 - o) * b + (1 - f) * o * c + f * o * d
                                   for a, b, c, d in zip(*corners))
                    values = areas(points, indices)
                    require(all(value > 1e-6 for value in values), "triangle inversion/degeneracy in interpolated expression grid")
                    min_area = min(min_area, min(values))
                    tested += len(values)
    return {"interpolated_poses": 1210, "triangles_tested": tested, "min_area_px2": min_area, "inverted_or_degenerate": 0}


def plan(source: Path) -> tuple[bytes, dict[str, Any]]:
    require("r21" in source.name.lower(), "source must be r21")
    data = source.read_bytes()
    _, xml = model_from_bytes(data)
    before = MouthNeutralModel(xml, TOLERANCE)
    require(not nonfinite_objects(before), "source has nonfinite positions")
    form_parameter = eye._parameter_ref(before.root, "ParamMouthForm")
    roles = [role for name in mouth.BOUND for role in (name + ":mouthform-binding",
             *(f"{name}:mouthform:{fi}:{oi}" for fi in (0, 2) for oi in range(6)))]
    slots = secondary._allocate(before.root, roles)
    current, shared, records, expected_baselines = xml, [], [], {}
    for name in mouth.BOUND:
        item = mouth.one(before, name, "art-mesh")
        semantic = eye._generic_grid_semantics(before.root, before, item, experiment)
        require(semantic["notes"] == ["ParamMouthOpenY"] and tuple(semantic["keys"][0]) == mouth.KEYS,
                name + ": expected unextended six-key OpenY grid")
        require(set(semantic["access_to_ref"]) == {(i,) for i in range(6)}, name + ": incomplete OpenY grid")
        raw = raw_source(xml, item)
        source_node = before.source(item)
        _, raw_forms = secondary._keyforms(raw, b"CArtMeshForm")
        raw_by_ref = {secondary._form_ref(form): form for form in raw_forms}
        nodes_by_ref = {experiment._one_named(form, "CFormGuid", "guid").get("xs.ref"): form
                        for form in direct(source_node, "carray_list", "keyforms")}
        ordered_refs = [semantic["access_to_ref"][i,] for i in range(6)]
        old_indices = numbers(direct(source_node, "int-array", "indices"), int)
        original = before.original_canvas(item)
        uvs = numbers(direct(source_node, "float-array", "uvs"))
        is_open = name in mouth.OPEN
        if is_open:
            weights, indices = subdivide(old_indices)
            refined_original, refined_uvs = interpolate(original, weights), interpolate(uvs, weights)
            changed = refine_source(raw, refined_original, refined_uvs, indices)
        else:
            weights, indices, refined_original = None, old_indices, original
            changed = raw
        parent = before.transform(item.parent_ref)
        baseline_local, baseline_global, baseline_forms = {}, {}, {}
        max_baseline_error = 0.0
        for oi, ref in enumerate(ordered_refs):
            old_local = numbers(experiment._one_named(nodes_by_ref[ref], "float-array", "positions"))
            local = interpolate(old_local, weights) if is_open else old_local
            baseline_local[oi] = local
            baseline_global[oi] = before.forward_many(parent, local)
            baseline_forms[oi] = secondary._clone_form(raw_by_ref[ref], new_ref=ref, opacity=None, positions=local,
                                      multiply=None, face=face, experiment=experiment) if is_open else raw_by_ref[ref]
            if is_open:
                # Barycentric subdivision of the existing posed triangle, not
                # re-evaluation of the old nonlinear opening() formula.
                old_global = before.forward_many(parent, old_local)
                max_baseline_error = max(max_baseline_error, canvas._maximum_error(baseline_global[oi], interpolate(old_global, weights)))
                require(local[:8] == tuple(canvas._float32(v) for v in old_local), name + ": original float32 corner coordinates changed")
            expected_baselines[name, oi] = baseline_forms[oi]
        require(max_baseline_error < TOLERANCE, name + ": baseline subdivision changed canvas mapping")
        all_forms, form_refs, access, poses = [], [], [], {}
        binding_ref, binding_idx = slots[name + ":mouthform-binding"]
        max_pose_error = 0.0
        for fi, form_key in enumerate(FORM_KEYS):
            for oi, open_key in enumerate(mouth.KEYS):
                ref = ordered_refs[oi]
                if fi == 1:
                    output_form = baseline_forms[oi]
                    points = baseline_global[oi]
                else:
                    role = f"{name}:mouthform:{fi}:{oi}"
                    ref, idx = slots[role]
                    points = expression(baseline_global[oi], form_key, open_key)
                    local = tuple(canvas._float32(v) for v in before.inverse_many(parent, points))
                    observed = before.forward_many(parent, local)
                    max_pose_error = max(max_pose_error, canvas._maximum_error(observed, points))
                    points = observed
                    output_form = secondary._clone_form(baseline_forms[oi], new_ref=ref, opacity=None, positions=local,
                                      multiply=None, face=face, experiment=experiment)
                    shared.append(secondary._form_guid_block(ref, idx, sha(data), role))
                poses[fi, oi] = points
                all_forms.append(output_form)
                form_refs.append(ref)
                access.append((oi, fi))
        require(max_pose_error < TOLERANCE, name + ": expression canvas error exceeds tolerance")
        gate = sampled_triangle_gate(poses, indices)
        forms_match, _ = secondary._keyforms(changed, b"CArtMeshForm")
        changed = secondary._replace_keyforms(changed, forms_match, all_forms)
        current = experiment._replace_exact(current, raw, changed, 1, "MouthForm " + name)
        old_grid = experiment._block_by_id(current, "KeyformGridSource", semantic["grid_ref"])
        new_grid = secondary._grid_block(grid_ref=semantic["grid_ref"], grid_idx=semantic["grid_idx"],
                    binding_refs=[semantic["binding_refs"][0], binding_ref], accesses=access, form_refs=form_refs)
        current = experiment._replace_exact(current, old_grid, new_grid, 1, "MouthForm grid " + name)
        shared.append(eye._new_binding_block(grid_ref=semantic["grid_ref"], binding_ref=binding_ref, binding_idx=binding_idx,
                                            parameter_ref=form_parameter, keys=FORM_KEYS))
        records.append({"name": name, "vertices_before": len(original) // 2, "vertices_after": len(refined_original) // 2,
                        "triangles_before": len(old_indices) // 3, "triangles_after": len(indices) // 3,
                        "form0_original_corners_and_opacity_unchanged": True,
                        "form0_neutral_forms_byte_exact": not is_open,
                        "max_form0_subdivision_error_px": max_baseline_error,
                        "max_expression_canvas_error_px": max_pose_error, "triangle_gate": gate})
    current = experiment._append_shared_blocks(current, shared)
    current = mouth.binding_imports(current)
    after = MouthNeutralModel(current, TOLERANCE)
    require(not nonfinite_objects(after), "nonfinite positions introduced")
    require(before.objects == after.objects, "hierarchy or object identity changed")
    changed_names = {i.name for i in before.objects if raw_source(xml, i) != raw_source(current, i)}
    require(changed_names == set(mouth.BOUND), "an unrelated object source changed")
    for name in mouth.BOUND:
        item = mouth.one(after, name, "art-mesh")
        semantic = eye._generic_grid_semantics(after.root, after, item, experiment)
        require(semantic["notes"] == ["ParamMouthOpenY", "ParamMouthForm"], name + ": parameter order differs")
        require(tuple(semantic["keys"][0]) == mouth.KEYS and tuple(semantic["keys"][1]) == FORM_KEYS, name + ": key values differ")
        require(set(semantic["access_to_ref"]) == set(itertools.product(range(6), range(3))), name + ": 3x6 grid incomplete")
        _, forms = secondary._keyforms(raw_source(current, item), b"CArtMeshForm")
        by_ref = {secondary._form_ref(form): form for form in forms}
        for oi in range(6):
            require(by_ref[semantic["access_to_ref"][oi, 1]] == expected_baselines[name, oi], name + ": serialized baseline changed")
        count = len(after.original_canvas(item))
        require(count == len(numbers(direct(after.source(item), "float-array", "uvs"))), name + ": UV count differs")
        for form in direct(after.source(item), "carray_list", "keyforms"):
            require(len(numbers(experiment._one_named(form, "float-array", "positions"))) == count, name + ": form size differs")
    output = safe._replace_main_xml(data, current)
    archive_before, _, _, _, _ = safe._validate_surgical_layout(data)
    archive_after, _, _, _, decoded = safe._validate_surgical_layout(output)
    require(decoded == current, "encoded main.xml differs")
    preserved = safe._compare_entry_preservation(data, archive_before, output, archive_after, main_may_change=True)
    require(preserved.get("all_non_main_entries_byte_identical") is True, "raster/non-main archive entry changed")
    require(source.read_bytes() == data, "source changed")
    return output, {"schema": "jade.r21.mouth-form-first-rig.v1", "status": "candidate_requires_native_cubism_visual_gate",
                    "source": str(source), "source_sha256": sha(data), "output_sha256": sha(output),
                    "mouth_form_keys": FORM_KEYS, "mouth_open_keys": mouth.KEYS, "subdivisions": SUBDIVISIONS,
                    "objects": records, "all_unrelated_sources_byte_identical": True,
                    "all_textures_and_non_main_members_byte_identical": True, "archive": preserved,
                    "limitations": ["First expressive smile/frown rig, not phonemes", "Existing v23 handoff and OpenY geometry deliberately preserved", "Native Cubism load/save and visual QA required"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    if not args.dry_run:
        require(args.output is not None and args.audit is not None, "--output and --audit required")
        require("TEST" in args.output.name and args.output.suffix.lower() == ".cmo3", "output must be a TEST CMO3")
        require(not args.output.exists() and not args.audit.exists(), "refusing overwrite")
        require(source != args.output.resolve(), "output must differ from source")
    data, audit = plan(source)
    if not args.dry_run:
        audit["output"] = str(args.output.resolve())
        exclusive(args.output, data)
        exclusive(args.audit, (json.dumps(audit, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
