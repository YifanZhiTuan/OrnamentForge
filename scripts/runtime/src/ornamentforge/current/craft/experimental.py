"""Shared raster-to-signed-field helpers retained from validated craft experiments."""
import cv2
import numpy as np

from .engraved import groove, skeleton_paths


def etch(image):
    """Convert line art and filled ink into graded, non-positive engraving support."""
    ink = (image.mean(2) < 145).astype("uint8")
    distance = cv2.distanceTransform(ink, cv2.DIST_L2, 5)
    original = ink.copy()
    ink[distance > 4.3] = 0
    _, paths, qa = skeleton_paths(ink, 14)
    masks = {grade: np.zeros_like(ink) for grade in ("primary", "secondary", "micro")}
    for path in paths:
        length = np.linalg.norm(np.diff(path, axis=0), axis=1).sum()
        grade = "primary" if length > 100 else "secondary" if length > 35 else "micro"
        cv2.polylines(masks[grade], [np.round(path).astype("int32")], False, 1, 1)
    channels = {grade: cv2.GaussianBlur(groove(masks[grade], radius, depth), (0,0), .6)
                for grade, radius, depth in (("primary",3.6,.027),("secondary",2.7,.020),("micro",2,.012))}
    field = np.maximum.reduce(list(channels.values()))
    qa.update(black_fill_pixels_outlined=int(np.count_nonzero(original-ink)),
              grades={grade:int(mask.sum()) for grade,mask in masks.items()},
              max_removal=float(field.max()),
              formula="SDF distance to smoothed skeleton; finite cosine removal")
    return field, paths, qa, masks


def radial_sample(field, x, y):
    size = field.shape[0]
    map_x = ((x/10+.5)*(size-1)).astype("f4")
    map_y = ((.5-y/10)*(size-1)).astype("f4")
    return cv2.remap(field.astype("f4"), map_x, map_y, cv2.INTER_LINEAR)
