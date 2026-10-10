---
name: insurance-vol-disc-tiers
description: Calculate annual volume-discount (Vol. Disc Amount) per branch for an insurance company in the '2026 SOA BY TPA' sheet, using tiered rate brackets on annualized business volume.
---

## When to use
User asks to calculate/rebuild "خصم حجم الأعمال" (volume discount) for a specific insurance company in the "2026 SOA BY TPA" sheet (or similarly structured SOA sheets), giving tier brackets like "من 0 لـ 100K = 2%، من 100K لـ 200K = 3%..." and asking the discount to be annualized even though the sheet only has partial-year actual data.

## Sheet structure assumptions
- Column C = "Insurance Co." (company name to filter on, e.g. "SAICO", "NEXT CARE")
- Column D = "Branch"
- Column E = "Month" (date serial, one row per branch per month)
- Column H = "Total" (Net Amount + VAT) — this is the base the discount rate applies to
- Column K = "Vol. Disc Amount" — the output column to fill
- The sheet is organized in sequential month-blocks (e.g. 6 blocks for Jan-Jun), so rows for one company are NOT one contiguous range — they appear once per month-block, each block internally contiguous. Always re-derive contiguous row runs; do not assume prior runs still apply after the user sorts/re-hides rows.

## Step 1: Get inputs from the user (ask if not given)
- Company name to filter (column C exact match)
- Tier brackets and rates (e.g. 0-100K:2%, 100K-200K:3%, 200K-300K:4%, 300K+:5%)
- How many months of actual data are present vs. the annualization target (e.g. "6 months actual, annualize to 12" → multiply by 2). Confirm the multiplier explicitly; don't assume 2x.

## Step 2: Scan the data (execute_office_js)
Read column C (and D, H) across the full used range in one shot (avoid dumping to chat). Build:
- List of (row, branch, H) for every row where C == company name
- Aggregate H by branch (sum across all months present) = "actual period total"
- Find contiguous row runs (sorted row numbers, group consecutive integers) — needed later to batch-write formulas efficiently instead of touching 100+ scattered cells one by one.

## Step 3: Build an audit-trail helper table (visible on sheet, not hidden)
In an unused column block (check first with get_cell_ranges that target columns are empty, e.g. far right like V:AB):
1. Tier table: lower-bound thresholds + rates, blue font (input assumptions). VLOOKUP-ready (ascending lower bounds).
2. Per-branch summary table: Branch (use `=UNIQUE(FILTER(branch_range, company_range=company))` so it stays dynamic) | Actual period total (`=SUMIFS(H_range, C_range, company, D_range, branch)`) | Annualized projection (`=actual * multiplier`) | Applicable rate (`=VLOOKUP(annualized, tier_table, 2, TRUE)`).
This table is the traceable source of truth for which rate each branch got — keep it on the sheet even after hardcoding (Step 4), so the user can audit/verify the rate later.

## Step 4: Write the final K column formulas as LITERAL rates, not lookups
**Important user preference confirmed in practice**: the final formula in column K must read as `=H<row>*<rate>%` (a plain hardcoded percentage), matching the convention already used elsewhere in this sheet for other insurance companies. Do NOT leave a live XLOOKUP/VLOOKUP or helper-cell reference in the final K formula — the user explicitly asked for the simple hardcoded form after first seeing a lookup-based version.
Process:
1. From the Step 3 summary table, read off each branch's resolved rate.
2. For each contiguous row run (Step 2), write `=H<row>*rate%` at the first row of the run, then `copy_paste_range` down the run.
3. Where a run mixes branches with different rates, split into sub-ranges by branch boundary within that run and write/copy each rate separately.
4. Re-verify branch-to-row mapping right before writing (re-run the Step 2 scan) if any sorting/hiding happened between planning and writing — row positions shift after RowSorted actions.

## Step 5: Verify
- Read back all written K cells; confirm no #N/A/#REF!/#VALUE!.
- Spot check 2-3 cells against the helper table (H * rate should equal K).
- Report which branches landed in which tier and why (e.g. "Doha Medical Clinics annualized to 447K → >300K bracket → 5%").

## Done when:
- Every target-company row in K has a literal `=H<row>*X%` formula (no lookup functions remaining in K).
- The helper tier + per-branch summary table remains on the sheet for audit purposes.
- No formula errors in the written range.
