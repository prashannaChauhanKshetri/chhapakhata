# ChhapaKhata user guide

ChhapaKhata keeps a print shop's daily work in one place: orders and quotations, the production board, bills and payments, every customer's account (khata), stock, reports and backups.

This guide is for the **owner**, the **admin (finance)**, the **front desk** and the **production operators**. Each part says who it is for. You only see the menus your role allows.

| Role | Can do |
|---|---|
| **Owner** | Everything: settings, prices, staff accounts, imports, reports, cancelling bills, backups, activity log |
| **Admin (Finance)** | All the money: customers, orders, bills, payments, cancelling bills and voiding receipts, balances, purchases and stock, every report, staff attendance and salary. Settings, prices, backups and the activity log only where the owner allows; never staff accounts |
| **Front desk** | Customers, orders, quotations, payments, bills, approving designs, delivering, daily sales |
| **Operator** | The production board, recording material used and wastage, their own production log |

---

## 1. Getting started

### 1.1 Opening ChhapaKhata

Open the shop's address in a browser (Chrome, Edge, Safari or Firefox), for example **https://chhapakhata.tech**. It works on computers, tablets and phones.

### 1.2 Signing in

1. Type **your own** username and password, then press **Sign in**.
2. Everything you do is recorded under your name, so never share your login.
3. After **5 wrong passwords**, that username is locked on that device for **15 minutes**.
4. You stay signed in for **12 hours** after your last action.

Forgot your password? Ask the owner to reset it (Settings → Users).

### 1.3 The screen

- **Top bar:** the shop name, today's date in **BS and AD**, the orange **New order** button, and your name.
- **Left menu (☰ on a phone):** Dashboard, Orders, Production, Customers, Invoices, Payments, Ledger, Inventory, Purchases, Insights, Reports, Settings. The current **fiscal year** is shown at the bottom.

### 1.4 Your account menu

Click your name (top right):

| Item | What it does |
|---|---|
| Business name | Shows which shop you are signed in to |
| **Text size** A / A+ / A++ | Makes all text bigger or smaller on this device |
| **Change password** | Enter your current password, then the new one twice |
| **Keyboard shortcuts** | The list in section 11 |
| **Install app on this device** | Adds ChhapaKhata to the phone or computer like an app (section 1.6) |
| **Sign out** | Always sign out on a shared computer |

### 1.5 Dates: BS and AD

Dates are shown in **Bikram Sambat (BS)** first, with the AD date beside it. Bills show both. The fiscal year runs from **1 Shrawan to the end of Asar**. Bill and receipt numbers start again from 1 every fiscal year (IRD practice).

### 1.6 Using it on a phone

- **Android (Chrome):** open the site, sign in, then account menu → **Install app on this device**.
- **iPhone (Safari):** tap **Share** → **Add to Home Screen**.

The app then opens from its own icon, full screen.

### 1.7 When the internet or the server drops

A yellow banner says **"This device is offline"** or **"The shop computer is not answering"**. You can still look at what was on screen before (it shows when it was last saved), but **nothing new can be saved** until the connection is back. The banner disappears by itself.

---

## 2. Setting up the shop (owner, once)

Do these in order before staff start using it.

### 2.1 Shop details: Settings → Shop

| Section | What to fill in |
|---|---|
| Identity | Shop name, tagline, address, phone, email, PAN / VAT number. These are printed on every bill. |
| Tax | **VAT registered** on or off, and the VAT rate (13%) |
| Pricing | **Default minimum sq ft** (small jobs are charged at least this much), **round totals to the rupee**, and the **front desk discount limit** (default 10%) |
| Documents | Logo, **stamp** and **signature** images (printed on bills), invoice footer note, quotation validity days and terms |
| Numbering | Patterns for order, job, invoice, receipt and purchase numbers, for example `INV-{fy}-{n:04d}` |

The stamp and signature are visible only to the owner.

### 2.2 Prices: Settings → Rate card

- **Media** (what you print on): name, **per sq ft** or **per piece**, rate, an optional minimum sq ft, and the stock item it uses (so printing deducts stock).
- **Add-ons:** design, eyelets, framing, lamination, pockets, urgent. Each is charged **fixed**, **per piece**, **per sq ft**, **per running ft** (around the edge) or as a **percent** of the print amount.
- Every price change is kept in the **rate history**.
- Front desk can also ask to add an item while taking an order. The owner sees **Add "…" to the rate card** there.

