#!/usr/bin/env python3
"""Generate Jade's seven-chain Cubism Physics v3 configuration.

The generator is deterministic, validates every source/destination and writes
exclusively.  It targets the four independent parameters created by
``cmo3_secondary_professional.py`` in addition to the three existing hair
parameters.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Sequence


class PhysicsProfessionalError(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PhysicsProfessionalError(message)


def _input(parameter_id: str, weight: int, kind: str, reflect: bool = False) -> dict[str, Any]:
    return {
        "Source": {"Target": "Parameter", "Id": parameter_id},
        "Weight": weight,
        "Type": kind,
        "Reflect": reflect,
    }


def _output(parameter_id: str, scale: float, reflect: bool = False) -> dict[str, Any]:
    return {
        "Destination": {"Target": "Parameter", "Id": parameter_id},
        "VertexIndex": 2,
        "Scale": scale,
        "Weight": 100,
        "Type": "Angle",
        "Reflect": reflect,
    }


def _vertex(y: float, mobility: float, delay: float, acceleration: float, radius: float) -> dict[str, Any]:
    return {
        "Position": {"X": 0, "Y": y},
        "Mobility": mobility,
        "Delay": delay,
        "Acceleration": acceleration,
        "Radius": radius,
    }


def _normalization() -> dict[str, Any]:
    return {
        "Position": {"Minimum": -10, "Default": 0, "Maximum": 10},
        "Angle": {"Minimum": -30, "Default": 0, "Maximum": 30},
    }


def _chain(
    setting_id: str,
    destination: str,
    inputs: Sequence[dict[str, Any]],
    *,
    radius: float,
    scale: float,
    mobility: tuple[float, float],
    delay: tuple[float, float],
    acceleration: tuple[float, float],
    reflect: bool = False,
) -> dict[str, Any]:
    _require(sum(int(entry["Weight"]) for entry in inputs) == 100, f"{setting_id}: input weights differ")
    return {
        "Id": setting_id,
        "Input": list(inputs),
        "Output": [_output(destination, scale, reflect)],
        "Vertices": [
            _vertex(0, 1.0, 1.0, 1.0, 0),
            _vertex(radius, mobility[0], delay[0], acceleration[0], radius),
            _vertex(radius * 2, mobility[1], delay[1], acceleration[1], radius),
        ],
        "Normalization": _normalization(),
    }


def _document() -> dict[str, Any]:
    def head_body(hw: int, bw: int) -> list[dict[str, Any]]:
        return [
            _input("ParamAngleX", hw // 2, "X"),
            _input("ParamAngleZ", hw - hw // 2, "Angle"),
            _input("ParamBodyAngleX", bw // 2, "X"),
            _input("ParamBodyAngleZ", bw - bw // 2, "Angle"),
        ]

    def head(reflect: bool = False) -> list[dict[str, Any]]:
        return [
            _input("ParamAngleX", 55, "X", reflect),
            _input("ParamAngleZ", 45, "Angle", reflect),
        ]
    body = [
        _input("ParamBodyAngleX", 65, "X"),
        _input("ParamBodyAngleZ", 35, "Angle"),
    ]
    settings = [
        _chain("PhysicsHairFront", "ParamHairFront", head_body(75, 25), radius=6, scale=1.25, mobility=(0.88, 0.84), delay=(0.70, 0.82), acceleration=(1.45, 1.30)),
        _chain("PhysicsHairSide", "ParamHairSide", head_body(65, 35), radius=8, scale=1.45, mobility=(0.90, 0.86), delay=(0.75, 0.86), acceleration=(1.35, 1.22)),
        _chain("PhysicsHairBack", "ParamHairBack", head_body(55, 45), radius=10, scale=1.65, mobility=(0.92, 0.88), delay=(0.80, 0.90), acceleration=(1.25, 1.12)),
        _chain("PhysicsEarL", "ParamEarSwingL", head(False), radius=5, scale=0.95, mobility=(0.84, 0.80), delay=(0.62, 0.74), acceleration=(1.50, 1.36)),
        _chain("PhysicsEarR", "ParamEarSwingR", head(False), radius=5, scale=0.95, mobility=(0.84, 0.80), delay=(0.66, 0.78), acceleration=(1.48, 1.34)),
        _chain("PhysicsAhoge", "ParamAhogeSwing", head(False), radius=7, scale=1.15, mobility=(0.94, 0.91), delay=(0.82, 0.92), acceleration=(1.18, 1.08)),
        _chain("PhysicsCloth", "ParamClothSwing", body, radius=11, scale=0.85, mobility=(0.87, 0.82), delay=(0.78, 0.89), acceleration=(1.18, 1.05)),
    ]
    names = {
        "PhysicsHairFront": "Hair Front",
        "PhysicsHairSide": "Hair Side",
        "PhysicsHairBack": "Hair Back",
        "PhysicsEarL": "Ear L",
        "PhysicsEarR": "Ear R",
        "PhysicsAhoge": "Ahoge",
        "PhysicsCloth": "Sleeves and Skirt",
    }
    meta = {
        "PhysicsSettingCount": len(settings),
        "TotalInputCount": sum(len(setting["Input"]) for setting in settings),
        "TotalOutputCount": sum(len(setting["Output"]) for setting in settings),
        "VertexCount": sum(len(setting["Vertices"]) for setting in settings),
        "EffectiveForces": {"Gravity": {"X": 0, "Y": -1}, "Wind": {"X": 0, "Y": 0}},
        "PhysicsDictionary": [{"Id": setting["Id"], "Name": names[setting["Id"]]} for setting in settings],
    }
    return {"Version": 3, "Meta": meta, "PhysicsSettings": settings}


def _validate(document: dict[str, Any]) -> None:
    _require(document.get("Version") == 3, "physics version differs")
    settings = document.get("PhysicsSettings")
    _require(isinstance(settings, list) and len(settings) == 7, "setting count differs")
    destinations = [setting["Output"][0]["Destination"]["Id"] for setting in settings]
    _require(
        destinations == [
            "ParamHairFront",
            "ParamHairSide",
            "ParamHairBack",
            "ParamEarSwingL",
            "ParamEarSwingR",
            "ParamAhogeSwing",
            "ParamClothSwing",
        ],
        "output destinations/order differs",
    )
    _require(len(destinations) == len(set(destinations)), "physics outputs are not independent")
    allowed_inputs = {"ParamAngleX", "ParamAngleZ", "ParamBodyAngleX", "ParamBodyAngleZ"}
    for setting in settings:
        _require(sum(int(entry["Weight"]) for entry in setting["Input"]) == 100, f"{setting['Id']}: input weight sum differs")
        _require({entry["Source"]["Id"] for entry in setting["Input"]}.issubset(allowed_inputs), f"{setting['Id']}: unknown input")
        _require(len(setting["Vertices"]) == 3 and setting["Output"][0]["VertexIndex"] == 2, f"{setting['Id']}: particle tip differs")
        for vertex in setting["Vertices"]:
            _require(0.0 <= float(vertex["Mobility"]) <= 1.0, f"{setting['Id']}: mobility unstable")
            _require(0.0 < float(vertex["Delay"]) <= 1.0, f"{setting['Id']}: delay unstable")
            _require(float(vertex["Acceleration"]) > 0.0 and float(vertex["Radius"]) >= 0.0, f"{setting['Id']}: particle value unstable")
    meta = document["Meta"]
    _require(meta["PhysicsSettingCount"] == 7 and meta["TotalOutputCount"] == 7 and meta["VertexCount"] == 21, "physics meta count differs")
    _require(meta["TotalInputCount"] == sum(len(s["Input"]) for s in settings), "physics input meta differs")


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
    parser.add_argument("output", type=Path)
    args = parser.parse_args(list(argv) if argv is not None else None)
    output = args.output.resolve(strict=False)
    _require(output.name.endswith(".physics3.json"), "output must end in .physics3.json")
    _require(output.parent.is_dir(), "output directory does not exist")
    _require(not output.exists(), "output exists; refusing overwrite")
    document = _document()
    _validate(document)
    payload = (json.dumps(document, ensure_ascii=False, indent="\t") + "\n").encode("utf-8")
    _require(json.loads(payload) == document, "JSON round-trip differs")
    _write_exclusive(output, payload)
    print(
        json.dumps(
            {
                "status": "ok",
                "output": str(output),
                "settings": 7,
                "inputs": document["Meta"]["TotalInputCount"],
                "outputs": 7,
                "vertices": 21,
                "destinations": [s["Output"][0]["Destination"]["Id"] for s in document["PhysicsSettings"]],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PhysicsProfessionalError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
