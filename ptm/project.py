"""Project the 2026 baseline forward year by year under current law.

    from ptm.project import Projection
    p = Projection(baseline, scenario="central")      # or "stall", "downturn", ... ; overrides=...
    p.run(2036)
    p.summary            # one row per year: tax by levy, sales, Save Our Homes savings, ...
    p.household_results  # per owner: tax_<year>, tax_<class>_<year>, av_school_<year>

Each year (owners only; renters come with pass-through):
  1. economy: just and market values and income components grow (ptm.economy)
  2. law: future-year values from the spec's `projection` rules - Save Our Homes cap = lesser of
     3% and the prior year's CPI change; the second homestead exemption and income limits indexed
     to CPI (project_law)
  3. sales: each home changes hands with a probability that falls with its Save Our Homes savings
     (lock-in), set so the 2026 average matches the 2025 sale rates in the rolls; a homestead sale
     resets the assessment to just value unless the owner ports their savings (turnover settings in
     inputs/fl_projection_assumptions.yaml). The household stays in the data (its home resets).
  4. engine: assessment caps, exemptions and taxable value (ptm.engine.step)
  5. rates: each county, city and school district sets its millage from Florida's rolled-back rate
     rules, given how its whole taxable base grew (ptm.rate_setting); then tax

Not yet (next pieces): deaths of older owners, reweighting to household projections by age, new
construction, homestead status changes, re-testing income-limited exemptions.
"""

import copy

import numpy as np
import pandas as pd

from ptm.economy import Economy
from ptm.engine.step import step
from ptm.law import Law, load_law
from ptm.rate_setting import RateSetter, _city_key, school_rle_2026
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


_CACHE: dict = {}


def _cached(key, make):
    if key not in _CACHE:
        _CACHE[key] = make()
    return _CACHE[key]


def _school_tables() -> pd.DataFrame:
    from ptm.millage import county_fips_by_name
    from ptm.ratemodel import norm, school_rates_2026
    sr = school_rates_2026()
    fips = {norm(k): v for k, v in county_fips_by_name().items()}
    sr["county_fips"] = sr["key"].map({**fips, "dade": fips.get("miamidade")})
    return sr.dropna(subset=["county_fips"]).set_index("county_fips")


DYNAMIC = ["jv", "valp_market_cal", "av_school_prior", "av_nonschool_prior", "taxable_school_prior",
           "taxable_county_prior"]


