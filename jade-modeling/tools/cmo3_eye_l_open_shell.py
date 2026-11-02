#!/usr/bin/env python3
"""Create Jade's FACE-S2 left-eye OPEN shell transactionally.

The pinned Cubism 5.2.03 checkpoint is never modified. ``--dry-run`` performs
the complete mutation, semantic proof, archive proof and byte-exact rollback
in memory without creating an output file.
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
from typing import Any, Callable, Sequence


TOOLS_DIR = Path(__file__).resolve(strict=True).parent
PROJECT_DIR = TOOLS_DIR.parent
REPORTS_DIR = (PROJECT_DIR / "reports").resolve(strict=True)

FACE_BUILDER_NAME = "cmo3_face_fx_scaffold.py"
FACE_BUILDER_SHA256 = (
    "9A49B9FF4DD3E07B4B1551121B67162B49DA6A2B5247C9219A36BFDBD69FD2EB"
)
CONTRACT_NAME = "Jade_v003.TEST_eye_l_open_shell_r01_contract.json"
CONTRACT_SHA256 = (
    "D2498DBE84F19AE4AC28123259180BC1CFC65D042F97FFA46D57A59BE813149E"
)
CONTRACT_BYTES = 16_063
SOURCE_NAME = "Jade_rig_5_2_v003.TEST_brow_semantic_freeze_r01.cmo3"
SOURCE_SHA256 = (
    "73D0BD0523DDF6E3EF1A1D2FFBF30BC0757BDF0B1A2D7E4186DD27A012A076BA"
)
SOURCE_BYTES = 2_027_138
SOURCE_MAIN_SHA256 = (
    "D7368D9CF3738B76DC1466CB7EFA3188CB931710BB27B05443F2EFA71C437484"
)
SOURCE_MAIN_BYTES = 1_523_122
OUTPUT_NAME = "Jade_rig_5_2_v003.TEST_eye_l_open_shell_r01.cmo3"
AUDIT_NAME = "Jade_v003.TEST_eye_l_open_shell_r01_audit.json"
GATE = "FACE-S2A_EYE_L_OPEN_SHELL"
TOLERANCE = 0.001
MAX_XML_BYTES = 256 * 1024 * 1024


class EyeLOpenError(RuntimeError):
    """Raised when a pinned FACE-S2 invariant cannot be proven."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _hash_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EyeLOpenError(message)


def _load_stack() -> tuple[Any, Any, Any, Any, Any, Any, Any, Any]:
    face_path = (TOOLS_DIR / FACE_BUILDER_NAME).resolve(strict=True)
    _require(_hash_file(face_path) == FACE_BUILDER_SHA256, "FACE builder SHA differs")
    sys.path.insert(0, str(TOOLS_DIR))
    import cmo3_face_fx_scaffold as face

    head, experiment, scaffold, safe, canvas, topology, inventory = (
        face._load_stack()
    )
    _require(
        _hash_file(face_path) == FACE_BUILDER_SHA256,
        "FACE builder changed while loading",
    )
    return face, head, experiment, scaffold, safe, canvas, topology, inventory


def _load_contract(head: Any) -> tuple[dict[str, Any], Any, Path, bytes]:
    path = (REPORTS_DIR / CONTRACT_NAME).resolve(strict=True)
    raw = path.read_bytes()
    _require(
        len(raw) == CONTRACT_BYTES and _sha256(raw) == CONTRACT_SHA256,
        "FACE-S2 contract bytes/SHA differ",
    )
    try:
        contract = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EyeLOpenError(f"FACE-S2 contract JSON is invalid: {exc}") from exc
    _require(
        contract.get("gate") == GATE
        and contract.get("status") == "approved_test_only_structural_checkpoint"
        and contract.get("source", {}).get("sha256") == SOURCE_SHA256,
        "FACE-S2 contract identity differs",
    )
    branch = contract["new_branch"]
    migrations = contract["migrations"]
    expected_names = [
        "JAD_EYE_L_WHITE",
        "JAD_EYE_L_LID_SKIN",
        "JAD_EYE_L_LASH_FRAME",
    ]
    _require(
        [row["name"] for row in migrations] == expected_names,
        "left OPEN migration order differs",
    )
    spec = head.MasterSpec(
        name=branch["name"],
        internal_id=branch["internal_id"],
        object_uuid=str(uuid.UUID(branch["object_uuid"])),
        part_name=branch["part"]["name"],
        part_guid_ref=branch["part"]["guid_ref"],
        part_source_ref=contract["part"]["source_ref"],
        bounds=tuple(float(value) for value in branch["bounds_canvas"]),
        columns=int(branch["divisions"][0]),
        rows=int(branch["divisions"][1]),
        children=tuple(expected_names),
        existing_form_count=sum(int(row["keyforms"]) for row in migrations),
        existing_position_scalar_count=sum(
            int(row["position_scalars"]) for row in migrations
        ),
    )
    _require(
        spec.name == "D_JAD_EYE_L_OPEN"
        and spec.columns == 4
        and spec.rows == 3
        and spec.existing_form_count == 3
        and spec.existing_position_scalar_count == 180,
        "left OPEN dimensions/migration totals differ",
    )
    derivation = branch["uuid5_derivation"]
    roles = derivation["roles_in_value_order"]
    pattern = derivation["name_pattern"]
    generated = [
        str(uuid.uuid5(uuid.UUID(derivation["namespace"]), pattern.format(role=role)))
        for role in roles
    ]
    expected = [
        branch["object_uuid"],
        branch["form_uuid"],
        *branch["extension_uuids_in_template_order"],
    ]
    _require(generated == expected and len(set(expected)) == 5, "UUIDv5 plan differs")
    return contract, spec, path, raw


def _object_by_source(model: Any, source_ref: str, label: str) -> Any:
    matches = [item for item in model.objects if item.source_ref == source_ref]
    _require(len(matches) == 1, f"{label}: source-ref match count {len(matches)}")
    return matches[0]


def _forms(item: Any, model: Any, scaffold: Any, canvas: Any) -> tuple[tuple[float, ...], ...]:
    try:
        return tuple(scaffold._form_values(model, canvas, item))
    except Exception as exc:
        raise EyeLOpenError(f"cannot read forms for {item.name}: {exc}") from exc


