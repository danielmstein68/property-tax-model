"""Results toolkit: distribution tables from a baseline (or policy) household file.

Conventions (ptm.settings.Settings; decided 2026-10-14):
  - Income deciles are defined over ALL households (renters included) using 2026 household
    income, so cut-offs don't move when renters are modelled.
  - Tax results cover owners only: owner households paying real-estate tax directly. Mobile
    homes on rented lots are excluded like renters (their tax comes through lot rent).
  - Standard errors use the 80 replicate weights (ACS successive-difference method):
    SE = sqrt(4/80 * sum_r (theta_r - theta)^2).

Main entry points:
  add_income_deciles(h)                    -> decile column
  owner_mask(h)                            -> rows with modelled owner tax
  table(h, by, tax_col=...)                -> summary by group, with SEs for key measures
  suits_index(income, tax, weights)        -> progressivity (-1 regressive .. +1 progressive)
"""

import numpy as np
import pandas as pd

from ptm.settings import Settings

REPLICATES = [f"WGTP{i}" for i in range(1, 81)]

# Regions by county FIPS (Florida, 3-digit)
REGIONS = {
    "Southeast": ["086", "011", "099", "087", "085", "111", "061", "093"],
    "Southwest": ["071", "021", "015", "115", "081", "051", "043", "027", "049", "055"],
    "Tampa Bay": ["057", "103", "101", "053", "105", "017"],
    "Central": ["095", "097", "117", "069", "127", "009", "119", "083", "035"],
    "Northeast": ["031", "109", "019", "089", "003", "107", "001", "007", "023", "041", "075", "121", "125"],
}
REGION_OF = {f: r for r, fs in REGIONS.items() for f in fs}

AGE_BANDS = [(0, 44, "Under 45"), (45, 64, "45–64"), (65, 74, "65–74"), (75, 200, "75 and over")]
MV_BANDS = {1: "Under 2 years", 2: "Under 2 years", 3: "2–4 years", 4: "5–9 years",
            5: "10–19 years", 6: "20 years or more", 7: "20 years or more"}
HOME_TYPES = {"sfr": "Single-family", "condo": "Condo / co-op", "mobile": "Mobile home (owns land)"}


def household_groups(h: pd.DataFrame) -> pd.DataFrame:
    """Readable groups for tables and comparisons: age, years in home, home type, homestead, region."""
    out = pd.DataFrame(index=h.index)
    out["age_group"] = pd.cut(h["HHLDRAGEP"], [a - 0.5 for a, _, _ in AGE_BANDS] + [200],
                              labels=[l for *_, l in AGE_BANDS]).astype(str)
    out["years_in_home"] = h["MV"].map(MV_BANDS)
    out["home_type"] = h["home_type"].map(HOME_TYPES)
    out["homestead"] = np.where(h["homestead"].fillna(False).astype(bool), "Homestead", "Not homestead")
    out["region"] = h["county_fips"].map(REGION_OF).fillna("North & Panhandle")
    return out


def weighted_cutoffs(x: pd.Series, w: pd.Series, n: int = 10) -> np.ndarray:
    o = np.argsort(x.to_numpy())
    xs, ws = x.to_numpy()[o], w.to_numpy()[o]
    c = np.cumsum(ws) / ws.sum()
    return np.array([xs[np.searchsorted(c, q)] for q in np.arange(1, n) / n])


def add_income_deciles(h: pd.DataFrame, income_col: str = "hincp_aged", settings: Settings = Settings()) -> pd.DataFrame:
    """Income decile (1-10) for every household; cut-offs over the settings' decile population."""
    out = h.copy()
    pop = out if settings.decile_population == "all_households" else out[owner_mask(out)]
    cuts = weighted_cutoffs(pop[income_col].fillna(0), pop["WGTP"])
    out["income_decile"] = np.searchsorted(cuts, out[income_col].fillna(0).to_numpy(), side="right") + 1
    out.attrs["decile_cutoffs"] = cuts
    return out


