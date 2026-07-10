"""Tests for the FileChartStore filesystem-backed chart store."""

from __future__ import annotations

import json

from pathlib import Path
from unittest.mock import patch

import pytest

from pywry.state.file import FileChartStore, _sanitize_layout_id


# --- Helper tests ---


class TestSanitizeLayoutId:
    """Tests for the _sanitize_layout_id helper."""

    def test_safe_id_passes_through(self) -> None:
        assert _sanitize_layout_id("layout_123") == "layout_123"

    def test_id_with_dashes(self) -> None:
        assert _sanitize_layout_id("layout-abc-123") == "layout-abc-123"

    def test_id_strips_unsafe_chars(self) -> None:
        assert _sanitize_layout_id("layout/../etc") == "layoutetc"

    def test_id_strips_path_separator(self) -> None:
        assert _sanitize_layout_id("a\\b/c") == "abc"

    def test_empty_after_strip_uses_default(self) -> None:
        assert _sanitize_layout_id("///") == "unnamed"

    def test_empty_input_uses_default(self) -> None:
        assert _sanitize_layout_id("") == "unnamed"

    def test_truncates_to_128_chars(self) -> None:
        long_id = "a" * 200
        result = _sanitize_layout_id(long_id)
        assert len(result) == 128
        assert result == "a" * 128

    def test_special_chars_removed(self) -> None:
        assert _sanitize_layout_id("layout!@#$%^&*()") == "layout"


# --- FileChartStore tests ---


