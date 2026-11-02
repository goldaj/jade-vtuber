#!/usr/bin/env python3
"""Activate the previously chosen moderate HeadZ range on native r21 v28.

The v23 experiment supplies only its accepted key/angle convention. Every
form, identity, raster and source used here comes from the pinned native v28.
Only R_JAD_HEAD_Z gains two rotation forms and one ParamAngleZ binding.
Body, breath, leg, skirt, eye and mouth additions are preserved byte-exact.
This is an unvalidated native candidate: shoulder underpainting and a Cubism
load/pose/save gate remain separate work.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import cmo3_create_deformer_experiment as ex
import cmo3_eye_closure_professional as eye
import cmo3_head_z_functional as native
import cmo3_reparent_preserve_canvas as canvas
import cmo3_safe_roundtrip as safe
import cmo3_secondary_professional as secondary
from cmo3_r21_body_secondary import select_keys
from cmo3_r21_face_roots_to_head import one
from cmo3_r21_head_z import HEAD, KEYS, ANGLES
from cmo3_r21_mouth_open_first_rig import binding_imports
from cmo3_r21_restore_eye_r_finite import require, sha, model_from_bytes, raw_source, exclusive, nonfinite_objects
from cmo3_r21_restore_sleeve_r_local import actual_neutral_transform


SOURCE_SHA = "36F1685567C4989168BA8D37F4CF35C0643971E593C1A514B2DDF3DACF225298"
TOLERANCE = 0.001
REQUIRED_CHILDREN = {
    "D_JAD_FACE", "D_JAD_EYE_L", "D_JAD_EYE_R", "D_JAD_MOUTH",
    "D_JAD_EYE_L_CLOSED", "D_JAD_EYE_R_CLOSED", "D_JAD_MOUTH_OPEN",
    "D_JAD_HAIR_FRONT_GLOBAL", "D_JAD_HAIR_BACK_GLOBAL", "D_JAD_HAIR_AHOGE_ROOT",
    "D_JAD_EAR_L_ROOT", "D_JAD_EAR_R_ROOT",
}


def neutral_model(xml: bytes):
    """Read-only geometry mirror; never return this normalized XML for saving."""
    root = ex._parse_xml(xml)
    head_sources = [n for n in root.find("shared").findall("CRotationDeformerSource")
                    if ex._one_named(n, "s", "localName").text == HEAD]
    require(len(head_sources) == 1, "HeadZ source missing/ambiguous")
    source = head_sources[0]
    forms = ex._direct_named(source, "carray_list", "keyforms")
    if len(forms) == 3:
        zero = [f for f in forms if float(f.get("angle")) == 0.0]
        require(len(zero) == 1, "HeadZ neutral not unique")
        chosen = copy.deepcopy(zero[0])
        forms.clear()
        forms.attrib.update({"xs.n": "keyforms", "count": "1"})
        forms.append(chosen)
        grid_ref = ex._one_named(source, "KeyformGridSource", "keyformGridSource").get("xs.ref")
        grid = ex._id_map(root)[grid_ref]
        bindings = ex._direct_named(grid, "array_list", "keyformBindings")
        bindings.clear()
        bindings.attrib.update({"xs.n": "keyformBindings", "count": "0"})
        grid_forms = ex._direct_named(grid, "array_list", "keyformsOnGrid")
        form_ref = ex._one_named(chosen, "CFormGuid", "guid").get("xs.ref")
        selected = [g for g in grid_forms if ex._one_named(g, "CFormGuid", "keyformGuid").get("xs.ref") == form_ref]
        require(len(selected) == 1, "HeadZ neutral grid entry missing")
        selected = copy.deepcopy(selected[0])
        grid_forms.clear()
        grid_forms.attrib.update({"xs.n": "keyformsOnGrid", "count": "1"})
        grid_forms.append(selected)
    else:
        require(len(forms) == 1, "HeadZ has an unsupported form count")
    model = select_keys(ET.tostring(root, encoding="utf-8"), {})
    head = one(model, HEAD, "rotation-deformer")
    # GeometryModel's rotation fallback uses stale original-shape pivots.
    # Cache the actual current-parent-chain pivot for every head descendant.
    model.transform_cache[head.guid_ref] = actual_neutral_transform(model, head.guid_ref)
    return model


def _world_mesh_forms(model):
    result = {}
    for item in model.objects:
        if item.object_type != "art-mesh":
            continue
        transform = model.transform(item.parent_ref)
        forms = ex._direct_named(model.source(item), "carray_list", "keyforms")
        result[item.name] = [model.forward_many(transform, canvas._float_values(
            ex._direct_named(form, "float-array", "positions"), item.name)) for form in forms]
    return result


def plan(source: Path) -> tuple[bytes, dict]:
    """Return candidate CAFF bytes plus audit, without any filesystem write."""
    source = source.resolve(strict=True)
    data = source.read_bytes()
    require(sha(data) == SOURCE_SHA, "requires exact native body_secondary v28")
    before, xml = model_from_bytes(data)
    require(KEYS == (-30.0, 0.0, 30.0) and ANGLES == (-15.0, 0.0, 15.0), "accepted HeadZ convention changed")
    require(not nonfinite_objects(before), "nonfinite source coordinates")
    meshes = [i for i in before.objects if i.object_type == "art-mesh"]
    require(len(meshes) == 66, "expected 66 v28 ArtMeshes")
    head = one(before, HEAD, "rotation-deformer")
    node = before.source(head)
    forms = ex._direct_named(node, "carray_list", "keyforms")
    require(len(forms) == 1, "HeadZ already bound; refusing replacement")
    form = forms[0]
    require(form.tag == "CRotationDeformerForm" and float(form.get("angle")) == 0.0
            and float(form.get("scale")) == 1.0 and form.get("isReflectX") == "false"
            and form.get("isReflectY") == "false", "HeadZ neutral rotation differs")
    grid = ex._one_named(node, "KeyformGridSource", "keyformGridSource")
    require(grid.get("xs.ref") is None and len(ex._direct_named(grid, "array_list", "keyformBindings")) == 0,
            "HeadZ already has a binding")
    children = {i.name for i in before.objects if i.parent_uuid == head.guid_uuid}
    require(REQUIRED_CHILDREN <= children, "required v25-v28 head branch missing")
    neutral_before = neutral_model(xml)
    pivot = actual_neutral_transform(neutral_before, head.guid_ref)
    require(1800.0 < pivot.pivot_x < 2050.0 and 1100.0 < pivot.pivot_y < 1350.0, "unexpected v28 head pivot")
    parameter_ref = eye._parameter_ref(before.root, "ParamAngleZ")
    neutral_ref = ex._one_named(form, "CFormGuid", "guid").get("xs.ref")
    slots = secondary._allocate(before.root, ("v28-head-grid", "v28-head-binding", "v28-head-left", "v28-head-right"))
    grid_ref, grid_idx = slots["v28-head-grid"]
    binding_ref, binding_idx = slots["v28-head-binding"]
    left_ref, left_idx = slots["v28-head-left"]
    right_ref, right_idx = slots["v28-head-right"]
    raw = raw_source(xml, head)
    raw_forms = re.findall(rb"<CRotationDeformerForm\b[^>]*>.*?</CRotationDeformerForm>", raw, re.DOTALL)
    require(len(raw_forms) == 1, "ambiguous raw v28 rotation neutral")
    neutral_form = raw_forms[0]
    new_forms = [native._clone_rotation_form(neutral_form, neutral_form_ref=neutral_ref, form_ref=left_ref, angle=ANGLES[0]),
                 neutral_form,
                 native._clone_rotation_form(neutral_form, neutral_form_ref=neutral_ref, form_ref=right_ref, angle=ANGLES[2])]
    changed = secondary._replace_inline_grid(raw, grid_ref)
    match, _ = secondary._keyforms(changed, b"CRotationDeformerForm")
    changed = secondary._replace_keyforms(changed, match, new_forms)
    current = ex._replace_exact(xml, raw, changed, 1, "activate v28 native HeadZ")
    blocks = [
        secondary._grid_block(grid_ref=grid_ref, grid_idx=grid_idx, binding_refs=[binding_ref],
                              accesses=[(0,), (1,), (2,)], form_refs=[left_ref, neutral_ref, right_ref]),
        eye._new_binding_block(grid_ref=grid_ref, binding_ref=binding_ref, binding_idx=binding_idx,
                               parameter_ref=parameter_ref, keys=KEYS),
        secondary._form_guid_block(left_ref, left_idx, SOURCE_SHA, "r21-v28-head-z-left"),
        secondary._form_guid_block(right_ref, right_idx, SOURCE_SHA, "r21-v28-head-z-right"),
    ]
    current = binding_imports(ex._append_shared_blocks(current, blocks))
    final_root = ex._parse_xml(current)
    definitions = [n.get("xs.id") for n in final_root.iter() if n.get("xs.id")]
    refs = [n.get("xs.ref") for n in final_root.iter() if n.get("xs.ref")]
    uuids = [n.get("uuid") for n in final_root.iter() if n.get("uuid")]
    indices = [n.get("xs.idx") for n in final_root.find("shared")]
    require(len(definitions) == len(set(definitions)) and set(refs) <= set(definitions), "invalid shared references")
    require(len(uuids) == len(set(uuids)) and len(indices) == len(set(indices)), "UUID/index collision")
    for old in before.root.find("shared"):
        if old.get("xs.id") == head.source_ref:
            continue
        require(ex._block_by_id(xml, old.tag, old.get("xs.id")) == ex._block_by_id(current, old.tag, old.get("xs.id")),
                "old shared dependency changed: " + old.get("xs.id"))
    # No existing parameter source/value, including the v27/v28 controls, changes.
    before_parameters = list(before.root.iter("CParameterSource"))
    after_parameters = list(final_root.iter("CParameterSource"))
    require([ET.tostring(p) for p in before_parameters] == [ET.tostring(p) for p in after_parameters], "parameter source changed")
    neutral_after = neutral_model(current)
    worlds_before, worlds_after = _world_mesh_forms(neutral_before), _world_mesh_forms(neutral_after)
    errors = {}
    for name, before_forms in worlds_before.items():
        require(len(before_forms) == len(worlds_after[name]), name + ": artwork form count changed")
        errors[name] = max(canvas._maximum_error(a, b) for a, b in zip(before_forms, worlds_after[name]))
        require(math.isfinite(errors[name]) and errors[name] < TOLERANCE, name + ": neutral canvas changed")
    result = safe._replace_main_xml(data, current)
    after, decoded = model_from_bytes(result)
    require(decoded == current and before.objects == after.objects, "roundtrip or hierarchy changed")
    require(not nonfinite_objects(after), "nonfinite output coordinates")
    final_forms = re.findall(rb"<CRotationDeformerForm\b[^>]*>.*?</CRotationDeformerForm>", raw_source(current, head), re.DOTALL)
    require(final_forms == new_forms and final_forms[1] == neutral_form, "HeadZ neutral/endpoint forms changed")
    changed_names = {i.name for i in before.objects if raw_source(xml, i) != raw_source(current, i)}
    require(changed_names == {HEAD}, "unrelated object source changed")
    a, _, _, _, _ = safe._validate_surgical_layout(data)
    b, _, _, _, _ = safe._validate_surgical_layout(result)
    preserved = safe._compare_entry_preservation(data, a, result, b, main_may_change=True)
    require(preserved.get("all_non_main_entries_byte_identical") is True, "raster/archive member changed")
    require(source.read_bytes() == data, "source checkpoint changed")
    return result, {
        "schema": "jade.r21.head-z-v28.v1", "status": "candidate_not_native_validated",
        "source": str(source), "source_sha256": SOURCE_SHA, "output_sha256": sha(result),
        "keys": KEYS, "angles_degrees": ANGLES, "parameter_id": "ParamAngleZ", "parameter_ref": parameter_ref,
        "head_source_ref": head.source_ref, "head_guid_ref": head.guid_ref, "grid_ref": grid_ref, "binding_ref": binding_ref,
        "canvas_pivot": [pivot.pivot_x, pivot.pivot_y], "neutral_byte_identical": True,
        "maximum_neutral_canvas_error_px": max(errors.values()), "artmesh_count": len(errors),
        "artmesh_form_count": sum(len(v) for v in worlds_before.values()),
        "object_count": len(after.objects), "old_shared_dependencies_byte_identical": True,
        "all_existing_parameter_sources_identical": True, "unrelated_sources_byte_identical": True,
        "all_v25_v28_art_rig_additions_preserved": True, "all_references_resolved": True,
        "all_uuids_indices_unique": True, "all_coordinates_finite": True,
        "direct_children": sorted(children), "archive": preserved,
        "remaining": ["Shoulder/neck underpainting handled separately", "Native head tilt and combined body/breath pose gate", "Native save/reopen"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    if not args.dry_run:
        require(args.output is not None and args.audit is not None, "--output/--audit required")
        require("TEST" in args.output.name and args.output.suffix.lower() == ".cmo3", "output must be TEST CMO3")
        require(len({source, args.output.resolve(), args.audit.resolve()}) == 3, "paths must be distinct")
        require(not args.output.exists() and not args.audit.exists(), "refusing overwrite")
    result, audit = plan(source)
    if not args.dry_run:
        audit["output"] = str(args.output.resolve())
        exclusive(args.output, result)
        exclusive(args.audit, (json.dumps(audit, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({k: audit[k] for k in ("status", "source_sha256", "output_sha256", "angles_degrees", "canvas_pivot", "maximum_neutral_canvas_error_px")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
