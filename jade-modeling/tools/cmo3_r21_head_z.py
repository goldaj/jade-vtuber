#!/usr/bin/env python3
"""Add a moderate r21 head tilt using the existing native rotation deformer.

The exact neutral rotation form and every other object remain unchanged.
This is a first AngleZ rig, not a completed head XYZ or neck-corrective pass.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
import cmo3_create_deformer_experiment as experiment
import cmo3_eye_closure_professional as eye
import cmo3_head_z_functional as native
import cmo3_safe_roundtrip as safe
import cmo3_secondary_professional as secondary
from cmo3_r21_restore_eye_r_finite import require, sha, model_from_bytes, raw_source, exclusive, nonfinite_objects
from cmo3_r21_restore_sleeve_r_local import actual_neutral_transform
from cmo3_r21_face_roots_to_head import one
from cmo3_r21_mouth_open_first_rig import binding_imports

HEAD = "R_JAD_HEAD_Z"
KEYS = (-30.0, 0.0, 30.0)
ANGLES = (-15.0, 0.0, 15.0)


def plan(source: Path) -> tuple[bytes, dict]:
    data = source.read_bytes()
    before, xml = model_from_bytes(data)
    head = one(before, HEAD, "rotation-deformer")
    node = before.source(head)
    forms = experiment._one_named(node, "carray_list", "keyforms")
    require(len(forms) == 1, "Head Z is already bound: refusing replacement")
    form = forms[0]
    require(form.tag == "CRotationDeformerForm" and float(form.get("angle")) == 0.0
            and float(form.get("scale")) == 1.0 and form.get("isReflectX") == "false"
            and form.get("isReflectY") == "false", "Head neutral rotation differs")
    grid = experiment._one_named(node, "KeyformGridSource", "keyformGridSource")
    require(grid.get("xs.ref") is None, "Head grid already bound")
    pivot = actual_neutral_transform(before, head.guid_ref)
    children = {x.name for x in before.objects if x.parent_uuid == head.guid_uuid}
    required = {"D_JAD_FACE", "D_JAD_EYE_L", "D_JAD_EYE_R", "D_JAD_MOUTH",
                "D_JAD_EYE_L_CLOSED", "D_JAD_EYE_R_CLOSED", "D_JAD_MOUTH_OPEN",
                "D_JAD_HAIR_FRONT_GLOBAL", "D_JAD_HAIR_BACK_GLOBAL", "D_JAD_HAIR_AHOGE_ROOT",
                "D_JAD_EAR_L_ROOT", "D_JAD_EAR_R_ROOT"}
    require(required <= children, "Facial/hair/ear branch not under Head Z")
    require(1800 < pivot.pivot_x < 2050 and 1100 < pivot.pivot_y < 1350,
            "Unexpected head pivot: inspect before binding")
    require(not nonfinite_objects(before), "Nonfinite source coordinates")
    neutral_ref = experiment._one_named(form, "CFormGuid", "guid").get("xs.ref")
    slots = secondary._allocate(before.root, ("head_grid", "head_binding", "head_left", "head_right"))
    grid_ref, grid_idx = slots["head_grid"]
    binding_ref, binding_idx = slots["head_binding"]
    left_ref, left_idx = slots["head_left"]
    right_ref, right_idx = slots["head_right"]
    raw = raw_source(xml, head)
    raw_forms = re.findall(rb"<CRotationDeformerForm\b[^>]*>.*?</CRotationDeformerForm>", raw, re.DOTALL)
    require(len(raw_forms) == 1, "Ambiguous raw rotation neutral")
    neutral = raw_forms[0]
    new_forms = [native._clone_rotation_form(neutral, neutral_form_ref=neutral_ref, form_ref=left_ref, angle=ANGLES[0]),
                 neutral,
                 native._clone_rotation_form(neutral, neutral_form_ref=neutral_ref, form_ref=right_ref, angle=ANGLES[2])]
    changed = secondary._replace_inline_grid(raw, grid_ref)
    match, _ = secondary._keyforms(changed, b"CRotationDeformerForm")
    changed = secondary._replace_keyforms(changed, match, new_forms)
    current = experiment._replace_exact(xml, raw, changed, 1, "r21 head Z")
    blocks = [
        secondary._grid_block(grid_ref=grid_ref, grid_idx=grid_idx, binding_refs=[binding_ref],
                              accesses=[(0,), (1,), (2,)], form_refs=[left_ref, neutral_ref, right_ref]),
        eye._new_binding_block(grid_ref=grid_ref, binding_ref=binding_ref, binding_idx=binding_idx,
                               parameter_ref=eye._parameter_ref(before.root, "ParamAngleZ"), keys=KEYS),
        secondary._form_guid_block(left_ref, left_idx, sha(data), "r21-head-z-left"),
        secondary._form_guid_block(right_ref, right_idx, sha(data), "r21-head-z-right"),
    ]
    current = binding_imports(experiment._append_shared_blocks(current, blocks))
    output = safe._replace_main_xml(data, current)
    after, decoded = model_from_bytes(output)
    require(decoded == current and before.objects == after.objects, "Roundtrip or hierarchy changed")
    require(not nonfinite_objects(after), "Nonfinite coordinates introduced")
    final_raw = raw_source(current, one(after, HEAD, "rotation-deformer"))
    final_forms = re.findall(rb"<CRotationDeformerForm\b[^>]*>.*?</CRotationDeformerForm>", final_raw, re.DOTALL)
    require(final_forms == new_forms and final_forms[1] == neutral, "Head neutral or poses changed")
    changed_names = {i.name for i in before.objects if raw_source(xml, i) != raw_source(current, i)}
    require(changed_names == {HEAD}, "Unrelated object changed")
    a, _, _, _, _ = safe._validate_surgical_layout(data)
    b, _, _, _, _ = safe._validate_surgical_layout(output)
    preserved = safe._compare_entry_preservation(data, a, output, b, main_may_change=True)
    require(preserved.get("all_non_main_entries_byte_identical") is True, "Raster/archive changed")
    require(source.read_bytes() == data, "Source changed")
    return output, {"schema": "jade.r21.head-z.v1", "status": "candidate_requires_native_visual_gate",
        "source": str(source), "source_sha256": sha(data), "output_sha256": sha(output),
        "keys": KEYS, "angles_degrees": ANGLES, "canvas_pivot": [pivot.pivot_x, pivot.pivot_y],
        "neutral_byte_identical": True, "unrelated_sources_byte_identical": True,
        "direct_children": sorted(children), "archive": preserved,
        "remaining": ["Native head tilt and jaw-neck seam check", "Head XY and diagonal corrective forms"]}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--audit", type=Path, required=True)
    args = p.parse_args()
    require("r21" in args.source.name.lower() and "TEST" in args.output.name, "Expected r21 source and TEST destination")
    require(not args.output.exists() and not args.audit.exists(), "Refusing overwrite")
    data, audit = plan(args.source.resolve(strict=True))
    audit["output"] = str(args.output.resolve())
    exclusive(args.output, data)
    exclusive(args.audit, (json.dumps(audit, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({k: audit[k] for k in ("status", "output", "output_sha256", "angles_degrees", "canvas_pivot")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
