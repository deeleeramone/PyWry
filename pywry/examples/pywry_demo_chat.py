"""PyWry Chat Demo — minimal usage with ChatManager.

Demonstrates how little code is needed to wire up a chat component:
  - ChatManager handles ALL event wiring, threading, state management
  - Developer provides a handler function — that's it
  - Settings, slash commands, and welcome message are declarative

Compare this to the raw event-callback approach — ChatManager reduces
hundreds of lines of boilerplate to a single handler function.

Run::

    python pywry_demo_chat.py
"""

from __future__ import annotations

import random
import time

from pywry import Button, Div, HtmlContent, PyWry, Toolbar
from pywry.chat_manager import (
    ChatManager,
    InputRequiredResponse,
    SettingsItem,
    SlashCommandDef,
    ThinkingResponse,
    TodoItem,
    TodoUpdateResponse,
)


# ---------------------------------------------------------------------------
# Handler — the ONLY thing the developer writes
# ---------------------------------------------------------------------------

RESPONSES = [
    "That's a great question! Let me think about it...\n\n"
    "After careful consideration, the answer involves **several factors**:\n\n"
    "1. The context of the situation\n"
    "2. The underlying assumptions\n"
    "3. A bit of creative thinking\n\n"
    "Hope that helps!",
    "Interesting! Here's what I know:\n\n"
    "```python\ndef hello(name):\n    return f'Hello, {name}!'\n\n"
    "print(hello('World'))\n```\n\n"
    "A simple Python greeting function.",
    "Let me break this down:\n\n"
    "**Step 1:** Understand the problem\n"
    "**Step 2:** Gather information\n"
    "**Step 3:** Analyze and conclude\n\n"
    "Each step builds on the previous one.",
]

JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs!",
    "There are only 10 types of people: those who understand binary and those who don't.",
    "A SQL query walks into a bar, sees two tables, and asks... 'Can I JOIN you?'",
]


def _handle_confirm(ctx):
    """Handle confirm/approve input flow."""
    yield "I'd like to proceed, but I need your confirmation first."
    yield InputRequiredResponse(
        prompt="Do you approve this action?",
        input_type="buttons",
    )
    answer = ctx.wait_for_input()
    if not answer or answer.lower().startswith("n"):
        yield "\n\nOk, action **cancelled**."
        return
    yield "\n\nGreat — confirmed! Proceeding with the action.\n\n"
    yield "Done! The operation completed successfully."


def _handle_choose(ctx):
    """Handle choose/pick/select input flow."""
    yield "Let me know which option you'd like:"
    yield InputRequiredResponse(
        prompt="Select a model:",
        input_type="radio",
        options=["GPT-4o", "Claude Sonnet", "Gemini Pro", "Llama 3"],
    )
    choice = ctx.wait_for_input()
    if not choice:
        yield "\n\nSelection cancelled."
        return
    yield f"\n\nYou selected **{choice}**. Switching to that model now.\n\n"
    yield f"Now using {choice} for all subsequent responses."


def _handle_filename(ctx):
    """Handle filename/input/path input flow."""
    yield "I need a bit more information to continue."
    yield InputRequiredResponse(
        prompt="Which file should I modify?",
        placeholder="Enter filename or path...",
    )
    filename = ctx.wait_for_input()
    if not filename:
        yield "\n\nNo file specified — aborting."
        return
    yield f"\n\nModifying **{filename}**...\n\n"
    yield "Done! Changes applied successfully."


def my_handler(messages, ctx):
    """Handle a user message by streaming a fake LLM response.

    This is where you'd call your real LLM API.  The ChatManager handles
    everything else — threading, cancellation, UI events, etc.
    """
    user_text = messages[-1]["text"].lower()

    # If the user mentions "confirm" or "approve", demonstrate buttons input
    if any(word in user_text for word in ("confirm", "approve", "permission")):
        yield from _handle_confirm(ctx)
        return

    # If the user mentions "choose" or "pick", demonstrate radio input
    if any(word in user_text for word in ("choose", "pick", "select", "model")):
        yield from _handle_choose(ctx)
        return

    # If the user mentions "filename" or "input", demonstrate text input
    if any(word in user_text for word in ("filename", "input", "path", "file")):
        yield from _handle_filename(ctx)
        return

    # Push todo list — agent tracks its own progress
    yield TodoUpdateResponse(
        items=[
            TodoItem(id=1, title="Analyze user request", status="in-progress"),
            TodoItem(id=2, title="Generate response", status="not-started"),
            TodoItem(id=3, title="Stream to user", status="not-started"),
        ]
    )

    # Stream thinking tokens — visible but NOT stored in history
    thinking_text = (
        "Let me analyze this request...\n"
        "The user asked: " + messages[-1]["text"] + "\n"
        "I need to consider several approaches.\n"
        "Evaluating option A: direct response with examples.\n"
        "Evaluating option B: step-by-step breakdown.\n"
        "Option A seems most appropriate here."
    )
    for line in thinking_text.split("\n"):
        if ctx.cancel_event.is_set():
            return
        yield ThinkingResponse(text=line + "\n")
        time.sleep(random.uniform(0.05, 0.15))

    # Update progress
    yield TodoUpdateResponse(
        items=[
            TodoItem(id=1, title="Analyze user request", status="completed"),
            TodoItem(id=2, title="Generate response", status="in-progress"),
            TodoItem(id=3, title="Stream to user", status="not-started"),
        ]
    )
    time.sleep(0.2)

    yield TodoUpdateResponse(
        items=[
            TodoItem(id=1, title="Analyze user request", status="completed"),
            TodoItem(id=2, title="Generate response", status="completed"),
            TodoItem(id=3, title="Stream to user", status="in-progress"),
        ]
    )

    response = random.choice(RESPONSES)
    words = response.split(" ")

    for i, word in enumerate(words):
        if ctx.cancel_event.is_set():
            return
        yield word + (" " if i < len(words) - 1 else "")
        time.sleep(random.uniform(0.02, 0.08))

    # All done
    yield TodoUpdateResponse(
        items=[
            TodoItem(id=1, title="Analyze user request", status="completed"),
            TodoItem(id=2, title="Generate response", status="completed"),
            TodoItem(id=3, title="Stream to user", status="completed"),
        ]
    )


