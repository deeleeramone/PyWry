"""LLM provider adapters for PyWry chat.

Optional module — all provider imports are lazy so no hard
dependencies on openai/anthropic/magentic packages are introduced.
"""

from __future__ import annotations

import asyncio

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from .chat import ChatConfig, ChatMessage


class ChatProvider(ABC):
    """Abstract base class for chat completion providers.

    Provider implementations adapt third-party LLM clients to PyWry's chat
    protocol. They accept a list of :class:`pywry.chat.ChatMessage` objects
    plus a :class:`pywry.chat.ChatConfig`, and return either a complete
    assistant message or a stream of text chunks.
    """

    @abstractmethod
    async def generate(
        self,
        messages: list[ChatMessage],
        config: ChatConfig,
    ) -> ChatMessage:
        """Generate a complete assistant response.

        Parameters
        ----------
        messages : list[ChatMessage]
            Conversation history to send to the provider.
        config : ChatConfig
            Chat generation settings such as model, temperature, max tokens,
            and optional system prompt.

        Returns
        -------
        ChatMessage
            A fully materialized assistant message.

        Raises
        ------
        ImportError
            If the provider depends on an optional package that is not
            installed.
        Exception
            Implementations may raise provider-specific client or transport
            errors when generation fails.
        """

    @abstractmethod
    async def stream(
        self,
        messages: list[ChatMessage],
        config: ChatConfig,
        cancel_event: asyncio.Event | None = None,
    ) -> AsyncIterator[str]:
        """Stream assistant response chunks.

        Parameters
        ----------
        messages : list[ChatMessage]
            Conversation history to send to the provider.
        config : ChatConfig
            Chat generation settings such as model, temperature, max tokens,
            and optional system prompt.
        cancel_event : asyncio.Event | None, optional
            Cooperative cancellation signal checked between yielded chunks.

        Yields
        ------
        str
            Incremental text chunks from the provider.

        Raises
        ------
        GenerationCancelledError
            If ``cancel_event`` is set while streaming.
        ImportError
            If the provider depends on an optional package that is not
            installed.
        Exception
            Implementations may raise provider-specific client or transport
            errors when streaming fails.

        Implementations MUST check ``cancel_event.is_set()`` between
        chunks and raise ``GenerationCancelledError`` when set.
        """
        yield ""  # pragma: no cover


class OpenAIProvider(ChatProvider):
    """Provider backed by the ``openai`` async client.

    Parameters
    ----------
    **kwargs
        Keyword arguments forwarded to :class:`openai.AsyncOpenAI`, such as
        ``api_key``, ``base_url``, or client transport settings.

    Raises
    ------
    ImportError
        If the optional ``openai`` dependency is not installed.
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the OpenAI client wrapper.

        Parameters
        ----------
        **kwargs
            Keyword arguments forwarded to :class:`openai.AsyncOpenAI`.

        Raises
        ------
        ImportError
            If the optional ``openai`` dependency is not installed.
        """
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise ImportError(
                "OpenAIProvider requires the openai extra: pip install 'pywry[openai]'"
            ) from exc
        self._client = AsyncOpenAI(**kwargs)

    def _build_messages(
        self, messages: list[ChatMessage], config: ChatConfig
    ) -> list[dict[str, str]]:
        """Convert PyWry chat messages into OpenAI chat payloads.

        Parameters
        ----------
        messages : list[ChatMessage]
            Conversation history excluding the optional system prompt.
        config : ChatConfig
            Chat configuration containing the system prompt and generation
            settings.

        Returns
        -------
        list[dict[str, str]]
            OpenAI-compatible chat message dictionaries.
        """
        result: list[dict[str, str]] = []
        if config.system_prompt:
            result.append({"role": "system", "content": config.system_prompt})
        result.extend({"role": m.role, "content": m.text_content()} for m in messages)
        return result

    async def generate(
        self,
        messages: list[ChatMessage],
        config: ChatConfig,
    ) -> ChatMessage:
        """Generate a complete response via OpenAI.

        Parameters
        ----------
        messages : list[ChatMessage]
            Conversation history to submit to the OpenAI chat completions API.
        config : ChatConfig
            Generation settings including model, temperature, max tokens, and
            optional system prompt.

        Returns
        -------
        ChatMessage
            Assistant response with model and token usage metadata attached.

        Raises
        ------
        Exception
            Any client, API, or transport exception raised by the OpenAI SDK.
        """
        from .chat import ChatMessage as ChatMsg

        resp = await self._client.chat.completions.create(
            model=config.model,
            messages=self._build_messages(messages, config),  # type: ignore[arg-type]
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            stream=False,
        )
        choice = resp.choices[0]  # type: ignore[union-attr]
        return ChatMsg(
            role="assistant",
            content=choice.message.content or "",
            metadata={
                "model": resp.model,  # type: ignore[union-attr]
                "usage": {
                    "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,  # type: ignore[union-attr]
                    "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,  # type: ignore[union-attr]
                },
            },
        )

    async def stream(
        self,
        messages: list[ChatMessage],
        config: ChatConfig,
        cancel_event: asyncio.Event | None = None,
    ) -> AsyncIterator[str]:
        """Stream response chunks from OpenAI.

        Parameters
        ----------
        messages : list[ChatMessage]
            Conversation history to submit to the OpenAI chat completions API.
        config : ChatConfig
            Generation settings including model, temperature, max tokens, and
            optional system prompt.
        cancel_event : asyncio.Event | None, optional
            Cooperative cancellation signal checked between streamed chunks.

        Yields
        ------
        str
            Incremental response text chunks.

        Raises
        ------
        GenerationCancelledError
            If ``cancel_event`` is set while streaming.
        Exception
            Any client, API, or transport exception raised by the OpenAI SDK.
        """
        from .chat import GenerationCancelledError

        resp = await self._client.chat.completions.create(
            model=config.model,
            messages=self._build_messages(messages, config),  # type: ignore[arg-type]
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            stream=True,
        )

        try:
            async for chunk in resp:  # type: ignore[union-attr]
                if cancel_event and cancel_event.is_set():
                    raise GenerationCancelledError("Generation cancelled by user")
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield delta.content
        finally:
            await resp.response.aclose()  # type: ignore[union-attr]


