"""TradingView chart state mixin.

Provides the ``TVChartStateMixin`` class that gives any host widget
(PyWry, PyWryWidget, InlineWidget) a full set of methods for driving
a TradingView Lightweight Charts instance.
"""

from __future__ import annotations

import logging

from typing import TYPE_CHECKING, Any

from ..state_mixins import EmittingWidget


if TYPE_CHECKING:
    from .datafeed import DatafeedProvider

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# Module-level helpers for chart storage event handling
# ──────────────────────────────────────────────────────────


def _chart_store_save_layout(
    store: Any,
    run_async: Any,
    user_id: str,
    layout_id: str,
    value: str,
    *,
    js_index: list[dict[str, Any]] | None = None,
) -> None:
    """Persist a single layout, looking up metadata from the JS or store index."""
    name = layout_id
    summary = ""

    # Prefer the cached JS index (always up-to-date since JS writes the index
    # before the layout data).
    resolved = False
    if js_index:
        for entry in js_index:
            if isinstance(entry, dict) and entry.get("id") == layout_id:
                name = entry.get("name", layout_id)
                summary = entry.get("summary", "")
                resolved = True
                break
    if not resolved:
        try:
            idx = run_async(store.list_layouts(user_id), timeout=5.0)
            for entry in idx:
                if entry.get("id") == layout_id:
                    name = entry.get("name", layout_id)
                    summary = entry.get("summary", "")
                    break
        except Exception:
            logger.debug("Failed to look up layout metadata for %s", layout_id, exc_info=True)
    run_async(
        store.save_layout(user_id, layout_id, name, value, summary=summary),
        timeout=10.0,
    )


def _chart_store_sync_index(
    store: Any,
    run_async: Any,
    user_id: str,
    value: str,
) -> None:
    """Reconcile the store against a full JS index update.

    Removes stale layouts and updates metadata (name, summary)
    for all entries so the Python-side index stays in sync with JS.
    """
    import json

    try:
        entries = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return
    if not isinstance(entries, list):
        return
    existing = run_async(store.list_layouts(user_id), timeout=5.0)
    existing_ids = {e.get("id") for e in existing}
    existing_map = {e.get("id"): e for e in existing}
    new_ids = {e.get("id") for e in entries if isinstance(e, dict) and e.get("id")}
    for removed_id in existing_ids - new_ids:
        run_async(store.delete_layout(user_id, removed_id), timeout=5.0)

    # Sync metadata for entries whose name/summary changed
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        eid = entry.get("id")
        if not eid:
            continue
        old = existing_map.get(eid, {})
        if old.get("name") != entry.get("name") or old.get("summary") != entry.get("summary", ""):
            run_async(
                store.update_layout_meta(
                    user_id,
                    eid,
                    name=entry.get("name", eid),
                    summary=entry.get("summary", ""),
                ),
                timeout=5.0,
            )


