"""Read appraisal district exports in the PACS / True Prodigy "Appraisal Export" layout (Legacy 8.0.x).

Used by Tarrant, Travis, El Paso, Galveston and Bell (and, if their files arrive, Bexar and
Montgomery). Two fixed-width files matter:
  APPRAISAL_INFO.TXT         one row per property x owner: values, cap losses, exemption flags and
                             qualifying years, state category codes, owner address state
  APPRAISAL_ENTITY_INFO.TXT  one row per property x owner x taxing unit: that unit's market,
                             appraised and taxable value, homestead (state and local), over-65,
                             disabled, disabled-veteran amounts, and the over-65/disabled freeze
Field positions: inputs/tx_pacs_layout_8.0.33.csv (from the layout workbook; 8.0.34 keeps these
positions). Only certified records (sup_num 0) are kept unless all=True.
"""

import io
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
LAYOUT = ROOT / "inputs" / "tx_pacs_layout_8.0.33.csv"
# Residential state property categories: A single-family, B multifamily, E rural with home, M mobile homes
RESIDENTIAL = ("A", "B", "E", "M")


def _specs(file: str) -> tuple[list[tuple[int, int]], list[str], set[str]]:
    lay = pd.read_csv(LAYOUT)
    lay = lay[lay["file"] == file].sort_values("start")
    return ([(int(s) - 1, int(e)) for s, e in zip(lay["start"], lay["end"])], lay["field"].tolist(),
            set(lay.loc[lay["numeric"], "field"]))


def _member(z: zipfile.ZipFile, stem: str) -> str:
    """The archive member for a PACS file (names vary: APPRAISAL_INFO.TXT, 2026-07-18_..._APPRAISAL_INFO.TXT)."""
    hits = [n for n in z.namelist() if Path(n).name.upper().endswith(stem + ".TXT")]
    if not hits:
        raise FileNotFoundError(f"{stem}.TXT not in {z.filename}")
    return max(hits, key=lambda n: z.getinfo(n).file_size)


def _read(zip_path: Path, stem: str, chunksize: int = 500_000, keep=None) -> pd.DataFrame:
    """Read one PACS fixed-width file from a (possibly nested) ZIP, chunk by chunk; `keep` filters each chunk."""
    colspecs, names, numeric = _specs(stem)
    parts = []
    with zipfile.ZipFile(zip_path) as z:
        try:
            member, inner = _member(z, stem), None
        except FileNotFoundError:   # export zipped inside the download (Bell, Galveston)
            inner = next(n for n in z.namelist() if n.lower().endswith(".zip"))
        src = z.open(member) if inner is None else zipfile.ZipFile(io.BytesIO(z.read(inner))).open(
            _member(zipfile.ZipFile(io.BytesIO(z.read(inner))), stem))
        with src as f:
            text = io.TextIOWrapper(f, encoding="latin-1", newline="")
            for chunk in pd.read_fwf(text, colspecs=colspecs, names=names, dtype=str, chunksize=chunksize):
                for c in numeric:
                    chunk[c] = pd.to_numeric(chunk[c], errors="coerce")
                if keep is not None:
                    chunk = keep(chunk)
                parts.append(chunk)
    return pd.concat(parts, ignore_index=True)


def read_pacs(zip_path: Path, all_sups: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(properties, property x taxing unit) for residential real property in a PACS export."""
    def props(c):
        c = c[(c["prop_type_cd"].str.strip() == "R") | (c["prop_type_cd"].str.strip() == "MH")]
        st = c["imprv_state_cd"].fillna(c["land_state_cd"]).fillna("").str.strip().str.upper()
        c = c[st.str.startswith(RESIDENTIAL)]
        return c if all_sups else c[c["sup_num"] == 0]
    p = _read(zip_path, "APPRAISAL_INFO", keep=props)
    ids = set(p["prop_id"])
    e = _read(zip_path, "APPRAISAL_ENTITY_INFO",
              keep=lambda c: c[c["prop_id"].isin(ids) & (all_sups | (c["sup_num"] == 0))])
    for c in ["entity_cd", "entity_name", "imprv_state_cd", "land_state_cd", "hs_exempt", "ov65_exempt",
              "dp_exempt", "py_addr_state", "situs_city", "situs_zip"]:
        for d in (p, e):
            if c in d:
                d[c] = d[c].str.strip()
    return p, e
