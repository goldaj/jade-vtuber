#!/usr/bin/env python3
"""Attach r21 CLOSED eye roots and MOUTH_OPEN to Head Z without moving artwork.

The three one-form unbound warps must start at ROOT. Only their parent fields
and local positions may change. Descendant canvas positions are independently
checked. No old-model geometry, keyforms or identifiers are imported.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from typing import Any
import cmo3_create_deformer_experiment as experiment
import cmo3_reparent_preserve_canvas as canvas
import cmo3_safe_roundtrip as safe
from cmo3_r21_restore_eye_r_finite import require, sha, model_from_bytes, nonfinite_objects, raw_source, exclusive

ROOTS = {
    "D_JAD_EYE_L_CLOSED": {"JAD_R21_EYE_L_CLOSED_TRUE"},
    "D_JAD_EYE_R_CLOSED": {"JAD_R21_EYE_R_CLOSED_TRUE"},
    "D_JAD_MOUTH_OPEN": {"JAD_R21_MOUTH_OPEN_OUTLINE", "JAD_R21_MOUTH_OPEN_TEETH_UPPER", "JAD_R21_MOUTH_OPEN_TONGUE", "JAD_R21_MOUTH_OPEN_INTERIOR"},
}
TOLERANCE = 0.001


def one(model: Any, name: str, kind: str = "warp-deformer") -> Any:
    matches = [i for i in model.objects if i.name == name and i.object_type == kind]
    require(len(matches) == 1, name + ": identity missing or ambiguous")
    return matches[0]


def canvas_positions(model: Any, item: Any) -> tuple[float, ...]:
    _, values = model.keyform_positions(item, require_single_unbound=True)
    return model.forward_many(model.transform(item.parent_ref), values)


def plan(source: Path) -> tuple[bytes, dict[str, Any]]:
    require("r21" in source.name.lower(), "source must be r21")
    version = re.search(r"_v(\d+)\.cmo3$", source.name)
    require(version is not None and int(version.group(1)) >= 22, "source must be native v22 or later")
    data = source.read_bytes()
    before, main = model_from_bytes(data)
    require(not nonfinite_objects(before), "source has nonfinite coordinates; repair eye R first")
    head = one(before, "R_JAD_HEAD_Z", "rotation-deformer")
    require(head.guid_uuid == "ca0c2616-17ad-4639-84d1-7e69fb3825b7", "Head Z identity differs")
    tracked = {}
    for name, child_names in ROOTS.items():
        root = one(before, name)
        require(root.parent_ref not in before.by_guid_ref and root.parent_note == "ROOT", name + ": expected top-level ROOT")
        children = [i for i in before.objects if i.parent_uuid == root.guid_uuid]
        require({i.name for i in children} == child_names, name + ": direct children differ")
        for item in [root, *children]:
            tracked[item.name] = canvas_positions(before, item)
    current = main
    changes = []
    for name in ROOTS:
        model = canvas.GeometryModel(current, TOLERANCE)
        root = one(model, name)
        current_head = one(model, "R_JAD_HEAD_Z", "rotation-deformer")
        _, old_local = model.keyform_positions(root, require_single_unbound=True)
        parent_transform = model.transform(current_head.guid_ref)
        local = tuple(canvas._float32(v) for v in model.inverse_many(parent_transform, tracked[name]))
        error = canvas._maximum_error(model.forward_many(parent_transform, local), tracked[name])
        require(error <= TOLERANCE, name + ": canvas compensation error")
        current, _ = canvas._patch_keyform_positions(current, target=root, old_values=old_local, new_values=local)
        current, _ = safe._patch_parent_ref_for_record(current, target=root, expected_old_ref=root.parent_ref, new_parent=current_head)
        changes.append({"name": name, "old_parent": "ROOT", "new_parent": current_head.name, "max_canvas_error_px": error})
    after = canvas.GeometryModel(current, TOLERANCE)
    require(not nonfinite_objects(after), "nonfinite coordinates introduced")
    require(len(before.objects) == len(after.objects), "object count changed")
    errors = {}
    for name, expected in tracked.items():
        item = one(after, name, "warp-deformer" if name in ROOTS else "art-mesh")
        errors[name] = canvas._maximum_error(canvas_positions(after, item), expected)
        require(errors[name] <= TOLERANCE, name + ": final descendant canvas proof failed")
    changed = {i.name for i in before.objects if raw_source(main, i) != raw_source(current, i)}
    require(changed == set(ROOTS), "unrelated object source changed")
    for item in after.objects:
        old = next(i for i in before.objects if i.guid_uuid == item.guid_uuid)
        if item.name not in ROOTS:
            require(item == old, item.name + ": unrelated object identity changed")
        else:
            require(item.parent_uuid == head.guid_uuid, item.name + ": wrong final parent")
    output = safe._replace_main_xml(data, current)
    before_archive, _, _, _, _ = safe._validate_surgical_layout(data)
    after_archive, _, _, _, decoded = safe._validate_surgical_layout(output)
    require(decoded == current, "encoded XML differs")
    preservation = safe._compare_entry_preservation(data, before_archive, output, after_archive, main_may_change=True)
    require(preservation.get("all_non_main_entries_byte_identical") is True, "non-main archive entry changed")
    require(source.read_bytes() == data, "source changed during planning")
    return output, {"schema": "jade.r21.face-roots-to-head.v1", "status": "candidate_requires_cubism_load_save", "source": str(source), "source_sha256": sha(data), "output_sha256": sha(output), "changes": changes, "descendant_canvas_errors_px": errors, "after_nonfinite": [], "all_unrelated_sources_byte_identical": True, "archive": preservation}


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
        require(not args.output.exists() and not args.audit.exists(), "output/audit exists; refusing overwrite")
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
