"""Toolbar builders for MCP widget creation.

This module provides functions to build toolbars and toolbar items
from configuration dictionaries.
"""

from __future__ import annotations

from typing import Any


def _build_options(opts_data: list[dict[str, Any]] | None) -> list[Any]:
    """Build options list for select-type components."""
    from pywry.toolbar import Option

    return [
        Option(
            label=o.get("label") or str(o.get("value", "")),
            value=o.get("value") or o.get("label", ""),
        )
        for o in (opts_data or [])
    ]


def _build_button(cfg: dict[str, Any]) -> Any:
    from pywry.toolbar import Button

    kwargs = {
        "label": cfg.get("label", "Button"),
        "event": cfg.get("event", "app:click"),
        "variant": cfg.get("variant", "neutral"),
        "disabled": cfg.get("disabled", False),
    }
    if cfg.get("size"):
        kwargs["size"] = cfg["size"]
    if cfg.get("data"):
        kwargs["data"] = cfg["data"]
    return Button(**kwargs)


def _build_select(cfg: dict[str, Any]) -> Any:
    from pywry.toolbar import Select

    kwargs = {
        "label": cfg.get("label") or "",
        "event": cfg.get("event", "app:select"),
        "options": _build_options(cfg.get("options")),
        "selected": cfg.get("selected") or "",
        "searchable": cfg.get("searchable", False),
    }
    if cfg.get("placeholder"):
        kwargs["placeholder"] = cfg["placeholder"]
    return Select(**kwargs)


def _build_multiselect(cfg: dict[str, Any]) -> Any:
    from pywry.toolbar import MultiSelect

    return MultiSelect(
        label=cfg.get("label") or "",
        event=cfg.get("event", "app:multiselect"),
        options=_build_options(cfg.get("options")),
        selected=cfg.get("selected") or [],
    )


def _build_toggle(cfg: dict[str, Any]) -> Any:
    from pywry.toolbar import Toggle

    return Toggle(
        label=cfg.get("label", "Toggle"),
        event=cfg.get("event", "app:toggle"),
        value=cfg.get("value", False),
    )


def _build_checkbox(cfg: dict[str, Any]) -> Any:
    from pywry.toolbar import Checkbox

    return Checkbox(
        label=cfg.get("label", "Checkbox"),
        event=cfg.get("event", "app:checkbox"),
        value=cfg.get("value", False),
        disabled=cfg.get("disabled", False),
    )


def _build_radio(cfg: dict[str, Any]) -> Any:
    from pywry.toolbar import RadioGroup

    return RadioGroup(
        label=cfg.get("label") or "",
        event=cfg.get("event", "app:radio"),
        options=_build_options(cfg.get("options")),
        selected=cfg.get("selected") or "",
        direction=cfg.get("direction", "horizontal"),
        disabled=cfg.get("disabled", False),
    )


def _build_tabs(cfg: dict[str, Any]) -> Any:
    from pywry.toolbar import TabGroup

    return TabGroup(
        event=cfg.get("event", "app:tab"),
        options=_build_options(cfg.get("options")),
        selected=cfg.get("selected") or "",
        size=cfg.get("size", "md"),
        disabled=cfg.get("disabled", False),
    )


def _build_text(cfg: dict[str, Any]) -> Any:
    from pywry.toolbar import TextInput

    return TextInput(
        label=cfg.get("label") or "",
        event=cfg.get("event", "app:text"),
        value=cfg.get("value", ""),
        placeholder=cfg.get("placeholder") or "",
        disabled=cfg.get("disabled", False),
    )


def _build_textarea(cfg: dict[str, Any]) -> Any:
    from pywry.toolbar import TextArea

    return TextArea(
        label=cfg.get("label") or "",
        event=cfg.get("event", "app:textarea"),
        value=cfg.get("value", ""),
        placeholder=cfg.get("placeholder") or "",
        rows=cfg.get("rows", 3),
        disabled=cfg.get("disabled", False),
    )


def _build_search(cfg: dict[str, Any]) -> Any:
    from pywry.toolbar import SearchInput

    return SearchInput(
        label=cfg.get("label") or "",
        event=cfg.get("event", "app:search"),
        value=cfg.get("value", ""),
        placeholder=cfg.get("placeholder") or "Search...",
        debounce=cfg.get("debounce", 300),
    )


def _build_number(cfg: dict[str, Any]) -> Any:
    from pywry.toolbar import NumberInput

    return NumberInput(
        label=cfg.get("label") or "",
        event=cfg.get("event", "app:number"),
        value=cfg.get("value", 0),
        min=cfg.get("min"),
        max=cfg.get("max"),
        step=cfg.get("step", 1),
        disabled=cfg.get("disabled", False),
    )


def _build_date(cfg: dict[str, Any]) -> Any:
    from pywry.toolbar import DateInput

    kwargs = {
        "label": cfg.get("label") or "",
        "event": cfg.get("event", "app:date"),
        "value": cfg.get("value", ""),
    }
    if cfg.get("min"):
        kwargs["min"] = cfg["min"]
    if cfg.get("max"):
        kwargs["max"] = cfg["max"]
    return DateInput(**kwargs)


