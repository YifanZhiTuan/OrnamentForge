"""HostAdapter -> immutable SurfaceMapV1 -> bidirectional SurfaceMapper."""
from .analytic import AnalyticHost
from .uv_mesh import UVHost
from .contract import SurfaceMapV1, complete_sample, restore_engine
from .math3d import SurfaceError, finite
from ornamentforge.canonical_curve import content_hash


class HostAdapter:
    @staticmethod
    def create(host_type, *, parameters=None, host_mesh=None, chart_id=None):
        if host_type == "UV_MESH":
            if parameters:
                raise SurfaceError("HOST_PARAMETERS", "UV_MESH takes existing host_mesh, not analytic parameters")
            engine = UVHost(host_mesh,chart_id)
            geometry, chart = engine.snapshot,engine.chart_id
            seeds = engine.seed_uvs()
        else:
            if host_mesh is not None or chart_id not in (None,"analytic_0"):
                raise SurfaceError("HOST_PARAMETERS", "Analytic hosts do not accept a mesh/chart override")
            if host_type == "REVOLUTION_VASE":
                from .revolution_vase import RevolutionVaseHost
                engine = RevolutionVaseHost(parameters or {})
            else:
                engine = AnalyticHost(host_type, parameters or {})
            geometry, chart = engine.p,"analytic_0"
            seeds = [(None,uv) for uv in engine.seed_uvs()]
        samples = [complete_sample(engine.forward(uv,tri),f"host_{i}") for i,(tri,uv) in enumerate(seeds)]
        data = dict(schema_version="SurfaceMapV1",host_type=host_type,host_mesh_hash=content_hash({"host_type":host_type,"geometry":geometry}),
            hash_basis="WORLD_MESH_AND_UV_LOOPS" if host_type == "UV_MESH" else "ANALYTIC_DESCRIPTOR",
            host_geometry=geometry,chart_id=chart,domain_bounds=engine.bounds,
            domain_coordinates={"PLANE":"PLANE_XY","CYLINDER":"NORMALIZED_CYLINDER_UV","CONE":"CONE_SECTOR_XY","REVOLUTION_VASE":"NORMALIZED_VASE_UV","UV_MESH":"EXISTING_UV"}[host_type],
            seam_information=engine.seams(),orientation="CROSS_DP_DU_DP_DV_ALIGNS_NORMAL",correspondence=samples,
            limitations=["No automatic unwrap or chart generation.",
                "Analytic face/barycentric coordinates identify parameter-domain triangles, not tessellated 3D faces." if host_type != "UV_MESH"
                else "Existing selected chart only; piecewise-flat face normals; UVs are not modified."])
        return SurfaceMapV1.from_dict(data)

    @staticmethod
    def from_blender(obj, *, uv_layer=None, chart_id=None):
        from .blender_uv import snapshot_blender_mesh
        try:
            mesh = snapshot_blender_mesh(obj,uv_layer)
        except ValueError as exc:
            raise SurfaceError("BLENDER_MESH_INPUT",str(exc),"NOT_SUPPORTED") from exc
        return HostAdapter.create("UV_MESH",host_mesh=mesh,chart_id=chart_id)


class SurfaceMapper:
    def __init__(self, surface_map: SurfaceMapV1):
        if not isinstance(surface_map,SurfaceMapV1):
            raise SurfaceError("SURFACE_CONTRACT", "Expected validated SurfaceMapV1")
        self.surface_map = surface_map
        self.data = surface_map.to_dict()
        self.engine = restore_engine(self.data)

    def to_surface(self, uv, *, triangle_hint=None):
        return complete_sample(self.engine.forward(uv,triangle_hint),"query")

    def to_domain(self, position, *, uv_hint=None, triangle_hint=None, tolerance=1e-7):
        finite([tolerance],1)
        if tolerance <= 0:
            raise SurfaceError("INVERSE_TOLERANCE", "Positive tolerance required")
        return complete_sample(self.engine.inverse(position,uv_hint,triangle_hint,tolerance),"query")

    def signed_offset(self, uv, *, height=0, depth=0):
        from .math3d import add, mul
        finite([height,depth],2)
        if height < 0 or depth < 0 or (height and depth):
            raise SurfaceError("CRAFT_OFFSET", "Specify nonnegative height OR depth, not both")
        sample = self.to_surface(uv)
        self.offset_differential(sample,height-depth)
        return add(sample["surface_position"],mul(sample["normal"],height-depth))

    def offset_differential(self, sample, offset):
        """d(P+hN)/du,dv for constant h; mesh normals are face-constant."""
        import math
        from .math3d import add, mul
        du,dv = sample["dp_du"],sample["dp_dv"]
        kind = self.data["host_type"]
        if kind == "REVOLUTION_VASE":
            return self.engine.offset_differential(sample,offset)
        if kind == "CYLINDER":
            factor = 1+offset/self.engine.p["radius"]
            if factor <= 1e-12:
                raise SurfaceError("OFFSET_SINGULARITY", "Offset reaches or crosses cylinder axis")
            du = mul(du,factor)
        elif kind == "CONE":
            u,v = sample["uv"]
            rho = math.hypot(u,v)
            factor = 1+offset*self.engine.c/(self.engine.k*rho)
            if factor <= 1e-12:
                raise SurfaceError("OFFSET_SINGULARITY", "Offset reaches or crosses cone axis")
            theta = (math.atan2(v,u) % (2*math.pi))/self.engine.k+self.engine.p["seam_angle"]
            angular = [-math.sin(theta),math.cos(theta),0]
            dn_du = mul(angular,-self.engine.c*v/(self.engine.k*rho*rho))
            dn_dv = mul(angular,self.engine.c*u/(self.engine.k*rho*rho))
            du,dv = add(du,mul(dn_du,offset)),add(dv,mul(dn_dv,offset))
        return du,dv
