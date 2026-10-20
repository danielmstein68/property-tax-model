"""Collin Central Appraisal District (Texas Open Data Portal, Socrata) -> the PACS-style tables.

data/raw/tx_rolls/collin/: collin_2026_appraisal.csv (one row per property: category, taxing units
"entitycodes", exemption codes, market / appraised / cap loss), collin_partial_exemptions.csv (per taxing
unit and exemption type: properties and total state and local amounts), collin_entities.csv (unit names).
The public table has no per-unit taxable values and no over-65 codes (confidential), so:
  - over-65: homesteads are flagged to the county's OV65 count (largest unit, Collin County), longest-held
    first (deed date), since owners age in place
  - per-unit taxable = appraised - state school exemptions ($140k, +$60k over-65/disabled) - the unit's
    average local homestead amount - its average local over-65 / disabled amount, floored at 0
    (100% disabled veterans: 0)
So Collin's "roll" tax is partly reconstructed; it checks values and exemption counts more than taxes.
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "tx_rolls" / "collin"


def read_collin(school_hs: float = 140_000, school_65: float = 60_000) -> tuple[pd.DataFrame, pd.DataFrame]:
    c = pd.read_csv(RAW / "collin_2026_appraisal.csv", dtype=str, usecols=[
        "propid", "proptype", "propcategorycode", "entitycodes", "exemptcodes", "exempthmstdflag", "currvalmarket",
        "currvalappraised", "currvalhscaploss", "deedeffdate", "owneraddrstate", "situszip"])
    cat = c["propcategorycode"].fillna("").str.upper()
    c = c[c["proptype"].isin(["Real", "Mobile Home"]) & cat.str.startswith(("A", "B", "E", "M"))].copy()
    for k in ["currvalmarket", "currvalappraised", "currvalhscaploss"]:
        c[k] = pd.to_numeric(c[k], errors="coerce").fillna(0)
    codes = c["exemptcodes"].fillna("").str.split(",").map(set)
    hs = c["exempthmstdflag"].eq("true")
    dvhs = codes.map(lambda s: bool(s & {"DVHS", "DVHSS"}))
    dp = codes.map(lambda s: bool(s & {"DP", "DPS"}))
    tiers = {k: codes.map(lambda s, k=k: bool(s & {f"DV{k}", f"DV{k}S"})) for k in (1, 2, 3, 4)}
    pe = pd.read_csv(RAW / "collin_partial_exemptions.csv")
    hs_local = (pe[pe["exempttypecode"] == "HS"].set_index("entitycode")["localamount"]
                / pe[pe["exempttypecode"] == "HS"].set_index("entitycode")["propcount"])
    o65_rows = pe[pe["exempttypecode"].isin(["OV65", "OV65S"])].groupby("entitycode")[["propcount", "localamount"]].sum()
    o65_local = o65_rows["localamount"] / o65_rows["propcount"]
    dp_rows = pe[pe["exempttypecode"].isin(["DP", "DPS"])].groupby("entitycode")[["propcount", "localamount"]].sum()
    dp_local = dp_rows["localamount"] / dp_rows["propcount"]
    # over-65 flags: the county's OV65 count, longest-held homesteads first
    n65 = int(o65_rows["propcount"].get("GCN", 0))
    held = pd.to_datetime(c["deedeffdate"], errors="coerce").fillna(pd.Timestamp("2026-01-01"))
    cand = c.index[hs & ~dp & ~dvhs]
    o65_idx = held.loc[cand].sort_values(kind="stable").index[:n65]
    ov65 = pd.Series(False, index=c.index)
    ov65.loc[o65_idx] = True
    p = pd.DataFrame({
        "prop_id": c["propid"], "prop_type_cd": "R", "sup_num": 0, "imprv_state_cd": cat.loc[c.index], "land_state_cd": cat.loc[c.index],
        "market_value": c["currvalmarket"], "appraised_val": c["currvalappraised"], "ten_percent_cap": c["currvalhscaploss"],
        "nhs_cap_loss": 0.0, "hs_exempt": np.where(hs, "T", "F"), "ov65_exempt": np.where(ov65, "T", "F"), "ov65s_exempt": "F",
        "dp_exempt": np.where(dp, "T", "F"), "dvhs_exempt": np.where(dvhs, "T", "F"), "dvhss_exempt": "F",
        "hs_qualify_yr": held.dt.year, "ov65_qualify_yr": np.nan, "py_addr_state": c["owneraddrstate"].fillna(""),
        "situs_zip": c["situszip"].fillna("")})
    for k, t in tiers.items():
        p[f"dv{k}_exempt"] = np.where(t, "T", "F")
        p[f"dv{k}s_exempt"] = "F"
    # units: one row per property x taxing unit
    u = c[["propid", "entitycodes", "currvalappraised"]].assign(entity_cd=c["entitycodes"].fillna("").str.split(",")).explode("entity_cd")
    u = u[u["entity_cd"].fillna("").str.len() > 0]
    names = pd.read_csv(RAW / "collin_entities.csv").set_index("code")["name"]
    flags = pd.DataFrame({"hs": hs, "o65": ov65, "dp": dp, "dvhs": dvhs}).set_index(c["propid"])
    f = flags.loc[u["propid"]].to_numpy()
    school = u["entity_cd"].str.startswith("S")
    ap = u["currvalappraised"].to_numpy()
    state = np.where(school & f[:, 0], school_hs + np.where(f[:, 1] | f[:, 2], school_65, 0), 0.0)
    local = np.where(f[:, 0], u["entity_cd"].map(hs_local).fillna(0).to_numpy(), 0.0)
    loc65 = np.where(f[:, 1], u["entity_cd"].map(o65_local).fillna(0).to_numpy(), 0.0) + np.where(f[:, 2], u["entity_cd"].map(dp_local).fillna(0).to_numpy(), 0.0)
    taxable = np.where(f[:, 3], 0.0, np.maximum(0, ap - state - local - loc65))
    e = pd.DataFrame({"prop_id": u["propid"].to_numpy(), "sup_num": 0, "entity_cd": u["entity_cd"].to_numpy(),
                      "entity_name": u["entity_cd"].map(names).to_numpy(), "appraised_value": ap, "taxable_val": taxable,
                      "hs_local_amt": np.minimum(local, ap), "freeze_ceiling": 0.0})
    return p.reset_index(drop=True), e.reset_index(drop=True)
