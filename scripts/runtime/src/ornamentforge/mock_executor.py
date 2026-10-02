"""Explicit JSON simulations, never fake .blend files or real renders."""
import json
from pathlib import Path

from .models import OrnamentSpec
from .qa import QAReport
from .serialization import write_json


class MockBlenderExecutor:
    def __init__(self):
        self.scene: dict | None = None

    def initialize_scene(self, spec: OrnamentSpec) -> None:
        self.scene = {"mock": True, "spec_hash": spec.spec_hash, "seed": spec.seed, "objects": []}

    def _require_scene(self):
        if self.scene is None:
            raise RuntimeError("Initialize scene first")

    def save_checkpoint(self, path: Path) -> Path:
        self._require_scene()
        write_json(path, self.scene)
        return path

    def restore_checkpoint(self, path: Path) -> None:
        scene = json.loads(path.read_text(encoding="utf-8"))
        if scene.get("mock") is not True or not isinstance(scene.get("objects"), list):
            raise ValueError("Invalid mock checkpoint")
        self.scene = scene

    def render_validation_views(self, directory: Path) -> list[Path]:
        self._require_scene()
        paths = []
        for view in ("front", "side", "top"):
            path = directory / f"{view}.mock-view.json"
            write_json(path, {"mock": True, "view": view, "scene": self.scene})
            paths.append(path)
        return paths

    def export_placeholder_report(self, path: Path, report: QAReport) -> Path:
        self._require_scene()
        write_json(path, {"mock": True, **report.to_dict()})
        return path
