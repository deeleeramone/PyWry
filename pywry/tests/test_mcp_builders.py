"""Tests for ``pywry.mcp.builders``.

Each builder converts a config dict into the corresponding Pydantic
toolbar/chat component. Tests verify both the type and at least one
non-default field per builder.
"""

from __future__ import annotations

import pytest


class TestBuildButton:
    def test_basic(self) -> None:
        from pywry.mcp.builders import _build_button
        from pywry.toolbar import Button

        btn = _build_button({"label": "Test", "event": "app:test", "variant": "primary"})
        assert isinstance(btn, Button)
        assert btn.label == "Test"
        assert btn.event == "app:test"
        assert btn.variant == "primary"

    def test_with_size_and_data(self) -> None:
        from pywry.mcp.builders import _build_button

        btn = _build_button({"label": "X", "event": "x:click", "size": "lg", "data": {"k": "v"}})
        assert btn.size == "lg"
        assert btn.data == {"k": "v"}


class TestBuildSelect:
    def test_basic(self) -> None:
        from pywry.mcp.builders import _build_select
        from pywry.toolbar import Select

        cfg = {
            "label": "Choose",
            "event": "form:select",
            "options": [{"label": "A", "value": "a"}, {"label": "B", "value": "b"}],
            "selected": "a",
        }
        sel = _build_select(cfg)
        assert isinstance(sel, Select)
        assert sel.label == "Choose"
        assert len(sel.options) == 2

    def test_placeholder_rejected_by_select(self) -> None:
        """The builder forwards placeholder; the underlying Select rejects it.

        Documents existing contract: Select does NOT support placeholders.
        """
        from pydantic import ValidationError

        from pywry.mcp.builders import _build_select

        with pytest.raises(ValidationError):
            _build_select({"label": "L", "event": "x:y", "placeholder": "Pick"})


class TestBuildPrimitives:
    def test_toggle(self) -> None:
        from pywry.mcp.builders import _build_toggle
        from pywry.toolbar import Toggle

        t = _build_toggle({"label": "Enable", "event": "app:toggle", "value": True})
        assert isinstance(t, Toggle)
        assert t.value is True

    def test_checkbox(self) -> None:
        from pywry.mcp.builders import _build_checkbox
        from pywry.toolbar import Checkbox

        c = _build_checkbox({"label": "Agree", "event": "form:agree", "value": False})
        assert isinstance(c, Checkbox)
        assert c.label == "Agree"

    def test_text(self) -> None:
        from pywry.mcp.builders import _build_text
        from pywry.toolbar import TextInput

        t = _build_text({"label": "Name", "event": "form:name", "placeholder": "Enter name"})
        assert isinstance(t, TextInput)
        assert t.placeholder == "Enter name"

    def test_number(self) -> None:
        from pywry.mcp.builders import _build_number
        from pywry.toolbar import NumberInput

        n = _build_number({"label": "Qty", "event": "form:qty", "min": 1, "max": 100, "step": 1})
        assert isinstance(n, NumberInput)
        assert n.min == 1
        assert n.max == 100

    def test_slider(self) -> None:
        from pywry.mcp.builders import _build_slider
        from pywry.toolbar import SliderInput

        s = _build_slider({"event": "app:slider", "value": 50, "min": 0, "max": 100})
        assert isinstance(s, SliderInput)
        assert s.value == 50

    def test_div(self) -> None:
        from pywry.mcp.builders import _build_div
        from pywry.toolbar import Div

        d = _build_div({"content": "<p>Hello</p>", "component_id": "my-div"})
        assert isinstance(d, Div)
        assert d.component_id == "my-div"

    def test_multiselect(self) -> None:
        from pywry.mcp.builders import _build_multiselect
        from pywry.toolbar import MultiSelect

        m = _build_multiselect(
            {
                "label": "Tags",
                "event": "form:tags",
                "options": [{"label": "A", "value": "a"}, {"label": "B", "value": "b"}],
                "selected": ["a"],
            }
        )
        assert isinstance(m, MultiSelect)
        assert m.selected == ["a"]

    def test_radio(self) -> None:
        from pywry.mcp.builders import _build_radio
        from pywry.toolbar import RadioGroup

        r = _build_radio(
            {
                "label": "Size",
                "event": "form:size",
                "options": [{"label": "S"}, {"label": "M"}, {"label": "L"}],
                "selected": "M",
            }
        )
        assert isinstance(r, RadioGroup)
        assert r.selected == "M"

    def test_tabs(self) -> None:
        from pywry.mcp.builders import _build_tabs
        from pywry.toolbar import TabGroup

        t = _build_tabs(
            {
                "event": "view:tab",
                "options": [
                    {"label": "Chart", "value": "chart"},
                    {"label": "Table", "value": "table"},
                ],
                "selected": "chart",
            }
        )
        assert isinstance(t, TabGroup)
        assert t.selected == "chart"

    def test_textarea(self) -> None:
        from pywry.mcp.builders import _build_textarea
        from pywry.toolbar import TextArea

        t = _build_textarea({"label": "Notes", "event": "form:notes", "rows": 5})
        assert isinstance(t, TextArea)
        assert t.rows == 5

    def test_search(self) -> None:
        from pywry.mcp.builders import _build_search
        from pywry.toolbar import SearchInput

        s = _build_search({"label": "Search", "event": "data:search", "debounce": 500})
        assert isinstance(s, SearchInput)
        assert s.debounce == 500

    def test_date(self) -> None:
        from pywry.mcp.builders import _build_date
        from pywry.toolbar import DateInput

        d = _build_date({"label": "Date", "event": "form:date", "value": "2024-01-15"})
        assert isinstance(d, DateInput)
        assert d.value == "2024-01-15"

    def test_date_with_min_max(self) -> None:
        from pywry.mcp.builders import _build_date

        d = _build_date({"label": "L", "event": "x:y", "min": "2024-01-01", "max": "2024-12-31"})
        assert d.min == "2024-01-01"
        assert d.max == "2024-12-31"

    def test_range(self) -> None:
        from pywry.mcp.builders import _build_range
        from pywry.toolbar import RangeInput

        r = _build_range({"event": "app:range", "start": 10, "end": 90, "min": 0, "max": 100})
        assert isinstance(r, RangeInput)
        assert r.start == 10
        assert r.end == 90

    def test_secret(self) -> None:
        from pywry.mcp.builders import _build_secret
        from pywry.toolbar import SecretInput

        s = _build_secret({"label": "API Key", "event": "form:api_key", "show_toggle": True})
        assert isinstance(s, SecretInput)
        assert s.show_toggle is True


