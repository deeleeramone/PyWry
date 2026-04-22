"""TradingView Lightweight Charts configuration models.

Pydantic models mirroring the Lightweight Charts API:

- TVChartConfig: Top-level chart configuration
- SeriesConfig: Per-series options (type, colors, price format)
- PriceScaleConfig / TimeScaleConfig / CrosshairConfig / LayoutConfig
- DrawingToolConfig / DrawingState: Drawing tool and persistence models
- IndicatorConfig / IndicatorPreset: Indicator definitions
- ChartTemplate / SavedChart / ChartTheme: Persistence models

All models use camelCase (via aliases) to match the Lightweight Charts JS API.

Lightweight Charts API Reference:
    https://tradingview.github.io/lightweight-charts/docs/api
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class SeriesType(str, Enum):
    """Lightweight Charts series types."""

    CANDLESTICK = "Candlestick"
    LINE = "Line"
    BAR = "Bar"
    AREA = "Area"
    BASELINE = "Baseline"
    HISTOGRAM = "Histogram"


class PriceScaleMode(int, Enum):
    """Price scale modes."""

    NORMAL = 0
    LOGARITHMIC = 1
    PERCENTAGE = 2
    INDEXED_TO_100 = 3


class CrosshairMode(int, Enum):
    """Crosshair modes."""

    NORMAL = 0
    MAGNET = 1


class LineStyle(int, Enum):
    """Line styles for crosshair and drawing lines."""

    SOLID = 0
    DOTTED = 1
    DASHED = 2
    LARGE_DASHED = 3
    SPARSE_DOTTED = 4


class LineWidth(int, Enum):
    """Predefined line widths."""

    ONE = 1
    TWO = 2
    THREE = 3
    FOUR = 4


class DrawingToolType(str, Enum):
    """Drawing tool types for the chart toolbar."""

    CROSSHAIR = "crosshair"
    POINTER = "pointer"
    ERASER = "eraser"
    TREND_LINE = "trendline"
    RAY = "ray"
    EXTENDED_LINE = "extended_line"
    HORIZONTAL_LINE = "hline"
    VERTICAL_LINE = "vline"
    HORIZONTAL_RAY = "hray"
    PARALLEL_CHANNEL = "parallel_channel"
    REGRESSION_CHANNEL = "regression_channel"
    FLAT_CHANNEL = "flat_channel"
    FIB_RETRACEMENT = "fib_retracement"
    FIB_EXTENSION = "fib_extension"
    FIB_TIME_ZONES = "fib_time_zones"
    FIB_FAN = "fib_fan"
    FIB_ARCS = "fib_arcs"
    FIB_CIRCLES = "fib_circles"
    GANN_FAN = "gann_fan"
    GANN_SQUARE = "gann_square"
    GANN_BOX = "gann_box"
    XABCD = "xabcd"
    HEAD_SHOULDERS = "head_shoulders"
    ELLIOTT_IMPULSE = "elliott_impulse"
    ELLIOTT_CORRECTION = "elliott_correction"
    ELLIOTT_TRIANGLE = "elliott_triangle"
    ELLIOTT_COMBO = "elliott_combo"
    ELLIOTT_DOUBLE = "elliott_double"
    RECTANGLE = "rect"
    CIRCLE = "circle"
    ELLIPSE = "ellipse"
    TRIANGLE_SHAPE = "triangle_shape"
    ARC = "arc"
    POLYLINE = "polyline"
    BRUSH = "brush"
    TEXT = "text"
    CALLOUT = "callout"
    NOTE = "note"
    PRICE_LABEL = "price_label"
    ARROW_MARKER = "arrow_marker"
    FLAG = "flag"
    MEASURE = "measure"
    DATE_RANGE = "date_range"
    PRICE_RANGE = "price_range"
    BARS_PATTERN = "bars_pattern"


_CAMEL_CONFIG = ConfigDict(
    populate_by_name=True,
    alias_generator=to_camel,
    extra="allow",
)


class PriceScaleConfig(BaseModel):
    """Price scale (Y-axis) configuration.

    See: https://tradingview.github.io/lightweight-charts/docs/api/interfaces/PriceScaleOptions

    Attributes
    ----------
    mode : PriceScaleMode
        Scale mode (normal, logarithmic, percentage, indexed-to-100).
    auto_scale : bool
        Automatically fit visible data to the price scale.
    invert_scale : bool
        Invert the price axis (high at bottom).
    align_labels : bool
        Align price labels to the scale edge.
    border_visible : bool
        Show the price scale border line.
    border_color : str or None
        Border line color.
    text_color : str or None
        Label text color.
    entire_text_only : bool
        Show labels only when they fit without truncation.
    visible : bool
        Show the price scale.
    scale_margins : dict or None
        Top/bottom margins as fractions (``{"top": 0.1, "bottom": 0.1}``).
    """

    model_config = _CAMEL_CONFIG

    mode: PriceScaleMode = PriceScaleMode.NORMAL
    auto_scale: bool = True
    invert_scale: bool = False
    align_labels: bool = True
    border_visible: bool = True
    border_color: str | None = None
    text_color: str | None = None
    entire_text_only: bool = False
    visible: bool = True
    scale_margins: dict[str, float] | None = None


class TimeScaleConfig(BaseModel):
    """Time scale (X-axis) configuration.

    See: https://tradingview.github.io/lightweight-charts/docs/api/interfaces/TimeScaleOptions

    Attributes
    ----------
    right_offset : int
        Whitespace bars to the right of the last data point.
    bar_spacing : float
        Minimum spacing between bars in pixels.
    min_bar_spacing : float
        Absolute minimum bar spacing (zoom limit).
    fix_left_edge : bool
        Prevent scrolling past the first bar.
    fix_right_edge : bool
        Prevent scrolling past the last bar.
    lock_visible_time_range_on_resize : bool
        Keep the same visible range when resizing.
    right_bar_stays_on_scroll : bool
        Pin the rightmost bar during scroll.
    border_visible : bool
        Show the time scale border line.
    border_color : str or None
        Border line color.
    visible : bool
        Show the time scale.
    time_visible : bool
        Show time-of-day on labels.
    seconds_visible : bool
        Show seconds on time labels.
    shift_visible_range_on_new_bar : bool
        Auto-scroll when a new bar arrives.
    tick_mark_max_character_length : int or None
        Max characters for tick mark labels.
    """

    model_config = _CAMEL_CONFIG

    right_offset: int = 5
    bar_spacing: float = 6.0
    min_bar_spacing: float = 0.5
    fix_left_edge: bool = False
    fix_right_edge: bool = False
    lock_visible_time_range_on_resize: bool = False
    right_bar_stays_on_scroll: bool = False
    border_visible: bool = True
    border_color: str | None = None
    visible: bool = True
    time_visible: bool = True
    seconds_visible: bool = True
    shift_visible_range_on_new_bar: bool = True
    tick_mark_max_character_length: int | None = None


class CrosshairConfig(BaseModel):
    """Crosshair configuration.

    Attributes
    ----------
    mode : CrosshairMode
        Crosshair tracking mode (normal or magnet).
    vert_line : dict or None
        Vertical crosshair line style overrides.
    horz_line : dict or None
        Horizontal crosshair line style overrides.
    """

    model_config = _CAMEL_CONFIG

    mode: CrosshairMode = CrosshairMode.MAGNET
    vert_line: dict[str, Any] | None = None
    horz_line: dict[str, Any] | None = None


class WatermarkConfig(BaseModel):
    """Watermark overlay text configuration.

    Attributes
    ----------
    visible : bool
        Show the watermark.
    text : str
        Watermark text content.
    font_size : int
        Font size in pixels.
    color : str
        Text color (CSS color string).
    horz_align : str
        Horizontal alignment (``"left"``, ``"center"``, ``"right"``).
    vert_align : str
        Vertical alignment (``"top"``, ``"center"``, ``"bottom"``).
    """

    model_config = _CAMEL_CONFIG

    visible: bool = False
    text: str = ""
    font_size: int = 48
    color: str = "rgba(128, 128, 128, 0.3)"
    horz_align: str = "center"
    vert_align: str = "center"


class GridConfig(BaseModel):
    """Chart grid lines configuration.

    Attributes
    ----------
    vert_lines : dict or None
        Vertical grid line style (``{"visible": True, "color": "..."``).
    horz_lines : dict or None
        Horizontal grid line style.
    """

    model_config = _CAMEL_CONFIG

    vert_lines: dict[str, Any] | None = None
    horz_lines: dict[str, Any] | None = None


class LayoutConfig(BaseModel):
    """Chart layout configuration.

    See: https://tradingview.github.io/lightweight-charts/docs/api/interfaces/LayoutOptions

    Attributes
    ----------
    background : dict or None
        Background style (``{"type": "solid", "color": "#000"}``).
    text_color : str or None
        Default text color for labels.
    font_size : int or None
        Default font size in pixels.
    font_family : str or None
        Default font family.
    """

    model_config = _CAMEL_CONFIG

    background: dict[str, str] | None = None
    text_color: str | None = None
    font_size: int | None = None
    font_family: str | None = None


class SeriesConfig(BaseModel):
    """Per-series configuration options.

    Attributes
    ----------
    series_type : SeriesType
        Chart series type (candlestick, line, area, etc.).
    price_scale_id : str
        Target price scale ('right', 'left', or custom ID).
    up_color : str or None
        Candlestick up (bullish) body color.
    down_color : str or None
        Candlestick down (bearish) body color.
    color : str or None
        Line / area / histogram color.
    line_width : int or None
        Line thickness in pixels.
    """

    model_config = _CAMEL_CONFIG

    series_type: SeriesType = SeriesType.CANDLESTICK
    price_scale_id: str = "right"
    visible: bool = True
    price_format: dict[str, Any] | None = None
    up_color: str | None = None
    down_color: str | None = None
    border_up_color: str | None = None
    border_down_color: str | None = None
    wick_up_color: str | None = None
    wick_down_color: str | None = None
    color: str | None = None
    line_width: int | None = None
    line_style: LineStyle | None = None
    top_color: str | None = None
    bottom_color: str | None = None
    line_color: str | None = None
    base_value: dict[str, Any] | None = None
    top_fill_color1: str | None = None
    top_fill_color2: str | None = None
    bottom_fill_color1: str | None = None
    bottom_fill_color2: str | None = None
    base: float | None = None


class DrawingToolConfig(BaseModel):
    """Configuration for an active drawing tool.

    Attributes
    ----------
    tool_type : DrawingToolType
        The drawing tool identifier.
    color : str
        Stroke color.
    line_width : int
        Stroke width in pixels.
    line_style : LineStyle
        Stroke dash pattern.
    fill_color : str or None
        Fill color (shapes only).
    fill_opacity : float
        Fill opacity 0-1.
    snap_to_candle : bool
        Whether coordinates snap to candle data points.
    """

    model_config = _CAMEL_CONFIG

    tool_type: DrawingToolType
    color: str = "#2196F3"
    line_width: int = 1
    line_style: LineStyle = LineStyle.SOLID
    fill_color: str | None = None
    fill_opacity: float = 0.2
    snap_to_candle: bool = True
    show_labels: bool = True
    text: str | None = None
    font_size: int = 12


class DrawingCoordinate(BaseModel):
    """A point in chart coordinate space (time, price).

    Attributes
    ----------
    time : int
        Unix epoch seconds.
    price : float
        Price value at the coordinate.
    """

    model_config = _CAMEL_CONFIG

    time: int  # Unix epoch seconds
    price: float


class DrawingState(BaseModel):
    """Serializable state of a single drawing on the chart.

    Attributes
    ----------
    drawing_id : str
        Unique identifier for this drawing.
    tool_type : DrawingToolType
        The type of drawing tool used.
    coordinates : list of DrawingCoordinate
        Anchor points for the drawing.
    config : DrawingToolConfig
        Visual configuration (color, line width, etc.).
    z_order : int
        Stacking order (higher = on top).
    locked : bool
        Whether the drawing is locked from editing.
    visible : bool
        Whether the drawing is visible.
    """

    model_config = _CAMEL_CONFIG

    drawing_id: str
    tool_type: DrawingToolType
    coordinates: list[DrawingCoordinate]
    config: DrawingToolConfig
    z_order: int = 0
    locked: bool = False
    visible: bool = True


class IndicatorConfig(BaseModel):
    """Configuration for a computed indicator overlay.

    Attributes
    ----------
    indicator_type : str
        Registry name (e.g. 'sma', 'rsi', 'macd').
    params : dict
        Indicator-specific parameters (period, source, etc.).
    series_style : SeriesConfig or None
        Override series rendering options.
    pane_index : int
        0 = main pane, 1+ = sub-panes.
    """

    model_config = _CAMEL_CONFIG

    indicator_type: str
    params: dict[str, Any] = Field(default_factory=dict)
    series_style: SeriesConfig | None = None
    pane_index: int = 0
    visible: bool = True
    label: str | None = None


class IndicatorPreset(BaseModel):
    """Saveable indicator parameter preset.

    Attributes
    ----------
    name : str
        Display name for the preset.
    indicator_type : str
        Registry name of the indicator (e.g. ``"sma"``, ``"rsi"``).
    params : dict
        Indicator-specific parameter values.
    description : str
        Optional description.
    """

    model_config = _CAMEL_CONFIG

    name: str
    indicator_type: str
    params: dict[str, Any]
    description: str = ""


class ChartTemplate(BaseModel):
    """Saveable chart style and indicator preset (no data).

    Templates store indicator configurations and chart style but not
    symbol, timeframe, or bar data.

    Attributes
    ----------
    name : str
        Template name.
    description : str
        Optional description.
    indicators : list of IndicatorConfig
        Indicator overlays and studies.
    series_config : SeriesConfig or None
        Main series rendering options.
    layout : LayoutConfig or None
        Chart layout overrides.
    grid : GridConfig or None
        Grid line overrides.
    crosshair : CrosshairConfig or None
        Crosshair overrides.
    price_scale : PriceScaleConfig or None
        Y-axis overrides.
    time_scale : TimeScaleConfig or None
        X-axis overrides.
    """

    model_config = _CAMEL_CONFIG

    name: str
    description: str = ""
    indicators: list[IndicatorConfig] = Field(default_factory=list)
    series_config: SeriesConfig | None = None
    layout: LayoutConfig | None = None
    grid: GridConfig | None = None
    crosshair: CrosshairConfig | None = None
    price_scale: PriceScaleConfig | None = None
    time_scale: TimeScaleConfig | None = None


class ChartTheme(BaseModel):
    """Custom color theme for chart elements.

    Attributes
    ----------
    name : str
        Theme name.
    description : str
        Optional description.
    background_color : str
        Chart background color.
    text_color : str
        Default text color.
    font_family : str or None
        Font family override.
    up_color : str
        Bullish (up) candle body color.
    down_color : str
        Bearish (down) candle body color.
    wick_up_color : str
        Bullish candle wick color.
    wick_down_color : str
        Bearish candle wick color.
    grid_color : str
        Grid line color.
    crosshair_color : str
        Crosshair line color.
    scale_border_color : str
        Price/time scale border color.
    scale_text_color : str
        Price/time scale text color.
    volume_up_color : str
        Up-volume bar color.
    volume_down_color : str
        Down-volume bar color.
    """

    model_config = _CAMEL_CONFIG

    name: str
    description: str = ""
    background_color: str = "#0a0a0d"
    text_color: str = "#d1d4dc"
    font_family: str | None = None
    up_color: str = "#089981"
    down_color: str = "#f23645"
    wick_up_color: str = "#089981"
    wick_down_color: str = "#f23645"
    grid_color: str = "rgba(255, 255, 255, 0.05)"
    crosshair_color: str = "#758696"
    scale_border_color: str = "#1c1f26"
    scale_text_color: str = "#d1d4dc"
    volume_up_color: str = "rgba(8, 153, 129, 0.35)"
    volume_down_color: str = "rgba(242, 54, 69, 0.35)"


class SavedChart(BaseModel):
    """Full chart state for persistence.

    Stores everything needed to restore a chart view. Bar data itself
    is not stored -- only a reference (symbol + timeframe) -- since data
    should be re-fetched on load.

    Attributes
    ----------
    name : str
        Layout name.
    symbol : str
        Symbol ticker (e.g. ``"XBTUSD"``).
    timeframe : str
        Resolution string (e.g. ``"1D"``, ``"60"``).
    series_type : SeriesType
        Chart series type (candlestick, line, etc.).
    indicators : list of IndicatorConfig
        Active indicator overlays.
    drawings : list of DrawingState
        Saved drawing annotations.
    visible_range : dict or None
        Time range to restore (``{"from": epoch, "to": epoch}``).
    template_ref : str or None
        Name of applied template.
    theme_ref : str or None
        Name of applied theme.
    compare_symbols : list of str
        Comparison overlay symbols.
    price_scale : PriceScaleConfig or None
        Y-axis configuration.
    time_scale : TimeScaleConfig or None
        X-axis configuration.
    layout : LayoutConfig or None
        Layout configuration.
    """

    model_config = _CAMEL_CONFIG

    name: str
    symbol: str = ""
    timeframe: str = "1D"
    series_type: SeriesType = SeriesType.CANDLESTICK
    indicators: list[IndicatorConfig] = Field(default_factory=list)
    drawings: list[DrawingState] = Field(default_factory=list)
    visible_range: dict[str, int] | None = None
    template_ref: str | None = None
    theme_ref: str | None = None
    compare_symbols: list[str] = Field(default_factory=list)
    price_scale: PriceScaleConfig | None = None
    time_scale: TimeScaleConfig | None = None
    layout: LayoutConfig | None = None


class TVChartConfig(BaseModel):
    """Top-level TradingView Lightweight Charts configuration.

    Attributes
    ----------
    series : SeriesConfig
        Main data series rendering options.
    chart_kind : str
        Which LWC factory to use.  ``"default"`` (time X axis) drives the
        standard ``createChart`` — this is what every equity / intraday /
        daily chart uses.  ``"price"`` drives ``createOptionsChart``
        (numeric price / strike on X) for options chains, IV smile,
        market-profile histograms, volume-by-strike.  ``"yield-curve"``
        drives ``createYieldCurveChart`` (tenor-in-months on X) for
        treasury / SOFR / swap / credit curves and any value-vs-tenor
        visualisation.
    yield_curve : dict or None
        Extra options forwarded to the yield-curve chart
        (``baseResolution``, ``minimumTimeRange``, ``startTimeRange``,
        ``formatTime``).  Ignored unless ``chart_kind == "yield-curve"``.
    layout : LayoutConfig or None
        Chart layout (background, text color, font).
    grid : GridConfig or None
        Grid line configuration.
    crosshair : CrosshairConfig or None
        Crosshair behavior and style.
    watermark : WatermarkConfig or None
        Watermark overlay.
    price_scale : PriceScaleConfig or None
        Default price scale options.
    time_scale : TimeScaleConfig or None
        Time scale options.
    right_price_scale : PriceScaleConfig or None
        Right price scale overrides.
    left_price_scale : PriceScaleConfig or None
        Left price scale overrides.
    overlay_price_scales : dict or None
        Named price scales for overlay series.
    locale : str or None
        Locale for number/date formatting.
    price_formatter : str or None
        Custom price formatting function name.
    time_formatter : str or None
        Custom time formatting function name.
    auto_size : bool
        Automatically resize chart to fill its container.
    """

    model_config = _CAMEL_CONFIG

    series: SeriesConfig = Field(default_factory=SeriesConfig)

    chart_kind: Literal["default", "price", "yield-curve"] = "default"
    yield_curve: dict[str, Any] | None = None

    layout: LayoutConfig | None = None
    grid: GridConfig | None = None
    crosshair: CrosshairConfig | None = None
    watermark: WatermarkConfig | None = None
    price_scale: PriceScaleConfig | None = None
    time_scale: TimeScaleConfig | None = None

    right_price_scale: PriceScaleConfig | None = None
    left_price_scale: PriceScaleConfig | None = None

    overlay_price_scales: dict[str, PriceScaleConfig] | None = None

    locale: str | None = None
    price_formatter: str | None = None
    time_formatter: str | None = None

    auto_size: bool = True

    def to_chart_options(self) -> dict[str, Any]:
        """Serialize to the options dict expected by createChart().

        Returns
        -------
        dict[str, Any]
            Chart options with camelCase keys.
        """
        opts: dict[str, Any] = {}

        if self.layout:
            opts["layout"] = self.layout.model_dump(by_alias=True, exclude_none=True)
        if self.grid:
            opts["grid"] = self.grid.model_dump(by_alias=True, exclude_none=True)
        if self.crosshair:
            opts["crosshair"] = self.crosshair.model_dump(by_alias=True, exclude_none=True)
        if self.watermark:
            opts["watermark"] = self.watermark.model_dump(by_alias=True, exclude_none=True)
        if self.right_price_scale:
            opts["rightPriceScale"] = self.right_price_scale.model_dump(
                by_alias=True, exclude_none=True
            )
        if self.left_price_scale:
            opts["leftPriceScale"] = self.left_price_scale.model_dump(
                by_alias=True, exclude_none=True
            )
        if self.time_scale:
            opts["timeScale"] = self.time_scale.model_dump(by_alias=True, exclude_none=True)

        opts["autoSize"] = self.auto_size

        if self.locale:
            opts["locale"] = self.locale

        # Yield-curve specific block.  Ignored by the non-yield-curve
        # factories but forwarded here so to_chart_options captures
        # the full config without a separate getter.
        if self.yield_curve:
            opts["yieldCurve"] = dict(self.yield_curve)

        return opts

    def to_payload(self) -> dict[str, Any]:
        """Serialize the full payload (options + chartKind) for the frontend.

        ``PYWRY_TVCHART_CREATE`` expects a dict with both the chart-factory
        selector (``chartKind``) and the options dict (``chartOptions``)
        so it can route to the right Lightweight Charts factory.
        """
        payload: dict[str, Any] = {
            "chartKind": self.chart_kind,
            "chartOptions": self.to_chart_options(),
        }
        return payload

    def to_series_options(self) -> dict[str, Any]:
        """Serialize the main series configuration.

        Returns
        -------
        dict[str, Any]
            Series options with camelCase keys.
        """
        return self.series.model_dump(by_alias=True, exclude_none=True)
