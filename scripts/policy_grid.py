"""Pre-compute every policy on the menu for the results page -> data/processed/results/fl_policy_grid.json

Usage:
    python scripts/policy_grid.py [workers]

Reads inputs/policy_menu.yaml (sliders: one number at a time; presets). Each entry is compared
with current law (central economic scenario) three ways: with governments' rate responses (history
rule), with none (rates follow current law's path), and revenue-neutral (each county, city and
school district re-solves its rate to raise the same revenue as under current law), also with the
state reimbursing 25%, 50% or 75% of the lost revenue (100% = no response). Current law runs once
per worker.
Output per entry and mode: yearly changes (total and by levy), and for the reporting years: changes
and winners/losers by income decile and by age, homestead and region (packed as columns + rows).
Per entry, for the revenue-neutral mode: each government's rate change, (current-law taxable value
- policy taxable value) / policy taxable value, by reporting year; with reimbursement r the change is
(1 - r) times that, exactly. `governments` has each one's current-law rates for the page.
"""

import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for _v in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"]:
    os.environ.setdefault(_v, "1")

END, SEED, SCENARIO = 2036, 2026, "central"
YEARS = [2027, 2031, 2036]
BIG = 1e9           # "none": no cap / no limit
GROUPS_OUT = ["income_decile", "age_group", "homestead", "region"]
REIMBURSE = [0.25, 0.5, 0.75]
MODES = ["respond", "none", "neutral"] + [f"neutral_{round(100 * r)}" for r in REIMBURSE]
GCOLS = ["year", "grouping", "group", "owners", "avg_change", "pct_change", "change_share_of_income", "total_change",
         "share_pay_less", "share_pay_more", "gain_more_5pct", "gain_less_5pct", "no_change", "lose_less_5pct",
         "lose_more_5pct", "avg_gain_if_less", "avg_loss_if_more"]
DOLLARS = {"owners", "avg_change", "total_change", "avg_gain_if_less", "avg_loss_if_more"}
_BASE = {}


def _base():
    if "run" not in _BASE:
        from ptm.compare import _run
        from ptm.law import load_law
        from ptm.montecarlo import _baseline
        b = _baseline()
        _BASE["b"], _BASE["law"] = b, load_law()
        _BASE["run"] = _run(b, SCENARIO, SEED, _BASE["law"], END)
    return _BASE


def current_value(rule: str, key: str, year: int):
    from ptm.economy import Economy
    from ptm.law import load_law
    from ptm.project import project_law
    return project_law(load_law(), Economy(SCENARIO), year).rule(rule).get(key, year)


def entries(menu: dict) -> list[dict]:
    """Every slider setting and preset as a policy (id, label, changes)."""
    start = int(menu["from"])
    out = []
    for sl in menu["sliders"]:
        cur = sl["current"]
        if cur == "current":
            cur = current_value(sl["changes"][0]["rule"], sl["changes"][0]["key"], start)
            sl["current"] = round(float(cur), 2)
        sl["settings"] = [round(float(cur), 2) if v == "current" else v for v in sl["settings"]]
        for v in sl["settings"]:
            if v == sl["current"] or (v == "none" and sl["current"] == "none"):
                continue
            ch = []
            for c in sl["changes"]:
                if v == "none" and (c["rule"], c["key"]) == ("soh_cap", "max_rate"):
                    ch.append({"rule": "soh_cap", "key": "cap", "values": {y: BIG for y in range(start, END + 1)}})
                elif v == "none" and (c["rule"], c["key"]) == ("senior_nonschool", "min_age"):
                    ch = None
                    break
                else:
                    ch.append({"rule": c["rule"], "key": c["key"], "value": BIG if v == "none" else v, "from": start})
            if ch is None:
                continue
            ch += [{**w, "from": start} for w in sl.get("with", [])]
            out.append({"id": f"{sl['id']}={v}", "slider": sl["id"], "setting": v, "changes": ch})
    for pr in menu["presets"]:
        out.append({"id": pr["id"], "preset": pr["id"], "changes": pr["changes"]})
    for a in menu.get("amendment3", []):
        pol = yaml.safe_load((ROOT / a["file"]).read_text(encoding="utf-8"))
        out.append({"id": a["id"], "amendment3": a["id"], "changes": pol["changes"] + a.get("also", [])})
    return out


