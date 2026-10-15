# 0004: Append-only stock and customer ledgers

**Status:** accepted · 2026-10-15

**Context.** Stock and money must be traceable; IRD practice forbids deleting issued invoices.

**Decision.** `StockMovement` and `LedgerEntry` rows cannot be edited or deleted (enforced in the models and read-only in the admin). Corrections are new rows (adjustment, reversal, void, cancel) with a reason. Cached balances (`on_hand`, `remaining_sqft`) are updated in the same transaction under row locks.

**Consequences.** Full history for audits and reports; balances can always be recomputed from the ledger. Mistakes leave visible correction entries, which is intended.
