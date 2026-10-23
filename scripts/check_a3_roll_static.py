"""Independent check of the Amendment 3 homestead-exemption loss from the 2026 property rolls alone.

Every residential homestead parcel on the 2026 NAL roll: non-school taxable value under current law vs
with the non-school homestead exemption replaced by $150,000 (2027) or $250,000 (2028), times the
parcel's district non-school 2025 millage. No model, no growth: a floor to compare the model's
homestead-exemption piece with (the state's own method starts from these same rolls).

Usage:  python scripts/check_a3_roll_static.py
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
from validate_2026 import EX_NONSCHOOL, RES_UC  # noqa: E402


def main() -> None:
    cols = ["CO_NO", "DOR_UC", "JV", "AV_NSD", "TAX_AUTH_CD", "homestead"]
    parts = []
    for f in glob.glob(str(ROOT / "data/processed/fl_nal_2026/co*.parquet")):
        have = set(pq.read_schema(f).names)
        d = pd.read_parquet(f, columns=cols + [c for c in EX_NONSCHOOL if c in have])
        parts.append(d.reindex(columns=cols + EX_NONSCHOOL, fill_value=0.0))
    p = pd.concat(parts, ignore_index=True)
    import os
    p = p[(p["DOR_UC"].isin(RES_UC) | bool(os.environ.get("ALL_UC"))) & (p["JV"] > 0) & p["homestead"].fillna(False).astype(bool)].copy()
    ex = p[EX_NONSCHOOL].fillna(0.0)
    hs = ex["EXMPT_01"] + ex["EXMPT_02"]
    others = ex.sum(axis=1) - hs
    av = p["AV_NSD"].fillna(0.0)
    p["county_fips"] = fl_dor_to_fips(p["CO_NO"])
    p["code"] = p["TAX_AUTH_CD"].astype(str).str.strip()
    rates = load_rates(2025).set_index(["county_fips", "code"])["nonschool_millage"].rename("mill")
    p = p.join(rates, on=["county_fips", "code"])
    p["mill"] = p["mill"].fillna(p.groupby("county_fips")["mill"].transform("mean"))
    base = (av - others - hs).clip(lower=0)
    print(f"homestead parcels {len(p):,}; non-school taxable $ {base.sum()/1e9:,.0f}B; tax $ {(base*p.mill).sum()/1e12:.2f}B (x1000 check)")
    # The state's method (impact0710.pdf s.3), homestead part: each parcel's assessed value grows at the lower of
    # just-value growth and the Save Our Homes cap, no sales; loss = taxable value change x 2025 non-school
    # rate; then scaled by (state's homestead county taxable forecast / this parcel-only baseline taxable value),
    # which is how the state brings in new construction and parcels the roll doesn't have.
    X = {2027: 150_000, 2028: 250_000, 2029: 255_600, 2030: 260_993, 2031: 267_231}
    SECOND = {2027: 27_143, 2028: 27_805, 2029: 28_428, 2030: 29_028, 2031: 29_721}
    JVG = {2027: .0316, 2028: .0496, 2029: .0605, 2030: .0687, 2031: .0725}      # state's homestead just value growth, incl. new construction
    NC = 0.0115                                                                     # new construction, share of prior just value
    REC_TV = {2026: 1268.5, 2027: 1340.8, 2028: 1423.0, 2029: 1517.1, 2030: 1612.1, 2031: 1713.9}   # $B, homestead county taxable
    jv = p["JV"].to_numpy(float)
    for soh in (0.028,):
        a, j_ = av.to_numpy(float), jv.copy()
        rows = []
        for y, x in X.items():
            g = JVG[y] - NC
            j_ = j_ * (1 + g)
            a = np.minimum(a * (1 + soh), j_)
            cur = np.minimum(a, 25_000) + np.clip(a - 50_000, 0, SECOND[y])
            old = np.maximum(a - others.to_numpy() - cur, 0)
            new = np.maximum(a - others.to_numpy() - x, 0)
            loss = (np.maximum(old - new, 0) * p["mill"].to_numpy() / 1000).sum() / 1e9
            scale = REC_TV[y] / (old.sum() / 1e9)
            rows.append((y, loss, old.sum() / 1e9, scale, loss * scale))
        print(f"Save Our Homes cap {soh:.1%}:")
        for y, l, tv, sc, ls in rows:
            print(f"  {y}: parcel-only loss ${l:.2f}B; baseline taxable ${tv:,.0f}B vs state ${REC_TV[y]:,.0f}B (x{sc:.3f}); scaled ${ls:.2f}B")


if __name__ == "__main__":
    main()
