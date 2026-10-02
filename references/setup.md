# Portable setup

Resolve SKILL_ROOT to the folder containing SKILL.md. Choose a separate WORKSPACE
for each project. Place a Python 3.11+ virtual environment outside SKILL_ROOT.
Python 3.11 is the release smoke-test environment. Install only into that chosen
environment, not a global interpreter:

```text
python -m venv <environment-directory>
<environment-python> -m pip install -r <SKILL_ROOT>/scripts/requirements.txt
<environment-python> <SKILL_ROOT>/scripts/run.py --workspace <WORKSPACE> init
<environment-python> <SKILL_ROOT>/scripts/run.py --workspace <WORKSPACE> cli --help
```

These angle-bracket values are invocation parameters to resolve locally, not literal
paths. Quote paths with spaces. Windows environment Python is Scripts/python.exe;
POSIX is bin/python. The launcher resolves bundled runtime from its own file and
sets the child process working directory to WORKSPACE. All subsequent relative
CLI inputs and outputs are relative to WORKSPACE. Init refuses conflicting files.
It copies required schemas and creates the workspace; it does not generate images.

Blender is separate: existing 4.2–5.x installation, with its bundled bpy and NumPy.
Use `blender` on PATH or set ORNAMENTFORGE_BLENDER to the local executable. Explicit
`--blender` is supported by the dense engraving command. Missing Blender is HOLD;
do not install Blender or change system configuration implicitly. GPU is optional.
Large dense meshes consume substantial memory; begin with the existing bounded
settings and preserve the actual resolution in QA.

For task-local Python using API examples, prepend the resolved
`<SKILL_ROOT>/scripts/runtime/src` to sys.path before importing ornamentforge, and
run with WORKSPACE as cwd. Do not pip-install a different ornamentforge package.
The bundled module tree is retained in source layout because schema lookup depends on that layout.

Installation in Codex: copy the inner `ornamentforge/` directory to the user's
configured Codex skills directory, or a project's `.agents/skills/ornamentforge/`.
Start a fresh chat and invoke `$ornamentforge`. Alternatively ask a chat to read
the absolute path to this SKILL.md and follow it; this does not require installation.
Keep this entire folder together when relocating. No original checkout is needed.

At runtime DesignHandoff intentionally resolves current image paths to absolute
paths and binds file hashes. This is provenance, not a hard-coded installation
path. Moving an existing run requires explicit rebinding and revalidation of its
handoff; never silently rewrite a signed/hash-bound record.
