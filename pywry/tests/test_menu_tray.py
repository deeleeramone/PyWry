"""Unit tests for MenuProxy and TrayProxy.

These tests mock the IPC layer and verify correct command serialization
without requiring a running pytauri subprocess.
"""

# pylint: disable=missing-function-docstring

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from pywry.types import (
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


# Shared no-op handler for tests that don't care about the callback.
def _noop(*_a: Any, **_kw: Any) -> None:
    pass


# ── Menu type serialization tests ────────────────────────────────────


class TestMenuItemConfig:
    """Test MenuItemConfig serialization."""

    def test_basic_item(self) -> None:
        item = MenuItemConfig(id="save", text="Save", handler=_noop)
        d = item.to_dict()
        assert d["kind"] == "item"
        assert d["id"] == "save"
        assert d["text"] == "Save"
        assert d["enabled"] is True
        assert "accelerator" not in d

    def test_item_with_accelerator(self) -> None:
        item = MenuItemConfig(id="save", text="Save", handler=_noop, accelerator="CmdOrCtrl+S")
        d = item.to_dict()
        assert d["accelerator"] == "CmdOrCtrl+S"

    def test_disabled_item(self) -> None:
        item = MenuItemConfig(id="x", text="X", handler=_noop, enabled=False)
        assert item.to_dict()["enabled"] is False

    def test_handler_required(self) -> None:
        with pytest.raises(TypeError, match="requires a handler"):
            MenuItemConfig(id="x", text="X")

    def test_handler_stored(self) -> None:
        item = MenuItemConfig(id="save", text="Save", handler=_noop)
        assert item.handler is _noop


class TestCheckMenuItemConfig:
    """Test CheckMenuItemConfig serialization."""

    def test_unchecked(self) -> None:
        item = CheckMenuItemConfig(id="bold", text="Bold", handler=_noop)
        d = item.to_dict()
        assert d["kind"] == "check"
        assert d["checked"] is False

    def test_checked(self) -> None:
        item = CheckMenuItemConfig(id="bold", text="Bold", handler=_noop, checked=True)
        assert item.to_dict()["checked"] is True

    def test_handler_required(self) -> None:
        with pytest.raises(TypeError, match="requires a handler"):
            CheckMenuItemConfig(id="bold", text="Bold")


class TestIconMenuItemConfig:
    """Test IconMenuItemConfig serialization."""

    def test_no_icon(self) -> None:
        item = IconMenuItemConfig(id="doc", text="Document", handler=_noop)
        d = item.to_dict()
        assert d["kind"] == "icon"
        assert "icon" not in d

    def test_with_rgba_icon(self) -> None:
        icon_data = b"\xff\x00\x00\xff" * 16  # 4x4 red RGBA
        item = IconMenuItemConfig(
            id="doc", text="Document", handler=_noop, icon=icon_data, icon_width=4, icon_height=4
        )
        d = item.to_dict()
        assert "icon" in d
        assert d["icon_width"] == 4
        assert d["icon_height"] == 4

    def test_with_native_icon(self) -> None:
        item = IconMenuItemConfig(id="doc", text="Document", handler=_noop, native_icon="Folder")
        d = item.to_dict()
        assert d["native_icon"] == "Folder"

    def test_handler_required(self) -> None:
        with pytest.raises(TypeError, match="requires a handler"):
            IconMenuItemConfig(id="doc", text="Document")


class TestPredefinedMenuItemConfig:
    """Test PredefinedMenuItemConfig serialization."""

    def test_separator(self) -> None:
        item = PredefinedMenuItemConfig(kind_name=PredefinedMenuItemKind.SEPARATOR)
        d = item.to_dict()
        assert d["kind"] == "predefined"
        assert d["kind_name"] == "separator"
        assert "text" not in d

    def test_with_text(self) -> None:
        item = PredefinedMenuItemConfig(kind_name=PredefinedMenuItemKind.ABOUT, text="About MyApp")
        d = item.to_dict()
        assert d["text"] == "About MyApp"


class TestSubmenuConfig:
    """Test SubmenuConfig serialization."""

    def test_empty_submenu(self) -> None:
        sub = SubmenuConfig(id="file", text="File")
        d = sub.to_dict()
        assert d["kind"] == "submenu"
        assert d["id"] == "file"
        assert "items" not in d

    def test_nested_items(self) -> None:
        sub = SubmenuConfig(
            id="file",
            text="File",
            items=[
                MenuItemConfig(id="new", text="New", handler=_noop),
                PredefinedMenuItemConfig(kind_name=PredefinedMenuItemKind.SEPARATOR),
                MenuItemConfig(id="quit", text="Quit", handler=_noop),
            ],
        )
        d = sub.to_dict()
        assert len(d["items"]) == 3
        assert d["items"][0]["kind"] == "item"
        assert d["items"][1]["kind"] == "predefined"


class TestMenuConfig:
    """Test MenuConfig serialization and deserialization."""

    def test_roundtrip(self) -> None:
        config = MenuConfig(
            id="main",
            items=[
                MenuItemConfig(id="save", text="Save", handler=_noop, accelerator="CmdOrCtrl+S"),
                CheckMenuItemConfig(id="bold", text="Bold", handler=_noop, checked=True),
            ],
        )
        d = config.to_dict()
        restored = MenuConfig.from_dict(d)
        assert restored.id == "main"
        assert len(restored.items) == 2
        assert isinstance(restored.items[0], MenuItemConfig)
        assert isinstance(restored.items[1], CheckMenuItemConfig)
        assert restored.items[1].checked is True

    def test_nested_submenu_roundtrip(self) -> None:
        config = MenuConfig(
            id="main",
            items=[
                SubmenuConfig(
                    id="file",
                    text="File",
                    items=[MenuItemConfig(id="new", text="New", handler=_noop)],
                ),
            ],
        )
        d = config.to_dict()
        restored = MenuConfig.from_dict(d)
        sub = restored.items[0]
        assert isinstance(sub, SubmenuConfig)
        assert len(sub.items) == 1


# ── Tray type serialization tests ────────────────────────────────────


class TestTrayIconConfig:
    """Test TrayIconConfig serialization."""

    def test_minimal(self) -> None:
        config = TrayIconConfig(id="tray1")
        d = config.to_dict()
        assert d["id"] == "tray1"
        assert d["menu_on_left_click"] is True
        assert "icon" not in d

    def test_full(self) -> None:
        icon_data = b"\x00" * 128
        menu = MenuConfig(
            id="tray-menu", items=[MenuItemConfig(id="quit", text="Quit", handler=_noop)]
        )
        config = TrayIconConfig(
            id="tray1",
            tooltip="My App",
            title="App",
            icon=icon_data,
            icon_width=16,
            icon_height=16,
            menu=menu,
        )
        d = config.to_dict()
        assert d["tooltip"] == "My App"
        assert d["title"] == "App"
        assert "icon" in d
        assert d["icon_width"] == 16
        assert "menu" in d
        assert d["menu"]["id"] == "tray-menu"


class TestMouseEnums:
    """Test mouse enums."""

    def test_mouse_button_values(self) -> None:
        assert MouseButton.LEFT.value == "Left"
        assert MouseButton.RIGHT.value == "Right"
        assert MouseButton.MIDDLE.value == "Middle"

    def test_mouse_button_state_values(self) -> None:
        assert MouseButtonState.UP.value == "Up"
        assert MouseButtonState.DOWN.value == "Down"


# ── MenuProxy IPC tests ──────────────────────────────────────────────


class TestMenuProxyIPC:
    """Test MenuProxy sends correct IPC commands."""

    @patch("pywry.menu_proxy.runtime")
    def test_create_sends_command(self, mock_runtime: MagicMock) -> None:
        mock_runtime.get_response.return_value = {"success": True}

        from pywry.menu_proxy import MenuProxy

        items = [MenuItemConfig(id="save", text="Save", handler=_noop)]
        proxy = MenuProxy.create(menu_id="test-menu", items=items)

        assert proxy.id == "test-menu"
        mock_runtime.send_command.assert_called_once()
        cmd = mock_runtime.send_command.call_args[0][0]
        assert cmd["action"] == "menu_create"
        assert cmd["menu_id"] == "test-menu"
        assert len(cmd["items"]) == 1

    @patch("pywry.menu_proxy.runtime")
    def test_create_failure_raises(self, mock_runtime: MagicMock) -> None:
        mock_runtime.get_response.return_value = {"success": False, "error": "boom"}

        from pywry.menu_proxy import MenuProxy

        with pytest.raises(RuntimeError, match="boom"):
            MenuProxy.create(menu_id="test-menu")

    @patch("pywry.menu_proxy.runtime")
    def test_from_config(self, mock_runtime: MagicMock) -> None:
        mock_runtime.get_response.return_value = {"success": True}

        from pywry.menu_proxy import MenuProxy

        config = MenuConfig(
            id="main",
            items=[MenuItemConfig(id="save", text="Save", handler=_noop)],
        )
        proxy = MenuProxy.from_config(config)
        assert proxy.id == "main"

    @patch("pywry.menu_proxy.runtime")
    def test_append(self, mock_runtime: MagicMock) -> None:
        proxy = _make_proxy("pywry.menu_proxy.MenuProxy", "m1", mock_runtime)
        proxy.append(MenuItemConfig(id="new", text="New", handler=_noop))

        cmd = mock_runtime.send_command.call_args[0][0]
        assert cmd["action"] == "menu_update"
        assert cmd["operation"] == "append"
        assert cmd["item_data"]["id"] == "new"

    @patch("pywry.menu_proxy.runtime")
    def test_set_text(self, mock_runtime: MagicMock) -> None:
        proxy = _make_proxy("pywry.menu_proxy.MenuProxy", "m1", mock_runtime)
        proxy.set_text("save", "Save As...")

        cmd = mock_runtime.send_command.call_args[0][0]
        assert cmd["operation"] == "set_text"
        assert cmd["item_id"] == "save"
        assert cmd["text"] == "Save As..."

    @patch("pywry.menu_proxy.runtime")
    def test_set_enabled(self, mock_runtime: MagicMock) -> None:
        proxy = _make_proxy("pywry.menu_proxy.MenuProxy", "m1", mock_runtime)
        proxy.set_enabled("save", False)

        cmd = mock_runtime.send_command.call_args[0][0]
        assert cmd["operation"] == "set_enabled"
        assert cmd["enabled"] is False

    @patch("pywry.menu_proxy.runtime")
    def test_set_checked(self, mock_runtime: MagicMock) -> None:
        proxy = _make_proxy("pywry.menu_proxy.MenuProxy", "m1", mock_runtime)
        proxy.set_checked("bold", True)

        cmd = mock_runtime.send_command.call_args[0][0]
        assert cmd["operation"] == "set_checked"
        assert cmd["checked"] is True

    @patch("pywry.menu_proxy.runtime")
    def test_set_as_app_menu(self, mock_runtime: MagicMock) -> None:
        proxy = _make_proxy("pywry.menu_proxy.MenuProxy", "m1", mock_runtime)
        proxy.set_as_app_menu()

        cmd = mock_runtime.send_command.call_args[0][0]
        assert cmd["action"] == "menu_set"
        assert cmd["target"] == "app"

    @patch("pywry.menu_proxy.runtime")
    def test_set_as_window_menu(self, mock_runtime: MagicMock) -> None:
        proxy = _make_proxy("pywry.menu_proxy.MenuProxy", "m1", mock_runtime)
        proxy.set_as_window_menu("main")

        cmd = mock_runtime.send_command.call_args[0][0]
        assert cmd["action"] == "menu_set"
        assert cmd["target"] == "window"
        assert cmd["label"] == "main"

    @patch("pywry.menu_proxy.runtime")
    def test_popup(self, mock_runtime: MagicMock) -> None:
        proxy = _make_proxy("pywry.menu_proxy.MenuProxy", "m1", mock_runtime)
        proxy.popup("main", x=100.0, y=200.0)

        cmd = mock_runtime.send_command.call_args[0][0]
        assert cmd["action"] == "menu_popup"
        assert cmd["position"] == {"x": 100.0, "y": 200.0}

    @patch("pywry.menu_proxy.runtime")
    def test_popup_no_position(self, mock_runtime: MagicMock) -> None:
        proxy = _make_proxy("pywry.menu_proxy.MenuProxy", "m1", mock_runtime)
        proxy.popup("main")

        cmd = mock_runtime.send_command.call_args[0][0]
        assert "position" not in cmd

    @patch("pywry.menu_proxy.runtime")
    def test_destroy(self, mock_runtime: MagicMock) -> None:
        proxy = _make_proxy("pywry.menu_proxy.MenuProxy", "m1", mock_runtime)
        proxy.destroy()

        cmd = mock_runtime.send_command.call_args[0][0]
        assert cmd["action"] == "menu_remove"

    @patch("pywry.menu_proxy.runtime")
    def test_remove_item(self, mock_runtime: MagicMock) -> None:
        proxy = _make_proxy("pywry.menu_proxy.MenuProxy", "m1", mock_runtime)
        proxy.remove("save")

        cmd = mock_runtime.send_command.call_args[0][0]
        assert cmd["operation"] == "remove"
        assert cmd["item_id"] == "save"

    @patch("pywry.menu_proxy.runtime")
    def test_repr(self, mock_runtime: MagicMock) -> None:
        proxy = _make_proxy("pywry.menu_proxy.MenuProxy", "m1", mock_runtime)
        assert repr(proxy) == "MenuProxy(id='m1')"


# ── TrayProxy IPC tests ──────────────────────────────────────────────


class TestTrayProxyIPC:
    """Test TrayProxy sends correct IPC commands."""

    @patch("pywry.tray_proxy.runtime")
    def test_create_sends_command(self, mock_runtime: MagicMock) -> None:
        mock_runtime.send_command_with_response.return_value = {"success": True}

        from pywry.tray_proxy import TrayProxy

        tray = TrayProxy.create(tray_id="tray1", tooltip="My App")

        assert tray.id == "tray1"
        cmd = mock_runtime.send_command_with_response.call_args[0][0]
        assert cmd["action"] == "tray_create"
        assert cmd["tray_id"] == "tray1"
        assert cmd["tooltip"] == "My App"

    @patch("pywry.tray_proxy.runtime")
    def test_create_with_menu(self, mock_runtime: MagicMock) -> None:
        mock_runtime.send_command_with_response.return_value = {"success": True}

        from pywry.tray_proxy import TrayProxy

        menu = MenuConfig(
            id="tray-menu",
            items=[MenuItemConfig(id="quit", text="Quit", handler=_noop)],
        )
        TrayProxy.create(tray_id="tray1", menu=menu)

        cmd = mock_runtime.send_command_with_response.call_args[0][0]
        assert "menu" in cmd
        assert cmd["menu"]["id"] == "tray-menu"

    @patch("pywry.tray_proxy.runtime")
    def test_create_failure_raises(self, mock_runtime: MagicMock) -> None:
        mock_runtime.send_command_with_response.return_value = {
            "success": False,
            "error": "no icon",
        }

        from pywry.tray_proxy import TrayProxy

        with pytest.raises(RuntimeError, match="no icon"):
            TrayProxy.create(tray_id="tray1")

    @patch("pywry.tray_proxy.runtime")
    def test_set_tooltip(self, mock_runtime: MagicMock) -> None:
        tray = _make_tray_proxy("tray1", mock_runtime)
        tray.set_tooltip("Running...")

        cmd = mock_runtime.send_command.call_args[0][0]
        assert cmd["action"] == "tray_update"
        assert cmd["tooltip"] == "Running..."

    @patch("pywry.tray_proxy.runtime")
    def test_set_title(self, mock_runtime: MagicMock) -> None:
        tray = _make_tray_proxy("tray1", mock_runtime)
        tray.set_title("My App v2")

        cmd = mock_runtime.send_command.call_args[0][0]
        assert cmd["title"] == "My App v2"

    @patch("pywry.tray_proxy.runtime")
    def test_set_visible(self, mock_runtime: MagicMock) -> None:
        tray = _make_tray_proxy("tray1", mock_runtime)
        tray.set_visible(False)

        cmd = mock_runtime.send_command.call_args[0][0]
        assert cmd["visible"] is False

    @patch("pywry.tray_proxy.runtime")
    def test_set_icon(self, mock_runtime: MagicMock) -> None:
        tray = _make_tray_proxy("tray1", mock_runtime)
        tray.set_icon(b"\x00" * 64, width=4, height=4)

        cmd = mock_runtime.send_command.call_args[0][0]
        assert "icon" in cmd
        assert cmd["icon_width"] == 4
        assert cmd["icon_height"] == 4

    @patch("pywry.tray_proxy.runtime")
    def test_set_menu(self, mock_runtime: MagicMock) -> None:
        tray = _make_tray_proxy("tray1", mock_runtime)
        menu = MenuConfig(id="new-menu", items=[MenuItemConfig(id="a", text="A", handler=_noop)])
        tray.set_menu(menu)

        cmd = mock_runtime.send_command.call_args[0][0]
        assert cmd["menu"]["id"] == "new-menu"

    @patch("pywry.tray_proxy.runtime")
    def test_remove(self, mock_runtime: MagicMock) -> None:
        tray = _make_tray_proxy("tray1", mock_runtime)
        tray.remove()

        cmd = mock_runtime.send_command_with_response.call_args[0][0]
        assert cmd["action"] == "tray_remove"

    @patch("pywry.tray_proxy.runtime")
    def test_on_registers_callback(self, mock_runtime: MagicMock) -> None:
        from pywry.callbacks import get_registry

        tray = _make_tray_proxy("tray1", mock_runtime)
        handler = MagicMock()
        tray.on("tray:click", handler)

        # Callback should be registered under __tray__tray1 label
        registry = get_registry()
        label = "__tray__tray1"
        dispatched = registry.dispatch(label, "tray:click", {"button": "left"})
        assert dispatched

    @patch("pywry.tray_proxy.runtime")
    def test_set_menu_on_left_click(self, mock_runtime: MagicMock) -> None:
        tray = _make_tray_proxy("tray1", mock_runtime)
        tray.set_menu_on_left_click(False)

        cmd = mock_runtime.send_command.call_args[0][0]
        assert cmd["menu_on_left_click"] is False

    @patch("pywry.tray_proxy.runtime")
    def test_from_config(self, mock_runtime: MagicMock) -> None:
        mock_runtime.get_response.return_value = {"success": True}

        from pywry.tray_proxy import TrayProxy

        config = TrayIconConfig(id="tray2", tooltip="Config Test")
        tray = TrayProxy.from_config(config)
        assert tray.id == "tray2"

    @patch("pywry.tray_proxy.runtime")
    def test_repr(self, mock_runtime: MagicMock) -> None:
        tray = _make_tray_proxy("tray1", mock_runtime)
        assert repr(tray) == "TrayProxy(id='tray1')"


# ── Builder options flow tests ────────────────────────────────────────


class TestBuilderOptionsFlow:
    """Test that WindowConfig builder fields flow through show()."""

    def test_builder_kwargs_returns_non_defaults(self) -> None:
        from pywry.models import WindowConfig

        config = WindowConfig(transparent=True, user_agent="test/1.0")
        kwargs = config.builder_kwargs()
        assert kwargs["transparent"] is True
        assert kwargs["user_agent"] == "test/1.0"
        # Default values should not be in kwargs
        assert "resizable" not in kwargs
        assert "decorations" not in kwargs

    def test_builder_kwargs_empty_for_defaults(self) -> None:
        from pywry.models import WindowConfig

        config = WindowConfig()
        assert config.builder_kwargs() == {}  # pylint: disable=use-implicit-booleaness-not-comparison

    def test_builder_fields_list(self) -> None:
        from pywry.models import WindowConfig

        expected = {
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
        assert expected == WindowConfig._BUILDER_FIELDS

    def test_initialization_script_field(self) -> None:
        from pywry.models import WindowConfig

        config = WindowConfig(initialization_script="console.log('hello')")
        assert config.initialization_script == "console.log('hello')"
        kwargs = config.builder_kwargs()
        assert kwargs["initialization_script"] == "console.log('hello')"


# ── Handler collection tests ─────────────────────────────────────────


class TestCollectHandlers:
    """Test collect_handlers() recursively extracts {item_id: handler}."""

    def test_flat_menu(self) -> None:
        h1 = MagicMock()
        h2 = MagicMock()
        config = MenuConfig(
            id="m",
            items=[
                MenuItemConfig(id="a", text="A", handler=h1),
                MenuItemConfig(id="b", text="B", handler=h2),
            ],
        )
        handlers = config.collect_handlers()
        assert handlers == {"a": h1, "b": h2}

    def test_nested_submenu(self) -> None:
        h1 = MagicMock()
        config = MenuConfig(
            id="m",
            items=[
                SubmenuConfig(
                    id="sub",
                    text="Sub",
                    items=[MenuItemConfig(id="inner", text="Inner", handler=h1)],
                ),
            ],
        )
        handlers = config.collect_handlers()
        assert handlers == {"inner": h1}

    def test_skips_predefined(self) -> None:
        config = MenuConfig(
            id="m",
            items=[
                MenuItemConfig(id="a", text="A", handler=_noop),
                PredefinedMenuItemConfig(kind_name=PredefinedMenuItemKind.SEPARATOR),
            ],
        )
        handlers = config.collect_handlers()
        assert list(handlers.keys()) == ["a"]

    def test_submenu_collect(self) -> None:
        h = MagicMock()
        sub = SubmenuConfig(
            id="s",
            text="S",
            items=[MenuItemConfig(id="x", text="X", handler=h)],
        )
        assert sub.collect_handlers() == {"x": h}

    def test_empty_menu(self) -> None:
        config = MenuConfig(id="m", items=[])
        assert config.collect_handlers() == {}  # pylint: disable=use-implicit-booleaness-not-comparison


class TestMenuProxyHandlers:
    """Test MenuProxy stores and registers handlers."""

    @patch("pywry.menu_proxy.runtime")
    def test_create_extracts_handlers(self, mock_runtime: MagicMock) -> None:
        mock_runtime.get_response.return_value = {"success": True}

        from pywry.menu_proxy import MenuProxy

        h = MagicMock()
        items = [MenuItemConfig(id="save", text="Save", handler=h)]
        proxy = MenuProxy.create(menu_id="m", items=items)
        assert proxy.handlers == {"save": h}

    @patch("pywry.menu_proxy.runtime")
    def test_from_config_extracts_handlers(self, mock_runtime: MagicMock) -> None:
        mock_runtime.get_response.return_value = {"success": True}

        from pywry.menu_proxy import MenuProxy

        h1 = MagicMock()
        h2 = MagicMock()
        config = MenuConfig(
            id="m",
            items=[
                SubmenuConfig(
                    id="file",
                    text="File",
                    items=[
                        MenuItemConfig(id="new", text="New", handler=h1),
                        MenuItemConfig(id="quit", text="Quit", handler=h2),
                    ],
                ),
            ],
        )
        proxy = MenuProxy.from_config(config)
        assert proxy.handlers == {"new": h1, "quit": h2}

    @patch("pywry.menu_proxy.runtime")
    def test_register_handlers_dispatches(self, mock_runtime: MagicMock) -> None:
        """register_handlers installs a menu:click dispatcher that routes to item handlers."""
        from pywry.callbacks import get_registry

        mock_runtime.get_response.return_value = {"success": True}

        from pywry.menu_proxy import MenuProxy

        h = MagicMock()
        proxy = MenuProxy.create(
            menu_id="m",
            items=[
                MenuItemConfig(id="save", text="Save", handler=h),
            ],
        )
        proxy.register_handlers("win-1")

        # Simulate a menu:click event
        registry = get_registry()
        dispatched = registry.dispatch("win-1", "menu:click", {"item_id": "save", "source": "app"})
        assert dispatched
        h.assert_called_once()

    @patch("pywry.menu_proxy.runtime")
    def test_register_handlers_idempotent(self, mock_runtime: MagicMock) -> None:
        """Calling register_handlers twice does not double-register."""
        mock_runtime.get_response.return_value = {"success": True}

        from pywry.menu_proxy import MenuProxy

        h = MagicMock()
        proxy = MenuProxy.create(
            menu_id="m",
            items=[
                MenuItemConfig(id="a", text="A", handler=h),
            ],
        )
        proxy.register_handlers("win-1")
        proxy.register_handlers("win-1")  # should be a no-op

        from pywry.callbacks import get_registry

        get_registry().dispatch("win-1", "menu:click", {"item_id": "a", "source": "app"})
        # Handler should only be called once — one registration
        assert h.call_count == 1


class TestTrayProxyAutoRegister:
    """Test TrayProxy.from_config auto-registers handlers."""

    @patch("pywry.tray_proxy.runtime")
    def test_on_click_auto_registered(self, mock_runtime: MagicMock) -> None:
        mock_runtime.get_response.return_value = {"success": True}

        from pywry.callbacks import get_registry
        from pywry.tray_proxy import TrayProxy

        h = MagicMock()
        config = TrayIconConfig(id="t1", tooltip="Test", on_click=h)
        TrayProxy.from_config(config)

        registry = get_registry()
        dispatched = registry.dispatch("__tray__t1", "tray:click", {"button": "Left"})
        assert dispatched

    @patch("pywry.tray_proxy.runtime")
    def test_menu_handlers_auto_registered(self, mock_runtime: MagicMock) -> None:
        mock_runtime.get_response.return_value = {"success": True}

        from pywry.callbacks import get_registry
        from pywry.tray_proxy import TrayProxy

        h = MagicMock()
        config = TrayIconConfig(
            id="t2",
            menu=MenuConfig(
                id="tm",
                items=[MenuItemConfig(id="show", text="Show", handler=h)],
            ),
        )
        TrayProxy.from_config(config)

        registry = get_registry()
        dispatched = registry.dispatch(
            "__tray__t2", "menu:click", {"item_id": "show", "source": "tray"}
        )
        assert dispatched


# ── Helpers ───────────────────────────────────────────────────────────


def _make_proxy(cls_path: str, menu_id: str, mock_runtime: MagicMock) -> Any:  # pylint: disable=unused-argument
    """Create a MenuProxy without going through IPC."""
    from pywry.menu_proxy import MenuProxy

    proxy = MenuProxy(menu_id)
    mock_runtime.reset_mock()
    return proxy


def _make_tray_proxy(tray_id: str, mock_runtime: MagicMock) -> Any:
    """Create a TrayProxy without going through IPC."""
    from pywry.tray_proxy import TrayProxy

    proxy = TrayProxy(tray_id)
    mock_runtime.reset_mock()
    return proxy
