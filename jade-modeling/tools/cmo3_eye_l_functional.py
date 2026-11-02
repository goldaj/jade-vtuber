#!/usr/bin/env python3
"""Build Jade's first functional left-eye rig for Cubism 5.2.03.

The pinned post-Cubism OPEN-shell checkpoint is read-only. The transaction adds
dedicated CLOSED and GAZE deformers, migrates their meshes without moving them
on canvas, and binds OPEN/CLOSED to ParamEyeLOpen at 0 / 0.5 / 1.
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

SOURCE_NAME = "Jade_rig_5_2_v003.TEST_eye_l_open_shell_r01.cmo3"
SOURCE_SHA256 = "9E22C35CB02B704020F9D7E8B2EE3DCCBB67060D48A095B10941384E4CC0D311"
SOURCE_BYTES = 2_026_379
OUTPUT_NAME = "Jade_rig_5_2_v003.TEST_eye_l_functional_r01.cmo3"
AUDIT_NAME = "Jade_v003.TEST_eye_l_functional_r01_audit.json"
TOLERANCE = 0.001
PARAMETER_GUID_REF = "#1313"
PART_GUID_REF = "#628"
PART_SOURCE_REF = "#1259"


class EyeLFunctionalError(RuntimeError):
    """Raised when the functional eye transaction is unsafe or inconsistent."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EyeLFunctionalError(message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _load_stack() -> tuple[Any, ...]:
    sys.path.insert(0, str(TOOLS_DIR))
    import cmo3_eye_l_open_shell as eye

    return (eye, *eye._load_stack())


def _generated_uuid(role: str) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"jade-cmo3-face-s2c-left-functional:{SOURCE_SHA256}:{role}",
        )
    )


def _f32_tuple(canvas: Any, values: Sequence[float]) -> tuple[float, ...]:
    return tuple(canvas._float32(value) for value in values)


def _local_grid(
    canvas: Any,
    model: Any,
    parent: Any,
    original: Sequence[float],
) -> tuple[float, ...]:
    return _f32_tuple(
        canvas,
        model.inverse_many(model.transform(parent.guid_ref), original),
    )


def _clone_warp(
    main_xml: bytes,
    *,
    face: Any,
    head: Any,
    experiment: Any,
    template: Any,
    name: str,
    object_uuid: str,
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
        object_uuid=object_uuid,
        part_name="36_EYE_L",
        part_guid_ref=PART_GUID_REF,
        part_source_ref=PART_SOURCE_REF,
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
        metadata["source_ref"] == ids[0]
        and metadata["positions_ref"] == ids[1]
        and metadata["form_ref"] == ids[2]
        and metadata["guid_ref"] == ids[3],
        f"{name}: cloned references differ",
    )
    return blocks, metadata


def _form_clone(
    form: bytes,
    *,
    old_guid_ref: str,
    new_guid_ref: str,
    opacity: float,
    positions: Sequence[float],
    face: Any,
    experiment: Any,
    label: str,
) -> bytes:
    result = experiment._replace_exact(
        form,
        f'<CFormGuid xs.n="guid" xs.ref="{old_guid_ref}" />'.encode("ascii"),
        f'<CFormGuid xs.n="guid" xs.ref="{new_guid_ref}" />'.encode("ascii"),
        1,
        f"{label} form guid",
    )
    opacity_pattern = re.compile(rb'(<f\b(?=[^>]*\bxs\.n="opacity")[^>]*>)[^<]*(</f>)')
    matches = list(opacity_pattern.finditer(result))
    _require(len(matches) == 1, f"{label}: opacity field is ambiguous")
    match = matches[0]
    token = experiment._format_float32(opacity).encode("ascii")
    result = result[: match.start()] + match.group(1) + token + match.group(2) + result[match.end() :]
    return face._resize_float_payload(
        result,
        positions,
        experiment=experiment,
        label=f"{label} positions",
    )


