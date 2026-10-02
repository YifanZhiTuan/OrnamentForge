"""Blender-independent, auditable stage gate state machine."""
from dataclasses import asdict, dataclass, field
from enum import IntEnum, StrEnum

from .serialization import utc_now


class Stage(IntEnum):
    G0_INTAKE = 0
    G1_ANALYSIS = 1
    G2_BASE = 2
    G3_MOTIF = 3
    G4_LAYOUT = 4
    G5_CONFORM = 5
    G6_RELIEF = 6
    G7_QA = 7
    G8_FINAL = 8

    @property
    def folder(self) -> str:
        return f"G{self.value:02d}_{self.name.split('_', 1)[1].lower()}"


class Status(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


class StageTransitionError(ValueError):
    pass


@dataclass(frozen=True)
class StageResult:
    stage: Stage
    status: Status
    timestamp: str = field(default_factory=utc_now)
    error_class: str | None = None
    notes: str = ""

    def __post_init__(self):
        if not isinstance(self.stage, Stage) or not isinstance(self.status, Status):
            raise ValueError("Stage and status must be enum values")
        if self.status == Status.FAIL and not self.error_class:
            raise ValueError("Failed stages require an error class")
        if self.status == Status.PASS and self.error_class:
            raise ValueError("Passing stages cannot carry an error class")


class StageMachine:
    def __init__(self):
        self.current = Stage.G0_INTAKE
        self.results: dict[Stage, StageResult] = {}
        self.history: list[dict] = []

    def record(self, result: StageResult) -> None:
        if result.stage != self.current:
            raise StageTransitionError("Result must belong to current stage")
        self.results[self.current] = result
        self.history.append({"event": "result", **asdict(result)})

    def advance(self, target: Stage) -> None:
        result = self.results.get(self.current)
        if not isinstance(target, Stage) or target.value != self.current.value + 1:
            raise StageTransitionError("Stages must advance exactly one step")
        if result is None or result.status != Status.PASS:
            raise StageTransitionError("Current stage must PASS before advancing")
        self.current = target
        self.history.append({"event": "advance", "stage": target, "timestamp": utc_now()})

    def rollback_target(self) -> Stage:
        passing = [s for s, r in self.results.items()
                   if s < self.current and r.status == Status.PASS]
        if not passing:
            raise StageTransitionError("No earlier passing stage exists")
        return max(passing)

    def rollback(self) -> Stage:
        target = self.rollback_target()
        self.results = {s: r for s, r in self.results.items() if s <= target}
        self.current = target
        self.history.append({"event": "rollback", "stage": target, "timestamp": utc_now()})
        return target

    def to_dict(self) -> dict:
        return {"current": self.current, "results": {s.name: asdict(r) for s, r in self.results.items()},
                "history": self.history}
