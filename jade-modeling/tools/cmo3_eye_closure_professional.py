#!/usr/bin/env python3
"""Shorten and align Jade's OPEN/CLOSED eye transition near EyeOpen=0.

The transaction is semantic and composable: it accepts any later Jade CMO3
checkpoint that still exposes the four audited OPEN/CLOSED deformers and their
EyeOpen x EyeSmile grids.  Only those four deformer sources, their existing
grids, and their existing EyeOpen bindings are changed.  ArtMeshes, topology,
object identities, hierarchy, neutral forms, textures, and all unrelated
parameters are preserved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Sequence


TOOLS_DIR = Path(__file__).resolve(strict=True).parent
TOLERANCE = 0.001
TARGETS = {
    "D_JAD_EYE_L_OPEN": ("ParamEyeLOpen", "ParamEyeLSmile", "open"),
    "D_JAD_EYE_L_CLOSED": ("ParamEyeLOpen", "ParamEyeLSmile", "closed"),
    "D_JAD_EYE_R_OPEN": ("ParamEyeROpen", "ParamEyeRSmile", "open"),
    "D_JAD_EYE_R_CLOSED": ("ParamEyeROpen", "ParamEyeRSmile", "closed"),
}
# Keep the gaze deformers geometry-only.  Putting the EyeOpen opacity mask on
# these parents makes CubismCore export their children (iris/pupil) at zero
# opacity even at EyeOpen=1.  Mask the coloured ArtMeshes directly instead.
GAZE_MASK_TARGETS: dict[str, str] = {}
WHITE_MASK_TARGETS = {
    "JAD_EYE_L_IRIS": "ParamEyeLOpen",
    "JAD_EYE_L_PUPIL": "ParamEyeLOpen",
    "JAD_EYE_L_WHITE": "ParamEyeLOpen",
    "JAD_EYE_R_IRIS": "ParamEyeROpen",
    "JAD_EYE_R_PUPIL": "ParamEyeROpen",
    "JAD_EYE_R_WHITE": "ParamEyeROpen",
}
MUTATED_WARPS = set(TARGETS) | set(GAZE_MASK_TARGETS)
MUTATED_ARTMESHES = set(WHITE_MASK_TARGETS)
OLD_OPEN_KEYS = (0.0, 0.5, 1.0)
SMILE_KEYS = (0.0, 0.5, 1.0)
NEW_OPEN_KEYS = (0.0, 0.02, 0.06, 0.1, 0.14, 0.16, 0.18, 0.2, 0.5, 1.0)
ADDED_OPEN_KEYS = (0.02, 0.06, 0.1, 0.14, 0.16, 0.18, 0.2)
# Iris/pupil/white now have an independent mask.  The OPEN lid/lash can thus
# remain continuous at low EyeOpen values; only the final, geometrically close
# .00..10 interval crossfades to the dedicated CLOSED lash artwork.
OPEN_TRANSITION_OPACITY = (0.0, 0.0, 0.0, 0.10, 0.35, 0.35, 0.65, 0.80, 1.0, 1.0)
CLOSED_TRANSITION_OPACITY = (1.0, 1.0, 1.0, 0.90, 0.65, 0.65, 0.35, 0.20, 0.0, 0.0)
COLOR_MASK_KEYS = (0.0, 0.1, 0.16, 0.2, 0.22, 0.25, 0.3, 1.0)
COLOR_MASK_OPACITY = (0.0, 0.0, 0.0, 0.0, 0.0, 0.40, 1.0, 1.0)


class EyeClosureProfessionalError(RuntimeError):
    """Raised when the eye patch cannot be proved narrow and safe."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EyeClosureProfessionalError(message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _load_modules() -> tuple[Any, ...]:
    sys.path.insert(0, str(TOOLS_DIR))
    import cmo3_create_deformer_experiment as experiment
    import cmo3_face_fx_scaffold as face
    import cmo3_reparent_preserve_canvas as canvas
    import cmo3_safe_roundtrip as safe
    import cmo3_secondary_professional as secondary

    return experiment, face, canvas, safe, secondary


def _object(model: Any, name: str) -> Any:
    matches = [item for item in model.objects if item.name == name]
    _require(len(matches) == 1, f"object {name!r} is missing or ambiguous")
    return matches[0]


def _direct_named(parent: Any, tag: str, name: str, label: str) -> Any:
    matches = [node for node in parent if node.tag == tag and node.get("xs.n") == name]
    _require(len(matches) == 1, f"{label}: expected one {tag}/{name}")
    return matches[0]


