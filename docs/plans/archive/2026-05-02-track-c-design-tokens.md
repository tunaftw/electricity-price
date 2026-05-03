# Track C — Design Tokens & Patterns

**Date:** 2026-05-02
**Status:** Design phase
**Track:** C (alternative to Track A's Bloomberg-dark)
**Skill consulted:** `frontend-design`

## Aesthetic direction

**"Nordic Editorial"** — refined, editorial-grade dashboard. Light theme. Inspired by
Linear/Stripe/Vercel, but with a distinctly Scandinavian voice: warm off-white paper
background instead of stark white, a serif display face for headlines paired with a
precise modern grotesque for the UI, and a single sharp accent (electric chartreuse)
that signals SveaSolar's renewable-energy DNA without being a literal "solar yellow."

**Voice:** quiet confidence. Information-dense but airy. Strong hierarchy through
typography (size, weight, case, tracking) rather than chrome (boxes, shadows, gradients).

## Differentiation from Track A

| Aspect | Track A (Bloomberg) | Track C (Editorial) |
|---|---|---|
| Theme | Dark, terminal | Light, paper |
| Layout | Top-bar tabs only | Persistent left sidebar with rail + section nav |
| Type | Mono-everywhere | Serif display + grotesque body + mono numerals |
| Accent | Cyan/violet (multiple) | Single chartreuse (#C7F26A) |
| Hierarchy | Box-driven | Type-driven (weight + tracking) |
| KPI tiles | Border-left colored | Number-first, large, with tabular-nums |
| Charts | Dense tooltips | Generous whitespace, soft gridlines |

## Design tokens

### Colors

```css
:root {
  /* Surfaces — warm paper, never pure white */
  --surface-base:    #F7F5F0;   /* page background, warm parchment */
  --surface-raised:  #FFFFFF;   /* cards (subtle elevation) */
  --surface-sunken:  #EFEBE2;   /* table stripes, hover states */
  --surface-rail:    #1A1814;   /* dark sidebar rail (counterpoint) */

  /* Ink — warm near-blacks, layered */
  --ink-1:  #1A1814;   /* primary, headlines */
  --ink-2:  #45413A;   /* body text */
  --ink-3:  #6B6660;   /* secondary / labels */
  --ink-4:  #9A958C;   /* muted / placeholders */
  --ink-5:  #C9C4B9;   /* dividers */

  /* Accent — electric chartreuse, a single sharp note */
  --accent:        #C7F26A;
  --accent-deep:   #92B53D;
  --accent-glow:   rgba(199, 242, 106, 0.18);

  /* Semantic — desaturated, editorial */
  --good:    #4F8A4D;
  --good-bg: #E5F0DF;
  --warn:    #B0832C;
  --warn-bg: #F5EBD2;
  --bad:     #B14E45;
  --bad-bg:  #F4DDD8;

  /* Data viz palette — calibrated for light bg, distinct hues, equal luminance */
  --viz-1: #2E5C4D;   /* deep teal */
  --viz-2: #C16E40;   /* terracotta */
  --viz-3: #5B6BA8;   /* dusty blue */
  --viz-4: #B14F75;   /* mulberry */
  --viz-5: #C9A53C;   /* mustard */
  --viz-6: #6E5B85;   /* aubergine */
  --viz-7: #4A8C7B;   /* sage */
  --viz-8: #A85838;   /* burnt sienna */
}
```

### Typography

Three families layered:

- **Display (headlines, tab titles):** `"Newsreader"` — Google Fonts serif, editorial,
  optical sizes. Used for: page H1, tab headers, KPI labels (small caps).
- **UI/Body:** `"Geist"` — modern grotesque, refined, neutral. Used for: body, buttons,
  labels, table cells.
- **Mono (all numerals):** `"JetBrains Mono"` with `font-variant-numeric: tabular-nums`.
  Used for: every number in the UI (KPI values, table cells, axis ticks).

```css
:root {
  --font-display: 'Newsreader', 'Charter', 'Iowan Old Style', Georgia, serif;
  --font-ui:      'Geist', -apple-system, 'Segoe UI', system-ui, sans-serif;
  --font-mono:    'JetBrains Mono', 'SF Mono', ui-monospace, Menlo, monospace;
}
```

### Type scale

```css
:root {
  --fs-xs:   11px;   /* eyebrow labels, small caps */
  --fs-sm:   12.5px; /* table cells, dense data */
  --fs-md:   13.5px; /* default body */
  --fs-lg:   15px;   /* section headers */
  --fs-xl:   20px;   /* card titles */
  --fs-2xl:  28px;   /* KPI values */
  --fs-3xl:  40px;   /* hero KPI / page H1 */
  --fs-4xl:  56px;   /* drilldown park name */

  --lh-tight:  1.15;
  --lh-snug:   1.35;
  --lh-normal: 1.55;
}
```

### Spacing — 4-px base, restrained

```css
:root {
  --sp-1:  4px;
  --sp-2:  8px;
  --sp-3:  12px;
  --sp-4:  16px;
  --sp-5:  24px;
  --sp-6:  32px;
  --sp-7:  48px;
  --sp-8:  64px;
}
```

### Radii — soft, editorial

```css
:root {
  --radius-sm:  4px;
  --radius-md:  8px;
  --radius-lg:  12px;
  --radius-pill: 999px;
}
```

### Shadows — paper-like, not card-like

Avoid cliche neumorphic shadows. Use a subtle 1px hairline + a tiny y-offset blur to
suggest paper resting on paper.

```css
:root {
  --shadow-hair:  0 0 0 1px rgba(26, 24, 20, 0.06);
  --shadow-rest:  0 1px 2px rgba(26, 24, 20, 0.04), 0 0 0 1px rgba(26, 24, 20, 0.05);
  --shadow-hover: 0 4px 12px rgba(26, 24, 20, 0.08), 0 0 0 1px rgba(26, 24, 20, 0.06);
  --shadow-focus: 0 0 0 3px var(--accent-glow);
}
```

### Motion

```css
:root {
  --ease:      cubic-bezier(0.4, 0, 0.2, 1);
  --ease-out:  cubic-bezier(0.16, 1, 0.3, 1);   /* satisfying decel */
  --dur-fast:  120ms;
  --dur-med:   220ms;
  --dur-slow:  400ms;
}
```

## Layout — sidebar + rail + section nav

Two-tier navigation:

1. **Vertical rail** (56px wide, dark `--surface-rail`, persistent): houses tab icons
   (CAPTURE, BESS, FUTURES, ASSETS) as monogram letters in serif. Selected tab has the
   chartreuse accent dot.
2. **Content column** (rest of width): page header with H1 + meta-pills, then content.

The rail being dark on a light page is a deliberate counterpoint — like a leather spine
on a cream-page magazine. Width of the rail stays narrow; everything else is generous.

```
+------+------------------------------------------------------+
|      | Capture Prices                          [SE3 ▾] [Y]  |  <- header strip
| C    |                                                       |
| B    | KPI    KPI    KPI    KPI                              |
| F    |                                                       |
| A    | [chart]                                               |
|      |                                                       |
+------+------------------------------------------------------+
```

## Component patterns

### KPI tile — number-first, no chrome

```
EYEBROW LABEL          (small caps, ink-3)
56.4 EUR/MWh           (mono, fs-3xl, ink-1, tabular-nums)
↑ +12.3% vs prev       (fs-xs, semantic color)
```

No background fill on tiles. Just generous padding and a hairline divider on the right
between adjacent tiles. Borders only on hover/focus.

### Card — paper on paper

`background: --surface-raised` (white) on `--surface-base` (cream). Hairline border
(`--shadow-hair`). Generous internal padding (`--sp-5`). Title is fs-lg in serif display,
subtitle is fs-xs in small caps + tracking.

### Data table — editorial, not gridded

- No vertical grid lines.
- Horizontal rules only between groups, not every row.
- Zebra stripes are `--surface-sunken` (warm beige), not gray.
- Numeric columns are right-aligned, mono, tabular-nums.
- Header row is small-caps eyebrow-style.
- Sortable header: arrow only appears on the active sort column; hover shows a faint
  arrow on others.

### Chart container

- Plotly background `--surface-raised` (matches card).
- Gridlines: `--ink-5` at 30% opacity (barely there).
- Axis labels: `--ink-3`, fs-xs, mono for numbers.
- Trace colors from the data-viz palette (--viz-1 through --viz-8).
- Hover: paper-tooltip with hairline border, no shadow.

### Drilldown navigation — breadcrumb + back

Top of drilldown: chartreuse pill "← Back to fleet" + breadcrumb path
"Assets / Hörby / 2026-04". Park name renders as fs-4xl serif display.

### Filters — inline pills, not dropdowns

Where possible, render filter options as horizontal pill buttons (like Linear's filter
chips). Active pill has chartreuse fill. Falls back to native `<select>` for long lists
(months).

### Status colors (vs budget)

- ≥ +5% : `--good` text + `--good-bg` fill on a subtle pill
- ±5%   : `--warn` text + `--warn-bg`
- ≤ -5% : `--bad` text + `--bad-bg`

Avoid hard red/green traffic-light. Editorial palette = muted, considered.

## Interaction patterns

- **Focus rings:** always visible, 3px chartreuse glow (`--shadow-focus`).
- **Hover:** charts/cards/rows lift only via a hairline darkening — no transform jumps.
- **Sort:** clicking a column header toggles asc/desc; arrow appears beside label.
- **Tab switch:** content fades+lifts in (200ms). Rail icon dot animates with
  `--ease-out`.

## Accessibility

- Color contrast ≥ 4.5:1 for body text, 3:1 for large text. Verified with the palette
  above (ink-2 on surface-base = 8.7:1).
- Status colors never carry meaning alone — always paired with text + icon.
- All interactive elements keyboard-reachable with visible focus.
- `aria-sort`, `aria-selected`, `aria-expanded` on stateful controls.
- `prefers-reduced-motion` cuts transitions to instant.

## File-size discipline

The dashboard ships ~17 MB inline JSON. The Track C styling layer must add no more than
~30 KB of CSS+HTML over what Track A already inlines. We use vanilla JS only and inline
fonts via Google Fonts CDN (one extra HTTP request, gracefully degrades to system serif).
