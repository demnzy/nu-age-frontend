"""
src/progress_sync.py

Pushes locally-tracked lesson progress (written by
offline_course_page.py's save_progress) up to
POST /courses/progress/bulk-sync whenever the app has connectivity.

Reads lesson_progress WHERE synced_at IS NULL, sends them as one batch,
and on success marks each returned lesson_id's synced_at. Rows the server
didn't confirm are left unsynced and retried on the next call — safe to
call this repeatedly (on reconnect, on app resume, on a manual "sync now"
button) without risk of double-counting, since the server's bulk-sync
endpoint already upserts by lesson_id rather than blindly inserting.
"""

import json
import httpx
import flet as ft
from datetime import datetime, timezone
from src.local_db import get_local_db

BASE_URL = "..."  # reuse your existing API base


class SyncResult:
    def __init__(self):
        self.status = "pending"        # pending | syncing | done | error | nothing_to_sync
        self.total = 0
        self.synced = 0
        self.failed = 0
        self.error_message = None


async def sync_offline_progress(page: ft.Page, result: SyncResult = None) -> SyncResult:
    result = result or SyncResult()
    if getattr(page, "web", False):
        result.status = "nothing_to_sync"
        return result
    db = get_local_db(page)

    rows = db.execute(
        """
        SELECT lesson_id, course_id, status, completed_at, quiz_answers, quiz_score
        FROM lesson_progress
        WHERE synced_at IS NULL
        """
    ).fetchall()

    if not rows:
        result.status = "nothing_to_sync"
        return result

    result.total = len(rows)
    result.status = "syncing"

    token = await page.shared_preferences.get("auth_token")
    if not token:
        # No valid session to sync under. Not an error — just can't
        # proceed right now. Leave everything unsynced for next attempt,
        # after route_change's normal refresh-token flow (re)establishes
        # a token.
        result.status = "error"
        result.error_message = "Not logged in."
        return result

    entries = [
        {
            "lesson_id": r[0],
            "course_id": r[1],
            "status": r[2],
            "completed_at": r[3],
            "quiz_answers": json.loads(r[4]) if r[4] else None,
            "quiz_score": r[5],
        }
        for r in rows
    ]

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{BASE_URL}/courses/progress/bulk-sync",
                headers={"Authorization": f"Bearer {token}"},
                json={"entries": entries},
            )
    except httpx.RequestError as ex:
        # Network failure mid-sync — not a "session ended" situation, just
        # try again next time. Nothing is marked synced.
        result.status = "error"
        result.error_message = f"Network error: {ex}"
        return result

    if resp.status_code == 401:
        # Access token was dead and this call didn't go through
        # route_change's refresh machinery (sync can run from a background
        # task, not just navigation). Don't clear tokens here — that's
        # route_change's job, and it'll sort itself out on next navigation
        # or resume. Just report failure so the caller can decide whether
        # to retry immediately after a manual refresh attempt.
        result.status = "error"
        result.error_message = "Session expired — will retry after next login."
        return result

    if resp.status_code != 200:
        result.status = "error"
        result.error_message = f"Server rejected sync ({resp.status_code})."
        return result

    data = resp.json()
    now = datetime.now(timezone.utc).isoformat()

    synced_count = 0
    for item in data.get("results", []):
        # Both "synced" and "skipped_already_completed" mean the server
        # has authoritative state for this lesson now — either way, this
        # local row no longer needs to be retried.
        if item.get("status") in ("synced", "skipped_already_completed"):
            db.execute(
                "UPDATE lesson_progress SET synced_at = ? WHERE lesson_id = ?",
                (now, item["lesson_id"]),
            )
            synced_count += 1

    db.commit()

    result.synced = synced_count
    result.failed = result.total - synced_count
    result.status = "done"
    return result


async def has_unsynced_progress(page: ft.Page) -> bool:
    if getattr(page, "web", False):
        return False
    try:
        db = get_local_db(page)
        row = db.execute(
            "SELECT 1 FROM lesson_progress WHERE synced_at IS NULL LIMIT 1"
        ).fetchone()
        return row is not None
    except Exception:
        return False