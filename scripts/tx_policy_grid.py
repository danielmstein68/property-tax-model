"""Pre-compute every Texas policy on the menu for the results page -> data/processed/results/tx_policy_grid.json

Usage:
    python scripts/tx_policy_grid.py [workers] [--only <plan or slider id> ...] [--no-pairs]

Reads inputs/tx_policy_menu.yaml: sliders (one current-law number at a time) and plans (each with its own
numbers, "knobs"). Entries: every slider setting; every plan as written; every plan knob setting one at a time
(the rest of the plan as written); and every pair of a plan's knobs (both moved), so the page can move any one
or two of a plan's numbers. Each entry is compared with current law (central scenario) three ways
(ptm.tx.compare): rates unchanged ("none"), units respond under their rules ("respond"), and revenue-neutral
("neutral"). When the state replaces local revenue, "neutral" equals "none" and isn't re-run.

Output, per entry and mode (compact): yearly changes 2026-2036 (homestead, owner, other-property and all
property tax; levies by unit type; state cost; local revenue lost; sales tax points; average homestead bill),
and for 2027, 2031 and 2036 the change by income tenth, age, homestead, region and 65+ status, with shares
paying less and more (size bands for all owners and by income tenth).
"""

import itertools
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for _v in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"]:
    os.environ.setdefault(_v, "1")

MENU = ROOT / "inputs" / "tx_policy_menu.yaml"
DEST = ROOT / "data" / "processed" / "results" / "tx_policy_grid.json"
MODES = ["none", "respond", "neutral"]
YEARLY = ["tax_total", "tax_owners", "nonowner_tax", "nonowner_tax_residential", "total_levy", "avg_tax", "credit_total",
          "levy_school", "levy_county", "levy_city", "levy_college", "levy_hospital", "levy_special",
          "state_cost", "local_revenue_lost", "sales_tax_points"]
GROUPINGS = ["all", "income_decile", "age_group", "homestead", "region", "over65"]
BANDS = ["gain_more_5pct", "gain_less_5pct", "no_change", "lose_less_5pct", "lose_more_5pct"]
_B = {}


# --- building policies from the menu -------------------------------------------------------------------
def schedule(fn: str, setting) -> dict:
    """values_fn -> {year: value}: "phase:N" (exempt share rising evenly to 1 over N years from 2027;
    "never" = 0) and "freeze:N:after" (0 for N years from 2027, then `after`)."""
    kind, *args = fn.split(":")
    a = [str(setting) if x == "@" else x for x in args]
    if kind == "phase":
        if a[0] == "never":
            return {2027: 0.0}
        n = int(a[0])
        return {2026 + i: round(min(i / n, 1.0), 6) for i in range(1, n + 1)}
    if kind == "freeze":
        n, after = int(a[0]), a[1]
        after = "none" if after == "none" else float(after)
        return {2027: after} if n == 0 else {2027: 0.0, 2027 + n: after}
    raise ValueError(fn)


def canon(v) -> str:
    """A setting as the page writes it (JavaScript's String(number)): 0.0 -> "0", 180000.0 -> "180000"."""
    if isinstance(v, bool):
        return str(int(v))
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else repr(v)
    return str(v)


def expand(changes: list, setting=None, frm: int = 2027) -> list:
    out = []
    for c in changes:
        c = dict(c)
        if "values_fn" in c:
            c["values"] = schedule(c.pop("values_fn"), setting)
        elif "values" not in c:
            v = c.get("value")
            c["value"] = setting if v == "@" else v
            c.setdefault("from", frm)
        out.append(c)
    return out


def merge(base: list, over: list) -> list:
    keys = {(c["rule"], c["key"]) for c in over}
    return [c for c in base if (c["rule"], c["key"]) not in keys] + over


def knob_changes(k: dict, setting) -> list:
    if "choice" in k:
        return expand(k["choice"][str(setting)] if str(setting) in k["choice"] else k["choice"][setting])
    return expand(k["changes"], setting)


def entries(menu: dict, only: set | None = None, pairs: bool = True) -> list[dict]:
    frm = int(menu.get("from", 2027))
    out = []
    for s in menu["sliders"]:
        if only and s["id"] not in only:
            continue
        for v in s["settings"]:
            if canon(v) == canon(s["current"]):
                continue
            ch = expand(s["changes"], v, frm) + expand(s.get("with", []), None, frm)
            out.append({"key": f"s:{s['id']}:{canon(v)}", "changes": ch})
    for p in menu["plans"]:
        if only and p["id"] not in only:
            continue
        base = expand(p["changes"], None, frm)
        out.append({"key": f"p:{p['id']}", "changes": base})
        knobs = p.get("knobs", [])
        for k in knobs:
            for v in k["settings"]:
                if canon(v) == canon(k["default"]):
                    continue
                out.append({"key": f"k:{p['id']}:{k['id']}={canon(v)}", "changes": merge(base, knob_changes(k, v))})
        if pairs:
            for k1, k2 in itertools.combinations(knobs, 2):
                for v1 in k1["settings"]:
                    for v2 in k2["settings"]:
                        if canon(v1) == canon(k1["default"]) or canon(v2) == canon(k2["default"]):
                            continue
                        ch = merge(merge(base, knob_changes(k1, v1)), knob_changes(k2, v2))
                        out.append({"key": f"q:{p['id']}:{k1['id']}={canon(v1)}|{k2['id']}={canon(v2)}", "changes": ch})
    return out


