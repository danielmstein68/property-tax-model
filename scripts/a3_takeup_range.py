"""Amendment 3 revenue lost under low and high behavioural responses -> data/processed/results/fl_a3_takeup_range.json

Usage:
    python scripts/a3_takeup_range.py [workers]

The policy grid (scripts/policy_grid.py) uses the central take-up and residency-switch values in
inputs/fl_projection_assumptions.yaml (20% of possibly-eligible non-claimers and 5% of out-of-state
second-home owners at a $2,500 gain). This re-runs Amendment 3 (as written, and with the five-year
rule struck down) at the file's low (10%, 2%) and high (40%, 10%) values, with rates unchanged and
with localities replacing the revenue (10-mill cap), so the page can show a range. The static run
(no behaviour, the state's method) is already in the grid as `none_static`.
"""

import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
for _v in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"]:
    os.environ.setdefault(_v, "1")

IDS = ["a3_full", "a3_full_nowait"]
LEVELS = ["low", "high"]
MODES = ["none", "neutral"]


def run_one(task: tuple) -> dict:
    eid, level, mode = task
    os.environ["PTM_BEHAVIOUR_LEVEL"] = level
    import policy_grid as pg
    from ptm.compare import _run, compare_runs
    from ptm.policy import apply_policy
    menu = yaml.safe_load((ROOT / "inputs" / "policy_menu.yaml").read_text(encoding="utf-8"))
    e = next(x for x in pg.entries(menu) if x["id"] == eid)
    B = pg._base()
    t = time.time()
    law1 = apply_policy(B["law"], {"name": eid, "changes": e["changes"]})
    neutral = mode == "neutral"
    new = _run(B["b"], pg.SCENARIO, pg.SEED, law1, pg.END,
               rate_replay=B["run"].rates.paths if not neutral else None,
               revenue_neutral=B["run"].rates.paths if neutral else None,
               millage_cap=10.0 if neutral else None)
    s = pg.summarize(compare_runs(B["run"], new, pg.END, years=pg.YEARS))
    keep = ["year", "all", "tax", "nonowner", "claimants", "switched"]
    return {"id": eid, "level": level, "mode": mode, "seconds": round(time.time() - t),
            "yearly": [{k: r[k] for k in keep} for r in s["yearly"]]}


def main(workers: int = 4) -> None:
    tasks = [(i, l, m) for i in IDS for l in LEVELS for m in MODES]
    spec = yaml.safe_load((ROOT / "inputs" / "fl_projection_assumptions.yaml").read_text(encoding="utf-8"))
    t = time.time()
    with ProcessPoolExecutor(max_workers=workers) as ex:
        res = list(ex.map(run_one, tasks))
    out = {"generated": time.strftime("%Y-%m-%d"),
           "levels": {l: {k: spec[k]["share_at_ref"][l] for k in ["takeup", "residency_switch"]} for l in ["low", "central", "high"]},
           "runs": {}}
    for r in res:
        out["runs"].setdefault(r["id"], {}).setdefault(r["level"], {})[r["mode"]] = r["yearly"]
        y = {x["year"]: x for x in r["yearly"]}
        print(f"  {r['id']:16s} {r['level']:4s} {r['mode']:7s} 2027 {y[2027]['all'] / 1e9:+.2f}B  2031 {y[2031]['all'] / 1e9:+.2f}B  ({r['seconds']}s)")
    dest = ROOT / "data" / "processed" / "results" / "fl_a3_takeup_range.json"
    dest.write_text(json.dumps(out), encoding="utf-8")
    print(f"{len(res)} runs in {time.time() - t:.0f}s; wrote {dest}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 4)
