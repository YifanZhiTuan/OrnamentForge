"""Line-art extraction: binary ink -> skeleton graph -> editable cubic geometry."""
from hashlib import sha256
from pathlib import Path
import cv2
import numpy as np
from skimage.morphology import skeletonize

from .reference_mode import load_rgb, classify_reference
from .stroke_graph import heal_gaps, prune_spurs, trace_graph
from .stroke_curves import fit_cubics, curve_payload, rasterize_master
from .line_qa import line_qa


def binary_strokes(rgb, mixed=False):
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    # Closing estimates light background without eroding/dilating the stroke mask.
    background=cv2.morphologyEx(gray,cv2.MORPH_CLOSE,np.ones((31,31),np.uint8))
    normalized=np.clip(gray.astype(float)/np.maximum(background,32)*255,0,255).astype(np.uint8)
    otsu,_=cv2.threshold(normalized,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
    upper=min(220.,max(200.,otsu+35.))
    strong=normalized<=otsu
    weak=normalized<upper
    if mixed:
        # Minimal mixed path: only neutral dark strokes, not colored fill interiors.
        chroma=rgb.max(axis=2).astype(float)-rgb.min(axis=2)
        eligible=(chroma<35)&(gray<180)
        strong &= eligible;weak &= eligible
    count,labels=cv2.connectedComponents(weak.astype(np.uint8),8)
    seeded=np.zeros(count,bool);seeded[np.unique(labels[strong & weak])]=True;seeded[0]=False
    raw=seeded[labels]
    count,labels,stats,_=cv2.connectedComponentsWithStats(raw.astype(np.uint8),8)
    keep=stats[:,cv2.CC_STAT_AREA]>=2;keep[0]=False
    cleaned=keep[labels]
    return raw,cleaned,dict(method="background closing normalization + Otsu-seeded connected antialias collapse",
        background_kernel_pixels=31,otsu_threshold=float(otsu),antialias_upper_threshold=upper,
        removed_single_pixels=int((raw & ~cleaned).sum()),morphology="No global opening/closing of stroke mask",
        mixed_neutral_dark_only=mixed)


def extract_line_art(path, scale=None, classification=None, resolution=2048, mixed=False):
    from ..input.planar_routes import base, entity
    from ..planar.contract import PlanarMasterV1
    rgb,sampling=load_rgb(path,resolution)
    h,w=rgb.shape[:2];factor=10/max(w,h)
    raw,mask,binary_info=binary_strokes(rgb,mixed)
    if not mask.any():raise ValueError("LINE_ART contains no extractable strokes")
    skeleton=skeletonize(mask)
    skeleton,mask,healing=heal_gaps(skeleton,mask,max_gap=3)
    skeleton=skeletonize(skeleton)
    skeleton,removed_spurs=prune_spurs(skeleton,2.)
    nodes,edges=trace_graph(skeleton)
    if not edges:raise ValueError("LINE_ART contains no continuous stroke edges")
    distance=cv2.distanceTransform(mask.astype(np.uint8),cv2.DIST_L2,5)
    m=base("FIDELITY_RECONSTRUCTION",[-w*factor/2,-h*factor/2,w*factor/2,h*factor/2],scale)
    m["source_hash"]=sha256(Path(path).read_bytes()).hexdigest()
    classification=classification or classify_reference(path,"line_art")
    details=dict(reference_mode=classification,sampling=sampling,binarization=binary_info,
        gap_healing=healing,spur_cleanup=dict(max_length_pixels=2.,removed=removed_spurs,passes=1),
        curve_fitting=dict(method="recursive chord-parameterized least-squares cubic",sample_error_pixels=.7),
        nodes=nodes,edges=[],loop_representation="self-loop graph edge, coincident end knots, noncyclic Bezier to preserve PlanarMasterV1 schema")
    m["provenance"].append(dict(id="line_reference",kind="raster_line_art",source=str(Path(path).resolve()),
        sha256=m["source_hash"],details=details))
    m["open_stroke_graph"]={"state":"EXTRACTED","nodes":[],"edges":[]}
    def xy(p):return [float((p[0]-w/2)*factor),float((h/2-p[1])*factor)]
    for i,node in enumerate(nodes):
        m["open_stroke_graph"]["nodes"].append(dict(id=f"stroke_node_{i}",position=xy(node["pixel"])))
    for i,edge in enumerate(edges):
        samples=np.rint(edge["pixels"]).astype(int)
        # Pixel-center EDT diameter; subtracting a full pixel erases two-pixel
        # antialiased strokes. Keep this explicit, mildly conservative estimator.
        widths=np.maximum(1.,2*distance[samples[:,1],samples[:,0]])
        width=float(np.median(widths))
        curve=curve_payload(fit_cubics(edge["pixels"]),w,h)
        gid,eid=f"stroke_geometry_{i}",f"stroke_edge_{i}"
        m["editable_geometry_references"].append(dict(id=gid,representation="bezier_curve",closed=False,data=curve))
        m["open_stroke_graph"]["edges"].append(dict(id=eid,start=f"stroke_node_{edge['start']}",
            end=f"stroke_node_{edge['end']}",geometry_ref=gid,width=width*factor))
        entity(m,eid,"closed_stroke_loop" if edge["loop"] else "line_stroke","line_reference",f"skeleton/edges/{i}",layer=2)
        details["edges"].append(dict(id=eid,length_pixels=edge["length"],width_pixels=width,width_basis="median 2*pixel-center EDT",
            width_min_pixels=float(widths.min()),width_max_pixels=float(widths.max()),loop=edge["loop"],
            skeleton_sample_count=len(edge["pixels"]),bezier_knots=len(curve["points"])))
    preview=rasterize_master(m,(w,h),strokes_only=True)
    qa=line_qa(raw,preview,nodes,edges)
    qa["unresolved_near_gap_pairs"]=healing["unresolved_near_pairs"]
    qa["healed_gap_count"]=len(healing["healed"])
    qa["max_junction_cluster_radius_pixels"]=float(max(n["cluster_radius"] for n in nodes))
    if qa["max_junction_cluster_radius_pixels"]>4:
        qa["blockers"].append("LARGE_JUNCTION_CLUSTER");qa["status"]="HOLD"
    details["line_qa"]=qa
    m["qa_state"]["limitations"]=["Line QA: "+qa["status"]+"; visual review required.",
        "Crossings are 2D graph intersections, not semantic over/under relations.",
        "Widths are representative per edge; local modulation is not reproduced.",
        "Loops are graph self-edges; no enclosed white-space fill regions are inferred.",
        "Semantic motifs, depth and repeat structure are not inferred."]
    master=PlanarMasterV1.from_dict(m)
    return dict(master=master,qa=qa,mask=mask,skeleton=skeleton,source_mask=raw,
        preview=preview,classification=classification,sampling=sampling)
