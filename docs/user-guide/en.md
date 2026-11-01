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
| Import the old Excel work log, customers with their opening balances, the rate card or opening stock; export orders in the work-log layout | Settings → Import & export (or Orders → Excel import / export) |
| Backups, online copy status, Excel export of all data | Settings → Backups & export |
| Who did what | Settings → Activity log |
| Record a purchase from a supplier | Purchases → Record purchase |
| Correct stock after a physical count | Inventory → item → Adjust after count |
| Finish a roll (write off the end) | Inventory → item → Rolls → Mark finished |
| Cancel an invoice / void a payment | Invoice → Cancel invoice / Payments → ⋮ → Void |
| Set or correct what a customer owed from last year (opening balance) | Customer → Opening balance |
| Correct a customer's balance for something that happened this year | Customer → Adjust balance |
| Reports (sales, dues, collections, material, operators, stock) | Reports |

### Opening balance from last year

What a customer owed the shop (or had paid in advance) when the last fiscal year closed is their **opening balance**. Open the customer and press **Opening balance**. Choose **Customer owes us (Dr)** or **Advance with us (Cr)** and enter the amount. The date is filled in as the last day of the previous fiscal year (end of Asar), so this year's statements open with it instead of showing it as a new charge.

If the figure was wrong, press **Opening balance** again and enter the right amount with a reason, for example "the old khata showed 4,200". The ledger is never edited: a correction is added on the same date and listed under **Changes** with your name, so the earlier figure is still visible. Uploading a corrected customer sheet in Settings → Import & export fixes opening balances the same way.

Use **Adjust balance** only for something that happened this year, such as a write-off or a missed charge.

### Importing your own sheets

Settings → **Import & export** takes the sheets the shop already keeps: the work log, a customer list with dues and advances, the rate card and opening stock. Your sheet does not need a special layout:

- **Any spreadsheet file:** Excel (.xlsx, .xls, .xlsm, .xlsb), LibreOffice or Google Sheets (.ods) and CSV. A workbook with one sheet per month is read sheet by sheet.
- **Any column names, in any order:** "Particular", "Customer's Name" or "Party Name" all mean the customer, and Nepali headings like मिति work too. A title row above the headings is fine.
- **Numbers and dates as you write them:** amounts like "Rs. 1,200/-", sizes like "12x4", and BS or AD dates (2083.04.01, 1 Shrawan 2083, 17/07/2026, Nepali digits).
- **Gaps from merged cells:** a missing date or customer is taken from the row above, and "Total" lines are left out.

Choose the file and it is **checked first**; nothing is saved yet. You see what will be added, plus **notes** (what was guessed) and **problems** (rows that cannot be read, with the row number). If a column was read wrongly, press **Change columns** and pick what each column holds. Then press **Import**. Uploading the same sheet again only adds what is new, so dues and stock are never counted twice. **Sample sheet** downloads an example layout.

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
