#!/usr/bin/env python3
"""Give r21 its first six-key MouthOpenY rig with existing painted mouth art.

The real neutral mouth and its socket are realigned to the healthy original
canvas. All four open layers share one continuous vertical opening field.
Their opacity is keyed directly on ArtMeshes, with a short complementary
handoff from the real neutral painting. This is a first speaking rig, not a
final phoneme/MouthForm rig. Native Cubism inspection remains required.
"""
from __future__ import annotations
import argparse
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
from cmo3_r21_restore_eye_r_finite import require, sha, model_from_bytes, nonfinite_objects, raw_source, exclusive, V5_SHA
from cmo3_r21_face_roots_to_head import one

KEYS = (0.0, 0.05, 0.12, 0.30, 0.60, 1.0)
OPEN_OPACITY = (0.0, 0.20, 0.85, 1.0, 1.0, 1.0)
SCALES = (0.04, 0.09, 0.16, 0.34, 0.62, 1.0)
NEUTRAL = "JAD_R21_MOUTH_NEUTRAL_CLEAN"
SOCKET = "JAD_R21_MOUTH_SOCKET_SKIN"
OPEN = ("JAD_R21_MOUTH_OPEN_OUTLINE", "JAD_R21_MOUTH_OPEN_TEETH_UPPER", "JAD_R21_MOUTH_OPEN_TONGUE", "JAD_R21_MOUTH_OPEN_INTERIOR")
BOUND = (NEUTRAL, *OPEN)
TOLERANCE = 0.001


class CurrentNeutralModel(canvas.GeometryModel):
    """Use actual one-form warp grids; do not assume they equal old originals."""
    def transform(self, guid_ref: str) -> Any:
        if guid_ref in self.transform_cache:
            return self.transform_cache[guid_ref]
        item = self.by_guid_ref.get(guid_ref)
        if item is None or item.object_type != "warp-deformer":
            return super().transform(guid_ref)
        source = self.source(item)
        cols = int(canvas._one_direct_named(source, "i", "col").text)
        rows = int(canvas._one_direct_named(source, "i", "row").text)
        _, points = self.keyform_positions(item, require_single_unbound=True)
        require(cols > 0 and rows > 0 and len(points) == 2 * (cols + 1) * (rows + 1), item.name + ": warp dimensions differ")
        result = canvas.WarpTransform(guid_ref, item.name, cols, rows, points, 0, 0.0, self.transform(item.parent_ref))
        self.transform_cache[guid_ref] = result
        return result


def opening(points: tuple[float, ...], scale: float) -> tuple[float, ...]:
    # Quadratic through the dark painted crease of the accepted v13 neutral:
    # global x center 1921, side line near y922, smiling middle near y930.5.
    result = []
    for x, y in zip(points[0::2], points[1::2]):
        dx = x - 1921.0
        crease = 930.5096659932564 + 0.005730386829566743 * dx - 0.007098758796739814 * dx * dx
        result.extend((x, crease + scale * (y - crease)))
    return tuple(result)


def visible_source(raw: bytes) -> bytes:
    pattern = re.compile(rb'(<b\b(?=[^>]*\bxs\.n="isVisible")[^>]*>)(?:true|false)(</b>)')
    matches = list(pattern.finditer(raw))
    require(len(matches) == 1, "isVisible source flag missing or ambiguous")
    match = matches[0]
    return raw[:match.start()] + match.group(1) + b"true" + match.group(2) + raw[match.end():]


def binding_imports(main: bytes) -> bytes:
    # These four Java serializer imports are absent in an entirely unbound
    # native model. Names verified against the working native v003 blink file.
    classes = (
        "com.live2d.cubism.doc.model.interpolator.InterpolationType",
        "com.live2d.cubism.doc.model.interpolator.KeyOnParameter",
        "com.live2d.cubism.doc.model.interpolator.KeyformBindingSource",
        "com.live2d.cubism.doc.model.interpolator.extendedInterpolation.ExtendedInterpolationType",
    )
    missing = [f"<?import {name}?>".encode("ascii") for name in classes if f"<?import {name}?>".encode("ascii") not in main]
    marker = b"<root fileFormatVersion="
    require(main.count(marker) == 1, "root marker ambiguous")
    pos = main.index(marker)
    return main[:pos] + b"".join(line+b"\r\n" for line in missing) + main[pos:]


