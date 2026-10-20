"""Texas 2026 results for the display -> data/processed/results/tx_2026_status_quo.json

Usage:
    python scripts/tx_results.py        # needs data/processed/tx_baseline_2026.parquet (python -m ptm.tx.project)

Owner households (homesteads from ptm.tx.baseline; owners who don't claim a homestead pay full tax with
no exemptions at their county's average combined rate on homesteads, provisional), income deciles over
all Texas households (renters at $0 tax, as for Florida), by age, homestead, region and over-65 status;
Suits index; projections summary from tx_projections.json.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ptm.results import suits_index, weighted_cutoffs  # noqa: E402
from ptm.tx.rolls import DISTRICTS  # noqa: E402
from ptm.tx.survey import tx_households  # noqa: E402

PROC = ROOT / "data" / "processed"
METROS = {"Houston": ["201", "157", "339", "039", "167", "291", "071", "473", "015"],
          "Dallas-Fort Worth": ["113", "439", "085", "121", "397", "251", "257", "139", "367", "221", "231", "497"],
          "Austin": ["453", "491", "209", "055", "021"], "San Antonio": ["029", "091", "187", "325", "013", "259", "019", "493"],
          "El Paso": ["141", "229"], "Rio Grande Valley": ["215", "061", "489", "427"]}
METRO_OF = {f: m for m, fs in METROS.items() for f in fs}
AGE = [(0, 44, "Under 45"), (45, 64, "45–64"), (65, 74, "65–74"), (75, 200, "75 and over")]


def main() -> None:
    o = pd.read_parquet(PROC / "tx_baseline_2026.parquet")
    rows = pd.read_parquet(PROC / "tx_baseline_2026_units.parquet")
    allh = tx_households()
    cut = weighted_cutoffs(allh["hincp_aged"].fillna(0), allh["WGTP"], 10)
    # owners without a homestead exemption: full tax at the county's average combined homestead rate
    hs = o[o["homestead"]]
    rate = rows.assign(r=rows["mo_rate"].fillna(0) + rows["is_rate"].fillna(0)).groupby("hid")["r"].sum()
    cty_rate = pd.Series(rate.reindex(hs.index).to_numpy(), index=hs.index).groupby(hs["county_fips_tax"]).median()
    nh = ~o["homestead"]
    o.loc[nh, "tax_total"] = o.loc[nh, "market"] * o.loc[nh, "county_fips_tax"].map(cty_rate).fillna(cty_rate.median()) / 100
    o["tax_total"] = o["tax_total"].fillna(0)
    o["income"] = o["hincp_aged"].fillna(0)
    o["decile"] = np.searchsorted(cut, o["income"], side="right") + 1
    allh["decile"] = np.searchsorted(cut, allh["hincp_aged"].fillna(0), side="right") + 1
    w = o["WGTP"]
    tot = float((o["tax_total"] * w).sum())

    def grp(by):
        out = []
        for k, g in o.groupby(by):
            gw = g["WGTP"]
            inc = float((g["income"].clip(lower=0) * gw).sum())
            t = float((g["tax_total"] * gw).sum())
            out.append({"group": str(k), "owners": float(gw.sum()), "avg_tax": t / gw.sum(),
                        "median_tax": float(np.interp(0.5, np.cumsum(gw.to_numpy()[np.argsort(g["tax_total"].to_numpy())]) / gw.sum(), np.sort(g["tax_total"].to_numpy()))),
                        "tax_share_of_income": t / inc if inc > 0 else None, "share_of_owner_tax": t / tot,
                        "avg_value": float(np.average(g["market"], weights=gw)), "avg_income": float(np.average(g["income"], weights=gw))})
        return out

    o["age_group"] = pd.cut(o["HHLDRAGEP"], [a - 1 for a, _, _ in AGE] + [200], labels=[l for _, _, l in AGE]).astype(str)
    o["region"] = o["county_fips_tax"].map(METRO_OF).fillna("Rest of Texas")
    o["hs"] = np.where(o["homestead"], "Homestead", "No homestead exemption")
    o["senior"] = np.where(o["over65_or_disabled"].fillna(False), "65+ or disabled (homestead)", "Other owners")
    dec = grp("decile")
    hh_dec = allh.groupby("decile")["WGTP"].sum()
    for d in dec:
        d["households"] = float(hh_dec.get(int(d["group"]), 0))
        d["owner_share_of_households"] = d["owners"] / d["households"] if d["households"] else None
        d["avg_tax_per_household"] = d["avg_tax"] * d["owner_share_of_households"] if d["households"] else None
    roll = {DISTRICTS[d][0] for d in DISTRICTS}
    res = {"state": "TX", "year": 2026, "coverage": "owners only", "decile_population": "all_households",
           "generated": pd.Timestamp.today().strftime("%Y-%m-%d"),
           "headline": {"owner_tax_total": tot, "owners": float(w.sum()), "homestead_owners": float(w[o["homestead"]].sum()),
                        "households": float(allh["WGTP"].sum()),
                        "median_tax": float(np.interp(0.5, np.cumsum(w.to_numpy()[np.argsort(o["tax_total"].to_numpy())]) / w.sum(), np.sort(o["tax_total"].to_numpy()))),
                        "suits_index": float(suits_index(o["income"].to_numpy(), o["tax_total"].to_numpy(), w.to_numpy())),
                        "share_in_roll_counties": float(w[o["homestead"] & o["county_fips_tax"].isin(roll)].sum() / w[o["homestead"]].sum()),
                        "by_class": {c: float((o[f"tax_{c}"].fillna(0) * w).sum()) for c in ["school", "county", "city", "college", "hospital", "special"] if f"tax_{c}" in o}},
           "decile_cutoffs": [float(c) for c in cut], "by_decile": dec,
           "by_age": grp("age_group"), "by_region": grp("region"), "by_homestead": grp("hs"), "by_senior": grp("senior")}
    proj = PROC / "results" / "tx_projections.json"
    if proj.exists():
        res["projections"] = json.loads(proj.read_text(encoding="utf-8"))
    dest = PROC / "results" / "tx_2026_status_quo.json"
    dest.write_text(json.dumps(res, indent=1), encoding="utf-8")
    h = res["headline"]
    print(f"owner tax ${h['owner_tax_total'] / 1e9:.2f}B, {h['owners']:,.0f} owners, median ${h['median_tax']:,.0f}, Suits {h['suits_index']:.3f}")
    for d in dec:
        print(f"  decile {d['group']:>2}: avg ${d['avg_tax']:7,.0f}  share of income {d['tax_share_of_income'] or 0:6.1%}  share of tax {d['share_of_owner_tax']:5.1%}")
    print("wrote", dest)


if __name__ == "__main__":
    main()
