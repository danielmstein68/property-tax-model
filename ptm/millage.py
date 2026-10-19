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
import re
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


NOT_A_CITY = (r"\b(county|fire|rescue|library|district|dda|mstu|msbu|school|hospital|health|water|children|"
              r"debt|port of|port authority|navigation|inlet|mosquito|drainage|erosion|lighting|road|parks|"
              r"improvement|authority|trust|unit|basin|transit|police|sheriff|fund|services|redevelopment|cra)\b")


NONCITY_NOTE = r"\b(fire|rescue|mstu|msbu|unincorporated|uninc)\b|^\s*county\b"   # Volusia: "County - Westside"


def tacd_municipal_authorities(year: int = 2025) -> dict[str, dict[int, tuple[str, float]]]:
    """Municipal authorities (class 4) from county TACD millage tables that list authorities by number
    (Collier's TBL202 format: CODE, NAME, LY-RATE, RB-RATE, TY-RATE, CLASS). county_fips ->
    {authority number: (city name, this year's rate)}."""
    from ptm.rates import pdf_text

    out = {}
    for county in ["Collier"]:
        f = ROOT / "data" / "raw" / f"fl_rates_{year}" / "tacd" / f"{county}.pdf"
        if not f.exists():
            continue
        auth = {}
        pat = r"^\s*(\d+)\s+(.+?)\s+(\d*\.\d{4})\s+(\d*\.\d{4})\s+(\d*\.\d{4})\s+4\s*$"
        for m in re.finditer(pat, pdf_text(f), re.M):
            name = m.group(2).strip().upper()
            if "CITY" not in name:  # class 4 also holds cities' dependent districts
                continue
            city = name.replace("GENERAL FUND (CITY OF ", "").replace("OPERATING CITY OF ", "")
            city = city.replace("OPERATING ", "").strip(" )")
            city = {"MARCO ISL": "MARCO ISLAND"}.get(city, city)
            auth.setdefault(int(m.group(1)), (city, float(m.group(5))))
        out[county_fips_by_name()[county]] = auth
    return out


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
        s = _re.sub(r"[^A-Z ]", "", s)
        s = _re.sub(r"\bSAINT\b", "ST", s)                 # "Saint Cloud" = "St Cloud"
        s = _re.sub(r"\s+OPERATING$", "", s.strip())       # Volusia's Table 1: "Deltona Operating"
        return _re.sub(r"\s+", " ", s).strip()

    city_mills, county_gov = {}, {}
    strong = set()   # Table 1 names that are certainly cities ("City of X", Volusia's "X Operating")
    exact = {"Palm Beach": "Palm Beach County", "Volusia": "Volusia County General Fund"}
    for county, fips in county_fips_by_name().items():
        t1 = parse_table1(pdf_text(ROOT / "data" / "raw" / f"fl_rates_{year}" / "table1" / f"{county}.pdf"))
        cities = t1[t1["authority"].str.match(r"(?i)^(city|town|village) of ") | t1["authority"].str.match(r"(?i)^[A-Za-z .'-]+ operating$")]
        for _, r in cities.iterrows():
            city_mills[(fips, norm(r["authority"]))] = r["millage_2025"]
            strong.add((fips, norm(r["authority"])))
        # Some counties' Table 1 lists cities by bare name (Palm Beach: "Boca Raton"). Accept bare
        # names that aren't county, school or special-district levies; they only apply where a
        # district's note or parcels' city names that city (and the county-levy check passes).
        bare = t1[~t1["authority"].str.match(r"(?i)^(city|town|village) of ")
                  & ~t1["authority"].str.contains(NOT_A_CITY, case=False, regex=True)]
        for _, r in bare.iloc[1:].iterrows():  # first row is the county government
            city_mills.setdefault((fips, norm(r["authority"])), r["millage_2025"])
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
    named = note.str.extract(r"(?i)\b((?:city|town|village) of [A-Za-z .'-]+?)(?:\s*[\(;,|]|$)")[0]

    def note_name(n: str) -> str:
        """The place a note names: its first segment that isn't about the source ("listed in TACD
        district group ...; Port St Lucie 4.6607 + ..."), cut before rates or "+" ("Lakeland city 5.43
        + ...", "Deltona; components sum to total")."""
        for seg in _re.split(r"[;|]", n):
            seg = seg.strip()
            if not seg or _re.match(r"(?i)(listed in|components|stacked header|column)", seg):
                continue
            seg = _re.split(r"\s+\d|\s\+\s|\s*\(", seg)[0]
            return _re.sub(r"(?i)\s+city$", "", seg).strip()
        return ""
    # unincorporated if the place the note names is ("unincorporated base area"), not if it only
    # mentions the county's unincorporated levies (Polk: "Lakeland city 5.43 + unincorporated-less-MSTU")
    uninc = note.map(note_name).str.contains("uninc", case=False) | note.str.match(r"(?i)\s*uninc")
    # a district note that names a place ("BOCA RATON", "Deltona; ...") names that city too
    named = named.where(named.notna(), note.map(note_name).where(~uninc & (note != "")))
    # a note's bare name counts only if Table 1 lists it as a city ("City of", "Operating"), the note
    # is just that name (Palm Beach: "BOCA RATON"), or the district's parcels carry that city name:
    # Osceola's Table 1 also lists MSBUs by bare name ("Bellalago; components sum to total")
    named_mills = [city_mills.get((f, norm(n))) if isinstance(n, str) and ((f, norm(n)) in strong or norm(n) == norm(full)
                                                                           or (isinstance(c, str) and norm(c) == norm(n))) else None
                   for f, n, c, full in zip(r["county_fips"], named, r["city"], note)]
    mail_mills = [city_mills.get((f, norm(c))) if isinstance(c, str) else None for f, c in zip(r["county_fips"], r["city"])]
    # A district whose description names a fire district, MSTU or unincorporated area, and not the
    # mailing city, is not in that city (Manatee's East Manatee Fire district has Bradenton
    # addresses but is unincorporated).
    # (only the description's name part: some notes are about how the rate file was read)
    name_part = note.str.split(r"[|;]").str[0].where(~note.str.contains("stacked header|column", case=False), "")
    noncity = name_part.str.contains(NONCITY_NOTE, case=False, regex=True)
    mail_mills = [None if nc and isinstance(c, str) and norm(c) not in norm(n) else mm
                  for mm, nc, c, n in zip(mail_mills, noncity, r["city"], note)]
    # Districts described by their authority list (Collier: "authorities 1+6+8+..."): in a city
    # only if a municipal authority (TACD class 4) is in the list; no mailing-city fallback.
    for fips, auth in tacd_municipal_authorities(year).items():
        for i in r.index[(r["county_fips"] == fips) & note.str.startswith("authorities")]:
            nums = {int(x) for x in re.findall(r"\d+", note[i])}
            hit = [auth[a] for a in sorted(nums) if a in auth]
            named.loc[i] = hit[0][0] if hit else None
            named_mills[r.index.get_loc(i)] = hit[0][1] if hit else None
            mail_mills[r.index.get_loc(i)] = None
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
    named_ok = pd.Series(named_mills, index=r.index).notna()
    r["city_source"] = np.where(ok & named_ok, "district note", np.where(ok, "mailing city", ""))
    r["note"] = note
    return r[["county_fips", "code", "municipality", "total_millage", "millage_school", "millage_county",
              "millage_municipal", "millage_special", "city_source", "note"]]


