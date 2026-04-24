"""Helpers for emitting PyWry widgets as ``AppArtifact`` payloads.

A rendered PyWry widget already has its self-contained HTML stored in
``inline._state.widgets[widget_id]["html"]`` (see :func:`build_html` in
``pywry.templates``). This module bumps the per-widget revision counter
and wraps that HTML into a dict the MCP server wrapper recognizes as a
rich-content response — a sibling ``TextContent`` (structured data for
code-only MCP clients) plus an ``EmbeddedResource`` (for clients that
render ``text/html`` inline, e.g. Claude Desktop artifact pane, any
``mcp-ui``-aware client, or PyWry's own chat widget).

The returned dict carries a top-level ``_app_artifact`` key. Handlers
may merge this into whatever their normal return payload looks like;
the server layer strips the key, emits the rich content blocks, and
passes the remaining keys through as ordinary JSON.
"""

from __future__ import annotations

from typing import Any

from ..chat.artifacts import AppArtifact


def build_app_artifact(
    widget_id: str,
    *,
    title: str = "",
    height: str = "600px",
    sandbox: bool = True,
) -> AppArtifact | None:
    """Build an :class:`AppArtifact` for *widget_id*.

    Looks up the widget's stored HTML, bumps its revision counter, and
    returns a populated :class:`AppArtifact`. Returns ``None`` when the
    widget's HTML cannot be found (e.g. native-window mode without a
    browser server, or the widget was never registered).
    """
    # Lazy import to avoid circulars
    from ..inline import _state

    record = _state.widgets.get(widget_id)
    if not record or not record.get("html"):
        return None

    revision = _state.bump_widget_revision(widget_id)

    return AppArtifact(
        title=title or f"PyWry widget {widget_id[:8]}",
        html=record["html"],
        widget_id=widget_id,
        revision=revision,
        height=height,
        sandbox=sandbox,
    )


def attach_app_artifact(
    result: dict[str, Any],
    widget_id: str,
    *,
    title: str = "",
    height: str = "600px",
    sandbox: bool = True,
) -> dict[str, Any]:
    """Attach an app-artifact snapshot to a handler result dict.

    Mutates and returns *result*, adding a ``_app_artifact`` key that
    the MCP server wrapper turns into a rich ``EmbeddedResource`` content
    block. Returns *result* unchanged when no snapshot can be built
    (e.g. native-window mode).
    """
    artifact = build_app_artifact(widget_id, title=title, height=height, sandbox=sandbox)
    if artifact is None:
        return result

    result["_app_artifact"] = {
        "artifact_type": "app",
        "title": artifact.title,
        "widget_id": artifact.widget_id,
        "revision": artifact.revision,
        "height": artifact.height,
        "sandbox": artifact.sandbox,
        "html": artifact.html,
        "uri": f"pywry-app://{widget_id}/{artifact.revision}",
        "mime_type": "text/html",
    }
    return result
