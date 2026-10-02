"""Deterministic local library, verified content identity and explainable retrieval."""
import json
from pathlib import Path

from ornamentforge.blender_contract import contained
from ornamentforge.canonical_curve import canonical_bytes, content_hash, validate_curve
from .motif_record import LibraryError, MotifRecord
from ornamentforge.serialization import utc_now, write_json

PARTITIONS = ("approved","generated","user")


class MotifLibrary:
    def __init__(self,workspace: str | Path):
        self.workspace = Path(workspace).resolve()
        self.root = self.workspace/"library"

    def records(self) -> list[dict]:
        records = []
        for kind in PARTITIONS:
            path = self.root/kind/"catalog.json"
            if not path.exists():
                continue
            catalog = json.loads(path.read_text(encoding="utf-8"))
            if set(catalog) != {"version","motifs"} or catalog["version"] != "1.0" or not isinstance(catalog["motifs"],list):
                raise LibraryError("CATALOG_SCHEMA",f"Invalid catalog {path}")
            for raw in catalog["motifs"]:
                record = MotifRecord.from_dict(raw).to_dict()
                if record["source_kind"] != kind:
                    raise LibraryError("PARTITION_MISMATCH",record["id"])
                records.append(record)
        if len({r["id"] for r in records}) != len(records):
            raise LibraryError("DUPLICATE_CONTENT","Duplicate geometry identity in catalogs")
        return sorted(records,key=lambda r:r["id"])

    def inspect(self,identifier: str) -> dict:
        match = next((r for r in self.records() if r["id"]==identifier),None)
        if match is None:
            raise LibraryError("MISSING_RECORD",identifier)
        return match

    def verify_record(self,record: dict, *, allow_user: bool = False) -> dict:
        record = MotifRecord.from_dict(record).to_dict()
        if self.inspect(record["id"]) != record:
            raise LibraryError("RECORD_MISMATCH","Record differs from current manifest")
        if record["qa_status"] != "PASS":
            raise LibraryError("QA_REJECTED",record["qa_status"])
        try:
            artifact = contained(self.workspace/record["artifact_path"],self.root/record["source_kind"])
            raw = json.loads(artifact.read_text(encoding="utf-8"))
            payload = validate_curve(raw)
            if canonical_bytes(raw) != canonical_bytes(payload) or content_hash(payload) != record["content_hash"]:
                raise LibraryError("HASH_MISMATCH",record["id"])
            provenance_path = contained(self.workspace/record["provenance_ref"],self.root/record["source_kind"])
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
            expected = {"version","motif_id","owner","license","source_url","source_kind",
                        "project_use_allowed","redistribution_allowed","attribution_required","evidence"}
            if (set(provenance)!=expected or provenance["version"]!="1.0" or provenance["motif_id"]!=record["id"]
                    or provenance["source_kind"]!=record["source_kind"]
                    or any(type(provenance[k]) is not bool for k in ("project_use_allowed","redistribution_allowed","attribution_required"))
                    or any(not isinstance(provenance[k],str) or not provenance[k].strip() for k in ("owner","license","source_url","evidence"))):
                raise LibraryError("PROVENANCE_INVALID",record["id"])
            if not provenance["project_use_allowed"] or provenance["license"].upper() in ("UNKNOWN","NOASSERTION"):
                raise LibraryError("PROVENANCE_DENIED","Current project use is not documented")
            if record["source_kind"]=="user" and not allow_user:
                raise LibraryError("USER_NOT_ALLOWED","Explicit request/configuration must allow user assets")
            evidence = contained(self.workspace/provenance["evidence"],self.workspace)
            if not evidence.is_file():
                raise LibraryError("PROVENANCE_EVIDENCE_MISSING",str(evidence))
            qa = json.loads(contained(self.workspace/record["qa_evidence"],self.workspace).read_text(encoding="utf-8"))
            if qa.get("final_pass") is not True:
                raise LibraryError("QA_EVIDENCE_REJECTED",record["id"])
            return payload
        except LibraryError:
            raise
        except (OSError,ValueError,TypeError) as exc:
            raise LibraryError("ARTIFACT_OR_EVIDENCE_INVALID",str(exc)) from exc

    def audit(self) -> dict:
        results = []
        for record in self.records():
            try:
                self.verify_record(record,allow_user=True)
                results.append({"id":record["id"],"valid":True,"content_hash":record["content_hash"]})
            except LibraryError as exc:
                results.append({"id":record["id"],"valid":False,"error":exc.to_dict()})
        return {"valid":all(r["valid"] for r in results),"motifs":results}

    def rebuild_index(self) -> dict:
        records = self.records()
        index = {"index_version":"1.0","catalog_hash":content_hash({"records":records}),
                 "entries":[{k:r[k] for k in ("id","family","type","tags","representation","source_kind",
                             "qa_status","compatible_mapping_modes")} for r in records]}
        write_json(self.root/"indexes/semantic.json",index)
        return index

    @staticmethod
    def range_rejections(record: dict,parameters: dict) -> list[dict]:
        errors = []
        for name,value in parameters.items():
            limits = record["parameter_ranges"].get(name)
            if limits is None or type(value) not in (int,float) or not limits["min"] <= value <= limits["max"]:
                errors.append({"code":"PARAMETER_OUT_OF_RANGE","parameter":name,"requested":value,"range":limits})
        return errors

    def search(self, *, family: str, motif_type: str, tags: list[str] | None = None,
               representation: str = "bezier_curve", mapping: str = "planar", threshold: int = 90,
               source_preference: str = "approved", allow_user: bool = False,
               parameters: dict | None = None) -> dict:
        if source_preference not in PARTITIONS or type(threshold) is not int or threshold < 0:
            raise LibraryError("INVALID_QUERY","Invalid source preference or threshold")
        index = self.rebuild_index()
        query = {"family":family,"type":motif_type,"tags":sorted(set(tags or [])),"representation":representation,
                 "mapping":mapping,"threshold":threshold,"source_preference":source_preference,
                 "allow_user":allow_user,"parameters":parameters or {}}
        candidates = []
        for entry in index["entries"]:
            record = self.inspect(entry["id"])
            components = {"exact_type":50 if record["type"]==motif_type else 0,
                          "family":20 if record["family"]==family else 0,
                          "tags":5*len(set(record["tags"]) & set(query["tags"])),
                          "representation":10 if record["representation"]==representation else 0,
                          "mapping":10 if mapping in record["compatible_mapping_modes"] else 0,
                          "qa":10 if record["qa_status"]=="PASS" else 0,
                          "source_preference":5 if record["source_kind"]==source_preference else 0}
            rejections = []
            for key,code in (("exact_type","TYPE_MISMATCH"),("representation","REPRESENTATION_MISMATCH"),("mapping","MAPPING_MISMATCH")):
                if components[key]==0:
                    rejections.append({"code":code})
            try:
                self.verify_record(record,allow_user=allow_user)
            except LibraryError as exc:
                rejections.append(exc.to_dict())
            rejections.extend(self.range_rejections(record,parameters or {}))
            score = sum(components.values())
            if score < threshold:
                rejections.append({"code":"BELOW_THRESHOLD"})
            candidates.append({"id":record["id"],"source_kind":record["source_kind"],"score":score,
                               "components":components,"rejections":rejections})
        candidates.sort(key=lambda c:(PARTITIONS.index(c["source_kind"]),-c["score"],c["id"]))
        selected = next((c["id"] for c in candidates if not c["rejections"]),None)
        lookups = [{"source_kind":kind,"status":"HIT" if any(c["id"]==selected and c["source_kind"]==kind for c in candidates)
                    else "DISABLED" if kind=="user" and not allow_user else "MISS"} for kind in PARTITIONS]
        return {"query":query,"library_state_hash":index["catalog_hash"],"candidate_ids":[c["id"] for c in candidates],
                "candidates":candidates,"selected_motif":selected,"status":"HIT" if selected else "MISS","lookups":lookups}

    def register(self,payload: dict,metadata: dict,provenance: dict) -> dict:
        payload = validate_curve(payload)
        digest = content_hash(payload)
        for record in self.records():
            if record["content_hash"]==digest:
                self.verify_record(record,allow_user=True)
                return record
        kind = metadata["source_kind"]
        if kind not in PARTITIONS:
            raise LibraryError("PARTITION_MISMATCH",kind)
        identifier = "motif-"+digest
        directory = self.root/kind
        artifact = directory/"artifacts"/(digest+".curve.json")
        provpath = directory/"provenance"/(digest+".json")
        record = {**metadata,"id":identifier,"content_hash":digest,
                  "artifact_path":artifact.relative_to(self.workspace).as_posix(),
                  "provenance_ref":provpath.relative_to(self.workspace).as_posix(),"created_at":utc_now()}
        record = MotifRecord.from_dict(record).to_dict()
        if record["qa_status"] != "PASS":
            raise LibraryError("QA_REJECTED","Registration requires PASS")
        qa = json.loads(contained(self.workspace/record["qa_evidence"],self.workspace).read_text(encoding="utf-8"))
        if qa.get("final_pass") is not True:
            raise LibraryError("QA_EVIDENCE_REJECTED",identifier)
        write_json(artifact,payload)
        write_json(provpath,{**provenance,"motif_id":identifier,"source_kind":kind})
        catalog_path = directory/"catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8")) if catalog_path.exists() else {"version":"1.0","motifs":[]}
        previous = list(catalog["motifs"])
        catalog["motifs"].append(record)
        catalog["motifs"].sort(key=lambda r:r["id"])
        write_json(catalog_path,catalog)
        try:
            self.verify_record(record,allow_user=True)
        except Exception:
            catalog["motifs"] = previous
            write_json(catalog_path,catalog)
            raise
        self.rebuild_index()
        return record
