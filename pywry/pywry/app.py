"""Main PyWry application class."""

# pylint: disable=too-many-lines

from __future__ import annotations

import contextlib
import json
import uuid

from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from .asset_loader import AssetLoader
from .assets import (
    get_aggrid_css,
    get_aggrid_js,
    get_openbb_icon,
    get_plotly_js,
)
from .callbacks import CallbackFunc, get_registry
from .config import PyWrySettings
from .hot_reload import HotReloadManager
from .log import debug, info, warn
from .models import (
    AlertPayload,
    HtmlContent,
    ThemeMode,
    WindowConfig,
    WindowMode,
)
from .notebook import should_use_inline_rendering
from .runtime import refresh_window as runtime_refresh_window
from .state_mixins import GridStateMixin, PlotlyStateMixin, ToolbarStateMixin
from .templates import build_html, build_plotly_init_script
from .widget_protocol import NativeWindowHandle
from .window_manager import (
    BrowserMode,
    MultiWindowMode,
    NewWindowMode,
    SingleWindowMode,
    WindowModeBase,
    get_lifecycle,
)


if TYPE_CHECKING:
    from .modal import Modal
    from .toolbar import Toolbar
    from .types import MenuConfig
    from .widget_protocol import BaseWidget
    from .window_manager import WindowLifecycle


