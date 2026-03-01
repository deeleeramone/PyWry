"""PyWry MCP Skills - On-demand guidance for agents.

Skills are loaded lazily when requested to minimize memory footprint.
Each skill is a standalone markdown file with context-specific guidance.

Available Skills
----------------
- native: Desktop window via PyWry/WRY/Tauri (Rust WebView)
- jupyter: Inline widgets in Jupyter notebook cells (iframe in cell output)
- iframe: Embedded widgets in external web pages
- deploy: Production multi-user SSE server
- css_selectors: Targeting elements for updates
- styling: Theme variables and CSS customization
- data_visualization: Charts, tables, live data patterns
- forms_and_inputs: User input collection and validation
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path


SKILLS_DIR = Path(__file__).parent

# Skill metadata (name, description) - guidance loaded on-demand
# ORDER MATTERS: component_reference MUST be first (most critical)
SKILL_METADATA: dict[str, dict[str, str]] = {
    "component_reference": {
        "name": "Component Reference - MANDATORY",
        "description": "⚠️ AUTHORITATIVE REFERENCE for ALL components and event signatures. READ THIS BEFORE CREATING ANY WIDGET.",
    },
    "interactive_buttons": {
        "name": "Interactive Buttons Pattern",
        "description": "CRITICAL: How to make buttons work automatically with auto-wired callbacks",
    },
    "autonomous_building": {
        "name": "Autonomous Application Building",
        "description": "Build complete PyWry apps from a description using plan_widget, build_app, export_project, and scaffold_app tools",
    },
    "native": {
        "name": "Native Window Mode",
        "description": "Desktop application via PyWry/WRY (Rust WebView) - NOT a browser, NOT Jupyter",
    },
    "jupyter": {
        "name": "Jupyter Notebook Mode",
        "description": "Inline widgets in notebook cell output via iframe - NOT native, NOT a browser tab",
    },
    "iframe": {
        "name": "iFrame Embed Mode",
        "description": "Widgets embedded in external web pages via iframe",
    },
    "deploy": {
        "name": "Production Deploy Mode",
        "description": "Multi-user SSE server for production deployments",
    },
    "css_selectors": {
        "name": "CSS Selectors",
        "description": "Targeting elements with selectors for set_content/set_style",
    },
    "styling": {
        "name": "Styling and Theming",
        "description": "CSS variables, theme colors, and visual customization",
    },
    "data_visualization": {
        "name": "Data Visualization",
        "description": "Charts, tables, and live data patterns",
    },
    "forms_and_inputs": {
        "name": "Forms and User Input",
        "description": "Building interactive forms with validation",
    },
    "modals": {
        "name": "Modals",
        "description": "Overlay dialogs for settings, confirmations, forms - with X close, Escape key, and reset behavior",
    },
}


@lru_cache(maxsize=16)
def load_skill(skill_name: str) -> str | None:
    """Load skill guidance from file (cached).

    Parameters
    ----------
    skill_name : str
        Name of the skill to load.

    Returns
    -------
    str or None
        Skill guidance markdown or None if not found.
    """
    skill_file = SKILLS_DIR / skill_name / "SKILL.md"
    if skill_file.exists():
        return skill_file.read_text(encoding="utf-8")
    return None


def get_skill(skill_name: str) -> dict[str, str] | None:
    """Get skill with metadata and guidance.

    Parameters
    ----------
    skill_name : str
        Name of the skill.

    Returns
    -------
    dict or None
        Dict with name, description, and guidance or None if not found.
    """
    if skill_name not in SKILL_METADATA:
        return None

    guidance = load_skill(skill_name)
    if guidance is None:
        return None

    return {
        "name": SKILL_METADATA[skill_name]["name"],
        "description": SKILL_METADATA[skill_name]["description"],
        "guidance": guidance,
    }


def list_skills() -> list[dict[str, str]]:
    """List all available skills with metadata.

    Returns
    -------
    list of dict
        List of skill metadata dicts (without guidance).
    """
    return [{"id": skill_id, **metadata} for skill_id, metadata in SKILL_METADATA.items()]


def get_all_skills() -> dict[str, dict[str, str]]:
    """Get all skills with full guidance (for backward compatibility).

    Returns
    -------
    dict
        Dict mapping skill_id to full skill data.
    """
    result: dict[str, dict[str, str]] = {}
    for skill_id in SKILL_METADATA:
        skill = get_skill(skill_id)
        if skill is not None:
            result[skill_id] = skill
    return result
