#!/usr/bin/env python3
"""Bind Jade's left GAZE warp to ParamEyeBallX/Y for Cubism 5.2.03."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Sequence


TOOLS_DIR = Path(__file__).resolve(strict=True).parent
PROJECT_DIR = TOOLS_DIR.parent
REPORTS_DIR = (PROJECT_DIR / "reports").resolve(strict=True)

SOURCE_NAME = "Jade_rig_5_2_v003.TEST_eye_l_functional_r01.cmo3"
SOURCE_SHA256 = "9F7953A8242D4631C5557AC84B5CBD4A7833ED2CE9F5F10E6FB2F4CE2F1F8D92"
SOURCE_BYTES = 2_029_139
OUTPUT_NAME = "Jade_rig_5_2_v003.TEST_eye_l_blink_gaze_r01.cmo3"
AUDIT_NAME = "Jade_v003.TEST_eye_l_blink_gaze_r01_audit.json"
GAZE_SOURCE_REF = "#1089"
GAZE_NEUTRAL_FORM_REF = "#1091"
PARAM_EYE_BALL_X_GUID_REF = "#1333"
PARAM_EYE_BALL_Y_GUID_REF = "#1334"
TOLERANCE = 0.001
AMPLITUDE_X_PX = 22.0
AMPLITUDE_Y_PX = 10.0


class EyeLGazeError(RuntimeError):
    """Raised if the left gaze transaction cannot be proven safe."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EyeLGazeError(message)


def _load_stack() -> tuple[Any, ...]:
    sys.path.insert(0, str(TOOLS_DIR))
    import cmo3_eye_l_functional as blink

    return (blink, *blink._load_stack())


def _generated_uuid(role: str) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"jade-cmo3-face-s2c-left-gaze:{SOURCE_SHA256}:{role}",
        )
    )


def _form_guid_block(form_ref: str, form_idx: int, role: str) -> bytes:
    return (
        f'<CFormGuid uuid="{_generated_uuid(role)}" note="(no debug info)" '
        f'xs.id="{form_ref}" xs.idx="{form_idx}" />'
    ).encode("ascii")


