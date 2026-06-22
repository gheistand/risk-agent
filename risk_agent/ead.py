"""
Expected Annual Damage (EAD) integration.

Given damage ($) at a set of return periods, EAD is the integral of damage with
respect to annual exceedance probability (AEP):

    AEP = 1 / return_period
    EAD = integral over AEP in [0, 1] of damage(AEP) d(AEP)

We integrate numerically with the trapezoidal rule over the modeled AEP points,
sorted descending in AEP (i.e. ascending in return period). Standard practice
adds boundary handling:

  - Between AEP=1 (the most frequent, e.g. annual) and the largest modeled AEP,
    damage is assumed constant at the most-frequent modeled damage (or zero if
    the most frequent event already produces no damage).
  - Beyond the rarest modeled event (toward AEP=0), the remaining tail is
    treated as constant damage out to AEP=0 (conservative) unless disabled.

This module is engine-agnostic: it just needs (return_period -> damage) pairs.
"""

from __future__ import annotations

from typing import Dict, Sequence

import numpy as np


def aep_from_return_periods(return_periods: Sequence[float]) -> np.ndarray:
    rp = np.asarray(return_periods, dtype=float)
    if np.any(rp <= 0):
        raise ValueError("return periods must be positive")
    return 1.0 / rp


def ead_from_damages(
    return_periods: Sequence[float],
    damages: Sequence[float],
    *,
    extend_to_certain: bool = True,
    extend_tail: bool = True,
) -> float:
    """Compute EAD ($/yr) from damage at a set of return periods.

    Args:
        return_periods: e.g. [2, 10, 100, 500].
        damages:        damage ($) at each corresponding return period.
        extend_to_certain: include the [largest_modeled_AEP, 1.0] band, holding
            damage at the most-frequent modeled value (USACE convention).
        extend_tail: include the [0, smallest_modeled_AEP] band, holding damage
            at the rarest modeled value (conservative tail).

    Returns:
        Expected Annual Damage in dollars per year.
    """
    rp = np.asarray(return_periods, dtype=float)
    dmg = np.asarray(damages, dtype=float)
    if rp.shape != dmg.shape:
        raise ValueError("return_periods and damages must be the same length")
    if rp.size == 0:
        return 0.0

    aep = 1.0 / rp
    # Sort ascending by AEP (rarest -> most frequent) for clean integration.
    order = np.argsort(aep)
    aep = aep[order]
    dmg = np.nan_to_num(dmg[order], nan=0.0)

    # Build the integration points in AEP.
    xs = list(aep)
    ys = list(dmg)

    if extend_tail and aep[0] > 0.0:
        # Tail toward AEP=0: hold rarest damage constant.
        xs = [0.0] + xs
        ys = [dmg[0]] + ys

    if extend_to_certain and aep[-1] < 1.0:
        # Band toward AEP=1: hold most-frequent damage constant.
        xs = xs + [1.0]
        ys = ys + [dmg[-1]]

    xs_arr = np.asarray(xs, dtype=float)
    ys_arr = np.asarray(ys, dtype=float)
    # Trapezoidal integration of damage over AEP.
    return float(np.trapezoid(ys_arr, xs_arr)) if hasattr(np, "trapezoid") \
        else float(np.trapz(ys_arr, xs_arr))


def ead_for_structures(
    return_periods: Sequence[float],
    damage_by_rp: Dict[float, np.ndarray],
    **kwargs,
) -> np.ndarray:
    """Vectorized EAD across many structures.

    Args:
        return_periods: ordered list of return periods.
        damage_by_rp:   {return_period: 1D array of damages ($), one per structure}.

    Returns:
        1D array of EAD ($/yr), one per structure.
    """
    rps = list(return_periods)
    if not rps:
        raise ValueError("need at least one return period")
    n = len(next(iter(damage_by_rp.values())))
    # Stack into (n_structures, n_rp).
    matrix = np.column_stack([np.asarray(damage_by_rp[rp], dtype=float) for rp in rps])

    out = np.empty(n, dtype=float)
    for i in range(n):
        out[i] = ead_from_damages(rps, matrix[i, :], **kwargs)
    return out
