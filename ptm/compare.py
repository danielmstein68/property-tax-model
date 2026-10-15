"""Compare a policy with current law: same households, same economy, same random draws.

    from ptm.compare import compare
    r = compare("inputs/policies/example_double_second_exemption.yaml", scenario="central")
    r["levels"]        # 1. the new situation: policy and current law side by side, by year
    r["changes"]       # 2. changes from current law, by year (revenue, by levy, rates, average bill)
    r["by_group"]      #    changes by income decile, age, homestead, years in home, home type, region
    r["winners"]       # 3. who wins and loses: shares paying less / more / about the same, by group

Both runs use the same Projection seed, so home sales, deaths and local rate decisions are drawn
from the same random numbers; differences come from the policy (and governments' responses to
it: under the history rate rule, a smaller base raises the rolled-back rate, and governments
respond as they have historically, within the legal limits). A policy may set `rate_response`
(a rate_setting dict, e.g. {county: hold, municipal: hold, school_rle: hold}) applied to the
policy run only - "what if governments don't respond".

response="none": local rates follow exactly the current-law path (the policy's direct effect
only); "history" (default): governments respond as in the rate rule.

"Pays about the same" = within `threshold` dollars a year (default $10).
"""

from pathlib import Path

import numpy as np
import pandas as pd

from ptm.law import load_law
from ptm.policy import apply_policy, load_policy
from ptm.project import BASE_YEAR, LEVIES, Projection
from ptm.results import household_groups

ROOT = Path(__file__).resolve().parents[1]
GROUPS = ["income_decile", "age_group", "homestead", "years_in_home", "home_type", "region"]


def _run(baseline, scenario, seed, law, end_year, rate_setting=None, rate_replay=None) -> Projection:
    return Projection(baseline, scenario, seed=seed, law=law, rate_setting=rate_setting,
                      rate_replay=rate_replay).run(end_year)


def compare(policy, scenario: str = "central", end_year: int = 2036, seed: int = 2026,
            baseline: pd.DataFrame | None = None, threshold: float = 10.0, years: list[int] | None = None,
            response: str = "history") -> dict:
    from ptm.montecarlo import _baseline, slim_baseline
    if baseline is None:
        slim_baseline()
        baseline = _baseline()
    pol = load_policy(policy) if isinstance(policy, (str, Path)) else policy
    law0 = load_law()
    law1 = apply_policy(law0, pol)
    base = _run(baseline, scenario, seed, law0, end_year)
    if response == "none":   # rates follow current law's path exactly
        new = _run(baseline, scenario, seed, law1, end_year, rate_replay=base.rates.paths)
    else:
        new = _run(baseline, scenario, seed, law1, end_year, pol.get("rate_response"))

    keep = ["owners", "tax_total", "avg_tax", "tax_school", "tax_county", "tax_municipal",
            "millage_school_avg", "millage_county_avg", "millage_municipal_avg", "homestead_assessed_to_just"]
    sb, sp = base.summary[keep], new.summary[keep]
    levels = pd.concat({"current_law": sb, "policy": sp}, axis=1)
    changes = (sp - sb).drop(columns=["owners"])
    changes["tax_total_pct"] = sp["tax_total"] / sb["tax_total"] - 1

    hb, hp = base.household_results, new.household_results
    groups = household_groups(base.units)
    groups["income_decile"] = base.units["income_decile"].astype("Int64").astype(str).radd("Decile ")
    years = years or sorted({min(BASE_YEAR + 1, end_year), (BASE_YEAR + 1 + end_year) // 2, end_year})
    rows_g, rows_w = [], []
    for y in years:
        w = base.weights[y]
        live = w > 0
        tb, tp = np.nan_to_num(hb[f"tax_{y}"].to_numpy()), np.nan_to_num(hp[f"tax_{y}"].to_numpy())
        inc = hb[f"income_{y}"].to_numpy()
        d = tp - tb
        win, lose = d < -threshold, d > threshold
        for gname in ["all"] + GROUPS:
            labels = pd.Series("All owners", index=base.units.index) if gname == "all" else groups[gname]
            for lab, idx in labels[live].groupby(labels[live]).groups.items():
                m = base.units.index.isin(idx)
                ww = w[m]
                W = ww.sum()
                if W <= 0:
                    continue
                rows_g.append({"year": y, "grouping": gname, "group": lab, "owners": W,
                               "avg_tax_current_law": (tb[m] * ww).sum() / W, "avg_tax_policy": (tp[m] * ww).sum() / W,
                               "avg_change": (d[m] * ww).sum() / W,
                               "pct_change": (tp[m] * ww).sum() / max((tb[m] * ww).sum(), 1) - 1,
                               "change_share_of_income": (d[m] * ww).sum() / max((inc[m] * ww).sum(), 1),
                               "total_change": (d[m] * ww).sum()})
                rows_w.append({"year": y, "grouping": gname, "group": lab, "owners": W,
                               "share_pay_less": ww[win[m]].sum() / W, "share_pay_more": ww[lose[m]].sum() / W,
                               "share_about_same": 1 - (ww[win[m]].sum() + ww[lose[m]].sum()) / W,
                               "avg_gain_if_less": -(d[m][win[m]] * ww[win[m]]).sum() / max(ww[win[m]].sum(), 1e-9),
                               "avg_loss_if_more": (d[m][lose[m]] * ww[lose[m]]).sum() / max(ww[lose[m]].sum(), 1e-9)})
    return {"policy": {k: v for k, v in pol.items()}, "scenario": scenario, "response": response, "years": years, "threshold": threshold,
            "levels": levels, "changes": changes, "by_group": pd.DataFrame(rows_g), "winners": pd.DataFrame(rows_w)}
