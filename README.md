# Risk Agent

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Reep Works](https://img.shields.io/badge/by-Reep%20Works-orange)](https://reepworks.com)

**Probabilistic flood risk aggregation for HEC-RAS multi-frequency outputs.**

Risk Agent takes the depth grids and water surface profiles from a multi-frequency HEC-RAS model run and converts them into actionable flood risk metrics: Expected Annual Damage (EAD) per structure, hazard curves, probability-of-exceedance maps, and reach-level prioritization rankings aligned with FEMA's [Future Flood Risk Data (FFRD)](https://www.hec.usace.army.mil/confluence/hecnews/spring-2023/fema-s-future-of-flood-risk-data-initiative) methodology.

---

## Why Risk Agent

Traditional HEC-RAS deliverables answer: *"Is this structure in the 100-year floodplain?"*

Risk Agent answers: *"What is the expected annual flood damage to this structure, and which reaches carry the most risk?"*

That shift — from binary floodplain membership to continuous, probabilistic risk — is the direction FEMA, USACE, and the engineering profession are moving. Risk Agent makes it practical at the project and watershed scale today, using models you already have.

---

## How it fits

```
Flow frequency table
        │
        ▼
  [ RAS Agent ]  ──►  depth grids (2yr–500yr)
                       WSE profiles
                              │
                              ▼
                      [ Risk Agent ]
                              │
                 ┌────────────┼────────────┐
                 ▼            ▼            ▼
            EAD per      Hazard       Reach
           structure     curves    prioritization
                              │
                              ▼
                    CNMS / SPHERE / report
```

Risk Agent is designed to chain with [RAS Agent](https://github.com/gheistand/ras-agent) but works on any HEC-RAS output organized by return period.

---

## Features

- **Depth extraction** — joins depth grids to NSI structure locations for each return period
- **Damage estimation** — applies USACE IWR/HEC depth-damage curves (pluggable) to compute $ damage per structure per return period
- **EAD integration** — trapezoidal integration across the AEP axis to compute Expected Annual Damage per structure
- **Reach aggregation** — sums EAD by reach segment for watershed-level prioritization
- **Hazard curves** — AEP vs. depth at each structure location
- **Probability-of-exceedance maps** — GeoTIFF showing probability of exceeding a user-defined depth threshold
- **CNMS prioritization output** — reach ranking by cumulative EAD, ready for CNMS 2.0 workflows
- **FFRD-aligned outputs** — schema designed for forward compatibility with FEMA FFRD data standards

---

## Installation

```bash
pip install risk-agent
```

Or from source:

```bash
git clone https://github.com/gheistand/risk-agent.git
cd risk-agent
pip install -e .
```

**Requirements:** Python 3.10+, GDAL, geopandas, numpy, scipy

---

## Quick start

### From RAS Agent output directory

```bash
risk-agent run \
  --ras-output ./ras_output/ \
  --study-area study_boundary.gpkg \
  --output-dir ./risk_output/
```

Risk Agent will auto-detect depth grids and WSE profiles by return period convention, fetch NSI structures within the study boundary, apply default USACE depth-damage curves, and write results to `./risk_output/`.

### From explicit depth grid stack

```bash
risk-agent run \
  --depth-grids depth_2yr.tif depth_10yr.tif depth_100yr.tif depth_500yr.tif \
  --return-periods 2 10 100 500 \
  --study-area study_boundary.gpkg \
  --output-dir ./risk_output/
```

### Python API

```python
from risk_agent import RiskAgent

ra = RiskAgent(
    depth_grids={
        2: "depth_2yr.tif",
        10: "depth_10yr.tif",
        100: "depth_100yr.tif",
        500: "depth_500yr.tif",
    },
    study_area="study_boundary.gpkg",
)

results = ra.run()

# EAD per structure
print(results.structures.head())

# Reach-level prioritization
print(results.reaches.sort_values("ead_total", ascending=False).head(10))

# Write all outputs
results.write("./risk_output/")
```

---

## Outputs

| File | Description |
|---|---|
| `structures_ead.gpkg` | NSI structures with depth × return period, damage, and EAD |
| `reaches_ead.gpkg` | Reach segments with cumulative EAD and prioritization rank |
| `hazard_curves.csv` | AEP vs. depth at each structure |
| `poe_map_1ft.tif` | Probability-of-exceedance GeoTIFF at 1ft depth threshold |
| `cnms_ranking.csv` | Reach ranking ready for CNMS 2.0 import |
| `summary.json` | Run metadata, input hashes, model versions |

---

## Depth-damage curves

Default: USACE IWR/HEC national depth-damage library, organized by structure occupancy type from NSI.

Custom curves:

```python
from risk_agent import RiskAgent, DepthDamageCurves

curves = DepthDamageCurves.from_csv("my_curves.csv")

ra = RiskAgent(
    depth_grids={...},
    depth_damage_curves=curves,
)
```

---

## NSI integration

By default, Risk Agent fetches NSI structures from the USACE NSI API for the study area extent. To use a local copy:

```bash
risk-agent run \
  --depth-grids ... \
  --nsi-local ./nsi_structures.gpkg \
  --output-dir ./risk_output/
```

---

## FFRD alignment

Risk Agent is designed to be forward-compatible with FEMA's Future Flood Risk Data initiative:

- Uses NSI as the authoritative structure inventory (same as FFRD)
- Uses USACE depth-damage curves (same library as FFRD consequence modeling)
- Output schema targets FFRD data standards for interoperability
- Reach-level EAD output aligns with FFRD risk metrics

When FFRD expands to include external model plugins, Risk Agent is designed to serve as the consequence aggregation layer for HEC-RAS-based workflows.

---

## Relationship to RAS Agent

[RAS Agent](https://github.com/gheistand/ras-agent) automates HEC-RAS model execution and produces the multi-frequency depth grids and WSE profiles that Risk Agent consumes.

| | RAS Agent | Risk Agent |
|---|---|---|
| Role | Hydraulic modeling automation | Consequence and risk aggregation |
| Inputs | Flow frequency table + HEC-RAS project | Depth grids + NSI + damage curves |
| Outputs | Depth grids + WSE profiles per return period | EAD, hazard curves, prioritization |
| HEC-RAS required | Yes | No |

---

## Contributing

Contributions welcome. Please open an issue before submitting a PR for significant changes.

```bash
git clone https://github.com/gheistand/risk-agent.git
cd risk-agent
pip install -e ".[dev]"
pytest
```

---

## License

Apache 2.0 — see [LICENSE](LICENSE)

---

## Built by

[Reep Works LLC](https://reepworks.com) — AI for What Matters
