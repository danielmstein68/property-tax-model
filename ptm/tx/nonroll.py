"""Taxing units, local exemptions and tax for homesteads in counties without an appraisal roll.

Units (Comptroller 2025 rates, ptm.tx.units), per household:
  county    the household's county (its total rate includes farm-to-market / flood control)
  school    a district drawn by the PVS's 2024 homesteads per district split within the county
  city      in a city with probability = the county's city market value / county market value (at most
            0.95); the city drawn by market value
  college, hospital, special   one combined unit per class: the market-value-weighted average rate
Local exemptions (docs/TX_DECISIONS.md, option A until Daniel decides): by unit class, the roll
counties' typical local percentage (share adopting x mean percentage) and over-65/disabled amount
(mean among over-65 homesteads; other dollar exemptions as their mean among the rest), weighted by homesteads; school districts use their own local-option
loss per homestead from the PVS instead of a percentage. Structure (appraised/market, school freeze
ratio) comes from a pooled roll donor, as in the roll counties.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from ptm.tx.pvs import load_pvs
from ptm.tx.units import load_units

ROOT = Path(__file__).resolve().parents[2]
STATS = ROOT / "data" / "processed" / "tx_local_exemption_stats.csv"
CLASSES = ["county", "city", "college", "hospital", "special"]


def exemption_stats(donor_units: dict[str, tuple[pd.DataFrame, pd.DataFrame]]) -> pd.DataFrame:
    """Typical local exemptions by unit class from the roll counties (homestead-weighted)."""
    rows = []
    for d, (p, u) in donor_units.items():
        u = u.merge(p[["prop_id", "o65", "dv_total"]], on="prop_id")
        u = u[~u["dv_total"]]
        for cls, g in u.groupby("levy_class"):
            fin = g["other_fixed"].replace(np.inf, np.nan)
            rows.append({"district": d, "levy_class": cls, "n": g["prop_id"].nunique(),
                         "local_pct_eff": g["local_pct"].mean(),
                         "o65_fixed": fin[g["o65"]].mean() if g["o65"].any() else 0.0,
                         "base_fixed": fin[~g["o65"]].mean() if (~g["o65"]).any() else 0.0})
    t = pd.DataFrame(rows)
    out = t.groupby("levy_class").apply(lambda g: pd.Series({
        "local_pct_eff": np.average(g["local_pct_eff"], weights=g["n"]),
        "o65_fixed": np.average(g["o65_fixed"].fillna(0), weights=g["n"]),
        "base_fixed": np.average(g["base_fixed"].fillna(0), weights=g["n"])})).reset_index()
    STATS.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(STATS, index=False)
    return out


def county_units(year: int = 2025) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(school district shares by county, cities by county, combined class rates by county)."""
    u = load_units(year)
    pv = load_pvs(2024)
    pv["unit_key"] = pv["cdn"].str[:3] + "-" + pv["cdn"].str[3:] + "-02"
    sch = u[u["levy_class"] == "school"][["unit_key", "cad_id", "total_rate", "name"]]
    s = pv.merge(sch, left_on=["unit_key", "cad_id"], right_on=["unit_key", "cad_id"], how="inner")
    s = s.assign(local_per_hs=(s["LOSS LOCL HMSTD"] / s["homesteads_est"]).where(s["homesteads_est"] > 0).fillna(0))
    school = s[["county_fips", "unit_key", "name", "total_rate", "homesteads_est", "local_per_hs"]]
    cnty = u[u["levy_class"] == "county"][["county_fips", "market_value", "total_rate"]].rename(
        columns={"market_value": "county_mv", "total_rate": "county_rate"})
    city = u[u["levy_class"] == "city"][["county_fips", "unit_key", "name", "market_value", "total_rate"]]
    comb = (u[u["levy_class"].isin(["college", "hospital", "special"])]
            .merge(cnty[["county_fips", "county_mv"]], on="county_fips")
            .assign(w=lambda x: x["total_rate"].fillna(0) * (x["market_value"] / x["county_mv"]).clip(0, 1))
            .groupby(["county_fips", "levy_class"])["w"].sum().unstack(fill_value=0.0))
    comb = comb.join(cnty.set_index("county_fips"), how="outer").fillna(0.0)
    return school, city, comb


