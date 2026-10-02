"""Replay the user's authoritative soft-cloud V5 shader and studio, shading only."""
import json
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector, Matrix

SOURCE=Path(__file__).with_name('soft_cloud_v5.json')

def replay(tree,record):
    tree.nodes.clear();created={}
    for row in record['nodes']:
        n=tree.nodes.new(row['type']);n.name=row['name'];n.label=row['label']
        for key,value in row['properties'].items():setattr(n,key,value)
        for socket in row['inputs']:
            i=socket['index']
            if i>=len(n.inputs) or n.inputs[i].name!=socket['name']:
                raise RuntimeError('HOLD: shader socket version mismatch; use Blender 5.1')
            n.inputs[i].default_value=socket['value']
        created[row['name']]=n
    for row in record['links']:
        tree.links.new(created[row['from_node']].outputs[row['from_socket']],created[row['to_node']].inputs[row['to_socket']])

def attributes(obj,key_names=None):
    mesh=obj.data;n=len(mesh.vertices);report={}
    refresh=bool(mesh.get('OF_V5_DerivedDepth',False))
    def put(name,value,kind='FLOAT'):
        at=mesh.attributes.get(name)
        if at and not (refresh and name in {'ActualEngravingDepth','GlazeCavitySpread'}):return
        if at is None:at=mesh.attributes.new(name,kind,'POINT')
        at.data.foreach_set('vector' if kind=='FLOAT_VECTOR' else 'value',np.asarray(value,'f4').ravel())
        report[name]='derived shading attribute only'
    if mesh.attributes.get('ActualEngravingDepth') and not refresh:
        depth=np.empty(n,'f4');mesh.attributes['ActualEngravingDepth'].data.foreach_get('value',depth)
    else:
        depth=np.zeros(n,'f4');used=[]
        if mesh.shape_keys:
            for key in mesh.shape_keys.key_blocks:
                selected=key.name in key_names if key_names is not None else ('engrav' in key.name.lower() or key.name.startswith('NEG_'))
                if not selected:continue
                used.append(key.name)
                a=np.empty(n*3,'f4');b=np.empty_like(a)
                key.data.foreach_get('co',a);key.relative_key.data.foreach_get('co',b)
                depth+=np.linalg.norm((a-b).reshape(-1,3),axis=1)*max(key.value,0)*(not key.mute)
        if not used:raise ValueError('HOLD: V5 requires measured engraving depth or named engraving keys')
        put('ActualEngravingDepth',depth)
        mesh['OF_V5_DerivedDepth']=True
    if not mesh.attributes.get('GlazeCavitySpread') or refresh:
        edges=np.empty(len(mesh.edges)*2,'i4');mesh.edges.foreach_get('vertices',edges);edges=edges.reshape(-1,2)
        a,b=edges.T;degree=np.bincount(edges.ravel(),minlength=n);spread=depth.astype(float)
        for _ in range(18):
            neighbors=np.bincount(a,weights=spread[b],minlength=n)+np.bincount(b,weights=spread[a],minlength=n)
            spread=.5*spread+.5*neighbors/np.maximum(degree,1)
        put('GlazeCavitySpread',spread)
    if not mesh.attributes.get('GlazeHostNormal'):
        # Derive base normals on a disposable copy, never write the approved mesh.
        temp=mesh.copy()
        try:
            if mesh.shape_keys:
                co=np.empty(n*3,'f4');mesh.shape_keys.reference_key.data.foreach_get('co',co)
                temp.vertices.foreach_set('co',co);temp.update()
            normals=np.empty(n*3,'f4');temp.vertices.foreach_get('normal',normals)
            put('GlazeHostNormal',normals,'FLOAT_VECTOR')
        finally:bpy.data.meshes.remove(temp)
    # Existing V5 rim zone is preserved. Other hosts use a neutral zone, not a plate-only formula.
    put('GlazeRimZone',np.zeros(n,'f4'))
    return report

def material(obj,name,key_names=None):
    source=json.loads(SOURCE.read_text(encoding='utf8'));report=attributes(obj,key_names)
    key='OF_FINISH_'+name+'__'+obj.name
    m=bpy.data.materials.get(key) or bpy.data.materials.new(key);m.use_nodes=True
    replay(m.node_tree,source['material'])
    # Both public names use the approved color until the user explicitly approves another palette.
    if obj.data.materials:obj.data.materials[0]=m
    else:obj.data.materials.append(m)
    m['finish_preset']=name;m['finish_version']='2.0.0';m['authoritative_source_sha256']=source['source_sha256']
    return {'basis':'authoritative V5 graph; existing or derived shading attributes','attributes_added':report}

def studio(obj,host):
    source=json.loads(SOURCE.read_text(encoding='utf8'));scene=bpy.context.scene
    span=max(obj.dimensions);scale=span/max(source['dimensions'])
    rotation=obj.matrix_world.to_quaternion().to_matrix()
    orientation=Matrix.Identity(3) if host=='PLATE' else Matrix(((1,0,0),(0,0,-1),(0,1,0)))
    frame=rotation@orientation
    center=obj.matrix_world.translation.copy()
    if host!='PLATE':center=sum((obj.matrix_world@Vector(v) for v in obj.bound_box),Vector())/8
    for o in scene.objects:
        if o.type=='LIGHT':o.hide_render=True
    for row in source['lights']:
        key='OF_FINISH_V5_'+row['name'];o=bpy.data.objects.get(key)
        if o is None:
            d=bpy.data.lights.new(key,row['type']);o=bpy.data.objects.new(key,d);scene.collection.objects.link(o)
        o.hide_render=False;o.location=center+frame@(Vector(row['location'])*scale)
        from mathutils import Euler
        o.rotation_euler=(frame@Euler(row['rotation']).to_matrix()).to_euler()
        for k in ['shape','color','specular_factor']:setattr(o.data,k,row[k])
        o.data.energy=row['energy']*scale*scale;o.data.size=row['size']*scale;o.data.size_y=row['size_y']*scale
    w=bpy.data.worlds.get('OF_FINISH_V5_World') or bpy.data.worlds.new('OF_FINISH_V5_World')
    scene.world=w;w.use_nodes=True;replay(w.node_tree,source['world'])
    for key,value in source['view'].items():setattr(scene.view_settings,key,value)
    scene.render.engine='CYCLES';scene.cycles.seed=20260926;scene.cycles.use_denoising=True
