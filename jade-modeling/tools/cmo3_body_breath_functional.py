#!/usr/bin/env python3
"""Add restrained body motion and breathing to Jade's post-head-Z checkpoint.

The source CMO3 remains read-only.  This transaction binds the existing global
body controls without changing artwork or hierarchy:

* ``D_JAD_BODY_XY`` -> ``ParamBodyAngleX`` / ``ParamBodyAngleY`` (3x3);
* ``R_JAD_BODY_Z`` -> ``ParamBodyAngleZ`` (three keys, +/-4 degrees);
* ``D_JAD_BODY_BREATH`` -> ``ParamBreath`` (0 / 0.5 / 1).

The neutral forms stay byte-exact.  Every non-target object source and every
archive entry other than ``main.xml`` must remain byte-identical.  Repin the
three ``SOURCE_*`` constants after the head Angle Z checkpoint has completed,
then load/save the generated result with Cubism Editor 5.2.03.
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
PROJECT_DIR = TOOLS_DIR.parent
REPORTS_DIR = (PROJECT_DIR / "reports").resolve(strict=True)

# Canonical Cubism-saved head Angle-Z checkpoint.
SOURCE_NAME = "Jade_rig_5_2_v003.TEST_eye_lr_mouth_head_xyz_r02.cmo3"
SOURCE_SHA256 = "065F9B3DBFC3E1280BB9C58EE9474C61851B749379DB996B62B9C134E5095C9A"
SOURCE_BYTES = 2_043_678
OUTPUT_NAME = (
    "Jade_rig_5_2_v003.TEST_eye_lr_mouth_head_xyz_body_breath_r01.cmo3"
)
AUDIT_NAME = "Jade_v003.TEST_body_breath_functional_r01_audit.json"

HEAD_XY_HELPER_NAME = "cmo3_head_xy_functional.py"
HEAD_XY_HELPER_SHA256 = (
    "D4FAADCB5AAC05720A0ECFD80BCB7F67DF1F7877EF541C5E95E09EC0F2D624D9"
)

TOLERANCE = 0.001
EXPECTED_OBJECT_COUNT = 93

ROOT_NAME = "D_JAD_ROOT"
BODY_Z_NAME = "R_JAD_BODY_Z"
BODY_XY_NAME = "D_JAD_BODY_XY"
BREATH_NAME = "D_JAD_BODY_BREATH"
HEAD_Z_NAME = "R_JAD_HEAD_Z"
DRESS_NAME = "D_JAD_DRESS_MAIN"

BODY_COLUMNS = 5
BODY_ROWS = 5
BREATH_COLUMNS = 5
BREATH_ROWS = 5
BODY_KEYS = (-10.0, 0.0, 10.0)
BREATH_KEYS = (0.0, 0.5, 1.0)

# Motion is deliberately short for face-tracked streaming.  The lower body is
# effectively anchored while the shoulders/head follow a soft upper-body lean.
BODY_X_TOP_SHIFT_PX = 22.0
BODY_X_TWIST_Y_PX = 4.0
BODY_Y_TOP_SHIFT_PX = 12.0
BODY_ROLL_DEGREES = 4.0

# Breath acts only on the existing upper-body breath branch.  A smooth vertical
# envelope prevents edge discontinuities and avoids moving archived breast art.
BREATH_EXPAND_X_PX = 7.0
BREATH_LIFT_Y_PX = 7.0

EXPECTED_BODY_CHILDREN = {BREATH_NAME, DRESS_NAME, HEAD_Z_NAME}
EXPECTED_BREATH_CHILDREN = {
    "JAD_ARM_L_UPPER",
    "JAD_DRESS_BODICE",
    "JAD_SKIN_NECK_CHEST",
    "Neck Position",
}
TARGET_PARAMETERS = {
    "ParamBodyAngleX",
    "ParamBodyAngleY",
    "ParamBodyAngleZ",
    "ParamBreath",
}


class BodyBreathFunctionalError(RuntimeError):
    """Raised when the body/breath transaction cannot be proven safe."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise BodyBreathFunctionalError(message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _load_stack() -> tuple[Any, ...]:
    helper_path = (TOOLS_DIR / HEAD_XY_HELPER_NAME).resolve(strict=True)
    _require(
        _sha256(helper_path.read_bytes()) == HEAD_XY_HELPER_SHA256,
        "pinned head-XY helper SHA-256 differs",
    )
    sys.path.insert(0, str(TOOLS_DIR))
    import cmo3_head_xy_functional as head_xy

    _require(
        _sha256(helper_path.read_bytes()) == HEAD_XY_HELPER_SHA256,
        "head-XY helper changed while loading",
    )
    return (head_xy, *head_xy._load_stack())


def _generated_uuid(role: str) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"jade-cmo3-body-breath-functional:{SOURCE_SHA256}:{role}",
        )
    )


def _form_guid_block(form_ref: str, form_idx: int, role: str) -> bytes:
    return (
        f'<CFormGuid uuid="{_generated_uuid(role)}" note="(no debug info)" '
        f'xs.id="{form_ref}" xs.idx="{form_idx}" />'
    ).encode("ascii")


def _binding_block(
    *,
    grid_ref: str,
    binding_ref: str,
    binding_idx: int,
    parameter_ref: str,
    keys: Sequence[float],
    experiment: Any,
) -> bytes:
    _require(len(keys) == 3, "parameter binding must have three keys")
    key_rows = [
        f"<f>{experiment._format_float32(value)}</f>" for value in keys
    ]
    return (
        "\r\n".join(
            [
                f'<KeyformBindingSource xs.id="{binding_ref}" '
                f'xs.idx="{binding_idx}">',
                f'<KeyformGridSource xs.n="_gridSource" xs.ref="{grid_ref}" />',
                f'<CParameterGuid xs.n="parameterGuid" '
                f'xs.ref="{parameter_ref}" />',
                '<array_list xs.n="keys" count="3">',
                *key_rows,
                "</array_list>",
                '<InterpolationType xs.n="interpolationType" v="LINEAR" />',
                '<ExtendedInterpolationType '
                'xs.n="extendedInterpolationType" v="LINEAR" />',
                '<i xs.n="insertPointCount">1</i>',
                '<f xs.n="extendedInterpolationScale">1.0</f>',
                '<s xs.n="description" />',
                "</KeyformBindingSource>",
            ]
        )
    ).encode("ascii")


