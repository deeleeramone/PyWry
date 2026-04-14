# pywry.chat.providers

ACP-conformant provider adapters for PyWry chat.

These classes implement the ACP session lifecycle (`initialize`, `new_session`, `prompt`, `cancel`) over optional provider SDKs and user-defined callables. They operate on `ContentBlock` lists from `pywry.chat.models` and yield `SessionUpdate` notifications from `pywry.chat.updates`.

---

## Base Provider

::: pywry.chat.providers.ChatProvider
    options:
      show_root_heading: true
      heading_level: 2
      members: true

---

## Provider Implementations

::: pywry.chat.providers.openai.OpenAIProvider
    options:
      show_root_heading: true
      heading_level: 2
      members: true

::: pywry.chat.providers.anthropic.AnthropicProvider
    options:
      show_root_heading: true
      heading_level: 2
      members: true

::: pywry.chat.providers.callback.CallbackProvider
    options:
      show_root_heading: true
      heading_level: 2
      members: true

::: pywry.chat.providers.magentic.MagenticProvider
    options:
      show_root_heading: true
      heading_level: 2
      members: true

::: pywry.chat.providers.stdio.StdioProvider
    options:
      show_root_heading: true
      heading_level: 2
      members: true

---

## Factory

::: pywry.chat.providers.get_provider
    options:
      show_root_heading: true
      heading_level: 2
