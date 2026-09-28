"""
Background Notification & Alert Sync Service for NU-Age Learner Hub.
Polls learner cohorts and active assessments in the background, synchronizing
in-memory notifications and dynamic bottom app bar badges on cold start,
login, and debounced route transitions.
"""

import time
from datetime import datetime, timezone
import flet as ft
from src.components.notifications_drawer import NotificationManager
from src.requests.Cohorts import get_learner_cohorts

_last_sync_ts = 0.0
_is_syncing = False


def get_effective_cohort_status(cohort: dict) -> str:
    raw = (cohort.get("status") or "").lower()
    if raw in ("archived", "cancelled"):
        return raw.upper()
    start_str = cohort.get("start_date")
    end_str = cohort.get("end_date")
    if not start_str or not end_str:
        return (raw or "upcoming").upper()
    try:
        now = datetime.now(timezone.utc)
        s_dt = datetime.fromisoformat(str(start_str).replace("Z", "+00:00"))
        if s_dt.tzinfo is None:
            s_dt = s_dt.replace(tzinfo=timezone.utc)
        e_dt = datetime.fromisoformat(str(end_str).replace("Z", "+00:00"))
        if e_dt.tzinfo is None:
            e_dt = e_dt.replace(tzinfo=timezone.utc)
        if now < s_dt:
            return "UPCOMING"
        elif s_dt <= now <= e_dt:
            return "ACTIVE"
        else:
            return "COMPLETED"
    except Exception:
        return (raw or "upcoming").upper()


def get_effective_exam_status(exam: dict) -> str:
    raw = (exam.get("status") or "").upper()
    open_str = exam.get("opens_at")
    close_str = exam.get("closes_at")
    if not open_str or not close_str:
        return raw or "SCHEDULED"
    try:
        now = datetime.now(timezone.utc)
        o_dt = datetime.fromisoformat(str(open_str).replace("Z", "+00:00"))
        if o_dt.tzinfo is None:
            o_dt = o_dt.replace(tzinfo=timezone.utc)
        c_dt = datetime.fromisoformat(str(close_str).replace("Z", "+00:00"))
        if c_dt.tzinfo is None:
            c_dt = c_dt.replace(tzinfo=timezone.utc)
        if now < o_dt:
            return "SCHEDULED"
        elif o_dt <= now <= c_dt:
            return "OPEN_NOW"
        else:
            return "CLOSED"
    except Exception:
        return raw or "SCHEDULED"


