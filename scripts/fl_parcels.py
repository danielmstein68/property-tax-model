"""Download and process every Florida county's NAL parcel tax roll.

Usage:
    python scripts/fl_parcels.py                  # all counties in the manifest
    python scripts/fl_parcels.py --county Calhoun --county Dade
    python scripts/fl_parcels.py --redo           # reprocess even if already done

Reads manifests/fl_nal_2026.csv (county, DOR county number, roll stage, file name).
The DOR directory pages need a browser, so the manifest is collected by hand;
refresh it when counties move from preliminary (P) to final (F).

For each county:
  1. download the zip (curl with retry and resume; the DOR server drops connections),
  2. verify the zip,
  3. process residential parcels with ptm.parcels.process_nal (anonymous owner IDs, no names),
  4. save data/processed/fl_nal_2026/co<NN>_<stage>.parquet,
  5. delete the extracted CSV (the zip is kept unless --delete-zip),
  6. append a row of checks to data/processed/fl_nal_2026/_checks.csv.
"""

import argparse
import csv
import subprocess
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ptm.parcels import process_nal  # noqa: E402

BASE = "https://floridarevenue.com/property/dataportal/Documents/PTO Data Portal/Tax Roll Data Files/NAL"
MANIFEST = ROOT / "manifests" / "fl_nal_2026.csv"
RAW = ROOT / "data" / "raw" / "fl_nal_2026"
OUT = ROOT / "data" / "processed" / "fl_nal_2026"
CHECKS = OUT / "_checks.csv"
TOPCODE_VALP_FL_2024 = 6_471_000


def download(url: str, dest: Path, attempts: int = 10) -> None:
    """curl with resume; retry until the zip verifies."""
    for i in range(1, attempts + 1):
        subprocess.run(["curl", "-sS", "-L", "-C", "-", "--speed-limit", "10000", "--speed-time", "60",
                        "-o", str(dest), url], check=False)
        try:
            with zipfile.ZipFile(dest) as z:
                if z.testzip() is None:
                    return
        except (zipfile.BadZipFile, FileNotFoundError):
            pass
        print(f"    attempt {i} incomplete, resuming...")
        time.sleep(5)
    raise RuntimeError(f"download failed after {attempts} attempts: {url}")


def checks(row: dict, raw_rows: int, df, dest: Path) -> dict:
    h = df[df["homestead"]]
    out = {
        "county": row["county"], "co_no": row["co_no"], "stage": row["stage"],
        "processed_at": datetime.now().isoformat(timespec="seconds"),
        "raw_parcels": raw_rows,
        "residential_parcels": len(df),
        "homestead_parcels": len(h),
        "homestead_share": round(len(h) / len(df), 3) if len(df) else None,
        "jv_total": int(df["JV"].sum()),
        "jv_homestead_total": int(h["JV"].sum()),
        "tv_sd_total": int(df["TV_SD"].sum()),
        "tv_nsd_total": int(df["TV_NSD"].sum()),
        "land_value_total": int(df["LND_VAL"].sum()),
        "homestead_jv_median": int(h["JV"].median()) if len(h) else None,
        "homestead_av_jv_median": round(float((h["AV_SD"] / h["JV"]).median()), 3) if len(h) else None,
        "homestead_jv_ge_topcode": int((h["JV"] >= TOPCODE_VALP_FL_2024).sum()),
        "homestead_jv_max": int(h["JV"].max()) if len(h) else None,
        "owners": int(df["owner_id"].nunique()),
        "owners_10plus": int((df.groupby("owner_id").size() >= 10).sum()),
        "own_zip_missing_share": round(float(df["own_zip_differs"].isna().mean()), 3),
        # Rule checks: these should be zero
        "err_av_gt_jv": int((df["AV_SD"] > df["JV"]).sum()),
        "err_tv_gt_av": int((df["TV_SD"] > df["AV_SD"]).sum()),
        "err_missing_jv": int(df["JV"].isna().sum()),
        "parquet_mb": round(dest.stat().st_size / 1e6, 2),
    }
    warn = []
    if out["residential_parcels"] == 0:
        warn.append("no residential parcels")
    if out["homestead_share"] is not None and not 0.1 <= out["homestead_share"] <= 0.8:
        warn.append("homestead share unusual")
    if out["err_av_gt_jv"] or out["err_tv_gt_av"] or out["err_missing_jv"]:
        warn.append("value rule violations")
    out["warnings"] = "; ".join(warn)
    return out


def write_check(rec: dict) -> None:
    new = not CHECKS.exists()
    with open(CHECKS, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rec))
        if new:
            w.writeheader()
        w.writerow(rec)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--county", action="append", help="county name as in the manifest (repeatable)")
    p.add_argument("--redo", action="store_true")
    p.add_argument("--delete-zip", action="store_true")
    args = p.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST) as fh:
        rows = list(csv.DictReader(fh))
    if args.county:
        rows = [r for r in rows if r["county"] in args.county]

    failed = []
    for n, row in enumerate(rows, 1):
        co = int(row["co_no"])
        dest = OUT / f"co{co:02d}_{row['stage']}.parquet"
        label = f"[{n}/{len(rows)}] {row['county']} ({row['stage']})"
        if dest.exists() and not args.redo:
            print(f"{label}: done already, skipping")
            continue
        try:
            stage_dir = "2026F" if row["stage"] == "F" else "2026P"
            zpath = RAW / row["file"].replace(" ", "_")
            print(f"{label}: downloading")
            download(f"{BASE}/{stage_dir}/{quote(row['file'])}".replace(" ", "%20"), zpath)
            with zipfile.ZipFile(zpath) as z:
                csv_name = next(m for m in z.namelist() if m.lower().endswith(".csv"))
                z.extract(csv_name, RAW)
            csv_path = RAW / csv_name
            with open(csv_path, encoding="latin-1") as fh:
                raw_rows = sum(1 for _ in fh) - 1
            print(f"{label}: processing {raw_rows:,} parcels")
            df = process_nal(csv_path)
            df.to_parquet(dest, index=False)
            rec = checks(row, raw_rows, df, dest)
            write_check(rec)
            csv_path.unlink()
            if args.delete_zip:
                zpath.unlink()
            print(f"{label}: {rec['residential_parcels']:,} residential, "
                  f"{rec['homestead_parcels']:,} homestead, {rec['parquet_mb']} MB"
                  + (f"  WARNING: {rec['warnings']}" if rec["warnings"] else ""))
        except Exception as e:  # keep going; report at the end
            print(f"{label}: FAILED: {e}")
            failed.append(row["county"])

    print(f"\nFinished. {len(rows) - len(failed)} ok, {len(failed)} failed"
          + (f": {', '.join(failed)}" if failed else ""))


if __name__ == "__main__":
    main()