def _index_plan(
    main_xml: bytes,
    *,
    contract: dict[str, Any],
    head: Any,
    experiment: Any,
) -> dict[str, Any]:
    root = experiment._parse_xml(main_xml)
    shared = root.find("shared")
    _require(shared is not None, "main.xml lacks shared definitions")
    ids = experiment._id_map(root)
    numeric_ids: list[int] = []
    for serialized_id in ids:
        _require(
            re.fullmatch(r"#\d+", serialized_id) is not None,
            f"unsupported xs.id {serialized_id!r}",
        )
        numeric_ids.append(int(serialized_id[1:]))
    maximum_id = max(numeric_ids)
    _require(
        set(numeric_ids) == set(range(maximum_id + 1)),
        "existing xs.id values are not contiguous from #0",
    )
    indices: list[int] = []
    for child in shared:
        raw = child.get("xs.idx")
        _require(raw is not None and raw.isdigit(), "shared definition lacks xs.idx")
        indices.append(int(raw))
    _require(len(indices) == len(set(indices)), "shared xs.idx values collide")
    maximum_index = max(indices)

    oracle = contract["serialization_oracle"]
    template_contract = oracle["clone_template_warp"]
    template = experiment._warp_info(root, template_contract["name"])
    _require(
        template.source_ref == template_contract["source_ref"]
        and template.source_idx == template_contract["source_idx"]
        and template.guid_ref == template_contract["guid_ref"]
        and template.guid_uuid == template_contract["uuid"]
        and template.col == 2
        and template.row == 2
        and len(template.positions) == 18
        and len(template.original_positions) == 18,
        "clone template identity/shape differs",
    )
    _, source_refs = head._source_set(root, experiment)
    expected_offsets = oracle["required_matching_relative_offsets"]
    observed_oracles: list[dict[str, Any]] = []
    for row in oracle["index_allocation_oracles"]:
        item = experiment._warp_info(root, row["name"])
        _require(
            item.source_ref == row["source_ref"]
            and item.source_idx == row["source_idx"]
            and item.guid_ref == row["guid_ref"]
            and item.guid_uuid == row["uuid"],
            f"serialization oracle {row['name']} identity differs",
        )
        offsets = {
            "source": 0,
            "form": item.form_idx - item.source_idx,
            "positions": item.positions_idx - item.source_idx,
            "deformer_guid": item.guid_idx - item.source_idx,
        }
        _require(offsets == expected_offsets, f"{row['name']} offsets differ")
        position = source_refs.index(item.source_ref)
        _require(position + 1 < len(source_refs), f"{row['name']} lacks next source")
        next_ref = source_refs[position + 1]
        next_node = ids[next_ref]
        next_raw = next_node.get("xs.idx")
        _require(next_raw is not None and next_raw.isdigit(), "next source lacks xs.idx")
        footprint = int(next_raw) - item.source_idx
        _require(
            footprint == oracle["required_observed_footprint"],
            f"{row['name']} footprint differs",
        )
        observed_oracles.append(
            {
                "name": row["name"],
                "source_ref": item.source_ref,
                "source_idx": item.source_idx,
                "next_source_ref": next_ref,
                "next_source_idx": int(next_raw),
                "relative_offsets": offsets,
                "footprint": footprint,
                "source_element_count": len(list(item.source.iter())),
            }
        )
    _require(
        maximum_id == int(oracle["pinned_source_max_xs_id"][1:])
        and maximum_index == oracle["pinned_source_max_xs_idx"],
        "source serialization tail differs",
    )
    base = maximum_index + 1
    _require(base == oracle["expected_derived_source_base_xs_idx"], "new base idx differs")
    offsets = observed_oracles[0]["relative_offsets"]
    generated_by_role = {name: base + int(offsets[name]) for name in offsets}
    _require(
        generated_by_role == oracle["expected_generated_xs_idx"],
        "generated xs.idx allocation differs",
    )
    _require(
        not set(generated_by_role.values()).intersection(indices)
        and len(set(generated_by_role.values())) == 4,
        "generated xs.idx allocation collides",
    )
    new_ids = [f"#{maximum_id + 1 + index}" for index in range(4)]
    expected_refs = oracle["expected_new_refs"]
    _require(
        new_ids
        == [
            expected_refs["source"],
            expected_refs["positions"],
            expected_refs["form"],
            expected_refs["deformer_guid"],
        ]
        and oracle["expected_new_xs_id_range"] == [new_ids[0], new_ids[-1]],
        "generated xs.id allocation differs",
    )
    return {
        "maximum_existing_xs_id": f"#{maximum_id}",
        "maximum_existing_xs_idx": maximum_index,
        "template": {
            "name": template.name,
            "source_ref": template.source_ref,
            "source_idx": template.source_idx,
            "dimensions": [template.col, template.row],
            "source_element_count": len(list(template.source.iter())),
        },
        "oracles": observed_oracles,
        "relative_offsets": offsets,
        "footprint": oracle["required_observed_footprint"],
        "source_bases": [base],
        "new_ids": new_ids,
        "generated_indices": [
            generated_by_role["source"],
            generated_by_role["form"],
            generated_by_role["positions"],
            generated_by_role["deformer_guid"],
        ],
        "generated_indices_by_role": generated_by_role,
    }


def _replace_uuid_once(
    blocks: list[bytes], old: str, new: str, label: str
) -> list[bytes]:
    needle = f'uuid="{old}"'.encode("ascii")
    replacement = f'uuid="{new}"'.encode("ascii")
    counts = [block.count(needle) for block in blocks]
    _require(sum(counts) == 1, f"{label}: UUID occurrence count differs")
    result: list[bytes] = []
    for block, count in zip(blocks, counts):
        result.append(block.replace(needle, replacement, 1) if count else block)
    return result


def _clone_open_blocks(
    main_xml: bytes,
    *,
    contract: dict[str, Any],
    spec: Any,
    index_plan: dict[str, Any],
    face: Any,
    head: Any,
    experiment: Any,
    template: Any,
    parent_ref: str,
    original_positions: Sequence[float],
    local_positions: Sequence[float],
) -> tuple[list[bytes], dict[str, Any]]:
    ids = tuple(index_plan["new_ids"])
    indices_by_role = index_plan["generated_indices_by_role"]
    indices = (
        indices_by_role["source"],
        indices_by_role["positions"],
        indices_by_role["form"],
        indices_by_role["deformer_guid"],
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
        original_positions=original_positions,
        local_positions=local_positions,
    )
    branch = contract["new_branch"]
    expected_uuids = {
        "deformer": branch["object_uuid"],
        "form": branch["form_uuid"],
        "bezier_edit_2": branch["extension_uuids_in_template_order"][0],
        "bezier_edit_3": branch["extension_uuids_in_template_order"][1],
        "original_shape": branch["extension_uuids_in_template_order"][2],
    }
    _require(
        metadata["uuids"]["deformer"] == expected_uuids["deformer"],
        "generated deformer UUID differs",
    )
    for role in ("form", "bezier_edit_2", "bezier_edit_3", "original_shape"):
        blocks = _replace_uuid_once(
            blocks,
            metadata["uuids"][role],
            expected_uuids[role],
            f"new OPEN {role}",
        )
    source_root = experiment._parse_xml(main_xml)
    source_uuids = {
        node.get("uuid") for node in source_root.iter() if node.get("uuid") is not None
    }
    _require(
        len(source_uuids) == contract["source"]["unique_uuids"]
        and not set(expected_uuids.values()).intersection(source_uuids),
        "new OPEN UUID collision/source UUID count differs",
    )
    metadata["uuids"] = expected_uuids
    return blocks, metadata


def _patch_part_after(
    main_xml: bytes,
    *,
    experiment: Any,
    face: Any,
    part_source_ref: str,
    anchor_guid_ref: str,
    new_guid_ref: str,
) -> tuple[bytes, dict[str, Any]]:
    block = experiment._block_by_id(main_xml, "CPartSource", part_source_ref)
    start, end, child_list = face._one_part_child_list(block, "36_EYE_L")
    opening = re.compile(
        rb'(<carray_list\b(?=[^>]*\bxs\.n="_childGuids")'
        rb'[^>]*\bcount=")(\d+)("[^>]*>\r\n)'
    )
    matches = list(opening.finditer(child_list))
    _require(len(matches) == 1, "36_EYE_L child-list opening is ambiguous")
    match = matches[0]
    old_count = int(match.group(2))
    new_opening = match.group(1) + str(old_count + 1).encode("ascii") + match.group(3)
    patched_list = child_list[: match.start()] + new_opening + child_list[match.end() :]
    anchor = f'<CDeformerGuid xs.ref="{anchor_guid_ref}" />\r\n'.encode("ascii")
    _require(patched_list.count(anchor) == 1, "left BASE Part anchor is ambiguous")
    insertion = f'<CDeformerGuid xs.ref="{new_guid_ref}" />\r\n'.encode("ascii")
    offset = patched_list.index(anchor) + len(anchor)
    patched_list = patched_list[:offset] + insertion + patched_list[offset:]
    patched_block = block[:start] + patched_list + block[end:]
    patched = experiment._replace_exact(
        main_xml, block, patched_block, 1, "36_EYE_L OPEN insertion"
    )
    return patched, {
        "part_source_ref": part_source_ref,
        "anchor_guid_ref": anchor_guid_ref,
        "inserted_guid_ref": new_guid_ref,
        "old_count": old_count,
        "new_count": old_count + 1,
        "insertion_index": 1,
        "all_existing_relative_order_preserved": True,
    }


