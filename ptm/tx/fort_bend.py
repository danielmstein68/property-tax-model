"""Fort Bend Central Appraisal District "Orion" certified export -> the PACS-style tables.

data/raw/tx_rolls/fort_bend/2026_07_07_1746-Orion-2026-Certified-Export-Redacted.zip (layout workbook
inside): PropertyExport (property type, state codes), EntityExport (owner x taxing unit: market, assessed,
taxable, local and state homestead / over-65 / disabled amounts taken, freeze ceilings), ExemptionExport
(owner x exemption: HS, OA over-65, DP disabled, DV disabled veteran with Type/Level), OwnerExport.
Units are codes only (G01, S01, C17 ...): matched by type prefix and market value (ptm.tx.rolls).
"""

import io
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
ZIP = ROOT / "data" / "raw" / "tx_rolls" / "fort_bend" / "2026_07_07_1746-Orion-2026-Certified-Export-Redacted.zip"


def _csv(z: zipfile.ZipFile, part: str, cols=None) -> pd.DataFrame:
    n = next(x for x in z.namelist() if x.endswith(f"_{part}.txt"))
    return pd.read_csv(io.TextIOWrapper(z.open(n), encoding="utf-8-sig", errors="replace"), dtype=str, usecols=cols)


def entity_market() -> pd.Series:
    with zipfile.ZipFile(ZIP) as z:
        e = _csv(z, "EntityExport", ["EntityCode", "MarketValue"])
    return pd.to_numeric(e["MarketValue"], errors="coerce").groupby(e["EntityCode"]).sum()


def read_fort_bend() -> tuple[pd.DataFrame, pd.DataFrame]:
    with zipfile.ZipFile(ZIP) as z:
        pr = _csv(z, "PropertyExport", ["PropertyQuickRefID", "PropertyTypeCode", "StateCodeLand", "StateCodeImp", "SitusZip"])
        e = _csv(z, "EntityExport", ["OwnerQuickRefID", "EntityCode", "MarketValue", "AssessedValue", "TaxableValue", "HSCapAdj",
                                      "HSLocalTaken", "OALocalTaken", "DPLocalTaken", "OAFreezeCeiling", "DPFreezeCeiling", "DVXTaken"])
        x = _csv(z, "ExemptionExport", ["OwnerQuickRefID", "ExemptionCode", "EffectiveDate", "Type", "Level"])
        ow = _csv(z, "OwnerExport", ["PropertyQuickRefID", "OwnerQuickRefID", "OwnerState"]).rename(columns={"OwnerState": "State"})
    st = pr["StateCodeImp"].fillna(pr["StateCodeLand"]).fillna("").str.upper()
    pr = pr[pr["PropertyTypeCode"].str[0].isin(["R", "M"]) & st.str.startswith(("A", "B", "E", "M"))]   # RR, RX ... real; M mobile
    ow = ow[ow["PropertyQuickRefID"].isin(set(pr["PropertyQuickRefID"]))].drop_duplicates("OwnerQuickRefID")
    ids = ow["OwnerQuickRefID"]
    num = lambda s: pd.to_numeric(s, errors="coerce").fillna(0)
    for c in ["MarketValue", "AssessedValue", "TaxableValue", "HSCapAdj", "HSLocalTaken", "OAFreezeCeiling", "DPFreezeCeiling", "DVXTaken"]:
        e[c] = num(e[c])
    e = e[e["OwnerQuickRefID"].isin(set(ids))]
    first = e.groupby("OwnerQuickRefID")[["MarketValue", "AssessedValue", "HSCapAdj"]].max().reindex(ids)
    codes = x[x["OwnerQuickRefID"].isin(set(ids))].groupby("OwnerQuickRefID")["ExemptionCode"].agg(set).reindex(ids)
    has = lambda c: codes.map(lambda s: isinstance(s, set) and c in s).to_numpy()
    lvl = x[x["ExemptionCode"].eq("DV")].assign(l=lambda d: pd.to_numeric(d["Level"], errors="coerce")).groupby("OwnerQuickRefID")["l"].max().reindex(ids).fillna(0).to_numpy()
    dvx = (e.groupby("OwnerQuickRefID")["DVXTaken"].max().reindex(ids).fillna(0) > 0).to_numpy()
    since = pd.to_datetime(x[x["ExemptionCode"].eq("HS")].groupby("OwnerQuickRefID")["EffectiveDate"].min(), errors="coerce").reindex(ids)
    hs = has("HS")
    p = pd.DataFrame({
        "prop_id": ids.to_numpy(), "prop_type_cd": "R", "sup_num": 0, "imprv_state_cd": "A1", "land_state_cd": "A1",
        "market_value": first["MarketValue"].to_numpy(), "appraised_val": first["AssessedValue"].to_numpy(),
        "ten_percent_cap": first["HSCapAdj"].to_numpy(), "nhs_cap_loss": 0.0, "hs_exempt": np.where(hs, "T", "F"),
        "ov65_exempt": np.where(has("OA"), "T", "F"), "ov65s_exempt": "F", "dp_exempt": np.where(has("DP"), "T", "F"),
        "dvhs_exempt": np.where(hs & dvx, "T", "F"), "dvhss_exempt": "F", "hs_qualify_yr": since.dt.year.to_numpy(), "ov65_qualify_yr": np.nan,
        "py_addr_state": ow["State"].fillna("").to_numpy(), "situs_zip": ""})
    for k in (1, 2, 3, 4):
        p[f"dv{k}_exempt"] = np.where((lvl == k) & ~dvx, "T", "F")
        p[f"dv{k}s_exempt"] = "F"
    out = pd.DataFrame({"prop_id": e["OwnerQuickRefID"].to_numpy(), "sup_num": 0, "entity_cd": e["EntityCode"].to_numpy(),
                        "entity_name": e["EntityCode"].to_numpy(), "appraised_value": e["AssessedValue"].to_numpy(),
                        "taxable_val": e["TaxableValue"].to_numpy(), "hs_local_amt": np.minimum(e["HSLocalTaken"], e["AssessedValue"]).to_numpy(),
                        "freeze_ceiling": np.maximum(e["OAFreezeCeiling"], e["DPFreezeCeiling"]).to_numpy()})
    out = out[out["entity_cd"] != "CAD"]
    return p.reset_index(drop=True), out.reset_index(drop=True)
