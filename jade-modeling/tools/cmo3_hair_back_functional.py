#!/usr/bin/env python3
"""Add restrained back/side hair motion after Jade's front-hair checkpoint.

This transaction binds the existing ``D_JAD_HAIR_BACK_MASTER`` 5x5 warp to a
3x3 ``ParamHairSide`` / ``ParamHairBack`` grid.  The top/root remains anchored,
the exact neutral keyform is reused at the centre, artwork and hierarchy stay
unchanged, and all non-target archive members remain byte-identical.

The source gate is intentionally left unpinned until the front-hair checkpoint
has been loaded/saved by Cubism 5.2.03.  Repin only ``SOURCE_NAME``,
``SOURCE_SHA256`` and ``SOURCE_BYTES``; the BODY checkpoint constants below are
read-only structural provenance, not an executable source fallback.
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

# Canonical Cubism-saved front-hair checkpoint.
SOURCE_NAME = (
    "Jade_rig_5_2_v003.TEST_eye_lr_mouth_head_xyz_body_breath_"
    "hair_front_r01.cmo3"
)
SOURCE_SHA256 = (
    "89EE408E4890052C3A2B4F15973EFC0912767D1B3919D80339460E967AC26DD7"
)
SOURCE_BYTES = 2_048_487

OUTPUT_NAME = (
    "Jade_rig_5_2_v003.TEST_eye_lr_mouth_head_xyz_body_breath_"
    "hair_front_back_r01.cmo3"
)
AUDIT_NAME = "Jade_v003.TEST_hair_back_functional_r01_audit.json"

# Structural reference inspected while preparing this tool.  Never silently
# use it as the executable source after a front-hair checkpoint exists.
REFERENCE_BODY_NAME = (
    "Jade_rig_5_2_v003.TEST_eye_lr_mouth_head_xyz_body_breath_r01.cmo3"
)
REFERENCE_BODY_SHA256 = (
    "3692D7E38B2CEAD581C70923638A84CE2417C7EC33D857178BE93F6239A069A5"
)
REFERENCE_BODY_BYTES = 2_048_534

BODY_HELPER_NAME = "cmo3_body_breath_functional.py"
BODY_HELPER_SHA256 = (
    "5289590ACC152B04AD2CF8C6EF058C573F272F24FF917A590FD87C80F420568B"
)

TOLERANCE = 0.001
EXPECTED_OBJECT_COUNT = 93
TARGET_NAME = "D_JAD_HAIR_BACK_MASTER"
PARENT_NAME = "D_JAD_HEAD_XY"
TARGET_COLUMNS = 5
TARGET_ROWS = 5
HAIR_KEYS = (-1.0, 0.0, 1.0)
TARGET_PARAMETERS = {"ParamHairBack", "ParamHairSide"}
EXPECTED_CHILDREN = {
    "JAD_HAIR_BACK_C",
    "JAD_HAIR_BACK_L_INNER",
    "JAD_HAIR_BACK_L_OUTER",
    "JAD_HAIR_BACK_R_INNER",
    "JAD_HAIR_BACK_R_OUTER",
}

# Small physical offsets at the bottom of the rear-hair cage.  The top row is
# pinned exactly.  HairSide supplies lateral pendulum sway; HairBack adds a
# softer lift/fan response so the two physics outputs do not duplicate motion.
SIDE_SWAY_X_PX = 13.0
SIDE_TWIST_Y_PX = 2.5
BACK_FAN_X_PX = 5.0
BACK_LIFT_Y_PX = 6.0
ROOT_FALLOFF_POWER = 1.55


class HairBackFunctionalError(RuntimeError):
    """Raised when the surgical rear-hair transaction is not provably safe."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise HairBackFunctionalError(message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _load_stack() -> tuple[Any, ...]:
    helper_path = (TOOLS_DIR / BODY_HELPER_NAME).resolve(strict=True)
    _require(
        _sha256(helper_path.read_bytes()) == BODY_HELPER_SHA256,
        "pinned body/breath helper SHA-256 differs",
    )
    sys.path.insert(0, str(TOOLS_DIR))
    import cmo3_body_breath_functional as body

    _require(
        _sha256(helper_path.read_bytes()) == BODY_HELPER_SHA256,
        "body/breath helper changed while loading",
    )
    return (body, *body._load_stack())


