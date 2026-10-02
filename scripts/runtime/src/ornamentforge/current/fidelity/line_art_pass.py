"""One evidence pass; geometry preview only, no SurfaceMap/Blender or repair loop.

python -m ornamentforge.current.fidelity.line_art_pass --source image.png --output run_dir
"""
import argparse
import json
from pathlib import Path
import shutil
from PIL import Image, ImageDraw

from .line_art import extract_line_art
from .reference_mode import classify_reference


def run(source, output, handoff=None):
    source=Path(source).resolve();out=Path(output).resolve()
    if out.exists() and any(out.iterdir()):raise ValueError("Evidence directory must be new or empty; refusing overwrite")
    record=None
    if handoff:
        from ..design import DesignHandoff
        record=DesignHandoff.load(handoff);record.verify(source)
    result=extract_line_art(source,classification=classify_reference(source,"line_art"))
    if record:result["master"]=record.attach(result["master"],source)
    out.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,out/"source.png")
    Image.fromarray(result["mask"].astype("uint8")*255).save(out/"binary_mask.png")
    Image.fromarray(result["skeleton"].astype("uint8")*255).save(out/"skeleton.png")
    result["preview"].save(out/"fidelity_preview.png")
    m=result["master"].to_dict()
    def write(name,value):
        with (out/name).open("x",encoding="utf-8") as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False)
    write("planar_master.json",m)
    write("stroke_graph.json",dict(graph=m["open_stroke_graph"],geometry=m["editable_geometry_references"],
        metadata=next(p["details"] for p in m["provenance"] if p["kind"]=="raster_line_art")))
    write("qa.json",result["qa"]|dict(classification=result["classification"],sampling=result["sampling"],
        contract="PASS",master_usage="DIAGNOSTIC_ONLY" if result["qa"]["status"]=="HOLD" else "REVIEW_REQUIRED",
        preview_basis="Serialized PlanarMaster cubic curves + representative widths only; no source pixel input to renderer"))
    with Image.open(source) as original:
        rgba=original.convert("RGBA");background=Image.new("RGBA",rgba.size,"white")
        left=Image.alpha_composite(background,rgba).convert("RGB").resize(result["preview"].size,Image.Resampling.LANCZOS)
    w,h=left.size
    comparison=Image.new("RGB",(2*w,h+36),"white")
    comparison.paste(left,(0,36));comparison.paste(result["preview"],(w,36))
    draw=ImageDraw.Draw(comparison)
    draw.text((12,10),"SOURCE (AI reference)",fill="black")
    draw.text((w+12,10),"RECONSTRUCTION (PlanarMaster geometry only)",fill="black")
    comparison.save(out/"comparison.png")
    return dict(output=str(out),status=result["qa"]["status"],contract="PASS",nodes=len(m["open_stroke_graph"]["nodes"]),
                edges=len(m["open_stroke_graph"]["edges"]),qa=result["qa"],sampling=result["sampling"],classification=result["classification"])


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",required=True);parser.add_argument("--output",required=True)
    parser.add_argument("--handoff")
    args=parser.parse_args()
    result=run(args.source,args.output,args.handoff)
    print(json.dumps(result,ensure_ascii=False))
    raise SystemExit(2 if result["status"]=="HOLD" else 0)
