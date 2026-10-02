"""Reference-driven vector relief for flat, segmented ornament artwork.

OpenCV contour extraction and bounded polygon simplification preserve measured
placement. Photograph reconstruction is deliberately not claimed by this route.
"""
from pathlib import Path
import hashlib


def decompose_flat_art(reference, palette_size=14, resolution=1000, opening_seed=None, contour_tolerance=.65):
    import cv2
    import numpy as np
    from PIL import Image
    source = Path(reference).resolve()
    image = Image.open(source).convert("RGBA")
    image.thumbnail((resolution, resolution), Image.Resampling.LANCZOS)
    rgba = np.asarray(image)
    h, w = rgba.shape[:2]
    support = (rgba[:, :, 3] > 127).astype(np.uint8) * 255
    opening = np.zeros_like(support)
    if opening_seed is not None:
        sx, sy = int(opening_seed[0]*(w-1)), int(opening_seed[1]*(h-1))
        white = (np.min(rgba[:, :, :3], axis=2) > 244).astype(np.uint8)
        _, labels = cv2.connectedComponents(white)
        label = labels[sy, sx]
        if label == 0:
            raise ValueError("Declared opening seed is not in a light region")
        opening[labels == label] = 255
        support[opening > 0] = 0
    quantized = image.convert("RGB").quantize(colors=palette_size, method=Image.Quantize.MEDIANCUT)
    indices = np.asarray(quantized)
    palette = quantized.getpalette()
    scale = 10.0/max(w, h)

    def regions(mask, min_area):
        contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        if hierarchy is None:
            return []
        result = []
        for i, contour in enumerate(contours):
            if hierarchy[0][i][3] != -1 or cv2.contourArea(contour) < min_area:
                continue
            rings = [contour]
            child = hierarchy[0][i][2]
            while child != -1:
                if cv2.contourArea(contours[child]) >= min_area:
                    rings.append(contours[child])
                child = hierarchy[0][child][0]
            paths = []
            for j, ring in enumerate(rings):
                p = cv2.approxPolyDP(ring, contour_tolerance, True).reshape(-1, 2)
                xy = [[round((float(x)-w/2)*scale, 6), round((h/2-float(y))*scale, 6)] for x, y in p]
                signed = sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(xy, xy[1:]+xy[:1]))
                if (signed > 0) != (j == 0):
                    xy.reverse()
                if len(xy) >= 3:
                    paths.append(xy)
            if paths:
                result.append({"rings": paths, "area_pixels": float(cv2.contourArea(contour))})
        return result

    layers = []
    for label in range(palette_size):
        color = palette[3*label:3*label+3]
        mask = ((indices == label) & (support > 0)).astype(np.uint8)*255
        for region in regions(mask, 5):
            layers.append({**region, "color": color, "palette_index": label})
    return {"version": "current", "source": str(source),
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "method": "palette segmentation / RETR_CCOMP / approxPolyDP", "sample_size": [w,h],
            "silhouette": regions(support, 10), "regions": layers,
            "opening_seed": opening_seed, "simplification_tolerance_pixels": contour_tolerance,
            "inferences": ["shallow relief heights inferred; image supplies planar boundaries and colors",
                           "declared light-region opening is an explicit interpretation, not depth recovered from pixels"]}
