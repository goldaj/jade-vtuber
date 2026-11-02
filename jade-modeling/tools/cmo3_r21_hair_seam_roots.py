#!/usr/bin/env python3
"""Vector-only lower-lock roots and temple/back-hair overlaps for native v30.

The old segmentation-coordinate cuts used unpadded PNG dimensions, whereas
the source UVs describe padded textures. LOWER_L's nominal y=1548 therefore
became canvas y=1572.35, removing the painted root. Use exact master-canvas
coordinates here. No bitmap is generated, edited, or written.

``patch(xml)`` returns bytes. ``patch_with_audit(xml)`` also returns an audit.
The CLI is a read-only model dry run, with an optional exclusive JSON report;
it deliberately cannot write a CMO3. Native neutral/HeadZ QA is still required.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import cmo3_create_deformer_experiment as ex
import cmo3_hair_art_partition_r16 as partition
import cmo3_secondary_professional as secondary
import cmo3_r21_mesh_polygon_trim as trim
import cmo3_safe_roundtrip as safe
from cmo3_inventory import CaffArchive
from cmo3_r21_face_roots_to_head import one
from cmo3_r21_fullbody_first_assembly import clone_roles, direct, named, role, serialize
from cmo3_r21_hair_shoulder_cleanup import _merge, _piece_arrays
from cmo3_r21_head_z_v28 import neutral_model
from cmo3_r21_iris_occlusion import values
from cmo3_r21_restore_eye_r_finite import exclusive, model_from_bytes, raw_source, require, sha
from cmo3_r21_underpaint_clone import clone_underpaint

SOURCE_SHA = '2AFC3C21F451626156B138733D0BC792CEB3463E086FA21334307FFC8B73A1EE'
PREFIX = 'JAD_R21_HAIR_'

# All (canvas_y, canvas_left_x, canvas_right_x) rows are in the 3840x4160
# untouched master. Inner edges stop on the hair side of the garment/arm.
# The original alpha supplies the outer tuft notches. No RGB-only inference.
LOWER_ROWS = {
    'L': [(1546,1452,1455),(1550,1450,1457),(1560,1441,1470),
          (1570,1428,1481),(1580,1413,1481),(1590,1395,1481),
          (1600,1360,1481),(1610,1360,1480),(1620,1378,1480),
          (1630,1396,1479),(1640,1440,1477),(1644,1463,1475)],
    'R': [(1546,2402,2420),(1550,2397,2425),(1560,2383,2423),
          (1570,2369,2420),(1580,2358,2430),(1590,2357,2450),
          (1600,2357,2488),(1610,2357,2495),(1620,2357,2480),
          (1630,2357,2458),(1640,2357,2428),(1650,2357,2412),
          (1658,2357,2393)],
}

# Small overlapping side strips below the ears. They deliberately avoid
# the mobile front locks/white tips, face, neck and garment. Existing TEMPLE
# geometry is retained, so the upper seam cannot delete previously good art.
TEMPLE_ROWS = {
    'L': [(1110,1435,1596),(1140,1415,1595),(1170,1395,1584),
          (1200,1390,1555),(1250,1375,1514),(1300,1365,1487),
          (1350,1350,1467),(1400,1345,1449),(1450,1340,1428),
          (1488,1380,1408)],
    'R': [(1110,2248,2400),(1140,2248,2407),(1170,2263,2420),
          (1200,2304,2425),(1250,2340,2440),(1300,2360,2450),
          (1350,2379,2470),(1400,2396,2480),(1450,2412,2470),
          (1495,2433,2460)],
}


def _edges(triangles):
    return [v for edge in sorted({tuple(sorted(edge))
        for offset in range(0,len(triangles),3)
        for a,b,c in [triangles[offset:offset+3]]
        for edge in ((a,b),(b,c),(c,a))}) for v in edge]


def _strip(rows, model, parent_ref, columns=4):
    require(all(b[0]>a[0] for a,b in zip(rows,rows[1:])), 'Rows must ascend')
    require(all(left<right for _,left,right in rows), 'Strip must have width')
    world=[v for y,left,right in rows for col in range(columns+1)
           for v in (left+(right-left)*col/columns,y)]
    local=[ex._float32(v) for v in model.inverse_many(model.transform(parent_ref),world)]
    error=max(abs(a-b) for a,b in zip(world,model.forward_many(model.transform(parent_ref),local)))
    require(error<.001, 'Root neutral roundtrip exceeds 0.001px')
    uv=[v for x,y in zip(world[::2],world[1::2]) for v in (x/3840,y/4160)]
    triangles=[]
    for row in range(len(rows)-1):
        for col in range(columns):
            a=row*(columns+1)+col;b=a+1;c=a+columns+1;d=c+1
            triangles.extend((a,b,d,a,d,c))
    return [world,uv,local],triangles,error


def patch_with_audit(xml):
    """Return (candidate_xml, audit); preserve all unrelated existing blocks."""
    geometry=neutral_model(xml)
    root=ET.fromstring(xml)
    ids={n.get('xs.id'):n for n in root.find('shared')}
    names=[PREFIX+'BACK_'+side+'_LOWER' for side in ('L','R')]
    added_names=[PREFIX+'FRONT_TEMPLE_'+side+'_PAINT_RESTORED' for side in ('L','R')]
    require(not any(i.name in added_names for i in geometry.objects), 'Seam patch already applied')
    tip=one(geometry,PREFIX+'FRONT_PAINTED_TIP_L','art-mesh')
    tip_source=ids[tip.source_ref]
    tip_roles=clone_roles(root,tip_source,tip.name)
    tex={'texture_ref':named(tip_source,'GTexture2D','texture').get('xs.ref'),
         'model_image_guid_ref':named(ids[tip_roles['model-input']],'CModelImageGuid','_modelImageGuid').get('xs.ref')}
    tip_pos=values(direct(tip_source,'float-array','positions'))
    tip_uv=values(direct(tip_source,'float-array','uvs'))
    require(max(abs(p-u*(3840 if n%2==0 else 4160)) for n,(p,u) in enumerate(zip(tip_pos,tip_uv)))<.001,
            'Tip texture is not the expected full-canvas master')
    current=xml;records=[]
    for side,name in zip(('L','R'),names):
        item=one(geometry,name,'art-mesh');source=copy.deepcopy(ids[item.source_ref])
        require(len(direct(source,'carray_list','keyforms'))==1, 'Cannot replace animated LOWER source')
        require(named(source,'GTexture2D','texture').get('xs.ref')==tex['texture_ref'], 'Requires master-restored v30 LOWER')
        pieces=[]
        if side=='L':
            # Keep the accepted upper island; only reconstruct the low tuft.
            upper=copy.deepcopy(source)
            trim.trim_source(upper,[(0,0),(3840,0),(3840,1510),(0,1510)])
            pieces.append(_piece_arrays(upper))
        arrays,tris,error=_strip(LOWER_ROWS[side],geometry,item.parent_ref)
        pieces.append((arrays,tris));_merge(source,pieces)
        require(all(math.isfinite(v) for n in source.iter('float-array') for v in values(n)), 'Nonfinite LOWER geometry')
        current=ex._replace_exact(current,raw_source(xml,item),serialize(source),1,'Reconnect true lower root '+side)
        records.append({'name':name,'action':'replace_low_tuft_with_master_canvas_strip',
            'rows_canvas':LOWER_ROWS[side],'retained_upper_before_y':1510 if side=='L' else None,
            'maximum_neutral_error_px':error,'parent_unchanged':True,'texture_unchanged':True,
            'vertices':len(values(direct(source,'float-array','positions')))//2})
    template=ids[one(geometry,'JAD_R21_DRESS_BELT','art-mesh').source_ref]
    slots=secondary._allocate(root,[role(name,key) for name in added_names for key in clone_roles(root,template,name)])
    blocks=[];new_records=[]
    for side,name in zip(('L','R'),added_names):
        parent_item=one(geometry,PREFIX+'FRONT_TEMPLE_'+side,'art-mesh')
        # This is rear-hair underpainting beside the temple, not a front lock.
        # The front-global warp has no invertible domain this far outboard.
        # Use the same existing rear-side chain as the restored LOWER mesh.
        rear_item=one(geometry,PREFIX+'BACK_'+side+'_LOWER','art-mesh')
        arrays,tris,error=_strip(TEMPLE_ROWS[side],geometry,rear_item.parent_ref)
        world,uv,local=arrays
        new,record=clone_underpaint(root,template,name,slots,tex,world,local,uv,tris,_edges(tris),rear_item.parent_ref,499)
        part=named(ids[rear_item.source_ref],'CPartGuid','parentGuid').get('xs.ref')
        node=ET.fromstring(new[0]);named(node,'CPartGuid','parentGuid').set('xs.ref',part);new[0]=serialize(node)
        blocks+=new;record.update(part_ref=part,rows_canvas=TEMPLE_ROWS[side],maximum_neutral_error_px=error,
                                 companion_mesh=parent_item.name,rear_parent_mesh=rear_item.name,draw_order=499)
        new_records.append(record)
    current=ex._append_shared_blocks(current,blocks)
    current=partition._patch_drawable_source_set(current,[r['source_ref'] for r in new_records])
    for part in sorted({r['part_ref'] for r in new_records}):
        current=partition._patch_part_children(current,part_source_ref=partition._part_source_ref(root,part),
            drawable_refs=[r['drawable_ref'] for r in new_records if r['part_ref']==part],experiment=ex)
    for item in geometry.objects:
        if item.name not in names:
            require(raw_source(xml,item)==raw_source(current,item), 'Unrelated object source changed '+item.name)
    final=ET.fromstring(current)
    definitions=[n.get('xs.id') for n in final.iter() if n.get('xs.id')]
    require(len(definitions)==len(set(definitions)), 'Duplicate shared ids')
    require({n.get('xs.ref') for n in final.iter() if n.get('xs.ref')}<=set(definitions), 'Unresolved refs')
    return current,{'schema':'jade.r21.hair-seam-roots.v1','status':'candidate_requires_native_neutral_and_head_z_gate',
        'changed_existing':records,'new_meshes':new_records,'all_unrelated_object_sources_byte_identical':True,
        'original_temple_meshes_preserved':True,'raster_bytes_not_touched_by_xml_helper':True,
        'uses_only_existing_master_samples_at_identity_uv':True,
        'diagnosis':'Manifest dimensions are unpadded; former LOWER_L trim y=174 maps to canvas 1572.35 rather than 1548, cutting the painted root.',
        'limits':['Root contour boundaries were visually traced from the original RGBA master, not a semantic mask.',
                  'Native seam/cloth-leak checks at neutral and both HeadZ extremes remain mandatory.',
                  'No hidden hair has been invented under the garment; large relative hair/body motion can still expose missing underpainting.',
                  'TEMPLE overlap meshes are rear underpainting, parented to the existing left/right rear-hair roots rather than the front-lock warps.']}


def patch(xml):
    return patch_with_audit(xml)[0]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path);parser.add_argument('--audit',type=Path)
    args=parser.parse_args()
    data=args.source.read_bytes();require(sha(data)==SOURCE_SHA,'Requires pinned native v30')
    _,xml=model_from_bytes(data);changed,report=patch_with_audit(xml)
    candidate=safe._replace_main_xml(data,changed)
    before,after=CaffArchive.parse(data),CaffArchive.parse(candidate)
    for entry in before.entries:
        if entry.path!='main.xml':
            require(before.read_unique_path(entry.path,256*1024*1024)==after.read_unique_path(entry.path,256*1024*1024),'Raster/archive member changed')
    report.update(source_sha256=sha(data),candidate_xml_sha256=sha(changed),
                  all_non_main_archive_members_byte_identical=True,model_file_written=False)
    if args.audit:exclusive(args.audit,(json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