def bind(main: bytes, model: Any, item: Any, originals: tuple[float, ...], slots: dict, source_sha: str, parameter_ref: str) -> tuple[bytes, list[bytes], dict]:
    source = model.source(item)
    raw = raw_source(main, item)
    form_node = experiment._one_named(source, "carray_list", "keyforms")
    require(len(form_node) == 1, item.name + ": expected one neutral form")
    form_tag = form_node[0].tag.encode("ascii")
    _, old_forms = secondary._keyforms(raw, form_tag)
    require(len(old_forms) == 1, item.name + ": raw neutral form differs")
    model.keyform_positions(item, require_single_unbound=True)
    parent = model.transform(item.parent_ref)
    grid_ref, grid_idx = slots[item.name + ":grid"]
    binding_ref, binding_idx = slots[item.name + ":binding"]
    forms, refs, blocks, errors, opacities = [], [], [], [], []
    for index, key in enumerate(KEYS):
        ref, idx = slots[item.name + ":form:" + str(index)]
        posed = originals if item.name == NEUTRAL else opening(originals, SCALES[index])
        local = tuple(canvas._float32(v) for v in model.inverse_many(parent, posed))
        error = canvas._maximum_error(model.forward_many(parent, local), posed)
        require(error <= TOLERANCE, item.name + ": pose canvas proof failed")
        opacity = 1.0 - OPEN_OPACITY[index] if item.name == NEUTRAL else OPEN_OPACITY[index]
        forms.append(secondary._clone_form(old_forms[0], new_ref=ref, opacity=opacity, positions=local, multiply=None, face=face, experiment=experiment))
        refs.append(ref)
        errors.append(error)
        opacities.append(opacity)
        blocks.append(secondary._form_guid_block(ref, idx, source_sha, item.name + ":form:" + str(index)))
    changed = secondary._replace_inline_grid(raw, grid_ref)
    match, _ = secondary._keyforms(changed, form_tag)
    changed = secondary._replace_keyforms(changed, match, forms)
    changed = visible_source(changed)
    blocks.extend([
        secondary._grid_block(grid_ref=grid_ref, grid_idx=grid_idx, binding_refs=[binding_ref], accesses=[(i,) for i in range(len(KEYS))], form_refs=refs),
        eye._new_binding_block(grid_ref=grid_ref, binding_ref=binding_ref, binding_idx=binding_idx, parameter_ref=parameter_ref, keys=KEYS),
    ])
    patched = experiment._replace_exact(main, raw, changed, 1, "bind " + item.name)
    return patched, blocks, {"name": item.name, "keys": KEYS, "opacities": opacities, "max_canvas_error_px": max(errors)}


