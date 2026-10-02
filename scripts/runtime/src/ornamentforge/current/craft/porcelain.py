"""Standalone engraved-porcelain sample and inspectable style routing."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from skimage.morphology import skeletonize

from ..planar.master import ROOT, current_planar_spec, load_art, sha, source, write
from ..surface.transfer import map_surface
from .engraved import groove, skeleton_paths
from .experimental import etch, radial_sample
from .painted import PALETTE, rgbhex

OUT = ROOT/"runs/current/craft/porcelain"
SOURCES = {"phoenix_peony":"SX1_018", "shoudai_meihua":"SX1_048", "decorative":"DH_018"}
VARIANTS = ["phoenix_peony", "shoudai_meihua", "decorative_painted", "decorative_monochrome"]
GLAZES = {"ivory_white":"#E8E4D7", "pale_celadon":"#C8DDD0", "qingbai":"#C8E0DF", "light_olive_celadon":"#CDD5BA"}


def style_route(features):
    if features["line_density"]>=.65 and features["fill_noise_risk"]>=.55:
        return "monochrome_engraved", "High density and fill-noise risk"
    if features["line_density"]<.65 and features["motif_separability"]>=.5:
        return "painted_engraved", "Moderate density and separable regions"
    return "monochrome_engraved", "Conservative fallback: uncertain color segmentation"


def measure(image, ink):
    small=cv2.resize(ink,(768,768),interpolation=cv2.INTER_NEAREST)>0
    skeleton=skeletonize(small)
    degree=cv2.filter2D(skeleton.astype("uint8"),-1,np.ones((3,3),np.uint8))-skeleton
    junction=float(np.mean(degree[skeleton]>=4)) if skeleton.any() else 0
    _,_,stats,_=cv2.connectedComponentsWithStats(1-small.astype("uint8"))
    valid=[s for s in stats[1:] if s[0]>0 and s[1]>0 and s[0]+s[2]<768 and s[1]+s[3]<768]
    tiny=sum(int(s[4]) for s in valid if s[4]<30);filled=sum(int(s[4]) for s in valid)
    broad=sum(int(s[4]) for s in valid if s[4]>80)/max(filled,1)
    density=min(1,float(skeleton.mean())/.055);overlap=min(1,junction/.22)
    separability=np.clip(broad*(1-overlap*.35),0,1)
    risk=np.clip(.5*density+.25*overlap+.25*tiny/max(filled,1),0,1)
    return {"line_density":round(density,4),"line_overlap":round(overlap,4),
            "motif_separability":round(float(separability),4),"fill_noise_risk":round(float(risk),4),
            "raw_skeleton_pixel_fraction":float(skeleton.mean()),
            "limitations":"Raster proxies; not semantic confidence or artistic approval."}


def inputs(name):
    if name not in SOURCES:
        raise ValueError(f"Unknown porcelain sample: {name}")
    image=load_art(SOURCES[name],.92 if name!="decorative" else 1)
    if name=="decorative":
        blur=cv2.GaussianBlur(image,(0,0),1.2);ink=np.zeros(image.shape[:2],np.uint8)
        for channel in range(3):
            ink|=(cv2.Canny(blur[:,:,channel],55,130)>0).astype("uint8")
        ink=cv2.morphologyEx(ink,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    else:
        ink=(image.mean(2)<145).astype("uint8")
    return image,ink


def channels(name,image,ink):
    if name=="decorative":
        _,paths,qa=skeleton_paths(ink,10)
        masks={grade:np.zeros_like(ink) for grade in ("primary","secondary","micro")}
        for path in paths:
            length=np.linalg.norm(np.diff(path,axis=0),axis=1).sum()
            grade="primary" if length>150 else "secondary" if length>45 else "micro"
            cv2.polylines(masks[grade],[np.round(path).astype("int32")],False,1,1)
    else:
        _,paths,qa,masks=etch(image)
    settings=(("primary",4.8,.036),("secondary",3.5,.024),("micro",2.4,.012))
    raw=np.array([cv2.GaussianBlur(groove(masks[g],width,depth),(0,0),.85) for g,width,depth in settings])
    union=raw.max(0);total=raw.sum(0)
    raw*=np.divide(union,total,out=np.zeros_like(total),where=total>0)[None]
    qa.update(grades={g:{"radius_px":w,"depth":d} for g,w,d in settings},
              grading_limit="Path length proxy, not semantic primary contour detection",
              junction="max union avoids additive pits")
    return -raw,paths,qa


def interpret_reference(path, colored_boundaries=False):
    from .interpreter import read_image
    image=read_image(path,size=1400)
    if image.std()<3:
        raise ValueError("Uniform image has no readable ornament; manual review required")
    if colored_boundaries:
        blur=cv2.GaussianBlur(image,(0,0),1.2);ink=np.zeros(image.shape[:2],np.uint8)
        for channel in range(3):ink|=(cv2.Canny(blur[:,:,channel],55,130)>0).astype("uint8")
    else:ink=(image.mean(2)<145).astype("uint8")
    metrics=measure(image,ink);style,reason=style_route(metrics)
    return {"version":"current","craft":"engraved","source":str(Path(path).resolve()),
            "source_sha256":sha(Path(path)),"metrics":metrics,"automatic_style":style,
            "reason":reason,"color_boundary_extraction":colored_boundaries,
            "status":"HEURISTIC_REQUIRES_VISUAL_REVIEW"}


def build_sample(name="phoenix_peony", out=None):
    """Build a self-contained signed-field porcelain sample without historical runs."""
    image,ink=inputs(name);fields,paths,qa=channels(name,image,ink)
    out=Path(out) if out else OUT/name
    out.mkdir(parents=True,exist_ok=True)
    radial=np.linspace(.004,5,420);theta=np.arange(1280)*2*np.pi/1280
    x=radial[:,None]*np.cos(theta);y=radial[:,None]*np.sin(theta);rho=np.hypot(x,y)/5
    mapped=np.array([radial_sample(field,x,y) for field in fields])
    border=(.025*np.exp(-((rho-.97)/.018)**2)).astype("f4")
    mapped=np.concatenate([mapped,border[None]])
    base=GLAZES["qingbai" if name=="shoudai_meihua" else "ivory_white"]
    rgb=np.broadcast_to(rgbhex(base),(*x.shape,3)).copy()
    removal=-mapped[:3].sum(0);rgb*=1-np.clip(removal/.036,0,1)[...,None]*.045
    np.savez_compressed(out/"master.npz",x=x,y=y,fields=mapped,
                        roles=np.array(["NEG_primary","NEG_secondary","NEG_micro","Host_lip_only"]),
                        rgb=rgb,inner_radius=0)
    identifier=SOURCES[name]
    spec=current_planar_spec(name,identifier);spec["ornament"]["relief_mode"]="engrave";write(out/"OrnamentSpec.json",spec)
    write(out/"ArtPlan.json",{"version":"current","id":name,"status":"SAMPLE_PENDING_VISUAL_REVIEW",
                              "craft":"engraved_porcelain","source_id":identifier,
                              "risks":["Line grading is a length proxy","Not manufacturing certification"]})
    write(out/"AssemblyPlan.json",{"version":"current","source_id":identifier,"host":"curved_plate",
                                   "positive_motif_fields":0,"editability":"Signed role fields and centerline guides"})
    write(out/"references.json",{"source_id":identifier,"path":str(source(identifier)),"sha256":sha(source(identifier))})
    guides=[{"role":"engraved_centerline","closed":False,"points":[[(float(px)/1399-.5)*10,(.5-float(py)/1399)*10] for px,py in path[::2]]}
            for path in paths if len(path)>3]
    write(out/"editable_regions.json",guides)
    map_surface(out,"curved_plate",out,require_review=False)
    qa.update(positive_motif_fields=0,all_detail_nonpositive=bool(np.all(mapped[:3]<=0)),
              max_removed=float(-mapped[:3].sum(0).min()),manufacturing_ready=False)
    write(out/"construction_qa.json",qa)
    return out
