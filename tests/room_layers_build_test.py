#!/usr/bin/env python3
"""DEV-010: offline compositor smoke and geometry tests, no network or AI calls."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_room_layers import ART, EXPECTED, CURTAIN_CROP, SHADOW_CROPS, build, make_layers  # noqa: E402


def synthetic_art() -> np.ndarray:
    width, height = EXPECTED
    yy, xx = np.indices((height, width))
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    arr[:, :, 0] = np.clip(190 + (xx / width * 20) - (yy / height * 17), 0, 255)
    arr[:, :, 1] = np.clip(145 + (xx / width * 12) - (yy / height * 12), 0, 255)
    arr[:, :, 2] = np.clip(159 + (xx / width * 10), 0, 255)
    # Plausible cloth and shadow tones exercise nonzero cutout alpha.
    cv2.ellipse(arr, (1063, 209), (90, 115), 0, 0, 360, (229, 215, 212), -1)
    cv2.ellipse(arr, (440, 350), (90, 44), -34, 0, 360, (160, 124, 135), -1)
    cv2.ellipse(arr, (900, 685), (80, 70), 27, 0, 360, (158, 122, 129), -1)
    return arr


def check_layer_geometry() -> None:
    source = synthetic_art()
    output, layers, metrics = make_layers(source)
    assert output.shape == source.shape
    assert metrics["exterior_max"] <= 1
    assert metrics["curtain_nontransparent_pixels"] > 15000
    assert 3 < metrics["affected_percentage"] < 35
    crop = CURTAIN_CROP
    assert layers["room-curtain.webp"].shape == (crop[3] - crop[1], crop[2] - crop[0], 4)
    for filename, bounds in SHADOW_CROPS.items():
        assert layers[filename].shape == (bounds[3] - bounds[1], bounds[2] - bounds[0], 4)
    # Conspicuous fixed pieces such as bed, wooden sash, foreground plants
    # must never be affected by the pixel-level layer builder.
    for px, py in ((40, 900), (1320, 175), (1160, 450), (742, 80), (400, 750)):
        assert np.array_equal(output[py, px], source[py, px]), (px, py)
    print("geometry and unchanged foreground PASS")


def check_real_assets() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result = build(output_dir=Path(tmp))
        original = Image.open(ART / "room-spring.webp")
        assert original.size == EXPECTED
        expected_files = {
            "room-backdrop.webp": EXPECTED,
            "room-curtain.webp": (CURTAIN_CROP[2] - CURTAIN_CROP[0], CURTAIN_CROP[3] - CURTAIN_CROP[1]),
            **{
                name: (box[2] - box[0], box[3] - box[1])
                for name, box in SHADOW_CROPS.items()
            },
        }
        sizes = {}
        for name, size in expected_files.items():
            target = Path(tmp) / name
            with Image.open(target) as check:
                assert check.size == size, (name, check.size, size)
                check.load()
            sizes[name] = target.stat().st_size
            assert sizes[name] > 200, name
        # Avoid massive scene textures on devices: fail on unexpectedly large assets.
        assert sum(sizes.values()) < 1_500_000, sizes
        print("generated WebP assets PASS; bytes:", sizes)
        print("builder metrics:", result)


if __name__ == "__main__":
    check_layer_geometry()
    check_real_assets()
