"""Aesthetic/fidelity gates and deterministic repair routing."""
from __future__ import annotations

from dataclasses import dataclass
import math

from ..input.router import IntentMode


AESTHETIC_WEIGHTS = {
    "silhouette": 14, "hierarchy": 13, "flow": 12, "negative_space": 11,
    "border_opening_integration": 10, "motif_coherence": 8, "craft_finish": 8,
    "thumbnail_readability": 7, "memory_hook": 5, "asset_pile_feel": 4,
    "object_fit": 4, "surface_integration": 4,
}
FIDELITY_WEIGHTS = {
    "silhouette_similarity": 16, "composition_similarity": 16,
    "motif_placement_similarity": 14, "density_similarity": 10,
    "border_similarity": 12, "opening_similarity": 12,
    "focal_point_similarity": 10, "local_faithfulness": 10,
}
MACRO_REQUIRED = ("silhouette", "hierarchy", "flow", "negative_space",
                  "border_opening_integration")


MODE_WEIGHTS = {
    IntentMode.TEXT_ORIGINAL: (1.0, 0.0),
    IntentMode.REFERENCE_INSPIRED: (1.0, 0.0),
    IntentMode.REFERENCE_EXACT: (.30, .70),
    IntentMode.HYBRID: (.55, .45),
}


REPAIR_POLICIES = {
    "hero_weak": ["enlarge hero", "reduce secondary", "strengthen primary flow"],
    "sticker_feel": ["merge skeleton", "reduce isolated ornaments", "add transition relationships"],
    "border_isolated": ["rebuild border response", "add transition band", "align motif flow with frame"],
    "too_dense": ["remove filler", "restore breathing space", "rebalance hierarchy"],
    "low_fidelity": ["compare silhouette", "compare motif placement", "compare border logic",
                     "rebuild deviating regions"],
    "thin_feature": ["widen to minimum", "simplify micro detail", "preserve primary silhouette"],
    "opening_collision": ["apply exclusion field", "trim or reroute secondary motif", "relocate filler"],
    "surface_penetration": ["recompute mapping", "adjust normal offset", "reduce local relief",
                            "remap affected region only"],
}


def _score_group(scores: dict, weights: dict) -> tuple[float | None, list[str]]:
    total = 0.0; available = 0; issues = []
    for key, weight in weights.items():
        entry = scores.get(key)
        value = entry.get("score") if isinstance(entry, dict) else entry
        if value is None:
            continue
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 5:
            issues.append(f"{key}: expected 0-5 or null")
            continue
        if not isinstance(entry, dict) or not entry.get("evidence") or not entry.get("observation"):
            issues.append(f"{key}: missing visual evidence or observation")
        total += float(value) / 5 * weight; available += weight
    return (round(total / available * 100, 2) if available else None), issues


def evaluate_review(mode: str | IntentMode, phase: str, aesthetic_scores: dict,
                    fidelity_scores: dict | None = None, blockers: list[str] | None = None) -> dict:
    mode = IntentMode(mode)
    if phase not in ("plan", "macro", "meso", "final"):
        raise ValueError("Unknown review phase")
    blockers = list(blockers or [])
    aesthetic, issues = _score_group(aesthetic_scores, AESTHETIC_WEIGHTS)
    fidelity, fidelity_issues = _score_group(fidelity_scores or {}, FIDELITY_WEIGHTS)
    issues.extend(fidelity_issues)
    if phase == "plan":
        return {"gate": "HOLD", "allow_next_detail": False, "aesthetic_score": aesthetic,
                "fidelity_score": fidelity, "combined_score": None,
                "issues": issues + ["Text plan cannot pass a visual gate"], "blockers": blockers}
    required = MACRO_REQUIRED if phase == "macro" else tuple(AESTHETIC_WEIGHTS)
    missing = [key for key in required if (aesthetic_scores.get(key) or {}).get("score") is None]
    below = [key for key in required if (aesthetic_scores.get(key) or {}).get("score") is not None
             and aesthetic_scores[key]["score"] < 3]
    if mode in (IntentMode.REFERENCE_EXACT, IntentMode.HYBRID):
        fidelity_missing = [key for key in FIDELITY_WEIGHTS
                            if (fidelity_scores or {}).get(key, {}).get("score") is None]
        fidelity_below = [key for key in FIDELITY_WEIGHTS
                          if (fidelity_scores or {}).get(key, {}).get("score") is not None
                          and fidelity_scores[key]["score"] < 3]
    else:
        fidelity_missing = []; fidelity_below = []
    aw, fw = MODE_WEIGHTS[mode]
    combined = None
    if aesthetic is not None and (fw == 0 or fidelity is not None):
        combined = round(aesthetic * aw + (fidelity or 0) * fw, 2)
    if missing: issues.append("Missing aesthetic scores: " + ", ".join(missing))
    if below: issues.append("Aesthetic hard failures: " + ", ".join(below))
    if fidelity_missing: issues.append("Missing fidelity scores: " + ", ".join(fidelity_missing))
    if fidelity_below: issues.append("Fidelity hard failures: " + ", ".join(fidelity_below))
    passed = not (issues or blockers or missing or below or fidelity_missing or fidelity_below)
    passed = passed and combined is not None and combined >= 75
    passed = passed and aesthetic is not None and aesthetic >= 75
    if mode == IntentMode.REFERENCE_EXACT:
        passed = passed and fidelity is not None and fidelity >= 85
    return {"gate": "PASS" if passed else "HOLD", "allow_next_detail": passed,
            "aesthetic_score": aesthetic, "fidelity_score": fidelity,
            "combined_score": combined, "weights": {"aesthetic": aw, "fidelity": fw},
            "issues": issues, "blockers": blockers}


def repairs_for(failures: list[str], stage: str, attempt: int, maximum: int = 3) -> dict:
    if attempt >= maximum:
        return {"status": "ROLLBACK", "stage": stage, "attempt": attempt,
                "reason": "maximum repair attempts reached", "actions": []}
    actions = []
    for failure in failures:
        actions.extend(REPAIR_POLICIES.get(failure, ["inspect named failure and repair locally"]))
    # Macro failures are never routed to micro-detail actions.
    if stage.lower() == "macro":
        actions = [action for action in actions if "micro" not in action]
    return {"status": "REPAIR", "stage": stage, "attempt": attempt + 1,
            "failures": failures, "actions": list(dict.fromkeys(actions))}
