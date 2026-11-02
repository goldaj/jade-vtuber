#!/usr/bin/env python3
"""Clone a static underpainting ArtMesh into an existing local deformer.

In-memory only. Allocate ``fullbody.role(name, key)`` for every key returned
by ``fullbody.clone_roles`` alongside the new ModelImage allocation roles.
The caller registers the returned source/Part child and writes a fresh CAFF.
"""
from __future__ import annotations

import hashlib
import math
import uuid
import xml.etree.ElementTree as ET

import cmo3_hair_art_partition_r16 as partition
from cmo3_r21_fullbody_first_assembly import clone_roles, role, named, direct, serialize
from cmo3_r21_iris_occlusion import replace_geometry, set_array
from cmo3_r21_restore_eye_r_finite import require


def clone_underpaint(root, template, name, slots, tex_info, canvas_positions,
                     local_positions, uvs, triangles, edges, parent_ref, draw=499):
    """Return ``(blocks, record)`` without changing the root or template.

    Original/editable geometry stays in canvas space; only the keyform uses
    the caller's compensated local coordinates. No ROOT lookup is performed.
    """
    ids = {node.get('xs.id'): node for node in root.find('shared') if node.get('xs.id')}
    require(parent_ref in ids and ids[parent_ref].tag == 'CDeformerGuid',
            'Underpaint parent must resolve to a shared deformer GUID')
    require(name and not any(node.text == name for node in root.iter('s')
                            if node.get('xs.n') == 'localName'), 'Mesh name exists or is empty')
    require(not any(node.get('idstr') == name for node in root.iter('CDrawableId')),
            'Mesh drawable ID exists')
    forms = direct(template, 'carray_list', 'keyforms')
    grid = named(template, 'KeyformGridSource', 'keyformGridSource')
    require(len(forms) == 1 and not grid.get('xs.ref'), 'Template must have one form and an inline grid')
    require(len(direct(grid, 'array_list', 'keyformBindings')) == 0,
            'Static underpaint must not inherit parameter bindings')
    coord_ref = named(forms[0], 'CoordType', 'coordType').get('xs.ref')
    require(coord_ref in ids and named(ids[coord_ref], 's', 'coordName').text == 'DeformerLocal',
            'Template must use DeformerLocal coordinates')
    canvas_positions, local_positions, uvs = map(tuple, (canvas_positions, local_positions, uvs))
    triangles, edges = tuple(triangles), tuple(edges)
    count = len(canvas_positions) // 2
    require(count >= 3 and len(canvas_positions) == count * 2
            and len(local_positions) == len(uvs) == len(canvas_positions), 'Geometry array sizes differ')
    require(all(math.isfinite(value) for values in (canvas_positions, local_positions, uvs)
                for value in values), 'Nonfinite underpaint coordinates')
    require(triangles and len(triangles) % 3 == 0 and len(edges) % 2 == 0,
            'Invalid triangle or edge array length')
    require(all(int(index) == index and 0 <= index < count for index in (*triangles, *edges)),
            'Mesh index is outside geometry')
    refs = clone_roles(root, template, name)
    require(all(role(name, key) in slots for key in refs), 'Clone allocation role missing')
    assigned = [slots[role(name, key)] for key in refs]
    require(len({ref for ref, _ in assigned}) == len(refs)
            and len({idx for _, idx in assigned}) == len(refs), 'Clone allocation collides')
    require(not set(ref for ref, _ in assigned).intersection(ids), 'Clone reference already exists')
    old_indices = {int(node.get('xs.idx')) for node in ids.values()}
    require(not set(idx for _, idx in assigned).intersection(old_indices), 'Clone index already exists')
    mapping = {ref: slots[role(name, key)][0] for key, ref in refs.items()}
    seed = hashlib.sha256(ET.tostring(template, encoding='utf-8')).hexdigest()
    nodes = {}
    for key, old_ref in refs.items():
        new_ref, index = slots[role(name, key)]
        node = partition._clone_shared_node(ids[old_ref], ref=new_ref, idx=index, replacements=mapping)
        for number, guid in enumerate(child for child in node.iter() if child.get('uuid') is not None):
            guid.set('uuid', str(uuid.uuid5(uuid.NAMESPACE_URL,
                     f'jade:r21:underpaint:{seed}:{name}:{key}:{number}')))
        nodes[key] = node
    source = nodes['source']
    named(source, 's', 'localName').text = name
    named(source, 'CDrawableId', 'id').set('idstr', name)
    nodes['drawable-guid'].set('note', name)
    named(source, 'CDeformerGuid', 'targetDeformerGuid').set('xs.ref', parent_ref)
    named(source, 'GTexture2D', 'texture').set('xs.ref', tex_info['texture_ref'])
    named(nodes['model-input'], 'CModelImageGuid', '_modelImageGuid').set('xs.ref', tex_info['model_image_guid_ref'])
    replace_geometry(source, canvas_positions, uvs, triangles, edges)
    form = direct(source, 'carray_list', 'keyforms')[0]
    set_array(direct(form, 'float-array', 'positions'), local_positions)
    require(named(form, 'CoordType', 'coordType').get('xs.ref') == coord_ref, 'Local CoordType changed')
    named(form, 'f', 'opacity').text = '1.0'
    named(form, 'i', 'drawOrder').text = str(int(draw))
    old_uuids = {node.get('uuid') for node in root.iter() if node.get('uuid') is not None}
    new_uuids = [child.get('uuid') for node in nodes.values() for child in node.iter()
                 if child.get('uuid') is not None]
    require(len(set(new_uuids)) == len(new_uuids) and not old_uuids.intersection(new_uuids),
            'Clone UUID collision')
    require(not any(child.get('xs.ref') in mapping for node in nodes.values() for child in node.iter()),
            'Original owned reference remains in clone')
    return [serialize(node) for node in nodes.values()], {
        'name': name, 'source_ref': mapping[refs['source']],
        'drawable_ref': mapping[refs['drawable-guid']],
        'part_ref': named(source, 'CPartGuid', 'parentGuid').get('xs.ref'),
        'parent_ref': parent_ref, 'coord_type_ref': coord_ref,
        'vertices': count, 'triangles': len(triangles) // 3, 'draw_order': int(draw),
        'bounds': [min(canvas_positions[::2]), min(canvas_positions[1::2]),
                   max(canvas_positions[::2]), max(canvas_positions[1::2])],
    }
