#!/usr/bin/env python3
"""Bind Jade's existing head rotation deformer to ParamAngleZ."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Sequence


TOOLS_DIR = Path(__file__).resolve(strict=True).parent
PROJECT_DIR = TOOLS_DIR.parent
REPORTS_DIR = PROJECT_DIR / "reports"
SOURCE_NAME = "Jade_rig_5_2_v003.TEST_eye_lr_mouth_head_xy_r01.cmo3"
SOURCE_SHA256 = "E846A6D37DBBB79933E955E8D06D1401FF1B80D44FA10D2970EC2F824D38D5C0"
SOURCE_BYTES = 2_043_462
OUTPUT_NAME = "Jade_rig_5_2_v003.TEST_eye_lr_mouth_head_xyz_r02.cmo3"
AUDIT_NAME = "Jade_v003.TEST_head_z_functional_r02_audit.json"
HEAD_NAME = "R_JAD_HEAD_Z"
ANGLE_KEYS = (-30.0, 0.0, 30.0)


class HeadZFunctionalError(RuntimeError):
    """Raised when the surgical head-Z edit is not unambiguous."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise HeadZFunctionalError(message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _generated_uuid(role: str) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"jade-cmo3-head-z-functional:{SOURCE_SHA256}:{role}",
        )
    )


def _form_guid_block(form_ref: str, form_idx: int, role: str) -> bytes:
    return (
        f'<CFormGuid uuid="{_generated_uuid(role)}" note="(no debug info)" '
        f'xs.id="{form_ref}" xs.idx="{form_idx}" />'
    ).encode("ascii")


def _binding_block(
    grid_ref: str,
    binding_ref: str,
    binding_idx: int,
    parameter_ref: str,
) -> bytes:
    return (
        "\r\n".join(
            [
                f'<KeyformBindingSource xs.id="{binding_ref}" xs.idx="{binding_idx}">',
                f'<KeyformGridSource xs.n="_gridSource" xs.ref="{grid_ref}" />',
                f'<CParameterGuid xs.n="parameterGuid" xs.ref="{parameter_ref}" />',
                '<array_list xs.n="keys" count="3">',
                "<f>-30.0</f>",
                "<f>0.0</f>",
                "<f>30.0</f>",
                "</array_list>",
                '<InterpolationType xs.n="interpolationType" v="LINEAR" />',
                '<ExtendedInterpolationType xs.n="extendedInterpolationType" v="LINEAR" />',
                '<i xs.n="insertPointCount">1</i>',
                '<f xs.n="extendedInterpolationScale">1.0</f>',
                '<s xs.n="description" />',
                "</KeyformBindingSource>",
            ]
        )
    ).encode("ascii")


def _clone_rotation_form(
    neutral: bytes,
    *,
    neutral_form_ref: str,
    form_ref: str,
    angle: float,
) -> bytes:
    old_guid = f'<CFormGuid xs.n="guid" xs.ref="{neutral_form_ref}" />'.encode(
        "ascii"
    )
    new_guid = f'<CFormGuid xs.n="guid" xs.ref="{form_ref}" />'.encode("ascii")
    _require(neutral.count(old_guid) == 1, "neutral rotation form GUID differs")
    result = neutral.replace(old_guid, new_guid, 1)
    pattern = re.compile(
        rb'(<CRotationDeformerForm\b(?=[^>]*\bangle=")[^>]*\bangle=")[^"]*(")'
    )
    matches = list(pattern.finditer(result))
    _require(len(matches) == 1, "rotation angle attribute is ambiguous")
    match = matches[0]
    token = f"{angle:.1f}".encode("ascii")
    return result[: match.start()] + match.group(1) + token + match.group(2) + result[match.end() :]


