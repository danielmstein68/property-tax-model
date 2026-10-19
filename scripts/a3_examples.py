"""Amendment 3 example households -> data/processed/results/fl_a3_examples.json

Usage:
    python scripts/a3_examples.py             # uses cached government rate paths if present
    python scripts/a3_examples.py --refresh   # re-runs the projections for the rate paths

Six typical cases, each a home in a named place, run through the rules engine (ptm.engine) year
by year under current law and under Amendment 3 (as written, and with the five-year rule struck
down). Values come from the 2026 parcel rolls (medians and percentiles for the place and home
type); tax rates are the place's real 2026 district rates, moved each year by the same rate paths
the projection uses:
  - current law, and Amendment 3 with rates unchanged: current law's rate path
  - Amendment 3, local governments replace the revenue: the revenue-neutral run (10-mill cap,
    no state reimbursement), as on the page
Property values grow at the central scenario's rates (homes; non-homestead homes with the REC
spread; commercial at the non-residential rate).
"""

import copy
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ptm.economy import Economy  # noqa: E402
from ptm.engine.exemptions import apply_exemptions  # noqa: E402
from ptm.engine.step import step  # noqa: E402
from ptm.law import Law, load_law  # noqa: E402
from ptm.policy import apply_policy, load_policy  # noqa: E402
from ptm.project import project_law  # noqa: E402

YEARS = list(range(2026, 2037))
SHOW = [2026, 2027, 2028, 2031, 2036]
SCENARIO, SEED, END = "central", 2026, 2036
OUT = ROOT / "data" / "processed" / "results" / "fl_a3_examples.json"
RATES_CACHE = ROOT / "data" / "processed" / "a3_example_rates.json"
LEVIES = ["school", "county", "municipal", "special"]

# place: (county FIPS, DOR county number, baseline municipality or "" for unincorporated)
PLACES = {
    "miami_dade": ("086", "23", "", "Miami-Dade County (unincorporated)"),
    "orlando": ("095", "58", "ORLANDO", "City of Orlando, Orange County"),
    "polk": ("105", "63", "", "Polk County (unincorporated)"),
    "cape_coral": ("071", "46", "CITY OF CAPE CORAL", "City of Cape Coral, Lee County"),
    "tampa": ("057", "39", "City of Tampa", "City of Tampa, Hillsborough County"),
}
STOREFRONT_JV = 1_000_000      # illustrative: the rolls used here hold residential parcels only


def _roll(co: str) -> pd.DataFrame:
    return pd.read_parquet(glob.glob(str(ROOT / "data" / "processed" / "fl_nal_2026" / f"co{co}_*.parquet"))[0])


def _city(s: pd.Series) -> pd.Series:
    return s.fillna("").str.upper().str.strip()


def place_rates(b: pd.DataFrame, place: str) -> dict:
    """2026 millage of the most common tax district among the place's owners."""
    fips, _, muni, _ = PLACES[place]
    x = b[(b["county_fips_tax"] == fips) & (b["municipality"].fillna("") == muni)]
    d = x["tax_district"].value_counts().index[0]
    r = x[x["tax_district"] == d].iloc[0]
    return {c: float(np.nan_to_num(r[f"millage_{c}"])) for c in LEVIES}