def _serialization_proof(
    main_xml: bytes,
    *,
    contract: dict[str, Any],
    experiment: Any,
    scaffold: Any,
    canvas: Any,
    original_grid: Sequence[float],
    local_grid: Sequence[float],
) -> dict[str, Any]:
    target = contract["new_branch"]["serialization_target_assertions"]
    info = experiment._warp_info(
        experiment._parse_xml(main_xml), contract["new_branch"]["name"]
    )
    branch = contract["new_branch"]
    _require(
        info.name == branch["name"]
        and info.deformer_id == branch["internal_id"]
        and info.guid_uuid == branch["object_uuid"]
        and info.form_uuid == branch["form_uuid"]
        and info.source_ref == target["source_ref"]
        and info.positions_ref == target["original_shared_positions"]["ref"]
        and info.form_ref == target["neutral_form"]["form_ref"]
        and info.guid_ref == target["deformer_guid_ref"]
        and info.parent_ref == target["target_deformer_guid_ref"]
        and info.parent_part_ref == target["parent_part_guid_ref"]
        and info.col == 4
        and info.row == 3,
        "new OPEN structural references/dimensions differ",
    )
    _require(
        len(info.original_positions) == target["original_shared_positions"]["count"]
        and len(info.positions) == target["neutral_form"]["count"]
        and scaffold._f32_equal(canvas, info.original_positions, original_grid)
        and scaffold._f32_equal(canvas, info.positions, local_grid),
        "new OPEN canvas/local position arrays differ",
    )
    block = experiment._block_by_id(main_xml, "CWarpDeformerSource", info.source_ref)
    source = info.source
    visible = experiment._one_named(source, "b", "isVisible").text
    locked = experiment._one_named(source, "b", "isLocked").text
    quad = experiment._one_named(source, "b", "isQuadTransform").text
    guid_definition = experiment._id_map(experiment._parse_xml(main_xml))[info.guid_ref]
    _require(
        visible == "true"
        and locked == "false"
        and quad == "true"
        and guid_definition.get("note") == branch["guid_note"],
        "new OPEN visibility/lock/quad/GUID note differs",
    )
    direct_col = canvas._one_direct_named(source, "i", "col")
    direct_row = canvas._one_direct_named(source, "i", "row")
    deformer_super = canvas._one_direct_named(source, "ACDeformerSource", "super")
    parameter_super = canvas._one_direct_named(
        deformer_super, "ACParameterControllableSource", "super"
    )
    extensions = canvas._one_direct_named(
        parameter_super, "carray_list", "_extensions"
    )
    _require(
        len(extensions) == 3 and extensions.get("count") == "3",
        "new OPEN extension list differs",
    )
    owner_refs: list[str] = []
    for extension in extensions:
        extension_super = canvas._one_direct_named(
            extension, "ACExtension", "super"
        )
        owner = canvas._one_direct_named(
            extension_super, "CWarpDeformerSource", "_owner"
        )
        owner_refs.append(owner.get("xs.ref") or "")
    original_extensions = [
        extension
        for extension in extensions
        if extension.tag == "CDeformerOriginalShapeExtension"
    ]
    _require(
        len(original_extensions) == 1,
        "new OPEN original-shape extension count differs",
    )
    original_shape = canvas._one_direct_named(
        original_extensions[0], "WarpDeformerOriginalShape", "originalShape"
    )
    original_super = canvas._one_direct_named(
        original_shape, "ACDeformerOriginalShape", "super"
    )
    original_dimensions = [
        [
            int(canvas._one_direct_named(node, "i", "col").text or "0"),
            int(canvas._one_direct_named(node, "i", "row").text or "0"),
        ]
        for node in (original_super, original_shape)
    ]
    original_position_refs = [
        canvas._one_direct_named(node, "float-array", "positions").get("xs.ref")
        for node in (original_super, original_shape)
    ]
    grid = canvas._one_direct_named(
        parameter_super, "KeyformGridSource", "keyformGridSource"
    )
    on_grid = canvas._one_direct_named(grid, "array_list", "keyformsOnGrid")
    forms = canvas._one_direct_named(source, "carray_list", "keyforms")
    _require(
        len(on_grid) == 1
        and on_grid.get("count") == "1"
        and len(forms) == 1
        and forms.get("count") == "1",
        "new OPEN one-form serialization differs",
    )
    keyform_guid = canvas._one_direct_named(
        on_grid[0], "CFormGuid", "keyformGuid"
    ).get("xs.ref")
    deformer_form_super = canvas._one_direct_named(
        forms[0], "ACDeformerForm", "super"
    )
    ac_form = canvas._one_direct_named(deformer_form_super, "ACForm", "super")
    inline_form_guid = canvas._one_direct_named(
        ac_form, "CFormGuid", "guid"
    ).get("xs.ref")
    col_values = re.findall(rb'<i xs\.n="col">(\d+)</i>', block)
    row_values = re.findall(rb'<i xs\.n="row">(\d+)</i>', block)
    _require(
        (int(direct_col.text or "0"), int(direct_row.text or "0")) == (4, 3)
        and original_dimensions == [[4, 3], [4, 3]]
        and col_values == [b"4", b"4", b"4"]
        and row_values == [b"3", b"3", b"3"],
        "new OPEN source/two originalShape dimensions differ",
    )
    positions_token = (
        f'<float-array xs.n="positions" xs.ref="{info.positions_ref}" />'.encode(
            "ascii"
        )
    )
    owner_token = (
        f'<CWarpDeformerSource xs.n="_owner" xs.ref="{info.source_ref}" />'.encode(
            "ascii"
        )
    )
    form_token = f'xs.ref="{info.form_ref}"'.encode("ascii")
    _require(
        block.count(positions_token) == target["original_shape_positions_ref_occurrences"]
        and owner_refs == [target["extension_owner_ref"]] * 3
        and block.count(owner_token) == target["extension_owner_ref_occurrences"]
        and original_position_refs
        == [target["original_shared_positions"]["ref"]] * 2
        and block.count(form_token) == target["form_guid_ref_occurrences"],
        "new OPEN serialized reference occurrence counts differ",
    )
    _require(
        keyform_guid == target["neutral_form"]["form_ref"]
        and inline_form_guid == target["neutral_form"]["form_ref"],
        "new OPEN keyform-grid/inline-form GUID placement differs",
    )
    bezier_rows: list[dict[str, int]] = []
    for extension in info.source.iter("CWarpDeformerBezierExtension"):
        values = {
            node.get("xs.n"): int(node.text or "")
            for node in extension
            if node.tag == "i"
            and node.get("xs.n") in {"editLevel", "bezierCol", "bezierRow"}
        }
        bezier_rows.append(
            {
                "edit_level": values["editLevel"],
                "bezier_col": values["bezierCol"],
                "bezier_row": values["bezierRow"],
            }
        )
    expected_bezier = [
        {
            "edit_level": row["edit_level"],
            "bezier_col": row["bezier_col"],
            "bezier_row": row["bezier_row"],
        }
        for row in target["bezier_extensions"]
    ]
    expected_extensions = tuple(
        contract["new_branch"]["extension_uuids_in_template_order"]
    )
    _require(
        bezier_rows == expected_bezier
        and info.extension_uuids == expected_extensions,
        "new OPEN Bezier metadata/extension UUIDs differ",
    )
    return {
        "source_ref": info.source_ref,
        "positions_ref": info.positions_ref,
        "form_ref": info.form_ref,
        "guid_ref": info.guid_ref,
        "dimensions_at_source_and_two_original_shapes": [4, 3],
        "dimension_occurrences_each": 3,
        "direct_source_dimensions": [4, 3],
        "two_original_shape_dimensions": original_dimensions,
        "original_shape_position_refs_by_layer": original_position_refs,
        "original_shape_position_ref_occurrences": block.count(positions_token),
        "extension_owner_ref_occurrences": block.count(owner_token),
        "extension_owner_refs_by_extension": owner_refs,
        "form_guid_ref_occurrences": block.count(form_token),
        "keyform_grid_form_guid_ref": keyform_guid,
        "inline_form_guid_ref": inline_form_guid,
        "original_canvas_position_scalars": len(info.original_positions),
        "neutral_base_local_position_scalars": len(info.positions),
        "visible": True,
        "locked": False,
        "quad_transform": True,
        "guid_note": guid_definition.get("note"),
        "bezier_extensions": bezier_rows,
        "extension_uuids": list(info.extension_uuids),
        "exact": True,
    }


