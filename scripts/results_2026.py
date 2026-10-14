"""2026 status quo results (owners only) -> data/processed/results/fl_2026_status_quo.json

Usage:
    python scripts/results_2026.py

Reads data/processed/baseline_fl_2026.parquet (scripts/build_baseline.py). Tables: by income
decile (deciles over all households), and by householder age, home type, homestead status,
years in home and region; each with replicate-weight standard errors. Plus totals by levy class,
Suits index and data-reliability figures for the display's notes.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ptm.results import add_income_deciles, owner_mask, suits_with_se, table  # noqa: E402
from ptm.settings import Settings  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
YEAR = 2026
CLASSES = ["school", "county", "municipal", "special"]

# Regions by county FIPS (Florida, 3-digit)
REGIONS = {
    "Southeast": ["086", "011", "099", "087", "085", "111", "061", "093"],
    "Southwest": ["071", "021", "015", "115", "081", "051", "043", "027", "049", "055"],
    "Tampa Bay": ["057", "103", "101", "053", "105", "017"],
    "Central": ["095", "097", "117", "069", "127", "009", "119", "083", "035"],
    "Northeast": ["031", "109", "019", "089", "003", "107", "001", "007", "023", "041", "075", "121", "125"],
}
REGION_OF = {f: r for r, fs in REGIONS.items() for f in fs}

AGE_BANDS = [(0, 44, "Under 45"), (45, 64, "45–64"), (65, 74, "65–74"), (75, 200, "75 and over")]
MV_BANDS = {1: "Under 2 years", 2: "Under 2 years", 3: "2–4 years", 4: "5–9 years",
            5: "10–19 years", 6: "20 years or more", 7: "20 years or more"}
HOME_TYPES = {"sfr": "Single-family", "condo": "Condo / co-op", "mobile": "Mobile home (owns land)"}


def weighted_median(x: pd.Series, w: pd.Series) -> float:
    o = np.argsort(x.to_numpy())
    c = np.cumsum(w.to_numpy()[o]) / w.sum()
    return float(x.to_numpy()[o][np.searchsorted(c, 0.5)])


def records(t: pd.DataFrame, order: list | None = None) -> list[dict]:
    t = t.copy()
    if order:
        t = t.loc[[k for k in order if k in t.index] + ["All owners"]]
    out = []
    for k, r in t.iterrows():
        d = {"group": str(k)}
        d.update({c: (None if pd.isna(v) else round(float(v), 6)) for c, v in r.items()})
        out.append(d)
    return out


def main() -> None:
    s = Settings()
    b = pd.read_parquet(ROOT / "data" / "processed" / f"baseline_fl_{YEAR}.parquet")
    b = add_income_deciles(b, settings=s)
    cuts = b.attrs["decile_cutoffs"]
    b["age_band"] = pd.cut(b["HHLDRAGEP"], [a - 0.5 for a, _, _ in AGE_BANDS] + [200], labels=[l for *_, l in AGE_BANDS]).astype(str)
    b["years_in_home"] = b["MV"].map(MV_BANDS)
    b["home_type_label"] = b["home_type"].map(HOME_TYPES)
    b["homestead_label"] = np.where(b["homestead"].fillna(False).astype(bool), "Homestead", "Not homestead")
    b["region"] = b["county_fips"].map(REGION_OF).fillna("North & Panhandle")

    own = owner_mask(b)
    o = b[own]
    w = o["WGTP"]
    hh = b.groupby("income_decile")["WGTP"].sum()

    dec = table(b, "income_decile")
    for c in CLASSES:  # average tax by levy class per decile
        g = o.assign(x=o[f"tax_{c}_{YEAR}"].fillna(0) * w).groupby("income_decile")
        dec[f"avg_tax_{c}"] = pd.concat([g["x"].sum() / g["WGTP"].sum(),
                                         pd.Series({"All owners": (o[f"tax_{c}_{YEAR}"].fillna(0) * w).sum() / w.sum()})])
    dec["households"] = pd.concat([hh, pd.Series({"All owners": hh.sum()})])
    dec["owner_share_of_households"] = dec["owners"] / dec["households"]
    lo = [0] + list(cuts)
    hi = list(cuts) + [None]
    dec_rows = records(dec, list(range(1, 11)))
    for i, r in enumerate(dec_rows[:10]):
        r["income_from"], r["income_to"] = round(float(lo[i])), (None if hi[i] is None else round(float(hi[i])))

    suits, suits_se = suits_with_se(b)
    totals = {c: float((o[f"tax_{c}_{YEAR}"].fillna(0) * w).sum()) for c in CLASSES}
    renters = b["tenure"] != "owner"
    rented_lot = (b["tenure"] == "owner") & b["mh_rented_lot"].fillna(False).astype(bool)

    res = {
        "state": "FL", "year": YEAR, "coverage": s.coverage_label,
        "decile_population": s.decile_population,
        "generated": pd.Timestamp.now().strftime("%Y-%m-%d"),
        "headline": {
            "owner_tax_total": float((o[f"tax_model_{YEAR}"] * w).sum()),
            "owner_tax_total_2025_rates": float((o[f"tax_model_{YEAR}_2025rates"] * w).sum()),
            "by_levy": totals,
            "owners": float(w.sum()),
            "households": float(b["WGTP"].sum()),
            "renter_households": float(b.loc[renters, "WGTP"].sum()),
            "rented_lot_mobile_homes": float(b.loc[rented_lot, "WGTP"].sum()),
            "homestead_owners": float(w[o["homestead"].fillna(False).astype(bool)].sum()),
            "median_tax": weighted_median(o[f"tax_model_{YEAR}"], w),
            "suits_index": suits, "suits_index_se": suits_se,
            "sample_records_owners": int(own.sum()),
        },
        "decile_cutoffs": [round(float(c)) for c in cuts],
        "by_decile": dec_rows,
        "by_age": records(table(b, "age_band"), [l for *_, l in AGE_BANDS]),
        "by_home_type": records(table(b, "home_type_label"), list(HOME_TYPES.values())),
        "by_homestead": records(table(b, "homestead_label"), ["Homestead", "Not homestead"]),
        "by_years_in_home": records(table(b, "years_in_home"), list(dict.fromkeys(MV_BANDS.values()))),
        "by_region": records(table(b, "region"), list(REGIONS) + ["North & Panhandle"]),
        "rate_sources": {
            "county_rate_adopted_share": float(w[o["county_rate_source_2026"] == "adopted (collected)"].sum() / w.sum()),
            "county_rate_predicted_share": float(w[o["county_rate_source_2026"].astype(str).str.startswith("predicted")].sum() / w.sum()),
        },
    }
    dest = ROOT / "data" / "processed" / "results" / f"fl_{YEAR}_status_quo.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(f"wrote {dest}")
    print(json.dumps(res["headline"], indent=1))


if __name__ == "__main__":
    main()
