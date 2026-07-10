"""Unit tests for pywry.callbacks targeting branches not covered by integration tests."""

from __future__ import annotations

import asyncio
import threading
import time

from unittest.mock import MagicMock, patch

import pytest

from pywry.callbacks import CallbackRegistry, WidgetType, get_registry


@pytest.fixture(autouse=True)
def _clean_registry():
    reg = get_registry()
    reg.clear()
    reg._destroyed_labels.clear()
    yield
    reg.clear()
    reg._destroyed_labels.clear()


class TestRegistrySingleton:
    def test_singleton(self):
        a = CallbackRegistry()
        b = CallbackRegistry()
        assert a is b

    def test_get_registry_returns_singleton(self):
        a = get_registry()
        b = get_registry()
        assert a is b


class TestRegister:
    def test_invalid_event_type_returns_false(self):
        reg = get_registry()
        ok = reg.register("w", "invalid no-colon", lambda d: None)
        assert ok is False

    def test_destroyed_label_rejected(self):
        reg = get_registry()
        reg.destroy("w")
        ok = reg.register("w", "evt:x", lambda d: None)
        assert ok is False

    def test_simple_register(self):
        reg = get_registry()
        ok = reg.register("w", "evt:x", lambda d: None)
        assert ok is True

    def test_scoped_register(self):
        reg = get_registry()
        ok = reg.register("w", "evt:x", lambda d: None, widget_type="grid", widget_id="g1")
        assert ok is True
        assert "w" in reg._scoped_callbacks


class TestUnregister:
    def test_unknown_label_returns_false(self):
        reg = get_registry()
        assert reg.unregister("nonexistent") is False

    def test_remove_all_for_label(self):
        reg = get_registry()
        reg.register("w", "evt:x", lambda d: None)
        reg.register("w", "evt:y", lambda d: None)
        assert reg.unregister("w") is True
        assert "w" not in reg._callbacks

    def test_remove_event_type_only(self):
        reg = get_registry()

        def h(d):
            return None

        reg.register("w", "evt:x", h)
        reg.register("w", "evt:y", h)
        assert reg.unregister("w", "evt:x") is True
        assert "evt:x" not in reg._callbacks["w"]
        assert "evt:y" in reg._callbacks["w"]

    def test_unknown_event_type_returns_false(self):
        reg = get_registry()
        reg.register("w", "evt:x", lambda d: None)
        assert reg.unregister("w", "evt:other") is False

    def test_remove_specific_handler(self):
        reg = get_registry()

        def h1(d):
            return None

        def h2(d):
            return None

        reg.register("w", "evt:x", h1)
        reg.register("w", "evt:x", h2)
        assert reg.unregister("w", "evt:x", h1) is True
        assert h1 not in reg._callbacks["w"]["evt:x"]
        assert h2 in reg._callbacks["w"]["evt:x"]

    def test_remove_unknown_handler_returns_false(self):
        reg = get_registry()

        def h1(d):
            return None

        def h2(d):
            return None

        reg.register("w", "evt:x", h1)
        assert reg.unregister("w", "evt:x", h2) is False


class TestMatchesWildcards:
    def test_wildcard_matches_anything(self):
        assert CallbackRegistry._matches("*", "anything") is True

    def test_glob_pattern(self):
        assert CallbackRegistry._matches("grid_*", "grid_123") is True
        assert CallbackRegistry._matches("grid_*", "chart_456") is False

    def test_exact_match(self):
        assert CallbackRegistry._matches("chart", "chart") is True


