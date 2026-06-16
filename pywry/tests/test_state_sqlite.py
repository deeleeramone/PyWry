"""Tests for the SQLite state backend.

Covers ChatStore CRUD, audit trail, session management, RBAC,
encryption setup, key resolution, and edge paths.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
import time

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from pywry.chat.models import ChatMessage, ChatThread, TextPart
from pywry.state.sqlite import (
    SqliteChatStore,
    SqliteConnectionRouter,
    SqliteEventBus,
    SqliteSessionStore,
    SqliteWidgetStore,
    _load_sqlcipher,
    _resolve_encryption_key,
)


if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "test.db")


@pytest.fixture
def chat_store(db_path: str) -> SqliteChatStore:
    return SqliteChatStore(db_path=db_path, encrypted=False)


@pytest.fixture
def session_store(db_path: str) -> SqliteSessionStore:
    return SqliteSessionStore(db_path=db_path, encrypted=False)


@pytest.fixture
def widget_store(db_path: str) -> SqliteWidgetStore:
    return SqliteWidgetStore(db_path=db_path, encrypted=False)


# --- _load_sqlcipher ---


class TestLoadSqlcipher:
    """Tests for the _load_sqlcipher helper."""

    def test_returns_module_if_available(self) -> None:
        import importlib

        fake_module = MagicMock()
        original_import = importlib.import_module

        def patched(name):
            if name in ("sqlcipher3.dbapi2", "pysqlcipher3.dbapi2"):
                return fake_module
            return original_import(name)

        with patch("importlib.import_module", patched):
            assert _load_sqlcipher() is fake_module

    def test_returns_none_when_unavailable(self) -> None:
        import importlib

        original_import = importlib.import_module

        def patched(name):
            if name in ("sqlcipher3.dbapi2", "pysqlcipher3.dbapi2"):
                raise ImportError("not available")
            return original_import(name)

        with patch("importlib.import_module", patched):
            assert _load_sqlcipher() is None

    def test_falls_back_to_pysqlcipher(self) -> None:
        """First import fails, second succeeds."""
        import importlib

        fake_module = MagicMock()
        original_import = importlib.import_module

        def patched(name):
            if name == "sqlcipher3.dbapi2":
                raise ImportError("not installed")
            if name == "pysqlcipher3.dbapi2":
                return fake_module
            return original_import(name)

        with patch("importlib.import_module", patched):
            assert _load_sqlcipher() is fake_module


# --- _resolve_encryption_key ---


class TestResolveEncryptionKey:
    """Tests for the encryption key resolver."""

    def test_uses_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PYWRY_SQLITE_KEY", "my-test-key")
        assert _resolve_encryption_key() == "my-test-key"

    def test_keyring_existing_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PYWRY_SQLITE_KEY", raising=False)

        fake_keyring = MagicMock()
        fake_keyring.get_password.return_value = "stored-key"
        monkeypatch.setitem(sys.modules, "keyring", fake_keyring)

        assert _resolve_encryption_key() == "stored-key"

    def test_keyring_generates_and_stores_new_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PYWRY_SQLITE_KEY", raising=False)

        captured: list[tuple[str, str, str]] = []

        fake_keyring = MagicMock()
        fake_keyring.get_password.return_value = None

        def set_password(service, user, key):
            captured.append((service, user, key))

        fake_keyring.set_password.side_effect = set_password
        monkeypatch.setitem(sys.modules, "keyring", fake_keyring)

        result = _resolve_encryption_key()
        assert result is not None
        assert len(result) == 64  # uuid.uuid4().hex * 2
        assert len(captured) == 1
        assert captured[0][:2] == ("pywry", "sqlite_key")

    def test_falls_back_to_salt_file_when_keyring_unavailable(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("PYWRY_SQLITE_KEY", raising=False)

        if "keyring" in sys.modules:
            monkeypatch.delitem(sys.modules, "keyring", raising=False)

        fake_keyring = MagicMock()
        fake_keyring.get_password.side_effect = RuntimeError("no keyring")
        monkeypatch.setitem(sys.modules, "keyring", fake_keyring)

        salt_path = tmp_path / "pywry" / ".salt"
        with patch("pywry.state.sqlite.Path") as mock_path_cls:
            mock_path = MagicMock()
            mock_path.expanduser.return_value = salt_path
            mock_path_cls.return_value = mock_path

            result = _resolve_encryption_key()
            assert result is not None
            # sha256 hex
            assert len(result) == 64

    def test_falls_back_to_existing_salt_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When the salt file already exists, reuse it."""
        monkeypatch.delenv("PYWRY_SQLITE_KEY", raising=False)

        fake_keyring = MagicMock()
        fake_keyring.get_password.side_effect = RuntimeError("no keyring")
        monkeypatch.setitem(sys.modules, "keyring", fake_keyring)

        salt_dir = tmp_path / "pywry"
        salt_dir.mkdir()
        salt_path = salt_dir / ".salt"
        salt_path.write_bytes(b"my-existing-salt-32-bytes-pad----")

        with patch("pywry.state.sqlite.Path") as mock_path_cls:
            mock_path = MagicMock()
            mock_path.expanduser.return_value = salt_path
            mock_path_cls.return_value = mock_path

            assert _resolve_encryption_key() is not None


