# AG Grid Events (grid:*)

## User Interactions (JS → Python)

| Event | Payload |
|-------|---------|
| `grid:row-selected` | `{gridId, widget_type, rows}` |
| `grid:cell-click` | `{gridId, widget_type, rowIndex, colId, value, data}` |
| `grid:cell-double-click` | `{gridId, widget_type, rowIndex, colId, value, data}` |
| `grid:cell-edit` | `{gridId, widget_type, rowIndex, rowId, colId, oldValue, newValue, data}` |
| `grid:filter-changed` | `{gridId, widget_type, filterModel}` |
| `grid:sort-changed` | `{gridId, widget_type, sortModel}` |
| `grid:data-truncated` | `{gridId, widget_type, displayedRows, truncatedRows, message}` |
| `grid:mode` | `{gridId, widget_type, mode, serverSide, totalRows, blockSize, message}` |
| `grid:request-page` | `{gridId, widget_type, startRow, endRow, sortModel, filterModel}` |
| `grid:state-response` | `{gridId, columnState, filterModel, sortModel, context?}` |
| `grid:export-csv` | `{gridId, data}` |

## Grid Updates (Python → JS)

| Event | Payload |
|-------|---------|
| `grid:update-data` | `{data, gridId?, strategy?}` |
| `grid:update-columns` | `{columnDefs, gridId?}` |
| `grid:update-cell` | `{rowId, colId, value, gridId?}` |
| `grid:update-grid` | `{data?, columnDefs?, restoreState?, gridId?}` |
| `grid:request-state` | `{gridId?, context?}` |
| `grid:restore-state` | `{state, gridId?}` |
| `grid:reset-state` | `{gridId?, hard?}` |
| `grid:update-theme` | `{theme, gridId?}` |
| `grid:page-response` | `{gridId, rows, totalRows, isLastPage, requestId}` |
| `grid:show-notification` | `{message, duration?, gridId?}` |

**Update strategies for `grid:update-data`:** `set` (default — replace all), `append`, `update`