def _one_descendant(parent: Any, tag: str, name: str, label: str) -> Any:
    matches = [node for node in parent.iter(tag) if node.get("xs.n") == name]
    _require(len(matches) == 1, f"{label}: expected one descendant {tag}/{name}")
    return matches[0]


def _numbers(node: Any, cast: Any, label: str) -> tuple[Any, ...]:
    values = tuple(cast(token) for token in (node.text or "").split())
    _require(len(values) == int(node.get("count", "-1")), f"{label}: count differs")
    return values


def _binding_keys(binding: Any, label: str) -> tuple[float, ...]:
    node = _direct_named(binding, "array_list", "keys", label)
    return tuple(float(child.text or "nan") for child in node if child.tag == "f")


def _binding_parameter_note(binding: Any, ids: dict[str, Any], label: str) -> str:
    link = _direct_named(binding, "CParameterGuid", "parameterGuid", label)
    parameter = ids.get(link.get("xs.ref"))
    _require(parameter is not None, f"{label}: parameter ref is unresolved")
    return str(parameter.get("note"))


def _grid_semantics(
    root: Any,
    model: Any,
    item: Any,
    expected_open: str,
    expected_smile: str,
    experiment: Any,
) -> dict[str, Any]:
    ids = experiment._id_map(root)
    source = model.source(item)
    _require(item.object_type == "warp-deformer", f"{item.name}: type differs")
    grid_link = _one_descendant(source, "KeyformGridSource", "keyformGridSource", item.name)
    grid_ref = str(grid_link.get("xs.ref"))
    grid = ids.get(grid_ref)
    _require(grid is not None and grid.tag == "KeyformGridSource", f"{item.name}: grid unresolved")
    binding_links = _direct_named(grid, "array_list", "keyformBindings", item.name)
    binding_refs = [str(node.get("xs.ref")) for node in binding_links]
    _require(len(binding_refs) == 2, f"{item.name}: expected EyeOpen x EyeSmile grid")
    bindings = [ids.get(ref) for ref in binding_refs]
    _require(all(node is not None for node in bindings), f"{item.name}: binding unresolved")
    notes = [_binding_parameter_note(node, ids, item.name) for node in bindings]
    _require(set(notes) == {expected_open, expected_smile}, f"{item.name}: parameter axes differ")
    open_dimension = notes.index(expected_open)
    smile_dimension = notes.index(expected_smile)
    open_binding = bindings[open_dimension]
    smile_binding = bindings[smile_dimension]
    _require(_binding_keys(open_binding, item.name) == OLD_OPEN_KEYS, f"{item.name}: EyeOpen keys differ")
    _require(_binding_keys(smile_binding, item.name) == SMILE_KEYS, f"{item.name}: EyeSmile keys differ")

    access_to_ref: dict[tuple[int, int], str] = {}
    entries = _direct_named(grid, "array_list", "keyformsOnGrid", item.name)
    for entry in entries:
        access = next(node for node in entry.iter("array_list") if node.get("xs.n") == "_keyOnParameterList")
        values: dict[str, int] = {}
        for key in access:
            binding_link = next(node for node in key.iter("KeyformBindingSource") if node.get("xs.n") == "binding")
            index_node = next(node for node in key.iter("i") if node.get("xs.n") == "keyIndex")
            values[str(binding_link.get("xs.ref"))] = int(index_node.text or "-1")
        _require(set(values) == set(binding_refs), f"{item.name}: incomplete grid access")
        guid = next(node for node in entry.iter("CFormGuid") if node.get("xs.n") == "keyformGuid")
        logical = (values[binding_refs[open_dimension]], values[binding_refs[smile_dimension]])
        _require(logical not in access_to_ref, f"{item.name}: duplicate grid access {logical}")
        access_to_ref[logical] = str(guid.get("xs.ref"))
    _require(set(access_to_ref) == {(x, s) for s in range(3) for x in range(3)}, f"{item.name}: grid is incomplete")
    return {
        "grid_ref": grid_ref,
        "grid_idx": int(grid.get("xs.idx", "-1")),
        "binding_refs": binding_refs,
        "open_dimension": open_dimension,
        "smile_dimension": smile_dimension,
        "open_binding_ref": binding_refs[open_dimension],
        "access_to_ref": access_to_ref,
    }


def _form_positions(form: bytes, label: str) -> tuple[float, ...]:
    root = ET.fromstring(form)
    node = _direct_named(root, "float-array", "positions", label)
    return _numbers(node, float, f"{label} positions")


