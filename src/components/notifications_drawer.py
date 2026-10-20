"""
Reusable In-App Notifications Drawer Utility with Badge Counter.
Provides:
  * get_notification_bell(page, on_open=None): Returns a bell icon with dynamic unread badge.
  * open_notifications_drawer(page): Opens a slide-in bottom sheet / drawer with categorized notifications.
  * add_inapp_notification(page, title, body, category, icon, action_label, on_action): Global notification dispatcher.
"""

from datetime import datetime, timezone
import flet as ft
from src.components.nu_coin_icon import nu_coin_icon

# In-memory store for session notifications
_NOTIFICATIONS_STORE = []


def _format_relative_time(dt: datetime) -> str:
    now = datetime.now(timezone.utc)
    diff = now - dt
    total_sec = max(0, int(diff.total_seconds()))
    if total_sec < 60:
        return "Just now"
    mins = total_sec // 60
    if mins < 60:
        return f"{mins}m ago"
    hours = mins // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def _format_notification_datetime(dt: datetime) -> dict:
    """Returns standardized sectioning and time badges for notifications."""
    if not isinstance(dt, datetime):
        return {
            "section": "Today",
            "time_badge": "Just now",
            "full_time": "",
            "relative": "Just now",
        }
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)

    diff = now - dt
    total_sec = max(0, int(diff.total_seconds()))

    try:
        dt_local = dt.astimezone()
        now_local = now.astimezone()
    except Exception:
        dt_local = dt
        now_local = now

    days_diff = (now_local.date() - dt_local.date()).days
    if days_diff <= 0:
        section = "Today"
    elif days_diff == 1:
        section = "Yesterday"
    elif 1 < days_diff <= 7:
        section = "Earlier this week"
    elif 7 < days_diff <= 30:
        section = "Earlier this month"
    else:
        section = dt_local.strftime("%B %Y")

    time_badge = dt_local.strftime("%I:%M %p").lstrip("0")
    full_date_time = dt_local.strftime("%b %d, %Y · %I:%M %p")

    if total_sec < 60:
        rel = "Just now"
    elif total_sec < 3600:
        rel = f"{total_sec // 60}m ago"
    elif total_sec < 86400:
        rel = f"{total_sec // 3600}h ago"
    else:
        rel = f"{days_diff}d ago" if days_diff > 0 else f"{total_sec // 86400}d ago"

    return {
        "section": section,
        "time_badge": time_badge,
        "full_time": full_date_time,
        "relative": rel,
        "raw_dt": dt,
    }