def _keyform_payload(source_block: bytes, label: str) -> tuple[Any, bytes]:
    pattern = re.compile(
        rb'<carray_list\b(?=[^>]*\bxs\.n="keyforms")[^>]*>\r\n'
        rb"(.*?)\r\n</carray_list>",
        re.DOTALL,
    )
    matches = list(pattern.finditer(source_block))
    _require(len(matches) == 1, f"{label}: keyform list is ambiguous")
    return matches[0], matches[0].group(1)


def _replace_inline_grid(
    source_block: bytes,
    *,
    grid_ref: str,
    label: str,
) -> bytes:
    pattern = re.compile(
        rb'<KeyformGridSource\b'
        rb'(?=[^>]*\bxs\.n="keyformGridSource")[^>]*>'
        rb".*?</KeyformGridSource>",
        re.DOTALL,
    )
    matches = list(pattern.finditer(source_block))
    _require(len(matches) == 1, f"{label}: inline grid is ambiguous")
    match = matches[0]
    link = (
        f'<KeyformGridSource xs.n="keyformGridSource" '
        f'xs.ref="{grid_ref}" />'
    ).encode("ascii")
    return source_block[: match.start()] + link + source_block[match.end() :]


def _bind_warp_source(
    source_block: bytes,
    *,
    source_ref: str,
    grid_ref: str,
    neutral_form_ref: str,
    neutral_index: int,
    form_refs: Sequence[str],
    form_positions: Sequence[Sequence[float]],
    blink: Any,
    face: Any,
    experiment: Any,
    label: str,
) -> tuple[bytes, bytes]:
    _require(
        len(form_refs) == len(form_positions),
        f"{label}: form plan differs",
    )
    _require(
        0 <= neutral_index < len(form_refs)
        and form_refs[neutral_index] == neutral_form_ref,
        f"{label}: neutral form plan differs",
    )
    result = _replace_inline_grid(
        source_block,
        grid_ref=grid_ref,
        label=label,
    )
    keyform_list, neutral_form = _keyform_payload(result, label)
    _require(
        neutral_form.startswith(b"<CWarpDeformerForm>")
        and neutral_form.endswith(b"</CWarpDeformerForm>")
        and neutral_form.count(b"<CWarpDeformerForm>") == 1,
        f"{label}: source is not one neutral warp form",
    )
    forms: list[bytes] = []
    for index, (form_ref, positions) in enumerate(
        zip(form_refs, form_positions)
    ):
        if index == neutral_index:
            forms.append(neutral_form)
        else:
            forms.append(
                blink._form_clone(
                    neutral_form,
                    old_guid_ref=neutral_form_ref,
                    new_guid_ref=form_ref,
                    opacity=1.0,
                    positions=positions,
                    face=face,
                    experiment=experiment,
                    label=f"{label} form {index}",
                )
            )
    replacement = (
        f'<carray_list xs.n="keyforms" count="{len(forms)}">\r\n'.encode(
            "ascii"
        )
        + b"\r\n".join(forms)
        + b"\r\n</carray_list>"
    )
    bound = (
        result[: keyform_list.start()]
        + replacement
        + result[keyform_list.end() :]
    )
    _require(
        bound.count(
            f'<CWarpDeformerSource xs.id="{source_ref}"'.encode("ascii")
        )
        == 1,
        f"{label}: source identity changed",
    )
    return bound, neutral_form


def _rotation_form_clone(
    neutral_form: bytes,
    *,
    old_guid_ref: str,
    new_guid_ref: str,
    angle: float,
    experiment: Any,
    label: str,
) -> bytes:
    result = experiment._replace_exact(
        neutral_form,
        f'<CFormGuid xs.n="guid" xs.ref="{old_guid_ref}" />'.encode("ascii"),
        f'<CFormGuid xs.n="guid" xs.ref="{new_guid_ref}" />'.encode("ascii"),
        1,
        f"{label} form guid",
    )
    opening_end = result.find(b">")
    _require(opening_end > 0, f"{label}: rotation opening is missing")
    opening = result[: opening_end + 1]
    pattern = re.compile(rb'(\bangle=")[^"]*(")')
    matches = list(pattern.finditer(opening))
    _require(len(matches) == 1, f"{label}: angle attribute is ambiguous")
    match = matches[0]
    token = experiment._format_float32(angle).encode("ascii")
    patched_opening = (
        opening[: match.start()]
        + match.group(1)
        + token
        + match.group(2)
        + opening[match.end() :]
    )
    return patched_opening + result[opening_end + 1 :]


def _bind_rotation_source(
    source_block: bytes,
    *,
    source_ref: str,
    grid_ref: str,
    neutral_form_ref: str,
    form_refs: Sequence[str],
    angles: Sequence[float],
    experiment: Any,
    label: str,
) -> tuple[bytes, bytes]:
    _require(
        len(form_refs) == len(angles) == 3 and form_refs[1] == neutral_form_ref,
        f"{label}: rotation plan differs",
    )
    result = _replace_inline_grid(
        source_block,
        grid_ref=grid_ref,
        label=label,
    )
    keyform_list, neutral_form = _keyform_payload(result, label)
    _require(
        neutral_form.startswith(b"<CRotationDeformerForm ")
        and neutral_form.endswith(b"</CRotationDeformerForm>")
        and neutral_form.count(b"<CRotationDeformerForm ") == 1,
        f"{label}: source is not one neutral rotation form",
    )
    forms: list[bytes] = []
    for index, (form_ref, angle) in enumerate(zip(form_refs, angles)):
        if index == 1:
            forms.append(neutral_form)
        else:
            forms.append(
                _rotation_form_clone(
                    neutral_form,
                    old_guid_ref=neutral_form_ref,
                    new_guid_ref=form_ref,
                    angle=angle,
                    experiment=experiment,
                    label=f"{label} form {index}",
                )
            )
    replacement = (
        b'<carray_list xs.n="keyforms" count="3">\r\n'
        + b"\r\n".join(forms)
        + b"\r\n</carray_list>"
    )
    bound = (
        result[: keyform_list.start()]
        + replacement
        + result[keyform_list.end() :]
    )
    _require(
        bound.count(
            f'<CRotationDeformerSource xs.id="{source_ref}"'.encode("ascii")
        )
        == 1,
        f"{label}: source identity changed",
    )
    return bound, neutral_form


