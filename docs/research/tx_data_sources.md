# Texas model: data sources (checked 2026-10-20)

Sources for a Texas property tax microsimulation: tax year 2026 base, projections to 2036. Each URL was
checked on 2026-10-20, with HTTP HEAD for size and date where the server allowed it. Nothing large was
downloaded; only small layout and summary files (under 8 MB) were opened. "Not verified" means the page
could not be reached or read from here and needs a person with a normal browser.

## 0. Coverage: residence homesteads by appraisal district (tax year 2024)

Derived from the Comptroller's 2024 final PVS ISD worksheet export
(`https://comptroller.texas.gov/taxes/property-tax/docs/2024-final-isd-worksheet-export-detail.xlsx`,
1.5 MB). The method: column `LOSS SCND INCR HMSTD` (value lost to the $10k step) ÷ $10,000, summed by
`CAD NAME`. Statewide total is **6,150,680**, which matches `texas_homestead_takeup.md` (Harris 850,527 exact).
2025 counts from the same method are unreliable (see that note), so 2024 is used for ranking.

| # | Appraisal district | Homesteads 2024 | Share | Cumulative |
|---|---|---|---|---|
| 1 | Harris (HCAD) | 850,527 | 13.8% | 13.8% |
| 2 | Tarrant (TAD) | 412,475 | 6.7% | 20.5% |
| 3 | Bexar (BCAD) | 412,004 | 6.7% | 27.2% |
| 4 | Dallas (DCAD) | 411,710 | 6.7% | 33.9% |
| 5 | Travis (TCAD) | 259,631 | 4.2% | 38.1% |
| 6 | Collin (CCAD) | 249,818 | 4.1% | 42.2% |
| 7 | Fort Bend (FBCAD) | 210,246 | 3.4% | 45.6% |
| 8 | Denton (DCAD) | 208,804 | 3.4% | 49.0% |
| 9 | El Paso (EPCAD) | 177,867 | 2.9% | 51.9% |
| 10 | Williamson (WCAD) | 162,238 | 2.6% | 54.6% |
| 11 | Montgomery (MCAD) | 160,008 | 2.6% | 57.2% |
| 12 | Hidalgo | 141,058 | 2.3% | 59.4% |
| 13 | Brazoria | 90,391 | 1.5% | 60.9% |
| 14 | Galveston | 85,817 | 1.4% | 62.3% |
| 15 | Bell | 72,935 | 1.2% | 63.5% |
| 16–20 | Nueces 72,379; Cameron 72,045; Lubbock 60,041; Hays 59,199; Potter-Randall 54,557 | | | 68.7% |

The top 12 cover 59.4% of state homesteads and the top 15 cover 63.5%. Districts 13–15 are cheap to add
because all three publish free exports.

## 1. Appraisal district bulk roll files

