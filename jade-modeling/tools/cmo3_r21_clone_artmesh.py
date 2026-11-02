#!/usr/bin/env python3
"""Clone an r21 one-binding ArtMesh while sharing its embedded texture.

This is an in-memory helper, not a candidate writer. Allocate every clone's
``allocation_roles(root, source_node, name)`` in one call to
``cmo3_secondary_professional._allocate``; then call ``clone``. The returned
blocks begin with the editable CArtMeshSource. The caller must append all
blocks and register the new source/Part child using the r16 helpers.

``set_mask`` writes the CDrawableGuid clip-list representation inferred from
the native r21 schema. Native Editor/save/export validation is still required;
this helper does not assert the rendering behavior of zero-opacity masks.
"""
from __future__ import annotations

import re
import uuid
import xml.etree.ElementTree as ET
from typing import Any, Mapping

import cmo3_hair_art_partition_r16 as partition


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _role(name: str, suffix: str) -> str:
    return f"clone:{name}:{suffix}"


def _uuid(source_sha: str, role: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"jade-cmo3-r21-clone:{source_sha}:{role}"))


def _layout(root: Any, source: Any) -> dict[str, Any]:
    """Resolve only dependencies that need a new identity for this clone."""
    _require(source.tag == "CArtMeshSource", "source must be a CArtMeshSource")
    shared = root.find("shared")
    _require(shared is not None, "shared section is missing")
    ids = {node.get("xs.id"): node for node in shared if node.get("xs.id")}
    label = str(source.get("xs.id"))
    _require(label in ids, "source must be an existing shared ArtMesh")
    desc = lambda tag, name: partition._descendant(source, tag, name, label)
    grid_ref = desc("KeyformGridSource", "keyformGridSource").get("xs.ref")
    _require(grid_ref in ids, "clone requires a shared keyform grid")
    grid = ids[grid_ref]
    binding_list = partition._direct(grid, "array_list", "keyformBindings", label)
    binding_refs = [node.get("xs.ref") for node in binding_list]
    _require(len(binding_refs) == 1, "clone requires exactly one binding")
    forms = partition._direct(source, "carray_list", "keyforms", label)
    form_refs = [partition._descendant(form, "CFormGuid", "guid", label).get("xs.ref") for form in forms]
    _require(form_refs and len(form_refs) == len(set(form_refs)), "form GUIDs must be nonempty and unique")
    grid_forms = partition._direct(grid, "array_list", "keyformsOnGrid", label)
    grid_form_refs = [partition._descendant(form, "CFormGuid", "keyformGuid", label).get("xs.ref") for form in grid_forms]
    _require(len(grid_form_refs) == len(form_refs) and set(grid_form_refs) == set(form_refs), "grid/forms differ")
    extension_list = desc("carray_list", "_extensions")
    extensions = [node.get("xs.ref") for node in extension_list if node.tag == "CTextureInputExtension"]
    _require(len(extensions) == 1 and extensions[0] in ids, "expected one shared texture extension")
    extension_ref = extensions[0]
    extension = ids[extension_ref]
    input_list = partition._direct(extension, "carray_list", "_textureInputs", label)
    _require(len(input_list) == 1 and input_list[0].tag == "CTextureInput_ModelImage", "clone supports MODEL_IMAGE input without atlas entries")
    model_input_ref = input_list[0].get("xs.ref")
    input_refs = {node.get("xs.ref") for node in extension.iter("CTextureInput_ModelImage")}
    _require(input_refs == {model_input_ref}, "texture extension has differing model inputs")
    drawable_ref = desc("CDrawableGuid", "guid").get("xs.ref")
    owned = {"source": label, "grid": grid_ref, "drawable-guid": drawable_ref,
             "texture-extension": extension_ref, "model-input": model_input_ref,
             **{f"binding-{i}": ref for i, ref in enumerate(binding_refs)},
             **{f"form-guid-{i}": ref for i, ref in enumerate(form_refs)}}
    for suffix, ref in owned.items():
        _require(ref in ids, f"unresolved clone dependency {suffix}: {ref}")
    _require(len(set(owned.values())) == len(owned), "owned dependency references overlap")
    return {"ids": ids, "owned": owned, "binding_refs": binding_refs,
            "form_refs": form_refs, "texture_ref": desc("GTexture2D", "texture").get("xs.ref"),
            "part_ref": desc("CPartGuid", "parentGuid").get("xs.ref"),
            "parent_deformer_ref": desc("CDeformerGuid", "targetDeformerGuid").get("xs.ref")}


def allocation_roles(root: Any, source_node: Any, name: str) -> list[str]:
    """Return ordered allocation roles; concatenate these for multiple clones."""
    _require(bool(name.strip()), "clone name is empty")
    layout = _layout(root, source_node)
    return [_role(name, suffix) for suffix in layout["owned"]]