def _lerp_positions(
    left: Sequence[float], right: Sequence[float], ratio: float, canvas: Any
) -> tuple[float, ...]:
    _require(len(left) == len(right), "form position sizes differ")
    return tuple(
        canvas._float32(float(a) + (float(b) - float(a)) * ratio)
        for a, b in zip(left, right)
    )


def _patched_opacity(branch: str, smile_index: int, key_index: int) -> float:
    if smile_index == 2:
        return 0.0 if branch == "open" else 1.0
    curve = OPEN_TRANSITION_OPACITY if branch == "open" else CLOSED_TRANSITION_OPACITY
    return curve[key_index]


def _patch_binding_keys(block: bytes, keys: Sequence[float]) -> bytes:
    pattern = re.compile(
        rb'<array_list\b(?=[^>]*\bxs\.n="keys")[^>]*>\r\n.*?\r\n</array_list>',
        re.DOTALL,
    )
    matches = list(pattern.finditer(block))
    _require(len(matches) == 1, "EyeOpen binding keys are ambiguous")
    values = (
        "0.0",
        "0.02",
        "0.06",
        "0.1",
        "0.14",
        "0.16",
        "0.18",
        "0.2",
        "0.5",
        "1.0",
    )
    _require(tuple(keys) == NEW_OPEN_KEYS, "unexpected professional EyeOpen key plan")
    replacement = (
        f'<array_list xs.n="keys" count="{len(values)}">\r\n'.encode("ascii")
        + "\r\n".join(f"<f>{value}</f>" for value in values).encode("ascii")
        + b"\r\n</array_list>"
    )
    result = block[: matches[0].start()] + replacement + block[matches[0].end() :]
    insert_pattern = re.compile(rb'(<i\b(?=[^>]*\bxs\.n="insertPointCount")[^>]*>)[^<]*(</i>)')
    insert_matches = list(insert_pattern.finditer(result))
    _require(len(insert_matches) == 1, "EyeOpen insertPointCount is ambiguous")
    match = insert_matches[0]
    return result[: match.start()] + match.group(1) + b"8" + match.group(2) + result[match.end() :]


def _new_binding_block(
    *,
    grid_ref: str,
    binding_ref: str,
    binding_idx: int,
    parameter_ref: str,
    keys: Sequence[float],
) -> bytes:
    tokens = [format(float(key), ".9g") for key in keys]
    rows = [
        f'<KeyformBindingSource xs.id="{binding_ref}" xs.idx="{binding_idx}">',
        f'<KeyformGridSource xs.n="_gridSource" xs.ref="{grid_ref}" />',
        f'<CParameterGuid xs.n="parameterGuid" xs.ref="{parameter_ref}" />',
        f'<array_list xs.n="keys" count="{len(tokens)}">',
        *(f"<f>{token}</f>" for token in tokens),
        "</array_list>",
        '<InterpolationType xs.n="interpolationType" v="LINEAR" />',
        '<ExtendedInterpolationType xs.n="extendedInterpolationType" v="LINEAR" />',
        f'<i xs.n="insertPointCount">{max(0, len(tokens) - 2)}</i>',
        '<f xs.n="extendedInterpolationScale">1.0</f>',
        '<s xs.n="description" />',
        "</KeyformBindingSource>",
    ]
    return "\r\n".join(rows).encode("ascii")


def _parameter_ref(root: Any, note: str) -> str:
    shared = root.find("shared")
    _require(shared is not None, "shared section is missing")
    matches = [
        node
        for node in shared
        if node.tag == "CParameterGuid" and node.get("note") == note
    ]
    _require(len(matches) == 1, f"parameter {note!r} is missing or ambiguous")
    return str(matches[0].get("xs.id"))


