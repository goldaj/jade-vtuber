#!/usr/bin/env python3
"""Deterministic texture-atlas packing helpers for Jade's Cubism CMO3.

The module is intentionally read-only with respect to the CMO3 archive.  It
extracts the ModelImage PNG payloads, derives their logical sizes from the
existing GTexture transforms, packs those logical rectangles, and renders one
RGBA atlas.  The CAFF/XML writer lives in a separate tool.
"""

from __future__ import annotations

import io
import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from PIL import Image

from cmo3_inventory import CaffArchive, InventoryError


MAX_XML_BYTES = 256 * 1024 * 1024
MAX_IMAGE_BYTES = 128 * 1024 * 1024
DEFAULT_ATLAS_SIZE = 4096
DEFAULT_GUTTER = 4


class AtlasPackError(RuntimeError):
    """Raised when model-image extraction or deterministic packing fails."""


@dataclass(frozen=True)
class ModelImageAsset:
    """One Cubism ModelImage and the source data needed by the atlas writer."""

    name: str
    guid_ref: str
    resource_ref: str
    resource_path: str
    png_bytes: bytes
    raw_width: int
    raw_height: int
    logical_width: int
    logical_height: int
    canvas_m00: float
    canvas_m01: float
    canvas_m02: float
    canvas_m10: float
    canvas_m11: float
    canvas_m12: float

    def image(self) -> Image.Image:
        """Decode the embedded source PNG as an independent RGBA image."""

        with Image.open(io.BytesIO(self.png_bytes)) as source:
            return source.convert("RGBA")


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height


@dataclass(frozen=True)
class AtlasPlacement:
    """Logical ModelImage placement inside an atlas."""

    asset: ModelImageAsset
    x: int
    y: int
    gutter: int
    atlas_size: int

    @property
    def padded_rect(self) -> Rect:
        return Rect(
            self.x - self.gutter,
            self.y - self.gutter,
            self.asset.logical_width + 2 * self.gutter,
            self.asset.logical_height + 2 * self.gutter,
        )

    def as_dict(self) -> dict[str, Any]:
        """Return fields consumed directly by the CMO3 XML writer/audit."""

        return {
            "name": self.asset.name,
            "model_image_guid_ref": self.asset.guid_ref,
            "resource_ref": self.asset.resource_ref,
            "resource_path": self.asset.resource_path,
            "raw_width": self.asset.raw_width,
            "raw_height": self.asset.raw_height,
            "logical_width": self.asset.logical_width,
            "logical_height": self.asset.logical_height,
            "x": self.x,
            "y": self.y,
            "gutter": self.gutter,
            "atlas_local_to_canvas": {
                "m00": self.asset.canvas_m00,
                "m01": self.asset.canvas_m01,
                "m02": self.asset.canvas_m02 - self.x,
                "m10": self.asset.canvas_m10,
                "m11": self.asset.canvas_m11,
                "m12": self.asset.canvas_m12 - self.y,
            },
        }


def _named_child(
    parent: ET.Element,
    tag: str,
    serialized_name: str,
) -> ET.Element | None:
    return next(
        (
            child
            for child in parent.iter(tag)
            if child.get("xs.n") == serialized_name
        ),
        None,
    )


def _required_named_child(
    parent: ET.Element,
    tag: str,
    serialized_name: str,
    context: str,
) -> ET.Element:
    node = _named_child(parent, tag, serialized_name)
    if node is None:
        raise AtlasPackError(
            f"{context} lacks {tag} xs.n={serialized_name!r}"
        )
    return node


def _positive_float(value: str | None, context: str) -> float:
    try:
        result = float(value or "")
    except ValueError as exc:
        raise AtlasPackError(f"invalid {context}: {value!r}") from exc
    if not math.isfinite(result) or result <= 0:
        raise AtlasPackError(f"non-positive {context}: {result!r}")
    return result


