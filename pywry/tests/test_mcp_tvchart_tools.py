"""Unit tests for the 32 first-class TVChart MCP tools.

Each handler resolves a registered widget, emits a tvchart:* event with
a derived payload, and returns a uniform result dict.  These tests
verify the schema → handler → emit chain for every tool.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from pywry.mcp import handlers as mcp_handlers, state as mcp_state
from pywry.mcp.handlers import HandlerContext


def _make_ctx(args: dict[str, Any]) -> HandlerContext:
    return HandlerContext(
        args=args,
        events={},
        make_callback=lambda _wid: lambda *_a, **_kw: None,
        headless=False,
    )


def _find_emit(widget: MagicMock, event_name: str) -> tuple[str, dict[str, Any]] | None:
    """Return the (name, payload) of the first ``widget.emit(event_name, ...)`` call.

    Handlers that confirm mutations via state polling may emit helper
    events (``tvchart:request-state``) before or after the mutation
    event; tests that care about the mutation payload should locate
    it by name rather than by positional index.
    """
    for call in widget.emit.call_args_list:
        args = call[0]
        if args and args[0] == event_name:
            name = args[0]
            payload = args[1] if len(args) > 1 else {}
            return name, payload
    return None


@pytest.fixture
def widget(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """A fresh widget mock registered under ``"chart"`` for the duration of a test.

    Mutation handlers (``tvchart_symbol_search`` / ``_compare`` /
    ``_change_interval``) block on the real ``tvchart:data-settled``
    round-trip, which never fires against a mocked widget.  Patch
    ``_wait_for_data_settled`` to return ``None`` immediately so tests
    exercise the emit + result-shape contract without waiting on a
    real frontend.  Tests that want to assert the confirmed-success
    path should patch it themselves with a stand-in state.
    """
    mcp_state._widgets.clear()
    w = MagicMock()
    mcp_state._widgets["chart"] = w
    monkeypatch.setattr(
        mcp_handlers,
        "_wait_for_data_settled",
        lambda *_a, **_kw: None,
    )
    monkeypatch.setattr(
        mcp_handlers,
        "_fetch_tvchart_state",
        lambda *_a, **_kw: None,
    )
    yield w
    mcp_state._widgets.clear()


# ---------------------------------------------------------------------------
# Tool catalog / dispatch coverage
# ---------------------------------------------------------------------------


def test_every_tvchart_tool_has_a_handler() -> None:
    """No tvchart_* tool may ship without a dispatch entry."""
    from pywry.mcp.tools import get_tools

    schema_names = {t.name for t in get_tools() if t.name.startswith("tvchart_")}
    handler_names = {n for n in mcp_handlers._HANDLERS if n.startswith("tvchart_")}
    assert schema_names == handler_names
    assert len(schema_names) == 32  # guard against accidental drops


def test_every_tvchart_tool_requires_widget_id() -> None:
    """Every tvchart_* tool must take widget_id."""
    from pywry.mcp.tools import get_tools

    for tool in get_tools():
        if not tool.name.startswith("tvchart_"):
            continue
        required = tool.inputSchema.get("required", [])
        assert "widget_id" in required, f"{tool.name} missing widget_id"


def test_unknown_widget_returns_error(widget: MagicMock) -> None:
    """Resolving an unregistered widget yields a clear error listing
    the registered widgets so the caller can recover."""
    ctx = _make_ctx({"widget_id": "ghost"})
    result = mcp_handlers._handle_tvchart_undo(ctx)
    assert "error" in result
    assert "ghost" in result["error"]
    assert "chart" in result["error"]  # the registered widget id
    widget.emit.assert_not_called()


def test_missing_widget_id_with_single_widget_auto_resolves(widget: MagicMock) -> None:
    """When exactly one widget is registered, missing ``widget_id`` is
    a no-op — the framework resolves it from the registry, the agent
    doesn't need to repeat what the server already knows."""
    ctx = _make_ctx({})  # no widget_id at all
    result = mcp_handlers._handle_tvchart_undo(ctx)
    assert "error" not in result
    assert result["widget_id"] == "chart"
    widget.emit.assert_called_once()


