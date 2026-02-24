# Standalone Executable

Build your PyWry application as a self-contained executable that runs on machines without Python installed. PyWry ships with a PyInstaller hook that handles everything automatically — no `.spec` file edits or manual `--hidden-import` flags required.

## Quick Start

```bash
pip install pywry[freeze]
pyinstaller --windowed --name MyApp my_app.py
```

The output in `dist/MyApp/` is a fully portable directory you can zip and distribute.

## How It Works

When you `pip install pywry`, a [PyInstaller hook](https://pyinstaller.org/en/stable/hooks.html) is registered via the `pyinstaller40` entry point. The next time you run `pyinstaller`, it automatically:

1. **Bundles data files** — frontend HTML/JS/CSS, gzipped AG Grid and Plotly libraries, Tauri configuration (`Tauri.toml`), capability manifests, icons, and MCP skill files.
2. **Includes hidden imports** — the Tauri subprocess entry point, native extension modules (`.pyd` / `.so`), pytauri plugins, IPC command handlers, and runtime dependencies like `anyio` and `importlib_metadata`.
3. **Collects native binaries** — the `pytauri_wheel` shared library for the current platform.

### Subprocess Re-entry

PyWry runs Tauri in a subprocess. In a normal Python install this subprocess is `python -m pywry`. In a frozen executable there is no Python interpreter — the bundled `.exe` **is** the app.

PyWry solves this transparently:

- `runtime.start()` detects the frozen environment and re-launches `sys.executable` (your app) with `PYWRY_IS_SUBPROCESS=1` in the environment.
- `freeze_support()`, called automatically when you `import pywry`, intercepts the child process on startup and routes it to the Tauri event loop — your application code never runs a second time in the subprocess.

No special code is needed in your app. A minimal freezable application looks like this:

```python
from pywry import PyWry, WindowMode

app = PyWry(mode=WindowMode.SINGLE_WINDOW, title="My App")
app.show("<h1>Hello from a standalone executable!</h1>")
app.block()
```

## Build Options

### PyInstaller — One-directory (recommended)

```bash
pyinstaller --windowed --name MyApp my_app.py
```

`--onedir` is the default and gives the best startup time. The `--windowed` flag prevents a console window from appearing on Windows.

### PyInstaller — One-file

```bash
pyinstaller --onefile --windowed --name MyApp my_app.py
```

One-file builds are simpler to distribute but have slower startup because PyInstaller extracts everything to a temp directory at launch.

### Custom icon

```bash
pyinstaller --windowed --icon=icon.ico --name MyApp my_app.py
```

On macOS use `--icon=icon.icns`; on Linux, `--icon=icon.png`.

### Nuitka

```bash
pip install nuitka
nuitka --standalone --include-package=pywry --output-dir=dist my_app.py
```

Nuitka compiles Python to C and produces a native binary. The `--include-package=pywry` flag ensures all data files and submodules are included.

## Target Platform Requirements

The output executable is native to the build platform. End users need only the OS-level WebView runtime:

| Platform | Requirement |
|:---|:---|
| Windows 10 (1803+) / 11 | WebView2 — pre-installed |
| macOS 11+ | WKWebView — built-in |
| Linux | `libwebkit2gtk-4.1` (`apt install libwebkit2gtk-4.1-0`) |

No Python installation is required on the target machine.

## Example Application

```python
"""Minimal PyWry app that can be built as a standalone distributable."""

from pywry import PyWry, WindowMode

app = PyWry(mode=WindowMode.SINGLE_WINDOW, title="Standalone App")
app.show(
    """
    <html>
    <body style="background:#1e1e1e; color:white; font-family:sans-serif;
                 display:flex; align-items:center; justify-content:center;
                 height:100vh; margin:0;">
      <div style="text-align:center;">
        <h1>Hello from a distributable executable!</h1>
        <p style="color:#888;">No Python installation required on the target machine.</p>
      </div>
    </body>
    </html>
    """
)
app.block()
```

Build it:

```bash
pip install pywry[freeze]
pyinstaller --windowed --name StandaloneDemo standalone_demo.py
```

## Advanced Topics

### Explicit `freeze_support()` Call

The interception is automatic on `import pywry`. For extra safety — ensuring no application code runs before interception — you can call `freeze_support()` at the very top of your entry point:

```python
if __name__ == "__main__":
    from pywry import freeze_support
    freeze_support()

    # ... rest of application ...
```

This is only necessary if you have expensive top-level initialization that you want to skip in the subprocess.

### Debugging Frozen Builds

Enable debug logging to see subprocess communication:

```bash
# Windows
set PYWRY_DEBUG=1
dist\MyApp\MyApp.exe

# Linux / macOS
PYWRY_DEBUG=1 ./dist/MyApp/MyApp
```

### Extra Tauri Plugins

If your app uses additional Tauri plugins beyond the defaults (`dialog`, `fs`), configure them before `app.show()`:

```python
from pywry import PyWry

app = PyWry(title="My App")
app.tauri_plugins = ["dialog", "fs", "notification", "clipboard-manager"]
app.show("<h1>With extra plugins</h1>")
app.block()
```

The PyInstaller hook automatically collects all `pytauri_plugins` submodules, so no manual `--hidden-import` is needed.

### Extra Capabilities

For Tauri capability permissions beyond the defaults:

```python
app.extra_capabilities = ["shell:allow-execute"]
```

### Custom `.spec` File

For complex builds you can generate a `.spec` file and customize it:

```bash
pyinstaller --windowed --name MyApp my_app.py --specpath .
```

Then edit `MyApp.spec` to add extra data files, change paths, etc. Rebuild with:

```bash
pyinstaller MyApp.spec
```

The PyWry hook still runs automatically — the `.spec` file is additive.

## Troubleshooting

### Window doesn't appear

- Verify `--windowed` was used (otherwise the subprocess may not get focus).
- Run with `PYWRY_DEBUG=1` and check stderr for errors.
- On Linux, ensure `libwebkit2gtk-4.1` is installed.

### Missing assets (blank window)

If the window opens but shows a blank page, the frontend assets may not be bundled. Verify the `dist/` directory contains `pywry/frontend/`:

```bash
# Windows
dir /s dist\MyApp\_internal\pywry\frontend

# Linux / macOS
find dist/MyApp/_internal/pywry/frontend -type f
```

If empty, ensure pywry is installed (not just editable-linked) so `collect_data_files` can find the package files.

### `ModuleNotFoundError: pytauri_wheel`

This means the native Tauri runtime wasn't bundled. Ensure you installed pywry from a platform wheel (not a pure-Python sdist):

```bash
pip install --force-reinstall pywry
```

### App runs twice (code executes in subprocess)

This should never happen with the automatic `freeze_support()`. If it does, add the explicit call at the very top of your script:

```python
if __name__ == "__main__":
    from pywry import freeze_support
    freeze_support()
```