def example_specs(b: pd.DataFrame) -> list[dict]:
    """The six examples, with values from the 2026 rolls."""
    md = _roll("23")
    h = md[md["homestead"] & (md["DOR_UC"] == "001")]
    p90 = float(h["JV"].quantile(0.9))
    band = h[h["JV"].between(p90 * 0.9, p90 * 1.1)]
    md_ratio = float((band["AV_SD"] / band["JV"]).median())

    orl = _roll("58")
    h = orl[orl["homestead"] & (orl["DOR_UC"] == "001") & (orl["SALE_YR1"] == 2025) & (_city(orl["PHY_CITY"]) == "ORLANDO")]
    orl_jv = float(h["JV"].median())

    pk = _roll("63")
    h = pk[pk["homestead"] & (pk["EXMPT_03"].fillna(0) > 0)]
    pk_jv, pk_ratio = float(h["JV"].median()), float((h["AV_SD"] / h["JV"]).median())
    pk_amt = float(b.loc[(b["county_fips_tax"] == "105") & (b["ex_senior_lowinc"] > 0), "ex_senior_amount"].median())

    lee = _roll("46")
    h = lee[lee["homestead"] & (lee["DOR_UC"] == "001") & (lee["SALE_YR1"] >= 2025) & (_city(lee["PHY_CITY"]) == "CAPE CORAL")]
    lee_jv = float(h["JV"].median())

    hb = _roll("39")
    a = hb[~hb["homestead"] & (hb["DOR_UC"] == "008") & (_city(hb["PHY_CITY"]) == "TAMPA")]
    apt_jv, apt_ratio = float(a["JV"].median()), float((a["AV_NSD"] / a["JV"]).median())
    apt_units = int(a["NO_RES_UNTS"].median())

    cb = pd.read_csv(ROOT / "data" / "processed" / "fl_cap_blocks_2026.csv", dtype={"county_fips": str})
    nr = cb[(cb["county_fips"] == "095") & (cb["cls"] == "nr")]
    store_ratio = float(nr["av"].sum() / nr["jv"].sum())

    def home(id_, place, title, who, jv, ratio=1.0, kind="homestead", **kw):
        return {"id": id_, "place": place, "place_name": PLACES[place][3], "title": title, "who": who,
                "kind": kind, "jv_2026": round(jv), "av_ratio_2026": round(ratio, 4),
                "rates_2026": place_rates(b, place), **kw}

    return [
        home("longtime_rich", "miami_dade", "Long-time owner of an expensive home",
             f"A single-family home worth ${p90 / 1e6:.2f} million, in the top tenth of Miami-Dade homesteads. "
             f"Like most long-time owners at this price, Save Our Homes keeps it assessed at {md_ratio:.0%} of its value.",
             p90, md_ratio),
        home("recent_buyer", "orlando", "Recent buyer of a typical home",
             f"Bought a ${orl_jv / 1e3:,.0f}k single-family home in 2025 (the median for 2025 buyers in Orlando), "
             "so it is assessed at full value.", orl_jv),
        home("lowinc_senior", "polk", "Low-income senior",
             f"A 65+ owner of a ${pk_jv / 1e3:,.0f}k home (the median for Polk homesteads with the low-income senior "
             f"exemption), assessed at {pk_ratio:.0%} of its value, with the county's ${pk_amt:,.0f} senior exemption.",
             pk_jv, pk_ratio, ex_senior_lowinc=1, ex_senior_amount=pk_amt),
        home("newcomer_pair", "cape_coral", "Two buyers of the same house",
             f"Two buyers each move into a ${lee_jv / 1e3:,.0f}k house in Cape Coral in 2027 (the median for recent "
             "buyers there): one already lived in Florida, one moves from another state.",
             lee_jv, kind="pair", buy_year=2027),
        home("apartments", "tampa", "Owner of a small rental building",
             f"A {apt_units}-unit rental building worth ${apt_jv / 1e3:,.0f}k (the median for buildings of 2 to 9 units "
             f"in Tampa), assessed at {apt_ratio:.0%} of its value for non-school taxes. Rent effects are not modelled.",
             apt_jv, apt_ratio, kind="nonhomestead"),
        home("storefront", "orlando", "Owner of a small business property",
             f"An illustrative ${STOREFRONT_JV / 1e6:.0f} million shop or office in Orlando, assessed at "
             f"{store_ratio:.0%} of its value for non-school taxes (Orange County's average for commercial property).",
             STOREFRONT_JV, store_ratio, kind="nonresidential"),
    ]


# --- government rate paths ------------------------------------------------------------------

