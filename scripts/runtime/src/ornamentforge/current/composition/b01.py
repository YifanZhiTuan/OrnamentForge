"""B01-only deterministic, explicit curve/placement build plan; no bpy."""
from dataclasses import asdict, dataclass
import bisect
import hashlib
import json
import math

from ornamentforge.models import OrnamentSpec


@dataclass(frozen=True)
class B01Parameters:
    vine_amplitude: float = 0.24
    vine_frequency: float = 1.5
    vine_width: float = 0.055
    leaf_count: int = 14
    leaf_scale: float = 0.38
    alternating_leaf_angle: float = 58.0
    emboss_height: float = 0.07
    margin: float = 0.18
    seed: int = 2187


def bezier(a, b, t):
    u = 1 - t
    points = [a["co"], a["right"], b["left"], b["co"]]
    return [sum(w * p[k] for w, p in zip((u**3, 3*u*u*t, 3*u*t*t, t**3), points)) for k in range(3)]


def generate_vine(p, half_span):
    phase = int(hashlib.sha256(f"B01:vine:{p.seed}".encode()).hexdigest()[:8], 16) / 2**32 * 2*math.pi
    n = max(24, math.ceil(p.vine_frequency * 24))
    step = 2 * half_span / n
    omega = 2*math.pi*p.vine_frequency / (2*half_span)
    points = []
    for i in range(n+1):
        x = -half_span + i*step
        y = p.vine_amplitude * math.sin(omega*x + phase)
        slope = p.vine_amplitude * omega * math.cos(omega*x + phase)
        points.append({"co": [x, y, 0], "left": [x-step/3, y-slope*step/3, 0],
                       "right": [x+step/3, y+slope*step/3, 0]})
    return points


def generate_leaf():
    # Rounded leaf outline is a closed Bezier stroke; its width is the rib cross-section.
    leaf = [
        {"co": [0,0,0], "left": [0,-0.06,0], "right": [0,0.06,0]},
        {"co": [0.45,0.25,0], "left": [0.22,0.25,0], "right": [0.72,0.25,0]},
        {"co": [1,0,0], "left": [1,0.06,0], "right": [1,-0.06,0]},
        {"co": [0.45,-0.25,0], "left": [0.72,-0.25,0], "right": [0.22,-0.25,0]}]
    return leaf


def build_plan(spec: OrnamentSpec, overrides: dict | None = None, resolver=None) -> dict:
    data = spec.to_dict()
    if (data["base_surface"]["type"] != "plane" or data["ornament"]["family"] != "botanical"
            or data["ornament"].get("subject") != "continuous_vine"
            or data["ornament"]["relief_mode"] != "emboss" or data["target"]["mode"] != "editable"
            or data.get("openings") or data["layout"]["method"] != "path_repeat"
            or data["input"]["mode"] != "text" or data["composition"]["primary_axis"] != "Z"
            or data.get("surface_mapping", {}).get("method", "planar") != "planar"):
        raise ValueError("B01 supports only editable text-driven planar continuous vine emboss")
    dims = data["base_surface"].get("dimensions")
    if dims is None:
        raise ValueError("B01 requires explicit plate dimensions")
    values = asdict(B01Parameters())
    values.update(seed=spec.seed, emboss_height=data["geometry"]["ornament_height"],
                  margin=data["layout"].get("border_clearance", 0.18),
                  leaf_count=max(2, round(24 * data["ornament"].get("density", 0.6))))
    values.update(overrides or {})
    p = B01Parameters(**values)
    for key, value in asdict(p).items():
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError(f"Invalid B01 parameter {key}")
    if type(p.leaf_count) is not int or not 2 <= p.leaf_count <= 128:
        raise ValueError("leaf_count must be an integer from 2 to 128")
    if type(p.seed) is not int or p.seed != spec.seed:
        raise ValueError("Build-plan seed must match the spec")
    if p.emboss_height != data["geometry"]["ornament_height"]:
        raise ValueError("Emboss height must match spec")
    if not 0 < p.vine_frequency <= 8 or not 0 < p.leaf_scale <= 2 or not 0 < p.vine_width <= 0.5:
        raise ValueError("Unsupported B01 size/frequency")
    if p.emboss_height <= 0 or p.margin < data["layout"].get("border_clearance", 0):
        raise ValueError("Invalid emboss height or margin")
    feature = data["geometry"]["minimum_feature_width"]
    leaf_stroke = max(feature * 1.25, p.vine_width * 0.6)
    if min(p.vine_width, leaf_stroke) < feature:
        raise ValueError("Curve stroke narrower than minimum feature width")
    # Conservative reservation includes leaf length, stroke and Bezier handle envelope.
    half_span = dims[0] / 2 - p.margin - p.leaf_scale * 1.15 - p.vine_width
    if half_span <= 0 or p.vine_amplitude + p.leaf_scale * 1.15 + p.vine_width > dims[1]/2-p.margin:
        raise ValueError("B01 ornament cannot fit inside requested margins")
    if resolver is None:
        points = generate_vine(p, half_span)
    else:
        points = resolver.resolve("vine", {"scale":1,"stroke_width":p.vine_width,"leaf_count":p.leaf_count,
                                  "vine_amplitude":p.vine_amplitude,"vine_frequency":p.vine_frequency},
                                  lambda: generate_vine(p, half_span))
    n = len(points)-1
    samples = [bezier(points[i], points[i+1], j/32) for i in range(n) for j in range(32)]
    samples.append(points[-1]["co"])
    lengths = [0.0]
    for a, b in zip(samples, samples[1:]):
        lengths.append(lengths[-1] + math.dist(a, b))
    leaves = []
    for i in range(p.leaf_count):
        distance = lengths[-1] * (i+0.5)/p.leaf_count
        k = min(len(samples)-1, bisect.bisect_left(lengths, distance))
        t = (distance-lengths[k-1])/(lengths[k]-lengths[k-1])
        a, b = samples[k-1], samples[k]
        angle = math.atan2(b[1]-a[1], b[0]-a[0]) + math.radians(p.alternating_leaf_angle)*(1 if i%2==0 else -1)
        leaves.append({"name": f"B01_Leaf_{i:03d}", "location": [a[j]+t*(b[j]-a[j]) for j in range(3)],
                       "rotation_z": angle, "scale_xy": p.leaf_scale})
    if resolver is None:
        leaf = generate_leaf()
    else:
        leaf = resolver.resolve("leaf", {"scale":p.leaf_scale,"stroke_width":leaf_stroke,"leaf_count":p.leaf_count},
                                generate_leaf)
    plan = {"plan_version": "1.0", "benchmark": "B01", "spec_hash": spec.spec_hash,
            "parameters": asdict(p), "plate_dimensions": dims, "leaf_stroke_width": leaf_stroke,
            "minimum_feature_width": feature, "tolerance": 0.0001,
            "attachment_distance": 0.0001, "burial_threshold": 0.0001,
            "vine_control_points": points, "leaf_motif_control_points": leaf, "leaf_transforms": leaves,
            "render": {"resolution": [640, 480], "samples": 16, "engine": "CYCLES", "device": "CPU"}}
    if resolver is not None:
        plan["motif_sources"] = resolver.sources
        del plan["vine_control_points"]
        del plan["leaf_motif_control_points"]
    plan["plan_hash"] = hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return plan
