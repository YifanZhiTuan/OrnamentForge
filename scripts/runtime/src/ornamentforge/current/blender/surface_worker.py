"""Blender worker: actual geometry, editable role keys, closed contours, studio evidence."""
import bpy,json,sys
import numpy as np
from pathlib import Path
from mathutils import Vector
out=Path(sys.argv[sys.argv.index('--')+1]).resolve();d=np.load(out/'surface.npz')
cfg=json.loads((out/'render_config.json').read_text(encoding='utf8')) if (out/'render_config.json').is_file() else {}
bpy.ops.wm.read_factory_settings(use_empty=True)
base,normal,top=d['base'],d['normal'],d['top'];nr,na=top.shape[:2];n=nr*na;ring=float(d['inner_radius'])>0
bottom=base-.19*normal
verts=np.concatenate([top.reshape(-1,3),bottom.reshape(-1,3)])
i=np.arange((nr-1)*na).reshape(-1,na);j=np.roll(i,-1,axis=1)
quads=np.stack([i,i+na,j+na,j],-1).reshape(-1,4)
faces=np.concatenate([quads,quads[:,::-1]+n]).tolist()
a=np.arange(na)+(nr-1)*na;b=np.roll(a,-1)
faces+=np.stack([a,a+n,b+n,b],-1).tolist()
if ring:
    a=np.arange(na);b=np.roll(a,-1);faces+=np.stack([a,b,b+n,a+n],-1).tolist()
else:
    ct=len(verts);cb=ct+1;verts=np.concatenate([verts,[top[0].mean(0),bottom[0].mean(0)]])
    for k in range(na):faces.extend([(ct,k,(k+1)%na),(cb,n+(k+1)%na,n+k)])
mesh=bpy.data.meshes.new('Continuous_Master_Surface');mesh.from_pydata(verts.tolist(),[],faces);mesh.update();del faces
obj=bpy.data.objects.new(out.name,mesh);bpy.context.collection.objects.link(obj);bpy.context.view_layer.objects.active=obj;obj.select_set(True)
mesh.polygons.foreach_set('use_smooth',np.ones(len(mesh.polygons),bool))
host=verts.copy();host[:n]=base.reshape(-1,3)
if not ring:host[ct]=base[0].mean(0)
obj.shape_key_add(name='Host_continuous_base').data.foreach_set('co',host.astype('f4').ravel())
for role,field in zip(d['roles'],d['fields']):
    co=host.copy();co[:n]+=(field[...,None]*normal).reshape(-1,3)
    if not ring:co[ct]+=np.mean(field[0,:,None]*normal[0],axis=0)
    key=obj.shape_key_add(name=str(role));key.data.foreach_set('co',co.astype('f4').ravel());key.value=1
obj['Edit instructions']='Role shape keys adjust heights. Hidden closed curves are editable construction guides, not live drivers. Rebuild masks with the current planar pipeline for outline changes; transfer regenerates from the immutable master field.'
obj['No image texture']='Single connected real relief mesh; color is vertex attribute; no bump or displacement shader.'
rgb=d['rgb'].reshape(-1,3);rgb=np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)
rgba=np.ones((len(verts),4),np.float32);rgba[:,:3]=[.18,.12,.06];rgba[:n,:3]=rgb
if 'base_glaze_srgb' in cfg:
    glaze_rgb=np.array(cfg['base_glaze_srgb']);glaze_rgb=np.where(glaze_rgb<=.04045,glaze_rgb/12.92,((glaze_rgb+.055)/1.055)**2.4)
    rgba[n:,:3]=glaze_rgb
if not ring:rgba[ct,:3]=rgb[:na].mean(0)
attr=mesh.color_attributes.new(name='MasterPalette',type='FLOAT_COLOR',domain='POINT');attr.data.foreach_set('color',rgba.ravel())
def mat(name,color,rough=.35):
    m=bpy.data.materials.new(name);m.use_nodes=True;nodes=m.node_tree.nodes;nodes.clear();p=nodes.new('ShaderNodeBsdfPrincipled');o=nodes.new('ShaderNodeOutputMaterial');m.node_tree.links.new(p.outputs['BSDF'],o.inputs['Surface']);p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=rough;return m,p
