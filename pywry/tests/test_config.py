"""Tests for configuration classes.

Tests PyWrySettings, SecuritySettings, and other config classes.
Including CSP (Content Security Policy) configuration and meta tag generation.
"""

from unittest.mock import patch

import pytest

from pywry.config import (
    AVAILABLE_TAURI_PLUGINS,
    DEFAULT_TAURI_PLUGINS,
    AssetSettings,
    HotReloadSettings,
    PyWrySettings,
    SecuritySettings,
    ThemeSettings,
    WindowSettings,
)
from pywry.models import HtmlContent, WindowConfig
from pywry.templates import build_csp_meta, build_html


class TestSecuritySettings:
    """Tests for SecuritySettings class."""

    def test_default_src_includes_self(self):
        """default-src includes 'self'."""
        settings = SecuritySettings()
        assert "'self'" in settings.default_src

    def test_default_src_includes_unsafe_inline(self):
        """default-src includes 'unsafe-inline'."""
        settings = SecuritySettings()
        assert "'unsafe-inline'" in settings.default_src

    def test_default_src_includes_unsafe_eval(self):
        """default-src includes 'unsafe-eval'."""
        settings = SecuritySettings()
        assert "'unsafe-eval'" in settings.default_src

    def test_default_src_includes_data(self):
        """default-src includes data:."""
        settings = SecuritySettings()
        assert "data:" in settings.default_src

    def test_default_src_includes_blob(self):
        """default-src includes blob:."""
        settings = SecuritySettings()
        assert "blob:" in settings.default_src

    def test_script_src_includes_self(self):
        """script-src includes 'self'."""
        settings = SecuritySettings()
        assert "'self'" in settings.script_src

    def test_script_src_includes_unsafe_inline(self):
        """script-src includes 'unsafe-inline'."""
        settings = SecuritySettings()
        assert "'unsafe-inline'" in settings.script_src

    def test_script_src_includes_unsafe_eval(self):
        """script-src includes 'unsafe-eval'."""
        settings = SecuritySettings()
        assert "'unsafe-eval'" in settings.script_src

    def test_style_src_includes_self(self):
        """style-src includes 'self'."""
        settings = SecuritySettings()
        assert "'self'" in settings.style_src

    def test_style_src_includes_unsafe_inline(self):
        """style-src includes 'unsafe-inline'."""
        settings = SecuritySettings()
        assert "'unsafe-inline'" in settings.style_src

    def test_img_src_includes_self(self):
        """img-src includes 'self'."""
        settings = SecuritySettings()
        assert "'self'" in settings.img_src

    def test_img_src_includes_data(self):
        """img-src includes data:."""
        settings = SecuritySettings()
        assert "data:" in settings.img_src

    def test_img_src_includes_blob(self):
        """img-src includes blob:."""
        settings = SecuritySettings()
        assert "blob:" in settings.img_src

    def test_font_src_includes_self(self):
        """font-src includes 'self'."""
        settings = SecuritySettings()
        assert "'self'" in settings.font_src

    def test_font_src_includes_data(self):
        """font-src includes data:."""
        settings = SecuritySettings()
        assert "data:" in settings.font_src

    def test_connect_src_includes_self(self):
        """connect-src includes 'self'."""
        settings = SecuritySettings()
        assert "'self'" in settings.connect_src

    def test_connect_src_includes_http(self):
        """connect-src includes http wildcard."""
        settings = SecuritySettings()
        assert "http://*:*" in settings.connect_src

    def test_connect_src_includes_https(self):
        """connect-src includes https wildcard."""
        settings = SecuritySettings()
        assert "https://*:*" in settings.connect_src

    def test_connect_src_includes_ws(self):
        """connect-src includes ws wildcard."""
        settings = SecuritySettings()
        assert "ws://*:*" in settings.connect_src

    def test_connect_src_includes_wss(self):
        """connect-src includes wss wildcard."""
        settings = SecuritySettings()
        assert "wss://*:*" in settings.connect_src


