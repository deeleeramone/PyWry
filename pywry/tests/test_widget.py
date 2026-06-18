"""Unit tests for pywry.widget targeting line coverage.

These tests cover:

* Lazy ESM/CSS loaders (``_get_*_widget_esm``, ``_get_pywry_base_css``,
  ``_get_aggrid_css_all``).
* The anywidget-based widgets: ``PyWryWidget``, ``PyWryPlotlyWidget``,
  ``PyWryAgGridWidget``, ``PyWryChatWidget``, ``PyWryTVChartWidget``.
* The fallback widgets that take effect when ``anywidget`` is missing
  (we monkey-patch ``HAS_ANYWIDGET`` to exercise them in isolation).

We avoid hitting the actual notebook/comm layer by stubbing
``IPython.display.display`` and ``anywidget.AnyWidget.send`` where needed.
"""

from __future__ import annotations

import json
import uuid

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from pywry.callbacks import get_registry


# ---------------------------------------------------------------------------
# ESM loader cache invalidation
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_callback_registry():
    get_registry().clear()
    yield
    get_registry().clear()


# ---------------------------------------------------------------------------
# Lazy ESM/CSS loaders
# ---------------------------------------------------------------------------


class TestEsmLoaders:
    def test_get_toolbar_handlers_js_loads(self):
        from pywry.widget import _get_toolbar_handlers_js

        # Cached after first call
        js = _get_toolbar_handlers_js()
        assert isinstance(js, str)
        assert len(js) > 0

    def test_get_toolbar_handlers_js_missing_file_raises(self, tmp_path, monkeypatch):
        from pywry import widget as widget_mod

        # Force a fresh load by clearing the lru_cache
        widget_mod._get_toolbar_handlers_js.cache_clear()
        monkeypatch.setattr(widget_mod, "_SRC_DIR", tmp_path)
        with pytest.raises(FileNotFoundError):
            widget_mod._get_toolbar_handlers_js()
        # Restore by clearing cache again so the real path repopulates
        widget_mod._get_toolbar_handlers_js.cache_clear()

    def test_get_plotly_widget_esm_loads(self):
        from pywry.widget import _get_plotly_widget_esm

        esm = _get_plotly_widget_esm()
        assert isinstance(esm, str)
        # Should reference Plotly
        assert "Plotly" in esm

    def test_get_plotly_widget_esm_missing_widget_file_raises(self, tmp_path, monkeypatch):
        from pywry import widget as widget_mod

        widget_mod._get_plotly_widget_esm.cache_clear()
        widget_mod._get_toolbar_handlers_js.cache_clear()
        monkeypatch.setattr(widget_mod, "_SRC_DIR", tmp_path)
        with pytest.raises(FileNotFoundError):
            widget_mod._get_plotly_widget_esm()
        # Restore real assets for subsequent tests
        widget_mod._get_plotly_widget_esm.cache_clear()
        widget_mod._get_toolbar_handlers_js.cache_clear()

    def test_get_plotly_widget_esm_no_plotly_assets_raises(self, monkeypatch):
        from pywry import widget as widget_mod

        widget_mod._get_plotly_widget_esm.cache_clear()
        with patch("pywry.assets.get_plotly_js", return_value=None):
            with pytest.raises(RuntimeError, match="Plotly.js not found"):
                widget_mod._get_plotly_widget_esm()
        widget_mod._get_plotly_widget_esm.cache_clear()

    def test_get_aggrid_css_all(self):
        from pywry.widget import _get_aggrid_css_all

        css = _get_aggrid_css_all()
        assert isinstance(css, str)

    def test_get_aggrid_widget_esm(self):
        from pywry.widget import _get_aggrid_widget_esm

        esm = _get_aggrid_widget_esm()
        assert isinstance(esm, str)
        assert len(esm) > 0

    def test_get_aggrid_widget_esm_missing_aggrid_assets(self, monkeypatch):
        from pywry import widget as widget_mod

        widget_mod._get_aggrid_widget_esm.cache_clear()
        with patch("pywry.assets.get_aggrid_js", return_value=None):
            with pytest.raises(RuntimeError, match="AG Grid JS not found"):
                widget_mod._get_aggrid_widget_esm()
        widget_mod._get_aggrid_widget_esm.cache_clear()

    def test_get_aggrid_widget_esm_missing_defaults(self, monkeypatch):
        from pywry import widget as widget_mod

        widget_mod._get_aggrid_widget_esm.cache_clear()
        with patch("pywry.assets.get_aggrid_defaults_js", return_value=None):
            with pytest.raises(RuntimeError, match="AG Grid defaults JS not found"):
                widget_mod._get_aggrid_widget_esm()
        widget_mod._get_aggrid_widget_esm.cache_clear()

    def test_get_widget_esm(self):
        from pywry.widget import _get_widget_esm

        esm = _get_widget_esm()
        assert isinstance(esm, str)

    def test_get_tvchart_widget_esm(self):
        from pywry.widget import _get_tvchart_widget_esm

        esm = _get_tvchart_widget_esm()
        assert isinstance(esm, str)

    def test_get_tvchart_widget_esm_missing_tvchart_js(self, monkeypatch):
        from pywry import widget as widget_mod

        widget_mod._get_tvchart_widget_esm.cache_clear()
        with patch("pywry.assets.get_tvchart_js", return_value=None):
            with pytest.raises(RuntimeError, match="LightweightCharts JS not found"):
                widget_mod._get_tvchart_widget_esm()
        widget_mod._get_tvchart_widget_esm.cache_clear()

    def test_get_tvchart_widget_esm_missing_defaults(self, monkeypatch):
        from pywry import widget as widget_mod

        widget_mod._get_tvchart_widget_esm.cache_clear()
        with patch("pywry.assets.get_tvchart_defaults_js", return_value=None):
            with pytest.raises(RuntimeError, match="TVChart defaults JS not found"):
                widget_mod._get_tvchart_widget_esm()
        widget_mod._get_tvchart_widget_esm.cache_clear()

    def test_get_tvchart_widget_esm_missing_widget_file(self, tmp_path, monkeypatch):
        from pywry import widget as widget_mod

        widget_mod._get_tvchart_widget_esm.cache_clear()
        widget_mod._get_toolbar_handlers_js.cache_clear()
        # Provide a stub toolbar-handlers.js so the toolbar loader succeeds —
        # the FileNotFoundError we're after is the tvchart-widget.js one.
        (tmp_path / "toolbar-handlers.js").write_text("// stub")
        monkeypatch.setattr(widget_mod, "_SRC_DIR", tmp_path)
        with pytest.raises(FileNotFoundError, match="TVChart widget JS"):
            widget_mod._get_tvchart_widget_esm()
        widget_mod._get_tvchart_widget_esm.cache_clear()
        widget_mod._get_toolbar_handlers_js.cache_clear()

    def test_get_chat_widget_esm(self):
        from pywry.widget import _get_chat_widget_esm

        esm = _get_chat_widget_esm()
        assert isinstance(esm, str)

    def test_get_chat_widget_esm_handles_missing_chat_handlers(self, tmp_path, monkeypatch):
        # Even when chat-handlers.js is missing, the chat ESM should still
        # build (it gracefully falls back to "").
        from pywry import widget as widget_mod

        widget_mod._get_toolbar_handlers_js.cache_clear()
        monkeypatch.setattr(widget_mod, "_SRC_DIR", tmp_path)
        # Recreate the toolbar-handlers.js so _get_toolbar_handlers_js succeeds
        (tmp_path / "toolbar-handlers.js").write_text("// stub")
        try:
            esm = widget_mod._get_chat_widget_esm()
            assert isinstance(esm, str)
        finally:
            widget_mod._get_toolbar_handlers_js.cache_clear()

    def test_get_pywry_base_css(self):
        from pywry.widget import _get_pywry_base_css

        css = _get_pywry_base_css()
        assert isinstance(css, str)