color,p=mat('Glossy enamel and warm relief',(.5,.3,.1),.3);p.inputs['Coat Weight'].default_value=.3;p.inputs['Coat Roughness'].default_value=.22;p.inputs['Metallic'].default_value=.22
for name,value in cfg.get('material_inputs',{}).items():p.inputs[name].default_value=value
at=color.node_tree.nodes.new('ShaderNodeVertexColor');at.layer_name='MasterPalette';color.node_tree.links.new(at.outputs['Color'],p.inputs['Base Color'])
if cfg.get('product_studio'):
    color.name='Porcelain_Layer_A_B_C';at.label='Layer B — regional pigment / monochrome pooling';p.label='Layer C — unified clear glaze coat'
    base_node=color.node_tree.nodes.new('ShaderNodeRGB');base_node.label='Layer A — base glaze';base_node.outputs[0].default_value=(*glaze_rgb,1)
    coverage=np.zeros(len(verts),np.float32);coverage[:n]=(np.max(np.abs(rgb-glaze_rgb),axis=1)>.001)
    if not ring:coverage[ct]=coverage[:na].mean()
    ca_mask=mesh.attributes.new('PatternCoverage','FLOAT','POINT');ca_mask.data.foreach_set('value',coverage)
    mask=color.node_tree.nodes.new('ShaderNodeAttribute');mask.attribute_name='PatternCoverage'
    mix=color.node_tree.nodes.new('ShaderNodeMixRGB');mix.label='Base glaze + region decoration'
    color.node_tree.links.new(mask.outputs['Fac'],mix.inputs[0]);color.node_tree.links.new(base_node.outputs[0],mix.inputs[1]);color.node_tree.links.new(at.outputs['Color'],mix.inputs[2]);color.node_tree.links.new(mix.outputs[0],p.inputs['Base Color'])
clay,_=mat('Neutral ivory inspection',cfg.get('clay_color',(.58,.56,.52)),.55);mesh.materials.append(color)
guides=bpy.data.collections.new('EDITABLE_ROLE_CONTOURS_rebuild_required');bpy.context.scene.collection.children.link(guides)
for k,region in enumerate(json.loads((out/'editable_regions.json').read_text(encoding='utf8'))):
    cu=bpy.data.curves.new(f'{region["role"]}_{k}','CURVE');cu.dimensions='2D';sp=cu.splines.new('POLY');sp.points.add(len(region['points'])-1)
    for p,(x,y) in zip(sp.points,region['points']):p.co=(x,y,0,1)
    sp.use_cyclic_u=region.get('closed',True);ob=bpy.data.objects.new(cu.name,cu);guides.objects.link(ob)
guides.hide_render=True;guides.hide_viewport=True
for f in ['ArtPlan.json','AssemblyPlan.json','OrnamentSpec.json','references.json','transfer_qa.json']:bpy.data.texts.load(str(out/f))
mesh.validate();ei=np.empty(len(mesh.loops),np.int32);mesh.loops.foreach_get('edge_index',ei);counts=np.bincount(ei,minlength=len(mesh.edges))
qa={'vertices':len(verts),'faces':len(mesh.polygons),'nonmanifold_edges':int(np.count_nonzero(counts!=2)),'euler':len(mesh.vertices)-len(mesh.edges)+len(mesh.polygons),'finite':bool(np.isfinite(verts).all()),'ornament_objects':1,'topology':'closed periodic annulus' if ring else 'closed disc','manufacturing_ready':False}
(out/'geometry_qa.json').write_text(json.dumps(qa,indent=2),encoding='utf8')
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=cfg.get('samples',32);scene.cycles.use_denoising=True
scene.render.resolution_x=cfg.get('resolution',900);scene.render.resolution_y=scene.render.resolution_x;scene.render.resolution_percentage=100
scene.world=bpy.data.worlds.new('Studio');scene.world.use_nodes=True;bg=scene.world.node_tree.nodes.get('Background');bg.inputs[0].default_value=(.045,.05,.065,1);bg.inputs[1].default_value=.23
bg.inputs[1].default_value=cfg.get('world_strength',.23)
if cfg.get('product_studio'):bg.inputs[0].default_value=(.7,.73,.76,1)
scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast';scene.view_settings.exposure=-.1
floor,_=mat('Charcoal studio',(.018,.024,.03),.8);bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.205));bpy.context.object.data.materials.append(floor);bpy.context.object.name='STUDIO_ONLY'
if cfg.get('product_studio'):
    floor.name='Warm neutral product sweep';floor.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.24,.225,.205,1)
    scene.view_settings.look='AgX - Medium High Contrast';scene.view_settings.exposure=0
