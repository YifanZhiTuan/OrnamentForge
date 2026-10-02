"""The single serialized planar contract. No Blender or generated assets required."""
from copy import deepcopy
from dataclasses import dataclass
import json

from jsonschema import Draft202012Validator
from ornamentforge.canonical_curve import canonical_bytes, validate_curve


def obj(**properties):
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


def array(items):
    return {"type": "array", "items": items}


S = {"type": "string", "minLength": 1}
N = {"type": "number"}
ID = S
POINT = {**array(N), "minItems": 2, "maxItems": 2}
POINT3 = {**array(N), "minItems": 3, "maxItems": 3}
CURVE = obj(
    curve_version={"const": "1.0"}, representation={"const": "bezier_curve"},
    dimensions={"const": "3D"}, resolution_u={"type": "integer", "minimum": 1, "maximum": 64},
    twist_mode={"const": "Z_UP"}, cyclic={"type": "boolean"},
    points={**array(obj(co=POINT3, left=POINT3, right=POINT3,
                       left_type={"const": "FREE"}, right_type={"const": "FREE"},
                       radius={"type": "number", "exclusiveMinimum": 0}, tilt=N)),
            "minItems": 2, "maxItems": 4096})
GEOMETRY = {"oneOf": [
    obj(id=ID, representation={"const": "polyline"}, closed={"const": True},
        data=obj(points={**array(POINT), "minItems": 3})),
    obj(id=ID, representation={"const": "polyline"}, closed={"const": False},
        data=obj(points={**array(POINT), "minItems": 2})),
    obj(id=ID, representation={"const": "bezier_curve"}, closed={"type": "boolean"}, data=CURVE),
]}
SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "PlanarMasterV1",
    **obj(
        schema_version={"const": "PlanarMasterV1"},
        route={"enum": ["FIDELITY_RECONSTRUCTION"]},
        domain=obj(bounds={**array(N), "minItems": 4, "maxItems": 4},
                   coordinates={"const": "XY_RIGHT_UP"}),
        physical_scale=obj(unit={"const": "design_unit"},
                           millimeters_per_unit={"type": ["number", "null"], "exclusiveMinimum": 0}),
        closed_regions=array(obj(id=ID, geometry_ref=ID, kind={"enum": ["support", "fill", "outline"]},
                                 palette_ref={"type": ["string", "null"]},
                                 stroke_width={"type": ["number", "null"], "exclusiveMinimum": 0})),
        holes=array(obj(id=ID, parent_region=ID, geometry_ref=ID)),
        open_stroke_graph=obj(state={"enum": ["EXTRACTED", "NOT_EXTRACTED"]},
                              nodes=array(obj(id=ID, position=POINT)),
                              edges=array(obj(id=ID, start=ID, end=ID, geometry_ref=ID,
                                              width={"type": "number", "exclusiveMinimum": 0}))),
        semantic_roles=array(obj(entity_ref=ID, role=S, basis={"enum": ["measured", "declared", "inferred"]})),
        z_order=array(obj(entity_ref=ID, layer={"type": "integer"}, basis={"enum": ["declared", "inferred"]})),
        palette=array(obj(id=ID, rgb={**array({"type": "integer", "minimum": 0, "maximum": 255}),
                                      "minItems": 3, "maxItems": 3})),
        repeat_groups=array(obj(id=ID, template_region=ID, transform_refs=array(ID))),
        repeat_transforms=array(obj(id=ID, matrix={**array(N), "minItems": 6, "maxItems": 6})),
        source_correspondence=array(obj(entity_ref=ID, source_ref=ID, locator=S)),
        provenance=array(obj(id=ID, kind=S, source=S, sha256={"type": "string", "pattern": "^[0-9a-f]{64}$"},
                             details={"type": "object"})),
        editable_geometry_references=array(GEOMETRY),
        qa_state=obj(status={"const": "REVIEW_REQUIRED"}, contract={"const": "PASS"},
                     limitations=array(S)),
        source_hash={"type": "string", "pattern": "^[0-9a-f]{64}$"},
    ),
}


