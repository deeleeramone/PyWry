"""Tests for Pydantic models.

Tests model validation, field types, and serialization.
"""

from pathlib import Path

import pytest

from pydantic import ValidationError

from pywry.models import (
    GenericEvent,
    GenericEventPayload,
    GridCellEvent,
    GridRowClickEvent,
    GridSelectionEvent,
    HtmlContent,
    PlotlyClickEvent,
    PlotlyHoverEvent,
    PlotlyRelayoutEvent,
    PlotlySelectEvent,
    ResultEvent,
    ThemeMode,
    WindowConfig,
    WindowMode,
    validate_event_type,
)


class TestThemeMode:
    """Tests for ThemeMode enum."""

    def test_dark_value(self):
        """DARK theme has correct value."""
        assert ThemeMode.DARK.value == "dark"

    def test_light_value(self):
        """LIGHT theme has correct value."""
        assert ThemeMode.LIGHT.value == "light"

    def test_system_value(self):
        """SYSTEM theme has correct value."""
        assert ThemeMode.SYSTEM.value == "system"

    def test_dark_is_string_enum(self):
        """ThemeMode is a string enum."""
        assert isinstance(ThemeMode.DARK, str)
        assert ThemeMode.DARK == "dark"


class TestWindowMode:
    """Tests for WindowMode enum."""

    def test_new_window_value(self):
        """NEW_WINDOW has correct value."""
        assert WindowMode.NEW_WINDOW.value == "new_window"

    def test_single_window_value(self):
        """SINGLE_WINDOW has correct value."""
        assert WindowMode.SINGLE_WINDOW.value == "single_window"

    def test_multi_window_value(self):
        """MULTI_WINDOW has correct value."""
        assert WindowMode.MULTI_WINDOW.value == "multi_window"


class TestWindowConfig:
    """Tests for WindowConfig model."""

    def test_default_title(self):
        """Default title is PyWry."""
        config = WindowConfig()
        assert config.title == "PyWry"

    def test_default_width(self):
        """Default width is 1280."""
        config = WindowConfig()
        assert config.width == 1280

    def test_default_height(self):
        """Default height is 720."""
        config = WindowConfig()
        assert config.height == 720

    def test_default_theme(self):
        """Default theme is DARK."""
        config = WindowConfig()
        assert config.theme == ThemeMode.DARK

    def test_custom_title(self):
        """Custom title is set."""
        config = WindowConfig(title="My App")
        assert config.title == "My App"

    def test_custom_dimensions(self):
        """Custom dimensions are set."""
        config = WindowConfig(width=800, height=600)
        assert config.width == 800
        assert config.height == 600

    def test_custom_theme(self):
        """Custom theme is set."""
        config = WindowConfig(theme=ThemeMode.LIGHT)
        assert config.theme == ThemeMode.LIGHT

    def test_min_width_default(self):
        """Default min_width is 400."""
        config = WindowConfig()
        assert config.min_width == 400

    def test_min_height_default(self):
        """Default min_height is 300."""
        config = WindowConfig()
        assert config.min_height == 300

    def test_center_default(self):
        """Default center is True."""
        config = WindowConfig()
        assert config.center is True

    def test_resizable_default(self):
        """Default resizable is True."""
        config = WindowConfig()
        assert config.resizable is True

    def test_decorations_default(self):
        """Default decorations is True."""
        config = WindowConfig()
        assert config.decorations is True

    def test_always_on_top_default(self):
        """Default always_on_top is False."""
        config = WindowConfig()
        assert config.always_on_top is False

    def test_devtools_default(self):
        """Default devtools is False."""
        config = WindowConfig()
        assert config.devtools is False

    def test_allow_network_default(self):
        """Default allow_network is True."""
        config = WindowConfig()
        assert config.allow_network is True

    def test_enable_plotly_default(self):
        """Default enable_plotly is False."""
        config = WindowConfig()
        assert config.enable_plotly is False

    def test_enable_aggrid_default(self):
        """Default enable_aggrid is False."""
        config = WindowConfig()
        assert config.enable_aggrid is False

    def test_plotly_theme_default(self):
        """Default plotly_theme is plotly_dark."""
        config = WindowConfig()
        assert config.plotly_theme == "plotly_dark"

    def test_aggrid_theme_default(self):
        """Default aggrid_theme is alpine."""
        config = WindowConfig()
        assert config.aggrid_theme == "alpine"


