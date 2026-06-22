"""Unit tests for depth-damage curves."""

import numpy as np

from risk_agent.depth_damage import DepthDamageCurves


def test_default_curve_keys():
    c = DepthDamageCurves.default()
    for k in ("RES1", "RES3", "COM", "IND", "PUB"):
        assert k in c.keys()


def test_occtype_resolution():
    c = DepthDamageCurves.default()
    assert c.curve_key_for("RES1-1SNB") == "RES1"
    assert c.curve_key_for("COM4") == "COM"
    assert c.curve_key_for("") == "RES1"
    assert c.curve_key_for("UNKNOWN_TYPE") == "RES1"


def test_damage_ratio_monotonic_and_bounded():
    c = DepthDamageCurves.default()
    depths = np.array([-5.0, 0.0, 1.0, 5.0, 25.0])
    r = c.damage_ratio("RES1", depths)
    assert r[0] == 0.0          # below curve -> 0
    assert np.all(r >= 0.0) and np.all(r <= 1.0)
    assert np.all(np.diff(r) >= -1e-9)   # non-decreasing
    assert r[-1] == r[3] or r[-1] >= r[3]  # clamps at the top


def test_nan_depth_is_zero_damage():
    c = DepthDamageCurves.default()
    r = c.damage_ratio("RES1", np.array([np.nan, 2.0]))
    assert r[0] == 0.0 and r[1] > 0.0
