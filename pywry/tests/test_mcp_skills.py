"""Tests for ``pywry.mcp.skills`` (the skill metadata + loader).

Covers:
- ``list_skills`` enumerates SKILL_METADATA entries.
- ``get_skill`` returns metadata + guidance for a known skill, ``None``
  for an unknown one, ``None`` when load returns ``None``.
- ``load_skill`` is lru-cached and reads from disk; missing files
  return ``None``.
- ``get_all_skills`` returns the full mapping with guidance.
- Required ordering: ``component_reference`` comes first.
- ``autonomous_building`` skill ships with metadata + loadable content.
"""

from __future__ import annotations


class TestListSkills:
    def test_returns_non_empty_list(self) -> None:
        from pywry.mcp.skills import list_skills

        skills = list_skills()
        assert isinstance(skills, list)
        assert len(skills) > 0

    def test_each_has_required_keys(self) -> None:
        from pywry.mcp.skills import list_skills

        for skill in list_skills():
            assert "id" in skill
            assert "name" in skill
            assert "description" in skill


class TestGetSkill:
    def test_returns_metadata_for_known_skill(self) -> None:
        from pywry.mcp.skills import get_skill

        skill = get_skill("native")
        assert skill is not None
        assert "name" in skill
        assert "description" in skill
        assert "guidance" in skill
        assert len(skill["guidance"]) > 0

    def test_returns_none_for_unknown_skill(self) -> None:
        from pywry.mcp.skills import get_skill

        assert get_skill("nonexistent_skill_xyz") is None

    def test_returns_none_when_load_returns_none(self, monkeypatch) -> None:
        """Known metadata + empty load → no skill payload."""
        from pywry.mcp import skills

        monkeypatch.setattr(skills, "load_skill", lambda _name: None)
        assert skills.get_skill("native") is None


class TestLoadSkill:
    def test_uses_lru_cache(self) -> None:
        from pywry.mcp.skills import load_skill

        a = load_skill("native")
        b = load_skill("native")
        assert a is b

    def test_returns_none_for_missing_file(self) -> None:
        from pywry.mcp.skills import load_skill

        load_skill.cache_clear()
        assert load_skill("nonexistent_xyz_unique_test_name") is None


class TestSkillMetadata:
    def test_component_reference_is_first(self) -> None:
        from pywry.mcp.skills import SKILL_METADATA

        keys = list(SKILL_METADATA.keys())
        assert keys[0] == "component_reference"

    def test_get_all_skills_includes_guidance(self) -> None:
        from pywry.mcp.skills import get_all_skills

        all_skills = get_all_skills()
        assert isinstance(all_skills, dict)
        assert "native" in all_skills
        assert "guidance" in all_skills["native"]


class TestAutonomousBuildingSkill:
    def test_listed_in_metadata(self) -> None:
        from pywry.mcp.skills import SKILL_METADATA

        assert "autonomous_building" in SKILL_METADATA

    def test_skill_md_file_exists(self) -> None:
        from pywry.mcp.skills import SKILLS_DIR

        assert (SKILLS_DIR / "autonomous_building" / "SKILL.md").exists()

    def test_load_returns_meaningful_content(self) -> None:
        from pywry.mcp.skills import load_skill

        content = load_skill("autonomous_building")
        assert content is not None
        assert len(content) > 100
        assert "build_app" in content
