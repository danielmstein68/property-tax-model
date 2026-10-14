# Taylor 2025 rates
- TACD is not actually a scan: it has a text layer (code matrix + a "Millage rates" list). Read with pypdf text and position extraction.
- Rates: County 7.2426, School-State 3.139, School-Local 2.498, SRWMD 0.2812, MSTU 1.225, City of Perry 5.8336 (all match Table 1 2025 adopted).
- The code matrix marks County/School-State/School-Local/SRWMD for both CO and PE but has no columns for MSTU or the city. Assumed MSTU applies to unincorporated only (Table 1 MSTU levy 1.71M at 1.225 implies ~1.39B base vs ~1.72B county base, i.e. excludes Perry) and Perry's city millage to PE.
- CO = 14.3858, PE = 18.9944; school 5.637. Medium confidence because MSTU/city assignment is inferred.
