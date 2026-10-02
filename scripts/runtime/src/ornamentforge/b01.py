"""Stage-gated B01 vertical slice and evidence-based deterministic rerun."""
import json
from pathlib import Path

from .blender_contract import contained
from .blender_detection import detect_blender
from .blender_executor import RealBlenderExecutor
from .serialization import write_json
from .spec import load_spec
from .stages import Stage, Status
from .workspace import RunContext


def run_b01(workspace: Path, spec_path: Path, parameters: dict | None = None,
            blender: str | Path | None = None, allow_user: bool = False) -> RunContext:
    workspace = Path(workspace).resolve()
    spec_path = contained(spec_path,workspace)
    installation = detect_blender(blender)
    adapter = RealBlenderExecutor(workspace,installation,parameters,allow_user=allow_user)
    run = RunContext.create(load_spec(spec_path),adapter,workspace/"runs")
    try:
        for stage in list(Stage)[1:]:
            run.advance(stage)
            run.finish(Status.PASS,notes="Real Blender B01 measured stage gate")
            if stage == Stage.G3_MOTIF:
                adapter.resolver.register_misses(run.root,adapter.plan,adapter.last_result.geometry_measurements)
        views = adapter.render_validation_views(run.root/Stage.G8_FINAL.folder/"validation")
        write_json(run.root/"b01_summary.json",{"benchmark":"B01","spec_hash":run.spec.spec_hash,
                   "seed":run.spec.seed,"blender_path":str(installation.path),"blender_version":list(installation.version),
                   "checkpoint":str(adapter.current_checkpoint),"validation_renders":[str(p) for p in views],
                   "qa":adapter.qa_report.to_dict(),"parameters":adapter.plan["parameters"],
                   "selected_motifs":adapter.resolver.sources,"generation_calls":adapter.resolver.generation_calls})
    except Exception as exc:
        run.finish(Status.FAIL,type(exc).__name__,str(exc))
        try:
            restored = run.rollback()
            write_json(run.root/"failure.json",{"error_class":type(exc).__name__,"error":str(exc),
                       "rollback_checkpoint":restored.to_dict()})
        except Exception as rollback_error:
            write_json(run.root/"failure.json",{"error_class":type(exc).__name__,"error":str(exc),
                       "rollback_error":str(rollback_error)})
        raise
    return run


def compare_runs(first: RunContext, second: RunContext) -> dict:
    def read(run,path):
        return json.loads((run.root/path).read_text(encoding="utf-8"))
    a,b = read(first,"build_plan.json"),read(second,"build_plan.json")
    sa,sb = read(first,"G08_final/scene_snapshot.json"),read(second,"G08_final/scene_snapshot.json")
    checks = {"normalized_spec_hash":first.spec.spec_hash==second.spec.spec_hash,
              "selected_motif_ids":{k:v["id"] for k,v in a.get("motif_sources",{}).items()} ==
                                   {k:v["id"] for k,v in b.get("motif_sources",{}).items()},
              "build_plan":a==b,"build_plan_parameters":a["parameters"]==b["parameters"],
              "vine_control_points":sa["vine_control_points"]==sb["vine_control_points"],
              "leaf_transforms":sa["leaf_transforms"]==sb["leaf_transforms"]}
    result = {"runs":[str(first.root),str(second.root)],"checks":checks,"passed":all(checks.values()),
              "note":"Compared actual Blender scene snapshots; file bytes/timestamps/internal IDs excluded"}
    write_json(second.root/"determinism.json",result)
    if not result["passed"]:
        raise RuntimeError("B01 deterministic rerun mismatch")
    return result