class AnthropicProvider(ChatProvider):
    """Provider backed by the ``anthropic`` async client.

    Parameters
    ----------
    **kwargs
        Keyword arguments forwarded to :class:`anthropic.AsyncAnthropic`, such
        as ``api_key`` or transport settings.

    Raises
    ------
    ImportError
        If the optional ``anthropic`` dependency is not installed.
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the Anthropic client wrapper.

        Parameters
        ----------
        **kwargs
            Keyword arguments forwarded to :class:`anthropic.AsyncAnthropic`.

        Raises
        ------
        ImportError
            If the optional ``anthropic`` dependency is not installed.
        """
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:
            raise ImportError(
                "AnthropicProvider requires the anthropic extra: pip install 'pywry[anthropic]'"
            ) from exc
        self._client = AsyncAnthropic(**kwargs)

    def _build_messages(
        self,
        messages: list[ChatMessage],
    ) -> list[dict[str, str]]:
        """Convert PyWry chat messages into Anthropic message payloads.

        Parameters
        ----------
        messages : list[ChatMessage]
            Conversation history to transform.

        Returns
        -------
        list[dict[str, str]]
            Anthropic-compatible message dictionaries.
        """
        return [{"role": m.role, "content": m.text_content()} for m in messages]

    async def generate(
        self,
        messages: list[ChatMessage],
        config: ChatConfig,
    ) -> ChatMessage:
        """Generate a complete response via Anthropic.

        Parameters
        ----------
        messages : list[ChatMessage]
            Conversation history to submit to the Anthropic messages API.
        config : ChatConfig
            Generation settings including model, temperature, max tokens, and
            optional system prompt.

        Returns
        -------
        ChatMessage
            Assistant response with model and token usage metadata attached.

        Raises
        ------
        Exception
            Any client, API, or transport exception raised by the Anthropic
            SDK.
        """
        from .chat import ChatMessage as ChatMsg

        resp = await self._client.messages.create(
            model=config.model,
            messages=self._build_messages(messages),
            system=config.system_prompt or "",
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            stream=False,
        )
        text = resp.content[0].text if resp.content else ""
        return ChatMsg(
            role="assistant",
            content=text,
            metadata={
                "model": resp.model,
                "usage": {
                    "input_tokens": resp.usage.input_tokens if resp.usage else 0,
                    "output_tokens": resp.usage.output_tokens if resp.usage else 0,
                },
            },
        )

    async def stream(
        self,
        messages: list[ChatMessage],
        config: ChatConfig,
        cancel_event: asyncio.Event | None = None,
    ) -> AsyncIterator[str]:
        """Stream response chunks from Anthropic.

        Parameters
        ----------
        messages : list[ChatMessage]
            Conversation history to submit to the Anthropic messages API.
        config : ChatConfig
            Generation settings including model, temperature, max tokens, and
            optional system prompt.
        cancel_event : asyncio.Event | None, optional
            Cooperative cancellation signal checked between streamed chunks.

        Yields
        ------
        str
            Incremental response text chunks.

        Raises
        ------
        GenerationCancelledError
            If ``cancel_event`` is set while streaming.
        Exception
            Any client, API, or transport exception raised by the Anthropic
            SDK.
        """
        from .chat import GenerationCancelledError

        async with self._client.messages.stream(
            model=config.model,
            messages=self._build_messages(messages),
            system=config.system_prompt or "",
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        ) as stream:
            async for text in stream.text_stream:
                if cancel_event and cancel_event.is_set():
                    raise GenerationCancelledError("Generation cancelled by user")
                yield text


