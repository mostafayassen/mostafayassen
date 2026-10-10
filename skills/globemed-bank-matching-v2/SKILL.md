---
name: globemed-bank-matching-v2
description: Match GlobeMed bank deposits in the BANK workbook against the GlobeMed payment-details file (per-check breakdown with fees), record each deposit's claim/billing month(s) in Payment Details, tag the confirmed underlying insurer in the INS Company column, and red-flag deposits that don't reconcile. (v2 — supersedes globemed-bank-matching)
---

## When to use
When the user asks to record Payment Details for GLOBEMED (TPA) deposits in the BANK workbook, using the GlobeMed source file ("globemed payment details.xlsx", sheet "globemend", table "globemend" A1:K1170, ~1169 data rows). This version supersedes "globemed-bank-matching" — use this one.

GlobeMed is different from SAICO/Bupa/Tawuniya/etc.: matching is driven by a **check-number grouping + one-time transfer fee**, not a payout ratio band and not a pre-reconciled SOA payment list.

## Source file structure ("globemend" table)
A **Source.Name** (branch — THIS is the branch identifier that matches the BANK workbook's BRANCH column; use this one for all branch matching) · B CATEG · C NPCOD · D PROVIDER DESC (a longer/different provider description — do NOT use this for branch matching, it is not the name used in the BANK sheet) · E RNBR · F RISK CARRIER DESC (underlying insurance company, e.g. AMANA COOPERATIVE INSURANCE CO, ARABIA INSURANCE CO., ORIENT INSURANCE, Salama Cooperative.Ins., Walaa Cooperative Insurance, Saudi Enaya, Mutakamela Insurance) · G BILLING MONTH (date = the claim/loss month) · H "Payment without fees" (formula `=[@[paid with fees]]-3.45`, i.e. always I−3.45 for that single row) · I "paid with fees" (the raw claim amount before any fee deduction) · J CHKNBR (check number) · K CHK DATE (dd/mm/yyyy text).

## BANK workbook column layout (confirmed on "BANK 2026 (2)")
A–I = year/month buckets (A=YEAR-2024, B=YEAR-2025, C=Jan-2026 ... I=Jul-2026, extend right as months are added) · J=Payment Details · K=Amount · L=Date · M=Month · N=Year · O=INS TPA (filter to "GLOBEMED") · P=BRANCH (match against Source.Name) · Q=Provider No. · R=INS Company · S=CHI · U=DIFFRANCE (formula `=K-A-B-C-...-I`, must be 0 once distributed). Column letters vary by file — always confirm the actual header row (row 2) before writing.

## Core matching rule (unifies single payments and batches)
A bank deposit from GlobeMed = one physical check. Group "globemend" rows into checks using the composite key **CHKNBR + Source.Name (branch) + RISK CARRIER DESC** — NOT CHKNBR alone.

**Known pitfall confirmed on real data**: CHKNBR values are reused across many different branches and carriers (e.g. the same CHKNBR+CHK DATE combo can appear for 7-16 different branches and 2 different carriers). Grouping by CHKNBR alone, or even CHKNBR+CHK DATE, produces massively mixed groups. Grouping by CHKNBR+branch+carrier, however, always resolves to exactly one CHK DATE (verified: 0 exceptions across 1025 groups) — that composite key is the true physical-check identifier.

1. **Group** all rows by CHKNBR + Source.Name + RISK CARRIER DESC.
2. **Expected deposit amount** = SUM("paid with fees" over the group) − 3.45. The 3.45 SAR transfer fee is deducted exactly **once per check**, regardless of how many claim lines (1 or many) are in the group.
3. **Billing months in the group**: collect distinct BILLING MONTH values, normalized to (year, month) — a group can have several different day-level BILLING MONTH values that all fall in the same calendar month; treat those as one bucket.

## Matching against the BANK workbook
For each empty GLOBEMED row (Payment Details/J blank) in the BANK sheet, for the row's branch (P — match against **Source.Name**, never PROVIDER DESC):
- Find a CHKNBR+branch+carrier group whose **expected amount** matches the bank Amount (K) within ±0.01 SAR.
- Date check: CHK DATE of the group must fall within **bank date − 2 days to bank date + 21 days**.
- **Do NOT restrict by the existing INS Company (R) suffix as a hard filter** — confirmed on real data that R's carrier suffix (e.g. "GLOBEMED - ARABIA") is not reliably applied before matching (bare "GLOBEMED" rows frequently turned out to belong to ARABIA/Mutakamela/Salama groups). Search across ALL carriers for the branch; amount + date window alone is sufficiently discriminating (zero ambiguous multi-candidate collisions observed across 133 test rows).
- Each CHKNBR+branch+carrier group can only be consumed by ONE bank deposit row — track usage so the same check isn't matched twice.
- If more than one group is a valid candidate for a row, do not guess — treat like a red flag and ask the user.

## Writing Payment Details (column J)
- If the whole group falls in one (year, month) bucket:
  - 2026 (or later) month with its own BANK-sheet column → J = that column's header date serial (first-of-month), e.g. `Jan-26`; put the amount in that month's column as formula `=K<row>`.
  - 2024/2025 (year-only bucket, no monthly column exists) → J = Dec-1 of that year as a placeholder (displays `Dec-25`); put the amount in that year's column (A or B) as formula `=K<row>`.
- If the group spans multiple (year, month) buckets → SAICO-style text list, thousands-separated, 2 decimals, in `amount for MM-YYYY` form, e.g. `1,122.79 for 01-2025, 35,722.72 for 01-2026`. Split the amount across the relevant columns: one bucket as a literal value, the other bucket as formula `=K<row>-<othercol><row>` so DIFFRANCE (U) nets to 0. The two split amounts must sum exactly to K.
- Apply the one-time 3.45 SAR fee deduction to whichever claim line has the largest "paid with fees" value in the group; document this choice in the cell note.
- Add a cell note (Excel comment) on the Payment Details cell: `CHKNBR | CHK DATE | Branch | Carrier`, which line absorbed the 3.45 fee, and the full list of underlying lines (PROVIDER DESC + billing date + paid-with-fees amount).

## Recording the confirmed insurer (column R, INS Company) — MANDATORY
Once a row is matched, set R to the SPECIFIC underlying carrier using the same `"GLOBEMED - <short name>"` format already used for historical transfers in the BANK sheet — do not leave it as the generic `"GLOBEMED"`. Confirmed mapping (derived from majority usage across existing BANK sheet rows — re-verify on the actual file if it's been edited, since this is house convention, not a globemend-file field):
| RISK CARRIER DESC | BANK sheet R value |
|---|---|
| AMANA COOPERATIVE INSURANCE CO | GLOBEMED - AMANA |
| ARABIA INSURANCE CO. | GLOBEMED - ARABIA |
| ORIENT INSURANCE | GLOBEMED - ORIENT |
| Salama Cooperative.Ins. | GLOBEMED - Salama |
| Walaa Cooperative Insurance | GLOBEMED - WALLA |
| Saudi Enaya | GLOBEMED - Enaya |
| Mutakamela Insurance | GLOBEMED - Mutakamela |

Only leave R as generic "GLOBEMED" for rows that remain red-flagged/unmatched (no confirmed carrier to report). Do NOT overwrite R on rows outside the current task's scope (i.e. rows that already had Payment Details filled in from a prior session) unless the user explicitly asks for a full-file carrier-label cleanup — only apply this to rows you are matching in the current run, to avoid silently overriding a prior human judgement call on an ambiguous historical row.

## Red/yellow flag rules (per house-wide bank-matching policy)
- No group matches within tolerance/date window, OR the branch doesn't appear anywhere in the globemend source table at all → do NOT record a month. Highlight Payment Details red `#FFC7CE`, leave empty, add a note with the closest-candidate CHKNBR groups considered and why they were rejected (amount diff, date diff, or "branch not found in source").
- An exact amount match with an implausible date (e.g. CHK DATE weeks after the deposit date) is still a red flag, not an auto-match — a coincidental amount match is not enough on its own.
- Tiny differences (~1 SAR, or ties that are unambiguous) → fill with a yellow flag and an explanatory note instead of red.

## After confirming Payment Details
Distribute the deposit amount into the BANK sheet's year/month columns based on the year(s)/month(s) of the matched BILLING MONTH bucket(s) — see "Writing Payment Details" above for the exact column/formula rules. Skip red-flagged rows entirely (no year-column entry).

## Verification (mandatory)
Re-read written Payment Details cells using their **displayed text** (not just the underlying serial) — confirm `Jan-26`/`Dec-25` render correctly, confirm multi-bucket text lists render and sum to K, and confirm DIFFRANCE (U) = 0 for every matched row. Note: this sheet can have a live sort/filter that reorders rows as data changes — always re-locate rows by their own K/L/P values for verification, never assume a row number is stable across calls once you've started writing. Report: how many rows filled single-bucket vs multi-bucket, how many red-flagged (with reasons), and any groups that failed the branch/carrier consistency check and were escalated to the user instead of guessed.

## Known pitfalls
- CHKNBR values are NOT globally unique across branches/carriers in the source file — always group by CHKNBR + Source.Name + RISK CARRIER DESC together, never by CHKNBR alone or CHKNBR+date alone.
- Don't deduct 3.45 per claim line — it's a single transfer fee per check, deducted once from the group total (applied to the largest line).
- Don't use the BANK sheet's existing INS Company (R) suffix to restrict which carrier a row can match against — it's not reliably pre-populated; match on branch+amount+date only, then WRITE the confirmed carrier to R afterward.
- Don't use PROVIDER DESC (column D) for branch identification — it's a different descriptive name not present in the BANK sheet. Always use Source.Name (column A).
- Rows can physically reorder mid-task if the sheet has an active sort/filter reacting to your writes — re-derive row locations from stable data (K amount, L date, P branch) rather than caching row numbers across tool calls.
