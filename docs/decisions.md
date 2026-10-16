# Decisions & rules

This file has two parts:

1. **Rules & patterns**: how the project works and the conventions every change must follow. Update a rule when a decision changes it.
2. **Log**: what was done and decided, newest first. Add an entry for every working session or significant change.

---

## 1. Rules & patterns

### Data sources
- Rates come from two public NBG Excel files, read directly from nbg.gov.ge on refresh:
  - `official-daily-exchange-ratesgeo.xlsx`, sheet `G`: the current year.
  - `exratesyearsgeo.xlsx`, the sheet whose name starts with `2001-`: 2001 to the end of last year. Matched by prefix, so the yearly rename (`2001-2025` → `2001-2026`) doesn't break it.
- Both sheets share one layout. The row containing `USD` holds the ISO codes, the row above it the units (K), and the row above that the Georgian names. Dates start on the next row. The shared function `fnNbgParseSheet` parses either sheet and returns `Rates` and `Currencies`.
- Never hard-code currency columns. Currencies come and go (BGN was dropped on 2026-01-01).
- Where both files cover the same date, the live file wins.
- English currency names come from NBG's English twins of the two files (`exchange_rates/eng/official-daily-exchange-rateseng.xlsx`, sheet `E`, and `exratesyearseng.xlsx`, sheet `2001-`). They have the same layout, so `fnNbgParseSheet` parses them too (`NBG_Live_Sheet_En`, `NBG_History_Sheet_En`). They are used for names only, never for rates.
- `Rate` is per K units (e.g. AMD per 1,000). `Normalized_Rate` is per 1 unit. The units always come from the source files.

### Model (TMDL)
- `Mapping` is built from the two files' header rows (code, units, Georgian name). The live file's values win for current currencies, and the history file supplies retired codes (DEM, ROL, BYR, …).
- English: `Mapping[Currency_Long_En]` (sorted by `Name_Sort_Order_En`) and `Currency_Desc_En` ("USD US Dollar"). Names are looked up by code; a code missing from the English files falls back to the code itself. Codes that share a Georgian name (BYR/BYN, TMM/TMT) share the English name of the code NBG still publishes. Test T9 checks that no listed currency fell back.
- `Mapping[Is_Listed]` = 1 when a currency was quoted in the last 24 months. Every page filters on it, which matches NBG's currency lists.
- Sort order: USD, EUR and GBP first, then the rest by code. **Sort columns are built in Power Query, not DAX.** Sorting a column by a DAX column derived from it is a circular dependency.
- New measures go in `Metrics` with `displayFolder: NBG Report`. Never change the old measures.
- Every Georgian text measure has an English twin named `<measure>_En`: `Base_Date_En`, `Title_Ex_Rate_En`, `Compare_Caption_En`, `Title_Cur_to_Gel_En`. When a Georgian one changes, change its twin too.
- Period window: `Window_End` is the latest rate date within the date slicer. `Window_Start` is `Window_End` minus 1M/3M/6M/1Y/5Y, or Jan 1 for YTD, never earlier than the slicer start.
- `Rate_Diff` compares with the previous **weekday**. Weekend and Monday dates carry Friday's rate, so 12/10/2026 compares with 09/10/2026. Public holidays aren't excluded.
- Monthly average = the mean over **all calendar days** in the month. This matches NBG (September 2026 USD: 2.6114).
- `Advanced_Calendar` is the marked date table, covering 2001 onwards. Auto date/time is off.

### Editing the PBIP files
- Keep Power BI Desktop **closed** while editing the files under `report/*.SemanticModel` or `report/*.Report`. Reopen the `.pbip` afterwards to validate.
- Write files as UTF-8 **without a byte-order mark**, so the Georgian text survives.
- Never put DAX or M inside Python f-strings: `{ … }` is evaluated as Python.
- Back up untracked folders before scripted edits, because git can't restore them.
- Keep NBG's page and visual IDs (the hex names). Bookmarks and visual interactions refer to them.
- After any report remap, validate: every JSON file parses; no `RateDD`, `CL_Cur`, `Calendar`, `Country_Flags` or `_Measures` references remain; every bookmark, group and interaction target exists.

