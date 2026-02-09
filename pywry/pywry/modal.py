# pylint: disable=too-many-lines
"""Pydantic models for PyWry modal components.

This module provides strongly-typed models for modal configurations:
- Modal container with sizing and behavior options
- Reuses toolbar input types (Button, Select, TextInput, etc.)
- Automatic component_id generation for state tracking

Usage:
    from pywry.modal import Modal
    from pywry.toolbar import Button, TextInput, Select, Option

    modal = Modal(
        title="Settings",
        size="md",
        items=[
            TextInput(label="Name", event="settings:name"),
            Select(
                label="Theme:",
                event="settings:theme",
                options=[Option(label="Dark", value="dark"), Option(label="Light", value="light")],
            ),
            Button(label="Save", event="settings:save", variant="primary"),
        ],
    )

    # Use in app.show()
    app.show(content, modals=[modal])

    # Open modal via JavaScript
    # pywry.modal.open('modal-id')
"""

from __future__ import annotations

import html
import uuid

from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from .toolbar import (
    Div,
    SecretInput,
    ToolbarItem,
    ToolbarItemUnion,
)


# Directory containing frontend source files
_SRC_DIR = Path(__file__).parent / "frontend" / "src"


def _generate_modal_id() -> str:
    """Generate a unique modal ID."""
    return f"modal-{uuid.uuid4().hex[:8]}"


# Type alias for modal items (same as toolbar items)
ModalItemUnion = ToolbarItemUnion

# Annotated version with discriminator for Pydantic deserialization
AnyModalItem = Annotated[
    ModalItemUnion,
    Field(discriminator="type"),
]


# Item type map for dict -> model conversion (reuse from toolbar)
_ITEM_TYPE_MAP: dict[str, type[ToolbarItem]] = {}


def _get_item_type_map() -> dict[str, type[ToolbarItem]]:
    """Lazily build item type map from toolbar module."""
    global _ITEM_TYPE_MAP  # noqa: PLW0603
    if not _ITEM_TYPE_MAP:
        from .toolbar import (
            Button,
            Checkbox,
            DateInput,
            Marquee,
            MultiSelect,
            NumberInput,
            RadioGroup,
            RangeInput,
            SearchInput,
            Select,
            SliderInput,
            TabGroup,
            TextArea,
            TextInput,
            Toggle,
        )

        _ITEM_TYPE_MAP = {
            "button": Button,
            "select": Select,
            "multiselect": MultiSelect,
            "text": TextInput,
            "textarea": TextArea,
            "secret": SecretInput,
            "search": SearchInput,
            "number": NumberInput,
            "date": DateInput,
            "slider": SliderInput,
            "range": RangeInput,
            "toggle": Toggle,
            "checkbox": Checkbox,
            "radio": RadioGroup,
            "tab": TabGroup,
            "div": Div,
            "marquee": Marquee,
        }
    return _ITEM_TYPE_MAP


