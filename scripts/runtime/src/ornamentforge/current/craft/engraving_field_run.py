"""Build Dense Line Art -> EngravingFieldV1 -> straight vase -> Blender evidence."""
from __future__ import annotations
import argparse,json,math,shutil,subprocess
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

from ornamentforge.blender_detection import detect_blender
from ornamentforge.canonical_curve import canonical_bytes
from .engraving_field import (EngravingFieldV1,file_hash,signed_distance,groove_depth,width_metrics,
    straight_vase_surface,distortion_qa,geometry_screen)


def write_json(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def gray(path,value):Image.fromarray(np.clip(255*(1-value/value.max()),0,255).astype('uint8') if value.max()>0 else np.full(value.shape,255,'uint8')).save(path)


def run(source,mask_path,out,blender=None,depth=.035,mesh_resolution=(1024,512)):
    source,mask_path,out=map(Path,(source,mask_path,out))
    if out.exists() and any(out.iterdir()):raise ValueError('Refusing to overwrite engraving-field evidence')
    out.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,out/'source.png');shutil.copyfile(mask_path,out/'binary_mask.png')
    mask=np.asarray(Image.open(mask_path).convert('L'))>127;h,w=mask.shape
    sdf,inside=signed_distance(mask);depth_field=groove_depth(sdf,inside,depth,'SOFT_ROUNDED',2.)
    np.savez_compressed(out/'engraving_field.npz',signed_distance=sdf,depth=depth_field)
    gray(out/'engraving_field.png',depth_field)
    domain=[-5.,-2.5,5.,2.5];surface,transform=straight_vase_surface(domain)
    surface_data=surface.to_dict();write_json(out/'surface_map.json',surface_data)
    widths=width_metrics(mask);unit=(domain[2]-domain[0])/w
    surface_qa=distortion_qa(surface,transform,widths['minimum_retained_width_pixels']*unit)
    if surface_qa['status']!='PASS':
        raise RuntimeError('Frozen SurfaceMap distortion QA HOLD; Blender not started')
    nu,nv=mesh_resolution;mapped=cv2.resize(depth_field,(nu,nv),interpolation=cv2.INTER_LINEAR)
    gray(out/'mapped_field.png',mapped)
    seam=dict(topology='PERIODIC_SHARED_VERTICES',source_edge_ink_pixels=[int(mask[:,0].sum()),int(mask[:,-1].sum())],
        source_depth_edge_max_delta=float(np.max(np.abs(depth_field[:,0]-depth_field[:,-1]))),
        mapped_depth_edge_max_delta=float(np.max(np.abs(mapped[:,0]-mapped[:,-1]))),status='PASS' if not (mask[:,0].any() or mask[:,-1].any()) else 'HOLD')
    radius=10/(2*math.pi);geometry=geometry_screen(mapped,radius,5.)
    reconstructed=depth_field>0
    field_recall=float((reconstructed&mask).sum()/mask.sum());field_precision=float((reconstructed&mask).sum()/max(1,reconstructed.sum()))
    field_path=out/'engraving_field.npz'
    preliminary=dict(schema_version='EngravingFieldV1',source_hash=file_hash(source),width=w,height=h,
        design_domain=dict(bounds=domain,coordinates='XY_RIGHT_UP'),binary_stroke_mask_hash=file_hash(mask_path),
        signed_distance_field=dict(path=str(field_path.resolve()),sha256=file_hash(field_path),format='NPZ:signed_distance',shape=[h,w],dtype='float32',sign_convention='negative inside stroke; positive outside'),
        requested_groove_depth=depth,requested_groove_width_policy=dict(mode='SOURCE_MASK_DISTANCE',minimum_filter_width_pixels=0,
            filtered_detail_fraction=0.,width_metrics=widths),edge_profile=dict(kind='SOFT_ROUNDED',edge_softness_pixels=2.,alternatives=['V','U_ROUND']),
        surface_map_hash=surface.content_hash,provenance=[dict(kind='SAVED_NORMALIZED_LINE_ART_MASK',source=str(mask_path.resolve()),sha256=file_hash(mask_path)),
            dict(kind='AI_SELECTED_REFERENCE',source=str(source.resolve()),sha256=file_hash(source)),
            dict(kind='DETERMINISTIC_SIGNED_DISTANCE',operation='OpenCV L2 distance transform; no vector cleanup or semantic topology')],
        qa=dict(status='PENDING_BLENDER',source_mask_to_field=dict(recall=field_recall,precision=field_precision),surface_transfer=surface_qa,seam=seam,geometry_screen=geometry))
    field=EngravingFieldV1.from_dict(preliminary);write_json(out/'engraving_field.json',field.to_dict())
    np.savez_compressed(out/'surface_field.npz',depth=mapped,radius=radius,vase_height=5.,seam_angle=math.pi/2,
        source_width=w,source_height=h)
    installation=detect_blender(blender);worker=Path(__file__).resolve().parents[1]/'blender'/'engraving_field_worker.py'
    with (out/'blender.log').open('w',encoding='utf-8') as log:
        process=subprocess.run([str(installation.path),'--background','--python',str(worker),'--',str(out)],stdout=log,stderr=subprocess.STDOUT,text=True)
    if process.returncode:raise RuntimeError(f'Blender failed; inspect {out/"blender.log"}')
    bqa=json.loads((out/'blender_geometry_qa.json').read_text(encoding='utf-8'))
    blockers=[]
    if seam['status']!='PASS':blockers.append('SEAM_FIELD_MISMATCH')
    if geometry['orientation_inversion_count'] or bqa['nonmanifold_edges'] or not bqa['finite']:blockers.append('GEOMETRY_INTEGRITY')
    qa=dict(status='PASS' if not blockers else 'HOLD',blockers=blockers,sdf_resolution=[w,h],mapped_mesh_resolution=[nu,nv],
        groove_profile='SOFT_ROUNDED',depth_range=[0.,float(mapped.max())],minimum_retained_line_width=widths,
        filtered_detail_fraction=0.,source_mask_to_planar_field=dict(stroke_recall=field_recall,stroke_precision=field_precision),
        surface_map=dict(host='REVOLUTION_VASE',profile='straight_vase',domain_transform=transform,qa=surface_qa),
        seam_continuity=seam,geometry=geometry,blender_geometry=bqa,blender_version='.'.join(map(str,installation.version)),
        limitations=['Source mask is the saved Fidelity normalized binary mask; no new line extraction.',
            'SDF is full resolution; actual mesh samples it at mapped_mesh_resolution.',
            'Numerical/mesh PASS is not manufacturing certification or artistic approval.'])
    write_json(out/'qa.json',qa)
    final=preliminary;final['qa']=qa;write_json(out/'engraving_field.json',EngravingFieldV1.from_dict(final).to_dict())
    report=f'''# Dense Line Art Engraving Field — first pass\n\nStatus: **{qa['status']}**. No AI generation, PlanarMaster schema change, SurfaceMap modification, vector hub repair or curve booleans.\n\n- Source / mask hashes: `{final['source_hash']}` / `{final['binary_stroke_mask_hash']}`. Copies are byte-identical.\n- SDF: {w} × {h}, signed L2 distance, negative inside strokes.\n- Profile: SOFT_ROUNDED, requested/max depth {depth:.6f} / {mapped.max():.6f} design units.\n- Width: source-mask distance preserves varying widths; minimum retained estimate {widths['minimum_retained_width_pixels']:.4f}px; filtered detail 0%.\n- Field fidelity: recall {field_recall:.6f}, precision {field_precision:.6f}.\n- Surface: frozen REVOLUTION_VASE / straight_vase, radius 10/(2π), height 5, seam on blank source margin. Distortion QA {surface_qa['status']}; max angle {surface_qa['metrics']['angle_distortion']:.3e}, area {surface_qa['metrics']['area_distortion']:.3e}, stretches {surface_qa['metrics']['min_stretch']:.6f}..{surface_qa['metrics']['max_stretch']:.6f}.\n- Seam: {seam['status']}; periodic shared vertices, source edge ink {seam['source_edge_ink_pixels']}, depth delta {seam['source_depth_edge_max_delta']:.6f}.\n- Geometry: actual shape-key vertex displacement plus evaluated closed Solidify wall; {bqa['vertices']} evaluated vertices, {bqa['faces']} faces, {bqa['nonmanifold_edges']} nonmanifold edges. One ornament mesh, zero curve objects.\n- Blender {qa['blender_version']}: editable_engraved_vase.blend saved; renders are real geometry, not bump/texture displacement.\n\nThe dense engraving field is independent of TRUE_BRANCH/CROSSING/hub blockers. CleanCurveNetwork remains editable diagnostic reference. Stop after this first pass for human review.\n'''
    (out/'report.md').write_text(report,encoding='utf-8')
    return qa


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True);p.add_argument('--mask',required=True);p.add_argument('--output',required=True);p.add_argument('--blender');a=p.parse_args()
    result=run(a.source,a.mask,a.output,a.blender);print(json.dumps(result,ensure_ascii=False));raise SystemExit(0 if result['status']=='PASS' else 2)
