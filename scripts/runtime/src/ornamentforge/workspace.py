"""Fresh deterministic run allocation and persisted stage orchestration."""
from dataclasses import asdict
from pathlib import Path

from .checkpoints import Checkpoint, artifact_hash
from .execution import BlenderExecutor
from .models import OrnamentSpec
from .qa import QAReport
from .serialization import utc_now, write_json
from .spec import normalize_spec
from .stages import Stage, StageMachine, StageResult, Status


class RunContext:
    def __init__(self, root: Path, spec: OrnamentSpec, executor: BlenderExecutor):
        self.root, self.spec, self.executor = root, spec, executor
        self.machine = StageMachine()
        self.checkpoints: list[Checkpoint] = []
        self.active_checkpoint: str | None = None

    @classmethod
    def create(cls, spec: OrnamentSpec, executor: BlenderExecutor,
               runs_dir: str | Path = "runs") -> "RunContext":
        spec = normalize_spec(spec.to_dict())
        runs = Path(runs_dir).resolve()
        runs.mkdir(parents=True, exist_ok=True)
        suffix = 0
        while True:
            run_id = spec.spec_hash + (f"-{suffix}" if suffix else "")
            root = runs / run_id
            try:
                root.mkdir()
                break
            except FileExistsError:
                suffix += 1
        context = cls(root, spec, executor)
        for stage in Stage:
            if stage.value:
                (root / stage.folder).mkdir()
        write_json(root / "spec.normalized.json", spec.to_dict())
        write_json(root / "metadata.json", {"run_id": run_id, "spec_hash": spec.spec_hash,
                   "seed": spec.seed, "created_time": utc_now(), "version": "0.1.0",
                   "executor": type(executor).__name__})
        write_json(root / "seed.json", {"seed": spec.seed})
        write_json(root / "provenance.json", {"version": "1.0", "sources": []})
        context.persist()
        try:
            executor.initialize_scene(spec)
            context.finish(Status.PASS, notes="Validated spec and initialized execution adapter")
        except Exception as exc:
            context.finish(Status.FAIL, type(exc).__name__, str(exc))
            raise
        return context

    def persist(self) -> None:
        write_json(self.root / "stage_state.json", {**self.machine.to_dict(),
                   "active_checkpoint": self.active_checkpoint,
                   "checkpoints": [c.to_dict() for c in self.checkpoints]})

    def advance(self, target: Stage) -> None:
        self.machine.advance(target)
        self.persist()

    def finish(self, status: Status, error_class: str | None = None, notes: str = "") -> None:
        stage = self.machine.current
        result = StageResult(stage, status, error_class=error_class, notes=notes)
        directory = self.root / stage.folder if stage.value else self.root / "intake"
        if status == Status.PASS:
            try:
                checkpoint_id = f"G{stage.value:02d}-{len(self.checkpoints):04d}"
                path = self.executor.save_checkpoint(directory / f"{checkpoint_id}.checkpoint")
                relative = path.resolve().relative_to(self.root.resolve()).as_posix()
                checkpoint = Checkpoint(checkpoint_id, stage, relative, self.spec.spec_hash,
                                        self.spec.seed, status, artifact_hash(path),
                                        parent_checkpoint=self.active_checkpoint)
                if 2 <= stage.value <= 7:
                    views = self.executor.render_validation_views(directory / checkpoint_id)
                    if not views or any(not p.is_file() or not p.resolve().is_relative_to(self.root)
                                        for p in views):
                        raise ValueError("Validation views missing or outside workspace")
                    self.executor.export_placeholder_report(directory / "qa.placeholder.json", QAReport())
                write_json(directory / "stage_report.json", asdict(result))
                self.checkpoints.append(checkpoint)
                self.active_checkpoint = checkpoint_id
            except Exception as exc:
                failure = StageResult(stage, Status.FAIL, error_class=type(exc).__name__, notes=str(exc))
                self.machine.record(failure)
                write_json(directory / "stage_report.json", asdict(failure))
                self.persist()
                raise
        else:
            write_json(directory / "stage_report.json", asdict(result))
        self.machine.record(result)
        self.persist()

    def rollback(self) -> Checkpoint:
        target = self.machine.rollback_target()
        checkpoint = next(c for c in reversed(self.checkpoints) if c.stage == target)
        path = checkpoint.verify(self.root, self.spec.spec_hash, self.spec.seed)
        self.executor.restore_checkpoint(path)
        self.machine.rollback()
        self.active_checkpoint = checkpoint.checkpoint_id
        self.persist()
        return checkpoint
