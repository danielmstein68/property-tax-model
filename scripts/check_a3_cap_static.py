"""Independent check of the Amendment 3 5%-cap piece from the 2026 rolls alone (non-homestead, non-agricultural).

Same idea as check_a3_roll_static.py: each parcel's non-school assessed value grows at the lower of just-value
growth and the cap (10% current law, 5% from 2027), no sales; loss = taxable value difference x the district's
2025 non-school rate. Just-value growth by category from the state's July 2026 forecast (New row) less new construction.

Usage:  python scripts/check_a3_cap_static.py
"""
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from ptm.millage import fl_dor_to_fips, load_rates  # noqa: E402
from validate_2026 import EX_NONSCHOOL  # noqa: E402

# State's non-homestead just value, $M, 2026..2032 (adval_comparisonstatewidecategories.txt, "New")
JV = {"res": [1370836.4, 1405220.6, 1462447.9, 1538358.8, 1633026.8, 1739503.8, 1852242.5],
      "non": [1338550.0, 1406828.7, 1485549.7, 1576098.4, 1675825.2, 1782987.2, 1897906.0]}
# New construction ($M, 2026..2032): added at just value outside the cap, so it is not growth of existing parcels
NC = {"res": [35601.3, 32390.9, 32946.7, 33913.4, 35066.0, 36116.6, 37166.1],
      "non": [27544.0, 26676.4, 26698.1, 27887.8, 28598.2, 29282.1, 30505.5]}
REC_TV = {"res": [1284273.2, 1325867.4, 1389193.7, 1470426.2, 1569769.3, 1680370.0, 1796791.1],
          "non": [901572.3, 956862.7, 1020582.6, 1093751.7, 1173816.4, 1259350.5, 1350539.9]}


def main() -> None:
    cols = ["CO_NO", "DOR_UC", "JV", "AV_NSD", "TV_NSD", "TAX_AUTH_CD", "homestead"]
    parts = []
    for f in glob.glob(str(ROOT / "data/processed/fl_nal_2026/co*.parquet")):
        have = set(pq.read_schema(f).names)
        d = pd.read_parquet(f, columns=cols + [c for c in EX_NONSCHOOL if c in have])
        parts.append(d.reindex(columns=cols + EX_NONSCHOOL, fill_value=0.0))
    r = pd.concat(parts, ignore_index=True)
    r = r[~r["homestead"].fillna(False).astype(bool)]
    n = pd.read_parquet(ROOT / "data/processed/fl_nal_2026_nonres.parquet", columns=cols[:-1] + ["JV_HMSTD"])
    n = n[n["JV_HMSTD"].fillna(0) == 0].drop(columns="JV_HMSTD")   # non-homestead only
    r["cat"], n["cat"] = "res", "non"
    p = pd.concat([r, n], ignore_index=True)
    p = p[(p["JV"] > 0) & p["DOR_UC"].notna()].copy()
    uc = pd.to_numeric(p["DOR_UC"], errors="coerce")
    p = p[~((uc >= 50) & (uc <= 69))]               # agricultural out
    av = p["AV_NSD"].fillna(0.0)
    exsum = p[EX_NONSCHOOL].fillna(0.0).sum(axis=1)
    ex = (av - p["TV_NSD"]).where(p["TV_NSD"].notna(), exsum).clip(lower=0)
    p = p[(av - ex) > 0].copy()                     # fully exempt parcels out, as the state does
    ex, av = ex[p.index], av[p.index]
    p["county_fips"] = fl_dor_to_fips(p["CO_NO"])
    p["code"] = p["TAX_AUTH_CD"].astype(str).str.strip()
    rates = load_rates(2025).set_index(["county_fips", "code"])["nonschool_millage"].rename("mill")
    p = p.join(rates, on=["county_fips", "code"])
    p["mill"] = p["mill"].fillna(p.groupby("county_fips")["mill"].transform("mean")).fillna(0.0)
    mill, ex_a, jv0 = p["mill"].to_numpy(), ex.to_numpy(float), p["JV"].to_numpy(float)
    a0, cat = av.to_numpy(float), p["cat"].to_numpy()
    print({c: (round(((a0 - ex_a)[cat == c]).sum() / 1e9), "B taxable at 2026; state", round(REC_TV[c][0] / 1e3)) for c in ("res", "non")})
    tot = np.zeros(6)
    for c in ("res", "non"):
        m = cat == c
        a_b = a_p = a0[m]
        jv, e, ml = jv0[m], ex_a[m], mill[m]
        for i in range(1, 6):
            jv = jv * (JV[c][i] - NC[c][i]) / JV[c][i - 1]
            a_b = np.minimum(jv, a_b * 1.10)
            a_p = np.minimum(jv, a_p * 1.05)
            loss = ((np.maximum(a_b - e, 0) - np.maximum(a_p - e, 0)) * ml / 1000).sum() / 1e9
            tot[i] += loss
            print(f"  {c} {2026 + i}: ${loss:.2f}B   baseline taxable ${(np.maximum(a_b - e, 0).sum()) / 1e9:,.0f}B vs state ${REC_TV[c][i] / 1e3:,.0f}B")
    print("5% cap loss, both categories (2027-2031):", [round(x, 2) for x in tot[1:]])


if __name__ == "__main__":
    main()