def validate_master(data):
    # JSON Schema's number type admits NaN in Python; canonical serialization does not.
    canonical_bytes(data)
    Draft202012Validator(SCHEMA).validate(data)
    tables = {}
    for key in ("closed_regions", "holes", "palette", "repeat_groups", "repeat_transforms",
                "provenance", "editable_geometry_references"):
        rows = data[key]
        tables[key] = {r["id"]: r for r in rows}
        if len(tables[key]) != len(rows):
            raise ValueError(f"Duplicate IDs in {key}")
    graph = data["open_stroke_graph"]
    for key in ("nodes", "edges"):
        tables[key] = {r["id"]: r for r in graph[key]}
        if len(tables[key]) != len(graph[key]):
            raise ValueError(f"Duplicate graph {key}")
    all_ids = [i for table in tables.values() for i in table]
    if len(set(all_ids)) != len(all_ids):
        raise ValueError("IDs must be globally unique")
    entities = set().union(*(set(tables[k]) for k in ("closed_regions", "holes", "edges", "repeat_groups")))
    def require(value, table):
        if value not in table:
            raise ValueError(f"Dangling reference: {value}")
    geometries = tables["editable_geometry_references"]
    for g in geometries.values():
        if g["representation"] == "bezier_curve":
            curve = validate_curve(g["data"])
            if curve["cyclic"] != g["closed"]:
                raise ValueError("Bezier closure mismatch")
            if any(p[k][2] != 0 for p in curve["points"] for k in ("co", "left", "right")):
                raise ValueError("Planar geometry must have zero Z")
        else:
            points = g["data"].get("points")
            if set(g["data"]) != {"points"} or not isinstance(points, list) or len(points) < (3 if g["closed"] else 2):
                raise ValueError("Invalid polyline")
            for point in points:
                Draft202012Validator(POINT).validate(point)
            if g["closed"] and abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points, points[1:]+points[:1]))) < 1e-12:
                raise ValueError("Degenerate closed region")
    for row in [*data["closed_regions"], *data["holes"], *graph["edges"]]:
        require(row["geometry_ref"], geometries)
        if geometries[row["geometry_ref"]]["closed"] != (row not in graph["edges"]):
            raise ValueError("Entity/geometry closure mismatch")
    for r in data["closed_regions"]:
        if (r["kind"] == "outline") != (r["stroke_width"] is not None):
            raise ValueError("Only outline regions require stroke_width")
        if r["palette_ref"] is not None:
            require(r["palette_ref"], tables["palette"])
    for h in data["holes"]:
        require(h["parent_region"], tables["closed_regions"])
    for edge in graph["edges"]:
        require(edge["start"], tables["nodes"])
        require(edge["end"], tables["nodes"])
        geometry = geometries[edge["geometry_ref"]]
        points = geometry["data"]["points"]
        ends = [p["co"][:2] for p in (points[0],points[-1])] if geometry["representation"] == "bezier_curve" else [points[0],points[-1]]
        if ends != [tables["nodes"][edge[k]]["position"] for k in ("start", "end")]:
            raise ValueError("Graph endpoints disagree with geometry")
    for t in data["repeat_transforms"]:
        a,b,_,c,d,_ = t["matrix"]
        if abs(a*d-b*c) < 1e-12:
            raise ValueError("Singular repeat transform")
    for group in data["repeat_groups"]:
        require(group["template_region"], tables["closed_regions"])
        for ref in group["transform_refs"]:
            require(ref, tables["repeat_transforms"])
    for key in ("semantic_roles", "z_order", "source_correspondence"):
        refs = [r["entity_ref"] for r in data[key]]
        if set(refs) != entities or len(refs) != len(entities):
            raise ValueError(f"{key} must cover every entity exactly once")
    for row in data["source_correspondence"]:
        require(row["source_ref"], tables["provenance"])
    x0,y0,x1,y1 = data["domain"]["bounds"]
    if x0 >= x1 or y0 >= y1:
        raise ValueError("Invalid domain bounds")
    if not entities or not data["provenance"]:
        raise ValueError("Empty master")
    if graph["state"] == "NOT_EXTRACTED" and (graph["nodes"] or graph["edges"]):
        raise ValueError("NOT_EXTRACTED graph must be empty")


@dataclass(frozen=True)
class PlanarMasterV1:
    """Validated immutable JSON snapshot; to_dict returns an independent copy."""
    _json: str

    def __post_init__(self):
        validate_master(json.loads(self._json))

    @classmethod
    def from_dict(cls, data):
        validate_master(data)
        return cls(canonical_bytes(data).decode("utf-8"))

    def to_dict(self):
        return json.loads(self._json)

    @staticmethod
    def schema():
        return deepcopy(SCHEMA)
