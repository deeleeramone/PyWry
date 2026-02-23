"""PyTauri type definitions for WebviewWindow API.

These types mirror the pytauri.webview and pytauri.window types for use
in the WindowProxy IPC layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, TypedDict


if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

# Color is RGBA tuple, each component 0-255
Color = tuple[int, int, int, int]


@dataclass(frozen=True)
class PhysicalSize:
    """Physical size in pixels."""

    width: int
    height: int

    def to_dict(self) -> dict[str, int]:
        """Serialize to dictionary for IPC."""
        return {"width": self.width, "height": self.height}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PhysicalSize:
        """Deserialize from dictionary."""
        return cls(width=int(data["width"]), height=int(data["height"]))


@dataclass(frozen=True)
class LogicalSize:
    """Logical size (scaled by DPI factor)."""

    width: float
    height: float

    def to_dict(self) -> dict[str, float]:
        """Serialize to dictionary for IPC."""
        return {"width": self.width, "height": self.height}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LogicalSize:
        """Deserialize from dictionary."""
        return cls(width=float(data["width"]), height=float(data["height"]))


@dataclass(frozen=True)
class PhysicalPosition:
    """Physical position in pixels."""

    x: int
    y: int

    def to_dict(self) -> dict[str, int]:
        """Serialize to dictionary for IPC."""
        return {"x": self.x, "y": self.y}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PhysicalPosition:
        """Deserialize from dictionary."""
        return cls(x=int(data["x"]), y=int(data["y"]))


@dataclass(frozen=True)
class LogicalPosition:
    """Logical position (scaled by DPI factor)."""

    x: float
    y: float

    def to_dict(self) -> dict[str, float]:
        """Serialize to dictionary for IPC."""
        return {"x": self.x, "y": self.y}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LogicalPosition:
        """Deserialize from dictionary."""
        return cls(x=float(data["x"]), y=float(data["y"]))


SizeType = PhysicalSize | LogicalSize
PositionType = PhysicalPosition | LogicalPosition


class Theme(Enum):
    """Window theme mode."""

    LIGHT = "Light"
    DARK = "Dark"


class TitleBarStyle(Enum):
    """Title bar style options."""

    VISIBLE = "Visible"
    TRANSPARENT = "Transparent"
    OVERLAY = "Overlay"


class UserAttentionType(Enum):
    """User attention request type."""

    CRITICAL = "Critical"
    INFORMATIONAL = "Informational"


class CursorIcon(Enum):
    """Cursor icon options."""

    DEFAULT = "Default"
    CROSSHAIR = "Crosshair"
    HAND = "Hand"
    ARROW = "Arrow"
    MOVE = "Move"
    TEXT = "Text"
    WAIT = "Wait"
    HELP = "Help"
    PROGRESS = "Progress"
    NOT_ALLOWED = "NotAllowed"
    CONTEXT_MENU = "ContextMenu"
    CELL = "Cell"
    VERTICAL_TEXT = "VerticalText"
    ALIAS = "Alias"
    COPY = "Copy"
    NO_DROP = "NoDrop"
    GRAB = "Grab"
    GRABBING = "Grabbing"
    ALL_SCROLL = "AllScroll"
    ZOOM_IN = "ZoomIn"
    ZOOM_OUT = "ZoomOut"
    E_RESIZE = "EResize"
    N_RESIZE = "NResize"
    NE_RESIZE = "NeResize"
    NW_RESIZE = "NwResize"
    S_RESIZE = "SResize"
    SE_RESIZE = "SeResize"
    SW_RESIZE = "SwResize"
    W_RESIZE = "WResize"
    EW_RESIZE = "EwResize"
    NS_RESIZE = "NsResize"
    NESW_RESIZE = "NeswResize"
    NWSE_RESIZE = "NwseResize"
    COL_RESIZE = "ColResize"
    ROW_RESIZE = "RowResize"


class Effect(Enum):
    """Visual effects for window background (platform-specific)."""

    # macOS vibrancy effects
    APPEARANCE_BASED = "AppearanceBased"
    LIGHT = "Light"
    DARK = "Dark"
    MEDIUM_LIGHT = "MediumLight"
    ULTRA_DARK = "UltraDark"
    TITLEBAR = "Titlebar"
    SELECTION = "Selection"
    MENU = "Menu"
    POPOVER = "Popover"
    SIDEBAR = "Sidebar"
    HEADER_VIEW = "HeaderView"
    SHEET = "Sheet"
    WINDOW_BACKGROUND = "WindowBackground"
    HUD_WINDOW = "HudWindow"
    FULL_SCREEN_UI = "FullScreenUI"
    TOOLTIP = "Tooltip"
    CONTENT_BACKGROUND = "ContentBackground"
    UNDER_WINDOW_BACKGROUND = "UnderWindowBackground"
    UNDER_PAGE_BACKGROUND = "UnderPageBackground"
    # Windows effects
    MICA = "Mica"
    MICA_DARK = "MicaDark"
    MICA_LIGHT = "MicaLight"
    TABBED = "Tabbed"
    TABBED_DARK = "TabbedDark"
    TABBED_LIGHT = "TabbedLight"
    BLUR = "Blur"
    ACRYLIC = "Acrylic"


class EffectState(Enum):
    """Effect state options."""

    FOLLOWS_WINDOW_ACTIVE_STATE = "FollowsWindowActiveState"
    ACTIVE = "Active"
    INACTIVE = "Inactive"


class ProgressBarStatus(Enum):
    """Progress bar status options."""

    NONE = "None"
    NORMAL = "Normal"
    INDETERMINATE = "Indeterminate"
    PAUSED = "Paused"
    ERROR = "Error"


class SameSite(Enum):
    """Cookie SameSite attribute."""

    STRICT = "Strict"
    LAX = "Lax"
    NONE = "None"


class Effects(TypedDict, total=False):
    """Visual effects configuration."""

    effects: Sequence[Effect]
    state: EffectState
    radius: float
    color: Color


class ProgressBarState(TypedDict, total=False):
    """Progress bar state configuration."""

    status: ProgressBarStatus
    progress: int  # 0-100


@dataclass
class Cookie:
    """HTTP Cookie representation."""

    name: str
    value: str
    domain: str = ""
    path: str = "/"
    secure: bool = False
    http_only: bool = False
    same_site: SameSite = SameSite.LAX
    expires: float | None = None  # Unix timestamp

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for IPC."""
        return {
            "name": self.name,
            "value": self.value,
            "domain": self.domain,
            "path": self.path,
            "secure": self.secure,
            "http_only": self.http_only,
            "same_site": self.same_site.value,
            "expires": self.expires,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Cookie:
        """Deserialize from dictionary."""
        return cls(
            name=data["name"],
            value=data["value"],
            domain=data.get("domain", ""),
            path=data.get("path", "/"),
            secure=data.get("secure", False),
            http_only=data.get("http_only", False),
            same_site=SameSite(data.get("same_site", "Lax")),
            expires=data.get("expires"),
        )


@dataclass
class Monitor:
    """Display monitor information."""

    name: str | None
    size: PhysicalSize
    position: PhysicalPosition
    scale_factor: float

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for IPC."""
        return {
            "name": self.name,
            "size": self.size.to_dict(),
            "position": self.position.to_dict(),
            "scale_factor": self.scale_factor,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Monitor:
        """Deserialize from dictionary."""
        return cls(
            name=data.get("name"),
            size=PhysicalSize.from_dict(data["size"]),
            position=PhysicalPosition.from_dict(data["position"]),
            scale_factor=float(data["scale_factor"]),
        )


def serialize_size(size: SizeType) -> dict[str, Any]:
    """Serialize a size value for IPC."""
    if isinstance(size, PhysicalSize):
        return {"type": "Physical", **size.to_dict()}
    return {"type": "Logical", **size.to_dict()}


def serialize_position(position: PositionType) -> dict[str, Any]:
    """Serialize a position value for IPC."""
    if isinstance(position, PhysicalPosition):
        return {"type": "Physical", **position.to_dict()}
    return {"type": "Logical", **position.to_dict()}


def serialize_effects(effects: Effects) -> dict[str, Any]:
    """Serialize effects configuration for IPC."""
    result: dict[str, Any] = {}
    if "effects" in effects:
        result["effects"] = [e.value for e in effects["effects"]]
    if "state" in effects:
        result["state"] = effects["state"].value
    if "radius" in effects:
        result["radius"] = effects["radius"]
    if "color" in effects:
        result["color"] = list(effects["color"])
    return result


def serialize_progress_bar(state: ProgressBarState) -> dict[str, Any]:
    """Serialize progress bar state for IPC."""
    result: dict[str, Any] = {}
    if "status" in state:
        result["status"] = state["status"].value
    if "progress" in state:
        result["progress"] = state["progress"]
    return result


# ── Menu types ────────────────────────────────────────────────────────


class PredefinedMenuItemKind(Enum):
    """Predefined OS-level menu item kinds."""

    SEPARATOR = "separator"
    COPY = "copy"
    CUT = "cut"
    PASTE = "paste"
    SELECT_ALL = "select_all"
    UNDO = "undo"
    REDO = "redo"
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"
    FULLSCREEN = "fullscreen"
    HIDE = "hide"
    HIDE_OTHERS = "hide_others"
    SHOW_ALL = "show_all"
    CLOSE_WINDOW = "close_window"
    QUIT = "quit"
    SERVICES = "services"
    ABOUT = "about"


@dataclass
class MenuItemConfig:
    """Configuration for a regular menu item.

    Every clickable menu item **must** have a handler.  Pass a callable that
    accepts ``(data, event_type, label)``.

    Parameters
    ----------
    id : str
        Unique identifier used for event routing.
    text : str
        Display text for the item.
    handler : Callable
        Click handler — receives ``(data, event_type, label)``.
    enabled : bool
        Whether the item is interactive.
    accelerator : str or None
        Keyboard shortcut (e.g. ``"CmdOrCtrl+S"``).
    """

    id: str
    text: str
    handler: Callable[..., Any] = field(repr=False, default=None)  # type: ignore[assignment]
    enabled: bool = True
    accelerator: str | None = None

    def __post_init__(self) -> None:
        if self.handler is None:
            msg = (
                f"MenuItemConfig(id={self.id!r}) requires a handler. "
                "Every menu item must have a click callback."
            )
            raise TypeError(msg)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for IPC."""
        d: dict[str, Any] = {
            "kind": "item",
            "id": self.id,
            "text": self.text,
            "enabled": self.enabled,
        }
        if self.accelerator is not None:
            d["accelerator"] = self.accelerator
        return d


@dataclass
class CheckMenuItemConfig:
    """Configuration for a check (toggle) menu item.

    Every check menu item **must** have a handler.

    Parameters
    ----------
    id : str
        Unique identifier used for event routing.
    text : str
        Display text.
    handler : Callable
        Click handler — receives ``(data, event_type, label)``.
    enabled : bool
        Whether the item is interactive.
    checked : bool
        Initial checked state.
    accelerator : str or None
        Keyboard shortcut.
    """

    id: str
    text: str
    handler: Callable[..., Any] = field(repr=False, default=None)  # type: ignore[assignment]
    enabled: bool = True
    checked: bool = False
    accelerator: str | None = None

    def __post_init__(self) -> None:
        if self.handler is None:
            msg = (
                f"CheckMenuItemConfig(id={self.id!r}) requires a handler. "
                "Every menu item must have a click callback."
            )
            raise TypeError(msg)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for IPC."""
        d: dict[str, Any] = {
            "kind": "check",
            "id": self.id,
            "text": self.text,
            "enabled": self.enabled,
            "checked": self.checked,
        }
        if self.accelerator is not None:
            d["accelerator"] = self.accelerator
        return d


@dataclass
class IconMenuItemConfig:
    """Configuration for a menu item with an icon.

    Every icon menu item **must** have a handler.

    Parameters
    ----------
    id : str
        Unique identifier used for event routing.
    text : str
        Display text.
    handler : Callable
        Click handler — receives ``(data, event_type, label)``.
    enabled : bool
        Whether the item is interactive.
    icon : bytes or None
        RGBA icon bytes (use ``pytauri.image.Image`` format).
    icon_width : int
        Icon width in pixels.
    icon_height : int
        Icon height in pixels.
    native_icon : str or None
        Native OS icon name (macOS only), e.g. ``"Add"``, ``"Folder"``.
    accelerator : str or None
        Keyboard shortcut.
    """

    id: str
    text: str
    handler: Callable[..., Any] = field(repr=False, default=None)  # type: ignore[assignment]
    enabled: bool = True
    icon: bytes | None = None
    icon_width: int = 16
    icon_height: int = 16
    native_icon: str | None = None
    accelerator: str | None = None

    def __post_init__(self) -> None:
        if self.handler is None:
            msg = (
                f"IconMenuItemConfig(id={self.id!r}) requires a handler. "
                "Every menu item must have a click callback."
            )
            raise TypeError(msg)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for IPC."""
        import base64

        d: dict[str, Any] = {
            "kind": "icon",
            "id": self.id,
            "text": self.text,
            "enabled": self.enabled,
        }
        if self.icon is not None:
            d["icon"] = base64.b64encode(self.icon).decode("ascii")
            d["icon_width"] = self.icon_width
            d["icon_height"] = self.icon_height
        if self.native_icon is not None:
            d["native_icon"] = self.native_icon
        if self.accelerator is not None:
            d["accelerator"] = self.accelerator
        return d


@dataclass
class PredefinedMenuItemConfig:
    """Configuration for a predefined OS menu item.

    Parameters
    ----------
    kind_name : PredefinedMenuItemKind
        Which predefined item to create.
    text : str or None
        Override text (some predefined items accept this).
    """

    kind_name: PredefinedMenuItemKind
    text: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for IPC."""
        d: dict[str, Any] = {
            "kind": "predefined",
            "kind_name": self.kind_name.value,
        }
        if self.text is not None:
            d["text"] = self.text
        return d


@dataclass
class SubmenuConfig:
    """Configuration for a submenu.

    Parameters
    ----------
    id : str
        Unique submenu identifier.
    text : str
        Display text for the submenu entry.
    enabled : bool
        Whether the submenu is interactive.
    items : list
        Child menu item configurations.
    """

    id: str
    text: str
    enabled: bool = True
    items: list[MenuItemKindConfig] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for IPC."""
        d: dict[str, Any] = {
            "kind": "submenu",
            "id": self.id,
            "text": self.text,
            "enabled": self.enabled,
        }
        if self.items:
            d["items"] = [item.to_dict() for item in self.items]
        return d

    def collect_handlers(self) -> dict[str, Callable[..., Any]]:
        """Walk children and return ``{item_id: handler}`` for every handled item."""
        return _collect_handlers_from_items(self.items or [])


# Union of all menu item config types
MenuItemKindConfig = (
    MenuItemConfig
    | CheckMenuItemConfig
    | IconMenuItemConfig
    | PredefinedMenuItemConfig
    | SubmenuConfig
)


@dataclass
class MenuConfig:
    """Top-level menu configuration.

    Parameters
    ----------
    id : str
        Menu identifier.
    items : list
        Menu item configurations.
    """

    id: str
    items: list[MenuItemKindConfig]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for IPC."""
        return {
            "id": self.id,
            "items": [item.to_dict() for item in self.items],
        }

    def collect_handlers(self) -> dict[str, Callable[..., Any]]:
        """Walk the full item tree and return ``{item_id: handler}``.

        Recursively descends into submenus.  Only items with a ``handler``
        attribute are included (e.g. ``PredefinedMenuItemConfig`` is skipped).
        """
        return _collect_handlers_from_items(self.items)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MenuConfig:
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            items=[_menu_item_from_dict(item) for item in data.get("items", [])],
        )


def _noop_handler(*_args: Any, **_kwargs: Any) -> None:
    """Placeholder handler for items created via ``from_dict``."""


def _menu_item_from_dict(data: dict[str, Any]) -> MenuItemKindConfig:
    """Deserialize a single menu item config from a dictionary.

    Items created this way receive a no-op handler.  Replace it with
    a real handler before attaching the menu to a window.
    """
    kind = data.get("kind", "item")
    if kind == "item":
        return MenuItemConfig(
            id=data["id"],
            text=data["text"],
            handler=_noop_handler,
            enabled=data.get("enabled", True),
            accelerator=data.get("accelerator"),
        )
    if kind == "check":
        return CheckMenuItemConfig(
            id=data["id"],
            text=data["text"],
            handler=_noop_handler,
            enabled=data.get("enabled", True),
            checked=data.get("checked", False),
            accelerator=data.get("accelerator"),
        )
    if kind == "icon":
        import base64

        icon_b64 = data.get("icon")
        icon_bytes = base64.b64decode(icon_b64) if icon_b64 else None
        return IconMenuItemConfig(
            id=data["id"],
            text=data["text"],
            handler=_noop_handler,
            enabled=data.get("enabled", True),
            icon=icon_bytes,
            icon_width=data.get("icon_width", 16),
            icon_height=data.get("icon_height", 16),
            native_icon=data.get("native_icon"),
            accelerator=data.get("accelerator"),
        )
    if kind == "predefined":
        return PredefinedMenuItemConfig(
            kind_name=PredefinedMenuItemKind(data["kind_name"]),
            text=data.get("text"),
        )
    if kind == "submenu":
        return SubmenuConfig(
            id=data["id"],
            text=data["text"],
            enabled=data.get("enabled", True),
            items=[_menu_item_from_dict(i) for i in data.get("items", [])],
        )
    msg = f"Unknown menu item kind: {kind}"
    raise ValueError(msg)


def _collect_handlers_from_items(
    items: list[MenuItemKindConfig],
) -> dict[str, Callable[..., Any]]:
    """Recursively collect ``{item_id: handler}`` from a list of menu items."""
    handlers: dict[str, Callable[..., Any]] = {}
    for item in items:
        if hasattr(item, "handler") and hasattr(item, "id") and item.handler is not None:
            handlers[item.id] = item.handler
        if isinstance(item, SubmenuConfig) and item.items:
            handlers.update(_collect_handlers_from_items(item.items))
    return handlers


# ── Tray types ────────────────────────────────────────────────────────


class MouseButton(Enum):
    """Mouse button identifiers."""

    LEFT = "Left"
    RIGHT = "Right"
    MIDDLE = "Middle"


class MouseButtonState(Enum):
    """Mouse button press state."""

    UP = "Up"
    DOWN = "Down"


@dataclass
class TrayIconConfig:
    """Configuration for a system tray icon.

    Parameters
    ----------
    id : str
        Unique tray icon identifier.
    tooltip : str or None
        Hover tooltip text.
    title : str or None
        Tray icon title (macOS menu bar text).
    icon : bytes or None
        RGBA icon bytes.
    icon_width : int
        Icon width in pixels.
    icon_height : int
        Icon height in pixels.
    menu : MenuConfig or None
        Menu to attach to the tray icon.
    menu_on_left_click : bool
        Whether left click shows the menu.
    on_click : Callable or None
        Handler for single-click events.
    on_double_click : Callable or None
        Handler for double-click events.
    on_right_click : Callable or None
        Handler for right-click events.
    """

    id: str
    tooltip: str | None = None
    title: str | None = None
    icon: bytes | None = None
    icon_width: int = 32
    icon_height: int = 32
    menu: MenuConfig | None = None
    menu_on_left_click: bool = True
    on_click: Callable[..., Any] | None = field(repr=False, default=None)
    on_double_click: Callable[..., Any] | None = field(repr=False, default=None)
    on_right_click: Callable[..., Any] | None = field(repr=False, default=None)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for IPC."""
        import base64

        d: dict[str, Any] = {"id": self.id}
        if self.tooltip is not None:
            d["tooltip"] = self.tooltip
        if self.title is not None:
            d["title"] = self.title
        if self.icon is not None:
            d["icon"] = base64.b64encode(self.icon).decode("ascii")
            d["icon_width"] = self.icon_width
            d["icon_height"] = self.icon_height
        if self.menu is not None:
            d["menu"] = self.menu.to_dict()
        d["menu_on_left_click"] = self.menu_on_left_click
        return d
