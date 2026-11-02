#!/usr/bin/env python3
"""Add expressive ear poses and independent rear-hair branches to Jade.

This is a composable, semantic CMO3 transaction.  It intentionally does not
pin one source SHA: a later professional checkpoint is accepted when the
audited Jade object and parameter contracts still match.  The source is never
overwritten and only ``main.xml`` may differ in the output archive.

Ear emotion and ear inertia remain separate axes:

* ``ParamEarPoseL/R``: -1 sad/down, -0.45 angry/back, 0 neutral, +1 alert/up;
* ``ParamEarSwingL/R``: the existing physics destination, retained exactly.

The five existing rear-hair ArtMeshes are not raster-split.  Each receives an
independent -1/0/+1 tip-bend parameter so physics can use deliberately
different delays for centre, inner and outer branches.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Sequence


TOOLS_DIR = Path(__file__).resolve(strict=True).parent
TOLERANCE = 0.001
EAR_PHYSICS_KEYS = (-1.0, 0.0, 1.0)
EAR_POSE_KEYS = (-1.0, -0.45, 0.0, 1.0)
HAIR_KEYS = (-1.0, 0.0, 1.0)
EYE_BRANCHES = {
    "D_JAD_EYE_L_OPEN",
    "D_JAD_EYE_L_CLOSED",
    "D_JAD_EYE_R_OPEN",
    "D_JAD_EYE_R_CLOSED",
}
EAR_TARGETS = {
    "D_JAD_EAR_L_MASTER": {
        "physics": "ParamEarSwingL",
        "pose": "ParamEarPoseL",
        "side": 1.0,
    },
    "D_JAD_EAR_R_MASTER": {
        "physics": "ParamEarSwingR",
        "pose": "ParamEarPoseR",
        "side": -1.0,
    },
}
HAIR_TARGETS = {
    "JAD_HAIR_BACK_C": {
        "parameter": "ParamHairBackC",
        "side": 0.0,
        "amplitude_x": 22.0,
        "amplitude_y": 2.0,
    },
    "JAD_HAIR_BACK_L_INNER": {
        "parameter": "ParamHairBackLInner",
        "side": 1.0,
        "amplitude_x": 27.0,
        "amplitude_y": 4.0,
    },
    "JAD_HAIR_BACK_L_OUTER": {
        "parameter": "ParamHairBackLOuter",
        "side": 1.0,
        "amplitude_x": 34.0,
        "amplitude_y": 6.0,
    },
    "JAD_HAIR_BACK_R_INNER": {
        "parameter": "ParamHairBackRInner",
        "side": -1.0,
        "amplitude_x": 25.0,
        "amplitude_y": 4.5,
    },
    "JAD_HAIR_BACK_R_OUTER": {
        "parameter": "ParamHairBackROuter",
        "side": -1.0,
        "amplitude_x": 32.0,
        "amplitude_y": 6.5,
    },
}
PARAMETERS = {
    "ParamEarPoseL": ("Ear Pose L", "Left ear emotional pose; physics remains independent"),
    "ParamEarPoseR": ("Ear Pose R", "Right ear emotional pose; physics remains independent"),
    "ParamHairBackC": ("Rear Hair Centre", "Independent centre rear-hair follow-through"),
    "ParamHairBackLInner": ("Rear Hair L Inner", "Independent left inner rear-hair follow-through"),
    "ParamHairBackLOuter": ("Rear Hair L Outer", "Independent left outer rear-hair follow-through"),
    "ParamHairBackRInner": ("Rear Hair R Inner", "Independent right inner rear-hair follow-through"),
    "ParamHairBackROuter": ("Rear Hair R Outer", "Independent right outer rear-hair follow-through"),
}


class EarsHairProfessionalError(RuntimeError):
    """Raised when the narrow semantic transaction is not provably safe."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EarsHairProfessionalError(message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _load_modules() -> tuple[Any, ...]:
    sys.path.insert(0, str(TOOLS_DIR))
    import cmo3_create_deformer_experiment as experiment
    import cmo3_face_fx_scaffold as face
    import cmo3_hair_back_functional as hair_back
    import cmo3_head_wrapper_scaffold as scaffold
    import cmo3_reparent_preserve_canvas as canvas
    import cmo3_safe_roundtrip as safe
    import cmo3_secondary_professional as secondary

    return experiment, face, hair_back, scaffold, canvas, safe, secondary


