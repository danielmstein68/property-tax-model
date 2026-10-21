"""Texas projections, 2026 -> 2036: owners' and other property's taxes under current law.

    from ptm.tx.project import TxProjection
    p = TxProjection(o, rows, "central").run(2036)      # o, rows: the 2026 baseline (ptm.tx.baseline.build_full)
    p.summary            # one row per year: tax by class, owners, over-65 homesteads, sales, rates, school finance
    p.household_results  # per owner record: tax_<year>, income_<year>, weight_<year>, ...

Each year (inputs/tx_projection_assumptions.yaml, through ptm.economy.Economy as for Florida):
  1. economy    market values x (1 + home value growth); income components grow (wages, other income,
                benefits by CPI)
  2. ages       every owner is a year older
  3. sales and deaths  each home changes hands with a probability that falls with its cap savings
                (lock-in), or passes on when the owner dies (both spouses for couples; Texas life table).
                Rates are set so sales plus deaths match the PUMS move-in rate. The home's appraised value
                resets to market, and it gets a new owner drawn from the county's recent buyers (moved in
                within two years): age, income, over-65 / disabled status. The freeze ends; a new owner who
                is 65+ or disabled starts a new freeze at this year's tax (ceiling portability not modelled).
  4. turning 65 owners whose older spouse reaches 65 claim the over-65 exemption and freeze at the 2026
                claim rate of owners 65+ (s. 11.13(c), s. 11.26): the state $60,000 school exemption, the
                units' local over-65 amounts, and a ceiling at this year's school tax (and at this year's
                tax for counties, cities and colleges that have adopted a freeze, s. 11.261)
  5. weights    owners by householder age (18-64, 65+) grow with Texas's projected population in each band
                (Texas Demographic Center), at 2026 ownership rates; the growth beyond existing homes is new
                owners in new homes (pre-built records from recent buyers, placed by county with TDC's county
                growth), appraised at market, entering the rolls as new construction
  6. appraisal  homesteads: min(market, last year's appraised x 1.10) (s. 23.23)
  7. rates      non-school units: the no-new-revenue M&O rate (last year's M&O rate / growth of existing
                taxable value - model homesteads plus each unit's non-homestead base) x (1 + position x
                (multiplier - 1)), position = where the unit set its 2025 rate between its no-new-revenue
                and voter-approval rates; I&S held. Schools: state compression (MCR = last x 1.025 / (1 + g)
                when value growth g > 2.5%), each district's MCR the lesser of its own compressed rate and the
                state's, at least 90% of it; M&O = MCR + enrichment (held); I&S held
  8. freezes    school ceilings fall by last year's taxable value x the MCR cut (s. 11.26(a-10)); other
                ceilings stay in dollars
  9. other property  each unit's non-homestead taxable value (2025 roll total less the model's owners)
                grows with its county's mix of residential, business and mineral value plus new
                construction; the 20% circuit breaker expires after 2026 (s. 23.231(k)), so 2027 adds back
                its 2025 loss; tax = base x the unit's rate
 10. finance    each district's value grows with g plus new construction; Tier One / Two state aid and
                recapture from ptm.tx.school.finance

Exemption amounts are the law spec's nominal dollars (not indexed in Texas); local percentages held.
Not modelled: ceiling portability on a move, owners becoming disabled, veterans' status changing on a sale
(it stays with the home), homestead status changes.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from ptm.economy import Economy
from ptm.law import load_law
from ptm.tx.school import finance, load_sof

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "inputs" / "tx_projection_assumptions.yaml"
PATHS = ROOT / "inputs" / "tx_economy_paths.csv"
PROC = ROOT / "data" / "processed"
BASE_YEAR = 2026
CLASSES = ["school", "county", "city", "college", "hospital", "special"]
COHORT_SIZE = 2000                      # new-owner records per year
INCOME = ["wagp_aged", "semp_aged", "intp_aged", "ssp_aged", "ssip_aged", "pap_aged", "retp_aged", "oip_aged"]


def apply_2026_school_rates(rows: pd.DataFrame) -> pd.DataFrame:
    """School districts' 2026 M&O and I&S rates from TEA's 2026-27 Summary of Finances (its estimate of each
    district's adopted rates) in place of the Comptroller's 2025 rates; other units stay at 2025 until the
    Comptroller's 2026 file (early 2027). The roll checks keep 2025 rates on both sides."""
    sof = load_sof().set_index("cdn")
    x = rows.copy()
    sch = x["levy_class"] == "school"
    cdn = x.loc[sch, "unit_id"].astype(str).str.split("-").str[:2].str.join("")
    mo, is_ = cdn.map(sof["mo_rate"]), cdn.map(sof["is_rate"])
    x.loc[sch, "mo_rate"] = mo.fillna(x.loc[sch, "mo_rate"]).to_numpy()
    x.loc[sch, "is_rate"] = is_.fillna(x.loc[sch, "is_rate"]).to_numpy()
    return x


# --- cached inputs -----------------------------------------------------------------------------------
def _cache(name: str, make):
    p = PROC / name
    if p.exists():
        return pd.read_parquet(p)
    d = make()
    d.to_parquet(p)
    return d


def couple_ages() -> pd.DataFrame:
    from ptm.tx.survey import couple_ages as make
    return _cache("tx_couple_ages_2026.parquet", make)


def units_2025() -> pd.DataFrame:
    from ptm.tx.units import load_units
    return _cache("tx_units_2025.parquet", lambda: load_units(2025))


def county_mix() -> pd.DataFrame:
    """Per county FIPS (PVS 2025 local market values): residential, business and mineral value, and the
    20% circuit breaker's value loss."""
    def make():
        from ptm.tx.pvs import load_pvs
        d = load_pvs(2025)
        res = d[["LOCL A", "LOCL B", "LOCL C1", "LOCL E", "LOCL M", "LOCL O"]].sum(axis=1)
        mine = d["LOCL G"]
        tot = d["LOCL CATG TOT"]
        out = pd.DataFrame({"county_fips": d["county_fips"], "residential": res, "mineral": mine,
                            "business": (tot - res - mine).clip(lower=0), "circuit_breaker": d["LOSS TO NON HOME CAP"]})
        return out.groupby("county_fips").sum().reset_index()
    return _cache("tx_county_mix_2025.parquet", make)


def rate_positions(u: pd.DataFrame) -> pd.Series:
    """Where each unit set its 2025 total rate between its no-new-revenue and voter-approval rates."""
    ok = u["nnr_rate"].notna() & u["var_rate"].notna() & (u["var_rate"] > u["nnr_rate"] + 1e-6)
    pos = ((u["total_rate"] - u["nnr_rate"]) / (u["var_rate"] - u["nnr_rate"])).where(ok)
    return pos.clip(0, 1.2)


def pop_factors(years: range) -> pd.DataFrame:
    """Texas population 18-64 and 65+ relative to the base year (TDC 2020 / 2040 / 2060, geometric)."""
    pop = pd.read_csv(ROOT / "inputs" / "tx_population_by_age.csv")
    out = {}
    for band, g in pop.groupby("age_band"):
        s = g.set_index("year")["population"].sort_index()
        lv = np.interp(list(years), s.index, np.log(s.to_numpy()))
        out[band] = np.exp(lv - np.interp(BASE_YEAR, s.index, np.log(s.to_numpy())))
    return pd.DataFrame(out, index=list(years))


def county_growth(years: range) -> pd.DataFrame:
    """Projected population by county FIPS and year (TDC decades, geometric in between)."""
    c = pd.read_csv(ROOT / "inputs" / "tx_county_population.csv", dtype={"county_fips": str}).set_index("county_fips")
    dec = [2020, 2030, 2040, 2050, 2060]
    lv = np.log(c[[f"pop_{y}" for y in dec]].clip(lower=1).to_numpy())
    return pd.DataFrame({y: np.exp([np.interp(y, dec, r) for r in lv]) for y in years}, index=c.index)


# --- projection -------------------------------------------------------------------------------------
class TxProjection:
    def __init__(self, o: pd.DataFrame, rows: pd.DataFrame, scenario: str = "central", overrides: dict | None = None,
                 seed: int = 2026, end_year: int = 2036, rate_setting: dict | None = None, demography: dict | None = None):
        self.econ = Economy(scenario, overrides, assumptions_path=SPEC, paths_path=PATHS)
        spec = self.spec = self.econ.spec
        self.rs = {**spec["rate_setting"], **(rate_setting or {})}
        self.demo = {**spec["demography"], **(demography or {})}
        self.law = load_law("tx")
        self.rng = np.random.default_rng(seed)
        self.end_year = end_year
        self.scenario = scenario
        self._records(o, rows, seed)
        self._units()
        self._weights_init()
        self.year = BASE_YEAR
        self.history, self.rows_out = {}, []
        self._tax_year(BASE_YEAR, first=True)
        self._base_sale = self._calibrate(self._p_death(self.age + 1))   # next year's ages, base-year savings

    # records: owners (homestead and not) + new-owner cohorts --------------------------------------------
    def _records(self, o: pd.DataFrame, rows: pd.DataFrame, seed: int) -> None:
        o = o.join(couple_ages(), on="SERIALNO")
        o["couple_age"] = o["couple_age"].fillna(o["HHLDRAGEP"] + 2)
        o["spouse"] = o["spouse"].fillna(False).astype(bool)
        n0 = len(o)
        years = range(BASE_YEAR + 1, self.end_year + 1)
        # cohorts: recent buyers (moved in within two years) with a homestead, by county, in proportion to
        # the county's projected population growth that year
        cg = county_growth(range(BASE_YEAR, self.end_year + 1))
        hs = o["homestead"].to_numpy()
        recent = hs & (o["MV"] <= 2).to_numpy()
        cty = o["county_fips_tax"].astype(str).to_numpy()
        crng = np.random.default_rng(seed + 31)
        picks, cyear = [], []
        donors_by_cty = {c: np.flatnonzero(recent & (cty == c)) for c in np.unique(cty[hs])}
        for c, d in list(donors_by_cty.items()):
            if len(d) < 5:
                donors_by_cty[c] = np.flatnonzero(hs & (cty == c))
        w0 = o["WGTP"].to_numpy(dtype=float)
        for y in years:
            add = (cg[y] - cg[y - 1]).clip(lower=0).reindex(list(donors_by_cty)).fillna(0)
            share = add / add.sum()
            n_c = np.floor(share * COHORT_SIZE).astype(int)
            pick = []
            for c, k in n_c.items():
                if k > 0:
                    d = donors_by_cty[c]
                    pick.append(crng.choice(d, size=k, replace=True, p=w0[d] / w0[d].sum()))
            pick = np.concatenate(pick)
            picks.append(pick)
            cyear.append(np.full(len(pick), y))
        pick = np.concatenate(picks)
        self.cohort_share = {y: None for y in years}
        allrec = np.concatenate([np.arange(n0), pick])
        self.cohort_year = np.concatenate([np.zeros(n0, int)] + cyear)
        # new-owner weight within its year: the donor's county share of growth x its weight within the county
        cs = np.zeros(len(allrec))
        for y, pk in zip(years, picks):
            add = (cg[y] - cg[y - 1]).clip(lower=0)
            c_ = cty[pk]
            cnt = pd.Series(w0[pk]).groupby(c_).transform("sum").to_numpy()
            cs[self.cohort_year == y] = add.reindex(c_).fillna(0).to_numpy() * w0[pk] / cnt
        self.cohort_rel = cs
        R = o.iloc[allrec].reset_index().rename(columns={"index": "hid0"})
        self.n = len(R)
        self.orig = self.cohort_year == 0
        # rows: each record's taxing-unit rows (cohorts copy their donor's)
        pos0 = pd.Series(np.arange(n0), index=o.index)
        rr = rows[rows["hid"].isin(o.index)].copy()
        rr["rec0"] = pos0.reindex(rr["hid"]).to_numpy()
        rr = rr.sort_values("rec0", kind="stable")
        start = np.searchsorted(rr["rec0"].to_numpy(), np.arange(n0))
        stop = np.searchsorted(rr["rec0"].to_numpy(), np.arange(n0), side="right")
        idx = np.concatenate([np.arange(start[j], stop[j]) for j in allrec])
        rec = np.concatenate([np.full(stop[j] - start[j], i) for i, j in enumerate(allrec)])
        X = rr.iloc[idx].reset_index(drop=True)
        X["rec"] = rec
        self.X = X
        self.rec = rec
        f = lambda c, d=0.0: np.array(R[c].fillna(d).to_numpy(dtype=float))  # noqa: E731
        self.R = R
        self.w0 = np.where(self.orig, f("WGTP"), 0.0)
        self.hs = np.array(R["homestead"].fillna(False).to_numpy(dtype=bool))
        self.mkt = f("market")
        self.ap = f("appraised", np.nan)
        self.ap = np.where(np.isnan(self.ap), self.mkt, self.ap)     # 2026: the circuit breaker still applies to non-homesteads
        self.age = f("couple_age")
        self.hage = f("HHLDRAGEP") + 2
        self.spouse = np.array(R["spouse"].to_numpy(dtype=bool))
        self.o65 = np.array(R["over65_or_disabled"].fillna(False).to_numpy(dtype=bool) & self.hs)
        self.dvt = R["dv_total"].fillna(False).to_numpy(dtype=bool)
        self.county = R["county_fips_tax"].astype(str).to_numpy()
        self.inc = {c: f(c) for c in INCOME if c in R}
        self.inc0 = {c: v.copy() for c, v in self.inc.items()}      # 2026 incomes (donor attributes)
        self.inc_idx = {c: 1.0 for c in self.inc}
        self.attr0 = {"age": self.age.copy(), "hage": self.hage.copy(), "spouse": self.spouse.copy(), "o65": self.o65.copy()}
        # donor pools for new owners after a sale: recent buyers in the county, homestead or not
        self.pool = {}
        for (c, h_), g in pd.DataFrame({"c": self.county[self.orig], "h": self.hs[self.orig],
                                         "r": (R["MV"].to_numpy()[self.orig] <= 2)}).groupby(["c", "h"]):
            d = g.index[g["r"]].to_numpy()
            self.pool[(c, h_)] = d if len(d) >= 5 else g.index.to_numpy()
        # death and take-up
        life = pd.read_csv(ROOT / "inputs" / "tx_life_table_2021.csv").set_index("age")["qx"]
        self.qx = life.reindex(range(0, 121)).ffill().fillna(1.0).to_numpy()
        a65 = self.orig & self.hs & (self.age >= 65) & ~self.dvt
        self.takeup65 = float(self.w0[a65 & self.o65].sum() / max(self.w0[a65].sum(), 1))
        self.u_take = np.random.default_rng(seed + 7).random(self.n)

    # units: rates, positions, local over-65 amounts, freezes, non-homestead bases ------------------------
    def _units(self) -> None:
        X, spec = self.X, self.spec
        U0 = units_2025()
        ids = pd.Index(pd.unique(pd.concat([X["unit_id"], U0["unit_id"]])))
        self.uid = ids
        self.upos = ids.get_indexer(X["unit_id"])
        nu = len(ids)
        first = X.groupby("unit_id")[["mo_rate", "is_rate", "levy_class"]].first()
        u0 = U0.drop_duplicates("unit_id").set_index("unit_id")
        cls = pd.Series(first["levy_class"].reindex(ids).to_numpy(), index=ids).fillna(u0["levy_class"].reindex(ids))
        self.ucls = cls.to_numpy()
        mo = first["mo_rate"].reindex(ids).fillna(u0["mo_rate"].reindex(ids)).fillna(0).to_numpy(dtype=float)
        is_ = first["is_rate"].reindex(ids).fillna(u0["is_rate"].reindex(ids)).fillna(0).to_numpy(dtype=float)
        # schools outside the model's rows: TEA 2026 rates
        sof = load_sof()
        sofi = sof.set_index("cdn")
        cdn = pd.Series(ids).str.split("-").str[:2].str.join("").to_numpy()
        sch = self.ucls == "school"
        mo = np.where(sch & pd.isna(first["mo_rate"].reindex(ids)).to_numpy(), pd.Series(cdn).map(sofi["mo_rate"]).fillna(pd.Series(mo)).to_numpy(), mo)
        self.mo, self.is_ = mo, is_
        self.mo0 = mo.copy()
        # rate positions (non-school); avg:<fips>:<class> units and units without rates: class means
        pos = rate_positions(u0).reindex(ids)
        lev = u0["levy"].reindex(ids).fillna(0)
        cls_mean = {c: float(np.average(pos[(cls == c) & pos.notna()], weights=lev[(cls == c) & pos.notna()].clip(lower=1)))
                    for c in CLASSES if c != "school" and ((cls == c) & pos.notna()).any()}
        self.pos_spread = {c: (pos[(cls == c) & pos.notna()].to_numpy(), lev[(cls == c) & pos.notna()].clip(lower=1).to_numpy()) for c in cls_mean}
        self.pos = pos.fillna(cls.map(cls_mean)).fillna(0.5).to_numpy(dtype=float)
        m = spec["rate_setting"]["multiplier"]
        self.mult = cls.map(lambda c: m.get(c, m["default"])).to_numpy(dtype=float)
        if self.rs.get("rule") == "voter_approval":
            self.pos = np.ones(nu)
        # county of each unit; avg units from their id
        ucty = u0["county_fips"].reindex(ids)
        avg = pd.Series(ids).str.startswith("avg:").to_numpy()
        ucty = np.where(avg, pd.Series(ids).str.split(":").str[1].to_numpy(), ucty.astype(object))
        self.ucty = ucty.astype(str)
        self.avg = avg
        # schools: MCR and enrichment (TEA)
        self.cdn = cdn
        mcr = pd.Series(cdn).map(sofi["mcr"]).to_numpy(dtype=float)
        self.mcr = np.where(sch, np.nan_to_num(mcr, nan=0.6254), np.nan)
        self.enrich = np.where(sch, np.clip(np.nan_to_num(pd.Series(cdn).map(sofi["mo_rate"]).to_numpy(dtype=float), nan=0.0) - self.mcr, 0, 0.17), 0.0)
        self.enrich = np.where(sch & np.isnan(pd.Series(cdn).map(sofi["mo_rate"]).to_numpy(dtype=float)), np.clip(mo - self.mcr, 0, 0.17), self.enrich)
        self.state_mcr = float(self.law.rule("school_mcr").get("state_max", BASE_YEAR))
        self.sof = sof
        self.district_v = sof.set_index("cdn")["value_t2"].copy()
        # local over-65 amount by unit: median other_fixed of over-65 rows less that of other rows (>= 0)
        o65r = self.o65[self.rec] & ~self.dvt[self.rec]
        of = X["other_fixed"].fillna(0)
        fin = np.isfinite(of)              # fully exempt rows carry an infinite amount
        m1, m0 = o65r & fin, ~o65r & fin
        a = of[m1].groupby(X.loc[m1, "unit_id"]).median().sub(of[m0].groupby(X.loc[m0, "unit_id"]).median(), fill_value=0)
        self.amt65 = a.clip(lower=0).reindex(ids).fillna(0).to_numpy()
        self.of = of.to_numpy(dtype=float).copy()
        # freezes: units with a freeze (schools all; others where any 2026 over-65 row has a ceiling)
        has_ceiling = X["ceiling_ratio"].notna().to_numpy() & self.o65[self.rec]
        adopted = np.zeros(nu, bool)
        adopted[np.unique(self.upos[has_ceiling])] = True
        self.freeze_unit = adopted | (self.ucls == "school")
        self.frozen = has_ceiling
        self.ratio0 = X["ceiling_ratio"].to_numpy(dtype=float)
        self.ceiling = np.full(len(X), np.nan)
        self.new_freeze = np.zeros(len(X), bool)
        # rows' static parts
        self.lpct = X["local_pct"].fillna(0).to_numpy(dtype=float)
        self.row_mo0 = X["mo_rate"].fillna(0).to_numpy(dtype=float)     # rows' own rates (a unit's can differ by row)
        self.row_is = X["is_rate"].fillna(0).to_numpy(dtype=float)
        self.hshare = X["hs_share"].fillna(1).to_numpy(dtype=float)
        self.is_school = (X["levy_class"] == "school").to_numpy()
        # non-homestead bases: 2025 roll taxable x 2026 growth, less the model's owners (avg units' owners
        # spread over the real units of their class in the county by taxable value)
        T = u0["taxable_value"].reindex(ids).fillna(0).to_numpy(dtype=float) * (1 + self.econ.rate("home_value", BASE_YEAR))
        self.T = np.where(avg, 0.0, T)
        mix = county_mix().set_index("county_fips")
        self.mix = mix
        self.nh = None                       # set in the base year once owners' taxable is known
        self.sch_state_mcr = self.state_mcr

    def _weights_init(self) -> None:
        years = range(BASE_YEAR, self.end_year + 2)
        self.pf = pop_factors(years) if self.demo.get("reweight_by_age", True) else pd.DataFrame(1.0, index=list(years), columns=["18_64", "65_plus"])
        band = self.hage >= 65
        self.band_t0 = {"18_64": self.w0[self.orig & ~band].sum(), "65_plus": self.w0[self.orig & band].sum()}
        self.w = self.w0.copy()
        self.weights = {BASE_YEAR: self.w.copy()}

    # one year's taxable values and tax ------------------------------------------------------------------
    def _taxable(self, y: int) -> np.ndarray:
        r = self.rec
        ap = self.ap[r]
        o65 = self.o65[r]
        hs = self.hs[r]
        sch_hs = self.law.rule("school_homestead").get("amount", y)
        sch_65 = self.law.rule("school_over65_disabled").get("amount", y)
        local = np.where(self.lpct > 0, np.maximum(self.lpct * ap, 5000), 0.0)
        state = np.where(self.is_school & hs, sch_hs + np.where(o65, sch_65, 0), 0.0)
        state = np.minimum(state, ap * self.hshare)
        tx = np.maximum(0, ap - state - local - self.of)
        return np.where(self.dvt[r] & hs, 0.0, tx)

    def _compress(self, H: np.ndarray, entering: np.ndarray) -> np.ndarray:
        """School compression from this year's total taxable value (DPV, new property included): the state
        compression percentage = last x 1.025 / (1 + statewide growth) when growth is 2.5% or more (Education
        Code s. 48.255(b); TEA truncates to 4 decimals); each district's MCR = last x 1.025 x last DPV / DPV
        when its own growth is 2.5% or more, at most the state's and at least 90% of it (ss. 48.2551(b),
        48.2552). Returns each unit's MCR cut (per $100) for the freezes; district values follow DPV growth."""
        lim, fl = self.spec["school"]["growth_limit"], self.spec["school"]["floor_share"]
        sch = (self.ucls == "school") & ~self.avg
        now, prev = H + self.nh, self.H_prev + self.nh_prev
        G = now[sch].sum() / prev[sch].sum() - 1
        gu = np.where(prev > 0, now / np.maximum(prev, 1e-9) - 1, G)
        new_state = self.state_mcr * (1 + lim) / (1 + G) if G >= lim else self.state_mcr
        new_state = float(np.floor(new_state * 10_000) / 10_000)
        own = np.where(gu >= lim, self.mcr * (1 + lim) / (1 + gu), self.mcr)
        new_mcr = np.where(self.ucls == "school", np.maximum(np.minimum(own, new_state), fl * new_state), np.nan)
        cut = np.nan_to_num(self.mcr - new_mcr)
        self.mcr, self.state_mcr, self.dpv_growth = new_mcr, new_state, float(G)
        # school finance values: each district's DPV growth (its units' total), else the state's
        d = pd.DataFrame({"cdn": self.cdn[sch], "now": now[sch], "prev": prev[sch]}).groupby("cdn")[["now", "prev"]].sum()
        gd = (d["now"] / d["prev"].replace(0, np.nan)).reindex(self.district_v.index).fillna(1 + G)
        self.district_v = self.district_v * gd.to_numpy()
        return cut

    def _tax_year(self, y: int, first: bool = False, entering: np.ndarray | None = None) -> None:
        taxable = self._taxable(y)
        live = self.orig | ((self.cohort_year > 0) & (self.cohort_year <= y))
        lr = live[self.rec]
        w_row = self.w[self.rec]
        nu = len(self.uid)
        H = np.bincount(self.upos[lr], weights=(taxable * w_row)[lr], minlength=nu)
        if first:
            # owners' taxable spread from avg units to the real units of their class and county
            Hr = H.copy()
            k = pd.DataFrame({"c": self.ucty, "k": self.ucls, "T": self.T, "H": H, "avg": self.avg})
            tot = k[~k["avg"]].groupby(["c", "k"])["T"].transform("sum")
            addh = k[k["avg"]].groupby(["c", "k"])["H"].sum()
            key = pd.MultiIndex.from_arrays([k.loc[~k["avg"], "c"], k.loc[~k["avg"], "k"]])
            share = (k.loc[~k["avg"], "T"] / tot.replace(0, np.nan)).fillna(0).to_numpy()
            Hr[~self.avg] += addh.reindex(key).fillna(0).to_numpy() * share
            self.nh = np.where(self.avg, 0.0, np.maximum(self.T - Hr, 0))
            self.H_prev, self.nh_prev = H, self.nh.copy()
            rate = self.mo + self.is_
        else:
            # existing property: owners other than this year's new homes, non-homestead base before new
            # construction; no-new-revenue M&O rate = last M&O rate / growth of the existing base
            ex = lr & ~entering[self.rec]
            H_ex = np.bincount(self.upos[ex], weights=(taxable * w_row)[ex], minlength=nu)
            prior = self.H_prev + self.nh_prev
            gb = np.where(prior > 0, (H_ex + self.nh) / np.maximum(prior, 1e-9), 1.0)
            gb = np.where(np.isfinite(gb) & (gb > 0), gb, 1.0)
            # avg units follow their county's class average
            k = pd.DataFrame({"c": self.ucty, "k": self.ucls, "gb": gb, "w": prior})
            real = ~self.avg
            cgb = k[real].assign(x=k["gb"] * k["w"]).groupby(["c", "k"])[["x", "w"]].sum()
            cgb = (cgb["x"] / cgb["w"].replace(0, np.nan))
            key = pd.MultiIndex.from_arrays([k.loc[self.avg, "c"], k.loc[self.avg, "k"]])
            gb[self.avg] = cgb.reindex(key).fillna(1.0).to_numpy()
            pos = self.pos
            if self.rs.get("draws"):
                pos = pos.copy()
                for c, (vals, lw) in self.pos_spread.items():
                    m = self.ucls == c
                    pos[m] = self.rng.choice(vals, size=m.sum(), p=lw / lw.sum())
            ns = self.ucls != "school"
            # voter-approval multiplier: 8% for special taxing units - hospital districts, junior colleges and
            # any unit whose M&O rate is 2.5 cents or less (Tax Code s. 26.012(19), s. 26.04(c)(2); low-rate
            # water districts, Water Code s. 49.23601); 3.5% otherwise (developed water districts, s. 49.23602)
            mult = np.where(self.mo <= self.spec["rate_setting"].get("special_unit_max_mo_rate", 0.025), 1.08, self.mult)
            if self.rs.get("rule") != "hold":
                self.mo[ns] = self.mo[ns] / gb[ns] * (1 + pos[ns] * (mult[ns] - 1))
            # new non-homestead construction is in the school districts' total value (DPV) for compression
            self.nh = self.nh * (1 + self.spec["new_construction"])
            cut = self._compress(H, entering)
            sch = ~ns
            self.mo[sch] = (self.mcr + self.enrich)[sch]
            rate = self.mo + self.is_
            self.H_prev = H
        up = self.upos
        idx = np.where(self.mo0[up] > 0, self.mo[up] / np.where(self.mo0[up] > 0, self.mo0[up], 1), 1.0)
        row_rate = np.where(self.is_school, self.mo[up], self.row_mo0 * idx) + self.row_is
        uncapped = taxable * row_rate / 100
        tax = uncapped.copy()
        if first:
            self.ceiling = np.where(self.frozen, uncapped * np.nan_to_num(self.ratio0, nan=1.0), np.nan)
        else:
            # school ceilings (s. 11.26(a-10)): last year's tax imposed, less last year's taxable value x the
            # MCR cut, less any increase in the state homestead and over-65 exemptions x this year's rate
            sc = self.frozen & self.is_school
            ex_up = (self.law.rule("school_homestead").get("amount", y) + self.law.rule("school_over65_disabled").get("amount", y)
                     - self.law.rule("school_homestead").get("amount", y - 1) - self.law.rule("school_over65_disabled").get("amount", y - 1))
            self.ceiling[sc] = (self.prev_tax[sc] - self.prev_taxable[sc] * cut[self.upos[sc]] / 100
                                - max(ex_up, 0) * row_rate[sc] / 100)
            # new freezes start at this year's tax
            self.ceiling[self.new_freeze] = uncapped[self.new_freeze]
            self.frozen = self.frozen | self.new_freeze
            self.new_freeze[:] = False
        fz = self.frozen & self.o65[self.rec]
        tax[fz] = np.minimum(uncapped[fz], np.maximum(self.ceiling[fz], 0))
        self.prev_taxable = taxable
        self.prev_tax = tax
        self.nh_prev = self.nh.copy()
        self._record(y, tax, taxable, rate, live)

    # one year -------------------------------------------------------------------------------------------
    def step_year(self) -> None:
        y = self.year + 1
        e, spec = self.econ, self.spec
        g = e.rate("home_value", y)
        self.mkt = self.mkt * (1 + g)
        for c in self.inc:
            gr = e.rate(spec["income_growth"][c], y)
            self.inc[c] = self.inc[c] * (1 + gr)
            self.inc_idx[c] *= 1 + gr
        live = self.orig | ((self.cohort_year > 0) & (self.cohort_year < y))
        entering = self.cohort_year == y
        prev_age = self.age.copy()
        self.age = self.age + 1
        self.hage = self.hage + 1
        # sales and deaths
        reset = np.zeros(self.n, bool)
        if self.demo.get("deaths", True) or self.spec["turnover"]["homestead_sale_rate"] > 0:
            d = self._p_death()
            li = spec["turnover"]["lock_in"]
            sav = np.where(self.hs, np.maximum(self.mkt - self.ap, 0), 0)
            p = np.clip(np.where(self.hs, self._base_sale[True], self._base_sale[False])
                        * np.maximum(1 + li["per_100k_savings"] * sav / 100_000, li["floor"]), 0, 1)
            sold = self.rng.random(self.n) < p
            died = (self.rng.random(self.n) < d) if self.demo.get("deaths", True) else np.zeros(self.n, bool)
            reset = (sold | died) & live
            self._died = died & ~sold & live
        self._reset = reset
        # appraisal: cap, resets and new homes at market
        self.ap = np.where(self.hs, np.minimum(self.mkt, self.ap * 1.10), self.mkt)
        self.ap[reset | entering] = self.mkt[reset | entering]
        # new owners on sold or inherited homes
        rows_of = self._rows_of
        if self.demo.get("replace_owner_on_sale", True) and reset.any():
            idx = np.flatnonzero(reset)
            donor = np.empty(len(idx), int)
            for (c, h_), g_ in pd.DataFrame({"c": self.county[idx], "h": self.hs[idx]}).groupby(["c", "h"]).groups.items():
                pool = self.pool.get((c, h_))
                if pool is None or not len(pool):
                    pool = self.pool.get((c, not h_), np.array([], int))
                if not len(pool):
                    donor[np.asarray(g_)] = idx[np.asarray(g_)]
                    continue
                pw = self.w0[pool] / self.w0[pool].sum()
                donor[np.asarray(g_)] = self.rng.choice(pool, size=len(g_), p=pw)
            old65 = self.o65[idx].copy()
            self.age[idx] = self.attr0["age"][donor]
            self.hage[idx] = self.attr0["hage"][donor]
            self.spouse[idx] = self.attr0["spouse"][donor]
            # over-65 at the 2026 claim rate (as for owners turning 65); disabled under-65 owners as the donor
            age65 = self.age[idx] >= 65
            self.o65[idx] = self.hs[idx] & np.where(age65, self.u_take[idx] < self.takeup65, self.attr0["o65"][donor])
            for c in self.inc:
                self.inc[c][idx] = self.inc0[c][donor] * self.inc_idx[c]
            r = rows_of(idx)
            self.frozen[r] = False
            self.ceiling[r] = np.nan
            self._o65_change(idx, old65)
        # cohorts entering: their donor's age, income grown to this year
        if entering.any():
            idx = np.flatnonzero(entering)
            self.o65[idx] = self.hs[idx] & np.where(self.age[idx] >= 65, self.u_take[idx] < self.takeup65, self.o65[idx])
            self._o65_change(idx, np.zeros(len(idx), bool))
        # turning 65 (or the older spouse): claim at the 2026 rate
        turn = live & self.hs & ~self.o65 & ~self.dvt & (prev_age < 65) & (self.age >= 65) & (self.u_take < self.takeup65)
        if turn.any():
            idx = np.flatnonzero(turn)
            self.o65[idx] = True
            self._o65_change(idx, np.zeros(len(idx), bool))
        self._new65 = float(self.w[turn].sum())
        # weights: owners by householder age band grow with the population in the band
        self._reweight(y)
        # non-homestead bases: county mix of residential / business / mineral growth; circuit breaker ends
        mix = self.mix.reindex(self.ucty)
        tot = mix[["residential", "business", "mineral"]].sum(axis=1).replace(0, np.nan)
        gm = ((mix["residential"] * g + mix["business"] * e.rate("nonresidential_value", y)
               + mix["mineral"] * e.rate("mineral_value", y)) / tot).fillna(g).to_numpy()
        self.nh = self.nh * (1 + gm)
        if y == BASE_YEAR + 1 and self.law.rule("circuit_breaker").spec.get("expires_after", 9999) < y:
            cb = self.mix["circuit_breaker"]
            sel = ~self.avg & (self.ucls == "school")     # the PVS loss is on the school base; spread to all units by base
            for m_ in [self.ucls == c for c in CLASSES]:
                m_ = m_ & ~self.avg
                s = pd.Series(self.nh[m_]).groupby(self.ucty[m_]).transform("sum").to_numpy()
                add = pd.Series(self.ucty[m_]).map(cb).fillna(0).to_numpy()
                self.nh[m_] = self.nh[m_] + np.where(s > 0, add * self.nh[m_] / np.maximum(s, 1), 0)
            del sel
        self.year = y
        self._tax_year(y, entering=entering)

    def _rows_of(self, idx: np.ndarray) -> np.ndarray:
        if not hasattr(self, "_row_start"):
            self._row_start = np.searchsorted(self.rec, np.arange(self.n))
            self._row_stop = np.searchsorted(self.rec, np.arange(self.n), side="right")
        return np.concatenate([np.arange(self._row_start[i], self._row_stop[i]) for i in idx]) if len(idx) else np.array([], int)

    def _o65_change(self, idx: np.ndarray, old65: np.ndarray) -> None:
        """Local over-65 amounts in or out as status changes; new freezes for new over-65 owners."""
        r = self._rows_of(idx)
        if not len(r):
            return
        now = self.o65[self.rec[r]]
        before = np.repeat(old65, self._row_stop[idx] - self._row_start[idx])
        a = self.amt65[self.upos[r]]
        new = np.maximum(self.of[r] + np.where(now & ~before, a, 0) - np.where(before & ~now, a, 0), 0)
        self.of[r] = np.where(np.isfinite(self.of[r]), new, self.of[r])
        nf = now & ~before & self.freeze_unit[self.upos[r]]
        self.new_freeze[r[nf]] = True

    def _p_death(self, age: np.ndarray | None = None) -> np.ndarray:
        q = self.qx[np.clip((self.age if age is None else age).astype(int), 0, 120)]
        return np.where(self.spouse, q * q, q)

    def _calibrate(self, d: np.ndarray) -> dict:
        """Base sale rates so sales plus deaths reset the target share of homes in the base year."""
        t, li = self.spec["turnover"], self.spec["turnover"]["lock_in"]
        sav = np.where(self.hs, np.maximum(self.mkt - self.ap, 0), 0)
        f = np.maximum(1 + li["per_100k_savings"] * sav / 100_000, li["floor"])
        w = self.w0
        out = {}
        for flag, key in [(True, "homestead_sale_rate"), (False, "nonhomestead_sale_rate")]:
            m = self.orig & (self.hs == flag)
            dd = d if self.demo.get("deaths", True) else np.zeros(self.n)
            out[flag] = max(t[key] - np.average(dd[m], weights=w[m]), 0) / np.average((f * (1 - dd))[m], weights=w[m])
        self.death_share = float(np.average(d[self.orig & self.hs], weights=w[self.orig & self.hs]))
        return out

    def _reweight(self, y: int) -> None:
        live = self.orig | ((self.cohort_year > 0) & (self.cohort_year <= y))
        band = self.hage >= 65
        f = self.pf.loc[y]
        tgt = {"18_64": self.band_t0["18_64"] * f["18_64"], "65_plus": self.band_t0["65_plus"] * f["65_plus"]}
        base = self.w0.copy()
        if self.demo.get("household_growth", True):
            # new owners: growth of the target total beyond last year's, spread over this year's cohort
            total_prev = sum(self.band_t0[b] * self.pf.loc[y - 1][b] for b in tgt)
            new = max(sum(tgt.values()) - total_prev, 0)
            if not hasattr(self, "cohort_w"):
                self.cohort_w = np.zeros(self.n)
            m = self.cohort_year == y
            if m.any():
                self.cohort_w[m] = new * self.cohort_rel[m] / self.cohort_rel[m].sum()
            base = np.where(self.orig, self.w0, np.where(live, self.cohort_w, 0.0))
        else:
            base = np.where(self.orig, self.w0, 0.0)
            tot0 = base.sum()
            s = tot0 / sum(tgt.values())
            tgt = {k: v * s for k, v in tgt.items()}
        w = base.copy()
        if self.demo.get("reweight_by_age", True):
            for b, m in [("18_64", ~band), ("65_plus", band)]:
                s = base[live & m].sum()
                w[live & m] = base[live & m] * tgt[b] / s if s > 0 else 0
        self.w = np.where(live, w, 0.0)
        self.weights[y] = self.w.copy()

    def _record(self, y: int, tax: np.ndarray, taxable: np.ndarray, rate: np.ndarray, live: np.ndarray) -> None:
        n, w = self.n, self.w
        cls_rows = self.X["levy_class"].to_numpy()
        t_rec = np.bincount(self.rec, weights=tax, minlength=n)
        by = {c: np.bincount(self.rec, weights=np.where(cls_rows == c, tax, 0), minlength=n) for c in CLASSES}
        inc = np.maximum(sum(np.nan_to_num(v) for v in self.inc.values()), 0)
        self.history[f"tax_{y}"] = t_rec
        for c in CLASSES:
            self.history[f"tax_{c}_{y}"] = by[c]
        self.history[f"income_{y}"] = inc
        self.history[f"weight_{y}"] = w.copy()
        self.history[f"o65_{y}"] = self.o65.copy()
        self.history[f"age_{y}"] = self.hage.copy()
        hs = self.hs & live
        fz_rec = np.bincount(self.rec, weights=(self.frozen & self.is_school & self.o65[self.rec]).astype(float), minlength=n) > 0
        nh_tax = self.nh * rate / 100
        row = {"year": y, "growth": self.econ.rate("home_value", y) if y > BASE_YEAR else 0.0,
               "school_dpv_growth": getattr(self, "dpv_growth", 0.0) if y > BASE_YEAR else 0.0,
               "state_mcr": round(self.state_mcr, 4),
               "owners": float(w[live].sum()), "homesteads": float(w[hs].sum()),
               "tax_owners": float((t_rec * w).sum()), "tax_total": float((t_rec * w)[hs].sum()),
               "homesteads_65_or_disabled": float(w[hs & self.o65].sum()),
               "owners_65_plus": float(w[live & (self.hage >= 65)].sum()),
               "new_owner_share": float(w[self.cohort_year > 0].sum() / w[live].sum()),
               "homestead_share_reset": float((w * getattr(self, "_reset", np.zeros(n, bool)))[hs].sum() / w[hs].sum()),
               "homestead_share_death": float((w * getattr(self, "_died", np.zeros(n, bool)))[hs].sum() / w[hs].sum()),
               "new_over65_claims": getattr(self, "_new65", 0.0),
               "appraised_to_market": float((self.ap * w)[hs].sum() / (self.mkt * w)[hs].sum()),
               "homesteads_school_frozen": float(w[hs & fz_rec].sum()),
               "avg_income_owner": float(np.average(inc[live], weights=w[live]))}
        row["avg_tax"] = row["tax_total"] / row["homesteads"]
        for c in CLASSES:
            row[f"tax_{c}"] = float((by[c] * w)[hs].sum())
            row[f"tax_owners_{c}"] = float((by[c] * w).sum())
            row[f"nonowner_tax_{c}"] = float(nh_tax[self.ucls == c].sum())
        row["nonowner_tax"] = float(nh_tax.sum())
        row["total_levy"] = row["tax_owners"] + row["nonowner_tax"]
        for c in CLASSES:
            if c != "school":
                m = (self.ucls == c) & (self.mo0 > 0) & ~self.avg
                row[f"rate_index_{c}"] = float(np.average(self.mo[m] / self.mo0[m], weights=np.maximum(self.nh[m] + self.H_prev[m], 1)))
        s2 = self.sof.copy()
        mcr_d = dict(zip(self.cdn[self.ucls == "school"], self.mcr[self.ucls == "school"]))
        s2["mcr"] = s2["cdn"].map(mcr_d).fillna(self.state_mcr) if y > BASE_YEAR else s2["mcr"]
        enrich = (self.sof["mo_rate"] - self.sof["mcr"]).clip(0, 0.17)
        fin = finance(self.sof) if y == BASE_YEAR else finance(s2, value_t2=s2["cdn"].map(self.district_v).to_numpy(), mo_rate=s2["mcr"] + enrich, mcr=s2["mcr"])
        row.update({k: float(fin[k].sum()) for k in ["state_aid", "recapture", "net_state_cost", "levy_mo"]})
        self.rows_out.append(row)

    def run(self, end_year: int | None = None) -> "TxProjection":
        while self.year < (end_year or self.end_year):
            self.step_year()
        return self

    @property
    def summary(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows_out).set_index("year")

    @property
    def household_results(self) -> pd.DataFrame:
        d = pd.DataFrame(self.history)
        d["hid0"], d["cohort_year"], d["homestead"], d["county_fips"] = self.R["hid0"].to_numpy(), self.cohort_year, self.hs, self.county
        return d


def project(o: pd.DataFrame, rows: pd.DataFrame, scenario: str = "central", seed: int = 2026, **kw) -> dict:
    """Yearly summary for one scenario (the results file's format)."""
    p = TxProjection(o, rows, scenario, seed=seed, **kw).run()
    return {"scenario": scenario, "years": p.summary.reset_index().to_dict(orient="records")}


if __name__ == "__main__":
    import json
    import sys
    from ptm.tx.baseline import build_full, compute_tax
    if "--rebuild" in sys.argv:
        ds = ["harris", "dallas", "tarrant", "travis", "collin", "fort_bend", "el_paso", "williamson", "galveston", "bell"]
        o, rows = build_full(ds)
        rows = apply_2026_school_rates(rows)
        o = o.drop(columns=[c for c in o if c.startswith("tax_") or c == "taxable_school"]).join(compute_tax(o, rows, load_law("tx"))[0])
        o.to_parquet(PROC / "tx_baseline_2026.parquet")
        rows.to_parquet(PROC / "tx_baseline_2026_units.parquet")
    o = pd.read_parquet(PROC / "tx_baseline_2026.parquet")
    rows = pd.read_parquet(PROC / "tx_baseline_2026_units.parquet")
    res = {}
    for sc in [a for a in sys.argv[1:] if not a.startswith("--")] or ["central", "low", "high", "stall", "downturn"]:
        r = project(o, rows, sc)
        res[sc] = r
        for y in r["years"]:
            if y["year"] in (2026, 2027, 2031, 2036):
                print(f"{sc:9s} {y['year']}  homestead tax ${y['tax_total'] / 1e9:6.2f}B  owners ${y['tax_owners'] / 1e9:6.2f}B  other property ${y['nonowner_tax'] / 1e9:6.2f}B  "
                      f"avg ${y['avg_tax']:,.0f}  homesteads {y['homesteads'] / 1e6:4.2f}M  65+/dis {y['homesteads_65_or_disabled'] / 1e6:4.2f}M  MCR {y['state_mcr']:.4f}")
    dest = PROC / "results" / "tx_projections.json"
    dest.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print("wrote", dest)
