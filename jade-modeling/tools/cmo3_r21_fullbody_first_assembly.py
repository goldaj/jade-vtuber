#!/usr/bin/env python3
"""Append five native lower-body meshes to v25, preserving every raster byte.

This is a first assembly, not the final articulated body. Mesh silhouettes
follow the generated cutouts; no bitmap is repainted, keyed or resized here.
The old long-skirt meshes remain recoverable with zero opacity in the copy.
"""
from __future__ import annotations
import argparse
import copy
import json
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from PIL import Image
import cmo3_create_deformer_experiment as ex
import cmo3_hair_art_partition_r16 as partition
import cmo3_secondary_professional as secondary
import cmo3_reparent_preserve_canvas as canvas
import cmo3_caff_rebuild as caff
import cmo3_r21_mesh_polygon_trim as trim
import cmo3_r21_add_model_image as new_image
from cmo3_inventory import CaffArchive
from cmo3_r21_mouth_form_first_rig import MouthNeutralModel
from cmo3_r21_restore_eye_r_finite import require, sha, model_from_bytes, raw_source, exclusive, nonfinite_objects
from cmo3_r21_face_roots_to_head import one
from cmo3_r21_iris_occlusion import replace_geometry, set_array

SOURCE_SHA = '37B3F0975640C522484D8F69C73884C2801D43E3D19A313412ABBFA216B474A3'
IMAGE_NAME = 'JAD_R21_LOWERBODY_PARTS_V3'
IMAGE_MEMBER = 'jade_r21_lowerbody_parts_v3.png'
# x/y are atlas coordinates. Transforms preserve upper-body scale and position.
SPECS = [
    ('JAD_R21_SHORT_SKIRT_V3', (24,65,718,692), 2.0, 1166.0, 1655.0, 505),
    ('JAD_R21_LEG_R_V3', (725,112,938,1050), 1.75, 262.0, 2585.0, 480),
    ('JAD_R21_LEG_L_V3', (1005,112,1215,1050), 1.75, 157.5, 2585.0, 480),
    ('JAD_R21_SHOE_R_V3', (173,784,318,1165), 1.5, 1378.0, 3030.0, 485),
    ('JAD_R21_SHOE_L_V3', (428,784,580,1165), 1.5, 1309.0, 3030.0, 485),
]

def direct(node,tag,name):
    return canvas._one_direct_named(node,tag,name)

def named(node,tag,name):
    return ex._one_named(node,tag,name)

def serialize(node):
    node.tail=None
    return ET.tostring(node,encoding='utf-8',short_empty_elements=True)

def mesh_from_rows(pixels, rect, scale, tx, ty):
    """Create a deformable strip following the largest opaque run per row.

    The raster stays untouched. Isolated extraction noise is excluded from
    the native mesh's boundary rather than being copied as extra islands.
    """
    x0,y0,x1,y1=rect
    bounds=[]
    for y in range(y0,y1):
        opaque=pixels[y,x0:x1,3]>220
        # All five assets have a large opaque interior and no internal holes.
        delta=np.diff(np.r_[False,opaque,False].astype(np.int8))
        starts=np.flatnonzero(delta==1); ends=np.flatnonzero(delta==-1)
        if len(starts):
            i=int(np.argmax(ends-starts))
            if ends[i]-starts[i]>12:
                bounds.append((y,x0+int(starts[i]),x0+int(ends[i])-1))
    require(len(bounds)>50,'Cutout is missing or too short')
    # Preserve the source outline densely enough for the scalloped skirt.
    selected=bounds[::6]
    if selected[-1]!=bounds[-1]: selected.append(bounds[-1])
    cols=12
    atlas_points=[]
    for y,left,right in selected:
        for col in range(cols+1):
            atlas_points.append((left+(right-left)*col/cols,float(y)))
    triangles=[]
    for row in range(len(selected)-1):
        for col in range(cols):
            a=row*(cols+1)+col; b=a+1; c=a+cols+1; d=c+1
            triangles.extend((a,b,d,a,d,c))
    edges=sorted({tuple(sorted(pair)) for i in range(0,len(triangles),3)
                  for a,b,c in [triangles[i:i+3]] for pair in ((a,b),(b,c),(c,a))})
    positions=[v for x,y in atlas_points for v in (x*scale+tx,y*scale+ty)]
    height,width=pixels.shape[:2]
    uvs=[v for x,y in atlas_points for v in (x/width,y/height)]
    return positions,uvs,triangles,[v for e in edges for v in e]

