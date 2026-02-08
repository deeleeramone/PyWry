"""Demo: Modal component with interactive controls.

This example shows a Plotly chart with a modal dialog for settings.
Click the Settings button to open the modal, change values, and click Apply.
All changes update the existing chart in place using Plotly's update APIs.
"""

from typing import Any

import plotly.graph_objects as go

from pywry import Button, NumberInput, Option, PyWry, Select, TextInput, Toolbar
from pywry.modal import Modal


# Will be set after widget is created
widget = None


def on_title_change(data: dict[str, Any], _event_type: str, _label: str) -> None:
    """Update chart title in place."""
    if widget:
        widget.emit("plotly:update-layout", {"layout": {"title.text": data.get("value", "")}})


def on_xlabel_change(data: dict[str, Any], _event_type: str, _label: str) -> None:
    """Update X-axis label in place."""
    if widget:
        widget.emit("plotly:update-layout", {"layout": {"xaxis.title.text": data.get("value")}})


def on_ylabel_change(data: dict[str, Any], _event_type: str, _label: str) -> None:
    """Update Y-axis label in place."""
    if widget:
        widget.emit("plotly:update-layout", {"layout": {"yaxis.title.text": data.get("value")}})


def on_color_change(data: dict[str, Any], _event_type: str, _label: str) -> None:
    """Update line color in place."""
    if widget:
        widget.emit(
            "plotly:update-traces",
            {"update": {"line.color": data.get("value")}, "indices": [0]},
        )


def on_style_change(data: dict[str, Any], _event_type: str, _label: str) -> None:
    """Update line dash style in place."""
    if widget:
        widget.emit(
            "plotly:update-traces",
            {"update": {"line.dash": data.get("value")}, "indices": [0]},
        )


def on_width_change(data: dict[str, Any], _event_type: str, _label: str) -> None:
    """Update line width in place."""
    if widget:
        widget.emit(
            "plotly:update-traces",
            {"update": {"line.width": int(data.get("value", 2))}, "indices": [0]},
        )


def on_marker_change(data: dict[str, Any], _event_type: str, _label: str) -> None:
    """Update marker size in place."""
    if widget:
        widget.emit(
            "plotly:update-traces",
            {"update": {"marker.size": int(data.get("value", 8))}, "indices": [0]},
        )


# Modal with settings controls
settings_modal = Modal(
    component_id="settings-modal",
    title="Chart Settings",
    reset_on_close=False,  # Keep changes in modal when closed
    items=[
        TextInput(
            label="Chart Title",
            event="settings:title",
            value="Modal Demo Chart",
        ),
        TextInput(
            label="X-Axis Label",
            event="settings:xlabel",
            value="X Axis",
        ),
        TextInput(
            label="Y-Axis Label",
            event="settings:ylabel",
            value="Y Axis",
        ),
        Select(
            label="Line Color",
            event="settings:color",
            selected="#1f77b4",
            options=[
                Option(label="Blue", value="#1f77b4"),
                Option(label="Red", value="#d62728"),
                Option(label="Green", value="#2ca02c"),
                Option(label="Orange", value="#ff7f0e"),
                Option(label="Purple", value="#9467bd"),
            ],
        ),
        Select(
            label="Line Style",
            event="settings:style",
            selected="solid",
            options=[
                Option(label="Solid", value="solid"),
                Option(label="Dashed", value="dash"),
                Option(label="Dotted", value="dot"),
            ],
        ),
        NumberInput(
            label="Line Width",
            event="settings:width",
            value=2,
            min=1,
            max=10,
            step=1,
        ),
        NumberInput(
            label="Marker Size",
            event="settings:marker",
            value=8,
            min=2,
            max=20,
            step=1,
        ),
    ],
)

# Toolbar with button to open the modal
toolbar = Toolbar(
    position="top",
    items=[
        Button(
            label="⚙ Settings",
            event="modal:open:settings-modal",
            variant="neutral",
        ),
    ],
)


def build_initial_figure() -> go.Figure:
    """Build initial chart figure."""
    x = list(range(1, 11))
    y = [i**2 for i in x]
    figure = go.Figure(
        go.Scatter(
            x=x,
            y=y,
            mode="lines+markers",
            line={"color": "#1f77b4", "width": 2, "dash": "solid"},
            marker={"size": 8},
        )
    )
    figure.update_layout(
        title="Modal Demo Chart",
        xaxis_title="X Axis",
        yaxis_title="Y Axis",
        template="plotly_dark",
    )
    return figure


# Create app and show chart
app = PyWry()
fig = build_initial_figure()

widget = app.show_plotly(
    fig,
    title="Chart with Modal Demo",
    toolbars=[toolbar],
    modals=[settings_modal],
    callbacks={
        "settings:title": on_title_change,
        "settings:xlabel": on_xlabel_change,
        "settings:ylabel": on_ylabel_change,
        "settings:color": on_color_change,
        "settings:style": on_style_change,
        "settings:width": on_width_change,
        "settings:marker": on_marker_change,
    },
    config={"displayModeBar": False},
)

app.block()
