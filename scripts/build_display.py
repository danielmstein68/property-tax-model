"""Build the results display page from the results file.

Usage:
    python scripts/build_display.py     # display/template.html + data/processed/results/fl_2026_status_quo.json
                                        #   + fl_projections.json (scripts/results_projections.py)
                                        # -> display/fl_2026_status_quo.html (published as a private artifact)
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    res = ROOT / "data" / "processed" / "results"
    data = (res / "fl_2026_status_quo.json").read_text(encoding="utf-8")
    proj = (res / "fl_projections.json").read_text(encoding="utf-8")
    page = (ROOT / "display" / "template.html").read_text(encoding="utf-8")
    page = page.replace("__DATA__", data).replace("__PROJ__", proj)
    dest = ROOT / "display" / "fl_2026_status_quo.html"
    dest.write_text(page, encoding="utf-8")
    print(f"wrote {dest}")


if __name__ == "__main__":
    main()
