"""Exemptions -> taxable value, by levy class, following the law spec.

Input: a DataFrame of units with
  av_<class>          assessed value for each levy class in law.levy_classes
  homestead           bool
  <household_flag>    eligibility for each exemption rule (bool, or a count for fixed-amount
                      rules where several people qualify, e.g. two $5,000 exemptions)
  <value_column>      per-unit value for local_option / percent / reduction rules
  av_homestead_portion  optional: assessed value of the homestead part of the property (e.g. the
                      owner's unit in a duplex, the home on a mixed lot). Homestead exemptions are
                      measured on this part only. Default: the whole assessed value.
  homestead_share     optional: share of the homestead exemptions granted (co-owners who don't
                      live there reduce it, e.g. 0.5). Default 1.
Columns that are missing count as "not eligible" (listed in the result's `missing` attribute).

Order (s. 196.031(8), s. 196.082(6), F.S. — rule `exemption_order` in the spec):
  1. total exemptions: taxable 0 in the levy classes they apply to;
  2. 'fixed' and 'band' homestead exemptions measured on the raw assessed value
     (homestead_first, homestead_second);
  3. every other dollar exemption (fixed, local_option, reduction) — subtractive with a $0
     floor, so their order among themselves doesn't change the result;
  4. percentage exemptions in spec order (deployed military: share of the remaining taxable
     value), with the veterans' discount last because it has the highest `order`;
  5. floor at 0.
"""

import numpy as np
import pandas as pd

from ptm.law import Law, LawError

HOMESTEAD_FIRST = {"homestead_first", "homestead_second"}


def _flag(units: pd.DataFrame, col: str, missing: set) -> np.ndarray:
    if col not in units:
        missing.add(col)
        return np.zeros(len(units))
    return units[col].fillna(0).astype(float).to_numpy()


def apply_exemptions(units: pd.DataFrame, law: Law, year: int, detail: bool = False) -> pd.DataFrame:
    """Return taxable_<class> for each levy class (and exempt_<rule>_<class> if detail)."""
    classes = law.levy_classes
    for c in classes:
        if f"av_{c}" not in units:
            raise LawError(f"units need an 'av_{c}' column (assessed value for {c} levies)")
    n = len(units)
    av = {c: units[f"av_{c}"].fillna(0).astype(float).to_numpy() for c in classes}
    remaining = {c: av[c].copy() for c in classes}
    zero = {c: np.zeros(n, bool) for c in classes}
    out = {}
    missing: set = set()
    rules = law.exemptions()

    # 1. Total exemptions
    for r in rules:
        if r.spec["kind"] != "total":
            continue
        elig = _flag(units, r.spec["household_flag"], missing) > 0
        for c in r.spec["applies_to"]:
            zero[c] |= elig

    # 2-3. Dollar exemptions
    def subtract(r, amount):
        for c in r.spec["applies_to"]:
            take = np.minimum(np.maximum(remaining[c], 0), amount)
            remaining[c] = remaining[c] - take
            if detail:
                out[f"exempt_{r.id}_{c}"] = take

    first = [r for r in rules if r.id in HOMESTEAD_FIRST]
    others = [r for r in rules if r.id not in HOMESTEAD_FIRST and r.spec["kind"] in {"fixed", "band", "local_option", "reduction"}]
    portion = units["av_homestead_portion"].to_numpy(float) if "av_homestead_portion" in units else None
    hs_share = units["homestead_share"].fillna(1).to_numpy(float) if "homestead_share" in units else 1.0

    def hs_base(c):
        """Raw assessed value the homestead exemptions are measured on (homestead part only)."""
        return av[c] if portion is None else np.minimum(av[c], np.nan_to_num(portion, nan=np.inf))

    for r in first + others:
        kind = r.spec["kind"]
        elig = _flag(units, r.spec["household_flag"], missing)
        if r.id in HOMESTEAD_FIRST:
            # s. 196.031: on the residence (homestead part), measured on raw assessed value,
            # prorated for co-owners who don't live there
            for c in r.spec["applies_to"]:
                base = hs_base(c)
                if kind == "fixed":
                    amount = (elig > 0) * np.minimum(base, float(r.get("amount", year))) * hs_share
                else:
                    start, width = float(r.get("band_start", year)), float(r.get("amount", year))
                    amount = (elig > 0) * np.clip(base - start, 0, width) * hs_share
                take = np.minimum(np.maximum(remaining[c], 0), amount)
                remaining[c] = remaining[c] - take
                if detail:
                    out[f"exempt_{r.id}_{c}"] = take
            continue
        if kind == "fixed":
            amount = elig * float(r.get("amount", year))           # a count multiplies the amount
        elif kind == "band":
            start, width = float(r.get("band_start", year)), float(r.get("amount", year))
            base = av[r.spec["applies_to"][0]]
            amount = (elig > 0) * np.clip(base - start, 0, width)
        elif kind == "local_option":
            amount = (elig > 0) * np.minimum(_flag(units, r.spec["value_column"], missing),
                                             float(r.get("max_amount", year, np.inf)))
        elif kind == "reduction":
            share_cap = float(r.get("max_share_of_assessed", year, 1.0))
            raw = _flag(units, r.spec["value_column"], missing)
            base = av[r.spec["applies_to"][0]]
            amount = (elig > 0) * np.minimum(raw, share_cap * base)
        subtract(r, amount)

    # 4. Percentage exemptions, in spec order (veterans' discount last)
    for r in [r for r in rules if r.spec["kind"] == "percent"]:
        elig = _flag(units, r.spec["household_flag"], missing) > 0
        share = np.clip(_flag(units, r.spec["value_column"], missing), 0, 1)
        for c in r.spec["applies_to"]:
            take = np.maximum(remaining[c], 0) * share * elig
            remaining[c] = remaining[c] - take
            if detail:
                out[f"exempt_{r.id}_{c}"] = take

    # 5. Totals and floor
    for c in classes:
        out[f"taxable_{c}"] = np.where(zero[c], 0.0, np.maximum(remaining[c], 0.0))
    res = pd.DataFrame(out, index=units.index)
    res.attrs["missing"] = sorted(missing)
    return res
