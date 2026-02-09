# API Reference

Complete API documentation for PyWry.

## Core

| Module | Description |
|--------|-------------|
| [pywry](pywry.md) | Main `PyWry` class for native windows |
| [InlineWidget](inline-widget.md) | Browser/notebook widgets via FastAPI |

## Events

| Module | Description |
|--------|-------------|
| [Event Reference](events.md) | All events, payloads, and the JavaScript bridge API |

## Models & Configuration

| Module | Description |
|--------|-------------|
| [pywry.models](models.md) | `HtmlContent`, `WindowConfig`, `WindowMode` |
| [pywry.config](config.md) | Settings classes and configuration |

## State Management

| Module | Description |
|--------|-------------|
| [State](state.md) | `WidgetStore`, `EventBus`, `CallbackRegistry`, Redis backend |

## Widgets & UI

| Module | Description |
|--------|-------------|
| [pywry.widget](widget.md) | Notebook widget classes |
| [Toolbar](../components/index.md) | Toolbar components |
| [CSS Reference](css.md) | CSS variables, classes, and theming |

## Integrations

| Module | Description |
|--------|-------------|
| [pywry.plotly_config](plotly-config.md) | Plotly configuration |
| [pywry.grid](grid.md) | AG Grid configuration |
| [MCP Server](mcp.md) | Model Context Protocol for AI agents |

## Utilities

| Module | Description |
|--------|-------------|
| [pywry.callbacks](callbacks.md) | Callback registry |
| [pywry.asset_loader](asset-loader.md) | Asset loading |
| [pywry.hot_reload](hot-reload.md) | Hot reload manager |
