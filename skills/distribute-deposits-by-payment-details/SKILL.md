---
name: distribute-deposits-by-payment-details
description: Distribute each deposit's Amount into the correct month or year column of a working sheet by parsing its Payment Details text, so the DIFF column nets to 0. Handles single months, year-only, multi-part splits, VAT/quoted formats, and itemized breakdowns embedded in narrative. Excludes the separate "copy INS Company column from another sheet" task.
---

Distribute deposit amounts from a free-text "Payment Details" column into the correct month/year columns of a working sheet (e.g. Sheet2 of the BANK aging workbook) so the difference column reconciles to 0.

## When to use
Trigger when the user asks to spread/allocate amounts by their details, e.g.:
- "وزع لى المبالغ من عمود ... بسحب التفاصيل بتاعتها" / "وزع المبالغ حسب التفاصيل"
- "distribute the amounts by their payment details so the DIFF column = 0"
- "put each amount in its month column, or its year column if only a year is given"
- "read transfers like this and distribute them correctly" (itemized breakdowns)

## Out of scope (do NOT do here)
Do NOT copy/pull an INS Company (insurance-company) column, or any other column, from another sheet like "BANK 2025-2026". That is a separate task. This skill is only about distributing the amount into month/year columns.

## Core rule
For each data row, parse the Payment Details text and place the Amount:
- **Specific month AND that year has a month column** → put it in that month's column.
- **Only a year given, OR a month in a year that has no month column** (e.g. 2024/2026 when only 2025 has monthly columns) → put it in that year's bucket/"Adj" column.
- **Goal:** the DIFF column (= Amount − SUM(distribution columns)) equals 0 for every parseable row.

## Critical working principles
1. **Content-driven, never row-number-driven.** The sheet is sorted/filtered frequently, so row numbers are NOT stable. Always re-parse the Payment Details column; never rely on a saved list of row numbers from a previous turn.
2. **Single-period rows → formula** `=<AmountCell>` (e.g. `=R57`) so the cell stays tied to the amount. **Multi-part splits → literal component amounts** (they come from the text and don't have a single source cell).
3. **Only write into the distribution columns**; don't touch Payment Details, Amount, Date, etc.
4. **Leave unparseable rows untouched** (do not force). Report them for manual review.

## Step 1 — Map the layout (read the header row). Done when you know every column's role.
Read row 1/2 headers and identify:
- **Year bucket columns** (labels like "Y-2023", "YEAR-2024", "YEAR-2025 Adj", "YEAR-2026 Adj").
- **Month columns** — their header cells are dates. Read the serial/date to know which (year, month) each column is (e.g. Jan-2025 … Dec-2025).
- **Payment Details** text column, **Amount** column, **DIFF** column, and any **Date/Month/Year** helper columns.
- Confirm the DIFF formula, e.g. `=Amount − SUM(firstDist:lastDist)`. Note whether any year bucket column is EXCLUDED from that SUM (see Step 5).

## Step 2 — Read details + amounts. Done when you have Payment Details and Amount for all data rows.
Read the Payment Details column and Amount column for the full data range in one pass.

## Step 3 — Parse each row. Support these formats:
- **Serial date number** (cell formatted mmm-yy) → convert to (year, month).
- **Text month:** "SEPTEMBER - 2025", "Nov-25", "Nov-2025", "May-2026" (2-digit year → 2000+yy).
- **Year only:** "Y-2025" or bare "2025" → year bucket.
- **Multi-part "amount for period"** repeated: `"219.00 for 01-2026 235.72 for 12-2025"`, `"1383.97 for 01-2025, 240.42 for 01-2026"`. Allow optional "VAT"/"RECON" words between "for" and the period, and allow the period to be a bare year (`"for VAT 2025"`).
- **Period-first:** `"Oct-2025 for 1,105.88"`.
- **Quoted pairs:** `02-2026"413.92"`.
- **Parenthetical / signed amounts:** `"(-3,366.00)"` = −3366; `"-381"`, `"+213"`.
- **Itemized breakdown inside narrative:** `"May-2026 (GI Batch#3 Closure: -381 for 12-2023, +213 for 09-2025, +305 for 05-2026 = 137 vs dep 136.76)"` → parse each `±N for MM-YYYY` component and place each in its column. A small residual between the components' sum and the deposit is acceptable (the note itself documents it, e.g. "137 vs dep 136.76") — do NOT distort figures to force exact 0.

**Flag (leave untouched) when the text can't be split unambiguously:**
- RECON / "up to" month ranges with one lump sum (`"RECON F 09-2024 up to 11-2025"`).
- Comma-listed months with NO per-month amount (`"10,11-2025"`, `"8,9,10,11-2025"`).
- Freeform narratives / recon-pool deduction notes with no clean per-period amounts.

For every parsed row, validate that the component amounts sum to the Amount (tolerance ≈ 0.05); if not, flag it.

## Step 4 — Write the distribution. Done when parseable rows are written.
- Build each row's full distribution range fresh (clear leftovers/placeholders), set target cells: single-bucket = `=<AmountCell>`, splits = literal amounts.
- Suspend auto-calc for large multi-row writes; write via a formulas array.

## Step 5 — Handle a year bucket column excluded from DIFF.
If you place an amount in a year bucket column that the DIFF formula does NOT currently sum (e.g. a newly inserted "Y-2023" column), extend the DIFF formula to include it (`=Amount − SUM(firstBucket:lastMonth)`). Safe as long as that column is empty on all other rows — verify first.

## Step 6 — Verify. Done when DIFF is checked on every row.
Re-read the DIFF column across all data rows. Confirm it is 0 everywhere except intentionally-flagged rows (and known rounding residuals). Report: count distributed, count flagged (with their row content), and any residual rows.

## Report
Tell the user: how many rows were distributed, which rows were left for manual review and why (recon ranges / comma-multi-months / narratives), and any row with an accepted rounding residual.
