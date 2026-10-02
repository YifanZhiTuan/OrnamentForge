"""Fixed Blender-owned showcase worker. No prompt code evaluation."""
import json
import math
from pathlib import Path
import sys
import traceback
import time
import hashlib
import struct

import bpy
import bmesh
from mathutils import Vector,Quaternion

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from blender_contract import contained
from canonical_curve import validate_curve,content_hash

AXES=[(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)]

def write(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,sort_keys=True,allow_nan=False),encoding="utf-8")

def frame(n):
    n=Vector(n);u=(Vector((0,0,1)) if abs(n.z)<.9 else Vector((0,1,0))).cross(n).normalized()
    return u,n.cross(u)

def collection(name):
    c=bpy.data.collections.get(name)
    if not c:
        c=bpy.data.collections.new(name);bpy.context.scene.collection.children.link(c)
    return c

def link(obj,group):
    collection(group).objects.link(obj)
    return obj

def material(name,color,metal=0,rough=.32):
    mat=bpy.data.materials.new(name);mat.use_fake_user=True;mat.use_nodes=True
    shader=mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value=(*color,1)
    shader.inputs["Metallic"].default_value=metal;shader.inputs["Roughness"].default_value=rough
    mat.diffuse_color=(*color,1)
    return mat

def initialize(plan):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s=bpy.context.scene;s["showcase_plan_hash"]=plan["plan_hash"];s["showcase_stage"]=0
    s["showcase_seed"]=plan["seed"]
    material("ivory",(.73,.66,.51),.12,.31)
    material("gold",(.56,.34,.11),.78,.24)
    material("dark",(.065,.077,.087),.2,.4)
    material("floor",(.105,.12,.14),.05,.5)
    if plan.get('detail_upgrade'):
        shader=bpy.data.materials['ivory'].node_tree.nodes.get('Principled BSDF')
        shader.inputs['Base Color'].default_value=(.78,.735,.635,1)
        shader.inputs['Metallic'].default_value=0
        shader.inputs['Roughness'].default_value=.38
        shader.inputs['Subsurface Weight'].default_value=.035
        shader=bpy.data.materials['gold'].node_tree.nodes.get('Principled BSDF')
        shader.inputs['Base Color'].default_value=(.78,.735,.635,1)
        shader.inputs['Metallic'].default_value=0;shader.inputs['Roughness'].default_value=.38
    if plan.get("material_style")=="silver_botanical":
        for name,color in (("ivory",(.43,.48,.52)),("gold",(.68,.73,.78))):
            shader=bpy.data.materials[name].node_tree.nodes.get("Principled BSDF")
            shader.inputs["Base Color"].default_value=(*color,1);shader.inputs["Metallic"].default_value=.85
    elif plan.get("material_style")=="bronze_botanical":
        shader=bpy.data.materials["ivory"].node_tree.nodes.get("Principled BSDF")
        shader.inputs["Base Color"].default_value=(.18,.10,.045,1);shader.inputs["Metallic"].default_value=.75
    s.render.engine="CYCLES";s.cycles.device="CPU";s.cycles.samples=48
    s.cycles.use_denoising=True;s.cycles.seed=plan["seed"];s.cycles.use_animated_seed=False
    s.render.threads_mode="FIXED";s.render.threads=8
    # Prefer installed GPU when usable; CPU fallback stays deterministic.
    try:
        prefs=bpy.context.preferences.addons["cycles"].preferences
        for backend in ("OPTIX","CUDA","HIP"):
            try:
                prefs.compute_device_type=backend;prefs.get_devices()
                gpu=[d for d in prefs.devices if d.type not in ("CPU",)]
                if gpu:
                    for d in prefs.devices:d.use=d.type!="CPU"
                    s.cycles.device="GPU";break
            except Exception: pass
    except Exception: pass
    s.world=bpy.data.worlds.new("StudioWorld");s.world.use_nodes=True
    s.world.node_tree.nodes["Background"].inputs["Color"].default_value=(.20,.23,.29,1)
    s.world.node_tree.nodes["Background"].inputs["Strength"].default_value=.22
    s.view_settings.view_transform="AgX"
    s.render.image_settings.file_format="PNG";s.render.image_settings.color_mode="RGB"
    s.render.resolution_x=s.render.resolution_y=1200;s.render.resolution_percentage=100
    s.render.film_transparent=False;s.render.use_compositing=False;s.render.use_sequencer=False
    s.unit_settings.system="METRIC"
    bpy.context.preferences.filepaths.save_version=0
    r=plan["radius"]
    bpy.ops.mesh.primitive_plane_add(size=200*r,location=(0,0,-1.14*r))
    floor=bpy.context.object;floor.name="Studio_Ground";floor.data.materials.append(bpy.data.materials["floor"])
    # Discreet display plinth supports the object visually without hiding the lower hemisphere.
    bpy.ops.mesh.primitive_cylinder_add(vertices=96,radius=.42*r,depth=.10*r,location=(0,0,-1.09*r))
    plinth=bpy.context.object;plinth.name="Display_Plinth";plinth.data.materials.append(bpy.data.materials["dark"])
    bevel=plinth.modifiers.new("Soft machined edge","BEVEL");bevel.width=.025*r;bevel.segments=4
    for p in plinth.data.polygons:p.use_smooth=True
    camera=bpy.data.cameras.new("Showcase_Camera");obj=bpy.data.objects.new("Showcase_Camera",camera)
    link(obj,"Studio");s.camera=obj;camera.lens=65;camera.clip_end=100*r
    for name,pos,energy,size,color in (("Key",(3,-4,5),850,4,(1,.88,.73)),("Fill",(-4,-2,1.5),600,3,(.68,.80,1)),
                                       ("Rim",(1,3,3),1100,3,(1,.9,.72))):
        light=bpy.data.lights.new(name,"AREA");light.energy=energy*r*r;light.shape="DISK";light.size=size*r;light.color=color
        o=bpy.data.objects.new(name,light);link(o,"Studio");o.location=Vector(pos)*r
        o.rotation_euler=(-o.location).to_track_quat("-Z","Y").to_euler()

