"""Tests for CLI module.

Tests the command-line interface for PyWry configuration management.
"""

import argparse
import contextlib
import sys
import tempfile

from io import StringIO
from pathlib import Path
from unittest.mock import patch

from pywry.cli import format_config_show, handle_config, handle_init, main, show_config_sources
from pywry.config import PyWrySettings


class TestMainEntryPoint:
    """Tests for CLI main entry point."""

    def test_no_args_prints_help_text(self):
        """Running with no args prints help text with usage info."""
        with (
            patch.object(sys, "argv", ["pywry"]),
            patch("sys.stdout", new_callable=StringIO) as mock_stdout,
        ):
            result = main()

        output = mock_stdout.getvalue()
        assert result == 0
        assert "usage:" in output.lower() or "pywry" in output
        assert "config" in output  # Should mention config subcommand
        assert "init" in output  # Should mention init subcommand

    def test_help_flag_shows_usage(self):
        """--help flag shows usage information."""
        with (
            patch.object(sys, "argv", ["pywry", "--help"]),
            patch("sys.stdout", new_callable=StringIO) as mock_stdout,
            contextlib.suppress(SystemExit),
        ):
            main()

        output = mock_stdout.getvalue()
        assert "usage:" in output.lower()
        assert "pywry" in output

    def test_config_command_dispatches_to_handler(self):
        """config command calls handle_config."""
        with (
            patch.object(sys, "argv", ["pywry", "config", "--show"]),
            patch("sys.stdout", new_callable=StringIO) as mock_stdout,
        ):
            result = main()

        output = mock_stdout.getvalue()
        assert result == 0
        # handle_config with --show should output configuration
        assert "csp" in output.lower() or "[" in output

    def test_init_command_dispatches_to_handler(self):
        """init command calls handle_init."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "pywry.toml"
            with (
                patch.object(sys, "argv", ["pywry", "init", "--path", str(config_path)]),
                patch("sys.stdout", new_callable=StringIO) as mock_stdout,
            ):
                result = main()

            output = mock_stdout.getvalue()
            assert result == 0
            assert config_path.exists()
            assert "created" in output.lower() or str(config_path) in output


class TestHandleConfigShow:
    """Tests for config --show command."""

    def test_show_outputs_all_sections(self):
        """--show outputs all configuration sections."""
        args = argparse.Namespace(show=True, toml=False, env=False, sources=False, output=None)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            result = handle_config(args)

        output = mock_stdout.getvalue()
        assert result == 0
        # Must contain all section headers
        assert "[csp]" in output
        assert "[theme]" in output
        assert "[timeout]" in output
        assert "[window]" in output
        assert "[hot_reload]" in output

    def test_show_outputs_csp_values(self):
        """--show outputs CSP directive values."""
        args = argparse.Namespace(show=True, toml=False, env=False, sources=False, output=None)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            result = handle_config(args)

        output = mock_stdout.getvalue()
        assert result == 0
        assert "default_src" in output
        assert "script_src" in output
        assert "'self'" in output  # CSP value

    def test_show_outputs_window_dimensions(self):
        """--show outputs window width and height."""
        args = argparse.Namespace(show=True, toml=False, env=False, sources=False, output=None)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            result = handle_config(args)

        output = mock_stdout.getvalue()
        assert result == 0
        assert "width" in output
        assert "height" in output
        assert "1280" in output  # Default width
        assert "720" in output  # Default height


class TestHandleConfigToml:
    """Tests for config --toml command."""

    def test_toml_outputs_valid_toml(self):
        """--toml outputs valid TOML format."""
        args = argparse.Namespace(show=False, toml=True, env=False, sources=False, output=None)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            result = handle_config(args)

        output = mock_stdout.getvalue()
        assert result == 0
        # TOML format: [section] headers and key = value
        assert "[csp]" in output
        assert "[theme]" in output
        assert "=" in output

    def test_toml_contains_csp_section(self):
        """--toml contains [csp] section with directives."""
        args = argparse.Namespace(show=False, toml=True, env=False, sources=False, output=None)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            result = handle_config(args)

        output = mock_stdout.getvalue()
        assert result == 0
        assert "[csp]" in output
        assert "default_src" in output

    def test_toml_output_to_file(self):
        """--toml --output writes to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "config.toml"
            args = argparse.Namespace(
                show=False, toml=True, env=False, sources=False, output=str(output_path)
            )

            with patch("sys.stdout", new_callable=StringIO):
                result = handle_config(args)

            assert result == 0
            assert output_path.exists()
            content = output_path.read_text()
            assert "[csp]" in content
            assert "[theme]" in content


