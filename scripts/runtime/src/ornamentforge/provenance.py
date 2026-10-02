"""License metadata is recorded explicitly; records do not grant asset rights."""
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath, PureWindowsPath
from urllib.parse import urlparse


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    source_url: str
    author_owner: str
    license: str
    redistribution_allowed: bool
    attribution_required: bool
    local_asset_path: str | None = None
    notes: str = ""

    def __post_init__(self):
        for name in ("source_id", "source_url", "author_owner", "license"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a nonempty string")
        url = urlparse(self.source_url)
        if (url.scheme not in ("http", "https") or not url.netloc) and not (
                url.scheme == "project" and url.netloc == "ornamentforge" and url.path.startswith("/library/generated/")):
            raise ValueError("source_url must be HTTP(S) or an OrnamentForge generated project URI")
        if type(self.redistribution_allowed) is not bool or type(self.attribution_required) is not bool:
            raise ValueError("License flags must be explicit booleans")
        if not isinstance(self.notes, str):
            raise ValueError("notes must be a string")
        if self.local_asset_path is not None:
            if not isinstance(self.local_asset_path, str) or not self.local_asset_path.strip():
                raise ValueError("local_asset_path must be null or a relative path")
            for cls in (PurePosixPath, PureWindowsPath):
                path = cls(self.local_asset_path)
                if path.anchor or ".." in path.parts:
                    raise ValueError("Asset path must stay inside the library")

    def to_dict(self) -> dict:
        return asdict(self)


def validate_manifest(data: dict, *, approved: bool = False) -> list[SourceRecord]:
    if not isinstance(data, dict) or set(data) != {"version", "sources"}:
        raise ValueError("Manifest requires only version and sources")
    if data["version"] != "1.0" or not isinstance(data["sources"], list):
        raise ValueError("Invalid manifest version or sources")
    records = [SourceRecord(**item) for item in data["sources"]]
    if len({r.source_id for r in records}) != len(records):
        raise ValueError("Duplicate source id")
    if approved and any(not r.redistribution_allowed or r.license.upper() in
                        {"UNKNOWN", "NOASSERTION", "UNSPECIFIED"} for r in records):
        raise ValueError("Approved sources require documented redistribution rights")
    return records
