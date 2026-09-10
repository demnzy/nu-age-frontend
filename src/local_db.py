"""
src/local_db.py

Local SQLite storage for downloaded courses + offline progress tracking.
This is the single source of truth for everything offline_course_page.py
reads and everything the download manager writes.

Design notes:
- One connection, reused across the app session (SQLite handles concurrent
  reads fine; writes are serialized by SQLite itself, which is plenty for
  a single-user local cache — no connection pool needed).
- `content` on downloaded_lessons is stored as a JSON TEXT blob, not
  decomposed into columns. It mirrors the server's JSONB column as-is, so
  a backend content-schema change doesn't require a local migration —
  offline_course_page.py just json.loads() it and hands it to the same
  CONTENT_RENDERERS dispatch course_page.py already has.
- lesson_progress is a separate table, deliberately never touched by
  re-downloading a course. Re-syncing/updating cached content must never
  wipe out what a user already completed offline.
- ON DELETE CASCADE on modules/lessons means deleting a downloaded_courses
  row (e.g. "remove download" action) cleans up its modules/lessons
  automatically. lesson_progress is NOT cascaded — a user's completion
  history should survive even if they delete the local copy and
  re-download later.
"""

import sqlite3
import os
import flet as ft

_connection = None
_platform_storage_dir = None


async def init_local_db(page: ft.Page):
    """
    Initialize the local SQLite database directory using Flet's cross-platform 
    storage paths, preventing issues on mobile where os.getcwd() is read-only.
    """
    global _platform_storage_dir
    if getattr(page, "web", False):
        _platform_storage_dir = None
        return
    try:
        _platform_storage_dir = await page.storage_paths.get_application_support_directory()
    except Exception:
        _platform_storage_dir = None


def get_local_db(page: ft.Page = None) -> sqlite3.Connection:
    """
    Returns a persistent sqlite3 Connection for offline course storage,
    chat caching, and progression sync. Ensures tables exist on the
    first call. `page` is accepted for API symmetry with other helpers in
    this codebase but isn't currently needed for path resolution — see
    _resolve_db_path.
    """
    global _connection
    if _connection is not None:
        return _connection

    db_path = _resolve_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    _connection = sqlite3.connect(db_path, check_same_thread=False)
    _connection.execute("PRAGMA foreign_keys = ON")

    # Handle schema migration for sender_name
    try:
        _connection.execute("ALTER TABLE chat_messages ADD COLUMN sender_name TEXT;")
    except sqlite3.OperationalError:
        pass # Column already exists

    _run_migrations(_connection)
    return _connection


def _resolve_db_path() -> str:
    """
    Uses the pre-initialized platform storage directory to resolve the SQLite DB path.
    Falls back to os.environ and os.getcwd() only for out-of-Flet environments like tests.
    """
    if _platform_storage_dir:
        base = _platform_storage_dir
    else:
        base = os.environ.get("FLET_APP_STORAGE_DATA")
        if not base:
            base = os.path.join(os.getcwd(), "app_data")
    return os.path.join(base, "courses_offline.db")


