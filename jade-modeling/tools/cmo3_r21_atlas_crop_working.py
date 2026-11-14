#!/usr/bin/env python3
"""Prepare isolated, pixel-exact texture crops for the r21 working model.

No artwork is repainted or scaled. This only prepares source images and UVs;
native Cubism atlas generation and visual validation remain mandatory.
"""
from __future__ import annotations
import argparse
import io
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image
import cmo3_caff_rebuild as caff
import cmo3_create_deformer_experiment as ex
import cmo3_reparent_preserve_canvas as canvas
import cmo3_r21_add_model_image as add_image
from cmo3_inventory import CaffArchive
from cmo3_r21_face_roots_to_head import one
from cmo3_r21_restore_eye_r_finite import exclusive, model_from_bytes, raw_source, require, sha
from cmo3_r21_split_model_images_v31 import SOURCE_SHA, TARGETS, array, idmap, mesh_image, one_named, serial

MARGIN = 8

def crop_png(png, uv):
    with Image.open(io.BytesIO(png)) as image:
        require(image.mode == 'RGBA', 'Expected RGBA source')
        width, height = image.size
        px = uv * np.array([width, height], dtype=np.float64)
        require(np.all(px >= -0.001) and np.all(px <= np.array([width, height])+0.001), 'Source UV outside image')
        x0 = max(0, math.floor(float(px[:,0].min())) - MARGIN)
        y0 = max(0, math.floor(float(px[:,1].min())) - MARGIN)
        x1 = min(width, math.ceil(float(px[:,0].max())) + MARGIN)
        y1 = min(height, math.ceil(float(px[:,1].max())) + MARGIN)
        require(x1>x0 and y1>y0, 'Empty crop')
        crop = image.crop((x0,y0,x1,y1))
        output = io.BytesIO()
        crop.save(output, format='PNG')
        with Image.open(io.BytesIO(output.getvalue())) as check:
            require(np.array_equal(np.asarray(crop), np.asarray(check)), 'Cropped pixel mismatch')
        transformed=(px-np.array([x0,y0]))/np.array([x1-x0,y1-y0])
        return output.getvalue(), transformed, (x0,y0,x1,y1), (width,height)

def build(source, output, audit):
    require(not output.exists() and not audit.exists(), 'Refusing overwrite')
    original=source.read_bytes(); require(sha(original)==SOURCE_SHA, 'Expected intact native v31')
    base, base_xml=model_from_bytes(original); base_archive=CaffArchive.parse(original)
    data=original; records=[]; names={name for name,_ in TARGETS}
    for index,(name,template) in enumerate(TARGETS,1):
        model,xml=model_from_bytes(data); obj=one(model,name,'art-mesh'); node=model.source(obj)
        _,resource,member,_,input_ref=mesh_image(model.root,node)
        png=CaffArchive.parse(data).read_unique_path(member,256*1024*1024)
        uv,points=array(node,'uvs'),array(node,'positions')
        cropped,new_uv,box,dimensions=crop_png(png,uv)
        require(dimensions==(int(resource.get('width')),int(resource.get('height'))),'Source dimensions changed')
        pixel=new_uv*np.array([box[2]-box[0],box[3]-box[1]])
        design=np.column_stack((pixel[:,0],pixel[:,1],np.ones(len(pixel))))
        matrix,_,rank,_=np.linalg.lstsq(design,points,rcond=None)
        require(rank==3 and np.max(np.abs(design@matrix-points))<.001,'Non-affine crop mapping')
        affine=tuple(float(v) for v in (matrix[0,0],matrix[1,0],matrix[2,0],matrix[0,1],matrix[1,1],matrix[2,1]))
        image_name=f'JAD_R21_CROP_IMAGE_{index:02d}'
        member_name=f'jade_r21_crop_image_{index:02d}.png'
        updated,info=add_image.add_model_image_xml(xml,cropped,image_name,member_name,
                                                   material_to_canvas=affine,template_name=template)
        ids=idmap(ET.fromstring(updated)); old_mesh=raw_source(updated,obj); mesh=ET.fromstring(old_mesh)
        one_named(mesh,'GTexture2D','texture').set('xs.ref',info['texture_ref'])
        uv_node=next(n for n in mesh if n.tag=='float-array' and n.get('xs.n')=='uvs')
        uv_node.text=' '.join(canvas._format_float32(float(v)) for v in new_uv.ravel())
        updated=ex._replace_exact(updated,old_mesh,serial(mesh),1,name+' cropped UV')
        input_node=ids[input_ref]; old_input=ex._block_by_id(updated,input_node.tag,input_ref)
        changed=ET.fromstring(old_input)
        one_named(changed,'CModelImageGuid','_modelImageGuid').set('xs.ref',info['model_image_guid_ref'])
        updated=ex._replace_exact(updated,old_input,serial(changed),1,name+' cropped image')
        data=caff.rebuild_caff_with_png(data,png_path=member_name,png_bytes=cropped,replacement_main_xml=updated)
        checked,_=model_from_bytes(data); actual=checked.source(one(checked,name,'art-mesh'))
        require(np.array_equal(array(node,'positions'),array(actual,'positions')),'Mesh positions changed')
        restored=array(actual,'uvs')*np.array([box[2]-box[0],box[3]-box[1]])+np.array(box[:2])
        error=float(np.max(np.abs(restored-uv*np.array(dimensions))))
        require(error<.001,'Serialized UV changed texture sampling')
        records.append({'mesh':name,'source_member':member,'new_member':member_name,'crop':box,
                        'source_dimensions':dimensions,'material_to_canvas':affine,'max_uv_error_px':error,
                        'cropped_png_sha256':sha(cropped)})
    final,final_xml=model_from_bytes(data); archive=CaffArchive.parse(data)
    require(len(base.objects)==len(final.objects),'Object count changed')
    for obj in base.objects:
        if obj.name not in names: require(raw_source(base_xml,obj)==raw_source(final_xml,obj),'Unrelated object changed: '+obj.name)
    for entry in base_archive.entries:
        if entry.path!='main.xml':
            require(base_archive.read_unique_path(entry.path,256*1024*1024)==archive.read_unique_path(entry.path,256*1024*1024),'Original archive changed')
    report={'status':'working_candidate_not_native_or_vts_validated','source_sha256':SOURCE_SHA,
            'output_sha256':sha(data),'images':records,'all_source_rasters_preserved':True,
            'limitations':['Crops are pixel-exact but require native preview and atlas validation',
                           'PSD/KRA still unsynchronized; do not regenerate old PSD filters']}
    exclusive(output,data); exclusive(audit,(json.dumps(report,indent=2,ensure_ascii=False)+'\n').encode('utf-8'))
    print(json.dumps({'output':str(output),'sha256':sha(data),'status':report['status']}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--audit',type=Path,required=True)
    a=p.parse_args();build(a.source,a.output,a.audit)

