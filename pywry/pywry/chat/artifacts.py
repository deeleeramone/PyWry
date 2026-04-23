"""Rich artifact models for the Chat component.

Artifacts are rendered as standalone blocks in the chat UI — they are
**not** streamed token-by-token and are **not** stored in conversation
history. These are PyWry extensions with no direct ACP equivalent.
"""

from __future__ import annotations

import re

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class _ArtifactBase(BaseModel):
    """Base class for all artifact types.

    Attributes
    ----------
    type : str
        Fixed to ``"artifact"`` for dispatch.
    artifact_type : str
        Subtype discriminator.
    title : str
        Display title shown in the artifact header.
    """

    type: Literal["artifact"] = "artifact"
    artifact_type: str = ""
    title: str = ""


class CodeArtifact(_ArtifactBase):
    """Code snippet rendered with syntax highlighting.

    Attributes
    ----------
    artifact_type : str
        Fixed to ``"code"``.
    content : str
        Source code or text snippet.
    language : str
        Language hint for syntax highlighting.
    """

    artifact_type: Literal["code"] = "code"
    content: str = ""
    language: str = ""


class MarkdownArtifact(_ArtifactBase):
    """Markdown content rendered as formatted HTML.

    Attributes
    ----------
    artifact_type : str
        Fixed to ``"markdown"``.
    content : str
        Markdown source.
    """

    artifact_type: Literal["markdown"] = "markdown"
    content: str = ""


class HtmlArtifact(_ArtifactBase):
    """Raw HTML rendered in a sandboxed container.

    Attributes
    ----------
    artifact_type : str
        Fixed to ``"html"``.
    content : str
        Raw HTML content.
    """

    artifact_type: Literal["html"] = "html"
    content: str = ""


class TableArtifact(_ArtifactBase):
    """Tabular data rendered as an AG Grid widget.

    Accepts the same data formats as ``normalize_data()`` in grid.py:
    pandas DataFrame, list of dicts, dict of lists, or single dict.

    Attributes
    ----------
    artifact_type : str
        Fixed to ``"table"``.
    data : list[dict[str, Any]] | dict[str, Any]
        Table rows or source object to normalize.
    column_defs : list[dict[str, Any]] | None
        Optional AG Grid column definitions.
    grid_options : dict[str, Any] | None
        Optional AG Grid configuration overrides.
    height : str
        CSS height for the table container.
    """

    artifact_type: Literal["table"] = "table"
    data: list[dict[str, Any]] | dict[str, Any] = Field(default_factory=list)
    column_defs: list[dict[str, Any]] | None = None
    grid_options: dict[str, Any] | None = None
    height: str = "400px"


class PlotlyArtifact(_ArtifactBase):
    """Plotly chart rendered as an interactive widget.

    ``figure`` accepts a standard Plotly figure dict:
    ``{"data": [...traces], "layout": {...}, "config": {...}}``.

    Attributes
    ----------
    artifact_type : str
        Fixed to ``"plotly"``.
    figure : dict[str, Any]
        Plotly figure payload.
    height : str
        CSS height for the chart container.
    """

    artifact_type: Literal["plotly"] = "plotly"
    figure: dict[str, Any] = Field(default_factory=dict)
    height: str = "400px"


class ImageArtifact(_ArtifactBase):
    """Image rendered as an ``<img>`` element.

    ``url`` can be a data URI (``data:image/png;base64,...``) or an
    HTTP(S) URL.

    Attributes
    ----------
    artifact_type : str
        Fixed to ``"image"``.
    url : str
        Image URL or data URI.
    alt : str
        Alternate text.
    """

    artifact_type: Literal["image"] = "image"
    url: str = ""
    alt: str = ""

    @field_validator("url")
    @classmethod
    def _block_dangerous_schemes(cls, v: str) -> str:
        """Reject ``javascript:`` URLs.

        Parameters
        ----------
        v : str
            Candidate image URL.

        Returns
        -------
        str
            The original URL when safe.

        Raises
        ------
        ValueError
            When the URL uses the ``javascript:`` scheme.
        """
        if re.match(r"\s*javascript\s*:", v, re.IGNORECASE):
            raise ValueError("javascript: URLs are not allowed")
        return v


