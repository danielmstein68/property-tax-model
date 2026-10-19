"""Yearly millage for projections: each government's rate from Florida's rolled-back rate rules.

The rolled-back rate is last year's levy over this year's taxable value excluding new
construction (s. 200.065(1)). Because last year's levy is last year's rate x last year's taxable
value, the rolled-back rate = last year's rate / g, where g is the growth of the jurisdiction's
existing taxable value. Rules (inputs/fl_projection_assumptions.yaml, `rate_setting`):
  history      each year, each government's rate change is drawn from what Florida governments of
               the same type did in years with similar base growth (EDR ad valorem profiles,
               counties 1996-2025, cities 2009-2025, school districts 1997-2025; RateHistory), then
               capped at cap_multiple x rolled-back except with exceed_cap_probability (2026 law:
               beyond 110% needs a unanimous vote; 1 of 33 counties did in 2026). n draws; the
               central path uses their mean (tax is linear in the rate)
  keep_capped  keep last year's rate, cut to cap_multiple x rolled-back if above it (tested on 2026:
               median error 0%; the 110% tier needs a two-thirds vote under s. 200.065(5)(a) as
               amended 2026)
  rolled_back  the rolled-back rate (revenue-neutral on existing property)
  hold         last year's rate
Applied to the county class (county levies, MSTUs, dependent and independent special districts),
each city's levy, and the school districts' required local effort (RLE); the other school levies
are fixed by statute (0.748 discretionary, up to 1.5 capital) and stay put.

Each jurisdiction's taxable value is tracked in three parts, from the 2026 rolls and Data Book:
  homestead residential      grows like the model's own homestead owners in the county
  non-homestead residential  school: grows with home values (just value). Non-school: the
                             assessment cap (nonhomestead_residential_cap, 10%; Amendment 3: 5%)
                             applied to each county's 2026 roll blocks (scripts/fl_cap_blocks_2026.py):
                             parcels in bands of assessed / just value (the last at just value),
                             each band assessed at most cap x last year and never above its just
                             value; the county's 2025 sold share resets to just value each year
  non-residential (+ TPP)    grows with non-residential values; = county total (Data Book) minus
                             residential (rolls); non-school: the same with nonresidential_cap (TPP
                             moves with the roll blocks); cities use their county's non-residential
                             share and their county's non-school growth
Not modelled yet: the maximum millage tracking in ch. 2026-240, rate increases by referendum or
unanimous vote, and new construction (it doesn't enter rolled-back rates).
"""

import glob
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RULES = {"history", "keep_capped", "rolled_back", "hold"}
_CACHE: dict = {}


def _cached(key, make):
    """Read-only inputs reused across RateSetters in one process (composition, rate history)."""
    if key not in _CACHE:
        _CACHE[key] = make()
    return _CACHE[key]


def _city_key(name) -> str:
    import re
    from ptm.ratemodel import norm
    return norm(re.sub(r"(?i)^(city|town|village) of\s+", "", str(name)))


