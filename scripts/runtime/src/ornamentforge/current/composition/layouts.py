"""Executable Macro layout controls shared by any prompt for each object family."""
from copy import deepcopy


LAYOUTS = {
    "MEDALLION": [
        {"name":"inward_coil", "spine":[[1.05,.25],[1.5,1.02],[.85,2.02],[-.65,2.25],[-2.05,1.38],[-2.45,-.1],[-1.72,-1.75],[-.3,-2.58],[1.42,-2.38],[2.52,-1.18],[2.73,.38],[2.12,1.72]], "body_width":.40},
        {"name":"open_crescent", "spine":[[1.05,.25],[1.98,.97],[2.62,1.75],[2.30,2.69],[.82,3.13],[-1.1,2.9],[-2.66,1.74],[-3.04,-.08],[-2.10,-1.93],[-.44,-2.58],[1.17,-2.18]], "body_width":.44},
        {"name":"descending_s", "spine":[[1.05,.25],[1.88,-.52],[1.74,-1.83],[.25,-2.55],[-1.58,-2.06],[-2.58,-.82],[-2.54,.92],[-1.42,2.37],[.25,2.90],[1.60,2.48]], "body_width":.46},
    ],
    "VASE": [
        {"name":"diagonal_flight","theta_mirror":1,"theta_offset":0,"vertical_scale":1,"tail_sweep":1,"flower_theta":-.52},
        {"name":"ascending_counterflow","theta_mirror":-1,"theta_offset":.15,"vertical_scale":.86,"tail_sweep":.64,"flower_theta":.70},
        {"name":"wide_shoulder_fan","theta_mirror":1,"theta_offset":-.34,"vertical_scale":.72,"tail_sweep":1.36,"flower_theta":-.80},
    ],
    "LAMPSHADE": [
        {"name":"six_panel_growth","panel_count":6,"vine_amplitude":.31,"vine_cycles":1,"bridge_levels":[-1.6,0,1.6]},
        {"name":"continuous_lattice","panel_count":10,"vine_amplitude":.29,"vine_cycles":1.5,"bridge_levels":[-2,-.8,.8,2]},
        {"name":"hero_panel","panel_count":8,"vine_amplitude":.22,"vine_cycles":.65,"bridge_levels":[-1.2,1.2]},
    ],
}


def geometry_directions(family, mode):
    if mode == "MODE_C_REFERENCE_EXACT":
        return [{"name":name,"contour_tolerance":tolerance,"preserve_reference":True}
                for name,tolerance in (("primary_reconstruction",.65),("faithful_repair",.45),("craft_adaptation",.65))]
    return deepcopy(LAYOUTS.get(family, []))