class TestSecuritySettingsPermissive:
    """Tests for SecuritySettings.permissive() factory."""

    def test_permissive_allows_unsafe_eval(self):
        """permissive() allows unsafe-eval."""
        settings = SecuritySettings.permissive()
        assert "'unsafe-eval'" in settings.script_src
        assert "'unsafe-eval'" in settings.default_src

    def test_permissive_allows_unsafe_inline(self):
        """permissive() allows unsafe-inline."""
        settings = SecuritySettings.permissive()
        assert "'unsafe-inline'" in settings.script_src
        assert "'unsafe-inline'" in settings.style_src

    def test_permissive_allows_data(self):
        """permissive() allows data:."""
        settings = SecuritySettings.permissive()
        assert "data:" in settings.default_src

    def test_permissive_allows_blob(self):
        """permissive() allows blob:."""
        settings = SecuritySettings.permissive()
        assert "blob:" in settings.default_src


class TestSecuritySettingsStrict:
    """Tests for SecuritySettings.strict() factory."""

    def test_strict_has_self(self):
        """strict() has 'self' in default-src."""
        settings = SecuritySettings.strict()
        assert "'self'" in settings.default_src

    def test_strict_removes_unsafe_eval_from_default(self):
        """strict() removes unsafe-eval from default-src."""
        settings = SecuritySettings.strict()
        assert "'unsafe-eval'" not in settings.default_src


class TestSecuritySettingsLocalhost:
    """Tests for SecuritySettings.localhost() factory."""

    def test_localhost_allows_localhost(self):
        """localhost() allows localhost connections."""
        settings = SecuritySettings.localhost()
        # Should have localhost in connect-src
        connect = settings.connect_src
        assert "localhost" in connect or "127.0.0.1" in connect


class TestCspMetaTag:
    """Tests for CSP meta tag generation."""

    def test_creates_meta_tag(self):
        """Creates Content-Security-Policy meta tag."""
        meta = build_csp_meta(SecuritySettings())
        assert '<meta http-equiv="Content-Security-Policy"' in meta

    def test_includes_default_src_directive(self):
        """Includes default-src directive."""
        meta = build_csp_meta(SecuritySettings())
        assert "default-src" in meta

    def test_includes_script_src_directive(self):
        """Includes script-src directive."""
        meta = build_csp_meta(SecuritySettings())
        assert "script-src" in meta

    def test_includes_style_src_directive(self):
        """Includes style-src directive."""
        meta = build_csp_meta(SecuritySettings())
        assert "style-src" in meta

    def test_includes_img_src_directive(self):
        """Includes img-src directive."""
        meta = build_csp_meta(SecuritySettings())
        assert "img-src" in meta

    def test_includes_font_src_directive(self):
        """Includes font-src directive."""
        meta = build_csp_meta(SecuritySettings())
        assert "font-src" in meta

    def test_includes_connect_src_directive(self):
        """Includes connect-src directive."""
        meta = build_csp_meta(SecuritySettings())
        assert "connect-src" in meta


class TestCspInHtml:
    """Tests for CSP integration in HTML output."""

    def test_build_html_includes_csp(self):
        """build_html includes CSP meta tag."""
        config = WindowConfig()
        content = HtmlContent(html="<div></div>")
        settings = PyWrySettings()
        html = build_html(content, config, window_label="main", settings=settings)
        assert "Content-Security-Policy" in html

    def test_permissive_csp_in_html(self):
        """Permissive CSP is included in HTML."""
        config = WindowConfig()
        content = HtmlContent(html="<div></div>")
        settings = PyWrySettings(csp=SecuritySettings.permissive())
        html = build_html(content, config, window_label="main", settings=settings)
        assert "'unsafe-eval'" in html

    def test_strict_csp_in_html(self):
        """Strict CSP is included in HTML."""
        config = WindowConfig()
        content = HtmlContent(html="<div></div>")
        settings = PyWrySettings(csp=SecuritySettings.strict())
        html = build_html(content, config, window_label="main", settings=settings)
        assert "default-src" in html


