"""Strict JSON intake and deterministic content normalization."""
import json
import math
from pathlib import Path

from .models import OrnamentSpec
from .validation import SpecValidationError, ValidationIssue, validate_spec


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _normalize(value):
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Non-finite numbers are not JSON")
        if value.is_integer():
            return int(value)
    return value


def normalize_spec(data: object) -> OrnamentSpec:
    validate_spec(data)
    try:
        canonical = json.dumps(_normalize(data), sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise SpecValidationError([ValidationIssue("", "json", str(exc))]) from exc
    return OrnamentSpec(canonical)


def load_spec(path: str | Path) -> OrnamentSpec:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=_pairs)
    except (ValueError, UnicodeError) as exc:
        raise SpecValidationError([ValidationIssue("", "json", str(exc))]) from exc
    return normalize_spec(data)
