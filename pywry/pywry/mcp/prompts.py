"""MCP Prompts for PyWry skills.

This module handles prompt listing and retrieval for agent skills.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pywry.mcp.skills import get_skill, list_skills


if TYPE_CHECKING:
    from mcp.types import GetPromptResult, Prompt


def get_prompts() -> list[Prompt]:
    """Return MCP prompts for agent skills.

    Returns
    -------
    list of Prompt
        All available skill prompts.
    """
    from mcp.types import Prompt

    return [
        Prompt(
            name=f"skill:{skill_info['id']}",
            description=skill_info["description"],
            arguments=[],
        )
        for skill_info in list_skills()
    ]


def get_prompt_content(name: str) -> GetPromptResult | None:
    """Get the content for a specific prompt.

    Parameters
    ----------
    name : str
        Prompt name (e.g., 'skill:native').

    Returns
    -------
    GetPromptResult or None
        Prompt content or None if not found.
    """
    from mcp.types import GetPromptResult, PromptMessage, TextContent

    # Extract skill key from "skill:key" format
    if name.startswith("skill:"):
        key = name[6:]
        skill = get_skill(key)
        if skill:
            return GetPromptResult(
                description=skill["description"],
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(type="text", text=skill["guidance"]),
                    )
                ],
            )
    return None