def roll_districts(base_year: int) -> pd.DataFrame:
    """Residential roll parcels with PUMA (or county fallback), homestead, just value, district code."""
    files = glob.glob(str(ROOT / "data" / "processed" / f"fl_nal_{base_year}" / "co*.parquet"))
    cols = ["CO_NO", "CENSUS_BK", "DOR_UC", "JV", "homestead", "TAX_AUTH_CD", "own_state", "own_business"]
    p = pd.concat([pd.read_parquet(f, columns=cols) for f in files], ignore_index=True)
    p = p[p["DOR_UC"].isin(["001", "002", "004", "005", "003", "008"]) & (p["JV"] > 0)]
    p["county_fips"] = fl_dor_to_fips(p["CO_NO"])
    p["PUMA"] = fl_parcel_puma(p)
    p["code"] = p["TAX_AUTH_CD"].astype(str).str.strip()
    # Florida-resident individual owner (not a company, mailing address in Florida)
    from ptm.parcels import out_of_state  # stored own_out_of_state is wrong where the state is spelled out
    p["fl_individual"] = ~out_of_state(p["own_state"]) & ~p["own_business"].fillna(False).astype(bool)
    return p[["county_fips", "PUMA", "homestead", "JV", "code", "fl_individual"]]


def assign_districts(h: pd.DataFrame, base_year: int, rate_year: int = 2025, seed: int = 2026,
                     min_donors: int = 50) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Give each owner (not rented-lot mobile homes) a tax district and its millage; modelled tax.

    Requires assign_exemptions (taxable_sd_<base>, taxable_nsd_<base>).
    Cells: PUMA x homestead x value third (donors: roll parcels in the PUMA, non-homestead ones only if owned by a Florida-resident individual; parcels whose
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
    # Non-homestead owners in PUMS are Florida residents living in the home, so their donors are
    # non-homestead parcels owned by Florida-resident individuals, not second homes of out-of-state
    # owners or company-owned rentals (which over-picked coastal districts such as Marco Island).
    roll_all = roll
    roll = roll[roll["homestead"].fillna(False).astype(bool) | roll["fl_individual"]]
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
    pumas_all = {k: g for k, g in roll_all[roll_all["PUMA"].notna()].groupby(["PUMA", "homestead"])}
    report = []
    for (puma, is_hs, band), idx in o.groupby(["PUMA", "is_hs", "band"]).groups.items():
        g = o.loc[idx]
        donors, level = cells.get((puma, is_hs, band)), "puma x homestead x band"
        if donors is None or len(donors) < min_donors:
            donors, level = pumas.get((puma, is_hs)), "puma x homestead"
        if donors is None or len(donors) < min_donors:  # too few Florida-individual parcels: use all
            donors, level = pumas_all.get((puma, is_hs)), "puma x homestead (all owners)"
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
