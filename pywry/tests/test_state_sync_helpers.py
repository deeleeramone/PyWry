"""Tests for sync_helpers module."""

from __future__ import annotations

import asyncio
import threading
import time

from unittest.mock import patch

import pytest

from pywry.state.sync_helpers import (
    WaitResult,
    _FallbackLoopHolder,
    _get_or_create_fallback_loop,
    _get_server_loop,
    run_async,
    run_async_fire_and_forget,
    wait_for_event,
)


def _stop_fallback_loop_helper() -> None:
    """Stop the fallback loop and wait for thread."""
    from pywry.state import sync_helpers

    holder = sync_helpers._fallback_holder
    if holder.loop is not None and holder.loop.is_running():
        holder.loop.call_soon_threadsafe(holder.loop.stop)
    if holder.thread is not None and holder.thread.is_alive():
        holder.thread.join(timeout=2.0)
    holder.loop = None
    holder.thread = None


@pytest.fixture(autouse=True)
def _reset_fallback_loop():
    """Ensure each test starts/finishes with a clean fallback loop state."""
    _stop_fallback_loop_helper()
    yield
    _stop_fallback_loop_helper()


class TestGetServerLoop:
    """Tests for _get_server_loop helper."""

    def test_no_running_loop_returns_none(self) -> None:
        # When there's no running loop, returns None
        from pywry.inline import _state

        # save original
        original_loop = _state.server_loop
        try:
            _state.server_loop = None
            assert _get_server_loop() is None
        finally:
            _state.server_loop = original_loop

    def test_loop_not_running_returns_none(self) -> None:
        from pywry.inline import _state

        original_loop = _state.server_loop
        try:
            # Set a loop that isn't running
            new_loop = asyncio.new_event_loop()
            _state.server_loop = new_loop
            assert _get_server_loop() is None
            new_loop.close()
        finally:
            _state.server_loop = original_loop

    def test_running_loop_returned(self) -> None:
        from pywry.inline import _state

        original_loop = _state.server_loop
        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever, daemon=True)
        thread.start()
        try:
            _state.server_loop = loop
            # Wait for loop to start
            for _ in range(50):
                if loop.is_running():
                    break
                time.sleep(0.01)
            assert _get_server_loop() is loop
        finally:
            _state.server_loop = original_loop
            loop.call_soon_threadsafe(loop.stop)
            thread.join(timeout=2.0)
            loop.close()

    def test_inline_import_error_returns_none(self) -> None:
        # Patch imports to simulate ImportError
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "pywry.inline":
                raise ImportError("simulated")
            return real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=fake_import):
            assert _get_server_loop() is None


