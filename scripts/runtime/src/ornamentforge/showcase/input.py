"""Constrained showcase input interpretation; image measurements are explicitly heuristic."""
import json
import math
import re
from pathlib import Path

from ..serialization import write_json
from ..spec import normalize_spec


def prompt_spec(workspace,prompt):
    data=json.loads((workspace/"schemas/example_showcase_ornament_sphere.json").read_text(encoding="utf-8"))
    data["input"]={"mode":"text","prompt":prompt}
    if any(s in prompt.lower() for s in ("silver","银")):data["ornament"]["style"]="silver_botanical"
    if any(s in prompt.lower() for s in ("bronze","青铜")):data["ornament"]["style"]="bronze_botanical"
    if any(s in prompt.lower() for s in ("sparse","稀疏","简约")):data["ornament"]["density"]=.65
    match=re.search(r"(?:seed|种子)\s*[:：=]?\s*(\d+)",prompt,re.I)
    if match:data["generation"]["seed"]=int(match.group(1))
    return normalize_spec(data)


def reference_spec(workspace,path):
    # Pillow is an optional input dependency, never needed to build/render from a spec.
    try:
        from PIL import Image,ImageFilter,ImageStat
    except ImportError as exc:
        raise RuntimeError("Reference input requires Pillow: python -m pip install 'ornamentforge[reference]'") from exc
    path=Path(path).resolve()
    with Image.open(path) as raw:
        image=raw.convert("RGB");image.thumbnail((256,256));w,h=image.size
        gray=image.convert("L");edges=gray.filter(ImageFilter.FIND_EDGES)
        edge_pixels=list(edges.getdata());density=sum(v>30 for v in edge_pixels)/len(edge_pixels)
        # Estimate object silhouette against median corner background colour.
        corner=[image.getpixel((x,y)) for x,y in ((0,0),(w-1,0),(0,h-1),(w-1,h-1))]
        bg=[sorted(c[i] for c in corner)[2] for i in range(3)]
        foreground={(x,y) for y in range(h) for x in range(w)
                    if sum((image.getpixel((x,y))[i]-bg[i])**2 for i in range(3))>45**2}
        if not foreground:raise ValueError("Reference silhouette could not be distinguished from background")
        xmin,xmax=min(p[0] for p in foreground),max(p[0] for p in foreground)
        ymin,ymax=min(p[1] for p in foreground),max(p[1] for p in foreground)
        aspect=(xmax-xmin+1)/(ymax-ymin+1)
        mean=[sum(image.getpixel(p)[channel] for p in foreground)/len(foreground) for channel in range(3)]
        style="silver_botanical" if max(mean)-min(mean)<12 else "bronze_botanical" if mean[0]>mean[2]*1.3 else "ivory_gilt_peony_filigree"
        # Candidate dark interior components; spec keeps six axes since hidden openings cannot be counted in one image.
        pixels=gray.load();dark={(x,y) for y in range(ymin+1,ymax) for x in range(xmin+1,xmax) if pixels[x,y]<55}
        components=[]
        while dark:
            seed=dark.pop();stack=[seed];area=[]
            while stack:
                x,y=stack.pop();area.append((x,y))
                for p in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                    if p in dark:dark.remove(p);stack.append(p)
            if 12<len(area)<w*h*.12:
                cx=sum(x for x,y in area)/len(area);cy=sum(y for x,y in area)/len(area)
                components.append({"center_image_fraction":[cx/w,cy/h],"area_fraction":len(area)/(w*h)})
        data=prompt_spec(workspace,"Reference-guided spherical botanical showcase").to_dict()
        data["input"]={"mode":"image","reference_images":[str(path)],"prompt":"Approximate reference structure/style with the constrained six-oculus botanical hero recipe"}
        data["ornament"]["density"]=min(.95,max(.65,.65+density))
        data["ornament"]["style"]=style
        analysis={"method":"Local silhouette/edge/palette measurements plus fixed spherical showcase grammar",
                  "reference":str(path),"silhouette_aspect":aspect,"edge_density":density,"palette_mean_rgb":mean,
                  "visible_dark_opening_candidates":components[:12],"selected_style":style,
                  "inferred_shape":"near-spherical" if .75<aspect<1.3 else "sphere preset; silhouette differs",
                  "opening_layout":"six symmetric axial openings; hidden positions are a declared prior",
                  "border":"double ring with milgrain, preset","relief_cutout":"mixed, preset",
                  "hierarchy":"vine/peony primary, leaves/scrolls secondary, fern/filler tertiary, preset",
                  "limitations":"Not semantic image reconstruction; shadows may resemble openings. Unknown hidden structure uses the documented hero preset."}
        return normalize_spec(data),analysis