def _object(model: Any, name: str) -> Any:
    matches = [item for item in model.objects if item.name == name]
    _require(len(matches) == 1, f"object {name!r} is not unique")
    return matches[0]


def _identity(item: Any) -> tuple[str, str, str, str, str, str]:
    return (
        item.object_type,
        item.name,
        item.guid_uuid,
        item.guid_ref,
        item.source_ref,
        item.parent_ref,
    )


def _generated_uuid(source_sha: str, role: str) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"jade-cmo3-ears-hair-professional-r04:{source_sha}:{role}",
        )
    )


def _parameter_guid_block(
    ref: str, idx: int, source_sha: str, parameter_id: str
) -> bytes:
    return (
        f'<CParameterGuid uuid="{_generated_uuid(source_sha, "parameter:" + parameter_id)}" '
        f'note="{parameter_id}" xs.id="{ref}" xs.idx="{idx}" />'
    ).encode("ascii")


def _form_guid_block(
    ref: str, idx: int, source_sha: str, role: str
) -> bytes:
    return (
        f'<CFormGuid uuid="{_generated_uuid(source_sha, role)}" '
        f'note="(no debug info)" xs.id="{ref}" xs.idx="{idx}" />'
    ).encode("ascii")


def _binding_keys(root: Any, binding_ref: str, experiment: Any) -> tuple[float, ...]:
    binding = experiment._id_map(root).get(binding_ref)
    _require(binding is not None, f"binding {binding_ref} is unresolved")
    keys = experiment._one_named(binding, "array_list", "keys")
    return tuple(float(node.text or "nan") for node in keys)


def _maximum_displacement(
    first: Sequence[float], second: Sequence[float]
) -> float:
    return max(
        math.hypot(x1 - x0, y1 - y0)
        for x0, y0, x1, y1 in zip(
            first[0::2], first[1::2], second[0::2], second[1::2]
        )
    )


def _ear_emotion_canvas(
    neutral: Sequence[float], pose: float, side: float
) -> tuple[float, ...]:
    """Return a tip-weighted expressive ear pose in canvas coordinates."""
    xs = neutral[0::2]
    ys = neutral[1::2]
    min_y, max_y = min(ys), max(ys)
    height = max_y - min_y
    _require(height > 0.0, "ear neutral canvas is degenerate")
    if abs(pose - 1.0) < 1e-9:  # alert/surprised: up and slightly inward
        tip_dx, tip_dy = -side * 105.0, -175.0
    elif abs(pose + 1.0) < 1e-9:  # sad: relaxed, down and out
        tip_dx, tip_dy = side * 75.0, 125.0
    elif abs(pose + 0.45) < 1e-9:  # angry: pinned back/lateral
        # Stay inside the neutral head cage even when physics is at an endpoint.
        tip_dx, tip_dy = side * 80.0, 8.0
    elif abs(pose) < 1e-9:
        tip_dx, tip_dy = 0.0, 0.0
    else:
        raise EarsHairProfessionalError(f"unsupported ear pose key {pose}")
    result: list[float] = []
    for x, y in zip(xs, ys):
        vertical = (max_y - y) / height
        weight = max(0.0, min(1.0, vertical)) ** 1.45
        # A mild transverse term prevents the cage from moving as a flat slab.
        centre_x = (min(xs) + max(xs)) * 0.5
        horizontal = (x - centre_x) / max(1.0, (max(xs) - min(xs)) * 0.5)
        result.extend(
            (
                x + tip_dx * weight,
                y + tip_dy * weight + side * horizontal * 6.0 * abs(pose) * weight,
            )
        )
    return tuple(result)