def clone_roles(root,source,name):
    ids={n.get('xs.id'):n for n in root.find('shared')}
    extension_ref=next(n.get('xs.ref') for n in source.iter('CTextureInputExtension'))
    model_refs={n.get('xs.ref') for n in ids[extension_ref].iter('CTextureInput_ModelImage')}
    require(len(model_refs)==1,'Ambiguous model image input')
    return {'source':source.get('xs.id'),
            'form-guid':named(source,'CFormGuid','guid').get('xs.ref'),
            'drawable-guid':named(source,'CDrawableGuid','guid').get('xs.ref'),
            'texture-extension':extension_ref,'model-input':next(iter(model_refs))}

def role(name,key):return 'body:'+name+':'+key

def clone_static(root,template,name,slots,tex_info,positions,uvs,triangles,edges,draw):
    refs=clone_roles(root,template,name)
    ids={n.get('xs.id'):n for n in root.find('shared')}
    mapping={ref:slots[role(name,key)][0] for key,ref in refs.items()}
    nodes={}
    for key,ref in refs.items():
        new_ref,idx=slots[role(name,key)]
        node=partition._clone_shared_node(ids[ref],ref=new_ref,idx=idx,replacements=mapping)
        for index,g in enumerate(n for n in node.iter() if n.get('uuid')):
            g.set('uuid',str(uuid.uuid5(uuid.NAMESPACE_URL,f'jade:r21:fullbody:{SOURCE_SHA}:{name}:{key}:{index}')))
        nodes[key]=node
    source=nodes['source']
    named(source,'s','localName').text=name
    named(source,'CDrawableId','id').set('idstr',name)
    nodes['drawable-guid'].set('note',name)
    root_guid=next(n.get('xs.id') for n in root.find('shared').findall('CDeformerGuid') if n.get('note')=='ROOT')
    named(source,'CDeformerGuid','targetDeformerGuid').set('xs.ref',root_guid)
    basic=next(n.get('xs.id') for n in root.find('shared').findall('CoordType') if named(n,'s','coordName').text=='Basic Coord')
    named(source,'GTexture2D','texture').set('xs.ref',tex_info['texture_ref'])
    named(nodes['model-input'],'CModelImageGuid','_modelImageGuid').set('xs.ref',tex_info['model_image_guid_ref'])
    replace_geometry(source,positions,uvs,triangles,edges)
    forms=direct(source,'carray_list','keyforms')
    require(len(forms)==1,'Template is not static')
    f=forms[0]
    set_array(direct(f,'float-array','positions'),positions)
    named(f,'CoordType','coordType').set('xs.ref',basic)
    named(f,'f','opacity').text='1.0'
    named(f,'i','drawOrder').text=str(draw)
    return [serialize(n) for n in nodes.values()], {
        'name':name,'source_ref':mapping[refs['source']],
        'drawable_ref':mapping[refs['drawable-guid']],
        'part_ref':named(source,'CPartGuid','parentGuid').get('xs.ref'),
        'vertices':len(positions)//2,'triangles':len(triangles)//3,
        'bounds':[min(positions[::2]),min(positions[1::2]),max(positions[::2]),max(positions[1::2])],
        'parent':'ROOT, body articulation remains next milestone'}

