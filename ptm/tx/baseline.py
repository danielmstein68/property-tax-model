"""Texas 2026 baseline: PUMS owners with homestead status, values, appraised (capped) values, taxing units,
per-unit exemptions, freezes and tax at each unit's rate.

Steps:
  1. survey households aged to 2026 (ptm.tx.survey)
  2. county within the PUMA: drawn with weights = the county's tracts in the PUMA x its homesteads per tract
  3. homestead status: per county, the roll's 2026 homestead count (PVS 2024 x 1.03 where there is no
     roll), filled with owners in order of reported tax / value (lowest first: claimers pay less)
  4. market value: in counties with a roll, homesteads' aged values are quantile-mapped to the roll's
     homestead market values; elsewhere the FHFA-aged survey value stands
  5. disabled veterans' total exemption: the roll's count per county, filled with 70-100% rated veterans
     (and widowed householders, for surviving spouses) reporting $0 tax first, then the rest
  6. donor parcel (counties with a roll): a roll homestead in the same county with the same over-65 /
     disabled status (and total-exemption status), by years since the homestead qualified (survey: years
     in home) and market value rank. The donor gives the appraised/market ratio (10% cap), its taxing
     units with their 2025 rates, and each unit's exemptions split three ways: the state school
     exemptions (recomputed from the law spec, so policies can change them), the local percentage
     exemption (a share of appraised value) and all other exemptions as a fixed dollar amount (local
     over-65/disabled, veterans, and anything else the roll records: appraised - taxable - the other two);
     and freeze ceilings as a ratio to the uncapped tax. Over-65/disabled status of a donor: the roll's
     flags, or (Tarrant removes them) a school exemption above the general one, or a school freeze.
  7. tax by unit: taxable = appraised - state school exemptions - local % - other fixed, floored at 0;
     tax = taxable x rate, capped by any freeze. On the donors themselves this reproduces the roll.
Counties without a roll (steps 6-7) are added next (ptm.tx.units: Comptroller units and rates).
"""

from pathlib import Path

import numpy as np
import pandas as pd

from ptm.gaps import quantile_pick
from ptm.law import load_law
from ptm.tx.nonroll import exemption_stats, nonroll_tax
from ptm.tx.pvs import GROWTH_2024_2026, county_controls, homestead_targets_2026
from ptm.tx.rolls import DISTRICTS, PROC, standard_props, unit_map
from ptm.tx.survey import tx_households

ROOT = Path(__file__).resolve().parents[2]
TRACTS = ROOT / "data" / "raw" / "tract_to_puma_2020.txt"
YIH_BANDS = [-1, 1, 4, 9, 19, 200]          # years since the homestead qualified / years in home
YIH_LABELS = ["<2", "2-4", "5-9", "10-19", "20+"]


def assign_county(h: pd.DataFrame, rng: np.random.Generator, targets: pd.Series) -> pd.Series:
    t = pd.read_csv(TRACTS, dtype=str, encoding="utf-8-sig")
    t = t[t["STATEFP"] == "48"]
    per_county_tracts = t.groupby("COUNTYFP").size()
    w = t.groupby(["PUMA5CE", "COUNTYFP"]).size().rename("tracts").reset_index()
    w["w"] = w["tracts"] * w["COUNTYFP"].map(targets / per_county_tracts).fillna(0)
    out = pd.Series(index=h.index, dtype=object)
    for puma, g in w.groupby("PUMA5CE"):
        idx = h.index[h["PUMA"] == puma]
        if not len(idx):
            continue
        ww = g["w"].to_numpy() if g["w"].sum() > 0 else g["tracts"].to_numpy().astype(float)
        p = ww / ww.sum()
        out.loc[idx] = rng.choice(g["COUNTYFP"].to_numpy(), size=len(idx), p=p)
    return out


def _fill(h: pd.DataFrame, mask: pd.Series, target: float, order: pd.Series) -> pd.Series:
    """Mark households in `mask`, lowest `order` first, until their weight reaches `target`."""
    got = pd.Series(False, index=h.index)
    idx = order[mask].sort_values(kind="stable").index
    cum = h.loc[idx, "WGTP"].cumsum()
    got.loc[idx[(cum - h.loc[idx, "WGTP"] / 2) <= target]] = True
    return got


def _wpct(v: pd.Series, w: pd.Series) -> pd.Series:
    """Weighted mid-point percentile of each value within the group."""
    order = v.sort_values(kind="stable").index
    cw = w.loc[order].cumsum()
    return ((cw - w.loc[order] / 2) / w.sum()).reindex(v.index)


