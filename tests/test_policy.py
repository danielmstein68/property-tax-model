import numpy as np
import pytest

from ptm.law import LawError, load_law
from ptm.policy import apply_policy, parameters


def test_parameters_listing():
    d = parameters()
    assert {"rule", "key", "value", "live"} <= set(d.columns)
    assert d[(d.rule == "homestead_second") & (d.key == "amount")].live.iloc[0]
    assert d[(d.rule == "senior_lowinc_county") & (d.key == "income_limit")].live.iloc[0]
    assert not d[(d.rule == "portability") & (d.key == "lookback_years")].live.iloc[0]


def test_apply_policy_values_and_indexing():
    from ptm.economy import Economy
    from ptm.project import project_law
    law = apply_policy(load_law(), {"name": "t", "changes": [
        {"rule": "homestead_second", "key": "amount", "value": 50000, "from": 2027},
        {"rule": "soh_cap", "key": "max_rate", "value": 0.02, "from": 2027}]})
    amt = law.rule("homestead_second").spec["amount"]
    assert amt[2026] == 26411 and amt[2027] == 50000
    p = project_law(law, Economy("central"), 2029)
    assert p.rule("homestead_second").get("amount", 2029) > 50000            # indexing continues
    assert p.rule("soh_cap").get("cap", 2028) == 0.02                         # CPI 2.3% > new 2% ceiling
    assert load_law().rule("homestead_second").spec["amount"].get(2027) is None   # original untouched


def test_apply_policy_refuses_bad_changes():
    with pytest.raises(LawError, match="unknown rule"):
        apply_policy(load_law(), {"changes": [{"rule": "nope", "key": "amount", "value": 1, "from": 2027}]})
    with pytest.raises(LawError, match="isn't live"):
        apply_policy(load_law(), {"changes": [{"rule": "portability", "key": "lookback_years", "value": 1, "from": 2027}]})
    with pytest.raises(LawError, match="no number"):
        apply_policy(load_law(), {"changes": [{"rule": "homestead_first", "key": "amout", "value": 1, "from": 2027}]})


def test_compare_no_change_is_zero():
    from ptm.compare import compare
    r = compare({"name": "nothing", "changes": []}, end_year=2028)
    assert np.allclose(r["changes"]["tax_total"].to_numpy(), 0)
    a = r["winners"][r["winners"].grouping == "all"]
    assert np.allclose(a["share_about_same"], 1)
