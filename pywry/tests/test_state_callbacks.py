"""Tests for the CallbackRegistry."""

from __future__ import annotations

import asyncio

import pytest

from pywry.state.callbacks import (
    CallbackRegistration,
    CallbackRegistry,
    _RegistryHolder,
    get_callback_registry,
    reset_callback_registry,
)


@pytest.fixture
def registry() -> CallbackRegistry:
    return CallbackRegistry()


class TestCallbackRegistration:
    """Tests for the CallbackRegistration dataclass."""

    def test_default_values(self) -> None:
        def cb(data: dict, widget_id: str, event_type: str) -> None:
            pass

        reg = CallbackRegistration(widget_id="w1", event_type="click", callback=cb)
        assert reg.widget_id == "w1"
        assert reg.event_type == "click"
        assert reg.is_async is False
        assert reg.invoke_count == 0
        assert reg.last_invoked is None
        assert reg.created_at > 0


class TestCallbackRegistry:
    """Tests for CallbackRegistry."""

    async def test_register_sync_callback(self, registry: CallbackRegistry) -> None:
        def cb(data: dict, widget_id: str, event_type: str) -> str:
            return "ok"

        await registry.register("w1", "click", cb)
        reg = await registry.get("w1", "click")
        assert reg is not None
        assert reg.is_async is False
        assert reg.callback is cb

    async def test_register_async_callback(self, registry: CallbackRegistry) -> None:
        async def cb(data: dict, widget_id: str, event_type: str) -> str:
            return "async-ok"

        await registry.register("w1", "click", cb)
        reg = await registry.get("w1", "click")
        assert reg is not None
        assert reg.is_async is True

    async def test_get_nonexistent_widget(self, registry: CallbackRegistry) -> None:
        result = await registry.get("missing-widget", "click")
        assert result is None

    async def test_get_nonexistent_event(self, registry: CallbackRegistry) -> None:
        async def cb(*args) -> None:
            pass

        await registry.register("w1", "click", cb)
        result = await registry.get("w1", "missing-event")
        assert result is None

    async def test_has_widget(self, registry: CallbackRegistry) -> None:
        async def cb(*args) -> None:
            pass

        assert await registry.has_widget("w1") is False
        await registry.register("w1", "click", cb)
        assert await registry.has_widget("w1") is True

    async def test_has_callback(self, registry: CallbackRegistry) -> None:
        async def cb(*args) -> None:
            pass

        await registry.register("w1", "click", cb)
        assert await registry.has_callback("w1", "click") is True
        assert await registry.has_callback("w1", "other-event") is False
        assert await registry.has_callback("missing-widget", "click") is False

    async def test_invoke_sync_callback(self, registry: CallbackRegistry) -> None:
        captured: list[tuple] = []

        def cb(data: dict, widget_id: str, event_type: str) -> str:
            captured.append((data, widget_id, event_type))
            return "result"

        await registry.register("w1", "click", cb)
        success, result = await registry.invoke("w1", "click", {"x": 100})
        assert success is True
        assert result == "result"
        assert captured == [({"x": 100}, "w1", "click")]

    async def test_invoke_async_callback(self, registry: CallbackRegistry) -> None:
        captured: list[tuple] = []

        async def cb(data: dict, widget_id: str, event_type: str) -> str:
            captured.append((data, widget_id, event_type))
            return "async-result"

        await registry.register("w1", "click", cb)
        success, result = await registry.invoke("w1", "click", {"y": 200})
        assert success is True
        assert result == "async-result"
        assert captured == [({"y": 200}, "w1", "click")]

    async def test_invoke_missing_callback(self, registry: CallbackRegistry) -> None:
        success, result = await registry.invoke("missing", "click", {})
        assert success is False
        assert result is None

    async def test_invoke_callback_raises(self, registry: CallbackRegistry) -> None:
        def bad_cb(*args) -> None:
            raise RuntimeError("oops")

        await registry.register("w1", "click", bad_cb)
        success, result = await registry.invoke("w1", "click", {})
        assert success is False
        assert result is None

    async def test_invoke_async_callback_raises(self, registry: CallbackRegistry) -> None:
        async def bad_cb(*args) -> None:
            raise RuntimeError("oops")

        await registry.register("w1", "click", bad_cb)
        success, result = await registry.invoke("w1", "click", {})
        assert success is False
        assert result is None

    async def test_invoke_increments_count(self, registry: CallbackRegistry) -> None:
        async def cb(*args) -> str:
            return "ok"

        await registry.register("w1", "click", cb)
        await registry.invoke("w1", "click", {})
        await registry.invoke("w1", "click", {})

        reg = await registry.get("w1", "click")
        assert reg is not None
        assert reg.invoke_count == 2
        assert reg.last_invoked is not None

    async def test_unregister(self, registry: CallbackRegistry) -> None:
        async def cb(*args) -> None:
            pass

        await registry.register("w1", "click", cb)
        result = await registry.unregister("w1", "click")
        assert result is True
        assert await registry.has_callback("w1", "click") is False

    async def test_unregister_widget_cleanup(self, registry: CallbackRegistry) -> None:
        """When the only callback for a widget is removed, the widget entry is gone."""

        async def cb(*args) -> None:
            pass

        await registry.register("w1", "click", cb)
        await registry.unregister("w1", "click")
        assert await registry.has_widget("w1") is False

    async def test_unregister_widget_keeps_other_events(self, registry: CallbackRegistry) -> None:
        async def cb1(*args) -> None:
            pass

        async def cb2(*args) -> None:
            pass

        await registry.register("w1", "click", cb1)
        await registry.register("w1", "change", cb2)
        await registry.unregister("w1", "click")
        assert await registry.has_callback("w1", "change") is True
        assert await registry.has_widget("w1") is True

    async def test_unregister_nonexistent_widget(self, registry: CallbackRegistry) -> None:
        result = await registry.unregister("missing", "click")
        assert result is False

    async def test_unregister_nonexistent_event(self, registry: CallbackRegistry) -> None:
        async def cb(*args) -> None:
            pass

        await registry.register("w1", "click", cb)
        result = await registry.unregister("w1", "missing")
        assert result is False

    async def test_unregister_widget_returns_count(self, registry: CallbackRegistry) -> None:
        async def cb(*args) -> None:
            pass

        await registry.register("w1", "click", cb)
        await registry.register("w1", "change", cb)
        await registry.register("w1", "submit", cb)

        count = await registry.unregister_widget("w1")
        assert count == 3
        assert await registry.has_widget("w1") is False

    async def test_unregister_widget_missing(self, registry: CallbackRegistry) -> None:
        count = await registry.unregister_widget("missing")
        assert count == 0

    async def test_list_widget_events(self, registry: CallbackRegistry) -> None:
        async def cb(*args) -> None:
            pass

        await registry.register("w1", "click", cb)
        await registry.register("w1", "change", cb)
        events = await registry.list_widget_events("w1")
        assert set(events) == {"click", "change"}

    async def test_list_widget_events_missing(self, registry: CallbackRegistry) -> None:
        events = await registry.list_widget_events("missing")
        assert events == []

    async def test_list_widgets(self, registry: CallbackRegistry) -> None:
        async def cb(*args) -> None:
            pass

        assert await registry.list_widgets() == []
        await registry.register("w1", "click", cb)
        await registry.register("w2", "click", cb)
        widgets = await registry.list_widgets()
        assert set(widgets) == {"w1", "w2"}

    async def test_get_stats(self, registry: CallbackRegistry) -> None:
        async def cb(*args) -> None:
            pass

        stats = await registry.get_stats()
        assert stats == {"widget_count": 0, "total_callbacks": 0, "widgets": {}}

        await registry.register("w1", "click", cb)
        await registry.register("w1", "change", cb)
        await registry.register("w2", "click", cb)

        stats = await registry.get_stats()
        assert stats["widget_count"] == 2
        assert stats["total_callbacks"] == 3
        assert "w1" in stats["widgets"]
        assert "w2" in stats["widgets"]
        assert set(stats["widgets"]["w1"]) == {"click", "change"}


class TestCallbackRegistrySingleton:
    """Tests for the singleton getter/reset."""

    def test_get_callback_registry_returns_singleton(self) -> None:
        reset_callback_registry()
        r1 = get_callback_registry()
        r2 = get_callback_registry()
        assert r1 is r2

    def test_get_callback_registry_initial_creation(self) -> None:
        # Reset internal state
        _RegistryHolder.instance = None
        r = get_callback_registry()
        assert isinstance(r, CallbackRegistry)
        assert _RegistryHolder.instance is r

    def test_reset_callback_registry(self) -> None:
        reset_callback_registry()
        r1 = get_callback_registry()
        reset_callback_registry()
        r2 = get_callback_registry()
        assert r1 is not r2
