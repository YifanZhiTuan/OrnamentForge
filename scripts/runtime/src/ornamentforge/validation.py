"""Use the authoritative Draft 2020-12 schema without coercion or defaults."""
import json
import sysconfig
from dataclasses import asdict, dataclass
from pathlib import Path

from jsonschema import Draft202012Validator


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    keyword: str
    message: str
    schema_path: str = ""


class SpecValidationError(ValueError):
    def __init__(self, issues: list[ValidationIssue]):
        self.issues = issues
        super().__init__("; ".join(f"{i.path or '/'}: {i.message}" for i in issues))

    def to_dict(self) -> dict:
        return {"valid": False, "errors": [asdict(i) for i in self.issues]}


def schema_path() -> Path:
    source = Path(__file__).resolve().parents[2] / "schemas/ornament_spec.schema.json"
    if source.is_file():
        return source
    return Path(sysconfig.get_path("data")) / "share/ornamentforge/schemas/ornament_spec.schema.json"


def pointer(parts) -> str:
    return "".join("/" + str(p).replace("~", "~0").replace("/", "~1") for p in parts)


def validate_spec(data: object) -> None:
    schema = json.loads(schema_path().read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(data),
                    key=lambda e: (pointer(e.absolute_path), e.message))
    if errors:
        raise SpecValidationError([ValidationIssue(pointer(e.absolute_path), str(e.validator),
                                  e.message, pointer(e.absolute_schema_path)) for e in errors])
