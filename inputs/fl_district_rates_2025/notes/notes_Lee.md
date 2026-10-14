# Lee 2025 district millage

**Source:** LeePA "2025 Taxing District Millage Book", https://www.leepa.org/TaxRoll/Millage%20Books/2025%20Taxing%20District%20Millage%20Book.pdf (saved as data/raw/fl_rates_2025/appraisers/lee_2025_millage_book.pdf; 109 pages, printed 10/13/2025). The book has one block per 3-digit district. The value used is the ACTUAL column of each district's TOTALS line.

**Checks**
- In all 108 districts, the ACTUAL authority rates sum to the printed total.
- District 001 = 14.6810, as expected.
- School is 2.2480 + 3.0710 = 5.3190 in every district, which matches inputs/fl_school_millage_2025.csv.
- County 3.7623, Fort Myers 6.5000 and Cape Coral 5.1471 match DOR Table 1.
- Totals for roll codes range from 10.83 to 16.53.

**Coverage:** 92 of 93 roll codes; 215,205 of 215,468 homesteads (99.88%).

## ISSUE: roll code 325

Roll code 325 (794 parcels, 263 homesteads, PHY_CITY Fort Myers) is not in the 2025 book. It is presumably a district created for 2026. Its total is left blank and not imputed. If it turns out to be a City of Fort Myers CRA sub-area, all such districts are 16.5269 in 2025.

The book also has district 000 (centrally assessed), which is excluded, and district 312 "DISTRICT TO BE REVIEWED" (9.3708), which is not in the roll but is written.

**Replaced (2026-10-14):** 106 of 108 codes now use DOR's 2025 TACD spreadsheet (district "Millage" column = sum of its authority rates). It differs from the appraiser millage book mostly by 0.0235 mills: Lee County Mosquito Control 0.2116 (DOR) vs 0.2351 (book); not independently confirmed. Codes 312 and 325 aren't in the DOR file (312 kept from the book; 325 blank).