def _bind_warp_source(
    source_block: bytes,
    *,
    source_ref: str,
    neutral_form_ref: str,
    grid_ref: str,
    form_refs: tuple[str, str, str],
    opacities: tuple[float, float, float],
    positions: tuple[Sequence[float], Sequence[float], Sequence[float]],
    face: Any,
    experiment: Any,
    label: str,
) -> bytes:
    grid_pattern = re.compile(
        rb'<KeyformGridSource\b(?=[^>]*\bxs\.n="keyformGridSource")[^>]*>'
        rb'.*?</KeyformGridSource>',
        re.DOTALL,
    )
    grid_matches = list(grid_pattern.finditer(source_block))
    _require(len(grid_matches) == 1, f"{label}: inline grid is ambiguous")
    grid = grid_matches[0]
    grid_ref_bytes = (
        f'<KeyformGridSource xs.n="keyformGridSource" xs.ref="{grid_ref}" />'
    ).encode("ascii")
    result = source_block[: grid.start()] + grid_ref_bytes + source_block[grid.end() :]

    list_pattern = re.compile(
        rb'<carray_list\b(?=[^>]*\bxs\.n="keyforms")[^>]*>\r\n'
        rb'(.*?)\r\n</carray_list>',
        re.DOTALL,
    )
    list_matches = list(list_pattern.finditer(result))
    _require(len(list_matches) == 1, f"{label}: keyform list is ambiguous")
    keyform_list = list_matches[0]
    neutral_form = keyform_list.group(1)
    _require(
        neutral_form.startswith(b"<CWarpDeformerForm>")
        and neutral_form.endswith(b"</CWarpDeformerForm>")
        and neutral_form.count(b"<CWarpDeformerForm>") == 1,
        f"{label}: neutral form differs",
    )
    forms: list[bytes] = []
    for index, (form_ref, opacity, payload) in enumerate(
        zip(form_refs, opacities, positions)
    ):
        forms.append(
            _form_clone(
                neutral_form,
                old_guid_ref=neutral_form_ref,
                new_guid_ref=form_ref,
                opacity=opacity,
                positions=payload,
                face=face,
                experiment=experiment,
                label=f"{label} key {index}",
            )
        )
    replacement = (
        b'<carray_list xs.n="keyforms" count="3">\r\n'
        + b"\r\n".join(forms)
        + b"\r\n</carray_list>"
    )
    result = result[: keyform_list.start()] + replacement + result[keyform_list.end() :]
    _require(
        result.count(f'<CWarpDeformerSource xs.id="{source_ref}"'.encode("ascii")) == 1,
        f"{label}: source identity changed",
    )
    return result


def _grid_block(
    grid_ref: str,
    grid_idx: int,
    binding_ref: str,
    form_refs: Sequence[str],
) -> bytes:
    rows: list[str] = [
        f'<KeyformGridSource xs.id="{grid_ref}" xs.idx="{grid_idx}">',
        '<array_list xs.n="keyformsOnGrid" count="3">',
    ]
    for key_index, form_ref in enumerate(form_refs):
        rows.extend(
            [
                "<KeyformOnGrid>",
                '<KeyformGridAccessKey xs.n="accessKey">',
                '<array_list xs.n="_keyOnParameterList" count="1">',
                "<KeyOnParameter>",
                f'<KeyformBindingSource xs.n="binding" xs.ref="{binding_ref}" />',
                f'<i xs.n="keyIndex">{key_index}</i>',
                "</KeyOnParameter>",
                "</array_list>",
                "</KeyformGridAccessKey>",
                f'<CFormGuid xs.n="keyformGuid" xs.ref="{form_ref}" />',
                "</KeyformOnGrid>",
            ]
        )
    rows.extend(
        [
            "</array_list>",
            '<array_list xs.n="keyformBindings" count="1">',
            f'<KeyformBindingSource xs.ref="{binding_ref}" />',
            "</array_list>",
            "</KeyformGridSource>",
        ]
    )
    return "\r\n".join(rows).encode("ascii")


