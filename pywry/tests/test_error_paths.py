"""Tests for error paths and edge cases.

These tests verify proper error handling for:
- Invalid configuration values
- Malformed callback data
- Missing/invalid resources
- Boundary conditions
- Type validation errors

Run with: pytest tests/test_error_paths.py -v
"""

from __future__ import annotations

import pytest

from pydantic import ValidationError


# =============================================================================
# Invalid Configuration Tests
# =============================================================================


class TestInvalidWindowConfig:
    """Tests for invalid WindowConfig values."""

    def test_width_below_minimum_raises(self) -> None:
        """Width below 200 raises validation error."""
        from pywry.models import WindowConfig

        with pytest.raises(ValidationError):
            WindowConfig(width=100)  # min is 200

    def test_height_below_minimum_raises(self) -> None:
        """Height below 150 raises validation error."""
        from pywry.models import WindowConfig

        with pytest.raises(ValidationError):
            WindowConfig(height=100)  # min is 150

    def test_negative_width_raises(self) -> None:
        """Negative width raises validation error."""
        from pywry.models import WindowConfig

        with pytest.raises(ValidationError):
            WindowConfig(width=-100)

    def test_negative_height_raises(self) -> None:
        """Negative height raises validation error."""
        from pywry.models import WindowConfig

        with pytest.raises(ValidationError):
            WindowConfig(height=-100)

    def test_min_width_below_minimum_raises(self) -> None:
        """min_width below 100 raises validation error."""
        from pywry.models import WindowConfig

        with pytest.raises(ValidationError):
            WindowConfig(min_width=50)  # min is 100

    def test_min_height_below_minimum_raises(self) -> None:
        """min_height below 100 raises validation error."""
        from pywry.models import WindowConfig

        with pytest.raises(ValidationError):
            WindowConfig(min_height=50)  # min is 100

    def test_invalid_theme_string_raises(self) -> None:
        """Invalid theme string raises validation error."""
        from pywry.models import WindowConfig

        with pytest.raises(ValidationError):
            WindowConfig(theme="invalid_theme")  # type: ignore[arg-type]

    def test_invalid_plotly_theme_string_raises(self) -> None:
        """Invalid plotly_theme string raises validation error."""
        from pywry.models import WindowConfig

        with pytest.raises(ValidationError):
            WindowConfig(plotly_theme="invalid_plotly_theme")  # type: ignore[arg-type]

    def test_min_width_greater_than_width_raises(self) -> None:
        """min_width > width raises validation error."""
        from pywry.models import WindowConfig

        with pytest.raises(ValidationError):
            WindowConfig(width=300, min_width=500)

    def test_min_height_greater_than_height_raises(self) -> None:
        """min_height > height raises validation error."""
        from pywry.models import WindowConfig

        with pytest.raises(ValidationError):
            WindowConfig(height=200, min_height=400)


class TestInvalidSecuritySettings:
    """Tests for invalid SecuritySettings values."""

    def test_empty_default_src_is_allowed(self) -> None:
        """Empty default_src is allowed (permissive)."""
        from pywry.config import SecuritySettings

        # Empty string is technically valid, just insecure
        settings = SecuritySettings(default_src="")
        assert settings.default_src == ""

    def test_none_default_src_uses_default(self) -> None:
        """None default_src falls back to default value."""
        from pywry.config import SecuritySettings

        settings = SecuritySettings()
        assert settings.default_src != ""


class TestInvalidAssetSettings:
    """Tests for invalid AssetSettings values."""

    def test_invalid_plotly_version_format(self) -> None:
        """Invalid plotly version format is accepted (no validation)."""
        from pywry.config import AssetSettings

        # Version strings aren't validated, user's responsibility
        settings = AssetSettings(plotly_version="not-a-version")
        assert settings.plotly_version == "not-a-version"


# =============================================================================
# Invalid Model Data Tests
# =============================================================================


class TestInvalidHtmlContent:
    """Tests for invalid HtmlContent values."""

    def test_empty_html_allowed(self) -> None:
        """Empty HTML is allowed."""
        from pywry.models import HtmlContent

        content = HtmlContent(html="")
        assert content.html == ""

    def test_none_html_raises(self) -> None:
        """None HTML raises validation error."""
        from pywry.models import HtmlContent

        with pytest.raises(ValidationError):
            HtmlContent(html=None)  # type: ignore[arg-type]

    def test_invalid_json_data_type_raises(self) -> None:
        """Non-dict json_data raises validation error."""
        from pywry.models import HtmlContent

        with pytest.raises(ValidationError):
            HtmlContent(html="<div></div>", json_data="not a dict")  # type: ignore[arg-type]


