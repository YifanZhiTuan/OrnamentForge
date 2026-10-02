# Distribution and provenance

This source-only Release exposes two input routes: user reference, or prompt through the actual Codex image tool and a selected 2D master. Both enter Fidelity before PlanarMaster, SurfaceMap/Craft and Blender.

The bundled motif database, its catalogs, provenance, previews, dedicated composition planner, authoring utilities and benchmark examples are excluded from this Release. The old source package is preserved outside Release for recovery. Its old packaging tests depended on 16 V2 and 10 V1 records; those database-only cases were removed. The retained Fidelity, SurfaceMap, Engraved, Relief, Painted and Blender paths do not require those records. Some legacy foundation helpers remain for shared imports; they do not establish additional supported user routes.

No ArtLibrary, user references, AI candidates, historical runs, environments, bytecode caches or Blender outputs are bundled. Fidelity, SurfaceMap, Craft and Blender source hashes are checked against the pre-change package. Only input routing, its PlanarMaster route enum, CLI, launcher, documentation, validation and packaging change.

Code, schemas and authored documentation use MIT. Prior asset license grants are not revoked by excluding those assets. User inputs/outputs are not automatically relicensed. External dependencies retain their own terms; unmodified third-party notice texts remain bundled. Presentation finish provenance and version 2.0.0 remain unchanged.

`release_manifest.json` lists the exact Release files, hashes and sizes. `scripts/build_release.py` creates a clean staged `ornamentforge/` folder and zip using explicit exclusions, verifies protected core hashes, then verifies archive contents. Build into a new output directory. No remote publication is performed.
