"""Project the 2026 baseline forward year by year under current law.

    from ptm.project import Projection
    p = Projection(baseline, scenario="central")      # or "stall", "downturn", ... ; overrides=...
    p.run(2036)
    p.summary            # one row per year: tax by levy, sales, Save Our Homes savings, ...
    p.units              # owner households with tax_<year> and av_school_<year> columns

Each year (owners only; renters come with pass-through):
  1. economy: just and market values and income components grow (ptm.economy)
  2. law: future-year values from the spec's `projection` rules - Save Our Homes cap = lesser of
     3% and the prior year's CPI change; the second homestead exemption and income limits indexed
     to CPI (project_law)
  3. sales: each home changes hands with a probability that falls with its Save Our Homes savings
     (lock-in), set so the 2026 average matches the 2025 sale rates in the rolls; a homestead sale
     resets the assessment to just value unless the owner ports their savings (turnover settings in
     inputs/fl_projection_assumptions.yaml). The household stays in the data (its home resets).
  4. engine: assessment caps, exemptions, taxable value and tax (ptm.engine.step)

Not yet (next pieces): deaths of older owners, reweighting to household projections by age, new
construction, homestead status changes, re-testing income-limited exemptions, and rate-setting -
millage is held at 2026 rates for now.
"""

import copy

import numpy as np
import pandas as pd

from ptm.economy import Economy
from ptm.engine.step import carry_forward, step
from ptm.law import Law, load_law
from ptm.results import owner_mask

BASE_YEAR = 2026
LEVIES = ["school", "county", "municipal", "special"]


def project_law(law: Law, econ: Economy, last_year: int) -> Law:
    """A copy of the law with year-keyed values filled in to `last_year` from each rule's
    `projection` entries (CPI from the economy)."""
    law = copy.deepcopy(law)
    for r in law.rules.values():
        for p in r.spec.get("projection") or []:
            key, method = p["key"], p["method"]
            vals = r.spec[key] if isinstance(r.spec[key], dict) else {BASE_YEAR: r.spec[key]}
            vals = {int(y): v for y, v in vals.items()}
            for y in range(max(vals) + 1, last_year + 1):
                cpi = econ.rate("cpi", y - p.get("cpi_lag", 1))
                if method == "lesser_of_max_and_cpi":
                    v = min(float(r.spec["max_rate"]), cpi)
                elif method == "index_cpi":
                    g = max(cpi, 0.0) if p.get("floor_zero") else cpi
                    v = vals[y - 1] * (1 + g)
                    if p.get("round"):
                        v = round(v / p["round"]) * p["round"]
                else:
                    raise ValueError(f"{r.id}: unknown projection method '{method}'")
                vals[y] = v
            r.spec[key] = vals
    return law


def lock_in_factor(savings: np.ndarray, per_100k: float, floor: float) -> np.ndarray:
    return np.maximum(1 + per_100k * np.maximum(savings, 0) / 100_000, floor)


