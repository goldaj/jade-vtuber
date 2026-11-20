#!/usr/bin/env python3
"""Prepare r21's used-image atlas, preserving native rig and source rasters.

Only the oversized master is cropped and remapped, without resampling. All
source archive payloads remain unchanged. Native Cubism/VTS validation is
still required; successful offline checks are NOT a visual validation.
"""
from __future__ import annotations

import argparse
import io
import json
import math
import re
import uuid
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image

import cmo3_caff_rebuild as caff
import cmo3_create_deformer_experiment as ex
import cmo3_reparent_preserve_canvas as canvas
import cmo3_r21_add_model_image as add_image
import cmo3_texture_atlas_pack as pack
import cmo3_texture_atlas_xml as native
from cmo3_inventory import CaffArchive
from cmo3_r21_restore_eye_r_finite import exclusive, require, sha
from cmo3_r21_split_model_images_v31 import array, idmap, mesh_image, one_named as named, serial

SOURCE_SHA = '0DF71AF75A6B8C55A1E3ADF6D53CBC6DB3F206EF704D5B079802C8D83D1B9920'
MASTER = 'JAD_R21_ORIGINAL_MASTER_FOR_TIPS'
PAGE = 4096
LIMIT = 256 * 1024 * 1024
KEYS = ('m00', 'm01', 'm02', 'm10', 'm11', 'm12')


def parse(data):
    archive = CaffArchive.parse(data)
    xml = archive.read_unique_path('main.xml', LIMIT)
    return archive, xml, ET.fromstring(xml)


def image_state(root):
    ids = idmap(root)
    def guid(node):
        return (ids[node.get('xs.ref')] if node.get('xs.ref') else node).get('uuid')
    images = {guid(named(n, 'CModelImageGuid', 'guid')): n for n in root.iter('CModelImage')}
    used = {}
    inputs = {}
    for mesh in root.iter('CArtMeshSource'):
        if not mesh.get('xs.id'):
            continue
        texture, resource, member, extension, inp = mesh_image(root, mesh)
        model_guid = guid(named(ids[inp], 'CModelImageGuid', '_modelImageGuid'))
        optional = named(ids[inp], 'CAffine', 'optionalTransformOnCanvas')
        require(tuple(float(optional.get(k)) for k in KEYS) == (1,0,0,0,1,0),
                'Nonidentity optional transform requires explicit atlas treatment')
        inputs[inp] = model_guid
        used.setdefault(model_guid, []).append((mesh, texture, resource, member, extension, inp))
    return ids, images, used, inputs


