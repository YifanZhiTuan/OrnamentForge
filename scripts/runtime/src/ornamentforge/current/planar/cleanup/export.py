"""Export clean curves with true-branch graph attachments preserved."""
from copy import deepcopy
from .geometry import controls,payload


def to_planar_master(original,network,network_hash):
    from ..contract import PlanarMasterV1
    m=original.to_dict() if hasattr(original,'to_dict') else deepcopy(original)
    # Source entities are replaced with clean entities; complete old input remains
    # hash-bound on disk. Historical extraction provenance is retained verbatim.
    m['editable_geometry_references']=[];m['semantic_roles']=[];m['z_order']=[];m['source_correspondence']=[]
    m['open_stroke_graph']=dict(state='EXTRACTED',nodes=[],edges=[])
    junctions={j['junction_id']:j for j in network['junctions']}
    lookup={}
    for j in network['junctions']:
        for p in j['ports']:lookup[(p['source_edge'],p['side'])]=j['junction_id']
    nodes={};mapping=[]
    def node_id(port,curve_id,position):
        key=tuple(port);j=junctions.get(lookup.get(key,''),{})
        if j.get('classification')=='TRUE_BRANCH':nid='model_node_'+j['junction_id']
        else:nid='model_port_'+key[0]+'_'+str(key[1])
        if nid in nodes and nodes[nid]!=position:raise ValueError('Branch coordinate mismatch')
        nodes[nid]=position
        return nid
    for curve in network['curves']:
        seg=controls(dict(points=curve['control_points']));pieces=curve['source_support']['pieces']
        groups=[];first=0
        for i,p in enumerate(pieces[:-1]):
            endport=(p['source_edge'],0 if p['reversed'] else 1)
            junction=junctions.get(lookup.get(endport,''),{})
            if junction.get('classification')=='TRUE_BRANCH':groups.append((first,i+1));first=i+1
        groups.append((first,len(pieces)))
        for part,(a,b) in enumerate(groups):
            pa,pb=pieces[a],pieces[b-1]
            curve_seg=seg[pa['segment_start']:pb['segment_end']]
            data=payload(curve_seg)
            eid=f"model_edge_{curve['curve_id']}_{part}";gid='geometry_'+eid
            startport=(pa['source_edge'],1 if pa['reversed'] else 0);endport=(pb['source_edge'],0 if pb['reversed'] else 1)
            start=node_id(startport,curve['curve_id'],data['points'][0]['co'][:2])
            if curve['closed'] and len(groups)==1:
                end=start
            else:end=node_id(endport,curve['curve_id'],data['points'][-1]['co'][:2])
            weight=sum(p['length'] for p in pieces[a:b]);width=sum(p['width']*p['length'] for p in pieces[a:b])/weight
            m['editable_geometry_references'].append(dict(id=gid,representation='bezier_curve',closed=False,data=data))
            m['open_stroke_graph']['edges'].append(dict(id=eid,start=start,end=end,geometry_ref=gid,width=width))
            m['semantic_roles'].append(dict(entity_ref=eid,role='model_curve_segment',basis='inferred'))
            m['z_order'].append(dict(entity_ref=eid,layer=2,basis='inferred'))
            m['source_correspondence'].append(dict(entity_ref=eid,source_ref='model_cleanup',locator=f"curves/{curve['curve_id']}/segments/{part}"))
            mapping.append(dict(entity=eid,curve_id=curve['curve_id'],source_edges=[p['source_edge'] for p in pieces[a:b]]))
    m['open_stroke_graph']['nodes']=[dict(id=k,position=v) for k,v in sorted(nodes.items())]
    m['provenance'].append(dict(id='model_cleanup',kind='CleanCurveNetworkV1',source='clean_curve_network.json',sha256=network_hash,
        details=dict(input_master_hash=network['input_master_hash'],support_mask_hash=network['support_mask_hash'],
            entity_mapping=mapping,junctions=network['junctions'],model_qa={k:v for k,v in network['qa'].items() if k!='curves'},
            policy=network['policy'],quarantine_count=len(network['quarantine']),
            curve_storage='Long curves in companion network; PlanarMaster graph split at true branches to retain interior attachment topology')))
    m['qa_state']['limitations']=['Model topology QA: '+network['qa']['status']+'; diagnostic/review output, not blanket Relief approval.',
        'Historical raster QA remains in source provenance but is not this cleanup objective.',
        'Quarantined original cubics are retained in clean_curve_network.json; unresolved hub interiors are not silently reconstructed.',
        'Crossing curves have independent graph topology; relief collision/height order is not resolved.',
        'No ridge width, height, profile or bevel has been selected.']
    for edge, geometry in zip(m['open_stroke_graph']['edges'],m['editable_geometry_references']):
        ends=[geometry['data']['points'][i]['co'][:2] for i in (0,-1)]
        expected=[nodes[edge[k]] for k in ('start','end')]
        if ends!=expected:
            raise ValueError(f"Cleanup endpoint mismatch: {edge['id']}: {ends} != {expected}")
    return PlanarMasterV1.from_dict(m)
