#!/usr/bin/env python3
"""Build Jade's neutral root/body/head wrapper scaffold on a new TEST CMO3.

The transaction is intentionally narrow and fail-closed.  It expands the
existing root and body warp envelopes, converts the empty head wrapper from
5x5 to 7x5, and reparents the exact current head roots while preserving every
serialized keyform on the neutral canvas.  Existing files are never replaced.
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
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Sequence


TOOLS_DIR = Path(__file__).resolve(strict=True).parent
PINS = {
    "cmo3_inventory.py": "9CBA62CFCEBBFE249F0F0785EA480A3963FD610F95D356EC5D36FCBDCA201083",
    "cmo3_safe_roundtrip.py": "AB9E67B350E6D42AA4B471B5359CFB45B8A09FF02489CCFF447D65A59B00AC5E",
    "cmo3_reparent_preserve_canvas.py": "4E191B07EBD2F15064197429B5ADFD57EE25B5C7252E34F458EC999FA003A38A",
    "cmo3_mesh_topology.py": "737C62FB40D3F359894A9E4FE1B718238AFED92D61B7CEE36323910EA8E7390F",
}

SOURCE_NAME = (
    "Jade_rig_5_2_v003.TEST_global_skeleton_identity_parts_r01."
    "CUBISM_roundtrip_r01.cmo3"
)
SOURCE_SHA256 = "2B792706F14186748E6CB90DC14F7838F027C0C22CC82A375BCDA4594BC01318"
OUTPUT_NAME = "Jade_rig_5_2_v003.TEST_head_wrapper_7x5_r01.cmo3"
AUDIT_NAME = "Jade_v003.TEST_head_wrapper_7x5_r01_audit.json"
TOLERANCE = 0.001

ROOT_UUID = "83426cc7-4530-5445-be79-c87e91402610"
BODY_Z_UUID = "bcf109f2-eb67-4217-97ad-e052050fd7bc"
BODY_XY_UUID = "95c12203-5376-448e-a9df-43e677228030"
HEAD_Z_UUID = "ad0fc628-c3b2-4a7a-a488-95624e274cbc"
HEAD_XY_UUID = "85d6a8c6-3bbb-40e0-8310-7101816df8e7"

ROOT_BOUNDS = (650.0, -100.0, 2860.0, 3250.0)
BODY_BOUNDS = (688.6489, -75.0, 2824.351, 3201.695)
HEAD_BOUNDS = (800.0, -50.0, 2700.0, 1850.0)

ROOT_CHILD_NAMES = {
    "JAD_SKIN_BREAST_L",
    "JAD_SKIN_BREAST_R",
    "R_JAD_BODY_Z",
}
BODY_CHILD_NAMES = {
    "D_JAD_BODY_BREATH",
    "D_JAD_DRESS_MAIN",
    "R_JAD_HEAD_Z",
}
HEAD_ART_NAMES = {
    "JAD_HAIR_AHOGE",
    "JAD_HAIR_BANG_C",
    "JAD_HAIR_BANG_L_INNER",
    "JAD_HAIR_BANG_R_INNER",
    "JAD_HAIR_BANG_L_OUTER",
    "JAD_HAIR_BANG_R_OUTER",
    "JAD_HAIR_TEMPLE_L",
    "JAD_HAIR_TEMPLE_R",
    "JAD_FACE_HAIR_SHADOW",
    "JAD_HAIR_BACK_L_INNER",
    "JAD_HAIR_BACK_R_INNER",
    "JAD_HAIR_BACK_L_OUTER",
    "JAD_HAIR_BACK_R_OUTER",
    "JAD_HAIR_BACK_C",
    "JAD_EAR_L_FUR",
    "JAD_EAR_L_INNER",
    "JAD_EAR_L_BASE",
    "JAD_EAR_R_FUR",
    "JAD_EAR_R_INNER",
    "JAD_EAR_R_BASE",
}
HEAD_WARP_NAMES = {
    "D_JAD_FACE_ANGLE_XY",
    "D_JAD_EYE_L_BASE",
    "D_JAD_EYE_R_BASE",
    "D_JAD_EYEBALLS_GAZE_TMP",
    "D_JAD_BROW_L",
    "D_JAD_BROW_R",
    "D_JAD_MOUTH_MAIN",
    "Nose Warp",
}
HEAD_CHILD_NAMES = HEAD_ART_NAMES | HEAD_WARP_NAMES


class ScaffoldError(RuntimeError):
    pass


@dataclass(frozen=True)
class UndoStep:
    label: str
    apply: Callable[[bytes], bytes]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _make_undo_step(before: bytes, after: bytes, label: str) -> UndoStep:
    if before == after:
        raise ScaffoldError(f"{label}: patch made no byte change")
    prefix = 0
    limit = min(len(before), len(after))
    while prefix < limit and before[prefix] == after[prefix]:
        prefix += 1
    suffix = 0
    before_remaining = len(before) - prefix
    after_remaining = len(after) - prefix
    while (
        suffix < before_remaining
        and suffix < after_remaining
        and before[len(before) - 1 - suffix] == after[len(after) - 1 - suffix]
    ):
        suffix += 1
    before_end = len(before) - suffix if suffix else len(before)
    after_end = len(after) - suffix if suffix else len(after)
    old_segment = before[prefix:before_end]
    new_segment = after[prefix:after_end]
    before_hash = _sha256(before)
    after_hash = _sha256(after)

    def restore(data: bytes) -> bytes:
        if _sha256(data) != after_hash:
            raise ScaffoldError(f"undo {label}: input state hash differs")
        if data[prefix : prefix + len(new_segment)] != new_segment:
            raise ScaffoldError(f"undo {label}: patched segment differs")
        recovered = (
            data[:prefix] + old_segment + data[prefix + len(new_segment) :]
        )
        if _sha256(recovered) != before_hash:
            raise ScaffoldError(f"undo {label}: recovered state hash differs")
        return recovered

    return UndoStep(label, restore)


def _hash_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ScaffoldError(f"cannot load {path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_dependencies() -> tuple[ModuleType, ModuleType, ModuleType]:
    for filename, expected in PINS.items():
        actual = _hash_file((TOOLS_DIR / filename).resolve(strict=True))
        if actual != expected:
            raise ScaffoldError(
                f"dependency {filename} SHA mismatch: expected {expected}, got {actual}"
            )
    sys.path.insert(0, str(TOOLS_DIR))
    _load_module("cmo3_inventory", TOOLS_DIR / "cmo3_inventory.py")
    safe = _load_module(
        "cmo3_safe_roundtrip", TOOLS_DIR / "cmo3_safe_roundtrip.py"
    )
    canvas = _load_module(
        "cmo3_reparent_preserve_canvas",
        TOOLS_DIR / "cmo3_reparent_preserve_canvas.py",
    )
    topology = _load_module("cmo3_mesh_topology", TOOLS_DIR / "cmo3_mesh_topology.py")
    for filename, expected in PINS.items():
        if _hash_file((TOOLS_DIR / filename).resolve(strict=True)) != expected:
            raise ScaffoldError(f"dependency {filename} changed while loading")
    return safe, canvas, topology


def _object_by_uuid(model: Any, guid_uuid: str, label: str) -> Any:
    matches = [item for item in model.objects if item.guid_uuid == guid_uuid]
    if len(matches) != 1:
        raise ScaffoldError(f"{label}: expected one UUID match, found {len(matches)}")
    return matches[0]


def _object_by_name(model: Any, name: str, label: str) -> Any:
    matches = [item for item in model.objects if item.name == name]
    if len(matches) != 1:
        raise ScaffoldError(f"{label}: expected one name match, found {len(matches)}")
    return matches[0]


def _children(model: Any, parent: Any) -> list[Any]:
    return [item for item in model.objects if item.parent_ref == parent.guid_ref]


def _grid(
    canvas: ModuleType,
    columns: int,
    rows: int,
    bounds: tuple[float, float, float, float],
) -> tuple[float, ...]:
    x0, y0, x1, y1 = bounds
    result: list[float] = []
    for row in range(rows + 1):
        y = canvas._float32(y0 + (y1 - y0) * row / rows)
        for column in range(columns + 1):
            x = canvas._float32(x0 + (x1 - x0) * column / columns)
            result.extend((x, y))
    return tuple(result)


def _parse_payload(payload: bytes, label: str) -> tuple[float, ...]:
    try:
        values = tuple(float(token) for token in payload.decode("ascii").split())
    except (UnicodeDecodeError, ValueError) as exc:
        raise ScaffoldError(f"{label} contains invalid floats") from exc
    if not values or len(values) % 2:
        raise ScaffoldError(f"{label} coordinate count is invalid")
    if any(not math.isfinite(value) for value in values):
        raise ScaffoldError(f"{label} contains a non-finite value")
    return values


def _payload(canvas: ModuleType, values: Sequence[float]) -> bytes:
    return " ".join(canvas._format_float32(value) for value in values).encode("ascii")


def _f32_equal(canvas: ModuleType, left: Sequence[float], right: Sequence[float]) -> bool:
    return len(left) == len(right) and all(
        canvas._float32(a) == canvas._float32(b) for a, b in zip(left, right)
    )


def _positions_ref(model: Any, item: Any) -> str:
    source = model.source(item)
    extensions = list(source.iter("CDeformerOriginalShapeExtension"))
    if len(extensions) != 1:
        raise ScaffoldError(f"{item.name!r} lacks one original-shape extension")
    refs = {
        node.get("xs.ref")
        for node in extensions[0].iter("float-array")
        if node.get("xs.n") == "positions"
    }
    if len(refs) != 1 or None in refs:
        raise ScaffoldError(f"{item.name!r} original positions reference is ambiguous")
    return next(iter(refs))


def _patch_shared_array(
    data: bytes,
    *,
    canvas: ModuleType,
    positions_ref: str,
    expected_old: Sequence[float],
    replacement: Sequence[float],
    label: str,
) -> tuple[bytes, dict[str, Any]]:
    pattern = re.compile(
        rb'(<float-array\b(?=[^>]*\bxs\.id="'
        + re.escape(positions_ref.encode("ascii"))
        + rb'")(?=[^>]*\bcount=")[^>]*\bcount=")(\d+)("[^>]*>)([^<]*)(</float-array>)'
    )
    matches = list(pattern.finditer(data))
    if len(matches) != 1:
        raise ScaffoldError(f"{label}: shared array match count {len(matches)}")
    match = matches[0]
    old_values = _parse_payload(match.group(4), f"{label} old shared payload")
    if not _f32_equal(canvas, old_values, expected_old):
        raise ScaffoldError(f"{label}: shared payload differs from plan")
    if int(match.group(2)) != len(old_values):
        raise ScaffoldError(f"{label}: shared count differs from payload")
    new_payload = _payload(canvas, replacement)
    new_block = (
        match.group(1)
        + str(len(replacement)).encode("ascii")
        + match.group(3)
        + new_payload
        + match.group(5)
    )
    patched = data[: match.start()] + new_block + data[match.end() :]
    return patched, {
        "kind": "shared-original-grid",
        "label": label,
        "positions_ref": positions_ref,
        "old_count": len(old_values),
        "new_count": len(replacement),
        "old_payload_sha256": _sha256(match.group(4)),
        "new_payload_sha256": _sha256(new_payload),
    }


def _keyform_payload_matches(source_block: bytes) -> tuple[int, int, list[re.Match[bytes]]]:
    openings = list(
        re.finditer(rb'<carray_list\b(?=[^>]*\bxs\.n="keyforms")[^>]*>', source_block)
    )
    if len(openings) != 1:
        raise ScaffoldError(f"keyform list match count {len(openings)}")
    close = source_block.find(b"</carray_list>", openings[0].end())
    if close < 0:
        raise ScaffoldError("keyform list is not closed")
    list_start = openings[0].start()
    list_end = close + len(b"</carray_list>")
    block = source_block[list_start:list_end]
    payloads = list(
        re.finditer(
            rb'(<float-array\b(?=[^>]*\bxs\.n="positions")'
            rb'(?=[^>]*\bcount=")[^>]*\bcount=")(\d+)("[^>]*>)([^<]*)(</float-array>)',
            block,
        )
    )
    return list_start, list_end, payloads


def _form_values(model: Any, canvas: ModuleType, item: Any) -> tuple[tuple[float, ...], ...]:
    source = model.source(item)
    forms = canvas._one_direct_named(source, "carray_list", "keyforms")
    if item.object_type == "rotation-deformer":
        result: list[tuple[float, ...]] = []
        for index, form in enumerate(forms):
            if form.tag != "CRotationDeformerForm":
                raise ScaffoldError(f"{item.name!r} form {index} is not rotation")
            try:
                result.append((float(form.attrib["originX"]), float(form.attrib["originY"])))
            except (KeyError, ValueError) as exc:
                raise ScaffoldError(f"{item.name!r} form {index} has invalid origin") from exc
        return tuple(result)
    result = []
    for index, form in enumerate(forms):
        node = canvas._one_direct_named(form, "float-array", "positions")
        result.append(canvas._float_values(node, f"{item.name} form {index}"))
    return tuple(result)


def _patch_form_positions(
    data: bytes,
    *,
    safe: ModuleType,
    canvas: ModuleType,
    target: Any,
    expected_old: Sequence[Sequence[float]],
    replacement: Sequence[Sequence[float]],
    label: str,
) -> tuple[bytes, list[dict[str, Any]]]:
    if target.object_type == "rotation-deformer":
        raise ScaffoldError(f"{label}: rotation passed to float-array patcher")
    if len(expected_old) != len(replacement):
        raise ScaffoldError(f"{label}: form count changed")
    block_start, block_end, source_block = safe._source_block_span(data, target)
    list_start, list_end, matches = _keyform_payload_matches(source_block)
    if len(matches) != len(expected_old):
        raise ScaffoldError(
            f"{label}: serialized form count {len(matches)} != {len(expected_old)}"
        )
    list_block = source_block[list_start:list_end]
    records: list[dict[str, Any]] = []
    patched_list = list_block
    for index in range(len(matches) - 1, -1, -1):
        match = matches[index]
        old_values = _parse_payload(match.group(4), f"{label} form {index}")
        if not _f32_equal(canvas, old_values, expected_old[index]):
            raise ScaffoldError(f"{label}: form {index} differs from plan")
        if int(match.group(2)) != len(old_values):
            raise ScaffoldError(f"{label}: form {index} count differs")
        new_values = replacement[index]
        if len(new_values) % 2:
            raise ScaffoldError(f"{label}: form {index} new coordinate count is odd")
        new_payload = _payload(canvas, new_values)
        new_block = (
            match.group(1)
            + str(len(new_values)).encode("ascii")
            + match.group(3)
            + new_payload
            + match.group(5)
        )
        patched_list = (
            patched_list[: match.start()] + new_block + patched_list[match.end() :]
        )
        records.append(
            {
                "kind": "keyform-positions",
                "label": label,
                "object_uuid": target.guid_uuid,
                "object_name": target.name,
                "form_index": index,
                "old_count": len(old_values),
                "new_count": len(new_values),
                "old_payload_sha256": _sha256(match.group(4)),
                "new_payload_sha256": _sha256(new_payload),
            }
        )
    patched_source = source_block[:list_start] + patched_list + source_block[list_end:]
    patched = data[:block_start] + patched_source + data[block_end:]
    records.reverse()
    return patched, records


def _patch_rotation_origins(
    data: bytes,
    *,
    safe: ModuleType,
    canvas: ModuleType,
    target: Any,
    expected_old: Sequence[Sequence[float]],
    replacement: Sequence[Sequence[float]],
    label: str,
) -> tuple[bytes, list[dict[str, Any]]]:
    if target.object_type != "rotation-deformer":
        raise ScaffoldError(f"{label}: non-rotation passed to origin patcher")
    if len(expected_old) != len(replacement):
        raise ScaffoldError(f"{label}: rotation form count changed")
    block_start, block_end, source_block = safe._source_block_span(data, target)
    openings = list(re.finditer(rb"<CRotationDeformerForm\b[^>]*>", source_block))
    if len(openings) != len(expected_old):
        raise ScaffoldError(f"{label}: rotation opening count differs")
    patched_source = source_block
    records: list[dict[str, Any]] = []
    for index in range(len(openings) - 1, -1, -1):
        opening = openings[index].group(0)
        old_tokens: dict[str, bytes] = {}
        for attribute in ("originX", "originY"):
            matches = list(
                re.finditer(rb"\b" + attribute.encode("ascii") + rb'="([^"]+)"', opening)
            )
            if len(matches) != 1:
                raise ScaffoldError(f"{label}: form {index} lacks one {attribute}")
            old_tokens[attribute] = matches[0].group(1)
        parsed = (float(old_tokens["originX"]), float(old_tokens["originY"]))
        if not _f32_equal(canvas, parsed, expected_old[index]):
            raise ScaffoldError(f"{label}: form {index} origin differs from plan")
        new_values = tuple(canvas._float32(value) for value in replacement[index])
        if len(new_values) != 2:
            raise ScaffoldError(f"{label}: form {index} origin is not two values")
        patched_opening = opening
        for attribute, value in zip(("originX", "originY"), new_values):
            old_token = attribute.encode("ascii") + b'="' + old_tokens[attribute] + b'"'
            new_token = (
                attribute.encode("ascii")
                + b'="'
                + canvas._format_float32(value).encode("ascii")
                + b'"'
            )
            if patched_opening.count(old_token) != 1:
                raise ScaffoldError(f"{label}: form {index} {attribute} is ambiguous")
            patched_opening = patched_opening.replace(old_token, new_token, 1)
        patched_source = (
            patched_source[: openings[index].start()]
            + patched_opening
            + patched_source[openings[index].end() :]
        )
        records.append(
            {
                "kind": "rotation-origin",
                "label": label,
                "object_uuid": target.guid_uuid,
                "object_name": target.name,
                "form_index": index,
                "old_values": list(parsed),
                "new_values": list(new_values),
            }
        )
    patched = data[:block_start] + patched_source + data[block_end:]
    records.reverse()
    return patched, records


def _patch_head_columns(
    data: bytes,
    *,
    safe: ModuleType,
    target: Any,
    expected_old: int,
    replacement: int,
) -> tuple[bytes, dict[str, Any]]:
    block_start, block_end, source_block = safe._source_block_span(data, target)
    pattern = re.compile(
        rb'(<i\b(?=[^>]*\bxs\.n="col")[^>]*>)\s*'
        + str(expected_old).encode("ascii")
        + rb'\s*(</i>)'
    )
    matches = list(pattern.finditer(source_block))
    if len(matches) != 3:
        raise ScaffoldError(f"D_HEAD col match count {len(matches)} != 3")
    replacement_bytes = str(replacement).encode("ascii")
    patched_source = source_block
    for match in reversed(matches):
        new_block = match.group(1) + replacement_bytes + match.group(2)
        patched_source = (
            patched_source[: match.start()] + new_block + patched_source[match.end() :]
        )
    patched = data[:block_start] + patched_source + data[block_end:]
    return patched, {
        "kind": "head-grid-columns",
        "object_uuid": target.guid_uuid,
        "occurrences": 3,
        "old": expected_old,
        "new": replacement,
    }


def _patch_parent_ref(
    data: bytes,
    *,
    safe: ModuleType,
    target: Any,
    expected_old_ref: str,
    new_ref: str,
    label: str,
) -> tuple[bytes, dict[str, Any]]:
    block_start, block_end, source_block = safe._source_block_span(data, target)
    pattern = re.compile(
        rb'(<CDeformerGuid\b(?=[^>]*\bxs\.n="targetDeformerGuid")'
        rb'(?=[^>]*\bxs\.ref=")[^>]*\bxs\.ref=")([^"\s]+)("[^>]*/>)'
    )
    matches = list(pattern.finditer(source_block))
    if len(matches) != 1:
        raise ScaffoldError(f"{label}: parent reference match count {len(matches)}")
    match = matches[0]
    observed = match.group(2).decode("ascii")
    if observed != expected_old_ref:
        raise ScaffoldError(f"{label}: parent {observed!r} != {expected_old_ref!r}")
    new_block = match.group(1) + new_ref.encode("ascii") + match.group(3)
    patched_source = source_block[: match.start()] + new_block + source_block[match.end() :]
    patched = data[:block_start] + patched_source + data[block_end:]
    return patched, {
        "kind": "parent-reference",
        "label": label,
        "object_uuid": target.guid_uuid,
        "object_name": target.name,
        "old_ref": expected_old_ref,
        "new_ref": new_ref,
    }


def _convert_forms(
    *,
    canvas: ModuleType,
    old_model: Any,
    new_model: Any,
    old_parent: Any,
    new_parent: Any,
    target: Any,
) -> tuple[tuple[tuple[float, ...], ...], list[dict[str, Any]]]:
    old_forms = _form_values(old_model, canvas, target)
    old_transform = old_model.transform(old_parent.guid_ref)
    new_transform = new_model.transform(new_parent.guid_ref)
    converted: list[tuple[float, ...]] = []
    proof: list[dict[str, Any]] = []
    for index, old_local in enumerate(old_forms):
        canvas_values = old_model.forward_many(old_transform, old_local)
        exact_new = new_model.inverse_many(new_transform, canvas_values)
        new_local = tuple(canvas._float32(value) for value in exact_new)
        reconstructed = new_model.forward_many(new_transform, new_local)
        error = canvas._maximum_error(canvas_values, reconstructed)
        if error >= TOLERANCE:
            raise ScaffoldError(
                f"{target.name!r} form {index} reconstruction error {error}px"
            )
        converted.append(new_local)
        proof.append(
            {
                "object_uuid": target.guid_uuid,
                "object_name": target.name,
                "object_type": target.object_type,
                "form_index": index,
                "coordinate_count": len(new_local),
                "canvas_bounds": canvas._bounds(canvas_values),
                "new_local_bounds": canvas._bounds(new_local),
                "max_reconstruction_error_px": error,
            }
        )
    return tuple(converted), proof


def _require_children(model: Any, parent: Any, names: set[str], label: str) -> list[Any]:
    children = _children(model, parent)
    observed = {item.name for item in children}
    if len(children) != len(names) or observed != names:
        raise ScaffoldError(
            f"{label} children differ: observed={sorted(observed)!r}, "
            f"expected={sorted(names)!r}"
        )
    return sorted(children, key=lambda item: (item.object_type, item.name))


def _inventory_signature(inventory: dict[str, Any]) -> dict[str, Any]:
    return {
        "counts": inventory["counts"],
        "parameter_ids": inventory["parameter_ids"],
        "warp_deformer_names": inventory["warp_deformer_names"],
        "rotation_deformer_names": inventory["rotation_deformer_names"],
        "bound_objects": inventory["bound_objects"],
    }


def _plan(
    source_data: bytes,
    *,
    safe: ModuleType,
    canvas: ModuleType,
) -> tuple[bytes, dict[str, Any]]:
    archive_before, _, _, source_zip, main_before = safe._validate_surgical_layout(source_data)
    model0 = canvas.GeometryModel(main_before, TOLERANCE)
    root0 = _object_by_uuid(model0, ROOT_UUID, "D_JAD_ROOT")
    body_z0 = _object_by_uuid(model0, BODY_Z_UUID, "R_JAD_BODY_Z")
    body0 = _object_by_uuid(model0, BODY_XY_UUID, "D_JAD_BODY_XY")
    head_z0 = _object_by_uuid(model0, HEAD_Z_UUID, "R_JAD_HEAD_Z")
    head0 = _object_by_uuid(model0, HEAD_XY_UUID, "D_JAD_HEAD_XY")
    if any(item.object_type != "warp-deformer" for item in (root0, body0, head0)):
        raise ScaffoldError("root/body/head wrapper type differs")
    if any(item.object_type != "rotation-deformer" for item in (body_z0, head_z0)):
        raise ScaffoldError("body/head rotation type differs")
    if body_z0.parent_uuid != ROOT_UUID or body0.parent_uuid != BODY_Z_UUID:
        raise ScaffoldError("root/body parent chain differs")
    if head_z0.parent_uuid != BODY_XY_UUID or head0.parent_uuid != HEAD_Z_UUID:
        raise ScaffoldError("head parent chain differs")
    root_children0 = _require_children(model0, root0, ROOT_CHILD_NAMES, "root")
    body_children0 = _require_children(model0, body0, BODY_CHILD_NAMES, "body")
    head_siblings0 = _require_children(
        model0,
        head_z0,
        HEAD_CHILD_NAMES | {head0.name},
        "R_HEAD",
    )
    if _children(model0, head0):
        raise ScaffoldError("D_HEAD must be empty before transaction")
    head_targets0 = [item for item in head_siblings0 if item.guid_uuid != HEAD_XY_UUID]
    if {item.name for item in head_targets0} != HEAD_CHILD_NAMES:
        raise ScaffoldError("head target set differs")
    if {item.name for item in head_targets0 if item.object_type == "art-mesh"} != HEAD_ART_NAMES:
        raise ScaffoldError("head ArtMesh target set differs")
    if {item.name for item in head_targets0 if item.object_type == "warp-deformer"} != HEAD_WARP_NAMES:
        raise ScaffoldError("head warp target set differs")

    wrapper_specs = ((root0, 5, 5), (body0, 5, 5), (head0, 5, 5))
    for item, columns, rows in wrapper_specs:
        source = model0.source(item)
        observed = (
            int(canvas._one_direct_named(source, "i", "col").text or "0"),
            int(canvas._one_direct_named(source, "i", "row").text or "0"),
        )
        if observed != (columns, rows):
            raise ScaffoldError(f"{item.name} grid {observed!r} differs")
    head_grid_source = model0.source(head0)
    head_grid = canvas._one_named(head_grid_source, "KeyformGridSource", "keyformGridSource")
    head_grid = model0.ids.get(head_grid.get("xs.ref"), head_grid)
    if len(canvas._one_direct_named(head_grid, "array_list", "keyformBindings")) != 0:
        raise ScaffoldError("D_HEAD unexpectedly has parameter bindings")
    if len(_form_values(model0, canvas, head0)) != 1:
        raise ScaffoldError("D_HEAD must have exactly one neutral form")

    current = main_before
    whitelist: list[dict[str, Any]] = []
    coordinate_proof: list[dict[str, Any]] = []
    undo: list[UndoStep] = []

    def patch_shared(item: Any, old: Sequence[float], new: Sequence[float], label: str) -> None:
        nonlocal current
        before = current
        ref = _positions_ref(canvas.GeometryModel(current, TOLERANCE), item)
        current, record = _patch_shared_array(
            current,
            canvas=canvas,
            positions_ref=ref,
            expected_old=old,
            replacement=new,
            label=label,
        )
        whitelist.append(record)
        undo.append(_make_undo_step(before, current, label))

    def patch_positions(item: Any, old: Sequence[Sequence[float]], new: Sequence[Sequence[float]], label: str) -> None:
        nonlocal current
        before = current
        current, records = _patch_form_positions(
            current,
            safe=safe,
            canvas=canvas,
            target=item,
            expected_old=old,
            replacement=new,
            label=label,
        )
        whitelist.extend(records)
        undo.append(_make_undo_step(before, current, label))

    def patch_rotation(item: Any, old: Sequence[Sequence[float]], new: Sequence[Sequence[float]], label: str) -> None:
        nonlocal current
        before = current
        current, records = _patch_rotation_origins(
            current,
            safe=safe,
            canvas=canvas,
            target=item,
            expected_old=old,
            replacement=new,
            label=label,
        )
        whitelist.extend(records)
        undo.append(_make_undo_step(before, current, label))

    # 1. Expand the global root and preserve its three direct children.
    root_original_old = model0.original_canvas(root0)
    root_forms_old = _form_values(model0, canvas, root0)
    root_original_new = _grid(canvas, 5, 5, ROOT_BOUNDS)
    root_local_new = tuple(
        canvas._float32(value)
        for value in model0.inverse_many(model0.transform(root0.parent_ref), root_original_new)
    )
    patch_shared(root0, root_original_old, root_original_new, "D_ROOT original")
    patch_positions(root0, root_forms_old, (root_local_new,), "D_ROOT neutral")
    root_grid_model = canvas.GeometryModel(current, TOLERANCE)
    root_new = _object_by_uuid(root_grid_model, ROOT_UUID, "expanded D_ROOT")
    for target0 in root_children0:
        target_new = _object_by_uuid(root_grid_model, target0.guid_uuid, target0.name)
        converted, proof = _convert_forms(
            canvas=canvas,
            old_model=model0,
            new_model=root_grid_model,
            old_parent=root0,
            new_parent=root_new,
            target=target0,
        )
        old_forms = _form_values(model0, canvas, target0)
        if target0.object_type == "rotation-deformer":
            patch_rotation(target_new, old_forms, converted, f"root child {target0.name}")
        else:
            patch_positions(target_new, old_forms, converted, f"root child {target0.name}")
        coordinate_proof.extend(proof)
    model1 = canvas.GeometryModel(current, TOLERANCE)

    # 2. Expand the body wrapper and preserve its three direct children.
    body1 = _object_by_uuid(model1, BODY_XY_UUID, "body before expansion")
    body_z1 = _object_by_uuid(model1, BODY_Z_UUID, "R_BODY before body expansion")
    body_original_old = model1.original_canvas(body1)
    body_forms_old = _form_values(model1, canvas, body1)
    body_original_new = _grid(canvas, 5, 5, BODY_BOUNDS)
    body_local_new = tuple(
        canvas._float32(value)
        for value in model1.inverse_many(model1.transform(body_z1.guid_ref), body_original_new)
    )
    patch_shared(body1, body_original_old, body_original_new, "D_BODY original")
    patch_positions(body1, body_forms_old, (body_local_new,), "D_BODY neutral")
    body_grid_model = canvas.GeometryModel(current, TOLERANCE)
    body_new = _object_by_uuid(body_grid_model, BODY_XY_UUID, "expanded D_BODY")
    for target1 in _require_children(model1, body1, BODY_CHILD_NAMES, "body pre-convert"):
        target_new = _object_by_uuid(body_grid_model, target1.guid_uuid, target1.name)
        converted, proof = _convert_forms(
            canvas=canvas,
            old_model=model1,
            new_model=body_grid_model,
            old_parent=body1,
            new_parent=body_new,
            target=target1,
        )
        old_forms = _form_values(model1, canvas, target1)
        if target1.object_type == "rotation-deformer":
            patch_rotation(target_new, old_forms, converted, f"body child {target1.name}")
        else:
            patch_positions(target_new, old_forms, converted, f"body child {target1.name}")
        coordinate_proof.extend(proof)
    model2 = canvas.GeometryModel(current, TOLERANCE)

    # 3. Rebuild the empty head wrapper as 7x5.
    head2 = _object_by_uuid(model2, HEAD_XY_UUID, "head before 7x5")
    head_z2 = _object_by_uuid(model2, HEAD_Z_UUID, "R_HEAD before 7x5")
    head_original_old = model2.original_canvas(head2)
    head_forms_old = _form_values(model2, canvas, head2)
    head_original_new = _grid(canvas, 7, 5, HEAD_BOUNDS)
    head_local_new = tuple(
        canvas._float32(value)
        for value in model2.inverse_many(model2.transform(head_z2.guid_ref), head_original_new)
    )
    patch_shared(head2, head_original_old, head_original_new, "D_HEAD original")
    patch_positions(head2, head_forms_old, (head_local_new,), "D_HEAD neutral")
    before_columns = current
    current, column_record = _patch_head_columns(
        current,
        safe=safe,
        target=head2,
        expected_old=5,
        replacement=7,
    )
    whitelist.append(column_record)
    undo.append(_make_undo_step(before_columns, current, "D_HEAD columns"))
    head_grid_model = canvas.GeometryModel(current, TOLERANCE)
    head_new = _object_by_uuid(head_grid_model, HEAD_XY_UUID, "7x5 D_HEAD")
    head_z_new = _object_by_uuid(head_grid_model, HEAD_Z_UUID, "R_HEAD after body expansion")

    # 4. Reparent the exact 28 roots and preserve all 84 forms.
    for target2 in sorted(
        [
            _object_by_name(model2, name, f"head target {name}")
            for name in HEAD_CHILD_NAMES
        ],
        key=lambda item: (item.object_type, item.name),
    ):
        converted, proof = _convert_forms(
            canvas=canvas,
            old_model=model2,
            new_model=head_grid_model,
            old_parent=head_z2,
            new_parent=head_new,
            target=target2,
        )
        old_forms = _form_values(model2, canvas, target2)
        before_parent = current
        current, parent_record = _patch_parent_ref(
            current,
            safe=safe,
            target=target2,
            expected_old_ref=head_z2.guid_ref,
            new_ref=head_new.guid_ref,
            label=f"head parent {target2.name}",
        )
        whitelist.append(parent_record)
        undo.append(
            _make_undo_step(
                before_parent, current, f"head parent {target2.name}"
            )
        )
        target_current = _object_by_uuid(
            canvas.GeometryModel(current, TOLERANCE), target2.guid_uuid, target2.name
        )
        patch_positions(
            target_current,
            old_forms,
            converted,
            f"head child {target2.name}",
        )
        coordinate_proof.extend(proof)

    final_model = canvas.GeometryModel(current, TOLERANCE)
    final_root = _object_by_uuid(final_model, ROOT_UUID, "final root")
    final_body = _object_by_uuid(final_model, BODY_XY_UUID, "final body")
    final_head_z = _object_by_uuid(final_model, HEAD_Z_UUID, "final R_HEAD")
    final_head = _object_by_uuid(final_model, HEAD_XY_UUID, "final D_HEAD")
    if {item.name for item in _children(final_model, final_head_z)} != {final_head.name}:
        raise ScaffoldError("final R_HEAD does not have only D_HEAD")
    if {item.name for item in _children(final_model, final_head)} != HEAD_CHILD_NAMES:
        raise ScaffoldError("final D_HEAD child set differs")
    safe._validate_deformer_graph(final_model.objects)

    before_by_uuid = {item.guid_uuid: item for item in model0.objects}
    after_by_uuid = {item.guid_uuid: item for item in final_model.objects}
    if set(before_by_uuid) != set(after_by_uuid):
        raise ScaffoldError("object UUID set changed")
    head_target_uuids = {item.guid_uuid for item in head_targets0}
    for guid_uuid, before in before_by_uuid.items():
        after = after_by_uuid[guid_uuid]
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
            raise ScaffoldError(f"immutable identity changed for {before.name!r}")
        expected_parent = HEAD_XY_UUID if guid_uuid in head_target_uuids else before.parent_uuid
        if after.parent_uuid != expected_parent:
            raise ScaffoldError(f"parent delta differs for {before.name!r}")

    expected_original_changes = {ROOT_UUID, BODY_XY_UUID, HEAD_XY_UUID}
    for guid_uuid, before in before_by_uuid.items():
        after = after_by_uuid[guid_uuid]
        before_original = model0.original_canvas(before)
        after_original = final_model.original_canvas(after)
        if guid_uuid not in expected_original_changes and before_original != after_original:
            raise ScaffoldError(f"immutable original canvas changed for {before.name!r}")

    # Reverse every declared patch and require byte-for-byte source XML.
    normalized = current
    for step in reversed(undo):
        normalized = step.apply(normalized)
    if normalized != main_before:
        raise ScaffoldError("reversing whitelist patches does not recover source XML")

    shared_records = [row for row in whitelist if row["kind"] == "shared-original-grid"]
    keyform_records = [row for row in whitelist if row["kind"] == "keyform-positions"]
    parent_records = [row for row in whitelist if row["kind"] == "parent-reference"]
    rotation_records = [row for row in whitelist if row["kind"] == "rotation-origin"]
    column_records = [row for row in whitelist if row["kind"] == "head-grid-columns"]
    expected_keyform_payloads = 3 + 2 + 2 + 84
    if (
        len(shared_records) != 3
        or len(keyform_records) != expected_keyform_payloads
        or len(parent_records) != 28
        or len(rotation_records) != 2
        or len(column_records) != 1
    ):
        raise ScaffoldError(
            "whitelist cardinality differs: "
            f"shared={len(shared_records)}, keyforms={len(keyform_records)}, "
            f"parents={len(parent_records)}, rotations={len(rotation_records)}, "
            f"columns={len(column_records)}"
        )
    if len(coordinate_proof) != 3 + 3 + 84:
        raise ScaffoldError(f"coordinate proof count {len(coordinate_proof)} differs")
    max_error = max(row["max_reconstruction_error_px"] for row in coordinate_proof)
    if max_error >= TOLERANCE:
        raise ScaffoldError("aggregate coordinate proof exceeds tolerance")

    # Exact wrapper geometry and divisions.
    wrapper_final_specs = (
        (final_root, 5, 5, root_original_new),
        (final_body, 5, 5, body_original_new),
        (final_head, 7, 5, head_original_new),
    )
    for item, columns, rows, expected_original in wrapper_final_specs:
        source = final_model.source(item)
        observed = (
            int(canvas._one_direct_named(source, "i", "col").text or "0"),
            int(canvas._one_direct_named(source, "i", "row").text or "0"),
        )
        if observed != (columns, rows):
            raise ScaffoldError(f"final {item.name} grid differs")
        if not _f32_equal(canvas, final_model.original_canvas(item), expected_original):
            raise ScaffoldError(f"final {item.name} original grid differs")

    output_data = safe._replace_main_xml(source_data, current)
    archive_after, _, _, _, decoded_after = safe._validate_surgical_layout(output_data)
    if decoded_after != current:
        raise ScaffoldError("planned archive main.xml differs")
    archive_proof = safe._compare_entry_preservation(
        source_data,
        archive_before,
        output_data,
        archive_after,
        main_may_change=True,
    )
    if archive_proof.get("all_non_main_entries_byte_identical") is not True:
        raise ScaffoldError("non-main archive members changed")

    body_z_final = _object_by_uuid(final_model, BODY_Z_UUID, "final R_BODY")
    head_z_final = _object_by_uuid(final_model, HEAD_Z_UUID, "final R_HEAD")
    body_origin = _form_values(final_model, canvas, body_z_final)[0]
    head_origin = _form_values(final_model, canvas, head_z_final)[0]
    # These are derived from the serialized neutral canvas point
    # (1974.4999673403752, 845.0000821762001), not the rounded UI pivot label.
    expected_body_origin = (0.5993212461471558, 0.28208959102630615)
    # Likewise preserve the serialized point
    # (1752.9999425732815, 1164.9999864581873) through the new body grid.
    expected_head_origin = (0.498361200094223, 0.3784300982952118)
    if not _f32_equal(canvas, body_origin, expected_body_origin):
        raise ScaffoldError(f"R_BODY final origin {body_origin!r} differs")
    if not _f32_equal(canvas, head_origin, expected_head_origin):
        raise ScaffoldError(f"R_HEAD final origin {head_origin!r} differs")

    return output_data, {
        "schema": "jade.cubism.head-wrapper-scaffold-audit.v1",
        "status": "ok",
        "source_sha256": _sha256(source_data),
        "planned_output_sha256": _sha256(output_data),
        "planned_output_bytes": len(output_data),
        "main_xml_sha256_before": _sha256(main_before),
        "main_xml_sha256_after": _sha256(current),
        "main_xml_bytes_before": len(main_before),
        "main_xml_bytes_after": len(current),
        "normalized_exact_source": True,
        "source_zlib_level": source_zip.zlib_level,
        "python_zlib_runtime": safe.zlib.ZLIB_RUNTIME_VERSION,
        "wrapper_geometry": {
            "D_JAD_ROOT": {"divisions": [5, 5], "bounds": list(ROOT_BOUNDS)},
            "D_JAD_BODY_XY": {"divisions": [5, 5], "bounds": list(BODY_BOUNDS)},
            "D_JAD_HEAD_XY": {"divisions": [7, 5], "bounds": list(HEAD_BOUNDS)},
        },
        "rotation_origins": {
            "R_JAD_BODY_Z": list(body_origin),
            "R_JAD_HEAD_Z": list(head_origin),
        },
        "head_contract": {
            "migrated_direct_children": len(head_target_uuids),
            "migrated_names": sorted(HEAD_CHILD_NAMES),
            "R_JAD_HEAD_Z_direct_children": [final_head.name],
            "D_JAD_HEAD_XY_direct_children": sorted(
                item.name for item in _children(final_model, final_head)
            ),
            "D_JAD_HEAD_XY_bindings": 0,
        },
        "whitelist_cardinality": {
            "shared_original_arrays": len(shared_records),
            "keyform_position_arrays": len(keyform_records),
            "parent_references": len(parent_records),
            "rotation_form_openings": len(rotation_records),
            "head_column_fields": column_records[0]["occurrences"],
        },
        "whitelist": whitelist,
        "coordinate_proof_count": len(coordinate_proof),
        "coordinate_proof_max_error_px": max_error,
        "coordinate_proof": coordinate_proof,
        "archive": archive_proof,
    }


def _write_json_exclusive(path: Path, document: dict[str, Any]) -> None:
    payload = (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
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
        raise ScaffoldError("source/output filename differs from pinned transaction")
    if source == output or source.parent != output.parent:
        raise ScaffoldError("source/output must be distinct files in one directory")
    if output.exists() or audit.exists():
        raise ScaffoldError("output or audit already exists; refusing overwrite")
    source_data = source.read_bytes()
    if _sha256(source_data) != SOURCE_SHA256:
        raise ScaffoldError("source SHA-256 differs from pinned checkpoint")
    safe, canvas, topology = _load_dependencies()
    output_data, result = _plan(source_data, safe=safe, canvas=canvas)
    result["tool"] = str(Path(__file__).resolve(strict=True))
    result["tool_sha256"] = _hash_file(Path(__file__).resolve(strict=True))
    result["source"] = str(source)
    result["output"] = str(output)
    result["audit"] = str(audit)
    result["dry_run"] = bool(args.dry_run)
    result["output_written"] = False
    if args.dry_run:
        result["verdict"] = "PASS_DRY_RUN__NO_FILE_WRITTEN"
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0

    created_output = False
    created_audit = False
    try:
        safe._write_new_file(output, output_data)
        created_output = True
        if output.read_bytes() != output_data:
            raise ScaffoldError("written output differs from plan")
        if source.read_bytes() != source_data:
            raise ScaffoldError("source changed during transaction")
        source_inventory = safe._structural_inventory(source)
        output_inventory = safe._structural_inventory(output)
        if _inventory_signature(source_inventory) != _inventory_signature(output_inventory):
            raise ScaffoldError("structural inventory changed outside the contract")
        source_topology = topology.inventory(source, 256 * 1024 * 1024)
        output_topology = topology.inventory(output, 256 * 1024 * 1024)
        if source_topology["aggregate"] != output_topology["aggregate"]:
            raise ScaffoldError("ArtMesh topology aggregate changed")
        source_meshes = {
            row["source_ref"]: {
                key: value
                for key, value in row.items()
                if key not in {"bounds"}
            }
            for row in source_topology["meshes"]
        }
        output_meshes = {
            row["source_ref"]: {
                key: value
                for key, value in row.items()
                if key not in {"bounds"}
            }
            for row in output_topology["meshes"]
        }
        if source_meshes != output_meshes:
            raise ScaffoldError("per-mesh topology changed")
        result["inventory_signature"] = _inventory_signature(output_inventory)
        result["topology_aggregate"] = output_topology["aggregate"]
        result["output_written"] = True
        result["output_sha256"] = _sha256(output_data)
        result["output_bytes"] = len(output_data)
        result["verdict"] = "PASS_TEST_TRANSACTION__CUBISM_5_2_03_GATE_REQUIRED"
        _write_json_exclusive(audit, result)
        created_audit = True
        result["audit_sha256"] = _hash_file(audit)
        result["audit_bytes"] = audit.stat().st_size
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
