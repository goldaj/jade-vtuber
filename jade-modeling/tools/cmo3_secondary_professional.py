#!/usr/bin/env python3
"""Finish Jade's eye-smile, blush and independent secondary-output rig.

The source is always read-only.  The command accepts any later Jade checkpoint
that still exposes the audited semantic object/parameter names, writes only a
new destination, and refuses overwrite.  ``--dry-run`` executes every mutation
and invariant in memory.

Stages are deliberately selectable so this transaction can be composed after
the eyebrow/mouth professional pass::

    python tools/cmo3_secondary_professional.py SOURCE OUTPUT --stages face
    python tools/cmo3_secondary_professional.py SOURCE OUTPUT --stages all

``face`` adds real EyeSmile cross-grids and makes the two existing blush
ArtMeshes invisible at ParamCheek=0 and fully visible at 1.  ``secondary`` adds
four independent output parameters, transfers the existing ear/dress poses to
them, and gives the existing ahoge ArtMesh a restrained tip swing.
"""

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
TOLERANCE = 0.001
FACE_TARGETS = {
    "D_JAD_EYE_L_OPEN": ("ParamEyeLOpen", "ParamEyeLSmile", "open"),
    "D_JAD_EYE_L_CLOSED": ("ParamEyeLOpen", "ParamEyeLSmile", "closed"),
    "D_JAD_EYE_R_OPEN": ("ParamEyeROpen", "ParamEyeRSmile", "open"),
    "D_JAD_EYE_R_CLOSED": ("ParamEyeROpen", "ParamEyeRSmile", "closed"),
}
SECONDARY_PARAMETERS = {
    "ParamEarSwingL": ("Ear Swing L", "Independent left ear follow-through"),
    "ParamEarSwingR": ("Ear Swing R", "Independent right ear follow-through"),
    "ParamAhogeSwing": ("Ahoge Swing", "Independent ahoge follow-through"),
    "ParamClothSwing": ("Cloth Swing", "Independent sleeve and skirt follow-through"),
}
SECONDARY_REBIND = {
    "D_JAD_EAR_L_MASTER": ("ParamAngleX", "ParamEarSwingL"),
    "D_JAD_EAR_R_MASTER": ("ParamAngleX", "ParamEarSwingR"),
    "D_JAD_DRESS_MAIN": ("ParamBodyAngleX", "ParamClothSwing"),
}
# The three inherited bindings were authored on AngleX [-30,+30] and BodyX
# [-10,+10].  Independent secondary parameters use [-1,+1], so their binding
# keys must be normalized or Cubism only evaluates 1/30 and 1/10 of the pose.
# A restrained 1.6 endpoint gain then puts the exported Core displacement in
# the production target bands (ears ~14 px, cloth ~22 px) without changing the
# neutral keyform.
SECONDARY_WARP_TUNING = {
    "D_JAD_EAR_L_MASTER": ((-30.0, 0.0, 30.0), 1.6),
    "D_JAD_EAR_R_MASTER": ((-30.0, 0.0, 30.0), 1.6),
    "D_JAD_DRESS_MAIN": ((-10.0, 0.0, 10.0), 1.6),
}
SECONDARY_OUTPUT_KEYS = (-1.0, 0.0, 1.0)
AHOGE_SWING_PX = 18.0