def _generic_grid_semantics(
    root: Any,
    model: Any,
    item: Any,
    experiment: Any,
) -> dict[str, Any]:
    ids = experiment._id_map(root)
    source = model.source(item)
    grid_link = _one_descendant(
        source, "KeyformGridSource", "keyformGridSource", item.name
    )
    grid_ref = str(grid_link.get("xs.ref"))
    grid = ids.get(grid_ref)
    _require(
        grid is not None and grid.tag == "KeyformGridSource",
        f"{item.name}: grid unresolved",
    )
    links = _direct_named(grid, "array_list", "keyformBindings", item.name)
    binding_refs = [str(link.get("xs.ref")) for link in links]
    notes: list[str] = []
    keys: list[tuple[float, ...]] = []
    for ref in binding_refs:
        binding = ids.get(ref)
        _require(binding is not None, f"{item.name}: binding {ref} unresolved")
        notes.append(_binding_parameter_note(binding, ids, item.name))
        keys.append(_binding_keys(binding, item.name))
    access_to_ref: dict[tuple[int, ...], str] = {}
    for entry in _direct_named(grid, "array_list", "keyformsOnGrid", item.name):
        access = next(
            node
            for node in entry.iter("array_list")
            if node.get("xs.n") == "_keyOnParameterList"
        )
        observed: dict[str, int] = {}
        for key in access:
            link = next(
                node
                for node in key.iter("KeyformBindingSource")
                if node.get("xs.n") == "binding"
            )
            index = next(
                node
                for node in key.iter("i")
                if node.get("xs.n") == "keyIndex"
            )
            observed[str(link.get("xs.ref"))] = int(index.text or "-1")
        _require(set(observed) == set(binding_refs), f"{item.name}: grid access differs")
        logical = tuple(observed[ref] for ref in binding_refs)
        guid = next(
            node
            for node in entry.iter("CFormGuid")
            if node.get("xs.n") == "keyformGuid"
        )
        _require(logical not in access_to_ref, f"{item.name}: duplicate grid access")
        access_to_ref[logical] = str(guid.get("xs.ref"))
    return {
        "grid_ref": grid_ref,
        "grid_idx": int(grid.get("xs.idx", "-1")),
        "binding_refs": binding_refs,
        "notes": notes,
        "keys": keys,
        "access_to_ref": access_to_ref,
    }


def _roles() -> list[str]:
    roles = [
        f"{name}:open-{open_value:g}:smile-{smile_value:g}"
        for name in TARGETS
        for smile_value in SMILE_KEYS
        for open_value in ADDED_OPEN_KEYS
    ]
    for name in GAZE_MASK_TARGETS:
        roles.append(f"{name}:mask-binding")
        roles.extend(
            f"{name}:mask-form:{gaze_index}:{mask_index}"
            for gaze_index in range(9)
            for mask_index in range(len(COLOR_MASK_KEYS) - 1)
        )
    for name in WHITE_MASK_TARGETS:
        roles.extend((f"{name}:mask-grid", f"{name}:mask-binding"))
        roles.extend(
            f"{name}:mask-form:{mask_index}"
            for mask_index in range(len(COLOR_MASK_KEYS) - 1)
        )
    return roles


def _patch_gaze_masks(
    main_xml: bytes,
    *,
    source_sha: str,
    slots: dict[str, tuple[str, int]],
    modules: tuple[Any, ...],
) -> tuple[bytes, dict[str, Any], list[bytes]]:
    experiment, face, canvas, _safe, secondary = modules
    current = main_xml
    shared: list[bytes] = []
    audit: dict[str, Any] = {}
    for name, eye_parameter in GAZE_MASK_TARGETS.items():
        root = experiment._parse_xml(current)
        model = canvas.GeometryModel(current, TOLERANCE)
        item = _object(model, name)
        _require(item.object_type == "warp-deformer", f"{name}: type differs")
        semantics = _generic_grid_semantics(root, model, item, experiment)
        _require(
            semantics["notes"] == ["ParamEyeBallX", "ParamEyeBallY"]
            and semantics["keys"] == [(-1.0, 0.0, 1.0), (-1.0, 0.0, 1.0)],
            f"{name}: gaze axes differ",
        )
        _require(len(semantics["access_to_ref"]) == 9, f"{name}: gaze grid differs")
        source_block = experiment._block_by_id(
            current, "CWarpDeformerSource", item.source_ref
        )
        keyform_match, forms = secondary._keyforms(
            source_block, b"CWarpDeformerForm"
        )
        _require(len(forms) == 9, f"{name}: expected nine gaze forms")
        form_by_ref = {secondary._form_ref(form): form for form in forms}
        _require(len(form_by_ref) == 9, f"{name}: form GUID duplication")
        mask_binding_ref, mask_binding_idx = slots[f"{name}:mask-binding"]
        output_forms: list[bytes] = []
        accesses: list[tuple[int, ...]] = []
        form_refs: list[str] = []
        for gaze_index, logical in enumerate(sorted(semantics["access_to_ref"])):
            original = form_by_ref[semantics["access_to_ref"][logical]]
            original_opacity = secondary._form_opacity(original)
            for mask_index, mask_opacity in enumerate(COLOR_MASK_OPACITY):
                if mask_index == len(COLOR_MASK_KEYS) - 1:
                    form = original
                else:
                    role = f"{name}:mask-form:{gaze_index}:{mask_index}"
                    form_ref, form_idx = slots[role]
                    form = secondary._clone_form(
                        original,
                        new_ref=form_ref,
                        opacity=original_opacity * mask_opacity,
                        positions=None,
                        multiply=None,
                        face=face,
                        experiment=experiment,
                    )
                    shared.append(
                        secondary._form_guid_block(
                            form_ref, form_idx, source_sha, role
                        )
                    )
                output_forms.append(form)
                form_refs.append(secondary._form_ref(form))
                accesses.append((*logical, mask_index))
        source_after = secondary._replace_keyforms(
            source_block, keyform_match, output_forms
        )
        current = experiment._replace_exact(
            current, source_block, source_after, 1, f"mask {name} colors"
        )
        old_grid = experiment._block_by_id(
            current, "KeyformGridSource", semantics["grid_ref"]
        )
        binding_refs = [*semantics["binding_refs"], mask_binding_ref]
        new_grid = secondary._grid_block(
            grid_ref=semantics["grid_ref"],
            grid_idx=semantics["grid_idx"],
            binding_refs=binding_refs,
            accesses=accesses,
            form_refs=form_refs,
        )
        current = experiment._replace_exact(
            current, old_grid, new_grid, 1, f"expand {name} mask grid"
        )
        shared.append(
            _new_binding_block(
                grid_ref=semantics["grid_ref"],
                binding_ref=mask_binding_ref,
                binding_idx=mask_binding_idx,
                parameter_ref=_parameter_ref(root, eye_parameter),
                keys=COLOR_MASK_KEYS,
            )
        )
        audit[name] = {
            "parameter": eye_parameter,
            "forms_before": 9,
            "forms_after": 9 * len(COLOR_MASK_KEYS),
            "mask_keys": list(COLOR_MASK_KEYS),
            "mask_opacities": list(COLOR_MASK_OPACITY),
            "original_gaze_forms_reused_at_eye_open_1": True,
        }
    return current, audit, shared


