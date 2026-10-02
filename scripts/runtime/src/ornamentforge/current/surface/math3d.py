"""Small deterministic numerical primitives for the surface correspondence layer."""
import math


class SurfaceError(ValueError):
    def __init__(self, code, message, status="HOLD"):
        self.code, self.status = code, status
        super().__init__(message)


def finite(values, size=None):
    if not isinstance(values, (list, tuple)) or (size is not None and len(values) != size):
        raise SurfaceError("INVALID_NUMBERS", "Invalid vector size")
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in values):
        raise SurfaceError("INVALID_NUMBERS", "Expected finite numeric coordinates")
    return list(values)


def add(a, b): return [x+y for x,y in zip(a,b)]
def sub(a, b): return [x-y for x,y in zip(a,b)]
def mul(a, s): return [x*s for x in a]
def dot(a, b): return sum(x*y for x,y in zip(a,b))
def norm(a): return math.sqrt(dot(a,a))
def cross(a, b): return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
def cross2(a, b): return a[0]*b[1]-a[1]*b[0]


def unit(a):
    n = norm(a)
    if n <= 1e-14:
        raise SurfaceError("SINGULAR_FRAME", "Zero-length differential or normal")
    return mul(a, 1/n)


def mix(points, weights):
    return [sum(p[k]*w for p,w in zip(points,weights)) for k in range(len(points[0]))]


def barycentric2(p, tri):
    a,b,c = tri
    det = cross2(sub(b,a),sub(c,a))
    if abs(det) <= 1e-14:
        raise SurfaceError("DEGENERATE_UV", "Zero-area UV triangle")
    t = cross2(sub(p,a),sub(c,a))/det
    s = cross2(sub(b,a),sub(p,a))/det
    return [1-t-s,t,s]


def barycentric3(p, tri):
    a,b,c = tri
    e,f,q = sub(b,a),sub(c,a),sub(p,a)
    ee,ef,ff = dot(e,e),dot(e,f),dot(f,f)
    det = ee*ff-ef*ef
    if det <= 1e-24:
        raise SurfaceError("DEGENERATE_FACE", "Zero-area 3D triangle")
    t = (dot(q,e)*ff-dot(q,f)*ef)/det
    s = (dot(q,f)*ee-dot(q,e)*ef)/det
    return [1-t-s,t,s]


def differential_metrics(du, dv, normal):
    e,f,g = dot(du,du),dot(du,dv),dot(dv,dv)
    discriminant = math.hypot(e-g,2*f)
    largest = math.sqrt(max(0,(e+g+discriminant)/2))
    area = norm(cross(du,dv))
    smallest = area/largest if largest else 0
    if smallest <= 1e-14:
        raise SurfaceError("SINGULAR_FRAME", "Singular surface differential")
    orientation = dot(unit(cross(du,dv)), normal)
    return dict(local_scale=[math.sqrt(e),math.sqrt(g)],
                principal_stretches=[smallest,largest], area_scale=area,
                angle_distortion=2*math.asin(min(1,max(0,(largest-smallest)/(largest+smallest)))),
                area_distortion=abs(area-1), stretch_distortion=max(abs(largest-1),abs(smallest-1)),
                orientation=1 if orientation >= 0 else -1,
                orientation_error=norm(sub(unit(cross(du,dv)),normal)))


def affine(point, matrix):
    a,b,x,c,d,y = matrix
    return [a*point[0]+b*point[1]+x,c*point[0]+d*point[1]+y]


def triangle_overlap(a, b):
    """Positive-area intersection, excluding shared boundaries; convex clipping."""
    if cross2(sub(b[1],b[0]),sub(b[2],b[0])) < 0:
        b = list(reversed(b))
    poly = list(a)
    for start,end in zip(b,b[1:]+b[:1]):
        result = []
        if not poly:
            return 0.0
        for p,q in zip(poly,poly[1:]+poly[:1]):
            dp = cross2(sub(end,start),sub(p,start))
            dq = cross2(sub(end,start),sub(q,start))
            if dp >= 0:
                result.append(p)
            if (dp >= 0) != (dq >= 0):
                result.append(add(p,mul(sub(q,p),dp/(dp-dq))))
        poly = result
    return abs(sum(cross2(p,q) for p,q in zip(poly,poly[1:]+poly[:1])))/2 if poly else 0.0
