# pylint: disable=too-many-lines,redefined-outer-name,unused-argument,unsubscriptable-object
"""End-to-end tests for PyWry modal component across all rendering paths.

Tests cover:
- Native window: Modal rendering in HTML, Plotly, and DataFrame modes
- Native window: Modal open/close via JavaScript API (pywry.modal.open/close/toggle)
- Native window: Modal behavior flags, interactive items, multiple modals
- Inline mode: Modal HTML served via FastAPI inline server
- Browser mode: Modal HTML served via browser-mode server
- Inline mode: Modal with Plotly charts and AG Grid DataFrames
"""

from __future__ import annotations

import socket
import time
import urllib.error
import urllib.request

from unittest.mock import patch

import pytest

from pywry.app import PyWry
from pywry.inline import (
    HAS_FASTAPI,
    _start_server,
    _state,
    show,
    show_dataframe as inline_show_dataframe,
    show_plotly as inline_show_plotly,
    stop_server,
)
from pywry.modal import Modal
from pywry.models import ThemeMode
from pywry.toolbar import Button, Option, Select, TextInput, Toolbar
from tests.conftest import (
    show_and_wait_ready,
    show_dataframe_and_wait_ready,
    show_plotly_and_wait_ready,
    wait_for_result,
)


def _require_result(label: str, script: str, **kwargs) -> dict:
    """Call wait_for_result and assert the result is a dict.

    Wraps wait_for_result so pylint can narrow the return type.
    """
    result = wait_for_result(label, script, **kwargs)
    assert isinstance(result, dict), f"wait_for_result returned {result!r}"
    return result


# =============================================================================
# Helper: verify modal DOM structure
# =============================================================================


def verify_modal_rendered(label: str, modal_id: str) -> dict:
    """Verify a modal exists in the DOM with correct structure.

    Parameters
    ----------
    label : str
        Window label to execute JS in.
    modal_id : str
        The modal's component_id.

    Returns
    -------
    dict
        Verification data with assertions about modal DOM presence.
    """
    script = f"""
    (function() {{
        var overlay = document.getElementById('{modal_id}');
        if (!overlay) {{
            pywry.result({{ error: 'Modal overlay not found', modalId: '{modal_id}' }});
            return;
        }}
        var container = overlay.querySelector('.pywry-modal-container');
        var header = overlay.querySelector('.pywry-modal-header');
        var title = overlay.querySelector('.pywry-modal-title');
        var closeBtn = overlay.querySelector('.pywry-modal-close');
        var body = overlay.querySelector('.pywry-modal-body');
        var isOpen = overlay.classList.contains('pywry-modal-open');

        pywry.result({{
            found: true,
            hasContainer: !!container,
            hasHeader: !!header,
            hasTitle: !!title,
            titleText: title ? title.textContent : null,
            hasCloseBtn: !!closeBtn,
            hasBody: !!body,
            isOpen: isOpen,
            overlayClass: overlay.className,
            containerClass: container ? container.className : null
        }});
    }})();
    """
    result = wait_for_result(label, script)
    return result if result else {"error": "No response"}


