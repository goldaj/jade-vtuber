#!/usr/bin/env python3
"""Bind Jade's global head warp to ParamAngleX/Y from the pinned mouth checkpoint.

The source CMO3 remains read-only.  The transaction gives ``D_JAD_HEAD_XY`` a
small, fold-free 3x3 motion grid while preserving its exact neutral keyform and
every existing face, eye, brow, nose, mouth, ear, and hair branch byte-for-byte.
Cubism 5.2.03 must load/save the generated checkpoint before it can become the
next canonical model.
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

SOURCE_NAME = "Jade_rig_5_2_v003.TEST_eye_lr_mouth_functional_r02.cmo3"
SOURCE_SHA256 = "44F0EB36D85DBDFD81E71CE8CC178443541CC100123FFBBCCE4846B82940D934"
SOURCE_BYTES = 2_039_347
OUTPUT_NAME = "Jade_rig_5_2_v003.TEST_eye_lr_mouth_head_xy_r01.cmo3"
AUDIT_NAME = "Jade_v003.TEST_head_xy_functional_r01_audit.json"

EYE_R_HELPER_NAME = "cmo3_eye_r_functional.py"
EYE_R_HELPER_SHA256 = "A22DC886A70BA040A64C4383F34E806AFE2351A6F2CE7EF6903B767751A44E33"

TOLERANCE = 0.001
HEAD_NAME = "D_JAD_HEAD_XY"
HEAD_PARENT_NAME = "R_JAD_HEAD_Z"
HEAD_COLUMNS = 7
HEAD_ROWS = 5
ANGLE_KEYS = (-30.0, 0.0, 30.0)

# Deliberately short global motion.  Existing child Angle X/Y branches retain
# their local facial parallax; this warp only makes the whole head/hair mass
# follow it coherently.
YAW_TRANSLATION_X_PX = 28.0
YAW_TOP_BIAS_X_PX = 8.0
YAW_TWIST_Y_PX = 5.0
PITCH_TRANSLATION_Y_PX = 18.0
PITCH_WIDTH_BIAS_X_PX = 3.0
PITCH_VERTICAL_BIAS_Y_PX = 4.0

EXPECTED_HEAD_CHILDREN = {
    "D_JAD_FACE_MASTER",
    "D_JAD_HAIR_FRONT_MASTER",
    "D_JAD_HAIR_BACK_MASTER",
    "D_JAD_EAR_L_MASTER",
    "D_JAD_EAR_R_MASTER",
}
REQUIRED_FACE_CHILDREN = {
    "D_JAD_FACE_ANGLE_XY",
    "D_JAD_EYE_L_BASE",
    "D_JAD_EYE_R_BASE",
    "D_JAD_BROW_L",
    "D_JAD_BROW_R",
    "D_JAD_MOUTH_MAIN",
    "Nose Warp",
}


class HeadXYFunctionalError(RuntimeError):
    """Raised when the global head transaction cannot be proven safe."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise HeadXYFunctionalError(message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _load_stack() -> tuple[Any, ...]:
    helper_path = (TOOLS_DIR / EYE_R_HELPER_NAME).resolve(strict=True)
    _require(
        _sha256(helper_path.read_bytes()) == EYE_R_HELPER_SHA256,
        "pinned right-eye helper SHA-256 differs",
    )
    sys.path.insert(0, str(TOOLS_DIR))
    import cmo3_eye_r_functional as eye_r

    _require(
        _sha256(helper_path.read_bytes()) == EYE_R_HELPER_SHA256,
        "right-eye helper changed while loading",
    )
    return (eye_r, *eye_r._load_stack())


def _generated_uuid(role: str) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"jade-cmo3-head-xy-functional:{SOURCE_SHA256}:{role}",
        )
    )


def _one_shared_note(root: Any, tag: str, note: str) -> Any:
    shared = root.find("shared")
    _require(shared is not None, "shared section is missing")
    matches = [
        node for node in shared if node.tag == tag and node.get("note") == note
    ]
    _require(len(matches) == 1, f"{tag} note {note!r} is not unique")
    return matches[0]