def _binding_block(
    *,
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
                "<f>-1.0</f>",
                "<f>0.0</f>",
                "<f>1.0</f>",
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


def _grid_block(
    *,
    grid_ref: str,
    grid_idx: int,
    binding_x_ref: str,
    binding_y_ref: str,
    form_refs: Sequence[str],
) -> bytes:
    _require(len(form_refs) == 9, "gaze form-ref count differs")
    rows: list[str] = [
        f'<KeyformGridSource xs.id="{grid_ref}" xs.idx="{grid_idx}">',
        '<array_list xs.n="keyformsOnGrid" count="9">',
    ]
    for y_index in range(3):
        for x_index in range(3):
            form_ref = form_refs[3 * y_index + x_index]
            rows.extend(
                [
                    "<KeyformOnGrid>",
                    '<KeyformGridAccessKey xs.n="accessKey">',
                    '<array_list xs.n="_keyOnParameterList" count="2">',
                    "<KeyOnParameter>",
                    f'<KeyformBindingSource xs.n="binding" xs.ref="{binding_x_ref}" />',
                    f'<i xs.n="keyIndex">{x_index}</i>',
                    "</KeyOnParameter>",
                    "<KeyOnParameter>",
                    f'<KeyformBindingSource xs.n="binding" xs.ref="{binding_y_ref}" />',
                    f'<i xs.n="keyIndex">{y_index}</i>',
                    "</KeyOnParameter>",
                    "</array_list>",
                    "</KeyformGridAccessKey>",
                    f'<CFormGuid xs.n="keyformGuid" xs.ref="{form_ref}" />',
                    "</KeyformOnGrid>",
                ]
            )
    rows.extend(
        [
            "</array_list>",
            '<array_list xs.n="keyformBindings" count="2">',
            f'<KeyformBindingSource xs.ref="{binding_x_ref}" />',
            f'<KeyformBindingSource xs.ref="{binding_y_ref}" />',
            "</array_list>",
            "</KeyformGridSource>",
        ]
    )
    return "\r\n".join(rows).encode("ascii")


def _bind_source(
    source_block: bytes,
    *,
    form_refs: Sequence[str],
    form_positions: Sequence[Sequence[float]],
    blink: Any,
    face: Any,
    experiment: Any,
) -> bytes:
    _require(len(form_refs) == len(form_positions) == 9, "gaze form plan differs")
    grid_pattern = re.compile(
        rb'<KeyformGridSource\b(?=[^>]*\bxs\.n="keyformGridSource")[^>]*>'
        rb'.*?</KeyformGridSource>',
        re.DOTALL,
    )
    matches = list(grid_pattern.finditer(source_block))
    _require(len(matches) == 1, "GAZE inline grid is ambiguous")
    match = matches[0]
    result = (
        source_block[: match.start()]
        + b'<KeyformGridSource xs.n="keyformGridSource" xs.ref="#1382" />'
        + source_block[match.end() :]
    )
    list_pattern = re.compile(
        rb'<carray_list\b(?=[^>]*\bxs\.n="keyforms")[^>]*>\r\n'
        rb'(.*?)\r\n</carray_list>',
        re.DOTALL,
    )
    matches = list(list_pattern.finditer(result))
    _require(len(matches) == 1, "GAZE keyform list is ambiguous")
    match = matches[0]
    neutral_form = match.group(1)
    _require(
        neutral_form.startswith(b"<CWarpDeformerForm>")
        and neutral_form.endswith(b"</CWarpDeformerForm>")
        and neutral_form.count(b"<CWarpDeformerForm>") == 1,
        "GAZE neutral form differs",
    )
    forms = [
        blink._form_clone(
            neutral_form,
            old_guid_ref=GAZE_NEUTRAL_FORM_REF,
            new_guid_ref=form_ref,
            opacity=1.0,
            positions=positions,
            face=face,
            experiment=experiment,
            label=f"left GAZE form {index}",
        )
        for index, (form_ref, positions) in enumerate(zip(form_refs, form_positions))
    ]
    replacement = (
        b'<carray_list xs.n="keyforms" count="9">\r\n'
        + b"\r\n".join(forms)
        + b"\r\n</carray_list>"
    )
    return result[: match.start()] + replacement + result[match.end() :]


def _binding_state(model: Any, gaze: Any, experiment: Any) -> dict[str, Any]:
    source = model.source(gaze)
    grid_link = experiment._one_named(source, "KeyformGridSource", "keyformGridSource")
    grid = model.ids[str(grid_link.get("xs.ref"))]
    keyforms = experiment._one_named(grid, "array_list", "keyformsOnGrid")
    bindings = experiment._one_named(grid, "array_list", "keyformBindings")
    _require(len(keyforms) == 9 and len(bindings) == 2, "GAZE grid counts differ")
    binding_refs = [str(node.get("xs.ref")) for node in bindings]
    parameter_refs: list[str] = []
    keys: list[list[float]] = []
    for binding_ref in binding_refs:
        binding = model.ids[binding_ref]
        parameter = experiment._one_named(binding, "CParameterGuid", "parameterGuid")
        key_list = experiment._one_named(binding, "array_list", "keys")
        parameter_refs.append(str(parameter.get("xs.ref")))
        keys.append([float(node.text or "nan") for node in key_list])
    form_refs: list[str] = []
    access_indices: list[list[int]] = []
    for keyform in keyforms:
        form_refs.append(
            str(experiment._one_named(keyform, "CFormGuid", "keyformGuid").get("xs.ref"))
        )
        access = experiment._one_named(keyform, "array_list", "_keyOnParameterList")
        _require(len(access) == 2, "GAZE access cardinality differs")
        row: list[int] = []
        for index, key_on_parameter in enumerate(access):
            binding = experiment._one_named(
                key_on_parameter, "KeyformBindingSource", "binding"
            )
            key_index = experiment._one_named(key_on_parameter, "i", "keyIndex")
            _require(
                binding.get("xs.ref") == binding_refs[index],
                "GAZE access binding order differs",
            )
            row.append(int(key_index.text or "-1"))
        access_indices.append(row)
    forms = experiment._one_named(source, "carray_list", "keyforms")
    source_form_refs = [
        str(experiment._one_named(form, "CFormGuid", "guid").get("xs.ref"))
        for form in forms
    ]
    _require(
        parameter_refs == [PARAM_EYE_BALL_X_GUID_REF, PARAM_EYE_BALL_Y_GUID_REF]
        and keys == [[-1.0, 0.0, 1.0], [-1.0, 0.0, 1.0]]
        and access_indices
        == [[x_index, y_index] for y_index in range(3) for x_index in range(3)]
        and source_form_refs == form_refs,
        "GAZE 3x3 binding semantics differ",
    )
    return {
        "grid_ref": grid_link.get("xs.ref"),
        "binding_refs": binding_refs,
        "parameter_guid_refs": parameter_refs,
        "keys": keys,
        "form_refs": form_refs,
        "access_indices": access_indices,
    }


def _plan(source_data: bytes, stack: tuple[Any, ...]) -> tuple[bytes, dict[str, Any]]:
    blink, _eye, face, head, experiment, scaffold, safe, canvas, topology, _inventory = stack
    archive_before, _entry, _location, _zip, main_before = safe._validate_surgical_layout(
        source_data
    )
    root_before = experiment._parse_xml(main_before)
    ids_before = experiment._id_map(root_before)
    numeric_ids = sorted(int(key[1:]) for key in ids_before)
    existing_indices = [int(node.get("xs.idx")) for node in root_before.find("shared")]
    _require(
        numeric_ids == list(range(1382)) and max(existing_indices) == 8009,
        "source serialized tail differs",
    )
    new_indices = set(range(9000, 10100, 100))
    _require(len(new_indices) == 11 and not new_indices.intersection(existing_indices), "new xs.idx collision")
    for parameter_ref, note in (
        (PARAM_EYE_BALL_X_GUID_REF, "ParamEyeBallX"),
        (PARAM_EYE_BALL_Y_GUID_REF, "ParamEyeBallY"),
    ):
        parameter = ids_before.get(parameter_ref)
        _require(
            parameter is not None
            and parameter.tag == "CParameterGuid"
            and parameter.get("note") == note,
            f"{note} GUID differs",
        )

    model_before = canvas.GeometryModel(main_before, TOLERANCE)
    gaze_before = head._object_by_name(model_before, "D_JAD_EYE_L_GAZE", "left GAZE")
    open_before = head._object_by_name(model_before, "D_JAD_EYE_L_OPEN", "left OPEN")
    _require(
        gaze_before.source_ref == GAZE_SOURCE_REF
        and gaze_before.parent_uuid == open_before.guid_uuid,
        "left GAZE source/hierarchy differs",
    )
    neutral_forms = scaffold._form_values(model_before, canvas, gaze_before)
    _require(len(neutral_forms) == 1 and len(neutral_forms[0]) == 32, "GAZE neutral grid differs")
    neutral_local = neutral_forms[0]
    original_canvas = model_before.original_canvas(gaze_before)
    parent_transform = model_before.transform(open_before.guid_ref)

    form_refs = (
        "#1385",
        "#1386",
        "#1387",
        "#1388",
        GAZE_NEUTRAL_FORM_REF,
        "#1389",
        "#1390",
        "#1391",
        "#1392",
    )
    form_positions: list[tuple[float, ...]] = []
    pose_errors: dict[str, float] = {}
    for y_value in (-1.0, 0.0, 1.0):
        for x_value in (-1.0, 0.0, 1.0):
            if x_value == 0.0 and y_value == 0.0:
                local = tuple(neutral_local)
                target = original_canvas
            else:
                target_values: list[float] = []
                edge_falloff = (0.15, 1.0, 1.0, 0.15)
                for point_index, (x, y) in enumerate(
                    zip(original_canvas[0::2], original_canvas[1::2])
                ):
                    column = point_index % 4
                    row = point_index // 4
                    weight = edge_falloff[column] * edge_falloff[row]
                    target_values.extend(
                        (
                            x + AMPLITUDE_X_PX * x_value * weight,
                            y - AMPLITUDE_Y_PX * y_value * weight,
                        )
                    )
                target = tuple(target_values)
                local = tuple(
                    canvas._float32(value)
                    for value in model_before.inverse_many(parent_transform, target)
                )
            reconstructed = model_before.forward_many(parent_transform, local)
            error = canvas._maximum_error(target, reconstructed)
            _require(error < TOLERANCE, "GAZE pose reconstruction exceeds tolerance")
            pose_errors[f"x={x_value:+.0f},y={y_value:+.0f}"] = error
            form_positions.append(local)

    gaze_source = experiment._block_by_id(
        main_before, "CWarpDeformerSource", gaze_before.source_ref
    )
    gaze_bound = _bind_source(
        gaze_source,
        form_refs=form_refs,
        form_positions=form_positions,
        blink=blink,
        face=face,
        experiment=experiment,
    )
    current = experiment._replace_exact(
        main_before, gaze_source, gaze_bound, 1, "bind left GAZE"
    )
    new_blocks = [
        _grid_block(
            grid_ref="#1382",
            grid_idx=9000,
            binding_x_ref="#1383",
            binding_y_ref="#1384",
            form_refs=form_refs,
        ),
        _binding_block(
            grid_ref="#1382",
            binding_ref="#1383",
            binding_idx=9100,
            parameter_ref=PARAM_EYE_BALL_X_GUID_REF,
        ),
        _binding_block(
            grid_ref="#1382",
            binding_ref="#1384",
            binding_idx=9200,
            parameter_ref=PARAM_EYE_BALL_Y_GUID_REF,
        ),
    ]
    new_form_refs = [ref for ref in form_refs if ref != GAZE_NEUTRAL_FORM_REF]
    for index, form_ref in enumerate(new_form_refs):
        new_blocks.append(
            _form_guid_block(
                form_ref,
                9300 + index * 100,
                f"gaze-form-{index}",
            )
        )
    current = experiment._append_shared_blocks(current, new_blocks)

    final_model = canvas.GeometryModel(current, TOLERANCE)
    gaze_final = head._object_by_name(final_model, "D_JAD_EYE_L_GAZE", "left GAZE")
    binding_state = _binding_state(final_model, gaze_final, experiment)
    _require(
        final_model.transform(gaze_final.guid_ref).neutral_keyform_index == 4,
        "GAZE neutral form is not the center key",
    )
    for stable_name in ("D_JAD_EYE_L_OPEN", "D_JAD_EYE_L_CLOSED"):
        stable_before = head._object_by_name(model_before, stable_name, stable_name)
        stable_after = head._object_by_name(final_model, stable_name, stable_name)
        _require(
            experiment._block_by_id(main_before, "CWarpDeformerSource", stable_before.source_ref)
            == experiment._block_by_id(current, "CWarpDeformerSource", stable_after.source_ref),
            f"{stable_name} changed while binding gaze",
        )
    _require(
        head._topology_xml(main_before, experiment=experiment, topology=topology)
        == head._topology_xml(current, experiment=experiment, topology=topology),
        "ArtMesh topology changed",
    )
    root_after = experiment._parse_xml(current)
    ids_after = experiment._id_map(root_after)
    _require(
        sorted(int(key[1:]) for key in ids_after) == list(range(1393)),
        "final xs.id range differs",
    )

    output_data = safe._replace_main_xml(source_data, current)
    archive_after, _entry_after, _loc_after, _zip_after, decoded_after = (
        safe._validate_surgical_layout(output_data)
    )
    _require(decoded_after == current, "planned archive main.xml differs")
    archive_proof = safe._compare_entry_preservation(
        source_data,
        archive_before,
        output_data,
        archive_after,
        main_may_change=True,
    )
    _require(
        archive_proof.get("all_non_main_entries_byte_identical") is True
        and archive_proof.get("changed_stored_entries") == ["main.xml"],
        "non-main archive members changed",
    )
    return output_data, {
        "schema": "jade.cubism.eye-l-gaze-pre-cubism-audit.v1",
        "status": "ok",
        "verdict": "PASS_FACE_S2C2_LEFT_GAZE_3X3__CUBISM_5_2_03_LOAD_REQUIRED",
        "operation": "bind_D_JAD_EYE_L_GAZE_to_ParamEyeBallXY",
        "source_sha256": blink._sha256(source_data),
        "source_bytes": len(source_data),
        "planned_output_sha256": blink._sha256(output_data),
        "planned_output_bytes": len(output_data),
        "main_xml_sha256_before": blink._sha256(main_before),
        "main_xml_sha256_after": blink._sha256(current),
        "binding": binding_state,
        "inner_control_point_amplitude_canvas_px": {
            "x": AMPLITUDE_X_PX,
            "y": AMPLITUDE_Y_PX,
        },
        "edge_falloff": [0.15, 1.0, 1.0, 0.15],
        "maximum_pose_reconstruction_error_px": max(pose_errors.values()),
        "pose_reconstruction_errors_px": pose_errors,
        "new_shared_definitions": 11,
        "blink_sources_preserved_byte_exact": True,
        "archive": archive_proof,
        "cubism_5_2_03_load_save_required": True,
        "visual_blink_and_gaze_check_required": True,
    }


def _write_json_exclusive(path: Path, document: dict[str, Any]) -> None:
    payload = (
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise


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
        "source/output path differs from the FACE-S2c gaze gate",
    )
    _require(not output.exists() and not audit_path.exists(), "exclusive output already exists")
    source_data = source.read_bytes()
    stack = _load_stack()
    blink = stack[0]
    _require(
        len(source_data) == SOURCE_BYTES and blink._sha256(source_data) == SOURCE_SHA256,
        "source bytes/SHA differs from pinned Cubism checkpoint",
    )
    output_data, audit = _plan(source_data, stack)
    tool_path = Path(__file__).resolve(strict=True)
    audit.update(
        {
            "tool": str(tool_path),
            "tool_sha256": blink._sha256(tool_path.read_bytes()),
            "source": str(source),
            "output": str(output),
            "audit": str(audit_path),
            "dry_run": bool(args.dry_run),
            "output_written": False,
        }
    )
    _require(source.read_bytes() == source_data, "source changed during planning")
    if args.dry_run:
        audit["verdict"] = "PASS_DRY_RUN__NO_FILE_WRITTEN"
        print(json.dumps(audit, ensure_ascii=False, sort_keys=True))
        return 0

    safe = stack[6]
    created_output = False
    created_audit = False
    try:
        safe._write_new_file(output, output_data)
        created_output = True
        _require(output.read_bytes() == output_data, "written output differs")
        audit["output_written"] = True
        audit["output_sha256"] = blink._sha256(output_data)
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
    except EyeLGazeError as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
