#!/usr/bin/env python3
"""Restore painted front tips from the unchanged approved full-canvas master.

The segmented LOCK PNGs already have zero alpha over the white tips. Reading
their RGB alone falsely suggested intact art. This changes only the two new
tip meshes' texture bindings and UVs, not bitmap pixels or existing rig forms.
"""
import argparse
import copy
import io
import json
from pathlib import Path
from PIL import Image
import cmo3_create_deformer_experiment as ex
import cmo3_caff_rebuild as caff
import cmo3_r21_add_model_image as image
from cmo3_inventory import CaffArchive
from cmo3_r21_face_roots_to_head import one
from cmo3_r21_fullbody_first_assembly import named, direct, serialize, clone_roles
from cmo3_r21_iris_occlusion import set_array, values
from cmo3_r21_restore_eye_r_finite import require, sha, model_from_bytes, raw_source, exclusive

SOURCE_SHA = '37722EC3752392669D3FBE4DA63A309F35A8DCBC93208C7BAEA20549901663DA'

def build(source, output, audit):
    require(not output.exists() and not audit.exists(), 'Refusing overwrite')
    data = source.read_bytes()
    require(sha(data) == SOURCE_SHA, 'Requires shoulders r04')
    model, xml = model_from_bytes(data)
    path = Path(__file__).resolve().parents[1] / 'assets/live2d/r21_professional_art/master_v4_assets_v1/Jade_r21_master_v3_canvas_3840x4160.png'
    png = path.read_bytes()
    raster = Image.open(io.BytesIO(png))
    width, height = raster.size
    require((width, height) == (3840, 4160), 'Master dimensions differ')
    require(all(raster.getpixel((x, 1282))[3] == 255 for x in (1705, 2142)), 'Real white tips not opaque in master')
    current, tex = image.add_model_image_xml(xml, png, 'JAD_R21_ORIGINAL_MASTER_FOR_TIPS',
        'jade_r21_original_master_for_tips.png', template_name='JAD_R21_DRESS_BELT')
    records = []
    for side in ('L', 'R'):
        item = one(model, 'JAD_R21_HAIR_FRONT_PAINTED_TIP_' + side, 'art-mesh')
        source_node = copy.deepcopy(model.source(item))
        original = values(direct(source_node, 'float-array', 'positions'))
        uvs = [v for x, y in zip(original[::2], original[1::2]) for v in (x/width, y/height)]
        set_array(direct(source_node, 'float-array', 'uvs'), uvs)
        named(source_node, 'GTexture2D', 'texture').set('xs.ref', tex['texture_ref'])
        current = ex._replace_exact(current, raw_source(xml, item), serialize(source_node), 1, 'Use opaque master tip ' + side)
        refs = clone_roles(model.root, model.source(item), item.name)
        inp = copy.deepcopy(model.ids[refs['model-input']])
        named(inp, 'CModelImageGuid', '_modelImageGuid').set('xs.ref', tex['model_image_guid_ref'])
        current = ex._replace_exact(current, ex._block_by_id(current, inp.tag, inp.get('xs.id')), serialize(inp), 1, 'Rebind master ' + side)
        records.append(item.name)
    for item in model.objects:
        if item.name not in records:
            require(raw_source(xml, item) == raw_source(current, item), 'Unrelated object changed ' + item.name)
    result = caff.rebuild_caff_with_png(data, png_path=tex['member_path'], png_bytes=png, replacement_main_xml=current)
    before, after = CaffArchive.parse(data), CaffArchive.parse(result)
    for entry in before.entries:
        if entry.path != 'main.xml':
            require(before.read_unique_path(entry.path, 256*1024*1024) == after.read_unique_path(entry.path, 256*1024*1024), 'Old raster changed')
    report = {'status': 'candidate_requires_native_gate', 'source_sha256': SOURCE_SHA,
        'output_sha256': sha(result), 'master_png': str(path), 'master_sha256': sha(png),
        'changed_meshes': records, 'bitmap_bytes_unchanged': True,
        'diagnosis': 'Both segmented disk LOCK assets also have alpha=0 over white tips; master RGBA has alpha=255. Native probe confirmed no broken texture binding.'}
    exclusive(output, result)
    exclusive(audit, (json.dumps(report, indent=2)+'\n').encode())
    print(json.dumps(report))

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--audit', type=Path, required=True)
    a = p.parse_args()
    build(a.source, a.output, a.audit)