class TestHtmlContent:
    """Tests for HtmlContent model."""

    def test_html_field_required(self):
        """html field is required."""
        content = HtmlContent(html="<p>Test</p>")
        assert content.html == "<p>Test</p>"

    def test_json_data_optional(self):
        """json_data is optional."""
        content = HtmlContent(html="<div></div>")
        assert content.json_data is None

    def test_json_data_set(self):
        """json_data can be set."""
        content = HtmlContent(html="<div></div>", json_data={"key": "value"})
        assert content.json_data == {"key": "value"}

    def test_init_script_optional(self):
        """init_script is optional."""
        content = HtmlContent(html="<div></div>")
        assert content.init_script is None

    def test_init_script_set(self):
        """init_script can be set."""
        content = HtmlContent(html="<div></div>", init_script="console.log('test');")
        assert content.init_script == "console.log('test');"

    def test_css_files_optional(self):
        """css_files is optional."""
        content = HtmlContent(html="<div></div>")
        assert content.css_files is None

    def test_css_files_single_string(self):
        """css_files accepts single string."""
        content = HtmlContent(html="<div></div>", css_files="style.css")
        assert len(content.css_files) == 1

    def test_css_files_list(self):
        """css_files accepts list."""
        content = HtmlContent(html="<div></div>", css_files=["a.css", "b.css"])
        assert len(content.css_files) == 2

    def test_script_files_optional(self):
        """script_files is optional."""
        content = HtmlContent(html="<div></div>")
        assert content.script_files is None

    def test_script_files_list(self):
        """script_files accepts list."""
        content = HtmlContent(html="<div></div>", script_files=["a.js", "b.js"])
        assert len(content.script_files) == 2

    def test_inline_css_optional(self):
        """inline_css is optional."""
        content = HtmlContent(html="<div></div>")
        assert content.inline_css is None

    def test_inline_css_set(self):
        """inline_css can be set."""
        content = HtmlContent(html="<div></div>", inline_css="body { margin: 0; }")
        assert content.inline_css == "body { margin: 0; }"

    def test_watch_default(self):
        """Default watch is False."""
        content = HtmlContent(html="<div></div>")
        assert content.watch is False


class TestEventTypeValidation:
    """Tests for event type validation."""

    def test_valid_simple_event(self):
        """Simple namespace:event is valid."""
        assert validate_event_type("pywry:result") is True

    def test_valid_plotly_event(self):
        """Plotly events are valid."""
        assert validate_event_type("plotly:click") is True
        assert validate_event_type("plotly:selected") is True
        assert validate_event_type("plotly:hover") is True

    def test_valid_grid_event(self):
        """Grid events are valid."""
        assert validate_event_type("grid:row-selected") is True
        assert validate_event_type("grid:cell-edit") is True

    def test_valid_custom_event(self):
        """Custom events are valid."""
        assert validate_event_type("custom:myEvent") is True
        assert validate_event_type("app:dataLoaded") is True

    def test_wildcard_valid(self):
        """Wildcard * is valid."""
        assert validate_event_type("*") is True

    def test_invalid_no_namespace(self):
        """Event without namespace is invalid."""
        assert validate_event_type("nocolon") is False

    def test_invalid_empty_namespace(self):
        """Empty namespace is invalid."""
        assert validate_event_type(":event") is False

    def test_invalid_empty_event(self):
        """Empty event name is invalid."""
        assert validate_event_type("namespace:") is False

    def test_invalid_empty_string(self):
        """Empty string is invalid."""
        assert validate_event_type("") is False


class TestResultEvent:
    """Tests for ResultEvent model."""

    def test_creates_with_data(self):
        """Creates with data field."""
        event = ResultEvent(data={"test": "value"}, window_label="main")
        assert event.data == {"test": "value"}

    def test_creates_with_label(self):
        """Creates with window_label field."""
        event = ResultEvent(data={}, window_label="main")
        assert event.window_label == "main"

    def test_accepts_any_data(self):
        """Accepts any data type."""
        event = ResultEvent(data=[1, 2, 3], window_label="main")
        assert event.data == [1, 2, 3]

        event = ResultEvent(data="string", window_label="main")
        assert event.data == "string"

        event = ResultEvent(data=42, window_label="main")
        assert event.data == 42


