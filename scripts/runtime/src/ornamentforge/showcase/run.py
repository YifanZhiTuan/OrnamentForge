"""One-command staged sphere showcase, portable artifacts and video capture."""
import json
from pathlib import Path
import shutil
import subprocess
import time

from ..serialization import write_json
from ..spec import load_spec
from ..stages import Stage,Status
from ..workspace import RunContext
from .executor import ShowcaseExecutor
from .plan import build
from .delivery import verify_artifacts,encode_process


def run(workspace,spec_path,blender=None,refinement=2,turntable=False,preview=False):
    workspace=Path(workspace).resolve();spec=load_spec(spec_path);start=time.perf_counter()
    executor=ShowcaseExecutor(workspace,blender,refinement)
    run=RunContext.create(spec,executor,workspace/"runs"/"current"/"showcase"/"runs")
    try:
        for stage in list(Stage)[1:]:
            run.advance(stage);run.finish(Status.PASS,notes="Automated spherical botanical showcase")
        # Compare a rebuilt plan from retrieved definitions before spending on final renders.
        again=build(spec,executor.definitions,refinement)
        deterministic=again["plan_hash"]==executor.plan["plan_hash"]
        write_json(run.root/"determinism.json",{"same_seed_plan_equal":deterministic,"plan_hash":again["plan_hash"],
                                               "scope":"Complete generated geometry plan, no timestamps or Blender IDs"})
        if not deterministic:raise ValueError("Nondeterministic showcase plan")
        if not preview:executor.execute("final_render",8,run.root,run.root/"final_showcase.blend")
        else:
            shutil.copy2(executor.current_checkpoint,run.root/"editable_showcase.blend")
            shutil.copy2(executor.current_checkpoint,run.root/"final_showcase.blend")
        artifact_checks=verify_artifacts(run.root,preview)
        executor.execute("verify_determinism",8,run.root,run.root/"final_showcase.blend")
        ffmpeg=shutil.which("ffmpeg")
        if ffmpeg:encode_process(run.root,ffmpeg)
        if turntable:
            executor.execute("turntable",8,run.root,run.root/"final_showcase.blend",frames=72)
            ffmpeg=shutil.which("ffmpeg")
            if ffmpeg:
                subprocess.run([ffmpeg,"-y","-framerate","12","-i",str(run.root/"turntable/frame_%04d.png"),
                                "-c:v","libx264","-crf","18","-pix_fmt","yuv420p",str(run.root/"turntable.mp4")],
                               check=True,capture_output=True,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        write_json(run.root/"qa_report.json",executor.metrics)
        report={"status":"PASS","run_directory":str(run.root),"elapsed_seconds":time.perf_counter()-start,
                "blender_path":str(executor.installation.path),"blender_version":executor.installation.version,
                "spec_hash":spec.spec_hash,"seed":spec.seed,"input":spec.to_dict()["input"],
                "artifact_checks":artifact_checks,
                "refinement":refinement,"counts":executor.metrics,"motif_usage":executor.usage,
                "deterministic":deterministic,"exclusion_repairs":executor.plan["exclusion_actions"],
                "artifacts":{"editable":str(run.root/"editable_showcase.blend"),"final":str(run.root/"final_showcase.blend"),
                             "renders":str(run.root/"renders"),"stages":str(run.root/"stages"),"turntable":str(run.root/"turntable.mp4") if turntable else None}}
        write_json(run.root/"showcase_report.json",report)
        write_json(workspace/"runs/current/showcase/LATEST.json",{"run":str(run.root),"report":str(run.root/"showcase_report.json")})
        if executor.plan.get('detail_upgrade') and not preview:
            from .delivery import publish
            publish(workspace,run.root,report)
        print(json.dumps({"run":str(run.root),"elapsed_seconds":report["elapsed_seconds"]}),flush=True)
        return run
    except Exception as exc:
        run.finish(Status.FAIL,type(exc).__name__,str(exc))
        try:checkpoint=run.rollback();rollback=checkpoint.to_dict()
        except Exception as rollback_exc:rollback={"error":str(rollback_exc)}
        write_json(run.root/"showcase_failure.json",{"error":str(exc),"rollback":rollback})
        raise
