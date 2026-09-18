"""
Reusable In-App Notifications Drawer Utility with Badge Counter.
Provides:
  * get_notification_bell(page, on_open=None): Returns a bell icon with dynamic unread badge.
  * open_notifications_drawer(page): Opens a slide-in bottom sheet / drawer with categorized notifications.
  * add_inapp_notification(page, title, body, category, icon, action_label, on_action): Global notification dispatcher.
"""

from datetime import datetime, timezone
import flet as ft

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
            action_label: str = None, on_action=None):
        notif = {
            "id": str(len(_NOTIFICATIONS_STORE) + 1),
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
            filtered = [n for n in items if n.get("category") == "courses"]
        else:
            filtered = items

        tiles = []
        for n in filtered:
            n_id = n["id"]
            is_unread = not n.get("is_read", False)
            cat = n.get("category", "general")
            time_label = _format_relative_time(n["created_at"])

            if cat in ("exams", "cohorts"):
                cat_color = ft.Colors.ORANGE_600
            elif cat == "courses":
                cat_color = ft.Colors.BLUE_600
            else:
                cat_color = ft.Colors.PRIMARY

            def make_click_handler(target_n):
                def _do(_):
                    NotificationManager.mark_read(target_n["id"])
                    if target_n.get("on_action"):
                        target_n["on_action"]()
                    render_notifications()
                    page.update()
                return _do

            action_btn = None
            if n.get("action_label"):
                action_btn = ft.TextButton(
                    n["action_label"],
                    style=ft.ButtonStyle(color=cat_color, padding=ft.Padding.symmetric(horizontal=8, vertical=4)),
                    on_click=make_click_handler(n),
                )

            tile = ft.Container(
                padding=12,
                border_radius=12,
                bgcolor=ft.Colors.with_opacity(0.06, cat_color) if is_unread else ft.Colors.SURFACE,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.18, cat_color) if is_unread else ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                ink=True,
                on_click=make_click_handler(n),
                content=ft.Row([
                    ft.Container(
                        padding=8,
                        border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.12, cat_color),
                        content=ft.Icon(n.get("icon", ft.Icons.NOTIFICATIONS_ROUNDED), size=18, color=cat_color),
                    ),
                    ft.Column([
                        ft.Row([
                            ft.Text(n.get("title", ""), size=13, weight=ft.FontWeight.BOLD if is_unread else ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE, expand=True),
                            ft.Text(time_label, size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Text(n.get("body", ""), size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Row([action_btn], alignment=ft.MainAxisAlignment.END) if action_btn else ft.Container(),
                    ], spacing=2, expand=True),
                ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START),
            )
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
        tab_btn("Exams & Cohorts", "exams"),
        tab_btn("Courses", "courses"),
    ], spacing=6)

    def do_mark_all_read(_):
        NotificationManager.mark_all_read()
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
                    ft.Row([
                        ft.TextButton("Mark all read", style=ft.ButtonStyle(text_style=ft.TextStyle(size=11)), on_click=do_mark_all_read),
                        ft.IconButton(ft.Icons.CLEAR_ALL_ROUNDED, icon_size=18, tooltip="Clear all", on_click=do_clear_all),
                    ], spacing=2, tight=True),
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
