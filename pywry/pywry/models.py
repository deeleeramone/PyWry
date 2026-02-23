"""Pydantic models for PyWry v2."""

from __future__ import annotations

import re

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ThemeMode(str, Enum):
    """Window theme mode."""

    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


class WindowMode(str, Enum):
    """Window management mode."""

    NEW_WINDOW = "new_window"
    SINGLE_WINDOW = "single_window"
    MULTI_WINDOW = "multi_window"
    NOTEBOOK = "notebook"  # Inline rendering in Jupyter notebooks
    BROWSER = "browser"  # Opens in system browser, headless server mode


class WindowConfig(BaseModel):
    """Configuration for window creation.

    Fields are split into two groups:

    **Application-level fields** — used by PyWry's template and content pipeline
    (``theme``, ``enable_plotly``, ``aggrid_theme``, etc.).

    **Builder-level fields** — forwarded to ``WebviewWindowBuilder.build()`` in
    the subprocess.  Fields marked *(build-only)* can **only** be set at window
    creation time; they have no post-creation ``set_*`` equivalent.
    """

    # ── Application-level ─────────────────────────────────────────────────
    title: str = "PyWry"
    width: int = Field(default=1280, ge=200)
    height: int = Field(default=720, ge=150)
    min_width: int = Field(default=400, ge=100)
    min_height: int = Field(default=300, ge=100)
    theme: ThemeMode = ThemeMode.DARK
    center: bool = True
    devtools: bool = False
    allow_network: bool = True
    enable_plotly: bool = False
    enable_aggrid: bool = False
    plotly_theme: Literal[
        "plotly", "plotly_white", "plotly_dark", "ggplot2", "seaborn", "simple_white"
    ] = "plotly_dark"
    aggrid_theme: Literal["quartz", "alpine", "balham", "material"] = "alpine"

    # ── Builder-level (forwarded to WebviewWindowBuilder.build()) ─────────
    resizable: bool = True
    decorations: bool = True
    always_on_top: bool = False
    always_on_bottom: bool = False
    transparent: bool = False  # (build-only)
    fullscreen: bool = False
    maximized: bool = False
    focused: bool = True
    visible: bool = True
    shadow: bool = True
    skip_taskbar: bool = False
    content_protected: bool = False
    user_agent: str | None = None  # (build-only)
    incognito: bool = False  # (build-only)
    initialization_script: str | None = None  # (build-only)
    drag_and_drop: bool = True  # (build-only)

    # Fields that map directly to WebviewWindowBuilder kwargs
    _BUILDER_FIELDS: ClassVar[set[str]] = {
        "resizable",
        "decorations",
        "always_on_top",
        "always_on_bottom",
        "transparent",
        "fullscreen",
        "maximized",
        "focused",
        "visible",
        "shadow",
        "skip_taskbar",
        "content_protected",
        "user_agent",
        "incognito",
        "initialization_script",
        "drag_and_drop",
    }

    def builder_kwargs(self) -> dict[str, Any]:
        """Return non-default builder kwargs for ``WebviewWindowBuilder.build()``.

        Only includes fields whose values differ from the Pydantic defaults,
        keeping the IPC payload minimal.  ``title`` and ``inner_size`` are
        always handled separately by the caller.
        """
        defaults = WindowConfig()
        result: dict[str, Any] = {}
        for field in self._BUILDER_FIELDS:
            value = getattr(self, field)
            if value != getattr(defaults, field):
                result[field] = value
        return result

    @model_validator(mode="after")
    def validate_dimensions(self) -> WindowConfig:
        """Validate min dimensions don't exceed actual dimensions."""
        if self.min_width > self.width:
            raise ValueError(
                f"min_width ({self.min_width}) cannot be greater than width ({self.width})"
            )
        if self.min_height > self.height:
            raise ValueError(
                f"min_height ({self.min_height}) cannot be greater than height ({self.height})"
            )
        return self


class HtmlContent(BaseModel):
    """HTML content to display in a window."""

    html: str
    json_data: dict[str, Any] | None = None
    init_script: str | None = None
    css_files: list[Path | str] | None = None
    script_files: list[Path | str] | None = None
    inline_css: str | None = None
    watch: bool = False

    @field_validator("css_files", "script_files", mode="before")
    @classmethod
    def convert_paths(cls, v: Any) -> list[Path | str] | None:
        """Convert string paths to Path objects.

        Parameters
        ----------
        v : Any
            The value to convert.

        Returns
        -------
        list of Path or str, or None
            Converted path list or None.
        """
        if v is None:
            return None
        if isinstance(v, (str, Path)):
            return [Path(v) if isinstance(v, str) else v]
        return [Path(p) if isinstance(p, str) else p for p in v]