class Projection:
    """Owners projected year by year. Static inputs (exemption flags, jurisdiction positions, 2026
    rates) are prepared once per baseline and reused by later Projections in the same process;
    each year only updates numeric arrays (values, assessed values, rates, tax)."""

    def __init__(self, baseline: pd.DataFrame, scenario: str = "central", overrides: dict | None = None,
                 seed: int = 2026, law: Law | None = None, rate_setting: dict | None = None,
                 end_year: int = 2036):
        self.econ = Economy(scenario, overrides)
        self.turnover = self.econ.spec["turnover"]
        self.rate_settings = {**self.econ.spec["rate_setting"], **(rate_setting or {})}
        self.law_base = law or _cached("law", load_law)
        self.end_year = end_year
        self.law = project_law(self.law_base, self.econ, end_year)
        sr = _cached("school", _school_tables)
        self.rates = RateSetter(self.rate_settings, BASE_YEAR, sr["rle_millage_2026"], sr["school_2026"])
        self.rng = np.random.default_rng(seed)

        prep = _cached(("prep", id(baseline), len(baseline)), lambda: self._prepare(baseline))
        self.units = prep["static"]                      # shared, read-only
        self.a = {k: v.copy() for k, v in prep["dynamic"].items()}
        self.income = {k: v.copy() for k, v in prep["income"].items()}
        self.hs = prep["hs"]
        self.w = prep["w"]
        self.ci = prep["ci"]
        self.ci_ok = prep["ci_ok"]
        self.yi = prep["yi"]
        self.min_count_ok = prep["min_count_ok"]
        self.mill = {c: prep[f"mill_{c}"].copy() for c in LEVIES}
        self.taxable = {}   # year -> {class: array} for draw totals
        self.history = {f"tax_{BASE_YEAR}": prep["tax_2026"], f"av_school_{BASE_YEAR}": self.a["av_school_prior"].copy()}
        for c in LEVIES:
            self.history[f"tax_{c}_{BASE_YEAR}"] = prep[f"tax_{c}_2026"]
        self.year = BASE_YEAR
        self._base_rates = self._calibrate_sale_rates()
        self.rows = [self._row(BASE_YEAR, np.zeros(len(self.w), bool), prep["tax_2026"],
                               self.a["av_school_prior"], {c: prep[f"tax_{c}_2026"] for c in LEVIES})]

    def _prepare(self, baseline: pd.DataFrame) -> dict:
        u = baseline.loc[owner_mask(baseline), self._needed_columns(baseline)].copy()
        u["homestead"] = (u["homestead"] == True)  # noqa: E712
        rle = u["county_fips_tax"].map(school_rle_2026()).fillna(0)
        u["rle_2026"] = rle
        u["millage_school_fixed"] = u["millage_school"] - rle
        for c in ["county", "municipal"]:
            u[f"millage_{c}_base"] = u[f"millage_{c}"]
        keys = u["municipality"].fillna("")
        key_map = {k: _city_key(k) for k in keys.unique()}
        u["city_key"] = keys.map(key_map)
        pairs = pd.Series(list(zip(u["county_fips_tax"], u["city_key"])), index=u.index)
        upos = {p: self.rates.city_pos.get(p, -1) for p in pairs.unique()}
        u["city_idx"] = pairs.map(upos).astype(int)
        cpos = {k: i for i, k in enumerate(self.rates.counties.index)}
        u["county_idx"] = u["county_fips_tax"].map(cpos).fillna(-1).astype(int)
        hs = u["homestead"].to_numpy()
        ci = u["county_idx"].to_numpy()
        counts = np.bincount(ci[hs & (ci >= 0)], minlength=len(cpos))
        f = lambda c: u[c].astype(float).to_numpy()  # noqa: E731
        # static frame for the engine: exemption flags and values, shares; plus reporting columns
        static_cols = [c for c in u.columns if c not in set(DYNAMIC)]
        return {
            "static": u[static_cols],
            "dynamic": {"jv": f("valp_jv_cal"), "valp_market_cal": f("valp_market_cal"),
                        "av_school_prior": f(f"av_sd_{BASE_YEAR}"), "av_nonschool_prior": f(f"av_nsd_{BASE_YEAR}"),
                        "taxable_school_prior": f(f"taxable_school_{BASE_YEAR}"),
                        "taxable_county_prior": f(f"taxable_county_{BASE_YEAR}")},
            "income": {c: f(c) for c in self.econ.spec["income_growth"] if c in u},
            "hs": hs, "w": f("WGTP"), "ci": ci, "ci_ok": ci >= 0, "yi": u["city_idx"].to_numpy(),
            "min_count_ok": counts >= 30,
            **{f"mill_{c}": np.nan_to_num(f(f"millage_{c}")) for c in LEVIES},
            "tax_2026": np.nan_to_num(f(f"tax_model_{BASE_YEAR}")),
            **{f"tax_{c}_2026": np.nan_to_num(f(f"tax_{c}_{BASE_YEAR}")) for c in LEVIES},
        }

    # --- sales -----------------------------------------------------------------------------------
    def _savings(self) -> np.ndarray:
        """Assessment savings carried into the year: just value minus last year's assessed value
        (school for homesteads, non-school for others)."""
        prior = np.where(self.hs, self.a["av_school_prior"], self.a["av_nonschool_prior"])
        return np.maximum(self.a["jv"] - prior, 0)

    def _calibrate_sale_rates(self) -> dict:
        li = self.turnover["lock_in"]
        f = lock_in_factor(self._savings(), li["per_100k_savings"], li["floor"])
        hs, w = self.hs, self.w
        return {True: self.turnover["homestead_sale_rate"] / np.average(f[hs], weights=w[hs]),
                False: self.turnover["nonhomestead_sale_rate"] / np.average(f[~hs], weights=w[~hs])}

    def _draw_sales(self) -> tuple[np.ndarray, np.ndarray]:
        li, port = self.turnover["lock_in"], self.turnover["portability"]
        savings = self._savings()
        n = len(self.w)
        base = np.where(self.hs, self._base_rates[True], self._base_rates[False])
        p = np.clip(base * lock_in_factor(savings, li["per_100k_savings"], li["floor"]), 0, 1)
        sold = self.rng.random(n) < p
        ports = sold & self.hs & (self.rng.random(n) < port["share_of_homestead_sales"])
        return sold, np.where(ports, np.minimum(savings, port["max_transfer"]), 0.0)

    # --- one year --------------------------------------------------------------------------------
    def step_year(self) -> None:
        y = self.year + 1
        if y > self.end_year:
            self.end_year = y
            self.law = project_law(self.law_base, self.econ, y)
        a, e = self.a, self.econ
        hv = 1 + e.rate("home_value", y)
        a["jv"] *= hv
        a["valp_market_cal"] *= hv
        for col, var in e.spec["income_growth"].items():
            if col in self.income:
                self.income[col] *= 1 + e.rate(var, y)
        sold, transfer = self._draw_sales()
        df = self.units.assign(jv=a["jv"], av_school_prior=a["av_school_prior"],
                               av_nonschool_prior=a["av_nonschool_prior"], homestead_prior=self.hs,
                               changed_ownership=sold, improvements=0.0, portability_transfer=transfer)
        res = step(df, self.law, y)
        taxable = {c: res[f"taxable_{c}"].fillna(0).to_numpy() for c in LEVIES}
        self._set_rates(taxable, y)
        tax = {c: taxable[c] * self.mill[c] / 1000 for c in LEVIES}
        total = sum(tax.values())
        av_school = res["av_school"].to_numpy()
        self.taxable[y] = taxable
        self.history[f"tax_{y}"] = total
        self.history[f"av_school_{y}"] = av_school
        for c in LEVIES:
            self.history[f"tax_{c}_{y}"] = tax[c]
        self.rows.append(self._row(y, sold, total, av_school, tax))
        a["av_school_prior"] = av_school
        a["av_nonschool_prior"] = res["av_county"].to_numpy()
        a["taxable_school_prior"] = taxable["school"]
        a["taxable_county_prior"] = taxable["county"]
        self.year = y

    def _set_rates(self, taxable: dict, y: int) -> None:
        """Rates for year y from each jurisdiction's taxable growth (homestead part from the model)."""
        hs, w, ci = self.hs, self.w, self.ci
        sel = hs & self.ci_ok
        nc = len(self.rates.counties)
        growth = {}
        for c in ["school", "county"]:
            now = np.bincount(ci[sel], weights=(taxable[c] * w)[sel], minlength=nc)
            before = np.bincount(ci[sel], weights=(self.a[f"taxable_{c}_prior"] * w)[sel], minlength=nc)
            with np.errstate(divide="ignore", invalid="ignore"):
                g = np.where((before > 0) & self.min_count_ok, now / before, np.nan)
            growth[c] = g                                  # thin counties use the median
        self.rates.step_arrays(growth["school"], growth["county"],
                               self.econ.rate("home_value", y), self.econ.rate("nonresidential_value", y), y)
        rc = self.rates.county_draws.mean(axis=0)
        rcity = self.rates.city_draws.mean(axis=0)
        rle = self.rates.rle_draws.mean(axis=0)
        u = self.units
        cty = np.where(self.ci_ok, rc[np.maximum(ci, 0)], 1.0)
        self.mill["county"] = np.nan_to_num(u["millage_county_base"].to_numpy(dtype=float)) * cty
        yi = self.yi
        city = np.where(yi >= 0, rcity[np.maximum(yi, 0)], 1.0)
        self.mill["municipal"] = np.nan_to_num(u["millage_municipal_base"].to_numpy(dtype=float)) * city
        rle_now = np.where(self.ci_ok, rle[np.maximum(ci, 0)], u["rle_2026"].to_numpy(dtype=float))
        self.mill["school"] = np.nan_to_num(u["millage_school_fixed"].to_numpy(dtype=float)) + rle_now

    def run(self, end_year: int = 2036) -> "Projection":
        while self.year < end_year:
            self.step_year()
        return self

    # --- reporting -------------------------------------------------------------------------------
    def _row(self, y, sold, tax, av, classes) -> dict:
        w, hs, jv = self.w, self.hs, self.a["jv"]
        wsum, whs = w.sum(), w[hs].sum()
        row = {"year": y, "owners": wsum, "tax_total": (tax * w).sum(), "avg_tax": (tax * w).sum() / wsum,
               "just_value": (jv * w).sum(),
               "homestead_assessed_to_just": (av * w)[hs].sum() / (jv * w)[hs].sum(),
               "homestead_soh_savings_avg": (np.maximum(jv - av, 0) * w)[hs].sum() / whs,
               "share_sold": (sold * w).sum() / wsum, "homestead_share_sold": (sold * w)[hs].sum() / whs}
        for c, t in classes.items():
            row[f"tax_{c}"] = (np.nan_to_num(t) * w).sum()
        for c in ["school", "county", "municipal"]:
            m = self.mill[c]
            has = m > 0
            row[f"millage_{c}_avg"] = np.average(m[has], weights=w[has]) if has.any() else np.nan
        if y > BASE_YEAR:
            row["soh_cap"] = float(self.law.rule("soh_cap").get("cap", y))
            row["homestead_second_amount"] = float(self.law.rule("homestead_second").get("amount", y))
        return row

    def _needed_columns(self, b: pd.DataFrame) -> list[str]:
        return Projection._needed_columns_for(b, self.econ, self.law_base)

    @staticmethod
    def _needed_columns_for(b: pd.DataFrame, econ: Economy | None = None, law: Law | None = None) -> list[str]:
        """Only what the loop uses: identifiers, values, incomes, exemption inputs, rates."""
        econ, law = econ or Economy("central"), law or load_law()
        cols = {"WGTP", "SERIALNO", "PUMA", "tenure", "mh_rented_lot", "county_fips", "county_fips_tax", "municipality", "homestead",
                "valp_jv_cal", "valp_market_cal", "hincp_aged", "HHLDRAGEP", "MV", "home_type",
                f"av_sd_{BASE_YEAR}", f"av_nsd_{BASE_YEAR}", f"tax_model_{BASE_YEAR}",
                "homestead_portion_share", "homestead_share"}
        cols |= set(econ.spec["income_growth"])
        cols |= {f"{x}_{c}" for x in ["millage", "taxable"] for c in LEVIES}
        cols |= {f"taxable_{c}_{BASE_YEAR}" for c in LEVIES} | {f"tax_{c}_{BASE_YEAR}" for c in LEVIES}
        for r in law.exemptions():
            for k in ["household_flag", "value_column"]:
                if r.spec.get(k):
                    cols.add(r.spec[k])
        cols |= {c for c in b.columns if c.startswith("ex_")}   # replicate weights stay in the baseline (join by index)
        return [c for c in b.columns if c in cols]

    def draw_totals(self, groups: pd.Series) -> dict:
        """Tax totals for every rate draw: {year: array (n_groups + 1, n_draws)}, rows = the sorted
        group labels, then the all-owner total. Exact: tax is taxable x rate, and taxable values
        don't depend on rates, so each draw's tax is a weighted sum computed by matrix products."""
        u = self.units
        labels = sorted(groups.reindex(u.index).dropna().unique())
        gpos = groups.reindex(u.index).map({g: i for i, g in enumerate(labels)}).to_numpy()
        ng = len(labels) + 1
        w = u["WGTP"].to_numpy()
        ci = u["county_idx"].to_numpy()
        yi = u["city_idx"].to_numpy()
        nc, ny = len(self.rates.counties), len(self.rates.cities)

        def by_group_and(j, v, n):  # (ng, n) sums of v by group and jurisdiction position j
            m = np.zeros((ng, n))
            ok = j >= 0
            gp = np.where(np.isnan(gpos.astype(float)), -1, gpos).astype(int)
            for rows in (gp, np.full(len(gp), ng - 1)):
                sel = ok & (rows >= 0)
                np.add.at(m, (rows[sel], j[sel]), v[sel])
            return m

        def by_group(v):
            out = np.zeros(ng)
            gp = np.where(np.isnan(gpos.astype(float)), -1, gpos).astype(int)
            sel = gp >= 0
            np.add.at(out, gp[sel], v[sel])
            out[-1] = v.sum()
            return out

        out = {}
        for y, tx in self.taxable.items():
            pth = self.rates.paths[y]
            t_cty = w * tx["county"] * u["millage_county_base"].fillna(0).to_numpy()
            t_mun = w * tx["municipal"] * u["millage_municipal_base"].fillna(0).to_numpy()
            t_sch = w * tx["school"]
            fixed = by_group(t_sch * u["millage_school_fixed"].fillna(0).to_numpy()) \
                + by_group(np.where(yi < 0, t_mun, 0)) + by_group(np.where(ci < 0, t_cty, 0))
            total = (fixed[:, None]
                     + by_group_and(ci, t_cty, nc) @ pth["county"].T
                     + by_group_and(yi, t_mun, ny) @ pth["city"].T
                     + by_group_and(ci, t_sch, nc) @ pth["rle"].T)
            out[y] = total / 1000
        out["labels"] = labels
        return out

    @property
    def household_results(self) -> pd.DataFrame:
        """Per-owner yearly tax and school assessed value (columns tax_<year>, tax_<class>_<year>, ...)."""
        return pd.DataFrame(self.history, index=self.units.index)

    @property
    def summary(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows).set_index("year")
