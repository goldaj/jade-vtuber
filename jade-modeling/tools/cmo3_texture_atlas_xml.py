#!/usr/bin/env python3
"""Build the native Cubism 5.2 texture-atlas objects in a decoded CMO3 XML.

This module intentionally operates on ``main.xml`` only.  It does not read or
write a CAFF/CMO3 archive and it does not create the PNG members referenced by
the generated ``CImageResource`` objects.  The archive writer owns those two
jobs and passes JSON-serializable atlas specifications to
``patch_texture_atlas_xml``.

The emitted graph follows an atlas created by Cubism Editor 5.2.03:

* one shared ``CTextureAtlas``, ``CImageResource`` and
  ``CTextureAtlasGuid`` per atlas image;
* one ``ModelImageEntry`` per placed model image;
* one inline ``CTextureInput_TextureAtlasRegion`` beside each existing model
  image texture input;
* the current texture input remains the model image, exactly as Cubism writes
  it while the editor is in model-image mode.

The function is deliberately strict.  It accepts only an atlas-free source,
requires a complete one-to-one placement of all model images, and verifies
that current texture inputs, TextureState, GTexture2D objects, and UV arrays
remain byte-for-byte unchanged.
"""

from __future__ import annotations

import math
import re
import uuid
from dataclasses import dataclass
from html import escape as xml_escape
from pathlib import PurePosixPath
from typing import Mapping, Sequence


__all__ = ["TextureAtlasXMLError", "patch_texture_atlas_xml"]


class TextureAtlasXMLError(RuntimeError):
    """Raised when atlas XML cannot be added without violating invariants."""


@dataclass(frozen=True)
class _Placement:
    model_image_guid: str
    x: float
    y: float
    scale_x: float
    scale_y: float
    euler_angle: float


@dataclass(frozen=True)
class _Atlas:
    name: str
    width: int
    height: int
    image_path: str
    image_file_size: int
    guid_uuid: str
    placements: tuple[_Placement, ...]


@dataclass(frozen=True)
class _AtlasIds:
    atlas_ref: str
    image_ref: str
    guid_ref: str
    atlas_idx: int
    image_idx: int
    guid_idx: int


_MODEL_IMAGE_BLOCK_RE = re.compile(
    r"<CModelImage\s+modelImageVersion=\"[^\"]+\">.*?</CModelImage>",
    re.DOTALL,
)
_GUID_DEFINITION_RE = re.compile(
    r"<CModelImageGuid\s+[^>]*\buuid=\"(?P<uuid>[^\"]+)\"[^>]*"
    r"\bxs\.id=\"(?P<ref>#[0-9]+)\"[^>]*/>"
)
_MODEL_INPUT_BLOCK_RE = re.compile(
    r"<CTextureInput_ModelImage\s+xs\.id=\"(?P<ref>#[0-9]+)\"[^>]*>"
    r".*?</CTextureInput_ModelImage>",
    re.DOTALL,
)
_EXTENSION_BLOCK_RE = re.compile(
    r"<CTextureInputExtension\s+xs\.id=\"#[0-9]+\"[^>]*>"
    r".*?</CTextureInputExtension>",
    re.DOTALL,
)
_TEXTURE_INPUT_LIST_RE = re.compile(
    r"(?P<open><carray_list\s+xs\.n=\"_textureInputs\"\s+count=\")"
    r"(?P<count>[0-9]+)(?P<open_end>\">)(?P<body>.*?)"
    r"(?P<close></carray_list>)",
    re.DOTALL,
)


def _error(message: str) -> TextureAtlasXMLError:
    return TextureAtlasXMLError(message)