class Modal(BaseModel):
    """A modal overlay container with input components.

    Attributes
    ----------
        component_id: Unique identifier for this modal (auto-generated if not provided)
        title: Modal header title
        items: List of input items (Button, Select, TextInput, Div, etc.)
        size: Preset size ("sm", "md", "lg", "xl", "full")
        width: Custom width override (e.g., "600px")
        max_height: Maximum height before scrolling (default: "80vh")
        overlay_opacity: Background overlay opacity 0.0-1.0 (default: 0.5)
        close_on_escape: Close when Escape key pressed (default: True)
        close_on_overlay_click: Close when clicking outside modal (default: True)
        reset_on_close: Reset form inputs when closed (default: True)
        on_close_event: Custom event name to emit when modal closes
        open_on_load: Whether modal starts open (default: False)
        style: Inline CSS for the modal container
        script: JS file path or inline string to inject
        class_name: Custom CSS class for the modal container

    Example:
        Modal(
            title="User Settings",
            size="md",
            class_name="settings-modal",
            items=[
                TextInput(label="Username", event="user:name"),
                Toggle(label="Notifications", event="user:notifications"),
                Button(label="Save", event="user:save", variant="primary"),
            ],
            reset_on_close=False,  # Preserve values between opens
            on_close_event="settings:closed",
        )
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    # Identity & targeting
    component_id: str = Field(default_factory=_generate_modal_id)
    class_name: str = Field(
        default="",
        description="Custom CSS class for modal container",
    )

    # Content
    title: str = "Modal"
    items: Sequence[ToolbarItemUnion] = Field(default_factory=list)

    # Custom assets (matching Toolbar pattern)
    style: str = Field(
        default="",
        description="Inline CSS for modal container",
    )
    script: str | Path | None = Field(
        default=None,
        description="JS file path or inline script for the modal",
    )

    # Sizing
    size: Literal["sm", "md", "lg", "xl", "full"] = "md"
    width: str | None = Field(
        default=None,
        description="Custom width override (e.g., '600px')",
    )
    max_height: str = Field(
        default="80vh",
        description="Maximum height before body scrolls",
    )

    # Appearance
    overlay_opacity: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Background overlay opacity",
    )

    # Behavior
    close_on_escape: bool = Field(
        default=True,
        description="Close when Escape key pressed",
    )
    close_on_overlay_click: bool = Field(
        default=True,
        description="Close when clicking outside modal",
    )
    reset_on_close: bool = Field(
        default=True,
        description="Reset form inputs when closed",
    )
    on_close_event: str | None = Field(
        default=None,
        description="Custom event name to emit when modal closes",
    )
    open_on_load: bool = Field(
        default=False,
        description="Whether modal starts open",
    )

    @field_validator("items", mode="before")
    @classmethod
    def normalize_items(cls, v: Any) -> list[ToolbarItem]:
        """Accept list of dicts or ToolbarItem objects."""
        if not v:
            return []
        result: list[ToolbarItem] = []
        item_map = _get_item_type_map()
        for item in v:
            if isinstance(item, ToolbarItem):
                result.append(item)
            elif isinstance(item, dict):
                item_type = item.get("type", "button")
                item_class = item_map.get(item_type)
                if item_class is None:
                    raise ValueError(f"Unknown modal item type: {item_type}")
                result.append(item_class(**item))
            else:
                raise TypeError(f"Invalid modal item type: {type(item)}")
        return result

    def build_html(self) -> str:
        """Build complete modal HTML.

        Returns
        -------
        str
            The modal HTML structure with overlay, container, header, and body.
        """
        # Size presets map to CSS widths
        # Build item HTMLs
        item_htmls = []
        for item in self.items:
            if isinstance(item, Div):
                item_htmls.append(item.build_html(parent_id=self.component_id))
            else:
                item_htmls.append(item.build_html())

        # Build container classes
        classes = ["pywry-modal-container", f"pywry-modal-{self.size}"]
        if self.class_name:
            classes.append(self.class_name)

        # Inline style - only set width if explicitly provided, otherwise use CSS
        inline_style = f"max-height: {self.max_height};"
        if self.width:
            inline_style = f"width: {self.width}; {inline_style}"
        if self.style:
            inline_style += f" {self.style}"

        # Data attributes for JS handlers
        data_attrs = [
            f'data-component-id="{self.component_id}"',
            f'data-close-escape="{str(self.close_on_escape).lower()}"',
            f'data-close-overlay="{str(self.close_on_overlay_click).lower()}"',
            f'data-reset-on-close="{str(self.reset_on_close).lower()}"',
        ]
        if self.on_close_event:
            data_attrs.append(f'data-on-close-event="{html.escape(self.on_close_event)}"')

        open_class = " pywry-modal-open" if self.open_on_load else ""

        # Escape the title for safety
        escaped_title = html.escape(self.title)

        return f"""<div id="{self.component_id}" class="pywry-modal-overlay{open_class}"
     style="--pywry-modal-overlay-opacity: {self.overlay_opacity};"
     {" ".join(data_attrs)}>
    <div class="{" ".join(classes)}" style="{inline_style}" onclick="event.stopPropagation()">
        <div class="pywry-modal-header">
            <h3 class="pywry-modal-title">{escaped_title}</h3>
            <button class="pywry-modal-close" type="button" aria-label="Close modal"
                    onclick="pywry.modal.close('{self.component_id}')">&times;</button>
        </div>
        <div class="pywry-modal-body">
            {"".join(item_htmls)}
        </div>
    </div>
