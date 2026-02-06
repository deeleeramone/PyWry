# Features

| Feature | Description |
|---------|-------------|
| Native Windows | OS webview (WebView2/WebKit), few MBs vs Electron 150MB+ |
| Jupyter Widgets | anywidget with traitlet sync, IFrame fallback |
| Browser Mode | FastAPI + WebSocket, Redis for scaling |
| Toolbar System | 18 Pydantic components, 7 layout positions |
| Two-Way Events | Python-JS communication, pre-wired Plotly/AgGrid events |
| Marquee Ticker | Scrolling text with dynamic updates |
| AgGrid Tables | Pandas-AgGrid conversion, grid events, context menus |
| Plotly Charts | Pre-wired plot events, custom modebar buttons |
| Toast Notifications | info, success, warning, error, confirm |
| Theming | Light/dark modes, 60+ CSS variables |
| Secrets | Server-side storage, never rendered in HTML |
| Security | Token auth, CSP headers, production presets |
| Configuration | TOML files, env vars, security presets |
| Hot Reload | Live CSS/JS updates |
| Deploy Mode | Redis backend for horizontal scaling |

## Rendering Paths

| Environment | Path | Backend |
|-------------|------|---------|
| Desktop | Native Window | PyTauri + OS webview |
| Jupyter + anywidget | Notebook Widget | anywidget comms |
| Jupyter (fallback) | Inline IFrame | FastAPI server |
| Headless/SSH | Browser Mode | FastAPI + browser |

## Toolbar Components

| Component | Type |
|-----------|------|
| Button | Action |
| Select, MultiSelect, RadioGroup, TabGroup | Selection |
| TextInput, TextArea, SearchInput, SecretInput | Text |
| NumberInput, DateInput, SliderInput, RangeInput | Numeric |
| Toggle, Checkbox | Boolean |
| Div, Marquee, TickerItem | Layout |

## Built-in Events

| Event | Direction | Description |
|-------|-----------|-------------|
| `pywry:set-content` | Python-JS | Update element text/HTML |
| `pywry:set-style` | Python-JS | Update element styles |
| `pywry:inject-css` | Python-JS | Inject CSS |
| `pywry:alert` | Python-JS | Toast notification |
| `pywry:download` | Python-JS | Trigger download |
| `plotly:click` | JS-Python | Chart point clicked |
| `plotly:update-layout` | Python-JS | Update chart layout |
| `grid:row-selected` | JS-Python | Grid row selected |
| `grid:cell-click` | JS-Python | Grid cell clicked |

## Configuration

Priority (highest last):
1. Built-in defaults
2. `pyproject.toml` `[tool.pywry]`
3. `pywry.toml`
4. `~/.config/pywry/config.toml`
5. Environment variables `PYWRY_*`

## Platform Support

| Platform | Window | Notebook | Browser |
|----------|--------|----------|---------|
| macOS | WebKit | anywidget/IFrame | FastAPI |
| Windows | WebView2 | anywidget/IFrame | FastAPI |
| Linux | WebKit | anywidget/IFrame | FastAPI |

Python 3.10-3.14. Linux requires WebKitGTK/GTK3 dev libraries.
