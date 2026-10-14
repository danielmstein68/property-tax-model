"""Florida tax rates (millage) by tax district, from DOR files.

Two inputs per county (scripts/fl_rates.py downloads them):
  TACD    tax district code -> millage components and total (codes match TAX_AUTH_CD on parcels)
  Table 1 each taxing authority's millage, rolled-back rate and taxes levied

Reading TACD tables: layouts differ by county, so the generic reader works line by line. For each
district code used in the county's parcel roll it finds the text lines containing that code and
takes the 2025 total as the number on the line that equals the sum of the line's component rates
(this tells the current-year total apart from the prior-year one printed next to it). Lines with
a single number take that number. Every county is then checked (check_county) before use.

School millage is countywide (one school district per county), so it comes from Table 1's school
board section; non-school millage = district total - school.
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
NUM = re.compile(r"(?<![\d,])\d{1,2}\.\d{2,5}(?![\d,])")  # millage-like numbers (no thousands separators)


def pdf_text(path: Path) -> str:
    return "\n".join(p.extract_text() or "" for p in PdfReader(path).pages)


def _total_from_line(nums: list[float], tol: float = 0.0025) -> tuple[float | None, str]:
    """Pick the line's total: the number equal to the sum of the smaller numbers before it."""
    if not nums:
        return None, "no numbers"
    if len(nums) == 1:
        return nums[0], "single number"
    for i, t in enumerate(nums):
        parts = [x for j, x in enumerate(nums) if j != i and x < t]
        # components are the numbers smaller than t, excluding any other total-sized numbers
        big = [x for x in parts if x > 0.6 * t]
        comps = [x for x in parts if x <= 0.6 * t]
        if comps and abs(sum(comps) - t) <= tol + 1e-4 * len(comps):
            return t, "sum of components"
        if comps and big and abs(sum(comps) - t) <= tol + 1e-4 * len(comps):
            return t, "sum of components"
    return None, "no sum match"


def parse_tacd(text: str, codes: list[str]) -> pd.DataFrame:
    """Total 2025 millage for each district code found in a TACD table's text."""
    lines = [l for l in text.splitlines() if l.strip()]
    rows = []
    for code in codes:
        variants = {code, code.lstrip("0") or "0"}
        found = None
        for k, line in enumerate(lines):
            toks = set(re.findall(r"[A-Za-z0-9]+", line))
            if not variants & toks:
                continue
            # numbers on this line; if none, look at the next line (codes printed on their own line)
            cand = [line] + ([lines[k + 1]] if k + 1 < len(lines) else [])
            for c in cand:
                nums = [float(x) for x in NUM.findall(c) if x not in variants]
                total, how = _total_from_line(nums)
                if total is not None:
                    found = (total, how, c.strip()[:120])
                    break
            if found:
                break
        rows.append({"code": code, "total_millage": found[0] if found else np.nan,
                     "method": found[1] if found else "not found", "line": found[2] if found else ""})
    return pd.DataFrame(rows)


def parse_table1(text: str) -> pd.DataFrame:
    """Authorities with 2024 millage/levy, rolled-back rate/levy, 2025 millage/levy; section label."""
    rows, section = [], None
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        m = re.match(r"^(.*?)\s+(\d+\.\d{3,4})\s+([\d,]+)\s*\$?\s+(\d+\.\d{3,4})\s+([\d,]+)\s*\$?\s+(\d+\.\d{3,4})\s+([\d,]+)", s)
        if m:
            name = m.group(1).strip()
            rows.append({"section": section, "authority": name,
                         "millage_2024": float(m.group(2)), "levy_2024": float(m.group(3).replace(",", "")),
                         "rolled_back": float(m.group(4)), "levy_rolled_back": float(m.group(5).replace(",", "")),
                         "millage_2025": float(m.group(6)), "levy_2025": float(m.group(7).replace(",", ""))})
        elif not re.match(r"^(TOTAL|County:|Millage|Rate)", s) and not re.search(r"\d", s):
            section = s  # section headers are plain text lines (e.g. "SCHOOL BOARD", "PINELLAS COUNTY BCC")
    return pd.DataFrame(rows)


def school_millage(t1: pd.DataFrame) -> float:
    """Sum of 2025 millage of school board levies (operating, debt, voted)."""
    sch = t1[t1["section"].fillna("").str.contains("SCHOOL", case=False)
             | t1["authority"].str.contains("School Board|School Dist", case=False)]
    sch = sch[~sch["authority"].str.contains("Charter|Readiness", case=False)]
    return float(sch["millage_2025"].sum())


def county_millage(t1: pd.DataFrame) -> float:
    """2025 millage of the county's general levy (BCC / County General)."""
    g = t1[t1["authority"].str.contains(r"BCC|Board of County|County General|General Fund", case=False)]
    return float(g["millage_2025"].iloc[0]) if len(g) else np.nan