class JsonArtifact(_ArtifactBase):
    """Structured data rendered as a collapsible JSON tree.

    Attributes
    ----------
    artifact_type : str
        Fixed to ``"json"``.
    data : Any
        Arbitrary JSON-serializable payload.
    """

    artifact_type: Literal["json"] = "json"
    data: Any = None


class TradingViewSeries(BaseModel):
    """A single data series on a TradingView chart.

    Attributes
    ----------
    type : str
        Series type — ``"candlestick"``, ``"line"``, ``"area"``,
        ``"bar"``, ``"baseline"``, or ``"histogram"``.
    data : list[dict[str, Any]]
        Data points. For candlestick:
        ``{"time", "open", "high", "low", "close"}``.
        For line/area/histogram: ``{"time", "value"}``.
    options : dict[str, Any]
        Series-level options (colors, line width, price format, etc.).
    markers : list[dict[str, Any]] | None
        Optional markers (buy/sell signals, annotations).
    """

    type: Literal["candlestick", "line", "area", "bar", "baseline", "histogram"] = "candlestick"
    data: list[dict[str, Any]] = Field(default_factory=list)
    options: dict[str, Any] = Field(default_factory=dict)
    markers: list[dict[str, Any]] | None = None


class AppArtifact(_ArtifactBase):
    """Full PyWry widget rendered inline as a sandboxed iframe.

    Unlike :class:`HtmlArtifact` which carries only raw HTML, an
    ``AppArtifact`` represents a complete PyWry app snapshot — inlined
    CSS / JS / data — and optionally carries a live ``widget_id`` +
    ``revision`` pair so the iframe can open a WebSocket bridge back to
    the Python runtime for event traffic. When a new revision of the
    same ``widget_id`` is emitted, older revisions close their bridge
    server-side and the iframe stays frozen at its last known state
    while remaining readable in chat history.

    Attributes
    ----------
    artifact_type : str
        Fixed to ``"app"``.
    html : str
        Self-contained HTML document (CSS / JS / data inlined).
    widget_id : str | None
        Optional backend identifier for live event wiring. When set,
        the iframe opens a WebSocket carrying ``revision`` so the
        server can reject stale renders.
    revision : int
        Monotonic render counter, incremented each time the widget is
        re-rendered via the MCP layer. ``0`` means "no live bridge —
        treat as a static snapshot".
    height : str
        CSS height for the iframe container.
    sandbox : bool
        If ``True`` (default), the iframe is loaded with
        ``sandbox="allow-scripts allow-same-origin"``.
    """

    artifact_type: Literal["app"] = "app"
    html: str = ""
    widget_id: str | None = None
    revision: int = 0
    height: str = "600px"
    sandbox: bool = True


class TradingViewArtifact(_ArtifactBase):
    """Interactive financial chart via TradingView lightweight-charts.

    Supports candlestick, line, area, bar, baseline, and histogram
    series. Multiple series can be overlaid on a single chart.

    Attributes
    ----------
    artifact_type : str
        Fixed to ``"tradingview"``.
    series : list[TradingViewSeries]
        One or more data series to render.
    options : dict[str, Any]
        Chart-level options passed to ``createChart()`` (layout, grid,
        crosshair, timeScale, rightPriceScale, etc.).
    height : str
        CSS height for the chart container.

    Examples
    --------
    >>> yield TradingViewArtifact(
    ...     title="AAPL Daily",
    ...     series=[
    ...         TradingViewSeries(
    ...             type="candlestick",
    ...             data=[
    ...                 {
    ...                     "time": "2024-01-02",
    ...                     "open": 185.5,
    ...                     "high": 186.1,
    ...                     "low": 184.0,
    ...                     "close": 185.6,
    ...                 },
    ...             ],
    ...         ),
    ...     ],
    ...     height="500px",
    ... )
    """

    artifact_type: Literal["tradingview"] = "tradingview"
    series: list[TradingViewSeries] = Field(default_factory=list)
    options: dict[str, Any] = Field(default_factory=dict)
    height: str = "400px"


Artifact = (
    CodeArtifact
    | MarkdownArtifact
    | HtmlArtifact
    | TableArtifact
    | PlotlyArtifact
    | ImageArtifact
    | JsonArtifact
    | TradingViewArtifact
    | AppArtifact
)
"""Union of all concrete artifact types."""