class NotificationManager:
    _listeners = []

    @classmethod
    def get_all(cls):
        return _NOTIFICATIONS_STORE

    @classmethod
    def get_unread_count(cls) -> int:
        return sum(1 for n in _NOTIFICATIONS_STORE if not n.get("is_read", False))

    @classmethod
    def add(cls, title: str, body: str, category: str = "general", icon=ft.Icons.NOTIFICATIONS_ROUNDED,
            action_label: str = None, on_action=None, notif_id: str = None):
        if notif_id:
            for n in _NOTIFICATIONS_STORE:
                if n.get("id") == notif_id:
                    n["title"] = title
                    n["body"] = body
                    n["category"] = category
                    n["icon"] = icon
                    n["action_label"] = action_label
                    n["on_action"] = on_action
                    cls._notify()
                    return n

        notif = {
            "id": notif_id or str(len(_NOTIFICATIONS_STORE) + 1),
            "title": title,
            "body": body,
            "category": category,   # "exams", "cohorts", "courses", "general"
            "icon": icon,
            "created_at": datetime.now(timezone.utc),
            "is_read": False,
            "action_label": action_label,
            "on_action": on_action,
        }
        _NOTIFICATIONS_STORE.insert(0, notif)
        cls._notify()
        return notif

    @classmethod
    def upsert(cls, notif_id: str, title: str, body: str, category: str = "general",
               icon=ft.Icons.NOTIFICATIONS_ROUNDED, action_label: str = None, on_action=None):
        return cls.add(title=title, body=body, category=category, icon=icon,
                       action_label=action_label, on_action=on_action, notif_id=notif_id)

    @classmethod
    def remove(cls, notif_id: str):
        global _NOTIFICATIONS_STORE
        before = len(_NOTIFICATIONS_STORE)
        _NOTIFICATIONS_STORE = [n for n in _NOTIFICATIONS_STORE if n.get("id") != notif_id]
        if len(_NOTIFICATIONS_STORE) != before:
            cls._notify()

    @classmethod
    def remove_by_category(cls, category: str):
        global _NOTIFICATIONS_STORE
        before = len(_NOTIFICATIONS_STORE)
        _NOTIFICATIONS_STORE = [n for n in _NOTIFICATIONS_STORE if n.get("category") != category]
        if len(_NOTIFICATIONS_STORE) != before:
            cls._notify()

    @classmethod
    def mark_all_read(cls):
        for n in _NOTIFICATIONS_STORE:
            n["is_read"] = True
        cls._notify()

    @classmethod
    def mark_read(cls, notif_id: str):
        for n in _NOTIFICATIONS_STORE:
            if n["id"] == notif_id:
                n["is_read"] = True
                break
        cls._notify()

    @classmethod
    def clear_all(cls):
        _NOTIFICATIONS_STORE.clear()
        cls._notify()

    @classmethod
    def subscribe(cls, callback):
        if callback not in cls._listeners:
            cls._listeners.append(callback)

    @classmethod
    def unsubscribe(cls, callback):
        if callback in cls._listeners:
            cls._listeners.remove(callback)

    @classmethod
    def _notify(cls):
        for cb in list(cls._listeners):
            try:
                cb()
            except Exception:
                pass

    @classmethod
    def serialize_store(cls) -> list:
        """Serializes current in-memory notifications into a JSON-safe structure."""
        out = []
        for n in _NOTIFICATIONS_STORE:
            c_at = n.get("created_at")
            if isinstance(c_at, datetime):
                c_at_str = c_at.isoformat()
            else:
                c_at_str = str(c_at) if c_at else ""

            out.append({
                "id": str(n.get("id", "")),
                "title": str(n.get("title", "")),
                "body": str(n.get("body", "")),
                "category": str(n.get("category", "general")),
                "is_read": bool(n.get("is_read", False)),
                "created_at": c_at_str,
                "action_route": n.get("action_route"),
                "backend_id": n.get("backend_id"),
                "data": n.get("data"),
                "is_claimed": bool(n.get("is_claimed", False)),
            })
        return out

    @classmethod
    def deserialize_and_hydrate(cls, items: list, page: ft.Page = None):
        """Hydrates the in-memory notification store from persistent cache."""
        global _NOTIFICATIONS_STORE
        if not items:
            return

        hydrated = []
        seen_ids = set()
        for item in items:
            nid = str(item.get("id", ""))
            if not nid or nid in seen_ids:
                continue
            seen_ids.add(nid)

            cat = item.get("category", "general")
            if cat == "chat":
                ic = ft.Icons.CHAT_BUBBLE_ROUNDED
            elif cat == "objective_completed":
                ic = ft.Icons.EMOJI_EVENTS_ROUNDED
            elif cat in ("exams", "cohorts"):
                ic = ft.Icons.TIMER_ROUNDED
            elif cat in ("courses", "course_progress"):
                ic = ft.Icons.SCHOOL_ROUNDED
            elif cat in ("discussion", "discussions"):
                ic = ft.Icons.FORUM_ROUNDED
            elif cat == "streak_warning":
                ic = ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED
            elif cat == "duo_nudge":
                ic = ft.Icons.HANDSHAKE_ROUNDED
            elif cat in ("reengagement", "daytime_nudge"):
                ic = ft.Icons.AUTO_AWESOME_ROUNDED
            else:
                ic = ft.Icons.NOTIFICATIONS_ROUNDED

            c_at_raw = item.get("created_at")
            c_at = None
            if c_at_raw:
                try:
                    c_at = datetime.fromisoformat(str(c_at_raw).replace("Z", "+00:00"))
                except Exception:
                    c_at = datetime.now(timezone.utc)
            else:
                c_at = datetime.now(timezone.utc)

            action_route = item.get("action_route")
            def _make_action(rt=action_route):
                def _act():
                    if rt and page:
                        page.go(rt)
                return _act

            hydrated.append({
                "id": nid,
                "title": item.get("title", "Notification"),
                "body": item.get("body", ""),
                "category": cat,
                "icon": ic,
                "created_at": c_at,
                "is_read": bool(item.get("is_read", False)),
                "action_label": "Open" if action_route else None,
                "on_action": _make_action(action_route) if action_route else None,
                "action_route": action_route,
                "backend_id": item.get("backend_id"),
                "data": item.get("data"),
                "is_claimed": bool(item.get("is_claimed", False)),
            })

        if hydrated:
            _NOTIFICATIONS_STORE = hydrated
            cls._notify()

    @classmethod
    async def init_from_cache(cls, page: ft.Page):
        """Loads cached notifications from shared_preferences on cold start (0ms latency)."""
        if not page or not hasattr(page, "shared_preferences"):
            return
        try:
            raw_json = await page.shared_preferences.get("cached_notifications_v1")
            if raw_json:
                import json
                data = json.loads(raw_json)
                if isinstance(data, list):
                    cls.deserialize_and_hydrate(data, page)
                    print(f"[NotificationManager] Hydrated {len(_NOTIFICATIONS_STORE)} cached notification(s). Unread: {cls.get_unread_count()}")
        except Exception as ex:
            print(f"[NotificationManager] Failed reading cache: {ex!r}")

    @classmethod
    async def persist_to_cache(cls, page: ft.Page):
        """Persists the current notification store to shared_preferences."""
        if not page or not hasattr(page, "shared_preferences"):
            return
        try:
            import json
            serialized = cls.serialize_store()
            raw_json = json.dumps(serialized)
            await page.shared_preferences.set("cached_notifications_v1", raw_json)
            await page.shared_preferences.set("cached_unread_notif_count", str(cls.get_unread_count()))
        except Exception as ex:
            print(f"[NotificationManager] Failed persisting cache: {ex!r}")


