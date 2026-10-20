"""Texas PUMS households brought to tax year 2026 (the survey side of the Texas baseline).

Steps:
  1. occupied households (ptm.load) from the 2024 1-year PUMS for Texas (psam_h48 / psam_p48)
  2. income aged by type, person by person (ptm.aging, inputs/tx_aging_factors_2026.csv)
  3. person flags for exemptions: householder or spouse 65+ by the end of 2026 (s. 11.42(c): the
     over-65 exemption covers the whole year a person turns 65), disabled (under 65 with an ACS
     disability and Social Security or SSI income: the proxy for Social Security disability
     eligibility, s. 11.13(m); docs/TX_DECISIONS.md), veterans by VA rating band (DRAT), and
     surviving spouses (widowed householder)
  4. home values aged from the survey (2024, interview dates spread over the year) to the Jan 1,
     2026 appraisal date: FHFA county all-transactions index, 2025 annual / 2024 annual, times the
     state's Q4 2025 / 2025 average; county = the PUMA's main county. Calibrated to the rolls later.
  5. county group (ptm.geo.county_groups), home type, years in home
"""

from pathlib import Path

import numpy as np
import pandas as pd

from ptm.aging import add_aged_income, home_type, years_in_home
from ptm.geo import county_groups
from ptm.load import load_households

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
STATE_FIPS = "48"


def person_flags(persons_path: Path, survey_year: int, base_year: int) -> pd.DataFrame:
    """Household flags from the person file (householder SPORDER 1 and spouse RELSHIPP 21/23)."""
    cols = ["SERIALNO", "SPORDER", "RELSHIPP", "AGEP", "DIS", "SSP", "SSIP", "DRAT", "MIL", "MAR"]
    p = pd.read_csv(persons_path, usecols=cols, dtype={"SERIALNO": str})
    owner_couple = (p["SPORDER"] == 1) | p["RELSHIPP"].isin([21, 23])
    age_base = p["AGEP"] + (base_year - survey_year)          # age reached during the base year
    p["over65"] = owner_couple & (age_base >= 65)
    p["disabled"] = owner_couple & (age_base < 65) & (p["DIS"] == 1) & ((p["SSP"].fillna(0) > 0) | (p["SSIP"].fillna(0) > 0))
    # VA service-connected disability rating (DRAT): 1 = 0%, 2 = 10-20%, 3 = 30-40%, 4 = 50-60%,
    # 5 = 70-100%, 6 = not reported. s. 11.22 tiers: 10-29% $5,000 ... 70%+ $12,000.
    p["dv_tier"] = np.where(owner_couple, p["DRAT"].map({2: 1, 3: 2, 4: 3, 5: 4}).fillna(0), 0)
    p["veteran"] = owner_couple & (p["MIL"] == 2)
    p["widowed"] = (p["SPORDER"] == 1) & (p["MAR"] == 2)
    hh = p.groupby("SERIALNO").agg(over65=("over65", "any"), disabled=("disabled", "any"), dv_tier=("dv_tier", "max"),
                                   veteran=("veteran", "any"), widowed=("widowed", "any"),
                                   householder_age=("AGEP", lambda a: a.iloc[0]))
    hh["over65_or_disabled"] = hh["over65"] | hh["disabled"]
    return hh.reset_index()


def value_factors(base_year: int = 2026) -> pd.DataFrame:
    """Survey-year value -> Jan 1 of the base year, by county (FHFA all-transactions indexes)."""
    c = pd.read_excel(RAW / "fhfa" / "hpi_at_county.xlsx", header=6)
    c.columns = ["state", "county", "fips", "year", "chg", "hpi", "hpi_1990", "hpi_2000"]
    c = c[c["state"] == "TX"].copy()
    c["county_fips"] = c["fips"].astype(str).str.zfill(5).str[-3:]
    w = c.pivot_table(index="county_fips", columns="year", values="hpi")
    s = pd.read_csv(RAW / "fhfa" / "hpi_at_state.csv", header=None, names=["state", "year", "q", "hpi"])
    s = s[s["state"] == "TX"]
    last = base_year - 1
    q4 = float(s[(s.year == last) & (s.q == 4)].hpi.iloc[0]) / float(s[s.year == last].hpi.mean())
    f = (w[last] / w[base_year - 2] * q4).rename("value_factor")
    state = float(s[s.year == last].hpi.mean() / s[s.year == base_year - 2].hpi.mean() * q4)
    return f.reset_index(), state


def tx_households(survey_year: int = 2024, base_year: int = 2026) -> pd.DataFrame:
    raw = RAW / f"pums_{survey_year}_1yr"
    h = load_households(raw / "psam_h48.csv")
    h = add_aged_income(h, raw / "psam_p48.csv", base_year, state="tx")
    h = h.merge(person_flags(raw / "psam_p48.csv", survey_year, base_year), on="SERIALNO", how="left")
    for c in ["over65", "disabled", "veteran", "widowed", "over65_or_disabled"]:
        h[c] = h[c].fillna(False).astype(bool)
    h["dv_tier"] = h["dv_tier"].fillna(0).astype(int)
    h["PUMA"] = h["PUMA"].astype(str).str.zfill(5)
    g = county_groups(STATE_FIPS)
    # the PUMA's main county (most tracts) and its county group
    main = g.groupby("PUMA")["county_fips"].agg(lambda s: s.value_counts().index[0])
    h["county_fips_main"] = h["PUMA"].map(main)
    h["value_area"] = h["PUMA"].map(g.drop_duplicates("PUMA").set_index("PUMA")["area"])
    f, state_f = value_factors(base_year)
    h["value_factor"] = h["county_fips_main"].map(f.set_index("county_fips")["value_factor"]).fillna(state_f)
    h["valp_mv_aged"] = h["VALP"] * h["value_factor"]
    h["home_type"] = home_type(h["BLD"])
    h["years_in_home"] = years_in_home(h["MV"], h["SERIALNO"])
    return h


if __name__ == "__main__":
    h = tx_households()
    o = h[h["tenure"] == "owner"]
    w = o["WGTP"]
    print(f"households {h.WGTP.sum():,.0f}; owners {w.sum():,.0f} ({len(o):,} records)")
    print(f"owners 65+ {w[o.over65].sum():,.0f}, disabled <65 {w[o.disabled].sum():,.0f}, rated veterans {w[o.dv_tier > 0].sum():,.0f}")
    print(f"value factor: weighted mean {np.average(o.value_factor, weights=w):.3f}; median aged value {o.valp_mv_aged.median():,.0f}")