def build(source,raster,output,audit):
    require(not output.exists() and not audit.exists(),'Refusing overwrite')
    data=source.read_bytes(); require(sha(data)==SOURCE_SHA,'Expected native v25')
    _,xml=model_from_bytes(data)
    archive=CaffArchive.parse(data)
    model=MouthNeutralModel(xml,.001)
    png=raster.read_bytes()
    im=Image.open(raster); require(im.mode=='RGBA','Actual alpha channel required')
    pixels=np.asarray(im)
    template=model.source(one(model,'JAD_R21_DRESS_BELT','art-mesh'))
    roles=list(new_image.allocation_roles(IMAGE_NAME))
    for name,*_ in SPECS: roles += [role(name,k) for k in clone_roles(model.root,template,name)]
    slots=secondary._allocate(model.root,roles)
    root,tex_info=new_image.add_model_image(model.root,png,IMAGE_NAME,IMAGE_MEMBER,slots=slots,template_name='JAD_R21_DRESS_BELT')
    # Keep original XML formatting outside the one image-group and added blocks.
    old_group=next(n for n in model.root.find('shared') if n.tag=='CModelImageGroup')
    new_group=next(n for n in root.find('shared') if n.get('xs.id')==old_group.get('xs.id'))
    current=ex._replace_exact(xml,ex._block_by_id(xml,old_group.tag,old_group.get('xs.id')),serialize(new_group),1,'Append body model image')
    old_ids={n.get('xs.id') for n in model.root.find('shared')}
    additions=[serialize(n) for n in root.find('shared') if n.get('xs.id') not in old_ids]
    records=[]
    for name,rect,scale,tx,ty,draw in SPECS:
        geometry=mesh_from_rows(pixels,rect,scale,tx,ty)
        blocks,record=clone_static(model.root,template,name,slots,tex_info,*geometry,draw)
        additions+=blocks; records.append(record)
    current=ex._append_shared_blocks(current,additions)
    current=partition._patch_drawable_source_set(current,[r['source_ref'] for r in records])
    part=records[0]['part_ref']; require(all(r['part_ref']==part for r in records),'Part differs')
    current=partition._patch_part_children(current,part_source_ref=partition._part_source_ref(model.root,part),
        drawable_refs=[r['drawable_ref'] for r in records],experiment=ex)
    changes=[]
    for item in model.objects:
        if item.name.startswith('JAD_R21_SKIRT_PANEL_') or item.name=='JAD_R21_DRESS_BELT':
            node=copy.deepcopy(model.source(item))
            for f in direct(node,'carray_list','keyforms'):named(f,'f','opacity').text='0.0'
            current=ex._replace_exact(current,raw_source(current,item),serialize(node),1,'Hide old long skirt '+item.name)
            changes.append(item.name)
        elif item.name in ('JAD_R21_HAND_L','JAD_R21_HAND_R','JAD_R21_ARM_L_FOREARM','JAD_R21_ARM_R_FOREARM'):
            node=copy.deepcopy(model.source(item))
            for f in direct(node,'carray_list','keyforms'):named(f,'i','drawOrder').text='520'
            current=ex._replace_exact(current,raw_source(current,item),serialize(node),1,'Hands in front of short skirt '+item.name)
            changes.append(item.name)
        elif item.name=='JAD_R21_RESIDUAL_UNDERLAY':
            node=copy.deepcopy(model.source(item))
            trim.trim_source(node,[(0,0),(3840,0),(3840,3020),(0,3020)])
            current=ex._replace_exact(current,raw_source(current,item),serialize(node),1,'Trim residual old long hem '+item.name)
            changes.append(item.name)
    # Extend only the canvas metadata, never scale any upper-body coordinates.
    require(current.count(b'<i xs.n="pixelHeight">4160</i>')==1,'Canvas height not unique')
    current=current.replace(b'<i xs.n="pixelHeight">4160</i>',b'<i xs.n="pixelHeight">5000</i>')
    after=MouthNeutralModel(current,.001)
    require(not nonfinite_objects(after),'Nonfinite geometry')
    for item in model.objects:
        if item.name not in changes: require(raw_source(xml,item)==raw_source(current,item),'Unrelated rig changed: '+item.name)
    require(len(after.objects)==len(model.objects)+5,'Unexpected mesh count')
    result=caff.rebuild_caff_with_png(data,png_path=IMAGE_MEMBER,png_bytes=png,replacement_main_xml=current)
    _,out_xml=model_from_bytes(result)
    out_archive=CaffArchive.parse(result)
    require(out_xml==current,'Archive XML differs')
    for entry in archive.entries:
        if entry.path!='main.xml': require(archive.read_unique_path(entry.path,256*1024*1024)==out_archive.read_unique_path(entry.path,256*1024*1024),'Existing asset differs')
    report={'status':'first_assembly_requires_native_gate','source_sha256':SOURCE_SHA,'output_sha256':sha(result),
        'new_image':str(raster),'new_image_sha256':sha(png),'raster_bytes_unchanged':True,
        'canvas':[3840,5000],'meshes':records,'changed_existing_meshes':changes,
        'upper_body_scale_unchanged':True,'eyes_and_closed_art_untouched':True,
        'remaining':['Seam and proportions native gate','Fine edge cleanup','Leg, shoe and skirt articulation','KRA/PSD source sync']}
    exclusive(output,result);exclusive(audit,(json.dumps(report,indent=2)+'\n').encode())
    print(json.dumps({'output':str(output),'sha256':sha(result),'meshes':len(records),'status':report['status']}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path);p.add_argument('raster',type=Path)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--audit',type=Path,required=True)
    a=p.parse_args();build(a.source,a.raster,a.output,a.audit)
