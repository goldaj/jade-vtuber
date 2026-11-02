#!/usr/bin/env python3
"""First leg relaxation and thoracic breathing keys, copy-only from native v27.

Leg rows translate sideways without narrowing; upper thighs and complete shoes
stay anchored. Breath moves the head rigidly and expands the chest very gently.
No raster edits, no application changes. Native pose observation still required.
"""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import cmo3_create_deformer_experiment as ex
import cmo3_secondary_professional as secondary
import cmo3_eye_closure_professional as eyes
import cmo3_reparent_preserve_canvas as canvas
import cmo3_safe_roundtrip as safe
import cmo3_r21_body_weight_shift as body
from cmo3_r21_body_weight_shift import direct, named, numbers, serialized, set_positions
from cmo3_r21_restore_eye_r_finite import require, sha, model_from_bytes, nonfinite_objects, raw_source, exclusive
from cmo3_r21_mouth_form_first_rig import MouthNeutralModel
from cmo3_r21_face_roots_to_head import one

SOURCE_SHA='580FABAA25A56EE55DBFA4BB0F0ADAC6DD4FA3C04E17019BB18AD24AC4C90030'
KEYS=(0.,.5,1.)
SPECS=(
    ('D_JAD_LEG_R','ParamJadeLegRelaxR','Jade - Right Leg Relax'),
    ('D_JAD_LEG_L','ParamJadeLegRelaxL','Jade - Left Leg Relax'),
    ('D_JAD_BODY_UPPER_XY','ParamBreath','Breath'),
)

def select_keys(xml, selections=None):
    """Geometry-only copy, resolving both v27 parents and these new keys."""
    selections=selections or {}
    parent_selection={name:selections.get(name,0.) for name,_,_,_ in body.SPECS}
    neutral_parent=body.posed_model(xml,parent_selection)
    root=copy.deepcopy(neutral_parent.root)
    by_ref={n.get('xs.id'):n for n in root.find('shared')}
    for name,_,_ in SPECS:
        item=one(neutral_parent,name,'warp-deformer')
        source=by_ref[item.source_ref]
        forms=direct(source,'carray_list','keyforms')
        if len(forms)==1:
            continue
        require(len(forms)==3,name+': expected three forms')
        index=KEYS.index(selections.get(name,0.))
        chosen=copy.deepcopy(forms[index])
        forms.clear();forms.set('xs.n','keyforms');forms.set('count','1');forms.append(chosen)
        grid=by_ref[named(source,'KeyformGridSource','keyformGridSource').get('xs.ref')]
        bindings=direct(grid,'array_list','keyformBindings')
        bindings.clear();bindings.set('xs.n','keyformBindings');bindings.set('count','0')
        grid_forms=direct(grid,'array_list','keyformsOnGrid')
        selected=copy.deepcopy(grid_forms[index])
        grid_forms.clear();grid_forms.set('xs.n','keyformsOnGrid');grid_forms.set('count','1');grid_forms.append(selected)
    return MouthNeutralModel(ET.tostring(root,encoding='utf-8'),.001)

def pose_points(model,item,points,key):
    if key==0.:return tuple(points)
    t=model.transform(item.guid_ref)
    output=[]
    for index,(x,y) in enumerate(zip(points[::2],points[1::2])):
        row=index//(t.columns+1)
        if item.name.startswith('D_JAD_LEG_'):
            # Complete upper thigh and ankle rows are exactly stationary.
            weights=(0.,0.,.58,1.,.52,0.,0.,0.,0.)
            direction=1. if item.name.endswith('_R') else -1.
            output.extend((x+direction*42.*key*weights[row],y))
        else:
            # Rows 0/1 cover the face: exactly the same rigid displacement.
            chest=(0.,0.,1.,0.,0.,0.)
            lift=(-7.,-7.,-10.,0.,0.,0.)
            output.extend((x+(x-1920.)*.008*key*chest[row], y+key*lift[row]))
    return tuple(output)

