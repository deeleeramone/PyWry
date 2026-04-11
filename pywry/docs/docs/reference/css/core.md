# Core Stylesheet

Source: `frontend/style/pywry.css` — Main stylesheet covering layout, toolbar, all form controls, modal, scrollbars, and utility classes.

---

## Theme Classes

Applied to the root element or widget container:

| Class | Description |
|:------|:------------|
| `.pywry-theme-dark` | Dark theme (default) |
| `.pywry-theme-light` | Light theme |
| `.pywry-theme-system` | Follow OS preference |

---

## Layout

### Widget Container

```css
.pywry-widget { /* Main widget container — flex column, sets width/height via variables */ }
.pywry-container { /* Content container — flex: 1, fills remaining space */ }
```

### Native Window

```css
html.pywry-native { /* Native Tauri window — full viewport height */ }
html.dark { /* Dark mode applied to <html> */ }
html.light { /* Light mode applied to <html> */ }
```

### Content Wrappers

```css
.pywry-wrapper-header { /* Header wrapper with bottom border */ }
.pywry-wrapper-left { /* Left sidebar wrapper */ }
.pywry-wrapper-right { /* Right sidebar wrapper */ }
.pywry-wrapper-top { /* Top wrapper */ }
.pywry-wrapper-bottom { /* Bottom wrapper */ }
.pywry-wrapper-inside { /* Floating overlay wrapper */ }
.pywry-body-scroll { /* Scrollable body content */ }
.pywry-content { /* Main content area */ }
.pywry-scroll-container { /* Scrollable content within wrapper */ }
```

---

## Toolbar

### Positions

```css
.pywry-toolbar { /* Base toolbar */ }
.pywry-toolbar-top { /* Top position — horizontal strip above content */ }
.pywry-toolbar-bottom { /* Bottom position — horizontal strip below content */ }
.pywry-toolbar-left { /* Left sidebar — vertical strip */ }
.pywry-toolbar-right { /* Right sidebar — vertical strip */ }
.pywry-toolbar-header { /* Header position — with bottom border */ }
.pywry-toolbar-footer { /* Footer position — with top border */ }
.pywry-toolbar-inside { /* Floating overlay inside content area */ }
```

### Content & Layout

```css
.pywry-toolbar-content { /* Flex container for toolbar items — wraps, gaps */ }
```

### Collapsible & Resizable

```css
.pywry-collapsed { /* Collapsed state — applied when toolbar is hidden */ }
[data-collapsible="true"] { /* Toolbar with collapse toggle button */ }
[data-resizable="true"] { /* Toolbar with drag-to-resize handle */ }
```

---

## Buttons

### Variants

```css
.pywry-btn { /* Base button — primary style by default */ }
.pywry-btn.pywry-btn-secondary { /* Secondary — subtle background */ }
.pywry-btn.pywry-btn-neutral { /* Neutral — blue accent */ }
.pywry-btn.pywry-btn-ghost { /* Ghost — transparent background */ }
.pywry-btn.pywry-btn-outline { /* Outline — border only */ }
.pywry-btn.pywry-btn-danger { /* Danger — red */ }
.pywry-btn.pywry-btn-warning { /* Warning — orange */ }
.pywry-btn.pywry-btn-icon { /* Icon-only — square, no text */ }
```

### Sizes

```css
.pywry-btn-xs { /* Extra small */ }
.pywry-btn-sm { /* Small */ }
.pywry-btn-lg { /* Large */ }
.pywry-btn-xl { /* Extra large */ }
```

---

## Inputs

### Text & Number

```css
.pywry-input { /* Base input element */ }
.pywry-input-group { /* Label + input wrapper */ }
.pywry-input-inline { /* Inline variant — label beside input */ }
.pywry-input-label { /* Input label */ }
.pywry-input-text { /* Text input */ }
.pywry-input-number { /* Number input */ }
.pywry-number-wrapper { /* Number input wrapper with spinners */ }
.pywry-number-spinner { /* Spinner buttons container */ }
```

### Date

```css
.pywry-input-date { /* Date input */ }
.pywry-date-wrapper { /* Date input wrapper */ }
```

### Range

```css
.pywry-input-range { /* Range input (single slider) */ }
```

### Secret

```css
.pywry-input-secret { /* Password/secret input */ }
.pywry-secret-wrapper { /* Secret input wrapper */ }
.pywry-secret-actions { /* Action buttons container */ }
.pywry-secret-btn { /* Secret action button */ }
.pywry-secret-copy { /* Copy button */ }
.pywry-secret-confirm { /* Confirm button (green) */ }
.pywry-secret-cancel { /* Cancel button (red) */ }
.pywry-secret-edit-actions { /* Edit mode actions */ }
.pywry-secret-textarea { /* Secret textarea (expanded mode) */ }
```

