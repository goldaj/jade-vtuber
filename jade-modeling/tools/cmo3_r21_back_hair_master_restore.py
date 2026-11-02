#!/usr/bin/env python3
"""Restore lost rear-hair paint below the ears and two neck-side overlaps.

Reuse the untouched full-canvas master already embedded in v29. Keep original
segmentation above y950, so no baked ear or facial art is reintroduced there.
All geometry clipping is vector-only; no raster pixels are edited.
"""
import argparse
import copy
import json
import xml.etree.ElementTree as ET
from pathlib import Path
import cmo3_create_deformer_experiment as ex
import cmo3_secondary_professional as secondary
import cmo3_hair_art_partition_r16 as partition
import cmo3_safe_roundtrip as safe
import cmo3_r21_mesh_polygon_trim as trim
from cmo3_inventory import CaffArchive
from cmo3_r21_head_z_v28 import neutral_model
from cmo3_r21_face_roots_to_head import one
from cmo3_r21_fullbody_first_assembly import named, direct, serialize, clone_roles, role
from cmo3_r21_underpaint_clone import clone_underpaint
from cmo3_r21_iris_occlusion import values, set_array
from cmo3_r21_restore_eye_r_finite import require, sha, model_from_bytes, raw_source, exclusive

SOURCE_SHA = 'F414CDC057CEE33036F975F0455EE43846988DECFB05ACACC0397AC91A6C5208'
TARGETS = ['JAD_R21_HAIR_BACK_'+s+'_'+p for s in ('L','R') for p in ('OUTER','MID_OUTER','LOWER')]

def master_uv(world):
    return [v for x,y in zip(world[::2],world[1::2]) for v in (x/3840,y/4160)]

def mesh_edges(tris):
    return [v for pair in sorted({tuple(sorted(pair)) for k in range(0,len(tris),3)
        for a,b,c in [tris[k:k+3]] for pair in ((a,b),(b,c),(c,a))}) for v in pair]

def neck_strip(side):
    rows=[(960,1710,1850),(990,1710,1844),(1020,1710,1842),
          (1050,1715,1840),(1070,1720,1835),(1090,1725,1820),
          (1110,1730,1790),(1130,1735,1755),(1138,1740,1745)]
    pts=[(x if side=='L' else 3840-x,y) for y,l,r in rows for x in (l,(l+r)/2,r)]
    tris=[]
    for row in range(len(rows)-1):
        for col in range(2):
            a=row*3+col;b=a+1;c=a+3;d=c+1
            tris += [a,b,d,a,d,c]
    return [v for p in pts for v in p],tris

