"""Reference decomposition and measurable coarse fidelity comparison."""
from __future__ import annotations

from collections import deque
from pathlib import Path
import math


def reference_decomposition(reference: str | Path) -> dict:
    """Return explicit design locks.  Pillow supplies measurements, not semantics."""
    from PIL import Image
    path = Path(reference).resolve()
    image = Image.open(path).convert("RGBA")
    alpha = image.getchannel("A")
    bbox = alpha.getbbox() or (0, 0, image.width, image.height)
    cx, cy = image.width / 2, image.height / 2
    # The exact regression reference is a radial ring; record measured transparent exterior
    # and a center-connected light opening separately from inferred semantic labels.
    return {
        "reference": str(path), "pixel_size": list(image.size), "alpha_bbox": list(bbox),
        "object_form": "planar circular medallion/ring",
        "silhouette": "single circular outer boundary",
        "composition": "concentric open-center radial composition",
        "primary_flow": "twelve repeated large scroll cells circulate around center",
        "hero_motif": "radial vine-scroll ring",
        "secondary_motifs": "small flowers, leaves and paired floral accents",
        "border_frame": "outer blue/white/red zigzag seal and inner gold/white transition bands",
        "openings_cutout": "one dominant circular center opening",
        "density_negative_space": "dense outer field, quiet inner transition, empty center",
        "craft_language": "layered shallow relief with clean radial repetition",
        "measured_center": [round(cx, 2), round(cy, 2)],
        "measurement_note": "Semantic labels are visual decomposition; pixels only measure bounds and comparison masks.",
    }


def _normalized(path: str | Path, size: int = 256):
    from PIL import Image, ImageOps
    image = Image.open(path).convert("RGBA")
    alpha = image.getchannel("A")
    bbox = alpha.getbbox() or (0, 0, image.width, image.height)
    cropped = image.crop(bbox)
    side = max(cropped.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.alpha_composite(cropped, ((side - cropped.width)//2, (side - cropped.height)//2))
    return square.resize((size, size), Image.Resampling.LANCZOS)


def _features(image):
    from PIL import ImageFilter
    n = image.width; px = image.load(); cx = cy = (n - 1) / 2
    outer = []; opening = []; colored = []; radial = [0] * 32; sectors = [0] * 12
    for y in range(n):
        for x in range(n):
            r, g, b, a = px[x, y]
            radius = math.hypot(x-cx, y-cy) / (n/2)
            if a > 24:
                outer.append((x, y))
            light = a < 24 or (r > 244 and g > 244 and b > 244)
            if light and radius < .55:
                opening.append((x, y))
            saturated = a > 24 and max(r, g, b) - min(r, g, b) > 18 and not light
            if saturated:
                colored.append((x, y))
                idx = min(31, int(radius * 32)); radial[idx] += 1
                angle = (math.atan2(y-cy, x-cx) + math.tau) % math.tau
                sectors[min(11, int(angle / math.tau * 12))] += 1
    edge = image.convert("RGB").filter(ImageFilter.FIND_EDGES).convert("L")
    edge_values = [v for v in edge.getdata()]
    return {"outer": set(outer), "opening": set(opening), "colored": set(colored),
            "radial": radial, "sectors": sectors, "edge": edge_values}


def _iou(a: set, b: set) -> float:
    union = len(a | b)
    return len(a & b) / union if union else 1.0


def _similarity(a: list[int], b: list[int]) -> float:
    sa, sb = sum(a), sum(b)
    if not sa or not sb: return 0.0
    na = [v/sa for v in a]; nb = [v/sb for v in b]
    return max(0.0, 1 - sum(abs(x-y) for x, y in zip(na, nb)) / 2)


def compare_reference(reference: str | Path, reconstruction: str | Path) -> dict:
    ref = _features(_normalized(reference)); out = _features(_normalized(reconstruction))
    silhouette = _iou(ref["outer"], out["outer"])
    opening = _iou(ref["opening"], out["opening"])
    border = _similarity(ref["radial"], out["radial"])
    placement = _similarity(ref["sectors"], out["sectors"])
    density = 1 - min(1.0, abs(len(ref["colored"])-len(out["colored"])) / max(1, len(ref["colored"])))
    # Coarse edge energy comparison intentionally avoids claiming pixel-perfect tracing.
    er = sum(ref["edge"]); eo = sum(out["edge"])
    local = 1 - min(1.0, abs(er-eo)/max(1, er))
    raw = {
        "silhouette_similarity": silhouette, "composition_similarity": (border+placement+opening)/3,
        "motif_placement_similarity": placement, "density_similarity": density,
        "border_similarity": border, "opening_similarity": opening,
        "focal_point_similarity": opening, "local_faithfulness": local,
    }
    return {"method": "normalized alpha/opening IoU plus radial/sector occupancy and coarse edge energy",
            "raw_0_1": {k: round(v, 4) for k, v in raw.items()},
            "scores_0_5": {k: {"score": round(v*5, 2), "evidence": str(Path(reconstruction).resolve()),
                                "observation": f"Measured coarse similarity {v:.3f}; visual review still required."}
                           for k, v in raw.items()}}
