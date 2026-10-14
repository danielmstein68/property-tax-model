"""Model run settings shared by simulations and results.

    from ptm.settings import Settings
    s = Settings()                                   # defaults: owners only, deciles over all households
    s = Settings(include_rental_pass_through=True)   # -> NotImplementedError until pass-through exists

Decisions (Daniel, 2026-10-14):
  - The status quo is modelled for **owners only** first; renters stay in the data, labelled as not
    yet modelled (not as paying $0), and results are labelled "owners only".
  - Income deciles (and other income groups) are defined over **all households**, renters included,
    so the cut-offs don't move when renters are added later.
  - Rental pass-through is a switch that exists now but raises an error until it is built
    (options in TODO.md: one share; different shares for increases/decreases; phased in over years;
    land vs building split; separate landlord line).
"""

from dataclasses import dataclass

DECILE_POPULATIONS = {"all_households", "owners"}


class NotBuiltYet(NotImplementedError):
    pass


@dataclass(frozen=True)
class Settings:
    include_rental_pass_through: bool = False
    decile_population: str = "all_households"

    def __post_init__(self):
        if self.include_rental_pass_through:
            raise NotBuiltYet(
                "Rental pass-through isn't built yet: results cover owners only. "
                "See TODO.md ('Deferred: pass-through to renters') for the options to decide.")
        if self.decile_population not in DECILE_POPULATIONS:
            raise ValueError(f"decile_population must be one of {sorted(DECILE_POPULATIONS)}")

    @property
    def coverage_label(self) -> str:
        return "owners and renters" if self.include_rental_pass_through else "owners only"
