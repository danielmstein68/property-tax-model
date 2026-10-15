"""Projection results for the display -> data/processed/results/fl_projections.json

Usage:
    python scripts/results_projections.py [n_paths]      # default 30 Monte Carlo paths per scenario

For each scenario in inputs/fl_projection_assumptions.yaml: Monte Carlo bands (ptm.montecarlo) of
owner tax by year, overall and by 2026 income decile; and from the scenario's central path
(ptm.project, rate draws averaged): tax by levy, owners, average rates, Save Our Homes ratio, and
by decile each year: average tax, average income, tax as a share of income.
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ptm.economy import Economy  # noqa: E402
from ptm.montecarlo import _baseline, run_montecarlo, slim_baseline  # noqa: E402
from ptm.project import BASE_YEAR, LEVIES, Projection  # noqa: E402

END = 2036


def central_detail(scenario: str) -> dict:
    b = _baseline()
    p = Projection(b, scenario).run(END)
    s = p.summary
    hr = p.household_results
    dec = p.units["income_decile"].to_numpy()
    years = list(range(BASE_YEAR, END + 1))
    by_decile = []
    for y in years:
        w = p.weights[y]
        tax = np.nan_to_num(hr[f"tax_{y}"].to_numpy())
        inc = hr[f"income_{y}"].to_numpy()
        for d in range(1, 11):
            m = (dec == d) & (w > 0)
            ws = w[m].sum()
            by_decile.append({"year": y, "decile": d, "owners": ws,
                              "avg_tax": (tax[m] * w[m]).sum() / ws, "avg_income": (inc[m] * w[m]).sum() / ws,
                              "tax_share_of_income": (tax[m] * w[m]).sum() / max((inc[m] * w[m]).sum(), 1)})
    yearly = []
    for y in years:
        r = s.loc[y]
        yearly.append({"year": y, "owners": r.owners, "tax_total": r.tax_total, "avg_tax": r.avg_tax,
                       **{f"tax_{c}": r[f"tax_{c}"] for c in LEVIES},
                       **{f"millage_{c}_avg": r[f"millage_{c}_avg"] for c in ["school", "county", "municipal"]},
                       "homestead_assessed_to_just": r.homestead_assessed_to_just,
                       "new_owner_share": r.get("new_owner_share", 0.0),
                       "homestead_share_reset": r.homestead_share_sold})
    e = Economy(scenario)
    econ = [{"year": y, **{k: e.rate(k, y) for k in ["home_value", "nonresidential_value", "wage", "households", "cpi"]}}
            for y in range(BASE_YEAR + 1, END + 1)]
    return {"yearly": yearly, "by_decile": by_decile, "economy": econ,
            "description": e.spec["scenarios"][scenario].get("description", "")}


def clean(o):
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else round(float(o), 6)
    if isinstance(o, np.integer):
        return int(o)
    return o


def main(n_paths: int = 30) -> None:
    slim_baseline()
    spec = Economy("central").spec
    out = {"base_year": BASE_YEAR, "end_year": END, "n_paths": n_paths, "generated": pd.Timestamp.now().strftime("%Y-%m-%d"),
           "coverage": "owners only", "rate_setting": {k: v for k, v in spec["rate_setting"].items() if k != "decided"},
           "uncertainty": {k: v for k, v in spec["uncertainty"].items() if k != "note"}, "scenarios": {}}
    for sc in spec["scenarios"]:
        t = time.time()
        mc = run_montecarlo(sc, n_paths=n_paths, end_year=END)
        bands = mc["bands"]
        out["scenarios"][sc] = {**central_detail(sc), "bands": bands.to_dict("records"),
                                "draws_per_path": mc["draws_per_path"]}
        a = bands[(bands.group == "all_owners") & (bands.year == END)].iloc[0]
        print(f"{sc}: {time.time() - t:.0f}s; {END} owner tax central {a.central / 1e9:.1f}B, p10-p90 {a.p10 / 1e9:.1f}-{a.p90 / 1e9:.1f}B")
    dest = ROOT / "data" / "processed" / "results" / "fl_projections.json"
    dest.write_text(json.dumps(clean(out)), encoding="utf-8")
    print(f"wrote {dest} ({dest.stat().st_size / 1e3:.0f} kB)")


if __name__ == "__main__":
    main(*(int(a) for a in sys.argv[1:]))
