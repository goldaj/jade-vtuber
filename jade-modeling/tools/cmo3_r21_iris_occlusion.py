#!/usr/bin/env python3
"""Replace whole-eye squash with stationary artwork + native moving aperture.

No bitmap is repainted. A same-texture eyelid frame uses reverse clipping;
the untouched full-size eye is clipped normally by the same aperture. True
CLOSED_TRUE sprites, unrelated objects, and every archive raster survive.
This is a first native masking candidate, not a claim of final visual QA.
"""
from __future__ import annotations
import argparse
import collections
import copy
import json
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
import cmo3_create_deformer_experiment as experiment
import cmo3_eye_closure_professional as eye
import cmo3_reparent_preserve_canvas as canvas
import cmo3_secondary_professional as secondary
import cmo3_safe_roundtrip as safe
import cmo3_hair_art_partition_r16 as partition
import cmo3_r21_clone_artmesh as cloning
import cmo3_r21_mesh_polygon_trim as trim
from cmo3_r21_restore_eye_r_finite import require, sha, model_from_bytes, nonfinite_objects, raw_source, exclusive
from cmo3_r21_face_roots_to_head import one
from cmo3_r21_mouth_form_first_rig import MouthNeutralModel
from cmo3_r21_true_closed_blink import KEYS, contour, open_pose

