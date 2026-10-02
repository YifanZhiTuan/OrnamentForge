"""Unified image-presence routing plus retained legacy intent/object classifiers.

InputRouter alone selects the P0 route. Legacy classify_intent keeps its exact /
inspired metadata semantics for existing callers; it cannot override that route.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
import math
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..planar.contract import PlanarMasterV1


class IntentMode(StrEnum):
    TEXT_ORIGINAL = "MODE_A_TEXT_ORIGINAL"
    REFERENCE_INSPIRED = "MODE_B_REFERENCE_INSPIRED"
    REFERENCE_EXACT = "MODE_C_REFERENCE_EXACT"
    HYBRID = "MODE_D_HYBRID"


class ObjectFamily(StrEnum):
    MEDALLION = "MEDALLION"
    VASE = "VASE"
    LAMPSHADE = "LAMPSHADE"
    PANEL_SCREEN = "PANEL_SCREEN"
    BOX_SURFACE = "BOX_SURFACE"
    PENDANT = "PENDANT"
    SPHERE = "SPHERE"


EXACT_TERMS = (
    "一比一复刻", "1:1", "1：1", "尽量一致", "按这张图", "按这个做", "就照这个",
    "原样还原", "不要自由发挥", "忠实复刻", "高保真复刻", "exact replica",
    "reproduce exactly", "match exactly", "no creative changes", "as-is",
)
INSPIRED_TERMS = (
    "类似", "参考这个风格", "借鉴这个", "借鉴这个感觉", "风格借鉴", "inspired by",
    "similar to", "use the style", "reference the feeling",
)
HYBRID_TERMS = (
    "部分一致", "其余发挥", "保留", "必须一致", "可以发挥", "混合模式", "hybrid",
    "keep the", "must match", "freely redesign", "change the",
)


@dataclass(frozen=True)
class IntentResult:
    mode: IntentMode
    confidence: float
    matched_terms: tuple[str, ...]
    has_reference: bool
    exact_locks: tuple[str, ...] = ()
    creative_zones: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "mode": self.mode.value,
            "confidence": self.confidence,
            "matched_terms": list(self.matched_terms),
            "has_reference": self.has_reference,
            "exact_locks": list(self.exact_locks),
            "creative_zones": list(self.creative_zones),
        }


def _matches(text: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    folded = text.casefold()
    return tuple(term for term in terms if term.casefold() in folded)


def classify_intent(prompt: str, reference_images: list[str] | tuple[str, ...] | None = None,
                    exact_locks: list[str] | tuple[str, ...] | None = None,
                    creative_zones: list[str] | tuple[str, ...] | None = None) -> IntentResult:
    references = tuple(reference_images or ())
    exact = _matches(prompt, EXACT_TERMS)
    hybrid = _matches(prompt, HYBRID_TERMS)
    inspired = _matches(prompt, INSPIRED_TERMS)
    locks = tuple(exact_locks or ())
    zones = tuple(creative_zones or ())
    if references and exact:
        return IntentResult(IntentMode.REFERENCE_EXACT, 1.0, exact, True, locks, ())
    if references and (locks or zones or len(hybrid) >= 2):
        return IntentResult(IntentMode.HYBRID, .94, hybrid, True, locks, zones)
    if references:
        return IntentResult(IntentMode.REFERENCE_INSPIRED, .88 if inspired else .72,
                            inspired, True, locks, zones)
    return IntentResult(IntentMode.TEXT_ORIGINAL, .98, (), False, locks, zones)


OBJECT_PATTERNS: tuple[tuple[ObjectFamily, tuple[str, ...]], ...] = (
    (ObjectFamily.LAMPSHADE, ("灯罩", "灯笼", "lampshade", "lantern")),
    (ObjectFamily.VASE, ("花瓶", "瓶", "vase")),
    (ObjectFamily.PANEL_SCREEN, ("屏风", "隔断", "panel", "screen")),
    (ObjectFamily.BOX_SURFACE, ("盒面", "盒盖", "box", "lid")),
    (ObjectFamily.PENDANT, ("吊坠", "挂件", "pendant")),
    (ObjectFamily.SPHERE, ("球体", "球形", "sphere", "spherical")),
    (ObjectFamily.MEDALLION, ("章牌", "圆牌", "团龙", "浮雕牌", "medallion", "roundel")),
)


def infer_object_family(prompt: str, hint: str | ObjectFamily | None = None) -> ObjectFamily:
    if isinstance(hint, ObjectFamily):
        return hint
    if hint:
        normalized = re.sub(r"[\s-]+", "_", hint.strip()).upper()
        aliases = {"PENDANT_ROUNDEL": "MEDALLION", "PANEL": "PANEL_SCREEN",
                   "BOX": "BOX_SURFACE"}
        normalized = aliases.get(normalized, normalized)
        try:
            return ObjectFamily(normalized)
        except ValueError:
            pass
    folded = prompt.casefold()
    for family, terms in OBJECT_PATTERNS:
        if any(term.casefold() in folded for term in terms):
            return family
    return ObjectFamily.MEDALLION


@dataclass(frozen=True)
class RouteResult:
    route: str
    status: str
    code: str
    message: str
    master: PlanarMasterV1 | None = None
    planning: dict | None = None

    def to_dict(self):
        result = dict(route=self.route, status=self.status, code=self.code, message=self.message,
                      master=self.master.to_dict() if self.master is not None else None)
        if self.planning is not None:
            result["planning"] = self.planning
        return result


class InputRouter:
    """Unified intake. Image presence alone decides the route; never use presets.

    READY means a validated planar contract, not visual or manufacturing approval.
    Existing intent classification remains available but cannot change this route.
    """
    def __init__(self, workspace="."):
        self.workspace = Path(workspace).resolve()

    def route(self, *, reference_images=None, spec=None, prompt="", millimeters_per_unit=None,
              allow_user_motifs=False, reference_options=None, design_handoff=None, image_tool_available=False, **unsupported) -> RouteResult:
        from .planar_routes import reference_master
        from jsonschema import ValidationError
        route = "FIDELITY_RECONSTRUCTION" if reference_images else "AI_IMAGE_DESIGN"
        def stop(status, code, message):
            return RouteResult(route, status, code, message)
        if unsupported:
            return stop("NOT_SUPPORTED", "UNSUPPORTED_FIELDS", ", ".join(sorted(unsupported)))
        if reference_images is not None and (not isinstance(reference_images, (list,tuple)) or
                any(not isinstance(p, (str,Path)) or not str(p).strip() for p in reference_images)):
            return stop("HOLD", "INVALID_REFERENCES", "reference_images must be a list of paths")
        if not isinstance(prompt,str) or type(allow_user_motifs) is not bool:
            return stop("HOLD", "INVALID_INPUT", "prompt must be text; allow_user_motifs must be boolean")
        if type(image_tool_available) is not bool:
            return stop("HOLD", "INVALID_INPUT", "image_tool_available must be boolean")
        if not reference_images:
            if not image_tool_available:
                return stop("HOLD", "AI_IMAGE_TOOL_UNAVAILABLE",
                            "Use the current Codex image tool to create and select a 2D master; this runtime has no image generation tool")
            return stop("HOLD", "AI_IMAGE_GENERATION_REQUIRED",
                        "Generate with the current Codex image tool, review/select a 2D master, then supply its reference and DesignHandoff")
        if millimeters_per_unit is not None and (type(millimeters_per_unit) not in (int,float) or
                not math.isfinite(millimeters_per_unit) or millimeters_per_unit <= 0):
            return stop("HOLD", "INVALID_SCALE", "millimeters_per_unit must be finite and positive")
        options = reference_options if reference_options is not None else {}
        if not isinstance(options,dict):
            return stop("HOLD", "INVALID_OPTIONS", "reference_options must be an object")
        if set(options) - {"palette_size", "resolution", "opening_seed", "contour_tolerance", "reference_mode"}:
            return stop("NOT_SUPPORTED", "UNSUPPORTED_OPTIONS", "Unknown reference decomposition options")
        if not reference_images and options:
            return stop("NOT_SUPPORTED", "REFERENCE_OPTIONS_WITHOUT_IMAGE", "No reference image provided")
        if "reference_mode" in options and (not isinstance(options["reference_mode"],str) or
                options["reference_mode"].upper() not in ("LINE_ART","COLOR_BLOCK","MIXED")):
            return stop("HOLD", "INVALID_OPTIONS", "Unknown reference_mode")
        if reference_images and len(reference_images) != 1:
            return stop("NOT_SUPPORTED", "MULTI_REFERENCE", "P0 supports exactly one raster reference")
        if design_handoff is not None and not reference_images:
            return stop("HOLD", "HANDOFF_REQUIRES_REFERENCE", "Design metadata cannot generate or select an input image")
        for key, lower, upper in (("palette_size",2,256),("resolution",16,4096)):
            if key in options and (type(options[key]) is not int or not lower <= options[key] <= upper):
                return stop("HOLD", "INVALID_OPTIONS", f"Invalid {key}")
        if "contour_tolerance" in options and (type(options["contour_tolerance"]) not in (int,float) or
                not math.isfinite(options["contour_tolerance"]) or options["contour_tolerance"] < 0):
            return stop("HOLD", "INVALID_OPTIONS", "Invalid contour_tolerance")
        seed = options.get("opening_seed")
        if seed is not None and (not isinstance(seed,(list,tuple)) or len(seed) != 2 or
                any(type(x) not in (int,float) or not math.isfinite(x) or not 0 <= x < 1 for x in seed)):
            return stop("HOLD", "INVALID_OPTIONS", "opening_seed coordinates must be in [0,1)")
        try:
            handoff = None
            if design_handoff is not None:
                from ..design.handoff import DesignHandoff, HandoffError
                try:
                    if isinstance(design_handoff, DesignHandoff):
                        handoff = design_handoff
                    elif isinstance(design_handoff, (str, Path)):
                        record_path = Path(design_handoff)
                        handoff = DesignHandoff.load(record_path if record_path.is_absolute() else self.workspace/record_path)
                    else:
                        raise HandoffError("design_handoff must be a DesignHandoff or JSON path")
                except HandoffError as exc:
                    return stop("HOLD", exc.code, str(exc))
            if reference_images:
                path = Path(reference_images[0])
                path = path if path.is_absolute() else self.workspace/path
                if path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"):
                    return stop("NOT_SUPPORTED", "REFERENCE_FORMAT", "Only flat raster images are supported")
                if handoff is not None:
                    try:
                        handoff.verify(path)
                    except HandoffError as exc:
                        return stop("HOLD", exc.code, str(exc))
                master = reference_master(path, millimeters_per_unit, options)
                if handoff is not None:
                    try:
                        master = handoff.attach(master, path)
                    except HandoffError as exc:
                        return stop("HOLD", exc.code, str(exc))
                from ..fidelity.frontend import line_qa_from_master
                line_qa = line_qa_from_master(master)
                if line_qa is not None and line_qa["status"] == "HOLD":
                    return RouteResult(route,"HOLD","LINE_FIDELITY_HOLD",
                        "Line fidelity numerical QA failed; stop before modeling",None,{"line_qa":line_qa})
            return RouteResult(route, "READY", "PLANAR_MASTER_READY", "Contract validated; QA review required", master)
        except ImportError as exc:
            return stop("HOLD", "DEPENDENCY_MISSING", str(exc))
        except (OSError, ValueError, TypeError, ValidationError) as exc:
            return stop("HOLD", "INVALID_SOURCE_OR_CONTRACT", str(exc))
