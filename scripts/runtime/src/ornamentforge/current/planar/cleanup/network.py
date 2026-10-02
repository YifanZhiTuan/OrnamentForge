"""Topology-first cleanup. Never deletes a stroke merely because it is short.

Geometry outside large-junction uncertainty zones is concatenated exactly, not
refitted. Removed redundant loops and isolated hub pieces stay in quarantine.
"""
from collections import defaultdict
from copy import deepcopy
import math
import cv2
import numpy as np
from .geometry import controls,sample,length,reverse,trim_start,payload,endpoint_direction


class Support:
    def __init__(self,mask,bounds):
        self.mask=np.asarray(mask,bool);self.bounds=bounds
        self.h,self.w=self.mask.shape
        self.distance=cv2.distanceTransform((~self.mask).astype('uint8'),cv2.DIST_L2,5)

    def pixels(self,p):
        x0,y0,x1,y1=self.bounds
        p=np.asarray(p)
        return np.c_[(p[:,0]-x0)/(x1-x0)*self.w,(y1-p[:,1])/(y1-y0)*self.h]

    def fraction(self,points,tolerance=1.):
        xy=np.rint(self.pixels(points)).astype(int)
        valid=(xy[:,0]>=0)&(xy[:,0]<self.w)&(xy[:,1]>=0)&(xy[:,1]<self.h)
        hit=np.zeros(len(xy),bool)
        hit[valid]=self.distance[xy[valid,1],xy[valid,0]]<=tolerance
        return float(hit.mean())

    def ink_interior(self,points):
        xy=self.pixels(points)
        lo=np.floor(xy.min(axis=0)).astype(int);hi=np.ceil(xy.max(axis=0)).astype(int)+1
        lo=np.maximum(lo,0);hi=np.minimum(hi,[self.w,self.h])
        if np.any(hi<=lo):return 0.,0
        region=np.zeros((hi[1]-lo[1],hi[0]-lo[0]),'uint8')
        cv2.fillPoly(region,[np.rint(xy-lo).astype('int32')],1)
        pixels=region>0
        return (float(self.mask[lo[1]:hi[1],lo[0]:hi[0]][pixels].mean()),int(pixels.sum())) if pixels.any() else (0.,0)


def classify_junction(ports, oversized=False):
    """ports have id, direction, bend and support; pair only unique continuations."""
    if oversized:return 'UNRESOLVED',[], 'Collapsed large hub: independent port isolation, no invented connection'
    if len(ports)<2:return 'ENDPOINT',[], 'Terminal'
    candidates=[]
    for i,a in enumerate(ports):
        for b in ports[i+1:]:
            angle=math.degrees(math.acos(float(np.clip(-np.dot(a['direction'],b['direction']),-1,1))))
            bend=math.degrees(abs(a['bend']-b['bend']))
            if min(a['support'],b['support'])>=.85 and angle<=40 and bend<=65:
                candidates.append((angle+.15*bend,a['id'],b['id']))
    choices=defaultdict(list)
    for score,a,b in sorted(candidates):choices[a].append((score,b));choices[b].append((score,a))
    best={}
    for key,rows in choices.items():
        if len(rows)==1 or rows[1][0]-rows[0][0]>=10:best[key]=rows[0][1]
    pairs=sorted((a,b) for a,b in best.items() if a<b and best.get(b)==a)
    if len(ports)==2 and pairs:return 'CONTINUATION',pairs,'Unique tangent/curvature continuation with source support'
    if len(ports)==4 and len(pairs)==2:return 'CROSSING',pairs,'Two independently paired continuations; not a welded four-way branch'
    if len(ports)==3 and pairs:return 'TRUE_BRANCH',pairs,'Unique through-curve and one attached branch (geometric inference)'
    if len(ports)==2 and min(p['support'] for p in ports)<.85:
        return 'NEAR_TOUCH',[], 'Weak source support; keep independent ports'
    return 'UNRESOLVED',[], 'Ambiguous directions/curvature or higher-degree contact; no automatic welding'


