"""Load and validate the property tax law spec (inputs/<state>_law.yaml).

The YAML file is the source of truth for the rules: every amount, cap, limit, which levies a
rule applies to, and the order exemptions are applied — each with its citation, quoted source
text and a confidence flag. The model reads parameters from here; editing the file changes the
model. Logic (how rules combine) lives in code; most changes, including policy alternatives,
are edits to this file.

Year-varying values are written as {year: value}. A value applies from its year until the next
listed year (so {2024: 25000, 2025: 25722} gives 25,722 for 2026 too). Asking for a year
before the first listed one is an error.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIDENCE = {"high", "medium", "low"}
EXEMPTION_KINDS = {"fixed", "band", "total", "percent", "local_option", "reduction"}
REQUIRED = ["description", "citation", "source_text", "source_url", "confidence"]


class LawError(ValueError):
    pass


def value_for(v: Any, year: int, name: str = "") -> Any:
    """Resolve a {year: value} mapping (or a plain value) for `year`."""
    if not isinstance(v, dict):
        return v
    years = sorted(int(y) for y in v)
    usable = [y for y in years if y <= year]
    if not usable:
        raise LawError(f"{name}: no value for {year} (first listed year is {years[0]})")
    return v[usable[-1]] if usable[-1] in v else v[str(usable[-1])]


@dataclass
class Rule:
    id: str
    section: str
    spec: dict

    def get(self, key: str, year: int | None = None, default: Any = None) -> Any:
        v = self.spec.get(key, default)
        return value_for(v, year, f"{self.id}.{key}") if year is not None else v


@dataclass
class Law:
    state: str
    levy_classes: list[str]
    meta: dict
    rules: dict[str, Rule] = field(default_factory=dict)

    def rule(self, rule_id: str) -> Rule:
        if rule_id not in self.rules:
            raise LawError(f"no rule '{rule_id}' in the {self.state} law spec")
        return self.rules[rule_id]

    def exemptions(self) -> list[Rule]:
        """Exemption rules in the order they are applied."""
        ex = [r for r in self.rules.values() if r.section == "exemptions"]
        return sorted(ex, key=lambda r: r.spec["order"])


def load_law(state: str = "fl", path: Path | None = None) -> Law:
    path = path or ROOT / "inputs" / f"{state}_law.yaml"
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    meta = raw.get("meta", {})
    levies = meta.get("levy_classes", [])
    law = Law(state=meta.get("state", state.upper()), levy_classes=levies, meta=meta)
    problems = []
    for section in ["assessment", "exemptions", "taxable"]:
        for rid, spec in (raw.get(section) or {}).items():
            if rid in law.rules:
                problems.append(f"{rid}: duplicate rule id")
            missing = [k for k in REQUIRED if not spec.get(k)]
            if missing:
                problems.append(f"{rid}: missing {', '.join(missing)}")
            if spec.get("confidence") not in CONFIDENCE:
                problems.append(f"{rid}: confidence must be one of {sorted(CONFIDENCE)}")
            bad = set(spec.get("applies_to", [])) - set(levies)
            if bad:
                problems.append(f"{rid}: applies_to has unknown levy classes {sorted(bad)}")
            if section == "exemptions":
                if spec.get("kind") not in EXEMPTION_KINDS:
                    problems.append(f"{rid}: kind must be one of {sorted(EXEMPTION_KINDS)}")
                if "order" not in spec:
                    problems.append(f"{rid}: exemptions need an 'order'")
                if not spec.get("household_flag"):
                    problems.append(f"{rid}: exemptions need a 'household_flag' (who gets it)")
            law.rules[rid] = Rule(rid, section, spec)
    orders = [r.spec.get("order") for r in law.exemptions() if "order" in r.spec]
    if len(orders) != len(set(orders)):
        problems.append("exemption 'order' values must be unique")
    if problems:
        raise LawError(f"{path} has problems:\n  - " + "\n  - ".join(problems))
    return law
