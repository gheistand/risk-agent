"""
Depth extraction — sample depth grids at structure locations.

Joins a stack of per-return-period depth rasters to point structures (from NSI),
producing a depth (ft) for each structure at each return period. Depths are
measured relative to ground; first-floor offset is applied downstream in damage
estimation.
"""

from __future__ import annotations

from typing import Dict

import numpy as np


def sample_depths_at_points(raster_path: str, xs, ys):
    """Sample a single-band raster at (xs, ys) in the raster's CRS.

    Returns a 1D float array; off-raster or nodata samples become NaN.
    Caller is responsible for reprojecting points to the raster CRS.
    """
    import rasterio

    coords = list(zip(np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)))
    with rasterio.open(raster_path) as src:
        nodata = src.nodata
        vals = np.array([v[0] for v in src.sample(coords)], dtype=float)
    if nodata is not None:
        vals = np.where(vals == nodata, np.nan, vals)
    # Negative or zero depths => dry.
    vals = np.where(vals <= 0, np.nan, vals)
    return vals


def extract_depth_stack(
    depth_grids: Dict[float, str],
    structures_gdf,
) -> Dict[float, np.ndarray]:
    """Sample every depth grid at the structure points.

    Args:
        depth_grids:    {return_period: path_to_depth_raster}.
        structures_gdf: GeoDataFrame of point structures (any CRS).

    Returns:
        {return_period: 1D depth array (ft) aligned with structures_gdf rows}.
    """
    import rasterio

    out: Dict[float, np.ndarray] = {}
    for rp, path in depth_grids.items():
        with rasterio.open(path) as src:
            raster_crs = src.crs
        pts = structures_gdf
        if raster_crs is not None and structures_gdf.crs is not None:
            if str(structures_gdf.crs) != str(raster_crs):
                pts = structures_gdf.to_crs(raster_crs)
        xs = pts.geometry.x.values
        ys = pts.geometry.y.values
        out[rp] = sample_depths_at_points(path, xs, ys)
    return out
