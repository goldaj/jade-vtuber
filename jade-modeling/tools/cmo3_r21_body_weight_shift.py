#!/usr/bin/env python3
"""Rig coordinated full-body weight shift and independent skirt follow-through.

Five keys per control. Shoe vertices stay anchored through full-body shift;
the waist band stays fixed relative to the body through skirt-only motion.
No application code or raster editing. Requires the v26-derived hierarchy.
"""
from __future__ import annotations
import argparse
import copy
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
import cmo3_create_deformer_experiment as ex
import cmo3_secondary_professional as secondary
import cmo3_eye_closure_professional as eyes
import cmo3_reparent_preserve_canvas as canvas
import cmo3_safe_roundtrip as safe
from cmo3_r21_restore_eye_r_finite import require, sha, model_from_bytes, nonfinite_objects, raw_source, exclusive
from cmo3_r21_mouth_form_first_rig import MouthNeutralModel
from cmo3_r21_face_roots_to_head import one
from cmo3_r21_mouth_open_first_rig import binding_imports

KEYS=(-1.,-.5,0.,.5,1.)
SPECS=(
    ('D_JAD_FULLBODY_ROOT','ParamJadeWeightShift','Jade - Weight Shift','Feet anchored; coordinated body and hip shift'),
    ('D_JAD_LOWERBODY_SKIRT','ParamJadeSkirtSway','Jade - Skirt Sway','Independent cloth follow-through; waist band locked'),
)

def direct(node,tag,name):return canvas._one_direct_named(node,tag,name)
def named(node,tag,name):return ex._one_named(node,tag,name)
def numbers(node):return tuple(float(v) for v in (node.text or '').split())
def serialized(node):
    node.tail=None
    return ET.tostring(node,encoding='utf-8',short_empty_elements=True)
def set_positions(node,values):
    node.set('count',str(len(values)))
    node.text=' '.join(canvas._format_float32(v) for v in values)

def smooth(t):
    t=max(0.,min(1.,t))
    return t*t*(3.-2.*t)

def pose(name,points,key):
    if key==0.:return tuple(points)
    result=[]
    for x,y in zip(points[::2],points[1::2]):
        if name=='D_JAD_FULLBODY_ROOT':
            # All grid rows at/below 4000 are exactly stationary: both
            # complete shoes (including hidden ankle overlap) stay planted.
            w=1.-smooth((y-2300.)/1700.)
            dx=key*(90.+.012*(1950.-min(y,2300.)))*w
            dy=(12.*key*key+.006*key*(x-1907.))*w
        else:
            depth=smooth((y-2000.)/1050.)
            lateral=max(-1.,min(1.,(x-1907.)/720.))
            dx=key*(65.*depth+15.*(1.-lateral*lateral)*depth*depth)
            dy=24.*key*lateral*depth*depth
        result.extend((x+dx,y+dy))
    return tuple(result)

def positive_cells(model,item,positions):
    transform=model.transform(item.guid_ref)
    columns,rows=transform.columns,transform.rows
    p=np.asarray(positions).reshape(rows+1,columns+1,2)
    a=p[:-1,1:]-p[:-1,:-1]; b=p[1:,:-1]-p[:-1,:-1]
    c=p[1:,1:]-p[:-1,1:]; d=p[1:,:-1]-p[:-1,1:]
    cross=lambda u,v:u[...,0]*v[...,1]-u[...,1]*v[...,0]
    values=np.r_[cross(a,b).ravel(),cross(c,d).ravel()]
    require(float(values.min())>0.,item.name+': folded grid')
    return float(values.min())

def posed_model(xml, selections):
    """Read-only mirror choosing exact new warp keys for geometry assertions."""
    m=MouthNeutralModel(xml,.001)
    root=copy.deepcopy(m.root)
    by_ref={n.get('xs.id'):n for n in root.find('shared')}
    for name,_,_,_ in SPECS:
        item=one(m,name,'warp-deformer')
        forms=direct(by_ref[item.source_ref],'carray_list','keyforms')
        chosen=copy.deepcopy(forms[KEYS.index(selections.get(name,0.))])
        forms.clear();forms.set('xs.n','keyforms');forms.set('count','1');forms.append(chosen)
        grid_ref=named(by_ref[item.source_ref],'KeyformGridSource','keyformGridSource').get('xs.ref')
        grid=by_ref[grid_ref]
        bindings=direct(grid,'array_list','keyformBindings')
        bindings.clear();bindings.set('xs.n','keyformBindings');bindings.set('count','0')
        grid_forms=direct(grid,'array_list','keyformsOnGrid')
        selected=copy.deepcopy(grid_forms[KEYS.index(selections.get(name,0.))])
        grid_forms.clear();grid_forms.set('xs.n','keyformsOnGrid');grid_forms.set('count','1');grid_forms.append(selected)
    return MouthNeutralModel(ET.tostring(root,encoding='utf-8'),.001)

