"""Amendment 3: change in tax on non-homestead homes and apartments (rentals and second homes)
-> data/processed/results/fl_a3_rentals.json

Usage:
    python scripts/a3_rentals.py

The projection estimates tax on property that isn't a model household from each county's tax bases
(Projection._nonowner): non-homestead residential (rentals, second homes) plus non-residential
(businesses). This splits out the residential part. It reruns current law and Amendment 3 as
written (rates unchanged, and local governments replacing the revenue under the 10-mill cap), and
records each year's tax on the non-homestead residential base (Projection._nonowner's
nonowner_tax_nh_res: county, city and school levies). Units: residential units on the 2026
rolls without a homestead exemption, less the model's own owner-occupied homes without one (which
are households, not in this base).
"""

import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))


OUT = ROOT / "data" / "processed" / "results" / "fl_a3_rentals.json"
RES_CODES = {"001", "002", "003", "004", "005", "006", "007", "008"}   # residential with homes (not vacant, not common elements)
ONE_UNIT = {"001", "002", "004", "005", "007"}

def units() -> dict:
    """Non-homestead residential units on the 2026 rolls."""
    n = 0.0
    for f in glob.glob(str(ROOT / "data" / "processed" / "fl_nal_2026" / "co*.parquet")):
        p = pd.read_parquet(f, columns=["DOR_UC", "NO_RES_UNTS", "homestead"])
        p = p[~p["homestead"].fillna(False).astype(bool) & p["DOR_UC"].isin(RES_CODES)]
        u = p["NO_RES_UNTS"].where(~p["DOR_UC"].isin(ONE_UNIT), 1).fillna(1).clip(lower=1)
        n += float(u.sum())
    b = pd.read_parquet(ROOT / "data" / "processed" / "baseline_fl_2026.parquet", columns=["WGTP", "homestead", "tenure", "mh_rented_lot", "tax_model_2026"])
    from ptm.results import owner_mask
    own_nh = float(b.loc[owner_mask(b) & ~b["homestead"].fillna(False).astype(bool), "WGTP"].sum())
    return {"roll_units": round(n), "model_owner_occupied": round(own_nh), "units": round(n - own_nh)}


def apartments(counties: pd.Index) -> pd.DataFrame:
    """Apartments on the 2026 rolls by county (DOR use codes 003 and 008, without a homestead exemption):
    non-school taxable value and units, aligned to the projection's counties."""
    from ptm.geo import fl_dor_to_fips
    frames = []
    for f in glob.glob(str(ROOT / "data" / "processed" / "fl_nal_2026" / "co*.parquet")):
        p = pd.read_parquet(f, columns=["CO_NO", "DOR_UC", "NO_RES_UNTS", "TV_NSD", "homestead"])
        p = p[~p["homestead"].fillna(False).astype(bool) & p["DOR_UC"].isin(["003", "008"])]
        frames.append(pd.DataFrame({"county_fips": fl_dor_to_fips(p["CO_NO"]), "tv": p["TV_NSD"].astype(float),
                                    "units": p["NO_RES_UNTS"].fillna(1).clip(lower=1)}))
    a = pd.concat(frames).groupby("county_fips")[["tv", "units"]].sum()
    return a.reindex(counties).fillna(0)


def main() -> None:
    import policy_grid as pg
    from ptm.compare import _run
    from ptm.policy import apply_policy
    B = pg._base()
    menu = yaml.safe_load((ROOT / "inputs" / "policy_menu.yaml").read_text(encoding="utf-8"))
    ents = {e["id"]: e for e in pg.entries(menu) if e.get("amendment3")}
    base_run = B["run"]
    base = base_run.summary["nonowner_tax_nh_res"]
    out = {"years": {}, **units()}
    # apartments' share of each county's non-homestead residential base (2026; assumed to hold)
    apt = apartments(base_run.rates.counties.index)
    b0 = base_run.nh_res_by_county[0]["base"]
    share = np.clip(np.where(b0 > 0, apt["tv"].to_numpy() / np.maximum(b0, 1), 0), 0, 1)
    out["apartment_units"] = round(float(apt["units"].sum()))
    runs = {}
    for eid in ("a3_full", "a3_full_nowait"):
        law1 = apply_policy(B["law"], {"name": eid, "changes": ents[eid]["changes"]})
        runs[eid] = {"none": _run(B["b"], pg.SCENARIO, pg.SEED, law1, pg.END, rate_replay=base_run.rates.paths),
                     "neutral": _run(B["b"], pg.SCENARIO, pg.SEED, law1, pg.END, revenue_neutral=base_run.rates.paths, millage_cap=10.0)}
    for y in base.index:
        if y <= 2026:
            continue
        i = int(y) - 2026
        row = {"current": round(float(base[y])),
               "current_apartments": round(float((base_run.nh_res_by_county[i]["tax"] * share).sum()))}
        for eid in runs:
            for m in ("none", "neutral"):
                r = runs[eid][m]
                row[f"{eid}_{m}"] = round(float(r.summary["nonowner_tax_nh_res"][y] - base[y]))
                row[f"{eid}_{m}_apartments"] = round(float(((r.nh_res_by_county[i]["tax"] - base_run.nh_res_by_county[i]["tax"]) * share).sum()))
        out["years"][str(int(y))] = row
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "years"}))
    au, ou = out["apartment_units"], out["units"] - out["apartment_units"]
    for y in ("2027", "2028", "2031", "2036"):
        r = out["years"][y]; x, xa = r["a3_full_neutral"], r["a3_full_neutral_apartments"]
        print(y, f"replace: all ${x/1e9:.2f}B = ${x/out['units']:,.0f}/unit ({x/r['current']:.1%}) | apartments ${xa/1e9:.2f}B = ${xa/au:,.0f}/unit ({xa/r['current_apartments']:.1%}) | other ${(x-xa)/1e9:.2f}B = ${(x-xa)/ou:,.0f}/unit")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