def shell(plan,openings=True,perforated=False):
    previous=bpy.data.objects.get("Base_Shell")
    if previous:bpy.data.objects.remove(previous,do_unlink=True)
    r=plan["radius"];vertices=[];faces=[];hole_count=0
    if not openings:
        bpy.ops.mesh.primitive_uv_sphere_add(segments=96,ring_count=48,radius=r)
        obj=bpy.context.object;obj.name="Base_Shell"
    else:
        nt=plan["shell"]["sectors"];nr=plan["shell"]["rings"]
        inner=math.tan(math.asin(plan["opening_ratio"]))
        for normal in AXES:
            n=Vector(normal);u,v=frame(n);offset=len(vertices)
            for i in range(nr+1):
                t=i/nr
                for j in range(nt):
                    angle=j*math.tau/nt;co,si=math.cos(angle),math.sin(angle)
                    outer=1/max(abs(co),abs(si));rho=inner+(outer-inner)*t
                    vertices.append(tuple((n+u*(rho*co)+v*(rho*si)).normalized()*r))
            for i in range(nr):
                for j in range(nt):
                    # Radial windows are masks in the shell plan, before any ornament exists.
                    width=plan["shell"]["cutout_width"];height=plan["shell"].get("cutout_height",2)
                    # Elliptical masks create leaf-shaped windows, rather than rectangular slots.
                    def window(start):
                        shift=((start//7+(j//12)*3)%5)-2 if plan['shell'].get('staggered') else 0
                        return ((i-start-(height-1)/2)/(height/2))**2+((j%12-5.5-shift)/(width/2))**2<1
                    skip=perforated and any(window(start) for start in plan["shell"]["cutout_rows"])
                    if skip:
                        continue
                    a=offset+i*nt+j;b=offset+(i+1)*nt+j;c=offset+(i+1)*nt+(j+1)%nt;d=offset+i*nt+(j+1)%nt
                    faces.append((a,b,c,d))
        mesh=bpy.data.meshes.new("SphericalAnnularPanels");mesh.from_pydata(vertices,[],faces);mesh.update()
        bm=bmesh.new();bm.from_mesh(mesh)
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=r*.00001)
        # Count real boundary components before Solidify closes their side walls.
        adjacency={}
        for edge in bm.edges:
            if edge.is_boundary:
                a,b=edge.verts;adjacency.setdefault(a,set()).add(b);adjacency.setdefault(b,set()).add(a)
        unseen=set(adjacency);boundaries=0
        while unseen:
            stack=[unseen.pop()];boundaries+=1
            while stack:
                for vertex in adjacency[stack.pop()]:
                    if vertex in unseen:unseen.remove(vertex);stack.append(vertex)
        hole_count=max(0,boundaries-6)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
        obj=bpy.data.objects.new("Base_Shell",mesh);link(obj,"Base_Shell")
        sub=obj.modifiers.new("Rounded lace windows","SUBSURF");sub.levels=1;sub.render_levels=1
        # Snap subdivision vertices back onto the design sphere using a geometry-node modifier.
        group=bpy.data.node_groups.new("Analytic sphere projection","GeometryNodeTree")
        group.interface.new_socket(name="Geometry",in_out="INPUT",socket_type="NodeSocketGeometry")
        group.interface.new_socket(name="Geometry",in_out="OUTPUT",socket_type="NodeSocketGeometry")
        nodes=group.nodes;links=group.links
        inp=nodes.new("NodeGroupInput");out=nodes.new("NodeGroupOutput");pos=nodes.new("GeometryNodeInputPosition")
        normal=nodes.new("ShaderNodeVectorMath");normal.operation="NORMALIZE"
        scale=nodes.new("ShaderNodeVectorMath");scale.operation="SCALE";scale.inputs[3].default_value=r
        setpos=nodes.new("GeometryNodeSetPosition")
        links.new(inp.outputs["Geometry"],setpos.inputs["Geometry"]);links.new(pos.outputs["Position"],normal.inputs[0])
        links.new(normal.outputs["Vector"],scale.inputs[0]);links.new(scale.outputs["Vector"],setpos.inputs["Position"])
        links.new(setpos.outputs["Geometry"],out.inputs["Geometry"])
        mod=obj.modifiers.new("Conform exactly to radius","NODES");mod.node_group=group
    obj.data.materials.append(bpy.data.materials["ivory"])
    for p in obj.data.polygons:p.use_smooth=True
    solid=obj.modifiers.new("Editable wall thickness","SOLIDIFY");solid.thickness=plan["wall_thickness"];solid.offset=-1;solid.use_even_offset=True
    bevel=obj.modifiers.new("Soft aperture edges","BEVEL");bevel.width=.002*r;bevel.segments=2
    obj["opening_count"]=6 if openings else 0;obj["pierced_windows"]=hole_count
    obj["topological_apertures"]=boundaries if openings else 0
    obj["radius"]=r;obj["wall_thickness"]=plan["wall_thickness"]
    return obj

def make_curve(item):
    data=bpy.data.curves.new(item["name"],"CURVE");data.dimensions="3D"
    data.resolution_u=2;data.bevel_depth=item["width"]/2;data.bevel_resolution=3;data.use_fill_caps=True
    spline=data.splines.new("POLY");spline.points.add(len(item["points"])-1)
    spline.use_cyclic_u=item["closed"]
    for point,co in zip(spline.points,item["points"]):point.co=(*co,1)
    obj=bpy.data.objects.new(item["name"],data);link(obj,item["category"].title())
    data.materials.append(bpy.data.materials[item["material"]])
    obj["category"]=item["category"];obj["motif_role"]=item.get("role") or "border"
    obj["width"]=item["width"]
    return obj

SURFACE_BATCHES={}

def surface(item,plan):
    boundary=[Vector(p) for p in item["boundary"]];n=len(boundary)
    center=sum(boundary,Vector())/n;normal=center.normalized();center=normal*(plan["radius"]+item["height"])
    # Two concentric domed bands give sculpted leaf/petal surfaces rather than flat line loops.
    middle=[]
    for p in boundary:
        q=center.lerp(p,.55).normalized()*(plan["radius"]+item["height"]*.75)
        middle.append(q)
    vertices=[tuple(center)]+[tuple(p) for p in middle]+[tuple(p.normalized()*(plan["radius"]+.002*plan["radius"]+item.get("base_offset",0))) for p in boundary]
    faces=[]
    for i in range(n):
        j=(i+1)%n;faces.append((0,1+i,1+j));faces.append((1+i,1+n+i,1+n+j,1+j))
    if plan.get('detail_upgrade'):
        # Explicit closed backs avoid Blender 5.1 Solidify instability on thousands
        # of disconnected tiny subdivided islands. Shape remains editable mesh.
        back_center=len(vertices);vertices.append(tuple(normal*(plan['radius']-.002*plan['radius'])))
        back_ring=len(vertices)
        vertices.extend(tuple(p.normalized()*(plan['radius']-.002*plan['radius'])) for p in boundary)
        for i in range(n):
            j=(i+1)%n
            faces.append((back_center,back_ring+j,back_ring+i))
            faces.append((1+n+i,back_ring+i,back_ring+j,1+n+j))
        key=(item['category'],item['role'])
        batch=SURFACE_BATCHES.setdefault(key,{'verts':[],'faces':[],'count':0})
        offset=len(batch['verts']);batch['verts'].extend(vertices)
        batch['faces'].extend(tuple(i+offset for i in face) for face in faces);batch['count']+=1
        return
    mesh=bpy.data.meshes.new(item["name"]);mesh.from_pydata(vertices,[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
    obj=bpy.data.objects.new(item["name"],mesh);link(obj,item["category"].title())
    obj.data.materials.append(bpy.data.materials[item["material"]])
    for p in mesh.polygons:p.use_smooth=True
    if plan.get('detail_upgrade'):
        sub=obj.modifiers.new('Soft carved leaf','SUBSURF');sub.levels=1;sub.render_levels=1
    solid=obj.modifiers.new("Petal body","SOLIDIFY");solid.thickness=.005*plan["radius"];solid.offset=-1
    obj["category"]=item["category"];obj["motif_role"]=item["role"]
    return obj

def flush_surfaces(plan):
    for (category,role),batch in SURFACE_BATCHES.items():
        mesh=bpy.data.meshes.new('Carved_'+category+'_'+role)
        mesh.from_pydata(batch['verts'],[],batch['faces']);mesh.update()
        bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
        obj=bpy.data.objects.new(mesh.name,mesh);link(obj,category.title())
        mesh.materials.append(bpy.data.materials['ivory'])
        for p in mesh.polygons:p.use_smooth=True
        # The sampled, smooth-shaded dome already has sufficient curvature at this
        # scale. Avoid OpenSubdiv stencil allocation for thousands of tiny islands.
        obj['category']=category;obj['motif_role']=role;obj['surface_count']=batch['count']
    SURFACE_BATCHES.clear()

def populate(plan,categories):
    if plan.get('detail_upgrade'):
        groups={}
        for item in plan['curves']:
            if item['category'] in categories:
                groups.setdefault((item['category'],item['role'],item['width'],item['material']),[]).append(item)
        for key,items in groups.items():
            obj=make_curve(items[0]);obj.name='CarvedPaths_'+items[0]['name'];obj['curve_count']=len(items)
            obj.data.bevel_resolution=2
            for item in items[1:]:
                spline=obj.data.splines.new('POLY');spline.points.add(len(item['points'])-1)
                spline.use_cyclic_u=item['closed']
                for point,co in zip(spline.points,item['points']):point.co=(*co,1)
    else:
        for item in plan["curves"]:
            if item["category"] in categories:make_curve(item)
    for item in plan["surfaces"]:
        if item["category"] in categories:surface(item,plan)
    if plan.get('detail_upgrade'):flush_surfaces(plan)
    bead_mesh=bpy.data.meshes.get("SharedMilgrain")
    if bead_mesh is None:
        bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,radius=1)
        obj=bpy.context.object;bead_mesh=obj.data;bead_mesh.name="SharedMilgrain";bead_mesh.use_fake_user=True
        bpy.data.objects.remove(obj,do_unlink=True);bead_mesh.materials.append(bpy.data.materials["gold"])
        for p in bead_mesh.polygons:p.use_smooth=True
    for i,item in enumerate(plan["beads"]):
        if item["category"] not in categories:continue
        obj=bpy.data.objects.new(f"Milgrain_{i:04d}",bead_mesh);link(obj,item["category"].title())
        obj.location=item["position"];obj.scale=(item["radius"],)*3;obj["category"]=item["category"]

def evaluate_motifs(definitions):
    result={}
    for role,payload in definitions.items():
        payload=validate_curve(payload)
        data=bpy.data.curves.new("Definition_"+role,"CURVE");data.dimensions="3D";data.bevel_depth=.004;data.bevel_resolution=2
        s=data.splines.new("BEZIER");s.bezier_points.add(len(payload["points"])-1);s.use_cyclic_u=payload["cyclic"]
        for p,co in zip(s.bezier_points,payload["points"]):
            p.co=co["co"];p.handle_left_type=p.handle_right_type="FREE";p.handle_left=co["left"];p.handle_right=co["right"]
        obj=bpy.data.objects.new("Definition_"+role,data);link(obj,"Canonical_Motif_Library")
        bpy.context.view_layer.update();ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
        count=len(mesh.vertices);ev.to_mesh_clear()
        result[role]={"passed":count>0,"vertices":count,"canonical_hash":content_hash(payload)}
        obj.hide_render=True;obj.hide_set(True)
    return result

def repair_unsupported_fillers(plan):
    """One bounded repair pass: discard tertiary motifs unsupported by pierced shell."""
    if plan.get('detail_upgrade'):
        # Compound fronds intentionally bridge small lace openings; moving individual
        # midribs would separate them from their batch of carved leaf surfaces.
        bpy.context.scene['filler_support_repairs']='[]'
        return []
    bpy.context.view_layer.update()
    shell_obj=bpy.data.objects["Base_Shell"].evaluated_get(bpy.context.evaluated_depsgraph_get())
    rejected=set();r=plan["radius"];groups={};repairs=[]
    for obj in list(bpy.context.scene.objects):
        if obj.get("category")=="filler":
            groups.setdefault(obj.name.removesuffix("_edge").removesuffix("_vein"),[]).append(obj)
    def supported(points):
        limit=math.sqrt(1-(plan["opening_ratio"]+.065)**2)
        for p in points:
            n=p.normalized()
            if max(abs(c) for c in n)>limit:return False
            hit,*_=shell_obj.ray_cast(n*(r+.12*r),-n,distance=.25*r)
            if not hit:return False
        return True
    for name,objects in sorted(groups.items()):
        points=[]
        for obj in objects:
            if obj.type=="CURVE":
                samples=[Vector(p.co[:3]) for spline in obj.data.splines for p in spline.points]
                points.extend(samples[::max(1,len(samples)//20)])
        if not points or supported(points):continue
        axis=Vector(max(AXES,key=lambda axis:Vector(axis).dot(points[0])))
        for angle in (.10,-.10,.20,-.20,.30,-.30):
            rotation=Quaternion(axis,angle)
            if supported([rotation @ p for p in points]):
                for obj in objects:obj.rotation_mode="QUATERNION";obj.rotation_quaternion=rotation
                repairs.append({"motif":name,"action":"rotate_to_supported_shell","radians":angle});break
        else:rejected.add(name)
    removed=[]
    for obj in list(bpy.context.scene.objects):
        if obj.get("category")=="filler" and obj.name.removesuffix("_edge").removesuffix("_vein") in rejected:
            removed.append(obj.name);bpy.data.objects.remove(obj,do_unlink=True)
    repairs.extend({"object":name,"action":"delete_unsupported_filler"} for name in sorted(removed))
    bpy.context.scene["filler_support_repairs"]=json.dumps(repairs)
    return removed

def camera(view,plan,angle=None):
    r=plan["radius"];obj=bpy.context.scene.camera;target=Vector((0,0,-.04*r))
    positions={"hero":(3.3,-4.3,2.7),"front":(0,-5.7,.05),"side":(5.7,0,.05),"top":(.001,0,5.7),
               "detail_01":(1.85,-2.3,1.75),"detail_02":(.0,-3.1,.35)}
    if plan.get('detail_upgrade'):positions['hero']=(2.9,-3.7,2.5)
    if angle is not None:pos=(5.1*math.sin(angle),-5.1*math.cos(angle),2.5)
    else:pos=positions.get(view,positions["hero"])
    obj.location=Vector(pos)*r
    if view=="detail_01":target=Vector((.50,-.58,.45))*r
    if view=="detail_02":target=Vector((0,-.9,0))*r
    obj.rotation_euler=(target-obj.location).to_track_quat("-Z","Y").to_euler()
    obj.data.type="ORTHO" if view in ("front","side","top") else "PERSP"
    obj.data.ortho_scale=2.45*r;obj.data.lens=65

def render(path,view,plan,size=800,samples=24,angle=None):
    s=bpy.context.scene;camera(view,plan,angle);s.render.resolution_x=s.render.resolution_y=size
    if plan.get('detail_upgrade'):
        key=bpy.data.objects['Key'];key.location=Vector((-3.5,-4,5))*plan['radius']
        key.rotation_euler=(-key.location).to_track_quat('-Z','Y').to_euler()
        bpy.data.lights['Fill'].energy=340*plan['radius']**2
        s.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.14
    s.cycles.samples=samples;s.render.filepath=str(path);Path(path).parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.render.render(write_still=True)

def qa(plan,stage):
    bpy.context.view_layer.update();r=plan["radius"];objects=list(bpy.context.scene.objects)
    ornaments=[o for o in objects if o.get("category") in ("primary","secondary","filler")]
    shell_obj=bpy.data.objects.get("Base_Shell")
    result={"stage":stage,"sphere_exists":shell_obj is not None,"curve_count":sum(o.get('curve_count',1) for o in objects if o.type=="CURVE" and not o.name.startswith("Definition_")),
            "motif_instances":sum(o.get('surface_count',o.get('curve_count',1)) for o in ornaments),"emboss_surfaces":sum(o.get('surface_count',1) for o in ornaments if o.type=="MESH" and o.get("motif_role")),
            "border_objects":sum(o.get('curve_count',1) for o in objects if o.get("category")=="border"),
            "opening_count":shell_obj.get("opening_count",0) if shell_obj else 0,
            "cutout_windows":shell_obj.get("pierced_windows",0) if shell_obj else 0}
    # Inspect actual control/mesh points in the generated objects against analytic sphere and aperture caps.
    violations=0;max_radius=0;min_radius=10*r;max_gap=0;max_burial=0;width=10*r
    for obj in ornaments:
        pts=[obj.matrix_world @ Vector(p.co[:3]) for s in obj.data.splines for p in s.points] if obj.type=="CURVE" else [obj.matrix_world @ v.co for v in obj.data.vertices]
        if not pts:continue
        radii=[p.length for p in pts];max_radius=max(max_radius,max(radii));min_radius=min(min_radius,min(radii))
        half=obj.get("width",.005*r)/2
        max_gap=max(max_gap,min(radii)-r-half);max_burial=max(max_burial,r-min(radii)-half)
        if obj.type=="CURVE":width=min(width,obj["width"])
        for p in pts:
            if p.length and max(abs(x) for x in p.normalized())>math.sqrt(1-(plan["opening_ratio"]+.012)**2):violations+=1
    result.update(exclusion_violations=violations,maximum_radius=max_radius,minimum_radius=min_radius if ornaments else 0,
                  maximum_attachment_gap=max(0,max_gap),maximum_burial=max(0,max_burial),minimum_feature_width=width if ornaments else 0,
                  wall_thickness=plan["wall_thickness"],motif_roles=sorted({o.get("motif_role") for o in ornaments if o.get("motif_role")}))
    if shell_obj and stage>=2:
        ev=shell_obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
        radial=[v.co.length for v in mesh.vertices]
        result["measured_wall_radial_span"]=max(radial)-min(radial)
        result["shell_vertices"]=len(mesh.vertices)
        # Real opening rays: point from exterior towards interior through each axial oculus.
        holes=0
        for normal in AXES:
            n=Vector(normal);hit,*_=ev.ray_cast(n*(r*1.3),-n,distance=r*.5)
            holes+=not hit
        result["ray_verified_openings"]=holes
        ev.to_mesh_clear()
    checks={"sphere":result["sphere_exists"]} if stage>=2 else {}
    if stage>=2:checks.update(six_openings=result.get("ray_verified_openings")==6,wall=result["measured_wall_radial_span"]>=plan["wall_thickness"]*.9)
    if stage>=3:checks["borders"]=result["border_objects"]>=12
    if stage>=6:checks.update(complexity=result["motif_instances"]>=400,variety=len(result["motif_roles"])>=8,
                              cutout=result["cutout_windows"]>=100,exclusion=violations==0,
                              conformity=max_gap<.045*r and max_burial<.02*r,bounds=max_radius<1.15*r,
                              feature=width>=plan["minimum_feature_width"]*.99)
    result["filler_support_repairs"]=json.loads(bpy.context.scene.get("filler_support_repairs","[]"))
    result["checks"]=checks;result["final_pass"]=all(checks.values()) if checks else None
    return result

def geometry_fingerprint():
    """Measure generated Blender data, ignoring timestamps, materials and studio objects."""
    bpy.context.view_layer.update();objects={}
    for obj in sorted(bpy.context.scene.objects,key=lambda o:o.name):
        if obj.name!="Base_Shell" and not obj.get("category"):continue
        digest=hashlib.sha256()
        digest.update(obj.name.encode())
        for row in obj.matrix_world:digest.update(struct.pack("<4f",*row))
        if obj.type=="CURVE":
            digest.update(struct.pack("<f",obj.data.bevel_depth))
            for spline in obj.data.splines:
                for point in spline.points:digest.update(struct.pack("<4f",*point.co))
        elif obj.type=="MESH":
            ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get()) if obj.name=="Base_Shell" else None
            mesh=ev.to_mesh() if ev else obj.data
            for vertex in mesh.vertices:digest.update(struct.pack("<3f",*vertex.co))
            # Blender may reorder primitive faces between sessions; preserve winding and
            # connectivity while excluding this non-geometric storage order.
            for face in sorted(tuple(p.vertices) for p in mesh.polygons):
                digest.update(struct.pack("<I",len(face)))
                digest.update(struct.pack("<"+"I"*len(face),*face))
            if ev:ev.to_mesh_clear()
        objects[obj.name]=digest.hexdigest()
    return {"hash":hashlib.sha256(json.dumps(objects,sort_keys=True).encode()).hexdigest(),"objects":objects}

def main(job):
    root=Path(job["run_directory"]);out=Path(job["output_directory"])
    plan=json.loads((root/"build_plan.json").read_text(encoding="utf-8"));stage=job["stage"];op=job["requested_operation"]
    definitions=json.loads((root/"motif_definitions.json").read_text(encoding="utf-8"))
    if job.get("input_checkpoint"):
        bpy.ops.wm.open_mainfile(filepath=job["input_checkpoint"],load_ui=False,use_scripts=False)
        if bpy.context.scene.get("showcase_plan_hash")!=plan["plan_hash"]:raise ValueError("Plan identity mismatch")
    else:initialize(plan)
    bpy.context.preferences.filepaths.save_version=0
    artifacts=[]
    if op=="build_stage":
        if stage==2:
            shell(plan,False);render(root/"stages/01_base.png","hero",plan,640,16)
            shell(plan,True);render(root/"stages/02_openings.png","hero",plan,640,16)
        elif stage==3:
            definition_qa=evaluate_motifs(definitions)
            bpy.context.scene["motif_definition_qa"]=json.dumps(definition_qa)
            populate(plan,{"border"});render(root/"stages/03_borders.png","hero",plan,640,16)
        elif stage==4:
            populate(plan,{"primary"});render(root/"stages/04_primary_vines.png","hero",plan,640,16)
        elif stage==5:
            populate(plan,{"secondary"});render(root/"stages/05_secondary_motifs.png","hero",plan,640,16)
        elif stage==6:
            populate(plan,{"filler"});render(root/"stages/06_dense_pattern.png","hero",plan,640,16)
            shell(plan,True,True);repair_unsupported_fillers(plan)
            render(root/"stages/07_cutout.png","hero",plan,640,16)
        elif stage==8:
            render(root/"stages/08_final.png","hero",plan,900,32)
        bpy.context.scene["showcase_stage"]=stage
        camera("hero",plan)
        bpy.ops.wm.save_as_mainfile(filepath=job["checkpoint_path"],check_existing=False);artifacts.append(job["checkpoint_path"])
    elif op=="render":
        view="hero";path=out/"validation.png";render(path,view,plan,640,16);artifacts.append(str(path))
    elif op=="final_render":
        for view in ("hero","front","side","top","detail_01","detail_02"):
            path=root/"renders"/(view+".png")
            size=(1800 if view=='hero' else 1600 if view.startswith('detail') else 1200) if plan.get('detail_upgrade') else (1400 if view=='hero' else 1100)
            samples=(80 if view=='hero' else 64 if view.startswith('detail') else 40) if plan.get('detail_upgrade') else (64 if view=='hero' else 40)
            render(path,view,plan,size,samples);artifacts.append(str(path))
        camera("hero",plan)
        bpy.ops.wm.save_as_mainfile(filepath=str(root/"editable_showcase.blend"),check_existing=False)
        bpy.ops.wm.save_as_mainfile(filepath=str(root/"final_showcase.blend"),check_existing=False)
        artifacts.extend([str(root/"editable_showcase.blend"),str(root/"final_showcase.blend")])
    elif op=="verify_determinism":
        before=geometry_fingerprint()
        initialize(plan);shell(plan,True,True)
        bpy.context.scene["motif_definition_qa"]=json.dumps(evaluate_motifs(definitions))
        populate(plan,{"primary","secondary","filler","border"})
        repair_unsupported_fillers(plan)
        after=geometry_fingerprint()
        evidence={"saved_geometry_hash":before["hash"],"fresh_build_geometry_hash":after["hash"],"equal":before==after,
                  "different_objects":[name for name in sorted(set(before["objects"])|set(after["objects"]))
                                       if before["objects"].get(name)!=after["objects"].get(name)],
                  "scope":"Blender curve controls, mesh vertices/faces, object transforms, evaluated shell topology; ignores polygon storage order"}
        write(root/"blender_determinism.json",evidence)
        artifacts.append(str(root/"blender_determinism.json"))
        if before!=after:raise ValueError("Fresh Blender reconstruction differs from saved showcase")
    elif op=="turntable":
        bpy.context.scene.render.use_persistent_data=True
        for i in range(job.get("frames",72)):
            path=root/"turntable"/f"frame_{i+1:04d}.png"
            if path.exists() and path.stat().st_size>10000:
                artifacts.append(str(path));continue
            render(path,"hero",plan,800,20,i*math.tau/job.get("frames",72));artifacts.append(str(path))
    elif op!="restore":raise ValueError("Unknown showcase operation")
    metrics=qa(plan,stage)
    metrics["motif_definition_qa"]=json.loads(bpy.context.scene.get("motif_definition_qa","{}"))
    return {"result_version":"1.0","success":True,"blender_version":bpy.app.version_string,
            "produced_artifacts":artifacts,"geometry_measurements":metrics,"warnings":["Showcase editable visual model; not print-ready certified"],"errors":[]}

if __name__=="__main__":
    args=sys.argv[sys.argv.index("--")+1:];workspace=Path(args[1]).resolve()
    path=contained(args[0],workspace);job=json.loads(path.read_text(encoding="utf-8"))
    root=contained(job["run_directory"],workspace)
    for key in ("output_directory","checkpoint_path","result_path"):
        contained(job[key],root)
    if job.get("input_checkpoint"):contained(job["input_checkpoint"],root)
    try:result=main(job)
    except Exception as exc:
        write(job["result_path"],{"result_version":"1.0","success":False,"blender_version":bpy.app.version_string,
              "produced_artifacts":[],"geometry_measurements":{},"warnings":[],"errors":[str(exc),traceback.format_exc()]})
        raise
    write(job["result_path"],result)
