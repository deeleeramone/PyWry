"""PyWry - Lightweight Python window manager using PyTauri.

This package provides a simple API for displaying HTML content in native
windows with support for Plotly.js, AG Grid, and custom event handling.
"""

# Frozen-executable subprocess interception — MUST run before any other
# pywry import.  In a frozen distributable (PyInstaller / Nuitka / cx_Freeze),
# when the parent process spawns itself as the Tauri subprocess, this call
# enters the Tauri event loop and exits immediately so the developer's
# application code never runs a second time.  It is a complete no-op in
# every other situation (normal Python, frozen parent process, etc.).
from ._freeze import freeze_support


freeze_support()

# pylint: disable=wrong-import-position
# Inline notebook module - import functions directly
from . import inline
from .app import PyWry
from .asset_loader import AssetLoader, get_asset_loader
from .callbacks import CallbackFunc, WidgetType, get_registry
from .config import (
    AssetSettings,
    HotReloadSettings,
    LogSettings,
    PyWrySettings,
    SecuritySettings,
    ThemeSettings,
    TimeoutSettings,
    WindowSettings,
)
from .grid import (
    ColDef,
    ColGroupDef,
    DefaultColDef,
    GridOptions,
    RowSelection,
    build_grid_config,
    to_js_grid_config,
)
from .hot_reload import HotReloadManager
from .inline import block, show_dataframe, show_plotly
from .menu_proxy import MenuProxy
from .modal import Modal
from .models import (
    HtmlContent,
    ThemeMode,
    WindowConfig,
    WindowMode,
)
from .notebook import (
    NotebookEnvironment,
    detect_notebook_environment,
    is_anywidget_available,
    should_use_inline_rendering,
)
from .plotly_config import (
    ModeBarButton,
    ModeBarConfig,
    PlotlyConfig,
    PlotlyIconName,
    StandardButton,
    SvgIcon,
)
from .state_mixins import (
    GridStateMixin,
    PlotlyStateMixin,
    ToolbarStateMixin,
)
from .toolbar import (
    Button,
    Checkbox,
    DateInput,
    Div,
    Marquee,
    MultiSelect,
    NumberInput,
    Option,
    RadioGroup,
    RangeInput,
    SearchInput,
    SecretInput,
    Select,
    SliderInput,
    TabGroup,
    TextArea,
    TextInput,
    TickerItem,
    Toggle,
    Toolbar,
    ToolbarItem,
)
from .tray_proxy import TrayProxy
from .types import (
    CheckMenuItemConfig,
    IconMenuItemConfig,
    MenuConfig,
    MenuItemConfig,
    MouseButton,
    MouseButtonState,
    PredefinedMenuItemConfig,
    PredefinedMenuItemKind,
    SubmenuConfig,
    TrayIconConfig,
)
from .widget import PyWryAgGridWidget, PyWryPlotlyWidget, PyWryWidget
from .window_manager import BrowserMode, get_lifecycle


__version__ = "2.0.0"

__all__ = [
    "AssetLoader",
    "AssetSettings",
    "BrowserMode",
    "Button",
    "CallbackFunc",
    "CheckMenuItemConfig",
    "Checkbox",
    "ColDef",
    "ColGroupDef",
    "DateInput",
    "DefaultColDef",
    "Div",
    "GridOptions",
    "GridStateMixin",
    "HotReloadManager",
    "HotReloadSettings",
    "HtmlContent",
    "IconMenuItemConfig",
    "LogSettings",
    "Marquee",
    "MenuConfig",
    "MenuItemConfig",
    "MenuProxy",
    "Modal",
    "ModeBarButton",
    "ModeBarConfig",
    "MouseButton",
    "MouseButtonState",
    "MultiSelect",
    "NotebookEnvironment",
    "NumberInput",
    "Option",
    "PlotlyConfig",
    "PlotlyIconName",
    "PlotlyStateMixin",
    "PredefinedMenuItemConfig",
    "PredefinedMenuItemKind",
    "PyWry",
    "PyWryAgGridWidget",
    "PyWryPlotlyWidget",
    "PyWrySettings",
    "PyWryWidget",
    "RadioGroup",
    "RangeInput",
    "RowSelection",
    "SearchInput",
    "SecretInput",
    "SecuritySettings",
    "Select",
    "SliderInput",
    "StandardButton",
    "SubmenuConfig",
    "SvgIcon",
    "TabGroup",
    "TextArea",
    "TextInput",
    "ThemeMode",
    "ThemeSettings",
    "TickerItem",
    "TimeoutSettings",
    "Toggle",
    "Toolbar",
    "ToolbarItem",
    "ToolbarStateMixin",
    "TrayIconConfig",
    "TrayProxy",
    "WidgetType",
    "WindowConfig",
    "WindowMode",
    "WindowSettings",
    "__version__",
    "block",
    "build_grid_config",
    "detect_notebook_environment",
    "freeze_support",
    "get_asset_loader",
    "get_lifecycle",
    "get_registry",
    "inline",
    "is_anywidget_available",
    "should_use_inline_rendering",
    "show_dataframe",
    "show_plotly",
    "to_js_grid_config",
]
