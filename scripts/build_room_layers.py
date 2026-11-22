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
# The curtain is the translucent textile, not its rod / rings / fixed wooden sash.
CURTAIN = [
    (1035, 72), (1055, 77), (1081, 72), (1112, 72), (1142, 65),
    (1155, 75), (1154, 142), (1147, 199), (1144, 264),
    (1140, 300), (1123, 315), (1093, 313), (1060, 304),
    (1030, 324), (1001, 339), (963, 352), (940, 349),
    (923, 338), (917, 326), (939, 297), (957, 277),
    (974, 246), (986, 210), (996, 167), (1004, 132),
    (1018, 93), (1026, 73),
]
# Exclude physical objects: leaves/shelf to the left, lamp/table/bed at bottom,
# window sash and wood to the right. Feather only within the wall.
WALL_LEFT = [
    (323, 190), (568, 169), (641, 307), (622, 466),
    (543, 604), (375, 586), (342, 443), (311, 284),
]
WALL_RIGHT = [
    (819, 458), (998, 424), (1022, 502), (1015, 835),
    (799, 829), (789, 704),
]
SHADOW_CROPS = {
    "room-shadow-left.webp": (286, 139, 674, 630),
    "room-shadow-right.webp": (767, 397, 1034, 861),
}
CURTAIN_CROP = (892, 49, 1181, 370)


def mask_polygon(height: int, width: int, vertices: list[tuple[int, int]], sigma: float) -> np.ndarray:
    solid = np.zeros((height, width), dtype=np.uint8)
    cv2.fillPoly(solid, [np.asarray(vertices, dtype=np.int32)], 255)
    blurred = cv2.GaussianBlur(solid, (0, 0), sigmaX=sigma)
    return blurred.astype(np.float32) / 255.0


def alpha_cutout(original: np.ndarray, under: np.ndarray, extent: np.ndarray,
                 upper_alpha: float = 0.87) -> np.ndarray:
    """Solve source-over for an editable translucent layer that reproduces its rest pose."""
    discrepancy = np.max(np.abs(original.astype(np.float32) - under), axis=2) / 255.0
    # Keep a strong fabric core while feathering the silhouette at the edges.
    opacity = extent * np.clip(upper_alpha + 0.12 * discrepancy, 0.0, 0.97)
    alpha = opacity[..., None]
    safe = np.maximum(alpha, 0.0001)
    pigment = (original.astype(np.float32) - under * (1.0 - alpha)) / safe
    pigment = np.clip(pigment, 0.0, 255.0)
    rgba = np.concatenate([pigment, alpha * 255.0], axis=2)
    rgba[extent < 0.004] = 0
    return rgba.clip(0, 255).astype(np.uint8)


def make_layers(source: np.ndarray) -> tuple[np.ndarray, dict[str, np.ndarray], dict[str, float]]:
    height, width = source.shape[:2]
    assert (width, height) == EXPECTED, f"unexpected artwork dimensions: {width}x{height}"
    curtain_mask = mask_polygon(height, width, CURTAIN, 2.3)
    # Inpaint only the textile, leaving all other stationary details untouched.
    hole = (curtain_mask > 0.12).astype(np.uint8) * 255
    behind = cv2.inpaint(source, hole, 10, cv2.INPAINT_TELEA).astype(np.float32)

    mask_l = mask_polygon(height, width, WALL_LEFT, 23)
    mask_r = mask_polygon(height, width, WALL_RIGHT, 23)
    # Morphological closing removes short dark leaf shadows from flat wall paint.
    # The moving shadow layers carry their visual structure back to the composition.
    sunlit = cv2.morphologyEx(
        behind.astype(np.uint8), cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (75, 75)),
    )
    sunlit = cv2.GaussianBlur(sunlit, (0, 0), 7).astype(np.float32)

    # The left and right leaf clusters can drift at different speeds.
    layers: dict[str, np.ndarray] = {}
    base = behind.copy()
    for filename, wall_mask in (
        ("room-shadow-left.webp", mask_l),
        ("room-shadow-right.webp", mask_r),
    ):
        before = base.copy()
        a = wall_mask[..., None]
        clean = before * (1.0 - a) + sunlit * a
        # Only dark texture is treated as leaf shadow; bright mural paint remains in base.
        contrast = np.maximum(before - clean, 0)
        blackness = np.max(np.maximum(clean - before, 0) / np.maximum(clean, 1), axis=2)
        opacity = np.where(blackness > 0.009, np.clip(blackness * 1.30 + 0.035, 0, 0.92), 0)
        opacity *= wall_mask
        cutout = alpha_cutout(before.astype(np.uint8), clean, opacity, upper_alpha=0.98)
        # Avoid unnecessarily erasing painterly wall texture. Only selected
        # dark shadows should be replaced by their sunlit counterpart.
        blend = np.clip(opacity[..., None] * 1.7, 0, 1)
        base = before * (1.0 - blend) + clean * blend
        # Re-solve against the final base for exact shadow positioning at rest.
        cutout = alpha_cutout(before.astype(np.uint8), base, opacity, upper_alpha=0.98)
        crop = SHADOW_CROPS[filename]
        layers[filename] = cutout[crop[1]:crop[3], crop[0]:crop[2]]
    # A final textile cutout is solved against the reconstructed stationary frame.
    fabric = alpha_cutout(source, base, curtain_mask, upper_alpha=0.90)
    crop = CURTAIN_CROP
    layers["room-curtain.webp"] = fabric[crop[1]:crop[3], crop[0]:crop[2]]
    output = np.clip(base, 0, 255).astype(np.uint8)

    # The fixed illustration must not be replaced outside the designated zones.
    altered = (curtain_mask > 0.005) | (mask_l > 0.005) | (mask_r > 0.005)
    unchanged = source[~altered].astype(np.int16) - output[~altered].astype(np.int16)
    exterior_max = float(np.abs(unchanged).max(initial=0))
    if exterior_max > 1:
        raise AssertionError(f"pixels outside intended layer zones changed: {exterior_max}")
    if int(np.count_nonzero(layers["room-curtain.webp"][:, :, 3] > 100)) < 15_000:
        raise AssertionError("curtain not extracted")

    return output, layers, {
        "exterior_max": exterior_max,
        "curtain_nontransparent_pixels": float(np.count_nonzero(layers["room-curtain.webp"][:, :, 3] > 100)),
        "affected_percentage": float(np.mean(altered) * 100),
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
