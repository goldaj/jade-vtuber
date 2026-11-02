#!/usr/bin/env python3
"""Create r21 continuous bilateral blink using the real painted CLOSED sprites.

Each open eye is progressively compressed toward the contour measured in its
accepted CLOSED_TRUE PNG. Closed artwork itself stays intact. A short
complementary opacity handoff is keyed directly on the two ArtMeshes per eye.
Editor visibility is explicitly enabled. All other rigs remain unchanged.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any
import numpy as np
from PIL import Image
import cmo3_create_deformer_experiment as experiment
import cmo3_eye_closure_professional as eye
import cmo3_face_fx_scaffold as face
import cmo3_reparent_preserve_canvas as canvas
import cmo3_secondary_professional as secondary
import cmo3_safe_roundtrip as safe
from cmo3_r21_restore_eye_r_finite import require, sha, model_from_bytes, nonfinite_objects, raw_source, exclusive, V5_SHA
from cmo3_r21_face_roots_to_head import one
from cmo3_r21_mouth_open_first_rig import CurrentNeutralModel, visible_source, binding_imports, BOUND as MOUTH_BOUND

KEYS = (0.0, 0.02, 0.04, 0.06, 0.08, 0.12, 0.20, 0.35, 0.55, 0.80, 1.0)
OPEN_ALPHA = (0.0, 0.05, 0.25, 0.55, 0.80, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
TOLERANCE = 0.001


def names(side: str) -> tuple[str, str, str]:
    stem = "JAD_R21_EYE_" + side
    return stem + "_OPEN_MASTER", stem + "_CLOSED_TRUE", stem + "_SOCKET_SKIN"


def contour(assets: Path, side: str) -> dict[str, Any]:
    closed_manifest = json.loads((assets / "eye_endpoints_v7/Jade_r21_eye_endpoints_v1_manifest.json").read_text(encoding="utf-8"))
    open_manifest = json.loads((assets / "master_v4_rig_layers_v1/Jade_r21_rig_layers_v1_manifest.json").read_text(encoding="utf-8"))
    open_name, closed_name, _ = names(side)
    closed_entry = next(x for x in closed_manifest["layers"] if x["name"] == closed_name)
    open_entry = next(x for x in open_manifest["layers"] if x["name"] == open_name)
    closed_file = assets / "eye_endpoints_v7" / (closed_name + ".png")
    open_file = assets / "master_v4_rig_layers_v1/layers" / (open_name + ".png")
    a = np.asarray(Image.open(closed_file).convert("RGBA"))
    require(a.shape[:2] == (closed_entry["height"], closed_entry["width"]), "closed asset dimensions differ")
    mask = (a[:, :, 3] > 140) & (a[:, :, :3].max(axis=2) < 135)
    ys, xs = np.nonzero(mask)
    closed_dark_count = len(xs)
    require(len(xs) > 1000, "closed contour has insufficient opaque dark pixels")
    xx, yy = [], []
    for column in np.unique(xs):
        rows = ys[xs == column]
        if len(rows) >= 2:
            xx.append(float(column + closed_entry["x"]))
            yy.append(float(np.median(rows) + closed_entry["y"]))
    closed_min, closed_max = min(xx), max(xx)
    closed_center = (closed_min + closed_max) * 0.5
    polynomial = np.polyfit(np.asarray(xx) - closed_center, yy, 2)
    a = np.asarray(Image.open(open_file).convert("RGBA"))
    require(a.shape[:2] == (open_entry["height"], open_entry["width"]), "open asset dimensions differ")
    rgb = a[:, :, :3].astype(float)
    mask = (a[:, :, 3] > 140) & (rgb.max(axis=2) < 110) & (rgb[:, :, 0] >= rgb[:, :, 2])
    ys, xs = np.nonzero(mask)
    require(len(xs) > 1000, "open contour has insufficient opaque dark pixels")
    open_min, open_max = float(xs.min() + open_entry["x"]), float(xs.max() + open_entry["x"])
    ratio = (closed_max - closed_min) / (open_max - open_min)
    require(0.60 < ratio < 1.10, "unexpected closed/open contour width ratio")
    require(abs(closed_center - (open_min + open_max) * 0.5) < 30, "unexpected contour center mismatch")
    return {"side": side, "closed_center_x": closed_center, "open_center_x": (open_min + open_max) * 0.5,
            "closed_to_open_width_ratio": ratio, "closed_contour_polynomial": polynomial.tolist(),
            "closed_dark_pixel_count": closed_dark_count, "closed_png_sha256": sha(closed_file.read_bytes()),
            "open_png_sha256": sha(open_file.read_bytes()), "closed_asset": str(closed_file), "open_asset": str(open_file)}


def open_pose(original: tuple[float, ...], key: float, curve: dict) -> tuple[float, ...]:
    if key == 1.0:
        return original
    result = []
    # Preserve a 6% geometric strip at zero (invisible): smaller compression
    # folds a few thin legacy lash triangles when following the painted arc.
    # The real CLOSED sprite supplies the exact zero endpoint.
    scale = 0.06 + 0.94 * key
    a, b, c = curve["closed_contour_polynomial"]
    for x, y in zip(original[0::2], original[1::2]):
        target_x = curve["closed_center_x"] + (x - curve["open_center_x"]) * curve["closed_to_open_width_ratio"]
        posed_x = key * x + (1.0 - key) * target_x
        dx = posed_x - curve["closed_center_x"]
        baseline = a * dx * dx + b * dx + c
        result.extend((posed_x, baseline + scale * (y - baseline)))
    return tuple(result)


def areas(points: tuple[float, ...], indices: tuple[int, ...]) -> list[float]:
    vertices = list(zip(points[0::2], points[1::2]))
    result = []
    for offset in range(0, len(indices), 3):
        a, b, c = (vertices[k] for k in indices[offset:offset+3])
        result.append((b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0]))
    return result


def plan(source: Path, reference: Path, assets: Path) -> tuple[bytes, dict[str, Any]]:
    require("r21" in source.name.lower(), "source must be Jade r21")
    data, reference_data = source.read_bytes(), reference.read_bytes()
    require(sha(reference_data) == V5_SHA, "healthy v5 reference differs")
    _, xml = model_from_bytes(data)
    before = CurrentNeutralModel(xml, TOLERANCE)
    healthy, _ = model_from_bytes(reference_data)
    require(not nonfinite_objects(before), "source contains nonfinite coordinates")
    # Do not silently build on the superseded mouth r01 visibility mistake.
    for name in MOUTH_BOUND:
        require(experiment._one_named(before.source(one(before, name, "art-mesh")), "b", "isVisible").text == "true", "mouth visibility off: use mouth_open_r02 or its native save")
    curves = {side: contour(assets, side) for side in ("L", "R")}
    bound_names = [name for side in ("L", "R") for name in names(side)[:2]]
    roles = [role for name in bound_names for role in (name+":grid", name+":binding", *(name+":form:"+str(i) for i in range(len(KEYS))))]
    slots = secondary._allocate(before.root, roles)
    current, shared, changes, alignments = xml, [], [], {}
    expected_poses = {}
    for side in ("L", "R"):
        open_name, closed_name, socket_name = names(side)
        parameter = eye._parameter_ref(before.root, "ParamEye"+side+"Open")
        for name in (open_name, closed_name, socket_name):
            item = one(before, name, "art-mesh")
            original = before.original_canvas(item)
            old = one(healthy, name, "art-mesh")
            require(canvas._maximum_error(original, healthy.original_canvas(old)) <= TOLERANCE, name+": immutable geometry differs from v5")
            _, local = before.keyform_positions(item, require_single_unbound=True)
            parent = before.transform(item.parent_ref)
            actual = before.forward_many(parent, local)
            offset = canvas._maximum_error(actual, original)
            if name == "JAD_R21_EYE_L_SOCKET_SKIN":
                # This exact imported branch retained finite but mis-scaled
                # coordinates since hierarchy normalization. Originals match
                # healthy v5; restore the full skin underlay before blinking.
                require(item.guid_uuid == "fb50024a-ac18-464d-8f03-c247de39c65a", "left socket identity differs")
                require(offset < 0.001 or 228.9 < offset < 229.1, "left socket corruption differs from measured source")
            else:
                require(offset < 30, name+": unexpected alignment correction above 30px")
            alignments[name] = offset
            if name == socket_name:
                restored = tuple(canvas._float32(v) for v in before.inverse_many(parent, original))
                require(canvas._maximum_error(before.forward_many(parent, restored), original) <= TOLERANCE, name+": socket proof failed")
                current, _ = canvas._patch_keyform_positions(current, target=item, old_values=local, new_values=restored)
                continue
            raw = raw_source(current, item)
            forms_node = experiment._one_named(before.source(item), "carray_list", "keyforms")
            require(len(forms_node) == 1, name+": expected one unbound neutral")
            form_tag = forms_node[0].tag.encode("ascii")
            _, source_forms = secondary._keyforms(raw, form_tag)
            require(len(source_forms) == 1, name+": raw form mismatch")
            grid_ref, grid_idx = slots[name+":grid"]
            binding_ref, binding_idx = slots[name+":binding"]
            forms, refs, opacity_values, pose_values = [], [], [], []
            index_node = canvas._one_direct_named(before.source(item), "int-array", "indices")
            indices = tuple(int(value) for value in index_node.text.split())
            reference_areas = areas(original, indices)
            min_area_ratio = 1.0
            for index, key in enumerate(KEYS):
                ref, idx = slots[name+":form:"+str(index)]
                posed = open_pose(original, key, curves[side]) if name == open_name else original
                local = tuple(canvas._float32(v) for v in before.inverse_many(parent, posed))
                observed = before.forward_many(parent, local)
                require(canvas._maximum_error(observed, posed) <= TOLERANCE, name+": canvas pose error")
                ratios = [a/b for a,b in zip(areas(observed,indices),reference_areas) if abs(b)>1e-8]
                require(all(r>0 for r in ratios), name+": triangle inversion at key "+str(key))
                min_area_ratio = min(min_area_ratio,min(ratios))
                alpha = OPEN_ALPHA[index] if name == open_name else 1.0-OPEN_ALPHA[index]
                forms.append(secondary._clone_form(source_forms[0],new_ref=ref,opacity=alpha,positions=local,multiply=None,face=face,experiment=experiment))
                refs.append(ref); opacity_values.append(alpha); pose_values.append(posed)
                shared.append(secondary._form_guid_block(ref,idx,sha(data),name+":form:"+str(index)))
            changed = secondary._replace_inline_grid(raw, grid_ref)
            match,_ = secondary._keyforms(changed,form_tag)
            changed = visible_source(secondary._replace_keyforms(changed,match,forms))
            current = experiment._replace_exact(current,raw,changed,1,"bind "+name)
            shared.extend([secondary._grid_block(grid_ref=grid_ref,grid_idx=grid_idx,binding_refs=[binding_ref],accesses=[(i,) for i in range(len(KEYS))],form_refs=refs), eye._new_binding_block(grid_ref=grid_ref,binding_ref=binding_ref,binding_idx=binding_idx,parameter_ref=parameter,keys=KEYS)])
            changes.append({"name":name,"parameter":"ParamEye"+side+"Open","keys":KEYS,"opacities":opacity_values,"isVisible":True,"minimum_triangle_area_ratio":min_area_ratio})
            expected_poses[name] = pose_values
    current = experiment._append_shared_blocks(current,shared)
    current = binding_imports(current)
    after = CurrentNeutralModel(current,TOLERANCE)
    require(before.objects == after.objects,"object identity or hierarchy changed")
    require(not nonfinite_objects(after),"nonfinite coordinates introduced")
    changed_names={i.name for i in before.objects if raw_source(xml,i)!=raw_source(current,i)}
    allowed={name for side in ("L","R") for name in names(side)}
    require(changed_names<=allowed and set(bound_names)<=changed_names,"unrelated object source changed")
    for name,poses in expected_poses.items():
        item=one(after,name,"art-mesh")
        require(experiment._one_named(after.source(item),"b","isVisible").text=="true",name+": editor visibility off")
        forms=experiment._one_named(after.source(item),"carray_list","keyforms")
        require(len(forms)==len(KEYS),name+": missing forms")
        semantics=eye._generic_grid_semantics(after.root,after,item,experiment)
        require(tuple(semantics["keys"][0])==KEYS and len(semantics["access_to_ref"])==len(KEYS),name+": grid mismatch")
        for form,expected in zip(forms,poses):
            local=canvas._float_values(experiment._one_named(form,"float-array","positions"),name)
            observed=after.forward_many(after.transform(item.parent_ref),local)
            require(canvas._maximum_error(observed,expected)<=TOLERANCE,name+": serialized pose differs")
    output=safe._replace_main_xml(data,current)
    a,_,_,_,_=safe._validate_surgical_layout(data)
    b,_,_,_,decoded=safe._validate_surgical_layout(output)
    require(decoded==current,"encoded main.xml differs")
    preserved=safe._compare_entry_preservation(data,a,output,b,main_may_change=True)
    require(preserved.get("all_non_main_entries_byte_identical") is True,"non-main archive member changed")
    require(source.read_bytes()==data and reference.read_bytes()==reference_data,"source/reference changed")
    return output,{"schema":"jade.r21.true-closed-blink.v1","status":"candidate_requires_native_visual_gate","source":str(source),"source_sha256":sha(data),"output_sha256":sha(output),"contour_measurements":curves,"original_alignment_offsets_corrected_px":alignments,"bindings":changes,"closed_zero":"Only original CLOSED_TRUE visible; open opacity zero","open_one":"Only original OPEN_MASTER visible; original geometry","handoff_interval":[0.0,0.12],"skin_sockets":"remain visible and geometrically static","all_unrelated_sources_byte_identical":True,"after_nonfinite":[],"archive":preserved}


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source",type=Path)
    parser.add_argument("--reference",type=Path,required=True)
    parser.add_argument("--assets",type=Path,default=Path("assets/live2d/r21_professional_art"))
    parser.add_argument("--output",type=Path)
    parser.add_argument("--audit",type=Path)
    parser.add_argument("--dry-run",action="store_true")
    args=parser.parse_args();source=args.source.resolve(strict=True)
    if not args.dry_run:
        require(args.output is not None and args.audit is not None,"--output and --audit required")
        require("TEST" in args.output.name and args.output.suffix.lower()==".cmo3","output must be TEST CMO3")
        require(not args.output.exists() and not args.audit.exists(),"output/audit exists; refusing overwrite")
        require(args.output.resolve()!=source,"source/output must differ")
    data,audit=plan(source,args.reference.resolve(strict=True),args.assets.resolve(strict=True))
    if not args.dry_run:
        audit["output"]=str(args.output.resolve());exclusive(args.output,data)
        exclusive(args.audit,(json.dumps(audit,ensure_ascii=False,indent=2)+"\n").encode("utf-8"))
    print(json.dumps(audit,ensure_ascii=False,indent=2));return 0


if __name__=="__main__":
    raise SystemExit(main())