def _patch_white_masks(
    main_xml: bytes,
    *,
    source_sha: str,
    slots: dict[str, tuple[str, int]],
    modules: tuple[Any, ...],
) -> tuple[bytes, dict[str, Any], list[bytes]]:
    experiment, face, canvas, _safe, secondary = modules
    current = main_xml
    shared: list[bytes] = []
    audit: dict[str, Any] = {}
    for name, eye_parameter in WHITE_MASK_TARGETS.items():
        root = experiment._parse_xml(current)
        model = canvas.GeometryModel(current, TOLERANCE)
        item = _object(model, name)
        _require(item.object_type == "art-mesh", f"{name}: type differs")
        source_block = experiment._block_by_id(
            current, "CArtMeshSource", item.source_ref
        )
        keyform_match, forms = secondary._keyforms(source_block, b"CArtMeshForm")
        _require(len(forms) == 1, f"{name}: expected one unbound form")
        original = forms[0]
        original_opacity = secondary._form_opacity(original)
        original_positions = _form_positions(original, name)
        grid_ref, grid_idx = slots[f"{name}:mask-grid"]
        binding_ref, binding_idx = slots[f"{name}:mask-binding"]
        output_forms: list[bytes] = []
        form_refs: list[str] = []
        for mask_index, mask_opacity in enumerate(COLOR_MASK_OPACITY):
            if mask_index == len(COLOR_MASK_KEYS) - 1:
                form = original
            else:
                role = f"{name}:mask-form:{mask_index}"
                form_ref, form_idx = slots[role]
                form = secondary._clone_form(
                    original,
                    new_ref=form_ref,
                    opacity=original_opacity * mask_opacity,
                    positions=None,
                    multiply=None,
                    face=face,
                    experiment=experiment,
                )
                _require(
                    _form_positions(form, role) == original_positions,
                    f"{name}: mask form geometry changed",
                )
                shared.append(
                    secondary._form_guid_block(form_ref, form_idx, source_sha, role)
                )
            output_forms.append(form)
            form_refs.append(secondary._form_ref(form))
        source_after = secondary._replace_inline_grid(source_block, grid_ref)
        keyform_match_after, _forms_after = secondary._keyforms(
            source_after, b"CArtMeshForm"
        )
        source_after = secondary._replace_keyforms(
            source_after, keyform_match_after, output_forms
        )
        current = experiment._replace_exact(
            current, source_block, source_after, 1, f"mask {name} white"
        )
        shared.extend(
            [
                secondary._grid_block(
                    grid_ref=grid_ref,
                    grid_idx=grid_idx,
                    binding_refs=[binding_ref],
                    accesses=[(index,) for index in range(len(COLOR_MASK_KEYS))],
                    form_refs=form_refs,
                ),
                _new_binding_block(
                    grid_ref=grid_ref,
                    binding_ref=binding_ref,
                    binding_idx=binding_idx,
                    parameter_ref=_parameter_ref(root, eye_parameter),
                    keys=COLOR_MASK_KEYS,
                ),
            ]
        )
        audit[name] = {
            "parameter": eye_parameter,
            "forms_before": 1,
            "forms_after": len(COLOR_MASK_KEYS),
            "mask_keys": list(COLOR_MASK_KEYS),
            "mask_opacities": list(COLOR_MASK_OPACITY),
            "positions_preserved": True,
            "original_form_reused_at_eye_open_1": True,
        }
    return current, audit, shared


