"""Build PyWry distribution artifacts for Cowork and Claude Desktop.

Produces, in ``dist/``:

* ``pywry-cowork.plugin`` — Cowork plugin (zip of ``claude/plugins/pywry/``
  with ``.mcp.json`` and ``hooks/`` stripped, since Cowork's hosted sandbox
  cannot launch the local ``pywry`` CLI).
* ``pywry.mcpb`` — Claude Desktop extension (zip of
  ``claude/desktop-extension/`` with ``manifest.json`` at root).

Run with the project Python: ``python claude/scripts/build_distributions.py``.
Stdlib only — no external dependencies.
"""

from __future__ import annotations

import json
import shutil
import sys
import zipfile
from pathlib import Path

CLAUDE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = CLAUDE_DIR.parent
PLUGIN_SRC = CLAUDE_DIR / "plugins" / "pywry"
DESKTOP_SRC = CLAUDE_DIR / "desktop-extension"
MARKETPLACE_JSON = CLAUDE_DIR / ".claude-plugin" / "marketplace.json"
PLUGIN_JSON = PLUGIN_SRC / ".claude-plugin" / "plugin.json"
MANIFEST_JSON = DESKTOP_SRC / "manifest.json"
DIST = CLAUDE_DIR / "dist"

SIZE_LIMIT_BYTES = 50 * 1024 * 1024
EXCLUDE_DIR_NAMES = {
    "__pycache__",
    ".venv",
    "venv",
    ".pytest_cache",
    ".ruff_cache",
    ".ty_cache",
    "node_modules",
    ".git",
}
EXCLUDE_FILE_NAMES = {".DS_Store"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}

COWORK_DESCRIPTION_SUFFIX = (
    " (Cowork edition — skills + commands + agent only; "
    "for full MCP integration use the Claude Code plugin)"
)


def _is_excluded(path: Path) -> bool:
    if any(part in EXCLUDE_DIR_NAMES for part in path.parts):
        return True
    if path.name in EXCLUDE_FILE_NAMES:
        return True
    if path.suffix in EXCLUDE_SUFFIXES:
        return True
    return False


def _check_versions_in_sync() -> str:
    plugin = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
    marketplace = json.loads(MARKETPLACE_JSON.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))

    v_plugin = plugin["version"]
    v_manifest = manifest["version"]
    v_marketplace = next(
        (p["version"] for p in marketplace["plugins"] if p["name"] == "pywry"),
        None,
    )
    if v_marketplace is None:
        raise RuntimeError(
            f"'pywry' entry not found in {MARKETPLACE_JSON.relative_to(REPO_ROOT)}"
        )

    if not (v_plugin == v_marketplace == v_manifest):
        raise RuntimeError(
            "Version drift detected — all three must match before building:\n"
            f"  {PLUGIN_JSON.relative_to(REPO_ROOT)}: {v_plugin}\n"
            f"  {MARKETPLACE_JSON.relative_to(REPO_ROOT)}: {v_marketplace}\n"
            f"  {MANIFEST_JSON.relative_to(REPO_ROOT)}: {v_manifest}"
        )
    return v_plugin


def _zip_directory(src: Path, out: Path) -> None:
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(src.rglob("*")):
            if _is_excluded(path) or not path.is_file():
                continue
            arcname = path.relative_to(src).as_posix()
            zf.write(path, arcname)


def _build_cowork_plugin() -> Path:
    workdir = DIST / "_cowork_staging"
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)

    for src in PLUGIN_SRC.rglob("*"):
        if _is_excluded(src):
            continue
        rel = src.relative_to(PLUGIN_SRC)
        if rel == Path(".mcp.json"):
            continue
        if rel.parts and rel.parts[0] == "hooks":
            continue
        dst = workdir / rel
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    plugin_json_path = workdir / ".claude-plugin" / "plugin.json"
    plugin = json.loads(plugin_json_path.read_text(encoding="utf-8"))
    if not plugin["description"].endswith(COWORK_DESCRIPTION_SUFFIX):
        plugin["description"] += COWORK_DESCRIPTION_SUFFIX
    plugin_json_path.write_text(
        json.dumps(plugin, indent=2) + "\n", encoding="utf-8"
    )

    out = DIST / "pywry-cowork.plugin"
    _zip_directory(workdir, out)
    shutil.rmtree(workdir)
    return out


def _build_desktop_extension() -> Path:
    out = DIST / "pywry.mcpb"
    _zip_directory(DESKTOP_SRC, out)
    return out


def _summarize(path: Path) -> None:
    size = path.stat().st_size
    if size > SIZE_LIMIT_BYTES:
        raise RuntimeError(
            f"{path.name} is {size:,} bytes — exceeds the 50 MB limit"
        )
    with zipfile.ZipFile(path) as zf:
        files = zf.namelist()
    rel = path.relative_to(REPO_ROOT)
    print(f"  {rel} — {size:,} bytes, {len(files)} files")


def main() -> int:
    DIST.mkdir(exist_ok=True)
    version = _check_versions_in_sync()
    print(f"Building PyWry distributions at version {version}")

    cowork = _build_cowork_plugin()
    desktop = _build_desktop_extension()

    print("\nArtifacts:")
    _summarize(cowork)
    _summarize(desktop)
    return 0


if __name__ == "__main__":
    sys.exit(main())
