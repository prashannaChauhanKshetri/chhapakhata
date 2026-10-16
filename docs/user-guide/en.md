# ChhapaKhata user guide

For the owner, front desk and production staff of OM Traders and Suppliers.

## Signing in

Open the shop address (for example `https://chhapakhata.local`) on any computer or phone in the shop. Sign in with **your own** username and password: everything you do is recorded under your name. Forgot your password? Ask the owner to reset it. After 5 wrong tries, wait 15 minutes.

Change your password any time: click your name (top right) → **Change password**.

## Front desk

### Take an order

1. Click **New order** (top bar).
2. **Customer:** type part of the name, phone or PAN. New customer? Click the **+** button next to the box.
3. **Item:** choose the **Media** (e.g. Star Flex), enter **Width** and **Height**, pick the unit (ft, in or cm) and the **Qty**. The price appears under the item. A yellow **Min. 5 sq ft** badge means the item is small and is charged at the minimum. For items sold **per piece** (photos, name plates, 3D letters) the size is optional; just enter the quantity.
4. **Rate:** for a returning customer, the rate they paid last time is filled in (**Last time Rs …**). Click **Card Rs …** to use the rate card instead, or type a new rate. A rate below the rate card by more than your discount limit needs the owner.
5. **Add-ons:** design, eyelets, framing, lamination, pockets, urgent. For eyelets, set how many per piece.
6. More items? Press **Enter** on the last item or click **Add another item**.
7. **Deliver by:** the promised date and time. Tick **Urgent job** to put it first on the board.
8. **Discount:** choose % or Rs in the summary. Your limit is shown; larger discounts need the owner.
9. Click **Confirm order** (work starts) or **Save as quotation** (customer is deciding). **Ctrl + S** also saves.

### Quotations

Open the order → **⋮** → **Print quotation**. When the customer agrees, click **Confirm order**. Each item becomes a job on the production board.

### Advance payment

On the order, click **Receive payment**. Enter the amount and mode:
- **Cash**
- **QR / Wallet:** choose eSewa, Khalti, Fonepay or other QR, and type the transaction reference
- **Bank transfer:** bank name and reference
- **Cheque:** cheque number, bank and cheque date

Print the receipt (3-inch or A5) from the confirmation.

### Approve the design

On the **Production** board, when the customer approves the proof, click **Ready for print** on the job card. Operators can only start printing after this.

### Deliver and collect payment

When the order shows **Ready for collection**, open it and click **Deliver**:
1. Keep **Issue the tax invoice now** ticked.
2. Choose how the customer pays now, or **Credit (udhar)** to add the balance to their dues.
3. Click **Mark delivered**, then print the invoice (3-inch, A5 or A4).

### Invoices

- Find invoices under **Invoices**. Printing again marks the copy **"Copy of original"**.
- A wrong invoice can only be **cancelled by the owner**, with a reason. It is never deleted.

### Customer dues

Open a customer to see the **balance** and the **Statement** tab. Pick a **Period** (this month, this fiscal year, all time or custom dates). The statement shows the opening balance, what was billed (Dr) and received (Cr), and the closing balance. **Dr** means the customer owes the shop; **Cr** means the shop holds an advance. Then **Print statement** or **Excel**. All customers at once: **Ledger** → **Customer balances** (or **Day book** for every entry). Payments towards old dues: **Receive payment** and leave **For order** empty.

## Production operators

1. Open **Production**. Columns show each stage; red edge = overdue, amber edge = due today. On a phone, tap a stage at the top.
   **Drag a card** to another column to move it (on a touch screen, press and hold first). Columns you may drop into get a dashed outline; others fade out. The buttons on each card still work.
2. Tap **My jobs** to see the jobs assigned to you.
3. Click **Printing** on a card when you start.
4. When printing is done click **Finishing** (or **Ready** if no finishing is needed). A window asks for the **roll used** and the **sq ft used**, already filled in, plus any **wastage** (test prints, misprints). Save. Stock is deducted automatically.
5. Click **Ready** when the job is finished and packed.
6. Click the job number to see details, print the **job ticket**, or record more material for a reprint.
7. Ink, eyelets or frame material used: **Inventory** → item → **Record** → **Usage**. Misprints: **Record** → **Wastage**.

## Owner

| Task | Where |
|---|---|
| Shop name, PAN/VAT, VAT on/off, logo, stamp, signature, invoice note | Settings → Shop |
| Rates, minimum sq ft, add-ons (with rate history) | Settings → Rate card |
| Staff accounts, roles, discount limits, password resets | Settings → Users |
| Import the old Excel work log; export orders in the same layout | Settings → Import & export (or Orders → Excel import / export) |
| Backups, online copy status, Excel export of all data | Settings → Backups & export |
| Who did what | Settings → Activity log |
| Record a purchase from a supplier | Purchases → Record purchase |
| Correct stock after a physical count | Inventory → item → Adjust after count |
| Finish a roll (write off the end) | Inventory → item → Rolls → Mark finished |
| Cancel an invoice / void a payment | Invoice → Cancel invoice / Payments → ⋮ → Void |
| Correct a customer's balance | Customer → Adjust balance |
| Reports (sales, dues, collections, material, operators, stock) | Reports |

Every morning, glance at the dashboard: today's sales and collection, pending dues, late jobs, low stock, and the **backup** status.

## When something goes wrong

| Problem | What to do |
|---|---|
| "This device is offline" banner | Check Wi-Fi/cable; the shop computer must be on |
| "Cannot reach the server" | The shop computer or Docker is off. Turn it on and wait 2 minutes |
| Price looks wrong | Check width/height units (in vs ft) and the media selected; check the rate card |
| "Roll has only … sq ft left" | Choose another roll; ask the owner to adjust after counting |
| Can't edit an order | It has an invoice. The owner must cancel the invoice first |
| Backup warning on the dashboard | Owner: Settings → Backups → Back up now; call the developer if it fails |
