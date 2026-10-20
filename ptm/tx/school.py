"""Texas school finance, district by district (docs/research/tx_school_finance_2026.md).

Base year: TEA's 2026-27 Summary of Finances (SOF), legislative payment estimate (LPE run, preliminary),
data/raw/tx_tea/fy2026-2027-sof-data.xlsx. Held fixed across policy runs (they don't depend on property
value): Tier One entitlement, weighted students (WADA), the Available School Fund, the basic allotment.
Recomputed from district value V (Comptroller T2), the M&O rate and the maximum compressed rate (MCR):

  Tier One rate      TR  = min(M&O rate, MCR)
  local share        LFA = TR x V / 100                      (100% collection, state value)
  Tier One aid       S1  = max(0, entitlement - ASF - LFA)
  Tier One recapture R1  = max(0, C1 - (entitlement - ASF))   C1 = Tier One collections
  golden pennies     g = first 8 cents above MCR; aid = g x 100 x WADA x max(0, 129.52 - y), y = V / (10,000 WADA)
  copper pennies     c = cents 9-17; aid = c x 100 x WADA x max(0, 49.72 - y); recapture on collections above 49.72 x WADA x c x 100
Collections = rate x V / 100 x the district's collection ratio on the state value, calibrated in the
base year as MO_COLL_LV1 / (TR x V / 100). (TEA's local-value field is far below T2 in oil-field districts,
e.g. Wink-Loving $5.8B vs $18.7B, so it is not used as the base.)

Hold-harmless aid: s. 48.2543 (the 2025 exemptions) is ~$0 in the SOF and is held at its SOF value;
s. 48.2542 (frozen levies after compression) is taken from the SOF for the base year.
I&S (debt) levies are rate x value; debt aid held fixed.
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOF = ROOT / "data" / "raw" / "tx_tea" / "fy2026-2027-sof-data.xlsx"
GOLDEN_YIELD, COPPER_YIELD = 129.52, 49.72      # $ per WADA per cent: BA $6,215 x 0.02084 and x 0.008
GOLDEN_CENTS, MAX_ENRICH = 0.08, 0.17


def load_sof(path: Path = SOF) -> pd.DataFrame:
    """One row per school district (ISDs, DISTRICT_TYPE_CD 1) with the inputs and SOF outputs used here."""
    i = pd.read_excel(path, sheet_name="inputs_lpe")
    o = pd.read_excel(path, sheet_name="outputs_lpe")
    a = pd.read_excel(path, sheet_name="mo_asahe_lpe")
    i = i[i["DISTRICT_TYPE_CD"] == 1]
    cols_i = ["DISTRICT_ID", "DISTRICT_NAME", "MAX_COMPR_RATE", "PY1_MO_RATE_ADOPT", "I_S_RATE", "PY1_DPV_LOCAL",
              "PY1_MO_COLL_LOCAL", "ACTUAL_FROZEN_LEVY"]
    cols_o = ["DISTRICT_ID", "TIER_I_TOT_COST_P2", "TIER_I_LOCAL_SHARE", "TIER_I_STATE_SHARE", "ASF_ALLOT", "TIER_I_MO_TAX_RATE",
              "DISTRICT_BA", "CPTD_PROPERTY_VALUE", "TIER_II_WADA", "TIER_II_DTR_LV2", "TIER_II_DTR_LV3", "TIER_II_LOCAL_REV_LV2",
              "TIER_II_LOCAL_REV_LV3", "TIER_II_AID_LV2", "TIER_II_AID_LV3", "MO_COLL_LV1", "MO_COLL_LV2", "MO_COLL_LV3",
              "RECAPTURE", "OP3_RECAP_AMT_LV1", "OP3_RECAP_AMT_LV3", "TOT_STATE_AID"]
    d = i[cols_i].merge(o[cols_o], on="DISTRICT_ID", how="left")
    asahe = [c for c in ["ASAHE", "ASAHE_065"] if c in a]
    if asahe:
        d = d.merge(a[["DISTRICT_ID"] + asahe], on="DISTRICT_ID", how="left")
    d["cdn"] = d["DISTRICT_ID"].astype(int).map(lambda v: f"{v:06d}")
    d = d.rename(columns={"MAX_COMPR_RATE": "mcr", "PY1_MO_RATE_ADOPT": "mo_rate", "I_S_RATE": "is_rate",
                          "CPTD_PROPERTY_VALUE": "value_t2", "PY1_DPV_LOCAL": "value_local", "TIER_I_TOT_COST_P2": "entitlement",
                          "ASF_ALLOT": "asf", "TIER_II_WADA": "wada"})
    # base-year collection ratio for Tier One (collections on local value at the Tier One rate)
    tr = d["TIER_I_MO_TAX_RATE"]
    d["collection_ratio"] = (d["MO_COLL_LV1"] / (tr * d["value_t2"] / 100)).where(tr * d["value_t2"] > 0).fillna(0.98)
    return d


def finance(d: pd.DataFrame, value_t2=None, mo_rate=None, mcr=None) -> pd.DataFrame:
    """Tier One and Tier Two local share, state aid and recapture for each district.
    value_t2 / mo_rate / mcr override the base year (policy runs)."""
    V = d["value_t2"] if value_t2 is None else value_t2
    rate = d["mo_rate"] if mo_rate is None else mo_rate
    M = d["mcr"] if mcr is None else mcr
    tr = np.minimum(rate, M)
    enrich = np.clip(rate - M, 0, MAX_ENRICH)
    # enrichment is measured in collected cents on the state value (TEA's DTR = collections / (T2 / 100)):
    # Austin 2026-27 adopts 17 cents, collects 15.96 (7.51 golden + 8.45 copper)
    eff = d["collection_ratio"]
    g = np.minimum(enrich, GOLDEN_CENTS) * eff
    c = np.clip(enrich - GOLDEN_CENTS, 0, MAX_ENRICH - GOLDEN_CENTS) * eff
    W = d["wada"]
    y = (V / (10_000 * W)).where(W > 0, np.inf)
    lfa = tr * V / 100
    s1 = np.maximum(0, d["entitlement"] - d["asf"] - lfa)
    c1 = tr * V / 100 * d["collection_ratio"]
    r1 = np.maximum(0, c1 - (d["entitlement"] - d["asf"]))
    golden_aid = g * 100 * W * np.maximum(0, GOLDEN_YIELD - y)
    copper_aid = c * 100 * W * np.maximum(0, COPPER_YIELD - y)
    r3 = np.maximum(0, c * V / 100 - COPPER_YIELD * W * c * 100)
    levy_mo = rate * V / 100 * d["collection_ratio"]
    return pd.DataFrame({"cdn": d["cdn"], "lfa": lfa, "tier1_aid": s1, "tier1_recapture": r1, "golden_aid": golden_aid,
                         "copper_aid": copper_aid, "copper_recapture": r3, "recapture": r1 + r3,
                         "state_aid": s1 + golden_aid + copper_aid, "levy_mo": levy_mo,
                         "net_state_cost": s1 + golden_aid + copper_aid - r1 - r3})


def check(d: pd.DataFrame | None = None) -> pd.DataFrame:
    """Base-year recomputation vs TEA's SOF outputs, statewide."""
    d = load_sof() if d is None else d
    f = finance(d)
    rows = [("Tier One local share", f.lfa.sum(), d.TIER_I_LOCAL_SHARE.sum()),
            ("Tier One state aid", f.tier1_aid.sum(), d.TIER_I_STATE_SHARE.sum()),
            ("Golden-penny aid", f.golden_aid.sum(), d.TIER_II_AID_LV2.sum()),
            ("Copper-penny aid", f.copper_aid.sum(), d.TIER_II_AID_LV3.sum()),
            ("Tier One recapture", f.tier1_recapture.sum(), d.OP3_RECAP_AMT_LV1.sum()),
            ("Copper recapture", f.copper_recapture.sum(), d.OP3_RECAP_AMT_LV3.sum())]
    t = pd.DataFrame(rows, columns=["item", "model", "sof"])
    t["ratio"] = t["model"] / t["sof"]
    return t


if __name__ == "__main__":
    t = check()
    print(t.assign(model=t.model / 1e9, sof=t.sof / 1e9).round(3).to_string(index=False))