def test_missing_widget_id_with_multiple_widgets_returns_error() -> None:
    """When multiple widgets are registered, the call is genuinely
    ambiguous and the handler returns a clear error listing the
    candidates so the agent can self-correct."""
    mcp_state._widgets.clear()
    mcp_state._widgets["chart_a"] = MagicMock()
    mcp_state._widgets["chart_b"] = MagicMock()
    try:
        ctx = _make_ctx({})  # no widget_id, ambiguous
        result = mcp_handlers._handle_tvchart_undo(ctx)
        assert "error" in result
        assert "widget_id" in result["error"].lower()
        assert "chart_a" in result["error"]
        assert "chart_b" in result["error"]
    finally:
        mcp_state._widgets.clear()


def test_missing_widget_id_with_no_widgets_returns_error() -> None:
    """With nothing registered, the handler tells the caller that no
    widgets exist instead of dumping a stack trace."""
    mcp_state._widgets.clear()
    ctx = _make_ctx({})
    result = mcp_handlers._handle_tvchart_undo(ctx)
    assert "error" in result
    assert "widget_id" in result["error"].lower()
    assert "no widgets" in result["error"].lower()


def test_send_event_missing_widget_id_with_single_widget_auto_resolves(widget: MagicMock) -> None:
    """The generic send_event tool also benefits from auto-resolution."""
    ctx = _make_ctx({"event_type": "tvchart:symbol-search", "data": {"query": "MSFT"}})
    result = mcp_handlers._handle_send_event(ctx)
    assert "error" not in result
    widget.emit.assert_called_once()


def test_send_event_missing_event_type_returns_error(widget: MagicMock) -> None:
    ctx = _make_ctx({"widget_id": "chart"})  # no event_type
    result = mcp_handlers._handle_send_event(ctx)
    assert "error" in result
    assert "event_type" in result["error"].lower()
    widget.emit.assert_not_called()


# ---------------------------------------------------------------------------
# Data & series
# ---------------------------------------------------------------------------


def test_update_series_emits_tvchart_update(widget: MagicMock) -> None:
    bars = [{"time": 1, "open": 1, "high": 2, "low": 0.5, "close": 1.5}]
    ctx = _make_ctx({"widget_id": "chart", "bars": bars, "series_id": "main"})
    out = mcp_handlers._handle_tvchart_update_series(ctx)
    assert out["event_type"] == "tvchart:update"
    widget.emit.assert_called_once()
    event_name, payload = widget.emit.call_args[0]
    assert event_name == "tvchart:update"
    assert payload["bars"] == bars
    assert payload["seriesId"] == "main"
    assert payload["fitContent"] is True


def test_update_series_passes_chart_id_when_set(widget: MagicMock) -> None:
    ctx = _make_ctx(
        {
            "widget_id": "chart",
            "bars": [],
            "chart_id": "alt-chart",
            "fit_content": False,
        }
    )
    mcp_handlers._handle_tvchart_update_series(ctx)
    payload = widget.emit.call_args[0][1]
    assert payload["chartId"] == "alt-chart"
    assert payload["fitContent"] is False


def test_update_bar_emits_tvchart_stream(widget: MagicMock) -> None:
    bar = {"time": 1, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 100}
    mcp_handlers._handle_tvchart_update_bar(_make_ctx({"widget_id": "chart", "bar": bar}))
    name, payload = widget.emit.call_args[0]
    assert name == "tvchart:stream"
    assert payload["bar"] == bar


def test_add_series_emits_tvchart_add_series(widget: MagicMock) -> None:
    bars = [{"time": 1, "value": 10}, {"time": 2, "value": 11}]
    ctx = _make_ctx(
        {
            "widget_id": "chart",
            "series_id": "overlay-1",
            "bars": bars,
            "series_type": "Line",
            "series_options": {"color": "#f00"},
        }
    )
    out = mcp_handlers._handle_tvchart_add_series(ctx)
    assert out["series_id"] == "overlay-1"
    name, payload = widget.emit.call_args[0]
    assert name == "tvchart:add-series"
    assert payload == {
        "seriesId": "overlay-1",
        "bars": bars,
        "seriesType": "Line",
        "seriesOptions": {"color": "#f00"},
    }