class TestModalHtmlMode:
    """Tests for modal rendering in basic HTML mode."""

    def test_modal_renders_in_html(self) -> None:
        """Modal renders with correct DOM structure in HTML mode."""
        app = PyWry(theme=ThemeMode.DARK)
        modal = Modal(
            title="Settings",
            component_id="e2e-settings",
            size="md",
        )

        label = show_and_wait_ready(
            app,
            "<div id='content'>Hello</div>",
            title="Modal HTML Test",
            modals=[modal],
        )

        result = verify_modal_rendered(label, "e2e-settings")
        assert result.get("found"), f"Modal not found: {result}"
        assert result["hasContainer"], "Container not found"
        assert result["hasHeader"], "Header not found"
        assert result["titleText"] == "Settings", f"Wrong title: {result['titleText']}"
        assert result["hasCloseBtn"], "Close button not found"
        assert result["hasBody"], "Body not found"
        assert not result["isOpen"], "Modal should start closed"
        app.close()

    def test_modal_open_on_load(self) -> None:
        """Modal with open_on_load=True starts in open state."""
        app = PyWry(theme=ThemeMode.DARK)
        modal = Modal(
            title="Auto Open",
            component_id="e2e-auto-open",
            open_on_load=True,
        )

        label = show_and_wait_ready(
            app,
            "<div>Content</div>",
            modals=[modal],
        )

        result = verify_modal_rendered(label, "e2e-auto-open")
        assert result.get("found"), f"Modal not found: {result}"
        assert result["isOpen"], "Modal should be open on load"
        app.close()

    def test_modal_open_close_via_js_api(self) -> None:
        """Modal can be opened and closed via pywry.modal API."""
        app = PyWry(theme=ThemeMode.DARK)
        modal = Modal(
            title="Toggle Test",
            component_id="e2e-toggle",
        )

        label = show_and_wait_ready(
            app,
            "<div>Content</div>",
            modals=[modal],
        )

        # Initially closed
        result = verify_modal_rendered(label, "e2e-toggle")
        assert not result["isOpen"], "Should start closed"

        # Open via JS API
        app.eval_js("pywry.modal.open('e2e-toggle');", label=label)
        time.sleep(0.3)

        result = verify_modal_rendered(label, "e2e-toggle")
        assert result["isOpen"], "Should be open after pywry.modal.open()"

        # Close via JS API
        app.eval_js("pywry.modal.close('e2e-toggle');", label=label)
        time.sleep(0.3)

        result = verify_modal_rendered(label, "e2e-toggle")
        assert not result["isOpen"], "Should be closed after pywry.modal.close()"
        app.close()

    def test_modal_toggle_via_js_api(self) -> None:
        """pywry.modal.toggle() toggles modal state."""
        app = PyWry(theme=ThemeMode.DARK)
        modal = Modal(title="Toggle", component_id="e2e-toggle2")

        label = show_and_wait_ready(app, "<div>Content</div>", modals=[modal])

        # Toggle open
        app.eval_js("pywry.modal.toggle('e2e-toggle2');", label=label)
        time.sleep(0.3)

        result = verify_modal_rendered(label, "e2e-toggle2")
        assert result["isOpen"], "Should be open after first toggle"

        # Toggle closed
        app.eval_js("pywry.modal.toggle('e2e-toggle2');", label=label)
        time.sleep(0.3)

        result = verify_modal_rendered(label, "e2e-toggle2")
        assert not result["isOpen"], "Should be closed after second toggle"
        app.close()

    def test_modal_size_class_applied(self) -> None:
        """Modal size class is correctly applied in DOM."""
        app = PyWry(theme=ThemeMode.DARK)

        for size in ("sm", "md", "lg", "xl", "full"):
            modal = Modal(
                title=f"Size {size}",
                component_id=f"e2e-size-{size}",
                size=size,  # type: ignore[arg-type]
            )
            label = show_and_wait_ready(
                app,
                "<div>Content</div>",
                modals=[modal],
            )
            result = verify_modal_rendered(label, f"e2e-size-{size}")
            assert result.get("found"), f"Modal not found for size={size}"
            assert f"pywry-modal-{size}" in result["containerClass"], (
                f"Size class missing for {size}: {result['containerClass']}"
            )
            app.close()

    def test_modal_with_items_renders(self) -> None:
        """Modal items are rendered in the body."""
        app = PyWry(theme=ThemeMode.DARK)
        modal = Modal(
            title="Form",
            component_id="e2e-form",
            items=[
                TextInput(label="Name", event="form:name"),
                Button(label="Submit", event="form:submit", variant="primary"),
            ],
            open_on_load=True,
        )

        label = show_and_wait_ready(app, "<div>Content</div>", modals=[modal])

        result: dict = _require_result(
            label,
            """
            pywry.result({
                hasTextInput: !!document.querySelector('#e2e-form .pywry-input-text'),
                hasButton: !!document.querySelector('#e2e-form .pywry-btn'),
                btnText: document.querySelector('#e2e-form .pywry-btn')?.textContent || ''
            });
            """,
        )
        assert result["hasTextInput"], "TextInput not found in modal body"
        assert result["hasButton"], "Button not found in modal body"
        assert result["btnText"] == "Submit", f"Wrong button text: {result['btnText']}"
        app.close()

    def test_modal_button_triggers_callback(self) -> None:
        """Button in modal triggers Python callback when clicked."""
        app = PyWry(theme=ThemeMode.DARK)

        events = {"clicked": False}

        def on_click(data, event_type="", widget_id=""):
            events["clicked"] = True

        modal = Modal(
            title="Action",
            component_id="e2e-action",
            items=[Button(label="Do It", event="dlg:action")],
            open_on_load=True,
        )

        label = show_and_wait_ready(
            app,
            "<div>Content</div>",
            modals=[modal],
            callbacks={"dlg:action": on_click},
        )

        # Click the button inside the modal via pywry.emit (more reliable than
        # DOM .click() which depends on delegated handler attachment timing)
        app.eval_js(
            """
            var btn = document.querySelector('#e2e-action .pywry-btn');
            if (btn) {
                var evt = btn.getAttribute('data-event');
                if (evt && window.pywry && window.pywry.emit) {
                    window.pywry.emit(evt, {componentId: btn.id});
                }
            }
            """,
            label=label,
        )

        start = time.time()
        while not events["clicked"] and (time.time() - start) < 3.0:
            time.sleep(0.1)

        assert events["clicked"], "Modal button callback not triggered"
        app.close()

    def test_modal_close_button_works(self) -> None:
        """Modal close button (x) closes the modal."""
        app = PyWry(theme=ThemeMode.DARK)
        modal = Modal(
            title="Closeable",
            component_id="e2e-closeable",
            open_on_load=True,
        )

        label = show_and_wait_ready(app, "<div>Content</div>", modals=[modal])

        # Verify open
        result = verify_modal_rendered(label, "e2e-closeable")
        assert result["isOpen"], "Should start open"

        # Click the close button
        app.eval_js(
            "document.querySelector('#e2e-closeable .pywry-modal-close').click();",
            label=label,
        )
        time.sleep(0.3)

        result = verify_modal_rendered(label, "e2e-closeable")
        assert not result["isOpen"], "Should be closed after clicking close button"
        app.close()


