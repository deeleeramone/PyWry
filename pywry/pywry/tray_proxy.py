"""TrayProxy — IPC-backed system tray icon management for PyWry.

Provides a Python interface to create and control system tray icons
via IPC to the pytauri subprocess.  Tray icons are **app-level** —
they are not tied to a specific window.

Events are dispatched through the standard :mod:`pywry.callbacks`
``CallbackRegistry`` using the ``tray:`` namespace.

Tray event handlers (``on_click``, ``on_double_click``, ``on_right_click``)
can be attached directly on :class:`~pywry.types.TrayIconConfig` and are
automatically registered when using :meth:`TrayProxy.from_config`.

Examples
--------
Create a tray that tracks state and updates its tooltip:

>>> from pywry.tray_proxy import TrayProxy
>>> from pywry.types import TrayIconConfig, MenuConfig, MenuItemConfig
>>>
>>> paused = False
>>>
>>> def toggle_pause(data, event_type, label):
...     global paused
...     paused = not paused
...     tray.set_tooltip("Paused" if paused else "Running")
>>>
>>> tray = TrayProxy.from_config(
...     TrayIconConfig(
...         id="main-tray",
...         tooltip="Running",
...         menu=MenuConfig(
...             id="tray-menu",
...             items=[
...                 MenuItemConfig(
...                     id="toggle",
...                     text="Pause / Resume",
...                     handler=toggle_pause,
...                 ),
...             ],
...         ),
...     )
... )
"""

from __future__ import annotations

import base64
import contextlib

from typing import TYPE_CHECKING, Any, ClassVar

from . import runtime
from .callbacks import get_registry
from .log import debug


if TYPE_CHECKING:
    from .types import MenuConfig, TrayIconConfig


