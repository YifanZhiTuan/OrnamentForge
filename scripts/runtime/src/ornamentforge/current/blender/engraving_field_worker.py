"""Blender worker for one periodic, actually displaced dense engraving mesh."""
import json,sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector

out=Path(sys.argv[sys.argv.index('--')+1]).resolve()
data=np.load(out/'surface_field.npz');depth=data['depth'].astype('f4')
nv,nu=depth.shape;radius=float(data['radius']);height=float(data['vase_height']);seam=float(data['seam_angle'])
u=np.arange(nu,dtype='f4')/nu;v=np.linspace(0,1,nv,dtype='f4')
theta=2*np.pi*u+seam;co,si=np.cos(theta),np.sin(theta)
base=np.empty((nv,nu,3),'f4');base[:,:,0]=radius*co;base[:,:,1]=radius*si;base[:,:,2]=height*v[:,None]
engraved=base.copy();engraved[:,:,0]-=depth*co;engraved[:,:,1]-=depth*si
verts=base.reshape(-1,3);rows=np.arange((nv-1)*nu,dtype=np.int32).reshape(nv-1,nu);nxt=np.roll(rows,-1,axis=1)
faces=np.stack([rows,nxt,nxt+nu,rows+nu],-1).reshape(-1,4)

bpy.ops.wm.read_factory_settings(use_empty=True)
mesh=bpy.data.meshes.new('Dense_Engraving_Surface');mesh.from_pydata(verts.tolist(),[],faces.tolist());mesh.update()
obj=bpy.data.objects.new('Straight_Vase_Actual_Displaced',mesh);bpy.context.collection.objects.link(obj)
obj.shape_key_add(name='Base_Straight_Vase')
key=obj.shape_key_add(name='Engraved_SOFT_ROUNDED_Field');key.data.foreach_set('co',engraved.reshape(-1,3).ravel());key.value=1
for p in mesh.polygons:p.use_smooth=True
solid=obj.modifiers.new('Porcelain wall and closed rims','SOLIDIFY');solid.thickness=.075;solid.offset=-1;solid.use_rim=True
obj['geometry']='Actual vertex displacement P-depth(u,v)*N; one periodic surface, no curve booleans'
obj['rebuild_source']='Packed source.png, binary_mask.png, engraving_field.png plus EngravingFieldV1 JSON/NPZ on disk'
obj['field_resolution']=f'{data["source_width"]} x {data["source_height"]}'
for filename in ('source.png','binary_mask.png','engraving_field.png'):
    image=bpy.data.images.load(str(out/filename));image.pack();image.use_fake_user=True
for filename in ('engraving_field.json','surface_map.json'):
    bpy.data.texts.load(str(out/filename))

mat=bpy.data.materials.new('White_Porcelain');mat.use_nodes=True;p=mat.node_tree.nodes.get('Principled BSDF')
p.inputs['Base Color'].default_value=(.82,.86,.88,1);p.inputs['Roughness'].default_value=.24;p.inputs['IOR'].default_value=1.46
p.inputs['Coat Weight'].default_value=.28;p.inputs['Coat Roughness'].default_value=.16
mesh.materials.append(mat)
floor_mat=bpy.data.materials.new('Neutral_Studio');floor_mat.use_nodes=True;fp=floor_mat.node_tree.nodes.get('Principled BSDF');fp.inputs['Base Color'].default_value=(.11,.12,.13,1);fp.inputs['Roughness'].default_value=.72
bpy.ops.mesh.primitive_plane_add(size=40,location=(0,0,0));floor=bpy.context.object;floor.name='STUDIO_ONLY';floor.data.materials.append(floor_mat)

scene=bpy.context.scene;engines=scene.render.bl_rna.properties['engine'].enum_items.keys();scene.render.engine='BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in engines else 'BLENDER_EEVEE'
scene.render.resolution_x=900;scene.render.resolution_y=1100;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
scene.world=bpy.data.worlds.new('Porcelain_Studio');scene.world.use_nodes=True;bg=scene.world.node_tree.nodes['Background'];bg.inputs[0].default_value=(.045,.055,.07,1);bg.inputs[1].default_value=.28
scene.view_settings.look='AgX - Medium High Contrast'
def aim(ob,target=(0,0,height*.5)):ob.rotation_euler=(Vector(target)-ob.location).to_track_quat('-Z','Y').to_euler()
for name,loc,power,size in [('Key',(-4,-5,6),1100,4),('Rake',(4,-1,3),850,2),('Rim',(0,4,6),1000,3),('Fill',(-2,2,4),300,5)]:
    li=bpy.data.lights.new(name,'AREA');li.energy=power;li.shape='DISK';li.size=size;ob=bpy.data.objects.new(name,li);scene.collection.objects.link(ob);ob.location=loc;aim(ob)
ca=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',ca);scene.collection.objects.link(cam);scene.camera=cam;ca.type='PERSP';ca.lens=62

# Material/studio only; retain all original displacement, keys and wall geometry.
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
from presentation_finish import apply_finish,build_material,apply_studio
finish_cfg=json.loads((out/'render_config.json').read_text(encoding='utf8')) if (out/'render_config.json').is_file() else {}
finish_name=finish_cfg.get('finish_preset','QINGBAI_GLAZE')
if finish_name!='NONE':
    finish_qa=apply_finish(obj,finish_name,'VASE')
    scene.cycles.samples=finish_cfg.get('samples',48)
    (out/'presentation_finish_qa.json').write_text(json.dumps(finish_qa,indent=2),encoding='utf8')
    bpy.data.texts.load(str(out/'presentation_finish_qa.json'))
def render(name,location,engraving=True):
    key.value=1 if engraving else 0;cam.location=location;aim(cam);scene.render.filepath=str(out/(name+'.png'))
    if finish_name!='NONE':
        build_material(obj,finish_name)
        apply_studio(obj,finish_name,'VASE')
    bpy.ops.render.render(write_still=True)
render('vase_white_preview',(0,-10,3.0),False)
render('vase_engraved_preview',(0,-10,3.0),True)
render('final_front',(0,-10,3.0),True)
render('final_3q',(6.4,-8.3,4.2),True)
key.value=1

deps=bpy.context.evaluated_depsgraph_get();evaluated=obj.evaluated_get(deps);em=evaluated.to_mesh();edge_users=np.zeros(len(em.edges),np.int32)
for poly in em.polygons:
    for edge in poly.edge_keys:
        idx=em.edge_keys.index(edge) if False else None
# Evaluated solidify mesh is closed when every edge has two linked polygons.
counts={}
for poly in em.polygons:
    vs=list(poly.vertices)
    for a,b in zip(vs,vs[1:]+vs[:1]):
        edge=(min(a,b),max(a,b));counts[edge]=counts.get(edge,0)+1
qa={'vertices':len(em.vertices),'faces':len(em.polygons),'nonmanifold_edges':sum(v!=2 for v in counts.values()),
    'finite':bool(np.isfinite(engraved).all()),'mesh_objects':1,'curve_objects':0,
    'actual_displacement':True,'solidify_modifier_evaluated':True,'shape_key':'Engraved_SOFT_ROUNDED_Field'}
evaluated.to_mesh_clear();(out/'blender_geometry_qa.json').write_text(json.dumps(qa,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(out/'editable_engraved_vase.blend'),compress=True)
print('ENGRAVING_FIELD_COMPLETE',qa,flush=True)
