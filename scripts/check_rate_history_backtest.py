"""Back-test of the rate-setting rule against Florida's own history -> docs/checks/rate_history_backtest.md

The model draws each government's log rate change from the `neighbors` past government-years of the same kind
with the closest base growth (ptm.rate_setting.RateHistory). Here, for each test year t from 2006 on, the rule
is fitted only on years before t and asked to predict every government's actual rate change in t:
  - where the actual change falls inside the predicted distribution (a calibrated rule: uniform)
  - share of actual changes inside the central 50% and 80% bands (should be 50% and 80%)
  - median error and mean absolute error against two naive rules (hold the rate, rolled-back rate)
By period (the 2008-2012 recession separately), by kind, and by base growth (the cases nearest a policy shock).

Usage:  python scripts/check_rate_history_backtest.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
K = 60
FIRST = 2006


def predict_window(xs_sorted, ys_by_x, x, k=K):
    lo = np.clip(np.searchsorted(xs_sorted, x) - k // 2, 0, len(xs_sorted) - k)
    return np.sort(ys_by_x[lo[:, None] + np.arange(k)[None, :]], axis=1)


def main() -> None:
    d = pd.read_parquet(ROOT / "data" / "processed" / "millage_changes.parquet").dropna(subset=["x", "dlm"])
    d["dlm"] = d["dlm"].round(8)          # about half of county and city rates don't change: exact zeros must tie
    rows = []
    for t in range(FIRST, int(d["year"].max()) + 1):
        for kind, g in d.groupby("kind"):
            tr, te = g[g["year"] < t].sort_values("x"), g[g["year"] == t]
            if len(te) == 0 or len(tr) < K:
                continue
            w = predict_window(tr["x"].to_numpy(), tr["dlm"].to_numpy(), te["x"].to_numpy())
            a = te["dlm"].to_numpy()
            rows.append(pd.DataFrame({
                "year": t, "kind": kind, "x": te["x"].to_numpy(), "actual": a,
                "pit": ((w < a[:, None]).sum(axis=1) + 0.5 * (w == a[:, None]).sum(axis=1)) / K,
                "pred_med": np.median(w, axis=1), "pred_mean": w.mean(axis=1),
                "err_model": a - np.median(w, axis=1), "err_hold": a, "err_rb": a + te["x"].to_numpy(),   # rolled back: dlm = -x
            }))
    r = pd.concat(rows, ignore_index=True)
    r["in50"] = (r["pit"] >= 0.25) & (r["pit"] <= 0.75)
    r["in80"] = (r["pit"] >= 0.10) & (r["pit"] <= 0.90)
    r["period"] = pd.cut(r["year"], [2005, 2007, 2012, 2019, 2025], labels=["2006-07", "2008-12", "2013-19", "2020-25"])
    r["all"] = "all"
    r["growth"] = pd.cut(r["x"], [-9, -0.02, 0.02, 0.06, 0.12, 9], labels=["falling >2%", "-2% to 2%", "2% to 6%", "6% to 12%", "over 12%"])

    for c in ("err_model", "err_hold", "err_rb"):
        r["abs_" + c] = r[c].abs()

    def md(t):
        t = t.reset_index()
        t.columns = [str(c) for c in t.columns]
        lines = ["| " + " | ".join(t.columns) + " |", "|" + "---|" * len(t.columns)]
        lines += ["| " + " | ".join(f"{v:.3g}" if isinstance(v, float) else str(v) for v in row) + " |" for row in t.itertuples(index=False)]
        return chr(10).join(lines)

    def tab(by):
        g = r.groupby(by, observed=True)
        return pd.DataFrame({"n": g.size(), "inside 50% band": g["in50"].mean(), "inside 80% band": g["in80"].mean(),
                             "median error (pts)": g["err_model"].median() * 100,
                             "MAE model": g["abs_err_model"].mean() * 100, "MAE hold": g["abs_err_hold"].mean() * 100,
                             "MAE rolled-back": g["abs_err_rb"].mean() * 100}).round(3)

    out = ["# Check: the rate-setting rule against Florida's history (2026-10-23)", "",
           f"`scripts/check_rate_history_backtest.py`. For each year from {FIRST}, the rule is fitted on earlier years only and predicts",
           "every county, city and school-RLE rate change that year. A well-calibrated rule puts 50% of actual changes inside its",
           "central 50% band and 80% inside the 80% band. MAE = mean absolute error of the predicted median (log points x 100,",
           "about percent); 'hold' and 'rolled-back' are the fixed rules.", ""]
    for name, by in [("All", "all"), ("By kind", "kind"), ("By period", "period"), ("By base growth that year", "growth")]:
        out += [f"## {name}", "", md(tab(by)), ""]
    # the cases most like a policy shock: base growth well below the rolled-back-rate region, by kind
    out += ["## Falling or flat base, by period", "", md(tab(["period", "growth"]).loc[lambda x: x.index.get_level_values(1).isin(["falling >2%", "-2% to 2%"])]), ""]
    Path(ROOT / "docs" / "checks" / "rate_history_backtest.md").write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
