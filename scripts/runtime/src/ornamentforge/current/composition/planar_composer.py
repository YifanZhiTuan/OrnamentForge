"""Deterministic ArtPlan, composition directions and OrnamentSpec creation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .grammar import MOTIF_GRAMMARS, object_grammar
from ..input.router import IntentMode, IntentResult, ObjectFamily, classify_intent, infer_object_family


MOTIFS_BY_OBJECT = {
    ObjectFamily.MEDALLION: ["DRAGON", "CLOUD_RUYI", "BORDER"],
    ObjectFamily.PENDANT: ["RADIAL_MEDALLION", "LOTUS", "BORDER"],
    ObjectFamily.VASE: ["PHOENIX", "PEONY", "FLORAL_BRANCH", "BORDER"],
    ObjectFamily.LAMPSHADE: ["VINE_SCROLL", "LOTUS", "LACE_CUTOUT", "BORDER"],
    ObjectFamily.PANEL_SCREEN: ["FULL_FIELD", "BIRD", "FLORAL_BRANCH", "BORDER"],
    ObjectFamily.BOX_SURFACE: ["RADIAL_MEDALLION", "PEONY", "BORDER"],
    ObjectFamily.SPHERE: ["FULL_FIELD", "VINE_SCROLL", "BORDER"],
}


VARIANTS = {
    ObjectFamily.MEDALLION: [
        ("coiled_hero", "Single coiled dragon with pearl and quiet head-facing pocket"),
        ("radial_confrontation", "Dragon-phoenix counterflow around one center"),
        ("open_center_ring", "Open-center radial scroll ring with stable outer seal"),
    ],
    ObjectFamily.VASE: [
        ("diagonal_flight", "Phoenix descends across shoulder; tail wraps back; peony anchors lower belly"),
        ("ascending_branch", "Peony branch rises from foot and carries phoenix across the shoulder"),
        ("front_reserve", "Front cartouche hero with asymmetric branch continuation on the back"),
    ],
    ObjectFamily.LAMPSHADE: [
        ("six_panel_growth", "Six varied S-vines bridge top and bottom rings"),
        ("continuous_lattice", "Unbroken full-field vine lattice circulates around the shade"),
        ("hero_panel", "One lotus hero panel with progressively quieter side panels"),
    ],
    ObjectFamily.PANEL_SCREEN: [("central_scene", "Central narrative field"),
                                ("paired_counterflow", "Paired counterflow panels"),
                                ("reserved_full_field", "Full field with central reserve")],
    ObjectFamily.BOX_SURFACE: [("center_medallion", "Center medallion"),
                               ("diagonal_bouquet", "Diagonal bouquet"),
                               ("reserved_full_field", "Full-field with cartouche")],
    ObjectFamily.PENDANT: [("single_emblem", "Single compact emblem"),
                           ("open_center", "Open-center symbol"),
                           ("paired_auspicious", "Paired auspicious motif")],
    ObjectFamily.SPHERE: [("hero_hemisphere", "Hero on primary hemisphere"),
                          ("great_circle", "Great-circle vine"),
                          ("six_opening", "Six-opening botanical network")],
}


EXACT_VARIANTS = [
    ("primary_reconstruction", "Primary high-fidelity reconstruction; all visual locks enforced"),
    ("faithful_repair", "Same design with curve cleanup and broken-region repair only"),
    ("craft_adaptation", "Same design with minimum-width and surface-fit adaptation only"),
]


def _stable_id(prompt: str, family: ObjectFamily, seed: int) -> str:
    digest = hashlib.sha256(f"{prompt}|{family.value}|{seed}".encode("utf-8")).hexdigest()[:12]
    return f"OF_CURRENT_{family.value}_{digest}".upper()


def _theme(prompt: str, family: ObjectFamily) -> str:
    p = prompt.casefold()
    if "龙" in p or "dragon" in p: return "dragon_cloud"
    if "凤" in p or "phoenix" in p: return "phoenix_peony"
    if "莲" in p or "lotus" in p: return "lotus_vine"
    if family == ObjectFamily.LAMPSHADE: return "vine_cutout"
    return "ornamental_composition"


def composition_directions(family: ObjectFamily, mode: IntentMode, seed: int) -> list[dict]:
    from .layouts import geometry_directions
    source = EXACT_VARIANTS if mode == IntentMode.REFERENCE_EXACT else VARIANTS[family]
    layouts = geometry_directions(family.value, mode.value)
    if layouts:
        return [{"id":f"D{i+1}","strategy":layout["name"],"seed":seed+i*101,
                 "fidelity_bound":mode == IntentMode.REFERENCE_EXACT,"geometry_parameters":layout}
                for i,layout in enumerate(layouts)]
    return [{"id": f"D{i+1}", "strategy": key, "description": desc,
             "seed": seed + i * 101, "fidelity_bound": mode == IntentMode.REFERENCE_EXACT}
            for i, (key, desc) in enumerate(source)]


def create_art_plan(prompt: str, seed: int = 20260923, object_hint: str | ObjectFamily | None = None,
                    reference_images: list[str] | None = None, references_file: str = "references.json",
                    exact_locks: list[str] | None = None,
                    creative_zones: list[str] | None = None) -> dict:
    family = infer_object_family(prompt, object_hint)
    intent = classify_intent(prompt, reference_images, exact_locks, creative_zones)
    motifs = MOTIFS_BY_OBJECT[family]
    directions = composition_directions(family, intent.mode, seed)
    selected = directions[0]
    grammar = object_grammar(family)
    exact_constraints = []
    if intent.mode == IntentMode.REFERENCE_EXACT:
        exact_constraints = ["global silhouette", "relative subject positions", "composition center",
                             "primary flow direction", "motif placement", "opening relationships",
                             "border relationships", "visual density", "focal point"]
    elif intent.mode == IntentMode.HYBRID:
        exact_constraints = list(intent.exact_locks)
    return {
        "version": "3.0", "id": _stable_id(prompt, family, seed),
        "title": f"{family.value.title()} / {_theme(prompt, family)}",
        "input": {"prompt": prompt, "object_family": family.value, "seed": seed,
                  "target_use": "render_ready", "reference_images": list(reference_images or [])},
        "intent": intent.to_dict(), "status": "MACRO_PENDING",
        "references_file": references_file,
        "object_grammar": {"name": family.value, **grammar},
        "motif_grammars": {name: MOTIF_GRAMMARS[name] for name in motifs},
        "composition_directions": directions, "selected_direction": selected["id"],
        "composition": {
            "theme": _theme(prompt, family), "primary_flow": grammar["primary_flow_patterns"][0],
            "focal_point": grammar["main_visual_zones"][0],
            "zones": grammar["main_visual_zones"], "border_zones": grammar["border_zones"],
        },
        "layers": {"macro": ["object silhouette", "hero mass", "primary flow", "openings",
                               "border structure", "negative space"],
                   "meso": ["secondary anchors", "medium motif groups", "border rhythm", "relief layers"],
                   "micro": ["surface marks", "veins/scales", "engraved lines", "micro cutouts"]},
        "negative_space": {"zones": grammar["negative_space_zones"],
                           "rule": "Purposeful regional spacing; never uniform filler density."},
        "border_cutout": {"logic": grammar["border_logic"],
                          "adaptation": grammar["relief_cutout_adaptation"]},
        "fidelity": {"enabled": intent.mode in (IntentMode.REFERENCE_EXACT, IntentMode.HYBRID),
                     "locked": exact_constraints, "creative_zones": list(intent.creative_zones),
                     "repair_permission": ["noise cleanup", "cleaner curves", "missing geometry inference",
                                           "unbuildable bridge repair", "surface conformance"],
                     "forbidden": ["theme substitution", "hero relocation", "border redesign",
                                   "density restyling"] if intent.mode == IntentMode.REFERENCE_EXACT else []},
        "macro_validation": {"required_scores": ["silhouette", "hierarchy", "flow", "negative_space",
                                                  "border_opening_integration"],
                             "threshold": 3, "weighted_threshold": 75,
                             "allow_high_detail": False,
                             "evidence_views": ["hero_front", "hero_3q", "thumbnail_160"]},
        "presentation": {"outputs": ["hero_front", "hero_3q", "detail_closeup", "thumbnail_160",
                                              "turntable", "before_after", "process_steps"],
                         "hook": "Readable hero at thumbnail size plus a clear macro-to-finish reveal."},
        "risks": grammar["common_failure_patterns"],
        "handoff": {"selected_direction": selected["id"], "allow_high_detail": False,
                    "next": "Build low-cost macro, review evidence, repair macro before meso."},
    }


def create_ornament_spec(plan: dict) -> dict:
    family = ObjectFamily(plan["input"]["object_family"])
    mode = IntentMode(plan["intent"]["mode"])
    surface = {ObjectFamily.VASE: "revolved", ObjectFamily.LAMPSHADE: "freeform",
               ObjectFamily.SPHERE: "sphere"}.get(family, "plane")
    relief = "cutout" if family == ObjectFamily.LAMPSHADE else "emboss"
    if mode == IntentMode.REFERENCE_EXACT and family == ObjectFamily.MEDALLION:
        relief = "mixed"
    input_mode = "text" if mode == IntentMode.TEXT_ORIGINAL else "mixed"
    motifs = list(plan["motif_grammars"])
    primary = [{"id": motifs[0].lower(), "type": motifs[0].lower(), "importance": "primary",
                "source": "generated"}]
    secondary = [{"id": name.lower(), "type": name.lower(), "importance": "secondary",
                  "source": "generated"} for name in motifs[1:]]
    spec = {
        "version": "1.0",
        "input": {"mode": input_mode, "prompt": plan["input"]["prompt"],
                  "reference_images": plan["input"]["reference_images"]},
        "base_surface": {"type": surface, "dimensions": [10.0, 10.0, 1.0],
                         "shell_thickness": .18},
        "composition": {"symmetry": "radial" if family in (ObjectFamily.MEDALLION, ObjectFamily.PENDANT) else "none",
                        "symmetry_count": 12 if mode == IntentMode.REFERENCE_EXACT else 1,
                        "primary_axis": "Z", "negative_space": .38},
        "ornament": {"family": "chinese_creature" if motifs[0] in ("DRAGON", "PHOENIX") else "chinese_traditional",
                     "subject": plan["composition"]["theme"], "style": "OrnamentForge Current",
                     "density": .62, "relief_mode": relief,
                     "primary_motifs": primary, "secondary_motifs": secondary},
        "layout": {"method": "radial" if family in (ObjectFamily.MEDALLION, ObjectFamily.PENDANT) else "surface_flow",
                   "avoid_openings": True, "border_clearance": .12, "minimum_spacing": .08,
                   "flow_strength": .9},
        "surface_mapping": {"method": "parameter_space" if surface in ("revolved", "sphere") else "auto",
                            "conform": True, "normal_alignment": True, "normal_offset": .02},
        "geometry": {"ornament_height": .16, "engrave_depth": .05,
                     "minimum_feature_width": .08, "minimum_wall_thickness": .16,
                     "bevel": .025, "boolean_tolerance": .01},
        "generation": {"seed": plan["input"]["seed"], "quality": "quality", "max_repair_attempts": 3},
        "target": {"mode": "render_ready", "export_formats": ["blend"]},
    }
    if not spec["input"]["reference_images"]:
        spec["input"].pop("reference_images")
    return spec


def canonical_hash(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()
