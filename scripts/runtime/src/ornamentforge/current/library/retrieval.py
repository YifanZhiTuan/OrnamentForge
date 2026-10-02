"""Resolve definitions before composition. Generation is called only on a verified MISS."""
from dataclasses import asdict
import json
from pathlib import Path

from ornamentforge.canonical_curve import control_points, content_hash, from_legacy
from .motif_library import MotifLibrary
from ornamentforge.motif_migration import b01_ranges
from .motif_record import LibraryError
from ornamentforge.serialization import write_json


class B01Resolver:
    def __init__(self,workspace: Path,allow_user: bool = False):
        self.library = MotifLibrary(workspace)
        self.allow_user = allow_user
        self.events = {}
        self.payloads = {}
        self.sources = {}
        self.generation_calls = {"vine":0,"leaf":0}

    def resolve(self,kind: str,parameters: dict,generator):
        query = {"family":"botanical","motif_type":kind,
                 "tags":["b01","outline"] if kind=="leaf" else ["b01","continuous"],
                 "source_preference":"generated","parameters":parameters,"allow_user":self.allow_user}
        event = self.library.search(**query)
        self.events[kind] = event
        if event["selected_motif"]:
            record = self.library.inspect(event["selected_motif"])
            payload = self.library.verify_record(record,allow_user=self.allow_user)
            source = {"id":record["id"],"content_hash":record["content_hash"],"source_kind":record["source_kind"],
                      "status":"HIT","artifact_path":record["artifact_path"],"snapshot_path":f"motifs/{kind}.curve.json"}
        else:
            # Range violations must not silently bypass an existing validated range by regeneration.
            range_errors = [r for c in event["candidates"] if c["components"]["exact_type"] for r in c["rejections"]
                            if r["code"]=="PARAMETER_OUT_OF_RANGE"]
            if range_errors:
                raise LibraryError("PARAMETER_OUT_OF_RANGE",json.dumps({"kind":kind,"rejections":range_errors}))
            self.generation_calls[kind] += 1
            payload = from_legacy({"representation":"bezier_curve","cyclic":kind=="leaf","control_points":generator()})
            source = {"id":None,"content_hash":content_hash(payload),"source_kind":"generated",
                      "status":"MISS","artifact_path":None,"snapshot_path":f"motifs/{kind}.curve.json"}
        self.payloads[kind],self.sources[kind] = payload,source
        return control_points(payload)

    def persist(self,run: Path):
        for kind,payload in self.payloads.items():
            write_json(run/self.sources[kind]["snapshot_path"],payload)
        write_json(run/"retrieval.json",{"version":"1.0","queries":self.events,"selected":self.sources,
                                        "generation_calls":self.generation_calls})
        write_json(run/"library_before_run.json",{"records":self.library.records(),"verification":self.library.audit()})
        records = [self.library.inspect(s["id"]) for s in self.sources.values() if s["id"]]
        write_json(run/"provenance.json",{"version":"1.0","motif_provenance":[
            json.loads((self.library.workspace/r["provenance_ref"]).read_text(encoding="utf-8")) for r in records]})

    def register_misses(self,run: Path,plan: dict,metrics: dict):
        for kind,source in self.sources.items():
            if source["status"]=="HIT":
                continue
            name = "B01_Vine" if kind=="vine" else "B01_LeafTemplate"
            metric = metrics["motif_validation"][name]
            if not metric["editable_curve"] or metric["vertices"]<=0 or metric["stroke_width"]+plan["tolerance"]<plan["minimum_feature_width"]:
                raise LibraryError("QA_REJECTED","Cannot register failed generated motif")
            ranges = b01_ranges(kind)
            evidence_dir = self.library.root/"generated/evidence"/source["content_hash"]
            write_json(evidence_dir/"qa.json",json.loads((run/"G03_motif/qa.report.json").read_text(encoding="utf-8")))
            write_json(evidence_dir/"retrieval.json",json.loads((run/"retrieval.json").read_text(encoding="utf-8")))
            # Generated fallback is certified only at the actual tested parameter point.
            for parameter,value in self.events[kind]["query"]["parameters"].items():
                ranges[parameter] = {"min":value,"max":value}
            metadata = {"semantic_version":"1.0.0","family":"botanical","type":kind,
                        "tags":self.events[kind]["query"]["tags"],"representation":"bezier_curve",
                        "source_kind":"generated","qa_status":"PASS","parameter_ranges":ranges,
                        "compatible_mapping_modes":["planar"],"qa_evidence":(evidence_dir/"qa.json").relative_to(self.library.workspace).as_posix()}
            provenance = {"version":"1.0","owner":"OrnamentForge project","license":"LicenseRef-ProjectOwned-Unlicensed",
                          "source_url":"project://ornamentforge/library/generated/"+kind,"project_use_allowed":True,
                          "redistribution_allowed":False,"attribution_required":True,
                          "evidence":(evidence_dir/"retrieval.json").relative_to(self.library.workspace).as_posix()}
            self.library.register(self.payloads[kind],metadata,provenance)
