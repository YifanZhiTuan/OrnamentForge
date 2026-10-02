"""Fixed Blender-owned procedural worker for current reference-led objects.

The host passes data, never executable code.  All builders share the same
semantic primitives and stage collections; object-specific functions only
express grammar adaptation.
"""
from __future__ import annotations

import json
import math
import sys
import traceback
from pathlib import Path

import bpy
from mathutils import Vector


ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
CONFIG = json.loads(Path(ARGS[0]).read_text(encoding="utf-8"))
OUT = Path(CONFIG["output_directory"]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
SEED = int(CONFIG["seed"])
FAMILY = CONFIG["object_family"]
PARAMS = CONFIG.get("geometry_parameters", {})
MATS = {}
COLLS = {}
ROOT = None


def material(name, color, metallic=0.0, roughness=.45, emission=None, emission_strength=0):
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    bs = mat.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value = color
    bs.inputs["Metallic"].default_value = metallic
    bs.inputs["Roughness"].default_value = roughness
    if emission:
        bs.inputs["Emission Color"].default_value = emission
        bs.inputs["Emission Strength"].default_value = emission_strength
    return mat


def initialize():
    global ROOT
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    engines = scene.render.bl_rna.properties["engine"].enum_items.keys()
    scene.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in engines else "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 720; scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"; scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    scene.render.image_settings.color_depth = "8"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.render.fps = 24
    scene.world = bpy.data.worlds.new("ArtDirectorWorld"); scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (.035, .045, .06, 1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = .25
    scene["ornamentforge_version"] = "OrnamentForge Current Fidelity"
    scene["seed"] = SEED; scene["object_family"] = FAMILY
    scene["intent_mode"] = CONFIG["intent_mode"]
    ROOT = bpy.data.objects.new("OF_CURRENT_EDITABLE_ROOT", None)
    scene.collection.objects.link(ROOT)
    for index, name in enumerate(("BASE", "MACRO", "MESO", "MICRO")):
        coll = bpy.data.collections.new(f"STAGE_{index}_{name}")
        scene.collection.children.link(coll); COLLS[name] = coll
    MATS.update({
        "jade": material("Deep Jade", (.035, .19, .15, 1), metallic=.18, roughness=.28),
        "bronze": material("Warm Bronze", (.52, .19, .045, 1), metallic=.72, roughness=.23),
        "gold": material("Pale Gold", (.82, .49, .12, 1), metallic=.8, roughness=.2),
        "ivory": material("Ivory", (.78, .72, .61, 1), roughness=.34),
        "cobalt": material("Cobalt", (.025, .14, .32, 1), metallic=.18, roughness=.26),
        "teal": material("Celadon Teal", (.05, .42, .38, 1), metallic=.12, roughness=.31),
        "coral": material("Coral Red", (.62, .09, .055, 1), metallic=.1, roughness=.38),
        "purple": material("Fidelity Purple", (.25, .012, .24, 1), roughness=.35),
        "green": material("Fidelity Green", (.34, .53, .27, 1), roughness=.4),
        "blue": material("Fidelity Blue", (.22, .42, .65, 1), roughness=.35),
        "light": material("Warm Inner Light", (.8, .38, .08, 1), roughness=.3,
                          emission=(1.0, .28, .06, 1), emission_strength=5),
    })
    scene["material_map"] = json.dumps({key: mat.name for key, mat in MATS.items()})
    scene["plan_hash"] = CONFIG["plan_hash"]
    bpy.context.preferences.filepaths.save_version = 0


def link(obj, name, stage="MACRO", mat="gold"):
    obj.name = name
    for coll in list(obj.users_collection): coll.objects.unlink(obj)
    COLLS[stage].objects.link(obj)
    obj.parent = ROOT
    if getattr(obj, "data", None) and hasattr(obj.data, "materials"):
        obj.data.materials.append(MATS[mat])
    obj["semantic_stage"] = stage
    return obj


def tube(name, points, radius=.08, stage="MACRO", mat="gold", cyclic=False, resolution=3):
    data = bpy.data.curves.new(name, "CURVE"); data.dimensions = "3D"
    data.resolution_u = 18; data.bevel_resolution = resolution; data.bevel_depth = radius
    data.use_fill_caps = True
    sp = data.splines.new("BEZIER"); sp.bezier_points.add(len(points)-1); sp.use_cyclic_u = cyclic
    for point, co in zip(sp.bezier_points, points):
        point.co = co; point.handle_left_type = point.handle_right_type = "AUTO"
    obj = bpy.data.objects.new(name, data)
    weld=obj.modifiers.new("Join coincident cap rims", "WELD");weld.merge_threshold=1e-6
    return link(obj, name, stage, mat)


def flat_shape(name, points, z=.2, depth=.06, stage="MACRO", mat="gold"):
    data = bpy.data.curves.new(name, "CURVE"); data.dimensions = "2D"; data.resolution_u = 12
    data.fill_mode = "BOTH"; data.extrude = depth; data.bevel_depth = .012; data.bevel_resolution = 2
    sp = data.splines.new("BEZIER"); sp.bezier_points.add(len(points)-1); sp.use_cyclic_u = True
    for point, co in zip(sp.bezier_points, points):
        point.co = (co[0], co[1], 0); point.handle_left_type = point.handle_right_type = "AUTO"
    obj = bpy.data.objects.new(name, data); obj.location.z = z
    return link(obj, name, stage, mat)


def ellipsoid(name, location, scale, stage="MACRO", mat="gold", segments=32):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=max(8, segments//2), radius=1,
                                        location=location)
    obj = bpy.context.object; obj.scale = scale
    for poly in obj.data.polygons: poly.use_smooth = True
    return link(obj, name, stage, mat)


def torus(name, major, minor, z=0, stage="BASE", mat="bronze"):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor,
                                    major_segments=128, minor_segments=12, location=(0,0,z))
    return link(bpy.context.object, name, stage, mat)


def annulus(name, outer, inner, depth=.22, z=0, stage="BASE", mat="purple", segments=192):
    verts=[]; faces=[]
    for zi in (-depth/2, depth/2):
        for r in (outer, inner):
            verts.extend((r*math.cos(math.tau*i/segments), r*math.sin(math.tau*i/segments), z+zi)
                         for i in range(segments))
    for i in range(segments):
        j=(i+1)%segments
        faces += [(i,j,segments+j,segments+i),
                  (2*segments+i,3*segments+i,3*segments+j,2*segments+j),
                  (segments+i,segments+j,3*segments+j,3*segments+i),
                  (i,2*segments+i,2*segments+j,j)]
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
    obj=bpy.data.objects.new(name,mesh)
    for p in mesh.polygons:p.use_smooth=True
    bevel=obj.modifiers.new("Craft bevel","BEVEL");bevel.width=.025;bevel.segments=3
    return link(obj,name,stage,mat)


def rosette(name, center, radius, petals=8, stage="MESO", mat="coral", z=.28, flatten=.08):
    cx,cy=center
    for i in range(petals):
        a=math.tau*i/petals; p=(cx+math.cos(a)*radius*.55,cy+math.sin(a)*radius*.55,z)
        ob=ellipsoid(f"{name}_Petal_{i:02d}",p,(radius*.46,radius*.20,flatten),stage,mat,20)
        ob.rotation_euler.z=a
    ellipsoid(name+"_Center",(cx,cy,z+.025),(radius*.28,radius*.28,flatten*1.15),stage,"gold",24)


def triangle(name, center, angle, size=.18, z=.27, stage="MICRO", mat="coral"):
    x,y=center; pts=[]
    for local in ((-.65,-.45),(.65,-.45),(0,.62)):
        c,s=math.cos(angle),math.sin(angle);lx,ly=local
        pts.append((x+size*(c*lx-s*ly),y+size*(s*lx+c*ly)))
    return flat_shape(name,pts,z,.035,stage,mat)


# ---------- MEDALLION / DRAGON ----------
def medallion_base():
    bpy.ops.mesh.primitive_cylinder_add(vertices=192, radius=5, depth=.34, location=(0,0,-.17))
    base=link(bpy.context.object,"Medallion_Base","BASE","jade")
    bevel=base.modifiers.new("Soft perimeter","BEVEL");bevel.width=.08;bevel.segments=4
    torus("Outer_Frame",4.72,.13,.04,"BASE","bronze")
    torus("Inner_Reveal",4.38,.045,.07,"BASE","gold")


DRAGON_SPINE=[(1.05,.25,.26),(1.50,1.02,.25),(.85,2.02,.24),(-.65,2.25,.23),
              (-2.05,1.38,.22),(-2.45,-.10,.21),(-1.72,-1.75,.20),(-.30,-2.58,.18),
              (1.42,-2.38,.16),(2.52,-1.18,.14),(2.73,.38,.11),(2.12,1.72,.075)]
if "spine" in PARAMS:
    DRAGON_SPINE = [(x,y,.26-.17*i/(len(PARAMS["spine"])-1)) for i,(x,y) in enumerate(PARAMS["spine"])]


def medallion_macro():
    # Layered body curves create one dominant mass and an intentional open center.
    spine=tube("Dragon_Primary_Spine",DRAGON_SPINE,PARAMS.get("body_width",.40),"MACRO","gold")
    for i,p in enumerate(spine.data.splines[0].bezier_points):
        p.radius=max(.04,1.2-(i/(len(DRAGON_SPINE)-1))**2*1.16)
    # Head is a connected angular silhouette; muzzle, open jaw and antlers
    # carry species identity at Macro scale.
    head=[(1.48,.18),(1.40,.65),(1.07,.91),(.66,.73),(.40,.44),
          (.03,.36),(-.28,.48),(-.53,.34),(-.49,.08),(-.10,.06),
          (.21,-.02),(.38,-.18),(.12,-.35),(-.27,-.29),(-.32,-.52),
          (.03,-.66),(.48,-.50),(.85,-.47),(1.22,-.18)]
    flat_shape("Dragon_Head_Plane",head,.40,.13,"MACRO","gold")
    tube("Dragon_Brow",[(.19,.45,.62),(.45,.58,.66),(.73,.65,.62)],.06,"MACRO","ivory")
    ellipsoid("Dragon_Focused_Eye",(.46,.40,.64),(.09,.065,.035),"MACRO","cobalt")
    for i,points in enumerate([
        [(1.18,.62,.53),(1.38,1.02,.53),(1.77,1.41,.49)],
        [(.86,.79,.53),(.93,1.13,.53),(.70,1.55,.49)],
        [(1.35,1.01,.53),(1.65,1.10,.52),(1.92,1.34,.49)],
    ]):tube(f"Dragon_Antler_{i}",points,.065,"MACRO","ivory")
    for i,points in enumerate([
        [(1.20,.40),(1.68,.45),(1.88,.68),(1.75,.04),(1.42,-.16)],
        [(1.05,-.21),(1.46,-.43),(1.59,-.21),(1.55,-.72),(1.19,-.63)],
    ]):flat_shape(f"Dragon_Mane_Mass_{i}",points,.34,.08,"MACRO","gold")
    tube("Dragon_Whisker_Flow",[(.02,.17,.62),(-.51,.08,.56),(-.77,.43,.50),(-.68,.78,.43)],.035,"MACRO","ivory")
    ellipsoid("Pearl",(-.83,-.72,.25),(.31,.31,.18),"MACRO","coral")
    limb_anchors=[]
    for fraction in (.26,.52,.76):
        index=round(fraction*(len(DRAGON_SPINE)-1))
        x,y,z=DRAGON_SPINE[index]
        limb_anchors.append(((x,y,z+.08),(x*.73,y*.73,z+.09)))
    for i,(start,end) in enumerate(limb_anchors):
        tube(f"Dragon_Arm_{i}",[start,((start[0]+end[0])/2+.12,(start[1]+end[1])/2,.36),end],.10,"MACRO","gold")
        for j in range(3):
            ex,ey,ez=end
            tube(f"Dragon_Digit_{i}_{j}",[(ex,ey,ez),(ex-.22+j*.16,ey+.22,ez),(ex-.25+j*.20,ey+.38,ez-.02)],.032,"MACRO","ivory")
    return
    # Head, muzzle, eye and horns are readable at thumbnail size.
    ellipsoid("Dragon_Head",(1.03,.22,.43),(.72,.54,.16),"MACRO","gold")
    ellipsoid("Dragon_Muzzle",(.48,-.12,.46),(.48,.25,.13),"MACRO","ivory")
    ellipsoid("Dragon_Eye",(.83,.39,.61),(.10,.10,.07),"MACRO","cobalt")
    tube("Horn_Upper",[(1.23,.55,.53),(1.43,.92,.59),(1.78,1.17,.56)],.085,"MACRO","ivory")
    tube("Horn_Rear",[(1.02,.64,.50),(.92,1.06,.55),(.62,1.34,.51)],.075,"MACRO","ivory")
    tube("Whisker",[(.60,.05,.51),(.10,.27,.48),(-.25,.08,.43),(-.40,-.30,.38)],.035,"MACRO","ivory")
    ellipsoid("Pearl",(-.83,-.72,.39),(.31,.31,.13),"MACRO","coral")


def cloud(name, cx, cy, angle=0, scale=1):
    pts=[]
    for i in range(12):
        t=i/11; x=-.9+1.8*t; y=.18*math.sin(t*math.tau*1.35)+.16*math.sin(t*math.tau*2.7)
        c,s=math.cos(angle),math.sin(angle);pts.append((cx+scale*(c*x-s*y),cy+scale*(s*x+c*y),.30))
    tube(name,pts,.09*scale,"MESO","teal")
    for off in (-.45,.08,.55):
        a=angle+off; ellipsoid(name+f"_Lobe_{off}",(cx+math.cos(a)*.35*scale,cy+math.sin(a)*.35*scale,.31),
                              (.23*scale,.16*scale,.07),"MESO","teal",20)


def medallion_meso():
    cloud("Cloud_Top",-1.45,3.05,.1,.9);cloud("Cloud_Left",-3.28,-.55,1.45,.78)
    cloud("Cloud_Bottom",.65,-3.35,-.1,.86);cloud("Cloud_Right",3.45,.25,1.7,.64)
    # Three limbs attach visibly to the spine, preventing sticker-like isolated claws.
    for i,(start,end) in enumerate([((-.4,1.92,.35),(-.95,1.05,.39)),((-1.92,-.75,.33),(-1.05,-1.2,.37)),
                                    ((1.55,-1.95,.30),(1.05,-1.13,.35))]):
        tube(f"Dragon_Limb_{i}",[start,end],.105,"MESO","gold")
        ex,ey,ez=end
        for j,a in enumerate((-.45,0,.45)):
            tube(f"Claw_{i}_{j}",[(ex,ey,ez),(ex+.22*math.cos(a),ey-.22*math.sin(a),ez+.02)],.032,"MESO","ivory")


def medallion_micro():
    for i in range(1,len(DRAGON_SPINE)-1):
        x,y,z=DRAGON_SPINE[i]
        for side in (-1,1):
            ellipsoid(f"Scale_{i:02d}_{side}",(x+side*.14,y,z+.19),(.12,.075,.035),"MICRO","cobalt",16)
    for i in range(36):
        a=math.tau*i/36;ellipsoid(f"PearlTrim_{i:02d}",(4.12*math.cos(a),4.12*math.sin(a),.23),
                                  (.055,.055,.035),"MICRO","gold",12)


# ---------- VASE / PHOENIX ----------
VASE_PROFILE=[(-4.0,.78),(-3.65,1.16),(-3.05,1.72),(-2.1,2.35),(-.8,2.63),(.65,2.55),
              (1.65,2.28),(2.45,1.72),(3.05,1.02),(3.55,.82),(4.0,.88)]


def vase_radius(z):
    for (z0,r0),(z1,r1) in zip(VASE_PROFILE,VASE_PROFILE[1:]):
        if z0<=z<=z1:
            t=(z-z0)/(z1-z0);return r0*(1-t)+r1*t
    return VASE_PROFILE[0][1] if z<VASE_PROFILE[0][0] else VASE_PROFILE[-1][1]


def vase_point(theta,z,offset=.05):
    theta=theta*PARAMS.get("theta_mirror",1)+PARAMS.get("theta_offset",0)
    z=z*PARAMS.get("vertical_scale",1)
    r=vase_radius(z)+offset;return (r*math.sin(theta),-r*math.cos(theta),z)


def vase_base():
    seg=160;verts=[];faces=[]
    for z,r in VASE_PROFILE:
        verts.extend((r*math.sin(math.tau*i/seg),-r*math.cos(math.tau*i/seg),z) for i in range(seg))
    for j in range(len(VASE_PROFILE)-1):
        for i in range(seg):faces.append((j*seg+i,j*seg+(i+1)%seg,(j+1)*seg+(i+1)%seg,(j+1)*seg+i))
    mesh=bpy.data.meshes.new("Vase_Surface");mesh.from_pydata(verts,[],faces);mesh.update()
    obj=bpy.data.objects.new("Vase_Surface",mesh)
    for p in mesh.polygons:p.use_smooth=True
    solid=obj.modifiers.new("Vessel wall","SOLIDIFY");solid.thickness=.13
    bevel=obj.modifiers.new("Soft lip","BEVEL");bevel.width=.035;bevel.segments=3
    link(obj,"Vase_Surface","BASE","cobalt")
    torus("Vase_Foot",.93,.13,-4.0,"BASE","gold")
    torus("Vase_Lip",.90,.11,4.0,"BASE","gold")


def vase_curve(name,samples,radius=.07,stage="MACRO",mat="gold"):
    return tube(name,[vase_point(t,z,.10) for t,z in samples],radius,stage,mat)


def vase_macro():
    body=vase_point(.13,.35,.12);ellipsoid("Phoenix_Body",body,(.42,.17,.61),"MACRO","gold")
    head=vase_point(-.22,1.31,.14);ellipsoid("Phoenix_Head",head,(.23,.12,.25),"MACRO","gold")
    neck=vase_curve("Phoenix_Neck",[(.13,.45),(-.02,.68),(-.12,.94),(-.22,1.31)],.115,"MACRO","gold")
    # Beak and crown define the hero before any feather lines.
    tube("Phoenix_Beak",[head,vase_point(-.42,1.29,.19)],.035,"MACRO","ivory")
    for i in range(3):
        vase_curve(f"Phoenix_Crown_{i}",[(-.22,1.48),(-.22+(i-1)*.08,1.92)],.045,"MACRO","coral")
    # Three distinct tail flows cross the side silhouette and reveal on turntable.
    for i,(dtheta,dz) in enumerate(((1.15,-2.35),(1.68,-2.75),(2.25,-3.1))):
        samples=[]
        for k in range(12):
            t=k/11;samples.append((.12+dtheta*t*PARAMS.get("tail_sweep",1), .15 + dz*t + .34*math.sin(t*math.pi)))
        surface_ribbon(f"Phoenix_Tail_Mass_{i}",samples,.12-i*.012,"MACRO",("coral" if i==1 else "gold"))
    # Wing and companion blooms are Macro masses, necessary before detail approval.
    for i in range(6):
        surface_ribbon(f"Phoenix_Wing_Mass_{i}",[(.08,.55),(.20+i*.07,1.08),(.30+i*.105,1.75-i*.13)],
                       .085,"MACRO","ivory" if i%2 else "gold")
    vase_rosette("Peony_Macro_Primary",PARAMS.get("flower_theta",-.52),-1.30,.61,9,"MACRO")
    vase_rosette("Peony_Macro_Secondary",-.14,-2.40,.38,7,"MACRO")
    flower_theta=PARAMS.get("flower_theta",-.52)
    vase_curve("Macro_Floral_Skeleton",[(-.14,-2.95),(-.14,-2.40),(flower_theta,-1.30),(flower_theta+.16,-.65)],.055,"MACRO","teal")


def surface_ribbon(name, samples, half_width, stage, mat):
    """Tapered raised ribbon in vessel coordinates, shared by wing/tail/leaf grammar."""
    # Linear sampling with smooth-shaded cross sections keeps conformance explicit.
    from mathutils import geometry
    points=[]
    for a,b in zip(samples,samples[1:]):
        for k in range(12):
            t=k/12;points.append((a[0]*(1-t)+b[0]*t,a[1]*(1-t)+b[1]*t))
    points.append(samples[-1]);verts=[];faces=[]
    for i,(theta,z) in enumerate(points):
        t=i/(len(points)-1);width=half_width*(.10+.90*math.sin(math.pi*t)**.7)
        for j in range(7):
            u=-1+2*j/6
            verts.append(vase_point(theta+width*u,z,.055+.085*(1-u*u)))
    for i in range(len(points)-1):
        for j in range(6):
            a=i*7+j;faces.append((a,a+1,a+8,a+7))
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
    obj=bpy.data.objects.new(name,mesh)
    for p in mesh.polygons:p.use_smooth=True
    solid=obj.modifiers.new("Ribbon thickness","SOLIDIFY");solid.thickness=.028
    return link(obj,name,stage,mat)


def vase_rosette(name,theta,z,r=.52,petals=9,stage="MESO"):
    # Broad overlapping cups grow from a common center, projected point by point
    # onto the vessel. This also respects mirrored composition coordinates.
    radius=vase_radius(z)
    for tier,(reach,count,offset) in enumerate(((1.,petals,0),(.68,max(5,petals-2),.37),(.37,5,.81))):
        for i in range(count):
            angle=math.tau*i/count+offset
            verts=[];faces=[];rows=12;cols=10
            for a in range(rows+1):
                t=a/rows
                length=r*reach*(.12+.88*t)
                width=r*reach*.48*(.10+.90*math.sin(math.pi*t*.91)**.65)
                for b in range(cols+1):
                    u=-1+2*b/cols
                    dx=math.cos(angle)*length-math.sin(angle)*width*u
                    dz=math.sin(angle)*length+math.cos(angle)*width*u
                    height=.06+tier*.035+.095*math.sin(math.pi*t)*(1-u*u)+.025*t*t
                    verts.append(vase_point(theta+dx/radius,z+dz,height))
            for a in range(rows):
                for b in range(cols):
                    q=a*(cols+1)+b;faces.append((q,q+1,q+cols+2,q+cols+1))
            title=f"{name}_Cup_{tier}_{i}"
            mesh=bpy.data.meshes.new(title);mesh.from_pydata(verts,[],faces);mesh.update()
            obj=bpy.data.objects.new(title,mesh)
            for poly in mesh.polygons:poly.use_smooth=True
            solid=obj.modifiers.new("Petal thickness","SOLIDIFY");solid.thickness=.028
            link(obj,title,stage,"coral" if tier<2 else "gold")


def vase_meso():
    # Wing fan uses nested arcs anchored into the body.
    for i in range(7):
        ang=-.50+i*.17;samples=[]
        for k in range(8):
            t=k/7;samples.append((ang*(.25+.75*t),.65+.95*t+.14*math.sin(t*math.pi)))
        vase_curve(f"Wing_Feather_{i}",samples,.065,"MESO",("teal" if i%2 else "ivory"))
    vase_rosette("Peony_Hero",-.62,-1.45,.64,10)
    vase_rosette("Peony_Companion",.48,-2.35,.46,8)
    branch=[(-.58,-2.35),(-.42,-1.8),(-.62,-1.45),(-.35,-.75),(-.10,-.25)]
    vase_curve("Peony_Branch",branch,.07,"MESO","teal")


def vase_micro():
    for i in range(28):
        theta=-.35+.7*(i%7)/6;z=.35+1.05*(i//7)/3
        ellipsoid(f"Wing_Scale_{i:02d}",vase_point(theta,z,.23),(.10,.045,.075),"MICRO","ivory",14)
    for i in range(18):
        theta=-.9+1.8*(i/17);z=-3.35+.22*math.sin(i*.9)
        ellipsoid(f"Foot_Band_{i:02d}",vase_point(theta,z,.16),(.09,.05,.16),"MICRO","gold",14)


# ---------- LAMPSHADE / CUTOUT ----------
def shade_radius(z): return 1.72 + (3.45-1.72)*((-z+3.0)/6.0)


def shade_point(theta,z,offset=0):
    r=shade_radius(z)+offset;return (r*math.sin(theta),-r*math.cos(theta),z)


def shade_base():
    torus("Shade_Top_Ring",1.72,.14,3.0,"BASE","bronze")
    torus("Shade_Bottom_Ring",3.45,.17,-3.0,"BASE","bronze")
    count=PARAMS.get("panel_count",8)
    for i in range(count):
        a=math.tau*i/count;tube(f"Structural_Rib_{i}",[shade_point(a,3.0),shade_point(a,-3.0)],.105,"BASE","bronze")
    # Validation uses the unlit network so apertures remain visible.


def shade_curve(name,samples,radius=.07,stage="MACRO",mat="gold"):
    return tube(name,[shade_point(t,z,.05) for t,z in samples],radius,stage,mat)


def shade_macro():
    count=PARAMS.get("panel_count",8)
    for panel in range(count):
        base=math.tau*panel/count
        samples=[]
        for k in range(13):
            t=k/12;z=-3+6*t;theta=base+PARAMS.get("vine_amplitude",.23)*math.sin(t*math.tau*PARAMS.get("vine_cycles",1)+(panel%2)*.7)
            samples.append((theta,z))
        shade_curve(f"Primary_Vine_{panel}",samples,.09,"MACRO",("gold" if panel%2==0 else "teal"))
        # One horizontal bridge at the widest lower third links each vine to the next rib.
        shade_curve(f"Bridge_{panel}",[(base,-1.85),(base+.22,-1.55),(base+math.tau/16,-1.42)],.065,"MACRO","bronze")
        for j,z in enumerate(PARAMS.get("bridge_levels",[-1.6,0,1.6])):
            side=-1 if j%2 else 1
            theta=base+.23*math.sin((z+3)/6*math.tau+(panel%2)*.7)
            endpoint=base+side*.35
            shade_curve(f"Macro_Branch_{panel}_{j}",[(theta,z-.28),(endpoint,z+.12),(base+side*math.tau/count,z+.25)],.055,"MACRO","gold")
            shade_leaf(f"Macro_Leaf_{panel}_{j}",endpoint,z+.12,.37,"MACRO","teal")


def shade_leaf(name,theta,z,scale=.28,stage="MESO",mat="teal"):
    p=shade_point(theta,z,.13)
    ob=ellipsoid(name,p,(scale,.09,scale*.48),stage,mat,18);ob.rotation_euler.z=theta
    return ob


def shade_meso():
    for panel in range(8):
        base=math.tau*panel/8
        for j,z in enumerate((-2.2,-.75,.75,2.05)):
            side=-1 if (j+panel)%2 else 1
            theta=base+side*.20
            shade_curve(f"Secondary_{panel}_{j}",[(base,z-.35),(theta,z),(base+side*.31,z+.22)],.045,"MESO","teal")
            shade_leaf(f"Leaf_{panel}_{j}",base+side*.31,z+.22,.25 if j!=2 else .31)
    # Three hero lotus rosettes remain sparse enough to preserve light apertures.
    for panel,z in ((0,.55),(7,-.25),(1,-1.15)):
        base=math.tau*panel/8
        center=shade_point(base,z,.18)
        for i in range(7):
            a=math.tau*i/7
            theta=base+math.cos(a)*.11;zz=z+math.sin(a)*.34
            shade_leaf(f"Lotus_{panel}_{i}",theta,zz,.28,"MESO","coral")
        ellipsoid(f"Lotus_{panel}_Center",center,(.18,.10,.18),"MESO","gold",18)


def shade_micro():
    for i in range(32):
        a=math.tau*i/32
        ellipsoid(f"Lower_Bead_{i:02d}",shade_point(a,-2.92,.08),(.07,.07,.07),"MICRO","gold",12)
    for panel in range(8):
        base=math.tau*panel/8
        shade_curve(f"Tendril_{panel}",[(base,1.35),(base+.15,1.58),(base+.03,1.84)],.026,"MICRO","ivory")


# ---------- EXACT RADIAL RECONSTRUCTION ----------
def exact_base():
    if CONFIG.get("reconstruction"):
        for i, region in enumerate(CONFIG["reconstruction"]["silhouette"]):
            reference_region(f"Measured_Base_{i}", region, "BASE", "bronze", -.08, .09)
        return
    annulus("Reference_Ring_Base",5.0,2.12,.28,0,"BASE","purple")
    torus("Outer_Blue_Seal",4.94,.09,.13,"BASE","cobalt")
    torus("Outer_White_Reveal",4.78,.055,.15,"BASE","ivory")
    torus("Inner_Gold_Seal",2.30,.12,.16,"BASE","gold")
    torus("Inner_White_Reveal",2.12,.045,.17,"BASE","ivory")


def exact_macro():
    if CONFIG.get("reconstruction"):
        for i, region in enumerate(CONFIG["reconstruction"]["regions"]):
            key = "ReferencePalette_" + str(region["palette_index"])
            if key not in MATS:
                def linear(c):
                    v=c/255
                    return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4
                MATS[key]=material(key,tuple(linear(c) for c in region["color"])+(1,),.12,.45)
            reference_region(f"Measured_Region_{i:04d}", region, "MACRO", key, .035, .025)
        return
    # Twelve large scroll cells preserve the reference's principal placement.
    for cell in range(12):
        a=math.tau*cell/12
        pts=[]
        for k in range(18):
            t=k/17;rr=3.72-.72*t;ang=a-.24+.95*t+1.25*t*t
            pts.append((rr*math.cos(ang),rr*math.sin(ang),.30))
        tube(f"Major_Scroll_{cell:02d}",pts,.115,"MACRO","blue")
        # Mirrored inner curl makes each cell a paired, closed visual unit.
        pts2=[]
        for k in range(12):
            t=k/11;rr=3.25-.43*t;ang=a+.22-.72*t-.75*t*t
            pts2.append((rr*math.cos(ang),rr*math.sin(ang),.31))
        tube(f"Counter_Scroll_{cell:02d}",pts2,.075,"MACRO","blue")


def exact_meso():
    for i in range(12):
        a=math.tau*i/12
        rosette(f"Outer_Flower_{i:02d}",(3.93*math.cos(a),3.93*math.sin(a)),.29,6,"MESO",
                "coral" if i%2 else "green",.31,.045)
    for i in range(16):
        a=math.tau*i/16
        rosette(f"Inner_Flower_{i:02d}",(2.55*math.cos(a),2.55*math.sin(a)),.12,5,"MESO","ivory",.32,.028)
    for i in range(24):
        a=math.tau*i/24
        ellipsoid(f"Leaf_Accent_{i:02d}",(3.48*math.cos(a),3.48*math.sin(a),.33),(.13,.07,.035),
                  "MESO","green",14).rotation_euler.z=a


def exact_micro():
    for i in range(64):
        a=math.tau*i/64;triangle(f"Zigzag_{i:02d}",(4.60*math.cos(a),4.60*math.sin(a)),a+math.pi/2,.20,.32,"MICRO","coral")
    for i in range(48):
        a=math.tau*i/48
        ellipsoid(f"Fine_Bead_{i:02d}",(2.82*math.cos(a),2.82*math.sin(a),.335),(.032,.032,.018),"MICRO","gold",10)


BUILDERS={
    "MEDALLION": (medallion_base,medallion_macro,medallion_meso,medallion_micro),
    "VASE": (vase_base,vase_macro,vase_meso,vase_micro),
    "LAMPSHADE": (shade_base,shade_macro,shade_meso,shade_micro),
    "EXACT_MEDALLION": (exact_base,exact_macro,exact_meso,exact_micro),
}


def reference_region(name, region, stage, mat, z, depth):
    data=bpy.data.curves.new(name,"CURVE");data.dimensions="2D";data.fill_mode="BOTH"
    data.extrude=depth;data.resolution_u=1
    for ring in region["rings"]:
        spline=data.splines.new("POLY");spline.points.add(len(ring)-1);spline.use_cyclic_u=True
        for point,xy in zip(spline.points,ring):point.co=(*xy,0,1)
    obj=bpy.data.objects.new(name,data);obj.location.z=z
    return link(obj,name,stage,mat)


def look_at(obj,target): obj.rotation_euler=(Vector(target)-obj.location).to_track_quat("-Z","Y").to_euler()


def light(name,location,energy,size,color=(1,1,1)):
    data=bpy.data.lights.new(name,"AREA");data.energy=energy;data.shape="DISK";data.size=size;data.color=color
    obj=bpy.data.objects.new(name,data);bpy.context.scene.collection.objects.link(obj);obj.location=location;look_at(obj,(0,0,0));return obj


def studio():
    scene=bpy.context.scene
    light("Key",(-6,-8,10),1150,5.5,(1,.76,.55));light("Fill",(7,-3,6),800,6.5,(.45,.65,1))
    light("Rim",(2,7,8),980,4,(.55,.72,1))
    cams={}
    if FAMILY in ("MEDALLION","EXACT_MEDALLION"):
        setups={"hero_front":((0,0,15),(0,0,0),"ORTHO",11.2),
                "hero_3q":((8,-9,12),(0,0,0),"PERSP",55),
                "detail_closeup":((3.8,-5.7,8.5),(1.0,.1,.25),"PERSP",35)}
    elif FAMILY=="VASE":
        setups={"hero_front":((0,-16,1),(0,0,.1),"PERSP",52),
                "hero_3q":((10,-13,3),(0,0,.1),"PERSP",52),
                "detail_closeup":((4,-10,2.2),(0,-1.4,.1),"PERSP",38)}
    else:
        setups={"hero_front":((0,-15,.5),(0,0,0),"PERSP",52),
                "hero_3q":((10,-12,3),(0,0,0),"PERSP",52),
                "detail_closeup":((4,-9,1),(0,-2,.2),"PERSP",36)}
    for name,(pos,target,kind,value) in setups.items():
        data=bpy.data.cameras.new("Camera_"+name);obj=bpy.data.objects.new(data.name,data)
        scene.collection.objects.link(obj);obj.location=pos;look_at(obj,target);data.type=kind
        if kind=="ORTHO":data.ortho_scale=value
        else:data.lens=value
        cams[name]=obj
    return cams


def set_stage(maximum):
    names=("BASE","MACRO","MESO","MICRO")
    for i,name in enumerate(names):COLLS[name].hide_render=i>maximum;COLLS[name].hide_viewport=False


def render(path,camera,resolution=720):
    scene=bpy.context.scene;scene.camera=camera;scene.render.resolution_x=resolution;scene.render.resolution_y=resolution
    scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)


def save(path): bpy.ops.wm.save_as_mainfile(filepath=str(path),check_existing=False)


def geometry_audit():
    """Measure evaluated objects. Topology alone cannot certify their unions."""
    import bmesh
    import hashlib
    deps=bpy.context.evaluated_depsgraph_get();rows=[];snapshot=[]
    for obj in sorted((o for o in bpy.data.objects if o.parent==ROOT and o.type in ("MESH","CURVE")),key=lambda o:o.name):
        evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh()
        bm=bmesh.new();bm.from_mesh(mesh)
        boundary=sum(1 for e in bm.edges if e.is_boundary)
        nonmanifold=sum(1 for e in bm.edges if not e.is_manifold)
        # Blender curve caps can duplicate rim vertices. Diagnose coincident
        # seams on a temporary audit copy; never silently alter editable assets.
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6)
        welded_nonmanifold=sum(1 for e in bm.edges if not e.is_manifold)
        finite=all(math.isfinite(c) for v in mesh.vertices for c in v.co)
        coordinates=[[round(c,6) for c in (obj.matrix_world@v.co)] for v in mesh.vertices]
        snapshot.append({"name":obj.name,"vertices":coordinates,"faces":[list(p.vertices) for p in mesh.polygons]})
        rows.append({"object":obj.name,"vertices":len(mesh.vertices),"faces":len(mesh.polygons),
                     "boundary_edges":boundary,"nonmanifold_edges":nonmanifold,
                     "nonmanifold_after_coincident_weld":welded_nonmanifold,"finite":finite})
        bm.free();evaluated.to_mesh_clear()
    fingerprint=hashlib.sha256(json.dumps(snapshot,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return {"evaluated_objects":rows,"geometry_sha256":fingerprint,
            "finite_coordinates":all(r["finite"] for r in rows),
            "nonempty_objects":all(r["vertices"] and r["faces"] for r in rows),
            "sum_nonmanifold_edges":sum(r["nonmanifold_edges"] for r in rows),
            "union_connectivity":None,"minimum_wall_thickness":None,"surface_penetration":None,
            "final_pass":False,"status":"HOLD",
            "limitations":["Object-level topology does not certify assembled intersections or connectivity",
                           "Wall thickness and conformance require separate measurements"]}


def checkpoints(stage_index):
    set_stage(stage_index)


def build_macro():
    phase = CONFIG.get("phase", "macro")
    if phase != "macro":
        raise ValueError("Downstream execution is disabled until evidence-bound stage approval is implemented")
    if CONFIG["intent_mode"] == "MODE_C_REFERENCE_EXACT" and not CONFIG.get("reconstruction"):
        raise ValueError("Reference-derived geometry required; preset ring is not an exact reconstruction")
    builder_key="EXACT_MEDALLION" if CONFIG["intent_mode"]=="MODE_C_REFERENCE_EXACT" else FAMILY
    if builder_key not in BUILDERS:raise ValueError("No current Blender grammar executor for "+builder_key)
    base,macro,meso,micro=BUILDERS[builder_key]
    checkpoints_dir=OUT/"checkpoints";renders=OUT/"renders";steps=OUT/"process_steps"
    checkpoints_dir.mkdir(exist_ok=True);renders.mkdir(exist_ok=True);steps.mkdir(exist_ok=True)
    save(checkpoints_dir/"G00_intake.blend");save(checkpoints_dir/"G01_analysis.blend")
    base();set_stage(0);save(checkpoints_dir/"G02_base.blend")
    macro();set_stage(1);save(checkpoints_dir/"G03_motif.blend")
    cams=studio();render(steps/"01_macro.png",cams["hero_front"],600)
    save(checkpoints_dir/"G04_layout.blend")
    for name in ("hero_front", "hero_3q"):
        render(renders/(name+".png"), cams[name], 720)
    render(renders/"thumbnail_160.png", cams["hero_front"], 160)
    gray=material("Validation Clay",(.40,.40,.40,1),0,.8)
    bpy.context.view_layer.material_override=gray
    render(renders/"gray_front.png",cams["hero_front"],720)
    bpy.context.view_layer.material_override=None
    audit=geometry_audit()
    (OUT/"geometry_qa.json").write_text(json.dumps(audit,indent=2),encoding="utf-8")
    save(OUT/"macro.blend")
    return {"success": True, "phase": "macro", "gate": "HOLD", "reason": "Visual review pending",
            "blender_version": bpy.app.version_string,
            "artifacts": {"checkpoint": str(OUT/"macro.blend"), "hero_front": str(renders/"hero_front.png"),
                          "hero_3q": str(renders/"hero_3q.png"), "thumbnail_160": str(renders/"thumbnail_160.png"),
                          "gray_front":str(renders/"gray_front.png")}}
    meso();set_stage(2);save(checkpoints_dir/"G05_conform.blend");render(steps/"02_meso.png",cams["hero_front"],600)
    micro();set_stage(3);save(checkpoints_dir/"G06_relief.blend");render(steps/"03_micro.png",cams["hero_front"],600)
    save(checkpoints_dir/"G07_qa.blend")
    final=OUT/"final.blend";save(final);save(checkpoints_dir/"G08_final.blend")
    for name in ("hero_front","hero_3q","detail_closeup"):
        render(renders/(name+".png"),cams[name],720)
    render(renders/"thumbnail_160.png",cams["hero_front"],160)
    if CONFIG["intent_mode"]=="MODE_C_REFERENCE_EXACT":
        render(renders/"fidelity_flat.png",cams["hero_front"],720)
    # Turntable: rotate editable root, not the studio.
    scene=bpy.context.scene;scene.camera=cams["hero_3q"];scene.render.resolution_x=480;scene.render.resolution_y=480
    scene.frame_start=1;scene.frame_end=18
    ROOT.rotation_euler.z=0;ROOT.keyframe_insert("rotation_euler",frame=1,index=2)
    ROOT.rotation_euler.z=math.tau;ROOT.keyframe_insert("rotation_euler",frame=19,index=2)
    for curve in ROOT.animation_data.action.fcurves:
        for key in curve.keyframe_points:key.interpolation="LINEAR"
    scene.render.image_settings.file_format="FFMPEG";scene.render.ffmpeg.format="MPEG4"
    scene.render.ffmpeg.codec="H264";scene.render.ffmpeg.constant_rate_factor="MEDIUM"
    scene.render.filepath=str(OUT/"turntable.mp4");bpy.ops.render.render(animation=True)
    scene.render.image_settings.file_format="PNG";ROOT.rotation_euler.z=0
    objects=sum(1 for obj in bpy.data.objects if obj.parent==ROOT)
    curves=sum(1 for obj in bpy.data.objects if obj.parent==ROOT and obj.type=="CURVE")
    meshes=sum(1 for obj in bpy.data.objects if obj.parent==ROOT and obj.type=="MESH")
    return {"success":True,"blender_version":bpy.app.version_string,"family":FAMILY,
            "objects":objects,"curves":curves,"meshes":meshes,
            "artifacts":{"final_blend":str(final),"hero_front":str(renders/"hero_front.png"),
                         "hero_3q":str(renders/"hero_3q.png"),"detail_closeup":str(renders/"detail_closeup.png"),
                         "thumbnail_160":str(renders/"thumbnail_160.png"),
                         "turntable":str(OUT/"turntable.mp4"),"process_steps":str(steps)},
            "stage_counts":{"G0":0,"G1":0,"G2":1,"G3":2,"G4":2,"G5":3,"G6":4,"G7":4,"G8":4}}


def resume_phase():
    global ROOT
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from ornamentforge.current.qa.gates import verify_gate
    phase=CONFIG["phase"]
    predecessor={"meso":"macro", "micro":"meso"}.get(phase)
    if predecessor is None:
        raise ValueError("Only macro, meso and micro construction are supported")
    parent=Path(CONFIG["parent_run"]).resolve()
    receipt=verify_gate(parent,predecessor)
    if receipt["plan_hash"] != CONFIG["plan_hash"]:
        raise ValueError("Cannot resume a different design")
    bpy.ops.wm.open_mainfile(filepath=str(parent/receipt["checkpoint"]),load_ui=False)
    ROOT=bpy.data.objects["OF_CURRENT_EDITABLE_ROOT"]
    for index,name in enumerate(("BASE","MACRO","MESO","MICRO")):
        COLLS[name]=bpy.data.collections[f"STAGE_{index}_{name}"]
    if "material_map" not in bpy.context.scene:
        raise ValueError("Checkpoint lacks material identity; rebuild macro with current worker")
    for key,name in json.loads(bpy.context.scene["material_map"]).items():
        MATS[key]=bpy.data.materials[name]
    key="EXACT_MEDALLION" if CONFIG["intent_mode"]=="MODE_C_REFERENCE_EXACT" else FAMILY
    if key=="EXACT_MEDALLION":
        raise ValueError("Exact Meso requires constraint-preserving craft operations, not preset ornament additions")
    index={"meso":2,"micro":3}[phase]
    BUILDERS[key][index]();set_stage(index)
    renders=OUT/"renders";renders.mkdir(exist_ok=True)
    checkpoint=OUT/(phase+".blend")
    save(checkpoint)
    artifacts={"checkpoint":str(checkpoint)}
    for name in ("hero_front","hero_3q","detail_closeup"):
        path=renders/(name+".png")
        render(path,bpy.data.objects["Camera_"+name],720)
        artifacts[name]=str(path)
    thumb=renders/"thumbnail_160.png"
    render(thumb,bpy.data.objects["Camera_hero_front"],160)
    artifacts["thumbnail_160"]=str(thumb)
    return {"success":True,"phase":"meso" if phase=="meso" else "final",
            "construction_phase":phase,"gate":"HOLD","reason":"Visual and geometry review pending",
            "blender_version":bpy.app.version_string,"artifacts":artifacts}


try:
    if CONFIG.get("phase", "macro") == "macro":
        initialize(); result=build_macro()
    else:
        result=resume_phase()
except Exception as exc:
    result={"success":False,"error":str(exc),"traceback":traceback.format_exc(),"blender_version":bpy.app.version_string}
(OUT/"blender_result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
if not result["success"]:raise SystemExit(17)
