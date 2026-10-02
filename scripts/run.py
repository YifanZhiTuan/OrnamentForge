"""Portable packaging launcher; leaves the Skill and existing workspace files intact."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

RUNTIME = Path(__file__).resolve().parent / "runtime"


def initialize(workspace):
    sources = []
    for directory in ("schemas",):
        sources.extend(p for p in (RUNTIME / directory).rglob("*") if p.is_file())
    # Check all collisions before copying; never overwrite user files.
    for source in sources:
        target = workspace / source.relative_to(RUNTIME)
        if target.exists() and (not target.is_file() or target.read_bytes() != source.read_bytes()):
            raise ValueError(f"Workspace content differs; choose a fresh workspace: {target}")
    for source in sources:
        target = workspace / source.relative_to(RUNTIME)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(source, target)
    print("Workspace initialized; schemas copied. Supply a reference or selected Codex-generated 2D master.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("action", choices=("init", "cli", "module"))
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    skill = RUNTIME.parents[1]
    if workspace == skill or workspace.is_relative_to(skill):
        parser.error("Use an output workspace outside the Skill folder")
    if args.action == "init":
        initialize(workspace)
        return 0
    if not workspace.is_dir():
        parser.error("Initialize a workspace first")
    extra = args.arguments
    if extra and extra[0] == "--":
        extra = extra[1:]
    if args.action == "module":
        if not extra or not extra[0].startswith("ornamentforge."):
            parser.error("module expects an ornamentforge module name")
        module, extra = extra[0], extra[1:]
    else:
        module = "ornamentforge"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(RUNTIME / "src") + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUTF8"] = "1"
    return subprocess.call([sys.executable, "-B", "-m", module, *extra], cwd=workspace, env=env)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f"HOLD: {exc}", file=sys.stderr)
        raise SystemExit(2)