def _generated_uuid(role: str) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"jade-cmo3-hair-back-functional:{SOURCE_SHA256}:{role}",
        )
    )


def _form_guid_block(form_ref: str, form_idx: int, role: str) -> bytes:
    return (
        f'<CFormGuid uuid="{_generated_uuid(role)}" note="(no debug info)" '
        f'xs.id="{form_ref}" xs.idx="{form_idx}" />'
    ).encode("ascii")


def _hair_canvas_pose(
    neutral_canvas: Sequence[float],
    side: float,
    back: float,
) -> tuple[float, ...]:
    xs = neutral_canvas[0::2]
    ys = neutral_canvas[1::2]
    center_x = (min(xs) + max(xs)) * 0.5
    half_width = (max(xs) - min(xs)) * 0.5
    height = max(ys) - min(ys)
    _require(half_width > 0.0 and height > 0.0, "rear-hair canvas is degenerate")
    result: list[float] = []
    for x, y in zip(xs, ys):
        horizontal = (x - center_x) / half_width
        vertical = min(1.0, max(0.0, (y - min(ys)) / height))
        weight = vertical**ROOT_FALLOFF_POWER
        # A sine envelope keeps the centre rows smooth without moving the root.
        bend = math.sin(vertical * math.pi * 0.5)
        target_x = x + weight * (
            SIDE_SWAY_X_PX * side + BACK_FAN_X_PX * back * horizontal
        )
        target_y = y + weight * SIDE_TWIST_Y_PX * side * horizontal
        target_y -= BACK_LIFT_Y_PX * back * bend
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
    width = TARGET_COLUMNS + 1
    _require(
        len(pairs) == width * (TARGET_ROWS + 1),
        "rear-hair grid size differs",
    )
    minimum = float("inf")
    for row in range(TARGET_ROWS):
        for column in range(TARGET_COLUMNS):
            p00 = pairs[row * width + column]
            p10 = pairs[row * width + column + 1]
            p01 = pairs[(row + 1) * width + column]
            p11 = pairs[(row + 1) * width + column + 1]
            areas = (
                _triangle_area2(p00, p10, p11),
                _triangle_area2(p00, p11, p01),
            )
            _require(min(areas) > 0.0, "rear-hair pose folds a grid cell")
            minimum = min(minimum, *areas)
    return minimum


def _neutral_rotation_mirror(
    main_xml: bytes,
    *,
    experiment: Any,
    safe: Any,
) -> tuple[bytes, list[str]]:
    """Return a validation-only XML with bound rotations reduced to angle 0."""
    current = main_xml
    neutralized: list[str] = []
    for item in safe._semantic_objects(main_xml):
        if item.object_type != "rotation-deformer":
            continue
        root = experiment._parse_xml(current)
        ids = experiment._id_map(root)
        source = ids.get(item.source_ref)
        _require(source is not None, f"{item.name}: rotation source is missing")
        forms = experiment._one_named(source, "carray_list", "keyforms")
        if len(forms) == 1:
            continue
        neutral_indices = [
            index
            for index, form in enumerate(forms)
            if float(form.get("angle", "nan")) == 0.0
            and float(form.get("scale", "nan")) == 1.0
            and form.get("isReflectX") == "false"
            and form.get("isReflectY") == "false"
        ]
        _require(
            len(neutral_indices) == 1,
            f"{item.name}: neutral rotation form is ambiguous",
        )
        source_block = experiment._block_by_id(
            current,
            source.tag,
            item.source_ref,
        )
        keyform_list, payload = _keyform_payload(source_block, item.name)
        form_blocks = re.findall(
            rb"<CRotationDeformerForm .*?</CRotationDeformerForm>",
            payload,
            re.DOTALL,
        )
        _require(
            len(form_blocks) == len(forms),
            f"{item.name}: serialized rotation forms differ",
        )
        replacement = (
            b'<carray_list xs.n="keyforms" count="1">\r\n'
            + form_blocks[neutral_indices[0]]
            + b"\r\n</carray_list>"
        )
        mirrored_source = (
            source_block[: keyform_list.start()]
            + replacement
            + source_block[keyform_list.end() :]
        )
        current = experiment._replace_exact(
            current,
            source_block,
            mirrored_source,
            1,
            f"neutral validation mirror for {item.name}",
        )
        neutralized.append(item.name)
    return current, neutralized


