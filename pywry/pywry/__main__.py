"""PyWry subprocess entry point.

This module runs as a subprocess, handling the pytauri event loop on the main thread
and receiving commands via stdin JSON IPC.
"""

# pylint: disable=C0301,C0413,C0415,C0103,W0718
# flake8: noqa: N806, PLR0915

import sys
import typing


# Set process and thread title for Activity Monitor/Task Manager visibility
try:
    import setproctitle

    setproctitle.setproctitle("PyWry")
    setproctitle.setthreadtitle("PyWry")
except ImportError:
    pass  # setproctitle is optional

# Set macOS process name early (before Tauri starts) so child processes inherit it

from ctypes import c_void_p


if sys.platform == "darwin":
    try:
        from ctypes import Structure, byref, c_uint32, cdll

        class _ProcessSerialNumber(Structure):
            _fields_: typing.ClassVar = [("highLongOfPSN", c_uint32), ("lowLongOfPSN", c_uint32)]

        _Carbon = cdll.LoadLibrary("/System/Library/Frameworks/Carbon.framework/Carbon")
        _psn = _ProcessSerialNumber()
        _Carbon.GetCurrentProcess(byref(_psn))
        _Carbon.CPSSetProcessName(byref(_psn), b"PyWry")
        del _Carbon, _psn, _ProcessSerialNumber
    except (OSError, AttributeError):
        pass

import io
import json
import os
import signal
import threading

from contextlib import suppress
from pathlib import Path
from typing import Any


def _set_macos_dock_icon() -> None:
    """Set the macOS dock icon programmatically using Cocoa APIs via ctypes.

    When running as a Python subprocess (not bundled as a .app), macOS uses the
    Python interpreter's icon for the dock. This function sets it to our custom icon.
    """
    if sys.platform != "darwin":
        return

    try:
        from ctypes import cdll  # pylint: disable=redefined-outer-name

        # Load the icon file - prefer .icns
        assets_dir = Path(__file__).parent / "frontend" / "assets"
        icon_path = assets_dir / "icon.icns"
        if not icon_path.exists():
            # Fallback to .png if .icns not available
            icon_path = assets_dir / "icon.png"
            if not icon_path.exists():
                return

        # Load Cocoa frameworks
        objc = cdll.LoadLibrary("/usr/lib/libobjc.A.dylib")
        AppKit = cdll.LoadLibrary("/System/Library/Frameworks/AppKit.framework/AppKit")

        # Set up objc_msgSend - the core Objective-C message sending function
        objc.objc_getClass.restype = c_void_p
        objc.objc_getClass.argtypes = [c_void_p]
        objc.sel_registerName.restype = c_void_p
        objc.sel_registerName.argtypes = [c_void_p]
        objc.objc_msgSend.restype = c_void_p
        objc.objc_msgSend.argtypes = [c_void_p, c_void_p]

        # Get NSApplication.sharedApplication
        NSApplication = objc.objc_getClass(b"NSApplication")
        sel_sharedApplication = objc.sel_registerName(b"sharedApplication")
        app = objc.objc_msgSend(NSApplication, sel_sharedApplication)

        if not app:
            return

        # Create NSString with path
        NSString = objc.objc_getClass(b"NSString")
        sel_stringWithUTF8String = objc.sel_registerName(b"stringWithUTF8String:")
        objc.objc_msgSend.argtypes = [c_void_p, c_void_p, c_void_p]
        path_str = objc.objc_msgSend(
            NSString, sel_stringWithUTF8String, str(icon_path).encode("utf-8")
        )

        if not path_str:
            return

        # Create NSImage from path
        NSImage = objc.objc_getClass(b"NSImage")
        sel_alloc = objc.sel_registerName(b"alloc")
        sel_initWithContentsOfFile = objc.sel_registerName(b"initWithContentsOfFile:")

        objc.objc_msgSend.argtypes = [c_void_p, c_void_p]
        image = objc.objc_msgSend(NSImage, sel_alloc)
        objc.objc_msgSend.argtypes = [c_void_p, c_void_p, c_void_p]
        image = objc.objc_msgSend(image, sel_initWithContentsOfFile, path_str)

        if not image:
            return

        # Set the application icon
        sel_setApplicationIconImage = objc.sel_registerName(b"setApplicationIconImage:")
        objc.objc_msgSend.argtypes = [c_void_p, c_void_p, c_void_p]
        objc.objc_msgSend(app, sel_setApplicationIconImage, image)

        # Keep reference to AppKit to prevent it from being garbage collected
        _ = AppKit

    except Exception:
        # Silently ignore errors - dock icon is non-critical
        pass


# Reconfigure stdin/stdout to UTF-8 on Windows
# This is needed because Windows may default to the locale encoding (cp1252)
if sys.platform == "win32":
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace")
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import importlib  # noqa: E402
import shutil  # noqa: E402
import tempfile  # noqa: E402

import pytauri_plugins  # noqa: E402

from anyio import create_task_group  # noqa: E402
from anyio.from_thread import start_blocking_portal  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from pytauri import Commands, Manager, RunEvent, WebviewUrl, WindowEvent  # noqa: E402
from pytauri.webview import WebviewWindowBuilder  # noqa: E402

from pywry.config import TAURI_PLUGIN_REGISTRY as _PLUGIN_REGISTRY  # noqa: E402


# Try vendored pytauri_wheel first, fall back to installed package
try:
    from pywry._vendor.pytauri_wheel.lib import (  # type: ignore
        builder_factory,
        context_factory,
    )
except ImportError:
    from pytauri_wheel.lib import builder_factory, context_factory


def _default_single_instance_callback(
    app_handle: Any,
    argv: list[str],  # pylint: disable=unused-argument
    cwd: str,  # pylint: disable=unused-argument
) -> None:
    """Default single-instance callback - focus the existing main window."""
    try:
        window = Manager.get_webview_window(app_handle, "main")
        if window:
            window.show()
            window.set_focus()
    except Exception as exc:
        log(f"single_instance callback error: {exc}")


def _load_plugins(plugin_names: list[str]) -> list[Any]:
    """Dynamically import and initialise the requested Tauri plugins.

    Handles the three pytauri_plugins initialisation patterns:

    * ``"init"``     - ``mod.init()``              (most plugins)
    * ``"builder"``  - ``mod.Builder.build()``      (updater, window_state, global_shortcut)
    * ``"callback"`` - ``mod.init(callback)``        (single_instance)

    Parameters
    ----------
    plugin_names : list[str]
        Plugin names to load (e.g. ``["dialog", "fs"]``).

    Returns
    -------
    list
        Initialised ``Plugin`` objects for ``builder_factory().build(plugins=...)``.

    Raises
    ------
    RuntimeError
        If a plugin is unknown or its feature flag is disabled in the
        compiled ``pytauri_wheel``.
    """
    plugins: list[Any] = []
    for name in plugin_names:
        if name not in _PLUGIN_REGISTRY:
            msg = f"Unknown Tauri plugin '{name}'. Available: {', '.join(sorted(_PLUGIN_REGISTRY))}"
            raise RuntimeError(msg)

        flag_name, module_path, init_method = _PLUGIN_REGISTRY[name]

        # Check the compile-time feature flag
        flag_value = getattr(pytauri_plugins, flag_name, None)
        if flag_value is not True:
            msg = (
                f"Tauri plugin '{name}' is not available — the "
                f"'{flag_name}' feature was not compiled into pytauri_wheel. "
                f"Current value: {flag_value!r}"
            )
            raise RuntimeError(msg)

        mod = importlib.import_module(module_path)

        if init_method == "builder":
            # updater, window_state, global_shortcut use Builder.build()
            plugin = mod.Builder.build()
        elif init_method == "callback":
            # single_instance requires a callback(app_handle, argv, cwd)
            plugin = mod.init(_default_single_instance_callback)
        else:
            # Most plugins: simple mod.init()
            plugin = mod.init()

        plugins.append(plugin)
        log(f"Loaded Tauri plugin: {name} (via {init_method})")

    return plugins


