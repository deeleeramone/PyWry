# System Events (pywry:*)

## Lifecycle Events (JS → Python)

| Event | Payload | Description |
|-------|---------|-------------|
| `pywry:ready` | `{}` | Window/widget initialized and ready |
| `pywry:result` | `any` | Data from `window.pywry.result(data)` |
| `pywry:message` | `any` | Data from `window.pywry.message(data)` |
| `pywry:content-request` | `{widget_type, window_label, reason}` | Window requests content |
| `pywry:disconnect` | `{}` | Widget disconnected (browser/inline mode) |
| `pywry:close` | `{label}` | Window close requested |

## Window Events (JS → Python)

| Event | Payload | Description |
|-------|---------|-------------|
| `window:closed` | `{label}` | Window was closed |
| `window:hidden` | `{label}` | Window was hidden |

## Content & Styling (Python → JS)

| Event | Payload | Description |
|-------|---------|-------------|
| `pywry:set-content` | `{id?, selector?, text?, html?}` | Update element text/HTML |
| `pywry:set-style` | `{id?, selector?, styles: {}}` | Update element CSS |
| `pywry:inject-css` | `{css, id?}` | Inject CSS (id for replacement) |
| `pywry:remove-css` | `{id}` | Remove injected CSS by id |
| `pywry:update-html` | `{html}` | Replace entire page content |
| `pywry:update-theme` | `{theme}` | Switch theme (`dark` or `light`) |

## Notifications & Actions (Python → JS)

| Event | Payload | Description |
|-------|---------|-------------|
| `pywry:alert` | `{message, type?, title?, duration?, position?, callback_event?}` | Toast notification |
| `pywry:download` | `{content, filename, mimeType?}` | Trigger file download |
| `pywry:navigate` | `{url}` | Navigate to URL |
| `pywry:refresh` | `{}` | Request content refresh |
| `pywry:cleanup` | `{}` | Cleanup resources (native mode) |

**Alert types:** `info`, `success`, `warning`, `error`, `confirm`

**Alert positions:** `top-right` (default), `top-left`, `bottom-right`, `bottom-left`