class TestInvalidGridModels:
    """Tests for Grid model validation."""

    def test_coldef_field_can_be_none(self) -> None:
        """None field is allowed (field is optional)."""
        from pywry.grid import ColDef

        col = ColDef(field=None)
        assert col.field is None

    def test_coldef_empty_field_allowed(self) -> None:
        """Empty string field is allowed (user's responsibility)."""
        from pywry.grid import ColDef

        col = ColDef(field="")
        assert col.field == ""

    def test_coldef_with_valid_field(self) -> None:
        """Valid field name works correctly."""
        from pywry.grid import ColDef

        col = ColDef(field="myColumn")
        assert col.field == "myColumn"

    def test_coldef_negative_width_raises(self) -> None:
        """Negative width raises validation error."""
        from pywry.grid import ColDef

        with pytest.raises(ValidationError):
            ColDef(field="test", width=-100)

    def test_coldef_negative_min_width_raises(self) -> None:
        """Negative min_width raises validation error."""
        from pywry.grid import ColDef

        with pytest.raises(ValidationError):
            ColDef(field="test", min_width=-50)

    def test_coldef_negative_max_width_raises(self) -> None:
        """Negative max_width raises validation error."""
        from pywry.grid import ColDef

        with pytest.raises(ValidationError):
            ColDef(field="test", max_width=-50)

    def test_coldef_zero_width_allowed(self) -> None:
        """Zero width is allowed (just not visible)."""
        from pywry.grid import ColDef

        col = ColDef(field="test", width=0)
        assert col.width == 0


class TestInvalidToolbarModels:
    """Tests for invalid Toolbar model values."""

    def test_button_empty_label_uses_default(self) -> None:
        """Empty button label uses 'Button' default in HTML."""
        from pywry.toolbar import Button

        btn = Button(label="", event="toolbar:click")
        html = btn.build_html()
        assert "Button" in html  # Default label used

    def test_button_empty_event_raises(self) -> None:
        """Empty event raises validation error."""
        from pywry.toolbar import Button

        with pytest.raises(ValidationError):
            Button(label="Test", event="")

    def test_button_invalid_event_format_raises(self) -> None:
        """Invalid event format raises validation error."""
        from pywry.toolbar import Button

        with pytest.raises(ValidationError):
            Button(label="Test", event="no_namespace")

    def test_select_empty_options_allowed(self) -> None:
        """Select without options is allowed."""
        from pywry.toolbar import Select

        sel = Select(event="view:change", options=[])
        assert len(sel.options) == 0

    def test_toolbar_invalid_position_raises(self) -> None:
        """Invalid toolbar position raises validation error."""
        from pywry.toolbar import Toolbar

        with pytest.raises(ValidationError):
            Toolbar(position="invalid", items=[])  # type: ignore[arg-type]

    def test_text_input_negative_debounce_raises(self) -> None:
        """Negative debounce raises validation error."""
        from pywry.toolbar import TextInput

        with pytest.raises(ValidationError):
            TextInput(event="search:query", debounce=-1)

    def test_slider_min_greater_than_max_raises(self) -> None:
        """Slider with min > max raises validation error."""
        from pywry.toolbar import SliderInput

        with pytest.raises(ValidationError):
            SliderInput(event="zoom:level", min=100, max=0)

    def test_slider_value_out_of_range_raises(self) -> None:
        """Slider with value outside min/max raises validation error."""
        from pywry.toolbar import SliderInput

        with pytest.raises(ValidationError):
            SliderInput(event="zoom:level", value=150, min=0, max=100)

    def test_range_start_greater_than_end_raises(self) -> None:
        """Range with start > end raises validation error."""
        from pywry.toolbar import RangeInput

        with pytest.raises(ValidationError):
            RangeInput(event="filter:range", start=100, end=0)

    def test_range_min_greater_than_max_raises(self) -> None:
        """Range with min > max raises validation error."""
        from pywry.toolbar import RangeInput

        with pytest.raises(ValidationError):
            RangeInput(event="filter:range", min=100, max=0)

    def test_range_start_out_of_range_raises(self) -> None:
        """Range with start outside min/max raises validation error."""
        from pywry.toolbar import RangeInput

        with pytest.raises(ValidationError):
            RangeInput(event="filter:range", start=-50, min=0, max=100)