def _body_canvas_pose(
    neutral_canvas: Sequence[float],
    angle_x: float,
    angle_y: float,
) -> tuple[float, ...]:
    xs = neutral_canvas[0::2]
    ys = neutral_canvas[1::2]
    center_x = (min(xs) + max(xs)) * 0.5
    half_width = (max(xs) - min(xs)) * 0.5
    height = max(ys) - min(ys)
    _require(half_width > 0.0 and height > 0.0, "body canvas is degenerate")
    yaw = angle_x / 10.0
    pitch = angle_y / 10.0
    result: list[float] = []
    for x, y in zip(xs, ys):
        normalized_x = (x - center_x) / half_width
        vertical = min(1.0, max(0.0, (y - min(ys)) / height))
        upper_weight = (1.0 - vertical) ** 1.35
        target_x = x + BODY_X_TOP_SHIFT_PX * yaw * upper_weight
        target_y = (
            y
            + BODY_X_TWIST_Y_PX * yaw * normalized_x * upper_weight
            - BODY_Y_TOP_SHIFT_PX * pitch * upper_weight
        )
        result.extend((target_x, target_y))
    return tuple(result)


def _breath_canvas_pose(
    neutral_canvas: Sequence[float],
    amount: float,
) -> tuple[float, ...]:
    xs = neutral_canvas[0::2]
    ys = neutral_canvas[1::2]
    center_x = (min(xs) + max(xs)) * 0.5
    half_width = (max(xs) - min(xs)) * 0.5
    height = max(ys) - min(ys)
    _require(half_width > 0.0 and height > 0.0, "breath canvas is degenerate")
    result: list[float] = []
    for x, y in zip(xs, ys):
        normalized_x = (x - center_x) / half_width
        vertical = min(1.0, max(0.0, (y - min(ys)) / height))
        envelope = math.sin(math.pi * vertical) ** 0.8
        target_x = (
            x + BREATH_EXPAND_X_PX * amount * normalized_x * envelope
        )
        target_y = y - BREATH_LIFT_Y_PX * amount * envelope
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


def _minimum_cell_area2(
    points: Sequence[float],
    *,
    columns: int,
    rows: int,
    label: str,
) -> float:
    pairs = list(zip(points[0::2], points[1::2]))
    width = columns + 1
    _require(len(pairs) == width * (rows + 1), f"{label}: grid size differs")
    minimum = float("inf")
    for row in range(rows):
        for column in range(columns):
            p00 = pairs[row * width + column]
            p10 = pairs[row * width + column + 1]
            p01 = pairs[(row + 1) * width + column]
            p11 = pairs[(row + 1) * width + column + 1]
            areas = (
                _triangle_area2(p00, p10, p11),
                _triangle_area2(p00, p11, p01),
            )
            _require(min(areas) > 0.0, f"{label}: folded grid cell")
            minimum = min(minimum, *areas)
    return minimum


def _object_identity(item: Any) -> tuple[str, str, str, str, str, str]:
    return (
        item.object_type,
        item.name,
        item.guid_uuid,
        item.guid_ref,
        item.source_ref,
        item.parent_ref,
    )


def _object_by_name(objects: Sequence[Any], name: str) -> Any:
    matches = [item for item in objects if item.name == name]
    _require(len(matches) == 1, f"object {name!r} is not unique")
    return matches[0]


def _raw_source_block(
    main_xml: bytes,
    ids: dict[str, Any],
    item: Any,
    experiment: Any,
) -> bytes:
    source = ids.get(item.source_ref)
    _require(source is not None, f"{item.name}: source is unresolved")
    return experiment._block_by_id(
        main_xml,
        source.tag,
        item.source_ref,
    )


def _parameter_state(
    root: Any,
    *,
    guid_ref: str,
    expected_id: str,
    experiment: Any,
) -> dict[str, Any]:
    ids = experiment._id_map(root)
    guid = ids.get(guid_ref)
    _require(
        guid is not None
        and guid.tag == "CParameterGuid"
        and guid.get("note") == expected_id,
        f"{expected_id}: GUID definition differs",
    )
    matches = []
    for source in root.iter("CParameterSource"):
        field = experiment._one_named(source, "CParameterGuid", "guid")
        if field.get("xs.ref") == guid_ref:
            matches.append(source)
    _require(len(matches) == 1, f"{expected_id}: parameter source is ambiguous")
    source = matches[0]
    return {
        "id": expected_id,
        "guid_ref": guid_ref,
        "minimum": float(
            experiment._one_named(source, "f", "minValue").text or "nan"
        ),
        "maximum": float(
            experiment._one_named(source, "f", "maxValue").text or "nan"
        ),
        "default": float(
            experiment._one_named(source, "f", "defaultValue").text
            or "nan"
        ),
    }


def _binding_parameter_ids_from_root(
    ids: dict[str, Any],
    item: Any,
    experiment: Any,
) -> list[str]:
    source = ids.get(item.source_ref)
    _require(source is not None, f"{item.name}: source is unresolved")
    grid_link = experiment._one_named(
        source,
        "KeyformGridSource",
        "keyformGridSource",
    )
    grid_ref = grid_link.get("xs.ref")
    grid = ids.get(str(grid_ref)) if grid_ref else grid_link
    _require(grid is not None, f"{item.name}: grid is unresolved")
    bindings = experiment._one_named(
        grid,
        "array_list",
        "keyformBindings",
    )
    result: list[str] = []
    for binding_link in bindings:
        binding = ids.get(str(binding_link.get("xs.ref")))
        _require(binding is not None, f"{item.name}: binding is unresolved")
        parameter = experiment._one_named(
            binding,
            "CParameterGuid",
            "parameterGuid",
        )
        parameter_node = ids.get(str(parameter.get("xs.ref")))
        _require(
            parameter_node is not None,
            f"{item.name}: parameter is unresolved",
        )
        result.append(str(parameter_node.get("note")))
    return result


def _body_binding_inventory(
    main_xml: bytes,
    *,
    experiment: Any,
    safe: Any,
) -> list[dict[str, Any]]:
    root = experiment._parse_xml(main_xml)
    ids = experiment._id_map(root)
    objects = safe._semantic_objects(main_xml)
    rows: list[dict[str, Any]] = []
    for item in objects:
        parameters = _binding_parameter_ids_from_root(ids, item, experiment)
        relevant = [name for name in parameters if name in TARGET_PARAMETERS]
        if relevant:
            source = ids[item.source_ref]
            forms = experiment._one_named(source, "carray_list", "keyforms")
            rows.append(
                {
                    "name": item.name,
                    "object_type": item.object_type,
                    "parameters": relevant,
                    "keyforms": len(forms),
                }
            )
    return sorted(rows, key=lambda row: (row["name"], row["object_type"]))


