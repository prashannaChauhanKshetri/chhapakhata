# Billing, ledger and tax

## Invoices

- Issued for a confirmed order (never a quotation); one **issued** invoice per order, enforced by a database constraint.
- Number pattern (default) `INV-{fy}-{n:04d}`, e.g. `INV-2083/84-0001`. The counter restarts on **1 Shrawan** each fiscal year and never reuses or skips a number (allocated under a row lock inside the issuing transaction).
- Dated today, with the **Miti (BS)** and AD date printed. Buyer name, address, phone and PAN are **snapshotted**; later customer edits do not change the invoice.
- Title is "Tax Invoice" when the shop is VAT-registered, otherwise "Invoice". VAT 13 % on the taxable amount.
- Amount in words uses lakh and crore ("Rupees One Lakh Twenty-Five Thousand Only").
- **Never deleted.** The owner cancels with a reason: the number stays used, the document prints with a CANCELLED mark, and the ledger is reversed. The order can then be edited and invoiced again under a new number.
- **Reprints:** every print is counted. Prints after the first show "Copy of original – n".
- Formats: A4, A5 and 80 mm (3-inch thermal, cut to the content height).

## Payments

Modes: cash; bank transfer (bank, reference); cheque (number, bank, date); QR wallets (eSewa, Khalti, Fonepay, other QR, with transaction reference). "Credit (udhar)" means nothing is received now and the amount stays due. A payment against an order before its invoice is marked **advance**. Payments can't be future-dated. Mistakes and bounced cheques are **voided** by the owner with a reason.

Receipts are numbered per fiscal year (`RCT-2083/84-0001`) and print as A5 or 3-inch.

## Customer ledger

Append-only entries: opening balance, invoice (debit), invoice cancelled (credit), work imported from the old Excel log (debit, no invoice), payment (credit), payment voided (debit), owner adjustment. **Balance = Σdebit − Σcredit**; positive (**Dr**) means the customer owes, negative (**Cr**) is an advance held.

Where to see it:

- **Customer → Statement:** a period picker in the Nepali calendar (this BS month, last month, this or last fiscal year, all time, custom dates). It shows the opening balance (brought forward), billed (Dr), received (Cr) and closing balance (carried forward), with a running Dr/Cr balance, totals by entry type and the age of what is still due. References link to the invoice or order. Print (PDF) or Excel.
- **Ledger → Customer balances:** every customer's opening, billed, received and closing balance for a period, with filters for due, advance or settled, the last payment date, and totals (receivable and advances held). Print or Excel. API: `GET /api/v1/ledger/summary/`.
- **Ledger → Day book:** every ledger entry for all customers, newest first, filterable by period, type and customer. API: `GET /api/v1/ledger/`.

Work that is confirmed but not yet invoiced is not in the ledger. The customer page shows it separately ("Plus Rs … on orders not yet invoiced"). The deliver dialog issues the invoice by default, so delivered work is always billed.

Pending dues are aged first-in-first-out: payments clear the oldest debits first, then the remainder is bucketed into 0–30, 31–60, 61–90 and 90+ days.

## Imported work log

The shop's old Excel work log can be imported (Settings → Import & export). Imported rows become delivered orders marked **Imported**. Each order is charged to the ledger as "Work (imported)" **without an invoice**, so no invoice numbers are used and the invoice sequence stays unbroken. The Payment column becomes receipts dated that day. Invoice-based reports (VAT, invoiced sales) therefore exclude imported history, while collections and dues include it.

## IRD notes (confirm with the client's auditor)

The design follows common IRD billing-software practice: no deletion of issued invoices, cancellation with reason, sequential numbers per fiscal year, "Copy of original" with count on reprints, BS and AD dates, and a per-user activity log.

What is **not** included: IRD approval of the software and real-time sync to the Central Billing Monitoring System (CBMS). Businesses above the IRD turnover threshold may need both (proposal §4.2 lists CBMS as a paid add-on). Until the auditor confirms, the shop may keep its approved invoice book for tax invoices and use the system for orders, production, stock and dues.
