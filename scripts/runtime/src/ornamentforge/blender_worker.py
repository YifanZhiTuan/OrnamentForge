"""Fixed B01 worker. Executed only by Blender's Python, never imported by host."""
import json
import math
from pathlib import Path
import sys
import traceback

import bpy
from mathutils import Vector

# Import the stdlib-only contract without importing the host package/jsonschema.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_contract import BlenderJob, contained
from canonical_curve import validate_curve, content_hash, control_points


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False), encoding="utf-8")


def material(name, color):
    mat = bpy.data.materials.new(name)
    mat.use_fake_user = True
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1)
    shader.inputs["Roughness"].default_value = 0.65
    return mat


def initialize(plan):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = plan["render"]["samples"]
    scene.cycles.seed = plan["parameters"]["seed"] % 2147483647
    scene.cycles.use_animated_seed = False
    scene.cycles.use_adaptive_sampling = False
    scene.cycles.use_denoising = False
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 4
    scene.render.resolution_x, scene.render.resolution_y = plan["render"]["resolution"]
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.film_transparent = False
    scene.render.use_file_extension = True
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    scene.world = bpy.data.worlds.new("B01_World")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.18,0.18,0.18,1)
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.7
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1
    scene["ornamentforge_spec_hash"] = plan["spec_hash"]
    scene["ornamentforge_plan_hash"] = plan["plan_hash"]
    scene["ornamentforge_stage"] = 0
    scene["ornamentforge_build_plan"] = json.dumps(plan, sort_keys=True)
    bpy.context.preferences.filepaths.save_version = 0
    material("B01_BaseMaterial", (0.20,0.25,0.28))
    material("B01_OrnamentMaterial", (0.65,0.42,0.18))
    width, depth, thickness = plan["plate_dimensions"]
    extent = max(width, depth)
    target = Vector((0,0,thickness/2))
    positions = {"front": (0,0,extent*2), "perspective": (extent*0.8,-extent,extent*1.1),
                 "low_side": (extent*0.28,-extent*1.25,extent*0.32)}
    for name, pos in positions.items():
        camera = bpy.data.cameras.new("B01_Camera_"+name)
        obj = bpy.data.objects.new(camera.name, camera)
        scene.collection.objects.link(obj)
        obj.location = pos
        obj.rotation_euler = (target-obj.location).to_track_quat("-Z", "Y").to_euler()
        camera.type = "ORTHO" if name != "perspective" else "PERSP"
        camera.ortho_scale = extent*1.2
        camera.lens = 48
        camera.clip_end = extent*20
        camera.clip_start = 0.001
    scene.camera = bpy.data.objects["B01_Camera_perspective"]
    for name, pos, energy in (("Key",(-extent/2,-extent/2,extent),750),
                              ("Fill",(extent/2,extent/2,extent*0.6),400)):
        light = bpy.data.lights.new("B01_"+name, "AREA")
        light.energy = energy * (extent/4)**2
        light.shape = "DISK"
        light.size = extent*0.75
        obj = bpy.data.objects.new(light.name, light)
        scene.collection.objects.link(obj)
        obj.location = pos
        obj.rotation_euler = (target-obj.location).to_track_quat("-Z", "Y").to_euler()


def base(plan):
    bpy.ops.mesh.primitive_cube_add(size=1)
    obj = bpy.context.object
    obj.name = "B01_Base"
    obj.dimensions = plan["plate_dimensions"]
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(bpy.data.materials["B01_BaseMaterial"])


def curve(name, points, width, cyclic=False):
    data = bpy.data.curves.new(name+"Curve", "CURVE")
    data.dimensions = "3D"
    data.resolution_u = 24
    data.render_resolution_u = 24
    data.bevel_depth = width/2
    data.bevel_resolution = 4
    data.use_fill_caps = True
    data.twist_mode = "Z_UP"
    spline = data.splines.new("BEZIER")
    spline.bezier_points.add(len(points)-1)
    spline.use_cyclic_u = cyclic
    for point, source in zip(spline.bezier_points, points):
        point.handle_left_type = point.handle_right_type = "FREE"
        point.co, point.handle_left, point.handle_right = source["co"], source["left"], source["right"]
        point.radius = 1
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    data.materials.append(bpy.data.materials["B01_OrnamentMaterial"])
    return obj


def serialize_curve(data):
    spline = data.splines[0]
    return validate_curve({"curve_version":"1.0","representation":"bezier_curve","dimensions":data.dimensions,
                           "resolution_u":data.resolution_u,"twist_mode":data.twist_mode,"cyclic":spline.use_cyclic_u,
                           "points":[{"co":list(p.co),"left":list(p.handle_left),"right":list(p.handle_right),
                                      "left_type":p.handle_left_type,"right_type":p.handle_right_type,
                                      "radius":p.radius,"tilt":p.tilt} for p in spline.bezier_points]})


