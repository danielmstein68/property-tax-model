"""Take-up checks -> docs/checks/takeup_checks.md

1. Florida 2006-2009: homestead-exempt parcels by county (DOR Data Books, data/raw/fl_databook_hist). Amendment 1 (2008) added
   up to $25,000 of non-school exemption. Did counts jump in 2008 more where the gain was larger, and could we have seen it?
2. Texas 2022-2024: homestead counts by school district from the Comptroller's PVS worksheet export
   (data/raw/tx_cpa): count = value lost to the previous increase step / step size ($10k in the 2022 file, $15k after).
   Rebuild the statewide excess claims in 2024 and the share of non-claiming owner units they imply, against the 4-5.5% the
   Florida take-up setting was calibrated on (docs/research/texas_homestead_takeup.md).

Usage:  python scripts/check_takeup.py
"""
import re
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
HIST = ROOT / "data" / "raw" / "fl_databook_hist"


STATE = {}   # statewide totals rows, filled by fl_counts


def fl_counts() -> pd.DataFrame:
    rows = []
    for yy in ("06", "07", "08", "09"):
        txt = HIST / f"{yy}r.txt"
        if not txt.exists():
            subprocess.run(["pdftotext", "-raw", str(HIST / f"{yy}FLpropdata.pdf"), str(txt)], check=True)
        lines = txt.read_text(encoding="utf-8", errors="ignore").splitlines()
        heads = [i for i, l in enumerate(lines) if re.match(rf"\s*20{yy} Totally and Partially Homestead Exempt Parcels", l)]
        seen = set()
        for h in heads:
            for l in lines[h:h + 80]:
                if l.startswith("** Totals **"):
                    STATE[2000 + int(yy)] = float(l.split()[7].replace(",", ""))
        for h in heads:
            for l in lines[h:h + 60]:
                m = re.match(r"^([A-Za-z][A-Za-z .'-]+?)\s+((?:[\d,]*\.?\d+\s+){6,}[\d,]+)\s*$", l)
                if m:
                    nums = [float(v.replace(",", "")) for v in m.group(2).split()]
                    name = m.group(1).strip()
                    if name not in seen and len(nums) >= 10:
                        seen.add(name)
                        rows.append({"year": 2000 + int(yy), "county": name, "homestead": nums[4], "parcels": nums[-1]})
    return pd.DataFrame(rows)


def tx_counts() -> pd.DataFrame:
    out = []
    for y, step in ((2022, 10_000), (2023, 15_000), (2024, 15_000)):
        d = pd.read_excel(ROOT / "data" / "raw" / "tx_cpa" / f"{y}-final-isd-worksheet-export-detail.xlsx", header=2)
        d = d.dropna(subset=["TU NAME"]).copy()
        d["hs"] = pd.to_numeric(d["LOSS PREV INCR HMSTD"], errors="coerce").fillna(0) / step
        g = d.groupby("TU NAME").agg(hs=("hs", "sum"), county=("COUNTY NAME", "first")).reset_index()
        g["year"] = y
        out.append(g)
    return pd.concat(out, ignore_index=True)


