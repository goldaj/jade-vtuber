#!/usr/bin/env python3
"""Rebuild Jade's ear motion around the inner skull root.

The r04/r11 ear poses weighted deformation by vertical height.  That makes the
upper *inner* control points move strongly even though the visible outer tip is
the part that should lead the motion.  This corrective transaction instead
uses lateral distance from the skull:

* the inner 28 percent of each ear cage is fixed;
* a smooth transition bends the middle of the cage;
* the outermost lateral edge receives the full emotional and swing motion.

Both ears are generated as mirrored semantics.  The neutral centre form is
preserved byte-for-byte, all other forms are rebuilt from that centre, and no
artwork, hierarchy, binding, opacity, eye or hair source is changed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Sequence

import cmo3_ears_hair_professional_r04 as ears_r04


TOLERANCE = 0.001
ROOT_FRACTION = 0.28
WEIGHT_EXPONENT = 1.0
CANVAS_WIDTH = 3840.0
CANVAS_HEIGHT = 4160.0

# r11 already contains the approved large emotional vectors.  We reuse each
# vector, but transfer its full strength from the old upper/inner reference
# point to the true exterior edge.  Surprise receives the one approved change:
# a stronger vertical component so that the outer tip becomes more upright.
POSE_LOCAL_COMPONENT_SCALES = {
    -1.0: (1.0, 1.0),
    -0.5: (1.0, 1.0),
    0.0: (0.0, 0.0),
    1.0: (1.0, 1.08),
}

TARGETS = {
    "D_JAD_EAR_L_MASTER": {
        "physics": "ParamEarSwingL",
        "pose": "ParamEarPoseL",
        "side": 1.0,
        "outer_edge": "maximum_x",
    },
    "D_JAD_EAR_R_MASTER": {
        "physics": "ParamEarSwingR",
        "pose": "ParamEarPoseR",
        "side": -1.0,
        "outer_edge": "minimum_x",
    },
}


class EarLateralMotionError(RuntimeError):
    """Raised when the expected ear contract or geometric safety fails."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EarLateralMotionError(message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _maximum_displacement(
    first: Sequence[float], second: Sequence[float]
) -> float:
    return max(
        math.hypot(x1 - x0, y1 - y0)
        for x0, y0, x1, y1 in zip(
            first[0::2], first[1::2], second[0::2], second[1::2]
        )
    )


def _grid_mapping(
    root: Any,
    grid_ref: str,
    binding_refs: Sequence[str],
    experiment: Any,
) -> dict[tuple[int, ...], str]:
    ids = experiment._id_map(root)
    grid = ids.get(grid_ref)
    _require(grid is not None, f"grid {grid_ref} is unresolved")
    entries = experiment._one_named(grid, "array_list", "keyformsOnGrid")
    result: dict[tuple[int, ...], str] = {}
    for entry in entries:
        access_key = experiment._one_named(
            entry, "KeyformGridAccessKey", "accessKey"
        )
        keys = experiment._one_named(
            access_key, "array_list", "_keyOnParameterList"
        )
        by_binding: dict[str, int] = {}
        for key in keys:
            binding = experiment._one_named(
                key, "KeyformBindingSource", "binding"
            )
            index = experiment._one_named(key, "i", "keyIndex")
            by_binding[str(binding.get("xs.ref"))] = int(index.text or "-1")
        _require(
            set(by_binding) == set(binding_refs),
            "grid access binding set differs",
        )
        form = experiment._one_named(entry, "CFormGuid", "keyformGuid")
        access = tuple(by_binding[ref] for ref in binding_refs)
        _require(access not in result, f"duplicate grid access {access}")
        result[access] = str(form.get("xs.ref"))
    return result


