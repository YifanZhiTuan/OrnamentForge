"""Strict immutable motif metadata, independent of geometry identity."""
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import sysconfig

from jsonschema import Draft202012Validator, FormatChecker

from ornamentforge.canonical_curve import canonical_bytes


class LibraryError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)

    def to_dict(self):
        return {"code":self.code,"message":str(self)}


def relative_path(value: str) -> None:
    for cls in (PurePosixPath,PureWindowsPath):
        path = cls(value)
        if path.anchor or ".." in path.parts:
            raise LibraryError("PATH_ESCAPE","Library paths must be relative and stay inside the workspace")


@dataclass(frozen=True)
class MotifRecord:
    canonical_json: str

    @classmethod
    def from_dict(cls,data: dict):
        path = Path(__file__).resolve().parents[4]/"schemas/motif_record.schema.json"
        if not path.is_file():
            path = Path(sysconfig.get_path("data"))/"share/ornamentforge/schemas/motif_record.schema.json"
        schema = json.loads(path.read_text(encoding="utf-8"))
        errors = sorted(Draft202012Validator(schema,format_checker=FormatChecker()).iter_errors(data),key=lambda e:str(e.path))
        if errors:
            raise LibraryError("MOTIF_SCHEMA","; ".join(f"{list(e.path)}: {e.message}" for e in errors))
        if data["id"] != "motif-"+data["content_hash"]:
            raise LibraryError("IDENTITY_MISMATCH","Motif ID must correspond to geometry hash")
        # jsonschema's RFC3339 format checker is optional; enforce timestamps without extras.
        try:
            created = datetime.fromisoformat(data["created_at"].replace("Z","+00:00"))
            if created.tzinfo is None or "T" not in data["created_at"]:
                raise ValueError("Timezone required")
        except ValueError as exc:
            raise LibraryError("MOTIF_SCHEMA","created_at must be an ISO timestamp with timezone") from exc
        for name in ("artifact_path","provenance_ref","qa_evidence"):
            relative_path(data[name])
        for limits in data["parameter_ranges"].values():
            if limits["min"] > limits["max"]:
                raise LibraryError("PARAMETER_RANGE","Range minimum exceeds maximum")
        return cls(canonical_bytes(data).decode())

    def to_dict(self) -> dict:
        return json.loads(self.canonical_json)

    @property
    def id(self):
        return self.to_dict()["id"]