def main() -> None:
    out = ["# Check: take-up of bigger homestead exemptions (2026-10-23)", "", "`scripts/check_takeup.py`", ""]

    f = fl_counts()
    p = f.pivot(index="county", columns="year", values="homestead").dropna()
    allp = f.pivot(index="county", columns="year", values="parcels").reindex(p.index)
    out += ["## 1. Florida 2006-2009 homestead-exempt parcels", ""]
    tot = p.sum()
    out += ["| Year | Parcels | Change |", "|---|---|---|"]
    for y in p.columns:
        chg = "" if y == p.columns[0] else f"{tot[y] / tot[y - 1] - 1:+.2%}"
        out.append(f"| {y} | {tot[y]:,.0f} | {chg} |")
    out += ["", "(57 of 67 counties parsed; the Data Book's own statewide totals row: " + ", ".join(f"{y} {STATE[y]:,.0f}" for y in STATE) + ".)"]
    g07, g08, g09 = (p[2007] / p[2006] - 1), (p[2008] / p[2007] - 1), (p[2009] / p[2008] - 1)
    out += ["", f"Counties parsed: {len(p)} of 67 (Miami-Dade is listed as Dade); missing: {', '.join(sorted(set(f['county']) ^ set(p.index))) or 'none'}.",
            f"Across counties, growth in 2007 {g07.mean():+.2%} (sd {g07.std():.2%}), 2008 {g08.mean():+.2%} (sd {g08.std():.2%}), 2009 {g09.mean():+.2%} (sd {g09.std():.2%}).", ""]
    # gain from the extra exemption: up to $25,000 x the county's non-school millage; proxy = county operating millage
    mh = pd.read_parquet(ROOT / "data" / "processed" / "millage_history.parquet")
    mh = mh[(mh["kind"] == "county") & (mh["year"] == 2008)].copy()
    mh["key"] = mh["name"].str.lower().str.replace(r"[^a-z]", "", regex=True)
    pk = p.copy()
    for y in (2006, 2007, 2008):
        pk[f"all{y}"] = allp[y]
    pk["key"] = p.index.str.lower().str.replace(r"[^a-z]", "", regex=True).str.replace("^dade$", "miamidade", regex=True)
    j = pk.merge(mh[["key", "millage"]], on="key", how="inner")
    j = j.replace([np.inf, -np.inf], np.nan).dropna(subset=[2006, 2007, 2008, "millage"])
    j = j[(j[2006] > 0) & (j[2007] > 0) & (j[2008] > 0) & (j["millage"] > 0)]
    if len(j) > 30:
        gain = 25_000 * j["millage"] / 1000
        d = (j[2008] / j[2007] - 1) - (j[2007] / j[2006] - 1)     # growth in 2008 relative to the county's own 2007 growth
        b = np.polyfit(gain, d, 1)
        r = np.corrcoef(gain, d)[0, 1]
        n = len(j)
        se = (d - np.polyval(b, gain)).std(ddof=2) / (gain.std() * np.sqrt(n - 1))
        # placebo: 2009 had no new exemption; if the same slope appears, it is geography and the crash, not the exemption
        j9 = j[(j[2009] > 0)]
        g9 = gain[j9.index] if hasattr(gain, "loc") else gain
        d9 = (j9[2009] / j9[2008] - 1) - (j9[2008] / j9[2007] - 1)
        b9 = np.polyfit(g9, d9, 1)
        out += [f"Placebo, 2009 against 2008 (no new exemption that year): slope {b9[0] * 100 * 100:+.2f} points of growth per $100 of the same gain measure "
                f"(correlation {np.corrcoef(g9, d9)[0, 1]:+.2f}).", ""]
        # control: the same change in growth of ALL parcels (new construction and the crash hit counties differently)
        dall = (j["all2008"] / j["all2007"] - 1) - (j["all2007"] / j["all2006"] - 1)
        X = np.column_stack([np.ones(n), gain / 1000, dall])  # gain in $1,000s
        beta, *_ = np.linalg.lstsq(X, d, rcond=None)
        resid = d - X @ beta
        cov = np.linalg.inv(X.T @ X) * resid.var(ddof=3)
        out += [f"Same, controlling for the change in growth of all parcels in the county: slope {beta[1] * 10:+.2f} points of growth per $100 of gain "
                f"(se {np.sqrt(cov[1, 1]) * 10:.2f}); the control's coefficient {beta[2]:+.2f}.", ""]
        out += [f"Dose-response across {n} counties: change in homestead-count growth from 2007 to 2008 against the gain from $25,000 more exemption "
                f"(county operating millage x $25,000; mean ${gain.mean():.0f}, range ${gain.min():.0f}-${gain.max():.0f}): "
                f"slope {b[0] * 100 * 100:+.2f} points of growth per $100 of gain (se {se * 100 * 100:.2f}), correlation {r:+.2f}.", ""]
    else:
        out += [f"(Only {len(j)} counties matched to millage history; dose-response skipped.)", ""]
    k = -np.log(1 - 0.20) / 2500
    pred_share = 1 - np.exp(-k * 300)
    out += [f"Model rule (20% at $2,500): a $300 gain gives {pred_share:.1%} of non-claimers; with 0.7-1.0 million non-claimers that is "
            f"{pred_share * 0.7e6 / tot[2007]:.2%}-{pred_share * 1.0e6 / tot[2007]:.2%} of homestead parcels, spread over two years. "
            f"The county-to-county spread in annual growth (sd {g08.std():.1%}) and the statewide swings (2007 {tot[2007] / tot[2006] - 1:+.1%}, "
            f"2008 {tot[2008] / tot[2007] - 1:+.1%}, 2009 {tot[2009] / tot[2008] - 1:+.1%}, the housing crash) are many times larger, "
            "so 2008 can neither support nor reject the rule.", ""]

    t = tx_counts()
    pv = t.pivot(index="TU NAME", columns="year", values="hs").fillna(0)
    out += ["## 2. Texas homestead counts by school district", "",
            "Count = value lost to the previous increase step / step size. Statewide totals should reproduce the research note (5.756M, 5.947M, 6.151M):", "",
            "| Year | Homesteads | Change |", "|---|---|---|"]
    s = pv.sum()
    for y in pv.columns:
        chg = "" if y == 2022 else f"{s[y] / s[y - 1] - 1:+.2%}"
        out.append(f"| {y} | {s[y]:,.0f} | {chg} |")
    both = pv[(pv[2022] > 500) & (pv[2023] > 0) & (pv[2024] > 0)]
    gr, gr0 = both[2024] / both[2023] - 1, both[2023] / both[2022] - 1
    out += ["", f"{len(both)} districts with at least 500 homesteads: growth 2023 to 2024 median {gr.median():+.2%} "
            f"(interquartile {gr.quantile(.25):+.2%} to {gr.quantile(.75):+.2%}); 2022 to 2023 median {gr0.median():+.2%}. "
            f"Correlation of the two growth rates across districts {np.corrcoef(gr, gr0)[0, 1]:+.2f}.", ""]
    owners = {2022: 6_926_616, 2023: 7_048_369, 2024: 7_134_877}   # ACS owner-occupied units (B25003), from the research note
    out += ["Excess claims in 2024 over a trend, and the share of non-claiming owner units they imply (non-claiming = ACS owner units minus claims):", "",
            "| Trend growth assumed | Excess claims | Non-claiming owner units 2023 | Share of non-claimers | Implied share at $2,500 (gain $681 now) |", "|---|---|---|---|---|"]
    nonclaim = owners[2023] - s[2023]
    for label, trend in [(f"owner-unit growth 2024 ({owners[2024] / owners[2023] - 1:.1%})", owners[2024] / owners[2023] - 1),
                         ("homestead growth 2019-21 (1.7%)", 0.017),
                         (f"2023 growth repeated ({s[2023] / s[2022] - 1:.1%})", s[2023] / s[2022] - 1)]:
        ex = s[2023] * (s[2024] / s[2023] - 1 - trend)
        sh = ex / nonclaim
        out.append(f"| {label} | {ex:,.0f} | {nonclaim:,.0f} | {sh:.1%} | {1 - (1 - sh) ** (2500 / 681):.0%} |")
    out += ["", "The research note used 4-5.5% of non-claimers at a $600-680 gain, which gives 16-21% at $2,500. Excess claims of about "
            "2 points of growth (100-130k units) are 9-12% of the roughly 1.1 million non-claiming owner units under the first two trends. "
            "Caveats: growth in 2022-23 (5.3%, 3.3%) was above trend too, partly SB 8 (claiming in the year of purchase) and the 2022 "
            "increase, so 2024 may include delayed response to those; some owner units can't claim (rented lots, entities); Texas needs an application.", ""]
    (ROOT / "docs" / "checks" / "takeup_checks.md").write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
