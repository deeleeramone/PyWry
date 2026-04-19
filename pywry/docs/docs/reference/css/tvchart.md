# TradingView Stylesheet

Source: `frontend/style/tvchart.css` — Complete UI for the TradingView Lightweight Charts integration, including toolbars, legend, drawing tools, settings panels, and dialogs.

This stylesheet defines ~67 CSS custom properties per theme (dark and light) for full chart theming.

---

## CSS Variables

### Chart Colors

```css
:root, html.dark, .pywry-theme-dark {
    --pywry-tvchart-bg: /* chart background */;
    --pywry-tvchart-border: /* toolbar/panel borders */;
    --pywry-tvchart-border-strong: /* emphasized borders */;
    --pywry-tvchart-panel-bg: /* panel background */;
    --pywry-tvchart-panel-bg-strong: /* dialog background */;
    --pywry-tvchart-hover: /* hover highlight */;
    --pywry-tvchart-active-bg: /* active item background */;
    --pywry-tvchart-active-text: /* active item text */;
    --pywry-tvchart-text: /* primary text */;
    --pywry-tvchart-text-muted: /* secondary text */;
    --pywry-tvchart-text-dim: /* disabled/dimmed text */;
}
```

### Candlestick Colors

```css
:root {
    --pywry-tvchart-up: /* bullish color (green) */;
    --pywry-tvchart-down: /* bearish color (red) */;
    --pywry-tvchart-border-up: /* bullish border */;
    --pywry-tvchart-border-down: /* bearish border */;
    --pywry-tvchart-wick-up: /* bullish wick */;
    --pywry-tvchart-wick-down: /* bearish wick */;

    /* Chart-style patch values — read by _tvResolveChartStyle() in JS
       to build the optionPatch for style switches.  Defined as CSS
       vars so themes stay the source of truth. */
    --pywry-tvchart-hollow-up-body: /* hollow-candles up-body fill (default: transparent) */;
    --pywry-tvchart-hidden: /* body/border/wick hide marker (default: transparent) */;
    --pywry-tvchart-price-line: /* right-axis price marker color — stays visible even when the body is hollow */;
}
```

### Grid & Crosshair

```css
:root {
    --pywry-tvchart-grid: /* grid line color */;
    --pywry-tvchart-grid-vert: /* vertical grid */;
    --pywry-tvchart-grid-horz: /* horizontal grid */;
    --pywry-tvchart-crosshair: /* crosshair line */;
    --pywry-tvchart-crosshair-color: /* crosshair color */;
    --pywry-tvchart-crosshair-label-bg: /* crosshair label background */;
}
```

### Volume & Area Charts

```css
:root {
    --pywry-tvchart-vol-up: /* volume up bar */;
    --pywry-tvchart-volume-down: /* volume down bar */;
    --pywry-tvchart-area-bottom: /* area chart fill bottom */;

    /* HLC Area */
    --pywry-tvchart-hlcarea-high: /* high line */;
    --pywry-tvchart-hlcarea-low: /* low line */;
    --pywry-tvchart-hlcarea-close: /* close line */;
    --pywry-tvchart-hlcarea-fill-up: /* up fill */;
    --pywry-tvchart-hlcarea-fill-down: /* down fill */;

    /* Baseline */
    --pywry-tvchart-baseline-top-fill1: /* above baseline gradient start */;
    --pywry-tvchart-baseline-top-fill2: /* above baseline gradient end */;
    --pywry-tvchart-baseline-bottom-fill1: /* below baseline gradient start */;
    --pywry-tvchart-baseline-bottom-fill2: /* below baseline gradient end */;

    /* Settings-dialog defaults — read by the series-settings modal
       when populating initial color pickers for Line / Area series. */
    --pywry-tvchart-line-default: /* default line-style series color */;
    --pywry-tvchart-area-top-default: /* default area top fill */;
    --pywry-tvchart-area-bottom-default: /* default area bottom fill */;
}
```

### Drawing Tools

```css
:root {
    --pywry-draw-default-color: /* default drawing color */;
    --pywry-draw-label-text: /* drawing label text */;
    --pywry-draw-handle-fill: /* drag handle fill */;
    --pywry-draw-measure-up: /* measure tool up color */;
    --pywry-draw-measure-down: /* measure tool down color */;
}
```

### Preset & Fibonacci Colors

```css
:root {
    /* 15-color preset palette for overlay series */
    --pywry-preset-0 through --pywry-preset-14;

    /* 7-level Fibonacci colors */
    --pywry-fib-color-0 through --pywry-fib-color-6;
}
```

### UI State