def rate_paths(refresh: bool = False) -> dict:
    """Rate multipliers by year (vs 2026) for every county and city, and school rates:
    current law and Amendment 3 with local governments replacing revenue (both versions)."""
    if RATES_CACHE.exists() and not refresh:
        return json.loads(RATES_CACHE.read_text(encoding="utf-8"))
    sys.path.insert(0, str(ROOT / "scripts"))
    import policy_grid as pg
    from ptm.compare import _run
    from ptm.rate_setting import _city_key  # noqa: F401  (keys below are already normalised)
    import yaml
    B = pg._base()
    menu = yaml.safe_load((ROOT / "inputs" / "policy_menu.yaml").read_text(encoding="utf-8"))
    ents = {e["id"]: e for e in pg.entries(menu) if e.get("amendment3")}

    def paths(run) -> dict:
        rs = run.rates
        return {str(y): {"county": dict(zip(rs.counties.index, np.round(rs.paths[y]["county"].mean(axis=0), 5).tolist())),
                         "city": {f"{k[0]}|{k[1]}": v for k, v in zip(rs.cities.index, np.round(rs.paths[y]["city"].mean(axis=0), 5).tolist())},
                         "school": dict(zip(rs.counties.index, np.round(rs.school_fixed + rs.paths[y]["rle"].mean(axis=0), 4).tolist()))}
                for y in YEARS if y in rs.paths}
    out = {"current": paths(B["run"])}
    for v, eid in [("written", "a3_full"), ("struck", "a3_full_nowait")]:
        law1 = apply_policy(B["law"], {"name": eid, "changes": ents[eid]["changes"]})
        new = _run(B["b"], SCENARIO, SEED, law1, END, revenue_neutral=B["run"].rates.paths, millage_cap=10.0)
        out[f"replace_{v}"] = paths(new)
    RATES_CACHE.write_text(json.dumps(out), encoding="utf-8")
    return out


def mills(spec: dict, paths: dict | None, year: int) -> dict:
    """The example's rates in `year` (2026 district rates moved by the path's multipliers)."""
    r = dict(spec["rates_2026"])
    if paths is None or year == 2026:
        return r
    from ptm.rate_setting import _city_key
    fips, _, muni, _ = PLACES[spec["place"]]
    p = paths[str(year)]
    r["county"] *= p["county"][fips]
    r["school"] = p["school"][fips]
    if muni:
        r["municipal"] *= p["city"][f"{fips}|{_city_key(muni)}"]
    return r


# --- the engine, year by year ----------------------------------------------------------------

def laws(econ: Economy) -> dict[str, Law]:
    base = load_law()
    a3 = load_policy(ROOT / "inputs" / "policies" / "amendment3.yaml")
    struck = {**a3, "changes": a3["changes"] + [{"rule": "homestead_new_resident", "key": "waiting_years", "value": 0, "from": 2027}]}
    return {"current": project_law(base, econ, END),
            "written": project_law(apply_policy(base, a3), econ, END),
            "struck": project_law(apply_policy(base, struck), econ, END)}


def growth(kind: str, econ: Economy, y: int) -> float:
    if kind == "nonresidential":
        return econ.rate("nonresidential_value", y)
    g = econ.rate("home_value", y)
    if kind == "nonhomestead":
        g += econ.rate("nonhomestead_spread", y)
    return g


def _commercial(law: Law) -> Law:
    """Commercial property: the engine's non-homestead rule with the non-residential cap."""
    law = copy.deepcopy(law)
    law.rules["nonhomestead_residential_cap"].spec["cap"] = law.rules["nonresidential_cap"].spec["cap"]
    return law


