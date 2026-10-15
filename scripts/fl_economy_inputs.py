"""Build the economic input paths for projections -> inputs/fl_economy_paths.csv

Usage:
    python scripts/fl_economy_inputs.py

Sources (downloaded PDFs, text extracted next to them):
  - Revenue Estimating Conference, Ad Valorem Assessments, July 31 / Aug 3, 2026
    (data/raw/fl_rec_advalorem/2026-08/adval_comparisonstatewidecategories.pdf): just value and new
    construction by property category, 2026-2032, for the adopted forecast ("New") and the three
    proposals it chose between (EDR = Legislature's economists, FEA = Governor's office, DOR).
    Appreciation of existing property = (JV[t] - new construction[t]) / JV[t-1] - 1.
  - Florida Economic Estimating Conference, July 17, 2026, long-run tables
    (data/raw/fl_eec/2026-07/floridaeconomicresultslongrun.pdf): personal income, average annual
    wage, population, households, Florida Realtors median sale prices, to 2036 (fiscal years
    ending in the year shown; population and households are April 1 estimates).

Output columns: variable, source, year, value, growth (growth = value[t] / value[t-1] - 1, except
appreciation rows, where value is already a rate).
"""

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REC = ROOT / "data" / "raw" / "fl_rec_advalorem" / "2026-08" / "adval_comparisonstatewidecategories.txt"
EEC = ROOT / "data" / "raw" / "fl_eec" / "2026-07" / "floridaeconomicresultslongrun.txt"
REC_YEARS = list(range(2026, 2033))
EEC_YEARS = list(range(2020, 2037))
CATEGORIES = {"Homestead": "homestead", "Non-Homestead Residential": "nonhomestead_residential",
              "Non-Residential": "nonresidential"}
PROPOSALS = {"New": "rec_adopted", "EDR": "rec_edr", "FEA": "rec_fea", "DOR": "rec_dor"}


def _num(s: str) -> float:
    s = s.replace(",", "")
    return -float(s[1:-1]) if s.startswith("(") else float(s)


def rec_rows(block: str, measure: str) -> dict[str, list[float]]:
    """Rows of one measure ("Just Value", "New Construction") in a category block -> {proposal: values}."""
    i = block.index(measure)
    part = block[i:i + 2500]
    out = {}
    for name in PROPOSALS:
        m = re.search(rf"^{name} \(\$ mil\) ((?:\(?[\d,]+\.\d\)?\s*)+)$", part, re.M)
        if m:
            out[name] = [_num(x) for x in m.group(1).split()]
    return out


def rec_paths() -> list[dict]:
    t = REC.read_text(encoding="utf-8")
    rows = []
    for title, var in CATEGORIES.items():
        start = t.index(f"Comparison of {title} Forecasts")
        block = t[start:start + 9000]
        jv, nc = rec_rows(block, "Just Value"), rec_rows(block, "New Construction")
        for name, src in PROPOSALS.items():
            if name not in jv or len(jv[name]) != len(REC_YEARS):
                continue
            for k, y in enumerate(REC_YEARS):
                rows.append({"variable": f"just_value_{var}", "source": src, "year": y, "value": jv[name][k] * 1e6})
                rows.append({"variable": f"new_construction_{var}", "source": src, "year": y, "value": nc[name][k] * 1e6})
                if k:
                    appr = (jv[name][k] - nc[name][k]) / jv[name][k - 1] - 1
                    rows.append({"variable": f"appreciation_{var}", "source": src, "year": y, "value": appr})
    return rows


EEC_SERIES = {
    "personal_income": r"^1\. Personal Income, July 2026, Millions of Dollars \(SAAR\) (.+)$",
    "average_wage": r"^9\. Average Annual Wage, July 2026, Thousands of Dollars \(SAAR\) (.+)$",
    "population": r"^1\. Population \(millions\) (.+)$",
    "households": r"^2\. Households \(millions\) (.+)$",
    "median_price_single_family": r"^9\. FAR Median Price of Existing Single-Family Homes Sold, July 2026, \$ (.+)$",
    "median_price_condo": r"^11 FAR Median Price of Existing Condominiums Sold, July 2026 (.+)$",
}


def eec_paths() -> list[dict]:
    t = EEC.read_text(encoding="utf-8")
    rows = []
    for var, pat in EEC_SERIES.items():
        m = re.search(pat, t, re.M)
        if not m:
            raise ValueError(f"EEC series not found: {var}")
        vals = [_num(x) for x in m.group(1).split()][:len(EEC_YEARS)]
        for y, v in zip(EEC_YEARS, vals):
            rows.append({"variable": var, "source": "fl_eec_2026_07", "year": y, "value": v})
    return rows


def combined_paths(d: pd.DataFrame) -> list[dict]:
    """Residential appreciation for homestead and non-homestead combined (homes moving between the
    two categories change each category's value but not market prices), and personal income per
    household."""
    rows = []
    for src in PROPOSALS.values():
        jv = sum(d[(d.variable == f"just_value_{c}") & (d.source == src)].set_index("year")["value"]
                 for c in ["homestead", "nonhomestead_residential"])
        nc = sum(d[(d.variable == f"new_construction_{c}") & (d.source == src)].set_index("year")["value"]
                 for c in ["homestead", "nonhomestead_residential"])
        if not isinstance(jv, pd.Series) or jv.empty:
            continue
        for y in REC_YEARS[1:]:
            rows.append({"variable": "appreciation_residential", "source": src, "year": y,
                         "value": (jv[y] - nc[y]) / jv[y - 1] - 1})
    pi = d[d.variable == "personal_income"].set_index("year")["value"]
    hh = d[d.variable == "households"].set_index("year")["value"]
    for y in EEC_YEARS:
        rows.append({"variable": "personal_income_per_household", "source": "fl_eec_2026_07", "year": y,
                     "value": pi[y] * 1e6 / (hh[y] * 1e3)})
    return rows


def main() -> None:
    d = pd.DataFrame(rec_paths() + eec_paths())
    d = pd.concat([d, pd.DataFrame(combined_paths(d))], ignore_index=True)
    level = ~d["variable"].str.startswith("appreciation_")
    d["growth"] = d[level].groupby(["variable", "source"])["value"].pct_change()
    d.loc[~level, "growth"] = d.loc[~level, "value"]
    dest = ROOT / "inputs" / "fl_economy_paths.csv"
    d.to_csv(dest, index=False)
    print(f"wrote {dest}: {len(d)} rows")
    show = d[d["variable"].isin(["appreciation_residential", "appreciation_nonresidential", "average_wage",
                                 "personal_income_per_household", "households", "median_price_single_family"])]
    print(show.pivot_table(index=["variable", "source"], columns="year", values="growth").round(4).to_string())


if __name__ == "__main__":
    main()
