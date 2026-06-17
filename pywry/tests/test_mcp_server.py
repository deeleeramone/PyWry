"""Tests for ``pywry.mcp.server``.

Covers:
- ``HAS_MCP`` flag and ``create_server`` configuration paths.
- ``_make_event_callback`` populates the ``_events`` bucket.
- ``_format_tool_result`` — plain JSON path, AppArtifact embedded
  resource path, and the fallback when ``mcp.types`` is unavailable.
- ``_register_component_docs``, ``_register_source_resources``,
  ``_register_static_resources`` — FastMCP closures actually read
  bytes from disk.
- ``run_server`` dispatch on ``transport``, signal handler cleanup,
  ``PYWRY_HEADLESS`` env var fallback.
- ``_setup_headless_mode`` starts the inline server.
- ``_create_tool_function`` wraps handlers and renders raises as JSON
  error strings.
"""

from __future__ import annotations

import asyncio
import builtins

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


pytest.importorskip("mcp")
pytest.importorskip("fastmcp")


# ---------------------------------------------------------------------------
# Flags + factory
# ---------------------------------------------------------------------------


class TestServerFactory:
    def test_has_mcp_flag_is_bool(self) -> None:
        from pywry.mcp.server import HAS_MCP

        assert isinstance(HAS_MCP, bool)

    def test_default_name(self) -> None:
        from pywry.mcp.server import HAS_MCP, create_server

        if not HAS_MCP:
            pytest.skip("fastmcp not available")
        server = create_server()
        assert server is not None
        assert server.name == "pywry-widgets"

    def test_custom_settings(self) -> None:
        from pywry.config import MCPSettings
        from pywry.mcp.server import HAS_MCP, create_server

        if not HAS_MCP:
            pytest.skip("fastmcp not available")
        settings = MCPSettings(name="custom-server", version="9.9.9", instructions="Be nice")
        srv = create_server(settings)
        assert srv.name == "custom-server"

    def test_resolves_pywry_version_when_missing(self) -> None:
        from pywry.config import MCPSettings
        from pywry.mcp.server import HAS_MCP, create_server

        if not HAS_MCP:
            pytest.skip("fastmcp not available")
        settings = MCPSettings(name="s")  # no explicit version
        srv = create_server(settings)
        assert srv.name == "s"

    def test_falls_back_when_pywry_version_unimportable(self, monkeypatch) -> None:
        from pywry.config import MCPSettings
        from pywry.mcp.server import HAS_MCP, create_server

        if not HAS_MCP:
            pytest.skip("fastmcp not available")
        original_import = builtins.__import__

        def fake_import(name, globals_=None, locals_=None, fromlist=None, level=0):
            if name == "pywry" and fromlist and "__version__" in fromlist:
                raise ImportError("simulated")
            return original_import(name, globals_, locals_, fromlist or (), level)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        settings = MCPSettings(name="x")  # no explicit version
        srv = create_server(settings)
        assert srv is not None

    def test_raises_import_error_when_no_mcp(self, monkeypatch) -> None:
        from pywry.mcp import server

        monkeypatch.setattr(server, "HAS_MCP", False)
        with pytest.raises(ImportError, match="fastmcp"):
            server.create_server()


# ---------------------------------------------------------------------------
# _make_event_callback
# ---------------------------------------------------------------------------


class TestEventCallback:
    def test_appends_event_to_widget_bucket(self) -> None:
        from pywry.mcp.server import _events, _make_event_callback

        _events.pop("w", None)
        cb = _make_event_callback("w")
        cb({"clicked": True}, "button:click", "Save")
        assert "w" in _events
        assert len(_events["w"]) == 1
        assert _events["w"][0]["event_type"] == "button:click"
        _events.pop("w", None)

    def test_appends_to_existing_bucket(self) -> None:
        from pywry.mcp.server import _events, _make_event_callback

        _events.clear()
        _events["w"] = [{"event_type": "old", "data": {}, "label": ""}]
        cb = _make_event_callback("w")
        cb({"x": 1}, "click", "")
        assert len(_events["w"]) == 2


# ---------------------------------------------------------------------------
# _format_tool_result
# ---------------------------------------------------------------------------