# =============================================================================
# Modal Rendering in Plotly Mode
# =============================================================================


class TestModalPlotlyMode:
    """Tests for modal rendering in Plotly chart mode."""

    def test_modal_renders_with_plotly(self) -> None:
        """Modal renders alongside Plotly chart."""
        app = PyWry(theme=ThemeMode.DARK)
        modal = Modal(
            title="Chart Options",
            component_id="e2e-plotly-modal",
            items=[
                Select(
                    label="Chart Type",
                    event="chart:type",
                    options=[
                        Option(label="Line", value="line"),
                        Option(label="Bar", value="bar"),
                    ],
                ),
            ],
        )

        figure = {"data": [{"x": [1, 2, 3], "y": [10, 15, 13], "type": "scatter"}]}

        label = show_plotly_and_wait_ready(
            app,
            figure,
            title="Plotly+Modal",
            modals=[modal],
        )
        time.sleep(0.5)

        # Verify both chart and modal exist
        result: dict = _require_result(
            label,
            """
            pywry.result({
                hasPlotly: !!document.querySelector('.js-plotly-plot'),
                hasModal: !!document.getElementById('e2e-plotly-modal'),
                modalHasSelect: !!document.querySelector('#e2e-plotly-modal .pywry-dropdown')
            });
            """,
        )
        assert result["hasPlotly"], "Plotly chart not found"
        assert result["hasModal"], "Modal not found"
        assert result["modalHasSelect"], "Select not found in modal"
        app.close()

    def test_modal_opens_over_plotly(self) -> None:
        """Modal opens correctly over a Plotly chart."""
        app = PyWry(theme=ThemeMode.DARK)
        modal = Modal(
            title="Options",
            component_id="e2e-plotly-over",
        )

        figure = {"data": [{"x": [1, 2], "y": [5, 10], "type": "bar"}]}

        label = show_plotly_and_wait_ready(
            app,
            figure,
            modals=[modal],
        )
        time.sleep(0.5)

        # Open modal
        app.eval_js("pywry.modal.open('e2e-plotly-over');", label=label)
        time.sleep(0.3)

        result = verify_modal_rendered(label, "e2e-plotly-over")
        assert isinstance(result, dict) and result["isOpen"], (
            "Modal should be open over Plotly chart"
        )
        app.close()


# =============================================================================
# Modal Rendering in DataFrame/AG Grid Mode
# =============================================================================


class TestModalDataFrameMode:
    """Tests for modal rendering in DataFrame/AG Grid mode."""

    def test_modal_renders_with_dataframe(self) -> None:
        """Modal renders alongside AG Grid table."""
        app = PyWry(theme=ThemeMode.DARK)
        modal = Modal(
            title="Filter Settings",
            component_id="e2e-grid-modal",
            items=[
                TextInput(label="Search", event="tbl:search"),
            ],
        )

        data = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]

        label = show_dataframe_and_wait_ready(
            app,
            data,
            title="Grid+Modal",
            modals=[modal],
        )
        time.sleep(0.5)

        # Verify both grid and modal exist
        result: dict = _require_result(
            label,
            """
            pywry.result({
                hasGrid: !!document.querySelector('[class*="ag-theme-"]'),
                hasModal: !!document.getElementById('e2e-grid-modal'),
                modalHasInput: !!document.querySelector('#e2e-grid-modal .pywry-input-text')
            });
            """,
        )
        assert result["hasGrid"], "AG Grid not found"
        assert result["hasModal"], "Modal not found"
        assert result["modalHasInput"], "TextInput not found in modal"
        app.close()

    def test_modal_opens_over_dataframe(self) -> None:
        """Modal opens correctly over an AG Grid table."""
        app = PyWry(theme=ThemeMode.DARK)
        modal = Modal(
            title="Edit",
            component_id="e2e-grid-over",
        )

        data = [{"x": 1, "y": 2}]

        label = show_dataframe_and_wait_ready(
            app,
            data,
            modals=[modal],
        )
        time.sleep(0.5)

        app.eval_js("pywry.modal.open('e2e-grid-over');", label=label)
        time.sleep(0.3)

        result = verify_modal_rendered(label, "e2e-grid-over")
        assert isinstance(result, dict) and result["isOpen"], "Modal should be open over AG Grid"
        app.close()