def motifs(plan,job):
    p = plan["parameters"]
    reconstructed = {}
    objects = {}
    for kind,name,width in (("vine","B01_Vine",p["vine_width"]),
                            ("leaf","B01_LeafTemplate",plan["leaf_stroke_width"]/p["leaf_scale"])):
        source = plan["motif_sources"][kind]
        artifact = contained(Path(job.run_directory)/source["snapshot_path"],job.run_directory)
        payload = validate_curve(json.loads(artifact.read_text(encoding="utf-8")))
        if content_hash(payload)!=source["content_hash"]:
            raise ValueError("Stored motif hash mismatch before Blender reconstruction")
        obj = curve(name,control_points(payload),width,payload["cyclic"])
        obj.data.resolution_u = obj.data.render_resolution_u = payload["resolution_u"]
        obj.data.twist_mode = payload["twist_mode"]
        for target,stored in zip(obj.data.splines[0].bezier_points,payload["points"]):
            target.radius,target.tilt = stored["radius"],stored["tilt"]
        observed = serialize_curve(obj.data)
        if content_hash(observed)!=source["content_hash"]:
            raise ValueError("Blender reconstructed curve differs from canonical asset")
        reconstructed[kind] = {"motif_id":source["id"],"source_status":source["status"],
                               "loaded_hash":source["content_hash"],"reconstructed_hash":content_hash(observed),
                               "snapshot_path":source["snapshot_path"],"canonical_equal":True}
        objects[kind] = obj
    vine,leaf = objects["vine"],objects["leaf"]
    bpy.context.scene["motif_reconstruction"] = json.dumps(reconstructed,sort_keys=True)
    write(Path(job.output_directory)/"motif_reconstruction.json",reconstructed)
    leaf.scale = (p["leaf_scale"],)*3
    # The template is previewed separately at G3 then hidden when linked instances are placed.
    leaf.location = (0, -0.65, 0)
    attach(plan, [vine, leaf], p["emboss_height"]*0.5)


def layout(plan):
    template = bpy.data.objects["B01_LeafTemplate"]
    template.hide_render = True
    template.hide_set(True)
    for transform in plan["leaf_transforms"]:
        obj = bpy.data.objects.new(transform["name"], template.data)
        bpy.context.scene.collection.objects.link(obj)
        obj.location = transform["location"]
        obj.rotation_euler.z = transform["rotation_z"]
        obj.scale = (transform["scale_xy"],)*3
    attach(plan, ornaments(), plan["parameters"]["emboss_height"]*0.5)


def ornaments():
    return [o for o in bpy.context.scene.objects if o.name == "B01_Vine" or o.name.startswith("B01_Leaf_")]


def attach(plan, objects, height):
    top = plan["plate_dimensions"][2]/2
    for obj in objects:
        # Curves lie in local XY. Z scaling controls relief independently of plan-view stroke width.
        obj.scale.z = height/(2*obj.data.bevel_depth)
        obj.location.z = top+height/2


def vertices(obj):
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        return [list(obj.matrix_world @ v.co) for v in mesh.vertices]
    finally:
        evaluated.to_mesh_clear()


def bounds(points):
    if not points:
        raise ValueError("Empty evaluated geometry")
    return [[min(p[i] for p in points) for i in range(3)],
            [max(p[i] for p in points) for i in range(3)]]


def stroke_measure(obj):
    # Measure an evaluated profile ring perpendicular to the first Bezier tangent.
    # Blender bevel_resolution=4 produces 20 vertices/ring. Identify ring by its
    # centerline tangent projection, rather than trusting the requested width.
    point = obj.data.splines[0].bezier_points[0]
    center = obj.matrix_world @ point.co
    tangent = obj.matrix_world.to_3x3() @ (point.handle_right-point.co)
    tangent.z = 0
    tangent.normalize()
    normal = Vector((-tangent.y, tangent.x, 0))
    ring = []
    radius = obj.data.bevel_depth*max(abs(obj.scale.x),abs(obj.scale.y))
    for raw in vertices(obj):
        delta = Vector(raw)-center
        if abs(delta.dot(tangent)) < 0.000001 and abs(delta.dot(normal)) <= radius*1.01:
            ring.append(delta.dot(normal))
    if len(ring) < 4:
        raise ValueError(f"Cannot measure bevel profile for {obj.name}")
    return max(ring)-min(ring)


def measurements(plan, stage):
    bpy.context.view_layer.update()
    result = {"stage": stage, "object_names": sorted(o.name for o in bpy.context.scene.objects)}
    plate = bpy.data.objects.get("B01_Base")
    if plate:
        low, high = bounds(vertices(plate))
        result["base_dimensions"] = [high[i]-low[i] for i in range(3)]
        result["base_dimension_error"] = max(abs(a-b) for a,b in zip(result["base_dimensions"],plan["plate_dimensions"]))
    if stage >= 3:
        result["motif_reconstruction"] = json.loads(bpy.context.scene.get("motif_reconstruction","{}"))
        motif_objects = [bpy.data.objects["B01_Vine"], bpy.data.objects["B01_LeafTemplate"]]
        result["motif_validation"] = {o.name: {"vertices": len(vertices(o)), "stroke_width": stroke_measure(o),
                                     "editable_curve": o.type == "CURVE"} for o in motif_objects}
    if stage >= 4:
        objects = ornaments()
        points = {o.name: vertices(o) for o in objects}
        low, high = bounds([v for values in points.values() for v in values])
        top = plan["plate_dimensions"][2]/2
        bottoms = [bounds(values)[0][2] for values in points.values()]
        heights = [bounds(values)[1][2]-top for values in points.values()]
        result.update(ornament_bounds=[low,high], leaf_count=sum(o.name.startswith("B01_Leaf_") for o in objects),
                      margin_clearance=min(plan["plate_dimensions"][i]/2-max(abs(low[i]),abs(high[i])) for i in (0,1)),
                      emboss_height=max(heights), emboss_height_min=min(heights),
                      attachment_gap=max(0,max(bottoms)-top), burial_depth=max(0,top-min(bottoms)),
                      minimum_feature_width=min(stroke_measure(o) for o in objects))
    return result