def crop_master(data):
    archive, xml, root = parse(data)
    ids, images, used, _ = image_state(root)
    key = next(k for k, im in images.items() if named(im, 's', 'name').text == MASTER)
    targets = used[key]
    require(len(targets) == 12, 'Expected twelve master-image meshes')
    resource = targets[0][2]
    width, height = int(resource.get('width')), int(resource.get('height'))
    points = []
    for mesh, texture, res, member, _, _ in targets:
        transform = named(texture, 'CAffine', 'transformImageResource01toLogical01')
        require(tuple(float(transform.get(k)) for k in KEYS) == (1, 0, 0, 0, 1, 0), 'Master requires identity logical transform')
        require(res.get('xs.id') == resource.get('xs.id'), 'Master sources disagree')
        points.append(array(mesh, 'uvs') * [width, height])
    all_points = np.concatenate(points)
    lo = np.maximum(np.floor(all_points.min(0)).astype(int) - 8, [0, 0])
    hi = np.minimum(np.ceil(all_points.max(0)).astype(int) + 8, [width, height])
    require(np.all(hi > lo), 'Invalid master crop')
    box = tuple(int(v) for v in (*lo, *hi))
    with Image.open(io.BytesIO(archive.read_unique_path(targets[0][3], LIMIT))) as source:
        require(source.mode == 'RGBA', 'Master must be RGBA')
        crop = source.crop(box)
        buffer = io.BytesIO()
        crop.save(buffer, format='PNG')
        png = buffer.getvalue()
        with Image.open(io.BytesIO(png)) as decoded:
            require(np.array_equal(np.asarray(crop), np.asarray(decoded)), 'Master crop pixel mismatch')
    original_affine = named(images[key], 'CAffine', '_materialLocalToCanvasTransform')
    a = np.array([float(original_affine.get(k)) for k in KEYS]).reshape(2, 3)
    a[:, 2] += a[:, :2] @ lo
    xml, info = add_image.add_model_image_xml(xml, png, 'JAD_R21_MASTER_USED_CROP',
        'jade_r21_master_used_crop.png', material_to_canvas=a.ravel(), template_name=MASTER)
    max_error = 0.0
    target_ids = []
    for mesh, _, _, _, _, inp in targets:
        old = ex._block_by_id(xml, 'CArtMeshSource', mesh.get('xs.id'))
        new = ET.fromstring(old)
        uv = (array(mesh, 'uvs') * [width, height] - lo) / (hi - lo)
        named(new, 'GTexture2D', 'texture').set('xs.ref', info['texture_ref'])
        named(new, 'float-array', 'uvs').text = ' '.join(canvas._format_float32(float(v)) for v in uv.ravel())
        restored = array(new, 'uvs') * (hi - lo) + lo
        max_error = max(max_error, float(np.max(np.abs(restored - array(mesh, 'uvs') * [width, height]))))
        require(np.array_equal(array(new, 'positions'), array(mesh, 'positions')), 'Position changed')
        xml = ex._replace_exact(xml, old, serial(new), 1, 'master mesh remap')
        old = ex._block_by_id(xml, 'CTextureInput_ModelImage', inp)
        new = ET.fromstring(old)
        named(new, 'CModelImageGuid', '_modelImageGuid').set('xs.ref', info['model_image_guid_ref'])
        xml = ex._replace_exact(xml, old, serial(new), 1, 'master input remap')
        target_ids.append(mesh.get('xs.id'))
    require(max_error < .001, 'Master crop exceeds UV error tolerance')
    data = caff.rebuild_caff_with_png(data, png_path='jade_r21_master_used_crop.png', png_bytes=png, replacement_main_xml=xml)
    return data, {'crop': box, 'mesh_ids': target_ids, 'max_uv_error_px': max_error, 'png_sha256': sha(png)}


def assets_for_used(data):
    archive, xml, root = parse(data)
    ids, images, used, inputs = image_state(root)
    assets = []
    transforms = {}
    guid_refs = {}
    bounds = {}
    for guid, meshes in used.items():
        im = images[guid]
        name = named(im, 's', 'name').text
        ref = named(im, 'CModelImageGuid', 'guid').get('xs.ref')
        require(ref in ids, 'Used ModelImage must have shared GUID')
        resource = meshes[0][2]
        width, height = int(resource.get('width')), int(resource.get('height'))
        require(named(im, 'CImageResource', '_filteredImage').get('xs.ref') == resource.get('xs.id'), 'Filtered/source image mismatch')
        footprint = []
        logical_sizes = set()
        for mesh, texture, res, _, _, _ in meshes:
            require(res.get('xs.id') == resource.get('xs.id'), 'Shared image resource mismatch')
            g = named(texture, 'CAffine', 'transformImageResource01toLogical01')
            require(all(abs(float(g.get(k))) < 1e-7 for k in ('m01', 'm02', 'm10', 'm12')), 'Unsupported logical transform')
            logical = np.array([width / float(g.get('m00')), height / float(g.get('m11'))])
            require(np.max(np.abs(logical - np.rint(logical))) < .001, 'Nonintegral logical dimensions')
            logical = np.rint(logical).astype(int)
            logical_sizes.add(tuple(int(v) for v in logical))
            footprint.append(array(mesh, 'uvs') * logical)
        require(len(logical_sizes) == 1, 'Inconsistent source logical dimensions')
        points = np.concatenate(footprint)
        lo = np.floor(np.minimum(points.min(0), [0, 0])).astype(int) - 8
        hi = np.ceil(np.maximum(points.max(0), [width, height])).astype(int) + 8
        a = named(im, 'CAffine', '_materialLocalToCanvasTransform')
        values = [float(a.get(k)) for k in KEYS]
        png = archive.read_unique_path(meshes[0][3], LIMIT)
        asset = pack.ModelImageAsset(name, ref, resource.get('xs.id'), meshes[0][3], png,
            width, height, int(hi[0]-lo[0]), int(hi[1]-lo[1]), *values)
        assets.append(asset)
        transforms[guid] = ET.tostring(a, encoding='unicode').strip()
        guid_refs[guid] = ref
        bounds[ref] = {'guid': guid, 'lo': lo.tolist(), 'hi': hi.tolist(), 'logical_size': list(next(iter(logical_sizes)))}
    return xml, root, assets, transforms, guid_refs, inputs, bounds