def taxable_path(spec: dict, law: Law, econ: Economy, newcomer: bool = False) -> dict[int, dict]:
    """Taxable value by levy class, each year the owner holds the property."""
    kind = spec["kind"]
    if kind == "nonresidential":
        law = _commercial(law)
    hs = kind in ("homestead", "pair")
    start = spec.get("buy_year", 2026) + (1 if kind == "pair" else 0)   # bought in 2027: homestead from 2028
    jv = float(spec["jv_2026"])
    flags = {k: spec[k] for k in ("ex_senior_lowinc", "ex_senior_amount") if k in spec}
    out, u = {}, None
    nr = law.rule("homestead_new_resident")
    for y in YEARS:
        if y > 2026:
            jv *= 1 + growth(kind, econ, y)
        if y < start:
            continue
        waiting = newcomer and (y - start) < float(nr.get("waiting_years", y, 0))
        if y == start and kind == "pair":       # bought: assessment resets, first homestead year
            u = pd.DataFrame([{"jv": jv, "homestead": True, "homestead_prior": False, "changed_ownership": True,
                               "improvements": 0.0, "av_school_prior": jv, "av_nonschool_prior": jv}])
        elif y == 2026:                         # known 2026 assessment
            av = jv * spec["av_ratio_2026"]
            a = pd.DataFrame([{"homestead": hs, **flags, "new_resident_waiting": False,
                               "av_school": av if hs else jv, **{f"av_{c}": av for c in LEVIES if c != "school"}}])
            t = apply_exemptions(a, law, y).iloc[0]
            out[y] = {c: float(t[f"taxable_{c}"]) for c in LEVIES}
            u = pd.DataFrame([{"jv": jv, "homestead": hs, "homestead_prior": hs, "changed_ownership": False,
                               "improvements": 0.0, "av_school_prior": float(a["av_school"].iloc[0]),
                               "av_nonschool_prior": av}])
            continue
        u = u.assign(jv=jv, new_resident_waiting=waiting, **flags)
        r = step(u, law, y)
        out[y] = {c: float(r[f"taxable_{c}"].iloc[0]) for c in LEVIES}
        u = u.assign(av_school_prior=float(r["av_school"].iloc[0]), av_nonschool_prior=float(r["av_county"].iloc[0]),
                     homestead_prior=hs, changed_ownership=False)
    return out


def bills(spec: dict, taxable: dict, paths: dict | None) -> dict:
    """Tax by year: school, non-school, total."""
    out = {}
    for y, t in taxable.items():
        m = mills(spec, paths, y)
        sch = t["school"] * m["school"] / 1000
        non = sum(t[c] * m[c] / 1000 for c in LEVIES if c != "school")
        out[y] = {"school": round(sch), "nonschool": round(non), "total": round(sch + non)}
    return out


def run_example(spec: dict, L: dict, econ: Economy, rp: dict) -> dict:
    """Each household in the example: current law, and both versions of the amendment with rates
    unchanged and with local governments replacing the revenue."""
    people = [("newcomer", True), ("floridian", False)] if spec["kind"] == "pair" else [("owner", False)]
    hh = []
    for who, newcomer in people:
        cur = taxable_path(spec, L["current"], econ, newcomer)
        row = {"who": who, "current": bills(spec, cur, rp["current"])}
        for v in ("written", "struck"):
            t = taxable_path(spec, L[v], econ, newcomer)
            row[v] = {"none": bills(spec, t, rp["current"]), "replace": bills(spec, t, rp[f"replace_{v}"])}
        hh.append(row)
    return {**spec, "households": hh}


def main(refresh: bool = False) -> None:
    econ = Economy(SCENARIO)
    b = pd.read_parquet(ROOT / "data" / "processed" / "baseline_fl_2026.parquet",
                        columns=["county_fips_tax", "municipality", "tax_district", "ex_senior_lowinc", "ex_senior_amount",
                                 *[f"millage_{c}" for c in LEVIES]])
    specs = example_specs(b)
    rp = rate_paths(refresh)
    L = laws(econ)
    ex = [run_example(s, L, econ, rp) for s in specs]
    OUT.write_text(json.dumps({"years": SHOW, "scenario": SCENARIO, "examples": ex}, default=float, indent=1), encoding="utf-8")
    for e in ex:
        for h in e["households"]:
            c, w = h["current"], h["written"]
            print(f"{e['id']:15s} {h['who']:9s} " + "  ".join(
                f"{y}: {c[y]['total'] if y in c else '-':>7} -> {w['none'][y]['total'] if y in c else '-':>7} / {w['replace'][y]['total'] if y in c else '-':>7}"
                for y in SHOW))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main("--refresh" in sys.argv)
