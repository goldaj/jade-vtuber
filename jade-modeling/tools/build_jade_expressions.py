#!/usr/bin/env python3
"""Create Jade's VTube Studio expression files in an exported Cubism model.

The target is either the runtime directory containing ``Jade.model3.json`` or
that file itself.  Seven stable Cubism Expression v3 files are created under
``expressions/`` and registered in ``FileReferences.Expressions``.  Existing
files are accepted only when byte-identical; name/path conflicts fail instead
of being overwritten.  The model3 update is an atomic same-directory replace.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


MODEL_FILENAME = "Jade.model3.json"
PHYSICS_FILENAME = "Jade.physics3.json"
EXPRESSION_DIR = "expressions"
EXPECTED_PARAMETERS = {
    "ParamEyeLOpen",
    "ParamEyeROpen",
    "ParamEyeLSmile",
    "ParamEyeRSmile",
    "ParamMouthForm",
    "ParamMouthOpenY",
    "ParamCheek",
    "ParamBrowLX",
    "ParamBrowRX",
    "ParamBrowLY",
    "ParamBrowRY",
    "ParamBrowLAngle",
    "ParamBrowRAngle",
    "ParamBrowLForm",
    "ParamBrowRForm",
    "ParamEarPoseL",
    "ParamEarPoseR",
}
STANDARD_GROUPS = {
    "EyeBlink": ("ParamEyeLOpen", "ParamEyeROpen"),
    "LipSync": ("ParamMouthOpenY",),
}


class ExpressionBuildError(RuntimeError):
    """Raised when the runtime export cannot be updated safely."""


@dataclass(frozen=True)
class ParameterValue:
    parameter_id: str
    value: float
    blend: str


@dataclass(frozen=True)
class ExpressionSpec:
    name: str
    fade_in: float
    fade_out: float
    parameters: tuple[ParameterValue, ...]

    @property
    def relative_file(self) -> str:
        return f"{EXPRESSION_DIR}/{self.name}.exp3.json"


EXPRESSIONS = (
    ExpressionSpec(
        "Smile",
        0.18,
        0.28,
        (
            # Keep eye-open and mouth-open tracking alive.  The expression
            # fixes the emotional shape, while speech and blinking continue.
            ParameterValue("ParamMouthForm", 1.0, "Overwrite"),
            ParameterValue("ParamEyeLOpen", 0.94, "Multiply"),
            ParameterValue("ParamEyeROpen", 0.94, "Multiply"),
            ParameterValue("ParamCheek", 0.90, "Overwrite"),
            ParameterValue("ParamBrowLY", 0.22, "Add"),
            ParameterValue("ParamBrowRY", 0.22, "Add"),
            ParameterValue("ParamBrowLForm", 0.38, "Add"),
            ParameterValue("ParamBrowRForm", 0.38, "Add"),
            ParameterValue("ParamEarPoseL", 0.65, "Overwrite"),
            ParameterValue("ParamEarPoseR", 0.65, "Overwrite"),
        ),
    ),
    ExpressionSpec(
        "Sad",
        0.30,
        0.35,
        (
            ParameterValue("ParamMouthForm", -1.0, "Overwrite"),
            ParameterValue("ParamEyeLSmile", 0.0, "Overwrite"),
            ParameterValue("ParamEyeRSmile", 0.0, "Overwrite"),
            ParameterValue("ParamCheek", 0.0, "Overwrite"),
            ParameterValue("ParamBrowLAngle", 0.95, "Add"),
            ParameterValue("ParamBrowRAngle", 0.95, "Add"),
            ParameterValue("ParamBrowLY", -0.38, "Add"),
            ParameterValue("ParamBrowRY", -0.38, "Add"),
            ParameterValue("ParamBrowLForm", -0.58, "Add"),
            ParameterValue("ParamBrowRForm", -0.58, "Add"),
            ParameterValue("ParamEyeLOpen", 0.76, "Multiply"),
            ParameterValue("ParamEyeROpen", 0.76, "Multiply"),
            ParameterValue("ParamEarPoseL", -1.0, "Overwrite"),
            ParameterValue("ParamEarPoseR", -1.0, "Overwrite"),
        ),
    ),
    ExpressionSpec(
        "Angry",
        0.14,
        0.30,
        (
            ParameterValue("ParamMouthForm", -0.62, "Overwrite"),
            ParameterValue("ParamEyeLSmile", 0.0, "Overwrite"),
            ParameterValue("ParamEyeRSmile", 0.0, "Overwrite"),
            ParameterValue("ParamCheek", 0.16, "Overwrite"),
            # Move the two brows towards the centre instead of translating
            # both in the same direction (the r03 expression did the latter).
            ParameterValue("ParamBrowLX", -0.48, "Add"),
            ParameterValue("ParamBrowRX", 0.48, "Add"),
            ParameterValue("ParamBrowLY", -0.52, "Add"),
            ParameterValue("ParamBrowRY", -0.52, "Add"),
            ParameterValue("ParamBrowLAngle", -1.0, "Add"),
            ParameterValue("ParamBrowRAngle", -1.0, "Add"),
            ParameterValue("ParamBrowLForm", -0.42, "Add"),
            ParameterValue("ParamBrowRForm", -0.42, "Add"),
            ParameterValue("ParamEyeLOpen", 0.68, "Multiply"),
            ParameterValue("ParamEyeROpen", 0.68, "Multiply"),
            ParameterValue("ParamEarPoseL", -0.5, "Overwrite"),
            ParameterValue("ParamEarPoseR", -0.5, "Overwrite"),
        ),
    ),
    ExpressionSpec(
        "Surprised",
        0.16,
        0.28,
        (
            # Add keeps live lipsync and blinking expressive while making the
            # pose unmistakable at normal Twitch framing.
            ParameterValue("ParamMouthOpenY", 0.62, "Add"),
            ParameterValue("ParamMouthForm", 0.08, "Overwrite"),
            ParameterValue("ParamEyeLSmile", 0.0, "Overwrite"),
            ParameterValue("ParamEyeRSmile", 0.0, "Overwrite"),
            ParameterValue("ParamCheek", 0.0, "Overwrite"),
            ParameterValue("ParamBrowLY", 1.0, "Add"),
            ParameterValue("ParamBrowRY", 1.0, "Add"),
            ParameterValue("ParamBrowLForm", 0.55, "Add"),
            ParameterValue("ParamBrowRForm", 0.55, "Add"),
            # Temporary art-direction decision: the dedicated surprised-ear
            # design is deferred, so Surprise must preserve the neutral ears.
            ParameterValue("ParamEarPoseL", 0.0, "Overwrite"),
            ParameterValue("ParamEarPoseR", 0.0, "Overwrite"),
        ),
    ),
    ExpressionSpec(
        "Blink",
        0.10,
        0.15,
        (
            ParameterValue("ParamEyeLOpen", 0.0, "Multiply"),
            ParameterValue("ParamEyeROpen", 0.0, "Multiply"),
        ),
    ),
    ExpressionSpec(
        "WinkL",
        0.10,
        0.15,
        (ParameterValue("ParamEyeLOpen", 0.0, "Multiply"),),
    ),
    ExpressionSpec(
        "WinkR",
        0.10,
        0.15,
        (ParameterValue("ParamEyeROpen", 0.0, "Multiply"),),
    ),
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ExpressionBuildError(message)


def _json_bytes(document: Any) -> bytes:
    return (
        json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")


def _load_json(path: Path, label: str) -> tuple[bytes, dict[str, Any]]:
    try:
        data = path.read_bytes()
        document = json.loads(data.decode("utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExpressionBuildError(f"cannot read {label}: {path}: {exc}") from exc
    _require(isinstance(document, dict), f"{label} root is not an object")
    return data, document


def _resolve_model_path(target: Path) -> Path:
    candidate = target.expanduser().resolve(strict=True)
    if candidate.is_dir():
        candidate = candidate / MODEL_FILENAME
    _require(candidate.is_file(), f"model3 file is missing: {candidate}")
    _require(
        candidate.name.casefold() == MODEL_FILENAME.casefold(),
        f"expected {MODEL_FILENAME}, got {candidate.name}",
    )
    return candidate


def _referenced_path(runtime_dir: Path, relative: str, label: str) -> Path:
    _require(relative.strip() == relative and relative, f"{label} path is empty")
    normalized = relative.replace("\\", "/")
    portable = Path(*normalized.split("/"))
    _require(not portable.is_absolute(), f"{label} path must be relative")
    resolved = (runtime_dir / portable).resolve(strict=False)
    _require(
        resolved.is_relative_to(runtime_dir),
        f"{label} path escapes the runtime directory",
    )
    return resolved


def _parameter_ids_from_cdi(document: dict[str, Any]) -> set[str]:
    parameters = document.get("Parameters")
    _require(isinstance(parameters, list), "cdi3 Parameters is not an array")
    result: set[str] = set()
    for index, row in enumerate(parameters):
        _require(isinstance(row, dict), f"cdi3 Parameters[{index}] is invalid")
        parameter_id = row.get("Id")
        _require(
            isinstance(parameter_id, str) and parameter_id,
            f"cdi3 Parameters[{index}].Id is invalid",
        )
        result.add(parameter_id)
    return result


def _collect_strings(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        result: set[str] = set()
        for item in value:
            result.update(_collect_strings(item))
        return result
    if isinstance(value, dict):
        result = set()
        for item in value.values():
            result.update(_collect_strings(item))
        return result
    return set()


def _validate_parameters(
    runtime_dir: Path,
    model: dict[str, Any],
    references: dict[str, Any],
) -> str:
    """Validate IDs with cdi3 first, then moc3/model3 as fallbacks."""

    observed: set[str] = set()
    evidence: list[str] = []
    display_info = references.get("DisplayInfo")
    cdi_candidates: list[Path] = []
    if isinstance(display_info, str):
        cdi_candidates.append(
            _referenced_path(runtime_dir, display_info, "DisplayInfo")
        )
    jade_cdi = runtime_dir / "Jade.cdi3.json"
    if jade_cdi not in cdi_candidates:
        cdi_candidates.append(jade_cdi)
    for candidate in cdi_candidates:
        if not candidate.is_file():
            continue
        _raw, cdi = _load_json(candidate, "cdi3")
        observed.update(_parameter_ids_from_cdi(cdi))
        evidence.append(candidate.name)

    moc_reference = references.get("Moc")
    if isinstance(moc_reference, str):
        moc_path = _referenced_path(runtime_dir, moc_reference, "Moc")
        if moc_path.is_file():
            try:
                moc_data = moc_path.read_bytes()
            except OSError as exc:
                raise ExpressionBuildError(
                    f"cannot read referenced moc3: {moc_path}: {exc}"
                ) from exc
            observed.update(
                parameter_id
                for parameter_id in EXPECTED_PARAMETERS
                if parameter_id.encode("ascii") in moc_data
            )
            evidence.append(moc_path.name)

    # model3 Groups commonly expose eye IDs and provide useful extra evidence.
    observed.update(EXPECTED_PARAMETERS.intersection(_collect_strings(model)))
    missing = sorted(EXPECTED_PARAMETERS - observed)
    _require(
        not missing,
        "cannot validate expression parameters; missing "
        + ", ".join(missing)
        + ". Export Jade.cdi3.json (Display Info) with the runtime model.",
    )
    return ", ".join(evidence) if evidence else MODEL_FILENAME


def _expression_document(spec: ExpressionSpec) -> dict[str, Any]:
    return {
        "Type": "Live2D Expression",
        "FadeInTime": spec.fade_in,
        "FadeOutTime": spec.fade_out,
        "Parameters": [
            {
                "Id": parameter.parameter_id,
                "Value": parameter.value,
                "Blend": parameter.blend,
            }
            for parameter in spec.parameters
        ],
    }


def _validate_expression_registry(expressions: Any) -> list[dict[str, Any]]:
    if expressions is None:
        return []
    _require(isinstance(expressions, list), "FileReferences.Expressions is invalid")
    result: list[dict[str, Any]] = []
    names: set[str] = set()
    files: set[str] = set()
    for index, row in enumerate(expressions):
        _require(isinstance(row, dict), f"Expressions[{index}] is invalid")
        name = row.get("Name")
        filename = row.get("File")
        _require(
            isinstance(name, str)
            and name
            and isinstance(filename, str)
            and filename,
            f"Expressions[{index}] Name/File is invalid",
        )
        folded_name = name.casefold()
        folded_file = filename.replace("\\", "/").casefold()
        _require(folded_name not in names, f"duplicate expression name: {name}")
        _require(
            folded_file not in files,
            f"duplicate expression file reference: {filename}",
        )
        names.add(folded_name)
        files.add(folded_file)
        result.append(row)
    return result


def _merge_standard_groups(groups: Any) -> list[dict[str, Any]]:
    if groups is None:
        result: list[dict[str, Any]] = []
    else:
        _require(isinstance(groups, list), "model3 Groups is invalid")
        _require(
            all(isinstance(row, dict) for row in groups),
            "model3 Groups contains a non-object entry",
        )
        result = copy.deepcopy(groups)
    for name, required_ids in STANDARD_GROUPS.items():
        matches = [row for row in result if row.get("Name") == name]
        _require(len(matches) <= 1, f"duplicate model3 group: {name}")
        if not matches:
            result.append(
                {"Target": "Parameter", "Name": name, "Ids": list(required_ids)}
            )
            continue
        row = matches[0]
        _require(
            row.get("Target") == "Parameter" and isinstance(row.get("Ids"), list),
            f"model3 group {name} is invalid",
        )
        ids = row["Ids"]
        _require(
            all(isinstance(parameter_id, str) for parameter_id in ids),
            f"model3 group {name} contains an invalid ID",
        )
        for parameter_id in required_ids:
            if parameter_id not in ids:
                ids.append(parameter_id)
    return result


def _merge_registry(
    existing: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    result = copy.deepcopy(existing)
    added: list[str] = []
    for spec in EXPRESSIONS:
        same_name = [
            row for row in result if str(row["Name"]).casefold() == spec.name.casefold()
        ]
        same_file = [
            row
            for row in result
            if str(row["File"]).replace("\\", "/").casefold()
            == spec.relative_file.casefold()
        ]
        if same_name or same_file:
            _require(
                len(same_name) == 1
                and len(same_file) == 1
                and same_name[0] is same_file[0]
                and same_name[0]["Name"] == spec.name
                and same_name[0]["File"].replace("\\", "/")
                == spec.relative_file,
                f"expression registry conflict for {spec.name}",
            )
            continue
        result.append({"Name": spec.name, "File": spec.relative_file})
        added.append(spec.name)
    return result, added


def _write_exclusive(path: Path, data: bytes) -> bool:
    if path.exists():
        _require(path.is_file(), f"expression target is not a file: {path}")
        _require(
            path.read_bytes() == data,
            f"refusing to replace differing expression: {path}",
        )
        return False
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
    return True


def _replace_atomic(path: Path, original: bytes, replacement: bytes) -> bool:
    if replacement == original:
        return False
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    _require(not temp.exists(), "atomic model3 temporary path already exists")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    descriptor = os.open(temp, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(replacement)
            handle.flush()
            os.fsync(handle.fileno())
        _require(path.read_bytes() == original, "model3 changed during planning")
        os.replace(temp, path)
    except Exception:
        temp.unlink(missing_ok=True)
        raise
    return True


def build(target: Path) -> dict[str, Any]:
    model_path = _resolve_model_path(target)
    runtime_dir = model_path.parent.resolve(strict=True)
    model_bytes, model = _load_json(model_path, "model3")
    _require(model.get("Version") == 3, "Jade.model3.json is not Version 3")
    references = model.get("FileReferences")
    _require(isinstance(references, dict), "FileReferences is missing or invalid")
    evidence = _validate_parameters(runtime_dir, model, references)

    registry = _validate_expression_registry(references.get("Expressions"))
    merged, registry_added = _merge_registry(registry)
    updated_model = copy.deepcopy(model)
    updated_model["FileReferences"]["Expressions"] = merged
    physics_path = runtime_dir / PHYSICS_FILENAME
    _require(physics_path.is_file(), f"physics file is missing: {physics_path}")
    updated_model["FileReferences"]["Physics"] = PHYSICS_FILENAME
    updated_model["Groups"] = _merge_standard_groups(updated_model.get("Groups"))
    updated_model_bytes = _json_bytes(updated_model)

    expression_dir = runtime_dir / EXPRESSION_DIR
    if expression_dir.exists():
        _require(expression_dir.is_dir(), f"not a directory: {expression_dir}")
    else:
        expression_dir.mkdir()

    payloads = {
        spec: _json_bytes(_expression_document(spec)) for spec in EXPRESSIONS
    }
    # Check every conflict before creating anything.
    for spec, payload in payloads.items():
        path = expression_dir / f"{spec.name}.exp3.json"
        if path.exists():
            _require(path.is_file(), f"expression target is not a file: {path}")
            _require(
                path.read_bytes() == payload,
                f"refusing to replace differing expression: {path}",
            )

    created: list[Path] = []
    try:
        for spec, payload in payloads.items():
            path = expression_dir / f"{spec.name}.exp3.json"
            if _write_exclusive(path, payload):
                created.append(path)
        model_updated = _replace_atomic(
            model_path, model_bytes, updated_model_bytes
        )
    except Exception:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise

    return {
        "status": "ok",
        "model": str(model_path),
        "model_updated": model_updated,
        "parameter_evidence": evidence,
        "expressions_created": [path.name for path in created],
        "expressions_registered": [spec.name for spec in EXPRESSIONS],
        "registry_entries_added": registry_added,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "target",
        type=Path,
        help="runtime directory or its Jade.model3.json file",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    print(json.dumps(build(args.target), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ExpressionBuildError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
