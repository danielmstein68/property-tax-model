# Brevard 2025 district millage

**Source:** BCPAO / Tax Collector "2025 Millage" matrix, https://www.bcpao.us/Docs/Taxroll/2025/Millage_2025.pdf (saved as data/raw/fl_rates_2025/appraisers/brevard_millage_2025.pdf). Authorities are rows; there are 39 value columns and a TOTALS row.

## Method

Plain text extraction scrambles the header, so glyph positions were rebuilt from the PDF content stream (TJ kerning offsets, font /W widths and clip paths).

Each column has one code in the bottom header row. 13 more codes are stacked above some columns:
- 1000/1800
- 13D0/23D0
- 13E0/23E0/43E0
- 15D0/26D0
- 2200/2400
- 2500/2600
- 34K0/43K0/53K0
- 34U0/54U0
- 34V0/52V0
- 41P0/51P0
- 4200/420Y
- 42P0/52P0
- 4300/430Y

Every stacked code sits within 0.2 pt of its column's x position. The table has only 39 totals, so stacked codes share their column's values and total. Within each stack the city letter is the same and only the 2-digit prefix differs, which is consistent with this reading.

## Checks

- **Column sums:** summing each column's authority cells reproduces the TOTALS row for 36 of 39 columns.
- **Fire MSTU cells:** the other 3 columns (13D0 Cocoa, 13E0 Rockledge, 2700) differ by exactly 0.6431, from a Fire Control MSTU cell printed ".6431" with its leading digit clipped. Cocoa and Rockledge run their own fire departments, and no other Cocoa column carries the fire MSTU. So the printed TOTALS, which exclude it, are used.
- **School:** 3.0620 + 0.7480 + 1.5000 + 1.0000 = 6.3100, which matches inputs/fl_school_millage_2025.csv.
- **County:** the county rates match DOR Table 1 (BCC 2.8643, Library 0.3242, and so on).
- **City:** city rates match Table 1 operating rates. Melbourne, Palm Bay, Indialantic and Melbourne Beach also include voted debt, which Table 1 leaves out.

## Coverage

All 47 roll codes, so 100% of 182,055 homesteads. Totals range from 10.08 to 18.11. Confidence high.
