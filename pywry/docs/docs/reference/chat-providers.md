# pywry.chat_providers

LLM provider adapters for PyWry chat.

These classes expose a common interface over optional provider SDKs and user-defined callables. They operate on `ChatMessage` histories and `ChatConfig` settings from `pywry.chat`.

---

## Base Provider

::: pywry.chat_providers.ChatProvider
    options:
      show_root_heading: true
      heading_level: 2
      members: true

---

## Provider Implementations

::: pywry.chat_providers.OpenAIProvider
    options:
      show_root_heading: true
      heading_level: 2
      members: true

::: pywry.chat_providers.AnthropicProvider
    options:
      show_root_heading: true
      heading_level: 2
      members: true

::: pywry.chat_providers.CallbackProvider
    options:
      show_root_heading: true
      heading_level: 2
      members: true

::: pywry.chat_providers.MagenticProvider
    options:
      show_root_heading: true
      heading_level: 2
      members: true

---

## Factory

::: pywry.chat_providers.get_provider
    options:
      show_root_heading: true
      heading_level: 2