# --- SqliteStateBackend connection and encryption setup ---


class TestSqliteStateBackendSetup:
    """Tests covering the encryption setup and initialization."""

    def test_encrypted_with_explicit_key(self, tmp_path: Path) -> None:
        """Encrypted backend with explicit key falls back to plain sqlite if sqlcipher missing."""
        store = SqliteWidgetStore(
            db_path=str(tmp_path / "enc.db"),
            encryption_key="test-key-1234",
            encrypted=True,
        )
        conn = store._connect()
        assert conn is not None

    def test_encrypted_without_key_calls_resolver(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """With encrypted=True and no key, the resolver is invoked."""
        monkeypatch.setenv("PYWRY_SQLITE_KEY", "resolved-key-1234")
        store = SqliteWidgetStore(
            db_path=str(tmp_path / "test.db"),
            encrypted=True,
        )
        assert store._key == "resolved-key-1234"

    def test_unencrypted_no_key(self, tmp_path: Path) -> None:
        store = SqliteWidgetStore(
            db_path=str(tmp_path / "plain.db"),
            encrypted=False,
        )
        assert store._encrypted is False
        assert store._connect() is not None

    def test_connect_with_sqlcipher_available(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When sqlcipher loads, it is used to open the connection."""
        fake_sqlcipher = MagicMock()
        real_conn = sqlite3.connect(":memory:")
        fake_sqlcipher.connect.return_value = real_conn

        monkeypatch.setattr("pywry.state.sqlite._load_sqlcipher", lambda: fake_sqlcipher)

        store = SqliteWidgetStore(
            db_path=str(tmp_path / "enc.db"),
            encryption_key="my-key",
            encrypted=True,
        )
        conn = store._connect()
        fake_sqlcipher.connect.assert_called_once()
        assert conn is real_conn

    def test_connect_encrypted_warns_when_sqlcipher_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """encrypted=True with key but no sqlcipher falls back to plain sqlite3."""
        monkeypatch.setattr("pywry.state.sqlite._load_sqlcipher", lambda: None)

        store = SqliteWidgetStore(
            db_path=str(tmp_path / "enc.db"),
            encryption_key="my-key",
            encrypted=True,
        )
        assert store._connect() is not None

    async def test_initialize_idempotent(self, tmp_path: Path) -> None:
        """Calling _initialize twice does not duplicate setup."""
        store = SqliteWidgetStore(db_path=str(tmp_path / "test.db"), encrypted=False)
        await store._initialize()
        await store._initialize()
        assert store._initialized is True

    async def test_initialize_double_check_locking(self, tmp_path: Path) -> None:
        """The inner _initialized check inside the lock skips re-initialization."""
        store = SqliteWidgetStore(db_path=str(tmp_path / "test.db"), encrypted=False)

        lock = store._get_lock()
        await lock.acquire()
        try:
            task = asyncio.create_task(store._initialize())
            await asyncio.sleep(0.05)
            store._initialized = True
        finally:
            lock.release()
        await asyncio.wait_for(task, timeout=2.0)

        assert store._initialized is True

    async def test_executemany(self, tmp_path: Path) -> None:
        """The _executemany helper inserts multiple rows in one batch."""
        store = SqliteWidgetStore(db_path=str(tmp_path / "test.db"), encrypted=False)
        await store._initialize()
        await store._executemany(
            "INSERT INTO widgets (widget_id, html, created_at) VALUES (?, ?, ?)",
            [("w1", "<p>1</p>", 1.0), ("w2", "<p>2</p>", 2.0)],
        )

        rows = await store._execute(
            "SELECT widget_id FROM widgets ORDER BY widget_id", commit=False
        )
        assert [r["widget_id"] for r in rows] == ["w1", "w2"]


# --- SqliteWidgetStore ---


class TestSqliteWidgetStore:
    """Tests for SqliteWidgetStore."""

    async def test_register_and_get(self, widget_store: SqliteWidgetStore) -> None:
        await widget_store.register("w1", "<h1>hi</h1>", token="tok1")
        widget = await widget_store.get("w1")
        assert widget is not None
        assert widget.html == "<h1>hi</h1>"
        assert widget.token == "tok1"

    async def test_get_missing(self, widget_store: SqliteWidgetStore) -> None:
        assert await widget_store.get("missing") is None

    async def test_get_with_metadata(self, widget_store: SqliteWidgetStore) -> None:
        await widget_store.register("w1", "<p>x</p>", metadata={"theme": "dark"})
        widget = await widget_store.get("w1")
        assert widget is not None
        assert widget.metadata == {"theme": "dark"}

    async def test_get_html_missing(self, widget_store: SqliteWidgetStore) -> None:
        assert await widget_store.get_html("missing") is None

    async def test_get_token_missing(self, widget_store: SqliteWidgetStore) -> None:
        assert await widget_store.get_token("missing") is None

    async def test_list_active(self, widget_store: SqliteWidgetStore) -> None:
        await widget_store.register("w1", "<h1>a</h1>")
        await widget_store.register("w2", "<h1>b</h1>")
        widgets = await widget_store.list_active()
        assert "w1" in widgets
        assert "w2" in widgets

    async def test_delete(self, widget_store: SqliteWidgetStore) -> None:
        await widget_store.register("w1", "<h1>a</h1>")
        assert await widget_store.delete("w1") is True
        assert await widget_store.get("w1") is None

    async def test_delete_missing(self, widget_store: SqliteWidgetStore) -> None:
        assert await widget_store.delete("missing") is False

    async def test_exists_and_count(self, widget_store: SqliteWidgetStore) -> None:
        assert await widget_store.exists("w1") is False
        assert await widget_store.count() == 0
        await widget_store.register("w1", "<h1>a</h1>")
        assert await widget_store.exists("w1") is True
        assert await widget_store.count() == 1

    async def test_update_html(self, widget_store: SqliteWidgetStore) -> None:
        await widget_store.register("w1", "<h1>old</h1>")
        assert await widget_store.update_html("w1", "<h1>new</h1>") is True
        assert (await widget_store.get_html("w1")) == "<h1>new</h1>"

    async def test_update_html_missing(self, widget_store: SqliteWidgetStore) -> None:
        assert await widget_store.update_html("missing", "<p>x</p>") is False

    async def test_update_token(self, widget_store: SqliteWidgetStore) -> None:
        await widget_store.register("w1", "<h1>a</h1>", token="old")
        assert await widget_store.update_token("w1", "new") is True
        assert (await widget_store.get_token("w1")) == "new"

    async def test_update_token_missing(self, widget_store: SqliteWidgetStore) -> None:
        assert await widget_store.update_token("missing", "tok") is False


# --- SqliteSessionStore ---


class TestSqliteSessionStore:
    """Tests for SqliteSessionStore."""

    async def test_auto_admin_session(self, session_store: SqliteSessionStore) -> None:
        """The 'local' session is auto-created on first init."""
        session = await session_store.get_session("local")
        assert session is not None
        assert session.user_id == "admin"
        assert "admin" in session.roles

    async def test_create_and_get_session(self, session_store: SqliteSessionStore) -> None:
        session = await session_store.create_session(
            session_id="s1", user_id="alice", roles=["editor"]
        )
        assert session.user_id == "alice"
        retrieved = await session_store.get_session("s1")
        assert retrieved is not None
        assert "editor" in retrieved.roles

    async def test_get_missing_session(self, session_store: SqliteSessionStore) -> None:
        assert await session_store.get_session("missing") is None

    async def test_validate_session_missing(self, session_store: SqliteSessionStore) -> None:
        assert await session_store.validate_session("missing") is False

    async def test_session_expiry(self, session_store: SqliteSessionStore) -> None:
        await session_store.create_session(session_id="s_exp", user_id="bob", ttl=1)
        assert await session_store.get_session("s_exp") is not None

        await asyncio.sleep(1.1)
        assert await session_store.get_session("s_exp") is None

    async def test_check_permission_admin(self, session_store: SqliteSessionStore) -> None:
        assert await session_store.check_permission("local", "widget", "w1", "admin") is True

    async def test_check_permission_viewer(self, session_store: SqliteSessionStore) -> None:
        await session_store.create_session(
            session_id="viewer_s", user_id="viewer_user", roles=["viewer"]
        )
        assert await session_store.check_permission(
            "viewer_s", "widget", "w1", "read"
        ) is True
        assert await session_store.check_permission(
            "viewer_s", "widget", "w1", "write"
        ) is False

    async def test_check_permission_missing_session(
        self, session_store: SqliteSessionStore
    ) -> None:
        assert await session_store.check_permission("missing", "widget", "w1", "read") is False

    async def test_check_permission_resource_specific(
        self, session_store: SqliteSessionStore
    ) -> None:
        """Resource-specific permission via session metadata grants access."""
        meta = {"permissions": {"widget:w1": ["read"]}}
        await session_store.create_session(
            "s1", "u1", roles=["unknown-role"], metadata=meta
        )

        assert await session_store.check_permission("s1", "widget", "w1", "read") is True
        assert await session_store.check_permission("s1", "widget", "w1", "write") is False

    async def test_delete_session(self, session_store: SqliteSessionStore) -> None:
        await session_store.create_session(session_id="del_s", user_id="u1")
        assert await session_store.delete_session("del_s") is True
        assert await session_store.get_session("del_s") is None

    async def test_refresh_session_missing(self, session_store: SqliteSessionStore) -> None:
        assert await session_store.refresh_session("missing") is False

    async def test_refresh_session_with_extend_ttl(
        self, session_store: SqliteSessionStore
    ) -> None:
        await session_store.create_session("s1", "u1", ttl=600)
        assert await session_store.refresh_session("s1", extend_ttl=1200) is True

    async def test_refresh_session_no_extend_ttl(
        self, session_store: SqliteSessionStore
    ) -> None:
        await session_store.create_session("s1", "u1", ttl=600)
        assert await session_store.refresh_session("s1") is True

    async def test_list_user_sessions(self, session_store: SqliteSessionStore) -> None:
        await session_store.create_session(session_id="s1", user_id="alice")
        await session_store.create_session(session_id="s2", user_id="alice")
        assert len(await session_store.list_user_sessions("alice")) == 2

    async def test_list_user_sessions_skips_expired(
        self, session_store: SqliteSessionStore
    ) -> None:
        await session_store.create_session("active", "u1", ttl=600)
        await session_store._execute(
            "INSERT INTO sessions (session_id, user_id, roles, created_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                "expired",
                "u1",
                json.dumps(["viewer"]),
                time.time() - 1000,
                time.time() - 100,
            ),
        )

        ids = [s.session_id for s in await session_store.list_user_sessions("u1")]
        assert "active" in ids
        assert "expired" not in ids


# --- SqliteChatStore CRUD ---


class TestSqliteChatStoreCRUD:
    """CRUD tests for SqliteChatStore."""

    async def test_save_and_get_thread(self, chat_store: SqliteChatStore) -> None:
        thread = ChatThread(thread_id="t1", title="Test Thread")
        await chat_store.save_thread("w1", thread)
        result = await chat_store.get_thread("w1", "t1")
        assert result is not None
        assert result.thread_id == "t1"
        assert result.title == "Test Thread"

    async def test_get_nonexistent_thread(self, chat_store: SqliteChatStore) -> None:
        assert await chat_store.get_thread("w1", "nonexistent") is None

    async def test_list_threads(self, chat_store: SqliteChatStore) -> None:
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await chat_store.save_thread("w1", ChatThread(thread_id="t2", title="B"))
        assert len(await chat_store.list_threads("w1")) == 2

    async def test_delete_thread(self, chat_store: SqliteChatStore) -> None:
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        assert await chat_store.delete_thread("w1", "t1") is True
        assert await chat_store.get_thread("w1", "t1") is None

    async def test_append_and_get_messages(self, chat_store: SqliteChatStore) -> None:
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await chat_store.append_message(
            "w1", "t1", ChatMessage(role="user", content="hello", message_id="m1")
        )
        messages = await chat_store.get_messages("w1", "t1")
        assert len(messages) == 1
        assert messages[0].text_content() == "hello"

    async def test_message_with_list_content(self, chat_store: SqliteChatStore) -> None:
        """Roundtrip a message whose content is a list of parts (stored as JSON)."""
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await chat_store.append_message(
            "w1",
            "t1",
            ChatMessage(
                role="user",
                content=[TextPart(text="hello"), TextPart(text="world")],
                message_id="m1",
            ),
        )

        messages = await chat_store.get_messages("w1", "t1")
        assert len(messages) == 1
        assert messages[0].text_content() == "helloworld"

    async def test_clear_messages(self, chat_store: SqliteChatStore) -> None:
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await chat_store.append_message("w1", "t1", ChatMessage(role="user", content="x"))
        await chat_store.clear_messages("w1", "t1")
        assert len(await chat_store.get_messages("w1", "t1")) == 0

    async def test_widget_isolation(self, chat_store: SqliteChatStore) -> None:
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="W1"))
        await chat_store.save_thread("w2", ChatThread(thread_id="t2", title="W2"))
        w1_threads = await chat_store.list_threads("w1")
        w2_threads = await chat_store.list_threads("w2")
        assert len(w1_threads) == 1
        assert len(w2_threads) == 1
        assert w1_threads[0].title == "W1"

    async def test_message_pagination(self, chat_store: SqliteChatStore) -> None:
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        for i in range(10):
            await chat_store.append_message(
                "w1",
                "t1",
                ChatMessage(role="user", content=f"msg{i}", message_id=f"m{i}"),
            )
        assert len(await chat_store.get_messages("w1", "t1", limit=3)) == 3

    async def test_message_eviction(self, chat_store: SqliteChatStore) -> None:
        """When message count exceeds _MAX_MESSAGES_PER_THREAD, oldest are evicted."""
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="A"))

        with patch("pywry.state.sqlite._MAX_MESSAGES_PER_THREAD", 5):
            for i in range(10):
                await chat_store.append_message(
                    "w1",
                    "t1",
                    ChatMessage(role="user", content=f"msg{i}", message_id=f"m{i}"),
                )

            messages = await chat_store.get_messages("w1", "t1", limit=20)
            assert len(messages) == 5

    async def test_get_messages_before_id_not_found(
        self, chat_store: SqliteChatStore
    ) -> None:
        """When before_id doesn't match anything, no messages are returned."""
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await chat_store.append_message(
            "w1", "t1", ChatMessage(role="user", content="hi", message_id="m1")
        )
        assert await chat_store.get_messages("w1", "t1", before_id="ghost") == []

    async def test_get_messages_before_id_returns_earlier(
        self, chat_store: SqliteChatStore
    ) -> None:
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        for i in range(5):
            await chat_store.append_message(
                "w1",
                "t1",
                ChatMessage(role="user", content=f"msg{i}", message_id=f"m{i}"),
            )

        messages = await chat_store.get_messages("w1", "t1", before_id="m3")
        ids = {m.message_id for m in messages}
        assert "m3" not in ids
        assert "m4" not in ids
        assert {"m0", "m1", "m2"} & ids

    async def test_get_messages_with_corrupt_json(self, chat_store: SqliteChatStore) -> None:
        """When content looks like JSON but is corrupt, fall back to raw text."""
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await chat_store._execute(
            "INSERT INTO messages "
            "(message_id, thread_id, widget_id, role, content, timestamp, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "m1",
                "t1",
                "w1",
                "user",
                "[corrupted-not-real-json",
                time.time(),
                "{}",
            ),
        )

        messages = await chat_store.get_messages("w1", "t1")
        assert len(messages) == 1
        assert "[corrupted" in messages[0].text_content()

    async def test_persistence_across_instances(self, db_path: str) -> None:
        """Data written by one store is readable by a fresh store on the same file."""
        store1 = SqliteChatStore(db_path=db_path, encrypted=False)
        await store1.save_thread("w1", ChatThread(thread_id="t1", title="Persistent"))
        await store1.append_message(
            "w1", "t1", ChatMessage(role="user", content="saved")
        )

        store2 = SqliteChatStore(db_path=db_path, encrypted=False)
        thread = await store2.get_thread("w1", "t1")
        assert thread is not None
        assert thread.title == "Persistent"
        messages = await store2.get_messages("w1", "t1")
        assert len(messages) == 1
        assert messages[0].text_content() == "saved"


# --- SqliteChatStore audit trail ---


class TestSqliteAuditTrail:
    """Tests for the SQLite-only audit trail methods."""

    async def test_log_and_get_tool_calls(self, chat_store: SqliteChatStore) -> None:
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await chat_store.append_message(
            "w1", "t1", ChatMessage(role="assistant", content="ok", message_id="m1")
        )
        await chat_store.log_tool_call(
            message_id="m1",
            tool_call_id="tc1",
            name="read_file",
            kind="read",
            status="completed",
            arguments={"path": "/tmp/test.txt"},
            result="file contents here",
        )
        calls = await chat_store.get_tool_calls("m1")
        assert len(calls) == 1
        assert calls[0]["name"] == "read_file"
        assert calls[0]["status"] == "completed"

    async def test_log_and_get_artifacts(self, chat_store: SqliteChatStore) -> None:
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await chat_store.append_message(
            "w1", "t1", ChatMessage(role="assistant", content="ok", message_id="m1")
        )
        await chat_store.log_artifact(
            message_id="m1",
            artifact_type="code",
            title="main.py",
            content="x = 42",
        )
        artifacts = await chat_store.get_artifacts("m1")
        assert len(artifacts) == 1
        assert artifacts[0]["artifact_type"] == "code"
        assert artifacts[0]["title"] == "main.py"

    async def test_log_token_usage_and_stats_by_thread(
        self, chat_store: SqliteChatStore
    ) -> None:
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await chat_store.append_message(
            "w1", "t1", ChatMessage(role="assistant", content="ok", message_id="m1")
        )
        await chat_store.log_token_usage(
            message_id="m1",
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_usd=0.005,
        )
        stats = await chat_store.get_usage_stats(thread_id="t1")
        assert stats["prompt_tokens"] == 100
        assert stats["completion_tokens"] == 50
        assert stats["total_tokens"] == 150
        assert stats["cost_usd"] == 0.005

    async def test_log_token_usage_stats_by_widget(
        self, chat_store: SqliteChatStore
    ) -> None:
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await chat_store.append_message(
            "w1", "t1", ChatMessage(role="user", content="hi", message_id="m1")
        )
        await chat_store.log_token_usage(
            message_id="m1",
            model="gpt-4",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            cost_usd=0.001,
        )

        stats = await chat_store.get_usage_stats(widget_id="w1")
        assert stats["total_tokens"] == 15
        assert stats["count"] >= 1

    async def test_get_usage_stats_no_filters(self, chat_store: SqliteChatStore) -> None:
        stats = await chat_store.get_usage_stats()
        assert "prompt_tokens" in stats
        assert stats["count"] == 0

    async def test_get_usage_stats_no_rows_returns_zero_dict(
        self,
        chat_store: SqliteChatStore,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When _execute returns no rows, get_usage_stats returns a zeroed dict."""

        async def fake_execute(*args, **kwargs):
            return []

        monkeypatch.setattr(chat_store, "_execute", fake_execute)
        stats = await chat_store.get_usage_stats(thread_id="t1")
        assert stats == {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0,
            "count": 0,
        }

    async def test_total_cost(self, chat_store: SqliteChatStore) -> None:
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await chat_store.append_message(
            "w1", "t1", ChatMessage(role="assistant", content="a", message_id="m1")
        )
        await chat_store.append_message(
            "w1", "t1", ChatMessage(role="assistant", content="b", message_id="m2")
        )
        await chat_store.log_token_usage(message_id="m1", cost_usd=0.01)
        await chat_store.log_token_usage(message_id="m2", cost_usd=0.02)
        cost = await chat_store.get_total_cost(thread_id="t1")
        assert abs(cost - 0.03) < 0.001

    async def test_search_messages(self, chat_store: SqliteChatStore) -> None:
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await chat_store.append_message(
            "w1", "t1", ChatMessage(role="user", content="find the fibonacci function")
        )
        await chat_store.append_message(
            "w1", "t1", ChatMessage(role="assistant", content="here is the code")
        )
        results = await chat_store.search_messages("fibonacci")
        assert len(results) == 1
        assert "fibonacci" in results[0]["content"]

    async def test_search_messages_with_widget_filter(
        self, chat_store: SqliteChatStore
    ) -> None:
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await chat_store.save_thread("w2", ChatThread(thread_id="t2", title="B"))
        await chat_store.append_message(
            "w1", "t1", ChatMessage(role="user", content="apple banana")
        )
        await chat_store.append_message(
            "w2", "t2", ChatMessage(role="user", content="apple cherry")
        )

        results = await chat_store.search_messages("apple", widget_id="w1")
        assert len(results) == 1
        assert results[0]["widget_id"] == "w1"

    async def test_log_resource(self, chat_store: SqliteChatStore) -> None:
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await chat_store.log_resource(
            thread_id="t1",
            uri="file:///data/report.csv",
            name="report.csv",
            mime_type="text/csv",
            size=1024,
        )

    async def test_log_skill(self, chat_store: SqliteChatStore) -> None:
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await chat_store.log_skill(
            thread_id="t1",
            name="langgraph-docs",
            metadata={"version": "1.0"},
        )


# --- Cross-backend aliases ---


class TestSqliteEventBusAndRouter:
    """SQLite mode reuses the memory event bus and connection router."""

    def test_event_bus_is_memory(self):
        from pywry.state.memory import MemoryEventBus

        assert SqliteEventBus is MemoryEventBus

    def test_connection_router_is_memory(self):
        from pywry.state.memory import MemoryConnectionRouter

        assert SqliteConnectionRouter is MemoryConnectionRouter


# --- Factory integration ---


class TestSqliteFactoryIntegration:
    def test_state_backend_sqlite(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PYWRY_DEPLOY__STATE_BACKEND", "sqlite")
        from pywry.state._factory import get_state_backend
        from pywry.state.types import StateBackend

        assert get_state_backend() == StateBackend.SQLITE


# --- Memory store audit-trail no-ops ---


class TestAuditTrailDefaultNoOps:
    """Memory and Redis stores have no-op audit-trail methods."""

    async def test_memory_store_no_op_methods(self) -> None:
        from pywry.state.memory import MemoryChatStore

        store = MemoryChatStore()
        await store.log_tool_call("m1", "tc1", "search")
        await store.log_artifact("m1", "code", "test.py")
        await store.log_token_usage("m1", prompt_tokens=100)
        assert await store.get_tool_calls("m1") == []
        stats = await store.get_usage_stats()
        assert stats["total_tokens"] == 0
