"""Blender-only read adapter; no operators, modifiers, unwrap, save or render.

Can be loaded with runpy.run_path inside Blender without project dependencies.
Coordinates are baked into an in-memory JSON snapshot, never into the user's mesh.
"""


def snapshot_blender_mesh(obj, uv_layer=None):
    if getattr(obj, "type", None) != "MESH":
        raise ValueError("UV_REQUIRED: a Blender mesh object is required")
    if obj.mode != "OBJECT":
        raise ValueError("HOLD: leave Edit Mode explicitly before snapshotting")
    if any(m.show_viewport for m in obj.modifiers):
        raise ValueError("NOT_SUPPORTED: active modifiers require an explicit evaluated mesh snapshot")
    mesh = obj.data
    layer = mesh.uv_layers.get(uv_layer) if uv_layer else mesh.uv_layers.active
    if layer is None:
        raise ValueError("UV_REQUIRED: existing UV layer required; no automatic unwrap")
    mesh.calc_loop_triangles()  # tessellation cache only; does not edit faces/UVs
    vertices = [list(obj.matrix_world @ v.co) for v in mesh.vertices]
    triangles = []
    for tri in mesh.loop_triangles:
        points = [obj.matrix_world @ mesh.vertices[i].co for i in tri.vertices]
        normal = (points[1]-points[0]).cross(points[2]-points[0]).normalized()
        triangles.append(dict(id=tri.index,face_id=tri.polygon_index,
            vertex_indices=list(tri.vertices),loop_indices=list(tri.loops),
            uv=[list(layer.data[i].uv) for i in tri.loops],normal=list(normal)))
    return dict(vertices=vertices,triangles=triangles,
                seam_edges=[list(edge.vertices) for edge in mesh.edges if edge.use_seam],
                uv_layer=layer.name,coordinate_space="WORLD",object_name=obj.name)
