"""Tax districts and rates for households, and modelled tax.

Rates (2025 final, the latest published; swap in 2026 when DOR posts it):
  inputs/fl_district_rates_<year>/<County>.csv  code -> total millage (and school, where shown)
  inputs/fl_school_millage_<year>.csv           countywide school millage (FLDOE)
Non-school millage = district total - countywide school millage.

PUMS households don't know their tax district, only their PUMA. Each owner gets the district of
a real roll parcel in the same PUMA x homestead status x value third. Within that cell, donors
are handed out in order of millage and households in order of the rate implied by their
reported tax (households paying more per dollar of taxable value are likely in higher-rate
districts, e.g. cities with their own levy); where reported tax isn't usable, order is random.
"""

import csv
import glob
from pathlib import Path

import numpy as np
import pandas as pd

from ptm.geo import fl_dor_to_fips, fl_parcel_puma
from ptm.gaps import quantile_pick

ROOT = Path(__file__).resolve().parents[1]


def county_fips_by_name() -> dict[str, str]:
    """County name (as used in rate files) -> 3-digit FIPS, via the parcel manifest's DOR numbers."""
    out = {}
    with open(ROOT / "manifests" / "fl_nal_2026.csv") as fh:
        for r in csv.DictReader(fh):
            name = {"Dade": "Miami-Dade", "Saint Licie": "Saint Lucie"}.get(r["county"], r["county"])
            out[name] = fl_dor_to_fips(pd.Series([int(r["co_no"])])).iloc[0]
    return out


def load_rates(year: int = 2025) -> pd.DataFrame:
    """District rates for all counties with a rate file: county_fips, code, total, school, nonschool."""
    fips = county_fips_by_name()
    school = pd.read_csv(ROOT / "inputs" / f"fl_school_millage_{year}.csv")
    school = dict(zip(school["county"], school["total"]))
    frames = []
    for f in glob.glob(str(ROOT / "inputs" / f"fl_district_rates_{year}" / "*.csv")):
        county = Path(f).stem
        d = pd.read_csv(f, dtype={"code": str})
        d["county"], d["county_fips"] = county, fips.get(county)
        d["school_millage"] = school.get(county, np.nan)
        frames.append(d)
    r = pd.concat(frames, ignore_index=True)
    r["code"] = r["code"].str.strip()
    r = r.rename(columns={"total_millage_2025": "total_millage"})
    r["nonschool_millage"] = r["total_millage"] - r["school_millage"]
    return r[["county", "county_fips", "code", "total_millage", "school_millage", "nonschool_millage", "confidence"]]


