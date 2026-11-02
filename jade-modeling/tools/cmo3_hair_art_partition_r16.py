#!/usr/bin/env python3
"""Split Jade r15 rear-hair ArtMeshes into cap + 13 mobile volumes.

This is a non-destructive structural art derivation: all clones reuse the
existing embedded pixels and texture inputs.  Every original triangle is
rendered exactly once, so the neutral composite remains the v004 artwork while
the model gains genuinely independent rear-hair objects for the next rig pass.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence


TOOLS_DIR = Path(__file__).resolve(strict=True).parent
TOLERANCE = 0.001

GROUP_OBJECT_NAMES: dict[str, str] = {
    "BackC_L": "JAD_HAIR_BACK_C_V005_L",
    "BackC_C": "JAD_HAIR_BACK_C_V005_C",
    "BackC_R": "JAD_HAIR_BACK_C_V005_R",
    "BackLInner_U": "JAD_HAIR_BACK_L_INNER_V005_U",
    "BackLInner_D": "JAD_HAIR_BACK_L_INNER_V005_D",
    "BackRInner_U": "JAD_HAIR_BACK_R_INNER_V005_U",
    "BackRInner_D": "JAD_HAIR_BACK_R_INNER_V005_D",
    "BackLOuter_U": "JAD_HAIR_BACK_L_OUTER_V005_U",
    "BackLOuter_M": "JAD_HAIR_BACK_L_OUTER_V005_M",
    "BackLOuter_D": "JAD_HAIR_BACK_L_OUTER_V005_D",
    "BackROuter_U": "JAD_HAIR_BACK_R_OUTER_V005_U",
    "BackROuter_M": "JAD_HAIR_BACK_R_OUTER_V005_M",
    "BackROuter_D": "JAD_HAIR_BACK_R_OUTER_V005_D",
}


class HairArtPartitionError(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise HairArtPartitionError(message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _generated_uuid(source_sha: str, role: str) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"jade-cmo3-hair-art-v005-r16:{source_sha}:{role}",
        )
    )


def _direct(parent: Any, tag: str, name: str, label: str) -> Any:
    matches = [child for child in parent if child.tag == tag and child.get("xs.n") == name]
    _require(len(matches) == 1, f"{label}: expected one direct {tag}/{name}")
    return matches[0]


def _descendant(parent: Any, tag: str, name: str, label: str) -> Any:
    matches = [node for node in parent.iter(tag) if node.get("xs.n") == name]
    _require(len(matches) == 1, f"{label}: expected one {tag}/{name}")
    return matches[0]


def _tokens(node: Any, label: str) -> list[str]:
    values = (node.text or "").split()
    _require(len(values) == int(node.get("count", "-1")), f"{label}: count differs")
    return values


def _set_tokens(node: Any, values: Iterable[Any]) -> None:
    tokens = [str(value) for value in values]
    node.set("count", str(len(tokens)))
    node.text = " ".join(tokens)


def _pair_subset(tokens: Sequence[str], used: Sequence[int], label: str) -> list[str]:
    _require(len(tokens) % 2 == 0, f"{label}: odd coordinate count")
    count = len(tokens) // 2
    _require(all(0 <= index < count for index in used), f"{label}: vertex out of range")
    result: list[str] = []
    for index in used:
        result.extend(tokens[2 * index : 2 * index + 2])
    return result


def _subset_source(source: Any, triangle_indices: Sequence[int], label: str) -> dict[str, Any]:
    indices_node = _direct(source, "int-array", "indices", label)
    original_indices = [int(value) for value in _tokens(indices_node, f"{label} indices")]
    _require(len(original_indices) % 3 == 0, f"{label}: malformed triangle list")
    triangle_count = len(original_indices) // 3
    _require(triangle_indices, f"{label}: empty triangle partition")
    _require(
        len(set(triangle_indices)) == len(triangle_indices)
        and all(0 <= index < triangle_count for index in triangle_indices),
        f"{label}: invalid triangle partition",
    )
    selected_original = [
        original_indices[3 * index : 3 * index + 3] for index in triangle_indices
    ]
    used = sorted({vertex for triangle in selected_original for vertex in triangle})
    old_to_new = {old: new for new, old in enumerate(used)}
    remapped = [old_to_new[vertex] for triangle in selected_original for vertex in triangle]
    _set_tokens(indices_node, remapped)

    source_positions = _direct(source, "float-array", "positions", label)
    source_uvs = _direct(source, "float-array", "uvs", label)
    original_source_positions = _tokens(source_positions, f"{label} source positions")
    original_uvs = _tokens(source_uvs, f"{label} uvs")
    original_vertex_count = len(original_source_positions) // 2
    _require(len(original_uvs) == len(original_source_positions), f"{label}: UV size differs")
    _set_tokens(source_positions, _pair_subset(original_source_positions, used, label))
    _set_tokens(source_uvs, _pair_subset(original_uvs, used, label))

    keyforms = _direct(source, "carray_list", "keyforms", label)
    _require(len(keyforms) > 0, f"{label}: no keyforms")
    for form_index, form in enumerate(keyforms):
        positions = _direct(form, "float-array", "positions", f"{label} form {form_index}")
        values = _tokens(positions, f"{label} form {form_index} positions")
        _require(len(values) == original_vertex_count * 2, f"{label}: form size differs")
        _set_tokens(positions, _pair_subset(values, used, label))

    editable = _descendant(source, "GEditableMesh2", "editableMesh", label)
    point = _direct(editable, "float-array", "point", label)
    point_priority = _direct(editable, "byte-array", "pointPriority", label)
    edge = _direct(editable, "short-array", "edge", label)
    edge_priority = _direct(editable, "byte-array", "edgePriority", label)
    point_uid = _direct(editable, "int-array", "pointUid", label)
    point_values = _tokens(point, f"{label} editable points")
    priority_values = _tokens(point_priority, f"{label} point priorities")
    _require(len(point_values) == original_vertex_count * 2, f"{label}: editable point size differs")
    _require(len(priority_values) == original_vertex_count, f"{label}: point priority size differs")
    _set_tokens(point, _pair_subset(point_values, used, label))
    _set_tokens(point_priority, [priority_values[index] for index in used])
    _set_tokens(point_uid, range(len(used)))
    editable.set("nextPointUid", str(len(used)))

    unique_edges: list[tuple[int, int]] = []
    seen_edges: set[tuple[int, int]] = set()
    for offset in range(0, len(remapped), 3):
        triangle = remapped[offset : offset + 3]
        for a, b in ((triangle[0], triangle[1]), (triangle[1], triangle[2]), (triangle[2], triangle[0])):
            key = tuple(sorted((a, b)))
            if key not in seen_edges:
                seen_edges.add(key)
                unique_edges.append(key)
    _set_tokens(edge, [value for pair in unique_edges for value in pair])
    _set_tokens(edge_priority, [30] * len(unique_edges))
    return {
        "source_triangles": list(triangle_indices),
        "triangle_count": len(triangle_indices),
        "vertex_count_before": original_vertex_count,
        "vertex_count_after": len(used),
        "edge_count": len(unique_edges),
        "old_vertex_indices": used,
    }


def _serialize(element: Any) -> bytes:
    element.tail = None
    return __import__("xml.etree.ElementTree", fromlist=["ElementTree"]).tostring(
        element, encoding="utf-8", short_empty_elements=True
    )


def _patch_refs(element: Any, replacements: dict[str, str]) -> None:
    for node in element.iter():
        ref = node.get("xs.ref")
        if ref in replacements:
            node.set("xs.ref", replacements[ref])


def _clone_shared_node(
    node: Any,
    *,
    ref: str,
    idx: int,
    replacements: dict[str, str],
) -> Any:
    cloned = copy.deepcopy(node)
    cloned.set("xs.id", ref)
    cloned.set("xs.idx", str(idx))
    _patch_refs(cloned, replacements)
    return cloned


def _clone_segment(
    *,
    original_source: Any,
    root: Any,
    source_sha: str,
    group: str,
    object_name: str,
    triangle_indices: Sequence[int],
    slots: dict[str, tuple[str, int]],
) -> tuple[list[bytes], dict[str, Any]]:
    ids = {
        str(node.get("xs.id")): node
        for node in root.find("shared")
        if node.get("xs.id")
    }
    old_source_ref = str(original_source.get("xs.id"))
    old_grid_ref = str(_descendant(original_source, "KeyformGridSource", "keyformGridSource", object_name).get("xs.ref"))
    old_drawable_ref = str(_descendant(original_source, "CDrawableGuid", "guid", object_name).get("xs.ref"))
    extensions = _descendant(original_source, "carray_list", "_extensions", object_name)
    old_texture_extension_refs = [
        str(node.get("xs.ref")) for node in extensions if node.tag == "CTextureInputExtension"
    ]
    _require(len(old_texture_extension_refs) == 1, f"{object_name}: texture extension differs")
    old_texture_extension_ref = old_texture_extension_refs[0]
    old_texture_extension = ids[old_texture_extension_ref]
    model_inputs = [
        str(node.get("xs.ref"))
        for node in old_texture_extension.iter("CTextureInput_ModelImage")
        if node.get("xs.ref")
    ]
    _require(len(set(model_inputs)) == 1, f"{object_name}: model input differs")
    old_model_input_ref = model_inputs[0]

    old_grid = ids[old_grid_ref]
    old_binding_refs = [
        str(node.get("xs.ref"))
        for node in _direct(old_grid, "array_list", "keyformBindings", object_name)
    ]
    old_form_refs = [
        str(_descendant(entry, "CFormGuid", "keyformGuid", object_name).get("xs.ref"))
        for entry in _direct(old_grid, "array_list", "keyformsOnGrid", object_name)
    ]
    _require(len(old_binding_refs) == 2 and len(old_form_refs) == 9, f"{object_name}: expected r15 3x3 grid")
    _require(len(set(old_form_refs)) == 9, f"{object_name}: form GUIDs are not unique")

    role = lambda suffix: f"segment:{group}:{suffix}"
    new_source_ref, new_source_idx = slots[role("source")]
    new_grid_ref, new_grid_idx = slots[role("grid")]
    new_drawable_ref, new_drawable_idx = slots[role("drawable-guid")]
    new_texture_extension_ref, new_texture_extension_idx = slots[role("texture-extension")]
    new_model_input_ref, new_model_input_idx = slots[role("model-input")]
    new_binding_pairs = [slots[role(f"binding-{index}")] for index in range(2)]
    new_form_pairs = [slots[role(f"form-guid-{index}")] for index in range(9)]
    replacements = {
        old_source_ref: new_source_ref,
        old_grid_ref: new_grid_ref,
        old_drawable_ref: new_drawable_ref,
        old_texture_extension_ref: new_texture_extension_ref,
        old_model_input_ref: new_model_input_ref,
        **{old: new_binding_pairs[index][0] for index, old in enumerate(old_binding_refs)},
        **{old: new_form_pairs[index][0] for index, old in enumerate(old_form_refs)},
    }

    source = _clone_shared_node(
        original_source,
        ref=new_source_ref,
        idx=new_source_idx,
        replacements=replacements,
    )
    _descendant(source, "s", "localName", object_name).text = object_name
    _descendant(source, "CDrawableId", "id", object_name).set("idstr", object_name)
    for index, node in enumerate(source.iter("CExtensionGuid")):
        node.set("uuid", _generated_uuid(source_sha, role(f"inline-extension-{index}")))
    mesh_guid = _descendant(source, "GEditableMeshGuid", "meshGuid", object_name)
    mesh_guid.set("uuid", _generated_uuid(source_sha, role("editable-mesh-guid")))
    subset = _subset_source(source, triangle_indices, object_name)

    grid = _clone_shared_node(
        old_grid,
        ref=new_grid_ref,
        idx=new_grid_idx,
        replacements=replacements,
    )
    bindings = []
    for index, old_ref in enumerate(old_binding_refs):
        new_ref, new_idx = new_binding_pairs[index]
        bindings.append(
            _clone_shared_node(
                ids[old_ref],
                ref=new_ref,
                idx=new_idx,
                replacements=replacements,
            )
        )
    form_guids = []
    for index, old_ref in enumerate(old_form_refs):
        new_ref, new_idx = new_form_pairs[index]
        form_guid = _clone_shared_node(
            ids[old_ref],
            ref=new_ref,
            idx=new_idx,
            replacements=replacements,
        )
        form_guid.set("uuid", _generated_uuid(source_sha, role(f"form-guid-{index}")))
        form_guids.append(form_guid)
    drawable = _clone_shared_node(
        ids[old_drawable_ref],
        ref=new_drawable_ref,
        idx=new_drawable_idx,
        replacements=replacements,
    )
    drawable.set("uuid", _generated_uuid(source_sha, role("drawable-guid")))
    drawable.set("note", object_name)
    texture_extension = _clone_shared_node(
        old_texture_extension,
        ref=new_texture_extension_ref,
        idx=new_texture_extension_idx,
        replacements=replacements,
    )
    extension_guid = _descendant(texture_extension, "CExtensionGuid", "guid", object_name)
    extension_guid.set("uuid", _generated_uuid(source_sha, role("texture-extension-guid")))
    model_input = _clone_shared_node(
        ids[old_model_input_ref],
        ref=new_model_input_ref,
        idx=new_model_input_idx,
        replacements=replacements,
    )
    blocks = [
        _serialize(source),
        _serialize(grid),
        *(_serialize(binding) for binding in bindings),
        *(_serialize(form_guid) for form_guid in form_guids),
        _serialize(drawable),
        _serialize(texture_extension),
        _serialize(model_input),
    ]
    return blocks, {
        "group": group,
        "object_name": object_name,
        "source_ref": new_source_ref,
        "drawable_guid_ref": new_drawable_ref,
        "grid_ref": new_grid_ref,
        "binding_refs": [pair[0] for pair in new_binding_pairs],
        "form_guid_refs": [pair[0] for pair in new_form_pairs],
        "texture_extension_ref": new_texture_extension_ref,
        "model_input_ref": new_model_input_ref,
        **subset,
    }


def _patch_drawable_source_set(main: bytes, new_source_refs: Sequence[str]) -> bytes:
    pattern = re.compile(
        rb'(<CDrawableSourceSet\b(?=[^>]*\bxs\.n="drawableSourceSet")[^>]*>.*?'
        rb'<carray_list\b(?=[^>]*\bxs\.n="_sources")[^>]*\bcount=")'
        rb'(\d+)("[^>]*>)(.*?)(</carray_list>.*?</CDrawableSourceSet>)',
        re.DOTALL,
    )
    matches = list(pattern.finditer(main))
    _require(len(matches) == 1, "drawable source set is not unique")
    match = matches[0]
    old_count = int(match.group(2))
    old_refs = re.findall(rb'<CArtMeshSource xs\.ref="(#[0-9]+)"\s*/>', match.group(4))
    _require(len(old_refs) == old_count, "drawable source set count differs")
    _require(not set(ref.encode("ascii") for ref in new_source_refs).intersection(old_refs), "new drawable source already exists")
    additions = b"\r\n".join(
        f'<CArtMeshSource xs.ref="{ref}" />'.encode("ascii") for ref in new_source_refs
    )
    body = match.group(4)
    if body and not body.endswith(b"\r\n"):
        body += b"\r\n"
    replacement = (
        match.group(1)
        + str(old_count + len(new_source_refs)).encode("ascii")
        + match.group(3)
        + body
        + additions
        + b"\r\n"
        + match.group(5)
    )
    return main[: match.start()] + replacement + main[match.end() :]


def _part_source_ref(root: Any, part_guid_ref: str) -> str:
    matches = []
    for source in root.find("shared").findall("CPartSource"):
        guid = _descendant(source, "CPartGuid", "guid", "Part")
        if guid.get("xs.ref") == part_guid_ref:
            matches.append(str(source.get("xs.id")))
    _require(len(matches) == 1, f"Part owner {part_guid_ref} is not unique")
    return matches[0]


def _patch_part_children(
    main: bytes,
    *,
    part_source_ref: str,
    drawable_refs: Sequence[str],
    experiment: Any,
) -> bytes:
    block = experiment._block_by_id(main, "CPartSource", part_source_ref)
    pattern = re.compile(
        rb'(<carray_list\b(?=[^>]*\bxs\.n="_childGuids")[^>]*\bcount=")'
        rb'(\d+)("[^>]*>)(.*?)(</carray_list>)',
        re.DOTALL,
    )
    matches = list(pattern.finditer(block))
    _require(len(matches) == 1, f"Part {part_source_ref}: child list is not unique")
    match = matches[0]
    old_count = int(match.group(2))
    old_refs = re.findall(
        rb'<(?:CDrawableGuid|CDeformerGuid|CPartGuid) xs\.ref="(#[0-9]+)"\s*/>',
        match.group(4),
    )
    _require(len(old_refs) == old_count, f"Part {part_source_ref}: child count differs")
    _require(not set(ref.encode("ascii") for ref in drawable_refs).intersection(old_refs), "new Part child already exists")
    additions = b"\r\n".join(
        f'<CDrawableGuid xs.ref="{ref}" />'.encode("ascii") for ref in drawable_refs
    )
    body = match.group(4)
    if body and not body.endswith(b"\r\n"):
        body += b"\r\n"
    replacement = (
        match.group(1)
        + str(old_count + len(drawable_refs)).encode("ascii")
        + match.group(3)
        + body
        + additions
        + b"\r\n"
        + match.group(5)
    )
    patched_block = block[: match.start()] + replacement + block[match.end() :]
    return experiment._replace_exact(main, block, patched_block, 1, f"Part {part_source_ref} children")


def _roles(groups: Sequence[str]) -> list[str]:
    result: list[str] = []
    for group in groups:
        prefix = f"segment:{group}:"
        result.extend(
            [
                prefix + "source",
                prefix + "grid",
                prefix + "binding-0",
                prefix + "binding-1",
                *(prefix + f"form-guid-{index}" for index in range(9)),
                prefix + "drawable-guid",
                prefix + "texture-extension",
                prefix + "model-input",
            ]
        )
    return result


def build(source: Path, partition_map: Path, output: Path, audit_path: Path) -> dict[str, Any]:
    sys.path.insert(0, str(TOOLS_DIR))
    import cmo3_create_deformer_experiment as experiment
    import cmo3_hair_motion_professional_r13 as base
    import cmo3_reparent_preserve_canvas as canvas
    import cmo3_safe_roundtrip as safe
    import cmo3_secondary_professional as secondary

    source_data = source.read_bytes()
    source_sha = _sha256(source_data)
    map_data = json.loads(partition_map.read_text(encoding="utf-8"))
    _require(map_data.get("source_sha256") == source_sha, "partition map/source hash differs")
    archive_before, _entry, _location, _zip, main_before = safe._validate_surgical_layout(source_data)
    root_before = experiment._parse_xml(main_before)
    shared_before = root_before.find("shared")
    _require(shared_before is not None, "shared section missing")
    model_before = canvas.GeometryModel(main_before, TOLERANCE)
    objects_before = {item.name: item for item in model_before.objects}
    _require(set(map_data["meshes"]).issubset(objects_before), "partition target missing")
    _require(not set(GROUP_OBJECT_NAMES.values()).intersection(objects_before), "v005 object already exists")

    group_order = [
        group
        for original_name in map_data["meshes"]
        for group in map_data["meshes"][original_name]["spec"]["groups"]
    ]
    _require(len(group_order) == 13 and set(group_order) == set(GROUP_OBJECT_NAMES), "expected thirteen mobile groups")
    slots = secondary._allocate(root_before, _roles(group_order))
    current = main_before
    additions: list[bytes] = []
    segment_audit: dict[str, Any] = {}
    part_additions: dict[str, list[str]] = defaultdict(list)
    original_blocks = base._source_blocks(main_before, base._load_modules())

    for original_name, mapping in map_data["meshes"].items():
        original_item = objects_before[original_name]
        original_source = model_before.source(original_item)
        original_source_ref = str(original_source.get("xs.id"))
        parent_part_ref = str(
            _descendant(
                original_source,
                "CPartGuid",
                "parentGuid",
                original_name,
            ).get("xs.ref")
        )
        assignments = list(mapping["assignments"])
        expected_triangles = len(assignments)
        group_counts = Counter(assignments)
        _require(group_counts["CAP"] > 0, f"{original_name}: empty cap")
        _require(set(group_counts) == {"CAP", *mapping["spec"]["groups"]}, f"{original_name}: group set differs")

        cap = copy.deepcopy(original_source)
        cap_triangles = [index for index, group in enumerate(assignments) if group == "CAP"]
        cap_audit = _subset_source(cap, cap_triangles, f"{original_name} CAP")
        old_block = experiment._block_by_id(current, "CArtMeshSource", original_source_ref)
        current = experiment._replace_exact(
            current,
            old_block,
            _serialize(cap),
            1,
            f"{original_name} cap partition",
        )
        segment_audit[original_name] = {
            "role": "fixed_root_cap_existing_identity",
            "source_ref": original_source_ref,
            **cap_audit,
        }

        covered = set(cap_triangles)
        for group in mapping["spec"]["groups"]:
            triangles = [index for index, assigned in enumerate(assignments) if assigned == group]
            _require(not covered.intersection(triangles), f"{original_name}: triangle duplicated")
            covered.update(triangles)
            object_name = GROUP_OBJECT_NAMES[group]
            blocks, audit = _clone_segment(
                original_source=original_source,
                root=root_before,
                source_sha=source_sha,
                group=group,
                object_name=object_name,
                triangle_indices=triangles,
                slots=slots,
            )
            additions.extend(blocks)
            segment_audit[object_name] = audit
            part_additions[parent_part_ref].append(audit["drawable_guid_ref"])
        _require(covered == set(range(expected_triangles)), f"{original_name}: partition is not exhaustive")

    current = experiment._append_shared_blocks(current, additions)
    new_source_refs = [segment_audit[GROUP_OBJECT_NAMES[group]]["source_ref"] for group in group_order]
    current = _patch_drawable_source_set(current, new_source_refs)
    for part_guid_ref, drawable_refs in part_additions.items():
        current = _patch_part_children(
            current,
            part_source_ref=_part_source_ref(root_before, part_guid_ref),
            drawable_refs=drawable_refs,
            experiment=experiment,
        )

    root_after = experiment._parse_xml(current)
    shared_after = root_after.find("shared")
    _require(shared_after is not None, "output shared section missing")
    ids_after = [int(node.get("xs.id", "#-1")[1:]) for node in shared_after]
    idx_after = [int(node.get("xs.idx", "-1")) for node in shared_after]
    _require(sorted(ids_after) == list(range(max(ids_after) + 1)), "output xs.id range differs")
    _require(len(idx_after) == len(set(idx_after)), "output xs.idx collision")
    model_after = canvas.GeometryModel(current, TOLERANCE)
    objects_after = {item.name: item for item in model_after.objects}
    _require(set(GROUP_OBJECT_NAMES.values()).issubset(objects_after), "mobile object missing after build")
    _require(len(model_after.objects) == len(model_before.objects) + 13, "object count increase differs")
    _require(len([item for item in model_after.objects if item.object_type == "art-mesh"]) == 71, "ArtMesh count differs")

    after_blocks = base._source_blocks(current, base._load_modules())
    protected = set(original_blocks) - set(map_data["meshes"])
    _require(all(after_blocks[name] == original_blocks[name] for name in protected), "non-target source changed")
    output_data = safe._replace_main_xml(source_data, current)
    archive_after, _e2, _l2, _z2, decoded_after = safe._validate_surgical_layout(output_data)
    _require(decoded_after == current, "encoded main.xml differs from plan")
    preservation = safe._compare_entry_preservation(
        source_data,
        archive_before,
        output_data,
        archive_after,
        main_may_change=True,
    )
    _require(preservation.get("all_non_main_entries_byte_identical") is True, "embedded art changed")

    audit = {
        "schema": "jade.cubism.hair-art-partition-r16.v1",
        "status": "candidate",
        "source": str(source),
        "source_sha256": source_sha,
        "partition_map": str(partition_map),
        "partition_map_sha256": _sha256(partition_map.read_bytes()),
        "output": str(output),
        "output_sha256": _sha256(output_data),
        "policy": {
            "art_derivation": "v005 structural triangle partition; original v004 pixels reused",
            "neutral_composite": "every original rear triangle retained exactly once",
            "existing_source_identity": "five historical rear objects retained as fixed caps",
            "new_mobile_objects": 13,
            "eyes_ears_front_hair_other_art": "byte-exact source blocks",
            "source_r15_never_overwritten": True,
        },
        "counts": {
            "objects_before": len(model_before.objects),
            "objects_after": len(model_after.objects),
            "art_meshes_before": 58,
            "art_meshes_after": 71,
            "shared_blocks_added": len(additions),
        },
        "segments": segment_audit,
        "all_non_target_sources_preserved_byte_exact": True,
        "all_non_main_archive_entries_preserved_byte_exact": True,
        "archive": preservation,
        "cubism_5_2_03_load_save_required": True,
    }
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    descriptor = os.open(output, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(output_data)
            handle.flush()
            os.fsync(handle.fileno())
        descriptor = os.open(audit_path, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", closefd=True) as handle:
            json.dump(audit, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except Exception:
        output.unlink(missing_ok=True)
        audit_path.unlink(missing_ok=True)
        raise
    return audit


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("partition_map", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("audit", type=Path)
    args = parser.parse_args(list(argv) if argv is not None else None)
    source = args.source.resolve(strict=True)
    partition_map = args.partition_map.resolve(strict=True)
    output = args.output.resolve(strict=False)
    audit = args.audit.resolve(strict=False)
    _require(source != output, "source/output must differ")
    _require(not output.exists() and not audit.exists(), "output/audit exists")
    _require(output.parent.is_dir() and audit.parent.is_dir(), "output parent missing")
    result = build(source, partition_map, output, audit)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HairArtPartitionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
