#!/usr/bin/env python3
"""Build Jade r13 hair keyforms from the validated r12 Cubism source.

The transaction is deliberately narrow:

* amplify the existing front/rear/ahoge hair keyforms around byte-exact neutral
  forms, in local space, so no inverse of an extreme parent deformation is
  required;
* keep the five existing rear ArtMeshes and make their already-independent
  outputs readable at stream scale;
* add independent -1/0/+1 follow-through controls to the two outer bangs and
  the two temple locks, breaking the monolithic front-hair motion;
* preserve every non-hair object source, the hierarchy, topology, UVs, eyes,
  ears and artwork.

The source is never overwritten and Cubism 5.2.03 still has to load/save the
candidate before the final runtime export.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Sequence


TOOLS_DIR = Path(__file__).resolve(strict=True).parent
TOLERANCE = 0.001
KEYS = (-1.0, 0.0, 1.0)
REVISION = "r13"
FRONT_PHASE_POLICY = "outer bangs and temples independently bound"

# These factors were chosen from the r12 CubismCore endpoint audit.  They make
# the motion readable after VTube Studio's global PhysicsStrength=65 while
# retaining the exact professional r12 neutral drawing.
EXISTING_TARGETS: dict[str, dict[str, Any]] = {
    "D_JAD_HAIR_FRONT_MASTER": {
        "parameters": ("ParamHairFront",),
        "form_tag": b"CWarpDeformerForm",
        "scale_x": 2.75,
        "scale_y": 1.50,
        "role": "front_shared_base",
    },
    "D_JAD_HAIR_BACK_MASTER": {
        "parameters": ("ParamHairSide", "ParamHairBack"),
        "form_tag": b"CWarpDeformerForm",
        "scale_x": 3.20,
        "scale_y": 2.50,
        "role": "rear_shared_base",
    },
    "JAD_HAIR_AHOGE": {
        "parameters": ("ParamAhogeSwing",),
        "form_tag": b"CArtMeshForm",
        "scale_x": 4.00,
        "scale_y": 2.50,
        "role": "ahoge_independent",
    },
    "JAD_HAIR_BACK_C": {
        "parameters": ("ParamHairBackC",),
        "form_tag": b"CArtMeshForm",
        "scale_x": 2.70,
        "scale_y": 2.00,
        "role": "rear_centre",
    },
    "JAD_HAIR_BACK_L_INNER": {
        "parameters": ("ParamHairBackLInner",),
        "form_tag": b"CArtMeshForm",
        "scale_x": 2.75,
        "scale_y": 2.00,
        "role": "rear_left_inner",
    },
    "JAD_HAIR_BACK_L_OUTER": {
        "parameters": ("ParamHairBackLOuter",),
        "form_tag": b"CArtMeshForm",
        "scale_x": 2.80,
        "scale_y": 2.20,
        "role": "rear_left_outer",
    },
    "JAD_HAIR_BACK_R_INNER": {
        "parameters": ("ParamHairBackRInner",),
        "form_tag": b"CArtMeshForm",
        "scale_x": 2.75,
        "scale_y": 2.00,
        "role": "rear_right_inner",
    },
    "JAD_HAIR_BACK_R_OUTER": {
        "parameters": ("ParamHairBackROuter",),
        "form_tag": b"CArtMeshForm",
        "scale_x": 2.80,
        "scale_y": 2.20,
        "role": "rear_right_outer",
    },
}

# Independent front controls.  The centre and inner fringe keep only the
# prompt shared response; temples and outer bangs get delayed child motion.
NEW_FRONT_TARGETS: dict[str, dict[str, Any]] = {
    "JAD_HAIR_BANG_L_OUTER": {
        "parameter": "ParamHairBangLOuter",
        "display_name": "Hair Bang L Outer",
        "description": "Independent left outer-bang follow-through",
        "amplitude_x": 38.0,
        "lift_y": 5.0,
        "root_fraction": 0.22,
        "exponent": 1.55,
    },
    "JAD_HAIR_BANG_R_OUTER": {
        "parameter": "ParamHairBangROuter",
        "display_name": "Hair Bang R Outer",
        "description": "Independent right outer-bang follow-through",
        "amplitude_x": 36.0,
        "lift_y": 5.0,
        "root_fraction": 0.22,
        "exponent": 1.55,
    },
    "JAD_HAIR_TEMPLE_L": {
        "parameter": "ParamHairTempleL",
        "display_name": "Hair Temple L",
        "description": "Independent left temple-lock follow-through",
        "amplitude_x": 52.0,
        "lift_y": 7.0,
        "root_fraction": 0.18,
        "exponent": 1.45,
    },
    "JAD_HAIR_TEMPLE_R": {
        "parameter": "ParamHairTempleR",
        "display_name": "Hair Temple R",
        "description": "Independent right temple-lock follow-through",
        "amplitude_x": 49.0,
        "lift_y": 7.0,
        "root_fraction": 0.18,
        "exponent": 1.45,
    },
}

PROTECTED_EYE_OBJECTS = {
    "D_JAD_EYE_L_OPEN",
    "D_JAD_EYE_L_CLOSED",
    "D_JAD_EYE_R_OPEN",
    "D_JAD_EYE_R_CLOSED",
}
PROTECTED_EAR_OBJECTS = {"D_JAD_EAR_L_MASTER", "D_JAD_EAR_R_MASTER"}


class HairMotionProfessionalError(RuntimeError):
    """Raised when the r12 semantic contract is not provably preserved."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise HairMotionProfessionalError(message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _load_modules() -> tuple[Any, ...]:
    sys.path.insert(0, str(TOOLS_DIR))
    import cmo3_create_deformer_experiment as experiment
    import cmo3_ear_lateral_motion_professional as lateral
    import cmo3_ears_hair_professional_r04 as r04
    import cmo3_face_fx_scaffold as face
    import cmo3_hair_back_functional as hair_back
    import cmo3_head_wrapper_scaffold as scaffold
    import cmo3_reparent_preserve_canvas as canvas
    import cmo3_safe_roundtrip as safe
    import cmo3_secondary_professional as secondary

    return experiment, lateral, r04, face, hair_back, scaffold, canvas, safe, secondary