def _hair_branch_canvas(
    neutral: Sequence[float], key: float, spec: dict[str, Any]
) -> tuple[float, ...]:
    xs = neutral[0::2]
    ys = neutral[1::2]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width, height = max_x - min_x, max_y - min_y
    _require(width > 0.0 and height > 0.0, "rear-hair branch is degenerate")
    centre_x = (min_x + max_x) * 0.5
    result: list[float] = []
    for x, y in zip(xs, ys):
        vertical = (y - min_y) / height
        # Preserve the upper 10% root zone and progressively bend the tips.
        weight = max(0.0, min(1.0, (vertical - 0.10) / 0.90)) ** 1.65
        horizontal = (x - centre_x) / (width * 0.5)
        dx = float(spec["amplitude_x"]) * key * weight
        dx += 2.5 * key * horizontal * weight
        dy = float(spec["amplitude_y"]) * float(spec["side"]) * key * weight
        dy += 1.5 * abs(key) * (horizontal**2) * weight
        result.extend((x + dx, y + dy))
    return tuple(result)


def _indices(source: Any, canvas: Any, label: str) -> tuple[int, ...]:
    node = canvas._one_direct_named(source, "int-array", "indices")
    values = tuple(int(token) for token in (node.text or "").split())
    _require(len(values) == int(node.get("count", "-1")), f"{label}: index count differs")
    _require(len(values) % 3 == 0, f"{label}: triangle index count differs")
    return values


def _triangle_signs(
    points: Sequence[float], indices: Sequence[int]
) -> tuple[float, ...]:
    pairs = list(zip(points[0::2], points[1::2]))
    signs = []
    for offset in range(0, len(indices), 3):
        a, b, c = (pairs[indices[offset + index]] for index in range(3))
        signs.append(
            (b[0] - a[0]) * (c[1] - a[1])
            - (b[1] - a[1]) * (c[0] - a[0])
        )
    return tuple(signs)


def _ear_roles(name: str) -> list[str]:
    return [
        f"{name}:pose-binding",
        *[
            f"{name}:pose-form:{pose_index}:{physics_index}"
            for pose_index, pose in enumerate(EAR_POSE_KEYS)
            if pose != 0.0
            for physics_index in range(3)
        ],
    ]


def _hair_roles(name: str) -> list[str]:
    return [
        f"{name}:grid",
        f"{name}:binding",
        f"{name}:form:left",
        f"{name}:form:right",
    ]


def _all_roles() -> list[str]:
    roles: list[str] = []
    for parameter in PARAMETERS:
        roles.extend([f"parameter:{parameter}:guid", f"parameter:{parameter}:id"])
    for name in EAR_TARGETS:
        roles.extend(_ear_roles(name))
    for name in HAIR_TARGETS:
        roles.extend(_hair_roles(name))
    return roles


