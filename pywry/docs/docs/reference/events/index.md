# Event Reference

Complete reference for all PyWry events, payloads, and the JavaScript bridge API.

## Event Format

All events follow the `namespace:event-name` pattern:

| Part | Rules | Examples |
|------|-------|----------|
| namespace | Starts with letter, alphanumeric | `app`, `plotly`, `grid`, `myapp` |
| event-name | Starts with letter, alphanumeric + hyphens | `click`, `row-select`, `update-data` |

**Reserved namespaces:** `pywry:*`, `plotly:*`, `grid:*`, `toolbar:*`, `auth:*`, `chat:*`, `tray:*`, `menu:*`, `modal:*`, `tvchart:*`

## Namespace Reference

| Namespace | Description |
|-----------|-------------|
| [System (`pywry:*`)](system.md) | Lifecycle, content, styling, notifications |
| [Plotly (`plotly:*`)](plotly.md) | Chart interactions and updates |
| [AG Grid (`grid:*`)](grid.md) | Table interactions and data updates |
| [Toolbar (`toolbar:*`)](toolbar.md) | Component state and marquee |
| [Auth (`auth:*`)](auth.md) | OAuth2 login/logout flow |
| [Chat (`chat:*`)](chat.md) | Chat messages, threads, artifacts |
| [TradingView (`tvchart:*`)](tvchart.md) | Datafeed protocol and chart control |
| [Tray (`tray:*`)](tray.md) | System tray icon interactions |
| [Menu (`menu:*`)](menu.md) | Native menu item clicks |
| [Modal (`modal:*`)](modal.md) | Modal dialog control |

See also: [JavaScript API](javascript-api.md) for the `window.pywry` bridge object and Tauri access.
