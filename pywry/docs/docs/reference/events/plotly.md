# Plotly Events (plotly:*)

## User Interactions (JS → Python)

| Event | Payload |
|-------|---------|
| `plotly:click` | `{chartId, widget_type, points, point_indices, curve_number, event}` |
| `plotly:hover` | `{chartId, widget_type, points, point_indices, curve_number}` |
| `plotly:unhover` | `{chartId}` |
| `plotly:selected` | `{chartId, widget_type, points, point_indices, range, lassoPoints}` |
| `plotly:deselect` | `{chartId}` |
| `plotly:relayout` | `{chartId, widget_type, relayout_data}` |
| `plotly:state-response` | `{chartId, layout, data}` |
| `plotly:export-response` | `{data: [{traceIndex, name, x, y, type}, ...]}` |

**Point structure:**

```python
{
    "curveNumber": 0,
    "pointNumber": 5,
    "pointIndex": 5,
    "x": 2.5,
    "y": 10.3,
    "z": None,
    "text": "label",
    "customdata": {...},
    "data": {...},
    "trace_name": "Series A"
}
```

## Chart Updates (Python → JS)

| Event | Payload |
|-------|---------|
| `plotly:update-figure` | `{figure, chartId?, config?, animate?}` |
| `plotly:update-layout` | `{layout, chartId?}` |
| `plotly:update-traces` | `{update, indices, chartId?}` |
| `plotly:replace` | `{figure, chartId?}` |
| `plotly:reset-zoom` | `{chartId?}` |
| `plotly:request-state` | `{chartId?}` |
| `plotly:export-data` | `{chartId?}` |
