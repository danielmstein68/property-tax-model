"""Williamson Central Appraisal District (data.wcad.org, Socrata) -> the PACS-style tables.

data/raw/tx_rolls/williamson/: wcad_asmt_certified.csv (property x taxing unit: market, assessed (capped),
taxable), wcad_exemptions.csv (property x exemption type), wcad_property_certified.csv (property type).
Flags from exemption types: "Homestead"; "Tax Code 11.13(c) Exemption" (the school over-65/disabled
exemption) = over-65 unless also "Disabled Person"; "Disabled Veteran" (100% veterans show as $0 taxable
in every unit). Units are codes only (GWI, SRR, F01 ...): ptm.tx.rolls.unit_map matches them to the
Comptroller's units by type prefix and market value (VALUE_MATCHED).
No local-percentage amounts by unit: all of a unit's exemptions count as fixed dollars for donors.
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "tx_rolls" / "williamson"


def read_williamson() -> tuple[pd.DataFrame, pd.DataFrame]:
    a = pd.read_csv(RAW / "wcad_asmt_certified.csv", usecols=["propertyid", "taxingunitcode", "mktvalue", "assessed", "hscapadj", "hsassessed", "taxable"],
                    dtype={"propertyid": str, "taxingunitcode": str})
    pr = pd.read_csv(RAW / "wcad_property_certified.csv", usecols=["propertyid", "propertytypecode", "zip", "state"], dtype=str)
    ex = pd.read_csv(RAW / "wcad_exemptions.csv", usecols=["propertyid", "exemptiontypedescription", "exemptionstatuscode", "effectivedate"],
                     dtype=str)
    ex = ex[ex["exemptionstatuscode"].eq("A")]
    types = ex.groupby("propertyid")["exemptiontypedescription"].agg(set)
    # one row per property: values from the county's unit (GWI; market and assessed are the same in every unit)
    g = a[a["taxingunitcode"] == "GWI"].drop_duplicates("propertyid").set_index("propertyid")
    real = pr[pr["propertytypecode"].isin(["RES", "M"])].drop_duplicates("propertyid").set_index("propertyid")
    ids = g.index.intersection(real.index)
    t = types.reindex(ids)
    has = lambda name: t.map(lambda s: isinstance(s, set) and name in s).to_numpy()
    hs, c11, dp, dv = has("Homestead"), has("Tax Code 11.13(c) Exemption"), has("Disabled Person"), has("Disabled Veteran")
    taxable_all = a[a["propertyid"].isin(ids)].groupby("propertyid")["taxable"].sum().reindex(ids).fillna(0).to_numpy()
    eff = ex[ex["exemptiontypedescription"] == "Homestead"].groupby("propertyid")["effectivedate"].min()
    p = pd.DataFrame({
        "prop_id": ids, "prop_type_cd": "R", "sup_num": 0, "imprv_state_cd": "A1", "land_state_cd": "A1",
        "market_value": g.loc[ids, "mktvalue"].to_numpy(), "appraised_val": g.loc[ids, "assessed"].to_numpy(),
        "ten_percent_cap": g.loc[ids, "hscapadj"].to_numpy(), "nhs_cap_loss": 0.0, "hs_exempt": np.where(hs, "T", "F"),
        "ov65_exempt": np.where(c11 & ~dp, "T", "F"), "ov65s_exempt": "F", "dp_exempt": np.where(dp, "T", "F"),
        "dvhs_exempt": np.where(hs & dv & (taxable_all <= 0) & (g.loc[ids, "assessed"].to_numpy() > 0), "T", "F"), "dvhss_exempt": "F",
        "hs_qualify_yr": pd.to_datetime(eff.reindex(ids), errors="coerce").dt.year.to_numpy(), "ov65_qualify_yr": np.nan,
        "py_addr_state": real.loc[ids, "state"].fillna("").to_numpy(), "situs_zip": real.loc[ids, "zip"].fillna("").str[:5].to_numpy()})
    for k in (1, 2, 3, 4):
        p[f"dv{k}_exempt"] = "F"
        p[f"dv{k}s_exempt"] = "F"
    p["dv4_exempt"] = np.where(dv & (p["dvhs_exempt"] == "F"), "T", "F")    # partial veterans: tier unknown
    u = a[a["propertyid"].isin(set(ids)) & (a["taxingunitcode"] != "CAD")]
    e = pd.DataFrame({"prop_id": u["propertyid"].to_numpy(), "sup_num": 0, "entity_cd": u["taxingunitcode"].to_numpy(),
                      "entity_name": u["taxingunitcode"].to_numpy(), "market_value": u["mktvalue"].to_numpy(),
                      "appraised_value": u["assessed"].to_numpy(), "taxable_val": u["taxable"].to_numpy(),
                      "hs_local_amt": 0.0, "freeze_ceiling": 0.0,
                      # homestead exemptions apply to the homestead part only (house and up to 20 acres)
                      "hs_share": (u["hsassessed"] / u["assessed"].where(u["assessed"] > 0)).clip(0, 1).fillna(1).to_numpy()})
    return p.reset_index(drop=True), e.reset_index(drop=True)