# ---------------------------------------------------------------------------
# anywidget-based widget classes
# ---------------------------------------------------------------------------


anywidget = pytest.importorskip("anywidget")


class TestPyWryWidget:
    def test_init_sets_traits(self):
        from pywry.widget import PyWryWidget

        w = PyWryWidget(content="<p>hi</p>", theme="light", width="200px", height="100px")
        assert w.content == "<p>hi</p>"
        assert w.theme == "light"
        assert w.width == "200px"
        assert w.height == "100px"
        assert w.label.startswith("w-")

    def test_label_property(self):
        from pywry.widget import PyWryWidget

        w = PyWryWidget()
        # Label should be a uuid-based string
        assert w.label == w._label

    def test_handle_js_event_empty_change(self):
        from pywry.widget import PyWryWidget

        w = PyWryWidget()
        # Should not raise
        w._handle_js_event({"new": ""})

    def test_handle_js_event_invokes_handlers(self):
        from pywry.widget import PyWryWidget

        w = PyWryWidget()
        called = []
        w.on("custom:event", lambda data, etype, lbl: called.append((data, etype, lbl)))

        change = {"new": json.dumps({"type": "custom:event", "data": {"v": 1}})}
        w._handle_js_event(change)
        assert called == [({"v": 1}, "custom:event", w.label)]

    def test_handle_js_event_dispatches_to_global_registry(self):
        from pywry.widget import PyWryWidget

        w = PyWryWidget()
        registry = get_registry()
        called = []
        registry.register(w.label, "global:event", lambda d, *_: called.append(d))

        change = {"new": json.dumps({"type": "global:event", "data": {"k": "v"}})}
        w._handle_js_event(change)
        assert called == [{"k": "v"}]

    def test_handle_js_event_handles_invalid_json(self):
        from pywry.widget import PyWryWidget

        w = PyWryWidget()
        # Should not raise - exception is caught
        w._handle_js_event({"new": "not-json{"})

    def test_on_returns_self(self):
        from pywry.widget import PyWryWidget

        w = PyWryWidget()
        result = w.on("foo", lambda *args: None)
        assert result is w

    def test_on_appends_to_existing_handler_list(self):
        from pywry.widget import PyWryWidget

        w = PyWryWidget()
        w.on("foo", lambda *args: None)
        w.on("foo", lambda *args: None)
        assert len(w._handlers["foo"]) == 2

    def test_emit_serializes_payload(self):
        from pywry.widget import PyWryWidget

        w = PyWryWidget()
        # Patch send to avoid trying to send through a real comm
        with patch.object(w, "send") as mock_send:
            w.emit("foo:bar", {"x": 1})
            # _py_event should be set to a JSON event
            payload = json.loads(w._py_event)
            assert payload["type"] == "foo:bar"
            assert payload["data"] == {"x": 1}
            assert "ts" in payload
            mock_send.assert_called_once()

    def test_emit_handles_send_failure(self):
        from pywry.widget import PyWryWidget

        w = PyWryWidget()
        # Make send raise -> falls back to send_state silently
        with (
            patch.object(w, "send", side_effect=RuntimeError("no comm")),
            patch.object(w, "send_state") as mock_send_state,
        ):
            w.emit("foo:bar", {"x": 1})
            # send_state may be called more than once (traitlets internals
            # also call it during the trait write).  We only care that the
            # fallback path explicitly invoked it for "_py_event".
            assert mock_send_state.call_count >= 1
            assert any(
                call.args == ("_py_event",) or call.kwargs.get("key") == "_py_event"
                for call in mock_send_state.call_args_list
            )

    def test_emit_with_none_data(self):
        from pywry.widget import PyWryWidget

        w = PyWryWidget()
        with patch.object(w, "send"):
            w.emit("foo:bar", None)
            payload = json.loads(w._py_event)
            assert payload["data"] == {}

    def test_update_changes_content(self):
        from pywry.widget import PyWryWidget

        w = PyWryWidget()
        w.update("<h1>new</h1>")
        assert w.content == "<h1>new</h1>"

    def test_set_content_alias(self):
        from pywry.widget import PyWryWidget

        w = PyWryWidget()
        w.set_content("<p>x</p>")
        assert w.content == "<p>x</p>"

    def test_display_calls_ipython(self):
        from pywry.widget import PyWryWidget

        w = PyWryWidget()
        with patch("IPython.display.display") as mock_display:
            w.display()
            mock_display.assert_called_once_with(w)

    def test_from_html_no_callbacks(self):
        from pywry.widget import PyWryWidget

        w = PyWryWidget.from_html("<p>x</p>")
        assert isinstance(w, PyWryWidget)

    def test_from_html_with_callbacks(self):
        from pywry.widget import PyWryWidget

        cb = lambda *args: None  # noqa: E731
        w = PyWryWidget.from_html("<p>x</p>", callbacks={"foo": cb})
        assert "foo" in w._handlers

    def test_from_html_with_int_height_normalises(self):
        from pywry.widget import PyWryWidget

        w = PyWryWidget.from_html("<p>x</p>", height=300)
        assert w.height == "300px"

    def test_from_html_with_toolbars(self):
        from pywry.toolbar import Toolbar
        from pywry.widget import PyWryWidget

        tb = Toolbar(items=[])
        w = PyWryWidget.from_html("<p>x</p>", toolbars=[tb])
        assert isinstance(w, PyWryWidget)

    def test_from_html_with_modals(self):
        from pywry.modal import Modal
        from pywry.widget import PyWryWidget

        modal = Modal(title="Test", items=[])
        w = PyWryWidget.from_html("<p>x</p>", modals=[modal])
        assert isinstance(w, PyWryWidget)

    def test_from_html_with_secret_inputs(self):
        from pywry.toolbar import SecretInput, Toolbar
        from pywry.widget import PyWryWidget

        secret = SecretInput(component_id="api-key", value="my-secret")
        tb = Toolbar(items=[secret])
        w = PyWryWidget.from_html("<p>x</p>", toolbars=[tb])
        assert isinstance(w, PyWryWidget)

    def test_from_html_with_modal_secret_inputs(self):
        """Cover the modal-secret-input branch in from_html."""
        from pywry.modal import Modal
        from pywry.toolbar import SecretInput
        from pywry.widget import PyWryWidget

        secret = SecretInput(component_id="modal-api-key", value="ms-secret")
        modal = Modal(title="t", items=[secret])
        w = PyWryWidget.from_html("<p>x</p>", modals=[modal])
        assert isinstance(w, PyWryWidget)