```css
:root {
    --pywry-tvchart-selected-bg: /* selected item background */;
    --pywry-tvchart-selected-text: /* selected item text */;
    --pywry-tvchart-overlay: /* modal overlay */;
    --pywry-tvchart-shadow: /* small shadow */;
    --pywry-tvchart-shadow-lg: /* large shadow */;
    --pywry-tvchart-separator: /* pane separator */;
    --pywry-tvchart-separator-hover: /* pane separator hover */;
    --pywry-tvchart-legend-border: /* legend border */;
    --pywry-tvchart-legend-bg: /* legend background */;
    --pywry-tvchart-session-breaks: /* session break lines */;
}
```

All variables are duplicated for the light theme with appropriate light-mode values.

---

## Container

The outer wrapper that hosts the chart and its toolbars:

```css
.pywry-tvchart-container { /* Root container holding the chart canvas, header toolbar, bottom status bar, and the drawing overlay */ }
```

---

## Icon Buttons

Shared icon button used throughout the chart UI:

```css
.pywry-icon-btn { /* Base icon button — rounded, transparent background */ }
.pywry-icon-btn:hover { /* Hover state */ }
.pywry-icon-btn:active { /* Active/pressed state */ }
.pywry-icon-btn.active { /* Toggled-on state */ }
.pywry-icon-btn svg { /* Icon SVG sizing */ }
.pywry-icon-btn-wrap { /* Icon button wrapper for flex layout */ }
```

---

## Top Header Toolbar

```css
.tvchart-header { /* Top toolbar bar — chart type, timeframes, symbol search */ }
.tvchart-menu-anchor { /* Dropdown anchor position */ }
.tvchart-menu-trigger { /* Menu trigger button */ }
```

### Separators

```css
.tv-separator { /* Vertical separator line between button groups */ }
.tv-separator-wrap { /* Separator wrapper */ }
```

### Timeframe Buttons

```css
.tv-tf-group { /* Timeframe button group container */ }
.tv-tf-btn { /* Individual timeframe button (1m, 5m, 1h, 1D, etc.) */ }
.tv-tf-btn:hover { /* Hover state */ }
.tv-tf-btn.tv-tf-active { /* Active/selected timeframe */ }
```

### Interval Menu

```css
.tvchart-interval-menu { /* Interval dropdown menu */ }
.tvchart-interval-item { /* Interval option */ }
.tvchart-interval-section { /* Section header within menu */ }
.tv-interval-btn { /* Interval trigger button */ }
.tv-interval-caret { /* Dropdown caret arrow */ }
```

### Chart Type Menu

```css
.tvchart-chart-type-menu { /* Chart type dropdown (candlestick, line, bar, etc.) */ }
.tvchart-chart-type-item { /* Chart type option */ }
.tvchart-chart-type-item.selected { /* Selected chart type */ }
```

---

## Left Drawing Toolbar

```css
.tvchart-left { /* Left sidebar toolbar container */ }
```

### Tool Groups

```css
.pywry-tool-group { /* Drawing tool button with sub-tool indicator */ }
.pywry-tool-group-icon { /* Tool icon */ }
.pywry-tool-group-caret { /* Small triangle indicating submenu */ }
```

### Tool Flyout

```css
.pywry-tool-flyout { /* Expanded flyout panel listing sub-tools */ }
.pywry-tool-flyout-header { /* Flyout header */ }
.pywry-tool-flyout-item { /* Individual tool in flyout */ }
.pywry-tool-flyout-icon { /* Tool icon in flyout */ }
.pywry-tool-flyout-name { /* Tool name */ }
.pywry-tool-flyout-shortcut { /* Keyboard shortcut hint */ }
```

---

## Bottom Status Bar

```css
.tvchart-bottom { /* Bottom toolbar — timezone, session, scale buttons */ }

/* Text Buttons (Timezone, Session) */
.tvchart-bottom-btn { /* Text-style button */ }
.tvchart-bottom-btn:hover { /* Hover state */ }
.tvchart-bottom-btn.active { /* Active state */ }
.tvchart-bottom-btn-caret { /* Dropdown caret */ }

/* Scale Mode Buttons */
.tvchart-scale-btn { /* %, log, auto scale toggle buttons */ }
.tvchart-scale-btn.active { /* Active scale mode */ }
```

### Timezone Menu

```css
.tvchart-tz-menu { /* Timezone dropdown menu */ }
.tvchart-tz-menu-item { /* Timezone option */ }
.tvchart-tz-menu-sep { /* Separator in timezone menu */ }
```

---

## Legend

### Main Legend (OHLC, Volume)

```css
.tvchart-legend-container { /* Legend overlay container */ }
.tvchart-legend-row { /* Legend row wrapper */ }
.tvchart-legend-title { /* Symbol title */ }
.tvchart-legend-ohlc { /* OHLC values display */ }
.tvchart-legend-vol { /* Volume display */ }
.tvchart-legend-collapse-btn { /* Collapse/expand legend button */ }
```

