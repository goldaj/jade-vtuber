#!/usr/bin/env python3
"""Build Jade's functional right-eye branch from the pinned left-eye checkpoint.

The source CMO3 is read-only. The transaction creates dedicated right OPEN,
CLOSED, and GAZE deformers, reparents the seven right-eye meshes without a
canvas-space jump, binds blink to ParamEyeROpen, and binds gaze to the shared
ParamEyeBallX/Y parameters. Cubism 5.2.03 must load/save the produced checkpoint
before it can replace the pinned source.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Sequence


TOOLS_DIR = Path(__file__).resolve(strict=True).parent
PROJECT_DIR = TOOLS_DIR.parent
REPORTS_DIR = (PROJECT_DIR / "reports").resolve(strict=True)

SOURCE_NAME = "Jade_rig_5_2_v003.TEST_eye_l_blink_gaze_clean_r01.cmo3"
SOURCE_SHA256 = "2B53A6807D66D85276A394CD1D1F2876883E0576102DF962033CD7F7DC997BFD"
SOURCE_BYTES = 2_030_716
OUTPUT_NAME = "Jade_rig_5_2_v003.TEST_eye_lr_blink_gaze_clean_r01.cmo3"
AUDIT_NAME = "Jade_v003.TEST_eye_r_functional_r01_audit.json"

TOLERANCE = 0.001
PART_NAME = "37_EYE_R"
PART_GUID_NOTE = "PartJAD_EYE_R"
OPEN_BOUNDS = (1439.0, 776.0, 1691.0, 971.0)
CLOSED_BOUNDS = (1440.0, 860.0, 1695.0, 955.0)
GAZE_BOUNDS = (1498.0, 793.0, 1672.0, 969.0)
GAZE_AMPLITUDE_X_PX = 22.0
GAZE_AMPLITUDE_Y_PX = 10.0


class EyeRFunctionalError(RuntimeError):
    """Raised when the right-eye transaction cannot be proven safe."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EyeRFunctionalError(message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _load_stack() -> tuple[Any, ...]:
    sys.path.insert(0, str(TOOLS_DIR))
    import cmo3_eye_l_functional as blink
    import cmo3_eye_l_gaze_functional as gaze

    return (blink, gaze, *blink._load_stack())


def _generated_uuid(role: str) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"jade-cmo3-face-s2c-right-functional:{SOURCE_SHA256}:{role}",
        )
    )


def _one_shared_note(root: Any, tag: str, note: str) -> Any:
    shared = root.find("shared")
    _require(shared is not None, "shared section is missing")
    matches = [node for node in shared if node.tag == tag and node.get("note") == note]
    _require(len(matches) == 1, f"{tag} note {note!r} is not unique")
    return matches[0]


def _one_source_name(root: Any, tag: str, name: str) -> Any:
    shared = root.find("shared")
    _require(shared is not None, "shared section is missing")
    matches = []
    for node in shared:
        if node.tag != tag:
            continue
        local_names = [
            child
            for child in node.iter("s")
            if child.get("xs.n") == "localName" and (child.text or "") == name
        ]
        if len(local_names) == 1:
            matches.append(node)
    _require(len(matches) == 1, f"{tag} localName {name!r} is not unique")
    return matches[0]