def _allocate_serial_slots(
    root: Any, roles: Sequence[str]
) -> dict[str, tuple[str, int]]:
    shared = root.find("shared")
    _require(shared is not None, "shared section is missing")
    ids = [int(node.get("xs.id", "#-1")[1:]) for node in shared]
    indices = [int(node.get("xs.idx", "-1")) for node in shared]
    _require(ids and sorted(ids) == list(range(max(ids) + 1)), "xs.id range differs")
    _require(len(indices) == len(set(indices)), "source xs.idx values collide")
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


def _form_guid_block(form_ref: str, form_idx: int, role: str) -> bytes:
    return (
        f'<CFormGuid uuid="{_generated_uuid(role)}" note="(no debug info)" '
        f'xs.id="{form_ref}" xs.idx="{form_idx}" />'
    ).encode("ascii")


def _angle_binding_block(
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
                "<f>-30.0</f>",
                "<f>0.0</f>",
                "<f>30.0</f>",
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


def _keyform_blocks(source_block: bytes, label: str) -> list[bytes]:
    list_pattern = re.compile(
        rb'<carray_list\b(?=[^>]*\bxs\.n="keyforms")[^>]*>\r\n'
        rb"(.*?)\r\n</carray_list>",
        re.DOTALL,
    )
    list_matches = list(list_pattern.finditer(source_block))
    _require(len(list_matches) == 1, f"{label}: keyform list is ambiguous")
    forms = re.findall(
        rb"<CWarpDeformerForm>.*?</CWarpDeformerForm>",
        list_matches[0].group(1),
        re.DOTALL,
    )
    return forms


def _bind_head_source(
    source_block: bytes,
    *,
    grid_ref: str,
    neutral_form_ref: str,
    form_refs: Sequence[str],
    form_positions: Sequence[Sequence[float]],
    blink: Any,
    face: Any,
    experiment: Any,
) -> tuple[bytes, bytes]:
    _require(
        len(form_refs) == len(form_positions) == 9,
        "head form plan is not 3x3",
    )
    grid_pattern = re.compile(
        rb'<KeyformGridSource\b(?=[^>]*\bxs\.n="keyformGridSource")[^>]*>'
        rb".*?</KeyformGridSource>",
        re.DOTALL,
    )
    matches = list(grid_pattern.finditer(source_block))
    _require(len(matches) == 1, "head inline grid is ambiguous")
    grid_match = matches[0]
    result = (
        source_block[: grid_match.start()]
        + f'<KeyformGridSource xs.n="keyformGridSource" xs.ref="{grid_ref}" />'.encode(
            "ascii"
        )
        + source_block[grid_match.end() :]
    )

    list_pattern = re.compile(
        rb'<carray_list\b(?=[^>]*\bxs\.n="keyforms")[^>]*>\r\n'
        rb"(.*?)\r\n</carray_list>",
        re.DOTALL,
    )
    list_matches = list(list_pattern.finditer(result))
    _require(len(list_matches) == 1, "head keyform list is ambiguous")
    list_match = list_matches[0]
    neutral_form = list_match.group(1)
    _require(
        neutral_form.startswith(b"<CWarpDeformerForm>")
        and neutral_form.endswith(b"</CWarpDeformerForm>")
        and neutral_form.count(b"<CWarpDeformerForm>") == 1
        and form_refs[4] == neutral_form_ref,
        "head neutral form identity differs",
    )

    forms: list[bytes] = []
    for index, (form_ref, positions) in enumerate(zip(form_refs, form_positions)):
        if index == 4:
            forms.append(neutral_form)
            continue
        forms.append(
            blink._form_clone(
                neutral_form,
                old_guid_ref=neutral_form_ref,
                new_guid_ref=form_ref,
                opacity=1.0,
                positions=positions,
                face=face,
                experiment=experiment,
                label=f"head Angle XY form {index}",
            )
        )
    replacement = (
        b'<carray_list xs.n="keyforms" count="9">\r\n'
        + b"\r\n".join(forms)
        + b"\r\n</carray_list>"
    )
    bound = result[: list_match.start()] + replacement + result[list_match.end() :]
    return bound, neutral_form


def _head_canvas_pose(
    neutral_canvas: Sequence[float], angle_x: float, angle_y: float
) -> tuple[float, ...]:
    xs = neutral_canvas[0::2]
    ys = neutral_canvas[1::2]
    center_x = (min(xs) + max(xs)) * 0.5
    center_y = (min(ys) + max(ys)) * 0.5
    half_width = (max(xs) - min(xs)) * 0.5
    half_height = (max(ys) - min(ys)) * 0.5
    _require(half_width > 0.0 and half_height > 0.0, "head canvas is degenerate")
    yaw = angle_x / 30.0
    pitch = angle_y / 30.0
    result: list[float] = []
    for x, y in zip(xs, ys):
        nx = (x - center_x) / half_width
        ny = (y - center_y) / half_height
        target_x = (
            x
            + YAW_TRANSLATION_X_PX * yaw
            - YAW_TOP_BIAS_X_PX * yaw * ny
            - PITCH_WIDTH_BIAS_X_PX * pitch * nx
        )
        target_y = (
            y
            - PITCH_TRANSLATION_Y_PX * pitch
            + YAW_TWIST_Y_PX * yaw * nx
            + PITCH_VERTICAL_BIAS_Y_PX * pitch * ny
        )
        result.extend((target_x, target_y))
    return tuple(result)


def _triangle_area2(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (
        c[0] - a[0]
    )


def _minimum_cell_area2(points: Sequence[float]) -> float:
    pairs = list(zip(points[0::2], points[1::2]))
    width = HEAD_COLUMNS + 1
    _require(
        len(pairs) == width * (HEAD_ROWS + 1),
        "head grid point count differs",
    )
    minimum = float("inf")
    for row in range(HEAD_ROWS):
        for column in range(HEAD_COLUMNS):
            p00 = pairs[row * width + column]
            p10 = pairs[row * width + column + 1]
            p01 = pairs[(row + 1) * width + column]
            p11 = pairs[(row + 1) * width + column + 1]
            areas = (
                _triangle_area2(p00, p10, p11),
                _triangle_area2(p00, p11, p01),
            )
            _require(min(areas) > 0.0, "head pose contains a folded cell")
            minimum = min(minimum, *areas)
    return minimum


def _binding_parameter_ids(
    model: Any, item: Any, experiment: Any
) -> list[str]:
    source = model.source(item)
    grid_link = experiment._one_named(
        source, "KeyformGridSource", "keyformGridSource"
    )
    grid_ref = grid_link.get("xs.ref")
    grid = model.ids[str(grid_ref)] if grid_ref else grid_link
    bindings = experiment._one_named(grid, "array_list", "keyformBindings")
    result: list[str] = []
    for binding_link in bindings:
        binding_ref = binding_link.get("xs.ref")
        _require(binding_ref in model.ids, f"{item.name}: binding is unresolved")
        binding = model.ids[str(binding_ref)]
        parameter = experiment._one_named(
            binding, "CParameterGuid", "parameterGuid"
        )
        parameter_ref = parameter.get("xs.ref")
        _require(parameter_ref in model.ids, f"{item.name}: parameter is unresolved")
        result.append(str(model.ids[str(parameter_ref)].get("note")))
    return result


def _angle_inventory(model: Any, experiment: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in model.objects:
        parameters = _binding_parameter_ids(model, item, experiment)
        if "ParamAngleX" not in parameters and "ParamAngleY" not in parameters:
            continue
        source = model.source(item)
        forms = experiment._one_named(source, "carray_list", "keyforms")
        rows.append(
            {
                "name": item.name,
                "object_type": item.object_type,
                "parameters": parameters,
                "keyforms": len(forms),
            }
        )
    return sorted(rows, key=lambda row: (row["name"], row["object_type"]))


def _binding_state(
    model: Any,
    item: Any,
    *,
    parameter_refs: tuple[str, str],
    experiment: Any,
    canvas: Any,
) -> dict[str, Any]:
    source = model.source(item)
    grid_link = experiment._one_named(
        source, "KeyformGridSource", "keyformGridSource"
    )
    grid_ref = grid_link.get("xs.ref")
    _require(grid_ref in model.ids, "head grid is not a shared definition")
    grid = model.ids[str(grid_ref)]
    keyforms = experiment._one_named(grid, "array_list", "keyformsOnGrid")
    bindings = experiment._one_named(grid, "array_list", "keyformBindings")
    _require(len(keyforms) == 9 and len(bindings) == 2, "head grid differs")
    binding_refs = [str(node.get("xs.ref")) for node in bindings]
    observed_parameter_refs: list[str] = []
    keys: list[list[float]] = []
    for binding_ref in binding_refs:
        _require(binding_ref in model.ids, "head binding is unresolved")
        binding = model.ids[binding_ref]
        parameter = experiment._one_named(
            binding, "CParameterGuid", "parameterGuid"
        )
        key_list = experiment._one_named(binding, "array_list", "keys")
        observed_parameter_refs.append(str(parameter.get("xs.ref")))
        keys.append([float(node.text or "nan") for node in key_list])

    grid_form_refs: list[str] = []
    access_indices: list[list[int]] = []
    for keyform in keyforms:
        grid_form_refs.append(
            str(
                experiment._one_named(
                    keyform, "CFormGuid", "keyformGuid"
                ).get("xs.ref")
            )
        )
        access = experiment._one_named(
            keyform, "array_list", "_keyOnParameterList"
        )
        _require(len(access) == 2, "head access-key cardinality differs")
        row: list[int] = []
        for binding_index, key_on_parameter in enumerate(access):
            binding_link = experiment._one_named(
                key_on_parameter, "KeyformBindingSource", "binding"
            )
            _require(
                binding_link.get("xs.ref") == binding_refs[binding_index],
                "head access-key binding order differs",
            )
            row.append(
                int(
                    experiment._one_named(
                        key_on_parameter, "i", "keyIndex"
                    ).text
                    or "-1"
                )
            )
        access_indices.append(row)

    forms = experiment._one_named(source, "carray_list", "keyforms")
    source_form_refs = [
        str(experiment._one_named(form, "CFormGuid", "guid").get("xs.ref"))
        for form in forms
    ]
    opacities = [
        float(experiment._one_named(form, "f", "opacity").text or "nan")
        for form in forms
    ]
    position_scalars = [
        len(
            canvas._float_values(
                experiment._one_named(form, "float-array", "positions"),
                f"{HEAD_NAME} form",
            )
        )
        for form in forms
    ]
    expected_access = [
        [x_index, y_index]
        for y_index in range(3)
        for x_index in range(3)
    ]
    _require(
        observed_parameter_refs == list(parameter_refs)
        and keys == [list(ANGLE_KEYS), list(ANGLE_KEYS)]
        and access_indices == expected_access
        and source_form_refs == grid_form_refs
        and position_scalars == [96] * 9
        and opacities == [1.0] * 9,
        "head ParamAngleX/Y semantics differ",
    )
    return {
        "grid_ref": str(grid_ref),
        "binding_refs": binding_refs,
        "parameter_guid_refs": observed_parameter_refs,
        "keys": keys,
        "form_refs": source_form_refs,
        "access_indices": access_indices,
        "neutral_form_index": 4,
        "position_scalars": position_scalars,
        "opacities": opacities,
    }


def _object_identity(item: Any) -> tuple[str, str, str, str, str, str]:
    return (
        item.object_type,
        item.name,
        item.guid_uuid,
        item.guid_ref,
        item.source_ref,
        item.parent_ref,
    )


def _raw_source_block(main_xml: bytes, model: Any, item: Any, experiment: Any) -> bytes:
    source = model.source(item)
    return experiment._block_by_id(main_xml, source.tag, item.source_ref)


def _plan(source_data: bytes, stack: tuple[Any, ...]) -> tuple[bytes, dict[str, Any]]:
    (
        _eye_r,
        blink,
        gaze,
        _eye,
        _face,
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
    _require(len(model_before.objects) == 93, "pinned source object count differs")

    head_before = head._object_by_name(model_before, HEAD_NAME, HEAD_NAME)
    parent_before = head._object_by_name(
        model_before, HEAD_PARENT_NAME, HEAD_PARENT_NAME
    )
    _require(
        head_before.object_type == "warp-deformer"
        and head_before.parent_uuid == parent_before.guid_uuid,
        "head warp identity/parent differs",
    )
    head_transform_before = model_before.transform(head_before.guid_ref)
    _require(
        head_transform_before.columns == HEAD_COLUMNS
        and head_transform_before.rows == HEAD_ROWS,
        "head warp is not the approved 7x5 grid",
    )
    head_source_before = _raw_source_block(
        main_before, model_before, head_before, experiment
    )
    neutral_blocks_before = _keyform_blocks(head_source_before, HEAD_NAME)
    _require(len(neutral_blocks_before) == 1, "head is already bound")
    neutral_form_before = neutral_blocks_before[0]
    neutral_form_ref = str(
        experiment._one_named(
            model_before.source(head_before), "CFormGuid", "guid"
        ).get("xs.ref")
    )
    _require(neutral_form_ref in ids_before, "head neutral form GUID is unresolved")
    _require(
        _binding_parameter_ids(model_before, head_before, experiment) == [],
        "head already exposes parameter bindings",
    )

    by_name_before = {item.name: item for item in model_before.objects}
    direct_head_children = {
        item.name
        for item in model_before.objects
        if item.parent_uuid == head_before.guid_uuid
    }
    _require(
        direct_head_children == EXPECTED_HEAD_CHILDREN,
        "head direct branch masters differ",
    )
    face_master = head._object_by_name(
        model_before, "D_JAD_FACE_MASTER", "face master"
    )
    direct_face_children = {
        item.name
        for item in model_before.objects
        if item.parent_uuid == face_master.guid_uuid
    }
    _require(
        REQUIRED_FACE_CHILDREN.issubset(direct_face_children),
        "face/eye/mouth branches are not ready for inherited head motion",
    )

    parameter_nodes = {
        name: _one_shared_note(root_before, "CParameterGuid", name)
        for name in ("ParamAngleX", "ParamAngleY")
    }
    parameter_refs = {
        name: str(node.get("xs.id")) for name, node in parameter_nodes.items()
    }
    parameter_blocks_before = {
        name: experiment._block_by_id(
            main_before, "CParameterGuid", parameter_refs[name]
        )
        for name in parameter_refs
    }
    angle_inventory_before = _angle_inventory(model_before, experiment)
    angle_inventory_names = {row["name"] for row in angle_inventory_before}
    _require(
        {
            "D_JAD_FACE_ANGLE_XY",
            "D_JAD_EYE_L_BASE",
            "D_JAD_EYE_R_BASE",
            "D_JAD_BROW_L",
            "D_JAD_BROW_R",
            "D_JAD_MOUTH_MAIN",
            "Nose Warp",
        }.issubset(angle_inventory_names),
        "existing face Angle X/Y branch inventory differs",
    )

    roles = [
        "head_grid",
        "head_binding_x",
        "head_binding_y",
        *[f"head_form_{index}" for index in range(9) if index != 4],
    ]
    slots = _allocate_serial_slots(root_before, roles)
    form_refs = tuple(
        neutral_form_ref if index == 4 else slots[f"head_form_{index}"][0]
        for index in range(9)
    )
    generated_uuids = {
        _generated_uuid(f"head-form-{index}")
        for index in range(9)
        if index != 4
    }
    existing_uuids = {
        str(node.get("uuid"))
        for node in root_before.iter()
        if node.get("uuid") is not None
    }
    _require(
        not generated_uuids.intersection(existing_uuids),
        "planned head form UUID collides",
    )

    neutral_local = scaffold._form_values(
        model_before, canvas, head_before
    )[0]
    neutral_canvas = model_before.original_canvas(head_before)
    parent_transform = model_before.transform(parent_before.guid_ref)
    form_positions: list[tuple[float, ...]] = []
    target_canvases: list[tuple[float, ...]] = []
    pose_errors: dict[str, float] = {}
    cell_areas: dict[str, float] = {}
    for angle_y in ANGLE_KEYS:
        for angle_x in ANGLE_KEYS:
            pose_index = len(form_positions)
            target = _head_canvas_pose(neutral_canvas, angle_x, angle_y)
            if pose_index == 4:
                local = tuple(neutral_local)
                target = tuple(neutral_canvas)
            else:
                local = tuple(
                    canvas._float32(value)
                    for value in model_before.inverse_many(parent_transform, target)
                )
            reconstructed = model_before.forward_many(parent_transform, local)
            error = canvas._maximum_error(target, reconstructed)
            label = f"x={angle_x:+.0f},y={angle_y:+.0f}"
            _require(error < TOLERANCE, f"head pose {label} exceeds tolerance")
            pose_errors[label] = error
            cell_areas[label] = _minimum_cell_area2(target)
            form_positions.append(local)
            target_canvases.append(target)

    head_source_bound, preserved_neutral = _bind_head_source(
        head_source_before,
        grid_ref=slots["head_grid"][0],
        neutral_form_ref=neutral_form_ref,
        form_refs=form_refs,
        form_positions=form_positions,
        blink=blink,
        face=_face,
        experiment=experiment,
    )
    _require(
        preserved_neutral == neutral_form_before,
        "head neutral form bytes changed during binding",
    )
    current = experiment._replace_exact(
        main_before,
        head_source_before,
        head_source_bound,
        1,
        "bind D_JAD_HEAD_XY",
    )
    shared_blocks = [
        gaze._grid_block(
            grid_ref=slots["head_grid"][0],
            grid_idx=slots["head_grid"][1],
            binding_x_ref=slots["head_binding_x"][0],
            binding_y_ref=slots["head_binding_y"][0],
            form_refs=form_refs,
        ),
        _angle_binding_block(
            grid_ref=slots["head_grid"][0],
            binding_ref=slots["head_binding_x"][0],
            binding_idx=slots["head_binding_x"][1],
            parameter_ref=parameter_refs["ParamAngleX"],
        ),
        _angle_binding_block(
            grid_ref=slots["head_grid"][0],
            binding_ref=slots["head_binding_y"][0],
            binding_idx=slots["head_binding_y"][1],
            parameter_ref=parameter_refs["ParamAngleY"],
        ),
    ]
    for index in range(9):
        if index == 4:
            continue
        shared_blocks.append(
            _form_guid_block(
                *slots[f"head_form_{index}"], f"head-form-{index}"
            )
        )
    current = experiment._append_shared_blocks(current, shared_blocks)

    root_after = experiment._parse_xml(current)
    ids_after = experiment._id_map(root_after)
    model_after = canvas.GeometryModel(current, TOLERANCE)
    head_after = head._object_by_name(model_after, HEAD_NAME, HEAD_NAME)
    _require(
        sorted(_object_identity(item) for item in model_after.objects)
        == sorted(_object_identity(item) for item in model_before.objects),
        "object identity/hierarchy changed",
    )
    _require(
        len(ids_after) == len(ids_before) + len(roles)
        and sorted(int(ref[1:]) for ref in ids_after)
        == list(range(len(ids_after))),
        "final serialized ID set differs",
    )
    final_indices = [int(node.get("xs.idx", "-1")) for node in root_after.find("shared")]
    _require(
        len(final_indices) == len(set(final_indices)),
        "final xs.idx values collide",
    )

    binding_state = _binding_state(
        model_after,
        head_after,
        parameter_refs=(
            parameter_refs["ParamAngleX"],
            parameter_refs["ParamAngleY"],
        ),
        experiment=experiment,
        canvas=canvas,
    )
    _require(
        model_after.transform(head_after.guid_ref).neutral_keyform_index == 4,
        "head neutral keyform is not the center pose",
    )
    final_head_source = _raw_source_block(
        current, model_after, head_after, experiment
    )
    final_forms = _keyform_blocks(final_head_source, "final head")
    _require(
        len(final_forms) == 9 and final_forms[4] == neutral_form_before,
        "head neutral keyform is not byte-exact",
    )

    preserved_sources: list[str] = []
    maximum_neutral_branch_error = 0.0
    for before_item in model_before.objects:
        after_item = by_name_before.get(before_item.name)
        _require(after_item is not None, f"{before_item.name}: source lookup failed")
        final_item = head._object_by_name(
            model_after, before_item.name, before_item.name
        )
        if before_item.guid_uuid != head_before.guid_uuid:
            _require(
                _raw_source_block(
                    main_before, model_before, before_item, experiment
                )
                == _raw_source_block(current, model_after, final_item, experiment),
                f"{before_item.name}: branch source changed",
            )
            preserved_sources.append(before_item.name)
        before_canvas = model_before.original_canvas(before_item)
        after_canvas = model_after.original_canvas(final_item)
        neutral_error = canvas._maximum_error(before_canvas, after_canvas)
        _require(
            neutral_error < TOLERANCE,
            f"{before_item.name}: neutral canvas changed by {neutral_error}px",
        )
        maximum_neutral_branch_error = max(
            maximum_neutral_branch_error, neutral_error
        )

    for name, before_block in parameter_blocks_before.items():
        _require(
            experiment._block_by_id(
                current, "CParameterGuid", parameter_refs[name]
            )
            == before_block,
            f"{name}: parameter definition changed",
        )
    _require(
        head._topology_xml(
            main_before, experiment=experiment, topology=topology
        )
        == head._topology_xml(current, experiment=experiment, topology=topology),
        "ArtMesh topology changed",
    )

    final_forms_values = scaffold._form_values(
        model_after, canvas, head_after
    )
    final_parent = head._object_by_name(
        model_after, HEAD_PARENT_NAME, HEAD_PARENT_NAME
    )
    final_parent_transform = model_after.transform(final_parent.guid_ref)
    final_pose_errors: dict[str, float] = {}
    for index, (angle_y, angle_x) in enumerate(
        (y, x) for y in ANGLE_KEYS for x in ANGLE_KEYS
    ):
        reconstructed = model_after.forward_many(
            final_parent_transform, final_forms_values[index]
        )
        target = target_canvases[index]
        label = f"x={angle_x:+.0f},y={angle_y:+.0f}"
        error = canvas._maximum_error(target, reconstructed)
        _require(error < TOLERANCE, f"final head pose {label} differs")
        final_pose_errors[label] = error

    angle_inventory_after = _angle_inventory(model_after, experiment)
    _require(
        angle_inventory_after
        == sorted(
            [
                *angle_inventory_before,
                {
                    "name": HEAD_NAME,
                    "object_type": "warp-deformer",
                    "parameters": ["ParamAngleX", "ParamAngleY"],
                    "keyforms": 9,
                },
            ],
            key=lambda row: (row["name"], row["object_type"]),
        ),
        "Angle X/Y binding inventory changed outside the head",
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
        "schema": "jade.cubism.head-xy-functional-pre-cubism-audit.v1",
        "status": "ok",
        "verdict": "PASS_HEAD_XY_FUNCTIONAL__CUBISM_5_2_03_LOAD_REQUIRED",
        "operation": "bind_global_head_warp_to_ParamAngleX_ParamAngleY",
        "source_sha256": _sha256(source_data),
        "source_bytes": len(source_data),
        "planned_output_sha256": _sha256(output_data),
        "planned_output_bytes": len(output_data),
        "main_xml_sha256_before": _sha256(main_before),
        "main_xml_sha256_after": _sha256(current),
        "head": {
            "name": HEAD_NAME,
            "object_guid_uuid": head_before.guid_uuid,
            "source_ref": head_before.source_ref,
            "parent": HEAD_PARENT_NAME,
            "divisions": [HEAD_COLUMNS, HEAD_ROWS],
            "direct_children": sorted(direct_head_children),
            "neutral_form_preserved_byte_exact": True,
            "neutral_form_index": 4,
            "binding": binding_state,
        },
        "motion_px": {
            "yaw_translation_x": YAW_TRANSLATION_X_PX,
            "yaw_top_bias_x": YAW_TOP_BIAS_X_PX,
            "yaw_twist_y": YAW_TWIST_Y_PX,
            "pitch_translation_y": PITCH_TRANSLATION_Y_PX,
            "pitch_width_bias_x": PITCH_WIDTH_BIAS_X_PX,
            "pitch_vertical_bias_y": PITCH_VERTICAL_BIAS_Y_PX,
        },
        "pose_reconstruction_errors_px": final_pose_errors,
        "maximum_pose_reconstruction_error_px": max(final_pose_errors.values()),
        "minimum_cell_area2_by_pose": cell_areas,
        "minimum_cell_area2": min(cell_areas.values()),
        "maximum_neutral_branch_error_px": maximum_neutral_branch_error,
        "preserved_non_head_object_sources": len(preserved_sources),
        "preserved_face_eye_mouth_hair_ear_sources_byte_exact": True,
        "existing_angle_binding_inventory_before": angle_inventory_before,
        "angle_binding_inventory_after": angle_inventory_after,
        "mouth_checkpoint_required_first": False,
        "mouth_architecture_note": (
            "D_JAD_MOUTH_MAIN already inherits D_JAD_HEAD_XY through "
            "D_JAD_FACE_MASTER and retains its existing Angle X/Y source byte-exact."
        ),
        "shared_definitions_added": len(roles),
        "archive": archive_proof,
        "cubism_5_2_03_load_save_required": True,
        "grouped_visual_head_pose_check_required": True,
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
        "source/output path differs from the head functional gate",
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

    safe = stack[8]
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
    except HeadXYFunctionalError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
