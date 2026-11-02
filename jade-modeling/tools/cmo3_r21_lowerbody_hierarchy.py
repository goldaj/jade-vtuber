#!/usr/bin/env python3
"""Add a neutral full-/lower-body hierarchy to pinned native Jade r21 v26.

Only five new lower-body ArtMeshes and the two explicitly authorized old
body roots are reparented. Their local keyform coordinates are compensated;
all original canvas arrays, artwork, other object sources and CAFF raster
members survive unchanged. This creates no motion keys or parameter binding.
Native Cubism load/save is still required before calling the result a checkpoint.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
from typing import Any
import uuid
import xml.etree.ElementTree as ET

import cmo3_create_deformer_experiment as ex
import cmo3_reparent_preserve_canvas as canvas
import cmo3_safe_roundtrip as safe
import cmo3_secondary_professional as secondary
from cmo3_r21_face_roots_to_head import one
from cmo3_r21_mouth_open_first_rig import CurrentNeutralModel
from cmo3_r21_restore_eye_r_finite import require, sha, nonfinite_objects, raw_source, exclusive


SOURCE_SHA = "2CCC047A2C2BFBF4B36E88AED394AFA4B707B7DD417EBD746926896B945EFBC1"
TOLERANCE = 0.001
TEMPLATE = "D_JAD_BODY_LOWER"
FULL_ROOT = "D_JAD_FULLBODY_ROOT"
LOWER_ROOT = "D_JAD_LOWERBODY_ROOT"
# Bounds are (left, top, right, bottom), in the existing 3840x5000 canvas.
# 250px global rows include the 2000px pelvis and 4250px foot-lock transition.
WARP_SPECS = (
    (FULL_ROOT, None, (900.0, 0.0, 2920.0, 5000.0), (4, 20)),
    (LOWER_ROOT, FULL_ROOT, (1000.0, 1700.0, 2840.0, 4900.0), (4, 8)),
    ("D_JAD_LOWERBODY_SKIRT", LOWER_ROOT, (1160.0, 1740.0, 2640.0, 3100.0), (4, 8)),
    ("D_JAD_LEG_R", LOWER_ROOT, (1480.0, 2700.0, 1920.0, 4850.0), (4, 8)),
    ("D_JAD_LEG_L", LOWER_ROOT, (1900.0, 2700.0, 2340.0, 4850.0), (4, 8)),
    ("D_JAD_ANKLE_R", "D_JAD_LEG_R", (1600.0, 4150.0, 1900.0, 4850.0), (4, 4)),
    ("D_JAD_ANKLE_L", "D_JAD_LEG_L", (1920.0, 4150.0, 2230.0, 4850.0), (4, 4)),
)
REPARENTS = {
    "D_JAD_BODY_UPPER_XY": ("warp-deformer", FULL_ROOT),
    "D_JAD_BODY_LOWER": ("warp-deformer", FULL_ROOT),
    "JAD_R21_SHORT_SKIRT_V3": ("art-mesh", "D_JAD_LOWERBODY_SKIRT"),
    "JAD_R21_LEG_R_V3": ("art-mesh", "D_JAD_LEG_R"),
    "JAD_R21_LEG_L_V3": ("art-mesh", "D_JAD_LEG_L"),
    "JAD_R21_SHOE_R_V3": ("art-mesh", "D_JAD_ANKLE_R"),
    "JAD_R21_SHOE_L_V3": ("art-mesh", "D_JAD_ANKLE_L"),
}


def _serialized(node: ET.Element) -> bytes:
    node = copy.deepcopy(node)
    node.tail = None
    # Keep native CRLF layout for the existing byte-surgical pose helpers.
    return ET.tostring(node, encoding="utf-8", short_empty_elements=True).replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")


def _array(node: ET.Element, values) -> None:
    values = tuple(values)
    require(all(math.isfinite(v) for v in values), "nonfinite generated grid")
    node.set("count", str(len(values)))
    node.text = " ".join(ex._format_float32(v) for v in values)


def _grid(bounds, divisions) -> tuple[float, ...]:
    left, top, right, bottom = bounds
    columns, rows = divisions
    require(right > left and bottom > top and columns > 0 and rows > 0, "invalid warp bounds")
    return tuple(ex._float32(v) for row in range(rows + 1) for column in range(columns + 1)
                 for v in (left + (right-left)*column/columns, top + (bottom-top)*row/rows))


def _canvas_form_positions(model, item, form) -> tuple[float, ...]:
    points = canvas._float_values(ex._direct_named(form, "float-array", "positions"), item.name)
    return model.forward_many(model.transform(item.parent_ref), points)


def _all_artmesh_world_forms(model) -> dict[str, list[tuple[float, ...]]]:
    return {item.name: [_canvas_form_positions(model, item, form)
                       for form in ex._direct_named(model.source(item), "carray_list", "keyforms")]
            for item in model.objects if item.object_type == "art-mesh"}


def _clone_warp(root, template, name, slots, parent_ref, part_ref, original, local, divisions):
    ids = ex._id_map(root)
    owned = {"source": template.source_ref, "positions": template.positions_ref,
             "form": template.form_ref, "guid": template.guid_ref}
    replacements = {ref: slots[f"lowerbody:{name}:{role}"][0] for role, ref in owned.items()}
    nodes = {}
    for role, old_ref in owned.items():
        ref, idx = slots[f"lowerbody:{name}:{role}"]
        node = copy.deepcopy(ids[old_ref])
        node.set("xs.id", ref)
        node.set("xs.idx", str(idx))
        for child in node.iter():
            old = child.get("xs.ref")
            if old in replacements:
                child.set("xs.ref", replacements[old])
        for index, child in enumerate(n for n in node.iter() if n.get("uuid") is not None):
            child.set("uuid", str(uuid.uuid5(uuid.NAMESPACE_URL, f"jade-r21-v26-lowerbody:{SOURCE_SHA}:{name}:{role}:{index}")))
        nodes[role] = node
    source = nodes["source"]
    ex._one_named(source, "s", "localName").text = name
    ex._one_named(source, "CDeformerId", "id").set("idstr", name)
    ex._one_named(source, "CDeformerGuid", "targetDeformerGuid").set("xs.ref", parent_ref)
    ex._one_named(source, "CPartGuid", "parentGuid").set("xs.ref", part_ref)
    columns, rows = divisions
    for child in source.iter("i"):
        if child.get("xs.n") in ("col", "row"):
            child.text = str(columns if child.get("xs.n") == "col" else rows)
    # Original-shape arrays remain in canvas space; only the form is local.
    _array(nodes["positions"], original)
    forms = ex._direct_named(source, "carray_list", "keyforms")
    require(len(forms) == 1, "template is not neutral one-form")
    _array(ex._direct_named(forms[0], "float-array", "positions"), local)
    nodes["guid"].set("note", name)
    nodes["form"].set("note", name + " neutral")
    return [_serialized(n) for n in nodes.values()], {
        "name": name, "source_ref": replacements[template.source_ref],
        "guid_ref": replacements[template.guid_ref], "guid_uuid": nodes["guid"].get("uuid"),
        "form_ref": replacements[template.form_ref], "original_positions_ref": replacements[template.positions_ref],
        "parent_ref": parent_ref, "part_ref": part_ref, "columns": columns, "rows": rows,
        "vertex_count": (columns+1)*(rows+1), "canvas_positions": list(original), "local_positions": list(local),
    }


def _allowed_source_delta(old, new):
    """Only parent reference and the unique keyform coordinate payload differ."""
    old, new = copy.deepcopy(old), copy.deepcopy(new)
    for source in (old, new):
        ex._one_named(source, "CDeformerGuid", "targetDeformerGuid").set("xs.ref", "#IGNORED")
        forms = ex._direct_named(source, "carray_list", "keyforms")
        require(len(forms) == 1, "reparent target acquired forms")
        ex._direct_named(forms[0], "float-array", "positions").text = "IGNORED"
    return _serialized(old) == _serialized(new)


def plan(source: Path) -> tuple[bytes, dict[str, Any]]:
    """Return verified candidate CAFF bytes and JSON-compatible audit; no writes."""
    source = source.resolve(strict=True)
    data = source.read_bytes()
    require(sha(data) == SOURCE_SHA, "source must be the exact native fullbody assembly v26 checkpoint")
    before_archive, _, _, _, main = safe._validate_surgical_layout(data)
    before = CurrentNeutralModel(main, TOLERANCE)
    root = ex._parse_xml(main)
    summary_before = ex._xml_summary(root)
    require(not nonfinite_objects(before), "source has nonfinite object coordinates")
    new_names = {spec[0] for spec in WARP_SPECS}
    require(not new_names.intersection(item.name for item in before.objects), "new warp name already exists")
    require(not new_names.intersection(n.get("idstr") for n in root.iter("CDeformerId")), "new warp ID already exists")
    template = ex._warp_info(root, TEMPLATE)
    root_ref = template.parent_ref
    require(before.ids[root_ref].get("note") == "ROOT", "template no longer starts at ROOT")
    tracked = {}
    for name, (kind, _) in REPARENTS.items():
        item = one(before, name, kind)
        require(item.parent_ref == root_ref, name + ": expected ROOT parent")
        _, tracked[name] = before.keyform_positions(item, require_single_unbound=True)
    mesh_world_before = _all_artmesh_world_forms(before)
    roles = [f"lowerbody:{name}:{role}" for name, _, _, _ in WARP_SPECS
             for role in ("source", "positions", "form", "guid")]
    slots = secondary._allocate(root, roles)
    current = main
    created = []
    for name, parent_name, bounds, divisions in WARP_SPECS:
        current_model = CurrentNeutralModel(current, TOLERANCE)
        parent_ref = root_ref if parent_name is None else one(current_model, parent_name).guid_ref
        original = _grid(bounds, divisions)
        parent = current_model.transform(parent_ref)
        local = tuple(ex._float32(v) for v in current_model.inverse_many(parent, original))
        error = canvas._maximum_error(current_model.forward_many(parent, local), original)
        require(error < TOLERANCE, name + ": new grid canvas error")
        blocks, info = _clone_warp(root, template, name, slots, parent_ref,
                                   template.parent_part_ref, original, local, divisions)
        current = ex._append_shared_blocks(current, blocks)
        current = ex._patch_deformer_source_set(current, info["source_ref"])
        current = ex._patch_part_hierarchy(current, template.parent_part_ref, info["guid_ref"])
        info.update(parent=parent_name or "ROOT", canvas_bounds=list(bounds), max_canvas_error_px=error)
        created.append(info)
    changes = []
    for name, (kind, parent_name) in REPARENTS.items():
        model = CurrentNeutralModel(current, TOLERANCE)
        item, parent_item = one(model, name, kind), one(model, parent_name)
        _, old_local = model.keyform_positions(item, require_single_unbound=True)
        parent = model.transform(parent_item.guid_ref)
        local = tuple(ex._float32(v) for v in model.inverse_many(parent, tracked[name]))
        error = canvas._maximum_error(model.forward_many(parent, local), tracked[name])
        require(error < TOLERANCE, name + ": compensated canvas error")
        current, _ = canvas._patch_keyform_positions(current, target=item, old_values=old_local, new_values=local)
        current, _ = safe._patch_parent_ref_for_record(current, target=item, expected_old_ref=root_ref, new_parent=parent_item)
        changes.append({"name": name, "type": kind, "source_ref": item.source_ref,
                        "old_parent": "ROOT", "new_parent": parent_name, "parent_guid_ref": parent_item.guid_ref,
                        "max_canvas_error_px": error, "coordinate_count": len(local)})
    after = CurrentNeutralModel(current, TOLERANCE)
    after_root = ex._parse_xml(current)
    summary_after = ex._xml_summary(after_root)
    require(len(after.objects) == len(before.objects) + len(WARP_SPECS), "object count delta differs")
    require(not nonfinite_objects(after), "nonfinite object coordinates introduced")
    changed_names = set()
    for item in before.objects:
        later = one(after, item.name, item.object_type)
        require(later.guid_uuid == item.guid_uuid and later.source_ref == item.source_ref, "old identity changed")
        if raw_source(main, item) != raw_source(current, later):
            changed_names.add(item.name)
        if item.name in REPARENTS:
            require(_allowed_source_delta(before.source(item), after.source(later)), item.name + ": out-of-scope source delta")
            require(later.parent_uuid == one(after, REPARENTS[item.name][1]).guid_uuid, item.name + ": final parent mismatch")
        else:
            require(item == later, item.name + ": unrelated object identity/parent changed")
    require(changed_names == set(REPARENTS), "unrelated object source changed")
    mesh_world_after = _all_artmesh_world_forms(after)
    mesh_errors = {}
    for name, forms in mesh_world_before.items():
        require(len(forms) == len(mesh_world_after[name]), name + ": form count changed")
        errors = [canvas._maximum_error(old, new) for old, new in zip(forms, mesh_world_after[name])]
        require(all(math.isfinite(e) and e < TOLERANCE for e in errors), name + ": descendant canvas invariance failed")
        mesh_errors[name] = max(errors, default=0.0)
    # Validate Part membership registration; no existing child is moved in UI Parts.
    part_before = ex._part_hierarchy_state(root)
    part_after = ex._part_hierarchy_state(after_root)
    new_refs = {info["guid_ref"] for info in created}
    old_owner = ex._one_named(next(n for n in root.find("shared").findall("CPartSource")
        if ex._one_named(n, "CPartGuid", "guid").get("xs.ref") == template.parent_part_ref), "carray_list", "_childGuids")
    new_owner = ex._one_named(next(n for n in after_root.find("shared").findall("CPartSource")
        if ex._one_named(n, "CPartGuid", "guid").get("xs.ref") == template.parent_part_ref), "carray_list", "_childGuids")
    require(len(new_owner) == len(old_owner)+7, "new Part child count differs")
    require({n.get("xs.ref") for n in new_owner} - {n.get("xs.ref") for n in old_owner} == new_refs, "new Part registrations differ")
    output = safe._replace_main_xml(data, current)
    after_archive, _, _, _, decoded = safe._validate_surgical_layout(output)
    require(decoded == current, "CAFF XML roundtrip differs")
    preservation = safe._compare_entry_preservation(data, before_archive, output, after_archive, main_may_change=True)
    require(preservation.get("all_non_main_entries_byte_identical") is True, "raster/archive member changed")
    require(source.read_bytes() == data, "native source changed during planning")
    return output, {"schema": "jade.r21.lowerbody-hierarchy.v1", "status": "candidate_requires_cubism_load_save",
        "source": str(source), "source_sha256": sha(data), "output_sha256": sha(output),
        "template": TEMPLATE, "new_warps": created, "reparents": changes,
        "artmesh_count": len(mesh_errors), "artmesh_form_count": sum(len(v) for v in mesh_world_before.values()),
        "all_artmesh_canvas_errors_px": mesh_errors, "maximum_canvas_error_px": max(mesh_errors.values()),
        "tolerance_px": TOLERANCE, "all_original_arrays_untouched": True,
        "all_unrelated_object_sources_byte_identical": True, "all_coordinates_finite": True,
        "old_object_count": len(before.objects), "new_object_count": len(after.objects),
        "old_shared_count": summary_before["shared_definitions"], "new_shared_count": summary_after["shared_definitions"],
        "all_references_resolved": summary_after["all_references_resolved"],
        "all_uuids_unique": summary_after["all_uuids_unique"], "part_hierarchy_validated": bool(part_before and part_after),
        "archive": preservation, "new_parameter_bindings": 0,
        "notes": ["Global full-body warp is unbound; no motion or auto-displacement applied.",
                  "Five lower-body meshes plus two explicitly authorized body roots only.",
                  "All new warps belong to existing Root Part; old Part children are retained.",
                  "Foot and skirt poses, seam QA and native save remain caller work."]}


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
        require("TEST" in args.output.name and args.output.suffix.lower() == ".cmo3", "output must be TEST CMO3")
        require(source != args.output.resolve() and source != args.audit.resolve(), "cannot overwrite source")
        require(args.output.resolve() != args.audit.resolve(), "output and audit must differ")
        require(not args.output.exists() and not args.audit.exists(), "output/audit exists; refusing overwrite")
    data, audit = plan(source)
    if not args.dry_run:
        audit["output"] = str(args.output.resolve())
        exclusive(args.output, data)
        exclusive(args.audit, (json.dumps(audit, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