def district_classes(year: int = 2025, base_year: int = 2026) -> pd.DataFrame:
    """Split each district's millage into the law spec's levy classes.

    school    = countywide school millage (FLDOE)
    municipal = the city's adopted millage (DOR Table 1) if the district is in a city, else 0.
                A district's city = the most common PHY_CITY of its parcels, accepted only if it
                matches a Table 1 city and the remainder (total - school - city) is at least the
                county government's millage, which every district pays. This rejects
                unincorporated areas with city mailing addresses (e.g. ORG37 with Orlando
                addresses would leave 3.18 mills for the county vs Orange's 4.43).
    county    = the rest (county levies, dependent districts and MSTUs, and — for now —
                independent special districts and water management districts)
    special   = 0 for now (independent districts aren't broken out per district in statewide data;
                only senior exemptions treat county and special differently, a small effect).
    """
    import re as _re
    from ptm.rates import parse_table1, pdf_text

    rates = load_rates(year)
    files = glob.glob(str(ROOT / "data" / "processed" / f"fl_nal_{base_year}" / "co*.parquet"))
    p = pd.concat([pd.read_parquet(f, columns=["CO_NO", "TAX_AUTH_CD", "PHY_CITY"]) for f in files], ignore_index=True)
    p["county_fips"] = fl_dor_to_fips(p["CO_NO"])
    p["code"] = p["TAX_AUTH_CD"].astype(str).str.strip()
    p["city"] = p["PHY_CITY"].fillna("").str.upper().str.strip()
    top = (p.groupby(["county_fips", "code", "city"]).size().rename("n").reset_index()
            .sort_values("n", ascending=False).drop_duplicates(["county_fips", "code"]))

    def norm(s: str) -> str:
        s = s.upper()
        s = _re.sub(r"^(CITY|TOWN|VILLAGE) OF\s+", "", s)
        return _re.sub(r"[^A-Z ]", "", s).strip()

    city_mills, county_gov = {}, {}
    exact = {"Palm Beach": "Palm Beach County", "Volusia": "Volusia County General Fund"}
    for county, fips in county_fips_by_name().items():
        t1 = parse_table1(pdf_text(ROOT / "data" / "raw" / f"fl_rates_{year}" / "table1" / f"{county}.pdf"))
        cities = t1[t1["authority"].str.match(r"(?i)^(city|town|village) of ")]
        for _, r in cities.iterrows():
            city_mills[(fips, norm(r["authority"]))] = r["millage_2025"]
        if county in exact:
            g = t1[t1["authority"] == exact[county]]
        elif county == "Duval":  # consolidated: lowest general-government levy
            g = t1[t1["authority"].str.contains("General G", case=False)].sort_values("millage_2025")
        else:
            g = t1[t1["authority"].str.contains(r"BCC|Board of County|County Commission", case=False)]
        county_gov[fips] = float(g["millage_2025"].iloc[0]) if len(g) else 0.0

    r = rates.merge(top[["county_fips", "code", "city"]], on=["county_fips", "code"], how="left")
    # District names from the rate files' notes take priority over parcels' mailing city:
    # "unincorporated" -> no city; "City/Town/Village of X" matching Table 1 -> that city.
    notes = {}
    for f in glob.glob(str(ROOT / "inputs" / f"fl_district_rates_{year}" / "*.csv")):
        d = pd.read_csv(f, dtype={"code": str})
        fips = county_fips_by_name().get(Path(f).stem)
        for code, note in zip(d["code"].str.strip(), d["note"].fillna("")):
            notes[(fips, code)] = note
    note = pd.Series([notes.get((f, c), "") for f, c in zip(r["county_fips"], r["code"])], index=r.index)
    uninc = note.str.contains("uninc", case=False)
    named = note.str.extract(r"(?i)\b((?:city|town|village) of [A-Za-z .'-]+?)(?:\s*[\(;,|]|$)")[0]
    named_mills = [city_mills.get((f, norm(n))) if isinstance(n, str) else None for f, n in zip(r["county_fips"], named)]
    mail_mills = [city_mills.get((f, norm(c))) if isinstance(c, str) else None for f, c in zip(r["county_fips"], r["city"])]
    r["city_millage"] = [nm if nm is not None else mm for nm, mm in zip(named_mills, mail_mills)]
    r.loc[uninc, "city_millage"] = None
    r["city"] = np.where(pd.notna(named) & pd.Series(named_mills, index=r.index).notna(), named.fillna(""), r["city"])
    r["millage_school"] = r["school_millage"]
    rest = r["total_millage"] - r["millage_school"]
    # every district pays the county government's levy, so a city match must leave at least that
    ok = r["city_millage"].notna() & (rest - r["city_millage"] >= r["county_fips"].map(county_gov) - 0.001)
    r["millage_municipal"] = np.where(ok, r["city_millage"], 0.0)
    r["millage_special"] = 0.0
    r["millage_county"] = rest - r["millage_municipal"]
    r["municipality"] = np.where(ok, r["city"], "")
    return r[["county_fips", "code", "municipality", "total_millage", "millage_school", "millage_county",
              "millage_municipal", "millage_special"]]


def roll_districts(base_year: int) -> pd.DataFrame:
    """Residential roll parcels with PUMA (or county fallback), homestead, just value, district code."""
    files = glob.glob(str(ROOT / "data" / "processed" / f"fl_nal_{base_year}" / "co*.parquet"))
    p = pd.concat([pd.read_parquet(f, columns=["CO_NO", "CENSUS_BK", "DOR_UC", "JV", "homestead", "TAX_AUTH_CD"])
                   for f in files], ignore_index=True)
    p = p[p["DOR_UC"].isin(["001", "002", "004", "005", "003", "008"]) & (p["JV"] > 0)]
    p["county_fips"] = fl_dor_to_fips(p["CO_NO"])
    p["PUMA"] = fl_parcel_puma(p)
    p["code"] = p["TAX_AUTH_CD"].astype(str).str.strip()
    return p[["county_fips", "PUMA", "homestead", "JV", "code"]]


