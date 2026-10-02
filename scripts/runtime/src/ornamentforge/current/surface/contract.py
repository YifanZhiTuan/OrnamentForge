"""Unique SurfaceMapV1 serialized correspondence contract and semantic validation."""
from copy import deepcopy
from dataclasses import dataclass
import json
from jsonschema import Draft202012Validator
from ornamentforge.canonical_curve import canonical_bytes, content_hash
from ..planar.contract import obj, array, S, N, POINT, POINT3
from .math3d import SurfaceError, unit, differential_metrics, norm, sub

HASH = {"type":"string","pattern":"^[a-f0-9]{64}$"}
DISTORTION = obj(local_scale=POINT, principal_stretches=POINT, area_scale=N,
                 angle_distortion=N, area_distortion=N, stretch_distortion=N,
                 orientation={"enum":[-1,1]}, orientation_error=N)
SAMPLE = obj(id=S, uv=POINT, canonical_uv=POINT,
             face_id={"type":"integer","minimum":0}, triangle_id={"type":"integer","minimum":0},
             barycentric=POINT3, correspondence_basis={"enum":["ANALYTIC_CHART_TRIANGLE","MESH_LOOP_TRIANGLE"]},
             surface_position=POINT3, normal=POINT3, dp_du=POINT3, dp_dv=POINT3,
             tangent_u=POINT3, tangent_v=POINT3, distortion=DISTORTION)
SCHEMA = {"$schema":"https://json-schema.org/draft/2020-12/schema", "title":"SurfaceMapV1", **obj(
    schema_version={"const":"SurfaceMapV1"},host_type={"enum":["PLANE","CYLINDER","CONE","REVOLUTION_VASE","UV_MESH"]},
    host_mesh_hash=HASH, hash_basis={"enum":["ANALYTIC_DESCRIPTOR","WORLD_MESH_AND_UV_LOOPS"]},
    host_geometry={"type":"object"}, chart_id=S,
    domain_bounds={**array(N),"minItems":4,"maxItems":4},
    domain_coordinates={"enum":["PLANE_XY","NORMALIZED_CYLINDER_UV","CONE_SECTOR_XY","NORMALIZED_VASE_UV","EXISTING_UV"]},
    seam_information=array({"type":"object"}),
    orientation={"const":"CROSS_DP_DU_DP_DV_ALIGNS_NORMAL"},
    correspondence={**array(SAMPLE),"minItems":1},
    limitations=array(S))}


def restore_engine(data):
    if data["host_type"] == "REVOLUTION_VASE":
        from .revolution_vase import RevolutionVaseHost
        return RevolutionVaseHost.restore(data["host_geometry"])
    if data["host_type"] == "UV_MESH":
        from .uv_mesh import UVHost
        return UVHost(data["host_geometry"], data["chart_id"])
    from .analytic import AnalyticHost
    return AnalyticHost.restore(data["host_type"],data["host_geometry"])


def complete_sample(raw, identifier):
    return dict(id=identifier,**raw,tangent_u=unit(raw["dp_du"]),tangent_v=unit(raw["dp_dv"]),
                distortion=differential_metrics(raw["dp_du"],raw["dp_dv"],raw["normal"]))


def close(a,b):
    if isinstance(a,(int,float)) and not isinstance(a,bool) and isinstance(b,(int,float)):
        return abs(a-b) <= 1e-8*max(1,abs(a),abs(b))
    if isinstance(a,list) and isinstance(b,list):
        return len(a)==len(b) and all(close(x,y) for x,y in zip(a,b))
    if isinstance(a,dict) and isinstance(b,dict):
        return a.keys()==b.keys() and all(close(a[k],b[k]) for k in a)
    return a==b


def validate_map(data):
    canonical_bytes(data)
    Draft202012Validator(SCHEMA).validate(data)
    if content_hash({"host_type":data["host_type"],"geometry":data["host_geometry"]}) != data["host_mesh_hash"]:
        raise SurfaceError("HOST_HASH_MISMATCH", "Host mesh/UV/parameters changed")
    engine = restore_engine(data)
    is_mesh = data["host_type"] == "UV_MESH"
    basis = "WORLD_MESH_AND_UV_LOOPS" if is_mesh else "ANALYTIC_DESCRIPTOR"
    coords = {"PLANE":"PLANE_XY","CYLINDER":"NORMALIZED_CYLINDER_UV","CONE":"CONE_SECTOR_XY","REVOLUTION_VASE":"NORMALIZED_VASE_UV","UV_MESH":"EXISTING_UV"}
    if data["hash_basis"] != basis or data["domain_coordinates"] != coords[data["host_type"]]:
        raise SurfaceError("HOST_METADATA", "Wrong coordinate/hash convention")
    if not is_mesh and (data["chart_id"] != "analytic_0" or not close(engine.p,data["host_geometry"])):
        raise SurfaceError("HOST_METADATA", "Analytic descriptor or chart mismatch")
    if not close(engine.bounds,data["domain_bounds"]) or not close(engine.seams(),data["seam_information"]):
        raise SurfaceError("HOST_METADATA", "Domain/seam metadata mismatch")
    ids = set()
    for s in data["correspondence"]:
        if s["id"] in ids:
            raise SurfaceError("SAMPLE_ID", "Duplicate sample ID")
        ids.add(s["id"])
        expected = complete_sample(engine.forward(s["uv"],s["triangle_id"]),s["id"])
        if not close(expected,s):
            raise SurfaceError("CORRESPONDENCE_MISMATCH", f"Invalid correspondence/frame: {s['id']}")


@dataclass(frozen=True)
class SurfaceMapV1:
    _json: str

    def __post_init__(self):
        validate_map(json.loads(self._json))

    @classmethod
    def from_dict(cls, data):
        return cls(canonical_bytes(data).decode("utf-8"))

    def to_dict(self): return json.loads(self._json)

    @property
    def content_hash(self): return content_hash(self.to_dict())

    @staticmethod
    def schema(): return deepcopy(SCHEMA)