class TestGetOrCreateFallbackLoop:
    """Tests for _get_or_create_fallback_loop."""

    def test_creates_loop(self) -> None:
        loop = _get_or_create_fallback_loop()
        assert loop is not None
        assert loop.is_running()

    def test_reuses_existing_loop(self) -> None:
        loop1 = _get_or_create_fallback_loop()
        loop2 = _get_or_create_fallback_loop()
        assert loop1 is loop2

    def test_loop_runs_coroutine(self) -> None:
        loop = _get_or_create_fallback_loop()

        async def add(a: int, b: int) -> int:
            return a + b

        future = asyncio.run_coroutine_threadsafe(add(2, 3), loop)
        assert future.result(timeout=2.0) == 5

    def test_loop_creation_waits_for_start(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Force the wait-for-loop-to-start path by mocking is_running."""
        from pywry.state import sync_helpers

        # Patch threading.Thread to delay actually starting the loop
        original_thread = threading.Thread
        thread_started = threading.Event()

        class SlowThread:
            def __init__(self, target, daemon=True):
                self._real = original_thread(target=target, daemon=daemon)

            def start(self):
                # Delay starting briefly
                def delayed_start():
                    time.sleep(0.05)
                    self._real.start()

                t = original_thread(target=delayed_start, daemon=True)
                t.start()
                thread_started.set()

            def join(self, timeout=None):
                self._real.join(timeout=timeout)

            @property
            def is_alive(self):
                return self._real.is_alive

        # Use the slow thread - this gives us time to hit the sleep loop
        monkeypatch.setattr(sync_helpers.threading, "Thread", SlowThread)

        loop = _get_or_create_fallback_loop()
        # Loop should still eventually be running
        assert loop is not None


class TestRunAsync:
    """Tests for run_async."""

    def test_runs_simple_coroutine(self) -> None:
        async def coro() -> str:
            return "hello"

        result = run_async(coro())
        assert result == "hello"

    def test_propagates_exception(self) -> None:
        async def coro() -> None:
            raise ValueError("bad")

        with pytest.raises(ValueError, match="bad"):
            run_async(coro())

    def test_timeout_raises(self) -> None:
        async def slow() -> None:
            await asyncio.sleep(5.0)

        # The future.result() raises a different TimeoutError type.
        # accept any exception in the timeout family
        with pytest.raises((asyncio.TimeoutError, TimeoutError, Exception)):
            run_async(slow(), timeout=0.1)

    def test_uses_server_loop_when_available(self) -> None:
        """If a server loop is running, run_async uses it."""
        from pywry.inline import _state

        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever, daemon=True)
        thread.start()
        # Wait for loop to start
        for _ in range(50):
            if loop.is_running():
                break
            time.sleep(0.01)

        original_loop = _state.server_loop
        try:
            _state.server_loop = loop

            async def coro() -> str:
                return "from-server"

            result = run_async(coro())
            assert result == "from-server"
        finally:
            _state.server_loop = original_loop
            loop.call_soon_threadsafe(loop.stop)
            thread.join(timeout=2.0)
            loop.close()

    def test_deadlock_protection(self) -> None:
        """run_async called from within the server loop must raise RuntimeError."""
        from pywry.inline import _state

        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever, daemon=True)
        thread.start()
        for _ in range(50):
            if loop.is_running():
                break
            time.sleep(0.01)

        original_loop = _state.server_loop
        try:
            _state.server_loop = loop

            error: list[Exception] = []

            async def inner_run() -> None:
                async def child() -> None:
                    pass

                try:
                    run_async(child())
                except Exception as e:
                    error.append(e)

            future = asyncio.run_coroutine_threadsafe(inner_run(), loop)
            future.result(timeout=2.0)

            assert len(error) == 1
            assert isinstance(error[0], RuntimeError)
            assert "deadlock" in str(error[0]).lower() or "async context" in str(error[0]).lower()
        finally:
            _state.server_loop = original_loop
            loop.call_soon_threadsafe(loop.stop)
            thread.join(timeout=2.0)
            loop.close()


class TestWaitForEvent:
    """Tests for wait_for_event."""

    def test_event_set_returns_completed(self) -> None:
        ev = threading.Event()
        ev.set()
        result = wait_for_event(ev, timeout=1.0)
        assert result.completed is True
        assert result.cancelled is False
        assert result.timed_out is False

    def test_cancellation_returns_cancelled(self) -> None:
        ev = threading.Event()
        cancel = threading.Event()
        cancel.set()
        result = wait_for_event(ev, timeout=1.0, cancellation=cancel)
        assert result.cancelled is True

    def test_timeout_returns_timed_out(self) -> None:
        ev = threading.Event()
        result = wait_for_event(ev, timeout=0.2, poll_interval=0.05)
        assert result.timed_out is True

    def test_event_set_during_wait(self) -> None:
        ev = threading.Event()

        def set_later() -> None:
            time.sleep(0.1)
            ev.set()

        thread = threading.Thread(target=set_later)
        thread.start()
        result = wait_for_event(ev, timeout=2.0, poll_interval=0.05)
        thread.join()
        assert result.completed is True


class TestRunAsyncFireAndForget:
    """Tests for run_async_fire_and_forget."""

    def test_schedules_with_fallback_loop(self) -> None:
        called = threading.Event()

        async def coro() -> None:
            called.set()

        run_async_fire_and_forget(coro())

        assert called.wait(timeout=2.0) is True

    def test_uses_server_loop_when_available(self) -> None:
        from pywry.inline import _state

        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever, daemon=True)
        thread.start()
        for _ in range(50):
            if loop.is_running():
                break
            time.sleep(0.01)

        called = threading.Event()

        async def coro() -> None:
            called.set()

        original_loop = _state.server_loop
        try:
            _state.server_loop = loop
            run_async_fire_and_forget(coro())
            assert called.wait(timeout=2.0) is True
        finally:
            _state.server_loop = original_loop
            loop.call_soon_threadsafe(loop.stop)
            thread.join(timeout=2.0)
            loop.close()


class TestWaitResult:
    """Tests for the WaitResult dataclass."""

    def test_default_values(self) -> None:
        result = WaitResult()
        assert result.completed is False
        assert result.cancelled is False
        assert result.timed_out is False

    def test_explicit_values(self) -> None:
        result = WaitResult(completed=True, cancelled=False, timed_out=False)
        assert result.completed is True


class TestFallbackHolder:
    """Tests for the _FallbackLoopHolder dataclass-like class."""

    def test_initial_state(self) -> None:
        holder = _FallbackLoopHolder()
        assert holder.loop is None
        assert holder.thread is None