def _patch_ear(
    main: bytes,
    *,
    name: str,
    spec: dict[str, Any],
    slots: dict[str, tuple[str, int]],
    parameter_refs: dict[str, str],
    source_sha: str,
    modules: tuple[Any, ...],
) -> tuple[bytes, dict[str, Any], list[bytes]]:
    experiment, face, hair_back, scaffold, canvas, safe, secondary = modules
    geometry_xml, _ = hair_back._neutral_rotation_mirror(
        main, experiment=experiment, safe=safe
    )
    geometry = canvas.GeometryModel(geometry_xml, TOLERANCE)
    item = _object(geometry, name)
    _require(item.object_type == "warp-deformer", f"{name}: type differs")
    root = experiment._parse_xml(main)
    grid_ref, grid_idx, binding_refs, parameter_guid_refs = secondary._binding_semantics(
        root, geometry, item, experiment
    )
    expected_physics_ref = str(
        secondary._shared_note(root, "CParameterGuid", spec["physics"]).get("xs.id")
    )
    _require(
        len(binding_refs) == 1 and parameter_guid_refs == [expected_physics_ref],
        f"{name}: existing physics binding differs",
    )
    _require(
        _binding_keys(root, binding_refs[0], experiment) == EAR_PHYSICS_KEYS,
        f"{name}: existing physics keys differ",
    )
    source_block = secondary._raw_source(main, geometry, item, experiment)
    keyform_match, forms = secondary._keyforms(source_block, b"CWarpDeformerForm")
    form_values = scaffold._form_values(geometry, canvas, item)
    _require(len(forms) == len(form_values) == 3, f"{name}: expected three physics forms")
    parent_transform = geometry.transform(item.parent_ref)
    physics_canvases = [
        geometry.forward_many(parent_transform, values) for values in form_values
    ]
    neutral_canvas = physics_canvases[1]
    neutral_signs = secondary._warp_cell_signs(
        neutral_canvas,
        geometry.transform(item.guid_ref).columns,
        geometry.transform(item.guid_ref).rows,
    )
    _require(all(abs(value) > TOLERANCE for value in neutral_signs), f"{name}: neutral cell is degenerate")

    pose_binding_ref, pose_binding_idx = slots[f"{name}:pose-binding"]
    all_forms = list(forms)
    additions: list[bytes] = []
    access_and_refs: list[tuple[tuple[int, int], str]] = []
    metrics: dict[str, Any] = {}
    original_refs = [secondary._form_ref(form) for form in forms]
    for pose_index, pose in enumerate(EAR_POSE_KEYS):
        emotion_canvas = _ear_emotion_canvas(neutral_canvas, pose, float(spec["side"]))
        emotion_delta = tuple(a - b for a, b in zip(emotion_canvas, neutral_canvas))
        pose_errors: list[float] = []
        pose_displacements: list[float] = []
        for physics_index, (form, physics_canvas) in enumerate(zip(forms, physics_canvases)):
            if pose == 0.0:
                access_and_refs.append(((physics_index, pose_index), original_refs[physics_index]))
                pose_errors.append(0.0)
                pose_displacements.append(_maximum_displacement(neutral_canvas, physics_canvas))
                continue
            target_canvas = tuple(
                value + delta for value, delta in zip(physics_canvas, emotion_delta)
            )
            local = tuple(
                canvas._float32(value)
                for value in geometry.inverse_many(parent_transform, target_canvas)
            )
            reconstructed = geometry.forward_many(parent_transform, local)
            error = canvas._maximum_error(target_canvas, reconstructed)
            _require(error < TOLERANCE, f"{name}: pose reconstruction exceeds tolerance")
            signs = secondary._warp_cell_signs(
                reconstructed,
                geometry.transform(item.guid_ref).columns,
                geometry.transform(item.guid_ref).rows,
            )
            _require(
                all(a * b > 0.0 for a, b in zip(neutral_signs, signs)),
                f"{name}: pose folds a warp cell",
            )
            role = f"{name}:pose-form:{pose_index}:{physics_index}"
            form_ref, form_idx = slots[role]
            cloned = secondary._clone_form(
                form,
                new_ref=form_ref,
                opacity=None,
                positions=local,
                multiply=None,
                face=face,
                experiment=experiment,
            )
            all_forms.append(cloned)
            additions.append(_form_guid_block(form_ref, form_idx, source_sha, role))
            access_and_refs.append(((physics_index, pose_index), form_ref))
            pose_errors.append(error)
            pose_displacements.append(_maximum_displacement(neutral_canvas, reconstructed))
        metrics[str(pose)] = {
            "semantic": {
                "-1.0": "sad_down",
                "-0.45": "angry_pinned_back",
                "0.0": "neutral",
                "1.0": "alert_surprised_up",
            }[str(pose)],
            "maximum_reconstruction_error_px": max(pose_errors),
            "control_displacement_px": max(pose_displacements),
        }

    source_after = secondary._replace_keyforms(source_block, keyform_match, all_forms)
    current = experiment._replace_exact(main, source_block, source_after, 1, f"{name} ear poses")
    old_grid = experiment._block_by_id(current, "KeyformGridSource", grid_ref)
    new_grid = secondary._grid_block(
        grid_ref=grid_ref,
        grid_idx=grid_idx,
        binding_refs=[binding_refs[0], pose_binding_ref],
        accesses=[access for access, _ref in access_and_refs],
        form_refs=[ref for _access, ref in access_and_refs],
    )
    current = experiment._replace_exact(current, old_grid, new_grid, 1, f"{name} cross-grid")
    additions.append(
        secondary._binding_block(
            grid_ref=grid_ref,
            binding_ref=pose_binding_ref,
            binding_idx=pose_binding_idx,
            parameter_ref=parameter_refs[str(spec["pose"])],
            keys=EAR_POSE_KEYS,
        )
    )
    return current, {
        "physics_parameter": spec["physics"],
        "pose_parameter": spec["pose"],
        "physics_keys": list(EAR_PHYSICS_KEYS),
        "pose_keys": list(EAR_POSE_KEYS),
        "forms_before": 3,
        "forms_after": 12,
        "all_three_original_physics_forms_preserved_at_pose_zero_byte_exact": True,
        "emotion_plus_physics_cross_grid_complete": True,
        "poses": metrics,
    }, additions


