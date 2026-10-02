# OrnamentForge Skill

OrnamentForge turns authorized references or natural-language briefs into editable Blender ornament assets. V1 has exactly two user input routes:

1. **Reference → Fidelity → PlanarMaster → SurfaceMap/Craft → Blender**
2. **Prompt → Codex built-in image generation → select a 2D ornament master → Fidelity → PlanarMaster → SurfaceMap/Craft → Blender**

Prompt-only work requires the actual current-session Codex image generation tool. If unavailable, return **AI_IMAGE_TOOL_UNAVAILABLE / HOLD** immediately. The Python runtime cannot generate images. There is no alternate composition route or silent fallback. Selected generated images retain their prompts, receipts, review and hash-bound DesignHandoff.

The default ceramic presentation finish remains verified **Soft Cloud V5 Qingbai glaze**, version 2.0.0. `QINGBAI_GLAZE` and `YINGQING_GLAZE` retain the approved gray-cyan appearance and preserve geometry.

## Install

1. Copy the complete `ornamentforge` folder from the skill zip to your Codex skills directory.
2. Create a Python 3.11+ environment outside the skill and install `scripts/requirements.txt`.
3. Initialize a separate workspace:

   ```powershell
   python <SKILL_ROOT>/scripts/run.py --workspace <WORKSPACE> init
   python <SKILL_ROOT>/scripts/run.py --workspace <WORKSPACE> cli --help
   ```

4. Keep Blender 4.2 or newer available separately. Release validation uses Blender 5.1.2.

Start with [SKILL.md](SKILL.md), [setup](references/setup.md) and [input and Fidelity](references/input-and-fidelity.md). See [presentation finish](references/presentation-finish.md) for rendering.

## Validation

```powershell
python -B scripts/check_runtime.py
python -B scripts/test_input_routes.py
blender --background --factory-startup your_asset.blend --python-exit-code 17 --python scripts/test_presentation_finish.py -- --object YOUR_OBJECT --output NEW_EMPTY_DIRECTORY
```

The finish test requires Blender and an existing asset; it is not automatically skipped. Current results and limits are in [validation](references/validation.md).

## Licensing

Code and documentation use [MIT](LICENSE). [Third-party notices](THIRD_PARTY_NOTICES.md) retain dependency terms. User reference images, generated candidates and Blender outputs are excluded and are not relicensed; see [asset boundary](LICENSE-ASSETS.md).
