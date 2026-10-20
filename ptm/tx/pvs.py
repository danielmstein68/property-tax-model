"""The Comptroller's School District Property Value Study (PVS) export: statewide control totals.

One row per appraisal district x school district split (data/raw/tx_cpa/<year>-final-isd-worksheet-
export-detail.xlsx). Local values by state property category (A single-family, B multifamily, E rural
with homes, M mobile homes ...), exemption losses (state homestead, over-65, veterans, the 10% cap,
the 20% circuit breaker, freezes), and the value lost to each step of the school homestead exemption,
from which homestead counts follow: a step of $X lost on n homesteads costs about n x X (less where
the home's value is below the step).

Used for: homestead counts and values where we have no roll (most of the state), checks where we do,
and school district values for the school finance module.
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "tx_cpa"
# School homestead exemption steps in the 2025 export, newest first: INCR $100k->$140k (2025), PREV
# $40k->$100k (2023), SCND $25k->$40k (2022), THRD $15k->$25k (2015). Checked on Harris (850,527
# homesteads): loss per homestead 37.4k, 59.3k, 15.1k, 10.1k. Counts come from the smallest step
# (THRD), which almost no home is worth less than.
STEPS = {"LOSS INCR HMSTD": 40_000, "LOSS PREV INCR HMSTD": 60_000, "LOSS SCND INCR HMSTD": 15_000, "LOSS THRD INCR HMSTD": 10_000}
# The $10,000 step's column by export year (labels shift each time a step is added): 2024 SCND, 2025 THRD.
TEN_K_STEP = {2024: "LOSS SCND INCR HMSTD", 2025: "LOSS THRD INCR HMSTD"}
# Homestead counts for 2026 where there's no roll: the 2024 count (2025's is off in some districts:
# Tarrant 374k in 2025 vs 412k in 2024 and 422k on the 2026 roll) grown by 3%, the growth the 2026 rolls
# show over 2024 (El Paso +4.8%, Tarrant +2.4%). Provisional (docs/TX_DECISIONS.md).
GROWTH_2024_2026 = 1.03


def county_fips_by_name(names: pd.Series) -> pd.Series:
    """Texas county name ("McLennan", "McLennan County") -> 3-digit county FIPS (Census county list)."""
    cou = pd.read_csv(ROOT / "data" / "raw" / "tx_census" / "st48_tx_cou2020.txt", sep="|", dtype=str)
    key = lambda s: s.astype(str).str.replace("*", "", regex=False).str.replace(r"\s+county\s*$", "", regex=True, case=False).str.strip().str.lower()
    m = dict(zip(key(cou["COUNTYNAME"]), cou["COUNTYFP"]))
    out = key(names).map(m)
    if out.isna().any():
        raise ValueError(f"unknown county names: {sorted(set(names[out.isna()]))[:5]}")
    return out


def load_pvs(year: int = 2025, kind: str = "final") -> pd.DataFrame:
    d = pd.read_excel(RAW / f"{year}-{kind}-isd-worksheet-export-detail.xlsx", header=2)
    d = d[d["SPLIT ID"].notna()].copy()
    d["cad_id"] = d["CAD ID"].astype(int)
    # the split's county by name; the "2 x county no. - 1" FIPS rule fails where the Comptroller's
    # alphabetical order differs from the Census's (McLennan, McMullen); Potter-Randall share a district
    d["county_fips"] = county_fips_by_name(d["COUNTY NAME"])
    sid = d["SPLIT ID"].astype(str).str.split("-")
    d["cdn"] = sid.str[0] + sid.str[1]                                     # TEA district number, e.g. 101912
    num = [c for c in d.columns if c not in {"CAD NAME", "COUNTY NAME", "SPLIT ID", "TU NAME", "VERSION TYPE",
                                              "VERSION DATE", "VAL ASGN CD", "FINDING STATUS", "FINDING CD", "cdn", "county_fips"}]
    d[num] = d[num].apply(pd.to_numeric, errors="coerce")
    d["homesteads_est"] = d[TEN_K_STEP[year]] / 10_000
    return d


def county_controls(year: int = 2025) -> pd.DataFrame:
    """Per county (appraisal district): homesteads, local single-family / multifamily / rural-home /
    mobile-home value, state homestead and over-65 exemptions, cap and freeze losses."""
    d = load_pvs(year)
    cols = {"homesteads_est": "homesteads", "LOCL A": "value_a", "LOCL B": "value_b", "LOCL E": "value_e",
            "LOCL M": "value_m", "ST MAN HSTD": "ex_state_homestead", "HSTD O65": "ex_over65",
            "VETERANS 100 PCT": "ex_dv_total", "VETERANS PARTIAL": "ex_dv_partial", "CAPD LOCL": "loss_hs_cap",
            "LOSS TO NON HOME CAP": "loss_circuit_breaker", "O65 FREEZE LOCL": "loss_freeze", "LOCL T2": "taxable_t2"}
    g = d.groupby(["county_fips", "CAD NAME"])[list(cols)].sum().rename(columns=cols).reset_index()
    return g.rename(columns={"CAD NAME": "cad_name"})


def homestead_targets_2026() -> pd.Series:
    """2026 homesteads by county FIPS from the PVS (2024 count x GROWTH_2024_2026); rolls override these."""
    c = county_controls(2024)
    return (c.set_index("county_fips")["homesteads"] * GROWTH_2024_2026).rename("homesteads_2026")


if __name__ == "__main__":
    c = county_controls()
    print(c.sort_values("homesteads", ascending=False).head(15).round(0).to_string(index=False))
    print(f"statewide homesteads {c.homesteads.sum():,.0f}; single-family value ${c.value_a.sum() / 1e9:,.0f}B")