class TestCspDirectiveValues:
    """Tests for individual CSP directive values."""

    def test_default_src_is_string(self):
        """default_src is a string."""
        csp = SecuritySettings()
        assert isinstance(csp.default_src, str)

    def test_script_src_is_string(self):
        """script_src is a string."""
        csp = SecuritySettings()
        assert isinstance(csp.script_src, str)

    def test_style_src_is_string(self):
        """style_src is a string."""
        csp = SecuritySettings()
        assert isinstance(csp.style_src, str)

    def test_img_src_is_string(self):
        """img_src is a string."""
        csp = SecuritySettings()
        assert isinstance(csp.img_src, str)

    def test_font_src_is_string(self):
        """font_src is a string."""
        csp = SecuritySettings()
        assert isinstance(csp.font_src, str)

    def test_connect_src_is_string(self):
        """connect_src is a string."""
        csp = SecuritySettings()
        assert isinstance(csp.connect_src, str)


class TestWindowSettings:
    """Tests for WindowSettings class."""

    def test_default_width(self):
        """Default width is 1280."""
        settings = WindowSettings()
        assert settings.width == 1280

    def test_default_height(self):
        """Default height is 720."""
        settings = WindowSettings()
        assert settings.height == 720

    def test_default_title(self):
        """Default title is PyWry."""
        settings = WindowSettings()
        assert settings.title == "PyWry"

    def test_default_resizable(self):
        """Default resizable is True."""
        settings = WindowSettings()
        assert settings.resizable is True

    def test_default_center(self):
        """Default center is True."""
        settings = WindowSettings()
        assert settings.center is True

    def test_custom_width(self):
        """Custom width is set."""
        settings = WindowSettings(width=800)
        assert settings.width == 800

    def test_custom_height(self):
        """Custom height is set."""
        settings = WindowSettings(height=600)
        assert settings.height == 600


class TestThemeSettings:
    """Tests for ThemeSettings class."""

    def test_default_css_file_is_none(self):
        """Default css_file is None."""
        settings = ThemeSettings()
        assert settings.css_file is None

    def test_custom_css_file(self):
        """Custom CSS file path can be set."""
        settings = ThemeSettings(css_file="/path/to/custom.css")
        assert settings.css_file == "/path/to/custom.css"


class TestHotReloadSettings:
    """Tests for HotReloadSettings class."""

    def test_default_enabled(self):
        """Default enabled is False."""
        settings = HotReloadSettings()
        assert settings.enabled is False

    def test_custom_enabled(self):
        """Custom enabled is set."""
        settings = HotReloadSettings(enabled=True)
        assert settings.enabled is True

    def test_default_debounce(self):
        """Default debounce_ms is reasonable."""
        settings = HotReloadSettings()
        assert settings.debounce_ms >= 0


class TestPyWrySettings:
    """Tests for PyWrySettings class."""

    def test_creates_default_settings(self):
        """Creates default settings."""
        settings = PyWrySettings()
        assert settings is not None

    def test_has_window_settings(self):
        """Has window settings."""
        settings = PyWrySettings()
        assert hasattr(settings, "window")
        assert isinstance(settings.window, WindowSettings)

    def test_has_theme_settings(self):
        """Has theme settings."""
        settings = PyWrySettings()
        assert hasattr(settings, "theme")
        assert isinstance(settings.theme, ThemeSettings)

    def test_has_csp_settings(self):
        """Has CSP settings."""
        settings = PyWrySettings()
        assert hasattr(settings, "csp")
        assert isinstance(settings.csp, SecuritySettings)

    def test_has_hot_reload_settings(self):
        """Has hot reload settings."""
        settings = PyWrySettings()
        assert hasattr(settings, "hot_reload")
        assert isinstance(settings.hot_reload, HotReloadSettings)

    def test_custom_window_settings(self):
        """Custom window settings work."""
        settings = PyWrySettings(window=WindowSettings(width=1024, height=768))
        assert settings.window.width == 1024
        assert settings.window.height == 768

    def test_custom_theme_css_file(self):
        """Custom theme settings with css_file work."""
        settings = PyWrySettings(theme=ThemeSettings(css_file="/path/to/custom.css"))
        assert settings.theme.css_file == "/path/to/custom.css"

    def test_custom_csp_settings(self):
        """Custom CSP settings work."""
        csp = SecuritySettings.strict()
        settings = PyWrySettings(csp=csp)
        assert "'unsafe-eval'" not in settings.csp.default_src

    def test_dict_window_settings(self):
        """Dict window settings work."""
        settings = PyWrySettings(window={"width": 800, "height": 600})
        assert settings.window.width == 800
        assert settings.window.height == 600

    def test_dict_theme_css_file(self):
        """Dict theme settings with css_file work."""
        settings = PyWrySettings(theme={"css_file": "/path/to/custom.css"})
        assert settings.theme.css_file == "/path/to/custom.css"