### Textarea

```css
.pywry-textarea { /* Textarea element */ }
.pywry-textarea-group { /* Textarea + label wrapper */ }
```

---

## Select & Dropdown

```css
.pywry-select { /* Native-style select dropdown */ }
.pywry-dropdown { /* Custom dropdown component */ }
.pywry-dropdown-selected { /* Selected value display */ }
.pywry-dropdown-menu { /* Dropdown menu container */ }
.pywry-dropdown-option { /* Individual option */ }
.pywry-dropdown-arrow { /* Arrow indicator */ }
.pywry-dropdown-text { /* Text label in dropdown */ }
.pywry-dropdown-up { /* Opens upward variant */ }
.pywry-searchable { /* Searchable dropdown variant */ }
.pywry-select-header { /* Select header area */ }
.pywry-select-options { /* Options container */ }
```

### Multi-Select

```css
.pywry-multiselect { /* Multi-select component */ }
.pywry-multiselect-header { /* Header showing selected count */ }
.pywry-multiselect-search { /* Search input within dropdown */ }
.pywry-multiselect-options { /* Options list */ }
.pywry-multiselect-option { /* Individual option */ }
.pywry-multiselect-checkbox { /* Checkbox in multi-select */ }
.pywry-multiselect-label { /* Label in multi-select */ }
.pywry-multiselect-actions { /* Action buttons (Select All / Clear) */ }
.pywry-multiselect-action { /* Individual action button */ }
```

### Search Input

```css
.pywry-search-wrapper { /* Search input wrapper */ }
.pywry-search-icon { /* Search magnifying glass icon */ }
.pywry-search-input { /* Search input field */ }
.pywry-search-inline { /* Inline search variant */ }
```

---

## Toggle & Checkbox

```css
.pywry-toggle { /* Toggle switch container */ }
.pywry-toggle-input { /* Hidden toggle input */ }
.pywry-toggle-slider { /* Toggle background track (legacy) */ }
.pywry-toggle-track { /* Toggle track */ }
.pywry-toggle-thumb { /* Toggle thumb / knob */ }

.pywry-checkbox { /* Checkbox wrapper */ }
.pywry-checkbox-input { /* Checkbox input element */ }
.pywry-checkbox-box { /* Checkbox visual box */ }
.pywry-checkbox-label { /* Checkbox label text */ }
```

---

## Radio Group

```css
.pywry-radio-group { /* Radio group container */ }
.pywry-radio-horizontal { /* Horizontal layout */ }
.pywry-radio-vertical { /* Vertical layout */ }
.pywry-radio-option { /* Individual radio option */ }
.pywry-radio-button { /* Radio visual element */ }
.pywry-radio-label { /* Radio label text */ }
```

---

## Tab Group

```css
.pywry-tab-group { /* Tab container */ }
.pywry-tab { /* Individual tab */ }
.pywry-tab-active { /* Active tab state */ }
.pywry-tab-sm { /* Small tab size */ }
.pywry-tab-lg { /* Large tab size */ }
```

---

## Slider & Range

```css
.pywry-slider { /* Single slider wrapper */ }
.pywry-slider-input { /* Range input element */ }
.pywry-slider-value { /* Value display */ }

.pywry-range-group { /* Dual-range group container */ }
.pywry-range-track { /* Range track wrapper */ }
.pywry-range-track-bg { /* Track background */ }
.pywry-range-track-fill { /* Filled portion between handles */ }
.pywry-range-separator { /* Separator between min/max values */ }
```

---

## Marquee & Ticker

```css
.pywry-marquee { /* Scrolling container */ }
.pywry-marquee-track { /* Animated track */ }
.pywry-marquee-content { /* Content wrapper (duplicated for seamless loop) */ }

/* Direction */
.pywry-marquee-left { /* Scroll left (default) */ }
.pywry-marquee-right { /* Scroll right */ }
.pywry-marquee-up { /* Scroll up */ }
.pywry-marquee-down { /* Scroll down */ }

/* Behavior */
.pywry-marquee-static { /* No animation */ }
.pywry-marquee-pause { /* Pause on hover */ }
.pywry-marquee-vertical { /* Vertical layout */ }
.pywry-marquee-alternate { /* Bounce back-and-forth */ }
.pywry-marquee-slide { /* Play once and stop */ }
.pywry-marquee-clickable { /* Clickable items */ }
.pywry-marquee-separator { /* Separator between items */ }

/* Ticker Items */
.pywry-ticker-item { /* Individual ticker entry */ }
.pywry-ticker-item.stock-up { /* Price up — green indicator */ }
.pywry-ticker-item.stock-down { /* Price down — red indicator */ }
.pywry-ticker-item.ticker-neutral { /* Neutral state */ }
```

