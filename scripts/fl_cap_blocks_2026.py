"""Non-homestead assessment-cap blocks by county from the 2026 NAL rolls (all parcels)
-> data/processed/fl_cap_blocks_2026.csv

Usage:
    python scripts/fl_cap_blocks_2026.py

The NAL splits each parcel's value by cap class:
  JV_/AV_NON_HMSTD_RESD   non-homestead residential, 9 units or fewer (Art. VII s. 4(g), 10% cap)
  JV_/AV_RESD_NON_RESD    other non-homestead real property: commercial, industrial, 10+ units
                          (s. 4(h), 10% cap)
Both caps apply to non-school levies only (school levies use just value). For each county and
class: just and assessed value of parcels below just value ("capped") and at just value, and
the share of just value that sold in 2025 (SALE_YR1 = 2025, any sale; resets on the 2026 roll).
Tangible personal property isn't in the NAL (no cap; the rate model keeps it with non-residential
growth). Used by ptm.rate_setting to apply caps (e.g. Amendment 3's 5%) to local tax bases.
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


def county_blocks(zpath: Path) -> dict:
    z = zipfile.ZipFile(zpath)
    name = [n for n in z.namelist() if n.lower().endswith(".csv")][0]
    cols = ["CO_NO", "SALE_YR1"] + [c for pair in CLASSES.values() for c in pair]
    d = pd.read_csv(z.open(name), usecols=cols, dtype=str, low_memory=False)
    num = {c: pd.to_numeric(d[c], errors="coerce").fillna(0).to_numpy() for c in cols if c != "CO_NO"}
    sold = num["SALE_YR1"] == 2025
    out = {"county_fips": fl_dor_to_fips(pd.Series([int(d["CO_NO"].iloc[0])])).iloc[0], "parcels": len(d)}
    for k, (jc, ac) in CLASSES.items():
        jv, av = num[jc], num[ac]
        capped = (jv > 0) & (av < jv - 1)
        at = (jv > 0) & ~capped
        out[f"{k}_jv_capped"] = jv[capped].sum()
        out[f"{k}_av_capped"] = av[capped].sum()
        out[f"{k}_jv_at"] = jv[at].sum()
        out[f"{k}_av_at"] = av[at].sum()
        out[f"{k}_sold_share"] = jv[sold & (jv > 0)].sum() / max(jv.sum(), 1)
    return out


def main() -> None:
    rows = []
    for zp in sorted(RAW.glob("*.zip")):
        rows.append(county_blocks(zp))
        r = rows[-1]
        print(f"{zp.name:45s} nh gap {1 - (r['nh_av_capped'] + r['nh_av_at']) / max(r['nh_jv_capped'] + r['nh_jv_at'], 1):6.1%}"
              f"  nr gap {1 - (r['nr_av_capped'] + r['nr_av_at']) / max(r['nr_jv_capped'] + r['nr_jv_at'], 1):6.1%}", flush=True)
    df = pd.DataFrame(rows).sort_values("county_fips")
    df.to_csv(DEST, index=False)
    t = df.sum(numeric_only=True)
    for k in CLASSES:
        jv, av = t[f"{k}_jv_capped"] + t[f"{k}_jv_at"], t[f"{k}_av_capped"] + t[f"{k}_av_at"]
        sold = np.average(df[f"{k}_sold_share"], weights=df[f"{k}_jv_capped"] + df[f"{k}_jv_at"])
        print(f"{k}: just ${jv / 1e9:,.0f}B, assessed ${av / 1e9:,.0f}B (gap {1 - av / jv:.1%}); "
              f"capped parcels' just value {t[f'{k}_jv_capped'] / jv:.0%} of the class; sold in 2025 {sold:.1%}")
    print(f"wrote {DEST} ({len(df)} counties)")


if __name__ == "__main__":
    main()