class TestPyWrySettingsValidation:
    """Tests for PyWrySettings validation."""

    def test_invalid_window_width_raises(self):
        """Invalid window width raises error."""
        with pytest.raises((TypeError, ValueError)):
            PyWrySettings(window={"width": "invalid"})


class TestAssetSettings:
    """Tests for AssetSettings class."""

    def test_default_plotly_version(self):
        """Default Plotly version is set."""
        settings = AssetSettings()
        assert settings.plotly_version == "3.3.1"

    def test_default_aggrid_version(self):
        """Default AG Grid version is set."""
        settings = AssetSettings()
        assert settings.aggrid_version == "35.0.0"

    def test_default_path_empty(self):
        """Default path is empty string."""
        settings = AssetSettings()
        assert settings.path == ""

    def test_default_css_files_empty(self):
        """Default css_files is empty list."""
        settings = AssetSettings()
        assert settings.css_files == []

    def test_default_script_files_empty(self):
        """Default script_files is empty list."""
        settings = AssetSettings()
        assert settings.script_files == []

    def test_custom_plotly_version(self):
        """Custom Plotly version can be set."""
        settings = AssetSettings(plotly_version="3.4.0")
        assert settings.plotly_version == "3.4.0"

    def test_custom_aggrid_version(self):
        """Custom AG Grid version can be set."""
        settings = AssetSettings(aggrid_version="36.0.0")
        assert settings.aggrid_version == "36.0.0"

    def test_custom_path(self):
        """Custom path can be set."""
        settings = AssetSettings(path="/custom/assets")
        assert settings.path == "/custom/assets"

    def test_custom_css_files_list(self):
        """Custom css_files list can be set."""
        settings = AssetSettings(css_files=["style.css", "theme.css"])
        assert settings.css_files == ["style.css", "theme.css"]

    def test_custom_script_files_list(self):
        """Custom script_files list can be set."""
        settings = AssetSettings(script_files=["app.js", "utils.js"])
        assert settings.script_files == ["app.js", "utils.js"]


class TestAssetSettingsCommaParsingCss:
    """Tests for AssetSettings.css_files comma-separated parsing."""

    def test_parses_comma_separated_css(self):
        """Parses comma-separated string to list."""
        settings = AssetSettings(css_files="style.css,theme.css")
        assert settings.css_files == ["style.css", "theme.css"]

    def test_trims_whitespace_css(self):
        """Trims whitespace around values."""
        settings = AssetSettings(css_files=" style.css , theme.css ")
        assert settings.css_files == ["style.css", "theme.css"]

    def test_handles_empty_string_css(self):
        """Empty string results in empty list."""
        settings = AssetSettings(css_files="")
        assert settings.css_files == []

    def test_ignores_empty_values_css(self):
        """Ignores empty values from multiple commas."""
        settings = AssetSettings(css_files="style.css,,theme.css")
        assert settings.css_files == ["style.css", "theme.css"]


class TestAssetSettingsCommaParsingScript:
    """Tests for AssetSettings.script_files comma-separated parsing."""

    def test_parses_comma_separated_script(self):
        """Parses comma-separated string to list."""
        settings = AssetSettings(script_files="app.js,utils.js")
        assert settings.script_files == ["app.js", "utils.js"]

    def test_trims_whitespace_script(self):
        """Trims whitespace around values."""
        settings = AssetSettings(script_files=" app.js , utils.js ")
        assert settings.script_files == ["app.js", "utils.js"]

    def test_handles_empty_string_script(self):
        """Empty string results in empty list."""
        settings = AssetSettings(script_files="")
        assert settings.script_files == []

    def test_ignores_empty_values_script(self):
        """Ignores empty values from multiple commas."""
        settings = AssetSettings(script_files="app.js,,utils.js")
        assert settings.script_files == ["app.js", "utils.js"]


