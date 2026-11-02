#!/usr/bin/env python3
"""
Read-only ArtMesh topology inventory for Live2D Cubism Editor .cmo3 files.

The tool reuses the bounded CAFF reader from ``cmo3_inventory.py`` and inspects
only the serialized ``main.xml`` member.  It reports declared and parsed vertex
/ triangle counts, malformed indices, unused vertices, degenerate triangles,
and aggregate density.  It never writes to the inspected model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterable

from cmo3_inventory import (
    CaffArchive,
    DEFAULT_MAX_XML_BYTES,
    InventoryError,
    _id_string,
    _source_name,
)


def _unique_array(
    source: ET.Element, tag: str, serialized_name: str
) -> ET.Element:
    matches = [
        child
        for child in source.findall(tag)
        if child.get("xs.n") == serialized_name
    ]
    if len(matches) != 1:
        raise InventoryError(
            f"{_source_name(source)!r}: expected one {tag} "
            f"{serialized_name!r}, found {len(matches)}"
        )
    return matches[0]


def _parse_numeric_array(
    node: ET.Element, converter: type[int] | type[float], label: str
) -> list[int] | list[float]:
    raw = (node.text or "").split()
    declared_text = node.get("count")
    try:
        declared = int(declared_text or "")
    except ValueError as exc:
        raise InventoryError(f"{label}: invalid count {declared_text!r}") from exc
    if declared != len(raw):
        raise InventoryError(
            f"{label}: declared count {declared}, parsed {len(raw)}"
        )
    try:
        values = [converter(token) for token in raw]
    except ValueError as exc:
        raise InventoryError(f"{label}: invalid numeric token") from exc
    if converter is float and any(not math.isfinite(value) for value in values):
        raise InventoryError(f"{label}: non-finite coordinate")
    return values


def _triangle_area2(
    positions: list[float], first: int, second: int, third: int
) -> float:
    ax, ay = positions[2 * first : 2 * first + 2]
    bx, by = positions[2 * second : 2 * second + 2]
    cx, cy = positions[2 * third : 2 * third + 2]
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def _mesh_row(source: ET.Element) -> dict[str, Any]:
    positions_node = _unique_array(source, "float-array", "positions")
    uvs_node = _unique_array(source, "float-array", "uvs")
    indices_node = _unique_array(source, "int-array", "indices")
    positions = _parse_numeric_array(positions_node, float, "positions")
    uvs = _parse_numeric_array(uvs_node, float, "uvs")
    indices = _parse_numeric_array(indices_node, int, "indices")

    if len(positions) % 2:
        raise InventoryError(f"{_source_name(source)!r}: odd position count")
    if len(uvs) != len(positions):
        raise InventoryError(
            f"{_source_name(source)!r}: UV count {len(uvs)} differs from "
            f"position count {len(positions)}"
        )
    if len(indices) % 3:
        raise InventoryError(f"{_source_name(source)!r}: index count not / 3")

    vertex_count = len(positions) // 2
    invalid_indices = [
        index for index in indices if index < 0 or index >= vertex_count
    ]
    used_vertices = {
        index for index in indices if 0 <= index < vertex_count
    }
    duplicate_index_triangles = 0
    degenerate_area_triangles = 0
    if not invalid_indices:
        for offset in range(0, len(indices), 3):
            triangle = indices[offset : offset + 3]
            if len(set(triangle)) != 3:
                duplicate_index_triangles += 1
            if abs(_triangle_area2(positions, *triangle)) <= 1e-8:
                degenerate_area_triangles += 1

    xs = positions[0::2]
    ys = positions[1::2]
    return {
        "name": _source_name(source),
        "id": _id_string(source, ("CDrawableId",)),
        "source_ref": source.get("xs.id"),
        "vertices": vertex_count,
        "triangles": len(indices) // 3,
        "indices": len(indices),
        "used_vertices": len(used_vertices),
        "unused_vertices": vertex_count - len(used_vertices),
        "invalid_indices": len(invalid_indices),
        "duplicate_index_triangles": duplicate_index_triangles,
        "degenerate_area_triangles": degenerate_area_triangles,
        "bounds": {
            "min_x": min(xs) if xs else None,
            "min_y": min(ys) if ys else None,
            "max_x": max(xs) if xs else None,
            "max_y": max(ys) if ys else None,
        },
    }


def inventory(path: Path, max_xml_bytes: int) -> dict[str, Any]:
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
    if shared is None:
        raise InventoryError("main.xml lacks expected shared node")

    meshes = [_mesh_row(source) for source in shared.findall("CArtMeshSource")]
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
        "zero_triangle_meshes": sum(
            1 for mesh in meshes if mesh["triangles"] == 0
        ),
    }
    return {
        "path": str(path.resolve()),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest().upper(),
        "main_xml_bytes": len(xml_bytes),
        "aggregate": aggregate,
        "meshes": meshes,
    }


def _print_inventory(result: dict[str, Any], limit: int) -> None:
    aggregate = result["aggregate"]
    print(result["path"])
    print(f"SHA-256: {result['sha256']}")
    print(
        "ArtMeshes={art_meshes} vertices={vertices} triangles={triangles} "
        "zero_triangle_meshes={zero_triangle_meshes} "
        "unused_vertices={unused_vertices} invalid_indices={invalid_indices} "
        "degenerate_triangles={degenerate_area_triangles}".format(**aggregate)
    )
    meshes = sorted(
        result["meshes"],
        key=lambda row: (row["vertices"], row["triangles"], row["name"]),
        reverse=True,
    )
    print("vertices\ttriangles\tunused\tdegenerate\tname")
    for mesh in meshes[:limit]:
        print(
            f"{mesh['vertices']}\t{mesh['triangles']}\t"
            f"{mesh['unused_vertices']}\t"
            f"{mesh['degenerate_area_triangles']}\t{mesh['name']}"
        )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cmo3", type=Path, nargs="+")
    parser.add_argument(
        "--json",
        type=Path,
        help="write the complete inventory list to this JSON file",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="number of densest meshes to print per file (default: 20)",
    )
    parser.add_argument(
        "--max-xml-bytes",
        type=int,
        default=DEFAULT_MAX_XML_BYTES,
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.limit < 0:
        parser.error("--limit must be non-negative")

    try:
        results = [
            inventory(path.resolve(), args.max_xml_bytes) for path in args.cmo3
        ]
    except (OSError, InventoryError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    for index, result in enumerate(results):
        if index:
            print()
        _print_inventory(result, args.limit)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(results, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