**The common layout.** Most large districts on True Automation / True Prodigy PACS publish the
"Appraisal Export" (Legacy 8.0.x): fixed-width TXT files `APPRAISAL_INFO.TXT` (property),
`APPRAISAL_ENTITY_INFO.TXT` (property × taxing unit), `APPRAISAL_ENTITY_TOTALS.TXT`,
`APPRAISAL_IMPROVEMENT_DETAIL.TXT`, `APPRAISAL_LAND_DETAIL.TXT`, `APPRAISAL_STATE_CODE.TXT`, and others.
Its fields were checked in layout 8.0.33 (TAD's copy, 99 KB):
- **Property file:** `market_value`, `appraised_val`, `ten_percent_cap` (homestead cap loss), `nhs_cap_loss`
  (20% circuit breaker, s. 23.231), `assessed_val`, `hs_exempt` flag, `imprv_state_cd` and
  `land_state_cd` (state category codes such as A1), and homestead / non-homestead land and improvement values.
- **Property-entity file, per taxing unit:** `entity_cd`, `market_value`, `appraised_value`, `hs_cap`,
  `hs_state_amt`, `hs_local_amt`, `ov65_amt`, `dp_amt`, `dv_amt`, `dvhs_amt`, `ex_amt`, `taxable_val`,
  `freeze_yr`, and `freeze_ceiling` (the over-65/disabled school tax ceiling).
- **Improvement detail file:** `yr_built`.

So the PACS districts give everything the model needs, including tax ceilings.

**The Comptroller's EARS format** (Electronic Appraisal Roll Submission, manual 96-1051:
https://comptroller.texas.gov/taxes/property-tax/docs/96-1051.pdf, 7.6 MB, not read in full) is a
statewide uniform parcel-level format that every appraisal district sends to the Comptroller each year
for the PVS. TCAD posts its own (`https://traviscad.org/wp-content/largefiles/227EARS082626.zip`,
103 MB, 2026). A Public Information Act request to the Comptroller for all districts' 2026 EARS
submissions could cover the whole state in one format. That is unconfirmed; see blockers.

| District | 2026 certified file (URL) | Format / size | Fields | Access / notes |
|---|---|---|---|---|
| **Harris (HCAD)** | Base path `https://download.hcad.org/data/CAMA/2026/`, with `Real_acct_owner.zip` (212 MB, modified 2026-10-18), `Real_jur_exempt.zip` (114 MB), `Real_building_land.zip` (235 MB), `Code_description_real.zip` (175 KB), `Hearing_files.zip` (19 MB), and `Real_acct_ownership_history.zip` (31 MB). 2025 is at the same path with `/2025/`. Landing page: https://hcad.org/hcad-online-services/pdata/ | Tab-delimited TXT in ZIP; HCAD's own layout, not PACS | `real_acct`: market, appraised, state class. `jur_exempt`: exemption codes and amounts per jurisdiction. Building file: year built. Codebook: https://hcad.org/assets/uploads/pdf/pdataCodebook.pdf | Free with no registration. Files are refreshed weekly after mid-August certification, so they are "certified plus supplements", not frozen. HCAD gives no technical support. The file links are JS-rendered on the page, but the direct paths work. |
| **Dallas (DCAD)** | `https://www.dallascad.org/ViewPDFs.aspx?type=3&id=%5C%5CDCAD.ORG%5CWEB%5CWEBDATA%5CWEBFORMS%5CDATA%20PRODUCTS%5CDCAD2026_CERTIFIED_07232026.zip` (CSV at certification, 193 MB). Fixed-format roll: same pattern with `2026_REAL_PROPERTY_CERT_APPR_ROLL.zip` (125 MB). With supplements: `DCAD2026_CURRENT.ZIP`. Page: https://www.dallascad.org/DataProducts.aspx | Comma-delimited CSV in ZIP; field documents inside the ZIP | Values, exemptions per taxing unit, state codes, year built (per DCAD's file set; field list inside the ZIP, not opened) | Free. The backslashes in the URL must be percent-encoded (`%5C`), or the request is sent to an error page. 2022–2026 are listed. |
| **Tarrant (TAD)** | True Prodigy extract, all taxing units: `https://www.tad.org/content/data-download/000_Tarrant_All_Taxing_Units.zip` (741 MB, revised weekly, modified 2026-10-17). Layout: `.../TP_Legacy8.0.33-AppraisalExportLayout.zip` (99 KB). Also `PropertyData(Delimited).ZIP` (102 MB, pipe-delimited, 2026 certified). Page: https://www.tad.org/resources/data-downloads | PACS Appraisal Export 8.0.33 (fixed width) | Full PACS set as above | Free. TAD's own Exemptions file leaves out over-65 exemptions (citing s. 25.027) and is being phased out for 2026; use the TP extract. 2021–2025 certified PropertyData ZIPs are kept. |
| **Bexar (BCAD)** | **No public bulk file found.** https://bcad.org/reports/ has only certified totals PDFs (2026: `https://bcad.org/wp-content/uploads/2026/07/2026-Certified-Totals-Report.pdf`). | n/a | n/a | **Needs a request.** BCAD's PIA form (https://bcad.org/wp-content/uploads/2026/04/BCAD-Public-Information-Act-Request.pdf) says it "may offer access" to the appraisal data export through its FTP server. Requests go to OpenRecords@bcad.org. Property search has moved to Harris Govern (hgo.harrisgovern.com/bexar). |
| **Travis (TCAD)** | `https://traviscad.org/wp-content/largefiles/2026%20Certified%20Appraisal%20Export%20Supp%200_07182026.zip` (557 MB). JSON special export: `.../2026%20Certified%20JSON%20SUPP%200%2007182026.zip` (3.55 GB). Latest supplement: `.../travis_SUPP%20335_2026_WEBSITE%20EXPORT_Renamed.zip` (511 MB). Layout: `.../Website_Legacy8.0.33-AppraisalExportLayout_06182026.zip`. Page: https://traviscad.org/publicinformation | PACS Appraisal Export 8.0.33 | Full PACS set | Free. The server returns 403 to requests without a browser User-Agent; with one it returns 200. Also posts EARS 2022–2026. |
| **Collin (CCAD)** | Texas Open Data Portal (Socrata): "Collin CAD Appraisal Data - 2026", id `5tkr-3759`, 502,526 rows: `https://data.texas.gov/resource/5tkr-3759.csv` (API; paging with `$limit`/`$offset`). Partial exemptions list: `c922-rc4c`. Entity codes: `kwi9-9pmz`. State category codes: `fre7-8m55`. Catalog: https://data.texas.gov/stories/s/mz7k-urqw | CSV / JSON via Socrata API | `currvalmarket`, `currvalappraised`, `currvalhscaploss`, `currvalnhscaploss`, `exempthmstdflag`, `exemptcodes`, `entitycodes`, `propcategorycode`, `imprvyearbuilt`. **No per-unit exemption amounts** in this table; those have to be rebuilt from the codes and the unit rules, or taken from the partial-exemption list. | Free and automation-friendly. The old Access export (`link.collincad.org/.../LiteDatabaseCurrent.zip`) is "retiring"; it returned a 7 KB stub when checked. Page: https://collincad.org/category/appraisal-data-exports/ |
| **Fort Bend (FBCAD)** | Certified export: `https://www.fbcad.org/wp-content/uploads/2026/08/2026_07_07_1746-Orion-2026-Certified-Export-Redacted.zip` (59 MB). Property data export: `.../2026/07/PropertyData-Post2026Cert-Redacted.zip` (163 MB). Supplements 1–3 (latest 2026-09-21: `.../2026/10/2026_09_16_0927-Orion-2026-Supplement-3-Export-Redacted-_Update3.zip`). Page: https://www.fbcad.org/certified-and-supplements-reports/ | "Orion" export (FBCAD moved off PACS; layout probably inside the ZIP, not opened) | Probably values, exemptions and entities; **check the layout before relying on per-unit amounts.** "Redacted" means confidential owners are removed. | Free. Also an ArcGIS Open Data Hub. |
| **Denton (DCAD)** | **Not verified.** dentoncad.com did not resolve from here (DNS failure; www.dentoncad.com loaded an empty "Public Portal" shell). Search shows a "Data Extracts" page (`https://dentoncad.com/?p=2815`) with CSV, standalone DBF and a weekly file geodatabase, plus schema and code files (cached for 2021–2024). | CSV / DBF / FGDB | Unknown for 2026 | Check by hand. If no 2026 certified file is posted, request one. |
| **El Paso (EPCAD)** | `https://export.epcad.org/datasets/2026_Certified_Export_Files.zip` (408 MB, modified 2026-10-13). Also `APPRAISAL_ROLL.zip` (122 MB). Layout: `https://export.epcad.org/datasets/Appraisal%20Export%20Layout%20-%208.0.34.zip`. 2025 certified: `.../2025_Certified_Export_Files.zip`. Page: https://epcad.org/OpenGovernment | PACS 8.0.34 | Full PACS set | Free. Also publishes certified entity totals with exemption amounts (PDF) for 2022–2026, useful for checking. |
| **Williamson (WCAD)** | Socrata portal https://data.wcad.org/. Key 2026 certified tables: `Asmt - Certified` `yeqp-u7bx` (1.93M rows = property × taxing unit: `mktvalue`, `assessed`, `hscapadj`, `taxable`); `Exemptions` `nbn7-h4pp`; `Property - Certified` `ai3c-c9pf`; `Improvement Real Property - Certified` `2huh-jk3y`; `Property Cama-Certified` `xrxg-afjm`. Example: `https://data.wcad.org/resource/yeqp-u7bx.csv` | CSV / JSON via Socrata | Per-unit market, assessed (capped), taxable; exemption types; property characteristics | Free and automation-friendly. Exemption amounts per unit are implied by assessed − taxable. Tyler/Socrata terms apply. |
| **Montgomery (MCAD)** | **Not verified.** https://mcad-tx.org/appraisal-data-exports is a JS app that did not render here. Search shows a 2025 certified roll ZIP back to 2019 and layouts (Legacy 8.0.33 PDF/XLSX, JSON layout). 2026 not confirmed. | PACS 8.0.33 | Full PACS set (if PACS export) | Check by hand. A county open-data copy carries "redistribution … prohibited without prior authorization", so check MCAD's terms. |
| **Hidalgo** | **No public bulk file found.** https://www.hidalgoad.org/ has only a sign-in portal. | n/a | n/a | **Needs a PIA request.** |
| **Brazoria** | 2026 certified roll data (Real, MH, Mineral): `https://u.pcloud.link/publink/show?code=kZYMUV7ZD6GgiyP3moR0gLKHGc1l5Qd0c9xV` (pCloud). Page: https://brazoriacad.org/public-gis-and-property-data-downloads/ | Database / TXT / CSV per page header | Unknown until opened | Free. pCloud share links are awkward to script; download by hand. |
| **Galveston** | `https://galvestoncad.org/wp-content/uploads/2026/08/2026-CERTIFIED-ROLL-WEB-EXPORT-W-EXPORT-LAYOUT.zip` (138 MB, layout included); 2017–2025 also posted. Page: https://galvestoncad.org/preliminary-and-certified-roll-export-data/ | Probably PACS (layout inside) | Probably the full set | Free. |
| **Bell** | `https://bellcad.org/wp-content/uploads/2019/06/2026-Bell-County-Certified-Export-3.zip` (161 MB, modified 2026-10-01). Condensed XLSX: `.../2026/09/BellCAD-Appraisal-Data-Condensed-2026-20260922.xlsx`. Layout 8.0.33: `.../2026/02/Appraisal-Export-Layout-8.0.33.xlsx`. Page: https://bellcad.org/data-portal/ | PACS | Full PACS set | Free. The page says files after 5/1/2026 follow a newer description that it doesn't link. Older years are 7z/RAR. |

Rules that apply to all of them:
- Tax Code s. 25.027 makes some owner information confidential, so files are "redacted" and TAD drops over-65
  exemptions from one file. The PACS entity file still carries `ov65_amt` and freeze ceilings.
- None of these sites states terms that forbid scripted download; most say only "no technical support".
- Commercial fallback: TaxNetUSA sells bulk data for every county (paid, quote on request).

## 2. Texas Comptroller statewide data

| Source | URL / pattern | Gives | Format, years | Notes |
|---|---|---|---|---|
| **School District Property Value Study (PVS)**, report index | `https://comptroller.texas.gov/taxes/property-tax/pvs/{YYYY}{p\|f}/index.php` (2016–2025 listed) | Per-ISD local vs. PVS value by category (A–S), deductions, T1–T13+ | HTML | **2025F** exists (certified Aug 2026). **2025P** exists. **2026P/2026F do not exist yet**: `auto-data/PT2/PVS/2026P/ALL0000001Y.php` returns 404. 2026P normally comes out about January 31, 2027 and 2026F about August 2027. |
| PVS pages | Statewide: `https://comptroller.texas.gov/auto-data/PT2/PVS/{YYYY}{P\|F}/ALL0000001Y.php`. County list: `.../{YYYY}F/{CCC}index.php` (CCC = county number 001–254, e.g. 101 = Harris). District pages: `.../{YYYY}F/{CCC}{CCCDDD}1{X}.php`, where X = `D` summary worksheet, `L` deduction detail, `F` confidence interval, `G` stratified ratio (e.g. `1011019021D.php` = Aldine ISD). | Same as above, per district and split | HTML | Scrape by hand or with a polite script; no robots restriction noted. |
| **PVS bulk XLSX** (best for the model) | `https://comptroller.texas.gov/taxes/property-tax/docs/{YYYY}-{final\|preliminary}-isd-worksheet-export-detail.xlsx` (2025F 1.7 MB, 2024F 1.5 MB, 2025P 1.6 MB). Also `-isd-worksheet-export-summary.xlsx`, `-isd-self-report-export-detail.xlsx` (3.4 MB), `-isd-self-report-export-summary.xlsx`, `-confidence-interval-detail-export.xlsx`, `-isd-top-ten-taxpayer.xlsx` | One row per CAD × ISD split, 157 columns: local / PVS / assigned value by category; homestead, over-65, disabled vet, freeport, cap loss, s. 23.231 cap, freeze; loss from each homestead step (`LOSS INCR HMSTD`, `LOSS PREV INCR HMSTD`, `LOSS SCND INCR HMSTD`, `LOSS LOCL HMSTD`); assigned T1–T18 | XLSX, direct download | Used above for homestead counts. Release template: `.../docs/school-district-pvs-data-release.xlsx`. |
| **Tax Rates and Levies** | https://comptroller.texas.gov/taxes/property-tax/rates/. Files: `https://comptroller.texas.gov/taxes/property-tax/docs/{YYYY}-{school-district\|city\|county\|special-district\|total}-rates-levies.xlsx` | Every taxing unit: market value, taxable value (M&O and I&S), no-new-revenue rate, voter-approval rate, M&O, I&S, total rate, levy | XLSX; **latest 2025** (school file 335 KB, special 574 KB, total 199 KB). 2021–2024 archived. | **2026 is not published** (404); it is expected about early 2027. This also serves as the county/city/special-district taxable values source: the files include market and taxable value per unit. |
| 2026 adopted rates, before the Comptroller publishes | Each county's truth-in-taxation website (Tax Code s. 26.17), e.g. `https://dallas.countytaxrates.com/` (200). Appraisal district rate charts, e.g. BCAD `https://bcad.org/wp-content/uploads/2026/09/BCAD-Tax-Rate-Chart.pdf`, DCAD https://www.dallascad.org/TaxRates.aspx | 2026 adopted rates by unit | HTML / PDF, district by district | Only good for the covered districts. Elsewhere, use 2025 rates and flag them (per TX_DECISIONS). School 2026 M&O/I&S rates are also in TEA's SOF data (section 3). |
| MAP reviews, ratio studies | `https://comptroller.texas.gov/taxes/property-tax/map/{YYYY}/{county}-{YYYY}.pdf`; ratio study `.../auto-data/PT2/ratio-study/{YYYY}/...` | CAD quality | PDF / HTML | Context only. |

## 3. Forecasts and school-funding inputs

| Source | URL | Gives | Format | Notes |
|---|---|---|---|---|
| **GAA 2026-27 value growth assumptions** (enacted) | TEA letter of 2025-07-15: https://tea.texas.gov/about-tea/state-funding/excess-local-revenue/annual-review-of-local-revenue-25-26.pdf ("2024 state certified property values increased by 5.60%, in accordance with the 2026-2027 General Appropriations Act"). TEA TY2026 MCR letter: https://tea.texas.gov/taa-letters/tax-year-2026-maximum-compressed-tax-rates ("set by the General Appropriations Act at 3.60 percent for TY 2026"). GAA: https://capitol.texas.gov/tlodocs/89R/billtext/pdf/SB00001F.pdf | **TY2025 +5.60%, TY2026 +3.60%** statewide district property value growth | PDF | Earlier, the House introduced version (LBB, Feb 2025) assumed 5.50% (FY2026) and 4.94% (FY2027): https://lbb.texas.gov/Documents/HAC_Summary_Recs/89R/8963_HAC_FSP_Property_Tax_Overview.pdf. |
| **LBB FSP overview, Sept 2026** | https://lbb.texas.gov/Documents/Publications/Presentation/9497_WAM_FSP_Overview.pdf (468 KB) | DPV growth history 2017–2026 (2025 estimated; 2026 at the assumed 3.6%), cost of compression, tax relief costs | PDF | No years beyond 2027. LBB/TEA do not publish 2028+ value forecasts until the January 2027 LAR/BRE cycle. |
| **TEA MCRs, TY2026** | Final MCRs (TAA 2026-08-27): https://tea.texas.gov/sites/default/files/taa-letters/taa-2026-08-27-final-maximum-compressed-tax-rates-and-adoption-of-tax-rate-for-tax-year-2026.pdf. State MCR **$0.6254** = 0.6322 × 1.025/1.036. Floor $0.5628. Template: https://tea.texas.gov/about-tea/state-funding/2026-27-tax-rate-and-mcr-template-finalv2.xlsx (471 KB). History: `.../mcr-for-tax-years-2018-2024-2.xlsx` | MCR rules and per-district values | PDF / XLSX | District MCR list is on https://tea.texas.gov/finance-and-grants/state-funding under "District & Charter Planning Tools". |
| **TEA Summary of Finances (SOF) data** | https://tea.texas.gov/about-tea/state-funding/fy2026-2027-sof-data.xlsx (7.1 MB, 2026-10-13); `fy2025-2026-sof-data.xlsx` (7.3 MB); `fy-2024-2025-sof-run-id-46820-final-data_0.xlsx` | Full formula inputs and outputs per district: LPE and DPE runs, DPV T1–T22, MCR, M&O and I&S rates, Tier 1/2 yields, ASAHE (state aid for homestead exemptions) at $140k/$60k vs $100k/$10k, recapture | XLSX (sheets `inputs_lpe`, `outputs_lpe`, `mo_asahe_*`, `is_asahe_*`) | **The key source for the school-finance module.** LPE = legislative payment estimate (uses the GAA growth figure); DPE = district planning estimate. |
| TEA certified property values (CPTD) and adopted rates | https://tea.texas.gov/about-tea/state-funding/additional-finance-resources/school-district-property-values-and-tax-rates. Files: `cptd-2025-final-data.xlsx` (86 KB: T1, T2, T8, T3, T4, value assigned); `school-district-adopted-tax-rates-1.xlsx` (2005-06 to 2024-25 M&O/I&S) | District values used for funding; rate history | XLSX | Rates stop at 2024-25; 2025-26/2026-27 rates are in the SOF files. |
| TEA funding data timeline | https://tea.texas.gov/finance-and-grants/state-funding/foundation-school-program/fsp-hot-topics/state-funding-data-elements-sources-and-timelines-feb2026.pdf | Which value is used when (LPE vs PVS) | PDF | Background. |
| **Comptroller BRE 2026-27** (Jan 2025) | https://comptroller.texas.gov/transparency/reports/biennial-revenue-estimate/2026-27/docs/bre-2026-27.pdf (5.4 MB). Data: `.../docs/bre-2026-27.xlsx` (844 KB) | Table 1: real and nominal GSP, **personal income**, **resident population**, FY2021–2027 | XLSX | The next BRE (2028-29) is due about January 2027. |
| **Comptroller CRE 2026-27** (fall 2025) | https://comptroller.texas.gov/transparency/reports/certification-revenue-estimate/2026-27/docs/cre2026-27.pdf. Data: `.../docs/cre-2026-27-data.xlsx` (16 MB) | Table 4: GSP, personal income, population to FY2027 | XLSX | Newer than the BRE. Neither forecasts property values or home prices. |
| **FHFA HPI** | State quarterly `https://www.fhfa.gov/hpi/download/quarterly_datasets/hpi_at_state.csv` (188 KB). Metro: `.../hpi_at_metro.csv` (4.2 MB). County annual: `https://www.fhfa.gov/hpi/download/annual/hpi_at_county.xlsx` (5.3 MB). Master: `https://www.fhfa.gov/hpi/download/monthly/hpi_master.csv` (17 MB). Index: https://www.fhfa.gov/data/hpi/datasets | Texas and metro home price history | CSV / XLSX | Free, scriptable. History only, no forecast. |
| **Texas A&M Real Estate Research Center** | https://trerc.tamu.edu/data/ (redirects, 200). Housing activity: https://www.recenter.tamu.edu/data/housing-activity/ | Monthly sales, median price, inventory by state / metro / county (from Texas REALTORS MLS) | Interactive, with CSV export | Interactive page, so download by hand. Check terms before republishing. |
| **Texas Demographic Center projections** | Vintage 2024 (current): https://demographics.texas.gov/Projections/2024 and `/Projections/2024/Download`. Vintage 2022: `/Projections/2022` | State and county population by age, sex and race/ethnicity, 2020–2060, low/mid/high migration | ZIP per scenario (JS download links) | **No household projections.** Use ACS headship rates times the TDC population. |
| Income history | BEA state personal income `https://apps.bea.gov/regional/zip/SAINC.zip` (17.6 MB) | Texas personal income history | CSV in ZIP | Pair with the BRE/CRE forecast, then a long-run trend. |

## 4. Census microdata and geography

| Source | URL | Gives | Format | Notes |
|---|---|---|---|---|
| **ACS PUMS 2024 1-year, Texas** | Households: `https://www2.census.gov/programs-surveys/acs/data/pums/2024/1-Year/csv_htx.zip` (20.9 MB). Persons: `.../csv_ptx.zip` (52.1 MB). Dictionary: `https://www2.census.gov/programs-surveys/acs/tech_docs/pums/data_dict/PUMS_Data_Dictionary_2024.pdf` | Households, owner value (VALP), taxes (TAXAMT), income | CSV | Free. **2025 1-year is not posted yet** (404 on the `/pums/2025/1-Year/` directory); recheck before building. |
| **Tract → 2020 PUMA** | `https://www2.census.gov/geo/docs/maps-data/data/rel2020/2020_Census_Tract_to_2020_PUMA.txt` (1.7 MB). County names: `https://www2.census.gov/geo/docs/reference/codes2020/cou/st48_tx_cou2020.txt` | PUMA → county or county group | TXT | Same files as Florida (`ptm/geo.py` `TRACT_TO_PUMA_URL`). |
| **Block → school district (Census BAF)** | `https://www2.census.gov/geo/docs/maps-data/data/baf2020/BlockAssign_ST48_TX.zip` (15.1 MB) | Each 2020 block's unified school district (plus county, place, etc.) | Pipe-delimited TXT in ZIP | Block → tract → PUMA gives PUMA × ISD overlap shares (weight by block population or housing units from the 2020 P.L. file). |
| **NCES EDGE Geographic Relationship Files** | `https://nces.ed.gov/programs/edge/data/GRF24.zip` (59 MB); GRF23 (55 MB). Page: https://nces.ed.gov/programs/edge/Geographic/RelationshipFiles | School district ↔ county, place, tract, etc., with LEAID | XLSX/TXT in ZIP | LEAID ↔ TEA CDN (6-digit, e.g. 101902) crosswalk is in NCES CCD. |
| **School district boundaries** | TIGER UNSD: `https://www2.census.gov/geo/tiger/TIGER2025/UNSD/tl_2025_48_unsd.zip` (16.9 MB; 2024 also). TEA open data: https://schoolsdata2-93b5c-tea-texas.opendata.arcgis.com/ | Polygons | Shapefile | Districts also publish their own ISD layers (WCAD `7bnq-gqjq`, TAD Schools, Brazoria). |
| Geocorr 2022 | https://mcdc.missouri.edu/applications/geocorr2022.html | PUMA ↔ county / ISD / place allocation factors | Web form → CSV | Quick alternative to the BAF route; interactive. |

**Mapping note.** Comptroller ISD IDs (`101-902`) are TEA CDNs (`101902`); the first three digits are the
county number (alphabetical, 001–254, not FIPS). County FIPS = 2 × county number − 1 (checked: Harris
101 → 201, Dallas 057 → 113, Anderson 001 → 001).

## Recommended download order

1. Comptroller PVS exports: 2025F, 2024F and 2025P `isd-worksheet-export-detail` and `-summary`, plus
   `isd-self-report-export-detail` (all < 4 MB). These are statewide control totals and homestead counts.
2. Comptroller 2025 rates and levies, all five XLSX files (< 1 MB).
3. TEA: `fy2026-2027-sof-data.xlsx`, `fy2025-2026-sof-data.xlsx`, `cptd-2025-final-data.xlsx`,
   the MCR template, and the TY2026 MCR letters.
4. ACS PUMS 2024 TX (h + p), tract → PUMA, county codes, BAF ST48, TIGER UNSD 2025.
5. FHFA state, metro and county HPI; BRE and CRE xlsx; BEA SAINC; TDC Vintage 2024 (by hand).
6. Roll files, largest first, all free and scriptable: HCAD (`/data/CAMA/2026/`: Real_acct_owner,
   Real_jur_exempt, Real_building_land, Code_description_real; about 560 MB); TAD TP extract (741 MB);
   DCAD certified CSV (193 MB); TCAD certified export (557 MB, with browser UA); Collin and Williamson
   through the Socrata API; FBCAD certified export and property data (220 MB); EPCAD certified export
   files (408 MB); Galveston (138 MB); Bell (161 MB). The total is about 3.5 GB compressed. Keep these under `data/`,
   outside git.
7. By hand: Brazoria (pCloud), Montgomery and Denton (pages need a normal browser), LBB/TEA PDFs as
   references.

## Blockers that need a person

- **Bexar (6.7% of homesteads), the biggest gap.** There is no public bulk export. Send a Public Information Act request to
  OpenRecords@bcad.org (form: https://bcad.org/wp-content/uploads/2026/04/BCAD-Public-Information-Act-Request.pdf)
  for the 2026 certified appraisal data export (PACS layout, including the property-entity file),
  delivered through their FTP. There may be a cost estimate to approve.
- **Hidalgo (2.3%).** No public download found. A PIA request is needed (no form or fee schedule found online).
- **Denton (3.4%) and Montgomery (2.6%).** The sites could not be reached or rendered from here. Someone needs
  to open https://dentoncad.com (Data Extracts) and https://mcad-tx.org/appraisal-data-exports in a normal
  browser, confirm a 2026 certified file exists, and copy the direct URLs. Montgomery's terms may restrict redistribution.
- **Brazoria.** Files sit behind pCloud share links; download by hand.
- **Optional, possibly a statewide shortcut.** A PIA request to the Comptroller (Property Tax Assistance Division) for
  all districts' 2026 EARS submissions (manual 96-1051). It is unconfirmed whether the Comptroller
  releases these. If it does, it would replace most district-by-district work and fill the Bexar/Hidalgo gap.
- **Data that doesn't exist yet.** 2026 statewide adopted rates (Comptroller, about early 2027), 2026 PVS (2026P
  about January 2027), ACS 2025 PUMS (recheck), and LBB/TEA value assumptions beyond FY2027 (next LAR/BRE,
  January 2027). Until then, use 2025 rates and the GAA's 3.60% for TY2026, and flag both.
- **Census API key.** Only needed for published ACS tables (see CHALLENGES.md); PUMS and relationship
  files don't need one.