class TestFileChartStore:
    """Tests for FileChartStore."""

    @pytest.fixture
    def store(self, tmp_path: Path) -> FileChartStore:
        return FileChartStore(base_path=tmp_path / "chart")

    async def test_initialization_creates_directories(self, tmp_path: Path) -> None:
        FileChartStore(base_path=tmp_path / "fresh")
        assert (tmp_path / "fresh").exists()
        assert (tmp_path / "fresh" / "layouts").exists()

    async def test_initialization_expands_user_path(self) -> None:
        # Just verify it doesn't crash with ~/ paths
        store = FileChartStore(base_path="~/.pywry-test-temp/foo")
        assert "~" not in str(store._base)

    async def test_save_and_get_layout(self, store: FileChartStore) -> None:
        entry = await store.save_layout(
            user_id="default",
            layout_id="layout1",
            name="My Layout",
            data_json='{"foo": "bar"}',
            summary="A test layout",
        )
        assert entry["id"] == "layout1"
        assert entry["name"] == "My Layout"
        assert entry["summary"] == "A test layout"
        assert entry["savedAt"] > 0

        data = await store.get_layout("default", "layout1")
        assert data == '{"foo": "bar"}'

    async def test_get_layout_nonexistent(self, store: FileChartStore) -> None:
        assert await store.get_layout("default", "nonexistent") is None

    async def test_list_layouts_empty(self, store: FileChartStore) -> None:
        assert await store.list_layouts("default") == []

    async def test_list_layouts_returns_in_order(self, store: FileChartStore) -> None:
        await store.save_layout("default", "l1", "First", "{}")
        await store.save_layout("default", "l2", "Second", "{}")
        layouts = await store.list_layouts("default")
        # Most recent first
        assert layouts[0]["id"] == "l2"
        assert layouts[1]["id"] == "l1"

    async def test_save_layout_replaces_existing(self, store: FileChartStore) -> None:
        await store.save_layout("default", "l1", "Old Name", '{"v": 1}')
        await store.save_layout("default", "l1", "New Name", '{"v": 2}')
        layouts = await store.list_layouts("default")
        assert len(layouts) == 1
        assert layouts[0]["name"] == "New Name"
        data = await store.get_layout("default", "l1")
        assert data == '{"v": 2}'

    async def test_save_layout_caps_index_size(self, store: FileChartStore) -> None:
        # Patch _MAX_LAYOUTS to a smaller value for the test
        with patch("pywry.state.file._MAX_LAYOUTS", 3):
            for i in range(10):
                await store.save_layout("default", f"l{i}", f"Layout {i}", "{}")
            layouts = await store.list_layouts("default")
            assert len(layouts) == 3

    async def test_delete_layout(self, store: FileChartStore) -> None:
        await store.save_layout("default", "l1", "First", "{}")
        deleted = await store.delete_layout("default", "l1")
        assert deleted is True
        assert await store.get_layout("default", "l1") is None
        assert await store.list_layouts("default") == []

    async def test_delete_layout_nonexistent(self, store: FileChartStore) -> None:
        deleted = await store.delete_layout("default", "nonexistent")
        assert deleted is False

    async def test_rename_layout(self, store: FileChartStore) -> None:
        await store.save_layout("default", "l1", "Original", "{}")
        renamed = await store.rename_layout("default", "l1", "Renamed")
        assert renamed is True
        layouts = await store.list_layouts("default")
        assert layouts[0]["name"] == "Renamed"

    async def test_rename_layout_nonexistent(self, store: FileChartStore) -> None:
        renamed = await store.rename_layout("default", "missing", "X")
        assert renamed is False

    async def test_rename_resorts_index(self, store: FileChartStore) -> None:
        await store.save_layout("default", "l1", "First", "{}")
        await store.save_layout("default", "l2", "Second", "{}")
        await store.rename_layout("default", "l1", "First Renamed")
        layouts = await store.list_layouts("default")
        # Rename updates savedAt and re-sorts; verify both entries present
        # and the renamed entry has its new name
        ids = {entry["id"] for entry in layouts}
        assert ids == {"l1", "l2"}
        renamed = next(e for e in layouts if e["id"] == "l1")
        assert renamed["name"] == "First Renamed"
        # l1's savedAt should be >= l2's (rename bumps timestamp)
        l1_entry = next(e for e in layouts if e["id"] == "l1")
        l2_entry = next(e for e in layouts if e["id"] == "l2")
        assert l1_entry["savedAt"] >= l2_entry["savedAt"]

    async def test_update_layout_meta_name_only(self, store: FileChartStore) -> None:
        await store.save_layout("default", "l1", "Original", "{}", summary="orig summary")
        updated = await store.update_layout_meta("default", "l1", name="New Name")
        assert updated is True
        layouts = await store.list_layouts("default")
        assert layouts[0]["name"] == "New Name"
        assert layouts[0]["summary"] == "orig summary"  # unchanged

    async def test_update_layout_meta_summary_only(self, store: FileChartStore) -> None:
        await store.save_layout("default", "l1", "Original", "{}", summary="orig")
        updated = await store.update_layout_meta("default", "l1", summary="new summary")
        assert updated is True
        layouts = await store.list_layouts("default")
        assert layouts[0]["summary"] == "new summary"
        assert layouts[0]["name"] == "Original"

    async def test_update_layout_meta_both(self, store: FileChartStore) -> None:
        await store.save_layout("default", "l1", "Old", "{}")
        updated = await store.update_layout_meta("default", "l1", name="New", summary="New summary")
        assert updated is True
        layouts = await store.list_layouts("default")
        assert layouts[0]["name"] == "New"
        assert layouts[0]["summary"] == "New summary"

    async def test_update_layout_meta_nonexistent(self, store: FileChartStore) -> None:
        updated = await store.update_layout_meta("default", "missing", name="X", summary="Y")
        assert updated is False

    async def test_update_layout_meta_no_changes(self, store: FileChartStore) -> None:
        await store.save_layout("default", "l1", "Original", "{}", summary="orig")
        updated = await store.update_layout_meta("default", "l1")
        assert updated is True

    async def test_save_and_get_settings_template(self, store: FileChartStore) -> None:
        await store.save_settings_template("default", '{"tpl": "data"}')
        result = await store.get_settings_template("default")
        assert result == '{"tpl": "data"}'

    async def test_get_settings_template_missing(self, store: FileChartStore) -> None:
        result = await store.get_settings_template("default")
        assert result is None

    async def test_settings_default_id_default_factory(self, store: FileChartStore) -> None:
        result = await store.get_settings_default_id("default")
        assert result == "factory"

    async def test_set_and_get_settings_default_id(self, store: FileChartStore) -> None:
        await store.set_settings_default_id("default", "custom")
        result = await store.get_settings_default_id("default")
        assert result == "custom"

    async def test_set_settings_default_id_invalid_resets_to_factory(
        self, store: FileChartStore
    ) -> None:
        await store.set_settings_default_id("default", "bogus")
        result = await store.get_settings_default_id("default")
        assert result == "factory"

    async def test_clear_settings_template(self, store: FileChartStore) -> None:
        await store.save_settings_template("default", '{"x": 1}')
        await store.set_settings_default_id("default", "custom")
        await store.clear_settings_template("default")
        assert await store.get_settings_template("default") is None
        assert await store.get_settings_default_id("default") == "factory"

    async def test_clear_settings_template_no_existing(self, store: FileChartStore) -> None:
        # No prior template
        await store.clear_settings_template("default")
        assert await store.get_settings_template("default") is None

    async def test_layout_id_sanitized_in_path(self, store: FileChartStore) -> None:
        # Special chars should be stripped
        await store.save_layout("default", "../bad/id", "test", "{}")
        # The layout should still be accessible by the original ID (sanitized internally)
        result = await store.get_layout("default", "../bad/id")
        assert result == "{}"

    async def test_corrupted_index_returns_empty(
        self, store: FileChartStore, tmp_path: Path
    ) -> None:
        # Manually write an invalid JSON to index
        index_path = store._base / "_index.json"
        index_path.write_text("not valid json", encoding="utf-8")
        layouts = await store.list_layouts("default")
        assert layouts == []

    async def test_index_with_non_list_returns_empty(self, store: FileChartStore) -> None:
        index_path = store._base / "_index.json"
        index_path.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
        layouts = await store.list_layouts("default")
        assert layouts == []

    async def test_get_layout_unreadable(
        self, store: FileChartStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Save layout, then patch read_text to raise OSError
        await store.save_layout("default", "l1", "x", "{}")

        def raise_oserror(*args, **kwargs):
            raise OSError("simulated read error")

        monkeypatch.setattr(Path, "read_text", raise_oserror)
        result = await store.get_layout("default", "l1")
        assert result is None

    async def test_get_settings_template_unreadable(
        self, store: FileChartStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        await store.save_settings_template("default", "{}")

        def raise_oserror(*args, **kwargs):
            raise OSError("simulated read error")

        monkeypatch.setattr(Path, "read_text", raise_oserror)
        result = await store.get_settings_template("default")
        assert result is None

    async def test_get_settings_default_id_unreadable(
        self, store: FileChartStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        await store.set_settings_default_id("default", "custom")

        def raise_oserror(*args, **kwargs):
            raise OSError("simulated read error")

        monkeypatch.setattr(Path, "read_text", raise_oserror)
        result = await store.get_settings_default_id("default")
        assert result == "factory"

    async def test_atomic_write_oserror_fallback(
        self, store: FileChartStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test fallback path in _atomic_write when tmp.write_text raises."""
        original_write = Path.write_text
        call_count = [0]

        def maybe_raise(self, *args, **kwargs):
            call_count[0] += 1
            # Raise on the first call (tmp file write), succeed on second (direct)
            if call_count[0] == 1 and ".tmp" in str(self):
                raise OSError("simulated tmp write error")
            return original_write(self, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", maybe_raise)

        # This should still complete via the fallback path
        store._atomic_write(store._base / "test_file.json", '{"x": 1}')
        # Verify it wrote via fallback
        assert (store._base / "test_file.json").exists()

    async def test_atomic_write_both_writes_fail(
        self, store: FileChartStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test the case where both tmp and direct write fail."""

        def raise_oserror(*args, **kwargs):
            raise OSError("simulated write error")

        monkeypatch.setattr(Path, "write_text", raise_oserror)

        # This should not crash but log warning
        store._atomic_write(store._base / "test_file.json", '{"x": 1}')
        # File should not exist since both writes failed
        assert not (store._base / "test_file.json").exists()
