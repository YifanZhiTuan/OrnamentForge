"""Deterministic skeleton topology and conservative local gap handling."""
import math
import cv2
import numpy as np
from scipy.spatial import cKDTree


def adjacency(skeleton):
    pixels = set(map(tuple, np.argwhere(skeleton)))
    graph = {}
    for y, x in sorted(pixels):
        neighbors = []
        for dy, dx in ((-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)):
            q = (y+dy, x+dx)
            if q not in pixels:
                continue
            # Suppress diagonal shortcuts around an existing orthogonal connection.
            if dy and dx and ((y, x+dx) in pixels or (y+dy, x) in pixels):
                continue
            neighbors.append(q)
        graph[(y,x)] = neighbors
    return graph


def heal_gaps(skeleton, mask, max_gap=3):
    if type(max_gap) is not int or not 0 <= max_gap <= 3:
        raise ValueError("Gap healing maximum must be an integer in [0,3] pixels")
    graph = adjacency(skeleton)
    ends = [p for p, ns in graph.items() if len(ns) == 1]
    proposals, accepted = {}, []
    if not max_gap or not ends:
        return skeleton.copy(), mask.copy(), dict(max_gap_pixels=max_gap, healed=[], unresolved_near_pairs=0)
    tree = cKDTree(ends)
    def outward(p):
        prev, curr = p, graph[p][0]
        for _ in range(4):
            ns = [v for v in graph[curr] if v != prev]
            if len(ns) != 1: break
            prev, curr = curr, ns[0]
        v = np.array(p, float)-curr
        return v/max(np.linalg.norm(v), 1e-12)
    directions = [outward(p) for p in ends]
    near_pairs = 0
    for i, p in enumerate(ends):
        choices = []
        for j in sorted(tree.query_ball_point(p, max_gap+1)):
            if j == i: continue
            q = ends[j]; v = np.array(q, float)-p; distance = np.linalg.norm(v)
            if distance <= 1: continue
            if i < j: near_pairs += 1
            v /= distance
            if directions[i] @ v < .92 or directions[j] @ (-v) < .92: continue
            # Never bridge across a third line or an existing interior pixel.
            samples = np.rint(np.linspace(p, q, int(math.ceil(distance))+1)).astype(int)[1:-1]
            if any(tuple(s) in graph for s in samples): continue
            if any((s[0]+dy,s[1]+dx) in graph and
                   min(np.linalg.norm(s-np.array(p)), np.linalg.norm(s-np.array(q))) > 1.5
                   for s in samples for dy,dx in ((-1,0),(1,0),(0,-1),(0,1))): continue
            choices.append(j)
        if len(choices) == 1: proposals[i] = choices[0]
    skel, healed_mask = skeleton.astype(np.uint8).copy(), mask.astype(np.uint8).copy()
    for i,j in sorted(proposals.items()):
        if i >= j or proposals.get(j) != i: continue
        p,q = ends[i], ends[j]
        cv2.line(skel, p[::-1], q[::-1], 1, 1)
        cv2.line(healed_mask, p[::-1], q[::-1], 1, 1)
        accepted.append(dict(start=list(map(int,p[::-1])), end=list(map(int,q[::-1])),
                             endpoint_distance=float(np.linalg.norm(np.array(p)-q))))
    return skel.astype(bool), healed_mask.astype(bool), dict(max_gap_pixels=max_gap,
        healed=accepted, unresolved_near_pairs=near_pairs-len(accepted),
        rule="mutually unique facing endpoints, cosine >= .92, no third-stroke crossing")


def trace_graph(skeleton):
    graph = adjacency(skeleton)
    critical = {p for p, n in graph.items() if len(n) != 2}
    junctions = {p for p in critical if len(graph[p]) >= 3}
    nodes, owner = [], {}
    for start in sorted(critical):
        if start in owner: continue
        cluster = {start}
        if start in junctions:
            queue = [start]
            while queue:
                p = queue.pop()
                for q in graph[p]:
                    if q in junctions and q not in cluster:
                        cluster.add(q); queue.append(q)
        coords = np.array(sorted(cluster), float)
        center = coords.mean(axis=0)
        # One existing skeleton pixel is the cluster representative, never an off-line centroid.
        anchor = tuple(coords[np.argmin(np.linalg.norm(coords-center, axis=1))].astype(int))
        index = len(nodes)
        nodes.append(dict(pixel=list(map(float,anchor[::-1])), members=sorted(cluster)))
        for p in cluster: owner[p] = index
    visited, edges = set(), []
    def link(a,b): return tuple(sorted((a,b)))
    def walk(start, first):
        points, prev, curr = [start], start, first
        visited.add(link(prev,curr))
        while curr not in owner:
            points.append(curr)
            candidates = [p for p in graph[curr] if p != prev]
            if len(candidates) != 1: raise ValueError("Invalid skeleton topology")
            prev,curr = curr,candidates[0]
            visited.add(link(prev,curr))
        points.append(curr)
        a,b = owner[start],owner[curr]
        xy = [nodes[a]["pixel"]] + [list(map(float,p[::-1])) for p in points[1:-1]] + [nodes[b]["pixel"]]
        xy = [p for i,p in enumerate(xy) if i == 0 or p != xy[i-1]]
        if len(xy) >= 2:
            edges.append(dict(start=a,end=b,pixels=xy,loop=a==b,
                length=float(np.linalg.norm(np.diff(xy,axis=0),axis=1).sum())))
    for start in sorted(owner):
        for q in graph[start]:
            if q in owner and owner[q] == owner[start]:
                visited.add(link(start,q)); continue
            if link(start,q) not in visited: walk(start,q)
    # Degree-two components are true closed strokes, not filled white regions.
    for start in sorted(graph):
        remaining = [q for q in graph[start] if link(start,q) not in visited]
        if not remaining: continue
        owner[start] = len(nodes)
        nodes.append(dict(pixel=list(map(float,start[::-1])), members=[start]))
        walk(start,remaining[0])
    degree = [0]*len(nodes)
    for edge in edges:
        degree[edge["start"]] += 1; degree[edge["end"]] += 1
    for i,node in enumerate(nodes):
        node["degree"] = degree[i]
        node["kind"] = "endpoint" if degree[i] == 1 else "intersection" if degree[i] >= 4 else "junction" if degree[i] == 3 else "loop_anchor" if degree[i] == 2 else "isolated"
        node["cluster_radius"] = max(np.linalg.norm(np.array(p[::-1])-node["pixel"]) for p in node["members"])
        del node["members"]
    return nodes, edges


def prune_spurs(skeleton, maximum=2.):
    """One pass only; preserve short free-standing strokes and genuine loops."""
    nodes,edges = trace_graph(skeleton)
    result = skeleton.copy(); removed = 0
    for edge in edges:
        degrees = [nodes[edge[k]]["degree"] for k in ("start","end")]
        if edge["length"] <= maximum and min(degrees) == 1 and max(degrees) >= 3:
            junction = nodes[edge["end"] if degrees[1] >= 3 else edge["start"]]["pixel"]
            for x,y in edge["pixels"]:
                if [x,y] != junction:
                    result[int(y),int(x)] = False
            removed += 1
    return result, removed
