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
  3. sales and deaths: each home changes hands with a probability that falls with its Save Our
     Homes savings (lock-in); and when the owner dies with no spouse in the household, the home
     passes on (Florida life table by householder age). Either resets the assessment to just value
     (a homestead seller may port savings). Sale rates are set so total resets match the calibrated
     rates (turnover settings, inputs/fl_projection_assumptions.yaml). Records stand for household
     types and keep their age; the home resets, the type stays.
  3b. ages: owner weights shift each year with Florida's projected population by age (Demographic
     Estimating Conference), total owners held fixed (growth in households = new homes, next piece).
  4. engine: assessment caps, exemptions and taxable value (ptm.engine.step)
  5. rates: each county, city and school district sets its millage from Florida's rolled-back rate
     rules, given how its whole taxable base grew (ptm.rate_setting); then tax

  3c. new owners: owner households grow with Florida's household forecast (constant ownership
     rate); each year's new owners live in new homes at full value (no Save Our Homes savings),
     with characteristics of recent buyers (moved in within ~2 years) placed by county in
     proportion to new construction (DOR Data Book). They are pre-built "cohort" records with zero
     weight until their year. New construction stays out of rolled-back rates in its first year
     and then joins each jurisdiction's base (REC new-construction rates by property type).

  4b. eligibility: income-, age- and residence-tested exemptions (senior low-income and long-term,
     county and city; total disability) are re-tested every year against the law's limits for that
     year (indexed, or changed by a policy) and households' grown incomes. Claimants keep the
     exemption while eligible; newly eligible households claim at 2026 take-up rates, where their
     county or city offers it.

Not yet: homestead status changes.
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
                    v = min(float(r.get("max_rate", y)), cpi)
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


AGE_BANDS = [(18, 24, "18_24"), (25, 44, "25_44"), (45, 64, "45_64"), (65, 69, "65_69"), (70, 74, "70_74"),
             (75, 79, "75_79"), (80, 84, "80_84"), (85, 200, "85_plus")]


def _demography() -> tuple[pd.DataFrame, pd.Series]:
    from ptm.economy import ROOT as EROOT
    pop = pd.read_csv(EROOT / "inputs" / "fl_population_by_age.csv")
    life = pd.read_csv(EROOT / "inputs" / "fl_life_table_2021.csv").set_index("age")["qx"]
    return pop, life


def age_band_factors(pop: pd.DataFrame, years: range) -> pd.DataFrame:
    """Population by age band relative to the base year, interpolated geometrically between the
    projection years (2020, 2030, 2040)."""
    out = {}
    for band, g in pop.groupby("age_band"):
        s = g.set_index("year")["population"].sort_index()
        logv = np.interp(list(years), s.index, np.log(s.to_numpy()))
        out[band] = np.exp(logv - np.interp(BASE_YEAR, s.index, np.log(s.to_numpy())))
    return pd.DataFrame(out, index=list(years))


TESTED = {   # exemption rule -> household flag; eligibility re-tested every year
    "senior_lowinc_county": "ex_senior_lowinc", "senior_lowinc_municipal": "ex_senior_lowinc_city",
    "senior_longterm_county": "ex_senior_longterm", "senior_longterm_municipal": "ex_senior_longterm_city",
    "disabled_total": "ex_disabled_total",
}
SURVEY_YEAR = 2024
COHORT_YEARS = range(BASE_YEAR + 1, 2037)   # new-owner cohorts (one per year)
COHORT_SIZE = 2500                           # records sampled per cohort


def _county_nc_share() -> pd.Series:
    """Share of 2026 new construction taxable value by county FIPS (DOR Data Book)."""
    from ptm.millage import county_fips_by_name
    from ptm.ratemodel import load_databook, norm
    db = load_databook()
    fips = {norm(k): v for k, v in county_fips_by_name().items()}
    db["county_fips"] = db["key"].map({**fips, "dade": fips.get("miamidade")})
    s = db.dropna(subset=["county_fips"]).set_index("county_fips")["nc_2026"].clip(lower=0)
    return s / s.sum()


