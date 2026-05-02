"""SQLite-backed state storage with encryption at rest.

Implements all five state ABCs (WidgetStore, SessionStore, ChatStore,
EventBus, ConnectionRouter) in a single encrypted SQLite database file.
Designed for local single-user desktop apps but uses the same multi-user
schema as Redis so the interfaces are fully interchangeable.

On first initialization, a default admin session is created with all
permissions. The database is encrypted using SQLCipher when available.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import time
import uuid

from pathlib import Path
from typing import Any

from .base import ChatStore, SessionStore, WidgetStore
from .memory import MemoryConnectionRouter, MemoryEventBus
from .types import UserSession, WidgetData


logger = logging.getLogger(__name__)


def _load_sqlcipher() -> Any:
    """Return the ``sqlcipher3`` / ``pysqlcipher3`` ``dbapi2`` module, or ``None``.

    Both packages expose the same DB-API 2.0 surface as stdlib
    ``sqlite3``.  ``sqlcipher3`` is the actively-maintained fork; the
    legacy ``pysqlcipher3`` is checked as a fallback for environments
    that still pin it.  ``importlib`` is used so the type checker
    doesn't complain about the alternative import paths missing stubs
    at runtime — neither package ships a ``py.typed`` marker.
    """
    import importlib

    for name in ("sqlcipher3", "pysqlcipher3"):
        try:
            module = importlib.import_module(f"{name}.dbapi2")
        except ImportError:
            continue
        return module
    return None


_SCHEMA = """
CREATE TABLE IF NOT EXISTS widgets (
    widget_id TEXT PRIMARY KEY,
    html TEXT NOT NULL,
    token TEXT,
    owner_worker_id TEXT,
    created_at REAL NOT NULL,
    metadata TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    roles TEXT NOT NULL DEFAULT '["admin"]',
    created_at REAL NOT NULL,
    expires_at REAL,
    metadata TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS role_permissions (
    role TEXT PRIMARY KEY,
    permissions TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS threads (
    thread_id TEXT PRIMARY KEY,
    widget_id TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT 'New Chat',
    status TEXT NOT NULL DEFAULT 'active',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    metadata TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL REFERENCES threads(thread_id) ON DELETE CASCADE,
    widget_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp REAL NOT NULL,
    model TEXT,
    stopped INTEGER DEFAULT 0,
    metadata TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS tool_calls (
    tool_call_id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL REFERENCES messages(message_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'other',
    status TEXT NOT NULL DEFAULT 'pending',
    arguments TEXT DEFAULT '{}',
    result TEXT,
    started_at REAL,
    completed_at REAL,
    error TEXT
);

CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL REFERENCES messages(message_id) ON DELETE CASCADE,
    artifact_type TEXT NOT NULL,
    title TEXT DEFAULT '',
    content TEXT,
    metadata TEXT DEFAULT '{}',
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS token_usage (
    usage_id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL REFERENCES messages(message_id) ON DELETE CASCADE,
    model TEXT,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    cost_usd REAL
);

CREATE TABLE IF NOT EXISTS resources (
    resource_id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL REFERENCES threads(thread_id) ON DELETE CASCADE,
    uri TEXT NOT NULL,
    name TEXT DEFAULT '',
    mime_type TEXT,
    content TEXT,
    size INTEGER,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS skills (
    skill_id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL REFERENCES threads(thread_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    activated_at REAL NOT NULL,
    metadata TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_threads_widget ON threads(widget_id);
CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(thread_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_widget ON messages(widget_id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_message ON tool_calls(message_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_message ON artifacts(message_id);
CREATE INDEX IF NOT EXISTS idx_token_usage_message ON token_usage(message_id);
CREATE INDEX IF NOT EXISTS idx_resources_thread ON resources(thread_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
"""

_DEFAULT_ROLE_PERMISSIONS = {
    "admin": ["read", "write", "admin", "delete", "manage_users"],
    "editor": ["read", "write"],
    "viewer": ["read"],
    "anonymous": [],
}

_MAX_MESSAGES_PER_THREAD = 1_000


def _resolve_encryption_key() -> str | None:
    env_key = os.environ.get("PYWRY_SQLITE_KEY")
    if env_key:
        return env_key

    try:
        import keyring

        key = keyring.get_password("pywry", "sqlite_key")
        if not key:
            key = uuid.uuid4().hex + uuid.uuid4().hex
            keyring.set_password("pywry", "sqlite_key", key)
    except Exception:
        logger.debug(
            "Keyring unavailable for SQLite key storage, falling back to salt file", exc_info=True
        )
    else:
        return key

    import hashlib

    salt_path = Path("~/.config/pywry/.salt").expanduser()
    salt_path.parent.mkdir(parents=True, exist_ok=True)
    if salt_path.exists():
        salt = salt_path.read_bytes()
    else:
        salt = os.urandom(32)
        salt_path.write_bytes(salt)

    node = str(uuid.getnode()).encode()
    return hashlib.sha256(node + salt).hexdigest()


class SqliteStateBackend:
    """Shared database connection and schema management.

    Parameters
    ----------
    db_path : str or Path
        Path to the SQLite database file.
    encryption_key : str or None
        Explicit encryption key. If ``None``, derived automatically.
    encrypted : bool
        Whether to encrypt the database. Defaults to ``True``.
    """

    _lock: asyncio.Lock | None = None
    _conn: sqlite3.Connection | None = None
    _initialized: bool = False

    def __init__(
        self,
        db_path: str | Path = "~/.config/pywry/pywry.db",
        encryption_key: str | None = None,
        encrypted: bool = True,
    ) -> None:
        self._db_path = Path(db_path).expanduser()
        self._encrypted = encrypted
        self._key = encryption_key
        if encrypted and not encryption_key:
            self._key = _resolve_encryption_key()

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _connect(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn

        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        conn: sqlite3.Connection
        if self._encrypted and self._key:
            sqlcipher = _load_sqlcipher()
            if sqlcipher is not None:
                conn = sqlcipher.connect(str(self._db_path))
                conn.execute(f"PRAGMA key = '{self._key}'")
                logger.debug("Opened encrypted SQLite database at %s", self._db_path)
            else:
                logger.warning(
                    "sqlcipher3 / pysqlcipher3 not installed — database will "
                    "NOT be encrypted.  Install with: pip install sqlcipher3"
                )
                conn = sqlite3.connect(str(self._db_path))
        else:
            conn = sqlite3.connect(str(self._db_path))

        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        self._conn = conn
        return conn

    async def _initialize(self) -> None:
        if self._initialized:
            return
        async with self._get_lock():
            if self._initialized:
                return
            conn = self._connect()
            conn.executescript(_SCHEMA)

            cursor = conn.execute("SELECT COUNT(*) FROM role_permissions")
            if cursor.fetchone()[0] == 0:
                for role, perms in _DEFAULT_ROLE_PERMISSIONS.items():
                    conn.execute(
                        "INSERT INTO role_permissions (role, permissions) VALUES (?, ?)",
                        (role, json.dumps(perms)),
                    )

            cursor = conn.execute("SELECT COUNT(*) FROM sessions")
            if cursor.fetchone()[0] == 0:
                conn.execute(
                    "INSERT INTO sessions (session_id, user_id, roles, created_at, metadata) "
                    "VALUES (?, ?, ?, ?, ?)",
                    ("local", "admin", json.dumps(["admin"]), time.time(), "{}"),
                )

            conn.commit()
            self._initialized = True

    async def _execute(
        self, sql: str, params: tuple[Any, ...] = (), commit: bool = True
    ) -> list[sqlite3.Row]:
        await self._initialize()
        async with self._get_lock():
            conn = self._connect()
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            if commit:
                conn.commit()
            return rows

    async def _executemany(self, sql: str, params_list: list[tuple[Any, ...]]) -> None:
        await self._initialize()
        async with self._get_lock():
            conn = self._connect()
            conn.executemany(sql, params_list)
            conn.commit()


class SqliteWidgetStore(SqliteStateBackend, WidgetStore):
    """SQLite-backed widget store."""

    async def register(
        self,
        widget_id: str,
        html: str,
        token: str | None = None,
        owner_worker_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self._execute(
            "INSERT OR REPLACE INTO widgets "
            "(widget_id, html, token, owner_worker_id, created_at, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (widget_id, html, token, owner_worker_id, time.time(), json.dumps(metadata or {})),
        )

    async def get(self, widget_id: str) -> WidgetData | None:
        rows = await self._execute(
            "SELECT * FROM widgets WHERE widget_id = ?", (widget_id,), commit=False
        )
        if not rows:
            return None
        r = rows[0]
        return WidgetData(
            widget_id=r["widget_id"],
            html=r["html"],
            token=r["token"],
            created_at=r["created_at"],
            owner_worker_id=r["owner_worker_id"],
            metadata=json.loads(r["metadata"] or "{}"),
        )

    async def get_html(self, widget_id: str) -> str | None:
        rows = await self._execute(
            "SELECT html FROM widgets WHERE widget_id = ?", (widget_id,), commit=False
        )
        return rows[0]["html"] if rows else None

    async def get_token(self, widget_id: str) -> str | None:
        rows = await self._execute(
            "SELECT token FROM widgets WHERE widget_id = ?", (widget_id,), commit=False
        )
        return rows[0]["token"] if rows else None

    async def exists(self, widget_id: str) -> bool:
        rows = await self._execute(
            "SELECT 1 FROM widgets WHERE widget_id = ?", (widget_id,), commit=False
        )
        return len(rows) > 0

    async def delete(self, widget_id: str) -> bool:
        before = await self.exists(widget_id)
        if before:
            await self._execute("DELETE FROM widgets WHERE widget_id = ?", (widget_id,))
        return before

    async def list_active(self) -> list[str]:
        rows = await self._execute("SELECT widget_id FROM widgets", commit=False)
        return [r["widget_id"] for r in rows]

    async def update_html(self, widget_id: str, html: str) -> bool:
        if not await self.exists(widget_id):
            return False
        await self._execute("UPDATE widgets SET html = ? WHERE widget_id = ?", (html, widget_id))
        return True

    async def update_token(self, widget_id: str, token: str) -> bool:
        if not await self.exists(widget_id):
            return False
        await self._execute("UPDATE widgets SET token = ? WHERE widget_id = ?", (token, widget_id))
        return True

    async def count(self) -> int:
        rows = await self._execute("SELECT COUNT(*) as cnt FROM widgets", commit=False)
        return rows[0]["cnt"] if rows else 0


class SqliteSessionStore(SqliteStateBackend, SessionStore):
    """SQLite-backed session store with RBAC."""

    async def create_session(
        self,
        session_id: str,
        user_id: str,
        roles: list[str] | None = None,
        ttl: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UserSession:
        now = time.time()
        expires_at = (now + ttl) if ttl else None
        session = UserSession(
            session_id=session_id,
            user_id=user_id,
            roles=roles or ["viewer"],
            created_at=now,
            expires_at=expires_at,
            metadata=metadata or {},
        )
        await self._execute(
            "INSERT OR REPLACE INTO sessions "
            "(session_id, user_id, roles, created_at, expires_at, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                session.session_id,
                session.user_id,
                json.dumps(session.roles),
                session.created_at,
                session.expires_at,
                json.dumps(session.metadata),
            ),
        )
        return session

    async def get_session(self, session_id: str) -> UserSession | None:
        rows = await self._execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,), commit=False
        )
        if not rows:
            return None
        r = rows[0]
        expires_at = r["expires_at"]
        if expires_at and time.time() > expires_at:
            await self.delete_session(session_id)
            return None
        return UserSession(
            session_id=r["session_id"],
            user_id=r["user_id"],
            roles=json.loads(r["roles"]),
            created_at=r["created_at"],
            expires_at=expires_at,
            metadata=json.loads(r["metadata"] or "{}"),
        )

    async def validate_session(self, session_id: str) -> bool:
        session = await self.get_session(session_id)
        return session is not None

    async def delete_session(self, session_id: str) -> bool:
        rows = await self._execute(
            "DELETE FROM sessions WHERE session_id = ? RETURNING session_id", (session_id,)
        )
        return len(rows) > 0

    async def refresh_session(self, session_id: str, extend_ttl: int | None = None) -> bool:
        session = await self.get_session(session_id)
        if session is None:
            return False
        if extend_ttl:
            new_expires = time.time() + extend_ttl
            await self._execute(
                "UPDATE sessions SET expires_at = ? WHERE session_id = ?",
                (new_expires, session_id),
            )
        return True

    async def list_user_sessions(self, user_id: str) -> list[UserSession]:
        rows = await self._execute(
            "SELECT * FROM sessions WHERE user_id = ?", (user_id,), commit=False
        )
        sessions = []
        now = time.time()
        for r in rows:
            expires_at = r["expires_at"]
            if expires_at and now > expires_at:
                continue
            sessions.append(
                UserSession(
                    session_id=r["session_id"],
                    user_id=r["user_id"],
                    roles=json.loads(r["roles"]),
                    created_at=r["created_at"],
                    expires_at=expires_at,
                    metadata=json.loads(r["metadata"] or "{}"),
                )
            )
        return sessions

    async def check_permission(
        self,
        session_id: str,
        resource_type: str,
        resource_id: str,
        permission: str,
    ) -> bool:
        session = await self.get_session(session_id)
        if session is None:
            return False
        for role in session.roles:
            rows = await self._execute(
                "SELECT permissions FROM role_permissions WHERE role = ?",
                (role,),
                commit=False,
            )
            if rows:
                perms = json.loads(rows[0]["permissions"])
                if permission in perms:
                    return True
        resource_perms = session.metadata.get("permissions", {})
        resource_key = f"{resource_type}:{resource_id}"
        if resource_key in resource_perms:
            return permission in resource_perms[resource_key]
        return False


class SqliteChatStore(SqliteStateBackend, ChatStore):
    """SQLite-backed chat store with audit trail."""

    async def save_thread(self, widget_id: str, thread: Any) -> None:
        await self._execute(
            "INSERT OR REPLACE INTO threads "
            "(thread_id, widget_id, title, status, created_at, updated_at, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                thread.thread_id,
                widget_id,
                thread.title,
                thread.status,
                thread.created_at,
                thread.updated_at,
                json.dumps(thread.metadata),
            ),
        )

    async def get_thread(self, widget_id: str, thread_id: str) -> Any:
        from ..chat.models import ChatThread

        rows = await self._execute(
            "SELECT * FROM threads WHERE widget_id = ? AND thread_id = ?",
            (widget_id, thread_id),
            commit=False,
        )
        if not rows:
            return None
        r = rows[0]
        return ChatThread(
            thread_id=r["thread_id"],
            title=r["title"],
            status=r["status"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
            metadata=json.loads(r["metadata"] or "{}"),
        )

    async def list_threads(self, widget_id: str) -> list[Any]:
        from ..chat.models import ChatThread

        rows = await self._execute(
            "SELECT * FROM threads WHERE widget_id = ? ORDER BY updated_at DESC",
            (widget_id,),
            commit=False,
        )
        return [
            ChatThread(
                thread_id=r["thread_id"],
                title=r["title"],
                status=r["status"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
                metadata=json.loads(r["metadata"] or "{}"),
            )
            for r in rows
        ]

    async def delete_thread(self, widget_id: str, thread_id: str) -> bool:
        rows = await self._execute(
            "DELETE FROM threads WHERE widget_id = ? AND thread_id = ? RETURNING thread_id",
            (widget_id, thread_id),
        )
        return len(rows) > 0

    async def append_message(self, widget_id: str, thread_id: str, message: Any) -> None:
        content = (
            message.content
            if isinstance(message.content, str)
            else json.dumps([p.model_dump(by_alias=True) for p in message.content])
        )
        await self._execute(
            "INSERT INTO messages "
            "(message_id, thread_id, widget_id, role, content, timestamp, model, stopped, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                message.message_id,
                thread_id,
                widget_id,
                message.role,
                content,
                message.timestamp,
                message.model,
                1 if message.stopped else 0,
                json.dumps(message.metadata),
            ),
        )

        await self._execute(
            "UPDATE threads SET updated_at = ? WHERE thread_id = ?",
            (time.time(), thread_id),
        )

        count_rows = await self._execute(
            "SELECT COUNT(*) as cnt FROM messages WHERE thread_id = ?",
            (thread_id,),
            commit=False,
        )
        count = count_rows[0]["cnt"] if count_rows else 0
        if count > _MAX_MESSAGES_PER_THREAD:
            excess = count - _MAX_MESSAGES_PER_THREAD
            await self._execute(
                "DELETE FROM messages WHERE message_id IN "
                "(SELECT message_id FROM messages WHERE thread_id = ? "
                "ORDER BY timestamp ASC LIMIT ?)",
                (thread_id, excess),
            )

    async def get_messages(
        self,
        widget_id: str,
        thread_id: str,
        limit: int = 50,
        before_id: str | None = None,
    ) -> list[Any]:
        from ..chat.models import ChatMessage

        if before_id:
            ts_rows = await self._execute(
                "SELECT timestamp FROM messages WHERE message_id = ?",
                (before_id,),
                commit=False,
            )
            if ts_rows:
                before_ts = ts_rows[0]["timestamp"]
                rows = await self._execute(
                    "SELECT * FROM messages WHERE thread_id = ? AND widget_id = ? "
                    "AND timestamp < ? ORDER BY timestamp DESC LIMIT ?",
                    (thread_id, widget_id, before_ts, limit),
                    commit=False,
                )
            else:
                rows = []
        else:
            rows = await self._execute(
                "SELECT * FROM messages WHERE thread_id = ? AND widget_id = ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (thread_id, widget_id, limit),
                commit=False,
            )

        messages = []
        for r in reversed(rows):
            content_raw = r["content"]
            try:
                content = json.loads(content_raw) if content_raw.startswith("[") else content_raw
            except (json.JSONDecodeError, AttributeError):
                content = content_raw

            messages.append(
                ChatMessage(
                    role=r["role"],
                    content=content,
                    message_id=r["message_id"],
                    timestamp=r["timestamp"],
                    model=r["model"],
                    stopped=bool(r["stopped"]),
                    metadata=json.loads(r["metadata"] or "{}"),
                )
            )
        return messages

    async def clear_messages(self, widget_id: str, thread_id: str) -> None:
        await self._execute(
            "DELETE FROM messages WHERE thread_id = ? AND widget_id = ?",
            (thread_id, widget_id),
        )

    async def log_tool_call(
        self,
        message_id: str,
        tool_call_id: str,
        name: str,
        kind: str = "other",
        status: str = "pending",
        arguments: dict[str, Any] | None = None,
        result: str | None = None,
        error: str | None = None,
    ) -> None:
        now = time.time()
        await self._execute(
            "INSERT OR REPLACE INTO tool_calls "
            "(tool_call_id, message_id, name, kind, status, arguments, result, "
            "started_at, completed_at, error) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                tool_call_id,
                message_id,
                name,
                kind,
                status,
                json.dumps(arguments or {}),
                result,
                now if status == "in_progress" else None,
                now if status in ("completed", "failed") else None,
                error,
            ),
        )

    async def log_artifact(
        self,
        message_id: str,
        artifact_type: str,
        title: str = "",
        content: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self._execute(
            "INSERT INTO artifacts "
            "(artifact_id, message_id, artifact_type, title, content, metadata, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                f"art_{uuid.uuid4().hex[:12]}",
                message_id,
                artifact_type,
                title,
                content,
                json.dumps(metadata or {}),
                time.time(),
            ),
        )

    async def log_token_usage(
        self,
        message_id: str,
        model: str | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        cost_usd: float | None = None,
    ) -> None:
        await self._execute(
            "INSERT INTO token_usage "
            "(message_id, model, prompt_tokens, completion_tokens, total_tokens, cost_usd) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (message_id, model, prompt_tokens, completion_tokens, total_tokens, cost_usd),
        )

    async def log_resource(
        self,
        thread_id: str,
        uri: str,
        name: str = "",
        mime_type: str | None = None,
        content: str | None = None,
        size: int | None = None,
    ) -> None:
        await self._execute(
            "INSERT INTO resources "
            "(resource_id, thread_id, uri, name, mime_type, content, size, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                f"res_{uuid.uuid4().hex[:12]}",
                thread_id,
                uri,
                name,
                mime_type,
                content,
                size,
                time.time(),
            ),
        )

    async def log_skill(
        self,
        thread_id: str,
        name: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self._execute(
            "INSERT INTO skills (skill_id, thread_id, name, activated_at, metadata) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                f"skill_{uuid.uuid4().hex[:12]}",
                thread_id,
                name,
                time.time(),
                json.dumps(metadata or {}),
            ),
        )

    async def get_tool_calls(self, message_id: str) -> list[dict[str, Any]]:
        rows = await self._execute(
            "SELECT * FROM tool_calls WHERE message_id = ? ORDER BY started_at",
            (message_id,),
            commit=False,
        )
        return [dict(r) for r in rows]

    async def get_artifacts(self, message_id: str) -> list[dict[str, Any]]:
        rows = await self._execute(
            "SELECT * FROM artifacts WHERE message_id = ? ORDER BY created_at",
            (message_id,),
            commit=False,
        )
        return [dict(r) for r in rows]

    async def get_usage_stats(
        self,
        thread_id: str | None = None,
        widget_id: str | None = None,
    ) -> dict[str, Any]:
        if thread_id:
            rows = await self._execute(
                "SELECT SUM(prompt_tokens) as prompt, SUM(completion_tokens) as completion, "
                "SUM(total_tokens) as total, SUM(cost_usd) as cost, COUNT(*) as count "
                "FROM token_usage tu JOIN messages m ON tu.message_id = m.message_id "
                "WHERE m.thread_id = ?",
                (thread_id,),
                commit=False,
            )
        elif widget_id:
            rows = await self._execute(
                "SELECT SUM(prompt_tokens) as prompt, SUM(completion_tokens) as completion, "
                "SUM(total_tokens) as total, SUM(cost_usd) as cost, COUNT(*) as count "
                "FROM token_usage tu JOIN messages m ON tu.message_id = m.message_id "
                "WHERE m.widget_id = ?",
                (widget_id,),
                commit=False,
            )
        else:
            rows = await self._execute(
                "SELECT SUM(prompt_tokens) as prompt, SUM(completion_tokens) as completion, "
                "SUM(total_tokens) as total, SUM(cost_usd) as cost, COUNT(*) as count "
                "FROM token_usage",
                commit=False,
            )
        if not rows:
            return {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost_usd": 0,
                "count": 0,
            }
        r = rows[0]
        return {
            "prompt_tokens": r["prompt"] or 0,
            "completion_tokens": r["completion"] or 0,
            "total_tokens": r["total"] or 0,
            "cost_usd": r["cost"] or 0.0,
            "count": r["count"] or 0,
        }

    async def get_total_cost(
        self,
        thread_id: str | None = None,
        widget_id: str | None = None,
    ) -> float:
        stats = await self.get_usage_stats(thread_id=thread_id, widget_id=widget_id)
        cost: float = stats["cost_usd"]
        return cost

    async def search_messages(
        self,
        query: str,
        widget_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        pattern = f"%{query}%"
        if widget_id:
            rows = await self._execute(
                "SELECT m.*, t.title as thread_title FROM messages m "
                "JOIN threads t ON m.thread_id = t.thread_id "
                "WHERE m.content LIKE ? AND m.widget_id = ? "
                "ORDER BY m.timestamp DESC LIMIT ?",
                (pattern, widget_id, limit),
                commit=False,
            )
        else:
            rows = await self._execute(
                "SELECT m.*, t.title as thread_title FROM messages m "
                "JOIN threads t ON m.thread_id = t.thread_id "
                "WHERE m.content LIKE ? ORDER BY m.timestamp DESC LIMIT ?",
                (pattern, limit),
                commit=False,
            )
        return [dict(r) for r in rows]


SqliteEventBus = MemoryEventBus
"""SQLite mode reuses the in-memory event bus — single-process, no pub/sub needed."""

SqliteConnectionRouter = MemoryConnectionRouter
"""SQLite mode reuses the in-memory connection router — single-process, routing is trivial."""
