"""Out-of-state owners' second homes from the 2026 rolls -> data/processed/fl_second_homes_2026.parquet

Usage:
    python scripts/fl_second_homes_2026.py

The pool for "second-home owners switch legal residence to Florida" (projection setting
`residency_switch`): non-homestead single-family homes, condos and mobile homes (DOR use codes
001, 004, 002) whose owner's mailing address is in another US state (ptm.parcels.out_of_state),
excluding business owners. One row per parcel: county FIPS, non-school and school assessed and
taxable value (2026). Owner identities are not stored (the processed rolls hold none).
"""

import glob
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ptm.geo import fl_dor_to_fips  # noqa: E402
from ptm.parcels import out_of_state  # noqa: E402

DEST = ROOT / "data" / "processed" / "fl_second_homes_2026.parquet"
CODES = {"001", "002", "004"}


def main() -> None:
    parts = []
    for f in sorted(glob.glob(str(ROOT / "data" / "processed" / "fl_nal_2026" / "co*.parquet"))):
        d = pd.read_parquet(f, columns=["CO_NO", "DOR_UC", "homestead", "own_state", "own_business",
                                        "JV", "AV_NSD", "AV_SD", "TV_NSD", "TV_SD"])
        d = d[~d["homestead"].fillna(False).astype(bool) & d["DOR_UC"].astype(str).str.zfill(3).isin(CODES)
              & out_of_state(d["own_state"]) & ~d["own_business"].fillna(False).astype(bool)]
        d = d.assign(county_fips=fl_dor_to_fips(d["CO_NO"]))
        parts.append(d[["county_fips", "JV", "AV_NSD", "AV_SD", "TV_NSD", "TV_SD"]])
    out = pd.concat(parts, ignore_index=True)
    out.to_parquet(DEST, index=False)
    print(f"wrote {DEST}: {len(out):,} parcels; just value ${out.JV.sum() / 1e9:,.0f}B, "
          f"non-school taxable ${out.TV_NSD.sum() / 1e9:,.0f}B; median assessed ${out.AV_NSD.median():,.0f}")
    print(out.groupby("county_fips").size().sort_values(ascending=False).head(8).to_string())


if __name__ == "__main__":
    main()
