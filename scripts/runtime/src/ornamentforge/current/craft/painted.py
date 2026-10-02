"""Independent color routing for current ceramic craft outputs."""
import numpy as np

PALETTE = {
    "background_glaze":"#DCE6DC", "phoenix_body":"#267B81",
    "phoenix_wing":"#BF6151", "phoenix_tail":"#388D94",
    "peony_flower":"#DB8490", "buds":"#CA675D", "leaves":"#7E9A78",
    "branches":"#88714A", "border":"#BB9457", "outline":"#AE884B",
}


def rgbhex(value):
    return np.array([int(value[i:i+2],16)/255 for i in (1,3,5)], np.float32)


def color_route(*, paint_requested=False, semantic_regions=False,
                accent_only=False, tint_requested=False):
    """Choose color treatment independently from relief/engraving geometry."""
    if paint_requested:
        if not semantic_regions:
            raise ValueError("Painted pattern requires a reviewed region map")
        return "painted_pattern"
    if accent_only:
        return "accent_color"
    if tint_requested:
        return "tinted_pattern"
    return "mono_glaze"
