"""Explainable relief/engraving recommendation from measurable image proxies."""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from skimage.morphology import skeletonize

from ..planar.master import sha


def read_image(path, crop_bottom=1, size=768):
    if not 0 < crop_bottom <= 1:
        raise ValueError("Invalid crop")
    image = Image.open(path).convert("RGBA")
    image = image.crop((0,0,image.width,round(image.height*crop_bottom)))
    image.thumbnail((size,size), Image.Resampling.LANCZOS)
    background = Image.new("RGBA", image.size, "white")
    background.alpha_composite(image)
    array = np.array(background.convert("RGB"))
    foreground = array.min(2) < 225
    if foreground.any():
        y, x = np.where(foreground)
        array = array[y.min():y.max()+1, x.min():x.max()+1]
    return array


def features(array):
    gray = cv2.cvtColor(array, cv2.COLOR_RGB2GRAY)
    chroma = array.max(2).astype(float)-array.min(2)
    ink = (gray < 135).astype("uint8")
    colored = float(((chroma > 28) & (gray < 240)).mean())
    line_art = float(np.clip(1-colored*5,0,1))
    skeleton = skeletonize(ink > 0)
    distance = cv2.distanceTransform(ink, cv2.DIST_L2, 5)
    thin_share = float(np.mean(distance[skeleton] < 3.2)) if skeleton.any() else 0
    _,_,stats,_ = cv2.connectedComponentsWithStats(ink)
    tiny = sum(int(s[4]) for s in stats[1:] if s[4] < 12)/max(int(ink.sum()),1)
    closed = cv2.morphologyEx(ink,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    count,labels,stats,_ = cv2.connectedComponentsWithStats(1-closed)
    enclosed = np.zeros_like(ink)
    for index in range(1,count):
        x,y,w,h,area = stats[index]
        if x>0 and y>0 and x+w<array.shape[1] and y+h<array.shape[0] and area>=35:
            enclosed[labels==index] = 1
    support = np.maximum(enclosed,closed)
    broad = float((cv2.distanceTransform(support,cv2.DIST_L2,5)>6).mean())
    density = float(np.count_nonzero(cv2.Canny(gray,70,160))/gray.size)
    small = cv2.resize(cv2.GaussianBlur(support.astype("f4"),(0,0),5),(192,192))
    symmetry = [float(np.minimum(small,other).sum()/max(np.maximum(small,other).sum(),1))
                for other in (small[:,::-1],small[::-1],np.rot90(small),np.rot90(small,2))]
    _,_,components,_ = cv2.connectedComponentsWithStats(support)
    areas = sorted([s[4] for s in components[1:] if s[4]>30],reverse=True)
    clarity = float(sum(areas[:8])/max(sum(areas),1))*(1-min(1,tiny*4))
    contours,hierarchy = cv2.findContours(ink,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
    depths = []
    if hierarchy is not None:
        for index,contour in enumerate(contours):
            if cv2.contourArea(contour)<25: continue
            depth,parent=1,int(hierarchy[0,index,3])
            while parent>=0 and depth<8:
                depth+=1;parent=int(hierarchy[0,parent,3])
            depths.append(depth)
    return {"area_like_region_ratio":round(broad,4),"enclosed_region_ratio":round(float(enclosed.mean()),4),
            "colored_area_ratio":round(colored,4),"linear_detail_density":round(density,4),
            "thin_stroke_share":round(thin_share,4),"main_contour_clarity_proxy":round(clarity,4),
            "symmetry_proxy":round(max(symmetry),4),"hierarchy_count_proxy":int(np.percentile(depths,85)) if depths else 0,
            "small_fragment_ratio":round(tiny,4),"line_art_likelihood_proxy":round(line_art,4),
            "limitations":"Pixel morphology proxies; not semantic recognition or artistic approval."}


def recommend(f, hybrid_reason=None):
    c=min(1,f["colored_area_ratio"]/.35);m=min(1,f["area_like_region_ratio"]/.25)
    l=f["line_art_likelihood_proxy"];d=min(1,f["linear_detail_density"]/.12)
    q=f["main_contour_clarity_proxy"];s=f["symmetry_proxy"]
    noise=min(1,f["small_fragment_ratio"]*8);hier=min(1,f["hierarchy_count_proxy"]/4)
    scores={"relief":.42*c+.22*m+.13*s+.13*q+.10*hier-.20*l*d-.12*noise,
            "engraved":.35*l+.18*d+.18*(1-m)+.14*f["thin_stroke_share"]+.15*(1-c)-.1*noise,
            "hybrid":.29*l+.30*m+.18*q+.14*hier+.09*d-.18*c-.08*noise}
    scores={key:round(max(0,value),4) for key,value in scores.items()}
    allowed=list(scores) if hybrid_reason and hybrid_reason.strip() else ["relief","engraved"]
    rank=sorted(allowed,key=scores.get,reverse=True)
    return rank[0],scores,round(scores[rank[0]]-scores[rank[1]],4)


def analyze(path,crop_bottom=1,hybrid_reason=None):
    array=read_image(path,crop_bottom)
    if array.std()<3:
        raise ValueError("No readable ornament: uniform image requires manual review")
    measured=features(array);mode,scores,margin=recommend(measured,hybrid_reason)
    return {"version":"current","routing_policy":"binary_default_hybrid_exception",
            "hybrid_exception_reason":hybrid_reason,"source":str(Path(path).resolve()),
            "source_sha256":sha(Path(path)),"crop_bottom":crop_bottom,"features":measured,
            "recommended_mode":mode,"scores":scores,"score_margin":margin,
            "confidence":"low_review_required" if margin<.12 else "heuristic_review_required",
            "visual_review":None}
