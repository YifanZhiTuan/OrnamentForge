"""Unmeasured QA remains unassessed; mock execution cannot certify geometry."""
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Metric:
    name: str
    value: float | None = None
    threshold: float | None = None
    notes: str = "Not measured in Phase 1"


@dataclass(frozen=True)
class MandatoryCheck:
    name: str
    passed: bool | None = None
    notes: str = "Not evaluated"


@dataclass(frozen=True)
class RepairAttempt:
    stage: int
    attempt: int
    action: str
    seed: int
    passed: bool
    error_class: str | None = None


@dataclass
class QAReport:
    visual_metrics: list[Metric] = field(default_factory=list)
    geometry_metrics: list[Metric] = field(default_factory=list)
    mandatory_checks: list[MandatoryCheck] = field(default_factory=list)
    repair_attempts: list[RepairAttempt] = field(default_factory=list)
    final_pass: bool | None = None
    notes: str = "Phase 1 placeholder; no visual or geometry assessment"

    def to_dict(self) -> dict:
        if self.final_pass is True and (not self.mandatory_checks or
                any(c.passed is not True for c in self.mandatory_checks)):
            raise ValueError("Final PASS requires evaluated passing mandatory checks")
        return asdict(self)