class CallbackProvider(ChatProvider):
    """Provider backed by user-supplied Python callables.

    Parameters
    ----------
    generate_fn : Any, optional
        Callable used for one-shot generation. It may be synchronous or async
        and should return either a string or a :class:`pywry.chat.ChatMessage`.
    stream_fn : Any, optional
        Callable used for streaming generation. It may return a synchronous or
        async iterator of text chunks.
    """

    def __init__(
        self,
        generate_fn: Any = None,
        stream_fn: Any = None,
    ) -> None:
        """Initialize a callback-based provider.

        Parameters
        ----------
        generate_fn : Any, optional
            Callable used for one-shot generation.
        stream_fn : Any, optional
            Callable used for streaming generation.
        """
        self._generate_fn = generate_fn
        self._stream_fn = stream_fn

    async def generate(
        self,
        messages: list[ChatMessage],
        config: ChatConfig,
    ) -> ChatMessage:
        """Generate a complete response via the callback.

        Parameters
        ----------
        messages : list[ChatMessage]
            Conversation history passed to ``generate_fn``.
        config : ChatConfig
            Generation settings passed to ``generate_fn``.

        Returns
        -------
        ChatMessage
            Assistant response returned by the callback, or a fallback message
            if no callback is configured.
        """
        from .chat import ChatMessage as ChatMsg

        if not self._generate_fn:
            return ChatMsg(role="assistant", content="No generate callback configured.")

        result = self._generate_fn(messages, config)
        if asyncio.iscoroutine(result):
            result = await result

        if isinstance(result, str):
            return ChatMsg(role="assistant", content=result)
        return result  # type: ignore[no-any-return]

    async def stream(
        self,
        messages: list[ChatMessage],
        config: ChatConfig,
        cancel_event: asyncio.Event | None = None,
    ) -> AsyncIterator[str]:
        """Stream response chunks via the callback.

        Parameters
        ----------
        messages : list[ChatMessage]
            Conversation history passed to ``stream_fn``.
        config : ChatConfig
            Generation settings passed to ``stream_fn``.
        cancel_event : asyncio.Event | None, optional
            Cooperative cancellation signal checked between streamed chunks.

        Yields
        ------
        str
            Incremental response text chunks from the callback.

        Raises
        ------
        GenerationCancelledError
            If ``cancel_event`` is set while streaming.
        """
        from .chat import GenerationCancelledError

        if not self._stream_fn:
            yield "No stream callback configured."
            return

        result = self._stream_fn(messages, config, cancel_event)
        if hasattr(result, "__aiter__"):
            async for chunk in result:
                if cancel_event and cancel_event.is_set():
                    raise GenerationCancelledError("Generation cancelled by user")
                yield chunk
        else:
            # Synchronous generator
            for chunk in result:
                if cancel_event and cancel_event.is_set():
                    raise GenerationCancelledError("Generation cancelled by user")
                yield chunk