def _bind_source(
    source: bytes,
    *,
    grid_ref: str,
    neutral_form_ref: str,
    left_form_ref: str,
    right_form_ref: str,
) -> tuple[bytes, bytes]:
    grid_pattern = re.compile(
        rb'<KeyformGridSource\b(?=[^>]*\bxs\.n="keyformGridSource")[^>]*>'
        rb".*?</KeyformGridSource>",
        re.DOTALL,
    )
    grids = list(grid_pattern.finditer(source))
    _require(len(grids) == 1, "head Z inline grid is ambiguous")
    grid = grids[0]
    result = (
        source[: grid.start()]
        + f'<KeyformGridSource xs.n="keyformGridSource" xs.ref="{grid_ref}" />'.encode(
            "ascii"
        )
        + source[grid.end() :]
    )
    list_pattern = re.compile(
        rb'<carray_list\b(?=[^>]*\bxs\.n="keyforms")[^>]*>\r?\n'
        rb"(.*?)\r?\n</carray_list>",
        re.DOTALL,
    )
    lists = list(list_pattern.finditer(result))
    _require(len(lists) == 1, "head Z keyform list is ambiguous")
    keyforms = lists[0]
    neutral = keyforms.group(1)
    _require(
        neutral.startswith(b"<CRotationDeformerForm ")
        and neutral.endswith(b"</CRotationDeformerForm>")
        and neutral.count(b"<CRotationDeformerForm ") == 1,
        "head Z does not have one neutral rotation form",
    )
    left = _clone_rotation_form(
        neutral,
        neutral_form_ref=neutral_form_ref,
        form_ref=left_form_ref,
        angle=-30.0,
    )
    right = _clone_rotation_form(
        neutral,
        neutral_form_ref=neutral_form_ref,
        form_ref=right_form_ref,
        angle=30.0,
    )
    replacement = (
        b'<carray_list xs.n="keyforms" count="3">\r\n'
        + b"\r\n".join((left, neutral, right))
        + b"\r\n</carray_list>"
    )
    bound = result[: keyforms.start()] + replacement + result[keyforms.end() :]
    return bound, neutral


