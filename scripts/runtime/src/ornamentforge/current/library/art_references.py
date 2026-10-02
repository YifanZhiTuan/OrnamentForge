"""Read-only visual-reference retrieval for current ArtPlans."""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from ..input.router import ObjectFamily


LIBRARY_RELATIVE = Path("art_direction/ArtLibrary")
FIT = {
    ObjectFamily.MEDALLION: "pendant_roundel", ObjectFamily.PENDANT: "pendant_roundel",
    ObjectFamily.VASE: "vase", ObjectFamily.LAMPSHADE: "lampshade",
    ObjectFamily.PANEL_SCREEN: "panel_screen", ObjectFamily.BOX_SURFACE: "box_surface",
    ObjectFamily.SPHERE: "sphere",
}
VIEWED_IDS = {"SX1_001", "SX1_018", "GC1_023", "GC1_032", "GC1_002",
              "DH_013", "DH_018", "MZY_022", "LS_014"}


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _borrow(row: dict) -> str:
    role = row["image_role"]
    if role == "hero_motif":
        return f"Borrow {row['motif_primary']} silhouette hierarchy and principal flow, not literal contours."
    if role == "composition_only":
        return f"Borrow {row['composition_type']} organization, density rhythm and negative-space distribution."
    if role == "border":
        return "Borrow edge rhythm, closure and structural bridging only."
    return "Borrow supporting rhythm and scale hierarchy below the hero motif."


def _avoid(row: dict) -> str:
    if row["pack"] == "LS":
        return "Do not let Western lace language replace the Chinese primary composition."
    if row["image_role"] == "hero_motif":
        return "Do not trace or redistribute the source asset; rebuild semantic grammar as editable geometry."
    return "Do not copy the whole plate or treat uniform density as finished composition."


def _subject_terms(prompt: str) -> set[str]:
    folded = prompt.casefold()
    groups = {
        "dragon": ("龙", "dragon"), "phoenix": ("凤", "phoenix"),
        "peony": ("牡丹", "peony"), "lotus": ("莲", "lotus"),
        "floral": ("花", "flower", "floral", "缠枝", "vine"),
        "vine_scroll": ("卷草", "缠枝", "vine", "scroll"),
        "bird": ("鸟", "bird"),
    }
    return {name for name, words in groups.items() if any(word in folded for word in words)}


def retrieve_references(workspace: str | Path, family: ObjectFamily, prompt: str,
                        limit: int = 18, primary_reference: str | Path | None = None) -> dict:
    if not 12 <= limit <= 30:
        raise ValueError("Reference shortlist must contain 12-30 candidates")
    workspace = Path(workspace).resolve()
    root = workspace / LIBRARY_RELATIVE
    manifest = root / "03_MANIFEST/CORE_LEARNING_SET.csv"
    with manifest.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    target = FIT[family]
    terms = _subject_terms(prompt)

    def score(row: dict) -> tuple:
        fits = target in row["object_fit"].split("|")
        motif = row["motif_primary"].casefold()
        subject = any(term in motif or motif in term for term in terms)
        quality = {"S": 3, "A": 2, "B": 1}.get(row["art_quality"], 0)
        role = {"hero_motif": 4, "composition_only": 3, "secondary_motif": 2,
                "border": 1}.get(row["image_role"], 0)
        return (fits, subject, quality, role, row["3d_value"] == "high", row["id"])

    ordered = sorted(rows, key=score, reverse=True)
    selected: list[dict] = []
    roles: set[str] = set()
    # Seed role diversity before filling by total score.
    for role in ("hero_motif", "composition_only", "secondary_motif", "border"):
        candidate = next((r for r in ordered if r["image_role"] == role and
                          target in r["object_fit"].split("|")), None)
        if candidate and candidate not in selected:
            selected.append(candidate); roles.add(role)
    for row in ordered:
        if len(selected) >= limit:
            break
        if row not in selected and (target in row["object_fit"].split("|") or len(selected) < 8):
            selected.append(row)
    records = []
    for row in selected:
        matches = list((root / "01_CORE_IMAGES" / row["pack"]).glob(row["id"] + ".*"))
        records.append({
            "id": row["id"], "role": row["image_role"], "motif": row["motif_primary"],
            "composition": row["composition_type"], "object_fit": row["object_fit"],
            "image_path": str(matches[0]) if matches else None,
            "borrow": _borrow(row), "avoid": _avoid(row),
            "viewed": False,
            "reuse_permission": "unknown; local visual study only",
        })
    primary = None
    if primary_reference:
        p = Path(primary_reference)
        if not p.is_absolute():
            p = workspace / p
        primary = {"id": p.stem, "role": "primary_exact_reference", "image_path": str(p.resolve()),
                   "borrow": "Lock decomposition and fidelity constraints to this image.",
                   "avoid": "Do not replace it with an ArtLibrary candidate or invent missing theme changes.",
                   "viewed": False,
                   "reuse_permission": "local reconstruction study; source licensing remains separate"}
    return {
        "version": "3.0", "family": family.value, "count": len(records),
        "primary_reference": primary, "references": records,
        "manifest_sha256": _sha(manifest),
        "policy": "CORE-only shortlist; primary user/reference input outranks library support references.",
    }