class TestPlotlyClickEvent:
    """Tests for PlotlyClickEvent model."""

    def test_default_point_indices(self):
        """Default point_indices is empty list."""
        event = PlotlyClickEvent()
        assert event.point_indices == []

    def test_default_curve_number(self):
        """Default curve_number is 0."""
        event = PlotlyClickEvent()
        assert event.curve_number == 0

    def test_default_point_data(self):
        """Default point_data is empty dict."""
        event = PlotlyClickEvent()
        assert event.point_data == {}

    def test_custom_values(self):
        """Custom values are set."""
        event = PlotlyClickEvent(
            point_indices=[0, 1, 2],
            curve_number=1,
            point_data={"x": 5, "y": 10},
            window_label="chart",
        )
        assert event.point_indices == [0, 1, 2]
        assert event.curve_number == 1
        assert event.point_data == {"x": 5, "y": 10}
        assert event.window_label == "chart"


class TestPlotlySelectEvent:
    """Tests for PlotlySelectEvent model."""

    def test_default_points(self):
        """Default points is empty list."""
        event = PlotlySelectEvent()
        assert event.points == []

    def test_default_range(self):
        """Default range is None."""
        event = PlotlySelectEvent()
        assert event.range is None

    def test_custom_values(self):
        """Custom values are set."""
        event = PlotlySelectEvent(
            points=[{"x": 1, "y": 2}, {"x": 3, "y": 4}],
            range={"x": [0, 10], "y": [0, 20]},
            window_label="chart",
        )
        assert len(event.points) == 2
        assert event.range is not None
        assert event.range["x"] == [0, 10]


class TestPlotlyHoverEvent:
    """Tests for PlotlyHoverEvent model."""

    def test_default_values(self):
        """Default values are set."""
        event = PlotlyHoverEvent()
        assert event.point_indices == []
        assert event.curve_number == 0
        assert event.point_data == {}

    def test_custom_values(self):
        """Custom values are set."""
        event = PlotlyHoverEvent(
            point_indices=[5],
            curve_number=2,
            point_data={"x": 100, "y": 200},
            window_label="hover-chart",
        )
        assert event.point_indices == [5]
        assert event.curve_number == 2


class TestPlotlyRelayoutEvent:
    """Tests for PlotlyRelayoutEvent model."""

    def test_default_relayout_data(self):
        """Default relayout_data is empty dict."""
        event = PlotlyRelayoutEvent()
        assert event.relayout_data == {}

    def test_custom_relayout_data(self):
        """Custom relayout_data is set."""
        event = PlotlyRelayoutEvent(
            relayout_data={
                "xaxis.range[0]": 0,
                "xaxis.range[1]": 100,
                "yaxis.range[0]": 0,
                "yaxis.range[1]": 50,
            },
            window_label="zoom-chart",
        )
        assert "xaxis.range[0]" in event.relayout_data
        assert event.relayout_data["xaxis.range[1]"] == 100


