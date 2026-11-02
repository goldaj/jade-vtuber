#!/usr/bin/env python3
"""Create Jade's FACE-S0 neutral FX scaffold transactionally.

The pinned Cubism 5.2.03 checkpoint is never modified.  The only business
changes allowed are one new unbound 2x2 warp, one Part membership, and the
canvas-preserving reparenting of the two blush ArtMeshes.  ``--dry-run``
performs the complete archive mutation, rollback and semantic audit in memory
without creating a file.
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

HEAD_BUILDER_NAME = "cmo3_head_branch_masters.py"
HEAD_BUILDER_SHA256 = (
    "33D5EBC6B0C3A0779193B2136B3A2C46E2D0A5F745E480F48DF0A8A17348155B"
)
CONTRACT_NAME = "Jade_v003.TEST_face_fx_scaffold_r01_contract.json"
CONTRACT_SHA256 = (
    "8A7DEA9152FA42040AAC23BB48D870F8A8AFE09715CABB39153FC9519E83C465"
)
SOURCE_NAME = (
    "Jade_rig_5_2_v003.TEST_head_branch_masters_r01."
    "CUBISM_roundtrip_r01.cmo3"
)
SOURCE_SHA256 = (
    "32E0C27D83CD577CA72234605AA3E54157C5757C5B75C1E0A53FBD06787C1B68"
)
SOURCE_BYTES = 2_025_458
OUTPUT_NAME = "Jade_rig_5_2_v003.TEST_face_fx_scaffold_r01.cmo3"
AUDIT_NAME = "Jade_v003.TEST_face_fx_scaffold_r01_audit.json"
TOLERANCE = 0.001
MAX_XML_BYTES = 256 * 1024 * 1024


class FaceFxError(RuntimeError):
    """Raised when the pinned FACE-S0 transaction cannot be proven."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _hash_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _load_stack() -> tuple[Any, Any, Any, Any, Any, Any, Any]:
    head_path = (TOOLS_DIR / HEAD_BUILDER_NAME).resolve(strict=True)
    if _hash_file(head_path) != HEAD_BUILDER_SHA256:
        raise FaceFxError("pinned head-branch builder SHA-256 differs")
    sys.path.insert(0, str(TOOLS_DIR))
    import cmo3_head_branch_masters as head

    experiment, scaffold, safe, canvas, topology, inventory = (
        head._load_dependencies()
    )
    if _hash_file(head_path) != HEAD_BUILDER_SHA256:
        raise FaceFxError("head-branch builder changed while loading")
    return head, experiment, scaffold, safe, canvas, topology, inventory


def _load_contract(head: Any) -> tuple[dict[str, Any], Any, Path]:
    path = (REPORTS_DIR / CONTRACT_NAME).resolve(strict=True)
    if _hash_file(path) != CONTRACT_SHA256:
        raise FaceFxError("FACE-S0 contract SHA-256 differs")
    contract = json.loads(path.read_text(encoding="utf-8"))
    if (
        contract.get("gate") != "FACE-S0_FX_SCAFFOLD"
        or contract.get("status") != "approved_test_only_structural_checkpoint"
        or contract.get("source", {}).get("sha256") != SOURCE_SHA256
    ):
        raise FaceFxError("FACE-S0 contract identity differs")
    branch = contract["new_branch"]
    migrations = contract["migrations"]
    if [row["name"] for row in migrations] != [
        "JAD_FX_BLUSH_L",
        "JAD_FX_BLUSH_R",
    ]:
        raise FaceFxError("FACE-S0 migration order differs")
    spec = head.MasterSpec(
        name=branch["name"],
        internal_id=branch["internal_id"],
        object_uuid=str(uuid.UUID(branch["object_uuid"])),
        part_name=branch["part"]["name"],
        part_guid_ref=branch["part"]["guid_ref_in_pinned_source"],
        part_source_ref=branch["part"]["source_ref_in_pinned_source"],
        bounds=tuple(float(value) for value in branch["bounds_canvas"]),
        columns=int(branch["divisions"][0]),
        rows=int(branch["divisions"][1]),
        children=tuple(row["name"] for row in migrations),
        existing_form_count=sum(int(row["keyforms"]) for row in migrations),
        existing_position_scalar_count=sum(
            int(row["position_scalars"]) for row in migrations
        ),
    )
    if (
        spec.columns != 2
        or spec.rows != 2
        or spec.existing_form_count != 2
        or spec.existing_position_scalar_count != 100
    ):
        raise FaceFxError("FACE-S0 branch dimensions or migration totals differ")
    return contract, spec, path


def _resize_float_payload(
    block: bytes,
    values: Sequence[float],
    *,
    experiment: Any,
    label: str,
) -> bytes:
    matches = list(
        re.finditer(
            rb'(<float-array\b(?=[^>]*\bcount="\d+")[^>]*>)([^<]*)(</float-array>)',
            block,
        )
    )
    if len(matches) != 1:
        raise FaceFxError(f"{label}: expected one float-array payload")
    match = matches[0]
    opening = match.group(1)
    resized_opening, count = re.subn(
        rb'\bcount="\d+"',
        f'count="{len(values)}"'.encode("ascii"),
        opening,
        count=1,
    )
    if count != 1:
        raise FaceFxError(f"{label}: float-array count is ambiguous")
    payload = " ".join(
        experiment._format_float32(value) for value in values
    ).encode("ascii")
    return (
        block[: match.start(1)]
        + resized_opening
        + payload
        + match.group(3)
        + block[match.end(3) :]
    )