### 2.3 Staff: Settings → Users

- Add a person with a username, name, **role** and a password of at least 8 characters.
- You can set a personal **discount limit** for a front desk person.
- Accounts are **deactivated, never deleted**, so old records keep the person's name. At least one active owner must remain.
- **Reset password** sets a new password for someone who forgot theirs.

### 2.4 Bringing in your old records

If the shop kept Excel sheets before, import them (section 9) in this order:

1. **Rate card**
2. **Opening stock**
3. **Customers with opening balances** (what each owed when last fiscal year closed)
4. **Payments received** since then
5. The old **work log** (past orders), if wanted

---

## 3. The dashboard

Open it every morning. It shows:

- today's sales and money collected;
- pending dues;
- jobs that are late or due today;
- stock running low;
- the **backup status**. A warning here means the owner should act (section 8.4).

**Insights** (owner) shows how the business is going over a period: sales trends, best customers and items, and a **dues follow-up** list of who to call.

---

## 4. Front desk: orders

### 4.1 Taking an order

1. Click **New order** (or press **N**).
2. **Customer:** type part of the name, phone or PAN and choose from the list.
   - Not there? Choose **Add "name" as a new customer**. Only the name is needed; phone, address and PAN are optional.
3. **Item:**
   - Choose the **Media** (e.g. Star Flex).
   - Enter **Width** and **Height**, pick the unit (**ft, in or cm**) and the **Qty**.
   - The price appears under the item. A yellow **Min. 5 sq ft** badge means it is charged at the minimum size.
   - For **per piece** items (photo prints, name plates, 3D letters) the size is optional; just enter the quantity.
4. **Rate:**
   - For a returning customer, the rate they paid **last time** is filled in.
   - Click **Card Rs …** to use the rate card instead, or type another rate.
   - A rate lower than the rate card by more than your discount limit needs the owner.
5. **Add-ons:** tick design, eyelets, framing and so on. For eyelets, set how many per piece.
6. **More items:** press **Enter** in the last item, or click **Add another item**.
7. **Deliver by:** the date and time promised to the customer. Tick **Urgent job** to put it at the top of the board.
8. **Discount:** in the summary, as % or Rs. Your limit is shown.
9. Click **Confirm order** to start the work, or **Save as quotation** if the customer is still deciding. **Ctrl + S** also saves.

Leaving the page with unsaved changes asks you to confirm first.

### 4.2 Quotations

- Open the quotation → **⋮** → **Print quotation** (A4, with validity and terms).
- When the customer agrees, open it and click **Confirm order**. Each item becomes a job on the production board.

### 4.3 Finding orders

