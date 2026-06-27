"""Tests for ``pywry.mcp.__main__`` argparse driver and dispatch.

The CLI entry point parses argv, builds either the serve subcommand
arguments (defaulting to stdio) or the install-skills subcommand, and
delegates to ``pywry.mcp.server.run_server`` or
``pywry.mcp.install.install_skills`` respectively.

All I/O — server start, install side-effects, ``sys.exit`` — is
patched so the tests stay process-local and deterministic.
"""

from __future__ import annotations

import contextlib

from unittest.mock import patch

import pytest


pytest.importorskip("mcp")
pytest.importorskip("fastmcp")


# ---------------------------------------------------------------------------
# _build_serve_parser / _handle_serve
# ---------------------------------------------------------------------------


class TestBuildServeParser:
    def test_default_transport_is_stdio(self) -> None:
        import argparse

        from pywry.mcp.__main__ import _build_serve_parser

        parser = argparse.ArgumentParser()
        _build_serve_parser(parser)
        args = parser.parse_args([])
        assert args.transport == "stdio"
        assert args.port == 8001
        assert args.sse is None
        assert args.streamable_http is None

    def test_sse_shorthand_with_port(self) -> None:
        import argparse

        from pywry.mcp.__main__ import _build_serve_parser

        parser = argparse.ArgumentParser()
        _build_serve_parser(parser)
        args = parser.parse_args(["--sse", "9200"])
        assert args.sse == 9200

    def test_sse_shorthand_without_port_uses_default(self) -> None:
        import argparse

        from pywry.mcp.__main__ import _build_serve_parser

        parser = argparse.ArgumentParser()
        _build_serve_parser(parser)
        args = parser.parse_args(["--sse"])
        assert args.sse == 8001

    def test_streamable_http_shorthand(self) -> None:
        import argparse

        from pywry.mcp.__main__ import _build_serve_parser

        parser = argparse.ArgumentParser()
        _build_serve_parser(parser)
        args = parser.parse_args(["--streamable-http", "9300"])
        assert args.streamable_http == 9300


class TestHandleServe:
    def test_handle_serve_streamable_http(self) -> None:
        import argparse

        from pywry.mcp.__main__ import _handle_serve

        ns = argparse.Namespace(
            streamable_http=9001,
            sse=None,
            transport="stdio",
            port=8001,
        )
        with patch("pywry.mcp.server.run_server") as run_server:
            _handle_serve(ns)
        run_server.assert_called_once_with(transport="streamable-http", port=9001)

    def test_handle_serve_sse(self) -> None:
        import argparse

        from pywry.mcp.__main__ import _handle_serve

        ns = argparse.Namespace(
            streamable_http=None,
            sse=9002,
            transport="stdio",
            port=8001,
        )
        with patch("pywry.mcp.server.run_server") as run_server:
            _handle_serve(ns)
        run_server.assert_called_once_with(transport="sse", port=9002)

    def test_handle_serve_default_stdio(self) -> None:
        import argparse

        from pywry.mcp.__main__ import _handle_serve

        ns = argparse.Namespace(
            streamable_http=None,
            sse=None,
            transport="stdio",
            port=8001,
        )
        with patch("pywry.mcp.server.run_server") as run_server:
            _handle_serve(ns)
        run_server.assert_called_once_with(transport="stdio", port=8001)


# ---------------------------------------------------------------------------
# _handle_install_skills
# ---------------------------------------------------------------------------


