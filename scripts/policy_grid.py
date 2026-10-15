"""Pre-compute every policy on the menu for the results page -> data/processed/results/fl_policy_grid.json

Usage:
    python scripts/policy_grid.py [workers]

Reads inputs/policy_menu.yaml (sliders: one number at a time; presets). Each entry is compared
with current law (central economic scenario) three ways: with governments' rate responses (history
rule), with none (rates follow current law's path), and revenue-neutral (each county, city and
school district re-solves its rate to raise the same revenue as under current law). Current law runs once per worker.
Output per entry: yearly changes (total and by levy), and for the reporting years: changes and
winners/losers by income decile and by age, homestead and region.
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
    return out


def summarize(r: dict) -> dict:
    ch = r["changes"]
    yearly = [{"year": int(y), "tax": float(ch.loc[y, "tax_total"]), "school": float(ch.loc[y, "tax_school"]),
               "county": float(ch.loc[y, "tax_county"]), "city": float(ch.loc[y, "tax_municipal"]),
               "pct": float(ch.loc[y, "tax_total_pct"]), "avg_tax": float(ch.loc[y, "avg_tax"]),
               "mill_county": float(ch.loc[y, "millage_county_avg"]), "mill_school": float(ch.loc[y, "millage_school_avg"])}
              for y in ch.index if y > 2026]
    g, w = r["by_group"], r["winners"]
    m = g.merge(w, on=["year", "grouping", "group", "owners"])
    m = m[m.grouping.isin(["all"] + GROUPS_OUT)]
    cols = ["avg_change", "pct_change", "change_share_of_income", "total_change", "share_pay_less", "share_pay_more",
            "gain_more_5pct", "gain_less_5pct", "no_change", "lose_less_5pct", "lose_more_5pct",
            "avg_gain_if_less", "avg_loss_if_more"]
    rows = [{"year": int(x.year), "grouping": x.grouping, "group": x.group, "owners": float(x.owners),
             **{c: float(getattr(x, c)) for c in cols}} for x in m.itertuples()]
    return {"yearly": yearly, "groups": rows}


def run_entry(e: dict) -> dict:
    from ptm.compare import _run, compare_runs
    from ptm.policy import apply_policy
    B = _base()
    t = time.time()
    law1 = apply_policy(B["law"], {"name": e["id"], "changes": e["changes"]})
    out = {"id": e["id"]}
    for resp in ["respond", "none", "neutral"]:
        new = _run(B["b"], SCENARIO, SEED, law1, END,
                   rate_replay=B["run"].rates.paths if resp == "none" else None,
                   revenue_neutral=B["run"].rates.paths if resp == "neutral" else None)
        out[resp] = summarize(compare_runs(B["run"], new, END, years=YEARS))
    out["seconds"] = time.time() - t
    return out


def base_levels() -> dict:
    B = _base()
    s = B["run"].summary
    return {"yearly": [{"year": int(y), "tax_total": float(r.tax_total), "avg_tax": float(r.avg_tax),
                        "owners": float(r.owners), "school": float(r.tax_school), "county": float(r.tax_county),
                        "city": float(r.tax_municipal), "mill_county": float(r.millage_county_avg),
                        "mill_school": float(r.millage_school_avg), "mill_city": float(r.millage_municipal_avg)}
                       for y, r in s.iterrows()]}


def main(workers: int = 4) -> None:
    from ptm.montecarlo import PREP, SLIM, _run_path, slim_baseline
    slim_baseline()
    if not PREP.exists() or PREP.stat().st_mtime < SLIM.stat().st_mtime:
        _run_path((SCENARIO, SEED, 2027, None, False))
    menu = yaml.safe_load((ROOT / "inputs" / "policy_menu.yaml").read_text(encoding="utf-8"))
    es = entries(menu)
    print(f"{len(es)} policies x 3 responses, {workers} workers")
    t = time.time()
    with ProcessPoolExecutor(max_workers=workers) as ex:
        res = list(ex.map(run_entry, es))
    out = {"scenario": SCENARIO, "years": YEARS, "from": menu["from"], "generated": pd.Timestamp.now().strftime("%Y-%m-%d"),
           "current_law": base_levels(), "sliders": menu["sliders"], "presets": menu["presets"],
           "runs": {r["id"]: {"respond": r["respond"], "none": r["none"], "neutral": r["neutral"]} for r in res}}
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
