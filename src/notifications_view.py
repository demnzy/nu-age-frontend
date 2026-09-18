"""
Full-Screen Notifications View / Tab for NU-Age.
Provides rich categorized notifications, urgent exam alerts, and real-time badge updates.
"""

from datetime import datetime, timezone
import flet as ft
from src.components.notifications_drawer import NotificationManager, _format_relative_time
from src.requests.Cohorts import get_learner_cohorts, start_cohort_exam
from src.components.cohort_exam_runner import build_cohort_exam_view
import asyncio


async def notifications_view(page: ft.Page) -> ft.View:
    theme_color = ft.Colors.PRIMARY

    state = {
        "tab": "all",
        "active_exams": [],
        "token": None,
    }

    try:
        state["token"] = await page.shared_preferences.get("auth_token")
    except Exception:
        pass

    content_list = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)

    header_badge = ft.Text(
        str(NotificationManager.get_unread_count()),
        size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE
    )
    header_badge_container = ft.Container(
        padding=ft.Padding.symmetric(horizontal=8, vertical=2),
        border_radius=12,
        bgcolor=ft.Colors.RED_600,
        content=header_badge,
        visible=NotificationManager.get_unread_count() > 0,
    )

    def update_unread_indicators():
        count = NotificationManager.get_unread_count()
        header_badge.value = f"{count} new" if count > 0 else ""
        header_badge_container.visible = count > 0
        try:
            page.update()
        except Exception:
            pass

    NotificationManager.subscribe(update_unread_indicators)

    def render_content():
        items = NotificationManager.get_all()
        tab = state["tab"]
        if tab == "exams":
            filtered = [n for n in items if n.get("category") in ("exams", "cohorts")]
        elif tab == "courses":
            filtered = [n for n in items if n.get("category") == "courses"]
        else:
            filtered = items

        tiles = []

        # Urgent live exam banner if any
        if state["active_exams"] and tab in ("all", "exams"):
            for ex in state["active_exams"]:
                ex_title = ex.get("title", "Assessment")
                ex_org = ex.get("org_name", "Organisation")
                ex_dur = ex.get("duration_minutes", 60)
                is_open = ex.get("status") == "OPEN_NOW"

                def make_exam_launcher(target_ex):
                    def _launch(_):
                        async def _do():
                            token = state["token"]
                            if not token:
                                return
                            content_socket.content = ft.Container(
                                alignment=ft.Alignment.CENTER,
                                padding=40,
                                content=ft.Column([
                                    ft.ProgressRing(color=theme_color, width=32, height=32),
                                    ft.Text("Launching assessment...", size=13),
                                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True, spacing=10),
                            )
                            page.update()

                            payload = await start_cohort_exam(token, target_ex.get("org_id"), target_ex.get("cohort_id"), target_ex.get("id"))
                            if "error" in payload:
                                page.snack_bar = ft.SnackBar(ft.Text(payload["error"]), bgcolor=ft.Colors.RED_700)
                                page.snack_bar.open = True
                                render_content()
                                page.update()
                                return

                            exam_runner = build_cohort_exam_view(
                                page=page,
                                exam_payload=payload,
                                org_id=target_ex.get("org_id"),
                                cohort_id=target_ex.get("cohort_id"),
                                exam_id=target_ex.get("id"),
                                token=token,
                                on_exit=lambda _: page.go("/dashboard"),
                            )
                            content_socket.content = exam_runner
                            page.update()

                        page.run_task(_do)
                    return _launch

                banner = ft.Container(
                    padding=16, border_radius=14,
                    bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.RED_600 if is_open else ft.Colors.BLUE_600),
                    border=ft.Border.all(1.5, ft.Colors.RED_600 if is_open else ft.Colors.BLUE_600),
                    content=ft.Column([
                        ft.Row([
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                border_radius=6, bgcolor=ft.Colors.RED_600 if is_open else ft.Colors.BLUE_600,
                                content=ft.Text("LIVE ASSESSMENT" if is_open else "UPCOMING EXAM", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            ),
                            ft.Text(f"{ex_dur} Mins Limit", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_700 if is_open else ft.Colors.BLUE_700),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Text(ex_title, size=15, weight=ft.FontWeight.BOLD),
                        ft.Text(f"Organized by {ex_org} · Proctoring Active", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Container(height=4),
                        ft.FilledButton(
                            "Begin Assessment Now",
                            icon=ft.Icons.PLAY_ARROW_ROUNDED,
                            style=ft.ButtonStyle(bgcolor=ft.Colors.RED_700 if is_open else ft.Colors.BLUE_700),
                            on_click=make_exam_launcher(ex),
                            visible=is_open,
                        ),
                    ], spacing=6),
                )
                tiles.append(banner)

        for n in filtered:
            is_unread = not n.get("is_read", False)
            cat = n.get("category", "general")
            time_str = _format_relative_time(n["created_at"])

            if cat in ("exams", "cohorts"):
                cat_color = ft.Colors.ORANGE_600
            elif cat == "courses":
                cat_color = ft.Colors.BLUE_600
            else:
                cat_color = ft.Colors.PRIMARY

            def make_tap_handler(notif):
                def _do(_):
                    NotificationManager.mark_read(notif["id"])
                    update_unread_indicators()
                    if notif.get("on_action"):
                        notif["on_action"]()
                    render_content()
                    page.update()
                return _do

            tile = ft.Container(
                padding=14,
                border_radius=12,
                bgcolor=ft.Colors.with_opacity(0.06, cat_color) if is_unread else ft.Colors.SURFACE,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.2, cat_color) if is_unread else ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                ink=True,
                on_click=make_tap_handler(n),
                content=ft.Row([
                    ft.Container(
                        padding=10,
                        border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.12, cat_color),
                        content=ft.Icon(n.get("icon", ft.Icons.NOTIFICATIONS_ROUNDED), size=20, color=cat_color),
                    ),
                    ft.Column([
                        ft.Row([
                            ft.Text(n.get("title", ""), size=13, weight=ft.FontWeight.BOLD if is_unread else ft.FontWeight.W_600, expand=True),
                            ft.Text(time_str, size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Text(n.get("body", ""), size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], spacing=3, expand=True),
                ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START),
            )
            tiles.append(tile)

        if not tiles:
            content_list.controls = [
                ft.Container(
                    alignment=ft.Alignment.CENTER,
                    padding=60,
                    content=ft.Column([
                        ft.Icon(ft.Icons.NOTIFICATIONS_OFF_OUTLINED, size=48, color=ft.Colors.GREY_400),
                        ft.Text("No notifications yet", size=16, weight=ft.FontWeight.BOLD),
                        ft.Text("When new exams, cohorts, or course announcements arrive, they will show up here.", size=12, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                )
            ]
        else:
            content_list.controls = tiles

    def switch_tab(tab_key: str):
        state["tab"] = tab_key
        tab_row.controls = [
            tab_btn("All", "all"),
            tab_btn("Exams & Cohorts", "exams"),
            tab_btn("Courses", "courses"),
        ]
        render_content()
        page.update()

    def tab_btn(label: str, key: str):
        is_sel = state["tab"] == key
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=14, vertical=6),
            border_radius=16,
            bgcolor=theme_color if is_sel else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
            ink=True,
            on_click=lambda _, k=key: switch_tab(k),
            content=ft.Text(label, size=12, weight=ft.FontWeight.BOLD if is_sel else ft.FontWeight.W_500,
                            color=ft.Colors.WHITE if is_sel else ft.Colors.ON_SURFACE),
        )

    tab_row = ft.Row([
        tab_btn("All", "all"),
        tab_btn("Exams & Cohorts", "exams"),
        tab_btn("Courses", "courses"),
    ], spacing=8)

    def do_mark_all_read(_):
        NotificationManager.mark_all_read()
        update_unread_indicators()
        render_content()
        page.update()

    def do_clear_all(_):
        NotificationManager.clear_all()
        update_unread_indicators()
        render_content()
        page.update()

    # Load background data for exams
    async def load_active_data():
        if state["token"]:
            res = await get_learner_cohorts(state["token"])
            state["active_exams"] = res.get("active_urgent_exams", [])
            for ex in state["active_exams"]:
                if ex.get("status") == "OPEN_NOW":
                    NotificationManager.add(
                        title=f"Assessment Live: {ex.get('title')}",
                        body=f"{ex.get('org_name')} assessment is open now ({ex.get('duration_minutes')}m limit).",
                        category="exams",
                        icon=ft.Icons.TIMER_ROUNDED,
                    )
            update_unread_indicators()
            render_content()
            page.update()

    page.run_task(load_active_data)

    content_socket = ft.Container(
        expand=True,
        content=ft.Column([
            # Top App Bar
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                content=ft.Row([
                    ft.IconButton(ft.Icons.ARROW_BACK_ROUNDED, on_click=lambda _: page.go("/dashboard")),
                    ft.Row([
                        ft.Text("Notifications", size=18, weight=ft.FontWeight.BOLD),
                        header_badge_container,
                    ], spacing=8, tight=True),
                    ft.Row([
                        ft.TextButton("Mark read", on_click=do_mark_all_read),
                        ft.IconButton(ft.Icons.DELETE_SWEEP_OUTLINED, tooltip="Clear all", on_click=do_clear_all),
                    ], spacing=2, tight=True),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ),
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=16),
                content=tab_row,
            ),
            ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=16, vertical=8),
                expand=True,
                content=content_list,
            ),
        ], spacing=8, expand=True),
    )

    render_content()

    from src.components.bottom_appbar import PersistentBottomAppBar
    bar_instance = PersistentBottomAppBar(page)

    return ft.View(
        route="/notifications",
        controls=[content_socket],
        bottom_appbar=bar_instance.bar,
        padding=0,
    )