def _smooth_lateral_weights(
    neutral_canvas: Sequence[float], side: float
) -> tuple[tuple[float, ...], dict[str, Any]]:
    xs = tuple(neutral_canvas[0::2])
    min_x, max_x = min(xs), max(xs)
    span = max_x - min_x
    _require(span > TOLERANCE, "ear neutral width is degenerate")
    inner_x = min_x if side > 0.0 else max_x
    outer_x = max_x if side > 0.0 else min_x
    weights: list[float] = []
    progresses: list[float] = []
    for x in xs:
        progress = side * (x - inner_x) / span
        progress = max(0.0, min(1.0, progress))
        progresses.append(progress)
        transition = max(
            0.0,
            min(1.0, (progress - ROOT_FRACTION) / (1.0 - ROOT_FRACTION)),
        )
        # A near-linear easing keeps adjacent columns ordered even for the
        # large approved r11 vectors.  Cubism's warp interpolation supplies the
        # visual smoothness between control columns.
        weights.append(transition**WEIGHT_EXPONENT)
    _require(min(weights) == 0.0, "inner root has no zero-weight controls")
    _require(max(weights) > 0.999999, "outer edge does not reach full weight")
    _require(
        all(
            a <= b + 1e-12
            for a, b in zip(
                [w for _p, w in sorted(zip(progresses, weights))][:-1],
                [w for _p, w in sorted(zip(progresses, weights))][1:],
            )
        ),
        "lateral weight is not monotonic",
    )
    return tuple(weights), {
        "inner_x": inner_x,
        "outer_x": outer_x,
        "lateral_span_px": span,
        "fixed_root_fraction": ROOT_FRACTION,
        "transition_exponent": WEIGHT_EXPONENT,
        "fixed_control_points": sum(
            1 for progress in progresses if progress <= ROOT_FRACTION + 1e-12
        ),
        "transition_control_points": sum(
            1 for weight in weights if 0.0 < weight < 1.0
        ),
        "full_weight_control_points": sum(
            1 for weight in weights if weight > 0.999999
        ),
        "weight_minimum": min(weights),
        "weight_maximum": max(weights),
    }


def _reference_tip_delta(
    source_local: Sequence[float],
    centre_local: Sequence[float],
    source_canvas: Sequence[float],
    centre_canvas: Sequence[float],
) -> tuple[int, tuple[float, float], tuple[float, float]]:
    point_count = len(source_local) // 2
    reference_index = max(
        range(point_count),
        key=lambda index: math.hypot(
            source_canvas[index * 2] - centre_canvas[index * 2],
            source_canvas[index * 2 + 1] - centre_canvas[index * 2 + 1],
        ),
    )
    offset = reference_index * 2
    return (
        reference_index,
        (
            source_local[offset] - centre_local[offset],
            source_local[offset + 1] - centre_local[offset + 1],
        ),
        (
            source_canvas[offset] - centre_canvas[offset],
            source_canvas[offset + 1] - centre_canvas[offset + 1],
        ),
    )


def _weighted_local_form(
    centre_local: Sequence[float],
    weights: Sequence[float],
    *,
    tip_delta_local: tuple[float, float],
    float32: Any,
) -> tuple[float, ...]:
    result: list[float] = []
    dx, dy = tip_delta_local
    for point_index, (x, y) in enumerate(
        zip(centre_local[0::2], centre_local[1::2])
    ):
        weight = weights[point_index]
        result.extend(
            (float32(x + dx * weight), float32(y + dy * weight))
        )
    return tuple(result)


