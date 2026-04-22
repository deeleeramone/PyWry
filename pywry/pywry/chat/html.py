"""HTML template builder for the Chat component.

Constructs the DOM structure for the chat widget, following
VS Code's Copilot Chat layout pattern.
"""

from __future__ import annotations


def build_chat_html(
    *,
    show_sidebar: bool = True,
    show_settings: bool = True,
    enable_context: bool = False,
    enable_file_attach: bool = False,
    file_accept_types: list[str] | None = None,
    container_id: str = "",
    header_actions: str = "",
) -> str:
    """Build the HTML structure for a chat widget.

    The layout follows VS Code's Copilot Chat pattern: a compact header
    bar with conversation management and settings, a full-width scrollable
    message area, and an input bar at the bottom.

    Parameters
    ----------
    show_sidebar : bool
        Include the thread/conversation picker in the header bar.
    show_settings : bool
        Include the settings toggle button in the header.
    enable_context : bool
        Enable ``@``-mention widget references in the chat input.
    enable_file_attach : bool
        Show the attach button and enable drag-and-drop file attachments.
    file_accept_types : list[str] | None
        Restrict the file picker to specific extensions (e.g.
        ``[".csv", ".json"]``). ``None`` uses a broad default set.
    container_id : str
        Optional id for the outer container div.
    header_actions : str
        Extra HTML injected into the header-actions area.

    Returns
    -------
    str
        HTML string for the chat widget.
    """
    # Conversation picker (dropdown) in header
    sidebar_html = ""
    if show_sidebar:
        sidebar_html = (
            '<div class="pywry-chat-conv-picker">'
            '<button id="pywry-chat-conv-btn" class="pywry-chat-conv-btn" data-tooltip="Switch conversation">'
            '<span id="pywry-chat-conv-title" class="pywry-chat-conv-title">New Chat</span>'
            '<svg width="12" height="12" viewBox="0 0 12 12" class="pywry-chat-chevron">'
            '<path d="M3 5l3 3 3-3" stroke="currentColor" fill="none" stroke-width="1.5"/>'
            "</svg>"
            "</button>"
            '<div id="pywry-chat-conv-dropdown" class="pywry-chat-conv-dropdown">'
            '<div id="pywry-chat-sidebar" class="pywry-chat-thread-list"></div>'
            "</div>"
            "</div>"
        )

    settings_html = ""
    if show_settings:
        settings_html = (
            '<div class="pywry-chat-settings-menu">'
            '<button id="pywry-chat-settings-toggle" class="pywry-chat-header-btn" data-tooltip="Settings">'
            '<svg width="16" height="16" viewBox="0 0 16 16">'
            '<path d="M9.1 4.4L8.6 2H7.4l-.5 2.4-.7.3-2-1.3-.9.8 1.3 2-.3.7L2 7.4v1.2l2.4.5.3.7-1.3 2 .8.9 2-1.3.7.3.5 2.4h1.2l.5-2.4.7-.3 2 1.3.9-.8-1.3-2 .3-.7 2.4-.5V7.4l-2.4-.5-.3-.7 1.3-2-.8-.9-2 1.3-.7-.3zM8 10a2 2 0 110-4 2 2 0 010 4z" '
            'fill="currentColor"/>'
            "</svg>"
            "</button>"
            '<div id="pywry-chat-settings" class="pywry-chat-settings-dropdown"></div>'
            "</div>"
        )

    container_attr = f' id="{container_id}"' if container_id else ""

    # Build data attribute for accepted file types (frontend validation)
    accept_data = ""
    if file_accept_types and enable_file_attach:
        import html as html_mod

        accept_data = f' data-accept-types="{html_mod.escape(",".join(file_accept_types))}"'

    return (
        f'<div class="pywry-chat"{container_attr}{accept_data}>'
        # Header bar
        '<div class="pywry-chat-header">'
        '<div class="pywry-chat-header-left">' + sidebar_html + "</div>"
        '<div class="pywry-chat-header-actions">'
        + header_actions
        + '<button id="pywry-chat-new-thread" class="pywry-chat-header-btn" data-tooltip="New chat">'
        '<svg width="16" height="16" viewBox="0 0 16 16">'
        '<path d="M8 3v10M3 8h10" stroke="currentColor" fill="none" stroke-width="1.5" stroke-linecap="round"/>'
        "</svg>"
        "</button>"
        '<button id="pywry-chat-fullscreen-btn" class="pywry-chat-header-btn" data-tooltip="Toggle full width">'
        '<svg width="16" height="16" viewBox="0 0 16 16" class="pywry-chat-fullscreen-expand">'
        '<path d="M2 2h5v1.5H4.3L7 6.2 5.9 7.3 3.5 4.6V7H2V2zm12 12h-5v-1.5h2.7L9 9.8l1.1-1.1 2.4 2.7V9H14v5z" fill="currentColor"/>'
        "</svg>"
        '<svg width="16" height="16" viewBox="0 0 16 16" class="pywry-chat-fullscreen-collapse" style="display:none">'
        '<path d="M7 7H2v1.5h2.7L2 11.2l1.1 1.1L5.5 9.6V12H7V7zm2 2h5V7.5h-2.7L14 4.8 12.9 3.7 10.5 6.4V4H9v5z" fill="currentColor"/>'
        "</svg>"
        "</button>" + settings_html + "</div>"
        "</div>"
        # Messages
        '<div id="pywry-chat-messages" class="pywry-chat-messages"></div>'
        '<div id="pywry-chat-typing" class="pywry-chat-typing">Thinking</div>'
        '<div id="pywry-chat-new-msg-badge" class="pywry-chat-new-msg-badge">New messages</div>'
        # Plan / todo list (above input bar)
        '<div id="pywry-chat-todo" class="pywry-chat-todo"></div>'
        # Input bar
        '<div class="pywry-chat-input-bar">'
        '<div id="pywry-chat-cmd-palette" class="pywry-chat-cmd-palette"></div>'
        # Mention popup (@ autocomplete)
        + (
            '<div id="pywry-chat-mention-popup" class="pywry-chat-mention-popup"></div>'
            if enable_context
            else ""
        )
        +
        # Attachments bar
        '<div id="pywry-chat-attachments-bar" class="pywry-chat-attachments-bar"></div>'
        '<div class="pywry-chat-input-row">'
        + (
            # Attach button
            '<button id="pywry-chat-attach-btn" class="pywry-chat-attach-btn" data-tooltip="Attach file">'
            '<svg width="16" height="16" viewBox="0 0 16 16">'
            '<path d="M11.5 1.5a2.5 2.5 0 00-3.54 0L3.04 6.42a4 4 0 005.66 5.66l4.24-4.24-1.06-1.06-4.24 4.24a2.5 2.5 0 01-3.54-3.54l4.95-4.95a1 1 0 011.41 1.41L5.52 8.89a.5.5 0 00.7.7l4.25-4.24 1.06 1.06-4.24 4.24a2 2 0 01-2.83-2.83l4.95-4.95a2.5 2.5 0 013.54 3.54l-4.95 4.95a3.5 3.5 0 01-4.95-4.95L8.33 2.33" '
            'fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>'
            "</svg>"
            "</button>"
            if enable_file_attach
            else ""
        )
        + '<textarea id="pywry-chat-input" rows="1" placeholder="Ask a question..."></textarea>'
        '<button id="pywry-chat-send" class="pywry-chat-send-btn" data-tooltip="Send message">'
        '<svg width="16" height="16" viewBox="0 0 16 16">'
        '<path d="M1 8l6-6v4h7v4H7v4L1 8z" fill="currentColor"/>'
        "</svg>"
        "</button>"
        "</div>"
        "</div>"
        # Drop overlay
        + (
            '<div id="pywry-chat-drop-overlay" class="pywry-chat-drop-overlay">'
            '<div class="pywry-chat-drop-overlay-content">'
            '<svg width="32" height="32" viewBox="0 0 16 16">'
            '<path d="M11.5 1.5a2.5 2.5 0 00-3.54 0L3.04 6.42a4 4 0 005.66 5.66l4.24-4.24-1.06-1.06-4.24 4.24a2.5 2.5 0 01-3.54-3.54l4.95-4.95a1 1 0 011.41 1.41L5.52 8.89a.5.5 0 00.7.7l4.25-4.24 1.06 1.06-4.24 4.24a2 2 0 01-2.83-2.83l4.95-4.95a2.5 2.5 0 013.54 3.54l-4.95 4.95a3.5 3.5 0 01-4.95-4.95L8.33 2.33" '
            'fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>'
            "</svg>"
            "<span>Drop files to attach</span>"
            "</div>"
            "</div>"
            if enable_file_attach
            else ""
        )
        + "</div>"
    )