def bind_warp(xml,model,item,slots,param_ref,source_sha):
    original=model.source(item)
    forms=direct(original,'carray_list','keyforms')
    require(len(forms)==1,'Expected neutral-only hierarchy')
    base_form=forms[0]
    _,neutral_local=model.keyform_positions(item,require_single_unbound=True)
    neutral_ref=named(base_form,'CFormGuid','guid').get('xs.ref')
    parent=model.transform(item.parent_ref)
    neutral_world=model.forward_many(parent,neutral_local)
    require(canvas._maximum_error(neutral_world,model.original_canvas(item))<.001,'Hierarchy neutral not intact')
    name=item.name
    grid_ref,grid_idx=slots[name+':grid']; binding_ref,binding_idx=slots[name+':binding']
    form_refs=[neutral_ref if k==0. else slots[name+':form:'+str(k)][0] for k in KEYS]
    changed=copy.deepcopy(original)
    owner=next(n for n in changed.iter() if any(c.tag=='KeyformGridSource' and c.get('xs.n')=='keyformGridSource' for c in n))
    grid=named(changed,'KeyformGridSource','keyformGridSource')
    idx=list(owner).index(grid);owner.remove(grid)
    owner.insert(idx,ET.Element('KeyformGridSource',{'xs.n':'keyformGridSource','xs.ref':grid_ref}))
    changed_forms=direct(changed,'carray_list','keyforms')
    changed_forms.clear();changed_forms.set('xs.n','keyforms');changed_forms.set('count',str(len(KEYS)))
    checks=[]
    for key,ref in zip(KEYS,form_refs):
        world=pose(name,neutral_world,key)
        local=neutral_local if key==0. else model.inverse_many(parent,world)
        form=copy.deepcopy(base_form)
        named(form,'CFormGuid','guid').set('xs.ref',ref)
        if key!=0.:set_positions(direct(form,'float-array','positions'),local)
        changed_forms.append(form)
        error=canvas._maximum_error(world,model.forward_many(parent,numbers(direct(form,'float-array','positions'))))
        require(error<.001,'Pose conversion error')
        checks.append({'key':key,'roundtrip_error':error,'minimum_triangle_area2':positive_cells(model,item,world)})
    require(numbers(direct(changed_forms[2],'float-array','positions'))==neutral_local,'Neutral changed')
    current=ex._replace_exact(xml,raw_source(xml,item),serialized(changed),1,'Bind body control '+name)
    blocks=[secondary._grid_block(grid_ref=grid_ref,grid_idx=grid_idx,binding_refs=[binding_ref],
        accesses=[(i,) for i in range(len(KEYS))],form_refs=form_refs),
        eyes._new_binding_block(grid_ref=grid_ref,binding_ref=binding_ref,binding_idx=binding_idx,parameter_ref=param_ref,keys=KEYS)]
    for key in KEYS:
        if key!=0.:blocks.append(secondary._form_guid_block(*slots[name+':form:'+str(key)],source_sha,name+':key:'+str(key)))
    return current,blocks,{'deformer':name,'keys':KEYS,'neutral_local_exact':True,'poses':checks}

