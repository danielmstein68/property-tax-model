import pytest

from ptm.settings import NotBuiltYet, Settings


def test_defaults_owners_only_deciles_all_households():
    s = Settings()
    assert not s.include_rental_pass_through
    assert s.decile_population == "all_households"
    assert s.coverage_label == "owners only"


def test_pass_through_switch_errors_until_built():
    with pytest.raises(NotBuiltYet, match="isn't built yet"):
        Settings(include_rental_pass_through=True)


def test_bad_decile_population():
    with pytest.raises(ValueError):
        Settings(decile_population="renters")
