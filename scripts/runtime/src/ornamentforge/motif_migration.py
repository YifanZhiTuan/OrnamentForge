"""Explicit import of validated Phase 2 artifacts; no motif constructors."""
import hashlib
import json
from pathlib import Path

from .blender_contract import contained
from .canonical_curve import from_legacy
from .current.library.motif_library import MotifLibrary
from .current.library.motif_record import LibraryError
from .serialization import write_json


def b01_ranges(kind: str) -> dict:
    ranges = {"scale":{"min":0.3,"max":0.45} if kind=="leaf" else {"min":1,"max":1},
              "stroke_width":{"min":0.025,"max":0.07},"leaf_count":{"min":4,"max":24}}
    if kind=="vine":
        ranges.update(vine_amplitude={"min":0.24,"max":0.24},vine_frequency={"min":1.5,"max":1.5})
    return ranges


def migrate_phase2(workspace: Path) -> dict:
    library = MotifLibrary(workspace)
    manifest = library.root/"generated/manifest.json"
    legacy = json.loads(manifest.read_text(encoding="utf-8"))
    migrated = []
    for record in legacy["motifs"]:
        if record["qa_status"]!="PASS" or record["author_owner"]!="OrnamentForge project":
            raise LibraryError("MIGRATION_REJECTED","Only original validated Phase 2 motifs may migrate")
        path = contained(library.root/record["local_asset_path"],library.root/"generated")
        if hashlib.sha256(path.read_bytes()).hexdigest()!=record["content_sha256"]:
            raise LibraryError("LEGACY_HASH_MISMATCH",str(path))
        qa = contained(record["qa_evidence"],library.workspace)
        if json.loads(qa.read_text(encoding="utf-8")).get("final_pass") is not True:
            raise LibraryError("QA_EVIDENCE_REJECTED",str(qa))
        kind = "leaf" if "b01_leaf_" in record["source_id"] else "vine"
        local_qa = library.root/"generated/evidence"/(record["source_id"]+".qa.json")
        write_json(local_qa,json.loads(qa.read_text(encoding="utf-8")))
        payload = from_legacy(json.loads(path.read_text(encoding="utf-8")))
        metadata = {"semantic_version":"1.0.0","family":"botanical","type":kind,
                    "tags":["b01","outline"] if kind=="leaf" else ["b01","continuous"],
                    "representation":"bezier_curve","source_kind":"generated","qa_status":"PASS",
                    "qa_evidence":local_qa.relative_to(library.workspace).as_posix(),
                    "parameter_ranges":b01_ranges(kind),"compatible_mapping_modes":["planar"],
                    "derived_from":record["source_id"]}
        provenance = {"version":"1.0","owner":record["author_owner"],"license":record["license"],
                      "source_url":record["source_url"],"project_use_allowed":True,
                      "redistribution_allowed":False,"attribution_required":True,
                      "evidence":manifest.relative_to(library.workspace).as_posix()}
        new = library.register(payload,metadata,provenance)
        if new["qa_evidence"] != metadata["qa_evidence"]:
            # Metadata-only migration preserves ID, geometry hash and creation time.
            catalog_path = library.root/"generated/catalog.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            for item in catalog["motifs"]:
                if item["id"]==new["id"]:
                    item["qa_evidence"] = metadata["qa_evidence"]
            write_json(catalog_path,catalog)
            new = library.inspect(new["id"])
            library.verify_record(new)
        migrated.append({"legacy_id":record["source_id"],"legacy_hash":record["content_sha256"],
                         "id":new["id"],"content_hash":new["content_hash"],"type":kind})
    result = {"version":"1.0","migration":"phase2-to-canonical-v1","motifs":migrated}
    write_json(library.root/"indexes/phase2_migration.json",result)
    library.rebuild_index()
    return result
