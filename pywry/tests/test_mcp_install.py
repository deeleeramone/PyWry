"""Tests for ``pywry.mcp.install``.

Covers:
- ``list_bundled_skills`` enumerates skills from disk.
- ``VENDOR_DIRS`` mapping and ``ALL_TARGETS`` ordering.
- ``install_skills`` — custom dir, vendor targets, overwrite/skip, dry run,
  error reporting on missing sources or filesystem failures.
- ``print_install_results`` output formatting.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest


class TestListBundledSkills:
    def test_returns_non_empty_list(self) -> None:
        from pywry.mcp.install import list_bundled_skills

        skills = list_bundled_skills()
        assert isinstance(skills, list)
        assert len(skills) > 0

    def test_returns_sorted(self) -> None:
        from pywry.mcp.install import list_bundled_skills

        skills = list_bundled_skills()
        assert skills == sorted(skills)

    def test_includes_native(self) -> None:
        from pywry.mcp.install import list_bundled_skills

        assert "native" in list_bundled_skills()


class TestVendorDirs:
    def test_expected_keys_present(self) -> None:
        from pywry.mcp.install import VENDOR_DIRS

        expected = {
            "claude",
            "cursor",
            "vscode",
            "copilot",
            "codex",
            "gemini",
            "goose",
            "opencode",
        }
        assert expected <= set(VENDOR_DIRS.keys())

    def test_all_targets_sorted(self) -> None:
        from pywry.mcp.install import ALL_TARGETS

        assert sorted(ALL_TARGETS) == ALL_TARGETS


class TestInstallSkills:
    def test_dry_run_writes_nothing(self, tmp_path: Any) -> None:
        from pywry.mcp.install import install_skills

        results = install_skills(
            targets=[],
            overwrite=False,
            custom_dir=tmp_path / "skills",
            dry_run=True,
        )
        assert not (tmp_path / "skills").exists()
        assert "custom" in results
        for status in results["custom"].values():
            assert status == "dry_run"

    def test_install_to_custom_dir(self, tmp_path: Any) -> None:
        from pywry.mcp.install import install_skills, list_bundled_skills

        custom_target = tmp_path / "skills"
        results = install_skills(targets=[], overwrite=False, custom_dir=custom_target)

        assert "custom" in results
        installed = [v for v in results["custom"].values() if v == "installed"]
        assert len(installed) > 0

        for skill_name in list_bundled_skills():
            assert (custom_target / skill_name / "SKILL.md").exists()

    def test_skip_existing_when_no_overwrite(self, tmp_path: Any) -> None:
        from pywry.mcp.install import install_skills

        custom_target = tmp_path / "skills"
        install_skills(targets=[], custom_dir=custom_target)
        sentinel = custom_target / "native" / "sentinel.txt"
        sentinel.write_text("original", encoding="utf-8")

        results = install_skills(targets=[], custom_dir=custom_target, overwrite=False)
        assert results["custom"].get("native") == "skipped"
        assert sentinel.exists()

    def test_overwrite_replaces_existing(self, tmp_path: Any) -> None:
        from pywry.mcp.install import install_skills

        custom_target = tmp_path / "skills"
        install_skills(targets=[], custom_dir=custom_target)
        sentinel = custom_target / "native" / "sentinel.txt"
        sentinel.write_text("original", encoding="utf-8")

        results = install_skills(targets=[], custom_dir=custom_target, overwrite=True)
        assert results["custom"].get("native") == "installed"
        assert not sentinel.exists()

    def test_unknown_target_raises(self) -> None:
        from pywry.mcp.install import install_skills

        with pytest.raises(ValueError, match="Unknown target"):
            install_skills(targets=["nonexistent_vendor_xyz"])

    def test_subset_via_skill_names(self, tmp_path: Any) -> None:
        from pywry.mcp.install import install_skills, list_bundled_skills

        custom_target = tmp_path / "skills"
        results = install_skills(targets=[], custom_dir=custom_target, skill_names=["native"])
        assert results["custom"].get("native") == "installed"
        assert (custom_target / "native" / "SKILL.md").exists()
        for skill in [s for s in list_bundled_skills() if s != "native"]:
            assert not (custom_target / skill).exists()

    def test_all_keyword_expands(self) -> None:
        from pywry.mcp.install import ALL_TARGETS, install_skills

        results = install_skills(targets=["all"], dry_run=True)
        assert set(results.keys()) == set(ALL_TARGETS)

    def test_specific_vendor_via_dir_patch(self, tmp_path: Any) -> None:
        from pywry.mcp.install import install_skills

        with patch.object(
            __import__("pywry.mcp.install", fromlist=["VENDOR_DIRS"]),
            "VENDOR_DIRS",
            {"claude": [tmp_path / "claude_skills"]},
        ):
            results = install_skills(targets=["claude"], dry_run=True)
        assert "claude" in results

    def test_source_dir_missing_raises(self, monkeypatch, tmp_path: Any) -> None:
        from pywry.mcp import install

        monkeypatch.setattr(install, "SKILLS_SOURCE_DIR", tmp_path / "nope")
        with pytest.raises(FileNotFoundError):
            install.install_skills()

    def test_skill_source_missing_reports_error(self, tmp_path: Any) -> None:
        from pywry.mcp.install import install_skills

        results = install_skills(
            targets=[],
            custom_dir=tmp_path / "skills",
            skill_names=["nonexistent_skill_xyz"],
        )
        assert "custom" in results
        for status in results["custom"].values():
            assert status.startswith("error:")

    def test_overwrite_rmtree_failure_reports_error(self, tmp_path: Any, monkeypatch) -> None:
        from pywry.mcp import install

        custom_target = tmp_path / "skills"
        install.install_skills(targets=[], custom_dir=custom_target)

        def fake_rmtree(_path):
            raise OSError("permission denied")

        monkeypatch.setattr(install.shutil, "rmtree", fake_rmtree)
        results = install.install_skills(
            targets=[],
            custom_dir=custom_target,
            overwrite=True,
            skill_names=["native"],
        )
        statuses = list(results["custom"].values())
        assert any(s.startswith("error:") for s in statuses)

    def test_copytree_failure_reports_error(self, tmp_path: Any, monkeypatch) -> None:
        from pywry.mcp import install

        def fake_copytree(_src, _dst):
            raise OSError("copy failed")

        monkeypatch.setattr(install.shutil, "copytree", fake_copytree)
        results = install.install_skills(
            targets=[],
            custom_dir=tmp_path / "skills",
            skill_names=["native"],
        )
        statuses = list(results["custom"].values())
        assert any(s.startswith("error:") for s in statuses)

    def test_multiple_paths_per_target(self, tmp_path: Any) -> None:
        from pywry.mcp import install

        with patch.dict(
            install.VENDOR_DIRS,
            {"twin": [tmp_path / "a", tmp_path / "b"]},
            clear=False,
        ):
            try:
                install.ALL_TARGETS.append("twin")
                results = install.install_skills(targets=["twin"], dry_run=True)
            finally:
                install.ALL_TARGETS.remove("twin")

        keys = list(results["twin"].keys())
        assert any("a" in k for k in keys)
        assert any("b" in k for k in keys)

    def test_mixed_all_and_specific_dedupes(self, tmp_path: Any) -> None:
        from pywry.mcp.install import ALL_TARGETS, install_skills

        results = install_skills(targets=["all", "claude"], dry_run=True)
        assert set(results.keys()) == set(ALL_TARGETS)


class TestPrintInstallResults:
    def test_verbose_summarises_each_status(self, capsys) -> None:
        from pywry.mcp.install import print_install_results

        results = {
            "claude": {
                "native": "installed",
                "css_selectors": "skipped",
                "events": "dry_run",
                "modals": "error:no source",
            }
        }
        print_install_results(results, verbose=True)
        out = capsys.readouterr().out
        assert "1 installed" in out
        assert "1 skipped" in out
        assert "1 (dry run)" in out
        assert "1 failed" in out
        assert "native: installed" in out

    def test_empty_results_says_nothing_to_do(self, capsys) -> None:
        from pywry.mcp.install import print_install_results

        print_install_results({"claude": {}})
        assert "nothing to do" in capsys.readouterr().out
