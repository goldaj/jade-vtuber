#!/usr/bin/env python3
"""Build reversible, independently animated room layers from the original art.

Runs OFFLINE on an artist/CI workstation, never on an Android device.
Dependency versions are in scripts/requirements-room-layers.txt.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "src/jade_runtime/mobile_web"
SOURCE = ART / "room-spring.webp"
EXPECTED = (1448, 1086)

# Image-space geometry from the native 1448 × 1086 artwork, not phone pixels.
# Image-space hand-traced textile; the curtain rod, rings and wooden sash stay
# in the stationary backdrop (no rectangular texture displacement).
CURTAIN = [
    (1038, 85), (1055, 85), (1081, 83), (1110, 84), (1133, 81),
    (1142, 90), (1142, 145), (1138, 191), (1137, 252),
    (1135, 296), (1125, 310), (1100, 307), (1074, 301),
    (1055, 314), (1041, 327), (1015, 344), (989, 348),
    (965, 349), (948, 350), (933, 344), (911, 336),
    (930, 303), (957, 281), (974, 252), (986, 217),
    (997, 173), (1008, 132), (1027, 92),
]
CURTAIN_CROP = (900, 66, 1162, 362)


def mask_polygon(height: int, width: int, vertices: list[tuple[int, int]], sigma: float) -> np.ndarray:
    solid = np.zeros((height, width), dtype=np.uint8)
    cv2.fillPoly(solid, [np.asarray(vertices, dtype=np.int32)], 255)
    blurred = cv2.GaussianBlur(solid, (0, 0), sigmaX=sigma)
    return blurred.astype(np.float32) / 255.0


def alpha_cutout(original: np.ndarray, under: np.ndarray, extent: np.ndarray,
                 upper_alpha: float = 0.91) -> np.ndarray:
    """Original textile RGB with soft source-art matte, without color extrapolation.

    Solving for translucent RGB against an invented background introduces
    saturated cyan/yellow fringes. Keep actual fabric paint instead: motion
    matters more than reproducing the exact stationary composite mathematically.
    """
    difference = np.max(np.abs(original.astype(np.float32) - under), axis=2) / 255.0
    opacity = extent * np.clip(upper_alpha + 0.04 * difference, 0, 0.96)
    rgba = np.dstack([original, (opacity * 255.0).astype(np.uint8)])
    rgba[extent < 0.006] = 0
    return rgba.astype(np.uint8)


def restore_behind_curtain(source: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Reconstruct wall, vertical wooden jamb and sky with nearby genuine pixels.

    Large-region inpainting painted orange smears across the fixed window.
    Instead we explicitly keep its geometry and use three source materials.
    The textile is then composited over this fixed plane.
    """
    h, w = source.shape[:2]
    yy, xx = np.indices((h, w))
    wall = source[yy, np.clip(xx - 225, 610, 920)].astype(np.float32)
    wood = source[np.clip(yy + 305, 367, 718), np.clip(xx, 1040, 1066)].astype(np.float32)
    sky = source[yy, np.clip(xx + 150, 1182, w - 1)].astype(np.float32)

    def blend_weight(x: np.ndarray, x0: float, x1: float) -> np.ndarray:
        p = np.clip((x.astype(np.float32) - x0) / (x1 - x0), 0.0, 1.0)
        return p * p * (3.0 - 2.0 * p)

    # A flat wall ends at x≈1038. The wooden jamb remains straight while the
    # glass behind the sheer cloth is filled with neighbouring blue sky.
    to_wood = blend_weight(xx, 1032, 1045)[..., None]
    to_sky = blend_weight(xx, 1069, 1083)[..., None]
    rebuilt_window = wood * (1 - to_sky) + sky * to_sky
    donor = wall * (1 - to_wood) + rebuilt_window * to_wood
    m = mask[..., None]
    return source.astype(np.float32) * (1 - m) + donor * m