class TestDispatch:
    def test_destroyed_label_returns_false(self):
        reg = get_registry()
        reg.destroy("w")
        assert reg.dispatch("w", "evt:x", {}) is False

    def test_dispatches_to_simple_handler(self):
        reg = get_registry()
        called = []

        def handler(data, event_type, label):
            called.append((event_type, label, data))

        reg.register("w", "evt:x", handler)
        result = reg.dispatch("w", "evt:x", {"k": 1})
        # Wait briefly for thread pool execution
        reg._drain(timeout=2.0)
        assert result is True
        assert len(called) == 1

    def test_dispatches_with_subevent(self):
        reg = get_registry()
        called = []
        reg.register("w", "ns:event", called.append)

        # Triple-colon event triggers base event match
        reg.dispatch("w", "ns:event:sub-id", {})
        reg._drain(timeout=2.0)
        assert len(called) == 1

    def test_namespace_wildcard(self):
        reg = get_registry()
        called = []

        # validate_event_type rejects "ns:*", but the dispatch code looks
        # up that key — directly inject so we hit the namespace-wildcard branch.
        def h(d):
            return called.append(d)

        reg._callbacks.setdefault("w", {}).setdefault("ns:*", []).append(h)

        reg.dispatch("w", "ns:event", {})
        reg._drain(timeout=2.0)
        assert len(called) == 1

    def test_global_wildcard(self):
        reg = get_registry()
        called = []
        reg.register("w", "*", called.append)
        reg.dispatch("w", "ns:event", {})
        reg._drain(timeout=2.0)
        assert len(called) == 1

    def test_scoped_dispatch_with_match(self):
        reg = get_registry()
        called = []
        reg.register(
            "w",
            "evt:x",
            called.append,
            widget_type="grid",
            widget_id="g1",
        )
        reg.dispatch("w", "evt:x", {"widget_type": "grid", "gridId": "g1"})
        reg._drain(timeout=2.0)
        assert len(called) == 1

    def test_scoped_dispatch_with_chart_id(self):
        reg = get_registry()
        called = []
        reg.register(
            "w",
            "evt:x",
            called.append,
            widget_type="chart",
            widget_id="c1",
        )
        reg.dispatch("w", "evt:x", {"widget_type": "chart", "chartId": "c1"})
        reg._drain(timeout=2.0)
        assert len(called) == 1

    def test_scoped_dispatch_with_toolbar_id(self):
        reg = get_registry()
        called = []
        reg.register(
            "w",
            "evt:x",
            called.append,
            widget_type="toolbar",
            widget_id="t1",
        )
        reg.dispatch("w", "evt:x", {"widget_type": "toolbar", "toolbarId": "t1"})
        reg._drain(timeout=2.0)
        assert len(called) == 1

    def test_scoped_dispatch_no_match(self):
        reg = get_registry()
        called = []
        reg.register(
            "w",
            "evt:x",
            called.append,
            widget_type="grid",
            widget_id="other",
        )
        reg.dispatch("w", "evt:x", {"widget_type": "grid", "gridId": "g1"})
        reg._drain(timeout=2.0)
        assert called == []

    def test_scoped_namespace_wildcard(self):
        reg = get_registry()
        called = []

        def h(d):
            return called.append(d)

        # Direct injection — `evt:*` fails event-type validation
        reg._scoped_callbacks.setdefault("w", {}).setdefault("evt:*", []).append(("grid", "*", h))
        # Scope simple callbacks dict so destroyed-label check passes
        reg._callbacks.setdefault("w", {})

        reg.dispatch("w", "evt:click", {"widget_type": "grid", "gridId": "any"})
        reg._drain(timeout=2.0)
        assert len(called) == 1

    def test_returns_false_when_no_handlers(self):
        reg = get_registry()
        assert reg.dispatch("w", "evt:x", {}) is False

    def test_handler_two_arg_signature(self):
        reg = get_registry()
        called = []
        reg.register("w", "evt:x", lambda data, et: called.append((data, et)))
        reg.dispatch("w", "evt:x", {"k": 1})
        reg._drain(timeout=2.0)
        assert len(called) == 1

    def test_handler_one_arg_signature(self):
        reg = get_registry()
        called = []
        reg.register("w", "evt:x", called.append)
        reg.dispatch("w", "evt:x", {"k": 1})
        reg._drain(timeout=2.0)
        assert called == [{"k": 1}]

    def test_handler_raising_logged_not_propagated(self):
        reg = get_registry()

        def bad(data):
            raise RuntimeError("boom")

        reg.register("w", "evt:x", bad)
        # Should not raise
        reg.dispatch("w", "evt:x", {})
        reg._drain(timeout=2.0)

    def test_invoke_handler_inspect_failure(self):
        reg = get_registry()
        called = []

        # A handler whose signature inspection will fail (built-in)
        # When inspect.signature() raises, the outer except logs.
        def make_failing_handler():
            class _C:
                def __call__(self, *a, **kw):
                    called.append("ok")

            obj = _C()
            return obj

        h = make_failing_handler()
        with patch("pywry.callbacks.inspect.signature", side_effect=ValueError("boom")):
            reg.register("w", "evt:x", h)
            assert reg.dispatch("w", "evt:x", {}) is False


