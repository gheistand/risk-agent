"""Unit tests for the EAD integration math."""

import numpy as np
import pytest

from risk_agent.ead import (
    aep_from_return_periods,
    ead_from_damages,
    ead_for_structures,
)


def test_aep_from_return_periods():
    np.testing.assert_allclose(
        aep_from_return_periods([2, 10, 100]), [0.5, 0.1, 0.01]
    )


def test_aep_rejects_nonpositive():
    with pytest.raises(ValueError):
        aep_from_return_periods([0, 10])


def test_ead_constant_damage_integrates_to_that_damage():
    # If damage is the same $D at every AEP and we extend to both bounds,
    # the integral over AEP in [0,1] is exactly D.
    ead = ead_from_damages([2, 10, 100], [1000.0, 1000.0, 1000.0])
    assert np.isclose(ead, 1000.0)


def test_ead_hand_calc_two_points_no_extension():
    # Two points: 10yr (AEP .1) damage 0; 100yr (AEP .01) damage 100.
    # Without boundary extension, trapezoid over AEP [.01,.1]:
    #   0.5 * (0 + 100) * (.1 - .01) = 0.5 * 100 * .09 = 4.5
    ead = ead_from_damages(
        [10, 100], [0.0, 100.0], extend_to_certain=False, extend_tail=False
    )
    assert np.isclose(ead, 4.5)


def test_ead_tail_extension_adds_area():
    # Rarest event (100yr, AEP .01) damage 100 held FLAT out to AEP=0 adds a
    # rectangle of area 100 * (.01 - 0) = 1.0 (both endpoints = 100, not a triangle).
    base = ead_from_damages(
        [10, 100], [0.0, 100.0], extend_to_certain=False, extend_tail=False
    )
    with_tail = ead_from_damages(
        [10, 100], [0.0, 100.0], extend_to_certain=False, extend_tail=True
    )
    assert np.isclose(with_tail - base, 1.0)


def test_ead_nan_damage_treated_as_zero():
    ead = ead_from_damages([10, 100], [np.nan, 100.0])
    assert np.isfinite(ead) and ead > 0


def test_ead_for_structures_vectorized_matches_scalar():
    rps = [2, 10, 100]
    dmg = {2: np.array([0.0, 10.0]), 10: np.array([50.0, 20.0]), 100: np.array([200.0, 40.0])}
    vec = ead_for_structures(rps, dmg)
    s0 = ead_from_damages(rps, [0.0, 50.0, 200.0])
    s1 = ead_from_damages(rps, [10.0, 20.0, 40.0])
    np.testing.assert_allclose(vec, [s0, s1])
