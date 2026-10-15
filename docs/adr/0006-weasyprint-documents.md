# 0006: PDF documents with WeasyPrint

**Status:** accepted · 2026-10-15

**Context.** Quotations, invoices (A4, A5, 80 mm thermal), receipts, statements, job tickets and reports must print the same offline.

**Decision.** Django HTML templates rendered by WeasyPrint with bundled Inter and Noto Sans Devanagari fonts. Thermal documents are laid out twice to cut the page to the content height. Invoice prints go through a POST that counts copies.

**Consequences.** Templates are plain HTML/CSS, easy to adjust when the client supplies the final layout, stamp and signature. Requires Pango system libraries (in the Docker image; `brew install pango` for macOS development).