def test_remove_series_emits_tvchart_remove_series(widget: MagicMock) -> None:
    out = mcp_handlers._handle_tvchart_remove_series(
        _make_ctx({"widget_id": "chart", "series_id": "overlay-1"})
    )
    assert out["series_id"] == "overlay-1"
    name, payload = widget.emit.call_args[0]
    assert name == "tvchart:remove-series"
    assert payload == {"seriesId": "overlay-1"}


def test_add_markers_emits_tvchart_add_markers(widget: MagicMock) -> None:
    markers = [
        {"time": 1, "position": "aboveBar", "color": "#f00", "shape": "arrowDown", "text": "sell"}
    ]
    mcp_handlers._handle_tvchart_add_markers(
        _make_ctx({"widget_id": "chart", "markers": markers, "series_id": "main"})
    )
    name, payload = widget.emit.call_args[0]
    assert name == "tvchart:add-markers"
    assert payload["markers"] == markers
    assert payload["seriesId"] == "main"


def test_add_price_line_uses_defaults(widget: MagicMock) -> None:
    mcp_handlers._handle_tvchart_add_price_line(_make_ctx({"widget_id": "chart", "price": 170.5}))
    name, payload = widget.emit.call_args[0]
    assert name == "tvchart:add-price-line"
    assert payload["price"] == 170.5
    assert payload["color"] == "#2196F3"
    assert payload["lineWidth"] == 1
    assert payload["title"] == ""


def test_apply_options_strips_none_keys(widget: MagicMock) -> None:
    chart_options = {"timeScale": {"secondsVisible": False}}
    mcp_handlers._handle_tvchart_apply_options(
        _make_ctx({"widget_id": "chart", "chart_options": chart_options})
    )
    name, payload = widget.emit.call_args[0]
    assert name == "tvchart:apply-options"
    assert payload == {"chartOptions": chart_options}


# ---------------------------------------------------------------------------
# Built-in indicators
# ---------------------------------------------------------------------------


def test_add_indicator_passes_all_options(widget: MagicMock) -> None:
    ctx = _make_ctx(
        {
            "widget_id": "chart",
            "name": "Bollinger Bands",
            "period": 20,
            "color": "#ff0",
            "source": "close",
            "method": "SMA",
            "multiplier": 2.0,
            "ma_type": "SMA",
            "offset": 0,
        }
    )
    mcp_handlers._handle_tvchart_add_indicator(ctx)
    name, payload = widget.emit.call_args[0]
    assert name == "tvchart:add-indicator"
    assert payload == {
        "name": "Bollinger Bands",
        "period": 20,
        "color": "#ff0",
        "source": "close",
        "method": "SMA",
        "multiplier": 2.0,
        "maType": "SMA",
        "offset": 0,
    }


def test_add_indicator_omits_unset_optionals(widget: MagicMock) -> None:
    mcp_handlers._handle_tvchart_add_indicator(_make_ctx({"widget_id": "chart", "name": "RSI"}))
    payload = widget.emit.call_args[0][1]
    assert payload == {"name": "RSI"}


def test_remove_indicator_emits_remove(widget: MagicMock) -> None:
    out = mcp_handlers._handle_tvchart_remove_indicator(
        _make_ctx({"widget_id": "chart", "series_id": "ind_sma_99"})
    )
    assert out["series_id"] == "ind_sma_99"
    payload = widget.emit.call_args[0][1]
    assert payload == {"seriesId": "ind_sma_99"}


def test_show_indicators_takes_no_payload(widget: MagicMock) -> None:
    mcp_handlers._handle_tvchart_show_indicators(_make_ctx({"widget_id": "chart"}))
    name, payload = widget.emit.call_args[0]
    assert name == "tvchart:show-indicators"
    assert payload == {}