class TestPyWryPlotlyWidget:
    def test_init_sets_chart_id(self):
        from pywry.widget import PyWryPlotlyWidget

        w = PyWryPlotlyWidget(figure_json='{"data":[]}', chart_id="my-chart")
        assert w.chart_id == "my-chart"
        assert w.figure_json == '{"data":[]}'

    def test_init_defaults_chart_id_to_label(self):
        from pywry.widget import PyWryPlotlyWidget

        w = PyWryPlotlyWidget()
        assert w.chart_id == w._label

    def test_emit_includes_chart_id(self):
        from pywry.widget import PyWryPlotlyWidget

        w = PyWryPlotlyWidget(chart_id="cid")
        with patch.object(w, "send"):
            w.emit("foo:bar", {"x": 1})
            payload = json.loads(w._py_event)
            assert payload["data"]["chartId"] == "cid"

    def test_emit_preserves_existing_chart_id(self):
        from pywry.widget import PyWryPlotlyWidget

        w = PyWryPlotlyWidget(chart_id="cid")
        with patch.object(w, "send"):
            w.emit("foo:bar", {"chartId": "other"})
            payload = json.loads(w._py_event)
            assert payload["data"]["chartId"] == "other"

    def test_emit_with_none_data(self):
        from pywry.widget import PyWryPlotlyWidget

        w = PyWryPlotlyWidget(chart_id="cid")
        with patch.object(w, "send"):
            w.emit("foo:bar", None)
            payload = json.loads(w._py_event)
            assert payload["data"]["chartId"] == "cid"