</div>"""

    def collect_scripts(self) -> list[str]:
        """Collect scripts from modal and all nested Div children.

        Modal script runs first, then Div scripts in item order.

        Returns
        -------
        list[str]
            List of script content strings.
        """
        scripts: list[str] = []

        # Modal script first (parent context available to children)
        if self.script:
            if isinstance(self.script, Path):
                if self.script.exists():
                    scripts.append(self.script.read_text(encoding="utf-8"))
            elif isinstance(self.script, str):
                # Check if it looks like a file path or inline script
                if not self.script.strip().startswith(
                    (
                        "(",
                        "{",
                        "function",
                        "//",
                        "/*",
                        "var ",
                        "let ",
                        "const ",
                        "if ",
                        "for ",
                        "while ",
                    )
                ):
                    # Treat as file path
                    script_path = Path(self.script)
                    if script_path.exists():
                        scripts.append(script_path.read_text(encoding="utf-8"))
                    else:
                        # Not a valid path, treat as inline script
                        scripts.append(self.script)
                else:
                    scripts.append(self.script)

        # Children's scripts (depth-first)
        for item in self.items:
            if isinstance(item, Div):
                scripts.extend(item.collect_scripts())

        return scripts

    def to_dict(self) -> dict[str, Any]:
        """Convert modal to dict for state/serialization.

        Returns
        -------
        dict
            Modal configuration as a dictionary.
        """
        return {
            "component_id": self.component_id,
            "title": self.title,
            "size": self.size,
            "width": self.width,
            "max_height": self.max_height,
            "overlay_opacity": self.overlay_opacity,
            "close_on_escape": self.close_on_escape,
            "close_on_overlay_click": self.close_on_overlay_click,
            "reset_on_close": self.reset_on_close,
            "on_close_event": self.on_close_event,
            "open_on_load": self.open_on_load,
            "style": self.style,
            "class_name": self.class_name,
            "items": [
                {
                    "component_id": item.component_id,
                    "type": item.type,
                    "label": item.label,
                    "event": item.event,
                    "style": item.style,
                    "disabled": item.disabled,
                    **item.model_dump(
                        exclude={
                            "component_id",
                            "type",
                            "label",
                            "event",
                            "style",
                            "disabled",
                        }
                    ),
                }
                for item in self.items
            ],
        }

    def get_secret_inputs(self) -> list[SecretInput]:
        """Get all SecretInput items in this modal (including nested in Divs).

        Returns
        -------
        list[SecretInput]
            All SecretInput components found.
        """
        secrets: list[SecretInput] = []
        for item in self.items:
            if isinstance(item, SecretInput):
                secrets.append(item)
            elif isinstance(item, Div) and hasattr(item, "get_secret_inputs"):
                secrets.extend(item.get_secret_inputs())
        return secrets


@lru_cache(maxsize=1)
def _get_modal_handlers_js() -> str:
    """Load modal handler JavaScript.

    Returns
    -------
    str
        The modal-handlers.js content.
    """
    modal_handlers_path = _SRC_DIR / "modal-handlers.js"
    if not modal_handlers_path.exists():
        raise RuntimeError(f"Modal handlers JS not found: {modal_handlers_path}")
    return modal_handlers_path.read_text(encoding="utf-8")


def get_modal_script() -> str:
    """Get the modal initialization script.

    This script is injected once per page to enable modal functionality.

    Returns
    -------
    str
        Complete modal script wrapped in script tags.
    """
    handlers_js = _get_modal_handlers_js()
    return f"<script>{handlers_js}</script>"


def wrap_content_with_modals(
    _content: str,  # Kept for API symmetry with toolbars
    modals: Sequence[Modal | dict[str, Any]] | None,
) -> tuple[str, str]:
    """Build modal HTML and scripts to inject into page.

    Parameters
    ----------
    content : str
        The main page content (unused, kept for API symmetry with toolbars).
    modals : Sequence[Modal | dict] | None
        List of Modal objects or dicts to render.

    Returns
    -------
    tuple[str, str]
        A tuple of (modal_html, modal_scripts) to inject into the page.
    """
    if not modals:
        return "", ""

    # Normalize modals
    normalized: list[Modal] = []
    for modal in modals:
        if isinstance(modal, Modal):
            normalized.append(modal)
        elif isinstance(modal, dict):
            normalized.append(Modal(**modal))
        else:
            raise TypeError(f"Invalid modal type: {type(modal)}")

    # Build modal HTML
    modal_html = "\n".join(m.build_html() for m in normalized)

    # Collect scripts from modals
    modal_scripts_list = [get_modal_script()]  # Core handlers first
    modal_scripts_list.extend(
        f"<script>{script}</script>" for modal in normalized for script in modal.collect_scripts()
    )

    modal_scripts = "\n".join(modal_scripts_list)

    return modal_html, modal_scripts
