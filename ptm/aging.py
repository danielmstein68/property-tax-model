"""Bring PUMS survey-year dollars forward to the model's base year.

Incomes are aged by type, person by person, then summed back to households:
wages and self-employment by wage growth, Social Security and SSI by actual
COLAs, other income by inflation. Factors come from inputs/aging_factors_<year>.csv
(built by scripts/aging_factors.py).
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INCOME_COMPONENTS = ["WAGP", "SEMP", "INTP", "SSP", "SSIP", "PAP", "RETP", "OIP"]


def _factor_table(to_year: int) -> pd.DataFrame:
    return pd.read_csv(ROOT / "inputs" / f"aging_factors_{to_year}.csv", dtype={"area": str})


def load_factors(to_year: int) -> dict[str, float]:
    """Statewide factors (rows without an area), keyed by variable."""
    f = _factor_table(to_year)
    f = f[f["area"].isna()]
    return dict(zip(f["variable"], f["factor"]))


def home_type(bld: pd.Series) -> pd.Series:
    """PUMS building type (BLD) -> sfr / condo / mobile for owner-occupied homes.

    BLD 1 mobile home, 10 boat/RV/van -> mobile; 2-3 one-family detached/attached -> sfr;
    4-9 buildings with 2+ units -> condo (owners there are condo or co-op owners).
    """
    t = pd.Series("condo", index=bld.index)
    t[bld.isin([2, 3])] = "sfr"
    t[bld.isin([1, 10])] = "mobile"
    return t


def _weighted_tercile(values: pd.Series, weights: pd.Series) -> pd.Series:
    order = values.sort_values().index
    cum = weights.loc[order].cumsum() / weights.sum()
    tier = pd.cut(cum, [0, 1 / 3, 2 / 3, 1.0001], labels=["bottom", "mid", "top"])
    return tier.reindex(values.index).astype(str)


def add_aged_values(households: pd.DataFrame, base_year: int) -> pd.DataFrame:
    """Age owners' home values to Jan 1 of the base year, by county x type x tier.

    Adds:
      county_fips, home_type, value_tier  (tier = weighted third of VALP within county)
      valp_market_aged  market value at Jan 1 (VALP x Zillow-based growth)
      valp_jv_aged      Florida just value at Jan 1 (market x just/market ratio from 2025 sales)
    Inputs: inputs/value_growth_fl_<base>.csv and inputs/just_value_ratio_fl_<base>.csv
    (built by scripts/value_factors.py). Florida only for now.
    """
    from ptm.geo import puma_main_county

    growth = pd.read_csv(ROOT / "inputs" / f"value_growth_fl_{base_year}.csv", dtype={"county_fips": str})
    jvr = pd.read_csv(ROOT / "inputs" / f"just_value_ratio_fl_{base_year}.csv", dtype={"county_fips": str})

    h = households.copy()
    puma = h["PUMA"].astype(str).str.zfill(5)
    h["county_fips"] = puma.map(puma_main_county("12").set_index("PUMA")["county_fips"])
    owner = h["VALP"].notna()
    h.loc[owner, "home_type"] = home_type(h.loc[owner, "BLD"])
    for _, idx in h[owner].groupby("county_fips").groups.items():
        h.loc[idx, "value_tier"] = _weighted_tercile(h.loc[idx, "VALP"], h.loc[idx, "WGTP"])

    keys = ["county_fips", "home_type", "value_tier"]
    g = growth.rename(columns={"type": "home_type", "tier": "value_tier", "factor": "value_growth"})
    r = jvr.rename(columns={"type": "home_type", "tier": "value_tier"})
    h = h.merge(g[keys + ["value_growth"]], on=keys, how="left")
    h = h.merge(r[keys + ["jv_to_market"]], on=keys, how="left")
    h["valp_market_aged"] = h["VALP"] * h["value_growth"]
    h["valp_jv_aged"] = h["valp_market_aged"] * h["jv_to_market"]
    return h


def add_aged_taxamt(households: pd.DataFrame, to_year: int) -> pd.DataFrame:
    """PROVISIONAL: grow owners' reported property tax by the Save Our Homes caps.

    Adds taxamt_aged; the reported 2024 TAXAMT is left untouched as the observed anchor.
    Holds tax rates fixed and assumes assessed value grew by the full cap. To be replaced
    by the rule-based version (assessed = min(prior x cap, market value), exemption
    indexing, actual rates) once home values are aged. $0 stays $0.
    """
    h = households.copy()
    h["taxamt_aged"] = h["TAXAMT"] * load_factors(to_year)["TAXAMT"]
    return h


# Years since moving in, midpoint of each PUMS MV category (MV 7 = 30+ years).
MV_YEARS_AGO = {1: 0.5, 2: 1.5, 3: 3.0, 4: 7.0, 5: 14.5, 6: 24.5, 7: 35.0}
# Rough share of a homestead's tax that is school tax; replace with county millage at calibration.
SCHOOL_SHARE = 0.37


def add_aged_taxamt_rules(households: pd.DataFrame, survey_year: int, base_year: int) -> pd.DataFrame:
    """Age owners' reported property tax with Florida's Save Our Homes and homestead rules.

    Requires add_aged_values first. For each owner (all treated as homesteads):
      1. purchase year from MV (category midpoint);
      2. assessed/just ratio in the survey year from Save Our Homes history since purchase
         (ptm.florida.soh_ratio_from_purchase);
      3. just value: survey year = valp_2024 (or VALP) x just/market ratio; base year = valp_jv_aged;
         years between interpolated geometrically;
      4. assessed value rolled forward each year: min(prior x cap, just value);
      5. school and non-school taxable value after the homestead exemption, both years;
      6. taxamt_aged = TAXAMT x (taxable base year / taxable survey year), rates held fixed,
         school share SCHOOL_SHARE.
    Owners the rules say pay nothing in the survey year but who report tax fall back to the
    caps-only growth. $0 stays $0. TAXAMT itself is untouched.
    Adds: purchase_year, soh_ratio_<survey>, soh_ratio_<base>, av_<survey>, av_<base>,
    taxamt_growth, taxamt_aged.
    """
    from ptm import florida

    hist = pd.read_csv(ROOT / "inputs" / "fl_soh_history.csv")
    caps = hist.set_index("year")["soh_cap"]
    h = households.copy()
    own = h["VALP"].notna()
    o = h.loc[own]

    years_ago = o["MV"].map(MV_YEARS_AGO)
    purchase = (survey_year - years_ago).round().clip(lower=1994).astype(int)
    ratio0 = florida.soh_ratio_from_purchase(purchase, survey_year, hist)

    # Survey-year value: valp_2024 (top-coded values replaced, ptm.topcode) when present, else VALP
    valp0 = o["valp_2024"] if "valp_2024" in o else o["VALP"]
    jv0 = valp0.to_numpy() * o["jv_to_market"].to_numpy()
    jv1 = o["valp_jv_aged"].to_numpy()
    av = ratio0 * jv0
    n = base_year - survey_year
    for k, y in enumerate(range(survey_year + 1, base_year + 1), start=1):
        jv_y = jv0 * (jv1 / jv0) ** (k / n)
        av = florida.soh_assessed(av, jv_y, caps.loc[y])

    def taxable(assessed, year):
        s, ns = florida.homestead_taxable(assessed, year)
        return SCHOOL_SHARE * s + (1 - SCHOOL_SHARE) * ns

    t0, t1 = taxable(ratio0 * jv0, survey_year), taxable(av, base_year)
    caps_only = float(np.prod([1 + caps.loc[y] for y in range(survey_year + 1, base_year + 1)]))
    growth = np.where(t0 > 0, t1 / np.where(t0 > 0, t0, 1), caps_only)

    h.loc[own, "purchase_year"] = purchase.to_numpy()
    h.loc[own, f"soh_ratio_{survey_year}"] = ratio0
    h.loc[own, f"av_{survey_year}"] = ratio0 * jv0
    h.loc[own, f"av_{base_year}"] = av
    h.loc[own, f"soh_ratio_{base_year}"] = av / jv1
    h.loc[own, "taxamt_growth"] = growth
    h["taxamt_aged"] = h["TAXAMT"] * h["taxamt_growth"]
    return h


def add_aged_rent(households: pd.DataFrame, to_year: int) -> pd.DataFrame:
    """Age contract rent by CPI area and the utilities part of gross rent by CPI-U.

    Adds rntp_aged and grntp_aged (monthly). Requires PUMA on households (Florida).
    """
    from ptm.geo import fl_cpi_area, puma_main_county

    f = _factor_table(to_year)
    rent = f[f["variable"] == "RNTP"].set_index("area")["factor"]
    util = load_factors(to_year)["UTIL"]

    h = households.copy()
    puma = h["PUMA"].astype(str).str.zfill(5)
    county = puma.map(puma_main_county("12").set_index("PUMA")["county_fips"])
    h["cpi_area"] = fl_cpi_area(county)
    h["rntp_aged"] = h["rntp_adj"] * h["cpi_area"].map(rent)
    h["grntp_aged"] = h["rntp_aged"] + (h["grntp_adj"] - h["rntp_adj"]) * util
    return h


def load_persons(path: str | Path) -> pd.DataFrame:
    """Read the PUMS person file: IDs, age, weight and income components."""
    cols = ["SERIALNO", "SPORDER", "PWGTP", "AGEP", "ADJINC", "PINCP"] + INCOME_COMPONENTS
    return pd.read_csv(path, usecols=cols, dtype={"SERIALNO": str})


def age_person_income(persons: pd.DataFrame, factors: dict[str, float]) -> pd.DataFrame:
    """Add survey-year (<var>_adj) and aged (<var>_aged) income for each component.

    PUMS income components are in the survey year's dollars after ADJINC.
    Missing components (people under 15) count as zero.
    """
    p = persons.copy()
    adjinc = p["ADJINC"] / 1_000_000
    for var in INCOME_COMPONENTS:
        base = p[var].fillna(0) * adjinc
        p[f"{var.lower()}_adj"] = base
        p[f"{var.lower()}_aged"] = base * factors[var]
    p["pincp_adj"] = p[[f"{v.lower()}_adj" for v in INCOME_COMPONENTS]].sum(axis=1)
    p["pincp_aged"] = p[[f"{v.lower()}_aged" for v in INCOME_COMPONENTS]].sum(axis=1)
    return p


def household_income(persons_aged: pd.DataFrame) -> pd.DataFrame:
    """Sum aged person income to households (one row per SERIALNO)."""
    cols = ["pincp_adj", "pincp_aged"] + [f"{v.lower()}_aged" for v in INCOME_COMPONENTS]
    hh = persons_aged.groupby("SERIALNO")[cols].sum()
    hh = hh.rename(columns={"pincp_adj": "hincp_from_persons", "pincp_aged": "hincp_aged"})
    return hh.reset_index()


def add_aged_income(households: pd.DataFrame, persons_path: str | Path, to_year: int) -> pd.DataFrame:
    """Attach aged household income (hincp_aged) and its components to households."""
    persons = age_person_income(load_persons(persons_path), load_factors(to_year))
    return households.merge(household_income(persons), on="SERIALNO", how="left")
