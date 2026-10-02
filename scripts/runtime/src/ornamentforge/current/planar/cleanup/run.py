"""Offline graph cleanup evidence runner. No image reconstruction or Relief Builder."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from ornamentforge.canonical_curve import canonical_bytes
from ..contract import PlanarMasterV1
from .geometry import controls,sample
from .network import clean_network
from .qa import model_qa
from .export import to_planar_master


def diagnostics(original,network,out):
    w,h=network['working_size'];unit=network['design_units_per_working_pixel']
    x0,y0,x1,y1=network['domain']['bounds']
    def pixels(segments):
        return [((x-x0)/unit,(y1-y)/unit) for x,y in sample(segments,unit*.75)]
    old=[controls(g['data']) for g in original['editable_geometry_references']]
    new=[controls(dict(points=c['control_points'])) for c in network['curves']]
    colors=['#2962a3','#398156','#b0702d','#885798','#408c90','#a05265']
    def render(rows,colored=False,risk=None):
        image=Image.new('RGB',(w,h),'white');draw=ImageDraw.Draw(image)
        for i,seg in enumerate(rows):
            color=colors[i%len(colors)] if colored else '#444444'
            if risk is not None:color='#b63e32' if risk[i] else '#2c7b54'
            draw.line(pixels(seg),fill=color,width=1)
        return image
    def paired(a,b,name,label):
        image=Image.new('RGB',(w*2,h+32),'white');image.paste(a,(0,32));image.paste(b,(w,32))
        d=ImageDraw.Draw(image);d.text((8,8),'BEFORE: existing graph',fill='black');d.text((w+8,8),label,fill='black')
        image.save(out/name)
    paired(render(old),render(new),'topology_before_after.png','AFTER: retained clean network (not a relief render)')
    paired(render(old,True),render(new,True),'curve_chaining.png','AFTER: one color per chained curve')
    risks=[bool(c['reasons']) for c in network['qa']['curves']]
    risk=render(new,risk=risks);d=ImageDraw.Draw(risk)
    for j in network['junctions']:
        if j['oversized_split']:
            x,y=j['original_position'];x=(x-x0)/unit;y=(y1-y)/unit
            d.ellipse((x-7,y-7,x+7,y+7),outline='#dd7800',width=2)
    risk.save(out/'model_risk_map.png')
    # Diagrammatic zooms of largest hub, not a source-image crop.
    largest=sorted((j for j in network['junctions'] if j['oversized_split']),key=lambda j:-j['original_cluster_radius_pixels'])[:4]
    before=render(old);after=render(new)
    sheet=Image.new('RGB',(800,max(1,len(largest))*220),'white');d=ImageDraw.Draw(sheet)
    for i,j in enumerate(largest):
        x,y=j['original_position'];x=(x-x0)/unit;y=(y1-y)/unit
        box=(int(x-24),int(y-24),int(x+24),int(y+24))
        for col,im in enumerate((before,after)):
            crop=im.crop(box).resize((192,192),Image.Resampling.NEAREST)
            sheet.paste(crop,(col*400,220*i+24))
        d.text((4,220*i+4),f"{j['junction_id']} BEFORE",fill='black')
        d.text((404,220*i+4),'AFTER independent ports / UNRESOLVED',fill='black')
    if not largest:d.text((10,10),'No oversized junctions',fill='black')
    sheet.save(out/'junction_cleanup.png')


def run(master_path,mask_path,output):
    src=Path(master_path);mask_path=Path(mask_path);out=Path(output)
    if out.exists() and any(out.iterdir()):raise ValueError('Refusing to overwrite existing cleanup evidence')
    raw=src.read_bytes();original=PlanarMasterV1.from_dict(json.loads(raw)).to_dict()
    with Image.open(mask_path) as im:mask=np.asarray(im.convert('L'))>127
    details=next((p['details'] for p in original['provenance'] if p['kind']=='raster_line_art'),None)
    if details is None or list(mask.shape[::-1])!=details['sampling']['working_size']:
        raise ValueError('Support mask dimensions must match original extraction provenance')
    network=clean_network(original,mask,sha256(raw).hexdigest(),sha256(mask_path.read_bytes()).hexdigest())
    network['qa']=model_qa(network)
    old_lengths=[e['length_pixels'] for e in details['edges']]
    active=network['curves'];unit=network['design_units_per_working_pixel']
    network['summary']=dict(source_edges=len(original['open_stroke_graph']['edges']),clean_curves=len(active),
        source_short_edges=sum(v<4 for v in old_lengths),clean_short_curves=sum(c['length']/unit<4 for c in active),
        source_long_edges=sum(v>=20 for v in old_lengths),clean_long_curves=sum(c['length']/unit>=20 for c in active),
        junction_classifications=dict(Counter(j['classification'] for j in network['junctions'])),
        quarantined_pieces_by_reason=dict(Counter(q['reason'] for q in network['quarantine'])),
        all_source_edges_accounted=len(network['source_edge_accounting'])==len(original['open_stroke_graph']['edges']),
        source_control_geometry_policy='Exact concatenation; de Casteljau subdivision only inside oversized hub endpoints; no global refitting',
        retained_centerline_length_ratio=sum(c['length'] for c in active)/sum(v['input_length'] for v in network['source_edge_accounting'].values()))
    master=to_planar_master(original,network,sha256(canonical_bytes(network)).hexdigest())
    out.mkdir(parents=True,exist_ok=True);(out/'diagnostics').mkdir()
    def write(path,value):
        with (out/path).open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False)
    write('clean_curve_network.json',network);write('planar_master_model_ready.json',master.to_dict())
    diagnostics(original,network,out/'diagnostics')
    metrics={k:v for k,v in network['qa'].items() if k!='curves'}
    result=dict(status=network['qa']['status'],contract='PASS',summary=network['summary'],qa=metrics,
        planar_graph_edges=len(master.to_dict()['open_stroke_graph']['edges']),output=str(out.resolve()))
    write('cleanup_summary.json',result)
    report=['# Model-Ready PlanarMaster Cleanup','',
        '**'+network['qa']['status']+' — not blanket authorization for Relief construction.**','',
        'Input is the existing PlanarMaster and its saved binary support mask. No reference reconstruction, new AI design or raster-similarity optimization occurred.',
        '', '## Measured result','', '```json',json.dumps(result,ensure_ascii=False,indent=2),'```','',
        '## Geometry and topology policy','',
        '- Merge first using tangent/curvature agreement, source support and unambiguous neighboring direction; concatenate existing cubics exactly.',
        '- Large collapsed hubs are separated into independent ports by exact bounded subdivision. Interior cubics are quarantined, not discarded or falsely reconstructed.',
        '- Tiny loops are quarantined only when sub-width and their sampled interior is >=98% ink: no true negative-space loop is removed just for being small.',
        '- Every source edge is accounted for in active curves or explicit quarantine. This preserves the source for review/rollback.',
        '- TRUE_BRANCH is a geometric hypothesis. PlanarMaster export splits long curves at true branch attachments so graph connectivity remains represented. The companion CleanCurveNetwork keeps the full long curves.',
        '- CROSSING curves remain independent: no welded four-way node. This does not solve 3D relief overlap or choose over/under height.',
        '- UNRESOLVED and NEAR_TOUCH are never silently welded. Separate coincident ports do not imply spatial separation or collision-free relief.',
        '- Width samples are source references only; Relief Builder must choose ridge width/height/bevel/profile later.',
        '', '## QA boundary','',
        'Model QA measures topology, micro curves, dangling fragments, loops, sampled self-intersections/curvature, proximity and component readiness. Raster recall/precision remain historical auxiliary provenance, not optimization targets.',
        'Spacing is a sampled neighborhood screen, not certified minimum clearance. Physical fabrication scale/profile is unknown. Read all limitations in cleanup_summary.json.',
        'The filename planar_master_model_ready.json identifies the intended stage, not a PASS claim. Contract PASS and model QA HOLD are separate.',
        '', '## Diagnostics','',
        'diagnostics/topology_before_after.png; curve_chaining.png; junction_cleanup.png; model_risk_map.png.',
        'Diagrams show geometry/topology only and use no source texture. Red risk strokes and orange oversized-hub markers require review.',
        '', 'Stop after this cleanup pass. Do not enter Relief Master Construction until unresolved modeling blockers have been reviewed.']
    with (out/'MODEL_READY_REPORT.md').open('x',encoding='utf-8') as f:f.write('\n'.join(report)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--master',required=True);parser.add_argument('--support-mask',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();result=run(args.master,args.support_mask,args.output)
    print(json.dumps(result,ensure_ascii=False));raise SystemExit(2 if result['status']=='HOLD' else 0)
