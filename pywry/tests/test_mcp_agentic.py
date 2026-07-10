"""Tests for ``pywry.mcp.agentic`` — autonomous-building MCP tools.

Covers:
- Pydantic models: ``ComponentSpec``, ``ToolbarSpec``, ``WidgetPlan``,
  ``CallbackSpec`` validation and defaults.
- ``_plan_to_create_args`` shape — title, html, toolbars, callbacks dict.
- ``_generate_project_files`` produces main.py / requirements.txt / README.md.
- ``export_project`` returns error for missing widget; generates files
  in-memory by default and writes them to disk when ``output_dir`` is set.
- ``build_app`` returns a widget id and python code (via mocked sampling).
- ``plan_widget`` returns a JSON-serialized WidgetPlan (via mocked sampling).
- ``scaffold_app`` honours elicitation flow including cancel paths.
"""

from __future__ import annotations

import json

from typing import Any
from unittest.mock import AsyncMock, MagicMock


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class TestPydanticModels:
    def test_component_spec_defaults(self) -> None:
        from pywry.mcp.agentic import ComponentSpec

        comp = ComponentSpec(type="button", label="Refresh", event="chart:refresh")
        assert comp.type == "button"
        assert comp.variant == "neutral"
        assert comp.options == []

    def test_toolbar_spec_holds_position_and_items(self) -> None:
        from pywry.mcp.agentic import ComponentSpec, ToolbarSpec

        tb = ToolbarSpec(
            position="top",
            items=[ComponentSpec(type="button", label="Go", event="app:go")],
        )
        assert tb.position == "top"
        assert len(tb.items) == 1

    def test_widget_plan_defaults(self) -> None:
        from pywry.mcp.agentic import WidgetPlan

        plan = WidgetPlan(
            title="Test App",
            description="A test widget",
            html_content="<p>Hello</p>",
        )
        assert plan.width == 900
        assert plan.height == 600
        assert plan.include_plotly is False
        assert plan.include_aggrid is False
        assert plan.toolbars == []
        assert plan.callbacks == []

    def test_callback_spec_defaults(self) -> None:
        from pywry.mcp.agentic import CallbackSpec

        cb = CallbackSpec(event="counter:increment", action="increment")
        assert cb.action == "increment"
        assert cb.target == ""


# ---------------------------------------------------------------------------
# _plan_to_create_args
# ---------------------------------------------------------------------------


class TestPlanToCreateArgs:
    def test_basic_shape(self) -> None:
        from pywry.mcp.agentic import (
            ComponentSpec,
            ToolbarSpec,
            WidgetPlan,
            _plan_to_create_args,
        )

        plan = WidgetPlan(
            title="My App",
            description="Test",
            html_content="<p>content</p>",
            toolbars=[
                ToolbarSpec(
                    position="top",
                    items=[ComponentSpec(type="button", label="Click", event="app:click")],
                )
            ],
        )
        args = _plan_to_create_args(plan)
        assert args["title"] == "My App"
        assert args["html"] == "<p>content</p>"
        assert len(args["toolbars"]) == 1
        assert args["toolbars"][0]["position"] == "top"
        assert args["toolbars"][0]["items"][0]["type"] == "button"

    def test_callbacks_converted_to_dict(self) -> None:
        from pywry.mcp.agentic import CallbackSpec, WidgetPlan, _plan_to_create_args

        plan = WidgetPlan(
            title="App",
            description="x",
            html_content="<p></p>",
            callbacks=[CallbackSpec(event="btn:click", action="increment")],
        )
        args = _plan_to_create_args(plan)
        assert args["callbacks"]["btn:click"]["action"] == "increment"

    def test_omits_keys_when_empty(self) -> None:
        from pywry.mcp.agentic import WidgetPlan, _plan_to_create_args

        plan = WidgetPlan(title="A", description="b", html_content="<p></p>")
        args = _plan_to_create_args(plan)
        assert "toolbars" not in args
        assert "callbacks" not in args

    def test_component_extras_propagate(self) -> None:
        """Components with variant/options/value/placeholder all serialize."""
        from pywry.mcp.agentic import (
            ComponentSpec,
            ToolbarSpec,
            WidgetPlan,
            _plan_to_create_args,
        )

        plan = WidgetPlan(
            title="X",
            description="d",
            html_content="<p></p>",
            toolbars=[
                ToolbarSpec(
                    position="top",
                    items=[
                        ComponentSpec(
                            type="select",
                            label="L",
                            event="x:y",
                            options=[{"label": "A", "value": "a"}],
                            value="a",
                            placeholder="Pick",
                            variant="primary",
                        )
                    ],
                )
            ],
        )
        args = _plan_to_create_args(plan)
        item = args["toolbars"][0]["items"][0]
        assert item["variant"] == "primary"
        assert item["options"][0]["value"] == "a"
        assert item["value"] == "a"
        assert item["placeholder"] == "Pick"