class TestPyWryAgGridWidget:
    def test_init_basic(self):
        from pywry.widget import PyWryAgGridWidget

        w = PyWryAgGridWidget(grid_config="{}", grid_id="g1")
        assert w.grid_id == "g1"
        assert w.grid_config == "{}"

    def test_init_defaults_grid_id_to_label(self):
        from pywry.widget import PyWryAgGridWidget

        w = PyWryAgGridWidget()
        assert w.grid_id == w._label

    def test_init_registers_csv_export_handler(self):
        from pywry.widget import PyWryAgGridWidget

        w = PyWryAgGridWidget()
        assert "grid:export-csv" in w._handlers

    def test_emit_includes_grid_id(self):
        from pywry.widget import PyWryAgGridWidget

        w = PyWryAgGridWidget(grid_id="g1")
        with patch.object(w, "send"):
            w.emit("foo:bar", {"x": 1})
            payload = json.loads(w._py_event)
            assert payload["data"]["gridId"] == "g1"

    def test_emit_preserves_existing_grid_id(self):
        from pywry.widget import PyWryAgGridWidget

        w = PyWryAgGridWidget(grid_id="g1")
        with patch.object(w, "send"):
            w.emit("foo:bar", {"gridId": "other"})
            payload = json.loads(w._py_event)
            assert payload["data"]["gridId"] == "other"

    def test_emit_with_none_data(self):
        from pywry.widget import PyWryAgGridWidget

        w = PyWryAgGridWidget(grid_id="g1")
        with patch.object(w, "send"):
            w.emit("foo:bar", None)
            payload = json.loads(w._py_event)
            assert payload["data"]["gridId"] == "g1"

    def test_csv_export_handler_normalises_line_endings(self):
        from pywry.widget import PyWryAgGridWidget

        w = PyWryAgGridWidget()
        emitted = []
        original_emit = w.emit
        w.emit = lambda etype, data: emitted.append((etype, data))  # type: ignore[method-assign]
        try:
            handlers = w._handlers["grid:export-csv"]
            assert len(handlers) >= 1
            # Invoke the handler with some CSV containing CRLF
            handlers[0]({"csvContent": "a,b\r\n1,2\r\n", "fileName": "x.csv"}, "", "")
            assert emitted
            etype, payload = emitted[0]
            assert etype == "pywry:download"
            assert payload["filename"] == "x.csv"
            assert "\r" not in payload["content"]
        finally:
            w.emit = original_emit  # type: ignore[method-assign]

    def test_csv_export_handler_default_filename(self):
        from pywry.widget import PyWryAgGridWidget

        w = PyWryAgGridWidget()
        emitted = []
        original_emit = w.emit
        w.emit = lambda etype, data: emitted.append((etype, data))  # type: ignore[method-assign]
        try:
            handler = w._handlers["grid:export-csv"][0]
            handler({"csvContent": "a,b\n1,2"}, "", "")
            _etype, payload = emitted[0]
            assert payload["filename"] == "export.csv"
        finally:
            w.emit = original_emit  # type: ignore[method-assign]

    def test_export_dir_property_get_set(self):
        from pywry.widget import PyWryAgGridWidget

        w = PyWryAgGridWidget(export_dir="/tmp/foo")
        assert w.export_dir == "/tmp/foo"
        w.export_dir = "/tmp/bar"
        assert w.export_dir == "/tmp/bar"

    def test_normalize_data_dataframe(self):
        from pywry.widget import PyWryAgGridWidget

        w = PyWryAgGridWidget()

        class FakeDF:
            columns = ["a", "b"]

            def to_dict(self, orient="records"):
                return [{"a": 1, "b": 2}, {"a": 3, "b": 4}]

        result = w._normalize_data(FakeDF())
        assert result == [{"a": 1, "b": 2}, {"a": 3, "b": 4}]

    def test_normalize_data_list(self):
        from pywry.widget import PyWryAgGridWidget

        w = PyWryAgGridWidget()
        data = [{"a": 1}, {"a": 2}]
        assert w._normalize_data(data) == data

    def test_normalize_data_dict_of_lists(self):
        from pywry.widget import PyWryAgGridWidget

        w = PyWryAgGridWidget()
        result = w._normalize_data({"a": [1, 2], "b": [3, 4]})
        assert result == [{"a": 1, "b": 3}, {"a": 2, "b": 4}]

    def test_normalize_data_empty_dict(self):
        from pywry.widget import PyWryAgGridWidget

        w = PyWryAgGridWidget()
        assert w._normalize_data({}) == []

    def test_normalize_data_unsupported(self):
        from pywry.widget import PyWryAgGridWidget

        w = PyWryAgGridWidget()
        assert w._normalize_data(42) == []

    def test_display_uses_ipython(self):
        from pywry.widget import PyWryAgGridWidget

        w = PyWryAgGridWidget()
        with patch("IPython.display.display") as mock_display:
            w.display()
            mock_display.assert_called_once_with(w)


