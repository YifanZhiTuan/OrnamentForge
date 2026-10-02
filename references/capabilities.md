# Capability and data boundary

The only maintained core is `scripts/runtime/src/ornamentforge/current/`.
Sibling foundation modules supply schema validation, hashes, checkpoints and
Blender contracts. A small retained showcase module supplies shared worker imports;
its presence is not an instruction to execute or expand showcase workflows.

| Stage | Supported | Boundary / stop |
| --- | --- | --- |
| AI design | Actual current-session image tool + offline DesignHandoff | Tool missing → AI_IMAGE_TOOL_UNAVAILABLE / HOLD; no API client |
| Fidelity | Flat raster color regions/holes, line graph/cubics, mixed mode | No photographic depth recovery or universal semantic recognition |
| PlanarMasterV1 | One validated shared editable contract | READY is not aesthetic/model approval |
| SurfaceMapV1 | Plane, Cylinder, Cone, monotone Revolution Vase, existing UV | No arbitrary unwrap, sphere, multi-chart, auto seams, complex freeform |
| Plate/Shallow Bowl | Older analytic graph field transfer | Separate reviewed NPZ contract; not V1 host equivalence |
| Craft adapter | Signed offset paths, reviewed color/material bindings | Not automatic watertight solid creation |
| Dense engraving | Mask/SDF → straight vase displaced mesh → Blender | Bounded domain and defaults; seam/distortion/mesh QA required |
| Relief / Painted | Existing profiles, field mesh worker, semantic bindings | Per-asset preparation and review; no universal final-art generator |

Export authoritative schemas instead of maintaining duplicate handwritten JSON:
`... cli master-schema` and `... cli surface-schema`.
EngravingFieldV1 schema: `current.craft.engraving_field.EngravingFieldV1.schema()`.
It belongs to Craft; do not add its SDF to the PlanarMaster schema.

PlanarMaster preserves domain/physical scale; closed regions/holes; open stroke
graph; semantic roles/z-order; palette; repeat groups/transforms; source
correspondence/provenance; editable geometry handles; QA/source hash. Repeats retain
local source geometry and explicit transforms, never silently bake or double-apply
them. A mapped master retains the original contract beside surface samples.

EngravingField holds source hash, raster width/height, design domain, mask hash,
signed distance array reference/hash, groove depth, width policy, profile/softness,
provenance and QA. SDF is negative inside ink; continuous positive depth magnitude
is subtracted along N. V, U_ROUND and SOFT_ROUNDED are existing profiles; command
defaults to SOFT_ROUNDED. Width is source-mask distance based, not uniform curves.

Visual approval is separate from contract validation, topology cleanup, surface
distortion and mesh QA. Keep each status and its evidence; never overwrite a HOLD
with another stage's PASS. No inherited project test count is a release validation.