def _stage_extra_capabilities(
    src_dir: Path,
    extra_caps: list[str],
) -> Path:
    """Create a temp copy of *src_dir* with an extra capability TOML.

    Tauri's ``context_factory(src_dir)`` reads every ``.toml`` file under
    ``<src_dir>/capabilities/``.  The package directory may be read-only
    (e.g. installed in site-packages), so we copy the entire source tree to
    a temporary directory and add an ``extra.toml`` capability file there.

    Parameters
    ----------
    src_dir : Path
        Original ``pywry/pywry`` package directory.
    extra_caps : list[str]
        Tauri permission strings, e.g. ``["shell:allow-execute"]``.

    Returns
    -------
    Path
        The temporary directory to pass to ``context_factory()``.
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="pywry_caps_"))
    # Copy Tauri.toml, capabilities/, frontend/ — everything context_factory needs
    shutil.copytree(src_dir, tmp_dir, dirs_exist_ok=True)

    # Write the extra capability file
    extra_toml = tmp_dir / "capabilities" / "extra.toml"
    perms = ", ".join(f'"{p}"' for p in extra_caps)
    extra_toml.write_text(
        f'identifier = "extra"\n'
        f'description = "User-supplied extra capabilities"\n'
        f'windows = ["*"]\n'
        f"permissions = [{perms}]\n",
        encoding="utf-8",
    )
    log(f"Staged extra capabilities in {tmp_dir}: {extra_caps}")
    return tmp_dir


# Debug mode controlled by environment variable
DEBUG = os.environ.get("PYWRY_DEBUG", "").lower() in ("1", "true", "yes", "on")

# Headless mode for CI testing - windows are created but not shown
HEADLESS = os.environ.get("PYWRY_HEADLESS", "").lower() in ("1", "true", "yes", "on")

# Window mode: "single", "multi", or "new"
WINDOW_MODE = os.environ.get("PYWRY_WINDOW_MODE", "new").lower()

# What happens when user clicks X in MULTI_WINDOW mode: "hide" or "close"
ON_WINDOW_CLOSE = os.environ.get("PYWRY_ON_WINDOW_CLOSE", "hide").lower()

# Lock for thread-safe stdout writes
_stdout_lock = threading.Lock()


def log(msg: str) -> None:
    """Log to stderr for debugging (only when DEBUG is enabled)."""
    if DEBUG:
        sys.stderr.write(f"[pywry] {msg}\n")
        sys.stderr.flush()


def log_error(msg: str) -> None:
    """Log error to stderr (always, regardless of DEBUG)."""
    sys.stderr.write(f"[pywry] ERROR: {msg}\n")
    sys.stderr.flush()


class JsonIPC:  # pylint: disable=too-many-public-methods
    """Handle JSON IPC communication via stdin/stdout."""

    def __init__(self) -> None:
        """Initialize the IPC handler."""
        self.windows: dict[str, Any] = {}
        self.menus: dict[str, Any] = {}  # menu_id -> Menu object
        self.menu_items: dict[str, Any] = {}  # item_id -> MenuItem-like object
        self.trays: dict[str, Any] = {}  # tray_id -> TrayIcon object
        self.tray_menu_items: set[str] = set()  # item IDs owned by trays
        self.app_handle: Any = None
        self.running = True

        # Request/response correlation for custom commands that round-trip
        # through the parent process.  The pytauri command handler sends a
        # request with a unique ``request_id`` to stdout, then waits on a
        # threading.Event.  When ``stdin_reader`` sees a response with a
        # matching ``request_id``, it fills ``_pending_responses`` and sets
        # the event so the blocked handler can return the value to JS.
        self._pending_requests: dict[str, threading.Event] = {}
        self._pending_responses: dict[str, dict[str, Any]] = {}
        self._pending_lock = threading.Lock()

    def send(self, msg: dict[str, Any]) -> None:
        """Send a JSON message to stdout."""
        try:
            line = json.dumps(msg)
            with _stdout_lock:
                sys.stdout.write(line + "\n")
                sys.stdout.flush()
        except Exception as e:
            log(f"IPC send error: {e}")

    def send_ready(self) -> None:
        """Signal that the app is ready."""
        self.send({"type": "ready"})

    def send_error(self, error: str) -> None:
        """Send an error message."""
        log_error(error)
        self.send({"type": "error", "error": error})

    def send_result(self, label: str, success: bool) -> None:
        """Send a command result."""
        self.send({"type": "result", "label": label, "success": success})

    def send_request_and_wait(
        self,
        msg: dict[str, Any],
        timeout: float = 10.0,
    ) -> dict[str, Any]:
        """Send a message to the parent and block until it replies.

        A unique ``request_id`` is attached to *msg*.  The parent must echo
        that ``request_id`` in its response so that ``handle_response`` can
        correlate it.

        Parameters
        ----------
        msg : dict
            The IPC message (``type``, payload, etc.).
        timeout : float
            How long to wait (seconds) before returning an error dict.

        Returns
        -------
        dict
            The parent's response payload, or an ``{error: ...}`` dict on
            timeout / failure.
        """
        import uuid as _uuid

        request_id = _uuid.uuid4().hex
        msg["request_id"] = request_id

        event = threading.Event()
        with self._pending_lock:
            self._pending_requests[request_id] = event

        try:
            self.send(msg)  # to parent via stdout
            if event.wait(timeout=timeout):
                with self._pending_lock:
                    return self._pending_responses.pop(request_id, {"error": "no response"})
            return {"error": f"timeout after {timeout}s"}
        finally:
            with self._pending_lock:
                self._pending_requests.pop(request_id, None)
                self._pending_responses.pop(request_id, None)

    def handle_response(self, msg: dict[str, Any]) -> bool:
        """Try to correlate *msg* with a pending request.

        Returns ``True`` if *msg* was consumed as a response, ``False`` if it
        should be handled as a normal command.
        """
        request_id = msg.get("request_id")
        if not request_id:
            return False
        with self._pending_lock:
            event = self._pending_requests.get(request_id)
            if event is None:
                return False
            self._pending_responses[request_id] = msg
            event.set()
        return True

    def handle_command(self, cmd: dict[str, Any]) -> None:  # noqa: C901, PLR0912  # pylint: disable=too-many-branches
        """Handle an incoming command."""
        action = cmd.get("action")
        log(f"Received command: {action}")

        if action == "create":
            self.create_window(cmd)
        elif action == "set_content":
            self.set_content(cmd)
        elif action == "show":
            self.show_window(cmd)
        elif action == "hide":
            self.hide_window(cmd)
        elif action == "close":
            self.close_window(cmd)
        elif action == "emit":
            self.emit_event(cmd)
        elif action == "eval":
            self.eval_js(cmd)
        elif action == "check_open":
            self.check_window_open(cmd)
        elif action == "window_get":
            self.window_get_property(cmd)
        elif action == "window_call":
            self.window_call_method(cmd)
        elif action == "menu_create":
            self.menu_create(cmd)
        elif action == "menu_set":
            self.menu_set(cmd)
        elif action == "menu_popup":
            self.menu_popup(cmd)
        elif action == "menu_update":
            self.menu_update(cmd)
        elif action == "menu_remove":
            self.menu_remove(cmd)
        elif action == "tray_create":
            self.tray_create(cmd)
        elif action == "tray_update":
            self.tray_update(cmd)
        elif action == "tray_remove":
            self.tray_remove(cmd)
        elif action == "quit":
            self.quit()
        else:
            self.send_error(f"Unknown action: {action}")

    def quit(self) -> None:
        """Quit the application."""
        log("Quit command received, exiting...")
        self.running = False

        # ── Clean up tray icons BEFORE destroying windows ─────────
        # Dropping the Python TrayIcon reference triggers pyo3 Rust Drop
        # which removes the icon from the OS.  Do NOT call
        # remove_tray_by_id — Rust Drop handles that internally.
        for tray_id in list(self.trays):
            try:
                tray = self.trays.pop(tray_id)
                tray.set_visible(False)
                del tray
            except Exception:
                pass
        self.trays.clear()

        # Destroy all windows (bypasses CloseRequested handler)
        if self.app_handle:
            for label in list(self.windows.keys()):
                try:
                    window = self.windows.get(label)
                    if window:
                        window.destroy()
                except Exception:
                    pass
            # Also destroy the main window if it exists
            try:
                main_window = Manager.get_webview_window(self.app_handle, "main")
                if main_window:
                    main_window.destroy()
            except Exception:
                pass
        # Force exit the process since prevent_exit() may have been called
        log("Forcing process exit...")
        import os  # pylint: disable=redefined-outer-name,reimported

        os._exit(0)

    def create_window(self, cmd: dict[str, Any]) -> None:
        """Create a new window, or reuse existing one."""
        label = cmd.get("label", "main")
        title = cmd.get("title", "PyWry")
        width = cmd.get("width", 800)
        height = cmd.get("height", 600)
        builder_opts: dict[str, Any] = cmd.get("builder_opts", {})

        if self.app_handle is None:
            self.send_error("App not ready")
            return

        # Check if window already exists - if so, just show it
        try:
            existing = Manager.get_webview_window(self.app_handle, label)
            if existing:
                log(f"Window '{label}' already exists, reusing it")
                self.windows[label] = existing
                if not HEADLESS:
                    existing.show()
                    existing.set_focus()
                self.send_result(label, True)
                return
        except Exception as e:
            log(f"Warning: Failed to check existing window: {e}")

        try:
            url = WebviewUrl.App(f"index.html?label={label}")

            # Build kwargs for WebviewWindowBuilder
            build_kwargs: dict[str, Any] = {
                "title": title,
                "inner_size": (float(width), float(height)),
                "visible": (not HEADLESS) and builder_opts.pop("visible", True),
            }

            # Forward all supported builder options
            _BUILDER_KWARG_MAP: dict[str, str] = {
                "resizable": "resizable",
                "decorations": "decorations",
                "always_on_top": "always_on_top",
                "always_on_bottom": "always_on_bottom",
                "transparent": "transparent",
                "fullscreen": "fullscreen",
                "maximized": "maximized",
                "focused": "focused",
                "shadow": "shadow",
                "skip_taskbar": "skip_taskbar",
                "content_protected": "content_protected",
                "user_agent": "user_agent",
                "incognito": "incognito",
                "initialization_script": "initialization_script",
                "drag_and_drop": "drag_and_drop",
            }
            for opt_key, builder_key in _BUILDER_KWARG_MAP.items():
                if opt_key in builder_opts:
                    build_kwargs[builder_key] = builder_opts[opt_key]

            log(f"Building window '{label}' with kwargs: {list(build_kwargs.keys())}")
            window = WebviewWindowBuilder.build(
                self.app_handle,
                label,
                url,
                **build_kwargs,
            )
            if not HEADLESS:
                window.center()
                window.show()
                window.set_focus()
            self.windows[label] = window
            log(f"Created window '{label}' (headless={HEADLESS})")
            self.send_result(label, True)
        except Exception as e:
            self.send_error(f"Failed to create window: {e}")

    def set_content(self, cmd: dict[str, Any]) -> None:
        """Set content for a window."""
        import time

        label = cmd.get("label", "main")
        html = cmd.get("html", "")
        theme = cmd.get("theme", "dark")
        log(f"set_content for '{label}', html length: {len(html)}, theme: {theme}")

        window = self.windows.get(label)
        if window is None and self.app_handle:
            log(f"Window '{label}' not in cache, trying Manager...")
            window = Manager.get_webview_window(self.app_handle, label)
            if window:
                self.windows[label] = window
                log(f"Found window '{label}' via Manager")

        if window is None:
            self.send_error(f"Window not found: {label}")
            return

        try:
            # Set native window background color to match theme
            # This prevents flash of wrong color and ensures window chrome matches
            if theme == "light":
                window.set_background_color((255, 255, 255, 255))  # White
            else:
                window.set_background_color((30, 30, 30, 255))  # Dark gray (#1e1e1e)

            # Wait for page to load
            time.sleep(0.5)

            # Use ensure_ascii=False to preserve emoji and unicode characters
            escaped = json.dumps(html, ensure_ascii=False)
            escaped_theme = json.dumps(theme, ensure_ascii=False)

            # Inject content into #app div and execute scripts
            # Order: Theme class -> CSS -> Scripts -> Body -> Body scripts
            script = f"""
            (function() {{
                var html = {escaped};
                var theme = {escaped_theme};
                var themeClass = 'pywry-theme-' + theme;

                // Set theme class on <html> element
                // Remove ALL theme-related classes (both pywry-theme-* and plain dark/light)
                var htmlEl = document.documentElement;
                htmlEl.classList.remove('pywry-theme-dark', 'pywry-theme-light', 'dark', 'light');
                htmlEl.classList.add('pywry-native', themeClass, theme);

                var app = document.getElementById('app');
                if (!app) return;

                // Extract head content
                var headMatch = html.match(/<head[^>]*>([\\s\\S]*?)<\\/head>/i);
                if (!headMatch) return;

                var headContent = headMatch[1];

                // Inject CSS
                var styleRegex = /<style[^>]*>([\\s\\S]*?)<\\/style>/gi;
                var styleMatch;
                while ((styleMatch = styleRegex.exec(headContent)) !== null) {{
                    var styleEl = document.createElement('style');
                    styleEl.textContent = styleMatch[1];
                    document.head.appendChild(styleEl);
                }}

                // Extract head scripts
                var scriptMatches = headContent.match(/<script[^>]*>([\\s\\S]*?)<\\/script>/gi) || [];
                var headScripts = [];
                scriptMatches.forEach(function(scriptHtml) {{
                    var contentMatch = scriptHtml.match(/<script[^>]*>([\\s\\S]*?)<\\/script>/i);
                    if (contentMatch && contentMatch[1].trim()) headScripts.push(contentMatch[1]);
                }});

                // Wait for CSS parse, then execute scripts and set content
                setTimeout(function() {{
                    headScripts.forEach(function(scriptContent) {{
                        try {{
                            var scriptEl = document.createElement('script');
                            scriptEl.textContent = scriptContent;
                            document.head.appendChild(scriptEl);
                        }} catch (e) {{ console.error('[PyWry]', e); }}
                    }});

                    // Set body content
                    var bodyMatch = html.match(/<body[^>]*>([\\s\\S]*?)<\\/body>/i);
                    app.innerHTML = bodyMatch ? bodyMatch[1] : html;

                    // Execute body scripts
                    setTimeout(function() {{
                        var scripts = app.querySelectorAll('script');
                        for (var i = 0; i < scripts.length; i++) {{
                            var oldScript = scripts[i];
                            var newScript = document.createElement('script');
                            if (oldScript.src) newScript.src = oldScript.src;
                            else newScript.textContent = oldScript.textContent;
                            oldScript.parentNode.replaceChild(newScript, oldScript);
                        }}

                        // Re-initialize toolbar handlers now that content is in DOM
                        if (typeof initToolbarHandlers === 'function' && window.pywry) {{
                            console.log('[PyWry] Re-initializing toolbar handlers after content injection');
                            initToolbarHandlers(document, window.pywry);
                        }}

                        // Notify Python that content is ready
                        if (window.pywry && window.pywry.sendEvent) {{
                            window.pywry.sendEvent('content:ready', {{ timestamp: Date.now() }});
                        }}
                    }}, 50);
                }}, 100);
            }})();
            """
            log("Calling eval with script")
            window.eval(script)
            log(f"Content set for '{label}'")
            self.send_result(label, True)
        except Exception as e:
            self.send_error(f"Failed to set content: {e}")

    def show_window(self, cmd: dict[str, Any]) -> None:
        """Show a hidden window."""
        label = cmd.get("label", "main")
        window = self.windows.get(label)

        if window is None and self.app_handle:
            window = Manager.get_webview_window(self.app_handle, label)
            if window:
                self.windows[label] = window

        if window:
            try:
                if not HEADLESS:
                    window.show()
                log(f"Showed window '{label}' (headless={HEADLESS})")
                self.send_result(label, True)
            except Exception as e:
                self.send_error(f"Failed to show window: {e}")
        else:
            self.send_error(f"Window not found: {label}")

    def hide_window(self, cmd: dict[str, Any]) -> None:
        """Hide a window (keeps it alive, just not visible)."""
        label = cmd.get("label", "main")
        window = self.windows.get(label)

        if window is None and self.app_handle:
            window = Manager.get_webview_window(self.app_handle, label)
            if window:
                self.windows[label] = window

        if window:
            try:
                if not HEADLESS:
                    window.hide()
                log(f"Hid window '{label}' (headless={HEADLESS})")
                # Notify Python side that window is hidden
                self.send(
                    {
                        "type": "event",
                        "event_type": "window:hidden",
                        "label": label,
                        "data": {},
                    }
                )
                self.send_result(label, True)
            except Exception as e:
                self.send_error(f"Failed to hide window: {e}")
        else:
            self.send_error(f"Window not found: {label}")

    def emit_event(self, cmd: dict[str, Any]) -> None:
        """Emit an event to a window.

        Uses Tauri's event system to send the event to the webview,
        which dispatches it to JavaScript handlers.
        """
        label = cmd.get("label", "main")
        event = cmd.get("event", "")
        payload = cmd.get("payload", {})

        if not event:
            self.send_error("emit: missing 'event' field")
            return

        # Handle wildcard - emit to all windows
        if label == "*":
            for window_label, window in self.windows.items():
                try:
                    self._emit_to_window(window, event, payload)
                    log(f"Emitted '{event}' to window '{window_label}'")
                except Exception as e:
                    log(f"Failed to emit to '{window_label}': {e}")
            self.send_result("*", True)
            return

        # Get specific window
        window = self.windows.get(label)
        if window is None and self.app_handle:
            window = Manager.get_webview_window(self.app_handle, label)
            if window:
                self.windows[label] = window

        if window is None:
            self.send_error(f"emit: Window not found: {label}")
            return

        try:
            self._emit_to_window(window, event, payload)
            log(f"Emitted '{event}' to window '{label}'")
            self.send_result(label, True)
        except Exception as e:
            self.send_error(f"emit: Failed to emit event: {e}")

    def _emit_to_window(self, window: Any, event: str, payload: dict[str, Any]) -> None:
        """Emit event to a window using JavaScript eval."""
        # Build JavaScript to dispatch the event
        # Use ensure_ascii=False to preserve emoji and unicode characters
        payload_json = json.dumps(payload, ensure_ascii=False)
        script = f"""
        (function() {{
            if (window.pywry && window.pywry.dispatch) {{
                window.pywry.dispatch({json.dumps(event, ensure_ascii=False)}, {payload_json});
            }}
        }})();
        """
        window.eval(script)

    def eval_js(self, cmd: dict[str, Any]) -> None:
        """Evaluate arbitrary JavaScript in a window without replacing content."""
        label = cmd.get("label", "main")
        script = cmd.get("script", "")

        if not script:
            self.send_error("eval: missing 'script' field")
            return

        window = self.windows.get(label)
        if window is None and self.app_handle:
            window = Manager.get_webview_window(self.app_handle, label)
            if window:
                self.windows[label] = window

        if window is None:
            self.send_error(f"eval: Window not found: {label}")
            return

        try:
            window.eval(script)
            log(f"Evaluated JS in window '{label}'")
            self.send_result(label, True)
        except Exception as e:
            self.send_error(f"eval: Failed to evaluate JS: {e}")

    def check_window_open(self, cmd: dict[str, Any]) -> None:
        """Check if a window is open."""
        label = cmd.get("label", "main")

        # Check cache
        window = self.windows.get(label)

        # Check manager if not in cache
        if window is None and self.app_handle:
            with suppress(Exception):
                window = Manager.get_webview_window(self.app_handle, label)

        is_open = window is not None
        log(f"check_open for '{label}': {is_open}")
        self.send({"type": "result", "label": label, "is_open": is_open})

    def close_window(self, cmd: dict[str, Any]) -> None:
        """Force-close a window (bypasses CloseRequested handler)."""
        label = cmd.get("label", "main")
        window = self.windows.pop(label, None)

        if window is None and self.app_handle:
            window = Manager.get_webview_window(self.app_handle, label)

        if window:
            try:
                # Use destroy() to bypass CloseRequested handler
                window.destroy()
                log(f"Destroyed window '{label}'")
                self.send_result(label, True)
            except Exception as e:
                self.send_error(f"Failed to close window: {e}")
        else:
            self.send_error(f"Window not found: {label}")

    def _get_window(self, label: str) -> Any | None:
        """Get a window by label, checking cache first then manager."""
        window = self.windows.get(label)
        if window is None and self.app_handle:
            window = Manager.get_webview_window(self.app_handle, label)
            if window:
                self.windows[label] = window
        return window

    def window_get_property(self, cmd: dict[str, Any]) -> None:
        """Get a window property - blocking call with response.

        Expected cmd format:
        {
            "action": "window_get",
            "label": "main",
            "property": "title",
            "request_id": "uuid-xxx"
        }

        Response format:
        {
            "type": "response",
            "request_id": "uuid-xxx",
            "success": true,
            "value": "Window Title"
        }
        or on error:
        {
            "type": "response",
            "request_id": "uuid-xxx",
            "success": false,
            "error": "error message"
        }
        """
        label = cmd.get("label", "main")
        prop = cmd.get("property", "")
        request_id = cmd.get("request_id", "")

        if not prop:
            self.send(
                {
                    "type": "response",
                    "request_id": request_id,
                    "success": False,
                    "error": "window_get: missing 'property' field",
                }
            )
            return

        window = self._get_window(label)
        if window is None:
            self.send(
                {
                    "type": "response",
                    "request_id": request_id,
                    "success": False,
                    "error": f"Window not found: {label}",
                }
            )
            return

        try:
            from .window_dispatch import get_window_property

            prop_args = cmd.get("args", {})
            value = get_window_property(window, prop, prop_args)
            log(f"window_get '{label}'.{prop} = {value!r}")
            self.send(
                {
                    "type": "response",
                    "request_id": request_id,
                    "success": True,
                    "value": value,
                }
            )
        except Exception as e:
            self.send(
                {
                    "type": "response",
                    "request_id": request_id,
                    "success": False,
                    "error": str(e),
                }
            )

    def window_call_method(self, cmd: dict[str, Any]) -> None:
        """Call a window method - fire-and-forget or blocking.

        Expected cmd format:
        {
            "action": "window_call",
            "label": "main",
            "method": "set_title",
            "args": ["New Title"],
            "request_id": "uuid-xxx"  # Optional for fire-and-forget
        }
        """
        label = cmd.get("label", "main")
        method = cmd.get("method", "")
        args = cmd.get("args", [])
        request_id = cmd.get("request_id", "")

        if not method:
            if request_id:
                self.send(
                    {
                        "type": "response",
                        "request_id": request_id,
                        "success": False,
                        "error": "window_call: missing 'method' field",
                    }
                )
            else:
                log_error("window_call: missing 'method' field")
            return

        window = self._get_window(label)
        if window is None:
            if request_id:
                self.send(
                    {
                        "type": "response",
                        "request_id": request_id,
                        "success": False,
                        "error": f"Window not found: {label}",
                    }
                )
            else:
                log_error(f"window_call: Window not found: {label}")
            return

        try:
            from .window_dispatch import call_window_method

            result = call_window_method(window, method, args)
            log(f"window_call '{label}'.{method}({args}) = {result!r}")
            if request_id:
                self.send(
                    {
                        "type": "response",
                        "request_id": request_id,
                        "success": True,
                        "value": result,
                    }
                )
        except Exception as e:
            log_error(f"window_call '{label}'.{method} failed: {e}")
            if request_id:
                self.send(
                    {
                        "type": "response",
                        "request_id": request_id,
                        "success": False,
                        "error": str(e),
                    }
                )

    # ── Menu handlers ─────────────────────────────────────────────────

    def _build_menu_item(self, data: dict[str, Any]) -> Any:
        """Build a single pytauri menu item from a config dict.

        Returns the pytauri menu item object and also registers it in
        ``self.menu_items`` keyed by its ``id``.
        """
        from pytauri.menu import (
            CheckMenuItem,
            IconMenuItem,
            MenuItem,
            PredefinedMenuItem,
            Submenu,
        )

        kind = data.get("kind", "item")
        item_id = data.get("id", "")

        if kind == "predefined":
            kind_name = data.get("kind_name", "separator")
            factory = getattr(PredefinedMenuItem, kind_name, None)
            if factory is None:
                factory = PredefinedMenuItem.separator
            text = data.get("text")
            item = factory(self.app_handle, text) if text is not None else factory(self.app_handle)  # type: ignore[call-arg]
            return item

        if kind == "check":
            item = CheckMenuItem.with_id(
                self.app_handle,
                item_id,
                data.get("text", ""),
                data.get("enabled", True),
                data.get("checked", False),
                data.get("accelerator"),
            )
            self.menu_items[item_id] = item
            return item

        if kind == "icon":
            icon_bytes = data.get("icon")
            native_icon_name = data.get("native_icon")
            if native_icon_name:
                from pytauri.menu import NativeIcon

                native_icon = getattr(NativeIcon, native_icon_name, None)
                if native_icon is not None:
                    item = IconMenuItem.with_id_and_native_icon(
                        self.app_handle,
                        item_id,
                        data.get("text", ""),
                        data.get("enabled", True),
                        native_icon,
                        data.get("accelerator"),
                    )
                    self.menu_items[item_id] = item
                    return item
            # RGBA icon bytes
            icon_image = None
            if icon_bytes:
                import base64

                from pytauri.image import Image

                raw = base64.b64decode(icon_bytes)
                icon_image = Image(raw, data.get("icon_width", 16), data.get("icon_height", 16))
            item = IconMenuItem.with_id(
                self.app_handle,
                item_id,
                data.get("text", ""),
                data.get("enabled", True),
                icon_image,
                data.get("accelerator"),
            )
            self.menu_items[item_id] = item
            return item

        if kind == "submenu":
            child_items = [self._build_menu_item(c) for c in data.get("items", [])]
            submenu = Submenu.with_id_and_items(
                self.app_handle,
                item_id,
                data.get("text", ""),
                data.get("enabled", True),
                child_items,
            )
            self.menu_items[item_id] = submenu
            return submenu

        # Default: regular MenuItem
        item = MenuItem.with_id(
            self.app_handle,
            item_id,
            data.get("text", ""),
            data.get("enabled", True),
            data.get("accelerator"),
        )
        self.menu_items[item_id] = item
        return item

    def menu_create(self, cmd: dict[str, Any]) -> None:
        """Create a native menu."""
        from pytauri.menu import Menu

        menu_id = cmd.get("menu_id", "")
        items_data = cmd.get("items", [])

        if self.app_handle is None:
            self.send_error("App not ready")
            return

        try:
            items = [self._build_menu_item(d) for d in items_data]
            menu = Menu.with_id_and_items(self.app_handle, menu_id, items)
            self.menus[menu_id] = menu
            log(f"Created menu '{menu_id}' with {len(items)} items")
            self.send({"type": "result", "success": True, "menu_id": menu_id})
        except Exception as e:
            self.send_error(f"Failed to create menu '{menu_id}': {e}")

    def menu_set(self, cmd: dict[str, Any]) -> None:
        """Attach a menu to a window or the app."""
        menu_id = cmd.get("menu_id", "")
        target = cmd.get("target", "app")
        label = cmd.get("label", "main")

        menu = self.menus.get(menu_id)
        if menu is None:
            self.send_error(f"Menu not found: {menu_id}")
            return

        try:
            if target == "app":
                self.app_handle.set_menu(menu)
                log(f"Set app menu: {menu_id}")
            elif target == "window":
                window = self._get_window(label)
                if window is None:
                    self.send_error(f"Window not found: {label}")
                    return
                window.set_menu(menu)
                log(f"Set window '{label}' menu: {menu_id}")
        except Exception as e:
            self.send_error(f"menu_set failed: {e}")

    def menu_popup(self, cmd: dict[str, Any]) -> None:
        """Show a menu as a context popup."""
        menu_id = cmd.get("menu_id", "")
        label = cmd.get("label", "main")
        position = cmd.get("position")

        menu = self.menus.get(menu_id)
        if menu is None:
            self.send_error(f"Menu not found: {menu_id}")
            return

        window = self._get_window(label)
        if window is None:
            self.send_error(f"Window not found: {label}")
            return

        try:
            from pytauri.menu import ContextMenu

            if position:
                from pytauri import Position

                pos = Position.Logical((float(position["x"]), float(position["y"])))
                ContextMenu.popup_at(menu, window, pos)
            else:
                ContextMenu.popup(menu, window)
            log(f"Menu popup '{menu_id}' on window '{label}'")
        except Exception as e:
            self.send_error(f"menu_popup failed: {e}")

    def menu_update(self, cmd: dict[str, Any]) -> None:  # noqa: C901, PLR0912  # pylint: disable=too-many-branches,too-many-statements
        """Mutate an existing menu or menu item."""
        menu_id = cmd.get("menu_id", "")
        operation = cmd.get("operation", "")

        menu = self.menus.get(menu_id)
        if menu is None:
            self.send_error(f"Menu not found: {menu_id}")
            return

        try:
            if operation == "append":
                item = self._build_menu_item(cmd.get("item_data", {}))
                menu.append(item)
            elif operation == "prepend":
                item = self._build_menu_item(cmd.get("item_data", {}))
                menu.prepend(item)
            elif operation == "insert":
                item = self._build_menu_item(cmd.get("item_data", {}))
                menu.insert(item, cmd.get("position", 0))
            elif operation == "remove":
                item_id = cmd.get("item_id", "")
                item = self.menu_items.get(item_id)
                if item:
                    menu.remove(item)
                    del self.menu_items[item_id]
            elif operation == "set_text":
                item_id = cmd.get("item_id", "")
                item = self.menu_items.get(item_id)
                if item and hasattr(item, "set_text"):
                    item.set_text(cmd.get("text", ""))
            elif operation == "set_enabled":
                item_id = cmd.get("item_id", "")
                item = self.menu_items.get(item_id)
                if item and hasattr(item, "set_enabled"):
                    item.set_enabled(cmd.get("enabled", True))
            elif operation == "set_checked":
                item_id = cmd.get("item_id", "")
                item = self.menu_items.get(item_id)
                if item and hasattr(item, "set_checked"):
                    item.set_checked(cmd.get("checked", False))
            elif operation == "set_accelerator":
                item_id = cmd.get("item_id", "")
                item = self.menu_items.get(item_id)
                if item and hasattr(item, "set_accelerator"):
                    item.set_accelerator(cmd.get("accelerator"))
            elif operation == "set_icon":
                item_id = cmd.get("item_id", "")
                item = self.menu_items.get(item_id)
                if item and hasattr(item, "set_icon"):
                    icon_b64 = cmd.get("icon")
                    if icon_b64:
                        import base64

                        from pytauri.image import Image

                        raw = base64.b64decode(icon_b64)
                        w = cmd.get("icon_width", 16)
                        h = cmd.get("icon_height", 16)
                        item.set_icon(Image(raw, w, h))
                    else:
                        item.set_icon(None)
            else:
                self.send_error(f"Unknown menu_update operation: {operation}")
            log(f"menu_update '{menu_id}' op={operation}")
        except Exception as e:
            self.send_error(f"menu_update failed: {e}")

    def menu_remove(self, cmd: dict[str, Any]) -> None:
        """Remove and destroy a menu."""
        menu_id = cmd.get("menu_id", "")
        if menu_id in self.menus:
            del self.menus[menu_id]
            log(f"Removed menu '{menu_id}'")
        else:
            log(f"menu_remove: menu '{menu_id}' not found")

    # ── Tray handlers ─────────────────────────────────────────────────

    def _apply_tray_icon(self, tray: Any, cmd: dict[str, Any]) -> None:
        """Apply icon to a tray from *cmd*, falling back to the app icon."""
        icon_b64 = cmd.get("icon")
        if icon_b64:
            import base64

            from pytauri.image import Image

            raw = base64.b64decode(icon_b64)
            w = cmd.get("icon_width", 32)
            h = cmd.get("icon_height", 32)
            tray.set_icon(Image(raw, w, h))
        else:
            default_icon = self.app_handle.default_window_icon()
            if default_icon is not None:
                tray.set_icon(default_icon)

    def _apply_tray_menu(self, tray: Any, tray_id: str, menu_data: dict[str, Any]) -> None:
        """Build and attach a menu to a tray icon."""
        from pytauri.menu import Menu

        items = [self._build_menu_item(d) for d in menu_data.get("items", [])]
        menu = Menu.with_id_and_items(
            self.app_handle, menu_data.get("id", f"{tray_id}-menu"), items
        )
        tray.set_menu(menu)
        self.menus[menu_data.get("id", f"{tray_id}-menu")] = menu
        # Track which menu item IDs belong to this tray so the
        # global RunEvent.MenuEvent handler can skip them.
        for item_data in menu_data.get("items", []):
            iid = item_data.get("id", "")
            if iid:
                self.tray_menu_items.add(iid)

    def tray_create(self, cmd: dict[str, Any]) -> None:
        """Create a system tray icon."""
        from pytauri.tray import TrayIcon

        tray_id = cmd.get("tray_id", "")

        if self.app_handle is None:
            self.send_error("App not ready")
            return

        # If a tray with this ID already exists, drop the Python
        # reference.  The pyo3 Rust ``Drop`` on ``TrayIcon`` automatically
        # calls ``remove_tray_by_id`` and removes the OS icon.
        old = self.trays.pop(tray_id, None)
        if old is not None:
            with suppress(Exception):
                old.set_visible(False)
            del old  # Rust Drop removes from Tauri registry + OS

        try:
            tray = TrayIcon.with_id(self.app_handle, tray_id)

            tooltip = cmd.get("tooltip")
            if tooltip:
                tray.set_tooltip(tooltip)

            title = cmd.get("title")
            if title:
                tray.set_title(title)

            self._apply_tray_icon(tray, cmd)

            menu_data = cmd.get("menu")
            if menu_data:
                self._apply_tray_menu(tray, tray_id, menu_data)

            tray.set_show_menu_on_left_click(cmd.get("menu_on_left_click", True))

            # Register tray event handler
            def _on_tray_event(_tray_icon: Any, event: Any) -> None:
                self._handle_tray_event(tray_id, event)

            tray.on_tray_icon_event(_on_tray_event)

            # Register menu event handler for this tray
            def _on_menu_event(_app_handle: Any, menu_event: Any) -> None:
                item_id = str(menu_event)
                self.send(
                    {
                        "type": "event",
                        "event_type": "menu:click",
                        "label": f"__tray__{tray_id}",
                        "data": {"item_id": item_id, "source": "tray"},
                    }
                )

            tray.on_menu_event(_on_menu_event)

            self.trays[tray_id] = tray
            log(f"Created tray icon '{tray_id}'")
            resp: dict[str, Any] = {"type": "result", "success": True, "tray_id": tray_id}
            if cmd.get("request_id"):
                resp["request_id"] = cmd["request_id"]
            self.send(resp)
        except Exception as e:
            err_resp: dict[str, Any] = {
                "type": "error",
                "success": False,
                "error": f"Failed to create tray '{tray_id}': {e}",
            }
            if cmd.get("request_id"):
                err_resp["request_id"] = cmd["request_id"]
            log_error(err_resp["error"])
            self.send(err_resp)

    def tray_update(self, cmd: dict[str, Any]) -> None:
        """Update a tray icon property."""
        tray_id = cmd.get("tray_id", "")
        tray = self.trays.get(tray_id)
        if tray is None:
            self.send_error(f"Tray not found: {tray_id}")
            return

        try:
            if "tooltip" in cmd:
                tray.set_tooltip(cmd["tooltip"])
            if "title" in cmd:
                tray.set_title(cmd["title"])
            if "visible" in cmd:
                tray.set_visible(cmd["visible"])
            if "menu_on_left_click" in cmd:
                tray.set_show_menu_on_left_click(cmd["menu_on_left_click"])
            if "icon" in cmd:
                import base64

                from pytauri.image import Image

                raw = base64.b64decode(cmd["icon"])
                w = cmd.get("icon_width", 32)
                h = cmd.get("icon_height", 32)
                tray.set_icon(Image(raw, w, h))
            if "menu" in cmd:
                from pytauri.menu import Menu

                menu_data = cmd["menu"]
                items = [self._build_menu_item(d) for d in menu_data.get("items", [])]
                menu = Menu.with_id_and_items(
                    self.app_handle, menu_data.get("id", f"{tray_id}-menu"), items
                )
                tray.set_menu(menu)
                self.menus[menu_data.get("id", f"{tray_id}-menu")] = menu
                # Update tray_menu_items tracking for the replaced menu
                for item_data in menu_data.get("items", []):
                    iid = item_data.get("id", "")
                    if iid:
                        self.tray_menu_items.add(iid)
            log(f"tray_update '{tray_id}'")
        except Exception as e:
            self.send_error(f"tray_update failed: {e}")

    def tray_remove(self, cmd: dict[str, Any]) -> None:
        """Remove and destroy a tray icon.

        pytauri's ``TrayIcon`` has no ``remove()`` method.  The OS tray
        entry is removed when the pyo3 wrapper is deallocated (CPython
        ref-count → 0), which triggers Rust ``Drop`` → Tauri calls
        ``remove_tray_by_id`` internally.

        We must **not** call ``remove_tray_by_id`` ourselves — doing so
        causes a double-removal and Tauri prints an error to stderr.
        Instead we simply drop the Python reference.
        """
        tray_id = cmd.get("tray_id", "")
        if tray_id not in self.trays:
            resp: dict[str, Any] = {
                "type": "result",
                "success": False,
                "tray_id": tray_id,
                "error": f"Tray '{tray_id}' not found",
            }
            if cmd.get("request_id"):
                resp["request_id"] = cmd["request_id"]
            self.send(resp)
            return

        # Pop our reference — this is the ONLY Python ref to the
        # TrayIcon.  ``del tray`` at the end of this block drops the
        # refcount to 0 → pyo3 Rust Drop → OS icon removed.
        tray = self.trays.pop(tray_id)
        with suppress(Exception):
            tray.set_visible(False)  # instant visual hide
        del tray  # triggers Rust Drop → OS removal

        log(f"Removed tray '{tray_id}'")
        resp = {"type": "result", "success": True, "tray_id": tray_id}
        if cmd.get("request_id"):
            resp["request_id"] = cmd["request_id"]
        self.send(resp)

    def _handle_tray_event(self, tray_id: str, event: Any) -> None:
        """Map a pytauri TrayIconEvent to an IPC event."""
        from pytauri.tray import TrayIconEvent

        label = f"__tray__{tray_id}"
        data: dict[str, Any] = {"tray_id": tray_id}

        if isinstance(event, TrayIconEvent.Click):
            button = str(event.button).rsplit(".", 1)[-1].lower()  # "Left" -> "left"
            state = str(event.button_state).rsplit(".", 1)[-1].lower()
            data.update({"button": button, "button_state": state})
            if hasattr(event, "position"):
                pos = event.position
                data["position"] = {"x": pos[0], "y": pos[1]}
            self.send(
                {
                    "type": "event",
                    "event_type": "tray:click",
                    "label": label,
                    "data": data,
                }
            )
        elif isinstance(event, TrayIconEvent.DoubleClick):
            button = str(event.button).rsplit(".", 1)[-1].lower()
            data["button"] = button
            if hasattr(event, "position"):
                pos = event.position
                data["position"] = {"x": pos[0], "y": pos[1]}
            self.send(
                {
                    "type": "event",
                    "event_type": "tray:double-click",
                    "label": label,
                    "data": data,
                }
            )
        elif isinstance(event, TrayIconEvent.Enter):
            if hasattr(event, "position"):
                pos = event.position
                data["position"] = {"x": pos[0], "y": pos[1]}
            self.send(
                {
                    "type": "event",
                    "event_type": "tray:enter",
                    "label": label,
                    "data": data,
                }
            )
        elif isinstance(event, TrayIconEvent.Leave):
            if hasattr(event, "position"):
                pos = event.position
                data["position"] = {"x": pos[0], "y": pos[1]}
            self.send(
                {
                    "type": "event",
                    "event_type": "tray:leave",
                    "label": label,
                    "data": data,
                }
            )
        elif isinstance(event, TrayIconEvent.Move):
            if hasattr(event, "position"):
                pos = event.position
                data["position"] = {"x": pos[0], "y": pos[1]}
            self.send(
                {
                    "type": "event",
                    "event_type": "tray:move",
                    "label": label,
                    "data": data,
                }
            )


def stdin_reader(ipc: JsonIPC) -> None:
    """Read commands from stdin in a separate thread."""
    log("stdin_reader started")
    try:
        for raw_line in sys.stdin:
            line = raw_line.strip()
            if not line:
                continue
            try:
                cmd = json.loads(line)
                # If this message has a request_id that matches a pending
                # custom-command round-trip, consume it as a response.
                if ipc.handle_response(cmd):
                    continue
                ipc.handle_command(cmd)
            except json.JSONDecodeError as e:
                ipc.send_error(f"Invalid JSON: {e}")
            except Exception as e:
                ipc.send_error(f"Command error: {e}")

            if not ipc.running:
                break
    except Exception as e:
        log_error(f"stdin reader error: {e}")
    log("stdin_reader exiting")


def _handle_ready_event(ipc: JsonIPC, app_handle: Any) -> None:
    """Handle app ready event."""
    log("App ready!")

    # Set the macOS dock icon (no-op on other platforms)
    _set_macos_dock_icon()

    ipc.app_handle = app_handle
    # Get pre-configured main window
    main_window = Manager.get_webview_window(app_handle, "main")
    if main_window:
        ipc.windows["main"] = main_window
        log("Registered 'main' window")
    else:
        log("WARNING: 'main' window not found!")
    ipc.send_ready()


def _handle_close_requested(ipc: JsonIPC, app_handle: Any, label: str, window_event: Any) -> None:
    """Handle window close requested event."""
    # User clicked X - behavior depends on window mode:
    # - SINGLE_WINDOW: Always hide (reuse the window)
    # - NEW_WINDOW: Always destroy (each window is independent)
    # - MULTI_WINDOW: Use ON_WINDOW_CLOSE setting
    window_event.api.prevent_close()

    window = ipc.windows.get(label)
    if window is None:
        window = Manager.get_webview_window(app_handle, label)

    # Determine whether to destroy based on window mode
    if WINDOW_MODE == "single":
        should_destroy = False  # SINGLE_WINDOW: Always hide
    elif WINDOW_MODE == "new":
        should_destroy = True  # NEW_WINDOW: Always destroy
    else:
        should_destroy = ON_WINDOW_CLOSE == "close"  # MULTI_WINDOW: Use setting

    if should_destroy:
        log(f"CloseRequested for '{label}' - destroying")
        if window:
            window.destroy()
        if label in ipc.windows:
            del ipc.windows[label]
        ipc.send({"type": "event", "event_type": "window:closed", "label": label, "data": {}})
    else:
        log(f"CloseRequested for '{label}' - hiding")
        if window:
            window.hide()
        ipc.send({"type": "event", "event_type": "window:hidden", "label": label, "data": {}})


def _register_custom_commands(
    commands: Any,
    ipc: JsonIPC,
    command_names: list[str],
) -> None:
    """Register forwarding stubs for developer-defined custom commands.

    Each stub is a pytauri ``@commands.command()`` handler.  When JS calls
    ``pyInvoke('my_command', body)``, the stub forwards the call to the
    parent process over stdout IPC, waits for the parent to execute the
    real handler, and returns the result to JS.

    Parameters
    ----------
    commands : Commands
        The pytauri ``Commands`` instance to register on.
    ipc : JsonIPC
        The subprocess IPC handler (used for stdout send / response wait).
    command_names : list[str]
        Command names to register (from ``PYWRY_CUSTOM_COMMANDS`` env var).
    """

    class _AnyBody(BaseModel):
        """Accept any JSON payload from JS."""

        model_config: typing.ClassVar = {"extra": "allow"}

    for name in command_names:

        def _make_forwarder(_name: str) -> Any:
            """Create a closure so each command captures its own name."""

            async def _forwarder(body: _AnyBody) -> dict[str, Any]:
                result = ipc.send_request_and_wait(
                    {
                        "type": "custom_command",
                        "command": _name,
                        "data": body.model_dump(),
                    },
                    timeout=30.0,
                )
                return result

            _forwarder.__name__ = _name
            _forwarder.__qualname__ = _name
            return _forwarder

        forwarder = _make_forwarder(name)
        commands.set_command(name, forwarder)
        log(f"Registered custom command forwarder: {name}")


def main() -> int:  # noqa: C901  # pylint: disable=too-many-statements
    """Run the PyWry subprocess."""
    # Ignore SIGINT in the subprocess.  The parent process handles Ctrl-C
    # and sends a "quit" IPC command for a clean shutdown.  Without this,
    # SIGINT raises KeyboardInterrupt inside the Rust/PyO3 on_run callback
    # which causes a panic in pytauri-core.
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    from .commands import register_commands

    log(f"Starting subprocess... (headless={HEADLESS})")
    src_dir = Path(__file__).parent.absolute()
    ipc = JsonIPC()
    tmp_caps_dir: Path | None = None
    # Start stdin reader thread
    reader_thread = threading.Thread(target=stdin_reader, args=(ipc,), daemon=True)
    reader_thread.start()

    try:
        with (
            start_blocking_portal("asyncio") as portal,
            portal.wrap_async_context_manager(portal.call(create_task_group)) as _,
        ):
            # --- Dynamic plugin initialisation from env var ---
            plugin_csv = os.environ.get("PYWRY_TAURI_PLUGINS", "dialog,fs")
            plugin_names = [p.strip() for p in plugin_csv.split(",") if p.strip()]
            log(f"Requested Tauri plugins: {plugin_names}")
            plugins = _load_plugins(plugin_names)

            # --- Extra capabilities from env var ---
            extra_csv = os.environ.get("PYWRY_EXTRA_CAPABILITIES", "")
            extra_caps = [c.strip() for c in extra_csv.split(",") if c.strip()]
            ctx_dir = src_dir
            if extra_caps:
                tmp_caps_dir = _stage_extra_capabilities(src_dir, extra_caps)
                ctx_dir = tmp_caps_dir

            context = context_factory(ctx_dir)
            commands = Commands()
            register_commands(commands)

            # --- Register custom developer commands (forwarded to parent) ---
            custom_csv = os.environ.get("PYWRY_CUSTOM_COMMANDS", "")
            custom_names = [c.strip() for c in custom_csv.split(",") if c.strip()]
            if custom_names:
                _register_custom_commands(commands, ipc, custom_names)

            app = builder_factory().build(
                context=context,
                invoke_handler=commands.generate_handler(portal),
                plugins=plugins,
            )

            def on_run(app_handle: Any, run_event: Any) -> None:
                if isinstance(run_event, RunEvent.Ready):
                    _handle_ready_event(ipc, app_handle)
                elif isinstance(run_event, RunEvent.ExitRequested):
                    # Prevent app exit when all windows are closed
                    # This keeps the subprocess alive so windows can be recreated
                    if ipc.running:
                        log("ExitRequested - preventing exit to keep subprocess alive")
                        run_event.api.prevent_exit()
                elif isinstance(run_event, RunEvent.WindowEvent):
                    window_event = run_event.event
                    label = run_event.label
                    if isinstance(window_event, WindowEvent.CloseRequested):
                        _handle_close_requested(ipc, app_handle, label, window_event)
                    elif isinstance(window_event, WindowEvent.Destroyed) and label in ipc.windows:
                        del ipc.windows[label]
                        log(f"Window '{label}' destroyed, removed from cache")
                elif isinstance(run_event, RunEvent.MenuEvent):
                    # Menu item clicked — forward as menu:click event.
                    # Tray menu items are already handled by per-tray
                    # on_menu_event callbacks registered in tray_create;
                    # skip them here to avoid double-dispatch / spurious
                    # "Window not found" errors.
                    item_id = str(run_event._0)
                    if item_id in ipc.tray_menu_items:
                        pass  # handled by tray.on_menu_event
                    else:
                        # For app/window-level menus, broadcast to all windows
                        labels = list(ipc.windows.keys()) or ["main"]
                        for lbl in labels:
                            ipc.send(
                                {
                                    "type": "event",
                                    "event_type": "menu:click",
                                    "label": lbl,
                                    "data": {"item_id": item_id, "source": "app"},
                                }
                            )
                elif isinstance(run_event, RunEvent.TrayIconEvent):
                    # Tray events are handled per-tray via on_tray_icon_event
                    # This RunEvent variant is a fallback for unhandled trays
                    pass

            log("Starting app.run()...")
            app.run(on_run)
    except Exception as e:
        sys.stderr.write(f"[pywry] FATAL: {e}\n")
        sys.stderr.flush()
        import traceback

        traceback.print_exc()
        return 1
    finally:
        # Clean up staged capabilities temp dir
        if tmp_caps_dir is not None:
            shutil.rmtree(tmp_caps_dir, ignore_errors=True)

    log("Subprocess exiting")
    return 0


if __name__ == "__main__":
    sys.exit(main())
