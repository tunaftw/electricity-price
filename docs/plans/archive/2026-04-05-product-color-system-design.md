# Product Color System — Visual Design

**Goal:** Differentiate the three ELPRIS products (CAPTURE, BESS, FUTURES) through a sparse signature-color system that preserves the existing dark navigation layout.

**Scope:** Visuals only — no layout, typography, or information-architecture changes.

---

## Color Palette

A unified "finance-terminal" palette where all three accents share similar luminosity and saturation, so they read as a family.

| Product | Color | Hex | Rationale |
|---|---|---|---|
| **CAPTURE** | Warm amber | `#E8A04B` | Solar/PV without being juvenile yellow |
| **BESS** | Electric mint/teal | `#2DD4BF` | Storage, battery, "cool" energy |
| **FUTURES** | Soft violet | `#A78BFA` | Markets, forward-looking, abstract |

All three meet WCAG AA contrast against a dark navy background (`#0B1220` or similar) for large and medium text.

The existing `ELPRIS` brand blue remains a constant across all pages — product color is additive, never replaces brand.

---

## Where Color Appears (Sparse — Level 1)

Only four surfaces carry the product color. Everything else stays neutral.

### 1. Navigation — active-item underline

- `border-bottom: 2px solid {productColor}` beneath the active `ELPRIS [PRODUCT]` group
- Subtle glow: `box-shadow: 0 2px 12px -2px {productColor}40` (25% opacity)
- ~8px gap between baseline and underline
- Active product word stays **white** (strongest legibility) — underline carries the product identity as a separate signal
- Hover on inactive items: underline at 30% opacity of the **current page's** product color

### 2. Hero KPI — 3px vertical accent bar

- Left-edge vertical bar on the primary KPI card in product color
- KPI number itself stays **white** — colored large numbers read as "shouty" on data-dense pages
- Supporting KPIs: no color accent

### 3. Main chart — primary series

- The "hero" series (the metric the page is about) is drawn in product color, 2px stroke
- Reference/support series in neutral grays: `#6B7280`, `#9CA3AF`, `#D1D5DB`
- Multi-zone comparisons use a tonal family of the product color (e.g. BESS: `#2DD4BF`, `#5EEAD4`, `#99F6E4`, `#134E4A`)

### 4. Primary CTA button

- Product color background, dark-navy text for contrast
- Secondary buttons: ghost/outline style, no product color

---

## Cross-cutting Interaction States

These small surfaces also pick up the product color to maintain feedback consistency:

- **Focus rings** (keyboard navigation): 2px outline, 2px offset, product color
- **Selection highlights** (table row selection): product color at 15% opacity
- **Loading spinners / progress bars**: product color

---

## What Stays Neutral

Tables, secondary KPIs, breadcrumbs, filters, borders, tooltips, chart grid lines, body numbers. These are reading surfaces — color interferes with comprehension.

---

## Per-Product Feel

Same layout, same components, same typography. Only the accent color shifts.

- **CAPTURE** → amber underline · amber KPI bar · amber capture-price line · amber "Export report" button → *sun, afternoon warmth*
- **BESS** → teal underline · teal arbitrage KPI · teal BESS-revenue line · teal "Run simulation" button → *electric, cool, precision*
- **FUTURES** → violet underline · violet forward-curve KPI · violet SYS-baseload line · violet "Compare contracts" button → *markets, forward-looking, abstract*

The user learns the interface once and recognizes the pattern on all three pages.
