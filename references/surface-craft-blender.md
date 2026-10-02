# Surface, craft and Blender

## Shared mapping API

Load a reviewed master from the saved route envelope. Retain source geometry and
provenance alongside mapped paths. Example task-local Python (set runtime sys.path
as described in setup.md):

```python
import json
from pathlib import Path
from ornamentforge.current.planar.contract import PlanarMasterV1
from ornamentforge.current.surface import HostAdapter, fit_domain_transform
from ornamentforge.current.craft.surface_adapter import map_surface_craft
raw = json.loads(Path("runs/current/intake.json").read_text(encoding="utf-8"))
if raw["status"] != "READY":
    raise RuntimeError("HOLD: master not ready")
master = PlanarMasterV1.from_dict(raw["master"])
surface = HostAdapter.create("REVOLUTION_VASE", parameters={"profile": "straight_vase"})
result = map_surface_craft(master, surface, craft="engraved", depth=.01,
    domain_transform=fit_domain_transform(master, surface),
    source_feature_width=measured_feature_width)
if result["status"] != "READY":
    raise RuntimeError(result["message"])
Path("runs/current/mapped.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
```

`measured_feature_width` must be measured or explicitly declared in source domain
units, not invented to satisfy QA; omit only when source widths are already known.
For relief use `craft="relief", height=...` without depth. For painted use
`craft="painted", reviewed_semantics=True` only AFTER actual semantic review,
zero offsets, and a source palette or explicit `material_by_role` mapping.
Paint missing bindings or unreviewed regions HOLD. Physical units must be consistent.

CLI mapping is also available:

```text
... cli surface-map runs/current/intake.json host.json --fit-domain --depth 0.01 --source-feature-width <measured-width> --output runs/current/mapped.json
```

`host.json`: `{"host_type":"REVOLUTION_VASE","parameters":{"profile":"straight_vase"}}`.
Do not infer that full-domain fitting is aesthetically appropriate: it may wrap an
entire drawing around 360 degrees. For a front-facing composition, declare a domain
transform, preserve X/Y physical scale, center the subject at the front and keep
seams in blank space. Check both sides remain visible. Do not change frozen mapper.

Supported vase profiles: straight_vase, belly_vase, bottle_vase; custom 2–32 positive
radius control points over monotone height. No inverted/self-intersecting profile,
branches or arbitrary mesh vase. Belly/bottle distortion may HOLD. Existing UV Mesh
requires a valid pre-existing selected chart: no unwrap, missing UV repair, mirrored
or overlapping chart acceptance. Plate/Shallow Bowl use retained `surface.transfer`
with its older reviewed NPZ contract, not the PlanarMasterV1 JSON adapter.

Mapped output stores sampled paths/boundaries, holes, roles, palette, repeat IDs,
source master and P/N/Tu/Tv correspondence. It is not a triangulated solid.

## Dense LINE_ART → actual engraved vase

This is the maintained bounded end-to-end field/Blender entry. First retain the
PlanarMaster as editable/diagnostic evidence and review the saved Fidelity mask.
Require an ink-free source seam, nonempty white-on-black stroke mask, appropriate
aspect ratio for the fixed 10×5 design domain, shallow requested depth and valid
surface QA. Source reference and mask hashes must remain bound in output.

```text
... run.py --workspace <WORKSPACE> module ornamentforge.current.craft.engraving_field_run --source inputs/reference.png --mask runs/current/lineart/binary_mask.png --output runs/current/engraving_field/my_design --blender <local-blender-executable>
```

The existing command uses SOFT_ROUNDED, .035 design-unit depth, a 1024×512 mesh,
full-resolution SDF, straight_vase and a full 360-degree wrap. Those are bounded
technical defaults, not a universal final presentation. It retains source widths,
reports filtering (default zero), keeps field/mask rebuild sources and creates real
negative-normal displacement with editable shape keys and a Solidify wall.
Outputs: source.png, binary_mask.png, engraving_field.npz/json/png, mapped_field.png,
surface_field.npz, surface_map.json, qa.json, report.md, Blender log/geometry QA,
vase_white_preview.png, vase_engraved_preview.png, final_front.png, final_3q.png,
editable_engraved_vase.blend.

Before running, inspect the seam/geometry preconditions independently. The retained
runner checks frozen distortion before Blender but assembles some seam/mesh blockers
after rendering; a render's existence is never proof of PASS. Stop and retain
diagnostics if any final QA is HOLD. Do not present that asset as approved.
Its provenance currently labels the source AI_SELECTED_REFERENCE even for arbitrary
input: for user-supplied art, record the actual source in the enclosing run report
and explicitly disclose this inherited label; never claim it was AI-generated.

Do not run vector cleanup to fix field-only engraving. Junction semantics belong
to the vector route. Field blockers are mask loss, source-width loss, distortion,
seam discontinuity, unsafe depth, inversion, self-intersection or surface integrity.
Numerical screens do not certify global self-intersection or manufacturing safety.

## Other craft delivery

The shared adapter above is available for Engraved / Relief / Painted. For Blender
delivery, inspect the existing worker contract before use:

- `scripts/runtime/src/ornamentforge/current/blender/engraving_field_worker.py`:
  straight vase field NPZ and real displaced mesh; used by the command above.
- `scripts/runtime/src/ornamentforge/current/blender/surface_worker.py`: periodic
  polar disc/annulus field mesh; consumes `surface.npz` (base, normal, top, per-role
  fields, rgb, roles, inner_radius), editable_regions.json, ArtPlan.json,
  AssemblyPlan.json, OrnamentSpec.json, references.json and transfer_qa.json.
  It supports actual signed role shape keys and vertex-color material; it does
  not accept mapped PlanarMaster JSON directly or generate vase topology.
- `current/craft/relief.py`, `relief_petal.py`, `vessel_relief.py`: bounded authored
  directional profiles, not semantic sculpting from any image.
- `current/blender/reference_worker.py`: compatible reference Macro checkpoint,
  not a universal shared-master-to-final mesh builder.

For a requested asset whose geometry fits these contracts, the Codex agent may
prepare a task-local build script using the reviewed master, existing mapping and
craft functions. Preserve holes, source correspondence, curve guides and repeat
transforms; pack input evidence into the .blend. For painted output bind only
reviewed semantic regions, keeping surface positions unchanged. This orchestration
is per-asset work, not a new core feature. If the requested shape cannot be produced
with the existing contracts, report the specific HOLD/NOT_SUPPORTED; do not invent
a universal conversion CLI, substitute a curated preset or claim completion from
sampled paths alone.

Curated `planar build`/porcelain recipes depend on excluded ArtLibrary art and
are unavailable in this self-contained package unless the user supplies the exact
required authorized sources. Never silently redirect arbitrary user art to them.

## Delivery verification

Inspect front, three-quarter and detail renders, comparing source structure rather
than optimizing pixel identity. Check holes, both mirrored subjects, flower center,
continuity, spacing, shallow depth and seam. Check evaluated geometry for finite
coordinates, nonmanifold edges, inversion and observable intersections; disclose
unverified global collision conditions. Reopen .blend, verify shape keys/curves,
modifiers and packed provenance. Rendering success alone is insufficient.
Use the versioned [Presentation Finish Preset](presentation-finish.md) for ceramic
engraving: QINGBAI_GLAZE by default, YINGQING_GLAZE for explicit 影青. Its material
and studio are reused together; do not improvise a generic porcelain substitute.
Historical per-artwork scripts and finished images are not distributed. The new
finish module reuses reviewed material/studio parameters, not old motifs or geometry.
