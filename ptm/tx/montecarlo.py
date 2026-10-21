"""Monte Carlo ranges for Texas projections: economic paths x rate-setting draws (as ptm.montecarlo for Florida).

    from ptm.tx.montecarlo import run_montecarlo
    mc = run_montecarlo("central", n_paths=30, cutoffs=cut)
    mc["bands"]        # year x group: p10, p50, p90, mean and the central path's value

Each path adds yearly noise to the scenario's home value, non-residential value and CPI growth (settings
in inputs/tx_projection_assumptions.yaml, `uncertainty`: normal shocks with first-order persistence, home
and non-residential shocks correlated) and redraws each non-school unit's rate position every year from
its class's 2025 spread (rate_setting draws). Groups: homestead tax, owner tax, all property tax, and owner
tax by income decile of all Texas households (2026 cutoffs grown with wages; each record's decile from its
income that year).
"""

import os

for _v in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"]:
    os.environ.setdefault(_v, "1")

from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from ptm.tx.project import BASE_YEAR, PATHS, PROC, SPEC

_B = None


def _baseline():
    global _B
    if _B is None:
        _B = (pd.read_parquet(PROC / "tx_baseline_2026.parquet"), pd.read_parquet(PROC / "tx_baseline_2026_units.parquet"))
    return _B


def shock_overrides(scenario: str, seed: int, end_year: int) -> dict:
    from ptm.economy import Economy
    e = Economy(scenario, assumptions_path=SPEC, paths_path=PATHS)
    u = e.spec["uncertainty"]
    rng = np.random.default_rng(seed)
    rho, corr = float(u["persistence"]), float(u["home_nonres_correlation"])
    z_h = z_n = z_c = 0.0
    out = {"home_value": {"set": {}}, "nonresidential_value": {"set": {}}, "cpi": {"set": {}}}
    for y in range(e.base_year + 1, end_year + 1):
        a, b, c = rng.standard_normal(3)
        z_h = rho * z_h + np.sqrt(1 - rho ** 2) * a
        z_n = rho * z_n + np.sqrt(1 - rho ** 2) * (corr * a + np.sqrt(1 - corr ** 2) * b)
        z_c = rho * z_c + np.sqrt(1 - rho ** 2) * c
        out["home_value"]["set"][y] = e.rate("home_value", y) + float(u["home_value_sd"]) * z_h
        out["nonresidential_value"]["set"][y] = e.rate("nonresidential_value", y) + float(u["nonresidential_sd"]) * z_n
        out["cpi"]["set"][y] = e.rate("cpi", y) + float(u["cpi_sd"]) * z_c
    return out


def path_totals(p, cutoffs: np.ndarray | None) -> dict:
    """{year: {group: value}} from a finished projection."""
    s = p.summary
    hr = p.history
    out = {}
    idx = 1.0
    for y in s.index:
        if y > BASE_YEAR:
            idx *= 1 + p.econ.rate("wage", y)
        r = {"homesteads": s.loc[y, "tax_total"], "all_owners": s.loc[y, "tax_owners"], "all_property": s.loc[y, "total_levy"]}
        if cutoffs is not None:
            w, t, inc = hr[f"weight_{y}"], hr[f"tax_{y}"], hr[f"income_{y}"]
            dec = np.searchsorted(cutoffs * idx, inc, side="right") + 1
            for d in range(1, 11):
                r[f"decile_{d}"] = float((t * w)[dec == d].sum())
        out[int(y)] = r
    return out


def _run_path(args) -> dict:
    scenario, seed, end_year, noise, cutoffs = args
    from ptm.tx.project import TxProjection
    o, rows = _baseline()
    ov = shock_overrides(scenario, seed, end_year) if noise else None
    p = TxProjection(o, rows, scenario, overrides=ov, seed=seed, end_year=end_year,
                     rate_setting={"draws": True} if noise else None).run()
    return {"seed": seed, "totals": path_totals(p, cutoffs)}


def run_montecarlo(scenario: str = "central", n_paths: int = 30, end_year: int = 2036, seed: int = 2026,
                   workers: int | None = None, cutoffs: np.ndarray | None = None) -> dict:
    workers = workers or max(1, min(4, (os.cpu_count() or 2) // 2 - 1))
    jobs = [(scenario, seed, end_year, False, cutoffs)] + [(scenario, seed + 1 + i, end_year, True, cutoffs) for i in range(n_paths)]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        res = list(ex.map(_run_path, jobs))
    central, paths = res[0]["totals"], [r["totals"] for r in res[1:]]
    rows = []
    for y in sorted(central):
        for g in central[y]:
            v = np.array([pth[y][g] for pth in paths])
            rows.append({"year": y, "group": g, "mean": v.mean(), "p10": np.percentile(v, 10), "p50": np.percentile(v, 50),
                         "p90": np.percentile(v, 90), "central": central[y][g]})
    return {"scenario": scenario, "n_paths": n_paths, "bands": pd.DataFrame(rows)}
