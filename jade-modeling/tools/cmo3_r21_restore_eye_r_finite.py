#!/usr/bin/env python3
"""Repair only r21's three all-NaN right-eye keyforms, copy-on-write.

Mesh originals are corroborated against healthy v5. Local coordinates are
recomputed from the intact original canvas, using the current parent chain.
All unrelated sources and non-main archive members must remain identical.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
import re
from pathlib import Path
from typing import Any
import cmo3_create_deformer_experiment as experiment
import cmo3_reparent_preserve_canvas as canvas
import cmo3_safe_roundtrip as safe

V5_SHA = "E8BDF5D7D685391AC8038C10BF67981CCD48DB7A5C2877AA6A7FAAB043C3B65F"
TARGETS = {
    "D_JAD_EYE_R": ("warp-deformer", "a65bd983-c43e-4f56-9804-b67f2c66d36c", 72),
    "JAD_R21_EYE_R_OPEN_MASTER": ("art-mesh", "fea9bee2-d39d-424a-b05f-731a046d18c6", 150),
    "JAD_R21_EYE_R_SOCKET_SKIN": ("art-mesh", "2c42079a-7954-423f-b00c-fcb32e660f68", 76),
}
HEAD_UUID = "ca0c2616-17ad-4639-84d1-7e69fb3825b7"
TOLERANCE = 0.001


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def model_from_bytes(data: bytes) -> tuple[Any, bytes]:
    _, _, _, _, main = safe._validate_surgical_layout(data)
    return canvas.GeometryModel(main, TOLERANCE), main


def nonfinite_objects(model: Any) -> list[dict[str, Any]]:
    result = []
    for item in model.objects:
        for node in model.source(item).iter("float-array"):
            values = [float(token) for token in (node.text or "").split()]
            count = sum(not math.isfinite(value) for value in values)
            if count:
                result.append({"name": item.name, "type": item.object_type,
                               "field": node.get("xs.n"), "scalars": len(values),
                               "nonfinite": count})
    return result


def resolve(model: Any, name: str) -> Any:
    kind, guid, _ = TARGETS[name]
    return model.resolve(object_type=kind, name=name, guid_uuid=guid, label=name)


def raw_source(main: bytes, item: Any) -> bytes:
    return safe._source_block_span(main, item)[2]


def patch_nan_positions(main: bytes, model: Any, item: Any, values: tuple[float, ...]) -> bytes:
    source = model.source(item)
    link = experiment._one_named(source, "KeyformGridSource", "keyformGridSource")
    grid = model.ids.get(link.get("xs.ref"), link)
    bindings = experiment._one_named(grid, "array_list", "keyformBindings")
    forms = experiment._one_named(source, "carray_list", "keyforms")
    require(len(bindings) == 0 and len(forms) == 1, item.name + ": must be neutral and unbound")
    node = experiment._one_named(forms[0], "float-array", "positions")
    old = tuple(float(token) for token in (node.text or "").split())
    require(len(old) == len(values) == TARGETS[item.name][2], item.name + ": count changed")
    require(all(math.isnan(v) for v in old), item.name + ": expected all-NaN keyform")
    require(all(math.isfinite(v) for v in values), item.name + ": replacement is not finite")
    start, end, block = safe._source_block_span(main, item)
    lists = list(re.finditer(rb'<carray_list\b(?=[^>]*\bxs\.n="keyforms")[^>]*>.*?</carray_list>', block, re.S))
    require(len(lists) == 1, item.name + ": keyform list ambiguous")
    section = lists[0]
    matches = list(re.finditer(rb'(<float-array\b(?=[^>]*\bxs\.n="positions")[^>]*>)([^<]*)(</float-array>)', section.group(0)))
    require(len(matches) == 1, item.name + ": positions ambiguous")
    pos = matches[0]
    raw = tuple(float(t) for t in pos.group(2).split())
    require(len(raw) == len(old) and all(math.isnan(v) for v in raw), item.name + ": raw NaN payload changed")
    payload = " ".join(canvas._format_float32(v) for v in values).encode("ascii")
    left, right = section.start() + pos.start(2), section.start() + pos.end(2)
    return main[:start] + block[:left] + payload + block[right:] + main[end:]


def plan(source: Path, reference: Path) -> tuple[bytes, dict[str, Any]]:
    require("r21" in source.name.lower(), "source must be a Jade r21 checkpoint")
    version = re.search(r"_v(\d+)\.cmo3$", source.name)
    require(version is not None and int(version.group(1)) >= 21, "repair input must be native v21 or later")
    source_data, reference_data = source.read_bytes(), reference.read_bytes()
    require(sha(reference_data) == V5_SHA, "healthy v5 reference SHA differs")
    before, main = model_from_bytes(source_data)
    healthy, _ = model_from_bytes(reference_data)
    diagnostic = nonfinite_objects(before)
    require({row["name"] for row in diagnostic} == set(TARGETS), "unexpected nonfinite object set")
    require(len(diagnostic) == 3, "unexpected number of nonfinite arrays")
    require(sum(i.object_type == "art-mesh" for i in before.objects) == 57, "r21 ArtMesh count differs")
    originals = {}
    for name in TARGETS:
        item = resolve(before, name)
        parent = before.by_guid_ref.get(item.parent_ref)
        expected = HEAD_UUID if name == "D_JAD_EYE_R" else TARGETS["D_JAD_EYE_R"][1]
        require(parent is not None and parent.guid_uuid == expected, name + ": parent differs")
        originals[name] = before.original_canvas(item)
        require(len(originals[name]) == TARGETS[name][2], name + ": original count differs")
        require(all(math.isfinite(v) for v in originals[name]), name + ": original is not finite")
        if item.object_type == "art-mesh":
            old_item = resolve(healthy, name)
            require(canvas._maximum_error(originals[name], healthy.original_canvas(old_item)) <= TOLERANCE, name + ": geometry differs from v5")
            healthy.keyform_positions(old_item, require_single_unbound=True)
    current, changes = main, []
    for name in TARGETS:
        model = canvas.GeometryModel(current, TOLERANCE)
        item = resolve(model, name)
        parent = model.transform(item.parent_ref)
        local = tuple(canvas._float32(v) for v in model.inverse_many(parent, originals[name]))
        reconstructed = model.forward_many(parent, local)
        error = canvas._maximum_error(reconstructed, originals[name])
        require(error <= TOLERANCE, name + ": canvas error exceeds 0.001px")
        current = patch_nan_positions(current, model, item, local)
        changes.append({"name": name, "scalars": len(local), "max_canvas_error_px": error,
                        "restored_canvas_bounds": canvas._bounds(reconstructed)})
    after = canvas.GeometryModel(current, TOLERANCE)
    remaining = nonfinite_objects(after)
    require(not remaining, "nonfinite coordinates remain")
    require(before.objects == after.objects, "object identity, hierarchy or binding changed")
    changed = [i.name for i in before.objects if raw_source(main, i) != raw_source(current, i)]
    require(set(changed) == set(TARGETS), "unrelated source changed")
    for name in TARGETS:
        item = resolve(after, name)
        _, local = after.keyform_positions(item, require_single_unbound=True)
        observed = after.forward_many(after.transform(item.parent_ref), local)
        require(canvas._maximum_error(observed, originals[name]) <= TOLERANCE, name + ": final canvas proof failed")
    output = safe._replace_main_xml(source_data, current)
    archive_before, _, _, _, _ = safe._validate_surgical_layout(source_data)
    archive_after, _, _, _, decoded = safe._validate_surgical_layout(output)
    require(decoded == current, "encoded main.xml differs")
    preserved = safe._compare_entry_preservation(source_data, archive_before, output, archive_after, main_may_change=True)
    require(preserved.get("all_non_main_entries_byte_identical") is True, "non-main archive member changed")
    require(source.read_bytes() == source_data and reference.read_bytes() == reference_data, "source/reference changed during repair")
    audit = {"schema": "jade.r21.restore-eye-r-finite.v1", "status": "candidate_requires_cubism_load_save",
             "source": str(source), "source_sha256": sha(source_data),
             "reference": str(reference), "reference_sha256": sha(reference_data),
             "output_sha256": sha(output), "before_nonfinite": diagnostic,
             "after_nonfinite": remaining, "changes": changes,
             "all_unrelated_sources_byte_identical": True,
             "hierarchy_and_bindings_unchanged": True, "archive": preserved}
    return output, audit


def exclusive(path: Path, data: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--diagnose", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    if args.diagnose:
        model, _ = model_from_bytes(source.read_bytes())
        print(json.dumps({"source": str(source), "nonfinite": nonfinite_objects(model)}, indent=2))
        return 0
    require(args.reference is not None, "--reference v5 is required")
    if not args.dry_run:
        require(args.output is not None and args.audit is not None, "--output and --audit are required")
        require("TEST" in args.output.name and args.output.suffix.lower() == ".cmo3", "output must be a TEST CMO3")
        require(not args.output.exists() and not args.audit.exists(), "output/audit exists; refusing overwrite")
        require(args.output.resolve() != source, "output must differ from source")
    data, audit = plan(source, args.reference.resolve(strict=True))
    if not args.dry_run:
        audit["output"] = str(args.output.resolve())
        exclusive(args.output, data)
        exclusive(args.audit, (json.dumps(audit, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
