"""Rate-setting model: estimate next year's millage from Florida's TRIM rules and official data.

Rolled-back rate (s. 200.065(1), F.S.): the rate that would raise last year's ad valorem
proceeds from this year's taxable value, excluding new construction (and other items:
additions, deletions, annexations, large rehabilitations — approximated here by new
construction):
    rolled_back[t] = levy[t-1] / (taxable[t] - new_construction[t]) x 1000
Inputs (all official):
  - levies, adopted and rolled-back rates: DOR Table 1 (Comparison of Levies), latest edition
  - county all-property taxable value and new-construction taxable value: DOR Data Book
    (data/raw/fl_databook/<date>/), which includes 2026 preliminary values.

County general levies only for now (one countywide levy per county; Duval's consolidated
government is handled separately). Each county's Table 1 reading is checked: 2025 levy / 2025
rate must match the data book's 2025 taxable value (within 5%) or the county is flagged.
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def norm(name: str) -> str:
    n = re.sub(r"[^a-z]", "", str(name).lower())
    return n.replace("saint", "st")


def latest_databook() -> Path:
    dirs = sorted((ROOT / "data" / "raw" / "fl_databook").glob("*"))
    if not dirs:
        raise FileNotFoundError("run scripts/fl_databook.py first")
    return dirs[-1]


def _sheet(path: Path, sheet: str, header_row: int) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=sheet, header=header_row)
    df = df[df.iloc[:, 0].notna()]
    df = df[~df.iloc[:, 0].astype(str).str.contains("Total|Statewide|Source|Note", case=False)]
    return df


def load_databook(folder: Path | None = None) -> pd.DataFrame:
    """County taxable value (all property) 2024-2026, new-construction taxable value, school
    taxable value; one row per county."""
    f = folder or latest_databook()
    tv = _sheet(f / "taxable_value.xlsx", "All Property Taxable Value", 3)
    tv = tv.rename(columns={tv.columns[0]: "county"})
    out = pd.DataFrame({"county": tv["county"], "tv_status": tv["Status"],
                        "tv_2026": tv["2026 Value"], "tv_2025": tv["2025 Value"], "tv_2024": tv["2024 Value"]})
    nc = _sheet(f / "new_construction.xlsx", "Taxable Value New Construction", 3)
    nc = nc.rename(columns={nc.columns[0]: "county"})
    for y in [2024, 2025, 2026]:
        col = y if y in nc.columns else str(y)
        out = out.merge(nc[["county", col]].rename(columns={col: f"nc_{y}"}), on="county", how="left")
    sc = _sheet(f / "school_report.xlsx", "School Taxable Value", 3)
    sc = sc.rename(columns={sc.columns[0]: "county"})
    out = out.merge(sc[["county", "2026 School Taxable Value", "2025 School Taxable Value"]]
                    .rename(columns={"2026 School Taxable Value": "school_tv_2026",
                                     "2025 School Taxable Value": "school_tv_2025"}), on="county", how="left")
    out["key"] = out["county"].map(norm)
    for c in out.columns:
        if c.startswith(("tv_2", "nc_", "school_tv")):
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def county_general_levies(year: int = 2025) -> pd.DataFrame:
    """Each county's general levy from Table 1: first authority listed (the county BCC /
    general fund). Duval (consolidated Jacksonville) is excluded."""
    from ptm.rates import parse_table1, pdf_text

    rows = []
    for p in sorted((ROOT / "data" / "raw" / f"fl_rates_{year}" / "table1").glob("*.pdf")):
        if p.stem in {"Statewide", "Duval"}:
            continue
        t1 = parse_table1(pdf_text(p))
        if t1.empty:
            continue
        r = t1.iloc[0]
        rows.append({"county": p.stem, "authority": r["authority"], "mill_prev": r["millage_2024"],
                     "levy_prev": r["levy_2024"], "rbr_official": r["rolled_back"],
                     "mill": r["millage_2025"], "levy": r["levy_2025"]})
    d = pd.DataFrame(rows)
    d["key"] = d["county"].map(norm)
    return d


def school_rates_2026() -> pd.DataFrame:
    """2026-27 school millage by district.

    Required local effort (RLE) is official: FLDOE 2026-27 FEFP Second Calculation
    (inputs/fl_school_rle_2026.csv). The rule it follows — RLE millage = district RLE dollars /
    (0.96 x school taxable value) — checks exactly against FLDOE's published RLE taxes.
    Other components carry forward from 2025-26 (inputs/fl_school_millage_2025.csv): 0.748
    discretionary operating, local capital, voted operating and debt. The 2025-26 prior-period
    funding adjustment is dropped (2026-27 adjustments not known yet; e.g. Miami-Dade's levied
    RLE was 0.111 above the FEFP figure for this reason).
    """
    rle = pd.read_csv(ROOT / "inputs" / "fl_school_rle_2026.csv")
    prev = pd.read_csv(ROOT / "inputs" / "fl_school_millage_2025.csv")
    rle["key"] = rle["district"].map(norm).replace({"dade": "miamidade"})
    prev["key"] = prev["county"].map(norm).replace({"dade": "miamidade"})
    d = prev.merge(rle[["key", "rle_millage_2026"]], on="key", how="left")
    d["school_2025"] = d["total"]
    d["school_2026"] = d["total"] - d["rle"] - d["prior_period_adjustment"].fillna(0) + d["rle_millage_2026"]
    return d[["county", "key", "rle", "prior_period_adjustment", "rle_millage_2026", "school_2025", "school_2026"]]


def county_rate_table() -> pd.DataFrame:
    """Join Table 1 general levies with the data book; reading check; 2025 rolled-back test;
    2026 rolled-back rate and candidate predictions."""
    lev = county_general_levies(2025)
    db = load_databook()
    d = lev.merge(db.drop(columns="county"), on="key", how="left")
    # Reading check: levy / rate = taxable value (county levy base ~ all-property taxable)
    d["implied_tv_2025"] = d["levy"] / d["mill"] * 1000
    d["read_ok"] = (d["implied_tv_2025"] / d["tv_2025"] - 1).abs() <= 0.05
    # 2025 test: model rolled-back vs DOR's official 2025 rolled-back rate
    d["rbr_model_2025"] = d["levy_prev"] / (d["tv_2025"] - d["nc_2025"]) * 1000
    d["rbr_2025_err"] = d["rbr_model_2025"] / d["rbr_official"] - 1
    # 2026 rolled-back rate and predictions
    d["rbr_2026"] = d["levy"] / (d["tv_2026"] - d["nc_2026"]) * 1000
    d["premium_2025"] = d["mill"] / d["rbr_official"]
    ok = d["read_ok"]
    state_premium = float(np.median(d.loc[ok, "premium_2025"]))
    d["pred_keep_rate"] = d["mill"]
    d["pred_rolled_back"] = d["rbr_2026"]
    d["pred_own_premium"] = d["rbr_2026"] * d["premium_2025"]
    d["pred_state_premium"] = d["rbr_2026"] * state_premium
    d.attrs["state_premium"] = state_premium
    return d
