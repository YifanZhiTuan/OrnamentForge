"""Blender regression: same existing asset, generic vs named finishes; geometry locked.

blender --background --factory-startup input.blend --python this.py -- --object NAME --output NEW_DIR
"""
import argparse, hashlib, json, sys
from pathlib import Path
import bpy

sys.dont_write_bytecode=True
sys.path.insert(0, str(Path(__file__).parent/'runtime/src/ornamentforge/current/blender'))
from presentation_finish import apply_finish, apply_studio, geometry_fingerprint, preset_config, PREFIX

p=argparse.ArgumentParser();p.add_argument('--object',required=True);p.add_argument('--output',required=True)
args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(args.output).resolve()
if out.exists() and any(out.iterdir()):raise ValueError('Use a new empty test output directory')
out.mkdir(parents=True,exist_ok=True)
source=Path(bpy.data.filepath);source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
obj=bpy.data.objects[args.object];scene=bpy.context.scene
before=geometry_fingerprint(obj);original=[m for m in obj.data.materials]
scene.render.resolution_x=1000;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.cycles.samples=48
def render(name):
    scene.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True)
def rig_state():
    return [(o.name,list(o.location),list(o.rotation_euler),o.data.energy,o.data.size,o.data.size_y)
            for o in scene.objects if o.type=='LIGHT' and o.name.startswith(PREFIX) and not o.hide_render]
# Keep the source camera and the exact same studio in both A/B images.
apply_studio(obj,'QINGBAI_GLAZE','PLATE')
generic=bpy.data.materials.new('TEST_Generic_Porcelain');generic.use_nodes=True
bsdf=generic.node_tree.nodes.get('Principled BSDF')
bsdf.inputs['Base Color'].default_value=(.58,.70,.64,1)
bsdf.inputs['Roughness'].default_value=.28;bsdf.inputs['IOR'].default_value=1.46
bsdf.inputs['Coat Weight'].default_value=.24;bsdf.inputs['Coat Roughness'].default_value=.2
obj.data.materials[0]=generic;render('generic_porcelain')
qa={'source_sha256':source_hash,'geometry_before':before,'comparison':'Identical asset/camera/studio/AgX/exposure/samples; material only','presets':{}}
for name in ['QINGBAI_GLAZE','YINGQING_GLAZE']:
    report=apply_finish(obj,name,'PLATE');first_rig=rig_state()
    for host in ['VASE','CYLINDER','PLATE']:
        apply_studio(obj,name,host)
        assert geometry_fingerprint(obj)==before
    apply_finish(obj,name,'PLATE');assert rig_state()==first_rig
    assert geometry_fingerprint(obj)==before
    assert len(first_rig)==4
    tree=obj.data.materials[0].node_tree
    assert not any(n.bl_idname in {'ShaderNodeBump','ShaderNodeDisplacement'} for n in tree.nodes)
    output=next(n for n in tree.nodes if n.type=='OUTPUT_MATERIAL')
    assert not output.inputs['Displacement'].is_linked
    report['repeat_apply_stable']=True;report['host_rig_smoke']=['PLATE','VASE','CYLINDER']
    render(name)
    text=bpy.data.texts.get('Presentation_Finish.json') or bpy.data.texts.new('Presentation_Finish.json')
    text.clear();text.write(json.dumps(preset_config(name),indent=2))
    bpy.ops.wm.save_as_mainfile(filepath=str(out/(name+'.blend')),compress=True)
    qa['presets'][name]=report
assert hashlib.sha256(source.read_bytes()).hexdigest()==source_hash
bpy.ops.wm.open_mainfile(filepath=str(out/'QINGBAI_GLAZE.blend'))
assert geometry_fingerprint(bpy.data.objects[args.object])==before
assert bpy.data.texts.get('Presentation_Finish.json')
qa.update(status='PASS',source_file_unchanged=True,reopen_geometry_unchanged=True,visual_review='REQUIRED')
(out/'finish_test_qa.json').write_text(json.dumps(qa,indent=2),encoding='utf8')
print('PRESENTATION_FINISH_TEST_PASS',json.dumps(qa),flush=True)
