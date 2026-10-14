import textwrap

import pytest

from ptm.law import LawError, load_law, value_for

GOOD = textwrap.dedent("""
    meta: {state: XX, levy_classes: [school, county], as_of: 2026}
    exemptions:
      first:
        description: d
        citation: c
        source_text: t
        source_url: u
        confidence: high
        kind: fixed
        household_flag: homestead
        order: 1
        applies_to: [school, county]
        amount: {2024: 100, 2026: 200}
""")


def test_value_for_carries_forward_and_errors_before_first_year():
    v = {2024: 100, 2026: 200}
    assert value_for(v, 2024) == 100
    assert value_for(v, 2025) == 100
    assert value_for(v, 2030) == 200
    assert value_for(5, 1999) == 5
    with pytest.raises(LawError):
        value_for(v, 2023)


def test_load_good_spec(tmp_path):
    p = tmp_path / "xx_law.yaml"
    p.write_text(GOOD)
    law = load_law("xx", p)
    assert law.rule("first").get("amount", 2025) == 100
    assert [r.id for r in law.exemptions()] == ["first"]


@pytest.mark.parametrize("broken, message", [
    ("confidence: high", "confidence must be"),         # replaced below with a bad value
    ("applies_to: [school, county]", "unknown levy classes"),
    ("kind: fixed", "kind must be"),
    ("source_url: u", "missing source_url"),
])
def test_validation_catches_mistakes(tmp_path, broken, message):
    bad = {
        "confidence: high": "confidence: sure",
        "applies_to: [school, county]": "applies_to: [school, city]",
        "kind: fixed": "kind: magic",
        "source_url: u": "source_url: ''",
    }[broken]
    p = tmp_path / "xx_law.yaml"
    p.write_text(GOOD.replace(broken, bad))
    with pytest.raises(LawError, match=message):
        load_law("xx", p)