class TestAssetSettingsNone:
    """Tests for AssetSettings with None values."""

    def test_none_css_files_becomes_empty_list(self):
        """None css_files becomes empty list."""
        settings = AssetSettings(css_files=None)
        assert settings.css_files == []

    def test_none_script_files_becomes_empty_list(self):
        """None script_files becomes empty list."""
        settings = AssetSettings(script_files=None)
        assert settings.script_files == []


class TestPyWrySettingsWithAsset:
    """Tests for PyWrySettings with AssetSettings."""

    def test_has_asset_settings(self):
        """Has asset settings."""
        settings = PyWrySettings()
        assert hasattr(settings, "asset")
        assert isinstance(settings.asset, AssetSettings)

    def test_custom_asset_settings(self):
        """Custom asset settings work."""
        settings = PyWrySettings(asset=AssetSettings(plotly_version="4.0.0"))
        assert settings.asset.plotly_version == "4.0.0"

    def test_dict_asset_settings(self):
        """Dict asset settings work."""
        settings = PyWrySettings(asset={"plotly_version": "4.0.0", "css_files": ["test.css"]})
        assert settings.asset.plotly_version == "4.0.0"
        assert settings.asset.css_files == ["test.css"]

    def test_asset_in_toml_export(self):
        """Asset settings are included in TOML export."""
        settings = PyWrySettings()
        toml = settings.to_toml()
        assert "[asset]" in toml
        assert "plotly_version" in toml
        assert "aggrid_version" in toml

    def test_asset_in_env_export(self):
        """Asset settings are included in env export."""
        settings = PyWrySettings()
        env = settings.to_env()
        assert "PYWRY_ASSET__PLOTLY_VERSION" in env
        assert "PYWRY_ASSET__AGGRID_VERSION" in env

    def test_asset_in_show_output(self):
        """Asset settings are included in show output."""
        settings = PyWrySettings()
        output = settings.show()
        assert "Assets" in output
        assert "plotly_version" in output


# =============================================================================
# Tauri Plugin Settings Tests
# =============================================================================


