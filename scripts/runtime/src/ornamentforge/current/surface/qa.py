"""Numerical transfer gates, including conservative mesh-geodesic error bounds."""
import math
from .math3d import (SurfaceError, norm, sub, add, mul, cross2, finite)

DEFAULT_THRESHOLDS = dict(round_trip_error=1e-6, angle_distortion=.1, area_distortion=.15,
                         max_stretch=1.1, min_stretch=.9, orientation_error=1e-6,
                         geodesic_spacing_error=.1, minimum_feature_width=0,
                         sampling_error=1e-4)


def geodesic_bounds(mapper, a, b, offset=0):
    """Exact analytic intrinsic distance; selected UV-chart path upper/chord lower bound.

    The UV-mesh upper bound follows the straight UV segment, split at every face
    edge. This is not an exact global mesh geodesic solver, and is labeled as such.
    """
    kind = mapper.data["host_type"]
    engine = mapper.engine
    if kind == "REVOLUTION_VASE":
        return engine.spacing_bounds(a,b,offset)
    sa,sb = mapper.to_surface(a),mapper.to_surface(b)
    pa,pb = add(sa["surface_position"],mul(sa["normal"],offset)),add(sb["surface_position"],mul(sb["normal"],offset))
    if kind == "PLANE":
        d = norm(sub(pa,pb))
    elif kind == "CYLINDER":
        du = (b[0]-a[0]+.5) % 1-.5
        d = math.hypot(2*math.pi*(engine.p["radius"]+offset)*du,engine.p["height"]*(b[1]-a[1]))
    elif kind == "CONE":
        shift = offset*engine.c/engine.k
        r1,r2 = norm(a)+shift,norm(b)+shift
        phi = math.atan2(b[1],b[0])-math.atan2(a[1],a[0])
        delta = abs((phi+engine.sector/2) % engine.sector-engine.sector/2)
        cutoff = max(0,engine.p["min_slant"]+shift)
        alpha,beta = math.acos(min(1,cutoff/r1)),math.acos(min(1,cutoff/r2))
        if delta > alpha+beta:
            d = math.sqrt(max(0,r1*r1-cutoff*cutoff))+math.sqrt(max(0,r2*r2-cutoff*cutoff))+cutoff*(delta-alpha-beta)
        else:
            d = math.hypot(r1-r2,2*math.sqrt(r1*r2)*math.sin(delta/2))
    else:
        direction = sub(b,a)
        cuts = {0.,1.}
        for tri in engine.selected:
            uv = tri["uv"]
            for p,q in zip(uv,uv[1:]+uv[:1]):
                edge = sub(q,p)
                det = cross2(direction,edge)
                if abs(det) <= 1e-14:
                    continue
                t,s = cross2(sub(p,a),edge)/det,cross2(sub(p,a),direction)/det
                if 0 < t < 1 and -1e-9 <= s <= 1+1e-9:
                    cuts.add(t)
        ordered = sorted(cuts)
        upper, previous = 0.,None
        for t0,t1 in zip(ordered,ordered[1:]):
            if t1-t0 < 1e-12:
                continue
            mid = add(a,mul(direction,(t0+t1)/2))
            triangle = mapper.to_surface(mid)["triangle_id"]
            s0 = mapper.to_surface(add(a,mul(direction,t0)),triangle_hint=triangle)
            s1 = mapper.to_surface(add(a,mul(direction,t1)),triangle_hint=triangle)
            p0 = add(s0["surface_position"],mul(s0["normal"],offset))
            p1 = add(s1["surface_position"],mul(s1["normal"],offset))
            if previous is not None and norm(sub(previous,p0)) > 1e-8:
                raise SurfaceError("OFFSET_FACE_DISCONTINUITY", "Offset crosses a sharp mesh edge; no implicit stitching")
            upper += norm(sub(p1,p0))
            previous = p1
        return norm(sub(pb,pa)),upper,"MESH_GEODESIC_BOUNDS"
    return d,d,"ANALYTIC_INTRINSIC"


class SurfaceTransferQA:
    def __init__(self, thresholds=None):
        if thresholds is not None and (not isinstance(thresholds,dict) or set(thresholds)-set(DEFAULT_THRESHOLDS)):
            raise SurfaceError("QA_THRESHOLDS", "Unknown QA threshold")
        self.thresholds = DEFAULT_THRESHOLDS | (thresholds or {})
        finite(list(self.thresholds.values()))
        if any(v < 0 for v in self.thresholds.values()) or self.thresholds["min_stretch"] <= 0:
            raise SurfaceError("QA_THRESHOLDS", "Nonnegative thresholds and positive min_stretch required")

    def assess(self, mapper, heatmap, spacing, sampling_error, missing_feature_width=False):
        if not heatmap:
            raise SurfaceError("EMPTY_TRANSFER", "No mapped samples")
        max_roundtrip = 0.
        for row in heatmap:
            s = row["sample"]
            inv = mapper.to_domain(s["surface_position"],uv_hint=s["uv"],triangle_hint=s["triangle_id"])
            back = mapper.to_surface(inv["uv"],triangle_hint=inv["triangle_id"])
            max_roundtrip = max(max_roundtrip,norm(sub(s["surface_position"],back["surface_position"])),norm(sub(s["uv"],inv["uv"])))
        widths = [r["feature_width_after_mapping"] for r in heatmap if r["feature_width_after_mapping"] is not None]
        metrics = dict(round_trip_error=max_roundtrip,
            angle_distortion=max(r["distortion"]["angle_distortion"] for r in heatmap),
            area_distortion=max(r["distortion"]["area_distortion"] for r in heatmap),
            max_stretch=max(r["distortion"]["principal_stretches"][1] for r in heatmap),
            min_stretch=min(r["distortion"]["principal_stretches"][0] for r in heatmap),
            orientation_error=max(r["orientation_error"] for r in heatmap),
            geodesic_spacing_error=max((s["relative_error_bound"] for s in spacing),default=0),
            minimum_feature_width_after_mapping=min(widths) if widths else None,
            sampling_error=sampling_error)
        failures = []
        for key,limit in self.thresholds.items():
            if key == "minimum_feature_width":
                value = metrics["minimum_feature_width_after_mapping"]
                if value is not None and value < limit:
                    failures.append(key)
            elif key == "min_stretch":
                if metrics[key] < limit:
                    failures.append(key)
            elif metrics[key] > limit:
                failures.append(key)
        if missing_feature_width:
            failures.append("SOURCE_FEATURE_WIDTH_REQUIRED")
        return dict(schema_version="SurfaceTransferQA",status="HOLD" if failures else "PASS",
            metrics=metrics, thresholds=self.thresholds, failures=failures,
            heatmap=[{k:v for k,v in r.items() if k != "sample"} for r in heatmap], spacing=spacing,
            limitations=["Sampled differential QA, not a global injectivity or manufacturing certificate.",
                "Mesh geodesic error uses conservative chord/path bounds, not an exact global geodesic solver.",
                "Feature widths use declared source stroke widths or user-supplied lower bounds; no medial-axis inference.",
                "Planar visual QA remains separate; numerical PASS never starts Blender final."])
