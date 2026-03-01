"""Utilities for installing PyWry bundled skills into vendor skill directories.

This module provides functions to copy PyWry's bundled skills into the
platform-specific directories used by AI coding tools such as Claude Code,
Cursor, VS Code Copilot, Gemini CLI, Goose, OpenCode, and Codex.

Skill directories follow the FastMCP SkillsDirectoryProvider convention:
each skill lives in a subdirectory containing a ``SKILL.md`` file.

Example usage::

    from pywry.mcp.install import install_skills

    # Install to a specific platform
    results = install_skills(targets=["claude"])

    # Install to all supported platforms
    results = install_skills(targets=["all"], overwrite=True)

    # Install to a custom directory
    results = install_skills(targets=["custom"], custom_dir="/path/to/skills")
"""

from __future__ import annotations

import shutil

from pathlib import Path


# Directory containing the bundled PyWry skills
SKILLS_SOURCE_DIR: Path = Path(__file__).parent / "skills"

# Mapping of vendor names to their skill root directories.
# Multiple paths can be listed; all will be written to.
VENDOR_DIRS: dict[str, list[Path]] = {
    "claude": [Path.home() / ".claude" / "skills"],
    "cursor": [Path.home() / ".cursor" / "skills"],
    "vscode": [Path.home() / ".copilot" / "skills"],
    "copilot": [Path.home() / ".copilot" / "skills"],
    "codex": [Path("/etc/codex/skills"), Path.home() / ".codex" / "skills"],
    "gemini": [Path.home() / ".gemini" / "skills"],
    "goose": [Path.home() / ".config" / "agents" / "skills"],
    "opencode": [Path.home() / ".config" / "opencode" / "skills"],
}

ALL_TARGETS: list[str] = sorted(VENDOR_DIRS.keys())


def _resolve_targets(targets: list[str] | None) -> dict[str, list[Path]]:
    """Resolve the *targets* list to a mapping of name → path list."""
    if targets is None or targets == ["all"]:
        return dict(VENDOR_DIRS)

    expanded: list[str] = []
    for t in targets:
        if t == "all":
            expanded.extend(ALL_TARGETS)
        else:
            expanded.append(t)

    unknown = set(expanded) - set(VENDOR_DIRS) - {"custom"}
    if unknown:
        raise ValueError(
            f"Unknown target(s): {', '.join(sorted(unknown))}. "
            f"Supported: {', '.join(ALL_TARGETS)} or 'all'."
        )
    return {t: VENDOR_DIRS[t] for t in expanded if t != "custom"}


def _install_one_skill(
    skill_name: str,
    dest_root: Path,
    *,
    overwrite: bool,
    dry_run: bool,
) -> str:
    """Copy a single skill directory into *dest_root*. Returns a status string."""
    src = SKILLS_SOURCE_DIR / skill_name
    if not src.exists():
        return f"error:source not found: {src}"

    dest = dest_root / skill_name

    if dry_run:
        return "dry_run"

    if dest.exists():
        if not overwrite:
            return "skipped"
        try:
            shutil.rmtree(dest)
        except OSError as exc:
            return f"error:{exc}"

    try:
        dest_root.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dest)
    except OSError as exc:
        return f"error:{exc}"
    return "installed"


def list_bundled_skills() -> list[str]:
    """Return the names of all bundled PyWry skills.

    Returns
    -------
    list[str]
        Skill directory names (i.e. each subdirectory of the bundled skills
        directory that contains a ``SKILL.md`` file).
    """
    return sorted(
        d.name for d in SKILLS_SOURCE_DIR.iterdir() if d.is_dir() and (d / "SKILL.md").exists()
    )


def install_skills(
    targets: list[str] | None = None,
    *,
    overwrite: bool = False,
    skill_names: list[str] | None = None,
    custom_dir: str | Path | None = None,
    dry_run: bool = False,
) -> dict[str, dict[str, str]]:
    """Copy PyWry bundled skills into vendor skill directories.

    Parameters
    ----------
    targets:
        List of vendor names to install into.  Use ``["all"]`` to install into
        every supported vendor directory.  Supported names:
        ``claude``, ``cursor``, ``vscode``, ``copilot``, ``codex``,
        ``gemini``, ``goose``, ``opencode``.  Defaults to ``["all"]``.
    overwrite:
        When ``True``, existing skill directories are removed and replaced.
        When ``False`` (default), existing skill directories are skipped.
    skill_names:
        Optional subset of skill names to install.  When ``None`` (default)
        all bundled skills are installed.
    custom_dir:
        Optional path to an additional target directory not in the vendor map.
        Providing this adds a ``"custom"`` entry to the results.
    dry_run:
        When ``True``, no files are written.  The return value describes what
        *would* happen.

    Returns
    -------
    dict[str, dict[str, str]]
        Nested mapping ``{target_name: {skill_name: status}}`` where *status*
        is one of ``"installed"``, ``"skipped"`` (already exists,
        ``overwrite=False``), ``"error:<message>"``, or ``"dry_run"``.

    Raises
    ------
    ValueError
        If an unknown vendor name is supplied.
    FileNotFoundError
        If the bundled skills source directory does not exist.
    """
    if not SKILLS_SOURCE_DIR.exists():
        raise FileNotFoundError(f"Bundled skills directory not found: {SKILLS_SOURCE_DIR}")

    resolved_targets = _resolve_targets(targets)

    # Handle custom directory
    if custom_dir is not None:
        resolved_targets["custom"] = [Path(custom_dir)]

    skills_to_install: list[str] = skill_names if skill_names else list_bundled_skills()

    results: dict[str, dict[str, str]] = {}
    for target_name, dest_dirs in resolved_targets.items():
        results[target_name] = {}
        for dest_root in dest_dirs:
            for skill_name in skills_to_install:
                key = skill_name if len(dest_dirs) == 1 else str(dest_root / skill_name)
                results[target_name][key] = _install_one_skill(
                    skill_name, dest_root, overwrite=overwrite, dry_run=dry_run
                )

    return results


def print_install_results(results: dict[str, dict[str, str]], *, verbose: bool = False) -> None:
    """Print a human-readable summary of :func:`install_skills` results.

    Parameters
    ----------
    results:
        Return value from :func:`install_skills`.
    verbose:
        When ``True``, print each skill's status individually.  When
        ``False``, print only per-target summary counts.
    """
    for target, skills in results.items():
        installed = [k for k, v in skills.items() if v == "installed"]
        skipped = [k for k, v in skills.items() if v == "skipped"]
        dry = [k for k, v in skills.items() if v == "dry_run"]
        errors = {k: v for k, v in skills.items() if v.startswith("error:")}

        parts: list[str] = []
        if installed:
            parts.append(f"{len(installed)} installed")
        if skipped:
            parts.append(f"{len(skipped)} skipped")
        if dry:
            parts.append(f"{len(dry)} (dry run)")
        if errors:
            parts.append(f"{len(errors)} failed")

        print(f"  [{target}] {', '.join(parts) or 'nothing to do'}")

        if verbose:
            for skill, status in sorted(skills.items()):
                print(f"    {skill}: {status}")