def test_list_indicators_round_trip_returns_inventory(widget: MagicMock) -> None:
    """list_indicators emits a request and waits for the response event."""
    captured_listener: dict[str, Any] = {}

    def fake_on(event: str, handler: Any) -> None:
        captured_listener["event"] = event
        captured_listener["handler"] = handler

    fake_payload = {
        "context": None,
        "indicators": [
            {
                "seriesId": "ind_sma_1",
                "name": "SMA",
                "type": "sma",
                "period": 50,
                "color": "#2196F3",
            }
        ],
    }

    def fake_emit(event: str, payload: dict[str, Any]) -> None:
        # Simulate the JS frontend echoing the correlation token back
        token = payload.get("context")
        fake_payload["context"] = token
        captured_listener["handler"](fake_payload, "", "")

    widget.on = fake_on
    widget.emit = fake_emit

    out = mcp_handlers._handle_tvchart_list_indicators(
        _make_ctx({"widget_id": "chart", "timeout": 1.0})
    )
    assert captured_listener["event"] == "tvchart:list-indicators-response"
    assert out["indicators"][0]["name"] == "SMA"


def test_list_indicators_returns_error_on_timeout(widget: MagicMock) -> None:
    widget.on = MagicMock()
    widget.emit = MagicMock()  # never echoes back
    out = mcp_handlers._handle_tvchart_list_indicators(
        _make_ctx({"widget_id": "chart", "timeout": 0.05})
    )
    assert "error" in out


# ---------------------------------------------------------------------------
# Symbol / interval / view
# ---------------------------------------------------------------------------


def test_symbol_search_with_query_and_auto_select(widget: MagicMock) -> None:
    mcp_handlers._handle_tvchart_symbol_search(
        _make_ctx({"widget_id": "chart", "query": "MSFT", "auto_select": True})
    )
    hit = _find_emit(widget, "tvchart:symbol-search")
    assert hit is not None, "mutation event was never emitted"
    _, payload = hit
    assert payload == {"query": "MSFT", "autoSelect": True}


def test_symbol_search_default_no_query(widget: MagicMock) -> None:
    mcp_handlers._handle_tvchart_symbol_search(_make_ctx({"widget_id": "chart"}))
    hit = _find_emit(widget, "tvchart:symbol-search")
    assert hit is not None, "mutation event was never emitted"
    _, payload = hit
    # auto_select defaults to True even without query
    assert payload == {"autoSelect": True}
    # No query → no mutation to confirm → no polling → only the mutation emit.
    assert widget.emit.call_count == 1


def test_compare_without_query_just_opens_dialog(widget: MagicMock) -> None:
    """No query → no mutation to confirm, single emit, empty payload."""
    mcp_handlers._handle_tvchart_compare(_make_ctx({"widget_id": "chart"}))
    hit = _find_emit(widget, "tvchart:compare")
    assert hit is not None, "compare event was never emitted"
    _, payload = hit
    assert payload == {}
    # No query → no pre-state snapshot, no polling → only the mutation emit.
    assert widget.emit.call_count == 1


def test_compare_with_query_emits_query_and_auto_add(widget: MagicMock) -> None:
    """With a query, the handler emits it so the frontend auto-adds the match."""
    mcp_handlers._handle_tvchart_compare(
        _make_ctx({"widget_id": "chart", "query": "GOOGL", "auto_add": True})
    )
    hit = _find_emit(widget, "tvchart:compare")
    assert hit is not None
    _, payload = hit
    assert payload == {"query": "GOOGL", "autoAdd": True}


def test_compare_passes_symbol_type_and_exchange_filters(widget: MagicMock) -> None:
    """``symbol_type`` / ``exchange`` narrow the datafeed search so SPY
    resolves to the ETF instead of a near-prefix like SPYM."""
    mcp_handlers._handle_tvchart_compare(
        _make_ctx(
            {
                "widget_id": "chart",
                "query": "SPY",
                "symbol_type": "etf",
                "exchange": "NYSEARCA",
            }
        )
    )
    hit = _find_emit(widget, "tvchart:compare")
    assert hit is not None
    _, payload = hit
    assert payload == {
        "query": "SPY",
        "autoAdd": True,
        "symbolType": "etf",
        "exchange": "NYSEARCA",
    }


def test_symbol_search_passes_symbol_type_and_exchange_filters(widget: MagicMock) -> None:
    """Same filter plumbing on ``tvchart_symbol_search`` for main-ticker changes."""
    mcp_handlers._handle_tvchart_symbol_search(
        _make_ctx(
            {
                "widget_id": "chart",
                "query": "SPY",
                "auto_select": True,
                "symbol_type": "etf",
                "exchange": "NYSEARCA",
            }
        )
    )
    hit = _find_emit(widget, "tvchart:symbol-search")
    assert hit is not None
    _, payload = hit
    assert payload == {
        "query": "SPY",
        "autoSelect": True,
        "symbolType": "etf",
        "exchange": "NYSEARCA",
    }