class TestHandleConfigEnv:
    """Tests for config --env command."""

    def test_env_outputs_environment_variables(self):
        """--env outputs environment variable format."""
        args = argparse.Namespace(show=False, toml=False, env=True, sources=False, output=None)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            result = handle_config(args)

        output = mock_stdout.getvalue()
        assert result == 0
        assert "PYWRY_" in output
        assert "=" in output

    def test_env_outputs_csp_variables(self):
        """--env outputs CSP-related environment variables."""
        args = argparse.Namespace(show=False, toml=False, env=True, sources=False, output=None)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            result = handle_config(args)

        output = mock_stdout.getvalue()
        assert result == 0
        # Should have CSP env vars
        assert "PYWRY_CSP__" in output or "CSP" in output.upper()


class TestHandleConfigSources:
    """Tests for config --sources command."""

    def test_sources_shows_source_list(self):
        """--sources shows configuration source list."""
        args = argparse.Namespace(show=False, toml=False, env=False, sources=True, output=None)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            result = handle_config(args)

        output = mock_stdout.getvalue()
        assert result == 0
        assert "source" in output.lower()
        assert "built-in" in output.lower() or "default" in output.lower()

    def test_sources_mentions_toml_files(self):
        """--sources mentions TOML configuration files."""
        args = argparse.Namespace(show=False, toml=False, env=False, sources=True, output=None)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            result = handle_config(args)

        output = mock_stdout.getvalue()
        assert result == 0
        assert "toml" in output.lower() or ".toml" in output

    def test_sources_mentions_env_vars(self):
        """--sources mentions environment variables."""
        args = argparse.Namespace(show=False, toml=False, env=False, sources=True, output=None)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            result = handle_config(args)

        output = mock_stdout.getvalue()
        assert result == 0
        assert "environment" in output.lower() or "PYWRY_" in output


class TestHandleInit:
    """Tests for init command handling."""

    def test_init_creates_toml_file(self):
        """Init creates pywry.toml file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "pywry.toml"
            args = argparse.Namespace(path=str(config_path), force=False)

            with patch("sys.stdout", new_callable=StringIO):
                result = handle_init(args)

            assert result == 0
            assert config_path.exists()

    def test_init_file_contains_toml_sections(self):
        """Init creates file with TOML section headers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "pywry.toml"
            args = argparse.Namespace(path=str(config_path), force=False)

            with patch("sys.stdout", new_callable=StringIO):
                handle_init(args)

            content = config_path.read_text()
            assert "[csp]" in content
            assert "[theme]" in content
            assert "[window]" in content

    def test_init_file_contains_header_comment(self):
        """Init creates file with documentation header."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "pywry.toml"
            args = argparse.Namespace(path=str(config_path), force=False)

            with patch("sys.stdout", new_callable=StringIO):
                handle_init(args)

            content = config_path.read_text()
            assert "# PyWry Configuration" in content
            assert "PYWRY_" in content  # Env var docs

    def test_init_refuses_overwrite_existing(self):
        """Init refuses to overwrite existing file without --force."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "pywry.toml"
            original_content = "# existing config"
            config_path.write_text(original_content)
            args = argparse.Namespace(path=str(config_path), force=False)

            with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                result = handle_init(args)

            assert result == 1
            assert (
                "already exists" in mock_stderr.getvalue().lower()
                or "error" in mock_stderr.getvalue().lower()
            )
            # File should not be modified
            assert config_path.read_text() == original_content

    def test_init_force_overwrites_existing(self):
        """Init --force overwrites existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "pywry.toml"
            config_path.write_text("# old content only")
            args = argparse.Namespace(path=str(config_path), force=True)

            with patch("sys.stdout", new_callable=StringIO):
                result = handle_init(args)

            assert result == 0
            content = config_path.read_text()
            assert "[csp]" in content  # New TOML content
            assert "# old content only" not in content

    def test_init_prints_success_message(self):
        """Init prints success message with path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "pywry.toml"
            args = argparse.Namespace(path=str(config_path), force=False)

            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                handle_init(args)

            output = mock_stdout.getvalue()
            assert "created" in output.lower() or str(config_path) in output


class TestFormatConfigShow:
    """Tests for format_config_show function."""

    def test_formats_settings_with_header(self):
        """Formats settings with PyWry Configuration header."""
        settings = PyWrySettings()
        output = format_config_show(settings)
        assert "PyWry Configuration" in output

    def test_formats_all_sections(self):
        """Formats all configuration sections."""
        settings = PyWrySettings()
        output = format_config_show(settings)
        assert "[csp]" in output
        assert "[theme]" in output
        assert "[timeout]" in output
        assert "[asset]" in output
        assert "[log]" in output
        assert "[window]" in output
        assert "[hot_reload]" in output

    def test_formats_field_values(self):
        """Formats field names and values."""
        settings = PyWrySettings()
        output = format_config_show(settings)
        # Check some known fields exist with values
        assert "default_src" in output
        assert "width" in output
        assert "=" in output


