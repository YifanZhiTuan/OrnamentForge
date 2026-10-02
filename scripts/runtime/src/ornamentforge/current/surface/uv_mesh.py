"""Read-only, per-loop existing UV charts and triangle barycentric queries."""
from copy import deepcopy
from .math3d import (SurfaceError, finite, sub, mul, add, cross, cross2, dot, norm, unit,
                     mix, barycentric2, barycentric3, triangle_overlap)


class UVHost:
    def __init__(self, snapshot, chart_id=None):
        if not isinstance(snapshot,dict) or not snapshot.get("uv_layer"):
            raise SurfaceError("UV_REQUIRED", "Existing UV layer required; automatic unwrap is disabled", "NOT_SUPPORTED")
        if set(snapshot) != {"vertices","triangles","seam_edges","uv_layer","coordinate_space","object_name"}:
            raise SurfaceError("MESH_SCHEMA", "Unexpected/missing UV snapshot fields")
        if snapshot["coordinate_space"] != "WORLD" or not isinstance(snapshot["object_name"],str):
            raise SurfaceError("MESH_SCHEMA", "Snapshot must use world coordinates")
        self.snapshot = deepcopy(snapshot)
        self.vertices = [finite(v,3) for v in snapshot["vertices"]]
        self.triangles = deepcopy(snapshot["triangles"])
        if not self.vertices or not self.triangles:
            raise SurfaceError("EMPTY_MESH", "Mesh is empty")
        ids = set()
        self.edges = {}
        for t in self.triangles:
            if set(t) != {"id","face_id","vertex_indices","loop_indices","uv","normal"}:
                raise SurfaceError("MESH_SCHEMA", "Invalid triangle fields")
            if type(t["id"]) is not int or t["id"] < 0 or t["id"] in ids or type(t["face_id"]) is not int or t["face_id"] < 0:
                raise SurfaceError("FACE_ID", "Unique nonnegative triangle IDs required")
            ids.add(t["id"])
            vi,li = t["vertex_indices"],t["loop_indices"]
            if len(vi) != 3 or len(set(vi)) != 3 or any(type(i) is not int or not 0 <= i < len(self.vertices) for i in vi):
                raise SurfaceError("FACE_VERTEX", "Invalid vertex indices")
            if len(li) != 3 or any(type(i) is not int or i < 0 for i in li):
                raise SurfaceError("FACE_LOOP", "Invalid loop indices")
            if len(t["uv"]) != 3:
                raise SurfaceError("UV_REQUIRED", "Every triangle needs all three UV loops")
            t["uv"] = [finite(uv,2) for uv in t["uv"]]
            xyz = [self.vertices[i] for i in vi]
            n = unit(cross(sub(xyz[1],xyz[0]),sub(xyz[2],xyz[0])))
            if norm(sub(n,finite(t["normal"],3))) > 1e-6:
                raise SurfaceError("FACE_NORMAL", "Face normal disagrees with world-space winding")
            det = cross2(sub(t["uv"][1],t["uv"][0]),sub(t["uv"][2],t["uv"][0]))
            if det <= 1e-14:
                raise SurfaceError("UV_ORIENTATION", "Degenerate or mirrored UV triangle; explicit repair required")
            for j in range(3):
                key = tuple(sorted((vi[j],vi[(j+1)%3])))
                side = dict(triangle_id=t["id"], face_id=t["face_id"],
                            uv=[t["uv"][vi.index(i)] for i in key])
                self.edges.setdefault(key,[]).append(side)
        marked = set()
        for edge in snapshot["seam_edges"]:
            if len(edge) != 2 or any(type(i) is not int or not 0 <= i < len(self.vertices) for i in edge):
                raise SurfaceError("SEAM_EDGE", "Invalid seam vertex indices")
            marked.add(tuple(sorted(edge)))
        if not marked.issubset(self.edges):
            raise SurfaceError("SEAM_EDGE", "Seam must belong to mesh")
        adjacency = {i:set() for i in ids}
        self.seam_data = []
        for edge,sides in sorted(self.edges.items()):
            if len(sides) > 2:
                raise SurfaceError("NONMANIFOLD_EDGE", "Nonmanifold UV host", "NOT_SUPPORTED")
            joined = len(sides) == 2 and edge not in marked and all(norm(sub(a,b)) <= 1e-10 for a,b in zip(sides[0]["uv"],sides[1]["uv"]))
            if joined:
                a,b = [s["triangle_id"] for s in sides]
                adjacency[a].add(b)
                adjacency[b].add(a)
            else:
                self.seam_data.append(dict(kind="BOUNDARY" if len(sides)==1 else "UV_SEAM",
                                           edge_vertices=list(edge), marked=edge in marked, sides=sides))
        self.chart_by_triangle = {}
        for start in sorted(ids):
            if start in self.chart_by_triangle:
                continue
            chart = f"chart_{start}"
            stack = [start]
            while stack:
                i = stack.pop()
                if i in self.chart_by_triangle:
                    continue
                self.chart_by_triangle[i] = chart
                stack.extend(adjacency[i]-self.chart_by_triangle.keys())
        charts = sorted(set(self.chart_by_triangle.values()))
        if chart_id is None and len(charts) != 1:
            raise SurfaceError("CHART_SELECTION_REQUIRED", f"Select an existing chart explicitly: {charts}", "NOT_SUPPORTED")
        self.chart_id = chart_id or charts[0]
        if self.chart_id not in charts:
            raise SurfaceError("CHART_NOT_FOUND", self.chart_id)
        self.selected = sorted([t for t in self.triangles if self.chart_by_triangle[t["id"]] == self.chart_id],key=lambda t:t["id"])
        for i,a in enumerate(self.selected):
            for b in self.selected[i+1:]:
                if triangle_overlap(a["uv"],b["uv"]) > 1e-10:
                    raise SurfaceError("UV_OVERLAP", "Positive-area overlap inside selected chart exceeds 1e-10 UV^2")
        for seam in self.seam_data:
            for side in seam["sides"]:
                side["chart_id"] = self.chart_by_triangle[side["triangle_id"]]
        uv = [p for t in self.selected for p in t["uv"]]
        self.bounds = [min(p[0] for p in uv),min(p[1] for p in uv),max(p[0] for p in uv),max(p[1] for p in uv)]

    def _sample(self, t, weights, uv):
        xyz = [self.vertices[i] for i in t["vertex_indices"]]
        e,f = sub(xyz[1],xyz[0]),sub(xyz[2],xyz[0])
        a,b = sub(t["uv"][1],t["uv"][0]),sub(t["uv"][2],t["uv"][0])
        det = cross2(a,b)
        du = mul(sub(mul(e,b[1]),mul(f,a[1])),1/det)
        dv = mul(sub(mul(f,a[0]),mul(e,b[0])),1/det)
        return dict(uv=list(uv),canonical_uv=list(uv),face_id=t["face_id"],triangle_id=t["id"],
                    barycentric=weights,correspondence_basis="MESH_LOOP_TRIANGLE",
                    surface_position=mix(xyz,weights),normal=t["normal"],dp_du=du,dp_dv=dv)

    def forward(self, uv, triangle_hint=None):
        finite(uv,2)
        for t in self.selected:
            if triangle_hint is not None and t["id"] != triangle_hint:
                continue
            bary = barycentric2(uv,t["uv"])
            if min(bary) >= -1e-9 and max(bary) <= 1+1e-9:
                return self._sample(t,bary,uv)
        raise SurfaceError("OUTSIDE_UV_CHART", "UV not inside the selected chart/triangle")

    def inverse(self, position, uv_hint=None, triangle_hint=None, tolerance=1e-7):
        finite(position,3)
        matches = []
        for t in self.selected:
            if triangle_hint is not None and t["id"] != triangle_hint:
                continue
            xyz = [self.vertices[i] for i in t["vertex_indices"]]
            bary = barycentric3(position,xyz)
            if min(bary) >= -1e-9 and norm(sub(mix(xyz,bary),position)) <= tolerance:
                matches.append(self._sample(t,bary,mix(t["uv"],bary)))
        if not matches:
            raise SurfaceError("OFF_SURFACE", "Point is not on the selected chart/triangle")
        if any(norm(sub(m["uv"],matches[0]["uv"])) > 1e-7 for m in matches[1:]):
            raise SurfaceError("AMBIGUOUS_INVERSE", "Multiple UV preimages; supply triangle_hint")
        return matches[0]

    def seams(self): return deepcopy(self.seam_data)

    def seed_uvs(self):
        return [(t["id"],uv) for t in self.selected for uv in [*t["uv"],mix(t["uv"],[1/3]*3)]]
