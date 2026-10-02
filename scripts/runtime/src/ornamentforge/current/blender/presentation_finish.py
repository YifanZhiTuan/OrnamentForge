"""Versioned ceramic presentation only. No geometry, normal or displacement edits.

Can be imported by Blender workers without importing the Python core dependencies.
"""
import hashlib
import json
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector

sys.dont_write_bytecode = True
DATA = Path(__file__).with_name('presentation_presets.json')
PREFIX = 'OF_FINISH_'
MODULE_DIR = str(Path(__file__).resolve().parent)
if MODULE_DIR not in sys.path:
    sys.path.insert(0, MODULE_DIR)


def preset_config(name='QINGBAI_GLAZE'):
    data = json.loads(DATA.read_text(encoding='utf8'))
    if name not in data['presets']:
        raise ValueError('Unknown presentation preset: ' + str(name))
    return dict(data['presets'][name], name=name, version=data['version'])


def geometry_fingerprint(obj):
    """Positions, connectivity, keys, transforms, modifiers and evaluated mesh."""
    digest = hashlib.sha256()
    def mesh_hash(mesh):
        for collection, prop, size, dtype in [(mesh.vertices, 'co', 3, 'f4'),
                (mesh.edges, 'vertices', 2, 'i4'), (mesh.loops, 'vertex_index', 1, 'i4'),
                (mesh.polygons, 'loop_total', 1, 'i4')]:
            values = np.empty(len(collection)*size, dtype=dtype)
            collection.foreach_get(prop, values); digest.update(values.tobytes())
    mesh_hash(obj.data)
    if obj.data.shape_keys:
        for key in obj.data.shape_keys.key_blocks:
            values = np.empty(len(key.data)*3, 'f4'); key.data.foreach_get('co', values)
            digest.update(values.tobytes())
            digest.update(repr((key.name, key.value, key.mute, key.relative_key.name)).encode())
    digest.update(repr([list(row) for row in obj.matrix_world]).encode())
    for modifier in obj.modifiers:
        state = {}
        for prop in modifier.bl_rna.properties:
            if prop.identifier == 'rna_type': continue
            value = getattr(modifier, prop.identifier, None)
            if isinstance(value, (bool, int, float, str)): state[prop.identifier] = value
        digest.update(json.dumps(state, sort_keys=True).encode())
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh(); mesh_hash(mesh); evaluated.to_mesh_clear()
    return digest.hexdigest()






def build_material(obj, name='QINGBAI_GLAZE', key_names=None):
    preset_config(name)
    from soft_cloud_finish import material
    return material(obj, name, key_names)


def apply_studio(obj, name='QINGBAI_GLAZE', host='PLATE'):
    preset_config(name)
    if host not in {'PLATE', 'VASE', 'CYLINDER'}: raise ValueError('Unknown host')
    from soft_cloud_finish import studio
    return studio(obj, host)


def apply_finish(obj, name='QINGBAI_GLAZE', host='PLATE', key_names=None, verify=True):
    """Only explicitly selected ceramic material slot 0 and presentation are changed."""
    if obj.type != 'MESH': raise ValueError('Expected the engraved mesh object')
    preset_config(name)  # Validate before any mutation.
    if host not in {'PLATE', 'VASE', 'CYLINDER'}: raise ValueError('Unknown host')
    before = geometry_fingerprint(obj) if verify else None
    evidence = build_material(obj, name, key_names); apply_studio(obj, name, host)
    after = geometry_fingerprint(obj) if verify else None
    if verify and before != after: raise RuntimeError('HOLD: finish changed geometry')
    return dict(preset=name, version=preset_config(name)['version'], host=host,
                geometry_before=before, geometry_after=after, geometry_unchanged=before == after if verify else None,
                pooling=evidence)


def main():
    import argparse, sys
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--object', required=True); p.add_argument('--output', required=True)
    p.add_argument('--preset', default='QINGBAI_GLAZE', choices=['QINGBAI_GLAZE', 'YINGQING_GLAZE'])
    p.add_argument('--host', required=True, choices=['PLATE', 'VASE', 'CYLINDER'])
    p.add_argument('--render', action='store_true')
    args = p.parse_args(sys.argv[sys.argv.index('--')+1:])
    output = Path(args.output).resolve(); output.mkdir(parents=True, exist_ok=True)
    target = output/(args.preset+'.blend')
    if target.exists() or target == Path(bpy.data.filepath).resolve(): raise ValueError('Choose a new output')
    report = apply_finish(bpy.data.objects[args.object], args.preset, args.host)
    (output/'finish_qa.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    text = bpy.data.texts.new('Presentation_Finish.json'); text.write(json.dumps(preset_config(args.preset), indent=2))
    if args.render:
        bpy.context.scene.render.filepath = str(output/(args.preset+'.png')); bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(target), compress=True)


if __name__ == '__main__': main()
