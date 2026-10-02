"""Versioned, stdlib-only JSON boundary shared with Blender-owned Python."""
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path

VIEWS = ("front", "perspective", "low_side")
OPERATIONS = ("build_stage", "render", "restore")


def contained(path: str | Path, root: str | Path) -> Path:
    resolved, base = Path(path).resolve(), Path(root).resolve()
    if not resolved.is_relative_to(base):
        raise ValueError(f"Path outside allowed workspace: {resolved}")
    return resolved


@dataclass(frozen=True)
class BlenderJob:
    job_version: str
    run_id: str
    stage: int
    seed: int
    input_spec_path: str
    output_directory: str
    requested_operation: str
    requested_validation_views: list[str]
    workspace: str
    run_directory: str
    build_plan_path: str
    result_path: str
    checkpoint_path: str
    input_checkpoint: str | None = None

    def validate(self) -> None:
        if self.job_version != "1.0" or self.requested_operation not in OPERATIONS:
            raise ValueError("Unknown job version or operation")
        if type(self.stage) is not int or not 0 <= self.stage <= 8:
            raise ValueError("Invalid stage")
        if type(self.seed) is not int or self.seed < 0:
            raise ValueError("Invalid seed")
        if not isinstance(self.requested_validation_views, list) or any(
                v not in VIEWS for v in self.requested_validation_views):
            raise ValueError("Unknown validation view")
        run = contained(self.run_directory, self.workspace)
        if run.name != self.run_id or run == Path(self.workspace).resolve():
            raise ValueError("Invalid run identity")
        output = contained(self.output_directory, run)
        for path in (self.result_path, self.checkpoint_path):
            contained(path, output)
        for path in (self.input_spec_path, self.build_plan_path):
            contained(path, run)
        if self.input_checkpoint:
            contained(self.input_checkpoint, run)
        if self.requested_operation != "build_stage" and not self.input_checkpoint:
            raise ValueError("Operation requires an input checkpoint")

    def to_dict(self) -> dict:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "BlenderJob":
        job = cls(**data)
        job.validate()
        return job


@dataclass(frozen=True)
class BlenderResult:
    success: bool
    blender_version: str
    produced_artifacts: list[str]
    geometry_measurements: dict
    warnings: list[str]
    errors: list[str]
    result_version: str = "1.0"

    @classmethod
    def from_dict(cls, data: dict) -> "BlenderResult":
        result = cls(**data)
        if result.result_version != "1.0" or type(result.success) is not bool:
            raise ValueError("Invalid result version/success")
        if not isinstance(result.blender_version, str) or not result.blender_version:
            raise ValueError("Missing Blender version")
        for values in (result.produced_artifacts, result.warnings, result.errors):
            if not isinstance(values, list) or any(not isinstance(s, str) for s in values):
                raise ValueError("Result lists must contain strings")
        if not isinstance(result.geometry_measurements, dict):
            raise ValueError("Geometry measurements must be an object")
        json.dumps(result.geometry_measurements, allow_nan=False)
        if result.success and result.errors:
            raise ValueError("Successful result cannot contain errors")
        return result


def numeric_metric(measurements: dict, name: str) -> float:
    value = measurements[name]
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"Invalid numeric metric: {name}")
    return value