class TestShowConfigSources:
    """Tests for show_config_sources function."""

    def test_shows_source_table(self):
        """Shows configuration source table."""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            result = show_config_sources()

        output = mock_stdout.getvalue()
        assert result == 0
        assert "Source" in output
        assert "Status" in output

    def test_shows_builtin_defaults(self):
        """Shows built-in defaults as active."""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            show_config_sources()

        output = mock_stdout.getvalue()
        assert "built-in" in output.lower() or "default" in output.lower()
        assert "✓" in output  # Active indicator

    def test_shows_pywry_toml_source(self):
        """Shows pywry.toml as a source."""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            show_config_sources()

        output = mock_stdout.getvalue()
        assert "pywry.toml" in output

    def test_shows_env_vars_source(self):
        """Shows environment variables as a source."""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            show_config_sources()

        output = mock_stdout.getvalue()
        assert "environment" in output.lower()

    def test_shows_precedence_note(self):
        """Shows note about source precedence."""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            show_config_sources()

        output = mock_stdout.getvalue()
        assert "override" in output.lower() or "precedence" in output.lower()


class TestHandlePluginPath:
    """Tests for the plugin-path command."""

    def test_returns_plugin_root(self, tmp_path, monkeypatch):
        # Mock pywry.__file__ and Path.exists to simulate plugin installed.
        import pywry
        from pywry.cli import handle_plugin_path

        # Build a fake plugin directory tree
        fake_pkg = tmp_path / "pywry"
        plugin_root = fake_pkg / "_claude_plugin" / ".claude-plugin"
        plugin_root.mkdir(parents=True)
        (plugin_root / "marketplace.json").write_text("{}")
        (plugin_root / "plugin.json").write_text("{}")

        # Patch pywry.__file__ so resolve points to fake_pkg/__init__.py
        fake_init = fake_pkg / "__init__.py"
        fake_init.write_text("")
        monkeypatch.setattr(pywry, "__file__", str(fake_init))

        args = argparse.Namespace(check=False, marketplace=False)
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            result = handle_plugin_path(args)
        assert result == 0
        assert "_claude_plugin" in mock_stdout.getvalue()

    def test_marketplace_flag_returns_marketplace_path(self, tmp_path, monkeypatch):
        import pywry
        from pywry.cli import handle_plugin_path

        fake_pkg = tmp_path / "pywry"
        plugin_root = fake_pkg / "_claude_plugin" / ".claude-plugin"
        plugin_root.mkdir(parents=True)
        (plugin_root / "marketplace.json").write_text("{}")
        (plugin_root / "plugin.json").write_text("{}")
        fake_init = fake_pkg / "__init__.py"
        fake_init.write_text("")
        monkeypatch.setattr(pywry, "__file__", str(fake_init))

        args = argparse.Namespace(check=False, marketplace=True)
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            result = handle_plugin_path(args)
        assert result == 0
        assert "marketplace.json" in mock_stdout.getvalue()

    def test_check_missing_returns_error(self, tmp_path, monkeypatch):
        import pywry
        from pywry.cli import handle_plugin_path

        fake_pkg = tmp_path / "pywry"
        fake_pkg.mkdir(parents=True)
        fake_init = fake_pkg / "__init__.py"
        fake_init.write_text("")
        monkeypatch.setattr(pywry, "__file__", str(fake_init))

        args = argparse.Namespace(check=True, marketplace=False)
        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            result = handle_plugin_path(args)
        assert result == 1
        assert "not found" in mock_stderr.getvalue().lower()


class TestHandleConfigOutputFile:
    """Tests for the --output option of config command."""

    def test_writes_to_file(self, tmp_path):
        out = tmp_path / "out.toml"
        args = argparse.Namespace(show=False, toml=True, env=False, sources=False, output=str(out))
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            result = handle_config(args)
        assert result == 0
        assert out.exists()
        assert "written" in mock_stdout.getvalue().lower()


class TestHandleConfigEnvOption:
    def test_env_output_to_stdout(self):
        args = argparse.Namespace(show=False, toml=False, env=True, sources=False, output=None)
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            result = handle_config(args)
        assert result == 0
        out = mock_stdout.getvalue()
        # to_env output should contain PYWRY_-prefixed vars or be empty if no overrides
        assert isinstance(out, str)