def _run_migrations(conn: sqlite3.Connection):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS downloaded_courses (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            category_id TEXT,
            objectives TEXT,              -- JSON-encoded list
            image_local_path TEXT,
            downloaded_at TEXT NOT NULL,
            server_updated_at TEXT,
            total_size_bytes INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS downloaded_modules (
            id TEXT PRIMARY KEY,
            course_id TEXT NOT NULL REFERENCES downloaded_courses(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            order_index INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS downloaded_lessons (
            id TEXT PRIMARY KEY,
            module_id TEXT NOT NULL REFERENCES downloaded_modules(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            order_index INTEGER NOT NULL,
            type TEXT NOT NULL,
            content TEXT NOT NULL          -- JSON-encoded, asset URLs already
                                            -- rewritten to local paths
        );

        CREATE TABLE IF NOT EXISTS downloaded_assets (
            id TEXT PRIMARY KEY,
            lesson_id TEXT NOT NULL REFERENCES downloaded_lessons(id) ON DELETE CASCADE,
            remote_url TEXT NOT NULL,
            local_path TEXT NOT NULL,
            mime_type TEXT,
            size_bytes INTEGER
        );

        CREATE TABLE IF NOT EXISTS lesson_progress (
            lesson_id TEXT PRIMARY KEY,
            course_id TEXT NOT NULL,
            status TEXT NOT NULL,          -- 'in_progress' | 'completed'
            completed_at TEXT,
            quiz_answers TEXT,             -- JSON-encoded
            quiz_score REAL,
            synced_at TEXT,                -- NULL until pushed to server
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_modules_course ON downloaded_modules(course_id);
        CREATE INDEX IF NOT EXISTS idx_lessons_module ON downloaded_lessons(module_id);
        CREATE INDEX IF NOT EXISTS idx_assets_lesson ON downloaded_assets(lesson_id);
        CREATE INDEX IF NOT EXISTS idx_progress_course ON lesson_progress(course_id);
        CREATE INDEX IF NOT EXISTS idx_progress_unsynced ON lesson_progress(synced_at);

        CREATE TABLE IF NOT EXISTS chat_channels (
            id TEXT PRIMARY KEY,
            name TEXT,
            type TEXT NOT NULL,
            role TEXT NOT NULL,
            last_message_snippet TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id TEXT PRIMARY KEY,
            channel_id TEXT NOT NULL REFERENCES chat_channels(id) ON DELETE CASCADE,
            sender_id TEXT NOT NULL,
            sender_name TEXT,
            type TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata_payload TEXT,           -- JSON-encoded (polls, tags)
            created_at TEXT NOT NULL,
            status TEXT NOT NULL             -- 'pending' | 'sent'
        );

        CREATE INDEX IF NOT EXISTS idx_messages_channel ON chat_messages(channel_id);
        """
    )
    conn.commit()


def close_local_db():
    """Call on app shutdown if you want a clean close; not strictly
    required since sqlite3 handles process-exit cleanup reasonably well,
    but tidy for tests."""
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None


def has_any_downloaded_courses(page: ft.Page = None) -> bool:
    """
    Single source of truth for "is there anything useful to send this
    person to offline" — used by both main.py's error-fallback screen and
    Login.py's connectivity-error dialogs, so both dead ends stay in sync
    without duplicating the query in two files.
    """
    if page is not None and getattr(page, "web", False):
        return False
    try:
        db = get_local_db(page)
        row = db.execute("SELECT 1 FROM downloaded_courses LIMIT 1").fetchone()
        return row is not None
    except Exception:
        # Fail closed — don't offer a button that would just fail again.
        return False

# ── Chat Caching Helpers ──────────────────────────────────────────────

def get_cached_chat_channels(page: ft.Page = None):
    if page is not None and getattr(page, "web", False):
        return []
    try:
        db = get_local_db(page)
        db.row_factory = sqlite3.Row
        rows = db.execute("SELECT * FROM chat_channels ORDER BY updated_at DESC").fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[CACHE ERROR] get_cached_chat_channels failed: {e}")
        return []

def upsert_chat_channels(page: ft.Page, channels: list):
    if page is not None and getattr(page, "web", False):
        return
    try:
        db = get_local_db(page)
        with db:
            for ch in channels:
                db.execute("""
                    INSERT INTO chat_channels (id, name, type, role, last_message_snippet, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name=excluded.name,
                        type=excluded.type,
                        role=excluded.role,
                        last_message_snippet=excluded.last_message_snippet,
                        updated_at=excluded.updated_at
                """, (ch['id'], ch.get('name'), ch['type'], ch.get('role', 'member'), ch.get('last_message_snippet'), ch.get('updated_at', '')))
    except Exception as e:
        print(f"[CACHE ERROR] upsert_chat_channels failed: {e}")

def get_cached_messages(page: ft.Page, channel_id: str):
    if page is not None and getattr(page, "web", False):
        return []
    try:
        db = get_local_db(page)
        db.row_factory = sqlite3.Row
        rows = db.execute("SELECT * FROM chat_messages WHERE channel_id=? ORDER BY created_at ASC", (channel_id,)).fetchall()
        
        msgs = []
        for r in rows:
            d = dict(r)
            d["sender"] = {
                "id": d["sender_id"],
                "name": d.get("sender_name") or "Unknown"
            }
            if d.get("metadata_payload"):
                import json
                try:
                    d["metadata_payload"] = json.loads(d["metadata_payload"])
                except Exception:
                    pass
            msgs.append(d)
        return msgs
    except Exception as e:
        print(f"[CACHE ERROR] get_cached_messages failed: {e}")
        return []

def upsert_chat_messages(page: ft.Page, messages: list):
    if page is not None and getattr(page, "web", False):
        return
    try:
        db = get_local_db(page)
        with db:
            for msg in messages:
                db.execute("""
                    INSERT INTO chat_messages (id, channel_id, sender_id, sender_name, type, content, metadata_payload, created_at, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        sender_name=excluded.sender_name,
                        content=excluded.content,
                        metadata_payload=excluded.metadata_payload,
                        status=excluded.status
                """, (msg['id'], msg['channel_id'], msg['sender_id'], msg.get('sender_name', 'Unknown'), msg.get('type', 'text'), msg.get('content', ''), msg.get('metadata_payload', None), msg.get('created_at', ''), msg.get('status', 'sent')))
    except Exception as e:
        print(f"[CACHE ERROR] upsert_chat_messages failed: {e}")