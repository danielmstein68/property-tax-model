# Sarasota 2025 district millage

There is no 2025 copy of the appraiser's millage-codes file. The Wayback Machine has only the 2022 and 2024 versions (on sc-pa.com) and nothing on sarasotapropertyappraiser.gov.

## Method (rebuild)

2025 totals = 2026 code-to-authority composition times 2025 certified rates.
- **Composition:** https://www.sarasotapropertyappraiser.gov/media/22algox5/millage-codes-with-rates-2026.xlsx (saved as data/raw/fl_rates_2025/appraisers/sarasota_millage_codes_2026.xlsx).
- **Rates:** the Tax Collector's "2025 Ad Valorem Taxes" list, https://sarasotataxcollector.gov/docs/2025Millage (saved as sarasota_taxcollector_2025millage.pdf; roll certified 10/03/2025, rev. 10/23/25).

2025 rates used:
- **County-wide:** county 3.2273, debt 0.0667, mosquito 0.0520, hospital 1.0420, WCIND 0.0394, SWFWMD 0.1831, Legacy Trail debt 0.0382.
- **EMS:** 0.7300, everywhere except Longboat Key, North Port and Venice.
- **Navigable Waterways MSTU:** 0.0300.
- **School:** 2.8470 + 3.2480 = 6.0950, which matches inputs/fl_school_millage_2025.csv. The 2026 file's 2.681 + 2.248 + 1.0 split corresponds to the 2025 3.248 local levy plus the state levy.
- **Cities:**
  - City of Sarasota 3.2730 + debt 0.1348.
  - Venice 3.8450 + debt 0.3405.
  - North Port 3.7667.
  - Longboat Key 1.9600 + debt 0.0380, plus Gulfside 0.5563 or Bayside 0.1391. The 2026 canal-maintenance levy is not in the 2025 list.
- **Special districts:** lighting districts are matched by name to the 2025 L-codes. Siesta Key Village PID 2.4647; Golden Gate Point 0.6148 + 0.5899; Downtown Improvement District 2.0000.

All 2025 rates match DOR Table 1 where it lists them.

## Checks and confidence

M0100 = 11.4737, and the city codes (M0200, M0300, M0420, M0430, M0500, M9100) equal the Tax Collector's own published 2025 subtotals: county-wide 10.7437 or 11.4737 plus the city totals. These codes are confidence high. Lighting and PID codes are confidence medium because they assume the 2026 composition also held in 2025. The range is 11.47 to 16.88.

## Coverage

All 62 roll codes, so 100% of 139,723 homesteads.

## Uncertainty

Lighting-district boundaries or code splits that changed between 2025 and 2026 would not be captured. The effect is at most about 0.3 mills.
