"""Finish-only glaze presets; geometry and craft routing remain immutable."""
from .painted import PALETTE

PRESETS = {
    "painted_soft_glaze":{"base_roughness":.32,"coat_weight":.80,"coat_roughness":.095,"coat_ior":1.46,"look":"AgX - Medium High Contrast","exposure":-.15},
    "painted_glossy_glaze":{"base_roughness":.27,"coat_weight":.94,"coat_roughness":.065,"coat_ior":1.48,"look":"AgX - Medium High Contrast","exposure":-.15},
    "painted_luxury_glaze":{"base_roughness":.23,"coat_weight":1.,"coat_roughness":.045,"coat_ior":1.49,"look":"AgX - High Contrast","exposure":-.15},
}
MONO = {
    "qingbai":("#B8D9D6","#448D94",.40),
    "yingqing":("#8CBFCA","#286777",.43),
    "celadon":("#8DB497","#396D53",.43),
}


def finish_config(name):
    """Return a copied, inspectable finish configuration."""
    if name in PRESETS:
        return {"family":"painted", "name":name, **PRESETS[name]}
    if name in MONO:
        base, rich, pooling = MONO[name]
        return {"family":"monochrome", "name":name, "base":base,
                "pooled":rich, "max_pooling":pooling,
                **PRESETS["painted_glossy_glaze"]}
    raise ValueError(f"Unknown glaze preset: {name}")