def _patch_hair_branch(
    main: bytes,
    *,
    name: str,
    spec: dict[str, Any],
    slots: dict[str, tuple[str, int]],
    parameter_refs: dict[str, str],
    source_sha: str,
    modules: tuple[Any, ...],
) -> tuple[bytes, dict[str, Any], list[bytes]]:
    experiment, face, hair_back, scaffold, canvas, safe, secondary = modules
    geometry_xml, _ = hair_back._neutral_rotation_mirror(
        main, experiment=experiment, safe=safe
    )
    geometry = canvas.GeometryModel(geometry_xml, TOLERANCE)
    item = _object(geometry, name)
    _require(item.object_type == "art-mesh", f"{name}: type differs")
    source_block = secondary._raw_source(main, geometry, item, experiment)
    keyform_match, forms = secondary._keyforms(source_block, b"CArtMeshForm")
    values = scaffold._form_values(geometry, canvas, item)
    _require(len(forms) == len(values) == 1, f"{name}: expected one unbound form")
    source_node = geometry.source(item)
    inline_grid = experiment._one_named(
        source_node, "KeyformGridSource", "keyformGridSource"
    )
    _require(
        inline_grid.get("xs.ref") is None,
        f"{name}: ArtMesh already references a shared grid",
    )
    bindings_node = experiment._one_named(
        inline_grid, "array_list", "keyformBindings"
    )
    on_grid_node = experiment._one_named(
        inline_grid, "array_list", "keyformsOnGrid"
    )
    _require(
        len(bindings_node) == 0 and len(on_grid_node) == 1,
        f"{name}: ArtMesh is already bound",
    )
    neutral_form = forms[0]
    neutral_ref = secondary._form_ref(neutral_form)
    neutral_local = values[0]
    neutral_canvas = geometry.original_canvas(item)
    parent_transform = geometry.transform(item.parent_ref)
    _require(
        canvas._maximum_error(
            neutral_canvas, geometry.forward_many(parent_transform, neutral_local)
        )
        < TOLERANCE,
        f"{name}: neutral ArtMesh reconstruction differs",
    )
    indices = _indices(geometry.source(item), canvas, name)
    neutral_signs = _triangle_signs(neutral_canvas, indices)
    _require(all(abs(value) > 1e-8 for value in neutral_signs), f"{name}: neutral triangle is degenerate")
    pose_forms: list[bytes] = []
    pose_refs: list[str] = []
    errors: dict[str, float] = {}
    displacements: dict[str, float] = {}
    additions: list[bytes] = []
    for key, role_suffix in ((-1.0, "left"), (1.0, "right")):
        target_canvas = _hair_branch_canvas(neutral_canvas, key, spec)
        signs = _triangle_signs(target_canvas, indices)
        _require(
            all(a * b > 0.0 for a, b in zip(neutral_signs, signs)),
            f"{name}: branch pose flips an ArtMesh triangle",
        )
        local = tuple(
            canvas._float32(value)
            for value in geometry.inverse_many(parent_transform, target_canvas)
        )
        reconstructed = geometry.forward_many(parent_transform, local)
        error = canvas._maximum_error(target_canvas, reconstructed)
        _require(error < TOLERANCE, f"{name}: branch reconstruction exceeds tolerance")
        role = f"{name}:form:{role_suffix}"
        form_ref, form_idx = slots[role]
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
        errors[str(key)] = error
        displacements[str(key)] = _maximum_displacement(neutral_canvas, reconstructed)

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
                parameter_ref=parameter_refs[str(spec["parameter"])],
                keys=HAIR_KEYS,
            ),
        ]
    )
    return current, {
        "parameter": spec["parameter"],
        "keys": list(HAIR_KEYS),
        "tip_bend_amplitude_x_px": spec["amplitude_x"],
        "neutral_form_preserved_byte_exact": True,
        "artmesh_indices_and_uvs_preserved": True,
        "triangle_winding_preserved": True,
        "maximum_reconstruction_error_px": max(errors.values()),
        "control_displacement_px": displacements,
    }, additions