def summarize(r: dict) -> dict:
    ch = r["changes"]
    yearly = [{"year": int(y), "tax": float(ch.loc[y, "tax_total"]), "school": float(ch.loc[y, "tax_school"]),
               "county": float(ch.loc[y, "tax_county"]), "city": float(ch.loc[y, "tax_municipal"]),
               "pct": float(ch.loc[y, "tax_total_pct"]), "avg_tax": float(ch.loc[y, "avg_tax"]),
               "mill_county": float(ch.loc[y, "millage_county_avg"]), "mill_school": float(ch.loc[y, "millage_school_avg"]),
               "nonowner": float(ch.loc[y, "nonowner_tax_nonschool"] + ch.loc[y, "nonowner_tax_school"]),
               "nonowner_school": float(ch.loc[y, "nonowner_tax_school"]),
               "all": float(ch.loc[y, "tax_all_property"])}
              for y in ch.index if y > 2026]
    g, w = r["by_group"], r["winners"]
    m = g.merge(w, on=["year", "grouping", "group", "owners"])
    m = m[m.grouping.isin(["all"] + GROUPS_OUT)]
    def num(c, v):
        v = float(v)
        return None if not np.isfinite(v) else round(v, 1 if c in DOLLARS else 4)
    rows = [[int(x.year), x.grouping, x.group] + [num(c, getattr(x, c)) for c in GCOLS[3:]] for x in m.itertuples()]
    return {"yearly": yearly, "groups": rows}


def rate_changes(base, new) -> dict:
    """Each government's revenue-neutral rate change (before reimbursement) in the reporting years."""
    out = {}
    for y in YEARS:
        b, p = base.rates.paths[y]["tv"], new.rates.paths[y]["tv"]
        with np.errstate(divide="ignore", invalid="ignore"):
            d = {k: np.where(p[k] > 0, (b[k] - p[k]) / p[k], 0.0) for k in ["county", "city", "school"]}
        out[str(y)] = {k: [round(float(v), 4) for v in d[k]] for k in d}
    return out


def run_entry(e: dict) -> dict:
    from ptm.compare import _run, compare_runs
    from ptm.policy import apply_policy
    B = _base()
    t = time.time()
    law1 = apply_policy(B["law"], {"name": e["id"], "changes": e["changes"]})
    out = {"id": e["id"]}
    for resp in MODES:
        neutral = resp.startswith("neutral")
        new = _run(B["b"], SCENARIO, SEED, law1, END,
                   rate_replay=B["run"].rates.paths if resp == "none" else None,
                   revenue_neutral=B["run"].rates.paths if neutral else None,
                   reimbursement=int(resp.split("_")[1]) / 100 if "_" in resp else 0.0)
        out[resp] = summarize(compare_runs(B["run"], new, END, years=YEARS))
        if resp == "neutral":
            out["rates"] = rate_changes(B["run"], new)
    out["seconds"] = time.time() - t
    return out


def base_levels() -> dict:
    B = _base()
    s = B["run"].summary
    return {"yearly": [{"year": int(y), "tax_total": float(r.tax_total), "avg_tax": float(r.avg_tax),
                        "owners": float(r.owners), "school": float(r.tax_school), "county": float(r.tax_county),
                        "city": float(r.tax_municipal), "mill_county": float(r.millage_county_avg),
                        "mill_school": float(r.millage_school_avg), "mill_city": float(r.millage_municipal_avg),
                        "nonowner": float(r.nonowner_tax_nonschool + r.nonowner_tax_school),
                        "nonowner_school": float(r.nonowner_tax_school)}
                       for y, r in s.iterrows()]}


