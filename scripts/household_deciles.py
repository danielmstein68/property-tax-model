"""All Florida households by 2026 income decile -> data/processed/results/fl_household_deciles.json

Usage:
    python scripts/household_deciles.py

Households (renters included), owners as the results count them, and total household income per
decile, with the same decile cut-offs as the results (ptm.results.add_income_deciles). The page
uses these to show policy changes per household (renters at $0) and each decile's share of
households and income next to its share of a tax cut.
"""

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ptm.results import add_income_deciles, owner_mask  # noqa: E402

OUT = ROOT / "data" / "processed" / "results" / "fl_household_deciles.json"


def household_deciles(b: pd.DataFrame) -> list[dict]:
    h = add_income_deciles(b)
    w = h["WGTP"]
    inc = h["hincp_aged"].fillna(0).clip(lower=0) * w
    own = owner_mask(h)
    g = pd.DataFrame({"households": w, "owners": w.where(own, 0), "income": inc}).groupby(h["income_decile"]).sum()
    return [{"decile": int(d), "households": round(float(r.households)), "owners": round(float(r.owners)),
             "income": round(float(r.income))} for d, r in g.iterrows()]


def main() -> None:
    b = pd.read_parquet(ROOT / "data" / "processed" / "baseline_fl_2026.parquet",
                        columns=["WGTP", "hincp_aged", "tenure", "mh_rented_lot", "tax_model_2026"])
    rows = household_deciles(b)
    OUT.write_text(json.dumps({"year": 2026, "income": "household income (2026), negatives as 0", "deciles": rows}, indent=1), encoding="utf-8")
    for r in rows:
        print(r)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
