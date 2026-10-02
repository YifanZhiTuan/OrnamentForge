"""Build a clean, source-only Release and verify every archived byte.

Usage: python scripts/build_release.py --output NEW_DIRECTORY
Historical input assets stay in the development source; they are never copied.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

EXCLUDED_PREFIXES = ('scripts/runtime/library/', 'scripts/runtime/benchmarks/')
EXCLUDED_FILES = {
    'references/license-changes.json',
    'scripts/runtime/schemas/motif_record.schema.json',
    'scripts/runtime/schemas/example_ornament_spec.json',
    'scripts/runtime/schemas/example_showcase_v1.json',
    'scripts/runtime/schemas/example_showcase_ornament_sphere.json',
    *('scripts/runtime/src/ornamentforge/current/composition/' + name + '.py' for name in
      ('composition_planner', 'composition_grammar', 'composition_qa', 'semantic_intent', 'preview')),
    *('scripts/runtime/src/ornamentforge/current/library/' + name + '.py' for name in
      ('semantic_library', 'original_motifs', 'publish_originals')),
}

def included(path):
    return (not path.startswith(EXCLUDED_PREFIXES) and path not in EXCLUDED_FILES
            and '__pycache__' not in Path(path).parts and not path.endswith(('.pyc', '.pyo'))
            and '.git' not in Path(path).parts and path != 'release_manifest.json')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def build(source, output):
    if output.exists():
        raise ValueError('Choose a new output directory')
    if output.is_relative_to(source):
        raise ValueError('Release output must be outside the skill source')
    protected = json.loads((source/'references/core-source-hashes.json').read_text())
    for name, digest in protected.items():
        assert sha(source/name) == digest, f'Protected core changed: {name}'
    stage = output/'ornamentforge'
    stage.mkdir(parents=True)
    for p in sorted(source.rglob('*')):
        if p.is_file() and included(p.relative_to(source).as_posix()):
            dest = stage/p.relative_to(source)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dest)
    manifest = json.loads((source/'release_manifest.json').read_text(encoding='utf8'))
    previous = {x['path']: x for x in manifest['files']}
    manifest.update(release_version='2.0.1-v1-two-input-routes',
        input_routes=['Reference → Fidelity → PlanarMaster → SurfaceMap/Craft → Blender',
                      'Prompt → Codex image tool → selected 2D master → Fidelity → PlanarMaster → SurfaceMap/Craft → Blender'],
        bundled_motif_database=False, protected_core_files_verified=len(protected))
    manifest['license_policy'].pop('original_motif_assets', None)
    manifest['excluded'] = sorted(set(manifest.get('excluded', [])) | set(EXCLUDED_PREFIXES) | EXCLUDED_FILES)
    manifest['files'] = []
    for p in sorted(stage.rglob('*')):
        if p.is_file():
            name = p.relative_to(stage).as_posix()
            entry = dict(previous.get(name, {'path': name, 'license': 'MIT', 'category': 'skill-package'}))
            entry.update(sha256=sha(p), size_bytes=p.stat().st_size)
            manifest['files'].append(entry)
    (stage/'release_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf8')
    archive = output/'ornamentforge-v1-two-input-routes.skill.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in sorted(stage.rglob('*')):
            if p.is_file():
                z.write(p, 'ornamentforge/'+p.relative_to(stage).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        expected = {'ornamentforge/'+x['path'] for x in manifest['files']} | {'ornamentforge/release_manifest.json'}
        assert set(z.namelist()) == expected
        for entry in manifest['files']:
            data = z.read('ornamentforge/'+entry['path'])
            assert hashlib.sha256(data).hexdigest() == entry['sha256']
            assert len(data) == entry['size_bytes']
        assert not any('/runtime/library/' in n or '__pycache__' in n for n in z.namelist())
    print(json.dumps({'stage': str(stage), 'zip': str(archive), 'files': len(manifest['files'])+1,
                      'sha256': sha(archive), 'protected_core_files': len(protected)}, indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    build(Path(__file__).resolve().parents[1], Path(args.output).resolve())
