"""Packaging smoke checks, isolated from installed code and original checkout."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def check(work):
    from run import RUNTIME, initialize
    sys.path.insert(0, str(RUNTIME / "src"))
    initialize(work)
    import ornamentforge
    assert Path(ornamentforge.__file__).is_relative_to(RUNTIME)
    from ornamentforge.current.input.router import InputRouter
    from ornamentforge.current.design import DesignHandoff
    from ornamentforge.current.surface import HostAdapter
    from ornamentforge.current.craft.surface_adapter import map_surface_craft
    from ornamentforge.current.craft.engraving_field import signed_distance, groove_depth
    from PIL import Image, ImageDraw
    import numpy as np
    router = InputRouter(work)
    missing = router.route(reference_images=["absent.png"])
    assert missing.status == "HOLD" and missing.master is None
    multi = router.route(reference_images=["one.png", "two.png"])
    assert multi.status == "NOT_SUPPORTED"
    source = work / "fixture.png"
    image = Image.new("RGB", (160, 160), "white")
    ImageDraw.Draw(image).ellipse((35, 35, 125, 125), fill=(60, 130, 160))
    image.save(source)
    ref = router.route(reference_images=[str(source)], reference_options={"reference_mode": "color_block"})
    assert ref.status == "READY", ref.to_dict()
    handoff = DesignHandoff.create(original_user_prompt="Packaging fixture", design_prompt="Not AI art",
        candidates={"fixture": source}, selected_candidate="fixture", generator="test_fixture",
        selection_notes="Synthetic dependency smoke test only", provenance={"fixture": True})
    handoff.save(work / "handoff.json")
    bound = router.route(reference_images=[str(source)], design_handoff=str(work / "handoff.json"),
        reference_options={"reference_mode": "color_block"})
    assert bound.status == "READY", bound.to_dict()
    bounds = ref.master.to_dict()["domain"]["bounds"]
    surface = HostAdapter.create("PLANE", parameters={"bounds": bounds})
    mapped = {}
    for craft, options in (("engraved", {"depth": .01}), ("relief", {"height": .01}),
                           ("painted", {"reviewed_semantics": True})):
        result = map_surface_craft(ref.master, surface, craft=craft, source_feature_width=.1, **options)
        assert result["status"] == "READY", result
        mapped[craft] = result["status"]
    mask = np.zeros((64, 128), bool)
    mask[20:44, 20:108] = True
    sdf, inside = signed_distance(mask)
    depth = groove_depth(sdf, inside)
    assert np.isfinite(depth).all() and depth.max() > 0 and not depth[0].any()
    print(json.dumps({"status": "PASS", "relocated_import": True, "reference": ref.status,
        "handoff_fixture": bound.status, "missing_input": missing.status,
        "multiple_references": multi.status, "craft_mapping": mapped,
        "sdf": "PASS", "ai_generated": False, "blender_render_tested": False}, indent=2))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--relocated":
        check(Path(sys.argv[2]))
    else:
        with tempfile.TemporaryDirectory(prefix="ornamentforge-release-") as tmp:
            root = Path(tmp)
            relocated = root / "skill with spaces"
            shutil.copytree(Path(__file__).resolve().parents[1], relocated,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            env["PYTHONUTF8"] = "1"
            raise SystemExit(subprocess.call([sys.executable, "-B", str(relocated / "scripts/check_runtime.py"),
                "--relocated", str(root / "workspace")], cwd=root, env=env))
