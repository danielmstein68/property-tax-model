"""Build the Texas economic and demographic inputs for projections.

Usage:
    python scripts/tx_economy_inputs.py

Writes:
  inputs/tx_economy_paths.csv       variable, source, year, value, growth (growth = value[t] / value[t-1] - 1)
  inputs/tx_population_by_age.csv   age_band, year, population (statewide, 18-64 and 65+)
  inputs/tx_county_population.csv  county_fips, name, pop_2020 ... pop_2060 (mid migration scenario)
  inputs/tx_life_table_2021.csv     age, qx

Sources:
  - Texas Comptroller, Certification Revenue Estimate 2026-27 (data/raw/tx_forecast/cre-2026-27-data.xlsx,
    Table 4): Texas personal income and resident population, US CPI, 2018-2027 (2025-27 projected).
  - Texas Demographic Center, Vintage 2024 population projections, mid migration scenario:
      county totals 2020-2060 from the site's totals API (data/raw/tx_demographic/tdc_2024_county_totals_*.json);
      statewide population by age, 2020 / 2040 / 2060, from the TDC projections webinar (Oct 22, 2025,
      slide 8: 18-64 17.9M / 22.4M / 25.6M; 65+ 3.9M / 6.8M / 9.2M; rounded to 0.1M on the slide). The
      full age file is behind TDC's sign-up form, so it isn't used yet (docs/TX_DECISIONS.md).
  - CDC NCHS, U.S. State Life Tables 2021, Texas, total population (NVSR 73-7; data/raw/life_tables/TX1_2021.xlsx).
"""

import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CRE = RAW / "tx_forecast" / "cre-2026-27-data.xlsx"
TDC = RAW / "tx_demographic"
LIFE = RAW / "life_tables" / "TX1_2021.xlsx"
# TDC webinar, Oct 22 2025, slide 8 (Vintage 2024, mid migration), millions
AGE_SLIDE = {"18_64": {2020: 17.9, 2040: 22.4, 2060: 25.6}, "65_plus": {2020: 3.9, 2040: 6.8, 2060: 9.2}}
CRE_ROWS = {"Personal Income (Billions, Current $)": "personal_income",
            "Resident Population (Thousands)": "population",
            "Consumer Price Index (1982-84=100)": "cpi_us"}


def cre_paths() -> pd.DataFrame:
    d = pd.read_excel(CRE, sheet_name="Table 4", header=None)
    years = [int(float(str(v).rstrip("*"))) for v in d.iloc[1, 1:]]
    rows = []
    for label, var in CRE_ROWS.items():
        r = d[d[0].astype(str).str.strip() == label].iloc[0, 1:].astype(float).to_numpy()
        for y, v in zip(years, r):
            rows.append({"variable": var, "source": "tx_cre_2026_27", "year": y, "value": v})
    p = pd.DataFrame(rows)
    pi = p[p.variable == "personal_income"].set_index("year")["value"]
    pop = p[p.variable == "population"].set_index("year")["value"]
    per = (pi * 1e9 / (pop * 1e3)).rename("value").reset_index()
    per["variable"], per["source"] = "personal_income_per_resident", "tx_cre_2026_27"
    p = pd.concat([p, per], ignore_index=True).sort_values(["variable", "year"])
    p["growth"] = p.groupby("variable")["value"].pct_change()
    # long-run nominal income growth after the Comptroller's forecast: CBO's CPI (2.3%) plus about 1.3
    # points of real growth (CBO, Budget and Economic Outlook 2026-2036: real potential GDP 1.8-2.1% a
    # year, labor force growth slowing); close to Florida's EEC average wage path for the 2030s (3.2-3.7%)
    lr = pd.DataFrame({"variable": "long_run_income", "source": "cbo_2026", "year": range(2026, 2051), "value": None, "growth": 0.036})
    return pd.concat([p[["variable", "source", "year", "value", "growth"]], lr], ignore_index=True)


def county_population() -> pd.DataFrame:
    from ptm.tx.pvs import county_fips_by_name
    j = json.loads((TDC / "tdc_2024_county_totals_Mid.json").read_text(encoding="utf-8"))
    d = pd.DataFrame(j)
    d["county_fips"] = county_fips_by_name(d["Name"]).to_numpy()
    d = d.rename(columns={f"Pop{y}": f"pop_{y}" for y in range(2020, 2061, 10)}).rename(columns={"Name": "name"})
    return d[["county_fips", "name"] + [f"pop_{y}" for y in range(2020, 2061, 10)]]


def population_by_age() -> pd.DataFrame:
    return pd.DataFrame([{"age_band": b, "year": y, "population": v * 1e6} for b, s in AGE_SLIDE.items() for y, v in s.items()])


def life_table() -> pd.DataFrame:
    d = pd.read_excel(LIFE, header=None)
    d = d[d[0].astype(str).str.match(r"^\d+")]
    age = d[0].astype(str).str.extract(r"^(\d+)")[0].astype(int)
    return pd.DataFrame({"age": age.to_numpy(), "qx": d[1].astype(float).to_numpy()})


def main() -> None:
    p = cre_paths()
    p.to_csv(ROOT / "inputs" / "tx_economy_paths.csv", index=False)
    population_by_age().to_csv(ROOT / "inputs" / "tx_population_by_age.csv", index=False)
    c = county_population()
    c.to_csv(ROOT / "inputs" / "tx_county_population.csv", index=False)
    lt = life_table()
    lt.to_csv(ROOT / "inputs" / "tx_life_table_2021.csv", index=False)
    print(p.pivot_table(index="variable", columns="year", values="growth").round(4).to_string())
    print(f"counties {len(c)}; state 2020 {c.pop_2020.sum():,.0f} 2030 {c.pop_2030.sum():,.0f} 2040 {c.pop_2040.sum():,.0f}")
    print(lt[lt.age.isin([50, 65, 75, 85, 95])].to_string(index=False))


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT))
    main()
