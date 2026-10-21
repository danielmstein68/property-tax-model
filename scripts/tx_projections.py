"""Texas projection results for the display -> data/processed/results/tx_projections.json

Usage:
    python scripts/tx_projections.py [n_paths]      # default 30 Monte Carlo paths per scenario

For each scenario in inputs/tx_projection_assumptions.yaml: the central path (ptm.tx.project; rates at each
unit's 2025 position): yearly summary (homestead, owner and other property tax by class, owners, over-65
homesteads, sales, rates, school finance), and by income decile and by householder age each year: owners,
average tax, average income, tax as a share of income. Monte Carlo bands (ptm.tx.montecarlo) of homestead,
owner and all property tax, and owner tax by decile. Deciles: all Texas households' 2026 income cutoffs
(renters included, as for 2026), grown with wages; each record's decile from its income that year.
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ptm.results import weighted_cutoffs  # noqa: E402
from ptm.tx.montecarlo import _baseline, run_montecarlo  # noqa: E402
from ptm.tx.project import BASE_YEAR, TxProjection  # noqa: E402
from ptm.tx.survey import tx_households  # noqa: E402

END = 2036
AGE = [(0, 44, "Under 45"), (45, 64, "45–64"), (65, 74, "65–74"), (75, 200, "75 and over")]


def central_detail(scenario: str, cut: np.ndarray) -> dict:
    o, rows = _baseline()
    p = TxProjection(o, rows, scenario).run(END)
    s = p.summary
    h = p.history
    by_dec, by_age = [], []
    idx = 1.0
    for y in s.index:
        if y > BASE_YEAR:
            idx *= 1 + p.econ.rate("wage", y)
        w, t, inc = h[f"weight_{y}"], h[f"tax_{y}"], h[f"income_{y}"]
        dec = np.searchsorted(cut * idx, inc, side="right") + 1
        age = h[f"age_{y}"]
        for d in range(1, 11):
            m = (dec == d) & (w > 0)
            ws = w[m].sum()
            by_dec.append({"year": int(y), "group": d, "owners": float(ws), "avg_tax": float((t * w)[m].sum() / ws) if ws else None,
                           "avg_income": float((inc * w)[m].sum() / ws) if ws else None,
                           "tax_share_of_income": float((t * w)[m].sum() / (inc * w)[m].sum()) if ws and (inc * w)[m].sum() > 0 else None})
        for lo, hi, lab in AGE:
            m = (age >= lo) & (age <= hi) & (w > 0)
            ws = w[m].sum()
            by_age.append({"year": int(y), "group": lab, "owners": float(ws), "avg_tax": float((t * w)[m].sum() / ws) if ws else None,
                           "tax_share_of_income": float((t * w)[m].sum() / (inc * w)[m].sum()) if ws and (inc * w)[m].sum() > 0 else None})
    yrs = s.reset_index().to_dict(orient="records")
    return {"scenario": scenario, "description": p.spec["scenarios"][scenario].get("description", ""),
            "years": yrs, "by_decile": by_dec, "by_age": by_age}


def clean(o):
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    return o


def main(n_paths: int = 30) -> None:
    import yaml
    spec = yaml.safe_load((ROOT / "inputs" / "tx_projection_assumptions.yaml").read_text(encoding="utf-8"))
    allh = tx_households()
    cut = np.asarray(weighted_cutoffs(allh["hincp_aged"].fillna(0), allh["WGTP"], 10), dtype=float)
    out = {}
    for sc in spec["scenarios"]:
        t0 = time.time()
        r = central_detail(sc, cut)
        if n_paths > 0:
            mc = run_montecarlo(sc, n_paths=n_paths, end_year=END, cutoffs=cut)
            r["bands"] = mc["bands"].to_dict(orient="records")
            r["n_paths"] = n_paths
        out[sc] = r
        y = {d["year"]: d for d in r["years"]}
        print(f"{sc:9s} homestead tax 2026 ${y[2026]['tax_total'] / 1e9:5.1f}B -> 2036 ${y[2036]['tax_total'] / 1e9:5.1f}B; "
              f"all property ${y[2036]['total_levy'] / 1e9:5.1f}B ({time.time() - t0:.0f}s)")
    dest = ROOT / "data" / "processed" / "results" / "tx_projections.json"
    dest.write_text(json.dumps(clean(out)), encoding="utf-8")
    print(f"wrote {dest} ({dest.stat().st_size / 1e3:.0f} kB)")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 30)