def _keyform_payload(source_block: bytes, label: str) -> tuple[Any, bytes]:
    pattern = re.compile(
        rb'<carray_list\b(?=[^>]*\bxs\.n="keyforms")[^>]*>\r\n'
        rb"(.*?)\r\n</carray_list>",
        re.DOTALL,
    )
    matches = list(pattern.finditer(source_block))
    _require(len(matches) == 1, f"{label}: keyform list is ambiguous")
    return matches[0], matches[0].group(1)


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
    sources = []
    for source in root.iter("CParameterSource"):
        field = experiment._one_named(source, "CParameterGuid", "guid")
        if field.get("xs.ref") == guid_ref:
            sources.append(source)
    _require(len(sources) == 1, f"{expected_id}: source is ambiguous")
    source = sources[0]
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
            experiment._one_named(source, "f", "defaultValue").text or "nan"
        ),
    }


def _binding_parameter_ids(
    ids: dict[str, Any],
    item: Any,
    *,
    experiment: Any,
) -> list[str]:
    source = ids.get(item.source_ref)
    _require(source is not None, f"{item.name}: source is missing")
    grid_link = experiment._one_named(
        source,
        "KeyformGridSource",
        "keyformGridSource",
    )
    grid_ref = grid_link.get("xs.ref")
    grid = ids.get(str(grid_ref)) if grid_ref else grid_link
    _require(grid is not None, f"{item.name}: keyform grid is missing")
    links = experiment._one_named(grid, "array_list", "keyformBindings")
    result: list[str] = []
    for link in links:
        binding = ids.get(str(link.get("xs.ref")))
        _require(binding is not None, f"{item.name}: binding is missing")
        parameter = experiment._one_named(
            binding,
            "CParameterGuid",
            "parameterGuid",
        )
        guid = ids.get(str(parameter.get("xs.ref")))
        _require(guid is not None, f"{item.name}: parameter GUID is missing")
        result.append(str(guid.get("note")))
    return result


def _hair_binding_inventory(
    main_xml: bytes,
    *,
    experiment: Any,
    safe: Any,
) -> list[dict[str, Any]]:
    root = experiment._parse_xml(main_xml)
    ids = experiment._id_map(root)
    rows: list[dict[str, Any]] = []
    for item in safe._semantic_objects(main_xml):
        relevant = [
            name
            for name in _binding_parameter_ids(ids, item, experiment=experiment)
            if name in TARGET_PARAMETERS
        ]
        if not relevant:
            continue
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


def _raw_source_block(
    main_xml: bytes,
    ids: dict[str, Any],
    item: Any,
    experiment: Any,
) -> bytes:
    source = ids.get(item.source_ref)
    _require(source is not None, f"{item.name}: source is unresolved")
    return experiment._block_by_id(main_xml, source.tag, item.source_ref)


def _object_identity(item: Any) -> tuple[str, str, str, str, str, str]:
    return (
        item.object_type,
        item.name,
        item.guid_uuid,
        item.guid_ref,
        item.source_ref,
        item.parent_ref,
    )


