"""Dense line-art engraving as one continuous signed field, not curve booleans."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path

import cv2
import numpy as np
from jsonschema import Draft202012Validator
from skimage.morphology import skeletonize

from ornamentforge.canonical_curve import canonical_bytes, content_hash
from ..surface import HostAdapter, SurfaceMapper, SurfaceTransferQA
from ..surface.math3d import differential_metrics, mul


HASH={"type":"string","pattern":"^[0-9a-f]{64}$"}
SCHEMA={"type":"object","additionalProperties":False,"required":[
    "schema_version","source_hash","width","height","design_domain",
    "binary_stroke_mask_hash","signed_distance_field","requested_groove_depth",
    "requested_groove_width_policy","edge_profile","surface_map_hash","provenance","qa"],
    "properties":{
        "schema_version":{"const":"EngravingFieldV1"},"source_hash":HASH,
        "width":{"type":"integer","minimum":1},"height":{"type":"integer","minimum":1},
        "design_domain":{"type":"object"},"binary_stroke_mask_hash":HASH,
        "signed_distance_field":{"type":"object"},
        "requested_groove_depth":{"type":"number","exclusiveMinimum":0},
        "requested_groove_width_policy":{"type":"object"},"edge_profile":{"type":"object"},
        "surface_map_hash":HASH,"provenance":{"type":"array","minItems":1},"qa":{"type":"object"}}}


def file_hash(path):return sha256(Path(path).read_bytes()).hexdigest()


@dataclass(frozen=True)
class EngravingFieldV1:
    _json:str
    def __post_init__(self):
        data=json.loads(self._json);canonical_bytes(data);Draft202012Validator(SCHEMA).validate(data)
        sdf=data["signed_distance_field"]
        if set(sdf)!={"path","sha256","format","shape","dtype","sign_convention"}:
            raise ValueError("Invalid signed-distance field descriptor")
        if sdf["shape"]!=[data["height"],data["width"]] or sdf["dtype"]!="float32":
            raise ValueError("Signed-distance shape/dtype mismatch")
        if data["edge_profile"].get("kind") not in {"V","U_ROUND","SOFT_ROUNDED"}:
            raise ValueError("Unsupported groove profile")
    @classmethod
    def from_dict(cls,data):return cls(canonical_bytes(data).decode("utf-8"))
    def to_dict(self):return json.loads(self._json)
    @staticmethod
    def schema():return deepcopy(SCHEMA)


def signed_distance(mask):
    """Negative inside ink, positive outside, in source pixels."""
    mask=np.asarray(mask,bool)
    inside=cv2.distanceTransform(mask.astype("uint8"),cv2.DIST_L2,5)
    outside=cv2.distanceTransform((~mask).astype("uint8"),cv2.DIST_L2,5)
    return (outside-inside).astype("f4"),inside.astype("f4")


def groove_depth(sdf,inside,depth=.035,profile="SOFT_ROUNDED",softness=2.):
    if depth<=0 or softness<=0:raise ValueError("Positive depth/softness required")
    x=np.clip(inside/softness,0,1)
    if profile=="V":shape=x
    elif profile=="U_ROUND":shape=np.sqrt(np.maximum(0,1-(1-x)**2))
    elif profile=="SOFT_ROUNDED":shape=x*x*(3-2*x)
    else:raise ValueError("Unknown groove profile")
    return np.where(sdf<0,depth*shape,0).astype("f4")


def width_metrics(mask):
    distance=cv2.distanceTransform(mask.astype("uint8"),cv2.DIST_L2,5)
    skel=skeletonize(mask)
    widths=2*distance[skel]
    return dict(minimum_retained_width_pixels=float(widths.min()),median_width_pixels=float(np.median(widths)),
        maximum_width_pixels=float(widths.max()),basis="2 * mask EDT sampled on skeleton")


def straight_vase_surface(domain, seam_angle=math.pi/2):
    x0,y0,x1,y1=domain
    width,height=x1-x0,y1-y0
    surface=HostAdapter.create("REVOLUTION_VASE",parameters={"profile":"straight_vase",
        "radius":width/(2*math.pi),"height":height,"seam_angle":seam_angle})
    return surface,[1/width,0,-x0/width,0,1/height,-y0/height]


def distortion_qa(surface,transform,feature_width):
    mapper=SurfaceMapper(surface);a,b,_,c,d,_=transform;heat=[]
    for v in (0,.25,.5,.75,1):
        for u in (0,.25,.5,.75,1):
            sample=mapper.to_surface([u,v]);du,dv=sample["dp_du"],sample["dp_dv"]
            dx=[du[i]*a+dv[i]*c for i in range(3)];dy=[du[i]*b+dv[i]*d for i in range(3)]
            metrics=differential_metrics(dx,dy,sample["normal"])
            heat.append(dict(sample=sample,sample_ref=f"field_{len(heat)}",path_id="dense_field",uv=[u,v],
                distortion=metrics,orientation_error=metrics["orientation_error"],
                feature_width_after_mapping=feature_width*metrics["principal_stretches"][0],
                circumference_scale=float(np.linalg.norm(sample["dp_du"])),vertical_scale=float(np.linalg.norm(sample["dp_dv"]))))
    return SurfaceTransferQA().assess(mapper,heat,[],0,False)


def geometry_screen(depth,radius,height):
    max_depth=float(depth.max());array=depth.astype(float)
    gradients=[]
    for axis,size in enumerate(array.shape):
        gradients.append(np.gradient(array,axis=axis) if size>1 else np.zeros_like(array))
    return dict(maximum_groove_depth=max_depth,minimum_radius_after_engraving=radius-max_depth,
        max_depth_gradient_pixels=float(max(np.abs(g).max() for g in gradients)),
        orientation_inversion_count=0 if radius>max_depth else 1,
        analytic_self_intersection="EXCLUDED_FOR_POSITIVE_RADIAL_GRAPH" if radius>max_depth else "FAILED",
        basis="straight cylinder radial graph r(u,v)=radius-depth; actual Blender mesh checked separately")


def canonical_hash(value):return content_hash(value)
