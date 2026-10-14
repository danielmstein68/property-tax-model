# Broward 2025 district millage

**Source:** BCPA "2025 Final Millage Rate Table", https://bcpa.net/Includes/Downloads/2025/2025%20Final%20Millage%20Rate%20Table.pdf (saved as data/raw/fl_rates_2025/appraisers/broward_2025_final_millage.pdf). The FINAL file is used, not the Proposed one. It has one row per 4-digit code. The "Total Real Property" column is used; the "Personal Property" column differs only by Hillsboro Inlet 0.1250.

**Checks**
- Each row's components sum to its total (asserted while parsing, 41 codes).
- 0312 Ft Lauderdale = 18.4464, as expected.
- School 6.3200 + 0.1645 debt = 6.4845, which matches inputs/fl_school_millage_2025.csv.
- County 5.6658 and the city operating rates match DOR Table 1 adopted values.
- Totals range from 16.28 to 23.19.

**Coverage:** all 70 roll codes have a value, so 100% of 419,037 homesteads have a number. Table codes that are not in the 2026 roll are also written (note "not in 2026 roll").

## ISSUE needing a human decision: letter-suffixed codes

75,137 homesteads (17.9%) are on roll codes with a letter suffix, for example 0012K, 1013H, 2412H, 3212I, 1112A, 1512B/E/F, 1912M-W, 2212N/T and 2513O/V.

The suffix marks a special district listed at the bottom of the table:
- Central Broward Water 0.8900 (land only)
- Cocomar Water 0.1363
- Water Mgt 2/3/4A/4B/4C, 0.0121-0.1325
- Golden Isles, Three Islands, Habitat, Isles of Inverrary and Windermere safe-neighborhood districts, 0.4584-2.0000
- Plantation Gateway 1.7108 and Plantation Midtown 0.9707
- Sunrise Key Safe 1.0000
- County Street Lighting 0.3743

The table gives no key from suffix letter to district. These codes therefore carry the BASE 4-digit total only (confidence medium) and are understated by that special levy. Homesteads by suffix:
- H: 33,481. The cities (Davie, Cooper City, Pembroke Pines, SW Ranches, Hollywood, unincorporated) suggest Central Broward Water Control (land only).
- I: 14,845. Coconut Creek and Margate suggest Cocomar.
- A: 11,897. Deerfield Beach.
- F: 3,250. B: 3,119. E: 2,391. K: 2,116. V: 1,593. G: 1,145. The rest are small.

These are not imputed. A suffix-to-district key from BCPA (or the NAL special-district fields) would resolve them.

**Replaced (2026-10-14):** all 74 codes now use DOR's 2025 TACD spreadsheet ("Total Real Property"), which includes the letter-suffixed special-district codes (e.g. H = Central Broward Water Control 0.89, I = Cocomar 0.1363, K = county street lighting 0.3743). 28 codes changed.
