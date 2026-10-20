"""Texas taxing units: values and rates from the Comptroller's Tax Rates and Levies files.

data/raw/tx_cpa/<year>-{county,city,school-district,special-district}-rates-levies.xlsx: one row per
taxing unit per appraisal district (a unit spanning counties appears once per appraisal district,
"split"). Taxing unit ID "CCC-UUU-TT-AAA-NNN": CCC county number, UUU unit, TT unit type, AAA appraisal
district. Type codes: 00 county, 02 school district, 03 city, 11 hospital district, 15 junior college;
everything else (04 MUD, 40 ESD, 19 WCID, 08 drainage, ...) is a special district.
Rates are per $100 of taxable value. The latest published year is 2025 (2026 comes out in early 2027,
so 2026 uses 2025 rates where a 2026 adopted rate isn't collected; docs/TX_DECISIONS.md).
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "tx_cpa"
TYPE_CLASS = {"00": "county", "02": "school", "03": "city", "11": "hospital", "15": "college"}
FILES = {"county": 2, "city": 2, "school-district": 2, "special-district": 3}   # file -> header row


def load_units(year: int = 2025) -> pd.DataFrame:
    """One row per taxing unit x appraisal district: unit_id, unit_key (county-unit-type, the same
    across splits), levy class, name, market and taxable value, M&O / I&S / total rate, levy, and the
    no-new-revenue and voter-approval rates."""
    out = []
    for f, hdr in FILES.items():
        d = pd.read_excel(RAW / f"{year}-{f}-rates-levies.xlsx", header=hdr)
        d = d[d["TAXING UNIT ID"].notna()].copy()
        name = next(c for c in ["TAXING UNIT NAME", "TU NAME", "COUNTY NAME"] if c in d)
        if f == "county":
            d["M&O RATE"] = d[["GF M&O TAX RATE", "R&B M&O TAX RATE"]].sum(axis=1, min_count=1)
            d["I&S RATE"] = d[["GF I&S TAX RATE", "R&B I&S TAX RATE"]].sum(axis=1, min_count=1)
            d["fmfc_rate"] = d["FMFC TOTAL  RATE"]
            d["TAXABLE VALUE"] = d["TAXABLE VALUE FOR GENERAL/ROAD AND BRIDGE FUNDS"]
            d["TOTAL TAX RATE"] = d["TOTAL COUNTY TAX RATE"]
        if f == "school-district":
            d["TAXABLE VALUE"] = d["TAXABLE VALUE M&O"]
        nnr = next(c for c in d.columns if c.startswith("NO-NEW-REVENUE"))
        u = pd.DataFrame({
            "unit_id": d["TAXING UNIT ID"].str.strip(), "name": d[name].astype(str).str.replace(r"\s*\*+\s*$", "", regex=True).str.strip(),
            "cad_id": d["CAD ID"].astype(int), "county_no": pd.to_numeric(d["COUNTY ID"], errors="coerce"), "split": d.get("SPLIT", pd.Series("", index=d.index)).fillna("").astype(str).str.strip(),
            "market_value": pd.to_numeric(d["MARKET VALUE"], errors="coerce"),
            "taxable_value": pd.to_numeric(d["TAXABLE VALUE"], errors="coerce"),
            "mo_rate": pd.to_numeric(d["M&O RATE"], errors="coerce"), "is_rate": pd.to_numeric(d["I&S RATE"], errors="coerce"),
            "total_rate": pd.to_numeric(d["TOTAL TAX RATE"], errors="coerce"),
            "fmfc_rate": pd.to_numeric(d.get("fmfc_rate", pd.Series(0.0, index=d.index)), errors="coerce").fillna(0.0),
            "nnr_rate": pd.to_numeric(d[nnr], errors="coerce"), "var_rate": pd.to_numeric(d["VOTER-APPROVAL RATE"], errors="coerce"),
            "levy": pd.to_numeric(d["CALCULATED LEVY"], errors="coerce")})
        parts = u["unit_id"].str.split("-")
        u["unit_key"] = parts.str[0] + "-" + parts.str[1] + "-" + parts.str[2]
        u["type_code"] = parts.str[2]
        u["levy_class"] = u["type_code"].map(TYPE_CLASS).fillna("special")
        # the row's county, by name (the "2 x county no. - 1" FIPS rule fails for McLennan and McMullen)
        from ptm.tx.pvs import county_fips_by_name
        u["county_fips"] = county_fips_by_name(d["COUNTY NAME"]).to_numpy()
        out.append(u)
    return pd.concat(out, ignore_index=True)


if __name__ == "__main__":
    u = load_units()
    g = u.groupby("levy_class").agg(units=("unit_key", "nunique"), rows=("unit_id", "size"), levy=("levy", "sum"))
    g["levy_share"] = g["levy"] / g["levy"].sum()
    print(g.assign(levy=g.levy / 1e9).round(3).to_string())
    print(f"total 2025 levy ${u.levy.sum() / 1e9:.2f}B")