def get_notification_bell(page: ft.Page, on_open=None) -> ft.Stack:
    """Returns an interactive Bell Icon with a dynamic unread badge counter."""
    badge_text = ft.Text(
        str(NotificationManager.get_unread_count()),
        size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE
    )
    badge_container = ft.Container(
        width=18,
        height=18,
        border_radius=9,
        bgcolor=ft.Colors.RED_600,
        alignment=ft.Alignment.CENTER,
        content=badge_text,
        visible=NotificationManager.get_unread_count() > 0,
        right=2,
        top=2,
    )

    def update_badge():
        count = NotificationManager.get_unread_count()
        badge_text.value = str(count) if count <= 99 else "99+"
        badge_container.visible = count > 0
        try:
            page.update()
        except Exception:
            pass

    NotificationManager.subscribe(update_badge)

    def handle_tap(_):
        if on_open:
            on_open()
        else:
            open_notifications_drawer(page)

    bell_btn = ft.IconButton(
        icon=ft.Icons.NOTIFICATIONS_OUTLINED,
        icon_size=22,
        icon_color=ft.Colors.ON_SURFACE,
        tooltip="Notifications",
        on_click=handle_tap,
    )

    return ft.Stack(
        controls=[bell_btn, badge_container],
        width=44,
        height=44,
    )


