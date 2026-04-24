# External marketplace / index submissions

Drafts for announcing the `pywry` Claude Code plugin to community
indexes and any first-party Anthropic registry. Each entry is ready to
copy / paste into a PR or issue against the target repo.

## Status tracker

| Target | State | PR / Issue |
|:---|:---|:---|
| [anthropics/claude-code](https://github.com/anthropics/claude-code) (if a plugin marketplace is accepted there) | TODO | — |
| [hesreallyhim/awesome-claude-code-agents](https://github.com/hesreallyhim/awesome-claude-code-agents) or successor `awesome-claude-code` list | TODO | — |
| [mcp-ui](https://github.com/mcp-ui) / mcpui.dev ecosystem listings | TODO | — |
| [claudecodemarketplace.com](https://claudecodemarketplace.com) (if they accept submissions) | TODO | — |

Update this file as submissions land.

---

## Standard announcement text

> **PyWry** — native Claude Code integration for the
> [PyWry](https://github.com/deeleeramone/PyWry) Python rendering
> engine. MCP tools for generating and rendering HTML components,
> chat artifacts, and building native, web, or Jupyter applications
> with live preview. Built-in support for AgGrid, Plotly,
> TradingView, and more. Widget-creating tools auto-return
> self-contained HTML `AppArtifact`s that MCP-UI-aware clients render
> inline.
>
> **Install**
> ```
> /plugin marketplace add deeleeramone/PyWry --path claude/.claude-plugin/marketplace.json
> /plugin install pywry@pywry
> ```
>
> **Prerequisite:** `pip install 'pywry[dev]'`.
>
> Docs: <https://deeleeramone.github.io/PyWry/mcp/plugin/>
> Source: <https://github.com/deeleeramone/PyWry/tree/main/claude/plugins/pywry>
> License: Apache-2.0

## awesome-claude-code list entry (markdown)

Drop this under the appropriate category (Plugins / Data / Charting).

```markdown
- **[pywry](https://github.com/deeleeramone/PyWry)** — MCP tools for
  generating and rendering HTML components, chat artifacts, and
  building native, web, or Jupyter applications with live preview.
  Built-in support for AgGrid, Plotly, TradingView, and more.
  Widget-creating tools auto-return `AppArtifact` snapshots for inline
  display in MCP-UI clients. Install:
  `/plugin marketplace add deeleeramone/PyWry --path claude/.claude-plugin/marketplace.json && /plugin install pywry@pywry`
  (Apache-2.0)
```

## anthropics/claude-code marketplace entry (JSON)

If Anthropic accepts community submissions into their first-party
marketplace (check the repo's CONTRIBUTING before filing), this is the
entry to add. The snippet matches the
[plugin source schema](https://code.claude.com/docs/en/plugin-marketplaces)
for a GitHub-hosted plugin:

```json
{
  "name": "pywry",
  "source": {
    "source": "github",
    "repo": "deeleeramone/PyWry",
    "path": "claude/plugins/pywry"
  },
  "description": "Native Claude Code integration for PyWry — MCP tools for generating and rendering HTML components, chat artifacts, and building native, web, or Jupyter applications with live preview. Built-in support for AgGrid, Plotly, TradingView, and more. AppArtifact auto-return for rich inline display.",
  "version": "0.1.0",
  "author": {
    "name": "PyWry",
    "email": "pywry2@gmail.com",
    "url": "https://github.com/deeleeramone/PyWry"
  },
  "license": "Apache-2.0",
  "keywords": ["pywry", "webview", "plotly", "tradingview", "dashboard", "chat", "mcp"]
}
```

## mcp-ui ecosystem listing (YAML)

If/when [mcp-ui.dev](https://mcpui.dev) maintains a directory of
MCP-UI-producing servers, submit something like:

```yaml
- name: pywry
  description: Self-contained HTML widget snapshots (AppArtifact) from PyWry MCP tools.
  ui_resource_mime_type: text/html
  ui_resource_uri_scheme: pywry-app
  repo: https://github.com/deeleeramone/PyWry
  plugin_path: claude/plugins/pywry
  license: Apache-2.0
```

## Claude Desktop / Code extension registry (if distinct)

If Anthropic or the community runs a separate registry focused on
Claude Desktop extensions, the same announcement text works. Add here
when that channel materialises.