def patch_main_xml(
    main_xml: bytes,
    *,
    source_sha: str,
    modules: tuple[Any, ...] | None = None,
) -> tuple[bytes, dict[str, Any]]:
    """Patch four eye branches and return ``(main_xml, audit)`` in memory."""
    experiment, face, canvas, _safe, secondary = modules or _load_modules()
    root_before = experiment._parse_xml(main_xml)
    model_before = canvas.GeometryModel(main_xml, TOLERANCE)
    identities_before = sorted(
        (item.object_type, item.name, item.guid_ref, item.source_ref, item.parent_ref)
        for item in model_before.objects
    )
    roles = _roles()
    slots = secondary._allocate(root_before, roles)
    artmesh_before = {
        item.source_ref: experiment._block_by_id(main_xml, "CArtMeshSource", item.source_ref)
        for item in model_before.objects
        if item.object_type == "art-mesh" and item.name not in MUTATED_ARTMESHES
    }
    other_warps_before = {
        item.source_ref: experiment._block_by_id(main_xml, "CWarpDeformerSource", item.source_ref)
        for item in model_before.objects
        if item.object_type == "warp-deformer" and item.name not in MUTATED_WARPS
    }

    current = main_xml
    shared_additions: list[bytes] = []
    target_audit: dict[str, Any] = {}
    neutral_form_hashes: dict[str, str] = {}
    for name, (open_parameter, smile_parameter, branch) in TARGETS.items():
        root = experiment._parse_xml(current)
        model = canvas.GeometryModel(current, TOLERANCE)
        item = _object(model, name)
        semantics = _grid_semantics(
            root, model, item, open_parameter, smile_parameter, experiment
        )
        source_block = experiment._block_by_id(
            current, "CWarpDeformerSource", item.source_ref
        )
        keyform_match, forms = secondary._keyforms(source_block, b"CWarpDeformerForm")
        _require(len(forms) == 9, f"{name}: expected nine EyeOpen x EyeSmile forms")
        form_by_ref = {secondary._form_ref(form): form for form in forms}
        _require(len(form_by_ref) == 9, f"{name}: form GUID duplication")
        old_forms = {
            logical: form_by_ref[form_ref]
            for logical, form_ref in semantics["access_to_ref"].items()
        }
        neutral_form_hashes[name] = _sha256(old_forms[(2, 0)])

        new_forms: list[bytes] = []
        new_refs: list[str] = []
        new_accesses: list[tuple[int, int]] = []
        interpolation_error = 0.0
        for smile_index, smile_value in enumerate(SMILE_KEYS):
            closed_form = old_forms[(0, smile_index)]
            half_form = old_forms[(1, smile_index)]
            closed_positions = _form_positions(closed_form, f"{name}/closed")
            half_positions = _form_positions(half_form, f"{name}/half")
            for key_index, open_value in enumerate(NEW_OPEN_KEYS):
                if open_value == 0.0:
                    form = closed_form
                elif open_value == 0.5:
                    form = half_form
                elif open_value == 1.0:
                    form = old_forms[(2, smile_index)]
                else:
                    role = f"{name}:open-{open_value:g}:smile-{smile_value:g}"
                    form_ref, form_idx = slots[role]
                    positions = _lerp_positions(
                        closed_positions,
                        half_positions,
                        open_value / 0.5,
                        canvas,
                    )
                    form = secondary._clone_form(
                        closed_form,
                        new_ref=form_ref,
                        opacity=_patched_opacity(branch, smile_index, key_index),
                        positions=positions,
                        multiply=None,
                        face=face,
                        experiment=experiment,
                    )
                    observed = _form_positions(form, f"{name}/{role}")
                    interpolation_error = max(
                        interpolation_error,
                        max(abs(a - b) for a, b in zip(observed, positions)),
                    )
                    shared_additions.append(
                        secondary._form_guid_block(form_ref, form_idx, source_sha, role)
                    )
                new_forms.append(form)
                new_refs.append(secondary._form_ref(form))
                access = [0, 0]
                access[semantics["open_dimension"]] = key_index
                access[semantics["smile_dimension"]] = smile_index
                new_accesses.append(tuple(access))

        source_after = secondary._replace_keyforms(source_block, keyform_match, new_forms)
        current = experiment._replace_exact(
            current, source_block, source_after, 1, f"expand {name} closure grid"
        )
        old_grid = experiment._block_by_id(
            current, "KeyformGridSource", semantics["grid_ref"]
        )
        new_grid = secondary._grid_block(
            grid_ref=semantics["grid_ref"],
            grid_idx=semantics["grid_idx"],
            binding_refs=semantics["binding_refs"],
            accesses=new_accesses,
            form_refs=new_refs,
        )
        current = experiment._replace_exact(
            current, old_grid, new_grid, 1, f"replace {name} closure grid"
        )
        old_binding = experiment._block_by_id(
            current, "KeyformBindingSource", semantics["open_binding_ref"]
        )
        new_binding = _patch_binding_keys(old_binding, NEW_OPEN_KEYS)
        current = experiment._replace_exact(
            current, old_binding, new_binding, 1, f"expand {name} EyeOpen binding"
        )
        target_audit[name] = {
            "branch": branch,
            "eye_open_parameter": open_parameter,
            "eye_smile_parameter": smile_parameter,
            "forms_before": 9,
            "forms_after": len(NEW_OPEN_KEYS) * len(SMILE_KEYS),
            "forms_added": len(ADDED_OPEN_KEYS) * len(SMILE_KEYS),
            "maximum_position_serialization_error": interpolation_error,
            "neutral_form_sha256": neutral_form_hashes[name],
        }

    current, gaze_audit, gaze_shared = _patch_gaze_masks(
        current,
        source_sha=source_sha,
        slots=slots,
        modules=modules or _load_modules(),
    )
    shared_additions.extend(gaze_shared)
    current, white_audit, white_shared = _patch_white_masks(
        current,
        source_sha=source_sha,
        slots=slots,
        modules=modules or _load_modules(),
    )
    shared_additions.extend(white_shared)
    current = experiment._append_shared_blocks(current, shared_additions)
    root_after = experiment._parse_xml(current)
    model_after = canvas.GeometryModel(current, TOLERANCE)
    identities_after = sorted(
        (item.object_type, item.name, item.guid_ref, item.source_ref, item.parent_ref)
        for item in model_after.objects
    )
    _require(identities_after == identities_before, "object identity/hierarchy changed")
    for item in model_after.objects:
        if item.object_type == "art-mesh" and item.name not in MUTATED_ARTMESHES:
            observed = experiment._block_by_id(current, "CArtMeshSource", item.source_ref)
            _require(observed == artmesh_before[item.source_ref], f"{item.name}: ArtMesh changed")
        elif item.object_type == "warp-deformer" and item.name not in MUTATED_WARPS:
            observed = experiment._block_by_id(current, "CWarpDeformerSource", item.source_ref)
            _require(observed == other_warps_before[item.source_ref], f"{item.name}: unrelated warp changed")

    for name, (open_parameter, smile_parameter, branch) in TARGETS.items():
        item = _object(model_after, name)
        ids = experiment._id_map(root_after)
        source = model_after.source(item)
        keyforms = _direct_named(source, "carray_list", "keyforms", name)
        _require(
            len(keyforms) == len(NEW_OPEN_KEYS) * len(SMILE_KEYS),
            f"{name}: final form count differs",
        )
        grid_link = _one_descendant(source, "KeyformGridSource", "keyformGridSource", name)
        grid = ids[str(grid_link.get("xs.ref"))]
        links = _direct_named(grid, "array_list", "keyformBindings", name)
        binding_refs = [str(link.get("xs.ref")) for link in links]
        notes = [_binding_parameter_note(ids[ref], ids, name) for ref in binding_refs]
        open_binding = ids[binding_refs[notes.index(open_parameter)]]
        _require(_binding_keys(open_binding, name) == NEW_OPEN_KEYS, f"{name}: final keys differ")
        form_hashes = {
            str(_one_descendant(form, "CFormGuid", "guid", name).get("xs.ref")): form
            for form in keyforms
        }
        neutral_ref = None
        for entry in _direct_named(grid, "array_list", "keyformsOnGrid", name):
            access = next(node for node in entry.iter("array_list") if node.get("xs.n") == "_keyOnParameterList")
            values: dict[str, int] = {}
            for key in access:
                link = next(node for node in key.iter("KeyformBindingSource") if node.get("xs.n") == "binding")
                idx = next(node for node in key.iter("i") if node.get("xs.n") == "keyIndex")
                values[str(link.get("xs.ref"))] = int(idx.text or "-1")
            if (
                values[binding_refs[notes.index(open_parameter)]]
                == len(NEW_OPEN_KEYS) - 1
                and values[binding_refs[notes.index(smile_parameter)]] == 0
            ):
                neutral_ref = str(next(node for node in entry.iter("CFormGuid") if node.get("xs.n") == "keyformGuid").get("xs.ref"))
                break
        _require(neutral_ref in form_hashes, f"{name}: neutral form unresolved")

    shared = root_after.find("shared")
    _require(shared is not None, "final shared section is missing")
    indices = [int(node.get("xs.idx", "-1")) for node in shared]
    _require(len(indices) == len(set(indices)), "final xs.idx collision")
    return current, {
        "schema": "jade.cmo3.eye-closure-professional.v1",
        "status": "ok",
        "diagnosis": (
            "The former 0..0.5 linear opacity crossfade kept both OPEN and CLOSED "
            "art branches visible near zero (at EyeOpen=0.1: OPEN 0.2 / CLOSED 0.8), "
            "creating a double contour. The original jadeV2 rig primarily deformed "
            "eye ArtMeshes directly and therefore exposed less branch ghosting."
        ),
        "old_eye_open_keys": list(OLD_OPEN_KEYS),
        "new_eye_open_keys": list(NEW_OPEN_KEYS),
        "normal_open_opacity": list(OPEN_TRANSITION_OPACITY),
        "normal_closed_opacity": list(CLOSED_TRANSITION_OPACITY),
        "eye_open_0_1_before": {"open": 0.2, "closed": 0.8},
        "eye_open_0_1_after": {
            "open_lid_lash": OPEN_TRANSITION_OPACITY[3],
            "closed_lash": CLOSED_TRANSITION_OPACITY[3],
            "iris_pupil_white": 0.0,
        },
        "lash_transition_window": [0.0, 0.2],
        "color_mask_keys": list(COLOR_MASK_KEYS),
        "color_mask_opacities": list(COLOR_MASK_OPACITY),
        "targets": target_audit,
        "gaze_color_masks": gaze_audit,
        "white_color_masks": white_audit,
        "shared_form_guids_added": len(shared_additions),
        "unrelated_artmesh_sources_byte_exact": True,
        "unrelated_warp_sources_byte_exact": True,
        "object_identity_and_hierarchy_exact": True,
        "cubism_5_2_03_load_save_required": True,
    }


