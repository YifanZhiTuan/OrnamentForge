"""Explainable raster classification; no motif semantics or online inference."""
from enum import StrEnum
import cv2
import numpy as np
from PIL import Image


class ReferenceMode(StrEnum):
    LINE_ART = "LINE_ART"
    COLOR_BLOCK = "COLOR_BLOCK"
    MIXED = "MIXED"


def load_rgb(path, resolution=None):
    with Image.open(path) as source:
        size = source.size
        image = source.convert("RGBA")
    if resolution is not None:
        image.thumbnail((resolution, resolution), Image.Resampling.LANCZOS)
    background = Image.new("RGBA", image.size, "white")
    rgb = np.asarray(Image.alpha_composite(background, image).convert("RGB"))
    return rgb, dict(source_size=list(size), working_size=list(image.size),
                    source_to_working_scale=[image.width/size[0], image.height/size[1]],
                    resampling="LANCZOS" if image.size != size else "NONE")


def classify_reference(path, override=None):
    rgb, _ = load_rgb(path, 1024)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    chroma = rgb.max(axis=2).astype(float)-rgb.min(axis=2)
    dark = (gray < 170).astype(np.uint8)
    distances = cv2.distanceTransform(dark, cv2.DIST_L2, 5)
    foreground = distances[dark > 0]
    metrics = dict(white_fraction=float((gray > 235).mean()),
        chromatic_fraction=float((chroma > 30).mean()), dark_fraction=float(dark.mean()),
        edge_density=float((cv2.Canny(gray, 60, 150) > 0).mean()),
        thin_fraction=float((foreground <= 2).mean()) if len(foreground) else 0.,
        dark_thin_fraction=float(((distances > 0) & (distances <= 2)).mean()))
    line = (metrics["white_fraction"] > .5 and metrics["chromatic_fraction"] < .015
            and .001 < metrics["dark_fraction"] < .4 and metrics["thin_fraction"] > .65
            and metrics["edge_density"] > .005)
    # A conservative mixed guess requires chromatic areas plus appreciable thin dark detail.
    mixed = (metrics["chromatic_fraction"] > .02 and metrics["dark_thin_fraction"] > .025
             and metrics["thin_fraction"] > .6 and metrics["edge_density"] > .03)
    inferred = ReferenceMode.LINE_ART if line else ReferenceMode.MIXED if mixed else ReferenceMode.COLOR_BLOCK
    selected = ReferenceMode(str(override).upper()) if override is not None else inferred
    return dict(mode=selected.value, inferred_mode=inferred.value, override=override is not None,
        metrics=metrics, analysis_longest_side=1024,
        reasons=(["Light background, low chroma, limited dark coverage, high edge/thin-structure density"] if line
                 else ["Chromatic regions plus thin internal dark detail"] if mixed
                 else ["Conservative color/filled-region route: line-art conditions not all satisfied"]),
        limitations=["Heuristic, not semantic recognition; explicit override is authoritative."])