def _float_attr(node: ET.Element, name: str, context: str) -> float:
    try:
        result = float(node.attrib[name])
    except (KeyError, ValueError) as exc:
        raise AtlasPackError(f"invalid {context}.{name}") from exc
    if not math.isfinite(result):
        raise AtlasPackError(f"non-finite {context}.{name}")
    return result


def _logical_dimension(raw: int, scale: float, context: str) -> int:
    calculated = raw / scale
    rounded = round(calculated)
    if not math.isclose(calculated, rounded, abs_tol=1e-3):
        raise AtlasPackError(
            f"{context} is not integral: raw={raw}, scale={scale}, "
            f"logical={calculated}"
        )
    if rounded < raw:
        raise AtlasPackError(
            f"{context} ({rounded}) is smaller than raw dimension ({raw})"
        )
    return int(rounded)


def load_model_image_assets(cmo3_path: Path) -> list[ModelImageAsset]:
    """Extract all unique ModelImages and their native PNGs from a CMO3."""

    try:
        archive = CaffArchive.parse(cmo3_path.read_bytes())
        xml_bytes = archive.read_unique_path("main.xml", MAX_XML_BYTES)
        root = ET.fromstring(xml_bytes)
    except (OSError, InventoryError, ET.ParseError) as exc:
        raise AtlasPackError(f"cannot read {cmo3_path}: {exc}") from exc

    shared = root.find("shared")
    if shared is None:
        raise AtlasPackError("main.xml lacks the shared object table")
    id_map = {
        serialized_id: node
        for node in root.iter()
        if (serialized_id := node.get("xs.id")) is not None
    }

    texture_scales: dict[str, set[tuple[float, float]]] = {}
    for texture in shared.findall("GTexture2D"):
        resource = _named_child(texture, "CImageResource", "srcImageResource")
        transform = _named_child(
            texture,
            "CAffine",
            "transformImageResource01toLogical01",
        )
        if resource is None or transform is None or not resource.get("xs.ref"):
            continue
        if abs(_float_attr(transform, "m01", "GTexture transform")) > 1e-9:
            raise AtlasPackError("rotated/sheared GTexture m01 is unsupported")
        if abs(_float_attr(transform, "m10", "GTexture transform")) > 1e-9:
            raise AtlasPackError("rotated/sheared GTexture m10 is unsupported")
        scales = texture_scales.setdefault(resource.get("xs.ref", ""), set())
        scales.add(
            (
                _positive_float(transform.get("m00"), "GTexture m00"),
                _positive_float(transform.get("m11"), "GTexture m11"),
            )
        )

    assets: list[ModelImageAsset] = []
    seen_guids: set[str] = set()
    for model_image in root.findall(".//CModelImage"):
        name_node = _required_named_child(
            model_image,
            "s",
            "name",
            "CModelImage",
        )
        name = name_node.text or "<unnamed>"
        guid_node = _required_named_child(
            model_image,
            "CModelImageGuid",
            "guid",
            name,
        )
        resource_node = _required_named_child(
            model_image,
            "CImageResource",
            "_filteredImage",
            name,
        )
        canvas = _required_named_child(
            model_image,
            "CAffine",
            "_materialLocalToCanvasTransform",
            name,
        )
        guid_ref = guid_node.get("xs.ref")
        resource_ref = resource_node.get("xs.ref")
        if not guid_ref or not resource_ref:
            raise AtlasPackError(f"{name} has an inline/missing GUID or image ref")
        if guid_ref in seen_guids:
            raise AtlasPackError(f"duplicate ModelImage GUID reference {guid_ref}")
        seen_guids.add(guid_ref)

        resource = id_map.get(resource_ref)
        if resource is None or resource.tag != "CImageResource":
            raise AtlasPackError(f"{name} cannot resolve image {resource_ref}")
        file_node = _required_named_child(
            resource,
            "file",
            "imageFileBuf",
            name,
        )
        resource_path = file_node.get("path")
        if not resource_path:
            raise AtlasPackError(f"{name} has an empty imageFileBuf path")
        try:
            png_bytes = archive.read_unique_path(resource_path, MAX_IMAGE_BYTES)
            with Image.open(io.BytesIO(png_bytes)) as decoded:
                decoded.load()
                raw_width, raw_height = decoded.size
                if decoded.format != "PNG":
                    raise AtlasPackError(
                        f"{name} resource {resource_path} is not PNG"
                    )
        except (InventoryError, OSError) as exc:
            raise AtlasPackError(
                f"cannot decode {name} resource {resource_path}: {exc}"
            ) from exc

        declared_size = (
            int(resource.get("width", "-1")),
            int(resource.get("height", "-1")),
        )
        if declared_size != (raw_width, raw_height):
            raise AtlasPackError(
                f"{name} PNG size {(raw_width, raw_height)} disagrees with "
                f"CImageResource {declared_size}"
            )
        scales = texture_scales.get(resource_ref, set())
        if len(scales) != 1:
            raise AtlasPackError(
                f"{name} expected one GTexture scale, found {sorted(scales)}"
            )
        scale_x, scale_y = next(iter(scales))
        assets.append(
            ModelImageAsset(
                name=name,
                guid_ref=guid_ref,
                resource_ref=resource_ref,
                resource_path=resource_path,
                png_bytes=png_bytes,
                raw_width=raw_width,
                raw_height=raw_height,
                logical_width=_logical_dimension(
                    raw_width,
                    scale_x,
                    f"{name} logical width",
                ),
                logical_height=_logical_dimension(
                    raw_height,
                    scale_y,
                    f"{name} logical height",
                ),
                canvas_m00=_float_attr(canvas, "m00", f"{name} canvas"),
                canvas_m01=_float_attr(canvas, "m01", f"{name} canvas"),
                canvas_m02=_float_attr(canvas, "m02", f"{name} canvas"),
                canvas_m10=_float_attr(canvas, "m10", f"{name} canvas"),
                canvas_m11=_float_attr(canvas, "m11", f"{name} canvas"),
                canvas_m12=_float_attr(canvas, "m12", f"{name} canvas"),
            )
        )

    if not assets:
        raise AtlasPackError("the model contains no CModelImage objects")
    return assets


