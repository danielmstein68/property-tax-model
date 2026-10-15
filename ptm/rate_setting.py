"""Yearly millage for projections: each government's rate from Florida's rolled-back rate rules.

The rolled-back rate is last year's levy over this year's taxable value excluding new
construction (s. 200.065(1)). Because last year's levy is last year's rate x last year's taxable
value, the rolled-back rate = last year's rate / g, where g is the growth of the jurisdiction's
existing taxable value. Rules (inputs/fl_projection_assumptions.yaml, `rate_setting`):
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
  non-homestead residential  grows with home values (school at just value; non-school 10% cap is
                             rarely binding at forecast growth rates)
  non-residential (+ TPP)    grows with non-residential values; = county total (Data Book) minus
                             residential (rolls); cities use their county's non-residential share
Not modelled yet: the maximum millage tracking in ch. 2026-240, rate increases by referendum or
unanimous vote, and new construction (it doesn't enter rolled-back rates).
"""

import glob
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RULES = {"keep_capped", "rolled_back", "hold"}


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
    dc = dc[dc["millage_municipal"] > 0][["county_fips", "code", "municipality"]]
    pc = p.merge(dc, on=["county_fips", "code"])
    pc["city"] = pc["municipality"].map(_city_key)
    cr = pc.groupby(["county_fips", "city", "hs"])["TV_NSD"].sum().unstack("hs").fillna(0)
    cities = pd.DataFrame({"hs": cr.get(True, 0), "nh": cr.get(False, 0)})
    nr_share = (c["nr_county"] / (c["hs_county"] + c["nh_county"]).replace(0, np.nan)).fillna(0)
    cities["nr"] = (cities["hs"] + cities["nh"]) * cities.index.get_level_values(0).map(nr_share).to_numpy()
    return c, cities


def school_rle_2026() -> pd.Series:
    """2026-27 required local effort millage by county FIPS (FLDOE, via ratemodel)."""
    from ptm.millage import county_fips_by_name
    from ptm.ratemodel import norm, school_rates_2026

    s = school_rates_2026()
    fips = {norm(k): v for k, v in county_fips_by_name().items()}
    fips.update({"dade": fips.get("miamidade")})
    s["county_fips"] = s["key"].map(fips)
    return s.dropna(subset=["county_fips"]).set_index("county_fips")["rle_millage_2026"]


def rate_ratio(rule: str, g: np.ndarray, cap_multiple: float) -> np.ndarray:
    """This year's rate / last year's rate, given existing taxable value growth g."""
    if rule == "hold":
        return np.ones_like(g)
    if rule == "rolled_back":
        return 1 / g
    if rule == "keep_capped":
        return np.minimum(1.0, cap_multiple / g)
    raise ValueError(f"unknown rate rule '{rule}'; choose from {sorted(RULES)}")


class RateSetter:
    """Tracks each jurisdiction's taxable value parts and cumulative rate ratios."""

    def __init__(self, settings: dict, base_year: int = 2026):
        self.settings = settings
        for k in ["county", "municipal", "school_rle"]:
            if settings[k] not in RULES:
                raise ValueError(f"rate_setting.{k}: '{settings[k]}' not one of {sorted(RULES)}")
        self.counties, self.cities = composition(base_year)
        self.ratio_county = pd.Series(1.0, index=self.counties.index)
        self.ratio_school = pd.Series(1.0, index=self.counties.index)
        self.ratio_city = pd.Series(1.0, index=self.cities.index)
        self.city_pos = {k: i for i, k in enumerate(self.cities.index)}   # (county, city) -> position

    def city_index(self, county: pd.Series, city: pd.Series) -> np.ndarray:
        """Position of each household's city in ratio_city (-1 if none)."""
        return np.array([self.city_pos.get(k, -1) for k in zip(county, city)])

    def step(self, hs_growth_school: pd.Series, hs_growth_county: pd.Series,
             home_value_growth: float, nonres_growth: float) -> None:
        """Advance one year. hs_growth_* = homestead taxable growth by county FIPS (model)."""
        c, cap = self.counties, float(self.settings.get("cap_multiple", 1.10))
        gs = hs_growth_school.reindex(c.index).fillna(hs_growth_school.median())
        gc = hs_growth_county.reindex(c.index).fillna(hs_growth_county.median())
        new = pd.DataFrame({
            "hs_school": c["hs_school"] * gs, "nh_school": c["nh_school"] * (1 + home_value_growth),
            "nr_school": c["nr_school"] * (1 + nonres_growth),
            "hs_county": c["hs_county"] * gc, "nh_county": c["nh_county"] * (1 + home_value_growth),
            "nr_county": c["nr_county"] * (1 + nonres_growth)}, index=c.index)
        g_school = new[["hs_school", "nh_school", "nr_school"]].sum(axis=1) / c[["hs_school", "nh_school", "nr_school"]].sum(axis=1)
        g_county = new[["hs_county", "nh_county", "nr_county"]].sum(axis=1) / c[["hs_county", "nh_county", "nr_county"]].sum(axis=1)
        self.ratio_school *= rate_ratio(self.settings["school_rle"], g_school.to_numpy(), cap)
        self.ratio_county *= rate_ratio(self.settings["county"], g_county.to_numpy(), cap)
        self.counties = new

        ct = self.cities
        cfips = ct.index.get_level_values(0)
        newc = pd.DataFrame({"hs": ct["hs"] * gc.reindex(cfips).fillna(gc.median()).to_numpy(),
                             "nh": ct["nh"] * (1 + home_value_growth),
                             "nr": ct["nr"] * (1 + nonres_growth)}, index=ct.index)
        g_city = newc.sum(axis=1) / ct.sum(axis=1).replace(0, np.nan)
        self.ratio_city *= rate_ratio(self.settings["municipal"], g_city.fillna(1).to_numpy(), cap)
        self.cities = newc
        self.last_growth = {"school": g_school, "county": g_county, "city": g_city}