def test_change_interval_passes_value(widget: MagicMock) -> None:
    mcp_handlers._handle_tvchart_change_interval(_make_ctx({"widget_id": "chart", "value": "5m"}))
    hit = _find_emit(widget, "tvchart:interval-change")
    assert hit is not None
    _, payload = hit
    assert payload == {"value": "5m"}


def test_set_visible_range_packs_from_to(widget: MagicMock) -> None:
    mcp_handlers._handle_tvchart_set_visible_range(
        _make_ctx({"widget_id": "chart", "from_time": 100, "to_time": 200})
    )
    name, payload = widget.emit.call_args[0]
    assert name == "tvchart:time-scale"
    assert payload == {"visibleRange": {"from": 100, "to": 200}}


def test_fit_content_emits_fit_flag(widget: MagicMock) -> None:
    mcp_handlers._handle_tvchart_fit_content(_make_ctx({"widget_id": "chart"}))
    payload = widget.emit.call_args[0][1]
    assert payload == {"fitContent": True}


def test_time_range_passes_preset_value(widget: MagicMock) -> None:
    mcp_handlers._handle_tvchart_time_range(_make_ctx({"widget_id": "chart", "value": "1Y"}))
    name, payload = widget.emit.call_args[0]
    assert name == "tvchart:time-range"
    assert payload == {"value": "1Y"}


def test_time_range_picker_emits_open_event(widget: MagicMock) -> None:
    mcp_handlers._handle_tvchart_time_range_picker(_make_ctx({"widget_id": "chart"}))
    name, payload = widget.emit.call_args[0]
    assert name == "tvchart:time-range-picker"
    assert payload == {}


def test_log_scale_coerces_value_to_bool(widget: MagicMock) -> None:
    mcp_handlers._handle_tvchart_log_scale(_make_ctx({"widget_id": "chart", "value": 1}))
    payload = widget.emit.call_args[0][1]
    assert payload == {"value": True}


def test_auto_scale_emits_event(widget: MagicMock) -> None:
    mcp_handlers._handle_tvchart_auto_scale(_make_ctx({"widget_id": "chart", "value": False}))
    name, payload = widget.emit.call_args[0]
    assert name == "tvchart:auto-scale"
    assert payload == {"value": False}


# ---------------------------------------------------------------------------
# Chart type
# ---------------------------------------------------------------------------


def test_chart_type_emits_change(widget: MagicMock) -> None:
    mcp_handlers._handle_tvchart_chart_type(
        _make_ctx({"widget_id": "chart", "value": "Heikin Ashi", "series_id": "main"})
    )
    name, payload = widget.emit.call_args[0]
    assert name == "tvchart:chart-type-change"
    assert payload == {"value": "Heikin Ashi", "seriesId": "main"}


# ---------------------------------------------------------------------------
# Drawing tools / undo / redo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mode", "expected_event"),
    [
        ("cursor", "tvchart:tool-cursor"),
        ("crosshair", "tvchart:tool-crosshair"),
        ("magnet", "tvchart:tool-magnet"),
        ("eraser", "tvchart:tool-eraser"),
        ("visibility", "tvchart:tool-visibility"),
        ("lock", "tvchart:tool-lock"),
    ],
)
def test_drawing_tool_dispatch(widget: MagicMock, mode: str, expected_event: str) -> None:
    mcp_handlers._handle_tvchart_drawing_tool(_make_ctx({"widget_id": "chart", "mode": mode}))
    assert widget.emit.call_args[0][0] == expected_event


def test_drawing_tool_unknown_mode_returns_error(widget: MagicMock) -> None:
    out = mcp_handlers._handle_tvchart_drawing_tool(
        _make_ctx({"widget_id": "chart", "mode": "ruler"})
    )
    assert "error" in out
    widget.emit.assert_not_called()


