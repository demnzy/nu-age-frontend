"""
src/offline_course_page.py

Offline entrypoint into the SAME course engine used online
(src/course_page.py's course_learner_view). This file does NOT reimplement
any rendering, locking, or lesson-type logic — it only supplies two
functions (fetch + save) that satisfy the exact contract course_page.py
already expects, sourced from local SQLite instead of the network.

Contract, reverse-engineered directly from course_page.py's usage:

    course_data = {
        "course_title": str,
        "completed_lesson_ids": [lesson_id, ...],
        "modules": [
            {
                "id": str,
                "title": str,
                "lessons": [
                    {
                        "id": str,
                        "title": str,
                        "type": str,           # "video" | "audio" | "text" | ...
                        "content": {            # dict, keys dispatch to CONTENT_RENDERERS
                            "video_url": "...",       # -> local file path when offline
                            "audio_path": "...",      # -> local file path when offline
                            "document_url": "...",    # -> local file path when offline
                            "text": "...",             # markdown, unchanged
                            "accompanying_text": "...",# markdown, unchanged
                            "cards": [...],
                            # assessment/scenario lessons carry their own
                            # keys (questions, scenario, choices, prompt_text)
                            # which render_lesson_ui explicitly skips from
                            # the generic dispatch loop and handles via
                            # render_assessment_ui / render_scenario_ui
                            # directly off the lesson dict — untouched here.
                        },
                    },
                    ...
                ],
            },
            ...
        ],
    }

Everything else (recalculate_locks, compute_progress, sidebar building,
assessment scoring, flashcards, etc) lives entirely in course_page.py and
is reused as-is.
"""

import json
import sqlite3
import flet as ft
from src.course_page import course_learner_view
from src.local_db import get_local_db  # adjust import to wherever your sqlite connection helper lives


async def offline_course_learner_view(page: ft.Page, course_id: str, back_target: str = "/courses"):
    async def fetch_course_data(c_id: str):
        db = get_local_db()

        course_row = db.execute(
            "SELECT id, name FROM downloaded_courses WHERE id = ?", (c_id,)
        ).fetchone()

        if not course_row:
            # Not downloaded — course_page.py already handles a falsy/
            # missing "modules" key by showing its own "Failed to load
            # course data" error state, so returning None here reuses
            # that existing failure UI instead of needing a new one.
            return None

        module_rows = db.execute(
            "SELECT id, title, order_index FROM downloaded_modules "
            "WHERE course_id = ? ORDER BY order_index",
            (c_id,),
        ).fetchall()

        modules = []
        for m_id, m_title, _ in module_rows:
            lesson_rows = db.execute(
                "SELECT id, title, type, content FROM downloaded_lessons "
                "WHERE module_id = ? ORDER BY order_index",
                (m_id,),
            ).fetchall()

            lessons = []
            for l_id, l_title, l_type, l_content_json in lesson_rows:
                content = json.loads(l_content_json)
                lessons.append({
                    "id": l_id,
                    "title": l_title,
                    "type": l_type,
                    "content": content,  # asset paths already rewritten to
                                          # local paths at download time —
                                          # see the download manager's
                                          # asset-rewrite step
                })

            modules.append({"id": m_id, "title": m_title, "lessons": lessons})

        # Local, offline-tracked completion state — separate table,
        # never touched by (re)downloading course content. This is what
        # makes "is_done" correct even though the course itself was cached
        # possibly weeks ago.
        completed_rows = db.execute(
            "SELECT lesson_id FROM lesson_progress "
            "WHERE course_id = ? AND status = 'completed'",
            (c_id,),
        ).fetchall()
        completed_lesson_ids = [row[0] for row in completed_rows]

        return {
            "course_title": course_row[1],
            "completed_lesson_ids": completed_lesson_ids,
            "modules": modules,
        }

    async def save_progress(c_id: str, lesson_id: str):
        db = get_local_db()
        now = __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat()

        db.execute(
            """
            INSERT INTO lesson_progress (lesson_id, course_id, status, completed_at, synced_at, updated_at)
            VALUES (?, ?, 'completed', ?, NULL, ?)
            ON CONFLICT(lesson_id) DO UPDATE SET
                status = 'completed',
                completed_at = excluded.completed_at,
                synced_at = NULL,
                updated_at = excluded.updated_at
            """,
            (lesson_id, c_id, now, now),
        )
        db.commit()

        # course_page.py's on_action_click just checks this dict doesn't
        # blow up — it doesn't inspect the return value beyond that, so a
        # simple success marker is enough to satisfy the same code path
        # that normally handles the API response shape.
        return {"success": True, "offline": True}

    return await course_learner_view(
        page,
        course_id,
        fetch_course_data=fetch_course_data,
        save_progress=save_progress,
        back_target=back_target,
    )