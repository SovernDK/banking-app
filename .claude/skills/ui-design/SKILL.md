---
name: ui-design
description: "Use when building or changing UI in the finance dashboard frontend: layout, charts, filters, tables, colors, number formatting."
---
# UI design: finance dashboard (NiceGUI)

Stack: NiceGUI mounted on the FastAPI app (`ui.run_with(app)`), `ui.echart` for charts, `ui.aggrid` for tables, Tailwind via `.classes()`, Quasar via `.props()`. No custom JS, no other UI or chart libraries.

Visual reference: "CRM Dashboard App Design" by Ronas IT (dribbble.com/shots/25742359). Monochrome ink on white, a pale cream band for the overview, flat bordered cards, black and hatched bars.

## Philosophy
- **Data first.** The numbers are the design. No gradients, no shadows, no icons that don't carry meaning.
- **Monochrome.** Ink on white. Color is spent only on meaning: gain, loss, warning, category. Emphasis comes from ink vs. hatch, size and the inverse card, not from hue.
- **Consistent over clever.** Same thing looks the same everywhere: one way to show money, one card, one chart style.
- **Answer a question.** Every widget answers one question ("Where did my money go this month?"); its title says which. If it doesn't, cut it.
- **Glanceable, then drillable.** Overview band (filters, KPIs, headline chart) → chart grid → table; filters change all of them together.

## Components
Pages are composed only from `app/ui/components/`. Don't style raw `ui.*` elements in page code; if a pattern appears twice, make it a component.
Built so far: `page_shell`, `overview_band`, `section`, `empty_state`, and `money`/`pct`/`date`. The other rows are the spec for components still to build; create each one in `app/ui/components/` the first time a page needs it.

| Component | Purpose |
|---|---|
| `page_shell(title)` | Page background, max width, top bar with title and dark-mode toggle |
| `overview_band()` | Full-width cream band holding the filter bar, KPI row and headline chart |
| `filter_bar(filters, on_change)` | Search + ghost buttons (icon + label: Sort, Filters) + primary action; binds to the `Filters` dataclass, syncs URL params, has Reset |
| `section(title, subtitle=None)` | Flat bordered card with title row and optional actions slot; every widget below the band lives in one |
| `kpi_tile(label, value, delta=None)` | Big number, two-line muted label below, optional arrow link; delta with sign/arrow and gain/loss color |
| `chart(option)` | Wraps `ui.echart`; applies theme, palette, fonts, hatch decal, dark mode, empty state |
| `gauge(value, label)` | ECharts gauge drawn as tick marks (filled ticks = ink, rest = track); for a single ratio such as budget used |
| `data_table(rows, columns)` | Wraps `ui.aggrid`; money columns right-aligned and formatted |
| `chip(icon, text)` | Small outlined pill (date, count) |
| `money(value, currency)`, `pct(value)`, `date(value)` | The only way to render numbers and dates (`app/ui/format.py`) |
| `empty_state(message)` | Shown instead of an empty chart or table |

Data-bound components are `@ui.refreshable`; a filter change refreshes them all.

## Surfaces and shape
- **Cards:** card background, 1px border, radius `rounded-xl` (12px), no shadow (`flat bordered`).
- **Muted card:** `card-muted` background, no border; for secondary or closed items.
- **Inverse card:** ink background with inverse text; at most one per view, for the selected or most important item.
- **Buttons:** primary = ink background, inverse text, `rounded-lg`; secondary = ghost (no background, icon + label).
- **Chips:** 1px border, `rounded-md`, `text-xs`, leading icon.
- **Form fields:** border uses the muted-text color, not the card border, so it meets 3:1.
- **Nav / selected item:** `card-muted` pill behind it.

## Typography
- One family: **Inter** (fallback `system-ui, sans-serif`), set globally in `page_shell` and on ECharts `textStyle`. To self-host it, serve the font files with `app.add_static_files`.
- All numbers use `tabular-nums` so columns and KPIs align.
- Large text is light, not bold: KPI value `text-4xl font-normal`; section/column title `text-2xl font-normal`; card title `text-lg font-medium`; body/table `text-sm`; labels, axes, captions `text-xs text-muted`.
- Weights 400 / 500 only; 600 only for the app name. No all-caps.

## Colors
Defined once in `app/ui/palette.py` and exposed as CSS variables by `page_shell`. Values are light / dark. Every text pair meets WCAG AA (4.5:1); chart colors meet 3:1 against card and band.

| Role | Light | Dark |
|---|---|---|
| Ink (primary button, main bars, gauge fill, inverse card) | `#1F1F1F` | `#F6F7ED` |
| Inverse text (on ink) | `#F6F7ED` | `#1F1F1F` |
| Text | `#111111` | `#F2F2F2` |
| Muted text, axes, form-field borders | `#6B6B6B` | `#A3A3A3` |
| Band (overview background) | `#F6F7ED` | `#1C1D17` |
| Page and card | `#FFFFFF` | `#121212` / `#1A1A1A` |
| Muted card, selected nav | `#F4F4F4` | `#242424` |
| Card borders, gridlines | `#D3D3D3` | `#3A3A3A` |
| Secondary bars (hatched), gauge track | `#82827D` / `#C7C8C0` | `#6B6B66` / `#3A3A35` |
| Gain / income | `#2E7D4F` | `#6FCF97` |
| Loss / expense | `#C0392B` | `#F28B82` |
| Warning | `#9A5B00` | `#F2B84B` |

Categories, in order (light / dark): ink `#1F1F1F`/`#F6F7ED`, olive `#6B7A3A`/`#A9B87A`, sand `#A07C3F`/`#D9B77A`, slate `#4F7390`/`#8FB0CC`, clay `#A65E4E`/`#D9907F`, plum `#6E5A8C`/`#A994C8`, teal `#3F7F7A`/`#7FBFB8`; "Other" `#8A8A82` hatched.
- Green/red mean gain/loss only, never categories; always paired with a sign or arrow.
- Max 7 categories, rest grouped into "Other"; a category keeps its color everywhere (map by name).
- Mirror into Quasar with `ui.colors(...)`, and override `--q-primary` etc. under `body.body--dark` so ink inverts in dark mode.

## Charts
- **Bars:** current period solid ink; comparison period (previous month, budget) the same bar hatched (ECharts `itemStyle.decal`, diagonal lines in the secondary-bar color). No legend needed when the title says "this vs last month".
- **Gauge:** tick-mark arc (`axisTick` only, no pointer, no progress band); value `text-4xl` centred with a muted label below.
- Axes: muted text, no axis line, light gridlines; rounded bar tops (`borderRadius: [4, 4, 0, 0]`).
- Tooltips use card background, border and text tokens.

## Layout
Top bar → overview band (filter bar, then KPIs and headline chart in one row on desktop, stacked on mobile) → chart grid on white (1 col mobile, 2 desktop) → table. Spacing on one rhythm: `gap-4` between sections, `p-4` inside cards, `p-6` inside the band.

## Done check
Run the app, take Playwright screenshots in light and dark mode, and look at them before finishing.
