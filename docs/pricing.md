# Pricing rules

Implemented in `backend/apps/catalog/pricing.py` (pure functions, unit-tested in `catalog/tests/test_pricing.py`). The order screen asks the server for every price, so the screen and the bill can never disagree.

## Per item

```
sq ft per piece  = width × height ÷ unit²        (in: ÷144, cm: ÷929.0304, ft: ÷1)   → 2 decimals
billable sq ft   = max(sq ft per piece, minimum sq ft)
print amount     = billable sq ft × rate × quantity
add-ons          = see table
line total       = print amount + add-ons
```

The minimum applies **per piece**: three 2 × 2 ft stickers (4 sq ft each) with a 5 sq ft minimum bill 15 sq ft.

| Add-on basis | Amount | Example |
|---|---|---|
| Fixed | rate × quantity (once per line) | Design: Rs 500 |
| Per piece | rate × units per piece × pieces | Eyelets: 8 × Rs 5 × 3 banners = Rs 120 |
| Per sq ft | rate × actual sq ft × pieces | Lamination: Rs 15 × 40 sq ft |
| Per running ft | rate × perimeter × pieces | Framing 10 × 4 ft: 28 ft × Rs 60 |
| Percent | rate % of the print amount | Urgent: 20 % |

## Per order

```
sub-total  = Σ line totals
discount   = percent of sub-total, or a fixed amount (never above sub-total)
taxable    = sub-total − discount
VAT        = taxable × 13 %                (only when the shop is VAT-registered)
total      = taxable + VAT (+ optional round-off to the nearest rupee)
```

All money is rounded half-up to two decimals at each step.

## Worked example

Order: 3 stickers 2 × 2 ft at Rs 35/sq ft with 4 eyelets each, 5 % discount, VAT-registered shop.

| Step | Value |
|---|---|
| sq ft per piece | 4.00 → billable 5.00 (minimum) |
| print amount | 5 × 35 × 3 = 525.00 |
| eyelets | 4 × 5 × 3 = 60.00 |
| sub-total | 585.00 |
| discount 5 % | 29.25 |
| taxable | 555.75 |
| VAT 13 % | 72.25 (72.2475 rounded) |
| **total** | **628.00** |

## Rate changes

Each order line stores the rate and minimum it was priced with. Editing an order keeps those for unchanged lines; new lines (or lines whose media changed) use today's rate card. Rate history is visible in Settings → Rate card → Rate history.

## Settings to confirm with the shop

Default minimum sq ft (5), front-desk discount limit (10 %), VAT registration, and whether to round totals to the rupee.