class TestAsyncDispatch:
    def test_async_handler_dispatched(self):
        reg = get_registry()
        called = []

        async def handler(data, event_type, label):
            called.append((event_type, label, data))

        reg.register("w", "evt:x", handler)
        # Mock runtime portal to avoid native subprocess
        with patch("pywry.runtime.get_portal") as mock_portal_get:
            portal = MagicMock()
            mock_portal_get.return_value = portal
            assert reg.dispatch("w", "evt:x", {}) is True
            portal.start_task_soon.assert_called()

    def test_async_handler_portal_start_failure(self):
        reg = get_registry()

        async def handler(data):
            return None

        reg.register("w", "evt:x", handler)
        with patch("pywry.runtime.get_portal") as mock_portal_get:
            portal = MagicMock()
            portal.start_task_soon.side_effect = RuntimeError("portal fail")
            mock_portal_get.return_value = portal
            assert reg.dispatch("w", "evt:x", {}) is False

    def test_async_handler_no_portal_falls_back(self):
        reg = get_registry()

        async def handler(data):
            return None

        reg.register("w", "evt:x", handler)
        with (
            patch("pywry.runtime.get_portal", return_value=None),
            patch("pywry.runtime._ensure_portal") as mock_ensure,
        ):
            portal = MagicMock()
            mock_ensure.return_value = portal
            assert reg.dispatch("w", "evt:x", {}) is True

    def test_async_handler_fallback_failure(self):
        reg = get_registry()

        async def handler(data):
            return None

        reg.register("w", "evt:x", handler)
        with (
            patch("pywry.runtime.get_portal", return_value=None),
            patch("pywry.runtime._ensure_portal", side_effect=RuntimeError("nope")),
        ):
            assert reg.dispatch("w", "evt:x", {}) is False

    def test_async_run_async_body_three_args(self):
        """Run the async wrapper body to cover lines 345-353."""
        reg = get_registry()
        called = []

        async def handler(data, event_type, label):
            called.append((event_type, label, data))

        reg.register("w", "evt:x", handler)

        captured = {"coro": None}

        def fake_start_task_soon(coro_fn):
            # Execute the coroutine in our event loop synchronously
            captured["coro"] = coro_fn()
            asyncio.get_event_loop().run_until_complete(captured["coro"])

        portal = MagicMock()
        portal.start_task_soon.side_effect = fake_start_task_soon

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            with patch("pywry.runtime.get_portal", return_value=portal):
                reg.dispatch("w", "evt:x", {"k": 1})
        finally:
            loop.close()
            asyncio.set_event_loop(None)
        assert len(called) == 1

    def test_async_run_async_body_two_args(self):
        reg = get_registry()
        called = []

        async def handler(data, event_type):
            called.append((event_type, data))

        reg.register("w", "evt:x", handler)

        def fake_start_task_soon(coro_fn):
            asyncio.get_event_loop().run_until_complete(coro_fn())

        portal = MagicMock()
        portal.start_task_soon.side_effect = fake_start_task_soon

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            with patch("pywry.runtime.get_portal", return_value=portal):
                reg.dispatch("w", "evt:x", {"k": 1})
        finally:
            loop.close()
            asyncio.set_event_loop(None)
        assert len(called) == 1

    def test_async_run_async_body_one_arg(self):
        reg = get_registry()
        called = []

        async def handler(data):
            called.append(data)

        reg.register("w", "evt:x", handler)

        def fake_start_task_soon(coro_fn):
            asyncio.get_event_loop().run_until_complete(coro_fn())

        portal = MagicMock()
        portal.start_task_soon.side_effect = fake_start_task_soon

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            with patch("pywry.runtime.get_portal", return_value=portal):
                reg.dispatch("w", "evt:x", {"k": 1})
        finally:
            loop.close()
            asyncio.set_event_loop(None)
        assert called == [{"k": 1}]

    def test_async_handler_raises_logged(self):
        """Cover line 353: log_callback_error inside run_async."""
        reg = get_registry()

        async def handler(data):
            raise RuntimeError("boom")

        reg.register("w", "evt:x", handler)

        def fake_start_task_soon(coro_fn):
            asyncio.get_event_loop().run_until_complete(coro_fn())

        portal = MagicMock()
        portal.start_task_soon.side_effect = fake_start_task_soon

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            with patch("pywry.runtime.get_portal", return_value=portal):
                # Should not raise
                reg.dispatch("w", "evt:x", {})
        finally:
            loop.close()
            asyncio.set_event_loop(None)


