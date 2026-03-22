# Chat Artifacts And Providers

PyWry chat handlers can emit more than plain text. `ChatManager` supports structured response objects for status updates, citations, tool call traces, thinking output, todo tracking, user input requests, and rich artifacts.

This page covers the advanced capabilities of the chat system, detailing how to render rich artifacts and integrate with various AI providers.

## Installation

The chat UI itself ships with the base package. Provider-backed integrations map directly to the adapter classes in `pywry.chat_providers`:

- `pip install 'pywry[openai]'` for `OpenAIProvider`
- `pip install 'pywry[anthropic]'` for `AnthropicProvider`
- `pip install 'pywry[magentic]'` for `MagenticProvider`
- `pip install 'pywry[all]'` for all optional integrations together

## Rich Chat Responses

Handlers may yield `ChatResponse` objects mixed with plain text chunks. Common response types include:

- `StatusResponse` for transient inline status messages
- `ThinkingResponse` for collapsible reasoning output
- `TodoUpdateResponse` for task list state
- `ToolCallResponse` and `ToolResultResponse` for agent/tool traces
- `CitationResponse` for source references
- `InputRequiredResponse` for interactive pauses

These can be mixed freely with regular text streaming.

```python
from pywry import StatusResponse, ThinkingResponse, ToolCallResponse, ToolResultResponse


def handler(messages, ctx):
    query = messages[-1]["text"]
    yield StatusResponse(text="Searching documentation...")
    yield ThinkingResponse(text="Selecting the most relevant modules first.\n")
    yield ToolCallResponse(name="search_docs", arguments={"query": query})
    yield ToolResultResponse(tool_id="call_123", result="Found 3 relevant modules")
    yield "Here is the synthesized answer."
```

## Artifact Types

Artifacts render as standalone blocks in the chat transcript and are not treated as token-by-token message content.

### CodeArtifact

Displays syntax-highlighted code.

```python
from pywry import CodeArtifact


yield CodeArtifact(
    title="main.py",
    language="python",
    content="print('hello from PyWry')",
)
```

### MarkdownArtifact

Renders Markdown as formatted content.

```python
from pywry import MarkdownArtifact


yield MarkdownArtifact(
    title="Summary",
    content="# Results\n\n- Build passed\n- 12 tests green",
)
```

### HtmlArtifact

Embeds raw HTML in a sandboxed container.

```python
from pywry import HtmlArtifact


yield HtmlArtifact(
    title="Status Card",
    content="<div style='padding:12px'><strong>Healthy</strong></div>",
)
```

### TableArtifact

Renders interactive AG Grid content inside the chat transcript. It accepts the same data shapes as `normalize_data()` in `pywry.grid`.

```python
from pywry import TableArtifact


yield TableArtifact(
    title="Positions",
    data=[
        {"symbol": "AAPL", "qty": 120, "price": 189.84},
        {"symbol": "MSFT", "qty": 80, "price": 425.22},
    ],
    height="320px",
)
```

### PlotlyArtifact

Embeds an interactive Plotly figure.

```python
from pywry import PlotlyArtifact


yield PlotlyArtifact(
    title="Revenue",
    figure={
        "data": [{"type": "scatter", "x": [1, 2, 3], "y": [3, 5, 8]}],
        "layout": {"title": {"text": "Revenue Trend"}},
        "config": {"responsive": True},
    },
    height="360px",
)
```

### ImageArtifact

Displays an image using an HTTP(S) URL or a data URI.

```python
from pywry import ImageArtifact


yield ImageArtifact(
    title="Diagram",
    url="https://example.com/diagram.png",
    alt="Architecture diagram",
)
```

### JsonArtifact

Displays structured JSON in a collapsible viewer.

```python
from pywry import JsonArtifact


yield JsonArtifact(
    title="API Response",
    data={"status": 200, "ok": True, "items": [1, 2, 3]},
)
```

## Asset Loading For Artifacts

`TableArtifact` and `PlotlyArtifact` need frontend libraries. `ChatManager` supports two strategies:

- Set `include_aggrid=True` and `include_plotly=True` in the constructor to preload those libraries.
- Leave them off and let the manager inject them lazily the first time the corresponding artifact type is emitted.

If you know the assistant will definitely emit tables or charts, eager loading avoids the first-render delay.

## Provider Layer

The lower-level provider system in `pywry.chat_providers` adapts external LLM clients to PyWry chat models.

Available providers:

- `OpenAIProvider`
- `AnthropicProvider`
- `CallbackProvider`
- `MagenticProvider`
- `get_provider(name, **kwargs)` factory

These providers operate on `ChatMessage` lists plus a `ChatConfig` object and return either a full `ChatMessage` or a stream of chunks.

## CallbackProvider

`CallbackProvider` is the lightest integration point if you already have your own Python callables and want a provider-shaped adapter.

```python
from pywry.chat import ChatConfig, ChatMessage
from pywry.chat_providers import CallbackProvider


def generate_fn(messages, config):
    return "Complete response"


def stream_fn(messages, config, cancel_event):
    for chunk in ["streamed ", "response"]:
        if cancel_event and cancel_event.is_set():
            return
        yield chunk


provider = CallbackProvider(generate_fn=generate_fn, stream_fn=stream_fn)
```

## OpenAI And Anthropic Providers

The OpenAI and Anthropic adapters lazily import their optional dependencies.

```python
from pywry.chat_providers import OpenAIProvider, AnthropicProvider


openai_provider = OpenAIProvider(api_key="...")
anthropic_provider = AnthropicProvider(api_key="...")
```

Both support:

- Full-message generation via `generate(...)`
- Streaming via `stream(...)`
- `ChatConfig` inputs for model, temperature, token limit, and system prompt
- Cooperative cancellation through `cancel_event`

## MagenticProvider

`MagenticProvider` wraps magentic `ChatModel` backends and gives you access to OpenAI-compatible providers, Anthropic, LiteLLM-backed models, and other magentic-supported engines through one adapter.

```python
from pywry.chat_providers import MagenticProvider


provider = MagenticProvider("gpt-4o-mini", api_key="...")
```

You can also pass a preconfigured magentic `ChatModel` instance directly.

## Provider Factory

Use `get_provider()` when you want a name-based configuration path.

```python
from pywry.chat_providers import get_provider


provider = get_provider("openai", api_key="...")
```

Supported names are `openai`, `anthropic`, `callback`, and `magentic`.

## Low-Level Chat Models

The provider layer uses these core types from `pywry.chat`:

- `ChatMessage`
- `ChatThread`
- `ChatConfig`
- `ChatWidgetConfig`
- `GenerationHandle`
- `GenerationCancelledError`

Use these directly if you are building a custom orchestration layer instead of `ChatManager`.

## Example Files

- `pywry/examples/pywry_demo_chat_artifacts.py` shows all seven artifact types.
- `pywry/examples/pywry_demo_chat.py` shows status, thinking, todo, slash commands, and input-required flows.

## Next Steps

- [Chat Guide](chat.md)
- [Chat API](../reference/chat.md)
- [ChatManager API](../reference/chat-manager.md)
- [Chat Providers API](../reference/chat-providers.md)