def pages_for(assets):
    pages = []
    for asset in sorted(assets, key=lambda a: (-a.logical_height, -a.logical_width, a.name)):
        require(asset.logical_width <= PAGE and asset.logical_height <= PAGE, 'Used image footprint exceeds page')
        for page in pages:
            try:
                pack.pack_model_images(page + [asset], atlas_size=PAGE, gutter=0)
                page.append(asset)
                break
            except pack.AtlasPackError:
                continue
        else:
            pages.append([asset])
    return [pack.pack_model_images(page, atlas_size=PAGE, gutter=0) for page in pages]


def atlas_xml(xml_bytes, specs, transforms, refs, inputs):
    xml = xml_bytes.decode('utf-8')
    require('<CTextureAtlas xs.id=' not in xml, 'Source already has atlas')
    before = native._preservation_snapshot(xml)
    atlases = native._parse_atlases(specs)
    allocated = native._allocate_ids(xml, len(atlases))
    # Earlier surgical patches retain their original line endings and add
    # ElementTree blocks with LF. Do not rewrite preserved source blocks.
    nl = '\r\n' if xml.splitlines(keepends=True)[0].endswith('\r\n') else '\n'
    blocks = nl.join(native._atlas_shared_object(a, i, transforms, refs, nl) for a, i in zip(atlases, allocated)) + nl
    anchor = re.search(r'<CArtMeshSource\s+xs.id="#[0-9]+"', xml)
    require(anchor is not None, 'Missing insertion anchor')
    xml = xml[:anchor.start()] + blocks + xml[anchor.start():]
    location = {p.model_image_guid: (i.guid_ref, p) for a, i in zip(atlases, allocated) for p in a.placements}
    xml, patched = native._patch_extensions(xml, placement_location=location, transform_by_uuid=transforms,
        model_input_guid_by_ref=inputs, newline=nl)
    require(patched == set(transforms), 'Used image coverage mismatch')
    atlas_refs = nl.join(f'<CTextureAtlas xs.ref="{i.atlas_ref}" />' for i in allocated)
    xml = native._replace_once(xml, '<carray_list xs.n="_textureAtlases" count="0" />',
        f'<carray_list xs.n="_textureAtlases" count="{len(atlases)}">{nl}{atlas_refs}{nl}</carray_list>', 'atlas list')
    xml = native._add_processing_instructions(xml, nl)
    require(native._preservation_snapshot(xml) == before, 'Atlas changed source UV/input/texture')
    ET.fromstring(xml)
    return xml.encode('utf-8')