def nonroll_tax(hh: pd.DataFrame, law, rng: np.random.Generator, stats: pd.DataFrame, year: int = 2026) -> pd.DataFrame:
    """hh: homesteads in counties without a roll (county_fips_tax, appraised, over65_or_disabled, dv_total,
    ceiling_ratio). Returns tax by levy class, taxable school value and the drawn school district / city."""
    school, city, comb = county_units()
    st = stats.set_index("levy_class").reindex(["school"] + CLASSES).fillna(0.0)   # classes no roll county has: none
    school_hs = law.rule("school_homestead").get("amount", year)
    school_65 = law.rule("school_over65_disabled").get("amount", year)
    out = pd.DataFrame(index=hh.index, columns=["school_unit", "city_unit"], dtype=object)
    sch_rate = pd.Series(0.0, index=hh.index)
    sch_local = pd.Series(0.0, index=hh.index)
    city_rate = pd.Series(0.0, index=hh.index)
    for c, g in hh.groupby("county_fips_tax"):
        s = school[school["county_fips"] == c]
        if len(s) and s["homesteads_est"].sum() > 0:
            k = rng.choice(len(s), size=len(g), p=(s["homesteads_est"] / s["homesteads_est"].sum()).to_numpy())
            out.loc[g.index, "school_unit"] = s["unit_key"].to_numpy()[k]
            sch_rate.loc[g.index] = s["total_rate"].to_numpy()[k]
            sch_local.loc[g.index] = s["local_per_hs"].to_numpy()[k]
        ct = city[city["county_fips"] == c]
        mv = comb.loc[c, "county_mv"] if c in comb.index else 0
        if len(ct) and mv > 0:
            p_in = min(0.95, ct["market_value"].sum() / mv)
            inside = rng.random(len(g)) < p_in
            k = rng.choice(len(ct), size=len(g), p=(ct["market_value"] / ct["market_value"].sum()).to_numpy())
            out.loc[g.index[inside], "city_unit"] = ct["unit_key"].to_numpy()[k][inside]
            city_rate.loc[g.index[inside]] = ct["total_rate"].fillna(0).to_numpy()[k][inside]
    ap = hh["appraised"]
    o65 = hh["over65_or_disabled"]
    res = pd.DataFrame(index=hh.index)

    def taxable(cls, local_pct=None, local_fixed=0.0, state=0.0):
        lp = st.loc[cls, "local_pct_eff"] if local_pct is None else local_pct
        # mean dollar exemptions (lumpy: means, not medians): over-65/disabled and everyone else
        fx = np.where(o65, st.loc[cls, "o65_fixed"], st.loc[cls, "base_fixed"]) if cls in st.index else 0.0
        t = np.maximum(0, ap - state - lp * ap - local_fixed - fx)
        return np.where(hh["dv_total"], 0.0, t)

    tx_s = taxable("school", local_pct=0.0, local_fixed=sch_local, state=school_hs + np.where(o65, school_65, 0))
    tax_s = tx_s * sch_rate / 100
    tax_s = np.where(o65 & hh["ceiling_ratio"].notna(), tax_s * hh["ceiling_ratio"].fillna(1), tax_s)
    res["tax_school"], res["taxable_school"] = tax_s, tx_s
    res["tax_county"] = taxable("county") * hh["county_fips_tax"].map(comb["county_rate"]).fillna(0) / 100
    res["tax_city"] = taxable("city") * city_rate / 100
    for cls in ["college", "hospital", "special"]:
        rate = hh["county_fips_tax"].map(comb[cls]) if cls in comb else 0.0
        res[f"tax_{cls}"] = taxable(cls) * pd.Series(rate, index=hh.index).fillna(0) / 100
    res["tax_total"] = res[[c for c in res if c.startswith("tax_") and c != "tax_total"]].sum(axis=1)
    return res.join(out)