class TestPyWryTVChartWidget:
    def test_init_default_chart_id(self):
        from pywry.widget import PyWryTVChartWidget

        w = PyWryTVChartWidget()
        assert w.chart_id == w._label

    def test_init_custom_chart_id(self):
        from pywry.widget import PyWryTVChartWidget

        w = PyWryTVChartWidget(chart_id="my-chart", chart_config="{}")
        assert w.chart_id == "my-chart"
        assert w.chart_config == "{}"

    def test_emit_includes_chart_id(self):
        from pywry.widget import PyWryTVChartWidget

        w = PyWryTVChartWidget(chart_id="tv1")
        with patch.object(w, "send"):
            w.emit("tvchart:foo", {"x": 1})
            payload = json.loads(w._py_event)
            assert payload["data"]["chartId"] == "tv1"

    def test_emit_with_none_data(self):
        from pywry.widget import PyWryTVChartWidget

        w = PyWryTVChartWidget(chart_id="tv1")
        with patch.object(w, "send"):
            w.emit("tvchart:foo", None)
            payload = json.loads(w._py_event)
            assert payload["data"]["chartId"] == "tv1"

    def test_emit_preserves_existing_chart_id(self):
        from pywry.widget import PyWryTVChartWidget

        w = PyWryTVChartWidget(chart_id="tv1")
        with patch.object(w, "send"):
            w.emit("tvchart:foo", {"chartId": "other"})
            payload = json.loads(w._py_event)
            assert payload["data"]["chartId"] == "other"

    def test_display(self):
        from pywry.widget import PyWryTVChartWidget

        w = PyWryTVChartWidget()
        with patch("IPython.display.display") as mock_display:
            w.display()
            mock_display.assert_called_once_with(w)


