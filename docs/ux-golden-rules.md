# Interface review: Shneiderman's Eight Golden Rules

Reviewed 17 October 2026 against the whole frontend. Each rule lists how ChhapaKhata meets it and what this review changed.

| # | Rule | How the app meets it | Changed in this review |
|---|---|---|---|
| 1 | **Strive for consistency** | One page layout (`PageHeader`, `SectionCard`), one table component, one money format (`Rs. 1,25,000.00`, Dr/Cr for balances), BS + AD dates everywhere, the same status badges and colours on every screen | Toasts now use the same position and width on every phone; counted messages use the singular for one ("1 invoice") |
| 2 | **Seek universal usability** | Desktop-first with phone layouts (board tabs, stacked forms), touch-friendly sizes, keyboard use, screen-reader labels, plain-English messages ready for Nepali | Keyboard shortcuts for frequent users: `/` search, `N` new order, `?` shortcut list (plus Ctrl/⌘+S and Enter in the order form); installable app on phones |
| 3 | **Offer informative feedback** | Live price on every keystroke, loading skeletons, success toasts naming the record ("ORD-00042 confirmed"), banners for low stock, overdue jobs and backups | Background refresh failures now say "Could not refresh, what you see may be out of date"; the offline banner says whether the device or the shop computer is the problem and when data was last saved |
| 4 | **Design dialogs to yield closure** | Each flow ends on a clear result: order saved → order page; delivery → "Fully paid. Thank you!" and the invoice; import → summary with links to balances and orders | — |
| 5 | **Prevent errors** | Server-side pricing, field validation, role-based actions (buttons a user cannot use are hidden), discount and custom-rate limits, stock that cannot go negative, invoice numbers that cannot repeat, a dry-run before any import | Leaving a half-entered order (link, back button, closing the tab) now asks first; saving while offline is refused before anything is sent |
| 6 | **Permit easy reversal of actions** | Orders stay editable until invoiced; invoices are cancelled (never deleted) and the order can be re-invoiced; payments can be voided; stock is corrected with reversing entries | Moving a job on the board shows **Undo** for 6 seconds |
| 7 | **Keep users in control** | Nothing changes without a click: new versions wait for "Reload now", deliveries ask how the customer pays, the board refreshes without moving what the user is touching | — |
| 8 | **Reduce short-term memory load** | The customer's balance and last rate appear as soon as they are chosen, totals stay visible while entering items, each job card carries customer, size and deadline, statements carry opening and closing balances | The front-desk home lists **dues to follow up** (oldest first, with phone numbers) |

## How to check a new screen

Before merging a screen, walk the list above: same components and formats (1), works at 390 px and by keyboard (2), says what happened (3), ends somewhere obvious (4), blocks the likely mistake (5), can be undone or corrected (6), never acts on its own (7), shows the facts the user would otherwise have to remember (8).