def _plan(source_data: bytes, stack: tuple[Any, ...]) -> tuple[bytes, dict[str, Any]]:
    (
        body,
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
    objects_before = safe._semantic_objects(main_before)
    _require(
        len(objects_before) == EXPECTED_OBJECT_COUNT,
        "pinned source object count differs",
    )
    target_matches = [item for item in objects_before if item.name == TARGET_NAME]
    parent_matches = [item for item in objects_before if item.name == PARENT_NAME]
    _require(len(target_matches) == 1, f"object {TARGET_NAME!r} is ambiguous")
    _require(len(parent_matches) == 1, f"object {PARENT_NAME!r} is ambiguous")
    target = target_matches[0]
    parent = parent_matches[0]
    _require(
        target.object_type == "warp-deformer"
        and target.parent_uuid == parent.guid_uuid,
        "rear-hair master identity/parent differs",
    )
    direct_children = {
        item.name for item in objects_before if item.parent_uuid == target.guid_uuid
    }
    _require(
        direct_children == EXPECTED_CHILDREN,
        "rear-hair direct ArtMesh inventory differs",
    )
    child_types = {
        item.object_type
        for item in objects_before
        if item.parent_uuid == target.guid_uuid
    }
    _require(child_types == {"art-mesh"}, "rear-hair children are not all ArtMeshes")

    target_source_before = _raw_source_block(
        main_before,
        ids_before,
        target,
        experiment,
    )
    keyform_list, neutral_form_before = _keyform_payload(
        target_source_before,
        TARGET_NAME,
    )
    _require(
        keyform_list.group(0).count(b"<CWarpDeformerForm>") == 1,
        "rear-hair master is already multi-form",
    )
    _require(
        _binding_parameter_ids(ids_before, target, experiment=experiment) == [],
        "rear-hair master is already bound",
    )
    inventory_before = _hair_binding_inventory(
        main_before,
        experiment=experiment,
        safe=safe,
    )
    _require(inventory_before == [], "rear-hair parameters are already used")

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
        all(
            state["minimum"] == -1.0
            and state["maximum"] == 1.0
            and state["default"] == 0.0
            for state in parameter_states_before.values()
        ),
        "rear-hair parameter ranges differ",
    )

    geometry_before_xml, neutralized_rotations = _neutral_rotation_mirror(
        main_before,
        experiment=experiment,
        safe=safe,
    )
    geometry_before = canvas.GeometryModel(geometry_before_xml, TOLERANCE)
    geometry_target = head._object_by_name(
        geometry_before,
        TARGET_NAME,
        TARGET_NAME,
    )
    geometry_parent = head._object_by_name(
        geometry_before,
        PARENT_NAME,
        PARENT_NAME,
    )
    target_transform = geometry_before.transform(geometry_target.guid_ref)
    _require(
        target_transform.columns == TARGET_COLUMNS
        and target_transform.rows == TARGET_ROWS
        and target_transform.neutral_keyform_index == 0,
        "rear-hair master is not the approved unbound 5x5 warp",
    )

    neutral_form_ref = str(
        experiment._one_named(
            geometry_before.source(geometry_target),
            "CFormGuid",
            "guid",
        ).get("xs.ref")
    )
    roles = [
        "hair_back_grid",
        "hair_back_binding_side",
        "hair_back_binding_back",
        *[f"hair_back_form_{index}" for index in range(9) if index != 4],
    ]
    slots = head_xy._allocate_serial_slots(root_before, roles)
    form_refs = tuple(
        neutral_form_ref
        if index == 4
        else slots[f"hair_back_form_{index}"][0]
        for index in range(9)
    )
    generated_uuids = {
        _generated_uuid(f"hair-back-form-{index}")
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
        "planned rear-hair form UUID collides",
    )

    neutral_local = scaffold._form_values(
        geometry_before,
        canvas,
        geometry_target,
    )[0]
    neutral_canvas = geometry_before.original_canvas(geometry_target)
    parent_transform = geometry_before.transform(geometry_parent.guid_ref)
    form_positions: list[tuple[float, ...]] = []
    target_canvases: list[tuple[float, ...]] = []
    pose_errors: dict[str, float] = {}
    cell_areas: dict[str, float] = {}
    for back in HAIR_KEYS:
        for side in HAIR_KEYS:
            index = len(form_positions)
            target_canvas = _hair_canvas_pose(neutral_canvas, side, back)
            if index == 4:
                local = tuple(neutral_local)
                target_canvas = tuple(neutral_canvas)
            else:
                local = tuple(
                    canvas._float32(value)
                    for value in geometry_before.inverse_many(
                        parent_transform,
                        target_canvas,
                    )
                )
            reconstructed = geometry_before.forward_many(parent_transform, local)
            error = canvas._maximum_error(target_canvas, reconstructed)
            label = f"side={side:+.0f},back={back:+.0f}"
            _require(error < TOLERANCE, f"rear-hair pose {label} exceeds tolerance")
            pose_errors[label] = error
            cell_areas[label] = _minimum_cell_area2(target_canvas)
            form_positions.append(local)
            target_canvases.append(target_canvas)

    target_source_bound, preserved_neutral = body._bind_warp_source(
        target_source_before,
        source_ref=target.source_ref,
        grid_ref=slots["hair_back_grid"][0],
        neutral_form_ref=neutral_form_ref,
        neutral_index=4,
        form_refs=form_refs,
        form_positions=form_positions,
        blink=blink,
        face=face,
        experiment=experiment,
        label=TARGET_NAME,
    )
    _require(
        preserved_neutral == neutral_form_before,
        "rear-hair neutral form bytes changed",
    )
    current = experiment._replace_exact(
        main_before,
        target_source_before,
        target_source_bound,
        1,
        f"bind {TARGET_NAME}",
    )
    shared_blocks = [
        gaze._grid_block(
            grid_ref=slots["hair_back_grid"][0],
            grid_idx=slots["hair_back_grid"][1],
            binding_x_ref=slots["hair_back_binding_side"][0],
            binding_y_ref=slots["hair_back_binding_back"][0],
            form_refs=form_refs,
        ),
        body._binding_block(
            grid_ref=slots["hair_back_grid"][0],
            binding_ref=slots["hair_back_binding_side"][0],
            binding_idx=slots["hair_back_binding_side"][1],
            parameter_ref=parameter_refs["ParamHairSide"],
            keys=HAIR_KEYS,
            experiment=experiment,
        ),
        body._binding_block(
            grid_ref=slots["hair_back_grid"][0],
            binding_ref=slots["hair_back_binding_back"][0],
            binding_idx=slots["hair_back_binding_back"][1],
            parameter_ref=parameter_refs["ParamHairBack"],
            keys=HAIR_KEYS,
            experiment=experiment,
        ),
    ]
    for index in range(9):
        if index == 4:
            continue
        shared_blocks.append(
            _form_guid_block(
                *slots[f"hair_back_form_{index}"],
                f"hair-back-form-{index}",
            )
        )
    current = experiment._append_shared_blocks(current, shared_blocks)

    root_after = experiment._parse_xml(current)
    ids_after = experiment._id_map(root_after)
    objects_after = safe._semantic_objects(current)
    safe._validate_deformer_graph(objects_after)
    _require(
        sorted(_object_identity(item) for item in objects_after)
        == sorted(_object_identity(item) for item in objects_before),
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

    geometry_after_xml, rotations_after = _neutral_rotation_mirror(
        current,
        experiment=experiment,
        safe=safe,
    )
    _require(
        rotations_after == neutralized_rotations,
        "validation-only neutral rotation inventory changed",
    )
    model_after = canvas.GeometryModel(geometry_after_xml, TOLERANCE)
    target_after = head._object_by_name(model_after, TARGET_NAME, TARGET_NAME)
    binding_state = body._warp_binding_state(
        model_after,
        target_after,
        expected_parameter_refs=[
            parameter_refs["ParamHairSide"],
            parameter_refs["ParamHairBack"],
        ],
        expected_keys=[HAIR_KEYS, HAIR_KEYS],
        expected_access=[
            [side_index, back_index]
            for back_index in range(3)
            for side_index in range(3)
        ],
        neutral_index=4,
        experiment=experiment,
        canvas=canvas,
    )
    final_target_source = _raw_source_block(
        current,
        ids_after,
        next(item for item in objects_after if item.name == TARGET_NAME),
        experiment,
    )
    _, final_form_payload = _keyform_payload(final_target_source, TARGET_NAME)
    final_form_blocks = re.findall(
        rb"<CWarpDeformerForm>.*?</CWarpDeformerForm>",
        final_form_payload,
        re.DOTALL,
    )
    _require(
        len(final_form_blocks) == 9
        and final_form_blocks[4] == neutral_form_before,
        "rear-hair neutral form is not byte-exact at centre",
    )

    final_values = scaffold._form_values(model_after, canvas, target_after)
    parent_after = head._object_by_name(model_after, PARENT_NAME, PARENT_NAME)
    parent_transform_after = model_after.transform(parent_after.guid_ref)
    final_pose_errors: dict[str, float] = {}
    for index, (back, side) in enumerate(
        (back, side) for back in HAIR_KEYS for side in HAIR_KEYS
    ):
        reconstructed = model_after.forward_many(
            parent_transform_after,
            final_values[index],
        )
        label = f"side={side:+.0f},back={back:+.0f}"
        error = canvas._maximum_error(target_canvases[index], reconstructed)
        _require(error < TOLERANCE, f"final rear-hair pose {label} differs")
        final_pose_errors[label] = error

    before_by_name = {item.name: item for item in objects_before}
    after_by_name = {item.name: item for item in objects_after}
    preserved_sources = 0
    for name, before_item in before_by_name.items():
        if name == TARGET_NAME:
            continue
        _require(
            _raw_source_block(main_before, ids_before, before_item, experiment)
            == _raw_source_block(current, ids_after, after_by_name[name], experiment),
            f"{name}: non-target source changed",
        )
        preserved_sources += 1
    _require(
        head._topology_xml(main_before, experiment=experiment, topology=topology)
        == head._topology_xml(current, experiment=experiment, topology=topology),
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
        "rear-hair parameter definitions changed",
    )
    inventory_after = _hair_binding_inventory(
        current,
        experiment=experiment,
        safe=safe,
    )
    expected_inventory = [
        {
            "name": TARGET_NAME,
            "object_type": "warp-deformer",
            "parameters": ["ParamHairSide", "ParamHairBack"],
            "keyforms": 9,
        }
    ]
    _require(inventory_after == expected_inventory, "rear-hair bindings differ")

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
        "schema": "jade.cubism.hair-back-functional-pre-cubism-audit.v1",
        "status": "ok",
        "verdict": "PASS_HAIR_BACK_FUNCTIONAL__CUBISM_5_2_03_LOAD_REQUIRED",
        "operation": "bind_rear_hair_master_to_ParamHairSide_ParamHairBack",
        "source_sha256": _sha256(source_data),
        "source_bytes": len(source_data),
        "planned_output_sha256": _sha256(output_data),
        "planned_output_bytes": len(output_data),
        "main_xml_sha256_before": _sha256(main_before),
        "main_xml_sha256_after": _sha256(current),
        "reference_body_checkpoint": {
            "name": REFERENCE_BODY_NAME,
            "sha256": REFERENCE_BODY_SHA256,
            "bytes": REFERENCE_BODY_BYTES,
        },
        "target": {
            "name": TARGET_NAME,
            "parent": PARENT_NAME,
            "divisions": [TARGET_COLUMNS, TARGET_ROWS],
            "direct_children": sorted(direct_children),
            "neutral_form_index": 4,
            "neutral_form_preserved_byte_exact": True,
            "binding": binding_state,
        },
        "motion_px": {
            "side_sway_x": SIDE_SWAY_X_PX,
            "side_twist_y": SIDE_TWIST_Y_PX,
            "back_fan_x": BACK_FAN_X_PX,
            "back_lift_y": BACK_LIFT_Y_PX,
            "root_falloff_power": ROOT_FALLOFF_POWER,
        },
        "pose_reconstruction_errors_px": final_pose_errors,
        "maximum_pose_reconstruction_error_px": max(final_pose_errors.values()),
        "minimum_cell_area2_by_pose": cell_areas,
        "minimum_cell_area2": min(cell_areas.values()),
        "validation_only_neutralized_rotations": neutralized_rotations,
        "parameter_definitions": parameter_states_after,
        "hair_binding_inventory_before": inventory_before,
        "hair_binding_inventory_after": inventory_after,
        "preserved_non_target_object_sources": preserved_sources,
        "preserved_non_target_object_sources_byte_exact": True,
        "artwork_and_topology_unchanged": True,
        "shared_definitions_added": len(roles),
        "archive": archive_proof,
        "cubism_5_2_03_load_save_required": True,
        "grouped_visual_hair_pose_check_required": True,
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
        "REPIN_AFTER_HAIR_FRONT_CUBISM_SAVE: source gate is intentionally pending",
    )
    _require(
        source.parent == REPORTS_DIR
        and output.parent == REPORTS_DIR
        and source.name == SOURCE_NAME
        and output.name == OUTPUT_NAME
        and source != output,
        "source/output path differs from the rear-hair functional gate",
    )
    _require(
        not output.exists() and not audit_path.exists(),
        "exclusive output exists",
    )
    source_data = source.read_bytes()
    _require(
        len(source_data) == SOURCE_BYTES and _sha256(source_data) == SOURCE_SHA256,
        "source bytes/SHA differs from pinned front-hair checkpoint",
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

    safe = stack[10]
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
    raise SystemExit(main())
