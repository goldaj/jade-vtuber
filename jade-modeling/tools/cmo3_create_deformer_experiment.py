#!/usr/bin/env python3
"""
Create one isolated TEST-only root warp in the known Jade Cubism 5.2 CMO3.

This is deliberately a narrow experiment, not a general CMO3 editor. It:

* accepts only the byte-identical Jade v003 checkpoint pinned below;
* clones the neutral ``Lower Body Warp`` serialization;
* derives new ``xs.idx`` offsets from the existing neutral
  ``Upper Body Warp Y`` object produced by Cubism 5.2;
* creates a new 5x5 neutral ``D_JAD_ROOT`` warp with independent IDs, GUIDs,
  form data, positions, and extension GUIDs;
* reparents only ``Upper Body Warp Z`` and ``Lower Body Warp``;
* registers the new deformer in its owning Part's ``_childGuids`` list;
* transforms those two child grids from canvas coordinates into the new
  parent's normalized coordinates so the neutral pose remains algebraically
  unchanged;
* writes only new files whose names contain TEST, directly below ``reports``.

The source checkpoint is never overwritten. The CAFF writer is imported from
``cmo3_safe_roundtrip.py`` so this experiment shares its strict last-member,
DEFLATE, metadata, and copy-on-write checks without modifying that module.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import struct
import sys
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from cmo3_inventory import CaffArchive, InventoryError, inventory_file
from cmo3_safe_roundtrip import (
    SafeWriteError,
    _replace_main_xml,
    _validate_surgical_layout,
)


MAX_XML_BYTES = 256 * 1024 * 1024
EXPECTED_SOURCE_SHA256 = (
    "D6058A8458B34F67C51C7ACC9A0CCC8FD460C13B986187DFEA23794BC5AA4B90"
)
ROOT_NAME = "D_JAD_ROOT"
ROOT_DEFORMER_ID = "Warp21"
CLONE_SOURCE_NAME = "Lower Body Warp"
INDEX_EXEMPLAR_NAME = "Upper Body Warp Y"
ROOT_CHILD_NAMES = ("Upper Body Warp Z", "Lower Body Warp")
INNER_MARGIN = 0.03
PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = (PROJECT_ROOT / "reports").resolve()


class ExperimentError(RuntimeError):
    """Raised when an unproven CMO3 mutation would otherwise be attempted."""


@dataclass(frozen=True)
class WarpInfo:
    name: str
    source: ET.Element
    source_ref: str
    source_idx: int
    deformer_id: str
    guid_ref: str
    guid_uuid: str
    guid_idx: int
    parent_ref: str
    parent_part_ref: str
    form_ref: str
    form_uuid: str
    form_idx: int
    positions_ref: str
    positions_idx: int
    col: int
    row: int
    original_positions: tuple[float, ...]
    positions: tuple[float, ...]
    extension_uuids: tuple[str, ...]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _float32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def _format_float32(value: float) -> str:
    value = _float32(value)
    if not math.isfinite(value):
        raise ExperimentError("non-finite float generated")
    if value == 0.0:
        return "0.0"
    text = format(value, ".9g")
    if "e" not in text.casefold() and "." not in text:
        text += ".0"
    return text


def _float32_sequences_equal(
    left: Sequence[float],
    right: Sequence[float],
) -> bool:
    return len(left) == len(right) and all(
        _float32(a) == _float32(b)
        for a, b in zip(left, right)
    )


def _parse_xml(xml_bytes: bytes) -> ET.Element:
    if b"<!DOCTYPE" in xml_bytes[:65536] or b"<!ENTITY" in xml_bytes[:65536]:
        raise ExperimentError("DTD/entity declarations are not accepted")
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ExperimentError(f"invalid main.xml: {exc}") from exc
    if root.find("shared") is None or root.find("main/CModelSource") is None:
        raise ExperimentError("main.xml lacks shared/main/CModelSource")
    return root


def _id_map(root: ET.Element) -> dict[str, ET.Element]:
    result: dict[str, ET.Element] = {}
    for node in root.iter():
        serialized_id = node.get("xs.id")
        if serialized_id is None:
            continue
        if serialized_id in result:
            raise ExperimentError(f"duplicate xs.id {serialized_id!r}")
        result[serialized_id] = node
    return result


def _one_named(
    source: ET.Element,
    tag: str,
    serialized_name: str,
) -> ET.Element:
    matches = [
        node
        for node in source.iter(tag)
        if node.get("xs.n") == serialized_name
    ]
    if len(matches) != 1:
        raise ExperimentError(
            f"{source.tag} {source.get('xs.id')!r}: expected one "
            f"{tag}[xs.n={serialized_name!r}], found {len(matches)}"
        )
    return matches[0]


def _direct_named(
    source: ET.Element,
    tag: str,
    serialized_name: str,
) -> ET.Element:
    matches = [
        node
        for node in source
        if node.tag == tag and node.get("xs.n") == serialized_name
    ]
    if len(matches) != 1:
        raise ExperimentError(
            f"{source.tag} {source.get('xs.id')!r}: expected one direct "
            f"{tag}[xs.n={serialized_name!r}], found {len(matches)}"
        )
    return matches[0]


def _canonical_uuid(value: str | None, label: str) -> str:
    try:
        return str(uuid.UUID(value or ""))
    except ValueError as exc:
        raise ExperimentError(f"{label} is not a canonical UUID: {value!r}") from exc


def _parse_positions(node: ET.Element, label: str) -> tuple[float, ...]:
    raw = (node.text or "").split()
    try:
        values = tuple(float(value) for value in raw)
    except ValueError as exc:
        raise ExperimentError(f"{label} contains an invalid float") from exc
    count_raw = node.get("count")
    if count_raw is None or not count_raw.isdigit():
        raise ExperimentError(f"{label} lacks a numeric count")
    if int(count_raw) != len(values):
        raise ExperimentError(
            f"{label} count={count_raw} but contains {len(values)} values"
        )
    if len(values) % 2:
        raise ExperimentError(f"{label} has an odd number of coordinates")
    if not all(math.isfinite(value) for value in values):
        raise ExperimentError(f"{label} contains a non-finite coordinate")
    return values


def _warp_info(
    root: ET.Element,
    name: str,
) -> WarpInfo:
    shared = root.find("shared")
    assert shared is not None
    ids = _id_map(root)
    matches = []
    for source in shared.findall("CWarpDeformerSource"):
        local_name = _one_named(source, "s", "localName").text or ""
        if local_name == name:
            matches.append(source)
    if len(matches) != 1:
        raise ExperimentError(
            f"expected one warp named {name!r}, found {len(matches)}"
        )
    source = matches[0]
    source_ref = source.get("xs.id")
    source_idx_raw = source.get("xs.idx")
    if not source_ref or not source_idx_raw or not source_idx_raw.isdigit():
        raise ExperimentError(f"warp {name!r} lacks source ID/index")

    guid_ref = _one_named(source, "CDeformerGuid", "guid").get("xs.ref")
    parent_ref = _one_named(
        source,
        "CDeformerGuid",
        "targetDeformerGuid",
    ).get("xs.ref")
    parent_part_ref = _one_named(
        source,
        "CPartGuid",
        "parentGuid",
    ).get("xs.ref")
    if not guid_ref or not parent_ref or not parent_part_ref:
        raise ExperimentError(
            f"warp {name!r} lacks GUID, deformer parent, or Part parent"
        )
    guid = ids.get(guid_ref)
    if guid is None or guid.tag != "CDeformerGuid":
        raise ExperimentError(f"warp {name!r} GUID {guid_ref!r} is unresolved")
    guid_idx_raw = guid.get("xs.idx")
    if not guid_idx_raw or not guid_idx_raw.isdigit():
        raise ExperimentError(f"warp {name!r} GUID lacks xs.idx")

    deformer_id_node = _one_named(source, "CDeformerId", "id")
    deformer_id = deformer_id_node.get("idstr") or ""
    if not deformer_id:
        raise ExperimentError(f"warp {name!r} lacks CDeformerId")

    grid = _one_named(source, "KeyformGridSource", "keyformGridSource")
    on_grid = _direct_named(grid, "array_list", "keyformsOnGrid")
    bindings = _direct_named(grid, "array_list", "keyformBindings")
    if on_grid.get("count") != "1" or len(on_grid) != 1:
        raise ExperimentError(f"warp {name!r} is not a one-keyform neutral warp")
    if bindings.get("count") != "0" or len(bindings) != 0:
        raise ExperimentError(f"warp {name!r} has parameter bindings")
    form_ref = _one_named(on_grid[0], "CFormGuid", "keyformGuid").get("xs.ref")
    if not form_ref:
        raise ExperimentError(f"warp {name!r} keyform GUID is missing")
    form = ids.get(form_ref)
    if form is None or form.tag != "CFormGuid":
        raise ExperimentError(f"warp {name!r} form {form_ref!r} is unresolved")
    form_idx_raw = form.get("xs.idx")
    if not form_idx_raw or not form_idx_raw.isdigit():
        raise ExperimentError(f"warp {name!r} form lacks xs.idx")

    extension_list = _one_named(source, "carray_list", "_extensions")
    if extension_list.get("count") != "3" or len(extension_list) != 3:
        raise ExperimentError(f"warp {name!r} does not have three extensions")
    extension_uuids = tuple(
        _canonical_uuid(
            _one_named(extension, "CExtensionGuid", "guid").get("uuid"),
            f"{name} extension GUID",
        )
        for extension in extension_list
    )

    original_shape = _one_named(
        extension_list[2],
        "WarpDeformerOriginalShape",
        "originalShape",
    )
    original_position_refs = [
        node.get("xs.ref")
        for node in original_shape.iter("float-array")
        if node.get("xs.n") == "positions"
    ]
    if (
        len(original_position_refs) != 2
        or len(set(original_position_refs)) != 1
        or not original_position_refs[0]
    ):
        raise ExperimentError(
            f"warp {name!r} original shape does not use one positions object"
        )
    positions_ref = original_position_refs[0]
    positions_definition = ids.get(positions_ref)
    if positions_definition is None or positions_definition.tag != "float-array":
        raise ExperimentError(
            f"warp {name!r} positions {positions_ref!r} are unresolved"
        )
    positions_idx_raw = positions_definition.get("xs.idx")
    if not positions_idx_raw or not positions_idx_raw.isdigit():
        raise ExperimentError(f"warp {name!r} positions lack xs.idx")
    original_positions = _parse_positions(
        positions_definition,
        f"{name} original positions",
    )

    col = int(_direct_named(source, "i", "col").text or "-1")
    row = int(_direct_named(source, "i", "row").text or "-1")
    keyforms = _direct_named(source, "carray_list", "keyforms")
    if keyforms.get("count") != "1" or len(keyforms) != 1:
        raise ExperimentError(f"warp {name!r} is not a neutral one-form warp")
    inline_positions_nodes = [
        node
        for node in keyforms[0]
        if node.tag == "float-array" and node.get("xs.n") == "positions"
    ]
    if len(inline_positions_nodes) != 1:
        raise ExperimentError(f"warp {name!r} lacks one inline positions array")
    inline_positions = _parse_positions(
        inline_positions_nodes[0],
        f"{name} inline positions",
    )
    expected_values = 2 * (col + 1) * (row + 1)
    if len(original_positions) != expected_values:
        raise ExperimentError(
            f"warp {name!r} dimensions {col}x{row} require "
            f"{expected_values} values, found {len(original_positions)}"
        )
    return WarpInfo(
        name=name,
        source=source,
        source_ref=source_ref,
        source_idx=int(source_idx_raw),
        deformer_id=deformer_id,
        guid_ref=guid_ref,
        guid_uuid=_canonical_uuid(guid.get("uuid"), f"{name} deformer GUID"),
        guid_idx=int(guid_idx_raw),
        parent_ref=parent_ref,
        parent_part_ref=parent_part_ref,
        form_ref=form_ref,
        form_uuid=_canonical_uuid(form.get("uuid"), f"{name} form GUID"),
        form_idx=int(form_idx_raw),
        positions_ref=positions_ref,
        positions_idx=int(positions_idx_raw),
        col=col,
        row=row,
        original_positions=original_positions,
        positions=inline_positions,
        extension_uuids=extension_uuids,
    )


def _block_by_id(xml_bytes: bytes, tag: str, serialized_id: str) -> bytes:
    tag_bytes = re.escape(tag.encode("ascii"))
    id_bytes = re.escape(serialized_id.encode("ascii"))
    opening = re.compile(
        rb"<"
        + tag_bytes
        + rb'\b(?=[^>]*\bxs\.id="'
        + id_bytes
        + rb'")[^>]*>'
    )
    matches = list(opening.finditer(xml_bytes))
    if len(matches) != 1:
        raise ExperimentError(
            f"expected one serialized {tag} block {serialized_id}, "
            f"found {len(matches)}"
        )
    start = matches[0].start()
    opening_bytes = matches[0].group(0)
    if opening_bytes.endswith(b"/>"):
        return opening_bytes
    closing = b"</" + tag.encode("ascii") + b">"
    end_start = xml_bytes.find(closing, matches[0].end())
    if end_start < 0:
        raise ExperimentError(f"serialized {tag} block is not closed")
    return xml_bytes[start : end_start + len(closing)]


def _replace_exact(
    data: bytes,
    old: bytes,
    new: bytes,
    expected_count: int,
    label: str,
) -> bytes:
    observed = data.count(old)
    if observed != expected_count:
        raise ExperimentError(
            f"{label}: expected {expected_count} exact token(s), found {observed}"
        )
    return data.replace(old, new)


def _replace_float_payload(
    block: bytes,
    values: Sequence[float],
    label: str,
) -> bytes:
    matches = list(
        re.finditer(
            rb'(<float-array\b(?=[^>]*\bcount="\d+")[^>]*>)([^<]*)(</float-array>)',
            block,
        )
    )
    if len(matches) != 1:
        raise ExperimentError(
            f"{label}: expected one inline float-array payload, found {len(matches)}"
        )
    match = matches[0]
    count_match = re.search(rb'\bcount="(\d+)"', match.group(1))
    assert count_match is not None
    if int(count_match.group(1)) != len(values):
        raise ExperimentError(
            f"{label}: serialized count differs from replacement length"
        )
    payload = " ".join(_format_float32(value) for value in values).encode("ascii")
    return block[: match.start(2)] + payload + block[match.end(2) :]


def _new_uuid(source_sha: str, role: str) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"jade-cmo3-root-test:{source_sha}:{ROOT_NAME}:{role}",
        )
    )


def _grid_bounds(positions: Sequence[float]) -> tuple[float, float, float, float]:
    xs = positions[0::2]
    ys = positions[1::2]
    return min(xs), max(xs), min(ys), max(ys)


def _root_geometry(
    child_positions: Sequence[Sequence[float]],
    col: int,
    row: int,
) -> tuple[tuple[float, ...], tuple[float, float, float, float]]:
    if not 0.0 < INNER_MARGIN < 0.5:
        raise ExperimentError("invalid inner margin")
    all_x = [
        value
        for positions in child_positions
        for value in positions[0::2]
    ]
    all_y = [
        value
        for positions in child_positions
        for value in positions[1::2]
    ]
    content_min_x, content_max_x = min(all_x), max(all_x)
    content_min_y, content_max_y = min(all_y), max(all_y)
    content_width = content_max_x - content_min_x
    content_height = content_max_y - content_min_y
    if content_width <= 0.0 or content_height <= 0.0:
        raise ExperimentError("root children have degenerate bounds")
    scale = 1.0 - 2.0 * INNER_MARGIN
    root_width = content_width / scale
    root_height = content_height / scale
    root_min_x = content_min_x - INNER_MARGIN * root_width
    root_min_y = content_min_y - INNER_MARGIN * root_height
    root_max_x = root_min_x + root_width
    root_max_y = root_min_y + root_height

    values: list[float] = []
    for y_index in range(row + 1):
        y = root_min_y + root_height * y_index / row
        for x_index in range(col + 1):
            x = root_min_x + root_width * x_index / col
            values.extend((_float32(x), _float32(y)))
    return (
        tuple(values),
        (
            _float32(root_min_x),
            _float32(root_max_x),
            _float32(root_min_y),
            _float32(root_max_y),
        ),
    )


def _to_parent_local(
    positions: Sequence[float],
    root_bounds: tuple[float, float, float, float],
) -> tuple[float, ...]:
    min_x, max_x, min_y, max_y = root_bounds
    width = max_x - min_x
    height = max_y - min_y
    if width <= 0.0 or height <= 0.0:
        raise ExperimentError("new root has degenerate bounds")
    result: list[float] = []
    for x, y in zip(positions[0::2], positions[1::2]):
        result.extend(
            (
                _float32((x - min_x) / width),
                _float32((y - min_y) / height),
            )
        )
    return tuple(result)


def _max_reconstruction_error(
    original: Sequence[float],
    local: Sequence[float],
    root_bounds: tuple[float, float, float, float],
) -> float:
    min_x, max_x, min_y, max_y = root_bounds
    width = max_x - min_x
    height = max_y - min_y
    maximum = 0.0
    for old_x, old_y, local_x, local_y in zip(
        original[0::2],
        original[1::2],
        local[0::2],
        local[1::2],
    ):
        maximum = max(
            maximum,
            abs((min_x + local_x * width) - old_x),
            abs((min_y + local_y * height) - old_y),
        )
    return maximum


def _clone_root_blocks(
    xml_bytes: bytes,
    clone: WarpInfo,
    exemplar: WarpInfo,
    source_sha: str,
    root_positions: Sequence[float],
) -> tuple[list[bytes], dict[str, Any]]:
    root = _parse_xml(xml_bytes)
    shared = root.find("shared")
    assert shared is not None
    ids = _id_map(root)
    numeric_ids = []
    for serialized_id in ids:
        if not re.fullmatch(r"#\d+", serialized_id):
            raise ExperimentError(f"unsupported nonnumeric xs.id {serialized_id!r}")
        numeric_ids.append(int(serialized_id[1:]))
    maximum_id = max(numeric_ids)
    if set(numeric_ids) != set(range(maximum_id + 1)):
        raise ExperimentError("existing xs.id values are not contiguous from #0")
    new_source_ref = f"#{maximum_id + 1}"
    new_positions_ref = f"#{maximum_id + 2}"
    new_form_ref = f"#{maximum_id + 3}"
    new_guid_ref = f"#{maximum_id + 4}"

    existing_indices = []
    for child in shared:
        raw_idx = child.get("xs.idx")
        if raw_idx is None or not raw_idx.isdigit():
            raise ExperimentError(
                f"shared child {child.tag} {child.get('xs.id')!r} lacks xs.idx"
            )
        existing_indices.append(int(raw_idx))
    if len(existing_indices) != len(set(existing_indices)):
        raise ExperimentError("existing shared xs.idx values are not unique")
    base_idx = max(existing_indices) + 1

    form_delta = exemplar.form_idx - exemplar.source_idx
    positions_delta = exemplar.positions_idx - exemplar.source_idx
    guid_delta = exemplar.guid_idx - exemplar.source_idx
    if (form_delta, positions_delta, guid_delta) != (6, 20, 22):
        raise ExperimentError(
            "Cubism 5.2 neutral-warp exemplar index pattern changed: "
            f"{(form_delta, positions_delta, guid_delta)!r}"
        )
    new_source_idx = base_idx
    new_form_idx = base_idx + form_delta
    new_positions_idx = base_idx + positions_delta
    new_guid_idx = base_idx + guid_delta
    generated_indices = {
        new_source_idx,
        new_form_idx,
        new_positions_idx,
        new_guid_idx,
    }
    if len(generated_indices) != 4 or generated_indices.intersection(
        existing_indices
    ):
        raise ExperimentError("generated xs.idx values are not unique")

    generated_uuids = {
        "form": _new_uuid(source_sha, "form"),
        "deformer": _new_uuid(source_sha, "deformer"),
        "bezier_edit_2": _new_uuid(source_sha, "extension-bezier-edit-2"),
        "bezier_edit_3": _new_uuid(source_sha, "extension-bezier-edit-3"),
        "original_shape": _new_uuid(source_sha, "extension-original-shape"),
    }
    existing_uuids = {
        _canonical_uuid(node.get("uuid"), f"existing {node.tag} UUID")
        for node in root.iter()
        if node.get("uuid") is not None
    }
    if set(generated_uuids.values()).intersection(existing_uuids):
        raise ExperimentError("a generated UUID collides with the source model")
    if len(set(generated_uuids.values())) != len(generated_uuids):
        raise ExperimentError("generated UUIDs are not unique")

    source_block = _block_by_id(
        xml_bytes,
        "CWarpDeformerSource",
        clone.source_ref,
    )
    positions_block = _block_by_id(
        xml_bytes,
        "float-array",
        clone.positions_ref,
    )
    form_block = _block_by_id(xml_bytes, "CFormGuid", clone.form_ref)
    guid_block = _block_by_id(xml_bytes, "CDeformerGuid", clone.guid_ref)

    source_block = _replace_exact(
        source_block,
        f'xs.id="{clone.source_ref}"'.encode("ascii"),
        f'xs.id="{new_source_ref}"'.encode("ascii"),
        1,
        "clone source xs.id",
    )
    source_block = _replace_exact(
        source_block,
        f'xs.idx="{clone.source_idx}"'.encode("ascii"),
        f'xs.idx="{new_source_idx}"'.encode("ascii"),
        1,
        "clone source xs.idx",
    )
    source_block = _replace_exact(
        source_block,
        f">{clone.name}</s>".encode("utf-8"),
        f">{ROOT_NAME}</s>".encode("utf-8"),
        1,
        "clone localName",
    )
    source_block = _replace_exact(
        source_block,
        f'xs.ref="{clone.source_ref}"'.encode("ascii"),
        f'xs.ref="{new_source_ref}"'.encode("ascii"),
        4,
        "clone owner/source references",
    )
    source_block = _replace_exact(
        source_block,
        f'xs.ref="{clone.positions_ref}"'.encode("ascii"),
        f'xs.ref="{new_positions_ref}"'.encode("ascii"),
        2,
        "clone original-shape positions references",
    )
    source_block = _replace_exact(
        source_block,
        f'xs.ref="{clone.form_ref}"'.encode("ascii"),
        f'xs.ref="{new_form_ref}"'.encode("ascii"),
        2,
        "clone form references",
    )
    source_block = _replace_exact(
        source_block,
        f'xs.ref="{clone.guid_ref}"'.encode("ascii"),
        f'xs.ref="{new_guid_ref}"'.encode("ascii"),
        1,
        "clone deformer GUID reference",
    )
    source_block = _replace_exact(
        source_block,
        f'idstr="{clone.deformer_id}"'.encode("utf-8"),
        f'idstr="{ROOT_DEFORMER_ID}"'.encode("utf-8"),
        1,
        "clone CDeformerId",
    )
    extension_roles = (
        "bezier_edit_2",
        "bezier_edit_3",
        "original_shape",
    )
    for old_uuid, role in zip(clone.extension_uuids, extension_roles):
        source_block = _replace_exact(
            source_block,
            f'uuid="{old_uuid}"'.encode("ascii"),
            f'uuid="{generated_uuids[role]}"'.encode("ascii"),
            1,
            f"clone extension UUID {role}",
        )
    source_block = _replace_float_payload(
        source_block,
        root_positions,
        "new root inline positions",
    )

    positions_block = _replace_exact(
        positions_block,
        f'xs.id="{clone.positions_ref}"'.encode("ascii"),
        f'xs.id="{new_positions_ref}"'.encode("ascii"),
        1,
        "clone positions xs.id",
    )
    positions_block = _replace_exact(
        positions_block,
        f'xs.idx="{clone.positions_idx}"'.encode("ascii"),
        f'xs.idx="{new_positions_idx}"'.encode("ascii"),
        1,
        "clone positions xs.idx",
    )
    positions_block = _replace_float_payload(
        positions_block,
        root_positions,
        "new root shared positions",
    )

    form_block = _replace_exact(
        form_block,
        f'xs.id="{clone.form_ref}"'.encode("ascii"),
        f'xs.id="{new_form_ref}"'.encode("ascii"),
        1,
        "clone form xs.id",
    )
    form_block = _replace_exact(
        form_block,
        f'xs.idx="{clone.form_idx}"'.encode("ascii"),
        f'xs.idx="{new_form_idx}"'.encode("ascii"),
        1,
        "clone form xs.idx",
    )
    form_block = _replace_exact(
        form_block,
        f'uuid="{clone.form_uuid}"'.encode("ascii"),
        f'uuid="{generated_uuids["form"]}"'.encode("ascii"),
        1,
        "clone form UUID",
    )

    guid_block = _replace_exact(
        guid_block,
        f'xs.id="{clone.guid_ref}"'.encode("ascii"),
        f'xs.id="{new_guid_ref}"'.encode("ascii"),
        1,
        "clone deformer GUID xs.id",
    )
    guid_block = _replace_exact(
        guid_block,
        f'xs.idx="{clone.guid_idx}"'.encode("ascii"),
        f'xs.idx="{new_guid_idx}"'.encode("ascii"),
        1,
        "clone deformer GUID xs.idx",
    )
    guid_block = _replace_exact(
        guid_block,
        f'uuid="{clone.guid_uuid}"'.encode("ascii"),
        f'uuid="{generated_uuids["deformer"]}"'.encode("ascii"),
        1,
        "clone deformer GUID UUID",
    )
    note_pattern = re.compile(rb'\bnote="[^"]*"')
    note_matches = list(note_pattern.finditer(guid_block))
    if len(note_matches) != 1:
        raise ExperimentError("clone deformer GUID does not have one note")
    guid_block = (
        guid_block[: note_matches[0].start()]
        + f'note="{ROOT_DEFORMER_ID}"'.encode("ascii")
        + guid_block[note_matches[0].end() :]
    )

    return (
        [source_block, positions_block, form_block, guid_block],
        {
            "source_ref": new_source_ref,
            "positions_ref": new_positions_ref,
            "form_ref": new_form_ref,
            "guid_ref": new_guid_ref,
            "parent_part_ref": clone.parent_part_ref,
            "source_idx": new_source_idx,
            "positions_idx": new_positions_idx,
            "form_idx": new_form_idx,
            "guid_idx": new_guid_idx,
            "uuids": generated_uuids,
            "index_exemplar": {
                "name": exemplar.name,
                "relative_offsets": {
                    "source": 0,
                    "form": form_delta,
                    "positions": positions_delta,
                    "deformer_guid": guid_delta,
                },
            },
        },
    )


def _patch_existing_child(
    xml_bytes: bytes,
    child: WarpInfo,
    new_parent_ref: str,
    local_positions: Sequence[float],
) -> bytes:
    source_block = _block_by_id(
        xml_bytes,
        "CWarpDeformerSource",
        child.source_ref,
    )
    patched_source = _replace_exact(
        source_block,
        (
            f'<CDeformerGuid xs.n="targetDeformerGuid" '
            f'xs.ref="{child.parent_ref}" />'
        ).encode("ascii"),
        (
            f'<CDeformerGuid xs.n="targetDeformerGuid" '
            f'xs.ref="{new_parent_ref}" />'
        ).encode("ascii"),
        1,
        f"{child.name} parent",
    )
    patched_source = _replace_float_payload(
        patched_source,
        local_positions,
        f"{child.name} inline positions",
    )
    xml_bytes = _replace_exact(
        xml_bytes,
        source_block,
        patched_source,
        1,
        f"{child.name} source block",
    )
    return xml_bytes


def _append_shared_blocks(xml_bytes: bytes, blocks: Sequence[bytes]) -> bytes:
    closing = b"</shared>"
    if xml_bytes.count(closing) != 1:
        raise ExperimentError("main.xml does not have one shared closing tag")
    insertion = b"\r\n".join(blocks) + b"\r\n"
    offset = xml_bytes.index(closing)
    return xml_bytes[:offset] + insertion + xml_bytes[offset:]


def _patch_deformer_source_set(
    xml_bytes: bytes,
    new_source_ref: str,
) -> bytes:
    opening = re.compile(
        rb'<CDeformerSourceSet\b(?=[^>]*\bxs\.n="deformerSourceSet")[^>]*>'
    )
    matches = list(opening.finditer(xml_bytes))
    if len(matches) != 1:
        raise ExperimentError(
            f"expected one CDeformerSourceSet, found {len(matches)}"
        )
    closing = b"</CDeformerSourceSet>"
    closing_offset = xml_bytes.find(closing, matches[0].end())
    if closing_offset < 0:
        raise ExperimentError("CDeformerSourceSet is not closed")
    end = closing_offset + len(closing)
    block = xml_bytes[matches[0].start() : end]
    list_opening = re.compile(
        rb'(<carray_list\b(?=[^>]*\bxs\.n="_sources")'
        rb'[^>]*\bcount=")(\d+)("[^>]*>\r\n)'
    )
    list_matches = list(list_opening.finditer(block))
    if len(list_matches) != 1:
        raise ExperimentError("deformer source list opening is not unique")
    list_match = list_matches[0]
    old_count = int(list_match.group(2))
    refs = re.findall(
        rb'<(?:CWarpDeformerSource|CRotationDeformerSource) xs\.ref="(#[0-9]+)" />',
        block,
    )
    if len(refs) != old_count:
        raise ExperimentError(
            f"deformer source set count={old_count}, refs={len(refs)}"
        )
    if new_source_ref.encode("ascii") in refs:
        raise ExperimentError("new root is already in CDeformerSourceSet")
    patched_opening = (
        list_match.group(1)
        + str(old_count + 1).encode("ascii")
        + list_match.group(3)
        + f'<CWarpDeformerSource xs.ref="{new_source_ref}" />\r\n'.encode("ascii")
    )
    patched_block = (
        block[: list_match.start()]
        + patched_opening
        + block[list_match.end() :]
    )
    return _replace_exact(
        xml_bytes,
        block,
        patched_block,
        1,
        "CDeformerSourceSet block",
    )


def _patch_part_hierarchy(
    xml_bytes: bytes,
    owner_part_guid_ref: str,
    new_deformer_guid_ref: str,
) -> bytes:
    root = _parse_xml(xml_bytes)
    shared = root.find("shared")
    assert shared is not None
    owners = [
        source
        for source in shared.findall("CPartSource")
        if _one_named(source, "CPartGuid", "guid").get("xs.ref")
        == owner_part_guid_ref
    ]
    if len(owners) != 1:
        raise ExperimentError(
            f"expected one owning Part {owner_part_guid_ref}, found {len(owners)}"
        )
    owner = owners[0]
    owner_source_ref = owner.get("xs.id")
    if not owner_source_ref:
        raise ExperimentError("owning Part source lacks xs.id")
    block = _block_by_id(xml_bytes, "CPartSource", owner_source_ref)
    list_opening = re.compile(
        rb'(<carray_list\b(?=[^>]*\bxs\.n="_childGuids")'
        rb'[^>]*\bcount=")(\d+)("[^>]*>\r\n)'
    )
    matches = list(list_opening.finditer(block))
    if len(matches) != 1:
        raise ExperimentError("owning Part _childGuids opening is not unique")
    match = matches[0]
    closing = b"</carray_list>"
    closing_offset = block.find(closing, match.end())
    if closing_offset < 0:
        raise ExperimentError("owning Part _childGuids list is not closed")
    child_region = block[match.end() : closing_offset]
    refs = re.findall(
        rb'<(?:CDrawableGuid|CDeformerGuid|CPartGuid) xs\.ref="(#[0-9]+)" />',
        child_region,
    )
    old_count = int(match.group(2))
    if len(refs) != old_count:
        raise ExperimentError(
            f"owning Part child count={old_count}, refs={len(refs)}"
        )
    new_ref_bytes = new_deformer_guid_ref.encode("ascii")
    if new_ref_bytes in refs:
        raise ExperimentError("new root is already in the Part hierarchy")
    patched_opening = (
        match.group(1)
        + str(old_count + 1).encode("ascii")
        + match.group(3)
        + (
            f'<CDeformerGuid xs.ref="{new_deformer_guid_ref}" />\r\n'
        ).encode("ascii")
    )
    patched_block = (
        block[: match.start()]
        + patched_opening
        + block[match.end() :]
    )
    return _replace_exact(
        xml_bytes,
        block,
        patched_block,
        1,
        "owning Part hierarchy block",
    )


def _deformer_graph(root: ET.Element) -> dict[str, dict[str, str]]:
    shared = root.find("shared")
    assert shared is not None
    ids = _id_map(root)
    result: dict[str, dict[str, str]] = {}
    for tag in ("CWarpDeformerSource", "CRotationDeformerSource"):
        for source in shared.findall(tag):
            name = _one_named(source, "s", "localName").text or ""
            guid_ref = _one_named(source, "CDeformerGuid", "guid").get("xs.ref")
            parent_ref = _one_named(
                source,
                "CDeformerGuid",
                "targetDeformerGuid",
            ).get("xs.ref")
            if not guid_ref or not parent_ref:
                raise ExperimentError(f"deformer {name!r} has unresolved identity")
            guid = ids.get(guid_ref)
            if guid is None:
                raise ExperimentError(f"deformer {name!r} GUID is unresolved")
            if guid_ref in result:
                raise ExperimentError(f"deformer GUID {guid_ref!r} is reused")
            result[guid_ref] = {
                "name": name,
                "kind": tag,
                "parent_ref": parent_ref,
                "uuid": _canonical_uuid(
                    guid.get("uuid"),
                    f"{name} deformer graph GUID",
                ),
            }
    return result


def _assert_deformer_id_plan(root: ET.Element) -> dict[str, Any]:
    shared = root.find("shared")
    assert shared is not None
    existing_ids: list[str] = []
    warp_numbers: list[int] = []
    for tag in ("CWarpDeformerSource", "CRotationDeformerSource"):
        for source in shared.findall(tag):
            deformer_id = _one_named(source, "CDeformerId", "id").get("idstr")
            if not deformer_id:
                raise ExperimentError("an existing deformer lacks an internal ID")
            existing_ids.append(deformer_id)
            if tag == "CWarpDeformerSource":
                match = re.fullmatch(r"Warp(\d*)", deformer_id)
                if match is None:
                    raise ExperimentError(
                        f"unsupported existing warp ID pattern: {deformer_id!r}"
                    )
                warp_numbers.append(int(match.group(1) or "1"))
    if len(existing_ids) != len(set(existing_ids)):
        raise ExperimentError("existing deformer IDs are not unique")
    if not warp_numbers:
        raise ExperimentError("source model has no attested warp ID sequence")
    planned_number = max(warp_numbers) + 1
    planned_id = f"Warp{planned_number}"
    if planned_id != ROOT_DEFORMER_ID:
        raise ExperimentError(
            "pinned Cubism warp-ID sequence changed: "
            f"expected {ROOT_DEFORMER_ID!r}, derived {planned_id!r}"
        )
    if ROOT_DEFORMER_ID in existing_ids:
        raise ExperimentError(f"{ROOT_DEFORMER_ID!r} already exists")
    return {
        "existing_ids_unique": True,
        "highest_existing_warp_number": max(warp_numbers),
        "planned_internal_id": ROOT_DEFORMER_ID,
        "pattern": "Warp, Warp2, ...",
    }


def _part_hierarchy_state(root: ET.Element) -> dict[str, Any]:
    shared = root.find("shared")
    assert shared is not None
    ids = _id_map(root)
    specs = (
        ("CArtMeshSource", "CDrawableGuid"),
        ("CWarpDeformerSource", "CDeformerGuid"),
        ("CRotationDeformerSource", "CDeformerGuid"),
        ("CPartSource", "CPartGuid"),
    )
    entities: dict[str, dict[str, Any]] = {}
    root_part_refs: list[str] = []
    for source_tag, guid_tag in specs:
        for source in shared.findall(source_tag):
            name = _one_named(source, "s", "localName").text or ""
            guid_ref = _one_named(source, guid_tag, "guid").get("xs.ref")
            source_ref = source.get("xs.id")
            if not guid_ref or not source_ref:
                raise ExperimentError(
                    f"{source_tag} {name!r} lacks source or identity reference"
                )
            guid = ids.get(guid_ref)
            if guid is None or guid.tag != guid_tag:
                raise ExperimentError(
                    f"{source_tag} {name!r} identity {guid_ref!r} is unresolved"
                )
            parent_nodes = [
                node
                for node in source.iter("CPartGuid")
                if node.get("xs.n") == "parentGuid"
            ]
            root_null_nodes = [
                node
                for node in source.iter("null")
                if node.get("xs.n") == "parentGuid"
            ]
            if len(parent_nodes) == 1 and not root_null_nodes:
                parent_part_ref = parent_nodes[0].get("xs.ref")
                if (
                    not parent_part_ref
                    or ids.get(parent_part_ref) is None
                    or ids[parent_part_ref].tag != "CPartGuid"
                ):
                    raise ExperimentError(
                        f"{source_tag} {name!r} has an unresolved Part parent"
                    )
            elif (
                source_tag == "CPartSource"
                and not parent_nodes
                and len(root_null_nodes) == 1
            ):
                parent_part_ref = None
                root_part_refs.append(guid_ref)
            else:
                raise ExperimentError(
                    f"{source_tag} {name!r} has an ambiguous Part parent"
                )
            if guid_ref in entities:
                raise ExperimentError(
                    f"Part hierarchy identity {guid_ref!r} is reused"
                )
            entities[guid_ref] = {
                "source_tag": source_tag,
                "guid_tag": guid_tag,
                "name": name,
                "source_ref": source_ref,
                "guid_uuid": _canonical_uuid(
                    guid.get("uuid"),
                    f"{source_tag} {name} hierarchy GUID",
                ),
                "parent_part_ref": parent_part_ref,
            }
    if len(root_part_refs) != 1:
        raise ExperimentError(
            f"expected one root Part, found {len(root_part_refs)}"
        )

    part_children: dict[str, list[tuple[str, str]]] = {}
    memberships: dict[str, list[tuple[str, str]]] = {}
    for source in shared.findall("CPartSource"):
        part_guid_ref = _one_named(
            source,
            "CPartGuid",
            "guid",
        ).get("xs.ref")
        if not part_guid_ref:
            raise ExperimentError("a Part source lacks its GUID reference")
        children = _direct_named(source, "carray_list", "_childGuids")
        if children.get("count") != str(len(children)):
            raise ExperimentError(
                f"Part {part_guid_ref} _childGuids count is inconsistent"
            )
        ordered: list[tuple[str, str]] = []
        for child in children:
            if child.tag not in {
                "CDrawableGuid",
                "CDeformerGuid",
                "CPartGuid",
            }:
                raise ExperimentError(
                    f"unsupported Part child tag {child.tag!r}"
                )
            child_ref = child.get("xs.ref")
            entity = entities.get(child_ref or "")
            if child_ref is None or entity is None:
                raise ExperimentError(
                    f"Part {part_guid_ref} has unresolved child {child_ref!r}"
                )
            if entity["guid_tag"] != child.tag:
                raise ExperimentError(
                    f"Part child {child_ref} uses {child.tag}, "
                    f"expected {entity['guid_tag']}"
                )
            ordered.append((child.tag, child_ref))
            memberships.setdefault(child_ref, []).append(
                (part_guid_ref, child.tag)
            )
        if len(ordered) != len(set(ordered)):
            raise ExperimentError(
                f"Part {part_guid_ref} has duplicate child entries"
            )
        part_children[part_guid_ref] = ordered

    for guid_ref, entity in entities.items():
        parent_part_ref = entity["parent_part_ref"]
        observed = memberships.get(guid_ref, [])
        if parent_part_ref is None:
            if observed:
                raise ExperimentError("root Part appears as another Part's child")
            continue
        expected = [(parent_part_ref, entity["guid_tag"])]
        if observed != expected:
            raise ExperimentError(
                f"{entity['source_tag']} {entity['name']!r} Part membership "
                f"is {observed!r}, expected {expected!r}"
            )
    if set(part_children) != {
        guid_ref
        for guid_ref, entity in entities.items()
        if entity["source_tag"] == "CPartSource"
    }:
        raise ExperimentError("Part source/child-list identity sets differ")
    return {
        "entities": entities,
        "part_children": part_children,
        "root_part_ref": root_part_refs[0],
        "entity_count": len(entities),
        "part_count": len(part_children),
        "membership_count": sum(len(items) for items in part_children.values()),
        "all_memberships_exact": True,
    }


def _assert_part_hierarchy_delta(
    before: dict[str, Any],
    after: dict[str, Any],
    root_meta: dict[str, Any],
) -> dict[str, Any]:
    new_guid_ref = root_meta["guid_ref"]
    owner_part_ref = root_meta["parent_part_ref"]
    before_entities = before["entities"]
    after_entities = after["entities"]
    if set(after_entities) != set(before_entities) | {new_guid_ref}:
        raise ExperimentError(
            "Part hierarchy entity set changed beyond the new root"
        )
    for guid_ref, entity in before_entities.items():
        if after_entities.get(guid_ref) != entity:
            raise ExperimentError(
                f"existing Part hierarchy entity changed: {entity['name']!r}"
            )
    new_entity = after_entities[new_guid_ref]
    if new_entity != {
        "source_tag": "CWarpDeformerSource",
        "guid_tag": "CDeformerGuid",
        "name": ROOT_NAME,
        "source_ref": root_meta["source_ref"],
        "guid_uuid": root_meta["uuids"]["deformer"],
        "parent_part_ref": owner_part_ref,
    }:
        raise ExperimentError(
            f"new root Part hierarchy identity is incorrect: {new_entity!r}"
        )
    if set(after["part_children"]) != set(before["part_children"]):
        raise ExperimentError("Part set changed")
    for part_ref, old_children in before["part_children"].items():
        new_children = after["part_children"][part_ref]
        expected = (
            [("CDeformerGuid", new_guid_ref), *old_children]
            if part_ref == owner_part_ref
            else old_children
        )
        if new_children != expected:
            raise ExperimentError(
                f"unexpected _childGuids delta in Part {part_ref}"
            )
    owner_entity = before_entities.get(owner_part_ref)
    if (
        owner_entity is None
        or owner_entity["source_tag"] != "CPartSource"
    ):
        raise ExperimentError("new root owner is not an existing Part")
    if after["membership_count"] != before["membership_count"] + 1:
        raise ExperimentError("Part hierarchy membership count did not grow by one")
    return {
        "owner_part_guid_ref": owner_part_ref,
        "owner_part_source_ref": owner_entity["source_ref"],
        "owner_part_name": owner_entity["name"],
        "owner_children_before": len(before["part_children"][owner_part_ref]),
        "owner_children_after": len(after["part_children"][owner_part_ref]),
        "inserted_entry": {
            "index": 0,
            "tag": "CDeformerGuid",
            "guid_ref": new_guid_ref,
            "deformer_name": ROOT_NAME,
            "deformer_internal_id": ROOT_DEFORMER_ID,
        },
        "entity_count": [before["entity_count"], after["entity_count"]],
        "membership_count": [
            before["membership_count"],
            after["membership_count"],
        ],
        "all_memberships_exact": after["all_memberships_exact"],
        "all_existing_part_children_order_preserved": True,
    }


def _validate_no_cycles(graph: dict[str, dict[str, str]]) -> None:
    for starting_ref in graph:
        seen: list[str] = []
        current = starting_ref
        while current in graph:
            if current in seen:
                cycle = seen[seen.index(current) :] + [current]
                raise ExperimentError(
                    "deformer cycle: "
                    + " -> ".join(graph[ref]["name"] for ref in cycle)
                )
            seen.append(current)
            current = graph[current]["parent_ref"]


def _xml_summary(root: ET.Element) -> dict[str, Any]:
    shared = root.find("shared")
    model = root.find("main/CModelSource")
    assert shared is not None and model is not None
    ids = _id_map(root)
    all_ids = list(ids)
    all_indices = [
        child.get("xs.idx")
        for child in shared
    ]
    if any(value is None or not value.isdigit() for value in all_indices):
        raise ExperimentError("a shared definition lacks numeric xs.idx")
    numeric_indices = [int(value) for value in all_indices if value is not None]
    if len(numeric_indices) != len(set(numeric_indices)):
        raise ExperimentError("duplicate shared xs.idx")
    unresolved = [
        serialized_ref
        for node in root.iter()
        if (serialized_ref := node.get("xs.ref")) is not None
        and serialized_ref not in ids
    ]
    if unresolved:
        raise ExperimentError(f"unresolved xs.ref values: {unresolved[:5]!r}")

    all_uuids = [
        _canonical_uuid(node.get("uuid"), f"{node.tag} UUID")
        for node in root.iter()
        if node.get("uuid") is not None
    ]
    if len(all_uuids) != len(set(all_uuids)):
        raise ExperimentError("duplicate UUID values")

    source_set = model.find("CDeformerSourceSet/carray_list")
    if source_set is None or source_set.get("xs.n") != "_sources":
        raise ExperimentError("missing CDeformerSourceSet/_sources")
    source_refs = [
        child.get("xs.ref")
        for child in source_set
    ]
    if source_set.get("count") != str(len(source_refs)):
        raise ExperimentError("CDeformerSourceSet count is inconsistent")
    if len(source_refs) != len(set(source_refs)):
        raise ExperimentError("duplicate CDeformerSourceSet reference")
    if any(ref not in ids for ref in source_refs):
        raise ExperimentError("unresolved CDeformerSourceSet reference")

    graph = _deformer_graph(root)
    _validate_no_cycles(graph)
    return {
        "shared_definitions": len(shared),
        "xs_id_count": len(all_ids),
        "xs_idx_count": len(numeric_indices),
        "uuid_count": len(all_uuids),
        "all_xs_ids_unique": len(all_ids) == len(set(all_ids)),
        "all_xs_indices_unique": len(numeric_indices) == len(set(numeric_indices)),
        "all_uuids_unique": len(all_uuids) == len(set(all_uuids)),
        "all_references_resolved": not unresolved,
        "deformer_source_count": len(source_refs),
        "deformer_source_refs": source_refs,
        "deformer_graph": graph,
    }


def _entry_proof(
    before_data: bytes,
    after_data: bytes,
) -> dict[str, Any]:
    before = CaffArchive.parse(before_data)
    after = CaffArchive.parse(after_data)
    if len(before.entries) != len(after.entries):
        raise ExperimentError("CAFF entry count changed")
    changed = []
    non_main_identical = 0
    for old, new in zip(before.entries, after.entries):
        if old.path != new.path:
            raise ExperimentError("CAFF entry order/path changed")
        old_stored = before_data[old.start : old.start + old.size]
        new_stored = after_data[new.start : new.start + new.size]
        if old.path == "main.xml":
            if (
                old.path,
                old.tag,
                old.start,
                old.obfuscated,
                old.compression,
            ) != (
                new.path,
                new.tag,
                new.start,
                new.obfuscated,
                new.compression,
            ):
                raise ExperimentError("main.xml metadata changed beyond size")
            if old_stored == new_stored:
                raise ExperimentError("main.xml stored bytes unexpectedly unchanged")
            changed.append("main.xml")
            continue
        if old != new or old_stored != new_stored:
            raise ExperimentError(f"non-main CAFF member changed: {old.path!r}")
        non_main_identical += 1
    if changed != ["main.xml"]:
        raise ExperimentError("expected only main.xml to change")
    return {
        "entry_count": len(before.entries),
        "non_main_member_count": non_main_identical,
        "all_non_main_members_metadata_and_bytes_identical": (
            non_main_identical == len(before.entries) - 1
        ),
        "changed_members": changed,
    }


def _assert_inventory_delta(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    before_counts = before["counts"]
    after_counts = after["counts"]
    expected_deltas = {
        "art_meshes": 0,
        "warp_deformers": 1,
        "rotation_deformers": 0,
        "deformers_total": 1,
        "parts": 0,
        "parameters": 0,
        "bound_objects": 0,
        "object_parameter_bindings": 0,
        "serialized_parameter_binding_definitions": 0,
        "unreferenced_parameter_binding_definitions": 0,
        "serialized_keyform_grid_definitions": 0,
        "keyforms_total": 1,
        "physics_settings": 0,
        "game_motions": 0,
        "motion_sync_settings": 0,
    }
    observed_deltas = {
        key: after_counts[key] - before_counts[key]
        for key in expected_deltas
    }
    if observed_deltas != expected_deltas:
        raise ExperimentError(
            f"unexpected inventory delta: {observed_deltas!r}"
        )
    if before["parameter_ids"] != after["parameter_ids"]:
        raise ExperimentError("parameter IDs/order changed")
    if before["bound_objects"] != after["bound_objects"]:
        raise ExperimentError("bound-object inventory changed")
    if after["warp_deformer_names"] != [
        *before["warp_deformer_names"],
        ROOT_NAME,
    ]:
        raise ExperimentError("warp deformer ordering/names changed unexpectedly")
    if before["rotation_deformer_names"] != after["rotation_deformer_names"]:
        raise ExperimentError("rotation deformer inventory changed")
    return {
        "expected_deltas": expected_deltas,
        "observed_deltas": observed_deltas,
        "art_meshes_unchanged": (
            before_counts["art_meshes"] == after_counts["art_meshes"] == 58
        ),
        "parameters_unchanged": (
            before_counts["parameters"] == after_counts["parameters"] == 27
            and before["parameter_ids"] == after["parameter_ids"]
        ),
        "warp_deformers": [
            before_counts["warp_deformers"],
            after_counts["warp_deformers"],
        ],
        "keyforms_total": [
            before_counts["keyforms_total"],
            after_counts["keyforms_total"],
        ],
    }


def _assert_semantic_graph_delta(
    before_summary: dict[str, Any],
    after_summary: dict[str, Any],
    root_meta: dict[str, Any],
) -> dict[str, Any]:
    before_graph = before_summary["deformer_graph"]
    after_graph = after_summary["deformer_graph"]
    new_guid_ref = root_meta["guid_ref"]
    if set(after_graph) != set(before_graph) | {new_guid_ref}:
        raise ExperimentError("deformer GUID set changed beyond the new root")
    changed_existing = {}
    for guid_ref, old in before_graph.items():
        new = after_graph.get(guid_ref)
        if new is None:
            raise ExperimentError(f"existing deformer disappeared: {old['name']!r}")
        immutable_keys = ("name", "kind", "uuid")
        if any(old[key] != new[key] for key in immutable_keys):
            raise ExperimentError(
                f"existing deformer identity changed: {old['name']!r}"
            )
        if old["parent_ref"] != new["parent_ref"]:
            changed_existing[old["name"]] = {
                "old_parent_ref": old["parent_ref"],
                "new_parent_ref": new["parent_ref"],
            }
    if set(changed_existing) != set(ROOT_CHILD_NAMES):
        raise ExperimentError(
            f"unexpected existing parent changes: {changed_existing!r}"
        )
    if any(
        change["new_parent_ref"] != new_guid_ref
        for change in changed_existing.values()
    ):
        raise ExperimentError("a root child does not reference the new root")
    new_root = after_graph[new_guid_ref]
    if (
        new_root["name"] != ROOT_NAME
        or new_root["kind"] != "CWarpDeformerSource"
    ):
        raise ExperimentError("new root semantic identity is incorrect")
    old_root_parent_refs = {
        before_graph[guid_ref]["parent_ref"]
        for guid_ref in before_graph
        if before_graph[guid_ref]["name"] in ROOT_CHILD_NAMES
    }
    if len(old_root_parent_refs) != 1:
        raise ExperimentError("existing root children did not share one root sentinel")
    root_sentinel = next(iter(old_root_parent_refs))
    if new_root["parent_ref"] != root_sentinel:
        raise ExperimentError("new root is not attached to the original root sentinel")
    return {
        "new_root_guid_ref": new_guid_ref,
        "new_root_parent_ref": root_sentinel,
        "changed_existing_parents": changed_existing,
        "only_requested_existing_deformers_reparented": True,
        "cycle_free": True,
    }


def _safe_output_paths(output: Path, report: Path) -> tuple[Path, Path]:
    output = output.resolve(strict=False)
    report = report.resolve(strict=False)
    for path, extension in ((output, ".cmo3"), (report, ".json")):
        if path.parent != REPORTS_DIR:
            raise ExperimentError(f"output must be directly under {REPORTS_DIR}")
        if path.suffix.casefold() != extension:
            raise ExperimentError(f"{path.name} must use {extension}")
        if "test" not in path.stem.casefold():
            raise ExperimentError(f"{path.name} must contain TEST")
        if path.exists():
            raise ExperimentError(f"refusing to overwrite existing file: {path}")
    if output == report:
        raise ExperimentError("CMO3 output and report paths must differ")
    return output, report


def _write_exclusive(path: Path, data: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    if path.read_bytes() != data:
        raise ExperimentError(f"filesystem verification failed for {path}")


def _build_experiment(
    source: Path,
    output: Path,
    report_path: Path,
) -> dict[str, Any]:
    source = source.resolve(strict=True)
    output, report_path = _safe_output_paths(output, report_path)
    if not source.is_file() or source.suffix.casefold() != ".cmo3":
        raise ExperimentError("source must be an existing .cmo3 file")
    if source in {output, report_path}:
        raise ExperimentError("source and outputs must differ")

    source_data = source.read_bytes()
    source_sha = _sha256(source_data)
    if source_sha != EXPECTED_SOURCE_SHA256:
        raise ExperimentError(
            "source is not the pinned Jade v003 checkpoint: "
            f"{source_sha} != {EXPECTED_SOURCE_SHA256}"
        )
    try:
        (
            _,
            _,
            _,
            _,
            main_before,
        ) = _validate_surgical_layout(source_data)
    except SafeWriteError as exc:
        raise ExperimentError(str(exc)) from exc

    before_root = _parse_xml(main_before)
    before_summary = _xml_summary(before_root)
    deformer_id_proof = _assert_deformer_id_plan(before_root)
    before_part_hierarchy = _part_hierarchy_state(before_root)
    if ROOT_NAME in [
        item["name"]
        for item in before_summary["deformer_graph"].values()
    ]:
        raise ExperimentError(f"{ROOT_NAME!r} already exists")

    clone = _warp_info(before_root, CLONE_SOURCE_NAME)
    exemplar = _warp_info(before_root, INDEX_EXEMPLAR_NAME)
    children = tuple(
        _warp_info(before_root, name)
        for name in ROOT_CHILD_NAMES
    )
    if clone.col != 5 or clone.row != 5:
        raise ExperimentError("clone source is not the observed 5x5 Cubism schema")
    if exemplar.col != clone.col or exemplar.row != clone.row:
        raise ExperimentError("index exemplar dimensions differ from clone")
    if clone.positions != clone.original_positions:
        raise ExperimentError("clone source is not a top-level neutral warp")
    if any(
        child.positions != child.original_positions
        for child in children
    ):
        raise ExperimentError(
            "a requested root child is not serialized in canvas coordinates"
        )
    if any(
        child.parent_ref != children[0].parent_ref
        for child in children
    ):
        raise ExperimentError("requested root children do not share one parent")

    root_positions, root_bounds = _root_geometry(
        [child.positions for child in children],
        clone.col,
        clone.row,
    )
    local_positions = {
        child.name: _to_parent_local(child.positions, root_bounds)
        for child in children
    }
    reconstruction_errors = {
        child.name: _max_reconstruction_error(
            child.positions,
            local_positions[child.name],
            root_bounds,
        )
        for child in children
    }
    if max(reconstruction_errors.values()) > 0.001:
        raise ExperimentError(
            f"neutral-pose reconstruction error is too high: "
            f"{reconstruction_errors!r}"
        )

    new_blocks, root_meta = _clone_root_blocks(
        main_before,
        clone,
        exemplar,
        source_sha,
        root_positions,
    )
    main_after_expected = main_before
    for child in children:
        main_after_expected = _patch_existing_child(
            main_after_expected,
            child,
            root_meta["guid_ref"],
            local_positions[child.name],
        )
    main_after_expected = _append_shared_blocks(
        main_after_expected,
        new_blocks,
    )
    main_after_expected = _patch_deformer_source_set(
        main_after_expected,
        root_meta["source_ref"],
    )
    main_after_expected = _patch_part_hierarchy(
        main_after_expected,
        root_meta["parent_part_ref"],
        root_meta["guid_ref"],
    )

    after_root = _parse_xml(main_after_expected)
    after_summary = _xml_summary(after_root)
    after_part_hierarchy = _part_hierarchy_state(after_root)
    graph_proof = _assert_semantic_graph_delta(
        before_summary,
        after_summary,
        root_meta,
    )
    part_hierarchy_proof = _assert_part_hierarchy_delta(
        before_part_hierarchy,
        after_part_hierarchy,
        root_meta,
    )
    if after_summary["shared_definitions"] != (
        before_summary["shared_definitions"] + 4
    ):
        raise ExperimentError("shared definition count did not increase by four")
    if after_summary["deformer_source_count"] != (
        before_summary["deformer_source_count"] + 1
    ):
        raise ExperimentError("deformer source count did not increase by one")

    new_root = _warp_info(after_root, ROOT_NAME)
    if (
        new_root.source_ref != root_meta["source_ref"]
        or new_root.guid_ref != root_meta["guid_ref"]
        or new_root.form_ref != root_meta["form_ref"]
        or new_root.positions_ref != root_meta["positions_ref"]
        or new_root.deformer_id != ROOT_DEFORMER_ID
        or new_root.parent_ref != graph_proof["new_root_parent_ref"]
        or new_root.parent_part_ref != root_meta["parent_part_ref"]
        or new_root.col != 5
        or new_root.row != 5
        or not _float32_sequences_equal(new_root.positions, root_positions)
        or not _float32_sequences_equal(
            new_root.original_positions,
            root_positions,
        )
    ):
        raise ExperimentError("new root does not match the planned serialization")
    for child_before in children:
        child_after = _warp_info(after_root, child_before.name)
        if not _float32_sequences_equal(
            child_after.positions,
            local_positions[child_before.name],
        ):
            raise ExperimentError(
                f"{child_before.name!r} local positions differ from the plan"
            )
        if child_after.original_positions != child_before.original_positions:
            raise ExperimentError(
                f"{child_before.name!r} original canvas shape changed"
            )

    try:
        output_data = _replace_main_xml(source_data, main_after_expected)
        (
            _,
            _,
            _,
            _,
            main_after_written,
        ) = _validate_surgical_layout(output_data)
    except SafeWriteError as exc:
        raise ExperimentError(str(exc)) from exc
    if main_after_written != main_after_expected:
        raise ExperimentError("written in-memory main.xml differs from planned XML")
    entry_proof = _entry_proof(source_data, output_data)

    # All structural and byte-preservation checks above run before the first write.
    _write_exclusive(output, output_data)
    try:
        if _sha256(source.read_bytes()) != source_sha:
            raise ExperimentError("source checkpoint changed during the experiment")
        if output.read_bytes() != output_data:
            raise ExperimentError("written CMO3 differs from validated in-memory bytes")
        before_inventory = inventory_file(
            source,
            max_xml_bytes=MAX_XML_BYTES,
            include_details=False,
        )
        after_inventory = inventory_file(
            output,
            max_xml_bytes=MAX_XML_BYTES,
            include_details=False,
        )
        inventory_proof = _assert_inventory_delta(
            before_inventory,
            after_inventory,
        )
    except Exception:
        # The output is newly created by this run and is never a user checkpoint.
        if output.exists():
            output.unlink()
        raise

    local_ranges = {
        name: {
            "x": [
                min(values[0::2]),
                max(values[0::2]),
            ],
            "y": [
                min(values[1::2]),
                max(values[1::2]),
            ],
        }
        for name, values in local_positions.items()
    }
    report: dict[str, Any] = {
        "status": "ok",
        "operation": (
            "create_test_root_warp_reparent_two_roots_and_register_part_hierarchy"
        ),
        "safety": {
            "test_only": True,
            "gui_opened": False,
            "cubism_editor_acceptance_pending": True,
            "source_overwritten": False,
            "source_sha256_pinned": True,
            "note": (
                "Structural/byte invariants are proven. Cubism Editor was not "
                "opened by this experiment, so application-level acceptance "
                "remains a separate gate."
            ),
        },
        "source": {
            "path": str(source),
            "bytes": len(source_data),
            "sha256_before": source_sha,
            "sha256_after": _sha256(source.read_bytes()),
        },
        "output": {
            "path": str(output),
            "bytes": len(output_data),
            "sha256": _sha256(output_data),
            "main_xml_bytes_before": len(main_before),
            "main_xml_bytes_after": len(main_after_written),
            "main_xml_sha256_before": _sha256(main_before),
            "main_xml_sha256_after": _sha256(main_after_written),
        },
        "schema_choice": {
            "requested_preference": "2x2 if proven, otherwise minimal safe",
            "chosen": "5x5 exact observed Cubism 5.2 schema",
            "reason": (
                "No 2x2 warp exists in the 230 historical warp samples scanned; "
                "all observed warps are 5x5. The experiment therefore clones "
                "the only attested schema."
            ),
            "clone_source": CLONE_SOURCE_NAME,
            "index_exemplar": root_meta["index_exemplar"],
        },
        "new_root": {
            "name": ROOT_NAME,
            "deformer_id": ROOT_DEFORMER_ID,
            "dimensions": [new_root.col, new_root.row],
            "keyforms": 1,
            "parameter_bindings": 0,
            "inner_margin": INNER_MARGIN,
            "canvas_bounds": {
                "min_x": root_bounds[0],
                "max_x": root_bounds[1],
                "min_y": root_bounds[2],
                "max_y": root_bounds[3],
            },
            "serialization": root_meta,
            "deformer_id_proof": deformer_id_proof,
        },
        "part_hierarchy_proof": {
            **part_hierarchy_proof,
            "observed_cubism_recovery_pattern": (
                "Cubism 5.2.03 recovered r01 by prepending Warp21's "
                "CDeformerGuid to Root Part/_childGuids; r02 applies that "
                "membership directly while preserving the intended name."
            ),
        },
        "reparenting": {
            "children": list(ROOT_CHILD_NAMES),
            "local_coordinate_ranges": local_ranges,
            "neutral_pose_max_reconstruction_error_pixels": reconstruction_errors,
            **graph_proof,
        },
        "xml_proof": {
            "before": {
                key: before_summary[key]
                for key in (
                    "shared_definitions",
                    "xs_id_count",
                    "xs_idx_count",
                    "uuid_count",
                    "deformer_source_count",
                )
            },
            "after": {
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
        },
        "caff_proof": entry_proof,
        "inventory_proof": inventory_proof,
    }
    report_bytes = (
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    try:
        _write_exclusive(report_path, report_bytes)
    except Exception:
        # Keep the already validated TEST CMO3; do not silently erase evidence.
        raise
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create a structurally validated TEST-only D_JAD_ROOT experiment "
            "from the pinned Jade v003 CMO3 checkpoint."
        )
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("report", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = _build_experiment(args.source, args.output, args.report)
    except (
        ExperimentError,
        InventoryError,
        OSError,
        SafeWriteError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
