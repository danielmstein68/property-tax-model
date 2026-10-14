"""Generate the readable rules page from the law spec.

Usage:
    python scripts/law_page.py            # inputs/fl_law.yaml -> docs/FL_LAW.md

The page is generated — edit inputs/fl_law.yaml, not the page. It lists every rule with its
values by year, which levies it applies to, its citation, the quoted source text and a
confidence flag (low/medium items first in the review list).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ptm.law import load_law  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SKIP = {"description", "citation", "source_text", "source_url", "confidence", "notes"}
BADGE = {"high": "✅ high", "medium": "🟡 medium", "low": "🔴 low"}


def fmt(v) -> str:
    if isinstance(v, dict):
        return "; ".join(f"{k}: {fmt(x)}" for k, x in v.items())
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    if isinstance(v, float) and v < 1:
        return f"{v:.1%}" if v * 1000 == int(v * 1000) else str(v)
    if isinstance(v, int) and v >= 1000:
        return f"{v:,}"
    return str(v)


def main(state: str = "fl") -> None:
    law = load_law(state)
    out = [f"# {law.state} property tax law — rules spec",
           "",
           f"_Generated from `inputs/{state}_law.yaml` by `scripts/law_page.py`. **Do not edit this page** — "
           "edit the YAML (or ask Claude to). Every value below is what the model uses._",
           "",
           f"- **Law as of:** {law.meta.get('as_of', '')}",
           f"- **Levy classes:** {', '.join(law.levy_classes)}",
           f"- **Scope:** {law.meta.get('scope', '')}",
           ""]
    review = [r for r in law.rules.values() if r.spec["confidence"] != "high"]
    out += ["## Needs review", ""]
    out += [f"- **{r.id}** ({BADGE[r.spec['confidence']]}): {r.spec.get('notes', '').strip() or r.spec['description'].strip()}"
            for r in sorted(review, key=lambda r: r.spec["confidence"] != "low")] or ["- Nothing flagged."]
    out.append("")

    titles = {"assessment": "Assessment", "exemptions": "Exemptions (in the order applied)", "taxable": "Taxable value and tax",
              "rates": "Setting rates (TRIM)"}
    for section in ["assessment", "exemptions", "taxable", "rates"]:
        rules = law.exemptions() if section == "exemptions" else [r for r in law.rules.values() if r.section == section]
        if not rules:
            continue
        out += [f"## {titles[section]}", ""]
        for r in rules:
            s = r.spec
            head = f"### {s['order']}. {r.id}" if section == "exemptions" else f"### {r.id}"
            out += [head, "", s["description"].strip(), ""]
            params = {k: v for k, v in s.items() if k not in SKIP}
            if params:
                out += ["| Parameter | Value |", "|---|---|"]
                out += [f"| {k} | {fmt(v)} |" for k, v in params.items()]
                out.append("")
            out += [f"**Source:** [{s['citation']}]({s['source_url']}) · **Confidence:** {BADGE[s['confidence']]}", "",
                    "> " + " ".join(s["source_text"].split()), ""]
            if s.get("notes"):
                out += [f"_Note:_ {' '.join(s['notes'].split())}", ""]
    dest = ROOT / "docs" / f"{state.upper()}_LAW.md"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {dest} ({len(law.rules)} rules, {len(review)} flagged for review)")


if __name__ == "__main__":
    main(*sys.argv[1:])
