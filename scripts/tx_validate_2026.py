"""Check the Texas 2026 baseline against statewide official totals -> data/processed/results/tx_2026_validation.json

Usage:
    python scripts/tx_validate_2026.py      # needs data/processed/tx_baseline_2026.parquet (python -m ptm.tx.project)

Benchmarks (the 2025 exemptions are the 2026 ones, $140k and $60k, so the 2025 study is like-for-like
except for one year of value change, about 0-2% in Texas):
  1. Comptroller PVS 2025 final, by county:
     - state homestead exemption total ("ST MAN HSTD") = sum over homesteads of min(appraised, $140k):
       tests homestead counts and the low end of values
     - over-65/disabled school exemption ("HSTD O65") = sum over them of min(max(appraised - $140k, 0), $60k):
       tests over-65/disabled counts and their values
     - 100% disabled veterans' exemption ("VETERANS 100 PCT") = their appraised value
     - homestead counts (2024 study x 1.03, rolls where we have them)
  2. TEA 2026-27 Summary of Finances: the school levy actually imposed on frozen over-65/disabled homesteads
     (ACTUAL_FROZEN_LEVY, M&O) vs the model's school M&O tax on over-65/disabled homesteads.
Split by counties with a roll and without.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ptm.tx.pvs import county_controls, homestead_targets_2026  # noqa: E402
from ptm.tx.rolls import DISTRICTS  # noqa: E402
from ptm.tx.school import load_sof  # noqa: E402

PROC = ROOT / "data" / "processed"
ROLLS = {"harris", "dallas", "tarrant", "travis", "collin", "fort_bend", "el_paso", "williamson", "galveston", "bell"}


def main() -> None:
    o = pd.read_parquet(PROC / "tx_baseline_2026.parquet")
    rows = pd.read_parquet(PROC / "tx_baseline_2026_units.parquet")
    h = o[o["homestead"]].copy()
    w = h["WGTP"]
    ap = h["appraised"]
    h["m_state_hs"] = np.minimum(ap, 140_000) * w
    # the PVS records exemptions in order (homestead, over-65, then the veterans' total exemption covers
    # what is left), so 100% veterans count only above $140k (+$60k if 65+) and not in the over-65 total
    h["m_o65"] = np.where(h["over65_or_disabled"] & ~h["dv_total"], np.clip(ap - 140_000, 0, 60_000), 0) * w
    h["m_dv"] = np.where(h["dv_total"], np.maximum(ap - 140_000 - np.where(h["over65_or_disabled"], 60_000, 0), 0), 0) * w
    h["m_n"] = w
    m = h.groupby("county_fips_tax")[["m_n", "m_state_hs", "m_o65", "m_dv"]].sum()
    c = county_controls(2025).groupby("county_fips")[["ex_state_homestead", "ex_over65", "ex_dv_total"]].sum()
    c["homesteads"] = homestead_targets_2026()
    roll_fips = {DISTRICTS[d][0] for d in ROLLS}
    t = c.join(m, how="outer").fillna(0)
    t["group"] = np.where(t.index.isin(roll_fips), "roll counties", "other counties")
    out = {"by_group": {}}
    for g, x in list(t.groupby("group")) + [("statewide", t)]:
        out["by_group"][g] = {
            "homesteads": [float(x["m_n"].sum()), float(x["homesteads"].sum())],
            "state_homestead_exemption": [float(x["m_state_hs"].sum()), float(x["ex_state_homestead"].sum())],
            "over65_school_exemption": [float(x["m_o65"].sum()), float(x["ex_over65"].sum())],
            "dv_total_exemption": [float(x["m_dv"].sum()), float(x["ex_dv_total"].sum())]}
    # TEA: frozen levy (M&O) vs the model's school M&O on over-65/disabled homesteads
    sof = load_sof()
    sch = rows[rows["levy_class"] == "school"]
    o65 = h.index[h["over65_or_disabled"]]
    s = sch[sch["hid"].isin(o65)].copy()
    s["ap"] = s["hid"].map(ap)
    taxable = np.maximum(0, s["ap"] - np.minimum(200_000, s["ap"] * s["hs_share"].fillna(1)) - s["other_fixed"].replace(np.inf, np.nan).fillna(s["ap"]))
    taxable = np.where(s["hid"].map(h["dv_total"]), 0, taxable)
    mo = taxable * s["mo_rate"].fillna(0) / 100
    mo = np.where(s["ceiling_ratio"].notna(), mo * s["ceiling_ratio"].fillna(1), mo)
    model_frozen = float((mo * s["hid"].map(w)).sum())
    out["frozen_school_levy_mo"] = [model_frozen, float(sof["ACTUAL_FROZEN_LEVY"].sum())]
    out["by_county"] = t.reset_index(names="county_fips").round(0).to_dict("records")
    dest = PROC / "results" / "tx_2026_validation.json"
    dest.write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    print(f"{'':28s} {'model':>14s} {'official':>14s} {'ratio':>7s}")
    for g, d in out["by_group"].items():
        print(g)
        for k, (a, b) in d.items():
            print(f"  {k:26s} {a:14,.0f} {b:14,.0f} {a / b if b else float('nan'):7.3f}")
    a, b = out["frozen_school_levy_mo"]
    print(f"frozen school M&O levy (TEA)  {a:14,.0f} {b:14,.0f} {a / b:7.3f}")
    print("wrote", dest)


if __name__ == "__main__":
    main()