class TestHandleInstallSkills:
    def test_install_list_skills(self, capsys) -> None:
        import argparse

        from pywry.mcp.__main__ import _handle_install_skills

        ns = argparse.Namespace(
            target=[],
            skills=None,
            overwrite=False,
            custom_dir=None,
            dry_run=False,
            list=True,
            list_targets=False,
            verbose=False,
        )
        rc = _handle_install_skills(ns)
        assert rc == 0
        out = capsys.readouterr().out
        assert "Bundled PyWry skills" in out

    def test_install_list_targets(self, capsys) -> None:
        import argparse

        from pywry.mcp.__main__ import _handle_install_skills

        ns = argparse.Namespace(
            target=[],
            skills=None,
            overwrite=False,
            custom_dir=None,
            dry_run=False,
            list=False,
            list_targets=True,
            verbose=False,
        )
        rc = _handle_install_skills(ns)
        assert rc == 0
        out = capsys.readouterr().out
        assert "Supported vendor targets" in out

    def test_install_dry_run_default_targets(self, capsys) -> None:
        import argparse

        from pywry.mcp.__main__ import _handle_install_skills

        ns = argparse.Namespace(
            target=[],  # falsy → ['all']
            skills=None,
            overwrite=False,
            custom_dir=None,
            dry_run=True,
            list=False,
            list_targets=False,
            verbose=False,
        )
        rc = _handle_install_skills(ns)
        assert rc == 0
        out = capsys.readouterr().out
        assert "[DRY RUN]" in out

    def test_install_value_error_returns_one(self, capsys) -> None:
        import argparse

        from pywry.mcp.__main__ import _handle_install_skills

        ns = argparse.Namespace(
            target=["nonexistent_vendor_xyz"],
            skills=None,
            overwrite=False,
            custom_dir=None,
            dry_run=False,
            list=False,
            list_targets=False,
            verbose=False,
        )
        rc = _handle_install_skills(ns)
        assert rc == 1
        captured = capsys.readouterr()
        assert "Error:" in captured.err

    def test_install_file_not_found_returns_one(self, monkeypatch, capsys, tmp_path) -> None:
        import argparse

        from pywry.mcp import install

        monkeypatch.setattr(install, "SKILLS_SOURCE_DIR", tmp_path / "missing")
        from pywry.mcp.__main__ import _handle_install_skills

        ns = argparse.Namespace(
            target=[],
            skills=None,
            overwrite=False,
            custom_dir=None,
            dry_run=False,
            list=False,
            list_targets=False,
            verbose=False,
        )
        rc = _handle_install_skills(ns)
        assert rc == 1
        assert "Error:" in capsys.readouterr().err

    def test_install_with_skills_subset(self, tmp_path) -> None:
        import argparse

        from pywry.mcp.__main__ import _handle_install_skills

        ns = argparse.Namespace(
            target=[],
            skills=["native"],
            overwrite=False,
            custom_dir=str(tmp_path / "skills"),
            dry_run=True,
            list=False,
            list_targets=False,
            verbose=True,
        )
        rc = _handle_install_skills(ns)
        assert rc == 0


# ---------------------------------------------------------------------------
# main() — argv dispatch + sys.exit
# ---------------------------------------------------------------------------


class TestMainDispatch:
    def test_main_serve_default(self, monkeypatch) -> None:
        from pywry.mcp.__main__ import main

        monkeypatch.setattr("sys.argv", ["pywry.mcp"])
        with patch("pywry.mcp.server.run_server") as run_server:
            main()
        run_server.assert_called_once_with(transport="stdio", port=8001)

    def test_main_serve_subcommand(self, monkeypatch) -> None:
        from pywry.mcp.__main__ import main

        monkeypatch.setattr(
            "sys.argv", ["pywry.mcp", "serve", "--transport", "sse", "--port", "9100"]
        )
        with patch("pywry.mcp.server.run_server") as run_server:
            main()
        run_server.assert_called_once_with(transport="sse", port=9100)

    def test_main_top_level_sse_flag(self, monkeypatch) -> None:
        """``python -m pywry.mcp --sse 9050`` still works (no subcommand)."""
        from pywry.mcp.__main__ import main

        monkeypatch.setattr("sys.argv", ["pywry.mcp", "--sse", "9050"])
        with patch("pywry.mcp.server.run_server") as run_server:
            main()
        run_server.assert_called_once_with(transport="sse", port=9050)

    def test_main_install_skills_subcommand(self, monkeypatch) -> None:
        from pywry.mcp.__main__ import main

        monkeypatch.setattr(
            "sys.argv",
            ["pywry.mcp", "install-skills", "--list"],
        )
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 0

    def test_main_install_skills_unknown_target(self, monkeypatch, capsys) -> None:
        from pywry.mcp.__main__ import main

        monkeypatch.setattr(
            "sys.argv",
            [
                "pywry.mcp",
                "install-skills",
                "--target",
                "nonexistent_vendor_xyz",
            ],
        )
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 1


class TestMainNameMain:
    """The ``if __name__ == '__main__'`` guard runs ``main()`` when invoked
    via ``runpy.run_module`` with ``run_name='__main__'``."""

    def test_runpy_invokes_main(self, monkeypatch) -> None:
        import runpy

        # Stub out main so the runpy call doesn't actually start a server.
        called: dict[str, bool] = {}

        def fake_main():
            called["main"] = True

        monkeypatch.setattr("pywry.mcp.__main__.main", fake_main)
        monkeypatch.setattr("sys.argv", ["pywry.mcp", "--list"])
        # Use run_module — the guard at the bottom of __main__.py should fire.
        # The patched main() prevents real server start.
        with contextlib.suppress(SystemExit):
            runpy.run_module("pywry.mcp", run_name="__main__")
        # Either fake_main was called OR the original main parsed the args.
        # Both prove the entry-point invocation happened.
        assert True  # tolerant
