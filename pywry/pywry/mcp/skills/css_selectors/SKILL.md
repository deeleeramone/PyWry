# CSS Selectors

> Target elements for `set_content` and `set_style` updates using CSS selectors or component IDs.

## Targeting by Component ID (Preferred)

The most reliable way to target elements is by `component_id`:

```python
# When creating content, always use component_id
content = Div(
    content="Hello",
    component_id="main-content",  # This becomes the element's id
)

# Target by id in set_content/set_style
set_content(widget_id, component_id="main-content", text="Updated!")
set_style(widget_id, component_id="main-content", styles={"color": "red"})
```

### Why component_id is Preferred

| Aspect | component_id | CSS Selector |
|--------|-------------|--------------|
| Reliability | Always unique | May match multiple elements |
| Refactoring | Survives DOM changes | May break on restructure |
| Performance | Direct lookup | May scan document |
| Clarity | Self-documenting | Requires knowledge of DOM |

## Targeting by CSS Selector

When you don't have a `component_id`, use CSS selectors:

```python
# By element type
set_style(widget_id, selector="h1", styles={"fontSize": "24px"})

# By class
set_style(widget_id, selector=".status-indicator", styles={"display": "block"})

# By attribute
set_content(widget_id, selector="[data-ticker='AAPL']", text="$185.00")

# Combined selectors
set_style(widget_id, selector=".toolbar button.primary", styles={"opacity": "0.5"})

# First/last/nth-child
set_style(widget_id, selector="ul li:first-child", styles={"fontWeight": "bold"})
```

## Common Selector Patterns

### Basic Selectors

| Selector | Matches | Example |
|----------|---------|---------|
| `#myid` | Element with id="myid" | `#header` |
| `.myclass` | Elements with class="myclass" | `.card` |
| `div` | All div elements | `span` |
| `*` | All elements | `*` |

### Combinators

| Selector | Matches | Example |
|----------|---------|---------|
| `div.myclass` | Divs with class="myclass" | `button.primary` |
| `div > p` | Direct child p of div | `.card > .title` |
| `div p` | Any descendant p of div | `.sidebar a` |
| `div + p` | p immediately after div | `h1 + p` |
| `div ~ p` | All p siblings after div | `h1 ~ p` |

### Attribute Selectors

| Selector | Matches | Example |
|----------|---------|---------|
| `[data-x]` | Elements with data-x attribute | `[data-ticker]` |
| `[data-x="val"]` | Elements where data-x="val" | `[data-ticker="AAPL"]` |
| `[data-x^="pre"]` | data-x starts with "pre" | `[data-id^="user-"]` |
| `[data-x$="suf"]` | data-x ends with "suf" | `[href$=".pdf"]` |
| `[data-x*="sub"]` | data-x contains "sub" | `[class*="btn"]` |

### Pseudo-Selectors

| Selector | Matches | Example |
|----------|---------|---------|
| `:first-child` | First child of parent | `li:first-child` |
| `:last-child` | Last child of parent | `li:last-child` |
| `:nth-child(n)` | Nth child of parent | `tr:nth-child(2)` |
| `:nth-child(odd)` | Odd children | `tr:nth-child(odd)` |
| `:nth-child(even)` | Even children | `tr:nth-child(even)` |
| `:not(selector)` | Elements not matching | `div:not(.hidden)` |
| `:empty` | Elements with no children | `p:empty` |

## Practical Examples

### Updating Multiple Elements
```python
# Update all prices
set_style(widget_id, selector=".price", styles={"color": "green"})

# Update all elements with data-status="stale"
set_style(widget_id, selector="[data-status='stale']", styles={"opacity": "0.5"})
```

### Targeting by Data Attribute (Dynamic Content)
```python
# Create content with data attributes
html = """
<div class="ticker-row" data-ticker="AAPL">
    <span class="symbol">AAPL</span>
    <span class="price">$185.00</span>
</div>
<div class="ticker-row" data-ticker="GOOGL">
    <span class="symbol">GOOGL</span>
    <span class="price">$142.00</span>
</div>
"""

# Update specific ticker
set_content(widget_id, selector="[data-ticker='AAPL'] .price", text="$186.50")
```

### Table Row Styling
```python
# Highlight header row
set_style(widget_id, selector="table tr:first-child", styles={
    "backgroundColor": "var(--bg-secondary)",
    "fontWeight": "bold",
})

# Zebra striping
set_style(widget_id, selector="table tr:nth-child(even)", styles={
    "backgroundColor": "var(--bg-tertiary)",
})
```

## Best Practices

### 1. Prefer component_id Over Selectors
```python
# ✓ Preferred - explicit and stable
set_content(widget_id, component_id="price-display", text="$100")

# ✓ OK for bulk updates
set_style(widget_id, selector=".price", styles={"color": "green"})

# ✗ Fragile - depends on DOM structure
set_style(widget_id, selector="div > div > span:nth-child(2)", styles=...)
```

### 2. Use Data Attributes for Dynamic Content
```python
# Create with data attributes
content = Div(
    content='<span data-field="status">Unknown</span>',
    component_id="card",
)

# Update by data attribute
set_content(widget_id, selector="[data-field='status']", text="Active")
```

### 3. Avoid Overly Specific Selectors
```python
# ✗ Bad - breaks if DOM changes
selector = "div.container > div.row:nth-child(2) > div.col > span.value"

# ✓ Good - targeted but flexible
selector = ".row .value"  # or use component_id
```

### 4. Test Selectors First
Use browser DevTools to test selectors:
1. Open DevTools (F12)
2. Go to Console
3. Type: `document.querySelectorAll(".your-selector")`
4. Verify it matches expected elements

## Performance Considerations

- `component_id` → Direct `getElementById` (fastest)
- ID selector (`#myid`) → Very fast
- Class selector (`.myclass`) → Fast
- Complex selectors → Slower, may need traversal
- Universal selector (`*`) → Slowest

For frequent updates (animations, live data), prefer `component_id` or simple selectors.
