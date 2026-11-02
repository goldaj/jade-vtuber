#!/usr/bin/env python3
"""Versioned front-hair rig: individual leaves, fixed roots, five curved poses.

Uses native v30 artwork verbatim. Painted white tips travel with their upper
locks. These are authored output controls, not yet a physics installation.
"""
import argparse
import copy
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET
import cmo3_create_deformer_experiment as ex
import cmo3_secondary_professional as secondary
import cmo3_eye_closure_professional as eyes
import cmo3_safe_roundtrip as safe
import cmo3_reparent_preserve_canvas as canvas
from cmo3_inventory import CaffArchive
from cmo3_r21_head_z_v28 import neutral_model
from cmo3_r21_lowerbody_hierarchy import _clone_warp, _grid
from cmo3_r21_body_weight_shift import direct, named, numbers, set_positions, positive_cells
from cmo3_r21_fullbody_first_assembly import serialize
from cmo3_r21_face_roots_to_head import one
from cmo3_r21_mouth_open_first_rig import binding_imports
from cmo3_r21_restore_eye_r_finite import require, sha, model_from_bytes, raw_source, exclusive

SOURCE_SHA='2AFC3C21F451626156B138733D0BC792CEB3463E086FA21334307FFC8B73A1EE'
KEYS=(-1.,-.5,0.,.5,1.)
P='JAD_R21_HAIR_FRONT_'
# Token, actual ArtMeshes, tip excursion in canvas px, root at bottom.
SPECS=[
 ('LockL',[P+'LOCK_L',P+'PAINTED_TIP_L'],85.,False),
 ('LockR',[P+'LOCK_R',P+'PAINTED_TIP_R'],92.,False),
 ('BangLOuter',[P+'BANG_L_OUTER'],58.,False),
 ('BangLInner',[P+'BANG_L_INNER'],42.,False),
 ('BangCenterL',[P+'BANG_CENTER_L'],28.,False),
 ('BangCenterR',[P+'BANG_CENTER_R'],32.,False),
 ('BangRInner',[P+'BANG_R_INNER'],46.,False),
 ('BangROuter',[P+'BANG_R_OUTER'],64.,False),
 ('Ahoge',['JAD_R21_HAIR_AHOGE'],68.,True),
]

def leaf(token): return 'D_JAD_HAIR_LEAF_'+token
def parameter(token): return 'ParamJadeHair'+token

def select_hair(xml,selections=None):
    """Read-only pose mirror; never serialize it into a deliverable."""
    selections=selections or {};root=ex._parse_xml(xml);ids=ex._id_map(root)
    for token,_,_,_ in SPECS:
        found=[s for s in root.find('shared').findall('CWarpDeformerSource')
               if named(s,'s','localName').text==leaf(token)]
        if not found: continue
        source=found[0];forms=direct(source,'carray_list','keyforms')
        if len(forms)==1: continue
        i=KEYS.index(selections.get(token,0.));chosen=copy.deepcopy(forms[i])
        forms.clear();forms.attrib.update({'xs.n':'keyforms','count':'1'});forms.append(chosen)
        grid=ids[named(source,'KeyformGridSource','keyformGridSource').get('xs.ref')]
        bindings=direct(grid,'array_list','keyformBindings')
        bindings.clear();bindings.attrib.update({'xs.n':'keyformBindings','count':'0'})
        entries=direct(grid,'array_list','keyformsOnGrid');chosen=copy.deepcopy(entries[i])
        entries.clear();entries.attrib.update({'xs.n':'keyformsOnGrid','count':'1'});entries.append(chosen)
    return neutral_model(ET.tostring(root,encoding='utf-8'))

def pose(points,key,bounds,amplitude,reverse):
    left,top,right,bottom=bounds;out=[]
    for x,y in zip(points[::2],points[1::2]):
        u=(bottom-y if reverse else y-top)/(bottom-top)
        t=max(0.,min(1.,(u-.20)/.80))
        # Curvature and its first derivative vanish at the anchored root.
        w=t*t*(2.-t)
        dx=amplitude*key*w
        dy=(1. if reverse else -1.)*.18*amplitude*key*key*t*t
        out.extend((x+dx,y+dy))
    return tuple(out)

