"""Read appraisal district exports in the PACS / True Prodigy "Appraisal Export" layout (Legacy 8.0.x).

Used by Tarrant, Travis, El Paso, Galveston and Bell (and, if their files arrive, Bexar and
Montgomery). Two fixed-width files matter:
  APPRAISAL_INFO.TXT         one row per property x owner: values, cap losses, exemption flags and
                             qualifying years, state category codes, owner address state
  APPRAISAL_ENTITY_INFO.TXT  one row per property x owner x taxing unit: that unit's market,
                             appraised and taxable value, homestead (state and local), over-65,
                             disabled, disabled-veteran amounts, and the over-65/disabled freeze
Field positions: inputs/tx_pacs_layout_8.0.33.csv (from the layout workbook; 8.0.34 keeps these
positions). Every line has the same length (El Paso: 9,716 and 3,007 bytes with CRLF), so blocks of
lines are read as a 2-D byte array and fields sliced by position: a 9 GB file reads in minutes.
Exports "with supplements" carry each property once at its latest version (sup_num 0 = as certified,
higher = a later supplement; El Paso: 452,086 properties, all unique), so every property row is kept and
taxing-unit rows are matched on (prop_id, sup_num).
Units: values in whole dollars; freeze_ceiling in cents (El Paso ISD: read as dollars it is ~0.41 of the
home's current school tax, as expected for ceilings set years ago and cut by compression). Only some
over-65/disabled homes carry a ceiling (El Paso ISD: 29% of those with school taxable value), probably
those where it binds; checked against the PVS freeze loss when calibrating.
"""

import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
LAYOUT = ROOT / "inputs" / "tx_pacs_layout_8.0.33.csv"
# Residential state property categories: A single-family, B multifamily, E rural with home, M mobile homes
RESIDENTIAL = ("A", "B", "E", "M")


def _layout(file: str) -> pd.DataFrame:
    lay = pd.read_csv(LAYOUT)
    return lay[lay["file"] == file].sort_values("start")


def _member(z: zipfile.ZipFile, stem: str) -> str:
    """The archive member for a PACS file (names vary: APPRAISAL_INFO.TXT, 2026-10-13_..._APPRAISAL_INFO.TXT)."""
    hits = [n for n in z.namelist() if Path(n).name.upper().endswith(stem + ".TXT")]
    if not hits:
        raise FileNotFoundError(f"{stem}.TXT not in {z.filename}")
    return max(hits, key=lambda n: z.getinfo(n).file_size)


def _decode(block: np.ndarray, lay: pd.DataFrame) -> pd.DataFrame:
    out = {}
    for f, s, e, num in zip(lay["field"], lay["start"], lay["end"], lay["numeric"]):
        raw = block[:, int(s) - 1:int(e)].copy().view(f"S{int(e) - int(s) + 1}").ravel()
        txt = pd.Series(np.char.strip(raw.astype("U"))) if not num else None
        if num:
            out[f] = pd.to_numeric(pd.Series(np.char.strip(raw).astype("U")), errors="coerce")
        else:
            out[f] = txt.replace("", None)
    return pd.DataFrame(out)


def _read(src, stem: str, keep=None, lines_per_block: int = 100_000) -> pd.DataFrame:
    lay = _layout(stem)
    with zipfile.ZipFile(src) as z, z.open(_member(z, stem)) as f:
        first = f.readline()
        width = len(first)
        parts, buf = [], first
        while True:
            data = buf + f.read(width * lines_per_block - len(buf))
            buf = b""
            if not data:
                break
            n = len(data) // width
            block = np.frombuffer(data[:n * width], dtype="S1").reshape(n, width).view(np.uint8)
            d = _decode(block, lay)
            if keep is not None:
                d = keep(d)
            parts.append(d)
            if len(data) < width * lines_per_block:
                break
    return pd.concat(parts, ignore_index=True)


def read_pacs(zip_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(properties, property x taxing unit) for residential real property in a PACS export."""
    def props(c):
        st = c["imprv_state_cd"].fillna(c["land_state_cd"]).fillna("").str.upper()
        return c[c["prop_type_cd"].isin(["R", "MH"]) & st.str.startswith(RESIDENTIAL)]
    p = _read(zip_path, "APPRAISAL_INFO", keep=props)
    p = p.sort_values("sup_num").drop_duplicates("prop_id", keep="last")
    key = set(zip(p["prop_id"], p["sup_num"]))
    e = _read(zip_path, "APPRAISAL_ENTITY_INFO",
              keep=lambda c: c[[k in key for k in zip(c["prop_id"], c["sup_num"])]])
    e["freeze_ceiling"] = e["freeze_ceiling"] / 100     # cents -> dollars
    return p.reset_index(drop=True), e.reset_index(drop=True)
