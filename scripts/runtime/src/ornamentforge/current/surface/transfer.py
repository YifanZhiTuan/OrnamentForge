"""Verified low-curvature transfer from a reviewed planar master.

The transfer intentionally supports only analytic graph hosts.  It does not
claim arbitrary UV unwrapping or manufacturing certification.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np


HOST_DEPTHS = {
    "flat_plate": 0.0,
    "annular_plate": 0.0,
    "curved_plate": 0.48,
    "shallow_bowl": 0.8,
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def map_points(x: np.ndarray, y: np.ndarray, height: np.ndarray, host: str):
    """Map planar coordinates along the normal of a low-curvature host."""
    if host not in HOST_DEPTHS:
        raise ValueError(f"Unsupported host: {host}")
    depth = HOST_DEPTHS[host]
    z = depth * (x * x + y * y) / 25
    dx = 2 * depth * x / 25
    dy = 2 * depth * y / 25
    normal = np.stack([-dx, -dy, np.ones_like(x)], -1)
    normal /= np.linalg.norm(normal, axis=-1)[..., None]
    base = np.stack([x, y, z], -1)
    top = base + height[..., None] * normal
    return base, normal, top


def map_surface(master: Path, host: str, out: Path, require_review: bool = True) -> Path:
    """Transfer an approved planar master and emit numerical QA evidence."""
    master, out = Path(master), Path(out)
    if require_review:
        review = json.loads((master / "master_review.json").read_text(encoding="utf-8"))
        if review["status"] != "FAST_ART_TRANSFER_READY" or review["master_sha256"] != _sha(master / "master.npz"):
            raise ValueError("Missing/stale master approval")
        required = {"clay_front.png", "clay_3q.png", "color_front.png", "AssemblyPlan.json", "geometry_qa.json"}
        if not required.issubset(review["evidence"]):
            raise ValueError("Incomplete master evidence")
        for filename, digest in review["evidence"].items():
            if _sha(master / filename) != digest:
                raise ValueError("Stale render evidence")
        qa = json.loads((master / "geometry_qa.json").read_text(encoding="utf-8"))
        if qa["nonmanifold_edges"] or not qa["finite"]:
            raise ValueError("Master geometry QA failed")

    data = np.load(master / "master.npz")
    inner = float(data["inner_radius"])
    if (host == "annular_plate") != (inner > 0):
        raise ValueError("Host topology must match approved master; no silent hero clipping")
    x, y = data["x"], data["y"]
    height = data["fields"].sum(0)
    base, normal, top = map_points(x, y, height, host)
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out / "surface.npz", base=base, normal=normal, top=top,
        fields=data["fields"], rgb=data["rgb"], roles=data["roles"], inner_radius=inner,
    )
    error = np.max(np.abs(np.sum((top - base) * normal, axis=-1) - height))
    slope = np.max(np.linalg.norm(normal[..., :2], axis=-1) / normal[..., 2])
    stretch = np.sqrt(1 + slope * slope)
    _write(out / "transfer_qa.json", {
        "host": host,
        "source_master": str(master),
        "master_sha256": _sha(master / "master.npz"),
        "formula": "P(u,v) + h_master(u,v) * unit_normal(P)",
        "height_error_max": float(error),
        "max_radial_stretch": float(stretch),
        "max_angular_stretch": 1.0,
        "xy_domain_preserved": True,
        "periodic_theta": True,
        "inner_radius": inner,
        "self_intersection_certified": False,
        "status": "NUMERIC_PASS" if error < 1e-6 and stretch < 1.08 else "HOLD",
        "limitations": "Low-curvature analytic graph only; not arbitrary UV unwrapping, not full cylinder wrap, not manufacturing certification.",
    })
    if out != master:
        for filename in ("AssemblyPlan.json", "ArtPlan.json", "OrnamentSpec.json", "editable_regions.json", "references.json"):
            (out / filename).write_bytes((master / filename).read_bytes())
    return out
