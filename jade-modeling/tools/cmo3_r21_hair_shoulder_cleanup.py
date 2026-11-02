#!/usr/bin/env python3
"""Separate observed cloth remnants from existing hair art, in memory only.

No raster edits. Convex strip intersections retain original texture samples;
the two front locks regain their existing painted white tips. Every source
keeps its identity, texture, parent and bindings. Native visual QA is required.
"""
from __future__ import annotations
import copy
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import cmo3_create_deformer_experiment as ex
import cmo3_r21_mesh_polygon_trim as trim
from cmo3_r21_fullbody_first_assembly import direct, named, serialize
from cmo3_r21_iris_occlusion import replace_geometry, set_array
from cmo3_r21_restore_eye_r_finite import require, raw_source
from cmo3_r21_face_roots_to_head import one
from cmo3_r21_head_z_v28 import neutral_model

PREFIX = 'JAD_R21_HAIR_'
# Limits are in the ORIGINAL PNG's pixel space, not deformer-local space.
# Each (y, boundary_x) curve retains the hair side of the cloth boundary.
CURVES = {
    'FRONT_TEMPLE_L': ('left', [(-40, 260), (750, 260), (752, 184),
        (790,126), (850,85), (950,50), (1018,22)]),
    'FRONT_TEMPLE_R': ('right', [(-40,-40), (775,-40), (777,79),
        (816,145), (880,177), (960,210), (1068,234)]),
    'BACK_L_MID_OUTER': ('left', [(-40,198), (600,198), (638,157),
        (680,144), (730,123), (770,97)]),
    'BACK_R_MID_OUTER': ('right', [(-40,-40), (535,-40), (560,0),
        (610,15), (690,42), (755,68), (800,94), (850,50), (899,17)]),
}
LOWER_REGIONS = {
    'BACK_L_LOWER': [
        [(-40,-40),(100,-40),(90,0),(42,120),(-40,120)],
        [(-40,174),(103,174),(103,273),(-40,273)],
    ],
    'BACK_R_LOWER': [
        [(90,-40),(230,-40),(230,148),(144,148),(120,80),(90,0)],
        [(144,148),(230,148),(230,286),(77,286),(77,225)],
    ],
}
# Underlay is allowed behind the head, never over the neck/shoulder garment.
DEPTH_L = [(900,590),(980,575),(1025,520),(1050,405),(1080,352),
           (1120,301),(1170,267),(1240,233),(1320,207),(1400,175),
           (1450,195),(1485,240),(1540,235)]
DEPTH_R = [(900,775),(980,787),(1025,842),(1070,980),(1110,1040),
           (1170,1068),(1240,1100),(1320,1130),(1410,1172),
           (1460,1160),(1500,1118),(1550,1120)]
# Dense enough for subsequent deformation; white tips are sampled from the
# supplied sprite, including the asymmetrical painted notches.
LOCK_ROWS = {
    'L': [(340,60,190),(370,60,195),(400,60,205),(430,60,220),
          (460,60,245),(485,63,279),(494,63,221),(510,65,179),
          (520,67,207),(540,70,239),(550,76,252),(560,81,260),
          (570,84,240),(580,90,250),(590,100,263),(600,117,281),
          (606,190,273),(610,215,252)],
    'R': [(340,100,242),(370,96,246),(400,94,247),(430,82,247),
          (460,57,247),(485,22,245),(494,70,243),(510,100,240),
          (520,92,238),(540,66,234),(550,49,229),(560,35,225),
          (565,65,223),(575,58,217),(585,49,209),(590,42,204),
          (600,29,127),(606,16,110),(610,19,80)],
}


def _numbers(node):
    return list(map(float, (node.text or '').split()))


def _bands(curve, side, width):
    result = []
    for (y0,x0),(y1,x1) in zip(curve,curve[1:]):
        if side == 'left':
            result.append([(-60,y0),(x0,y0),(x1,y1),(-60,y1)])
        else:
            result.append([(x0,y0),(width+60,y0),(width+60,y1),(x1,y1)])
    return result


def _pixel_map(source, width, height):
    original=np.asarray(_numbers(direct(source,'float-array','positions'))).reshape(-1,2)
    uv=np.asarray(_numbers(direct(source,'float-array','uvs'))).reshape(-1,2)*[width,height]
    design=np.c_[uv,np.ones(len(uv))]
    affine=np.linalg.lstsq(design,original,rcond=None)[0]
    error=float(np.max(np.abs(design@affine-original)))
    require(error < .001,'Sprite original/UV mapping is not affine')
    return affine,error


def _canvas_polygon(polygon, affine):
    return (np.c_[np.asarray(polygon),np.ones(len(polygon))]@affine).tolist()


def _piece_arrays(source):
    return [_numbers(direct(source,'float-array','positions')),
            _numbers(direct(source,'float-array','uvs')),
            *[_numbers(direct(form,'float-array','positions'))
              for form in direct(source,'carray_list','keyforms')]],\
           list(map(int,direct(source,'int-array','indices').text.split()))


def _merge(source,pieces):
    """Join disjoint bands without keeping duplicated editable seam points."""
    form_count=len(direct(source,'carray_list','keyforms'))
    arrays=[[] for _ in range(2+form_count)]; indices=[]; registry={}
    for values,triangles in pieces:
        remap={}
        for vertex in sorted(set(triangles)):
            packed=tuple(value for valueset in values for value in valueset[2*vertex:2*vertex+2])
            identity=tuple(round(value,6) for value in packed)
            if identity not in registry:
                registry[identity]=len(arrays[0])//2
                for result,valueset in zip(arrays,values):result.extend(valueset[2*vertex:2*vertex+2])
            remap[vertex]=registry[identity]
        indices.extend(remap[index] for index in triangles)
    require(indices,'Hair cleanup removes every triangle')
    edges=sorted({tuple(sorted(pair)) for i in range(0,len(indices),3)
                  for a,b,c in [indices[i:i+3]] for pair in ((a,b),(b,c),(c,a))})
    replace_geometry(source,arrays[0],arrays[1],indices,[v for e in edges for v in e])
    for form,positions in zip(direct(source,'carray_list','keyforms'),arrays[2:]):
        set_array(direct(form,'float-array','positions'),positions)


