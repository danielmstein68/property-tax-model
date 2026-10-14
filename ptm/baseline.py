"""Build the base-year household file: PUMS households aged and reweighted.

    from ptm.baseline import build_baseline, load_baseline
    df = build_baseline()          # builds and saves data/processed/baseline_fl_2026.parquet
    df = load_baseline()           # later steps just load it

Steps (Florida, 2024 PUMS -> 2026):
  1. load occupied households (ptm.load)
  2. age income by type, person by person (ptm.aging.add_aged_income)
  3. age rents by CPI area (add_aged_rent)
  4. age home values by county x type x tier, market and just value (add_aged_values)
  5. replace top-coded home values with draws from the roll's top homesteads (ptm.topcode)
  6. age reported property tax with Save Our Homes and homestead rules (add_aged_taxamt_rules)
  7. reweight for homes built after the survey (ptm.reweight)
  8. link to the parcel roll (ptm.link): mobile homes on rented lots, then homestead status
     (roll counts by PUMA x type; households chosen mainly by the implied-rate test)
  9. calibrate just values to the roll by county group x home type (ptm.calibrate)
 10. assessment gaps (school and non-school assessed / just) from roll donors (ptm.gaps)
 11. special exemptions (veterans, disabled, low-income seniors) matched to roll counts, modelled
     taxable value, and classification of $0-tax owners (ptm.exemptions)
 12. tax districts and 2025 millage (latest published) from roll donors; modelled tax (ptm.millage)

Not yet in the baseline (next steps):
calibration to the roll and published levies (incl. top-coded tax), renters' tax burden.

A JSON file next to the Parquet records when and from what it was built.
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path

import pandas as pd

from ptm.aging import (add_aged_income, add_aged_rent, add_aged_taxamt_rules, add_aged_values)
from ptm.calibrate import calibrate_values
from ptm.exemptions import assign_exemptions
from ptm.gaps import assign_assessment_gaps
from ptm.millage import assign_districts
from ptm.link import assign_homestead, assign_mobile_home_lots
from ptm.load import load_households
from ptm.reweight import new_home_targets, reweight_new_development
from ptm.topcode import impute_topcoded_values

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ["aging_factors_{base}.csv", "value_growth_fl_{base}.csv", "just_value_ratio_fl_{base}.csv",
          "fl_soh_history.csv"]


def _path(base_year: int) -> Path:
    return ROOT / "data" / "processed" / f"baseline_fl_{base_year}.parquet"


def build_baseline(survey_year: int = 2024, base_year: int = 2026, save: bool = True) -> pd.DataFrame:
    raw = ROOT / "data" / "raw" / f"pums_{survey_year}_1yr"
    h = load_households(raw / "psam_h12.csv")
    h = add_aged_income(h, raw / "psam_p12.csv", base_year)
    h = add_aged_rent(h, base_year)
    h = add_aged_values(h, base_year)
    h, tc_report = impute_topcoded_values(h, base_year)
    h = add_aged_taxamt_rules(h, survey_year, base_year)
    h["WGTP_survey"] = h["WGTP"]
    h, report = reweight_new_development(h, new_home_targets(base_year, survey_year), survey_year)
    h, mh_report = assign_mobile_home_lots(h, base_year)
    h, hs_report = assign_homestead(h, base_year, raw / "psam_p12.csv", survey_year=survey_year)
    h, cal_report = calibrate_values(h, base_year)
    h, gap_report = assign_assessment_gaps(h, base_year)
    h, ex_report = assign_exemptions(h, base_year, raw / "psam_p12.csv")
    h, district_report = assign_districts(h, base_year)
    h["survey_year"], h["base_year"] = survey_year, base_year

    if save:
        dest = _path(base_year)
        dest.parent.mkdir(parents=True, exist_ok=True)
        h.to_parquet(dest, index=False)
        report.to_csv(dest.with_name(f"baseline_fl_{base_year}_newdev_report.csv"), index=False)
        mh_report.to_csv(dest.with_name(f"baseline_fl_{base_year}_mobile_home_report.csv"), index=False)
        hs_report.to_csv(dest.with_name(f"baseline_fl_{base_year}_homestead_report.csv"), index=False)
        tc_report.to_csv(dest.with_name(f"baseline_fl_{base_year}_topcode_report.csv"), index=False)
        cal_report.to_csv(dest.with_name(f"baseline_fl_{base_year}_value_calibration_report.csv"), index=False)
        gap_report.to_csv(dest.with_name(f"baseline_fl_{base_year}_assessment_gap_report.csv"), index=False)
        ex_report.to_csv(dest.with_name(f"baseline_fl_{base_year}_exemptions_report.csv"), index=False)
        district_report.to_csv(dest.with_name(f"baseline_fl_{base_year}_tax_district_report.csv"), index=False)
        try:
            commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                                    capture_output=True, text=True).stdout.strip()
        except OSError:
            commit = None
        meta = {
            "built_at": datetime.now().isoformat(timespec="seconds"),
            "git_commit": commit,
            "survey_year": survey_year,
            "base_year": base_year,
            "pums_files": [(raw / f).relative_to(ROOT).as_posix() for f in ("psam_h12.csv", "psam_p12.csv")],
            "inputs": [f"inputs/{f.format(base=base_year)}" for f in INPUTS],
            "parcel_roll": f"data/processed/fl_nal_{base_year}/ (see _checks.csv for roll stages)",
            "households": int(len(h)),
            "weighted_households": round(float(h["WGTP"].sum())),
        }
        dest.with_suffix(".json").write_text(json.dumps(meta, indent=2))
    return h


def load_baseline(base_year: int = 2026) -> pd.DataFrame:
    return pd.read_parquet(_path(base_year))
