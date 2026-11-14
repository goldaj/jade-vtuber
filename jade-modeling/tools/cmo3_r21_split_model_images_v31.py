#!/usr/bin/env python3
"""Duplicate seven per-mesh images with correct canvas affines, without packing.

Experimental pre-atlas copy only. Existing PNGs, mesh geometry, UVs and poses
are unchanged. Each duplicate PNG is byte-identical to its original. A native
Cubism open/save and separate atlas preview are required before using it.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

import cmo3_caff_rebuild as caff
import cmo3_create_deformer_experiment as ex
import cmo3_r21_add_model_image as add_image
from cmo3_inventory import CaffArchive
from cmo3_r21_face_roots_to_head import one
from cmo3_r21_fullbody_first_assembly import SPECS
from cmo3_r21_restore_eye_r_finite import exclusive, model_from_bytes, raw_source, require, sha

SOURCE_SHA = '39C00ECC82468B70004590E6E8EC549C7C16150A03341A322CB5A223A7CEBA8C'
BODY_IMAGE = 'JAD_R21_LOWERBODY_PARTS_V3'
HAIR_IMAGE = 'JAD_R21_REAR_HAIR_UNDERPAINT_CANDIDATE'
TARGETS = [(name, BODY_IMAGE) for name, *_ in SPECS] + [
    ('JAD_R21_HAIR_SHOULDER_UNDERPAINT_L', HAIR_IMAGE),
    ('JAD_R21_HAIR_SHOULDER_UNDERPAINT_R', HAIR_IMAGE),
]


def serial(node):
    node.tail = None
    return ET.tostring(node, encoding='utf-8', short_empty_elements=True)


def one_named(node, tag, name):
    return ex._one_named(node, tag, name)


def idmap(root):
    return {node.get('xs.id'): node for node in root.iter() if node.get('xs.id')}


def array(node, name):
    child = next(n for n in node if n.tag == 'float-array' and n.get('xs.n') == name)
    return np.array([float(x) for x in child.text.split()], dtype=np.float64).reshape(-1, 2)


def mesh_image(root, mesh):
    ids = idmap(root)
    tex_ref = one_named(mesh, 'GTexture2D', 'texture').get('xs.ref')
    texture = ids[tex_ref]
    image_ref = one_named(texture, 'CImageResource', 'srcImageResource').get('xs.ref')
    resource = ids[image_ref]
    member = one_named(resource, 'file', 'imageFileBuf').get('path')
    extension_ref = next(n.get('xs.ref') for n in mesh.iter('CTextureInputExtension'))
    extension = ids[extension_ref]
    model_input_ref = one_named(extension, 'CTextureInput_ModelImage', 'currentTextureInputData').get('xs.ref')
    return texture, resource, member, extension_ref, model_input_ref


def build(source, output, audit):
    require(not output.exists() and not audit.exists(), 'Refusing overwrite')
    original = source.read_bytes()
    require(sha(original) == SOURCE_SHA, 'Requires exact v31 native checkpoint')
    original_model, original_xml = model_from_bytes(original)
    original_archive = CaffArchive.parse(original)
    expected_names = {name for name, _ in TARGETS}
    require(len(expected_names) == 7, 'Unexpected target count')
    current_data = original
    report = []
    for index, (name, template_name) in enumerate(TARGETS, 1):
        model, xml = model_from_bytes(current_data)
        obj = one(model, name, 'art-mesh')
        node = model.source(obj)
        texture, resource, member, _, input_ref = mesh_image(model.root, node)
        png = CaffArchive.parse(current_data).read_unique_path(member, 256 * 1024 * 1024)
        width, height = int(resource.get('width')), int(resource.get('height'))
        uv, points = array(node, 'uvs'), array(node, 'positions')
        require(len(uv) == len(points) and len(uv) >= 4, 'Unexpected source geometry')
        design = np.column_stack((uv[:, 0] * width, uv[:, 1] * height, np.ones(len(uv))))
        matrix, _, rank, _ = np.linalg.lstsq(design, points, rcond=None)
        require(rank == 3, 'Cannot solve unique pixel-to-canvas affine')
        max_error = float(np.max(np.abs(design @ matrix - points)))
        require(max_error < .001, f'{name} non-affine mapping; max error {max_error}')
        # Least-squares rounding removes harmless float32 noise from an exact
        # affine while preserving the computed mapping to sub-millipixel error.
        affine = tuple(float(v) for v in (matrix[0, 0], matrix[1, 0], matrix[2, 0],
                                          matrix[0, 1], matrix[1, 1], matrix[2, 1]))
        require(all(np.isfinite(affine)), 'Non-finite affine')
        image_name = f'JAD_R21_ATLAS_IMAGE_{index:02d}'
        member_name = f'jade_r21_atlas_image_{index:02d}_r01.png'
        require(not any(e.path == member_name for e in CaffArchive.parse(current_data).entries),
                'PNG member exists')
        updated_xml, info = add_image.add_model_image_xml(
            xml, png, image_name, member_name, material_to_canvas=affine,
            template_name=template_name,
        )
        # Retarget only this mesh and its independent model-image input.
        ids = idmap(ET.fromstring(updated_xml))
        old_mesh = raw_source(updated_xml, obj)
        mesh_node = ET.fromstring(old_mesh)
        one_named(mesh_node, 'GTexture2D', 'texture').set('xs.ref', info['texture_ref'])
        updated_xml = ex._replace_exact(updated_xml, old_mesh, serial(mesh_node), 1, name+' texture')
        input_node = ids[input_ref]
        old_input = ex._block_by_id(updated_xml, input_node.tag, input_ref)
        changed_input = ET.fromstring(old_input)
        one_named(changed_input, 'CModelImageGuid', '_modelImageGuid').set('xs.ref', info['model_image_guid_ref'])
        updated_xml = ex._replace_exact(updated_xml, old_input, serial(changed_input), 1, name+' model image')
        current_data = caff.rebuild_caff_with_png(
            current_data, png_path=member_name, png_bytes=png, replacement_main_xml=updated_xml,
        )
        check_model, _ = model_from_bytes(current_data)
        check = check_model.source(one(check_model, name, 'art-mesh'))
        require(np.array_equal(array(node, 'uvs'), array(check, 'uvs')), 'UVs changed')
        require(np.array_equal(array(node, 'positions'), array(check, 'positions')), 'Base positions changed')
        report.append({'mesh': name, 'new_image': image_name, 'new_member': member_name,
                       'source_member': member, 'png_sha256': sha(png), 'dimensions': [width, height],
                       'material_to_canvas': affine, 'affine_fit_max_error_px': max_error})

    final_model, final_xml = model_from_bytes(current_data)
    final_archive = CaffArchive.parse(current_data)
    require(len(final_model.objects) == len(original_model.objects), 'Object count changed')
    for obj in original_model.objects:
        if obj.name not in expected_names:
            require(raw_source(original_xml, obj) == raw_source(final_xml, obj),
                    'Unexpected object changed: '+obj.name)
    for entry in original_archive.entries:
        if entry.path != 'main.xml':
            require(original_archive.read_unique_path(entry.path, 256 * 1024 * 1024)
                    == final_archive.read_unique_path(entry.path, 256 * 1024 * 1024),
                    'Original archive member changed: '+entry.path)
    for rec in report:
        require(final_archive.read_unique_path(rec['new_member'], 256 * 1024 * 1024)
                == original_archive.read_unique_path(rec['source_member'], 256 * 1024 * 1024),
                'Duplicate raster differs')
    result = {'status': 'experimental_pre_atlas_requires_native_gate', 'source_sha256': SOURCE_SHA,
              'output_sha256': sha(current_data), 'images': report,
              'existing_rasters_unchanged': True, 'target_uv_and_positions_unchanged': True,
              'no_atlas_created': True,
              'limitations': ['Cubism rendering and atlas behavior untested',
                              'Full PNG duplicates may reduce automatic atlas resolution',
                              'Inherited image filter provenance must not be regenerated']}
    exclusive(output, current_data)
    exclusive(audit, (json.dumps(result, indent=2, ensure_ascii=False)+'\n').encode('utf-8'))
    print(json.dumps({'output': str(output), 'sha256': sha(current_data), 'status': result['status']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--audit', type=Path, required=True)
    args = parser.parse_args()
    build(args.source, args.output, args.audit)