### Report structure
- Three pages, with Georgian labels (and an English twin of each, see "Twin pages"): **ოფიციალური კურსები** (overview), **ყოველდღიური ცხრილი** (daily table) and **საშუალოთვიური ცხრილი** (monthly table).
- No NBG branding: no logo, background image, contact panel, address or phone.
- Slicer defaults: Frequency = 1Y. Currency = USD. Comparison = USD, EUR, GBP and TRY.
- Slicer isolation (NBG's `visualInteractions`): the currency dropdown filters only the area chart, the comparison list filters only the line chart, and the latest-rates table follows only the date slicer.
- KPI cards on the overview always show **USD, EUR, GBP and RUB**, each through a visual-level filter. They ignore every slicer except the date slicer (`NoFilter` interactions).
- Navigation: three page buttons in the top nav (`PageNavigation`). Pages 2 and 3 stay hidden from the page list. The reset button applies the page's `Home_Page_x` bookmark.
- Info button: opens a pop-up panel (card colour, 1px hairline, 8px corners) with NBG's help text, bold labels, bullets and an italic footer; its ✕ closes it. The panel is a text box plus a close button, both `isHidden`, toggled by the `Info_Open_Page_x` / `Info_Close_Page_x` bookmarks (display only, `suppressData`, so no slicer is touched). It sits at x 880, y 68, 376 wide, ends on the 24px right margin and grows with its text. It has z 4000 (close button 4001), above every page visual (they stop at z 3012), but Desktop still drew tables and slicers over it. Its height uses a 1.6 line-height estimate, because 1.4 made the text box scroll. Its last line names the creator (`CREATOR` in the script). The English texts are the ones NBG shows on its English report.
- A visual that has a line (`outline`) colour needs `selector: {id: default}` on the colour and weight properties. Without it Desktop falls back to the theme's first data colour, blue.
- Theme: `StaticResources/RegisteredResources/NBG_Ferrari.json`, registered as the custom theme on top of the `CY24SU10` base theme. Every visual also carries explicit formatting in the design-system colours.

### Design system (Ferrari-inspired, see `docs/design/ferrari.md`)
Workflow: **design in Figma first, get approval, then build in Power BI.**

| Token | Value | Use |
|---|---|---|
| canvas | `#181818` | Page background (never pure black) |
| card | `#222222` | Visual/card background (a dashboard step between canvas and elevated) |
| elevated | `#303030` | Inputs, hover, hairline borders |
| ink | `#ffffff` | Titles, key numbers |
| body | `#969696` | Secondary text, axis labels |
| muted | `#666666` | Captions, disabled |
| accent (Rosso Corsa) | `#da291c` | **Scarce**: active tab underline, selected period, base-date line only |
| rate up | `#f13a2c` + ▲ | Rate rose against GEL (as NBG does) |
| rate down | `#03904a` + ▼ | Rate fell against GEL |

- **Type:** Segoe UI everywhere. It's built into Windows and Power BI and renders Georgian. Titles are 500 weight (semibold), never heavy. Section labels are 11px uppercase with tracking. Numbers in tables use tabular figures.
- **Corners:** 8px on cards and slicers, 4px on buttons and chips.
- **Spacing:** an 8px ladder (4 / 8 / 16 / 24 / 32). There's a 16px gutter between cards and 16px padding inside them.
- **Elevation:** brightness steps and 1px hairlines only. No drop shadows.
- **Canvas:** 1280 × 720.
- **Layout:** a 56px top navigation bar (title left, 3 page tabs right, active tab underlined in red), then one filter bar above the content, then content cards. No left rail.
  - Filter bar: y 68, height 64 (label and input of a slicer need about 60px; at 52 the input poked out of the card border).
  - Filter bar slicers (overview): period x 24 (228 wide), currency 268 (200), frequency 484 (360), compare 860 (206). The frequency slicer needs 360 so all seven chips (1M … YTD) fit; at 330 the YTD chip was cut to "Y…". On the daily page the frequency slicer is at x 268, 360 wide.
  - KPI row: y 144, height 96, 4 × 296 wide.
  - Overview: charts 840 wide at y 256 and y 494; latest-rates panel at x 880, 376 wide.
  - Daily: table 840 × 560 plus the side panel.
  - Monthly: table full width, 1232 × 560.
- **Nav row:** tabs at x 552 / 728 / 904 (widths 168 / 168 / 184, ending at 1088, 16px before the first icon). The underline of the active tab starts 14px inside its tab.
- **Nav icon buttons** (language EN/ქა, ☀/🌛 mode toggle, reset ↺, info ⓘ): all 32×32 at y 12, x 1104 / 1144 / 1184 / 1224 (8px gaps, 24px right margin), and all with the same container settings (no background, padding 0/0/2/2, no border, 4px corners). Text-based icons also get zero text margins so they centre like the built-in icons.
- **Font sizes** (Power BI points): titles 11 semibold, labels 7.5–8, values 9, KPI numbers 21.
- **Up/down:** always shown as an arrow plus a sign, never by colour alone.

### Twin pages (generated: light and English)
- Each dark Georgian page has three **twins**, hidden in the page list: light-ka, dark-en and light-en (12 pages in all). ☀ / 🌛 switches mode and keeps the language; **EN / ქა** switches language and keeps the mode.
- Slicer pairs share a `syncGroup` (`sync_<dark slicer name>`), so date and period selections carry over between all four variants. The **currency** slicers on the English pages filter a different column (`Currency_Desc_En`), so they sit in their own group (`…_en`): switching language resets the currency picks to the defaults (USD; USD/EUR/GBP/TRY).
- **The dark Georgian pages are the source of truth.** Never edit a twin by hand. After changing a dark page, close Desktop and run `python tools/make_light_pages.py`. It is idempotent: IDs are hashes of the dark IDs (`light:`, `en:` and `light-en:` prefixes), and each `Home_Page_x` reset bookmark is cloned as `_Light`, `_En` and `_Light_En`.
- The English transform (`to_english` in the script) translates every static string through `TEXT_EN` and `CURRENCY_EN`, and renames the model fields that have an `_En` twin. The script fails if any Georgian text is left on an English page (apart from the ქა label), so a new Georgian string needs a `TEXT_EN` entry.
- Light-ka pages: `df5bbb2d…` (overview), `a759698f…` (daily), `6fcadc18…` (monthly).
- The light palette ("Stone", v4) is a calm, low-glare neutral grey: no pure white or black, depth from soft brightness steps and hairlines. History: plain white and an Airbnb-based palette were too bright; v3 was a warm off-white (`#FAF9F7` cards on `#EFEEEA`) approved from a Figma mock, but still read as too bright in Desktop. v4 was chosen on 2026-10-16 from a side-by-side mock of three calmer options (Sand, Stone, Taupe). Text contrast is checked on the card colour `#EBECEA`.

| Dark | Light | Role |
|---|---|---|
| `#181818` | `#E1E2E0` | canvas (soft stone grey) |
| `#222222` | `#EBECEA` | card (light stone), with a `#CFD1CE` hairline border |
| `#303030` | `#D9DBD8` | elevated surfaces (inputs, button fills), table grid lines |
| `#FFFFFF` | `#20221F` | ink (13.5:1) |
| `#969696` | `#50544F` | body (6.5:1) |
| `#666666` | `#737772` | muted (3.8:1) |
| `#2C2C2A` | `#D6D8D5` | chart grid |
| `#F0EFEC` | `#20221F` | area line |
| `#DA291C` | `#DA291C` | accent, unchanged in both modes (4.1:1, used for the underline and the base-date line, not for text) |
| `#FF5A4F` | `#B42318` | rate up (5.5:1) |
| `#22B066` | `#0E7A43` | rate down (4.6:1) |
| `#3987E5` `#D95926` `#199E70` `#C98500` `#D55181` | `#2A78D6` `#EB6834` `#1BAF7A` `#EDA100` `#E87BA4` | series (colours below 3:1 are relieved by direct series labels) |

- Weekend dimming in light mode uses `Weekend_Font_Color_Light` (`#737772` on weekends, `#20221F` otherwise).
- Chart tooltips keep NBG's dark `#333333` style in both modes.
- The mapping lives in `PALETTE` in `tools/make_light_pages.py`; `soften()` adds the hairline card borders (corners stay 8px, as in dark mode).

### Charts
- Categorical colours, in a fixed order validated for dark mode on `#222222` (all six checks pass; worst adjacent colour-blind ΔE 8.4): `#3987e5` blue, `#d95926` orange, `#199e70` aqua, `#c98500` yellow, `#d55181` magenta, `#008300` green, `#9085e9` violet, `#e66767` red.
- Colours follow the currency, never its rank: **USD blue, EUR orange, GBP aqua, TRY yellow**. Other currencies take the next slots.
- The single-series area chart uses ink-white with a subtle grey fill. The base-date reference line is dashed Rosso Corsa.
- One y-axis per chart. Lines are 2px. Gridlines are hairline `#2c2c2a`. Show a legend whenever there are 2 or more series, plus direct labels when there are 4 or fewer.
- Text uses text colours, never the series colour.

### Quality checks (run before every hand-off; Desktop closed for the first two)
- `python tools/check_layout.py` runs static checks on all 12 pages. It must PASS:
  - every visual is inside the 1280×720 canvas and none is hidden, apart from the info pop-up (which must fit its text and be readable)
  - every twin page has exactly the dark page's visual positions
  - no overlaps, except content placed inside a background shape that sits below it
  - 24px margins and 16px gutters, an aligned filter bar, equal KPI tiles and nav icons
  - text fits its box (Georgian width estimate)
  - contrast is at least 4.5:1 (at least 3:1 for text of 8pt or smaller)
- `python tools/validate_report.py` checks that files parse, no stale references remain, and every bookmark, group and interaction target exists.
- `tests/visual_tests.dax` (T1–T8) runs against the loaded model in Desktop's DAX query view. Each query reproduces one visual's query with the default slicers and lists the expected NBG values.

---

## 2. Log

### 2026-10-16

**Language button, info pop-up and light-mode KPI border**
- New **EN / ქა** button in the nav row, at x 1104. Tabs and their underline moved 40px left (now 552 / 728 / 904), so the four icons and the three tabs sit on one grid. It jumps to an English twin of the page (or back); mode and the date and period selections carry over.
- Model: `NBG_Live_Sheet_En` and `NBG_History_Sheet_En` read NBG's English files; `Mapping` gets `Currency_Long_En`, `Name_Sort_Order_En` and `Currency_Desc_En`; `Metrics` gets `Base_Date_En`, `Title_Ex_Rate_En`, `Compare_Caption_En` and `Title_Cur_to_Gel_En`. Test T9 added. The TMDL loads (7 tables, 44 measures); the M still has to be refreshed in Desktop.
- `tools/make_light_pages.py` now builds three twins per page (light-ka, dark-en, light-en): 12 pages and 36 bookmarks. It is idempotent, and it fails on any Georgian text left on an English page.
- Decision: currency slicers are not synced across languages, because their field differs. Switching language resets the currency picks. The alternative (show only the ISO code in the slicers) was offered and not chosen.
- Info button: now a pop-up panel with formatted text (bold, bullets, italic) instead of a plain tooltip; Georgian text from NBG's own info box, English text from NBG's English report.
- **Fix:** the light-mode KPI tiles showed a blue border. The outline colour was saved without `selector: {id: default}`, so Desktop used the theme's first data colour. It now uses the grey hairline `#E2DFD9` like the other light cards (`soften()` in the script).
- **Filter bar 52 → 64px.** A slicer's label plus its input needs about 60px, so at 52 the date input poked out of the card border. Content now starts at y 144 (the 12px gap is kept), the bottom row and the tables are 12px shorter so the bottom margin stays, and slicer padding is 2px top and bottom. Moving the cards alone couldn't fix it, because the overflow was inside the cards.
- Dark-mode icon: the thin ☾ is now 🌛 (U+1F31B + U+FE0E, a solid moon with a face), chosen from a side-by-side comparison of eight candidates (it replaced an interim 🌑 disc). U+FE0E makes Power BI use the plain grey glyph from Segoe UI Symbol instead of the coloured emoji. If Desktop still shows it coloured, fall back to a custom filled-crescent image.
- **Fix:** the info panel opened *under* the slicers and the latest-rates table, so part of its text was hidden. It now has z 4000, above everything, and a creator line ("Created by: Luka Tcheishvili" / "შემქმნელი: ლუკა ჭეიშვილი") closes each text.
- **Light palette v4 "Stone".** The v3 cards (`#FAF9F7`) still read as too bright. Three calmer palettes were mocked side by side and Stone was chosen: page `#E1E2E0`, cards `#EBECEA`, inputs `#D9DBD8`, hairline `#CFD1CE`, ink `#20221F`. Dark mode is unchanged. Contrast checks pass on all 12 pages.
- **Fix:** the colour of the change label on the KPI cards and in the latest-rates table used the wrong comparison kinds (≥0 red, >0 green, =0 grey), so a falling rate had no colour and showed as faint grey. It is now >0 red, <0 green, =0 grey (kinds 1 / 3 / 0), in both modes.
- The info panel is simply on top again (z 4000). The earlier workaround that hid the visuals under it was removed, because it was built on a Desktop session that was still showing an old copy of the files.
- **Fix:** the YTD chip of the frequency slicer was cut off ("Y…"). The slicer is 30px wider (360), and the slicers to its right moved over (the compare slicer on the overview is 30px narrower, so the bar still ends at x 1066).
- `tools/check_layout.py` now covers 12 pages, the pop-up and a twin-position check. It passes, and `validate_report.py` reports no problems.
- Still to check in Desktop: the refresh (English files), the `Mapping` English names (T9), that the pop-up opens and closes without touching the slicers, and that the sync groups carry date and period across EN/ქა and ☀/🌛.

### 2026-10-11

**Repository reorganised and published**
- New layout:
  - `report/`: the PBIP project, moved from `notebooks/`
  - `tools/`: `make_light_pages.py`, `check_layout.py`, `validate_report.py`
  - `tests/`: `visual_tests.dax`
  - `docs/`: this log, plus `design/ferrari.md` and `design/airbnb.md`
  - `reference/`: NBG's report definition, the sample rates file and screenshots
- The README was rewritten for the new structure and maintenance workflow. `.gitignore` covers local Power BI files, common secret and credential patterns, Python caches and OS files. No credentials exist in the project: both NBG sources are public and read anonymously.
- After the move, `check_layout.py` passes, `validate_report.py` reports no problems, and regenerating the light pages produces no changes.

**Light mode v3 built + quality pass**
- The warm light palette was approved from the Figma mock.
  - `tools/make_light_pages.py`: `PALETTE` updated (page `#EFEEEA`, cards `#FAF9F7` with `#E2DFD9` hairline, text `#22201C` / `#5F5B54` / `#8A857C`, up `#B42318`, down `#0E7A43`; Ferrari red kept, 8px corners).
  - `Weekend_Font_Color_Light` is now `#8A857C` / `#22201C`.
- New `tools/check_layout.py` found 52 issues; all are fixed and it now passes with 0:
  - KPI tiles: the title strip is 22px tall and the change label sits at +148, so nothing overlaps the rate.
  - "Last update" date moved to y 90, below its label.
  - Nav tabs widened to 168 / 168 / 184 (x 592 / 768 / 944) so the Georgian labels fit.
  - Dark-mode contrast: change colours `#FF5A4F` / `#22B066`, and the compare caption uses `#969696`.
- The overview's latest-rates table got a "rate is not blank" filter, so BGN (listed, but no current rate) doesn't show as an empty row.
- New `tests/visual_tests.dax` (T1–T8).

**Light mode v3: warm, low-glare redesign (Figma, awaiting approval)**
- The Airbnb-based light mode was still too bright. Redesigned for eye comfort and mocked in Figma first.
- Proposed palette (checked in light mode on `#FAF9F7`):
  - page `#EFEEEA`, card `#FAF9F7` with a `#E2DFD9` hairline, elevated `#ECEAE5`, grid `#E8E5E0`
  - ink `#22201C` (15.5:1), body `#5F5B54` (6.4:1), muted `#8A857C` (3.5:1)
  - accent Ferrari red `#DA291C` kept for brand consistency (4.6:1)
  - rate up `#B42318` (6.3:1), rate down `#0E7A43` (5.1:1)
  - series `#2A78D6` `#EB6834` `#1BAF7A` `#EDA100`
- Figma (file H8YXahhpwjKxgJWpwr2exe, page Dashboard, row y = 800):
  - `01/02/03 … — Light` screens and a `00 · Design system — Light` board
  - a separate token collection `NBG Dashboard · Light`, because the Starter plan allows only 1 mode per collection
- Known issue in the Figma light screens: some text inside component instances is still bound to the dark `text/ink` token and renders white. Fix in Figma: select the light frames and, under Selection colors, swap it for the `NBG Dashboard · Light` token.

**Light mode switched to an Airbnb palette** (plain white was too bright)
- `npx getdesign@latest add airbnb` was run in a temporary folder and saved as `docs/design/airbnb.md`, so the Ferrari reference is kept for dark mode.
- Light mode now uses softened Airbnb tokens: grey `#EBEBEB` page, `#F7F7F7` cards with `#DDDDDD` hairlines, 12px corners, `#222222` / `#6A6A6A` text, Rausch `#FF385C` accent, rate up `#C13515` and down `#027A3F`.
- The ☀/☾ toggle was off-centre next to reset and info: it lacked their padding and border settings and used default text margins. Fixed in `toggle_button()`, so all three nav buttons now share identical geometry and container settings.
- `tools/make_light_pages.py` was rerun twice with identical output. The report validates: 142 visuals, 6 bookmarks, no dark leftovers on the light pages.

**Light-mode toggle** (light twin pages, built without a Figma mock)
- Added the `Weekend_Font_Color_Light` measure and the repo script `tools/make_light_pages.py`:
  - adds a ☀ toggle at 1144,12 to each dark page and shifts the tabs 40px left (once)
  - syncs the slicers
  - generates 3 light pages and 3 light reset bookmarks
- Validation: all JSON is valid; there are 6 pages and 142 visuals; every light link points to a light page except the ☾ toggle; 9 slicer sync pairs; the model loads with 40 measures. Rerunning the script gives identical output.
- Still to check in Desktop: that the hand-written `syncGroup` really carries selections across, that slicer drop-downs and tooltips have no dark leftovers in light mode, and the DAX number checks.

**Ferrari-inspired redesign: decisions (Figma mock in progress)**
- Ran `npx getdesign@latest add ferrari`, which created the design reference now in `docs/design/ferrari.md`.
- Decided: 8px rounded corners (not Ferrari's 0px), Segoe UI (it supports Georgian), Rosso Corsa as a scarce accent with green/red reserved for rate changes, and a top nav bar replacing the hamburger menu.
- Chart palette validated for the dark card surface.
- Figma mock built with real NBG data: https://www.figma.com/design/H8YXahhpwjKxgJWpwr2exe
  - Page "Dashboard": `01` Overview, `02` daily table, `03` monthly table, `00` design-system board. Page "Components": the reusable components.
  - Local variables for every colour, radius and spacing token. Components: Nav Tab, Period Chip, Rate Delta, Filter Field, Flag, Rate Row, KPI Card, Icon Button.
  - The Overview adds a KPI row (USD, EUR, GBP, TRY: rate plus change), above the area chart, the comparison chart and the latest-rates panel.
  - Daily table: weekend rows dimmed, latest row highlighted. Monthly table: the average column emphasised.
  - Figma has no Segoe UI, so Noto Sans / Noto Sans Georgian stand in. Flags are placeholders.
- **Approved.** KPI currencies changed to USD, EUR, GBP and **RUB** (the Figma mock was updated to match).

**Ferrari redesign: Power BI build**
- New measures in `Metrics` (folder `NBG Report`): `Prev_Date` (now reused by `Rate_Diff`), `Rate_Diff_Label` (▲/▼ + sign), `Compare_Caption`, `Last_Update_Label` and `Weekend_Font_Color`. `Title_Ex_Rate` is now one line.
- A one-off restyle script:
  - removed 56 NBG decoration visuals (left rail, panels, hamburger menu, info groups, old titles)
  - moved the data visuals to the Figma coordinates and restyled every slicer, chart and matrix
  - added the top nav (title, page buttons with a red underline on the active page, reset, info) and the "last update" field
  - built the 4 KPI cards from a background shape, a text box and 3 cards each
  - the latest-rates tables now show every listed currency, with the Georgian name added; daily-table weekend values are dimmed; the monthly average column is emphasised
  - bookmarks reduced to `Home_Page_1/2/3`
- Validation: all JSON is valid, no stale references, and the model loads with 39 measures. Still to check: render and refresh in Desktop, plus the DAX number checks.

**Desktop load fixes**
- Desktop failed to open the project:
  1. A circular dependency: `Currency_Long` was sorted by a DAX column derived from it. Fixed by moving `Sort_Order` and `Name_Sort_Order` into Mapping's Power Query.
  2. The `Frequency` DATATABLE was garbled by a Python f-string. Fixed.
- Desktop has since re-saved `Frequency.tmdl` and `Mapping.tmdl`. The numbers still need checking against NBG with DAX.

**Rebuild of NBG's report**
- Model: dynamic parsing of both NBG files (`fnNbgParseSheet`); history now comes from NBG's `exratesyearsgeo.xlsx` (2001–2025) instead of a missing local file; Mapping comes from the files' header rows; new `Frequency` table; `Advanced_Calendar` covers 2001 onwards; 13 new measures; automatic date tables removed.
- Report: replaced the 3 old pages with NBG's 3 pages (74 visuals, 12 bookmarks), remapped all fields, removed NBG branding and the contact panels, swapped the PNG icons for ☰ / ✕ / ⓘ, added a teal background and an `Is_Listed` page filter.
- Checked with a Python replica against the NBG files: USD 2.6005 (−0.0014), EUR 2.9154, GBP 3.4415, 1Y base date 12-10-2025 (USD 2.7117), September 2026 USD average 2.6114 (min 2.6051, max 2.6250).
- README updated for the PBIP layout.
- Session decisions: history read from the NBG website, NBG's hamburger navigation (later replaced by the top nav in the redesign), and Currency_Long kept in Georgian (it already was).