def _generated_uuid(source_sha: str, role: str) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"jade-cmo3-hair-motion-professional-{REVISION}:{source_sha}:{role}",
        )
    )


def _parameter_guid_block(
    ref: str, idx: int, source_sha: str, parameter_id: str
) -> bytes:
    return (
        f'<CParameterGuid uuid="{_generated_uuid(source_sha, "parameter:" + parameter_id)}" '
        f'note="{parameter_id}" xs.id="{ref}" xs.idx="{idx}" />'
    ).encode("ascii")


def _form_guid_block(ref: str, idx: int, source_sha: str, role: str) -> bytes:
    return (
        f'<CFormGuid uuid="{_generated_uuid(source_sha, role)}" '
        f'note="(no debug info)" xs.id="{ref}" xs.idx="{idx}" />'
    ).encode("ascii")


def _identity(item: Any) -> tuple[str, str, str, str, str, str]:
    return (
        item.object_type,
        item.name,
        item.guid_uuid,
        item.guid_ref,
        item.source_ref,
        item.parent_ref,
    )


def _source_blocks(main: bytes, modules: tuple[Any, ...]) -> dict[str, bytes]:
    experiment, _lateral, _r04, _face, _hair, _scaffold, canvas, _safe, secondary = modules
    model = canvas.GeometryModel(main, TOLERANCE)
    return {
        item.name: secondary._raw_source(main, model, item, experiment)
        for item in model.objects
    }


def _parameter_ref(root: Any, parameter_id: str, secondary: Any) -> str:
    return str(secondary._shared_note(root, "CParameterGuid", parameter_id).get("xs.id"))


def _maximum_displacement(
    neutral: Sequence[float], target: Sequence[float]
) -> float:
    return max(
        math.hypot(x1 - x0, y1 - y0)
        for x0, y0, x1, y1 in zip(
            neutral[0::2], neutral[1::2], target[0::2], target[1::2]
        )
    )