def bind(current,model,item,slots,param_ref,bounds,amplitude,reverse):
    source=model.source(item);base=direct(source,'carray_list','keyforms')[0]
    _,local=model.keyform_positions(item,require_single_unbound=True)
    parent=model.transform(item.parent_ref);world=model.forward_many(parent,local)
    name=item.name;grid_ref,grid_idx=slots[name+':grid'];br,bi=slots[name+':binding']
    neutral_ref=named(base,'CFormGuid','guid').get('xs.ref')
    refs=[neutral_ref if k==0 else slots[name+':form:'+str(k)][0] for k in KEYS]
    changed=copy.deepcopy(source)
    owner=next(n for n in changed.iter() if any(c.tag=='KeyformGridSource' and c.get('xs.n')=='keyformGridSource' for c in n))
    old=named(changed,'KeyformGridSource','keyformGridSource');index=list(owner).index(old);owner.remove(old)
    owner.insert(index,ET.Element('KeyformGridSource',{'xs.n':'keyformGridSource','xs.ref':grid_ref}))
    forms=direct(changed,'carray_list','keyforms');forms.clear();forms.attrib.update({'xs.n':'keyforms','count':'5'})
    checks=[]
    for key,ref in zip(KEYS,refs):
        target=pose(world,key,bounds,amplitude,reverse)
        coords=list(local if key==0 else model.inverse_many(parent,target))
        for j in range(0,len(world),2):
            if target[j:j+2]==world[j:j+2]:coords[j:j+2]=local[j:j+2]
        form=copy.deepcopy(base);named(form,'CFormGuid','guid').set('xs.ref',ref)
        if key!=0:set_positions(direct(form,'float-array','positions'),coords)
        forms.append(form)
        error=canvas._maximum_error(target,model.forward_many(parent,numbers(direct(form,'float-array','positions'))))
        require(error<.001,'Pose conversion failed '+name)
        checks.append({'key':key,'error_px':error,'min_cell_area2':positive_cells(model,item,target)})
    current=ex._replace_exact(current,raw_source(current,item),serialize(changed),1,'Independent hair '+name)
    blocks=[secondary._grid_block(grid_ref=grid_ref,grid_idx=grid_idx,binding_refs=[br],accesses=[(i,) for i in range(5)],form_refs=refs),
        eyes._new_binding_block(grid_ref=grid_ref,binding_ref=br,binding_idx=bi,parameter_ref=param_ref,keys=KEYS)]
    blocks += [secondary._form_guid_block(*slots[name+':form:'+str(k)],SOURCE_SHA,name+':'+str(k)) for k in KEYS if k!=0]
    return current,blocks,checks

