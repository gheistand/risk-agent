"""
Risk Agent command-line interface.

    risk-agent run \
        --depth-grids depth_2yr.tif depth_100yr.tif depth_500yr.tif \
        --return-periods 2 100 500 \
        --nsi-local structures.gpkg \
        --study-area boundary.gpkg \
        --output-dir ./risk_output/
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="risk-agent",
        description="Probabilistic flood risk aggregation for HEC-RAS multi-frequency outputs.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run the EAD/risk pipeline.")
    run.add_argument(
        "--depth-grids", nargs="+", required=True,
        help="Depth raster paths (ft), one per return period.",
    )
    run.add_argument(
        "--return-periods", nargs="+", type=int, required=True,
        help="Return periods (years) matching --depth-grids order.",
    )
    run.add_argument(
        "--nsi-local", default=None,
        help="Local structure inventory (GeoPackage/GeoParquet/GeoJSON).",
    )
    run.add_argument("--study-area", default=None, help="Clip boundary.")
    run.add_argument(
        "--depth-damage-curves", default=None,
        help="CSV of custom depth-damage curves (else built-in USACE-style set).",
    )
    run.add_argument("--output-dir", required=True, help="Where to write outputs.")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "run":
        if len(args.depth_grids) != len(args.return_periods):
            print(
                "error: --depth-grids and --return-periods must have equal length",
                file=sys.stderr,
            )
            return 2
        if not args.nsi_local:
            print(
                "error: --nsi-local is required (NSI auto-fetch is a future "
                "enhancement)",
                file=sys.stderr,
            )
            return 2

        # Imports deferred so `--help` works without geospatial deps installed.
        from .core import RiskAgent
        from .depth_damage import DepthDamageCurves

        depth_grids = dict(zip((float(r) for r in args.return_periods), args.depth_grids))
        curves = (
            DepthDamageCurves.from_csv(args.depth_damage_curves)
            if args.depth_damage_curves
            else None
        )

        ra = RiskAgent(
            depth_grids=depth_grids,
            structures=args.nsi_local,
            study_area=args.study_area,
            depth_damage_curves=curves,
        )
        result = ra.run()
        manifest = result.write(args.output_dir)
        total_ead = float(result.structures["ead"].sum())
        print(f"Risk Agent: {len(result.structures)} structures, "
              f"total EAD ${total_ead:,.0f}/yr")
        for name, path in manifest.items():
            print(f"  {name}: {path}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