class TestDestroyAndRecover:
    def test_destroy_existing(self):
        reg = get_registry()
        reg.register("w", "evt:x", lambda d: None)
        assert reg.destroy("w") is True

    def test_destroy_nonexistent(self):
        reg = get_registry()
        assert reg.destroy("nope") is False

    def test_destroy_scoped(self):
        reg = get_registry()
        reg.register("w", "evt:x", lambda d: None, widget_type="grid", widget_id="g1")
        assert reg.destroy("w") is True

    def test_recover_label(self):
        reg = get_registry()
        reg.destroy("w")
        assert reg.is_destroyed("w") is True
        assert reg.recover_label("w") is True
        assert reg.is_destroyed("w") is False

    def test_recover_unknown_label(self):
        reg = get_registry()
        assert reg.recover_label("nope") is False


class TestHasHandlers:
    def test_no_handlers(self):
        reg = get_registry()
        assert reg.has_handlers("w") is False

    def test_simple_handlers(self):
        reg = get_registry()
        reg.register("w", "evt:x", lambda d: None)
        assert reg.has_handlers("w") is True

    def test_scoped_handlers(self):
        reg = get_registry()
        reg.register("w", "evt:x", lambda d: None, widget_type="grid", widget_id="g1")
        assert reg.has_handlers("w") is True


class TestGetLabels:
    def test_empty(self):
        reg = get_registry()
        assert reg.get_labels() == []

    def test_combines_simple_and_scoped(self):
        reg = get_registry()
        reg.register("w1", "evt:x", lambda d: None)
        reg.register("w2", "evt:y", lambda d: None, widget_type="grid", widget_id="g1")
        labels = set(reg.get_labels())
        assert labels == {"w1", "w2"}


class TestClear:
    def test_clear_resets_state(self):
        reg = get_registry()
        reg.register("w", "evt:x", lambda d: None)
        reg.destroy("z")
        reg.clear()
        assert reg._callbacks == {}
        assert reg._scoped_callbacks == {}
        assert reg._destroyed_labels == set()


class TestWidgetType:
    def test_widget_type_values(self):
        assert WidgetType.GRID.value == "grid"
        assert WidgetType.CHART.value == "chart"
        assert WidgetType.TOOLBAR.value == "toolbar"
        assert WidgetType.HTML.value == "html"
        assert WidgetType.WINDOW.value == "window"


class TestDispatchUnknownEventType:
    """Tests for dispatching unknown event types to known labels."""

    def test_dispatch_nonexistent_event_returns_false(self) -> None:
        """Dispatching nonexistent event returns False even when label has handlers."""
        registry = get_registry()
        registry.clear()
        registry.register("test-window", "known:event", lambda _: None)

        result = registry.dispatch("test-window", "unknown:event", {})
        assert result is False
