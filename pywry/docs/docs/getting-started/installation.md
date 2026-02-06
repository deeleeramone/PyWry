# Installation

Python 3.10 to 3.14 in a virtual environment.

## Basic

```bash
pip install pywry
```

## Optional Extras

| Extra | Command | Description |
|-------|---------|-------------|
| `notebook` | `pip install 'pywry[notebook]'` | anywidget for Jupyter |
| `mcp` | `pip install 'pywry[mcp]'` | MCP server for AI agents |
| `all` | `pip install 'pywry[all]'` | All optional dependencies |
| `dev` | `pip install 'pywry[dev]'` | Development tools |

## Linux Requirements

```bash
# Ubuntu/Debian
sudo apt-get install libwebkit2gtk-4.1-dev libgtk-3-dev libglib2.0-dev \
    libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
    libxcb-randr0 libxcb-render-util0 libxcb-xinerama0 libxcb-xfixes0 \
    libxcb-shape0 libgl1 libegl1
```

macOS and Windows have no additional requirements.

## Verify

```python
from pywry import PyWry

app = PyWry()
app.show("PyWry installed!")
app.block()
```
    pip install pywry
    ```

=== "conda"

    ```bash
    conda create -n pywry python=3.11
    conda activate pywry
    pip install pywry
    ```

=== "uv"

    ```bash
    uv venv
    source .venv/bin/activate
    uv pip install pywry
    ```

## Next Steps

Now that PyWry is installed, head to the [Quick Start](quickstart.md) guide to build your first interactive window.