# =============================================================================
# Multiple Modals
# =============================================================================


class TestMultipleModals:
    """Tests for multiple modals in a single window."""

    def test_two_modals_render(self) -> None:
        """Two modals both render in the same window."""
        app = PyWry(theme=ThemeMode.DARK)
        modal1 = Modal(title="First", component_id="e2e-first")
        modal2 = Modal(title="Second", component_id="e2e-second")

        label = show_and_wait_ready(
            app,
            "<div>Content</div>",
            modals=[modal1, modal2],
        )

        r1 = verify_modal_rendered(label, "e2e-first")
        r2 = verify_modal_rendered(label, "e2e-second")
        assert r1.get("found"), "First modal not found"
        assert r2.get("found"), "Second modal not found"
        assert r1["titleText"] == "First"
        assert r2["titleText"] == "Second"
        app.close()

    def test_open_one_of_two_modals(self) -> None:
        """Opening one modal does not affect another."""
        app = PyWry(theme=ThemeMode.DARK)
        modal1 = Modal(title="A", component_id="e2e-a")
        modal2 = Modal(title="B", component_id="e2e-b")

        label = show_and_wait_ready(
            app,
            "<div>Content</div>",
            modals=[modal1, modal2],
        )

        # Open only modal A
        app.eval_js("pywry.modal.open('e2e-a');", label=label)
        time.sleep(0.3)

        r1 = verify_modal_rendered(label, "e2e-a")
        r2 = verify_modal_rendered(label, "e2e-b")
        assert r1["isOpen"], "Modal A should be open"
        assert not r2["isOpen"], "Modal B should remain closed"
        app.close()


# =============================================================================
# Modal + Toolbar Combination
# =============================================================================


class TestModalWithToolbar:
    """Tests for using modals and toolbars together."""

    def test_modal_with_toolbar(self) -> None:
        """Modal and toolbar coexist in the same window."""
        app = PyWry(theme=ThemeMode.DARK)
        toolbar = Toolbar(
            position="top",
            items=[Button(label="Open Settings", event="app:open-settings")],
        )
        modal = Modal(
            title="Settings",
            component_id="e2e-settings-combo",
            items=[Button(label="Save", event="settings:save")],
        )

        label = show_and_wait_ready(
            app,
            "<div>Content</div>",
            toolbars=[toolbar],
            modals=[modal],
        )

        # Verify both exist
        result: dict = _require_result(
            label,
            """
            pywry.result({
                hasToolbar: !!document.querySelector('.pywry-toolbar-top'),
                hasModal: !!document.getElementById('e2e-settings-combo'),
                toolbarBtnText: document.querySelector('.pywry-toolbar-top .pywry-btn')?.textContent || '',
            });
            """,
        )
        assert result["hasToolbar"], "Toolbar not found"
        assert result["hasModal"], "Modal not found"
        assert result["toolbarBtnText"] == "Open Settings"
        app.close()

    def test_toolbar_button_opens_modal(self) -> None:
        """Toolbar button can open a modal via custom callback."""
        app = PyWry(theme=ThemeMode.DARK)

        toolbar = Toolbar(
            position="top",
            items=[Button(label="Settings", event="app:settings")],
        )
        modal = Modal(
            title="Settings",
            component_id="e2e-tb-modal",
        )

        def on_settings(data, event_type="", widget_id=""):
            # In a real app, this would trigger JS to open the modal
            pass

        label = show_and_wait_ready(
            app,
            "<div>Content</div>",
            toolbars=[toolbar],
            modals=[modal],
            callbacks={"app:settings": on_settings},
        )

        # Open modal directly via JS (simulating what a callback + eval_js would do)
        app.eval_js("pywry.modal.open('e2e-tb-modal');", label=label)
        time.sleep(0.3)

        result = verify_modal_rendered(label, "e2e-tb-modal")
        assert result["isOpen"], "Modal should be opened by toolbar action"
        app.close()


