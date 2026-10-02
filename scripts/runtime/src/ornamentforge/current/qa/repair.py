"""Bounded deterministic modifications to executable layout controls."""
from copy import deepcopy


def repair_layout(parameters, failure, *, mode, attempt, maximum=3):
    if attempt >= maximum:
        raise ValueError("Repair budget exhausted; rollback to reviewed candidate")
    result=deepcopy(parameters)
    if mode == "MODE_C_REFERENCE_EXACT":
        if failure != "low_fidelity":
            raise ValueError("Exact repair requires a measured deviating region; generic restyling forbidden")
        result["contour_tolerance"]=max(.15,result.get("contour_tolerance",.65)*.65)
        return result
    if failure == "too_dense":
        if "bridge_levels" in result and len(result["bridge_levels"])>2:
            levels=result["bridge_levels"]
            result["bridge_levels"]=[levels[0],levels[-1]]
        elif "body_width" in result:
            result["body_width"] *= .90
        elif "tail_sweep" in result:
            result["tail_sweep"] *= 1.10
        else:
            raise ValueError("No density repair available for these layout controls")
    elif failure == "border_isolated" and "spine" in result:
        # Keep the head attachment fixed while letting the outer sweep respond to the rim.
        result["spine"]=[point if i<2 else [x*1.04 for x in point] for i,point in enumerate(result["spine"])]
    elif failure == "hero_weak" and "tail_sweep" in result:
        result["tail_sweep"] *= .92
        result["vertical_scale"] = min(1.,result.get("vertical_scale",1.)*1.08)
    else:
        raise ValueError("Failure needs a grammar-level repair, not an unrelated parameter change")
    return result
