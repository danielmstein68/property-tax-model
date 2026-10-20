"""Dallas Central Appraisal District certified export (CSV) -> the PACS-style tables.

data/raw/tx_rolls/dallas/DCAD2026_CERTIFIED_07232026.zip:
  ACCOUNT_APPRL_YEAR.CSV  one row per account: market (TOT_VAL), capped value (HMSTD_CAP_VAL), state code,
                          division, and for each of six unit slots (city, county, ISD, hospital, college,
                          special district) the unit's name, taxable value and freeze ceiling (dollars of tax)
  APPLIED_STD_EXEMPT.CSV  homestead effective date, over-65 / disabled, veteran disability %, per owner
  ACCT_EXEMPT_VALUE.CSV   exemption amounts applied in each slot, by exemption code (1 homestead,
                          2 over-65, 3/15 disabled veteran, 5 disabled, 14 total)
  ACCOUNT_INFO.CSV        owner state, property ZIP
The homestead amount applied in a non-school slot is that unit's local homestead exemption.
"""

import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
ZIP = ROOT / "data" / "raw" / "tx_rolls" / "dallas" / "DCAD2026_CERTIFIED_07232026.zip"
SLOTS = {"CITY": "CITY", "COUNTY": "CNTY", "ISD": "ISD", "HOSPITAL": "HOSPITAL", "COLLEGE": "COLLEGE", "SPECIAL_DIST": "SPCL"}


def read_dallas() -> tuple[pd.DataFrame, pd.DataFrame]:
    z = zipfile.ZipFile(ZIP)
    rd = lambda n, cols=None: pd.read_csv(z.open(n), dtype=str, usecols=cols, encoding="latin-1")
    a = rd("ACCOUNT_APPRL_YEAR.CSV")
    a = a[a["DIVISION_CD"].eq("RES") & a["SPTD_CODE"].fillna("").str.upper().str.startswith(("A", "B", "E", "M"))].copy()
    num = lambda s: pd.to_numeric(s, errors="coerce").fillna(0)
    a["mkt"], a["cap"] = num(a["TOT_VAL"]), num(a["HMSTD_CAP_VAL"])
    a["appr"] = np.where(a["cap"] > 0, np.minimum(a["cap"], a["mkt"]), a["mkt"])
    s = rd("APPLIED_STD_EXEMPT.CSV", ["ACCOUNT_NUM", "HOMESTEAD_EFF_DT", "OVER65_DESC", "DISABLED_DESC", "VET_DISABLE_PCT"])
    # "UNASSIGNED" = no exemption
    s = s.assign(hs=s["HOMESTEAD_EFF_DT"].notna(), o65=s["OVER65_DESC"].isin(["OVER 65", "SURVIVING SPOUSE"]),
                 dp=s["DISABLED_DESC"].eq("DISABLED"), vet=pd.to_numeric(s["VET_DISABLE_PCT"], errors="coerce"),
                 since=pd.to_datetime(s["HOMESTEAD_EFF_DT"], format="%m/%d/%Y", errors="coerce"))
    s = s.groupby("ACCOUNT_NUM").agg(hs=("hs", "max"), o65=("o65", "max"), dp=("dp", "max"), vet=("vet", "max"), since=("since", "min"))
    info = rd("ACCOUNT_INFO.CSV", ["ACCOUNT_NUM", "OWNER_STATE", "PROPERTY_ZIPCODE"]).drop_duplicates("ACCOUNT_NUM").set_index("ACCOUNT_NUM")
    s = s.reindex(a["ACCOUNT_NUM"])
    hs = s["hs"].fillna(False).astype(bool).to_numpy()
    vet = s["vet"].fillna(0).to_numpy()
    tier = np.select([vet >= 70, vet >= 50, vet >= 30, vet >= 10], [4, 3, 2, 1], 0)
    p = pd.DataFrame({
        "prop_id": a["ACCOUNT_NUM"].to_numpy(), "prop_type_cd": "R", "sup_num": 0, "imprv_state_cd": a["SPTD_CODE"].to_numpy(),
        "land_state_cd": a["SPTD_CODE"].to_numpy(), "market_value": a["mkt"].to_numpy(), "appraised_val": a["appr"].to_numpy(),
        "ten_percent_cap": (a["mkt"] - a["appr"]).clip(lower=0).to_numpy(), "nhs_cap_loss": 0.0, "hs_exempt": np.where(hs, "T", "F"),
        "ov65_exempt": np.where(s["o65"].fillna(False), "T", "F"), "ov65s_exempt": "F", "dp_exempt": np.where(s["dp"].fillna(False), "T", "F"),
        "dvhs_exempt": "F", "dvhss_exempt": "F", "hs_qualify_yr": s["since"].dt.year.to_numpy(), "ov65_qualify_yr": np.nan,
        "py_addr_state": info["OWNER_STATE"].reindex(a["ACCOUNT_NUM"]).fillna("").to_numpy(),
        "situs_zip": info["PROPERTY_ZIPCODE"].reindex(a["ACCOUNT_NUM"]).fillna("").str[:5].to_numpy()})
    for k in (1, 2, 3, 4):
        p[f"dv{k}s_exempt"] = "F"
    # local homestead amounts applied in each slot (exemption code 1)
    x = rd("ACCT_EXEMPT_VALUE.CSV", ["ACCOUNT_NUM", "EXEMPTION_CD", "CITY_APPLD_VAL", "CNTY_APPLD_VAL", "ISD_APPLD_VAL",
                                     "HOSPITAL_APPLD_VAL", "COLLEGE_APPLD_VAL", "SPCL_APPLIED_VAL"])
    # 100% disabled veterans (s. 11.131): exemption code 15 "DISABLED VET" (3 is the partial s. 11.22 one)
    dvhs = hs & a["ACCOUNT_NUM"].isin(set(x.loc[x["EXEMPTION_CD"] == "15", "ACCOUNT_NUM"])).to_numpy()
    p["dvhs_exempt"] = np.where(dvhs, "T", "F")
    for k in (1, 2, 3, 4):
        p[f"dv{k}_exempt"] = np.where((tier == k) & ~dvhs, "T", "F")
    x = x[x["EXEMPTION_CD"] == "1"].drop_duplicates("ACCOUNT_NUM").set_index("ACCOUNT_NUM")
    parts = []
    for slot, xs in SLOTS.items():
        name = a[f"{slot}_JURIS_DESC"].fillna("").str.strip()
        ok = (name != "") & (name.str.upper() != "UNASSIGNED")
        appl = "SPCL_APPLIED_VAL" if slot == "SPECIAL_DIST" else f"{xs}_APPLD_VAL"
        local = num(x[appl].reindex(a["ACCOUNT_NUM"])).to_numpy() if appl in x else 0.0
        if slot == "ISD":
            local = np.zeros(len(a))          # the ISD's homestead amount includes the state's $140k
        ceil = num(a[f"{slot}_CEILING_VALUE"]) if f"{slot}_CEILING_VALUE" in a else 0.0
        parts.append(pd.DataFrame({"prop_id": a["ACCOUNT_NUM"].to_numpy(), "sup_num": 0, "entity_cd": slot + ":" + name.to_numpy(),
                                   "entity_name": name.to_numpy(), "appraised_value": a["appr"].to_numpy(),
                                   "taxable_val": num(a[f"{slot}_TAXABLE_VAL"]).to_numpy(), "hs_local_amt": np.minimum(local, a["appr"].to_numpy()),
                                   "freeze_ceiling": np.asarray(ceil, dtype=float)})[ok.to_numpy()])
    e = pd.concat(parts, ignore_index=True)
    return p.reset_index(drop=True), e
