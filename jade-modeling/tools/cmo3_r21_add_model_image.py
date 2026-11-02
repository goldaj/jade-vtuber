#!/usr/bin/env python3
"""Add an unchanged PNG as one r21 ModelImage, entirely in memory.

The source ModelImage, CImageResource and GTexture2D templates are resolved
from the supplied XML, never from pinned r19 references. No PNG is written,
painted, resized or re-encoded. This helper does not create an ArtMesh, pack
an atlas or write a CAFF/checkpoint.

Allocate ``allocation_roles(name)`` together with the caller's mesh roles,
then pass those slots to ``add_model_image`` (or let it allocate itself).
``add_model_image_xml`` additionally preserves every original XML block
except the affected ModelImageGroup and appends the three shared blocks.

Native QA remains required: the existing PSD input-filter provenance and
small icon are retained from the template. The cached raster/texture is new;
reimporting or regenerating the old PSD is NOT supported by this operation.
"""
from __future__ import annotations

import copy
import hashlib
import io
import math
import re
import uuid
import xml.etree.ElementTree as ET
from typing import Any, Mapping, Sequence

from PIL import Image


IDENTITY = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0)
AFFINE_KEYS = ("m00", "m01", "m02", "m10", "m11", "m12")
SUFFIXES = ("model-image-guid", "image-resource", "texture")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _one(parent: ET.Element, tag: str, name: str) -> ET.Element:
    nodes = [n for n in parent.iter(tag) if n.get("xs.n") == name]
    _require(len(nodes) == 1, f"expected one {tag}/{name}; found {len(nodes)}")
    return nodes[0]


def _serialize(node: ET.Element) -> bytes:
    result = copy.deepcopy(node)
    result.tail = None
    return ET.tostring(result, encoding="utf-8", short_empty_elements=True)


def allocation_roles(name: str) -> list[str]:
    """Three unique roles, compatible with secondary._allocate(root, roles)."""
    _require(isinstance(name, str) and bool(name.strip()), "image name is empty")
    return [f"model-image:{name}:{suffix}" for suffix in SUFFIXES]


def _layout(root: ET.Element, template_name: str | None) -> dict[str, Any]:
    shared = root.find("shared")
    _require(shared is not None, "shared section is missing")
    nodes = [n for n in shared if n.get("xs.id") is not None]
    ids = {n.get("xs.id"): n for n in nodes}
    _require(len(ids) == len(nodes), "existing shared IDs collide")
    candidates = []
    for group in shared.findall("CModelImageGroup"):
        lists = [n for n in group if n.tag == "carray_list" and n.get("xs.n") == "_modelImages"]
        if not lists:
            continue
        _require(len(lists) == 1, "ambiguous model-image list")
        images = lists[0]
        _require(images.get("count") == str(len(images)), "model-image list count differs")
        for model_image in images:
            name = _one(model_image, "s", "name").text
            if template_name is not None and name != template_name:
                continue
            guid_ref = _one(model_image, "CModelImageGuid", "guid").get("xs.ref")
            resources = {n.get("xs.ref") for n in model_image.iter("CImageResource")}
            # r21 has one shared raw/cached resource per imported layer.
            if len(resources) != 1:
                continue
            resource_ref = next(iter(resources))
            if guid_ref not in ids or resource_ref not in ids:
                continue
            if ids[guid_ref].tag != "CModelImageGuid" or ids[resource_ref].tag != "CImageResource":
                continue
            textures = [n for n in shared.findall("GTexture2D")
                        if any(c.get("xs.n") == "srcImageResource" and c.get("xs.ref") == resource_ref
                               for c in n.iter("CImageResource"))]
            if not textures:
                continue
            preferred = [n for n in textures if _one(n, "s", "name").text == name]
            texture = (preferred or textures)[0]
            candidates.append({"shared": shared, "ids": ids, "group": group, "images": images,
                               "model_image": model_image, "guid": ids[guid_ref],
                               "resource": ids[resource_ref], "texture": texture, "name": name})
    _require(bool(candidates), "no compatible native ModelImage/resource/texture template")
    if template_name is not None:
        _require(len(candidates) == 1, "requested ModelImage template is not unique")
    return candidates[0]


def _affine(node: ET.Element, values: Sequence[float]) -> None:
    node.attrib.update({key: str(float(value)) for key, value in zip(AFFINE_KEYS, values)})


