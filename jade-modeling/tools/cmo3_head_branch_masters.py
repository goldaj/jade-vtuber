#!/usr/bin/env python3
"""Create Jade's five neutral TEST head-branch masters transactionally.

This builder accepts one byte-pinned Cubism 5.2.03 checkpoint and one frozen
JSON contract.  It clones the observed neutral 5x5 warp serialization five
times, inserts the new sources immediately after ``D_JAD_HEAD_XY`` in the
model deformer-source order, registers each master in its approved Part, and
reparents the exact 28 current head roots while preserving all 84 serialized
forms in canvas space.

The input is never modified.  ``--dry-run`` performs the complete in-memory
transaction and all validations without creating the output or audit files.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Sequence


TOOLS_DIR = Path(__file__).resolve(strict=True).parent
PROJECT_DIR = TOOLS_DIR.parent
REPORTS_DIR = (PROJECT_DIR / "reports").resolve(strict=True)

DEPENDENCY_PINS = {
    "cmo3_create_deformer_experiment.py": (
        "7D81CC278FE2E09850BBF46A48DF427BA79FB7993ECF22D3F61FDE28B41D4C65"
    ),
    "cmo3_head_wrapper_scaffold.py": (
        "6ADB42DFCBB22491D9278E34D1B42D6B327418B3C7D43BBEB3049DDDC6C71519"
    ),
    "cmo3_inventory.py": (
        "9CBA62CFCEBBFE249F0F0785EA480A3963FD610F95D356EC5D36FCBDCA201083"
    ),
    "cmo3_safe_roundtrip.py": (
        "AB9E67B350E6D42AA4B471B5359CFB45B8A09FF02489CCFF447D65A59B00AC5E"
    ),
    "cmo3_reparent_preserve_canvas.py": (
        "4E191B07EBD2F15064197429B5ADFD57EE25B5C7252E34F458EC999FA003A38A"
    ),
    "cmo3_mesh_topology.py": (
        "737C62FB40D3F359894A9E4FE1B718238AFED92D61B7CEE36323910EA8E7390F"
    ),
}

CONTRACT_NAME = "Jade_v003.TEST_head_branch_masters_r01_contract.json"
CONTRACT_SHA256 = (
    "16B8DCF3B52B3CFE09ED8DCCC5DD76D03106D3BA7C77C8502CDB1A0D11504C13"
)
SOURCE_NAME = (
    "Jade_rig_5_2_v003.TEST_head_wrapper_7x5_r01."
    "CUBISM_roundtrip_r01.cmo3"
)
SOURCE_SHA256 = (
    "86160CDC3A73B855A16BD6B7C632067604F4AAC6FF69CE230B9154528718AAA6"
)
SOURCE_BYTES = 2_020_533
OUTPUT_NAME = "Jade_rig_5_2_v003.TEST_head_branch_masters_r01.cmo3"
AUDIT_NAME = "Jade_v003.TEST_head_branch_masters_r01_audit.json"

HEAD_NAME = "D_JAD_HEAD_XY"
HEAD_GUID_REF = "#572"
CLONE_TEMPLATE_NAME = "D_JAD_BODY_XY"
TOLERANCE = 0.001
MAX_XML_BYTES = 256 * 1024 * 1024


class BranchMasterError(RuntimeError):
    """Raised whenever the pinned mutation contract cannot be proven."""


@dataclass(frozen=True)
class MasterSpec:
    name: str
    internal_id: str
    object_uuid: str
    part_name: str
    part_guid_ref: str
    part_source_ref: str
    bounds: tuple[float, float, float, float]
    columns: int
    rows: int
    children: tuple[str, ...]
    existing_form_count: int
    existing_position_scalar_count: int


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _hash_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise BranchMasterError(f"cannot load dependency {path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_dependencies() -> tuple[
    ModuleType, ModuleType, ModuleType, ModuleType, ModuleType, ModuleType
]:
    for filename, expected in DEPENDENCY_PINS.items():
        path = (TOOLS_DIR / filename).resolve(strict=True)
        actual = _hash_file(path)
        if actual != expected:
            raise BranchMasterError(
                f"dependency {filename} SHA mismatch: expected {expected}, got {actual}"
            )
    sys.path.insert(0, str(TOOLS_DIR))
    experiment = _load_module(
        "jade_branch_create_deformer_dependency",
        TOOLS_DIR / "cmo3_create_deformer_experiment.py",
    )
    scaffold = _load_module(
        "jade_branch_head_scaffold_dependency",
        TOOLS_DIR / "cmo3_head_wrapper_scaffold.py",
    )
    safe, canvas, topology = scaffold._load_dependencies()
    inventory = sys.modules.get("cmo3_inventory")
    if inventory is None:
        raise BranchMasterError("cmo3_inventory was not loaded")
    for filename, expected in DEPENDENCY_PINS.items():
        if _hash_file((TOOLS_DIR / filename).resolve(strict=True)) != expected:
            raise BranchMasterError(f"dependency {filename} changed while loading")
    return experiment, scaffold, safe, canvas, topology, inventory


def _strict_keys(value: Any, required: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BranchMasterError(f"{label} must be an object")
    if set(value) != required:
        raise BranchMasterError(
            f"{label} keys differ: observed={sorted(value)}, expected={sorted(required)}"
        )
    return value


def _load_contract() -> tuple[dict[str, Any], tuple[MasterSpec, ...], Path]:
    path = (REPORTS_DIR / CONTRACT_NAME).resolve(strict=True)
    raw = path.read_bytes()
    if _sha256(raw) != CONTRACT_SHA256:
        raise BranchMasterError("head-branch contract SHA-256 differs")
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BranchMasterError("head-branch contract is not valid UTF-8 JSON") from exc
    contract = _strict_keys(
        document,
        {
            "contract_version",
            "status",
            "production_status",
            "purpose",
            "source",
            "parent",
            "serialization_oracle",
            "masters",
            "new_master_requirements",
            "whitelist",
            "expected_inventory",
            "acceptance",
            "planned_flattening",
        },
        "contract",
    )
    if contract["contract_version"] != 1:
        raise BranchMasterError("unsupported contract version")
    if contract["status"] != "approved_test_only_transitional_checkpoint":
        raise BranchMasterError("contract status is not approved")
    if contract["production_status"] != "not_a_final_professional_tree":
        raise BranchMasterError("contract production status differs")

    source = _strict_keys(
        contract["source"],
        {
            "filename",
            "sha256",
            "bytes",
            "cubism_file_format_version",
            "required_editor",
            "upgrade_forbidden",
        },
        "contract.source",
    )
    if source != {
        "filename": SOURCE_NAME,
        "sha256": SOURCE_SHA256,
        "bytes": SOURCE_BYTES,
        "cubism_file_format_version": "502030002",
        "required_editor": "Live2D Cubism Editor 5.2.03",
        "upgrade_forbidden": True,
    }:
        raise BranchMasterError("contract source checkpoint differs")
    parent = _strict_keys(
        contract["parent"],
        {"name", "guid_ref_in_pinned_source"},
        "contract.parent",
    )
    if parent != {"name": HEAD_NAME, "guid_ref_in_pinned_source": HEAD_GUID_REF}:
        raise BranchMasterError("contract head parent differs")

    oracle = _strict_keys(
        contract["serialization_oracle"],
        {
            "names",
            "derive_at_runtime",
            "required_matching_relative_offsets",
            "required_observed_footprint",
            "pinned_source_tail_xs_idx",
            "expected_derived_source_bases",
        },
        "contract.serialization_oracle",
    )
    if oracle != {
        "names": ["Eyebrow L Position", "Eyebrow R Position"],
        "derive_at_runtime": True,
        "required_matching_relative_offsets": {
            "source": 0,
            "form": 6,
            "positions": 20,
            "deformer_guid": 22,
        },
        "required_observed_footprint": 29,
        "pinned_source_tail_xs_idx": 7706,
        "expected_derived_source_bases": [7707, 7736, 7765, 7794, 7823],
    }:
        raise BranchMasterError("contract serialization oracle differs")

    raw_masters = contract["masters"]
    if not isinstance(raw_masters, list) or len(raw_masters) != 5:
        raise BranchMasterError("contract must define exactly five masters")
    specs: list[MasterSpec] = []
    for index, raw_master in enumerate(raw_masters):
        master = _strict_keys(
            raw_master,
            {
                "name",
                "internal_id",
                "object_uuid",
                "part",
                "bounds_canvas",
                "divisions",
                "children",
                "existing_form_count",
                "existing_position_scalar_count",
            },
            f"contract.masters[{index}]",
        )
        part = _strict_keys(
            master["part"],
            {"name", "guid_ref_in_pinned_source", "source_ref_in_pinned_source"},
            f"contract.masters[{index}].part",
        )
        bounds = master["bounds_canvas"]
        divisions = master["divisions"]
        children = master["children"]
        if (
            not isinstance(bounds, list)
            or len(bounds) != 4
            or any(not isinstance(value, (int, float)) for value in bounds)
            or any(not math.isfinite(float(value)) for value in bounds)
        ):
            raise BranchMasterError(f"master {index} has invalid bounds")
        if divisions != [5, 5]:
            raise BranchMasterError(f"master {index} is not 5x5")
        if (
            not isinstance(children, list)
            or not children
            or any(not isinstance(name, str) or not name for name in children)
            or len(children) != len(set(children))
        ):
            raise BranchMasterError(f"master {index} has invalid children")
        try:
            object_uuid = str(uuid.UUID(master["object_uuid"]))
        except (ValueError, TypeError) as exc:
            raise BranchMasterError(f"master {index} object UUID is invalid") from exc
        spec = MasterSpec(
            name=master["name"],
            internal_id=master["internal_id"],
            object_uuid=object_uuid,
            part_name=part["name"],
            part_guid_ref=part["guid_ref_in_pinned_source"],
            part_source_ref=part["source_ref_in_pinned_source"],
            bounds=tuple(float(value) for value in bounds),
            columns=int(divisions[0]),
            rows=int(divisions[1]),
            children=tuple(children),
            existing_form_count=int(master["existing_form_count"]),
            existing_position_scalar_count=int(
                master["existing_position_scalar_count"]
            ),
        )
        if spec.internal_id != spec.name:
            raise BranchMasterError(f"{spec.name}: internal ID must equal approved name")
        specs.append(spec)

    expected_names = [
        "D_JAD_FACE_MASTER",
        "D_JAD_HAIR_BACK_MASTER",
        "D_JAD_HAIR_FRONT_MASTER",
        "D_JAD_EAR_L_MASTER",
        "D_JAD_EAR_R_MASTER",
    ]
    if [spec.name for spec in specs] != expected_names:
        raise BranchMasterError("approved master ordering/names differ")
    if len({spec.object_uuid for spec in specs}) != 5:
        raise BranchMasterError("approved master object UUIDs are not unique")
    all_children = [name for spec in specs for name in spec.children]
    if len(all_children) != 28 or len(all_children) != len(set(all_children)):
        raise BranchMasterError("approved child partition is not 28 unique roots")
    if sum(spec.existing_form_count for spec in specs) != 84:
        raise BranchMasterError("approved form total is not 84")
    if sum(spec.existing_position_scalar_count for spec in specs) != 7530:
        raise BranchMasterError("approved position-scalar total is not 7530")
    if specs[0].part_name != "33_FACE" or specs[0].part_guid_ref != "#797":
        raise BranchMasterError("face master must belong to 33_FACE")

    requirements = _strict_keys(
        contract["new_master_requirements"],
        {
            "keyforms_each",
            "parameter_bindings_each",
            "grid_position_scalars_each",
            "new_shared_definitions_each",
            "new_unique_uuids_each",
            "neutral_only",
        },
        "contract.new_master_requirements",
    )
    if requirements != {
        "keyforms_each": 1,
        "parameter_bindings_each": 0,
        "grid_position_scalars_each": 72,
        "new_shared_definitions_each": 4,
        "new_unique_uuids_each": 5,
        "neutral_only": True,
    }:
        raise BranchMasterError("new-master requirements differ")
    whitelist = _strict_keys(
        contract["whitelist"],
        {
            "existing_parent_refs_changed",
            "existing_position_arrays_changed",
            "existing_position_scalars_changed",
            "part_memberships_added",
            "deformer_source_refs_added",
            "shared_definitions_added",
            "all_other_existing_payloads_must_remain_exact",
        },
        "contract.whitelist",
    )
    if whitelist != {
        "existing_parent_refs_changed": 28,
        "existing_position_arrays_changed": 84,
        "existing_position_scalars_changed": 7530,
        "part_memberships_added": 5,
        "deformer_source_refs_added": 5,
        "shared_definitions_added": 20,
        "all_other_existing_payloads_must_remain_exact": True,
    }:
        raise BranchMasterError("contract whitelist differs")

    expected_inventory = _strict_keys(
        contract["expected_inventory"],
        {
            "objects",
            "art_meshes",
            "warp_deformers",
            "rotation_deformers",
            "deformers_total",
            "parts",
            "part_memberships",
            "parameters",
            "bound_objects",
            "object_parameter_bindings",
            "keyforms_total",
            "shared_definitions_pre_cubism",
            "deformer_source_refs",
            "art_mesh_vertices",
            "art_mesh_triangles",
            "caff_members",
            "caff_non_main_members_byte_exact",
        },
        "contract.expected_inventory",
    )
    expected_inventory_literal = {
        "objects": 83,
        "art_meshes": 58,
        "warp_deformers": 22,
        "rotation_deformers": 3,
        "deformers_total": 25,
        "parts": 32,
        "part_memberships": 114,
        "parameters": 27,
        "bound_objects": 7,
        "object_parameter_bindings": 14,
        "keyforms_total": 171,
        "shared_definitions_pre_cubism": 1358,
        "deformer_source_refs": 25,
        "art_mesh_vertices": 2839,
        "art_mesh_triangles": 4140,
        "caff_members": 294,
        "caff_non_main_members_byte_exact": 293,
    }
    if expected_inventory != expected_inventory_literal:
        raise BranchMasterError("expected inventory contract differs")
    acceptance = _strict_keys(
        contract["acceptance"],
        {
            "head_direct_children_exactly_five_masters",
            "graph_acyclic",
            "existing_object_ids_names_uuids_unchanged",
            "existing_parts_parameters_bindings_topology_unchanged",
            "maximum_canvas_reconstruction_error_pixels",
            "undo_must_restore_source_main_xml_byte_exact",
            "dry_run_must_create_no_output",
            "cubism_roundtrip_required",
            "cubism_verify_after_save_required",
            "cubism_close_and_reopen_required",
            "post_cubism_semantic_audit_required",
        },
        "contract.acceptance",
    )
    if acceptance["maximum_canvas_reconstruction_error_pixels"] != TOLERANCE:
        raise BranchMasterError("contract tolerance differs")
    if any(
        acceptance[key] is not True
        for key in acceptance
        if key != "maximum_canvas_reconstruction_error_pixels"
    ):
        raise BranchMasterError("all Boolean acceptance gates must be true")
    flattening = _strict_keys(
        contract["planned_flattening"],
        {"required_before_production", "reason", "face_master_target", "hair_and_ear_targets"},
        "contract.planned_flattening",
    )
    if flattening["required_before_production"] is not True:
        raise BranchMasterError("transitional flattening gate is not enabled")
    return contract, tuple(specs), path


def _object_by_name(model: Any, name: str, label: str) -> Any:
    matches = [item for item in model.objects if item.name == name]
    if len(matches) != 1:
        raise BranchMasterError(f"{label}: expected one object, found {len(matches)}")
    return matches[0]


def _children(model: Any, parent: Any) -> list[Any]:
    return [item for item in model.objects if item.parent_ref == parent.guid_ref]


def _canonical_uuid(value: str, label: str) -> str:
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError) as exc:
        raise BranchMasterError(f"{label} is not a canonical UUID: {value!r}") from exc


def _generated_uuid(source_sha: str, master_name: str, role: str) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"jade-cmo3-head-branch-master:{source_sha}:{master_name}:{role}",
        )
    )


def _source_set(root: Any, experiment: ModuleType) -> tuple[Any, list[str]]:
    model = root.find("main/CModelSource")
    if model is None:
        raise BranchMasterError("main.xml lacks CModelSource")
    source_set = model.find("CDeformerSourceSet")
    if source_set is None:
        raise BranchMasterError("main.xml lacks CDeformerSourceSet")
    lists = [
        node
        for node in source_set.findall("carray_list")
        if node.get("xs.n") == "_sources"
    ]
    if len(lists) != 1:
        raise BranchMasterError("CDeformerSourceSet/_sources is ambiguous")
    source_list = lists[0]
    refs = [node.get("xs.ref") for node in source_list]
    if (
        source_list.get("count") != str(len(source_list))
        or any(ref is None for ref in refs)
        or len(refs) != len(set(refs))
    ):
        raise BranchMasterError("CDeformerSourceSet is inconsistent")
    ids = experiment._id_map(root)
    if any(ref not in ids for ref in refs):
        raise BranchMasterError("CDeformerSourceSet contains an unresolved reference")
    return source_list, [str(ref) for ref in refs]


def _derive_index_plan(
    main_xml: bytes,
    *,
    experiment: ModuleType,
    contract: dict[str, Any],
    specs: Sequence[MasterSpec],
) -> dict[str, Any]:
    root = experiment._parse_xml(main_xml)
    shared = root.find("shared")
    if shared is None:
        raise BranchMasterError("main.xml lacks shared definitions")
    ids = experiment._id_map(root)
    numeric_ids: list[int] = []
    for serialized_id in ids:
        if re.fullmatch(r"#\d+", serialized_id) is None:
            raise BranchMasterError(f"unsupported nonnumeric xs.id {serialized_id!r}")
        numeric_ids.append(int(serialized_id[1:]))
    maximum_id = max(numeric_ids)
    if set(numeric_ids) != set(range(maximum_id + 1)):
        raise BranchMasterError("existing xs.id values are not contiguous from #0")

    shared_indices: list[int] = []
    for child in shared:
        raw = child.get("xs.idx")
        if raw is None or not raw.isdigit():
            raise BranchMasterError(
                f"shared definition {child.tag} {child.get('xs.id')!r} lacks numeric xs.idx"
            )
        shared_indices.append(int(raw))
    if len(shared_indices) != len(set(shared_indices)):
        raise BranchMasterError("existing shared xs.idx values are not unique")
    maximum_index = max(shared_indices)

    template = experiment._warp_info(root, CLONE_TEMPLATE_NAME)
    if (
        template.col != 5
        or template.row != 5
        or len(template.positions) != 72
        or len(template.original_positions) != 72
        or len(list(template.source.iter())) != 75
    ):
        raise BranchMasterError("D_BODY is not the approved 75-element 5x5 clone payload")

    oracle_contract = contract["serialization_oracle"]
    expected_offsets = oracle_contract["required_matching_relative_offsets"]
    _, source_refs = _source_set(root, experiment)
    observed_oracles: list[dict[str, Any]] = []
    for oracle_name in oracle_contract["names"]:
        oracle = experiment._warp_info(root, oracle_name)
        if len(list(oracle.source.iter())) != len(list(template.source.iter())):
            raise BranchMasterError(
                f"serialization oracle {oracle_name!r} does not match template shape"
            )
        offsets = {
            "source": 0,
            "form": oracle.form_idx - oracle.source_idx,
            "positions": oracle.positions_idx - oracle.source_idx,
            "deformer_guid": oracle.guid_idx - oracle.source_idx,
        }
        try:
            position = source_refs.index(oracle.source_ref)
        except ValueError as exc:
            raise BranchMasterError(f"oracle {oracle_name!r} is absent from source set") from exc
        if position + 1 >= len(source_refs):
            raise BranchMasterError(f"oracle {oracle_name!r} lacks a following source")
        next_source_ref = source_refs[position + 1]
        next_source = ids[next_source_ref]
        next_idx_raw = next_source.get("xs.idx")
        if next_idx_raw is None or not next_idx_raw.isdigit():
            raise BranchMasterError(f"source after oracle {oracle_name!r} lacks xs.idx")
        footprint = int(next_idx_raw) - oracle.source_idx
        if offsets != expected_offsets:
            raise BranchMasterError(
                f"oracle {oracle_name!r} offsets {offsets!r} differ from contract"
            )
        if footprint != oracle_contract["required_observed_footprint"]:
            raise BranchMasterError(
                f"oracle {oracle_name!r} footprint {footprint} differs from contract"
            )
        observed_oracles.append(
            {
                "name": oracle_name,
                "source_ref": oracle.source_ref,
                "source_idx": oracle.source_idx,
                "next_source_ref": next_source_ref,
                "next_source_idx": int(next_idx_raw),
                "relative_offsets": offsets,
                "footprint": footprint,
                "source_element_count": len(list(oracle.source.iter())),
            }
        )
    if maximum_index != oracle_contract["pinned_source_tail_xs_idx"]:
        raise BranchMasterError(
            f"source tail xs.idx {maximum_index} differs from contract"
        )
    footprint = observed_oracles[0]["footprint"]
    bases = [maximum_index + 1 + index * footprint for index in range(len(specs))]
    if bases != oracle_contract["expected_derived_source_bases"]:
        raise BranchMasterError(f"derived source bases {bases!r} differ from contract")

    offsets = observed_oracles[0]["relative_offsets"]
    generated_indices: list[int] = []
    for base in bases:
        generated_indices.extend(
            [
                base + offsets["source"],
                base + offsets["form"],
                base + offsets["positions"],
                base + offsets["deformer_guid"],
            ]
        )
    if (
        len(generated_indices) != len(set(generated_indices))
        or set(generated_indices).intersection(shared_indices)
    ):
        raise BranchMasterError("derived xs.idx allocation collides")
    new_ids = [f"#{maximum_id + 1 + index}" for index in range(4 * len(specs))]
    if set(new_ids).intersection(ids):
        raise BranchMasterError("derived xs.id allocation collides")
    return {
        "maximum_existing_xs_id": f"#{maximum_id}",
        "maximum_existing_xs_idx": maximum_index,
        "template": {
            "name": template.name,
            "source_ref": template.source_ref,
            "source_idx": template.source_idx,
            "source_element_count": len(list(template.source.iter())),
            "dimensions": [template.col, template.row],
        },
        "oracles": observed_oracles,
        "relative_offsets": offsets,
        "footprint": footprint,
        "source_bases": bases,
        "new_ids": new_ids,
        "generated_indices": generated_indices,
    }


def _clone_master_blocks(
    main_xml: bytes,
    *,
    experiment: ModuleType,
    template: Any,
    spec: MasterSpec,
    source_sha: str,
    ids: tuple[str, str, str, str],
    indices: tuple[int, int, int, int],
    parent_ref: str,
    original_positions: Sequence[float],
    local_positions: Sequence[float],
) -> tuple[list[bytes], dict[str, Any]]:
    source_ref, positions_ref, form_ref, guid_ref = ids
    source_idx, positions_idx, form_idx, guid_idx = indices
    root = experiment._parse_xml(main_xml)
    existing_uuids = {
        _canonical_uuid(node.get("uuid"), f"existing {node.tag} UUID")
        for node in root.iter()
        if node.get("uuid") is not None
    }
    generated_uuids = {
        "deformer": spec.object_uuid,
        "form": _generated_uuid(source_sha, spec.name, "form"),
        "bezier_edit_2": _generated_uuid(source_sha, spec.name, "extension-bezier-edit-2"),
        "bezier_edit_3": _generated_uuid(source_sha, spec.name, "extension-bezier-edit-3"),
        "original_shape": _generated_uuid(source_sha, spec.name, "extension-original-shape"),
    }
    if len(set(generated_uuids.values())) != 5:
        raise BranchMasterError(f"{spec.name}: generated UUIDs are not unique")
    if set(generated_uuids.values()).intersection(existing_uuids):
        raise BranchMasterError(f"{spec.name}: generated UUID collides with source")

    source_block = experiment._block_by_id(
        main_xml, "CWarpDeformerSource", template.source_ref
    )
    positions_block = experiment._block_by_id(
        main_xml, "float-array", template.positions_ref
    )
    form_block = experiment._block_by_id(main_xml, "CFormGuid", template.form_ref)
    guid_block = experiment._block_by_id(
        main_xml, "CDeformerGuid", template.guid_ref
    )

    source_block = experiment._replace_exact(
        source_block,
        f'xs.id="{template.source_ref}"'.encode("ascii"),
        f'xs.id="{source_ref}"'.encode("ascii"),
        1,
        f"{spec.name} source xs.id",
    )
    source_block = experiment._replace_exact(
        source_block,
        f'xs.idx="{template.source_idx}"'.encode("ascii"),
        f'xs.idx="{source_idx}"'.encode("ascii"),
        1,
        f"{spec.name} source xs.idx",
    )
    source_block = experiment._replace_exact(
        source_block,
        f">{template.name}</s>".encode("utf-8"),
        f">{spec.name}</s>".encode("utf-8"),
        1,
        f"{spec.name} localName",
    )
    source_block = experiment._replace_exact(
        source_block,
        f'xs.ref="{template.source_ref}"'.encode("ascii"),
        f'xs.ref="{source_ref}"'.encode("ascii"),
        4,
        f"{spec.name} owner/source references",
    )
    source_block = experiment._replace_exact(
        source_block,
        f'xs.ref="{template.positions_ref}"'.encode("ascii"),
        f'xs.ref="{positions_ref}"'.encode("ascii"),
        2,
        f"{spec.name} original positions references",
    )
    source_block = experiment._replace_exact(
        source_block,
        f'xs.ref="{template.form_ref}"'.encode("ascii"),
        f'xs.ref="{form_ref}"'.encode("ascii"),
        2,
        f"{spec.name} form references",
    )
    source_block = experiment._replace_exact(
        source_block,
        f'xs.ref="{template.guid_ref}"'.encode("ascii"),
        f'xs.ref="{guid_ref}"'.encode("ascii"),
        1,
        f"{spec.name} deformer GUID reference",
    )
    source_block = experiment._replace_exact(
        source_block,
        f'idstr="{template.deformer_id}"'.encode("utf-8"),
        f'idstr="{spec.internal_id}"'.encode("utf-8"),
        1,
        f"{spec.name} internal ID",
    )
    source_block = experiment._replace_exact(
        source_block,
        (
            f'<CPartGuid xs.n="parentGuid" '
            f'xs.ref="{template.parent_part_ref}" />'
        ).encode("ascii"),
        (
            f'<CPartGuid xs.n="parentGuid" '
            f'xs.ref="{spec.part_guid_ref}" />'
        ).encode("ascii"),
        1,
        f"{spec.name} Part parent",
    )
    source_block = experiment._replace_exact(
        source_block,
        (
            f'<CDeformerGuid xs.n="targetDeformerGuid" '
            f'xs.ref="{template.parent_ref}" />'
        ).encode("ascii"),
        (
            f'<CDeformerGuid xs.n="targetDeformerGuid" '
            f'xs.ref="{parent_ref}" />'
        ).encode("ascii"),
        1,
        f"{spec.name} deformer parent",
    )
    for old_uuid, role in zip(
        template.extension_uuids,
        ("bezier_edit_2", "bezier_edit_3", "original_shape"),
    ):
        source_block = experiment._replace_exact(
            source_block,
            f'uuid="{old_uuid}"'.encode("ascii"),
            f'uuid="{generated_uuids[role]}"'.encode("ascii"),
            1,
            f"{spec.name} extension UUID {role}",
        )
    source_block = experiment._replace_float_payload(
        source_block, local_positions, f"{spec.name} neutral local positions"
    )

    positions_block = experiment._replace_exact(
        positions_block,
        f'xs.id="{template.positions_ref}"'.encode("ascii"),
        f'xs.id="{positions_ref}"'.encode("ascii"),
        1,
        f"{spec.name} positions xs.id",
    )
    positions_block = experiment._replace_exact(
        positions_block,
        f'xs.idx="{template.positions_idx}"'.encode("ascii"),
        f'xs.idx="{positions_idx}"'.encode("ascii"),
        1,
        f"{spec.name} positions xs.idx",
    )
    positions_block = experiment._replace_float_payload(
        positions_block, original_positions, f"{spec.name} original positions"
    )

    form_block = experiment._replace_exact(
        form_block,
        f'xs.id="{template.form_ref}"'.encode("ascii"),
        f'xs.id="{form_ref}"'.encode("ascii"),
        1,
        f"{spec.name} form xs.id",
    )
    form_block = experiment._replace_exact(
        form_block,
        f'xs.idx="{template.form_idx}"'.encode("ascii"),
        f'xs.idx="{form_idx}"'.encode("ascii"),
        1,
        f"{spec.name} form xs.idx",
    )
    form_block = experiment._replace_exact(
        form_block,
        f'uuid="{template.form_uuid}"'.encode("ascii"),
        f'uuid="{generated_uuids["form"]}"'.encode("ascii"),
        1,
        f"{spec.name} form UUID",
    )

    guid_block = experiment._replace_exact(
        guid_block,
        f'xs.id="{template.guid_ref}"'.encode("ascii"),
        f'xs.id="{guid_ref}"'.encode("ascii"),
        1,
        f"{spec.name} GUID xs.id",
    )
    guid_block = experiment._replace_exact(
        guid_block,
        f'xs.idx="{template.guid_idx}"'.encode("ascii"),
        f'xs.idx="{guid_idx}"'.encode("ascii"),
        1,
        f"{spec.name} GUID xs.idx",
    )
    guid_block = experiment._replace_exact(
        guid_block,
        f'uuid="{template.guid_uuid}"'.encode("ascii"),
        f'uuid="{generated_uuids["deformer"]}"'.encode("ascii"),
        1,
        f"{spec.name} object UUID",
    )
    note_matches = list(re.finditer(rb'\bnote="[^"]*"', guid_block))
    if len(note_matches) != 1:
        raise BranchMasterError(f"{spec.name}: clone GUID note is ambiguous")
    note = note_matches[0]
    guid_block = (
        guid_block[: note.start()]
        + f'note="{spec.internal_id}"'.encode("utf-8")
        + guid_block[note.end() :]
    )
    return [source_block, positions_block, form_block, guid_block], {
        "name": spec.name,
        "internal_id": spec.internal_id,
        "source_ref": source_ref,
        "positions_ref": positions_ref,
        "form_ref": form_ref,
        "guid_ref": guid_ref,
        "source_idx": source_idx,
        "positions_idx": positions_idx,
        "form_idx": form_idx,
        "guid_idx": guid_idx,
        "parent_deformer_guid_ref": parent_ref,
        "parent_part_guid_ref": spec.part_guid_ref,
        "uuids": generated_uuids,
        "bounds_canvas": list(spec.bounds),
        "divisions": [spec.columns, spec.rows],
        "original_position_scalars": len(original_positions),
        "neutral_local_position_scalars": len(local_positions),
    }


def _patch_source_set_after(
    main_xml: bytes,
    *,
    experiment: ModuleType,
    anchor_ref: str,
    new_refs: Sequence[str],
) -> tuple[bytes, dict[str, Any]]:
    root = experiment._parse_xml(main_xml)
    _, before_refs = _source_set(root, experiment)
    if before_refs.count(anchor_ref) != 1:
        raise BranchMasterError("D_HEAD source-set anchor is not unique")
    if set(new_refs).intersection(before_refs) or len(new_refs) != len(set(new_refs)):
        raise BranchMasterError("new source-set references collide")

    opening = re.compile(
        rb'<CDeformerSourceSet\b(?=[^>]*\bxs\.n="deformerSourceSet")[^>]*>'
    )
    matches = list(opening.finditer(main_xml))
    if len(matches) != 1:
        raise BranchMasterError("CDeformerSourceSet serialized block is ambiguous")
    closing = b"</CDeformerSourceSet>"
    closing_offset = main_xml.find(closing, matches[0].end())
    if closing_offset < 0:
        raise BranchMasterError("CDeformerSourceSet serialized block is unclosed")
    block_end = closing_offset + len(closing)
    block = main_xml[matches[0].start() : block_end]
    list_opening = re.compile(
        rb'(<carray_list\b(?=[^>]*\bxs\.n="_sources")'
        rb'[^>]*\bcount=")(\d+)("[^>]*>\r\n)'
    )
    list_matches = list(list_opening.finditer(block))
    if len(list_matches) != 1:
        raise BranchMasterError("serialized deformer _sources list is ambiguous")
    list_match = list_matches[0]
    if int(list_match.group(2)) != len(before_refs):
        raise BranchMasterError("serialized deformer source count differs")
    new_opening = (
        list_match.group(1)
        + str(len(before_refs) + len(new_refs)).encode("ascii")
        + list_match.group(3)
    )
    patched_block = (
        block[: list_match.start()] + new_opening + block[list_match.end() :]
    )
    anchor_line = f'<CWarpDeformerSource xs.ref="{anchor_ref}" />\r\n'.encode("ascii")
    if patched_block.count(anchor_line) != 1:
        raise BranchMasterError("serialized D_HEAD source-set line is ambiguous")
    insertion = b"".join(
        f'<CWarpDeformerSource xs.ref="{ref}" />\r\n'.encode("ascii")
        for ref in new_refs
    )
    anchor_offset = patched_block.index(anchor_line) + len(anchor_line)
    patched_block = (
        patched_block[:anchor_offset] + insertion + patched_block[anchor_offset:]
    )
    patched = experiment._replace_exact(
        main_xml, block, patched_block, 1, "CDeformerSourceSet insertion"
    )
    after_root = experiment._parse_xml(patched)
    _, after_refs = _source_set(after_root, experiment)
    anchor_index = before_refs.index(anchor_ref)
    expected = [
        *before_refs[: anchor_index + 1],
        *new_refs,
        *before_refs[anchor_index + 1 :],
    ]
    if after_refs != expected:
        raise BranchMasterError("deformer source ordering differs from plan")
    return patched, {
        "anchor_ref": anchor_ref,
        "inserted_refs": list(new_refs),
        "old_count": len(before_refs),
        "new_count": len(after_refs),
        "insertion_index": anchor_index + 1,
        "all_existing_relative_order_preserved": True,
    }


def _inventory_xml(
    main_xml: bytes,
    *,
    experiment: ModuleType,
    inventory: ModuleType,
) -> dict[str, Any]:
    root = experiment._parse_xml(main_xml)
    shared = root.find("shared")
    model = root.find("main/CModelSource")
    if shared is None or model is None:
        raise BranchMasterError("inventory XML lacks shared/model")
    ids = experiment._id_map(root)
    parameters, parameter_by_guid = inventory._parameter_inventory(model, ids)
    objects = inventory._object_inventory(shared, ids, parameter_by_guid)
    all_objects = (
        objects["art_meshes"]
        + objects["warp_deformers"]
        + objects["rotation_deformers"]
        + objects["parts"]
    )
    used_binding_refs = {
        binding["binding_ref"]
        for item in all_objects
        for binding in item["bindings"]
        if binding.get("binding_ref")
    }
    bound_objects = [
        {
            "kind": next(
                kind
                for kind, group in objects.items()
                if any(candidate is item for candidate in group)
            ),
            "name": item["name"],
            "keyforms": item["keyforms"],
            "parameters": [
                binding["parameter_id"] or binding["parameter_name"]
                for binding in item["bindings"]
            ],
        }
        for item in all_objects
        if item["bindings"]
    ]
    serialized_bindings = len(shared.findall("KeyformBindingSource"))
    counts = {
        "art_meshes": len(objects["art_meshes"]),
        "warp_deformers": len(objects["warp_deformers"]),
        "rotation_deformers": len(objects["rotation_deformers"]),
        "deformers_total": len(objects["warp_deformers"])
        + len(objects["rotation_deformers"]),
        "parts": len(objects["parts"]),
        "parameters": len(parameters),
        "bound_objects": len(bound_objects),
        "object_parameter_bindings": sum(
            len(item["bindings"]) for item in all_objects
        ),
        "serialized_parameter_binding_definitions": serialized_bindings,
        "unreferenced_parameter_binding_definitions": max(
            0, serialized_bindings - len(used_binding_refs)
        ),
        "serialized_keyform_grid_definitions": len(
            shared.findall("KeyformGridSource")
        ),
        "keyforms_total": sum(item["keyforms"] for item in all_objects),
        "physics_settings": inventory._count_source_set(
            model, "CPhysicsSettingsSourceSet"
        ),
        "game_motions": inventory._count_source_set(model, "CGameMotionSet"),
        "motion_sync_settings": inventory._count_source_set(
            model, "CMotionSyncSettingSourceSet"
        ),
    }
    return {
        "cubism_file_format_version": root.get("fileFormatVersion"),
        "counts": counts,
        "parameter_ids": [parameter["id"] for parameter in parameters],
        "parameters": parameters,
        "objects": objects,
        "warp_deformer_names": [item["name"] for item in objects["warp_deformers"]],
        "rotation_deformer_names": [
            item["name"] for item in objects["rotation_deformers"]
        ],
        "bound_objects": bound_objects,
    }


def _topology_xml(
    main_xml: bytes,
    *,
    experiment: ModuleType,
    topology: ModuleType,
) -> dict[str, Any]:
    root = experiment._parse_xml(main_xml)
    shared = root.find("shared")
    if shared is None:
        raise BranchMasterError("topology XML lacks shared definitions")
    meshes = [topology._mesh_row(source) for source in shared.findall("CArtMeshSource")]
    aggregate = {
        "art_meshes": len(meshes),
        "vertices": sum(mesh["vertices"] for mesh in meshes),
        "triangles": sum(mesh["triangles"] for mesh in meshes),
        "unused_vertices": sum(mesh["unused_vertices"] for mesh in meshes),
        "invalid_indices": sum(mesh["invalid_indices"] for mesh in meshes),
        "duplicate_index_triangles": sum(
            mesh["duplicate_index_triangles"] for mesh in meshes
        ),
        "degenerate_area_triangles": sum(
            mesh["degenerate_area_triangles"] for mesh in meshes
        ),
        "zero_triangle_meshes": sum(1 for mesh in meshes if mesh["triangles"] == 0),
    }
    return {"aggregate": aggregate, "meshes": meshes}


def _xml_summary(
    main_xml: bytes,
    *,
    experiment: ModuleType,
    safe: ModuleType,
) -> dict[str, Any]:
    """Summarize the current Cubism XML, including its inline ROOT sentinel."""
    root = experiment._parse_xml(main_xml)
    shared = root.find("shared")
    if shared is None:
        raise BranchMasterError("XML summary lacks shared definitions")
    ids = experiment._id_map(root)
    all_ids = list(ids)
    shared_indices: list[int] = []
    for child in shared:
        raw = child.get("xs.idx")
        if raw is None or not raw.isdigit():
            raise BranchMasterError(
                f"shared definition {child.tag} {child.get('xs.id')!r} lacks xs.idx"
            )
        shared_indices.append(int(raw))
    if len(shared_indices) != len(set(shared_indices)):
        raise BranchMasterError("duplicate shared xs.idx")
    unresolved = [
        ref
        for node in root.iter()
        if (ref := node.get("xs.ref")) is not None and ref not in ids
    ]
    if unresolved:
        raise BranchMasterError(f"unresolved xs.ref values: {unresolved[:5]!r}")
    all_uuids = [
        _canonical_uuid(node.get("uuid"), f"{node.tag} UUID")
        for node in root.iter()
        if node.get("uuid") is not None
    ]
    if len(all_uuids) != len(set(all_uuids)):
        raise BranchMasterError("duplicate UUID values")
    _, source_refs = _source_set(root, experiment)
    semantic_objects = safe._semantic_objects(main_xml)
    safe._validate_deformer_graph(semantic_objects)
    graph: dict[str, dict[str, str]] = {}
    for item in semantic_objects:
        if item.object_type not in {"warp-deformer", "rotation-deformer"}:
            continue
        if item.guid_ref in graph:
            raise BranchMasterError(f"deformer GUID {item.guid_ref!r} is reused")
        graph[item.guid_ref] = {
            "name": item.name,
            "kind": (
                "CWarpDeformerSource"
                if item.object_type == "warp-deformer"
                else "CRotationDeformerSource"
            ),
            "parent_ref": item.parent_ref,
            "uuid": item.guid_uuid,
        }
    return {
        "shared_definitions": len(shared),
        "xs_id_count": len(all_ids),
        "xs_idx_count": len(shared_indices),
        "uuid_count": len(all_uuids),
        "all_xs_ids_unique": len(all_ids) == len(set(all_ids)),
        "all_xs_indices_unique": len(shared_indices) == len(set(shared_indices)),
        "all_uuids_unique": len(all_uuids) == len(set(all_uuids)),
        "all_references_resolved": not unresolved,
        "deformer_source_count": len(source_refs),
        "deformer_source_refs": source_refs,
        "deformer_graph": graph,
    }


def _assert_inventory_delta(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    specs: Sequence[MasterSpec],
    metadata_by_name: dict[str, dict[str, Any]],
    contract: dict[str, Any],
) -> dict[str, Any]:
    expected_deltas = {
        "art_meshes": 0,
        "warp_deformers": 5,
        "rotation_deformers": 0,
        "deformers_total": 5,
        "parts": 0,
        "parameters": 0,
        "bound_objects": 0,
        "object_parameter_bindings": 0,
        "serialized_parameter_binding_definitions": 0,
        "unreferenced_parameter_binding_definitions": 0,
        "serialized_keyform_grid_definitions": 0,
        "keyforms_total": 5,
        "physics_settings": 0,
        "game_motions": 0,
        "motion_sync_settings": 0,
    }
    observed = {
        key: after["counts"][key] - before["counts"][key]
        for key in expected_deltas
    }
    if observed != expected_deltas:
        raise BranchMasterError(f"inventory delta differs: {observed!r}")
    immutable_keys = (
        "cubism_file_format_version",
        "parameter_ids",
        "parameters",
        "rotation_deformer_names",
        "bound_objects",
    )
    for key in immutable_keys:
        if before[key] != after[key]:
            raise BranchMasterError(f"inventory field {key} changed")

    target_names = {child for spec in specs for child in spec.children}
    existing_object_rows_checked = 0
    for group_name, before_rows in before["objects"].items():
        after_rows = after["objects"][group_name]
        after_by_source = {row["source_ref"]: row for row in after_rows}
        if len(after_by_source) != len(after_rows):
            raise BranchMasterError(f"{group_name}: duplicate source_ref in inventory")
        for old_row in before_rows:
            new_row = after_by_source.get(old_row["source_ref"])
            if new_row is None:
                raise BranchMasterError(
                    f"existing inventory object disappeared: {old_row['name']!r}"
                )
            if old_row["name"] in target_names:
                immutable_row = {
                    key: value
                    for key, value in old_row.items()
                    if key not in {"parent_deformer", "parent_deformer_guid_ref"}
                }
                observed_row = {
                    key: value
                    for key, value in new_row.items()
                    if key not in {"parent_deformer", "parent_deformer_guid_ref"}
                }
                if observed_row != immutable_row:
                    raise BranchMasterError(
                        f"target inventory payload changed: {old_row['name']!r}"
                    )
            elif new_row != old_row:
                raise BranchMasterError(
                    f"non-target inventory object changed: {old_row['name']!r}"
                )
            existing_object_rows_checked += 1
    new_warp_rows = [
        row
        for row in after["objects"]["warp_deformers"]
        if row["source_ref"]
        not in {item["source_ref"] for item in before["objects"]["warp_deformers"]}
    ]
    if len(new_warp_rows) != len(specs):
        raise BranchMasterError("new warp inventory-row count differs")
    new_warp_by_name = {row["name"]: row for row in new_warp_rows}
    for spec in specs:
        row = new_warp_by_name.get(spec.name)
        meta = metadata_by_name[spec.name]
        if row is None or row != {
            "name": spec.name,
            "id": spec.internal_id,
            "source_ref": meta["source_ref"],
            "parent_deformer": HEAD_NAME,
            "parent_deformer_guid_ref": HEAD_GUID_REF,
            "parent_part": spec.part_name,
            "parent_part_guid_ref": spec.part_guid_ref,
            "keyforms": 1,
            "bindings": [],
        }:
            raise BranchMasterError(f"{spec.name}: new inventory row differs")
    if after["warp_deformer_names"] != [
        *before["warp_deformer_names"],
        *(spec.name for spec in specs),
    ]:
        raise BranchMasterError("warp deformer names/order differs")
    expected = contract["expected_inventory"]
    exact_counts = {
        "art_meshes": expected["art_meshes"],
        "warp_deformers": expected["warp_deformers"],
        "rotation_deformers": expected["rotation_deformers"],
        "deformers_total": expected["deformers_total"],
        "parts": expected["parts"],
        "parameters": expected["parameters"],
        "bound_objects": expected["bound_objects"],
        "object_parameter_bindings": expected["object_parameter_bindings"],
        "keyforms_total": expected["keyforms_total"],
    }
    for key, value in exact_counts.items():
        if after["counts"][key] != value:
            raise BranchMasterError(
                f"final inventory {key}={after['counts'][key]} differs from {value}"
            )
    return {
        "expected_deltas": expected_deltas,
        "observed_deltas": observed,
        "final_counts": after["counts"],
        "parameter_ids_exact": True,
        "bound_objects_exact": True,
        "existing_object_ids_keyforms_bindings_and_parts_exact": True,
        "existing_object_rows_checked": existing_object_rows_checked,
        "new_master_inventory_rows_exact": True,
        "warp_order_existing_then_new": after["warp_deformer_names"],
    }


def _assert_part_delta(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    specs: Sequence[MasterSpec],
    metadata_by_name: dict[str, dict[str, Any]],
    contract: dict[str, Any],
) -> dict[str, Any]:
    new_guid_refs = {metadata_by_name[spec.name]["guid_ref"] for spec in specs}
    if set(after["entities"]) != set(before["entities"]) | new_guid_refs:
        raise BranchMasterError("Part hierarchy entity set differs")
    for guid_ref, entity in before["entities"].items():
        if after["entities"].get(guid_ref) != entity:
            raise BranchMasterError(
                f"existing Part hierarchy entity changed: {entity['name']!r}"
            )
    if set(after["part_children"]) != set(before["part_children"]):
        raise BranchMasterError("Part definition set changed")
    additions_by_part: dict[str, tuple[str, MasterSpec]] = {}
    records: list[dict[str, Any]] = []
    for spec in specs:
        meta = metadata_by_name[spec.name]
        if spec.part_guid_ref in additions_by_part:
            raise BranchMasterError("two masters target the same Part")
        additions_by_part[spec.part_guid_ref] = (meta["guid_ref"], spec)
        owner = before["entities"].get(spec.part_guid_ref)
        if (
            owner is None
            or owner["source_tag"] != "CPartSource"
            or owner["guid_tag"] != "CPartGuid"
            or owner["name"] != spec.part_name
            or owner["source_ref"] != spec.part_source_ref
        ):
            raise BranchMasterError(f"{spec.name}: approved Part identity differs")
        new_entity = after["entities"][meta["guid_ref"]]
        expected_entity = {
            "source_tag": "CWarpDeformerSource",
            "guid_tag": "CDeformerGuid",
            "name": spec.name,
            "source_ref": meta["source_ref"],
            "guid_uuid": spec.object_uuid,
            "parent_part_ref": spec.part_guid_ref,
        }
        if new_entity != expected_entity:
            raise BranchMasterError(f"{spec.name}: Part entity differs")
    for part_ref, old_children in before["part_children"].items():
        addition = additions_by_part.get(part_ref)
        expected_children = (
            [("CDeformerGuid", addition[0]), *old_children]
            if addition is not None
            else old_children
        )
        if after["part_children"][part_ref] != expected_children:
            raise BranchMasterError(f"Part {part_ref} child order/delta differs")
        if addition is not None:
            records.append(
                {
                    "part_guid_ref": part_ref,
                    "part_name": addition[1].part_name,
                    "part_source_ref": addition[1].part_source_ref,
                    "inserted_master": addition[1].name,
                    "inserted_guid_ref": addition[0],
                    "old_children": len(old_children),
                    "new_children": len(expected_children),
                    "insertion_index": 0,
                }
            )
    expected_memberships = contract["expected_inventory"]["part_memberships"]
    if (
        after["membership_count"] != before["membership_count"] + 5
        or after["membership_count"] != expected_memberships
    ):
        raise BranchMasterError("Part membership total differs")
    return {
        "part_count": after["part_count"],
        "membership_count_before": before["membership_count"],
        "membership_count_after": after["membership_count"],
        "additions": records,
        "all_existing_part_entities_and_child_order_exact": True,
    }


def _assert_graph_delta(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    specs: Sequence[MasterSpec],
    metadata_by_name: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    before_graph = before["deformer_graph"]
    after_graph = after["deformer_graph"]
    new_refs = {metadata_by_name[spec.name]["guid_ref"] for spec in specs}
    if set(after_graph) != set(before_graph) | new_refs:
        raise BranchMasterError("deformer graph GUID set differs")
    child_to_spec = {child: spec for spec in specs for child in spec.children}
    changed: dict[str, dict[str, str]] = {}
    for guid_ref, old in before_graph.items():
        new = after_graph.get(guid_ref)
        if new is None:
            raise BranchMasterError(f"deformer disappeared: {old['name']!r}")
        for key in ("name", "kind", "uuid"):
            if old[key] != new[key]:
                raise BranchMasterError(f"deformer identity changed: {old['name']!r}")
        if old["parent_ref"] != new["parent_ref"]:
            spec = child_to_spec.get(old["name"])
            if spec is None:
                raise BranchMasterError(
                    f"unexpected existing deformer parent change: {old['name']!r}"
                )
            expected_parent = metadata_by_name[spec.name]["guid_ref"]
            if new["parent_ref"] != expected_parent:
                raise BranchMasterError(f"{old['name']!r} graph parent differs")
            changed[old["name"]] = {
                "old_parent_ref": old["parent_ref"],
                "new_parent_ref": new["parent_ref"],
            }
    expected_changed_deformers = {
        child
        for child in child_to_spec
        if any(row["name"] == child for row in before_graph.values())
    }
    if set(changed) != expected_changed_deformers:
        raise BranchMasterError("existing deformer parent-change set differs")
    for spec in specs:
        meta = metadata_by_name[spec.name]
        node = after_graph[meta["guid_ref"]]
        if node != {
            "name": spec.name,
            "kind": "CWarpDeformerSource",
            "parent_ref": HEAD_GUID_REF,
            "uuid": spec.object_uuid,
        }:
            raise BranchMasterError(f"{spec.name}: graph node differs")
    return {
        "new_master_guid_refs": {
            spec.name: metadata_by_name[spec.name]["guid_ref"] for spec in specs
        },
        "changed_existing_deformer_parents": changed,
        "changed_existing_deformer_parent_count": len(changed),
        "all_other_deformer_graph_nodes_exact": True,
        "cycle_free": True,
    }


def _plan(
    source_data: bytes,
    *,
    contract: dict[str, Any],
    specs: Sequence[MasterSpec],
    experiment: ModuleType,
    scaffold: ModuleType,
    safe: ModuleType,
    canvas: ModuleType,
    topology: ModuleType,
    inventory: ModuleType,
) -> tuple[bytes, dict[str, Any]]:
    archive_before, _, _, source_zip, main_before = safe._validate_surgical_layout(
        source_data
    )
    root_before = experiment._parse_xml(main_before)
    if root_before.get("fileFormatVersion") != contract["source"][
        "cubism_file_format_version"
    ]:
        raise BranchMasterError("Cubism file-format version differs")
    shared_before = root_before.find("shared")
    if shared_before is None:
        raise BranchMasterError("source lacks shared definitions")
    model0 = canvas.GeometryModel(main_before, TOLERANCE)
    if len(model0.objects) != 78:
        raise BranchMasterError(f"source object count {len(model0.objects)} != 78")
    head0 = _object_by_name(model0, HEAD_NAME, "source D_HEAD")
    if head0.object_type != "warp-deformer" or head0.guid_ref != HEAD_GUID_REF:
        raise BranchMasterError("source D_HEAD identity differs")
    head_info = experiment._warp_info(root_before, HEAD_NAME)
    if (
        head_info.guid_ref != HEAD_GUID_REF
        or head_info.col != 7
        or head_info.row != 5
        or head_info.parent_ref != head0.parent_ref
    ):
        raise BranchMasterError("source D_HEAD 7x5 contract differs")

    approved_children = {child for spec in specs for child in spec.children}
    direct_children0 = _children(model0, head0)
    if (
        len(direct_children0) != 28
        or {item.name for item in direct_children0} != approved_children
    ):
        raise BranchMasterError("source D_HEAD direct child set differs")
    if any(item.object_type == "rotation-deformer" for item in direct_children0):
        raise BranchMasterError("approved D_HEAD roots unexpectedly include a rotation")
    if any(spec.name in {item.name for item in model0.objects} for spec in specs):
        raise BranchMasterError("one approved master already exists")

    target0_by_name = {item.name: item for item in direct_children0}
    group_evidence: list[dict[str, Any]] = []
    for spec in specs:
        forms = [
            scaffold._form_values(model0, canvas, target0_by_name[name])
            for name in spec.children
        ]
        form_count = sum(len(group) for group in forms)
        scalar_count = sum(len(form) for group in forms for form in group)
        if (
            form_count != spec.existing_form_count
            or scalar_count != spec.existing_position_scalar_count
        ):
            raise BranchMasterError(
                f"{spec.name}: source form/scalar contract differs "
                f"({form_count}, {scalar_count})"
            )
        group_evidence.append(
            {
                "master": spec.name,
                "children": list(spec.children),
                "child_count": len(spec.children),
                "existing_form_count": form_count,
                "existing_position_scalar_count": scalar_count,
            }
        )

    index_plan = _derive_index_plan(
        main_before,
        experiment=experiment,
        contract=contract,
        specs=specs,
    )
    template = experiment._warp_info(root_before, CLONE_TEMPLATE_NAME)
    existing_deformer_ids: list[str] = []
    for tag in ("CWarpDeformerSource", "CRotationDeformerSource"):
        for source in shared_before.findall(tag):
            internal_id = experiment._one_named(source, "CDeformerId", "id").get(
                "idstr"
            )
            if not internal_id:
                raise BranchMasterError("an existing deformer lacks an internal ID")
            existing_deformer_ids.append(internal_id)
    if len(existing_deformer_ids) != len(set(existing_deformer_ids)):
        raise BranchMasterError("existing deformer internal IDs are not unique")
    if set(existing_deformer_ids).intersection(spec.internal_id for spec in specs):
        raise BranchMasterError("approved master internal ID collides")

    current = main_before
    undo: list[Any] = []
    whitelist: list[dict[str, Any]] = []

    def apply(label: str, operation: Callable[[bytes], bytes]) -> None:
        nonlocal current
        before = current
        after = operation(before)
        undo.append(scaffold._make_undo_step(before, after, label))
        current = after

    head_transform = model0.transform(head0.guid_ref)
    all_blocks: list[bytes] = []
    master_metadata: list[dict[str, Any]] = []
    master_local_grids: dict[str, tuple[float, ...]] = {}
    master_original_grids: dict[str, tuple[float, ...]] = {}
    master_neutral_proofs: list[dict[str, Any]] = []
    offsets = index_plan["relative_offsets"]
    for master_index, spec in enumerate(specs):
        original = scaffold._grid(canvas, spec.columns, spec.rows, spec.bounds)
        local = tuple(
            canvas._float32(value)
            for value in model0.inverse_many(head_transform, original)
        )
        reconstructed = model0.forward_many(head_transform, local)
        error = canvas._maximum_error(original, reconstructed)
        if error >= TOLERANCE:
            raise BranchMasterError(
                f"{spec.name}: neutral master grid reconstruction error {error}px"
            )
        id_offset = 4 * master_index
        new_ids = tuple(index_plan["new_ids"][id_offset : id_offset + 4])
        base = index_plan["source_bases"][master_index]
        new_indices = (
            base + offsets["source"],
            base + offsets["positions"],
            base + offsets["form"],
            base + offsets["deformer_guid"],
        )
        blocks, metadata = _clone_master_blocks(
            main_before,
            experiment=experiment,
            template=template,
            spec=spec,
            source_sha=SOURCE_SHA256,
            ids=new_ids,
            indices=new_indices,
            parent_ref=HEAD_GUID_REF,
            original_positions=original,
            local_positions=local,
        )
        all_blocks.extend(blocks)
        master_metadata.append(metadata)
        master_local_grids[spec.name] = local
        master_original_grids[spec.name] = original
        master_neutral_proofs.append(
            {
                "master": spec.name,
                "canvas_bounds": list(spec.bounds),
                "position_scalars": len(original),
                "max_reconstruction_error_px": error,
            }
        )
    all_generated_uuids = [
        value for metadata in master_metadata for value in metadata["uuids"].values()
    ]
    if len(all_generated_uuids) != 25 or len(set(all_generated_uuids)) != 25:
        raise BranchMasterError("generated UUID plan is not 25 unique values")

    apply(
        "append five master shared-definition groups",
        lambda data: experiment._append_shared_blocks(data, all_blocks),
    )
    whitelist.append(
        {
            "kind": "new-shared-definitions",
            "definition_count": len(all_blocks),
            "masters": [metadata["name"] for metadata in master_metadata],
            "source_refs": [metadata["source_ref"] for metadata in master_metadata],
        }
    )
    metadata_by_name = {metadata["name"]: metadata for metadata in master_metadata}
    new_source_refs = [metadata_by_name[spec.name]["source_ref"] for spec in specs]
    source_set_record: dict[str, Any] = {}

    def patch_source_set(data: bytes) -> bytes:
        nonlocal source_set_record
        patched, source_set_record = _patch_source_set_after(
            data,
            experiment=experiment,
            anchor_ref=head0.source_ref,
            new_refs=new_source_refs,
        )
        return patched

    apply("insert five masters after D_HEAD source", patch_source_set)
    whitelist.append({"kind": "deformer-source-set", **source_set_record})

    part_patch_records: list[dict[str, Any]] = []
    for spec in specs:
        meta = metadata_by_name[spec.name]
        apply(
            f"register {spec.name} in {spec.part_name}",
            lambda data, part_ref=spec.part_guid_ref, guid_ref=meta["guid_ref"]: (
                experiment._patch_part_hierarchy(data, part_ref, guid_ref)
            ),
        )
        record = {
            "kind": "part-membership",
            "master": spec.name,
            "part_name": spec.part_name,
            "part_guid_ref": spec.part_guid_ref,
            "part_source_ref": spec.part_source_ref,
            "new_deformer_guid_ref": meta["guid_ref"],
        }
        part_patch_records.append(record)
        whitelist.append(record)

    scaffold_model = canvas.GeometryModel(current, TOLERANCE)
    scaffold_head = _object_by_name(scaffold_model, HEAD_NAME, "scaffold D_HEAD")
    if {item.name for item in _children(scaffold_model, scaffold_head)} != (
        approved_children | {spec.name for spec in specs}
    ):
        raise BranchMasterError("pre-migration D_HEAD child set differs")
    scaffold_masters = {
        spec.name: _object_by_name(scaffold_model, spec.name, spec.name)
        for spec in specs
    }
    for spec in specs:
        master = scaffold_masters[spec.name]
        if master.parent_ref != HEAD_GUID_REF or master.guid_uuid != spec.object_uuid:
            raise BranchMasterError(f"{spec.name}: scaffold identity/parent differs")
        transform = scaffold_model.transform(master.guid_ref)
        if getattr(transform, "neutral_match_error_px", 0.0) >= TOLERANCE:
            raise BranchMasterError(f"{spec.name}: no exact neutral transform")

    coordinate_proof: list[dict[str, Any]] = []
    planned_forms: dict[str, tuple[tuple[float, ...], ...]] = {}
    parent_records: list[dict[str, Any]] = []
    position_records: list[dict[str, Any]] = []
    for spec in specs:
        master = scaffold_masters[spec.name]
        for child_name in spec.children:
            target0 = target0_by_name[child_name]
            converted, proof = scaffold._convert_forms(
                canvas=canvas,
                old_model=model0,
                new_model=scaffold_model,
                old_parent=head0,
                new_parent=master,
                target=target0,
            )
            old_forms = scaffold._form_values(model0, canvas, target0)
            planned_forms[target0.guid_uuid] = converted
            parent_record: dict[str, Any] = {}

            def patch_parent(data: bytes) -> bytes:
                nonlocal parent_record
                patched, parent_record = scaffold._patch_parent_ref(
                    data,
                    safe=safe,
                    target=target0,
                    expected_old_ref=HEAD_GUID_REF,
                    new_ref=master.guid_ref,
                    label=f"{child_name} -> {spec.name}",
                )
                return patched

            apply(f"reparent {child_name} to {spec.name}", patch_parent)
            parent_records.append(parent_record)
            whitelist.append(parent_record)
            current_target = _object_by_name(
                canvas.GeometryModel(current, TOLERANCE),
                child_name,
                f"current {child_name}",
            )
            records: list[dict[str, Any]] = []

            def patch_forms(data: bytes) -> bytes:
                nonlocal records
                patched, records = scaffold._patch_form_positions(
                    data,
                    safe=safe,
                    canvas=canvas,
                    target=current_target,
                    expected_old=old_forms,
                    replacement=converted,
                    label=f"{child_name} compensated forms",
                )
                return patched

            apply(f"compensate {child_name} forms", patch_forms)
            position_records.extend(records)
            whitelist.extend(records)
            coordinate_proof.extend(
                [{"master": spec.name, **row} for row in proof]
            )

    if (
        len(parent_records) != contract["whitelist"]["existing_parent_refs_changed"]
        or len(position_records)
        != contract["whitelist"]["existing_position_arrays_changed"]
        or sum(row["new_count"] for row in position_records)
        != contract["whitelist"]["existing_position_scalars_changed"]
        or len(coordinate_proof) != 84
    ):
        raise BranchMasterError("reparent/form whitelist cardinality differs")
    max_coordinate_error = max(
        row["max_reconstruction_error_px"] for row in coordinate_proof
    )
    if max_coordinate_error >= TOLERANCE:
        raise BranchMasterError("aggregate child canvas reconstruction error differs")

    final_model = canvas.GeometryModel(current, TOLERANCE)
    final_head = _object_by_name(final_model, HEAD_NAME, "final D_HEAD")
    final_master_names = {spec.name for spec in specs}
    if {item.name for item in _children(final_model, final_head)} != final_master_names:
        raise BranchMasterError("final D_HEAD does not have exactly five masters")
    final_by_uuid = {item.guid_uuid: item for item in final_model.objects}
    before_by_uuid = {item.guid_uuid: item for item in model0.objects}
    if set(final_by_uuid) != set(before_by_uuid) | {spec.object_uuid for spec in specs}:
        raise BranchMasterError("final object UUID set differs")
    child_to_spec = {child: spec for spec in specs for child in spec.children}
    for guid_uuid, before in before_by_uuid.items():
        after = final_by_uuid[guid_uuid]
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
            raise BranchMasterError(f"existing object identity changed: {before.name!r}")
        spec = child_to_spec.get(before.name)
        expected_parent_uuid = spec.object_uuid if spec is not None else before.parent_uuid
        if after.parent_uuid != expected_parent_uuid:
            raise BranchMasterError(f"existing object parent differs: {before.name!r}")
        if model0.original_canvas(before) != final_model.original_canvas(after):
            raise BranchMasterError(
                f"existing original-canvas payload changed: {before.name!r}"
            )

    final_root = experiment._parse_xml(current)
    final_master_evidence: list[dict[str, Any]] = []
    final_canvas_proof: list[dict[str, Any]] = []
    for spec in specs:
        meta = metadata_by_name[spec.name]
        master = final_by_uuid[spec.object_uuid]
        if (
            master.object_type != "warp-deformer"
            or master.name != spec.name
            or master.source_ref != meta["source_ref"]
            or master.guid_ref != meta["guid_ref"]
            or master.parent_ref != HEAD_GUID_REF
        ):
            raise BranchMasterError(f"{spec.name}: final semantic identity differs")
        info = experiment._warp_info(final_root, spec.name)
        if (
            info.deformer_id != spec.internal_id
            or info.guid_uuid != spec.object_uuid
            or info.parent_ref != HEAD_GUID_REF
            or info.parent_part_ref != spec.part_guid_ref
            or info.col != spec.columns
            or info.row != spec.rows
            or not scaffold._f32_equal(
                canvas, info.original_positions, master_original_grids[spec.name]
            )
            or not scaffold._f32_equal(
                canvas, info.positions, master_local_grids[spec.name]
            )
        ):
            raise BranchMasterError(f"{spec.name}: final serialization differs")
        children = _children(final_model, master)
        if {item.name for item in children} != set(spec.children):
            raise BranchMasterError(f"{spec.name}: final child set differs")
        source = final_model.source(master)
        grid = experiment._one_named(source, "KeyformGridSource", "keyformGridSource")
        bindings = experiment._direct_named(grid, "array_list", "keyformBindings")
        if bindings.get("count") != "0" or len(bindings) != 0:
            raise BranchMasterError(f"{spec.name}: new master is unexpectedly bound")
        final_master_evidence.append(
            {
                **meta,
                "children": list(spec.children),
                "child_count": len(children),
                "keyforms": 1,
                "parameter_bindings": 0,
                "neutral_only": True,
                "part_name": spec.part_name,
            }
        )
        parent_transform = final_model.transform(master.guid_ref)
        for child_name in spec.children:
            target_before = target0_by_name[child_name]
            target_after = final_by_uuid[target_before.guid_uuid]
            expected_forms = planned_forms[target_before.guid_uuid]
            actual_forms = scaffold._form_values(final_model, canvas, target_after)
            if len(actual_forms) != len(expected_forms):
                raise BranchMasterError(f"{child_name}: final form count differs")
            old_forms = scaffold._form_values(model0, canvas, target_before)
            old_parent_transform = model0.transform(head0.guid_ref)
            for form_index, (old_local, expected_local, actual_local) in enumerate(
                zip(old_forms, expected_forms, actual_forms)
            ):
                if not scaffold._f32_equal(canvas, actual_local, expected_local):
                    raise BranchMasterError(
                        f"{child_name}: final form {form_index} differs from plan"
                    )
                old_canvas = model0.forward_many(old_parent_transform, old_local)
                new_canvas = final_model.forward_many(parent_transform, actual_local)
                error = canvas._maximum_error(old_canvas, new_canvas)
                if error >= TOLERANCE:
                    raise BranchMasterError(
                        f"{child_name}: final form {form_index} error {error}px"
                    )
                final_canvas_proof.append(
                    {
                        "master": spec.name,
                        "object_name": child_name,
                        "object_uuid": target_before.guid_uuid,
                        "object_type": target_before.object_type,
                        "form_index": form_index,
                        "coordinate_count": len(actual_local),
                        "max_reconstruction_error_px": error,
                    }
                )
    if len(final_canvas_proof) != 84:
        raise BranchMasterError("final canvas proof count differs")
    final_max_error = max(row["max_reconstruction_error_px"] for row in final_canvas_proof)
    if final_max_error >= TOLERANCE:
        raise BranchMasterError("final canvas proof exceeds tolerance")

    before_summary = _xml_summary(
        main_before, experiment=experiment, safe=safe
    )
    after_summary = _xml_summary(current, experiment=experiment, safe=safe)
    expected_shared = contract["expected_inventory"]["shared_definitions_pre_cubism"]
    if (
        after_summary["shared_definitions"] != before_summary["shared_definitions"] + 20
        or after_summary["shared_definitions"] != expected_shared
        or after_summary["xs_id_count"] != before_summary["xs_id_count"] + 20
        or after_summary["xs_idx_count"] != before_summary["xs_idx_count"] + 20
        or after_summary["uuid_count"] != before_summary["uuid_count"] + 25
        or after_summary["deformer_source_count"]
        != before_summary["deformer_source_count"] + 5
        or after_summary["deformer_source_count"]
        != contract["expected_inventory"]["deformer_source_refs"]
    ):
        raise BranchMasterError("serialized XML inventory delta differs")
    graph_proof = _assert_graph_delta(
        before_summary,
        after_summary,
        specs=specs,
        metadata_by_name=metadata_by_name,
    )

    part_before = experiment._part_hierarchy_state(root_before)
    part_after = experiment._part_hierarchy_state(final_root)
    part_proof = _assert_part_delta(
        part_before,
        part_after,
        specs=specs,
        metadata_by_name=metadata_by_name,
        contract=contract,
    )
    inventory_before = _inventory_xml(
        main_before, experiment=experiment, inventory=inventory
    )
    inventory_after = _inventory_xml(current, experiment=experiment, inventory=inventory)
    inventory_proof = _assert_inventory_delta(
        inventory_before,
        inventory_after,
        specs=specs,
        metadata_by_name=metadata_by_name,
        contract=contract,
    )
    topology_before = _topology_xml(
        main_before, experiment=experiment, topology=topology
    )
    topology_after = _topology_xml(current, experiment=experiment, topology=topology)
    if topology_before != topology_after:
        raise BranchMasterError("ArtMesh topology inventory changed")
    if (
        topology_after["aggregate"]["art_meshes"]
        != contract["expected_inventory"]["art_meshes"]
        or topology_after["aggregate"]["vertices"]
        != contract["expected_inventory"]["art_mesh_vertices"]
        or topology_after["aggregate"]["triangles"]
        != contract["expected_inventory"]["art_mesh_triangles"]
    ):
        raise BranchMasterError("ArtMesh topology totals differ from contract")

    normalized = current
    for step in reversed(undo):
        normalized = step.apply(normalized)
    if normalized != main_before:
        raise BranchMasterError("undo ledger does not restore source main.xml byte-exact")

    output_data = safe._replace_main_xml(source_data, current)
    archive_after, _, _, _, decoded_after = safe._validate_surgical_layout(output_data)
    if decoded_after != current:
        raise BranchMasterError("planned archive main.xml differs")
    archive_proof = safe._compare_entry_preservation(
        source_data,
        archive_before,
        output_data,
        archive_after,
        main_may_change=True,
    )
    if (
        archive_proof.get("entry_count")
        != contract["expected_inventory"]["caff_members"]
        or archive_proof.get("entry_count", 0) - 1
        != contract["expected_inventory"]["caff_non_main_members_byte_exact"]
        or archive_proof.get("all_non_main_entries_byte_identical") is not True
    ):
        raise BranchMasterError("CAFF non-main preservation proof differs")

    max_master_error = max(
        row["max_reconstruction_error_px"] for row in master_neutral_proofs
    )
    return output_data, {
        "schema": "jade.cubism.head-branch-masters-audit.v1",
        "status": "ok",
        "operation": "create_five_neutral_head_macro_branches_and_preserve_84_forms",
        "production_status": contract["production_status"],
        "source_sha256": _sha256(source_data),
        "source_bytes": len(source_data),
        "planned_output_sha256": _sha256(output_data),
        "planned_output_bytes": len(output_data),
        "main_xml_sha256_before": _sha256(main_before),
        "main_xml_sha256_after": _sha256(current),
        "main_xml_bytes_before": len(main_before),
        "main_xml_bytes_after": len(current),
        "source_zlib_level": source_zip.zlib_level,
        "python_zlib_runtime": safe.zlib.ZLIB_RUNTIME_VERSION,
        "contract": {
            "filename": CONTRACT_NAME,
            "sha256": CONTRACT_SHA256,
            "status": contract["status"],
            "required_editor": contract["source"]["required_editor"],
            "upgrade_forbidden": contract["source"]["upgrade_forbidden"],
            "planned_flattening": contract["planned_flattening"],
        },
        "index_allocation": index_plan,
        "source_groups": group_evidence,
        "new_masters": final_master_evidence,
        "master_neutral_proof": {
            "count": len(master_neutral_proofs),
            "max_reconstruction_error_px": max_master_error,
            "rows": master_neutral_proofs,
        },
        "child_canvas_proof": {
            "form_count": len(final_canvas_proof),
            "position_scalar_count": sum(
                row["coordinate_count"] for row in final_canvas_proof
            ),
            "max_reconstruction_error_px": final_max_error,
            "rows": final_canvas_proof,
        },
        "whitelist_cardinality": {
            "new_shared_definitions": len(all_blocks),
            "new_unique_uuids": len(all_generated_uuids),
            "deformer_source_refs_added": len(new_source_refs),
            "part_memberships_added": len(part_patch_records),
            "existing_parent_refs_changed": len(parent_records),
            "existing_position_arrays_changed": len(position_records),
            "existing_position_scalars_changed": sum(
                row["new_count"] for row in position_records
            ),
        },
        "whitelist": whitelist,
        "source_set_proof": source_set_record,
        "part_hierarchy_proof": part_proof,
        "deformer_graph_proof": graph_proof,
        "inventory_proof": inventory_proof,
        "topology_proof": topology_after,
        "xml_summary_before": {
            key: before_summary[key]
            for key in (
                "shared_definitions",
                "xs_id_count",
                "xs_idx_count",
                "uuid_count",
                "deformer_source_count",
            )
        },
        "xml_summary_after": {
            key: after_summary[key]
            for key in (
                "shared_definitions",
                "xs_id_count",
                "xs_idx_count",
                "uuid_count",
                "deformer_source_count",
                "all_xs_ids_unique",
                "all_xs_indices_unique",
                "all_uuids_unique",
                "all_references_resolved",
            )
        },
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
        raise BranchMasterError("source/output filename differs from pinned transaction")
    if source.parent != REPORTS_DIR or output.parent != REPORTS_DIR:
        raise BranchMasterError("source/output must be direct children of reports")
    if source == output:
        raise BranchMasterError("source and output must be distinct")
    if output.exists() or audit.exists():
        raise BranchMasterError("output or audit exists; refusing overwrite")

    contract, specs, contract_path = _load_contract()
    source_data = source.read_bytes()
    if len(source_data) != SOURCE_BYTES or _sha256(source_data) != SOURCE_SHA256:
        raise BranchMasterError("source bytes/SHA-256 differs from pinned checkpoint")
    experiment, scaffold, safe, canvas, topology, inventory = _load_dependencies()
    output_data, result = _plan(
        source_data,
        contract=contract,
        specs=specs,
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
        raise BranchMasterError("source changed during in-memory plan")
    if _hash_file(contract_path) != CONTRACT_SHA256:
        raise BranchMasterError("contract changed during in-memory plan")
    if args.dry_run:
        if output.exists() or audit.exists():
            raise BranchMasterError("dry-run unexpectedly created an output")
        result["verdict"] = "PASS_DRY_RUN__NO_FILE_WRITTEN"
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0

    created_output = False
    created_audit = False
    try:
        safe._write_new_file(output, output_data)
        created_output = True
        if output.read_bytes() != output_data:
            raise BranchMasterError("written output differs from validated plan")
        if source.read_bytes() != source_data:
            raise BranchMasterError("source changed during transaction")
        written_inventory = safe._structural_inventory(output)
        if written_inventory["counts"] != result["inventory_proof"]["final_counts"]:
            raise BranchMasterError("written output inventory differs from plan")
        written_topology = topology.inventory(output, MAX_XML_BYTES)
        if written_topology["aggregate"] != result["topology_proof"]["aggregate"]:
            raise BranchMasterError("written output topology differs from plan")
        result["output_written"] = True
        result["output_sha256"] = _sha256(output_data)
        result["output_bytes"] = len(output_data)
        result["verdict"] = "PASS_TEST_TRANSACTION__CUBISM_5_2_03_GATE_REQUIRED"
        _write_json_exclusive(audit, result)
        created_audit = True
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception:
        if created_audit and audit.exists():
            audit.unlink()
        if created_output and output.exists():
            output.unlink()
        raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
