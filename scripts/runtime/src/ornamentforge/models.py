"""Immutable validated spec value; JSON Schema owns the domain field definitions."""
import hashlib
import json
from dataclasses import dataclass

from .validation import validate_spec


@dataclass(frozen=True)
class OrnamentSpec:
    canonical_json: str

    def __post_init__(self) -> None:
        data = json.loads(self.canonical_json)
        validate_spec(data)
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False, allow_nan=False)
        if canonical != self.canonical_json:
            raise ValueError("Construct specs using normalize_spec")

    @property
    def seed(self) -> int:
        return int(self.to_dict()["generation"]["seed"])

    @property
    def spec_hash(self) -> str:
        return hashlib.sha256(self.canonical_json.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        return json.loads(self.canonical_json)
