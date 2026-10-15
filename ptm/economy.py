"""Economic paths for projections: home values, incomes, inflation, households.

    from ptm.economy import Economy
    e = Economy("central")                       # or "low", "high", "stall", "downturn"
    e.rate("home_value", 2028)                   # growth from 2027 to 2028
    e.index("home_value", 2026, 2030)            # cumulative factor 2026 -> 2030
    e = Economy("central", overrides={"home_value": {"shift": -0.01}})   # a custom what-if
    h2 = e.grow(h, 2026, 2027)                   # values and incomes one year forward

Assumptions live in inputs/fl_projection_assumptions.yaml (editable); forecast paths in
inputs/fl_economy_paths.csv (scripts/fl_economy_inputs.py). Fiscal-year forecasts (EEC) are used
as calendar-year growth.
"""

from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
ASSUMPTIONS = ROOT / "inputs" / "fl_projection_assumptions.yaml"
PATHS = ROOT / "inputs" / "fl_economy_paths.csv"
OVERRIDE_KEYS = {"source", "set", "shift", "description"}


class Economy:
    def __init__(self, scenario: str = "central", overrides: dict | None = None,
                 assumptions_path: Path = ASSUMPTIONS, paths_path: Path = PATHS):
        self.spec = yaml.safe_load(Path(assumptions_path).read_text(encoding="utf-8"))
        self.paths = pd.read_csv(paths_path)
        scenarios = self.spec["scenarios"]
        if scenario not in scenarios:
            raise ValueError(f"unknown scenario '{scenario}'; choose from {sorted(scenarios)}")
        self.scenario = scenario
        self.base_year = self.spec["meta"]["base_year"]
        self.end_year = self.spec["meta"]["end_year"]
        merged = {k: v for k, v in (scenarios[scenario] or {}).items() if k != "description"}
        for var, ov in (overrides or {}).items():
            merged[var] = {**merged.get(var, {}), **ov}
        for var, ov in merged.items():
            if var not in self.spec["variables"]:
                raise ValueError(f"scenario sets unknown variable '{var}'")
            bad = set(ov) - OVERRIDE_KEYS
            if bad:
                raise ValueError(f"{var}: unknown override keys {sorted(bad)}")
        self.overrides = merged
        self._rates = {v: self._build(v) for v in self.spec["variables"]}

    def _series(self, variable: str, source: str) -> pd.Series:
        d = self.paths[(self.paths["variable"] == variable) & (self.paths["source"] == source)]
        if d.empty:
            raise ValueError(f"no path for {variable} from {source} in {PATHS.name}")
        return d.set_index("year")["growth"].dropna()

    def _build(self, var: str) -> pd.Series:
        v, ov = self.spec["variables"][var], self.overrides.get(var, {})
        years = range(self.base_year, self.end_year + 1)  # base year's own growth kept where known (CPI)
        if "values" in v:
            r = pd.Series({int(y): float(x) for y, x in v["values"].items()})
        else:
            r = self._series(v["paths_variable"], ov.get("source", v["source"]))
        r = r.reindex(years)
        last = r.last_valid_index()
        after = v.get("after_forecast", {"method": "hold"})
        if last is not None and last < self.end_year:
            if after["method"] == "ease_to":
                target = self._series(after["target_variable"], after["target_source"])
                n = after["years"]
                for k, y in enumerate(range(last + 1, self.end_year + 1), start=1):
                    w = min(k / n, 1.0)
                    r[y] = (1 - w) * r[last] + w * target.get(y, target.iloc[-1])
            else:  # hold the last forecast year's rate
                r = r.ffill()
        for y, x in (ov.get("set") or {}).items():
            r[int(y)] = float(x)
        r = r + float(ov.get("shift", 0.0))
        gaps = r[r.isna() & (r.index > self.base_year)]
        if len(gaps):
            raise ValueError(f"{var}: no rate for {list(gaps.index)}")
        return r

    def rate(self, variable: str, year: int) -> float:
        return float(self._rates[variable][year])

    def index(self, variable: str, from_year: int, to_year: int) -> float:
        f = 1.0
        for y in range(from_year + 1, to_year + 1):
            f *= 1 + self.rate(variable, y)
        return f

    def table(self) -> pd.DataFrame:
        """All yearly rates for this scenario (years x variables)."""
        return pd.DataFrame(self._rates).loc[self.base_year + 1:]

    def grow(self, h: pd.DataFrame, from_year: int, to_year: int) -> pd.DataFrame:
        """Move market and just values and income components forward. Assessed values, exemptions
        and tax are the projection engine's job (caps, resets), not this function's."""
        out = h.copy()
        hv = self.index("home_value", from_year, to_year)
        for c in ["valp_market_cal", "valp_jv_cal"]:
            if c in out:
                out[c] = out[c] * hv
        comps = self.spec["income_growth"]
        for col, var in comps.items():
            if col in out:
                out[col] = out[col] * self.index(var, from_year, to_year)
        present = [c for c in comps if c in out]
        if present and "hincp_aged" in out:
            # total income moves with its components; parts not listed (none today) stay put
            before = h[present].fillna(0).sum(axis=1)
            after = out[present].fillna(0).sum(axis=1)
            out["hincp_aged"] = h["hincp_aged"] + (after - before)
        return out
