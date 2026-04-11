# Components

PyWry's component system covers everything that gets rendered in the window — from
the HTML content itself, to toolbars, modals, toasts, chat, and theming.

## What's in this section

[HtmlContent](htmlcontent/index.md)
:   The Pydantic model that describes what to render. Controls HTML, CSS files,
    JS files, JSON data injection, init scripts, and hot reload.

[Toolbar](toolbar/index.md)
:   18 declarative Pydantic components (buttons, selects, inputs, toggles, etc.)
    grouped into `Toolbar` containers and placed at 7 positions around the content area.

[Modal](modal/index.md)
:   Popup dialogs that overlay the content. Reuse the same toolbar components
    with added overlay, sizing, and keyboard handling.

[Toasts](toasts/index.md)
:   Non-blocking in-window notifications (info, success, warning, error, confirm)
    with auto-dismiss and event-based control.

[Chat](chat/index.md)
:   Built-in chat UI with `ChatManager` for thread management, streaming,
    slash commands, and provider integration.

[Theming & CSS](theming.md)
:   Light/dark modes, 60+ CSS custom properties, system detection, and custom
    CSS overrides.
