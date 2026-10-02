"""Error-bounded cubic fitting and geometry-only rasterization."""
import math
import numpy as np
from PIL import Image, ImageDraw


def fit_cubics(points, tolerance=.7):
    """Fit chord-parameterized cubics recursively; preserve segment endpoints.

    Error bound is at measured skeleton samples, not a global topology certificate.
    Splitting retains sharp features; no fitting across graph junctions.
    """
    p = np.asarray(points, float)
    def fit(q):
        length = np.linalg.norm(np.diff(q,axis=0),axis=1)
        total = length.sum()
        if len(q) == 2:
            delta = (q[-1]-q[0])/3
            return [[q[0],q[0]+delta,q[-1]-delta,q[-1]]]
        if np.linalg.norm(q[-1]-q[0]) < 1e-8:
            middle = len(q)//2
            return fit(q[:middle+1])+fit(q[middle:])
        t = np.r_[0,np.cumsum(length)]/total
        look = min(3,len(q)-1)
        a,b = q[look]-q[0],q[-1-look]-q[-1]
        a /= max(np.linalg.norm(a),1e-12); b /= max(np.linalg.norm(b),1e-12)
        s = 1-t
        basis = np.array([s**3,3*s*s*t,3*s*t*t,t**3]).T
        fixed = (basis[:,0]+basis[:,1])[:,None]*q[0]+(basis[:,2]+basis[:,3])[:,None]*q[-1]
        mat = np.stack([basis[:,1,None]*a,basis[:,2,None]*b],axis=-1).reshape(-1,2)
        alpha = np.linalg.lstsq(mat,(q-fixed).reshape(-1),rcond=None)[0]
        chord = np.linalg.norm(q[-1]-q[0])
        if np.any(alpha < 0) or np.any(alpha > 2*chord): alpha[:] = chord/3
        controls = np.array([q[0],q[0]+alpha[0]*a,q[-1]+alpha[1]*b,q[-1]])
        errors = np.linalg.norm(basis@controls-q,axis=1)
        split = int(np.argmax(errors))
        if errors[split] <= tolerance: return [list(controls)]
        split = max(1,min(split,len(q)-2))
        return fit(q[:split+1])+fit(q[split:])
    return fit(p)


def curve_payload(segments, w, h):
    scale = 10/max(w,h)
    def xy(p): return [float((p[0]-w/2)*scale),float((h/2-p[1])*scale),0.]
    points = []
    for i,c in enumerate(segments):
        points.append(dict(co=xy(c[0]),left=xy(segments[i-1][2] if i else c[0]),right=xy(c[1]),
            left_type="FREE",right_type="FREE",radius=1.,tilt=0.))
    c=segments[-1]
    points.append(dict(co=xy(c[3]),left=xy(c[2]),right=xy(c[3]),
        left_type="FREE",right_type="FREE",radius=1.,tilt=0.))
    return dict(curve_version="1.0",representation="bezier_curve",dimensions="3D",
                resolution_u=24,twist_mode="Z_UP",cyclic=False,points=points)


def sample_curve(payload, design_units_per_pixel):
    result = []
    p = payload["points"]
    for a,b in zip(p,p[1:]):
        c = np.array([a["co"][:2],a["right"][:2],b["left"][:2],b["co"][:2]])
        upper = np.linalg.norm(np.diff(c,axis=0),axis=1).sum()/design_units_per_pixel
        t = np.linspace(0,1,max(2,int(math.ceil(upper*2))+1));s=1-t
        q = np.array([s**3,3*s*s*t,3*s*t*t,t**3]).T@c
        result.extend(q.tolist() if not result else q[1:].tolist())
    return result


def rasterize_master(master, size, supersample=2, strokes_only=False):
    """Only serialized geometry/width/palette are read. No source raster accepted."""
    m = master.to_dict() if hasattr(master,"to_dict") else master
    w,h = size; factor = supersample
    x0,y0,x1,y1 = m["domain"]["bounds"]
    units = (x1-x0)/w
    image = Image.new("RGB",(w*factor,h*factor),"white")
    geometry={g["id"]:g for g in m["editable_geometry_references"]}
    colors={p["id"]:tuple(p["rgb"]) for p in m["palette"]}
    def px(points):return [((x-x0)/(x1-x0)*w*factor,(y1-y)/(y1-y0)*h*factor) for x,y in points]
    if not strokes_only:
        holes={}
        for hole in m["holes"]:holes.setdefault(hole["parent_region"],[]).append(hole["geometry_ref"])
        for region in m["closed_regions"]:
            if region["kind"] == "support": continue
            mask=Image.new("L",image.size,0);draw=ImageDraw.Draw(mask)
            draw.polygon(px(geometry[region["geometry_ref"]]["data"]["points"]),fill=255)
            for ref in holes.get(region["id"],[]):
                draw.polygon(px(geometry[ref]["data"]["points"]),fill=0)
            image.paste(colors.get(region["palette_ref"],(0,0,0)),(0,0,*image.size),mask)
    draw=ImageDraw.Draw(image)
    for edge in m["open_stroke_graph"]["edges"]:
        g=geometry[edge["geometry_ref"]]
        coords=sample_curve(g["data"],units) if g["representation"] == "bezier_curve" else g["data"]["points"]
        coords=px(coords);width=max(1,round(edge["width"]/units*factor))
        draw.line(coords,fill="black",width=width,joint="curve")
        # Consistent round caps also fill small numerical joins between edge endpoints.
        radius=width/2
        for x,y in (coords[0],coords[-1]):draw.ellipse((x-radius,y-radius,x+radius,y+radius),fill="black")
    return image.resize((w,h),Image.Resampling.LANCZOS)
