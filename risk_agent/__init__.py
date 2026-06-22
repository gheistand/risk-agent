"""
Risk Agent — probabilistic flood risk aggregation for HEC-RAS multi-frequency
outputs.

Takes per-return-period depth grids + structures (NSI) + depth-damage curves and
produces Expected Annual Damage (EAD) per structure, reach-level prioritization,
and FFRD-aligned risk outputs.

Quick start:

    from risk_agent import RiskAgent

    ra = RiskAgent(
        depth_grids={2: "d2.tif", 10: "d10.tif", 100: "d100.tif", 500: "d500.tif"},
        structures="nsi.gpkg",
    )
    result = ra.run()
    result.write("./risk_output/")
"""

from .core import RiskAgent, RiskResult
from .depth_damage import DepthDamageCurves
from .ead import ead_from_damages, ead_for_structures, aep_from_return_periods

__version__ = "0.1.0a0"

__all__ = [
    "RiskAgent",
    "RiskResult",
    "DepthDamageCurves",
    "ead_from_damages",
    "ead_for_structures",
    "aep_from_return_periods",
    "__version__",
]