def add_model_image(
    root: ET.Element,
    png_bytes: bytes,
    name: str,
    member_path: str,
    *,
    material_to_canvas: Sequence[float] = IDENTITY,
    slots: Mapping[str, tuple[str, int]] | None = None,
    template_name: str | None = None,
) -> tuple[ET.Element, dict[str, Any]]:
    """Return (new_root, info); original root and PNG bytes remain unchanged.

    ``material_to_canvas`` is (m00,m01,m02,m10,m11,m12), mapping PNG pixels
    into model canvas pixels. The returned root contains both the new image
    registration and its three shared blocks. ``info`` is JSON-compatible.
    CAFF-member name uniqueness must also be checked by the CAFF rebuilder.
    """
    roles = allocation_roles(name)
    _require(isinstance(png_bytes, bytes) and png_bytes.startswith(b"\x89PNG\r\n\x1a\n"), "PNG bytes required")
    _require(isinstance(member_path, str) and re.fullmatch(r"[A-Za-z0-9_.-]+\.png", member_path, re.I) is not None,
             "member_path must be a simple PNG member filename")
    _require(not any(n.get("path") == member_path for n in root.iter("file")), "PNG member path already referenced")
    _require(len(material_to_canvas) == 6 and all(math.isfinite(float(v)) for v in material_to_canvas),
             "material_to_canvas must contain six finite values")
    determinant = float(material_to_canvas[0]) * float(material_to_canvas[4]) - float(material_to_canvas[1]) * float(material_to_canvas[3])
    _require(math.isfinite(determinant) and abs(determinant) > 1e-12, "material_to_canvas is singular")
    with Image.open(io.BytesIO(png_bytes)) as raster:
        _require(raster.format == "PNG" and not getattr(raster, "is_animated", False), "single static PNG required")
        width, height = raster.size
        _require(0 < width <= 65535 and 0 < height <= 65535, "unsupported PNG dimensions")
        raster.verify()
    for old in root.iter("CModelImage"):
        _require(_one(old, "s", "name").text != name, "ModelImage name already exists")
    layout = _layout(root, template_name)
    ids = layout["ids"]
    _require(all(re.fullmatch(r"#[0-9]+", ref) for ref in ids), "invalid source shared ID")
    indices = [int(n.get("xs.idx", "-1")) for n in ids.values()]
    _require(all(i >= 0 for i in indices) and len(set(indices)) == len(indices), "invalid/colliding source indices")
    if slots is None:
        first_id = max(int(ref[1:]) for ref in ids) + 1
        first_index = (max(indices) // 100 + 1) * 100
        slots = {role: (f"#{first_id + offset}", first_index + offset * 100) for offset, role in enumerate(roles)}
    _require(all(role in slots for role in roles), "image allocation roles missing")
    assigned = [slots[role] for role in roles]
    _require(len({ref for ref, _ in assigned}) == 3 and len({idx for _, idx in assigned}) == 3,
             "allocated image identities collide")
    for ref, idx in assigned:
        _require(isinstance(ref, str) and re.fullmatch(r"#[0-9]+", ref) is not None, "invalid allocated reference")
        _require(isinstance(idx, int) and not isinstance(idx, bool) and idx >= 0, "invalid allocated index")
        _require(ref not in ids and idx not in indices, "allocated identity already exists")
    refs = dict(zip(SUFFIXES, (ref for ref, _ in assigned)))
    old_nodes = (layout["guid"], layout["resource"], layout["texture"])
    replacements = {node.get("xs.id"): ref for node, (ref, _) in zip(old_nodes, assigned)}
    seed = hashlib.sha256(png_bytes).hexdigest() + ":" + name + ":" + member_path
    blocks = []
    for suffix, original, (ref, idx) in zip(SUFFIXES, old_nodes, assigned):
        node = copy.deepcopy(original)
        node.set("xs.id", ref)
        node.set("xs.idx", str(idx))
        for child in node.iter():
            if child.get("xs.ref") in replacements:
                child.set("xs.ref", replacements[child.get("xs.ref")])
        for number, child in enumerate(n for n in node.iter() if n.get("uuid") is not None):
            child.set("uuid", str(uuid.uuid5(uuid.NAMESPACE_URL, f"jade-r21-model-image:{seed}:{suffix}:{number}")))
        blocks.append(node)
    guid, resource, texture = blocks
    guid.set("note", name)
    resource.attrib.update(width=str(width), height=str(height), imageFileBuf_size=str(len(png_bytes)), previewFileBuf_size="0")
    _one(resource, "file", "imageFileBuf").set("path", member_path)
    for child in list(resource):
        if child.get("xs.n") == "previewFileBuf":
            resource.remove(child)
    _one(texture, "s", "name").text = name
    _affine(_one(texture, "CAffine", "transformImageResource01toLogical01"), IDENTITY)
    model_image = copy.deepcopy(layout["model_image"])
    _require(not any(n.get("xs.id") is not None for n in model_image.iter()), "ModelImage owns unsupported inline shared identities")
    for child in model_image.iter():
        if child.get("xs.ref") in replacements:
            child.set("xs.ref", replacements[child.get("xs.ref")])
    _one(model_image, "s", "name").text = name
    _affine(_one(model_image, "CAffine", "_materialLocalToCanvasTransform"), material_to_canvas)
    for size in model_image.iter("CSize"):
        if size.get("xs.n") == "rawImageSize":
            size.attrib.update(width=str(width), height=str(height))
    _affine(_one(model_image, "CAffine", "transformRawImageToCachedImage"), IDENTITY)
    _one(model_image, "i", "reductionRatio").text = "1"
    _one(model_image, "b", "hasMargin").text = "false"
    _one(model_image, "b", "isSharedImage").text = "true"
    new_uuids = [n.get("uuid") for block in blocks for n in block.iter() if n.get("uuid") is not None]
    old_uuids = {n.get("uuid") for n in root.iter() if n.get("uuid") is not None}
    _require(len(set(new_uuids)) == len(new_uuids) and not old_uuids.intersection(new_uuids), "new UUID collision")
    result = copy.deepcopy(root)
    shared = result.find("shared")
    group = next(n for n in shared if n.get("xs.id") == layout["group"].get("xs.id"))
    images = _one(group, "carray_list", "_modelImages")
    images.append(model_image)
    images.set("count", str(len(images)))
    shared.extend(blocks)
    info = {"name": name, "member_path": member_path, "png_sha256": hashlib.sha256(png_bytes).hexdigest().upper(),
            "png_size_bytes": len(png_bytes), "width": width, "height": height,
            "model_image_guid_ref": refs["model-image-guid"], "image_resource_ref": refs["image-resource"],
            "texture_ref": refs["texture"], "model_image_guid_uuid": guid.get("uuid"),
            "model_image_group_ref": group.get("xs.id"), "new_shared_refs": [ref for ref, _ in assigned],
            "allocation_roles": roles, "template_name": layout["name"], "material_to_canvas": list(material_to_canvas),
            "source_filter_and_icon_retained": True, "png_reencoded": False,
            "warning": "Native open/save validation required; do not regenerate/reimport the retained source PSD filter."}
    return result, info


def add_model_image_xml(main_xml: bytes, png_bytes: bytes, name: str, member_path: str,
                        **kwargs: Any) -> tuple[bytes, dict[str, Any]]:
    """Byte-preserving XML wrapper around add_model_image; no CAFF writes.

    Return value can be passed directly as ``replacement_main_xml`` to
    ``cmo3_caff_rebuild.rebuild_caff_with_png``. Only the ModelImageGroup is
    replaced; all three newly allocated shared blocks are appended.
    """
    result, info = add_model_image(ET.fromstring(main_xml), png_bytes, name, member_path, **kwargs)
    shared = result.find("shared")
    by_ref = {n.get("xs.id"): n for n in shared if n.get("xs.id")}
    group_ref = info["model_image_group_ref"]
    pattern = re.compile(rb'<CModelImageGroup\b(?=[^>]*\bxs\.id="' + re.escape(group_ref.encode("ascii")) + rb'")[^>]*>.*?</CModelImageGroup>', re.DOTALL)
    matches = list(pattern.finditer(main_xml))
    _require(len(matches) == 1, "ModelImageGroup serialized block is ambiguous")
    match = matches[0]
    current = main_xml[:match.start()] + _serialize(by_ref[group_ref]) + main_xml[match.end():]
    _require(current.count(b"</shared>") == 1, "shared closing tag is ambiguous")
    additions = b"\r\n".join(_serialize(by_ref[ref]) for ref in info["new_shared_refs"])
    current = current.replace(b"</shared>", additions + b"\r\n</shared>", 1)
    ET.fromstring(current)
    return current, info