def bind(xml,model,item,slots,param_ref):
    source=model.source(item)
    forms=direct(source,'carray_list','keyforms')
    require(len(forms)==1,'Expected neutral unbound target')
    base_form=forms[0]
    _,local=model.keyform_positions(item,require_single_unbound=True)
    neutral_ref=named(base_form,'CFormGuid','guid').get('xs.ref')
    parent=model.transform(item.parent_ref)
    world=model.forward_many(parent,local)
    grid_ref,grid_idx=slots[item.name+':grid']
    binding_ref,binding_idx=slots[item.name+':binding']
    form_refs=[neutral_ref]+[slots[item.name+':form:'+str(k)][0] for k in KEYS[1:]]
    changed=copy.deepcopy(source)
    owner=next(n for n in changed.iter() if any(c.tag=='KeyformGridSource' and c.get('xs.n')=='keyformGridSource' for c in n))
    old=named(changed,'KeyformGridSource','keyformGridSource')
    idx=list(owner).index(old);owner.remove(old)
    owner.insert(idx,ET.Element('KeyformGridSource',{'xs.n':'keyformGridSource','xs.ref':grid_ref}))
    new_forms=direct(changed,'carray_list','keyforms')
    new_forms.clear();new_forms.set('xs.n','keyforms');new_forms.set('count','3')
    checks=[]
    for key,ref in zip(KEYS,form_refs):
        target=pose_points(model,item,world,key)
        if key==0.:
            coords=local
        else:
            coords=list(model.inverse_many(parent,target))
            # Keep all unchanged vertices byte-numerically exact in every key.
            for j in range(0,len(world),2):
                if target[j:j+2]==world[j:j+2]:coords[j:j+2]=local[j:j+2]
        form=copy.deepcopy(base_form)
        named(form,'CFormGuid','guid').set('xs.ref',ref)
        if key!=0.:set_positions(direct(form,'float-array','positions'),coords)
        new_forms.append(form)
        restored=model.forward_many(parent,numbers(direct(form,'float-array','positions')))
        error=canvas._maximum_error(restored,target)
        require(error<.001,item.name+': pose conversion error')
        checks.append({'key':key,'roundtrip_error_px':error,'min_triangle_area2':body.positive_cells(model,item,target)})
    current=ex._replace_exact(xml,raw_source(xml,item),serialized(changed),1,'Secondary control '+item.name)
    blocks=[secondary._grid_block(grid_ref=grid_ref,grid_idx=grid_idx,binding_refs=[binding_ref],accesses=[(i,) for i in range(3)],form_refs=form_refs),
            eyes._new_binding_block(grid_ref=grid_ref,binding_ref=binding_ref,binding_idx=binding_idx,parameter_ref=param_ref,keys=KEYS)]
    for key in KEYS[1:]:blocks.append(secondary._form_guid_block(*slots[item.name+':form:'+str(key)],SOURCE_SHA,item.name+':secondary:'+str(key)))
    return current,blocks,{'deformer':item.name,'keys':KEYS,'poses':checks}

