# Release validation — V1 two input routes

Validated on 2026-10-01 with Python 3.11 and Blender 5.1.2. These results cover the tests available in this source distribution; no unavailable historical development suite is claimed.

## Current results

- **15/15 input-boundary regression tests PASS**: prompt without tool, tool present but no selected image, empty intake, reference reconstruction and precedence, missing/corrupt/multiple/unsupported references, invalid scale, selected DesignHandoff, tampered selected/candidate images, unsupported master route and structured CLI HOLD with exit code 2.
- **9/9 retained runtime smoke checks PASS**: relocated import, reference intake, offline test-fixture handoff, missing reference HOLD, multiple-reference stop, Plane mapping for Engraved/Relief/Painted, and signed-distance/groove profile. Run from the clean staged Release with no bundled motif assets and with inherited PYTHONPATH removed.
- **1/1 existing Blender presentation regression PASS**: same lotus asset, generic/QINGBAI_GLAZE/YINGQING_GLAZE renders, repeat application, PLATE/VASE/CYLINDER studio adaptation, reopening, unchanged source bytes and geometry fingerprint. Finish version remains 2.0.0. Rendering is verified execution, not a new artistic approval.
- **1/1 skill-creator validation PASS**: Skill is valid! Use the local Python interpreter with PyYAML and -X utf8; the runtime-only virtual environment does not include PyYAML.
- **1/1 Release integrity check PASS**: explicit exclusions, full archive CRC/content/hash/size verification, and **45/45 protected Fidelity/SurfaceMap/Craft/Blender source files byte-identical** to the pre-change package.

Total: **27/27 named checks PASS, 0 failures, 0 skipped** (15 route tests + 9 runtime checks + Blender + skill + Release integrity). The 45 source hashes are an additional integrity invariant, not 45 additional behavioral tests. Source and staged-copy runs are not double-counted.

## Reproduce

```text
<runtime-python> -B <SKILL_ROOT>/scripts/test_input_routes.py
<runtime-python> -B <SKILL_ROOT>/scripts/check_runtime.py
<validator-python> -X utf8 <skill-creator>/scripts/quick_validate.py <SKILL_ROOT>
blender --background --factory-startup <EXISTING_ASSET.blend> --python-exit-code 17 --python <SKILL_ROOT>/scripts/test_presentation_finish.py -- --object <OBJECT> --output <NEW_EMPTY_DIRECTORY>
<runtime-python> -B <SKILL_ROOT>/scripts/build_release.py --output <NEW_RELEASE_DIRECTORY>
```

The smoke checker relocates the package into a temporary path with spaces. Handoff tests explicitly use test_fixture; they do not claim live AI generation. No live image generation, new full modeling run, fresh dependency install, Linux/macOS execution or manufacturing certification was performed. Existing presentation provenance remains in presentation-finish-provenance.json and its earlier validation record; this update's structured results are in input-route-validation.json.

Removed input-route asset dependencies and recovery policy are documented in [distribution.md](distribution.md). All available non-database core tests are retained and pass. Historical database-only assertions are not counted as current tests.