def _source_blocks(main: bytes, modules: tuple[Any, ...]) -> dict[str, bytes]:
    experiment, _face, _hair_back, _scaffold, canvas, _safe, secondary = modules
    model = canvas.GeometryModel(main, TOLERANCE)
    return {
        item.name: secondary._raw_source(main, model, item, experiment)
        for item in model.objects
    }


def _plan(source_data: bytes, modules: tuple[Any, ...]) -> tuple[bytes, dict[str, Any]]:
    experiment, _face, _hair_back, _scaffold, canvas, safe, secondary = modules
    archive_before, _entry, _location, _zip, main_before = safe._validate_surgical_layout(source_data)
    model_before = canvas.GeometryModel(main_before, TOLERANCE)
    identities_before = sorted(_identity(item) for item in model_before.objects)
    blocks_before = _source_blocks(main_before, modules)
    required_names = set(EAR_TARGETS) | set(HAIR_TARGETS) | EYE_BRANCHES
    _require(required_names.issubset(blocks_before), "required Jade objects are missing")
    root_before = experiment._parse_xml(main_before)
    shared = root_before.find("shared")
    _require(shared is not None, "shared section is missing")
    existing_parameter_ids = {
        str(node.get("note")) for node in shared if node.tag == "CParameterGuid"
    }
    _require(
        {"ParamEarSwingL", "ParamEarSwingR"}.issubset(existing_parameter_ids),
        "professional ear physics parameters are missing",
    )
    _require(
        not set(PARAMETERS).intersection(existing_parameter_ids),
        "one or more r04 ear/hair parameters already exist",
    )
    source_sha = _sha256(source_data)
    slots = secondary._allocate(root_before, _all_roles())
    parameter_refs: dict[str, str] = {}
    parameter_shared: list[bytes] = []
    parameter_sources: list[bytes] = []
    for parameter_id, (name, description) in PARAMETERS.items():
        guid_ref, guid_idx = slots[f"parameter:{parameter_id}:guid"]
        id_ref, id_idx = slots[f"parameter:{parameter_id}:id"]
        parameter_refs[parameter_id] = guid_ref
        parameter_shared.extend(
            [
                _parameter_guid_block(guid_ref, guid_idx, source_sha, parameter_id),
                secondary._parameter_id_block(id_ref, id_idx, parameter_id),
            ]
        )
        parameter_sources.append(
            secondary._parameter_source(guid_ref, id_ref, name, description)
        )
    current = experiment._append_shared_blocks(main_before, parameter_shared)
    current = secondary._append_parameter_sources(current, parameter_sources)
    current = secondary._append_root_parameter_children(
        current, list(parameter_refs.values()), experiment=experiment
    )

    ear_audit: dict[str, Any] = {}
    hair_audit: dict[str, Any] = {}
    shared_added = len(parameter_shared)
    for name, spec in EAR_TARGETS.items():
        current, ear_audit[name], additions = _patch_ear(
            current,
            name=name,
            spec=spec,
            slots=slots,
            parameter_refs=parameter_refs,
            source_sha=source_sha,
            modules=modules,
        )
        current = experiment._append_shared_blocks(current, additions)
        shared_added += len(additions)
    for name, spec in HAIR_TARGETS.items():
        current, hair_audit[name], additions = _patch_hair_branch(
            current,
            name=name,
            spec=spec,
            slots=slots,
            parameter_refs=parameter_refs,
            source_sha=source_sha,
            modules=modules,
        )
        current = experiment._append_shared_blocks(current, additions)
        shared_added += len(additions)

    root_after = experiment._parse_xml(current)
    model_after = canvas.GeometryModel(current, TOLERANCE)
    identities_after = sorted(_identity(item) for item in model_after.objects)
    _require(identities_after == identities_before, "object identity/hierarchy changed")
    indices = [int(node.get("xs.idx", "-1")) for node in root_after.find("shared")]
    _require(len(indices) == len(set(indices)), "output xs.idx collision")
    hierarchy = secondary._parameter_hierarchy_audit(root_after, experiment)
    blocks_after = _source_blocks(current, modules)
    changed_objects = set(EAR_TARGETS) | set(HAIR_TARGETS)
    for name in blocks_before:
        if name not in changed_objects:
            _require(blocks_after[name] == blocks_before[name], f"non-target source {name!r} changed")
    _require(
        all(blocks_after[name] == blocks_before[name] for name in EYE_BRANCHES),
        "one or more eye OPEN/CLOSED branches changed",
    )
    output_data = safe._replace_main_xml(source_data, current)
    archive_after, _entry2, _location2, _zip2, decoded_after = safe._validate_surgical_layout(output_data)
    _require(decoded_after == current, "output main.xml differs from plan")
    preservation = safe._compare_entry_preservation(
        source_data,
        archive_before,
        output_data,
        archive_after,
        main_may_change=True,
    )
    _require(
        preservation.get("all_non_main_entries_byte_identical") is True,
        "non-main archive entry changed",
    )
    return output_data, {
        "schema": "jade.cmo3.ears-hair-professional-r04.v1",
        "status": "ok",
        "source_sha256": source_sha,
        "source_bytes": len(source_data),
        "output_sha256": _sha256(output_data),
        "output_bytes": len(output_data),
        "parameters_added": list(PARAMETERS),
        "expression_contract": {
            "surprised": {"ParamEarPoseL": 1.0, "ParamEarPoseR": 1.0},
            "sad": {"ParamEarPoseL": -1.0, "ParamEarPoseR": -1.0},
            "angry": {"ParamEarPoseL": -0.45, "ParamEarPoseR": -0.45},
            "neutral": {"ParamEarPoseL": 0.0, "ParamEarPoseR": 0.0},
        },
        "physics_destination_contract": [
            "ParamEarSwingL",
            "ParamEarSwingR",
            *[str(spec["parameter"]) for spec in HAIR_TARGETS.values()],
        ],
        "ears": ear_audit,
        "rear_hair": {
            "strategy": "five_existing_artmeshes_independently_bound_no_raster_split",
            "master_global_motion_retained": ["ParamHairSide", "ParamHairBack"],
            "branches": hair_audit,
        },
        "eye_open_closed_source_blocks_preserved_byte_exact": True,
        "all_non_target_object_sources_preserved_byte_exact": True,
        "object_identity_and_hierarchy_preserved": True,
        "artwork_uvs_indices_and_topology_preserved": True,
        "parameter_hierarchy": hierarchy,
        "shared_definitions_added": shared_added,
        "archive": preservation,
        "cubism_5_2_03_load_save_required": True,
    }


