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


def local_exemptions() -> pd.DataFrame:
    """Collected local-option exemptions (inputs/tx_local_exemptions_*.csv, from appraisal districts'
    published unit tables) matched to the Comptroller's units: unit_id, local_pct, over65_amount,
    disabled_amount. Units not listed keep the typical values (exemption_stats)."""
    import glob
    import difflib
    from ptm.tx.pvs import county_fips_by_name
    from ptm.tx.rolls import _norm
    files = sorted(glob.glob(str(ROOT / "inputs" / "tx_local_exemptions_*.csv")))
    if not files:
        return pd.DataFrame(columns=["unit_id", "levy_class", "county_fips", "local_pct", "over65_amount", "disabled_amount"])
    x = pd.concat([pd.read_csv(f, dtype=str) for f in files], ignore_index=True)
    x = x[x["county"].notna() & x["unit_name"].notna()].copy()
    x["county_fips"] = county_fips_by_name(x["county"].str.strip())
    typ = {"county": "county", "city": "city", "school": "school", "isd": "school", "college": "college", "hospital": "hospital"}
    x["levy_class"] = x["unit_type"].str.strip().str.lower().map(typ).fillna("special")
    for c in ["local_pct", "local_min", "over65_amount", "disabled_amount"]:
        x[c] = pd.to_numeric(x[c].astype(str).str.replace(r"[$,%\s]", "", regex=True), errors="coerce").fillna(0)
    x.loc[x["local_pct"] > 1, "local_pct"] = x.loc[x["local_pct"] > 1, "local_pct"] / 100     # "20" -> 0.20
    x["local_pct"] = x["local_pct"].clip(0, 0.2)
    u = load_units()
    out = []
    for (c, cls), g in x.groupby(["county_fips", "levy_class"]):
        cand = u[(u["county_fips"] == c) & (u["levy_class"] == cls)]
        if cand.empty:
            continue
        norms = cand["name"].map(_norm).tolist()
        for _, r in g.iterrows():
            if cls == "county" or len(cand.drop_duplicates("unit_key")) == 1:     # the only unit of its class
                i = 0
            else:
                sc = [difflib.SequenceMatcher(None, _norm(r["unit_name"]), n).ratio() for n in norms]
                i = int(np.argmax(sc))
                if sc[i] < 0.6:
                    continue
            # a flat-dollar homestead exemption with no percentage (Guadalupe: San Marcos $15,000)
            flat = r["local_min"] if r["local_pct"] == 0 else 0.0
            out.append({"unit_id": cand["unit_id"].iloc[i], "levy_class": cls, "county_fips": c, "local_pct": r["local_pct"], "flat": flat,
                        "over65_amount": r["over65_amount"], "disabled_amount": r["disabled_amount"]})
    return pd.DataFrame(out).drop_duplicates("unit_id")


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
    # collected unit-by-unit exemptions where we have them (by unit, or for the averaged college / hospital
    # rows, the county's own unit of that class)
    loc = local_exemptions()
    if len(rows) and len(loc) and stats["local_pct_eff"].sum() > 0:     # not for non-homestead owners
        o65 = rows["hid"].map(hh["over65_or_disabled"]).fillna(False).to_numpy()
        dis = rows["hid"].map(hh["disabled"] if "disabled" in hh else hh["over65_or_disabled"] & False).fillna(False).to_numpy()
        by_unit = loc.set_index("unit_id")
        avg_key = loc[loc["levy_class"].isin(["college", "hospital"])].assign(k=lambda d: "avg:" + d["county_fips"] + ":" + d["levy_class"]).drop_duplicates("k").set_index("k")
        # school districts keep their own PVS local-option loss; other units take the collected % and amounts
        nonschool = (rows["levy_class"] != "school").to_numpy()
        for src in (by_unit, avg_key):
            m = rows["unit_id"].isin(src.index).to_numpy() & nonschool
            if not m.any():
                continue
            r = src.reindex(rows.loc[m, "unit_id"])
            rows.loc[m, "local_pct"] = r["local_pct"].to_numpy()
            amt = np.where(dis[m] & (r["disabled_amount"].to_numpy() > 0), r["disabled_amount"].to_numpy(), r["over65_amount"].to_numpy())
            rows.loc[m, "other_fixed"] = np.where(o65[m], amt, 0.0) + r["flat"].fillna(0).to_numpy()
    return rows, drawn
