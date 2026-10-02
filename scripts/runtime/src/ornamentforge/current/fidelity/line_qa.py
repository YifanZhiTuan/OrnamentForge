"""Line-specific numerical review; never an aesthetic/manufacturing approval."""
import cv2
import numpy as np
from skimage.morphology import skeletonize
from .stroke_graph import adjacency


def skeleton_length(skeleton):
    graph=adjacency(skeleton)
    return sum(np.linalg.norm(np.array(a)-b) for a,ns in graph.items() for b in ns)/2


def fragmentation(nodes, edges, short_limit=4.):
    lengths=[e["length"] for e in edges]
    short=[v for v in lengths if v < short_limit]
    # Graph connected components, including real loops and standalone strokes.
    parents=list(range(len(nodes)))
    def root(i):
        while parents[i]!=i:
            parents[i]=parents[parents[i]];i=parents[i]
        return i
    for e in edges:parents[root(e["end"])]=root(e["start"])
    component_edges={}
    for e in edges:component_edges.setdefault(root(e["start"]),[]).append(e)
    isolated=sum(len(es)==1 and es[0]["length"] < short_limit for es in component_edges.values())
    ratio=len(short)/max(1,len(edges));length_ratio=sum(short)/max(1e-12,sum(lengths))
    # Short junction-to-junction links may be legitimate: require a count AND a
    # large fraction, or a material amount of disconnected short content.
    blockers=[]
    if len(short)>=20 and (ratio>.5 or length_ratio>.1):blockers.append("SHORT_FRAGMENT_EXPLOSION")
    if isolated>=20 and isolated/max(1,len(component_edges))>.25:blockers.append("ISOLATED_FRAGMENT_EXPLOSION")
    return dict(short_edge_limit_pixels=short_limit, short_edge_count=len(short),
        short_fragment_ratio=ratio,short_edge_length_ratio=length_ratio,
        isolated_component_count=isolated,graph_component_count=len(component_edges),
        endpoint_count=sum(n["degree"]==1 for n in nodes),
        junction_count=sum(n["degree"]>=3 for n in nodes),
        intersection_count=sum(n["degree"]>=4 for n in nodes),
        status="HOLD" if blockers else "PASS",blockers=blockers)


def line_qa(source_mask, preview, nodes, edges, tolerance=2.):
    reconstructed=np.asarray(preview.convert("L")) < 128
    src=source_mask.astype(bool)
    a,b=skeletonize(src),skeletonize(reconstructed)
    if not a.any() or not b.any():
        raise ValueError("Empty source or reconstruction skeleton")
    da=cv2.distanceTransform((~a).astype(np.uint8),cv2.DIST_L2,5)
    db=cv2.distanceTransform((~b).astype(np.uint8),cv2.DIST_L2,5)
    recall=float((src & reconstructed).sum()/max(1,src.sum()))
    precision=float((src & reconstructed).sum()/max(1,reconstructed.sum()))
    tolerant=float((db[a]<=tolerance).mean())
    lengths=[float(skeleton_length(s)) for s in (a,b)]
    # Dilated line occupancy is a coarse silhouette proxy, not a filled motif mask.
    kernel=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(17,17))
    sa=cv2.dilate(src.astype(np.uint8),kernel)>0;sb=cv2.dilate(reconstructed.astype(np.uint8),kernel)>0
    f=fragmentation(nodes,edges);blockers=list(f["blockers"])
    if tolerant < .85:blockers.append("LOW_SKELETON_RECALL")
    if recall < .65 or precision < .6:blockers.append("LOW_STROKE_AGREEMENT")
    if not .7 <= lengths[1]/lengths[0] <= 1.3:blockers.append("STROKE_LENGTH_DRIFT")
    return dict(status="HOLD" if blockers else "PASS",visual_review="REVIEW_REQUIRED",
        blockers=blockers,stroke_pixel_recall=recall,stroke_precision=precision,
        tolerant_skeleton_recall=tolerant,tolerant_skeleton_precision=float((da[b]<=tolerance).mean()),
        tolerance_pixels=tolerance,chamfer_mean_pixels=float((db[a].mean()+da[b].mean())/2),
        source_skeleton_distance_p95_pixels=float(np.percentile(db[a],95)),
        connected_component_count={"source":int(cv2.connectedComponents(src.astype(np.uint8),8)[0]-1),
            "reconstruction":int(cv2.connectedComponents(reconstructed.astype(np.uint8),8)[0]-1)},
        source_stroke_length_pixels=lengths[0],reconstruction_stroke_length_pixels=lengths[1],
        total_stroke_length_ratio=lengths[1]/lengths[0],
        major_silhouette_similarity=float((sa&sb).sum()/max(1,(sa|sb).sum())),
        silhouette_basis="8px dilated ink occupancy IoU, not semantic silhouette",
        fragment_qa=f,source_basis="normalized binary mask BEFORE cleanup/healing/pruning",
        limitations=["2D crossings do not infer over/under order.",
                     "Representative per-edge widths cannot preserve all local width variation.",
                     "Thresholded source is a proxy; raw source visual review is mandatory."])
