# Gadsden 2025 district millage

No district table was found, so totals are built from components.

## Components

- **County and cities**, from DOR Table 1 2025-26 adopted rates (data/raw/fl_rates_2025/table1/Gadsden.pdf):
  - County BCC 9.0000
  - Chattahoochee 3.0000
  - Greensboro 5.0000
  - Gretna 5.2847
  - Havana 3.0000
  - Midway 4.6839
  - Quincy 6.8718
- **School:** 5.2480, from inputs/fl_school_millage_2025.csv (FLDOE 2025-26 district budget).
- **Northwest Florida WMD:** 0.0207. This is the FY2025-26 rolled-back rate the Governing Board adopted at the 9/24/2025 final hearing. Source: https://nwfwater.com/business-finance/district-budget/, which says the board "adopted a rolled-back millage rate of .0207", down from 0.0218 in FY2024-25.

## Code mapping

Each roll code has a single PHY_CITY for 100% of its parcels:

| Code | Area |
|---|---|
| 001 | Chattahoochee |
| 002 | Greensboro |
| 003 | Gretna |
| 004 | Havana |
| 005 | Midway |
| 006 | Quincy |
| 007 | "COUNTY" (unincorporated) |

## Results

Unincorporated is 14.2687. Cities range from 17.27 to 21.14. City minus unincorporated equals the city millage by construction.

## Coverage and confidence

7 of 7 codes, so 100% of 9,686 homesteads. Confidence medium.

Not included: any city voted debt or independent special district. DOR Table 1 lists only county and municipal operating levies, so totals could be slightly low if any such levies exist.
