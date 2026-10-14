"""One year of the tax system for every unit: assessment -> exemptions -> taxable -> tax.

    res = step(units, law, year)            # this year's values
    units = carry_forward(units, res)       # last year's state for next year's step

Input columns (per unit, this year):
  jv, homestead, homestead_prior, changed_ownership, improvements      -> ptm.engine.assess
  av_school_prior, av_nonschool_prior                                  state from last year
  exemption flags / values named in the law spec                       -> ptm.engine.exemptions
  homestead_portion_share   optional: homestead part as a share of the property (default 1)
  homestead_share           optional: co-owner proration of homestead exemptions (default 1)
  millage_<class>           optional: rate in mills for each levy class (school, county,
                            municipal, special) — the rates plug-in; tax is computed if present

Output: av_<class>, taxable_<class>, tax_<class> and tax_total (when rates are present), and
`basis` (which assessment rule set the value).

A first year with no prior state: pass the units' current assessed values as *_prior with
homestead_prior = homestead, changed_ownership = False and jv equal to those values, or start
the projection from a base year where assessed values are known (e.g. the 2026 baseline).
"""

import numpy as np
import pandas as pd

from ptm.engine.assess import assess
from ptm.engine.exemptions import apply_exemptions
from ptm.law import Law


def step(units: pd.DataFrame, law: Law, year: int) -> pd.DataFrame:
    a = assess(units, law, year)
    av = pd.DataFrame(index=units.index)
    av["av_school"] = a["av_school"]
    for c in law.levy_classes:
        if c != "school":
            av[f"av_{c}"] = a["av_nonschool"]
    ex_in = units.drop(columns=[c for c in units if c.startswith("av_")], errors="ignore").join(av)
    if "homestead_portion_share" in units:
        ex_in["av_homestead_portion"] = a["av_school"] * units["homestead_portion_share"].fillna(1).clip(0, 1)
    t = apply_exemptions(ex_in, law, year)

    out = av.join(t)
    out["basis"] = a["basis"]
    if all(f"millage_{c}" in units for c in law.levy_classes):
        for c in law.levy_classes:
            out[f"tax_{c}"] = out[f"taxable_{c}"] * units[f"millage_{c}"].fillna(0) / 1000
        out["tax_total"] = out[[f"tax_{c}" for c in law.levy_classes]].sum(axis=1)
    out.attrs["missing"] = t.attrs.get("missing", [])
    return out


def carry_forward(units: pd.DataFrame, result: pd.DataFrame) -> pd.DataFrame:
    """This year's results become next year's prior state. Year-specific events are cleared;
    the caller sets next year's jv, changed_ownership and improvements."""
    nxt = units.copy()
    nxt["av_school_prior"] = result["av_school"]
    nxt["av_nonschool_prior"] = result["av_county"]
    nxt["homestead_prior"] = units["homestead"]
    nxt["changed_ownership"] = False
    nxt["improvements"] = 0.0
    return nxt