def _require_mapping(value: object, context: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise _error(f"{context} must be a JSON object")
    return value


def _strict_keys(
    value: Mapping[str, object],
    *,
    required: set[str],
    optional: set[str],
    context: str,
) -> None:
    keys = set(value)
    missing = sorted(required - keys)
    unknown = sorted(keys - required - optional)
    if missing:
        raise _error(f"{context} is missing keys: {', '.join(missing)}")
    if unknown:
        raise _error(f"{context} has unknown keys: {', '.join(unknown)}")


def _string(value: object, context: str, *, max_chars: int = 255) -> str:
    if not isinstance(value, str):
        raise _error(f"{context} must be a string")
    if not value or value.strip() != value or len(value) > max_chars:
        raise _error(
            f"{context} must be non-empty, trimmed, and at most {max_chars} chars"
        )
    if any(ord(character) < 0x20 for character in value):
        raise _error(f"{context} contains a control character")
    return value


def _positive_int(value: object, context: str, *, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _error(f"{context} must be an integer")
    if not 0 < value <= maximum:
        raise _error(f"{context} must be between 1 and {maximum}")
    return value


def _finite_number(value: object, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _error(f"{context} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise _error(f"{context} must be a finite number")
    return 0.0 if result == 0.0 else result


def _canonical_uuid(value: object, context: str) -> str:
    raw = _string(value, context, max_chars=36)
    try:
        parsed = uuid.UUID(raw)
    except ValueError as exc:
        raise _error(f"{context} is not a UUID: {raw!r}") from exc
    if str(parsed) != raw.lower():
        raise _error(f"{context} must use canonical UUID spelling")
    return str(parsed)


def _parse_placement(value: object, context: str) -> _Placement:
    item = _require_mapping(value, context)
    _strict_keys(
        item,
        required={"model_image_guid", "x", "y"},
        optional={"scale_x", "scale_y", "euler_angle"},
        context=context,
    )
    scale_x = _finite_number(item.get("scale_x", 1.0), f"{context}.scale_x")
    scale_y = _finite_number(item.get("scale_y", 1.0), f"{context}.scale_y")
    if scale_x <= 0.0 or scale_y <= 0.0:
        raise _error(f"{context} scale values must be positive")
    euler_angle = _finite_number(
        item.get("euler_angle", 0.0), f"{context}.euler_angle"
    )
    if not math.isclose(scale_x, 1.0, abs_tol=1e-12):
        raise _error(f"{context}.scale_x must be 1.0 for this atlas writer")
    if not math.isclose(scale_y, 1.0, abs_tol=1e-12):
        raise _error(f"{context}.scale_y must be 1.0 for this atlas writer")
    if not math.isclose(euler_angle, 0.0, abs_tol=1e-12):
        raise _error(f"{context}.euler_angle must be 0.0 for this atlas writer")
    return _Placement(
        model_image_guid=_canonical_uuid(
            item["model_image_guid"], f"{context}.model_image_guid"
        ),
        x=_finite_number(item["x"], f"{context}.x"),
        y=_finite_number(item["y"], f"{context}.y"),
        scale_x=scale_x,
        scale_y=scale_y,
        euler_angle=euler_angle,
    )


def _parse_atlases(values: Sequence[Mapping[str, object]]) -> tuple[_Atlas, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise _error("atlases must be a JSON array")
    if not values:
        raise _error("at least one atlas is required")

    result: list[_Atlas] = []
    for atlas_index, raw_atlas in enumerate(values):
        context = f"atlases[{atlas_index}]"
        item = _require_mapping(raw_atlas, context)
        _strict_keys(
            item,
            required={
                "name",
                "width",
                "height",
                "image_path",
                "image_file_size",
                "guid_uuid",
                "placements",
            },
            optional=set(),
            context=context,
        )
        image_path = _string(item["image_path"], f"{context}.image_path")
        posix_path = PurePosixPath(image_path)
        if (
            posix_path.name != image_path
            or image_path in {".", ".."}
            or not image_path.lower().endswith(".png")
        ):
            raise _error(
                f"{context}.image_path must be a flat PNG member name"
            )
        raw_placements = item["placements"]
        if (
            isinstance(raw_placements, (str, bytes))
            or not isinstance(raw_placements, Sequence)
            or not raw_placements
        ):
            raise _error(f"{context}.placements must be a non-empty JSON array")
        placements = tuple(
            _parse_placement(raw, f"{context}.placements[{placement_index}]")
            for placement_index, raw in enumerate(raw_placements)
        )
        result.append(
            _Atlas(
                name=_string(item["name"], f"{context}.name"),
                width=_positive_int(
                    item["width"], f"{context}.width", maximum=16_384
                ),
                height=_positive_int(
                    item["height"], f"{context}.height", maximum=16_384
                ),
                image_path=image_path,
                image_file_size=_positive_int(
                    item["image_file_size"],
                    f"{context}.image_file_size",
                    maximum=2**31 - 1,
                ),
                guid_uuid=_canonical_uuid(
                    item["guid_uuid"], f"{context}.guid_uuid"
                ),
                placements=placements,
            )
        )

    if len({atlas.name for atlas in result}) != len(result):
        raise _error("atlas names must be unique")
    if len({atlas.image_path for atlas in result}) != len(result):
        raise _error("atlas image paths must be unique")
    if len({atlas.guid_uuid for atlas in result}) != len(result):
        raise _error("atlas GUIDs must be unique")
    all_guids = [
        placement.model_image_guid
        for atlas in result
        for placement in atlas.placements
    ]
    if len(set(all_guids)) != len(all_guids):
        raise _error("each model image GUID must occur in exactly one placement")
    return tuple(result)


def _format_float(value: float) -> str:
    rendered = repr(value)
    return rendered if "." in rendered or "e" in rendered.lower() else rendered + ".0"


def _newline(xml: str) -> str:
    if "\r\n" in xml:
        if xml.count("\n") != xml.count("\r\n"):
            raise _error("main.xml has mixed newline conventions")
        return "\r\n"
    if "\r" in xml:
        raise _error("main.xml uses unsupported bare CR newlines")
    return "\n"


def _replace_once(xml: str, old: str, new: str, context: str) -> str:
    count = xml.count(old)
    if count != 1:
        raise _error(f"expected one {context}, found {count}")
    return xml.replace(old, new, 1)


def _insert_line_after(xml: str, anchor: str, line: str, newline: str) -> str:
    if line in xml:
        raise _error(f"processing instruction already exists: {line}")
    return _replace_once(xml, anchor + newline, anchor + newline + line + newline, anchor)


def _insert_line_before(xml: str, anchor: str, line: str, newline: str) -> str:
    if line in xml:
        raise _error(f"processing instruction already exists: {line}")
    return _replace_once(xml, anchor + newline, line + newline + anchor + newline, anchor)


def _add_processing_instructions(xml: str, newline: str) -> str:
    xml = _insert_line_after(
        xml,
        "<?version CModelImage:3?>",
        "<?version com.live2d.cubism.doc.model.texture.textureAtlas.ModelImageEntry:2?>",
        newline,
    )
    xml = _insert_line_after(
        xml,
        "<?import com.live2d.cubism.doc.model.extension.textureInput.CTextureInput_ModelImage?>",
        "<?import com.live2d.cubism.doc.model.extension.textureInput.CTextureInput_TextureAtlasRegion?>",
        newline,
    )
    xml = _insert_line_after(
        xml,
        "<?import com.live2d.cubism.doc.model.texture.modelImage.CModelImageGroup?>",
        "<?import com.live2d.cubism.doc.model.texture.textureAtlas.CTextureAtlas?>",
        newline,
    )
    xml = _insert_line_after(
        xml,
        "<?import com.live2d.cubism.doc.model.texture.textureAtlas.CTextureAtlas?>",
        "<?import com.live2d.cubism.doc.model.texture.textureAtlas.CTextureAtlas$ModelImageEntry?>",
        newline,
    )
    xml = _insert_line_before(
        xml,
        "<?import com.live2d.graphics3d.editableMesh.GEditableMesh2?>",
        "<?import com.live2d.graphics3d.component.GTransform2?>",
        newline,
    )
    xml = _insert_line_before(
        xml,
        "<?import com.live2d.type.CAffine?>",
        "<?import com.live2d.graphics3d.type.GVector2?>",
        newline,
    )
    return _insert_line_after(
        xml,
        "<?import com.live2d.type.CSize?>",
        "<?import com.live2d.type.CTextureAtlasGuid?>",
        newline,
    )


def _model_image_state(
    xml: str,
) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    uuid_by_ref: dict[str, str] = {}
    ref_by_uuid: dict[str, str] = {}
    for match in _GUID_DEFINITION_RE.finditer(xml):
        guid_uuid = _canonical_uuid(match.group("uuid"), "CModelImageGuid.uuid")
        guid_ref = match.group("ref")
        if guid_ref in uuid_by_ref or guid_uuid in ref_by_uuid:
            raise _error("duplicate CModelImageGuid shared definition")
        uuid_by_ref[guid_ref] = guid_uuid
        ref_by_uuid[guid_uuid] = guid_ref

    blocks = _MODEL_IMAGE_BLOCK_RE.findall(xml)
    transforms_by_uuid: dict[str, str] = {}
    for block_index, block in enumerate(blocks):
        guid_matches = re.findall(
            r"<CModelImageGuid\s+xs\.n=\"guid\"\s+xs\.ref=\"(#[0-9]+)\"\s*/>",
            block,
        )
        transform_matches = re.findall(
            r"<CAffine\s+xs\.n=\"_materialLocalToCanvasTransform\"[^>]*/>",
            block,
        )
        if len(guid_matches) != 1 or len(transform_matches) != 1:
            raise _error(
                f"CModelImage[{block_index}] lacks one GUID ref or canvas affine"
            )
        guid_ref = guid_matches[0]
        if guid_ref not in uuid_by_ref:
            raise _error(f"CModelImage[{block_index}] uses unknown GUID ref {guid_ref}")
        guid_uuid = uuid_by_ref[guid_ref]
        if guid_uuid in transforms_by_uuid:
            raise _error(f"duplicate CModelImage for GUID {guid_uuid}")
        transforms_by_uuid[guid_uuid] = transform_matches[0]

    model_input_guid_by_ref: dict[str, str] = {}
    for match in _MODEL_INPUT_BLOCK_RE.finditer(xml):
        block = match.group(0)
        guid_matches = re.findall(
            r"<CModelImageGuid\s+xs\.n=\"_modelImageGuid\"\s+"
            r"xs\.ref=\"(#[0-9]+)\"\s*/>",
            block,
        )
        if len(guid_matches) != 1:
            raise _error(
                f"texture input {match.group('ref')} lacks exactly one model GUID"
            )
        guid_ref = guid_matches[0]
        if guid_ref not in uuid_by_ref:
            raise _error(f"texture input uses unknown model GUID ref {guid_ref}")
        model_input_guid_by_ref[match.group("ref")] = uuid_by_ref[guid_ref]

    group_count_matches = re.findall(
        r"<carray_list\s+xs\.n=\"_modelImages\"\s+count=\"([0-9]+)\">",
        xml,
    )
    if group_count_matches != [str(len(blocks))]:
        raise _error("_modelImages count does not match serialized CModelImage blocks")
    return transforms_by_uuid, model_input_guid_by_ref, ref_by_uuid


def _preservation_snapshot(xml: str) -> dict[str, tuple[str, ...]]:
    patterns = {
        "currentTextureInputData": (
            r"<CTextureInput_ModelImage\s+xs\.n=\"currentTextureInputData\"[^>]*/>"
        ),
        "TextureState": r"<TextureState\s+[^>]*/>",
        "GTexture2D": r"<GTexture2D\s+xs\.id=\"#[0-9]+\"[^>]*>.*?</GTexture2D>",
        "uvs": r"<float-array\s+xs\.n=\"uvs\"[^>]*>.*?</float-array>",
    }
    return {
        name: tuple(re.findall(pattern, xml, re.DOTALL))
        for name, pattern in patterns.items()
    }


def _allocate_ids(xml: str, atlas_count: int) -> tuple[_AtlasIds, ...]:
    object_ids = [int(value) for value in re.findall(r"xs\.id=\"#([0-9]+)\"", xml)]
    object_indices = [int(value) for value in re.findall(r"xs\.idx=\"([0-9]+)\"", xml)]
    if not object_ids or not object_indices:
        raise _error("main.xml has no shared object IDs or indices")
    next_id = max(object_ids) + 1
    next_idx = max(object_indices) + 1
    result: list[_AtlasIds] = []
    for _ in range(atlas_count):
        result.append(
            _AtlasIds(
                atlas_ref=f"#{next_id}",
                image_ref=f"#{next_id + 1}",
                guid_ref=f"#{next_id + 2}",
                atlas_idx=next_idx,
                image_idx=next_idx + 1,
                guid_idx=next_idx + 2,
            )
        )
        next_id += 3
        next_idx += 3
    return tuple(result)


def _canvas_affine(
    source_affine: str,
    serialized_name: str,
    placement: _Placement,
) -> str:
    marker = 'xs.n="_materialLocalToCanvasTransform"'
    if source_affine.count(marker) != 1:
        raise _error("invalid model-image canvas affine")

    def attribute(name: str) -> float:
        matches = re.findall(rf'\b{name}="([^"]+)"', source_affine)
        if len(matches) != 1:
            raise _error(f"invalid model-image canvas affine {name}")
        try:
            value = float(matches[0])
        except ValueError as exc:
            raise _error(f"invalid model-image canvas affine {name}") from exc
        if not math.isfinite(value):
            raise _error(f"non-finite model-image canvas affine {name}")
        return 0.0 if value == 0.0 else value

    # Cubism stores materialLocalToAtlas as a translation for this layout.
    # The atlas-to-canvas affine therefore satisfies A = B o T(x, y).
    m00 = attribute("m00")
    m01 = attribute("m01")
    m02 = attribute("m02")
    m10 = attribute("m10")
    m11 = attribute("m11")
    m12 = attribute("m12")
    atlas_m02 = m02 - m00 * placement.x - m01 * placement.y
    atlas_m12 = m12 - m10 * placement.x - m11 * placement.y
    result = source_affine.replace(marker, f'xs.n="{serialized_name}"', 1)
    result = re.sub(
        r'\bm02="[^"]+"',
        f'm02="{_format_float(atlas_m02)}"',
        result,
        count=1,
    )
    result = re.sub(
        r'\bm12="[^"]+"',
        f'm12="{_format_float(atlas_m12)}"',
        result,
        count=1,
    )
    return result


def _atlas_shared_object(
    atlas: _Atlas,
    ids: _AtlasIds,
    transform_by_uuid: Mapping[str, str],
    model_guid_ref_by_uuid: Mapping[str, str],
    newline: str,
) -> str:
    lines = [
        f'<CTextureAtlas xs.id="{ids.atlas_ref}" xs.idx="{ids.atlas_idx}">',
        f'<s xs.n="name">{xml_escape(atlas.name)}</s>',
        f'<i xs.n="width">{atlas.width}</i>',
        f'<i xs.n="height">{atlas.height}</i>',
        f'<CImageResource xs.n="cachedAtlasImage" xs.ref="{ids.image_ref}" />',
        '<b xs.n="lockCachedAtlasImage">false</b>',
        f'<CTextureAtlasGuid xs.n="guid" xs.ref="{ids.guid_ref}" />',
        f'<carray_list xs.n="modelImages" count="{len(atlas.placements)}">',
    ]
    for placement in atlas.placements:
        model_guid_ref = model_guid_ref_by_uuid[placement.model_image_guid]
        canvas_affine = _canvas_affine(
            transform_by_uuid[placement.model_image_guid],
            "atlasLocalToCanvasTransform",
            placement,
        )
        lines.extend(
            [
                "<ModelImageEntry>",
                f'<CTextureAtlas xs.n="atlas" xs.ref="{ids.atlas_ref}" />',
                (
                    '<CModelImageGuid xs.n="modelImageGuid" '
                    f'xs.ref="{model_guid_ref}" />'
                ),
                canvas_affine,
                '<GTransform2 xs.n="materialLocalToAtlasTransform">',
                '<GVector2 xs.n="position">',
                f'<f xs.n="x">{_format_float(placement.x)}</f>',
                f'<f xs.n="y">{_format_float(placement.y)}</f>',
                "</GVector2>",
                '<GVector2 xs.n="scale">',
                f'<f xs.n="x">{_format_float(placement.scale_x)}</f>',
                f'<f xs.n="y">{_format_float(placement.scale_y)}</f>',
                "</GVector2>",
                (
                    '<f xs.n="eulerAngle">'
                    f'{_format_float(placement.euler_angle)}</f>'
                ),
                "</GTransform2>",
                "</ModelImageEntry>",
            ]
        )
    lines.extend(
        [
            "</carray_list>",
            '<CCachedImageManager xs.n="cachedImageManager">',
            '<CachedImageType xs.n="defaultCacheType" v="SCALE_1" />',
            f'<CImageResource xs.n="rawImage" xs.ref="{ids.image_ref}" />',
            '<array_list xs.n="cachedImages" count="0" />',
            '<i xs.n="requiredMipmapLevel">64</i>',
            "</CCachedImageManager>",
            "</CTextureAtlas>",
            (
                f'<CImageResource width="{atlas.width}" height="{atlas.height}" '
                f'type="INT_ARGB" imageFileBuf_size="{atlas.image_file_size}" '
                f'previewFileBuf_size="0" xs.id="{ids.image_ref}" '
                f'xs.idx="{ids.image_idx}">'
            ),
            (
                f'<file xs.n="imageFileBuf" path="'
                f'{xml_escape(atlas.image_path)}" />'
            ),
            "</CImageResource>",
            (
                f'<CTextureAtlasGuid uuid="{atlas.guid_uuid}" '
                f'note="(no debug info)" xs.id="{ids.guid_ref}" '
                f'xs.idx="{ids.guid_idx}" />'
            ),
        ]
    )
    return newline.join(lines)


def _region(
    *,
    extension_ref: str,
    atlas_guid_ref: str,
    source_affine: str,
    placement: _Placement,
    newline: str,
) -> str:
    input_affine = _canvas_affine(
        source_affine,
        "inputImageLocalToCanvasTransform",
        placement,
    )
    return newline.join(
        [
            "<CTextureInput_TextureAtlasRegion>",
            '<ACTextureInput xs.n="super">',
            (
                '<CAffine xs.n="optionalTransformOnCanvas" m00="1.0" '
                'm01="0.0" m02="0.0" m10="0.0" m11="1.0" m12="0.0" />'
            ),
            f'<CTextureInputExtension xs.n="_owner" xs.ref="{extension_ref}" />',
            "</ACTextureInput>",
            (
                '<CTextureAtlasGuid xs.n="textureAtlasGuid" '
                f'xs.ref="{atlas_guid_ref}" />'
            ),
            input_affine,
            "</CTextureInput_TextureAtlasRegion>",
        ]
    )


def _patch_extensions(
    xml: str,
    *,
    placement_location: Mapping[str, tuple[str, _Placement]],
    transform_by_uuid: Mapping[str, str],
    model_input_guid_by_ref: Mapping[str, str],
    newline: str,
) -> tuple[str, set[str]]:
    patched_model_guids: set[str] = set()

    def replace_extension(match: re.Match[str]) -> str:
        block = match.group(0)
        extension_ref_match = re.match(
            r'<CTextureInputExtension\s+xs\.id="(#[0-9]+)"', block
        )
        if extension_ref_match is None:
            raise _error("texture-input extension lacks a shared ID")
        extension_ref = extension_ref_match.group(1)
        list_match = _TEXTURE_INPUT_LIST_RE.search(block)
        if list_match is None or list_match.group("count") != "1":
            raise _error(f"extension {extension_ref} is not an atlas-free input list")
        model_inputs = re.findall(
            r'<CTextureInput_ModelImage\s+xs\.ref="(#[0-9]+)"\s*/>',
            list_match.group("body"),
        )
        if len(model_inputs) != 1:
            raise _error(
                f"extension {extension_ref} must contain one model-image input"
            )
        model_input_ref = model_inputs[0]
        if model_input_ref not in model_input_guid_by_ref:
            raise _error(
                f"extension {extension_ref} uses unknown input {model_input_ref}"
            )
        model_guid = model_input_guid_by_ref[model_input_ref]
        if model_guid not in placement_location:
            raise _error(f"model image {model_guid} has no atlas placement")
        atlas_guid_ref, placement = placement_location[model_guid]
        if placement.model_image_guid != model_guid:
            raise _error("internal placement mapping mismatch")

        current_matches = re.findall(
            r'<CTextureInput_ModelImage\s+xs\.n="currentTextureInputData"\s+'
            r'xs\.ref="(#[0-9]+)"\s*/>',
            block,
        )
        if current_matches != [model_input_ref]:
            raise _error(
                f"extension {extension_ref} current texture input is not preserved"
            )
        region = _region(
            extension_ref=extension_ref,
            atlas_guid_ref=atlas_guid_ref,
            source_affine=transform_by_uuid[model_guid],
            placement=placement,
            newline=newline,
        )
        new_list = (
            list_match.group("open")
            + "2"
            + list_match.group("open_end")
            + list_match.group("body")
            + region
            + newline
            + list_match.group("close")
        )
        patched_model_guids.add(model_guid)
        return block[: list_match.start()] + new_list + block[list_match.end() :]

    patched, count = _EXTENSION_BLOCK_RE.subn(replace_extension, xml)
    if count == 0:
        raise _error("main.xml has no CTextureInputExtension definitions")
    return patched, patched_model_guids


def patch_texture_atlas_xml(
    main_xml: bytes,
    atlases: Sequence[Mapping[str, object]],
    *,
    expected_model_image_count: int = 58,
) -> bytes:
    """Return ``main.xml`` patched with native Cubism 5.2 atlas objects.

    ``atlases`` is deliberately JSON-serializable.  Each atlas mapping has the
    required keys ``name``, ``width``, ``height``, ``image_path``,
    ``image_file_size``, ``guid_uuid``, and ``placements``.  Every placement
    requires ``model_image_guid``, ``x``, and ``y`` and optionally accepts
    ``scale_x``, ``scale_y``, and ``euler_angle`` (defaults: 1, 1, 0).

    Coordinates are written verbatim to Cubism's
    ``materialLocalToAtlasTransform``.  Canvas transforms are recovered from
    the corresponding existing ``CModelImage`` so callers cannot accidentally
    move an ArtMesh on the canvas.
    """

    if not isinstance(main_xml, bytes):
        raise _error("main_xml must be UTF-8 bytes")
    if not isinstance(expected_model_image_count, int) or isinstance(
        expected_model_image_count, bool
    ):
        raise _error("expected_model_image_count must be an integer")
    if expected_model_image_count <= 0:
        raise _error("expected_model_image_count must be positive")
    try:
        xml = main_xml.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _error("main_xml is not valid UTF-8") from exc
    if not xml.startswith('<?xml version="1.0" encoding="UTF-8"?>'):
        raise _error("unexpected main.xml declaration")
    newline = _newline(xml)
    parsed_atlases = _parse_atlases(atlases)

    forbidden_markers = (
        "<CTextureAtlas xs.id=",
        "<CTextureInput_TextureAtlasRegion>",
        "<?import com.live2d.cubism.doc.model.texture.textureAtlas.CTextureAtlas?>",
    )
    for marker in forbidden_markers:
        if marker in xml:
            raise _error("source main.xml already contains texture-atlas objects")

    preservation_before = _preservation_snapshot(xml)
    transform_by_uuid, model_input_guid_by_ref, model_guid_ref_by_uuid = (
        _model_image_state(xml)
    )
    model_guids = set(transform_by_uuid)
    if len(model_guids) != expected_model_image_count:
        raise _error(
            f"expected {expected_model_image_count} model images, "
            f"found {len(model_guids)}"
        )
    placement_guids = {
        placement.model_image_guid
        for atlas in parsed_atlases
        for placement in atlas.placements
    }
    missing = sorted(model_guids - placement_guids)
    unexpected = sorted(placement_guids - model_guids)
    if missing or unexpected:
        raise _error(
            "placement/model-image GUID mismatch: "
            f"missing={missing}, unexpected={unexpected}"
        )

    allocated_ids = _allocate_ids(xml, len(parsed_atlases))
    shared_blocks = [
        _atlas_shared_object(
            atlas,
            ids,
            transform_by_uuid,
            model_guid_ref_by_uuid,
            newline,
        )
        for atlas, ids in zip(parsed_atlases, allocated_ids, strict=True)
    ]
    first_art_mesh = re.search(r"<CArtMeshSource\s+xs\.id=\"#[0-9]+\"", xml)
    if first_art_mesh is None:
        raise _error("main.xml has no shared CArtMeshSource insertion anchor")
    shared_xml = newline.join(shared_blocks) + newline
    xml = xml[: first_art_mesh.start()] + shared_xml + xml[first_art_mesh.start() :]

    placement_location = {
        placement.model_image_guid: (ids.guid_ref, placement)
        for atlas, ids in zip(parsed_atlases, allocated_ids, strict=True)
        for placement in atlas.placements
    }
    xml, patched_guids = _patch_extensions(
        xml,
        placement_location=placement_location,
        transform_by_uuid=transform_by_uuid,
        model_input_guid_by_ref=model_input_guid_by_ref,
        newline=newline,
    )
    if patched_guids != model_guids:
        raise _error(
            "texture-input extensions do not cover all model images exactly"
        )

    atlas_refs = newline.join(
        f'<CTextureAtlas xs.ref="{ids.atlas_ref}" />' for ids in allocated_ids
    )
    xml = _replace_once(
        xml,
        '<carray_list xs.n="_textureAtlases" count="0" />',
        (
            f'<carray_list xs.n="_textureAtlases" '
            f'count="{len(allocated_ids)}">{newline}'
            f"{atlas_refs}{newline}</carray_list>"
        ),
        "atlas-free CTextureManager._textureAtlases list",
    )
    xml = _add_processing_instructions(xml, newline)

    preservation_after = _preservation_snapshot(xml)
    if preservation_after != preservation_before:
        changed = sorted(
            name
            for name in preservation_before
            if preservation_before[name] != preservation_after[name]
        )
        raise _error(f"protected XML structures changed: {', '.join(changed)}")

    if len(re.findall(r"<CTextureAtlas\s+xs\.id=", xml)) != len(parsed_atlases):
        raise _error("atlas shared-object postcondition failed")
    if len(re.findall(r"<ModelImageEntry>", xml)) != expected_model_image_count:
        raise _error("ModelImageEntry postcondition failed")
    if (
        len(re.findall(r"<CTextureInput_TextureAtlasRegion>", xml))
        != len(_EXTENSION_BLOCK_RE.findall(xml))
    ):
        raise _error("texture-atlas region postcondition failed")
    if xml.count('xs.n="_textureAtlases"') != 1:
        raise _error("texture-atlas root list postcondition failed")

    encoded = xml.encode("utf-8")
    if encoded == main_xml:
        raise _error("atlas patch unexpectedly produced no XML changes")
    return encoded
