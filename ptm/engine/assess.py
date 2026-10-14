"""Assessment rules: last year's assessed value + this year's just value -> this year's assessed value.

Input: a DataFrame of units with
  jv                       just value this January 1
  av_school_prior          assessed value last year, school levies
  av_nonschool_prior       assessed value last year, non-school levies (county, city, special)
  homestead                homestead exemption this year (bool)
  homestead_prior          homestead exemption last year (bool)
  changed_ownership        sold / change of ownership or control since last January 1 (bool)
  improvements             just value of changes, additions or improvements substantially
                           completed since last January 1 (dollars; optional, default 0)
Output: av_school, av_nonschool (the latter applies to county, municipal and special levies),
and `basis` explaining which rule set the value.

Rules (inputs/fl_law.yaml):
  Homestead (Save Our Homes, all levies; s. 193.155, Rule 12D-8.0062):
    - first homestead year, or after a change of ownership: just value
    - otherwise: last year's assessed value changed by the cap (lower of 3% and CPI; may be
      negative if CPI fell), plus improvements at just value, never above just value. Because
      the value is raised by the cap whenever just value exceeds last year's assessed value
      (recapture), this is min(prior x (1 + cap) + improvements, just value).
  Non-homestead residential (s. 193.1554):
    - school levies: just value
    - non-school: just value in the first non-homestead year (incl. a homestead that lost its
      exemption) or after a change of ownership or control; otherwise
      min(prior x 1.10 + improvements, just value)
Portability is not applied here (see the spec's `portability` notes).
"""

import numpy as np
import pandas as pd

from ptm.law import Law


def assess(units: pd.DataFrame, law: Law, year: int) -> pd.DataFrame:
    n = len(units)
    col = lambda c, default=0.0: (units[c].fillna(default).to_numpy() if c in units  # noqa: E731
                                  else np.full(n, default))
    jv = col("jv").astype(float)
    prior_sd = col("av_school_prior").astype(float)
    prior_ns = col("av_nonschool_prior").astype(float)
    hs = col("homestead", False).astype(bool)
    hs_prior = col("homestead_prior", False).astype(bool)
    sold = col("changed_ownership", False).astype(bool)
    impr = col("improvements").astype(float)

    soh = float(law.rule("soh_cap").get("cap", year))
    nh = float(law.rule("nonhomestead_residential_cap").get("cap", year))

    # Homestead (Save Our Homes): same assessed value for all levies
    hs_reset = hs & (~hs_prior | sold)
    hs_capped = np.minimum(prior_sd * (1 + soh) + impr, jv)
    av_hs = np.where(hs_reset, jv, hs_capped)

    # Non-homestead residential: school at just value; non-school capped at 10%
    nh_reset = ~hs & (hs_prior | sold)
    nh_capped = np.minimum(prior_ns * (1 + nh) + impr, jv)
    av_nh_ns = np.where(nh_reset, jv, nh_capped)

    av_school = np.where(hs, av_hs, jv)
    av_nonschool = np.where(hs, av_hs, av_nh_ns)
    basis = np.select(
        [hs & hs_reset, hs & (hs_capped < jv), hs, ~hs & nh_reset, ~hs & (nh_capped < jv)],
        ["homestead: reset to just value", "homestead: capped (Save Our Homes)", "homestead: at just value",
         "non-homestead: reset to just value", "non-homestead: capped (10%)"],
        default="non-homestead: at just value")
    return pd.DataFrame({"av_school": av_school, "av_nonschool": av_nonschool, "basis": basis},
                        index=units.index)
