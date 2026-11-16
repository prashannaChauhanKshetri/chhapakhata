# Prompt: bulk payment import, and the features around it

Use this prompt with an AI coding assistant or a developer working on ChhapaKhata
(Django + DRF backend, React + Mantine frontend, PostgreSQL with one business per
shop). Read `apps/system/sheets.py`, `apps/system/go_live.py` and
`apps/billing/services.py` before starting.

---

## Background

OM Traders keeps a separate sheet of **payments received**. Each customer's
**opening balance** (what they owed when last fiscal year closed) is already
imported. The shop now needs the payments received after that imported in bulk,
instead of typing them one by one in Receive payment. Other shops keep the same
kind of sheet laid out differently.

A real sheet looks like this:

| DATE | CUSTOMER | AMOUNT | MODE | REMARK |
|---|---|---|---|---|
| *(blank)* | Prem Sir Yog Samiti | 250.00 | — | Esewa |
| *(blank)* | Rara IT Hub | 5,300.00 | — | QR: Om Trade |
| *(blank)* | Sanjeevani College of Medical Sciences | 1,78,098.00 | — | ChequeM Mahalaxmi |
| *(blank)* | Digital Nepal | 36,000.00 | — | Cash Received |
| 2083.04.01 | Aayan Digital | 820.00 | — | Bill payment |

## Main feature: import payments from Excel

1. **Where:** a new section in Settings → Import & export, "Import payments
   received". It works like the other go-live imports: choose a file, see a
   check (nothing saved), correct the columns if needed, then press Import.
   The same import is a management command for the server.
2. **Files and columns:** the shared forgiving reader handles any spreadsheet
   type, several sheets, a title row and loose header names:
   - Date / Miti
   - Customer / Party / Name / Particular
   - Amount / Received / Paid / Credit / Cr
   - Mode / Method / Via
   - Remark / Notes / Narration / Details
   - Reference / Transaction no. / Cheque no.
   - Phone (optional, to tell apart customers with the same name)
3. **Customer matching:** match by name, ignoring case and extra spaces, and by
   phone when given. A name that is not in the system is a **problem row**
   with the closest existing names as suggestions ("Did you mean …?"). It
   never silently creates a duplicate customer.
4. **Dates:** BS or AD in any form the reader knows. A blank date takes the
   date of the row above in the same sheet (merged cells). Undated rows at the
   top use the date chosen in the form ("Date for payments without a date",
   default today), with a note on each such row. Future dates are problems.
5. **Mode:** taken from the Mode column. When that is blank, it is read from
   the remark: Esewa / Khalti / Fonepay / IME / QR mean a wallet, cheque /
   chq mean cheque, bank / transfer / online / IPS mean bank, anything else
   means cash. A word the reader cannot place in the Mode column becomes cash,
   with a note. Imported cheque and bank payments do not need a cheque number
   or bank name; whatever is in the remark or reference is kept.
6. **Recording:** each row becomes a payment with its own receipt number in
   the fiscal year of its date, received "on account" (not against an order).
   The ledger is credited, so the customer's balance goes down. Remarks go into
   the payment's notes.
7. **No double counting:** each row gets a fingerprint (date, customer, amount,
   remark, and its position among identical rows). Uploading the same sheet
   again, or a longer version of it, adds only the new rows.
8. **Skipped quietly:** blank rows, Total / Grand Total lines, and rows with
   zero amount.
9. **Problems:** a negative amount, an unknown customer, an unreadable date or
   amount. Problems stop the import unless "import the good rows, skip the
   rest" is chosen.
10. **Check results:**
    - payments to add, with the total amount, and how much by cash, wallet,
      bank and cheque;
    - a note for every guess (date taken from the row above, mode read from
      the remark);
    - the problem rows, each with its row and sheet.
11. **Who:** owner only (Settings manage). Recorded in the activity log.

## Other features this needs

- **Payments list:** filter by "Imported" and by receipt number range, so
  imported payments can be reviewed after an import.
- **Undo an import:** the owner can void every payment from one import
  (a reason is required), using the existing payment void, so the ledger stays
  append-only.
- **Sample sheet** with Date, Customer, Amount, Mode and Remark columns.
- **Customer statement:** imported payments appear like any other payment,
  with the remark visible.
- **Tests:**
  - the sheet above (blank dates, remark-based modes, Indian digit grouping);
  - a differently laid-out sheet;
  - re-upload adds nothing;
  - an unknown customer with suggestions;
  - another business's customers are never matched.

## Done when

- The OM Traders payment sheet imports with no problems. Each customer's
  balance equals the opening balance minus the imported payments. A second
  upload of the same file adds nothing.
- All backend tests, lint, the API schema check and the frontend checks pass.
- The user guide explains the payment import.
