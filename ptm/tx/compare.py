"""Compare a Texas policy with current law: same households, same economy, same random draws.

    from ptm.tx.compare import compare, Base
    b = Base()                                   # current law, central scenario (run once, reused)
    r = compare(policy, b, mode="respond")       # mode: none | respond | neutral
    r["changes"]      # by year: tax by class (owners, other property, all), homesteads, state cost, sales tax points
    r["by_group"]     # by income tenth, age, homestead, region, 65+: average change, share of income
    r["winners"]      # shares paying less / more / about the same, and size bands

Modes, as for Florida (ptm.compare): "none" - every unit's rate follows the current-law path; "respond" - units
set rates under their own rules on their policy bases (school compressed rates follow the current-law path, less
any policy buy-down); "neutral" - each county, city and district raises the same M&O levy as under current law.
With state_replaces_local on, non-school rates follow current law in every mode (the state pays them back).

State cost each year = the drop in school levies (the state pays districts back for exemptions, eliminations
and buy-downs, as it has for every Texas school tax cut), plus the drop in non-school levies when the state
replaces them, plus income credits. Sales tax points = state cost / what one point of the state sales tax
raises that year (scripts/tx_offset_taxes.py).
"""

from pathlib import Path

import numpy as np
import pandas as pd

from ptm.law import load_law
from ptm.tx.project import BASE_YEAR, CLASSES, PROC, TxProjection
from ptm.tx.policy import apply_tx_policy

ROOT = Path(__file__).resolve().parents[2]
REGIONS = {"Houston": ["201", "157", "339", "039", "167", "291", "071", "473", "015"],
           "Dallas-Fort Worth": ["113", "439", "085", "121", "397", "251", "257", "139", "367", "221", "231", "497"],
           "Austin": ["453", "491", "209", "055", "021"], "San Antonio": ["029", "091", "187", "325", "013", "259", "019", "493"],
           "El Paso": ["141", "229"], "Rio Grande Valley": ["215", "061", "489", "427"]}
REGION_OF = {f: m for m, fs in REGIONS.items() for f in fs}
AGE = [(0, 44, "Under 45"), (45, 54, "45–54"), (55, 64, "55–64"), (65, 74, "65–74"), (75, 200, "75 and over")]
YEARS = [2027, 2031, 2036]


def _baseline():
    return pd.read_parquet(PROC / "tx_baseline_2026.parquet"), pd.read_parquet(PROC / "tx_baseline_2026_units.parquet")


def decile_cutoffs() -> np.ndarray:
    """All Texas households' 2026 income tenths (renters included), cached."""
    p = PROC / "tx_decile_cutoffs_2026.npy"
    if p.exists():
        return np.load(p)
    from ptm.results import weighted_cutoffs
    from ptm.tx.survey import tx_households
    h = tx_households()
    cut = np.asarray(weighted_cutoffs(h["hincp_aged"].fillna(0), h["WGTP"], 10), dtype=float)
    np.save(p, cut)
    return cut


def sales_tax_point() -> dict:
    """What one point of the state sales tax raises each year (scripts/tx_offset_taxes.py), else None."""
    import json
    p = PROC / "results" / "tx_offset_taxes.json"
    if not p.exists():
        return {}
    d = json.loads(p.read_text(encoding="utf-8"))
    return {int(k): v for k, v in d["point_value"].items()}


class Base:
    """The current-law run (central scenario), reused by every comparison."""

    def __init__(self, scenario: str = "central", seed: int = 2026, end_year: int = 2036, baseline=None):
        self.o, self.rows = baseline or _baseline()
        self.scenario, self.seed, self.end_year = scenario, seed, end_year
        self.law = load_law("tx")
        self.run = TxProjection(self.o, self.rows, scenario, seed=seed, end_year=end_year, law=self.law).run()
        self.cut = decile_cutoffs()


def run_policy(policy: dict, base: Base, mode: str = "respond") -> TxProjection:
    law = apply_tx_policy(base.law, policy)
    kw = {"none": {"rate_replay": base.run.paths}, "respond": {"school_replay": base.run.paths},
          "neutral": {"revenue_neutral": base.run.paths}}[mode]
    return TxProjection(base.o, base.rows, base.scenario, seed=base.seed, end_year=base.end_year, law=law, **kw).run()


def groups(p: TxProjection, y: int, cut: np.ndarray, wage_index: float) -> dict[str, np.ndarray]:
    h = p.history
    inc = h[f"income_{y}"]
    dec = np.searchsorted(cut * wage_index, inc, side="right") + 1
    age = h[f"age_{y}"]
    lab_age = np.full(p.n, "", dtype=object)
    for lo, hi, lab in AGE:
        lab_age[(age >= lo) & (age <= hi)] = lab
    return {"income_decile": np.array([f"{d}" for d in dec], dtype=object), "age_group": lab_age,
            "homestead": np.where(p.hs, "Homestead", "No homestead exemption").astype(object),
            "region": np.array([REGION_OF.get(c, "Rest of Texas") for c in p.county], dtype=object),
            "over65": np.where(p.hs & h[f"o65_{y}"], "65+ or disabled (homestead)", "Other owners").astype(object)}