# ---------------------------------------------------------------------------
# _generate_project_files
# ---------------------------------------------------------------------------


class TestGenerateProjectFiles:
    def test_produces_expected_keys(self) -> None:
        from pywry.mcp.agentic import _generate_project_files

        files = _generate_project_files({}, "my_app")
        assert "main.py" in files
        assert "requirements.txt" in files
        assert "README.md" in files

    def test_requirements_contains_pywry(self) -> None:
        from pywry.mcp.agentic import _generate_project_files

        files = _generate_project_files({}, "my_app")
        assert "pywry" in files["requirements.txt"]

    def test_readme_uses_project_name(self) -> None:
        from pywry.mcp.agentic import _generate_project_files

        files = _generate_project_files({}, "cool_project")
        assert "# cool_project" in files["README.md"]


# ---------------------------------------------------------------------------
# export_project
# ---------------------------------------------------------------------------


class TestExportProject:
    async def test_missing_widget_returns_error(self, mcp_fresh_state) -> None:
        from pywry.mcp.agentic import export_project

        ctx = MagicMock()
        ctx.report_progress = AsyncMock()

        result = await export_project(widget_ids=["does-not-exist"], ctx=ctx)
        data = json.loads(result)
        assert "error" in data
        assert "does-not-exist" in data["error"]

    async def test_generates_files_for_known_widget(self, mcp_fresh_state) -> None:
        from pywry.mcp.agentic import export_project
        from pywry.mcp.state import store_widget_config

        store_widget_config(
            "test-export-001",
            {
                "title": "Test Widget",
                "html": "<p>Hello</p>",
                "width": 800,
                "height": 500,
                "include_plotly": False,
                "include_aggrid": False,
                "toolbars": [],
            },
        )

        ctx = MagicMock()
        ctx.report_progress = AsyncMock()
        result = await export_project(
            widget_ids=["test-export-001"], ctx=ctx, project_name="test_proj"
        )
        data = json.loads(result)
        assert "files" in data
        assert "main.py" in data["files"]
        assert "requirements.txt" in data["files"]
        assert "README.md" in data["files"]

    async def test_writes_files_to_disk(self, mcp_fresh_state, tmp_path: Any) -> None:
        from pywry.mcp.agentic import export_project
        from pywry.mcp.state import store_widget_config

        store_widget_config(
            "test-export-002",
            {
                "title": "Disk Widget",
                "html": "<p>Hi</p>",
                "width": 800,
                "height": 500,
                "include_plotly": False,
                "include_aggrid": False,
                "toolbars": [],
            },
        )

        ctx = MagicMock()
        ctx.report_progress = AsyncMock()
        result = await export_project(
            widget_ids=["test-export-002"],
            ctx=ctx,
            project_name="disk_proj",
            output_dir=str(tmp_path),
        )
        data = json.loads(result)
        assert "files_written" in data
        proj_root = tmp_path / "disk_proj"
        assert (proj_root / "main.py").exists()
        assert (proj_root / "requirements.txt").exists()
        assert (proj_root / "README.md").exists()

    async def test_progress_reported_while_writing(self, mcp_fresh_state, tmp_path: Any) -> None:
        from pywry.mcp.agentic import export_project
        from pywry.mcp.state import store_widget_config

        store_widget_config(
            "ep-1",
            {"title": "T", "html": "<p></p>", "toolbars": []},
        )
        ctx = MagicMock()
        ctx.report_progress = AsyncMock()
        result = await export_project(
            widget_ids=["ep-1"],
            ctx=ctx,
            project_name="my-app",
            output_dir=str(tmp_path),
        )
        data = json.loads(result)
        assert "files_written" in data


# ---------------------------------------------------------------------------
# build_app (sampling mocked)
# ---------------------------------------------------------------------------


class TestBuildApp:
    async def test_returns_widget_id_and_code(self, mcp_fresh_state) -> None:
        from pywry.mcp.agentic import WidgetPlan, build_app

        mock_plan = WidgetPlan(
            title="Counter",
            description="A simple counter widget",
            html_content="<div id='counter'>0</div>",
        )
        mock_sample_result = MagicMock()
        mock_sample_result.result = mock_plan

        ctx = MagicMock()
        ctx.report_progress = AsyncMock()
        ctx.sample = AsyncMock(return_value=mock_sample_result)

        result = await build_app(description="A simple counter", ctx=ctx)
        data = json.loads(result)
        assert "widget_id" in data
        assert "python_code" in data
        assert "Counter" in data["title"]
        assert len(data["widget_id"]) > 0
        assert "Counter" in data["python_code"]

    async def test_open_window_branch(self, mcp_fresh_state) -> None:
        from pywry.mcp.agentic import WidgetPlan, build_app

        mock_plan = WidgetPlan(title="OW", description="d", html_content="<p></p>")
        mock_sample_result = MagicMock()
        mock_sample_result.result = mock_plan

        ctx = MagicMock()
        ctx.report_progress = AsyncMock()
        ctx.sample = AsyncMock(return_value=mock_sample_result)

        result = await build_app(description="x", ctx=ctx, open_window=True)
        data = json.loads(result)
        assert "widget_id" in data


