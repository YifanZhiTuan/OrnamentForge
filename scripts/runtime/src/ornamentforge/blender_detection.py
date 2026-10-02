"""Find an existing Blender installation. Never install or import bpy."""
import os
from pathlib import Path
import re
import shutil
import subprocess
from dataclasses import dataclass


class BlenderUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class BlenderInstallation:
    path: Path
    version: tuple[int, int, int]


def detect_blender(explicit: str | Path | None = None) -> BlenderInstallation:
    candidates = []
    if explicit:
        candidates = [Path(explicit)]
    elif os.environ.get("ORNAMENTFORGE_BLENDER"):
        candidates = [Path(os.environ["ORNAMENTFORGE_BLENDER"])]
    else:
        found = shutil.which("blender")
        if found:
            candidates.append(Path(found))
        for base in (Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Blender Foundation",
                     Path("/Applications/Blender.app/Contents/MacOS"), Path("/usr/bin")):
            candidates.extend(sorted(base.glob("Blender */blender.exe"), reverse=True))
            candidates.append(base / "blender")
    errors = []
    for path in dict.fromkeys(candidates):
        if not path.is_file():
            continue
        try:
            result = subprocess.run([str(path), "--version"], capture_output=True,
                                    text=True, encoding="utf-8", errors="replace", timeout=20,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            match = re.search(r"Blender (\d+)\.(\d+)\.(\d+)", result.stdout)
            if result.returncode or not match:
                raise ValueError("Version probe failed")
            version = tuple(int(n) for n in match.groups())
            if not (4, 2, 0) <= version < (6, 0, 0):
                raise ValueError(f"Unsupported version {version}; require 4.2 through 5.x")
            return BlenderInstallation(path.resolve(), version)
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            errors.append(f"{path}: {exc}")
    raise BlenderUnavailableError("No compatible Blender found. Set ORNAMENTFORGE_BLENDER or --blender. "
                                  + "; ".join(errors))