def _write_exclusive(path: Path, payload: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    source = args.source.resolve(strict=True)
    output = args.output.resolve(strict=False)
    _require(source.suffix.lower() == ".cmo3" and output.suffix.lower() == ".cmo3", "source/output must be CMO3")
    _require(source != output, "source and output must differ")
    _require(not output.exists(), "output exists; refusing overwrite")
    _require(output.parent.is_dir(), "output directory does not exist")
    source_data = source.read_bytes()
    output_data, audit = _plan(source_data, _load_modules())
    audit.update(
        {
            "source": str(source),
            "output": str(output),
            "dry_run": bool(args.dry_run),
            "output_written": False,
        }
    )
    _require(source.read_bytes() == source_data, "source changed during planning")
    if args.dry_run:
        audit["verdict"] = "PASS_DRY_RUN__NO_FILE_WRITTEN"
        print(json.dumps(audit, ensure_ascii=False, sort_keys=True))
        return 0
    audit_path = output.with_suffix(".audit.json")
    _require(not audit_path.exists(), "audit exists; refusing overwrite")
    try:
        _write_exclusive(output, output_data)
        audit["output_written"] = True
        audit["verdict"] = "PASS_PRE_CUBISM__LOAD_SAVE_5_2_03_REQUIRED"
        _write_exclusive(
            audit_path,
            (
                json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n"
            ).encode("utf-8"),
        )
    except Exception:
        output.unlink(missing_ok=True)
        audit_path.unlink(missing_ok=True)
        raise
    print(json.dumps(audit, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EarsHairProfessionalError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
