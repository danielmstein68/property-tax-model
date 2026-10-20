"""Build the results display page from the results file.

Usage:
    python scripts/build_display.py     # display/template.html + data/processed/results/fl_2026_status_quo.json
                                        #   + fl_projections.json (scripts/results_projections.py)
                                        #   + fl_policy_grid.json (scripts/policy_grid.py)
                                        #   + fl_a3_examples.json (scripts/a3_examples.py)
                                        #   + fl_2026_validation.json (scripts/validate_2026.py)
                                        #   + fl_household_deciles.json (scripts/household_deciles.py)
                                        #   + fl_offset_taxes.json (scripts/offset_taxes.py)
                                        #   + fl_a3_rentals.json (scripts/a3_rentals.py)
                                        #   + fl_a3_takeup_range.json (scripts/a3_takeup_range.py)
                                        #   + fl_a3_rec_by_government.json (scripts/check_rec_by_government.py)
                                        # -> display/fl_2026_status_quo.html (published as a private artifact)
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    res = ROOT / "data" / "processed" / "results"
    data = (res / "fl_2026_status_quo.json").read_text(encoding="utf-8")
    proj = (res / "fl_projections.json").read_text(encoding="utf-8")
    page = (ROOT / "display" / "template.html").read_text(encoding="utf-8")
    import json as _json
    g = _json.loads((res / "fl_policy_grid.json").read_text(encoding="utf-8"))
    for run in g.get("runs", {}).values():          # the static run is only used for yearly totals
        if isinstance(run.get("none_static"), dict):
            run["none_static"] = {"yearly": run["none_static"].get("yearly", [])}
    grid = _json.dumps(g, separators=(",", ":"))
    import json
    import yaml
    fin = json.dumps(yaml.safe_load((ROOT / "inputs" / "fl_local_finance_fy2024.yaml").read_text(encoding="utf-8")))
    rec = json.dumps(yaml.safe_load((ROOT / "inputs" / "fl_rec_amendment3.yaml").read_text(encoding="utf-8")))
    a3ex = (res / "fl_a3_examples.json").read_text(encoding="utf-8")      # scripts/a3_examples.py
    a3gov = (res / "fl_a3_rec_by_government.json").read_text(encoding="utf-8")   # scripts/check_rec_by_government.py
    a3rent = (res / "fl_a3_rentals.json").read_text(encoding="utf-8")   # scripts/a3_rentals.py
    a3range = (res / "fl_a3_takeup_range.json").read_text(encoding="utf-8")   # scripts/a3_takeup_range.py
    tx = (res / "tx_2026_status_quo.json").read_text(encoding="utf-8")   # scripts/tx_results.py
    offset = (res / "fl_offset_taxes.json").read_text(encoding="utf-8")   # scripts/offset_taxes.py
    hhdec = (res / "fl_household_deciles.json").read_text(encoding="utf-8")   # scripts/household_deciles.py
    val = json.dumps(json.loads((res / "fl_2026_validation.json").read_text(encoding="utf-8"))["statewide_homestead"])
    page = (page.replace("__DATA__", data).replace("__PROJ__", proj).replace("__GRID__", grid).replace("__FIN__", fin)
            .replace("__REC__", rec).replace("__A3EX__", a3ex).replace("__VAL__", val).replace("__HHDEC__", hhdec).replace("__OFFSET__", offset).replace("__A3RENT__", a3rent).replace("__A3RANGE__", a3range).replace("__TX__", tx).replace("__A3GOV__", a3gov))
    dest = ROOT / "display" / "fl_2026_status_quo.html"
    dest.write_text(page, encoding="utf-8")
    print(f"wrote {dest}")


if __name__ == "__main__":
    main()