class SecondaryProfessionalError(RuntimeError):
    """Raised when a semantic or byte-preservation gate fails."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SecondaryProfessionalError(message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _load_modules() -> tuple[Any, ...]:
    sys.path.insert(0, str(TOOLS_DIR))
    import cmo3_create_deformer_experiment as experiment
    import cmo3_face_fx_scaffold as face
    import cmo3_hair_back_functional as hair_back
    import cmo3_head_wrapper_scaffold as scaffold
    import cmo3_reparent_preserve_canvas as canvas
    import cmo3_safe_roundtrip as safe

    return experiment, face, hair_back, scaffold, canvas, safe


def _generated_uuid(source_sha: str, role: str) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"jade-cmo3-secondary-professional:{source_sha}:{role}",
        )
    )


def _object(model: Any, name: str) -> Any:
    matches = [item for item in model.objects if item.name == name]
    _require(len(matches) == 1, f"object {name!r} is not unique")
    return matches[0]


def _shared_note(root: Any, tag: str, note: str) -> Any:
    shared = root.find("shared")
    _require(shared is not None, "shared section is missing")
    matches = [node for node in shared if node.tag == tag and node.get("note") == note]
    _require(len(matches) == 1, f"{tag} note {note!r} is not unique")
    return matches[0]


def _allocate(root: Any, roles: Sequence[str]) -> dict[str, tuple[str, int]]:
    shared = root.find("shared")
    _require(shared is not None, "shared section is missing")
    ids = [int(node.get("xs.id", "#-1")[1:]) for node in shared]
    indices = [int(node.get("xs.idx", "-1")) for node in shared]
    _require(ids and sorted(ids) == list(range(max(ids) + 1)), "xs.id range differs")
    _require(len(indices) == len(set(indices)), "source xs.idx collision")
    first_id = max(ids) + 1
    first_index = ((max(indices) // 100) + 1) * 100
    return {
        role: (f"#{first_id + offset}", first_index + 100 * offset)
        for offset, role in enumerate(roles)
    }


def _raw_source(main: bytes, model: Any, item: Any, experiment: Any) -> bytes:
    return experiment._block_by_id(main, model.source(item).tag, item.source_ref)


def _keyforms(source_block: bytes, form_tag: bytes) -> tuple[Any, list[bytes]]:
    pattern = re.compile(
        rb'<carray_list\b(?=[^>]*\bxs\.n="keyforms")[^>]*>\r\n'
        rb"(.*?)\r\n</carray_list>",
        re.DOTALL,
    )
    matches = list(pattern.finditer(source_block))
    _require(len(matches) == 1, "keyform list is ambiguous")
    forms = re.findall(
        rb"<" + form_tag + rb">.*?</" + form_tag + rb">",
        matches[0].group(1),
        re.DOTALL,
    )
    return matches[0], forms


def _form_ref(form: bytes) -> str:
    match = re.search(
        rb'<CFormGuid\b(?=[^>]*\bxs\.n="guid")(?=[^>]*\bxs\.ref="([^"]+)")[^>]*/>',
        form,
    )
    _require(match is not None, "form GUID is missing")
    return match.group(1).decode("ascii")


def _form_opacity(form: bytes) -> float:
    matches = list(
        re.finditer(
            rb'<f\b(?=[^>]*\bxs\.n="opacity")[^>]*>([^<]*)</f>',
            form,
        )
    )
    _require(len(matches) == 1, "form opacity is ambiguous")
    return float(matches[0].group(1))


def _compress_eye_open(
    values: Sequence[float], factor: float, canvas: Any
) -> tuple[float, ...]:
    ys = values[1::2]
    center = (min(ys) + max(ys)) * 0.5
    result: list[float] = []
    for x, y in zip(values[0::2], ys):
        result.extend((x, center + (y - center) * factor))
    return tuple(canvas._float32(value) for value in result)


def _clone_form(
    form: bytes,
    *,
    new_ref: str,
    opacity: float | None,
    positions: Sequence[float] | None,
    multiply: tuple[float, float, float, float] | None,
    face: Any,
    experiment: Any,
) -> bytes:
    old_ref = _form_ref(form)
    result = experiment._replace_exact(
        form,
        f'<CFormGuid xs.n="guid" xs.ref="{old_ref}" />'.encode("ascii"),
        f'<CFormGuid xs.n="guid" xs.ref="{new_ref}" />'.encode("ascii"),
        1,
        "clone form GUID",
    )
    if opacity is not None:
        pattern = re.compile(rb'(<f\b(?=[^>]*\bxs\.n="opacity")[^>]*>)[^<]*(</f>)')
        matches = list(pattern.finditer(result))
        _require(len(matches) == 1, "form opacity is ambiguous")
        match = matches[0]
        token = experiment._format_float32(opacity).encode("ascii")
        result = result[: match.start()] + match.group(1) + token + match.group(2) + result[match.end() :]
    if positions is not None:
        result = face._resize_float_payload(
            result, positions, experiment=experiment, label="cloned form positions"
        )
    if multiply is not None:
        pattern = re.compile(
            rb'<CFloatColor\b(?=[^>]*\bxs\.n="multiplyColor")[^>]*/>'
        )
        matches = list(pattern.finditer(result))
        _require(len(matches) == 1, "multiply color is ambiguous")
        red, green, blue, alpha = multiply
        replacement = (
            f'<CFloatColor xs.n="multiplyColor" red="{red:.2f}" '
            f'green="{green:.2f}" blue="{blue:.2f}" alpha="{alpha:.1f}" />'
        ).encode("ascii")
        result = result[: matches[0].start()] + replacement + result[matches[0].end() :]
    return result


def _replace_keyforms(
    source: bytes, match: Any, forms: Sequence[bytes]
) -> bytes:
    replacement = (
        f'<carray_list xs.n="keyforms" count="{len(forms)}">\r\n'.encode("ascii")
        + b"\r\n".join(forms)
        + b"\r\n</carray_list>"
    )
    return source[: match.start()] + replacement + source[match.end() :]


def _grid_block(
    *,
    grid_ref: str,
    grid_idx: int,
    binding_refs: Sequence[str],
    accesses: Sequence[Sequence[int]],
    form_refs: Sequence[str],
) -> bytes:
    _require(len(accesses) == len(form_refs), "grid form/access count differs")
    rows = [
        f'<KeyformGridSource xs.id="{grid_ref}" xs.idx="{grid_idx}">',
        f'<array_list xs.n="keyformsOnGrid" count="{len(form_refs)}">',
    ]
    for access, form_ref in zip(accesses, form_refs):
        _require(len(access) == len(binding_refs), "grid access dimension differs")
        rows.extend(
            [
                "<KeyformOnGrid>",
                '<KeyformGridAccessKey xs.n="accessKey">',
                f'<array_list xs.n="_keyOnParameterList" count="{len(access)}">',
            ]
        )
        for binding_ref, key_index in zip(binding_refs, access):
            rows.extend(
                [
                    "<KeyOnParameter>",
                    f'<KeyformBindingSource xs.n="binding" xs.ref="{binding_ref}" />',
                    f'<i xs.n="keyIndex">{key_index}</i>',
                    "</KeyOnParameter>",
                ]
            )
        rows.extend(
            [
                "</array_list>",
                "</KeyformGridAccessKey>",
                f'<CFormGuid xs.n="keyformGuid" xs.ref="{form_ref}" />',
                "</KeyformOnGrid>",
            ]
        )
    rows.extend(
        [
            "</array_list>",
            f'<array_list xs.n="keyformBindings" count="{len(binding_refs)}">',
            *(f'<KeyformBindingSource xs.ref="{ref}" />' for ref in binding_refs),
            "</array_list>",
            "</KeyformGridSource>",
        ]
    )
    return "\r\n".join(rows).encode("ascii")


def _binding_block(
    *,
    grid_ref: str,
    binding_ref: str,
    binding_idx: int,
    parameter_ref: str,
    keys: Sequence[float],
) -> bytes:
    rows = [
        f'<KeyformBindingSource xs.id="{binding_ref}" xs.idx="{binding_idx}">',
        f'<KeyformGridSource xs.n="_gridSource" xs.ref="{grid_ref}" />',
        f'<CParameterGuid xs.n="parameterGuid" xs.ref="{parameter_ref}" />',
        f'<array_list xs.n="keys" count="{len(keys)}">',
        *(f"<f>{float(key):.1f}</f>" for key in keys),
        "</array_list>",
        '<InterpolationType xs.n="interpolationType" v="LINEAR" />',
        '<ExtendedInterpolationType xs.n="extendedInterpolationType" v="LINEAR" />',
        '<i xs.n="insertPointCount">1</i>',
        '<f xs.n="extendedInterpolationScale">1.0</f>',
        '<s xs.n="description" />',
        "</KeyformBindingSource>",
    ]
    return "\r\n".join(rows).encode("ascii")


def _form_guid_block(
    ref: str, idx: int, source_sha: str, role: str
) -> bytes:
    return (
        f'<CFormGuid uuid="{_generated_uuid(source_sha, role)}" '
        f'note="(no debug info)" xs.id="{ref}" xs.idx="{idx}" />'
    ).encode("ascii")


def _replace_inline_grid(source: bytes, grid_ref: str) -> bytes:
    pattern = re.compile(
        rb'<KeyformGridSource\b(?=[^>]*\bxs\.n="keyformGridSource")[^>]*>'
        rb".*?</KeyformGridSource>",
        re.DOTALL,
    )
    matches = list(pattern.finditer(source))
    _require(len(matches) == 1, "inline grid is ambiguous")
    replacement = f'<KeyformGridSource xs.n="keyformGridSource" xs.ref="{grid_ref}" />'.encode("ascii")
    return source[: matches[0].start()] + replacement + source[matches[0].end() :]


def _binding_semantics(root: Any, model: Any, item: Any, experiment: Any) -> tuple[str, int, list[str], list[str]]:
    ids = experiment._id_map(root)
    source = model.source(item)
    grid_link = experiment._one_named(source, "KeyformGridSource", "keyformGridSource")
    grid_ref = str(grid_link.get("xs.ref"))
    _require(grid_ref in ids, f"{item.name}: grid is not shared")
    grid = ids[grid_ref]
    bindings = experiment._one_named(grid, "array_list", "keyformBindings")
    refs = [str(node.get("xs.ref")) for node in bindings]
    parameters = []
    for ref in refs:
        binding = ids[ref]
        parameter = experiment._one_named(binding, "CParameterGuid", "parameterGuid")
        parameters.append(str(parameter.get("xs.ref")))
    return grid_ref, int(grid.get("xs.idx", "-1")), refs, parameters


def _face_stage(
    main: bytes,
    *,
    source_sha: str,
    slots: dict[str, tuple[str, int]],
    modules: tuple[Any, ...],
) -> tuple[bytes, dict[str, Any], list[bytes]]:
    experiment, face, _hair_back, scaffold, canvas, _safe = modules
    root0 = experiment._parse_xml(main)
    parameter_refs = {
        note: str(_shared_note(root0, "CParameterGuid", note).get("xs.id"))
        for note in {
            "ParamEyeLOpen",
            "ParamEyeLSmile",
            "ParamEyeROpen",
            "ParamEyeRSmile",
            "ParamCheek",
        }
    }
    current = main
    shared: list[bytes] = []
    audit: dict[str, Any] = {"eyes": {}, "cheek": {}}

    for name, (open_id, smile_id, branch) in FACE_TARGETS.items():
        root = experiment._parse_xml(current)
        model = canvas.GeometryModel(current, TOLERANCE)
        item = _object(model, name)
        _require(item.object_type == "warp-deformer", f"{name}: type differs")
        source_block = _raw_source(current, model, item, experiment)
        keyform_match, forms = _keyforms(source_block, b"CWarpDeformerForm")
        _require(len(forms) == 3, f"{name}: expected 3 EyeOpen forms")
        form_values = scaffold._form_values(model, canvas, item)
        _require(len(form_values) == 3, f"{name}: EyeOpen geometry differs")
        original_hashes = [_sha256(form) for form in forms]
        grid_ref, grid_idx, binding_refs, observed_params = _binding_semantics(
            root, model, item, experiment
        )
        _require(
            len(binding_refs) == 1
            and observed_params == [parameter_refs[open_id]],
            f"{name}: EyeOpen binding differs",
        )
        smile_binding_ref, smile_binding_idx = slots[f"{name}:smile-binding"]
        half_forms: list[bytes] = []
        half_form_refs: list[str] = []
        full_forms: list[bytes] = []
        full_form_refs: list[str] = []
        for index in range(3):
            half_ref, half_idx = slots[f"{name}:smile-half-form:{index}"]
            if branch == "open" and index > 0:
                half_positions: Sequence[float] | None = _compress_eye_open(
                    form_values[index], 0.55 if index == 1 else 0.30, canvas
                )
            else:
                half_positions = None
            half_forms.append(
                _clone_form(
                    forms[index],
                    new_ref=half_ref,
                    opacity=_form_opacity(forms[index]),
                    positions=half_positions,
                    multiply=None,
                    face=face,
                    experiment=experiment,
                )
            )
            half_form_refs.append(half_ref)
            shared.append(
                _form_guid_block(
                    half_ref, half_idx, source_sha, f"{name}:smile-half:{index}"
                )
            )
            full_ref, full_idx = slots[f"{name}:smile-form:{index}"]
            template = forms[index] if branch == "open" else forms[0]
            full_opacity = 0.0 if branch == "open" else 1.0
            full_forms.append(
                _clone_form(
                    template,
                    new_ref=full_ref,
                    opacity=full_opacity,
                    positions=None,
                    multiply=None,
                    face=face,
                    experiment=experiment,
                )
            )
            full_form_refs.append(full_ref)
            shared.append(
                _form_guid_block(
                    full_ref, full_idx, source_sha, f"{name}:smile:{index}"
                )
            )
        combined = [*forms, *half_forms, *full_forms]
        source_after = _replace_keyforms(source_block, keyform_match, combined)
        current = experiment._replace_exact(current, source_block, source_after, 1, f"bind {name} smile")
        existing_refs = [_form_ref(form) for form in forms]
        old_grid = experiment._block_by_id(current, "KeyformGridSource", grid_ref)
        new_grid = _grid_block(
            grid_ref=grid_ref,
            grid_idx=grid_idx,
            binding_refs=[binding_refs[0], smile_binding_ref],
            accesses=[
                (0, 0),
                (1, 0),
                (2, 0),
                (0, 1),
                (1, 1),
                (2, 1),
                (0, 2),
                (1, 2),
                (2, 2),
            ],
            form_refs=[*existing_refs, *half_form_refs, *full_form_refs],
        )
        current = experiment._replace_exact(current, old_grid, new_grid, 1, f"expand {name} grid")
        shared.append(
            _binding_block(
                grid_ref=grid_ref,
                binding_ref=smile_binding_ref,
                binding_idx=smile_binding_idx,
                parameter_ref=parameter_refs[smile_id],
                keys=(0.0, 0.5, 1.0),
            )
        )
        audit["eyes"][name] = {
            "open_parameter": open_id,
            "smile_parameter": smile_id,
            "forms_before": 3,
            "forms_after": 9,
            "smile_0_forms_byte_exact": True,
            "original_form_sha256": original_hashes,
            "smile_half_policy": (
                "compressed OPEN without CLOSED overlay"
                if branch == "open"
                else "original blink visibility only"
            ),
            "smile_1_branch_opacity": full_opacity,
        }

    root = experiment._parse_xml(current)
    model = canvas.GeometryModel(current, TOLERANCE)
    cheek = _object(model, "D_JAD_FACE_FX")
    source_block = _raw_source(current, model, cheek, experiment)
    match, forms = _keyforms(source_block, b"CWarpDeformerForm")
    _require(len(forms) == 1, "D_JAD_FACE_FX is already bound")
    original = forms[0]
    original_ref = _form_ref(original)
    form0_ref, form0_idx = slots["cheek:form:0"]
    form_half_ref, form_half_idx = slots["cheek:form:half"]
    form1_ref, form1_idx = slots["cheek:form:1"]
    cheek_grid_ref, cheek_grid_idx = slots["cheek:grid"]
    cheek_binding_ref, cheek_binding_idx = slots["cheek:binding"]
    cheek_forms = [
        _clone_form(original, new_ref=form0_ref, opacity=0.0, positions=None, multiply=None, face=face, experiment=experiment),
        _clone_form(original, new_ref=form_half_ref, opacity=0.55, positions=None, multiply=None, face=face, experiment=experiment),
        _clone_form(original, new_ref=form1_ref, opacity=1.0, positions=None, multiply=(1.0, 0.82, 0.88, 1.0), face=face, experiment=experiment),
    ]
    source_after = _replace_inline_grid(source_block, cheek_grid_ref)
    match_after, _ = _keyforms(source_after, b"CWarpDeformerForm")
    source_after = _replace_keyforms(source_after, match_after, cheek_forms)
    current = experiment._replace_exact(current, source_block, source_after, 1, "bind cheek")
    shared.extend(
        [
            _grid_block(
                grid_ref=cheek_grid_ref,
                grid_idx=cheek_grid_idx,
                binding_refs=[cheek_binding_ref],
                accesses=[(0,), (1,), (2,)],
                form_refs=[form0_ref, form_half_ref, form1_ref],
            ),
            _binding_block(
                grid_ref=cheek_grid_ref,
                binding_ref=cheek_binding_ref,
                binding_idx=cheek_binding_idx,
                parameter_ref=parameter_refs["ParamCheek"],
                keys=(0.0, 0.5, 1.0),
            ),
            _form_guid_block(form0_ref, form0_idx, source_sha, "cheek:0"),
            _form_guid_block(form_half_ref, form_half_idx, source_sha, "cheek:half"),
            _form_guid_block(form1_ref, form1_idx, source_sha, "cheek:1"),
        ]
    )
    children = {
        item.name
        for item in model.objects
        if item.parent_uuid == cheek.guid_uuid
    }
    _require(children == {"JAD_FX_BLUSH_L", "JAD_FX_BLUSH_R"}, "blush children differ")
    audit["cheek"] = {
        "parameter": "ParamCheek",
        "children": sorted(children),
        "keys": [0.0, 0.5, 1.0],
        "opacities": [0.0, 0.55, 1.0],
        "full_tint_multiply": [1.0, 0.82, 0.88, 1.0],
        "geometry_preserved": True,
        "source_neutral_form_sha256": _sha256(original),
        "source_neutral_form_ref": original_ref,
        "policy": "ParamCheek=0 intentionally hides pre-existing static blush",
    }
    return current, audit, shared


def _parameter_guid_block(ref: str, idx: int, source_sha: str, parameter_id: str) -> bytes:
    return (
        f'<CParameterGuid uuid="{_generated_uuid(source_sha, "parameter:" + parameter_id)}" '
        f'note="{parameter_id}" xs.id="{ref}" xs.idx="{idx}" />'
    ).encode("ascii")


def _parameter_id_block(ref: str, idx: int, parameter_id: str) -> bytes:
    return f'<CParameterId idstr="{parameter_id}" xs.id="{ref}" xs.idx="{idx}" />'.encode("ascii")


def _parameter_source(guid_ref: str, id_ref: str, name: str, description: str) -> bytes:
    return (
        "\r\n".join(
            [
                "<CParameterSource>",
                '<i xs.n="decimalPlaces">3</i>',
                f'<CParameterGuid xs.n="guid" xs.ref="{guid_ref}" />',
                '<f xs.n="snapEpsilon">0.001</f>',
                '<f xs.n="minValue">-1.0</f>',
                '<f xs.n="maxValue">1.0</f>',
                '<f xs.n="defaultValue">0.0</f>',
                '<b xs.n="isRepeat">false</b>',
                f'<CParameterId xs.n="id" xs.ref="{id_ref}" />',
                '<Type xs.n="paramType" v="NORMAL" />',
                f'<s xs.n="name">{name}</s>',
                f'<s xs.n="description">{description}</s>',
                '<b xs.n="combined">false</b>',
                '<CParameterGroupGuid xs.n="parentGroupGuid" xs.ref="#0" />',
                "</CParameterSource>",
            ]
        )
    ).encode("ascii")


def _append_parameter_sources(main: bytes, sources: Sequence[bytes]) -> bytes:
    pattern = re.compile(
        rb'(<CParameterSourceSet\b[^>]*>\r\n<carray_list\b(?=[^>]*\bxs\.n="_sources")[^>]*\bcount=")(\d+)(">\r\n)(.*?)(\r\n</carray_list>\r\n</CParameterSourceSet>)',
        re.DOTALL,
    )
    matches = list(pattern.finditer(main))
    _require(len(matches) == 1, "parameter source set is ambiguous")
    match = matches[0]
    count = int(match.group(2))
    body = match.group(4) + b"\r\n" + b"\r\n".join(sources)
    replacement = match.group(1) + str(count + len(sources)).encode("ascii") + match.group(3) + body + match.group(5)
    return main[: match.start()] + replacement + main[match.end() :]


def _append_root_parameter_children(
    main: bytes,
    parameter_refs: Sequence[str],
    *,
    experiment: Any,
) -> bytes:
    root = experiment._parse_xml(main)
    candidates = []
    for group in root.iter("CParameterGroup"):
        if group.get("xs.id") is None:
            continue
        guid = [
            child
            for child in group
            if child.tag == "CParameterGroupGuid" and child.get("xs.n") == "guid"
        ]
        if len(guid) == 1 and guid[0].get("xs.ref") == "#0":
            candidates.append(group)
    _require(len(candidates) == 1, "root parameter group is not unique")
    group_ref = str(candidates[0].get("xs.id"))
    block = experiment._block_by_id(main, "CParameterGroup", group_ref)
    pattern = re.compile(
        rb'(<carray_list\b(?=[^>]*\bxs\.n="_childGuids")[^>]*\bcount=")(\d+)(">\r\n)(.*?)(\r\n</carray_list>)',
        re.DOTALL,
    )
    matches = list(pattern.finditer(block))
    _require(len(matches) == 1, "root parameter child list is ambiguous")
    match = matches[0]
    existing = set(
        ref.decode("ascii")
        for ref in re.findall(rb'<CParameterGuid xs\.ref="([^"]+)" />', match.group(4))
    )
    _require(not existing.intersection(parameter_refs), "custom parameter is already grouped")
    additions = b"\r\n".join(
        f'<CParameterGuid xs.ref="{ref}" />'.encode("ascii")
        for ref in parameter_refs
    )
    body = match.group(4) + b"\r\n" + additions
    replacement = (
        match.group(1)
        + str(int(match.group(2)) + len(parameter_refs)).encode("ascii")
        + match.group(3)
        + body
        + match.group(5)
    )
    changed = block[: match.start()] + replacement + block[match.end() :]
    return experiment._replace_exact(
        main, block, changed, 1, "append root parameter children"
    )


def _swap_binding_parameter(
    main: bytes,
    *,
    object_name: str,
    old_ref: str,
    new_ref: str,
    modules: tuple[Any, ...],
) -> bytes:
    experiment, _face, _hair_back, _scaffold, canvas, _safe = modules
    root = experiment._parse_xml(main)
    model = canvas.GeometryModel(main, TOLERANCE)
    item = _object(model, object_name)
    _grid, _idx, bindings, parameters = _binding_semantics(root, model, item, experiment)
    _require(len(bindings) == 1 and parameters == [old_ref], f"{object_name}: binding differs")
    block = experiment._block_by_id(main, "KeyformBindingSource", bindings[0])
    before = f'<CParameterGuid xs.n="parameterGuid" xs.ref="{old_ref}" />'.encode("ascii")
    after = f'<CParameterGuid xs.n="parameterGuid" xs.ref="{new_ref}" />'.encode("ascii")
    changed = experiment._replace_exact(block, before, after, 1, f"{object_name} parameter")
    return experiment._replace_exact(main, block, changed, 1, f"{object_name} binding")


def _replace_binding_keys(
    main: bytes,
    *,
    object_name: str,
    expected_keys: Sequence[float],
    new_keys: Sequence[float],
    modules: tuple[Any, ...],
) -> tuple[bytes, dict[str, Any]]:
    experiment, _face, _hair_back, _scaffold, canvas, _safe = modules
    root = experiment._parse_xml(main)
    model = canvas.GeometryModel(main, TOLERANCE)
    item = _object(model, object_name)
    _grid, _idx, bindings, _parameters = _binding_semantics(
        root, model, item, experiment
    )
    _require(len(bindings) == 1, f"{object_name}: binding count differs")
    block = experiment._block_by_id(
        main, "KeyformBindingSource", bindings[0]
    )
    pattern = re.compile(
        rb'<array_list\b(?=[^>]*\bxs\.n="keys")[^>]*>\r\n'
        rb'(.*?)\r\n</array_list>',
        re.DOTALL,
    )
    matches = list(pattern.finditer(block))
    _require(len(matches) == 1, f"{object_name}: binding keys are ambiguous")
    observed = tuple(
        float(token)
        for token in re.findall(rb"<f>([^<]+)</f>", matches[0].group(1))
    )
    _require(
        observed == tuple(expected_keys),
        f"{object_name}: expected binding keys {tuple(expected_keys)!r}, found {observed!r}",
    )
    replacement = (
        f'<array_list xs.n="keys" count="{len(new_keys)}">\r\n'.encode("ascii")
        + b"\r\n".join(
            f"<f>{float(key):.1f}</f>".encode("ascii") for key in new_keys
        )
        + b"\r\n</array_list>"
    )
    changed = (
        block[: matches[0].start()]
        + replacement
        + block[matches[0].end() :]
    )
    return (
        experiment._replace_exact(
            main, block, changed, 1, f"{object_name} normalized binding keys"
        ),
        {
            "before": list(observed),
            "after": [float(key) for key in new_keys],
            "full_endpoint_reachable_at_parameter_limit": True,
        },
    )


def _warp_cell_signs(
    points: Sequence[float], columns: int, rows: int
) -> list[float]:
    pairs = list(zip(points[0::2], points[1::2]))
    width = columns + 1
    _require(
        len(pairs) == width * (rows + 1),
        "warp grid point count differs",
    )
    result: list[float] = []
    for row in range(rows):
        for column in range(columns):
            p00 = pairs[row * width + column]
            p10 = pairs[row * width + column + 1]
            p01 = pairs[(row + 1) * width + column]
            p11 = pairs[(row + 1) * width + column + 1]
            result.extend(
                [
                    (p10[0] - p00[0]) * (p11[1] - p00[1])
                    - (p10[1] - p00[1]) * (p11[0] - p00[0]),
                    (p11[0] - p00[0]) * (p01[1] - p00[1])
                    - (p11[1] - p00[1]) * (p01[0] - p00[0]),
                ]
            )
    return result


def _amplify_warp_endpoints(
    main: bytes,
    *,
    object_name: str,
    gain: float,
    modules: tuple[Any, ...],
) -> tuple[bytes, dict[str, Any]]:
    experiment, face, hair_back, scaffold, canvas, safe = modules
    _require(gain > 1.0, f"{object_name}: endpoint gain must exceed one")
    geometry_main, _ = hair_back._neutral_rotation_mirror(
        main, experiment=experiment, safe=safe
    )
    geometry = canvas.GeometryModel(geometry_main, TOLERANCE)
    item = _object(geometry, object_name)
    _require(item.object_type == "warp-deformer", f"{object_name}: type differs")
    source_block = _raw_source(main, geometry, item, experiment)
    keyform_match, forms = _keyforms(source_block, b"CWarpDeformerForm")
    values = scaffold._form_values(geometry, canvas, item)
    _require(
        len(forms) == len(values) == 3,
        f"{object_name}: expected exactly three warp keyforms",
    )
    neutral_form = forms[1]
    neutral_values = values[1]
    parent_transform = geometry.transform(item.parent_ref)
    neutral_canvas = geometry.forward_many(parent_transform, neutral_values)
    transform = geometry.transform(item.guid_ref)
    neutral_signs = _warp_cell_signs(
        neutral_canvas, transform.columns, transform.rows
    )
    _require(
        all(abs(value) > TOLERANCE for value in neutral_signs),
        f"{object_name}: neutral warp has a degenerate cell",
    )
    patched_forms: list[bytes] = []
    endpoint_metrics: dict[str, Any] = {}
    for index, (form, original) in enumerate(zip(forms, values)):
        if index == 1:
            patched_forms.append(form)
            continue
        amplified = tuple(
            canvas._float32(
                neutral + gain * (posed - neutral)
            )
            for neutral, posed in zip(neutral_values, original)
        )
        original_canvas = geometry.forward_many(parent_transform, original)
        amplified_canvas = geometry.forward_many(parent_transform, amplified)
        reconstructed_error = canvas._maximum_error(
            amplified_canvas,
            geometry.forward_many(parent_transform, amplified),
        )
        _require(
            reconstructed_error < TOLERANCE,
            f"{object_name}: endpoint reconstruction exceeds tolerance",
        )
        signs = _warp_cell_signs(
            amplified_canvas, transform.columns, transform.rows
        )
        _require(
            all(a * b > 0.0 for a, b in zip(neutral_signs, signs)),
            f"{object_name}: endpoint gain folds a warp cell",
        )

        def maximum_displacement(
            first: Sequence[float], second: Sequence[float]
        ) -> float:
            return max(
                (
                    (x1 - x0) ** 2 + (y1 - y0) ** 2
                )
                ** 0.5
                for x0, y0, x1, y1 in zip(
                    first[0::2], first[1::2], second[0::2], second[1::2]
                )
            )

        endpoint_metrics[str(index)] = {
            "control_displacement_before_px": maximum_displacement(
                neutral_canvas, original_canvas
            ),
            "control_displacement_after_px": maximum_displacement(
                neutral_canvas, amplified_canvas
            ),
            "minimum_abs_cell_area2": min(abs(value) for value in signs),
        }
        patched_forms.append(
            face._resize_float_payload(
                form,
                amplified,
                experiment=experiment,
                label=f"{object_name} amplified endpoint {index}",
            )
        )
    _require(
        forms[1] == neutral_form == patched_forms[1],
        f"{object_name}: neutral keyform changed",
    )
    source_after = _replace_keyforms(
        source_block, keyform_match, patched_forms
    )
    return (
        experiment._replace_exact(
            main,
            source_block,
            source_after,
            1,
            f"{object_name} amplify endpoint forms",
        ),
        {
            "endpoint_gain": gain,
            "neutral_form_sha256": _sha256(neutral_form),
            "neutral_form_preserved_byte_exact": True,
            "endpoint_metrics": endpoint_metrics,
            "warp_cell_winding_preserved": True,
        },
    )


def _triangle_signs(points: Sequence[float], indices: Sequence[int]) -> list[float]:
    pairs = list(zip(points[0::2], points[1::2]))
    result = []
    for offset in range(0, len(indices), 3):
        a, b, c = (pairs[indices[offset + n]] for n in range(3))
        result.append((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))
    return result


def _secondary_stage(
    main: bytes,
    *,
    source_sha: str,
    slots: dict[str, tuple[str, int]],
    modules: tuple[Any, ...],
) -> tuple[bytes, dict[str, Any], list[bytes]]:
    experiment, face, hair_back, scaffold, canvas, safe = modules
    root0 = experiment._parse_xml(main)
    existing_notes = {node.get("note") for node in root0.find("shared") if node.tag == "CParameterGuid"}
    _require(not set(SECONDARY_PARAMETERS).intersection(existing_notes), "custom secondary parameter already exists")
    shared: list[bytes] = []
    parameter_sources: list[bytes] = []
    parameter_refs: dict[str, str] = {}
    for parameter_id, (name, description) in SECONDARY_PARAMETERS.items():
        guid_ref, guid_idx = slots[f"parameter:{parameter_id}:guid"]
        id_ref, id_idx = slots[f"parameter:{parameter_id}:id"]
        parameter_refs[parameter_id] = guid_ref
        shared.extend(
            [
                _parameter_guid_block(guid_ref, guid_idx, source_sha, parameter_id),
                _parameter_id_block(id_ref, id_idx, parameter_id),
            ]
        )
        parameter_sources.append(_parameter_source(guid_ref, id_ref, name, description))
    current = _append_parameter_sources(main, parameter_sources)
    current = _append_root_parameter_children(
        current,
        list(parameter_refs.values()),
        experiment=experiment,
    )
    original_parameter_refs = {
        note: str(_shared_note(root0, "CParameterGuid", note).get("xs.id"))
        for note in {value[0] for value in SECONDARY_REBIND.values()}
    }
    warp_tuning: dict[str, Any] = {}
    for object_name, (old_id, new_id) in SECONDARY_REBIND.items():
        current = _swap_binding_parameter(
            current,
            object_name=object_name,
            old_ref=original_parameter_refs[old_id],
            new_ref=parameter_refs[new_id],
            modules=modules,
        )
        expected_keys, gain = SECONDARY_WARP_TUNING[object_name]
        current, key_audit = _replace_binding_keys(
            current,
            object_name=object_name,
            expected_keys=expected_keys,
            new_keys=SECONDARY_OUTPUT_KEYS,
            modules=modules,
        )
        current, geometry_audit = _amplify_warp_endpoints(
            current,
            object_name=object_name,
            gain=gain,
            modules=modules,
        )
        warp_tuning[object_name] = {
            "binding_keys": key_audit,
            "geometry": geometry_audit,
        }

    geometry_main, _ = hair_back._neutral_rotation_mirror(current, experiment=experiment, safe=safe)
    geometry = canvas.GeometryModel(geometry_main, TOLERANCE)
    ahoge = _object(geometry, "JAD_HAIR_AHOGE")
    _require(ahoge.object_type == "art-mesh", "ahoge type differs")
    source_block = _raw_source(current, canvas.GeometryModel(current, TOLERANCE), _object(canvas.GeometryModel(current, TOLERANCE), "JAD_HAIR_AHOGE"), experiment)
    match, forms = _keyforms(source_block, b"CArtMeshForm")
    _require(len(forms) == 1, "ahoge is already directly bound")
    neutral_form = forms[0]
    neutral_local = scaffold._form_values(geometry, canvas, ahoge)[0]
    neutral_canvas = geometry.original_canvas(ahoge)
    parent_transform = geometry.transform(ahoge.parent_ref)
    ys = neutral_canvas[1::2]
    min_y, max_y = min(ys), max(ys)
    _require(max_y - min_y > 0.0, "ahoge geometry is degenerate")
    poses: list[tuple[float, ...]] = []
    reconstruction_errors: list[float] = []
    for key in (-1.0, 0.0, 1.0):
        if key == 0.0:
            poses.append(tuple(neutral_local))
            reconstruction_errors.append(0.0)
            continue
        target: list[float] = []
        for x, y in zip(neutral_canvas[0::2], neutral_canvas[1::2]):
            weight = ((max_y - y) / (max_y - min_y)) ** 1.6
            target.extend((x + AHOGE_SWING_PX * key * weight, y + 2.0 * abs(key) * weight))
        local = tuple(canvas._float32(v) for v in geometry.inverse_many(parent_transform, target))
        reconstructed = geometry.forward_many(parent_transform, local)
        error = max(abs(float(a) - float(b)) for a, b in zip(target, reconstructed))
        _require(error < TOLERANCE, "ahoge pose reconstruction exceeds tolerance")
        poses.append(local)
        reconstruction_errors.append(error)
    indices_node = experiment._one_named(geometry.source(ahoge), "int-array", "indices")
    indices = [int(token) for token in (indices_node.text or "").split()]
    neutral_signs = _triangle_signs(neutral_local, indices)
    for pose in poses:
        signs = _triangle_signs(pose, indices)
        _require(all(a * b > 0.0 for a, b in zip(neutral_signs, signs)), "ahoge triangle flipped")
    grid_ref, grid_idx = slots["ahoge:grid"]
    binding_ref, binding_idx = slots["ahoge:binding"]
    left_ref, left_idx = slots["ahoge:form:left"]
    right_ref, right_idx = slots["ahoge:form:right"]
    neutral_ref = _form_ref(neutral_form)
    new_forms = [
        _clone_form(neutral_form, new_ref=left_ref, opacity=None, positions=poses[0], multiply=None, face=face, experiment=experiment),
        neutral_form,
        _clone_form(neutral_form, new_ref=right_ref, opacity=None, positions=poses[2], multiply=None, face=face, experiment=experiment),
    ]
    source_after = _replace_inline_grid(source_block, grid_ref)
    match_after, _ = _keyforms(source_after, b"CArtMeshForm")
    source_after = _replace_keyforms(source_after, match_after, new_forms)
    current = experiment._replace_exact(current, source_block, source_after, 1, "bind ahoge")
    shared.extend(
        [
            _grid_block(grid_ref=grid_ref, grid_idx=grid_idx, binding_refs=[binding_ref], accesses=[(0,), (1,), (2,)], form_refs=[left_ref, neutral_ref, right_ref]),
            _binding_block(grid_ref=grid_ref, binding_ref=binding_ref, binding_idx=binding_idx, parameter_ref=parameter_refs["ParamAhogeSwing"], keys=(-1.0, 0.0, 1.0)),
            _form_guid_block(left_ref, left_idx, source_sha, "ahoge:left"),
            _form_guid_block(right_ref, right_idx, source_sha, "ahoge:right"),
        ]
    )
    return current, {
        "parameters_added": sorted(SECONDARY_PARAMETERS),
        "parameter_hierarchy": {
            "group": "Root Parameter Group",
            "children_added": list(parameter_refs),
            "all_custom_parameters_grouped": True,
        },
        "rebound": {name: {"from": old, "to": new} for name, (old, new) in SECONDARY_REBIND.items()},
        "warp_tuning": warp_tuning,
        "ahoge": {
            "parameter": "ParamAhogeSwing",
            "tip_swing_px": AHOGE_SWING_PX,
            "neutral_form_byte_exact": True,
            "reconstruction_errors_px": reconstruction_errors,
            "triangle_winding_preserved": True,
        },
    }, shared


def _roles(stages: set[str]) -> list[str]:
    roles: list[str] = []
    if "face" in stages:
        for name in FACE_TARGETS:
            roles.append(f"{name}:smile-binding")
            roles.extend(f"{name}:smile-half-form:{index}" for index in range(3))
            roles.extend(f"{name}:smile-form:{index}" for index in range(3))
        roles.extend(["cheek:grid", "cheek:binding", "cheek:form:0", "cheek:form:half", "cheek:form:1"])
    if "secondary" in stages:
        for parameter_id in SECONDARY_PARAMETERS:
            roles.extend([f"parameter:{parameter_id}:guid", f"parameter:{parameter_id}:id"])
        roles.extend(["ahoge:grid", "ahoge:binding", "ahoge:form:left", "ahoge:form:right"])
    return roles


def _parameter_hierarchy_audit(root: Any, experiment: Any) -> dict[str, Any]:
    source_refs = []
    for source in root.iter("CParameterSource"):
        guid = experiment._one_named(source, "CParameterGuid", "guid")
        source_refs.append(str(guid.get("xs.ref")))
    groups = []
    for group in root.iter("CParameterGroup"):
        if group.get("xs.id") is None:
            continue
        guid_nodes = [
            child
            for child in group
            if child.tag == "CParameterGroupGuid" and child.get("xs.n") == "guid"
        ]
        if len(guid_nodes) == 1 and guid_nodes[0].get("xs.ref") == "#0":
            groups.append(group)
    _require(len(groups) == 1, "root parameter group validation is ambiguous")
    children = experiment._one_named(groups[0], "carray_list", "_childGuids")
    child_refs = [str(node.get("xs.ref")) for node in children]
    _require(len(source_refs) == len(set(source_refs)), "parameter source GUID is duplicated")
    _require(len(child_refs) == len(set(child_refs)), "parameter hierarchy child is duplicated")
    _require(
        child_refs == source_refs,
        "parameter hierarchy order/membership differs from parameter sources",
    )
    return {
        "parameter_sources": len(source_refs),
        "root_children": len(child_refs),
        "membership_and_order_exact": True,
        "duplicate_children": 0,
        "predicted_cubism_recovery_count": 0,
    }


def _plan(source_data: bytes, stages: set[str], modules: tuple[Any, ...]) -> tuple[bytes, dict[str, Any]]:
    experiment, _face, _hair_back, _scaffold, canvas, safe = modules
    archive_before, _entry, _location, _zip, main_before = safe._validate_surgical_layout(source_data)
    root_before = experiment._parse_xml(main_before)
    model_before = canvas.GeometryModel(main_before, TOLERANCE)
    identities_before = sorted((i.object_type, i.name, i.guid_uuid, i.guid_ref, i.source_ref, i.parent_ref) for i in model_before.objects)
    slots = _allocate(root_before, _roles(stages))
    current = main_before
    audit: dict[str, Any] = {"stages": sorted(stages)}
    shared: list[bytes] = []
    if "face" in stages:
        current, audit["face"], additions = _face_stage(current, source_sha=_sha256(source_data), slots=slots, modules=modules)
        shared.extend(additions)
    if "secondary" in stages:
        current, audit["secondary"], additions = _secondary_stage(current, source_sha=_sha256(source_data), slots=slots, modules=modules)
        shared.extend(additions)
    current = experiment._append_shared_blocks(current, shared)
    root_after = experiment._parse_xml(current)
    model_after = canvas.GeometryModel(current, TOLERANCE)
    identities_after = sorted((i.object_type, i.name, i.guid_uuid, i.guid_ref, i.source_ref, i.parent_ref) for i in model_after.objects)
    _require(identities_after == identities_before, "object identity/hierarchy changed")
    indices = [int(node.get("xs.idx", "-1")) for node in root_after.find("shared")]
    _require(len(indices) == len(set(indices)), "output xs.idx collision")
    if "secondary" in stages:
        audit["secondary"]["parameter_hierarchy_validation"] = (
            _parameter_hierarchy_audit(root_after, experiment)
        )
    output_data = safe._replace_main_xml(source_data, current)
    archive_after, _e2, _l2, _z2, decoded_after = safe._validate_surgical_layout(output_data)
    _require(decoded_after == current, "output main.xml differs")
    preservation = safe._compare_entry_preservation(source_data, archive_before, output_data, archive_after, main_may_change=True)
    _require(preservation.get("all_non_main_entries_byte_identical") is True, "non-main archive entry changed")
    audit.update(
        {
            "schema": "jade.cmo3.secondary-professional.v1",
            "status": "ok",
            "source_sha256": _sha256(source_data),
            "output_sha256": _sha256(output_data),
            "source_bytes": len(source_data),
            "output_bytes": len(output_data),
            "objects_preserved": True,
            "shared_definitions_added": len(shared),
            "archive": preservation,
            "cubism_5_2_03_load_save_required": True,
        }
    )
    return output_data, audit


def _write_exclusive(path: Path, payload: bytes) -> None:
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
    parser.add_argument("--stages", choices=("face", "secondary", "all"), default="all")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    source = args.source.resolve(strict=True)
    output = args.output.resolve(strict=False)
    _require(source.suffix.lower() == ".cmo3" and output.suffix.lower() == ".cmo3", "source/output must be CMO3")
    _require(source != output, "source and output must differ")
    _require(not output.exists(), "output exists; refusing overwrite")
    _require(output.parent.is_dir(), "output directory does not exist")
    stages = {"face", "secondary"} if args.stages == "all" else {args.stages}
    source_data = source.read_bytes()
    output_data, audit = _plan(source_data, stages, _load_modules())
    audit.update({"source": str(source), "output": str(output), "dry_run": bool(args.dry_run), "output_written": False})
    _require(source.read_bytes() == source_data, "source changed during planning")
    if args.dry_run:
        audit["verdict"] = "PASS_DRY_RUN__NO_FILE_WRITTEN"
        print(json.dumps(audit, ensure_ascii=False, sort_keys=True))
        return 0
    audit_path = output.with_suffix(".audit.json")
    _require(not audit_path.exists(), "audit exists; refusing overwrite")
    try:
        _write_exclusive(output, output_data)
        audit["output_written"] = True
        audit["verdict"] = "PASS_PRE_CUBISM__LOAD_SAVE_5_2_03_REQUIRED"
        payload = (json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        _write_exclusive(audit_path, payload)
    except Exception:
        output.unlink(missing_ok=True)
        audit_path.unlink(missing_ok=True)
        raise
    print(json.dumps(audit, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SecondaryProfessionalError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