### Series Indicators

```css
.tvchart-legend-series { /* Series legend group */ }
.tvchart-legend-series-row { /* Individual series row */ }
.tvchart-legend-series-dot { /* Color dot indicator */ }
.tvchart-legend-series-name { /* Series name */ }
.tvchart-legend-series-value { /* Current value */ }
.tvchart-legend-series-actions { /* Action buttons */ }
```

### Per-Pane Indicators (RSI, MACD, etc.)

```css
.tvchart-pane-legend { /* Subplot pane legend */ }
.tvchart-ind-row { /* Indicator row */ }
.tvchart-ind-dot { /* Indicator color dot */ }
.tvchart-ind-name { /* Indicator name */ }
.tvchart-ind-val { /* Indicator value */ }
.tvchart-ind-ctrl { /* Indicator controls (visibility, settings, remove) */ }
```

### Legend Actions

```css
.tvchart-legend-row-actions { /* Hover-revealed action buttons */ }
.tvchart-legend-btn { /* Legend action button */ }
```

### Legend Context Menu

```css
.tvchart-legend-menu { /* Right-click context menu for legend items */ }
.tvchart-legend-menu-item { /* Menu item */ }
.tvchart-legend-menu-item.is-disabled { /* Disabled item */ }
.tvchart-legend-menu-sep { /* Menu separator */ }
```

---

## Drawing Toolbar

Floating toolbar shown when a drawing is selected:

```css
.pywry-draw-toolbar { /* Floating drawing toolbar */ }
.dt-sep { /* Separator in drawing toolbar */ }
.dt-swatch { /* Color swatch button */ }
.dt-color-btn { /* Color picker button */ }
.dt-color-indicator { /* Current color indicator dot */ }
.dt-label { /* Action label (Delete, etc.) */ }
```

### Width Picker

```css
.pywry-draw-width-picker { /* Line width selection popup */ }
.wp-row { /* Width option row */ }
.wp-line { /* Preview line at specified width */ }
```

### Drawing Context Menu

```css
.pywry-draw-ctx-menu { /* Right-click menu for drawings */ }
.cm-item { /* Context menu item */ }
.cm-icon { /* Item icon */ }
.cm-label { /* Item label */ }
.cm-shortcut { /* Keyboard shortcut */ }
.cm-sep { /* Separator */ }
.cm-danger { /* Danger action (red) */ }
```

---

## Settings Panel

Full settings dialog with sidebar tabs and form controls:

```css
.tv-settings-overlay { /* Modal backdrop overlay */ }
.tv-settings-panel { /* Settings panel container */ }
.tv-settings-header { /* Panel header with title and close button */ }
.tv-settings-close { /* Close button */ }

/* Sidebar */
.tv-settings-sidebar { /* Left sidebar with tab navigation */ }
.tv-settings-sidebar-tab { /* Individual sidebar tab */ }

/* Content */
.tv-settings-content { /* Right content area */ }
.tv-settings-content-pane { /* Individual content pane */ }
.tv-settings-body { /* Scrollable body area */ }
.tv-settings-section { /* Section with heading */ }
.tv-settings-title { /* Section title */ }
.tv-settings-section-body { /* Section content area */ }
.tv-settings-row { /* Form row (label + control) */ }

/* Form Controls */
.ts-swatch { /* Color swatch selector */ }
.ts-select { /* Select dropdown */ }
.ts-input { /* Text input */ }
.ts-input-sm { /* Small input */ }
.ts-input-wide { /* Wide input */ }
.ts-checkbox { /* Checkbox */ }
.tv-settings-slider { /* Range slider */ }
.tv-settings-slider-value { /* Slider value display */ }
.tv-settings-color-pair { /* Paired color swatches */ }
.ts-line-style-group { /* Line style selector group */ }
.ts-line-style-btn { /* Line style button (solid, dashed, dotted) */ }

/* Footer */
.tv-settings-footer { /* Footer with OK/Cancel buttons */ }
.ts-btn-cancel { /* Cancel button */ }
.ts-btn-ok { /* OK button */ }

/* Templates */
.ts-btn-template { /* Template dropdown trigger */ }
.tv-settings-template-menu { /* Template menu */ }
.tv-settings-template-item { /* Template option */ }
```

### Tab Bars

```css
.tv-settings-tabs { /* Settings horizontal tab bar */ }
.tv-settings-tab { /* Individual tab */ }
.tv-ind-settings-tabs { /* Indicator settings tab bar */ }
.tv-ind-settings-tab { /* Indicator settings tab */ }
```

---

## Indicator Panel

