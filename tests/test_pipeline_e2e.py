"""End-to-end pipeline test with synthetic rasters + structures."""

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
gpd = pytest.importorskip("geopandas")
from rasterio.transform import from_origin  # noqa: E402
from shapely.geometry import Point  # noqa: E402

from risk_agent import RiskAgent  # noqa: E402


def _write_depth_raster(path, depth_value):
    """10x10 raster, constant depth (ft), EPSG:4326, covering lon[0,10] lat[0,10]."""
    data = np.full((10, 10), depth_value, dtype=np.float32)
    transform = from_origin(0, 10, 1, 1)
    with rasterio.open(
        path, "w", driver="GTiff", height=10, width=10, count=1,
        dtype="float32", crs="EPSG:4326", transform=transform, nodata=-9999.0,
    ) as dst:
        dst.write(data, 1)


@pytest.fixture
def synthetic_case(tmp_path):
    # Three return periods with increasing depth.
    grids = {}
    for rp, depth in [(10, 1.0), (100, 4.0), (500, 8.0)]:
        p = tmp_path / f"depth_{rp}.tif"
        _write_depth_raster(p, depth)
        grids[rp] = str(p)

    # Two structures inside the raster footprint, different reaches.
    gdf = gpd.GeoDataFrame(
        {
            "val_struct": [200_000.0, 300_000.0],
            "occtype": ["RES1", "COM"],
            "found_ht": [1.0, 0.5],
            "reach_id": ["R1", "R2"],
        },
        geometry=[Point(2.5, 7.5), Point(5.5, 4.5)],
        crs="EPSG:4326",
    )
    nsi = tmp_path / "nsi.gpkg"
    gdf.to_file(nsi, driver="GPKG")
    return grids, str(nsi)


def test_full_pipeline(synthetic_case, tmp_path):
    grids, nsi = synthetic_case
    ra = RiskAgent(depth_grids=grids, structures=nsi)
    result = ra.run()

    s = result.structures
    assert len(s) == 2
    assert result.return_periods == [10, 100, 500]

    # Per-RP depth + damage columns exist.
    for rp in (10, 100, 500):
        assert f"depth_ft_{rp}yr" in s.columns
        assert f"damage_{rp}yr" in s.columns

    # EAD computed, finite, positive (structures get inundated).
    assert "ead" in s.columns
    assert np.all(np.isfinite(s["ead"]))
    assert s["ead"].sum() > 0

    # Damage rises with return period for the residential structure.
    res = s[s["occtype"] == "RES1"].iloc[0]
    assert res["damage_10yr"] <= res["damage_100yr"] <= res["damage_500yr"]

    # Reach aggregation produced a ranking.
    assert result.reaches is not None
    assert set(result.reaches["reach_id"]) == {"R1", "R2"}
    assert list(result.reaches["rank"]) == sorted(result.reaches["rank"])

    # Write outputs.
    manifest = result.write(str(tmp_path / "out"))
    assert "structures_ead" in manifest
    assert "reaches_ead" in manifest
    assert "summary" in manifest


def test_requires_structures(tmp_path):
    p = tmp_path / "d.tif"
    _write_depth_raster(p, 2.0)
    ra = RiskAgent(depth_grids={100: str(p)}, structures=None)
    with pytest.raises(ValueError, match="structures is required"):
        ra.run()
