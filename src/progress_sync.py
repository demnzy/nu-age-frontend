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

try:
    from src.requests.Courses import api_url as BASE_URL
except Exception:
    BASE_URL = "https://api.nu-age.name.ng"


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
    from src.local_db import get_local_db, get_unsynced_study_reviews, mark_study_reviews_synced

    db = get_local_db(page)
    rows = db.execute(
        """
        SELECT lesson_id, course_id, status, completed_at, quiz_answers, quiz_score
        FROM lesson_progress
        WHERE synced_at IS NULL
        """
    ).fetchall()

    unsynced_reviews = get_unsynced_study_reviews(page)

    if not rows and not unsynced_reviews:
        result.status = "nothing_to_sync"
        return result

    result.total = len(rows) + len(unsynced_reviews)
    result.status = "syncing"

    token = None
    if hasattr(page, "shared_preferences"):
        try:
            token = await page.shared_preferences.get("auth_token")
        except Exception:
            pass
    if not token:
        from src.utils.session_utils import get_session_store
        _s = get_session_store(page)
        if hasattr(_s, "get"):
            token = _s.get("session_auth_token") or _s.get("auth_token") or _s.get("token")
    if not token and hasattr(page, "client_storage"):
        try:
            token = await page.client_storage.get_async("token") or await page.client_storage.get_async("auth_token")
        except Exception:
            pass

    if not token:
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

    synced_count = 0
    now = datetime.now(timezone.utc).isoformat()
    bulk_succeeded = False

    # 1. Primary Strategy: Try bulk-sync for lesson entries (if any exist)
    if entries:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{BASE_URL}/courses/progress/bulk-sync",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"entries": entries},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("results", []):
                        if item.get("status") in ("synced", "skipped_already_completed", "skipped_not_found"):
                            db.execute(
                                "UPDATE lesson_progress SET synced_at = ? WHERE lesson_id = ?",
                                (now, item["lesson_id"]),
                            )
                            synced_count += 1
                    db.commit()
                    bulk_succeeded = True
                elif resp.status_code == 401:
                    result.status = "error"
                    result.error_message = "Session expired — please log in again."
                    return result
                else:
                    print(f"[Sync] bulk-sync rejected with status {resp.status_code}: {resp.text}")
        except httpx.RequestError as ex:
            print(f"[Sync] bulk-sync network error: {ex}")
        except Exception as ex:
            print(f"[Sync] bulk-sync unexpected error: {ex}")

    # 2. Secondary Strategy: If bulk-sync was rejected or failed, sync individually via mark_complete
    if not bulk_succeeded:
        from src.requests.Courses import mark_complete
        for r in rows:
            lesson_id = r[0]
            course_id = r[1]
            try:
                res = await mark_complete(token, course_id, lesson_id)
                err = res.get("error") if isinstance(res, dict) else None
                details = str(res.get("details", "")) if isinstance(res, dict) else ""
                msg = str(res.get("message", "")) if isinstance(res, dict) else ""

                # Check for success, already completed, or obsolete/deleted lesson on server
                is_obsolete = (
                    err == "not_found"
                    or "ForeignKeyViolation" in details
                    or "not present in table" in details
                    or "does not exist or was removed" in msg
                )

                if not err or err in ("already_completed", "not_found") or is_obsolete:
                    if is_obsolete:
                        print(f"[Sync] Lesson {lesson_id} was removed on server; marking progress resolved.")
                    db.execute(
                        "UPDATE lesson_progress SET synced_at = ? WHERE lesson_id = ?",
                        (now, lesson_id),
                    )
                    synced_count += 1
                elif err == "unauthorized":
                    result.status = "error"
                    result.error_message = "Session expired — please log in again."
                    db.commit()
                    return result
                else:
                    print(f"[Sync] Individual mark_complete failed for {lesson_id}: {res}")
            except Exception as ex:
                print(f"[Sync] Exception marking lesson {lesson_id} complete: {ex}")
        db.commit()

    # 3. Synchronize any queued offline flashcard reviews
    try:
        from src.local_db import get_unsynced_study_reviews, mark_study_reviews_synced
        unsynced_reviews = get_unsynced_study_reviews(page)
        if unsynced_reviews and token:
            from src.requests.study import post_review
            synced_review_ids = []
            for rev in unsynced_reviews:
                try:
                    res = await post_review(token, card_id=rev["card_id"], quality=rev["quality"])
                    err_str = str(res.get("error", "")) if isinstance(res, dict) else ""
                    if isinstance(res, dict) and not res.get("error"):
                        synced_review_ids.append(rev["id"])
                    elif "404" in err_str or "not found" in err_str.lower():
                        print(f"[Sync] Flashcard {rev['card_id']} was removed from server; resolving review.")
                        synced_review_ids.append(rev["id"])
                except Exception as rev_err:
                    print(f"[Sync] Flashcard review sync error: {rev_err}")
            if synced_review_ids:
                mark_study_reviews_synced(synced_review_ids, page=page)
                synced_count += len(synced_review_ids)
    except Exception as srs_sync_err:
        print(f"[Sync] Study reviews sync exception: {srs_sync_err}")

    if synced_count > 0:
        result.synced = synced_count
        result.failed = max(0, result.total - synced_count)
        result.status = "done"
    elif result.total == 0:
        result.status = "nothing_to_sync"
    else:
        result.status = "error"
        result.error_message = "Could not sync with server. Check internet connectivity."

    return result


async def has_unsynced_progress(page: ft.Page) -> bool:
    if getattr(page, "web", False):
        return False
    try:
        db = get_local_db(page)
        row = db.execute(
            """
            SELECT 1 FROM lesson_progress WHERE synced_at IS NULL 
            UNION ALL 
            SELECT 1 FROM study_review_queue WHERE synced_at IS NULL 
            LIMIT 1
            """
        ).fetchone()
        return row is not None
    except Exception:
        return False