#!/usr/bin/env python3
"""
Read-only inventory for Live2D Cubism Editor .cmo3 files.

The script parses the CAFF archive, extracts the in-memory ``main.xml`` member,
and reports editor-side objects such as ArtMeshes, Parts, deformers, parameters,
keyforms, and parameter bindings. It never writes to the inspected model.

CAFF is an undocumented/proprietary format. The archive parsing implemented
here follows the independently reverse-engineered structure used by the MIT
licensed wader/fq CAFF decoder:
https://github.com/wader/fq/tree/master/format/caff
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import xml.etree.ElementTree as ET
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence


RAW_COMPRESSION = 0x10
KNOWN_COMPRESSIONS = {RAW_COMPRESSION, 0x21, 0x25}
DEFAULT_MAX_XML_BYTES = 256 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 100_000
MAX_STRING_BYTES = 1024 * 1024


class InventoryError(RuntimeError):
    """Raised when an input is malformed or outside the safety limits."""


@dataclass(frozen=True)
class ArchiveEntry:
    path: str
    tag: str
    start: int
    size: int
    obfuscated: bool
    compression: int


class BufferReader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.offset = 0

    def read(self, size: int) -> bytes:
        if size < 0 or self.offset + size > len(self.data):
            raise InventoryError(
                f"unexpected end of file at 0x{self.offset:x} while reading {size} bytes"
            )
        result = self.data[self.offset : self.offset + size]
        self.offset += size
        return result

    def u8(self) -> int:
        return self.read(1)[0]

    def u16be(self) -> int:
        return struct.unpack(">H", self.read(2))[0]

    def u32be(self) -> int:
        return struct.unpack(">I", self.read(4))[0]

    def s32be(self) -> int:
        return struct.unpack(">i", self.read(4))[0]

    def u64be(self) -> int:
        return struct.unpack(">Q", self.read(8))[0]


@dataclass
class CaffArchive:
    data: bytes
    archive_version: tuple[int, int, int]
    format_id: str
    format_version: tuple[int, int, int]
    obfuscation_key_signed: int
    preview: dict[str, int]
    entries: list[ArchiveEntry]

    @classmethod
    def parse(cls, data: bytes) -> "CaffArchive":
        if len(data) < 2 or data[-2:] != b"bc":
            raise InventoryError("invalid CAFF guard bytes")
        reader = BufferReader(data)
        if reader.read(4) != b"CAFF":
            raise InventoryError("not a CAFF archive (missing CAFF signature)")

        archive_version = tuple(reader.read(3))
        format_id_bytes = reader.read(4)
        format_version = tuple(reader.read(3))
        key_signed = reader.s32be()
        key_u32 = key_signed & 0xFFFF_FFFF
        key_low = key_u32 & 0xFF
        key_u64 = ((key_signed << 32) | key_signed) & 0xFFFF_FFFF_FFFF_FFFF

        reader.read(8)  # unused
        preview = {
            "image_format": reader.u8(),
            "color_type": reader.u8(),
            "unused": reader.u16be(),
            "width": reader.u16be(),
            "height": reader.u16be(),
            "start": reader.u64be(),
            "size": reader.u32be(),
        }
        reader.read(8)  # unused

        def obfuscated_u8() -> int:
            return reader.u8() ^ key_low

        def obfuscated_u32() -> int:
            return reader.u32be() ^ key_u32

        def obfuscated_u64() -> int:
            return reader.u64be() ^ key_u64

        def obfuscated_beb128() -> int:
            value = 0
            for _ in range(10):
                byte = obfuscated_u8()
                value = (value << 7) | (byte & 0x7F)
                if byte & 0x80 == 0:
                    return value
            raise InventoryError("invalid or excessively long BEB128 integer")

        def obfuscated_string() -> str:
            length = obfuscated_beb128()
            if length > MAX_STRING_BYTES:
                raise InventoryError(
                    f"archive string length {length} exceeds safety limit"
                )
            raw = reader.read(length)
            try:
                return bytes(byte ^ key_low for byte in raw).decode("utf-8")
            except UnicodeDecodeError as exc:
                raise InventoryError("invalid UTF-8 archive string") from exc

        entry_count = obfuscated_u32()
        if entry_count > MAX_ARCHIVE_ENTRIES:
            raise InventoryError(
                f"archive entry count {entry_count} exceeds safety limit"
            )

        entries: list[ArchiveEntry] = []
        for _ in range(entry_count):
            path = obfuscated_string()
            tag = obfuscated_string()
            start = obfuscated_u64()
            size = obfuscated_u32()
            obfuscated = bool(obfuscated_u8())
            compression = obfuscated_u8()
            reader.read(8)  # unused

            if start > len(data) or size > len(data) - start:
                raise InventoryError(
                    f"entry {path!r} points outside archive: start={start}, size={size}"
                )
            entries.append(
                ArchiveEntry(
                    path=path,
                    tag=tag,
                    start=start,
                    size=size,
                    obfuscated=obfuscated,
                    compression=compression,
                )
            )

        try:
            format_id = format_id_bytes.decode("ascii")
        except UnicodeDecodeError:
            format_id = format_id_bytes.hex()

        return cls(
            data=data,
            archive_version=archive_version,
            format_id=format_id,
            format_version=format_version,
            obfuscation_key_signed=key_signed,
            preview=preview,
            entries=entries,
        )

    def read_entry(self, entry: ArchiveEntry, max_output_bytes: int) -> bytes:
        raw = self.data[entry.start : entry.start + entry.size]
        if entry.obfuscated:
            key_low = (self.obfuscation_key_signed & 0xFFFF_FFFF) & 0xFF
            raw = bytes(byte ^ key_low for byte in raw)

        if entry.compression == RAW_COMPRESSION:
            if len(raw) > max_output_bytes:
                raise InventoryError(
                    f"raw entry {entry.path!r} exceeds {max_output_bytes} bytes"
                )
            return raw

        if entry.compression not in KNOWN_COMPRESSIONS:
            raise InventoryError(
                f"unsupported CAFF compression option 0x{entry.compression:02x}"
            )
        return _inflate_zip_local_entry(raw, max_output_bytes)

    def read_unique_path(self, path: str, max_output_bytes: int) -> bytes:
        matches = [entry for entry in self.entries if entry.path == path]
        if len(matches) != 1:
            raise InventoryError(
                f"expected exactly one {path!r} entry, found {len(matches)}"
            )
        return self.read_entry(matches[0], max_output_bytes)


def _inflate_zip_local_entry(raw: bytes, max_output_bytes: int) -> bytes:
    """Inflate the first ZIP local-file entry while enforcing an output cap."""

    if len(raw) < 30 or raw[:4] != b"PK\x03\x04":
        raise InventoryError("compressed CAFF member lacks a ZIP local-file header")
    compression_method = int.from_bytes(raw[8:10], "little")
    if compression_method != 8:
        raise InventoryError(
            f"unsupported ZIP compression method {compression_method}; expected DEFLATE"
        )
    filename_length = int.from_bytes(raw[26:28], "little")
    extra_length = int.from_bytes(raw[28:30], "little")
    payload_start = 30 + filename_length + extra_length
    if payload_start > len(raw):
        raise InventoryError("truncated ZIP local-file header")

    decompressor = zlib.decompressobj(-zlib.MAX_WBITS)
    output = decompressor.decompress(
        raw[payload_start:], max_output_bytes + 1
    )
    if len(output) > max_output_bytes or decompressor.unconsumed_tail:
        raise InventoryError(
            f"decompressed entry exceeds safety limit of {max_output_bytes} bytes"
        )
    remaining = max_output_bytes + 1 - len(output)
    output += decompressor.flush(remaining)
    if len(output) > max_output_bytes:
        raise InventoryError(
            f"decompressed entry exceeds safety limit of {max_output_bytes} bytes"
        )
    if not decompressor.eof:
        raise InventoryError("truncated DEFLATE stream in CAFF member")
    return output


def _first_named(
    element: ET.Element | None, tag: str, serialized_name: str
) -> ET.Element | None:
    if element is None:
        return None
    return next(
        (
            node
            for node in element.iter(tag)
            if node.get("xs.n") == serialized_name
        ),
        None,
    )


def _named_text(
    element: ET.Element | None, tag: str, serialized_name: str
) -> str | None:
    node = _first_named(element, tag, serialized_name)
    return node.text if node is not None else None


def _resolve(
    element: ET.Element | None, id_map: dict[str, ET.Element]
) -> ET.Element | None:
    if element is None:
        return None
    ref = element.get("xs.ref")
    return id_map.get(ref, element) if ref else element


def _serialized_count(element: ET.Element | None) -> int:
    if element is None:
        return 0
    raw = element.get("count")
    if raw is not None:
        try:
            return int(raw)
        except ValueError:
            pass
    return len(element)


def _source_name(source: ET.Element) -> str:
    return _named_text(source, "s", "localName") or source.get("xs.id") or "<unnamed>"


def _source_guid_ref(source: ET.Element, tag: str) -> str | None:
    node = _first_named(source, tag, "guid")
    return node.get("xs.ref") if node is not None else None


def _target_ref(source: ET.Element, tag: str, name: str) -> str | None:
    node = _first_named(source, tag, name)
    return node.get("xs.ref") if node is not None else None


def _id_string(source: ET.Element, preferred_tags: Sequence[str]) -> str | None:
    for tag in preferred_tags:
        for node in source.iter(tag):
            value = node.get("idstr")
            if value:
                return value
    return None


def _binding_details(
    source: ET.Element,
    id_map: dict[str, ET.Element],
    parameter_by_guid_ref: dict[str, dict[str, Any]],
) -> tuple[int, list[dict[str, Any]]]:
    grid_node = _first_named(source, "KeyformGridSource", "keyformGridSource")
    grid = _resolve(grid_node, id_map)
    if grid is None:
        return 0, []

    keyforms_node = _first_named(grid, "array_list", "keyformsOnGrid")
    keyform_count = _serialized_count(keyforms_node)
    bindings_node = _first_named(grid, "array_list", "keyformBindings")
    if bindings_node is None:
        return keyform_count, []

    bindings: list[dict[str, Any]] = []
    for binding_ref in bindings_node.iter("KeyformBindingSource"):
        binding = _resolve(binding_ref, id_map)
        if binding is None:
            continue
        serialized_binding_ref = binding_ref.get("xs.ref") or binding.get("xs.id")
        parameter_guid = _first_named(binding, "CParameterGuid", "parameterGuid")
        guid_ref = parameter_guid.get("xs.ref") if parameter_guid is not None else None
        parameter = parameter_by_guid_ref.get(guid_ref or "", {})
        keys_node = _first_named(binding, "array_list", "keys")
        keys: list[float | str] = []
        if keys_node is not None:
            for key_node in keys_node.iter("f"):
                if key_node.text is None:
                    continue
                try:
                    keys.append(float(key_node.text))
                except ValueError:
                    keys.append(key_node.text)
        bindings.append(
            {
                "parameter_id": parameter.get("id"),
                "parameter_name": parameter.get("name"),
                "parameter_guid_ref": guid_ref,
                "binding_ref": serialized_binding_ref,
                "keys": keys,
            }
        )
    return keyform_count, bindings


def _parameter_inventory(
    model_source: ET.Element,
    id_map: dict[str, ET.Element],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    source_set = model_source.find("CParameterSourceSet")
    if source_set is None:
        return [], {}

    parameters: list[dict[str, Any]] = []
    by_guid_ref: dict[str, dict[str, Any]] = {}
    for source in source_set.iter("CParameterSource"):
        guid_node = _first_named(source, "CParameterGuid", "guid")
        id_node = _first_named(source, "CParameterId", "id")
        guid_ref = guid_node.get("xs.ref") if guid_node is not None else None
        id_ref = id_node.get("xs.ref") if id_node is not None else None
        id_definition = id_map.get(id_ref or "")

        floats: dict[str, float | str] = {}
        for node in source.iter("f"):
            name = node.get("xs.n")
            if not name or node.text is None:
                continue
            try:
                floats[name] = float(node.text)
            except ValueError:
                floats[name] = node.text

        parameter = {
            "id": id_definition.get("idstr") if id_definition is not None else None,
            "name": _named_text(source, "s", "name"),
            "description": _named_text(source, "s", "description"),
            "guid_ref": guid_ref,
            "minimum": floats.get("minValue"),
            "maximum": floats.get("maxValue"),
            "default": floats.get("defaultValue"),
        }
        parameters.append(parameter)
        if guid_ref:
            by_guid_ref[guid_ref] = parameter
    return parameters, by_guid_ref


def _count_source_set(model_source: ET.Element, tag: str) -> int:
    source_set = model_source.find(tag)
    if source_set is None:
        return 0
    candidates = [
        node
        for node in source_set.iter("carray_list")
        if node.get("xs.n") in {"_sources", "sources", "_settings", "settings"}
    ]
    return _serialized_count(candidates[0]) if candidates else 0


def _object_inventory(
    shared: ET.Element,
    id_map: dict[str, ET.Element],
    parameter_by_guid_ref: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    specs = (
        ("art_meshes", "CArtMeshSource", ("CDrawableId",)),
        ("warp_deformers", "CWarpDeformerSource", ("CDeformerId",)),
        ("rotation_deformers", "CRotationDeformerSource", ("CDeformerId",)),
        ("parts", "CPartSource", ("CPartId",)),
    )
    result: dict[str, list[dict[str, Any]]] = {}

    deformer_name_by_guid: dict[str, str] = {}
    part_name_by_guid: dict[str, str] = {}
    for tag in ("CWarpDeformerSource", "CRotationDeformerSource"):
        for source in shared.findall(tag):
            guid_ref = _source_guid_ref(source, "CDeformerGuid")
            if guid_ref:
                deformer_name_by_guid[guid_ref] = _source_name(source)
    for source in shared.findall("CPartSource"):
        guid_ref = _source_guid_ref(source, "CPartGuid")
        if guid_ref:
            part_name_by_guid[guid_ref] = _source_name(source)

    for output_key, source_tag, id_tags in specs:
        objects: list[dict[str, Any]] = []
        for source in shared.findall(source_tag):
            keyform_count, bindings = _binding_details(
                source, id_map, parameter_by_guid_ref
            )
            parent_deformer_ref = _target_ref(
                source, "CDeformerGuid", "targetDeformerGuid"
            )
            parent_part_ref = _target_ref(source, "CPartGuid", "parentGuid")
            objects.append(
                {
                    "name": _source_name(source),
                    "id": _id_string(source, id_tags),
                    "source_ref": source.get("xs.id"),
                    "parent_deformer": deformer_name_by_guid.get(parent_deformer_ref or ""),
                    "parent_deformer_guid_ref": parent_deformer_ref,
                    "parent_part": part_name_by_guid.get(parent_part_ref or ""),
                    "parent_part_guid_ref": parent_part_ref,
                    "keyforms": keyform_count,
                    "bindings": bindings,
                }
            )
        result[output_key] = objects
    return result


def inventory_file(
    path: Path, max_xml_bytes: int, include_details: bool
) -> dict[str, Any]:
    data = path.read_bytes()
    archive = CaffArchive.parse(data)
    xml_bytes = archive.read_unique_path("main.xml", max_xml_bytes)
    if b"<!DOCTYPE" in xml_bytes[:65536] or b"<!ENTITY" in xml_bytes[:65536]:
        raise InventoryError("XML DTD/entity declarations are not accepted")
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise InventoryError(f"invalid main.xml: {exc}") from exc

    shared = root.find("shared")
    model_source = root.find("main/CModelSource")
    if shared is None or model_source is None:
        raise InventoryError("main.xml lacks expected shared/main/CModelSource nodes")

    id_map = {
        serialized_id: node
        for node in root.iter()
        if (serialized_id := node.get("xs.id")) is not None
    }
    parameters, parameter_by_guid_ref = _parameter_inventory(model_source, id_map)
    objects = _object_inventory(shared, id_map, parameter_by_guid_ref)
    all_objects = (
        objects["art_meshes"]
        + objects["warp_deformers"]
        + objects["rotation_deformers"]
        + objects["parts"]
    )
    used_binding_refs = {
        binding["binding_ref"]
        for obj in all_objects
        for binding in obj["bindings"]
        if binding.get("binding_ref")
    }
    serialized_binding_count = len(shared.findall("KeyformBindingSource"))
    bound_objects = [
        {
            "kind": next(
                kind
                for kind, group in objects.items()
                if any(candidate is obj for candidate in group)
            ),
            "name": obj["name"],
            "keyforms": obj["keyforms"],
            "parameters": [
                binding["parameter_id"] or binding["parameter_name"]
                for binding in obj["bindings"]
            ],
        }
        for obj in all_objects
        if obj["bindings"]
    ]

    main_entry = next(entry for entry in archive.entries if entry.path == "main.xml")
    result: dict[str, Any] = {
        "path": str(path.resolve()),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest().upper(),
        "caff": {
            "archive_version": list(archive.archive_version),
            "format_id": archive.format_id,
            "format_version": list(archive.format_version),
            "entry_count": len(archive.entries),
            "main_xml_compressed_bytes": main_entry.size,
            "main_xml_uncompressed_bytes": len(xml_bytes),
            "preview_width": archive.preview["width"],
            "preview_height": archive.preview["height"],
        },
        "cubism_file_format_version": root.get("fileFormatVersion"),
        "counts": {
            "art_meshes": len(objects["art_meshes"]),
            "warp_deformers": len(objects["warp_deformers"]),
            "rotation_deformers": len(objects["rotation_deformers"]),
            "deformers_total": len(objects["warp_deformers"])
            + len(objects["rotation_deformers"]),
            "parts": len(objects["parts"]),
            "parameters": len(parameters),
            "bound_objects": len(bound_objects),
            "object_parameter_bindings": sum(
                len(obj["bindings"]) for obj in all_objects
            ),
            "serialized_parameter_binding_definitions": serialized_binding_count,
            "unreferenced_parameter_binding_definitions": max(
                0, serialized_binding_count - len(used_binding_refs)
            ),
            "serialized_keyform_grid_definitions": len(
                shared.findall("KeyformGridSource")
            ),
            "keyforms_total": sum(obj["keyforms"] for obj in all_objects),
            "physics_settings": _count_source_set(
                model_source, "CPhysicsSettingsSourceSet"
            ),
            "game_motions": _count_source_set(model_source, "CGameMotionSet"),
            "motion_sync_settings": _count_source_set(
                model_source, "CMotionSyncSettingSourceSet"
            ),
        },
        "parameter_ids": [parameter["id"] for parameter in parameters],
        "warp_deformer_names": [
            obj["name"] for obj in objects["warp_deformers"]
        ],
        "rotation_deformer_names": [
            obj["name"] for obj in objects["rotation_deformers"]
        ],
        "bound_objects": bound_objects,
    }
    if include_details:
        result["parameters"] = parameters
        result["objects"] = objects
        result["archive_entries"] = [
            {
                "path": entry.path,
                "tag": entry.tag,
                "start": entry.start,
                "size": entry.size,
                "obfuscated": entry.obfuscated,
                "compression": f"0x{entry.compression:02x}",
            }
            for entry in archive.entries
        ]
    return result


def _iter_model_paths(paths: Iterable[Path], recursive: bool) -> Iterator[Path]:
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved.is_file():
            candidates = [resolved]
        elif resolved.is_dir():
            candidates = (
                list(resolved.rglob("*.cmo3"))
                if recursive
                else list(resolved.glob("*.cmo3"))
            )
        else:
            yield resolved
            continue
        for candidate in sorted(candidates, key=lambda item: str(item).casefold()):
            if candidate not in seen:
                seen.add(candidate)
                yield candidate


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help=".cmo3 file(s), or directories containing .cmo3 files",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="scan directories recursively",
    )
    parser.add_argument(
        "--details",
        action="store_true",
        help="include per-object details and archive entry metadata",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="pretty-print one JSON array instead of JSON Lines",
    )
    parser.add_argument(
        "--max-xml-mib",
        type=int,
        default=DEFAULT_MAX_XML_BYTES // (1024 * 1024),
        help="maximum allowed decompressed main.xml size (default: 256 MiB)",
    )
    args = parser.parse_args(argv)
    if args.max_xml_mib <= 0:
        parser.error("--max-xml-mib must be positive")

    results: list[dict[str, Any]] = []
    had_error = False
    for path in _iter_model_paths(args.paths, args.recursive):
        try:
            if not path.is_file():
                raise InventoryError("path does not exist or is not a file")
            result = inventory_file(
                path,
                max_xml_bytes=args.max_xml_mib * 1024 * 1024,
                include_details=args.details,
            )
        except (InventoryError, OSError) as exc:
            had_error = True
            result = {"path": str(path), "error": str(exc)}
        results.append(result)
        if not args.pretty:
            print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))

    if args.pretty:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    return 1 if had_error else 0


if __name__ == "__main__":
    sys.exit(main())