class TestFormatToolResult:
    def test_plain_dict_returns_json_string(self) -> None:
        from pywry.mcp.server import _format_tool_result

        out = _format_tool_result({"a": 1})
        assert isinstance(out, str)
        assert '"a": 1' in out

    def test_app_artifact_emits_embedded_resource(self) -> None:
        from pywry.mcp.server import _format_tool_result

        payload = {
            "widget_id": "w",
            "_app_artifact": {
                "html": "<b>hi</b>",
                "uri": "pywry-app://w/3",
                "mime_type": "text/html",
                "widget_id": "w",
                "revision": 3,
            },
        }
        out = _format_tool_result(payload)
        if isinstance(out, list):
            assert len(out) == 2
            text, embedded = out
            assert getattr(text, "type", None) == "text"
            assert "widget_id" in getattr(text, "text", "")
            assert getattr(embedded, "type", None) == "resource"
            resource = embedded.resource
            assert str(getattr(resource, "uri", "")).rstrip("/") == "pywry-app://w/3"
            assert getattr(resource, "mimeType", "") == "text/html"
            assert getattr(resource, "text", "") == "<b>hi</b>"
        else:
            # Fallback path — the app artifact remains in the dict.
            assert "_app_artifact" in out

    def test_app_artifact_default_uri(self) -> None:
        from pywry.mcp.server import _format_tool_result

        payload = {
            "widget_id": "w",
            "_app_artifact": {"html": "<b>hi</b>", "widget_id": "w", "revision": 3},
        }
        out = _format_tool_result(payload)
        assert out is not None

    def test_falls_back_when_mcp_types_missing(self, monkeypatch) -> None:
        from pywry.mcp import server

        original_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "mcp.types":
                raise ImportError("simulated")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        out = server._format_tool_result({"_app_artifact": {"html": "<b>x</b>"}, "widget_id": "w"})
        assert isinstance(out, str)
        assert "_app_artifact" in out


# ---------------------------------------------------------------------------
# Resource registration closures
# ---------------------------------------------------------------------------


class TestResourceRegistrationClosures:
    def test_component_docs_register_and_read(self) -> None:
        from pywry.mcp.server import HAS_MCP, _register_component_docs

        if not HAS_MCP:
            pytest.skip("fastmcp not available")
        from fastmcp import FastMCP

        mcp = FastMCP(name="test")
        _register_component_docs(mcp)

        async def _exercise() -> None:
            res = await mcp._list_resources()
            comp_resources = [r for r in res if "component" in str(r.uri)]
            for r in comp_resources[:3]:
                await r.read()

        asyncio.run(_exercise())

    def test_source_resources_register_and_read(self) -> None:
        from pywry.mcp.server import HAS_MCP, _register_source_resources

        if not HAS_MCP:
            pytest.skip("fastmcp not available")
        from fastmcp import FastMCP

        mcp = FastMCP(name="test")
        _register_source_resources(mcp)

        async def _exercise() -> None:
            res = await mcp._list_resources()
            for r in res:
                if "source" in str(r.uri):
                    await r.read()
                    break

        asyncio.run(_exercise())

    def test_source_resources_aggregate(self) -> None:
        from pywry.mcp.server import HAS_MCP, _register_source_resources

        if not HAS_MCP:
            pytest.skip("fastmcp not available")
        from fastmcp import FastMCP

        mcp = FastMCP(name="test")
        _register_source_resources(mcp)

        async def _exercise() -> None:
            res = await mcp._list_resources()
            agg = [r for r in res if str(r.uri) == "pywry://source/components"]
            if agg:
                await agg[0].read()

        asyncio.run(_exercise())

    def test_static_resources_register_and_read(self) -> None:
        from pywry.mcp.server import HAS_MCP, _register_static_resources

        if not HAS_MCP:
            pytest.skip("fastmcp not available")
        from fastmcp import FastMCP

        mcp = FastMCP(name="test")
        _register_static_resources(mcp)

        async def _exercise() -> None:
            res = await mcp._list_resources()
            for r in res:
                if "events" in str(r.uri) or "quickstart" in str(r.uri):
                    await r.read()

        asyncio.run(_exercise())

    def test_export_resource_template(self, mcp_fresh_state) -> None:
        from pywry.mcp import state as mcp_state
        from pywry.mcp.server import HAS_MCP, _register_static_resources

        if not HAS_MCP:
            pytest.skip("fastmcp not available")
        from fastmcp import FastMCP

        mcp_state._widget_configs["abc"] = {"html": "x", "toolbars": []}
        mcp = FastMCP(name="test")
        _register_static_resources(mcp)

        async def _exercise() -> None:
            templates = await mcp._list_resource_templates()
            for t in templates:
                if "export" in str(getattr(t, "uri_template", "")):
                    fn = getattr(t, "fn", None)
                    if callable(fn):
                        result = fn(widget_id="abc")
                        assert result is not None
                        result_missing = fn(widget_id="nonexistent_xyz")
                        assert "Widget not found" in result_missing

        asyncio.run(_exercise())