def open_notifications_drawer(page: ft.Page):
    """Opens a slide-up notification drawer showing categorized alerts."""
    state = {
        "tab": "all",
    }

    content_area = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)

    def render_notifications():
        items = NotificationManager.get_all()
        tab = state["tab"]
        if tab == "exams":
            filtered = [n for n in items if n.get("category") in ("exams", "cohorts")]
        elif tab == "courses":
            filtered = [n for n in items if n.get("category") in ("courses", "course_progress", "discussion", "discussions")]
        elif tab == "chat":
            filtered = [n for n in items if n.get("category") == "chat"]
        else:
            filtered = items

        # Sort newest first
        filtered_sorted = sorted(
            filtered,
            key=lambda x: x.get("created_at") if isinstance(x.get("created_at"), datetime) else datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )

        sections = {}
        for n in filtered_sorted:
            info = _format_notification_datetime(n.get("created_at"))
            sec_name = info["section"]
            if sec_name not in sections:
                sections[sec_name] = []
            sections[sec_name].append((n, info))

        tiles = []
        for sec_name, group_items in sections.items():
            tiles.append(
                ft.Container(
                    padding=ft.Padding.only(top=8, bottom=4),
                    content=ft.Row([
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                            border_radius=6,
                            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.PRIMARY),
                            content=ft.Text(sec_name.upper(), size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                        ),
                        ft.Divider(height=1, color=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE), expand=True),
                    ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                )
            )

            for n, info in group_items:
                n_id = n["id"]
                is_unread = not n.get("is_read", False)
                cat = n.get("category", "general")

                if cat in ("exams", "cohorts"):
                    cat_color = ft.Colors.ORANGE_600
                elif cat in ("courses", "course_progress", "discussion", "discussions"):
                    cat_color = ft.Colors.DEEP_PURPLE_500 if cat in ("discussion", "discussions") else ft.Colors.BLUE_600
                elif cat == "objective_completed":
                    cat_color = ft.Colors.AMBER_600
                elif cat == "streak_warning":
                    cat_color = ft.Colors.ORANGE_600
                elif cat == "duo_nudge":
                    cat_color = ft.Colors.CYAN_700
                elif cat in ("reengagement", "daytime_nudge"):
                    cat_color = ft.Colors.GREEN_600
                elif cat == "chat":
                    cat_color = ft.Colors.GREEN_600
                else:
                    cat_color = ft.Colors.PRIMARY

                def make_click_handler(target_n):
                    def _do(_):
                        NotificationManager.mark_read(target_n["id"])
                        b_id = target_n.get("backend_id")
                        if b_id:
                            async def _mark_b():
                                try:
                                    t = await page.shared_preferences.get("auth_token")
                                    if t:
                                        from src.requests.notifications import mark_notification_read
                                        await mark_notification_read(t, str(b_id))
                                except Exception:
                                    pass
                            page.run_task(_mark_b)
                        if target_n.get("category") == "objective_completed":
                            async def _open_obj_modal():
                                try:
                                    t = await page.shared_preferences.get("auth_token")
                                    from src.components.objectives_and_leaderboard_modal import show_objectives_and_leaderboard_dialog
                                    show_objectives_and_leaderboard_dialog(page, t, initial_tab="objectives")
                                except Exception as ex:
                                    print(f"[NOTIF_DRAWER] Failed to open objectives dialog: {ex}")
                            page.run_task(_open_obj_modal)
                        elif target_n.get("on_action"):
                            try:
                                target_n["on_action"]()
                            except TypeError:
                                try:
                                    target_n["on_action"](page)
                                except Exception:
                                    pass
                        elif target_n.get("action_route"):
                            try:
                                if hasattr(page, "pop_dialog"):
                                    page.pop_dialog()
                            except Exception:
                                pass
                            page.go(target_n["action_route"])
                        render_notifications()
                        page.update()
                    return _do

                action_btn = None
                if cat == "objective_completed":
                    n_data = n.get("data") if isinstance(n.get("data"), dict) else {}
                    is_claimed = bool(n.get("is_claimed", False) or n_data.get("is_claimed", False))
                    claim_spinner = ft.ProgressRing(width=12, height=12, stroke_width=2, color=ft.Colors.WHITE, visible=False)
                    claim_text = ft.Text("Claim Reward", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
                    claim_icon = nu_coin_icon(size=14)

                    claim_btn = ft.ElevatedButton(
                        content=ft.Row([claim_spinner, claim_icon, claim_text], tight=True, spacing=4),
                        bgcolor=ft.Colors.AMBER_800,
                        height=28,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6), elevation=0),
                    )

                    async def _claim_obj_from_drawer(e, target_n=n, btn=claim_btn, sp=claim_spinner, ic=claim_icon, tx=claim_text):
                        if target_n.get("is_claimed") or getattr(target_n, "_is_claiming", False):
                            return
                        target_n["_is_claiming"] = True
                        btn.disabled = True
                        sp.visible = True
                        ic.visible = False
                        tx.value = "Claiming..."
                        page.update()

                        obj_data = target_n.get("data") if isinstance(target_n.get("data"), dict) else {}
                        obj_code = obj_data.get("code") or target_n.get("objective_code")
                        t = await page.shared_preferences.get("auth_token")
                        if not obj_code or not t:
                            target_n["_is_claiming"] = False
                            from src.components.objectives_and_leaderboard_modal import show_objectives_and_leaderboard_dialog
                            show_objectives_and_leaderboard_dialog(page, t, initial_tab="objectives")
                            return

                        from src.requests.objectives import claim_objective_reward_api
                        from src.utils.file_opener import show_page_snackbar
                        res = await claim_objective_reward_api(t, obj_code)
                        target_n["_is_claiming"] = False
                        if res.get("status") == "success":
                            coins_awarded = res.get("coins_awarded") or obj_data.get("reward") or obj_data.get("reward_coins", "")
                            target_n["is_claimed"] = True
                            orig_b = target_n.get("body", "")
                            if "• Claimed" not in orig_b:
                                target_n["body"] = f"{orig_b} • Claimed (+{coins_awarded} 🪙)"
                            NotificationManager.mark_read(target_n["id"])
                            await NotificationManager.persist_to_cache(page)
                            show_page_snackbar(page, f"🎉 Claimed +{coins_awarded} Nu-Coins! Added to your wallet.")
                            render_notifications()
                            page.update()
                        else:
                            msg = res.get("message", "Already claimed or could not claim.")
                            if "already" in msg.lower():
                                target_n["is_claimed"] = True
                                orig_b = target_n.get("body", "")
                                if "• Claimed" not in orig_b:
                                    target_n["body"] = f"{orig_b} • Claimed"
                                NotificationManager.mark_read(target_n["id"])
                                await NotificationManager.persist_to_cache(page)
                                render_notifications()
                                page.update()
                            else:
                                btn.disabled = False
                                sp.visible = False
                                ic.visible = True
                                tx.value = "Claim Reward"
                                page.update()
                            show_page_snackbar(page, msg)

                    claim_btn.on_click = lambda e, tn=n: page.run_task(_claim_obj_from_drawer, e, tn)

                    if is_claimed:
                        action_btn = ft.Container(
                            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                            border_radius=6,
                            bgcolor=ft.Colors.with_opacity(0.14, ft.Colors.GREEN_600),
                            border=ft.Border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.GREEN_600)),
                            content=ft.Row([
                                ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=12, color=ft.Colors.GREEN_600),
                                ft.Text("Reward Claimed ✓", size=10.5, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_600),
                            ], tight=True, spacing=4),
                        )
                    else:
                        action_btn = claim_btn
                elif n.get("action_label"):
                    action_btn = ft.TextButton(
                        n["action_label"],
                        style=ft.ButtonStyle(color=cat_color, padding=ft.Padding.symmetric(horizontal=8, vertical=4)),
                        on_click=make_click_handler(n),
                    )

                time_badge = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                    border_radius=4,
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                    content=ft.Text(f"{info['time_badge']} · {info['relative']}", size=9, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE_VARIANT),
                )

                unread_dot = ft.Container(
                    width=7, height=7, border_radius=3.5,
                    bgcolor=cat_color,
                    visible=is_unread,
                )

                tile = ft.Container(
                    padding=12,
                    border_radius=12,
                    bgcolor=ft.Colors.with_opacity(0.07, cat_color) if is_unread else ft.Colors.SURFACE,
                    border=ft.Border.all(1.2 if is_unread else 1, ft.Colors.with_opacity(0.24, cat_color) if is_unread else ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    ink=True,
                    scale=1.0,
                    animate_scale=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
                    animate=ft.Animation(220, ft.AnimationCurve.EASE_OUT),
                    on_click=make_click_handler(n),
                    content=ft.Row([
                        ft.Container(
                            padding=8,
                            border_radius=10,
                            bgcolor=ft.Colors.with_opacity(0.14 if is_unread else 0.08, cat_color),
                            content=ft.Icon(n.get("icon", ft.Icons.NOTIFICATIONS_ROUNDED), size=18, color=cat_color),
                        ),
                        ft.Column([
                            ft.Row([
                                ft.Row([
                                    unread_dot,
                                    ft.Text(n.get("title", ""), size=13, weight=ft.FontWeight.BOLD if is_unread else ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE, expand=True),
                                ], spacing=6, expand=True),
                                time_badge,
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.Text(n.get("body", ""), size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Row([action_btn], alignment=ft.MainAxisAlignment.END) if action_btn else ft.Container(),
                        ], spacing=3, expand=True),
                    ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START),
                )

                def _make_drawer_hover(target_tile):
                    def _hover(e):
                        if e.data == "true":
                            target_tile.scale = 1.012
                            target_tile.shadow = ft.BoxShadow(
                                blur_radius=10,
                                spread_radius=0,
                                color=ft.Colors.with_opacity(0.10, ft.Colors.BLACK),
                                offset=ft.Offset(0, 2),
                            )
                        else:
                            target_tile.scale = 1.0
                            target_tile.shadow = None
                        try:
                            target_tile.update()
                        except Exception:
                            pass
                    return _hover

                tile.on_hover = _make_drawer_hover(tile)
                tiles.append(tile)

        if not tiles:
            content_area.controls = [
                ft.Container(
                    alignment=ft.Alignment.CENTER,
                    padding=40,
                    content=ft.Column([
                        ft.Icon(ft.Icons.NOTIFICATIONS_OFF_OUTLINED, size=40, color=ft.Colors.GREY_400),
                        ft.Text("No notifications", size=14, weight=ft.FontWeight.BOLD),
                        ft.Text("You're all caught up! New exam & course alerts will appear here.", size=12, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                )
            ]
        else:
            content_area.controls = tiles

    def switch_tab(tab_key: str):
        state["tab"] = tab_key
        tab_buttons.controls = [
            tab_btn("All", "all"),
            tab_btn("Chat", "chat"),
            tab_btn("Exams & Cohorts", "exams"),
            tab_btn("Courses", "courses"),
        ]
        render_notifications()
        page.update()

    def tab_btn(label: str, key: str):
        is_sel = state["tab"] == key
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            border_radius=16,
            bgcolor=ft.Colors.PRIMARY if is_sel else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
            ink=True,
            on_click=lambda _, k=key: switch_tab(k),
            content=ft.Text(label, size=11, weight=ft.FontWeight.BOLD if is_sel else ft.FontWeight.W_500,
                            color=ft.Colors.WHITE if is_sel else ft.Colors.ON_SURFACE),
        )

    tab_buttons = ft.Row([
        tab_btn("All", "all"),
        tab_btn("Chat", "chat"),
        tab_btn("Exams & Cohorts", "exams"),
        tab_btn("Courses", "courses"),
    ], spacing=6)

    def do_mark_all_read(_):
        NotificationManager.mark_all_read()
        async def _mark_all():
            try:
                t = await page.shared_preferences.get("auth_token")
                if t:
                    from src.requests.notifications import mark_all_notifications_read
                    await mark_all_notifications_read(t)
            except Exception:
                pass
        page.run_task(_mark_all)
        render_notifications()
        page.update()

    def do_clear_all(_):
        NotificationManager.clear_all()
        render_notifications()
        page.update()

    sheet = ft.BottomSheet(
        content=ft.Container(
            padding=16,
            bgcolor=ft.Colors.SURFACE,
            border_radius=ft.BorderRadius.only(top_left=20, top_right=20),
            height=480,
            content=ft.Column([
                # Header row
                ft.Row([
                    ft.Row([
                        ft.Icon(ft.Icons.NOTIFICATIONS_ROUNDED, size=20, color=ft.Colors.PRIMARY),
                        ft.Text("Notifications", size=16, weight=ft.FontWeight.BOLD),
                    ], spacing=8, tight=True),
                    ft.TextButton(
                        "Mark all read",
                        icon=ft.Icons.DONE_ALL_ROUNDED,
                        style=ft.ButtonStyle(
                            color=ft.Colors.PRIMARY,
                            text_style=ft.TextStyle(size=11),
                            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                        ),
                        on_click=do_mark_all_read,
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                tab_buttons,
                ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                content_area,
            ], spacing=10),
        ),
        dismissible=True,
    )

    render_notifications()
    page.overlay.append(sheet)
    sheet.open = True
    page.update()