class TestGridSelectionEvent:
    """Tests for GridSelectionEvent model."""

    def test_default_selected_rows(self):
        """Default selected_rows is empty list."""
        event = GridSelectionEvent()
        assert event.selected_rows == []

    def test_default_selected_row_ids(self):
        """Default selected_row_ids is empty list."""
        event = GridSelectionEvent()
        assert event.selected_row_ids == []

    def test_custom_values(self):
        """Custom values are set."""
        event = GridSelectionEvent(
            selected_rows=[{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
            selected_row_ids=["1", "2"],
            window_label="grid",
        )
        assert len(event.selected_rows) == 2
        assert event.selected_row_ids == ["1", "2"]


class TestGridCellEvent:
    """Tests for GridCellEvent model."""

    def test_default_values(self):
        """Default values are set."""
        event = GridCellEvent()
        assert event.row_id == ""
        assert event.row_index == 0
        assert event.column == ""
        assert event.old_value is None
        assert event.new_value is None

    def test_custom_values(self):
        """Custom values are set."""
        event = GridCellEvent(
            row_id="row-123",
            row_index=5,
            column="price",
            old_value=100,
            new_value=150,
            window_label="edit-grid",
        )
        assert event.row_id == "row-123"
        assert event.row_index == 5
        assert event.column == "price"
        assert event.old_value == 100
        assert event.new_value == 150


class TestGridRowClickEvent:
    """Tests for GridRowClickEvent model."""

    def test_default_values(self):
        """Default values are set."""
        event = GridRowClickEvent()
        assert event.row_data == {}
        assert event.row_id == ""
        assert event.row_index == 0

    def test_custom_values(self):
        """Custom values are set."""
        event = GridRowClickEvent(
            row_data={"id": 1, "name": "Test", "value": 42},
            row_id="row-1",
            row_index=0,
            window_label="click-grid",
        )
        assert event.row_data["name"] == "Test"
        assert event.row_id == "row-1"


class TestWindowConfigBuilderKwargs:
    def test_dimensions_validation_min_width(self):
        with pytest.raises(ValueError, match="min_width"):
            WindowConfig(width=200, min_width=300)

    def test_dimensions_validation_min_height(self):
        with pytest.raises(ValueError, match="min_height"):
            WindowConfig(height=200, min_height=300)

    def test_builder_kwargs_default_is_empty(self):
        cfg = WindowConfig()
        assert cfg.builder_kwargs() == {}

    def test_builder_kwargs_picks_up_overrides(self):
        cfg = WindowConfig(resizable=False, fullscreen=True)
        kwargs = cfg.builder_kwargs()
        assert kwargs.get("resizable") is False
        assert kwargs.get("fullscreen") is True


class TestHtmlContentPathConversion:
    def test_none_passthrough(self):
        c = HtmlContent(html="<p/>", css_files=None)
        assert c.css_files is None

    def test_string_path_wrapped_in_list(self):
        c = HtmlContent(html="<p/>", css_files="style.css")
        assert c.css_files == [Path("style.css")]

    def test_path_object_wrapped_in_list(self):
        p = Path("style.css")
        c = HtmlContent(html="<p/>", css_files=p)
        assert c.css_files == [p]

    def test_list_with_strings_and_paths(self):
        c = HtmlContent(
            html="<p/>",
            css_files=["a.css", Path("b.css"), "c.css"],
        )
        assert all(isinstance(p, Path) for p in c.css_files)
        assert len(c.css_files) == 3

    def test_script_files_conversion(self):
        c = HtmlContent(html="<p/>", script_files="x.js")
        assert c.script_files == [Path("x.js")]


class TestGenericEventPayloadValidator:
    def test_invalid_event_type_raises(self):
        with pytest.raises(ValueError, match="Invalid event type"):
            GenericEventPayload(event_type="invalidNoColon", window_label="w")

    def test_valid_event_type(self):
        evt = GenericEventPayload(event_type="evt:click", window_label="w")
        assert evt.event_type == "evt:click"


class TestGenericEventValidator:
    def test_invalid_event_type_raises(self):
        with pytest.raises(ValueError, match="Invalid event type"):
            GenericEvent(event_type="badformat", window_label="w")

    def test_valid_event_type_returned(self):
        evt = GenericEvent(event_type="my:evt", window_label="w")
        assert evt.event_type == "my:evt"

    def test_wildcard_accepted(self):
        evt = GenericEvent(event_type="*", window_label="w")
        assert evt.event_type == "*"


class TestInvalidWindowConfig:
    """Tests for invalid WindowConfig values."""

    def test_width_below_minimum_raises(self) -> None:
        """Width below 200 raises validation error."""
        with pytest.raises(ValidationError):
            WindowConfig(width=100)  # min is 200

    def test_height_below_minimum_raises(self) -> None:
        """Height below 150 raises validation error."""
        with pytest.raises(ValidationError):
            WindowConfig(height=100)  # min is 150

    def test_negative_width_raises(self) -> None:
        """Negative width raises validation error."""
        with pytest.raises(ValidationError):
            WindowConfig(width=-100)

    def test_negative_height_raises(self) -> None:
        """Negative height raises validation error."""
        with pytest.raises(ValidationError):
            WindowConfig(height=-100)

    def test_min_width_below_minimum_raises(self) -> None:
        """min_width below 100 raises validation error."""
        with pytest.raises(ValidationError):
            WindowConfig(min_width=50)  # min is 100

    def test_min_height_below_minimum_raises(self) -> None:
        """min_height below 100 raises validation error."""
        with pytest.raises(ValidationError):
            WindowConfig(min_height=50)  # min is 100

    def test_invalid_theme_string_raises(self) -> None:
        """Invalid theme string raises validation error."""
        with pytest.raises(ValidationError):
            WindowConfig(theme="invalid_theme")  # type: ignore

    def test_invalid_plotly_theme_string_raises(self) -> None:
        """Invalid plotly_theme string raises validation error."""
        with pytest.raises(ValidationError):
            WindowConfig(plotly_theme="invalid_plotly_theme")  # type: ignore


class TestInvalidHtmlContent:
    """Tests for invalid HtmlContent values."""

    def test_empty_html_allowed(self) -> None:
        """Empty HTML is allowed."""
        content = HtmlContent(html="")
        assert content.html == ""

    def test_none_html_raises(self) -> None:
        """None HTML raises validation error."""
        with pytest.raises(ValidationError):
            HtmlContent(html=None)  # type: ignore

    def test_invalid_json_data_type_raises(self) -> None:
        """Non-dict json_data raises validation error."""
        with pytest.raises(ValidationError):
            HtmlContent(html="<div></div>", json_data="not a dict")  # type: ignore


class TestWindowConfigBoundaryConditions:
    """Tests for WindowConfig boundary conditions and edge cases."""

    def test_very_large_window_dimensions(self) -> None:
        """Very large window dimensions are accepted."""
        config = WindowConfig(width=10000, height=10000)
        assert config.width == 10000
        assert config.height == 10000

    def test_minimum_valid_dimensions(self) -> None:
        """Minimum valid dimensions are accepted (width=200, height=150)."""
        config = WindowConfig(width=200, height=150, min_width=100, min_height=100)
        assert config.width == 200
        assert config.height == 150

    def test_very_long_title(self) -> None:
        """Very long title is accepted."""
        long_title = "A" * 1000
        config = WindowConfig(title=long_title)
        assert config.title == long_title

    def test_unicode_in_title(self) -> None:
        """Unicode characters in title are accepted."""
        config = WindowConfig(title="测试窗口 🪟")
        assert config.title == "测试窗口 🪟"


class TestHtmlContentBoundaryConditions:
    """Tests for HtmlContent boundary conditions and edge cases."""

    def test_unicode_in_html_content(self) -> None:
        """Unicode characters in HTML content are accepted."""
        content = HtmlContent(html="<div>こんにちは 🌍</div>")
        assert "こんにちは" in content.html

    def test_special_characters_in_json_data(self) -> None:
        """Special characters in JSON data are preserved."""
        content = HtmlContent(
            html="<div></div>",
            json_data={"message": "Hello <script>alert('xss')</script>"},
        )
        json_data = content.json_data
        assert json_data is not None
        assert "<script>" in json_data["message"]

    def test_deeply_nested_json_data(self) -> None:
        """Deeply nested JSON data is accepted."""
        from typing import Any

        nested: dict[str, Any] = {"level1": {"level2": {"level3": {"level4": {"value": "deep"}}}}}
        content = HtmlContent(html="<div></div>", json_data=nested)
        json_data = content.json_data
        assert json_data is not None
        assert json_data["level1"]["level2"]["level3"]["level4"]["value"] == "deep"


class TestTypeCoercionErrors:
    """Tests for type coercion and validation."""

    def test_window_width_string_coerced(self) -> None:
        """String width is coerced to int."""
        config = WindowConfig(width="800")  # type: ignore
        assert config.width == 800

    def test_window_width_float_not_coerced(self) -> None:
        """Float width with fractional part raises validation error."""
        # Pydantic v2 strict mode doesn't auto-coerce floats with decimals
        with pytest.raises(ValidationError):
            WindowConfig(width=800.5)  # type: ignore

    def test_window_width_float_whole_number_coerced(self) -> None:
        """Float width without fractional part is coerced to int."""
        config = WindowConfig(width=800.0)  # type: ignore
        assert config.width == 800

    def test_invalid_type_raises_validation_error(self) -> None:
        """Non-numeric width raises validation error."""
        with pytest.raises(ValidationError):
            WindowConfig(width="not-a-number")  # type: ignore

    def test_list_to_string_raises(self) -> None:
        """List where string expected raises validation error."""
        with pytest.raises(ValidationError):
            WindowConfig(title=["not", "a", "string"])  # type: ignore