def clone(root: Any, source_node: Any, name: str, source_sha: str,
          slots: Mapping[str, tuple[str, int]]) -> tuple[list[bytes], dict[str, Any]]:
    """Return identity-independent shared blocks, preserving geometry and pixels.

    Supports the native r21 eleven-form blink grid and any other nonempty
    one-binding grid with MODEL_IMAGE texture input. Neither root nor source
    is mutated. Return ``info`` is JSON-compatible. Modify ``blocks[0]`` after
    parsing it as XML to change geometry, opacities, or clipping.
    """
    _require(bool(name.strip()), "clone name is empty")
    _require(re.fullmatch(r"[0-9a-fA-F]{64}", source_sha) is not None, "source_sha must be SHA-256")
    existing_names = [node.text for node in root.iter("s") if node.get("xs.n") == "localName"]
    _require(name not in existing_names, "clone localName already exists")
    existing_ids = [node.get("idstr") for node in root.iter("CDrawableId")]
    _require(name not in existing_ids, "clone drawable ID already exists")
    layout = _layout(root, source_node)
    ids, owned = layout["ids"], layout["owned"]
    required_roles = [_role(name, suffix) for suffix in owned]
    _require(all(role in slots for role in required_roles), "clone allocation roles missing")
    allocated = [slots[role] for role in required_roles]
    _require(len({ref for ref, _ in allocated}) == len(allocated), "allocated references collide")
    _require(len({idx for _, idx in allocated}) == len(allocated), "allocated indices collide")
    existing_indices = {int(node.get("xs.idx")) for node in ids.values()}
    for ref, idx in allocated:
        _require(re.fullmatch(r"#[0-9]+", ref) is not None, f"invalid allocated reference: {ref}")
        _require(ref not in ids and idx not in existing_indices, "allocated identity already exists")
    replacements = {old_ref: slots[_role(name, suffix)][0] for suffix, old_ref in owned.items()}
    nodes = {}
    for suffix, old_ref in owned.items():
        ref, idx = slots[_role(name, suffix)]
        template = source_node if suffix == "source" else ids[old_ref]
        node = partition._clone_shared_node(template, ref=ref, idx=idx, replacements=replacements)
        # Includes form/drawable GUIDs, editable-mesh GUIDs and extensions.
        for number, guid in enumerate(child for child in node.iter() if child.get("uuid") is not None):
            guid.set("uuid", _uuid(source_sha, _role(name, f"{suffix}:uuid:{number}")))
        nodes[suffix] = node
    source = nodes["source"]
    partition._descendant(source, "s", "localName", name).text = name
    partition._descendant(source, "CDrawableId", "id", name).set("idstr", name)
    nodes["drawable-guid"].set("note", name)
    _require(partition._descendant(source, "GTexture2D", "texture", name).get("xs.ref") == layout["texture_ref"], "shared texture changed")
    for node in nodes.values():
        _require(not any(child.get("xs.ref") in replacements for child in node.iter()), "old owned reference remained in clone")
    existing_uuids = {node.get("uuid") for node in root.iter() if node.get("uuid") is not None}
    clone_uuids = [guid.get("uuid") for node in nodes.values() for guid in node.iter() if guid.get("uuid") is not None]
    _require(len(set(clone_uuids)) == len(clone_uuids) and not existing_uuids.intersection(clone_uuids), "clone UUID collision")
    info = {"name": name, "source_ref": replacements[owned["source"]],
            "drawable_guid_ref": replacements[owned["drawable-guid"]],
            "grid_ref": replacements[owned["grid"]],
            "texture_extension_ref": replacements[owned["texture-extension"]],
            "model_input_ref": replacements[owned["model-input"]],
            "binding_refs": [replacements[ref] for ref in layout["binding_refs"]],
            "form_guid_refs": [replacements[ref] for ref in layout["form_refs"]],
            "form_count": len(layout["form_refs"]), "shared_texture_ref": layout["texture_ref"],
            "part_guid_ref": layout["part_ref"], "parent_deformer_ref": layout["parent_deformer_ref"],
            "block_roles": list(nodes), "allocation_roles": required_roles}
    return [partition._serialize(node) for node in nodes.values()], info


def set_mask(source: Any, drawable_ref: str, inverted: bool = False) -> Any:
    """Mutate one ArtMesh to clip against a drawable GUID; return the source.

    ``drawable_ref`` must be the mask's shared CDrawableGuid reference, not its
    CArtMeshSource reference. The caller resolves/validates that reference in
    the assembled root and confirms clipping behavior in native Cubism.
    """
    _require(source.tag == "CArtMeshSource", "mask target must be a CArtMeshSource")
    _require(re.fullmatch(r"#[0-9]+", drawable_ref) is not None, "invalid drawable reference")
    _require(isinstance(inverted, bool), "inverted must be boolean")
    own_guid = partition._descendant(source, "CDrawableGuid", "guid", "mask target").get("xs.ref")
    _require(drawable_ref != own_guid, "ArtMesh cannot clip against itself")
    drawable = partition._direct(source, "ACDrawableSource", "super", "mask target")
    clip_list = partition._direct(drawable, "carray_list", "clipGuidList", "mask target")
    for child in list(clip_list):
        clip_list.remove(child)
    clip_list.text = "\n"
    clip_list.set("count", "1")
    ET.SubElement(clip_list, "CDrawableGuid", {"xs.ref": drawable_ref}).tail = "\n"
    partition._direct(drawable, "b", "invertClippingMask", "mask target").text = "true" if inverted else "false"
    return source