# =============================================================================
# Callback/Event Error Tests
# =============================================================================


class TestCallbackErrors:
    """Tests for callback registry error handling."""

    def test_dispatch_nonexistent_label_returns_false(self) -> None:
        """Dispatching to nonexistent label returns False."""
        from pywry.callbacks import get_registry

        registry = get_registry()
        registry.clear()

        result = registry.dispatch("nonexistent-label", "test:event", {})
        assert result is False

    def test_dispatch_nonexistent_event_returns_false(self) -> None:
        """Dispatching nonexistent event returns False."""
        from pywry.callbacks import get_registry

        registry = get_registry()
        registry.clear()
        registry.register("test-window", "known:event", lambda _: None)

        result = registry.dispatch("test-window", "unknown:event", {})
        assert result is False

    def test_unregister_nonexistent_callback_returns_false(self) -> None:
        """Unregistering nonexistent callback returns False."""
        from pywry.callbacks import get_registry

        registry = get_registry()
        registry.clear()

        result = registry.unregister("nonexistent", "test:event", lambda _: None)
        assert result is False

    def test_register_invalid_event_type_returns_false(self) -> None:
        """Registering invalid event type returns False."""
        from pywry.callbacks import get_registry

        registry = get_registry()
        registry.clear()

        result = registry.register("test-window", "invalid", lambda _: None)
        assert result is False


class TestEventValidationErrors:
    """Tests for event type validation errors."""

    def test_validate_empty_event_type(self) -> None:
        """Empty event type is invalid."""
        from pywry.models import validate_event_type

        assert validate_event_type("") is False

    def test_validate_no_namespace(self) -> None:
        """Event without namespace is invalid."""
        from pywry.models import validate_event_type

        assert validate_event_type("click") is False

    def test_validate_empty_namespace(self) -> None:
        """Empty namespace is invalid."""
        from pywry.models import validate_event_type

        assert validate_event_type(":click") is False

    def test_validate_empty_event_name(self) -> None:
        """Empty event name is invalid."""
        from pywry.models import validate_event_type

        assert validate_event_type("toolbar:") is False


# =============================================================================
# Exception Hierarchy Tests
# =============================================================================


class TestExceptionChaining:
    """Tests for exception chaining and context preservation."""

    def test_window_error_preserves_context(self) -> None:
        """WindowError preserves context in message."""
        from pywry.exceptions import WindowError

        exc = WindowError("Failed", label="test-win", operation="close")
        exc_str = str(exc)
        assert "test-win" in exc_str
        assert "close" in exc_str

    def test_ipc_timeout_includes_timeout_value(self) -> None:
        """IPCTimeoutError includes timeout value in message."""
        from pywry.exceptions import IPCTimeoutError

        exc = IPCTimeoutError("Timed out", timeout=5.0)
        exc_str = str(exc)
        assert "5.0" in exc_str

    def test_exception_can_be_caught_as_base(self) -> None:
        """Specific exceptions can be caught as base PyWryException."""
        from pywry.exceptions import PyWryException, WindowError

        try:
            raise WindowError("Test error", label="win")
        except PyWryException as e:
            assert "Test error" in str(e)


# =============================================================================
# Boundary Condition Tests
# =============================================================================


