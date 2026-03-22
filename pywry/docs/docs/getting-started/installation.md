# Installation

Python 3.10 to 3.14 in a virtual environment.

## Basic

```bash
pip install pywry
```

## Optional Extras

Core extras:

| Extra | Installs |
|-------|----------|
| `pip install 'pywry[notebook]'` | Jupyter / anywidget integration |
| `pip install 'pywry[auth]'` | OAuth2 and secure token storage support |
| `pip install 'pywry[freeze]'` | PyInstaller hook for frozen desktop apps |
| `pip install 'pywry[mcp]'` | Model Context Protocol server support |
| `pip install 'pywry[all]'` | Every optional dependency above |

Provider SDK extras:

| Extra | Installs |
|-------|----------|
| `pip install 'pywry[openai]'` | OpenAI SDK for `OpenAIProvider` |
| `pip install 'pywry[anthropic]'` | Anthropic SDK for `AnthropicProvider` |
| `pip install 'pywry[magentic]'` | Magentic package for `MagenticProvider` |

Chat UI support is part of the base package. Provider extras only install third-party SDKs for the matching adapter classes.

## Development

PyWry keeps a single maintainer dependency group: `dev`.
Optional runtime features stay in package extras.

For example, with `uv`:

```bash
uv sync --all-extras --group dev
```

This installs the editable project, all optional feature extras, and the maintainer toolchain used for linting, testing, type checking, docs, and builds.

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

## Next Steps

Now that PyWry is installed, head to the [Quick Start](quickstart.md) guide to build your first interactive window.