def _scaled_local(
    neutral: Sequence[float], values: Sequence[float], scale_x: float, scale_y: float, float32: Any
) -> tuple[float, ...]:
    _require(len(neutral) == len(values), "local form sizes differ")
    result: list[float] = []
    for nx, ny, x, y in zip(
        neutral[0::2], neutral[1::2], values[0::2], values[1::2]
    ):
        result.extend(
            (
                float32(nx + (x - nx) * scale_x),
                float32(ny + (y - ny) * scale_y),
            )
        )
    return tuple(result)


def _patch_existing_target(
    main: bytes,
    *,
    name: str,
    spec: dict[str, Any],
    modules: tuple[Any, ...],
) -> tuple[bytes, dict[str, Any]]:
    experiment, lateral, r04, face, hair, scaffold, canvas, safe, secondary = modules
    root = experiment._parse_xml(main)
    geometry_xml, _neutralized = hair._neutral_rotation_mirror(
        main, experiment=experiment, safe=safe
    )
    model = canvas.GeometryModel(geometry_xml, TOLERANCE)
    item = r04._object(model, name)
    expected_type = "warp-deformer" if spec["form_tag"] == b"CWarpDeformerForm" else "art-mesh"
    _require(item.object_type == expected_type, f"{name}: type differs")

    grid_ref, _grid_idx, binding_refs, parameter_refs = secondary._binding_semantics(
        root, model, item, experiment
    )
    expected_refs = [_parameter_ref(root, parameter, secondary) for parameter in spec["parameters"]]
    _require(
        set(parameter_refs) == set(expected_refs) and len(parameter_refs) == len(expected_refs),
        f"{name}: parameter binding set differs",
    )
    keys_by_binding = {
        ref: r04._binding_keys(root, ref, experiment) for ref in binding_refs
    }
    _require(
        all(keys_by_binding[ref] == KEYS for ref in binding_refs),
        f"{name}: expected -1/0/+1 bindings",
    )

    source_block = secondary._raw_source(main, model, item, experiment)
    keyform_match, forms = secondary._keyforms(source_block, spec["form_tag"])
    form_values = scaffold._form_values(model, canvas, item)
    _require(len(forms) == len(form_values), f"{name}: form/value count differs")
    forms_by_ref = {
        secondary._form_ref(form): (form, values)
        for form, values in zip(forms, form_values)
    }
    _require(len(forms_by_ref) == len(forms), f"{name}: duplicate form GUID")
    access_to_ref = lateral._grid_mapping(root, grid_ref, binding_refs, experiment)
    _require(
        set(access_to_ref.values()) == set(forms_by_ref),
        f"{name}: grid/form GUID set differs",
    )
    neutral_access = tuple(keys_by_binding[ref].index(0.0) for ref in binding_refs)
    neutral_ref = access_to_ref[neutral_access]
    neutral_form, neutral_local = forms_by_ref[neutral_ref]
    parent_transform = model.transform(item.parent_ref)
    neutral_canvas = model.forward_many(parent_transform, neutral_local)
    neutral_cell_signs: tuple[float, ...] | None = None
    if item.object_type == "warp-deformer":
        transform = model.transform(item.guid_ref)
        neutral_cell_signs = secondary._warp_cell_signs(
            neutral_canvas, transform.columns, transform.rows
        )
        _require(
            all(abs(value) > TOLERANCE for value in neutral_cell_signs),
            f"{name}: neutral warp cell is degenerate",
        )

    replacements: dict[str, bytes] = {}
    displacements: dict[str, float] = {}
    minimum_area_ratio = 1.0
    source_node = model.source(item)
    if item.object_type == "art-mesh":
        indices = r04._indices(source_node, canvas, name)
        neutral_triangle_signs = r04._triangle_signs(neutral_canvas, indices)
        _require(
            all(abs(value) > 1e-8 for value in neutral_triangle_signs),
            f"{name}: neutral triangle is degenerate",
        )
    else:
        indices = ()
        neutral_triangle_signs = ()

    for access, ref in access_to_ref.items():
        form, values = forms_by_ref[ref]
        if access == neutral_access:
            replacements[ref] = form
            displacements[str(access)] = 0.0
            continue
        scaled = _scaled_local(
            neutral_local,
            values,
            float(spec["scale_x"]),
            float(spec["scale_y"]),
            canvas._float32,
        )
        target_canvas = model.forward_many(parent_transform, scaled)
        if item.object_type == "warp-deformer":
            target_signs = secondary._warp_cell_signs(
                target_canvas, transform.columns, transform.rows
            )
            _require(
                all(a * b > 0.0 for a, b in zip(neutral_cell_signs or (), target_signs)),
                f"{name}: scaled form folds a warp cell",
            )
            ratios = [
                abs(b) / abs(a)
                for a, b in zip(neutral_cell_signs or (), target_signs)
            ]
        else:
            target_signs = r04._triangle_signs(target_canvas, indices)
            _require(
                all(a * b > 0.0 for a, b in zip(neutral_triangle_signs, target_signs)),
                f"{name}: scaled form flips an ArtMesh triangle",
            )
            ratios = [
                abs(b) / abs(a)
                for a, b in zip(neutral_triangle_signs, target_signs)
            ]
        minimum_area_ratio = min(minimum_area_ratio, min(ratios))
        replacements[ref] = secondary._clone_form(
            form,
            new_ref=ref,
            opacity=None,
            positions=scaled,
            multiply=None,
            face=face,
            experiment=experiment,
        )
        displacements[str(access)] = _maximum_displacement(neutral_canvas, target_canvas)

    rebuilt = [replacements[secondary._form_ref(form)] for form in forms]
    source_after = secondary._replace_keyforms(source_block, keyform_match, rebuilt)
    current = experiment._replace_exact(main, source_block, source_after, 1, f"amplify {name}")
    return current, {
        "role": spec["role"],
        "parameters": list(spec["parameters"]),
        "scale_x": spec["scale_x"],
        "scale_y": spec["scale_y"],
        "forms_total": len(forms),
        "forms_rebuilt": len(forms) - 1,
        "neutral_form_ref": neutral_ref,
        "neutral_form_preserved_byte_exact": replacements[neutral_ref] == neutral_form,
        "local_space_delta_scaling": True,
        "maximum_control_displacement_px": max(displacements.values()),
        "minimum_signed_area_ratio_vs_neutral": minimum_area_ratio,
        "control_displacements_px": displacements,
    }


