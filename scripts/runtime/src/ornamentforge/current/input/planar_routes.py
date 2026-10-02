"""Loss-preserving adapters for reference decomposition."""
from pathlib import Path

from ..planar.contract import PlanarMasterV1


def base(route, bounds, scale):
    return dict(schema_version="PlanarMasterV1", route=route,
                domain={"bounds": bounds, "coordinates": "XY_RIGHT_UP"},
                physical_scale={"unit": "design_unit", "millimeters_per_unit": scale},
                closed_regions=[], holes=[], palette=[], repeat_groups=[], repeat_transforms=[],
                open_stroke_graph={"state": "NOT_EXTRACTED", "nodes": [], "edges": []},
                semantic_roles=[], z_order=[], source_correspondence=[], provenance=[],
                editable_geometry_references=[], source_hash="0"*64,
                qa_state={"status": "REVIEW_REQUIRED", "contract": "PASS", "limitations": []})


def entity(m, identifier, role, source, locator, layer=0, basis="inferred"):
    m["semantic_roles"].append(dict(entity_ref=identifier, role=role, basis=basis))
    m["z_order"].append(dict(entity_ref=identifier, layer=layer, basis=basis if basis == "declared" else "inferred"))
    m["source_correspondence"].append(dict(entity_ref=identifier, source_ref=source, locator=locator))


def reference_master(path, scale, options):
    from ..fidelity.frontend import reference_frontend
    return reference_frontend(path, scale, options)


def color_reference_master(path, scale, options):
    from ..fidelity.reconstruction import decompose_flat_art
    data = decompose_flat_art(path, **options)
    w,h = data["sample_size"]
    factor = 10/max(w,h)
    m = base("FIDELITY_RECONSTRUCTION", [-w*factor/2,-h*factor/2,w*factor/2,h*factor/2], scale)
    m["source_hash"] = data["source_sha256"]
    data["decomposition_options"] = dict(palette_size=14, resolution=1000, opening_seed=None, contour_tolerance=.65)
    data["decomposition_options"].update(options)
    m["provenance"].append(dict(id="reference", kind="raster", source=str(Path(path).resolve()),
                               sha256=data["source_sha256"], details={k:v for k,v in data.items() if k not in ("regions", "silhouette")}))
    for kind, rows in (("support", data["silhouette"]), ("fill", data["regions"])):
        for i,row in enumerate(rows):
            rid = f"{kind}_{i}"
            palette = None
            if kind == "fill":
                palette = f"color_{i}"
                m["palette"].append(dict(id=palette, rgb=row["color"]))
            for j, ring in enumerate(row["rings"]):
                gid = f"geometry_{rid}_{j}"
                m["editable_geometry_references"].append(dict(id=gid, representation="polyline", closed=True, data={"points": ring}))
                eid = rid if j == 0 else f"hole_{rid}_{j}"
                if j == 0:
                    m["closed_regions"].append(dict(id=eid, geometry_ref=gid, kind=kind, palette_ref=palette, stroke_width=None))
                else:
                    m["holes"].append(dict(id=eid, parent_region=rid, geometry_ref=gid))
                entity(m,eid,kind if j == 0 else "boundary_hole", "reference", f"{kind}/{i}/rings/{j}", 0 if kind == "support" else 1)
    m["qa_state"]["limitations"] = ["Palette contours are measured, not semantic recognition.",
        "Open strokes and repeats are not extracted; empty lists do not prove absence.",
        "Layer order is inferred, not measured depth; visual fidelity review is pending.",
        "Physical scale is unspecified." if scale is None else "Physical scale is user-declared."]
    return PlanarMasterV1.from_dict(m)
