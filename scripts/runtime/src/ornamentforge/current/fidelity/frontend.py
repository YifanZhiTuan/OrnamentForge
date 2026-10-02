"""Reference mode dispatch; existing color decomposition remains independent."""
from .reference_mode import classify_reference


def reference_frontend(path, scale, options):
    from ..input.planar_routes import color_reference_master
    from ..planar.contract import PlanarMasterV1
    options=dict(options)
    classification=classify_reference(path,options.pop("reference_mode",None))
    mode=classification["mode"]
    if mode=="COLOR_BLOCK":
        m=color_reference_master(path,scale,options).to_dict()
        m["provenance"][0]["details"]["reference_mode"]=classification
        return PlanarMasterV1.from_dict(m)
    if mode=="LINE_ART" and set(options)-{"resolution"}:
        raise ValueError("LINE_ART accepts resolution; palette/opening/contour options require COLOR_BLOCK or MIXED")
    from .line_art import extract_line_art
    result=extract_line_art(path,scale,classification,resolution=options.get("resolution",2048),mixed=mode=="MIXED")
    if mode=="LINE_ART":return result["master"]
    # Namespaces are already disjoint: color IDs versus stroke_* / line_reference.
    # Force both independent extractions to the same working coordinate domain.
    color_options=options|{"resolution":options.get("resolution",2048)}
    m=color_reference_master(path,scale,color_options).to_dict()
    line=result["master"].to_dict()
    m["provenance"][0]["details"]["reference_mode"]=classification
    for key in ("editable_geometry_references","semantic_roles","z_order","source_correspondence","provenance"):
        m[key].extend(line[key])
    m["open_stroke_graph"]=line["open_stroke_graph"]
    m["qa_state"]["limitations"]=[v for v in m["qa_state"]["limitations"] if not v.startswith("Open strokes and repeats")]
    m["qa_state"]["limitations"].append("Repeats are not extracted; empty groups do not prove absence.")
    m["qa_state"]["limitations"].extend(line["qa_state"]["limitations"]+[
        "MIXED is independent color regions plus neutral dark strokes; no deduplication or semantic fusion."])
    return PlanarMasterV1.from_dict(m)


def line_qa_from_master(master):
    for row in master.to_dict()["provenance"]:
        if row["kind"]=="raster_line_art":return row["details"]["line_qa"]
    return None