# --- running ---------------------------------------------------------------------------------------------
def _base():
    if "b" not in _B:
        from ptm.tx.compare import Base
        _B["b"] = Base()
    return _B["b"]


def _r(x, nd=0):
    x = float(x)
    return None if not np.isfinite(x) else round(x, nd)


def compact(r: dict) -> dict:
    ch = r["changes"]
    yearly = {k: [_r(ch.loc[y, k], 4 if k == "sales_tax_points" else 0) for y in ch.index] for k in YEARLY if k in ch}
    g, w = r["by_group"], r["winners"]
    groups = {}
    for y in r["years"]:
        gy, wy = g[g.year == y], w[w.year == y].set_index(["grouping", "group"])
        rows = []
        for _, x in gy.iterrows():
            ww = wy.loc[(x["grouping"], x["group"])]
            row = [x["grouping"], x["group"], _r(x["owners"]), _r(x["avg_change"], 1), _r(x["change_share_of_income"] * 1e4, 2),
                   _r(x["pct_change"] * 1e4, 1), _r(ww["share_pay_less"] * 1e3, 1), _r(ww["share_pay_more"] * 1e3, 1)]
            if x["grouping"] in ("all", "income_decile"):
                row += [_r(ww[b] * 1e3, 1) for b in BANDS]
            rows.append(row)
        groups[str(y)] = rows
    return {"yearly": yearly, "groups": groups}


def run_entry(e: dict) -> tuple[str, dict, float]:
    from ptm.tx.compare import compare
    t = time.time()
    b = _base()
    pol = {"name": e["key"], "changes": e["changes"]}
    state_local = any(c["rule"] == "state_replaces_local" and (c.get("value") == 1) for c in e["changes"])
    out = {}
    for mode in MODES:
        if mode == "neutral" and state_local:
            out[mode] = out["none"]
            continue
        try:
            out[mode] = compact(compare(pol, b, mode))
        except Exception as ex:              # report, keep going
            out[mode] = {"error": f"{type(ex).__name__}: {ex}"}
    return e["key"], out, time.time() - t


def main() -> None:
    args = sys.argv[1:]
    workers = int(args[0]) if args and args[0].isdigit() else max(1, min(4, (os.cpu_count() or 2) // 2 - 1))
    only = set(args[args.index("--only") + 1:]) if "--only" in args else None
    menu = yaml.safe_load(MENU.read_text(encoding="utf-8"))
    es = entries(menu, only, pairs="--no-pairs" not in args)
    print(f"{len(es)} entries x {len(MODES)} modes on {workers} workers")
    prev = json.loads(DEST.read_text(encoding="utf-8")) if (only and DEST.exists()) else None
    runs = dict(prev["runs"]) if prev else {}
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=workers, initializer=_base) as ex:
        for i, (k, out, secs) in enumerate(ex.map(run_entry, es, chunksize=1)):
            runs[k] = out
            if i % 10 == 0 or i == len(es) - 1:
                el = time.time() - t0
                print(f"  {i + 1}/{len(es)} {k} ({secs:.0f}s; {el / 60:.0f} min, ~{el / (i + 1) * (len(es) - i - 1) / 60:.0f} min left)", flush=True)
    b = _base()
    s = b.run.summary
    meta = {"generated": time.strftime("%Y-%m-%d"), "scenario": "central", "years": [int(y) for y in s.index],
            "report_years": [2027, 2031, 2036], "modes": MODES,
            "current_law": {k: [_r(s.loc[y, k]) for y in s.index] for k in ["tax_total", "tax_owners", "nonowner_tax", "total_levy", "avg_tax", "homesteads",
                                                                             "levy_school", "levy_county", "levy_city", "levy_college", "levy_hospital", "levy_special"]},
            "group_columns": ["grouping", "group", "owners", "avg_change", "change_share_of_income_bp", "pct_change_bp",
                              "share_pay_less_pm", "share_pay_more_pm"] + [f"{x}_pm" for x in BANDS]}
    out = {"meta": meta, "sliders": menu["sliders"], "plans": menu["plans"], "runs": runs}
    DEST.write_text(json.dumps(out, separators=(",", ":"), default=str), encoding="utf-8")
    print(f"wrote {DEST} ({DEST.stat().st_size / 1e6:.1f} MB, {len(runs)} entries, {(time.time() - t0) / 60:.0f} min)")


if __name__ == "__main__":
    main()
