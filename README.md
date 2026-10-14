# property-tax-model

A microsimulation model of state property tax policies. It estimates **who gains and loses** (distributional effects) and **how revenue changes** under policies such as rollbacks, assessment caps and exemption changes, using household data from the American Community Survey (ACS) Public Use Microdata Sample (PUMS).

- **States:** Florida (in progress), then Ohio and Texas.
- **Base year:** 2026, with year-by-year projections.
- **Status:** early. See [TODO.md](TODO.md) for what's built and what's next.

## Replicating

Requires Python 3.12 and git.

1. Clone and set up the environment:
   ```bash
   git clone https://github.com/danielmstein68/property-tax-model.git
   cd property-tax-model
   python -m venv .venv
   .venv\Scripts\activate          # Windows
   # source .venv/bin/activate     # macOS / Linux
   pip install -r requirements.txt
   ```
2. Download the data (not stored in git — `data/` is ignored):
   ```bash
   python scripts/download_pums.py --state fl --year 2024 --person
   ```
3. Download and process Florida's parcel tax rolls (all 67 counties; ~1 GB download, can take an hour):
   ```bash
   python scripts/fl_parcels.py
   ```
4. Build the input tables (growth factors, value aging, Save Our Homes history):
   ```bash
   python scripts/aging_factors.py
   python scripts/fl_soh_history.py
   python scripts/value_factors.py
   ```
   These are committed in `inputs/`, so this step is only needed to refresh them.
5. Build the 2026 baseline household file:
   ```bash
   python scripts/build_baseline.py
   ```
   Then in Python:
   ```python
   from ptm.baseline import load_baseline
   df = load_baseline()
   ```
   `psam_h12.csv` is Florida's PUMS housing file (`12` is Florida's state FIPS code; Ohio is `39`, Texas `48`).

Run the tests with:
```bash
python -m pytest
```

## Repository layout

| Path | What it is |
|---|---|
| `ptm/` | Model package. `load.py` reads PUMS into one row per occupied household. |
| `scripts/` | Data download scripts. |
| `data/` | Downloaded and processed data (git-ignored). |
| `TODO.md` | Steps done, in progress and planned; deferred decisions. |
| `LIMITATIONS.md` | What the model can't do or does only approximately. **Read before citing results.** |
| `CHALLENGES.md` | Every data/modelling problem met so far, by state, and how it was solved. **Read before adding a state.** |

## Data sources

- **ACS PUMS**, U.S. Census Bureau: https://www.census.gov/programs-surveys/acs/microdata.html
- PUMS data dictionary: https://www2.census.gov/programs-surveys/acs/tech_docs/pums/data_dict/

- **Florida parcel tax rolls (NAL)**, Florida Department of Revenue: https://floridarevenue.com/property/Pages/DataPortal_RequestAssessmentRollGISData.aspx — `scripts/fl_parcels.py`
- **Zillow Home Value Index (ZHVI)**, county series: Zillow Research, https://www.zillow.com/research/data/ — `scripts/value_factors.py`. Home value aging uses Zillow data; attribution required.
- **BLS** (QCEW wages, CPI) and **SSA** (COLAs) — `scripts/aging_factors.py`

## Key assumptions so far

- All occupied households are kept (owners, renters, and those living rent-free); an owners-only option is available.
- Model is in nominal property tax for now; how much of landlords' tax reaches renters is deferred.
- All owner-occupied homes are treated as homesteads (PUMS has no homestead flag).
- Top-coded values and zero/negative values are flagged, not dropped.