def _front_canvas(
    neutral: Sequence[float], key: float, spec: dict[str, Any]
) -> tuple[tuple[float, ...], dict[str, Any]]:
    xs = tuple(neutral[0::2])
    ys = tuple(neutral[1::2])
    min_y, max_y = min(ys), max(ys)
    height = max_y - min_y
    _require(height > TOLERANCE, "front lock is vertically degenerate")
    root_fraction = float(spec["root_fraction"])
    exponent = float(spec["exponent"])
    weights: list[float] = []
    result: list[float] = []
    for x, y in zip(xs, ys):
        vertical = (y - min_y) / height
        progress = max(0.0, min(1.0, (vertical - root_fraction) / (1.0 - root_fraction)))
        weight = progress**exponent
        weights.append(weight)
        result.extend(
            (
                x + float(spec["amplitude_x"]) * key * weight,
                y - float(spec["lift_y"]) * abs(key) * weight,
            )
        )
    return tuple(result), {
        "fixed_root_fraction": root_fraction,
        "weight_exponent": exponent,
        "fixed_vertices": sum(weight == 0.0 for weight in weights),
        "full_weight_vertices": sum(weight > 0.999999 for weight in weights),
        "weight_minimum": min(weights),
        "weight_maximum": max(weights),
    }


def _bind_front_target(
    main: bytes,
    *,
    name: str,
    spec: dict[str, Any],
    slots: dict[str, tuple[str, int]],
    parameter_ref: str,
    source_sha: str,
    modules: tuple[Any, ...],
) -> tuple[bytes, dict[str, Any], list[bytes]]:
    experiment, _lateral, r04, face, hair, scaffold, canvas, safe, secondary = modules
    geometry_xml, _neutralized = hair._neutral_rotation_mirror(
        main, experiment=experiment, safe=safe
    )
    model = canvas.GeometryModel(geometry_xml, TOLERANCE)
    item = r04._object(model, name)
    _require(item.object_type == "art-mesh", f"{name}: type differs")
    source_block = secondary._raw_source(main, model, item, experiment)
    keyform_match, forms = secondary._keyforms(source_block, b"CArtMeshForm")
    values = scaffold._form_values(model, canvas, item)
    _require(len(forms) == len(values) == 1, f"{name}: expected one unbound form")
    inline_grid = experiment._one_named(
        model.source(item), "KeyformGridSource", "keyformGridSource"
    )
    _require(inline_grid.get("xs.ref") is None, f"{name}: already uses a shared grid")
    bindings = experiment._one_named(inline_grid, "array_list", "keyformBindings")
    on_grid = experiment._one_named(inline_grid, "array_list", "keyformsOnGrid")
    _require(len(bindings) == 0 and len(on_grid) == 1, f"{name}: already bound")

    neutral_form = forms[0]
    neutral_ref = secondary._form_ref(neutral_form)
    neutral_local = values[0]
    parent_transform = model.transform(item.parent_ref)
    neutral_canvas = model.forward_many(parent_transform, neutral_local)
    indices = r04._indices(model.source(item), canvas, name)
    neutral_signs = r04._triangle_signs(neutral_canvas, indices)
    _require(
        all(abs(value) > 1e-8 for value in neutral_signs),
        f"{name}: neutral triangle is degenerate",
    )

    pose_forms: list[bytes] = []
    pose_refs: list[str] = []
    additions: list[bytes] = []
    displacements: dict[str, float] = {}
    reconstruction_errors: dict[str, float] = {}
    minimum_area_ratio = 1.0
    weighting: dict[str, Any] | None = None
    for key, suffix in ((-1.0, "negative"), (1.0, "positive")):
        target_canvas, weighting = _front_canvas(neutral_canvas, key, spec)
        target_signs = r04._triangle_signs(target_canvas, indices)
        _require(
            all(a * b > 0.0 for a, b in zip(neutral_signs, target_signs)),
            f"{name}: new pose flips an ArtMesh triangle",
        )
        minimum_area_ratio = min(
            minimum_area_ratio,
            min(abs(b) / abs(a) for a, b in zip(neutral_signs, target_signs)),
        )
        local = tuple(
            canvas._float32(value)
            for value in model.inverse_many(parent_transform, target_canvas)
        )
        reconstructed = model.forward_many(parent_transform, local)
        error = canvas._maximum_error(target_canvas, reconstructed)
        _require(error < TOLERANCE, f"{name}: reconstruction exceeds tolerance")
        form_ref, form_idx = slots[f"{name}:form:{suffix}"]
        role = f"{name}:form:{suffix}"
        pose_forms.append(
            secondary._clone_form(
                neutral_form,
                new_ref=form_ref,
                opacity=None,
                positions=local,
                multiply=None,
                face=face,
                experiment=experiment,
            )
        )
        pose_refs.append(form_ref)
        additions.append(_form_guid_block(form_ref, form_idx, source_sha, role))
        displacements[str(key)] = _maximum_displacement(neutral_canvas, reconstructed)
        reconstruction_errors[str(key)] = error

    grid_ref, grid_idx = slots[f"{name}:grid"]
    binding_ref, binding_idx = slots[f"{name}:binding"]
    source_after = secondary._replace_inline_grid(source_block, grid_ref)
    match_after, _ = secondary._keyforms(source_after, b"CArtMeshForm")
    source_after = secondary._replace_keyforms(
        source_after, match_after, [pose_forms[0], neutral_form, pose_forms[1]]
    )
    current = experiment._replace_exact(main, source_block, source_after, 1, f"bind {name}")
    additions.extend(
        [
            secondary._grid_block(
                grid_ref=grid_ref,
                grid_idx=grid_idx,
                binding_refs=[binding_ref],
                accesses=[(0,), (1,), (2,)],
                form_refs=[pose_refs[0], neutral_ref, pose_refs[1]],
            ),
            secondary._binding_block(
                grid_ref=grid_ref,
                binding_ref=binding_ref,
                binding_idx=binding_idx,
                parameter_ref=parameter_ref,
                keys=KEYS,
            ),
        ]
    )
    return current, {
        "parameter": spec["parameter"],
        "keys": list(KEYS),
        "tip_amplitude_x_px": spec["amplitude_x"],
        "tip_lift_y_px": spec["lift_y"],
        "neutral_form_preserved_byte_exact": True,
        "topology_and_uvs_preserved": True,
        "triangle_winding_preserved": True,
        "minimum_signed_area_ratio_vs_neutral": minimum_area_ratio,
        "maximum_reconstruction_error_px": max(reconstruction_errors.values()),
        "control_displacements_px": displacements,
        "weighting": weighting,
    }, additions


