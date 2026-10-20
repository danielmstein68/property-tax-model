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
    """(school district shares by county, cities by county, county rows and combined class rates by county)."""
    u = load_units(year)
    pv = load_pvs(2024)
    pv["unit_key"] = pv["cdn"].str[:3] + "-" + pv["cdn"].str[3:] + "-02"
    sch = u[u["levy_class"] == "school"][["unit_key", "unit_id", "county_fips", "cad_id", "mo_rate", "is_rate", "name"]]
    s = pv.merge(sch, on=["unit_key", "cad_id"], how="inner", suffixes=("", "_u"))
    s = s.assign(local_per_hs=(s["LOSS LOCL HMSTD"] / s["homesteads_est"]).where(s["homesteads_est"] > 0).fillna(0))
    school = s[["county_fips", "unit_key", "unit_id", "name", "mo_rate", "is_rate", "homesteads_est", "local_per_hs"]]
    cnty = u[u["levy_class"] == "county"].drop_duplicates("county_fips")
    cnty = cnty.assign(c_is=cnty["is_rate"].fillna(0), c_mo=cnty["total_rate"].fillna(0) - cnty["is_rate"].fillna(0))
    city = u[u["levy_class"] == "city"][["county_fips", "unit_key", "unit_id", "name", "market_value", "mo_rate", "is_rate"]]
    comb = (u[u["levy_class"].isin(["college", "hospital", "special"])]
            .merge(cnty[["county_fips", "market_value"]].rename(columns={"market_value": "county_mv"}), on="county_fips")
            .assign(w=lambda x: x["total_rate"].fillna(0) * (x["market_value"] / x["county_mv"]).clip(0, 1))
            .groupby(["county_fips", "levy_class"])["w"].sum().unstack(fill_value=0.0))
    comb = cnty.set_index("county_fips")[["unit_id", "market_value", "c_mo", "c_is"]].rename(
        columns={"unit_id": "county_unit", "market_value": "county_mv"}).join(comb, how="left").fillna(0.0)
    return school, city, comb


def nonroll_rows(hh: pd.DataFrame, rng: np.random.Generator, stats: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """hh: homesteads in counties without a roll (county_fips_tax, over65_or_disabled, ceiling_ratio).
    Returns (household x unit rows in ptm.tx.baseline.ROW_COLS form, the drawn school district and city)."""
    school, city, comb = county_units()
    st = stats.set_index("levy_class").reindex(["school"] + CLASSES).fillna(0.0)   # classes no roll county has: none
    o65 = hh["over65_or_disabled"].to_numpy()
    fixed = lambda cls: np.where(o65, st.loc[cls, "o65_fixed"], st.loc[cls, "base_fixed"])
    drawn = pd.DataFrame(index=hh.index, columns=["school_unit", "city_unit"], dtype=object)
    parts = []

    def add(idx, cls, unit_id, mo, is_, local_pct, other_fixed, ceiling=np.nan):
        parts.append(pd.DataFrame({"hid": idx, "levy_class": cls, "unit_id": unit_id, "mo_rate": mo, "is_rate": is_,
                                   "local_pct": local_pct, "other_fixed": other_fixed, "ceiling_ratio": ceiling, "hs_share": 1.0}))

    for c, g in hh.groupby("county_fips_tax"):
        gi = g.index.to_numpy()
        go65 = g["over65_or_disabled"].to_numpy()
        fx = lambda cls: np.where(go65, st.loc[cls, "o65_fixed"], st.loc[cls, "base_fixed"])
        s = school[school["county_fips"] == c]
        if len(s) and s["homesteads_est"].sum() > 0:
            k = rng.choice(len(s), size=len(g), p=(s["homesteads_est"] / s["homesteads_est"].sum()).to_numpy())
            drawn.loc[gi, "school_unit"] = s["unit_id"].to_numpy()[k]
            add(gi, "school", s["unit_id"].to_numpy()[k], s["mo_rate"].to_numpy()[k], s["is_rate"].to_numpy()[k], 0.0,
                s["local_per_hs"].to_numpy()[k] + fx("school"), g["ceiling_ratio"].to_numpy())
        if c in comb.index:
            r = comb.loc[c]
            add(gi, "county", r["county_unit"], r["c_mo"], r["c_is"], st.loc["county", "local_pct_eff"], fx("county"))
            for cls in ["college", "hospital", "special"]:
                if cls in comb and r.get(cls, 0) > 0:
                    add(gi, cls, f"avg:{c}:{cls}", r[cls], 0.0, st.loc[cls, "local_pct_eff"], fx(cls))
            ct = city[city["county_fips"] == c]
            if len(ct) and r["county_mv"] > 0:
                p_in = min(0.95, ct["market_value"].sum() / r["county_mv"])
                inside = rng.random(len(g)) < p_in
                k = rng.choice(len(ct), size=len(g), p=(ct["market_value"] / ct["market_value"].sum()).to_numpy())
                if inside.any():
                    drawn.loc[gi[inside], "city_unit"] = ct["unit_id"].to_numpy()[k][inside]
                    add(gi[inside], "city", ct["unit_id"].to_numpy()[k][inside], ct["mo_rate"].fillna(0).to_numpy()[k][inside],
                        ct["is_rate"].fillna(0).to_numpy()[k][inside], st.loc["city", "local_pct_eff"], fx("city")[inside])
    rows = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    return rows, drawn
