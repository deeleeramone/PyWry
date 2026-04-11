"""Tests for the ChartStore persistence system.

Covers FileChartStore, MemoryChartStore, factory wiring, preload pipeline,
event-handler routing, and JS server backend contract.
"""

from __future__ import annotations

import asyncio
import json

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from pywry.state.file import FileChartStore, _sanitize_layout_id
from pywry.state.memory import MemoryChartStore
from pywry.tvchart.mixin import (
    TVChartStateMixin,
    _chart_store_save_layout,
    _chart_store_sync_index,
)


if TYPE_CHECKING:
    from pathlib import Path


# =========================================================================
# Helpers
# =========================================================================

USER = "default"


class _FakeRunAsync:
    """Synchronous run_async replacement for tests."""

    def __call__(self, coro: Any, *, timeout: float = 10.0) -> Any:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


_run_async = _FakeRunAsync()


class _MockEmitterWithOn(TVChartStateMixin):
    """Mock widget that captures both emits and event registrations."""

    def __init__(self) -> None:
        self._emitted: list[tuple[str, Any]] = []
        self._handlers: dict[str, list] = {}

    def emit(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        self._emitted.append((event_type, data))

    def on(self, event_type: str, handler: Any, **kwargs: Any) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def fire(self, event_type: str, data: dict[str, Any]) -> None:
        """Simulate receiving an event from JS."""
        for handler in self._handlers.get(event_type, []):
            handler(data)


# =========================================================================
# _sanitize_layout_id
# =========================================================================


class TestSanitizeLayoutId:
    """Tests for the layout ID sanitizer."""

    def test_alphanumeric_passthrough(self) -> None:
        assert _sanitize_layout_id("my-layout_01") == "my-layout_01"

    def test_strips_unsafe_chars(self) -> None:
        assert _sanitize_layout_id("layout/../../etc/passwd") == "layoutetcpasswd"

    def test_empty_becomes_unnamed(self) -> None:
        assert _sanitize_layout_id("") == "unnamed"

    def test_all_unsafe_becomes_unnamed(self) -> None:
        assert _sanitize_layout_id("///...") == "unnamed"

    def test_truncates_to_128(self) -> None:
        long_id = "a" * 300
        assert len(_sanitize_layout_id(long_id)) == 128

    def test_unicode_stripped(self) -> None:
        assert _sanitize_layout_id("café-résumé") == "caf-rsum"


# =========================================================================
# MemoryChartStore
# =========================================================================


class TestMemoryChartStore:
    """Tests for the in-memory chart store."""

    @pytest.fixture
    def store(self) -> MemoryChartStore:
        return MemoryChartStore()

    async def test_save_and_get_layout(self, store: MemoryChartStore) -> None:
        meta = await store.save_layout(USER, "L1", "Layout One", '{"data":"A"}')
        assert meta["id"] == "L1"
        assert meta["name"] == "Layout One"
        assert meta["savedAt"] > 0

        data = await store.get_layout(USER, "L1")
        assert data == '{"data":"A"}'

    async def test_get_nonexistent_layout_returns_none(self, store: MemoryChartStore) -> None:
        assert await store.get_layout(USER, "missing") is None

    async def test_list_layouts_ordering(self, store: MemoryChartStore) -> None:
        await store.save_layout(USER, "A", "First", "{}")
        await store.save_layout(USER, "B", "Second", "{}")
        layouts = await store.list_layouts(USER)
        assert len(layouts) == 2
        # Most recent first
        assert layouts[0]["id"] == "B"
        assert layouts[1]["id"] == "A"

    async def test_save_layout_updates_existing(self, store: MemoryChartStore) -> None:
        await store.save_layout(USER, "L1", "Old", '{"v":1}')
        await store.save_layout(USER, "L1", "New", '{"v":2}')
        layouts = await store.list_layouts(USER)
        assert len(layouts) == 1
        assert layouts[0]["name"] == "New"
        data = await store.get_layout(USER, "L1")
        assert data == '{"v":2}'

    async def test_delete_layout(self, store: MemoryChartStore) -> None:
        await store.save_layout(USER, "L1", "Name", "{}")
        assert await store.delete_layout(USER, "L1") is True
        assert await store.get_layout(USER, "L1") is None
        assert await store.list_layouts(USER) == []

    async def test_delete_nonexistent_returns_false(self, store: MemoryChartStore) -> None:
        assert await store.delete_layout(USER, "missing") is False

    async def test_rename_layout(self, store: MemoryChartStore) -> None:
        await store.save_layout(USER, "L1", "Old", "{}")
        assert await store.rename_layout(USER, "L1", "New") is True
        layouts = await store.list_layouts(USER)
        assert layouts[0]["name"] == "New"

    async def test_rename_nonexistent_returns_false(self, store: MemoryChartStore) -> None:
        assert await store.rename_layout(USER, "missing", "New") is False

    async def test_max_layouts_cap(self, store: MemoryChartStore) -> None:
        for i in range(210):
            await store.save_layout(USER, f"L{i}", f"Layout {i}", "{}")
        layouts = await store.list_layouts(USER)
        assert len(layouts) == 200

    async def test_settings_template_roundtrip(self, store: MemoryChartStore) -> None:
        assert await store.get_settings_template(USER) is None
        await store.save_settings_template(USER, '{"color":"red"}')
        assert await store.get_settings_template(USER) == '{"color":"red"}'

    async def test_settings_default_id_lifecycle(self, store: MemoryChartStore) -> None:
        assert await store.get_settings_default_id(USER) == "factory"
        await store.set_settings_default_id(USER, "custom")
        assert await store.get_settings_default_id(USER) == "custom"

    async def test_settings_default_id_rejects_invalid(self, store: MemoryChartStore) -> None:
        await store.set_settings_default_id(USER, "bogus")
        assert await store.get_settings_default_id(USER) == "factory"

    async def test_clear_settings_template(self, store: MemoryChartStore) -> None:
        await store.save_settings_template(USER, '{"x":1}')
        await store.set_settings_default_id(USER, "custom")
        await store.clear_settings_template(USER)
        assert await store.get_settings_template(USER) is None
        assert await store.get_settings_default_id(USER) == "factory"


# =========================================================================
# FileChartStore
# =========================================================================


class TestFileChartStore:
    """Tests for the filesystem-backed chart store."""

    @pytest.fixture
    def store(self, tmp_path: Path) -> FileChartStore:
        return FileChartStore(base_path=tmp_path / "tvchart")

    @pytest.fixture
    def base(self, tmp_path: Path) -> Path:
        return tmp_path / "tvchart"

    async def test_creates_directory_structure(self, store: FileChartStore, base: Path) -> None:
        assert base.exists()
        assert (base / "layouts").is_dir()

    async def test_save_and_get_layout(self, store: FileChartStore, base: Path) -> None:
        meta = await store.save_layout(USER, "L1", "Layout One", '{"data":"hello"}')
        assert meta["id"] == "L1"
        assert meta["name"] == "Layout One"
        assert meta["savedAt"] > 0

        # Verify file was written
        layout_file = base / "layouts" / "L1.json"
        assert layout_file.exists()
        assert layout_file.read_text(encoding="utf-8") == '{"data":"hello"}'

        # Round-trip through API
        data = await store.get_layout(USER, "L1")
        assert data == '{"data":"hello"}'

    async def test_get_nonexistent_returns_none(self, store: FileChartStore) -> None:
        assert await store.get_layout(USER, "missing") is None

    async def test_index_persisted_as_json(self, store: FileChartStore, base: Path) -> None:
        await store.save_layout(USER, "L1", "First", "{}")
        index_path = base / "_index.json"
        assert index_path.exists()
        index = json.loads(index_path.read_text(encoding="utf-8"))
        assert isinstance(index, list)
        assert len(index) == 1
        assert index[0]["id"] == "L1"

    async def test_list_layouts_ordering(self, store: FileChartStore) -> None:
        await store.save_layout(USER, "A", "First", "{}")
        await store.save_layout(USER, "B", "Second", "{}")
        layouts = await store.list_layouts(USER)
        # Most recent first
        assert layouts[0]["id"] == "B"
        assert layouts[1]["id"] == "A"

    async def test_save_updates_existing(self, store: FileChartStore) -> None:
        await store.save_layout(USER, "L1", "Old", '{"v":1}')
        await store.save_layout(USER, "L1", "New", '{"v":2}')
        layouts = await store.list_layouts(USER)
        assert len(layouts) == 1
        assert layouts[0]["name"] == "New"
        assert await store.get_layout(USER, "L1") == '{"v":2}'

    async def test_delete_layout_removes_file_and_index_entry(
        self,
        store: FileChartStore,
        base: Path,
    ) -> None:
        await store.save_layout(USER, "L1", "Doomed", "{}")
        assert (base / "layouts" / "L1.json").exists()

        assert await store.delete_layout(USER, "L1") is True
        assert not (base / "layouts" / "L1.json").exists()
        assert await store.list_layouts(USER) == []

    async def test_delete_nonexistent_returns_false(self, store: FileChartStore) -> None:
        assert await store.delete_layout(USER, "nope") is False

    async def test_rename_layout(self, store: FileChartStore) -> None:
        await store.save_layout(USER, "L1", "Old", "{}")
        assert await store.rename_layout(USER, "L1", "Renamed") is True
        layouts = await store.list_layouts(USER)
        assert layouts[0]["name"] == "Renamed"

    async def test_rename_nonexistent_returns_false(self, store: FileChartStore) -> None:
        assert await store.rename_layout(USER, "nope", "X") is False

    async def test_sanitizes_dangerous_ids(self, store: FileChartStore, base: Path) -> None:
        await store.save_layout(USER, "../../etc/passwd", "Evil", '{"x":1}')
        # Should NOT write to ../../etc/passwd, should sanitize to "etcpasswd"
        assert not (base / ".." / ".." / "etc" / "passwd").exists()
        safe = base / "layouts" / "etcpasswd.json"
        assert safe.exists()

    async def test_settings_template_roundtrip(
        self,
        store: FileChartStore,
        base: Path,
    ) -> None:
        assert await store.get_settings_template(USER) is None
        await store.save_settings_template(USER, '{"theme":"dark"}')
        assert (base / "settings_template.json").exists()
        assert await store.get_settings_template(USER) == '{"theme":"dark"}'

    async def test_settings_default_id_lifecycle(
        self,
        store: FileChartStore,
        base: Path,
    ) -> None:
        assert await store.get_settings_default_id(USER) == "factory"
        await store.set_settings_default_id(USER, "custom")
        assert (base / "settings_default_id.txt").read_text(encoding="utf-8") == "custom"
        assert await store.get_settings_default_id(USER) == "custom"

    async def test_settings_default_id_rejects_invalid(self, store: FileChartStore) -> None:
        await store.set_settings_default_id(USER, "hacked")
        assert await store.get_settings_default_id(USER) == "factory"

    async def test_clear_settings_template(self, store: FileChartStore, base: Path) -> None:
        await store.save_settings_template(USER, '{"x":1}')
        await store.set_settings_default_id(USER, "custom")
        await store.clear_settings_template(USER)
        assert not (base / "settings_template.json").exists()
        assert await store.get_settings_default_id(USER) == "factory"

    async def test_max_layouts_cap(self, store: FileChartStore) -> None:
        for i in range(210):
            await store.save_layout(USER, f"L{i}", f"Layout {i}", "{}")
        index = await store.list_layouts(USER)
        assert len(index) == 200

    async def test_metadata_includes_summary(self, store: FileChartStore) -> None:
        meta = await store.save_layout(
            USER,
            "L1",
            "AAPL Daily",
            "{}",
            summary="SMA 200, EMA 26, BB 20",
        )
        assert meta["summary"] == "SMA 200, EMA 26, BB 20"
        layouts = await store.list_layouts(USER)
        assert layouts[0]["summary"] == "SMA 200, EMA 26, BB 20"

    async def test_concurrent_saves_dont_corrupt(self, store: FileChartStore) -> None:
        """Multiple concurrent save_layout calls should not lose data."""

        async def _save(idx: int) -> None:
            await store.save_layout(USER, f"concurrent_{idx}", f"C{idx}", f'{{"i":{idx}}}')

        await asyncio.gather(*[_save(i) for i in range(20)])
        layouts = await store.list_layouts(USER)
        assert len(layouts) == 20


# =========================================================================
# Factory
# =========================================================================


class TestChartStoreFactory:
    """Test the get_chart_store() factory function."""

    def test_default_returns_file_chart_store(self) -> None:
        from pywry.state._factory import clear_state_caches, get_chart_store

        clear_state_caches()
        store = get_chart_store()
        assert isinstance(store, FileChartStore)
        clear_state_caches()

    def test_memory_backend_via_config(self) -> None:
        from pywry.state._factory import clear_state_caches, get_chart_store

        clear_state_caches()
        with patch("pywry.config.get_settings") as mock_settings:
            mock_tvchart = MagicMock()
            mock_tvchart.storage_backend = "memory"
            mock_settings.return_value.tvchart = mock_tvchart
            store = get_chart_store()
            assert isinstance(store, MemoryChartStore)
        clear_state_caches()

    def test_factory_is_cached(self) -> None:
        from pywry.state._factory import clear_state_caches, get_chart_store

        clear_state_caches()
        store1 = get_chart_store()
        store2 = get_chart_store()
        assert store1 is store2
        clear_state_caches()


# =========================================================================
# Module-level storage helpers (from tvchart/mixin.py)
# =========================================================================


class TestChartStoreHelpers:
    """Test _chart_store_save_layout and _chart_store_sync_index."""

    @pytest.fixture
    def store(self) -> MemoryChartStore:
        return MemoryChartStore()

    def test_save_layout_persists_data(self, store: MemoryChartStore) -> None:
        _chart_store_save_layout(store, _run_async, USER, "L1", '{"data":"saved"}')
        data = _run_async(store.get_layout(USER, "L1"))
        assert data == '{"data":"saved"}'

    def test_save_layout_preserves_existing_metadata(self, store: MemoryChartStore) -> None:
        """When saving layout data, metadata (name/summary) should come from store index."""
        _run_async(
            store.save_layout(USER, "L1", "My Chart", "{}", summary="SMA 200"),
        )
        # Now simulate a JS write-through that only sends data, not metadata
        _chart_store_save_layout(store, _run_async, USER, "L1", '{"data":"updated"}')

        data = _run_async(store.get_layout(USER, "L1"))
        assert data == '{"data":"updated"}'
        layouts = _run_async(store.list_layouts(USER))
        assert layouts[0]["name"] == "My Chart"
        assert layouts[0]["summary"] == "SMA 200"

    def test_save_layout_new_id_uses_id_as_name(self, store: MemoryChartStore) -> None:
        """A brand-new layout (not in index) should use the layout_id as its name."""
        _chart_store_save_layout(store, _run_async, USER, "new_chart", "{}")
        layouts = _run_async(store.list_layouts(USER))
        assert layouts[0]["name"] == "new_chart"

    def test_sync_index_deletes_removed_layouts(self, store: MemoryChartStore) -> None:
        """When JS sends an index update, layouts not in the new index should be deleted."""
        _run_async(store.save_layout(USER, "keep", "Keep", "{}"))
        _run_async(store.save_layout(USER, "remove", "Remove", "{}"))

        # JS sends a new index that only contains "keep"
        new_index = json.dumps([{"id": "keep"}])
        _chart_store_sync_index(store, _run_async, USER, new_index)

        layouts = _run_async(store.list_layouts(USER))
        ids = {e["id"] for e in layouts}
        assert "keep" in ids
        assert "remove" not in ids

    def test_sync_index_invalid_json_is_noop(self, store: MemoryChartStore) -> None:
        _run_async(store.save_layout(USER, "L1", "Safe", "{}"))
        _chart_store_sync_index(store, _run_async, USER, "not json at all")
        assert len(_run_async(store.list_layouts(USER))) == 1

    def test_sync_index_non_list_is_noop(self, store: MemoryChartStore) -> None:
        _run_async(store.save_layout(USER, "L1", "Safe", "{}"))
        _chart_store_sync_index(store, _run_async, USER, '{"not": "a list"}')
        assert len(_run_async(store.list_layouts(USER))) == 1


# =========================================================================
# Event handler wiring (_wire_chart_storage)
# =========================================================================


class TestWireChartStorage:
    """Test the _wire_chart_storage method routes events to ChartStore."""

    @pytest.fixture
    def widget(self) -> _MockEmitterWithOn:
        return _MockEmitterWithOn()

    @pytest.fixture
    def store(self) -> MemoryChartStore:
        return MemoryChartStore()

    def _wire(self, widget: _MockEmitterWithOn, store: MemoryChartStore) -> None:
        """Wire chart storage with a patched factory."""
        with patch("pywry.state.get_chart_store", return_value=store):
            widget._wire_chart_storage(user_id=USER)

    def test_registers_set_and_remove_handlers(self, widget: _MockEmitterWithOn) -> None:
        store = MemoryChartStore()
        self._wire(widget, store)
        assert "tvchart:storage-set" in widget._handlers
        assert "tvchart:storage-remove" in widget._handlers

    def test_storage_set_layout_data(
        self,
        widget: _MockEmitterWithOn,
        store: MemoryChartStore,
    ) -> None:
        self._wire(widget, store)
        widget.fire(
            "tvchart:storage-set",
            {
                "key": "__pywry_tvchart_layout_data_v1_my-chart",
                "value": '{"bars":[1,2,3]}',
            },
        )
        data = _run_async(store.get_layout(USER, "my-chart"))
        assert data == '{"bars":[1,2,3]}'

    def test_storage_set_settings_template(
        self,
        widget: _MockEmitterWithOn,
        store: MemoryChartStore,
    ) -> None:
        self._wire(widget, store)
        widget.fire(
            "tvchart:storage-set",
            {
                "key": "__pywry_tvchart_settings_custom_template_v1",
                "value": '{"upColor":"green"}',
            },
        )
        tmpl = _run_async(store.get_settings_template(USER))
        assert tmpl == '{"upColor":"green"}'

    def test_storage_set_default_id(
        self,
        widget: _MockEmitterWithOn,
        store: MemoryChartStore,
    ) -> None:
        self._wire(widget, store)
        widget.fire(
            "tvchart:storage-set",
            {
                "key": "__pywry_tvchart_settings_default_template_v1",
                "value": "custom",
            },
        )
        did = _run_async(store.get_settings_default_id(USER))
        assert did == "custom"

    def test_storage_set_index_reconciles(
        self,
        widget: _MockEmitterWithOn,
        store: MemoryChartStore,
    ) -> None:
        _run_async(store.save_layout(USER, "keep", "Keep", "{}"))
        _run_async(store.save_layout(USER, "stale", "Stale", "{}"))
        self._wire(widget, store)

        new_index = json.dumps([{"id": "keep"}])
        widget.fire(
            "tvchart:storage-set",
            {
                "key": "__pywry_tvchart_layout_index_v1",
                "value": new_index,
            },
        )
        layouts = _run_async(store.list_layouts(USER))
        ids = {e["id"] for e in layouts}
        assert "stale" not in ids
        assert "keep" in ids

    def test_storage_remove_layout(
        self,
        widget: _MockEmitterWithOn,
        store: MemoryChartStore,
    ) -> None:
        _run_async(store.save_layout(USER, "doomed", "Doomed", "{}"))
        self._wire(widget, store)

        widget.fire(
            "tvchart:storage-remove",
            {
                "key": "__pywry_tvchart_layout_data_v1_doomed",
            },
        )
        assert _run_async(store.get_layout(USER, "doomed")) is None

    def test_storage_remove_settings_template(
        self,
        widget: _MockEmitterWithOn,
        store: MemoryChartStore,
    ) -> None:
        _run_async(store.save_settings_template(USER, '{"x":1}'))
        self._wire(widget, store)

        widget.fire(
            "tvchart:storage-remove",
            {
                "key": "__pywry_tvchart_settings_custom_template_v1",
            },
        )
        assert _run_async(store.get_settings_template(USER)) is None

    def test_storage_remove_default_id_resets(
        self,
        widget: _MockEmitterWithOn,
        store: MemoryChartStore,
    ) -> None:
        _run_async(store.set_settings_default_id(USER, "custom"))
        self._wire(widget, store)

        widget.fire(
            "tvchart:storage-remove",
            {
                "key": "__pywry_tvchart_settings_default_template_v1",
            },
        )
        assert _run_async(store.get_settings_default_id(USER)) == "factory"

    def test_empty_key_is_ignored(
        self,
        widget: _MockEmitterWithOn,
        store: MemoryChartStore,
    ) -> None:
        self._wire(widget, store)
        # Should not raise
        widget.fire("tvchart:storage-set", {"key": "", "value": "x"})
        widget.fire("tvchart:storage-remove", {"key": ""})

    def test_unknown_key_is_ignored(
        self,
        widget: _MockEmitterWithOn,
        store: MemoryChartStore,
    ) -> None:
        self._wire(widget, store)
        # Random key should not raise or mutate store
        widget.fire("tvchart:storage-set", {"key": "random_key", "value": "x"})


# =========================================================================
# Preload pipeline
# =========================================================================


class TestPreloadPipeline:
    """Test the _preload_chart_data function builds the correct dict."""

    def test_empty_store_returns_empty_index(self) -> None:
        store = MemoryChartStore()
        with patch("pywry.state.get_chart_store", return_value=store):
            from pywry.inline import _preload_chart_data

            preload = _preload_chart_data()

        assert "__pywry_tvchart_layout_index_v1" in preload
        assert json.loads(preload["__pywry_tvchart_layout_index_v1"]) == []
        assert "__pywry_tvchart_settings_default_template_v1" in preload
        assert preload["__pywry_tvchart_settings_default_template_v1"] == "factory"

    def test_preload_includes_all_layouts(self) -> None:
        store = MemoryChartStore()
        _run_async(store.save_layout(USER, "A", "Alpha", '{"a":1}'))
        _run_async(store.save_layout(USER, "B", "Beta", '{"b":2}'))

        with patch("pywry.state.get_chart_store", return_value=store):
            from pywry.inline import _preload_chart_data

            preload = _preload_chart_data()

        index = json.loads(preload["__pywry_tvchart_layout_index_v1"])
        assert len(index) == 2
        assert preload["__pywry_tvchart_layout_data_v1_A"] == '{"a":1}'
        assert preload["__pywry_tvchart_layout_data_v1_B"] == '{"b":2}'

    def test_preload_includes_settings_template(self) -> None:
        store = MemoryChartStore()
        _run_async(store.save_settings_template(USER, '{"upColor":"lime"}'))
        _run_async(store.set_settings_default_id(USER, "custom"))

        with patch("pywry.state.get_chart_store", return_value=store):
            from pywry.inline import _preload_chart_data

            preload = _preload_chart_data()

        assert preload["__pywry_tvchart_settings_custom_template_v1"] == '{"upColor":"lime"}'
        assert preload["__pywry_tvchart_settings_default_template_v1"] == "custom"

    def test_preload_omits_template_when_none(self) -> None:
        store = MemoryChartStore()

        with patch("pywry.state.get_chart_store", return_value=store):
            from pywry.inline import _preload_chart_data

            preload = _preload_chart_data()

        assert "__pywry_tvchart_settings_custom_template_v1" not in preload


# =========================================================================
# JS server backend contract
# =========================================================================


class TestJSServerBackendContract:
    """Validate the JS 06-storage.js contract for the server adapter."""

    @pytest.fixture
    def storage_js(self) -> str:
        from pywry.assets import get_tvchart_defaults_js

        return get_tvchart_defaults_js()

    def test_server_is_in_allowed_backends(self, storage_js: str) -> None:
        assert "server:" in storage_js

    def test_server_adapter_function_exists(self, storage_js: str) -> None:
        assert "function _tvBuildServerAdapter(chartId, namespace)" in storage_js

    def test_server_adapter_reads_preload(self, storage_js: str) -> None:
        """Server adapter must pre-seed from payload.storage.preload."""
        assert "payload.storage.preload" in storage_js
        assert "preload" in storage_js

    def test_server_adapter_emits_set_event(self, storage_js: str) -> None:
        assert "'tvchart:storage-set'" in storage_js

    def test_server_adapter_emits_remove_event(self, storage_js: str) -> None:
        assert "'tvchart:storage-remove'" in storage_js

    def test_server_adapter_has_standard_interface(self, storage_js: str) -> None:
        """Adapter must expose getItem, setItem, removeItem."""
        # These must appear inside _tvBuildServerAdapter
        assert "getItem: function(key)" in storage_js
        assert "setItem: function(key, value)" in storage_js
        assert "removeItem: function(key)" in storage_js

    def test_storage_adapter_routes_server_backend(self, storage_js: str) -> None:
        """_tvStorageAdapter must route 'server' to _tvBuildServerAdapter."""
        assert "backend === 'server'" in storage_js
        assert "_tvBuildServerAdapter(chartId, namespace)" in storage_js


# =========================================================================
# End-to-end round-trip: JS event → ChartStore → preload → JS hydrate
# =========================================================================


class TestEndToEndRoundTrip:
    """Simulate the full pipeline without a browser.

    JS writes → event handler → ChartStore → _preload_chart_data → preload dict
    """

    def test_layout_survives_round_trip(self) -> None:
        store = MemoryChartStore()
        widget = _MockEmitterWithOn()

        with patch("pywry.state.get_chart_store", return_value=store):
            widget._wire_chart_storage(user_id=USER)

        # 1. Simulate JS saving a layout
        layout_data = json.dumps({"bars": [{"time": 1, "open": 100}]})
        widget.fire(
            "tvchart:storage-set",
            {
                "key": "__pywry_tvchart_layout_data_v1_myChart",
                "value": layout_data,
            },
        )

        # 2. Simulate JS updating the index
        index = json.dumps([{"id": "myChart", "name": "My Chart"}])
        widget.fire(
            "tvchart:storage-set",
            {
                "key": "__pywry_tvchart_layout_index_v1",
                "value": index,
            },
        )

        # 3. Build preload (as app.py/inline.py would)
        with patch("pywry.state.get_chart_store", return_value=store):
            from pywry.inline import _preload_chart_data

            preload = _preload_chart_data()

        # 4. Verify the layout data appears in preload
        assert preload["__pywry_tvchart_layout_data_v1_myChart"] == layout_data
        loaded_index = json.loads(preload["__pywry_tvchart_layout_index_v1"])
        assert any(e["id"] == "myChart" for e in loaded_index)

    def test_settings_survive_round_trip(self) -> None:
        store = MemoryChartStore()
        widget = _MockEmitterWithOn()

        with patch("pywry.state.get_chart_store", return_value=store):
            widget._wire_chart_storage(user_id=USER)

        # 1. JS saves a custom template
        template = '{"upColor":"#26a69a","downColor":"#ef5350"}'
        widget.fire(
            "tvchart:storage-set",
            {
                "key": "__pywry_tvchart_settings_custom_template_v1",
                "value": template,
            },
        )

        # 2. JS sets default to custom
        widget.fire(
            "tvchart:storage-set",
            {
                "key": "__pywry_tvchart_settings_default_template_v1",
                "value": "custom",
            },
        )

        # 3. Build preload
        with patch("pywry.state.get_chart_store", return_value=store):
            from pywry.inline import _preload_chart_data

            preload = _preload_chart_data()

        assert preload["__pywry_tvchart_settings_custom_template_v1"] == template
        assert preload["__pywry_tvchart_settings_default_template_v1"] == "custom"

    def test_delete_then_preload_omits_layout(self) -> None:
        store = MemoryChartStore()
        widget = _MockEmitterWithOn()

        with patch("pywry.state.get_chart_store", return_value=store):
            widget._wire_chart_storage(user_id=USER)

        # 1. Save a layout
        widget.fire(
            "tvchart:storage-set",
            {
                "key": "__pywry_tvchart_layout_data_v1_ephemeral",
                "value": "{}",
            },
        )

        # 2. Delete it
        widget.fire(
            "tvchart:storage-remove",
            {
                "key": "__pywry_tvchart_layout_data_v1_ephemeral",
            },
        )

        # 3. Preload should not include it
        with patch("pywry.state.get_chart_store", return_value=store):
            from pywry.inline import _preload_chart_data

            preload = _preload_chart_data()

        assert "__pywry_tvchart_layout_data_v1_ephemeral" not in preload

    def test_filesystem_round_trip(self, tmp_path: Path) -> None:
        """Full round-trip through FileChartStore — proves filesystem I/O works."""
        store = FileChartStore(base_path=tmp_path / "charts")
        widget = _MockEmitterWithOn()

        with patch("pywry.state.get_chart_store", return_value=store):
            widget._wire_chart_storage(user_id=USER)

        # 1. Simulate JS saving a layout via event
        layout_json = '{"chart":{"crosshair":{}}, "bars":[{"t":1}]}'
        widget.fire(
            "tvchart:storage-set",
            {
                "key": "__pywry_tvchart_layout_data_v1_persistent",
                "value": layout_json,
            },
        )

        # 2. Verify the file actually exists on disk
        layout_file = tmp_path / "charts" / "layouts" / "persistent.json"
        assert layout_file.exists()
        assert layout_file.read_text(encoding="utf-8") == layout_json

        # 3. Create a FRESH store from the same path (simulates app restart)
        store2 = FileChartStore(base_path=tmp_path / "charts")

        # 4. Build preload from the fresh store
        with patch("pywry.state.get_chart_store", return_value=store2):
            from pywry.inline import _preload_chart_data

            preload = _preload_chart_data()

        # 5. The layout must reappear in the preload dict
        assert preload["__pywry_tvchart_layout_data_v1_persistent"] == layout_json
        loaded_index = json.loads(preload["__pywry_tvchart_layout_index_v1"])
        assert any(e["id"] == "persistent" for e in loaded_index)


# =========================================================================
# Config integration
# =========================================================================


class TestConfigIntegration:
    """Test that config changes affect the storage pipeline."""

    def test_default_backend_is_file(self) -> None:
        from pywry.config import get_settings

        settings = get_settings()
        assert settings.tvchart.storage_backend == "file"

    def test_file_backend_in_allowed_values(self) -> None:
        from pywry.config import TVChartSettings

        # Should not raise
        cfg = TVChartSettings(storage_backend="file")
        assert cfg.storage_backend == "file"

    def test_server_backend_in_allowed_values(self) -> None:
        from pywry.config import TVChartSettings

        cfg = TVChartSettings(storage_backend="server")
        assert cfg.storage_backend == "server"

    def test_memory_backend_in_allowed_values(self) -> None:
        from pywry.config import TVChartSettings

        cfg = TVChartSettings(storage_backend="memory")
        assert cfg.storage_backend == "memory"
