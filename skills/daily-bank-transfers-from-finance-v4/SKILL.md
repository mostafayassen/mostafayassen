---
name: daily-bank-transfers-from-finance-v4
description: >-
  Add daily/new incoming bank transfers from Finance into the Aging Bank workbook (BANK 2025-2026 / BANK 2025-2026 By Year / BANK 2025 / BANK 2026) — match each transfer by IBAN, or by (Branch, Company) if IBAN unavailable, via PR.CODE, and log it in both sheets, leaving Payment Details blank until claim-month reconciliation. v4 (English rewrite, supersedes v2 and v3 — delete both): adds (1) matching without IBAN via (Branch, Company) with branch names resolved to canonical via PR.CODE; (2) TPA sub-branding rule — when the extracted insurer is just a TPA (e.g. TCS) but narration names the real carrier (e.g. ALSAGR, ARABIAN SHIELD), reuse the existing "TPA - SUBBRAND" convention instead of the generic name; (3) warning that historical rows in BANK 2025-2026 and BANK 2025-2026 By Year are not row-synced 1:1 — locate matching rows independently via (date, amount, branch), except for rows just appended in the same session.
---

## When to Use
Same use cases as previous versions: The user wants to record new incoming bank transfers from Finance into the unified Aging Bank workbook.
- **Typical Prompts:** "Add missing transfers", "Record Finance transfers", or invoking `/daily-bank-transfers-from-finance`.
- **Golden Rule (Unchanged):** In this stage, record **ONLY** the full identity metadata of the transfer (`Amount`, `Date`, `Month`, `Year`, `INS TPA`, `BRANCH`, `Provider No.`, `INS Company`, `CHI`). **DO NOT** populate `Payment Details` (claim billing month); this is handled later by dedicated company-specific reconciliation skills.

---
## Pattern: Multi-Sheet Source (`Insurance Collection - Month YYYY.xlsx`)
In practice, the raw Finance file may arrive split into separate daily sheets (one sheet per day or date range) rather than a single consolidated sheet, or as a flat file with columns: `Date` / `Transaction Details` / `Description` / `Amount` / `Company` (completely lacking `ACC`/`IBAN` columns — see "Matching Without IBAN" below).

### Handling Daily Sheets:
1. Extract all rows where `Debit > 0` across all daily sheets in one batch via `execute_office_js`, recording the source sheet name alongside each row.
2. If the user requests "current sheet only" or specifies a particular day/range, verify the active sheet name via `read_surface_context`.
3. Write the consolidated dataset into a single shared JSON file (`conductor.writeFile`).

---
## Pattern: Source and Target Workbooks Across Separate Excel Agents
- **Source Agent Scope:** Aggregation + filtering + writing to the shared JSON file.
- **Target Agent Scope (`Aging Bank`):** Reading `PR.CODE`, matching, deduplication (dedup), and executing writes into `BANK 2025-2026` and `BANK 2025-2026 By Year`.
- Use `send_message` to transfer the JSON file path along with explicit instructions (matching key used, dedup rules, leave `Payment Details` blank).
- Silently absorb and log any confirmation messages from the peer agent that do not contain actionable questions into the Claude Log.

---
## Matching Without IBAN — When Source Lacks IBAN/ACC
If the raw file is flat (`Date`, `narration`, `Description`, `Amount`, `Company`), lacks `ACC`/`IBAN` columns, and IBAN cannot be inferred from narration:
1. **User Confirmation Required:** Pause and ask the user to confirm the canonical branch name (never infer or assume a branch name purely from descriptive narration) — unless previously confirmed in the conversation history.
2. **Composite Match via `(Branch, Company)`:** Look up `PR.CODE` where `Branch PRIME NAME` (or a known alias) matches the confirmed branch name, and extract:
   - Canonical `Branch` (written to `BRANCH`).
   - `CHI`.
   - `Provider No.` specific to each insurance company (`Insurance Co.`) — note that a single branch has different Provider Numbers across insurers.
3. **Company Canonicalization:** Map the extracted descriptive company name (e.g., "Bupa Insurance Company") to the canonical code in `PR.CODE` column `Insurance Co.`. If the name is ambiguous (e.g., "Axa Insurance Company" which resolved to `GIG` based on the narration string "GULF INSURANCE GROUP"), inspect the full narration text for verification rather than relying solely on the extracted name.
4. **Deduplication:** Treat a transfer as duplicate if an existing row matches `(date serial, amount)` within the same canonical branch — do not insert duplicates.