def _binding_block(grid_ref: str, binding_ref: str, binding_idx: int) -> bytes:
    return (
        "\r\n".join(
            [
                f'<KeyformBindingSource xs.id="{binding_ref}" xs.idx="{binding_idx}">',
                f'<KeyformGridSource xs.n="_gridSource" xs.ref="{grid_ref}" />',
                f'<CParameterGuid xs.n="parameterGuid" xs.ref="{PARAMETER_GUID_REF}" />',
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


def _scale_y(
    canvas: Any,
    points: Sequence[float],
    center_y: float,
    scale: float,
) -> tuple[float, ...]:
    result: list[float] = []
    for x, y in zip(points[0::2], points[1::2]):
        result.extend((x, center_y + (y - center_y) * scale))
    return _f32_tuple(canvas, result)


def _closed_open_grid(canvas: Any, open_original: Sequence[float]) -> tuple[float, ...]:
    _require(len(open_original) == 40, "OPEN original grid size differs")
    xs = list(open_original[0:10:2])
    curve = (904.0, 916.0, 921.0, 912.0, 890.0)
    offsets = (-5.0, -1.5, 1.5, 5.0)
    result: list[float] = []
    for offset in offsets:
        for x, y in zip(xs, curve):
            result.extend((x, y + offset))
    return _f32_tuple(canvas, result)


def _triangle_area2(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _positive_cells(points: Sequence[float], columns: int, rows: int) -> float:
    pairs = list(zip(points[0::2], points[1::2]))
    minimum = float("inf")
    for row in range(rows):
        for column in range(columns):
            width = columns + 1
            p00 = pairs[row * width + column]
            p10 = pairs[row * width + column + 1]
            p01 = pairs[(row + 1) * width + column]
            p11 = pairs[(row + 1) * width + column + 1]
            areas = (_triangle_area2(p00, p10, p11), _triangle_area2(p00, p11, p01))
            _require(min(areas) > 0.0, "OPEN closed grid has a degenerate/inverted cell")
            minimum = min(minimum, *areas)
    return minimum


def _patch_part_sequence(
    main_xml: bytes,
    *,
    eye: Any,
    face: Any,
    experiment: Any,
    open_guid_ref: str,
    gaze_guid_ref: str,
    closed_guid_ref: str,
) -> bytes:
    current, _ = eye._patch_part_after(
        main_xml,
        experiment=experiment,
        face=face,
        part_source_ref=PART_SOURCE_REF,
        anchor_guid_ref=open_guid_ref,
        new_guid_ref=gaze_guid_ref,
    )
    current, _ = eye._patch_part_after(
        current,
        experiment=experiment,
        face=face,
        part_source_ref=PART_SOURCE_REF,
        anchor_guid_ref=gaze_guid_ref,
        new_guid_ref=closed_guid_ref,
    )
    return current


def _migrate(
    main_xml: bytes,
    *,
    old_model: Any,
    old_parent: Any,
    new_parent_name: str,
    target_name: str,
    head: Any,
    scaffold: Any,
    safe: Any,
    canvas: Any,
) -> tuple[bytes, float]:
    before_target = head._object_by_name(old_model, target_name, f"source {target_name}")
    before_forms = scaffold._form_values(old_model, canvas, before_target)
    current_model = canvas.GeometryModel(main_xml, TOLERANCE)
    new_parent = head._object_by_name(current_model, new_parent_name, new_parent_name)
    converted, proof = scaffold._convert_forms(
        canvas=canvas,
        old_model=old_model,
        new_model=current_model,
        old_parent=old_parent,
        new_parent=new_parent,
        target=before_target,
    )
    current_target = head._object_by_name(current_model, target_name, target_name)
    result, _ = scaffold._patch_parent_ref(
        main_xml,
        safe=safe,
        target=current_target,
        expected_old_ref=old_parent.guid_ref,
        new_ref=new_parent.guid_ref,
        label=f"{target_name} functional parent",
    )
    parent_patched_model = canvas.GeometryModel(result, TOLERANCE)
    parent_patched_target = head._object_by_name(
        parent_patched_model, target_name, target_name
    )
    result, _ = scaffold._patch_form_positions(
        result,
        safe=safe,
        canvas=canvas,
        target=parent_patched_target,
        expected_old=before_forms,
        replacement=converted,
        label=f"{target_name} compensated positions",
    )
    return result, max(row["max_reconstruction_error_px"] for row in proof)


def _binding_state(
    model: Any,
    item: Any,
    *,
    experiment: Any,
    canvas: Any,
) -> dict[str, Any]:
    source = model.source(item)
    grid_link = experiment._one_named(source, "KeyformGridSource", "keyformGridSource")
    grid_ref = grid_link.get("xs.ref")
    _require(grid_ref is not None, f"{item.name}: grid is not shared")
    grid = model.ids[grid_ref]
    keyforms = experiment._one_named(grid, "array_list", "keyformsOnGrid")
    bindings = experiment._one_named(grid, "array_list", "keyformBindings")
    _require(len(keyforms) == 3 and len(bindings) == 1, f"{item.name}: grid cardinality differs")
    binding_ref = bindings[0].get("xs.ref")
    _require(binding_ref is not None, f"{item.name}: binding ref missing")
    binding = model.ids[binding_ref]
    parameter = experiment._one_named(binding, "CParameterGuid", "parameterGuid")
    keys_node = experiment._one_named(binding, "array_list", "keys")
    keys = [float(node.text or "nan") for node in keys_node]
    form_refs: list[str] = []
    key_indices: list[int] = []
    for keyform in keyforms:
        guid = experiment._one_named(keyform, "CFormGuid", "keyformGuid")
        access = experiment._one_named(keyform, "array_list", "_keyOnParameterList")
        _require(len(access) == 1, f"{item.name}: key access cardinality differs")
        key_on_parameter = access[0]
        binding_node = experiment._one_named(key_on_parameter, "KeyformBindingSource", "binding")
        index_node = experiment._one_named(key_on_parameter, "i", "keyIndex")
        _require(binding_node.get("xs.ref") == binding_ref, f"{item.name}: key binding differs")
        form_refs.append(str(guid.get("xs.ref")))
        key_indices.append(int(index_node.text or "-1"))
    forms = experiment._one_named(source, "carray_list", "keyforms")
    source_form_refs: list[str] = []
    opacities: list[float] = []
    for form in forms:
        guid = experiment._one_named(form, "CFormGuid", "guid")
        opacity = experiment._one_named(form, "f", "opacity")
        source_form_refs.append(str(guid.get("xs.ref")))
        opacities.append(float(opacity.text or "nan"))
    _require(
        parameter.get("xs.ref") == PARAMETER_GUID_REF
        and keys == [0.0, 0.5, 1.0]
        and key_indices == [0, 1, 2]
        and source_form_refs == form_refs,
        f"{item.name}: ParamEyeLOpen binding differs",
    )
    return {
        "grid_ref": grid_ref,
        "binding_ref": binding_ref,
        "parameter_guid_ref": PARAMETER_GUID_REF,
        "keys": keys,
        "form_refs": form_refs,
        "opacities": opacities,
        "position_scalars": [
            len(canvas._float_values(experiment._one_named(form, "float-array", "positions"), item.name))
            for form in forms
        ],
    }


def _plan(source_data: bytes, stack: tuple[Any, ...]) -> tuple[bytes, dict[str, Any]]:
    eye, face, head, experiment, scaffold, safe, canvas, topology, _inventory = stack
    archive_before, _main_entry, _location, _zip_layout, main_before = (
        safe._validate_surgical_layout(source_data)
    )
    root0 = experiment._parse_xml(main_before)
    ids0 = experiment._id_map(root0)
    numeric_ids = sorted(int(key[1:]) for key in ids0)
    _require(numeric_ids == list(range(1366)), "source xs.id range differs")
    existing_indices = [int(node.get("xs.idx")) for node in root0.find("shared")]
    _require(max(existing_indices) == 7909, "source xs.idx tail differs")
    planned_indices = {
        8000,
        8200,
        8400,
        8600,
        8800,
        9000,
        9200,
        9400,
        9600,
        9700,
        9800,
        9900,
        10000,
        10100,
        10200,
        10300,
    }
    _require(not planned_indices.intersection(existing_indices), "planned xs.idx collision")

    model0 = canvas.GeometryModel(main_before, TOLERANCE)
    base0 = head._object_by_name(model0, "D_JAD_EYE_L_BASE", "left BASE")
    open0 = head._object_by_name(model0, "D_JAD_EYE_L_OPEN", "left OPEN")
    shared_gaze0 = head._object_by_name(
        model0, "D_JAD_EYEBALLS_GAZE_TMP", "shared gaze"
    )
    _require(
        base0.guid_ref == "#633"
        and open0.guid_ref == "#664"
        and open0.parent_ref == base0.guid_ref,
        "left-eye anchor references differ",
    )
    parameter = ids0.get(PARAMETER_GUID_REF)
    _require(
        parameter is not None
        and parameter.tag == "CParameterGuid"
        and parameter.get("note") == "ParamEyeLOpen",
        "ParamEyeLOpen GUID differs",
    )
    template = experiment._warp_info(root0, "D_JAD_FACE_FX")

    closed_bounds = (1795.0, 860.0, 2050.0, 955.0)
    closed_original = scaffold._grid(canvas, 4, 2, closed_bounds)
    closed_local = _local_grid(canvas, model0, base0, closed_original)
    gaze_bounds = (1818.0, 793.0, 1992.0, 969.0)
    gaze_original = scaffold._grid(canvas, 3, 3, gaze_bounds)
    gaze_local = _local_grid(canvas, model0, open0, gaze_original)

    closed_blocks, closed_meta = _clone_warp(
        main_before,
        face=face,
        head=head,
        experiment=experiment,
        template=template,
        name="D_JAD_EYE_L_CLOSED",
        object_uuid=_generated_uuid("closed-object"),
        parent_ref=base0.guid_ref,
        bounds=closed_bounds,
        columns=4,
        rows=2,
        ids=("#1366", "#1367", "#1368", "#1369"),
        indices=(8000, 8200, 8400, 8600),
        original=closed_original,
        local=closed_local,
        children=("JAD_EYE_L_CLOSED_LASH", "JAD_EYE_L_CLOSED_SHADOW"),
    )
    gaze_blocks, gaze_meta = _clone_warp(
        main_before,
        face=face,
        head=head,
        experiment=experiment,
        template=template,
        name="D_JAD_EYE_L_GAZE",
        object_uuid=_generated_uuid("gaze-object"),
        parent_ref=open0.guid_ref,
        bounds=gaze_bounds,
        columns=3,
        rows=3,
        ids=("#1370", "#1371", "#1372", "#1373"),
        indices=(8800, 9000, 9200, 9400),
        original=gaze_original,
        local=gaze_local,
        children=("JAD_EYE_L_IRIS", "JAD_EYE_L_PUPIL"),
    )

    current = experiment._append_shared_blocks(main_before, [*closed_blocks, *gaze_blocks])
    current, _ = head._patch_source_set_after(
        current,
        experiment=experiment,
        anchor_ref=open0.source_ref,
        new_refs=[gaze_meta["source_ref"], closed_meta["source_ref"]],
    )
    current = _patch_part_sequence(
        current,
        eye=eye,
        face=face,
        experiment=experiment,
        open_guid_ref=open0.guid_ref,
        gaze_guid_ref=gaze_meta["guid_ref"],
        closed_guid_ref=closed_meta["guid_ref"],
    )

    migrations = [
        ("JAD_EYE_L_CLOSED_LASH", base0, "D_JAD_EYE_L_CLOSED"),
        ("JAD_EYE_L_CLOSED_SHADOW", base0, "D_JAD_EYE_L_CLOSED"),
        ("JAD_EYE_L_IRIS", shared_gaze0, "D_JAD_EYE_L_GAZE"),
        ("JAD_EYE_L_PUPIL", shared_gaze0, "D_JAD_EYE_L_GAZE"),
    ]
    migration_errors: dict[str, float] = {}
    for target_name, old_parent, new_parent_name in migrations:
        current, error = _migrate(
            current,
            old_model=model0,
            old_parent=old_parent,
            new_parent_name=new_parent_name,
            target_name=target_name,
            head=head,
            scaffold=scaffold,
            safe=safe,
            canvas=canvas,
        )
        migration_errors[target_name] = error

    pre_binding_model = canvas.GeometryModel(current, TOLERANCE)
    open_pre = head._object_by_name(pre_binding_model, "D_JAD_EYE_L_OPEN", "left OPEN")
    closed_pre = head._object_by_name(
        pre_binding_model, "D_JAD_EYE_L_CLOSED", "left CLOSED"
    )
    open_source = experiment._block_by_id(current, "CWarpDeformerSource", open_pre.source_ref)
    closed_source = experiment._block_by_id(
        current, "CWarpDeformerSource", closed_pre.source_ref
    )

    open_original = model0.original_canvas(open0)
    open_neutral = scaffold._form_values(model0, canvas, open0)[0]
    open_closed_canvas = _closed_open_grid(canvas, open_original)
    minimum_closed_area = _positive_cells(open_closed_canvas, 4, 3)
    open_half_canvas = _f32_tuple(
        canvas,
        ((a + b) * 0.5 for a, b in zip(open_closed_canvas, open_original)),
    )
    base_transform = model0.transform(base0.guid_ref)
    open_closed_local = _f32_tuple(
        canvas, model0.inverse_many(base_transform, open_closed_canvas)
    )
    open_half_local = _f32_tuple(
        canvas, model0.inverse_many(base_transform, open_half_canvas)
    )

    closed_half_canvas = _scale_y(canvas, closed_original, 907.5, 0.65)
    closed_open_canvas = _scale_y(canvas, closed_original, 907.5, 0.10)
    closed_half_local = _f32_tuple(
        canvas, model0.inverse_many(base_transform, closed_half_canvas)
    )
    closed_open_local = _f32_tuple(
        canvas, model0.inverse_many(base_transform, closed_open_canvas)
    )

    open_form_refs = ("#1376", "#1377", "#1081")
    closed_form_refs = ("#1368", "#1380", "#1381")
    open_bound = _bind_warp_source(
        open_source,
        source_ref=open_pre.source_ref,
        neutral_form_ref="#1081",
        grid_ref="#1374",
        form_refs=open_form_refs,
        opacities=(0.0, 1.0, 1.0),
        positions=(open_closed_local, open_half_local, open_neutral),
        face=face,
        experiment=experiment,
        label="left OPEN",
    )
    closed_bound = _bind_warp_source(
        closed_source,
        source_ref=closed_pre.source_ref,
        neutral_form_ref=closed_meta["form_ref"],
        grid_ref="#1378",
        form_refs=closed_form_refs,
        opacities=(1.0, 0.65, 0.0),
        positions=(closed_local, closed_half_local, closed_open_local),
        face=face,
        experiment=experiment,
        label="left CLOSED",
    )
    current = experiment._replace_exact(
        current, open_source, open_bound, 1, "bind left OPEN"
    )
    current = experiment._replace_exact(
        current, closed_source, closed_bound, 1, "bind left CLOSED"
    )
    binding_blocks = [
        _grid_block("#1374", 9600, "#1375", open_form_refs),
        _binding_block("#1374", "#1375", 9700),
        _form_guid_block("#1376", 9800, "open-key-0-form"),
        _form_guid_block("#1377", 9900, "open-key-half-form"),
        _grid_block("#1378", 10000, "#1379", closed_form_refs),
        _binding_block("#1378", "#1379", 10100),
        _form_guid_block("#1380", 10200, "closed-key-half-form"),
        _form_guid_block("#1381", 10300, "closed-key-1-form"),
    ]
    current = experiment._append_shared_blocks(current, binding_blocks)

    final_model = canvas.GeometryModel(current, TOLERANCE)
    by_name = {item.name: item for item in final_model.objects}
    _require(
        by_name["D_JAD_EYE_L_CLOSED"].parent_uuid == base0.guid_uuid
        and by_name["D_JAD_EYE_L_GAZE"].parent_uuid == open0.guid_uuid,
        "new left-eye hierarchy differs",
    )
    expected_parents = {
        "JAD_EYE_L_CLOSED_LASH": "D_JAD_EYE_L_CLOSED",
        "JAD_EYE_L_CLOSED_SHADOW": "D_JAD_EYE_L_CLOSED",
        "JAD_EYE_L_IRIS": "D_JAD_EYE_L_GAZE",
        "JAD_EYE_L_PUPIL": "D_JAD_EYE_L_GAZE",
    }
    for child_name, parent_name in expected_parents.items():
        _require(
            by_name[child_name].parent_uuid == by_name[parent_name].guid_uuid,
            f"{child_name}: final parent differs",
        )
    gaze_node, gaze_positions = final_model.keyform_positions(
        by_name["D_JAD_EYE_L_GAZE"], require_single_unbound=True
    )
    _require(gaze_node is not None and len(gaze_positions) == 32, "GAZE neutral grid differs")
    open_binding = _binding_state(
        final_model,
        by_name["D_JAD_EYE_L_OPEN"],
        experiment=experiment,
        canvas=canvas,
    )
    closed_binding = _binding_state(
        final_model,
        by_name["D_JAD_EYE_L_CLOSED"],
        experiment=experiment,
        canvas=canvas,
    )
    _require(open_binding["opacities"] == [0.0, 1.0, 1.0], "OPEN opacities differ")
    _require(
        all(
            abs(observed - expected) < 1e-6
            for observed, expected in zip(
                closed_binding["opacities"], (1.0, 0.65, 0.0)
            )
        ),
        "CLOSED opacities differ",
    )

    root_final = experiment._parse_xml(current)
    ids_final = experiment._id_map(root_final)
    final_numeric_ids = sorted(int(key[1:]) for key in ids_final)
    final_indices = [int(node.get("xs.idx")) for node in root_final.find("shared")]
    _require(
        final_numeric_ids == list(range(1382))
        and len(final_indices) == len(set(final_indices)),
        "final serialized id/index set differs",
    )
    part_state = experiment._part_hierarchy_state(root_final)
    part_members = part_state["part_children"][PART_GUID_REF]
    expected_prefix = [
        ("CDeformerGuid", base0.guid_ref),
        ("CDeformerGuid", open0.guid_ref),
        ("CDeformerGuid", gaze_meta["guid_ref"]),
        ("CDeformerGuid", closed_meta["guid_ref"]),
    ]
    _require(part_members[:4] == expected_prefix, "36_EYE_L deformer order differs")

    topology_before = head._topology_xml(
        main_before, experiment=experiment, topology=topology
    )
    topology_after = head._topology_xml(
        current, experiment=experiment, topology=topology
    )
    _require(topology_after == topology_before, "ArtMesh topology changed")

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
        "schema": "jade.cubism.eye-l-functional-pre-cubism-audit.v1",
        "status": "ok",
        "verdict": "PASS_FACE_S2C1_LEFT_EYE_FUNCTIONAL__CUBISM_5_2_03_LOAD_REQUIRED",
        "operation": "add_left_eye_closed_gaze_and_bind_blink",
        "source_sha256": _sha256(source_data),
        "source_bytes": len(source_data),
        "planned_output_sha256": _sha256(output_data),
        "planned_output_bytes": len(output_data),
        "main_xml_sha256_before": _sha256(main_before),
        "main_xml_sha256_after": _sha256(current),
        "objects_added": ["D_JAD_EYE_L_CLOSED", "D_JAD_EYE_L_GAZE"],
        "hierarchy": {
            "D_JAD_EYE_L_OPEN": [
                "JAD_EYE_L_WHITE",
                "JAD_EYE_L_LID_SKIN",
                "JAD_EYE_L_LASH_FRAME",
                "D_JAD_EYE_L_GAZE",
            ],
            "D_JAD_EYE_L_GAZE": ["JAD_EYE_L_IRIS", "JAD_EYE_L_PUPIL"],
            "D_JAD_EYE_L_CLOSED": [
                "JAD_EYE_L_CLOSED_LASH",
                "JAD_EYE_L_CLOSED_SHADOW",
            ],
        },
        "open_binding": open_binding,
        "closed_binding": closed_binding,
        "gaze": {"parameter_bindings": 0, "position_scalars": len(gaze_positions)},
        "maximum_migration_error_px": max(migration_errors.values()),
        "migration_errors_px": migration_errors,
        "minimum_open_closed_cell_area2": minimum_closed_area,
        "shared_definitions_added": 16,
        "objects_added_count": 2,
        "archive": archive_proof,
        "cubism_5_2_03_load_save_required": True,
        "visual_blink_check_required": True,
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
        "source/output path differs from the FACE-S2c.1 gate",
    )
    _require(not output.exists() and not audit_path.exists(), "exclusive output already exists")
    source_data = source.read_bytes()
    _require(
        len(source_data) == SOURCE_BYTES and _sha256(source_data) == SOURCE_SHA256,
        "source bytes/SHA differs from pinned post-Cubism checkpoint",
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

    eye, _face, _head, _experiment, _scaffold, safe, _canvas, _topology, _inventory = stack
    del eye
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
    except EyeLFunctionalError as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
