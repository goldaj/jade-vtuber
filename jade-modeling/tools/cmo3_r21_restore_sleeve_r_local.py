#!/usr/bin/env python3
"""Restore r21 right sleeve's mis-parented local coordinates, copy-on-write.

Only the single unbound sleeve keyform positions are changed. Its intact
original ArtMesh canvas and texture are corroborated against healthy v5.
The actual neutral rotation pivot is evaluated through the current hierarchy,
then independently corroborated by all three intact right-arm meshes.
No raster, UV, topology, hierarchy, facial source or visibility is changed.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import cmo3_reparent_preserve_canvas as canvas
import cmo3_safe_roundtrip as safe
from cmo3_r21_restore_eye_r_finite import (
    V5_SHA, exclusive, model_from_bytes, nonfinite_objects, raw_source, require, sha,
)

TARGET = "JAD_R21_DRESS_SLEEVE_R"
TARGET_UUID = "6d91301e-9fc4-4f11-a7f9-4f5dac7cbd9c"
PARENT_UUID = "476cf56a-82e2-4542-96de-ddae867f1546"
WITNESSES = ("JAD_R21_ARM_R_UPPER", "JAD_R21_ARM_R_FOREARM", "JAD_R21_HAND_R")
TOLERANCE = 0.001


def one(model: Any, name: str) -> Any:
    matches = [item for item in model.objects if item.name == name]
    require(len(matches) == 1, name + ": identity is not unique")
    return matches[0]


def direct(node: Any, tag: str, name: str) -> Any:
    return canvas._one_direct_named(node, tag, name)


def actual_neutral_transform(model: Any, guid_ref: str) -> Any:
    """Evaluate current one-form chain, not stale original-shape extensions.