class MagenticProvider(ChatProvider):
    """Wraps any `magentic <https://magentic.dev>`_ ``ChatModel`` backend.

    This enables plug-and-play access to every LLM backend that magentic
    supports — OpenAI, Anthropic, LiteLLM (100+ providers), Mistral,
    and any OpenAI-compatible API (Ollama, Azure, Gemini, xAI, etc.).

    Parameters
    ----------
    model : ChatModel | str
        A pre-configured magentic ``ChatModel`` instance, **or** a model
        name string (which creates an ``OpenaiChatModel``).
    **kwargs
        Extra keyword arguments forwarded to ``OpenaiChatModel`` when
        *model* is a string (e.g. ``base_url``, ``api_key``).
    """

    def __init__(self, model: Any, **kwargs: Any) -> None:
        try:
            from magentic.chat_model.base import ChatModel
        except ImportError as exc:
            raise ImportError(
                "MagenticProvider requires the magentic extra: pip install 'pywry[magentic]'"
            ) from exc

        if isinstance(model, str):
            from magentic import OpenaiChatModel

            model = OpenaiChatModel(model, **kwargs)
        elif not isinstance(model, ChatModel):
            raise TypeError(
                f"Expected a magentic ChatModel or model name string, got {type(model).__name__}"
            )
        self._model = model

    def _build_messages(
        self,
        messages: list[ChatMessage],
        config: ChatConfig,
    ) -> list[Any]:
        """Convert PyWry messages to magentic message objects.

        Parameters
        ----------
        messages : list[ChatMessage]
            Conversation history to transform.
        config : ChatConfig
            Chat configuration containing the optional system prompt.

        Returns
        -------
        list[Any]
            magentic message objects appropriate for the configured backend.
        """
        from magentic import AssistantMessage, SystemMessage, UserMessage

        result: list[Any] = []
        if config.system_prompt:
            result.append(SystemMessage(config.system_prompt))
        for m in messages:
            text = m.text_content()
            if m.role == "system":
                result.append(SystemMessage(text))
            elif m.role == "assistant":
                result.append(AssistantMessage(text))
            else:
                result.append(UserMessage(text))
        return result

    async def generate(
        self,
        messages: list[ChatMessage],
        config: ChatConfig,
    ) -> ChatMessage:
        """Generate a complete response via magentic.

        Parameters
        ----------
        messages : list[ChatMessage]
            Conversation history to submit to the magentic chat model.
        config : ChatConfig
            Generation settings including model metadata and optional system
            prompt.

        Returns
        -------
        ChatMessage
            Assistant response generated by the magentic model.

        Raises
        ------
        TypeError
            If the configured magentic model returns a content object that
            cannot be converted to text as expected by the caller.
        Exception
            Any backend-specific exception raised while executing the model.
        """
        from .chat import ChatMessage as ChatMsg

        try:
            from magentic import Chat
        except ImportError:  # pragma: no cover
            return ChatMsg(role="assistant", content="magentic is not installed.")

        chat = Chat(
            messages=self._build_messages(messages, config),
            model=self._model,
        )
        chat = await chat.asubmit()
        content = chat.last_message.content
        if not isinstance(content, str):
            content = str(content)
        return ChatMsg(role="assistant", content=content)

    async def stream(
        self,
        messages: list[ChatMessage],
        config: ChatConfig,
        cancel_event: asyncio.Event | None = None,
    ) -> AsyncIterator[str]:
        """Stream response chunks from magentic.

        Parameters
        ----------
        messages : list[ChatMessage]
            Conversation history to submit to the magentic chat model.
        config : ChatConfig
            Generation settings including model metadata and optional system
            prompt.
        cancel_event : asyncio.Event | None, optional
            Cooperative cancellation signal checked between streamed chunks.

        Yields
        ------
        str
            Incremental response text chunks.

        Raises
        ------
        GenerationCancelledError
            If ``cancel_event`` is set while streaming.
        Exception
            Any backend-specific exception raised while executing the model.
        """
        from .chat import GenerationCancelledError

        try:
            from magentic import Chat
            from magentic.streaming import AsyncStreamedStr
        except ImportError:  # pragma: no cover
            yield "magentic is not installed."
            return

        chat = Chat(
            messages=self._build_messages(messages, config),
            model=self._model,
            output_types=[AsyncStreamedStr],
        )
        chat = await chat.asubmit()
        async for chunk in chat.last_message.content:
            if cancel_event and cancel_event.is_set():
                raise GenerationCancelledError("Generation cancelled by user")
            yield chunk


_PROVIDERS: dict[str, type[ChatProvider]] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "callback": CallbackProvider,
    "magentic": MagenticProvider,
}


def get_provider(name: str, **kwargs: Any) -> ChatProvider:
    """Create a provider instance by name.

    Parameters
    ----------
    name : str
        Provider name. Supported values are ``openai``, ``anthropic``,
        ``callback``, and ``magentic``.
    **kwargs
        Passed to the provider constructor.

    Returns
    -------
    ChatProvider
        Instantiated provider.

    Raises
    ------
    ValueError
        If provider name is unknown.
    """
    cls = _PROVIDERS.get(name)
    if not cls:
        raise ValueError(f"Unknown provider: {name!r}. Available: {', '.join(_PROVIDERS)}")
    return cls(**kwargs)