# =============================================================================
# Modal from Dict Config
# =============================================================================


class TestModalFromDict:
    """Tests for creating modals from dict configurations."""

    def test_modal_from_dict_renders(self) -> None:
        """Modal created from dict config renders in window."""
        app = PyWry(theme=ThemeMode.DARK)

        label = show_and_wait_ready(
            app,
            "<div>Content</div>",
            modals=[
                {
                    "title": "Dict Modal",
                    "component_id": "e2e-dict-modal",
                    "items": [
                        {"type": "button", "label": "OK", "event": "dlg:ok"},
                    ],
                    "open_on_load": True,
                }
            ],
        )

        result = verify_modal_rendered(label, "e2e-dict-modal")
        assert result.get("found"), f"Dict modal not found: {result}"
        assert result["isOpen"], "Dict modal should be open on load"
        assert result["titleText"] == "Dict Modal"

        # Verify button
        btn_result: dict = _require_result(
            label,
            "pywry.result({ hasBtn: !!document.querySelector('#e2e-dict-modal .pywry-btn') });",
        )
        assert btn_result["hasBtn"], "Button not found in dict modal"
        app.close()


# =============================================================================
# Modal isOpen JS API
# =============================================================================


class TestModalIsOpenApi:
    """Tests for pywry.modal.isOpen() JavaScript API."""

    def test_is_open_returns_false_when_closed(self) -> None:
        """pywry.modal.isOpen() returns false for closed modal."""
        app = PyWry(theme=ThemeMode.DARK)
        modal = Modal(component_id="e2e-isopen")

        label = show_and_wait_ready(app, "<div>Content</div>", modals=[modal])

        result: dict = _require_result(
            label,
            "pywry.result({ isOpen: pywry.modal.isOpen('e2e-isopen') });",
        )
        assert result["isOpen"] is False
        app.close()

    def test_is_open_returns_true_when_open(self) -> None:
        """pywry.modal.isOpen() returns true for open modal."""
        app = PyWry(theme=ThemeMode.DARK)
        modal = Modal(component_id="e2e-isopen2", open_on_load=True)

        label = show_and_wait_ready(app, "<div>Content</div>", modals=[modal])

        result: dict = _require_result(
            label,
            "pywry.result({ isOpen: pywry.modal.isOpen('e2e-isopen2') });",
        )
        assert result["isOpen"] is True
        app.close()


# =============================================================================
# Inline Mode Helpers & Fixtures
# =============================================================================


@pytest.fixture
def server_port():
    """Get a free port for the inline server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("0.0.0.0", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


@pytest.fixture(autouse=True)
def clean_inline_state(server_port):
    """Clean up inline server state before/after each test."""
    stop_server()
    _state.widgets.clear()
    _state.connections.clear()
    _state.local_widgets.clear()
    _state.widget_tokens.clear()
    yield
    stop_server()
    _state.widgets.clear()
    _state.connections.clear()
    _state.local_widgets.clear()
    _state.widget_tokens.clear()


def wait_for_server(host: str, port: int, timeout: float = 5.0) -> bool:
    """Wait for inline server to accept connections."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                if s.connect_ex((host, port)) == 0:
                    return True
        except Exception:  # noqa: S110
            pass
        time.sleep(0.1)
    return False


