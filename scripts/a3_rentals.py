"""Amendment 3: change in tax on non-homestead homes and apartments (rentals and second homes)
-> data/processed/results/fl_a3_rentals.json

Usage:
    python scripts/a3_rentals.py

The projection estimates tax on property that isn't a model household from each county's tax bases
(Projection._nonowner): non-homestead residential (rentals, second homes) plus non-residential
(businesses). This splits out the residential part. It reruns current law and Amendment 3 as
written (rates unchanged, and local governments replacing the revenue under the 10-mill cap), and
records each year's tax on the non-homestead residential base. Units: residential units on the 2026
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

from ptm import project  # noqa: E402

OUT = ROOT / "data" / "processed" / "results" / "fl_a3_rentals.json"
RES_CODES = {"001", "002", "003", "004", "005", "006", "007", "008"}   # residential with homes (not vacant, not common elements)
ONE_UNIT = {"001", "002", "004", "005", "007"}

_orig = project.Projection._nonowner


def _nonowner_with_residential(self, own_school, own_county):
    """Projection._nonowner, plus the tax on the non-homestead residential part of the base alone."""
    out = _orig(self, own_school, own_county)
    ci, ok, w = self.ci, self.ci_ok, self.w
    nc, c = len(self.rates.counties), self.rates._c
    with np.errstate(divide="ignore", invalid="ignore"):
        idx = {k: np.where(self.nh_base0[k] > 0, c[f"nh_{k}"] / self.nh_base0[k], 1.0) for k in ("county", "school")}
    o26, nh_new = ok & self.orig, ok & ~self.orig & ~self.hs
    own = {}
    for k, cur in (("county", own_county), ("school", own_school)):
        v = np.bincount(ci[o26], weights=(self.own0[k] * w)[o26], minlength=nc) * idx[k]
        own[k] = v + np.bincount(ci[nh_new], weights=(cur * w)[nh_new], minlength=nc) + self.sb_ex[k]
    wsum = np.bincount(ci[ok], weights=w[ok], minlength=nc)
    avg = lambda m: np.where(wsum > 0, np.bincount(ci[ok], weights=(m * w)[ok], minlength=nc) / np.maximum(wsum, 1e-9), 0.0)
    m_ns = avg(self.mill["county"] + self.mill["municipal"] + np.nan_to_num(self.mill["special"]))
    m_s = avg(self.mill["school"])
    out["nh_res_tax"] = float((np.maximum(c["nh_county"] - own["county"], 0) * m_ns).sum() / 1000
                              + (np.maximum(c["nh_school"] - own["school"], 0) * m_s).sum() / 1000)
    return out


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


def main() -> None:
    project.Projection._nonowner = _nonowner_with_residential
    import policy_grid as pg
    from ptm.compare import _run
    from ptm.policy import apply_policy
    B = pg._base()
    menu = yaml.safe_load((ROOT / "inputs" / "policy_menu.yaml").read_text(encoding="utf-8"))
    ents = {e["id"]: e for e in pg.entries(menu) if e.get("amendment3")}
    base = B["run"].summary["nh_res_tax"]
    out = {"years": {}, **units()}
    runs = {}
    for eid in ("a3_full", "a3_full_nowait"):
        law1 = apply_policy(B["law"], {"name": eid, "changes": ents[eid]["changes"]})
        runs[eid] = {"none": _run(B["b"], pg.SCENARIO, pg.SEED, law1, pg.END, rate_replay=B["run"].rates.paths).summary["nh_res_tax"],
                     "neutral": _run(B["b"], pg.SCENARIO, pg.SEED, law1, pg.END, revenue_neutral=B["run"].rates.paths, millage_cap=10.0).summary["nh_res_tax"]}
    for y in base.index:
        if y <= 2026:
            continue
        out["years"][str(int(y))] = {"current": round(float(base[y])),
                                     **{f"{eid}_{m}": round(float(runs[eid][m][y] - base[y])) for eid in runs for m in ("none", "neutral")}}
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "years"}))
    for y in ("2027", "2031", "2036"):
        r = out["years"][y]
        print(y, {k: (v, round(v / out["units"])) for k, v in r.items()})
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