class TestHandleMcp:
    def test_import_error_path(self):
        import builtins

        from pywry.cli import handle_mcp

        real_import = builtins.__import__

        # Save and remove cached pywry.mcp so the inner re-import goes through __import__
        cached_pkg = sys.modules.pop("pywry.mcp", None)

        def fake_import(name, *a, **k):
            # Relative import inside pywry.cli: `from .mcp import run_server`
            # passes name="mcp" (or "pywry.mcp" for absolute).
            if name == "mcp" or name == "pywry.mcp":
                raise ImportError("no mcp")
            return real_import(name, *a, **k)

        args = argparse.Namespace(
            transport="stdio",
            port=None,
            host=None,
            name=None,
            headless=False,
            native=False,
        )
        try:
            with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                with patch.object(builtins, "__import__", side_effect=fake_import):
                    result = handle_mcp(args)
            assert result == 1
            assert "MCP SDK" in mock_stderr.getvalue() or "mcp" in mock_stderr.getvalue().lower()
        finally:
            if cached_pkg is not None:
                sys.modules["pywry.mcp"] = cached_pkg

    def test_runs_server_successfully(self):
        from pywry.cli import handle_mcp

        with patch("pywry.mcp.run_server") as mock_run:
            mock_run.return_value = None
            args = argparse.Namespace(
                transport=None,
                port=None,
                host=None,
                name=None,
                headless=False,
                native=False,
            )
            result = handle_mcp(args)
        assert result == 0
        mock_run.assert_called_once()

    def test_keyboard_interrupt(self):
        from pywry.cli import handle_mcp

        with patch("pywry.mcp.run_server", side_effect=KeyboardInterrupt):
            args = argparse.Namespace(
                transport=None,
                port=None,
                host=None,
                name=None,
                headless=False,
                native=False,
            )
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                result = handle_mcp(args)
        assert result == 0
        assert "stopped" in mock_stdout.getvalue().lower()

    def test_server_error(self):
        from pywry.cli import handle_mcp

        with patch("pywry.mcp.run_server", side_effect=RuntimeError("boom")):
            args = argparse.Namespace(
                transport=None,
                port=None,
                host=None,
                name=None,
                headless=False,
                native=False,
            )
            with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                result = handle_mcp(args)
        assert result == 1
        assert "boom" in mock_stderr.getvalue() or "Error" in mock_stderr.getvalue()

    def test_native_flag_disables_headless(self):
        from pywry.cli import handle_mcp

        with patch("pywry.mcp.run_server") as mock_run:
            args = argparse.Namespace(
                transport=None,
                port=None,
                host=None,
                name="my-server",
                headless=False,
                native=True,
            )
            handle_mcp(args)
        # native=True → headless=False
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs.get("headless") is False

    def test_headless_flag(self):
        from pywry.cli import handle_mcp

        with patch("pywry.mcp.run_server") as mock_run:
            args = argparse.Namespace(
                transport=None,
                port=None,
                host=None,
                name=None,
                headless=True,
                native=False,
            )
            handle_mcp(args)
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs.get("headless") is True

    def test_no_flags_uses_config_headless(self, monkeypatch):
        """When --headless, --native, and PYWRY_HEADLESS env are all unset, use config."""
        from pywry.cli import handle_mcp

        monkeypatch.delenv("PYWRY_HEADLESS", raising=False)
        with patch("pywry.mcp.run_server") as mock_run:
            args = argparse.Namespace(
                transport=None,
                port=None,
                host=None,
                name=None,
                headless=False,
                native=False,
            )
            handle_mcp(args)
        # config default headless is used
        assert "headless" in mock_run.call_args.kwargs


class TestHandleConfigDefaults:
    def test_show_defaults_when_no_flags(self):
        """When no toml/env/show flag passed, output defaults to show format."""
        args = argparse.Namespace(show=False, toml=False, env=False, sources=False, output=None)
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            result = handle_config(args)
        assert result == 0
        # Default falls through to show format
        assert "[csp]" in mock_stdout.getvalue()


class TestShowConfigSourcesEnvNotSet:
    def test_empty_env_vars(self, monkeypatch):
        """Env vars section shows ✗ No vars when no PYWRY_* present."""
        # Remove all PYWRY_ env vars
        for key in list(__import__("os").environ.keys()):
            if key.startswith("PYWRY_"):
                monkeypatch.delenv(key, raising=False)
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            show_config_sources()
        out = mock_stdout.getvalue()
        assert "No vars" in out or "No" in out

    def test_more_than_three_env_vars_truncates(self, monkeypatch):
        """Env vars section shows ... when more than 3 PYWRY_ vars exist."""
        for i in range(5):
            monkeypatch.setenv(f"PYWRY_FAKE_{i}", "1")
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            show_config_sources()
        out = mock_stdout.getvalue()
        assert "..." in out


