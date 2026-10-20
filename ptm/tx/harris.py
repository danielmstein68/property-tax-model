"""Harris Central Appraisal District (HCAD) roll -> the same tables as the PACS districts (ptm.tx.pacs).

HCAD's own tab-delimited layout (codebook: data/raw/tx_rolls/harris/pdataCodebook.pdf):
  Real_acct_owner.zip / real_acct.txt   one row per account: state class, market (tot_mkt_val) and
                                        appraised (capped, tot_appr_val) value, new owner date, mail state
  Real_jur_exempt.zip / jur_value.txt   account x taxing unit: appraised and taxable value
                      jur_exempt.txt    account x taxing unit x exemption category: exempt value
                      jur_tax_dist_exempt_value_rate.txt  each unit's name, 2026 adopted rate, exemption
                                        amounts and percentages
Exemption categories -> flags: RES/APR/PAR homestead; OVR/APO/POV/SUR over-65; DIS/APD/PDS disabled;
VTX/STX total veterans' exemption (incl. surviving spouse); V11-V24/VS1-VS4 partial veteran tiers.
Not in HCAD's files: freeze ceilings (estimated when calibrating) and the year the homestead
qualified (the new-owner date stands in).
Output columns use the PACS names so ptm.tx.rolls.standard_props works unchanged.
"""

import io
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "tx_rolls" / "harris"
RESIDENTIAL = ("A", "B", "E", "M")


def _tsv(zname: str, member: str, usecols: list[str]) -> pd.DataFrame:
    with zipfile.ZipFile(RAW / zname) as z, z.open(member) as f:
        return pd.read_csv(io.TextIOWrapper(f, encoding="latin-1"), sep="\t", usecols=usecols, dtype=str,
                           quoting=3, on_bad_lines="skip")


def read_harris() -> tuple[pd.DataFrame, pd.DataFrame]:
    a = _tsv("Real_acct_owner.zip", "real_acct.txt",
             ["acct", "state_class", "tot_mkt_val", "tot_appr_val", "new_own_dt", "mail_state", "site_addr_3"])
    a["acct"] = a["acct"].str.strip()
    a["state_class"] = a["state_class"].fillna("").str.strip().str.upper()
    a = a[a["state_class"].str.startswith(RESIDENTIAL)]
    for c in ["tot_mkt_val", "tot_appr_val"]:
        a[c] = pd.to_numeric(a[c], errors="coerce").fillna(0)
    ids = set(a["acct"])
    ex = _tsv("Real_jur_exempt.zip", "jur_exempt.txt", ["acct", "tax_district", "exempt_cat", "exempt_val"])
    ex["acct"] = ex["acct"].str.strip()
    ex = ex[ex["acct"].isin(ids)]
    ex["exempt_cat"] = ex["exempt_cat"].str.strip()
    ex["exempt_val"] = pd.to_numeric(ex["exempt_val"], errors="coerce").fillna(0)
    cats = ex.groupby("acct")["exempt_cat"].agg(set)
    has = lambda codes: a["acct"].map(cats).map(lambda s: bool(s & codes) if isinstance(s, set) else False)
    tiers = {4: {"V14", "V24", "VS4"}, 3: {"V13", "V23", "VS3"}, 2: {"V12", "V22", "VS2"}, 1: {"V11", "V21", "VS1"}}
    p = pd.DataFrame({
        "prop_id": a["acct"], "prop_type_cd": "R", "sup_num": 0, "imprv_state_cd": a["state_class"], "land_state_cd": a["state_class"],
        "market_value": a["tot_mkt_val"], "appraised_val": a["tot_appr_val"],
        "ten_percent_cap": (a["tot_mkt_val"] - a["tot_appr_val"]).clip(lower=0), "nhs_cap_loss": 0.0,
        "hs_exempt": np.where(has({"RES", "APR", "PAR"}), "T", "F"),
        "ov65_exempt": np.where(has({"OVR", "APO", "POV"}), "T", "F"), "ov65s_exempt": np.where(has({"SUR"}), "T", "F"),
        "dp_exempt": np.where(has({"DIS", "APD", "PDS"}), "T", "F"),
        "dvhs_exempt": np.where(has({"VTX"}), "T", "F"), "dvhss_exempt": np.where(has({"STX", "SSA", "SSP", "SST", "STT"}), "T", "F"),
        "hs_qualify_yr": pd.to_numeric(a["new_own_dt"].str[-4:], errors="coerce"), "ov65_qualify_yr": np.nan,
        "py_addr_state": a["mail_state"].fillna("").str.strip(), "situs_zip": a["site_addr_3"].fillna("").str.strip()})
    for k, codes in tiers.items():
        p[f"dv{k}_exempt"] = np.where(has(codes), "T", "F")
        p[f"dv{k}s_exempt"] = "F"
    # units: appraised and taxable value per unit; local percentage exemption from the unit's rate table
    v = _tsv("Real_jur_exempt.zip", "jur_value.txt", ["acct", "tax_district", "appraised_val", "taxable_val"])
    v["acct"] = v["acct"].str.strip()
    v = v[v["acct"].isin(ids)]
    for c in ["appraised_val", "taxable_val"]:
        v[c] = pd.to_numeric(v[c], errors="coerce").fillna(0)
    r = _tsv("Real_jur_exempt.zip", "jur_tax_dist_exempt_value_rate.txt", ["tax_dist", "name", "exempt_cd", "curr", "exempt_val", "exempt_rate"])
    r["tax_dist"] = r["tax_dist"].str.strip()
    names = r.drop_duplicates("tax_dist").set_index("tax_dist")["name"].str.strip()
    rate_2026 = pd.to_numeric(r.drop_duplicates("tax_dist").set_index("tax_dist")["curr"], errors="coerce")
    pct = pd.to_numeric(r[r["exempt_cd"].str.strip().isin(["RES", "APR"])].drop_duplicates("tax_dist").set_index("tax_dist")["exempt_rate"], errors="coerce")
    v["tax_district"] = v["tax_district"].str.strip()
    hs_ids = set(p.loc[p["hs_exempt"] == "T", "prop_id"])
    local = np.where(v["acct"].isin(hs_ids), np.maximum(v["tax_district"].map(pct).fillna(0) * v["appraised_val"], 5000)
                     * (v["tax_district"].map(pct).fillna(0) > 0), 0.0)
    e = pd.DataFrame({"prop_id": v["acct"], "sup_num": 0, "entity_cd": v["tax_district"], "entity_name": v["tax_district"].map(names),
                      "appraised_value": v["appraised_val"], "taxable_val": v["taxable_val"], "hs_local_amt": np.minimum(local, v["appraised_val"]),
                      "ov65_amt": 0.0, "dp_amt": 0.0, "dv_amt": 0.0, "freeze_ceiling": 0.0, "rate_2026": v["tax_district"].map(rate_2026)})
    return p.reset_index(drop=True), e.reset_index(drop=True)
