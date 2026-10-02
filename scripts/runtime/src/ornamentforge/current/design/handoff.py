"""Hash-bound external PNG handoff. This module never generates or edits images.

Generator identity and visual observations are caller declarations, not attestation
that a tool ran or that its output is aesthetically/historically correct.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError
from PIL import Image


class HandoffError(ValueError):
    code = "INVALID_DESIGN_HANDOFF"


def _object(**fields):
    return dict(type="object", properties=fields, required=list(fields), additionalProperties=False)


_TEXT = {"type": "string", "minLength": 1}
_HASH = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
_TIME = {"type": ["string", "null"]}
_SCHEMA = _object(
    schema_version={"const": "DesignHandoffV1"},
    original_user_prompt=_TEXT, design_prompt=_TEXT,
    generator={"enum": ["codex_image_tool", "test_fixture"]},
    candidates={"type": "array", "minItems": 1, "items": _object(
        candidate_id=_TEXT, image_path=_TEXT, sha256=_HASH,
        width={"type": "integer", "minimum": 1}, height={"type": "integer", "minimum": 1})},
    selected_candidate=_TEXT,
    timestamps=_object(recorded_at=_TEXT, generated_at=_TIME, selected_at=_TIME),
    selection_notes=_TEXT, provenance={"type": "object"},
)


def _canonical(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _png(path):
    """Decode and hash the same bytes; no resave or preprocessing."""
    path = Path(path).resolve(strict=True)
    raw = path.read_bytes()
    with Image.open(BytesIO(raw)) as image:
        if image.format != "PNG" or getattr(image, "n_frames", 1) != 1:
            raise HandoffError("External design must be a single-frame PNG")
        image.load()
        width, height = image.size
    return dict(image_path=str(path), sha256=sha256(raw).hexdigest(), width=width, height=height)


@dataclass(frozen=True)
class DesignHandoff:
    """Immutable metadata snapshot, not a generator, selector or approval receipt."""
    _json: str

    def __post_init__(self):
        try:
            data = json.loads(self._json)
            _canonical(data)
            Draft202012Validator(_SCHEMA).validate(data)
            for value in (data["original_user_prompt"], data["design_prompt"], data["selection_notes"]):
                if not value.strip():
                    raise ValueError("Prompt and selection notes cannot be blank")
            ids = [c["candidate_id"] for c in data["candidates"]]
            if len(ids) != len(set(ids)) or data["selected_candidate"] not in ids:
                raise ValueError("Candidate IDs must be unique and selection must exist")
            for c in data["candidates"]:
                if not c["candidate_id"].strip() or not Path(c["image_path"]).is_absolute():
                    raise ValueError("Candidate paths must be absolute and IDs nonblank")
            for timestamp in data["timestamps"].values():
                if timestamp is not None:
                    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    if parsed.tzinfo is None:
                        raise ValueError("Timestamps must include a timezone")
        except (ValueError, TypeError, ValidationError) as exc:
            raise HandoffError(str(exc)) from exc

    @classmethod
    def from_dict(cls, data):
        try:
            return cls(_canonical(data))
        except (ValueError, TypeError) as exc:
            raise HandoffError(str(exc)) from exc

    @classmethod
    def create(cls, *, original_user_prompt, design_prompt, candidates, selected_candidate,
               selection_notes, provenance, generator="codex_image_tool",
               generated_at=None, selected_at=None):
        """Record existing {candidate_id: PNG_path}; never create candidate images.

        Unknown external generation/selection times stay null. recorded_at records
        only this metadata operation. Use test_fixture for synthetic test evidence.
        """
        try:
            if not isinstance(candidates, dict):
                raise HandoffError("candidates must map IDs to existing PNG paths")
            rows = [dict(candidate_id=key, **_png(path)) for key, path in candidates.items()]
            return cls.from_dict(dict(schema_version="DesignHandoffV1",
                original_user_prompt=original_user_prompt, design_prompt=design_prompt,
                generator=generator, candidates=rows, selected_candidate=selected_candidate,
                timestamps=dict(recorded_at=datetime.now(timezone.utc).isoformat(),
                                generated_at=generated_at, selected_at=selected_at),
                selection_notes=selection_notes, provenance=provenance))
        except (OSError, ValueError, TypeError) as exc:
            raise HandoffError(str(exc)) from exc

    def to_dict(self):
        return json.loads(self._json)

    @classmethod
    def load(cls, path):
        try:
            return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8-sig")))
        except (OSError, ValueError, TypeError) as exc:
            raise HandoffError(str(exc)) from exc

    def save(self, path):
        """Write metadata only; exclusive creation preserves earlier evidence."""
        self.verify()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n")

    def verify(self, reference=None):
        """Recheck all retained candidates and optionally an unchanged selected copy."""
        data = self.to_dict()
        try:
            for candidate in data["candidates"]:
                measured = _png(candidate["image_path"])
                if any(measured[k] != candidate[k] for k in measured):
                    raise HandoffError("Candidate bytes/dimensions/path changed: " + candidate["candidate_id"])
            chosen = next(c for c in data["candidates"] if c["candidate_id"] == data["selected_candidate"])
            if reference is not None and _png(reference)["sha256"] != chosen["sha256"]:
                raise HandoffError("Reference is not the recorded selected candidate (SHA-256 mismatch)")
            return chosen
        except (OSError, ValueError, TypeError) as exc:
            raise HandoffError(str(exc)) from exc

    def attach(self, master, reference):
        """Add source history only; preserve geometry, core route and review state."""
        from ..planar.contract import PlanarMasterV1
        selected = self.verify(reference)
        data = master.to_dict()
        if data["route"] != "FIDELITY_RECONSTRUCTION" or data["source_hash"] != selected["sha256"]:
            raise HandoffError("Handoff must match the actual fidelity source hash")
        data["provenance"].append(dict(id="external_design", kind="DesignHandoffV1",
            source="external_design_record", sha256=sha256(_canonical(self.to_dict()).encode("utf-8")).hexdigest(),
            details=self.to_dict()))
        data["qa_state"]["limitations"].append(
            "External design provenance is caller-declared; hashes verify file integrity, not tool identity or visual approval.")
        return PlanarMasterV1.from_dict(data)
