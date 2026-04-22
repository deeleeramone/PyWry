---
description: The PyWry event system — namespaced events, request/response round-trips, widget IDs, component IDs, and how tool results flow back to the agent.
---

# PyWry Event System — Agent Reference

> **The event bus is the plumbing underneath every MCP tool.**  You
> rarely need to think about it — the typed tools wrap emit + wait +
> state-poll for you — but when you reach for `send_event` or
> interpret tool results, this is how it works.

## Event names are namespaced

Every event has the form `namespace:event-name`, e.g.:

- `tvchart:symbol-search`     — ask the chart to open symbol search
- `tvchart:state-response`    — chart's reply with its current state
- `tvchart:data-request`      — chart asks Python for bars
- `tvchart:data-response`     — Python delivers bars
- `toolbar:request-state`     — ask a toolbar component for its value
- `toolbar:state-response`    — component's reply
- `chat:user-message`         — user typed something
- `chat:ai-response`          — model produced a token
- `pywry:update-theme`        — dark/light mode change

Never emit an event with a name that doesn't match `namespace:event-name`
— the framework rejects it.

## Widget IDs vs component IDs

**widget_id** — identifies the top-level PyWry widget (a chart, a grid,
a chat panel, a dashboard).  Every MCP tool takes `widget_id` as an
argument because all events route to the widget first.

**componentId** — identifies a child *inside* a widget (a specific
toolbar button, a marquee ticker slot, a chart pane).  Component IDs
are scoped to their containing widget.

When you call `send_event(widget_id, event_type, data)`, the
`widget_id` picks the target widget; anything identifying a specific
component goes in the `data` payload (typically as `data.componentId`
or `data.chartId`).

## Request / response pattern

Some events are fire-and-forget (e.g. `tvchart:symbol-search` —
"please do this").  Others are request/response round-trips where the
caller wants a reply (e.g. `tvchart:request-state` → `tvchart:state-response`).

The framework correlates request/response with a `context` token:

1. Emitter generates a random `context` token.
2. Emitter injects it into the request payload.
3. Listener sees the request, attaches the same `context` to its
   response, and emits the response event.
4. Emitter sees the matching `context` on the response and wakes up.

All of this is handled inside `request_response()` in
`pywry.mcp.state` — you never construct tokens yourself.  Typed MCP
tools that need a reply (`tvchart_request_state`,
`tvchart_list_indicators`) use this under the hood and return the
stripped response (no `context` token) in their tool result.

## How tool results reach the agent

```
Agent             MCP Server          PyWry Widget (JS)
  │                   │                       │
  │ tool call ──────► │                       │
  │                   │ widget.emit() ──────► │
  │                   │                       │ (updates chart)
  │                   │                       │
  │                   │ ◄───── bridge.emit()  │
  │                   │ (state-response)      │
  │                   │                       │
  │ ◄──── tool result │                       │
  │ (includes state)  │                       │
```

Mutating tools (`tvchart_symbol_search`, `tvchart_change_interval`)
poll `tvchart:request-state` after emitting the mutation, wait for the
chart to actually reflect the change, and return the real post-change
state in the tool result.  The `state` field in the tool result
contains the SAME structure as a direct call to
`tvchart_request_state`.

If the mutation didn't settle in time, the result contains a `note`
field explaining the discrepancy — relay the note to the user, do
not invent state.

## Emitting events from tools — `send_event`

Only reach for `send_event` when no typed MCP tool exists for the
target event.  It's a raw passthrough with no state polling:

```
send_event(widget_id, event_type, data)
  → { "widget_id": ..., "event_sent": true, "event_type": ... }
```

Example — apply a rare tvchart option with no typed wrapper:

```
send_event(
  widget_id="chart",
  event_type="tvchart:apply-options",
  data={"chartOptions": {"timeScale": {"secondsVisible": False}}},
)
```

The returned `event_sent: true` means the event was successfully
handed to the widget — it does NOT mean the JS handler ran
successfully.  For confirmation, follow up with
`tvchart_request_state` to read the new state.

## Event capture (`get_events`)

Some events fire from the widget *to* Python (e.g. the user clicked a
bar, moved the crosshair).  These are automatically captured into a
per-widget event buffer and can be retrieved with:

```
get_events(widget_id, event_types=[...], clear=True)
  → { "events": [{ "event_type": ..., "data": ..., "label": ... }, ...] }
```

Default captured events for charts:

- `tvchart:click`
- `tvchart:crosshair-move`
- `tvchart:visible-range-change`
- `tvchart:drawing-added`
- `tvchart:drawing-deleted`
- `tvchart:open-layout-request`
- `tvchart:interval-change`
- `tvchart:chart-type-change`

Use `get_events` if the user asks "what did I just click" or "what
was the last drawing I added".

## Don'ts

- Do NOT synthesise event payloads.  Only report event data the
  framework actually handed you.
- Do NOT emit events whose name doesn't match `ns:name` — they're
  rejected.
- Do NOT emit to a widget id that isn't registered — the tool will
  return an error listing the registered widgets; correct and retry.
- Do NOT assume `event_sent: true` means the downstream JS succeeded.
  When it matters, follow up with `tvchart_request_state` (or the
  relevant state query) to confirm.
