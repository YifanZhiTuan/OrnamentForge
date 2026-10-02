"""Real executor: host Python launches a fixed Blender-owned worker via JSON."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import re
import subprocess

from .current.composition.b01 import build_plan
from .b01_qa import assess_b01
from .current.library.retrieval import B01Resolver
from .blender_contract import BlenderJob, BlenderResult, VIEWS, contained
from .blender_detection import BlenderInstallation, detect_blender
from .models import OrnamentSpec
from .qa import QAReport
from .serialization import write_json


class BlenderExecutionError(RuntimeError):
    pass


class RealBlenderExecutor:
    """Implements all five existing BlenderExecutor methods. One adapter per run."""
    def __init__(self, workspace: str | Path, installation: BlenderInstallation | None = None,
                 parameters: dict | None = None, timeout: int = 240, allow_user: bool = False):
        self.workspace = Path(workspace).resolve()
        self.installation = installation or detect_blender()
        self.parameters, self.timeout = parameters, timeout
        self.spec = None
        self.plan = None
        self.root = None
        self.current_checkpoint = None
        self.current_stage = 0
        self.last_result = None
        self.qa_report = QAReport()
        self.job_number = 0
        self.resolver = B01Resolver(self.workspace,allow_user)

    def initialize_scene(self, spec: OrnamentSpec) -> None:
        # Scene creation is deferred to the first save, when RunContext supplies its root.
        self.spec = spec
        self.plan = build_plan(spec,self.parameters,self.resolver)

    def _bind(self, checkpoint_path: Path) -> None:
        if self.spec is None:
            raise BlenderExecutionError("Initialize scene first")
        contained(checkpoint_path,self.workspace)
        if self.root is None:
            root = checkpoint_path.parent.parent.resolve()
            contained(root,self.workspace)
            if not (root/"spec.normalized.json").is_file():
                raise BlenderExecutionError("RunContext workspace required")
            self.root = root
            write_json(root/"build_plan.json",self.plan)
            self.resolver.persist(root)
            write_json(root/"blender_installation.json",{"path":str(self.installation.path),
                       "version":list(self.installation.version)})

    def _execute(self, operation: str, stage: int, directory: Path, checkpoint: Path,
                 views: list[str] | None = None) -> BlenderResult:
        directory = contained(directory,self.root)
        directory.mkdir(parents=True,exist_ok=True)
        self.job_number += 1
        prefix = f"job_{self.job_number:03d}_{operation}"
        job = BlenderJob("1.0",self.root.name,stage,self.spec.seed,
                         str(self.root/"spec.normalized.json"),str(directory),operation,views or [],
                         str(self.workspace),str(self.root),str(self.root/"build_plan.json"),
                         str(directory/(prefix+".result.json")),str(checkpoint),
                         str(self.current_checkpoint) if self.current_checkpoint else None)
        job_path = directory/(prefix+".job.json")
        write_json(job_path,job.to_dict())
        worker = contained(Path(__file__).with_name("blender_worker.py"),self.workspace)
        scratch = self.root/".blender_runtime"
        scratch.mkdir(exist_ok=True)
        environment = os.environ.copy()
        for key in ("TEMP","TMP","TMPDIR","BLENDER_USER_CONFIG","BLENDER_USER_SCRIPTS","BLENDER_USER_DATAFILES"):
            environment[key] = str(scratch)
        command = [str(self.installation.path),"--background","--factory-startup","--disable-autoexec",
                   "--python-exit-code","17","--python",str(worker),"--",str(job_path),str(self.workspace)]
        try:
            process = subprocess.run(command,cwd=self.workspace,env=environment,capture_output=True,
                                     text=True,encoding="utf-8",errors="replace",timeout=self.timeout,
                                     creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        except (OSError,subprocess.TimeoutExpired) as exc:
            write_json(Path(job.result_path),{"result_version":"1.0","success":False,
                       "blender_version":".".join(map(str,self.installation.version)),"produced_artifacts":[],
                       "geometry_measurements":{},"warnings":[],"errors":[str(exc)]})
            raise BlenderExecutionError(str(exc)) from exc
        (directory/(prefix+".log.txt")).write_text(process.stdout+process.stderr,encoding="utf-8")
        try:
            result = BlenderResult.from_dict(json.loads(Path(job.result_path).read_text(encoding="utf-8")))
        except (OSError,ValueError,TypeError) as exc:
            raise BlenderExecutionError(f"Invalid or missing Blender result; see {prefix}.log.txt") from exc
        self.last_result = result
        if process.returncode or not result.success:
            raise BlenderExecutionError(f"Blender exit {process.returncode}: {'; '.join(result.errors)}")
        for artifact in result.produced_artifacts:
            if not contained(artifact,directory).is_file():
                raise BlenderExecutionError(f"Missing Blender artifact: {artifact}")
        return result

    def save_checkpoint(self,path: Path) -> Path:
        path = Path(path).resolve()
        self._bind(path)
        match = re.fullmatch(r"G(\d{2})-\d+",path.stem)
        if not match:
            raise BlenderExecutionError("Expected stage checkpoint name from RunContext")
        stage = int(match.group(1))
        output = path.with_suffix(".blend")
        result = self._execute("build_stage",stage,path.parent,output)
        if str(output) not in result.produced_artifacts or not output.is_file():
            raise BlenderExecutionError("Real .blend checkpoint missing")
        self.qa_report = assess_b01(self.plan,result.geometry_measurements,stage)
        write_json(path.parent/"qa.report.json",self.qa_report.to_dict())
        if self.qa_report.final_pass is False:
            raise BlenderExecutionError("B01 QA failed: "+", ".join(c.name for c in self.qa_report.mandatory_checks if not c.passed))
        self.current_checkpoint, self.current_stage = output,stage
        return output

    def restore_checkpoint(self,path: Path) -> None:
        path = contained(path,self.root)
        stage = int(path.stem[1:3])
        previous = self.current_checkpoint
        self.current_checkpoint = path
        try:
            result = self._execute("restore",stage,path.parent,path)
        except Exception:
            self.current_checkpoint = previous
            raise
        self.current_stage = stage
        self.qa_report = assess_b01(self.plan,result.geometry_measurements,stage)

    def render_validation_views(self,directory: Path) -> list[Path]:
        directory = contained(directory,self.root)
        self._execute("render",self.current_stage,directory,directory/"unused.blend",list(VIEWS))
        paths = [directory/(view+".png") for view in VIEWS]
        for path in paths:
            if not path.is_file() or path.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
                raise BlenderExecutionError(f"Missing/invalid render: {path}")
        return paths

    def export_placeholder_report(self,path: Path,report: QAReport) -> Path:
        # Retain the Phase 1 protocol; real path exports measured QA, never a mock placeholder.
        output = contained(path,self.root).with_name("qa.report.json")
        write_json(output,{"mock":False,**self.qa_report.to_dict()})
        return output