def plan(source,expected_sha):
    data=source.read_bytes();require(sha(data)==expected_sha,'Unexpected hierarchy checkpoint')
    _,xml=model_from_bytes(data);before=MouthNeutralModel(xml,.001)
    require(not nonfinite_objects(before),'Nonfinite input')
    require(len([o for o in before.objects if o.object_type=='art-mesh'])==66,'Expected full-body meshes')
    roles=[]
    for name,param,_,_ in SPECS:
        require(not any(n.get('idstr')==param for n in before.root.iter('CParameterId')),'Parameter already exists')
        roles += [param+':guid',param+':id',name+':grid',name+':binding']
        roles += [name+':form:'+str(k) for k in KEYS if k!=0.]
    slots=secondary._allocate(before.root,roles)
    current=xml;blocks=[];sources=[];parameter_refs=[];records=[]
    for name,param,label,description in SPECS:
        guid_ref,guid_idx=slots[param+':guid'];id_ref,id_idx=slots[param+':id']
        blocks += [secondary._parameter_guid_block(guid_ref,guid_idx,expected_sha,param),secondary._parameter_id_block(id_ref,id_idx,param)]
        sources.append(secondary._parameter_source(guid_ref,id_ref,label,description));parameter_refs.append(guid_ref)
        current,added,record=bind_warp(current,before,one(before,name,'warp-deformer'),slots,guid_ref,expected_sha)
        record['parameter_id']=param;blocks+=added;records.append(record)
    current=ex._append_shared_blocks(current,blocks)
    current=secondary._append_parameter_sources(current,sources)
    current=secondary._append_root_parameter_children(current,parameter_refs,experiment=ex)
    current=binding_imports(current)
    neutral=posed_model(current,{})
    max_neutral_error=0.
    for item in before.objects:
        if item.object_type!='art-mesh':continue
        # Existing multi-key artwork remains untouched; use immutable neutral
        # canvas locations mapped through its original neutral parent chain.
        original=before.original_canvas(item)
        parent=before.transform(item.parent_ref)
        if item.name.startswith(('JAD_R21_SHORT_SKIRT','JAD_R21_LEG_','JAD_R21_SHOE_')):
            _,local=before.keyform_positions(item,require_single_unbound=True)
            moved=neutral.forward_many(neutral.transform(item.parent_ref),local)
            max_neutral_error=max(max_neutral_error,canvas._maximum_error(original,moved))
    require(max_neutral_error<.001,'Neutral body positions moved')
    anchor=[]
    for key in (-1.,1.):
        sample=posed_model(current,{'D_JAD_FULLBODY_ROOT':key})
        maximum=0.
        for name in ('JAD_R21_SHOE_R_V3','JAD_R21_SHOE_L_V3'):
            item=one(before,name,'art-mesh');_,local=before.keyform_positions(item,require_single_unbound=True)
            points=sample.forward_many(sample.transform(item.parent_ref),local)
            baseline=neutral.forward_many(neutral.transform(item.parent_ref),local)
            maximum=max(maximum,canvas._maximum_error(points,baseline))
        require(maximum<.001,'Weight shift slides shoes')
        anchor.append({'weight_shift':key,'maximum_shoe_axis_displacement_px':maximum})
    changed_names={name for name,_,_,_ in SPECS}
    for item in before.objects:
        if item.name not in changed_names:require(raw_source(xml,item)==raw_source(current,item),'Unrelated rig source changed: '+item.name)
    result=safe._replace_main_xml(data,current)
    a,_,_,_,_=safe._validate_surgical_layout(data);b,_,_,_,decoded=safe._validate_surgical_layout(result)
    require(decoded==current,'Archive roundtrip differs')
    preserved=safe._compare_entry_preservation(data,a,result,b,main_may_change=True)
    require(preserved['all_non_main_entries_byte_identical'],'Raster changed')
    require(not nonfinite_objects(neutral),'Nonfinite output')
    return result,{'schema':'jade.r21.body-weight-shift.v1','status':'candidate_requires_native_pose_gate',
        'source':str(source),'source_sha256':expected_sha,'output_sha256':sha(result),
        'controls':records,'maximum_neutral_body_error_px':max_neutral_error,'foot_anchors':anchor,
        'all_artmesh_sources_unchanged':True,'all_rasters_unchanged':True,
        'remaining':['Native body and skirt controls','Calf/ankle secondary motion','Fine art seams','VTS export/physics']}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path);p.add_argument('--expected-sha',required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--audit',type=Path,required=True)
    a=p.parse_args();require(not a.output.exists() and not a.audit.exists(),'Refusing overwrite')
    result,report=plan(a.source,a.expected_sha.upper())
    exclusive(a.output,result);exclusive(a.audit,(json.dumps(report,indent=2)+'\n').encode())
    print(json.dumps({'output':str(a.output),'sha256':sha(result),'status':report['status'],'controls':[r['parameter_id'] for r in report['controls']]}))
