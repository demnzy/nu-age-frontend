"""
Full-Screen Notifications View / Tab for NU-Age.
Provides rich categorized notifications, urgent exam alerts, and real-time badge updates.
"""

from datetime import datetime, timezone
import flet as ft
from src.components.notifications_drawer import NotificationManager, _format_relative_time, _format_notification_datetime
from src.requests.Cohorts import get_learner_cohorts, start_cohort_exam
from src.components.cohort_exam_runner import build_cohort_exam_view
import asyncio

import asyncio


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


async def notifications_view(page: ft.Page) -> ft.View:
    theme_color = ft.Colors.PRIMARY

    state = {
        "tab": "all",
        "active_exams": [],
        "my_cohorts": [],
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
                            ft.Text("Setting up secure assessment environment...", size=13),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True, spacing=10),
                    )
                    page.update()

                    def return_from_exam(*_):
                        try:
                            page.window.full_screen = False
                            page.update()
                        except Exception:
                            pass
                        content_socket.content = ft.Column([
                            # Top App Bar
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                                content=ft.Row([
                                    ft.IconButton(ft.Icons.ARROW_BACK_ROUNDED, on_click=lambda _: page.go("/dashboard")),
                                    ft.Row([
                                        ft.Text("Notifications & Cohorts", size=18, weight=ft.FontWeight.BOLD),
                                        header_badge_container,
                                    ], spacing=8, tight=True),
                                    ft.Row([
                                        ft.TextButton("Mark read", on_click=do_mark_all_read),
                                        ft.IconButton(ft.Icons.DELETE_SWEEP_OUTLINED, tooltip="Clear all", on_click=do_clear_all),
                                    ], spacing=2, tight=True),
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                            ),
                            ft.Container(padding=ft.Padding.symmetric(horizontal=16), content=tab_row),
                            ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                            ft.Container(padding=ft.Padding.symmetric(horizontal=16, vertical=8), expand=True, content=content_list),
                        ], spacing=8, expand=True)
                        page.run_task(load_active_data)

                    payload = await start_cohort_exam(token, target_ex.get("org_id"), target_ex.get("cohort_id"), target_ex.get("id"))
                    if "error" in payload:
                        err_msg = payload["error"]
                        content_socket.content = ft.Container(
                            expand=True,
                            alignment=ft.Alignment.CENTER,
                            padding=24,
                            content=ft.Container(
                                width=480,
                                padding=32,
                                border_radius=18,
                                bgcolor=ft.Colors.SURFACE,
                                border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                                content=ft.Column([
                                    ft.Container(
                                        width=56, height=56, border_radius=28,
                                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_700),
                                        alignment=ft.Alignment.CENTER,
                                        content=ft.Icon(ft.Icons.LOCK_CLOCK_ROUNDED, size=28, color=ft.Colors.AMBER_700),
                                    ),
                                    ft.Text("Assessment Notice", size=18, weight=ft.FontWeight.BOLD),
                                    ft.Text(
                                        err_msg,
                                        size=13,
                                        color=ft.Colors.ON_SURFACE,
                                        text_align=ft.TextAlign.CENTER,
                                    ),
                                    ft.Container(height=4),
                                    ft.Text(
                                        "If you require an additional attempt or have questions regarding your assessment eligibility, please reach out to your instructor or cohort administrator.",
                                        size=11,
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                        text_align=ft.TextAlign.CENTER,
                                    ),
                                    ft.Container(height=12),
                                    ft.FilledButton(
                                        "Return to Learning Hub",
                                        icon=ft.Icons.ARROW_BACK_ROUNDED,
                                        on_click=return_from_exam,
                                        style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=24, vertical=12)),
                                    ),
                                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                            ),
                        )
                        page.update()
                        return

                    exam_runner = build_cohort_exam_view(
                        page=page,
                        exam_payload=payload,
                        org_id=target_ex.get("org_id"),
                        cohort_id=target_ex.get("cohort_id"),
                        exam_id=target_ex.get("id"),
                        token=token,
                        on_exit=return_from_exam,
                    )
                    content_socket.content = exam_runner
                    page.update()

                page.run_task(_do)
            return _launch

        # 1. Urgent live exam banner if any
        if state["active_exams"] and tab in ("all", "exams"):
            for ex in state["active_exams"]:
                ex_title = ex.get("title", "Assessment")
                ex_org = ex.get("org_name", "Organisation")
                ex_dur = ex.get("duration_minutes", 60)
                is_open = get_effective_exam_status(ex) == "OPEN_NOW"

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
                        ft.Text(f"Organized by {ex_org} · Strict Proctoring Active", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
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

        # 2. My Enrolled Cohorts Hub (For Candidates)
        if state["my_cohorts"] and tab in ("all", "exams"):
            tiles.append(
                ft.Row([
                    ft.Icon(ft.Icons.SCHOOL_ROUNDED, size=18, color=theme_color),
                    ft.Text("My Training Cohorts", size=15, weight=ft.FontWeight.BOLD),
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                        border_radius=10, bgcolor=ft.Colors.with_opacity(0.1, theme_color),
                        content=ft.Text(str(len(state["my_cohorts"])), size=11, weight=ft.FontWeight.BOLD, color=theme_color),
                    ),
                ], spacing=8, tight=True)
            )
            for c in state["my_cohorts"]:
                c_name = c.get("name", "Cohort")
                c_org = c.get("organisation_name", "Organisation")
                c_status = get_effective_cohort_status(c)
                c_courses = c.get("courses", [])
                c_exams = c.get("exams", [])
                c_id = str(c.get("id", ""))

                avg_prog = 0
                if c_courses:
                    avg_prog = round(sum(crs.get("progress", 0) for crs in c_courses) / len(c_courses))

                def make_hub_click(target_cid):
                    return lambda _: page.go(f"/cohorts/{target_cid}")

                cohort_card = ft.Container(
                    padding=14, border_radius=14,
                    bgcolor=ft.Colors.SURFACE,
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
                    ink=True,
                    on_click=make_hub_click(c_id),
                    content=ft.Row([
                        ft.Container(
                            width=38, height=38, border_radius=10,
                            bgcolor=ft.Colors.with_opacity(0.1, theme_color),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(ft.Icons.SCHOOL_ROUNDED, size=20, color=theme_color),
                        ),
                        ft.Column([
                            ft.Row([
                                ft.Text(c_name, size=13, weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                ft.Container(
                                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                    border_radius=6, bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.GREEN_600 if c_status == "ACTIVE" else ft.Colors.BLUE_600),
                                    content=ft.Text(c_status, size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_700 if c_status == "ACTIVE" else ft.Colors.BLUE_700),
                                ),
                            ], spacing=6, tight=True),
                            ft.Text(f"{c_org} · {len(c_courses)} Courses · {len(c_exams)} Assessments · {avg_prog}% Completed", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ], spacing=2, expand=True),
                        ft.FilledButton(
                            "Open Hub",
                            icon=ft.Icons.ARROW_FORWARD_ROUNDED,
                            style=ft.ButtonStyle(bgcolor=theme_color, padding=ft.Padding.symmetric(horizontal=12, vertical=6)),
                            on_click=make_hub_click(c_id),
                        ),
                    ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                )
                tiles.append(cohort_card)

            tiles.append(ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)))

        # Sort newest first
        filtered_sorted = sorted(
            filtered,
            key=lambda x: x.get("created_at") if isinstance(x.get("created_at"), datetime) else datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )

        # Group notifications by date section
        sections = {}
        for n in filtered_sorted:
            info = _format_notification_datetime(n.get("created_at"))
            sec_name = info["section"]
            if sec_name not in sections:
                sections[sec_name] = []
            sections[sec_name].append((n, info))

        for sec_name, group_items in sections.items():
            tiles.append(
                ft.Container(
                    padding=ft.Padding.only(top=10, bottom=4),
                    content=ft.Row([
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=10, vertical=3),
                            border_radius=6,
                            bgcolor=ft.Colors.with_opacity(0.08, theme_color),
                            content=ft.Text(sec_name.upper(), size=10, weight=ft.FontWeight.BOLD, color=theme_color),
                        ),
                        ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE), expand=True),
                    ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                )
            )

            for n, info in group_items:
                is_unread = not n.get("is_read", False)
                cat = n.get("category", "general")

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

                time_badge = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=7, vertical=2.5),
                    border_radius=4,
                    bgcolor=ft.Colors.with_opacity(0.12 if is_unread else 0.05, cat_color if is_unread else ft.Colors.ON_SURFACE),
                    content=ft.Text(
                        f"{info['time_badge']} · {info['relative']}",
                        size=10,
                        weight=ft.FontWeight.BOLD if is_unread else ft.FontWeight.NORMAL,
                        color=cat_color if is_unread else ft.Colors.ON_SURFACE_VARIANT,
                    ),
                )

                unread_dot = ft.Container(
                    width=7, height=7, border_radius=3.5,
                    bgcolor=cat_color,
                    visible=is_unread,
                )

                tile = ft.Container(
                    padding=14,
                    border_radius=12,
                    bgcolor=ft.Colors.with_opacity(0.07, cat_color) if is_unread else ft.Colors.SURFACE,
                    border=ft.Border.all(1.2 if is_unread else 1, ft.Colors.with_opacity(0.24, cat_color) if is_unread else ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    ink=True,
                    on_click=make_tap_handler(n),
                    content=ft.Row([
                        ft.Container(
                            padding=10,
                            border_radius=10,
                            bgcolor=ft.Colors.with_opacity(0.14 if is_unread else 0.08, cat_color),
                            content=ft.Icon(n.get("icon", ft.Icons.NOTIFICATIONS_ROUNDED), size=20, color=cat_color),
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

    # Load background data for exams and cohorts
    async def load_active_data():
        if state["token"]:
            try:
                from src.services.notification_service import sync_learner_notifications
                await sync_learner_notifications(page, force=True)
            except Exception:
                pass
            res = await get_learner_cohorts(state["token"])
            state["active_exams"] = res.get("active_urgent_exams", [])
            state["my_cohorts"] = res.get("cohorts", [])
            update_unread_indicators()
            render_content()
            page.update()

    render_content()
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
