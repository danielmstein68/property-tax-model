"""Texas projections, 2026 -> 2036: homestead taxes by taxing unit under current law.

Starts from the 2026 baseline (ptm.tx.baseline.build_full: households and household x unit rows) and
steps each year (inputs/tx_projection_assumptions.yaml):
  values      market value x (1 + g_t), g_t the scenario's statewide growth
  appraised   homesteads: min(market, last year's appraised x 1.10) (Tax Code s. 23.23); a share
              `turnover` of homes sells and resets to market
  non-school  each unit's M&O rate set to its voter-approval rate: last year's M&O levy x multiplier
  units       spread over this year's base of existing property (last year's base x (1 + g_t)); I&S held
  schools     state MCR = last year's x 1.025 / (1 + g_t) when g_t > 2.5% (no new buy-downs); each district's
              MCR the lesser of its own compressed rate and the state's, at least 90% of the state's;
              M&O = MCR + the district's enrichment cents (held); I&S held
  freezes     over-65/disabled school ceilings fall by last year's taxable value x the MCR cut (s. 11.26(a-10))
  finance     each district's value grows with g_t plus new construction; Tier One / Two state aid and
              recapture from ptm.tx.school.finance
Households and exemption amounts (the law spec's nominal dollars) are held fixed; local percentages too.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from ptm.law import load_law
from ptm.tx.baseline import compute_tax
from ptm.tx.school import finance, load_sof

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "inputs" / "tx_projection_assumptions.yaml"


def growth_path(scenario: str, spec: dict) -> dict[int, float]:
    pts = spec["scenarios"][scenario]
    y0, y1 = spec["meta"]["base_year"], spec["meta"]["end_year"]
    out, last = {}, 0.0
    for y in range(y0 + 1, y1 + 1):
        last = pts.get(y, last)
        out[y] = last
    return out


def project(o: pd.DataFrame, rows: pd.DataFrame, scenario: str = "central", seed: int = 2026) -> dict:
    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    law = load_law("tx")
    rng = np.random.default_rng(seed)
    g = growth_path(scenario, spec)
    y0, y1 = spec["meta"]["base_year"], spec["meta"]["end_year"]
    hh = o[o["homestead"]].copy()
    w = hh["WGTP"]
    rows = rows[rows["hid"].isin(hh.index)].copy()
    # base-year unit rates
    rates = rows.groupby("unit_id")[["mo_rate", "is_rate"]].first()
    cls = rows.groupby("unit_id")["levy_class"].first()
    mult = cls.map(lambda c: spec["rate_setting"]["multiplier"].get(c, spec["rate_setting"]["multiplier"]["default"]))
    # schools: TEA district data (MCR, enrichment = adopted M&O above MCR)
    sof = load_sof()
    school_unit = rows.loc[rows["levy_class"] == "school", "unit_id"].drop_duplicates()
    cdn = school_unit.str.split("-").str[0] + school_unit.str.split("-").str[1]
    sch = pd.DataFrame({"unit_id": school_unit.to_numpy(), "cdn": cdn.to_numpy()}).merge(
        sof[["cdn", "mcr", "mo_rate"]].rename(columns={"mo_rate": "sof_mo"}), on="cdn", how="left").set_index("unit_id")
    sch["mcr"] = sch["mcr"].fillna(0.6254)
    sch["enrich"] = (sch["sof_mo"].fillna(sch["mcr"] + 0.06) - sch["mcr"]).clip(0, 0.17)
    state_mcr = law.rule("school_mcr").get("state_max", y0)
    floor_share = spec["school"]["floor_share"]
    # base year
    tax, x = compute_tax(hh, rows, law, y0)
    ap = hh["appraised"].copy()
    mkt = hh["market"].copy()
    sch_rows = x["levy_class"] == "school"
    frozen = sch_rows & x["ceiling_ratio"].notna() & x["hid"].map(hh["over65_or_disabled"]).fillna(False)
    ceiling = pd.Series(np.where(frozen, x["tax"], np.nan), index=x.index)
    prev_taxable = x["taxable"].copy()
    district_v = sof.set_index("cdn")["value_t2"].copy()
    out = {"scenario": scenario, "years": []}

    def record(y, t, x, mcr_state, fin):
        r = {"year": y, "growth": g.get(y, 0.0), "state_mcr": round(float(mcr_state), 4), "homesteads": float(w.sum()),
             "tax_total": float((t["tax_total"].reindex(hh.index).fillna(0) * w).sum())}
        for c in ["school", "county", "city", "college", "hospital", "special"]:
            col = f"tax_{c}"
            r[col] = float((t[col].reindex(hh.index).fillna(0) * w).sum()) if col in t else 0.0
        r["avg_tax"] = r["tax_total"] / r["homesteads"]
        r.update({k: float(fin[k].sum()) for k in ["state_aid", "recapture", "net_state_cost", "levy_mo"]})
        out["years"].append(r)

    record(y0, tax, x, state_mcr, finance(sof))
    mcr_d = sch["mcr"].copy()
    for y in range(y0 + 1, y1 + 1):
        gy = g[y]
        mkt = mkt * (1 + gy)
        sold = pd.Series(rng.random(len(ap)) < spec["turnover"], index=ap.index)
        ap = np.minimum(mkt, ap * 1.10)
        ap[sold] = mkt[sold]
        # non-school units: voter-approval M&O rate on existing property (values move with g)
        rates.loc[cls != "school", "mo_rate"] = rates.loc[cls != "school", "mo_rate"] * mult[cls != "school"] / (1 + gy)
        # schools: compression
        lim = spec["school"]["growth_limit"]
        new_state = state_mcr * (1 + lim) / (1 + gy) if gy > lim else state_mcr
        new_state = float(np.floor(new_state * 10_000) / 10_000)          # TEA truncates to 4 decimals
        own = mcr_d * (1 + spec["school"]["growth_limit"]) / (1 + gy) if gy > spec["school"]["growth_limit"] else mcr_d
        new_mcr_d = np.maximum(np.minimum(own, new_state), floor_share * new_state)
        cut = (mcr_d - new_mcr_d).reindex(x.loc[sch_rows, "unit_id"]).fillna(0).to_numpy()
        mcr_d, state_mcr = new_mcr_d, new_state
        rates.loc[sch.index, "mo_rate"] = (mcr_d + sch["enrich"]).reindex(sch.index).to_numpy()
        tax, x = compute_tax(hh, rows, law, y, rates=rates, appraised=ap)
        # freezes: ceiling falls by last year's taxable x the MCR cut; tax = min(uncapped, ceiling)
        ceiling.loc[sch_rows[sch_rows].index] = ceiling.loc[sch_rows[sch_rows].index] - prev_taxable.loc[sch_rows[sch_rows].index] * cut / 100
        uncapped = x["taxable"] * (rates["mo_rate"].reindex(x["unit_id"]).to_numpy() + rates["is_rate"].reindex(x["unit_id"]).fillna(0).to_numpy()) / 100
        x.loc[frozen, "tax"] = np.minimum(uncapped[frozen], ceiling[frozen].clip(lower=0))
        prev_taxable = x["taxable"].copy()
        t = x.pivot_table(index="hid", columns="levy_class", values="tax", aggfunc="sum", fill_value=0.0)
        t.columns = [f"tax_{c}" for c in t.columns]
        t["tax_total"] = t.sum(axis=1)
        # school finance on projected district values
        district_v = district_v * (1 + gy + spec["new_construction"])
        s2 = sof.copy()
        s2["mcr"] = s2["cdn"].map(dict(zip(sch["cdn"], mcr_d.reindex(sch.index)))).fillna(state_mcr)
        enrich = (sof["mo_rate"] - sof["mcr"]).clip(0, 0.17)
        fin = finance(s2, value_t2=s2["cdn"].map(district_v).to_numpy(), mo_rate=s2["mcr"] + enrich, mcr=s2["mcr"])
        record(y, t, x, state_mcr, fin)
    return out


if __name__ == "__main__":
    import json
    import sys
    from ptm.tx.baseline import build_full
    ds = ["harris", "dallas", "tarrant", "travis", "collin", "fort_bend", "el_paso", "williamson", "galveston"]
    o, rows = build_full(ds)
    o.to_parquet(ROOT / "data" / "processed" / "tx_baseline_2026.parquet")
    rows.to_parquet(ROOT / "data" / "processed" / "tx_baseline_2026_units.parquet")
    res = {}
    for sc in (sys.argv[1:] or ["central", "low", "high", "stall", "downturn"]):
        r = project(o, rows, sc)
        res[sc] = r
        for y in r["years"]:
            if y["year"] in (2026, 2027, 2031, 2036):
                print(f"{sc:9s} {y['year']}  homestead tax ${y['tax_total'] / 1e9:6.2f}B  avg ${y['avg_tax']:,.0f}  school ${y['tax_school'] / 1e9:5.2f}B  "
                      f"state MCR {y['state_mcr']:.4f}  school state aid ${y['state_aid'] / 1e9:5.2f}B  recapture ${y['recapture'] / 1e9:4.2f}B")
    dest = ROOT / "data" / "processed" / "results" / "tx_projections.json"
    dest.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print("wrote", dest)