def aim(ob,target=(0,0,0)):ob.rotation_euler=(Vector(target)-ob.location).to_track_quat('-Z','Y').to_euler()
for name,loc,power,sx,sy in [('Key',(-4.8,-3,4.2),850,3.4,2.2),('Fill',(4,3,8),130,5,5),('Edge',(0,5,5),280,3,.8)]:
    li=bpy.data.lights.new(name,'AREA');li.energy=power;li.shape='RECTANGLE';li.size=sx;li.size_y=sy;ob=bpy.data.objects.new(name,li);scene.collection.objects.link(ob);ob.location=loc;aim(ob)
ca=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',ca);scene.collection.objects.link(cam);scene.camera=cam;ca.type='ORTHO';ca.ortho_scale=10.9

# Presentation only: monochrome engraving uses the versioned finish by default.
# Painted/relief roles and explicit NONE retain their reviewed materials.
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
from presentation_finish import apply_finish,apply_studio
engraved_roles=any('engrav' in str(role).lower() or str(role).startswith('NEG_') for role in d['roles'])
finish_name=cfg.get('finish_preset','QINGBAI_GLAZE' if engraved_roles else 'NONE')
finish_material=None
if finish_name!='NONE':
    finish_qa=apply_finish(obj,finish_name,'PLATE')
    finish_material=mesh.materials[0]
    (out/'presentation_finish_qa.json').write_text(json.dumps(finish_qa,indent=2),encoding='utf8')
    bpy.data.texts.load(str(out/'presentation_finish_qa.json'))
def render(name,white,location,target=(0,0,0),scale=10.9,lighting='standard'):
    key=bpy.data.objects['Key'];fill=bpy.data.objects['Fill'];edge=bpy.data.objects['Edge']
    key.location=(-4.8,-3,4.2);key.data.energy=850;fill.data.energy=130;edge.data.energy=280
    if lighting in ['left','right']:
        key.location=(-6 if lighting=='left' else 6,0,2.8);key.data.energy=760;fill.data.energy=65;edge.data.energy=100
    if cfg.get('product_studio'):
        key.location=(-5,-3,6);key.data.energy=950;key.data.size=4.2;key.data.size_y=3
        fill.location=(5,1,6);fill.data.energy=180;edge.location=(1,5,6);edge.data.energy=650;edge.data.size=4;edge.data.size_y=1.4
        if white:key.location=(-6,-1,3);key.data.energy=800;fill.data.energy=65;edge.data.energy=150
        aim(fill);aim(edge)
        ca.type='ORTHO' if white or abs(location[1])<.01 or scale<8 else 'PERSP';ca.lens=50
    aim(key);mesh.materials[0]=clay if white else (finish_material or color);cam.location=location;aim(cam,target);ca.ortho_scale=scale;scene.render.filepath=str(out/(name+'.png'))
    if finish_material:apply_studio(obj,finish_name,'PLATE')
    bpy.ops.render.render(write_still=True)
if 'views' in cfg:
    for view in cfg['views']:render(**view)
else:
    render('clay_front',True,(0,0,16));render('clay_3q',True,(0,-9,12));render('color_front',False,(0,0,16))
    if out.name.startswith('transfer'):render('color_3q',False,(0,-9,12))
bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
if cfg:
    # Open delivered project on a complete color view, not the last cropped detail.
    mesh.materials[0]=finish_material or color;cam.location=(0,-9,12);aim(cam);ca.ortho_scale=10.9
    key=bpy.data.objects['Key'];key.location=(-4.8,-3,4.2);key.data.energy=850;aim(key)
    bpy.data.objects['Fill'].data.energy=130;bpy.data.objects['Edge'].data.energy=280
    if cfg.get('product_studio'):
        cam.location=(0,-11,14);aim(cam);ca.type='PERSP';ca.lens=50
        key.location=(-5,-3,6);key.data.energy=950;aim(key)
        bpy.data.objects['Fill'].data.energy=180;bpy.data.objects['Edge'].data.energy=650
bpy.ops.wm.save_as_mainfile(filepath=str(out/cfg.get('blend_name','editable_'+out.name+'.blend')),compress=True)
print('CURRENT_SURFACE_COMPLETE',out.name,qa,flush=True)