def clean_network(master,mask,input_hash='',mask_hash=''):
    m=master.to_dict() if hasattr(master,'to_dict') else deepcopy(master)
    if m['closed_regions'] or m['holes'] or m['repeat_groups']:
        raise ValueError('Cleanup V1 accepts stroke-only masters; no region/repeat content may be silently dropped')
    graph=m['open_stroke_graph']
    if graph['state']!='EXTRACTED' or not graph['edges']:raise ValueError('An extracted stroke graph is required')
    if any(g['representation']!='bezier_curve' for g in m['editable_geometry_references']):
        raise ValueError('Cleanup V1 requires existing editable Bezier geometry')
    support=Support(mask,m['domain']['bounds']);unit=(support.bounds[2]-support.bounds[0])/support.w
    geometries={g['id']:g for g in m['editable_geometry_references']}
    oldnodes={n['id']:n for n in graph['nodes']}
    metadata=next((p['details'] for p in m['provenance'] if p['kind']=='raster_line_art'),{})
    original_meta=metadata.get('nodes',[])
    large={n['id']:float(original_meta[i].get('cluster_radius',0)) for i,n in enumerate(graph['nodes'])
           if i<len(original_meta) and original_meta[i].get('cluster_radius',0)>4}
    parent={k:k for k in oldnodes}
    def root(k):
        while parent[k]!=k:parent[k]=parent[parent[k]];k=parent[k]
        return k
    for e in graph['edges']:parent[root(e['end'])]=root(e['start'])
    components={r:f'component_{i}' for i,r in enumerate(sorted({root(k) for k in parent}))}
    edges={};quarantine=[];accounting={};incidents=defaultdict(list)
    for e in graph['edges']:
        seg=controls(geometries[e['geometry_ref']]['data']);before=length(seg,unit)
        if before<=1e-12:raise ValueError('Zero-length source curve')
        a,b=e['start'],e['end'];parts=[]
        # Restore no lost centerline: isolate a bounded part of the already collapsed
        # hub exactly. Keep every trimmed cubic in quarantine with its source ID.
        for side,node in ((0,a),(1,b)):
            if node not in large:continue
            amount=min((large[node]+1)*unit,before*.24)
            view=reverse(seg) if side else seg
            removed,kept=trim_start(view,amount,unit)
            if not kept:raise ValueError('Junction trimming consumed an entire edge')
            seg=reverse(kept) if side else kept
            parts.append(dict(reason='OVERSIZED_HUB_INTERIOR',junction=node,side=side,
                source_edges=[e['id']],geometry=payload(reverse(removed) if side else removed)))
        quarantine.extend(parts)
        pts=sample(seg,unit*.75);remaining=length(seg,unit)
        loop=a==b and not parts
        # MERGE stage is not impeded by closed loops: loops are kept as independent
        # line structures rather than welded as two extra incident spokes.
        edge=dict(id=e['id'],segments=seg,start=a,end=b,width=e['width'],source_length=before,
            length=remaining,parent=components[root(a)],support=support.fraction(pts),loop=loop,trimmed=bool(parts))
        edges[e['id']]=edge
        accounting[e['id']]=dict(input_length=before,retained_length=remaining,quarantined_hub_length=before-remaining)
        if not loop:
            incidents[a].append((e['id'],0));incidents[b].append((e['id'],1))
    pairmap={};junctions=[]
    for node,items in sorted(incidents.items()):
        ports=[]
        for key,side in items:
            edge=edges[key];direction,bend=endpoint_direction(edge['segments'],side,unit)
            ports.append(dict(id=(key,side),direction=direction,bend=bend,support=edge['support']))
        kind,pairs,reason=classify_junction(ports,node in large)
        for a,b in pairs:pairmap[a]=b;pairmap[b]=a
        junctions.append(dict(junction_id=node,classification=kind,reason=reason,
            original_position=oldnodes[node]['position'],original_cluster_radius_pixels=large.get(node,0),
            ports=[dict(source_edge=k,side=s,position=edges[k]['segments'][0][0].tolist() if s==0 else edges[k]['segments'][-1][-1].tolist()) for k,s in items],
            pairs=[[list(a),list(b)] for a,b in pairs],oversized_split=node in large,
            topology='INDEPENDENT_PORTS' if kind in ('CROSSING','NEAR_TOUCH','UNRESOLVED') else 'BRANCH_WITH_INTERIOR_ATTACHMENT' if kind=='TRUE_BRANCH' else 'CONTINUOUS'))
    visited=set();chains=[]
    # Walk unpaired ends first, then cyclic chains. Each old edge is visited once.
    starters=sorted((k,s) for k,e in edges.items() if not e['loop'] for s in (0,1) if (k,s) not in pairmap)
    starters += [(k,0) for k in sorted(edges)]
    for initial in starters:
        if initial[0] in visited:continue
        current=initial;segments=[];pieces=[]
        while current[0] not in visited:
            key,side=current;edge=edges[key];visited.add(key)
            part=reverse(edge['segments']) if side else edge['segments']
            if segments and np.linalg.norm(segments[-1][-1]-part[0][0])>1e-9:
                raise ValueError('Chaining attempted to bridge unmatched endpoints')
            start_segment=len(segments);segments.extend(part)
            pieces.append(dict(source_edge=key,reversed=bool(side),segment_start=start_segment,
                segment_end=len(segments),width=edge['width'],support=edge['support'],length=edge['length']))
            endport=(key,1-side)
            if endport not in pairmap:break
            current=pairmap[endport]
        last=pieces[-1];endkey=last['source_edge'];endside=0 if last['reversed'] else 1
        firstkey,firstside=initial
        startnode=edges[firstkey]['start' if firstside==0 else 'end']
        endnode=edges[endkey]['start' if endside==0 else 'end']
        # Proximity is not topological closure: distinct unresolved ports may
        # be coincident (or differ only by floating point roundoff).
        closed=bool(edges[firstkey]['loop'] or pairmap.get((endkey,endside))==initial)
        if closed and not np.array_equal(segments[0][0],segments[-1][-1]):
            raise ValueError('Topologically closed chain has unequal endpoints')
        total=sum(p['length'] for p in pieces)
        evidence=sum(p['support']*p['length'] for p in pieces)/total
        chains.append(dict(curve_id=f'clean_curve_{len(chains)}',control_points=payload(segments)['points'],
            closed=closed,parent_component=edges[firstkey]['parent'],
            local_width=dict(representative=sum(p['width']*p['length'] for p in pieces)/total,
                             samples=[dict(source_edge=p['source_edge'],width=p['width']) for p in pieces],basis='source-only, not a relief profile'),
            confidence=float(evidence*.9),junction_start=startnode,junction_end=endnode,
            source_support=dict(fraction=evidence,tolerance_pixels=1.,source_edges=[p['source_edge'] for p in pieces],pieces=pieces),
            length=total,endpoint_ports=[list(initial),[endkey,endside]],status='REVIEW_REQUIRED'))
    # Secondary noise pruning: only sub-width loops whose interior has no white
    # gap. Tiny loops with a real negative-space interior are explicitly retained.
    kept=[]
    for c in chains:
        if c['closed'] and c['length']/unit<12:
            seg=controls(dict(points=c['control_points']));points=sample(seg,unit*.4)
            ink,count=support.ink_interior(points)
            extent=np.ptp(points,axis=0)/unit
            if ink>=.98 and count>0 and max(extent)<=max(3.,c['local_width']['representative']/unit):
                quarantine.append(dict(reason='REDUNDANT_INK_INTERIOR_MICRO_LOOP',source_edges=c['source_support']['source_edges'],
                    geometry=payload(seg),ink_interior_fraction=ink,interior_pixel_count=count,curve_record=c))
                for key in c['source_support']['source_edges']:accounting[key]['disposition']='QUARANTINED_REDUNDANT_LOOP'
                continue
        kept.append(c)
        for key in c['source_support']['source_edges']:accounting[key]['disposition']='ACTIVE'
    if set(accounting)!=set(edges) or any('disposition' not in a for a in accounting.values()):
        raise ValueError('Lost source-edge accounting')
    return dict(schema_version='CleanCurveNetworkV1',source_hash=m['source_hash'],input_master_hash=input_hash,
        support_mask_hash=mask_hash,domain=m['domain'],physical_scale=m['physical_scale'],working_size=[support.w,support.h],
        design_units_per_working_pixel=unit,curves=kept,junctions=junctions,quarantine=quarantine,source_edge_accounting=accounting,
        policy=dict(primary_objective='geometry topology for relief, not raster similarity',merge_first=True,
            delete_for_shortness=False,max_pair_angle_degrees=40,ambiguity_margin_degrees=10,
            large_junction_radius_threshold_pixels=4,large_hub_trim_max_edge_fraction_per_end=.24),
        limitations=['Pairings and TRUE_BRANCH are geometric hypotheses, not semantic labels.',
            'Oversized hub interiors are quarantined, not reconstructed. Their ports require resolution.',
            '2D crossings are separate curves; relief vertical ordering/collision treatment is undecided.',
            'Source widths are references only; no ridge width, height, bevel or profile is selected.'])
