#!/usr/bin/env python3
"""
Conservative copy-on-write tool for a narrowly supported Live2D CMO3 layout.

This tool exists as a last-resort bridge when Cubism Editor cannot select an
object through supported keyboard controls. It never overwrites an existing
file. Output names must contain ``TEST`` and all writes are verified before the
command succeeds.

Four operations are supported:

* ``roundtrip``: copy an archive byte-for-byte, or optionally recompress its
  unchanged ``main.xml`` member to exercise the surgical writer.
* ``rename-deformer``: replace exactly one serialized deformer ``localName`` in
  ``main.xml`` and write the result to a new TEST archive.
* ``reparent-object``: change exactly one existing object's parent deformer
  reference after resolving both objects by type, name, and UUID.
* ``apply-manifest``: apply a preflighted transaction of exact reparent and
  rename operations from a strict JSON manifest.

The writer deliberately supports less than the read-only inventory parser. It
requires ``main.xml`` to be the last metadata entry, the last physical member,
obfuscated, and encoded as a single DEFLATE ZIP local-file stream followed by a
data descriptor. It refuses every archive that does not meet those invariants.
Cubism 5.2's inline ``targetDeformerGuid`` ROOT sentinel is accepted for
semantic reads and rename verification, but an object currently parented by
that inline sentinel cannot be reparented by this tool.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import struct
import sys
import uuid
import xml.etree.ElementTree as ET
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence
from xml.sax.saxutils import escape as xml_escape

from cmo3_inventory import (
    ArchiveEntry,
    BufferReader,
    CaffArchive,
    InventoryError,
    inventory_file,
)


MAX_XML_BYTES = 256 * 1024 * 1024
MAX_NAME_CHARS = 200
MAX_MANIFEST_BYTES = 1024 * 1024
ZIP_LOCAL_SIGNATURE = b"PK\x03\x04"
ZIP_DESCRIPTOR_SIGNATURE = b"PK\x07\x08"
CAFF_GUARD = b"bc"
OBJECT_TYPE_SPECS = {
    "art-mesh": ("CArtMeshSource", "CDrawableGuid", "art_meshes"),
    "warp-deformer": ("CWarpDeformerSource", "CDeformerGuid", "warp_deformers"),
    "rotation-deformer": (
        "CRotationDeformerSource",
        "CDeformerGuid",
        "rotation_deformers",
    ),
}
DEFORMER_OBJECT_TYPES = {"warp-deformer", "rotation-deformer"}
INLINE_PARENT_REF_PREFIX = "inline-guid:"
ROOT_SENTINEL_NOTE = "ROOT"


class SafeWriteError(RuntimeError):
    """Raised when a write would violate a safety or preservation invariant."""


@dataclass(frozen=True)
class EntryMetadataLocation:
    entry: ArchiveEntry
    size_field_offset: int


@dataclass(frozen=True)
class ZipLocalLayout:
    header: bytes
    compressed_payload: bytes
    descriptor: bytes
    filename: str
    crc32: int
    compressed_size: int
    uncompressed_size: int
    zlib_level: int


@dataclass(frozen=True)
class SemanticObject:
    object_type: str
    source_tag: str
    name: str
    source_ref: str
    guid_ref: str
    guid_uuid: str
    guid_note: str | None
    parent_ref: str
    parent_uuid: str
    parent_note: str | None


@dataclass(frozen=True)
class BatchOperation:
    operation_id: str
    kind: str
    target_type: str
    old_name: str
    target_uuid: str
    old_parent_uuid: str
    new_parent_type: str | None = None
    new_parent_name: str | None = None
    new_parent_uuid: str | None = None
    new_name: str | None = None


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _read_obfuscated_string(
    reader: BufferReader,
    key_low: int,
) -> str:
    value = 0
    for _ in range(10):
        decoded = reader.u8() ^ key_low
        value = (value << 7) | (decoded & 0x7F)
        if decoded & 0x80 == 0:
            break
    else:
        raise SafeWriteError("invalid or excessively long CAFF BEB128 integer")
    if value > 1024 * 1024:
        raise SafeWriteError("CAFF metadata string exceeds 1 MiB")
    raw = reader.read(value)
    try:
        return bytes(byte ^ key_low for byte in raw).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SafeWriteError("invalid UTF-8 in CAFF metadata") from exc


def _metadata_locations(
    data: bytes,
    archive: CaffArchive,
) -> tuple[list[EntryMetadataLocation], int]:
    """Reparse metadata while retaining each encrypted size-field offset."""

    reader = BufferReader(data)
    if reader.read(4) != b"CAFF":
        raise SafeWriteError("missing CAFF signature")
    reader.read(3 + 4 + 3)
    key_signed = reader.s32be()
    if key_signed != archive.obfuscation_key_signed:
        raise SafeWriteError("CAFF key changed between parser passes")
    key_u32 = key_signed & 0xFFFF_FFFF
    key_low = key_u32 & 0xFF
    key_u64 = ((key_signed << 32) | key_signed) & 0xFFFF_FFFF_FFFF_FFFF

    # Eight unknown bytes, the 20-byte preview block, and eight trailing bytes.
    reader.read(8 + 20 + 8)
    entry_count = reader.u32be() ^ key_u32
    if entry_count != len(archive.entries):
        raise SafeWriteError(
            f"entry count mismatch: table={entry_count}, parser={len(archive.entries)}"
        )

    locations: list[EntryMetadataLocation] = []
    for expected in archive.entries:
        path = _read_obfuscated_string(reader, key_low)
        tag = _read_obfuscated_string(reader, key_low)
        start = reader.u64be() ^ key_u64
        size_field_offset = reader.offset
        size = reader.u32be() ^ key_u32
        obfuscated = bool(reader.u8() ^ key_low)
        compression = reader.u8() ^ key_low
        reader.read(8)
        observed = ArchiveEntry(
            path=path,
            tag=tag,
            start=start,
            size=size,
            obfuscated=obfuscated,
            compression=compression,
        )
        if observed != expected:
            raise SafeWriteError(
                f"metadata parser disagreement for entry {expected.path!r}"
            )
        locations.append(
            EntryMetadataLocation(
                entry=expected,
                size_field_offset=size_field_offset,
            )
        )
    return locations, reader.offset


def _clear_stored_member(archive: CaffArchive, entry: ArchiveEntry) -> bytes:
    stored = archive.data[entry.start : entry.start + entry.size]
    if not entry.obfuscated:
        return stored
    key_low = (archive.obfuscation_key_signed & 0xFFFF_FFFF) & 0xFF
    return bytes(byte ^ key_low for byte in stored)


def _parse_zip_local_member(clear_member: bytes) -> ZipLocalLayout:
    if len(clear_member) < 46 or clear_member[:4] != ZIP_LOCAL_SIGNATURE:
        raise SafeWriteError("main.xml is not a supported ZIP local-file stream")
    flags = int.from_bytes(clear_member[6:8], "little")
    method = int.from_bytes(clear_member[8:10], "little")
    filename_length = int.from_bytes(clear_member[26:28], "little")
    extra_length = int.from_bytes(clear_member[28:30], "little")
    payload_start = 30 + filename_length + extra_length
    if method != 8:
        raise SafeWriteError(f"unsupported main.xml compression method {method}")
    if flags & 0x0008 == 0:
        raise SafeWriteError("main.xml ZIP stream does not use a data descriptor")
    if payload_start > len(clear_member):
        raise SafeWriteError("truncated ZIP local-file header")

    try:
        filename = clear_member[30 : 30 + filename_length].decode(
            "utf-8" if flags & 0x0800 else "cp437"
        )
    except UnicodeDecodeError as exc:
        raise SafeWriteError("invalid ZIP member filename") from exc

    compressed_and_descriptor = clear_member[payload_start:]
    inflater = zlib.decompressobj(-zlib.MAX_WBITS)
    uncompressed = inflater.decompress(
        compressed_and_descriptor,
        MAX_XML_BYTES + 1,
    )
    if len(uncompressed) > MAX_XML_BYTES:
        raise SafeWriteError("invalid or oversized main.xml DEFLATE stream")
    uncompressed += inflater.flush(MAX_XML_BYTES + 1 - len(uncompressed))
    if len(uncompressed) > MAX_XML_BYTES or not inflater.eof:
        raise SafeWriteError("invalid or oversized main.xml DEFLATE stream")
    descriptor = inflater.unused_data
    compressed_size = len(compressed_and_descriptor) - len(descriptor)
    if len(descriptor) != 16 or descriptor[:4] != ZIP_DESCRIPTOR_SIGNATURE:
        raise SafeWriteError(
            "main.xml must end in one 16-byte ZIP data descriptor"
        )
    crc32, described_compressed, described_uncompressed = struct.unpack(
        "<III", descriptor[4:]
    )
    if described_compressed != compressed_size:
        raise SafeWriteError("ZIP descriptor compressed size mismatch")
    if described_uncompressed != len(uncompressed):
        raise SafeWriteError("ZIP descriptor uncompressed size mismatch")
    if crc32 != (zlib.crc32(uncompressed) & 0xFFFF_FFFF):
        raise SafeWriteError("ZIP descriptor CRC-32 mismatch")

    compressed_payload = compressed_and_descriptor[:compressed_size]
    matching_levels: list[int] = []
    for level in range(10):
        candidate = zlib.compressobj(
            level=level,
            method=zlib.DEFLATED,
            wbits=-zlib.MAX_WBITS,
            memLevel=8,
            strategy=zlib.Z_DEFAULT_STRATEGY,
        )
        candidate_payload = (
            candidate.compress(uncompressed)
            + candidate.flush()
        )
        if candidate_payload == compressed_payload:
            matching_levels.append(level)
    if not matching_levels:
        raise SafeWriteError(
            "cannot reproduce the source DEFLATE stream with supported zlib "
            "levels; refusing a non-conservative rewrite"
        )

    return ZipLocalLayout(
        header=clear_member[:payload_start],
        compressed_payload=compressed_payload,
        descriptor=descriptor,
        filename=filename,
        crc32=crc32,
        compressed_size=compressed_size,
        uncompressed_size=len(uncompressed),
        zlib_level=matching_levels[0],
    )


def _build_zip_local_member(source: ZipLocalLayout, contents: bytes) -> bytes:
    if len(contents) > MAX_XML_BYTES:
        raise SafeWriteError("replacement main.xml exceeds 256 MiB")
    compressor = zlib.compressobj(
        level=source.zlib_level,
        method=zlib.DEFLATED,
        wbits=-zlib.MAX_WBITS,
        memLevel=8,
        strategy=zlib.Z_DEFAULT_STRATEGY,
    )
    compressed = compressor.compress(contents) + compressor.flush()
    if len(compressed) > 0xFFFF_FFFF or len(contents) > 0xFFFF_FFFF:
        raise SafeWriteError("replacement ZIP member exceeds 32-bit size fields")
    descriptor = ZIP_DESCRIPTOR_SIGNATURE + struct.pack(
        "<III",
        zlib.crc32(contents) & 0xFFFF_FFFF,
        len(compressed),
        len(contents),
    )
    return source.header + compressed + descriptor


def _validate_surgical_layout(
    data: bytes,
) -> tuple[
    CaffArchive,
    ArchiveEntry,
    EntryMetadataLocation,
    ZipLocalLayout,
    bytes,
]:
    try:
        archive = CaffArchive.parse(data)
    except InventoryError as exc:
        raise SafeWriteError(str(exc)) from exc
    main_matches = [entry for entry in archive.entries if entry.path == "main.xml"]
    if len(main_matches) != 1:
        raise SafeWriteError(
            f"expected one main.xml entry, found {len(main_matches)}"
        )
    main = main_matches[0]
    locations, metadata_end = _metadata_locations(data, archive)
    main_location = next(
        location for location in locations if location.entry.path == "main.xml"
    )

    if archive.entries[-1] != main:
        raise SafeWriteError("main.xml is not the last CAFF metadata entry")
    physical = sorted(archive.entries, key=lambda entry: entry.start)
    if physical[-1] != main:
        raise SafeWriteError("main.xml is not the last physical CAFF member")
    if metadata_end > physical[0].start:
        raise SafeWriteError("CAFF metadata overlaps the first data member")
    for previous, current in zip(physical, physical[1:]):
        if previous.start + previous.size != current.start:
            raise SafeWriteError(
                f"CAFF data is not contiguous between {previous.path!r} "
                f"and {current.path!r}"
            )
    if main.start + main.size != len(data) - len(CAFF_GUARD):
        raise SafeWriteError("main.xml does not end immediately before CAFF guard")
    if data[-len(CAFF_GUARD) :] != CAFF_GUARD:
        raise SafeWriteError("invalid CAFF trailing guard")
    if not main.obfuscated:
        raise SafeWriteError("main.xml is unexpectedly not obfuscated")
    if main.compression not in {0x21, 0x25}:
        raise SafeWriteError(
            f"unsupported main.xml CAFF compression 0x{main.compression:02x}"
        )

    clear_member = _clear_stored_member(archive, main)
    zip_layout = _parse_zip_local_member(clear_member)
    try:
        main_xml = archive.read_unique_path("main.xml", MAX_XML_BYTES)
    except InventoryError as exc:
        raise SafeWriteError(str(exc)) from exc
    if zip_layout.uncompressed_size != len(main_xml):
        raise SafeWriteError("independent main.xml size checks disagree")
    return archive, main, main_location, zip_layout, main_xml


def _replace_main_xml(
    data: bytes,
    replacement: bytes,
    *,
    force_repack: bool = False,
) -> bytes:
    archive, main, location, zip_layout, original = _validate_surgical_layout(data)
    if replacement == original and not force_repack:
        return data

    new_clear_member = _build_zip_local_member(zip_layout, replacement)
    key_u32 = archive.obfuscation_key_signed & 0xFFFF_FFFF
    key_low = key_u32 & 0xFF
    new_stored_member = bytes(byte ^ key_low for byte in new_clear_member)
    if len(new_stored_member) > 0xFFFF_FFFF:
        raise SafeWriteError("replacement main.xml CAFF member is too large")

    prefix = bytearray(data[: main.start])
    encrypted_size = len(new_stored_member) ^ key_u32
    prefix[
        location.size_field_offset : location.size_field_offset + 4
    ] = struct.pack(">I", encrypted_size)
    result = bytes(prefix) + new_stored_member + data[main.start + main.size :]

    # Parse immediately in memory before any filesystem write.
    output_archive, output_main, _, _, output_xml = _validate_surgical_layout(result)
    if output_xml != replacement:
        raise SafeWriteError("in-memory output main.xml differs from replacement")
    if len(output_archive.entries) != len(archive.entries):
        raise SafeWriteError("in-memory output entry count changed")
    for before, after in zip(archive.entries, output_archive.entries):
        if before.path == "main.xml":
            if (
                before.path,
                before.tag,
                before.start,
                before.obfuscated,
                before.compression,
            ) != (
                after.path,
                after.tag,
                after.start,
                after.obfuscated,
                after.compression,
            ):
                raise SafeWriteError("main.xml metadata changed beyond its size")
            if output_main.size != len(new_stored_member):
                raise SafeWriteError("main.xml metadata size was not updated")
        elif before != after:
            raise SafeWriteError(f"metadata changed for {before.path!r}")
    return result


def _validate_deformer_name(name: str, label: str) -> None:
    if not name:
        raise SafeWriteError(f"{label} name must not be empty")
    if len(name) > MAX_NAME_CHARS:
        raise SafeWriteError(f"{label} name exceeds {MAX_NAME_CHARS} characters")
    if any(ord(character) < 0x20 for character in name):
        raise SafeWriteError(f"{label} name contains a control character")


def _deformer_names(main_xml: bytes) -> list[tuple[str, str]]:
    if b"<!DOCTYPE" in main_xml[:65536] or b"<!ENTITY" in main_xml[:65536]:
        raise SafeWriteError("XML DTD/entity declarations are not accepted")
    try:
        root = ET.fromstring(main_xml)
    except ET.ParseError as exc:
        raise SafeWriteError(f"invalid main.xml: {exc}") from exc
    shared = root.find("shared")
    if shared is None:
        raise SafeWriteError("main.xml lacks shared object definitions")
    result: list[tuple[str, str]] = []
    for kind in ("CWarpDeformerSource", "CRotationDeformerSource"):
        for source in shared.findall(kind):
            names = [
                node.text or ""
                for node in source.iter("s")
                if node.get("xs.n") == "localName"
            ]
            if len(names) != 1:
                raise SafeWriteError(
                    f"{kind} {source.get('xs.id')!r} has {len(names)} localName fields"
                )
            result.append((kind, names[0]))
    return result


def _rename_one_deformer(main_xml: bytes, old: str, new: str) -> bytes:
    _validate_deformer_name(old, "old")
    _validate_deformer_name(new, "new")
    if old == new:
        raise SafeWriteError("old and new deformer names are identical")

    semantic = _deformer_names(main_xml)
    matches = [(kind, name) for kind, name in semantic if name == old]
    if len(matches) != 1:
        raise SafeWriteError(
            f"expected exactly one deformer named {old!r}, found {len(matches)}"
        )
    if any(name == new for _, name in semantic):
        raise SafeWriteError(f"a deformer named {new!r} already exists")

    old_serialized = xml_escape(old).encode("utf-8")
    new_serialized = xml_escape(new).encode("utf-8")
    pattern = re.compile(
        rb'(<s\s+xs\.n="localName">)'
        + re.escape(old_serialized)
        + rb"(</s>)"
    )
    patched, replacement_count = pattern.subn(
        lambda match: match.group(1) + new_serialized + match.group(2),
        main_xml,
    )
    if replacement_count != 1:
        raise SafeWriteError(
            "serialized deformer name is not uniquely patchable; refusing write"
        )

    after = _deformer_names(patched)
    expected = [
        (kind, new if name == old else name)
        for kind, name in semantic
    ]
    if after != expected:
        raise SafeWriteError("deformer semantic validation failed after patch")
    return patched


def _canonical_uuid(value: str, label: str) -> str:
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError) as exc:
        raise SafeWriteError(f"{label} is not a valid UUID: {value!r}") from exc


def _one_named_descendant(
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
        raise SafeWriteError(
            f"{source.tag} {source.get('xs.id')!r} has {len(matches)} "
            f"{tag} fields named {serialized_name!r}"
        )
    return matches[0]


def _semantic_objects(main_xml: bytes) -> list[SemanticObject]:
    if b"<!DOCTYPE" in main_xml[:65536] or b"<!ENTITY" in main_xml[:65536]:
        raise SafeWriteError("XML DTD/entity declarations are not accepted")
    try:
        root = ET.fromstring(main_xml)
    except ET.ParseError as exc:
        raise SafeWriteError(f"invalid main.xml: {exc}") from exc
    shared = root.find("shared")
    if shared is None:
        raise SafeWriteError("main.xml lacks shared object definitions")

    id_map: dict[str, ET.Element] = {}
    for node in root.iter():
        serialized_id = node.get("xs.id")
        if serialized_id is None:
            continue
        if serialized_id in id_map:
            raise SafeWriteError(f"duplicate serialized xs.id {serialized_id!r}")
        id_map[serialized_id] = node

    objects: list[SemanticObject] = []
    for object_type, (
        source_tag,
        guid_tag,
        _,
    ) in OBJECT_TYPE_SPECS.items():
        for source in shared.findall(source_tag):
            source_ref = source.get("xs.id")
            if not source_ref:
                raise SafeWriteError(f"{source_tag} lacks xs.id")
            name_node = _one_named_descendant(source, "s", "localName")
            name = name_node.text or ""
            if not name:
                raise SafeWriteError(f"{source_tag} {source_ref!r} has an empty name")

            guid_node = _one_named_descendant(source, guid_tag, "guid")
            guid_ref = guid_node.get("xs.ref")
            if not guid_ref:
                raise SafeWriteError(
                    f"{source_tag} {source_ref!r} has no referenced object GUID"
                )
            guid_definition = id_map.get(guid_ref)
            if guid_definition is None or guid_definition.tag != guid_tag:
                raise SafeWriteError(
                    f"{source_tag} {source_ref!r} GUID {guid_ref!r} is unresolved"
                )
            guid_uuid_raw = guid_definition.get("uuid")
            if not guid_uuid_raw:
                raise SafeWriteError(f"GUID definition {guid_ref!r} lacks uuid")
            guid_uuid = _canonical_uuid(guid_uuid_raw, f"object GUID {guid_ref}")

            parent_node = _one_named_descendant(
                source,
                "CDeformerGuid",
                "targetDeformerGuid",
            )
            parent_ref = parent_node.get("xs.ref")
            if parent_ref:
                parent_definition = id_map.get(parent_ref)
                if (
                    parent_definition is None
                    or parent_definition.tag != "CDeformerGuid"
                ):
                    raise SafeWriteError(
                        f"{source_tag} {source_ref!r} parent "
                        f"{parent_ref!r} is unresolved"
                    )
                parent_uuid_raw = parent_definition.get("uuid")
                if not parent_uuid_raw:
                    raise SafeWriteError(
                        f"parent GUID {parent_ref!r} lacks uuid"
                    )
                parent_uuid = _canonical_uuid(
                    parent_uuid_raw,
                    f"parent GUID {parent_ref}",
                )
                parent_note = parent_definition.get("note")
            else:
                # Cubism 5.2 serializes the top-level ROOT sentinel inline
                # instead of through a shared ``xs.ref`` definition.  Keep a
                # deterministic synthetic reference for semantic graph
                # validation, but never treat it as a writable shared ID.
                parent_uuid_raw = parent_node.get("uuid")
                if not parent_uuid_raw:
                    raise SafeWriteError(
                        f"{source_tag} {source_ref!r} parent GUID is neither "
                        "a shared xs.ref nor an inline uuid"
                    )
                parent_uuid = _canonical_uuid(
                    parent_uuid_raw,
                    f"inline parent GUID for {source_ref}",
                )
                if parent_node.get("note") != ROOT_SENTINEL_NOTE:
                    raise SafeWriteError(
                        f"{source_tag} {source_ref!r} inline parent GUID "
                        f"must carry note={ROOT_SENTINEL_NOTE!r}"
                    )
                parent_ref = INLINE_PARENT_REF_PREFIX + parent_uuid
                parent_note = parent_node.get("note")
            objects.append(
                SemanticObject(
                    object_type=object_type,
                    source_tag=source_tag,
                    name=name,
                    source_ref=source_ref,
                    guid_ref=guid_ref,
                    guid_uuid=guid_uuid,
                    guid_note=guid_definition.get("note"),
                    parent_ref=parent_ref,
                    parent_uuid=parent_uuid,
                    parent_note=parent_note,
                )
            )

    seen_guids: dict[str, SemanticObject] = {}
    inline_parent_refs: set[str] = set()
    for item in objects:
        previous = seen_guids.get(item.guid_ref)
        if previous is not None:
            raise SafeWriteError(
                f"object GUID {item.guid_ref!r} is shared by "
                f"{previous.name!r} and {item.name!r}"
            )
        seen_guids[item.guid_ref] = item
        if item.parent_ref.startswith(INLINE_PARENT_REF_PREFIX):
            inline_parent_refs.add(item.parent_ref)
    if len(inline_parent_refs) > 1:
        raise SafeWriteError(
            "model contains multiple distinct inline ROOT parent GUIDs"
        )
    return objects


def _resolve_semantic_object(
    objects: list[SemanticObject],
    *,
    object_type: str,
    name: str,
    guid_uuid: str,
    label: str,
) -> SemanticObject:
    canonical_guid = _canonical_uuid(guid_uuid, f"{label} GUID")
    matches = [
        item
        for item in objects
        if item.object_type == object_type
        and item.name == name
        and item.guid_uuid == canonical_guid
    ]
    if len(matches) != 1:
        raise SafeWriteError(
            f"expected exactly one {label} matching type={object_type!r}, "
            f"name={name!r}, GUID={canonical_guid!r}; found {len(matches)}"
        )
    return matches[0]


def _validate_deformer_graph(objects: list[SemanticObject]) -> None:
    deformers = {
        item.guid_ref: item
        for item in objects
        if item.object_type in DEFORMER_OBJECT_TYPES
    }
    for starting_ref, starting in deformers.items():
        seen: list[str] = []
        current_ref = starting_ref
        while current_ref in deformers:
            if current_ref in seen:
                cycle = seen[seen.index(current_ref) :] + [current_ref]
                cycle_names = [
                    deformers[guid_ref].name
                    for guid_ref in cycle
                ]
                raise SafeWriteError(
                    "existing deformer hierarchy contains a cycle: "
                    + " -> ".join(cycle_names)
                )
            seen.append(current_ref)
            current_ref = deformers[current_ref].parent_ref
        if not seen or seen[0] != starting.guid_ref:
            raise SafeWriteError("internal deformer graph validation error")


def _reparent_one_object(
    main_xml: bytes,
    *,
    object_type: str,
    object_name: str,
    object_guid: str,
    expected_parent_guid: str,
    parent_type: str,
    parent_name: str,
    parent_guid: str,
) -> tuple[bytes, SemanticObject, SemanticObject, dict[str, Any]]:
    if object_type not in OBJECT_TYPE_SPECS:
        raise SafeWriteError(f"unsupported object type {object_type!r}")
    if parent_type not in DEFORMER_OBJECT_TYPES:
        raise SafeWriteError(f"parent type must be a deformer, got {parent_type!r}")
    objects_before = _semantic_objects(main_xml)
    _validate_deformer_graph(objects_before)
    target = _resolve_semantic_object(
        objects_before,
        object_type=object_type,
        name=object_name,
        guid_uuid=object_guid,
        label="target object",
    )
    parent = _resolve_semantic_object(
        objects_before,
        object_type=parent_type,
        name=parent_name,
        guid_uuid=parent_guid,
        label="parent deformer",
    )
    expected_old_parent = _canonical_uuid(
        expected_parent_guid,
        "expected current parent GUID",
    )
    if target.parent_uuid != expected_old_parent:
        raise SafeWriteError(
            f"target current parent GUID is {target.parent_uuid!r}, "
            f"not expected {expected_old_parent!r}"
        )
    if target.parent_ref == parent.guid_ref:
        raise SafeWriteError("target already has the requested parent")
    if target.parent_ref.startswith(INLINE_PARENT_REF_PREFIX):
        raise SafeWriteError(
            "reparenting an object whose current parent GUID is serialized "
            "inline is intentionally unsupported"
        )

    if target.object_type in DEFORMER_OBJECT_TYPES:
        deformers = {
            item.guid_ref: item
            for item in objects_before
            if item.object_type in DEFORMER_OBJECT_TYPES
        }
        current_ref = parent.guid_ref
        visited: set[str] = set()
        while current_ref in deformers:
            if current_ref == target.guid_ref:
                raise SafeWriteError(
                    f"reparenting {target.name!r} below {parent.name!r} "
                    "would create a cycle"
                )
            if current_ref in visited:
                raise SafeWriteError("cycle encountered while checking new parent")
            visited.add(current_ref)
            current_ref = deformers[current_ref].parent_ref

    source_tag_bytes = re.escape(target.source_tag.encode("ascii"))
    source_ref_bytes = re.escape(target.source_ref.encode("ascii"))
    opening_pattern = re.compile(
        rb"<"
        + source_tag_bytes
        + rb'\b(?=[^>]*\bxs\.id="'
        + source_ref_bytes
        + rb'")[^>]*>'
    )
    openings = list(opening_pattern.finditer(main_xml))
    if len(openings) != 1:
        raise SafeWriteError(
            f"serialized source block {target.source_ref!r} is not unique"
        )
    block_start = openings[0].start()
    closing_token = b"</" + target.source_tag.encode("ascii") + b">"
    closing_start = main_xml.find(closing_token, openings[0].end())
    if closing_start < 0:
        raise SafeWriteError(
            f"serialized source block {target.source_ref!r} is not closed"
        )
    block_end = closing_start + len(closing_token)
    source_block = main_xml[block_start:block_end]

    parent_tag_pattern = re.compile(
        rb'<CDeformerGuid\b'
        rb'(?=[^>]*\bxs\.n="targetDeformerGuid")'
        rb"[^>]*/>"
    )
    parent_tags = list(parent_tag_pattern.finditer(source_block))
    if len(parent_tags) != 1:
        raise SafeWriteError(
            f"target source block has {len(parent_tags)} serialized parent fields"
        )
    parent_tag = parent_tags[0].group(0)
    old_ref_token = b'xs.ref="' + target.parent_ref.encode("ascii") + b'"'
    new_ref_token = b'xs.ref="' + parent.guid_ref.encode("ascii") + b'"'
    if parent_tag.count(old_ref_token) != 1:
        raise SafeWriteError(
            "serialized parent field does not contain the expected old reference"
        )
    if old_ref_token == new_ref_token:
        raise SafeWriteError("serialized old and new parent references are identical")
    patched_parent_tag = parent_tag.replace(old_ref_token, new_ref_token, 1)
    patched_source_block = (
        source_block[: parent_tags[0].start()]
        + patched_parent_tag
        + source_block[parent_tags[0].end() :]
    )
    patched = (
        main_xml[:block_start]
        + patched_source_block
        + main_xml[block_end:]
    )

    objects_after = _semantic_objects(patched)
    _validate_deformer_graph(objects_after)
    target_after = _resolve_semantic_object(
        objects_after,
        object_type=object_type,
        name=object_name,
        guid_uuid=object_guid,
        label="patched target object",
    )
    parent_after = _resolve_semantic_object(
        objects_after,
        object_type=parent_type,
        name=parent_name,
        guid_uuid=parent_guid,
        label="patched parent deformer",
    )
    if target_after.parent_ref != parent_after.guid_ref:
        raise SafeWriteError("patched target does not resolve to requested parent")
    if parent_after != parent:
        raise SafeWriteError("parent deformer changed during reparent patch")

    absolute_field_offset = (
        block_start
        + parent_tags[0].start()
        + parent_tag.index(old_ref_token)
        + len(b'xs.ref="')
    )
    old_ref_bytes = target.parent_ref.encode("ascii")
    new_ref_bytes = parent.guid_ref.encode("ascii")
    changed_byte_count = None
    if len(old_ref_bytes) == len(new_ref_bytes):
        changed_byte_count = sum(
            before != after
            for before, after in zip(old_ref_bytes, new_ref_bytes)
        )
    return (
        patched,
        target,
        parent,
        {
            "field": "CDeformerGuid[targetDeformerGuid]/@xs.ref",
            "xml_byte_offset": absolute_field_offset,
            "old_ref": target.parent_ref,
            "new_ref": parent.guid_ref,
            "old_field_tag": parent_tag.decode("utf-8"),
            "new_field_tag": patched_parent_tag.decode("utf-8"),
            "logical_xml_bytes_before": len(main_xml),
            "logical_xml_bytes_after": len(patched),
            "changed_byte_count_same_length": changed_byte_count,
        },
    )


def _source_block_span(
    main_xml: bytes,
    target: SemanticObject,
) -> tuple[int, int, bytes]:
    source_tag_bytes = re.escape(target.source_tag.encode("ascii"))
    source_ref_bytes = re.escape(target.source_ref.encode("ascii"))
    opening_pattern = re.compile(
        rb"<"
        + source_tag_bytes
        + rb'\b(?=[^>]*\bxs\.id="'
        + source_ref_bytes
        + rb'")[^>]*>'
    )
    openings = list(opening_pattern.finditer(main_xml))
    if len(openings) != 1:
        raise SafeWriteError(
            f"serialized source block {target.source_ref!r} is not unique"
        )
    block_start = openings[0].start()
    closing_token = b"</" + target.source_tag.encode("ascii") + b">"
    closing_start = main_xml.find(closing_token, openings[0].end())
    if closing_start < 0:
        raise SafeWriteError(
            f"serialized source block {target.source_ref!r} is not closed"
        )
    block_end = closing_start + len(closing_token)
    return block_start, block_end, main_xml[block_start:block_end]


def _patch_parent_ref_for_record(
    main_xml: bytes,
    *,
    target: SemanticObject,
    expected_old_ref: str,
    new_parent: SemanticObject,
) -> tuple[bytes, dict[str, Any]]:
    if expected_old_ref.startswith(INLINE_PARENT_REF_PREFIX):
        raise SafeWriteError(
            "reparenting an object whose current parent GUID is serialized "
            "inline is intentionally unsupported"
        )
    block_start, block_end, source_block = _source_block_span(main_xml, target)
    parent_tag_pattern = re.compile(
        rb'<CDeformerGuid\b'
        rb'(?=[^>]*\bxs\.n="targetDeformerGuid")'
        rb"[^>]*/>"
    )
    parent_tags = list(parent_tag_pattern.finditer(source_block))
    if len(parent_tags) != 1:
        raise SafeWriteError(
            f"target source block has {len(parent_tags)} serialized parent fields"
        )
    parent_tag = parent_tags[0].group(0)
    old_ref_token = b'xs.ref="' + expected_old_ref.encode("ascii") + b'"'
    new_ref_token = b'xs.ref="' + new_parent.guid_ref.encode("ascii") + b'"'
    if parent_tag.count(old_ref_token) != 1:
        raise SafeWriteError(
            f"parent field for {target.name!r} does not contain "
            f"expected reference {expected_old_ref!r}"
        )
    if old_ref_token == new_ref_token:
        raise SafeWriteError(f"{target.name!r} already has requested parent")
    patched_parent_tag = parent_tag.replace(old_ref_token, new_ref_token, 1)
    patched_source_block = (
        source_block[: parent_tags[0].start()]
        + patched_parent_tag
        + source_block[parent_tags[0].end() :]
    )
    patched = (
        main_xml[:block_start]
        + patched_source_block
        + main_xml[block_end:]
    )
    absolute_value_offset = (
        block_start
        + parent_tags[0].start()
        + parent_tag.index(old_ref_token)
        + len(b'xs.ref="')
    )
    old_bytes = expected_old_ref.encode("ascii")
    new_bytes = new_parent.guid_ref.encode("ascii")
    return patched, {
        "field": "CDeformerGuid[targetDeformerGuid]/@xs.ref",
        "source_ref": target.source_ref,
        "object_guid": target.guid_uuid,
        "xml_value_offset_before_step": absolute_value_offset,
        "old_value": expected_old_ref,
        "new_value": new_parent.guid_ref,
        "old_serialized_field": parent_tag.decode("utf-8"),
        "new_serialized_field": patched_parent_tag.decode("utf-8"),
        "changed_byte_count_same_length": (
            sum(a != b for a, b in zip(old_bytes, new_bytes))
            if len(old_bytes) == len(new_bytes)
            else None
        ),
    }


def _patch_name_for_record(
    main_xml: bytes,
    *,
    target: SemanticObject,
    expected_old_name: str,
    new_name: str,
) -> tuple[bytes, dict[str, Any]]:
    _validate_deformer_name(expected_old_name, "old object")
    _validate_deformer_name(new_name, "new object")
    if expected_old_name == new_name:
        raise SafeWriteError("old and new object names are identical")
    block_start, block_end, source_block = _source_block_span(main_xml, target)
    old_serialized = xml_escape(expected_old_name).encode("utf-8")
    new_serialized = xml_escape(new_name).encode("utf-8")
    local_name_pattern = re.compile(
        rb'(<s\b(?=[^>]*\bxs\.n="localName")[^>]*>)'
        + re.escape(old_serialized)
        + rb"(</s>)"
    )
    matches = list(local_name_pattern.finditer(source_block))
    if len(matches) != 1:
        raise SafeWriteError(
            f"source block for {target.name!r} has {len(matches)} "
            "patchable localName fields"
        )
    name_match = matches[0]
    old_field = name_match.group(0)
    new_field = (
        name_match.group(1)
        + new_serialized
        + name_match.group(2)
    )
    patched_source_block = (
        source_block[: name_match.start()]
        + new_field
        + source_block[name_match.end() :]
    )
    patched = (
        main_xml[:block_start]
        + patched_source_block
        + main_xml[block_end:]
    )
    absolute_value_offset = (
        block_start
        + name_match.start()
        + len(name_match.group(1))
    )
    return patched, {
        "field": "s[localName]/text()",
        "source_ref": target.source_ref,
        "object_guid": target.guid_uuid,
        "xml_value_offset_before_step": absolute_value_offset,
        "old_value": expected_old_name,
        "new_value": new_name,
        "old_serialized_field": old_field.decode("utf-8"),
        "new_serialized_field": new_field.decode("utf-8"),
        "changed_byte_count_same_length": (
            sum(
                a != b
                for a, b in zip(
                    old_serialized,
                    new_serialized,
                )
            )
            if len(old_serialized) == len(new_serialized)
            else None
        ),
    }


def _reject_duplicate_json_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SafeWriteError(f"manifest contains duplicate JSON key {key!r}")
        result[key] = value
    return result


def _expect_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SafeWriteError(f"{label} must be a JSON object")
    return value


def _expect_exact_keys(
    value: dict[str, Any],
    *,
    required: set[str],
    optional: set[str] | None = None,
    label: str,
) -> None:
    optional = optional or set()
    missing = required - set(value)
    unexpected = set(value) - required - optional
    if missing:
        raise SafeWriteError(
            f"{label} is missing keys: {', '.join(sorted(missing))}"
        )
    if unexpected:
        raise SafeWriteError(
            f"{label} has unexpected keys: {', '.join(sorted(unexpected))}"
        )


def _expect_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise SafeWriteError(f"{label} must be a non-empty string")
    return value


def _normalize_sha256(value: Any, label: str) -> str:
    text = _expect_string(value, label).upper()
    if re.fullmatch(r"[0-9A-F]{64}", text) is None:
        raise SafeWriteError(f"{label} must be a 64-character SHA-256")
    return text


def _validated_identity(
    raw: Any,
    *,
    label: str,
    include_old_parent: bool,
) -> dict[str, str]:
    identity = _expect_mapping(raw, label)
    required = {"type", "old_name", "uuid"}
    if include_old_parent:
        required.add("old_parent_uuid")
    _expect_exact_keys(identity, required=required, label=label)
    object_type = _expect_string(identity["type"], f"{label}.type")
    if object_type not in OBJECT_TYPE_SPECS:
        raise SafeWriteError(f"{label}.type is unsupported: {object_type!r}")
    old_name = _expect_string(identity["old_name"], f"{label}.old_name")
    _validate_deformer_name(old_name, f"{label}.old_name")
    result = {
        "type": object_type,
        "old_name": old_name,
        "uuid": _canonical_uuid(
            _expect_string(identity["uuid"], f"{label}.uuid"),
            f"{label}.uuid",
        ),
    }
    if include_old_parent:
        result["old_parent_uuid"] = _canonical_uuid(
            _expect_string(
                identity["old_parent_uuid"],
                f"{label}.old_parent_uuid",
            ),
            f"{label}.old_parent_uuid",
        )
    return result


def _read_batch_manifest(
    manifest_path: Path,
) -> tuple[
    dict[str, Any],
    list[BatchOperation],
    list[dict[str, Any]],
    bytes,
]:
    manifest_path = manifest_path.resolve(strict=True)
    if not manifest_path.is_file():
        raise SafeWriteError(f"manifest is not a file: {manifest_path}")
    raw_bytes = manifest_path.read_bytes()
    if len(raw_bytes) > MAX_MANIFEST_BYTES:
        raise SafeWriteError("manifest exceeds 1 MiB")
    try:
        raw = json.loads(
            raw_bytes.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except UnicodeDecodeError as exc:
        raise SafeWriteError("manifest is not valid UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise SafeWriteError(f"invalid manifest JSON: {exc}") from exc
    root = _expect_mapping(raw, "manifest")
    _expect_exact_keys(
        root,
        required={
            "schema_version",
            "transaction_id",
            "description",
            "source",
            "output",
            "operations",
            "assertions",
        },
        label="manifest",
    )
    if root["schema_version"] != 1:
        raise SafeWriteError("manifest.schema_version must be exactly 1")
    transaction_id = _expect_string(
        root["transaction_id"],
        "manifest.transaction_id",
    )
    if re.fullmatch(r"[A-Za-z0-9._-]{1,100}", transaction_id) is None:
        raise SafeWriteError("manifest.transaction_id has unsafe characters")
    _expect_string(root["description"], "manifest.description")

    source = _expect_mapping(root["source"], "manifest.source")
    _expect_exact_keys(
        source,
        required={"required_filename", "sha256"},
        label="manifest.source",
    )
    source_filename = _expect_string(
        source["required_filename"],
        "manifest.source.required_filename",
    )
    if Path(source_filename).name != source_filename:
        raise SafeWriteError(
            "manifest.source.required_filename must be a basename"
        )
    source["sha256"] = _normalize_sha256(
        source["sha256"],
        "manifest.source.sha256",
    )

    output = _expect_mapping(root["output"], "manifest.output")
    _expect_exact_keys(
        output,
        required={"required_filename"},
        label="manifest.output",
    )
    output_filename = _expect_string(
        output["required_filename"],
        "manifest.output.required_filename",
    )
    if Path(output_filename).name != output_filename:
        raise SafeWriteError(
            "manifest.output.required_filename must be a basename"
        )
    if (
        Path(output_filename).suffix.casefold() != ".cmo3"
        or "test" not in Path(output_filename).stem.casefold()
    ):
        raise SafeWriteError("manifest output filename must be a TEST .cmo3")

    raw_operations = root["operations"]
    if (
        not isinstance(raw_operations, list)
        or not raw_operations
        or len(raw_operations) > 100
    ):
        raise SafeWriteError("manifest.operations must contain 1 to 100 items")
    operations: list[BatchOperation] = []
    operation_ids: set[str] = set()
    for index, raw_operation in enumerate(raw_operations):
        label = f"manifest.operations[{index}]"
        operation = _expect_mapping(raw_operation, label)
        kind = _expect_string(operation.get("op"), f"{label}.op")
        if kind == "reparent":
            _expect_exact_keys(
                operation,
                required={"id", "op", "object", "new_parent"},
                label=label,
            )
        elif kind == "rename":
            _expect_exact_keys(
                operation,
                required={"id", "op", "object", "new_name"},
                label=label,
            )
        else:
            raise SafeWriteError(f"{label}.op is unsupported: {kind!r}")
        operation_id = _expect_string(operation["id"], f"{label}.id")
        if re.fullmatch(r"[A-Za-z0-9._-]{1,100}", operation_id) is None:
            raise SafeWriteError(f"{label}.id has unsafe characters")
        if operation_id in operation_ids:
            raise SafeWriteError(f"duplicate operation id {operation_id!r}")
        operation_ids.add(operation_id)
        target = _validated_identity(
            operation["object"],
            label=f"{label}.object",
            include_old_parent=True,
        )
        if kind == "reparent":
            new_parent = _validated_identity(
                operation["new_parent"],
                label=f"{label}.new_parent",
                include_old_parent=False,
            )
            if new_parent["type"] not in DEFORMER_OBJECT_TYPES:
                raise SafeWriteError(f"{label}.new_parent must be a deformer")
            operations.append(
                BatchOperation(
                    operation_id=operation_id,
                    kind=kind,
                    target_type=target["type"],
                    old_name=target["old_name"],
                    target_uuid=target["uuid"],
                    old_parent_uuid=target["old_parent_uuid"],
                    new_parent_type=new_parent["type"],
                    new_parent_name=new_parent["old_name"],
                    new_parent_uuid=new_parent["uuid"],
                )
            )
        else:
            new_name = _expect_string(
                operation["new_name"],
                f"{label}.new_name",
            )
            _validate_deformer_name(new_name, f"{label}.new_name")
            operations.append(
                BatchOperation(
                    operation_id=operation_id,
                    kind=kind,
                    target_type=target["type"],
                    old_name=target["old_name"],
                    target_uuid=target["uuid"],
                    old_parent_uuid=target["old_parent_uuid"],
                    new_name=new_name,
                )
            )

    assertions = _expect_mapping(
        root["assertions"],
        "manifest.assertions",
    )
    _expect_exact_keys(
        assertions,
        required={"preserve_children"},
        label="manifest.assertions",
    )
    raw_preserve = assertions["preserve_children"]
    if not isinstance(raw_preserve, list) or len(raw_preserve) > 100:
        raise SafeWriteError(
            "manifest.assertions.preserve_children must be a list"
        )
    normalized_assertions: list[dict[str, Any]] = []
    assertion_ids: set[str] = set()
    for index, raw_assertion in enumerate(raw_preserve):
        label = f"manifest.assertions.preserve_children[{index}]"
        assertion = _expect_mapping(raw_assertion, label)
        _expect_exact_keys(
            assertion,
            required={
                "id",
                "parent",
                "children",
                "require_exact_child_set",
            },
            label=label,
        )
        assertion_id = _expect_string(assertion["id"], f"{label}.id")
        if re.fullmatch(r"[A-Za-z0-9._-]{1,100}", assertion_id) is None:
            raise SafeWriteError(f"{label}.id has unsafe characters")
        if assertion_id in assertion_ids:
            raise SafeWriteError(f"duplicate assertion id {assertion_id!r}")
        assertion_ids.add(assertion_id)
        parent = _validated_identity(
            assertion["parent"],
            label=f"{label}.parent",
            include_old_parent=False,
        )
        if parent["type"] not in DEFORMER_OBJECT_TYPES:
            raise SafeWriteError(f"{label}.parent must be a deformer")
        raw_children = assertion["children"]
        if not isinstance(raw_children, list) or not raw_children:
            raise SafeWriteError(f"{label}.children must be a non-empty list")
        children = [
            _validated_identity(
                raw_child,
                label=f"{label}.children[{child_index}]",
                include_old_parent=False,
            )
            for child_index, raw_child in enumerate(raw_children)
        ]
        if assertion["require_exact_child_set"] is not True:
            raise SafeWriteError(
                f"{label}.require_exact_child_set must be true"
            )
        normalized_assertions.append(
            {
                "id": assertion_id,
                "parent": parent,
                "children": children,
                "require_exact_child_set": True,
            }
        )
    return root, operations, normalized_assertions, raw_bytes


def _validate_planned_deformer_graph(
    objects: list[SemanticObject],
    parent_refs: dict[str, str],
) -> None:
    deformers = {
        item.guid_ref: item
        for item in objects
        if item.object_type in DEFORMER_OBJECT_TYPES
    }
    for starting_ref in deformers:
        seen: list[str] = []
        current_ref = starting_ref
        while current_ref in deformers:
            if current_ref in seen:
                cycle = seen[seen.index(current_ref) :] + [current_ref]
                raise SafeWriteError(
                    "planned final hierarchy contains a cycle: "
                    + " -> ".join(deformers[item].name for item in cycle)
                )
            seen.append(current_ref)
            current_ref = parent_refs[current_ref]


def _plan_and_patch_manifest(
    main_xml: bytes,
    operations: list[BatchOperation],
    assertions: list[dict[str, Any]],
) -> tuple[
    bytes,
    list[dict[str, Any]],
    list[SemanticObject],
    list[SemanticObject],
    list[dict[str, Any]],
]:
    objects_before = _semantic_objects(main_xml)
    _validate_deformer_graph(objects_before)
    by_uuid: dict[str, SemanticObject] = {}
    for item in objects_before:
        if item.guid_uuid in by_uuid:
            raise SafeWriteError(f"duplicate object UUID {item.guid_uuid!r}")
        by_uuid[item.guid_uuid] = item

    resolved: list[
        tuple[BatchOperation, SemanticObject, SemanticObject | None]
    ] = []
    touched_fields: set[tuple[str, str]] = set()
    final_names = {
        item.guid_ref: item.name
        for item in objects_before
    }
    final_parents = {
        item.guid_ref: item.parent_ref
        for item in objects_before
    }
    for operation in operations:
        target = _resolve_semantic_object(
            objects_before,
            object_type=operation.target_type,
            name=operation.old_name,
            guid_uuid=operation.target_uuid,
            label=f"operation {operation.operation_id} target",
        )
        if target.parent_uuid != operation.old_parent_uuid:
            raise SafeWriteError(
                f"operation {operation.operation_id!r} expected old parent "
                f"{operation.old_parent_uuid!r}, found {target.parent_uuid!r}"
            )
        field_name = "parent" if operation.kind == "reparent" else "name"
        conflict_key = (target.guid_uuid, field_name)
        if conflict_key in touched_fields:
            raise SafeWriteError(
                f"conflicting operations target {target.name!r} "
                f"field {field_name!r}"
            )
        touched_fields.add(conflict_key)
        parent: SemanticObject | None = None
        if operation.kind == "reparent":
            if (
                operation.new_parent_type is None
                or operation.new_parent_name is None
                or operation.new_parent_uuid is None
            ):
                raise SafeWriteError("incomplete normalized reparent operation")
            parent = _resolve_semantic_object(
                objects_before,
                object_type=operation.new_parent_type,
                name=operation.new_parent_name,
                guid_uuid=operation.new_parent_uuid,
                label=f"operation {operation.operation_id} parent",
            )
            if target.parent_ref == parent.guid_ref:
                raise SafeWriteError(
                    f"operation {operation.operation_id!r} is a parent no-op"
                )
            final_parents[target.guid_ref] = parent.guid_ref
        else:
            if operation.new_name is None:
                raise SafeWriteError("incomplete normalized rename operation")
            same_named = [
                item
                for item in objects_before
                if item.object_type == target.object_type
                and item.name == target.name
            ]
            if len(same_named) != 1:
                raise SafeWriteError(
                    f"rename source name {target.name!r} is ambiguous "
                    f"within type {target.object_type!r}"
                )
            if operation.new_name == target.name:
                raise SafeWriteError(
                    f"operation {operation.operation_id!r} is a rename no-op"
                )
            final_names[target.guid_ref] = operation.new_name
        resolved.append((operation, target, parent))

    renamed_targets = {
        target.guid_ref
        for operation, target, _ in resolved
        if operation.kind == "rename"
    }
    for target_ref in renamed_targets:
        final_name = final_names[target_ref]
        collisions = [
            item
            for item in objects_before
            if item.guid_ref != target_ref
            and final_names[item.guid_ref] == final_name
        ]
        if collisions:
            raise SafeWriteError(
                f"planned name {final_name!r} collides with "
                + ", ".join(item.name for item in collisions)
            )
    _validate_planned_deformer_graph(objects_before, final_parents)

    assertion_proof: list[dict[str, Any]] = []
    for assertion in assertions:
        parent_identity = assertion["parent"]
        parent = _resolve_semantic_object(
            objects_before,
            object_type=parent_identity["type"],
            name=parent_identity["old_name"],
            guid_uuid=parent_identity["uuid"],
            label=f"assertion {assertion['id']} parent",
        )
        expected_children = [
            _resolve_semantic_object(
                objects_before,
                object_type=child["type"],
                name=child["old_name"],
                guid_uuid=child["uuid"],
                label=f"assertion {assertion['id']} child",
            )
            for child in assertion["children"]
        ]
        expected_refs = {child.guid_ref for child in expected_children}
        actual_initial_refs = {
            item.guid_ref
            for item in objects_before
            if item.parent_ref == parent.guid_ref
        }
        actual_final_refs = {
            item.guid_ref
            for item in objects_before
            if final_parents[item.guid_ref] == parent.guid_ref
        }
        if actual_initial_refs != expected_refs:
            raise SafeWriteError(
                f"assertion {assertion['id']!r} initial child set differs"
            )
        if actual_final_refs != expected_refs:
            raise SafeWriteError(
                f"assertion {assertion['id']!r} final child set differs"
            )
        assertion_proof.append(
            {
                "id": assertion["id"],
                "parent_guid": parent.guid_uuid,
                "parent_name_before": parent.name,
                "parent_name_after": final_names[parent.guid_ref],
                "child_guids": sorted(child.guid_uuid for child in expected_children),
                "child_names": sorted(child.name for child in expected_children),
                "exact_child_set_preserved": True,
            }
        )

    current_xml = main_xml
    whitelist: list[dict[str, Any]] = []
    for operation, target, parent in resolved:
        before_sha = _sha256(current_xml)
        if operation.kind == "reparent":
            if parent is None:
                raise SafeWriteError("missing resolved parent")
            patched, patch = _patch_parent_ref_for_record(
                current_xml,
                target=target,
                expected_old_ref=target.parent_ref,
                new_parent=parent,
            )
        else:
            if operation.new_name is None:
                raise SafeWriteError("missing resolved new name")
            patched, patch = _patch_name_for_record(
                current_xml,
                target=target,
                expected_old_name=target.name,
                new_name=operation.new_name,
            )
        patch.update(
            {
                "operation_id": operation.operation_id,
                "operation": operation.kind,
                "main_xml_sha256_before_step": before_sha,
                "main_xml_sha256_after_step": _sha256(patched),
            }
        )
        whitelist.append(patch)
        current_xml = patched

    objects_after = _semantic_objects(current_xml)
    _validate_deformer_graph(objects_after)
    after_by_uuid = {
        item.guid_uuid: item
        for item in objects_after
    }
    if set(after_by_uuid) != set(by_uuid):
        raise SafeWriteError("batch changed the set of serialized object UUIDs")
    for before in objects_before:
        after = after_by_uuid[before.guid_uuid]
        if (
            after.object_type != before.object_type
            or after.source_ref != before.source_ref
            or after.guid_ref != before.guid_ref
            or after.guid_note != before.guid_note
        ):
            raise SafeWriteError(
                f"batch changed immutable identity of {before.name!r}"
            )
        if after.name != final_names[before.guid_ref]:
            raise SafeWriteError(f"final name mismatch for {before.name!r}")
        if after.parent_ref != final_parents[before.guid_ref]:
            raise SafeWriteError(f"final parent mismatch for {before.name!r}")

    return (
        current_xml,
        whitelist,
        objects_before,
        objects_after,
        assertion_proof,
    )


def _entry_rows(data: bytes, archive: CaffArchive) -> list[dict[str, Any]]:
    return [
        {
            "path": entry.path,
            "tag": entry.tag,
            "start": entry.start,
            "size": entry.size,
            "obfuscated": entry.obfuscated,
            "compression": f"0x{entry.compression:02X}",
            "stored_sha256": _sha256(
                data[entry.start : entry.start + entry.size]
            ),
        }
        for entry in archive.entries
    ]


def _structural_inventory(path: Path) -> dict[str, Any]:
    try:
        result = inventory_file(
            path,
            max_xml_bytes=MAX_XML_BYTES,
            include_details=False,
        )
    except (InventoryError, OSError) as exc:
        raise SafeWriteError(f"inventory failed for {path}: {exc}") from exc
    return {
        "cubism_file_format_version": result["cubism_file_format_version"],
        "counts": result["counts"],
        "parameter_ids": result["parameter_ids"],
        "warp_deformer_names": result["warp_deformer_names"],
        "rotation_deformer_names": result["rotation_deformer_names"],
        "bound_objects": result["bound_objects"],
    }


def _write_new_file(path: Path, data: bytes) -> None:
    if path.suffix.casefold() != ".cmo3":
        raise SafeWriteError("output must use the .cmo3 extension")
    if "test" not in path.stem.casefold():
        raise SafeWriteError("output filename must contain TEST")
    if path.exists():
        raise SafeWriteError(f"output already exists and will not be overwritten: {path}")
    if not path.parent.is_dir():
        raise SafeWriteError(f"output directory does not exist: {path.parent}")

    created = False
    try:
        with path.open("xb") as handle:
            created = True
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if path.read_bytes() != data:
            raise SafeWriteError("filesystem verification differs from intended output")
    except Exception:
        if created and path.exists():
            path.unlink()
        raise


def _assert_safe_paths(source: Path, output: Path) -> tuple[Path, Path]:
    source = source.resolve(strict=True)
    output = output.resolve(strict=False)
    if not source.is_file():
        raise SafeWriteError(f"input is not a file: {source}")
    if source.suffix.casefold() != ".cmo3":
        raise SafeWriteError("input must use the .cmo3 extension")
    if source == output:
        raise SafeWriteError("input and output resolve to the same path")
    return source, output


def _compare_entry_preservation(
    before_data: bytes,
    before_archive: CaffArchive,
    after_data: bytes,
    after_archive: CaffArchive,
    main_may_change: bool,
) -> dict[str, Any]:
    before_rows = _entry_rows(before_data, before_archive)
    after_rows = _entry_rows(after_data, after_archive)
    if len(before_rows) != len(after_rows):
        raise SafeWriteError("entry count changed")

    changed_paths: list[str] = []
    for before, after in zip(before_rows, after_rows):
        if before == after:
            continue
        if (
            main_may_change
            and before["path"] == "main.xml"
            and after["path"] == "main.xml"
        ):
            allowed_keys = {"size", "stored_sha256"}
            if any(
                before[key] != after[key]
                for key in before
                if key not in allowed_keys
            ):
                raise SafeWriteError("main.xml metadata changed beyond size/hash")
            changed_paths.append("main.xml")
            continue
        raise SafeWriteError(f"unexpected entry change: {before['path']!r}")
    before_size_vector = [
        [row["path"], row["size"]]
        for row in before_rows
    ]
    after_size_vector = [
        [row["path"], row["size"]]
        for row in after_rows
    ]
    before_sizes_json = json.dumps(
        before_size_vector,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    after_sizes_json = json.dumps(
        after_size_vector,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    before_main = next(row for row in before_rows if row["path"] == "main.xml")
    after_main = next(row for row in after_rows if row["path"] == "main.xml")
    return {
        "entry_count": len(before_rows),
        "changed_stored_entries": changed_paths,
        "all_non_main_entries_byte_identical": all(
            before == after
            for before, after in zip(before_rows, after_rows)
            if before["path"] != "main.xml"
        ),
        "all_entry_sizes_identical": before_size_vector == after_size_vector,
        "entry_sizes_sha256_before": _sha256(before_sizes_json),
        "entry_sizes_sha256_after": _sha256(after_sizes_json),
        "stored_entry_bytes_total_before": sum(
            row["size"] for row in before_rows
        ),
        "stored_entry_bytes_total_after": sum(
            row["size"] for row in after_rows
        ),
        "main_xml_stored_bytes_before": before_main["size"],
        "main_xml_stored_bytes_after": after_main["size"],
    }


def _run_roundtrip(
    source: Path,
    output: Path,
    repack_main: bool,
) -> dict[str, Any]:
    source, output = _assert_safe_paths(source, output)
    source_before = source.read_bytes()
    source_before_sha = _sha256(source_before)
    (
        archive_before,
        _,
        _,
        source_zip_layout,
        main_before,
    ) = _validate_surgical_layout(source_before)

    if repack_main:
        output_data = _replace_main_xml(
            source_before,
            main_before,
            force_repack=True,
        )
    else:
        output_data = _replace_main_xml(source_before, main_before)

    _write_new_file(output, output_data)
    try:
        source_after = source.read_bytes()
        if _sha256(source_after) != source_before_sha:
            raise SafeWriteError("source changed during operation")
        written = output.read_bytes()
        archive_after, _, _, _, main_after = _validate_surgical_layout(written)
        if main_after != main_before:
            raise SafeWriteError("roundtrip changed logical main.xml")
        entry_proof = _compare_entry_preservation(
            source_before,
            archive_before,
            written,
            archive_after,
            main_may_change=repack_main,
        )
        source_inventory = _structural_inventory(source)
        output_inventory = _structural_inventory(output)
        if source_inventory != output_inventory:
            raise SafeWriteError("roundtrip changed structural inventory")
    except Exception:
        if output.exists():
            output.unlink()
        raise

    return {
        "status": "ok",
        "operation": "roundtrip_repack_main" if repack_main else "roundtrip_exact",
        "source": str(source),
        "output": str(output),
        "source_sha256_before": source_before_sha,
        "source_sha256_after": _sha256(source_after),
        "source_unchanged": source_before == source_after,
        "output_sha256": _sha256(written),
        "output_byte_identical_to_source": written == source_before,
        "main_xml_sha256_before": _sha256(main_before),
        "main_xml_sha256_after": _sha256(main_after),
        "main_xml_byte_identical": main_before == main_after,
        "compression_profile": {
            "source_zlib_level": source_zip_layout.zlib_level,
            "python_zlib_runtime": zlib.ZLIB_RUNTIME_VERSION,
        },
        "archive": entry_proof,
        "structural_inventory_identical": True,
    }


def _run_rename_deformer(
    source: Path,
    output: Path,
    old: str,
    new: str,
) -> dict[str, Any]:
    source, output = _assert_safe_paths(source, output)
    source_before = source.read_bytes()
    source_before_sha = _sha256(source_before)
    (
        archive_before,
        _,
        _,
        source_zip_layout,
        main_before,
    ) = _validate_surgical_layout(source_before)
    main_after_expected = _rename_one_deformer(main_before, old, new)
    output_data = _replace_main_xml(source_before, main_after_expected)

    _write_new_file(output, output_data)
    try:
        source_after = source.read_bytes()
        if _sha256(source_after) != source_before_sha:
            raise SafeWriteError("source changed during operation")
        written = output.read_bytes()
        archive_after, _, _, _, main_after = _validate_surgical_layout(written)
        if main_after != main_after_expected:
            raise SafeWriteError("written main.xml differs from exact expected patch")
        entry_proof = _compare_entry_preservation(
            source_before,
            archive_before,
            written,
            archive_after,
            main_may_change=True,
        )
        source_inventory = _structural_inventory(source)
        output_inventory = _structural_inventory(output)
        if source_inventory["counts"] != output_inventory["counts"]:
            raise SafeWriteError("deformer rename changed structural counts")
        if source_inventory["parameter_ids"] != output_inventory["parameter_ids"]:
            raise SafeWriteError("deformer rename changed parameter IDs")
        expected_warp = [
            new if name == old else name
            for name in source_inventory["warp_deformer_names"]
        ]
        expected_rotation = [
            new if name == old else name
            for name in source_inventory["rotation_deformer_names"]
        ]
        if output_inventory["warp_deformer_names"] != expected_warp:
            raise SafeWriteError("warp deformer inventory does not show exact rename")
        if output_inventory["rotation_deformer_names"] != expected_rotation:
            raise SafeWriteError("rotation deformer inventory does not show exact rename")
    except Exception:
        if output.exists():
            output.unlink()
        raise

    return {
        "status": "ok",
        "operation": "rename_deformer",
        "source": str(source),
        "output": str(output),
        "rename": {
            "old": old,
            "new": new,
            "same_utf8_length": len(old.encode("utf-8")) == len(new.encode("utf-8")),
        },
        "source_sha256_before": source_before_sha,
        "source_sha256_after": _sha256(source_after),
        "source_unchanged": source_before == source_after,
        "output_sha256": _sha256(written),
        "main_xml_sha256_before": _sha256(main_before),
        "main_xml_sha256_after": _sha256(main_after),
        "main_xml_bytes_before": len(main_before),
        "main_xml_bytes_after": len(main_after),
        "compression_profile": {
            "source_zlib_level": source_zip_layout.zlib_level,
            "python_zlib_runtime": zlib.ZLIB_RUNTIME_VERSION,
        },
        "archive": entry_proof,
        "structural_counts_identical": True,
        "parameter_ids_identical": True,
        "semantic_rename_verified": True,
    }


def _inventory_with_details(path: Path) -> dict[str, Any]:
    try:
        return inventory_file(
            path,
            max_xml_bytes=MAX_XML_BYTES,
            include_details=True,
        )
    except (InventoryError, OSError) as exc:
        raise SafeWriteError(f"inventory failed for {path}: {exc}") from exc


def _inventory_object(
    inventory: dict[str, Any],
    object_type: str,
    source_ref: str,
) -> dict[str, Any]:
    group_name = OBJECT_TYPE_SPECS[object_type][2]
    matches = [
        item
        for item in inventory["objects"][group_name]
        if item["source_ref"] == source_ref
    ]
    if len(matches) != 1:
        raise SafeWriteError(
            f"inventory expected one {object_type} source {source_ref!r}, "
            f"found {len(matches)}"
        )
    return matches[0]


def _verify_reparent_inventory(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    target: SemanticObject,
    parent: SemanticObject,
) -> tuple[dict[str, Any], dict[str, Any]]:
    invariant_keys = (
        "cubism_file_format_version",
        "counts",
        "parameter_ids",
        "warp_deformer_names",
        "rotation_deformer_names",
        "bound_objects",
        "parameters",
    )
    for key in invariant_keys:
        if before[key] != after[key]:
            raise SafeWriteError(f"reparent changed inventory field {key!r}")

    target_before = _inventory_object(before, target.object_type, target.source_ref)
    target_after = _inventory_object(after, target.object_type, target.source_ref)
    expected_target_after = dict(target_before)
    expected_target_after["parent_deformer"] = parent.name
    expected_target_after["parent_deformer_guid_ref"] = parent.guid_ref
    if target_after != expected_target_after:
        raise SafeWriteError(
            "target inventory changed beyond its parent deformer fields"
        )

    for object_type, (_, _, group_name) in OBJECT_TYPE_SPECS.items():
        before_group = before["objects"][group_name]
        after_group = after["objects"][group_name]
        if len(before_group) != len(after_group):
            raise SafeWriteError(
                f"reparent changed object count for {object_type!r}"
            )
        for before_item, after_item in zip(before_group, after_group):
            if before_item["source_ref"] == target.source_ref:
                continue
            if before_item != after_item:
                raise SafeWriteError(
                    f"reparent changed non-target object "
                    f"{before_item['name']!r}"
                )
    if before["objects"]["parts"] != after["objects"]["parts"]:
        raise SafeWriteError("reparent changed one or more Parts")
    return target_before, target_after


def _verify_batch_inventory(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    objects_before: list[SemanticObject],
    objects_after: list[SemanticObject],
) -> list[dict[str, Any]]:
    invariant_keys = (
        "cubism_file_format_version",
        "counts",
        "parameter_ids",
        "parameters",
    )
    for key in invariant_keys:
        if before[key] != after[key]:
            raise SafeWriteError(f"batch changed inventory field {key!r}")

    expected_objects = copy.deepcopy(before["objects"])
    after_by_source = {
        item.source_ref: item
        for item in objects_after
    }
    after_deformer_names = {
        item.guid_ref: item.name
        for item in objects_after
        if item.object_type in DEFORMER_OBJECT_TYPES
    }
    for before_object in objects_before:
        group_name = OBJECT_TYPE_SPECS[before_object.object_type][2]
        matches = [
            item
            for item in expected_objects[group_name]
            if item["source_ref"] == before_object.source_ref
        ]
        if len(matches) != 1:
            raise SafeWriteError(
                f"expected inventory lacks unique source "
                f"{before_object.source_ref!r}"
            )
        expected_item = matches[0]
        final_object = after_by_source[before_object.source_ref]
        expected_item["name"] = final_object.name
        if final_object.parent_ref.startswith(INLINE_PARENT_REF_PREFIX):
            # The read-only inventory intentionally reports an inline ROOT
            # sentinel as ``None`` because there is no shared ``xs.ref`` and
            # no deformer object to name.
            expected_item["parent_deformer_guid_ref"] = None
            expected_item["parent_deformer"] = None
        else:
            expected_item["parent_deformer_guid_ref"] = final_object.parent_ref
            expected_item["parent_deformer"] = after_deformer_names.get(
                final_object.parent_ref
            )
    if expected_objects != after["objects"]:
        raise SafeWriteError(
            "batch inventory object diff exceeds planned name/parent fields"
        )

    expected_warp_names = [
        item["name"]
        for item in expected_objects["warp_deformers"]
    ]
    expected_rotation_names = [
        item["name"]
        for item in expected_objects["rotation_deformers"]
    ]
    if after["warp_deformer_names"] != expected_warp_names:
        raise SafeWriteError("batch warp deformer name inventory mismatch")
    if after["rotation_deformer_names"] != expected_rotation_names:
        raise SafeWriteError("batch rotation deformer name inventory mismatch")

    before_by_source = {
        item.source_ref: item
        for item in objects_before
    }
    renamed_by_kind_and_name: dict[tuple[str, str], str] = {}
    for source_ref, before_object in before_by_source.items():
        final_object = after_by_source[source_ref]
        if before_object.name == final_object.name:
            continue
        group_name = OBJECT_TYPE_SPECS[before_object.object_type][2]
        key = (group_name, before_object.name)
        if key in renamed_by_kind_and_name:
            raise SafeWriteError(
                f"cannot unambiguously normalize bound object name "
                f"{before_object.name!r}"
            )
        renamed_by_kind_and_name[key] = final_object.name
    expected_bound_objects = copy.deepcopy(before["bound_objects"])
    for item in expected_bound_objects:
        replacement = renamed_by_kind_and_name.get(
            (item["kind"], item["name"])
        )
        if replacement is not None:
            item["name"] = replacement
    if expected_bound_objects != after["bound_objects"]:
        raise SafeWriteError("batch changed bound object inventory unexpectedly")

    changed_objects: list[dict[str, Any]] = []
    for before_object in objects_before:
        final_object = after_by_source[before_object.source_ref]
        if (
            before_object.name != final_object.name
            or before_object.parent_ref != final_object.parent_ref
        ):
            changed_objects.append(
                {
                    "type": before_object.object_type,
                    "source_ref": before_object.source_ref,
                    "guid_uuid": before_object.guid_uuid,
                    "name_before": before_object.name,
                    "name_after": final_object.name,
                    "parent_ref_before": before_object.parent_ref,
                    "parent_ref_after": final_object.parent_ref,
                    "parent_uuid_before": before_object.parent_uuid,
                    "parent_uuid_after": final_object.parent_uuid,
                }
            )
    return changed_objects


def _run_reparent_object(
    source: Path,
    output: Path,
    *,
    object_type: str,
    object_name: str,
    object_guid: str,
    expected_parent_guid: str,
    parent_type: str,
    parent_name: str,
    parent_guid: str,
) -> dict[str, Any]:
    source, output = _assert_safe_paths(source, output)
    source_before = source.read_bytes()
    source_before_sha = _sha256(source_before)
    (
        archive_before,
        _,
        _,
        source_zip_layout,
        main_before,
    ) = _validate_surgical_layout(source_before)
    (
        main_after_expected,
        target,
        parent,
        xml_patch,
    ) = _reparent_one_object(
        main_before,
        object_type=object_type,
        object_name=object_name,
        object_guid=object_guid,
        expected_parent_guid=expected_parent_guid,
        parent_type=parent_type,
        parent_name=parent_name,
        parent_guid=parent_guid,
    )
    output_data = _replace_main_xml(source_before, main_after_expected)

    _write_new_file(output, output_data)
    try:
        source_after = source.read_bytes()
        if _sha256(source_after) != source_before_sha:
            raise SafeWriteError("source changed during operation")
        written = output.read_bytes()
        archive_after, _, _, _, main_after = _validate_surgical_layout(written)
        if main_after != main_after_expected:
            raise SafeWriteError("written main.xml differs from exact parent patch")
        entry_proof = _compare_entry_preservation(
            source_before,
            archive_before,
            written,
            archive_after,
            main_may_change=True,
        )
        inventory_before = _inventory_with_details(source)
        inventory_after = _inventory_with_details(output)
        target_inventory_before, target_inventory_after = (
            _verify_reparent_inventory(
                inventory_before,
                inventory_after,
                target=target,
                parent=parent,
            )
        )
    except Exception:
        if output.exists():
            output.unlink()
        raise

    return {
        "status": "ok",
        "operation": "reparent_object",
        "source": str(source),
        "output": str(output),
        "source_sha256_before": source_before_sha,
        "source_sha256_after": _sha256(source_after),
        "source_unchanged": source_before == source_after,
        "output_sha256": _sha256(written),
        "main_xml_sha256_before": _sha256(main_before),
        "main_xml_sha256_after": _sha256(main_after),
        "target": {
            "type": target.object_type,
            "name": target.name,
            "source_ref": target.source_ref,
            "guid_ref": target.guid_ref,
            "guid_uuid": target.guid_uuid,
        },
        "old_parent": {
            "guid_ref": target.parent_ref,
            "guid_uuid": target.parent_uuid,
            "guid_note": target.parent_note,
        },
        "new_parent": {
            "type": parent.object_type,
            "name": parent.name,
            "source_ref": parent.source_ref,
            "guid_ref": parent.guid_ref,
            "guid_uuid": parent.guid_uuid,
            "guid_note": parent.guid_note,
        },
        "xml_patch": xml_patch,
        "compression_profile": {
            "source_zlib_level": source_zip_layout.zlib_level,
            "python_zlib_runtime": zlib.ZLIB_RUNTIME_VERSION,
        },
        "archive": entry_proof,
        "inventory": {
            "counts_identical": True,
            "parameters_identical": True,
            "all_non_target_objects_identical": True,
            "target_before": target_inventory_before,
            "target_after": target_inventory_after,
        },
        "cycle_check_before_and_after": "ok",
        "exact_parent_field_patch_verified": True,
    }


def _run_apply_manifest(
    manifest_path: Path,
    source: Path,
    output: Path,
) -> dict[str, Any]:
    (
        manifest,
        operations,
        assertions,
        manifest_bytes,
    ) = _read_batch_manifest(manifest_path)
    source, output = _assert_safe_paths(source, output)
    if source.name != manifest["source"]["required_filename"]:
        raise SafeWriteError(
            f"source filename {source.name!r} does not match manifest "
            f"{manifest['source']['required_filename']!r}"
        )
    if output.name != manifest["output"]["required_filename"]:
        raise SafeWriteError(
            f"output filename {output.name!r} does not match manifest "
            f"{manifest['output']['required_filename']!r}"
        )

    source_before = source.read_bytes()
    source_before_sha = _sha256(source_before)
    if source_before_sha != manifest["source"]["sha256"]:
        raise SafeWriteError(
            f"source SHA-256 {source_before_sha} does not match manifest "
            f"{manifest['source']['sha256']}"
        )
    (
        archive_before,
        _,
        _,
        source_zip_layout,
        main_before,
    ) = _validate_surgical_layout(source_before)
    (
        main_after_expected,
        whitelist,
        objects_before,
        objects_after,
        assertion_proof,
    ) = _plan_and_patch_manifest(
        main_before,
        operations,
        assertions,
    )
    if main_after_expected == main_before:
        raise SafeWriteError("manifest produced no logical XML change")
    output_data = _replace_main_xml(source_before, main_after_expected)

    # All schema, identity, graph, assertion, and in-memory archive validation
    # has completed before this exclusive create.
    _write_new_file(output, output_data)
    try:
        source_after = source.read_bytes()
        if _sha256(source_after) != source_before_sha:
            raise SafeWriteError("source changed during manifest transaction")
        written = output.read_bytes()
        archive_after, _, _, _, main_after = _validate_surgical_layout(written)
        if main_after != main_after_expected:
            raise SafeWriteError(
                "written main.xml differs from manifest transaction result"
            )
        entry_proof = _compare_entry_preservation(
            source_before,
            archive_before,
            written,
            archive_after,
            main_may_change=True,
        )
        inventory_before = _inventory_with_details(source)
        inventory_after = _inventory_with_details(output)
        changed_objects = _verify_batch_inventory(
            inventory_before,
            inventory_after,
            objects_before=objects_before,
            objects_after=objects_after,
        )
        if len(changed_objects) != len(
            {
                operation.target_uuid
                for operation in operations
            }
        ):
            raise SafeWriteError(
                "changed object set differs from manifest target set"
            )
    except Exception:
        if output.exists():
            output.unlink()
        raise

    return {
        "status": "ok",
        "operation": "apply_manifest",
        "transaction": {
            "id": manifest["transaction_id"],
            "description": manifest["description"],
            "manifest_path": str(manifest_path.resolve()),
            "manifest_sha256": _sha256(manifest_bytes),
            "operation_count": len(operations),
            "assertion_count": len(assertions),
            "atomic_preflight_before_write": True,
            "conflicting_field_writes_refused": True,
        },
        "source": str(source),
        "output": str(output),
        "source_sha256_before": source_before_sha,
        "source_sha256_after": _sha256(source_after),
        "source_unchanged": source_before == source_after,
        "output_sha256": _sha256(written),
        "main_xml_sha256_before": _sha256(main_before),
        "main_xml_sha256_after": _sha256(main_after),
        "main_xml_bytes_before": len(main_before),
        "main_xml_bytes_after": len(main_after),
        "compression_profile": {
            "source_zlib_level": source_zip_layout.zlib_level,
            "python_zlib_runtime": zlib.ZLIB_RUNTIME_VERSION,
        },
        "diff_whitelist": {
            "patch_count": len(whitelist),
            "only_manifested_fields_patched": True,
            "patches": whitelist,
        },
        "archive": entry_proof,
        "inventory": {
            "full_object_inventory_verified": True,
            "counts_identical": True,
            "parameters_identical": True,
            "parts_identical": True,
            "changed_objects": changed_objects,
        },
        "assertions": assertion_proof,
        "final_deformer_graph_acyclic": True,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    roundtrip = subparsers.add_parser(
        "roundtrip",
        help="write a verified TEST roundtrip without changing logical content",
    )
    roundtrip.add_argument("input", type=Path)
    roundtrip.add_argument("output", type=Path)
    roundtrip.add_argument(
        "--repack-main",
        action="store_true",
        help=(
            "exercise DEFLATE/CAFF replacement while preserving exact logical "
            "main.xml (default is a byte-identical conservative copy)"
        ),
    )

    rename = subparsers.add_parser(
        "rename-deformer",
        help="rename exactly one warp/rotation deformer in a new TEST copy",
    )
    rename.add_argument("input", type=Path)
    rename.add_argument("output", type=Path)
    rename.add_argument("--old", required=True)
    rename.add_argument("--new", required=True)

    reparent = subparsers.add_parser(
        "reparent-object",
        help=(
            "reparent one existing object to one existing deformer in a new "
            "TEST copy"
        ),
    )
    reparent.add_argument("input", type=Path)
    reparent.add_argument("output", type=Path)
    reparent.add_argument(
        "--object-type",
        required=True,
        choices=sorted(OBJECT_TYPE_SPECS),
    )
    reparent.add_argument("--object-name", required=True)
    reparent.add_argument("--object-guid", required=True)
    reparent.add_argument("--expected-parent-guid", required=True)
    reparent.add_argument(
        "--parent-type",
        required=True,
        choices=sorted(DEFORMER_OBJECT_TYPES),
    )
    reparent.add_argument("--parent-name", required=True)
    reparent.add_argument("--parent-guid", required=True)

    apply_manifest = subparsers.add_parser(
        "apply-manifest",
        help=(
            "apply a strict batch manifest atomically to one new TEST copy"
        ),
    )
    apply_manifest.add_argument("manifest", type=Path)
    apply_manifest.add_argument("input", type=Path)
    apply_manifest.add_argument("output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "roundtrip":
            report = _run_roundtrip(
                args.input,
                args.output,
                repack_main=args.repack_main,
            )
        elif args.command == "rename-deformer":
            report = _run_rename_deformer(
                args.input,
                args.output,
                old=args.old,
                new=args.new,
            )
        elif args.command == "reparent-object":
            report = _run_reparent_object(
                args.input,
                args.output,
                object_type=args.object_type,
                object_name=args.object_name,
                object_guid=args.object_guid,
                expected_parent_guid=args.expected_parent_guid,
                parent_type=args.parent_type,
                parent_name=args.parent_name,
                parent_guid=args.parent_guid,
            )
        else:
            report = _run_apply_manifest(
                args.manifest,
                args.input,
                args.output,
            )
    except (SafeWriteError, InventoryError, OSError) as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
