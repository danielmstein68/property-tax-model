# Baker 2025 district millage

**Source:** Baker County Property Appraiser "Tax Rates" page, https://www.bakerpa.com/taxrates.html (saved as data/raw/fl_rates_2025/appraisers/baker_taxrates.html), section "Total Millage Rate by Taxing District" (2025 rates).

**Method:** the published district totals are used directly.
- CO/SA/GL/MA = 13.6516
- MC (Macclenny) = 17.2516
- SR (Suwannee River WMD area) = 13.7535

**Checks**
- 7.2916 county + 5.3250 school + 0.8557 hospital + 0.1793 SJRWMD = 13.6516.
- Adding Macclenny's 3.6000 gives 17.2516. SR uses SRWMD 0.2812 instead, giving 13.7535.
- County 7.2916 and Macclenny 3.6000 match the DOR Table 1 adopted 2025-26 rates.
- School 5.3250 matches inputs/fl_school_millage_2025.csv.
- City minus unincorporated = 3.6000, which is the city millage.

**Coverage:** all 5 roll codes (CO, GL, MC, SA, SR), so 100% of 5,884 homesteads. Confidence high.

**Uncertainty:** the page labels the column "2025 Rate", not "final". The values match the DOR adopted rates.
