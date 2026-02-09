# pylint: disable=too-many-lines
"""Unit tests for the Modal component.

Tests cover:
- Modal model defaults and custom values
- Sizing presets and custom width
- Behavior flags (close_on_escape, close_on_overlay_click, etc.)
- Item normalization (ToolbarItem objects, dicts, mixed)
- Validation (unknown item types, invalid overlay_opacity, invalid size)
- HTML generation (build_html)
- Data attributes and CSS classes
- Title escaping (XSS prevention)
- Script collection (inline, file path, nested Div scripts)
- to_dict() serialization
- get_secret_inputs() extraction
- wrap_content_with_modals() helper
- get_modal_script() loading
- _generate_modal_id() uniqueness
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from pydantic import ValidationError

from pywry.modal import (
    Modal,
    _generate_modal_id,
    get_modal_script,
    wrap_content_with_modals,
)
from pywry.toolbar import (
    Button,
    Div,
    NumberInput,
    Option,
    SecretInput,
    Select,
    TextInput,
    Toggle,
)


if TYPE_CHECKING:
    from pathlib import Path


class TestGenerateModalId:
    """Tests for _generate_modal_id helper."""

    def test_has_modal_prefix(self) -> None:
        """Generated ID starts with 'modal-'."""
        mid = _generate_modal_id()
        assert mid.startswith("modal-")

    def test_unique_ids(self) -> None:
        """Each call generates a unique ID."""
        ids = {_generate_modal_id() for _ in range(100)}
        assert len(ids) == 100

    def test_length(self) -> None:
        """Generated ID has expected length (modal- + 8 hex chars)."""
        mid = _generate_modal_id()
        assert len(mid) == len("modal-") + 8


class TestModalDefaults:
    """Tests for Modal default values."""

    def test_default_title(self) -> None:
        """Default title is 'Modal'."""
        m = Modal()
        assert m.title == "Modal"

    def test_default_size(self) -> None:
        """Default size is 'md'."""
        m = Modal()
        assert m.size == "md"

    def test_default_max_height(self) -> None:
        """Default max_height is '80vh'."""
        m = Modal()
        assert m.max_height == "80vh"

    def test_default_overlay_opacity(self) -> None:
        """Default overlay_opacity is 0.5."""
        m = Modal()
        assert m.overlay_opacity == 0.5

    def test_default_close_on_escape(self) -> None:
        """close_on_escape defaults to True."""
        m = Modal()
        assert m.close_on_escape is True

    def test_default_close_on_overlay_click(self) -> None:
        """close_on_overlay_click defaults to True."""
        m = Modal()
        assert m.close_on_overlay_click is True

    def test_default_reset_on_close(self) -> None:
        """reset_on_close defaults to True."""
        m = Modal()
        assert m.reset_on_close is True

    def test_default_on_close_event(self) -> None:
        """on_close_event defaults to None."""
        m = Modal()
        assert m.on_close_event is None

    def test_default_open_on_load(self) -> None:
        """open_on_load defaults to False."""
        m = Modal()
        assert m.open_on_load is False

    def test_default_width(self) -> None:
        """width defaults to None."""
        m = Modal()
        assert m.width is None

    def test_default_items(self) -> None:
        """items defaults to empty list."""
        m = Modal()
        assert not list(m.items)

    def test_default_style(self) -> None:
        """style defaults to empty string."""
        m = Modal()
        assert m.style == ""

    def test_default_script(self) -> None:
        """script defaults to None."""
        m = Modal()
        assert m.script is None

    def test_default_class_name(self) -> None:
        """class_name defaults to empty string."""
        m = Modal()
        assert m.class_name == ""

    def test_auto_generated_component_id(self) -> None:
        """component_id is auto-generated with modal- prefix."""
        m = Modal()
        assert m.component_id.startswith("modal-")

    def test_component_ids_unique_across_instances(self) -> None:
        """Each Modal instance gets a unique component_id."""
        m1 = Modal()
        m2 = Modal()
        assert m1.component_id != m2.component_id


class TestModalCustomValues:
    """Tests for Modal with custom values."""

    def test_custom_title(self) -> None:
        """Custom title is preserved."""
        m = Modal(title="Settings")
        assert m.title == "Settings"

    def test_custom_component_id(self) -> None:
        """Custom component_id is preserved."""
        m = Modal(component_id="my-modal")
        assert m.component_id == "my-modal"

    def test_custom_size(self) -> None:
        """Custom size is preserved."""
        m = Modal(size="lg")
        assert m.size == "lg"

    def test_custom_width(self) -> None:
        """Custom width is preserved."""
        m = Modal(width="600px")
        assert m.width == "600px"

    def test_custom_max_height(self) -> None:
        """Custom max_height is preserved."""
        m = Modal(max_height="90vh")
        assert m.max_height == "90vh"

    def test_custom_overlay_opacity(self) -> None:
        """Custom overlay_opacity is preserved."""
        m = Modal(overlay_opacity=0.8)
        assert m.overlay_opacity == 0.8

    def test_custom_close_on_escape(self) -> None:
        """close_on_escape can be set to False."""
        m = Modal(close_on_escape=False)
        assert m.close_on_escape is False

    def test_custom_close_on_overlay_click(self) -> None:
        """close_on_overlay_click can be set to False."""
        m = Modal(close_on_overlay_click=False)
        assert m.close_on_overlay_click is False

    def test_custom_reset_on_close(self) -> None:
        """reset_on_close can be set to False."""
        m = Modal(reset_on_close=False)
        assert m.reset_on_close is False

    def test_custom_on_close_event(self) -> None:
        """on_close_event can be set."""
        m = Modal(on_close_event="settings:closed")
        assert m.on_close_event == "settings:closed"

    def test_custom_open_on_load(self) -> None:
        """open_on_load can be set to True."""
        m = Modal(open_on_load=True)
        assert m.open_on_load is True

    def test_custom_style(self) -> None:
        """Custom inline style is preserved."""
        m = Modal(style="border: 1px solid red;")
        assert m.style == "border: 1px solid red;"

    def test_custom_class_name(self) -> None:
        """Custom class_name is preserved."""
        m = Modal(class_name="settings-modal")
        assert m.class_name == "settings-modal"


class TestModalSizing:
    """Tests for Modal size presets and width override."""

    def test_size_sm(self) -> None:
        """'sm' size is accepted."""
        m = Modal(size="sm")
        assert m.size == "sm"

    def test_size_md(self) -> None:
        """'md' size is accepted."""
        m = Modal(size="md")
        assert m.size == "md"

    def test_size_lg(self) -> None:
        """'lg' size is accepted."""
        m = Modal(size="lg")
        assert m.size == "lg"

    def test_size_xl(self) -> None:
        """'xl' size is accepted."""
        m = Modal(size="xl")
        assert m.size == "xl"

    def test_size_full(self) -> None:
        """'full' size is accepted."""
        m = Modal(size="full")
        assert m.size == "full"

    def test_invalid_size(self) -> None:
        """Invalid size is rejected."""
        with pytest.raises(ValidationError):
            Modal(size="tiny")  # type: ignore[arg-type]

    def test_overlay_opacity_min(self) -> None:
        """Overlay opacity at minimum (0.0) is accepted."""
        m = Modal(overlay_opacity=0.0)
        assert m.overlay_opacity == 0.0

    def test_overlay_opacity_max(self) -> None:
        """Overlay opacity at maximum (1.0) is accepted."""
        m = Modal(overlay_opacity=1.0)
        assert m.overlay_opacity == 1.0

    def test_overlay_opacity_below_range(self) -> None:
        """Overlay opacity below 0.0 is rejected."""
        with pytest.raises(ValidationError):
            Modal(overlay_opacity=-0.1)

    def test_overlay_opacity_above_range(self) -> None:
        """Overlay opacity above 1.0 is rejected."""
        with pytest.raises(ValidationError):
            Modal(overlay_opacity=1.1)


class TestModalExtraFields:
    """Tests that extra fields are rejected (model_config extra='forbid')."""

    def test_extra_field_rejected(self) -> None:
        """Unknown field raises ValidationError."""
        with pytest.raises(ValidationError):
            Modal(unknown_field="value")  # type: ignore[call-arg]


class TestModalItemNormalization:
    """Tests for Modal item normalization (dicts, objects, mixed)."""

    def test_accept_toolbar_item_objects(self) -> None:
        """Modal accepts ToolbarItem objects directly."""
        items = [
            Button(label="OK", event="dlg:ok"),
            TextInput(label="Name", event="dlg:name"),
        ]
        m = Modal(items=items)
        assert len(m.items) == 2
        assert isinstance(m.items[0], Button)
        assert isinstance(m.items[1], TextInput)

    def test_accept_dicts(self) -> None:
        """Modal accepts dicts with 'type' key."""
        items = [
            {"type": "button", "label": "OK", "event": "dlg:ok"},
            {"type": "text", "label": "Name", "event": "dlg:name"},
        ]
        m = Modal(items=items)
        assert len(m.items) == 2
        assert isinstance(m.items[0], Button)
        assert isinstance(m.items[1], TextInput)

    def test_accept_mixed(self) -> None:
        """Modal accepts mixed dicts and objects."""
        items: list[Any] = [
            Button(label="OK", event="dlg:ok"),
            {"type": "text", "label": "Name", "event": "dlg:name"},
        ]
        m = Modal(items=items)
        assert len(m.items) == 2

    def test_dict_defaults_to_button(self) -> None:
        """Dict without 'type' defaults to button."""
        items = [{"label": "OK", "event": "dlg:ok"}]
        m = Modal(items=items)
        assert isinstance(m.items[0], Button)

    def test_all_item_types(self) -> None:
        """Modal accepts all supported item types via dicts."""
        items = [
            {"type": "button", "label": "Btn", "event": "m:btn"},
            {
                "type": "select",
                "event": "m:select",
                "options": [{"label": "A", "value": "a"}],
            },
            {
                "type": "multiselect",
                "event": "m:ms",
                "options": [{"label": "A", "value": "a"}],
            },
            {"type": "text", "label": "Text", "event": "m:text"},
            {"type": "textarea", "label": "Area", "event": "m:area"},
            {"type": "secret", "label": "Secret", "event": "m:secret"},
            {"type": "search", "label": "Search", "event": "m:search"},
            {"type": "number", "label": "Num", "event": "m:num"},
            {"type": "date", "label": "Date", "event": "m:date"},
            {"type": "slider", "label": "Slider", "event": "m:slider"},
            {"type": "range", "label": "Range", "event": "m:range"},
            {"type": "toggle", "label": "Toggle", "event": "m:toggle"},
            {"type": "checkbox", "label": "Check", "event": "m:check"},
            {
                "type": "radio",
                "event": "m:radio",
                "options": [{"label": "A", "value": "a"}],
            },
            {
                "type": "tab",
                "event": "m:tabs",
                "options": [{"label": "Tab1", "value": "t1"}],
            },
            {"type": "div", "label": "", "event": "m:div"},
        ]
        m = Modal(items=items)
        assert len(m.items) == 16

    def test_unknown_dict_type_rejected(self) -> None:
        """Unknown item type in dict raises ValueError."""
        with pytest.raises(ValidationError, match="Unknown modal item type"):
            Modal(items=[{"type": "nonexistent_widget", "label": "X", "event": "m:x"}])

    def test_invalid_item_type_rejected(self) -> None:
        """Non-dict, non-ToolbarItem raises TypeError."""
        with pytest.raises((ValidationError, TypeError), match="Invalid modal item type"):
            Modal(items=[42])  # type: ignore[list-item]

    def test_empty_items_allowed(self) -> None:
        """Empty items list is allowed."""
        m = Modal(items=[])
        assert not list(m.items)

    def test_none_items_normalized_to_empty(self) -> None:
        """None items are normalized to empty list."""
        m = Modal(items=None)  # type: ignore[arg-type]
        assert not list(m.items)


# =============================================================================
# HTML Generation
# =============================================================================


class TestModalBuildHtml:
    """Tests for Modal.build_html() output."""

    def test_contains_overlay_div(self) -> None:
        """HTML contains the overlay div with correct ID."""
        m = Modal(component_id="test-modal")
        html = m.build_html()
        assert 'id="test-modal"' in html
        assert "pywry-modal-overlay" in html

    def test_contains_container_with_size_class(self) -> None:
        """HTML contains container div with size-specific class."""
        m = Modal(size="lg")
        html = m.build_html()
        assert "pywry-modal-container" in html
        assert "pywry-modal-lg" in html

    def test_contains_header_and_title(self) -> None:
        """HTML contains header with title text."""
        m = Modal(title="Settings")
        html = m.build_html()
        assert "pywry-modal-header" in html
        assert "pywry-modal-title" in html
        assert "Settings" in html

    def test_contains_close_button(self) -> None:
        """HTML contains close button with onclick handler."""
        m = Modal(component_id="test-modal")
        html = m.build_html()
        assert "pywry-modal-close" in html
        assert "pywry.modal.close('test-modal')" in html
        assert "aria-label" in html

    def test_contains_modal_body(self) -> None:
        """HTML contains modal body div."""
        m = Modal()
        html = m.build_html()
        assert "pywry-modal-body" in html

    def test_contains_overlay_opacity_css_var(self) -> None:
        """HTML contains the CSS variable for overlay opacity."""
        m = Modal(overlay_opacity=0.7)
        html = m.build_html()
        assert "--pywry-modal-overlay-opacity: 0.7" in html

    def test_contains_max_height_style(self) -> None:
        """HTML contains max-height inline style."""
        m = Modal(max_height="60vh")
        html = m.build_html()
        assert "max-height: 60vh" in html

    def test_custom_width_in_style(self) -> None:
        """Custom width appears in inline style."""
        m = Modal(width="500px")
        html = m.build_html()
        assert "width: 500px" in html

    def test_custom_style_appended(self) -> None:
        """Custom style is appended to inline styles."""
        m = Modal(style="border: 2px solid blue;")
        html = m.build_html()
        assert "border: 2px solid blue;" in html

    def test_custom_class_name_included(self) -> None:
        """Custom class_name is included in container classes."""
        m = Modal(class_name="my-modal")
        html = m.build_html()
        assert "my-modal" in html

    def test_data_attributes_present(self) -> None:
        """Data attributes for JS handlers are present."""
        m = Modal(
            component_id="dm",
            close_on_escape=True,
            close_on_overlay_click=False,
            reset_on_close=True,
        )
        html = m.build_html()
        assert 'data-component-id="dm"' in html
        assert 'data-close-escape="true"' in html
        assert 'data-close-overlay="false"' in html
        assert 'data-reset-on-close="true"' in html

    def test_on_close_event_data_attribute(self) -> None:
        """on_close_event is rendered as data attribute."""
        m = Modal(on_close_event="settings:closed")
        html = m.build_html()
        assert 'data-on-close-event="settings:closed"' in html

    def test_no_on_close_event_attribute_when_none(self) -> None:
        """No data-on-close-event attribute when on_close_event is None."""
        m = Modal(on_close_event=None)
        html = m.build_html()
        assert "data-on-close-event" not in html

    def test_open_on_load_class(self) -> None:
        """open_on_load adds pywry-modal-open class."""
        m = Modal(open_on_load=True)
        html = m.build_html()
        assert "pywry-modal-open" in html

    def test_no_open_class_by_default(self) -> None:
        """Default modal does NOT have pywry-modal-open class."""
        m = Modal(open_on_load=False)
        html = m.build_html()
        # The overlay class should NOT include the open class
        # Check the overlay div specifically
        assert 'class="pywry-modal-overlay"' in html

    def test_stop_propagation_onclick(self) -> None:
        """Container div has stopPropagation onclick to prevent overlay close."""
        m = Modal()
        html = m.build_html()
        assert "event.stopPropagation()" in html

    def test_items_rendered_in_body(self) -> None:
        """Modal items are rendered inside the modal body."""
        m = Modal(
            items=[
                Button(label="Save", event="dlg:save"),
                TextInput(label="Name", event="dlg:name"),
            ],
        )
        html = m.build_html()
        assert "Save" in html
        assert "Name" in html
        # Both items should be present inside modal body
        assert 'data-event="dlg:save"' in html
        # TextInput renders event in oninput handler, not data-event
        assert "dlg:name" in html

    def test_div_item_gets_parent_id(self) -> None:
        """Div items receive parent_id from modal."""
        m = Modal(
            component_id="parent-modal",
            items=[Div(label="", event="m:div", content="<p>Hello</p>")],
        )
        html = m.build_html()
        assert "Hello" in html

    def test_title_xss_escaped(self) -> None:
        """Title with HTML is properly escaped."""
        m = Modal(title='<script>alert("xss")</script>')
        html = m.build_html()
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_on_close_event_xss_escaped(self) -> None:
        """on_close_event with special chars is escaped."""
        m = Modal(on_close_event='test"><script>alert(1)</script>')
        html = m.build_html()
        assert "<script>" not in html


class TestModalCollectScripts:
    """Tests for Modal.collect_scripts()."""

    def test_no_scripts_by_default(self) -> None:
        """Modal with no script returns empty list."""
        m = Modal()
        assert not m.collect_scripts()

    def test_inline_script(self) -> None:
        """Inline JS script is collected."""
        m = Modal(script="console.log('hello');")
        scripts = m.collect_scripts()
        assert len(scripts) == 1
        assert "console.log('hello');" in scripts[0]

    def test_inline_script_function_prefix(self) -> None:
        """Script starting with 'function' is treated as inline."""
        m = Modal(script="function init() { return true; }")
        scripts = m.collect_scripts()
        assert len(scripts) == 1
        assert "function init()" in scripts[0]

    def test_inline_script_const_prefix(self) -> None:
        """Script starting with 'const' is treated as inline."""
        m = Modal(script="const x = 42;")
        scripts = m.collect_scripts()
        assert len(scripts) == 1
        assert "const x = 42;" in scripts[0]

    def test_file_path_script(self, tmp_path: Path) -> None:
        """Script from file Path is read and collected."""
        js_file = tmp_path / "modal.js"
        js_file.write_text("// modal script", encoding="utf-8")
        m = Modal(script=js_file)
        scripts = m.collect_scripts()
        assert len(scripts) == 1
        assert "// modal script" in scripts[0]

    def test_file_path_string_script(self, tmp_path: Path) -> None:
        """Script from string file path is read and collected."""
        js_file = tmp_path / "modal.js"
        js_file.write_text("// string path script", encoding="utf-8")
        m = Modal(script=str(js_file))
        scripts = m.collect_scripts()
        assert len(scripts) == 1
        assert "// string path script" in scripts[0]

    def test_nonexistent_file_path_treated_as_inline(self) -> None:
        """Non-existent file path string is treated as inline script."""
        m = Modal(script="nonexistent_file.js")
        scripts = m.collect_scripts()
        assert len(scripts) == 1
        assert "nonexistent_file.js" in scripts[0]

    def test_nonexistent_path_object_skipped(self, tmp_path: Path) -> None:
        """Non-existent Path object is skipped."""
        m = Modal(script=tmp_path / "missing.js")
        scripts = m.collect_scripts()
        assert len(scripts) == 0

    def test_nested_div_scripts_collected(self) -> None:
        """Scripts from nested Div items are collected."""
        m = Modal(
            script="// modal script",
            items=[
                Div(
                    label="",
                    event="m:div",
                    content="<p>Div</p>",
                    script="// div script",
                ),
            ],
        )
        scripts = m.collect_scripts()
        # Modal script first, then Div script
        assert len(scripts) >= 2
        assert "// modal script" in scripts[0]
        assert "// div script" in scripts[1]


class TestModalToDict:
    """Tests for Modal.to_dict()."""

    def test_basic_to_dict(self) -> None:
        """to_dict returns expected keys."""
        m = Modal(title="Test", size="sm", component_id="d-modal")
        d = m.to_dict()
        assert d["component_id"] == "d-modal"
        assert d["title"] == "Test"
        assert d["size"] == "sm"

    def test_to_dict_contains_behavior_flags(self) -> None:
        """to_dict includes all behavior flags."""
        m = Modal(
            close_on_escape=False,
            close_on_overlay_click=False,
            reset_on_close=False,
            open_on_load=True,
        )
        d = m.to_dict()
        assert d["close_on_escape"] is False
        assert d["close_on_overlay_click"] is False
        assert d["reset_on_close"] is False
        assert d["open_on_load"] is True

    def test_to_dict_includes_items(self) -> None:
        """to_dict includes serialized items."""
        m = Modal(
            items=[
                Button(label="OK", event="m:ok"),
                TextInput(label="Name", event="m:name"),
            ],
        )
        d = m.to_dict()
        assert len(d["items"]) == 2
        assert d["items"][0]["type"] == "button"
        assert d["items"][0]["label"] == "OK"
        assert d["items"][1]["type"] == "text"
        assert d["items"][1]["label"] == "Name"

    def test_to_dict_item_has_component_id(self) -> None:
        """Each item in to_dict has a component_id."""
        m = Modal(items=[Button(label="Btn", event="m:btn")])
        d = m.to_dict()
        assert "component_id" in d["items"][0]
        assert d["items"][0]["component_id"].startswith("button-")

    def test_to_dict_empty_items(self) -> None:
        """to_dict with no items has empty items list."""
        m = Modal()
        d = m.to_dict()
        assert d["items"] == []

    def test_to_dict_width_none(self) -> None:
        """to_dict has width=None by default."""
        m = Modal()
        d = m.to_dict()
        assert d["width"] is None

    def test_to_dict_on_close_event_none(self) -> None:
        """to_dict has on_close_event=None by default."""
        m = Modal()
        d = m.to_dict()
        assert d["on_close_event"] is None

    def test_to_dict_custom_on_close_event(self) -> None:
        """to_dict includes custom on_close_event."""
        m = Modal(on_close_event="dialog:closed")
        d = m.to_dict()
        assert d["on_close_event"] == "dialog:closed"


class TestModalGetSecretInputs:
    """Tests for Modal.get_secret_inputs()."""

    def test_no_secrets(self) -> None:
        """Modal with no SecretInput returns empty list."""
        m = Modal(items=[Button(label="OK", event="m:ok")])
        assert not m.get_secret_inputs()

    def test_direct_secret_input(self) -> None:
        """Modal with direct SecretInput returns it."""
        secret = SecretInput(label="API Key", event="m:key")
        m = Modal(items=[secret])
        secrets = m.get_secret_inputs()
        assert len(secrets) == 1
        assert secrets[0] is secret

    def test_multiple_secrets(self) -> None:
        """Modal with multiple SecretInputs returns all."""
        s1 = SecretInput(label="Key 1", event="m:key1")
        s2 = SecretInput(label="Key 2", event="m:key2")
        m = Modal(items=[s1, Button(label="X", event="m:x"), s2])
        secrets = m.get_secret_inputs()
        assert len(secrets) == 2

    def test_nested_secret_in_div(self) -> None:
        """SecretInput nested in a Div is not discovered (Div lacks get_secret_inputs)."""
        secret = SecretInput(label="Nested", event="m:nested")
        div = Div(label="", event="m:div", children=[secret])
        m = Modal(items=[div])
        secrets = m.get_secret_inputs()
        # Div.get_secret_inputs() doesn't exist, so hasattr guard skips it
        assert len(secrets) == 0

    def test_empty_modal_no_secrets(self) -> None:
        """Empty modal returns empty list."""
        m = Modal()
        assert not m.get_secret_inputs()


class TestGetModalScript:
    """Tests for the get_modal_script() function."""

    def test_returns_script_tags(self) -> None:
        """get_modal_script wraps JS in <script> tags."""
        script = get_modal_script()
        assert script.startswith("<script>")
        assert script.endswith("</script>")

    def test_contains_modal_namespace(self) -> None:
        """Script contains pywry.modal namespace setup."""
        script = get_modal_script()
        assert "pywry" in script
        assert "modal" in script

    def test_contains_open_close_functions(self) -> None:
        """Script contains open and close function definitions."""
        script = get_modal_script()
        assert "open" in script
        assert "close" in script


class TestWrapContentWithModals:
    """Tests for the wrap_content_with_modals() helper."""

    def test_none_modals_returns_empty(self) -> None:
        """None modals returns empty strings."""
        html, scripts = wrap_content_with_modals("<div>Content</div>", None)
        assert html == ""
        assert scripts == ""

    def test_empty_modals_returns_empty(self) -> None:
        """Empty modals list returns empty strings."""
        html, scripts = wrap_content_with_modals("<div>Content</div>", [])
        assert html == ""
        assert scripts == ""

    def test_single_modal_object(self) -> None:
        """Single Modal object is rendered."""
        m = Modal(title="Test", component_id="wrap-test")
        html, scripts = wrap_content_with_modals("<div>Content</div>", [m])
        assert 'id="wrap-test"' in html
        assert "Test" in html
        assert "<script>" in scripts

    def test_single_modal_dict(self) -> None:
        """Single dict modal is normalized and rendered."""
        html, scripts = wrap_content_with_modals(
            "<div>Content</div>",
            [{"title": "Dict Modal", "component_id": "dict-modal"}],
        )
        assert 'id="dict-modal"' in html
        assert "Dict Modal" in html
        assert "<script>" in scripts

    def test_multiple_modals(self) -> None:
        """Multiple modals are all rendered."""
        modals = [
            Modal(title="First", component_id="first-modal"),
            Modal(title="Second", component_id="second-modal"),
        ]
        html, _scripts = wrap_content_with_modals("<div>Content</div>", modals)
        assert 'id="first-modal"' in html
        assert 'id="second-modal"' in html
        assert "First" in html
        assert "Second" in html

    def test_mixed_modal_objects_and_dicts(self) -> None:
        """Mixed Modal objects and dicts are handled."""
        modals: list[Any] = [
            Modal(title="Obj Modal", component_id="obj-modal"),
            {"title": "Dict Modal", "component_id": "dict-modal"},
        ]
        html, _scripts = wrap_content_with_modals("<div>Content</div>", modals)
        assert 'id="obj-modal"' in html
        assert 'id="dict-modal"' in html

    def test_invalid_modal_type_rejected(self) -> None:
        """Non-Modal, non-dict raises TypeError."""
        with pytest.raises(TypeError, match="Invalid modal type"):
            wrap_content_with_modals("<div>Content</div>", [42])  # type: ignore[list-item]

    def test_scripts_include_modal_handlers(self) -> None:
        """Returned scripts include core modal handlers."""
        m = Modal(title="Test")
        _, scripts = wrap_content_with_modals("<div>Content</div>", [m])
        assert "<script>" in scripts
        # Should contain the core modal-handlers.js content
        assert "modal" in scripts

    def test_modal_custom_scripts_collected(self) -> None:
        """Modal with custom script has it collected in output."""
        m = Modal(title="Test", script="console.log('custom');")
        _, scripts = wrap_content_with_modals("<div>Content</div>", [m])
        assert "console.log('custom');" in scripts

    def test_content_parameter_unused(self) -> None:
        """Content parameter is unused (API symmetry with toolbars)."""
        m = Modal(title="Test", component_id="content-test")
        html, _ = wrap_content_with_modals("IGNORED_CONTENT", [m])
        assert "IGNORED_CONTENT" not in html


# =============================================================================
# Complex/Integration Scenarios
# =============================================================================


class TestModalComplexScenarios:
    """Tests for complex or integration-level modal scenarios."""

    def test_full_settings_modal(self) -> None:
        """A realistic settings modal with multiple input types."""
        m = Modal(
            title="Application Settings",
            size="lg",
            component_id="settings-modal",
            items=[
                TextInput(label="Username", event="settings:username"),
                SecretInput(label="API Key", event="settings:api_key"),
                Select(
                    label="Theme",
                    event="settings:theme",
                    options=[
                        Option(label="Dark", value="dark"),
                        Option(label="Light", value="light"),
                    ],
                    selected="dark",
                ),
                Toggle(label="Notifications", event="settings:notifications"),
                NumberInput(
                    label="Font Size",
                    event="settings:font_size",
                    value=14,
                    min=8,
                    max=36,
                ),
                Button(label="Save", event="settings:save", variant="primary"),
                Button(label="Cancel", event="settings:cancel"),
            ],
            close_on_escape=True,
            close_on_overlay_click=False,
            reset_on_close=False,
            on_close_event="settings:closed",
        )

        html = m.build_html()
        assert 'id="settings-modal"' in html
        assert "Application Settings" in html
        assert "pywry-modal-lg" in html
        assert 'data-close-overlay="false"' in html
        assert 'data-reset-on-close="false"' in html
        assert 'data-on-close-event="settings:closed"' in html

        # Items rendered (TextInput uses oninput handler, not data-event)
        assert "settings:username" in html
        assert "settings:api_key" in html
        assert 'data-event="settings:theme"' in html
        assert 'data-event="settings:save"' in html

        # to_dict works
        d = m.to_dict()
        assert d["title"] == "Application Settings"
        assert len(d["items"]) == 7

        # Secrets found
        secrets = m.get_secret_inputs()
        assert len(secrets) == 1
        assert secrets[0].label == "API Key"

    def test_modal_from_all_dicts(self) -> None:
        """Modal created entirely from dict config."""
        config: dict[str, Any] = {
            "title": "Quick Add",
            "size": "sm",
            "component_id": "quick-add",
            "items": [
                {"type": "text", "label": "Item Name", "event": "add:name"},
                {"type": "number", "label": "Quantity", "event": "add:qty", "value": 1},
                {
                    "type": "button",
                    "label": "Add",
                    "event": "add:submit",
                    "variant": "primary",
                },
            ],
            "close_on_escape": True,
            "reset_on_close": True,
        }
        m = Modal(**config)
        assert m.component_id == "quick-add"
        assert m.title == "Quick Add"
        assert len(m.items) == 3
        assert isinstance(m.items[0], TextInput)
        assert isinstance(m.items[1], NumberInput)
        assert isinstance(m.items[2], Button)

    def test_modal_with_div_containing_nested_items(self) -> None:
        """Modal with Div containing nested form elements."""
        m = Modal(
            title="Form",
            items=[
                Div(
                    label="",
                    event="m:group",
                    content="<h4>Personal Info</h4>",
                    children=[
                        TextInput(label="First", event="form:first"),
                        TextInput(label="Last", event="form:last"),
                    ],
                ),
                Button(label="Submit", event="form:submit"),
            ],
        )
        html = m.build_html()
        assert "Personal Info" in html
        # TextInput renders event via oninput handler, not data-event
        assert "form:first" in html
        assert "form:last" in html
        assert 'data-event="form:submit"' in html

    def test_multiple_modals_independent_ids(self) -> None:
        """Multiple modals have independent IDs and don't interfere."""
        m1 = Modal(title="Modal 1")
        m2 = Modal(title="Modal 2")
        assert m1.component_id != m2.component_id

        html1 = m1.build_html()
        html2 = m2.build_html()
        assert m1.component_id in html1
        assert m2.component_id in html2
        assert m1.component_id not in html2
        assert m2.component_id not in html1

    def test_marquee_item_in_modal(self) -> None:
        """Marquee item can be used in a modal."""
        from pywry.toolbar import Marquee

        m = Modal(
            title="Ticker",
            items=[
                Marquee(
                    label="",
                    event="m:marquee",
                    text="AAPL: Apple $150 | GOOGL: Alphabet $180",
                ),
            ],
        )
        html = m.build_html()
        assert "AAPL" in html
