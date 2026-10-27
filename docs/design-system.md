# Design system

Defined in `frontend/src/app/theme.ts` (Mantine theme) and `frontend/src/styles/global.css` (tokens and global rules). Printed documents follow the same palette (`backend/templates/documents/base.html`).

## Colour

The client's reference slate palette for everything neutral, plus **one accent, orange**, chosen on 27 Oct 2026 because an all-slate interface read as flat and the main actions did not stand out. In-between shades come from the same families (Tailwind slate and orange), which Mantine needs for hover and border states.

| Token | Hex | Use |
|---|---|---|
| Background | `#F8FAFC` | App background, table headers |
| Surface | `#FFFFFF` | Cards, inputs, tables |
| Border | `#E2E8F0` | Dividers, input borders, subtle fills |
| Decor | `#94A3B8` | Icons, placeholders, disabled, progress tracks. **Never body text** (2.6:1 contrast) |
| Muted text | `#64748B` / dimmed `#475569` | Secondary text (≥ 4.8:1, passes WCAG AA) |
| Strong text | `#334155` | Headings in tables, strong labels, links |
| **Accent** | orange `#C2410C` (hover `#9A3412`, tint `#FFF7ED`) | The main action on each screen (New order, Save, Confirm, Deliver, Sign in), checkboxes and switches, the active sidebar marker, the focus ring. `#C2410C` with white text is 5.2:1 (passes AA); the brighter `#EA580C` is not used for text-on-fill |
| Text / sidebar | `#0F172A` | Body text; sidebar background |

One orange filled button per screen at most: the top-bar **New order** is the main action everywhere, so pages do not repeat it (a customer's page offers a light-orange "New order" for that customer). Links stay slate, so orange always means "act here".

**Other colour is reserved for meaning**, as soft badges or small marks, always with a text label. Dashboard and Insights cards tint their icons (sales blue, money green, dues amber, jobs violet, stock orange) so each kind of figure is recognisable at a glance:

| Meaning | Colour |
|---|---|
| Done, paid, available, ready | green `#15803D` |
| Due today, low stock, warnings | amber `#B45309` |
| Overdue, cancelled, void, dues owed | red `#B91C1C` |
| Ready for print (stage) | blue `#1D4ED8` |
| Finishing (stage) | violet `#6D28D9` |

## Type

- **Inter** (variable, self-hosted) with **Noto Sans Devanagari** as fallback for Nepali names and BS month names. No fonts load from the internet.
- Sizes: 12 caption · **14 body, tables and inputs (desktop)** · 16 inputs on phones (stops iOS zoom) · 18 / 20 section titles · 24 page title · 28 stat values.
- Weights 400 / 500 / 600. Line height 1.5 for text, 1.25 for headings.
- Money and quantity **columns** use tabular figures and are right-aligned; large single numbers (stat tiles) use normal figures.
- Money uses South Asian grouping: `Rs. 1,25,000.00`.

## Space and shape

4 px grid: 4 · 8 · 12 · 16 · 24 · 32 · 48. Page gutter 24 px on desktop, 16 px on phones. Radius 8 px for controls, 12 px for cards. Borders separate surfaces; shadows are reserved for menus and dialogs.

## Layout (desktop-first)

Breakpoints: xs 576 · sm 768 · md 992 · lg 1200 · xl 1408 px. Base styles target desktop; `@mixin smaller-than` media queries adapt down.

| Below | Change |
|---|---|
| lg (1200) | Order summary panel stacks under the form; a sticky total bar appears at the bottom |
| md (992) | Sidebar becomes a menu drawer |
| sm (768) | Production board shows one stage at a time (tabs with counts); less important table columns hide |

## Components and patterns

- Page header: title, short description, actions on the right (wrap on phones).
- Tables: `mantine-datatable`, server-side paging, filters kept in the URL, quiet uppercase headers.
- Badges: sentence case, soft fills.
- Empty states always say what will appear and offer the next action.
- Destructive or irreversible actions ask for confirmation; cancellations and voids require a written reason.
- Toasts confirm saves; form errors appear on the field the server named.

## Charts

One chart: daily sales for 30 days, a single slate series (no legend box), bars at most 24 px wide with 4 px rounded tops, solid hairline grid, compact axis labels (5K, 1.2L), hover tooltip, and a table view toggle. Stage counts are shown as a labelled list, not a chart.

## Accessibility

Visible focus rings, labelled inputs and icon buttons, AA contrast for all text, status never shown by colour alone, keyboard shortcuts (`/` search, `N` new order, `?` list; Ctrl+S saves an order; Enter on the last item adds another).

**Text size:** Normal / Large / Extra large (100 / 112.5 / 125 %) from the account menu and on the sign-in screen, remembered per device (`src/app/textSize.ts`). Everything is sized in rem, so text, buttons and spacing grow together; tables scroll sideways instead of squeezing, and key columns do not wrap. The browser's own font-size setting still applies on top.

## Brand

The ChhapaKhata mark is a print stamp (*chhapa*) over two ledger lines (*khata*), on a `#0F172A` tile with rounded corners (radius ≈ 21 % of the side). It uses only the palette: handle `#E2E8F0`, neck and ledger lines `#94A3B8`, stamp base `#F8FAFC`.

| Asset | Where |
|---|---|
| Mark (SVG, master) | `frontend/public/brand/logo-mark.svg` (also `favicon.svg`) |
| React component | `frontend/src/components/Logo.tsx`: `<Logo size onDark />` (mark + wordmark) and `<LogoMark />` |
| App icons | `frontend/public/icons/`: 192 and 512 px rounded tiles; 512 px maskable (full bleed, glyph at 78 % inside the safe zone); 180 px Apple touch icon |

Wordmark: "Chhapa" bold, "Khata" medium, Inter, letter-spacing −0.02 em. On light backgrounds `#0F172A` + `#64748B`; on dark (sidebar, login panel) `#F8FAFC` + `#94A3B8`, and the tile gets a faint `#334155` edge so it does not melt into the background. The shop's own logo (Settings → Shop) stays on invoices and receipts; the ChhapaKhata mark is for the app only.
