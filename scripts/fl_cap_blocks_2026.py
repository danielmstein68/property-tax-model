"""Non-homestead assessment-cap blocks by county from the 2026 NAL rolls (all parcels)
-> data/processed/fl_cap_blocks_2026.csv

Usage:
    python scripts/fl_cap_blocks_2026.py

The NAL splits each parcel's value by cap class:
  JV_/AV_NON_HMSTD_RESD   non-homestead residential, 9 units or fewer (Art. VII s. 4(g), 10% cap)
  JV_/AV_RESD_NON_RESD    other non-homestead real property: commercial, industrial, 10+ units
                          (s. 4(h), 10% cap)
Both caps apply to non-school levies only (school levies use just value). For each county, class
and band of assessed / just value (BANDS; the last band is "at just value"): just and assessed value
of the parcels in it. Each band catches up to just value separately in ptm.rate_setting, so parcels
far below just value take years, as they do (one block per county caught up too fast: see
docs/checks/projection_vs_rec_2026.md). Also each county and class's share of just value sold in
2025 (SALE_YR1 = 2025, any sale; resets on the 2026 roll). Tangible personal property isn't in the
NAL (no cap). Long format: county_fips, cls, band, jv, av, sold_share.
"""

import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ptm.geo import fl_dor_to_fips  # noqa: E402

RAW = ROOT / "data" / "raw" / "fl_nal_2026"
DEST = ROOT / "data" / "processed" / "fl_cap_blocks_2026.csv"
CLASSES = {"nh": ("JV_NON_HMSTD_RESD", "AV_NON_HMSTD_RESD"), "nr": ("JV_RESD_NON_RESD", "AV_RESD_NON_RESD")}
BANDS = [0.0, 0.3, 0.4, 0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.93, 0.96, 0.985, 0.9995]   # last: at just value


def county_blocks(zpath: Path) -> list[dict]:
    z = zipfile.ZipFile(zpath)
    name = [n for n in z.namelist() if n.lower().endswith(".csv")][0]
    cols = ["CO_NO", "SALE_YR1"] + [c for pair in CLASSES.values() for c in pair]
    d = pd.read_csv(z.open(name), usecols=cols, dtype=str, low_memory=False)
    num = {c: pd.to_numeric(d[c], errors="coerce").fillna(0).to_numpy() for c in cols if c != "CO_NO"}
    sold = num["SALE_YR1"] == 2025
    fips = fl_dor_to_fips(pd.Series([int(d["CO_NO"].iloc[0])])).iloc[0]
    rows = []
    for k, (jc, ac) in CLASSES.items():
        jv, av = num[jc], np.minimum(num[ac], num[jc])
        ok = jv > 0
        ratio = np.where(ok, av / np.where(ok, jv, 1), 1.0)
        band = np.digitize(ratio, BANDS[1:])          # 0 .. len(BANDS) - 1
        share = jv[sold & ok].sum() / max(jv[ok].sum(), 1)
        for b in range(len(BANDS)):
            m = ok & (band == b)
            rows.append({"county_fips": fips, "cls": k, "band": b, "jv": jv[m].sum(), "av": av[m].sum(),
                         "sold_share": share})
    return rows


def main() -> None:
    rows = []
    for zp in sorted(RAW.glob("*.zip")):
        rows += county_blocks(zp)
        print(zp.name, flush=True)
    df = pd.DataFrame(rows).sort_values(["county_fips", "cls", "band"])
    df.to_csv(DEST, index=False)
    for k in CLASSES:
        s = df[df.cls == k]
        t = s.groupby("band")[["jv", "av"]].sum()
        print(f"{k}: just ${t.jv.sum() / 1e9:,.0f}B, assessed ${t.av.sum() / 1e9:,.0f}B (gap {1 - t.av.sum() / t.jv.sum():.1%})")
        print("  share of just value by band:", ", ".join(f"{BANDS[b]:.2f}+: {t.jv[b] / t.jv.sum():.0%}" for b in t.index))
    print(f"wrote {DEST} ({df.county_fips.nunique()} counties)")


if __name__ == "__main__":
    main()