# Allow namespace:event or namespace:event:id
EVENT_NAMESPACE_PATTERN = re.compile(
    r"^[a-zA-Z][a-zA-Z0-9]*:[a-zA-Z][a-zA-Z0-9_-]*(:[a-zA-Z0-9_-]+)?$"
)
RESERVED_NAMESPACES = frozenset({"pywry", "plotly", "grid", "menu", "tray", "window"})


def validate_event_type(event_type: str) -> bool:
    """Validate event type matches namespace:event-name pattern or is wildcard.

    Parameters
    ----------
    event_type : str
        The event type string to validate.

    Returns
    -------
    bool
        True if valid, False otherwise.
    """
    if event_type == "*":
        return True
    return bool(EVENT_NAMESPACE_PATTERN.match(event_type))


class GenericEvent(BaseModel):
    """Generic event for custom event handling."""

    event_type: str
    data: Any = None
    window_label: str
    timestamp: datetime = Field(default_factory=datetime.now)

    @field_validator("event_type")
    @classmethod
    def validate_event_type_format(cls, v: str) -> str:
        """Validate event type matches namespace:event-name pattern.

        Parameters
        ----------
        v : str
            The event type string to validate.

        Returns
        -------
        str
            The validated event type.

        Raises
        ------
        ValueError
            If the event type is invalid.
        """
        if not validate_event_type(v):
            raise ValueError(
                f"Invalid event type '{v}'. Must match 'namespace:event-name' pattern "
                f"(lowercase, alphanumeric + hyphens) or '*' for wildcard."
            )
        return v


class ResultEvent(BaseModel):
    """Result sent from JavaScript via window.pywry.result()."""

    data: Any
    window_label: str


class PlotlyClickEvent(BaseModel):
    """Plotly click event data."""

    point_indices: list[int] = Field(default_factory=list)
    curve_number: int = 0
    point_data: dict[str, Any] = Field(default_factory=dict)
    window_label: str = ""


class PlotlySelectEvent(BaseModel):
    """Plotly selection event data."""

    points: list[dict[str, Any]] = Field(default_factory=list)
    range: dict[str, Any] | None = None
    window_label: str = ""


class PlotlyHoverEvent(BaseModel):
    """Plotly hover event data."""

    point_indices: list[int] = Field(default_factory=list)
    curve_number: int = 0
    point_data: dict[str, Any] = Field(default_factory=dict)
    window_label: str = ""


class PlotlyRelayoutEvent(BaseModel):
    """Plotly relayout event data (zoom, pan, etc.)."""

    relayout_data: dict[str, Any] = Field(default_factory=dict)
    window_label: str = ""


class GridSelectionEvent(BaseModel):
    """AG Grid selection event data."""

    selected_rows: list[dict[str, Any]] = Field(default_factory=list)
    selected_row_ids: list[str] = Field(default_factory=list)
    window_label: str = ""


class GridCellEvent(BaseModel):
    """AG Grid cell edit event data."""

    row_id: str = ""
    row_index: int = 0
    column: str = ""
    old_value: Any = None
    new_value: Any = None
    window_label: str = ""


class GridRowClickEvent(BaseModel):
    """AG Grid row click event data."""

    row_data: dict[str, Any] = Field(default_factory=dict)
    row_id: str = ""
    row_index: int = 0
    window_label: str = ""


class ResultPayload(BaseModel):
    """Payload for pywry_result command."""

    data: Any
    window_label: str


class GenericEventPayload(BaseModel):
    """Payload for pywry_event command."""

    event_type: str
    data: Any = None
    window_label: str

    @field_validator("event_type")
    @classmethod
    def validate_event_type_format(cls, v: str) -> str:
        """Validate event type matches namespace:event-name pattern.

        Parameters
        ----------
        v : str
            The event type string to validate.

        Returns
        -------
        str
            The validated event type.

        Raises
        ------
        ValueError
            If the event type is invalid.
        """
        if not validate_event_type(v):
            raise ValueError(
                f"Invalid event type '{v}'. Must match 'namespace:event-name' pattern."
            )
        return v


class FilePathPayload(BaseModel):
    """Payload for open_file command."""

    path: str


class WindowClosedPayload(BaseModel):
    """Payload for window closed notification."""

    window_label: str


class AlertPayload(BaseModel):
    """Enhanced alert event payload for pywry:alert system event.

    Supports typed toast notifications with auto-dismiss, persistence,
    and confirmation dialogs with callbacks.
    """

    message: str = Field(..., description="Alert message text (required)")
    type: Literal["info", "success", "warning", "error", "confirm"] = Field(
        default="info", description="Alert type determining icon and behavior"
    )
    title: str | None = Field(default=None, description="Optional alert title/header")
    duration: int | None = Field(
        default=None,
        description="Auto-dismiss duration in ms (None uses type default)",
    )
    callback_event: str | None = Field(
        default=None,
        description="Event to emit on confirm/cancel (for type='confirm')",
    )
    position: Literal["top-right", "bottom-right", "bottom-left", "top-left"] = Field(
        default="top-right", description="Toast position on screen"
    )