def roll_donors(district: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Roll homesteads (donors) and their units with per-unit exemption parameters."""
    p = standard_props(district)
    p = p[p["homestead"] & (p["market"] > 0)].copy()
    p["yih"] = pd.cut(2026 - p["hs_qualify_yr"].fillna(2026 - 10), YIH_BANDS, labels=YIH_LABELS).astype(str)
    p["ratio"] = (p["appraised"] / p["market"]).clip(0, 1)
    import pyarrow.parquet as pq
    f = PROC / f"{district}_units.parquet"
    have = set(pq.read_schema(f).names)
    want = ["prop_id", "entity_cd", "entity_name", "appraised_value", "taxable_val", "hs_local_amt", "freeze_ceiling"]
    e = pd.read_parquet(f, columns=[c for c in want if c in have])
    e = e[e["prop_id"].isin(set(p["prop_id"]))]
    m = unit_map(district, e.drop_duplicates("entity_cd")[["entity_cd", "entity_name"]])
    e = e.merge(m[["entity_cd", "levy_class", "unit_id", "total_rate"]].dropna(subset=["unit_id"]), on="entity_cd")
    av = e["appraised_value"].where(e["appraised_value"] > 0)
    e["local_pct"] = (e["hs_local_amt"] / av).fillna(0).clip(0, 0.2)
    # over-65/disabled donors: roll flags, else a school exemption beyond the general $140k, or a school freeze
    law = load_law("tx")
    sch = e[e["levy_class"] == "school"]
    beyond = (sch["appraised_value"] - sch["taxable_val"] - sch["hs_local_amt"] - law.rule("school_homestead").get("amount", 2026))
    inferred = set(sch.loc[(beyond >= 50_000) | (sch["freeze_ceiling"] > 0), "prop_id"])
    p["o65"] = p["over65"] | p["disabled"] | (p["prop_id"].isin(inferred) & ~p["dv_total"])
    o65 = e["prop_id"].isin(set(p.loc[p["o65"], "prop_id"]))
    state = np.where(e["levy_class"] == "school", law.rule("school_homestead").get("amount", 2026)
                     + np.where(o65, law.rule("school_over65_disabled").get("amount", 2026), 0), 0.0)
    state = np.minimum(state, e["appraised_value"])
    e["other_fixed"] = np.maximum(0, e["appraised_value"] - e["taxable_val"] - e["hs_local_amt"] - state)
    e.loc[e["taxable_val"] <= 0, "other_fixed"] = np.inf          # fully exempt in this unit (e.g. 100% veteran)
    tax_uncapped = e["taxable_val"] * e["total_rate"] / 100
    e["ceiling_ratio"] = np.where((e["freeze_ceiling"] > 0) & (tax_uncapped > 0), (e["freeze_ceiling"] / tax_uncapped).clip(0, 1), np.nan)
    keep = ["prop_id", "levy_class", "unit_id", "total_rate", "local_pct", "other_fixed", "ceiling_ratio"]
    p["prop_id"] = district + ":" + p["prop_id"].astype(str)        # donor keys: text, unique across districts
    e = e[keep].assign(prop_id=district + ":" + e["prop_id"].astype(str))
    return p, e


def unit_tax(hh: pd.DataFrame, units: pd.DataFrame, law, year: int = 2026) -> pd.DataFrame:
    """hh: one row per household with donor prop_id, appraised, over65 / disabled / dv_total flags.
    Returns tax by levy class per household index."""
    school_hs = law.rule("school_homestead").get("amount", year)
    school_65 = law.rule("school_over65_disabled").get("amount", year)
    x = hh[["donor", "appraised", "over65_or_disabled", "dv_total"]].reset_index(names="hid").merge(
        units, left_on="donor", right_on="prop_id", how="left")
    ap = x["appraised"]
    local = np.where(x["local_pct"] > 0, np.maximum(x["local_pct"] * ap, 5000), 0.0)
    state = np.where(x["levy_class"] == "school", school_hs + np.where(x["over65_or_disabled"], school_65, 0), 0.0)
    taxable = np.maximum(0, ap - state - local - x["other_fixed"].fillna(0))
    taxable = np.where(x["dv_total"], 0.0, taxable)
    tax = taxable * x["total_rate"].fillna(0) / 100
    capped = x["ceiling_ratio"].notna() & x["over65_or_disabled"]
    tax = np.where(capped, tax * x["ceiling_ratio"].fillna(1), tax)
    x["tax"], x["taxable"] = tax, taxable
    t = x.pivot_table(index="hid", columns="levy_class", values="tax", aggfunc="sum", fill_value=0.0)
    t.columns = [f"tax_{c}" for c in t.columns]
    t["tax_total"] = t.sum(axis=1)
    t["taxable_school"] = x[x["levy_class"] == "school"].groupby("hid")["taxable"].sum()
    return t


def build(districts: list[str] | None = None, seed: int = 2026) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    law = load_law("tx")
    h = tx_households()
    o = h[h["tenure"] == "owner"].copy()
    targets = homestead_targets_2026()
    districts = districts or [d for d in DISTRICTS if (PROC / f"{d}_props.parquet").exists()]
    donors = {d: roll_donors(d) for d in districts}
    for d, (p, _) in donors.items():
        targets.loc[DISTRICTS[d][0]] = len(p)
    o["county_fips_tax"] = assign_county(o, rng, targets)
    # 3. homestead status: lowest reported tax / value first
    implied = (o["TAXAMT"].fillna(0) / o["VALP"].where(o["VALP"] > 0)).fillna(1) + rng.random(len(o)) * 1e-9
    o["homestead"] = False
    for c, g in o.groupby("county_fips_tax"):
        o.loc[_fill(o, o["county_fips_tax"] == c, targets.get(c, 0), implied).loc[lambda s: s].index, "homestead"] = True
    o["market"] = o["valp_mv_aged"]
    o["dv_total"] = False
    o["donor"] = pd.Series(None, index=o.index, dtype=object)
    o["appraised"] = o["market"]
    for d, (p, units) in donors.items():
        fips = DISTRICTS[d][0]
        hs = o[(o["county_fips_tax"] == fips) & o["homestead"]]
        if hs.empty:
            continue
        # 4. market values: quantile map to the roll's homestead market values
        pos = quantile_pick(hs["valp_mv_aged"].to_numpy(), hs["WGTP"].to_numpy(), len(p))
        o.loc[hs.index, "market"] = np.sort(p["market"].to_numpy())[pos]
        # 5. veterans' total exemption to the roll's count
        vet = hs["dv_tier"].eq(4) | (hs["widowed"] & hs["over65"])
        order = pd.Series(np.select([hs["TAXAMT"].eq(0) & hs["dv_tier"].eq(4), hs["TAXAMT"].eq(0) & vet, hs["dv_tier"].eq(4)], [0, 1, 2], 3), index=hs.index)
        got = _fill(o.loc[hs.index], vet | hs["TAXAMT"].eq(0), p["dv_total"].sum(), order + rng.random(len(hs)) * 1e-3)
        o.loc[got[got].index, "dv_total"] = True
        # over-65 / disabled to at least the roll's count: the survey's disabled proxy undercounts, so
        # homesteads short of it are filled oldest householder first (El Paso: 68.5k vs 72k flagged)
        o.loc[hs.index, "over65_or_disabled"] = hs["over65_or_disabled"]
        short = p["o65"].sum() - hs.loc[hs["over65_or_disabled"], "WGTP"].sum()
        if short > 0:
            add = _fill(o.loc[hs.index], ~hs["over65_or_disabled"] & ~o.loc[hs.index, "dv_total"], short, -hs["householder_age"] + rng.random(len(hs)) * 1e-3)
            o.loc[add[add].index, "over65_or_disabled"] = True
        hs = o.loc[hs.index]
        # 6. donors by cell: total exemption, over-65/disabled, years band; by market rank
        hs_yih = pd.cut(hs["years_in_home"].fillna(10), YIH_BANDS, labels=YIH_LABELS).astype(str)
        for (dv, o65, yb), g in hs.groupby([hs["dv_total"], hs["over65_or_disabled"], hs_yih]):
            cand = p[(p["dv_total"] == dv) & (p["o65"] == o65) & (p["yih"] == yb)]
            if len(cand) < 30:
                cand = p[(p["dv_total"] == dv) & (p["o65"] == o65)]
            if len(cand) < 30:
                cand = p
            cand = cand.sort_values("market", kind="stable")
            pick = cand.iloc[quantile_pick(g["market"].to_numpy(), g["WGTP"].to_numpy(), len(cand))]
            o.loc[g.index, "donor"] = pick["prop_id"].to_numpy()
            o.loc[g.index, "appraised"] = g["market"].to_numpy() * pick["ratio"].to_numpy()
    o["over65_or_disabled"] = o["over65_or_disabled"] & o["homestead"]
    parts = []
    for d, (p, units) in donors.items():
        hh = o[(o["county_fips_tax"] == DISTRICTS[d][0]) & o["homestead"] & o["donor"].notna()]
        if len(hh):
            parts.append(unit_tax(hh, units, law))
    # counties without a roll: veterans' total exemption from the PVS, structure from pooled roll donors,
    # units and local exemptions from ptm.tx.nonroll
    roll_fips = {DISTRICTS[d][0] for d in donors}
    nr = o["homestead"] & ~o["county_fips_tax"].isin(roll_fips)
    if nr.any() and donors:
        # market values: survey values are more spread out than appraisals (lowest tenth 12-36% below the
        # roll, highest 11-25% above); apply the roll counties' average roll/survey ratio by within-county
        # value percentile, weighted by homesteads
        grid = np.linspace(0.025, 0.975, 20)
        curves, wts = [], []
        for d in donors:
            m = o[(o["county_fips_tax"] == DISTRICTS[d][0]) & o["homestead"]]
            if len(m) < 200:
                continue
            q = _wpct(m["valp_mv_aged"], m["WGTP"])
            srt = np.argsort(q.to_numpy())
            ratio = (m["market"] / m["valp_mv_aged"]).to_numpy()[srt]
            curves.append(np.interp(grid, q.to_numpy()[srt], pd.Series(ratio).rolling(51, center=True, min_periods=1).median().to_numpy()))
            wts.append(m["WGTP"].sum())
        if curves:
            curve = np.average(np.array(curves), axis=0, weights=wts)
            for c, g in o[nr].groupby("county_fips_tax"):
                q = _wpct(g["valp_mv_aged"], g["WGTP"])
                o.loc[g.index, "market"] = g["valp_mv_aged"] * np.interp(q, grid, curve)
        cc = county_controls(2024).set_index("county_fips")
        for c, g in o[nr].groupby("county_fips_tax"):
            mean_mv = np.average(g["market"], weights=g["WGTP"])
            target = cc["ex_dv_total"].get(c, 0) * GROWTH_2024_2026 / max(mean_mv, 1)
            vet = g["dv_tier"].eq(4) | (g["widowed"] & g["over65"])
            order = pd.Series(np.select([g["TAXAMT"].eq(0) & g["dv_tier"].eq(4), g["TAXAMT"].eq(0) & vet, g["dv_tier"].eq(4)], [0, 1, 2], 3), index=g.index)
            got = _fill(g, vet | g["TAXAMT"].eq(0), target, order + rng.random(len(g)) * 1e-3)
            o.loc[got[got].index, "dv_total"] = True
        pool = pd.concat([p for p, _ in donors.values()], ignore_index=True)
        sch = pd.concat([u[u["levy_class"] == "school"] for _, u in donors.values()]).groupby("prop_id")["ceiling_ratio"].first()
        pool["ceiling_ratio"] = pool["prop_id"].map(sch)
        hs = o[nr]
        hs_yih = pd.cut(hs["years_in_home"].fillna(10), YIH_BANDS, labels=YIH_LABELS).astype(str)
        o["ceiling_ratio"] = np.nan
        for (dv, o65, yb), g in hs.groupby([hs["dv_total"], hs["over65_or_disabled"], hs_yih]):
            cand = pool[(pool["dv_total"] == dv) & (pool["o65"] == o65) & (pool["yih"] == yb)]
            if len(cand) < 30:
                cand = pool[(pool["dv_total"] == dv) & (pool["o65"] == o65)]
            cand = cand.sort_values("market", kind="stable")
            pick = cand.iloc[quantile_pick(g["market"].to_numpy(), g["WGTP"].to_numpy(), len(cand))]
            o.loc[g.index, "donor"] = pick["prop_id"].to_numpy()
            o.loc[g.index, "appraised"] = g["market"].to_numpy() * pick["ratio"].to_numpy()
            o.loc[g.index, "ceiling_ratio"] = pick["ceiling_ratio"].to_numpy()
        stats = exemption_stats(donors)
        parts.append(nonroll_tax(o[nr], law, rng, stats))
    if parts:
        o = o.join(pd.concat(parts))
    return o


if __name__ == "__main__":
    import sys
    from ptm.tx.rolls import parcel_tax
    ds = sys.argv[1:] or ["el_paso", "tarrant"]
    o = build(ds)
    for d in ds:
        fips = DISTRICTS[d][0]
        m = o[(o["county_fips_tax"] == fips) & o["homestead"]]
        r = parcel_tax(d)
        w = m["WGTP"]
        print(f"{d}: model {w.sum():,.0f} homesteads ({len(m)} records) vs roll {len(r):,}")
        for c in ["tax_total", "tax_school", "tax_county", "tax_city"]:
            if c in m and c in r:
                print(f"  {c:11s} model {np.average(m[c].fillna(0), weights=w):8,.0f}  roll {r[c].mean():8,.0f}  ratio {np.average(m[c].fillna(0), weights=w) / r[c].mean():.3f}")
        print(f"  market    model {np.average(m.market, weights=w):9,.0f}  roll {r.market.mean():9,.0f};  appraised/market model {np.average(m.appraised, weights=w) / np.average(m.market, weights=w):.3f} roll {r.appraised.sum() / r.market.sum():.3f}")
        print(f"  over-65/disabled model {w[m.over65_or_disabled].sum():,.0f} roll {(r.over65 | r.disabled).sum():,};  dv total model {w[m.dv_total].sum():,.0f} roll {r.dv_total.sum():,}")