async def sync_learner_notifications(page: ft.Page, force: bool = False):
    """Fetches learner cohort alerts and active exams, updating NotificationManager
    and bottom app bar badge in the background with a 60s debounce cooldown."""
    global _last_sync_ts, _is_syncing

    now_ts = time.time()
    if not force and (now_ts - _last_sync_ts < 60.0):
        return

    if _is_syncing:
        return

    _is_syncing = True
    try:
        token = None
        try:
            token = await page.shared_preferences.get("auth_token")
        except Exception:
            pass

        if not token and hasattr(page, "session") and hasattr(page.session, "store"):
            token = page.session.store.get("auth_token")

        if not token:
            NotificationManager.clear_all()
            _last_sync_ts = now_ts
            return

        # 1. Fetch persistent user notifications from backend (chat mentions, DMs, announcements, etc.)
        try:
            from src.requests.notifications import get_user_notifications
            b_notifs = await get_user_notifications(token, limit=50)
            items = []
            if isinstance(b_notifs, dict):
                items = b_notifs.get("items") or b_notifs.get("notifications") or []
            if items:
                for item in items:
                    nid = f"backend_{item.get('id')}"
                    cat = item.get("category", "general")
                    
                    if cat == "chat":
                        ic = ft.Icons.CHAT_BUBBLE_ROUNDED
                    elif cat in ("exams", "cohorts"):
                        ic = ft.Icons.TIMER_ROUNDED
                    elif cat == "courses":
                        ic = ft.Icons.SCHOOL_ROUNDED
                    else:
                        ic = ft.Icons.NOTIFICATIONS_ROUNDED
                    
                    c_at = None
                    if item.get("created_at"):
                        try:
                            c_at = datetime.fromisoformat(str(item["created_at"]).replace("Z", "+00:00"))
                        except Exception:
                            c_at = datetime.now(timezone.utc)
                    else:
                        c_at = datetime.now(timezone.utc)
                    
                    action_route = item.get("action_route")
                    def _make_action(rt=action_route):
                        def _act():
                            if rt:
                                page.go(rt)
                        return _act

                    NotificationManager.upsert(
                        notif_id=nid,
                        title=item.get("title", "Notification"),
                        body=item.get("body", ""),
                        category=cat,
                        icon=ic,
                        action_label="Open" if action_route else None,
                        on_action=_make_action(action_route) if action_route else None,
                    )
                    # Sync metadata & read state
                    for store_n in NotificationManager.get_all():
                        if store_n.get("id") == nid:
                            store_n["is_read"] = item.get("is_read", False)
                            store_n["backend_id"] = item.get("id")
                            store_n["action_route"] = action_route
                            if c_at:
                                store_n["created_at"] = c_at
                            break
        except Exception as e:
            print(f"sync_learner_notifications backend sync warning: {e}")

        # 2. Fetch cohorts and active exam assessments
        res = await get_learner_cohorts(token)
        if not isinstance(res, dict) or "error" in res:
            return

        active_exams = res.get("active_urgent_exams", [])
        cohorts = res.get("cohorts", [])

        # Collect current live exam IDs to prune stale notifications
        current_live_exam_ids = set()

        for ex in active_exams:
            ex_id = str(ex.get("id"))
            ex_title = ex.get("title", "Assessment")
            ex_org = ex.get("org_name", "Organisation")
            ex_dur = ex.get("duration_minutes", 60)
            status = get_effective_exam_status(ex)

            if status == "OPEN_NOW":
                current_live_exam_ids.add(f"exam_live_{ex_id}")
                NotificationManager.upsert(
                    notif_id=f"exam_live_{ex_id}",
                    title=f"Assessment Live: {ex_title}",
                    body=f"{ex_org} assessment is open now ({ex_dur}m limit). Tap to begin.",
                    category="exams",
                    icon=ft.Icons.TIMER_ROUNDED,
                )
            elif status == "SCHEDULED":
                # Check if it opens within 24h
                open_str = ex.get("opens_at")
                if open_str:
                    try:
                        o_dt = datetime.fromisoformat(str(open_str).replace("Z", "+00:00"))
                        if o_dt.tzinfo is None:
                            o_dt = o_dt.replace(tzinfo=timezone.utc)
                        diff_sec = (o_dt - datetime.now(timezone.utc)).total_seconds()
                        if 0 < diff_sec <= 86400:
                            hrs = int(diff_sec // 3600)
                            NotificationManager.upsert(
                                notif_id=f"exam_upcoming_{ex_id}",
                                title=f"Upcoming Exam: {ex_title}",
                                body=f"{ex_org} assessment opens in {hrs}h. Review your syllabus.",
                                category="exams",
                                icon=ft.Icons.EVENT_AVAILABLE_ROUNDED,
                            )
                    except Exception:
                        pass

        # Prune stale exam_live notifications if exam is closed or expired
        all_notifs = NotificationManager.get_all()
        for n in list(all_notifs):
            n_id = n.get("id", "")
            if n_id.startswith("exam_live_") and n_id not in current_live_exam_ids:
                NotificationManager.remove(n_id)

        # Persist synced notifications to local cache for instant 0ms cold-start display
        try:
            await NotificationManager.persist_to_cache(page)
        except Exception:
            pass

        _last_sync_ts = time.time()

        # Explicitly trigger persistent nav bar badge refresh if mounted
        nav_bar = getattr(page, "persistent_nav_bar", None)
        if nav_bar and hasattr(nav_bar, "_update_unread_badge"):
            try:
                nav_bar._update_unread_badge()
            except Exception:
                pass

    except Exception as ex:
        print(f"sync_learner_notifications warning: {ex}")
    finally:
        _is_syncing = False
