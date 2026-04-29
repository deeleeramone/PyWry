"""TradingView chart data models.

Pydantic models for chart bar data, datafeed request/response messages,
symbol info, marks, and series data containers.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .config import SeriesType


class TVChartSeriesData(BaseModel):
    """Normalized bar data for a single series.

    Attributes
    ----------
    series_id : str
        Unique identifier for this series.
    bars : list[dict]
        OHLC or value bars with time key.
    volume : list[dict]
        Volume bars with time and value keys.
    series_type : SeriesType
        Chart series type (candlestick, line, etc.).
    has_volume : bool
        Whether volume data is available.
    total_rows : int
        Original row count before truncation.
    truncated_rows : int
        Number of rows dropped due to max_bars limit.
    """

    series_id: str
    bars: list[dict[str, Any]] = Field(default_factory=list)
    volume: list[dict[str, Any]] = Field(default_factory=list)
    series_type: SeriesType = SeriesType.CANDLESTICK
    has_volume: bool = False
    total_rows: int = 0
    truncated_rows: int = 0


class TVChartData(BaseModel):
    """Container for normalized chart data, possibly multi-series.

    Attributes
    ----------
    series : list[TVChartSeriesData]
        One or more series of bar data.
    columns : list[str]
        Original column names from the input data.
    time_column : str
        Name of the column used for time.
    symbol_column : str or None
        Name of the column used for multi-series grouping.
    is_multi_series : bool
        Whether there are multiple series.
    source_format : str
        Detected format: 'single', 'narrow', 'wide', 'multiindex'.
    column_types : dict[str, str]
        Column name to dtype string mapping.
    """

    series: list[TVChartSeriesData] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    time_column: str = "time"
    symbol_column: str | None = None
    is_multi_series: bool = False
    source_format: str = "single"
    column_types: dict[str, str] = Field(default_factory=dict)

    @property
    def bars(self) -> list[dict[str, Any]]:
        """Shortcut: bars from the first series."""
        return self.series[0].bars if self.series else []

    @property
    def volume(self) -> list[dict[str, Any]]:
        """Shortcut: volume bars from the first series."""
        return self.series[0].volume if self.series else []

    @property
    def series_ids(self) -> list[str]:
        """List of series identifiers."""
        return [s.series_id for s in self.series]

    @property
    def total_rows(self) -> int:
        """Sum of total_rows across all series."""
        return sum(s.total_rows for s in self.series)


class TVChartExchange(BaseModel):
    """Exchange descriptor for datafeed configuration."""

    value: str
    name: str
    desc: str = ""


class TVChartDatafeedSymbolType(BaseModel):
    """Symbol type descriptor for datafeed configuration."""

    name: str
    value: str


class TVChartSymbolInfoPriceSource(BaseModel):
    """Price source for symbol info."""

    id: str
    name: str


class TVChartLibrarySubsessionInfo(BaseModel):
    """Subsession info for extended session support."""

    id: str
    description: str
    session: str | None = None
    session_display: str | None = None
    session_correction: str | None = None


class TVChartSymbolInfo(BaseModel):
    """Full TradingView symbol metadata (LibrarySymbolInfo).

    Describes a tradeable instrument for the charting library.  All fields
    are optional except ``name``.

    Attributes
    ----------
    name : str
        Short symbol name (e.g. ``"BTCUSD"``).
    full_name : str
        Full symbol path (``"EXCHANGE:SYMBOL"``).
    base_name : list of str or None
        Underlying symbols for spread/expression instruments.
    ticker : str or None
        Unique symbol identifier used in datafeed requests.
    description : str
        Human-readable symbol description.
    type : str
        Instrument type (``"stock"``, ``"crypto"``, ``"forex"``, etc.).
    session : str
        Trading session in HHMM format (``"24x7"``, ``"0930-1600"``).
    session_display : str or None
        Display-formatted session string.
    exchange : str
        Exchange name.
    listed_exchange : str
        Primary listing exchange.
    timezone : str
        IANA timezone (e.g. ``"America/New_York"``).
    format : str
        Price display format (``"price"`` or ``"volume"``).
    pricescale : int
        Price precision denominator (100 = 2 decimals).
    minmov : int
        Minimum price movement numerator.
    has_intraday : bool or None
        Whether intraday resolutions are available.
    has_daily : bool or None
        Whether daily resolution is available.
    has_weekly_and_monthly : bool or None
        Whether weekly/monthly resolutions are available.
    supported_resolutions : list of str or None
        List of available resolutions (e.g. ``["1", "60", "D"]``).
    intraday_multipliers : list of str or None
        Intraday resolution multipliers.
    volume_precision : int or None
        Volume decimal precision.
    data_status : str
        Data availability (``"streaming"``, ``"endofday"``, ``"delayed_streaming"``).
    currency_code : str or None
        Currency code for the instrument.
    """

    name: str = ""
    full_name: str = ""
    base_name: list[str] | None = None
    ticker: str | None = None
    description: str = ""
    type: str = "stock"
    symbol_type: str | None = None
    session: str = "24x7"
    session_display: str | None = None
    session_holidays: str | None = None
    corrections: str | None = None
    exchange: str = ""
    listed_exchange: str = ""
    timezone: str = "Etc/UTC"
    format: str = "price"
    pricescale: int = 100
    minmov: int = 1
    minmove2: int | None = None
    fractional: bool | None = None
    has_intraday: bool | None = None
    has_daily: bool | None = None
    has_weekly_and_monthly: bool | None = None
    has_seconds: bool | None = None
    has_ticks: bool | None = None
    has_empty_bars: bool | None = None
    supported_resolutions: list[str] | None = None
    intraday_multipliers: list[str] | None = None
    seconds_multipliers: list[str] | None = None
    visible_plots_set: str | None = None
    volume_precision: int | None = None
    data_status: str = "streaming"
    expired: bool | None = None
    expiration_date: int | None = None
    sector: str | None = None
    industry: str | None = None
    currency_code: str | None = None
    original_currency_code: str | None = None
    unit_id: str | None = None
    original_unit_id: str | None = None
    unit_conversion_types: list[str] | None = None
    logo_urls: list[str] | None = None
    exchange_logo: str | None = None
    variable_tick_size: str | None = None
    price_source_id: str | None = None
    price_sources: list[TVChartSymbolInfoPriceSource] | None = None
    subsession_id: str | None = None
    subsessions: list[TVChartLibrarySubsessionInfo] | None = None


class TVChartDatafeedConfiguration(BaseModel):
    """Datafeed onReady configuration."""

    exchanges: list[TVChartExchange] | None = None
    symbols_types: list[TVChartDatafeedSymbolType] | None = None
    supported_resolutions: list[str] | None = None
    supports_marks: bool | None = None
    supports_time: bool | None = None
    supports_timescale_marks: bool | None = None
    currency_codes: list[str] | list[dict[str, Any]] | None = None


class TVChartSearchSymbolResultItem(BaseModel):
    """Single item from a symbol search result."""

    symbol: str
    full_name: str = ""
    description: str = ""
    exchange: str = ""
    ticker: str | None = None
    type: str = ""


class TVChartBar(BaseModel):
    """OHLCV bar data point (Bar)."""

    time: int  # milliseconds since Unix epoch
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None


class TVChartMark(BaseModel):
    """Chart mark placed on bars (Mark)."""

    id: str | int
    time: int  # Unix timestamp in seconds
    color: str | dict[str, str]
    text: str = ""
    label: str = ""
    label_font_color: str = ""
    min_size: int = 0
    border_width: int | None = None
    hovered_border_width: int | None = None
    image_url: str | None = None
    show_label_when_image_loaded: bool | None = None


class TVChartTimescaleMark(BaseModel):
    """Mark placed on the timescale axis (TimescaleMark)."""

    id: str | int
    time: int  # Unix timestamp in seconds
    color: str
    label: str = ""
    tooltip: list[str] = Field(default_factory=list)
    label_font_color: str | None = None
    shape: Literal["circle", "earningUp", "earningDown", "square", "diamond"] | None = None
    image_url: str | None = None
    show_label_when_image_loaded: bool | None = None


class TVChartDatafeedConfigRequest(BaseModel):
    """Frontend request for datafeed configuration (onReady)."""

    request_id: str
    chart_id: str | None = None


class TVChartDatafeedConfigResponse(BaseModel):
    """Backend response with datafeed configuration."""

    request_id: str
    config: TVChartDatafeedConfiguration = Field(default_factory=TVChartDatafeedConfiguration)
    chart_id: str | None = None
    error: str | None = None


class TVChartDatafeedSearchRequest(BaseModel):
    """Frontend request for symbol search suggestions."""

    request_id: str
    query: str
    exchange: str = ""
    symbol_type: str = ""
    chart_id: str | None = None
    limit: int = 20


class TVChartDatafeedSearchResponse(BaseModel):
    """Backend response with symbol search results."""

    request_id: str
    items: list[TVChartSearchSymbolResultItem] = Field(default_factory=list)
    chart_id: str | None = None
    query: str | None = None
    error: str | None = None


class TVChartDatafeedResolveRequest(BaseModel):
    """Frontend request for full metadata of a specific symbol."""

    request_id: str
    symbol: str
    chart_id: str | None = None


class TVChartDatafeedResolveResponse(BaseModel):
    """Backend response with resolved symbol metadata."""

    request_id: str
    symbol_info: TVChartSymbolInfo | None = None
    chart_id: str | None = None
    error: str | None = None


class TVChartDatafeedHistoryRequest(BaseModel):
    """Frontend request for historical bars (getBars)."""

    request_id: str
    symbol: str
    resolution: str
    from_time: int  # Unix timestamp seconds
    to_time: int  # Unix timestamp seconds (not inclusive)
    count_back: int | None = None
    first_data_request: bool = False
    chart_id: str | None = None


class TVChartDatafeedHistoryResponse(BaseModel):
    """Backend response with historical bars."""

    request_id: str
    bars: list[dict[str, Any]] = Field(default_factory=list)
    chart_id: str | None = None
    status: Literal["ok", "no_data", "error"] = "ok"
    no_data: bool | None = None
    next_time: int | None = None  # Unix timestamp milliseconds
    error: str | None = None


class TVChartDatafeedSubscribeRequest(BaseModel):
    """Frontend request to start real-time bar updates (subscribeBars)."""

    request_id: str
    symbol: str
    resolution: str
    listener_guid: str
    chart_id: str | None = None


class TVChartDatafeedUnsubscribeRequest(BaseModel):
    """Frontend request to stop real-time bar updates (unsubscribeBars)."""

    listener_guid: str
    chart_id: str | None = None


class TVChartDatafeedBarUpdate(BaseModel):
    """Real-time bar update pushed from backend to frontend."""

    listener_guid: str
    bar: dict[str, Any]
    chart_id: str | None = None


class TVChartDatafeedMarksRequest(BaseModel):
    """Frontend request for chart marks (getMarks)."""

    request_id: str
    symbol: str
    from_time: int  # Unix timestamp seconds
    to_time: int  # Unix timestamp seconds
    resolution: str
    chart_id: str | None = None


class TVChartDatafeedMarksResponse(BaseModel):
    """Backend response with chart marks."""

    request_id: str
    marks: list[dict[str, Any]] = Field(default_factory=list)
    chart_id: str | None = None
    error: str | None = None


class TVChartDatafeedTimescaleMarksRequest(BaseModel):
    """Frontend request for timescale marks (getTimescaleMarks)."""

    request_id: str
    symbol: str
    from_time: int  # Unix timestamp seconds
    to_time: int  # Unix timestamp seconds
    resolution: str
    chart_id: str | None = None


class TVChartDatafeedTimescaleMarksResponse(BaseModel):
    """Backend response with timescale marks."""

    request_id: str
    marks: list[dict[str, Any]] = Field(default_factory=list)
    chart_id: str | None = None
    error: str | None = None


class TVChartDatafeedServerTimeRequest(BaseModel):
    """Frontend request for server time."""

    request_id: str
    chart_id: str | None = None


class TVChartDatafeedServerTimeResponse(BaseModel):
    """Backend response with server time."""

    request_id: str
    time: int  # Unix timestamp seconds (no milliseconds)
    chart_id: str | None = None
    error: str | None = None