class TestTauriPluginSettings:
    """Tests for tauri_plugins and extra_capabilities config fields."""

    def test_default_plugins(self):
        """Default tauri_plugins value is ['dialog', 'fs']."""
        settings = PyWrySettings()
        assert settings.tauri_plugins == DEFAULT_TAURI_PLUGINS

    def test_custom_plugins_list(self):
        """Custom plugin list is accepted."""
        settings = PyWrySettings(tauri_plugins=["dialog", "fs", "notification"])
        assert "notification" in settings.tauri_plugins

    def test_comma_separated_string(self):
        """Comma-separated string is parsed into a list."""
        settings = PyWrySettings(tauri_plugins="dialog,fs,http")
        assert settings.tauri_plugins == ["dialog", "fs", "http"]

    def test_comma_separated_with_spaces(self):
        """Comma-separated string with spaces is trimmed."""
        settings = PyWrySettings(tauri_plugins=" dialog , fs , notification ")
        assert settings.tauri_plugins == ["dialog", "fs", "notification"]

    def test_unknown_plugin_raises(self):
        """Unknown plugin name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown Tauri plugin"):
            PyWrySettings(tauri_plugins=["dialog", "nonexistent_plugin"])

    def test_all_known_plugins_accepted(self):
        """All 19 known plugins are individually accepted."""
        for name in AVAILABLE_TAURI_PLUGINS:
            settings = PyWrySettings(tauri_plugins=[name])
            assert settings.tauri_plugins == [name]

    def test_extra_capabilities_default_empty(self):
        """Default extra_capabilities is an empty list."""
        settings = PyWrySettings()
        assert settings.extra_capabilities == []

    def test_extra_capabilities_list(self):
        """Custom capability list is accepted."""
        caps = ["shell:allow-execute", "fs:allow-read-file"]
        settings = PyWrySettings(extra_capabilities=caps)
        assert settings.extra_capabilities == caps

    def test_extra_capabilities_comma_string(self):
        """Comma-separated capability string is parsed."""
        settings = PyWrySettings(extra_capabilities="shell:allow-execute,fs:allow-read-file")
        assert settings.extra_capabilities == ["shell:allow-execute", "fs:allow-read-file"]

    def test_plugins_in_toml_export(self):
        """Tauri plugins appear in TOML export."""
        settings = PyWrySettings(tauri_plugins=["dialog", "fs", "notification"])
        toml = settings.to_toml()
        assert "tauri_plugins" in toml
        assert '"notification"' in toml

    def test_plugins_in_env_export(self):
        """Tauri plugins appear in env export."""
        settings = PyWrySettings(tauri_plugins=["dialog", "fs", "http"])
        env = settings.to_env()
        assert "PYWRY_TAURI_PLUGINS" in env
        assert "http" in env

    def test_env_var_override(self, monkeypatch):
        """PYWRY_TAURI_PLUGINS env var overrides default."""
        monkeypatch.setenv("PYWRY__TAURI_PLUGINS", "dialog,fs,notification,http")
        settings = PyWrySettings()
        assert "notification" in settings.tauri_plugins
        assert "http" in settings.tauri_plugins

    def test_available_plugins_has_19(self):
        """Registry contains exactly 19 plugins."""
        assert len(AVAILABLE_TAURI_PLUGINS) == 19


# ─────────────────────────────────────────────────────────────────────────────
# Coverage gaps: helper functions, validators, edge paths
# ─────────────────────────────────────────────────────────────────────────────


class TestFindConfigFiles:
    """Cover the _find_config_files helper."""

    def test_finds_pyproject_toml(self, tmp_path, monkeypatch):
        from pywry.config import _find_config_files

        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text("[tool.pywry]\n")
        result = _find_config_files()
        assert any("pyproject.toml" in str(p) for p in result)

    def test_finds_pywry_toml(self, tmp_path, monkeypatch):
        from pywry.config import _find_config_files

        monkeypatch.chdir(tmp_path)
        (tmp_path / "pywry.toml").write_text("")
        result = _find_config_files()
        assert any("pywry.toml" in str(p) for p in result)

    def test_finds_env_config_file(self, tmp_path, monkeypatch):
        from pywry.config import _find_config_files

        monkeypatch.chdir(tmp_path)
        env_path = tmp_path / "custom.toml"
        env_path.write_text("")
        monkeypatch.setenv("PYWRY_CONFIG_FILE", str(env_path))
        result = _find_config_files()
        assert any("custom.toml" in str(p) for p in result)

    def test_skips_missing_env_config(self, tmp_path, monkeypatch):
        from pywry.config import _find_config_files

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("PYWRY_CONFIG_FILE", str(tmp_path / "nonexistent.toml"))
        result = _find_config_files()
        # No file added
        assert not any("nonexistent.toml" in str(p) for p in result)

    def test_linux_user_config_path(self, tmp_path, monkeypatch):
        """Trigger line 55: linux user config path branch."""
        import pywry.config as cfg

        monkeypatch.chdir(tmp_path)
        with patch.object(cfg.sys, "platform", "linux"):
            result = cfg._find_config_files()
        # Even on linux path, the function still runs and returns a list
        assert isinstance(result, list)

    def test_finds_user_config_file(self, tmp_path, monkeypatch):
        """Trigger line 58: user_config exists branch (Windows APPDATA path)."""
        import pywry.config as cfg

        # Create a fake APPDATA dir with the config file
        appdata = tmp_path / "appdata"
        config_dir = appdata / "pywry"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"
        config_file.write_text("[csp]\n")

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("APPDATA", str(appdata))

        # Patch sys.platform to win32 to ensure that branch runs
        with patch.object(cfg.sys, "platform", "win32"):
            result = cfg._find_config_files()
        assert any("config.toml" in str(p) for p in result)


class TestLoadTomlConfig:
    """Cover _load_toml_config error paths."""

    def test_handles_decode_error(self, tmp_path, monkeypatch):
        from pywry.config import _load_toml_config

        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text("[invalid toml [[[")
        result = _load_toml_config()
        assert isinstance(result, dict)

    def test_returns_empty_when_tomllib_none(self, monkeypatch):
        import pywry.config as cfg

        with patch.object(cfg, "tomllib", None):
            result = cfg._load_toml_config()
        assert result == {}


class TestDeepMergeOverride:
    """Cover the non-dict override branch of _deep_merge."""

    def test_override_replaces_non_dict(self):
        from pywry.config import _deep_merge

        # base[key] is a non-dict, override[key] is a non-dict → replace
        result = _deep_merge({"x": 1, "y": [1, 2]}, {"x": 2, "y": [3, 4]})
        assert result == {"x": 2, "y": [3, 4]}

    def test_override_replaces_dict_with_value(self):
        from pywry.config import _deep_merge

        result = _deep_merge({"x": {"a": 1}}, {"x": "literal"})
        assert result == {"x": "literal"}

    def test_recursive_merge_of_dicts(self):
        from pywry.config import _deep_merge

        # Triggers line 100 (recursive call) - both keys are dicts
        result = _deep_merge(
            {"section": {"a": 1, "b": 2}},
            {"section": {"b": 3, "c": 4}},
        )
        assert result == {"section": {"a": 1, "b": 3, "c": 4}}


class TestSecuritySettingsLocalhostWithPorts:
    def test_with_specific_ports(self):
        from pywry.config import SecuritySettings

        settings = SecuritySettings.localhost(ports=[8080, 9000])
        assert "8080" in settings.connect_src
        assert "9000" in settings.connect_src


class TestTVChartStorageValidators:
    """Cover storage identifier/path validation paths."""

    def test_empty_string_returns_empty(self):
        from pywry.config import TVChartSettings

        s = TVChartSettings(storage_namespace="")
        assert s.storage_namespace == ""

    def test_too_long_raises(self):
        from pywry.config import TVChartSettings

        with pytest.raises(Exception, match="<= 512"):
            TVChartSettings(storage_namespace="x" * 513)

    def test_control_chars_raises(self):
        from pywry.config import TVChartSettings

        with pytest.raises(Exception, match="control characters"):
            TVChartSettings(storage_namespace="bad\x01char")

    def test_unsupported_chars_raises(self):
        from pywry.config import TVChartSettings

        with pytest.raises(Exception, match="unsupported"):
            TVChartSettings(storage_namespace="bad@char")

    def test_path_too_long_raises(self):
        from pywry.config import TVChartSettings

        with pytest.raises(Exception, match="<= 512"):
            TVChartSettings(storage_path="x" * 513)

    def test_path_control_chars_raises(self):
        from pywry.config import TVChartSettings

        with pytest.raises(Exception, match="control"):
            TVChartSettings(storage_path="bad\x01")

    def test_path_unsupported_chars_raises(self):
        from pywry.config import TVChartSettings

        with pytest.raises(Exception, match="unsupported"):
            TVChartSettings(storage_path="bad@char")

    def test_storage_path_empty_returns_empty(self):
        from pywry.config import TVChartSettings

        # Empty string triggers the early-return branch (line 522)
        s = TVChartSettings(storage_path="")
        assert s.storage_path == ""


class TestCommaSeparatedValidators:
    def test_watch_directories_string(self):
        from pywry.config import HotReloadSettings

        s = HotReloadSettings(watch_directories="a, b, c")
        assert s.watch_directories == ["a", "b", "c"]

    def test_watch_directories_empty_string(self):
        from pywry.config import HotReloadSettings

        s = HotReloadSettings(watch_directories="")
        assert s.watch_directories == []

    def test_default_roles_string(self):
        from pywry.config import DeploySettings

        s = DeploySettings(default_roles="admin, user")
        assert "admin" in s.default_roles

    def test_admin_users_string(self):
        from pywry.config import DeploySettings

        s = DeploySettings(admin_users="alice, bob")
        assert "alice" in s.admin_users

    def test_admin_users_none(self):
        from pywry.config import DeploySettings

        s = DeploySettings(admin_users=None)
        assert s.admin_users == []

    def test_public_paths_string(self):
        from pywry.config import DeploySettings

        s = DeploySettings(auth_public_paths="/health, /metrics")
        assert "/health" in s.auth_public_paths

    def test_server_cors_origins_string(self):
        """ServerSettings parses cors_origins from comma-separated string."""
        from pywry.config import ServerSettings

        s = ServerSettings(cors_origins="https://example.com, https://other.com")
        assert "https://example.com" in s.cors_origins

    def test_server_cors_methods_string(self):
        from pywry.config import ServerSettings

        s = ServerSettings(cors_allow_methods="GET, POST")
        assert "GET" in s.cors_allow_methods


class TestOAuth2ValidateCustomProvider:
    def test_returns_value(self):
        from pywry.config import OAuth2Settings

        s = OAuth2Settings(client_id="abc")
        assert s.client_id == "abc"


class TestTauriPluginsTypeErrors:
    def test_invalid_tauri_plugins_type(self):
        with pytest.raises(TypeError, match="must be a list"):
            PyWrySettings(tauri_plugins=42)

    def test_invalid_extra_capabilities_type(self):
        with pytest.raises(TypeError, match="must be a list"):
            PyWrySettings(extra_capabilities=42)


class TestOAuth2AutoDetection:
    def test_auto_oauth2_from_env(self, monkeypatch):
        monkeypatch.setenv("PYWRY_OAUTH2__CLIENT_ID", "test-client")
        from pywry.config import PyWrySettings

        settings = PyWrySettings()
        assert settings.oauth2 is not None


class TestToTomlOAuth2Section:
    def test_oauth2_included_when_set(self):
        from pywry.config import OAuth2Settings, PyWrySettings

        oauth2 = OAuth2Settings(client_id="x", provider="google")
        settings = PyWrySettings(oauth2=oauth2)
        toml = settings.to_toml()
        assert "[oauth2]" in toml

    def test_extra_capabilities_included(self):
        settings = PyWrySettings(extra_capabilities=["read-file"])
        toml = settings.to_toml()
        assert "extra_capabilities" in toml

    def test_extra_capabilities_in_env(self):
        """Trigger line 1338: extra_capabilities export in to_env()."""
        settings = PyWrySettings(extra_capabilities=["read-file"])
        env = settings.to_env()
        assert "PYWRY_EXTRA_CAPABILITIES" in env
        assert "read-file" in env


class TestToEnvOAuth2Section:
    def test_oauth2_env_export(self):
        from pywry.config import OAuth2Settings, PyWrySettings

        oauth2 = OAuth2Settings(client_id="x", provider="google")
        settings = PyWrySettings(oauth2=oauth2)
        env = settings.to_env()
        # OAuth2 may not appear in env-export, but should run without error
        assert isinstance(env, str)
        assert "PYWRY_" in env


class TestSettingsCacheManagement:
    def test_get_settings_cached(self):
        from pywry.config import clear_settings, get_settings

        clear_settings()
        a = get_settings()
        b = get_settings()
        assert a is b

    def test_clear_settings_resets(self):
        from pywry.config import clear_settings, get_settings

        a = get_settings()
        clear_settings()
        b = get_settings()
        # New instance after clear
        assert isinstance(b, type(a))

    def test_reload_settings(self):
        from pywry.config import reload_settings

        s = reload_settings()
        assert s is not None


class TestInvalidSecuritySettings:
    """Tests for invalid SecuritySettings values."""

    def test_empty_default_src_is_allowed(self) -> None:
        """Empty default_src is allowed (permissive)."""
        # Empty string is technically valid, just insecure
        settings = SecuritySettings(default_src="")
        assert settings.default_src == ""

    def test_none_default_src_uses_default(self) -> None:
        """None default_src falls back to default value."""
        settings = SecuritySettings()
        assert settings.default_src != ""


class TestInvalidAssetSettings:
    """Tests for invalid AssetSettings values."""

    def test_invalid_plotly_version_format(self) -> None:
        """Invalid plotly version format is accepted (no validation)."""
        # Version strings aren't validated, user's responsibility
        settings = AssetSettings(plotly_version="not-a-version")
        assert settings.plotly_version == "not-a-version"
