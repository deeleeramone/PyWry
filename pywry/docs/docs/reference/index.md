# API Reference

Complete API documentation for PyWry.

## Core

| Module | Description |
|--------|-------------|
| [pywry](pywry.md) | Main `PyWry` class for native windows |
| [InlineWidget](inline-widget.md) | Browser/notebook widgets via FastAPI |
| [Widget](widget.md) | Notebook widget classes |
| [Runtime](runtime.md) | PyTauri subprocess management |
| [WindowProxy](window-proxy.md) | Native window control handle |
| [MenuProxy](menu-proxy.md) | Native menu management |
| [TrayProxy](tray-proxy.md) | System tray management |

## Events

| Module | Description |
|--------|-------------|
| [Event Reference](events/index.md) | All events, payloads, and the JavaScript bridge API |

## Models & Configuration

| Module | Description |
|--------|-------------|
| [pywry.models](models.md) | `HtmlContent`, `WindowConfig`, `WindowMode` |
| [pywry.config](config.md) | Settings classes and configuration |
| [pywry.types](types.md) | Type aliases and enums |
| [pywry.exceptions](exceptions.md) | Exception classes |

## CSS

| Page | Description |
|------|-------------|
| [CSS Overview](css/index.md) | Variables, theming, custom CSS injection |
| [Core Stylesheet](css/core.md) | Layout, toolbar, buttons, inputs, controls, modal, scrollbars |
| [Chat Stylesheet](css/chat.md) | Chat UI classes |
| [Toast Stylesheet](css/toast.md) | Toast notification classes |
| [TradingView Stylesheet](css/tvchart.md) | TradingView chart UI classes |

## Chat

| Module | Description |
|--------|-------------|
| [pywry.chat](chat.md) | Core ACP-aligned chat models, config, and HTML builder |
| [pywry.chat (manager, updates, artifacts)](chat-manager.md) | ChatManager orchestrator, ACP session updates, artifacts, and providers |

## State Management

| Module | Description |
|--------|-------------|
| [State](state.md) | `WidgetStore`, `EventBus`, `CallbackRegistry`, Redis backend |
| [State Mixins](state-mixins.md) | Grid, Plotly, TVChart, Toolbar state mixins |

## Toolbar & Modal

| Module | Description |
|--------|-------------|
| [Modal](modal.md) | Modal dialog API |
| [Toolbar Functions](toolbar-functions.md) | Secret management and event utilities |

Toolbar component signatures are documented inline on each [Components](../components/index.md) page.

## Utilities

| Module | Description |
|--------|-------------|
| [pywry.callbacks](callbacks.md) | Callback registry |
| [pywry.asset_loader](asset-loader.md) | Asset loading |
| [pywry.hot_reload](hot-reload.md) | Hot reload manager |
| [pywry.templates](templates.md) | HTML template builder |
| [pywry.scripts](scripts.md) | JavaScript bridge code |
