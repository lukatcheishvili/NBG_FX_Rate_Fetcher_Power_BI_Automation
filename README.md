# NBG FX Rate Fetcher: Power BI Automation

A Power BI report that loads the official exchange rates of the National Bank of Georgia (NBG) directly from the bank's public files and presents them as a dashboard: daily rates, period-over-period changes against the lari, a daily table and monthly averages. It replaces the manual routine of looking up rates on the NBG website when preparing financial statement working files.

## Why

Closing rates, average rates and transaction-date rates are needed every reporting period, for several currencies. Looking them up one by one on the NBG website is slow and easy to get wrong. This report pulls the full history (2001 to today) on refresh and makes any rate, change or monthly average available in a few clicks.

## Report

The report has three pages, each available in a dark and a light version and in Georgian and English.

| Page | Contents |
|---|---|
| Official rates (overview) | Rate cards for USD, EUR, GBP and RUB with the daily change; the selected currency against its base-date rate; percentage change of several currencies against GEL; latest official rates for every listed currency |
| Daily table | Rates for every day in the selected period, with weekend rows dimmed (weekends carry Friday's rate) |
| Monthly table | End-of-month, average, minimum and maximum rate per month; the current, unfinished month is excluded |

Navigation and controls:

- The tabs in the top bar switch between pages.
- The sun / moon button switches between dark and light mode. Date and period selections are kept.
- The EN / ქა button switches between English and Georgian. Date and period selections are kept; the currency selections return to the defaults.
- The reset button restores the default filters; the info button opens a short description of the page, closed with ✕.
- The period buttons (1M, 3M, 6M, 1Y, 5Y, ALL, YTD) set the base date used by the charts. Defaults: 1Y, USD, and USD / EUR / GBP / TRY for comparison.

Labels follow NBG's own report: Georgian, with English translations on the English pages.

## Data sources

Both files are read directly from nbg.gov.ge on every refresh:

| File | Coverage |
|---|---|
| `official-daily-exchange-ratesgeo.xlsx` | Current year, daily |
| `exratesyearsgeo.xlsx` (sheet `2001-...`) | 2001 to the end of last year, daily |
| `eng/official-daily-exchange-rateseng.xlsx`, `eng/exratesyearseng.xlsx` | English currency names only (same layout) |

The currency list, quotation units (for example AMD per 1,000) and Georgian currency names are taken from the files' header rows, so new or discontinued currencies do not break the refresh. Where both files cover the same date, the current-year file is used. Rates are as published by NBG; for audit purposes, verify critical figures against [nbg.gov.ge](https://nbg.gov.ge/en/monetary-policy/currency).

## Repository structure

```
Personal Portfolio - NBG Rates.pbix              Single-file copy of the report (open in Power BI Desktop)
report/
  Personal Portfolio - NBG Rates.pbip            Open this file in Power BI Desktop
  Personal Portfolio - NBG Rates.Report/         Pages, visuals, bookmarks and theme (PBIR)
  Personal Portfolio - NBG Rates.SemanticModel/  Tables, Power Query and DAX measures (TMDL)
tools/
  make_light_pages.py    Generates the light-mode and English pages from the dark Georgian ones
  check_layout.py        Layout checks: bounds, overlaps, alignment, text fit, contrast
  validate_report.py     Structural checks of the report definition
tests/
  visual_tests.dax       Data tests for each visual, with expected values
docs/
  decisions.md           Design and modelling decisions, conventions and change log
  design/                Design-system references used for the dark and light themes
reference/
  nbg-report-definition/ NBG's public report definition used as the starting template
  screenshots/           Screenshots of NBG's report used for comparison
  nbg-daily-rates-sample.xlsx  Sample of the NBG daily rates file used to test the import
```

The report is saved as a Power BI Project (PBIP), so every page, visual and measure is a plain text file that can be reviewed and versioned in git.

## Getting started

Requirements: Power BI Desktop (recent version) with internet access to nbg.gov.ge. Python 3.10+ is only needed for the maintenance scripts.

1. Clone the repository. For a quick look you can instead open the single-file copy `Personal Portfolio - NBG Rates.pbix` in the repository root.
2. Open `report/Personal Portfolio - NBG Rates.pbip` in Power BI Desktop.
3. Select Refresh. The first refresh downloads the full rate history and can take a minute or two.
4. If prompted for data source credentials for nbg.gov.ge, choose Anonymous; set the privacy level to Public.

## Maintaining the report

The dark Georgian pages are the source of truth. The light and English pages are generated from them and should not be edited by hand.

After changing the report, close Power BI Desktop and run:

```
python tools/make_light_pages.py   # regenerate the light and English pages
python tools/check_layout.py       # must report PASS
python tools/validate_report.py    # must report no problems
```

Then reopen the project in Power BI Desktop, refresh, and run the queries in `tests/visual_tests.dax` from the DAX query view. Each query reproduces what one visual displays under the default filters and lists the expected values.

Power BI Desktop must be closed while files under `report/` are edited outside of Desktop; otherwise Desktop may overwrite the changes when it saves.

## Notes

- This is a personal productivity project. It is not an official tool of the National Bank of Georgia or of JSC Bank of Georgia, and it is not affiliated with either.
- The report layout is based on NBG's public "Official Exchange Rates" report; NBG's logo and branding are not used.
- NBG official rates may differ from interbank or market rates.