def _access_state(
    ids: dict[str, Any],
    source: Any,
    *,
    expected_parameter_refs: Sequence[str],
    expected_keys: Sequence[Sequence[float]],
    expected_access: Sequence[Sequence[int]],
    experiment: Any,
) -> dict[str, Any]:
    grid_link = experiment._one_named(
        source,
        "KeyformGridSource",
        "keyformGridSource",
    )
    grid_ref = str(grid_link.get("xs.ref"))
    grid = ids.get(grid_ref)
    _require(grid is not None, "shared keyform grid is unresolved")
    keyforms = experiment._one_named(grid, "array_list", "keyformsOnGrid")
    bindings = experiment._one_named(grid, "array_list", "keyformBindings")
    binding_refs = [str(link.get("xs.ref")) for link in bindings]
    observed_parameter_refs: list[str] = []
    observed_keys: list[list[float]] = []
    for binding_ref in binding_refs:
        binding = ids.get(binding_ref)
        _require(binding is not None, "binding definition is unresolved")
        parameter = experiment._one_named(
            binding,
            "CParameterGuid",
            "parameterGuid",
        )
        keys = experiment._one_named(binding, "array_list", "keys")
        observed_parameter_refs.append(str(parameter.get("xs.ref")))
        observed_keys.append([float(node.text or "nan") for node in keys])

    form_refs: list[str] = []
    access_rows: list[list[int]] = []
    for keyform in keyforms:
        form_refs.append(
            str(
                experiment._one_named(
                    keyform,
                    "CFormGuid",
                    "keyformGuid",
                ).get("xs.ref")
            )
        )
        access = experiment._one_named(
            keyform,
            "array_list",
            "_keyOnParameterList",
        )
        row: list[int] = []
        for index, key_on_parameter in enumerate(access):
            binding_link = experiment._one_named(
                key_on_parameter,
                "KeyformBindingSource",
                "binding",
            )
            _require(
                binding_link.get("xs.ref") == binding_refs[index],
                "binding access order differs",
            )
            row.append(
                int(
                    experiment._one_named(
                        key_on_parameter,
                        "i",
                        "keyIndex",
                    ).text
                    or "-1"
                )
            )
        access_rows.append(row)

    _require(
        observed_parameter_refs == list(expected_parameter_refs)
        and observed_keys == [list(row) for row in expected_keys]
        and access_rows == [list(row) for row in expected_access],
        "parameter grid semantics differ",
    )
    return {
        "grid_ref": grid_ref,
        "binding_refs": binding_refs,
        "parameter_guid_refs": observed_parameter_refs,
        "keys": observed_keys,
        "form_refs": form_refs,
        "access_indices": access_rows,
    }


def _warp_binding_state(
    model: Any,
    item: Any,
    *,
    expected_parameter_refs: Sequence[str],
    expected_keys: Sequence[Sequence[float]],
    expected_access: Sequence[Sequence[int]],
    neutral_index: int,
    experiment: Any,
    canvas: Any,
) -> dict[str, Any]:
    source = model.source(item)
    state = _access_state(
        model.ids,
        source,
        expected_parameter_refs=expected_parameter_refs,
        expected_keys=expected_keys,
        expected_access=expected_access,
        experiment=experiment,
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
        source_form_refs == state["form_refs"]
        and opacities == [1.0] * len(forms)
        and model.transform(item.guid_ref).neutral_keyform_index == neutral_index,
        f"{item.name}: warp keyform semantics differ",
    )
    state.update(
        {
            "neutral_form_index": neutral_index,
            "opacities": opacities,
            "position_scalars": [
                len(
                    canvas._float_values(
                        experiment._one_named(form, "float-array", "positions"),
                        f"{item.name} form",
                    )
                )
                for form in forms
            ],
        }
    )
    return state


def _rotation_binding_state(
    root: Any,
    source: Any,
    *,
    expected_parameter_ref: str,
    experiment: Any,
) -> dict[str, Any]:
    ids = experiment._id_map(root)
    state = _access_state(
        ids,
        source,
        expected_parameter_refs=[expected_parameter_ref],
        expected_keys=[BODY_KEYS],
        expected_access=[[0], [1], [2]],
        experiment=experiment,
    )
    forms = experiment._one_named(source, "carray_list", "keyforms")
    _require(len(forms) == 3, "body Z form count differs")
    form_refs = [
        str(experiment._one_named(form, "CFormGuid", "guid").get("xs.ref"))
        for form in forms
    ]
    angles = [float(form.get("angle", "nan")) for form in forms]
    origins = [
        [float(form.get("originX", "nan")), float(form.get("originY", "nan"))]
        for form in forms
    ]
    scales = [float(form.get("scale", "nan")) for form in forms]
    _require(
        form_refs == state["form_refs"]
        and angles == [-BODY_ROLL_DEGREES, 0.0, BODY_ROLL_DEGREES]
        and origins[0] == origins[1] == origins[2]
        and scales == [1.0, 1.0, 1.0]
        and all(form.get("isReflectX") == "false" for form in forms)
        and all(form.get("isReflectY") == "false" for form in forms),
        "body Z rotation semantics differ",
    )
    state.update(
        {
            "neutral_form_index": 1,
            "angles_degrees": angles,
            "origins": origins,
            "scales": scales,
        }
    )
    return state