def compare_runs(base: Base, new: TxProjection, threshold: float = 10.0, years: list[int] | None = None) -> dict:
    b, p = base.run, new
    sb, sp = b.summary, p.summary
    cols = (["tax_total", "tax_owners", "nonowner_tax", "nonowner_tax_residential", "total_levy", "credit_total", "avg_tax",
             "homesteads", "state_aid", "recapture", "net_state_cost", "state_mcr"]
            + [f"levy_{c}" for c in CLASSES] + [f"tax_{c}" for c in CLASSES] + [f"nonowner_tax_{c}" for c in CLASSES])
    ch = (sp[cols] - sb[cols])
    pol_law = p.law
    repl = np.array([bool(pol_law.rule("state_replaces_local").get("enabled", y, 0)) for y in ch.index])
    nonschool = ch[[f"levy_{c}" for c in CLASSES if c != "school"]].sum(axis=1)
    ch["state_cost"] = -ch["levy_school"] + np.where(repl, -nonschool, 0.0) + sp["credit_total"]
    ch["local_revenue_lost"] = np.where(repl, 0.0, -nonschool)
    pt = sales_tax_point()
    ch["sales_tax_points"] = [ch.loc[y, "state_cost"] / pt[y] if y in pt and pt[y] else np.nan for y in ch.index]
    ch["tax_total_pct"] = sp["tax_total"] / sb["tax_total"] - 1
    years = years or YEARS
    rows_g, rows_w = [], []
    wi = 1.0
    wage_index = {}
    for y in range(BASE_YEAR, base.end_year + 1):
        if y > BASE_YEAR:
            wi *= 1 + b.econ.rate("wage", y)
        wage_index[y] = wi
    for y in years:
        w = b.weights[y]
        live = w > 0
        tb, tp = b.history[f"tax_{y}"], p.history[f"tax_{y}"]
        inc = b.history[f"income_{y}"]
        d = tp - tb
        win, lose = d < -threshold, d > threshold
        rel = np.where(tb > 0, d / np.maximum(tb, 1e-9), np.where(d > 0, np.inf, np.where(d < 0, -np.inf, 0)))
        cats = {"gain_more_5pct": win & (rel < -0.05), "gain_less_5pct": win & (rel >= -0.05),
                "no_change": ~win & ~lose, "lose_less_5pct": lose & (rel <= 0.05), "lose_more_5pct": lose & (rel > 0.05)}
        gs = groups(b, y, base.cut, wage_index[y])
        for gname, lab in [("all", np.full(b.n, "All owners", dtype=object))] + list(gs.items()):
            for g in pd.unique(lab[live]):
                m = live & (lab == g)
                ww = w[m]
                W = ww.sum()
                if W <= 0:
                    continue
                rows_g.append({"year": y, "grouping": gname, "group": g, "owners": W,
                               "avg_tax_current_law": (tb[m] * ww).sum() / W, "avg_tax_policy": (tp[m] * ww).sum() / W,
                               "avg_change": (d[m] * ww).sum() / W, "pct_change": (tp[m] * ww).sum() / max((tb[m] * ww).sum(), 1) - 1,
                               "change_share_of_income": (d[m] * ww).sum() / max((inc[m] * ww).sum(), 1), "total_change": (d[m] * ww).sum()})
                rows_w.append({"year": y, "grouping": gname, "group": g, "owners": W,
                               "share_pay_less": ww[win[m]].sum() / W, "share_pay_more": ww[lose[m]].sum() / W,
                               "avg_gain_if_less": -(d[m][win[m]] * ww[win[m]]).sum() / max(ww[win[m]].sum(), 1e-9),
                               "avg_loss_if_more": (d[m][lose[m]] * ww[lose[m]]).sum() / max(ww[lose[m]].sum(), 1e-9),
                               **{k: ww[v[m]].sum() / W for k, v in cats.items()}})
    return {"years": years, "levels": pd.concat({"current_law": sb[cols], "policy": sp[cols]}, axis=1), "changes": ch,
            "by_group": pd.DataFrame(rows_g), "winners": pd.DataFrame(rows_w)}


def compare(policy: dict, base: Base, mode: str = "respond", **kw) -> dict:
    out = compare_runs(base, run_policy(policy, base, mode), **kw)
    out.update({"policy": policy, "mode": mode})
    return out
