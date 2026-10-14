"""Build the results display page from the results file.

Usage:
    python scripts/build_display.py     # display/template.html + data/processed/results/fl_2026_status_quo.json
                                        # -> display/fl_2026_status_quo.html (published as a private artifact)
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    data = (ROOT / "data" / "processed" / "results" / "fl_2026_status_quo.json").read_text(encoding="utf-8")
    page = (ROOT / "display" / "template.html").read_text(encoding="utf-8").replace("__DATA__", data)
    dest = ROOT / "display" / "fl_2026_status_quo.html"
    dest.write_text(page, encoding="utf-8")
    print(f"wrote {dest}")


if __name__ == "__main__":
    main()
