---
name: ui-design
description: "Use when building or changing UI in the finance dashboard frontend: pages, components, dialogs, forms, buttons, layout, charts, filters, tables, colors, dark mode, styling, accessibility, number formatting."
---
# UI design: finance dashboard (NiceGUI)

Stack: NiceGUI mounted on the FastAPI app (`ui.run_with(app)`), `ui.echart` for charts, `ui.aggrid` for data tables, Tailwind via `.classes()`, Quasar via `.props()`. No custom JS, no other UI or chart libraries.

Look: monochrome ink on white, a pale cream band for the overview, flat bordered cards, solid ink and hatched bars.

## Philosophy
- **Data first.** The numbers are the design. No gradients, no shadows, no icons that don't carry meaning.
- **Monochrome.** Ink on white. Color is spent only on meaning: gain, loss, warning, category. Emphasis comes from ink vs. hatch, size and the inverse card, not from hue.
- **Consistent over clever.** Same thing looks the same everywhere: one way to show money, one card, one chart style.
- **Answer a question.** Every widget answers one question ("Where did my money go this month?"); its title says which. If it doesn't, cut it.
- **Glanceable, then drillable.** Overview band (filters, KPIs, headline chart) → chart grid → table; filters change all of them together.

## Components
- Pages are composed only from `app/ui/components/`. List that folder and reuse what is there before writing anything; don't style raw `ui.*` elements in page code. If a pattern appears twice, make it a component.
- Numbers and dates render only through `app/ui/format.py` (`money`, `pct`, `date`, `chart_amount` for ECharts values).
- Charts go through `chart(...)` in `components/chart.py`, which applies theme, palette, fonts and dark mode; use its `hatch_decal` for hatched marks.
- Not built yet, create in `app/ui/components/` when first needed:
  - `gauge(value, label)`: ECharts gauge drawn as tick marks (filled ticks = ink, rest = track) for a single ratio such as budget used.
  - `data_table(rows, columns)`: wraps `ui.aggrid`; money columns right-aligned and formatted.

## Updating on screen
- **Edits never move the page.** After a user edit (select, input, dialog), update the existing elements in place: `echart.options` + `update()`, `select.set_options(...)`, a component's own `update`/`show` method, or clearing only a small container. Never `@ui.refreshable.refresh()` a section for an edit: the section briefly shrinks and the browser clamps the scroll position.
- Full refreshes are for filter changes at the top of the page only.
- Cover an edit with an E2E test asserting the scroll position is unchanged.

## Surfaces and shape
- **Cards:** card background, 1px border, radius `rounded-xl` (12px), no shadow (`flat bordered`).
- **Muted card:** `card_muted` background, no border; for secondary or closed items.
- **Inverse card:** ink background with inverse text; at most one per view, for the selected or most important item.
- **Buttons:** `primary_button` = ink background, inverse text, `rounded-lg`; `ghost_button` = no background, icon + label.
- **Chips:** 1px border, `rounded-md`, `text-xs`, leading icon.
- **Form fields:** border uses the muted-text color, not the card border, so it meets 3:1.
- **Nav / selected item:** `card_muted` pill behind it.

## Typography
- One family: **Inter** (fallback `system-ui, sans-serif`, `FONT_FAMILY` in `palette.py`), set globally in `page_shell` and on ECharts `textStyle`.
- All numbers use `tabular-nums` so columns and KPIs align.
- Large text is light, not bold: KPI value `text-4xl font-normal`; section/column title `text-2xl font-normal`; card title `text-lg font-medium`; body/table `text-sm`; labels, axes, captions `text-xs text-muted`.
- Weights 400 / 500 only; 600 only for the app name. No all-caps.

## Colors
The source of truth is `app/ui/palette.py` (`LIGHT` / `DARK` `Palette`); `page_shell` exposes it as `--yiji-*` CSS variables. Never write a hex value outside `palette.py`. Python code reads `Palette` fields; CSS uses the variables or the existing `yiji-*` / `text-muted` classes.

| Token | Use for |
|---|---|
| `ink` | Primary button, current-period bars, gauge fill, inverse card |
| `inverse_text` | Text on ink |
| `text` | Body text |
| `muted` | Secondary text, axes, form-field borders |
| `band` | Overview band background |
| `page`, `card` | Page and card backgrounds |
| `card_muted` | Muted card, selected nav, alerts |
| `border` | Card borders, gridlines |
| `secondary_bar`, `gauge_track` | Hatched comparison bars, gauge track |
| `gain`, `loss` | Income / gain and expense / loss only |
| `warning` | Warnings (Quasar `--q-warning`) |
| `categories`, `other_category` | Category colors in fixed order; "Other" is hatched |

- Every text pair meets WCAG AA (4.5:1); chart colors meet 3:1 against card and band. Check any new or changed value in both themes.
- Green/red mean gain/loss only, never categories; always paired with a sign or arrow.
- Max 7 categories, rest grouped into "Other"; a category keeps its color everywhere (map by name).
- `page_shell` maps the palette onto Quasar's `--q-primary` (ink), `--q-positive` (gain), `--q-negative` (loss) and `--q-warning` for both themes, so Quasar `color=` props follow dark mode; use those, not `ui.colors(...)`.

## Charts
- **Bars:** current period solid ink; comparison period (previous month, budget) the same bar hatched (`hatch_decal`). No legend needed when the title says "this vs last month".
- **Gauge:** tick-mark arc (`axisTick` only, no pointer, no progress band); value `text-4xl` centred with a muted label below.
- Axes: muted text, no axis line, light gridlines; rounded bar tops (`borderRadius: [4, 4, 0, 0]`).
- Tooltips use card background, border and text tokens.

## Layout
Top bar → overview band (filters, then KPIs and headline chart in one row on desktop, stacked on mobile) → chart grid on white (1 col mobile, 2 desktop) → table. Spacing on one rhythm: `gap-4` between sections, `p-4` inside cards, `p-6` inside the band.

## Accessibility
Every UI is responsive and meets WCAG 2.1 AA.
- Every input and select has a visible label or a `label` prop; icon-only buttons get `aria-label`.
- Everything is reachable and usable by keyboard; never remove focus outlines.
- Headings use `role="heading"` with `aria-level` when built from labels.
- Give elements tests select a `data-testid` (E2E tests select by role, label or test id, never by class).

## Done check
Use the `verify` skill to run the app against the fake bank and look at the change in a real browser, in light and dark mode and at phone width, before finishing.