def build(source,output,audit,seam_roots=False):
    require(not output.exists() and not audit.exists(),'Refusing overwrite')
    data=source.read_bytes();require(sha(data)==SOURCE_SHA,'Requires native v30')
    original,xml=model_from_bytes(data);before=neutral_model(xml);root=original.root
    template=ex._warp_info(root,'D_JAD_HAIR_FRONT_ROOT')
    jobs=[];roles=[];tracked={}
    for token,names,amplitude,reverse in SPECS:
        meshes=[one(before,n,'art-mesh') for n in names];world=[]
        for mesh in meshes:
            _,local=before.keyform_positions(mesh,require_single_unbound=True)
            pts=before.forward_many(before.transform(mesh.parent_ref),local)
            tracked[mesh.name]=pts;world+=list(pts)
        bounds=(min(world[::2]),min(world[1::2]),max(world[::2]),max(world[1::2]))
        # Existing tiny legacy grids cannot contain the new swing envelopes.
        # Attach leaves to the existing head rotation, compensate canvas
        # coordinates, and keep old static grids intact for other children.
        parent=one(before,'R_JAD_HEAD_Z','rotation-deformer').guid_ref
        part=named(before.source(meshes[0]),'CPartGuid','parentGuid').get('xs.ref')
        jobs.append((token,names,amplitude,reverse,bounds,parent,part))
        n=leaf(token);p=parameter(token)
        require(not any(o.name==n for o in before.objects),'Leaf already exists')
        roles += ['lowerbody:'+n+':'+r for r in ('source','positions','form','guid')]
        roles += [p+':guid',p+':id',n+':grid',n+':binding']+[n+':form:'+str(k) for k in KEYS if k!=0]
    slots=secondary._allocate(root,roles);current=xml;records=[]
    for token,names,amplitude,reverse,bounds,parent,part in jobs:
        n=leaf(token);p=parameter(token)
        padded=(bounds[0]-32,bounds[1]-32,bounds[2]+32,bounds[3]+32)
        grid=_grid(padded,(4,8));local=before.inverse_many(before.transform(parent),grid)
        blocks,record=_clone_warp(root,template,n,slots,parent,part,grid,local,(4,8))
        current=ex._append_shared_blocks(current,blocks)
        current=ex._patch_deformer_source_set(current,record['source_ref'])
        current=ex._patch_part_hierarchy(current,part,record['guid_ref'])
        record.update(token=token,meshes=names,parameter_id=p,art_bounds=bounds,amplitude_px=amplitude,root_at_bottom=reverse)
        records.append(record)
    hierarchy=neutral_model(current)
    for record in records:
        parent=one(hierarchy,record['name'])
        for name in record['meshes']:
            item=one(hierarchy,name,'art-mesh');node=copy.deepcopy(hierarchy.source(item))
            local=hierarchy.inverse_many(hierarchy.transform(parent.guid_ref),tracked[name])
            forms=direct(node,'carray_list','keyforms')
            set_positions(direct(forms[0],'float-array','positions'),local)
            named(node,'CDeformerGuid','targetDeformerGuid').set('xs.ref',parent.guid_ref)
            current=ex._replace_exact(current,raw_source(current,item),serialize(node),1,'Reparent '+name)
    hierarchy=neutral_model(current);blocks=[];params=[];refs=[]
    for record in records:
        p=record['parameter_id'];pr,pi=slots[p+':guid'];ir,ii=slots[p+':id']
        blocks += [secondary._parameter_guid_block(pr,pi,SOURCE_SHA,p),secondary._parameter_id_block(ir,ii,p)]
        params.append(secondary._parameter_source(pr,ir,'Jade Hair '+record['token'],'Independent curved strand output; fixed root; physics pending'))
        refs.append(pr)
        current,added,checks=bind(current,hierarchy,one(hierarchy,record['name']),slots,pr,record['art_bounds'],record['amplitude_px'],record['root_at_bottom'])
        blocks+=added;record['pose_checks']=checks
    current=ex._append_shared_blocks(current,blocks)
    current=secondary._append_parameter_sources(current,params)
    current=secondary._append_root_parameter_children(current,refs,experiment=ex)
    current=binding_imports(current);after=select_hair(current)
    errors={}
    for name,world in tracked.items():
        item=one(after,name,'art-mesh');_,local=after.keyform_positions(item,require_single_unbound=True)
        error=canvas._maximum_error(world,after.forward_many(after.transform(item.parent_ref),local))
        require(error<.001,'Neutral moved '+name);errors[name]=error
    for item in original.objects:
        if item.name not in tracked: require(raw_source(xml,item)==raw_source(current,item),'Unrelated object changed '+item.name)
    seam_report=None
    if seam_roots:
        from cmo3_r21_hair_seam_roots import patch_with_audit
        current,seam_report=patch_with_audit(current)
    final=ex._parse_xml(current)
    definitions=[n.get('xs.id') for n in final.iter() if n.get('xs.id')]
    references=[n.get('xs.ref') for n in final.iter() if n.get('xs.ref')]
    uuids=[n.get('uuid') for n in final.iter() if n.get('uuid')]
    require(len(definitions)==len(set(definitions)) and set(references)<=set(definitions),'Invalid references')
    require(len(uuids)==len(set(uuids)),'UUID collision')
    result=safe._replace_main_xml(data,current);a,b=CaffArchive.parse(data),CaffArchive.parse(result)
    for e in a.entries:
        if e.path!='main.xml':require(a.read_unique_path(e.path,256*1024*1024)==b.read_unique_path(e.path,256*1024*1024),'Raster changed')
    report={'status':'candidate_requires_native_gate','source_sha256':SOURCE_SHA,'output_sha256':sha(result),
        'leaves':records,'neutral_mesh_errors_px':errors,'all_raster_bytes_preserved':True,
        'unrelated_sources_unchanged':True,'seam_roots':seam_report,
        'remaining':['Native poses and save','Rear seam finish and rear leaves','Physics and combined-pose finish']}
    exclusive(output,result);exclusive(audit,(json.dumps(report,indent=2)+'\n').encode())
    print(json.dumps({'output':str(output),'sha256':sha(result),'leaf_count':len(records),'new_keys':len(records)*5,'neutral_max_error_px':max(errors.values())}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--audit',type=Path,required=True)
    p.add_argument('--seam-roots',action='store_true')
    a=p.parse_args();build(a.source,a.output,a.audit,a.seam_roots)