def _clone_fx_blocks(
    main_xml: bytes,
    *,
    head: Any,
    experiment: Any,
    template: Any,
    spec: Any,
    ids: tuple[str, str, str, str],
    indices: tuple[int, int, int, int],
    parent_ref: str,
    original_positions: Sequence[float],
    local_positions: Sequence[float],
) -> tuple[list[bytes], dict[str, Any]]:
    blocks, metadata = head._clone_master_blocks(
        main_xml,
        experiment=experiment,
        template=template,
        spec=spec,
        source_sha=SOURCE_SHA256,
        ids=ids,
        indices=indices,
        parent_ref=parent_ref,
        original_positions=template.original_positions,
        local_positions=template.positions,
    )
    source_block = blocks[0]
    source_block = experiment._replace_exact(
        source_block,
        f'<i xs.n="col">{template.col}</i>'.encode("ascii"),
        f'<i xs.n="col">{spec.columns}</i>'.encode("ascii"),
        3,
        "D_JAD_FACE_FX column count",
    )
    source_block = experiment._replace_exact(
        source_block,
        f'<i xs.n="row">{template.row}</i>'.encode("ascii"),
        f'<i xs.n="row">{spec.rows}</i>'.encode("ascii"),
        3,
        "D_JAD_FACE_FX row count",
    )
    source_block = _resize_float_payload(
        source_block,
        local_positions,
        experiment=experiment,
        label="D_JAD_FACE_FX local grid",
    )
    positions_block = _resize_float_payload(
        blocks[1],
        original_positions,
        experiment=experiment,
        label="D_JAD_FACE_FX original grid",
    )
    metadata["original_position_scalars"] = len(original_positions)
    metadata["neutral_local_position_scalars"] = len(local_positions)
    return [source_block, positions_block, blocks[2], blocks[3]], metadata


_PARENT_FIELD_PATTERN = re.compile(
    rb'(<CDeformerGuid\b(?=[^>]*\bxs\.n="targetDeformerGuid")'
    rb'(?=[^>]*\bxs\.ref=")[^>]*\bxs\.ref=")([^"\s]+)("[^>]*/>)'
)


def _one_parent_field(block: bytes, expected_ref: str, label: str) -> tuple[int, int, bytes]:
    matches = list(_PARENT_FIELD_PATTERN.finditer(block))
    if len(matches) != 1:
        raise FaceFxError(f"{label}: parent field count {len(matches)}")
    match = matches[0]
    observed = match.group(2).decode("ascii")
    if observed != expected_ref:
        raise FaceFxError(
            f"{label}: parent reference {observed!r} != {expected_ref!r}"
        )
    return match.start(), match.end(), match.group(0)


def _one_keyform_position_field(
    block: bytes,
    *,
    scaffold: Any,
    label: str,
) -> tuple[int, int, bytes, tuple[float, ...]]:
    list_start, _, matches = scaffold._keyform_payload_matches(block)
    if len(matches) != 1:
        raise FaceFxError(f"{label}: keyform position field count {len(matches)}")
    match = matches[0]
    try:
        values = tuple(float(token) for token in match.group(4).split())
    except ValueError as exc:
        raise FaceFxError(f"{label}: nonnumeric keyform position payload") from exc
    if int(match.group(2)) != len(values):
        raise FaceFxError(f"{label}: keyform position count differs")
    return (
        list_start + match.start(),
        list_start + match.end(),
        match.group(0),
        values,
    )


def _one_part_child_list(block: bytes, label: str) -> tuple[int, int, bytes]:
    openings = list(
        re.finditer(
            rb'<carray_list\b(?=[^>]*\bxs\.n="_childGuids")[^>]*>',
            block,
        )
    )
    if len(openings) != 1:
        raise FaceFxError(f"{label}: _childGuids opening count {len(openings)}")
    opening = openings[0]
    closing = b"</carray_list>"
    close = block.find(closing, opening.end())
    if close < 0:
        raise FaceFxError(f"{label}: _childGuids list is unclosed")
    inner = block[opening.end() : close]
    if b"<carray_list" in inner or b"</carray_list>" in inner:
        raise FaceFxError(f"{label}: nested list inside _childGuids")
    end = close + len(closing)
    return opening.start(), end, block[opening.start() : end]


