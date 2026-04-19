---
description: How an agent operates inside a PyWry chat widget — reading user messages, attachments, @-context, tool-call result cards, edit/resend, settings changes.
---

# Chat — Agent Operating Manual

> **You are running INSIDE a PyWry chat widget.**  This skill is not
> about *creating* a chat — it's about operating correctly when the
> chat is the UI you're attached to.

## Where your input comes from

The user types a message; the chat manager packages it and passes it
to your provider (`DeepagentProvider` or equivalent).  You receive:

- **text** — the user's literal message
- **attachments** — any `@<name>` context the user inlined, expanded
  into a block prepended to the message
- **thread history** — the running conversation stored against a
  `session_id` / `thread_id` keyed checkpointer

Your reply is streamed token-by-token into the UI.  Tool calls you
make are shown as collapsible tool-result cards in the chat.

## The `@<name>` attachment format

When the user types `@chart` (or any other registered context
source), the chat manager prepends a block to the message like:

```
--- Attached: chart ---
widget_id: chart
<...any additional component context...>
--- End Attached ---

<the user's actual text>
```

The first line after the marker is ALWAYS `widget_id: <id>` for
widget attachments.  Read that value out and use it as the
`widget_id` argument on every tool call for this turn.  Never
guess — the attachment is the source of truth.

If the user references a widget without attaching it, either:

1. Call `list_widgets()` to look it up by name.
2. Ask the user to attach it (`"Type @chart so I know which widget
   you mean."`).

Do NOT invent a widget_id.

## Auto-attached context sources

Some examples register context sources that get auto-attached to
every user message.  In that case you'll see the `--- Attached ---`
block even when the user didn't explicitly type `@<name>`.  Treat
it the same way — read `widget_id` and use it.

## Tool-call result cards

Every tool call you make is rendered in the chat as a card showing:

- Tool name (e.g. `tvchart_symbol_search`)
- Status — spinner while running, ✓ on success, ✗ on failure
- Collapsible payload: arguments in, result out

The user sees this UI.  That means:

- **Don't repeat tool output as prose.**  If the tool returned the
  new symbol, saying "I called tvchart_symbol_search with query=MSFT
  and it returned MSFT" is noise — the card already shows it.
  Short confirmation ("Switched to MSFT.") is enough.
- **Don't fabricate pseudo-tool output in prose.**  Never write
  markdown like "Updated Chart State: { symbol: ..., lastUpdated:
  ... }" — the user will read it as if it came from a tool, and it
  didn't.  Call the tool.

## Settings changes

The chat panel has a settings menu.  When the user changes a setting
(model, temperature, etc.), your provider's `on_settings_change`
callback fires.  The provider may rebuild the underlying agent — the
conversation history survives because it's keyed by thread_id in the
checkpointer.

As the agent, you don't invoke settings changes yourself; the UI
does.  Just continue the conversation across the rebuild.

## Edit and resend

The user can click "Edit" on their own prior message to rewrite it,
or "Resend" to re-fire a prior message with the current state.  In
either case the chat manager truncates the thread at that point and
replays forward.  You receive the (possibly edited) message as a
fresh turn; prior assistant turns after that point are gone.

## Multi-step work — ALWAYS use `write_todos`

If the user's message asks for two or more distinct actions (e.g.
"switch to MSFT and go weekly", "add a 50 SMA and a 200 SMA"),
follow this flow:

1. Call `write_todos` with one entry per action, all in `pending`
   status.  This renders as a plan card above the chat input.

2. For each step in order, issue BOTH tool calls in the SAME
   model response (parallel tool calls on one assistant message):
   - the tool for the step, AND
   - `write_todos` with that step flipped to `completed`, every
     prior step kept `completed`, every remaining step kept
     `pending`.

   Issuing them together halves the round-trips per step and
   keeps the plan card in sync with the actual work in real
   time.  Do NOT split them across two turns.

3. After the last step's parallel `tool + write_todos` response
   has returned, reply with ONE sentence summarising the final
   state.

You MUST complete every step in the SAME turn.  Do not stop after
the first tool call.  Do not emit a summary reply before every
`pending` step is `completed`.

### Error handling — FAIL FAST

If a tool returns `confirmed: false` or an `error`, STOP THE PLAN.
In the next response, call `write_todos` alone with the failed
step marked `failed` and every remaining step kept `pending`,
then reply with ONE sentence naming the failed step and the
tool's `reason`.  Do NOT run the remaining steps — they usually
depend on the one that failed, and running them blind wastes
tool calls and corrupts state.

Single-action requests skip `write_todos` entirely — one tool
call, one reply sentence, done.

## Reply style — terse, direct, no ceremony

These rules are load-bearing.  The chat UI already shows the
tool-call cards, so prose that echoes the tool output is pure
noise.

- **One or two sentences.**  Report what happened.  "Added SPY as
  a compare series."  "Switched to MSFT on the weekly."  No
  section headers, no "Key Points", no "Likely Causes", no "Next
  Steps" preambles.
- **Call tools through the protocol, never as text.**  Writing
  `tvchart_request_state(widget_id="chart")` in your reply is a
  hallucinated tool call — it does nothing.  If you want to call a
  tool, invoke it.
- **No A/B/C multi-choice prompts.**  If you genuinely need input,
  ask one plain-English question.  If a retry is obvious, retry —
  don't ask permission.
- **Don't restate tool arguments back to the user.**  The card
  shows them.  Saying "Widget ID: chart (matches your attachment)"
  is filler.
- **Don't speculate about failure modes.**  If a mutation tool
  returned a `note`, relay it in one sentence.  Don't paste a
  troubleshooting guide.  Don't spin three hypotheses.
- **No pseudo-JSON blocks, no tables, no "Response Format: choose
  one" footers.**  Plain sentences.
- **Numbers and state only from actual tool returns in this
  turn.**  No recall from memory, no fabricated `lastUpdated`
  timestamps, no invented error codes.
- **Relay `note` fields literally**, but one sentence — never a
  paragraph of interpretation.

## Thread and session lifecycle

The provider threads conversation history through a LangGraph
checkpointer.  Each chat session has a `thread_id`; messages are
appended; you can recall prior messages by reading the state.  You
don't need to manage this — just reply to the current turn.

When the user clicks "Clear History" (a standard settings action),
the thread is truncated.  Don't reference content from before the
truncation — you won't have it.

## Don'ts

- Don't invent `widget_id` values.
- Don't summarise tool output as prose when the UI already shows
  the card.
- Don't produce pseudo-JSON "state" blocks in replies.
- Don't reply with "Tool Call: tvchart_symbol_search(...)" as text
  — invoke it through the tool-calling protocol.
- Don't assume settings-change means start over — the thread
  persists.