def _intersects(left: Rect, right: Rect) -> bool:
    return not (
        left.right <= right.x
        or right.right <= left.x
        or left.bottom <= right.y
        or right.bottom <= left.y
    )


def _contains(outer: Rect, inner: Rect) -> bool:
    return (
        outer.x <= inner.x
        and outer.y <= inner.y
        and outer.right >= inner.right
        and outer.bottom >= inner.bottom
    )


def _split_free_rect(free: Rect, used: Rect) -> list[Rect]:
    if not _intersects(free, used):
        return [free]
    split: list[Rect] = []
    if used.x > free.x:
        split.append(Rect(free.x, free.y, used.x - free.x, free.height))
    if used.right < free.right:
        split.append(
            Rect(used.right, free.y, free.right - used.right, free.height)
        )
    if used.y > free.y:
        split.append(Rect(free.x, free.y, free.width, used.y - free.y))
    if used.bottom < free.bottom:
        split.append(
            Rect(free.x, used.bottom, free.width, free.bottom - used.bottom)
        )
    return [rect for rect in split if rect.width > 0 and rect.height > 0]


def _prune_free_rects(rectangles: Sequence[Rect]) -> list[Rect]:
    unique = sorted(
        set(rectangles),
        key=lambda rect: (rect.y, rect.x, rect.height, rect.width),
    )
    return [
        rect
        for index, rect in enumerate(unique)
        if not any(
            index != other_index and _contains(other, rect)
            for other_index, other in enumerate(unique)
        )
    ]


