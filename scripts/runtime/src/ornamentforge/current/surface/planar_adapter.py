"""Formal PlanarMasterV1 -> SurfaceMappedMasterV1 adapter with mandatory QA.

Source curves remain editable in the embedded original master. Mapped polylines are
adaptive samples, not a false claim that nonlinear maps preserve cubic Béziers.
"""
from dataclasses import dataclass
import json
from ornamentforge.canonical_curve import canonical_bytes, content_hash
from ..planar.contract import PlanarMasterV1
from .contract import SurfaceMapV1, close
from .mapper import SurfaceMapper
from .qa import SurfaceTransferQA, geodesic_bounds
from .math3d import (SurfaceError, finite, affine, add, sub, mul, norm, unit,
                     cross, differential_metrics)


def fit_domain_transform(master, surface):
    """Explicit opt-in rectangle fit. Cone/UV chart cutouts may still HOLD."""
    x0,y0,x1,y1 = master.to_dict()["domain"]["bounds"]
    u0,v0,u1,v1 = surface.to_dict()["domain_bounds"]
    sx,sy = (u1-u0)/(x1-x0),(v1-v0)/(y1-y0)
    return [sx,0,u0-sx*x0,0,sy,v0-sy*y0]


@dataclass(frozen=True)
class SurfaceMappedMasterV1:
    _json: str

    def __post_init__(self):
        d = json.loads(self._json)
        canonical_bytes(d)
        required = {"schema_version","source_master","source_master_hash","surface_map_hash",
                    "domain_transform","signed_offset","paths","qa_status"}
        if set(d) != required or d["schema_version"] != "SurfaceMappedMasterV1" or d["qa_status"] != "PASS":
            raise SurfaceError("MAPPED_CONTRACT", "Invalid mapped master fields/state")
        PlanarMasterV1.from_dict(d["source_master"])
        if content_hash(d["source_master"]) != d["source_master_hash"]:
            raise SurfaceError("MAPPED_HASH", "Source master changed")
        finite(d["domain_transform"],6)
        a,b,_,c,e,_ = d["domain_transform"]
        if abs(a*e-b*c) < 1e-14:
            raise SurfaceError("DOMAIN_TRANSFORM", "Singular domain transform")
        finite([d["signed_offset"]])
        if not d["paths"] or len({p["id"] for p in d["paths"]}) != len(d["paths"]):
            raise SurfaceError("MAPPED_PATHS", "Empty or duplicate paths")
        source = d["source_master"]
        entities = {e["id"]:e for e in [*source["closed_regions"],*source["holes"],*source["open_stroke_graph"]["edges"]]}
        roles = {e["entity_ref"]:e for e in source["semantic_roles"]}
        orders = {e["entity_ref"]:e for e in source["z_order"]}
        groups = {g["id"]:g for g in source["repeat_groups"]}
        identifiers = {p["id"] for p in d["paths"]}
        path_fields = {"id","source_entity","geometry_ref","parent_path","repeat_group","repeat_transform",
                       "closed","semantic_role","z_order","palette_ref","repeat_group_role","sample_refs",
                       "design_positions","offset_positions","frames"}
        for path in d["paths"]:
            if set(path) != path_fields or path["source_entity"] not in entities:
                raise SurfaceError("MAPPED_PATHS", "Invalid path schema/source entity")
            entity = entities[path["source_entity"]]
            if (path["geometry_ref"] != entity["geometry_ref"] or path["semantic_role"] != roles[entity["id"]]
                    or path["z_order"] != orders[entity["id"]] or path["palette_ref"] != entity.get("palette_ref")):
                raise SurfaceError("MAPPED_METADATA", "Source geometry/roles/order/palette must be preserved")
            if path["parent_path"] is not None and path["parent_path"] not in identifiers:
                raise SurfaceError("MAPPED_PARENT", "Missing hole parent path")
            if path["repeat_group"] is not None:
                group = groups.get(path["repeat_group"])
                if group is None or path["repeat_transform"] not in group["transform_refs"] or path["repeat_group_role"] != roles[group["id"]]:
                    raise SurfaceError("MAPPED_REPEAT", "Invalid repeated instance")
            n = len(path["sample_refs"])
            if n < 2 or any(len(path[k]) != n for k in ("design_positions","offset_positions","frames")):
                raise SurfaceError("MAPPED_PATHS", "Inconsistent mapped sample arrays")
            for p in path["offset_positions"]:
                finite(p,3)
            for p in path["design_positions"]:
                finite(p,2)
            for frame in path["frames"]:
                if set(frame) != {"tangent_x","tangent_y","motif_tangent_x","motif_tangent_y","normal"}:
                    raise SurfaceError("MAPPED_FRAME", "Incomplete tangent frame")
                for vector in frame.values():
                    if abs(norm(finite(vector,3))-1) > 1e-7:
                        raise SurfaceError("MAPPED_FRAME", "Non-unit frame direction")

    @classmethod
    def from_dict(cls, data): return cls(canonical_bytes(data).decode("utf-8"))

    def to_dict(self): return json.loads(self._json)

    def to_planar(self, surface, surface_position, *, uv_hint=None, triangle_hint=None):
        """Host/base point -> original design domain; offset points are not projected."""
        if surface.content_hash != self.to_dict()["surface_map_hash"]:
            raise SurfaceError("MAPPED_HASH", "Surface map changed")
        sample = SurfaceMapper(surface).to_domain(surface_position,uv_hint=uv_hint,triangle_hint=triangle_hint)
        a,b,x,c,d,y = self.to_dict()["domain_transform"]
        det = a*d-b*c
        if abs(det) < 1e-14:
            raise SurfaceError("DOMAIN_TRANSFORM", "Singular domain transform")
        u,v = sample["uv"][0]-x,sample["uv"][1]-y
        return dict(design_position=[(d*u-b*v)/det,(-c*u+a*v)/det],correspondence=sample)

    def verify_surface_map(self, surface):
        if surface.content_hash != self.to_dict()["surface_map_hash"]:
            raise SurfaceError("MAPPED_HASH", "Surface correspondence has changed")
        samples = {s["id"]:s for s in surface.to_dict()["correspondence"]}
        data = self.to_dict()
        mapper = SurfaceMapper(surface)
        a,b,_,c,d,_ = data["domain_transform"]
        transforms = {t["id"]:t["matrix"] for t in data["source_master"]["repeat_transforms"]}
        for path in data["paths"]:
            pa,pb,_,pc,pd,_ = transforms.get(path["repeat_transform"],[1,0,0,0,1,0])
            for ref,point,design,frame in zip(path["sample_refs"],path["offset_positions"],path["design_positions"],path["frames"]):
                if ref not in samples:
                    raise SurfaceError("MAPPED_REFERENCE", "Missing surface sample")
                s = samples[ref]
                expected = add(s["surface_position"],mul(s["normal"],data["signed_offset"]))
                if norm(sub(point,expected)) > 1e-7 or norm(sub(affine(design,data["domain_transform"]),s["uv"])) > 1e-7:
                    raise SurfaceError("MAPPED_CORRESPONDENCE", "Mapped positions disagree with correspondence")
                du,dv = mapper.offset_differential(s,data["signed_offset"])
                dx,dy = add(mul(du,a),mul(dv,c)),add(mul(du,b),mul(dv,d))
                expected_frame = dict(tangent_x=unit(dx),tangent_y=unit(dy),normal=s["normal"],
                    motif_tangent_x=unit(add(mul(dx,pa),mul(dy,pc))),motif_tangent_y=unit(add(mul(dx,pb),mul(dy,pd))))
                if not close(frame,expected_frame):
                    raise SurfaceError("MAPPED_FRAME", "Tangent frame disagrees with surface/instance differential")
        return True