def _patch_ear(
    main: bytes,
    *,
    name: str,
    spec: dict[str, Any],
    modules: tuple[Any, ...],
) -> tuple[bytes, dict[str, Any]]:
    experiment, face, hair_back, scaffold, canvas, safe, secondary = modules
    root = experiment._parse_xml(main)
    geometry_xml, _neutralized = hair_back._neutral_rotation_mirror(
        main, experiment=experiment, safe=safe
    )
    geometry = canvas.GeometryModel(geometry_xml, TOLERANCE)
    item = ears_r04._object(geometry, name)
    _require(item.object_type == "warp-deformer", f"{name}: type differs")

    grid_ref, _grid_idx, binding_refs, parameter_refs = (
        secondary._binding_semantics(root, geometry, item, experiment)
    )
    expected = {
        str(
            secondary._shared_note(root, "CParameterGuid", spec[axis]).get(
                "xs.id"
            )
        ): axis
        for axis in ("physics", "pose")
    }
    _require(
        set(parameter_refs) == set(expected),
        f"{name}: binding parameters differ",
    )
    axis_for_binding = [expected[ref] for ref in parameter_refs]
    physics_dimension = axis_for_binding.index("physics")
    pose_dimension = axis_for_binding.index("pose")

    keys_by_binding = {
        ref: ears_r04._binding_keys(root, ref, experiment)
        for ref in binding_refs
    }
    physics_keys = keys_by_binding[binding_refs[physics_dimension]]
    pose_keys = keys_by_binding[binding_refs[pose_dimension]]
    _require(physics_keys == (-1.0, 0.0, 1.0), f"{name}: physics keys differ")
    _require(len(pose_keys) == 4, f"{name}: pose key count differs")
    physics_zero_index = physics_keys.index(0.0)
    pose_zero_index = pose_keys.index(0.0)

    source_block = secondary._raw_source(main, geometry, item, experiment)
    keyform_match, forms = secondary._keyforms(
        source_block, b"CWarpDeformerForm"
    )
    form_values = scaffold._form_values(geometry, canvas, item)
    _require(len(forms) == len(form_values) == 12, f"{name}: expected 12 forms")
    forms_by_ref = {
        secondary._form_ref(form): (form, values)
        for form, values in zip(forms, form_values)
    }
    _require(len(forms_by_ref) == len(forms), f"{name}: duplicate form GUID")
    access_to_ref = _grid_mapping(root, grid_ref, binding_refs, experiment)
    _require(len(access_to_ref) == 12, f"{name}: grid must contain 12 accesses")
    _require(
        set(access_to_ref.values()) == set(forms_by_ref),
        f"{name}: grid/form GUID set differs",
    )

    parent_transform = geometry.transform(item.parent_ref)
    transform = geometry.transform(item.guid_ref)

    neutral_access = [0] * len(binding_refs)
    neutral_access[physics_dimension] = physics_zero_index
    neutral_access[pose_dimension] = pose_zero_index
    neutral_ref = access_to_ref[tuple(neutral_access)]
    _neutral_form, neutral_local = forms_by_ref[neutral_ref]
    neutral_canvas = geometry.forward_many(parent_transform, neutral_local)
    neutral_signs = secondary._warp_cell_signs(
        neutral_canvas, transform.columns, transform.rows
    )
    _require(
        all(abs(value) > TOLERANCE for value in neutral_signs),
        f"{name}: neutral form is degenerate",
    )

    weights, weight_metrics = _smooth_lateral_weights(
        neutral_canvas, float(spec["side"])
    )

    # Extract the full r11 pose vectors from the points that previously moved
    # the most, then transfer those vectors to the actual lateral exterior.
    pose_tip_deltas_local: dict[float, tuple[float, float]] = {}
    pose_source_metrics: dict[str, Any] = {}
    for pose_index, pose_key in enumerate(pose_keys):
        access = [0] * len(binding_refs)
        access[physics_dimension] = physics_zero_index
        access[pose_dimension] = pose_index
        ref = access_to_ref[tuple(access)]
        _form, source_local = forms_by_ref[ref]
        source_canvas = geometry.forward_many(parent_transform, source_local)
        nearest = min(
            POSE_LOCAL_COMPONENT_SCALES,
            key=lambda key: abs(key - pose_key),
        )
        _require(abs(nearest - pose_key) <= 0.051, f"unsupported pose key {pose_key}")
        reference_index, source_local_delta, source_canvas_delta = (
            _reference_tip_delta(
                source_local,
                neutral_local,
                source_canvas,
                neutral_canvas,
            )
        )
        scale_x, scale_y = POSE_LOCAL_COMPONENT_SCALES[nearest]
        pose_tip_deltas_local[pose_key] = (
            source_local_delta[0] * scale_x,
            source_local_delta[1] * scale_y,
        )
        pose_source_metrics[str(pose_key)] = {
            "old_vertical_reference_control_index": reference_index,
            "old_reference_local_delta": {
                "x": source_local_delta[0],
                "y": source_local_delta[1],
            },
            "old_reference_canvas_delta_px": {
                "x": source_canvas_delta[0],
                "y": source_canvas_delta[1],
            },
            "new_local_component_scale": {"x": scale_x, "y": scale_y},
        }

    # Reuse the already-approved r11 swing amplitude only at the exterior edge.
    swing_tip_deltas_local: dict[float, tuple[float, float]] = {}
    source_swing_metrics: dict[str, Any] = {}
    for physics_index, physics_key in enumerate(physics_keys):
        access = [0] * len(binding_refs)
        access[physics_dimension] = physics_index
        access[pose_dimension] = pose_zero_index
        ref = access_to_ref[tuple(access)]
        _form, local = forms_by_ref[ref]
        physics_canvas = geometry.forward_many(parent_transform, local)
        reference_index, local_delta, canvas_delta = _reference_tip_delta(
            local,
            neutral_local,
            physics_canvas,
            neutral_canvas,
        )
        swing_tip_deltas_local[physics_key] = local_delta
        source_swing_metrics[str(physics_key)] = {
            "old_reference_control_index": reference_index,
            "old_reference_local_delta": {"x": local_delta[0], "y": local_delta[1]},
            "old_reference_canvas_delta_px": {
                "x": canvas_delta[0],
                "y": canvas_delta[1],
            },
            "old_maximum_displacement_px": _maximum_displacement(
                neutral_canvas, physics_canvas
            ),
        }

    replacements: dict[str, tuple[float, ...]] = {}
    pose_metrics: dict[str, Any] = {}
    all_x: list[float] = []
    all_y: list[float] = []
    maximum_fixed_root_displacement = 0.0
    fixed_indices = [index for index, weight in enumerate(weights) if weight == 0.0]
    outer_indices = [index for index, weight in enumerate(weights) if weight > 0.999999]
    _require(bool(outer_indices), f"{name}: no full-weight exterior controls")

    for pose_index, pose_key in enumerate(pose_keys):
        centre_local = _weighted_local_form(
            neutral_local,
            weights,
            tip_delta_local=pose_tip_deltas_local[pose_key],
            float32=canvas._float32,
        )
        centre_canvas = geometry.forward_many(parent_transform, centre_local)
        centre_displacement = _maximum_displacement(neutral_canvas, centre_canvas)
        outer_vectors = [
            (
                centre_canvas[index * 2] - neutral_canvas[index * 2],
                centre_canvas[index * 2 + 1] - neutral_canvas[index * 2 + 1],
            )
            for index in outer_indices
        ]
        pose_forms: dict[str, Any] = {}
        for physics_index, physics_key in enumerate(physics_keys):
            access = [0] * len(binding_refs)
            access[physics_dimension] = physics_index
            access[pose_dimension] = pose_index
            form_ref = access_to_ref[tuple(access)]
            target_local = _weighted_local_form(
                centre_local,
                weights,
                tip_delta_local=swing_tip_deltas_local[physics_key],
                float32=canvas._float32,
            )
            reconstructed = geometry.forward_many(parent_transform, target_local)
            signs = secondary._warp_cell_signs(
                reconstructed, transform.columns, transform.rows
            )
            _require(
                all(a * b > 0.0 for a, b in zip(neutral_signs, signs)),
                f"{name}: pose {pose_key}, swing {physics_key} folds a cell",
            )
            for point_index in fixed_indices:
                offset = point_index * 2
                maximum_fixed_root_displacement = max(
                    maximum_fixed_root_displacement,
                    math.hypot(
                        reconstructed[offset] - neutral_canvas[offset],
                        reconstructed[offset + 1] - neutral_canvas[offset + 1],
                    ),
                )
            all_x.extend(reconstructed[0::2])
            all_y.extend(reconstructed[1::2])
            if form_ref != neutral_ref:
                replacements[form_ref] = target_local
            pose_forms[str(physics_key)] = {
                "maximum_displacement_from_neutral_px": _maximum_displacement(
                    neutral_canvas, reconstructed
                ),
                "maximum_swing_displacement_from_pose_centre_px": (
                    _maximum_displacement(centre_canvas, reconstructed)
                ),
                "minimum_cell_signed_area_magnitude": min(abs(v) for v in signs),
            }
        nearest = min(
            POSE_LOCAL_COMPONENT_SCALES,
            key=lambda key: abs(key - pose_key),
        )
        pose_metrics[str(pose_key)] = {
            "semantic": {
                -1.0: "sad_outer_tip_down_and_out",
                -0.5: "angry_outer_tip_pinned_back",
                0.0: "neutral",
                1.0: "surprise_outer_tip_strongly_upright",
            }[nearest],
            "source_reference": pose_source_metrics[str(pose_key)],
            "result_outer_edge_delta_canvas_px": {
                "mean_x": sum(value[0] for value in outer_vectors) / len(outer_vectors),
                "mean_y": sum(value[1] for value in outer_vectors) / len(outer_vectors),
                "maximum_magnitude": max(
                    math.hypot(value[0], value[1]) for value in outer_vectors
                ),
            },
            "centre_maximum_displacement_px": centre_displacement,
            "forms": pose_forms,
        }

    _require(len(replacements) == 11, f"{name}: expected eleven rebuilt forms")
    _require(
        maximum_fixed_root_displacement < TOLERANCE,
        f"{name}: fixed inner root moved",
    )
    _require(min(all_x) >= 0.0, f"{name}: cage exceeds canvas left")
    _require(max(all_x) <= CANVAS_WIDTH, f"{name}: cage exceeds canvas right")
    _require(min(all_y) >= 0.0, f"{name}: cage exceeds canvas top")
    _require(max(all_y) <= CANVAS_HEIGHT, f"{name}: cage exceeds canvas bottom")

    patched_forms: list[bytes] = []
    for form in forms:
        ref = secondary._form_ref(form)
        if ref not in replacements:
            patched_forms.append(form)
            continue
        patched_forms.append(
            face._resize_float_payload(
                form,
                replacements[ref],
                experiment=experiment,
                label=f"{name} lateral-root ear positions",
            )
        )
    source_after = secondary._replace_keyforms(
        source_block, keyform_match, patched_forms
    )
    current = experiment._replace_exact(
        main, source_block, source_after, 1, f"rebuild lateral motion {name}"
    )
    return current, {
        "physics_parameter": spec["physics"],
        "pose_parameter": spec["pose"],
        "physics_keys": list(physics_keys),
        "pose_keys": list(pose_keys),
        "outer_edge": spec["outer_edge"],
        "weight_axis": "lateral_distance_from_skull",
        "weighting": weight_metrics,
        "forms_total": len(forms),
        "forms_rebuilt": len(replacements),
        "neutral_centre_form_ref": neutral_ref,
        "neutral_centre_preserved_byte_exact": True,
        "fixed_root_maximum_displacement_px": maximum_fixed_root_displacement,
        "source_r11_swing": source_swing_metrics,
        "local_space_rebuild_no_parent_inverse": True,
        "combined_cage_bbox": {
            "min_x": min(all_x),
            "max_x": max(all_x),
            "min_y": min(all_y),
            "max_y": max(all_y),
        },
        "poses": pose_metrics,
    }