def governments() -> dict:
    """Each county (general levy, school total) and city: current-law rate in the reporting years."""
    from ptm.millage import county_fips_by_name
    from ptm.rate_setting import _city_key
    B = _base()
    rs, b = B["run"].rates, B["b"]
    fips = county_fips_by_name()
    norm = lambda n: str(n).lower().replace("st. ", "saint ").replace("st ", "saint ").replace("-", " ").strip()
    by_norm = {norm(k): v for k, v in fips.items()}
    rep26 = pd.read_csv(ROOT / "data" / "processed" / "baseline_fl_2026_rates_2026_report.csv")
    rep26["fips"] = rep26["county"].map(lambda n: fips.get(n, by_norm.get(norm(n))))
    name = {v: k for k, v in fips.items()}
    gen = rep26.set_index("fips")["mill_2026"]
    from ptm.project import owner_mask
    own = b[owner_mask(b)]
    own = own[own["municipality"].notna() & own["millage_municipal"].gt(0)]
    keys = list(zip(own["county_fips_tax"], own["municipality"].map(_city_key)))
    own = own.assign(k=keys)
    city_mill = own.groupby("k")["millage_municipal"].median()
    city_name = own.groupby("k")["municipality"].agg(lambda s: s.mode().iloc[0])
    path = {y: rs.paths[y] for y in YEARS}
    counties = []
    for i, f in enumerate(rs.counties.index):
        g = float(gen.get(f, np.nan))
        counties.append({"fips": f, "name": name.get(f, f),
                         "general": {str(y): round(g * float(path[y]["county"][:, i].mean()), 4) for y in YEARS} if np.isfinite(g) else None,
                         "school": {str(y): round(float(rs.school_fixed[i] + path[y]["rle"][:, i].mean()), 4) for y in YEARS},
                         "tv": {str(y): round(float(path[y]["tv"]["county"][i])) for y in YEARS},
                         "tv_school": {str(y): round(float(path[y]["tv"]["school"][i])) for y in YEARS}})
    cities = []
    for j, k in enumerate(rs.cities.index):
        m = city_mill.get(k)
        if m is None or not np.isfinite(m):
            continue
        nm = str(city_name.get(k)).title().replace("Of ", "of ")
        cities.append({"i": j, "county": k[0], "name": nm,
                       "rate": {str(y): round(float(m) * float(path[y]["city"][:, j].mean()), 4) for y in YEARS},
                       "tv": {str(y): round(float(path[y]["tv"]["city"][j])) for y in YEARS}})
    return {"counties": counties, "cities": cities}


def main(workers: int = 4) -> None:
    from ptm.montecarlo import PREP, SLIM, _run_path, slim_baseline
    slim_baseline()
    if not PREP.exists() or PREP.stat().st_mtime < SLIM.stat().st_mtime:
        _run_path((SCENARIO, SEED, 2027, None, False))
    menu = yaml.safe_load((ROOT / "inputs" / "policy_menu.yaml").read_text(encoding="utf-8"))
    es = entries(menu)
    print(f"{len(es)} policies x {len(MODES)} responses, {workers} workers")
    t = time.time()
    with ProcessPoolExecutor(max_workers=workers) as ex:
        res = list(ex.map(run_entry, es))
    out = {"scenario": SCENARIO, "years": YEARS, "from": menu["from"], "generated": pd.Timestamp.now().strftime("%Y-%m-%d"),
           "current_law": base_levels(), "sliders": menu["sliders"], "presets": menu["presets"],
           "amendment3": [{k: a[k] for k in ("id", "label", "description")} for a in menu.get("amendment3", [])],
           "group_cols": GCOLS, "reimburse": REIMBURSE, "governments": governments(),
           "runs": {r["id"]: {k: r[k] for k in MODES + ["rates"]} for r in res}}
    dest = ROOT / "data" / "processed" / "results" / "fl_policy_grid.json"

    def clean(o):
        if isinstance(o, dict):
            return {str(k): clean(v) for k, v in o.items()}
        if isinstance(o, list):
            return [clean(v) for v in o]
        if isinstance(o, float):
            return None if not np.isfinite(o) else round(o, 4)
        return o
    dest.write_text(json.dumps(clean(out)), encoding="utf-8")
    print(f"done in {time.time() - t:.0f}s; wrote {dest} ({dest.stat().st_size / 1e6:.1f} MB)")
    for r in res:
        if r["id"].split("=")[0] in {"homestead_second", "soh_cap"} or "=" not in r["id"]:
            y = [x for x in r["respond"]["yearly"] if x["year"] == 2027][0]
            n = [x for x in r["none"]["yearly"] if x["year"] == 2027][0]
            print(f"  {r['id']:38s} 2027: respond {y['tax'] / 1e9:+.2f}B  none {n['tax'] / 1e9:+.2f}B")


if __name__ == "__main__":
    main(*(int(a) for a in sys.argv[1:]))