# ---------------------------------------------------------------------------
# run_server dispatch
# ---------------------------------------------------------------------------


class TestRunServer:
    def test_setup_headless_mode_starts_inline_server(self, monkeypatch) -> None:
        from pywry.mcp import server

        called: dict[str, bool] = {}
        monkeypatch.setattr(
            "pywry.inline._start_server", lambda: called.setdefault("started", True)
        )
        server._setup_headless_mode()
        assert called.get("started") is True

    def test_unknown_transport_raises(self, monkeypatch) -> None:
        from pywry.mcp import server

        fake_mcp = MagicMock()
        monkeypatch.setattr(server, "create_server", lambda _settings=None: fake_mcp)
        monkeypatch.setattr("pywry.mcp.server._setup_headless_mode", lambda: None)
        with pytest.raises(ValueError, match="Unknown transport"):
            server.run_server(transport="not_a_real_transport", headless=False)

    def test_stdio_dispatch(self, monkeypatch) -> None:
        from pywry.mcp import server

        fake_mcp = MagicMock()
        monkeypatch.setattr(server, "create_server", lambda _settings=None: fake_mcp)
        monkeypatch.setattr("signal.signal", lambda *_a, **_kw: None)
        monkeypatch.setattr("pywry.mcp.server._setup_headless_mode", lambda: None)
        server.run_server(transport="stdio", headless=False)
        fake_mcp.run.assert_called_once()

    def test_sse_dispatch(self, monkeypatch) -> None:
        from pywry.mcp import server

        fake_mcp = MagicMock()
        monkeypatch.setattr(server, "create_server", lambda _settings=None: fake_mcp)
        monkeypatch.setattr("signal.signal", lambda *_a, **_kw: None)
        monkeypatch.setattr("pywry.mcp.server._setup_headless_mode", lambda: None)
        server.run_server(transport="sse", port=9000, host="127.0.0.1", headless=True)
        fake_mcp.run.assert_called_once()
        kwargs = fake_mcp.run.call_args[1]
        assert kwargs["transport"] == "sse"
        assert kwargs["port"] == 9000

    def test_streamable_http_dispatch(self, monkeypatch) -> None:
        from pywry.mcp import server

        fake_mcp = MagicMock()
        monkeypatch.setattr(server, "create_server", lambda _settings=None: fake_mcp)
        monkeypatch.setattr("signal.signal", lambda *_a, **_kw: None)
        monkeypatch.setattr("pywry.mcp.server._setup_headless_mode", lambda: None)
        server.run_server(transport="streamable-http", port=9001, headless=False)
        fake_mcp.run.assert_called_once()
        kwargs = fake_mcp.run.call_args[1]
        assert kwargs["transport"] == "streamable-http"

    def test_signal_handler_cleans_inline_when_headless(self, monkeypatch) -> None:
        from pywry.mcp import server

        fake_mcp = MagicMock()
        captured: dict[str, Any] = {}

        def fake_signal(_signum, handler):
            captured.setdefault("handlers", []).append(handler)

        monkeypatch.setattr("signal.signal", fake_signal)
        monkeypatch.setattr(server, "create_server", lambda _settings=None: fake_mcp)
        monkeypatch.setattr("pywry.mcp.server._setup_headless_mode", lambda: None)
        server.run_server(transport="stdio", headless=True)
        handler = captured["handlers"][0]
        with patch("pywry.inline.stop_server") as stopper, pytest.raises(SystemExit):
            handler(0, None)
        stopper.assert_called_once()

    def test_signal_handler_cleans_runtime_when_native(self, monkeypatch) -> None:
        from pywry.mcp import server

        fake_mcp = MagicMock()
        captured: dict[str, Any] = {}

        def fake_signal(_signum, handler):
            captured.setdefault("handlers", []).append(handler)

        monkeypatch.setattr("signal.signal", fake_signal)
        monkeypatch.setattr(server, "create_server", lambda _settings=None: fake_mcp)
        monkeypatch.setattr("pywry.mcp.server._setup_headless_mode", lambda: None)
        server.run_server(transport="stdio", headless=False)
        handler = captured["handlers"][0]
        with patch("pywry.runtime.stop") as stopper, pytest.raises(SystemExit):
            handler(0, None)
        stopper.assert_called_once()

    def test_uses_env_headless_when_arg_none(self, monkeypatch) -> None:
        from pywry.mcp import server

        fake_mcp = MagicMock()
        monkeypatch.setattr(server, "create_server", lambda _settings=None: fake_mcp)
        monkeypatch.setattr("signal.signal", lambda *_a, **_kw: None)
        monkeypatch.setattr("pywry.mcp.server._setup_headless_mode", lambda: None)
        monkeypatch.setenv("PYWRY_HEADLESS", "1")
        server.run_server(transport="stdio")
        fake_mcp.run.assert_called_once()

    def test_falls_back_to_settings_when_no_env(self, monkeypatch) -> None:
        from pywry.mcp import server

        fake_mcp = MagicMock()
        monkeypatch.setattr(server, "create_server", lambda _settings=None: fake_mcp)
        monkeypatch.setattr("signal.signal", lambda *_a, **_kw: None)
        monkeypatch.setattr("pywry.mcp.server._setup_headless_mode", lambda: None)
        monkeypatch.delenv("PYWRY_HEADLESS", raising=False)
        server.run_server(transport="stdio")
        fake_mcp.run.assert_called_once()


