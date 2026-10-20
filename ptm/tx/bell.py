"""Bell Central Appraisal District certified export (tab-delimited) -> the PACS-style tables.

data/raw/tx_rolls/bell/2026-Bell-County-Certified-Export-3.zip:
  externalnal.tab         one row per parcel: use code, market, appraised and assessed value, homestead
                          cap, and up to 13 taxing units (T1..T13: name, capped value, taxable value)
  externalexemptions.tab  parcel x exemption x jurisdiction: HS homestead, HSLOC local homestead,
                          O65 / O65LOC over-65, DIS / DISLOC disabled, DVHS 100% veteran, DV1-DV4 by rating
"BELL COUNTY ROAD" (road and bridge) is dropped: the Comptroller's county rate already includes it.
No freeze ceilings (calibrated to TEA in ptm.tx.baseline).
"""

import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
ZIP = ROOT / "data" / "raw" / "tx_rolls" / "bell" / "2026-Bell-County-Certified-Export-3.zip"


def read_bell() -> tuple[pd.DataFrame, pd.DataFrame]:
    z = zipfile.ZipFile(ZIP)
    member = lambda end: next(n for n in z.namelist() if n.endswith(end))
    # a few lines carry a stray extra tab: keep their first fields (the header's count)
    a = pd.read_csv(z.open(member("externalnal.tab")), sep="\t", dtype=str, encoding="latin-1", quoting=3,
                    engine="python", on_bad_lines=lambda line: line[:108])
    a.columns = [c.strip() for c in a.columns]
    a = a.rename(columns={"T2 CAP CAL": "T2 CAP VAL"})
    use = a["PARCEL USE CD"].fillna("").str.strip().str.upper()
    a = a[use.str.startswith(("A", "B", "E", "M"))].copy()
    num = lambda s: pd.to_numeric(s, errors="coerce").fillna(0)
    a["pid"] = a["PARCEL ID"].str.strip()
    ex = pd.read_csv(z.open(member("externalexemptions.tab")), sep="\t", dtype=str, encoding="latin-1", quoting=3)
    ex["pid"], ex["cd"] = ex["parcel_id"].str.strip(), ex["EXEMPT CD"].fillna("").str.strip()
    codes = ex.groupby("pid")["cd"].agg(set).reindex(a["pid"])
    has = lambda s: codes.map(lambda c: isinstance(c, set) and bool(c & s)).to_numpy()
    hs = has({"HS", "HSLOC"})
    dvhs = hs & has({"DVHS"})
    p = pd.DataFrame({
        "prop_id": a["pid"].to_numpy(), "prop_type_cd": "R", "sup_num": 0, "imprv_state_cd": use.loc[a.index].to_numpy(),
        "land_state_cd": use.loc[a.index].to_numpy(), "market_value": num(a["MKT VAL"]).to_numpy(),
        "appraised_val": num(a["ASSESSED VALUE"]).to_numpy(), "ten_percent_cap": num(a["HMS CAP EXEMPT VAL"]).to_numpy(),
        "nhs_cap_loss": num(a["CB CAP EXEMPT VAL"]).to_numpy(), "hs_exempt": np.where(hs, "T", "F"),
        "ov65_exempt": np.where(has({"O65", "O65LOC", "DVO65"}), "T", "F"), "ov65s_exempt": "F",
        "dp_exempt": np.where(has({"DIS", "DISLOC"}), "T", "F"), "dvhs_exempt": np.where(dvhs, "T", "F"), "dvhss_exempt": "F",
        "hs_qualify_yr": pd.to_datetime(a["RECD DATE"], errors="coerce").dt.year.to_numpy(), "ov65_qualify_yr": np.nan,
        "py_addr_state": a["MAIL STATE"].fillna("").str.strip().to_numpy(), "situs_zip": ""})
    for k in (1, 2, 3, 4):
        p[f"dv{k}_exempt"] = np.where(has({f"DV{k}"}) & ~dvhs, "T", "F")
        p[f"dv{k}s_exempt"] = "F"
    # local homestead amounts by parcel and jurisdiction (HSLOC)
    loc = ex[ex["cd"] == "HSLOC"].assign(v=lambda d: num(d["TAX DIST EXEMPT VAL"]))
    parts = []
    for k in range(1, 14):
        name = a.get(f"T{k} DSCR")
        if name is None:
            continue
        name = name.fillna("").str.strip()
        ok = (name != "") & (name.str.upper() != "BELL COUNTY ROAD")
        parts.append(pd.DataFrame({"prop_id": a["pid"], "sup_num": 0, "entity_cd": name, "entity_name": name,
                                   "appraised_value": num(a[f"T{k} CAP VAL"]), "taxable_val": num(a[f"T{k} TXBL VAL"]),
                                   "hs_local_amt": 0.0, "freeze_ceiling": 0.0})[ok])
    e = pd.concat(parts, ignore_index=True)
    return p.reset_index(drop=True), e