def pack_model_images(
    assets: Sequence[ModelImageAsset],
    *,
    atlas_size: int = DEFAULT_ATLAS_SIZE,
    gutter: int = DEFAULT_GUTTER,
) -> list[AtlasPlacement]:
    """Pack logical rectangles with deterministic MaxRects BSSF, no rotation."""

    if atlas_size <= 0 or gutter < 0:
        raise AtlasPackError("atlas_size must be positive and gutter non-negative")
    ordered = sorted(
        assets,
        key=lambda asset: (
            -asset.logical_height,
            -asset.logical_width,
            asset.name.casefold(),
            asset.guid_ref,
        ),
    )
    free_rects = [Rect(0, 0, atlas_size, atlas_size)]
    placements: list[AtlasPlacement] = []
    for asset in ordered:
        padded_width = asset.logical_width + 2 * gutter
        padded_height = asset.logical_height + 2 * gutter
        candidates: list[tuple[tuple[int, int, int, int], Rect]] = []
        for free in free_rects:
            if padded_width <= free.width and padded_height <= free.height:
                leftover_x = free.width - padded_width
                leftover_y = free.height - padded_height
                score = (
                    min(leftover_x, leftover_y),
                    max(leftover_x, leftover_y),
                    free.y,
                    free.x,
                )
                candidates.append((score, free))
        if not candidates:
            raise AtlasPackError(
                f"{asset.name} ({padded_width}x{padded_height}) does not fit "
                f"the {atlas_size}x{atlas_size} atlas"
            )
        _, selected = min(candidates, key=lambda candidate: candidate[0])
        used = Rect(selected.x, selected.y, padded_width, padded_height)
        free_rects = _prune_free_rects(
            [
                split
                for free in free_rects
                for split in _split_free_rect(free, used)
            ]
        )
        placements.append(
            AtlasPlacement(
                asset=asset,
                x=used.x + gutter,
                y=used.y + gutter,
                gutter=gutter,
                atlas_size=atlas_size,
            )
        )
    return placements


def render_atlas(
    placements: Sequence[AtlasPlacement],
    *,
    atlas_size: int = DEFAULT_ATLAS_SIZE,
) -> Image.Image:
    """Render source pixels at each logical rectangle's top-left corner."""

    atlas = Image.new("RGBA", (atlas_size, atlas_size), (0, 0, 0, 0))
    for placement in placements:
        if placement.atlas_size != atlas_size:
            raise AtlasPackError("placement atlas size does not match render size")
        image = placement.asset.image()
        if image.size != (
            placement.asset.raw_width,
            placement.asset.raw_height,
        ):
            raise AtlasPackError(f"decoded size changed for {placement.asset.name}")
        if (
            placement.x + image.width > atlas_size
            or placement.y + image.height > atlas_size
        ):
            raise AtlasPackError(f"raw pixels overflow for {placement.asset.name}")
        # No alpha mask: preserve the embedded RGBA bytes exactly, including
        # RGB values carried by fully transparent pixels.
        atlas.paste(image, (placement.x, placement.y))
    return atlas


def encode_atlas_png(atlas: Image.Image) -> bytes:
    """Encode a deterministic, non-interlaced RGBA PNG."""

    output = io.BytesIO()
    atlas.save(output, format="PNG", optimize=False, compress_level=9)
    return output.getvalue()


def build_atlas(
    cmo3_path: Path,
    *,
    atlas_size: int = DEFAULT_ATLAS_SIZE,
    gutter: int = DEFAULT_GUTTER,
) -> tuple[bytes, list[dict[str, Any]]]:
    """Convenience API returning atlas PNG bytes and JSON-friendly placements."""

    assets = load_model_image_assets(cmo3_path)
    placements = pack_model_images(
        assets,
        atlas_size=atlas_size,
        gutter=gutter,
    )
    atlas = render_atlas(placements, atlas_size=atlas_size)
    return encode_atlas_png(atlas), [item.as_dict() for item in placements]