def owner_mask(h: pd.DataFrame, tax_col: str = "tax_model_2026") -> pd.Series:
    return (h["tenure"] == "owner") & ~h["mh_rented_lot"].fillna(False).astype(bool) & h[tax_col].notna()


def suits_index(income: np.ndarray, tax: np.ndarray, w: np.ndarray) -> float:
    """Suits index: 1 - 2 x area under the cumulative tax share vs cumulative income share curve
    (incomes floored at 0, sorted ascending). 0 = proportional, < 0 regressive, > 0 progressive."""
    inc = np.maximum(np.asarray(income, float), 0)
    o = np.argsort(inc)
    inc, tax, w = inc[o], np.asarray(tax, float)[o], np.asarray(w, float)[o]
    ci = np.concatenate([[0], np.cumsum(inc * w) / np.sum(inc * w)])
    ct = np.concatenate([[0], np.cumsum(tax * w) / np.sum(tax * w)])
    area = np.sum((ci[1:] - ci[:-1]) * (ct[1:] + ct[:-1]) / 2)
    return float(1 - 2 * area)


def weighted_median(x, w) -> float:
    x, w = np.asarray(x, float), np.asarray(w, float)
    o = np.argsort(x)
    c = np.cumsum(w[o])
    return float(x[o][np.searchsorted(c, c[-1] / 2)])


def _measures(g: pd.DataFrame, w: str, tax_col: str, total_tax: float) -> dict:
    ww = g[w]
    tax, inc, val = g[tax_col], g["hincp_aged"].clip(lower=0), g["valp_market_cal"]
    # each owner's own tax / income; zero or negative income counts as an infinite share
    own_share = np.where(inc > 0, tax / inc.where(inc > 0, 1), np.inf)
    return {
        "median_tax_share_of_income": weighted_median(own_share, ww),
        "owners": ww.sum(),
        "avg_tax": (tax * ww).sum() / ww.sum(),
        "tax_share_of_income": (tax * ww).sum() / (inc * ww).sum() if (inc * ww).sum() > 0 else np.nan,
        "effective_rate_on_value": (tax * ww).sum() / (val * ww).sum(),
        "share_of_owner_tax": (tax * ww).sum() / total_tax,
        "avg_income": (inc * ww).sum() / ww.sum(),
        "avg_value": (val * ww).sum() / ww.sum(),
    }


def table(h: pd.DataFrame, by: str, tax_col: str = "tax_model_2026", with_se: bool = True) -> pd.DataFrame:
    """Owner tax measures by group, with replicate-weight standard errors."""
    o = h[owner_mask(h, tax_col)]
    total = (o[tax_col] * o["WGTP"]).sum()
    rows = {k: _measures(g, "WGTP", tax_col, total) for k, g in o.groupby(by)}
    rows["All owners"] = _measures(o, "WGTP", tax_col, total)
    res = pd.DataFrame(rows).T
    if with_se:
        reps = []
        for r in REPLICATES:
            tr = (o[tax_col] * o[r]).sum()
            m = {k: _measures(g, r, tax_col, tr) for k, g in o.groupby(by)}
            m["All owners"] = _measures(o, r, tax_col, tr)
            reps.append(pd.DataFrame(m).T)
        for col in ["owners", "avg_tax", "tax_share_of_income", "median_tax_share_of_income", "effective_rate_on_value", "share_of_owner_tax"]:
            dev = np.stack([(rep[col] - res[col]).to_numpy(float) for rep in reps])
            res[f"{col}_se"] = np.sqrt(4 / 80 * (dev ** 2).sum(axis=0))
    return res


def suits_with_se(h: pd.DataFrame, tax_col: str = "tax_model_2026") -> tuple[float, float]:
    o = h[owner_mask(h, tax_col)]
    s = suits_index(o["hincp_aged"], o[tax_col], o["WGTP"])
    reps = [suits_index(o["hincp_aged"], o[tax_col], o[r]) for r in REPLICATES]
    return s, float(np.sqrt(4 / 80 * np.sum((np.array(reps) - s) ** 2)))