**Orders** lists everything, newest first. Use the tabs (All, Open, Quotations, Ready, Unpaid, Delivered, Cancelled) and the search box (order no., customer, phone or description). Press **/** to jump to search.

Each order shows its **progress bar** (how far the jobs have moved) and what is still due.

### 4.4 Advance payment

On the order, click **Receive payment**, enter the amount and choose the mode:

| Mode | Also enter |
|---|---|
| **Cash** | — |
| **QR / Wallet** | eSewa, Khalti, Fonepay or other QR, and the transaction reference |
| **Bank transfer** | Bank name and reference |
| **Cheque** | Cheque number, bank and cheque date |

Print the **receipt** (3-inch roll or A5) from the confirmation.

### 4.5 Approving the design

On **Production**, when the customer approves the proof, click **Ready for print** on the job card. Operators can start printing only after this.

### 4.6 Delivery and the bill

When the order shows **Ready for collection**, open it and click **Deliver**:

1. Keep **Issue the tax invoice now** ticked.
2. Choose how the customer is paying now, or **Credit (udhar)** to add the balance to their account.
3. Click **Mark delivered**, then print the invoice: **3-inch**, **A5** or **A4**.

### 4.7 Bills (Invoices)

- All bills are under **Invoices**. Printing a bill again marks it **"Copy of original"** with the copy number.
- A wrong bill is never deleted. The **owner cancels it** with a reason; it stays on record, marked cancelled, and the customer's account is corrected.
- An order with a bill cannot be edited. Cancel the bill first (owner).

### 4.8 Money towards old dues

Customers → open the customer → **Receive payment**, and leave **For order** empty. It is credited to their account.

---

## 5. Customers and their accounts (khata)

### 5.1 A customer's page

- **Balance due:** what they owe now. **Dr** means the customer owes the shop; **Cr** means the shop holds an advance.
- **Orders** tab: their orders and what is unpaid.
- **Statement** tab: pick a **Period** (this month, this fiscal year, all time, or your own dates). It shows the **opening balance**, every bill (Dr) and payment (Cr) with a running balance, and the **closing balance**. Then **Print statement** or **Excel**.
- **Their usual rates:** the last rate they paid for each item, used when taking their next order.

### 5.2 Opening balance from last year (owner)

What a customer owed the shop (or had paid in advance) when the last fiscal year closed is their **opening balance**.

1. Open the customer → **Opening balance**.
2. Choose **Customer owes us (Dr)** or **Advance with us (Cr)** and enter the amount.
3. The date is filled in as the last day of the previous fiscal year (end of Asar). This year's statements then start from it instead of showing it as a new charge.
4. **Save opening balance**.

**Correcting it:** press **Opening balance** again, enter the right amount and write the reason (for example "the old khata showed 4,200"). The old figure is never erased: a correction is added on the same date and listed under **Changes** with your name.

You can also enter it when adding a customer ("Balance from last year"), or import it for many customers at once (section 9.5).

### 5.3 Adjust balance (owner)

For something that happened **this year** and is not a bill or payment, such as a write-off or a missed charge: customer → **Adjust balance**. A positive amount increases what they owe; a negative one reduces it. A reason is required.

### 5.4 All customers at once: Ledger

- **Customer balances:** every customer's opening, billed, received and closing balance for a period, with totals. Sort by any column; search by name or phone; show only those with dues or advances. **Print** or **Excel** lists everyone.
- **Day book:** every ledger entry in date order.

---

## 6. Production (operators)

1. Open **Production**. Each column is a stage:
   - Design pending / Proof sent
   - Ready for print
   - Printing
   - Finishing / Framing
   - Ready for collection

   A **red** edge means overdue and **amber** means due today. On a phone, tap a stage name at the top.

2. **Move a job** by dragging its card to another column (on a touch screen, press and hold first), or use the buttons on the card. Columns you may move it to get a dashed outline. Moved it by mistake? Click **Undo** in the message that appears.
3. **My jobs** shows only the jobs given to you.
4. Click **Printing** when you start a job.
5. When printing is done, click **Finishing** (or **Ready** if there is no finishing). A window asks for the **roll used** and the **sq ft used** (already filled in), plus any **wastage** such as test prints or misprints. Save; the stock goes down automatically.
6. Click **Ready** when the job is finished and packed.
7. Click the job number for details, to print the **job ticket** (A5), or to record more material for a reprint.

**Who may move what:**

- Front desk moves jobs to Design, Ready for print and Delivered.
- Operators move them to Printing, Finishing and Ready for collection, and only after **Ready for print**.
- Leaving **Printing** needs the roll and sq ft used for media that is tracked in stock (the owner may skip this).
- **Delivered** comes only after Ready for collection. Only the owner can reopen a delivered job.

---

## 7. Stock and purchases

### 7.1 Inventory

- Every stock item with what is **on hand**. Items below their **low-stock level** are highlighted, and also appear on the dashboard.
- **Roll media** (flex, vinyl) is tracked **roll by roll**: width, length, sq ft left and status.
- Open an item → **Record**:
  - **Usage:** ink, eyelets or frame material used.
  - **Wastage:** misprints and offcuts, with a reason.
  - **Adjust after count** (owner): after a physical count, enter what is really there.
- **Rolls → Mark finished** (owner) writes off the last bit of a roll.
- Every change is kept in the item's **movement history**.

### 7.2 Purchases (owner)

**Purchases → Record purchase**:

1. Choose the supplier (or add one) and the bill date and number.
2. Add each item with its quantity and amount. For rolls, give the number of rolls and each roll's width and length; the rolls are created for you.
3. Save. Stock goes up immediately, and the purchase is kept in the list.

---

## 8. Owner tools

### 8.1 Reports

| Report | Shows |
|---|---|
| **Daily sales** | One day's bills and collections (front desk can see this too) |
| **Sales summary** | Sales over a period |
| **Pending dues** | Who owes what, oldest first |
| **Collection report** | Money received over a period, by mode |
| **Material consumption vs sales** | Material used compared with what was sold |
| **Operator production log** | What each operator printed (operators see their own) |
| **Stock report** | Every item and what is left |

Choose a period (this BS month, last 7 or 30 days, this or last fiscal year, or your own dates). Then **Print / PDF** or **Excel**.

### 8.2 Insights

Sales trends, best customers and items, and the **dues follow-up** list, for any period.

### 8.3 Activity log

Settings → **Activity log**: who did what and when, including sign-ins, prices changed, bills cancelled, payments voided, imports and data deleted. Filter by date, person or action.

### 8.4 Backups and export

Settings → **Backups & export**:

- **Automatic backup every night at 9 pm**: 14 daily, 8 weekly and 12 monthly copies are kept. The list shows each backup with its size and whether the online copy worked.
- **Back up now** makes one immediately. Do it before anything big.
- **Download Excel export:** every table as one Excel file. The data always belongs to you.

### 8.5 Correcting, cancelling and voiding

- **Correct a payment entered wrongly** (wrong amount, customer, date, mode, reference or note):
  1. Payments → **⋮** → **Correct payment…**. The form opens filled in from that payment.
  2. Change what was wrong and write **What was wrong?** (for example "typed 1,500, it was 1,000").
  3. Press **Save correction**.

  The wrong receipt is kept on record as **Void** ("Corrected by RCT-…"), and a corrected receipt with a new number is saved. The change is applied on the original date, so that month's statement is right too. Balances update straight away.

- **Void a payment** that should not exist at all (a bounced cheque, a double entry): Payments → **⋮** → **Void payment**, with a reason. It stays on record, and the customer's balance goes back up.
- **Cancel a bill:** Invoice → **Cancel invoice**, with a reason. It stays on record, marked cancelled.

Only the owner can correct, void or cancel. Nothing is ever deleted, so the activity log and statements always show what happened.

### 8.6 Starting again with an empty shop

For test entries, or to enter everything again from the start: Settings → **Backups & export** → **Delete all data…**

- **Deleted:** customers, orders, jobs, bills, payments, the ledger, purchases, suppliers and stock. The rate card is deleted too, unless you tick **Keep the rate card and the stock item list** (stock quantities then go to zero).
- **Kept:** staff logins, shop settings and the activity log.
- Bill and receipt numbers start again from 1.
- Type **Confirm**, then press **Delete all data**.
- **A full backup is taken first**; if it fails, nothing is deleted. Only the owner sees this option.

---

## 9. Importing your Excel sheets (owner)

Settings → **Import & export**. There are five imports, and they all work the same way.

### 9.1 How every import works

1. Choose the file. It is **checked first; nothing is saved yet**.
2. Read the result:
   - **Ready: N to add** and the totals;
   - **Columns found:** which of your columns holds what;
   - **Notes:** what was guessed, for example "No date; used the date from the row above";
   - **Problems:** rows that cannot be read, with the sheet and row number.
3. A column read wrongly? Press **Change columns** and choose what each column holds, or **Not used**. Then check again.
4. Press **Import**. If some rows have problems, fix them in Excel and upload again, or press **Import N good rows, skip M** to bring in the rest.
5. **Uploading the same sheet again only adds what is new.** Dues, payments and stock are never counted twice.

**Sample sheet** downloads an example layout for each import.

### 9.2 Money is never counted twice

The imports and the app check for these mistakes for you:

| Situation | What happens |
|---|---|
| The same sheet (or a longer version) is uploaded again | Rows already imported are skipped |
| A payment is in the work log **and** in the payments sheet | Recorded once; the note says "already recorded as RCT-…" |
| A customer's payments on one day are **split differently** in the two files (500 + 450 in one, 950 in the other) | The day's totals match, so it is recorded once; the note says "split differently" |
| Work or a payment dated **on or before a customer's opening balance** (end of last year) | Left out, because the opening balance already includes it; the note says so |
| A work-log row was **changed in Excel** after it was imported | Shown as a problem, not added as a second order |
| A payments-sheet row was changed after it was imported | A note points to **Correct payment** on the old receipt |
| An order from the work log | Cannot be billed again (it is already on the customer's account) |
| **Save payment** pressed twice, or saved again on a slow connection | Asks "Save a second payment?" before saving it |
| The same adjustment saved twice in a moment | Refused |
| A customer made by the work log appears in the customers sheet with a phone | Matched as the same customer, and the phone is filled in |

**What still needs your eye:** a payment is "the same" only when the customer and date match, and the amount (or that day's total) matches. A payment entered with a different date, split into two rows, or under a misspelled name cannot be matched automatically. After importing, read the notes and look at the statements of your biggest customers. Fix any odd one with **Correct payment** or **Void payment**.

### 9.3 What your sheet can look like

You do not need a special layout:

- **Any spreadsheet file:** Excel (.xlsx, .xls, .xlsm, .xlsb, templates), LibreOffice or Google Sheets (.ods), CSV or TSV. A web page saved as .xls works too.
- **One sheet or many:** a workbook with one sheet per month is read sheet by sheet. Hidden sheets are left out.
- **Your own column names, in any order:**
  - "Particular", "Customer's Name" and "Party Name" all mean the customer.
  - "Rate (Rs.)", "Qty.", "Miti" and Nepali headings such as **मिति** work too.
  - A title row above the headings is fine, and so are headings over two rows.
- **Numbers as you write them:** "Rs. 1,20,000/-", "1,78,098.00", "2 pcs", "35/sqft" and Nepali digits (१२००). A dash (—) or "N/A" means empty.
- **Dates in BS or AD:** 2083.04.01, 01/04/2083, 1 Shrawan 2083, 17/07/2026, 17 Jul 2026, Nepali digits, and Excel date cells. A BS date that Excel turned into a date is also read correctly.
- **Gaps from merged cells:** a missing date or customer is taken from the row above. "Total" and "Grand Total" lines are skipped.

### 9.4 The work log (past orders)

The sheet the shop kept before, one row per job: Date, Particular (customer), Address, Items, Height, Width, Qty, SQFT, Rate, Amount, Details, Payment, Payment mode, Discount, Balance. A **Size** column like "12x4" also works.

- Rows with the **same date and customer** become one delivered order.
- What was charged goes to the customer's account, and **Payment** becomes a receipt.
- **New customers and items are created.** Items keep the rate from the sheet; check them in the rate card afterwards.
- Each customer's **last rates** are remembered for their next order.
- **Export** does the reverse: orders for any period in the same Excel layout.

### 9.5 Customers and opening balances

A list of customers with what each owed (or had paid in advance) when last fiscal year closed:

| Name | Phone | Address | PAN | Opening balance |
|---|---|---|---|---|

- **The balance can be given in several ways:**
  - one column (negative means an advance);
  - separate **Dr** and **Cr** columns;
  - a **Dr/Cr** marker column.
- **Phones:** two numbers in one cell ("98… / 98…") become the phone and the second phone.
- **PAN:** a PAN that is not 9 digits is left out, with a note.
- **Balances as on:** the date of the balances, filled in as last year's closing day.
- **Duplicates:** a customer already in the system is not added twice.
- **Corrections:** uploading a corrected sheet changes their opening balance to the new figure, with the file name as the reason.

### 9.6 Payments received

Payments customers made after the opening balances, all at once:

| Date | Customer | Amount | Mode | Remark |
|---|---|---|---|---|

- **Mode:** if the Mode column is empty (or shows "—"), the **remark** tells how it was paid:
  - "eSewa", "Khalti", "Fonepay" or "QR" means a wallet;
  - "cheque" means a cheque;
  - "bank", "online" or "IPS" means a bank transfer;
  - anything else means cash.
- **Dates:** rows **without a date at the top** use **Date for undated rows** from the form (today, unless you change it). A blank date further down takes the date of the row above.
- **What it records:** each payment becomes a receipt on the customer's account and lowers their balance. The remark is kept with the payment.
- **Names must match customers already in the system.** A misspelled name is shown as a problem with the closest names ("Did you mean …?"), and no extra customer is created. If two customers share a name, add a Phone column.
- **Never counted twice:** a payment already recorded with its order (on the order slip, or in the work log's Payment column) for the same customer, day and amount is skipped, with the note "already recorded as RCT-…". The work log import does the same for payments that came from a payments sheet.
- **Duplicates from before:** if payments were recorded twice by an earlier import, Import & export shows a red box "N payments are recorded twice", with examples. Press **Void the duplicates…** and type **Confirm**. The copies from the sheet are voided (kept on record as "Duplicate of RCT-…"), balances are corrected, and a backup is taken first.

### 9.7 Rate card

Name, rate and unit, for media and add-ons:

- **Unit:** write sq ft or piece in its own column, or next to the rate ("60/pc", "35/sqft").
- **Media or add-on:** a "Kind" column, or an add-on **basis** (per piece, per sq ft, running ft, %, fixed), marks a row as an add-on.
- **Updates:** items with the same name are updated, so you can upload the sheet again when prices change.

### 9.8 Opening stock

Stock on hand on the day you start:

- **Rolls:** width and length in feet, and how many identical rolls ("Rolls"). For a part-used roll, give the **sq ft left**.
- **Other items:** a quantity and unit (litre, box, pcs, running ft).
- **Kind:** if there is no Kind column, it is guessed from the name (ink, eyelets, frame, standee).
- **Duplicates:** an item that already has opening stock is skipped, so uploading twice does not double it.

---

## 10. Printing

| Document | Sizes | From |
|---|---|---|
| Tax invoice / invoice | 3-inch roll, A5, A4 | Invoice → Print, or after Deliver |
| Payment receipt | 3-inch roll, A5 | After receiving a payment, or Payments |
| Quotation | A4 | Order → ⋮ → Print quotation |
| Job ticket | A5 | Job → Print ticket, or all tickets from the order |
| Customer statement | A4 | Customer → Statement → Print |
| Reports | A4 | Report → Print / PDF |

Bills show both dates (BS and AD), the buyer's PAN, the amount in words, and the stamp and signature if set. Signatures sit at the bottom of the page.

---

## 11. Keyboard shortcuts

| Keys | Action |
|---|---|
| **/** | Jump to the search box on the page |
| **N** | Start a new order |
| **Ctrl + S** (⌘ + S on Mac) | Save the order |
| **Enter** | In the last item of an order: add another item |
| **Esc** | Close a window or menu |
| **?** | Show the list of shortcuts |

