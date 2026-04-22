# Chat Stylesheet

Source: `frontend/style/chat.css` — Styles for the `show_chat()` / `ChatManager` component, including messages, threads, tool calls, artifacts, and syntax highlighting.

---

## Layout

```css
.pywry-chat { /* Chat container — full height flex column */ }
.pywry-chat-header { /* Header bar with title and actions */ }
.pywry-chat-header-left { /* Left header content (title, conversation picker) */ }
.pywry-chat-header-actions { /* Right header actions (settings, fullscreen) */ }
.pywry-chat-header-btn { /* Header button */ }
.pywry-chat-messages { /* Messages scroll area */ }
.pywry-chat-input-bar { /* Input bar at bottom */ }
.pywry-chat-input-row { /* Input row (textarea + send button) */ }
#pywry-chat-input { /* Chat textarea input (ID selector — one per widget) */ }
.pywry-chat-send-btn { /* Send button */ }
.pywry-chat-send-btn.pywry-chat-stop { /* Stop button (red, shown during streaming) */ }
.pywry-chat-fullscreen { /* Fullscreen state — expands to fill viewport */ }
.pywry-chat-fullscreen-expand { /* Expand icon */ }
.pywry-chat-fullscreen-collapse { /* Collapse icon */ }
```

---

## Messages

```css
.pywry-chat-msg { /* Message container — full-width VS Code style */ }
.pywry-chat-msg-user { /* User message */ }
.pywry-chat-msg-assistant { /* Assistant message */ }
.pywry-chat-msg-system { /* System message */ }
.pywry-chat-msg-role { /* Role label (User, Assistant, System) */ }
.pywry-chat-msg-role-icon { /* Role icon next to label */ }
.pywry-chat-msg-content { /* Message content area */ }
.pywry-chat-msg-content.streaming { /* Streaming animation cursor */ }
.pywry-chat-stopped { /* Stopped indicator */ }
.pywry-chat-typing { /* Typing indicator with animated dots */ }
.pywry-chat-expand { /* Expand/collapse button for long messages */ }
.pywry-chat-new-msg-badge { /* "New messages" badge at bottom of scroll */ }
```

Every message bubble carries `data-msg-id="msg_..."`, which the edit/
resend UI uses to address messages on both sides of the bridge.

### Edit / Resend actions

Each user message gets **Edit** and **Resend** buttons.  Assistant
messages (including the welcome bubble) have no action buttons —
rerun happens from the user's own prior message, not from the
assistant's reply.  Both buttons tie into the `chat:edit-message` /
`chat:resend-from` events.  Actions fade in on hover and stay
visible during edit mode.

```css
.pywry-chat-msg-actions { /* Flex toolbar at bottom of each user bubble.
                            opacity: 0 by default. */ }
.pywry-chat-msg:hover .pywry-chat-msg-actions,
.pywry-chat-msg-editing .pywry-chat-msg-actions {
    /* Visible on hover or while editing. */
}
.pywry-chat-msg-action { /* Individual action button (Edit / Resend /
                           Save & Resend / Cancel). */ }
.pywry-chat-msg-action:hover { /* Hover state. */ }
.pywry-chat-msg-action svg { /* Icon inside action buttons. */ }

.pywry-chat-msg-editing { /* Applied to the message bubble while its
                            textarea is open.  Keeps actions pinned
                            visible. */ }
.pywry-chat-msg-edit-textarea { /* The inline editor swapped in for
                                   the message content during edit. */ }
```

Button semantics (by `data-action` attribute):

| Button | `data-action` | Effect |
|--------|---------------|--------|
| **Edit** | `edit` | Swap the message content for `<textarea.pywry-chat-msg-edit-textarea>` and show Save/Cancel. |
| **Resend** | `resend` | Emit `chat:resend-from` with this message's id.  Backend truncates the thread to this message and re-runs. |
| **Save & Resend** (edit mode) | `save` (`data-edit-action`) | Emit `chat:edit-message` with new text. |
| **Cancel** (edit mode) | `cancel` (`data-edit-action`) | Restore the original rendered markdown, discard the textarea. |

Tooltips on these buttons use PyWry's shared tooltip manager (the
globally injected `#pywry-tooltip` element, styled by `.pywry-tooltip`)
via the `data-tooltip="..."` attribute — not the native browser
`title=` popup.  Hover delay, arrow positioning, and light/dark theme
colors come from the shared CSS in `frontend/style/pywry.css`.