def build(source,output,audit):
    require(not output.exists() and not audit.exists(),'Refusing overwrite')
    data=source.read_bytes();require(sha(data)==SOURCE_SHA,'Requires native v29')
    original,xml=model_from_bytes(data);model=neutral_model(xml);root=original.root
    tip=one(original,'JAD_R21_HAIR_FRONT_PAINTED_TIP_L','art-mesh')
    tip_roles=clone_roles(root,original.source(tip),tip.name)
    tex={'texture_ref':named(original.source(tip),'GTexture2D','texture').get('xs.ref'),
         'model_image_guid_ref':named(original.ids[tip_roles['model-input']],'CModelImageGuid','_modelImageGuid').get('xs.ref')}
    template=original.source(one(original,'JAD_R21_DRESS_BELT','art-mesh'))
    jobs=[];current=xml;changed=[];splits=[]
    def bind_existing(item,node):
        nonlocal current
        set_array(direct(node,'float-array','uvs'),master_uv(values(direct(node,'float-array','positions'))))
        named(node,'GTexture2D','texture').set('xs.ref',tex['texture_ref'])
        refs=clone_roles(root,original.source(item),item.name)
        inp=copy.deepcopy(original.ids[refs['model-input']])
        named(inp,'CModelImageGuid','_modelImageGuid').set('xs.ref',tex['model_image_guid_ref'])
        current=ex._replace_exact(current,ex._block_by_id(current,inp.tag,inp.get('xs.id')),serialize(inp),1,'Master input '+item.name)
    for name in TARGETS:
        item=one(original,name,'art-mesh');node=copy.deepcopy(original.source(item))
        forms=direct(node,'carray_list','keyforms')
        require(len(forms)==1,'Cannot split animated source '+name)
        ys=values(direct(node,'float-array','positions'))[1::2]
        if min(ys)<950:
            lower=copy.deepcopy(node)
            trim.trim_source(lower,[(0,950),(3840,950),(3840,5000),(0,5000)])
            trim.trim_source(node,[(0,0),(3840,0),(3840,950),(0,950)])
            world=list(values(direct(lower,'float-array','positions')))
            local=list(values(direct(direct(lower,'carray_list','keyforms')[0],'float-array','positions')))
            tris=[int(v) for v in (direct(lower,'int-array','indices').text or '').split()]
            jobs.append((name+'_PAINT_RESTORED',world,local,tris,item.parent_ref,
                         named(node,'CPartGuid','parentGuid').get('xs.ref'),500))
            splits.append(name)
        else:
            bind_existing(item,node)
        current=ex._replace_exact(current,raw_source(xml,item),serialize(node),1,'Restore lower paint '+name)
        changed.append(name)
    depth=one(model,'JAD_R21_HAIR_DEPTH_UNDERLAY','art-mesh')
    for side in ('L','R'):
        world,tris=neck_strip(side)
        local=[ex._float32(v) for v in model.inverse_many(model.transform(depth.parent_ref),world)]
        jobs.append(('JAD_R21_HAIR_NECK_OVERLAP_'+side,world,local,tris,depth.parent_ref,
                     named(model.source(depth),'CPartGuid','parentGuid').get('xs.ref'),499))
    roles=[role(name,k) for name,*_ in jobs for k in clone_roles(root,template,name)]
    slots=secondary._allocate(root,roles);records=[];blocks=[]
    for name,world,local,tris,parent,part,draw in jobs:
        new,record=clone_underpaint(root,template,name,slots,tex,world,local,master_uv(world),tris,mesh_edges(tris),parent,draw)
        # Organize in the original hair Part, not in the BELT template's Part.
        source_node=ET.fromstring(new[0])
        named(source_node,'CPartGuid','parentGuid').set('xs.ref',part)
        new[0]=serialize(source_node);record['part_ref']=part
        blocks+=new;records.append(record)
    current=ex._append_shared_blocks(current,blocks)
    current=partition._patch_drawable_source_set(current,[r['source_ref'] for r in records])
    for part in sorted({r['part_ref'] for r in records}):
        current=partition._patch_part_children(current,part_source_ref=partition._part_source_ref(root,part),
            drawable_refs=[r['drawable_ref'] for r in records if r['part_ref']==part],experiment=ex)
    for item in original.objects:
        if item.name not in changed:require(raw_source(xml,item)==raw_source(current,item),'Unrelated object changed '+item.name)
    result=safe._replace_main_xml(data,current)
    a,b=CaffArchive.parse(data),CaffArchive.parse(result)
    for e in a.entries:
        if e.path!='main.xml':require(a.read_unique_path(e.path,256*1024*1024)==b.read_unique_path(e.path,256*1024*1024),'Raster changed')
    report={'status':'candidate_requires_native_gate','source_sha256':SOURCE_SHA,'output_sha256':sha(result),
        'restored_existing':changed,'upper_segments_preserved':splits,'new_meshes':records,
        'all_raster_bytes_preserved':True,'remaining':'Native seam gate; hidden roots of bottom locks and independent dynamics are not finalized.'}
    exclusive(output,result);exclusive(audit,(json.dumps(report,indent=2)+'\n').encode())
    print(json.dumps({'output':str(output),'sha256':sha(result),'new_meshes':len(records)}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--audit',type=Path,required=True)
    a=p.parse_args();build(a.source,a.output,a.audit)