class TrayProxy:
    """Proxy for a system tray icon living in the pytauri subprocess.

    Instances are **not** created directly — use the :meth:`create` class
    method which sends the ``tray_create`` IPC command and returns a proxy.

    Parameters
    ----------
    tray_id : str
        The tray icon identifier.
    """

    _all_proxies: ClassVar[dict[str, TrayProxy]] = {}

    def __init__(self, tray_id: str) -> None:
        self._tray_id = tray_id
        self._menu_handler_map: dict[str, Any] = {}
        self._menu_dispatcher_registered = False
        TrayProxy._all_proxies[tray_id] = self

    # ── Properties ────────────────────────────────────────────────────

    @property
    def id(self) -> str:
        """The tray icon identifier."""
        return self._tray_id

    # ── Factory ───────────────────────────────────────────────────────

    @classmethod
    def create(
        cls,
        tray_id: str,
        tooltip: str | None = None,
        title: str | None = None,
        icon: bytes | None = None,
        icon_width: int = 32,
        icon_height: int = 32,
        menu: MenuConfig | None = None,
        menu_on_left_click: bool = True,
    ) -> TrayProxy:
        """Create a system tray icon in the subprocess.

        Parameters
        ----------
        tray_id : str
            Unique tray icon identifier.
        tooltip : str or None
            Hover tooltip text.
        title : str or None
            Tray title (macOS menu bar text).
        icon : bytes or None
            RGBA icon bytes.
        icon_width : int
            Icon width in pixels.
        icon_height : int
            Icon height in pixels.
        menu : MenuConfig or None
            Menu to attach.
        menu_on_left_click : bool
            Whether left click opens the menu.

        Returns
        -------
        TrayProxy
            Proxy connected to the created tray icon.

        Raises
        ------
        RuntimeError
            If the subprocess cannot be started or the tray creation fails.
        """
        # Ensure the pytauri subprocess is running (tray icons are app-level,
        # they don't require a window to be created first).
        if not runtime.is_running():
            debug("TrayProxy.create: starting pytauri subprocess...")
            if not runtime.start():
                msg = "Failed to start pytauri subprocess"
                raise RuntimeError(msg)
        if not runtime.wait_ready(timeout=10.0):
            msg = "pytauri subprocess did not become ready in time"
            raise RuntimeError(msg)

        cmd: dict[str, Any] = {
            "action": "tray_create",
            "tray_id": tray_id,
            "menu_on_left_click": menu_on_left_click,
        }
        if tooltip is not None:
            cmd["tooltip"] = tooltip
        if title is not None:
            cmd["title"] = title
        if icon is not None:
            cmd["icon"] = base64.b64encode(icon).decode("ascii")
            cmd["icon_width"] = icon_width
            cmd["icon_height"] = icon_height
        if menu is not None:
            cmd["menu"] = menu.to_dict()
        resp = runtime.send_command_with_response(cmd, timeout=5.0)
        if resp is None or not resp.get("success", False):
            err = (resp or {}).get("error", "Unknown error")
            msg = f"Failed to create tray icon '{tray_id}': {err}"
            raise RuntimeError(msg)
        debug(f"TrayProxy created: {tray_id}")
        return cls(tray_id)

    @classmethod
    def from_config(cls, config: TrayIconConfig) -> TrayProxy:
        """Create a tray icon from a :class:`TrayIconConfig`.

        Automatically registers any handlers declared on the config:

        - ``config.on_click`` → ``tray:click``
        - ``config.on_double_click`` → ``tray:double-click``
        - ``config.on_right_click`` → ``tray:right-click``
        - Item handlers from ``config.menu`` → ``tray:menu-click``

        Parameters
        ----------
        config : TrayIconConfig
            Complete tray icon configuration.

        Returns
        -------
        TrayProxy
        """
        proxy = cls.create(
            tray_id=config.id,
            tooltip=config.tooltip,
            title=config.title,
            icon=config.icon,
            icon_width=config.icon_width,
            icon_height=config.icon_height,
            menu=config.menu,
            menu_on_left_click=config.menu_on_left_click,
        )

        # Auto-register tray event handlers from config
        if config.on_click is not None:
            proxy.on("tray:click", config.on_click)
        if config.on_double_click is not None:
            proxy.on("tray:double-click", config.on_double_click)
        if config.on_right_click is not None:
            proxy.on("tray:right-click", config.on_right_click)

        # Auto-register menu item handlers from config.menu
        if config.menu is not None:
            proxy._register_menu_handlers(config.menu)

        return proxy

    # ── Setters ───────────────────────────────────────────────────────

    def set_icon(self, icon: bytes, width: int = 32, height: int = 32) -> None:
        """Update the tray icon image.

        Parameters
        ----------
        icon : bytes
            RGBA icon bytes.
        width : int
            Icon width.
        height : int
            Icon height.
        """
        self._send_update(
            icon=base64.b64encode(icon).decode("ascii"),
            icon_width=width,
            icon_height=height,
        )

    def set_tooltip(self, tooltip: str) -> None:
        """Set the hover tooltip text."""
        self._send_update(tooltip=tooltip)

    def set_title(self, title: str) -> None:
        """Set the tray title (macOS menu bar text)."""
        self._send_update(title=title)

    def set_menu(self, menu: MenuConfig) -> None:
        """Attach or replace the tray menu.

        Handlers declared on items in *menu* are registered
        automatically — the same as when creating via
        :meth:`from_config`.  Previous menu handlers are replaced.

        Parameters
        ----------
        menu : MenuConfig
            New menu configuration.
        """
        self._register_menu_handlers(menu)
        self._send_update(menu=menu.to_dict())

    def set_visible(self, visible: bool) -> None:
        """Show or hide the tray icon."""
        self._send_update(visible=visible)

    def set_menu_on_left_click(self, enabled: bool) -> None:
        """Control whether left click shows the tray menu."""
        self._send_update(menu_on_left_click=enabled)

    # ── Events ────────────────────────────────────────────────────────

    def on(self, event_type: str, callback: Any) -> None:
        """Register a callback for tray events.

        Event types use the ``tray:`` namespace:

        - ``tray:click`` — single click
        - ``tray:double-click`` — double click
        - ``tray:right-click`` — right click (convenience alias)
        - ``tray:enter`` — cursor enters tray icon area
        - ``tray:leave`` — cursor leaves tray icon area
        - ``tray:move`` — cursor moves over tray icon area

        Parameters
        ----------
        event_type : str
            Event type string (e.g. ``"tray:click"``).
        callback : Callable
            Handler function.
        """
        # Register on a synthetic label derived from the tray ID
        label = f"__tray__{self._tray_id}"
        get_registry().register(label, event_type, callback)

    # ── Removal ───────────────────────────────────────────────────────

    def remove(self) -> None:
        """Remove and destroy this tray icon in the subprocess."""
        TrayProxy._all_proxies.pop(self._tray_id, None)
        runtime.send_command_with_response(
            {
                "action": "tray_remove",
                "tray_id": self._tray_id,
            },
            timeout=2.0,
        )

    @classmethod
    def remove_all(cls) -> None:
        """Remove every tracked tray icon.

        Called by :meth:`PyWry.destroy` to guarantee cleanup regardless
        of whether trays were created via ``app.create_tray()`` or
        ``TrayProxy.from_config()``.
        """
        for proxy in list(cls._all_proxies.values()):
            with contextlib.suppress(Exception):
                proxy.remove()
        cls._all_proxies.clear()

    # ── Internals ─────────────────────────────────────────────────────

    def _register_menu_handlers(self, menu: MenuConfig) -> None:
        """Collect handlers from *menu* and (re-)register the dispatcher."""
        new_handlers = menu.collect_handlers()
        # Merge new handlers into the map (replaces any with the same ID)
        self._menu_handler_map.update(new_handlers)

        if not self._menu_dispatcher_registered and self._menu_handler_map:
            label = f"__tray__{self._tray_id}"

            # The dispatcher reads self._menu_handler_map at call time,
            # so swapping the map contents is enough — no re-registration.
            def _tray_menu_dispatcher(
                data: dict[str, Any],
                event_type: str,
                lbl: str,
            ) -> None:
                item_id = data.get("item_id", "")
                handler = self._menu_handler_map.get(item_id)
                if handler is not None:
                    handler(data, event_type, lbl)

            get_registry().register(label, "menu:click", _tray_menu_dispatcher)
            self._menu_dispatcher_registered = True

    def _send_update(self, **kwargs: Any) -> None:
        """Send a tray update command."""
        runtime.send_command(
            {
                "action": "tray_update",
                "tray_id": self._tray_id,
                **kwargs,
            }
        )

    def __repr__(self) -> str:
        return f"TrayProxy(id={self._tray_id!r})"
