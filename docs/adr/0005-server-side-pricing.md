# 0005: Prices are calculated only on the server

**Status:** accepted · 2026-10-15

**Context.** Pricing rules (unit conversion, minimum sq ft per piece, five add-on bases, discount limits, VAT, rounding) must match the bill exactly.

**Decision.** A pure-function engine (`apps/catalog/pricing.py`) is the only calculator. The order form calls `POST orders/price-preview/` (debounced) for live totals; saving recalculates on the server.

**Consequences.** No duplicated logic in TypeScript; on a LAN the round trip is instant. Rates are snapshotted on order lines so later rate changes never alter past orders.