```css
.tv-indicators-overlay { /* Indicator panel backdrop */ }
.tv-indicators-panel { /* Indicator selection panel */ }
.tv-indicators-header { /* Panel header */ }
.tv-indicators-search { /* Search input area */ }
.tv-indicators-list { /* Scrollable indicator list */ }
.tv-indicators-section { /* Category section header */ }
.tv-indicator-item { /* Individual indicator option */ }
```

---

## Compare Symbol Dialog

```css
.tv-compare-panel { /* Compare dialog panel */ }
.tv-compare-header { /* Dialog header */ }
.tv-compare-search-row { /* Search input row */ }
.tv-compare-search-input { /* Symbol search input */ }
.tv-compare-add-btn { /* Add symbol button */ }
.tv-compare-results { /* Search results area */ }
.tv-compare-results-list { /* Results list */ }
.tv-compare-result-row { /* Individual result */ }
.tv-compare-result-symbol { /* Symbol name */ }
.tv-compare-list { /* Active comparisons list */ }
.tv-compare-symbol-row { /* Active comparison row */ }
.tv-compare-symbol-dot { /* Color indicator dot */ }
.tv-compare-symbol-remove { /* Remove button */ }
```

---

## Date Range Picker

Calendar-based date range selection dialog:

```css
.tv-date-range-overlay { /* Backdrop overlay */ }
.tv-date-range-panel { /* Dialog panel */ }
.tv-date-range-tabs { /* Preset tabs (1W, 1M, 3M, 6M, YTD, 1Y, Custom) */ }
.tv-date-range-tab { /* Individual tab */ }
.tv-date-range-body { /* Content area */ }

/* Calendar */
.tv-date-range-month-nav { /* Month navigation (prev/next) */ }
.tv-date-range-month-label { /* Current month display */ }
.tv-date-range-grid { /* Day grid (7-column calendar) */ }
.tv-date-range-day { /* Individual day cell */ }
.tv-date-range-week-header { /* Day-of-week header row */ }

/* Custom Range Inputs */
.tv-date-range-custom-fields { /* Start/end date inputs */ }
.tv-date-range-field { /* Date field */ }
.tv-date-range-input { /* Date text input */ }

/* Footer */
.tv-date-range-footer { /* Apply/cancel buttons */ }
.tv-date-range-btn-primary { /* Apply button */ }
.tv-date-range-btn-secondary { /* Cancel button */ }
```

---

## Symbol Search Dialog

```css
.tv-symbol-search-panel { /* Symbol search panel */ }
.tv-symbol-search-filters { /* Filter dropdowns */ }
.tv-symbol-search-filter-select { /* Filter select element */ }
.tv-symbol-search-results { /* Search results */ }
.tv-symbol-search-result-row { /* Individual result row */ }
```

---

## Save Button & Layout Modals

### Save Split Button

```css
.tvchart-save-split { /* Split button (save + dropdown caret) */ }
.tvchart-save-main { /* Main save button */ }
.tvchart-save-label { /* Save label text */ }
.tvchart-save-caret { /* Dropdown caret */ }
.tvchart-save-menu { /* Save dropdown menu */ }
.tvchart-save-menu-item { /* Menu item (Save, Save As, etc.) */ }
```

### Layout Modals

Modals for saving, opening, and managing chart layouts:

```css
.tvchart-layout-modal-overlay { /* Modal backdrop */ }
.tvchart-layout-modal-panel { /* Modal panel */ }
.tvchart-layout-modal-panel-save { /* Save layout variant */ }
.tvchart-layout-modal-panel-open { /* Open layout variant */ }

/* Header */
.tvchart-layout-modal-header { /* Modal header */ }
.tvchart-layout-modal-title { /* Title text */ }
.tvchart-layout-modal-close { /* Close button */ }

/* Search & Sort */
.tvchart-layout-search-input { /* Search input */ }
.tvchart-layout-sort-btn { /* Sort toggle button */ }

/* Layout List */
.tvchart-layout-list { /* Scrollable layout list */ }
.tvchart-layout-item { /* Individual layout entry */ }
.tvchart-layout-item-name { /* Layout name */ }
.tvchart-layout-item-meta { /* Layout metadata (date, etc.) */ }
.tvchart-layout-item-fav { /* Favorite toggle */ }
.tvchart-layout-item-delete { /* Delete button */ }

/* Save Input */
.tvchart-layout-save-input { /* Layout name input (save modal) */ }
.tvchart-layout-error { /* Validation error message */ }
.tvchart-layout-duplicate { /* Duplicate name warning */ }
```

---

## Miscellaneous

```css
.pywry-tvchart-plus-button { /* Floating "+" button for adding panes */ }
.pywry-tvchart-countdown { /* Countdown timer overlay */ }
```

---

## Responsive

```css
@media (max-width: 960px) {
    /* Reduced padding and font sizes for layout modals on narrow viewports */
}
```
