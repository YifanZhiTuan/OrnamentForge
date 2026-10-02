"""Command-line entry for the single maintained OrnamentForge workflow."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ornamentforge.blender_contract import contained
from ornamentforge.serialization import write_json
from ornamentforge.spec import load_spec
from ornamentforge.validation import SpecValidationError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OrnamentForge current capability line")
    commands = parser.add_subparsers(dest="command", required=True)
    route = commands.add_parser("route", help="Unified input -> PlanarMasterV1 (no Blender, no preset fallback)")
    route.add_argument("--workspace", default=".")
    route.add_argument("--reference", action="append", default=[])
    route.add_argument("--reference-mode", choices=("line_art","color_block","mixed"), help="Override explainable fidelity mode classification")
    route.add_argument("--design-handoff", help="Optional offline DesignHandoff JSON; requires matching --reference PNG")
    route.add_argument("--prompt", default="")
    route.add_argument("--millimeters-per-unit", type=float)
    route.add_argument("--output")
    commands.add_parser("master-schema", help="Print the authoritative PlanarMasterV1 JSON Schema")
    commands.add_parser("surface-schema", help="Print the SurfaceMapV1 JSON Schema")
    surface = commands.add_parser("surface-map", help="PlanarMasterV1 + explicit host JSON -> correspondence and numerical QA; no render")
    surface.add_argument("master")
    surface.add_argument("host")
    surface.add_argument("--fit-domain", action="store_true")
    surface.add_argument("--height", type=float, default=0)
    surface.add_argument("--depth", type=float, default=0)
    surface.add_argument("--source-feature-width", type=float)
    surface.add_argument("--output")
    validate = commands.add_parser("validate", help="Validate an OrnamentSpec")
    validate.add_argument("spec")
    reference = commands.add_parser("reference", help="Decompose or execute a reference-led Macro pass")
    reference.add_argument("reference")
    reference.add_argument("--prompt", default="按这张图尽量一致，不要自由发挥")
    reference.add_argument("--workspace", default=".")
    reference.add_argument("--family")
    reference.add_argument("--opening-seed", nargs=2, type=float)
    reference.add_argument("--decompose-only", action="store_true")
    reference.add_argument("--output")
    planar = commands.add_parser("planar", help="Retrieve, build, approve or transfer a planar master")
    planar.add_argument("action", choices=("retrieve", "build", "approve", "transfer"))
    planar.add_argument("name")
    planar.add_argument("--host", default="flat_plate")
    planar.add_argument("--observation")
    planar.add_argument("--assembly")
    planar.add_argument("--reference")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "surface-schema":
            from .surface.contract import SurfaceMapV1
            result = SurfaceMapV1.schema()
        elif args.command == "surface-map":
            from .surface import HostAdapter, map_planar_master, fit_domain_transform
            from .surface.math3d import SurfaceError
            from .planar.contract import PlanarMasterV1
            from jsonschema import ValidationError
            try:
                raw = json.loads(Path(args.master).read_text(encoding="utf-8-sig"))
                master = PlanarMasterV1.from_dict(raw["master"] if "master" in raw else raw)
                host = json.loads(Path(args.host).read_text(encoding="utf-8-sig"))
                if not isinstance(host,dict) or set(host)-{"host_type","parameters","host_mesh","chart_id"} or "host_type" not in host:
                    raise SurfaceError("HOST_INPUT", "Expected host_type plus optional parameters/host_mesh/chart_id")
                surface = HostAdapter.create(**host)
                result = map_planar_master(master,surface,
                    domain_transform=fit_domain_transform(master,surface) if args.fit_domain else None,
                    height=args.height,depth=args.depth,source_feature_width=args.source_feature_width)
            except (OSError, ValueError, TypeError, KeyError, ValidationError) as exc:
                result = dict(status=getattr(exc,"status","HOLD"),code=getattr(exc,"code","INVALID_SURFACE_INPUT"),
                              message=str(exc),surface_map=None,mapped_master=None,qa=None)
            if args.output:
                write_json(Path(args.output),result)
            print(json.dumps(result,ensure_ascii=False))
            return {"READY":0,"HOLD":2,"NOT_SUPPORTED":3}[result["status"]]
        elif args.command == "master-schema":
            from .planar.contract import PlanarMasterV1
            result = PlanarMasterV1.schema()
        elif args.command == "route":
            from .input.router import InputRouter, RouteResult
            routed = InputRouter(args.workspace).route(reference_images=args.reference,
                prompt=args.prompt, millimeters_per_unit=args.millimeters_per_unit,
                design_handoff=args.design_handoff,
                reference_options={"reference_mode":args.reference_mode} if args.reference_mode else None)
            result = routed.to_dict()
            if args.output:
                write_json(Path(args.output), result)
            print(json.dumps(result, ensure_ascii=False))
            return {"READY":0, "HOLD":2, "NOT_SUPPORTED":3}[routed.status]
        elif args.command == "validate":
            spec = load_spec(args.spec)
            result = {"valid": True, "spec_hash": spec.spec_hash, "seed": spec.seed}
        elif args.command == "reference":
            if args.decompose_only:
                from .fidelity.reconstruction import decompose_flat_art
                data = decompose_flat_art(args.reference, opening_seed=args.opening_seed)
                result = data
                if args.output:
                    write_json(Path(args.output), data)
                    result = {"decomposition": str(Path(args.output).resolve()), "regions": len(data["regions"])}
            else:
                from .fidelity.run import run
                root = run(args.workspace, args.prompt, args.family, reference=args.reference, opening_seed=args.opening_seed)
                result = {"workspace": str(root), "phase": "macro"}
        else:
            from .planar.master import OUT, approve, build, retrieve, retrieve_reference, write
            from .surface.transfer import map_surface
            if args.action == "retrieve":
                if not args.reference:
                    result = dict(status="HOLD", code="AI_IMAGE_TOOL_UNAVAILABLE", master=None,
                                  message="Supply a user reference or a selected Codex-generated 2D master")
                    print(json.dumps(result))
                    return 2
                result = retrieve_reference(args.reference)
                write(OUT / "retrieval" / f"{args.name}.json", result)
            elif args.action == "build":
                result = {"master": str(build(args.name, args.assembly))}
            elif args.action == "approve":
                if not args.observation:
                    raise ValueError("Visual observation required")
                approve(OUT / ("master_" + args.name), args.observation)
                result = {"approved": str(OUT / ("master_" + args.name))}
            else:
                out = map_surface(OUT / ("master_" + args.name), args.host, OUT / ("transfer_" + args.name))
                result = {"transfer": str(out), "host": args.host}
        print(json.dumps(result, ensure_ascii=False))
        return 0 if not isinstance(result, dict) or result.get("valid", True) else 1
    except SpecValidationError as exc:
        print(json.dumps(exc.to_dict(), ensure_ascii=False), file=sys.stderr)
        return 1
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"error_class": type(exc).__name__, "code": getattr(exc, "code", None), "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
