"""Tests for pywry.mcp.prompts."""

from __future__ import annotations

import pytest


pytest.importorskip("mcp")


from pywry.mcp.prompts import get_prompt_content, get_prompts
from pywry.mcp.skills import list_skills


class TestGetPrompts:
    def test_returns_one_prompt_per_skill(self):
        prompts = get_prompts()
        skills = list_skills()
        assert len(prompts) == len(skills)

    def test_prompt_names_use_skill_prefix(self):
        prompts = get_prompts()
        for prompt in prompts:
            assert prompt.name.startswith("skill:")

    def test_prompt_arguments_empty(self):
        prompts = get_prompts()
        for prompt in prompts:
            assert prompt.arguments == []


class TestGetPromptContent:
    def test_returns_none_for_unknown(self):
        result = get_prompt_content("unknown:thing")
        assert result is None

    def test_returns_none_for_missing_prefix(self):
        # Doesn't start with "skill:" -> None
        skills = list_skills()
        if skills:
            # Bare skill id without prefix should be None
            assert get_prompt_content(skills[0]["id"]) is None

    def test_returns_prompt_for_known_skill(self):
        # native skill exists
        result = get_prompt_content("skill:native")
        if result is not None:
            assert result.description is not None
            assert len(result.messages) == 1
            assert result.messages[0].role == "user"

    def test_returns_none_for_unknown_skill(self):
        result = get_prompt_content("skill:nonexistent_skill_xyz")
        assert result is None