def _segments(geometry, transform):
    points = geometry["data"]["points"]
    if geometry["representation"] == "polyline":
        pairs = list(zip(points,points[1:]))
        if geometry["closed"]:
            pairs.append((points[-1],points[0]))
        for a,b in pairs:
            aa,bb = affine(a,transform),affine(b,transform)
            yield lambda t,a=aa,b=bb:add(a,mul(sub(b,a),t))
    else:
        pairs = list(zip(points,points[1:]))
        if geometry["closed"]:
            pairs.append((points[-1],points[0]))
        for a,b in pairs:
            controls = [affine(p,transform) for p in (a["co"],a["right"],b["left"],b["co"])]
            def cubic(t, controls=controls):
                w = [(1-t)**3,3*(1-t)**2*t,3*(1-t)*t*t,t**3]
                return [sum(c[k]*v for c,v in zip(controls,w)) for k in range(2)]
            yield cubic


def map_planar_master(master, surface, *, domain_transform=None, height=0, depth=0,
                      source_feature_width=None, thresholds=None, max_step=.1,
                      sampling_tolerance=5e-5, max_samples=50000):
    """Returns READY + both bound contracts, or HOLD/NOT_SUPPORTED with no deliverable.

    domain_transform defaults to identity, NEVER an implicit rectangle fit. Offsets
    are signed along the host normal. QA includes the offset metric, but is not a
    certificate of global self-intersection freedom.
    """
    try:
        return _map(master,surface,domain_transform,height,depth,source_feature_width,
                    thresholds,max_step,sampling_tolerance,max_samples)
    except SurfaceError as exc:
        return dict(status=exc.status,code=exc.code,message=str(exc),surface_map=None,mapped_master=None,qa=None)


