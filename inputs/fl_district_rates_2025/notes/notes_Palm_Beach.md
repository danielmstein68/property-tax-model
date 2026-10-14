# Palm Beach 2025 district millage

## Source

The 2025 PBCPAO "Taxing Authority Code Description" table, recovered from the Internet Archive:
https://web.archive.org/web/20260106174251/https://pbcpao.gov/pdf/taxroll/Palm_Beach_County_Tax_Auth_Code_Description.pdf
It is saved as data/raw/fl_rates_2025/appraisers/palmbeach_2025_tax_auth_code_wayback20260106.pdf. County debt 0.033 and school state 3.073 show it is the 2025 version.

The table spans 9 pages: 3 column panels times 3 row pages. Rows were rejoined by y-position and the TOTAL column used.

Also saved for reference:
- the 2025_Final_vs_Proposed_Millage_Rates PDF (Wayback, 2026-01-06)
- the current 2026 code table
- 2026_Proposed_Rollback_025_Final_Millage_Rates.pdf

## Independent check

The totals were also rebuilt from the 2026 code-to-authority composition times the 2025 final authority rates (the "2025 Final" column), with these adjustments:
- Jupiter Fire/Rescue MSTU 1.7251, from DOR Table 1
- Atlantis NBHD district is new in 2026, so 0 in 2025
- Riviera Beach debt is 0 in 2025
- Boca Beach & Park 1.08, WPB DDA 0.97, Delray DDA 1.00

The rebuild matches the archived total exactly for all 118 codes present in both years.

School is 6.3210 (3.248 + 3.073), which matches inputs/fl_school_millage_2025.csv. Unincorporated is 16.2652; the range is 14.87 to 22.81.

## Coverage

89 of 93 roll codes are in the 2025 table. Four 2026 codes are new:
- 02432 (Atlantis; 2025 codes 02982/02983)
- 30581 (Jupiter; 2025 code 30571)
- 56421 and 56427 (Riviera Beach; 2025 codes 56401/56407)

Each gets the single 2025 value of its city, which also equals the rebuild. Confidence is medium for these four codes (22,560 homesteads). Overall, 100% of 366,403 homesteads are covered.
