"""Check: Amendment 3 revenue lost by type of government, model vs the Revenue Estimating Conference
-> data/processed/results/fl_a3_rec_by_government.json (+ docs/checks/a3_rec_by_government.md)

Usage:
    python scripts/check_rec_by_government.py

The state's estimate (impact0710.pdf, July 10, 2026, Addendum 1, data/raw/fl_rec_amendment3/)
splits the loss into county governments (Boards of County Commissioners with their dependent
districts), municipalities, and independent special districts. The model has no separate special
district class (they sit in its county rates), so it is compared as county + special districts and
cities. Scored the state's way: Amendment 3 as written, rates on current law's path, no behavioural
responses (the grid's "none_static"). All property: owners from the model, other property from
county tax bases (Projection._nonowner, split here between county and city rates).
"""

import json
import sys
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from ptm import project  # noqa: E402

OUT = ROOT / "data" / "processed" / "results" / "fl_a3_rec_by_government.json"
DOC = ROOT / "docs" / "checks" / "a3_rec_by_government.md"
YEARS = [2027, 2028, 2029, 2030, 2031]
# Addendum 1, statewide impact by government type, roll years 2027-2031 (fiscal years 27-28 to 31-32), $
REC = {"county": [3_202_018_153, 5_663_206_034, 6_266_671_763, 6_954_515_623, 7_682_528_033],
       "special": [432_803_391, 775_209_713, 855_990_534, 949_408_896, 1_051_185_290],
       "city": [1_294_722_333, 2_276_076_774, 2_525_200_452, 2_806_233_229, 3_101_018_335]}

_orig = project.Projection._nonowner


def _nonowner_by_class(self, own_school, own_county):
    """Projection._nonowner, plus its non-school tax split between county (incl. special) and city rates."""
    out = _orig(self, own_school, own_county)
    ci, ok, w = self.ci, self.ci_ok, self.w
    nc, c = len(self.rates.counties), self.rates._c
    with np.errstate(divide="ignore", invalid="ignore"):
        idx = np.where(self.nh_base0["county"] > 0, c["nh_county"] / self.nh_base0["county"], 1.0)
    o26, nh_new = ok & self.orig, ok & ~self.orig & ~self.hs
    own = (np.bincount(ci[o26], weights=(self.own0["county"] * w)[o26], minlength=nc) * idx
           + np.bincount(ci[nh_new], weights=(own_county * w)[nh_new], minlength=nc) + self.sb_ex["county"])
    wsum = np.bincount(ci[ok], weights=w[ok], minlength=nc)
    avg = lambda m: np.where(wsum > 0, np.bincount(ci[ok], weights=(m * w)[ok], minlength=nc) / np.maximum(wsum, 1e-9), 0.0)
    b_ns = np.maximum(c["nh_county"] - own, 0) + c["nr_county"]
    out["nonowner_county"] = float((b_ns * avg(self.mill["county"] + np.nan_to_num(self.mill["special"]))).sum() / 1000)
    out["nonowner_city"] = float((b_ns * avg(self.mill["municipal"])).sum() / 1000)
    return out


def main() -> None:
    project.Projection._nonowner = _nonowner_by_class
    import policy_grid as pg
    from ptm.compare import _run
    from ptm.policy import apply_policy
    B = pg._base()
    menu = yaml.safe_load((ROOT / "inputs" / "policy_menu.yaml").read_text(encoding="utf-8"))
    e = next(x for x in pg.entries(menu) if x["id"] == "a3_full")
    law1 = apply_policy(B["law"], {"name": "a3_full", "changes": e["changes"]})
    new = _run(B["b"], pg.SCENARIO, pg.SEED, law1, pg.END, rate_replay=B["run"].rates.paths, behaviour=False)
    b, n = B["run"].summary, new.summary
    rows = []
    for i, y in enumerate(YEARS):
        model = {"county": -((n.loc[y, "tax_county"] - b.loc[y, "tax_county"]) + (n.loc[y, "nonowner_county"] - b.loc[y, "nonowner_county"])),
                 "city": -((n.loc[y, "tax_municipal"] - b.loc[y, "tax_municipal"]) + (n.loc[y, "nonowner_city"] - b.loc[y, "nonowner_city"]))}
        rec = {"county": REC["county"][i] + REC["special"][i], "city": REC["city"][i]}
        rows.append({"year": y, **{f"model_{k}": round(float(v)) for k, v in model.items()}, **{f"rec_{k}": v for k, v in rec.items()},
                     "rec_special": REC["special"][i]})
    OUT.write_text(json.dumps({"source": "impact0710.pdf, Addendum 1 (July 10, 2026)", "rows": rows}, indent=1), encoding="utf-8")
    lines = ["# Check: Amendment 3 revenue lost by type of government, model vs REC (2026-10-19)", "",
             "Scored like the state (as written, rates on current law's path, no behavioural responses). REC: impact0710.pdf",
             "Addendum 1. County = Boards of County Commissioners with dependent districts plus independent special districts",
             "(the model has no separate special-district class); city = municipalities. $ millions.", "",
             "| Roll year | County + special: model | REC | Gap | Cities: model | REC | Gap |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        g = lambda k: f"{r[f'model_{k}'] / r[f'rec_{k}'] - 1:+.0%}"
        lines.append(f"| {r['year']} | {r['model_county'] / 1e6:,.0f} | {r['rec_county'] / 1e6:,.0f} | {g('county')} | {r['model_city'] / 1e6:,.0f} | {r['rec_city'] / 1e6:,.0f} | {g('city')} |")
    DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[6:]))
    print(f"wrote {OUT} and {DOC}")


if __name__ == "__main__":
    main()
