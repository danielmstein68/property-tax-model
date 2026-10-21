"""Texas policies: changes to numbers in inputs/tx_law.yaml (ptm.policy.apply_policy with Texas's live list).

    from ptm.tx.policy import apply_tx_policy
    law = apply_tx_policy(load_law("tx"), {"changes": [{"rule": "school_homestead", "key": "amount", "value": 180000, "from": 2027}]})
"""

from ptm.law import Law
from ptm.policy import apply_policy

# (rule, key) the Texas projection reads each year -> what it does
LIVE = {
    ("school_homestead", "amount"): "School homestead exemption (s. 11.13(b))",
    ("school_over65_disabled", "amount"): "Extra school exemption for owners 65+ or disabled (s. 11.13(c))",
    ("school_over65_disabled", "min_age"): "Age for the school over-65 exemption and school tax freeze",
    ("homestead_cap", "cap"): "Homestead appraisal cap (s. 23.23)",
    ("circuit_breaker", "expires_after"): "Last year of the 20% circuit breaker on other property up to $5.32M (s. 23.231)",
    ("voter_approval_rate", "multiplier"): "Voter-approval multiplier, most units (s. 26.04: 1.035)",
    ("voter_approval_rate", "special_unit_multiplier"): "Voter-approval multiplier, special taxing units (1.08)",
    ("nonhomestead_cap", "cap"): "Appraisal cap on other property (policy lever)",
    ("nonhomestead_cap", "residential_only"): "Other-property cap for rentals and second homes only (1) or all (0)",
    ("reappraisal", "cycle_years"): "Years between reappraisals (policy lever)",
    ("value_rollback", "from_year"): "First year of cost-basis values from 2019 (policy lever)",
    ("value_rollback", "cap"): "Yearly cap under cost-basis values",
    ("homestead_exempt_share", "school_mo"): "Share of homestead school M&O tax exempt",
    ("homestead_exempt_share", "school_is"): "Share of homestead school debt (I&S) tax exempt",
    ("homestead_exempt_share", "nonschool"): "Share of homestead county, city and district tax exempt",
    ("nonhomestead_exempt_share", "residential"): "Share of rental and second-home tax exempt",
    ("nonhomestead_exempt_share", "business"): "Share of business property tax exempt",
    ("nonhomestead_exempt_share", "mineral"): "Share of mineral property tax exempt",
    ("state_exemptions_all_units", "enabled"): "School homestead exemptions apply at every unit (1)",
    ("local_flat_homestead", "amount"): "Flat-dollar homestead exemption at every non-school unit",
    ("local_freeze_mandatory", "enabled"): "Counties, cities and colleges must freeze over-65 taxes (1)",
    ("spending_limit", "max_growth"): "Most a unit's levy on existing property may grow a year",
    ("spending_limit", "pop_plus_inflation"): "Spending limit also at population plus inflation (1)",
    ("increase_approval", "share"): "Share of planned rate increases that pass (two-thirds approval)",
    ("school_buydown", "cents"): "Extra school M&O compression, cents per $100",
    ("school_buydown", "dollars_per_year"): "State dollars a year for more school compression",
    ("income_credit", "share_of_income"): "Credit for homestead tax above this share of income",
    ("income_credit", "max_credit"): "Largest credit",
    ("income_credit", "income_limit"): "Income limit for the credit",
    ("state_replaces_local", "enabled"): "The state pays non-school units back (1)",
}


def apply_tx_policy(law: Law, policy: dict) -> Law:
    return apply_policy(law, policy, live=LIVE)