def _interpolate_angle_grid(
    form_by_pose: dict[tuple[float, float], tuple[float, ...]],
    angle_x: float,
    angle_y: float,
) -> tuple[float, ...]:
    def bracket(value: float) -> tuple[float, float, float]:
        if value <= 0.0:
            return -30.0, 0.0, (value + 30.0) / 30.0
        return 0.0, 30.0, value / 30.0

    x0, x1, tx = bracket(angle_x)
    y0, y1, ty = bracket(angle_y)
    q00 = form_by_pose[(x0, y0)]
    q10 = form_by_pose[(x1, y0)]
    q01 = form_by_pose[(x0, y1)]
    q11 = form_by_pose[(x1, y1)]
    _require(len(q00) == len(q10) == len(q01) == len(q11), "Angle grids differ")
    return tuple(
        (1.0 - tx) * (1.0 - ty) * a
        + tx * (1.0 - ty) * b
        + (1.0 - tx) * ty * c
        + tx * ty * d
        for a, b, c, d in zip(q00, q10, q01, q11)
    )


def _warp_transform(
    model: Any,
    item: Any,
    positions: Sequence[float],
    parent: Any,
    *,
    canvas: Any,
) -> Any:
    source = model.source(item)
    columns = int(canvas._one_direct_named(source, "i", "col").text or "0")
    rows = int(canvas._one_direct_named(source, "i", "row").text or "0")
    _require(
        len(positions) == 2 * (columns + 1) * (rows + 1),
        f"{item.name}: warp position count differs",
    )
    return canvas.WarpTransform(
        guid_ref=item.guid_ref,
        name=item.name,
        columns=columns,
        rows=rows,
        neutral_positions=tuple(positions),
        neutral_keyform_index=0,
        neutral_match_error_px=0.0,
        parent=parent,
    )