def test_undo_emits_event(widget: MagicMock) -> None:
    mcp_handlers._handle_tvchart_undo(_make_ctx({"widget_id": "chart"}))
    assert widget.emit.call_args[0][0] == "tvchart:undo"


def test_redo_emits_event(widget: MagicMock) -> None:
    mcp_handlers._handle_tvchart_redo(_make_ctx({"widget_id": "chart"}))
    assert widget.emit.call_args[0][0] == "tvchart:redo"


# ---------------------------------------------------------------------------
# Chart chrome
# ---------------------------------------------------------------------------


def test_show_settings_emits_event(widget: MagicMock) -> None:
    mcp_handlers._handle_tvchart_show_settings(_make_ctx({"widget_id": "chart"}))
    assert widget.emit.call_args[0][0] == "tvchart:show-settings"


def test_toggle_dark_mode_emits_value(widget: MagicMock) -> None:
    mcp_handlers._handle_tvchart_toggle_dark_mode(_make_ctx({"widget_id": "chart", "value": True}))
    name, payload = widget.emit.call_args[0]
    assert name == "tvchart:toggle-dark-mode"
    assert payload == {"value": True}


def test_screenshot_emits_event(widget: MagicMock) -> None:
    mcp_handlers._handle_tvchart_screenshot(_make_ctx({"widget_id": "chart"}))
    assert widget.emit.call_args[0][0] == "tvchart:screenshot"


def test_fullscreen_emits_event(widget: MagicMock) -> None:
    mcp_handlers._handle_tvchart_fullscreen(_make_ctx({"widget_id": "chart"}))
    assert widget.emit.call_args[0][0] == "tvchart:fullscreen"


# ---------------------------------------------------------------------------
# Layout / state
# ---------------------------------------------------------------------------


def test_save_layout_passes_optional_name(widget: MagicMock) -> None:
    mcp_handlers._handle_tvchart_save_layout(
        _make_ctx({"widget_id": "chart", "name": "Daily Setup"})
    )
    name, payload = widget.emit.call_args[0]
    assert name == "tvchart:save-layout"
    assert payload == {"name": "Daily Setup"}


def test_save_layout_omits_name_when_none(widget: MagicMock) -> None:
    mcp_handlers._handle_tvchart_save_layout(_make_ctx({"widget_id": "chart"}))
    payload = widget.emit.call_args[0][1]
    assert payload == {}


def test_open_layout_emits_event(widget: MagicMock) -> None:
    mcp_handlers._handle_tvchart_open_layout(_make_ctx({"widget_id": "chart"}))
    assert widget.emit.call_args[0][0] == "tvchart:open-layout"


def test_save_state_emits_event(widget: MagicMock) -> None:
    out = mcp_handlers._handle_tvchart_save_state(_make_ctx({"widget_id": "chart"}))
    assert out["event_sent"] is True
    assert widget.emit.call_args[0][0] == "tvchart:save-state"


def test_request_state_round_trip_returns_decoded_state(widget: MagicMock) -> None:
    captured: dict[str, Any] = {}

    def fake_on(event: str, handler: Any) -> None:
        captured["event"] = event
        captured["handler"] = handler

    response = {
        "context": None,
        "chartId": "main",
        "theme": "dark",
        "series": {"main": {"type": "Candles"}},
        "visibleRange": {"from": 1, "to": 2},
        "rawData": [],
        "drawings": [],
        "indicators": [],
    }

    def fake_emit(event: str, payload: dict[str, Any]) -> None:
        response["context"] = payload.get("context")
        captured["handler"](response, "", "")

    widget.on = fake_on
    widget.emit = fake_emit

    out = mcp_handlers._handle_tvchart_request_state(
        _make_ctx({"widget_id": "chart", "timeout": 1.0})
    )
    assert captured["event"] == "tvchart:state-response"
    state = out["state"]
    assert "context" not in state  # token stripped
    assert state["theme"] == "dark"
    assert state["series"]["main"]["type"] == "Candles"


def test_request_state_returns_error_on_timeout(widget: MagicMock) -> None:
    widget.on = MagicMock()
    widget.emit = MagicMock()
    out = mcp_handlers._handle_tvchart_request_state(
        _make_ctx({"widget_id": "chart", "timeout": 0.05})
    )
    assert "error" in out
