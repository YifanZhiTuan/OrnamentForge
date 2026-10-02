"""Bounded ornamental vase host: positive radius, strictly increasing linear height.

Piecewise cubic smoothstep interpolates a few (v, radius) points without overshoot.
This is a UV parameter map, NOT an isometric development or arbitrary vessel solver.
"""
import math
from copy import deepcopy
from .analytic import AnalyticHost, TAU
from .math3d import SurfaceError, finite, norm, sub, mul, add

PROFILES = {
    "straight_vase": [[0,1],[1,1]],
    "belly_vase": [[0,.72],[.25,1.05],[.55,1.2],[.85,.7],[1,.75]],
    "bottle_vase": [[0,.85],[.2,1],[.55,1],[.8,.45],[1,.45]],
}


class RevolutionVaseHost:
    kind = "REVOLUTION_VASE"

    def __init__(self, parameters):
        allowed = {"profile","profile_points","radius","height","z_min","seam_angle"}
        if not isinstance(parameters,dict) or set(parameters)-allowed:
            raise SurfaceError("VASE_PARAMETERS", "Unknown vase parameters")
        preset = parameters.get("profile","straight_vase")
        radius,height,z,seam = [parameters.get(k,d) for k,d in (("radius",4/TAU),("height",2.4),("z_min",0),("seam_angle",0))]
        finite([radius,height,z,seam])
        if radius <= 0 or height <= 0:
            raise SurfaceError("VASE_PARAMETERS", "Positive radius/height required")
        custom = parameters.get("profile_points")
        if custom is not None:
            if "profile" in parameters or "radius" in parameters:
                raise SurfaceError("VASE_PARAMETERS", "Custom points are absolute radii; do not also pass profile/radius")
            points = deepcopy(custom)
            preset = "custom"
        else:
            if not isinstance(preset,str) or preset not in PROFILES:
                raise SurfaceError("VASE_PROFILE", "Choose straight_vase, belly_vase or bottle_vase", "NOT_SUPPORTED")
            points = [[v,r*radius] for v,r in PROFILES[preset]]
        if not isinstance(points,list) or not 2 <= len(points) <= 32:
            raise SurfaceError("VASE_PROFILE", "Expected 2..32 profile points")
        for point in points:
            finite(point,2)
        if points[0][0] != 0 or points[-1][0] != 1 or any(r <= 0 for v,r in points):
            raise SurfaceError("VASE_PROFILE", "Profile must span [0,1] with strictly positive radii; no axis caps")
        if any(b[0]-a[0] <= 1e-6 for a,b in zip(points,points[1:])):
            raise SurfaceError("VASE_PROFILE", "v must strictly increase; folded/branching profiles unsupported")
        self.points = points
        self.p = dict(profile=preset,profile_points=points,height=height,z_min=z,seam_angle=seam,
                      interpolation="CUBIC_SMOOTHSTEP",height_mapping="z_min + height*v")
        self.bounds = [0,0,1,1]

    @classmethod
    def restore(cls, parameters):
        host = cls({k:parameters[k] for k in ("profile_points","height","z_min","seam_angle")})
        host.p["profile"] = parameters["profile"]
        return host

    def radius_at(self, v):
        if not -1e-10 <= v <= 1+1e-10:
            raise SurfaceError("OUTSIDE_DOMAIN", "Vase height outside [0,1]")
        v = min(1,max(0,v))
        a,b = next(((a,b) for a,b in zip(self.points,self.points[1:]) if v <= b[0]),(self.points[-2],self.points[-1]))
        length,delta = b[0]-a[0],b[1]-a[1]
        t = (v-a[0])/length
        return a[1]+delta*(3*t*t-2*t*t*t),delta*6*t*(1-t)/length,delta*(6-12*t)/(length*length)

    def forward(self, uv, triangle_hint=None):
        u,v = finite(uv,2)
        r,rp,_ = self.radius_at(v)
        theta = TAU*u+self.p["seam_angle"]
        co,si,h = math.cos(theta),math.sin(theta),self.p["height"]
        length = math.hypot(h,rp)
        canonical = [u % 1,v]
        a,b = canonical
        tri,bary = (0,[1-a,a-b,b]) if a >= b else (1,[1-b,a,b-a])
        return dict(uv=[u,v],canonical_uv=canonical,face_id=tri,triangle_id=tri,barycentric=bary,
            correspondence_basis="ANALYTIC_CHART_TRIANGLE",
            surface_position=[r*co,r*si,self.p["z_min"]+h*v],
            normal=[h*co/length,h*si/length,-rp/length],
            dp_du=[-TAU*r*si,TAU*r*co,0],dp_dv=[rp*co,rp*si,h])

    def inverse(self, position, uv_hint=None, triangle_hint=None, tolerance=1e-7):
        x,y,z = finite(position,3)
        if uv_hint is not None: finite(uv_hint,2)
        u = ((math.atan2(y,x)-self.p["seam_angle"])/TAU) % 1
        if abs(u-1) < 1e-12: u = 0
        if uv_hint is not None: u += round(uv_hint[0]-u)
        sample = self.forward([u,(z-self.p["z_min"])/self.p["height"]])
        if norm(sub(sample["surface_position"],position)) > tolerance:
            raise SurfaceError("OFF_SURFACE", "Not on RevolutionVase; no projection or arbitrary vessel fitting")
        return sample

    def offset_differential(self, sample, offset):
        u,v = sample["uv"]
        r,rp,rpp = self.radius_at(v)
        h = self.p["height"]
        length = math.hypot(h,rp)
        theta = TAU*u+self.p["seam_angle"]
        co,si = math.cos(theta),math.sin(theta)
        radial_scale = 1+offset*h/(length*r)
        meridian_scale = 1-offset*h*rpp/(length**3)
        if min(radial_scale,meridian_scale) <= 1e-10:
            raise SurfaceError("OFFSET_SINGULARITY", "Vase normal offset folds or crosses axis")
        return mul(sample["dp_du"],radial_scale),mul(sample["dp_dv"],meridian_scale)

    def seams(self):
        return [dict(kind="PERIODIC_U",sides=[[[0,0],[0,1]],[[1,0],[1,1]]],period=1,
                     seam_angle=self.p["seam_angle"],inverse_policy="canonical [0,1); uv_hint preserves winding")]

    def seed_uvs(self):
        heights = sorted({v for v,r in self.points} | {(a[0]+b[0])/2 for a,b in zip(self.points,self.points[1:])})
        return [[u,v] for u in (0,.25,.5,.75,1) for v in heights]

    def spacing_bounds(self, a, b, offset):
        """Conservative local spacing bound, not a global geodesic solver."""
        pa,pb = self.forward(a),self.forward(b)
        chord = norm(sub(add(pb["surface_position"],mul(pb["normal"],offset)),
                         add(pa["surface_position"],mul(pa["normal"],offset))))
        du = abs((b[0]-a[0]+.5) % 1-.5)
        v0,v1 = sorted((a[1],b[1]))
        # Exact cylinder distance when all radii agree (straight_vase).
        if all(r == self.points[0][1] for v,r in self.points):
            d = math.hypot(TAU*(self.points[0][1]+offset)*du,self.p["height"]*(v1-v0))
            return d,d,"VASE_STRAIGHT_INTRINSIC"
        rmax,drmax,d2max = 0.,0.,0.
        for p,q in zip(self.points,self.points[1:]):
            lo,hi = max(v0,p[0]),min(v1,q[0])
            if lo > hi: continue
            candidates = [lo,hi]
            mid = (p[0]+q[0])/2
            if lo <= mid <= hi: candidates.append(mid)
            # Derivatives at knots evaluated from this segment, not adjacent one.
            length,delta = q[0]-p[0],q[1]-p[1]
            for v in candidates:
                t = (v-p[0])/length
                rmax = max(rmax,p[1]+delta*(3*t*t-2*t*t*t))
                drmax = max(drmax,abs(delta*6*t*(1-t)/length))
                d2max = max(d2max,abs(delta*(6-12*t)/(length*length)))
        h = self.p["height"]
        circumference_bound = TAU*(rmax+abs(offset))
        vertical_bound = math.hypot(h,drmax)*(1+abs(offset)*d2max/(h*h))
        upper = math.hypot(circumference_bound*du,vertical_bound*(v1-v0))
        return chord,max(chord,upper),"VASE_LOCAL_SPACING_BOUNDS_NOT_GLOBAL_GEODESIC"
