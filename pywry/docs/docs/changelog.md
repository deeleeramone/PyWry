# Changelog

## Version 2.0.0

PyWry 2.0 is a major release with a completely redesigned architecture and API.

### Highlights

- **Unified API** — Single `PyWry` class works across all rendering modes
- **Native window support** — Full PyTauri/Tauri integration with WebView2/WebKit
- **Toolbar system** — 18 declarative Pydantic components
- **Event system** — Bidirectional Python ↔ JavaScript communication
- **Deploy mode** — Redis backend for horizontal scaling
- **MCP server** — AI agent integration via Model Context Protocol

### New Features

- Native desktop windows with OS webview
- anywidget-based Jupyter widgets
- Browser mode with FastAPI server
- Comprehensive toolbar component library
- Built-in Plotly and AgGrid integration
- Toast notification system
- Hot reload for development
- Layered configuration system
- Security presets and CSP support

### Breaking Changes

This is a complete rewrite. If you were using PyWry 1.x, please refer to the updated documentation for the new API.