class TestBoundaryConditions:
    """Tests for boundary conditions and edge cases."""

    def test_very_large_window_dimensions(self) -> None:
        """Very large window dimensions are accepted."""
        from pywry.models import WindowConfig

        config = WindowConfig(width=10000, height=10000)
        assert config.width == 10000
        assert config.height == 10000

    def test_minimum_valid_dimensions(self) -> None:
        """Minimum valid dimensions are accepted (width=200, height=150)."""
        from pywry.models import WindowConfig

        # Minimum allowed values based on model validation
        config = WindowConfig(width=200, height=150, min_width=100, min_height=100)
        assert config.width == 200
        assert config.height == 150

    def test_very_long_title(self) -> None:
        """Very long title is accepted."""
        from pywry.models import WindowConfig

        long_title = "A" * 1000
        config = WindowConfig(title=long_title)
        assert config.title == long_title

    def test_unicode_in_title(self) -> None:
        """Unicode characters in title are accepted."""
        from pywry.models import WindowConfig

        config = WindowConfig(title="测试窗口 🪟")
        assert config.title == "测试窗口 🪟"

    def test_unicode_in_html_content(self) -> None:
        """Unicode characters in HTML content are accepted."""
        from pywry.models import HtmlContent

        content = HtmlContent(html="<div>こんにちは 🌍</div>")
        assert "こんにちは" in content.html

    def test_special_characters_in_json_data(self) -> None:
        """Special characters in JSON data are preserved."""
        from pywry.models import HtmlContent

        content = HtmlContent(
            html="<div></div>",
            json_data={"message": "Hello <script>alert('xss')</script>"},
        )
        json_data = content.json_data
        assert json_data is not None
        assert "<script>" in json_data["message"]  # pylint: disable=unsubscriptable-object

    def test_empty_toolbar_items_list(self) -> None:
        """Empty toolbar items list is valid."""
        from pywry.toolbar import Toolbar

        toolbar = Toolbar(items=[])
        assert len(toolbar.items) == 0

    def test_deeply_nested_json_data(self) -> None:
        """Deeply nested JSON data is accepted."""
        from typing import Any

        from pywry.models import HtmlContent

        nested: dict[str, Any] = {"level1": {"level2": {"level3": {"level4": {"value": "deep"}}}}}
        content = HtmlContent(html="<div></div>", json_data=nested)
        json_data = content.json_data
        assert json_data is not None
        # pylint: disable=unsubscriptable-object
        assert json_data["level1"]["level2"]["level3"]["level4"]["value"] == "deep"


# =============================================================================
# State Store Error Tests
# =============================================================================


class TestMemoryStoreErrors:
    """Tests for memory store error handling."""

    @pytest.mark.asyncio
    async def test_get_nonexistent_widget_returns_none(self) -> None:
        """Getting nonexistent widget returns None."""
        from pywry.state import MemoryWidgetStore

        store = MemoryWidgetStore()
        result = await store.get("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_widget_returns_false(self) -> None:
        """Deleting nonexistent widget returns False."""
        from pywry.state import MemoryWidgetStore

        store = MemoryWidgetStore()
        result = await store.delete("nonexistent-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_update_nonexistent_widget_returns_false(self) -> None:
        """Updating nonexistent widget returns False."""
        from pywry.state import MemoryWidgetStore

        store = MemoryWidgetStore()
        result = await store.update_html("nonexistent-id", "<p>New</p>")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_html_nonexistent_returns_none(self) -> None:
        """Getting HTML of nonexistent widget returns None."""
        from pywry.state import MemoryWidgetStore

        store = MemoryWidgetStore()
        result = await store.get_html("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_token_nonexistent_returns_none(self) -> None:
        """Getting token of nonexistent widget returns None."""
        from pywry.state import MemoryWidgetStore

        store = MemoryWidgetStore()
        result = await store.get_token("nonexistent-id")
        assert result is None


# =============================================================================
# Type Coercion Error Tests
# =============================================================================


class TestTypeCoercionErrors:
    """Tests for type coercion and validation."""

    def test_window_width_string_coerced(self) -> None:
        """String width is coerced to int."""
        from pywry.models import WindowConfig

        config = WindowConfig(width="800")  # type: ignore[arg-type]
        assert config.width == 800

    def test_window_width_float_not_coerced(self) -> None:
        """Float width with fractional part raises validation error."""
        from pywry.models import WindowConfig

        # Pydantic v2 strict mode doesn't auto-coerce floats with decimals
        with pytest.raises(ValidationError):
            WindowConfig(width=800.5)  # type: ignore[arg-type]

    def test_window_width_float_whole_number_coerced(self) -> None:
        """Float width without fractional part is coerced to int."""
        from pywry.models import WindowConfig

        config = WindowConfig(width=800.0)  # type: ignore[arg-type]
        assert config.width == 800

    def test_invalid_type_raises_validation_error(self) -> None:
        """Non-numeric width raises validation error."""
        from pywry.models import WindowConfig

        with pytest.raises(ValidationError):
            WindowConfig(width="not-a-number")  # type: ignore[arg-type]

    def test_list_to_string_raises(self) -> None:
        """List where string expected raises validation error."""
        from pywry.models import WindowConfig

        with pytest.raises(ValidationError):
            WindowConfig(title=["not", "a", "string"])  # type: ignore[arg-type]