def build(source: Path, output: Path, audit_path: Path) -> dict[str, Any]:
    modules = ears_r04._load_modules()
    _experiment, _face, _hair, _scaffold, _canvas, safe, _secondary = modules
    source_data = source.read_bytes()
    archive, _entry, _location, _zip, main_before = (
        safe._validate_surgical_layout(source_data)
    )
    current = main_before
    target_audit: dict[str, Any] = {}
    for name, spec in TARGETS.items():
        current, target_audit[name] = _patch_ear(
            current, name=name, spec=spec, modules=modules
        )

    output_data = safe._replace_main_xml(source_data, current)
    archive_after, _e2, _l2, _z2, decoded = safe._validate_surgical_layout(
        output_data
    )
    _require(decoded == current, "encoded main.xml differs")
    preservation = safe._compare_entry_preservation(
        source_data,
        archive,
        output_data,
        archive_after,
        main_may_change=True,
    )
    _require(
        preservation.get("all_non_main_entries_byte_identical") is True,
        "non-main CAFF member changed",
    )

    audit = {
        "schema": "jade.ear-lateral-motion-professional.v1",
        "status": "candidate",
        "source": str(source),
        "source_sha256": _sha256(source_data),
        "output": str(output),
        "output_sha256": _sha256(output_data),
        "approved_motion_sketch": "reports/Jade_ears_expected_motion_sketch.svg",
        "policy": {
            "weight_axis": "lateral_distance_from_skull_not_vertical_height",
            "fixed_inner_root_fraction": ROOT_FRACTION,
            "outer_tip_full_weight": True,
            "surprise_more_upright": True,
            "neutral_centre_preserved": True,
            "r11_outer_swing_amplitude_retained": True,
            "head_eye_hair_artwork_bindings_opacities_unchanged": True,
        },
        "targets": target_audit,
        "archive": preservation,
        "cubism_5_2_03_load_save_required": True,
    }

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    descriptor = os.open(output, flags, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(output_data)
    descriptor = os.open(audit_path, flags, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(audit, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return audit


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("audit", type=Path)
    args = parser.parse_args(argv)
    _require(args.source.resolve() != args.output.resolve(), "source/output must differ")
    _require(not args.output.exists(), "output exists; refusing overwrite")
    _require(not args.audit.exists(), "audit exists; refusing overwrite")
    print(json.dumps(build(args.source, args.output, args.audit), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
