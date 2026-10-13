"""Bring PUMS survey-year dollars forward to the model's base year.

Incomes are aged by type, person by person, then summed back to households:
wages and self-employment by wage growth, Social Security and SSI by actual
COLAs, other income by inflation. Factors come from inputs/aging_factors_<year>.csv
(built by scripts/aging_factors.py).
"""

from pathlib import Path

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