def _plan(source_data: bytes, stack: tuple[Any, ...]) -> tuple[bytes, dict[str, Any]]:
    (
        head_xy,
        _right,
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
    archive_before, _entry, _location, _zip_layout, main_before = (
        safe._validate_surgical_layout(source_data)
    )
    root_before = experiment._parse_xml(main_before)
    ids_before = experiment._id_map(root_before)
    model_before = canvas.GeometryModel(main_before, TOLERANCE)
    _require(
        len(model_before.objects) == EXPECTED_OBJECT_COUNT,
        "pinned source object count differs",
    )

    root_object = head._object_by_name(model_before, ROOT_NAME, ROOT_NAME)
    body_z = head._object_by_name(model_before, BODY_Z_NAME, BODY_Z_NAME)
    body_xy = head._object_by_name(model_before, BODY_XY_NAME, BODY_XY_NAME)
    breath = head._object_by_name(model_before, BREATH_NAME, BREATH_NAME)
    head_z = head._object_by_name(model_before, HEAD_Z_NAME, HEAD_Z_NAME)
    dress = head._object_by_name(model_before, DRESS_NAME, DRESS_NAME)
    _require(
        body_z.object_type == "rotation-deformer"
        and body_xy.object_type == "warp-deformer"
        and breath.object_type == "warp-deformer"
        and body_z.parent_uuid == root_object.guid_uuid
        and body_xy.parent_uuid == body_z.guid_uuid
        and breath.parent_uuid == body_xy.guid_uuid
        and head_z.parent_uuid == body_xy.guid_uuid
        and dress.parent_uuid == body_xy.guid_uuid,
        "body hierarchy differs",
    )
    direct_body_children = {
        item.name
        for item in model_before.objects
        if item.parent_uuid == body_xy.guid_uuid
    }
    direct_breath_children = {
        item.name
        for item in model_before.objects
        if item.parent_uuid == breath.guid_uuid
    }
    _require(
        direct_body_children == EXPECTED_BODY_CHILDREN,
        "D_JAD_BODY_XY direct children differ",
    )
    _require(
        direct_breath_children == EXPECTED_BREATH_CHILDREN,
        "D_JAD_BODY_BREATH direct children differ",
    )

    body_transform = model_before.transform(body_xy.guid_ref)
    breath_transform = model_before.transform(breath.guid_ref)
    _require(
        body_transform.columns == BODY_COLUMNS
        and body_transform.rows == BODY_ROWS
        and body_transform.neutral_keyform_index == 0,
        "D_JAD_BODY_XY is not the approved unbound 5x5 warp",
    )
    _require(
        breath_transform.columns == BREATH_COLUMNS
        and breath_transform.rows == BREATH_ROWS
        and breath_transform.neutral_keyform_index == 0,
        "D_JAD_BODY_BREATH is not the approved unbound 5x5 warp",
    )
    for item in (body_z, body_xy, breath):
        _require(
            head_xy._binding_parameter_ids(model_before, item, experiment) == [],
            f"{item.name}: target is already bound",
        )
    binding_inventory_before = _body_binding_inventory(
        main_before,
        experiment=experiment,
        safe=safe,
    )
    _require(
        binding_inventory_before == [],
        "body/breath parameters are already used",
    )

    parameter_nodes = {
        name: head_xy._one_shared_note(root_before, "CParameterGuid", name)
        for name in sorted(TARGET_PARAMETERS)
    }
    parameter_refs = {
        name: str(node.get("xs.id")) for name, node in parameter_nodes.items()
    }
    parameter_states_before = {
        name: _parameter_state(
            root_before,
            guid_ref=parameter_refs[name],
            expected_id=name,
            experiment=experiment,
        )
        for name in parameter_refs
    }
    _require(
        parameter_states_before["ParamBodyAngleX"]["minimum"] == -10.0
        and parameter_states_before["ParamBodyAngleX"]["maximum"] == 10.0
        and parameter_states_before["ParamBodyAngleX"]["default"] == 0.0
        and parameter_states_before["ParamBodyAngleY"]["minimum"] == -10.0
        and parameter_states_before["ParamBodyAngleY"]["maximum"] == 10.0
        and parameter_states_before["ParamBodyAngleY"]["default"] == 0.0
        and parameter_states_before["ParamBodyAngleZ"]["minimum"] == -10.0
        and parameter_states_before["ParamBodyAngleZ"]["maximum"] == 10.0
        and parameter_states_before["ParamBodyAngleZ"]["default"] == 0.0
        and parameter_states_before["ParamBreath"]["minimum"] == 0.0
        and parameter_states_before["ParamBreath"]["maximum"] == 1.0
        and parameter_states_before["ParamBreath"]["default"] == 0.0,
        "body/breath parameter ranges differ",
    )

    body_source_before = _raw_source_block(
        main_before, ids_before, body_xy, experiment
    )
    breath_source_before = _raw_source_block(
        main_before, ids_before, breath, experiment
    )
    body_z_source_before = _raw_source_block(
        main_before, ids_before, body_z, experiment
    )
    _, body_neutral_form = _keyform_payload(
        body_source_before, BODY_XY_NAME
    )
    _, breath_neutral_form = _keyform_payload(
        breath_source_before, BREATH_NAME
    )
    _, body_z_neutral_form = _keyform_payload(
        body_z_source_before, BODY_Z_NAME
    )
    body_neutral_ref = str(
        experiment._one_named(
            model_before.source(body_xy), "CFormGuid", "guid"
        ).get("xs.ref")
    )
    breath_neutral_ref = str(
        experiment._one_named(
            model_before.source(breath), "CFormGuid", "guid"
        ).get("xs.ref")
    )
    body_z_neutral_ref = str(
        experiment._one_named(
            model_before.source(body_z), "CFormGuid", "guid"
        ).get("xs.ref")
    )

    roles = [
        "body_xy_grid",
        "body_xy_binding_x",
        "body_xy_binding_y",
        *[f"body_xy_form_{index}" for index in range(9) if index != 4],
        "breath_grid",
        "breath_binding",
        "breath_form_1",
        "breath_form_2",
        "body_z_grid",
        "body_z_binding",
        "body_z_form_0",
        "body_z_form_2",
    ]
    slots = head_xy._allocate_serial_slots(root_before, roles)
    body_form_refs = tuple(
        body_neutral_ref if index == 4 else slots[f"body_xy_form_{index}"][0]
        for index in range(9)
    )
    breath_form_refs = (
        breath_neutral_ref,
        slots["breath_form_1"][0],
        slots["breath_form_2"][0],
    )
    body_z_form_refs = (
        slots["body_z_form_0"][0],
        body_z_neutral_ref,
        slots["body_z_form_2"][0],
    )
    generated_uuids = {
        _generated_uuid(role.replace("_", "-"))
        for role in roles
        if "form" in role
    }
    existing_uuids = {
        str(node.get("uuid"))
        for node in root_before.iter()
        if node.get("uuid") is not None
    }
    _require(
        not generated_uuids.intersection(existing_uuids),
        "planned form UUID collides",
    )

    body_neutral_local = scaffold._form_values(
        model_before, canvas, body_xy
    )[0]
    body_neutral_canvas = model_before.original_canvas(body_xy)
    body_parent = model_before.transform(body_z.guid_ref)
    body_form_positions: list[tuple[float, ...]] = []
    body_target_canvases: list[tuple[float, ...]] = []
    body_pose_errors: dict[str, float] = {}
    body_cell_areas: dict[str, float] = {}
    for angle_y in BODY_KEYS:
        for angle_x in BODY_KEYS:
            index = len(body_form_positions)
            target = _body_canvas_pose(body_neutral_canvas, angle_x, angle_y)
            if index == 4:
                target = tuple(body_neutral_canvas)
                local = tuple(body_neutral_local)
            else:
                local = tuple(
                    canvas._float32(value)
                    for value in model_before.inverse_many(body_parent, target)
                )
            reconstructed = model_before.forward_many(body_parent, local)
            error = canvas._maximum_error(target, reconstructed)
            label = f"x={angle_x:+.0f},y={angle_y:+.0f}"
            _require(error < TOLERANCE, f"body pose {label} exceeds tolerance")
            body_pose_errors[label] = error
            body_cell_areas[label] = _minimum_cell_area2(
                target,
                columns=BODY_COLUMNS,
                rows=BODY_ROWS,
                label=f"body {label}",
            )
            body_form_positions.append(local)
            body_target_canvases.append(target)

    breath_neutral_local = scaffold._form_values(
        model_before, canvas, breath
    )[0]
    breath_neutral_canvas = model_before.original_canvas(breath)
    breath_parent = model_before.transform(body_xy.guid_ref)
    breath_form_positions: list[tuple[float, ...]] = []
    breath_target_canvases: list[tuple[float, ...]] = []
    breath_pose_errors: dict[str, float] = {}
    breath_cell_areas: dict[str, float] = {}
    for index, amount in enumerate(BREATH_KEYS):
        target = _breath_canvas_pose(breath_neutral_canvas, amount)
        if index == 0:
            target = tuple(breath_neutral_canvas)
            local = tuple(breath_neutral_local)
        else:
            local = tuple(
                canvas._float32(value)
                for value in model_before.inverse_many(breath_parent, target)
            )
        reconstructed = model_before.forward_many(breath_parent, local)
        error = canvas._maximum_error(target, reconstructed)
        label = f"breath={amount:.1f}"
        _require(error < TOLERANCE, f"{label} exceeds tolerance")
        breath_pose_errors[label] = error
        breath_cell_areas[label] = _minimum_cell_area2(
            target,
            columns=BREATH_COLUMNS,
            rows=BREATH_ROWS,
            label=label,
        )
        breath_form_positions.append(local)
        breath_target_canvases.append(target)

    body_source_bound, preserved_body_neutral = _bind_warp_source(
        body_source_before,
        source_ref=body_xy.source_ref,
        grid_ref=slots["body_xy_grid"][0],
        neutral_form_ref=body_neutral_ref,
        neutral_index=4,
        form_refs=body_form_refs,
        form_positions=body_form_positions,
        blink=blink,
        face=face,
        experiment=experiment,
        label=BODY_XY_NAME,
    )
    breath_source_bound, preserved_breath_neutral = _bind_warp_source(
        breath_source_before,
        source_ref=breath.source_ref,
        grid_ref=slots["breath_grid"][0],
        neutral_form_ref=breath_neutral_ref,
        neutral_index=0,
        form_refs=breath_form_refs,
        form_positions=breath_form_positions,
        blink=blink,
        face=face,
        experiment=experiment,
        label=BREATH_NAME,
    )
    _require(
        preserved_body_neutral == body_neutral_form
        and preserved_breath_neutral == breath_neutral_form,
        "body/breath neutral form bytes changed",
    )
    current = experiment._replace_exact(
        main_before,
        body_source_before,
        body_source_bound,
        1,
        f"bind {BODY_XY_NAME}",
    )
    current = experiment._replace_exact(
        current,
        breath_source_before,
        breath_source_bound,
        1,
        f"bind {BREATH_NAME}",
    )

    shared_blocks = [
        gaze._grid_block(
            grid_ref=slots["body_xy_grid"][0],
            grid_idx=slots["body_xy_grid"][1],
            binding_x_ref=slots["body_xy_binding_x"][0],
            binding_y_ref=slots["body_xy_binding_y"][0],
            form_refs=body_form_refs,
        ),
        _binding_block(
            grid_ref=slots["body_xy_grid"][0],
            binding_ref=slots["body_xy_binding_x"][0],
            binding_idx=slots["body_xy_binding_x"][1],
            parameter_ref=parameter_refs["ParamBodyAngleX"],
            keys=BODY_KEYS,
            experiment=experiment,
        ),
        _binding_block(
            grid_ref=slots["body_xy_grid"][0],
            binding_ref=slots["body_xy_binding_y"][0],
            binding_idx=slots["body_xy_binding_y"][1],
            parameter_ref=parameter_refs["ParamBodyAngleY"],
            keys=BODY_KEYS,
            experiment=experiment,
        ),
        blink._grid_block(
            slots["breath_grid"][0],
            slots["breath_grid"][1],
            slots["breath_binding"][0],
            breath_form_refs,
        ),
        _binding_block(
            grid_ref=slots["breath_grid"][0],
            binding_ref=slots["breath_binding"][0],
            binding_idx=slots["breath_binding"][1],
            parameter_ref=parameter_refs["ParamBreath"],
            keys=BREATH_KEYS,
            experiment=experiment,
        ),
    ]
    for index in range(9):
        if index != 4:
            role = f"body_xy_form_{index}"
            shared_blocks.append(
                _form_guid_block(
                    *slots[role],
                    role.replace("_", "-"),
                )
            )
    for index in (1, 2):
        role = f"breath_form_{index}"
        shared_blocks.append(
            _form_guid_block(*slots[role], role.replace("_", "-"))
        )
    current = experiment._append_shared_blocks(current, shared_blocks)

    # Validate both bound warps while the parent rotation is still neutral.
    warp_model = canvas.GeometryModel(current, TOLERANCE)
    warp_body = head._object_by_name(warp_model, BODY_XY_NAME, BODY_XY_NAME)
    warp_breath = head._object_by_name(warp_model, BREATH_NAME, BREATH_NAME)
    body_binding = _warp_binding_state(
        warp_model,
        warp_body,
        expected_parameter_refs=[
            parameter_refs["ParamBodyAngleX"],
            parameter_refs["ParamBodyAngleY"],
        ],
        expected_keys=[BODY_KEYS, BODY_KEYS],
        expected_access=[
            [x_index, y_index]
            for y_index in range(3)
            for x_index in range(3)
        ],
        neutral_index=4,
        experiment=experiment,
        canvas=canvas,
    )
    breath_binding = _warp_binding_state(
        warp_model,
        warp_breath,
        expected_parameter_refs=[parameter_refs["ParamBreath"]],
        expected_keys=[BREATH_KEYS],
        expected_access=[[0], [1], [2]],
        neutral_index=0,
        experiment=experiment,
        canvas=canvas,
    )

    body_z_source_bound, preserved_body_z_neutral = _bind_rotation_source(
        body_z_source_before,
        source_ref=body_z.source_ref,
        grid_ref=slots["body_z_grid"][0],
        neutral_form_ref=body_z_neutral_ref,
        form_refs=body_z_form_refs,
        angles=(-BODY_ROLL_DEGREES, 0.0, BODY_ROLL_DEGREES),
        experiment=experiment,
        label=BODY_Z_NAME,
    )
    _require(
        preserved_body_z_neutral == body_z_neutral_form,
        "body Z neutral form bytes changed",
    )
    body_z_shared_blocks = [
        blink._grid_block(
            slots["body_z_grid"][0],
            slots["body_z_grid"][1],
            slots["body_z_binding"][0],
            body_z_form_refs,
        ),
        _binding_block(
            grid_ref=slots["body_z_grid"][0],
            binding_ref=slots["body_z_binding"][0],
            binding_idx=slots["body_z_binding"][1],
            parameter_ref=parameter_refs["ParamBodyAngleZ"],
            keys=BODY_KEYS,
            experiment=experiment,
        ),
    ]
    for index in (0, 2):
        role = f"body_z_form_{index}"
        body_z_shared_blocks.append(
            _form_guid_block(*slots[role], role.replace("_", "-"))
        )
    current = experiment._replace_exact(
        current,
        body_z_source_before,
        body_z_source_bound,
        1,
        f"bind {BODY_Z_NAME}",
    )
    current = experiment._append_shared_blocks(current, body_z_shared_blocks)

    root_after = experiment._parse_xml(current)
    ids_after = experiment._id_map(root_after)
    objects_after = safe._semantic_objects(current)
    safe._validate_deformer_graph(objects_after)
    _require(
        sorted(_object_identity(item) for item in objects_after)
        == sorted(_object_identity(item) for item in model_before.objects),
        "object identity/hierarchy changed",
    )
    _require(
        len(ids_after) == len(ids_before) + len(roles)
        and sorted(int(ref[1:]) for ref in ids_after)
        == list(range(len(ids_after))),
        "final serialized ID set differs",
    )
    shared_after = root_after.find("shared")
    _require(shared_after is not None, "final shared section is missing")
    final_indices = [int(node.get("xs.idx", "-1")) for node in shared_after]
    _require(
        len(final_indices) == len(set(final_indices)),
        "final xs.idx values collide",
    )

    body_z_after = _object_by_name(objects_after, BODY_Z_NAME)
    body_z_source_after = ids_after[body_z_after.source_ref]
    body_z_binding = _rotation_binding_state(
        root_after,
        body_z_source_after,
        expected_parameter_ref=parameter_refs["ParamBodyAngleZ"],
        experiment=experiment,
    )
    final_body_z_block = _raw_source_block(
        current, ids_after, body_z_after, experiment
    )
    _, final_body_z_forms = _keyform_payload(final_body_z_block, BODY_Z_NAME)
    rotation_forms = re.findall(
        rb"<CRotationDeformerForm .*?</CRotationDeformerForm>",
        final_body_z_forms,
        re.DOTALL,
    )
    _require(
        len(rotation_forms) == 3 and rotation_forms[1] == body_z_neutral_form,
        "body Z neutral form is not byte-exact at center",
    )

    # GeometryModel intentionally accepts only a one-form rotation parent.
    # Restore just the original body-Z source in a validation-only XML mirror;
    # the two final warp bindings remain intact and can then be reconstructed.
    geometry_xml = experiment._replace_exact(
        current,
        final_body_z_block,
        body_z_source_before,
        1,
        "neutral rotation validation mirror",
    )
    geometry_model = canvas.GeometryModel(geometry_xml, TOLERANCE)
    final_body = head._object_by_name(
        geometry_model, BODY_XY_NAME, BODY_XY_NAME
    )
    final_breath = head._object_by_name(
        geometry_model, BREATH_NAME, BREATH_NAME
    )
    final_body_source = _raw_source_block(
        geometry_xml,
        geometry_model.ids,
        final_body,
        experiment,
    )
    final_breath_source = _raw_source_block(
        geometry_xml,
        geometry_model.ids,
        final_breath,
        experiment,
    )
    _, final_body_forms = _keyform_payload(final_body_source, BODY_XY_NAME)
    _, final_breath_forms = _keyform_payload(final_breath_source, BREATH_NAME)
    body_forms = re.findall(
        rb"<CWarpDeformerForm>.*?</CWarpDeformerForm>",
        final_body_forms,
        re.DOTALL,
    )
    breath_forms = re.findall(
        rb"<CWarpDeformerForm>.*?</CWarpDeformerForm>",
        final_breath_forms,
        re.DOTALL,
    )
    _require(
        len(body_forms) == 9
        and body_forms[4] == body_neutral_form
        and len(breath_forms) == 3
        and breath_forms[0] == breath_neutral_form,
        "body/breath neutral form is not byte-exact",
    )

    body_final_values = scaffold._form_values(
        geometry_model, canvas, final_body
    )
    body_parent_final = geometry_model.transform(body_z.guid_ref)
    final_body_pose_errors: dict[str, float] = {}
    for index, (angle_y, angle_x) in enumerate(
        (y, x) for y in BODY_KEYS for x in BODY_KEYS
    ):
        reconstructed = geometry_model.forward_many(
            body_parent_final,
            body_final_values[index],
        )
        error = canvas._maximum_error(
            body_target_canvases[index], reconstructed
        )
        label = f"x={angle_x:+.0f},y={angle_y:+.0f}"
        _require(error < TOLERANCE, f"final body pose {label} differs")
        final_body_pose_errors[label] = error

    breath_final_values = scaffold._form_values(
        geometry_model, canvas, final_breath
    )
    breath_parent_final = geometry_model.transform(final_body.guid_ref)
    final_breath_pose_errors: dict[str, float] = {}
    for index, amount in enumerate(BREATH_KEYS):
        reconstructed = geometry_model.forward_many(
            breath_parent_final,
            breath_final_values[index],
        )
        error = canvas._maximum_error(
            breath_target_canvases[index], reconstructed
        )
        label = f"breath={amount:.1f}"
        _require(error < TOLERANCE, f"final {label} differs")
        final_breath_pose_errors[label] = error

    target_names = {BODY_XY_NAME, BODY_Z_NAME, BREATH_NAME}
    before_by_name = {item.name: item for item in model_before.objects}
    after_by_name = {item.name: item for item in objects_after}
    preserved_sources = 0
    for name, before_item in before_by_name.items():
        after_item = after_by_name[name]
        if name in target_names:
            continue
        _require(
            _raw_source_block(main_before, ids_before, before_item, experiment)
            == _raw_source_block(current, ids_after, after_item, experiment),
            f"{name}: non-target source changed",
        )
        preserved_sources += 1
    _require(
        head._topology_xml(
            main_before,
            experiment=experiment,
            topology=topology,
        )
        == head._topology_xml(
            current,
            experiment=experiment,
            topology=topology,
        ),
        "ArtMesh topology changed",
    )

    parameter_states_after = {
        name: _parameter_state(
            root_after,
            guid_ref=parameter_refs[name],
            expected_id=name,
            experiment=experiment,
        )
        for name in parameter_refs
    }
    _require(
        parameter_states_after == parameter_states_before,
        "body/breath parameter definitions changed",
    )
    binding_inventory_after = _body_binding_inventory(
        current,
        experiment=experiment,
        safe=safe,
    )
    expected_inventory = sorted(
        [
            {
                "name": BODY_XY_NAME,
                "object_type": "warp-deformer",
                "parameters": ["ParamBodyAngleX", "ParamBodyAngleY"],
                "keyforms": 9,
            },
            {
                "name": BODY_Z_NAME,
                "object_type": "rotation-deformer",
                "parameters": ["ParamBodyAngleZ"],
                "keyforms": 3,
            },
            {
                "name": BREATH_NAME,
                "object_type": "warp-deformer",
                "parameters": ["ParamBreath"],
                "keyforms": 3,
            },
        ],
        key=lambda row: (row["name"], row["object_type"]),
    )
    _require(
        binding_inventory_after == expected_inventory,
        "body/breath binding inventory differs",
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
        "schema": "jade.cubism.body-breath-functional-pre-cubism-audit.v1",
        "status": "ok",
        "verdict": (
            "PASS_BODY_BREATH_FUNCTIONAL__CUBISM_5_2_03_LOAD_REQUIRED"
        ),
        "operation": (
            "bind_body_xy_body_z_and_breath_to_standard_vts_parameters"
        ),
        "source_sha256": _sha256(source_data),
        "source_bytes": len(source_data),
        "planned_output_sha256": _sha256(output_data),
        "planned_output_bytes": len(output_data),
        "main_xml_sha256_before": _sha256(main_before),
        "main_xml_sha256_after": _sha256(current),
        "hierarchy": {
            "body_z_parent": ROOT_NAME,
            "body_xy_parent": BODY_Z_NAME,
            "body_xy_direct_children": sorted(direct_body_children),
            "breath_parent": BODY_XY_NAME,
            "breath_direct_children": sorted(direct_breath_children),
        },
        "bindings": {
            BODY_XY_NAME: body_binding,
            BODY_Z_NAME: body_z_binding,
            BREATH_NAME: breath_binding,
        },
        "motion": {
            "body_x_top_shift_px": BODY_X_TOP_SHIFT_PX,
            "body_x_twist_y_px": BODY_X_TWIST_Y_PX,
            "body_y_top_shift_px": BODY_Y_TOP_SHIFT_PX,
            "body_roll_degrees": BODY_ROLL_DEGREES,
            "breath_expand_x_px": BREATH_EXPAND_X_PX,
            "breath_lift_y_px": BREATH_LIFT_Y_PX,
        },
        "body_pose_reconstruction_errors_px": final_body_pose_errors,
        "breath_pose_reconstruction_errors_px": final_breath_pose_errors,
        "maximum_pose_reconstruction_error_px": max(
            *final_body_pose_errors.values(),
            *final_breath_pose_errors.values(),
        ),
        "minimum_body_cell_area2_by_pose": body_cell_areas,
        "minimum_breath_cell_area2_by_pose": breath_cell_areas,
        "minimum_cell_area2": min(
            *body_cell_areas.values(),
            *breath_cell_areas.values(),
        ),
        "neutral_forms_preserved_byte_exact": {
            BODY_XY_NAME: True,
            BODY_Z_NAME: True,
            BREATH_NAME: True,
        },
        "parameter_definitions": parameter_states_after,
        "body_binding_inventory_before": binding_inventory_before,
        "body_binding_inventory_after": binding_inventory_after,
        "preserved_non_target_object_sources": preserved_sources,
        "preserved_non_target_object_sources_byte_exact": True,
        "artwork_and_topology_unchanged": True,
        "shared_definitions_added": len(roles),
        "archive": archive_proof,
        "cubism_5_2_03_load_save_required": True,
        "grouped_visual_body_pose_check_required": True,
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
        SOURCE_BYTES > 0
        and re.fullmatch(r"[0-9A-F]{64}", SOURCE_SHA256) is not None
        and set(SOURCE_SHA256) != {"0"},
        "REPIN_AFTER_HEAD_ANGLE_Z: SOURCE_NAME/SHA256/BYTES are pending",
    )
    _require(
        source.parent == REPORTS_DIR
        and output.parent == REPORTS_DIR
        and source.name == SOURCE_NAME
        and output.name == OUTPUT_NAME
        and source != output,
        "source/output path differs from the body/breath functional gate",
    )
    _require(
        not output.exists() and not audit_path.exists(),
        "exclusive output exists",
    )
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

    safe = stack[9]
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
    except BodyBreathFunctionalError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
