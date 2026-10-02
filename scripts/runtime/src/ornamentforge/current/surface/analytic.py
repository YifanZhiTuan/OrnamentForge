"""Exact plane, cylinder and DEVELOPED cone charts. No mesh projection or unwrap."""
import math
from .math3d import SurfaceError, finite, add, mul, sub, norm, unit

TAU = 2*math.pi


class AnalyticHost:
    def __init__(self, host_type, parameters):
        self.kind = host_type
        defaults = {
            "PLANE": dict(bounds=[0,0,1,1], z=0),
            "CYLINDER": dict(radius=1, height=1, z_min=0, seam_angle=0),
            "CONE": dict(radius=1, height=1, z_min=0, seam_angle=0, min_slant=1e-6),
        }
        if host_type not in defaults:
            raise SurfaceError("HOST_NOT_SUPPORTED", host_type, "NOT_SUPPORTED")
        if not isinstance(parameters,dict) or set(parameters)-set(defaults[host_type]):
            raise SurfaceError("HOST_PARAMETERS", "Unknown host parameters")
        self.p = defaults[host_type] | parameters
        finite([v for k,v in self.p.items() if k != "bounds"])
        if host_type == "PLANE":
            self.bounds = finite(self.p["bounds"],4)
            if self.bounds[0] >= self.bounds[2] or self.bounds[1] >= self.bounds[3]:
                raise SurfaceError("DOMAIN_BOUNDS", "Empty plane domain")
        else:
            r,h = self.p["radius"],self.p["height"]
            if r <= 0 or h <= 0:
                raise SurfaceError("HOST_PARAMETERS", "Positive radius and height required")
            self.bounds = [0,0,1,1]
            if host_type == "CONE":
                self.slant = math.hypot(r,h)
                self.k, self.c = r/self.slant,h/self.slant
                self.sector = TAU*self.k
                if not 0 < self.p["min_slant"] < self.slant:
                    raise SurfaceError("CONE_APEX", "min_slant must exclude apex and be below slant radius")
                angles = [0,self.sector]+[i*math.pi/2 for i in range(1,4) if i*math.pi/2 < self.sector]
                pts = [[rho*math.cos(a),rho*math.sin(a)] for rho in (self.p["min_slant"],self.slant) for a in angles]
                self.bounds = [min(p[0] for p in pts), min(p[1] for p in pts),max(p[0] for p in pts),max(p[1] for p in pts)]
                self.p.update(slant_radius=self.slant,cone_angle=math.atan2(r,h),sector_angle=self.sector)

    @classmethod
    def restore(cls, kind, parameters):
        return cls(kind,{k:v for k,v in parameters.items() if k not in ("slant_radius","cone_angle","sector_angle")})

    def forward(self, uv, triangle_hint=None):
        u,v = finite(uv,2)
        if self.kind == "PLANE":
            x0,y0,x1,y1 = self.bounds
            if not x0-1e-9 <= u <= x1+1e-9 or not y0-1e-9 <= v <= y1+1e-9:
                raise SurfaceError("OUTSIDE_DOMAIN", "Point outside plane")
            pos,du,dv,n = [u,v,self.p["z"]],[1,0,0],[0,1,0],[0,0,1]
            canonical = [u,v]
        elif self.kind == "CYLINDER":
            if not -1e-9 <= v <= 1+1e-9:
                raise SurfaceError("OUTSIDE_DOMAIN", "Cylinder normalized height outside [0,1]")
            theta = TAU*u+self.p["seam_angle"]
            co,si,r,h = math.cos(theta),math.sin(theta),self.p["radius"],self.p["height"]
            pos = [r*co,r*si,self.p["z_min"]+h*v]
            du,dv,n = [-TAU*r*si,TAU*r*co,0],[0,0,h],[co,si,0]
            canonical = [u % 1,v]
        else:
            rho = math.hypot(u,v)
            phi = math.atan2(v,u) % TAU
            if abs(phi-TAU) < 1e-10:
                phi = 0
            if not self.p["min_slant"]-1e-10 <= rho <= self.slant+1e-9 or phi > self.sector+1e-9:
                raise SurfaceError("OUTSIDE_DOMAIN", "Point outside cone development or at excluded apex")
            theta = phi/self.k+self.p["seam_angle"]
            co,si,cp,sp = math.cos(theta),math.sin(theta),math.cos(phi),math.sin(phi)
            pos = [rho*self.k*co,rho*self.k*si,self.p["z_min"]+self.p["height"]-rho*self.c]
            radial = [self.k*co,self.k*si,-self.c]
            angular = [-si,co,0]
            du,dv = sub(mul(radial,cp),mul(angular,sp)),add(mul(radial,sp),mul(angular,cp))
            n = [self.c*co,self.c*si,self.k]
            canonical = [u,v]
        # Analytic chart triangles are parameter-space patches, NOT flat 3D faces.
        x0,y0,x1,y1 = self.bounds
        a,b = (canonical[0]-x0)/(x1-x0),(canonical[1]-y0)/(y1-y0)
        tri,bary = (0,[1-a,a-b,b]) if a >= b else (1,[1-b,a,b-a])
        return dict(uv=[u,v], canonical_uv=canonical, face_id=tri, triangle_id=tri,
                    barycentric=bary, correspondence_basis="ANALYTIC_CHART_TRIANGLE",
                    surface_position=pos, normal=n, dp_du=du, dp_dv=dv)

    def inverse(self, position, uv_hint=None, triangle_hint=None, tolerance=1e-7):
        x,y,z = finite(position,3)
        if uv_hint is not None:
            finite(uv_hint,2)
        if self.kind == "PLANE":
            uv = [x,y]
        else:
            theta = (math.atan2(y,x)-self.p["seam_angle"]) % TAU
            if abs(theta-TAU) < 1e-12:
                theta = 0
            if self.kind == "CYLINDER":
                u = theta/TAU
                if uv_hint is not None:
                    u += round(uv_hint[0]-u)
                uv = [u,(z-self.p["z_min"])/self.p["height"]]
            else:
                rho = (self.p["z_min"]+self.p["height"]-z)/self.c
                phi = theta*self.k
                uv = [rho*math.cos(phi),rho*math.sin(phi)]
                if uv_hint is not None and min(theta,TAU-theta) < 1e-8:
                    candidates = [[rho,0],[rho*math.cos(self.sector),rho*math.sin(self.sector)]]
                    uv = min(candidates,key=lambda q:norm(sub(q,uv_hint)))
        result = self.forward(uv)
        if norm(sub(result["surface_position"],position)) > tolerance:
            raise SurfaceError("OFF_SURFACE", "Inverse input is not on host; no nearest-point projection")
        return result

    def seams(self):
        if self.kind == "PLANE":
            return []
        if self.kind == "CYLINDER":
            return [dict(kind="PERIODIC_U", sides=[[[0,0],[0,1]],[[1,0],[1,1]]],
                         period=1, seam_angle=self.p["seam_angle"], inverse_policy="canonical [0,1); uv_hint preserves winding")]
        lo,hi = self.p["min_slant"],self.slant
        return [dict(kind="SECTOR_RADIAL", sides=[[[lo,0],[hi,0]],
                    [[lo*math.cos(self.sector),lo*math.sin(self.sector)],[hi*math.cos(self.sector),hi*math.sin(self.sector)]]],
                    sector_angle=self.sector,seam_angle=self.p["seam_angle"],inverse_policy="uv_hint chooses radial seam side")]

    def seed_uvs(self):
        if self.kind == "CONE":
            return [[rho*math.cos(phi),rho*math.sin(phi)] for rho in (self.slant*.25,self.slant*.75,self.slant)
                    if rho >= self.p["min_slant"] for phi in (0,self.sector*.25,self.sector*.5,self.sector*.75,self.sector)]
        x0,y0,x1,y1 = self.bounds
        return [[x0+(x1-x0)*a,y0+(y1-y0)*b] for a in (0,.25,.5,.75,1) for b in (0,.5,1)]
