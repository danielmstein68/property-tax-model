"""Appraisal rolls in a common form, and their taxing units matched to the Comptroller's rates.

standard_props(district): one row per residential property: county, market and appraised value, cap
  losses, homestead / over-65 / disabled / disabled-veteran flags and qualifying years, owner state.
unit_map(district): each roll taxing unit (entity code) -> the Comptroller's taxing unit (unit_id,
  levy class, 2025 rates), matched by levy class and normalized name within the appraisal district.
Rolls are converted to Parquet by scripts/tx_rolls.py (data/processed/tx_rolls/).
"""

import difflib
import re
from pathlib import Path

import numpy as np
import pandas as pd

from ptm.tx.units import load_units

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed" / "tx_rolls"
# appraisal district -> county FIPS and the Comptroller's appraisal district (county) number
DISTRICTS = {"el_paso": ("141", 71), "tarrant": ("439", 220), "travis": ("453", 227), "harris": ("201", 101),
             "dallas": ("113", 57), "collin": ("085", 43), "williamson": ("491", 246), "fort_bend": ("157", 79),
             "galveston": ("167", 84), "bell": ("027", 14)}
NOT_TAXING = re.compile(r"\b(central appraisal|appraisal district|^cad$)\b", re.I)


def classify(name: str) -> str:
    n = name.lower()
    if re.search(r"\bi\.?\s*s\.?\s*d\.?\b|independent school|\bisd\b|c\.?i\.?s\.?d", n):
        return "school"
    if re.search(r"college|\bcc\b|epcc|\bacc\b|community coll", n):
        return "college"
    if re.search(r"hospital|med(ical)? c(en)?t(e)?r|health district|\buniv med", n):
        return "hospital"
    if re.search(r"\bcounty\b", n) and not re.search(r"mud|wcid|wc ?& ?id|esd|emergency|district|water|drainage|levee|road|fwsd|pid|mmd|management|\bdist\b|#", n):
        return "county"
    if re.search(r"^(city|town|village) of\b|\bcity\b|\btown\b|\bvillage\b", n) and not re.search(r"mud|district|pid|\bdist\b", n):
        return "city"
    return "special"


def _norm(name: str) -> str:
    n = name.lower().replace("&", " and ")
    n = re.sub(r"\b(city|town|village) of\b|\bi\.?\s*s\.?\s*d\.?\b|\bindependent school district\b|\bisd\b|\bcounty\b", " ", n)
    n = re.sub(r"\bmunicipal utility district\b|\bm\.?u\.?d\.?\b", " mud ", n)
    n = re.sub(r"\bemergency (services?|svcs?|srvc) (district|dist)?\b|\bemgcy srvc\b|\besd\b", " esd ", n)
    n = re.sub(r"[^a-z0-9# ]", " ", n)
    n = re.sub(r"\bno\b|\bnumber\b", "#", n)
    n = re.sub(r"#\s*", "#", n)
    return re.sub(r"\s+", " ", n).strip()


def unit_map(district: str, entities: pd.DataFrame, year: int = 2025) -> pd.DataFrame:
    """entities: entity_cd, entity_name (one row each). Returns entity_cd, entity_name, levy_class,
    unit_id, unit_name, score, rates (mo, is, total, fmfc)."""
    _, cad = DISTRICTS[district]
    u = load_units(year)
    u = u[u["cad_id"] == cad].copy()
    u["norm"] = u["name"].map(_norm)
    out = []
    for cd, name in zip(entities["entity_cd"], entities["entity_name"]):
        if not isinstance(name, str) or NOT_TAXING.search(name):
            continue
        cls = classify(name)
        cand = u[u["levy_class"] == cls]
        best, score = None, 0.0
        nn = _norm(name)
        for i, cn in zip(cand.index, cand["norm"]):
            # the county, or the only unit of its class in the district (El Paso's "UNIV MED CTR" is the
            # El Paso County Hospital District, "EPCC" its college district)
            s = 1.0 if cls == "county" or len(cand) == 1 else difflib.SequenceMatcher(None, nn, cn).ratio()
            if s > score:
                best, score = i, s
        row = {"entity_cd": cd, "entity_name": name, "levy_class": cls, "score": round(score, 3)}
        if best is not None and score >= 0.6:
            b = u.loc[best]
            row.update(unit_id=b["unit_id"], unit_name=b["name"], mo_rate=b["mo_rate"], is_rate=b["is_rate"],
                       total_rate=b["total_rate"], fmfc_rate=b["fmfc_rate"])
        out.append(row)
    return pd.DataFrame(out)