---
## TPA Sub-Brand Correction
Some insurance names extracted from narration represent a TPA / claims administrator (e.g., `TCS`) rather than the underlying insurance carrier. Always inspect the full `narration` / `description` of each row:
1. If narration explicitly mentions a specific carrier (e.g., "ALSAGR Cooperation Insurance CO.", "ARABIAN SHIELD COOPERATIV CO"):
   - Do **NOT** record `INS Company` as the raw TPA name.
   - Search existing rows in `BANK 2025-2026` (for the same branch and TPA) for the convention `"TPA - SUBBRAND"` (e.g., `"TCS - ALSAGR"`, `"TCS - ARABIAN SHIELD"`, `"TCS - ACIG"`).
   - Use the **exact literal string** already established in the sheet — do not invent a new variant.
   - If no prior row exists with this sub-brand, use the closest established convention and explicitly notify the user/peer agent that this is a new, unverified sub-brand label.
2. `INS TPA` remains unchanged (the canonical TPA name, e.g., `"TCS"`) — correction applies strictly to `INS Company`.
3. If the narration contains only generic TPA text without a specific carrier (e.g., "TOTAL CARE SAUDI THIRD PARTY ADMINISTRATORS" or generic B2B/FRACCT references), keep `INS Company` as the raw TPA name without guessing sub-brands.

---
## Warning: Historical Row Asynchrony Between Sheets
Row index alignment (identical row numbers between `BANK 2025-2026` and `BANK 2025-2026 By Year`) is **only guaranteed for newly appended tail rows added within the same session**.
- Historical rows may have completely different row numbers between the two sheets for the exact same transaction.
- **Rule:** For any edits, lookups, or corrections on historical records, independently locate the target row in each sheet using the composite key `(date, amount, branch)`. Never assume row indices match across sheets unless dealing with the current insertion batch.

---
## Target Workbook Structure (`Aging Bank`) — Verified at Runtime

### `BANK 2025-2026` (Master Sheet)
- **Data Range:** Starts at Row 3 (Row 1 = totals, Row 2 = headers).
- **Columns:**
  - `AG`: Payment Details
  - `AH`: Amount
  - `AI`: Date
  - `AJ`: Month (`=MONTH(AI)`)
  - `AK`: Year (`=YEAR(AI)`)
  - `AL`: INS TPA
  - `AM`: BRANCH
  - `AN`: Provider No.
  - `AO`: INS Company
  - `AP`: CHI
  - `AQ`: Bank (blank)
  - `AR`: DIFFRANCE (`=AH-SUM(A:AF)`)

### `BANK 2025-2026 By Year`
- **Columns:**
  - `A:H`: `YEAR-2019` through `YEAR-2026`
  - `I`: Payment Details
  - `J`: Amount
  - `K`: Date
  - `L`: Month
  - `M`: Year
  - `N`: INS TPA
  - `O`: BRANCH
  - `P`: Provider No.
  - `Q`: INS Company
  - `R`: CHI
  - `S`: Bank (blank)
  - `T`: DIFFRANCE (`=J-SUM(A:H)`)

### `PR.CODE` (Mapping Sheet)
- **Columns:**
  - `C`: Prim Insurance Co. Name
  - `D`: INS CODE
  - `E`: Insurance Co. (Canonical Code)
  - `F`: Branch PRIME NAME
  - `G`: Branch (Canonical Name used in BANK sheets)
  - `H`: NAME
  - `I`: Provider No.
  - `J`: CHI
  - `K`: VAT NO
  - `L`: Nphies ID
  - `M`: IBAN
- **Composite Key (when IBAN is present):** `(M=IBAN, E=Insurance Co.)`.

---
## Branch Name Correction via IBAN (When IBAN is Available)
In multiple production cases, the descriptive `Branch` column in the raw Finance file was erroneous and corrected via `IBAN -> PR.CODE` (e.g., `IBAN=2370 -> Al Waha`, `ACC=2198 -> OLAYA`, `ACC=8815 -> MADINA 2`).
- **Rule:** Always prioritize `IBAN -> PR.CODE` to determine the canonical branch whenever an IBAN is available. Do not trust descriptive branch names from the raw file even if they appear plausible.

---
## Execution Workflow
1. Build an in-memory lookup table: `IBAN / Branch -> (Canonical Branch, Provider No., CHI)` from `PR.CODE` after filtering corrupt/invalid rows.
2. Resolve each transaction to its canonical Branch and Insurance Company.
3. Perform deduplication against the master bank sheets using `(date, amount, canonical branch)`.
4. Append verified new transactions to both synchronized sheets (current tail), leaving `Payment Details` blank and applying standard `DIFFRANCE` formulas.
5. Perform mandatory reconciliation to confirm total debits match and zero duplicates exist.

---
## User Reporting Guidelines
Always include the following in the final summary:
1. **Matching Method:** State whether matching was performed via IBAN or via `(Branch, Company)` due to missing IBAN, including user confirmation details for the branch name.
2. **Corrections Detected:** Report any branch name corrections or insurance company corrections (TPA sub-branding), noting row numbers and final values.
3. **Execution Context:** Indicate whether source and target resided in the same workbook or across separate agent sessions, including `send_message` payload details.
4. **Reconciliation Counts:** Specify the count of newly inserted transfers versus duplicates skipped.
