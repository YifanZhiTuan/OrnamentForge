"""Honest approved-library lookup and post-validation project motif registration."""
import hashlib
import json
from pathlib import Path

from .provenance import validate_manifest
from .serialization import write_json


def lookup_approved(workspace: Path, run: Path) -> dict:
    manifest = workspace/"library/approved/manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    records = validate_manifest(data,approved=True)
    # Phase 1 records have no motif taxonomy or supported ingestion representation.
    # A record is not an importable motif. Never silently call metadata an asset hit.
    result = {"library":str(manifest),"manifest_sha256":hashlib.sha256(manifest.read_bytes()).hexdigest(),
              "requested":["continuous_vine","leaf_outline"],"records_examined":len(records),
              "status":"MISS","matches":[],
              "reason":"No approved B01 curve representation available",
              "action":"Generate original project curves, validate, then register"}
    write_json(run/"library_lookup.json",result)
    return result


def register_generated(workspace: Path, run: Path, plan: dict, metrics: dict) -> dict:
    validation = metrics.get("motif_validation",{})
    names = {"vine":"B01_Vine","leaf":"B01_LeafTemplate"}
    if set(validation) != set(names.values()) or any(
            m.get("editable_curve") is not True or m.get("vertices",0) <= 0 or
            m.get("stroke_width",0)+plan["tolerance"] < plan["minimum_feature_width"] for m in validation.values()):
        raise ValueError("Generated motifs must pass Blender validation before registration")
    generated = workspace/"library/generated"
    generated.mkdir(parents=True,exist_ok=True)
    manifest_path = generated/"manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"version":"1.0","motifs":[]}
    created = []
    for kind,name in names.items():
        payload = {"representation":"bezier_curve","cyclic":kind=="leaf",
                   "control_points":plan["vine_control_points" if kind=="vine" else "leaf_motif_control_points"]}
        digest = hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
        identifier = f"b01_{kind}_{digest[:16]}"
        asset = generated/(identifier+".json")
        write_json(asset,payload)
        record = {"source_id":identifier,"source_url":f"project://ornamentforge/library/generated/{asset.name}",
                  "author_owner":"OrnamentForge project","license":"LicenseRef-ProjectOwned-Unlicensed",
                  "redistribution_allowed":False,"attribution_required":True,
                  "local_asset_path":asset.relative_to(workspace/"library").as_posix(),
                  "notes":"Original procedural B01 curve; no third-party asset; public license not assigned",
                  "qa_status":"PASS","qa_evidence":str(run/"G03_motif/qa.report.json"),
                  "geometry_validation":validation[name],"content_sha256":hashlib.sha256(asset.read_bytes()).hexdigest()}
        if not any(m["source_id"] == identifier for m in manifest["motifs"]):
            manifest["motifs"].append(record)
        created.append(record)
    write_json(manifest_path,manifest)
    provenance = {"version":"1.0","sources":[{k:r[k] for k in
                  ("source_id","source_url","author_owner","license","redistribution_allowed",
                   "attribution_required","local_asset_path","notes")} for r in created]}
    validate_manifest(provenance)
    write_json(run/"provenance.json",provenance)
    write_json(run/"generated_motifs.json",{"motifs":created})
    return provenance