def _normalized_existing_block_proof(
    before_xml: bytes,
    after_xml: bytes,
    *,
    experiment: Any,
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
    """Prove every byte in the three modified existing definitions.

    The after blocks are normalized by restoring only the five contractually
    allowed fields.  Byte identity with the before blocks then proves that no
    opacity, color, clipping, draw-order, texture, Part identity or other
    payload changed alongside the intended transaction.
    """

    rows: list[dict[str, Any]] = []
    for before in targets_before:
        after = targets_after_by_uuid.get(before.guid_uuid)
        if after is None or after.source_ref != before.source_ref:
            raise FaceFxError(f"{before.name}: normalized proof identity differs")
        before_block = experiment._block_by_id(
            before_xml, "CArtMeshSource", before.source_ref
        )
        after_block = experiment._block_by_id(
            after_xml, "CArtMeshSource", before.source_ref
        )
        before_parent = _one_parent_field(
            before_block, old_parent_ref, f"{before.name} before"
        )
        after_parent = _one_parent_field(
            after_block, new_parent_ref, f"{before.name} after"
        )
        before_positions = _one_keyform_position_field(
            before_block, scaffold=scaffold, label=f"{before.name} before"
        )
        after_positions = _one_keyform_position_field(
            after_block, scaffold=scaffold, label=f"{before.name} after"
        )
        expected_before = source_forms.get(before.guid_uuid)
        expected_after = planned_forms.get(before.guid_uuid)
        if expected_before is None or expected_after is None:
            raise FaceFxError(f"{before.name}: normalized proof lacks planned forms")
        if len(expected_before) != 1 or len(expected_after) != 1:
            raise FaceFxError(f"{before.name}: normalized proof expects one form")
        if not scaffold._f32_equal(canvas, before_positions[3], expected_before[0]):
            raise FaceFxError(f"{before.name}: before positions differ from source plan")
        if not scaffold._f32_equal(canvas, after_positions[3], expected_after[0]):
            raise FaceFxError(f"{before.name}: after positions differ from migration plan")

        normalized = (
            after_block[: after_positions[0]]
            + before_positions[2]
            + after_block[after_positions[1] :]
        )
        normalized_parent = _one_parent_field(
            normalized, new_parent_ref, f"{before.name} normalized"
        )
        normalized = (
            normalized[: normalized_parent[0]]
            + before_parent[2]
            + normalized[normalized_parent[1] :]
        )
        if normalized != before_block:
            raise FaceFxError(
                f"{before.name}: non-whitelisted bytes remain after normalization"
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
    if part_before["part_children"].get(part_guid_ref) != list(
        expected_part_children_before
    ):
        raise FaceFxError("80_FX before semantic child order differs")
    if part_after["part_children"].get(part_guid_ref) != list(
        expected_part_children_after
    ):
        raise FaceFxError("80_FX after semantic child order differs")
    before_part_block = experiment._block_by_id(
        before_xml, "CPartSource", part_source_ref
    )
    after_part_block = experiment._block_by_id(
        after_xml, "CPartSource", part_source_ref
    )
    before_list = _one_part_child_list(before_part_block, "80_FX before")
    after_list = _one_part_child_list(after_part_block, "80_FX after")
    normalized_part = (
        after_part_block[: after_list[0]]
        + before_list[2]
        + after_part_block[after_list[1] :]
    )
    if normalized_part != before_part_block:
        raise FaceFxError(
            "80_FX: non-whitelisted bytes remain after membership normalization"
        )
    rows.append(
        {
            "definition": "CPartSource",
            "name": "80_FX",
            "source_ref": part_source_ref,
            "allowed_fields": ["carray_list[_childGuids]"],
            "before_sha256": _sha256(before_part_block),
            "after_sha256": _sha256(after_part_block),
            "normalized_sha256": _sha256(normalized_part),
            "normalized_byte_exact": True,
        }
    )
    return {
        "modified_existing_definitions": len(rows),
        "allowed_existing_field_mutations": 5,
        "all_modified_existing_definitions_normalized_byte_exact": True,
        "rows": rows,
    }


def _stable_shared_definition_proof(
    before_xml: bytes,
    after_xml: bytes,
    *,
    experiment: Any,
    excluded_existing_refs: set[str],
) -> dict[str, Any]:
    before_root = experiment._parse_xml(before_xml)
    after_root = experiment._parse_xml(after_xml)
    before_shared = before_root.find("shared")
    after_shared = after_root.find("shared")
    if before_shared is None or after_shared is None:
        raise FaceFxError("shared definition set is missing")
    after_ids = {node.get("xs.id") for node in after_shared}
    checked = 0
    for node in before_shared:
        ref = node.get("xs.id")
        if ref is None or ref in excluded_existing_refs:
            continue
        if ref not in after_ids:
            raise FaceFxError(f"stable shared definition {ref} disappeared")
        before_block = experiment._block_by_id(before_xml, node.tag, ref)
        after_block = experiment._block_by_id(after_xml, node.tag, ref)
        if before_block != after_block:
            raise FaceFxError(f"stable shared definition {ref} changed")
        checked += 1
    return {
        "excluded_existing_refs": sorted(excluded_existing_refs),
        "existing_definitions_byte_exact": checked,
        "all_non_whitelisted_existing_definitions_byte_exact": True,
    }


def _resolved_definition(
    model: Any,
    field: Any,
    expected_tag: str,
    label: str,
) -> tuple[str, Any]:
    reference = field.get("xs.ref") or ""
    target = model.ids.get(reference)
    if target is None or target.tag != expected_tag:
        raise FaceFxError(
            f"{label}: reference {reference!r} does not resolve to {expected_tag}"
        )
    return reference, target


def _face_angle_pose_map(
    model: Any,
    *,
    experiment: Any,
    canvas: Any,
    face_angle: Any,
) -> dict[str, Any]:
    """Resolve FACE Angle's bindings, access keys and form order explicitly."""

    source = model.source(face_angle)
    grid_field = experiment._one_named(
        source, "KeyformGridSource", "keyformGridSource"
    )
    grid_ref, grid = _resolved_definition(
        model, grid_field, "KeyformGridSource", "FACE Angle keyform grid"
    )
    binding_list = canvas._one_direct_named(
        grid, "array_list", "keyformBindings"
    )
    binding_refs = [node.get("xs.ref") or "" for node in binding_list]
    if (
        binding_list.get("count") != "2"
        or len(binding_refs) != 2
        or len(set(binding_refs)) != 2
    ):
        raise FaceFxError("FACE Angle must expose two unique keyform bindings")

    parameter_set = model.root.find("main/CModelSource/CParameterSourceSet")
    if parameter_set is None:
        raise FaceFxError("model lacks CParameterSourceSet")
    parameter_ids_by_guid: dict[str, str] = {}
    for parameter in parameter_set.iter("CParameterSource"):
        guid_field = experiment._one_named(parameter, "CParameterGuid", "guid")
        guid_ref = guid_field.get("xs.ref") or ""
        id_field = experiment._one_named(parameter, "CParameterId", "id")
        _, id_definition = _resolved_definition(
            model, id_field, "CParameterId", f"parameter {guid_ref} ID"
        )
        parameter_id = id_definition.get("idstr") or ""
        if not guid_ref or not parameter_id or guid_ref in parameter_ids_by_guid:
            raise FaceFxError("parameter GUID/ID mapping is ambiguous")
        parameter_ids_by_guid[guid_ref] = parameter_id

    binding_rows: list[dict[str, Any]] = []
    binding_by_ref: dict[str, dict[str, Any]] = {}
    for binding_ref in binding_refs:
        binding = model.ids.get(binding_ref)
        if binding is None or binding.tag != "KeyformBindingSource":
            raise FaceFxError(
                f"FACE Angle binding {binding_ref!r} is unresolved"
            )
        backref = experiment._one_named(
            binding, "KeyformGridSource", "_gridSource"
        ).get("xs.ref")
        if backref != grid_ref:
            raise FaceFxError("FACE Angle binding grid back-reference differs")
        parameter_field = experiment._one_named(
            binding, "CParameterGuid", "parameterGuid"
        )
        parameter_ref, parameter_definition = _resolved_definition(
            model,
            parameter_field,
            "CParameterGuid",
            f"FACE Angle binding {binding_ref} parameter",
        )
        parameter_id = parameter_ids_by_guid.get(parameter_ref, "")
        if parameter_definition.get("note") != parameter_id:
            raise FaceFxError(
                f"FACE Angle parameter GUID note differs for {parameter_id!r}"
            )
        keys = canvas._one_direct_named(binding, "array_list", "keys")
        try:
            key_values = tuple(float(node.text or "") for node in keys)
        except ValueError as exc:
            raise FaceFxError("FACE Angle binding contains a nonnumeric key") from exc
        expected_keys = (-30.0, 0.0, 30.0)
        if (
            keys.get("count") != "3"
            or len(keys) != 3
            or any(node.tag != "f" for node in keys)
            or tuple(canvas._float32(value) for value in key_values)
            != expected_keys
        ):
            raise FaceFxError(
                f"FACE Angle {parameter_id!r} keys differ from [-30, 0, 30]"
            )
        row = {
            "binding_ref": binding_ref,
            "parameter_guid_ref": parameter_ref,
            "parameter_id": parameter_id,
            "keys": list(expected_keys),
        }
        binding_rows.append(row)
        binding_by_ref[binding_ref] = row
    if [row["parameter_id"] for row in binding_rows] != [
        "ParamAngleX",
        "ParamAngleY",
    ]:
        raise FaceFxError("FACE Angle binding order is not Angle X then Angle Y")

    forms = canvas._one_direct_named(source, "carray_list", "keyforms")
    if forms.get("count") != "9" or len(forms) != 9:
        raise FaceFxError("FACE Angle form list is not exactly nine forms")
    form_guid_refs: list[str] = []
    for index, form in enumerate(forms):
        guid_ref = experiment._one_named(form, "CFormGuid", "guid").get(
            "xs.ref"
        )
        if not guid_ref or guid_ref not in model.ids:
            raise FaceFxError(f"FACE Angle form {index} GUID is unresolved")
        form_guid_refs.append(guid_ref)
    if len(set(form_guid_refs)) != 9:
        raise FaceFxError("FACE Angle form GUIDs are not unique")

    on_grid = canvas._one_direct_named(grid, "array_list", "keyformsOnGrid")
    if on_grid.get("count") != "9" or len(on_grid) != 9:
        raise FaceFxError("FACE Angle keyformsOnGrid is not exactly nine rows")
    expected_pairs = [
        (-30.0, -30.0),
        (0.0, -30.0),
        (30.0, -30.0),
        (-30.0, 0.0),
        (0.0, 0.0),
        (30.0, 0.0),
        (-30.0, 30.0),
        (0.0, 30.0),
        (30.0, 30.0),
    ]
    poses: list[dict[str, Any]] = []
    for form_index, keyform in enumerate(on_grid):
        if keyform.tag != "KeyformOnGrid":
            raise FaceFxError(f"FACE Angle grid row {form_index} has wrong type")
        access = canvas._one_direct_named(
            keyform, "KeyformGridAccessKey", "accessKey"
        )
        key_list = canvas._one_direct_named(
            access, "array_list", "_keyOnParameterList"
        )
        if key_list.get("count") != "2" or len(key_list) != 2:
            raise FaceFxError(
                f"FACE Angle grid row {form_index} lacks two access keys"
            )
        indices_by_binding: dict[str, int] = {}
        for key_on_parameter in key_list:
            if key_on_parameter.tag != "KeyOnParameter":
                raise FaceFxError(
                    f"FACE Angle grid row {form_index} access-key type differs"
                )
            binding_ref = experiment._one_named(
                key_on_parameter, "KeyformBindingSource", "binding"
            ).get("xs.ref") or ""
            key_index_node = experiment._one_named(
                key_on_parameter, "i", "keyIndex"
            )
            try:
                key_index = int(key_index_node.text or "")
            except ValueError as exc:
                raise FaceFxError("FACE Angle keyIndex is nonnumeric") from exc
            if (
                binding_ref not in binding_by_ref
                or binding_ref in indices_by_binding
                or key_index not in (0, 1, 2)
            ):
                raise FaceFxError(
                    f"FACE Angle grid row {form_index} access-key mapping differs"
                )
            indices_by_binding[binding_ref] = key_index
        if set(indices_by_binding) != set(binding_refs):
            raise FaceFxError(
                f"FACE Angle grid row {form_index} does not cover both bindings"
            )
        x_index = indices_by_binding[binding_refs[0]]
        y_index = indices_by_binding[binding_refs[1]]
        pair = (
            binding_by_ref[binding_refs[0]]["keys"][x_index],
            binding_by_ref[binding_refs[1]]["keys"][y_index],
        )
        keyform_guid = experiment._one_named(
            keyform, "CFormGuid", "keyformGuid"
        ).get("xs.ref")
        if keyform_guid != form_guid_refs[form_index]:
            raise FaceFxError(
                f"FACE Angle grid row {form_index} points to the wrong form GUID"
            )
        if pair != expected_pairs[form_index]:
            raise FaceFxError(
                f"FACE Angle grid row {form_index} maps to {pair!r}, "
                f"expected {expected_pairs[form_index]!r}"
            )
        poses.append(
            {
                "form_index": form_index,
                "form_guid_ref": keyform_guid,
                "key_indices": [x_index, y_index],
                "angle_x_y": list(pair),
            }
        )
    if len({tuple(row["angle_x_y"]) for row in poses}) != 9:
        raise FaceFxError("FACE Angle access keys do not form a Cartesian product")
    return {
        "grid_ref": grid_ref,
        "bindings": binding_rows,
        "poses": poses,
        "cartesian_pose_count": 9,
        "form_order_matches_keyform_grid": True,
    }


def _angle_pose_proof(
    *,
    canvas: Any,
    scaffold: Any,
    old_model: Any,
    final_model: Any,
    face_angle_before: Any,
    fx_after: Any,
    targets_before: Sequence[Any],
    targets_after_by_uuid: dict[str, Any],
    pose_map: dict[str, Any],
) -> dict[str, Any]:
    face_forms = scaffold._form_values(old_model, canvas, face_angle_before)
    if len(face_forms) != 9 or any(len(form) != 72 for form in face_forms):
        raise FaceFxError("D_JAD_FACE_ANGLE_XY does not expose nine 5x5 forms")
    face_parent = old_model.transform(face_angle_before.parent_ref)
    fx_transform = final_model.transform(fx_after.guid_ref)
    inner_fx = canvas.WarpTransform(
        guid_ref=fx_after.guid_ref,
        name=fx_after.name,
        columns=fx_transform.columns,
        rows=fx_transform.rows,
        neutral_positions=fx_transform.neutral_positions,
        neutral_keyform_index=0,
        neutral_match_error_px=0.0,
        parent=canvas.IdentityTransform(
            guid_ref="FACE_LOCAL",
            guid_uuid="00000000-0000-0000-0000-000000000000",
        ),
    )
    pose_rows = pose_map.get("poses", [])
    if len(pose_rows) != 9:
        raise FaceFxError("FACE Angle pose map does not contain nine poses")
    rows: list[dict[str, Any]] = []
    for before in targets_before:
        after = targets_after_by_uuid[before.guid_uuid]
        old_forms = scaffold._form_values(old_model, canvas, before)
        new_forms = scaffold._form_values(final_model, canvas, after)
        if len(old_forms) != 1 or len(new_forms) != 1:
            raise FaceFxError(f"{before.name}: expected one ArtMesh form")
        restored_face_local = final_model.forward_many(inner_fx, new_forms[0])
        local_error = canvas._maximum_error(old_forms[0], restored_face_local)
        if local_error >= TOLERANCE:
            raise FaceFxError(
                f"{before.name}: FACE-local reconstruction error {local_error}px"
            )
        for form_index, face_grid in enumerate(face_forms):
            pose_transform = canvas.WarpTransform(
                guid_ref=face_angle_before.guid_ref,
                name=face_angle_before.name,
                columns=5,
                rows=5,
                neutral_positions=face_grid,
                neutral_keyform_index=form_index,
                neutral_match_error_px=0.0,
                parent=face_parent,
            )
            old_canvas = old_model.forward_many(pose_transform, old_forms[0])
            new_canvas = old_model.forward_many(
                pose_transform, restored_face_local
            )
            error = canvas._maximum_error(old_canvas, new_canvas)
            if error >= TOLERANCE:
                raise FaceFxError(
                    f"{before.name}: Angle pose {form_index} error {error}px"
                )
            rows.append(
                {
                    "object": before.name,
                    "object_uuid": before.guid_uuid,
                    "form_index": form_index,
                    "angle_x_y": pose_rows[form_index]["angle_x_y"],
                    "position_scalars": len(old_forms[0]),
                    "face_local_error_px": local_error,
                    "canvas_error_px": error,
                }
            )
    return {
        "objects": len(targets_before),
        "angle_poses_each": 9,
        "comparisons": len(rows),
        "maximum_canvas_error_px": max(row["canvas_error_px"] for row in rows),
        "tolerance_px_exclusive": TOLERANCE,
        "pose_map": pose_map,
        "rows": rows,
    }


def _plan(
    source_data: bytes,
    *,
    contract: dict[str, Any],
    spec: Any,
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
    root_before = experiment._parse_xml(main_before)
    if root_before.get("fileFormatVersion") != "502030002":
        raise FaceFxError("Cubism file-format version differs")
    model0 = canvas.GeometryModel(main_before, TOLERANCE)
    if len(model0.objects) != 83:
        raise FaceFxError(f"source object count {len(model0.objects)} != 83")

    branch_contract = contract["new_branch"]
    face_angle = head._object_by_name(
        model0, branch_contract["parent"]["name"], "FACE Angle parent"
    )
    if (
        face_angle.object_type != "warp-deformer"
        or face_angle.guid_uuid != branch_contract["parent"]["uuid"]
        or face_angle.guid_ref
        != branch_contract["parent"]["guid_ref_in_pinned_source"]
    ):
        raise FaceFxError("D_JAD_FACE_ANGLE_XY identity differs")
    if spec.name in {item.name for item in model0.objects}:
        raise FaceFxError("D_JAD_FACE_FX already exists")

    migration_contract = {row["name"]: row for row in contract["migrations"]}
    targets0 = [
        head._object_by_name(model0, name, f"source {name}")
        for name in spec.children
    ]
    source_forms: dict[str, tuple[tuple[float, ...], ...]] = {}
    for target in targets0:
        row = migration_contract[target.name]
        if (
            target.object_type != "art-mesh"
            or target.guid_uuid != row["uuid"]
            or target.parent_ref != face_angle.guid_ref
        ):
            raise FaceFxError(f"{target.name}: source identity/parent differs")
        forms = scaffold._form_values(model0, canvas, target)
        if len(forms) != row["keyforms"] or sum(map(len, forms)) != row[
            "position_scalars"
        ]:
            raise FaceFxError(f"{target.name}: form/scalar contract differs")
        source_forms[target.guid_uuid] = forms

    inventory_before = head._inventory_xml(
        main_before, experiment=experiment, inventory=inventory
    )
    parameter_by_id = {
        row["id"]: row for row in inventory_before["parameters"]
    }
    for expected in contract["angle_oracle"]["parameters"]:
        observed = parameter_by_id.get(expected["id"])
        if observed is None or any(
            float(observed[key]) != float(expected[key])
            for key in ("minimum", "default", "maximum")
        ):
            raise FaceFxError(f"parameter {expected['id']} contract differs")

    part_before = experiment._part_hierarchy_state(root_before)
    part_ref = spec.part_guid_ref
    part_entity = part_before["entities"].get(part_ref)
    if (
        part_entity is None
        or part_entity["name"] != spec.part_name
        or part_entity["guid_uuid"] != branch_contract["part"]["uuid"]
        or part_entity["source_ref"] != spec.part_source_ref
    ):
        raise FaceFxError("80_FX Part identity differs")
    expected_old_part_children = [
        ("CDrawableGuid", target.guid_ref) for target in targets0
    ]
    if part_before["part_children"][part_ref] != expected_old_part_children:
        raise FaceFxError("80_FX initial membership/order differs")

    index_plan = head._derive_index_plan(
        main_before,
        experiment=experiment,
        contract=contract,
        specs=[spec],
    )
    if index_plan["new_ids"] != ["#1358", "#1359", "#1360", "#1361"]:
        raise FaceFxError("new serialization ID allocation differs")
    template = experiment._warp_info(root_before, head.CLONE_TEMPLATE_NAME)
    original_grid = scaffold._grid(canvas, spec.columns, spec.rows, spec.bounds)
    parent_transform = model0.transform(face_angle.guid_ref)
    local_grid = tuple(
        canvas._float32(value)
        for value in model0.inverse_many(parent_transform, original_grid)
    )
    grid_reconstructed = model0.forward_many(parent_transform, local_grid)
    grid_error = canvas._maximum_error(original_grid, grid_reconstructed)
    if grid_error >= TOLERANCE:
        raise FaceFxError(f"FX neutral grid error {grid_error}px")

    offsets = index_plan["relative_offsets"]
    base = index_plan["source_bases"][0]
    new_indices = (
        base + offsets["source"],
        base + offsets["positions"],
        base + offsets["form"],
        base + offsets["deformer_guid"],
    )
    blocks, metadata = _clone_fx_blocks(
        main_before,
        head=head,
        experiment=experiment,
        template=template,
        spec=spec,
        ids=tuple(index_plan["new_ids"]),
        indices=new_indices,
        parent_ref=face_angle.guid_ref,
        original_positions=original_grid,
        local_positions=local_grid,
    )
    generated_uuids = list(metadata["uuids"].values())
    if len(generated_uuids) != 5 or len(set(generated_uuids)) != 5:
        raise FaceFxError("generated UUID plan differs")

    current = main_before
    undo: list[Any] = []
    whitelist: list[dict[str, Any]] = []

    def apply(label: str, operation: Callable[[bytes], bytes]) -> None:
        nonlocal current
        before = current
        after = operation(before)
        undo.append(scaffold._make_undo_step(before, after, label))
        current = after

    apply(
        "append FACE FX shared definitions",
        lambda data: experiment._append_shared_blocks(data, blocks),
    )
    whitelist.append(
        {
            "kind": "new-shared-definitions",
            "definition_count": 4,
            "source_ref": metadata["source_ref"],
        }
    )
    source_set_record: dict[str, Any] = {}

    def patch_source_set(data: bytes) -> bytes:
        nonlocal source_set_record
        patched, source_set_record = head._patch_source_set_after(
            data,
            experiment=experiment,
            anchor_ref=face_angle.source_ref,
            new_refs=[metadata["source_ref"]],
        )
        return patched

    apply("insert FACE FX source after FACE Angle", patch_source_set)
    whitelist.append({"kind": "deformer-source-set", **source_set_record})
    apply(
        "register FACE FX in Part 80_FX",
        lambda data: experiment._patch_part_hierarchy(
            data, spec.part_guid_ref, metadata["guid_ref"]
        ),
    )
    whitelist.append(
        {
            "kind": "part-membership",
            "part": spec.part_name,
            "part_guid_ref": spec.part_guid_ref,
            "new_deformer_guid_ref": metadata["guid_ref"],
        }
    )

    scaffold_model = canvas.GeometryModel(current, TOLERANCE)
    fx_scaffold = head._object_by_name(scaffold_model, spec.name, spec.name)
    if (
        fx_scaffold.guid_uuid != spec.object_uuid
        or fx_scaffold.parent_ref != face_angle.guid_ref
    ):
        raise FaceFxError("new FX scaffold identity or parent differs")
    fx_transform = scaffold_model.transform(fx_scaffold.guid_ref)
    if (
        fx_transform.columns != 2
        or fx_transform.rows != 2
        or fx_transform.neutral_match_error_px >= TOLERANCE
    ):
        raise FaceFxError("new FX scaffold neutral transform differs")

    parent_records: list[dict[str, Any]] = []
    position_records: list[dict[str, Any]] = []
    conversion_proof: list[dict[str, Any]] = []
    planned_forms: dict[str, tuple[tuple[float, ...], ...]] = {}
    for target0 in targets0:
        converted, proof = scaffold._convert_forms(
            canvas=canvas,
            old_model=model0,
            new_model=scaffold_model,
            old_parent=face_angle,
            new_parent=fx_scaffold,
            target=target0,
        )
        planned_forms[target0.guid_uuid] = converted
        parent_record: dict[str, Any] = {}

        def patch_parent(data: bytes, target: Any = target0) -> bytes:
            nonlocal parent_record
            patched, parent_record = scaffold._patch_parent_ref(
                data,
                safe=safe,
                target=target,
                expected_old_ref=face_angle.guid_ref,
                new_ref=fx_scaffold.guid_ref,
                label=f"{target.name} -> {spec.name}",
            )
            return patched

        apply(f"reparent {target0.name} to FACE FX", patch_parent)
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
    if (
        len(parent_records) != whitelist_contract["existing_parent_refs_changed"]
        or len(position_records)
        != whitelist_contract["existing_position_arrays_changed"]
        or sum(row["new_count"] for row in position_records)
        != whitelist_contract["existing_position_scalars_changed"]
        or len(undo) != 7
    ):
        raise FaceFxError("transaction whitelist cardinality differs")

    final_model = canvas.GeometryModel(current, TOLERANCE)
    final_by_uuid = {item.guid_uuid: item for item in final_model.objects}
    before_by_uuid = {item.guid_uuid: item for item in model0.objects}
    if set(final_by_uuid) != set(before_by_uuid) | {spec.object_uuid}:
        raise FaceFxError("final object UUID set differs")
    for object_uuid, before in before_by_uuid.items():
        after = final_by_uuid[object_uuid]
        if (
            before.object_type,
            before.name,
            before.source_ref,
            before.guid_ref,
            before.guid_note,
        ) != (
            after.object_type,
            after.name,
            after.source_ref,
            after.guid_ref,
            after.guid_note,
        ):
            raise FaceFxError(f"existing object identity changed: {before.name}")
        expected_parent_uuid = (
            spec.object_uuid if before.name in spec.children else before.parent_uuid
        )
        if after.parent_uuid != expected_parent_uuid:
            raise FaceFxError(f"existing object parent changed: {before.name}")
        if model0.original_canvas(before) != final_model.original_canvas(after):
            raise FaceFxError(f"original canvas payload changed: {before.name}")

    fx_final = final_by_uuid[spec.object_uuid]
    fx_info = experiment._warp_info(experiment._parse_xml(current), spec.name)
    if (
        fx_info.deformer_id != spec.internal_id
        or fx_info.guid_uuid != spec.object_uuid
        or fx_info.parent_ref != face_angle.guid_ref
        or fx_info.parent_part_ref != spec.part_guid_ref
        or fx_info.col != 2
        or fx_info.row != 2
        or not scaffold._f32_equal(canvas, fx_info.original_positions, original_grid)
        or not scaffold._f32_equal(canvas, fx_info.positions, local_grid)
    ):
        raise FaceFxError("final FACE FX serialization differs")
    final_children = head._children(final_model, fx_final)
    if [item.name for item in final_children] != list(spec.children):
        raise FaceFxError("final FACE FX child order differs")
    fx_source = final_model.source(fx_final)
    fx_grid = experiment._one_named(
        fx_source, "KeyformGridSource", "keyformGridSource"
    )
    fx_bindings = experiment._direct_named(
        fx_grid, "array_list", "keyformBindings"
    )
    if fx_bindings.get("count") != "0" or len(fx_bindings) != 0:
        raise FaceFxError("new FACE FX branch is unexpectedly bound")

    final_root = experiment._parse_xml(current)
    part_after = experiment._part_hierarchy_state(final_root)
    expected_final_part_children = [
        ("CDeformerGuid", fx_final.guid_ref),
        *expected_old_part_children,
    ]
    if (
        part_after["part_children"][part_ref]
        != expected_final_part_children
        or part_after["membership_count"]
        != part_before["membership_count"] + 1
    ):
        raise FaceFxError("final 80_FX membership/order differs")
    for key in ("entities", "root_part_ref", "part_count"):
        if key != "entities" and part_after[key] != part_before[key]:
            raise FaceFxError(f"Part hierarchy field {key} changed")

    pose_map_before = _face_angle_pose_map(
        model0,
        experiment=experiment,
        canvas=canvas,
        face_angle=face_angle,
    )
    pose_map_after = _face_angle_pose_map(
        final_model,
        experiment=experiment,
        canvas=canvas,
        face_angle=final_by_uuid[face_angle.guid_uuid],
    )
    if pose_map_after != pose_map_before:
        raise FaceFxError("FACE Angle binding/access-key map changed")
    angle_proof = _angle_pose_proof(
        canvas=canvas,
        scaffold=scaffold,
        old_model=model0,
        final_model=final_model,
        face_angle_before=face_angle,
        fx_after=fx_final,
        targets_before=targets0,
        targets_after_by_uuid=final_by_uuid,
        pose_map=pose_map_before,
    )
    if angle_proof["maximum_canvas_error_px"] >= TOLERANCE:
        raise FaceFxError("nine-pose Angle proof exceeds tolerance")

    normalized_existing_proof = _normalized_existing_block_proof(
        main_before,
        current,
        experiment=experiment,
        scaffold=scaffold,
        canvas=canvas,
        targets_before=targets0,
        targets_after_by_uuid=final_by_uuid,
        source_forms=source_forms,
        planned_forms=planned_forms,
        old_parent_ref=face_angle.guid_ref,
        new_parent_ref=fx_final.guid_ref,
        part_source_ref=spec.part_source_ref,
        part_guid_ref=spec.part_guid_ref,
        expected_part_children_before=expected_old_part_children,
        expected_part_children_after=expected_final_part_children,
    )
    shared_proof = _stable_shared_definition_proof(
        main_before,
        current,
        experiment=experiment,
        excluded_existing_refs={target.source_ref for target in targets0}
        | {spec.part_source_ref},
    )
    if shared_proof["existing_definitions_byte_exact"] != 1355:
        raise FaceFxError("stable shared-definition count differs")
    existing_definition_total = (
        shared_proof["existing_definitions_byte_exact"]
        + normalized_existing_proof["modified_existing_definitions"]
    )
    if existing_definition_total != 1358:
        raise FaceFxError("exhaustive existing-definition proof count differs")
    shared_proof.update(
        {
            "normalized_modified_definitions": normalized_existing_proof,
            "existing_definitions_proved": existing_definition_total,
            "all_1358_existing_definitions_proved_byte_exact_after_normalization": True,
        }
    )

    before_summary = head._xml_summary(
        main_before, experiment=experiment, safe=safe
    )
    after_summary = head._xml_summary(current, experiment=experiment, safe=safe)
    expected = contract["expected_inventory_pre_cubism"]
    if (
        after_summary["shared_definitions"] != expected["shared_definitions"]
        or after_summary["shared_definitions"]
        != before_summary["shared_definitions"] + 4
        or after_summary["xs_id_count"] != before_summary["xs_id_count"] + 4
        or after_summary["xs_idx_count"] != before_summary["xs_idx_count"] + 4
        or after_summary["uuid_count"] != before_summary["uuid_count"] + 5
        or after_summary["deformer_source_count"]
        != expected["deformer_source_refs"]
        or not all(
            after_summary[key]
            for key in (
                "all_xs_ids_unique",
                "all_xs_indices_unique",
                "all_uuids_unique",
                "all_references_resolved",
            )
        )
    ):
        raise FaceFxError("serialized XML inventory delta differs")

    inventory_after = head._inventory_xml(
        current, experiment=experiment, inventory=inventory
    )
    if (
        inventory_after["parameters"] != inventory_before["parameters"]
        or inventory_after["bound_objects"] != inventory_before["bound_objects"]
        or inventory_after["parameter_ids"] != inventory_before["parameter_ids"]
    ):
        raise FaceFxError("parameters or bindings changed")
    observed_inventory = {
        "objects": len(final_model.objects),
        **{
            key: inventory_after["counts"][key]
            for key in (
                "art_meshes",
                "warp_deformers",
                "rotation_deformers",
                "deformers_total",
                "parts",
                "parameters",
                "bound_objects",
                "object_parameter_bindings",
                "keyforms_total",
            )
        },
        "part_memberships": part_after["membership_count"],
        "shared_definitions": after_summary["shared_definitions"],
        "deformer_source_refs": after_summary["deformer_source_count"],
    }
    for key, value in observed_inventory.items():
        if expected[key] != value:
            raise FaceFxError(
                f"final inventory {key}={value}, expected {expected[key]}"
            )

    topology_before = head._topology_xml(
        main_before, experiment=experiment, topology=topology
    )
    topology_after = head._topology_xml(
        current, experiment=experiment, topology=topology
    )
    if topology_after != topology_before:
        raise FaceFxError("ArtMesh topology changed")
    aggregate = topology_after["aggregate"]
    if (
        aggregate["art_meshes"] != expected["art_meshes"]
        or aggregate["vertices"] != expected["art_mesh_vertices"]
        or aggregate["triangles"] != expected["art_mesh_triangles"]
    ):
        raise FaceFxError("ArtMesh topology totals differ")

    normalized = current
    for step in reversed(undo):
        normalized = step.apply(normalized)
    if normalized != main_before:
        raise FaceFxError("undo ledger does not restore source main.xml byte-exact")

    output_data = safe._replace_main_xml(source_data, current)
    archive_after, _, _, _, decoded_after = safe._validate_surgical_layout(
        output_data
    )
    if decoded_after != current:
        raise FaceFxError("planned archive main.xml differs")
    archive_proof = safe._compare_entry_preservation(
        source_data,
        archive_before,
        output_data,
        archive_after,
        main_may_change=True,
    )
    if (
        archive_proof.get("entry_count") != expected["caff_members"]
        or archive_proof.get("entry_count", 0) - 1
        != expected["caff_non_main_members_byte_exact"]
        or archive_proof.get("all_non_main_entries_byte_identical") is not True
    ):
        raise FaceFxError("CAFF non-main preservation differs")

    return output_data, {
        "schema": "jade.cubism.face-fx-scaffold-audit.v1",
        "status": "ok",
        "gate": contract["gate"],
        "operation": "create_D_JAD_FACE_FX_and_migrate_two_blushes",
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
            "keyforms": 1,
            "parameter_bindings": 0,
            "neutral_grid_reconstruction_error_px": grid_error,
        },
        "conversion_proof": conversion_proof,
        "angle_pose_proof": angle_proof,
        "whitelist_cardinality": {
            "new_shared_definitions": len(blocks),
            "new_unique_uuids": len(generated_uuids),
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
            "ordered_members": branch_contract["part_member_order"],
        },
        "stable_shared_definitions": shared_proof,
        "inventory_before": inventory_before["counts"],
        "inventory_after": inventory_after["counts"],
        "observed_final_inventory": observed_inventory,
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
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    source = args.source.resolve(strict=True)
    output = args.output.resolve(strict=False)
    audit = output.with_name(AUDIT_NAME)
    if source.name != SOURCE_NAME or output.name != OUTPUT_NAME:
        raise FaceFxError("source/output filename differs from pinned transaction")
    if source.parent != REPORTS_DIR or output.parent != REPORTS_DIR:
        raise FaceFxError("source/output must be direct children of reports")
    if source == output:
        raise FaceFxError("source and output must be distinct")
    if output.exists() or audit.exists():
        raise FaceFxError("output or audit exists; refusing overwrite")

    head, experiment, scaffold, safe, canvas, topology, inventory = _load_stack()
    contract, spec, contract_path = _load_contract(head)
    source_data = source.read_bytes()
    if len(source_data) != SOURCE_BYTES or _sha256(source_data) != SOURCE_SHA256:
        raise FaceFxError("source bytes/SHA-256 differs from pinned checkpoint")
    output_data, result = _plan(
        source_data,
        contract=contract,
        spec=spec,
        head=head,
        experiment=experiment,
        scaffold=scaffold,
        safe=safe,
        canvas=canvas,
        topology=topology,
        inventory=inventory,
    )
    tool_path = Path(__file__).resolve(strict=True)
    result.update(
        {
            "tool": str(tool_path),
            "tool_sha256": _hash_file(tool_path),
            "source": str(source),
            "output": str(output),
            "audit": str(audit),
            "contract_path": str(contract_path),
            "dry_run": bool(args.dry_run),
            "output_written": False,
        }
    )
    if source.read_bytes() != source_data:
        raise FaceFxError("source changed during in-memory plan")
    if _hash_file(contract_path) != CONTRACT_SHA256:
        raise FaceFxError("contract changed during in-memory plan")

    if args.dry_run:
        if output.exists() or audit.exists():
            raise FaceFxError("dry-run unexpectedly created an output")
        result["verdict"] = "PASS_DRY_RUN__NO_FILE_WRITTEN"
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0

    created_output = False
    created_audit = False
    try:
        safe._write_new_file(output, output_data)
        created_output = True
        if output.read_bytes() != output_data:
            raise FaceFxError("written output differs from validated plan")
        if source.read_bytes() != source_data:
            raise FaceFxError("source changed during transaction")
        written_inventory = safe._structural_inventory(output)
        if written_inventory["counts"] != result["inventory_after"]:
            raise FaceFxError("written output inventory differs from plan")
        written_topology = topology.inventory(output, MAX_XML_BYTES)
        if written_topology["aggregate"] != result["topology"]["aggregate"]:
            raise FaceFxError("written output topology differs from plan")
        result["output_written"] = True
        result["output_sha256"] = _sha256(output_data)
        result["output_bytes"] = len(output_data)
        result["verdict"] = (
            "PASS_FACE_S0_TEST_TRANSACTION__CUBISM_5_2_03_GATE_REQUIRED"
        )
        _write_json_exclusive(audit, result)
        created_audit = True
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception:
        if created_audit:
            audit.unlink(missing_ok=True)
        if created_output:
            output.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FaceFxError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