class PyWry(GridStateMixin, PlotlyStateMixin, ToolbarStateMixin):  # pylint: disable=too-many-public-methods
    """Main PyWry application for displaying content in native windows.

    Supports three window modes:
    - NEW_WINDOW: Creates a new window for each show() call
    - SINGLE_WINDOW: Reuses one window, replaces content
    - MULTI_WINDOW: Multiple independent windows

    Examples
    --------
    >>> pywry = PyWry(mode=WindowMode.SINGLE_WINDOW)
    >>> pywry.show("<h1>Hello World</h1>")
    """

    def __init__(
        self,
        mode: WindowMode = WindowMode.NEW_WINDOW,
        theme: ThemeMode = ThemeMode.DARK,
        title: str = "PyWry",
        width: int = 800,
        height: int = 600,
        settings: PyWrySettings | None = None,
        hot_reload: bool = False,
    ) -> None:
        """Initialize PyWry.

        Parameters
        ----------
        mode : WindowMode, optional
            Window mode to use.
        theme : ThemeMode, optional
            Default theme mode.
        title : str, optional
            Default window title.
        width : int, optional
            Default window width.
        height : int, optional
            Default window height.
        settings : PyWrySettings or None, optional
            Configuration settings. If None, loads from env/files.
        hot_reload : bool, optional
            Enable hot reload for CSS/JS files.
        """
        super().__init__()
        self._mode_enum = mode
        self._theme = theme
        self._default_config = WindowConfig(
            title=title,
            width=width,
            height=height,
        )

        # Load settings (from env vars, config files, or defaults)
        self._settings = settings or PyWrySettings()

        # Set window close behavior before subprocess starts
        from . import runtime

        runtime.set_on_window_close(self._settings.window.on_window_close)
        # Set window mode so subprocess knows how to handle X button
        mode_map = {
            WindowMode.SINGLE_WINDOW: "single",
            WindowMode.MULTI_WINDOW: "multi",
            WindowMode.NEW_WINDOW: "new",
        }
        runtime.set_window_mode(mode_map.get(mode, "new"))
        # Pass Tauri plugin selection to subprocess
        runtime.set_tauri_plugins(self._settings.tauri_plugins)
        runtime.set_extra_capabilities(self._settings.extra_capabilities)

        # Initialize the appropriate window mode
        self._mode: WindowModeBase = self._create_mode(mode)

        # Asset loader for CSS/JS files
        self._asset_loader = AssetLoader()

        # Hot reload manager (only if enabled)
        self._hot_reload_manager: HotReloadManager | None = None
        if hot_reload or self._settings.hot_reload.enabled:
            self._hot_reload_manager = HotReloadManager(
                settings=self._settings.hot_reload,
                asset_loader=self._asset_loader,
            )
            self._hot_reload_manager.start()
            info("Hot reload enabled")

        # Registry of inline (anywidget/IFrame) widgets for notebook mode
        # Maps widget label -> widget instance, so app.emit() can route to them
        self._inline_widgets: dict[str, Any] = {}

        # Cache for bundled assets
        self._plotly_js: str | None = None
        self._aggrid_js: str | None = None
        self._aggrid_css: dict[tuple[str, ThemeMode], str] = {}

        # Auth state
        self._auth_result: Any = None  # AuthFlowResult | None
        self._session_manager: Any = None  # SessionManager | None

        # Active tray icons (for lifecycle cleanup)
        self._trays: dict[str, Any] = {}  # tray_id -> TrayProxy

        info(f"PyWry initialized with {mode.value} mode")

    def _create_mode(self, mode: WindowMode) -> WindowModeBase:
        """Create the appropriate window mode handler.

        Parameters
        ----------
        mode : WindowMode
            Window mode enum.

        Returns
        -------
        WindowModeBase
            Window mode handler instance.
        """
        if mode == WindowMode.NEW_WINDOW:
            return NewWindowMode()
        if mode == WindowMode.SINGLE_WINDOW:
            return SingleWindowMode()
        if mode == WindowMode.BROWSER:
            return BrowserMode()
        # MULTI_WINDOW
        return MultiWindowMode()

    def _register_inline_widget(self, widget: Any) -> None:
        """Register an inline widget so app.emit() can route events to it.

        Parameters
        ----------
        widget : BaseWidget
            Widget instance with a ``label`` attribute and ``emit`` method.
        """
        if hasattr(widget, "label") and hasattr(widget, "emit"):
            self._inline_widgets[widget.label] = widget

    @property
    def settings(self) -> PyWrySettings:
        """Get the current settings."""
        return self._settings

    @property
    def theme(self) -> ThemeMode:
        """Get the current theme mode."""
        return self._theme

    @theme.setter
    def theme(self, value: ThemeMode) -> None:
        """Set the theme mode."""
        self._theme = value
        debug(f"Theme changed to {value.value}")

    def _setup_hot_reload_watching(
        self,
        target_label: str,
        html_content: HtmlContent,
    ) -> None:
        """Set up hot reload file watching for a window.

        Parameters
        ----------
        target_label : str
            The window label.
        html_content : HtmlContent
            The HTML content with files to watch.
        """
        lifecycle = get_lifecycle()

        if html_content.css_files:
            for css_file in html_content.css_files:
                css_path = Path(css_file) if isinstance(css_file, str) else css_file
                lifecycle.add_watched_file(target_label, css_path, "css")

        if html_content.script_files:
            for script_file in html_content.script_files:
                script_path = Path(script_file) if isinstance(script_file, str) else script_file
                lifecycle.add_watched_file(target_label, script_path, "js")

        watch_content = html_content
        if not html_content.watch:
            watch_content = HtmlContent(
                html=html_content.html,
                json_data=html_content.json_data,
                init_script=html_content.init_script,
                css_files=html_content.css_files,
                script_files=html_content.script_files,
                inline_css=html_content.inline_css,
                watch=True,
            )

        if self._hot_reload_manager:
            self._hot_reload_manager.enable_for_window(target_label, watch_content)

        debug(f"Hot reload enabled for window {target_label}")

    # ── Auth API ──────────────────────────────────────────────────────

    @property
    def is_authenticated(self) -> bool:
        """Check if the app has a successful authentication result."""
        return self._auth_result is not None and getattr(self._auth_result, "success", False)

    def login(
        self,
        provider: Any | None = None,
        **kwargs: Any,
    ) -> Any:
        """Authenticate via OAuth2.

        In native mode, opens a dedicated auth window pointing at the
        provider's authorize URL. Blocks until authentication completes.

        In deploy mode, returns the login URL for the frontend.

        Parameters
        ----------
        provider : OAuthProvider, optional
            Override the default provider from settings.
        **kwargs : Any
            Additional keyword arguments passed to ``AuthFlowManager.run_native()``.

        Returns
        -------
        AuthFlowResult
            The result of the authentication flow.

        Raises
        ------
        AuthenticationError
            If authentication fails.
        """
        from .auth.flow import AuthFlowManager
        from .auth.providers import OAuthProvider, create_provider_from_settings
        from .auth.session import SessionManager
        from .auth.token_store import get_token_store

        # Resolve provider
        if provider is None:
            oauth2_settings = self._settings.oauth2
            if oauth2_settings is None:
                # Try to instantiate from env vars as a fallback
                from .config import OAuth2Settings

                try:
                    oauth2_settings = OAuth2Settings()
                except Exception:
                    oauth2_settings = None
                if oauth2_settings is None or not oauth2_settings.client_id:
                    from .exceptions import AuthenticationError

                    msg = (
                        "No OAuth2 settings configured. "
                        "Set PYWRY_OAUTH2__CLIENT_ID and PYWRY_OAUTH2__PROVIDER, "
                        "or pass a provider instance."
                    )
                    raise AuthenticationError(msg)
                # Cache the auto-detected settings
                self._settings.oauth2 = oauth2_settings
            provider = create_provider_from_settings(oauth2_settings)
        elif not isinstance(provider, OAuthProvider):
            # Assume it's settings-like
            provider = create_provider_from_settings(provider)

        oauth2_settings = self._settings.oauth2
        use_pkce = getattr(oauth2_settings, "use_pkce", True) if oauth2_settings else True
        auth_timeout = (
            getattr(oauth2_settings, "auth_timeout_seconds", 120.0) if oauth2_settings else 120.0
        )
        token_backend = (
            getattr(oauth2_settings, "token_store_backend", "memory")
            if oauth2_settings
            else "memory"
        )
        refresh_buffer = (
            getattr(oauth2_settings, "refresh_buffer_seconds", 60) if oauth2_settings else 60
        )

        # Create token store
        token_store = get_token_store(backend=token_backend)

        # Create session manager
        self._session_manager = SessionManager(
            provider=provider,
            token_store=token_store,
            refresh_buffer_seconds=refresh_buffer,
        )

        # Create flow manager
        flow_manager = AuthFlowManager(
            provider=provider,
            token_store=token_store,
            session_manager=self._session_manager,
            use_pkce=use_pkce,
            auth_timeout=auth_timeout,
        )

        # Run the flow
        result = flow_manager.authenticate(app=self, **kwargs)

        self._auth_result = result
        return result

    def logout(self) -> None:
        """Log out and clear authentication state.

        Clears stored tokens and cancels any background refresh.
        """
        if self._session_manager is not None:
            from .state.sync_helpers import run_async

            with contextlib.suppress(Exception):
                run_async(self._session_manager.logout())
            self._session_manager = None
        self._auth_result = None

    # ── Builder defaults ──────────────────────────────────────────────

    def set_initialization_script(self, js: str) -> None:
        """Set the default ``initialization_script`` for new windows.

        This JavaScript is injected by ``WebviewWindowBuilder`` **before**
        the page loads and persists across navigations.  Individual
        ``show()`` calls can override this via the ``initialization_script``
        keyword argument.

        Parameters
        ----------
        js : str
            JavaScript source code to inject.
        """
        self._default_config.initialization_script = js

    @property
    def default_config(self) -> WindowConfig:
        """Return the mutable default ``WindowConfig``.

        Callers may set builder-level fields directly::

            app.default_config.resizable = False
            app.default_config.transparent = True
        """
        return self._default_config

    # ── Menu & Tray ───────────────────────────────────────────────────

    def create_menu(
        self,
        menu_id: str,
        items: list[Any] | None = None,
    ) -> Any:
        """Create a native menu.

        Parameters
        ----------
        menu_id : str
            Unique menu identifier.
        items : list of MenuItemKindConfig, optional
            Menu items.

        Returns
        -------
        MenuProxy
            Proxy for the created menu.
        """
        self._require_native_mode("create_menu()")

        from .menu_proxy import MenuProxy

        return MenuProxy.create(menu_id=menu_id, items=items)

    def create_tray(
        self,
        tray_id: str,
        tooltip: str | None = None,
        title: str | None = None,
        icon: bytes | None = None,
        icon_width: int = 32,
        icon_height: int = 32,
        menu: Any = None,
        menu_on_left_click: bool = True,
    ) -> Any:
        """Create a system tray icon.

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
            Icon width.
        icon_height : int
            Icon height.
        menu : MenuConfig or None
            Menu to attach.
        menu_on_left_click : bool
            Whether left click opens the menu.

        Returns
        -------
        TrayProxy
            Proxy for the created tray icon.
        """
        self._require_native_mode("create_tray()")

        from .tray_proxy import TrayProxy

        tray = TrayProxy.create(
            tray_id=tray_id,
            tooltip=tooltip,
            title=title,
            icon=icon,
            icon_width=icon_width,
            icon_height=icon_height,
            menu=menu,
            menu_on_left_click=menu_on_left_click,
        )
        self._trays[tray_id] = tray
        return tray

    def remove_tray(self, tray_id: str) -> None:
        """Remove a system tray icon.

        Works for trays created via :meth:`create_tray` **and** those
        created directly via ``TrayProxy.from_config()`` or
        ``TrayProxy.create()``.

        Parameters
        ----------
        tray_id : str
            The tray icon identifier.
        """
        from .tray_proxy import TrayProxy

        tray = self._trays.pop(tray_id, None)
        if tray is None:
            # Fall back to the class-level registry
            tray = TrayProxy._all_proxies.get(tray_id)
        if tray is not None:
            tray.remove()

    # pylint: disable=too-many-arguments,too-many-branches,too-many-statements
    def show(  # noqa: C901, PLR0912, PLR0915
        self,
        content: str | HtmlContent,
        title: str | None = None,
        width: int | str | None = None,
        height: int | None = None,
        callbacks: dict[str, CallbackFunc] | None = None,
        include_plotly: bool = False,
        include_aggrid: bool = False,
        aggrid_theme: Literal["quartz", "alpine", "balham", "material"] = "alpine",
        label: str | None = None,
        watch: bool | None = None,
        toolbars: list[dict[str, Any] | Toolbar] | None = None,
        modals: list[dict[str, Any] | Modal] | None = None,
        initialization_script: str | None = None,
        menu: MenuConfig | None = None,
    ) -> NativeWindowHandle | BaseWidget:
        """Show content in a window.

        In a notebook environment (Jupyter, IPython, Colab, etc.), this will
        automatically render content inline via IFrame instead of opening
        a native window.

        Parameters
        ----------
        content : str or HtmlContent
            HTML content or HtmlContent object.
        title : str or None, optional
            Window title (overrides default).
        width : int or str or None, optional
            Window width - int for pixels, str for CSS value (e.g., "60%", "500px").
        height : int or None, optional
            Window height (overrides default).
        callbacks : dict[str, CallbackFunc] or None, optional
            Event callbacks (event_type -> handler).
        include_plotly : bool, optional
            Include Plotly.js library.
        include_aggrid : bool, optional
            Include AG Grid library.
        aggrid_theme : {'quartz', 'alpine', 'balham', 'material'}, optional
            AG Grid theme name (default: 'alpine').
        label : str or None, optional
            Window label (for MULTI_WINDOW mode updates).
        watch : bool or None, optional
            Enable hot reload for CSS/JS files (overrides HtmlContent.watch).
        toolbars : list[dict], optional
            List of toolbar configs. Each toolbar has 'position' and 'items' keys.
        modals : list[dict], optional
            List of modal configs. Each modal has 'title' and 'items' keys.
        initialization_script : str or None, optional
            JavaScript to inject via `WebviewWindowBuilder` *before* the
            page loads.  Persists across navigations (unlike per-content
            ``HtmlContent.init_script``).  Overrides the default set via
            ``set_initialization_script()`` for this call only.
        menu : MenuConfig or None, optional
            Native menu bar configuration.  Item handlers are automatically
            registered **before** the window is created so menus work from
            the moment the window appears.  Pass a :class:`MenuConfig` with
            handler-bearing items (e.g.
            ``MenuItemConfig(id="save", text="Save", handler=on_save)``).

        Returns
        -------
        NativeWindowHandle or PyWryWidget or InlineWidget
            A NativeWindowHandle (native window) or widget (notebook).
            All implement the BaseWidget protocol.
        """
        # Check if we're in BROWSER mode - use inline server but open in system browser
        is_browser_mode = isinstance(self._mode, BrowserMode)

        # Check if we're in a notebook environment OR explicit BROWSER mode
        if should_use_inline_rendering() or is_browser_mode:
            # Convert HtmlContent to string if needed, preserving inline_css
            if isinstance(content, HtmlContent):
                html_str = content.html
                # Prepend inline CSS as a style tag if present
                if content.inline_css:
                    html_str = (
                        f'<style id="pywry-inline-css">{content.inline_css}</style>{html_str}'
                    )
            else:
                html_str = content

            # Build callbacks dict from CallbackFunc to plain Callable
            plain_callbacks: dict[str, Any] | None = None
            if callbacks:
                plain_callbacks = {
                    event: (cb.func if hasattr(cb, "func") else cb)
                    for event, cb in callbacks.items()
                }

            # For BROWSER mode, use InlineWidget (IFrame + WebSocket)
            if is_browser_mode:
                from . import inline as pywry_inline

                widget = pywry_inline.show(
                    content=html_str,
                    title=title or self._default_config.title,
                    width="100%",
                    height=height or self._default_config.height,
                    theme="dark" if self._theme == ThemeMode.DARK else "light",
                    callbacks=plain_callbacks,
                    include_plotly=include_plotly,
                    include_aggrid=include_aggrid,
                    aggrid_theme=aggrid_theme,
                    toolbars=toolbars,
                    modals=modals,
                    open_browser=True,
                )
                self._register_inline_widget(widget)
                return widget

            # For notebook inline: use PyWryWidget (AnyWidget) for plain HTML
            # Use InlineWidget only for Plotly/AG Grid (they need specialized handling)
            if include_plotly or include_aggrid:
                from . import inline as pywry_inline

                widget = pywry_inline.show(
                    content=html_str,
                    title=title or self._default_config.title,
                    width="100%",
                    height=height or self._default_config.height,
                    theme="dark" if self._theme == ThemeMode.DARK else "light",
                    callbacks=plain_callbacks,
                    include_plotly=include_plotly,
                    include_aggrid=include_aggrid,
                    aggrid_theme=aggrid_theme,
                    toolbars=toolbars,
                    modals=modals,
                    open_browser=False,
                )
                self._register_inline_widget(widget)
                return widget

            # Plain HTML with toolbars: use PyWryWidget (AnyWidget) if available
            # Otherwise fall back to InlineWidget (IFrame)
            from .widget import HAS_ANYWIDGET

            if not HAS_ANYWIDGET:
                # Fall back to InlineWidget when anywidget is not available
                from . import inline as pywry_inline

                widget = pywry_inline.show(
                    content=html_str,
                    title=title or self._default_config.title,
                    width="100%",
                    height=height or self._default_config.height,
                    theme="dark" if self._theme == ThemeMode.DARK else "light",
                    callbacks=plain_callbacks,
                    include_plotly=include_plotly,
                    include_aggrid=include_aggrid,
                    aggrid_theme=aggrid_theme,
                    toolbars=toolbars,
                    modals=modals,
                    open_browser=False,
                )
                self._register_inline_widget(widget)
                return widget

            from .widget import PyWryWidget

            # Handle width - can be int (pixels), string (css value), or None
            widget_width = width
            if widget_width is None:
                widget_width = "100%"
            elif isinstance(widget_width, int):
                widget_width = f"{widget_width}px"
            # else: already a string like "60%" or "500px"

            widget = PyWryWidget.from_html(
                content=html_str,
                callbacks=plain_callbacks,
                theme="dark" if self._theme == ThemeMode.DARK else "light",
                width=widget_width,
                height=f"{height or self._default_config.height}px",
                toolbars=toolbars,
                modals=modals,
            )
            self._register_inline_widget(widget)
            widget.display()  # Auto-display in notebook
            return widget

        # Build config - start from _default_config (preserves builder-level
        # fields like resizable, transparent, user_agent, etc.) and overlay
        # per-show options.
        native_width = width if isinstance(width, int) else self._default_config.width
        config = self._default_config.model_copy(
            update={
                "title": title or self._default_config.title,
                "width": native_width,
                "height": height or self._default_config.height,
                "theme": self._theme,
                "enable_plotly": include_plotly,
                "enable_aggrid": include_aggrid,
                "aggrid_theme": aggrid_theme,
            }
        )

        # Apply per-call initialization_script override if provided
        if initialization_script is not None:
            config.initialization_script = initialization_script

        # Build HtmlContent from string if needed
        html_content = content if isinstance(content, HtmlContent) else HtmlContent(html=content)

        # Auto-promote: if HtmlContent has init_script but WindowConfig has no
        # initialization_script, copy it to the builder-level so it persists
        # across navigations.  The per-content injection still happens via
        # templates.py on every set_content call.
        if html_content.init_script and not config.initialization_script:
            config.initialization_script = html_content.init_script

        # Get window label - for SINGLE_WINDOW mode, use the mode's fixed label
        # For other modes, let the mode's show() generate unique label if not provided
        target_label = (
            self._mode.label
            if hasattr(self._mode, "label")
            else (label or f"pywry-{uuid.uuid4().hex[:8]}")
        )

        # Determine if hot reload should be enabled for this window
        should_watch = watch if watch is not None else html_content.watch
        enable_hot_reload = should_watch and self._hot_reload_manager is not None

        # Build HTML using templates with settings
        html = build_html(
            content=html_content,
            config=config,
            window_label=target_label,
            settings=self._settings,
            loader=self._asset_loader,
            enable_hot_reload=enable_hot_reload,
            toolbars=toolbars,
            modals=modals,
        )

        # Show in window (pass label for multi-window mode)
        # This creates the window resources entry

        # ── Menu: wire handlers BEFORE the window is created ──────────
        _menu_proxy = None
        if menu is not None:
            # Merge menu item handlers into the callbacks dict so they are
            # registered on the window label before the window appears.
            handler_map = menu.collect_handlers()
            if handler_map:
                if callbacks is None:
                    callbacks = {}

                def _menu_dispatcher(
                    data: dict[str, Any],
                    event_type: str,
                    lbl: str,
                ) -> None:
                    item_id = data.get("item_id", "")
                    handler = handler_map.get(item_id)
                    if handler is not None:
                        handler(data, event_type, lbl)

                callbacks["menu:click"] = _menu_dispatcher

        label_result = self._mode.show(config, html, callbacks, target_label)

        # Create the native menu AFTER the window exists (Tauri needs a
        # window to attach to) but handlers were already registered above.
        if menu is not None:
            from .menu_proxy import MenuProxy as _MenuProxy

            menu_proxy = _MenuProxy.from_config(menu)
            menu_proxy.set_as_window_menu(label_result)

        # Store content for refresh support (after window exists)
        lifecycle = get_lifecycle()
        lifecycle.store_content_for_refresh(label_result, html_content, config)

        # Enable hot reload watching if requested
        if enable_hot_reload:
            self._setup_hot_reload_watching(label_result, html_content)

        # Return a NativeWindowHandle for native windows (provides widget-like API)
        return NativeWindowHandle(label_result, self)

    def show_plotly(  # noqa: C901, PLR0912  # pylint: disable=too-many-branches
        self,
        figure: Any,
        title: str | None = None,
        width: int | None = None,
        height: int | None = None,
        callbacks: dict[str, CallbackFunc] | None = None,
        label: str | None = None,
        inline_css: str | None = None,
        on_click: Any = None,
        on_hover: Any = None,
        on_select: Any = None,
        toolbars: list[dict[str, Any] | Toolbar] | None = None,
        modals: list[dict[str, Any] | Modal] | None = None,
        config: Any = None,
    ) -> NativeWindowHandle | BaseWidget:
        """Show a Plotly figure.

        In a notebook environment, this will automatically render the figure
        inline via IFrame with full interactivity.

        Parameters
        ----------
        figure : Any
            Plotly figure object (must have to_html method) or dictionary spec.
        title : str or None, optional
            Window title.
        width : int or None, optional
            Window/IFrame width (overrides default).
        height : int or None, optional
            Window/IFrame height (overrides default).
        callbacks : dict[str, CallbackFunc] or None, optional
            Event callbacks.
        label : str or None, optional
            Window label (for MULTI_WINDOW mode).
        inline_css : str or None, optional
            Custom CSS to inject (e.g., override window background).
        on_click : Callable or None, optional
            Click callback for notebook mode.
        on_hover : Callable or None, optional
            Hover callback for notebook mode.
        on_select : Callable or None, optional
            Selection callback for notebook mode.
        toolbars : list[dict], optional
            List of toolbar configs. Each toolbar has 'position' and 'items' keys.
        modals : list[dict], optional
            List of modal configs. Each modal has 'title' and 'items' keys.
        config : PlotlyConfig or dict, optional
            Plotly.js configuration (modebar, responsive, etc.).

        Returns
        -------
        NativeWindowHandle or BaseWidget
            A NativeWindowHandle (native window) or widget (notebook).
            All implement the BaseWidget protocol.
        """
        # Check if we're in BROWSER mode - use inline server but open in system browser
        is_browser_mode = isinstance(self._mode, BrowserMode)

        # Check if we're in a notebook environment OR explicit BROWSER mode
        if should_use_inline_rendering() or is_browser_mode:
            from . import inline as pywry_inline

            # Map specific callbacks to generic dict for inline
            inline_callbacks = callbacks or {}
            if on_click and "plotly_click" not in inline_callbacks:
                inline_callbacks["plotly_click"] = on_click
            if on_hover and "plotly_hover" not in inline_callbacks:
                inline_callbacks["plotly_hover"] = on_hover
            if on_select and "plotly_selected" not in inline_callbacks:
                inline_callbacks["plotly_selected"] = on_select

            widget = pywry_inline.show_plotly(
                figure=figure,
                title=title or "Plotly Chart",
                width="100%",
                height=height or self._default_config.height,
                theme="dark" if self._theme == ThemeMode.DARK else "light",
                callbacks=inline_callbacks,
                toolbars=toolbars,
                modals=modals,
                config=config,
                open_browser=is_browser_mode,  # Open in browser for BROWSER mode
            )
            self._register_inline_widget(widget)
            return widget

        # Generate unique chart ID
        chart_id = f"chart_{uuid.uuid4().hex}"

        # Convert figure to JSON
        try:
            if isinstance(figure, dict):
                fig_dict = dict(figure)
            elif hasattr(figure, "to_plotly_json"):
                fig_dict = figure.to_plotly_json()
            elif hasattr(figure, "to_dict"):
                fig_dict = figure.to_dict()
            else:
                fig_dict = {"data": [], "layout": {}}
                warn("Figure does not have to_plotly_json or to_dict method")

            if "layout" not in fig_dict:
                fig_dict["layout"] = {}

            # Apply PlotlyConfig if provided
            if config is not None:
                if hasattr(config, "model_dump"):
                    # Pydantic model - convert to dict with camelCase aliases
                    config_dict = config.model_dump(by_alias=True, exclude_none=True)
                elif isinstance(config, dict):
                    config_dict = config
                else:
                    config_dict = {}
                fig_dict["config"] = config_dict

            # Generate HTML containing div + init script
            html_content = build_plotly_init_script(
                figure=fig_dict,
                chart_id=chart_id,
                theme=self._theme,
            )

        except Exception as e:
            warn(f"Failed to convert figure: {e}")
            html_content = f"<pre>Error: {e}</pre>"

        # Wrap in HtmlContent if inline_css provided
        content: str | HtmlContent
        if inline_css:
            content = HtmlContent(html=html_content, inline_css=inline_css)
        else:
            content = html_content

        return self.show(
            content=content,
            title=title or "Plotly Chart",
            width=width,
            height=height,
            callbacks=callbacks,
            include_plotly=True,
            label=label,
            toolbars=toolbars,
            modals=modals,
        )

    def show_dataframe(  # pylint: disable=too-many-branches
        self,
        data: Any,
        title: str | None = None,
        width: int | None = None,
        height: int | None = None,
        callbacks: dict[str, CallbackFunc] | None = None,
        label: str | None = None,
        column_defs: list[dict[str, Any]] | None = None,
        aggrid_theme: Literal["quartz", "alpine", "balham", "material"] = "alpine",
        grid_options: dict[str, Any] | None = None,
        toolbars: list[dict[str, Any] | Toolbar] | None = None,
        modals: list[dict[str, Any] | Modal] | None = None,
        inline_css: str | None = None,
        on_cell_click: Any = None,
        on_row_selected: Any = None,
        server_side: bool = False,
    ) -> NativeWindowHandle | BaseWidget:
        """Show a DataFrame in an AG Grid table.

        In a notebook environment, this will automatically render the table
        inline via IFrame with full interactivity.

        Parameters
        ----------
        data : Any
            DataFrame or list of dicts to display.
        title : str or None, optional
            Window title.
        width : int or None, optional
            Window/IFrame width (overrides default).
        height : int or None, optional
            Window/IFrame height (overrides default).
        callbacks : dict[str, CallbackFunc] or None, optional
            Event callbacks.
        label : str or None, optional
            Window label (for MULTI_WINDOW mode).
        column_defs : list[dict[str, Any]] or None, optional
            AG Grid column definitions.
        aggrid_theme : {'quartz', 'alpine', 'balham', 'material'}, optional
            AG Grid theme.
        grid_options : dict[str, Any] or None, optional
            Custom AG Grid options to merge with defaults.
        toolbars : list[dict], optional
            List of toolbar configs. Each toolbar has 'position' and 'items' keys.
        inline_css : str or None, optional
            Custom CSS to inject (e.g., override window background).
        on_cell_click : Callable or None, optional
            Cell click callback for notebook mode.
        on_row_selected : Callable or None, optional
            Row selection callback for notebook mode.
        server_side : bool, optional
            Enable server-side mode where data stays in Python memory.
            Useful for very large datasets (>100K rows) where you want
            to filter/sort the full data. Data is fetched via IPC on
            demand. Default is False.

        Returns
        -------
        NativeWindowHandle or BaseWidget
            A NativeWindowHandle (native window) or widget (notebook).
            All implement the BaseWidget protocol.
        """
        # Check if we're in BROWSER mode - use inline server but open in system browser
        is_browser_mode = isinstance(self._mode, BrowserMode)

        # Check if we're in a notebook environment OR explicit BROWSER mode
        if should_use_inline_rendering() or is_browser_mode:
            from . import inline as pywry_inline

            # Map specific callbacks to generic dict for inline
            inline_callbacks = callbacks or {}
            if on_cell_click and "cell_click" not in inline_callbacks:
                inline_callbacks["cell_click"] = on_cell_click
            if on_row_selected and "row_selected" not in inline_callbacks:
                inline_callbacks["row_selected"] = on_row_selected

            widget = pywry_inline.show_dataframe(
                df=data,
                title=title or "Data Table",
                width="100%",
                height=height or self._default_config.height,
                theme="dark" if self._theme == ThemeMode.DARK else "light",
                aggrid_theme=aggrid_theme,
                toolbars=toolbars,
                modals=modals,
                callbacks=inline_callbacks,
                open_browser=is_browser_mode,  # Open in browser for BROWSER mode
            )
            self._register_inline_widget(widget)
            return widget

        # Use unified grid config builder for column defs with type detection
        from .grid import build_column_defs, normalize_data

        # Normalize input data (handles DataFrame, dict, list)
        grid_data = normalize_data(data)
        row_data = grid_data.row_data

        # Build column defs with type detection and formatters
        if column_defs is None:
            column_defs = build_column_defs(
                grid_data.columns,
                column_types=grid_data.column_types,
            )
        else:
            # Convert ColDef objects to dicts for JSON serialization
            column_defs = [c.to_dict() if hasattr(c, "to_dict") else c for c in column_defs]

        # Build the AG Grid HTML
        # Theme class automatically includes -dark suffix for dark mode
        if self._theme == ThemeMode.DARK:
            theme_class = f"ag-theme-{aggrid_theme}-dark"
        else:
            theme_class = f"ag-theme-{aggrid_theme}"

        # Serialize user grid options for merging in JS
        user_options_json = json.dumps(grid_options or {})

        # Generate unique grid ID for this instance
        grid_id = f"app-grid-{uuid.uuid4().hex[:8]}"
        row_count = len(row_data)

        if server_side:
            # Server-side mode: data stays in Python, JS gets it via IPC
            # Useful for very large datasets where you want full filtering
            info(f"Server-side mode for {row_count:,} rows (grid: {grid_id})")

            server_config = {
                "totalRows": row_count,
                "blockSize": 500,
            }

            grid_html = f"""
        <div id="myGrid" class="pywry-grid {theme_class}"></div>
        <script>
            (function() {{
                function initGrid() {{
                    if (typeof agGrid === 'undefined') {{
                        setTimeout(initGrid, 50);
                        return;
                    }}

                    var gridConfig = {{
                        columnDefs: {json.dumps(column_defs or [])},
                        serverSide: {json.dumps(server_config)},
                        domLayout: 'normal'
                    }};

                    var userOptions = {user_options_json};
                    if (userOptions) {{
                        Object.assign(gridConfig, userOptions);
                    }}

                    const gridDiv = document.querySelector('#myGrid');
                    if (gridDiv) {{
                        const gridId = '{grid_id}';

                        var gridOptions = window.PYWRY_AGGRID_BUILD_OPTIONS
                            ? window.PYWRY_AGGRID_BUILD_OPTIONS(gridConfig, gridId)
                            : gridConfig;

                        window.__PYWRY_GRID_API__ = agGrid.createGrid(gridDiv, gridOptions);

                        if (window.PYWRY_AGGRID_REGISTER_LISTENERS) {{
                            window.PYWRY_AGGRID_REGISTER_LISTENERS(window.__PYWRY_GRID_API__, gridDiv, gridId);
                        }}
                    }}
                }}
                initGrid();
            }})();
        </script>
        """
            # Set up IPC handler for data requests
            self._setup_server_side_handler(grid_id, row_data, label)
        else:
            # Client-side mode: send all data to frontend
            # AG Grid's DOM virtualization handles large datasets efficiently
            # JS-side truncates if > 100K rows to protect browser memory
            grid_html = f"""
        <div id="myGrid" class="pywry-grid {theme_class}"></div>
        <script>
            (function() {{
                function initGrid() {{
                    if (typeof agGrid === 'undefined') {{
                        setTimeout(initGrid, 50);
                        return;
                    }}

                    var gridConfig = {{
                        columnDefs: {json.dumps(column_defs or [])},
                        rowData: {json.dumps(row_data)},
                        domLayout: 'normal'
                    }};

                    var userOptions = {user_options_json};
                    if (userOptions) {{
                        Object.assign(gridConfig, userOptions);
                        if (!userOptions.columnDefs) gridConfig.columnDefs = {json.dumps(column_defs or [])};
                        if (!userOptions.rowData) gridConfig.rowData = {json.dumps(row_data)};
                    }}

                    const gridDiv = document.querySelector('#myGrid');
                    if (gridDiv) {{
                        const gridId = '{grid_id}';

                        var gridOptions = window.PYWRY_AGGRID_BUILD_OPTIONS
                            ? window.PYWRY_AGGRID_BUILD_OPTIONS(gridConfig, gridId)
                            : gridConfig;

                        window.__PYWRY_GRID_API__ = agGrid.createGrid(gridDiv, gridOptions);

                        if (window.PYWRY_AGGRID_REGISTER_LISTENERS) {{
                            window.PYWRY_AGGRID_REGISTER_LISTENERS(window.__PYWRY_GRID_API__, gridDiv, gridId);
                        }}
                    }}
                }}
                initGrid();
            }})();
        </script>
        """

        # Wrap in HtmlContent if inline_css provided
        content = HtmlContent(html=grid_html, inline_css=inline_css) if inline_css else grid_html

        return self.show(
            content=content,
            title=title or "Data Table",
            width=width,
            height=height,
            callbacks=callbacks,
            include_aggrid=True,
            aggrid_theme=aggrid_theme,
            label=label,
            toolbars=toolbars,
            modals=modals,
        )

    def emit(self, event_type: str, data: dict[str, Any], label: str | None = None) -> None:
        """Emit an event to the JavaScript side.

        Parameters
        ----------
        event_type : str
            Event name.
        data : dict
            Event data.
        label : str, optional
            Window label. If None, targets all active windows.
        """
        labels = [label] if label else self._mode.get_labels()

        # Also include inline (notebook) widgets when targeting all
        if not label and self._inline_widgets:
            labels = list(set(labels) | set(self._inline_widgets.keys()))

        for lbl in labels:
            self.send_event(event_type, data, label=lbl)

    def alert(
        self,
        message: str,
        alert_type: Literal["info", "success", "warning", "error", "confirm"] = "info",
        title: str | None = None,
        duration: int | None = None,
        callback_event: str | None = None,
        position: Literal["top-right", "bottom-right", "bottom-left", "top-left"] = "top-right",
        label: str | None = None,
    ) -> None:
        """Show a toast notification.

        Parameters
        ----------
        message : str
            The message to display.
        alert_type : str
            Alert type: 'info', 'success', 'warning', 'error', or 'confirm'.
        title : str, optional
            Optional title for the toast.
        duration : int, optional
            Auto-dismiss duration in ms. Defaults based on type.
        callback_event : str, optional
            Event name to emit when confirm dialog is answered.
        position : str
            Toast position: 'top-right', 'top-left', 'bottom-right', 'bottom-left'.
        label : str, optional
            Window label. If None, targets all active windows.
        """
        payload = AlertPayload(
            message=message,
            type=alert_type,
            title=title,
            duration=duration,
            callback_event=callback_event,
            position=position,
        )
        self.emit("pywry:alert", payload.model_dump(exclude_none=True), label=label)

    def on(
        self,
        event_type: str,
        handler: CallbackFunc,
        label: str | None = None,
        widget_id: str | None = None,
    ) -> bool:
        """Register an event handler.

        Parameters
        ----------
        event_type : str
            Event type (namespace:event-name or * for wildcard).
        handler : CallbackFunc
            Callback function.
        label : str, optional
            Window label. If None, registers on all active windows.
        widget_id : str, optional
            Widget ID to target specific component events.

        Returns
        -------
        bool
            True if registered successfully.
        """
        registry = get_registry()
        # If widget_id provided, compound the event type
        if widget_id and ":" not in event_type:
            # e.g., "plotly_click" -> "plotly_click:my_chart_id"
            event_type = f"{event_type}:{widget_id}"

        labels = self._mode.get_labels()

        if label:
            labels = [label]
        elif not labels:
            # No windows yet - register on "main" which will be created later
            labels = ["main"]

        success = True
        for lbl in labels:
            if not registry.register(lbl, event_type, handler):
                success = False

        return success

    # ------------------------------------------------------------------
    # Custom IPC commands (callable from JS via pyInvoke)
    # ------------------------------------------------------------------

    _NATIVE_MODES = frozenset(
        {
            WindowMode.NEW_WINDOW,
            WindowMode.SINGLE_WINDOW,
            WindowMode.MULTI_WINDOW,
        }
    )

    def _require_native_mode(self, feature: str) -> None:
        """Raise if the app is not in a native window mode.

        Parameters
        ----------
        feature : str
            Human-readable feature name for the error message
            (e.g. ``"@app.command()"`` or ``"create_menu()"``).

        Raises
        ------
        RuntimeError
            If the current mode is BROWSER or NOTEBOOK where the Tauri
            webview (and therefore native menus, trays, and pyInvoke)
            is not available.
        """
        if self._mode_enum not in self._NATIVE_MODES:
            msg = (
                f"{feature} requires a native window mode "
                f"(NEW_WINDOW, SINGLE_WINDOW, or MULTI_WINDOW), "
                f"but app is in {self._mode_enum.value!r} mode. "
                f"Native menus, trays, and custom commands use the Tauri "
                f"webview which is only available in native window modes."
            )
            raise RuntimeError(msg)

    def command(
        self,
        name: str | None = None,
    ) -> Any:
        """Register a custom IPC command callable from JavaScript.

        The decorated function becomes available to the front-end via
        ``window.__TAURI__.pytauri.pyInvoke('name', body)``.

        Must be called **before** ``show()`` / ``start()`` so the command
        is registered in the subprocess before the Tauri app builder runs.

        Parameters
        ----------
        name : str or None
            Command name exposed to JS.  Defaults to the function's
            ``__name__``.

        Returns
        -------
        callable
            Decorator that registers the handler.

        Raises
        ------
        TypeError
            If the handler is not callable.
        RuntimeError
            If the app is in a non-native mode (BROWSER, NOTEBOOK) where
            ``pyInvoke`` is not available, or if the subprocess has already
            started.

        Examples
        --------
        >>> app = PyWry()
        >>>
        >>> @app.command()
        ... def get_user(data: dict) -> dict:
        ...     return {"name": "Alice", "id": 42}
        >>>
        >>> @app.command("fetch_data")
        ... async def _fetch(data: dict) -> dict:
        ...     rows = await load_from_db(data["query"])
        ...     return {"rows": rows}
        """
        from . import runtime
        from .notebook import should_use_inline_rendering as _should_use_inline

        def decorator(func: Any) -> Any:
            if not callable(func):
                msg = f"command handler must be callable, got {type(func).__name__}"
                raise TypeError(msg)

            # Validate window mode — pyInvoke only exists in native windows
            self._require_native_mode("@app.command()")

            # Warn if running inside a notebook — show() will silently
            # switch to inline rendering where pyInvoke doesn't exist.
            if _should_use_inline():
                warn(
                    "@app.command() registered in a notebook environment. "
                    "Custom commands will only work if show() opens a "
                    "native window (set PYWRY_FORCE_NATIVE=1 to override "
                    "inline rendering)."
                )

            # Must register BEFORE subprocess starts
            if runtime.is_running():
                msg = (
                    "@app.command() must be called before show(). "
                    "The pytauri subprocess is already running and "
                    "cannot accept new command registrations."
                )
                raise RuntimeError(msg)

            cmd_name = name or func.__name__
            runtime.register_custom_command(cmd_name, func)
            debug(f"Registered custom command: {cmd_name}")
            return func

        return decorator

    def on_grid(
        self,
        event_type: str,
        handler: CallbackFunc,
        label: str | None = None,
        grid_id: str = "*",
    ) -> bool:
        """Register an event handler for grid events.

        Convenience method that filters events to only AG Grid widgets.

        Parameters
        ----------
        event_type : str
            Event type (e.g., "grid:cell-click", "cell_click").
        handler : CallbackFunc
            Callback function.
        label : str, optional
            Window label. If None, registers on all active windows.
        grid_id : str, optional
            Grid ID to target specific grid instance (default "*" for all).

        Returns
        -------
        bool
            True if registered successfully.
        """
        registry = get_registry()
        labels = self._mode.get_labels()
        if label:
            labels = [label]
        elif not labels:
            labels = ["main"]

        success = True
        for lbl in labels:
            if not registry.register(
                lbl, event_type, handler, widget_type="grid", widget_id=grid_id
            ):
                success = False
        return success

    def on_chart(
        self,
        event_type: str,
        handler: CallbackFunc,
        label: str | None = None,
        chart_id: str = "*",
    ) -> bool:
        """Register an event handler for chart (Plotly) events.

        Convenience method that filters events to only Plotly chart widgets.

        Parameters
        ----------
        event_type : str
            Event type (e.g., "plotly:click", "plotly:hover").
        handler : CallbackFunc
            Callback function.
        label : str, optional
            Window label. If None, registers on all active windows.
        chart_id : str, optional
            Chart ID to target specific chart instance (default "*" for all).

        Returns
        -------
        bool
            True if registered successfully.
        """
        registry = get_registry()
        labels = self._mode.get_labels()
        if label:
            labels = [label]
        elif not labels:
            labels = ["main"]

        success = True
        for lbl in labels:
            if not registry.register(
                lbl, event_type, handler, widget_type="chart", widget_id=chart_id
            ):
                success = False
        return success

    def on_toolbar(
        self,
        event_type: str,
        handler: CallbackFunc,
        label: str | None = None,
        toolbar_id: str = "*",
    ) -> bool:
        """Register an event handler for toolbar events.

        Convenience method that filters events to only toolbar widgets.

        Parameters
        ----------
        event_type : str
            Event type (e.g., "toolbar:change", custom button events).
        handler : CallbackFunc
            Callback function.
        label : str, optional
            Window label. If None, registers on all active windows.
        toolbar_id : str, optional
            Toolbar ID to target specific toolbar (default "*" for all).

        Returns
        -------
        bool
            True if registered successfully.
        """
        registry = get_registry()
        labels = self._mode.get_labels()
        if label:
            labels = [label]
        elif not labels:
            labels = ["main"]

        success = True
        for lbl in labels:
            if not registry.register(
                lbl, event_type, handler, widget_type="toolbar", widget_id=toolbar_id
            ):
                success = False
        return success

    def on_html(
        self,
        event_type: str,
        handler: CallbackFunc,
        label: str | None = None,
        element_id: str = "*",
    ) -> bool:
        """Register an event handler for HTML element events.

        Convenience method that filters events to HTML content.

        Parameters
        ----------
        event_type : str
            Event type (e.g., custom events from HTML elements).
        handler : CallbackFunc
            Callback function.
        label : str, optional
            Window label. If None, registers on all active windows.
        element_id : str, optional
            HTML element ID to target specific element (default "*" for all).

        Returns
        -------
        bool
            True if registered successfully.
        """
        registry = get_registry()
        labels = self._mode.get_labels()
        if label:
            labels = [label]
        elif not labels:
            labels = ["main"]

        success = True
        for lbl in labels:
            if not registry.register(
                lbl, event_type, handler, widget_type="html", widget_id=element_id
            ):
                success = False
        return success

    def on_window(
        self,
        event_type: str,
        handler: CallbackFunc,
        label: str | None = None,
    ) -> bool:
        """Register an event handler for window-level events.

        Convenience method that filters events to window lifecycle events.

        Parameters
        ----------
        event_type : str
            Event type (e.g., "window:close", "window:resize").
        handler : CallbackFunc
            Callback function.
        label : str, optional
            Window label. If None, registers on all active windows.

        Returns
        -------
        bool
            True if registered successfully.
        """
        registry = get_registry()
        labels = self._mode.get_labels()
        if label:
            labels = [label]
        elif not labels:
            labels = ["main"]

        success = True
        for lbl in labels:
            if not registry.register(lbl, event_type, handler, widget_type="window", widget_id="*"):
                success = False
        return success

    def send_event(
        self,
        event_type: str,
        data: Any,
        label: str | None = None,
    ) -> bool:
        """Send an event to window(s).

        Parameters
        ----------
        event_type : str
            Event type (namespace:event-name).
        data : Any
            Event data.
        label : str or None, optional
            Specific window label (None = all windows).

        Returns
        -------
        bool
            True if event was sent to at least one window.
        """
        if label:
            # Check inline widgets first (notebook/anywidget mode)
            inline_widget = self._inline_widgets.get(label)
            if inline_widget is not None:
                inline_widget.emit(event_type, data)
                return True
            return self._mode.send_event(label, event_type, data)

        # Send to all windows (native + inline)
        labels = list(self._mode.get_labels())
        # Include inline widgets when targeting all
        inline_labels = set(self._inline_widgets.keys()) - set(labels)
        all_labels = labels + list(inline_labels)

        if not all_labels:
            return False

        success = False
        for lbl in all_labels:
            inline_widget = self._inline_widgets.get(lbl)
            if inline_widget is not None:
                inline_widget.emit(event_type, data)
                success = True
            elif self._mode.send_event(lbl, event_type, data):
                success = True

        return success

    def update_content(self, html: str, label: str | None = None) -> bool:
        """Update window content.

        Parameters
        ----------
        html : str
            New HTML content.
        label : str or None, optional
            Window label (required for NEW_WINDOW/MULTI_WINDOW).

        Returns
        -------
        bool
            True if updated successfully.
        """
        theme_str = "dark" if self._theme.value in ("dark", "system") else "light"

        if label:
            return self._mode.update_content(label, html, theme_str)

        # For SINGLE_WINDOW mode, update the main window
        labels = self._mode.get_labels()
        if labels:
            return self._mode.update_content(labels[0], html, theme_str)

        return False

    def eval_js(self, script: str, label: str | None = None) -> bool:
        """Evaluate JavaScript in a window without replacing content.

        This is useful for DOM queries and dynamic updates that
        should not replace the window content.

        Parameters
        ----------
        script : str
            JavaScript code to execute.
        label : str or None, optional
            Window label (None = main window in SINGLE_WINDOW mode).

        Returns
        -------
        bool
            True if command was sent.
        """
        from . import runtime

        if label is None:
            labels = self._mode.get_labels()
            if not labels:
                return False
            label = labels[0]

        return runtime.eval_js(label, script)

    def show_window(self, label: str) -> bool:
        """Show a hidden window.

        Parameters
        ----------
        label : str
            Window label to show.

        Returns
        -------
        bool
            True if window was shown.
        """
        return self._mode.show_window(label)

    def hide_window(self, label: str) -> bool:
        """Hide a window (keeps it alive, just not visible).

        Parameters
        ----------
        label : str
            Window label to hide.

        Returns
        -------
        bool
            True if window was hidden.
        """
        return self._mode.hide_window(label)

    def close(self, label: str | None = None) -> bool:
        """Close window(s).

        Parameters
        ----------
        label : str or None, optional
            Window label to close (None = close all).

        Returns
        -------
        bool
            True if any window was closed.
        """
        if label:
            return self._mode.close(label)

        return self._mode.close_all() > 0

    def get_labels(self) -> list[str]:
        """Get all active window labels.

        Returns
        -------
        list of str
            List of window labels.
        """
        return self._mode.get_labels()

    def is_open(self, label: str | None = None) -> bool:
        """Check if window(s) are open.

        Parameters
        ----------
        label : str or None, optional
            Specific window to check (None = any window).

        Returns
        -------
        bool
            True if window(s) are open.
        """
        if label:
            return self._mode.is_open(label)
        return len(self._mode.get_labels()) > 0

    def refresh(self, label: str | None = None) -> bool:
        """Refresh window content.

        Triggers a full page refresh while preserving scroll position.

        Parameters
        ----------
        label : str or None, optional
            Specific window to refresh (None = all windows).

        Returns
        -------
        bool
            True if at least one window was refreshed.
        """
        if label:
            return runtime_refresh_window(label)

        # Refresh all windows
        labels = self._mode.get_labels()
        if not labels:
            return False

        success = False
        for lbl in labels:
            if runtime_refresh_window(lbl):
                success = True

        return success

    def refresh_css(self, label: str | None = None) -> bool:
        """Hot-reload CSS files for window(s).

        Re-injects CSS files without page refresh.

        Parameters
        ----------
        label : str or None, optional
            Specific window to refresh CSS (None = all windows).

        Returns
        -------
        bool
            True if at least one window's CSS was refreshed.
        """
        if not self._hot_reload_manager:
            warn("Hot reload not enabled. Initialize PyWry with hot_reload=True")
            return False

        if label:
            return self._hot_reload_manager.reload_css(label)

        # Refresh CSS for all windows
        labels = self._mode.get_labels()
        if not labels:
            return False

        success = False
        for lbl in labels:
            if self._hot_reload_manager.reload_css(lbl):
                success = True

        return success

    def enable_hot_reload(self) -> None:
        """Enable hot reload if not already enabled."""
        if self._hot_reload_manager is None:
            self._hot_reload_manager = HotReloadManager(
                settings=self._settings.hot_reload,
                asset_loader=self._asset_loader,
            )
            self._hot_reload_manager.start()
            info("Hot reload enabled")

    def disable_hot_reload(self) -> None:
        """Disable hot reload and stop file watching."""
        if self._hot_reload_manager:
            self._hot_reload_manager.stop()
            self._hot_reload_manager = None
            info("Hot reload disabled")

    # Storage for server-side grid data
    _grid_data: dict[str, list[dict[str, Any]]]

    def _setup_server_side_handler(
        self,
        grid_id: str,
        row_data: list[dict[str, Any]],
        label: str | None,
    ) -> None:
        """Set up IPC handler for server-side grid data requests.

        This keeps the data in Python and sends slices on demand.

        Parameters
        ----------
        grid_id : str
            Unique grid identifier.
        row_data : list[dict[str, Any]]
            The full dataset (kept in Python memory).
        label : str or None
            Window label to register handler on.
        """
        # Initialize storage if needed
        if not hasattr(self, "_grid_data"):
            self._grid_data = {}

        # Store the data
        self._grid_data[grid_id] = row_data

        def handle_page_request(event_data: dict[str, Any]) -> None:
            """Handle grid:request-page events from frontend."""
            # Only respond to requests for this grid
            if event_data.get("gridId") != grid_id:
                return

            request_id = event_data.get("requestId", "")
            start_row = event_data.get("startRow", 0)
            end_row = event_data.get("endRow", 100)
            sort_model = event_data.get("sortModel", [])
            filter_model = event_data.get("filterModel", {})

            debug(
                f"Grid {grid_id}: page request {request_id} "
                f"rows {start_row}-{end_row}, "
                f"sort={sort_model}, filter={filter_model}"
            )

            # Get the full dataset
            data = self._grid_data.get(grid_id, [])

            # Apply filtering (simple contains/equals logic)
            filtered_data = self._apply_grid_filter(data, filter_model)

            # Apply sorting
            sorted_data = self._apply_grid_sort(filtered_data, sort_model)

            # Get the requested slice
            total_rows = len(sorted_data)
            rows = sorted_data[start_row:end_row]
            is_last_page = end_row >= total_rows

            # Add row IDs for selection persistence
            for i, row in enumerate(rows):
                row["__rowId"] = start_row + i

            # Send response back to frontend
            self.send_event(
                "grid:page-response",
                {
                    "gridId": grid_id,
                    "requestId": request_id,
                    "rows": rows,
                    "totalRows": total_rows,
                    "isLastPage": is_last_page,
                },
                label=label,
            )

        # Register the handler
        target_label = label or (self._mode.get_labels() or ["main"])[0]
        registry = get_registry()
        registry.register(target_label, "grid:request-page", handle_page_request)

        debug(f"Registered server-side handler for grid {grid_id} on label {target_label}")

    def _apply_grid_filter(
        self,
        data: list[dict[str, Any]],
        filter_model: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Apply AG Grid filter model to data.

        Parameters
        ----------
        data : list[dict[str, Any]]
            Data to filter.
        filter_model : dict[str, Any]
            AG Grid filter model.

        Returns
        -------
        list[dict[str, Any]]
            Filtered data.
        """
        if not filter_model:
            return data

        result = data
        for field, filter_def in filter_model.items():
            filter_type = filter_def.get("filterType", "text")
            filter_op = filter_def.get("type", "contains")
            filter_value = filter_def.get("filter")

            if filter_value is None:
                continue

            result = [
                row
                for row in result
                if self._row_matches_filter(row, field, filter_type, filter_op, filter_value)
            ]

        return result

    def _row_matches_filter(
        self,
        row: dict[str, Any],
        field: str,
        filter_type: str,
        filter_op: str,
        filter_value: Any,
    ) -> bool:
        """Check if a row matches a single filter condition."""
        val = row.get(field)
        if val is None:
            return False

        if filter_type == "text":
            return self._text_filter_match(val, filter_op, filter_value)

        if filter_type == "number":
            return self._number_filter_match(val, filter_op, filter_value)

        return True

    def _text_filter_match(  # noqa: PLR0911  # pylint: disable=too-many-return-statements
        self, val: Any, filter_op: str, filter_value: Any
    ) -> bool:
        """Check if value matches text filter."""
        val_str = str(val).lower()
        filter_str = str(filter_value).lower()

        if filter_op == "contains":
            return filter_str in val_str
        if filter_op == "equals":
            return val_str == filter_str
        if filter_op == "startsWith":
            return val_str.startswith(filter_str)
        if filter_op == "endsWith":
            return val_str.endswith(filter_str)
        if filter_op == "notContains":
            return filter_str not in val_str
        if filter_op == "notEqual":
            return val_str != filter_str
        return filter_str in val_str

    def _number_filter_match(  # noqa: PLR0911  # pylint: disable=too-many-return-statements
        self, val: Any, filter_op: str, filter_value: Any
    ) -> bool:
        """Check if value matches number filter."""
        try:
            num_val = float(val)
            num_filter = float(filter_value)
        except (ValueError, TypeError):
            return False

        if filter_op == "equals":
            return num_val == num_filter
        if filter_op == "notEqual":
            return num_val != num_filter
        if filter_op == "lessThan":
            return num_val < num_filter
        if filter_op == "lessThanOrEqual":
            return num_val <= num_filter
        if filter_op == "greaterThan":
            return num_val > num_filter
        if filter_op == "greaterThanOrEqual":
            return num_val >= num_filter
        return True

    def _apply_grid_sort(
        self,
        data: list[dict[str, Any]],
        sort_model: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Apply AG Grid sort model to data.

        Parameters
        ----------
        data : list[dict[str, Any]]
            Data to sort.
        sort_model : list[dict[str, Any]]
            AG Grid sort model.

        Returns
        -------
        list[dict[str, Any]]
            Sorted data.
        """
        if not sort_model:
            return data

        # Apply sorts in reverse order (last sort is primary)
        result = list(data)
        for sort_item in reversed(sort_model):
            col_id = sort_item.get("colId")
            sort_dir = sort_item.get("sort", "asc")

            if not col_id:
                continue

            # Use functools.partial or lambda with default arg to capture col_id
            result.sort(
                key=lambda row, c=col_id: self._get_sort_key(row, c),  # type: ignore[misc]
                reverse=(sort_dir == "desc"),
            )

        return result

    def _get_sort_key(self, row: dict[str, Any], col_id: str) -> tuple[int, Any]:
        """Get sort key for a row value."""
        val = row.get(col_id)
        if val is None:
            return (1, "")
        try:
            return (0, float(val))
        except (ValueError, TypeError):
            return (0, str(val).lower())

    def _get_plotly_js(self) -> str:
        """Get Plotly.js library (lazy loaded)."""
        if self._plotly_js is None:
            self._plotly_js = get_plotly_js()
        return self._plotly_js

    def _get_aggrid_js(self) -> str:
        """Get AG Grid JS library (lazy loaded)."""
        if self._aggrid_js is None:
            self._aggrid_js = get_aggrid_js()
        return self._aggrid_js

    def _get_aggrid_css(self) -> str:
        """Get AG Grid CSS for current theme (lazy loaded)."""
        theme_key = ("alpine", self._theme)
        if theme_key not in self._aggrid_css:
            self._aggrid_css[theme_key] = get_aggrid_css("alpine", self._theme)
        return self._aggrid_css[theme_key]

    def get_icon(self) -> bytes:
        """Get the OpenBB icon.

        Returns
        -------
        bytes
            Icon bytes.
        """
        return get_openbb_icon()

    def get_lifecycle(self) -> WindowLifecycle:
        """Get the window lifecycle manager.

        Returns
        -------
        WindowLifecycle
            WindowLifecycle instance.
        """
        return get_lifecycle()

    def destroy(self) -> None:
        """Destroy all resources and close all windows."""
        info("Destroying PyWry")

        # Remove ALL tray icons — both those tracked by the app
        # (app.create_tray) and those created directly via
        # TrayProxy.from_config() / TrayProxy.create().
        from .tray_proxy import TrayProxy

        TrayProxy.remove_all()
        self._trays.clear()

        # Stop hot reload if active
        if self._hot_reload_manager:
            self._hot_reload_manager.stop()
            self._hot_reload_manager = None

        self._mode.close_all()
        get_lifecycle().destroy_all()
        self._plotly_js = None
        self._aggrid_js = None
        self._aggrid_css.clear()
        self._asset_loader.clear_cache()

    def block(self, label: str | None = None) -> None:
        """Block until window(s) are closed or KeyboardInterrupt.

        This is the recommended way to keep your script running while
        windows are open. Works for all modes:

        - Native modes (NEW_WINDOW, SINGLE_WINDOW, MULTI_WINDOW): Waits for
          windows to close via the Tauri event loop.
        - BROWSER mode: Delegates to pywry.inline.block() to wait for
          browser tabs to disconnect.

        Parameters
        ----------
        label : str or None, optional
            Specific window label to wait for. If None, waits for all windows.

        Examples
        --------
        >>> app = PyWry()
        >>> label = app.show("<h1>Hello</h1>")
        >>> app.block()  # Wait until all windows are closed

        >>> # Or wait for a specific window
        >>> app.block(label)  # Wait until this specific window is closed
        """
        if isinstance(self._mode, BrowserMode):
            # Browser mode uses inline server
            from . import inline as pywry_inline

            pywry_inline.block()
        else:
            # Native mode - wait for window(s) to close
            try:
                if label:
                    # Wait for specific window to close
                    while label in self._mode.get_labels():
                        import time

                        time.sleep(0.1)
                else:
                    # Wait for all windows to close
                    while self._mode.get_labels():
                        import time

                        time.sleep(0.1)
            except KeyboardInterrupt:
                info("Interrupted, closing windows...")
                self.destroy()
