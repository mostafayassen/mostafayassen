---
name: saico-bank-matching
description: Match SAICO bank deposits in the BANK workbook against SAICO per-branch Customer SOA files uploaded by the user (PDF or merged xlsx), record each deposit's Loss Month(s) in Payment Details — including split multi-month payments and AP-DEBIT recoveries — and red-flag deposits not covered by the statements.
---

## When to use
When the user asks to record Payment Details for SAICO deposits in the BANK workbook (sheet like "2024-2025-2026"). SAICO is DIFFERENT from the other insurers: there is no payout-percentage band and no statement via the connected agent. Instead the user uploads SAICO "Customer SOA / Supplier SOA" files — one per branch (PDF) or several branches merged in one xlsx ("Binder"). Matching is exact amount reconciliation, not ratio-based.

## Golden rule (from the user)
Never guess a month. If a deposit cannot be matched exactly against the uploaded statements, highlight it red #FFC7CE, leave Payment Details empty, and add a note explaining why (statement missing / deposit after SOA run date / sum mismatch).

## SOA file structure
- Sections start with a row/text "Customer Name :<code>  <NAME>" — one customer = one branch.
- **AP-STANDARD** rows = claim details: Narration contains "Loss Month YYYY-MM"; amount in the **Credit** column (positive).
- **AP-DEBIT** rows = recoveries/deductions: amount in the **Debit** column → treat as **negative** part; also has its own Loss Month (usually an older month being clawed back).
- **AP_Payments** rows (Narration "MED CLAIMS") = the actual bank transfers: amount in the **Debit** column; equals the sum of the detail rows since the previous payment, exactly.
- The SOA header has a "Run Date And Time" — deposits dated after it cannot be matched.
- Parsing: xlsx → openpyxl in the Python container; PDF → PyMuPDF `fitz` (pdfplumber may be broken in the sandbox). Regex `Loss Month\s*(\d{4}-\d{2})` on the Narration.
- **Page-break quirk:** a detail row sometimes appears AFTER its AP_Payments row (or as a leftover at section end). If a payment's parts don't sum to its amount, attach the adjacent leftover detail(s) — every payment must reconcile to ±0.01 before you use it.

## Known customer → branch mapping (verified by amount-matching; extend as new ones appear)
1003371 DAMMAM 1→DAMM 1 · 1003575 IHSAA ALAHSA→AHSSA 1 · 1004779 SAUDI SWISS→OLAYA · 1004823 ALKHOBAR→KHOBAR 1 · 1004834 DAMMAM 2→DAMM 2 · 1010487 AL DOHA→Doha Medical Clinics · 1010545 KHOBR2→KHOBAR 2 · 1010546 AL QATIF→QATIF · 1014637 YANBU→YANBU · 1014638 BASAMAT RAKA→BASAMAT · 1014639 DAR RAM KHOBAR 3→Dar Ram · 1014641 AHSA2 HUFUF→AHSSA 2 · 1015918 RAM MEDICAL CLINICS CO→DAWHA · 1016629 (JUBAIL)→JUBAIL · 1016740 RAM MEDICAL CLINICS COMPLEX→DAMM 3 · 1027042 RIYDH→RIYADH · 1027043 RAM DAMMAM MEDICAL COMPANY COMPLEX→DAMM 4 · 1027051 ALWAHA→Al Waha · 1029105 RAHIMA→RAS TANWROA · 1033325 FAKHIRA→Al Fakhria · 1036758 JEDDAH→JEDDAH 3 · 1041143 AL-KHAFJI→Khafgi · 1046860 RAM MEDICAL CLINICS→Al Manar · 1051828 AZIZIA KHOBAR→Al Azizia.
For any NEW/unknown customer, derive the branch by voting: match its payments (amount ±0.01, bank date within payment date −2..+21 days) against ALL SAICO bank rows (filled + empty); if candidates for a payment are all in one branch it's a vote; majority wins; if ambiguous ask the user (they offered to identify branches by name).

## Steps
### 1. Parse the SOA file(s)
Extract per customer the reconciled payment list: {date, amount, parts:[[loss_month, part_amount±],…]}. Verify every payment reconciles exactly; fix page-break leftovers.
**Done when:** all payments reconcile ±0.01 (print any that don't — investigate AP-DEBIT rows before proceeding).

### 2. Scope bank rows
Scan the BANK sheet (col I=Payment Details, J=Amount, K=Date, N=INS TPA contains "SAICO", O=BRANCH). The user re-sorts rows constantly — never reuse row numbers from earlier scans, and before every write re-verify branch+amount of the target row.
**Done when:** fresh list of empty SAICO rows.

### 3. Match
For each empty row: payments of the branch's customer with |amount diff| ≤ 0.01 and bank date within payment date −2..+21 days; nearest date wins; each payment used once. Typical pattern: Loss Month M is paid ~8th–13th of M+1.

### 4. Write
- Single Loss Month → date serial of the month's 1st, numberFormat "mmm-yy".
- Multi-month → text in the user's house format, thousands-separated with 2 decimals: `43.61 for 11-2025 26.02 for 12-2025 92.50 for 09-2025`; negative recovery parts as `(-1,185.28) for 12-2025`. (Format numbers manually — the sandbox's toLocaleString may not add thousands separators.)
- Add a cell note on every filled cell: Loss Month(s), payment amount+date, customer code+name, source file name + SOA run date. Use worksheet-level `sheet.comments.add("I<row>", text)` — workbook-level comments.add with a sheet-qualified address throws InvalidArgument.
- Uncovered deposits (missing branch SOA / dated after run date / irreconcilable) → red #FFC7CE, blank, note with the reason.
**Done when:** every scoped row is filled-with-note or red-flagged.

### 5. Verify and report
Re-read written range (values + rendered text + fills). Report: counts (filled single/split, red by reason), the branch mapping used for any new customers, and exactly which deposits need a newer SOA or missing branch files.
**Done when:** read-back matches the claims and every exception is named with row + branch + amount.