class TestPyWryChatWidget:
    def test_init(self):
        from pywry.widget import PyWryChatWidget

        w = PyWryChatWidget(content="<p>chat</p>")
        assert w.content == "<p>chat</p>"
        assert w._asset_js == ""
        assert w._asset_css == ""


# ---------------------------------------------------------------------------
# Fallback widgets (anywidget unavailable)
# ---------------------------------------------------------------------------


class TestFallbackWidgets:
    """Exercise the fallback classes that are defined when anywidget is
    unavailable.  We can't actually uninstall anywidget — instead we
    construct fresh fallback classes by re-executing the fallback branch
    of widget.py inside a controlled namespace."""

    def _build_fallback_namespace(self):
        """Reconstruct the fallback-class branch of widget.py in isolation.

        This avoids touching the actually installed PyWryWidget (which is
        the anywidget version)."""
        from pywry.state_mixins import EmittingWidget

        ns: dict[str, Any] = {
            "EmittingWidget": EmittingWidget,
            "uuid": uuid,
            "Callable": __import__("typing").Callable,
            "Any": Any,
        }
        # Build the fallback PyWryWidget class
        fallback_src = """
class PyWryWidget(EmittingWidget):
    def __init__(self, **kwargs):
        self._label = f"w-{uuid.uuid4().hex[:8]}"
        self.content = kwargs.get("content", "")
        self._handlers = {}

    @property
    def label(self):
        return self._label

    def on(self, event_type, callback, label=None):
        self._handlers.setdefault(event_type, []).append(callback)
        return self

    def emit(self, event_type, data=None):
        pass

    def set_content(self, content):
        self.content = content

    def update(self, html):
        self.content = html

    def _repr_html_(self):
        return (
            "<div style='padding:20px;background:#ff6b6b;color:#fff;"
            "border-radius:8px'><b>anywidget not installed. "
            "Run: pip install anywidget</b></div>"
        )

    def display(self):
        pass

    @classmethod
    def from_html(cls, content, callbacks=None, theme="dark", width="100%",
                  height="500px", toolbars=None, modals=None):
        del callbacks, theme, width, height, toolbars, modals
        return cls(content=content)


class PyWryPlotlyWidget(PyWryWidget):
    pass


class PyWryAgGridWidget(PyWryWidget):
    def update_data(self, data):
        pass

    def update_columns(self, columns):
        pass

    def update_grid(self, data=None, columns=None):
        pass


class PyWryChatWidget(PyWryWidget):
    pass


class PyWryTVChartWidget(PyWryWidget):
    def _wire_datafeed_provider(self, provider):
        pass
"""
        exec(fallback_src, ns)
        return ns

    def test_fallback_pywrywidget_init(self):
        ns = self._build_fallback_namespace()
        W = ns["PyWryWidget"]
        w = W(content="<p>x</p>")
        assert w.content == "<p>x</p>"
        assert w.label.startswith("w-")

    def test_fallback_on_returns_self(self):
        ns = self._build_fallback_namespace()
        w = ns["PyWryWidget"]()
        result = w.on("foo", lambda *a: None)
        assert result is w
        assert "foo" in w._handlers

    def test_fallback_emit_is_noop(self):
        ns = self._build_fallback_namespace()
        w = ns["PyWryWidget"]()
        # Should not raise
        w.emit("foo", {})
        w.emit("foo", None)

    def test_fallback_set_content(self):
        ns = self._build_fallback_namespace()
        w = ns["PyWryWidget"]()
        w.set_content("<p>x</p>")
        assert w.content == "<p>x</p>"

    def test_fallback_update(self):
        ns = self._build_fallback_namespace()
        w = ns["PyWryWidget"]()
        w.update("<p>y</p>")
        assert w.content == "<p>y</p>"

    def test_fallback_repr_html(self):
        ns = self._build_fallback_namespace()
        w = ns["PyWryWidget"]()
        html = w._repr_html_()
        assert "anywidget not installed" in html

    def test_fallback_display_noop(self):
        ns = self._build_fallback_namespace()
        w = ns["PyWryWidget"]()
        w.display()  # No raise

    def test_fallback_from_html(self):
        ns = self._build_fallback_namespace()
        W = ns["PyWryWidget"]
        w = W.from_html("<p>x</p>", callbacks={"a": lambda *args: None})
        assert isinstance(w, W)
        assert w.content == "<p>x</p>"

    def test_fallback_aggrid_no_op_methods(self):
        ns = self._build_fallback_namespace()
        w = ns["PyWryAgGridWidget"]()
        w.update_data([])
        w.update_columns([])
        w.update_grid()
        w.update_grid(data=[], columns=[])

    def test_fallback_tvchart_wire_datafeed_noop(self):
        ns = self._build_fallback_namespace()
        w = ns["PyWryTVChartWidget"]()
        w._wire_datafeed_provider(provider=MagicMock())  # No raise


