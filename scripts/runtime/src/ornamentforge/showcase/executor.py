"""Showcase-specific real subprocess adapter; keeps the five executor protocol methods."""
import json
import os
from pathlib import Path
import subprocess

from ..blender_contract import BlenderResult,contained
from ..blender_detection import detect_blender
from ..blender_executor import BlenderExecutionError
from ..qa import QAReport,MandatoryCheck
from ..serialization import write_json
from .motifs import retrieve,register_validated
from .plan import build


class ShowcaseExecutor:
    def __init__(self,workspace,blender=None,refinement=2):
        self.workspace=Path(workspace).resolve();self.installation=detect_blender(blender)
        self.refinement=refinement;self.root=None;self.current_checkpoint=None;self.current_stage=0
        self.job_number=0;self.last_result=None;self.metrics={}

    def initialize_scene(self,spec):
        self.spec=spec;self.definitions,self.usage=retrieve(self.workspace)
        self.plan=build(spec,self.definitions,self.refinement)

    def _bind(self,path):
        if self.root is None:
            self.root=contained(Path(path).parent.parent,self.workspace)
            write_json(self.root/"build_plan.json",self.plan)
            write_json(self.root/"motif_definitions.json",self.definitions)
            write_json(self.root/"motif_usage.json",self.usage)
            write_json(self.root/"provenance.json",{"sources":self.usage,"policy":"Original project motifs only; canonical library verified before use"})

    def execute(self,op,stage,directory,checkpoint,**extra):
        directory=contained(directory,self.root);directory.mkdir(parents=True,exist_ok=True)
        self.job_number+=1;prefix=f"job_{self.job_number:03d}_{op}"
        result_path=directory/(prefix+".result.json")
        job={"job_version":"showcase-1.0","run_id":self.root.name,"stage":stage,"seed":self.spec.seed,
             "input_spec_path":str(self.root/"spec.normalized.json"),"run_directory":str(self.root),
             "output_directory":str(directory),"requested_operation":op,"requested_validation_views":["hero"],
             "checkpoint_path":str(checkpoint),"input_checkpoint":str(self.current_checkpoint) if self.current_checkpoint else None,
             "result_path":str(result_path),**extra}
        jobpath=directory/(prefix+".job.json");write_json(jobpath,job)
        worker=contained(Path(__file__).with_name("worker.py"),self.workspace)
        env=os.environ.copy();scratch=self.root/".blender_runtime";scratch.mkdir(exist_ok=True)
        for key in ("TEMP","TMP","TMPDIR","BLENDER_USER_CONFIG","BLENDER_USER_SCRIPTS","BLENDER_USER_DATAFILES"):env[key]=str(scratch)
        command=[str(self.installation.path),"--background","--factory-startup","--disable-autoexec","--python-exit-code","17","--python",str(worker),"--",str(jobpath),str(self.workspace)]
        print(f"Showcase G{stage}: {op}",flush=True)
        with (directory/(prefix+".log.txt")).open("w",encoding="utf-8") as log:
            process=subprocess.run(command,cwd=self.workspace,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=3600,
                                   creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        if not result_path.is_file():raise BlenderExecutionError(f"Missing result: {result_path}")
        result=BlenderResult.from_dict(json.loads(result_path.read_text(encoding="utf-8")))
        if process.returncode or not result.success:raise BlenderExecutionError("; ".join(result.errors))
        for p in result.produced_artifacts:
            if not contained(p,self.root).is_file():raise BlenderExecutionError(f"Missing artifact {p}")
        self.last_result=result;self.metrics=result.geometry_measurements
        return result

    def save_checkpoint(self,path):
        path=Path(path).resolve();self._bind(path);stage=int(path.stem[1:3]);output=path.with_suffix(".blend")
        self.execute("build_stage",stage,path.parent,output)
        write_json(path.parent/"qa.report.json",self.metrics)
        if self.metrics.get("final_pass") is False:
            raise BlenderExecutionError("Showcase gate failed: "+str(self.metrics["checks"]))
        self.current_checkpoint=output;self.current_stage=stage
        if stage==3:register_validated(self.workspace,self.root,self.definitions,self.usage,self.metrics)
        return output

    def render_validation_views(self,directory):
        self.execute("render",self.current_stage,directory,Path(directory)/"unused.blend")
        return [Path(directory)/"validation.png"]

    def export_placeholder_report(self,path,report):
        path=Path(path).with_name("qa.report.json");write_json(path,self.metrics);return path

    def restore_checkpoint(self,path):
        old=self.current_checkpoint;self.current_checkpoint=contained(path,self.root)
        stage=int(Path(path).stem[1:3])
        try:self.execute("restore",stage,Path(path).parent,Path(path))
        except Exception:self.current_checkpoint=old;raise
        self.current_stage=stage