def assign_districts(h: pd.DataFrame, base_year: int, rate_year: int = 2025, seed: int = 2026,
                     min_donors: int = 50) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Give each owner (not rented-lot mobile homes) a tax district and its millage; modelled tax.

    Requires assign_exemptions (taxable_sd_<base>, taxable_nsd_<base>).
    Cells: PUMA x homestead x value third (donors: roll parcels in the PUMA; parcels whose
    CENSUS_BK doesn't map to a PUMA are pooled by county and used for the county's PUMAs when the
    PUMA cell is thin). Adds county_fips_tax, tax_district, school_millage, nonschool_millage,
    tax_school_<base>, tax_nonschool_<base>, tax_model_<base> (2025 rates on 2026 taxable values).
    """
    from ptm.gaps import _bands

    rng = np.random.default_rng(seed)
    rates = load_rates(rate_year).set_index(["county_fips", "code"])
    roll = roll_districts(base_year)
    roll = roll.join(rates[["total_millage"]], on=["county_fips", "code"])
    roll = roll[roll["total_millage"].notna()]
    pct = roll.groupby(["PUMA", "homestead"])["JV"].rank(pct=True, method="first")
    roll["band"] = pd.cut(pct, [0, 1 / 3, 2 / 3, 1.0001], labels=["low", "mid", "high"]).astype(str)

    out = h.copy()
    owner = (out["tenure"] == "owner") & ~out["mh_rented_lot"].fillna(False).astype(bool)
    o = out[owner].copy()
    o["PUMA"] = o["PUMA"].astype(str).str.zfill(5)
    o["is_hs"] = (o["homestead"] == True).to_numpy()  # noqa: E712
    o["band"] = ""
    for _, idx in o.groupby(["PUMA", "is_hs"]).groups.items():
        o.loc[idx, "band"] = _bands(o.loc[idx, "valp_jv_cal"], o.loc[idx, "WGTP"])
    taxable = 0.37 * o[f"taxable_sd_{base_year}"] + 0.63 * o[f"taxable_nsd_{base_year}"]
    usable = (o["TAXAMT"] > 0) & ~o["flag_topcode_taxamt"] & (taxable > 1000)
    implied = (o["taxamt_aged"] / taxable).where(usable)
    o["_order"] = implied.groupby(o["PUMA"]).rank(pct=True).fillna(pd.Series(rng.random(len(o)), index=o.index))

    cells = {k: g for k, g in roll[roll["PUMA"].notna()].groupby(["PUMA", "homestead", "band"])}
    pumas = {k: g for k, g in roll[roll["PUMA"].notna()].groupby(["PUMA", "homestead"])}
    report = []
    for (puma, is_hs, band), idx in o.groupby(["PUMA", "is_hs", "band"]).groups.items():
        g = o.loc[idx]
        donors, level = cells.get((puma, is_hs, band)), "puma x homestead x band"
        if donors is None or len(donors) < min_donors:
            donors, level = pumas.get((puma, is_hs)), "puma x homestead"
        if donors is None or len(donors) < min_donors:
            report.append({"PUMA": puma, "homestead": is_hs, "band": band, "level": "no donors",
                           "records": len(g)})
            continue
        donors = donors.sort_values("total_millage", kind="stable")
        pos = quantile_pick(g["_order"].to_numpy(), g["WGTP"].to_numpy(), len(donors))
        pick = donors.iloc[pos]
        o.loc[idx, "county_fips_tax"] = pick["county_fips"].to_numpy()
        o.loc[idx, "tax_district"] = pick["code"].to_numpy()
        report.append({"PUMA": puma, "homestead": is_hs, "band": band, "level": level, "records": len(g),
                       "donors": len(donors)})

    o = o.join(rates[["school_millage", "nonschool_millage"]], on=["county_fips_tax", "tax_district"])
    classes = district_classes(rate_year, base_year).set_index(["county_fips", "code"])
    o = o.join(classes[["municipality", "millage_school", "millage_county", "millage_municipal", "millage_special"]],
               on=["county_fips_tax", "tax_district"])
    cols = ["county_fips_tax", "tax_district", "school_millage", "nonschool_millage", "municipality",
            "millage_school", "millage_county", "millage_municipal", "millage_special"]
    for c in cols:
        out.loc[o.index, c] = o[c]
    out = assign_city_senior_exemptions(out, base_year, rng)
    out = engine_tax(out, base_year)
    return out, pd.DataFrame(report)


def assign_city_senior_exemptions(h: pd.DataFrame, base_year: int, rng) -> pd.DataFrame:
    """City versions of the senior exemptions (codes 04, 40), matched to roll counts by area.

    Candidates: homesteads in a city district that pass the same age/income (and, for the
    long-term version, residence and value) test as the county version (elig_* from
    ptm.exemptions) — not only those with the county version, since some cities adopt the
    exemption where the county hasn't. Chosen at random within each county group until the roll's
    count of parcels with the city exemption is reached. Amount: the roll's median city exemption
    (code 04) for the county group, statewide median where none.
    """
    from ptm.exemptions import roll_exemption_counts  # noqa: F401  (kept for the county version)
    from ptm.geo import parcel_area
    from ptm.link import _fill_by_priority

    rows, amounts = [], []
    for f in glob.glob(str(ROOT / "data" / "processed" / f"fl_nal_{base_year}" / "co*.parquet")):
        d0 = pd.read_parquet(f)
        d0 = d0[d0["homestead"]]
        if d0.empty:
            continue
        for a, d in d0.groupby(parcel_area(d0)):  # one area per county, except split counties
            n04 = int((d["EXMPT_04"].fillna(0) > 0).sum()) if "EXMPT_04" in d else 0
            n40 = int((d["EXMPT_40"].fillna(0) > 0).sum()) if "EXMPT_40" in d else 0
            rows.append({"area": a, "lowinc_city": n04, "longterm_city": n40})
            if "EXMPT_04" in d:
                amounts.append(pd.DataFrame({"area": a, "amount": d.loc[d["EXMPT_04"] > 0, "EXMPT_04"]}))
    counts = pd.DataFrame(rows).groupby("area").sum()
    am = pd.concat(amounts) if amounts else pd.DataFrame(columns=["area", "amount"])
    amount_by_area = am.groupby("area")["amount"].median()
    amount_state = float(am["amount"].median()) if len(am) else 0.0

    out = h.copy()
    out["_rand"] = rng.random(len(out))
    in_city = out["millage_municipal"].fillna(0) > 0
    for flag, elig_col, target in [("ex_senior_lowinc_city", "elig_senior_lowinc", "lowinc_city"),
                                   ("ex_senior_longterm_city", "elig_senior_longterm", "longterm_city")]:
        elig = in_city & out[elig_col].fillna(False).astype(bool)
        out[flag] = _fill_by_priority(out, elig, counts[target], priority=["_rand"], ascending=[True], group="value_area")
    city_amount = out["value_area"].map(amount_by_area).fillna(amount_state)
    out["ex_senior_city_amount"] = np.where(out["ex_senior_lowinc_city"], city_amount, 0.0)
    return out.drop(columns="_rand")


def engine_tax(h: pd.DataFrame, base_year: int) -> pd.DataFrame:
    """Taxable value by levy class from the rules engine (ptm.engine, law spec), then tax.

    Assessed value: school = av_sd_<base>; county, municipal, special = av_nsd_<base> (the
    non-homestead 10% cap applies to all non-school levies alike). Adds taxable_<class>_<base>
    and tax_<class>_<base> for each class, and tax_model_<base> = their sum. Owners only (not
    rented-lot mobile homes).
    """
    from ptm.engine import apply_exemptions
    from ptm.law import load_law

    law = load_law()
    out = h.copy()
    owner = (out["tenure"] == "owner") & ~out["mh_rented_lot"].fillna(False).astype(bool)
    u = out[owner].copy()
    u["homestead"] = (u["homestead"] == True)  # noqa: E712
    u["av_school"] = u[f"av_sd_{base_year}"]
    for c in ["county", "municipal", "special"]:
        u[f"av_{c}"] = u[f"av_nsd_{base_year}"]
    taxable = apply_exemptions(u, law, base_year)
    total = 0
    for c in law.levy_classes:
        out.loc[u.index, f"taxable_{c}_{base_year}"] = taxable[f"taxable_{c}"].to_numpy()
        tax = out[f"taxable_{c}_{base_year}"] * out[f"millage_{c}"] / 1000
        out[f"tax_{c}_{base_year}"] = tax
        total = total + tax.fillna(0)
    out[f"tax_model_{base_year}"] = total.where(owner)
    out.attrs["engine_missing_flags"] = sorted(getattr(taxable, "attrs", {}).get("missing", []))
    return out