def _allocate_serial_slots(root: Any, roles: Sequence[str]) -> dict[str, tuple[str, int]]:
    ids = [int(node.get("xs.id")[1:]) for node in root.find("shared")]
    indices = [int(node.get("xs.idx")) for node in root.find("shared")]
    _require(sorted(ids) == list(range(max(ids) + 1)), "source xs.id range is not contiguous")
    next_id = max(ids) + 1
    next_index = ((max(indices) // 100) + 1) * 100
    slots = {
        role: (f"#{next_id + offset}", next_index + offset * 100)
        for offset, role in enumerate(roles)
    }
    _require(
        not {index for _, index in slots.values()}.intersection(indices),
        "planned xs.idx collision",
    )
    return slots


def _clone_warp(
    main_xml: bytes,
    *,
    face: Any,
    head: Any,
    experiment: Any,
    template: Any,
    part_guid_ref: str,
    part_source_ref: str,
    name: str,
    parent_ref: str,
    bounds: tuple[float, float, float, float],
    columns: int,
    rows: int,
    ids: tuple[str, str, str, str],
    indices: tuple[int, int, int, int],
    original: Sequence[float],
    local: Sequence[float],
    children: tuple[str, ...],
) -> tuple[list[bytes], dict[str, Any]]:
    spec = head.MasterSpec(
        name=name,
        internal_id=name,
        object_uuid=_generated_uuid(f"{name}-object"),
        part_name=PART_NAME,
        part_guid_ref=part_guid_ref,
        part_source_ref=part_source_ref,
        bounds=bounds,
        columns=columns,
        rows=rows,
        children=children,
        existing_form_count=len(children),
        existing_position_scalar_count=0,
    )
    blocks, metadata = face._clone_fx_blocks(
        main_xml,
        head=head,
        experiment=experiment,
        template=template,
        spec=spec,
        ids=ids,
        indices=indices,
        parent_ref=parent_ref,
        original_positions=original,
        local_positions=local,
    )
    _require(
        tuple(metadata[key] for key in ("source_ref", "positions_ref", "form_ref", "guid_ref"))
        == ids,
        f"{name}: cloned references differ",
    )
    return blocks, metadata


def _patch_part_after(
    main_xml: bytes,
    *,
    experiment: Any,
    face: Any,
    part_source_ref: str,
    anchor_guid_ref: str,
    new_guid_refs: Sequence[str],
) -> bytes:
    _require(len(new_guid_refs) == len(set(new_guid_refs)), "Part insert refs collide")
    block = experiment._block_by_id(main_xml, "CPartSource", part_source_ref)
    start, end, child_list = face._one_part_child_list(block, PART_NAME)
    opening = re.compile(
        rb'(<carray_list\b(?=[^>]*\bxs\.n="_childGuids")'
        rb'[^>]*\bcount=")(\d+)("[^>]*>\r\n)'
    )
    matches = list(opening.finditer(child_list))
    _require(len(matches) == 1, f"{PART_NAME}: child-list opening is ambiguous")
    match = matches[0]
    old_count = int(match.group(2))
    replacement = (
        match.group(1)
        + str(old_count + len(new_guid_refs)).encode("ascii")
        + match.group(3)
    )
    patched_list = child_list[: match.start()] + replacement + child_list[match.end() :]
    anchor = f'<CDeformerGuid xs.ref="{anchor_guid_ref}" />\r\n'.encode("ascii")
    _require(patched_list.count(anchor) == 1, f"{PART_NAME}: anchor is ambiguous")
    insertion = b"".join(
        f'<CDeformerGuid xs.ref="{guid_ref}" />\r\n'.encode("ascii")
        for guid_ref in new_guid_refs
    )
    offset = patched_list.index(anchor) + len(anchor)
    patched_list = patched_list[:offset] + insertion + patched_list[offset:]
    patched_block = block[:start] + patched_list + block[end:]
    return experiment._replace_exact(
        main_xml,
        block,
        patched_block,
        1,
        f"{PART_NAME} deformer insertion",
    )


def _blink_binding_block(
    *,
    grid_ref: str,
    binding_ref: str,
    binding_idx: int,
    parameter_ref: str,
) -> bytes:
    return (
        "\r\n".join(
            [
                f'<KeyformBindingSource xs.id="{binding_ref}" xs.idx="{binding_idx}">',
                f'<KeyformGridSource xs.n="_gridSource" xs.ref="{grid_ref}" />',
                f'<CParameterGuid xs.n="parameterGuid" xs.ref="{parameter_ref}" />',
                '<array_list xs.n="keys" count="3">',
                "<f>0.0</f>",
                "<f>0.5</f>",
                "<f>1.0</f>",
                "</array_list>",
                '<InterpolationType xs.n="interpolationType" v="LINEAR" />',
                '<ExtendedInterpolationType xs.n="extendedInterpolationType" v="LINEAR" />',
                '<i xs.n="insertPointCount">1</i>',
                '<f xs.n="extendedInterpolationScale">1.0</f>',
                '<s xs.n="description" />',
                "</KeyformBindingSource>",
            ]
        )
    ).encode("ascii")


def _form_guid_block(form_ref: str, form_idx: int, role: str) -> bytes:
    return (
        f'<CFormGuid uuid="{_generated_uuid(role)}" note="(no debug info)" '
        f'xs.id="{form_ref}" xs.idx="{form_idx}" />'
    ).encode("ascii")


def _right_closed_open_grid(canvas: Any, open_original: Sequence[float]) -> tuple[float, ...]:
    _require(len(open_original) == 40, "right OPEN original grid size differs")
    xs = list(open_original[0:10:2])
    curve = (890.0, 912.0, 921.0, 916.0, 904.0)
    offsets = (-5.0, -1.5, 1.5, 5.0)
    values: list[float] = []
    for offset in offsets:
        for x, y in zip(xs, curve):
            values.extend((x, y + offset))
    return tuple(canvas._float32(value) for value in values)


def _bind_gaze_source(
    source_block: bytes,
    *,
    grid_ref: str,
    neutral_form_ref: str,
    form_refs: Sequence[str],
    form_positions: Sequence[Sequence[float]],
    blink: Any,
    face: Any,
    experiment: Any,
) -> bytes:
    _require(len(form_refs) == len(form_positions) == 9, "right GAZE form plan differs")
    grid_pattern = re.compile(
        rb'<KeyformGridSource\b(?=[^>]*\bxs\.n="keyformGridSource")[^>]*>'
        rb".*?</KeyformGridSource>",
        re.DOTALL,
    )
    matches = list(grid_pattern.finditer(source_block))
    _require(len(matches) == 1, "right GAZE inline grid is ambiguous")
    match = matches[0]
    result = (
        source_block[: match.start()]
        + f'<KeyformGridSource xs.n="keyformGridSource" xs.ref="{grid_ref}" />'.encode(
            "ascii"
        )
        + source_block[match.end() :]
    )
    list_pattern = re.compile(
        rb'<carray_list\b(?=[^>]*\bxs\.n="keyforms")[^>]*>\r\n'
        rb"(.*?)\r\n</carray_list>",
        re.DOTALL,
    )
    matches = list(list_pattern.finditer(result))
    _require(len(matches) == 1, "right GAZE keyform list is ambiguous")
    match = matches[0]
    neutral_form = match.group(1)
    _require(
        neutral_form.startswith(b"<CWarpDeformerForm>")
        and neutral_form.endswith(b"</CWarpDeformerForm>")
        and neutral_form.count(b"<CWarpDeformerForm>") == 1,
        "right GAZE neutral form differs",
    )
    forms = [
        blink._form_clone(
            neutral_form,
            old_guid_ref=neutral_form_ref,
            new_guid_ref=form_ref,
            opacity=1.0,
            positions=positions,
            face=face,
            experiment=experiment,
            label=f"right GAZE form {index}",
        )
        for index, (form_ref, positions) in enumerate(zip(form_refs, form_positions))
    ]
    replacement = (
        b'<carray_list xs.n="keyforms" count="9">\r\n'
        + b"\r\n".join(forms)
        + b"\r\n</carray_list>"
    )
    return result[: match.start()] + replacement + result[match.end() :]


def _blink_binding_state(
    model: Any,
    item: Any,
    *,
    parameter_ref: str,
    experiment: Any,
    canvas: Any,
) -> dict[str, Any]:
    source = model.source(item)
    grid_link = experiment._one_named(source, "KeyformGridSource", "keyformGridSource")
    grid_ref = str(grid_link.get("xs.ref"))
    grid = model.ids[grid_ref]
    keyforms = experiment._one_named(grid, "array_list", "keyformsOnGrid")
    bindings = experiment._one_named(grid, "array_list", "keyformBindings")
    _require(len(keyforms) == 3 and len(bindings) == 1, f"{item.name}: blink grid differs")
    binding_ref = str(bindings[0].get("xs.ref"))
    binding = model.ids[binding_ref]
    parameter = experiment._one_named(binding, "CParameterGuid", "parameterGuid")
    keys_node = experiment._one_named(binding, "array_list", "keys")
    keys = [float(node.text or "nan") for node in keys_node]
    grid_form_refs: list[str] = []
    access_indices: list[int] = []
    for keyform in keyforms:
        grid_form_refs.append(
            str(experiment._one_named(keyform, "CFormGuid", "keyformGuid").get("xs.ref"))
        )
        access = experiment._one_named(keyform, "array_list", "_keyOnParameterList")
        _require(len(access) == 1, f"{item.name}: blink access differs")
        access_indices.append(
            int(experiment._one_named(access[0], "i", "keyIndex").text or "-1")
        )
    forms = experiment._one_named(source, "carray_list", "keyforms")
    source_form_refs = [
        str(experiment._one_named(form, "CFormGuid", "guid").get("xs.ref"))
        for form in forms
    ]
    opacities = [
        float(experiment._one_named(form, "f", "opacity").text or "nan")
        for form in forms
    ]
    _require(
        parameter.get("xs.ref") == parameter_ref
        and keys == [0.0, 0.5, 1.0]
        and access_indices == [0, 1, 2]
        and source_form_refs == grid_form_refs,
        f"{item.name}: ParamEyeROpen binding differs",
    )
    return {
        "grid_ref": grid_ref,
        "binding_ref": binding_ref,
        "parameter_guid_ref": parameter_ref,
        "keys": keys,
        "form_refs": source_form_refs,
        "opacities": opacities,
        "position_scalars": [
            len(
                canvas._float_values(
                    experiment._one_named(form, "float-array", "positions"), item.name
                )
            )
            for form in forms
        ],
    }


def _gaze_binding_state(
    model: Any,
    item: Any,
    *,
    parameter_refs: tuple[str, str],
    experiment: Any,
) -> dict[str, Any]:
    source = model.source(item)
    grid_link = experiment._one_named(source, "KeyformGridSource", "keyformGridSource")
    grid_ref = str(grid_link.get("xs.ref"))
    grid = model.ids[grid_ref]
    keyforms = experiment._one_named(grid, "array_list", "keyformsOnGrid")
    bindings = experiment._one_named(grid, "array_list", "keyformBindings")
    _require(len(keyforms) == 9 and len(bindings) == 2, "right GAZE grid differs")
    binding_refs = [str(node.get("xs.ref")) for node in bindings]
    observed_parameters: list[str] = []
    keys: list[list[float]] = []
    for binding_ref in binding_refs:
        binding = model.ids[binding_ref]
        observed_parameters.append(
            str(
                experiment._one_named(binding, "CParameterGuid", "parameterGuid").get(
                    "xs.ref"
                )
            )
        )
        key_list = experiment._one_named(binding, "array_list", "keys")
        keys.append([float(node.text or "nan") for node in key_list])
    grid_form_refs: list[str] = []
    access_indices: list[list[int]] = []
    for keyform in keyforms:
        grid_form_refs.append(
            str(experiment._one_named(keyform, "CFormGuid", "keyformGuid").get("xs.ref"))
        )
        access = experiment._one_named(keyform, "array_list", "_keyOnParameterList")
        _require(len(access) == 2, "right GAZE access differs")
        row: list[int] = []
        for binding_index, key_on_parameter in enumerate(access):
            binding = experiment._one_named(
                key_on_parameter, "KeyformBindingSource", "binding"
            )
            _require(
                binding.get("xs.ref") == binding_refs[binding_index],
                "right GAZE binding order differs",
            )
            row.append(
                int(experiment._one_named(key_on_parameter, "i", "keyIndex").text or "-1")
            )
        access_indices.append(row)
    forms = experiment._one_named(source, "carray_list", "keyforms")
    source_form_refs = [
        str(experiment._one_named(form, "CFormGuid", "guid").get("xs.ref"))
        for form in forms
    ]
    _require(
        observed_parameters == list(parameter_refs)
        and keys == [[-1.0, 0.0, 1.0], [-1.0, 0.0, 1.0]]
        and access_indices
        == [[x_index, y_index] for y_index in range(3) for x_index in range(3)]
        and source_form_refs == grid_form_refs,
        "right GAZE 3x3 binding semantics differ",
    )
    return {
        "grid_ref": grid_ref,
        "binding_refs": binding_refs,
        "parameter_guid_refs": observed_parameters,
        "keys": keys,
        "form_refs": source_form_refs,
        "access_indices": access_indices,
    }


def _plan(source_data: bytes, stack: tuple[Any, ...]) -> tuple[bytes, dict[str, Any]]:
    (
        blink,
        gaze,
        _eye,
        face,
        head,
        experiment,
        scaffold,
        safe,
        canvas,
        topology,
        _inventory,
    ) = stack
    archive_before, _entry, _location, _zip, main_before = (
        safe._validate_surgical_layout(source_data)
    )
    root_before = experiment._parse_xml(main_before)
    ids_before = experiment._id_map(root_before)

    model_before = canvas.GeometryModel(main_before, TOLERANCE)
    base_before = head._object_by_name(model_before, "D_JAD_EYE_R_BASE", "right BASE")
    shared_gaze_before = head._object_by_name(
        model_before, "D_JAD_EYEBALLS_GAZE_TMP", "shared gaze"
    )
    for forbidden in ("D_JAD_EYE_R_OPEN", "D_JAD_EYE_R_CLOSED", "D_JAD_EYE_R_GAZE"):
        _require(not any(item.name == forbidden for item in model_before.objects), f"{forbidden} exists")

    base_children = (
        "JAD_EYE_R_WHITE",
        "JAD_EYE_R_LID_SKIN",
        "JAD_EYE_R_LASH_FRAME",
        "JAD_EYE_R_CLOSED_LASH",
        "JAD_EYE_R_CLOSED_SHADOW",
    )
    gaze_children = ("JAD_EYE_R_IRIS", "JAD_EYE_R_PUPIL")
    for name in base_children:
        item = head._object_by_name(model_before, name, name)
        _require(item.parent_uuid == base_before.guid_uuid, f"{name}: source parent differs")
    for name in gaze_children:
        item = head._object_by_name(model_before, name, name)
        _require(
            item.parent_uuid == shared_gaze_before.guid_uuid,
            f"{name}: source parent differs",
        )

    parameter_nodes = {
        note: _one_shared_note(root_before, "CParameterGuid", note)
        for note in ("ParamEyeROpen", "ParamEyeBallX", "ParamEyeBallY")
    }
    parameter_refs = {
        note: str(node.get("xs.id")) for note, node in parameter_nodes.items()
    }
    part_guid = _one_shared_note(root_before, "CPartGuid", PART_GUID_NOTE)
    part_source = _one_source_name(root_before, "CPartSource", PART_NAME)
    part_guid_ref = str(part_guid.get("xs.id"))
    part_source_ref = str(part_source.get("xs.id"))
    template = experiment._warp_info(root_before, "D_JAD_FACE_FX")

    roles = [
        "open_source",
        "open_positions",
        "open_neutral_form",
        "open_guid",
        "closed_source",
        "closed_positions",
        "closed_neutral_form",
        "closed_guid",
        "gaze_source",
        "gaze_positions",
        "gaze_neutral_form",
        "gaze_guid",
        "open_grid",
        "open_binding",
        "open_closed_form",
        "open_half_form",
        "closed_grid",
        "closed_binding",
        "closed_half_form",
        "closed_open_form",
        "gaze_grid",
        "gaze_binding_x",
        "gaze_binding_y",
        *[f"gaze_form_{index}" for index in range(9) if index != 4],
    ]
    slots = _allocate_serial_slots(root_before, roles)

    def refs(*names: str) -> tuple[str, ...]:
        return tuple(slots[name][0] for name in names)

    def indices(*names: str) -> tuple[int, ...]:
        return tuple(slots[name][1] for name in names)

    open_original = scaffold._grid(canvas, 4, 3, OPEN_BOUNDS)
    open_local = blink._local_grid(canvas, model_before, base_before, open_original)
    open_roles = ("open_source", "open_positions", "open_neutral_form", "open_guid")
    open_blocks, open_meta = _clone_warp(
        main_before,
        face=face,
        head=head,
        experiment=experiment,
        template=template,
        part_guid_ref=part_guid_ref,
        part_source_ref=part_source_ref,
        name="D_JAD_EYE_R_OPEN",
        parent_ref=base_before.guid_ref,
        bounds=OPEN_BOUNDS,
        columns=4,
        rows=3,
        ids=refs(*open_roles),
        indices=indices(*open_roles),
        original=open_original,
        local=open_local,
        children=("JAD_EYE_R_WHITE", "JAD_EYE_R_LID_SKIN", "JAD_EYE_R_LASH_FRAME"),
    )
    current = experiment._append_shared_blocks(main_before, open_blocks)
    current, _ = head._patch_source_set_after(
        current,
        experiment=experiment,
        anchor_ref=base_before.source_ref,
        new_refs=[open_meta["source_ref"]],
    )
    current = _patch_part_after(
        current,
        experiment=experiment,
        face=face,
        part_source_ref=part_source_ref,
        anchor_guid_ref=base_before.guid_ref,
        new_guid_refs=[open_meta["guid_ref"]],
    )

    model_with_open = canvas.GeometryModel(current, TOLERANCE)
    open_unbound = head._object_by_name(model_with_open, "D_JAD_EYE_R_OPEN", "right OPEN")
    closed_original = scaffold._grid(canvas, 4, 2, CLOSED_BOUNDS)
    closed_local = blink._local_grid(
        canvas, model_with_open, base_before, closed_original
    )
    gaze_original = scaffold._grid(canvas, 3, 3, GAZE_BOUNDS)
    gaze_local = blink._local_grid(
        canvas, model_with_open, open_unbound, gaze_original
    )
    closed_roles = (
        "closed_source",
        "closed_positions",
        "closed_neutral_form",
        "closed_guid",
    )
    gaze_roles = ("gaze_source", "gaze_positions", "gaze_neutral_form", "gaze_guid")
    closed_blocks, closed_meta = _clone_warp(
        current,
        face=face,
        head=head,
        experiment=experiment,
        template=template,
        part_guid_ref=part_guid_ref,
        part_source_ref=part_source_ref,
        name="D_JAD_EYE_R_CLOSED",
        parent_ref=base_before.guid_ref,
        bounds=CLOSED_BOUNDS,
        columns=4,
        rows=2,
        ids=refs(*closed_roles),
        indices=indices(*closed_roles),
        original=closed_original,
        local=closed_local,
        children=("JAD_EYE_R_CLOSED_LASH", "JAD_EYE_R_CLOSED_SHADOW"),
    )
    gaze_blocks, gaze_meta = _clone_warp(
        current,
        face=face,
        head=head,
        experiment=experiment,
        template=template,
        part_guid_ref=part_guid_ref,
        part_source_ref=part_source_ref,
        name="D_JAD_EYE_R_GAZE",
        parent_ref=open_unbound.guid_ref,
        bounds=GAZE_BOUNDS,
        columns=3,
        rows=3,
        ids=refs(*gaze_roles),
        indices=indices(*gaze_roles),
        original=gaze_original,
        local=gaze_local,
        children=gaze_children,
    )
    current = experiment._append_shared_blocks(current, [*closed_blocks, *gaze_blocks])
    current, _ = head._patch_source_set_after(
        current,
        experiment=experiment,
        anchor_ref=open_meta["source_ref"],
        new_refs=[gaze_meta["source_ref"], closed_meta["source_ref"]],
    )
    current = _patch_part_after(
        current,
        experiment=experiment,
        face=face,
        part_source_ref=part_source_ref,
        anchor_guid_ref=open_meta["guid_ref"],
        new_guid_refs=[gaze_meta["guid_ref"], closed_meta["guid_ref"]],
    )

    migrations = [
        ("JAD_EYE_R_WHITE", base_before, "D_JAD_EYE_R_OPEN"),
        ("JAD_EYE_R_LID_SKIN", base_before, "D_JAD_EYE_R_OPEN"),
        ("JAD_EYE_R_LASH_FRAME", base_before, "D_JAD_EYE_R_OPEN"),
        ("JAD_EYE_R_CLOSED_LASH", base_before, "D_JAD_EYE_R_CLOSED"),
        ("JAD_EYE_R_CLOSED_SHADOW", base_before, "D_JAD_EYE_R_CLOSED"),
        ("JAD_EYE_R_IRIS", shared_gaze_before, "D_JAD_EYE_R_GAZE"),
        ("JAD_EYE_R_PUPIL", shared_gaze_before, "D_JAD_EYE_R_GAZE"),
    ]
    migration_errors: dict[str, float] = {}
    for target_name, old_parent, new_parent_name in migrations:
        current, error = blink._migrate(
            current,
            old_model=model_before,
            old_parent=old_parent,
            new_parent_name=new_parent_name,
            target_name=target_name,
            head=head,
            scaffold=scaffold,
            safe=safe,
            canvas=canvas,
        )
        migration_errors[target_name] = error

    pre_blink_model = canvas.GeometryModel(current, TOLERANCE)
    base_pre = head._object_by_name(pre_blink_model, "D_JAD_EYE_R_BASE", "right BASE")
    open_pre = head._object_by_name(pre_blink_model, "D_JAD_EYE_R_OPEN", "right OPEN")
    closed_pre = head._object_by_name(
        pre_blink_model, "D_JAD_EYE_R_CLOSED", "right CLOSED"
    )
    open_source = experiment._block_by_id(
        current, "CWarpDeformerSource", open_pre.source_ref
    )
    closed_source = experiment._block_by_id(
        current, "CWarpDeformerSource", closed_pre.source_ref
    )
    open_neutral = scaffold._form_values(pre_blink_model, canvas, open_pre)[0]
    open_closed_canvas = _right_closed_open_grid(canvas, open_original)
    minimum_closed_area = blink._positive_cells(open_closed_canvas, 4, 3)
    open_half_canvas = blink._f32_tuple(
        canvas,
        ((closed + neutral) * 0.5 for closed, neutral in zip(open_closed_canvas, open_original)),
    )
    base_transform = pre_blink_model.transform(base_pre.guid_ref)
    open_closed_local = blink._f32_tuple(
        canvas, pre_blink_model.inverse_many(base_transform, open_closed_canvas)
    )
    open_half_local = blink._f32_tuple(
        canvas, pre_blink_model.inverse_many(base_transform, open_half_canvas)
    )
    closed_half_canvas = blink._scale_y(canvas, closed_original, 907.5, 0.65)
    closed_open_canvas = blink._scale_y(canvas, closed_original, 907.5, 0.10)
    closed_half_local = blink._f32_tuple(
        canvas, pre_blink_model.inverse_many(base_transform, closed_half_canvas)
    )
    closed_open_local = blink._f32_tuple(
        canvas, pre_blink_model.inverse_many(base_transform, closed_open_canvas)
    )
    open_form_refs = (
        slots["open_closed_form"][0],
        slots["open_half_form"][0],
        open_meta["form_ref"],
    )
    closed_form_refs = (
        closed_meta["form_ref"],
        slots["closed_half_form"][0],
        slots["closed_open_form"][0],
    )
    open_bound = blink._bind_warp_source(
        open_source,
        source_ref=open_pre.source_ref,
        neutral_form_ref=open_meta["form_ref"],
        grid_ref=slots["open_grid"][0],
        form_refs=open_form_refs,
        opacities=(0.0, 1.0, 1.0),
        positions=(open_closed_local, open_half_local, open_neutral),
        face=face,
        experiment=experiment,
        label="right OPEN",
    )
    closed_bound = blink._bind_warp_source(
        closed_source,
        source_ref=closed_pre.source_ref,
        neutral_form_ref=closed_meta["form_ref"],
        grid_ref=slots["closed_grid"][0],
        form_refs=closed_form_refs,
        opacities=(1.0, 0.0, 0.0),
        positions=(closed_local, closed_half_local, closed_open_local),
        face=face,
        experiment=experiment,
        label="right CLOSED",
    )
    current = experiment._replace_exact(current, open_source, open_bound, 1, "bind right OPEN")
    current = experiment._replace_exact(
        current, closed_source, closed_bound, 1, "bind right CLOSED"
    )
    blink_blocks = [
        blink._grid_block(
            slots["open_grid"][0],
            slots["open_grid"][1],
            slots["open_binding"][0],
            open_form_refs,
        ),
        _blink_binding_block(
            grid_ref=slots["open_grid"][0],
            binding_ref=slots["open_binding"][0],
            binding_idx=slots["open_binding"][1],
            parameter_ref=parameter_refs["ParamEyeROpen"],
        ),
        _form_guid_block(*slots["open_closed_form"], "open-closed-form"),
        _form_guid_block(*slots["open_half_form"], "open-half-form"),
        blink._grid_block(
            slots["closed_grid"][0],
            slots["closed_grid"][1],
            slots["closed_binding"][0],
            closed_form_refs,
        ),
        _blink_binding_block(
            grid_ref=slots["closed_grid"][0],
            binding_ref=slots["closed_binding"][0],
            binding_idx=slots["closed_binding"][1],
            parameter_ref=parameter_refs["ParamEyeROpen"],
        ),
        _form_guid_block(*slots["closed_half_form"], "closed-half-form"),
        _form_guid_block(*slots["closed_open_form"], "closed-open-form"),
    ]
    current = experiment._append_shared_blocks(current, blink_blocks)

    pre_gaze_model = canvas.GeometryModel(current, TOLERANCE)
    open_bound_item = head._object_by_name(
        pre_gaze_model, "D_JAD_EYE_R_OPEN", "right OPEN"
    )
    gaze_pre = head._object_by_name(pre_gaze_model, "D_JAD_EYE_R_GAZE", "right GAZE")
    neutral_forms = scaffold._form_values(pre_gaze_model, canvas, gaze_pre)
    _require(len(neutral_forms) == 1 and len(neutral_forms[0]) == 32, "right GAZE grid differs")
    neutral_local = neutral_forms[0]
    gaze_original_canvas = pre_gaze_model.original_canvas(gaze_pre)
    gaze_parent_transform = pre_gaze_model.transform(open_bound_item.guid_ref)
    gaze_form_refs = tuple(
        gaze_meta["form_ref"] if index == 4 else slots[f"gaze_form_{index}"][0]
        for index in range(9)
    )
    gaze_form_positions: list[tuple[float, ...]] = []
    pose_errors: dict[str, float] = {}
    edge_falloff = (0.15, 1.0, 1.0, 0.15)
    for y_value in (-1.0, 0.0, 1.0):
        for x_value in (-1.0, 0.0, 1.0):
            if x_value == 0.0 and y_value == 0.0:
                target = gaze_original_canvas
                local = tuple(neutral_local)
            else:
                target_values: list[float] = []
                for point_index, (x, y) in enumerate(
                    zip(gaze_original_canvas[0::2], gaze_original_canvas[1::2])
                ):
                    column = point_index % 4
                    row = point_index // 4
                    weight = edge_falloff[column] * edge_falloff[row]
                    target_values.extend(
                        (
                            x + GAZE_AMPLITUDE_X_PX * x_value * weight,
                            y - GAZE_AMPLITUDE_Y_PX * y_value * weight,
                        )
                    )
                target = tuple(target_values)
                local = tuple(
                    canvas._float32(value)
                    for value in pre_gaze_model.inverse_many(gaze_parent_transform, target)
                )
            reconstructed = pre_gaze_model.forward_many(gaze_parent_transform, local)
            error = canvas._maximum_error(target, reconstructed)
            _require(error < TOLERANCE, "right GAZE pose reconstruction exceeds tolerance")
            pose_errors[f"x={x_value:+.0f},y={y_value:+.0f}"] = error
            gaze_form_positions.append(local)

    gaze_source = experiment._block_by_id(
        current, "CWarpDeformerSource", gaze_pre.source_ref
    )
    gaze_bound = _bind_gaze_source(
        gaze_source,
        grid_ref=slots["gaze_grid"][0],
        neutral_form_ref=gaze_meta["form_ref"],
        form_refs=gaze_form_refs,
        form_positions=gaze_form_positions,
        blink=blink,
        face=face,
        experiment=experiment,
    )
    current = experiment._replace_exact(current, gaze_source, gaze_bound, 1, "bind right GAZE")
    gaze_blocks_to_add = [
        gaze._grid_block(
            grid_ref=slots["gaze_grid"][0],
            grid_idx=slots["gaze_grid"][1],
            binding_x_ref=slots["gaze_binding_x"][0],
            binding_y_ref=slots["gaze_binding_y"][0],
            form_refs=gaze_form_refs,
        ),
        gaze._binding_block(
            grid_ref=slots["gaze_grid"][0],
            binding_ref=slots["gaze_binding_x"][0],
            binding_idx=slots["gaze_binding_x"][1],
            parameter_ref=parameter_refs["ParamEyeBallX"],
        ),
        gaze._binding_block(
            grid_ref=slots["gaze_grid"][0],
            binding_ref=slots["gaze_binding_y"][0],
            binding_idx=slots["gaze_binding_y"][1],
            parameter_ref=parameter_refs["ParamEyeBallY"],
        ),
    ]
    for index in range(9):
        if index == 4:
            continue
        gaze_blocks_to_add.append(
            _form_guid_block(*slots[f"gaze_form_{index}"], f"gaze-form-{index}")
        )
    current = experiment._append_shared_blocks(current, gaze_blocks_to_add)

    final_model = canvas.GeometryModel(current, TOLERANCE)
    by_name = {item.name: item for item in final_model.objects}
    expected_parents = {
        "D_JAD_EYE_R_OPEN": "D_JAD_EYE_R_BASE",
        "D_JAD_EYE_R_CLOSED": "D_JAD_EYE_R_BASE",
        "D_JAD_EYE_R_GAZE": "D_JAD_EYE_R_OPEN",
        "JAD_EYE_R_WHITE": "D_JAD_EYE_R_OPEN",
        "JAD_EYE_R_LID_SKIN": "D_JAD_EYE_R_OPEN",
        "JAD_EYE_R_LASH_FRAME": "D_JAD_EYE_R_OPEN",
        "JAD_EYE_R_CLOSED_LASH": "D_JAD_EYE_R_CLOSED",
        "JAD_EYE_R_CLOSED_SHADOW": "D_JAD_EYE_R_CLOSED",
        "JAD_EYE_R_IRIS": "D_JAD_EYE_R_GAZE",
        "JAD_EYE_R_PUPIL": "D_JAD_EYE_R_GAZE",
    }
    for child_name, parent_name in expected_parents.items():
        _require(
            by_name[child_name].parent_uuid == by_name[parent_name].guid_uuid,
            f"{child_name}: final parent differs",
        )
    open_binding = _blink_binding_state(
        final_model,
        by_name["D_JAD_EYE_R_OPEN"],
        parameter_ref=parameter_refs["ParamEyeROpen"],
        experiment=experiment,
        canvas=canvas,
    )
    closed_binding = _blink_binding_state(
        final_model,
        by_name["D_JAD_EYE_R_CLOSED"],
        parameter_ref=parameter_refs["ParamEyeROpen"],
        experiment=experiment,
        canvas=canvas,
    )
    gaze_binding = _gaze_binding_state(
        final_model,
        by_name["D_JAD_EYE_R_GAZE"],
        parameter_refs=(parameter_refs["ParamEyeBallX"], parameter_refs["ParamEyeBallY"]),
        experiment=experiment,
    )
    _require(open_binding["opacities"] == [0.0, 1.0, 1.0], "right OPEN opacities differ")
    _require(
        all(
            abs(observed - expected) < 1e-6
            for observed, expected in zip(
                closed_binding["opacities"], (1.0, 0.0, 0.0)
            )
        ),
        "right CLOSED opacities differ",
    )
    _require(
        final_model.transform(by_name["D_JAD_EYE_R_GAZE"].guid_ref).neutral_keyform_index
        == 4,
        "right GAZE neutral form is not the center key",
    )

    part_state = experiment._part_hierarchy_state(experiment._parse_xml(current))
    members = part_state["part_children"][part_guid_ref]
    base_index = members.index(("CDeformerGuid", base_before.guid_ref))
    _require(
        members[base_index : base_index + 4]
        == [
            ("CDeformerGuid", base_before.guid_ref),
            ("CDeformerGuid", open_meta["guid_ref"]),
            ("CDeformerGuid", gaze_meta["guid_ref"]),
            ("CDeformerGuid", closed_meta["guid_ref"]),
        ],
        f"{PART_NAME} deformer order differs",
    )
    root_final = experiment._parse_xml(current)
    final_ids = sorted(int(ref[1:]) for ref in experiment._id_map(root_final))
    final_indices = [int(node.get("xs.idx")) for node in root_final.find("shared")]
    _require(
        final_ids == list(range(len(ids_before) + len(roles)))
        and len(final_indices) == len(set(final_indices)),
        "final serialized id/index set differs",
    )
    _require(
        head._topology_xml(main_before, experiment=experiment, topology=topology)
        == head._topology_xml(current, experiment=experiment, topology=topology),
        "ArtMesh topology changed",
    )
    for left_name in ("D_JAD_EYE_L_OPEN", "D_JAD_EYE_L_CLOSED", "D_JAD_EYE_L_GAZE"):
        before_item = head._object_by_name(model_before, left_name, left_name)
        after_item = head._object_by_name(final_model, left_name, left_name)
        _require(
            experiment._block_by_id(
                main_before, "CWarpDeformerSource", before_item.source_ref
            )
            == experiment._block_by_id(current, "CWarpDeformerSource", after_item.source_ref),
            f"{left_name} changed",
        )

    output_data = safe._replace_main_xml(source_data, current)
    archive_after, _entry_after, _loc_after, _zip_after, decoded_after = (
        safe._validate_surgical_layout(output_data)
    )
    _require(decoded_after == current, "planned archive main.xml differs")
    archive_proof = safe._compare_entry_preservation(
        source_data,
        archive_before,
        output_data,
        archive_after,
        main_may_change=True,
    )
    _require(
        archive_proof.get("all_non_main_entries_byte_identical") is True
        and archive_proof.get("changed_stored_entries") == ["main.xml"],
        "non-main archive members changed",
    )
    return output_data, {
        "schema": "jade.cubism.eye-r-functional-pre-cubism-audit.v1",
        "status": "ok",
        "verdict": "PASS_RIGHT_EYE_BLINK_GAZE__CUBISM_5_2_03_LOAD_REQUIRED",
        "operation": "add_right_open_closed_gaze_bind_blink_and_gaze",
        "source_sha256": _sha256(source_data),
        "source_bytes": len(source_data),
        "planned_output_sha256": _sha256(output_data),
        "planned_output_bytes": len(output_data),
        "main_xml_sha256_before": _sha256(main_before),
        "main_xml_sha256_after": _sha256(current),
        "objects_added": [
            "D_JAD_EYE_R_OPEN",
            "D_JAD_EYE_R_CLOSED",
            "D_JAD_EYE_R_GAZE",
        ],
        "hierarchy": expected_parents,
        "open_binding": open_binding,
        "closed_binding": closed_binding,
        "gaze_binding": gaze_binding,
        "gaze_inner_control_point_amplitude_canvas_px": {
            "x": GAZE_AMPLITUDE_X_PX,
            "y": GAZE_AMPLITUDE_Y_PX,
        },
        "gaze_edge_falloff": list(edge_falloff),
        "maximum_pose_reconstruction_error_px": max(pose_errors.values()),
        "pose_reconstruction_errors_px": pose_errors,
        "maximum_migration_error_px": max(migration_errors.values()),
        "migration_errors_px": migration_errors,
        "minimum_open_closed_cell_area2": minimum_closed_area,
        "shared_definitions_added": len(roles),
        "left_eye_deformer_sources_preserved_byte_exact": True,
        "archive": archive_proof,
        "cubism_5_2_03_load_save_required": True,
        "visual_blink_and_gaze_check_required": True,
    }


def _write_json_exclusive(path: Path, document: dict[str, Any]) -> None:
    payload = (
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
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
    audit_path = output.with_name(AUDIT_NAME)
    _require(
        source.parent == REPORTS_DIR
        and output.parent == REPORTS_DIR
        and source.name == SOURCE_NAME
        and output.name == OUTPUT_NAME
        and source != output,
        "source/output path differs from the right-eye functional gate",
    )
    _require(not output.exists() and not audit_path.exists(), "exclusive output exists")
    source_data = source.read_bytes()
    _require(
        len(source_data) == SOURCE_BYTES and _sha256(source_data) == SOURCE_SHA256,
        "source bytes/SHA differs from pinned Cubism checkpoint",
    )
    stack = _load_stack()
    output_data, audit = _plan(source_data, stack)
    tool_path = Path(__file__).resolve(strict=True)
    audit.update(
        {
            "tool": str(tool_path),
            "tool_sha256": _sha256(tool_path.read_bytes()),
            "source": str(source),
            "output": str(output),
            "audit": str(audit_path),
            "dry_run": bool(args.dry_run),
            "output_written": False,
        }
    )
    _require(source.read_bytes() == source_data, "source changed during planning")
    if args.dry_run:
        audit["verdict"] = "PASS_DRY_RUN__NO_FILE_WRITTEN"
        print(json.dumps(audit, ensure_ascii=False, sort_keys=True))
        return 0

    safe = stack[7]
    created_output = False
    created_audit = False
    try:
        safe._write_new_file(output, output_data)
        created_output = True
        _require(output.read_bytes() == output_data, "written output differs")
        audit["output_written"] = True
        audit["output_sha256"] = _sha256(output_data)
        audit["output_bytes"] = len(output_data)
        _write_json_exclusive(audit_path, audit)
        created_audit = True
        print(json.dumps(audit, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception:
        if created_audit:
            audit_path.unlink(missing_ok=True)
        if created_output:
            output.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EyeRFunctionalError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
