---
name: ornamentforge
description: Build editable traditional ornament, relief, engraving and painted ceramic assets from references or selected Codex-generated 2D designs. Use for ornament modeling through PlanarMaster, bounded SurfaceMap hosts and Blender; not generic modeling or automatic UV unwrapping.
---

# OrnamentForge

Use the bundled current runtime. This release contains no reference art, historical
runs or finished Blender assets. Treat this folder as read-only; place inputs,
environments and results in a separate user workspace.

Read [setup.md](references/setup.md) on first use. Resolve all paths relative to
this SKILL.md, never a previous machine or checkout. The launcher prepares a local
workspace and runs the bundled Python modules; it does not install dependencies,
generate images or silently change routes.

## Select the input route

| User input | Codex action | Python core route |
| --- | --- | --- |
| A reference image | Preserve and hash it; reconstruct without redesign | FIDELITY_RECONSTRUCTION |
| Prompt, no reference | Use the session's actual image tool; save, inspect and select candidates; record DesignHandoff | Selected PNG → FIDELITY_RECONSTRUCTION |

Read [input-and-fidelity.md](references/input-and-fidelity.md) for intake,
DesignHandoff and line-art evidence. If the session has no callable image tool,
report `AI_IMAGE_TOOL_UNAVAILABLE / HOLD`; do not call an online API, request an API key,
produce a procedural substitute, or substitute procedural assets.
Prompt-only work must use the current Codex built-in image tool, then select a 2D
master before Fidelity. Core `route --prompt` cannot generate images and returns
`AI_IMAGE_TOOL_UNAVAILABLE / HOLD`. No silent fallback is permitted.
Reference presence wins over prompt/spec. Multiple references are NOT_SUPPORTED.

## Preserve the shared contract and gates

Both user routes converge through Fidelity into PlanarMasterV1. READY means contract-valid, not visually
approved. Keep domain/physical scale, closed regions and holes, open strokes,
semantic roles, z-order, palette, repeats/transforms, correspondence, provenance,
editable geometry, QA and source hashes. Unknown scale stays null.

Review silhouette, hierarchy, flow, negative space and border/opening integration
before detail: each at least 3/5, weighted score at least 75, with actual evidence
and no blocker. Text plans and software test success do not establish visual PASS.
Preserve source identity and declared locks. Missing/corrupt sources, ambiguous
constraints and stale hashes HOLD; unsupported geometry is
NOT_SUPPORTED. Never silently replace a missing or rejected source with a preset.

## Continue to modeling only within the requested scope

Read [surface-craft-blender.md](references/surface-craft-blender.md) before host,
craft or Blender work. Use PlanarMaster → explicit SurfaceMap → craft → Blender.
SurfaceMap V1 is frozen: Plane, Cylinder, Cone, simple Revolution Vase, limited
Existing UV Mesh. Plate/Shallow Bowl retain an older transfer API, not SurfaceMapV1.
No auto unwrap, sphere, automatic seams, multi-chart, global geodesic solver or
complex freeform vessels. Preserve explicit seams, correspondence and Tu/Tv/N.
Distortion HOLD stops delivery; do not relax thresholds.

Engraved uses P-depth*N; relief P+height*N; painted uses surface position plus
reviewed semantic color/material. Broad masses and line-led details need different
craft treatment. Palette decisions do not silently change geometry. Prefer fields,
curves, instances, modifiers and shape keys; do not make thousands of Booleans.

Dense LINE_ART may use the existing EngravingFieldV1 craft route with a saved,
hash-bound normalized mask. CleanCurveNetwork remains editable/diagnostic, not a
mandatory engraving input. Vector-only hub/crossing HOLD does not certify or veto
the separate field route: review mask fidelity and require its own distortion,
seam and mesh QA. Never bypass source-loss or surface/geometry blockers.

For explicitly requested vector cleanup, merge continuous curves before pruning;
do not discard edges solely for short length. Preview/comparison images diagnose
geometry; pixel matching is not the modeling goal. Keep quarantined source data.

Stop at the requested checkpoint. After a first-pass asset, report route, stage,
reused/generated source, editability, hashes, visual and geometry QA, limitations
and output paths. Do not automatically begin another optimization phase.

## Presentation finish

For ceramic engraving with no other explicit material, use `QINGBAI_GLAZE`.
“瓷器/青白瓷” selects `QINGBAI_GLAZE`; “影青” selects `YINGQING_GLAZE`.
Read [presentation-finish.md](references/presentation-finish.md) before final
ceramic rendering. Use the bundled, versioned material AND studio preset; do not
rebuild an unknown generic porcelain shader from experience. Target a lustrous
pale cyan-white glaze, soft window reflections and slightly deeper cyan cavity
pooling, never matte gray or black linework. Explicit user materials take priority.
The authoritative finish is the user's `shoudai_soft_cloud_v5` .blend and its
front/3q/closeup renders, captured in the bundled `soft_cloud_v5.json` node graph.
Use version 2.0.0; the approximate 1.0.0 shader is superseded. Both public preset
names retain this approved gray-cyan palette unless the user requests another.
For all subsequent glaze work this is the default visual acceptance standard,
not merely a color suggestion. Judge lustrous clearcoat, soft cloud variation,
window/rim highlights and cyan cavity/shoulder pooling together. Applying a preset
or passing code tests does not establish visual approval. If these qualities are
missing, hold visual approval and report the gap instead of lowering the standard.
This is a finish-only step: preserve motif, Fidelity, SurfaceMap, vertices, topology,
shape keys, modifiers and mesh normals. Plate, Vase and Cylinder share the same finish;
only the lighting frame/scale adapts. Verify geometry hashes and inspect the render.

## Real limitations

Read [capabilities.md](references/capabilities.md) when choosing an implementation.
The release includes the current reference-led runtime, not a universal
prompt-to-finished-sculpture command. Generic SurfaceMap craft consumers return
sampled paths and bindings; they do not create arbitrary watertight solids.
ArtLibrary-dependent curated recipes need external art and are not runnable from
this distribution alone. No manufacturing, historical-authenticity or automatic
aesthetic certification is claimed.

## Distribution / License

- **Code: MIT** — code, SKILL.md, scripts and authored references; see [LICENSE](LICENSE).
- **External reference materials: not included / not licensed** — ArtLibrary,
  third-party images, historical runs, AI test images and Blender final assets.

Read [distribution.md](references/distribution.md) and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) before redistribution. Dependencies
keep their own licenses. Future user references/outputs are not automatically
relicensed by this release. See [LICENSE-ASSETS.md](LICENSE-ASSETS.md) for asset exclusions.
See [validation.md](references/validation.md) for release checks.
