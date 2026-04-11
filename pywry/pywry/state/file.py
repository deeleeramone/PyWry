"""Filesystem-backed chart store.

Persists chart layouts and settings templates as JSON files under a
configurable base directory (default ``~/.config/pywry/tvchart``).

Directory layout::

    {base_path}/
        _index.json                    # layout metadata list
        settings_template.json         # custom settings template
        settings_default_id.txt        # "factory" or "custom"
        layouts/
            {layout_id}.json           # per-layout data
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

from pathlib import Path
from typing import Any

from .base import ChartStore


logger = logging.getLogger(__name__)

_MAX_LAYOUTS = 200
_SAFE_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")


def _sanitize_layout_id(layout_id: str) -> str:
    """Ensure the layout ID is safe for use as a filename."""
    sanitized = "".join(c for c in layout_id if c in _SAFE_ID_CHARS)
    if not sanitized:
        sanitized = "unnamed"
    return sanitized[:128]


class FileChartStore(ChartStore):
    """Filesystem-backed chart layout and settings store.

    Writes JSON files under *base_path*.  Thread-safe via
    ``asyncio.Lock``.

    Parameters
    ----------
    base_path : str or Path
        Root directory for chart storage.  ``~`` is expanded.
    """

    def __init__(self, base_path: str | Path = "~/.config/pywry/tvchart") -> None:
        self._base = Path(base_path).expanduser().resolve()
        self._layouts_dir = self._base / "layouts"
        self._lock = asyncio.Lock()
        self._ensure_dirs()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_dirs(self) -> None:
        self._base.mkdir(parents=True, exist_ok=True)
        self._layouts_dir.mkdir(parents=True, exist_ok=True)

    def _index_path(self) -> Path:
        return self._base / "_index.json"

    def _layout_path(self, layout_id: str) -> Path:
        return self._layouts_dir / f"{_sanitize_layout_id(layout_id)}.json"

    def _template_path(self) -> Path:
        return self._base / "settings_template.json"

    def _default_id_path(self) -> Path:
        return self._base / "settings_default_id.txt"

    def _read_index(self) -> list[dict[str, Any]]:
        path = self._index_path()
        if not path.exists():
            return []
        try:
            raw = path.read_text(encoding="utf-8")
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            logger.debug("Failed to read chart index at %s", path, exc_info=True)
            return []

    def _write_index(self, index: list[dict[str, Any]]) -> None:
        data = json.dumps(index, ensure_ascii=False)
        self._atomic_write(self._index_path(), data)

    def _atomic_write(self, path: Path, data: str) -> None:
        """Write *data* to *path* via a temporary file + rename."""
        tmp = path.with_suffix(".tmp")
        try:
            tmp.write_text(data, encoding="utf-8")
            tmp.replace(path)
        except OSError:
            # Fallback: direct write (Windows edge case with open handles)
            try:
                path.write_text(data, encoding="utf-8")
            except OSError:
                logger.warning("Failed to write %s", path, exc_info=True)
            finally:
                tmp.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Layout operations
    # ------------------------------------------------------------------

    async def save_layout(
        self,
        user_id: str,
        layout_id: str,
        name: str,
        data_json: str,
        *,
        summary: str = "",
    ) -> dict[str, Any]:
        """Save or update a chart layout."""
        safe_id = _sanitize_layout_id(layout_id)
        now = int(time.time() * 1000)

        entry: dict[str, Any] = {
            "id": safe_id,
            "name": name,
            "savedAt": now,
            "summary": summary,
        }

        async with self._lock:
            self._ensure_dirs()
            # Write layout data
            self._atomic_write(self._layout_path(safe_id), data_json)

            # Update index
            index = self._read_index()
            index = [e for e in index if e.get("id") != safe_id]
            index.insert(0, entry)
            index = index[:_MAX_LAYOUTS]
            self._write_index(index)

        return entry

    async def get_layout(self, user_id: str, layout_id: str) -> str | None:
        """Get layout data by ID."""
        path = self._layout_path(layout_id)
        async with self._lock:
            if not path.exists():
                return None
            try:
                return path.read_text(encoding="utf-8")
            except OSError:
                logger.debug("Failed to read layout %s", path, exc_info=True)
                return None

    async def list_layouts(self, user_id: str) -> list[dict[str, Any]]:
        """List all layout index entries."""
        async with self._lock:
            return self._read_index()

    async def delete_layout(self, user_id: str, layout_id: str) -> bool:
        """Delete a layout."""
        safe_id = _sanitize_layout_id(layout_id)
        async with self._lock:
            index = self._read_index()
            new_index = [e for e in index if e.get("id") != safe_id]
            if len(new_index) == len(index):
                return False
            self._write_index(new_index)
            path = self._layout_path(safe_id)
            path.unlink(missing_ok=True)
            return True

    async def rename_layout(self, user_id: str, layout_id: str, new_name: str) -> bool:
        """Rename a layout."""
        safe_id = _sanitize_layout_id(layout_id)
        async with self._lock:
            index = self._read_index()
            found = False
            for entry in index:
                if entry.get("id") == safe_id:
                    entry["name"] = new_name
                    entry["savedAt"] = int(time.time() * 1000)
                    found = True
                    break
            if not found:
                return False
            index.sort(key=lambda e: e.get("savedAt", 0), reverse=True)
            self._write_index(index)
            return True

    async def update_layout_meta(
        self,
        user_id: str,
        layout_id: str,
        *,
        name: str = "",
        summary: str = "",
    ) -> bool:
        """Update metadata for an existing layout index entry."""
        safe_id = _sanitize_layout_id(layout_id)
        async with self._lock:
            index = self._read_index()
            found = False
            for entry in index:
                if entry.get("id") == safe_id:
                    if name:
                        entry["name"] = name
                    if summary:
                        entry["summary"] = summary
                    found = True
                    break
            if not found:
                return False
            self._write_index(index)
            return True

    # ------------------------------------------------------------------
    # Settings template operations
    # ------------------------------------------------------------------

    async def save_settings_template(self, user_id: str, template_json: str) -> None:
        """Save a custom settings template."""
        async with self._lock:
            self._ensure_dirs()
            self._atomic_write(self._template_path(), template_json)

    async def get_settings_template(self, user_id: str) -> str | None:
        """Get the custom settings template."""
        async with self._lock:
            path = self._template_path()
            if not path.exists():
                return None
            try:
                return path.read_text(encoding="utf-8")
            except OSError:
                return None

    async def get_settings_default_id(self, user_id: str) -> str:
        """Get which settings template is active."""
        async with self._lock:
            path = self._default_id_path()
            if not path.exists():
                return "factory"
            try:
                val = path.read_text(encoding="utf-8").strip()
            except OSError:
                return "factory"
            else:
                return val if val in ("factory", "custom") else "factory"

    async def set_settings_default_id(self, user_id: str, template_id: str) -> None:
        """Set which settings template is active."""
        val = template_id if template_id in ("factory", "custom") else "factory"
        async with self._lock:
            self._ensure_dirs()
            self._atomic_write(self._default_id_path(), val)

    async def clear_settings_template(self, user_id: str) -> None:
        """Remove the custom settings template and reset to factory."""
        async with self._lock:
            self._template_path().unlink(missing_ok=True)
            self._atomic_write(self._default_id_path(), "factory")