---

## Div

```css
.pywry-div { /* Div component — custom HTML container in toolbar */ }
```

---

## Grid & Plotly Containers

```css
.pywry-grid { /* AG Grid container */ }
.pywry-grid-wrapper { /* Grid wrapper with sizing */ }
.pywry-plotly { /* Plotly chart container */ }
.pywry-plotly-container { /* Plotly wrapper */ }
```

### AG Grid Theme Integration

```css
.ag-theme-quartz-dark,
.ag-theme-quartz {
    --ag-browser-color-scheme: dark; /* or light */
    --ag-wrapper-border-radius: 0;
    --ag-scrollbar-size: 10px;
    --ag-scrollbar-color: var(--pywry-scrollbar-thumb);
    --ag-scrollbar-track-color: transparent;
    --ag-input-focus-border-color: var(--pywry-accent);
    --ag-range-selection-border-color: var(--pywry-accent);
}
```

---

## Modal

```css
.pywry-modal-overlay { /* Backdrop overlay */ }
.pywry-modal-overlay.pywry-modal-open { /* Overlay visible state */ }
.pywry-modal-container { /* Modal box */ }

/* Sizes */
.pywry-modal-sm { /* Small — 400px */ }
.pywry-modal-md { /* Medium — 560px */ }
.pywry-modal-lg { /* Large — 720px */ }
.pywry-modal-xl { /* Extra large — 960px */ }
.pywry-modal-full { /* Full width */ }

/* Inner elements */
.pywry-modal-header { /* Modal header */ }
.pywry-modal-title { /* Modal title */ }
.pywry-modal-body { /* Modal body/content */ }
.pywry-modal-footer { /* Modal footer */ }
.pywry-modal-close { /* Close button */ }
.pywry-modal-body-locked { /* Body scroll lock (applied to <body>) */ }
```

---

## Tooltips

```css
.pywry-tooltip { /* Tooltip element */ }
.pywry-tooltip.visible { /* Visible state */ }
.pywry-tooltip.arrow-bottom { /* Arrow points down */ }
.pywry-tooltip.arrow-top { /* Arrow points up */ }
```

---

## Scrollbars

Custom scrollbar system for native Tauri windows:

```css
.pywry-scroll-wrapper { /* Scroll container wrapper */ }
.pywry-scroll-wrapper.has-scrollbar-v { /* Has vertical scrollbar */ }
.pywry-scroll-wrapper.has-scrollbar-h { /* Has horizontal scrollbar */ }
.pywry-scroll-wrapper.has-both-scrollbars { /* Both scrollbars visible */ }
.pywry-scroll-wrapper.is-scrolling { /* Currently actively scrolling */ }
.pywry-scroll-container { /* Scrollable content area */ }
.pywry-scrollbar-track-v { /* Vertical scrollbar track */ }
.pywry-scrollbar-track-h { /* Horizontal scrollbar track */ }
.pywry-scrollbar-thumb-v { /* Vertical scrollbar thumb */ }
.pywry-scrollbar-thumb-h { /* Horizontal scrollbar thumb */ }
```

---

## State Classes

```css
.pywry-disabled { /* Disabled state — reduced opacity, no pointer events */ }
.pywry-collapsed { /* Collapsed toolbar */ }
.pywry-loading { /* Loading state */ }
.pywry-selected { /* Selected state */ }
.pywry-open { /* Open state (dropdowns, menus) */ }
```

---

## Utility Classes

### Background Colors

```css
.pywry-bg-primary { /* var(--pywry-bg-primary) */ }
.pywry-bg-secondary { /* var(--pywry-bg-secondary) */ }
.pywry-bg-tertiary { /* var(--pywry-bg-tertiary) */ }
.pywry-bg-quartary { /* var(--pywry-bg-quartary) */ }
.pywry-bg-accent { /* var(--pywry-accent) */ }
.pywry-bg-hover { /* var(--pywry-bg-hover) */ }
```

### Text Colors

```css
.pywry-text-primary { /* var(--pywry-text-primary) */ }
.pywry-text-secondary { /* var(--pywry-text-secondary) */ }
.pywry-text-muted { /* var(--pywry-text-muted) */ }
.pywry-text-accent { /* var(--pywry-text-accent) */ }
```

### Borders

```css
.pywry-border-theme { /* var(--pywry-border-color) */ }
.pywry-border-outline { /* Outline border */ }
.pywry-border-modal { /* Modal border */ }
```

### Icons

```css
.pywry-ghost-icon { /* Ghost icon color */ }
.pywry-info-icon { /* Info icon color */ }
```
