"""
RiskAgent — orchestrates the depth -> damage -> EAD pipeline.

Pipeline:
  1. Load/accept structures (NSI) with value + occupancy + first-floor offset.
  2. Sample each per-return-period depth grid at every structure (depth_extract).
  3. Convert ground depth -> depth-above-first-floor; apply depth-damage curves
     to get a damage ratio, multiply by structure value -> $ damage per RP.
  4. Integrate damage over AEP -> Expected Annual Damage ($/yr) per structure.
  5. Aggregate EAD by reach for prioritization.

Outputs are returned as a RiskResult and can be written to disk.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np

from .depth_damage import DepthDamageCurves
from .depth_extract import extract_depth_stack
from .ead import ead_for_structures


# NSI default first-floor height above ground (ft) when not provided.
_DEFAULT_FFH_FT = 1.0
# Fallback structure value ($) when NSI value is missing.
_DEFAULT_VAL = 100_000.0


@dataclass
class RiskResult:
    """Container for Risk Agent outputs."""

    structures: "object"      # GeoDataFrame: per-structure depth/damage/EAD
    reaches: Optional["object"]  # GeoDataFrame or None: reach-level EAD ranking
    return_periods: list
    metadata: dict

    def write(self, output_dir: str) -> dict:
        """Write outputs to ``output_dir``; returns a manifest of written files."""
        import json
        import os

        os.makedirs(output_dir, exist_ok=True)
        written = {}

        struct_path = os.path.join(output_dir, "structures_ead.gpkg")
        self.structures.to_file(struct_path, driver="GPKG")
        written["structures_ead"] = struct_path

        if self.reaches is not None:
            reach_path = os.path.join(output_dir, "reaches_ead.gpkg")
            self.reaches.to_file(reach_path, driver="GPKG")
            written["reaches_ead"] = reach_path

        summary_path = os.path.join(output_dir, "summary.json")
        with open(summary_path, "w") as fh:
            json.dump(
                {
                    "return_periods": self.return_periods,
                    "n_structures": int(len(self.structures)),
                    "total_ead": float(self.structures["ead"].sum()),
                    **self.metadata,
                },
                fh,
                indent=2,
            )
        written["summary"] = summary_path
        return written


class RiskAgent:
    """Probabilistic flood-risk aggregation for HEC-RAS multi-frequency output.

    Args:
        depth_grids:   {return_period: path_to_depth_raster_ft}.
        structures:    path to a structure inventory (GeoPackage/GeoParquet/
                       GeoJSON) OR a prebuilt GeoDataFrame of point structures.
                       Expected columns (NSI-style, all optional with defaults):
                         - ``val_struct`` : structure value ($)
                         - ``occtype``    : NSI occupancy type (e.g. RES1)
                         - ``found_ht``   : first-floor height above ground (ft)
                         - ``reach_id``   : reach identifier for aggregation
        study_area:    optional path/GeoDataFrame to clip structures to.
        depth_damage_curves: DepthDamageCurves; defaults to the built-in library.
    """

    def __init__(
        self,
        depth_grids: Dict[float, str],
        structures=None,
        study_area=None,
        depth_damage_curves: Optional[DepthDamageCurves] = None,
    ):
        if not depth_grids:
            raise ValueError("depth_grids must map at least one return period to a raster")
        self.depth_grids = {float(k): v for k, v in depth_grids.items()}
        self.structures_input = structures
        self.study_area = study_area
        self.curves = depth_damage_curves or DepthDamageCurves.default()

    # ------------------------------------------------------------------ #
    def run(self) -> RiskResult:
        gdf = self._load_structures()

        # 1. Sample depths (ft) at each structure per return period.
        depth_stack = extract_depth_stack(self.depth_grids, gdf)

        # 2. Structure attributes with defaults.
        val = self._col(gdf, "val_struct", _DEFAULT_VAL).astype(float)
        occ = self._col(gdf, "occtype", "RES1").astype(str)
        ffh = self._col(gdf, "found_ht", _DEFAULT_FFH_FT).astype(float)

        rps = sorted(self.depth_grids.keys())

        # 3. Damage ($) per structure per return period.
        damage_by_rp: Dict[float, np.ndarray] = {}
        for rp in rps:
            ground_depth = depth_stack[rp]
            ffe_depth = ground_depth - ffh  # depth above first floor
            ratio = np.array(
                [self.curves.damage_ratio(o, d) for o, d in zip(occ, ffe_depth)],
                dtype=float,
            )
            dmg = ratio * val
            damage_by_rp[rp] = dmg
            gdf[f"depth_ft_{int(rp)}yr"] = ground_depth
            gdf[f"damage_{int(rp)}yr"] = dmg

        # 4. EAD per structure ($/yr).
        gdf["ead"] = ead_for_structures(rps, damage_by_rp)

        # 5. Reach aggregation (if reach_id present).
        reaches = self._aggregate_reaches(gdf)

        return RiskResult(
            structures=gdf,
            reaches=reaches,
            return_periods=[int(r) for r in rps],
            metadata={
                "curve_keys": list(self.curves.keys()),
                "n_return_periods": len(rps),
            },
        )

    # ------------------------------------------------------------------ #
    def _load_structures(self):
        import geopandas as gpd

        src = self.structures_input
        if src is None:
            raise ValueError(
                "structures is required (a path or GeoDataFrame). NSI auto-fetch "
                "is a future enhancement; supply --nsi-local for now."
            )
        gdf = src if isinstance(src, gpd.GeoDataFrame) else gpd.read_file(src)

        if self.study_area is not None:
            area = (
                self.study_area
                if isinstance(self.study_area, gpd.GeoDataFrame)
                else gpd.read_file(self.study_area)
            )
            if area.crs is not None and gdf.crs is not None and str(area.crs) != str(gdf.crs):
                area = area.to_crs(gdf.crs)
            gdf = gpd.clip(gdf, area)

        return gdf.reset_index(drop=True)

    @staticmethod
    def _col(gdf, name, default):
        if name in gdf.columns:
            s = gdf[name]
            if isinstance(default, str):
                return s.fillna(default).values
            return s.fillna(default).values
        return np.full(len(gdf), default)

    @staticmethod
    def _aggregate_reaches(gdf):
        if "reach_id" not in gdf.columns:
            return None
        import geopandas as gpd
        import pandas as pd

        grouped = (
            gdf.groupby("reach_id")
            .agg(ead_total=("ead", "sum"), n_structures=("ead", "size"))
            .reset_index()
            .sort_values("ead_total", ascending=False)
        )
        grouped["rank"] = range(1, len(grouped) + 1)

        # Build representative reach geometry from member structure centroids.
        # Centroids are computed in a projected CRS (equal-area) to avoid the
        # "geographic CRS centroid" inaccuracy, then returned in the input CRS.
        dissolved = gdf.dissolve(by="reach_id")
        src_crs = gdf.crs
        if src_crs is not None and src_crs.is_geographic:
            cent = dissolved.to_crs("EPSG:5070").geometry.centroid.to_crs(src_crs)
        else:
            cent = dissolved.geometry.centroid
        cent = cent.reindex(grouped["reach_id"].values)
        return gpd.GeoDataFrame(grouped, geometry=cent.values, crs=src_crs)
