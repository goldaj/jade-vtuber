#!/usr/bin/env python3
"""
Apply narrowly-scoped, neutral-canvas-preserving CMO3 reparents.

This is a copy-on-write TEST-only tool.  It is intentionally stricter than a
general Cubism editor:

* the input filename and SHA-256 must match a manifest;
* every reparented target must have exactly one unbound keyform;
* the target's immutable original-shape coordinates must reconstruct its
  current neutral canvas position within the manifest tolerance;
* the replacement local keyform is quantized to IEEE-754 binary32 and must
  reconstruct the same canvas coordinates within the same tolerance;
* only the target parent reference, target keyform position payload, and an
  explicitly declared visible-name field may change;
* the output filename must contain TEST and must not already exist;
* all non-main.xml CAFF members remain byte-identical.

It supports the neutral deformer forms required by the Jade v003 repair:
ROOT identity, neutral rotation deformers (angle 0, scale 1, no reflection),
and warp deformers whose unique neutral keyform is recoverable by matching
their immutable original canvas grid.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
import sys
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import cmo3_safe_roundtrip as safe


ROOT_NOTE = "ROOT"
MAX_MANIFEST_BYTES = 1024 * 1024
SUPPORTED_TYPES = {"art-mesh", "warp-deformer", "rotation-deformer"}
DEFORMER_TYPES = {"warp-deformer", "rotation-deformer"}


class CanvasPreserveError(RuntimeError):
    """Raised when a coordinate-preserving mutation cannot be proven safe."""


@dataclass(frozen=True)
class Operation:
    operation_id: str
    kind: str
    target_type: str
    target_name: str
    target_uuid: str
    old_parent_uuid: str
    new_parent_type: str | None = None
    new_parent_name: str | None = None
    new_parent_uuid: str | None = None
    new_name: str | None = None


@dataclass(frozen=True)
class IdentityTransform:
    guid_ref: str
    guid_uuid: str


@dataclass(frozen=True)
class RotationTransform:
    guid_ref: str
    name: str
    pivot_x: float
    pivot_y: float


@dataclass(frozen=True)
class WarpTransform:
    guid_ref: str
    name: str
    columns: int
    rows: int
    neutral_positions: tuple[float, ...]
    neutral_keyform_index: int
    neutral_match_error_px: float
    parent: "NeutralTransform"


NeutralTransform = IdentityTransform | RotationTransform | WarpTransform


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _float32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def _format_float32(value: float) -> str:
    value = _float32(value)
    if not math.isfinite(value):
        raise CanvasPreserveError("generated a non-finite float")
    if value == 0.0:
        return "0.0"
    text = format(value, ".9g")
    if "e" not in text.casefold() and "." not in text:
        text += ".0"
    return text


def _canonical_uuid(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise CanvasPreserveError(f"{label} must be a UUID string")
    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise CanvasPreserveError(f"{label} is not a valid UUID") from exc


def _exact_keys(
    value: dict[str, Any],
    required: set[str],
    label: str,
) -> None:
    missing = required - set(value)
    unexpected = set(value) - required
    if missing or unexpected:
        raise CanvasPreserveError(
            f"{label} keys differ; missing={sorted(missing)}, "
            f"unexpected={sorted(unexpected)}"
        )


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CanvasPreserveError(f"{label} must be an object")
    return value


def _nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise CanvasPreserveError(f"{label} must be a non-empty string")
    return value


def _identity(
    value: Any,
    label: str,
    *,
    include_parent: bool,
) -> dict[str, str]:
    raw = _mapping(value, label)
    keys = {"type", "old_name", "uuid"}
    if include_parent:
        keys.add("old_parent_uuid")
    _exact_keys(raw, keys, label)
    object_type = _nonempty_string(raw["type"], f"{label}.type")
    if object_type not in SUPPORTED_TYPES:
        raise CanvasPreserveError(
            f"{label}.type is unsupported: {object_type!r}"
        )
    result = {
        "type": object_type,
        "old_name": _nonempty_string(raw["old_name"], f"{label}.old_name"),
        "uuid": _canonical_uuid(raw["uuid"], f"{label}.uuid"),
    }
    if include_parent:
        result["old_parent_uuid"] = _canonical_uuid(
            raw["old_parent_uuid"],
            f"{label}.old_parent_uuid",
        )
    return result


def _load_manifest(
    path: Path,
) -> tuple[dict[str, Any], list[Operation], list[dict[str, Any]], bytes]:
    path = path.resolve(strict=True)
    raw_bytes = path.read_bytes()
    if len(raw_bytes) > MAX_MANIFEST_BYTES:
        raise CanvasPreserveError("manifest exceeds 1 MiB")
    try:
        raw = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CanvasPreserveError(f"invalid UTF-8 JSON manifest: {exc}") from exc
    root = _mapping(raw, "manifest")
    _exact_keys(
        root,
        {
            "schema_version",
            "transaction_id",
            "description",
            "source",
            "output",
            "coordinate_contract",
            "operations",
            "assertions",
        },
        "manifest",
    )
    if root["schema_version"] != 1:
        raise CanvasPreserveError("manifest.schema_version must equal 1")
    transaction_id = _nonempty_string(
        root["transaction_id"],
        "manifest.transaction_id",
    )
    if re.fullmatch(r"[A-Za-z0-9._-]{1,100}", transaction_id) is None:
        raise CanvasPreserveError("manifest.transaction_id has unsafe characters")
    _nonempty_string(root["description"], "manifest.description")

    source = _mapping(root["source"], "manifest.source")
    _exact_keys(source, {"required_filename", "sha256"}, "manifest.source")
    source_name = _nonempty_string(
        source["required_filename"],
        "manifest.source.required_filename",
    )
    if Path(source_name).name != source_name:
        raise CanvasPreserveError("source required_filename must be a basename")
    source_sha = _nonempty_string(source["sha256"], "manifest.source.sha256")
    if re.fullmatch(r"[0-9A-Fa-f]{64}", source_sha) is None:
        raise CanvasPreserveError("manifest source SHA-256 is malformed")
    source["sha256"] = source_sha.upper()

    output = _mapping(root["output"], "manifest.output")
    _exact_keys(output, {"required_filename"}, "manifest.output")
    output_name = _nonempty_string(
        output["required_filename"],
        "manifest.output.required_filename",
    )
    if Path(output_name).name != output_name:
        raise CanvasPreserveError("output required_filename must be a basename")
    if (
        Path(output_name).suffix.casefold() != ".cmo3"
        or "test" not in Path(output_name).stem.casefold()
    ):
        raise CanvasPreserveError("manifest output must be a TEST .cmo3")

    contract = _mapping(
        root["coordinate_contract"],
        "manifest.coordinate_contract",
    )
    _exact_keys(
        contract,
        {
            "space",
            "float_encoding",
            "max_reconstruction_error_px",
        },
        "manifest.coordinate_contract",
    )
    if contract["space"] != "neutral_canvas":
        raise CanvasPreserveError("coordinate space must be neutral_canvas")
    if contract["float_encoding"] != "IEEE-754 binary32":
        raise CanvasPreserveError("float encoding must be IEEE-754 binary32")
    tolerance = contract["max_reconstruction_error_px"]
    if not isinstance(tolerance, (int, float)) or not 0 < tolerance <= 0.001:
        raise CanvasPreserveError(
            "max_reconstruction_error_px must be in (0, 0.001]"
        )

    raw_operations = root["operations"]
    if not isinstance(raw_operations, list) or not raw_operations:
        raise CanvasPreserveError("manifest.operations must be a non-empty list")
    operations: list[Operation] = []
    seen_ids: set[str] = set()
    seen_fields: set[tuple[str, str]] = set()
    for index, raw_operation in enumerate(raw_operations):
        label = f"manifest.operations[{index}]"
        item = _mapping(raw_operation, label)
        kind = _nonempty_string(item.get("op"), f"{label}.op")
        if kind == "reparent-preserve-canvas":
            _exact_keys(item, {"id", "op", "object", "new_parent"}, label)
        elif kind == "rename":
            _exact_keys(item, {"id", "op", "object", "new_name"}, label)
        else:
            raise CanvasPreserveError(f"{label}.op is unsupported: {kind!r}")
        operation_id = _nonempty_string(item["id"], f"{label}.id")
        if (
            re.fullmatch(r"[A-Za-z0-9._-]{1,100}", operation_id) is None
            or operation_id in seen_ids
        ):
            raise CanvasPreserveError(
                f"{label}.id is unsafe or duplicated: {operation_id!r}"
            )
        seen_ids.add(operation_id)
        target = _identity(item["object"], f"{label}.object", include_parent=True)
        field = "parent" if kind == "reparent-preserve-canvas" else "name"
        if (target["uuid"], field) in seen_fields:
            raise CanvasPreserveError(
                f"{label} duplicates target field {field!r}"
            )
        seen_fields.add((target["uuid"], field))
        if kind == "reparent-preserve-canvas":
            parent = _identity(
                item["new_parent"],
                f"{label}.new_parent",
                include_parent=False,
            )
            if parent["type"] not in DEFORMER_TYPES:
                raise CanvasPreserveError(f"{label}.new_parent is not a deformer")
            operations.append(
                Operation(
                    operation_id=operation_id,
                    kind=kind,
                    target_type=target["type"],
                    target_name=target["old_name"],
                    target_uuid=target["uuid"],
                    old_parent_uuid=target["old_parent_uuid"],
                    new_parent_type=parent["type"],
                    new_parent_name=parent["old_name"],
                    new_parent_uuid=parent["uuid"],
                )
            )
        else:
            new_name = _nonempty_string(item["new_name"], f"{label}.new_name")
            operations.append(
                Operation(
                    operation_id=operation_id,
                    kind=kind,
                    target_type=target["type"],
                    target_name=target["old_name"],
                    target_uuid=target["uuid"],
                    old_parent_uuid=target["old_parent_uuid"],
                    new_name=new_name,
                )
            )

    assertions = _mapping(root["assertions"], "manifest.assertions")
    _exact_keys(assertions, {"preserve_children"}, "manifest.assertions")
    raw_preserve = assertions["preserve_children"]
    if not isinstance(raw_preserve, list):
        raise CanvasPreserveError("assertions.preserve_children must be a list")
    normalized_assertions: list[dict[str, Any]] = []
    for index, raw_assertion in enumerate(raw_preserve):
        label = f"manifest.assertions.preserve_children[{index}]"
        assertion = _mapping(raw_assertion, label)
        _exact_keys(
            assertion,
            {"id", "parent", "children", "require_exact_child_set"},
            label,
        )
        if assertion["require_exact_child_set"] is not True:
            raise CanvasPreserveError(
                f"{label}.require_exact_child_set must be true"
            )
        parent = _identity(
            assertion["parent"],
            f"{label}.parent",
            include_parent=False,
        )
        if parent["type"] not in DEFORMER_TYPES:
            raise CanvasPreserveError(f"{label}.parent is not a deformer")
        children_raw = assertion["children"]
        if not isinstance(children_raw, list) or not children_raw:
            raise CanvasPreserveError(f"{label}.children must be non-empty")
        normalized_assertions.append(
            {
                "id": _nonempty_string(assertion["id"], f"{label}.id"),
                "parent": parent,
                "children": [
                    _identity(
                        child,
                        f"{label}.children[{child_index}]",
                        include_parent=False,
                    )
                    for child_index, child in enumerate(children_raw)
                ],
            }
        )
    return root, operations, normalized_assertions, raw_bytes


def _parse_xml(xml_bytes: bytes) -> ET.Element:
    if b"<!DOCTYPE" in xml_bytes[:65536] or b"<!ENTITY" in xml_bytes[:65536]:
        raise CanvasPreserveError("DTD/entity declarations are not accepted")
    try:
        return ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise CanvasPreserveError(f"invalid main.xml: {exc}") from exc


def _id_map(root: ET.Element) -> dict[str, ET.Element]:
    result: dict[str, ET.Element] = {}
    for node in root.iter():
        serialized_id = node.get("xs.id")
        if serialized_id is None:
            continue
        if serialized_id in result:
            raise CanvasPreserveError(f"duplicate xs.id {serialized_id!r}")
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
        raise CanvasPreserveError(
            f"{source.tag} {source.get('xs.id')!r} has {len(matches)} "
            f"{tag}[xs.n={serialized_name!r}] fields"
        )
    return matches[0]


def _one_direct_named(
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
        raise CanvasPreserveError(
            f"{source.tag} {source.get('xs.id')!r} has {len(matches)} direct "
            f"{tag}[xs.n={serialized_name!r}] fields"
        )
    return matches[0]


def _float_values(node: ET.Element, label: str) -> tuple[float, ...]:
    try:
        values = tuple(float(item) for item in (node.text or "").split())
    except ValueError as exc:
        raise CanvasPreserveError(f"{label} has invalid floats") from exc
    count = node.get("count")
    if count is None or not count.isdigit() or int(count) != len(values):
        raise CanvasPreserveError(f"{label} count differs from payload")
    if len(values) % 2 or not all(math.isfinite(value) for value in values):
        raise CanvasPreserveError(f"{label} is odd-length or non-finite")
    return values


def _bounds(values: Sequence[float]) -> dict[str, float]:
    return {
        "min_x": min(values[0::2]),
        "max_x": max(values[0::2]),
        "min_y": min(values[1::2]),
        "max_y": max(values[1::2]),
    }


def _maximum_error(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise CanvasPreserveError("cannot compare coordinate arrays of unequal size")
    return max((abs(a - b) for a, b in zip(left, right)), default=0.0)


class GeometryModel:
    def __init__(self, main_xml: bytes, tolerance: float) -> None:
        self.main_xml = main_xml
        self.root = _parse_xml(main_xml)
        self.ids = _id_map(self.root)
        self.tolerance = tolerance
        self.objects = safe._semantic_objects(main_xml)
        safe._validate_deformer_graph(self.objects)
        self.by_guid_ref = {item.guid_ref: item for item in self.objects}
        self.sources = {
            item.source_ref: self.ids[item.source_ref]
            for item in self.objects
        }
        self.deformer_source_by_guid = {
            item.guid_ref: self.sources[item.source_ref]
            for item in self.objects
            if item.object_type in DEFORMER_TYPES
        }
        self.inline_parent_guids: dict[str, tuple[str, str | None]] = {}
        for item in self.objects:
            if not item.parent_ref.startswith(safe.INLINE_PARENT_REF_PREFIX):
                continue
            previous = self.inline_parent_guids.setdefault(
                item.parent_ref,
                (item.parent_uuid, item.parent_note),
            )
            if previous != (item.parent_uuid, item.parent_note):
                raise CanvasPreserveError(
                    f"inconsistent inline parent GUID {item.parent_ref!r}"
                )
            if item.parent_note != ROOT_NOTE:
                raise CanvasPreserveError(
                    f"inline parent GUID {item.parent_ref!r} is not ROOT"
                )
        self.transform_cache: dict[str, NeutralTransform] = {}

    def resolve(
        self,
        *,
        object_type: str,
        name: str,
        guid_uuid: str,
        label: str,
    ) -> safe.SemanticObject:
        return safe._resolve_semantic_object(
            self.objects,
            object_type=object_type,
            name=name,
            guid_uuid=guid_uuid,
            label=label,
        )

    def source(self, item: safe.SemanticObject) -> ET.Element:
        return self.sources[item.source_ref]

    def keyform_positions(
        self,
        item: safe.SemanticObject,
        *,
        require_single_unbound: bool,
    ) -> tuple[ET.Element, tuple[float, ...]]:
        source = self.source(item)
        grid_node = _one_named(source, "KeyformGridSource", "keyformGridSource")
        grid = self.ids.get(grid_node.get("xs.ref"), grid_node)
        keyforms_on_grid = _one_direct_named(
            grid,
            "array_list",
            "keyformsOnGrid",
        )
        bindings = _one_direct_named(grid, "array_list", "keyformBindings")
        forms = _one_direct_named(source, "carray_list", "keyforms")
        if require_single_unbound:
            if (
                keyforms_on_grid.get("count") != "1"
                or len(keyforms_on_grid) != 1
                or bindings.get("count") != "0"
                or len(bindings) != 0
                or forms.get("count") != "1"
                or len(forms) != 1
            ):
                raise CanvasPreserveError(
                    f"{item.name!r} is not exactly one-keyform and unbound"
                )
        if len(forms) != 1:
            raise CanvasPreserveError(
                f"{item.name!r} does not have exactly one form"
            )
        form = forms[0]
        position_node = _one_direct_named(form, "float-array", "positions")
        return position_node, _float_values(
            position_node,
            f"{item.name} keyform positions",
        )

    def original_canvas(
        self,
        item: safe.SemanticObject,
    ) -> tuple[float, ...]:
        source = self.source(item)
        if item.object_type == "art-mesh":
            return _float_values(
                _one_direct_named(source, "float-array", "positions"),
                f"{item.name} immutable ArtMesh positions",
            )
        original_extensions = list(
            source.iter("CDeformerOriginalShapeExtension")
        )
        if len(original_extensions) != 1:
            raise CanvasPreserveError(
                f"{item.name!r} lacks one original-shape extension"
            )
        refs = {
            node.get("xs.ref")
            for node in original_extensions[0].iter("float-array")
            if node.get("xs.n") == "positions"
        }
        if len(refs) != 1 or None in refs:
            raise CanvasPreserveError(
                f"{item.name!r} original shape does not use one shared array"
            )
        definition = self.ids.get(next(iter(refs)))
        if definition is None or definition.tag != "float-array":
            raise CanvasPreserveError(
                f"{item.name!r} original position array is unresolved"
            )
        return _float_values(definition, f"{item.name} original canvas positions")

    def transform(self, guid_ref: str) -> NeutralTransform:
        cached = self.transform_cache.get(guid_ref)
        if cached is not None:
            return cached
        inline_parent = self.inline_parent_guids.get(guid_ref)
        if inline_parent is not None:
            guid_uuid, _ = inline_parent
            result = IdentityTransform(guid_ref, guid_uuid)
            self.transform_cache[guid_ref] = result
            return result
        definition = self.ids.get(guid_ref)
        if definition is None or definition.tag != "CDeformerGuid":
            raise CanvasPreserveError(
                f"deformer parent reference {guid_ref!r} is unresolved"
            )
        item = self.by_guid_ref.get(guid_ref)
        if item is None:
            guid_uuid = _canonical_uuid(
                definition.get("uuid"),
                f"root sentinel {guid_ref}",
            )
            if definition.get("note") != ROOT_NOTE:
                raise CanvasPreserveError(
                    f"non-object deformer GUID {guid_ref!r} is not ROOT"
                )
            result = IdentityTransform(guid_ref, guid_uuid)
            self.transform_cache[guid_ref] = result
            return result

        source = self.source(item)
        if item.object_type == "rotation-deformer":
            forms = _one_direct_named(source, "carray_list", "keyforms")
            if forms.get("count") != "1" or len(forms) != 1:
                raise CanvasPreserveError(
                    f"rotation {item.name!r} does not have one neutral form"
                )
            form = forms[0]
            if (
                float(form.get("angle", "nan")) != 0.0
                or float(form.get("scale", "nan")) != 1.0
                or form.get("isReflectX") != "false"
                or form.get("isReflectY") != "false"
            ):
                raise CanvasPreserveError(
                    f"rotation {item.name!r} is not identity at neutral"
                )
            pivot = self.original_canvas(item)
            if len(pivot) != 2:
                raise CanvasPreserveError(
                    f"rotation {item.name!r} original pivot is not one point"
                )
            result = RotationTransform(
                guid_ref=guid_ref,
                name=item.name,
                pivot_x=pivot[0],
                pivot_y=pivot[1],
            )
            self.transform_cache[guid_ref] = result
            return result

        if item.object_type != "warp-deformer":
            raise CanvasPreserveError(
                f"parent {item.name!r} is not a supported deformer"
            )
        columns = int(_one_direct_named(source, "i", "col").text or "0")
        rows = int(_one_direct_named(source, "i", "row").text or "0")
        if columns <= 0 or rows <= 0:
            raise CanvasPreserveError(f"warp {item.name!r} has invalid divisions")
        parent_node = _one_named(
            source,
            "CDeformerGuid",
            "targetDeformerGuid",
        )
        parent_ref = parent_node.get("xs.ref")
        if not parent_ref:
            parent_uuid = _canonical_uuid(
                parent_node.get("uuid"),
                f"inline parent GUID for {item.name}",
            )
            if parent_node.get("note") != ROOT_NOTE:
                raise CanvasPreserveError(
                    f"inline parent of warp {item.name!r} is not ROOT"
                )
            parent_ref = safe.INLINE_PARENT_REF_PREFIX + parent_uuid
            expected_inline = self.inline_parent_guids.get(parent_ref)
            if expected_inline != (parent_uuid, ROOT_NOTE):
                raise CanvasPreserveError(
                    f"inline parent of warp {item.name!r} is inconsistent"
                )
        parent_transform = self.transform(parent_ref)
        original = self.original_canvas(item)
        expected_count = 2 * (columns + 1) * (rows + 1)
        if len(original) != expected_count:
            raise CanvasPreserveError(
                f"warp {item.name!r} original grid has {len(original)} values; "
                f"expected {expected_count}"
            )
        forms = _one_direct_named(source, "carray_list", "keyforms")
        candidates: list[tuple[float, int, tuple[float, ...]]] = []
        for index, form in enumerate(forms):
            positions = _float_values(
                _one_direct_named(form, "float-array", "positions"),
                f"{item.name} form {index}",
            )
            if len(positions) != expected_count:
                raise CanvasPreserveError(
                    f"warp {item.name!r} form {index} has wrong grid size"
                )
            reconstructed = self.forward_many(parent_transform, positions)
            candidates.append(
                (_maximum_error(reconstructed, original), index, positions)
            )
        candidates.sort(key=lambda candidate: (candidate[0], candidate[1]))
        matches = [
            candidate
            for candidate in candidates
            if candidate[0] < self.tolerance
        ]
        if len(matches) != 1:
            raise CanvasPreserveError(
                f"warp {item.name!r} has {len(matches)} neutral-form matches "
                f"below {self.tolerance}px"
            )
        error, index, neutral = matches[0]
        result = WarpTransform(
            guid_ref=guid_ref,
            name=item.name,
            columns=columns,
            rows=rows,
            neutral_positions=neutral,
            neutral_keyform_index=index,
            neutral_match_error_px=error,
            parent=parent_transform,
        )
        self.transform_cache[guid_ref] = result
        return result

    @staticmethod
    def _grid_point(
        transform: WarpTransform,
        column: int,
        row: int,
    ) -> tuple[float, float]:
        index = 2 * (row * (transform.columns + 1) + column)
        return (
            transform.neutral_positions[index],
            transform.neutral_positions[index + 1],
        )

    def forward(
        self,
        transform: NeutralTransform,
        point: tuple[float, float],
    ) -> tuple[float, float]:
        if isinstance(transform, IdentityTransform):
            return point
        if isinstance(transform, RotationTransform):
            return (
                transform.pivot_x + point[0],
                transform.pivot_y + point[1],
            )
        u, v = point
        scaled_u = u * transform.columns
        scaled_v = v * transform.rows
        column = min(
            transform.columns - 1,
            max(0, math.floor(scaled_u)),
        )
        row = min(
            transform.rows - 1,
            max(0, math.floor(scaled_v)),
        )
        local_u = scaled_u - column
        local_v = scaled_v - row
        p00 = self._grid_point(transform, column, row)
        p10 = self._grid_point(transform, column + 1, row)
        p01 = self._grid_point(transform, column, row + 1)
        p11 = self._grid_point(transform, column + 1, row + 1)
        parent_point = (
            (1 - local_u) * (1 - local_v) * p00[0]
            + local_u * (1 - local_v) * p10[0]
            + (1 - local_u) * local_v * p01[0]
            + local_u * local_v * p11[0],
            (1 - local_u) * (1 - local_v) * p00[1]
            + local_u * (1 - local_v) * p10[1]
            + (1 - local_u) * local_v * p01[1]
            + local_u * local_v * p11[1],
        )
        return self.forward(transform.parent, parent_point)

    def forward_many(
        self,
        transform: NeutralTransform,
        values: Sequence[float],
    ) -> tuple[float, ...]:
        result: list[float] = []
        for x, y in zip(values[0::2], values[1::2]):
            result.extend(self.forward(transform, (x, y)))
        return tuple(result)

    def _inverse_warp_cell(
        self,
        transform: WarpTransform,
        point: tuple[float, float],
    ) -> tuple[float, float, float]:
        best: tuple[float, float, float] | None = None
        for row in range(transform.rows):
            for column in range(transform.columns):
                p00 = self._grid_point(transform, column, row)
                p10 = self._grid_point(transform, column + 1, row)
                p01 = self._grid_point(transform, column, row + 1)
                p11 = self._grid_point(transform, column + 1, row + 1)
                local_u = 0.5
                local_v = 0.5
                for _ in range(24):
                    x = (
                        (1 - local_u) * (1 - local_v) * p00[0]
                        + local_u * (1 - local_v) * p10[0]
                        + (1 - local_u) * local_v * p01[0]
                        + local_u * local_v * p11[0]
                    )
                    y = (
                        (1 - local_u) * (1 - local_v) * p00[1]
                        + local_u * (1 - local_v) * p10[1]
                        + (1 - local_u) * local_v * p01[1]
                        + local_u * local_v * p11[1]
                    )
                    residual_x = x - point[0]
                    residual_y = y - point[1]
                    derivative_u_x = (
                        (1 - local_v) * (p10[0] - p00[0])
                        + local_v * (p11[0] - p01[0])
                    )
                    derivative_u_y = (
                        (1 - local_v) * (p10[1] - p00[1])
                        + local_v * (p11[1] - p01[1])
                    )
                    derivative_v_x = (
                        (1 - local_u) * (p01[0] - p00[0])
                        + local_u * (p11[0] - p10[0])
                    )
                    derivative_v_y = (
                        (1 - local_u) * (p01[1] - p00[1])
                        + local_u * (p11[1] - p10[1])
                    )
                    determinant = (
                        derivative_u_x * derivative_v_y
                        - derivative_v_x * derivative_u_y
                    )
                    if abs(determinant) < 1e-12:
                        break
                    delta_u = (
                        residual_x * derivative_v_y
                        - residual_y * derivative_v_x
                    ) / determinant
                    delta_v = (
                        derivative_u_x * residual_y
                        - derivative_u_y * residual_x
                    ) / determinant
                    local_u -= delta_u
                    local_v -= delta_v
                    if max(abs(delta_u), abs(delta_v)) < 1e-12:
                        break
                x = (
                    (1 - local_u) * (1 - local_v) * p00[0]
                    + local_u * (1 - local_v) * p10[0]
                    + (1 - local_u) * local_v * p01[0]
                    + local_u * local_v * p11[0]
                )
                y = (
                    (1 - local_u) * (1 - local_v) * p00[1]
                    + local_u * (1 - local_v) * p10[1]
                    + (1 - local_u) * local_v * p01[1]
                    + local_u * local_v * p11[1]
                )
                error = math.hypot(x - point[0], y - point[1])
                outside = max(
                    0.0,
                    -local_u,
                    local_u - 1.0,
                    -local_v,
                    local_v - 1.0,
                )
                if outside <= 1e-5 and (best is None or error < best[0]):
                    best = (
                        error,
                        (column + local_u) / transform.columns,
                        (row + local_v) / transform.rows,
                    )
        if best is None or best[0] >= self.tolerance:
            raise CanvasPreserveError(
                f"cannot invert warp {transform.name!r} within "
                f"{self.tolerance}px"
            )
        return best

    def inverse(
        self,
        transform: NeutralTransform,
        point: tuple[float, float],
    ) -> tuple[float, float]:
        if isinstance(transform, IdentityTransform):
            return point
        if isinstance(transform, RotationTransform):
            return (
                point[0] - transform.pivot_x,
                point[1] - transform.pivot_y,
            )
        parent_point = self.inverse(transform.parent, point)
        _, u, v = self._inverse_warp_cell(transform, parent_point)
        return (u, v)

    def inverse_many(
        self,
        transform: NeutralTransform,
        values: Sequence[float],
    ) -> tuple[float, ...]:
        result: list[float] = []
        for x, y in zip(values[0::2], values[1::2]):
            result.extend(self.inverse(transform, (x, y)))
        return tuple(result)


def _patch_keyform_positions(
    main_xml: bytes,
    *,
    target: safe.SemanticObject,
    old_values: Sequence[float],
    new_values: Sequence[float],
) -> tuple[bytes, dict[str, Any]]:
    block_start, block_end, source_block = safe._source_block_span(
        main_xml,
        target,
    )
    source = ET.fromstring(source_block)
    keyform_lists = [
        node
        for node in source
        if node.tag == "carray_list" and node.get("xs.n") == "keyforms"
    ]
    if len(keyform_lists) != 1 or len(keyform_lists[0]) != 1:
        raise CanvasPreserveError(
            f"{target.name!r} serialized source lacks one keyform list/form"
        )
    form = keyform_lists[0][0]
    if list(form.iter("carray_list")):
        raise CanvasPreserveError(
            f"{target.name!r} keyform contains nested carray_list fields"
        )
    position_node = _one_direct_named(form, "float-array", "positions")
    parsed_old = _float_values(position_node, f"{target.name} serialized keyform")
    if len(parsed_old) != len(old_values) or any(
        _float32(a) != _float32(b)
        for a, b in zip(parsed_old, old_values)
    ):
        raise CanvasPreserveError(
            f"{target.name!r} serialized keyform differs from the plan"
        )
    if len(new_values) != len(old_values):
        raise CanvasPreserveError(
            f"{target.name!r} replacement coordinate count changed"
        )

    keyforms_openings = list(
        re.finditer(
            rb'<carray_list\b(?=[^>]*\bxs\.n="keyforms")[^>]*>',
            source_block,
        )
    )
    if len(keyforms_openings) != 1:
        raise CanvasPreserveError(
            f"{target.name!r} keyform list is not uniquely patchable"
        )
    list_start = keyforms_openings[0].start()
    list_end_token = b"</carray_list>"
    list_close = source_block.find(list_end_token, keyforms_openings[0].end())
    if list_close < 0:
        raise CanvasPreserveError(f"{target.name!r} keyform list is not closed")
    list_end = list_close + len(list_end_token)
    list_block = source_block[list_start:list_end]
    position_matches = list(
        re.finditer(
            rb'(<float-array\b(?=[^>]*\bxs\.n="positions")'
            rb'(?=[^>]*\bcount="\d+")[^>]*>)([^<]*)(</float-array>)',
            list_block,
        )
    )
    if len(position_matches) != 1:
        raise CanvasPreserveError(
            f"{target.name!r} keyform positions are not uniquely patchable"
        )
    match = position_matches[0]
    old_payload = match.group(2)
    serialized_old_values = tuple(
        float(value) for value in old_payload.decode("ascii").split()
    )
    if len(serialized_old_values) != len(old_values) or any(
        _float32(a) != _float32(b)
        for a, b in zip(serialized_old_values, old_values)
    ):
        raise CanvasPreserveError(
            f"{target.name!r} raw keyform payload differs from parsed values"
        )
    new_payload = " ".join(
        _format_float32(value) for value in new_values
    ).encode("ascii")
    patched_list = (
        list_block[: match.start(2)]
        + new_payload
        + list_block[match.end(2) :]
    )
    patched_source = (
        source_block[:list_start]
        + patched_list
        + source_block[list_end:]
    )
    patched = (
        main_xml[:block_start]
        + patched_source
        + main_xml[block_end:]
    )
    return patched, {
        "field": "carray_list[keyforms]/form/float-array[positions]/text()",
        "source_ref": target.source_ref,
        "object_guid": target.guid_uuid,
        "coordinate_count": len(new_values),
        "old_payload_sha256": _sha256(old_payload),
        "new_payload_sha256": _sha256(new_payload),
        "old_local_bounds": _bounds(old_values),
        "new_local_bounds": _bounds(new_values),
    }


def _integrity(root: ET.Element) -> dict[str, Any]:
    ids: set[str] = set()
    indices: set[str] = set()
    uuids: set[str] = set()
    references = 0
    for node in root.iter():
        serialized_id = node.get("xs.id")
        if serialized_id is not None:
            if serialized_id in ids:
                raise CanvasPreserveError(f"duplicate xs.id {serialized_id!r}")
            ids.add(serialized_id)
        serialized_index = node.get("xs.idx")
        if serialized_index is not None:
            if serialized_index in indices:
                raise CanvasPreserveError(
                    f"duplicate xs.idx {serialized_index!r}"
                )
            indices.add(serialized_index)
        raw_uuid = node.get("uuid")
        if raw_uuid is not None:
            canonical = _canonical_uuid(raw_uuid, "serialized UUID")
            if canonical in uuids:
                raise CanvasPreserveError(f"duplicate UUID {canonical!r}")
            uuids.add(canonical)
        reference = node.get("xs.ref")
        if reference is not None:
            references += 1
            if reference not in ids:
                # IDs may be defined later; final pass below handles that case.
                pass
    unresolved = [
        node.get("xs.ref")
        for node in root.iter()
        if node.get("xs.ref") is not None and node.get("xs.ref") not in ids
    ]
    if unresolved:
        raise CanvasPreserveError(
            f"unresolved xs.ref values: {sorted(set(unresolved))[:10]}"
        )
    return {
        "xs_id_count": len(ids),
        "xs_idx_count": len(indices),
        "uuid_count": len(uuids),
        "xs_ref_count": references,
        "all_unique_and_resolved": True,
    }


def _assert_children(
    model: GeometryModel,
    assertions: list[dict[str, Any]],
    *,
    require_declared_names: bool,
) -> list[dict[str, Any]]:
    def resolve_assertion_identity(
        spec: dict[str, str],
        label: str,
    ) -> safe.SemanticObject:
        matches = [
            item
            for item in model.objects
            if item.object_type == spec["type"]
            and item.guid_uuid == spec["uuid"]
        ]
        if len(matches) != 1:
            raise CanvasPreserveError(
                f"{label} identity does not resolve uniquely"
            )
        item = matches[0]
        if require_declared_names and item.name != spec["old_name"]:
            raise CanvasPreserveError(
                f"{label} name {item.name!r} differs from "
                f"{spec['old_name']!r}"
            )
        return item

    result: list[dict[str, Any]] = []
    for assertion in assertions:
        parent_spec = assertion["parent"]
        parent = resolve_assertion_identity(
            parent_spec,
            f"assertion {assertion['id']} parent",
        )
        expected = {
            resolve_assertion_identity(
                child,
                f"assertion {assertion['id']} child",
            ).guid_uuid
            for child in assertion["children"]
        }
        actual = {
            item.guid_uuid
            for item in model.objects
            if item.parent_ref == parent.guid_ref
        }
        if actual != expected:
            raise CanvasPreserveError(
                f"assertion {assertion['id']!r} child set differs"
            )
        result.append(
            {
                "id": assertion["id"],
                "parent_uuid": parent.guid_uuid,
                "parent_name": parent.name,
                "child_uuids": sorted(actual),
                "exact_child_set": True,
            }
        )
    return result


def _coordinate_target_snapshots(
    model: GeometryModel,
    targets: Sequence[safe.SemanticObject],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for target in targets:
        _, keyform = model.keyform_positions(
            target,
            require_single_unbound=True,
        )
        original = model.original_canvas(target)
        result[target.guid_uuid] = {
            "name": target.name,
            "parent_ref": target.parent_ref,
            "original_canvas": original,
            "keyform": keyform,
        }
    return result


def _run(
    manifest_path: Path,
    source_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    manifest, operations, assertions, manifest_bytes = _load_manifest(
        manifest_path
    )
    source_path = source_path.resolve(strict=True)
    output_path = output_path.resolve(strict=False)
    if source_path.name != manifest["source"]["required_filename"]:
        raise CanvasPreserveError("source filename differs from manifest")
    if output_path.name != manifest["output"]["required_filename"]:
        raise CanvasPreserveError("output filename differs from manifest")
    if source_path == output_path:
        raise CanvasPreserveError("source and output resolve to the same path")
    if output_path.exists():
        raise CanvasPreserveError("output already exists; refusing overwrite")
    if not output_path.parent.is_dir():
        raise CanvasPreserveError("output directory does not exist")

    source_data = source_path.read_bytes()
    source_sha = _sha256(source_data)
    if source_sha != manifest["source"]["sha256"]:
        raise CanvasPreserveError(
            f"source SHA-256 {source_sha} differs from manifest"
        )
    (
        archive_before,
        _,
        _,
        source_zip,
        main_before,
    ) = safe._validate_surgical_layout(source_data)
    tolerance = float(
        manifest["coordinate_contract"]["max_reconstruction_error_px"]
    )
    model_before = GeometryModel(main_before, tolerance)
    integrity_before = _integrity(model_before.root)
    child_assertions_before = _assert_children(
        model_before,
        assertions,
        require_declared_names=True,
    )

    resolved: list[
        tuple[Operation, safe.SemanticObject, safe.SemanticObject | None]
    ] = []
    reparent_targets: list[safe.SemanticObject] = []
    final_names = {item.guid_uuid: item.name for item in model_before.objects}
    final_parents = {
        item.guid_uuid: item.parent_uuid for item in model_before.objects
    }
    for operation in operations:
        target = model_before.resolve(
            object_type=operation.target_type,
            name=operation.target_name,
            guid_uuid=operation.target_uuid,
            label=f"operation {operation.operation_id} target",
        )
        if target.parent_uuid != operation.old_parent_uuid:
            raise CanvasPreserveError(
                f"operation {operation.operation_id!r} old parent differs"
            )
        parent: safe.SemanticObject | None = None
        if operation.kind == "reparent-preserve-canvas":
            assert (
                operation.new_parent_type
                and operation.new_parent_name
                and operation.new_parent_uuid
            )
            parent = model_before.resolve(
                object_type=operation.new_parent_type,
                name=operation.new_parent_name,
                guid_uuid=operation.new_parent_uuid,
                label=f"operation {operation.operation_id} parent",
            )
            if parent.guid_ref == target.parent_ref:
                raise CanvasPreserveError(
                    f"operation {operation.operation_id!r} is a parent no-op"
                )
            final_parents[target.guid_uuid] = parent.guid_uuid
            reparent_targets.append(target)
        else:
            assert operation.new_name is not None
            if operation.new_name == target.name:
                raise CanvasPreserveError(
                    f"operation {operation.operation_id!r} is a rename no-op"
                )
            if any(
                item.guid_uuid != target.guid_uuid
                and item.name == operation.new_name
                for item in model_before.objects
            ):
                raise CanvasPreserveError(
                    f"new name {operation.new_name!r} collides"
                )
            final_names[target.guid_uuid] = operation.new_name
        resolved.append((operation, target, parent))

    # Validate the planned graph using serialized references.
    planned_parent_refs = {
        item.guid_ref: item.parent_ref for item in model_before.objects
    }
    for operation, target, parent in resolved:
        if operation.kind == "reparent-preserve-canvas":
            assert parent is not None
            planned_parent_refs[target.guid_ref] = parent.guid_ref
    safe._validate_planned_deformer_graph(
        model_before.objects,
        planned_parent_refs,
    )

    snapshots_before = _coordinate_target_snapshots(
        model_before,
        reparent_targets,
    )
    current_xml = main_before
    whitelist: list[dict[str, Any]] = []
    coordinate_proof: list[dict[str, Any]] = []
    for operation, target, parent in resolved:
        if operation.kind == "rename":
            assert operation.new_name is not None
            patched, record = safe._patch_name_for_record(
                current_xml,
                target=target,
                expected_old_name=target.name,
                new_name=operation.new_name,
            )
            record.update(
                {
                    "operation_id": operation.operation_id,
                    "operation": "rename",
                    "main_xml_sha256_before_step": _sha256(current_xml),
                    "main_xml_sha256_after_step": _sha256(patched),
                }
            )
            whitelist.append(record)
            current_xml = patched
            continue

        assert parent is not None
        _, old_local = model_before.keyform_positions(
            target,
            require_single_unbound=True,
        )
        original_canvas = model_before.original_canvas(target)
        if len(old_local) != len(original_canvas):
            raise CanvasPreserveError(
                f"{target.name!r} keyform/original coordinate count differs"
            )
        old_transform = model_before.transform(target.parent_ref)
        new_transform = model_before.transform(parent.guid_ref)
        reconstructed_before = model_before.forward_many(
            old_transform,
            old_local,
        )
        before_error = _maximum_error(
            reconstructed_before,
            original_canvas,
        )
        if before_error >= tolerance:
            raise CanvasPreserveError(
                f"{target.name!r} source neutral reconstruction error "
                f"{before_error}px exceeds tolerance"
            )
        exact_new_local = model_before.inverse_many(
            new_transform,
            original_canvas,
        )
        new_local = tuple(_float32(value) for value in exact_new_local)
        reconstructed_after = model_before.forward_many(
            new_transform,
            new_local,
        )
        after_error = _maximum_error(
            reconstructed_after,
            original_canvas,
        )
        if after_error >= tolerance:
            raise CanvasPreserveError(
                f"{target.name!r} output neutral reconstruction error "
                f"{after_error}px exceeds tolerance"
            )

        before_step_sha = _sha256(current_xml)
        parent_patched, parent_record = safe._patch_parent_ref_for_record(
            current_xml,
            target=target,
            expected_old_ref=target.parent_ref,
            new_parent=parent,
        )
        positions_patched, position_record = _patch_keyform_positions(
            parent_patched,
            target=target,
            old_values=old_local,
            new_values=new_local,
        )
        after_step_sha = _sha256(positions_patched)
        parent_record.update(
            {
                "operation_id": operation.operation_id,
                "operation": "reparent-preserve-canvas",
                "main_xml_sha256_before_step": before_step_sha,
                "main_xml_sha256_after_parent_step": _sha256(parent_patched),
            }
        )
        position_record.update(
            {
                "operation_id": operation.operation_id,
                "operation": "convert-local-keyform",
                "main_xml_sha256_before_step": _sha256(parent_patched),
                "main_xml_sha256_after_step": after_step_sha,
            }
        )
        whitelist.extend([parent_record, position_record])
        coordinate_proof.append(
            {
                "operation_id": operation.operation_id,
                "object_type": target.object_type,
                "object_name_before": target.name,
                "object_uuid": target.guid_uuid,
                "old_parent_uuid": target.parent_uuid,
                "new_parent_name": parent.name,
                "new_parent_uuid": parent.guid_uuid,
                "keyforms": 1,
                "bindings": 0,
                "coordinate_count": len(new_local),
                "original_canvas_bounds": _bounds(original_canvas),
                "old_local_bounds": _bounds(old_local),
                "new_local_bounds": _bounds(new_local),
                "max_reconstruction_error_before_px": before_error,
                "max_reconstruction_error_after_float32_px": after_error,
                "within_tolerance": True,
            }
        )
        current_xml = positions_patched

    model_after_memory = GeometryModel(current_xml, tolerance)
    integrity_after_memory = _integrity(model_after_memory.root)
    after_by_uuid = {
        item.guid_uuid: item for item in model_after_memory.objects
    }
    before_by_uuid = {
        item.guid_uuid: item for item in model_before.objects
    }
    if set(after_by_uuid) != set(before_by_uuid):
        raise CanvasPreserveError("object UUID set changed")
    for guid_uuid, before in before_by_uuid.items():
        after = after_by_uuid[guid_uuid]
        if (
            after.object_type != before.object_type
            or after.source_ref != before.source_ref
            or after.guid_ref != before.guid_ref
        ):
            raise CanvasPreserveError(
                f"immutable identity changed for {before.name!r}"
            )
        if after.name != final_names[guid_uuid]:
            raise CanvasPreserveError(f"name delta differs for {before.name!r}")
        if after.parent_uuid != final_parents[guid_uuid]:
            raise CanvasPreserveError(
                f"parent delta differs for {before.name!r}"
            )
    safe._validate_deformer_graph(model_after_memory.objects)

    # Immutable canvas originals must stay byte/float identical; only local
    # keyforms may change for the seven declared targets.
    target_guids = {target.guid_uuid for target in reparent_targets}
    snapshots_after = _coordinate_target_snapshots(
        model_after_memory,
        [after_by_uuid[target.guid_uuid] for target in reparent_targets],
    )
    for guid_uuid in target_guids:
        if (
            snapshots_after[guid_uuid]["original_canvas"]
            != snapshots_before[guid_uuid]["original_canvas"]
        ):
            raise CanvasPreserveError(
                f"immutable original canvas changed for {guid_uuid}"
            )
    child_assertions_after_memory = _assert_children(
        model_after_memory,
        assertions,
        require_declared_names=False,
    )

    output_data = safe._replace_main_xml(source_data, current_xml)
    # Complete in-memory archive and inventory validation before writing.
    archive_after_memory, _, _, _, decoded_after = safe._validate_surgical_layout(
        output_data
    )
    if decoded_after != current_xml:
        raise CanvasPreserveError("in-memory output main.xml differs")
    archive_proof = safe._compare_entry_preservation(
        source_data,
        archive_before,
        output_data,
        archive_after_memory,
        main_may_change=True,
    )

    safe._write_new_file(output_path, output_data)
    try:
        source_after = source_path.read_bytes()
        if source_after != source_data:
            raise CanvasPreserveError("source changed during operation")
        written = output_path.read_bytes()
        if written != output_data:
            raise CanvasPreserveError("written output differs from plan")
        _, _, _, _, written_main = safe._validate_surgical_layout(written)
        model_written = GeometryModel(written_main, tolerance)
        integrity_written = _integrity(model_written.root)
        child_assertions_written = _assert_children(
            model_written,
            assertions,
            require_declared_names=False,
        )
        source_inventory = safe._structural_inventory(source_path)
        output_inventory = safe._structural_inventory(output_path)
        if source_inventory["counts"] != output_inventory["counts"]:
            raise CanvasPreserveError("structural counts changed")
        if source_inventory["parameter_ids"] != output_inventory["parameter_ids"]:
            raise CanvasPreserveError("parameter IDs changed")
        if source_inventory["bound_objects"] != output_inventory["bound_objects"]:
            raise CanvasPreserveError("parameter bindings changed")
        expected_warp_names = [
            final_names[item.guid_uuid]
            for item in model_before.objects
            if item.object_type == "warp-deformer"
        ]
        expected_rotation_names = [
            final_names[item.guid_uuid]
            for item in model_before.objects
            if item.object_type == "rotation-deformer"
        ]
        if output_inventory["warp_deformer_names"] != expected_warp_names:
            raise CanvasPreserveError("warp name inventory differs")
        if output_inventory["rotation_deformer_names"] != expected_rotation_names:
            raise CanvasPreserveError("rotation name inventory differs")
    except Exception:
        if output_path.exists():
            output_path.unlink()
        raise

    return {
        "status": "ok",
        "operation": "apply-neutral-canvas-preserving-manifest",
        "transaction_id": manifest["transaction_id"],
        "manifest": str(manifest_path.resolve(strict=True)),
        "manifest_sha256": _sha256(manifest_bytes),
        "source": str(source_path),
        "source_bytes": len(source_data),
        "source_sha256_before": source_sha,
        "source_sha256_after": _sha256(source_after),
        "source_unchanged": source_after == source_data,
        "output": str(output_path),
        "output_bytes": len(written),
        "output_sha256": _sha256(written),
        "main_xml_bytes_before": len(main_before),
        "main_xml_bytes_after": len(written_main),
        "main_xml_sha256_before": _sha256(main_before),
        "main_xml_sha256_after": _sha256(written_main),
        "coordinate_contract": manifest["coordinate_contract"],
        "coordinate_proof": coordinate_proof,
        "whitelist": whitelist,
        "whitelist_field_count": len(whitelist),
        "assertions_before": child_assertions_before,
        "assertions_after_memory": child_assertions_after_memory,
        "assertions_after_written": child_assertions_written,
        "integrity_before": integrity_before,
        "integrity_after_memory": integrity_after_memory,
        "integrity_after_written": integrity_written,
        "archive": archive_proof,
        "compression_profile": {
            "source_zlib_level": source_zip.zlib_level,
            "python_zlib_runtime": safe.zlib.ZLIB_RUNTIME_VERSION,
        },
        "structural_inventory": output_inventory,
        "cubism_validation": "PENDING",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Apply a strict neutral-canvas-preserving manifest to a new TEST CMO3."
        )
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = _run(args.manifest, args.source, args.output)
    except (
        CanvasPreserveError,
        safe.SafeWriteError,
        OSError,
        ValueError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
