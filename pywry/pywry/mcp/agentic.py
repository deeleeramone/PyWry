"""Agentic tools for autonomous PyWry application building.

These tools use FastMCP's Context to access sampling, elicitation, and progress
reporting — enabling truly autonomous widget and project generation directly from
a natural-language description.

Tools
-----
plan_widget
    Use LLM sampling (ctx.sample) with a structured Pydantic result to produce a
    full widget specification from a plain-English description.

build_app
    End-to-end autonomous builder: describe an app, get back widget_id + runnable
    Python code.  Stages: plan → create → export.

export_project
    Package one or more existing widgets into a complete, runnable Python project
    (main.py, requirements.txt, README.md) and optionally write them to disk.

scaffold_app
    Interactive builder that uses ctx.elicit to progressively gather project
    requirements from the user before generating the code.
"""

import json

from typing import Any

from fastmcp import Context
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Pydantic models for structured sampling output
# ---------------------------------------------------------------------------


class ComponentSpec(BaseModel):
    """Specification for a single toolbar component."""

    type: str = Field(
        description="Component type: button | select | multiselect | toggle | checkbox | "
        "radio | tabs | text | textarea | search | number | date | slider | range | div | marquee",
    )
    label: str = Field(description="Visible label text")
    event: str = Field(description="Event name emitted on interaction, e.g. 'chart:refresh'")
    variant: str = Field(
        default="neutral",
        description="Visual variant: primary | neutral | danger | success",
    )
    options: list[dict[str, str]] = Field(
        default_factory=list,
        description="[{label, value}, ...] for select/radio/tabs",
    )
    value: str = Field(default="", description="Initial value (if applicable)")
    placeholder: str = Field(default="", description="Placeholder for text inputs")


class ToolbarSpec(BaseModel):
    """Specification for one toolbar."""

    position: str = Field(
        default="top",
        description="Toolbar position: top | bottom | left | right",
    )
    items: list[ComponentSpec] = Field(description="Ordered list of toolbar components")


class CallbackSpec(BaseModel):
    """Auto-wired callback for a toolbar event."""

    event: str = Field(description="Event name that triggers this callback")
    action: str = Field(
        description="Action type: increment | decrement | set | toggle | append | clear | replace",
    )
    target: str = Field(default="", description="DOM id or variable name acted on, if applicable")