---

## Threads & Conversation Picker

```css
.pywry-chat-conv-picker { /* Conversation picker dropdown */ }
.pywry-chat-conv-picker.open { /* Open state */ }
.pywry-chat-conv-btn { /* Picker trigger button */ }
.pywry-chat-conv-title { /* Current conversation title display */ }
.pywry-chat-conv-dropdown { /* Dropdown menu */ }
.pywry-chat-chevron { /* Dropdown arrow icon */ }
.pywry-chat-thread-list { /* Thread list container */ }
.pywry-chat-thread-item { /* Individual thread item */ }
.pywry-chat-thread-item.active { /* Active/current thread */ }
.pywry-chat-thread-info { /* Thread info container */ }
.pywry-chat-thread-title { /* Thread title text */ }
.pywry-chat-thread-title-input { /* Editable title input */ }
.pywry-chat-thread-id { /* Thread ID (monospace) */ }
.pywry-chat-thread-actions { /* Action buttons (rename, delete) */ }
```

---

## Thinking & Todo

```css
/* LLM Thinking Block */
.pywry-chat-thinking { /* Thinking block (<details> element) */ }
.pywry-chat-thinking[open] { /* Expanded thinking */ }
.pywry-chat-thinking-summary { /* Thinking summary toggle */ }
.pywry-chat-thinking-icon { /* Thinking icon */ }
.pywry-chat-thinking-count { /* Token count display */ }
.pywry-chat-thinking-spinner { /* Animated thinking spinner */ }
.pywry-chat-thinking-content { /* Thinking text content */ }

/* Task Todo List */
.pywry-chat-todo { /* Todo list container (above input bar) */ }
.pywry-chat-todo-details { /* Collapsible details element */ }
.pywry-chat-todo-summary { /* Todo summary toggle */ }
.pywry-chat-todo-label { /* Todo label text */ }
.pywry-chat-todo-actions { /* Action buttons next to the summary (clear) */ }
.pywry-chat-todo-progress { /* Progress bar track */ }
.pywry-chat-todo-progress-fill { /* Progress bar fill */ }
.pywry-chat-todo-list { /* Todo items list */ }
.pywry-chat-todo-item { /* Individual todo item */ }
.pywry-chat-todo-item-done { /* Completed todo */ }
.pywry-chat-todo-item-active { /* Currently active todo */ }
.pywry-chat-todo-icon { /* Todo status icon (pending / active / done) */ }
.pywry-chat-todo-active { /* Active-state icon modifier */ }
.pywry-chat-todo-done { /* Done-state icon modifier */ }
.pywry-chat-todo-clear { /* Clear all button */ }
```

---

## Tool Calls & Artifacts

```css
/* Tool Calls */
.pywry-chat-tool-call { /* Tool call block (<details>) */ }
.pywry-chat-tool-call[open] { /* Expanded tool call */ }
.pywry-chat-tool-summary { /* Tool summary toggle */ }
.pywry-chat-tool-icon { /* Tool icon */ }
.pywry-chat-tool-label { /* Tool label text */ }
.pywry-chat-tool-name { /* Tool name (monospace) */ }
.pywry-chat-tool-spinner { /* Execution spinner */ }
.pywry-chat-tool-args { /* Tool arguments display */ }
.pywry-chat-tool-result { /* Tool result display */ }
.pywry-chat-tool-error { /* Error state */ }
.pywry-chat-tool-error-text { /* Error message text */ }

/* Artifacts */
.pywry-chat-artifact { /* Artifact container (<details>) */ }
.pywry-chat-artifact[open] { /* Expanded artifact */ }
.pywry-chat-artifact-header { /* Artifact header with icon + title */ }
.pywry-chat-artifact-chevron { /* Toggle arrow */ }
.pywry-chat-artifact-icon { /* Artifact type icon */ }
.pywry-chat-artifact-title { /* Artifact title text */ }
.pywry-chat-artifact-collapsed { /* Collapsed state text */ }
.pywry-chat-artifact-body { /* Artifact body wrapper */ }
.pywry-chat-artifact-content { /* Artifact content area */ }

/* Artifact Types */
.pywry-chat-artifact-code { /* Code artifact */ }
.pywry-chat-artifact-md { /* Markdown artifact */ }
.pywry-chat-artifact-iframe { /* HTML/iframe artifact */ }
.pywry-chat-artifact-image { /* Image artifact */ }
.pywry-chat-artifact-json { /* JSON artifact */ }
.pywry-chat-artifact-table { /* Table artifact */ }
.pywry-chat-artifact-plotly { /* Plotly chart artifact */ }
```

