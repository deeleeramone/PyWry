# Skills & Resources

The MCP server teaches AI agents how to use PyWry through two mechanisms: **skills** (prompt-based guidance documents) and **resources** (read-only data accessible via `pywry://` URIs). Together they give the agent the context it needs to build widgets correctly without hallucinating parameters or inventing APIs.

## Skills (Prompts)

Skills are structured guidance documents — each one a focused tutorial on a specific topic. They're registered as MCP prompts under the `skill:` prefix and also accessible via the `get_skills` tool.

### How Skills Work

1. **Agent connects** — If `skills_auto_load` is enabled, the skill list is available immediately
2. **Agent calls `get_skills`** — Returns the skill list with descriptions
3. **Agent calls `get_skills` with a specific skill** — Returns the full guidance text
4. **Agent reads `pywry://skill/{id}` resource** — Alternative access via MCP resources

Skills are **lazy-loaded** from markdown files on disk and cached in memory (LRU, max 16). They don't consume resources until first requested.

### Skill Reference

| ID | Priority | What it teaches |
|:---|:---|:---|
| `component_reference` | **Mandatory** | All 18 components — property tables, event signatures, JSON schemas, auto-wired actions, toolbar structure, event format rules |
| `interactive_buttons` | High | The `elementId:action` auto-wiring pattern for buttons (increment, decrement, reset, toggle) |
| `native` | Medium | Desktop native window mode — full-viewport layout, system integration, window management |
| `jupyter` | Medium | Notebook integration — AnyWidget (recommended) and IFrame (fallback) approaches with code examples |
| `iframe` | Medium | Sandboxed embedding — resize constraints, postMessage communication |
| `deploy` | Medium | Production SSE server mode — stateless widgets, horizontal scaling, Redis patterns |
| `css_selectors` | Medium | Targeting elements for `set_content` / `set_style` — component_id vs CSS selectors, selector patterns |
| `styling` | Medium | CSS variables (all `--pywry-*` properties), theme switching, `inject_css` usage |
| `data_visualization` | Medium | Plotly charts, AG Grid tables, Marquee tickers, live data polling and event-driven update patterns |
| `forms_and_inputs` | Medium | Form building with TextInput, Select, Toggle, etc. — validation patterns, event-based data collection |
| `modals` | Medium | Modal dialog schemas — sizes, nested components, open/close events, JS API, `reset_on_close` behavior |
| `autonomous_building` | Medium | End-to-end app generation — `plan_widget`, `build_app`, `export_project`, `scaffold_app` workflows and chaining patterns |

### The Component Reference

The `component_reference` skill is special — it's the **authoritative source** for all toolbar component definitions. It contains:

- Property tables for all 18 component types
- Event payload signatures for each component
- JSON schema examples for tool call construction
- Auto-wired action documentation
- Toolbar structure and nesting rules
- Event naming conventions (`namespace:event-name`)

Agents should load this skill before creating any widgets with toolbars.

### Accessing Skills

**Via the `get_skills` tool:**

```
// List all skills
get_skills()

// Get specific skill
get_skills(skill="component_reference")
get_skills(skill="data_visualization")
```

**Via resources:**

```
read_resource("pywry://skill/component_reference")
read_resource("pywry://skill/forms_and_inputs")
```

**Via prompts (MCP prompt protocol):**

```
get_prompt("skill:component_reference")
get_prompt("skill:modals")
```

---

## Resources

Resources are read-only data the agent can fetch via MCP's `read_resource` or `list_resources` protocol methods.

### Documentation Resources

| URI | Content | MIME |
|:---|:---|:---|
| `pywry://docs/events` | Built-in events reference — all 14 system events with descriptions, tool mappings, and payload schemas | `text/markdown` |
| `pywry://docs/quickstart` | Getting started guide | `text/markdown` |

### Component Resources

| URI Pattern | Content | MIME |
|:---|:---|:---|
| `pywry://component/{name}` | Component documentation — properties, description, usage example | `text/markdown` |
| `pywry://source/{name}` | Python source code for the component class (via `inspect.getsource()`) | `text/x-python` |
| `pywry://source/components` | All component source codes combined into one document | `text/x-python` |

Available `{name}` values: `button`, `select`, `multiselect`, `toggle`, `checkbox`, `radio`, `tabs`, `text`, `textarea`, `search`, `number`, `date`, `slider`, `range`, `div`, `secret`, `marquee`, `ticker_item`, `toolbar`, `option`

### Skill Resources

| URI Pattern | Content | MIME |
|:---|:---|:---|
| `pywry://skill/{skill_id}` | Full skill guidance text | `text/markdown` |

### Export Resources

| URI Pattern | Content | MIME |
|:---|:---|:---|
| `pywry://export/{widget_id}` | Active widget exported as a complete Python script | `text/x-python` |

### Resource Templates

The server also registers MCP resource templates for parameterized URIs:

| URI Template | Description |
|:---|:---|
| `pywry://component/{component}` | Component documentation |
| `pywry://source/{component}` | Component source code |
| `pywry://export/{widget_id}` | Widget export |
| `pywry://skill/{skill}` | Skill guidance |

---

## Built-In Events Reference

The `pywry://docs/events` resource documents all system events that can be sent via the `send_event` tool:

| Event | Description |
|:---|:---|
| `pywry:set-content` | Update element text/HTML |
| `pywry:set-style` | Update element CSS styles |
| `pywry:alert` | Show toast notification |
| `pywry:update-theme` | Switch theme |
| `pywry:inject-css` | Inject CSS rules |
| `pywry:remove-css` | Remove injected CSS |
| `pywry:navigate` | Client-side redirect |
| `pywry:download` | Trigger file download |
| `plotly:update-figure` | Update Plotly chart |
| `plotly:update-layout` | Update Plotly layout only |
| `toolbar:marquee-set-content` | Update marquee content |
| `toolbar:marquee-set-item` | Update marquee ticker item |
| `modal:open:{id}` | Open a modal |
| `modal:close:{id}` | Close a modal |

Most of these have dedicated tools (e.g., `set_content`, `inject_css`). The `send_event` tool is the low-level escape hatch for events that don't have a dedicated tool.

## How Agents Use This System

A typical interaction pattern:

1. **Agent list tools** → sees 29 available tools
2. **Agent calls `get_skills()`** → receives the skill list with descriptions
3. **Agent calls `get_skills(skill="component_reference")`** → loads the mandatory component docs
4. **Agent calls `create_widget`** → builds widget JSON using component reference as guide
5. **Agent calls `get_events`** → reads user interactions
6. **Agent calls `set_content` / `set_style`** → updates the widget in response
7. **Agent calls `export_widget`** → generates Python code the user can save
8. **Agent calls `build_app`** *(optional)* → fully autonomous end-to-end build from a description

The skills ensure the agent knows the exact JSON structure, event naming conventions, and available properties before making tool calls.

## Next Steps

- **[Tools Reference](tools.md)** — Every tool with parameters
- **[Examples](examples.md)** — Common workflows
- **[Setup](setup.md)** — Configuration and client setup
