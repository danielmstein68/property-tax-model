"""Policies: changes to the numbers in current law, applied to a copy of the law spec.

    from ptm.policy import load_policy, apply_policy, parameters
    parameters()                                    # every number in current law, live or not
    pol = load_policy("inputs/policies/example_double_second_exemption.yaml")
    law = apply_policy(load_law(), pol)             # current law + the policy's changes

A policy file (YAML):
    name: Double the second homestead exemption
    description: ...
    changes:
      - {rule: homestead_second, key: amount, value: 52822, from: 2027}
      - {rule: soh_cap, key: max_rate, value: 0.02, from: 2027}

`from` is the first tax year the new value applies. Year-keyed values keep earlier years and
replace everything from `from` on; if the rule is indexed (a `projection` entry, e.g. CPI), later
years are indexed from the new value. Plain numbers become year-keyed (old value before `from`).

Only "live" numbers can be changed - ones the projection actually reads every year. Others (e.g.
income limits and ages that decided eligibility when the 2026 baseline was built) are refused
with an explanation until they are wired in, so a policy can never silently do nothing.
"""

import copy
from pathlib import Path

import pandas as pd
import yaml

from ptm.law import Law, LawError, load_law

ROOT = Path(__file__).resolve().parents[1]

# (rule, key) the projection reads each year -> what it does
LIVE = {
    ("soh_cap", "max_rate"): "Save Our Homes cap ceiling (cap = lesser of this and CPI)",
    ("soh_cap", "cap"): "Save Our Homes cap by year (future years follow max_rate and CPI)",
    ("nonhomestead_residential_cap", "cap"): "Non-homestead residential cap (non-school levies)",
    ("portability", "max_transfer"): "Most Save Our Homes savings a mover can carry to a new homestead",
    ("homestead_first", "amount"): "First homestead exemption (all levies)",
    ("homestead_second", "amount"): "Second homestead exemption (non-school levies)",
    ("homestead_second", "band_start"): "Assessed value where the second exemption starts",
    ("senior_lowinc_county", "max_amount"): "Most a county may grant as the low-income senior exemption (binds only if set below a county's amount)",
    ("senior_lowinc_municipal", "max_amount"): "Most a city may grant as the low-income senior exemption (binds only if set below a city's amount)",
    ("widow_blind_disabled_5000", "amount"): "Widow(er), blind and disabled exemption",
    ("disabled_exservice_5000", "amount"): "Disabled ex-servicemember exemption",
    ("maximum_millage_vote", "two_thirds_vote_max_of_rolled_back"):
        "Highest rate allowed with a two-thirds vote, as a multiple of the rolled-back rate",
}
SKIP_KEYS = {"description", "citation", "source_text", "source_url", "confidence", "notes", "order", "kind",
             "household_flag", "value_column", "roll_code", "projection", "applies_to", "indexed",
             "income_limit_indexed", "income_measure", "just_value_limit_when", "majority_vote_max_of_rolled_back"}


def _is_number_param(v) -> bool:
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return True
    return isinstance(v, dict) and v and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v.values())


def parameters(law: Law | None = None) -> pd.DataFrame:
    """Every number in the law spec, with whether policies can change it yet."""
    law = law or load_law()
    rows = []
    for r in law.rules.values():
        for k, v in r.spec.items():
            if k in SKIP_KEYS or not _is_number_param(v):
                continue
            live = (r.id, k) in LIVE
            rows.append({"section": r.section, "rule": r.id, "key": k, "value": v, "live": live,
                         "what": LIVE.get((r.id, k), "not yet live: decided eligibility or isn't used by the yearly projection")})
    return pd.DataFrame(rows)


def load_policy(path) -> dict:
    p = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    p.setdefault("name", Path(path).stem)
    p.setdefault("changes", [])
    return p


def apply_policy(law: Law, policy: dict) -> Law:
    """A copy of `law` with the policy's changes. Raises LawError for unknown or not-yet-live numbers."""
    law = copy.deepcopy(law)
    problems = []
    for ch in policy.get("changes", []):
        rid, key = ch.get("rule"), ch.get("key")
        if rid not in law.rules:
            problems.append(f"unknown rule '{rid}'")
            continue
        spec = law.rules[rid].spec
        if key not in spec:
            problems.append(f"{rid}: no number called '{key}' (has: {', '.join(k for k in spec if k not in SKIP_KEYS)})")
            continue
        if (rid, key) not in LIVE:
            problems.append(f"{rid}.{key} isn't live yet: it decided eligibility when the 2026 baseline was built "
                            "or isn't read by the yearly projection; changing it would do nothing")
            continue
        if "value" not in ch or "from" not in ch:
            problems.append(f"{rid}.{key}: a change needs 'value' and 'from' (first tax year)")
            continue
        value, start = ch["value"], int(ch["from"])
        old = spec[key]
        if isinstance(old, dict):
            vals = {int(y): v for y, v in old.items() if int(y) < start}
            if not vals:   # keep a value for years before `from` if the rule starts later
                vals = {}
        else:
            vals = {min(start - 1, 2024): old}
        vals[start] = value
        spec[key] = vals
    if problems:
        raise LawError(f"policy '{policy.get('name')}' can't be applied:\n  - " + "\n  - ".join(problems))
    return law