def plan(source:Path):
    data=source.read_bytes();require(sha(data)==SOURCE_SHA,'Requires native v27')
    _,xml=model_from_bytes(data)
    before=body.posed_model(xml,{})
    require(not nonfinite_objects(before),'Nonfinite source')
    raw_root=ex._parse_xml(xml)
    roles=[]
    for name,param,_ in SPECS:
        roles.extend([name+':grid',name+':binding']+[name+':form:'+str(k) for k in KEYS[1:]])
        if param!='ParamBreath':roles.extend([param+':guid',param+':id'])
    slots=secondary._allocate(raw_root,roles)
    ids=ex._id_map(raw_root)
    breath=[]
    for p in raw_root.iter('CParameterSource'):
        idnode=named(p,'CParameterId','id');real=ids.get(idnode.get('xs.ref'),idnode)
        if real.get('idstr')=='ParamBreath':breath.append(p)
    require(len(breath)==1,'Breath parameter ambiguous')
    breath_ref=named(breath[0],'CParameterGuid','guid').get('xs.ref')
    require(float(named(breath[0],'f','minValue').text)==0. and float(named(breath[0],'f','maxValue').text)==1.,'Unexpected Breath range')
    current=xml;blocks=[];new_parameters=[];new_refs=[];records=[]
    for name,param,label in SPECS:
        if param=='ParamBreath':param_ref=breath_ref
        else:
            require(not any(n.get('idstr')==param for n in raw_root.iter('CParameterId')),'Duplicate parameter')
            param_ref,param_idx=slots[param+':guid'];id_ref,id_idx=slots[param+':id']
            blocks.extend([secondary._parameter_guid_block(param_ref,param_idx,SOURCE_SHA,param),secondary._parameter_id_block(id_ref,id_idx,param)])
            block=secondary._parameter_source(param_ref,id_ref,label,'Gentle inward knee relaxation; upper thigh and feet anchored')
            node=ET.fromstring(block);named(node,'f','minValue').text='0.0'
            new_parameters.append(ET.tostring(node,encoding='utf-8').replace(b'\n',b'\r\n'))
            new_refs.append(param_ref)
        current,new_blocks,record=bind(current,before,one(before,name,'warp-deformer'),slots,param_ref)
        blocks.extend(new_blocks);record['parameter_id']=param;records.append(record)
    current=ex._append_shared_blocks(current,blocks)
    current=secondary._append_parameter_sources(current,new_parameters)
    current=secondary._append_root_parameter_children(current,new_refs,experiment=ex)
    neutral=select_keys(current)
    require(not nonfinite_objects(neutral),'Nonfinite output')
    neutral_error=0.
    for name,_,_ in SPECS:
        a=one(before,name);b=one(neutral,name)
        _,p=before.keyform_positions(a,require_single_unbound=True)
        _,q=neutral.keyform_positions(b,require_single_unbound=True)
        require(p==q,'Neutral local changed')
        neutral_error=max(neutral_error,canvas._maximum_error(before.forward_many(before.transform(a.parent_ref),p),neutral.forward_many(neutral.transform(b.parent_ref),q)))
    anchors=[]
    for weight in (-1.,0.,1.):
        base=select_keys(current,{'D_JAD_FULLBODY_ROOT':weight})
        sample=select_keys(current,{'D_JAD_FULLBODY_ROOT':weight,**{name:1. for name,_,_ in SPECS}})
        error=0.
        for name in ('JAD_R21_SHOE_R_V3','JAD_R21_SHOE_L_V3'):
            item=one(before,name,'art-mesh');_,local=before.keyform_positions(item,require_single_unbound=True)
            p=base.forward_many(base.transform(item.parent_ref),local)
            q=sample.forward_many(sample.transform(item.parent_ref),local)
            error=max(error,canvas._maximum_error(p,q))
        require(error<.001,'Secondary motion shifted shoes')
        anchors.append({'weight_shift':weight,'maximum_shoe_displacement_px':error})
    expected={n for n,_,_ in SPECS}
    # Compare the real source XML, not the neutralized geometry-only mirrors.
    for item in before.objects:
        if item.name not in expected:require(raw_source(xml,item)==raw_source(current,item),'Unrelated source changed '+item.name)
    # Cubism natively inlines ROOT's GUID; the old experiment graph checker
    # assumes all GUIDs are shared references and rejects this valid form.
    final_root=ex._parse_xml(current)
    definitions=[n.get('xs.id') for n in final_root.iter() if n.get('xs.id')]
    references=[n.get('xs.ref') for n in final_root.iter() if n.get('xs.ref')]
    uuids=[n.get('uuid') for n in final_root.iter() if n.get('uuid')]
    require(len(definitions)==len(set(definitions)),'Duplicate shared identity')
    require(set(references)<=set(definitions),'Unresolved shared reference')
    require(len(uuids)==len(set(uuids)),'Duplicate UUID')
    result=safe._replace_main_xml(data,current)
    a,_,_,_,_=safe._validate_surgical_layout(data);b,_,_,_,decoded=safe._validate_surgical_layout(result)
    require(decoded==current,'CAFF roundtrip error')
    preservation=safe._compare_entry_preservation(data,a,result,b,main_may_change=True)
    require(preservation['all_non_main_entries_byte_identical'],'Raster changed')
    require(source.read_bytes()==data,'Source checkpoint changed')
    return result,{'status':'candidate_requires_native_pose_gate','source':str(source),'source_sha256':SOURCE_SHA,'output_sha256':sha(result),
        'controls':records,'maximum_neutral_error_px':neutral_error,'foot_anchors':anchors,
        'all_rasters_unchanged':True,'all_artmesh_sources_unchanged':True,'references_resolved':True,'uuids_unique':True,
        'notes':['Only mild lateral knee relaxation, not a walk cycle or a completed leg rig.','Breath uses the existing standard parameter.','Native pose and combined appui gate pending.']}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--audit',required=True,type=Path)
    args=p.parse_args();require(not args.output.exists() and not args.audit.exists(),'Refusing overwrite')
    result,audit=plan(args.source)
    exclusive(args.output,result);exclusive(args.audit,(json.dumps(audit,indent=2)+'\n').encode())
    print(json.dumps({'output':str(args.output),'sha256':sha(result),'status':audit['status']}))
