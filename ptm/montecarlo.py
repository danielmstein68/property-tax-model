"""Monte Carlo ranges for projections: economic paths x rate-behaviour draws.

    from ptm.montecarlo import run_montecarlo
    mc = run_montecarlo("central", n_paths=50)          # ~30-40 s on 12 cores
    mc["bands"]        # year x group: p10, p50, p90 and mean of owner tax
    mc["central"]      # the scenario's own path (no economic noise; rate draws averaged)

Each economic path adds yearly noise to the scenario's home value, non-residential value and CPI
growth (settings in inputs/fl_projection_assumptions.yaml, `uncertainty`): normal shocks with
first-order persistence, home and non-residential shocks correlated. Each path runs the
households once (ptm.project.Projection, in parallel); its rate draws (rate_setting.draws) are
then totalled exactly by Projection.draw_totals. The bands therefore combine economic and
rate-setting uncertainty. Survey sampling error is separate (replicate weights, ptm.results).

Groups: income deciles of all households in 2026 (ptm.results), held fixed over the projection.
"""

import os

# one maths thread per worker process (they run in parallel; extra threads only compete)
for _v in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"]:
    os.environ.setdefault(_v, "1")

from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "data" / "processed" / "baseline_fl_2026.parquet"
_B = None  # baseline, loaded once per worker


SLIM = ROOT / "data" / "processed" / "projection_input_2026.parquet"


def slim_baseline(refresh: bool = False) -> Path:
    """Only the columns the projection uses, plus income deciles: workers load this (the full
    baseline is ~500 columns; several workers loading it exhaust memory on a laptop)."""
    if refresh or not SLIM.exists() or SLIM.stat().st_mtime < BASELINE.stat().st_mtime:
        from ptm.project import Projection
        from ptm.results import add_income_deciles, owner_mask
        b = add_income_deciles(pd.read_parquet(BASELINE))
        cols = Projection._needed_columns_for(b) + ["income_decile", "tenure", "mh_rented_lot"]
        slim = b[[c for c in b.columns if c in set(cols)]].copy()
        slim.attrs = {}
        slim.to_parquet(SLIM)
    return SLIM


PREP = ROOT / "data" / "processed" / "projection_prep_2026.pkl"


def _baseline() -> pd.DataFrame:
    global _B
    if _B is None:
        _B = pd.read_parquet(SLIM)
        _B.attrs = {"prep_cache": str(PREP), "prep_source": str(SLIM)}
    return _B


def shock_overrides(scenario: str, seed: int, end_year: int) -> dict:
    """Economy overrides for one noisy path around `scenario`."""
    from ptm.economy import Economy
    e = Economy(scenario)
    u = e.spec["uncertainty"]
    rng = np.random.default_rng(seed)
    years = list(range(e.base_year + 1, end_year + 1))
    rho, corr = float(u["persistence"]), float(u["home_nonres_correlation"])
    z_h = z_n = z_c = 0.0
    out = {"home_value": {"set": {}}, "nonresidential_value": {"set": {}}, "cpi": {"set": {}}}
    for y in years:
        a, b, c = rng.standard_normal(3)
        z_h = rho * z_h + np.sqrt(1 - rho ** 2) * a
        z_n = rho * z_n + np.sqrt(1 - rho ** 2) * (corr * a + np.sqrt(1 - corr ** 2) * b)
        z_c = rho * z_c + np.sqrt(1 - rho ** 2) * c
        out["home_value"]["set"][y] = e.rate("home_value", y) + float(u["home_value_sd"]) * z_h
        out["nonresidential_value"]["set"][y] = e.rate("nonresidential_value", y) + float(u["nonresidential_sd"]) * z_n
    for y in [e.base_year] + years[:-1]:   # CPI of year t-1 sets year t's cap and indexing
        z_c = rho * z_c + np.sqrt(1 - rho ** 2) * rng.standard_normal()
        out["cpi"]["set"][y] = e.rate("cpi", y) + float(u["cpi_sd"]) * z_c
    return out


def _run_path(args) -> dict:
    import time
    t0 = time.time()
    scenario, path_seed, end_year, rate_setting, noise = args
    from ptm.project import Projection
    b = _baseline()
    t1 = time.time()
    ov = shock_overrides(scenario, path_seed, end_year) if noise else None
    rs = {**(rate_setting or {}), "seed": path_seed}
    p = Projection(b, scenario, overrides=ov, rate_setting=rs, seed=path_seed).run(end_year)
    d = p.draw_totals("income_decile")
    return {"seed": path_seed, "draws": {y: v for y, v in d.items() if y != "labels"},
            "labels": d["labels"], "summary": p.summary, "seconds": (t1 - t0, time.time() - t1)}


def run_montecarlo(scenario: str = "central", n_paths: int = 50, end_year: int = 2036, seed: int = 2026,
                   workers: int | None = None, rate_setting: dict | None = None) -> dict:
    workers = workers or max(1, min(5, (os.cpu_count() or 2) // 2 - 1))   # physical cores - 1, memory-bound
    slim_baseline()
    if not PREP.exists() or PREP.stat().st_mtime < SLIM.stat().st_mtime:
        _run_path((scenario, seed, 2027, rate_setting, False))   # builds the prepared inputs once
    jobs = [(scenario, seed, end_year, rate_setting, False)]
    jobs += [(scenario, seed + 1 + i, end_year, rate_setting, True) for i in range(n_paths)]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        res = list(ex.map(_run_path, jobs))
    central, paths = res[0], res[1:]
    secs = np.array([r["seconds"] for r in res])
    labels = [f"decile_{int(g)}" for g in central["labels"]] + ["all_owners"]
    years = sorted(central["draws"])
    rows = []
    for y in years:
        allv = np.concatenate([r["draws"][y] for r in paths], axis=1)   # (groups, paths x draws)
        for gi, g in enumerate(labels):
            v = allv[gi]
            rows.append({"year": y, "group": g, "mean": v.mean(), "p10": np.percentile(v, 10),
                         "p50": np.percentile(v, 50), "p90": np.percentile(v, 90),
                         "central": central["draws"][y][gi].mean()})
    bands = pd.DataFrame(rows)
    base = central["summary"].loc[2026]
    b26 = pd.DataFrame([{"year": 2026, "group": "all_owners", "mean": base.tax_total, "p10": base.tax_total,
                         "p50": base.tax_total, "p90": base.tax_total, "central": base.tax_total}])
    bands = pd.concat([b26, bands], ignore_index=True)
    return {"scenario": scenario, "n_paths": n_paths, "draws_per_path": paths[0]["draws"][years[0]].shape[1],
            "bands": bands, "central": central["summary"],
            "timing": {"load_mean": secs[:, 0].mean(), "run_mean": secs[:, 1].mean(), "workers": workers}}
