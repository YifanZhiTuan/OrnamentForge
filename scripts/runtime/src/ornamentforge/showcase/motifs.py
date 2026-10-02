"""Retrieve original canonical motifs; generate missing definitions once, then validate/register."""
import math
import json
from pathlib import Path
from ..canonical_curve import from_legacy, content_hash
from ..current.library.motif_library import MotifLibrary
from ..serialization import write_json

ROLES = {"Vine_Main":"vine","Vine_Secondary":"showcase_secondary","Leaf_A":"leaf",
         "Leaf_B":"showcase_acanthus","Flower_A":"showcase_petal","Fern_A":"showcase_fern",
         "Cloud_A":"showcase_cloud","Scroll_A":"showcase_scroll","Filler_A":"showcase_filler","Border_A":"showcase_border"}


def definition(role):
    if role=="Vine_Secondary":
        pts=[[i/16,0.12*math.sin(i/16*math.pi*2),0] for i in range(17)]
    elif role in ("Scroll_A","Cloud_A"):
        turns=1.5 if role=="Scroll_A" else 1.1
        pts=[]
        for i in range(49):
            t=i/48; r=0.5*(1-t)+0.045; a=t*2*math.pi*turns
            pts.append([r*math.cos(a),r*math.sin(a),0])
    elif role=="Leaf_B":
        pts=[[0,0,0],[.18,.17,0],[.38,.12,0],[.45,.24,0],[.65,.15,0],[1,0,0],
             [.65,-.15,0],[.45,-.24,0],[.38,-.12,0],[.18,-.17,0]]
    elif role=="Flower_A":
        pts=[[0,0,0],[.3,.28,0],[.7,.35,0],[1,.15,0],[1.05,0,0],[1,-.15,0],[.7,-.35,0],[.3,-.28,0]]
    elif role=="Fern_A":
        pts=[[i/20,.12*math.sin(i*.7)*(1-i/24),0] for i in range(21)]
    elif role=="Filler_A":
        pts=[[.5+.5*math.cos(2*math.pi*i/16),.2*math.sin(2*math.pi*i/16),0] for i in range(16)]
    else:
        pts=[[i/24,.06*math.sin(i/24*6*math.pi),0] for i in range(25)]
    closed=role in ("Leaf_B","Flower_A","Filler_A")
    points=[]
    for i,point in enumerate(pts):
        prev=pts[(i-1)%len(pts)] if closed or i else point
        nxt=pts[(i+1)%len(pts)] if closed or i<len(pts)-1 else point
        tangent=[(nxt[j]-prev[j])/6 for j in range(3)]
        points.append({"co":point,"left":[point[j]-tangent[j] for j in range(3)],"right":[point[j]+tangent[j] for j in range(3)]})
    return from_legacy({"representation":"bezier_curve","cyclic":closed,"control_points":points})


def retrieve(workspace):
    library=MotifLibrary(workspace); definitions={}; usage={}
    for role,kind in ROLES.items():
        query=library.search(family="botanical",motif_type=kind,tags=["showcase"] if kind.startswith("showcase") else ["b01"],threshold=90,source_preference="generated")
        if query["selected_motif"]:
            record=library.inspect(query["selected_motif"])
            payload=library.verify_record(record)
            usage[role]={"status":"HIT","id":record["id"],"query":query,"provenance_ref":record["provenance_ref"]}
        else:
            if role in ("Vine_Main","Leaf_A"):
                raise ValueError("Existing Phase 3 vine/leaf library is required")
            payload=definition(role)
            usage[role]={"status":"MISS","id":None,"query":query}
        definitions[role]=payload
    return definitions,usage


def register_validated(workspace,run,definitions,usage,measurements):
    library=MotifLibrary(workspace)
    for role,entry in usage.items():
        if entry["status"]=="HIT": continue
        check=measurements["motif_definition_qa"][role]
        if not check["passed"]: raise ValueError(f"Motif failed QA: {role}")
        digest=content_hash(definitions[role])
        evidence=library.root/"generated/evidence"/("showcase_"+digest+".json")
        write_json(evidence,{"final_pass":True,"method":"Blender local canonical curve evaluation","measurement":check,
                             "origin_run":str(run),"query":entry["query"],"original_project_geometry":True})
        ref=evidence.relative_to(workspace).as_posix()
        meta={"semantic_version":"1.0.0","family":"botanical","type":ROLES[role],"tags":["showcase",role],
              "representation":"bezier_curve","source_kind":"generated","qa_status":"PASS","qa_evidence":ref,
              "parameter_ranges":{"scale":{"min":.02,"max":.5},"stroke_width":{"min":.008,"max":.04},"leaf_count":{"min":1,"max":1000}},
              "compatible_mapping_modes":["planar"]}
        provenance={"version":"1.0","owner":"OrnamentForge project","license":"LicenseRef-ProjectOwned-Unlicensed",
                    "source_url":"project://ornamentforge/library/generated/"+role,"project_use_allowed":True,
                    "redistribution_allowed":False,"attribution_required":True,"evidence":ref}
        record=library.register(definitions[role],meta,provenance)
        entry.update(id=record["id"],registered_after_qa=True,provenance_ref=record["provenance_ref"])
    write_json(run/"motif_usage.json",usage)
