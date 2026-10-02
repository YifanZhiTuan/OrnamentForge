"""Evidence-bound visual gates. Success of Blender is never visual approval."""
import hashlib
import json
from pathlib import Path

from ornamentforge.serialization import write_json
from ..composition.planar_composer import canonical_hash
from .review import evaluate_review


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def local_file(root, path):
    root = Path(root).resolve()
    path = Path(path)
    path = (root/path).resolve() if not path.is_absolute() else path.resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError(f"Missing or nonlocal evidence: {path}")
    return path


def assess(root, review):
    root = Path(root).resolve()
    phase = review.get("phase")
    if phase not in ("macro", "meso", "final"):
        raise ValueError("A geometry gate needs macro, meso or final review")
    plan = json.loads((root/"ArtPlan.json").read_text(encoding="utf-8"))
    if review.get("plan_hash") != canonical_hash(plan):
        raise ValueError("Review belongs to a different ArtPlan")
    result = json.loads((root/"blender_result.json").read_text(encoding="utf-8"))
    if result.get("phase") != phase or result.get("success") is not True:
        raise ValueError("Review requires successful geometry of the same phase")
    checkpoint = local_file(root, result["artifacts"]["checkpoint"])
    evidence = {}
    for group in ("aesthetic", "fidelity"):
        for entry in review.get(group, {}).values():
            if not isinstance(entry, dict):
                raise ValueError("Scores must be structured observations")
            if entry.get("score") is not None:
                path = local_file(root, entry.get("evidence", ""))
                if path.suffix.lower() != ".png" or path.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
                    raise ValueError("Visual evidence must be a real PNG render")
                # Evidence must be emitted by this build, not an older image in the folder.
                if str(path) not in result["artifacts"].values():
                    raise ValueError("Evidence is not an artifact of this build")
                evidence[path.relative_to(root).as_posix()] = digest(path)
    evaluation = evaluate_review(plan["intent"]["mode"], phase, review.get("aesthetic", {}),
                                 review.get("fidelity", {}), review.get("blockers", []))
    geometry_evidence = None
    if phase == "final":
        qa_path = root/"geometry_qa.json"
        if not qa_path.is_file():
            raise ValueError("Final approval requires measured geometry QA")
        qa = json.loads(qa_path.read_text(encoding="utf-8"))
        checks = qa.get("mandatory_checks", [])
        if qa.get("final_pass") is not True or not checks or any(c.get("passed") is not True for c in checks):
            raise ValueError("Final geometry QA has not passed every mandatory check")
        if qa.get("checkpoint_sha256") != digest(checkpoint):
            raise ValueError("Geometry QA belongs to a different checkpoint")
        geometry_evidence = digest(qa_path)
    return {"version": "3.0", "phase": phase, "plan_hash": canonical_hash(plan),
            "checkpoint": checkpoint.relative_to(root).as_posix(),
            "checkpoint_sha256": digest(checkpoint), "evidence_sha256": evidence,
            "review": review, "evaluation": evaluation, "geometry_qa_sha256": geometry_evidence}


def record_review(root, review):
    root = Path(root).resolve()
    receipt = assess(root, review)
    target = root/(receipt["phase"]+"_review.json")
    if target.exists():
        raise ValueError("Review already exists; preserve it and use a new iteration folder")
    write_json(target, receipt)
    return receipt


def verify_gate(root, phase):
    root = Path(root).resolve()
    saved = json.loads((root/(phase+"_review.json")).read_text(encoding="utf-8"))
    fresh = assess(root, saved["review"])
    if fresh != saved:
        raise ValueError("Stage evidence changed since review; re-review the current build")
    if fresh["evaluation"]["gate"] != "PASS":
        raise ValueError("Stage is HOLD; repair before proceeding")
    return fresh