Single-key shortcuts work when you are not typing in a box.

---

## 12. When something goes wrong

| Problem | What to do |
|---|---|
| "This device is offline" | Check the Wi-Fi or mobile data. The banner goes away when the connection is back. |
| "The shop computer is not answering" | The server is restarting or down. Wait 2 minutes; if it continues, call the developer. |
| Locked out after wrong passwords | Wait 15 minutes, or ask the owner to reset your password. |
| Price looks wrong | Check the size units (inches or feet), the media chosen and the rate card. |
| "Roll has only … sq ft left" | Choose another roll; the owner adjusts the stock after counting. |
| Cannot edit an order | It has a bill. The owner must cancel the bill first. |
| A payment was entered wrongly (amount, customer, date, mode) | Owner: Payments → ⋮ → **Correct payment…**, change it and write what was wrong. |
| Opening balance is wrong | Owner: customer → Opening balance → enter the right figure with a reason. |
| A payment shows twice on a statement (with the order and "on account") | Owner: Settings → Import & export → **Void the duplicates…**, type **Confirm**. |
| An import shows problems | Read the row numbers listed, fix those rows in Excel and upload again. Rows already imported are not added twice. |
| A column is read wrongly in an import | Press **Change columns** and choose what each column holds. |
| Backup warning on the dashboard | Owner: Settings → Backups & export → **Back up now**. If it fails, call the developer. |
| Text is too small | Account menu → Text size → A+ or A++. |

---

## 13. Words used in ChhapaKhata

| Word | Meaning |
|---|---|
| **Dr** | Debit: the customer owes the shop |
| **Cr** | Credit: the shop holds the customer's advance |
| **Opening balance** | What a customer owed (or had in advance) when the last fiscal year closed |
| **Closing balance** | What they owe at the end of the chosen period |
| **Udhar / credit** | Work delivered but not yet paid, added to the customer's account |
| **Advance** | Money taken before the work is done or billed |
| **Quotation** | A price offered; it becomes an order when confirmed |
| **Job** | One item of an order, moving through the production stages |
| **Rate card** | The shop's price list |
| **Add-on** | An extra charge on an item: design, eyelets, framing, lamination |
| **Fiscal year (FY)** | 1 Shrawan to the end of Asar, for example 2083/84 |
| **BS / AD** | Bikram Sambat (Nepali) and Gregorian dates |
| **Void / cancel** | Marking a payment or bill as wrong; it stays on record with a reason |