SOURCE_SHA = 'CE5C07E3C3B080C48E9646A8CE2BBE85786703F6AA78781D46D20A64E94A505B'
HANDOFF = (0.0, .35, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
# Interior aperture contours in each existing eye bitmap's pixel space.
# These are mask mesh vertices, not newly painted eye/eyelash artwork.
APERTURES = {
    'L': [(21,111),(24,96),(33,86),(48,79),(68,77),(91,80),(113,87),(131,97),(141,106),
          (136,126),(128,143),(116,157),(98,165),(78,169),(57,170),(40,165),(27,155),(20,136)],
    'R': [(62,107),(75,98),(92,88),(111,80),(134,77),(157,80),(175,89),(187,102),
          (189,126),(184,146),(174,160),(158,168),(137,170),(115,167),(96,159),(81,146),(70,128)]
}
OFFSETS = {'L': (1978,652), 'R': (1654,652)}
# Restrict the deforming frame to the actual painted eye. Imported OPEN art
# has connected transparent bridges leading to hair and brow fragments.
FRAME_POLYGONS = {
    'L': [(4,111),(9,87),(22,75),(38,63),(59,54),(84,55),(111,60),(134,69),
          (153,87),(160,105),(151,128),(139,149),(124,166),(105,177),(56,179),(28,170),(17,149)],
    'R': [(44,109),(50,92),(68,76),(90,61),(112,56),(135,54),(157,58),(179,71),
          (198,95),(200,118),(195,144),(180,168),(157,181),(115,180),(86,164),(66,141)]
}

def direct(node, tag, name):
    return canvas._one_direct_named(node, tag, name)

def named(node, tag, name):
    return experiment._one_named(node, tag, name)

def values(node):
    return tuple(float(v) for v in (node.text or '').split())

def set_array(node, items, integer=False):
    items = list(items)
    node.set('count', str(len(items)))
    node.text = ' '.join(str(int(v)) if integer else canvas._format_float32(v) for v in items)

def serialize(node):
    node.tail = None
    return ET.tostring(node, encoding='utf-8', short_empty_elements=True)

def aperture_mesh(side):
    boundary = APERTURES[side]
    center = tuple(sum(p[k] for p in boundary)/len(boundary) for k in (0,1))
    offset = OFFSETS[side]
    xy = tuple(v+offset[k] for p in [center,*boundary] for k,v in enumerate(p))
    count = len(boundary)
    indices = tuple(v for n in range(count) for v in (0,n+1,(n+1)%count+1))
    areas = signed_areas(xy, indices)
    require(all(a>0 for a in areas), 'Aperture polygon is not a positive star fan')
    edges = sorted({tuple(sorted((t[a],t[b]))) for k in range(0,len(indices),3)
                    for t in [indices[k:k+3]] for a,b in ((0,1),(1,2),(2,0))})
    return xy, indices, tuple(v for e in edges for v in e)

def signed_areas(points, indices):
    p = np.asarray(points).reshape(-1,2)
    tris = p[np.asarray(indices).reshape(-1,3)]
    a,b = tris[:,1]-tris[:,0], tris[:,2]-tris[:,0]
    return (a[:,0]*b[:,1]-a[:,1]*b[:,0]).tolist()

def replace_geometry(source, original, uvs, indices, edges):
    set_array(direct(source,'float-array','positions'),original)
    set_array(direct(source,'float-array','uvs'),uvs)
    set_array(direct(source,'int-array','indices'),indices,True)
    editable = named(source,'GEditableMesh2','editableMesh')
    n = len(original)//2
    editable.set('nextPointUid',str(n))
    set_array(direct(editable,'float-array','point'),original)
    set_array(direct(editable,'byte-array','pointPriority'),[10]*n,True)
    set_array(direct(editable,'int-array','pointUid'),range(n),True)
    set_array(direct(editable,'short-array','edge'),edges,True)
    set_array(direct(editable,'byte-array','edgePriority'),[30]*(len(edges)//2),True)

def keep_primary_eye_component(frame, side):
    """Remove detached hair/skin islands, not the actual painted eyelash mesh."""
    indices = [int(v) for v in direct(frame,'int-array','indices').text.split()]
    triangles = [indices[i:i+3] for i in range(0,len(indices),3)]
    graph = collections.defaultdict(set)
    for tri in triangles:
        for a,b in ((0,1),(1,2),(2,0)):
            graph[tri[a]].add(tri[b]); graph[tri[b]].add(tri[a])
    todo, components = set(graph), []
    while todo:
        stack = [todo.pop()]; component = set(stack)
        while stack:
            adjacent = graph[stack.pop()] & todo
            todo -= adjacent; component |= adjacent; stack.extend(adjacent)
        components.append(component)
    components.sort(key=len,reverse=True)
    if len(components)==1:
        return {'removed_component_sizes':[],'note':'Single connected mesh; no automatic pruning'}
    original = values(direct(frame,'float-array','positions'))
    center = (OFFSETS[side][0]+(68 if side=='L' else 140), OFFSETS[side][1]+120)
    nearest = min(range(len(original)//2),key=lambda i:(original[2*i]-center[0])**2+(original[2*i+1]-center[1])**2)
    require(nearest in components[0],'Largest component does not contain the eye interior')
    keep = [i for i,tri in enumerate(triangles) if set(tri)<=components[0]]
    report = partition._subset_source(frame,keep,'eye-frame-'+side)
    report['removed_component_sizes'] = [len(c) for c in components[1:]]
    return report

def plan(source: Path, assets: Path):
    data = source.read_bytes()
    require(sha(data)==SOURCE_SHA,'Expected native v24 checkpoint')
    _, xml = model_from_bytes(data)
    before = MouthNeutralModel(xml,.001)
    originals = {s:one(before,f'JAD_R21_EYE_{s}_OPEN_MASTER','art-mesh') for s in ('L','R')}
    roles = []
    for side,item in originals.items():
        for kind in ('APERTURE_MASK','LID_FRAME'):
            roles.extend(cloning.allocation_roles(before.root,before.source(item),f'JAD_R21_EYE_{side}_{kind}'))
    slots = secondary._allocate(before.root,roles)
    current, shared, new_sources, part_additions, records = xml, [], [], {}, []
    for side,item in originals.items():
        old_source = before.source(item)
        semantics = eye._generic_grid_semantics(before.root,before,item,experiment)
        require(tuple(semantics['keys'][0])==KEYS,'Unexpected blink grid')
        ref_to_key = {semantics['access_to_ref'][(i,)]:k for i,k in enumerate(KEYS)}
        old_forms = direct(old_source,'carray_list','keyforms')
        ordered_keys = [ref_to_key[named(f,'CFormGuid','guid').get('xs.ref')] for f in old_forms]
        full_form = next(f for f,k in zip(old_forms,ordered_keys) if k==1)
        full_local = values(direct(full_form,'float-array','positions'))
        parent = before.transform(item.parent_ref)
        full_world = before.forward_many(parent,full_local)
        require(canvas._maximum_error(full_world,before.original_canvas(item))<.001,'Open endpoint shifted')
        clones = {}
        for kind in ('APERTURE_MASK','LID_FRAME'):
            name = f'JAD_R21_EYE_{side}_{kind}'
            blocks, info = cloning.clone(before.root,old_source,name,sha(data),slots)
            node = ET.fromstring(blocks[0])
            clones[kind] = (node,blocks[1:],info)
            new_sources.append(info['source_ref'])
            part_ref = named(node,'CPartGuid','parentGuid').get('xs.ref')
            part_additions.setdefault(part_ref,[]).append(info['drawable_guid_ref'])
        mask,mask_tail,mask_info = clones['APERTURE_MASK']
        frame,frame_tail,frame_info = clones['LID_FRAME']
        mask_ref = mask_info['drawable_guid_ref']
        original,indices,edges = aperture_mesh(side)
        # Sample a tiny opaque patch within the EXISTING iris texture. Color is
        # immaterial: native clipping reads texture alpha even at form opacity 0.
        uvs = tuple(v for _ in range(len(original)//2) for v in ((.27 if side=='L' else .56),.62))
        replace_geometry(mask,original,uvs,indices,edges)
        curve = contour(assets,side)
        poses = []
        for f,key in zip(direct(mask,'carray_list','keyforms'),ordered_keys):
            world = open_pose(original,key,curve)
            local = before.inverse_many(parent,world)
            set_array(direct(f,'float-array','positions'),local)
            named(f,'f','opacity').text='0.0'
            observed = before.forward_many(parent,tuple(canvas._float32(v) for v in local))
            require(canvas._maximum_error(observed,world)<.001,'Aperture parent inverse differs')
            require(min(signed_areas(observed,indices))>0,'Aperture folds')
            poses.append((key,observed))
        polygon = [(x+OFFSETS[side][0],y+OFFSETS[side][1]) for x,y in FRAME_POLYGONS[side]]
        frame_cleanup = trim.trim_source(frame,polygon)
        cloning.set_mask(frame,mask_ref,True)
        interior = copy.deepcopy(old_source)
        cloning.set_mask(interior,mask_ref,False)
        for f,key in zip(direct(interior,'carray_list','keyforms'),ordered_keys):
            # All 11 poses use EXACT full-open local vertices. Iris, pupil and
            # highlights cannot geometrically squash when EyeOpen changes.
            set_array(direct(f,'float-array','positions'),full_local)
            named(f,'f','opacity').text = str(HANDOFF[KEYS.index(key)])
        for f,key in zip(direct(frame,'carray_list','keyforms'),ordered_keys):
            named(f,'f','opacity').text = str(HANDOFF[KEYS.index(key)])
        closed_item = one(before,f'JAD_R21_EYE_{side}_CLOSED_TRUE','art-mesh')
        closed = copy.deepcopy(before.source(closed_item))
        closed_sem = eye._generic_grid_semantics(before.root,before,closed_item,experiment)
        closed_keys = {ref:KEYS[access[0]] for access,ref in closed_sem['access_to_ref'].items()}
        for f in direct(closed,'carray_list','keyforms'):
            key = closed_keys[named(f,'CFormGuid','guid').get('xs.ref')]
            named(f,'f','opacity').text = str(1.0-HANDOFF[KEYS.index(key)])
        current = experiment._replace_exact(current,raw_source(current,closed_item),serialize(closed),1,'Short closed-art handoff '+side)
        changed = serialize(interior)
        current = experiment._replace_exact(current,raw_source(current,item),changed,1,'Stable iris '+side)
        shared.extend([serialize(mask),*mask_tail,serialize(frame),*frame_tail])
        records.append({'side':side,'stationary_eye':item.name,'mask':mask_info,'frame':frame_info,
                        'all_11_interior_local_poses_identical':True,'mask_vertices':len(original)//2,
                        'mask_keys':KEYS,'mask_form_opacity':0,'frame_cleanup':frame_cleanup,
                        'handoff_end':.04,'native_clipping_gate_required':True})
    current = experiment._append_shared_blocks(current,shared)
    current = partition._patch_drawable_source_set(current,new_sources)
    for part_ref,guids in part_additions.items():
        current = partition._patch_part_children(current,part_source_ref=partition._part_source_ref(before.root,part_ref),
                        drawable_refs=guids,experiment=experiment)
    after = MouthNeutralModel(current,.001)
    require(not nonfinite_objects(after),'Nonfinite geometry')
    require(len(after.objects)==len(before.objects)+4,'Missing cloned meshes')
    for item in before.objects:
        if item.name not in {i.name for i in originals.values()} | {'JAD_R21_EYE_L_CLOSED_TRUE','JAD_R21_EYE_R_CLOSED_TRUE'}:
            require(raw_source(xml,item)==raw_source(current,item),'Unrelated source changed: '+item.name)
    for side in ('L','R'):
        node = after.source(one(after,f'JAD_R21_EYE_{side}_OPEN_MASTER','art-mesh'))
        poses=[values(direct(f,'float-array','positions')) for f in direct(node,'carray_list','keyforms')]
        require(all(p==poses[0] for p in poses),'Iris pose is not stable')
        old_closed = before.source(one(before,f'JAD_R21_EYE_{side}_CLOSED_TRUE','art-mesh'))
        new_closed = after.source(one(after,f'JAD_R21_EYE_{side}_CLOSED_TRUE','art-mesh'))
        for old_f,new_f in zip(direct(old_closed,'carray_list','keyforms'),direct(new_closed,'carray_list','keyforms')):
            require(values(direct(old_f,'float-array','positions'))==values(direct(new_f,'float-array','positions')),'True closed geometry changed')
    output=safe._replace_main_xml(data,current)
    a,_,_,_,_=safe._validate_surgical_layout(data);b,_,_,_,decoded=safe._validate_surgical_layout(output)
    require(decoded==current,'Decoded XML differs')
    preserved=safe._compare_entry_preservation(data,a,output,b,main_may_change=True)
    require(preserved['all_non_main_entries_byte_identical'],'Texture changed')
    return output,{'schema':'jade.r21.iris-occlusion.v1','status':'candidate_requires_native_clipping_and_visual_gate',
        'source':str(source),'source_sha256':sha(data),'output_sha256':sha(output),'eyes':records,
        'all_raster_assets_unchanged':True,'all_true_closed_geometry_unchanged':True,
        'limitations':['Aperture boundary first trace requires native visual refinement','Short complementary endpoint alpha handoff 0-.04'],
        'archive':preserved}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--audit',type=Path,required=True)
    p.add_argument('--assets',type=Path,default=Path('assets/live2d/r21_professional_art'))
    a=p.parse_args();require(not a.output.exists() and not a.audit.exists(),'Refusing overwrite')
    output,report=plan(a.source.resolve(strict=True),a.assets.resolve(strict=True))
    exclusive(a.output,output);exclusive(a.audit,(json.dumps(report,indent=2)+'\n').encode())
    print(json.dumps({'output':str(a.output),'sha256':sha(output),'status':report['status']}))

if __name__=='__main__':main()
