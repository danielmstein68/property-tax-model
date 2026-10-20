"""Convert downloaded appraisal district rolls to Parquet -> data/processed/tx_rolls/<district>_{props,units}.parquet

Usage:
    python scripts/tx_rolls.py tarrant el_paso      # districts to convert (default: every one downloaded)

PACS-layout districts (ptm.tx.pacs): Tarrant, Travis, El Paso, Galveston, Bell. Harris, Dallas, Fort
Bend, Collin and Williamson have their own layouts (readers in ptm.tx.rolls as they are added).
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ptm.tx.pacs import read_pacs  # noqa: E402

RAW, OUT = ROOT / "data" / "raw" / "tx_rolls", ROOT / "data" / "processed" / "tx_rolls"
PACS = {"tarrant": "000_Tarrant_All_Taxing_Units.zip", "travis": "2026_certified_export_supp0.zip",
        "el_paso": "2026_Certified_Export_Files.zip", "galveston": "2026-CERTIFIED-ROLL-WEB-EXPORT-W-EXPORT-LAYOUT.zip",
        "bell": "2026-Bell-County-Certified-Export-3.zip"}


def main(names: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for n in names or [k for k, f in PACS.items() if (RAW / k / f).exists()]:
        t = time.time()
        p, e = read_pacs(RAW / n / PACS[n])
        p.to_parquet(OUT / f"{n}_props.parquet", index=False)
        e.to_parquet(OUT / f"{n}_units.parquet", index=False)
        hs = (p["hs_exempt"] == "T").sum()
        print(f"{n}: {len(p):,} residential properties, {hs:,} homesteads, {len(e):,} unit rows ({time.time() - t:.0f}s)")


if __name__ == "__main__":
    main(sys.argv[1:])