The accepted r21 body grids are axis-aligned affine grids. The existing
bilinear evaluator is exact for these, independent of Cubism interpolation.
Rotation use is limited to neutral, unreflected, unit-scale forms.
"""
    item = model.by_guid_ref.get(guid_ref)
    if item is None:
        return model.transform(guid_ref)
    source = model.source(item)
    forms = direct(source, "carray_list", "keyforms")
    require(len(forms) == 1, item.name + ": must have one neutral form")
    link = canvas._one_named(source, "KeyformGridSource", "keyformGridSource")
    grid = model.ids.get(link.get("xs.ref"), link)
    require(len(direct(grid, "array_list", "keyformBindings")) == 0,
            item.name + ": neutral chain must be unbound")
    parent = actual_neutral_transform(model, item.parent_ref)
    if item.object_type == "rotation-deformer":
        form = forms[0]
        require(float(form.get("angle", "nan")) == 0 and float(form.get("scale", "nan")) == 1
                and form.get("isReflectX") == "false" and form.get("isReflectY") == "false",
                item.name + ": rotation must be neutral identity")
        pivot = model.forward_many(parent, (float(form.get("originX")), float(form.get("originY"))))
        return canvas.RotationTransform(guid_ref, item.name, pivot[0], pivot[1])
    require(item.object_type == "warp-deformer", item.name + ": unsupported parent")
    _, local = model.keyform_positions(item, require_single_unbound=True)
    cols, rows = int(direct(source, "i", "col").text), int(direct(source, "i", "row").text)
    require(len(local) == (cols + 1) * (rows + 1) * 2, item.name + ": invalid grid size")
    x0, y0, x1, y1 = local[0], local[1], local[cols * 2], local[-1]
    affine = tuple(v for row in range(rows + 1) for col in range(cols + 1)
                   for v in (x0 + (x1 - x0) * col / cols, y0 + (y1 - y0) * row / rows))
    require(canvas._maximum_error(local, affine) < TOLERANCE,
            item.name + ": chain grid is not affine; cannot safely infer interpolation")
    return canvas.WarpTransform(guid_ref, item.name, cols, rows, local, 0, 0.0, parent)


def texture_bytes(data: bytes, model: Any, item: Any) -> bytes:
    archive, _, _, _, _ = safe._validate_surgical_layout(data)
    texture_link = direct(model.source(item), "GTexture2D", "texture")
    texture = model.ids[texture_link.get("xs.ref")]
    resource_link = direct(texture, "CImageResource", "srcImageResource")
    resource = model.ids[resource_link.get("xs.ref")]
    files = [n for n in resource.iter("file") if n.get("xs.n") == "imageFileBuf"]
    require(len(files) == 1, "ambiguous sleeve embedded raster")
    return archive.read_unique_path(files[0].get("path"), 20_000_000)


def plan(source: Path, reference: Path) -> tuple[bytes, dict[str, Any]]:
    require("r21" in source.name.lower(), "source must be an r21 checkpoint")
    source_data, reference_data = source.read_bytes(), reference.read_bytes()
    require(sha(reference_data) == V5_SHA, "healthy v5 reference SHA differs")
    before, main = model_from_bytes(source_data)
    healthy, _ = model_from_bytes(reference_data)
    require(not nonfinite_objects(before), "source has invalid coordinates; use repaired v22 or later")
    target, old_target = one(before, TARGET), one(healthy, TARGET)
    require(target.guid_uuid == old_target.guid_uuid == TARGET_UUID, "sleeve identity differs")
    require(target.parent_uuid == PARENT_UUID, "sleeve is not under the expected right-arm root")
    _, local = before.keyform_positions(target, require_single_unbound=True)
    original = before.original_canvas(target)
    require(len(local) == len(original) == 302, "sleeve point count differs")
    require(all(0 < value < 1 for value in local), "expected faulty normalized sleeve coordinates")
    require(canvas._maximum_error(original, healthy.original_canvas(old_target)) == 0,
            "sleeve original canvas differs from healthy v5")
    require(texture_bytes(source_data, before, target) == texture_bytes(reference_data, healthy, old_target),
            "sleeve texture differs from healthy v5")
    for field, tag in (("uvs", "float-array"), ("indices", "int-array")):
        require(direct(before.source(target), tag, field).text == direct(healthy.source(old_target), tag, field).text,
                "sleeve " + field + " differs from healthy v5")
    transform = actual_neutral_transform(before, target.parent_ref)
    require(isinstance(transform, canvas.RotationTransform), "expected neutral rotation transform")
    witness_errors = {}
    for name in WITNESSES:
        item, healthy_item = one(before, name), one(healthy, name)
        require(item.parent_uuid == PARENT_UUID, name + ": parent differs")
        immutable = before.original_canvas(item)
        require(canvas._maximum_error(immutable, healthy.original_canvas(healthy_item)) == 0,
                name + ": witness canvas differs from v5")
        _, positions = before.keyform_positions(item, require_single_unbound=True)
        error = canvas._maximum_error(before.forward_many(transform, positions), immutable)
        require(error < TOLERANCE, name + ": does not corroborate actual parent pivot")
        witness_errors[name] = error
    new_local = tuple(canvas._float32(value) for value in before.inverse_many(transform, original))
    require(all(math.isfinite(value) for value in new_local), "new local coordinates invalid")
    current, patch = canvas._patch_keyform_positions(main, target=target, old_values=local, new_values=new_local)
    after = canvas.GeometryModel(current, TOLERANCE)
    require(before.objects == after.objects, "object identity or hierarchy changed")
    require(not nonfinite_objects(after), "invalid coordinates introduced")
    changed = [item.name for item in before.objects if raw_source(main, item) != raw_source(current, item)]
    require(changed == [TARGET], "an unrelated object source changed")
    reconstructed = after.forward_many(transform, after.keyform_positions(one(after, TARGET), require_single_unbound=True)[1])
    error = canvas._maximum_error(reconstructed, original)
    require(error < TOLERANCE, "restored sleeve canvas differs from v5")
    output = safe._replace_main_xml(source_data, current)
    archive_before, _, _, _, _ = safe._validate_surgical_layout(source_data)
    archive_after, _, _, _, decoded = safe._validate_surgical_layout(output)
    require(decoded == current, "encoded main.xml differs")
    preserved = safe._compare_entry_preservation(source_data, archive_before, output, archive_after, main_may_change=True)
    require(preserved.get("all_non_main_entries_byte_identical") is True, "non-main member changed")
    require(source.read_bytes() == source_data and reference.read_bytes() == reference_data, "source/reference changed")
    return output, {
        "schema": "jade.r21.restore-sleeve-r-local.v1", "status": "candidate_requires_cubism_load_save",
        "source": str(source), "source_sha256": sha(source_data),
        "reference": str(reference), "reference_sha256": sha(reference_data),
        "output_sha256": sha(output), "changed_objects": changed,
        "reason": "Warp-normalized positions were retained after parenting sleeve to arm rotation",
        "parent_actual_canvas_pivot": [transform.pivot_x, transform.pivot_y],
        "parent_pivot_witness_errors_px": witness_errors,
        "before_canvas_bounds": canvas._bounds(before.forward_many(transform, local)),
        "after_canvas_bounds": canvas._bounds(reconstructed), "max_canvas_error_px": error,
        "healthy_v5_original_texture_uv_topology_verified": True,
        "all_unrelated_sources_byte_identical": True, "archive": preserved, "patch": patch,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    source, reference = args.source.resolve(strict=True), args.reference.resolve(strict=True)
    if not args.dry_run:
        require(args.output is not None and args.audit is not None, "--output and --audit required")
        require("TEST" in args.output.name and args.output.suffix.lower() == ".cmo3", "output must be TEST CMO3")
        require(not args.output.exists() and not args.audit.exists(), "refusing to overwrite output/audit")
        require(args.output.resolve() != source, "output must differ from source")
    data, audit = plan(source, reference)
    if not args.dry_run:
        audit["output"] = str(args.output.resolve())
        exclusive(args.output, data)
        exclusive(args.audit, (json.dumps(audit, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