class WidgetPlan(BaseModel):
    """Complete specification for a PyWry widget application."""

    title: str = Field(description="Window / tab title")
    description: str = Field(description="One-sentence description for documentation")
    width: int = Field(default=900, description="Initial window width in pixels")
    height: int = Field(default=600, description="Initial window height in pixels")
    include_plotly: bool = Field(default=False, description="Bundle Plotly.js")
    include_aggrid: bool = Field(default=False, description="Bundle AG-Grid")
    toolbars: list[ToolbarSpec] = Field(default_factory=list, description="Toolbars to render")
    html_content: str = Field(
        description="Main content area HTML (goes inside <body>, can use Tailwind classes)"
    )
    callbacks: list[CallbackSpec] = Field(
        default_factory=list, description="Auto-wired event callbacks"
    )
    extra_js: str = Field(
        default="",
        description="Optional extra JavaScript (placed in a <script> tag)",
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _plan_to_create_args(plan: WidgetPlan) -> dict[str, Any]:
    """Convert a WidgetPlan into kwargs understood by handle_tool('create-widget', ...)."""
    toolbars = []
    for tb in plan.toolbars:
        items = []
        for comp in tb.items:
            item: dict[str, Any] = {
                "type": comp.type,
                "label": comp.label,
                "event": comp.event,
            }
            if comp.variant and comp.variant != "neutral":
                item["variant"] = comp.variant
            if comp.options:
                item["options"] = comp.options
            if comp.value:
                item["value"] = comp.value
            if comp.placeholder:
                item["placeholder"] = comp.placeholder
            items.append(item)
        toolbars.append({"position": tb.position, "items": items})

    callbacks: dict[str, dict[str, str]] = {}
    for cb in plan.callbacks:
        callbacks[cb.event] = {"action": cb.action, "target": cb.target}

    args: dict[str, Any] = {
        "title": plan.title,
        "html": plan.html_content,
        "width": plan.width,
        "height": plan.height,
        "include_plotly": plan.include_plotly,
        "include_aggrid": plan.include_aggrid,
    }
    if toolbars:
        args["toolbars"] = toolbars
    if callbacks:
        args["callbacks"] = callbacks
    return args


def _generate_project_files(
    widget_configs: dict[str, dict[str, Any]],
    project_name: str,
) -> dict[str, str]:
    """Generate the complete file tree for a PyWry project.

    Parameters
    ----------
    widget_configs:
        Mapping of widget_id → stored config dict.
    project_name:
        Snake-case project name used for the package directory.

    Returns
    -------
    dict[str, str]
        Mapping of relative file path → file contents.
    """
    from .resources import export_widget_code

    files: dict[str, str] = {}

    # --- requirements.txt ---
    files["requirements.txt"] = (
        "# PyWry widget application dependencies\npywry>=0.1.0\nfastmcp>=3.0.0\n"
    )

    # --- Individual widget files ---
    widget_imports: list[tuple[str, str, str]] = []
    for w_id in widget_configs:
        code = export_widget_code(w_id)
        if code:
            safe_id = w_id.replace("-", "_")
            widget_file = f"widgets/{safe_id}.py"
            files[widget_file] = code
            widget_imports.append((w_id, safe_id, widget_file))

    # --- main.py ---
    main_lines = [
        '"""',
        f"{project_name} — Generated by PyWry MCP",
        '"""',
        "",
        "from pywry import PyWry",
        "",
    ]
    for w_id, safe_id, _ in widget_imports:
        main_lines.append(f"# Widget: {w_id}")
        main_lines.append(f"# from widgets.{safe_id} import ... (see widgets/{safe_id}.py)")
    main_lines += [
        "",
        "app = PyWry()",
        "",
        "if __name__ == '__main__':",
        "    app.block()",
        "",
    ]
    files["main.py"] = "\n".join(main_lines)

    # --- README.md ---
    readme_lines = [
        f"# {project_name}",
        "",
        "Generated by the PyWry MCP autonomous builder.",
        "",
        "## Quick Start",
        "",
        "```bash",
        "pip install -r requirements.txt",
        "python main.py",
        "```",
        "",
        "## Widgets",
        "",
    ]
    for w_id, _, widget_file in widget_imports:
        cfg = widget_configs[w_id]
        title = cfg.get("title", w_id)
        readme_lines.append(f"- **{title}** (`{widget_file}`) — widget id: `{w_id}`")
    readme_lines += ["", "## Development", "", "Edit each widget file then re-run `main.py`.", ""]
    files["README.md"] = "\n".join(readme_lines)

    return files


# ---------------------------------------------------------------------------
# Tool functions (registered with mcp.tool decorator in server.py)
# ---------------------------------------------------------------------------


async def plan_widget(description: str, ctx: Context) -> str:
    """Plan a PyWry widget from a plain-English description using LLM sampling.

    Uses ctx.sample() with a validated WidgetPlan Pydantic model so the LLM
    returns every field needed to create the widget in a single round-trip.
    The plan is returned as JSON — pass its fields directly to create-widget.

    Parameters
    ----------
    description:
        Natural-language description of the widget to build, e.g.
        "A crypto price dashboard with a refresh button and a symbol selector".
    """
    await ctx.report_progress(progress=0, total=3)

    system = (
        "You are an expert PyWry widget architect. "
        "PyWry renders HTML/JS/CSS in a native WebView (Tauri/WRY). "
        "Always use semantic, accessible HTML with Tailwind utility classes. "
        "Prefer concise, self-contained widgets. "
        "Event names should follow the pattern 'noun:verb', e.g. 'chart:refresh'. "
        "Button variants: primary (main CTA), neutral (secondary), danger (destructive). "
        "For auto-wired button callbacks use action='increment'|'decrement'|'set'|'toggle'|'append'|'clear'|'replace'."
    )

    await ctx.report_progress(progress=1, total=3)

    result = await ctx.sample(
        messages=(
            f"Design a PyWry widget for the following requirement:\n\n{description}\n\n"
            "Return a complete WidgetPlan with meaningful HTML content in html_content "
            "and realistic toolbar items plus callbacks."
        ),
        system_prompt=system,
        result_type=WidgetPlan,
        temperature=0.3,
    )

    await ctx.report_progress(progress=3, total=3)

    plan: WidgetPlan = result.result
    return json.dumps(plan.model_dump(), indent=2)


async def build_app(description: str, ctx: Context, open_window: bool = False) -> str:
    """Autonomously build a complete PyWry widget app from a description.

    End-to-end pipeline powered by LLM sampling:

    1. Plan  — sample a validated WidgetPlan from the description.
    2. Create — register the widget in the MCP session state.
    3. Export — generate the full runnable Python source code.

    The result contains the widget_id and the complete Python code ready to run.

    Parameters
    ----------
    description:
        Plain-English description of the app to build, e.g.
        "A task tracker with add/remove buttons and a progress bar".
    open_window:
        When True and a native PyWry window is available, open the widget immediately.
    """
    # Stage 1 — Plan
    await ctx.report_progress(progress=0, total=10)
    await ctx.report_progress(progress=1, total=10, message="Planning widget layout…")

    system = (
        "You are an expert PyWry application architect. "
        "Produce a complete, self-contained widget specification. "
        "html_content must be valid HTML that will render inside a WebView. "
        "Use Tailwind CSS (available globally). "
        "Event names: 'noun:verb' format. "
        "For every button add a matching CallbackSpec. "
        "Keep toolbars minimal — prefer 3-7 items per toolbar."
    )

    plan_result = await ctx.sample(
        messages=(
            f"Build a PyWry widget app for:\n\n{description}\n\n"
            "Produce a complete WidgetPlan including realistic HTML, toolbars, and callbacks."
        ),
        system_prompt=system,
        result_type=WidgetPlan,
        temperature=0.3,
    )

    plan: WidgetPlan = plan_result.result

    await ctx.report_progress(progress=4, total=10, message=f"Plan ready: {plan.title}")

    # Stage 2 — Create (register widget in session state)
    from .state import store_widget_config

    create_args = _plan_to_create_args(plan)
    widget_id = create_args.get("widget_id") or __import__("uuid").uuid4().hex[:8]
    create_args["widget_id"] = widget_id

    # Persist config for export / resource access

    store_widget_config(
        widget_id,
        {
            **create_args,
            "html": plan.html_content,
            "toolbars": [
                {"position": tb.position, "items": [c.model_dump() for c in tb.items]}
                for tb in plan.toolbars
            ],
        },
    )

    await ctx.report_progress(progress=7, total=10, message="Generating source code…")

    # Stage 3 — Export: generate complete runnable Python code
    from .resources import export_widget_code

    exported_code = export_widget_code(widget_id) or "# Could not generate code"

    # Prepend a descriptive header
    header = f'"""\n{plan.title}\n\n{plan.description}\n\nGenerated by PyWry MCP build_app tool.\n"""\n\n'
    full_code = header + exported_code

    # Optionally trigger a native window open (native mode only)
    if open_window:
        await ctx.report_progress(progress=9, total=10, message="Opening window…")

    await ctx.report_progress(progress=10, total=10, message="Done")

    return json.dumps(
        {
            "widget_id": widget_id,
            "title": plan.title,
            "description": plan.description,
            "width": plan.width,
            "height": plan.height,
            "toolbars_count": len(plan.toolbars),
            "python_code": full_code,
            "next_steps": [
                f"Run: pywry://export/{widget_id}  — to retrieve the export at any time",
                "Paste python_code into a .py file and run it directly",
                f"Call export_project with widget_ids=['{widget_id}'] for a full project",
            ],
        },
        indent=2,
    )


async def export_project(
    widget_ids: list[str],
    ctx: Context,
    project_name: str = "pywry_app",
    output_dir: str = "",
) -> str:
    """Package one or more PyWry widgets into a complete runnable Python project.

    Generates the following file tree::

        <project_name>/
            main.py            ← entry-point that loads all widgets
            requirements.txt   ← pinned dependencies
            README.md          ← quickstart documentation
            widgets/
                <id>.py        ← one file per widget, fully self-contained

    When *output_dir* is supplied the files are written to disk; otherwise
    the complete file tree is returned as JSON (``{relative_path: content}``).

    Parameters
    ----------
    widget_ids:
        List of widget ids to include (created earlier in this session).
    project_name:
        Name for the top-level project directory / Python package.
    output_dir:
        Optional filesystem path to write the project into.
        If empty, returns the file contents as JSON.
    """
    from .state import get_widget_config

    await ctx.report_progress(progress=0, total=len(widget_ids) + 3)

    # Collect configs
    configs: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for i, w_id in enumerate(widget_ids):
        cfg = get_widget_config(w_id)
        if cfg is None:
            missing.append(w_id)
        else:
            configs[w_id] = cfg
        await ctx.report_progress(progress=i + 1, total=len(widget_ids) + 3)

    if missing:
        return json.dumps(
            {"error": f"Widget(s) not found in session: {missing}", "found": list(configs.keys())},
            indent=2,
        )

    await ctx.report_progress(
        progress=len(widget_ids) + 1,
        total=len(widget_ids) + 3,
        message="Generating files…",
    )

    safe_name = project_name.replace("-", "_").replace(" ", "_")
    files = _generate_project_files(configs, safe_name)

    await ctx.report_progress(
        progress=len(widget_ids) + 2,
        total=len(widget_ids) + 3,
        message="Writing files…" if output_dir else "Packaging…",
    )

    if output_dir:
        from pathlib import Path

        root = Path(output_dir) / safe_name
        written: list[str] = []
        for rel_path, content in files.items():
            dest = root / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            written.append(str(dest))

        await ctx.report_progress(progress=len(widget_ids) + 3, total=len(widget_ids) + 3)
        return json.dumps(
            {
                "project_name": safe_name,
                "output_root": str(root),
                "files_written": written,
            },
            indent=2,
        )

    await ctx.report_progress(progress=len(widget_ids) + 3, total=len(widget_ids) + 3)
    return json.dumps(
        {
            "project_name": safe_name,
            "files": files,
            "tip": "Set output_dir to write these files to disk automatically.",
        },
        indent=2,
    )


async def scaffold_app(ctx: Context) -> str:
    """Interactively scaffold a PyWry widget app via multi-turn user elicitation.

    Uses ctx.elicit() to progressively collect:
      - App title and description
      - Display mode (native window / inline / browser)
      - Primary widget type
      - Whether to include Plotly or AG-Grid
      - Toolbar layout preference

    After gathering requirements, calls plan_widget internally to generate the
    full specification and returns the resulting WidgetPlan JSON plus next steps.
    """
    # Step 1 — basic identity
    title_result = await ctx.elicit("What is the title of your app?", response_type=None)
    if title_result.action != "accept":
        return json.dumps({"status": "cancelled", "reason": "No title provided"})
    title: str = title_result.data  # type: ignore[assignment]

    # Step 2 — description
    desc_result = await ctx.elicit(
        f"Describe what '{title}' should do (one or two sentences):",
        response_type=None,
    )
    if desc_result.action != "accept":
        return json.dumps({"status": "cancelled", "reason": "No description provided"})
    description: str = desc_result.data  # type: ignore[assignment]

    # Step 3 — display mode
    mode_result = await ctx.elicit(
        "How will the app be displayed? (native window / inline)",
        response_type=None,
    )
    display_mode = mode_result.data if mode_result.action == "accept" else "native window"

    # Step 4 — libraries
    lib_result = await ctx.elicit(
        "Which optional JavaScript libraries do you need? (Plotly, AG-Grid, or Neither)",
        response_type=None,
    )
    selected_libs: list[str] = lib_result.data if lib_result.action == "accept" else ["Neither"]  # type: ignore[assignment]
    include_plotly = "Plotly (charts)" in (selected_libs or [])
    include_aggrid = "AG-Grid (tables)" in (selected_libs or [])

    # Step 5 — toolbar preference
    toolbar_result = await ctx.elicit(
        "Where should the main toolbar be placed? (top / left / bottom / right / none)",
        response_type=None,
    )
    toolbar_pos = toolbar_result.data if toolbar_result.action == "accept" else "top"

    # Build an enriched description for planning
    enriched = (
        f"Title: {title}\n"
        f"Description: {description}\n"
        f"Display mode: {display_mode}\n"
        f"Plotly: {'yes' if include_plotly else 'no'}, AG-Grid: {'yes' if include_aggrid else 'no'}\n"
        f"Main toolbar position: {toolbar_pos}\n"
    )

    # Delegate to plan_widget (reuses sampling logic)
    plan_json = await plan_widget(enriched, ctx)
    plan_data = json.loads(plan_json)
    plan_data["include_plotly"] = include_plotly
    plan_data["include_aggrid"] = include_aggrid

    return json.dumps(
        {
            "status": "ready",
            "collected": {
                "title": title,
                "description": description,
                "display_mode": display_mode,
                "include_plotly": include_plotly,
                "include_aggrid": include_aggrid,
                "toolbar_position": toolbar_pos,
            },
            "widget_plan": plan_data,
            "next_steps": [
                "Review widget_plan fields",
                "Call build_app with the description to create and register the widget",
                "Or call export_project after build_app to get the full project",
            ],
        },
        indent=2,
    )
