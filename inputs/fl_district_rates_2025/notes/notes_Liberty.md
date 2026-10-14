# Liberty 2025 district millage

No district table was found, so totals are built from components.

## Components

- **County and city:** county BCC 9.2240 and City of Bristol 6.5567, from DOR Table 1 2025-26 adopted rates (data/raw/fl_rates_2025/table1/Liberty.pdf).
- **School:** 5.3800, from inputs/fl_school_millage_2025.csv (FLDOE).
- **NWFWMD:** 0.0207, the FY2025-26 adopted rolled-back rate (https://nwfwater.com/business-finance/district-budget/).

## Code mapping (inferred, not documented)

- **Code "1"** (2,906 parcels; PHY_CITY Bristol 1,875, Hosford 752, Telogia 147) is taken as unincorporated county: 14.6247.
- **Code "2"** (436 parcels, 96% PHY_CITY Bristol) is taken as the City of Bristol: 21.1814.

Code 1 spans several communities and is much larger, and Bristol is the county's only municipality, so this is the natural reading. But "Bristol" is also the postal city for unincorporated land, so the mapping is not certain.

## Coverage and confidence

2 of 2 codes, so 100% of 1,419 homesteads. Confidence is medium for code 1 and low for code 2 (because of the mapping).

Not included: city voted debt or special districts, if any exist.
