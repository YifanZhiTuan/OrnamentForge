"""Checkpoint metadata and integrity verification before restoration."""
import hashlib
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .serialization import utc_now
from .stages import Stage, Status


def artifact_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class Checkpoint:
    checkpoint_id: str
    stage: Stage
    artifact_path: str
    spec_hash: str
    seed: int
    status: Status
    artifact_hash: str
    created_time: str = field(default_factory=utc_now)
    parent_checkpoint: str | None = None

    def verify(self, root: Path, spec_hash: str, seed: int) -> Path:
        path = (root / self.artifact_path).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("Checkpoint escapes run workspace")
        if self.status != Status.PASS or self.spec_hash != spec_hash or self.seed != seed:
            raise ValueError("Checkpoint is not a passing checkpoint for this spec")
        if artifact_hash(path) != self.artifact_hash:
            raise ValueError("Checkpoint artifact integrity failure")
        return path

    def to_dict(self) -> dict:
        return asdict(self)
