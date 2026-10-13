"""Process Florida DOR NAL (Name-Address-Legal) parcel tax roll files.

One NAL CSV per county. We keep residential parcels (DOR use codes 000-009)
and the columns the model needs, and drop personal data:
  - owner and fiduciary names and mailing addresses are dropped;
  - each owner name becomes an anonymous `owner_id` (keyed hash), so parcels
    with the same owner can be linked (e.g. homes per landlord) without
    storing who the owner is;
  - the owner's mailing address is reduced to flags (out of state,
    mailing ZIP differs from the property ZIP, business or trust owner).
The property's own (site) address and census block group are kept for
locational analysis.

Field names follow the DOR NAL layout; check the current year's user guide,
since field numbers can change between years.
"""

import re
from pathlib import Path

import pandas as pd

RESIDENTIAL_USE_CODES = [f"{i:03d}" for i in range(10)]  # 000 vacant residential ... 009

ID_COLS = ["CO_NO", "PARCEL_ID", "ASMNT_YR", "DOR_UC", "PA_UC", "CENSUS_BK",
           "PHY_ADDR1", "PHY_ADDR2", "PHY_CITY", "PHY_ZIPCD", "MKT_AR", "NBRHD_CD", "TAX_AUTH_CD"]
VALUE_COLS = ["JV", "AV_SD", "AV_NSD", "TV_SD", "TV_NSD",
              "JV_HMSTD", "AV_HMSTD", "JV_NON_HMSTD_RESD", "AV_NON_HMSTD_RESD",
              "LND_VAL", "LND_SQFOOT", "SPEC_FEAT_VAL", "NCONST_VAL"]
BUILDING_COLS = ["ACT_YR_BLT", "EFF_YR_BLT", "TOT_LVG_AREA", "NO_BULDNG", "NO_RES_UNTS"]
SALE_COLS = ["SALE_PRC1", "SALE_YR1", "SALE_MO1", "QUAL_CD1",
             "SALE_PRC2", "SALE_YR2", "SALE_MO2", "QUAL_CD2"]
PORTABILITY_COLS = ["ASS_TRNSFR_FG", "ASS_DIF_TRNS", "YR_VAL_TRNSF"]
NUMERIC_COLS = VALUE_COLS + BUILDING_COLS + [c for c in SALE_COLS if not c.startswith("QUAL")] + ["ASS_DIF_TRNS", "YR_VAL_TRNSF"]

BUSINESS_RE = re.compile(r"\b(?:LLC|L L C|INC|CORP|CORPORATION|COMPANY|LP|LLP|LTD|PARTNERS(?:HIP)?|"
                         r"HOLDINGS?|PROPERTIES|INVESTMENTS?|BANK|ASSN|ASSOCIATION|FUND|REIT)\b")
TRUST_RE = re.compile(r"\b(?:TRUST|TRUSTEE|TR|REV TR|LIV TR)\b")


SALT_FILE = Path(__file__).resolve().parents[1] / "data" / ".owner_id_salt"


def _owner_salt() -> bytes:
    """Secret key for owner IDs, created once and kept in the git-ignored data folder.

    Owner names are public in the tax roll, so a plain hash could be reversed by
    hashing every name. A secret key prevents that. Every county must use the same
    key so the same owner gets the same ID statewide.
    """
    import secrets

    if not SALT_FILE.exists():
        SALT_FILE.parent.mkdir(parents=True, exist_ok=True)
        SALT_FILE.write_text(secrets.token_hex(32))
    return SALT_FILE.read_text().strip().encode()


def normalize_owner_name(name: pd.Series) -> pd.Series:
    """Standardize spelling so the same owner matches across parcels."""
    s = name.fillna("").str.upper()
    s = s.str.replace(r"L\.?\s?L\.?\s?C\.?", "LLC", regex=True)
    s = s.str.replace(r"[^\w\s&]", " ", regex=True)
    return s.str.replace(r"\s+", " ", regex=True).str.strip()


def owner_ids(name: pd.Series) -> pd.Series:
    """Anonymous owner ID: keyed hash of the normalized name (16 hex chars)."""
    import hashlib
    import hmac

    key = _owner_salt()
    norm = normalize_owner_name(name)
    return norm.map(lambda n: hmac.new(key, n.encode(), hashlib.sha256).hexdigest()[:16] if n else pd.NA)


def owner_flags(nal: pd.DataFrame) -> pd.DataFrame:
    """Reduce owner name and mailing address to an anonymous ID and flags."""
    name = nal["OWN_NAME"].fillna("").str.upper()
    own_state = nal["OWN_STATE"].fillna("").str.upper().str.strip()
    own_zip = nal["OWN_ZIPCD"].fillna("").astype(str).str[:5]
    phy_zip = nal["PHY_ZIPCD"].fillna("").astype(str).str[:5]
    return pd.DataFrame({
        "owner_id": owner_ids(nal["OWN_NAME"]),
        "own_state": own_state.replace("", pd.NA),
        "own_out_of_state": (own_state != "") & (own_state != "FL"),
        # Unknown (NA) when either ZIP is missing: some counties (e.g. Miami-Dade) leave
        # most owner ZIPs blank, so treating blanks as "same ZIP" would be wrong.
        "own_zip_differs": (own_zip != phy_zip).astype("boolean").mask((own_zip == "") | (phy_zip == "")),
        "own_business": name.str.contains(BUSINESS_RE),
        "own_trust": name.str.contains(TRUST_RE),
    }, index=nal.index)


def process_nal(csv_path: str | Path) -> pd.DataFrame:
    """Read one county NAL CSV and return residential parcels, de-identified."""
    nal = pd.read_csv(csv_path, dtype=str, low_memory=False)
    nal["DOR_UC"] = nal["DOR_UC"].str.zfill(3)
    nal = nal[nal["DOR_UC"].isin(RESIDENTIAL_USE_CODES)]

    exempt_cols = [c for c in nal if c.startswith("EXMPT_")]
    keep = ID_COLS + VALUE_COLS + BUILDING_COLS + SALE_COLS + PORTABILITY_COLS + exempt_cols
    out = nal[[c for c in keep if c in nal]].copy()
    for c in NUMERIC_COLS + exempt_cols:
        if c in out:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    # Exemption columns: drop ones that are empty for the whole county
    out = out.drop(columns=[c for c in exempt_cols if out[c].fillna(0).eq(0).all()])

    out = out.join(owner_flags(nal))
    out["homestead"] = out["JV_HMSTD"].fillna(0) > 0
    return out.reset_index(drop=True)


def process_county_file(zip_or_csv: Path, out_dir: Path, delete_raw: bool = False) -> Path:
    """Process a county NAL file (zip or extracted CSV) into Parquet."""
    import zipfile

    out_dir.mkdir(parents=True, exist_ok=True)
    if zip_or_csv.suffix == ".zip":
        with zipfile.ZipFile(zip_or_csv) as z:
            csv_name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
            z.extract(csv_name, zip_or_csv.parent)
        csv_path = zip_or_csv.parent / csv_name
    else:
        csv_path = zip_or_csv

    df = process_nal(csv_path)
    dest = out_dir / f"{csv_path.stem}.parquet"
    df.to_parquet(dest, index=False)

    if delete_raw:
        csv_path.unlink(missing_ok=True)
        if zip_or_csv.suffix == ".zip":
            zip_or_csv.unlink(missing_ok=True)
    return dest