def _plan(source_data: bytes, modules: tuple[Any, ...]) -> tuple[bytes, dict[str, Any]]:
    experiment, _face, _canvas, safe, _secondary = modules
    archive_before, _entry, _location, _zip, main_before = safe._validate_surgical_layout(source_data)
    main_after, audit = patch_main_xml(
        main_before, source_sha=_sha256(source_data), modules=modules
    )
    output_data = safe._replace_main_xml(source_data, main_after)
    archive_after, _e2, _l2, _z2, decoded_after = safe._validate_surgical_layout(output_data)
    _require(decoded_after == main_after, "encoded main.xml differs")
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
    audit.update(
        {
            "source_sha256": _sha256(source_data),
            "source_bytes": len(source_data),
            "output_sha256": _sha256(output_data),
            "output_bytes": len(output_data),
            "archive": preservation,
        }
    )
    return output_data, audit


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
    _require(source != output, "source/output must differ")
    _require(output.parent.is_dir(), "output parent does not exist")
    _require(not output.exists(), "output exists; refusing overwrite")
    audit_path = output.with_suffix(".audit.json")
    _require(not audit_path.exists(), "audit exists; refusing overwrite")
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
    try:
        _write_exclusive(output, output_data)
        audit["output_written"] = True
        audit["verdict"] = "PASS_PRE_CUBISM__LOAD_SAVE_5_2_03_REQUIRED"
        _write_exclusive(
            audit_path,
            (json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
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
    except EyeClosureProfessionalError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