def _roles() -> list[str]:
    roles: list[str] = []
    for spec in NEW_FRONT_TARGETS.values():
        parameter = str(spec["parameter"])
        roles.extend([f"parameter:{parameter}:guid", f"parameter:{parameter}:id"])
    for name in NEW_FRONT_TARGETS:
        roles.extend(
            [
                f"{name}:grid",
                f"{name}:binding",
                f"{name}:form:negative",
                f"{name}:form:positive",
            ]
        )
    return roles


def build(source: Path, output: Path, audit_path: Path) -> dict[str, Any]:
    modules = _load_modules()
    experiment, _lateral, r04, _face, _hair, _scaffold, canvas, safe, secondary = modules
    source_data = source.read_bytes()
    archive_before, _entry, _location, _zip, main_before = safe._validate_surgical_layout(source_data)
    model_before = canvas.GeometryModel(main_before, TOLERANCE)
    identities_before = sorted(_identity(item) for item in model_before.objects)
    blocks_before = _source_blocks(main_before, modules)
    required = set(EXISTING_TARGETS) | set(NEW_FRONT_TARGETS) | PROTECTED_EYE_OBJECTS | PROTECTED_EAR_OBJECTS
    _require(
        required.issubset(blocks_before),
        f"one or more {REVISION} contract objects are missing",
    )
    root_before = experiment._parse_xml(main_before)
    shared = root_before.find("shared")
    _require(shared is not None, "shared section is missing")
    existing_parameters = {
        str(node.get("note")) for node in shared if node.tag == "CParameterGuid"
    }
    expected_existing = {
        parameter
        for spec in EXISTING_TARGETS.values()
        for parameter in spec["parameters"]
    }
    new_parameters = {str(spec["parameter"]) for spec in NEW_FRONT_TARGETS.values()}
    _require(expected_existing.issubset(existing_parameters), "r12 hair parameters are missing")
    _require(
        not new_parameters.intersection(existing_parameters),
        f"one or more {REVISION} front parameters already exist",
    )

    source_sha = _sha256(source_data)
    slots = secondary._allocate(root_before, _roles())
    parameter_refs: dict[str, str] = {}
    parameter_shared: list[bytes] = []
    parameter_sources: list[bytes] = []
    for spec in NEW_FRONT_TARGETS.values():
        parameter = str(spec["parameter"])
        guid_ref, guid_idx = slots[f"parameter:{parameter}:guid"]
        id_ref, id_idx = slots[f"parameter:{parameter}:id"]
        parameter_refs[parameter] = guid_ref
        parameter_shared.extend(
            [
                _parameter_guid_block(guid_ref, guid_idx, source_sha, parameter),
                secondary._parameter_id_block(id_ref, id_idx, parameter),
            ]
        )
        parameter_sources.append(
            secondary._parameter_source(
                guid_ref,
                id_ref,
                str(spec["display_name"]),
                str(spec["description"]),
            )
        )

    current = main_before
    existing_audit: dict[str, Any] = {}
    for name, spec in EXISTING_TARGETS.items():
        current, existing_audit[name] = _patch_existing_target(
            current, name=name, spec=spec, modules=modules
        )

    current = experiment._append_shared_blocks(current, parameter_shared)
    current = secondary._append_parameter_sources(current, parameter_sources)
    current = secondary._append_root_parameter_children(
        current, list(parameter_refs.values()), experiment=experiment
    )

    front_audit: dict[str, Any] = {}
    shared_added = len(parameter_shared)
    for name, spec in NEW_FRONT_TARGETS.items():
        current, front_audit[name], additions = _bind_front_target(
            current,
            name=name,
            spec=spec,
            slots=slots,
            parameter_ref=parameter_refs[str(spec["parameter"])],
            source_sha=source_sha,
            modules=modules,
        )
        current = experiment._append_shared_blocks(current, additions)
        shared_added += len(additions)

    root_after = experiment._parse_xml(current)
    model_after = canvas.GeometryModel(current, TOLERANCE)
    identities_after = sorted(_identity(item) for item in model_after.objects)
    _require(identities_after == identities_before, "object identity or hierarchy changed")
    indices = [int(node.get("xs.idx", "-1")) for node in root_after.find("shared")]
    _require(len(indices) == len(set(indices)), "output xs.idx collision")
    hierarchy = secondary._parameter_hierarchy_audit(root_after, experiment)

    blocks_after = _source_blocks(current, modules)
    changed_objects = set(EXISTING_TARGETS) | set(NEW_FRONT_TARGETS)
    for name, block in blocks_before.items():
        if name not in changed_objects:
            _require(blocks_after[name] == block, f"non-target source {name!r} changed")
    _require(
        all(blocks_after[name] == blocks_before[name] for name in PROTECTED_EYE_OBJECTS),
        "eye source changed",
    )
    _require(
        all(blocks_after[name] == blocks_before[name] for name in PROTECTED_EAR_OBJECTS),
        "ear source changed",
    )

    output_data = safe._replace_main_xml(source_data, current)
    archive_after, _e2, _l2, _z2, decoded_after = safe._validate_surgical_layout(output_data)
    _require(decoded_after == current, "encoded main.xml differs from plan")
    preservation = safe._compare_entry_preservation(
        source_data,
        archive_before,
        output_data,
        archive_after,
        main_may_change=True,
    )
    _require(
        preservation.get("all_non_main_entries_byte_identical") is True,
        "non-main CAFF member changed",
    )

    audit = {
        "schema": f"jade.cmo3.hair-motion-professional-{REVISION}.v1",
        "status": "candidate",
        "source": str(source),
        "source_sha256": source_sha,
        "output": str(output),
        "output_sha256": _sha256(output_data),
        "policy": {
            "surprise_ears": "neutral_expression_only; ear rig untouched",
            "neutral_forms": "byte-exact",
            "existing_forms": "local-space delta scaling around neutral",
            "front_phase_separation": FRONT_PHASE_POLICY,
            "eyes_ears_artwork": "source blocks byte-exact",
            "source_r12_never_overwritten": True,
        },
        "existing_hair": existing_audit,
        "new_front_controls": front_audit,
        "parameters_added": sorted(new_parameters),
        "physics_destinations_required": sorted(new_parameters),
        "shared_definitions_added": shared_added,
        "object_identity_and_hierarchy_preserved": True,
        "all_non_target_sources_preserved_byte_exact": True,
        "eye_sources_preserved_byte_exact": True,
        "ear_sources_preserved_byte_exact": True,
        "parameter_hierarchy": hierarchy,
        "archive": preservation,
        "cubism_5_2_03_load_save_required": True,
    }

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    descriptor = os.open(output, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(output_data)
            handle.flush()
            os.fsync(handle.fileno())
        descriptor = os.open(audit_path, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", closefd=True) as handle:
            json.dump(audit, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except Exception:
        output.unlink(missing_ok=True)
        audit_path.unlink(missing_ok=True)
        raise
    return audit


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("audit", type=Path)
    args = parser.parse_args(list(argv) if argv is not None else None)
    source = args.source.resolve(strict=True)
    output = args.output.resolve(strict=False)
    audit = args.audit.resolve(strict=False)
    _require(source != output, "source/output must differ")
    _require(not output.exists(), "output exists; refusing overwrite")
    _require(not audit.exists(), "audit exists; refusing overwrite")
    _require(output.parent.is_dir() and audit.parent.is_dir(), "output parent is missing")
    result = build(source, output, audit)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HairMotionProfessionalError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
