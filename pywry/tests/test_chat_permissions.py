"""Tests for pywry.chat.permissions."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from pywry.chat.permissions import ACP_PERMISSION_MAP, check_acp_permission


class TestPermissionMap:
    def test_session_operations_require_write(self):
        assert ACP_PERMISSION_MAP["session/new"] == "write"
        assert ACP_PERMISSION_MAP["session/prompt"] == "write"
        assert ACP_PERMISSION_MAP["session/cancel"] == "write"

    def test_fs_read_requires_read(self):
        assert ACP_PERMISSION_MAP["fs/read_text_file"] == "read"

    def test_fs_write_requires_admin(self):
        assert ACP_PERMISSION_MAP["fs/write_text_file"] == "admin"

    def test_terminal_operations_require_admin(self):
        for op in [
            "terminal/create",
            "terminal/output",
            "terminal/kill",
            "terminal/wait_for_exit",
            "terminal/release",
        ]:
            assert ACP_PERMISSION_MAP[op] == "admin"


class TestCheckAcpPermission:
    async def test_none_session_allowed(self):
        result = await check_acp_permission(None, "widget-1", "session/new", MagicMock())
        assert result is True

    async def test_known_operation_uses_mapped_permission(self):
        session = MagicMock()
        store = MagicMock()
        store.check_permission = AsyncMock(return_value=True)

        result = await check_acp_permission(session, "widget-1", "session/new", store)
        assert result is True

    async def test_unknown_operation_defaults_to_admin(self):
        session = MagicMock()
        session.session_id = "abc"
        session.roles = ["admin"]
        store = MagicMock()
        store.check_permission = AsyncMock(return_value=False)

        # Patch the imported check_widget_permission inside the function
        result = await check_acp_permission(session, "widget-1", "completely/unknown", store)
        assert result is False
        # Confirm "admin" was the default permission requested
        call_args = store.check_permission.await_args
        assert call_args[0][3] == "admin"

    async def test_returns_check_result(self):
        session = MagicMock()
        session.session_id = "s1"
        store = MagicMock()
        store.check_permission = AsyncMock(return_value=False)

        result = await check_acp_permission(session, "w-1", "session/prompt", store)
        assert result is False

    async def test_import_error_fallback(self, monkeypatch):
        """If state.auth import fails, returns True (allow all)."""
        import builtins

        original_import = builtins.__import__

        def fail_state_auth(name, *args, **kwargs):
            if name == "pywry.state.auth" or name.endswith("..state.auth"):
                raise ImportError("simulated")
            # The check uses relative import: "..state.auth" (resolves through __import__)
            if "state.auth" in name:
                raise ImportError("simulated")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fail_state_auth)

        session = MagicMock()
        store = MagicMock()

        result = await check_acp_permission(session, "w", "session/new", store)
        assert result is True


@pytest.mark.parametrize(
    "operation,expected",
    [
        ("session/load", "write"),
        ("session/set_mode", "write"),
        ("session/request_permission", "write"),
        ("session/set_config_option", "write"),
    ],
)
def test_session_management_operations(operation, expected):
    assert ACP_PERMISSION_MAP[operation] == expected