def _map(master,surface,transform,height,depth,feature,thresholds,max_step,tolerance,budget):
    if not isinstance(master,PlanarMasterV1):
        raise SurfaceError("PLANAR_CONTRACT", "Expected validated PlanarMasterV1")
    mapper = SurfaceMapper(surface)
    qa = SurfaceTransferQA(thresholds)
    finite([height,depth,max_step,tolerance])
    if height < 0 or depth < 0 or (height and depth) or max_step <= 0 or tolerance <= 0:
        raise SurfaceError("TRANSFER_OPTIONS", "Positive sampling tolerances and height OR depth required")
    if type(budget) is not int or not 2 <= budget <= 1000000:
        raise SurfaceError("SAMPLE_BUDGET", "max_samples must be 2..1000000")
    if feature is not None:
        finite([feature])
        if feature <= 0:
            raise SurfaceError("FEATURE_WIDTH", "Source feature lower bound must be positive")
    matrix = finite(transform if transform is not None else [1,0,0,0,1,0],6)
    a,b,_,c,d,_ = matrix
    if abs(a*d-b*c) < 1e-14:
        raise SurfaceError("DOMAIN_TRANSFORM", "Singular domain transform")
    original = master.to_dict()
    geometries = {g["id"]:g for g in original["editable_geometry_references"]}
    regions = {r["id"]:r for r in original["closed_regions"]}
    roles = {r["entity_ref"]:r for r in original["semantic_roles"]}
    orders = {r["entity_ref"]:r for r in original["z_order"]}
    transforms = {t["id"]:t["matrix"] for t in original["repeat_transforms"]}
    templates = {g["template_region"] for g in original["repeat_groups"]}
    jobs = []
    identity = [1,0,0,0,1,0]
    def add_region(region, placement, suffix="", group=None, transform_ref=None):
        identifier = region["id"]+suffix
        jobs.append((identifier,region,placement,None,group,transform_ref))
        for hole in original["holes"]:
            if hole["parent_region"] == region["id"]:
                jobs.append((hole["id"]+suffix,hole,placement,identifier,group,transform_ref))
    for region in regions.values():
        if region["id"] not in templates:
            add_region(region,identity)
    for group in original["repeat_groups"]:
        for ref in group["transform_refs"]:
            add_region(regions[group["template_region"]],transforms[ref],f"@{group['id']}:{ref}",group["id"],ref)
    for edge in original["open_stroke_graph"]["edges"]:
        jobs.append((edge["id"],edge,identity,None,None,None))
    mapped, heatmap, spacing, correspondence = [],[],[],[]
    max_error, missing_width = 0.,False
    for identifier,entity,placement,parent,group,transform_ref in jobs:
        geometry = geometries[entity["geometry_ref"]]
        width = entity.get("stroke_width") or entity.get("width") or feature
        if width is None and entity.get("kind") != "support":
            missing_width = True
        points = []
        def evaluate(p):
            return mapper.to_surface(affine(p,matrix))
        def offset(s): return add(s["surface_position"],mul(s["normal"],height-depth))
        def subdivide(fn,t0,t1,p0,p1,s0,s1,level=0):
            nonlocal max_error
            samples = [(q,fn(t0+(t1-t0)*q)) for q in (.25,.5,.75)]
            values = [(q,p,evaluate(p)) for q,p in samples]
            err = max(norm(sub(offset(s),add(offset(s0),mul(sub(offset(s1),offset(s0)),q)))) for q,p,s in values)
            planar_error = max(norm(sub(p,add(p0,mul(sub(p1,p0),q)))) for q,p,s in values)
            if norm(sub(p1,p0)) > max_step or max(err,planar_error) > tolerance:
                if level >= 20:
                    raise SurfaceError("SAMPLING_LIMIT", "Adaptive subdivision failed to meet tolerance")
                _,pm,sm = values[1]
                subdivide(fn,t0,(t0+t1)/2,p0,pm,s0,sm,level+1)
                subdivide(fn,(t0+t1)/2,t1,pm,p1,sm,s1,level+1)
            else:
                max_error = max(max_error,err,planar_error)
                points.append((p1,s1))
                if len(points)+len(correspondence) > budget:
                    raise SurfaceError("SAMPLE_BUDGET", "Transfer sample budget exceeded; nothing finalized")
        for fn in _segments(geometry,placement):
            p0,p1 = fn(0),fn(1)
            s0,s1 = evaluate(p0),evaluate(p1)
            if not points:
                points.append((p0,s0))
            subdivide(fn,0,1,p0,p1,s0,s1)
        path = dict(id=identifier,source_entity=entity["id"],geometry_ref=entity["geometry_ref"],
                    parent_path=parent,repeat_group=group,repeat_transform=transform_ref,
                    closed=geometry["closed"],semantic_role=roles[entity["id"]],z_order=orders[entity["id"]],
                    palette_ref=entity.get("palette_ref"),repeat_group_role=roles[group] if group else None,
                    sample_refs=[],design_positions=[],offset_positions=[],frames=[])
        previous = None
        for point,sample in points:
            sample["id"] = f"mapped_{len(correspondence)}"
            correspondence.append(sample)
            du,dv = mapper.offset_differential(sample,height-depth)
            dx = add(mul(du,a),mul(dv,c))
            dy = add(mul(du,b),mul(dv,d))
            metrics = differential_metrics(dx,dy,sample["normal"])
            pa,pb,_,pc,pd,_ = placement
            tx,ty = unit(add(mul(dx,pa),mul(dy,pc))),unit(add(mul(dx,pb),mul(dy,pd)))
            orient = norm(sub(unit(cross(tx,ty)),sample["normal"]))
            row = dict(sample=sample,sample_ref=sample["id"],path_id=identifier,uv=sample["uv"],
                       distortion=metrics,orientation_error=max(orient,metrics["orientation_error"]),
                       feature_width_after_mapping=width*metrics["principal_stretches"][0] if width is not None else None)
            heatmap.append(row)
            if mapper.data["host_type"] == "REVOLUTION_VASE":
                row["circumference_scale"] = norm(sample["dp_du"])
                row["vertical_scale"] = norm(sample["dp_dv"])
            path["sample_refs"].append(sample["id"])
            path["design_positions"].append(point)
            path["offset_positions"].append(offset(sample))
            path["frames"].append(dict(tangent_x=unit(dx),tangent_y=unit(dy),motif_tangent_x=tx,motif_tangent_y=ty,normal=sample["normal"]))
            if previous is not None:
                pp,ss = previous
                length = norm(sub(point,pp))
                if length > 1e-12:
                    lo,hi,method = geodesic_bounds(mapper,ss["uv"],sample["uv"],height-depth)
                    spacing.append(dict(start=ss["id"],end=sample["id"],source_distance=length,
                        distance_bounds=[lo,hi],method=method,relative_error_bound=max(abs(lo/length-1),abs(hi/length-1))))
            previous = (point,sample)
        mapped.append(path)
    report = qa.assess(mapper,heatmap,spacing,max_error,missing_width)
    report["offset_qa"] = "Offset differential and sampled polyline error measured; global offset self-intersection is not certified"
    data = surface.to_dict()
    # A new snapshot, not mutation of the caller's surface map.
    data["correspondence"] = correspondence
    bound_map = SurfaceMapV1.from_dict(data)
    if report["status"] != "PASS":
        return dict(status="HOLD",code="SURFACE_QA_FAILED",message="Threshold exceeded or missing feature evidence; do not continue Blender final",
                    surface_map=bound_map.to_dict(),mapped_master=None,qa=report)
    result = SurfaceMappedMasterV1.from_dict(dict(schema_version="SurfaceMappedMasterV1",source_master=original,
        source_master_hash=content_hash(original),surface_map_hash=bound_map.content_hash,domain_transform=matrix,
        signed_offset=height-depth,paths=mapped,qa_status="PASS"))
    result.verify_surface_map(bound_map)
    return dict(status="READY",code="SURFACE_TRANSFER_READY",message="Numerical QA passed; visual approval remains separate",
                surface_map=bound_map.to_dict(),mapped_master=result.to_dict(),qa=report)