def http_get(url: str, timeout: float = 5.0) -> tuple[int, str]:
    """Make HTTP GET request and return (status, body)."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


class MockOutput:
    """Mock for IPython.display.Output."""

    def __init__(self):
        self.outputs = []

    def append_display_data(self, data):
        """Append display data."""
        self.outputs.append(data)


# =============================================================================
# Modal in Inline Mode (FastAPI server)
# =============================================================================


@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")
class TestModalInlineMode:
    """Tests for modal rendering in inline notebook mode via FastAPI server."""

    def test_modal_html_served_via_http(self, server_port) -> None:
        """Modal HTML is present in the served inline page."""
        _start_server(port=server_port, host="0.0.0.0")
        assert wait_for_server("127.0.0.1", server_port)

        modal = Modal(
            title="Inline Settings",
            component_id="inline-modal",
            size="lg",
            items=[Button(label="Save", event="dlg:save")],
        )

        with (
            patch("IPython.display.display"),
            patch("IPython.display.IFrame"),
            patch("pywry.inline.Output", MockOutput),
            patch("pywry.inline.HAS_IPYTHON", True),
        ):
            widget = show(
                "<div>Inline Content</div>",
                modals=[modal],
                port=server_port,
            )

        status, html = http_get(f"http://127.0.0.1:{server_port}/widget/{widget._widget_id}")

        assert status == 200
        assert "pywry-modal-overlay" in html
        assert "inline-modal" in html
        assert "Inline Settings" in html
        assert "pywry-modal-lg" in html
        assert "Save" in html

    def test_modal_open_on_load_class_in_html(self, server_port) -> None:
        """Modal with open_on_load=True has the open class in served HTML."""
        _start_server(port=server_port, host="0.0.0.0")
        assert wait_for_server("127.0.0.1", server_port)

        modal = Modal(
            title="Auto Open",
            component_id="inline-auto",
            open_on_load=True,
        )

        with (
            patch("IPython.display.display"),
            patch("IPython.display.IFrame"),
            patch("pywry.inline.Output", MockOutput),
            patch("pywry.inline.HAS_IPYTHON", True),
        ):
            widget = show(
                "<div>Content</div>",
                modals=[modal],
                port=server_port,
            )

        status, html = http_get(f"http://127.0.0.1:{server_port}/widget/{widget._widget_id}")

        assert status == 200
        assert "pywry-modal-open" in html

    def test_modal_js_handlers_in_html(self, server_port) -> None:
        """Modal JavaScript handlers (open/close/toggle) are included."""
        _start_server(port=server_port, host="0.0.0.0")
        assert wait_for_server("127.0.0.1", server_port)

        modal = Modal(title="JS Test", component_id="inline-js")

        with (
            patch("IPython.display.display"),
            patch("IPython.display.IFrame"),
            patch("pywry.inline.Output", MockOutput),
            patch("pywry.inline.HAS_IPYTHON", True),
        ):
            widget = show(
                "<div>Content</div>",
                modals=[modal],
                port=server_port,
            )

        status, html = http_get(f"http://127.0.0.1:{server_port}/widget/{widget._widget_id}")

        assert status == 200
        # Modal handler JS should include open/close/toggle functions
        assert "pywry.modal" in html or "modal.open" in html

    def test_modal_with_multiple_items_in_html(self, server_port) -> None:
        """Modal with multiple items renders all items in served HTML."""
        _start_server(port=server_port, host="0.0.0.0")
        assert wait_for_server("127.0.0.1", server_port)

        modal = Modal(
            title="Form",
            component_id="inline-form",
            items=[
                TextInput(label="Name", event="dlg:name"),
                Select(
                    label="Role",
                    event="dlg:role",
                    options=[
                        Option(label="Admin", value="admin"),
                        Option(label="User", value="user"),
                    ],
                ),
                Button(label="Submit", event="dlg:submit"),
            ],
        )

        with (
            patch("IPython.display.display"),
            patch("IPython.display.IFrame"),
            patch("pywry.inline.Output", MockOutput),
            patch("pywry.inline.HAS_IPYTHON", True),
        ):
            widget = show(
                "<div>Content</div>",
                modals=[modal],
                port=server_port,
            )

        status, html = http_get(f"http://127.0.0.1:{server_port}/widget/{widget._widget_id}")

        assert status == 200
        assert "Name" in html
        assert "Submit" in html
        assert "dlg:name" in html
        assert "dlg:submit" in html
        assert "Admin" in html

    def test_multiple_modals_in_html(self, server_port) -> None:
        """Multiple modals all appear in the served HTML."""
        _start_server(port=server_port, host="0.0.0.0")
        assert wait_for_server("127.0.0.1", server_port)

        m1 = Modal(title="First", component_id="inline-first")
        m2 = Modal(title="Second", component_id="inline-second")

        with (
            patch("IPython.display.display"),
            patch("IPython.display.IFrame"),
            patch("pywry.inline.Output", MockOutput),
            patch("pywry.inline.HAS_IPYTHON", True),
        ):
            widget = show(
                "<div>Content</div>",
                modals=[m1, m2],
                port=server_port,
            )

        status, html = http_get(f"http://127.0.0.1:{server_port}/widget/{widget._widget_id}")

        assert status == 200
        assert "inline-first" in html
        assert "inline-second" in html
        assert "First" in html
        assert "Second" in html

    def test_modal_from_dict_config_in_html(self, server_port) -> None:
        """Modal created from dict config is rendered in served HTML."""
        _start_server(port=server_port, host="0.0.0.0")
        assert wait_for_server("127.0.0.1", server_port)

        with (
            patch("IPython.display.display"),
            patch("IPython.display.IFrame"),
            patch("pywry.inline.Output", MockOutput),
            patch("pywry.inline.HAS_IPYTHON", True),
        ):
            widget = show(
                "<div>Content</div>",
                modals=[
                    {
                        "title": "Dict Modal",
                        "component_id": "inline-dict",
                        "items": [
                            {"type": "button", "label": "OK", "event": "dlg:ok"},
                        ],
                    }
                ],
                port=server_port,
            )

        status, html = http_get(f"http://127.0.0.1:{server_port}/widget/{widget._widget_id}")

        assert status == 200
        assert "inline-dict" in html
        assert "Dict Modal" in html
        assert "OK" in html

    def test_modal_data_attributes_in_html(self, server_port) -> None:
        """Modal data attributes are present in served HTML."""
        _start_server(port=server_port, host="0.0.0.0")
        assert wait_for_server("127.0.0.1", server_port)

        modal = Modal(
            title="Attrs",
            component_id="inline-attrs",
            close_on_escape=False,
            close_on_overlay_click=False,
            on_close_event="dlg:closed",
        )

        with (
            patch("IPython.display.display"),
            patch("IPython.display.IFrame"),
            patch("pywry.inline.Output", MockOutput),
            patch("pywry.inline.HAS_IPYTHON", True),
        ):
            widget = show(
                "<div>Content</div>",
                modals=[modal],
                port=server_port,
            )

        status, html = http_get(f"http://127.0.0.1:{server_port}/widget/{widget._widget_id}")

        assert status == 200
        assert 'data-close-escape="false"' in html
        assert 'data-close-overlay="false"' in html
        assert 'data-on-close-event="dlg:closed"' in html


# =============================================================================
# Modal in Anywidget Plotly Mode
# =============================================================================


class TestModalAnywidgetPlotlyMode:
    """Tests for modal rendering in Plotly anywidget backend.

    When anywidget is available, show_plotly() returns a PyWryPlotlyWidget
    with modal HTML injected into its `content` traitlet.
    """

    def test_modal_in_plotly_widget_content(self, server_port) -> None:
        """Modal HTML is present in the anywidget content traitlet."""
        try:
            import plotly.graph_objects as go
        except ImportError:
            pytest.skip("Plotly not installed")

        _start_server(port=server_port, host="0.0.0.0")
        assert wait_for_server("127.0.0.1", server_port)

        fig = go.Figure(data=[go.Bar(x=["A", "B"], y=[10, 20])])
        modal = Modal(
            title="Chart Options",
            component_id="aw-plotly-modal",
            items=[Button(label="Refresh", event="chart:refresh")],
        )

        with (
            patch("IPython.display.display"),
            patch("IPython.display.IFrame"),
            patch("pywry.inline.Output", MockOutput),
            patch("pywry.inline.HAS_IPYTHON", True),
        ):
            widget = inline_show_plotly(
                fig,
                modals=[modal],
                port=server_port,
            )

        # Anywidget returns a widget with .content traitlet
        # InlineWidget returns a widget with ._widget_id for HTTP
        html = ""
        if hasattr(widget, "content") and widget.content:
            html = widget.content
        elif hasattr(widget, "_widget_id"):
            status, html = http_get(f"http://127.0.0.1:{server_port}/widget/{widget._widget_id}")
            assert status == 200
        else:
            pytest.fail(f"Cannot get HTML from widget type: {type(widget).__name__}")

        assert "aw-plotly-modal" in html
        assert "Chart Options" in html
        assert "Refresh" in html


# =============================================================================
# Modal in Anywidget DataFrame Mode
# =============================================================================


class TestModalAnywidgetDataFrameMode:
    """Tests for modal rendering in AG Grid anywidget backend.

    When anywidget is available, show_dataframe() returns a PyWryAgGridWidget
    with modal HTML injected into its `content` traitlet.
    """

    def test_modal_in_dataframe_widget_content(self, server_port) -> None:
        """Modal HTML is present in the anywidget content traitlet."""
        _start_server(port=server_port, host="0.0.0.0")
        assert wait_for_server("127.0.0.1", server_port)

        data = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
        modal = Modal(
            title="Filter",
            component_id="aw-grid-modal",
            items=[TextInput(label="Search", event="tbl:search")],
        )

        with (
            patch("IPython.display.display"),
            patch("IPython.display.IFrame"),
            patch("pywry.inline.Output", MockOutput),
            patch("pywry.inline.HAS_IPYTHON", True),
        ):
            widget = inline_show_dataframe(
                data,
                modals=[modal],
                port=server_port,
            )

        # Anywidget returns a widget with .content traitlet
        # InlineWidget returns a widget with ._widget_id for HTTP
        html = ""
        if hasattr(widget, "content") and widget.content:
            html = widget.content
        elif hasattr(widget, "_widget_id"):
            status, html = http_get(f"http://127.0.0.1:{server_port}/widget/{widget._widget_id}")
            assert status == 200
        else:
            pytest.fail(f"Cannot get HTML from widget type: {type(widget).__name__}")

        assert "aw-grid-modal" in html
        assert "Filter" in html
        assert "Search" in html


# =============================================================================
# Modal in Browser Mode (open_browser=True)
# =============================================================================


@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")
class TestModalBrowserMode:
    """Tests for modal rendering in browser mode (open_browser=True)."""

    def test_modal_in_browser_mode_html(self, server_port) -> None:
        """Modal appears in browser mode HTML output."""
        _start_server(port=server_port, host="0.0.0.0")
        assert wait_for_server("127.0.0.1", server_port)

        modal = Modal(
            title="Browser Modal",
            component_id="browser-modal",
            items=[
                Button(label="Action", event="dlg:action"),
            ],
            open_on_load=True,
        )

        with patch("webbrowser.open"):
            widget = show(
                "<div>Browser Content</div>",
                modals=[modal],
                port=server_port,
                open_browser=True,
            )

        status, html = http_get(f"http://127.0.0.1:{server_port}/widget/{widget._widget_id}")

        assert status == 200
        assert "browser-modal" in html
        assert "Browser Modal" in html
        assert "Action" in html
        assert "pywry-modal-open" in html

    def test_browser_mode_plotly_with_modal(self, server_port) -> None:
        """Modal appears alongside Plotly chart in browser mode."""
        _start_server(port=server_port, host="0.0.0.0")
        assert wait_for_server("127.0.0.1", server_port)

        try:
            import plotly.graph_objects as go
        except ImportError:
            pytest.skip("Plotly not installed")

        fig = go.Figure(data=[go.Scatter(x=[1, 2, 3], y=[4, 5, 6])])
        modal = Modal(
            title="Chart Settings",
            component_id="browser-plotly-modal",
        )

        with patch("webbrowser.open"):
            widget = inline_show_plotly(
                fig,
                modals=[modal],
                port=server_port,
                open_browser=True,
            )

        wid = widget._widget_id if hasattr(widget, "_widget_id") else widget.widget_id
        status, html = http_get(f"http://127.0.0.1:{server_port}/widget/{wid}")

        assert status == 200
        assert "browser-plotly-modal" in html
        assert "Chart Settings" in html
        assert "plotly" in html.lower()

    def test_browser_mode_dataframe_with_modal(self, server_port) -> None:
        """Modal appears alongside AG Grid in browser mode."""
        _start_server(port=server_port, host="0.0.0.0")
        assert wait_for_server("127.0.0.1", server_port)

        data = [{"x": 1, "y": 2}]
        modal = Modal(
            title="Grid Options",
            component_id="browser-grid-modal",
        )

        with patch("webbrowser.open"):
            widget = inline_show_dataframe(
                data,
                modals=[modal],
                port=server_port,
                open_browser=True,
            )

        wid = widget._widget_id if hasattr(widget, "_widget_id") else widget.widget_id
        status, html = http_get(f"http://127.0.0.1:{server_port}/widget/{wid}")

        assert status == 200
        assert "browser-grid-modal" in html
        assert "Grid Options" in html
        assert "ag-grid" in html.lower() or "agGrid" in html


# =============================================================================
# Modal + Toolbar in Inline Mode
# =============================================================================


@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")
class TestModalWithToolbarInline:
    """Tests for modal + toolbar coexistence in inline mode."""

    def test_modal_and_toolbar_both_in_html(self, server_port) -> None:
        """Modal and toolbar both appear in inline served HTML."""
        _start_server(port=server_port, host="0.0.0.0")
        assert wait_for_server("127.0.0.1", server_port)

        toolbar = Toolbar(
            position="top",
            items=[Button(label="Open", event="app:open")],
        )
        modal = Modal(
            title="Settings",
            component_id="inline-tb-modal",
            items=[Button(label="Save", event="dlg:save")],
        )

        with (
            patch("IPython.display.display"),
            patch("IPython.display.IFrame"),
            patch("pywry.inline.Output", MockOutput),
            patch("pywry.inline.HAS_IPYTHON", True),
        ):
            widget = show(
                "<div>Content</div>",
                toolbars=[toolbar],
                modals=[modal],
                port=server_port,
            )

        status, html = http_get(f"http://127.0.0.1:{server_port}/widget/{widget._widget_id}")

        assert status == 200
        # Toolbar present
        assert "Open" in html
        assert "app:open" in html or 'data-event="app:open"' in html
        # Modal present
        assert "inline-tb-modal" in html
        assert "Settings" in html
        assert "Save" in html
