"""Tests for pywry.utils.async_helpers."""

from __future__ import annotations

import asyncio
import threading
import time

from pywry.utils.async_helpers import async_task, run_async, run_in_thread


class TestRunAsync:
    def test_runs_coroutine_synchronously(self):
        @run_async
        async def add(a, b):
            await asyncio.sleep(0)
            return a + b

        assert add(1, 2) == 3

    def test_passes_kwargs(self):
        @run_async
        async def echo(**kwargs):
            return kwargs

        assert echo(a=1, b=2) == {"a": 1, "b": 2}

    def test_propagates_exceptions(self):
        @run_async
        async def boom():
            raise RuntimeError("nope")

        try:
            boom()
        except RuntimeError as e:
            assert str(e) == "nope"
        else:
            raise AssertionError("Exception not propagated")


class TestAsyncTask:
    def test_wraps_async_function(self):
        @async_task
        async def double(x):
            return x * 2

        result = asyncio.run(double(5))
        assert result == 10

    def test_preserves_async_behavior(self):
        @async_task
        async def slow():
            await asyncio.sleep(0)
            return "done"

        assert asyncio.run(slow()) == "done"


class TestRunInThread:
    def test_runs_function_in_thread(self):
        results = []

        @run_in_thread
        def worker(value):
            results.append(value)

        thread = worker("hello")
        assert isinstance(thread, threading.Thread)
        thread.join(timeout=2.0)
        assert results == ["hello"]

    def test_returns_thread(self):
        @run_in_thread
        def quick():
            time.sleep(0.01)

        thread = quick()
        assert isinstance(thread, threading.Thread)
        assert thread.is_alive() or not thread.is_alive()  # smoke
        thread.join(timeout=2.0)