def _retained(source,regions,affine):
    pieces=[]; reports=[]
    for region in regions:
        piece=copy.deepcopy(source)
        try:
            report=trim.trim_source(piece,_canvas_polygon(region,affine))
        except ValueError as error:
            if 'removes every triangle' in str(error):continue
            raise
        pieces.append(_piece_arrays(piece));reports.append(report)
    return pieces,reports


def _restore_lock(source,item,model,side,width,height,affine):
    cut=LOCK_ROWS[side][0][0]
    pieces,reports=_retained(source,[[(-80,-80),(width+80,-80),(width+80,cut),(-80,cut)]],affine)
    rows=LOCK_ROWS[side]; columns=8
    pixel=[(left+(right-left)*col/columns,y)
           for y,left,right in rows for col in range(columns+1)]
    original=(np.c_[np.asarray(pixel),np.ones(len(pixel))]@affine).reshape(-1).tolist()
    local=list(model.inverse_many(model.transform(item.parent_ref),original))
    uvs=[v for x,y in pixel for v in (x/width,y/height)]
    triangles=[]
    for row in range(len(rows)-1):
        for col in range(columns):
            a=row*(columns+1)+col;b=a+1;c=a+columns+1;d=c+1
            triangles.extend((a,b,d,a,d,c))
    pieces.append(([original,uvs,local],triangles));_merge(source,pieces)
    return {'restored_existing_painted_tip':True,'retained_upper_sprite_before_y':cut,
            'tip_rows_pixel':rows,'upper_intersections':len(reports)}


def patch(xml):
    """Return (new_xml, audit), preserving all unlisted object source bytes."""
    root=ET.fromstring(xml);ids={n.get('xs.id'):n for n in root.find('shared')}
    geometry=neutral_model(xml)
    manifest_path=Path(__file__).resolve().parents[1]/'assets/live2d/r21_professional_art/master_v4_rig_layers_v1/Jade_r21_rig_layers_v1_manifest.json'
    manifest={r['name']:r for r in json.loads(manifest_path.read_text(encoding='utf-8'))['layers']}
    suffixes=[*CURVES,*LOWER_REGIONS,'BACK_L_MID_INNER','BACK_R_MID_INNER',
              'HAIR_DEPTH_UNDERLAY','FRONT_LOCK_L','FRONT_LOCK_R']
    names=[s if s=='HAIR_DEPTH_UNDERLAY' else PREFIX+s for s in suffixes]
    names=[PREFIX+'DEPTH_UNDERLAY' if s=='HAIR_DEPTH_UNDERLAY' else s for s in names]
    current=xml;records=[]
    for name in names:
        item=one(geometry,name,'art-mesh');source=copy.deepcopy(ids[item.source_ref])
        require(len(direct(source,'carray_list','keyforms'))==1,name+': expected static source')
        record={'name':name,'texture_unchanged':True,'parent_unchanged':True}
        if name.endswith('MID_INNER'):
            named(direct(source,'carray_list','keyforms')[0],'f','opacity').text='0.0'
            record['action']='hide_misclassified_sleeve_and_arm_only_no_hair'
        else:
            meta=manifest[name];width,height=meta['width'],meta['height']
            affine,error=_pixel_map(source,width,height)
            short=name[len(PREFIX):]
            if short.startswith('FRONT_LOCK_'):
                record.update(_restore_lock(source,item,geometry,short[-1],width,height,affine))
                record['action']='restore_existing_white_tip_geometry'
            else:
                if short=='DEPTH_UNDERLAY':
                    regions=[[(-60,-60),(width+60,-60),(width+60,900),(-60,900)]]
                    regions+=_bands(DEPTH_L,'left',width)+_bands(DEPTH_R,'right',width)
                elif short in CURVES:
                    side,curve=CURVES[short];regions=_bands(curve,side,width)
                elif short=='BACK_L_LOWER':
                    regions=_bands([(-40,100),(0,90),(120,42)],'left',width)
                    regions+=[[(-40,174),(103,174),(103,273),(-40,273)]]
                else:
                    regions=_bands([(-40,90),(0,90),(80,120),(148,144),
                                    (225,77),(286,77)],'right',width)
                pieces,checks=_retained(source,regions,affine);_merge(source,pieces)
                record.update(action='retain_hair_side_of_observed_cloth_boundary',
                              regions_pixel=regions,nonempty_regions=len(checks))
            record.update(original_pixel_affine=affine.tolist(),affine_error_px=error,
                          vertices=int(direct(source,'float-array','positions').get('count'))//2)
        current=ex._replace_exact(current,raw_source(current,item),serialize(source),1,'Hair shoulder separation '+name)
        records.append(record)
    for item in geometry.objects:
        if item.name not in names:
            require(raw_source(xml,item)==raw_source(current,item),'Unrelated source changed: '+item.name)
    return current,{'status':'candidate_requires_native_head_z_gate','changed_names':names,
                    'records':records,'all_raster_pixels_unchanged':True,
                    'limits':['Contours follow observed existing artwork; native seam review is required.',
                              'Hair dynamics and full head XY remain later work.']}