def make_layers(source: np.ndarray) -> tuple[np.ndarray, dict[str, np.ndarray], dict[str, float]]:
    height, width = source.shape[:2]
    assert (width, height) == EXPECTED, f"unexpected artwork dimensions: {width}x{height}"
    curtain_mask = mask_polygon(height, width, CURTAIN, 2.0)
    behind = restore_behind_curtain(source, curtain_mask)

    # A light, low-saturation matte keeps painted wood, blue sky and warm
    # wall pixels OUT of the moving textile. Low-opacity lace stays soft.
    colors = source.astype(np.float32)
    red, green, blue = colors[:, :, 0], colors[:, :, 1], colors[:, :, 2]
    pastel = np.minimum.reduce([
        np.clip((red - 155) / 29, 0, 1),
        np.clip((green - 137) / 30, 0, 1),
        np.clip((blue - 125) / 30, 0, 1),
        np.clip((red + 12 - blue) / 35, 0, 1),
    ])
    pastel = cv2.GaussianBlur(pastel, (0, 0), 1.3)
    fabric_mask = curtain_mask * np.clip(pastel * 1.18, 0.0, 1.0)
    fabric = alpha_cutout(source, behind, fabric_mask, upper_alpha=0.88)
    # Conservative fixed-geometry exclusion. The original composite includes
    # wood immediately behind the sheer edge. Never let that wood travel with
    # the cloth, even if it means sacrificing a few lace-edge pixels.
    yy, xx = np.indices((height, width))
    # Scalloped underside: no moving rectangle of wall or wooden sill.
    lower_edge = np.interp(
        xx, [900, 925, 946, 970, 1005, 1030, 1070, 1110, 1140, 1162],
        [330, 348, 352, 345, 328, 311, 302, 301, 297, 290],
    )
    fade = np.clip((lower_edge - yy) / 4.0, 0, 1)
    fabric[:, :, 3] = (fabric[:, :, 3].astype(np.float32) * fade).astype(np.uint8)
    fabric[(xx >= 1139) & (yy >= 100), 3] = 0
    crop = CURTAIN_CROP
    layers = {
        "room-curtain.webp": fabric[crop[1]:crop[3], crop[0]:crop[2]],
    }
    output = np.clip(behind, 0, 255).astype(np.uint8)
    unchanged = source[curtain_mask < 0.005].astype(np.int16) - output[curtain_mask < 0.005].astype(np.int16)
    exterior_max = float(np.abs(unchanged).max(initial=0))
    if exterior_max > 1:
        raise AssertionError(f"pixels outside textile area changed: {exterior_max}")
    visible = int(np.count_nonzero(layers["room-curtain.webp"][:, :, 3] > 100))
    if visible < 12_000:
        raise AssertionError(f"fabric matte too sparse: {visible}")
    return output, layers, {
        "exterior_max": exterior_max,
        "curtain_nontransparent_pixels": float(visible),
        "affected_percentage": float(np.mean(curtain_mask > 0.005) * 100),
    }

def build(*, output_dir: Path = ART) -> dict[str, float]:
    source = np.asarray(Image.open(SOURCE).convert("RGB"))
    backdrop, layers, metrics = make_layers(source)
    output_dir.mkdir(parents=True, exist_ok=True)
    Image.fromarray(backdrop, "RGB").save(
        output_dir / "room-backdrop.webp", "WEBP", quality=94, method=6
    )
    for name, image in layers.items():
        Image.fromarray(image, "RGBA").save(
            output_dir / name, "WEBP", lossless=True, method=6
        )
    for file in ("room-backdrop.webp", *layers):
        image = Image.open(output_dir / file)
        image.verify()
        metrics[file + "_bytes"] = float((output_dir / file).stat().st_size)
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ART)
    args = parser.parse_args()
    for key, value in build(output_dir=args.output).items():
        print(f"{key}: {value:.2f}")


if __name__ == "__main__":
    main()