def composition(base_year: int = 2026, refresh: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Taxable value parts per county (school and non-school) and per city (non-school).
    Cached in data/processed/ (reading 9.8M parcels takes over a minute); refresh=True rebuilds."""
    cache = ROOT / "data" / "processed" / f"rate_composition_{base_year}"
    if not refresh and (cache / "counties.parquet").exists():
        return pd.read_parquet(cache / "counties.parquet"), pd.read_parquet(cache / "cities.parquet")
    c, cities = _composition(base_year)
    cache.mkdir(parents=True, exist_ok=True)
    c.to_parquet(cache / "counties.parquet")
    cities.to_parquet(cache / "cities.parquet")
    return c, cities


def _composition(base_year: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    from ptm.geo import fl_dor_to_fips
    from ptm.millage import county_fips_by_name, district_classes
    from ptm.ratemodel import load_databook, norm

    files = glob.glob(str(ROOT / "data" / "processed" / f"fl_nal_{base_year}" / "co*.parquet"))
    p = pd.concat([pd.read_parquet(f, columns=["CO_NO", "TV_SD", "TV_NSD", "homestead", "TAX_AUTH_CD"])
                   for f in files], ignore_index=True)
    p["county_fips"] = fl_dor_to_fips(p["CO_NO"])
    p["code"] = p["TAX_AUTH_CD"].astype(str).str.strip()
    p["hs"] = p["homestead"].fillna(False).astype(bool)
    res = p.groupby(["county_fips", "hs"])[["TV_SD", "TV_NSD"]].sum().unstack("hs").fillna(0)
    c = pd.DataFrame({
        "hs_school": res[("TV_SD", True)], "nh_school": res[("TV_SD", False)],
        "hs_county": res[("TV_NSD", True)], "nh_county": res[("TV_NSD", False)]})
    db = load_databook()
    fips = {norm(k): v for k, v in county_fips_by_name().items()}
    db["county_fips"] = db["key"].map(fips)
    db = db.dropna(subset=["county_fips"]).set_index("county_fips")
    c["nr_school"] = (db["school_tv_2026"] - c["hs_school"] - c["nh_school"]).clip(lower=0)
    c["nr_county"] = (db["tv_2026"] - c["hs_county"] - c["nh_county"]).clip(lower=0)
    c = c.fillna(0)

    dc = district_classes(base_year - 1, base_year)
    dc = dc[dc["millage_municipal"] > 0][["county_fips", "code", "municipality", "millage_municipal"]]
    pc = p.merge(dc, on=["county_fips", "code"])
    pc["city"] = pc["municipality"].map(_city_key)
    cr = pc.groupby(["county_fips", "city", "hs"])["TV_NSD"].sum().unstack("hs").fillna(0)
    cities = pd.DataFrame({"hs": cr.get(True, 0), "nh": cr.get(False, 0)})
    # the city's rate on the roll (taxable-value weighted over its districts; base_year - 1 rates)
    pc["w"] = pc["TV_NSD"] * pc["millage_municipal"]
    g = pc.groupby(["county_fips", "city"])[["w", "TV_NSD"]].sum()
    cities["rate_roll"] = (g["w"] / g["TV_NSD"].replace(0, np.nan)).reindex(cities.index)
    nr_share = (c["nr_county"] / (c["hs_county"] + c["nh_county"]).replace(0, np.nan)).fillna(0)
    cities["nr"] = (cities["hs"] + cities["nh"]) * cities.index.get_level_values(0).map(nr_share).to_numpy()
    return c, cities


def general_levy_2026(index: pd.Index) -> np.ndarray:
    """Each county's 2026 general levy (BCC / county general, mills), aligned to `index` (county
    FIPS); NaN where not known (Duval: consolidated with Jacksonville, a city levy)."""
    from ptm.millage import county_fips_by_name
    fips = county_fips_by_name()
    norm = lambda n: str(n).lower().replace("st. ", "saint ").replace("st ", "saint ").replace("-", " ").strip()
    by_norm = {norm(k): v for k, v in fips.items()}
    rep = pd.read_csv(ROOT / "data" / "processed" / "baseline_fl_2026_rates_2026_report.csv")
    rep["fips"] = rep["county"].map(lambda n: fips.get(n, by_norm.get(norm(n))))
    return rep.dropna(subset=["fips"]).set_index("fips")["mill_2026"].reindex(index).to_numpy(dtype=float)


def cap_blocks(base_year: int = 2026) -> pd.DataFrame | None:
    """Non-homestead cap blocks by county and band (scripts/fl_cap_blocks_2026.py), or None if not built."""
    path = ROOT / "data" / "processed" / f"fl_cap_blocks_{base_year}.csv"
    if not path.exists():
        return None
    return pd.read_csv(path, dtype={"county_fips": str}).set_index("county_fips")


def school_rle_2026() -> pd.Series:
    """2026-27 required local effort millage by county FIPS (FLDOE, via ratemodel)."""
    from ptm.millage import county_fips_by_name
    from ptm.ratemodel import norm, school_rates_2026

    s = school_rates_2026()
    fips = {norm(k): v for k, v in county_fips_by_name().items()}
    fips.update({"dade": fips.get("miamidade")})
    s["county_fips"] = s["key"].map(fips)
    return s.dropna(subset=["county_fips"]).set_index("county_fips")["rle_millage_2026"]


class RateHistory:
    """Florida rate changes by government type and base growth (scripts/fl_millage_history.py)."""

    def __init__(self, path: Path = ROOT / "data" / "processed" / "millage_changes.parquet", neighbors: int = 60):
        d = pd.read_parquet(path)
        self.neighbors = neighbors
        self.by = {}
        for kind, g in d.groupby("kind"):
            g = g.sort_values("x")
            self.by[kind] = (g["x"].to_numpy(), g["dlm"].to_numpy())

    def draw(self, kind: str, x: np.ndarray, rng: np.random.Generator, n_draws: int) -> np.ndarray:
        """(n_draws, len(x)) log rate changes: for each government, a random percentile of the
        `neighbors` historical government-years of the same kind with the closest base growth."""
        xs, ys = self.by[kind]
        k = min(self.neighbors, len(xs))
        lo = np.clip(np.searchsorted(xs, x) - k // 2, 0, len(xs) - k)
        # each draw is a fixed percentile of the neighbours' rate changes (sorted), so a small
        # change in growth moves a draw only slightly - comparisons of two runs aren't swamped by
        # resampling noise (common random numbers)
        window = np.sort(ys[lo[:, None] + np.arange(k)[None, :]], axis=1)          # (n, k)
        q = rng.random((n_draws, len(x)))
        pos = np.minimum((q * k).astype(int), k - 1)
        return np.take_along_axis(window[None, :, :].repeat(n_draws, axis=0), pos[:, :, None], axis=2)[:, :, 0]


HISTORY_KIND = {"county": "county", "municipal": "municipal", "school_rle": "school"}


def rate_ratio(rule: str, g: np.ndarray, cap_multiple: float) -> np.ndarray:
    """This year's rate / last year's rate, given existing taxable value growth g (fixed rules)."""
    if rule == "hold":
        return np.ones_like(g)
    if rule == "rolled_back":
        return 1 / g
    if rule == "keep_capped":
        return np.minimum(1.0, cap_multiple / g)
    raise ValueError(f"unknown rate rule '{rule}'; choose from {sorted(RULES)}")


class RateSetter:
    """Tracks each jurisdiction's taxable value parts and rates for n_draws rate paths.

    ratio_county / ratio_city: rate now / 2026 rate (mean over draws, by jurisdiction);
    ratio_school: required local effort now / 2026 (mean over draws, by county). The full draws
    are in the *_draws arrays and `paths` (per year) for the Monte Carlo summaries."""

    def __init__(self, settings: dict, base_year: int = 2026, rle_2026: pd.Series | None = None,
                 school_total_2026: pd.Series | None = None):
        self.settings = settings
        for k in HISTORY_KIND:
            if settings[k] not in RULES:
                raise ValueError(f"rate_setting.{k}: '{settings[k]}' not one of {sorted(RULES)}")
        uses_history = any(settings[k] == "history" for k in HISTORY_KIND)
        self.n_draws = int(settings.get("draws", 200)) if uses_history else 1
        self.rng = np.random.default_rng(int(settings.get("seed", 2026)))
        nb = int(settings.get("history_neighbors", 60))
        self.history = _cached(("history", nb), lambda: RateHistory(neighbors=nb)) if uses_history else None
        self.counties, self.cities = _cached(("composition", base_year), lambda: composition(base_year))
        self._c = {k: self.counties[k].to_numpy(dtype=float) for k in self.counties.columns}
        self._y = {k: self.cities[k].to_numpy(dtype=float) for k in ("hs", "nh", "nr")}
        self._city_county = self.cities.index.get_level_values(0).map(
            {k: i for i, k in enumerate(self.counties.index)}).fillna(-1).astype(int).to_numpy()
        nc, ny = len(self.counties), len(self.cities)
        self.county_draws = np.ones((self.n_draws, nc))
        self.city_draws = np.ones((self.n_draws, ny))
        rle = (rle_2026 if rle_2026 is not None else school_rle_2026()).reindex(self.counties.index).fillna(0)
        total = school_total_2026.reindex(self.counties.index).fillna(rle) if school_total_2026 is not None else rle
        self.rle_2026 = rle.to_numpy()
        self.school_fixed = (total - rle).to_numpy()
        self.rle_draws = np.tile(self.rle_2026, (self.n_draws, 1))
        self.city_pos = {k: i for i, k in enumerate(self.cities.index)}   # (county, city) -> position
        self.paths = {}
        blk = _cached(("cap_blocks", base_year), lambda: cap_blocks(base_year))
        self.blocks = None
        if blk is not None:
            self.blocks = {}
            for k in ["nh", "nr"]:      # (county, band) arrays; the last band is at just value
                sub = blk[blk["cls"] == k]
                jv = sub.pivot_table(index="county_fips", columns="band", values="jv", aggfunc="sum").reindex(self.counties.index).fillna(0)
                av = sub.pivot_table(index="county_fips", columns="band", values="av", aggfunc="sum").reindex(jv.index).reindex(columns=jv.columns).fillna(0)
                sold = sub.groupby("county_fips")["sold_share"].first().reindex(jv.index).fillna(0)
                self.blocks[k] = {"jv": jv.to_numpy(float), "av": av.to_numpy(float), "sold": sold.to_numpy(float)}

    @property
    def ratio_county(self) -> pd.Series:
        return pd.Series(self.county_draws.mean(axis=0), index=self.counties.index)

    @property
    def ratio_city(self) -> pd.Series:
        return pd.Series(self.city_draws.mean(axis=0), index=self.cities.index)

    @property
    def ratio_school(self) -> pd.Series:
        with np.errstate(divide="ignore", invalid="ignore"):
            r = np.where(self.rle_2026 > 0, self.rle_draws.mean(axis=0) / self.rle_2026, 1.0)
        return pd.Series(r, index=self.counties.index)

    def city_index(self, county: pd.Series, city: pd.Series) -> np.ndarray:
        """Position of each household's city in ratio_city (-1 if none)."""
        return np.array([self.city_pos.get(k, -1) for k in zip(county, city)])

    def _ratio(self, which: str, g: np.ndarray) -> np.ndarray:
        """(n_draws, n) rate ratios for one year under the configured rule, with the legal cap."""
        rule, cap = self.settings[which], float(self.settings.get("cap_multiple", 1.10))
        if rule != "history":
            return np.tile(rate_ratio(rule, g, cap), (self.n_draws, 1))
        r = np.exp(self.history.draw(HISTORY_KIND[which], np.log(g), self.rng, self.n_draws))
        if which != "school_rle":  # 2026 law: above cap x rolled-back needs a unanimous vote
            exceed = self.rng.random(r.shape) < float(self.settings.get("exceed_cap_probability", 0.03))
            r = np.where(exceed, r, np.minimum(r, cap / g[None, :]))
        return r

    def step(self, hs_growth_school: pd.Series, hs_growth_county: pd.Series,
             home_value_growth: float, nonres_growth: float, year: int | None = None) -> None:
        """Advance one year. hs_growth_* = homestead taxable growth by county FIPS (model; NaN or
        missing counties use the median)."""
        idx = self.counties.index
        self.step_arrays(hs_growth_school.reindex(idx).to_numpy(dtype=float),
                         hs_growth_county.reindex(idx).to_numpy(dtype=float),
                         home_value_growth, nonres_growth, year)

    def _capped_growth(self, k: str, growth: float, cap: float) -> np.ndarray:
        """Advance class k's cap blocks one year; return each county's non-school assessed growth."""
        b = self.blocks[k]
        before = b["av"].sum(axis=1)
        jv = b["jv"] * growth
        av = np.minimum(jv, b["av"] * (1 + cap))
        sold = b["sold"][:, None]
        b["jv"], b["av"] = jv, sold * jv + (1 - sold) * av
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(before > 0, b["av"].sum(axis=1) / before, growth)

    def step_arrays(self, gs: np.ndarray, gc: np.ndarray, home_value_growth: float, nonres_growth: float,
                    year: int | None = None, nc_rates: tuple | None = None,
                    cap_multiple: float | None = None, caps: tuple | None = None,
                    nonhomestead_growth: float | None = None) -> None:
        """step() on arrays aligned to self.counties (NaN = use the median). cap_multiple overrides
        the settings' limit for this year (from the law spec). caps = (non-homestead residential,
        non-residential) assessment caps for non-school levies this year (default 10%). nc_rates = new
        construction as a share of each part (homestead, non-homestead residential,
        non-residential): excluded from this year's rolled-back rates, added to the base after."""
        if cap_multiple is not None:
            self.settings = {**self.settings, "cap_multiple": cap_multiple}
        def fill(g):   # thin or empty homestead bases: the median, or no change if none is known
            g = np.asarray(g, dtype=float)
            med = np.nanmedian(g) if np.isfinite(g).any() else 1.0
            return np.where(np.isfinite(g), g, med)
        gs, gc = fill(gs), fill(gc)
        c, hv, nr = self._c, 1 + home_value_growth, 1 + nonres_growth
        hv = 1 + (home_value_growth if nonhomestead_growth is None else nonhomestead_growth)   # non-homestead homes
        if self.blocks is not None:
            cap_nh, cap_nr = caps if caps is not None else (0.10, 0.10)
            f_nh, f_nr = self._capped_growth("nh", hv, cap_nh), self._capped_growth("nr", nr, cap_nr)
        else:
            f_nh, f_nr = np.full(len(gc), hv), np.full(len(gc), nr)
        new = {"hs_school": c["hs_school"] * gs, "nh_school": c["nh_school"] * hv, "nr_school": c["nr_school"] * nr,
               "hs_county": c["hs_county"] * gc, "nh_county": c["nh_county"] * f_nh, "nr_county": c["nr_county"] * f_nr}
        g_school = (new["hs_school"] + new["nh_school"] + new["nr_school"]) / (c["hs_school"] + c["nh_school"] + c["nr_school"])
        g_county = (new["hs_county"] + new["nh_county"] + new["nr_county"]) / (c["hs_county"] + c["nh_county"] + c["nr_county"])
        g_school = np.where(np.isfinite(g_school), g_school, 1.0)
        g_county = np.where(np.isfinite(g_county), g_county, 1.0)
        rs = self._ratio("school_rle", g_school)
        if self.settings["school_rle"] == "history":
            total_prev = self.school_fixed[None, :] + self.rle_draws
            self.rle_draws = np.maximum(self.rle_draws + total_prev * (rs - 1), 0)
        else:
            self.rle_draws = self.rle_draws * rs
        self.county_draws = self.county_draws * self._ratio("county", g_county)
        if nc_rates is not None:
            nh_, nn_, nr_ = nc_rates
            for k, r in [("hs_school", nh_), ("nh_school", nn_), ("nr_school", nr_),
                         ("hs_county", nh_), ("nh_county", nn_), ("nr_county", nr_)]:
                new[k] = new[k] * (1 + r)
            if self.blocks is not None:   # new construction enters at just value
                for k, r in [("nh", nn_), ("nr", nr_)]:
                    b = self.blocks[k]
                    add = np.asarray(r) * b["jv"].sum(axis=1)
                    b["jv"][:, -1] += add
                    b["av"][:, -1] += add
        self._c = new

        yv, cc = self._y, self._city_county
        gcy = np.where(cc >= 0, gc[np.maximum(cc, 0)], np.nanmedian(gc))
        by_county = lambda f: np.where(cc >= 0, f[np.maximum(cc, 0)], np.nanmedian(f))
        newy = {"hs": yv["hs"] * gcy, "nh": yv["nh"] * by_county(f_nh), "nr": yv["nr"] * by_county(f_nr)}
        before = yv["hs"] + yv["nh"] + yv["nr"]
        with np.errstate(divide="ignore", invalid="ignore"):
            g_city = np.where(before > 0, (newy["hs"] + newy["nh"] + newy["nr"]) / before, 1.0)
        self.city_draws = self.city_draws * self._ratio("municipal", g_city)
        if nc_rates is not None:
            newy = {"hs": newy["hs"] * (1 + nc_rates[0]), "nh": newy["nh"] * (1 + nc_rates[1]),
                    "nr": newy["nr"] * (1 + nc_rates[2])}
        self._y = newy
        c2 = self._c   # taxable value this year by jurisdiction (existing + new construction)
        self.tv = {"county": c2["hs_county"] + c2["nh_county"] + c2["nr_county"],
                   "school": c2["hs_school"] + c2["nh_school"] + c2["nr_school"],
                   "city": newy["hs"] + newy["nh"] + newy["nr"]}
        self.last_growth = {"school": pd.Series(g_school, index=self.counties.index),
                            "county": pd.Series(g_county, index=self.counties.index),
                            "city": pd.Series(g_city, index=self.cities.index)}
        if year is not None:
            self.paths[year] = {"county": self.county_draws.copy(), "city": self.city_draws.copy(),
                                "rle": self.rle_draws.copy(), "tv": {k: v.copy() for k, v in self.tv.items()}}
