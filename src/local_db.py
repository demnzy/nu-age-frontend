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
import json
import re
import uuid
from datetime import datetime, timezone, timedelta
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
        if not base and os.name == "nt":
            appdata = os.environ.get("APPDATA")
            if appdata:
                candidate = os.path.join(appdata, "Appveyor Systems Inc", "Flet")
                if os.path.exists(candidate):
                    base = candidate
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

        CREATE TABLE IF NOT EXISTS downloaded_study_materials (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            title TEXT NOT NULL,
            source_type TEXT NOT NULL,          -- 'text', 'pdf', 'youtube', 'pack_import'
            content TEXT,                       -- Markdown notes / extracted text
            file_url TEXT,
            downloaded_at TEXT NOT NULL,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS downloaded_flashcards (
            id TEXT PRIMARY KEY,
            material_id TEXT NOT NULL REFERENCES downloaded_study_materials(id) ON DELETE CASCADE,
            user_id TEXT,
            front TEXT NOT NULL,
            back TEXT NOT NULL,
            interval_days INTEGER DEFAULT 0,
            ease_factor REAL DEFAULT 2.5,
            repetitions INTEGER DEFAULT 0,
            next_review_date TEXT
        );

        CREATE TABLE IF NOT EXISTS downloaded_study_questions (
            id TEXT PRIMARY KEY,
            material_id TEXT NOT NULL REFERENCES downloaded_study_materials(id) ON DELETE CASCADE,
            user_id TEXT,
            question_text TEXT NOT NULL,
            options TEXT NOT NULL,              -- JSON-encoded list of choices
            answer_index INTEGER NOT NULL,
            explanation TEXT,
            difficulty TEXT,
            image_url TEXT,
            topic TEXT,
            exam_type TEXT,
            exam_year INTEGER
        );

        CREATE TABLE IF NOT EXISTS study_review_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id TEXT NOT NULL,
            quality INTEGER NOT NULL,
            reviewed_at TEXT NOT NULL,
            synced_at TEXT                      -- NULL until pushed to server
        );

        CREATE TABLE IF NOT EXISTS exam_attempts (
            id TEXT PRIMARY KEY,
            material_id TEXT,
            bundle_id TEXT,
            exam_title TEXT NOT NULL,
            exam_type TEXT,
            score INTEGER NOT NULL,
            total INTEGER NOT NULL,
            percentage REAL NOT NULL,
            scaled_score INTEGER,
            grade TEXT,
            time_spent_seconds INTEGER,
            attempted_at TEXT NOT NULL,
            breakdown_json TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_fc_material ON downloaded_flashcards(material_id);
        CREATE INDEX IF NOT EXISTS idx_q_material ON downloaded_study_questions(material_id);
        CREATE INDEX IF NOT EXISTS idx_study_reviews_unsynced ON study_review_queue(synced_at);
        CREATE INDEX IF NOT EXISTS idx_exam_attempts_material ON exam_attempts(material_id);
        CREATE INDEX IF NOT EXISTS idx_exam_attempts_date ON exam_attempts(attempted_at);
        """
    )
    conn.commit()

    # Self-healing migration for downloaded_study_questions CBT columns
    try:
        cur = conn.cursor()
        cols = [r[1] for r in cur.execute("PRAGMA table_info(downloaded_study_questions)").fetchall()]
        if cols:
            if "image_url" not in cols:
                cur.execute("ALTER TABLE downloaded_study_questions ADD COLUMN image_url TEXT")
            if "topic" not in cols:
                cur.execute("ALTER TABLE downloaded_study_questions ADD COLUMN topic TEXT")
            if "exam_type" not in cols:
                cur.execute("ALTER TABLE downloaded_study_questions ADD COLUMN exam_type TEXT")
            if "exam_year" not in cols:
                cur.execute("ALTER TABLE downloaded_study_questions ADD COLUMN exam_year INTEGER")
        conn.commit()
    except Exception:
        pass

    # ── Self-Healing Migration: Restore YouTube URLs mistakenly downloaded as HTML stubs ──
    try:
        cur = conn.cursor()
        bad_assets = cur.execute(
            """
            SELECT a.id, a.lesson_id, a.remote_url, a.local_path, l.content
            FROM downloaded_assets a
            JOIN downloaded_lessons l ON l.id = a.lesson_id
            WHERE a.remote_url LIKE '%youtube.com%' OR a.remote_url LIKE '%youtu.be%'
            """
        ).fetchall()
        for a_id, lesson_id, remote_url, local_path, content_json in bad_assets:
            if content_json:
                import json
                try:
                    c = json.loads(content_json)
                    if c.get("video_url") == local_path:
                        c["video_url"] = remote_url
                        cur.execute("UPDATE downloaded_lessons SET content = ? WHERE id = ?", (json.dumps(c), lesson_id))
                except Exception:
                    pass
            # Remove the HTML file from disk if it exists
            if local_path and os.path.isfile(local_path):
                try:
                    os.remove(local_path)
                except Exception:
                    pass
            cur.execute("DELETE FROM downloaded_assets WHERE id = ?", (a_id,))
        conn.commit()
    except Exception:
        pass

    # Purge empty study materials created without content
    try:
        conn.execute(
            """
            DELETE FROM downloaded_study_materials
            WHERE NOT EXISTS (SELECT 1 FROM downloaded_flashcards WHERE material_id = downloaded_study_materials.id)
              AND NOT EXISTS (SELECT 1 FROM downloaded_study_questions WHERE material_id = downloaded_study_materials.id)
            """
        )
        conn.commit()
    except Exception:
        pass


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
    person to offline" — checks both downloaded courses and offline study materials with content.
    """
    if page is not None and getattr(page, "web", False):
        return False
    try:
        db = get_local_db(page)
        row = db.execute(
            """
            SELECT 1 FROM downloaded_courses 
            UNION ALL 
            SELECT 1 FROM downloaded_study_materials m
            WHERE EXISTS (SELECT 1 FROM downloaded_flashcards WHERE material_id = m.id)
               OR EXISTS (SELECT 1 FROM downloaded_study_questions WHERE material_id = m.id)
            LIMIT 1
            """
        ).fetchone()
        return row is not None
    except Exception:
        return False


def has_any_downloaded_study_materials(page: ft.Page = None) -> bool:
    """Returns True if any study materials or packs with cards or questions are cached locally."""
    if page is not None and getattr(page, "web", False):
        return False
    try:
        db = get_local_db(page)
        row = db.execute(
            """
            SELECT 1 FROM downloaded_study_materials m
            WHERE EXISTS (SELECT 1 FROM downloaded_flashcards WHERE material_id = m.id)
               OR EXISTS (SELECT 1 FROM downloaded_study_questions WHERE material_id = m.id)
            LIMIT 1
            """
        ).fetchone()
        return row is not None
    except Exception:
        return False


def has_any_offline_content(page: ft.Page = None) -> bool:
    """Returns True if user has any downloaded courses OR study materials."""
    return has_any_downloaded_courses(page)


def is_course_downloaded(course_id: str, page: ft.Page = None) -> bool:
    """Check if a specific course has been downloaded locally for offline study."""
    if page is not None and getattr(page, "web", False):
        return False
    if not course_id:
        return False
    try:
        db = get_local_db(page)
        row = db.execute("SELECT 1 FROM downloaded_courses WHERE id = ? LIMIT 1", (str(course_id),)).fetchone()
        return row is not None
    except Exception:
        return False


def is_study_material_downloaded(material_id: str, page: ft.Page = None) -> bool:
    """Check if a specific study material has actually been saved locally with cards or questions."""
    if page is not None and getattr(page, "web", False):
        return False
    if not material_id:
        return False
    try:
        db = get_local_db(page)
        row = db.execute(
            """
            SELECT 1 FROM downloaded_study_materials m
            WHERE m.id = ? AND (
                EXISTS (SELECT 1 FROM downloaded_flashcards WHERE material_id = m.id)
                OR EXISTS (SELECT 1 FROM downloaded_study_questions WHERE material_id = m.id)
            )
            LIMIT 1
            """,
            (str(material_id),)
        ).fetchone()
        return row is not None
    except Exception:
        return False


# ── Study Materials & SRS Local DB Operations ─────────────────────────────

def save_study_material_offline(
    material: dict,
    flashcards: list = None,
    questions: list = None,
    page: ft.Page = None,
):
    """
    Saves or updates a study material, its flashcards, and its questions into local SQLite.
    Accepts data dicts directly from the API.
    """
    if page is not None and getattr(page, "web", False):
        return
    mat_id = str(material.get("id"))
    if not mat_id:
        return

    now_iso = datetime.now(timezone.utc).isoformat()
    db = get_local_db(page)

    raw_title = str(material.get("title") or "Untitled Document")
    clean_mat_title = re.sub(r"(?i)\s*[\[\(]\s*pack\s*import\s*[\]\)]\s*[:\-–—]?\s*", " ", raw_title)
    clean_mat_title = re.sub(r"(?i)^pack\s*import\s*[:\-–—]?\s*", "", clean_mat_title).strip() or "Study Pack"

    with db:
        # Upsert material
        db.execute(
            """
            INSERT INTO downloaded_study_materials (id, user_id, title, source_type, content, file_url, downloaded_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                source_type = excluded.source_type,
                content = excluded.content,
                file_url = excluded.file_url,
                updated_at = excluded.updated_at
            """,
            (
                mat_id,
                str(material.get("user_id") or ""),
                clean_mat_title,
                str(material.get("source_type") or "text"),
                str(material.get("content") or material.get("pasted_text") or ""),
                str(material.get("file_url") or ""),
                now_iso,
                now_iso,
            ),
        )

        # Upsert flashcards
        if flashcards:
            for card in flashcards:
                c_id = str(card.get("id"))
                if not c_id:
                    continue
                srs = card.get("srs_state") or {}
                interval = int(card.get("interval_days", srs.get("interval", 0)))
                ease = float(card.get("ease_factor", srs.get("ease_factor", 2.5)))
                reps = int(card.get("repetitions", srs.get("repetitions", 0)))
                next_rev = card.get("next_review_date") or now_iso

                db.execute(
                    """
                    INSERT INTO downloaded_flashcards (id, material_id, user_id, front, back, interval_days, ease_factor, repetitions, next_review_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        front = excluded.front,
                        back = excluded.back,
                        interval_days = excluded.interval_days,
                        ease_factor = excluded.ease_factor,
                        repetitions = excluded.repetitions,
                        next_review_date = excluded.next_review_date
                    """,
                    (
                        c_id,
                        mat_id,
                        str(card.get("user_id") or ""),
                        str(card.get("front") or ""),
                        str(card.get("back") or ""),
                        interval,
                        ease,
                        reps,
                        str(next_rev),
                    ),
                )

        # Upsert questions
        if questions:
            for q in questions:
                q_id = str(q.get("id"))
                if not q_id:
                    continue
                opts = q.get("options") or []
                opts_json = json.dumps(opts) if isinstance(opts, (list, tuple)) else str(opts)

                db.execute(
                    """
                    INSERT INTO downloaded_study_questions (id, material_id, user_id, question_text, options, answer_index, explanation, difficulty, image_url, topic, exam_type, exam_year)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        question_text = excluded.question_text,
                        options = excluded.options,
                        answer_index = excluded.answer_index,
                        explanation = excluded.explanation,
                        difficulty = excluded.difficulty,
                        image_url = excluded.image_url,
                        topic = excluded.topic,
                        exam_type = excluded.exam_type,
                        exam_year = excluded.exam_year
                    """,
                    (
                        q_id,
                        mat_id,
                        str(q.get("user_id") or ""),
                        str(q.get("question") or q.get("question_text") or ""),
                        opts_json,
                        int(q.get("answer", q.get("answer_index", 0))),
                        str(q.get("explanation") or ""),
                        str(q.get("difficulty") or "standard"),
                        str(q.get("image_url") or "") if q.get("image_url") else None,
                        str(q.get("topic") or "") if q.get("topic") else None,
                        str(q.get("exam_type") or "") if q.get("exam_type") else None,
                        int(q["exam_year"]) if q.get("exam_year") is not None else None,
                    ),
                )


def get_offline_study_materials(page: ft.Page = None) -> list:
    """Returns list of downloaded study materials with card and question counts."""
    if page is not None and getattr(page, "web", False):
        return []
    try:
        db = get_local_db(page)
        db.row_factory = sqlite3.Row
        rows = db.execute(
            """
            SELECT 
                m.*,
                (SELECT COUNT(*) FROM downloaded_flashcards WHERE material_id = m.id) as flashcards_count,
                (SELECT COUNT(*) FROM downloaded_study_questions WHERE material_id = m.id) as questions_count
            FROM downloaded_study_materials m
            WHERE (
                EXISTS (SELECT 1 FROM downloaded_flashcards WHERE material_id = m.id)
                OR EXISTS (SELECT 1 FROM downloaded_study_questions WHERE material_id = m.id)
            )
            ORDER BY m.downloaded_at DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[LOCAL DB ERROR] get_offline_study_materials failed: {e}")
        return []


def get_offline_study_material(material_id: str, page: ft.Page = None) -> dict | None:
    """Returns a single downloaded study material by ID."""
    if page is not None and getattr(page, "web", False):
        return None
    try:
        db = get_local_db(page)
        db.row_factory = sqlite3.Row
        row = db.execute(
            "SELECT * FROM downloaded_study_materials WHERE id = ?", (str(material_id),)
        ).fetchone()
        return dict(row) if row else None
    except Exception as e:
        print(f"[LOCAL DB ERROR] get_offline_study_material failed: {e}")
        return None


def delete_offline_study_material(material_id: str, page: ft.Page = None) -> bool:
    """Removes a downloaded study material and cascades to its cards and questions."""
    if page is not None and getattr(page, "web", False):
        return False
    try:
        db = get_local_db(page)
        with db:
            db.execute("DELETE FROM downloaded_study_materials WHERE id = ?", (str(material_id),))
        return True
    except Exception as e:
        print(f"[LOCAL DB ERROR] delete_offline_study_material failed: {e}")
        return False


def get_offline_due_cards(material_ids: list | None = None, all_cards: bool = False, page: ft.Page = None) -> list:
    """
    Returns flashcards from SQLite matching due review date or all cards.
    Formats output identically to GET /study/cards/due.
    """
    if page is not None and getattr(page, "web", False):
        return []
    try:
        db = get_local_db(page)
        db.row_factory = sqlite3.Row
        now_iso = datetime.now(timezone.utc).isoformat()

        query = "SELECT * FROM downloaded_flashcards WHERE 1=1"
        params = []

        if not all_cards:
            query += " AND (next_review_date IS NULL OR next_review_date <= ?)"
            params.append(now_iso)

        if material_ids:
            clean_ids = [str(mid) for mid in material_ids if mid]
            if clean_ids:
                placeholders = ",".join("?" for _ in clean_ids)
                query += f" AND material_id IN ({placeholders})"
                params.extend(clean_ids)

        query += " ORDER BY next_review_date ASC"
        rows = db.execute(query, params).fetchall()

        cards = []
        for r in rows:
            cards.append({
                "id": r["id"],
                "front": r["front"],
                "back": r["back"],
                "material_id": r["material_id"],
                "interval_days": r["interval_days"],
                "ease_factor": r["ease_factor"],
                "repetitions": r["repetitions"],
                "next_review_date": r["next_review_date"],
                "srs_state": {
                    "interval": r["interval_days"],
                    "ease_factor": r["ease_factor"],
                    "repetitions": r["repetitions"],
                },
            })
        return cards
    except Exception as e:
        print(f"[LOCAL DB ERROR] get_offline_due_cards failed: {e}")
        return []


def get_offline_quiz_questions(material_ids: list | None = None, limit: int = 10, page: ft.Page = None) -> list:
    """Returns random questions for a quick quiz from local SQLite."""
    if page is not None and getattr(page, "web", False):
        return []
    try:
        db = get_local_db(page)
        db.row_factory = sqlite3.Row

        query = "SELECT * FROM downloaded_study_questions WHERE 1=1"
        params = []

        if material_ids:
            clean_ids = [str(mid) for mid in material_ids if mid]
            if clean_ids:
                placeholders = ",".join("?" for _ in clean_ids)
                query += f" AND material_id IN ({placeholders})"
                params.extend(clean_ids)

        query += f" ORDER BY RANDOM() LIMIT {int(limit)}"
        rows = db.execute(query, params).fetchall()

        questions = []
        for r in rows:
            try:
                opts = json.loads(r["options"])
            except Exception:
                opts = []
            questions.append({
                "id": r["id"],
                "question": r["question_text"],
                "options": opts,
                "answer": r["answer_index"],
                "explanation": r["explanation"] or "",
                "difficulty": r["difficulty"] if "difficulty" in r.keys() else "standard",
                "image_url": r["image_url"] if "image_url" in r.keys() else None,
                "topic": r["topic"] if "topic" in r.keys() else None,
                "exam_type": r["exam_type"] if "exam_type" in r.keys() else None,
                "exam_year": r["exam_year"] if "exam_year" in r.keys() else None,
            })
        return questions
    except Exception as e:
        print(f"[LOCAL DB ERROR] get_offline_quiz_questions failed: {e}")
        return []


def get_offline_exam_questions(material_ids: list | None = None, limit: int = 50, page: ft.Page = None) -> dict:
    """Returns questions and calculated duration for full exam simulator from local SQLite."""
    if page is not None and getattr(page, "web", False):
        return {"questions": [], "duration_seconds": 300}
    try:
        db = get_local_db(page)
        db.row_factory = sqlite3.Row

        query = "SELECT * FROM downloaded_study_questions WHERE 1=1"
        params = []

        if material_ids:
            clean_ids = [str(mid) for mid in material_ids if mid]
            if clean_ids:
                placeholders = ",".join("?" for _ in clean_ids)
                query += f" AND material_id IN ({placeholders})"
                params.extend(clean_ids)

        query += f" ORDER BY RANDOM() LIMIT {int(limit)}"
        rows = db.execute(query, params).fetchall()

        questions = []
        for r in rows:
            try:
                opts = json.loads(r["options"])
            except Exception:
                opts = []
            questions.append({
                "id": r["id"],
                "question": r["question_text"],
                "options": opts,
                "answer": r["answer_index"],
                "explanation": r["explanation"] or "",
                "difficulty": r["difficulty"] if "difficulty" in r.keys() else "standard",
                "image_url": r["image_url"] if "image_url" in r.keys() else None,
                "topic": r["topic"] if "topic" in r.keys() else None,
                "exam_type": r["exam_type"] if "exam_type" in r.keys() else None,
                "exam_year": r["exam_year"] if "exam_year" in r.keys() else None,
            })

        duration = max(len(questions) * 60, 300)
        return {"questions": questions, "duration_seconds": duration}
    except Exception as e:
        print(f"[LOCAL DB ERROR] get_offline_exam_questions failed: {e}")
        return {"questions": [], "duration_seconds": 300}


def record_offline_flashcard_review(card_id: str, quality: int, page: ft.Page = None) -> dict:
    """
    Applies the SM-2 algorithm locally in SQLite, updates the flashcard's review schedule,
    and enqueues the review into study_review_queue for later cloud sync.
    """
    if page is not None and getattr(page, "web", False):
        return {}
    try:
        db = get_local_db(page)
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()

        row = db.execute(
            "SELECT interval_days, ease_factor, repetitions FROM downloaded_flashcards WHERE id = ?",
            (str(card_id),),
        ).fetchone()

        if not row:
            # Card not found locally, queue review anyway
            with db:
                db.execute(
                    "INSERT INTO study_review_queue (card_id, quality, reviewed_at, synced_at) VALUES (?, ?, ?, NULL)",
                    (str(card_id), int(quality), now_iso),
                )
            return {"next_review_date": now_iso, "interval_days": 1}

        interval_days = int(row[0] or 0)
        ease_factor = float(row[1] or 2.5)
        repetitions = int(row[2] or 0)
        q = int(quality)

        # Standard SM-2 logic matching backend
        if q >= 3:
            if repetitions == 0:
                interval_days = 1
            elif repetitions == 1:
                interval_days = 6
            else:
                interval_days = max(1, round(interval_days * ease_factor))
            repetitions += 1
        else:
            repetitions = 0
            interval_days = 1

        ease_factor = ease_factor + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
        ease_factor = max(1.3, ease_factor)
        next_review_date = (now_dt + timedelta(days=interval_days)).isoformat()

        with db:
            db.execute(
                """
                UPDATE downloaded_flashcards
                SET interval_days = ?, ease_factor = ?, repetitions = ?, next_review_date = ?
                WHERE id = ?
                """,
                (interval_days, ease_factor, repetitions, next_review_date, str(card_id)),
            )
            db.execute(
                "INSERT INTO study_review_queue (card_id, quality, reviewed_at, synced_at) VALUES (?, ?, ?, NULL)",
                (str(card_id), q, now_iso),
            )

        return {"next_review_date": next_review_date, "interval_days": interval_days}
    except Exception as e:
        print(f"[LOCAL DB ERROR] record_offline_flashcard_review failed: {e}")
        return {}


def get_unsynced_study_reviews(page: ft.Page = None) -> list:
    """Returns queued offline flashcard reviews pending synchronization."""
    if page is not None and getattr(page, "web", False):
        return []
    try:
        db = get_local_db(page)
        db.row_factory = sqlite3.Row
        rows = db.execute(
            "SELECT id, card_id, quality, reviewed_at FROM study_review_queue WHERE synced_at IS NULL ORDER BY id ASC"
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[LOCAL DB ERROR] get_unsynced_study_reviews failed: {e}")
        return []


def mark_study_reviews_synced(review_ids: list, page: ft.Page = None):
    """Marks queued reviews as synchronized."""
    if not review_ids:
        return
    try:
        db = get_local_db(page)
        now_iso = datetime.now(timezone.utc).isoformat()
        with db:
            placeholders = ",".join("?" for _ in review_ids)
            db.execute(
                f"UPDATE study_review_queue SET synced_at = ? WHERE id IN ({placeholders})",
                [now_iso] + list(review_ids),
            )
    except Exception as e:
        print(f"[LOCAL DB ERROR] mark_study_reviews_synced failed: {e}")

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
                msg_id = msg.get('id')
                channel_id = msg.get('channel_id')
                if not msg_id or not channel_id:
                    continue
                sender_id = msg.get('sender_id') or (msg.get('sender') or {}).get('id') or ''
                sender_name = msg.get('sender_name') or (msg.get('sender') or {}).get('name') or 'Unknown'
                meta_val = msg.get('metadata_payload', None)
                if isinstance(meta_val, (dict, list)):
                    import json
                    meta_val = json.dumps(meta_val)
                db.execute(
                    "INSERT OR IGNORE INTO chat_channels (id, name, type, role, updated_at) VALUES (?, 'Chat', 'direct', 'member', '')",
                    (str(channel_id),)
                )
                db.execute("""
                    INSERT INTO chat_messages (id, channel_id, sender_id, sender_name, type, content, metadata_payload, created_at, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        sender_name=excluded.sender_name,
                        content=excluded.content,
                        metadata_payload=excluded.metadata_payload,
                        status=excluded.status
                """, (str(msg_id), str(channel_id), str(sender_id), str(sender_name), msg.get('type', 'text'), msg.get('content', ''), meta_val, msg.get('created_at', ''), msg.get('status', 'sent')))
    except Exception as e:
        print(f"[CACHE ERROR] upsert_chat_messages failed: {e}")


def record_exam_attempt(
    material_id: str | None,
    exam_title: str,
    exam_type: str,
    score: int,
    total: int,
    percentage: float,
    scaled_score: int | None = None,
    grade: str | None = None,
    time_spent_seconds: int = 0,
    breakdown_json: str | None = None,
    bundle_id: str | None = None,
    page: ft.Page = None,
) -> str:
    """Records an assessment attempt for longitudinal progress and score trend charting."""
    if page is not None and getattr(page, "web", False):
        return ""
    attempt_id = str(uuid.uuid4())
    attempted_at = datetime.now(timezone.utc).isoformat()
    try:
        db = get_local_db(page)
        with db:
            db.execute(
                """
                INSERT INTO exam_attempts (
                    id, material_id, bundle_id, exam_title, exam_type,
                    score, total, percentage, scaled_score, grade,
                    time_spent_seconds, attempted_at, breakdown_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt_id,
                    str(material_id) if material_id else None,
                    str(bundle_id) if bundle_id else None,
                    exam_title,
                    exam_type,
                    int(score),
                    int(total),
                    float(percentage),
                    int(scaled_score) if scaled_score is not None else None,
                    grade,
                    int(time_spent_seconds),
                    attempted_at,
                    breakdown_json or "{}",
                ),
            )
        return attempt_id
    except Exception as e:
        print(f"[LOCAL DB ERROR] record_exam_attempt failed: {e}")
        return ""


def get_exam_attempts(
    material_id: str | None = None,
    exam_type: str | None = None,
    limit: int = 20,
    page: ft.Page = None,
) -> list[dict]:
    """Retrieves chronological exam attempts for progress analytics and score trajectory charts."""
    if page is not None and getattr(page, "web", False):
        return []
    try:
        db = get_local_db(page)
        db.row_factory = sqlite3.Row
        query = "SELECT * FROM exam_attempts WHERE 1=1"
        params = []
        if material_id:
            query += " AND (material_id = ? OR bundle_id = ?)"
            params.extend([str(material_id), str(material_id)])
        if exam_type:
            query += " AND exam_type = ?"
            params.append(str(exam_type))
        query += f" ORDER BY attempted_at ASC LIMIT {int(limit)}"
        rows = db.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[LOCAL DB ERROR] get_exam_attempts failed: {e}")
        return []