class TVChartStateMixin(EmittingWidget):  # pylint: disable=abstract-method
    """Mixin for TradingView Lightweight Charts state management."""

    def update_series(
        self,
        data: Any,
        chart_id: str | None = None,
        series_id: str | None = None,
        fit_content: bool = True,
    ) -> None:
        """Replace all bar data for a series.

        Parameters
        ----------
        data : list[dict] | DataFrame
            OHLCV bar data. If a DataFrame, it will be normalized via
            normalize_ohlcv().
        chart_id : str, optional
            Target chart instance ID.
        series_id : str, optional
            Series to update (defaults to 'main').
        fit_content : bool
            Whether to auto-fit the time scale after update.
        """
        bars, volume = self._normalize_tvchart_data(data)
        payload: dict[str, Any] = {"bars": bars, "fitContent": fit_content}
        if volume:
            payload["volume"] = volume
        if chart_id:
            payload["chartId"] = chart_id
        if series_id:
            payload["seriesId"] = series_id
        self.emit("tvchart:update", payload)

    def update_bar(
        self,
        bar: dict[str, Any],  # pylint: disable=disallowed-name
        chart_id: str | None = None,
        series_id: str | None = None,
    ) -> None:
        """Stream a single bar update (real-time tick).

        Parameters
        ----------
        bar : dict
            Single bar with time, open, high, low, close keys.
        chart_id : str, optional
            Target chart instance ID.
        series_id : str, optional
            Series to update (defaults to 'main').
        """
        payload: dict[str, Any] = {"bar": bar}
        if chart_id:
            payload["chartId"] = chart_id
        if series_id:
            payload["seriesId"] = series_id
        # Build volume entry if volume is present in the bar
        if "volume" in bar:
            vol_entry: dict[str, Any] = {"time": bar["time"], "value": bar["volume"]}
            if bar.get("close", 0) >= bar.get("open", 0):
                vol_entry["color"] = "rgba(38, 166, 154, 0.3)"
            else:
                vol_entry["color"] = "rgba(239, 83, 80, 0.3)"
            payload["volume"] = vol_entry
        self.emit("tvchart:stream", payload)

    def add_indicator(
        self,
        indicator_data: list[dict[str, Any]],
        series_id: str = "indicator",
        series_type: str = "Line",
        series_options: dict[str, Any] | None = None,
        chart_id: str | None = None,
    ) -> None:
        """Add an indicator overlay series to the chart.

        Parameters
        ----------
        indicator_data : list[dict]
            List of {time, value} dicts for the indicator line.
        series_id : str
            Unique identifier for this indicator series.
        series_type : str
            Series type: 'Line', 'Histogram', 'Area', etc.
        series_options : dict, optional
            Options for the series (color, lineWidth, etc.).
        chart_id : str, optional
            Target chart instance ID.
        """
        payload: dict[str, Any] = {
            "seriesId": series_id,
            "bars": indicator_data,
            "seriesType": series_type,
            "seriesOptions": series_options or {},
        }
        if chart_id:
            payload["chartId"] = chart_id
        self.emit("tvchart:add-series", payload)

    def remove_indicator(
        self,
        series_id: str,
        chart_id: str | None = None,
    ) -> None:
        """Remove an indicator series from the chart.

        Parameters
        ----------
        series_id : str
            The series to remove.
        chart_id : str, optional
            Target chart instance ID.
        """
        payload: dict[str, Any] = {"seriesId": series_id}
        if chart_id:
            payload["chartId"] = chart_id
        self.emit("tvchart:remove-series", payload)

    def add_builtin_indicator(
        self,
        name: str,
        period: int | None = None,
        *,
        color: str | None = None,
        source: str | None = None,
        method: str | None = None,
        multiplier: float | None = None,
        ma_type: str | None = None,
        offset: int | None = None,
        chart_id: str | None = None,
    ) -> None:
        """Add a built-in indicator computed on the JS frontend.

        Uses the full indicator engine: legend integration, undo/redo,
        subplot panes, and Bollinger Bands band-fill rendering.

        Available indicators (by name):
            SMA, EMA, WMA, SMA (50), SMA (200), EMA (12), EMA (26),
            RSI, ATR, VWAP, Volume SMA, Bollinger Bands

        Parameters
        ----------
        name : str
            Indicator name from the catalog (e.g. ``"SMA"``, ``"RSI"``).
        period : int, optional
            Lookback period.  Falls back to the catalog default.
        color : str, optional
            Hex colour.  Auto-assigned from the palette when omitted.
        source : str, optional
            OHLC source: ``"close"``, ``"open"``, ``"high"``, ``"low"``,
            ``"hl2"``, ``"hlc3"``, ``"ohlc4"``.
        method : str, optional
            Moving average method for the Moving Average indicator:
            ``"SMA"``, ``"EMA"``, ``"WMA"``.
        multiplier : float, optional
            Bollinger Bands standard-deviation multiplier (default 2).
        ma_type : str, optional
            Bollinger Bands moving-average type (default ``"SMA"``).
        offset : int, optional
            Bar offset for indicator shifting.
        chart_id : str, optional
            Target chart instance ID.
        """
        payload: dict[str, Any] = {"name": name}
        if period is not None:
            payload["period"] = period
        if color is not None:
            payload["color"] = color
        if source is not None:
            payload["source"] = source
        if method is not None:
            payload["method"] = method
        if multiplier is not None:
            payload["multiplier"] = multiplier
        if ma_type is not None:
            payload["maType"] = ma_type
        if offset is not None:
            payload["offset"] = offset
        if chart_id is not None:
            payload["chartId"] = chart_id
        self.emit("tvchart:add-indicator", payload)

    def remove_builtin_indicator(
        self,
        series_id: str,
        chart_id: str | None = None,
    ) -> None:
        """Remove a built-in indicator by its series ID.

        Handles grouped indicators (e.g. Bollinger Bands upper/mid/lower
        are removed together), subplot pane cleanup, and undo/redo.

        Parameters
        ----------
        series_id : str
            The indicator series ID (e.g. ``"ind_sma_1713200000"``).
        chart_id : str, optional
            Target chart instance ID.
        """
        payload: dict[str, Any] = {"seriesId": series_id}
        if chart_id is not None:
            payload["chartId"] = chart_id
        self.emit("tvchart:remove-indicator", payload)

    def list_indicators(
        self,
        chart_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Request the list of active built-in indicators.

        The frontend replies with a ``tvchart:list-indicators-response``
        event containing an ``indicators`` array.

        Parameters
        ----------
        chart_id : str, optional
            Target chart instance ID.
        context : dict, optional
            Opaque context echoed back in the response.
        """
        payload: dict[str, Any] = {}
        if chart_id is not None:
            payload["chartId"] = chart_id
        if context is not None:
            payload["context"] = context
        self.emit("tvchart:list-indicators", payload)

    def add_marker(
        self,
        markers: list[dict[str, Any]],
        series_id: str | None = None,
        chart_id: str | None = None,
    ) -> None:
        """Add markers (buy/sell signals) to a series.

        Parameters
        ----------
        markers : list[dict]
            List of marker dicts with time, position ('aboveBar'/'belowBar'),
            color, shape ('arrowUp'/'arrowDown'/'circle'), and text keys.
        series_id : str, optional
            Target series (defaults to 'main').
        chart_id : str, optional
            Target chart instance ID.
        """
        payload: dict[str, Any] = {"markers": markers}
        if series_id:
            payload["seriesId"] = series_id
        if chart_id:
            payload["chartId"] = chart_id
        self.emit("tvchart:add-markers", payload)

    def add_price_line(
        self,
        price: float,
        color: str = "#2196F3",
        line_width: int = 1,
        title: str = "",
        series_id: str | None = None,
        chart_id: str | None = None,
    ) -> None:
        """Add a horizontal price line to a series.

        Parameters
        ----------
        price : float
            Price level for the line.
        color : str
            Line color.
        line_width : int
            Line width in pixels.
        title : str
            Label text for the price line.
        series_id : str, optional
            Target series (defaults to 'main').
        chart_id : str, optional
            Target chart instance ID.
        """
        payload: dict[str, Any] = {
            "price": price,
            "color": color,
            "lineWidth": line_width,
            "title": title,
        }
        if series_id:
            payload["seriesId"] = series_id
        if chart_id:
            payload["chartId"] = chart_id
        self.emit("tvchart:add-price-line", payload)

    def set_visible_range(
        self,
        from_time: int,
        to_time: int,
        chart_id: str | None = None,
    ) -> None:
        """Set the visible time range on the chart.

        Parameters
        ----------
        from_time : int
            Start time as Unix epoch seconds.
        to_time : int
            End time as Unix epoch seconds.
        chart_id : str, optional
            Target chart instance ID.
        """
        payload: dict[str, Any] = {"visibleRange": {"from": from_time, "to": to_time}}
        if chart_id:
            payload["chartId"] = chart_id
        self.emit("tvchart:time-scale", payload)

    def fit_content(self, chart_id: str | None = None) -> None:
        """Auto-fit the chart to show all data.

        Parameters
        ----------
        chart_id : str, optional
            Target chart instance ID.
        """
        payload: dict[str, Any] = {"fitContent": True}
        if chart_id:
            payload["chartId"] = chart_id
        self.emit("tvchart:time-scale", payload)

    def apply_chart_options(
        self,
        chart_options: dict[str, Any] | None = None,
        series_options: dict[str, Any] | None = None,
        series_id: str | None = None,
        chart_id: str | None = None,
    ) -> None:
        """Apply options to the chart or a specific series.

        Parameters
        ----------
        chart_options : dict, optional
            Chart-level options (layout, grid, crosshair, etc.).
        series_options : dict, optional
            Series-level options (colors, line width, etc.).
        series_id : str, optional
            Target series for series_options.
        chart_id : str, optional
            Target chart instance ID.
        """
        payload: dict[str, Any] = {}
        if chart_options:
            payload["chartOptions"] = chart_options
        if series_options:
            payload["seriesOptions"] = series_options
        if series_id:
            payload["seriesId"] = series_id
        if chart_id:
            payload["chartId"] = chart_id
        self.emit("tvchart:apply-options", payload)

    def request_tvchart_state(
        self,
        chart_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Request the current chart state (viewport, series info).

        The frontend responds with a 'tvchart:state-response' event.

        Parameters
        ----------
        chart_id : str, optional
            Target chart instance ID.
        context : dict, optional
            Context data to echo back in the response. Useful for
            correlating state requests during reloads or view/context
            switches managed by the application shell.
        """
        payload: dict[str, Any] = {}
        if chart_id:
            payload["chartId"] = chart_id
        if context:
            payload["context"] = context
        self.emit("tvchart:request-state", payload)

    # ──────────────────────────────────────────────────────────
    # TradingView Datafeed API — complete event protocol
    # ──────────────────────────────────────────────────────────

    # -- onReady / DatafeedConfiguration --

    def respond_tvchart_datafeed_config(
        self,
        request_id: str,
        config: dict[str, Any] | None = None,
        chart_id: str | None = None,
        error: str | None = None,
    ) -> None:
        """Respond with datafeed configuration (onReady).

        Parameters
        ----------
        request_id : str
            Correlation ID from the incoming ``tvchart:datafeed-config-request``.
        config : dict, optional
            Datafeed configuration dict (supported_resolutions, exchanges, etc.).
        chart_id : str, optional
            Target chart instance ID.
        error : str, optional
            Error message; the frontend will reject the onReady promise.
        """
        payload: dict[str, Any] = {
            "requestId": request_id,
            "config": config or {},
        }
        if chart_id:
            payload["chartId"] = chart_id
        if error:
            payload["error"] = error
        self.emit("tvchart:datafeed-config-response", payload)

    # -- searchSymbols --

    def request_tvchart_symbol_search(
        self,
        query: str,
        request_id: str,
        chart_id: str | None = None,
        exchange: str = "",
        symbol_type: str = "",
        limit: int = 20,
    ) -> None:
        """Request dynamic symbol search results from the host.

        Parameters
        ----------
        query : str
            User-typed search string.
        request_id : str
            Correlation ID for the response.
        chart_id : str, optional
            Target chart instance ID.
        exchange : str
            Exchange filter (empty string for all).
        symbol_type : str
            Symbol type filter (empty string for all).
        limit : int
            Maximum number of results to return.
        """
        payload: dict[str, Any] = {
            "query": query,
            "requestId": request_id,
            "limit": limit,
            "exchange": exchange,
            "symbolType": symbol_type,
        }
        if chart_id:
            payload["chartId"] = chart_id
        self.emit("tvchart:datafeed-search-request", payload)

    def respond_tvchart_symbol_search(
        self,
        request_id: str,
        items: list[dict[str, Any]],
        chart_id: str | None = None,
        query: str | None = None,
        error: str | None = None,
    ) -> None:
        """Respond with symbol search results for a datafeed request.

        Parameters
        ----------
        request_id : str
            Correlation ID from the incoming search request.
        items : list of dict
            Search result items, each with ``symbol``, ``full_name``,
            ``description``, ``exchange``, ``type`` keys.
        chart_id : str, optional
            Target chart instance ID.
        query : str, optional
            Echo the original query for client-side dedup.
        error : str, optional
            Error message; rejects the search promise.
        """
        payload: dict[str, Any] = {
            "requestId": request_id,
            "items": items,
        }
        if chart_id:
            payload["chartId"] = chart_id
        if query is not None:
            payload["query"] = query
        if error:
            payload["error"] = error
        self.emit("tvchart:datafeed-search-response", payload)

    # -- resolveSymbol --

    def request_tvchart_symbol_resolve(
        self,
        symbol: str,
        request_id: str,
        chart_id: str | None = None,
    ) -> None:
        """Request full metadata for a specific symbol from the host.

        Parameters
        ----------
        symbol : str
            Symbol name to resolve (e.g. ``"AAPL"``).
        request_id : str
            Correlation ID for the response.
        chart_id : str, optional
            Target chart instance ID.
        """
        payload: dict[str, Any] = {
            "symbol": symbol,
            "requestId": request_id,
        }
        if chart_id:
            payload["chartId"] = chart_id
        self.emit("tvchart:datafeed-resolve-request", payload)

    def respond_tvchart_symbol_resolve(
        self,
        request_id: str,
        symbol_info: dict[str, Any] | None,
        chart_id: str | None = None,
        error: str | None = None,
    ) -> None:
        """Respond with resolved symbol metadata for a datafeed request.

        Parameters
        ----------
        request_id : str
            Correlation ID from the incoming resolve request.
        symbol_info : dict or None
            Full symbol metadata matching ``TVChartSymbolInfo`` shape.
        chart_id : str, optional
            Target chart instance ID.
        error : str, optional
            Error message; rejects the resolve promise.
        """
        payload: dict[str, Any] = {
            "requestId": request_id,
            "symbolInfo": symbol_info,
        }
        if chart_id:
            payload["chartId"] = chart_id
        if error:
            payload["error"] = error
        self.emit("tvchart:datafeed-resolve-response", payload)

    # -- getBars / history --

    def request_tvchart_history(
        self,
        symbol: str,
        resolution: str,
        from_time: int,
        to_time: int,
        request_id: str,
        chart_id: str | None = None,
        count_back: int | None = None,
        first_data_request: bool = False,
    ) -> None:
        """Request historical bars using the datafeed contract.

        Parameters
        ----------
        symbol : str
            Symbol name (e.g. ``"AAPL"``).
        resolution : str
            Bar resolution string (``"1"``, ``"60"``, ``"1D"``, etc.).
        from_time : int
            Start of the requested range (UNIX seconds).
        to_time : int
            End of the requested range (UNIX seconds).
        request_id : str
            Correlation ID for the response.
        chart_id : str, optional
            Target chart instance ID.
        count_back : int, optional
            Preferred number of bars counting back from ``to_time``.
        first_data_request : bool
            ``True`` on the very first load for a symbol.
        """
        payload: dict[str, Any] = {
            "symbol": symbol,
            "resolution": resolution,
            "from": from_time,
            "to": to_time,
            "requestId": request_id,
            "firstDataRequest": first_data_request,
        }
        if count_back is not None:
            payload["countBack"] = count_back
        if chart_id:
            payload["chartId"] = chart_id
        self.emit("tvchart:datafeed-history-request", payload)

    def respond_tvchart_history(
        self,
        request_id: str,
        bars: list[dict[str, Any]],
        chart_id: str | None = None,
        status: str = "ok",
        no_data: bool | None = None,
        next_time: int | None = None,
        error: str | None = None,
    ) -> None:
        """Respond with historical bars for a datafeed history request.

        Parameters
        ----------
        request_id : str
            Correlation ID from the incoming history request.
        bars : list of dict
            OHLCV bar dicts with ``time``, ``open``, ``high``, ``low``,
            ``close`` keys (``volume`` optional).
        chart_id : str, optional
            Target chart instance ID.
        status : str
            ``"ok"`` on success, ``"error"`` on failure.
        no_data : bool, optional
            ``True`` when no more historical data is available.
        next_time : int, optional
            Earliest timestamp with data, used for scrollback hinting.
        error : str, optional
            Error message; rejects the history promise.
        """
        payload: dict[str, Any] = {
            "requestId": request_id,
            "bars": bars,
            "status": status,
        }
        if chart_id:
            payload["chartId"] = chart_id
        if no_data is not None:
            payload["noData"] = no_data
        if next_time is not None:
            payload["nextTime"] = next_time
        if error:
            payload["error"] = error
        self.emit("tvchart:datafeed-history-response", payload)

    # -- subscribeBars / unsubscribeBars --

    def respond_tvchart_bar_update(
        self,
        listener_guid: str,
        bar: dict[str, Any],  # pylint: disable=disallowed-name
        chart_id: str | None = None,
    ) -> None:
        """Push a real-time bar update to a subscribed listener.

        Parameters
        ----------
        listener_guid : str
            Subscription GUID from the ``tvchart:datafeed-subscribe`` event.
        bar : dict
            OHLCV bar dict with ``time``, ``open``, ``high``, ``low``,
            ``close`` keys (``volume`` optional).
        chart_id : str, optional
            Target chart instance ID.
        """
        payload: dict[str, Any] = {
            "listenerGuid": listener_guid,
            "bar": bar,
        }
        if chart_id:
            payload["chartId"] = chart_id
        self.emit("tvchart:datafeed-bar-update", payload)

    def respond_tvchart_reset_cache(
        self,
        listener_guid: str,
        chart_id: str | None = None,
    ) -> None:
        """Signal that cached bar data for a listener should be reset.

        Parameters
        ----------
        listener_guid : str
            Subscription GUID from the ``tvchart:datafeed-subscribe`` event.
        chart_id : str, optional
            Target chart instance ID.
        """
        payload: dict[str, Any] = {
            "listenerGuid": listener_guid,
        }
        if chart_id:
            payload["chartId"] = chart_id
        self.emit("tvchart:datafeed-reset-cache", payload)

    # -- getMarks --

    def respond_tvchart_marks(
        self,
        request_id: str,
        marks: list[dict[str, Any]],
        chart_id: str | None = None,
        error: str | None = None,
    ) -> None:
        """Respond with chart marks for a getMarks request.

        Parameters
        ----------
        request_id : str
            Correlation ID from the incoming marks request.
        marks : list of dict
            Mark objects with ``id``, ``time``, ``color``, ``text``, etc.
        chart_id : str, optional
            Target chart instance ID.
        error : str, optional
            Error message; rejects the marks promise.
        """
        payload: dict[str, Any] = {
            "requestId": request_id,
            "marks": marks,
        }
        if chart_id:
            payload["chartId"] = chart_id
        if error:
            payload["error"] = error
        self.emit("tvchart:datafeed-marks-response", payload)

    # -- getTimescaleMarks --

    def respond_tvchart_timescale_marks(
        self,
        request_id: str,
        marks: list[dict[str, Any]],
        chart_id: str | None = None,
        error: str | None = None,
    ) -> None:
        """Respond with timescale marks for a getTimescaleMarks request.

        Parameters
        ----------
        request_id : str
            Correlation ID from the incoming timescale marks request.
        marks : list of dict
            Timescale mark objects with ``id``, ``time``, ``color``,
            ``label``, ``tooltip`` keys.
        chart_id : str, optional
            Target chart instance ID.
        error : str, optional
            Error message; rejects the timescale marks promise.
        """
        payload: dict[str, Any] = {
            "requestId": request_id,
            "marks": marks,
        }
        if chart_id:
            payload["chartId"] = chart_id
        if error:
            payload["error"] = error
        self.emit("tvchart:datafeed-timescale-marks-response", payload)

    # -- getServerTime --

    def respond_tvchart_server_time(
        self,
        request_id: str,
        time: int,
        chart_id: str | None = None,
        error: str | None = None,
    ) -> None:
        """Respond with server time (unix seconds, no milliseconds).

        Parameters
        ----------
        request_id : str
            Correlation ID from the incoming server-time request.
        time : int
            Current server time as UNIX seconds.
        chart_id : str, optional
            Target chart instance ID.
        error : str, optional
            Error message; rejects the server-time promise.
        """
        payload: dict[str, Any] = {
            "requestId": request_id,
            "time": time,
        }
        if chart_id:
            payload["chartId"] = chart_id
        if error:
            payload["error"] = error
        self.emit("tvchart:datafeed-server-time-response", payload)

    # ──────────────────────────────────────────────────────────
    # DatafeedProvider auto-wiring
    # ──────────────────────────────────────────────────────────

    def _wire_datafeed_provider(
        self,
        provider: DatafeedProvider,
        label: str | None = None,
    ) -> None:
        """Register all datafeed event handlers for *provider*.

        This eliminates the boilerplate each adapter would otherwise
        need to duplicate.  Call once after the provider is ready
        (e.g. after its config has been fetched).

        The host class must implement ``on(event, callback)`` (which
        ``PyWry``, ``InlineWidget``, and ``PyWryWidget`` all do).

        Parameters
        ----------
        provider : DatafeedProvider
            The datafeed provider instance.
        label : str or None
            Window label to register handlers on. If None, registers
            on all active windows (default ``on()`` behavior).
        """
        self._wire_data_request_handler(provider, label=label)
        self._wire_core_handlers(provider, label=label)
        self._wire_subscription_handlers(provider, label=label)
        self._wire_optional_handlers(provider, label=label)

    def _wire_data_request_handler(
        self,
        provider: DatafeedProvider,
        label: str | None = None,
    ) -> None:
        """Wire the ``tvchart:data-request`` handler for interval changes.

        When the user changes the interval, the JS toolbar emits
        ``tvchart:data-request``.  We call ``provider.get_bars()`` to
        fetch data from the upstream source (e.g. UDF server) and
        respond with ``tvchart:data-response`` containing the bars.
        The JS then destroys and recreates the chart with the new data.
        """
        from ..state.sync_helpers import run_async

        on = getattr(self, "on")  # noqa: B009 — dynamic but always present

        def _on_data_request(data: dict[str, Any], _et: str, _lb: str) -> None:
            chart_id = data.get("chartId", "main")
            series_id = data.get("seriesId", "main")
            interval = data.get("interval") or data.get("resolution") or "D"
            symbol = data.get("symbol", "")
            period_params = data.get("periodParams") or {}

            bars: list[dict[str, Any]] = []
            try:
                result = run_async(
                    provider.get_bars(
                        symbol,
                        interval,
                        period_params.get("from", 0),
                        period_params.get("to", 0),
                        period_params.get("countBack"),
                    ),
                    timeout=30.0,
                )
                bars = result.get("bars", [])
            except Exception:
                logger.exception(
                    "Data-request get_bars failed for %s %s",
                    symbol,
                    interval,
                )

            self.emit(
                "tvchart:data-response",
                {
                    "chartId": chart_id,
                    "seriesId": series_id,
                    "bars": bars,
                    "interval": interval,
                    "symbol": symbol,
                    "fitContent": True,
                },
            )

        on("tvchart:data-request", _on_data_request, label=label)

    def _wire_core_handlers(
        self,
        provider: DatafeedProvider,
        label: str | None = None,
    ) -> None:
        """Wire config, search, resolve, and history handlers."""
        from ..state.sync_helpers import run_async

        on = getattr(self, "on")  # noqa: B009 — dynamic but always present

        # -- onReady / config --
        def _on_config_request(data: dict[str, Any], _et: str, _lb: str) -> None:
            try:
                config = run_async(provider.get_config(), timeout=30.0)
                self.respond_tvchart_datafeed_config(
                    request_id=data.get("requestId", ""),
                    config=config,
                    chart_id=data.get("chartId"),
                )
            except Exception:
                logger.exception("Datafeed provider config failed")
                self.respond_tvchart_datafeed_config(
                    request_id=data.get("requestId", ""),
                    chart_id=data.get("chartId"),
                    error="Config request failed",
                )

        on("tvchart:datafeed-config-request", _on_config_request, label=label)

        # -- searchSymbols --
        if provider.supports_search:

            def _on_search_request(data: dict[str, Any], _et: str, _lb: str) -> None:
                request_id = data.get("requestId", "")
                chart_id = data.get("chartId")
                query = data.get("query", "")
                try:
                    items = run_async(
                        provider.search_symbols(
                            query,
                            data.get("symbolType", ""),
                            data.get("exchange", ""),
                            data.get("limit", 30),
                        ),
                        timeout=30.0,
                    )
                    self.respond_tvchart_symbol_search(
                        request_id=request_id,
                        items=items,
                        chart_id=chart_id,
                        query=query,
                    )
                except Exception:
                    logger.exception("Datafeed symbol search failed for query=%r", query)
                    self.respond_tvchart_symbol_search(
                        request_id=request_id,
                        items=[],
                        chart_id=chart_id,
                        query=query,
                        error="Symbol search failed",
                    )

            on("tvchart:datafeed-search-request", _on_search_request, label=label)

        # -- resolveSymbol --
        def _on_resolve_request(data: dict[str, Any], _et: str, _lb: str) -> None:
            request_id = data.get("requestId", "")
            chart_id = data.get("chartId")
            symbol = data.get("symbol", "")
            try:
                info = run_async(provider.resolve_symbol(symbol), timeout=30.0)
                self.respond_tvchart_symbol_resolve(
                    request_id=request_id,
                    symbol_info=info,
                    chart_id=chart_id,
                )
            except Exception:
                logger.exception("Datafeed symbol resolve failed for %r", symbol)
                self.respond_tvchart_symbol_resolve(
                    request_id=request_id,
                    symbol_info=None,
                    chart_id=chart_id,
                    error=f"Failed to resolve symbol: {symbol}",
                )

        on("tvchart:datafeed-resolve-request", _on_resolve_request, label=label)

        # -- getBars / history --
        def _on_history_request(data: dict[str, Any], _et: str, _lb: str) -> None:
            request_id = data.get("requestId", "")
            chart_id = data.get("chartId")
            symbol = data.get("symbol", "")
            resolution = data.get("resolution", "D")
            try:
                result = run_async(
                    provider.get_bars(
                        symbol,
                        resolution,
                        data.get("from", 0),
                        data.get("to", 0),
                        data.get("countBack"),
                    ),
                    timeout=30.0,
                )
                self.respond_tvchart_history(
                    request_id=request_id,
                    bars=result["bars"],
                    chart_id=chart_id,
                    status=result["status"],
                    no_data=result.get("no_data"),
                    next_time=result.get("next_time"),
                    error=result.get("error"),
                )
            except Exception:
                logger.exception("Datafeed history failed for %s %s", symbol, resolution)
                self.respond_tvchart_history(
                    request_id=request_id,
                    bars=[],
                    chart_id=chart_id,
                    status="error",
                    error="History request failed",
                )

        on("tvchart:datafeed-history-request", _on_history_request, label=label)

    def _wire_subscription_handlers(
        self,
        provider: DatafeedProvider,
        label: str | None = None,
    ) -> None:
        """Wire subscribe/unsubscribe bar-update handlers."""
        on = getattr(self, "on")  # noqa: B009

        def _on_subscribe(data: dict[str, Any], _et: str, _lb: str) -> None:
            provider.on_subscribe(
                listener_guid=data.get("listenerGuid", ""),
                symbol=data.get("symbol", ""),
                resolution=data.get("resolution", "D"),
                chart_id=data.get("chartId"),
            )

        on("tvchart:datafeed-subscribe", _on_subscribe, label=label)

        def _on_unsubscribe(data: dict[str, Any], _et: str, _lb: str) -> None:
            provider.on_unsubscribe(data.get("listenerGuid", ""))

        on("tvchart:datafeed-unsubscribe", _on_unsubscribe, label=label)

    def _wire_optional_handlers(
        self,
        provider: DatafeedProvider,
        label: str | None = None,
    ) -> None:
        """Wire marks, timescale marks, and server time handlers."""
        from ..state.sync_helpers import run_async

        on = getattr(self, "on")  # noqa: B009

        if provider.supports_marks:

            def _on_marks_request(data: dict[str, Any], _et: str, _lb: str) -> None:
                request_id = data.get("requestId", "")
                chart_id = data.get("chartId")
                try:
                    marks = run_async(
                        provider.get_marks(
                            data.get("symbol", ""),
                            data.get("from", 0),
                            data.get("to", 0),
                            data.get("resolution", "D"),
                        ),
                        timeout=30.0,
                    )
                    self.respond_tvchart_marks(
                        request_id=request_id,
                        marks=marks,
                        chart_id=chart_id,
                    )
                except Exception:
                    logger.exception("Datafeed marks request failed")
                    self.respond_tvchart_marks(
                        request_id=request_id,
                        marks=[],
                        chart_id=chart_id,
                        error="Marks request failed",
                    )

            on("tvchart:datafeed-marks-request", _on_marks_request, label=label)

        if provider.supports_timescale_marks:

            def _on_ts_marks_request(data: dict[str, Any], _et: str, _lb: str) -> None:
                request_id = data.get("requestId", "")
                chart_id = data.get("chartId")
                try:
                    marks = run_async(
                        provider.get_timescale_marks(
                            data.get("symbol", ""),
                            data.get("from", 0),
                            data.get("to", 0),
                            data.get("resolution", "D"),
                        ),
                        timeout=30.0,
                    )
                    self.respond_tvchart_timescale_marks(
                        request_id=request_id,
                        marks=marks,
                        chart_id=chart_id,
                    )
                except Exception:
                    logger.exception("Datafeed timescale marks request failed")
                    self.respond_tvchart_timescale_marks(
                        request_id=request_id,
                        marks=[],
                        chart_id=chart_id,
                        error="Timescale marks request failed",
                    )

            on("tvchart:datafeed-timescale-marks-request", _on_ts_marks_request, label=label)

        if provider.supports_time:

            def _on_server_time_request(data: dict[str, Any], _et: str, _lb: str) -> None:
                request_id = data.get("requestId", "")
                chart_id = data.get("chartId")
                try:
                    server_time = run_async(provider.get_server_time(), timeout=30.0)
                    self.respond_tvchart_server_time(
                        request_id=request_id,
                        time=server_time,
                        chart_id=chart_id,
                    )
                except Exception:
                    logger.exception("Datafeed server time request failed")
                    self.respond_tvchart_server_time(
                        request_id=request_id,
                        time=0,
                        chart_id=chart_id,
                        error="Server time request failed",
                    )

            on("tvchart:datafeed-server-time-request", _on_server_time_request, label=label)

    # ──────────────────────────────────────────────────────────
    # Chart storage write-through (server backend)
    # ──────────────────────────────────────────────────────────

    _TV_INDEX_KEY = "__pywry_tvchart_layout_index_v1"
    _TV_DATA_PREFIX = "__pywry_tvchart_layout_data_v1_"
    _TV_SETTINGS_DEFAULT_KEY = "__pywry_tvchart_settings_default_template_v1"
    _TV_SETTINGS_CUSTOM_KEY = "__pywry_tvchart_settings_custom_template_v1"

    def _wire_chart_storage(self, user_id: str = "default") -> None:  # noqa: C901
        """Register event handlers for the ``server`` storage backend.

        The JS ``server`` adapter emits ``tvchart:storage-set`` and
        ``tvchart:storage-remove`` on every write/delete.  This method
        translates those events into ``ChartStore`` calls so data is
        persisted on the Python side.

        Parameters
        ----------
        user_id : str
            Owner identity for the chart store.
        """
        from ..state import get_chart_store
        from ..state.sync_helpers import run_async

        on = getattr(self, "on")  # noqa: B009 — dynamic but always present
        store = get_chart_store()

        dp = self._TV_DATA_PREFIX
        ik = self._TV_INDEX_KEY
        dk = self._TV_SETTINGS_DEFAULT_KEY
        ck = self._TV_SETTINGS_CUSTOM_KEY

        # Cache the most recent JS index so layout data saves can look up
        # names/metadata even when the Python-side index hasn't been updated.
        _js_index_cache: list[dict[str, Any]] = []

        def _on_storage_set(data: dict[str, Any], _et: str = "", _lb: str = "") -> None:
            key = data.get("key", "")
            value = data.get("value", "")
            if not key:
                return
            try:
                if key.startswith(dp):
                    _chart_store_save_layout(
                        store,
                        run_async,
                        user_id,
                        key[len(dp) :],
                        value,
                        js_index=_js_index_cache,
                    )
                elif key == ik:
                    import json as _json

                    try:
                        parsed = _json.loads(value)
                        if isinstance(parsed, list):
                            _js_index_cache.clear()
                            _js_index_cache.extend(parsed)
                    except (ValueError, TypeError):
                        pass
                    _chart_store_sync_index(store, run_async, user_id, value)
                elif key == ck:
                    run_async(store.save_settings_template(user_id, value), timeout=5.0)
                elif key == dk:
                    run_async(store.set_settings_default_id(user_id, value), timeout=5.0)
            except Exception:
                logger.debug("Chart storage-set failed for key=%s", key, exc_info=True)

        def _on_storage_remove(data: dict[str, Any], _et: str = "", _lb: str = "") -> None:
            key = data.get("key", "")
            if not key:
                return
            try:
                if key.startswith(dp):
                    run_async(store.delete_layout(user_id, key[len(dp) :]), timeout=5.0)
                elif key == ck:
                    run_async(store.clear_settings_template(user_id), timeout=5.0)
                elif key == dk:
                    run_async(store.set_settings_default_id(user_id, "factory"), timeout=5.0)
            except Exception:
                logger.debug("Chart storage-remove failed for key=%s", key, exc_info=True)

        on("tvchart:storage-set", _on_storage_set)
        on("tvchart:storage-remove", _on_storage_remove)

    @staticmethod
    def _normalize_tvchart_data(data: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Convert data into bars and volume lists.

        Parameters
        ----------
        data : list[dict] | DataFrame
            OHLCV data.

        Returns
        -------
        tuple[list[dict], list[dict]]
            (bars, volume) ready for the JS frontend.
        """
        if hasattr(data, "to_dict") and hasattr(data, "columns"):
            from .normalize import normalize_ohlcv

            chart_data = normalize_ohlcv(data)
            if chart_data.series:
                s = chart_data.series[0]
                return s.bars, s.volume
            return [], []
        if isinstance(data, list):
            return data, []
        return [], []
