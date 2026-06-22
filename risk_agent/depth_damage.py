"""
Depth-damage curves.

A depth-damage curve maps inundation depth (feet, relative to the structure's
first-floor elevation) to a damage *ratio* (0.0-1.0) of structure value. Risk
Agent integrates these across return periods to compute Expected Annual Damage.

Default library: a compact USACE/IWR-style set keyed by NSI occupancy type.
These are reasonable national defaults for screening; supply calibrated local
curves via ``DepthDamageCurves.from_csv`` for regulatory work.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable

import numpy as np

# Default depth (ft) breakpoints shared by the built-in curves.
_DEFAULT_DEPTHS = np.array([-2.0, 0.0, 1.0, 2.0, 3.0, 4.0, 6.0, 8.0, 10.0, 15.0, 20.0])

# Damage ratio (fraction of structure value) at each breakpoint above.
# Compact stand-ins for the USACE generic depth-percent-damage curves.
_DEFAULT_RATIOS: Dict[str, list] = {
    # Residential, 1-story, no basement
    "RES1": [0.00, 0.10, 0.18, 0.26, 0.34, 0.42, 0.54, 0.62, 0.68, 0.78, 0.85],
    # Residential, multi-family / 2-story
    "RES3": [0.00, 0.08, 0.14, 0.22, 0.30, 0.38, 0.50, 0.58, 0.64, 0.74, 0.82],
    # Commercial
    "COM":  [0.00, 0.12, 0.20, 0.30, 0.40, 0.48, 0.60, 0.68, 0.74, 0.84, 0.90],
    # Industrial
    "IND":  [0.00, 0.10, 0.17, 0.25, 0.33, 0.41, 0.53, 0.61, 0.67, 0.77, 0.84],
    # Public / institutional
    "PUB":  [0.00, 0.09, 0.16, 0.24, 0.32, 0.40, 0.52, 0.60, 0.66, 0.76, 0.83],
}

# NSI occupancy type (occtype prefix) -> curve key.
_OCC_PREFIX_MAP = {
    "RES1": "RES1", "RES2": "RES1", "RES3": "RES3",
    "COM": "COM", "IND": "IND", "PUB": "PUB", "GOV": "PUB", "EDU": "PUB",
}


@dataclass
class DepthDamageCurves:
    """A set of depth-damage curves keyed by curve name.

    depths:  1D array of depth breakpoints (ft, relative to first-floor elev).
    ratios:  {curve_key: 1D array of damage ratios at each depth}.
    """

    depths: np.ndarray
    ratios: Dict[str, np.ndarray]

    @classmethod
    def default(cls) -> "DepthDamageCurves":
        return cls(
            depths=_DEFAULT_DEPTHS.copy(),
            ratios={k: np.asarray(v, dtype=float) for k, v in _DEFAULT_RATIOS.items()},
        )

    @classmethod
    def from_csv(cls, path: str) -> "DepthDamageCurves":
        """Load curves from a wide CSV.

        Expected format: first column ``depth_ft``, remaining columns are curve
        keys (e.g. RES1, COM, ...), values are damage ratios 0-1.
        """
        import csv

        with open(path, newline="") as fh:
            reader = csv.reader(fh)
            header = next(reader)
            keys = header[1:]
            depths: list[float] = []
            cols: dict[str, list[float]] = {k: [] for k in keys}
            for row in reader:
                if not row:
                    continue
                depths.append(float(row[0]))
                for k, v in zip(keys, row[1:]):
                    cols[k].append(float(v))
        return cls(
            depths=np.asarray(depths, dtype=float),
            ratios={k: np.asarray(v, dtype=float) for k, v in cols.items()},
        )

    def curve_key_for(self, occtype: str) -> str:
        """Resolve an NSI occupancy type to a curve key (longest-prefix match)."""
        if not occtype:
            return "RES1"
        occ = str(occtype).upper()
        # Exact key first, then longest matching prefix.
        if occ in self.ratios:
            return occ
        for prefix in sorted(_OCC_PREFIX_MAP, key=len, reverse=True):
            if occ.startswith(prefix):
                key = _OCC_PREFIX_MAP[prefix]
                if key in self.ratios:
                    return key
        return "RES1" if "RES1" in self.ratios else next(iter(self.ratios))

    def damage_ratio(self, occtype: str, depth_ft) -> np.ndarray:
        """Interpolate damage ratio(s) for a depth (ft) and occupancy type.

        Depths below the curve's first breakpoint => 0 damage; above the last =>
        clamped to the final ratio. NaN depths (dry/no-data) => 0 damage.
        """
        key = self.curve_key_for(occtype)
        ratios = self.ratios[key]
        d = np.asarray(depth_ft, dtype=float)
        out = np.interp(d, self.depths, ratios, left=0.0, right=ratios[-1])
        out = np.where(np.isnan(d), 0.0, out)
        return np.clip(out, 0.0, 1.0)

    def keys(self) -> Iterable[str]:
        return self.ratios.keys()