class TestBuildMarquee:
    def test_basic(self) -> None:
        from pywry.mcp.builders import _build_marquee
        from pywry.toolbar import Marquee

        m = _build_marquee({"text": "Scrolling text", "speed": 10})
        assert isinstance(m, Marquee)
        assert m.speed == 10

    def test_with_ticker_items(self) -> None:
        from pywry.mcp.builders import _build_marquee

        cfg = {
            "ticker_items": [
                {"ticker": "AAPL", "text": "AAPL: $150"},
                {"ticker": "GOOG", "text": "GOOG: $2800"},
            ]
        }
        m = _build_marquee(cfg)
        assert "data-ticker" in m.text

    def test_with_separator(self) -> None:
        from pywry.mcp.builders import _build_marquee

        m = _build_marquee({"text": "x", "separator": "|"})
        assert m.separator == "|"


class TestBuildOptions:
    def test_basic(self) -> None:
        from pywry.mcp.builders import _build_options
        from pywry.toolbar import Option

        opts = _build_options([{"label": "One", "value": "1"}, {"label": "Two", "value": "2"}])
        assert len(opts) == 2
        assert all(isinstance(o, Option) for o in opts)
        assert opts[0].value == "1"

    def test_label_only_falls_back_to_label_as_value(self) -> None:
        from pywry.mcp.builders import _build_options

        opts = _build_options([{"label": "X"}])
        assert opts[0].label == "X"
        assert opts[0].value == "X"

    def test_value_only_falls_back_to_value_as_label(self) -> None:
        from pywry.mcp.builders import _build_options

        opts = _build_options([{"value": "5"}])
        assert opts[0].label == "5"

    def test_none_input_returns_empty(self) -> None:
        from pywry.mcp.builders import _build_options

        assert _build_options(None) == []


class TestBuildToolbarItem:
    def test_dispatches_by_type(self) -> None:
        from pywry.mcp.builders import build_toolbar_item
        from pywry.toolbar import Button, Toggle

        btn = build_toolbar_item({"type": "button", "label": "Click", "event": "app:click"})
        assert isinstance(btn, Button)

        toggle = build_toolbar_item({"type": "toggle", "label": "T", "event": "app:t"})
        assert isinstance(toggle, Toggle)

    def test_unknown_type_returns_none(self) -> None:
        from pywry.mcp.builders import build_toolbar_item

        assert build_toolbar_item({"type": "unknown_component"}) is None


class TestBuildToolbars:
    def test_creates_toolbar_list(self) -> None:
        from pywry.mcp.builders import build_toolbars
        from pywry.toolbar import Toolbar

        data = [
            {
                "position": "top",
                "items": [
                    {"type": "button", "label": "Save", "event": "app:save"},
                    {"type": "button", "label": "Load", "event": "app:load"},
                ],
            },
            {
                "position": "bottom",
                "items": [{"type": "toggle", "label": "Dark", "event": "app:theme"}],
            },
        ]
        result = build_toolbars(data)
        assert len(result) == 2
        assert all(isinstance(t, Toolbar) for t in result)
        assert result[0].position == "top"
        assert len(result[0].items) == 2


class TestBuildChatConfig:
    def test_build_chat_config(self) -> None:
        from pywry.mcp.builders import build_chat_config

        cfg = build_chat_config(
            {
                "system_prompt": "P",
                "model": "gpt-x",
                "temperature": 0.8,
                "max_tokens": 1000,
                "streaming": False,
                "persist": True,
            }
        )
        assert cfg.model == "gpt-x"
        assert cfg.temperature == 0.8

    def test_build_chat_widget_config(self) -> None:
        from pywry.mcp.builders import build_chat_widget_config

        cfg = build_chat_widget_config(
            {
                "title": "Hello",
                "height": 800,
                "show_sidebar": False,
                "model": "gpt-4",
            }
        )
        assert cfg.title == "Hello"
        assert cfg.height == 800
        assert cfg.show_sidebar is False
        assert cfg.chat_config.model == "gpt-4"