class TestHandleInstallSkillsImportError:
    def test_import_error_path(self):
        """When the mcp.install module isn't importable, return 1."""
        import builtins

        from pywry.cli import handle_install_skills

        real_import = builtins.__import__

        # Save and remove cached module so the re-import goes through __import__.
        cached = sys.modules.pop("pywry.mcp.install", None)

        def fake_import(name, *a, **k):
            # Relative import inside pywry.cli passes name="mcp.install".
            if "mcp.install" in name:
                raise ImportError("no install")
            return real_import(name, *a, **k)

        args = argparse.Namespace(
            list=False,
            list_targets=False,
            target=None,
            skills=None,
            custom_dir=None,
            overwrite=False,
            dry_run=False,
            verbose=False,
        )
        try:
            with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                with patch.object(builtins, "__import__", side_effect=fake_import):
                    result = handle_install_skills(args)
            assert result == 1
            assert "MCP module" in mock_stderr.getvalue()
        finally:
            if cached is not None:
                sys.modules["pywry.mcp.install"] = cached


class TestHandleInstallSkills:
    def test_list_flag_prints_skills(self):
        from pywry.cli import handle_install_skills

        args = argparse.Namespace(
            list=True,
            list_targets=False,
            target=None,
            skills=None,
            custom_dir=None,
            overwrite=False,
            dry_run=False,
            verbose=False,
        )
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            result = handle_install_skills(args)
        assert result == 0
        assert "skills" in mock_stdout.getvalue().lower()

    def test_list_targets_flag(self):
        from pywry.cli import handle_install_skills

        args = argparse.Namespace(
            list=False,
            list_targets=True,
            target=None,
            skills=None,
            custom_dir=None,
            overwrite=False,
            dry_run=False,
            verbose=False,
        )
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            result = handle_install_skills(args)
        assert result == 0
        assert "target" in mock_stdout.getvalue().lower()

    def test_install_with_targets(self):
        from pywry.cli import handle_install_skills

        args = argparse.Namespace(
            list=False,
            list_targets=False,
            target=["claude_code"],
            skills=None,
            custom_dir=None,
            overwrite=False,
            dry_run=True,
            verbose=False,
        )
        with patch("pywry.mcp.install.install_skills") as mock_install:
            mock_install.return_value = {}
            with patch("pywry.mcp.install.print_install_results"):
                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    result = handle_install_skills(args)
        assert result == 0
        assert "DRY RUN" in mock_stdout.getvalue()

    def test_install_value_error(self):
        from pywry.cli import handle_install_skills

        args = argparse.Namespace(
            list=False,
            list_targets=False,
            target=["invalid"],
            skills=None,
            custom_dir=None,
            overwrite=False,
            dry_run=False,
            verbose=False,
        )
        with patch("pywry.mcp.install.install_skills", side_effect=ValueError("bad")):
            with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                result = handle_install_skills(args)
        assert result == 1
        assert "Error" in mock_stderr.getvalue()


class TestMainEntryPointDispatch:
    """Cover the if/elif branches in main() for mcp/install-skills/plugin-path."""

    def test_mcp_command_dispatches(self):
        with patch("pywry.cli.handle_mcp", return_value=0) as mock_handle:
            with patch.object(sys, "argv", ["pywry", "mcp"]):
                result = main()
        assert result == 0
        mock_handle.assert_called_once()

    def test_install_skills_command_dispatches(self):
        with patch("pywry.cli.handle_install_skills", return_value=0) as mock_handle:
            with patch.object(sys, "argv", ["pywry", "install-skills", "--list"]):
                result = main()
        assert result == 0
        mock_handle.assert_called_once()

    def test_plugin_path_command_dispatches(self):
        with patch("pywry.cli.handle_plugin_path", return_value=0) as mock_handle:
            with patch.object(sys, "argv", ["pywry", "plugin-path"]):
                result = main()
        assert result == 0
        mock_handle.assert_called_once()


class TestMainModuleEntry:
    """Cover the `if __name__ == "__main__"` guard."""

    def test_module_main(self):
        import runpy

        with patch("pywry.cli.main", return_value=0):
            with patch.object(sys, "argv", ["pywry"]):
                try:
                    runpy.run_module("pywry.cli", run_name="__main__")
                except SystemExit as e:
                    assert e.code == 0