def snapshot():
    vine = bpy.data.objects["B01_Vine"]
    return {"vine_control_points": [{"co": list(p.co), "left": list(p.handle_left), "right": list(p.handle_right)}
                                    for p in vine.data.splines[0].bezier_points],
            "leaf_transforms": [{"name": o.name, "location": list(o.location), "rotation": list(o.rotation_euler),
                                  "scale": list(o.scale), "matrix_world": [list(row) for row in o.matrix_world]}
                                 for o in sorted(ornaments(),key=lambda obj:obj.name) if o.name.startswith("B01_Leaf_")]}


def main(job):
    plan = json.loads(Path(job.build_plan_path).read_text(encoding="utf-8"))
    spec = json.loads(Path(job.input_spec_path).read_text(encoding="utf-8"))
    if plan["benchmark"] != "B01" or plan["parameters"]["seed"] != job.seed or spec["generation"]["seed"] != job.seed:
        raise ValueError("Job/spec/plan identity mismatch")
    if job.input_checkpoint:
        bpy.ops.wm.open_mainfile(filepath=job.input_checkpoint, load_ui=False, use_scripts=False)
        if bpy.context.scene.get("ornamentforge_plan_hash") != plan["plan_hash"]:
            raise ValueError("Checkpoint belongs to a different build plan")
    else:
        if job.stage != 0:
            raise ValueError("First Blender job must initialize G0")
        initialize(plan)
    scene = bpy.context.scene
    scene.render.filepath = str(Path(job.output_directory)/"render.png")
    scene.render.use_compositing = False
    scene.render.use_sequencer = False
    bpy.context.preferences.filepaths.save_version = 0
    artifacts = []
    if job.requested_operation == "build_stage":
        prior = scene.get("ornamentforge_stage", 0)
        if job.stage not in (prior, prior+1):
            raise ValueError("Blender stage cannot skip")
        if job.stage > prior:
            if job.stage == 2:
                base(plan)
            elif job.stage == 3:
                retrieval = json.loads((Path(job.run_directory)/"retrieval.json").read_text(encoding="utf-8"))
                if retrieval.get("selected") != plan.get("motif_sources"):
                    raise ValueError("Recorded retrieval selection must match the build plan")
                motifs(plan,job)
            elif job.stage == 4:
                layout(plan)
            elif job.stage == 5:
                attach(plan, ornaments(), plan["parameters"]["emboss_height"]*0.5)
            elif job.stage == 6:
                attach(plan, ornaments(), plan["parameters"]["emboss_height"])
        scene["ornamentforge_stage"] = job.stage
        bpy.context.view_layer.update()
        bpy.ops.wm.save_as_mainfile(filepath=job.checkpoint_path, check_existing=False)
        artifacts.append(job.checkpoint_path)
        if job.stage >= 4:
            path = Path(job.output_directory)/"scene_snapshot.json"
            write(path, snapshot())
            artifacts.append(str(path))
    elif job.requested_operation == "render":
        for view in job.requested_validation_views:
            scene.camera = bpy.data.objects["B01_Camera_"+view]
            path = Path(job.output_directory)/(view+".png")
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            artifacts.append(str(path))
    elif job.requested_operation == "restore":
        if scene.get("ornamentforge_stage") != job.stage:
            raise ValueError("Restored checkpoint stage mismatch")
    return {"result_version": "1.0", "success": True, "blender_version": bpy.app.version_string,
            "produced_artifacts": artifacts, "geometry_measurements": measurements(plan,job.stage),
            "warnings": ["Editable B01; separate curves, no print-ready manifold certification"], "errors": []}


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--")+1:]
    if len(args) != 2:
        raise ValueError("Expected job path and trusted workspace root")
    job_path = contained(args[0], args[1])
    job = BlenderJob.from_dict(json.loads(job_path.read_text(encoding="utf-8")))
    if Path(job.workspace).resolve() != Path(args[1]).resolve():
        raise ValueError("Workspace identity mismatch")
    try:
        result = main(job)
    except Exception as exc:
        result = {"result_version": "1.0", "success": False, "blender_version": bpy.app.version_string,
                  "produced_artifacts": [], "geometry_measurements": {}, "warnings": [],
                  "errors": [f"{type(exc).__name__}: {exc}", traceback.format_exc()]}
        write(job.result_path, result)
        raise
    write(job.result_path, result)