def _nc_rates() -> pd.DataFrame:
    """Yearly new construction as a share of the prior year's just value, by REC category
    (adopted forecast, 2027-2032; later years hold 2032)."""
    from ptm.economy import PATHS
    d = pd.read_csv(PATHS)
    d = d[d["source"] == "rec_adopted"]
    out = {}
    for cat, key in [("homestead", "hs"), ("nonhomestead_residential", "nh"), ("nonresidential", "nr")]:
        jv = d[d["variable"] == f"just_value_{cat}"].set_index("year")["value"]
        nc = d[d["variable"] == f"new_construction_{cat}"].set_index("year")["value"]
        out[key] = (nc / jv.shift()).dropna()
    r = pd.DataFrame(out)
    return r.reindex(range(BASE_YEAR + 1, 2051)).ffill()


DYNAMIC = ["jv", "valp_market_cal", "av_school_prior", "av_nonschool_prior", "taxable_school_prior",
           "taxable_county_prior"]


class Projection:
    """Owners projected year by year. Static inputs (exemption flags, jurisdiction positions, 2026
    rates) are prepared once per baseline and reused by later Projections in the same process;
    each year only updates numeric arrays (values, assessed values, rates, tax)."""

    def __init__(self, baseline: pd.DataFrame, scenario: str = "central", overrides: dict | None = None,
                 seed: int = 2026, law: Law | None = None, rate_setting: dict | None = None,
                 end_year: int = 2036, demography: dict | None = None, rate_replay: dict | None = None):
        self.rate_replay = rate_replay    # {year: rate draws} from another run: rates don't respond
        self.econ = Economy(scenario, overrides)
        self.turnover = self.econ.spec["turnover"]
        self.rate_settings = {**self.econ.spec["rate_setting"], **(rate_setting or {})}
        self.law_base = law or _cached("law", load_law)
        self.end_year = end_year
        self.law = project_law(self.law_base, self.econ, end_year)
        sr = _cached("school", _school_tables)
        self.rates = RateSetter(self.rate_settings, BASE_YEAR, sr["rle_millage_2026"], sr["school_2026"])
        self.rng = np.random.default_rng(seed)

        prep = _cached(("prep", id(baseline), len(baseline)), lambda: self._prepare_cached(baseline))
        self.units = prep["static"]                      # shared, read-only
        self.a = {k: v.copy() for k, v in prep["dynamic"].items()}
        self.income = {k: v.copy() for k, v in prep["income"].items()}
        self.hs = prep["hs"]
        self.w0 = prep["w"]
        self.w = prep["w"].copy()
        self.demo = {**self.econ.spec.get("demography", {}), **(demography or {})}
        self.p_death = prep["p_death_reset"] if self.demo.get("deaths", True) else np.zeros(len(self.w0))
        self.age_band = prep["age_band"]
        self._band_names = [n for _, _, n in AGE_BANDS] + [""]
        pos = {n: i for i, n in enumerate(self._band_names)}
        self._band_idx = np.array([pos.get(b, len(self._band_names) - 1) for b in self.age_band])
        self.band_factors = age_band_factors(_cached("demography", _demography)[0], range(BASE_YEAR, 2051)) \
            if self.demo.get("reweight_by_age", True) else None
        self.weights = {BASE_YEAR: self.w.copy()}
        self.cohort_year = prep["cohort_year"]
        self.orig = self.cohort_year == 0
        self.owners_2026 = self.w0[self.orig].sum()
        self.nc = _cached("nc_rates", _nc_rates)
        # new owners each year = owners x household growth (constant ownership rate)
        self.cohort_w = np.zeros(len(self.w0))
        if self.demo.get("household_growth", True):
            idx, prev = 1.0, 1.0
            for y in COHORT_YEARS:
                idx *= 1 + self.econ.rate("households", y)
                m = self.cohort_year == y
                share = prep["cohort_share"][m]
                self.cohort_w[m] = self.owners_2026 * (idx - prev) * share / share.sum()
                prev = idx
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
        self.history[f"income_{BASE_YEAR}"] = self._income()
        self._base_rates = self._calibrate_sale_rates()
        self.age, self.tenure, self.jv_first = prep["age"], prep["tenure"], prep["jv_first"]
        self.flags0, self.takeup_u = prep["flags0"], prep["takeup_u"]
        self.flags = {k: v.copy() for k, v in self.flags0.items()}
        base_law = project_law(_cached("law", load_law), self.econ, BASE_YEAR + 1)
        self.takeup, self.offered, self.elig0 = {}, {}, {}
        for rid, fl in TESTED.items():
            elig = self._eligible(rid, BASE_YEAR, base_law)
            self.elig0[rid] = elig
            claim = self.flags0[fl]
            w = self.w0
            self.takeup[rid] = (w[claim & elig].sum() / max(w[elig].sum(), 1)) if elig.any() else 0.0
            # offered where any 2026 claimant lives in the same county (county rules) or city (city rules)
            j = self.yi if rid.endswith("municipal") else self.ci
            self.offered[rid] = np.isin(j, np.unique(j[claim & (j >= 0)]))
        self.rows = [self._row(BASE_YEAR, np.zeros(len(self.w), bool), prep["tax_2026"],
                               self.a["av_school_prior"], {c: prep[f"tax_{c}_2026"] for c in LEVIES})]

    def _prepare_cached(self, baseline: pd.DataFrame) -> dict:
        """_prepare, saved to disk when the baseline says where (Monte Carlo workers load it)."""
        import pickle
        from pathlib import Path
        path = baseline.attrs.get("prep_cache")
        src = baseline.attrs.get("prep_source")
        if path and Path(path).exists() and (not src or Path(path).stat().st_mtime >= Path(src).stat().st_mtime):
            with open(path, "rb") as fh:
                return pickle.load(fh)
        prep = self._prepare(baseline)
        if path:
            with open(path, "wb") as fh:
                pickle.dump(prep, fh)
        return prep

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
        pop, life = _cached("demography", _demography)
        age = np.clip(u["HHLDRAGEP"].fillna(45).astype(int).to_numpy(), 18, life.index.max())
        q = life.reindex(age).fillna(1.0).to_numpy()
        spouse = (u["HHT"] == 1).to_numpy() if "HHT" in u else np.zeros(len(u), bool)
        band = np.full(len(u), "", dtype=object)
        for lo, hi, name in AGE_BANDS:
            band[(age >= lo) & (age <= hi)] = name
        # new-owner cohorts: recent buyers (moved in within ~2 years), placed by county in
        # proportion to new construction; one block of COHORT_SIZE records per year, zero weight
        # until then (weights set in __init__ from the household forecast)
        n0 = len(u)
        donors = np.flatnonzero((u["MV"] <= 2).to_numpy())
        dw = u["WGTP"].to_numpy(dtype=float)[donors]
        dc = u["county_fips_tax"].to_numpy()[donors]
        share_now = pd.Series(dw).groupby(dc).sum() / dw.sum()
        target = _cached("nc_share", _county_nc_share)
        adj = (target.reindex(share_now.index) / share_now).fillna(1.0).clip(0.2, 5.0)
        pw = dw * pd.Series(dc).map(adj).fillna(1.0).to_numpy()
        pw = pw / pw.sum()
        crng = np.random.default_rng(2026)
        picks, cyear = [], []
        for y in COHORT_YEARS:
            picks.append(crng.choice(donors, size=COHORT_SIZE, replace=True, p=pw))
            cyear.append(np.full(COHORT_SIZE, y))
        pick = np.concatenate(picks)
        cohort_year = np.concatenate([np.zeros(n0, int)] + cyear)
        allrows = np.concatenate([np.arange(n0), pick])
        u = u.iloc[allrows].copy()
        u.index = pd.RangeIndex(len(u))
        u["cohort_year"] = cohort_year
        take = lambda arr: arr[allrows]  # noqa: E731
        hs, ci, q, spouse, band = take(hs), take(ci), take(q), take(spouse), take(band)
        f = lambda c: u[c].astype(float).to_numpy()  # noqa: E731
        # static frame for the engine: exemption flags and values, shares; plus reporting columns
        static_cols = [c for c in u.columns if c not in set(DYNAMIC)]
        tax26 = np.where(cohort_year == 0, np.nan_to_num(f(f"tax_model_{BASE_YEAR}")), 0.0)
        from ptm.exemptions import first_qualifying_jv
        jv_first = first_qualifying_jv(u, SURVEY_YEAR, BASE_YEAR).to_numpy(dtype=float) \
            if "purchase_year" in u else np.full(len(u), np.inf)
        tenure = (SURVEY_YEAR - u["purchase_year"].astype(float)).to_numpy() if "purchase_year" in u else np.zeros(len(u))
        flags0 = {fl: u[fl].fillna(False).astype(bool).to_numpy() if fl in u else np.zeros(len(u), bool)
                  for fl in TESTED.values()}
        # local-option amounts for households that may start claiming: the typical amount granted
        # by their county (city) in 2026, else the statewide median
        for amt, fl, key in [("ex_senior_amount", "ex_senior_lowinc", "county_fips_tax"),
                             ("ex_senior_city_amount", "ex_senior_lowinc_city", "city_idx")]:
            if amt in u:
                a_ = u[amt].astype(float)
                claim = flags0[fl] & (a_ > 0).to_numpy()
                med = a_[claim].groupby(u[key][claim]).median()
                fill = u[key].map(med).fillna(a_[claim].median() if claim.any() else 0.0)
                u[amt] = np.where(a_ > 0, a_, fill)
        return {
            "static": u[static_cols], "cohort_year": cohort_year,
            "age": u["HHLDRAGEP"].fillna(45).to_numpy(dtype=float), "tenure": np.nan_to_num(tenure),
            "jv_first": np.nan_to_num(jv_first, nan=np.inf), "flags0": flags0,
            "takeup_u": np.random.default_rng(7).random(len(u)), "cohort_share": np.concatenate(
                [np.zeros(n0)] + [pw[np.searchsorted(donors, k)] for k in picks]),
            "dynamic": {"jv": f("valp_jv_cal"), "valp_market_cal": f("valp_market_cal"),
                        "av_school_prior": f(f"av_sd_{BASE_YEAR}"), "av_nonschool_prior": f(f"av_nsd_{BASE_YEAR}"),
                        "taxable_school_prior": f(f"taxable_school_{BASE_YEAR}"),
                        "taxable_county_prior": f(f"taxable_county_{BASE_YEAR}")},
            "income": {c: f(c) for c in self.econ.spec["income_growth"] if c in u},
            "hs": hs, "w": np.where(cohort_year == 0, f("WGTP"), 0.0), "ci": ci, "ci_ok": ci >= 0, "yi": u["city_idx"].to_numpy(),
            "min_count_ok": counts >= 30,
            # death of the owner with no spouse present passes the home on (transfer to a surviving
            # spouse isn't a change of ownership, s. 193.155(3)(a)); married couples: both die
            "p_death_reset": np.where(spouse, q * q, q), "age_band": band,
            **{f"mill_{c}": np.nan_to_num(f(f"millage_{c}")) for c in LEVIES},
            "tax_2026": tax26,
            **{f"tax_{c}_2026": np.where(cohort_year == 0, np.nan_to_num(f(f"tax_{c}_{BASE_YEAR}")), 0.0)
               for c in LEVIES},
        }

    def _eligible(self, rid: str, y: int, law) -> np.ndarray:
        """Eligibility for a tested exemption in year y under `law` (homestead households)."""
        r = law.rule(rid)
        gross = self._income()
        agi = gross - np.nan_to_num(self.income.get("ssp_aged", 0)) - np.nan_to_num(self.income.get("ssip_aged", 0))
        ok = self.hs.copy()
        if rid == "disabled_total":
            return ok & (gross <= float(r.get("income_limit", y)))
        ok &= self.age >= float(r.get("min_age", y, 65))
        ok &= agi <= float(r.get("income_limit", y))
        if "residence_years" in r.spec:
            ok &= self.tenure >= float(r.get("residence_years", y))
        if "just_value_limit" in r.spec:
            ok &= self.jv_first < float(r.get("just_value_limit", y))
        return ok

    def _update_flags(self, y: int) -> dict:
        """This year's tested exemption flags: keep while eligible; new claimants at 2026 take-up.
        Total disability claimants above the income limit in 2026 are taken to have no income test
        (e.g. quadriplegic) and keep it."""
        out = {}
        for rid, fl in TESTED.items():
            elig = self._eligible(rid, y, self.law)
            f0 = self.flags0[fl]
            # only households that weren't eligible in 2026 can start claiming (eligible 2026
            # non-claimers stay non-claimers, so current law keeps 2026 claim rates)
            new = elig & ~self.elig0[rid] & self.offered[rid] & (self.takeup_u < self.takeup[rid])
            if rid == "disabled_total":
                no_test = f0 & ~self.elig0[rid]      # claimants above the limit in 2026: no income test
                out[fl] = (f0 & (elig | no_test)) | new
                continue
            out[fl] = (f0 & elig) | new
        self.flags = out
        return out

    def _income(self) -> np.ndarray:
        """Household income this year: sum of the grown income components (floored at 0)."""
        return np.maximum(sum(np.nan_to_num(v) for v in self.income.values()), 0)

    # --- sales -----------------------------------------------------------------------------------
    def _savings(self) -> np.ndarray:
        """Assessment savings carried into the year: just value minus last year's assessed value
        (school for homesteads, non-school for others)."""
        prior = np.where(self.hs, self.a["av_school_prior"], self.a["av_nonschool_prior"])
        return np.maximum(self.a["jv"] - prior, 0)

    def _calibrate_sale_rates(self) -> dict:
        """Base sale rates such that sales plus death transfers reset the calibrated share of homes
        in 2026: base x mean(lock-in x (1 - death)) + mean(death) = target."""
        li = self.turnover["lock_in"]
        f = lock_in_factor(self._savings(), li["per_100k_savings"], li["floor"])
        d, hs, w = self.p_death, self.hs, self.w
        out = {}
        for flag, key in [(True, "homestead_sale_rate"), (False, "nonhomestead_sale_rate")]:
            m = hs if flag else ~hs
            target = self.turnover[key]
            out[flag] = max(target - np.average(d[m], weights=w[m]), 0) / np.average((f * (1 - d))[m], weights=w[m])
        self.death_share_2026 = {flag: np.average(d[hs if flag else ~hs], weights=w[hs if flag else ~hs])
                                 for flag in (True, False)}
        return out

    def _draw_sales(self) -> tuple[np.ndarray, np.ndarray]:
        li, port = self.turnover["lock_in"], self.turnover["portability"]
        savings = self._savings()
        n = len(self.w)
        base = np.where(self.hs, self._base_rates[True], self._base_rates[False])
        p = np.clip(base * lock_in_factor(savings, li["per_100k_savings"], li["floor"]), 0, 1)
        sold = self.rng.random(n) < p
        ports = sold & self.hs & (self.rng.random(n) < port["share_of_homestead_sales"])
        died = self.rng.random(n) < self.p_death
        self._died = died & ~sold
        return sold | died, np.where(ports, np.minimum(savings, port["max_transfer"]), 0.0)

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
        w = self.w0.copy()
        if self.band_factors is not None:
            r = self.band_factors.loc[y].reindex(self._band_names).fillna(1.0).to_numpy()
            fac = r[self._band_idx]
            w = self.w0 * fac
            w = w * self.owners_2026 / w[self.orig].sum()   # existing owners: composition shifts
        entering = self.cohort_year == y
        active = (self.cohort_year > 0) & (self.cohort_year <= y)
        self.w = np.where(self.orig, w, np.where(active, self.cohort_w, 0.0))
        self.weights[y] = self.w.copy()
        # new homes enter at just value, first homestead year (no Save Our Homes savings)
        for k in ["av_school_prior", "av_nonschool_prior"]:
            a[k] = np.where(entering, a["jv"], a[k])
        for k in ["taxable_school_prior", "taxable_county_prior"]:
            a[k] = np.where(entering, 0.0, a[k])
        self._existing = self.orig | ((self.cohort_year > 0) & (self.cohort_year < y))
        self.history[f"income_{y}"] = self._income()
        sold, transfer = self._draw_sales()
        flags = self._update_flags(y)
        df = self.units.assign(**flags, jv=a["jv"], av_school_prior=a["av_school_prior"],
                               av_nonschool_prior=a["av_nonschool_prior"],
                               homestead_prior=self.hs & ~entering,
                               changed_ownership=sold, improvements=0.0, portability_transfer=transfer)
        live = self.orig | active                      # future cohorts don't exist yet: skip them
        res_live = step(df[live], self.law, y)
        res = res_live.reindex(df.index)
        for c in ["av_school", "av_county"]:
            res[c] = res[c].fillna(pd.Series(a["jv"], index=df.index))
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
        sel = hs & self.ci_ok & self._existing        # new construction stays out of rolled-back rates
        nc = len(self.rates.counties)
        growth = {}
        for c in ["school", "county"]:
            now = np.bincount(ci[sel], weights=(taxable[c] * w)[sel], minlength=nc)
            before = np.bincount(ci[sel], weights=(self.a[f"taxable_{c}_prior"] * w)[sel], minlength=nc)
            with np.errstate(divide="ignore", invalid="ignore"):
                g = np.where((before > 0) & self.min_count_ok, now / before, np.nan)
            growth[c] = g                                  # thin counties use the median
        if self.rate_replay is not None:          # "no response": the other run's rate decisions
            rp = self.rate_replay[y]
            self.rates.county_draws, self.rates.city_draws, self.rates.rle_draws = rp["county"], rp["city"], rp["rle"]
            self.rates.paths[y] = rp
        else:
            self._step_rates(growth, y)
        self._apply_rates()

    def _step_rates(self, growth: dict, y: int) -> None:
        nc = self.nc.loc[y] if self.demo.get("household_growth", True) else None
        try:   # the law's two-thirds-vote limit (multiple of the rolled-back rate) for this year
            cap = float(self.law.rule("maximum_millage_vote").get("two_thirds_vote_max_of_rolled_back", y))
        except Exception:
            cap = None
        self.rates.step_arrays(growth["school"], growth["county"],
                               self.econ.rate("home_value", y), self.econ.rate("nonresidential_value", y), y,
                               nc_rates=None if nc is None else (nc["hs"], nc["nh"], nc["nr"]), cap_multiple=cap)

    def _apply_rates(self) -> None:
        ci = self.ci
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
               "share_sold": (sold * w).sum() / wsum, "homestead_share_sold": (sold * w)[hs].sum() / whs,
               "homestead_share_death_transfer": (getattr(self, "_died", np.zeros(len(w), bool)) * w)[hs].sum() / whs,
               "new_owner_share": w[self.cohort_year > 0].sum() / wsum if hasattr(self, "cohort_year") else 0.0,
               "share_owners_75_plus": w[np.isin(self.age_band, ["75_79", "80_84", "85_plus"])].sum() / wsum}
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
                "valp_jv_cal", "valp_market_cal", "hincp_aged", "HHLDRAGEP", "MV", "home_type", "HHT", "purchase_year",
                f"av_sd_{BASE_YEAR}", f"av_nsd_{BASE_YEAR}", f"tax_model_{BASE_YEAR}",
                "homestead_portion_share", "homestead_share"}
        cols |= set(econ.spec["income_growth"])
        cols |= {f"{x}_{c}" for x in ["millage", "taxable"] for c in LEVIES}
        cols |= {f"taxable_{c}_{BASE_YEAR}" for c in LEVIES} | {f"tax_{c}_{BASE_YEAR}" for c in LEVIES}
        for r in law.exemptions():
            for k in ["household_flag", "value_column"]:
                if r.spec.get(k):
                    cols.add(r.spec[k])
        cols |= {"income_decile"}
        cols |= {c for c in b.columns if c.startswith("ex_")}   # replicate weights stay in the baseline (join by index)
        return [c for c in b.columns if c in cols]

    def draw_totals(self, groups: "pd.Series | str") -> dict:
        """Tax totals for every rate draw: {year: array (n_groups + 1, n_draws)}, rows = the sorted
        group labels, then the all-owner total. Exact: tax is taxable x rate, and taxable values
        don't depend on rates, so each draw's tax is a weighted sum computed by matrix products."""
        u = self.units
        g = u[groups] if isinstance(groups, str) else groups.reindex(u.index)
        labels = sorted(g.dropna().unique())
        gpos = g.map({v: i for i, v in enumerate(labels)}).to_numpy()
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
            w = self.weights.get(y, u["WGTP"].to_numpy())
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
