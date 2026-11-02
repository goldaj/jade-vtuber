#!/usr/bin/env python3
"""Validate a Jade Cubism runtime package before importing it in VTube Studio."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
from typing import Any, Sequence


MODEL3_NAME = "Jade.model3.json"
EXPECTED_MOC = "Jade.moc3"
EXPECTED_PHYSICS = "Jade.physics3.json"
EXPECTED_CDI = "Jade.cdi3.json"
EXPECTED_CDI_PARAMETERS = {
    "ParamAngleX",
    "ParamAngleY",
    "ParamAngleZ",
    "ParamBodyAngleX",
    "ParamBodyAngleY",
    "ParamBodyAngleZ",
    "ParamEyeLOpen",
    "ParamEyeROpen",
    "ParamEyeBallX",
    "ParamEyeBallY",
    "ParamMouthForm",
    "ParamMouthOpenY",
    "ParamBreath",
    "ParamHairFront",
    "ParamHairSide",
    "ParamHairBack",
}


def _json_file(
    path: Path, label: str, errors: list[str], checked: set[Path]
) -> Any | None:
    checked.add(path)
    if not path.is_file():
        errors.append(f"{label}: fichier absent: {path.name}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"{label}: JSON illisible: {exc}")
        return None


def _safe_reference(root: Path, value: Any, label: str, errors: list[str]) -> Path | None:
    if not isinstance(value, str) or not value:
        errors.append(f"{label}: chemin vide ou non textuel")
        return None
    if "\\" in value:
        errors.append(f"{label}: utiliser des séparateurs '/' dans le JSON")
        return None
    relative = PurePosixPath(value)
    if relative.is_absolute() or relative.anchor or ".." in relative.parts:
        errors.append(f"{label}: chemin absolu ou échappant au dossier runtime: {value}")
        return None
    candidate = (root / Path(*relative.parts)).resolve(strict=False)
    try:
        inside = os.path.commonpath((str(root), str(candidate))) == str(root)
    except ValueError:
        inside = False
    if not inside:
        errors.append(f"{label}: chemin hors du dossier runtime: {value}")
        return None
    return candidate


def _file_reference(
    root: Path,
    value: Any,
    label: str,
    errors: list[str],
    *,
    expected_name: str | None = None,
) -> Path | None:
    path = _safe_reference(root, value, label, errors)
    if path is None:
        return None
    if expected_name is not None and path.name != expected_name:
        errors.append(f"{label}: attendu {expected_name}, reçu {path.name}")
    if not path.is_file():
        errors.append(f"{label}: fichier référencé absent: {value}")
    elif path.stat().st_size <= 0:
        errors.append(f"{label}: fichier référencé vide: {value}")
    return path


def _validate_groups(model: dict[str, Any], errors: list[str]) -> dict[str, list[str]]:
    groups = model.get("Groups")
    if not isinstance(groups, list):
        errors.append("model3: Groups absent ou invalide")
        return {}
    observed: dict[str, list[str]] = {}
    for index, group in enumerate(groups):
        if not isinstance(group, dict):
            errors.append(f"model3: Groups[{index}] invalide")
            continue
        name = group.get("Name")
        ids = group.get("Ids")
        if group.get("Target") != "Parameter" or not isinstance(name, str):
            continue
        if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
            errors.append(f"model3: groupe {name} sans liste Ids valide")
            continue
        if name in observed:
            errors.append(f"model3: groupe {name} dupliqué")
            continue
        observed[name] = ids
    blink = set(observed.get("EyeBlink", []))
    lipsync = set(observed.get("LipSync", []))
    if not {"ParamEyeLOpen", "ParamEyeROpen"}.issubset(blink):
        errors.append("model3: EyeBlink doit contenir ParamEyeLOpen et ParamEyeROpen")
    if "ParamMouthOpenY" not in lipsync:
        errors.append("model3: LipSync doit contenir ParamMouthOpenY")
    return observed


def _validate_cdi(path: Path, errors: list[str], checked: set[Path]) -> int:
    document = _json_file(path, "cdi3", errors, checked)
    if not isinstance(document, dict):
        return 0
    parameters = document.get("Parameters")
    if not isinstance(parameters, list):
        errors.append("cdi3: Parameters absent ou invalide")
        return 0
    ids = {
        row.get("Id")
        for row in parameters
        if isinstance(row, dict) and isinstance(row.get("Id"), str)
    }
    missing = sorted(EXPECTED_CDI_PARAMETERS - ids)
    if missing:
        errors.append("cdi3: IDs Jade manquants: " + ", ".join(missing))
    return len(ids)


def _validate(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checked: set[Path] = set()
    model_path = root / MODEL3_NAME
    model = _json_file(model_path, "model3", errors, checked)
    if not isinstance(model, dict):
        return {
            "status": "error",
            "runtime": str(root),
            "errors": errors,
            "warnings": warnings,
            "checked_files": len(checked),
        }
    if model.get("Version") != 3:
        errors.append("model3: Version doit être 3")
    references = model.get("FileReferences")
    if not isinstance(references, dict):
        errors.append("model3: FileReferences absent ou invalide")
        references = {}

    moc_path = _file_reference(
        root, references.get("Moc"), "model3.Moc", errors, expected_name=EXPECTED_MOC
    )
    if moc_path is not None:
        checked.add(moc_path)

    texture_paths: list[Path] = []
    textures = references.get("Textures")
    if not isinstance(textures, list) or not textures:
        errors.append("model3: aucune texture référencée")
    else:
        seen_textures: set[str] = set()
        for index, value in enumerate(textures):
            path = _file_reference(root, value, f"model3.Textures[{index}]", errors)
            if path is None:
                continue
            checked.add(path)
            if path.suffix.casefold() != ".png":
                errors.append(f"texture non-PNG: {path.name}")
            key = str(path).casefold()
            if key in seen_textures:
                errors.append(f"texture référencée deux fois: {path.name}")
            seen_textures.add(key)
            texture_paths.append(path)

    physics_path = _file_reference(
        root,
        references.get("Physics"),
        "model3.Physics",
        errors,
        expected_name=EXPECTED_PHYSICS,
    )
    physics = None
    if physics_path is not None:
        physics = _json_file(physics_path, "physics3", errors, checked)
        if isinstance(physics, dict) and physics.get("Version") != 3:
            errors.append("physics3: Version doit être 3")

    expressions = references.get("Expressions")
    expression_names: set[str] = set()
    expression_count = 0
    if not isinstance(expressions, list) or not expressions:
        errors.append("model3: aucune expression référencée")
    else:
        for index, entry in enumerate(expressions):
            if not isinstance(entry, dict):
                errors.append(f"model3.Expressions[{index}] invalide")
                continue
            name = entry.get("Name")
            if not isinstance(name, str) or not name:
                errors.append(f"model3.Expressions[{index}].Name invalide")
            elif name in expression_names:
                errors.append(f"expression dupliquée: {name}")
            else:
                expression_names.add(name)
            path = _file_reference(
                root, entry.get("File"), f"model3.Expressions[{index}].File", errors
            )
            if path is not None:
                document = _json_file(path, f"expression {name or index}", errors, checked)
                if isinstance(document, dict) and document.get("Type") != "Live2D Expression":
                    warnings.append(f"expression {name or index}: champ Type non standard")
                expression_count += 1

    groups = _validate_groups(model, errors)

    cdi_candidates: set[Path] = set()
    display_info = references.get("DisplayInfo")
    if display_info is not None:
        path = _file_reference(
            root,
            display_info,
            "model3.DisplayInfo",
            errors,
            expected_name=EXPECTED_CDI,
        )
        if path is not None:
            cdi_candidates.add(path)
    conventional_cdi = root / EXPECTED_CDI
    if conventional_cdi.exists():
        cdi_candidates.add(conventional_cdi.resolve(strict=False))
    cdi_parameter_count = 0
    if cdi_candidates:
        for path in sorted(cdi_candidates):
            cdi_parameter_count = max(
                cdi_parameter_count, _validate_cdi(path, errors, checked)
            )
    else:
        warnings.append("Jade.cdi3.json absent (facultatif pour l'exécution)")

    return {
        "status": "ok" if not errors else "error",
        "runtime": str(root),
        "errors": errors,
        "warnings": warnings,
        "checked_files": len(checked),
        "textures": len(texture_paths),
        "expressions": expression_count,
        "groups": {name: ids for name, ids in sorted(groups.items())},
        "cdi_parameter_ids": cdi_parameter_count,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runtime", type=Path, help="dossier contenant Jade.model3.json")
    args = parser.parse_args(list(argv) if argv is not None else None)
    runtime = args.runtime.resolve(strict=True)
    if not runtime.is_dir():
        parser.error("runtime doit être un dossier")
    report = _validate(runtime)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
