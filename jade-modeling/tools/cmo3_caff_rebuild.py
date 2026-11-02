#!/usr/bin/env python3
"""Small, strict CAFF rebuilder for Cubism texture-atlas work.

The public API adds one or more raw PNG members immediately before
``main.xml`` and replaces ``main.xml`` in one in-memory transaction.  Existing
member payloads are copied byte-for-byte.  Existing metadata records are also
copied byte-for-byte except for the absolute member starts and the replaced
``main.xml`` size.

Cubism stores image resources as raw CAFF members (compression ``0x10``),
optionally XOR-obfuscated.  ``main.xml`` is different: it remains a ZIP local
DEFLATE stream with a trailing data descriptor, using the exact source header
and a reproducible source compression level.

This module deliberately has no file-writing API.  Callers remain responsible
for copy-on-write filenames, atomic writes, and higher-level semantic checks.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Sequence

from cmo3_inventory import ArchiveEntry, BufferReader, CaffArchive, RAW_COMPRESSION
from cmo3_safe_roundtrip import (
    CAFF_GUARD,
    MAX_XML_BYTES,
    SafeWriteError,
    _build_zip_local_member,
    _validate_surgical_layout,
)


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_METADATA_STRING_BYTES = 1024 * 1024


@dataclass(frozen=True)
class RawMember:
    """A new raw, XOR-obfuscated CAFF member."""

    path: str
    contents: bytes
    tag: str = ""


@dataclass(frozen=True)
class _RawMetadataRecord:
    entry: ArchiveEntry
    raw: bytes
    start_offset: int
    size_offset: int
    unknown: bytes


def _read_obfuscated_beb128(reader: BufferReader, key_low: int) -> int:
    value = 0
    for _ in range(10):
        decoded = reader.u8() ^ key_low
        value = (value << 7) | (decoded & 0x7F)
        if decoded & 0x80 == 0:
            return value
    raise SafeWriteError("invalid or excessively long CAFF BEB128 integer")


def _read_obfuscated_string(reader: BufferReader, key_low: int) -> str:
    length = _read_obfuscated_beb128(reader, key_low)
    if length > MAX_METADATA_STRING_BYTES:
        raise SafeWriteError("CAFF metadata string exceeds 1 MiB")
    raw = reader.read(length)
    try:
        return bytes(byte ^ key_low for byte in raw).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SafeWriteError("invalid UTF-8 in CAFF metadata") from exc


def _encode_obfuscated_beb128(value: int, key_low: int) -> bytes:
    if value < 0:
        raise SafeWriteError("cannot encode a negative CAFF BEB128 integer")
    groups = [value & 0x7F]
    value >>= 7
    while value:
        groups.append(value & 0x7F)
        value >>= 7
    groups.reverse()
    clear = bytes(
        group | (0x80 if index < len(groups) - 1 else 0)
        for index, group in enumerate(groups)
    )
    return bytes(byte ^ key_low for byte in clear)


def _encode_obfuscated_string(value: str, key_low: int) -> bytes:
    try:
        raw = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise SafeWriteError("CAFF member metadata is not valid UTF-8") from exc
    if len(raw) > MAX_METADATA_STRING_BYTES:
        raise SafeWriteError("CAFF metadata string exceeds 1 MiB")
    return _encode_obfuscated_beb128(len(raw), key_low) + bytes(
        byte ^ key_low for byte in raw
    )


def _metadata_records(
    data: bytes,
    archive: CaffArchive,
) -> tuple[bytes, bytes, list[_RawMetadataRecord], int]:
    """Return header/count bytes, exact records, and old metadata end."""

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

    reader.read(8 + 20 + 8)
    count_offset = reader.offset
    count_raw = reader.read(4)
    entry_count = int.from_bytes(count_raw, "big") ^ key_u32
    if entry_count != len(archive.entries):
        raise SafeWriteError(
            f"entry count mismatch: table={entry_count}, parser={len(archive.entries)}"
        )

    records: list[_RawMetadataRecord] = []
    for expected in archive.entries:
        record_start = reader.offset
        path = _read_obfuscated_string(reader, key_low)
        tag = _read_obfuscated_string(reader, key_low)
        start_offset = reader.offset - record_start
        start = reader.u64be() ^ key_u64
        size_offset = reader.offset - record_start
        size = reader.u32be() ^ key_u32
        obfuscated = bool(reader.u8() ^ key_low)
        compression = reader.u8() ^ key_low
        unknown = reader.read(8)
        record_end = reader.offset
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
        records.append(
            _RawMetadataRecord(
                entry=expected,
                raw=data[record_start:record_end],
                start_offset=start_offset,
                size_offset=size_offset,
                unknown=unknown,
            )
        )
    return data[:count_offset], count_raw, records, reader.offset


def _new_record(
    member: RawMember,
    *,
    start: int,
    unknown: bytes,
    key_u32: int,
    key_low: int,
    key_u64: int,
) -> bytes:
    if len(unknown) != 8:
        raise SafeWriteError("CAFF metadata unknown field must contain 8 bytes")
    if start > 0xFFFF_FFFF_FFFF_FFFF:
        raise SafeWriteError("new CAFF member start exceeds 64-bit range")
    if len(member.contents) > 0xFFFF_FFFF:
        raise SafeWriteError("new CAFF member exceeds 32-bit size range")
    return b"".join(
        (
            _encode_obfuscated_string(member.path, key_low),
            _encode_obfuscated_string(member.tag, key_low),
            struct.pack(">Q", start ^ key_u64),
            struct.pack(">I", len(member.contents) ^ key_u32),
            bytes((1 ^ key_low, RAW_COMPRESSION ^ key_low)),
            unknown,
        )
    )


def _patched_existing_record(
    record: _RawMetadataRecord,
    *,
    start: int,
    size: int | None,
    key_u32: int,
    key_u64: int,
) -> bytes:
    if start > 0xFFFF_FFFF_FFFF_FFFF:
        raise SafeWriteError("CAFF member start exceeds 64-bit range")
    patched = bytearray(record.raw)
    patched[record.start_offset : record.start_offset + 8] = struct.pack(
        ">Q", start ^ key_u64
    )
    if size is not None:
        if size > 0xFFFF_FFFF:
            raise SafeWriteError("CAFF member exceeds 32-bit size range")
        patched[record.size_offset : record.size_offset + 4] = struct.pack(
            ">I", size ^ key_u32
        )
    return bytes(patched)


def _validate_new_members(
    archive: CaffArchive,
    members: Sequence[RawMember],
) -> None:
    if not members:
        raise SafeWriteError("at least one new raw member is required")
    existing_paths = {entry.path for entry in archive.entries}
    new_paths: set[str] = set()
    for member in members:
        if not member.path or "\x00" in member.path:
            raise SafeWriteError("new CAFF member path is empty or contains NUL")
        if member.path in existing_paths or member.path in new_paths:
            raise SafeWriteError(f"duplicate CAFF member path {member.path!r}")
        if not member.path.casefold().endswith(".png"):
            raise SafeWriteError(f"new member {member.path!r} is not a PNG path")
        if not member.contents.startswith(PNG_SIGNATURE):
            raise SafeWriteError(f"new member {member.path!r} lacks a PNG signature")
        new_paths.add(member.path)


def _patched_preview_header(
    header: bytes,
    *,
    old_metadata_end: int,
    old_first_start: int,
    old_entries: Sequence[ArchiveEntry],
    new_starts: dict[str, int],
    metadata_delta: int,
) -> bytes:
    """Relocate the optional preview pointer while preserving its other bytes."""

    # The preview start occupies bytes 34..41 in the fixed CAFF header.
    old_preview_start = int.from_bytes(header[34:42], "big")
    if old_preview_start == 0:
        return header

    new_preview_start: int | None = None
    if old_metadata_end <= old_preview_start < old_first_start:
        new_preview_start = old_preview_start + metadata_delta
    else:
        for entry in old_entries:
            if entry.start <= old_preview_start < entry.start + entry.size:
                new_preview_start = (
                    new_starts[entry.path] + old_preview_start - entry.start
                )
                break
    if new_preview_start is None:
        raise SafeWriteError("cannot safely relocate the CAFF preview start")

    patched = bytearray(header)
    patched[34:42] = struct.pack(">Q", new_preview_start)
    return bytes(patched)


def rebuild_caff_with_raw_members(
    data: bytes,
    *,
    members: Sequence[RawMember],
    replacement_main_xml: bytes,
) -> bytes:
    """Add raw PNG members and replace ``main.xml`` without filesystem writes.

    New members are inserted immediately before the last ``main.xml`` member.
    The source must satisfy the conservative layout accepted by
    :mod:`cmo3_safe_roundtrip`: metadata and physical order agree, all payloads
    are contiguous, and ``main.xml`` ends immediately before the ``bc`` guard.
    """

    if len(replacement_main_xml) > MAX_XML_BYTES:
        raise SafeWriteError("replacement main.xml exceeds 256 MiB")
    archive, main, _, main_zip, _ = _validate_surgical_layout(data)
    _validate_new_members(archive, members)

    physical = sorted(archive.entries, key=lambda entry: entry.start)
    if physical != archive.entries:
        raise SafeWriteError("CAFF metadata order differs from physical order")

    header, _, records, old_metadata_end = _metadata_records(data, archive)
    first_start = archive.entries[0].start
    pre_payload_gap = data[old_metadata_end:first_start]
    main_clear = _build_zip_local_member(main_zip, replacement_main_xml)

    key_u32 = archive.obfuscation_key_signed & 0xFFFF_FFFF
    key_low = key_u32 & 0xFF
    key_u64 = (
        (archive.obfuscation_key_signed << 32) | archive.obfuscation_key_signed
    ) & 0xFFFF_FFFF_FFFF_FFFF
    main_stored = bytes(byte ^ key_low for byte in main_clear)
    new_stored = [
        bytes(byte ^ key_low for byte in member.contents) for member in members
    ]

    main_index = archive.entries.index(main)
    record_by_path = {record.entry.path: record for record in records}
    unknown_template = next(
        (
            record.unknown
            for record in records
            if record.entry.compression == RAW_COMPRESSION
            and record.entry.path.casefold().endswith(".png")
        ),
        records[0].unknown,
    )

    # Record lengths are independent of absolute starts, so placeholders give
    # the final metadata length before physical offsets are assigned.
    placeholder_new_records = [
        _new_record(
            member,
            start=0,
            unknown=unknown_template,
            key_u32=key_u32,
            key_low=key_low,
            key_u64=key_u64,
        )
        for member in members
    ]
    new_count = len(archive.entries) + len(members)
    count_bytes = struct.pack(">I", new_count ^ key_u32)
    new_metadata_end = (
        len(header)
        + len(count_bytes)
        + sum(len(record.raw) for record in records)
        + sum(len(record) for record in placeholder_new_records)
    )

    payload_start = new_metadata_end + len(pre_payload_gap)
    new_starts: dict[str, int] = {}
    cursor = payload_start
    for entry in archive.entries[:main_index]:
        new_starts[entry.path] = cursor
        cursor += entry.size
    for member, stored in zip(members, new_stored, strict=True):
        new_starts[member.path] = cursor
        cursor += len(stored)
    new_starts[main.path] = cursor
    cursor += len(main_stored)

    existing_records_before_main = [
        _patched_existing_record(
            record_by_path[entry.path],
            start=new_starts[entry.path],
            size=None,
            key_u32=key_u32,
            key_u64=key_u64,
        )
        for entry in archive.entries[:main_index]
    ]
    new_records = [
        _new_record(
            member,
            start=new_starts[member.path],
            unknown=unknown_template,
            key_u32=key_u32,
            key_low=key_low,
            key_u64=key_u64,
        )
        for member in members
    ]
    main_record = _patched_existing_record(
        record_by_path[main.path],
        start=new_starts[main.path],
        size=len(main_stored),
        key_u32=key_u32,
        key_u64=key_u64,
    )
    metadata_delta = new_metadata_end - old_metadata_end
    header = _patched_preview_header(
        header,
        old_metadata_end=old_metadata_end,
        old_first_start=first_start,
        old_entries=archive.entries,
        new_starts=new_starts,
        metadata_delta=metadata_delta,
    )

    old_payloads = [
        data[entry.start : entry.start + entry.size]
        for entry in archive.entries[:main_index]
    ]
    result = b"".join(
        (
            header,
            count_bytes,
            *existing_records_before_main,
            *new_records,
            main_record,
            pre_payload_gap,
            *old_payloads,
            *new_stored,
            main_stored,
            CAFF_GUARD,
        )
    )
    if len(result) != cursor + len(CAFF_GUARD):
        raise SafeWriteError("rebuilt CAFF size disagrees with assigned offsets")

    output_archive, output_main, _, _, output_xml = _validate_surgical_layout(result)
    if output_xml != replacement_main_xml:
        raise SafeWriteError("rebuilt CAFF main.xml differs from replacement")
    if output_main.start != new_starts[main.path]:
        raise SafeWriteError("rebuilt CAFF main.xml start is incorrect")
    expected_paths = [
        *(entry.path for entry in archive.entries[:main_index]),
        *(member.path for member in members),
        main.path,
    ]
    if [entry.path for entry in output_archive.entries] != expected_paths:
        raise SafeWriteError("rebuilt CAFF member ordering is incorrect")

    output_by_path = {entry.path: entry for entry in output_archive.entries}
    for entry in archive.entries[:main_index]:
        after = output_by_path[entry.path]
        if (
            entry.path,
            entry.tag,
            entry.size,
            entry.obfuscated,
            entry.compression,
        ) != (
            after.path,
            after.tag,
            after.size,
            after.obfuscated,
            after.compression,
        ):
            raise SafeWriteError(f"metadata changed for {entry.path!r}")
        old_stored = data[entry.start : entry.start + entry.size]
        new_stored_payload = result[after.start : after.start + after.size]
        if new_stored_payload != old_stored:
            raise SafeWriteError(f"stored payload changed for {entry.path!r}")
    for member in members:
        after = output_by_path[member.path]
        if (
            after.tag != member.tag
            or after.compression != RAW_COMPRESSION
            or not after.obfuscated
        ):
            raise SafeWriteError(f"new member metadata is incorrect for {member.path!r}")
        if output_archive.read_entry(after, len(member.contents)) != member.contents:
            raise SafeWriteError(f"new member payload is incorrect for {member.path!r}")
    return result


def rebuild_caff_with_png(
    data: bytes,
    *,
    png_path: str,
    png_bytes: bytes,
    replacement_main_xml: bytes,
) -> bytes:
    """Convenience wrapper for adding exactly one raw PNG member."""

    return rebuild_caff_with_raw_members(
        data,
        members=(RawMember(path=png_path, contents=png_bytes),),
        replacement_main_xml=replacement_main_xml,
    )
