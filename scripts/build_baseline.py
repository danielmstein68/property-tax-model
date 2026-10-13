"""Build and save the base-year household file, then print a summary.

Usage:
    python scripts/build_baseline.py

Requires: PUMS files (scripts/download_pums.py --state fl --year 2024 --person), the parcel roll
(scripts/fl_parcels.py), and the inputs/ tables (scripts/aging_factors.py,
scripts/value_factors.py, scripts/fl_soh_history.py).
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ptm.baseline import _path, build_baseline  # noqa: E402


def wmed(x, w):
    m = x.notna()
    x, w = x[m].to_numpy(), w[m].to_numpy()
    o = np.argsort(x)
    c = np.cumsum(w[o])
    return x[o][np.searchsorted(c, c[-1] / 2)]


def main() -> None:
    h = build_baseline()
    w = h["WGTP"]
    o, r = h[h["tenure"] == "owner"], h[h["tenure"] == "renter"]
    print(f"saved {_path(2026)}  ({_path(2026).stat().st_size / 1e6:.1f} MB)")
    print(f"households: {len(h):,} records, {w.sum():,.0f} weighted "
          f"(owners {o['WGTP'].sum():,.0f}, renters {r['WGTP'].sum():,.0f}, "
          f"no rent {h.loc[h['tenure'] == 'no_rent', 'WGTP'].sum():,.0f})")
    rows = [
        ("household income", "hincp_adj", "hincp_aged", h),
        ("owner market value", "VALP", "valp_market_aged", o),
        ("owner just value", None, "valp_jv_aged", o),
        ("owner property tax", "TAXAMT", "taxamt_aged", o),
        ("renter gross rent (monthly)", "grntp_adj", "grntp_aged", r),
    ]
    print(f"\n{'median':30s}{'2024':>12}{'2026':>12}")
    for label, a, b, d in rows:
        va = f"{wmed(d[a], d['WGTP']):,.0f}" if a else ""
        print(f"{label:30s}{va:>12}{wmed(d[b], d['WGTP']):>12,.0f}")
    print(f"\ntotal owner property tax: ${(o['TAXAMT'] * o['WGTP_survey']).sum() / 1e9:.2f}B (2024, survey weights)"
          f" -> ${(o['taxamt_aged'] * o['WGTP']).sum() / 1e9:.2f}B (2026, incl. new homes)")
    missing = {c: int(o[c].isna().sum()) for c in ["valp_jv_aged", "taxamt_aged", "hincp_aged"]}
    print(f"missing values among owners: {missing}")


if __name__ == "__main__":
    main()
