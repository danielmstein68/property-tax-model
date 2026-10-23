"""Non-residential, non-agricultural parcels from the 2026 NAL zips -> data/processed/fl_nal_2026_nonres.parquet

The main roll pipeline keeps residential parcels only. The 5% assessment cap also binds commercial,
industrial, institutional and other non-agricultural property, so this keeps what the cap check needs
(county, use code, just value, non-school assessed and taxable value, district code, exemption amounts).

Usage:  python scripts/fl_nonres_2026.py
"""
import glob
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASE = ["CO_NO", "DOR_UC", "JV", "AV_NSD", "TV_NSD", "TAX_AUTH_CD", "JV_HMSTD"]


def main() -> None:
    parts = []
    for z in sorted(glob.glob(str(ROOT / "data/raw/fl_nal_2026/*.zip"))):
        with zipfile.ZipFile(z) as zf:
            name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
            with zf.open(name) as fh:
                d = pd.read_csv(fh, dtype=str, low_memory=False, encoding="latin-1")
        uc = pd.to_numeric(d["DOR_UC"], errors="coerce")
        d = d[((uc >= 10) & (uc <= 49)) | ((uc >= 70) & (uc <= 99))]
        ex = [c for c in d if c.startswith("EXMPT_")]
        d = d[[c for c in BASE + ex if c in d]].copy()
        for c in d.columns:
            if c not in ("DOR_UC", "TAX_AUTH_CD"):
                d[c] = pd.to_numeric(d[c], errors="coerce")
        parts.append(d)
        print(Path(z).name, len(d), flush=True)
    out = pd.concat(parts, ignore_index=True)
    out.to_parquet(ROOT / "data/processed/fl_nal_2026_nonres.parquet", index=False)
    print("rows", len(out))


if __name__ == "__main__":
    main()
