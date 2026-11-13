#!/usr/bin/env python3
"""Add two experimental rear-hair underlays to a copy of r21 r02.

The generated source image stays unchanged; UVs sample its inner hair only.
This is a pose-check candidate, not a final rig or a source-art sync.
"""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from PIL import Image
import cmo3_create_deformer_experiment as ex
import cmo3_caff_rebuild as caff
import cmo3_hair_art_partition_r16 as partition
import cmo3_secondary_professional as secondary
import cmo3_r21_add_model_image as image
from cmo3_inventory import CaffArchive
from cmo3_r21_head_z_v28 import neutral_model
from cmo3_r21_face_roots_to_head import one
from cmo3_r21_fullbody_first_assembly import clone_roles, named, role, serialize
from cmo3_r21_underpaint_clone import clone_underpaint
from cmo3_r21_restore_eye_r_finite import require, sha, model_from_bytes, raw_source, exclusive

SOURCE_SHA='68617D558A59593E54C2582AB7845FFA317D8A7E0676E25D5B5514B083C95F62'
PAINT_SHA='3A402867E3CB697CF1B2581F4F5481B9EEB669EF3E447A1AC64BFDF362B0EA93'
# Rectangles stay predominantly behind the garment and existing rear strands.
# Hand-tuned scene registration is a starting hypothesis, not a QA result.
RIGHT_ROWS=((1050.,2200.,2310.),(1150.,2200.,2330.),(1250.,2190.,2370.),
            (1350.,2180.,2400.),(1450.,2180.,2410.),(1525.,2200.,2380.),
            (1600.,2250.,2370.),(1640.,2325.,2355.))
SPECS=(('L',tuple((y,3840.-right,3840.-left) for y,left,right in RIGHT_ROWS)),('R',RIGHT_ROWS))

def grid(strips):
    cols=4;rows=len(strips)-1
    points=[v for y,left,right in strips for x in range(cols+1)
            for v in (left+(right-left)*x/cols,y)]
    triangles=[]
    for y in range(rows):
        for x in range(cols):
            a=y*(cols+1)+x;b=a+1;c=a+cols+1;d=c+1
            triangles.extend((a,b,d,a,d,c))
    edges=[v for edge in sorted({tuple(sorted(edge)) for i in range(0,len(triangles),3)
        for a,b,c in [triangles[i:i+3]] for edge in ((a,b),(b,c),(c,a))}) for v in edge]
    return points,triangles,edges

def build(source,paint,output,audit):
    require(not output.exists() and not audit.exists(),'Refusing overwrite')
    data=source.read_bytes();png=paint.read_bytes()
    require(sha(data)==SOURCE_SHA and sha(png)==PAINT_SHA,'Unexpected source')
    with Image.open(paint) as im:
        require(im.size==(1200,1311) and im.mode=='RGBA','Unexpected underpainting')
    original,xml=model_from_bytes(data);base=neutral_model(xml)
    current,tex=image.add_model_image_xml(xml,png,'JAD_R21_REAR_HAIR_UNDERPAINT_CANDIDATE',
        'jade_r21_rear_hair_underpaint_candidate_v1.png',template_name='JAD_R21_DRESS_BELT')
    root=ET.fromstring(current);template=original.source(one(original,'JAD_R21_DRESS_BELT','art-mesh'))
    names=['JAD_R21_HAIR_SHOULDER_UNDERPAINT_'+side for side,_ in SPECS]
    slots=secondary._allocate(root,[role(n,k) for n in names for k in clone_roles(root,template,n)])
    blocks=[];records=[]
    parent=one(base,'D_JAD_HAIR_BACK_GLOBAL','warp-deformer').guid_ref
    for (side,strips),name in zip(SPECS,names):
        target=one(base,'JAD_R21_HAIR_BACK_'+side+'_LOWER','art-mesh')
        part=named(base.source(target),'CPartGuid','parentGuid').get('xs.ref')
        world,tris,edges=grid(strips)
        local=[ex._float32(v) for v in base.inverse_many(base.transform(parent),world)]
        error=max(abs(a-b) for a,b in zip(world,base.forward_many(base.transform(parent),local)))
        require(error<.001,'Underlay parent conversion failed')
        # Sample the opaque inner hair rather than transparent outer silhouette.
        # Each shoulder has a distinct region; this remains a visual experiment.
        left=min(r[1] for r in strips);right=max(r[2] for r in strips)
        top=strips[0][0];bottom=strips[-1][0]
        ulo,uhi=(.26,.47) if side=='L' else (.53,.74)
        uv=[v for x,y in zip(world[::2],world[1::2])
            for v in (ulo+(uhi-ulo)*(x-left)/(right-left),.43+.37*(y-top)/(bottom-top))]
        new,record=clone_underpaint(root,template,name,slots,tex,world,local,uv,tris,edges,parent,498)
        node=ET.fromstring(new[0]);named(node,'CPartGuid','parentGuid').set('xs.ref',part);new[0]=serialize(node)
        blocks+=new;record.update(part_ref=part,strips=strips,max_neutral_error_px=error)
        records.append(record)
    current=ex._append_shared_blocks(current,blocks)
    current=partition._patch_drawable_source_set(current,[r['source_ref'] for r in records])
    for part in sorted({r['part_ref'] for r in records}):
        current=partition._patch_part_children(current,part_source_ref=partition._part_source_ref(root,part),
            drawable_refs=[r['drawable_ref'] for r in records if r['part_ref']==part],experiment=ex)
    for obj in original.objects:require(raw_source(xml,obj)==raw_source(current,obj),'Existing object changed '+obj.name)
    result=caff.rebuild_caff_with_png(data,png_path=tex['member_path'],png_bytes=png,replacement_main_xml=current)
    a,b=CaffArchive.parse(data),CaffArchive.parse(result)
    for e in a.entries:
        if e.path!='main.xml':require(a.read_unique_path(e.path,256*1024*1024)==b.read_unique_path(e.path,256*1024*1024),'Existing raster changed')
    report={'status':'experimental_requires_native_gate','source_sha256':SOURCE_SHA,'paint_sha256':PAINT_SHA,
        'output_sha256':sha(result),'meshes':records,'old_objects_and_rasters_unchanged':True,
        'warning':'UV alignment and neutral/tilt appearance are unverified; source KRA/PSD not synchronized.'}
    exclusive(output,result);exclusive(audit,(json.dumps(report,indent=2)+'\n').encode())
    print(json.dumps({'output':str(output),'sha256':sha(result),'status':report['status']}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('paint',type=Path)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--audit',type=Path,required=True)
    a=p.parse_args();build(a.source,a.paint,a.output,a.audit)