def _write_json_exclusive(path: Path, document: dict[str, Any]) -> None:
    data = (
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise


def _plan(source_data: bytes) -> tuple[bytes, dict[str, Any]]:
    sys.path.insert(0, str(TOOLS_DIR))
    import cmo3_create_deformer_experiment as experiment
    import cmo3_eye_l_functional as blink
    import cmo3_eye_r_functional as right
    import cmo3_reparent_preserve_canvas as geometry
    import cmo3_safe_roundtrip as safe

    archive, _entry, _location, _zip, main_before = safe._validate_surgical_layout(
        source_data
    )
    root_before = experiment._parse_xml(main_before)
    model_before = geometry.GeometryModel(main_before, 0.001)
    candidates = [
        item
        for item in model_before.objects
        if item.object_type == "rotation-deformer" and item.name == HEAD_NAME
    ]
    _require(len(candidates) == 1, "R_JAD_HEAD_Z is missing or ambiguous")
    head_z = candidates[0]
    source_before = model_before.source(head_z)
    keyforms = experiment._one_named(source_before, "carray_list", "keyforms")
    _require(len(keyforms) == 1, "R_JAD_HEAD_Z is not single-form")
    neutral_form_node = keyforms[0]
    _require(
        neutral_form_node.tag == "CRotationDeformerForm"
        and float(neutral_form_node.get("angle", "nan")) == 0.0
        and float(neutral_form_node.get("scale", "nan")) == 1.0
        and neutral_form_node.get("isReflectX") == "false"
        and neutral_form_node.get("isReflectY") == "false",
        "R_JAD_HEAD_Z neutral form differs",
    )
    neutral_form_ref = str(
        experiment._one_named(neutral_form_node, "CFormGuid", "guid").get(
            "xs.ref"
        )
    )
    grid = experiment._one_named(
        source_before, "KeyformGridSource", "keyformGridSource"
    )
    _require(grid.get("xs.ref") is None, "R_JAD_HEAD_Z is already bound")
    parameter = right._one_shared_note(root_before, "CParameterGuid", "ParamAngleZ")
    parameter_ref = str(parameter.get("xs.id"))
    _require(parameter_ref.startswith("#"), "ParamAngleZ ref differs")

    slots = right._allocate_serial_slots(
        root_before,
        ("grid", "binding", "left_form", "right_form"),
    )
    grid_ref, grid_idx = slots["grid"]
    binding_ref, binding_idx = slots["binding"]
    left_form_ref, left_form_idx = slots["left_form"]
    right_form_ref, right_form_idx = slots["right_form"]
    _start, _end, raw_source = safe._source_block_span(main_before, head_z)
    bound_source, neutral_raw = _bind_source(
        raw_source,
        grid_ref=grid_ref,
        neutral_form_ref=neutral_form_ref,
        left_form_ref=left_form_ref,
        right_form_ref=right_form_ref,
    )
    current = experiment._replace_exact(
        main_before,
        raw_source,
        bound_source,
        1,
        "bind R_JAD_HEAD_Z",
    )
    shared_blocks = [
        blink._grid_block(
            grid_ref,
            grid_idx,
            binding_ref,
            (left_form_ref, neutral_form_ref, right_form_ref),
        ),
        _binding_block(grid_ref, binding_ref, binding_idx, parameter_ref),
        _form_guid_block(left_form_ref, left_form_idx, "left-form"),
        _form_guid_block(right_form_ref, right_form_idx, "right-form"),
    ]
    current = experiment._append_shared_blocks(current, shared_blocks)

    model_after = geometry.GeometryModel(current, 0.001)
    final = next(item for item in model_after.objects if item.name == HEAD_NAME)
    _require(
        [(item.name, item.guid_uuid, item.parent_uuid) for item in model_after.objects]
        == [(item.name, item.guid_uuid, item.parent_uuid) for item in model_before.objects],
        "object identity/hierarchy changed",
    )
    final_source = model_after.source(final)
    final_forms = experiment._one_named(final_source, "carray_list", "keyforms")
    _require(len(final_forms) == 3, "final head Z form count differs")
    angles = [float(form.get("angle", "nan")) for form in final_forms]
    origins = [
        [float(form.get("originX", "nan")), float(form.get("originY", "nan"))]
        for form in final_forms
    ]
    _require(angles == list(ANGLE_KEYS), "final head Z angles differ")
    _require(
        origins[0] == origins[1] == origins[2]
        and all(float(form.get("scale", "nan")) == 1.0 for form in final_forms)
        and all(form.get("isReflectX") == "false" for form in final_forms)
        and all(form.get("isReflectY") == "false" for form in final_forms),
        "head Z pivot/scale/reflection changed",
    )
    _after_start, _after_end, final_raw_source = safe._source_block_span(current, final)
    final_form_blocks = re.findall(
        rb"<CRotationDeformerForm .*?</CRotationDeformerForm>",
        final_raw_source,
        re.DOTALL,
    )
    _require(
        len(final_form_blocks) == 3 and final_form_blocks[1] == neutral_raw,
        "neutral head Z form is not byte-exact",
    )
    grid_link = experiment._one_named(
        final_source, "KeyformGridSource", "keyformGridSource"
    )
    _require(grid_link.get("xs.ref") == grid_ref, "final head Z grid ref differs")
    final_grid = model_after.ids[grid_ref]
    grid_forms = experiment._one_named(final_grid, "array_list", "keyformsOnGrid")
    grid_bindings = experiment._one_named(final_grid, "array_list", "keyformBindings")
    _require(len(grid_forms) == 3 and len(grid_bindings) == 1, "head Z grid cardinality differs")
    access_indices = []
    for form in grid_forms:
        access = experiment._one_named(form, "array_list", "_keyOnParameterList")
        access_indices.append(
            int(experiment._one_named(access[0], "i", "keyIndex").text or "-1")
        )
    _require(access_indices == [0, 1, 2], "head Z key access differs")

    preserved = 0
    after_by_uuid = {item.guid_uuid: item for item in model_after.objects}
    for item in model_before.objects:
        if item.guid_uuid == head_z.guid_uuid:
            continue
        after_item = after_by_uuid[item.guid_uuid]
        _require(
            safe._source_block_span(main_before, item)[2]
            == safe._source_block_span(current, after_item)[2],
            f"{item.name}: source changed",
        )
        preserved += 1
    output_data = safe._replace_main_xml(source_data, current)
    audit = {
        "schema": "jade.cubism.head-z-functional-pre-cubism-audit.v1",
        "status": "ok",
        "operation": "bind_R_JAD_HEAD_Z_to_ParamAngleZ",
        "source_sha256": SOURCE_SHA256,
        "main_xml_sha256_before": _sha256(main_before),
        "main_xml_sha256_after": _sha256(current),
        "planned_output_sha256": _sha256(output_data),
        "planned_output_bytes": len(output_data),
        "archive_entries": len(archive.entries),
        "head_z": {
            "name": HEAD_NAME,
            "parameter": "ParamAngleZ",
            "keys": list(ANGLE_KEYS),
            "angles": angles,
            "origin": origins[1],
            "scale": 1.0,
            "neutral_form_index": 1,
            "neutral_form_preserved_byte_exact": True,
            "direct_children": [
                item.name
                for item in model_after.objects
                if item.parent_uuid == final.guid_uuid
            ],
        },
        "preserved_non_head_z_object_sources": preserved,
        "cubism_5_2_03_load_save_required": True,
        "grouped_visual_head_xyz_check_required": True,
        "verdict": "PASS_HEAD_Z_FUNCTIONAL__CUBISM_5_2_03_LOAD_REQUIRED",
    }
    return output_data, audit


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    source = args.source.resolve(strict=True)
    output = args.output.resolve(strict=False)
    audit_path = output.with_name(AUDIT_NAME)
    _require(
        source.parent == REPORTS_DIR
        and output.parent == REPORTS_DIR
        and source.name == SOURCE_NAME
        and output.name == OUTPUT_NAME
        and source != output,
        "source/output path differs from the head-Z gate",
    )
    _require(not output.exists() and not audit_path.exists(), "exclusive output exists")
    source_data = source.read_bytes()
    _require(
        len(source_data) == SOURCE_BYTES and _sha256(source_data) == SOURCE_SHA256,
        "source bytes/SHA differs from pinned Cubism checkpoint",
    )
    output_data, audit = _plan(source_data)
    audit.update(
        {
            "source": str(source),
            "output": str(output),
            "audit": str(audit_path),
            "dry_run": bool(args.dry_run),
            "output_written": False,
            "tool": str(Path(__file__).resolve(strict=True)),
            "tool_sha256": _sha256(Path(__file__).read_bytes()),
        }
    )
    _require(source.read_bytes() == source_data, "source changed during planning")
    if args.dry_run:
        audit["verdict"] = "PASS_DRY_RUN__NO_FILE_WRITTEN"
        print(json.dumps(audit, ensure_ascii=False, sort_keys=True))
        return 0

    sys.path.insert(0, str(TOOLS_DIR))
    import cmo3_safe_roundtrip as safe

    created_output = False
    created_audit = False
    try:
        safe._write_new_file(output, output_data)
        created_output = True
        audit["output_written"] = True
        audit["output_sha256"] = _sha256(output_data)
        audit["output_bytes"] = len(output_data)
        _write_json_exclusive(audit_path, audit)
        created_audit = True
        print(json.dumps(audit, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception:
        if created_audit:
            audit_path.unlink(missing_ok=True)
        if created_output:
            output.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HeadZFunctionalError as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