# ---------------------------------------------------------------------------
# HAS_ANYWIDGET branch coverage (lines 30-31)
# ---------------------------------------------------------------------------


class TestHasAnywidgetImport:
    """Lines 30-31 and the ``else`` branch (~line 2030+) of widget.py only run
    when ``anywidget`` is missing.  We exercise them by reloading the module
    with anywidget hidden, then restore the real module afterwards."""

    def test_import_without_anywidget(self):
        """Force the ImportError branch by hiding anywidget at import time."""
        import importlib
        import sys

        # Save existing references
        saved_anywidget = sys.modules.get("anywidget")
        saved_traitlets = sys.modules.get("traitlets")
        saved_widget = sys.modules.get("pywry.widget")

        # Block anywidget imports by stubbing it as a package that raises
        sys.modules["anywidget"] = None  # None entry triggers ImportError on `import anywidget`

        try:
            # Force a reload by removing cached module
            if "pywry.widget" in sys.modules:
                del sys.modules["pywry.widget"]

            import pywry.widget as fresh_widget  # type: ignore[import]

            assert fresh_widget.HAS_ANYWIDGET is False

            # Fallback PyWryWidget
            w = fresh_widget.PyWryWidget(content="<p>x</p>")
            assert w.content == "<p>x</p>"
            assert w.label.startswith("w-")
            # Property
            assert w.label == w._label
            # on() returns self and registers handler
            cb = lambda *a: None  # noqa: E731
            assert w.on("foo", cb) is w
            assert "foo" in w._handlers
            # emit() is a no-op
            w.emit("foo", {"x": 1})
            w.emit("foo")
            # set_content/update
            w.set_content("<p>y</p>")
            assert w.content == "<p>y</p>"
            w.update("<p>z</p>")
            assert w.content == "<p>z</p>"
            # _repr_html_ contains the install-anywidget message
            assert "anywidget not installed" in w._repr_html_()
            # display is a no-op
            w.display()
            # from_html
            w2 = fresh_widget.PyWryWidget.from_html(
                "<p>x</p>",
                callbacks={"a": cb},
                theme="dark",
                width="100%",
                height="500px",
                toolbars=[],
                modals=[],
            )
            assert isinstance(w2, fresh_widget.PyWryWidget)

            # Fallback PyWryAgGridWidget no-ops
            grid = fresh_widget.PyWryAgGridWidget()
            grid.update_data([])
            grid.update_columns([])
            grid.update_grid()
            grid.update_grid(data=[], columns=[])

            # Fallback PyWryTVChartWidget._wire_datafeed_provider
            tv = fresh_widget.PyWryTVChartWidget()
            tv._wire_datafeed_provider(provider=MagicMock())

            # Fallback PyWryPlotlyWidget and PyWryChatWidget exist
            assert fresh_widget.PyWryPlotlyWidget is not None
            assert fresh_widget.PyWryChatWidget is not None

        finally:
            # Restore environment
            if saved_anywidget is not None:
                sys.modules["anywidget"] = saved_anywidget
            else:
                sys.modules.pop("anywidget", None)
            if saved_traitlets is not None:
                sys.modules["traitlets"] = saved_traitlets

            # Restore the original widget module so subsequent tests see anywidget
            if "pywry.widget" in sys.modules:
                del sys.modules["pywry.widget"]
            if saved_widget is not None:
                sys.modules["pywry.widget"] = saved_widget
            else:
                # Reload from scratch
                importlib.import_module("pywry.widget")