# ---------------------------------------------------------------------------
# plan_widget (sampling mocked)
# ---------------------------------------------------------------------------


class TestPlanWidget:
    async def test_returns_serialized_plan(self) -> None:
        from pywry.mcp.agentic import WidgetPlan, plan_widget

        mock_plan = WidgetPlan(
            title="Price Dashboard",
            description="Crypto price display",
            html_content="<div>BTC: $100k</div>",
        )
        mock_result = MagicMock()
        mock_result.result = mock_plan

        ctx = MagicMock()
        ctx.report_progress = AsyncMock()
        ctx.sample = AsyncMock(return_value=mock_result)

        result = await plan_widget("crypto price dashboard", ctx)
        data = json.loads(result)
        assert data["title"] == "Price Dashboard"
        assert "html_content" in data
        assert "toolbars" in data


# ---------------------------------------------------------------------------
# scaffold_app (elicit + sampling mocked)
# ---------------------------------------------------------------------------


class TestScaffoldApp:
    async def test_cancelled_on_title(self) -> None:
        from pywry.mcp.agentic import scaffold_app

        ctx = MagicMock()
        ctx.report_progress = AsyncMock()
        ctx.elicit = AsyncMock(return_value=MagicMock())  # not AcceptedElicitation
        result = await scaffold_app(ctx)
        data = json.loads(result)
        assert data["status"] == "cancelled"
        assert "title" in data["reason"].lower()

    async def test_cancelled_on_description(self) -> None:
        from mcp.server.elicitation import AcceptedElicitation
        from pydantic import BaseModel

        from pywry.mcp.agentic import scaffold_app

        class _Form(BaseModel):
            value: str = ""

        title_resp = AcceptedElicitation(data=_Form(value="Demo"))
        desc_resp = MagicMock()

        ctx = MagicMock()
        ctx.report_progress = AsyncMock()
        ctx.elicit = AsyncMock(side_effect=[title_resp, desc_resp])
        result = await scaffold_app(ctx)
        data = json.loads(result)
        assert data["status"] == "cancelled"

    async def test_full_flow(self) -> None:
        from mcp.server.elicitation import AcceptedElicitation
        from pydantic import BaseModel

        from pywry.mcp.agentic import WidgetPlan, scaffold_app

        class _Form(BaseModel):
            value: str = ""

        class _MultiForm(BaseModel):
            value: list[str] = []

        ctx = MagicMock()
        ctx.report_progress = AsyncMock()
        ctx.elicit = AsyncMock(
            side_effect=[
                AcceptedElicitation(data=_Form(value="Demo")),
                AcceptedElicitation(data=_Form(value="Test app")),
                AcceptedElicitation(data=_Form(value="native window")),
                AcceptedElicitation(data=_MultiForm(value=["Plotly (charts)", "AG-Grid (tables)"])),
                AcceptedElicitation(data=_Form(value="top")),
            ]
        )
        mock_plan = WidgetPlan(title="Demo", description="Test app", html_content="<p></p>")
        mock_sample = MagicMock()
        mock_sample.result = mock_plan
        ctx.sample = AsyncMock(return_value=mock_sample)
        result = await scaffold_app(ctx)
        data = json.loads(result)
        assert data["status"] == "ready"
        assert "collected" in data
        assert "include_plotly" in data["collected"]
        assert "include_aggrid" in data["collected"]

    async def test_libs_neither_defaults_off(self) -> None:
        from mcp.server.elicitation import AcceptedElicitation
        from pydantic import BaseModel

        from pywry.mcp.agentic import WidgetPlan, scaffold_app

        class _Form(BaseModel):
            value: str = ""

        ctx = MagicMock()
        ctx.report_progress = AsyncMock()
        ctx.elicit = AsyncMock(
            side_effect=[
                AcceptedElicitation(data=_Form(value="Demo")),
                AcceptedElicitation(data=_Form(value="d")),
                MagicMock(),  # display mode declined → defaults
                AcceptedElicitation(data=_Form(value="Neither")),
                MagicMock(),  # toolbar position declined → defaults
            ]
        )
        mock_plan = WidgetPlan(title="Demo", description="d", html_content="<p></p>")
        mock_sample = MagicMock()
        mock_sample.result = mock_plan
        ctx.sample = AsyncMock(return_value=mock_sample)
        result = await scaffold_app(ctx)
        data = json.loads(result)
        assert data["collected"]["include_plotly"] is False
        assert data["collected"]["include_aggrid"] is False
        assert data["collected"]["toolbar_position"] == "top"