def _triangle_area2(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _dense_pose_proof(
    *,
    contract: dict[str, Any],
    face: Any,
    head: Any,
    experiment: Any,
    scaffold: Any,
    canvas: Any,
    before_model: Any,
    after_model: Any,
    base_before: Any,
    base_after: Any,
    open_after: Any,
) -> dict[str, Any]:
    pose_map_before = face._face_angle_pose_map(
        before_model,
        experiment=experiment,
        canvas=canvas,
        face_angle=base_before,
    )
    pose_map_after = face._face_angle_pose_map(
        after_model,
        experiment=experiment,
        canvas=canvas,
        face_angle=base_after,
    )
    _require(pose_map_before == pose_map_after, "left BASE Angle map changed")
    base_forms_before = _forms(base_before, before_model, scaffold, canvas)
    base_forms_after = _forms(base_after, after_model, scaffold, canvas)
    _require(
        len(base_forms_before) == len(base_forms_after) == 9
        and all(len(form) == 72 for form in base_forms_before)
        and all(
            scaffold._f32_equal(canvas, left, right)
            for left, right in zip(base_forms_before, base_forms_after)
        ),
        "left BASE nine-form payload changed",
    )
    form_by_pose_before = {
        tuple(row["angle_x_y"]): base_forms_before[row["form_index"]]
        for row in pose_map_before["poses"]
    }
    form_by_pose_after = {
        tuple(row["angle_x_y"]): base_forms_after[row["form_index"]]
        for row in pose_map_after["poses"]
    }
    open_forms = _forms(open_after, after_model, scaffold, canvas)
    _require(len(open_forms) == 1 and len(open_forms[0]) == 40, "OPEN form differs")

    migrated = {row["name"] for row in contract["migrations"]}
    preserved = {row["name"] for row in contract["left_eye_preservation_set"]}
    names = [row["name"] for row in contract["migrations"]] + [
        row["name"] for row in contract["left_eye_preservation_set"]
    ]
    _require(len(names) == 7 and len(set(names)) == 7, "left-eye proof set differs")
    before_items = {name: head._object_by_name(before_model, name, name) for name in names}
    after_items = {name: head._object_by_name(after_model, name, name) for name in names}
    migrated_ranges: dict[str, dict[str, float]] = {}
    for name in migrated:
        form = _forms(after_items[name], after_model, scaffold, canvas)[0]
        xs = form[0::2]
        ys = form[1::2]
        _require(min(xs) >= 0.0 and max(xs) <= 1.0 and min(ys) >= 0.0 and max(ys) <= 1.0, f"{name} leaves OPEN unit square")
        migrated_ranges[name] = {
            "min_x": min(xs),
            "max_x": max(xs),
            "min_y": min(ys),
            "max_y": max(ys),
        }

    dense_values = [float(value) for value in contract["angle_oracle"]["parameters"][0]["dense_values"]]
    rows: list[dict[str, Any]] = []
    cell_checks = 0
    min_area_a = float("inf")
    min_area_b = float("inf")
    dense_vertices = 0
    for angle_y in dense_values:
        for angle_x in dense_values:
            grid_before = _interpolate_angle_grid(form_by_pose_before, angle_x, angle_y)
            grid_after = _interpolate_angle_grid(form_by_pose_after, angle_x, angle_y)
            base_transform_before = _warp_transform(
                before_model,
                base_before,
                grid_before,
                before_model.transform(base_before.parent_ref),
                canvas=canvas,
            )
            base_transform_after = _warp_transform(
                after_model,
                base_after,
                grid_after,
                after_model.transform(base_after.parent_ref),
                canvas=canvas,
            )
            open_transform = _warp_transform(
                after_model,
                open_after,
                open_forms[0],
                base_transform_after,
                canvas=canvas,
            )
            open_canvas_grid = after_model.forward_many(base_transform_after, open_forms[0])
            points = list(zip(open_canvas_grid[0::2], open_canvas_grid[1::2]))
            for row_index in range(3):
                for column_index in range(4):
                    width = 5
                    p00 = points[row_index * width + column_index]
                    p10 = points[row_index * width + column_index + 1]
                    p01 = points[(row_index + 1) * width + column_index]
                    p11 = points[(row_index + 1) * width + column_index + 1]
                    area_a = _triangle_area2(p00, p10, p11)
                    area_b = _triangle_area2(p00, p11, p01)
                    _require(area_a > 0.0 and area_b > 0.0, "OPEN cell inverted/degenerate")
                    min_area_a = min(min_area_a, area_a)
                    min_area_b = min(min_area_b, area_b)
                    cell_checks += 1

            for name in names:
                before = before_items[name]
                after = after_items[name]
                old_forms = _forms(before, before_model, scaffold, canvas)
                new_forms = _forms(after, after_model, scaffold, canvas)
                _require(len(old_forms) == len(new_forms) == 1, f"{name}: form count differs")
                if name in migrated:
                    _require(
                        before.parent_uuid == base_before.guid_uuid
                        and after.parent_uuid == open_after.guid_uuid,
                        f"{name}: migration parent differs",
                    )
                    old_canvas = before_model.forward_many(base_transform_before, old_forms[0])
                    new_canvas = after_model.forward_many(open_transform, new_forms[0])
                elif before.parent_uuid == base_before.guid_uuid:
                    _require(after.parent_uuid == base_after.guid_uuid, f"{name}: BASE parent changed")
                    old_canvas = before_model.forward_many(base_transform_before, old_forms[0])
                    new_canvas = after_model.forward_many(base_transform_after, new_forms[0])
                else:
                    _require(name in preserved and after.parent_uuid == before.parent_uuid, f"{name}: preserved parent changed")
                    old_canvas = before_model.forward_many(before_model.transform(before.parent_ref), old_forms[0])
                    new_canvas = after_model.forward_many(after_model.transform(after.parent_ref), new_forms[0])
                error = canvas._maximum_error(old_canvas, new_canvas)
                _require(error < TOLERANCE, f"{name} pose ({angle_x},{angle_y}) error {error}px")
                vertices = len(old_forms[0]) // 2
                dense_vertices += vertices
                rows.append(
                    {
                        "object": name,
                        "object_uuid": before.guid_uuid,
                        "angle_x": angle_x,
                        "angle_y": angle_y,
                        "exact_key_pose": angle_x in (-30.0, 0.0, 30.0)
                        and angle_y in (-30.0, 0.0, 30.0),
                        "vertices": vertices,
                        "canvas_error_px": error,
                    }
                )
    exact_rows = [row for row in rows if row["exact_key_pose"]]
    oracle = contract["angle_oracle"]
    _require(
        len(rows) == oracle["dense_mesh_pose_comparisons"]
        and len(exact_rows) == oracle["exact_key_mesh_pose_comparisons"]
        and dense_vertices == oracle["dense_vertices_evaluated"]
        and 2 * dense_vertices == oracle["dense_coordinates_evaluated"]
        and cell_checks == oracle["new_open_cell_pose_checks"],
        "dense pose/cell proof cardinality differs",
    )
    return {
        "dense_pose_count": oracle["dense_pose_count"],
        "left_eye_meshes": len(names),
        "dense_mesh_pose_comparisons": len(rows),
        "exact_key_mesh_pose_comparisons": len(exact_rows),
        "dense_vertices_evaluated": dense_vertices,
        "dense_coordinates_evaluated": 2 * dense_vertices,
        "maximum_canvas_error_px": max(row["canvas_error_px"] for row in rows),
        "tolerance_px_exclusive": TOLERANCE,
        "new_open_cell_pose_checks": cell_checks,
        "minimum_doubled_triangle_area_a": min_area_a,
        "minimum_doubled_triangle_area_b": min_area_b,
        "migrated_child_local_ranges": migrated_ranges,
        "all_three_migrated_children_inside_open_unit_square": True,
        "all_open_cells_positive": True,
        "pose_map": pose_map_before,
        "rows": rows,
    }


def _normalized_existing_proof(
    before_xml: bytes,
    after_xml: bytes,
    *,
    experiment: Any,
    face: Any,
    scaffold: Any,
    canvas: Any,
    targets_before: Sequence[Any],
    targets_after_by_uuid: dict[str, Any],
    source_forms: dict[str, tuple[tuple[float, ...], ...]],
    planned_forms: dict[str, tuple[tuple[float, ...], ...]],
    old_parent_ref: str,
    new_parent_ref: str,
    part_source_ref: str,
    part_guid_ref: str,
    expected_part_children_before: Sequence[tuple[str, str]],
    expected_part_children_after: Sequence[tuple[str, str]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for before in targets_before:
        after = targets_after_by_uuid.get(before.guid_uuid)
        _require(
            after is not None and after.source_ref == before.source_ref,
            f"{before.name}: normalized identity differs",
        )
        before_block = experiment._block_by_id(
            before_xml, "CArtMeshSource", before.source_ref
        )
        after_block = experiment._block_by_id(
            after_xml, "CArtMeshSource", before.source_ref
        )
        before_parent = face._one_parent_field(
            before_block, old_parent_ref, f"{before.name} before"
        )
        face._one_parent_field(after_block, new_parent_ref, f"{before.name} after")
        before_positions = face._one_keyform_position_field(
            before_block, scaffold=scaffold, label=f"{before.name} before"
        )
        after_positions = face._one_keyform_position_field(
            after_block, scaffold=scaffold, label=f"{before.name} after"
        )
        expected_before = source_forms[before.guid_uuid]
        expected_after = planned_forms[before.guid_uuid]
        _require(
            len(expected_before) == len(expected_after) == 1
            and scaffold._f32_equal(canvas, before_positions[3], expected_before[0])
            and scaffold._f32_equal(canvas, after_positions[3], expected_after[0]),
            f"{before.name}: normalized form plan differs",
        )
        normalized = (
            after_block[: after_positions[0]]
            + before_positions[2]
            + after_block[after_positions[1] :]
        )
        normalized_parent = face._one_parent_field(
            normalized, new_parent_ref, f"{before.name} normalized"
        )
        normalized = (
            normalized[: normalized_parent[0]]
            + before_parent[2]
            + normalized[normalized_parent[1] :]
        )
        _require(
            normalized == before_block,
            f"{before.name}: non-whitelisted bytes remain after normalization",
        )
        rows.append(
            {
                "definition": "CArtMeshSource",
                "name": before.name,
                "source_ref": before.source_ref,
                "allowed_fields": [
                    "CDeformerGuid[targetDeformerGuid]/@xs.ref",
                    "keyforms[0]/float-array[positions]",
                ],
                "before_sha256": _sha256(before_block),
                "after_sha256": _sha256(after_block),
                "normalized_sha256": _sha256(normalized),
                "normalized_byte_exact": True,
            }
        )

    part_before = experiment._part_hierarchy_state(experiment._parse_xml(before_xml))
    part_after = experiment._part_hierarchy_state(experiment._parse_xml(after_xml))
    _require(
        part_before["part_children"].get(part_guid_ref)
        == list(expected_part_children_before)
        and part_after["part_children"].get(part_guid_ref)
        == list(expected_part_children_after),
        "36_EYE_L semantic child order differs",
    )
    before_part = experiment._block_by_id(before_xml, "CPartSource", part_source_ref)
    after_part = experiment._block_by_id(after_xml, "CPartSource", part_source_ref)
    before_list = face._one_part_child_list(before_part, "36_EYE_L before")
    after_list = face._one_part_child_list(after_part, "36_EYE_L after")
    normalized_part = (
        after_part[: after_list[0]] + before_list[2] + after_part[after_list[1] :]
    )
    _require(
        normalized_part == before_part,
        "36_EYE_L non-whitelisted bytes remain after normalization",
    )
    rows.append(
        {
            "definition": "CPartSource",
            "name": "36_EYE_L",
            "source_ref": part_source_ref,
            "allowed_fields": ["carray_list[_childGuids]"],
            "before_sha256": _sha256(before_part),
            "after_sha256": _sha256(after_part),
            "normalized_sha256": _sha256(normalized_part),
            "normalized_byte_exact": True,
        }
    )
    return {
        "modified_existing_definitions": len(rows),
        "allowed_existing_field_mutations": 7,
        "all_modified_existing_definitions_normalized_byte_exact": True,
        "rows": rows,
    }


def _inventory_snapshot(
    *,
    model: Any,
    inventory_xml: dict[str, Any],
    part_state: dict[str, Any],
    xml_summary: dict[str, Any],
    topology_xml: dict[str, Any],
) -> dict[str, int]:
    counts = inventory_xml["counts"]
    aggregate = topology_xml["aggregate"]
    root = model.root
    unique_uuids = len(
        {node.get("uuid") for node in root.iter() if node.get("uuid") is not None}
    )
    return {
        "objects": len(model.objects),
        "art_meshes": counts["art_meshes"],
        "warp_deformers": counts["warp_deformers"],
        "rotation_deformers": counts["rotation_deformers"],
        "deformers_total": counts["deformers_total"],
        "parts": counts["parts"],
        "part_memberships": part_state["membership_count"],
        "parameters": counts["parameters"],
        "bound_objects": counts["bound_objects"],
        "object_parameter_bindings": counts["object_parameter_bindings"],
        "keyforms_total": counts["keyforms_total"],
        "shared_definitions": xml_summary["shared_definitions"],
        "deformer_source_refs": xml_summary["deformer_source_count"],
        "unique_uuids": unique_uuids,
        "art_mesh_vertices": aggregate["vertices"],
        "art_mesh_triangles": aggregate["triangles"],
        "caff_members": 294,
    }


def _plan(
    source_data: bytes,
    *,
    contract: dict[str, Any],
    spec: Any,
    face: Any,
    head: Any,
    experiment: Any,
    scaffold: Any,
    safe: Any,
    canvas: Any,
    topology: Any,
    inventory: Any,
) -> tuple[bytes, dict[str, Any]]:
    archive_before, _, _, source_zip, main_before = safe._validate_surgical_layout(
        source_data
    )
    _require(
        len(archive_before.entries) == 294
        and len(main_before) == SOURCE_MAIN_BYTES
        and _sha256(main_before) == SOURCE_MAIN_SHA256,
        "pinned source archive/main.xml differs",
    )
    root_before = experiment._parse_xml(main_before)
    _require(
        root_before.get("fileFormatVersion") == "502030002",
        "Cubism file-format version differs",
    )
    model0 = canvas.GeometryModel(main_before, TOLERANCE)
    _require(len(model0.objects) == 84, "source object count differs")

    base_contract = contract["parent_base"]
    base0 = _object_by_source(model0, base_contract["source_ref"], "left BASE")
    _require(
        base0.object_type == "warp-deformer"
        and base0.name == base_contract["name"]
        and base0.guid_ref == base_contract["guid_ref"]
        and base0.guid_uuid == base_contract["uuid"]
        and base0.parent_ref == base_contract["parent_guid_ref"],
        "left BASE identity/parent differs",
    )
    _require(
        spec.name not in {item.name for item in model0.objects},
        "left OPEN already exists",
    )

    migration_rows = {row["name"]: row for row in contract["migrations"]}
    targets0 = [
        _object_by_source(model0, migration_rows[name]["source_ref"], name)
        for name in spec.children
    ]
    source_forms: dict[str, tuple[tuple[float, ...], ...]] = {}
    for target in targets0:
        row = migration_rows[target.name]
        forms = _forms(target, model0, scaffold, canvas)
        _require(
            target.object_type == "art-mesh"
            and target.guid_ref == row["guid_ref"]
            and target.guid_uuid == row["uuid"]
            and target.parent_ref == base0.guid_ref
            and len(forms) == row["keyforms"]
            and sum(map(len, forms)) == row["position_scalars"],
            f"{target.name}: source identity/form contract differs",
        )
        source_forms[target.guid_uuid] = forms
    preservation_rows = contract["left_eye_preservation_set"]
    for row in preservation_rows:
        item = _object_by_source(model0, row["source_ref"], row["name"])
        expected_parent = (
            base0.guid_uuid
            if row["parent_must_remain"] == base0.name
            else contract["temporary_gaze_branch_to_preserve"]["uuid"]
        )
        _require(
            item.guid_ref == row["guid_ref"]
            and item.guid_uuid == row["uuid"]
            and item.parent_uuid == expected_parent,
            f"{row['name']}: preservation anchor differs",
        )

    inventory_before = head._inventory_xml(
        main_before, experiment=experiment, inventory=inventory
    )
    part_before = experiment._part_hierarchy_state(root_before)
    before_summary = head._xml_summary(main_before, experiment=experiment, safe=safe)
    topology_before = head._topology_xml(
        main_before, experiment=experiment, topology=topology
    )
    before_snapshot = _inventory_snapshot(
        model=model0,
        inventory_xml=inventory_before,
        part_state=part_before,
        xml_summary=before_summary,
        topology_xml=topology_before,
    )
    expected_before = contract["expected_inventory_before"]
    for key, value in before_snapshot.items():
        _require(expected_before.get(key) == value, f"source inventory {key} differs")

    parameter_rows = {row["id"]: row for row in inventory_before["parameters"]}
    for frozen in contract["parameter_freeze"]:
        observed = parameter_rows.get(frozen["id"])
        _require(observed is not None, f"missing frozen parameter {frozen['id']}")
        binding_count = sum(
            row["parameters"].count(frozen["id"])
            for row in inventory_before["bound_objects"]
        )
        _require(
            binding_count == frozen["binding_count_before_and_after"],
            f"{frozen['id']} binding count differs",
        )
        if "guid_ref" in frozen:
            _require(
                observed["guid_ref"] == frozen["guid_ref"],
                f"{frozen['id']} GUID reference differs",
            )
        for field in ("minimum", "default", "maximum"):
            if field in frozen:
                _require(
                    float(observed[field]) == float(frozen[field]),
                    f"{frozen['id']} {field} differs",
                )

    part_ref = spec.part_guid_ref
    part_entity = part_before["entities"].get(part_ref)
    _require(
        part_entity is not None
        and part_entity["name"] == contract["part"]["name"]
        and part_entity["guid_uuid"] == contract["part"]["uuid"]
        and part_entity["source_ref"] == spec.part_source_ref,
        "36_EYE_L identity differs",
    )
    object_by_name = {item.name: item for item in model0.objects}
    expected_part_before: list[tuple[str, str]] = []
    for name in contract["part"]["member_order_before"]:
        item = object_by_name[name]
        tag = "CDeformerGuid" if item.object_type != "art-mesh" else "CDrawableGuid"
        expected_part_before.append((tag, item.guid_ref))
    _require(
        part_before["part_children"][part_ref] == expected_part_before,
        "36_EYE_L initial membership/order differs",
    )

    index_plan = _index_plan(
        main_before, contract=contract, head=head, experiment=experiment
    )
    template = experiment._warp_info(
        root_before, contract["serialization_oracle"]["clone_template_warp"]["name"]
    )
    original_grid = scaffold._grid(canvas, spec.columns, spec.rows, spec.bounds)
    local_grid = tuple(
        canvas._float32(value)
        for value in model0.inverse_many(model0.transform(base0.guid_ref), original_grid)
    )
    reconstructed = model0.forward_many(model0.transform(base0.guid_ref), local_grid)
    grid_error = canvas._maximum_error(original_grid, reconstructed)
    _require(grid_error < TOLERANCE, f"OPEN neutral grid error {grid_error}px")
    blocks, metadata = _clone_open_blocks(
        main_before,
        contract=contract,
        spec=spec,
        index_plan=index_plan,
        face=face,
        head=head,
        experiment=experiment,
        template=template,
        parent_ref=base0.guid_ref,
        original_positions=original_grid,
        local_positions=local_grid,
    )

    current = main_before
    undo: list[Any] = []
    whitelist: list[dict[str, Any]] = []

    def apply(label: str, operation: Callable[[bytes], bytes]) -> None:
        nonlocal current
        before = current
        after = operation(before)
        _require(after != before, f"{label}: operation made no change")
        undo.append(scaffold._make_undo_step(before, after, label))
        current = after

    apply(
        "append left OPEN shared definitions",
        lambda data: experiment._append_shared_blocks(data, blocks),
    )
    whitelist.append(
        {
            "kind": "new-shared-definitions",
            "definition_count": len(blocks),
            "source_ref": metadata["source_ref"],
        }
    )
    source_set_record: dict[str, Any] = {}

    def patch_source_set(data: bytes) -> bytes:
        nonlocal source_set_record
        patched, source_set_record = head._patch_source_set_after(
            data,
            experiment=experiment,
            anchor_ref=base0.source_ref,
            new_refs=[metadata["source_ref"]],
        )
        return patched

    apply("insert left OPEN source after left BASE", patch_source_set)
    whitelist.append({"kind": "deformer-source-set", **source_set_record})
    part_record: dict[str, Any] = {}

    def patch_part(data: bytes) -> bytes:
        nonlocal part_record
        patched, part_record = _patch_part_after(
            data,
            experiment=experiment,
            face=face,
            part_source_ref=spec.part_source_ref,
            anchor_guid_ref=base0.guid_ref,
            new_guid_ref=metadata["guid_ref"],
        )
        return patched

    apply("register left OPEN in 36_EYE_L", patch_part)
    whitelist.append({"kind": "part-membership", **part_record})

    scaffold_model = canvas.GeometryModel(current, TOLERANCE)
    open_scaffold = head._object_by_name(scaffold_model, spec.name, spec.name)
    _require(
        open_scaffold.guid_uuid == spec.object_uuid
        and open_scaffold.parent_ref == base0.guid_ref,
        "new OPEN scaffold identity/parent differs",
    )
    open_transform = scaffold_model.transform(open_scaffold.guid_ref)
    _require(
        open_transform.columns == 4
        and open_transform.rows == 3
        and open_transform.neutral_match_error_px < TOLERANCE,
        "new OPEN neutral transform differs",
    )

    parent_records: list[dict[str, Any]] = []
    position_records: list[dict[str, Any]] = []
    conversion_proof: list[dict[str, Any]] = []
    planned_forms: dict[str, tuple[tuple[float, ...], ...]] = {}
    for target0 in targets0:
        converted, proof = scaffold._convert_forms(
            canvas=canvas,
            old_model=model0,
            new_model=scaffold_model,
            old_parent=base0,
            new_parent=open_scaffold,
            target=target0,
        )
        planned_forms[target0.guid_uuid] = tuple(converted)
        parent_record: dict[str, Any] = {}

        def patch_parent(data: bytes, target: Any = target0) -> bytes:
            nonlocal parent_record
            patched, parent_record = scaffold._patch_parent_ref(
                data,
                safe=safe,
                target=target,
                expected_old_ref=base0.guid_ref,
                new_ref=open_scaffold.guid_ref,
                label=f"{target.name} -> {spec.name}",
            )
            return patched

        apply(f"reparent {target0.name} to left OPEN", patch_parent)
        parent_records.append(parent_record)
        whitelist.append(parent_record)
        current_target = head._object_by_name(
            canvas.GeometryModel(current, TOLERANCE),
            target0.name,
            f"current {target0.name}",
        )
        records: list[dict[str, Any]] = []

        def patch_forms(
            data: bytes,
            target: Any = current_target,
            expected: Any = source_forms[target0.guid_uuid],
            replacement: Any = converted,
        ) -> bytes:
            nonlocal records
            patched, records = scaffold._patch_form_positions(
                data,
                safe=safe,
                canvas=canvas,
                target=target,
                expected_old=expected,
                replacement=replacement,
                label=f"{target.name} compensated form",
            )
            return patched

        apply(f"compensate {target0.name} form", patch_forms)
        position_records.extend(records)
        whitelist.extend(records)
        conversion_proof.extend(proof)

    whitelist_contract = contract["whitelist"]
    _require(
        len(parent_records) == whitelist_contract["existing_parent_refs_changed"]
        and len(position_records)
        == whitelist_contract["existing_position_arrays_changed"]
        and sum(row["new_count"] for row in position_records)
        == whitelist_contract["existing_position_scalars_changed"]
        and len(undo) == 9,
        "transaction whitelist cardinality differs",
    )

    final_model = canvas.GeometryModel(current, TOLERANCE)
    final_by_uuid = {item.guid_uuid: item for item in final_model.objects}
    before_by_uuid = {item.guid_uuid: item for item in model0.objects}
    _require(
        set(final_by_uuid) == set(before_by_uuid) | {spec.object_uuid},
        "final object UUID set differs",
    )
    migrated_names = set(spec.children)
    for object_uuid, before in before_by_uuid.items():
        after = final_by_uuid[object_uuid]
        _require(
            (
                before.object_type,
                before.name,
                before.source_ref,
                before.guid_ref,
                before.guid_note,
            )
            == (
                after.object_type,
                after.name,
                after.source_ref,
                after.guid_ref,
                after.guid_note,
            ),
            f"existing object identity changed: {before.name}",
        )
        expected_parent_uuid = (
            spec.object_uuid if before.name in migrated_names else before.parent_uuid
        )
        _require(
            after.parent_uuid == expected_parent_uuid,
            f"existing object parent changed: {before.name}",
        )
        _require(
            model0.original_canvas(before) == final_model.original_canvas(after),
            f"original canvas payload changed: {before.name}",
        )

    open_final = final_by_uuid[spec.object_uuid]
    serialization = _serialization_proof(
        current,
        contract=contract,
        experiment=experiment,
        scaffold=scaffold,
        canvas=canvas,
        original_grid=original_grid,
        local_grid=local_grid,
    )
    observed_open_children = [
        item.name for item in head._children(final_model, open_final)
    ]
    _require(
        len(observed_open_children) == len(spec.children)
        and set(observed_open_children) == set(spec.children),
        f"final OPEN direct-child set differs: {observed_open_children!r}",
    )
    base_final = final_by_uuid[base0.guid_uuid]
    dense_proof = _dense_pose_proof(
        contract=contract,
        face=face,
        head=head,
        experiment=experiment,
        scaffold=scaffold,
        canvas=canvas,
        before_model=model0,
        after_model=final_model,
        base_before=base0,
        base_after=base_final,
        open_after=open_final,
    )
    _require(
        dense_proof["maximum_canvas_error_px"] < TOLERANCE,
        "dense left-eye preservation exceeds tolerance",
    )

    final_root = experiment._parse_xml(current)
    part_after = experiment._part_hierarchy_state(final_root)
    expected_part_after: list[tuple[str, str]] = []
    object_by_name_after = {item.name: item for item in final_model.objects}
    for name in contract["part"]["member_order_after"]:
        item = object_by_name_after[name]
        tag = "CDeformerGuid" if item.object_type != "art-mesh" else "CDrawableGuid"
        expected_part_after.append((tag, item.guid_ref))
    _require(
        part_after["part_children"][part_ref] == expected_part_after
        and part_after["membership_count"] == part_before["membership_count"] + 1,
        "final 36_EYE_L membership/order differs",
    )

    normalized_existing = _normalized_existing_proof(
        main_before,
        current,
        experiment=experiment,
        face=face,
        scaffold=scaffold,
        canvas=canvas,
        targets_before=targets0,
        targets_after_by_uuid=final_by_uuid,
        source_forms=source_forms,
        planned_forms=planned_forms,
        old_parent_ref=base0.guid_ref,
        new_parent_ref=open_final.guid_ref,
        part_source_ref=spec.part_source_ref,
        part_guid_ref=spec.part_guid_ref,
        expected_part_children_before=expected_part_before,
        expected_part_children_after=expected_part_after,
    )
    stable_shared = face._stable_shared_definition_proof(
        main_before,
        current,
        experiment=experiment,
        excluded_existing_refs={target.source_ref for target in targets0}
        | {spec.part_source_ref},
    )
    _require(
        stable_shared["existing_definitions_byte_exact"] == 1_358
        and normalized_existing["modified_existing_definitions"] == 4,
        "exhaustive existing shared-definition proof count differs",
    )
    stable_shared.update(
        {
            "normalized_modified_definitions": normalized_existing,
            "existing_definitions_proved": 1_362,
            "all_1362_existing_definitions_proved_after_normalization": True,
        }
    )

    after_summary = head._xml_summary(current, experiment=experiment, safe=safe)
    inventory_after = head._inventory_xml(
        current, experiment=experiment, inventory=inventory
    )
    topology_after = head._topology_xml(
        current, experiment=experiment, topology=topology
    )
    _require(topology_after == topology_before, "ArtMesh topology changed")
    _require(
        inventory_after["parameters"] == inventory_before["parameters"]
        and inventory_after["bound_objects"] == inventory_before["bound_objects"]
        and inventory_after["parameter_ids"] == inventory_before["parameter_ids"],
        "parameters or bindings changed",
    )
    after_snapshot = _inventory_snapshot(
        model=final_model,
        inventory_xml=inventory_after,
        part_state=part_after,
        xml_summary=after_summary,
        topology_xml=topology_after,
    )
    expected_after = contract["expected_inventory_after"]
    for key, value in after_snapshot.items():
        _require(expected_after.get(key) == value, f"final inventory {key} differs")
    _require(
        after_summary["shared_definitions"] == before_summary["shared_definitions"] + 4
        and after_summary["xs_id_count"] == before_summary["xs_id_count"] + 4
        and after_summary["xs_idx_count"] == before_summary["xs_idx_count"] + 4
        and after_summary["uuid_count"] == before_summary["uuid_count"] + 5
        and after_summary["deformer_source_count"]
        == before_summary["deformer_source_count"] + 1
        and all(
            after_summary[key]
            for key in (
                "all_xs_ids_unique",
                "all_xs_indices_unique",
                "all_uuids_unique",
                "all_references_resolved",
            )
        ),
        "serialized XML inventory delta differs",
    )

    restored = current
    for step in reversed(undo):
        restored = step.apply(restored)
    _require(restored == main_before, "undo ledger does not restore source main.xml")

    output_data = safe._replace_main_xml(source_data, current)
    archive_after, _, _, _, decoded_after = safe._validate_surgical_layout(output_data)
    _require(decoded_after == current, "planned archive main.xml differs")
    archive_proof = safe._compare_entry_preservation(
        source_data,
        archive_before,
        output_data,
        archive_after,
        main_may_change=True,
    )
    _require(
        archive_proof.get("entry_count") == 294
        and archive_proof.get("all_non_main_entries_byte_identical") is True
        and archive_proof.get("changed_stored_entries") == ["main.xml"],
        "CAFF member preservation differs",
    )

    return output_data, {
        "schema": "jade.cubism.eye-l-open-shell-pre-cubism-audit.v1",
        "status": "ok",
        "verdict": "PASS_FACE_S2B_TEST_TRANSACTION__CUBISM_5_2_03_GATE_REQUIRED",
        "gate": contract["gate"],
        "operation": "create_D_JAD_EYE_L_OPEN_and_migrate_three_open_meshes",
        "test_only": True,
        "promotion_authorized": False,
        "source_sha256": _sha256(source_data),
        "source_bytes": len(source_data),
        "planned_output_sha256": _sha256(output_data),
        "planned_output_bytes": len(output_data),
        "main_xml_sha256_before": _sha256(main_before),
        "main_xml_sha256_after": _sha256(current),
        "main_xml_bytes_before": len(main_before),
        "main_xml_bytes_after": len(current),
        "source_zlib_level": source_zip.zlib_level,
        "contract": {
            "filename": CONTRACT_NAME,
            "sha256": CONTRACT_SHA256,
            "required_editor": contract["source"]["required_editor"],
            "upgrade_forbidden": contract["source"]["upgrade_forbidden"],
        },
        "index_allocation": index_plan,
        "new_branch": {
            **metadata,
            "children": list(spec.children),
            "direct_children_in_preserved_drawable_source_order": observed_open_children,
            "keyforms": 1,
            "parameter_bindings": 0,
            "neutral_grid_reconstruction_error_px": grid_error,
            "serialization": serialization,
        },
        "conversion_proof": conversion_proof,
        "dense_angle_pose_proof": dense_proof,
        "whitelist_cardinality": {
            "new_shared_definitions": len(blocks),
            "new_unique_uuids": len(metadata["uuids"]),
            "deformer_source_refs_added": 1,
            "part_memberships_added": 1,
            "existing_parent_refs_changed": len(parent_records),
            "existing_position_arrays_changed": len(position_records),
            "existing_position_scalars_changed": sum(
                row["new_count"] for row in position_records
            ),
            "objects_deleted": 0,
        },
        "whitelist": whitelist,
        "source_set_proof": source_set_record,
        "part_membership_proof": {
            "before_memberships": part_before["membership_count"],
            "after_memberships": part_after["membership_count"],
            "part": spec.part_name,
            "ordered_members": contract["part"]["member_order_after"],
        },
        "stable_shared_definitions": stable_shared,
        "inventory_before": before_snapshot,
        "inventory_after": after_snapshot,
        "topology": topology_after,
        "archive": archive_proof,
        "undo_ledger_steps": len(undo),
        "undo_restores_source_main_xml_byte_exact": True,
        "all_other_existing_payloads_exact_by_reversible_whitelist": True,
        "cubism_5_2_03_roundtrip_required": True,
        "post_cubism_semantic_audit_required": True,
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
        _require(path.read_bytes() == payload, "written audit differs")
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
        source.name == SOURCE_NAME and output.name == OUTPUT_NAME,
        "source/output filename differs from pinned gate",
    )
    _require(
        source.parent == REPORTS_DIR and output.parent == REPORTS_DIR,
        "source/output must be direct reports children",
    )
    _require(
        source != output and not output.exists() and not audit_path.exists(),
        "source/output collision or exclusive output exists",
    )

    face, head, experiment, scaffold, safe, canvas, topology, inventory = (
        _load_stack()
    )
    contract, spec, contract_path, contract_data = _load_contract(head)
    source_data = source.read_bytes()
    _require(
        len(source_data) == SOURCE_BYTES and _sha256(source_data) == SOURCE_SHA256,
        "source bytes/SHA differs from pinned checkpoint",
    )
    output_data, audit = _plan(
        source_data,
        contract=contract,
        spec=spec,
        face=face,
        head=head,
        experiment=experiment,
        scaffold=scaffold,
        safe=safe,
        canvas=canvas,
        topology=topology,
        inventory=inventory,
    )
    tool_path = Path(__file__).resolve(strict=True)
    audit.update(
        {
            "tool": str(tool_path),
            "tool_sha256": _hash_file(tool_path),
            "contract_path": str(contract_path),
            "source": str(source),
            "output": str(output),
            "audit": str(audit_path),
            "dry_run": bool(args.dry_run),
            "output_written": False,
        }
    )
    _require(source.read_bytes() == source_data, "source changed during plan")
    _require(contract_path.read_bytes() == contract_data, "contract changed during plan")
    if args.dry_run:
        _require(
            not output.exists() and not audit_path.exists(),
            "dry-run unexpectedly created an output",
        )
        audit["verdict"] = "PASS_DRY_RUN__NO_FILE_WRITTEN"
        print(json.dumps(audit, ensure_ascii=False, sort_keys=True))
        return 0

    created_output = False
    created_audit = False
    try:
        safe._write_new_file(output, output_data)
        created_output = True
        _require(output.read_bytes() == output_data, "written output differs from plan")
        _require(source.read_bytes() == source_data, "source changed during write")
        _require(
            contract_path.read_bytes() == contract_data,
            "contract changed during write",
        )
        _, _, _, _, written_main = safe._validate_surgical_layout(output_data)
        _require(
            _sha256(written_main) == audit["main_xml_sha256_after"],
            "written main.xml hash differs",
        )
        written_topology = topology.inventory(output, MAX_XML_BYTES)
        _require(
            written_topology["aggregate"] == audit["topology"]["aggregate"],
            "written topology differs",
        )
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
    except EyeLOpenError as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
