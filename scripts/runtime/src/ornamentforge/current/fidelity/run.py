"""Persist intake and run the fixed Blender worker, initially to the Macro gate."""
import argparse
import json
import subprocess
import shutil
from pathlib import Path

from ornamentforge.blender_detection import detect_blender
from ornamentforge.serialization import write_json
from ornamentforge.spec import normalize_spec
from ..composition.planar_composer import create_art_plan, create_ornament_spec, canonical_hash
from ..library.art_references import retrieve_references
from ..qa.gates import verify_gate, record_review


def run(workspace, prompt, family=None, seed=20260923, reference=None, opening_seed=None, direction=1):
    workspace = Path(workspace).resolve()
    references = [str(Path(reference).resolve())] if reference else []
    plan = create_art_plan(prompt, seed, family, references)
    chosen = plan["composition_directions"][direction-1]
    plan["selected_direction"] = chosen["id"]
    plan["handoff"]["selected_direction"] = chosen["id"]
    spec = normalize_spec(create_ornament_spec(plan))
    parent = workspace / "runs/current/reference"
    parent.mkdir(parents=True, exist_ok=True)
    stem = plan["id"].lower()
    suffix = 0
    while True:
        root = parent / (stem + (f"-{suffix}" if suffix else ""))
        try:
            root.mkdir()
            break
        except FileExistsError:
            suffix += 1
    from ..input.router import ObjectFamily
    selection = retrieve_references(workspace, ObjectFamily(plan["input"]["object_family"]),
                                    prompt, primary_reference=reference)
    write_json(root/"ArtPlan.json", plan)
    write_json(root/"OrnamentSpec.json", spec.to_dict())
    write_json(root/"references.json", selection)
    installation = detect_blender()
    config = {"output_directory": str(root), "seed": seed, "phase": "macro",
              "object_family": plan["input"]["object_family"], "intent_mode": plan["intent"]["mode"],
              "plan_hash": canonical_hash(plan), "spec_hash": spec.spec_hash}
    config["geometry_parameters"] = chosen.get("geometry_parameters", {})
    if plan["intent"]["mode"] == "MODE_C_REFERENCE_EXACT":
        from .reconstruction import decompose_flat_art
        config["reconstruction"] = decompose_flat_art(reference, opening_seed=opening_seed,
            contour_tolerance=config["geometry_parameters"].get("contour_tolerance",.65))
        write_json(root/"reference_decomposition.json", config["reconstruction"])
    write_json(root/"job.json", config)
    execute(workspace, root, installation)
    return root


def execute(workspace, root, installation):
    worker = Path(__file__).resolve().parents[1]/"blender"/"reference_worker.py"
    command = [str(installation.path), "--background", "--factory-startup", "--disable-autoexec",
               "--python-exit-code", "17", "--python", str(worker), "--", str(root/"job.json")]
    print(json.dumps({"run": str(root)}), flush=True)
    with (root/"blender.log").open("w", encoding="utf-8") as log:
        process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, cwd=workspace,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=900)
    result_path = root/"blender_result.json"
    result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else {}
    if process.returncode or not result.get("success"):
        raise RuntimeError(f"Blender failed; inspect {root/'blender.log'}: {result.get('error')}")
    return result


def resume(root, phase):
    root = Path(root).resolve()
    predecessor = {"meso": "macro", "micro": "meso"}.get(phase)
    if predecessor is None:
        raise ValueError("Resume requires meso or micro")
    receipt = verify_gate(root, predecessor)
    config = json.loads((root/"job.json").read_text(encoding="utf-8"))
    suffix = 0
    while True:
        child = root.parent/(root.name+"_"+phase+(f"-{suffix}" if suffix else ""))
        try:
            child.mkdir()
            break
        except FileExistsError:
            suffix += 1
    for name in ("ArtPlan.json", "OrnamentSpec.json", "references.json"):
        shutil.copy2(root/name, child/name)
    config.update(output_directory=str(child), phase=phase, parent_run=str(root))
    write_json(child/"job.json", config)
    write_json(child/"approved_parent.json", receipt)
    execute(root.parent.parent.parent, child, detect_blender())
    return child


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--prompt")
    parser.add_argument("--resume")
    parser.add_argument("--phase", choices=["meso", "micro"])
    parser.add_argument("--review-run")
    parser.add_argument("--review-file")
    parser.add_argument("--family")
    parser.add_argument("--seed", type=int, default=20260923)
    parser.add_argument("--reference")
    parser.add_argument("--opening-seed", type=float, nargs=2)
    parser.add_argument("--direction", type=int, choices=[1,2,3], default=1)
    parser.add_argument("--all-directions", action="store_true")
    args = parser.parse_args()
    if args.review_run:
        if not args.review_file: parser.error("--review-file required")
        review=json.loads(Path(args.review_file).read_text(encoding="utf-8"))
        print(json.dumps(record_review(args.review_run,review),ensure_ascii=False))
        return
    if args.resume:
        print(resume(args.resume,args.phase))
        return
    if not args.prompt: parser.error("--prompt required for a new design")
    for direction in ([1,2,3] if args.all_directions else [args.direction]):
        print(run(args.workspace, args.prompt, args.family, args.seed, args.reference, args.opening_seed, direction))


if __name__ == "__main__":
    main()