def standard_props(district: str) -> pd.DataFrame:
    p = pd.read_parquet(PROC / f"{district}_props.parquet")
    fips, _ = DISTRICTS[district]
    return pd.DataFrame({
        "district": district, "county_fips": fips, "prop_id": p["prop_id"],
        "state_cd": p["imprv_state_cd"].fillna(p["land_state_cd"]).fillna("").str.upper(),
        "market": p["market_value"], "appraised": p["appraised_val"], "hs_cap_loss": p["ten_percent_cap"],
        "nhs_cap_loss": p["nhs_cap_loss"], "homestead": p["hs_exempt"].eq("T"),
        "over65": p["ov65_exempt"].eq("T") | p["ov65s_exempt"].eq("T"), "disabled": p["dp_exempt"].eq("T"),
        "dv_total": p["dvhs_exempt"].eq("T") | p["dvhss_exempt"].eq("T"),
        "dv_tier": np.select([p[f"dv{k}_exempt"].eq("T") | p[f"dv{k}s_exempt"].eq("T") for k in (4, 3, 2, 1)], [4, 3, 2, 1], 0),
        "hs_qualify_yr": p["hs_qualify_yr"].where(p["hs_qualify_yr"] > 1900),
        "ov65_qualify_yr": p["ov65_qualify_yr"].where(p["ov65_qualify_yr"] > 1900),
        "owner_state": p["py_addr_state"].fillna("").str.upper().str.strip(), "zip": p["situs_zip"].fillna("").str[:5]})


if __name__ == "__main__":
    import sys
    for d in sys.argv[1:] or ["el_paso", "tarrant"]:
        e = pd.read_parquet(PROC / f"{d}_units.parquet", columns=["entity_cd", "entity_name", "taxable_val"])
        g = e.groupby(["entity_cd", "entity_name"], as_index=False)["taxable_val"].sum()
        m = unit_map(d, g).merge(g, on=["entity_cd", "entity_name"])
        ok = m["unit_id"].notna()
        print(f"{d}: {ok.sum()} of {len(m)} units matched, {m.loc[ok, 'taxable_val'].sum() / m['taxable_val'].sum():.1%} of taxable value")
        print(m.sort_values("taxable_val", ascending=False)[["entity_name", "levy_class", "unit_name", "score", "total_rate"]].head(25).to_string(index=False))
        miss = m[~ok].sort_values("taxable_val", ascending=False)
        if len(miss):
            print("unmatched:", miss[["entity_name", "levy_class", "taxable_val"]].head(10).to_string(index=False))


def parcel_tax(district: str, homesteads_only: bool = True) -> pd.DataFrame:
    """Each roll property's tax by levy class at the matched units' 2025 rates: taxable value x rate,
    capped at the unit's freeze ceiling where the roll carries one. The roll benchmark for the model."""
    props = standard_props(district)
    if homesteads_only:
        props = props[props["homestead"]]
    import pyarrow.parquet as pq
    f = PROC / f"{district}_units.parquet"
    want = ["prop_id", "entity_cd", "entity_name", "taxable_val", "appraised_value", "freeze_ceiling"]
    e = pd.read_parquet(f, columns=[c for c in want if c in pq.read_schema(f).names])
    e = e[e["prop_id"].isin(set(props["prop_id"]))]
    names = e.drop_duplicates("entity_cd")[["entity_cd", "entity_name"]]
    m = unit_map(district, names)
    e = e.merge(m[["entity_cd", "levy_class", "unit_id", "total_rate"]], on="entity_cd", how="inner")
    e["tax"] = e["taxable_val"] * e["total_rate"].fillna(0) / 100
    frozen = e["freeze_ceiling"] > 0
    e.loc[frozen, "tax"] = np.minimum(e.loc[frozen, "tax"], e.loc[frozen, "freeze_ceiling"])
    t = e.pivot_table(index="prop_id", columns="levy_class", values="tax", aggfunc="sum", fill_value=0.0)
    t.columns = [f"tax_{c}" for c in t.columns]
    t["tax_total"] = t.sum(axis=1)
    sch = e[e["levy_class"] == "school"].groupby("prop_id").agg(taxable_school=("taxable_val", "sum"),
                                                                 school_freeze=("freeze_ceiling", lambda v: bool((v > 0).any())))
    return props.merge(t.reset_index(), on="prop_id", how="left").merge(sch.reset_index(), on="prop_id", how="left")