---

## Citations

```css
.pywry-chat-citation { /* Citation block */ }
.pywry-chat-citation-icon { /* Citation icon */ }
.pywry-chat-citation-snippet { /* Citation text snippet */ }
```

---

## Interactive Input

```css
.pywry-chat-input-prompt { /* Question prompt display */ }
.pywry-chat-input-prompt-icon { /* Prompt icon */ }
.pywry-chat-input-required { /* Required input indicator */ }
.pywry-chat-ir-controls { /* Inline controls container */ }
.pywry-chat-ir-buttons { /* Button group */ }
.pywry-chat-ir-btn { /* Inline button */ }
.pywry-chat-ir-radio-group { /* Radio option group */ }
.pywry-chat-ir-radio-item { /* Radio option item */ }
.pywry-chat-ir-radio-input { /* Radio input element */ }
.pywry-chat-ir-radio-label { /* Radio label */ }
.pywry-chat-ir-radio-submit { /* Submit button for radio selection */ }
```

---

## Command Palette & Mentions

```css
.pywry-chat-cmd-palette { /* Slash command palette popup */ }
.pywry-chat-cmd-item { /* Command item */ }
.pywry-chat-cmd-item.active { /* Active/highlighted command */ }
.pywry-chat-mention-popup { /* @mention autocomplete popup */ }
.pywry-chat-mention-item { /* Mention suggestion item */ }
.pywry-chat-mention-icon { /* Mention icon */ }
```

---

## Settings & Attachments

```css
/* Settings Menu */
.pywry-chat-settings-menu { /* Settings dropdown trigger */ }
.pywry-chat-settings-menu.open { /* Open state */ }
.pywry-chat-settings-dropdown { /* Dropdown menu */ }
.pywry-chat-settings-item { /* Settings item (radio, range, etc.) */ }
.pywry-chat-settings-item-label { /* Item label */ }
.pywry-chat-settings-sep { /* Separator line */ }
.pywry-chat-settings-range-val { /* Range value display */ }
.pywry-chat-settings-empty { /* "No settings configured" placeholder */ }

/* File Attachments */
.pywry-chat-attach-btn { /* Attach file button */ }
.pywry-chat-attachments-bar { /* Attachments display bar */ }
.pywry-chat-attachment-pill { /* Attachment badge/pill */ }
.pywry-chat-attachment-pill-icon { /* Attachment icon */ }
.pywry-chat-attachment-pill-name { /* Attachment filename */ }
.pywry-chat-attachment-pill-remove { /* Remove attachment button */ }
.pywry-chat-drop-overlay { /* Drag-and-drop overlay */ }
.pywry-chat-drop-overlay-content { /* Inner "Drop files here" message card */ }
.pywry-chat-msg-attachments { /* Attachments within a message */ }
.pywry-chat-msg-attach-badge { /* Attachment badge in message */ }
```

---

## Syntax Highlighting

Chat messages use a custom lightweight syntax highlighter:

```css
.pywry-hl-kw { /* Keyword — purple/magenta */ }
.pywry-hl-str { /* String — green */ }
.pywry-hl-cmt { /* Comment — italic, muted */ }
.pywry-hl-num { /* Number — orange */ }
.pywry-hl-fn { /* Function name — blue */ }
.pywry-hl-type { /* Type/builtin — teal */ }
.pywry-hl-dec { /* Decorator/attribute — yellow */ }
.pywry-hl-op { /* Operator */ }
.pywry-hl-punc { /* Punctuation */ }
.pywry-hl-prop { /* Property/key */ }
```

Both dark and light theme variants are provided.

---

## Markdown Rendering

```css
.pywry-chat-md-table { /* Markdown table in messages */ }
.pywry-chat-fmt-warn { /* Format timeout warning */ }
.pywry-chat-code-hidden { /* Hidden code block */ }
```
