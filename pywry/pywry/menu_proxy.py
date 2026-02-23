"""MenuProxy — IPC-backed native menu management for PyWry.

Provides a Python interface to create, modify, and attach native OS menus
via IPC to the pytauri subprocess.  Menus are per-window (attached via
``WindowProxy.set_menu``) or app-level (via ``MenuProxy.set_as_app_menu``).

Menu items **must** have handlers — you cannot create a menu without
wiring up callbacks.  Use :meth:`register_handlers` to bind the item
callbacks to a window label after creation.

Examples
--------
>>> from pywry import PyWry
>>> from pywry.types import MenuConfig, MenuItemConfig, SubmenuConfig
>>>
>>> def on_new(data, event_type, label):
...     print("New file!")
>>>
>>> def on_quit(data, event_type, label):
...     print("Quitting…")
>>>
>>> menu = MenuConfig(
...     id="main-menu",
...     items=[
...         SubmenuConfig(
...             id="file",
...             text="File",
...             items=[
...                 MenuItemConfig(id="new", text="New", handler=on_new),
...                 MenuItemConfig(id="quit", text="Quit", handler=on_quit),
...             ],
...         ),
...     ],
... )
>>>
>>> app = PyWry()
>>> app.show("<h1>Hello</h1>", menu=menu)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from . import runtime
from .callbacks import get_registry
from .log import debug


if TYPE_CHECKING:
    from collections.abc import Callable

    from .types import MenuConfig, MenuItemKindConfig


class MenuProxy:
    """Proxy for a native menu living in the pytauri subprocess.

    Stores the ``{item_id: handler}`` map extracted from items at creation
    time.  Call :meth:`register_handlers` with a window label to wire
    everything up before the window is shown.

    Parameters
    ----------
    menu_id : str
        The menu identifier (matches the subprocess-side ``Menu`` ID).
    handlers : dict[str, Callable]
        Mapping of ``item_id`` → click handler extracted from item configs.
    """

    def __init__(
        self,
        menu_id: str,
        handlers: dict[str, Callable[..., Any]] | None = None,
    ) -> None:
        self._menu_id = menu_id
        self._handlers: dict[str, Callable[..., Any]] = handlers or {}
        self._registered_labels: set[str] = set()

    # ── Properties ────────────────────────────────────────────────────

    @property
    def id(self) -> str:
        """The menu identifier."""
        return self._menu_id

    @property
    def handlers(self) -> dict[str, Callable[..., Any]]:
        """Mapping of ``item_id`` → click handler."""
        return dict(self._handlers)

    # ── Factory ───────────────────────────────────────────────────────

    @classmethod
    def create(
        cls,
        menu_id: str,
        items: list[MenuItemKindConfig] | None = None,
    ) -> MenuProxy:
        """Create a native menu in the subprocess.

        Handlers are automatically extracted from every item that has one.

        Parameters
        ----------
        menu_id : str
            Unique menu identifier.
        items : list of MenuItemKindConfig, optional
            Initial menu items.  Each item must implement ``to_dict()``.

        Returns
        -------
        MenuProxy
            Proxy connected to the created menu.
        """
        from .types import _collect_handlers_from_items

        cmd: dict[str, Any] = {
            "action": "menu_create",
            "menu_id": menu_id,
        }
        handler_map: dict[str, Callable[..., Any]] = {}
        if items:
            cmd["items"] = [item.to_dict() for item in items]
            handler_map = _collect_handlers_from_items(items)
        runtime.send_command(cmd)
        resp = runtime.get_response(timeout=5.0)
        if resp is None or not resp.get("success", False):
            err = (resp or {}).get("error", "Unknown error")
            msg = f"Failed to create menu '{menu_id}': {err}"
            raise RuntimeError(msg)
        debug(f"MenuProxy created: {menu_id} ({len(handler_map)} handlers)")
        return cls(menu_id, handlers=handler_map)

    @classmethod
    def from_config(cls, config: MenuConfig) -> MenuProxy:
        """Create a native menu from a :class:`MenuConfig`.

        Handlers are extracted from the config's item tree automatically.

        Parameters
        ----------
        config : MenuConfig
            Complete menu configuration.

        Returns
        -------
        MenuProxy
        """
        return cls.create(menu_id=config.id, items=config.items)

    # ── Handler registration ──────────────────────────────────────────

    def register_handlers(self, label: str) -> None:
        """Register all item handlers for a window label.

        Installs a single ``menu:click`` callback on *label* that dispatches
        to the correct item handler based on ``data["item_id"]``.

        Safe to call multiple times — duplicate registrations are ignored.

        Parameters
        ----------
        label : str
            The window label to register handlers on.
        """
        if not self._handlers:
            return
        if label in self._registered_labels:
            return
        self._registered_labels.add(label)

        # Capture handler map in closure
        handler_map = self._handlers

        def _menu_dispatcher(
            data: dict[str, Any],
            event_type: str,
            lbl: str,
        ) -> None:
            item_id = data.get("item_id", "")
            handler = handler_map.get(item_id)
            if handler is not None:
                handler(data, event_type, lbl)

        registry = get_registry()
        registry.register(label, "menu:click", _menu_dispatcher)

    # ── Mutation ──────────────────────────────────────────────────────

    def append(self, item: MenuItemKindConfig) -> None:
        """Append an item to the end of the menu."""
        self._send_update("append", item_data=item.to_dict())

    def prepend(self, item: MenuItemKindConfig) -> None:
        """Prepend an item to the beginning of the menu."""
        self._send_update("prepend", item_data=item.to_dict())

    def insert(self, item: MenuItemKindConfig, position: int) -> None:
        """Insert an item at a specific position."""
        self._send_update("insert", item_data=item.to_dict(), position=position)

    def remove(self, item_id: str) -> None:
        """Remove a menu item by ID."""
        self._send_update("remove", item_id=item_id)

    def set_text(self, item_id: str, text: str) -> None:
        """Update the text of a menu item."""
        self._send_update("set_text", item_id=item_id, text=text)

    def set_enabled(self, item_id: str, enabled: bool) -> None:
        """Enable or disable a menu item."""
        self._send_update("set_enabled", item_id=item_id, enabled=enabled)

    def set_checked(self, item_id: str, checked: bool) -> None:
        """Set the checked state of a check menu item."""
        self._send_update("set_checked", item_id=item_id, checked=checked)

    def set_accelerator(self, item_id: str, accelerator: str | None) -> None:
        """Set or clear the keyboard accelerator for a menu item."""
        self._send_update("set_accelerator", item_id=item_id, accelerator=accelerator)

    def set_icon(self, item_id: str, icon: bytes | None, width: int = 16, height: int = 16) -> None:
        """Set the icon for an icon menu item."""
        import base64

        icon_b64 = base64.b64encode(icon).decode("ascii") if icon else None
        self._send_update(
            "set_icon", item_id=item_id, icon=icon_b64, icon_width=width, icon_height=height
        )

    # ── Attachment ────────────────────────────────────────────────────

    def set_as_app_menu(self) -> None:
        """Set this menu as the application-level menu bar."""
        runtime.send_command(
            {
                "action": "menu_set",
                "menu_id": self._menu_id,
                "target": "app",
            }
        )

    def set_as_window_menu(self, window_label: str) -> None:
        """Attach this menu to a specific window.

        Parameters
        ----------
        window_label : str
            The target window's label.
        """
        runtime.send_command(
            {
                "action": "menu_set",
                "menu_id": self._menu_id,
                "target": "window",
                "label": window_label,
            }
        )

    def popup(self, window_label: str, x: float | None = None, y: float | None = None) -> None:
        """Show this menu as a context menu.

        Parameters
        ----------
        window_label : str
            The window to show the popup on.
        x : float or None
            X coordinate (logical pixels).  ``None`` uses cursor position.
        y : float or None
            Y coordinate (logical pixels).  ``None`` uses cursor position.
        """
        cmd: dict[str, Any] = {
            "action": "menu_popup",
            "menu_id": self._menu_id,
            "label": window_label,
        }
        if x is not None and y is not None:
            cmd["position"] = {"x": x, "y": y}
        runtime.send_command(cmd)

    # ── Removal ───────────────────────────────────────────────────────

    def destroy(self) -> None:
        """Remove and destroy this menu in the subprocess."""
        runtime.send_command(
            {
                "action": "menu_remove",
                "menu_id": self._menu_id,
            }
        )

    # ── Internals ─────────────────────────────────────────────────────

    def _send_update(self, operation: str, **kwargs: Any) -> None:
        """Send a menu update command."""
        cmd: dict[str, Any] = {
            "action": "menu_update",
            "menu_id": self._menu_id,
            "operation": operation,
            **kwargs,
        }
        runtime.send_command(cmd)

    def __repr__(self) -> str:
        return f"MenuProxy(id={self._menu_id!r})"
