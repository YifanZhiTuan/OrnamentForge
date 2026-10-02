"""Thin consumer for mapped engraved/relief/painted data; no new craft aesthetics."""
from ..surface.planar_adapter import map_planar_master


def map_surface_craft(master, surface, *, craft, height=0, depth=0,
                      reviewed_semantics=False, material_by_role=None, **mapping_options):
    if craft not in ("engraved","relief","painted"):
        return dict(status="NOT_SUPPORTED",code="CRAFT_NOT_SUPPORTED",message=craft,
                    surface_map=None,mapped_master=None,qa=None)
    if (craft == "engraved" and height != 0) or (craft == "relief" and depth != 0) or (craft == "painted" and (height != 0 or depth != 0)):
        return dict(status="HOLD",code="CRAFT_SIGN",message="Engraved uses depth, relief uses height, painted uses zero offset",
                    surface_map=None,mapped_master=None,qa=None)
    if craft == "painted":
        from .painted import color_route
        try:
            color_route(paint_requested=True,semantic_regions=reviewed_semantics is True)
        except ValueError as exc:
            return dict(status="HOLD",code="SEMANTIC_REVIEW_REQUIRED",message=str(exc),
                        surface_map=None,mapped_master=None,qa=None)
    materials = material_by_role or {}
    if not isinstance(materials,dict) or any(not isinstance(k,str) or not isinstance(v,str) or not v for k,v in materials.items()):
        return dict(status="HOLD",code="MATERIAL_BINDING",message="Materials must map semantic role to nonempty material ID",
                    surface_map=None,mapped_master=None,qa=None)
    result = map_planar_master(master,surface,height=height,depth=depth,**mapping_options)
    if result["status"] != "READY":
        return result
    source = result["mapped_master"]["source_master"]
    palette = {p["id"]:p["rgb"] for p in source["palette"]}
    paths = {p["id"]:p for p in result["mapped_master"]["paths"]}
    bindings = []
    for path in paths.values():
        # Holes inherit parent region color, but remain holes, never filled shapes.
        color_path = paths[path["parent_path"]] if path["parent_path"] else path
        role = color_path["semantic_role"]["role"]
        rgb,material = palette.get(color_path["palette_ref"]),materials.get(role)
        if craft == "painted" and rgb is None and material is None and role != "support":
            return dict(status="HOLD",code="PAINT_BINDING_REQUIRED",message=f"No source palette or declared material for {role}",
                        surface_map=result["surface_map"],mapped_master=None,qa=result["qa"])
        bindings.append(dict(path_id=path["id"],positions_ref="mapped_master.paths.offset_positions",
                             semantic_role=role,rgb=rgb,material_id=material,parent_path=path["parent_path"]))
    result["craft"] = dict(kind=craft,formula={"engraved":"P - depth*N","relief":"P + height*N","painted":"P + semantic color/material"}[craft],
                           bindings=bindings,visual_approval="NOT_GRANTED",blender_final_started=False)
    return result