def build(source, output, audit):
    require(not output.exists() and not audit.exists(), 'Refusing overwrite')
    data = source.read_bytes()
    require(sha(data) == SOURCE_SHA, 'Expected exact cropped working source')
    original, original_xml, original_root = parse(data)
    data, master_report = crop_master(data)
    xml, root, assets, transforms, refs, inputs, bounds = assets_for_used(data)
    pages = pages_for(assets)
    specs, members, report = [], [], []
    for index, placements in enumerate(pages):
        atlas = Image.new('RGBA', (PAGE, PAGE), (0, 0, 0, 0))
        entries, rows = [], []
        for placement in placements:
            asset = placement.asset
            b = bounds[asset.guid_ref]
            x, y = placement.x - b['lo'][0], placement.y - b['lo'][1]
            image = asset.image()
            atlas.paste(image, (x, y))
            require(np.array_equal(np.asarray(image), np.asarray(atlas.crop((x,y,x+image.width,y+image.height)))), 'Packed RGBA differs')
            entries.append({'model_image_guid': b['guid'], 'x': x, 'y': y})
            rows.append({'name': asset.name, 'source': asset.resource_path, 'guid': b['guid'],
                'source_size': [image.width,image.height], 'logical_size': b['logical_size'],
                'source_origin_in_atlas': [x,y], 'footprint': [placement.x,placement.y,asset.logical_width,asset.logical_height]})
        # Check the complete page, after every paste, so a later overwrite
        # cannot be hidden by an earlier successful local pixel comparison.
        for i, (placement, row) in enumerate(zip(placements, rows)):
            image = placement.asset.image()
            x, y = row['source_origin_in_atlas']
            require(np.array_equal(np.asarray(image), np.asarray(atlas.crop((x,y,x+image.width,y+image.height)))), 'Final atlas overwrote source RGBA')
            for other in placements[i+1:]:
                require(not pack._intersects(placement.padded_rect, other.padded_rect), 'Atlas UV footprints overlap')
        png = pack.encode_atlas_png(atlas)
        with Image.open(io.BytesIO(png)) as decoded:
            require(np.array_equal(np.asarray(atlas),np.asarray(decoded)), 'Atlas PNG roundtrip differs')
        member = f'jade_r21_atlas_page_{index:02d}.png'
        specs.append({'name': f'Jade r21 atlas {index+1}', 'width': PAGE, 'height': PAGE,
            'image_path': member, 'image_file_size': len(png),
            'guid_uuid': str(uuid.uuid5(uuid.NAMESPACE_URL, SOURCE_SHA+':'+member)), 'placements': entries})
        members.append(caff.RawMember(member, png))
        report.append({'page': index, 'png_sha256': sha(png), 'images': rows})
    updated = atlas_xml(xml, specs, transforms, refs, inputs)
    result = caff.rebuild_caff_with_raw_members(data, members=members, replacement_main_xml=updated)
    final, final_xml, final_root = parse(result)
    # All original resources and all rig sources survive unchanged. Only the
    # twelve master meshes may change their UV and texture resource reference.
    final_ids = idmap(final_root)
    all_ids = [node.get('xs.id') for node in final_root.iter() if node.get('xs.id')]
    require(len(all_ids) == len(set(all_ids)), 'Duplicate serialized object IDs')
    require(all(node.get('xs.ref') in final_ids for node in final_root.iter() if node.get('xs.ref')), 'Unresolved serialized reference')
    regions = list(final_root.iter('CTextureInput_TextureAtlasRegion'))
    require(len(regions) == len(inputs) == 78, 'Expected atlas regions for all 78 mesh inputs')
    for atlas in final_root.iter('CTextureAtlas'):
        if not atlas.get('xs.id'):
            continue
        for entry in atlas.iter('ModelImageEntry'):
            guid = final_ids[named(entry,'CModelImageGuid','modelImageGuid').get('xs.ref')].get('uuid')
            source_affine = ET.fromstring(transforms[guid])
            expected = np.array([float(source_affine.get(k)) for k in KEYS]).reshape(2,3)
            actual = np.array([float(named(entry,'CAffine','atlasLocalToCanvasTransform').get(k)) for k in KEYS]).reshape(2,3)
            position = named(entry,'GVector2','position')
            translation = np.array([float(named(position,'f',key).text) for key in ('x','y')])
            actual[:,2] += actual[:,:2] @ translation
            require(np.max(np.abs(expected-actual)) < 1e-9, 'Atlas/canvas affine composition mismatch')
    for entry in original.entries:
        if entry.path != 'main.xml':
            require(original.read_unique_path(entry.path,LIMIT) == final.read_unique_path(entry.path,LIMIT), 'Original payload changed: '+entry.path)
    for node in original_root.iter():
        ref = node.get('xs.id')
        if ref and node.tag in ('CArtMeshSource', 'CWarpDeformerSource', 'CRotationDeformerSource'):
            other = ET.fromstring(serial(final_ids[ref]))
            if ref in master_report['mesh_ids']:
                named(other, 'GTexture2D', 'texture').set('xs.ref', named(node,'GTexture2D','texture').get('xs.ref'))
                named(other, 'float-array', 'uvs').text = named(node, 'float-array','uvs').text
            require(serial(node)==serial(other), 'Rig geometry/poses changed: '+ref)
    result_report = {'status': 'offline_atlas_candidate_requires_native_validation',
        'source_sha256':SOURCE_SHA, 'output_sha256':sha(result), 'page_size':PAGE,
        'page_count':len(pages), 'used_images':len(assets), 'mesh_count':sum(len(v) for v in image_state(final_root)[2].values()),
        'master_crop':master_report, 'pages':report, 'original_payloads_unchanged':True,
        'rig_geometry_and_poses_unchanged':True, 'native_rendering_validated':False,
        'limitations':['Requires native open, atlas-mode preview and export before VTS use',
                       'Source PSD/KRA filters remain inherited; do not regenerate/reimport them']}
    exclusive(output,result)
    exclusive(audit,(json.dumps(result_report,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    print(json.dumps({k:result_report[k] for k in ('status','output_sha256','page_count','used_images','mesh_count')}))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--audit',type=Path,required=True)
    args=parser.parse_args()
    build(args.source,args.output,args.audit)