def on_slash(command, args, thread_id):
    """Handle custom slash commands."""
    if command == "/joke":
        chat.send_message(random.choice(JOKES), thread_id)
    elif command == "/time":
        chat.send_message(f"Current time: **{time.strftime('%H:%M:%S')}**", thread_id)
    elif command == "/confirm":
        # Demonstrate InputRequiredResponse via a programmatic handler call
        import threading

        def _confirm_flow():
            time.sleep(0.1)
            chat.send_message(
                "Try sending a message — the handler will ask for confirmation "
                "mid-stream using `InputRequiredResponse`.",
                thread_id,
            )

        threading.Thread(target=_confirm_flow, daemon=True).start()


# ---------------------------------------------------------------------------
# ChatManager — declarative configuration
# ---------------------------------------------------------------------------

chat = ChatManager(
    handler=my_handler,
    welcome_message=(
        "Welcome to **PyWry Chat**!\n\n"
        "Try typing a message, `/joke`, `/time`, `/confirm`, or `/clear`.\n"
        "Say **confirm** for Yes/No buttons, **choose** for radio select, "
        "or **filename** for text input.\n"
        "Click **Stop** mid-stream to cancel generation."
    ),
    system_prompt="You are a helpful assistant.",
    model="gpt-4",
    temperature=0.7,
    slash_commands=[
        SlashCommandDef(name="/joke", description="Tell a programming joke"),
        SlashCommandDef(name="/time", description="Show current time"),
        SlashCommandDef(name="/confirm", description="Demonstrate input_required flow"),
    ],
    on_slash_command=on_slash,
    settings=[
        SettingsItem(
            id="model",
            label="Model",
            type="select",
            value="gpt-4",
            options=["gpt-4", "gpt-3.5-turbo", "claude-3"],
        ),
        SettingsItem(
            id="temperature", label="Temperature", type="range", value=0.7, min=0, max=2, step=0.1
        ),
        SettingsItem(id="stream", label="Stream responses", type="toggle", value=True),
        SettingsItem(id="sep1", type="separator"),
        SettingsItem(id="clear-history", label="Clear History", type="action"),
    ],
    toolbar_width="380px",
)


# ---------------------------------------------------------------------------
# Main page content — composed with PyWry Div components
# ---------------------------------------------------------------------------

FEATURES = [
    "Event wiring (all <code>chat:*</code> events)",
    "Background threading + cooperative cancellation",
    "Thread CRUD (create, switch, delete, rename)",
    "Streaming token-by-token from your handler",
    "Settings dropdown management",
    "Slash command registration",
    "Welcome message + state restoration",
]

main_content = Div(
    event="app:main",
    style=("padding: 24px; font-family: var(--pywry-font-family); overflow-y: auto; height: 100%;"),
    children=[
        Div(
            event="app:header",
            content=(
                '<h1 style="margin: 0 0 16px; color: var(--pywry-text-primary);">'
                "PyWry Chat Demo</h1>"
                '<p style="color: var(--pywry-text-secondary); margin: 0 0 16px;'
                ' line-height: 1.6;">'
                "The chat panel is in the <strong>collapsible right toolbar</strong>."
                " It uses <code>ChatManager</code> — zero boilerplate."
                "</p>"
            ),
        ),
        Div(
            event="app:features",
            style=(
                "background: var(--pywry-bg-tertiary);"
                " border: 1px solid var(--pywry-border-color);"
                " border-radius: 8px; padding: 16px;"
            ),
            content=(
                '<h3 style="margin: 0 0 8px; font-size: 14px;'
                ' color: var(--pywry-text-primary);">'
                "What ChatManager handles for you:</h3>"
                '<ul style="margin: 0; padding-left: 20px;'
                ' color: var(--pywry-text-secondary); line-height: 1.8;">'
                + "".join(f"<li>{f}</li>" for f in FEATURES)
                + "</ul>"
            ),
        ),
    ],
)

app = PyWry(title="Chat Demo", width=1100, height=700)
content = HtmlContent(html=main_content.build_html())

top_toolbar = Toolbar(
    position="top",
    items=[
        Button(label="Clear Chat", event="app:clear-chat", variant="secondary"),
    ],
)


def on_clear_chat(_data, _event_type, _label):
    """Top toolbar clear button."""
    chat._emit("chat:clear", {})
    chat._threads[chat.active_thread_id] = []


widget = app.show(
    content,
    toolbars=[top_toolbar, chat.toolbar()],
    callbacks={
        **chat.callbacks(),
        "app:clear-chat": on_clear_chat,
    },
)
chat.bind(widget)
app.block()
