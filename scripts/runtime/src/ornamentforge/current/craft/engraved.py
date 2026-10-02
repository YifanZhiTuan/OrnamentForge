"""Reusable signed engraving primitives for the current craft pipeline."""
from __future__ import annotations

import cv2
import numpy as np
from scipy.ndimage import gaussian_filter1d
from skimage.morphology import skeletonize


def polygon(points, size: int = 1400):
    p = np.asarray(points, np.float32)
    dense = []
    for a, b in zip(p, np.roll(p, -1, axis=0)):
        count = max(2, int(np.linalg.norm(b - a) / 2))
        dense.extend(a + (b - a) * np.arange(count)[:, None] / count)
    smooth = gaussian_filter1d(np.array(dense), 3, axis=0, mode="wrap")
    mask = np.zeros((size, size), np.uint8)
    cv2.fillPoly(mask, [np.round(smooth).astype(np.int32)], 1)
    return mask


def volume(mask, height, width=28):
    distance = cv2.distanceTransform(mask.astype("uint8"), cv2.DIST_L2, 5)
    t = np.clip(distance / 27, 0, 1)
    smooth = t * t * (3 - 2 * t)
    return height * smooth * (0.25 + 0.75 * (1 - np.exp(-distance / width)))


def skeleton_paths(binary, min_length=18, protected=None):
    """Thin linework, prune short spurs and retain editable centerlines."""
    closed = cv2.morphologyEx(binary.astype("uint8"), cv2.MORPH_CLOSE,
                              cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    points = set(map(tuple, np.argwhere(skeletonize(closed > 0))))
    neighbors = {p: [(p[0]+dy, p[1]+dx) for dy in (-1,0,1) for dx in (-1,0,1)
                     if (dy or dx) and (p[0]+dy, p[1]+dx) in points
                     and not (dy and dx and ((p[0]+dy,p[1]) in points or (p[0],p[1]+dx) in points))]
                 for p in points}
    visited, paths, removed = set(), [], 0
    for start in sorted(points, key=lambda p: (len(neighbors[p]) == 2, p)):
        for nxt in neighbors[start]:
            edge = tuple(sorted((start, nxt)))
            if edge in visited:
                continue
            visited.add(edge); path = [start, nxt]; previous, current = start, nxt
            while len(neighbors[current]) == 2:
                others = [p for p in neighbors[current] if p != previous]
                if not others:
                    break
                point = others[0]; edge = tuple(sorted((current, point)))
                if edge in visited:
                    break
                visited.add(edge); path.append(point); previous, current = current, point
            limit = 6 if protected is not None and protected[path[len(path)//2]] else min_length
            bridge = len(neighbors[path[0]]) >= 3 and len(neighbors[path[-1]]) >= 3
            if len(path) < limit and not bridge:
                removed += 1; continue
            raw = np.array(path, dtype="f4")[:, ::-1]
            smoothed = gaussian_filter1d(raw, 1.2, axis=0, mode="nearest")
            smoothed[0], smoothed[-1] = raw[0], raw[-1]
            paths.append(smoothed)
    result = np.zeros_like(binary, np.uint8)
    for path in paths:
        cv2.polylines(result, [np.round(path).astype("int32")], False, 1, 1, cv2.LINE_8)
    return result, paths, {"raw_skeleton_pixels": len(points), "kept_path_count": len(paths),
                           "removed_short_paths": removed, "kept_skeleton_pixels": int(result.sum())}


def groove(skeleton, radius, depth):
    """Return positive removal depth using a finite cosine SDF profile."""
    if not np.any(skeleton):
        return np.zeros_like(skeleton, np.float32)
    distance = cv2.distanceTransform(1-skeleton.astype("uint8"), cv2.DIST_L2, 5)
    return np.where(distance < radius,
                    depth*.5*(1+np.cos(np.pi*np.clip(distance/radius,0,1))), 0).astype("f4")
