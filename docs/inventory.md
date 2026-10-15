# Inventory

## Items and rolls

- **Roll media** (Star Flex, Normal Flex, Vinyl, Backlit, Sticker…) is tracked **per roll** in sq ft. Each roll gets a code (`R-0001`) with width, length, total and remaining sq ft.
- **Other items** (ink in litres, eyelets in boxes, frame material in running ft, standees and others in pieces) are tracked by quantity.
- Each item has a **low-stock level**; the dashboard lists items below it. For roll media the level applies to the total across all rolls.

## How stock changes

Every change is a row in the append-only stock ledger with who, when, why, and the balance after. Balances on items and rolls are kept in step under row locks, so two people recording usage at the same time can't overdraw a roll.

| Event | Who | Effect |
|---|---|---|
| Opening stock (go-live) | Owner | Adds quantity or part-used rolls |
| Purchase | Owner | Adds stock; roll lines create one roll each (`count × width × length`) |
| Job material (leaving Printing) | Operator / owner | Deducts sq ft used from the chosen roll; optional wastage |
| Usage | Operator / owner | Deducts ink, eyelets, frame material… |
| Wastage | Operator / owner | Misprints, test prints, trimming (reason required) |
| Adjustment after count | Owner | Sets a roll or item to the counted quantity (reason required) |
| Mark roll finished | Owner | Writes off the leftover as wastage and closes the roll |

A deduction that would take a roll below zero is refused with a clear message; the owner fixes the count with an adjustment. When the print's shorter side is wider than the chosen roll, a warning is shown (it can still be saved, e.g. for tiled prints).

## Material vs sales

The report compares, per material and period: sq ft **billed** (including minimum charges), sq ft **printed** (actual size), sq ft **used** from rolls, and **wastage**. A large "used − printed" difference points to unrecorded reprints or wastage; a negative one usually means jobs moved past Printing without recording material.
