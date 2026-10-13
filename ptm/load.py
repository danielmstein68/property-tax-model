"""Load an ACS PUMS housing file into a household-level DataFrame.

One row per occupied housing unit. Vacant units and group quarters are
dropped because they carry no household data.

Dollar adjustments (per the 2024 PUMS data dictionary):
  - ADJINC applies to income variables (HINCP, FINCP, ...).
  - ADJHSG applies to housing-cost variables (RNTP, GRNTP, SMOCP, ...).
  - Neither applies to VALP (property value) or TAXAMT (property tax).
"""

from pathlib import Path

import pandas as pd

TENURE_LABELS = {1: "owner", 2: "owner", 3: "renter", 4: "no_rent"}

INCOME_VARS = ["HINCP", "FINCP"]
HOUSING_COST_VARS = ["CONP", "ELEP", "FULP", "GASP", "GRNTP", "INSP",
                     "MHP", "MRGP", "RNTP", "SMOCP", "SMP", "WATP"]


def load_households(path: str | Path, owners_only: bool = False) -> pd.DataFrame:
    """Read a PUMS housing CSV and return occupied households.

    Keeps every column from the file and adds:
      tenure        owner / renter / no_rent
      adjinc, adjhsg  adjustment factors as decimals
      hincp_adj     household income in survey-year dollars
      <var>_adj     housing-cost variables in survey-year dollars
      flag_*        top-coded and zero/negative value flags (records are kept)
    """
    df = pd.read_csv(path, dtype={"SERIALNO": str, "PUMA": str}, low_memory=False)

    # Occupied housing units only: TYPEHUGQ 1 = housing unit, TEN blank = vacant
    df = df[(df["TYPEHUGQ"] == 1) & df["TEN"].notna()].copy()
    df["TEN"] = df["TEN"].astype(int)
    df["tenure"] = df["TEN"].map(TENURE_LABELS)

    if owners_only:
        df = df[df["tenure"] == "owner"].copy()

    df["adjinc"] = df["ADJINC"] / 1_000_000
    df["adjhsg"] = df["ADJHSG"] / 1_000_000
    for var in INCOME_VARS:
        if var in df:
            df[f"{var.lower()}_adj"] = df[var] * df["adjinc"]
    for var in HOUSING_COST_VARS:
        if var in df:
            df[f"{var.lower()}_adj"] = df[var] * df["adjhsg"]

    # Top-coded values are replaced by a single state-specific amount,
    # so they show up as ties at the column maximum.
    for var in ["VALP", "TAXAMT", "HINCP"]:
        df[f"flag_topcode_{var.lower()}"] = df[var].notna() & (df[var] == df[var].max())

    owner = df["tenure"] == "owner"
    df["flag_zero_taxamt"] = owner & (df["TAXAMT"] == 0)
    df["flag_nonpos_hincp"] = df["HINCP"] <= 0

    return df.reset_index(drop=True)