def plan(source: Path, reference: Path) -> tuple[bytes, dict[str, Any]]:
    require("r21" in source.name.lower(), "source must be Jade r21")
    data, reference_data = source.read_bytes(), reference.read_bytes()
    require(sha(reference_data) == V5_SHA, "healthy v5 reference differs")
    _, original_xml = model_from_bytes(data)
    before = CurrentNeutralModel(original_xml, TOLERANCE)
    healthy, _ = model_from_bytes(reference_data)
    require(not nonfinite_objects(before), "source contains nonfinite coordinates")
    head = one(before, "R_JAD_HEAD_Z", "rotation-deformer")
    for name in ("D_JAD_EYE_L_CLOSED", "D_JAD_EYE_R_CLOSED", "D_JAD_MOUTH_OPEN"):
        require(one(before, name).parent_uuid == head.guid_uuid, name + ": run face-roots attachment first")
    originals, alignments = {}, {}
    for name in (*BOUND, SOCKET):
        item = one(before, name, "art-mesh")
        original = before.original_canvas(item)
        old = one(healthy, name, "art-mesh")
        require(canvas._maximum_error(original, healthy.original_canvas(old)) <= TOLERANCE, name + ": originals differ from healthy art checkpoint")
        _, local = before.keyform_positions(item, require_single_unbound=True)
        current = before.forward_many(before.transform(item.parent_ref), local)
        delta = canvas._maximum_error(current, original)
        require(delta < 30.0, name + ": unexpected alignment correction above 30px")
        originals[name] = original
        alignments[name] = {"max_original_offset_before_px": delta, "target_canvas_bounds": canvas._bounds(original)}
    parameter_ref = eye._parameter_ref(before.root, "ParamMouthOpenY")
    roles = [role for name in BOUND for role in (name + ":grid", name + ":binding", *(name + ":form:" + str(i) for i in range(len(KEYS))))]
    slots = secondary._allocate(before.root, roles)
    current, shared, bindings = original_xml, [], []
    for name in BOUND:
        # Parent grids remain unbound, so the initial current model suffices.
        item = one(before, name, "art-mesh")
        current, blocks, report = bind(current, before, item, originals[name], slots, sha(data), parameter_ref)
        shared.extend(blocks)
        bindings.append(report)
    socket = one(before, SOCKET, "art-mesh")
    _, old_local = before.keyform_positions(socket, require_single_unbound=True)
    parent = before.transform(socket.parent_ref)
    new_local = tuple(canvas._float32(v) for v in before.inverse_many(parent, originals[SOCKET]))
    require(canvas._maximum_error(before.forward_many(parent, new_local), originals[SOCKET]) <= TOLERANCE, "socket canvas proof failed")
    current, _ = canvas._patch_keyform_positions(current, target=socket, old_values=old_local, new_values=new_local)
    current = experiment._append_shared_blocks(current, shared)
    current = binding_imports(current)
    after = CurrentNeutralModel(current, TOLERANCE)
    require(not nonfinite_objects(after), "nonfinite coordinates introduced")
    require(before.objects == after.objects, "hierarchy/object identity changed")
    changed = {i.name for i in before.objects if raw_source(original_xml, i) != raw_source(current, i)}
    require(changed <= set((*BOUND, SOCKET)) and set(BOUND) <= changed, "unexpected changed source set")
    for name in BOUND:
        item = one(after, name, "art-mesh")
        semantic = eye._generic_grid_semantics(after.root, after, item, experiment)
        require(semantic["notes"] == ["ParamMouthOpenY"], name + ": incorrect bound parameter")
        require(tuple(semantic["keys"][0]) == KEYS, name + ": incorrect six-key grid")
        require(len(semantic["access_to_ref"]) == len(KEYS), name + ": incomplete keyforms")
        forms = experiment._one_named(after.source(item), "carray_list", "keyforms")
        require(experiment._one_named(after.source(item), "b", "isVisible").text == "true", name + ": editor visibility is off")
        require(len(forms) == len(KEYS), name + ": wrong form count")
        for index, form in enumerate(forms):
            local = canvas._float_values(experiment._one_named(form, "float-array", "positions"), name)
            expected = originals[name] if name == NEUTRAL else opening(originals[name], SCALES[index])
            observed = after.forward_many(after.transform(item.parent_ref), local)
            require(canvas._maximum_error(observed, expected) <= TOLERANCE, name + ": serialized pose differs")
            opacity = float(experiment._one_named(form, "f", "opacity").text)
            expected_opacity = 1 - OPEN_OPACITY[index] if name == NEUTRAL else OPEN_OPACITY[index]
            require(abs(opacity - expected_opacity) < 1e-6, name + ": opacity differs")
    output = safe._replace_main_xml(data, current)
    archive_before, _, _, _, _ = safe._validate_surgical_layout(data)
    archive_after, _, _, _, decoded = safe._validate_surgical_layout(output)
    require(decoded == current, "encoded XML differs")
    preserved = safe._compare_entry_preservation(data, archive_before, output, archive_after, main_may_change=True)
    require(preserved.get("all_non_main_entries_byte_identical") is True, "non-main member changed")
    require(source.read_bytes() == data and reference.read_bytes() == reference_data, "source/reference changed")
    return output, {"schema": "jade.r21.mouth-open-first-rig.v1", "status": "candidate_requires_cubism_visual_gate", "source": str(source), "source_sha256": sha(data), "output_sha256": sha(output), "alignments": alignments, "bindings": bindings, "opening_scales": SCALES, "painted_crease_reference": "accepted mouth_endpoints_v13 neutral dark contour, quadratic in original canvas", "endpoint_zero": "real neutral visible; four OPEN ArtMeshes invisible", "endpoint_one": "neutral invisible; four original OPEN ArtMeshes visible at original shape", "all_unrelated_sources_byte_identical": True, "after_nonfinite": [], "archive": preserved, "remaining": ["Native visual test of intermediate opening", "MouthForm and phoneme shaping"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--reference", type=Path, required=True)
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
    data, audit = plan(source, args.reference.resolve(strict=True))
    if not args.dry_run:
        audit["output"] = str(args.output.resolve())
        exclusive(args.output, data)
        exclusive(args.audit, (json.dumps(audit, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
