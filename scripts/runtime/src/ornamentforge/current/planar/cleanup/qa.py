"""Model topology/risk QA in working pixels; raster similarity is not a gate."""
from collections import defaultdict
import numpy as np
from scipy.spatial import cKDTree
from .geometry import controls,sample


def proper_cross(a,b,c,d):
    def cross(u,v):return float(u[0]*v[1]-u[1]*v[0])
    return cross(b-a,c-a)*cross(b-a,d-a)<-1e-12 and cross(d-c,a-c)*cross(d-c,b-c)<-1e-12


def self_crossings(points,closed):
    cells=defaultdict(list);hits=set()
    for i,(a,b) in enumerate(zip(points,points[1:])):
        low=np.floor(np.minimum(a,b)/2).astype(int);high=np.floor(np.maximum(a,b)/2).astype(int)
        candidates=set();keys=[]
        for x in range(low[0],high[0]+1):
            for y in range(low[1],high[1]+1):keys.append((x,y));candidates.update(cells[(x,y)])
        for j in candidates:
            if i-j<=1 or (closed and j==0 and i==len(points)-2):continue
            if proper_cross(a,b,points[j],points[j+1]):hits.add((j,i))
        for key in keys:cells[key].append(i)
    return len(hits)


def model_qa(network):
    unit=network['design_units_per_working_pixel'];curves=network['curves']
    junctions={j['junction_id']:j for j in network['junctions']}
    per=[];samples=[];owners=[];micro=0;dangling=0;spikes=0;tiny=0;crossings=0
    byclass=defaultdict(int)
    for j in junctions.values():byclass[j['classification']]+=1
    for index,c in enumerate(curves):
        points=sample(controls(dict(points=c['control_points'])),unit*.75)/unit
        n=len(points);curve_cross=self_crossings(points,c['closed']);crossings+=curve_cross
        # Angle over a ~3px window, not curvature of raw source pixels.
        count=0
        if n>8:
            a=points[4:-4]-points[:-8];b=points[8:]-points[4:-4]
            norm=np.linalg.norm(a,axis=1)*np.linalg.norm(b,axis=1)
            cosine=(a*b).sum(axis=1)/np.maximum(norm,1e-12)
            bad=(cosine<np.cos(np.deg2rad(100)))&(norm>1)
            count=int(np.count_nonzero(bad & ~np.r_[False,bad[:-1]]))
        spikes+=count
        kinds=[junctions.get(c[k],{}).get('classification','ENDPOINT') for k in ('junction_start','junction_end')]
        isolated=not c['closed'] and c['length']/unit<4 and kinds==['ENDPOINT','ENDPOINT']
        dangling_frag=not c['closed'] and c['length']/unit<4 and kinds.count('ENDPOINT')==1
        small_loop=c['closed'] and c['length']/unit<12
        micro+=isolated;dangling+=dangling_frag;tiny+=small_loop
        unresolved=any(k in ('UNRESOLVED','NEAR_TOUCH') for k in kinds)
        reasons=[]
        for flag,name in ((isolated,'ISOLATED_MICRO'),(dangling_frag,'DANGLING_FRAGMENT'),(small_loop,'TINY_LOOP'),
                          (curve_cross,'SELF_INTERSECTION'),(count,'CURVATURE_SPIKE'),(unresolved,'UNRESOLVED_PORT')):
            if flag:reasons.append(name)
        per.append(dict(curve_id=c['curve_id'],self_intersections=curve_cross,curvature_spikes=count,
            reasons=reasons,model_ready=False))
        samples.extend(points);owners.extend([index]*n)
    # Conservative sampled proximity screen, independent of aesthetic/image QA.
    points=np.asarray(samples);owners=np.asarray(owners);near=set();minimum=None;risk_pairs=set()
    if len(points)>1:
        distances,indices=cKDTree(points).query(points,k=min(12,len(points)))
        for i in range(len(points)):
            for distance,j in zip(np.atleast_1d(distances[i])[1:],np.atleast_1d(indices[i])[1:]):
                a,b=int(owners[i]),int(owners[j])
                if a==b:continue
                minimum=float(distance) if minimum is None else min(minimum,float(distance))
                # Reference widths give a risk envelope, NOT chosen relief dimensions.
                reach=(curves[a]['local_width']['representative']+curves[b]['local_width']['representative'])/(2*unit)
                if distance<min(reach,3.):
                    risk_pairs.add(tuple(sorted((a,b))));near.update((a,b))
    bycomponent=defaultdict(list)
    for i,(c,q) in enumerate(zip(curves,per)):
        if i in near:q['reasons'].append('PROXIMITY_REQUIRES_RELIEF_PROFILE_REVIEW')
        q['model_ready']=not q['reasons'];bycomponent[c['parent_component']].append(q['model_ready'])
    total=sum(c['length'] for c in curves)
    oversized=sum(j['oversized_split'] for j in junctions.values())
    blockers=[]
    if oversized:blockers.append('SPLIT_HUB_PORTS_REQUIRE_LOCAL_RESOLUTION')
    if byclass['UNRESOLVED'] or byclass['NEAR_TOUCH']:blockers.append('UNRESOLVED_TOPOLOGY')
    if crossings:blockers.append('SELF_INTERSECTIONS')
    if spikes:blockers.append('CURVATURE_SPIKES')
    if tiny>=20:blockers.append('TINY_LOOPS')
    if micro+dangling>=20:blockers.append('MICRO_OR_DANGLING_FRAGMENTS')
    if risk_pairs:blockers.append('RELIEF_SPACING_REVIEW_REQUIRED')
    return dict(status='HOLD' if blockers else 'REVIEW_REQUIRED',blockers=blockers,
        isolated_micro_curve_count=int(micro),dangling_fragment_count=int(dangling),
        long_curve_continuity=dict(long_threshold_pixels=20,long_curve_count=sum(c['length']/unit>=20 for c in curves),
            long_curve_length_ratio=sum(c['length'] for c in curves if c['length']/unit>=20)/max(total,1e-12),
            mean_source_edges_per_curve=float(np.mean([len(c['source_support']['pieces']) for c in curves]))),
        self_intersection_count=crossings,oversized_junction_count=oversized,
        welded_oversized_junction_count=0,curve_curvature_spikes=spikes,tiny_loop_count=int(tiny),
        minimum_feature_spacing=dict(sampled_centerline_distance_pixels=minimum,
            conservative_centerline_lower_bound_pixels=0. if minimum is not None else None,
            physical_scale_known=network['physical_scale']['millimeters_per_unit'] is not None,
            certified=False,scope='12-nearest sampled points; excludes same-curve spacing; contacts included'),
        relief_collision_risk=dict(candidate_curve_pairs=len(risk_pairs),profile_defined=False,
            actual_solid_collisions='NOT_EVALUATED',policy='No ridge dimensions or crossing height order inferred'),
        model_ready_component_ratio=sum(all(v) for v in bycomponent.values())/max(1,len(bycomponent)),
        model_ready_curve_ratio=sum(q['model_ready'] for q in per)/max(1,len(per)),
        model_ready_length_ratio=sum(c['length'] for c,q in zip(curves,per) if q['model_ready'])/max(total,1e-12),
        junction_classifications=dict(byclass),curves=per,
        limitations=['Self-crossings are sampled proper segment crossings, not exact cubic certification or overlap detection.',
            'Proximity screening may include deliberate true branches and crossings; risks require Relief Builder review.',
            'A split unresolved hub is not counted as repaired merely because its shared vertex was removed.',
            'Original components are used for readiness denominator; ratios are conservative, not art quality scores.'])
