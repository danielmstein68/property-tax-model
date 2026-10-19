"""Paying for a property tax cut with other taxes (scripts/offset_taxes.py): what a point of each tax
raises, and the sales tax base by income tenth."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import offset_taxes as ot  # noqa: E402

RAW = ot.RAW


def test_general_revenue_share_of_sales_tax():
    # s. 212.20(6)(d): what's left for General Revenue after the local transfers
    assert ot.GR_SHARE == pytest.approx(0.874827, abs=1e-6)


def test_fiscal_years_follow_the_roll_and_extend():
    s = ot.by_fiscal_year(ot.GR["sales"])
    assert s[2027] == pytest.approx(38_799.9e6)                 # roll 2027 is paid in FY 2027-28
    g = ot.GR["sales"][-1] / ot.GR["sales"][-2]
    assert s[2032] == pytest.approx(43_352.6e6 * g)             # past the forecast: last year's growth


@pytest.mark.skipif(not (RAW / "cu-income-deciles-before-taxes-2024.xlsx").exists(), reason="CE table not downloaded")
def test_taxable_spending_rises_with_income():
    t = ot.taxable_spending()["taxable_spending_2024"]
    assert len(t) == 10 and all(b > a for a, b in zip(t, t[1:]))


@pytest.mark.skipif(not (RAW / "lgfih25.pdf").exists(), reason="handbook not downloaded")
def test_surtax_tables_parse():
    st = ot.surtax()
    assert len(st["counties"]) == 67
    assert st["statewide"]["one_point"] == pytest.approx(sum(c["one_point"] for c in st["counties"].values()), rel=0.01)