class Projection:
    def __init__(self, baseline: pd.DataFrame, scenario: str = "central", overrides: dict | None = None,
                 seed: int = 2026, law: Law | None = None):
        self.econ = Economy(scenario, overrides)
        self.turnover = self.econ.spec["turnover"]
        self.law_base = law or load_law()
        self.rng = np.random.default_rng(seed)
        h = baseline[owner_mask(baseline)].copy()
        u = h.copy()
        u["homestead"] = (u["homestead"] == True)  # noqa: E712
        u["homestead_prior"] = u["homestead"]
        u["jv"] = u["valp_jv_cal"]
        u["av_school_prior"] = u[f"av_sd_{BASE_YEAR}"]
        u["av_nonschool_prior"] = u[f"av_nsd_{BASE_YEAR}"]
        u["changed_ownership"] = False
        u["improvements"] = 0.0
        u[f"tax_{BASE_YEAR}"] = u[f"tax_model_{BASE_YEAR}"]
        u[f"av_school_{BASE_YEAR}"] = u["av_school_prior"]
        self.units = u
        self.year = BASE_YEAR
        self._base_rates = self._calibrate_sale_rates(u)
        self.rows = [self._row(u, BASE_YEAR, sold=pd.Series(False, index=u.index),
                               tax=u[f"tax_{BASE_YEAR}"], av=u["av_school_prior"],
                               classes={c: u[f"tax_{c}_{BASE_YEAR}"] for c in LEVIES})]

    # --- sales -----------------------------------------------------------------------------------
    def _savings(self, u: pd.DataFrame) -> np.ndarray:
        """Assessment savings carried into the year: just value minus last year's assessed value
        (school for homesteads, non-school for others)."""
        prior = np.where(u["homestead"], u["av_school_prior"], u["av_nonschool_prior"])
        return np.maximum(u["jv"].to_numpy() - prior, 0)

    def _calibrate_sale_rates(self, u: pd.DataFrame) -> dict:
        li = self.turnover["lock_in"]
        f = lock_in_factor(self._savings(u), li["per_100k_savings"], li["floor"])
        w = u["WGTP"].to_numpy()
        hs = u["homestead"].to_numpy()
        return {
            True: self.turnover["homestead_sale_rate"] / np.average(f[hs], weights=w[hs]),
            False: self.turnover["nonhomestead_sale_rate"] / np.average(f[~hs], weights=w[~hs]),
        }

    def _draw_sales(self, u: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        li, port = self.turnover["lock_in"], self.turnover["portability"]
        savings = self._savings(u)
        hs = u["homestead"].to_numpy()
        base = np.where(hs, self._base_rates[True], self._base_rates[False])
        p = np.clip(base * lock_in_factor(savings, li["per_100k_savings"], li["floor"]), 0, 1)
        sold = self.rng.random(len(u)) < p
        ports = sold & hs & (self.rng.random(len(u)) < port["share_of_homestead_sales"])
        transfer = np.where(ports, np.minimum(savings, port["max_transfer"]), 0.0)
        return pd.Series(sold, index=u.index), pd.Series(transfer, index=u.index)

    # --- one year --------------------------------------------------------------------------------
    def step_year(self) -> None:
        y = self.year + 1
        law = project_law(self.law_base, self.econ, y)
        u = self.econ.grow(self.units, self.year, y)
        u["jv"] = u["valp_jv_cal"]
        sold, transfer = self._draw_sales(u)
        u["changed_ownership"] = sold
        u["portability_transfer"] = transfer
        res = step(u, law, y)
        u[f"tax_{y}"] = res["tax_total"]
        u[f"av_school_{y}"] = res["av_school"]
        for c in LEVIES:
            u[f"tax_{c}_{y}"] = res[f"tax_{c}"]
        self.rows.append(self._row(u, y, sold, res["tax_total"], res["av_school"],
                                   {c: res[f"tax_{c}"] for c in LEVIES}, law))
        self.units = carry_forward(u, res).drop(columns=["portability_transfer"])
        self.year = y

    def run(self, end_year: int = 2036) -> "Projection":
        while self.year < end_year:
            self.step_year()
        return self

    # --- reporting -------------------------------------------------------------------------------
    def _row(self, u, y, sold, tax, av, classes, law: Law | None = None) -> dict:
        w = u["WGTP"]
        hs = u["homestead"]
        jv = u["jv"]
        row = {"year": y, "owners": w.sum(), "tax_total": (tax * w).sum(),
               "avg_tax": (tax * w).sum() / w.sum(),
               "just_value": (jv * w).sum(),
               "homestead_assessed_to_just": (av[hs] * w[hs]).sum() / (jv[hs] * w[hs]).sum(),
               "homestead_soh_savings_avg": ((jv - av).clip(lower=0)[hs] * w[hs]).sum() / w[hs].sum(),
               "share_sold": (sold * w).sum() / w.sum(),
               "homestead_share_sold": (sold[hs] * w[hs]).sum() / w[hs].sum()}
        for c, t in classes.items():
            row[f"tax_{c}"] = (t.fillna(0) * w).sum()
        if law is not None:
            row["soh_cap"] = float(law.rule("soh_cap").get("cap", y))
            row["homestead_second_amount"] = float(law.rule("homestead_second").get("amount", y))
        return row

    @property
    def summary(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows).set_index("year")