def _build_slider(cfg: dict[str, Any]) -> Any:
    from pywry.toolbar import SliderInput

    return SliderInput(
        label=cfg.get("label") or "",
        event=cfg.get("event", "app:slider"),
        value=cfg.get("value", 50),
        min=cfg.get("min", 0),
        max=cfg.get("max", 100),
        step=cfg.get("step", 1),
        show_value=cfg.get("show_value", True),
    )


def _build_range(cfg: dict[str, Any]) -> Any:
    from pywry.toolbar import RangeInput

    value = cfg.get("value") or [25, 75]
    start: float | int = cfg.get("start") or (value[0] if isinstance(value, list) else 25)
    end: float | int = cfg.get("end") or (value[1] if isinstance(value, list) else 75)
    return RangeInput(
        label=cfg.get("label") or "",
        event=cfg.get("event", "app:range"),
        start=start,
        end=end,
        min=cfg.get("min", 0),
        max=cfg.get("max", 100),
        step=cfg.get("step", 1),
        show_value=cfg.get("show_value", True),
    )


def _build_div(cfg: dict[str, Any]) -> Any:
    from pywry.toolbar import Div

    return Div(
        content=cfg.get("content", ""),
        component_id=cfg.get("component_id") or cfg.get("id") or "",
        style=cfg.get("style") or "",
        class_name=cfg.get("class_name") or "",
    )


def _build_secret(cfg: dict[str, Any]) -> Any:
    from pywry.toolbar import SecretInput

    return SecretInput(
        label=cfg.get("label") or "",
        event=cfg.get("event", "app:secret"),
        value=cfg.get("value", ""),
        placeholder=cfg.get("placeholder") or "",
        show_toggle=cfg.get("show_toggle", True),
        show_copy=cfg.get("show_copy", True),
    )


def _build_marquee(cfg: dict[str, Any]) -> Any:
    from pywry.toolbar import Marquee, TickerItem

    ticker_items = cfg.get("ticker_items", [])
    if ticker_items:
        items_html = " • ".join(
            TickerItem(
                ticker=ti.get("ticker", ""),
                text=ti.get("text", ""),
                html=ti.get("html", ""),
                class_name=ti.get("class_name", ""),
                style=ti.get("style", ""),
            ).build_html()
            for ti in ticker_items
        )
        text = items_html
    else:
        text = cfg.get("text", "")

    kwargs = {
        "text": text,
        "event": cfg.get("event", "app:marquee"),
        "speed": cfg.get("speed", 15),
        "direction": cfg.get("direction", "left"),
        "behavior": cfg.get("behavior", "scroll"),
        "pause_on_hover": cfg.get("pause_on_hover", True),
        "gap": cfg.get("gap", 50),
        "clickable": cfg.get("clickable", False),
    }
    if cfg.get("separator"):
        kwargs["separator"] = cfg["separator"]
    return Marquee(**kwargs)


# Dispatch table mapping component types to builder functions
_COMPONENT_BUILDERS: dict[str, Any] = {
    "button": _build_button,
    "select": _build_select,
    "multiselect": _build_multiselect,
    "toggle": _build_toggle,
    "checkbox": _build_checkbox,
    "radio": _build_radio,
    "tabs": _build_tabs,
    "text": _build_text,
    "textarea": _build_textarea,
    "search": _build_search,
    "number": _build_number,
    "date": _build_date,
    "slider": _build_slider,
    "range": _build_range,
    "div": _build_div,
    "secret": _build_secret,
    "marquee": _build_marquee,
}


def build_toolbar_item(cfg: dict[str, Any]) -> Any | None:
    """Build a single toolbar item from config dict.

    Parameters
    ----------
    cfg : dict[str, Any]
        Configuration dictionary with 'type' and component-specific options.

    Returns
    -------
    Any or None
        Toolbar component instance or None if type is unknown.
    """
    component_type = cfg.get("type", "button")
    builder = _COMPONENT_BUILDERS.get(component_type)
    if builder:
        return builder(cfg)
    return None


def build_toolbars(toolbars_data: list[dict[str, Any]]) -> list[Any]:
    """Build Toolbar objects from config dicts.

    Parameters
    ----------
    toolbars_data : list[dict[str, Any]]
        List of toolbar configurations with 'position' and 'items'.

    Returns
    -------
    list[Any]
        Built toolbar instances.
    """
    from pywry.toolbar import Toolbar

    toolbars: list[Any] = []
    for tb_config in toolbars_data:
        items: list[Any] = []
        for cfg in tb_config.get("items", []):
            item = build_toolbar_item(cfg)
            if item is not None:
                items.append(item)
        toolbars.append(
            Toolbar(
                position=tb_config.get("position", "top"),
                items=items,
                class_name=tb_config.get("class_name") or "",
            )
        )
    return toolbars