# ---------------------------------------------------------------------------
# _create_tool_function
# ---------------------------------------------------------------------------


class TestCreateToolFunction:
    def test_wraps_raising_handler_as_error_string(self, mcp_fresh_state) -> None:
        from pywry.mcp import server

        async def raising_handler(_name, _args, _events, _make_callback):
            raise RuntimeError("boom")

        fn = server._create_tool_function(
            "fake_tool",
            {"properties": {"x": {"type": "string"}}},
            raising_handler,
            {},
        )
        out = asyncio.run(fn(x="a"))
        assert isinstance(out, str)
        assert "error" in out


class TestHasMcpFallback:
    """Verify that pywry.mcp.server loads cleanly when fastmcp is unavailable.

    fastmcp is an optional dependency (``mcp`` extras group), so users
    who install pywry without that extra will hit the ImportError fallback.
    Runs in a subprocess so the parent session's module state isn't
    polluted by the reload.
    """

    def test_module_loads_without_fastmcp(self, tmp_path):
        """Spawn a fresh interpreter with fastmcp pre-blocked, then import pywry.mcp.server."""
        import os
        import subprocess
        import sys

        from pathlib import Path

        rcfile = str(Path(__file__).resolve().parent.parent / ".coveragerc")
        script = tmp_path / "check_fastmcp_fallback.py"
        script.write_text(
            f"import os\n"
            f"os.environ['COVERAGE_PROCESS_START'] = {rcfile!r}\n"
            f"import coverage\n"
            f"coverage.process_startup()\n"
            f"import sys\n"
            f"import builtins\n"
            f"_real = builtins.__import__\n"
            f"def _blocked(name, *a, **k):\n"
            f"    if name == 'fastmcp' or name.startswith('fastmcp.'):\n"
            f"        raise ImportError('blocked for test')\n"
            f"    return _real(name, *a, **k)\n"
            f"builtins.__import__ = _blocked\n"
            f"sys.modules.pop('fastmcp', None)\n"
            f"from pywry.mcp import server\n"
            f"assert server.HAS_MCP is False\n"
            f"print('OK')\n"
        )
        env = {**os.environ, "COVERAGE_PROCESS_START": rcfile}
        result = subprocess.run(
            [sys.executable, str(script)],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(Path(rcfile).parent),
            env=env,
        )
        assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
        assert "OK" in result.stdout
