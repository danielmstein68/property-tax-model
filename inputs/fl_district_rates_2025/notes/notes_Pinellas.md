# Pinellas 2025 rates
- TACD (PA "Municipal/Fire Dist 2025 final rates") has one row per district: 3 local-authority rate columns (final, rolled-back, prior), 15 component columns, then two DIST TOTAL columns (Real Property, Tangible Personal Property).
- Used the first DIST TOTAL (real property): the 15 components sum to it exactly for every row (asserted). The TPP total excludes some levies (e.g. fire/library) and is not used.
- Rows were matched by the trailing code token on each data line (codes with wrapped descriptions such as CW, ETF, PHMT, PPW print the code on a separate line).
- Components are 2025: county general 4.5423 and fire district rates (Seminole Fire 1.80, Clearwater Fire 1.37, Largo Fire 1.62, Gandy 0.78) match Table 1 2025 adopted.
- School millage 6.2930 in every district. Totals range ~13.9 (Belleair Shore) to ~22.9 (Lealman fire + Pinellas Park water).
