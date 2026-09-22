"""
Organisation Cohorts & Trainings Hub:
  * Cohort list, status filters, search, and KPI overview.
  * Cohort creation wizard with course selection and member assignment.
  * Cohort detail hub: Overview, Courses, Members Roster, and Scheduled Exams.
  * Scheduled Exam Builder & Question Bank (Manual + Bulk Excel/CSV Upload).
  * Exam Gradebook with live candidate leaderboard and CSV export.
  * Integration with Candidate Exam Runner.
"""

import asyncio
from datetime import datetime, timezone, timedelta, time
import flet as ft

from src.components.cohort_exam_runner import build_cohort_exam_view
from src.requests.Cohorts import (
    create_cohort,
    get_cohorts,
    get_cohort_details,
    update_cohort,
    delete_cohort,
    add_cohort_courses,
    remove_cohort_course,
    add_cohort_members,
    remove_cohort_member,
    create_cohort_exam,
    get_cohort_exam,
    update_cohort_exam,
    delete_cohort_exam,
    add_exam_question,
    update_exam_question,
    delete_exam_question,
    upload_exam_questions_file,
    get_exam_question_template_csv,
    start_cohort_exam,
    get_exam_gradebook,
    export_exam_gradebook_csv,
)

_INPUT = {
    "border_color": ft.Colors.with_opacity(0.20, ft.Colors.ON_SURFACE),
    "focused_border_color": ft.Colors.PRIMARY,
    "cursor_color": ft.Colors.PRIMARY,
    "border_radius": 10,
    "width": float("inf"),
    "text_size": 13,
    "content_padding": ft.Padding.symmetric(horizontal=14, vertical=12),
}



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


def build_cohorts_tab(
    page: ft.Page,
    org_id: str,
    org_data: dict,
    token: str,
    is_admin: bool,
    org_courses: list,
    org_members: list,
    theme_color=ft.Colors.PRIMARY,
    on_refresh_parent=None,
):
    container = ft.Container(expand=True)

    state = {
        "cohorts": [],
        "filter": "ALL",
        "search": "",
        "active_cohort_id": None,
        "active_cohort_data": None,
        "loading": True,
    }

    def is_mobile():
        w = page.width or (getattr(page.window, "width", 1000))
        return w < 720

    def show_snack(text: str, is_error: bool = False):
        snack = ft.SnackBar(
            content=ft.Text(text, size=13, color=ft.Colors.WHITE),
            bgcolor=ft.Colors.RED_700 if is_error else ft.Colors.GREEN_700,
            duration=3200,
            behavior=ft.SnackBarBehavior.FLOATING,
        )
        try:
            page.overlay.append(snack)
            snack.open = True
            page.update()
        except Exception:
            pass

    def show_confirm_dialog(title: str, message: str, confirm_label: str, on_confirm, is_destructive: bool = True):
        def do_action(e):
            try:
                page.pop_dialog()
            except Exception:
                pass
            page.run_task(on_confirm)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(
                    ft.Icons.WARNING_AMBER_ROUNDED if is_destructive else ft.Icons.INFO_OUTLINE_ROUNDED,
                    color=ft.Colors.RED_500 if is_destructive else theme_color,
                    size=22,
                ),
                ft.Text(title, weight=ft.FontWeight.BOLD, size=16),
            ], spacing=8),
            content=ft.Text(message, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: page.pop_dialog()),
                ft.FilledButton(
                    confirm_label,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.RED_600 if is_destructive else theme_color,
                        color=ft.Colors.WHITE,
                    ),
                    on_click=do_action,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.show_dialog(dlg)

    def format_date_str(iso_str: str) -> str:
        if not iso_str: return "—"
        try:
            dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            return dt.strftime("%b %d, %Y")
        except Exception:
            return iso_str[:10]

    # ── LOAD COHORTS ─────────────────────────────────────────────────────
    async def load_cohorts_data():
        state["loading"] = True
        render_main_cohorts_view()
        page.update()

        cohorts = await get_cohorts(token, org_id)
        state["cohorts"] = cohorts if isinstance(cohorts, list) else []
        state["loading"] = False
        render_main_cohorts_view()
        page.update()

    # ── CREATE COHORT MODAL ──────────────────────────────────────────────
    def open_create_cohort_dialog(e=None):
        name_field = ft.TextField(label="Cohort Name *", hint_text="e.g. 2026 Tech Scholarship Cohort", **_INPUT)
        desc_field = ft.TextField(label="Description", hint_text="Program goals, timeline, and requirements...", multiline=True, min_lines=2, max_lines=3, **_INPUT)

        now_dt = datetime.now()
        three_months_dt = now_dt + timedelta(days=90)

        start_date_val = [now_dt.date()]
        end_date_val = [three_months_dt.date()]

        start_btn_text = ft.Text(start_date_val[0].strftime("%b %d, %Y"), size=13, weight=ft.FontWeight.W_600)
        end_btn_text = ft.Text(end_date_val[0].strftime("%b %d, %Y"), size=13, weight=ft.FontWeight.W_600)

        def on_start_change(e=None):
            if e and getattr(e, "control", None) and e.control.value:
                val = e.control.value
                start_date_val[0] = val.date() if isinstance(val, datetime) else val
                start_btn_text.value = start_date_val[0].strftime("%b %d, %Y")
                page.update()

        def on_end_change(e=None):
            if e and getattr(e, "control", None) and e.control.value:
                val = e.control.value
                end_date_val[0] = val.date() if isinstance(val, datetime) else val
                end_btn_text.value = end_date_val[0].strftime("%b %d, %Y")
                page.update()

        start_picker = ft.DatePicker(
            value=now_dt,
            first_date=now_dt - timedelta(days=365),
            last_date=now_dt + timedelta(days=365 * 5),
            on_change=on_start_change,
        )
        end_picker = ft.DatePicker(
            value=three_months_dt,
            first_date=now_dt - timedelta(days=365),
            last_date=now_dt + timedelta(days=365 * 5),
            on_change=on_end_change,
        )
        page.overlay.extend([start_picker, end_picker])

        def open_start_picker(_):
            start_picker.open = True
            page.update()

        def open_end_picker(_):
            end_picker.open = True
            page.update()

        start_picker_btn = ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            border_radius=10,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE)),
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
            ink=True,
            on_click=open_start_picker,
            content=ft.Row([
                ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, size=18, color=theme_color),
                ft.Column([
                    ft.Text("Start Date", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                    start_btn_text,
                ], spacing=1, expand=True),
            ], spacing=8),
        )

        end_picker_btn = ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            border_radius=10,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE)),
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
            ink=True,
            on_click=open_end_picker,
            content=ft.Row([
                ft.Icon(ft.Icons.EVENT_REPEAT_ROUNDED, size=18, color=theme_color),
                ft.Column([
                    ft.Text("End Date", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                    end_btn_text,
                ], spacing=1, expand=True),
            ], spacing=8),
        )

        # Courses selection checkboxes
        course_checks = []
        for c in org_courses:
            c_id = str(c.get("id", ""))
            c_name = c.get("name", "Untitled Course")
            course_checks.append(ft.Checkbox(label=c_name, data=c_id, value=False))

        # Members selection checkboxes
        member_checks = []
        for m in org_members:
            m_id = str(m.get("id", "") or m.get("user_id", ""))
            m_name = f"{m.get('first_name', '')} {m.get('last_name', '')}".strip() or m.get("email", "")
            m_role = m.get("role", "student")
            member_checks.append(ft.Checkbox(label=f"{m_name} ({m_role})", data=m_id, value=False))

        def select_all_members(e=None):
            if e and getattr(e, "control", None):
                for chk in member_checks:
                    chk.value = e.control.value
                page.update()

        all_members_toggle = ft.Checkbox(label="Select All Members", value=False, on_change=select_all_members)

        async def do_create(e=None):
            if not name_field.value or not name_field.value.strip():
                show_snack("Cohort name is required.", is_error=True)
                return

            s_dt = datetime.combine(start_date_val[0], datetime.min.time()).replace(tzinfo=timezone.utc)
            e_dt = datetime.combine(end_date_val[0], datetime.max.time()).replace(tzinfo=timezone.utc)

            if e_dt <= s_dt:
                show_snack("End date must be after start date.", is_error=True)
                return

            selected_courses = [chk.data for chk in course_checks if chk.value]
            selected_members = [chk.data for chk in member_checks if chk.value]

            payload = {
                "name": name_field.value.strip(),
                "description": desc_field.value.strip() if desc_field.value else None,
                "start_date": s_dt.isoformat(),
                "end_date": e_dt.isoformat(),
                "course_ids": selected_courses,
                "member_ids": selected_members,
            }

            res = await create_cohort(token, org_id, payload)
            if "error" in res:
                show_snack(f"Failed to create cohort: {res['error']}", is_error=True)
            else:
                if hasattr(page, "pop_dialog"):
                    page.pop_dialog()
                show_snack("Cohort created successfully!")
                await load_cohorts_data()

        dialog_content = ft.Container(
            width=min(getattr(page, "width", 800) - 32, 540),
            height=460,
            content=ft.Column([
                name_field,
                desc_field,
                ft.Row([
                    ft.Container(content=start_picker_btn, expand=True),
                    ft.Container(content=end_picker_btn, expand=True),
                ], spacing=10),
                ft.Divider(height=1, color=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
                ft.Text("Assign Courses to Cohort:", size=12, weight=ft.FontWeight.BOLD),
                ft.Column(course_checks, spacing=4) if course_checks else ft.Text("No organization courses created yet.", size=11, italic=True),
                ft.Divider(height=1, color=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
                ft.Row([
                    ft.Text("Enroll Members into Cohort:", size=12, weight=ft.FontWeight.BOLD),
                    all_members_toggle,
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Column(member_checks, spacing=4) if member_checks else ft.Text("No organization members found.", size=11, italic=True),
            ], scroll=ft.ScrollMode.AUTO, spacing=12),
        )

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.Icons.SCHOOL_ROUNDED, color=theme_color, size=22),
                ft.Text("Create Training Cohort", weight=ft.FontWeight.BOLD, size=16),
            ], spacing=8),
            content=dialog_content,
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: page.pop_dialog()),
                ft.FilledButton("Create Cohort", on_click=lambda _: page.run_task(do_create), style=ft.ButtonStyle(bgcolor=theme_color)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        if hasattr(page, "show_dialog"):
            page.show_dialog(dlg)
        else:
            page.dialog = dlg
            dlg.open = True
            page.update()

    # ── MAIN COHORTS LIST VIEW ───────────────────────────────────────────
    def render_main_cohorts_view():
        if state["loading"]:
            container.content = ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=40,
                content=ft.Column([
                    ft.ProgressRing(color=theme_color, width=32, height=32),
                    ft.Text("Loading Training Cohorts...", size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True, spacing=12),
            )
            return

        all_cohorts = state["cohorts"]
        filtered = []
        for c in all_cohorts:
            st = get_effective_cohort_status(c)
            if state["filter"] != "ALL" and st != state["filter"]:
                continue
            if state["search"]:
                q = state["search"].lower()
                if q not in c.get("name", "").lower() and q not in (c.get("description") or "").lower():
                    continue
            filtered.append(c)

        # KPI Counter Cards
        active_count = sum(1 for c in all_cohorts if get_effective_cohort_status(c) == "ACTIVE")
        upcoming_count = sum(1 for c in all_cohorts if get_effective_cohort_status(c) == "UPCOMING")
        completed_count = sum(1 for c in all_cohorts if get_effective_cohort_status(c) == "COMPLETED")

        def kpi_card(label: str, count: int, icon_name, color):
            return ft.Container(
                expand=True,
                padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                border_radius=14,
                bgcolor=ft.Colors.with_opacity(0.06, color),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.18, color)),
                shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.04, color), offset=ft.Offset(0, 2)),
                content=ft.Row([
                    ft.Container(
                        width=38, height=38, border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.15, color),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(icon_name, size=19, color=color),
                    ),
                    ft.Column([
                        ft.Text(str(count), size=20, weight=ft.FontWeight.BOLD, color=color),
                        ft.Text(label, size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
                    ], spacing=1),
                ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            )

        kpis = ft.Row([
            kpi_card("Active Cohorts", active_count, ft.Icons.PLAY_ARROW_ROUNDED, ft.Colors.GREEN_600),
            kpi_card("Upcoming", upcoming_count, ft.Icons.UPCOMING_ROUNDED, ft.Colors.BLUE_600),
            kpi_card("Completed", completed_count, ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, ft.Colors.GREY_600),
        ], spacing=10)

        # Filter Pills
        def filter_pill(label: str, key: str):
            is_sel = state["filter"] == key
            return ft.Container(
                padding=ft.Padding.symmetric(horizontal=14, vertical=7),
                border_radius=20,
                bgcolor=theme_color if is_sel else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                border=ft.Border.all(1, theme_color if is_sel else ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
                shadow=ft.BoxShadow(blur_radius=6, color=ft.Colors.with_opacity(0.25, theme_color)) if is_sel else None,
                ink=True,
                on_click=lambda _, k=key: set_filter(k),
                content=ft.Text(label, size=11, weight=ft.FontWeight.BOLD if is_sel else ft.FontWeight.W_500,
                                color=ft.Colors.WHITE if is_sel else ft.Colors.ON_SURFACE),
            )

        def set_filter(k: str):
            state["filter"] = k
            render_main_cohorts_view()
            page.update()

        filter_bar = ft.Row([
            filter_pill("All Cohorts", "ALL"),
            filter_pill("Active", "ACTIVE"),
            filter_pill("Upcoming", "UPCOMING"),
            filter_pill("Completed", "COMPLETED"),
        ], spacing=6, scroll=ft.ScrollMode.AUTO)

        # Search box
        def on_search_change(e=None):
            if e and getattr(e, "control", None) and e.control.value is not None:
                state["search"] = e.control.value.strip()
                render_main_cohorts_view()
                page.update()

        search_input = ft.TextField(
            hint_text="Search cohort by name or topic...",
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            border_radius=10,
            text_size=12,
            height=42,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=0),
            border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
            focused_border_color=theme_color,
            on_change=on_search_change,
            expand=True,
        )

        create_btn = ft.FilledButton(
            content=ft.Row([
                ft.Icon(ft.Icons.ADD_ROUNDED, size=16, color=ft.Colors.WHITE),
                ft.Text("New Cohort", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
            ], tight=True, spacing=6),
            style=ft.ButtonStyle(bgcolor=theme_color, padding=ft.Padding.symmetric(horizontal=16, vertical=11)),
            on_click=open_create_cohort_dialog,
        )

        # Cohort Cards
        cohort_cards = []
        for c in filtered:
            c_id = str(c["id"])
            c_name = c.get("name", "Untitled Cohort")
            c_desc = c.get("description") or "No description provided."
            c_status = get_effective_cohort_status(c)
            s_date = format_date_str(c.get("start_date"))
            e_date = format_date_str(c.get("end_date"))
            m_count = c.get("members_count", 0)
            crs_count = c.get("courses_count", 0)
            ex_count = c.get("exams_count", 0)

            if c_status == "ACTIVE":
                badge_bg, badge_fg = ft.Colors.with_opacity(0.12, ft.Colors.GREEN_600), ft.Colors.GREEN_700
                stripe_color = ft.Colors.GREEN_600
            elif c_status == "COMPLETED":
                badge_bg, badge_fg = ft.Colors.with_opacity(0.10, ft.Colors.GREY_600), ft.Colors.GREY_700
                stripe_color = ft.Colors.GREY_600
            else:
                badge_bg, badge_fg = ft.Colors.with_opacity(0.12, ft.Colors.BLUE_600), ft.Colors.BLUE_700
                stripe_color = ft.Colors.BLUE_600

            def make_open_handler(target_id):
                return lambda _: page.run_task(open_cohort_details, target_id)

            def meta_badge(icon_name, text_val, tint):
                return ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.06, tint),
                    content=ft.Row([
                        ft.Icon(icon_name, size=13, color=tint),
                        ft.Text(text_val, size=11, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                    ], spacing=5, tight=True),
                )

            card = ft.Container(
                padding=16,
                border_radius=14,
                bgcolor=ft.Colors.SURFACE,
                border=ft.Border(
                    left=ft.BorderSide(4, stripe_color),
                    top=ft.BorderSide(1, ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)),
                    right=ft.BorderSide(1, ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)),
                    bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)),
                ),
                shadow=ft.BoxShadow(blur_radius=12, color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK), offset=ft.Offset(0, 2)),
                ink=True,
                on_click=make_open_handler(c_id),
                content=ft.Column([
                    ft.Row([
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                            border_radius=6, bgcolor=badge_bg,
                            content=ft.Text(c_status, size=10, weight=ft.FontWeight.BOLD, color=badge_fg),
                        ),
                        ft.Row([
                            ft.Icon(ft.Icons.CALENDAR_TODAY_ROUNDED, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(f"{s_date} – {e_date}", size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
                        ], spacing=4, tight=True),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Text(c_name, size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(c_desc, size=12, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    ft.Row([
                        meta_badge(ft.Icons.PEOPLE_ROUNDED, f"{m_count} Members", theme_color),
                        meta_badge(ft.Icons.AUTO_STORIES_ROUNDED, f"{crs_count} Courses", theme_color),
                        meta_badge(ft.Icons.TIMER_ROUNDED, f"{ex_count} Assessments", theme_color),
                    ], spacing=8),
                ], spacing=10),
            )
            cohort_cards.append(card)

        content_column = ft.Column([
            kpis,
            ft.Container(height=4),
            ft.Row([search_input, create_btn if is_admin else ft.Container()], spacing=8),
            filter_bar,
            ft.Container(height=4),
            ft.Column(cohort_cards, spacing=10) if cohort_cards else ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=40,
                content=ft.Column([
                    ft.Icon(ft.Icons.SCHOOL_OUTLINED, size=48, color=ft.Colors.GREY_400),
                    ft.Text("No cohorts found", size=15, weight=ft.FontWeight.BOLD),
                    ft.Text("Create a dated cohort to organize training and scheduled assessments.", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
            ),
        ], spacing=12, scroll=ft.ScrollMode.AUTO)

        container.content = content_column

    # ── COHORT DETAILS HUB ───────────────────────────────────────────────
    async def open_cohort_details(cohort_id: str):
        state["active_cohort_id"] = cohort_id
        container.content = ft.Container(
            alignment=ft.Alignment.CENTER,
            padding=40,
            content=ft.Column([
                ft.ProgressRing(color=theme_color, width=32, height=32),
                ft.Text("Loading Cohort Details...", size=13, color=ft.Colors.ON_SURFACE_VARIANT),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True, spacing=12),
        )
        page.update()

        details = await get_cohort_details(token, org_id, cohort_id)
        if "error" in details:
            show_snack(f"Could not load cohort: {details['error']}", is_error=True)
            render_main_cohorts_view()
            page.update()
            return

        state["active_cohort_data"] = details
        render_cohort_detail_view()
        page.update()

    def render_cohort_detail_view():
        data = state["active_cohort_data"]
        c_id = str(data["id"])
        c_name = data.get("name", "Cohort")
        c_desc = data.get("description") or ""
        s_date = format_date_str(data.get("start_date"))
        e_date = format_date_str(data.get("end_date"))
        c_status = get_effective_cohort_status(data)

        sub_tab = {"key": "overview"}

        sub_tab_container = ft.Container(expand=True)

        # ── SUB TAB: OVERVIEW ────────────────────────────────────────────
        def render_sub_overview():
            courses_list = data.get("courses", [])
            members_list = data.get("members", [])
            exams_list = data.get("exams", [])

            return ft.Column([
                ft.Container(
                    padding=18, border_radius=14,
                    bgcolor=ft.Colors.with_opacity(0.04, theme_color),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.12, theme_color)),
                    content=ft.Column([
                        ft.Text("Cohort Objectives & Information", size=13, weight=ft.FontWeight.BOLD, color=theme_color),
                        ft.Text(c_desc if c_desc else "No description provided for this training cohort.", size=13, color=ft.Colors.ON_SURFACE),
                        ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                        ft.Row([
                            ft.Column([
                                ft.Text("Curriculum Courses", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(f"{len(courses_list)} Courses Registered", size=13, weight=ft.FontWeight.BOLD),
                            ], spacing=2),
                            ft.Column([
                                ft.Text("Active Candidates", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(f"{data.get('members_count', len(members_list))} Enrolled", size=13, weight=ft.FontWeight.BOLD),
                            ], spacing=2),
                            ft.Column([
                                ft.Text("Scheduled Exams", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(f"{len(exams_list)} Assessments", size=13, weight=ft.FontWeight.BOLD),
                            ], spacing=2),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ], spacing=10),
                ),
            ], spacing=12)

        # ── SUB TAB: COURSES ─────────────────────────────────────────────
        def render_sub_courses():
            courses_list = data.get("courses", [])
            cards = []

            for crs in courses_list:
                crs_id = str(crs["id"])
                crs_name = crs.get("name", "Untitled Course")
                crs_lessons = crs.get("total_lessons", 0)

                def remove_crs(c_target, crs_title):
                    async def _do():
                        res = await remove_cohort_course(token, org_id, c_id, c_target)
                        if "error" in res:
                            show_snack(res["error"], is_error=True)
                        else:
                            show_snack("Course removed from cohort.")
                            await open_cohort_details(c_id)
                    return lambda _: show_confirm_dialog(
                        "Remove Course",
                        f"Are you sure you want to remove '{crs_title}' from this cohort? Candidates will lose course access.",
                        "Remove Course",
                        _do,
                        is_destructive=True,
                    )

                cards.append(
                    ft.Container(
                        padding=12, border_radius=12,
                        bgcolor=ft.Colors.SURFACE,
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
                        ink=True,
                        on_click=lambda _, cid=crs_id: page.go(f"/courses/{cid}"),
                        content=ft.Row([
                            ft.Container(
                                padding=8, border_radius=8, bgcolor=ft.Colors.with_opacity(0.08, theme_color),
                                content=ft.Icon(ft.Icons.AUTO_STORIES_ROUNDED, size=20, color=theme_color),
                            ),
                            ft.Column([
                                ft.Text(crs_name, size=13, weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                ft.Text(f"{crs_lessons} Lessons · Auto-enrolled for cohort candidates", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                            ], spacing=2, expand=True),
                            ft.IconButton(
                                icon=ft.Icons.PLAY_ARROW_ROUNDED,
                                icon_color=theme_color,
                                icon_size=20,
                                tooltip="Study course",
                                on_click=lambda _, cid=crs_id: page.go(f"/courses/{cid}"),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                icon_color=ft.Colors.RED_500,
                                icon_size=18,
                                tooltip="Remove from cohort",
                                on_click=remove_crs(crs_id, crs_name),
                                visible=is_admin,
                            ),
                        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    )
                )

            # Add course dialog
            def open_add_course_dlg(e=None):
                existing_ids = {str(c["id"]) for c in courses_list}
                eligible = [c for c in org_courses if str(c.get("id")) not in existing_ids]

                checks = [ft.Checkbox(label=c.get("name", "Course"), data=str(c.get("id"))) for c in eligible]
                course_col = ft.Column(scroll=ft.ScrollMode.AUTO, spacing=4)

                def filter_courses(ev=None):
                    q = (crs_search_f.value or "").strip().lower() if crs_search_f.value else ""
                    matched = [chk for chk in checks if not q or q in (chk.label or "").lower()]
                    course_col.controls = matched if matched else [
                        ft.Container(
                            padding=20, alignment=ft.Alignment.CENTER,
                            content=ft.Text("No matching courses found.", italic=True, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        )
                    ] if checks else [ft.Text("All org courses are already registered.", italic=True, size=11)]
                    page.update()

                crs_search_f = ft.TextField(
                    hint_text="Search courses by name...",
                    prefix_icon=ft.Icons.SEARCH_ROUNDED,
                    height=40, text_size=12,
                    content_padding=ft.Padding.symmetric(horizontal=10, vertical=0),
                    border_radius=8,
                    on_change=filter_courses,
                )
                filter_courses()

                async def do_add(e=None):
                    selected = [chk.data for chk in checks if chk.value]
                    if not selected:
                        show_snack("Select at least one course.", is_error=True)
                        return
                    res = await add_cohort_courses(token, org_id, c_id, selected)
                    if "error" in res:
                        show_snack(res["error"], is_error=True)
                    else:
                        if hasattr(page, "pop_dialog"):
                            page.pop_dialog()
                        show_snack("Courses added to cohort successfully.")
                        await open_cohort_details(c_id)

                dlg = ft.AlertDialog(
                    modal=True,
                    title=ft.Row([
                        ft.Icon(ft.Icons.AUTO_STORIES_ROUNDED, color=theme_color, size=20),
                        ft.Text("Add Courses to Cohort", weight=ft.FontWeight.BOLD, size=15),
                    ], spacing=8),
                    content=ft.Container(
                        width=420, height=320,
                        content=ft.Column([
                            crs_search_f,
                            ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                            ft.Container(content=course_col, expand=True),
                        ], spacing=8),
                    ),
                    actions=[
                        ft.TextButton("Cancel", on_click=lambda _: page.pop_dialog()),
                        ft.FilledButton("Add Selected", on_click=lambda _: page.run_task(do_add), style=ft.ButtonStyle(bgcolor=theme_color)) if checks else ft.Container(),
                    ],
                )
                page.show_dialog(dlg)

            return ft.Column([
                ft.Row([
                    ft.Text(f"Assigned Curriculum ({len(courses_list)})", size=13, weight=ft.FontWeight.BOLD),
                    ft.FilledButton(
                        content=ft.Row([ft.Icon(ft.Icons.ADD_ROUNDED, size=14), ft.Text("Add Course", size=11, weight=ft.FontWeight.BOLD)], tight=True, spacing=4),
                        style=ft.ButtonStyle(bgcolor=theme_color, padding=ft.Padding.symmetric(horizontal=10, vertical=6)),
                        on_click=open_add_course_dlg,
                        visible=is_admin,
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Column(cards, spacing=8) if cards else ft.Container(
                    alignment=ft.Alignment.CENTER, padding=30,
                    content=ft.Text("No courses mapped to this cohort yet.", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ),
            ], spacing=10)

        # ── SUB TAB: MEMBERS ─────────────────────────────────────────────
        def render_sub_members():
            members_list = data.get("members", [])
            member_rows = []

            for m in members_list:
                m_uid = str(m["user_id"])
                m_name = f"{m.get('first_name', '')} {m.get('last_name', '')}".strip() or m.get("email", "")
                m_prog = m.get("avg_progress", 0.0)

                def remove_mem(u_target, m_label):
                    async def _do():
                        res = await remove_cohort_member(token, org_id, c_id, u_target)
                        if "error" in res:
                            show_snack(res["error"], is_error=True)
                        else:
                            show_snack("Member removed from cohort.")
                            await open_cohort_details(c_id)
                    return lambda _: show_confirm_dialog(
                        "Remove Member",
                        f"Are you sure you want to remove {m_label} from this cohort?",
                        "Remove Member",
                        _do,
                        is_destructive=True,
                    )

                member_rows.append(
                    ft.Container(
                        padding=12, border_radius=12,
                        bgcolor=ft.Colors.SURFACE,
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
                        content=ft.Row([
                            ft.CircleAvatar(
                                content=ft.Text(m_name[:2].upper(), size=12, weight=ft.FontWeight.BOLD),
                                radius=18, bgcolor=ft.Colors.with_opacity(0.1, theme_color),
                            ),
                            ft.Column([
                                ft.Text(m_name, size=13, weight=ft.FontWeight.BOLD),
                                ft.Text(m.get("email", ""), size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                            ], spacing=1, expand=True),
                            ft.Column([
                                ft.Text(f"{m_prog}% Complete", size=11, weight=ft.FontWeight.BOLD, color=theme_color),
                                ft.Container(
                                    width=70, content=ft.ProgressBar(value=m_prog / 100.0, height=4, color=theme_color),
                                ),
                            ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.END),
                            ft.IconButton(
                                icon=ft.Icons.PERSON_REMOVE_ROUNDED,
                                icon_color=ft.Colors.RED_500,
                                icon_size=18,
                                tooltip="Remove member",
                                on_click=remove_mem(m_uid, m_name),
                                visible=is_admin,
                            ),
                        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    )
                )

            # Add members dialog
            def open_add_members_dlg(e=None):
                existing_uids = {str(m["user_id"]) for m in members_list}
                eligible = [m for m in org_members if str(m.get("id", "") or m.get("user_id", "")) not in existing_uids]

                checks = [
                    ft.Checkbox(
                        label=f"{m.get('first_name', '')} {m.get('last_name', '')}".strip() or m.get('email', ''),
                        data=str(m.get("id", "") or m.get("user_id", ""))
                    )
                    for m in eligible
                ]
                members_col = ft.Column(scroll=ft.ScrollMode.AUTO, spacing=4)

                def filter_members(ev=None):
                    q = (mem_search_f.value or "").strip().lower() if mem_search_f.value else ""
                    matched = [chk for chk in checks if not q or q in (chk.label or "").lower()]
                    members_col.controls = matched if matched else [
                        ft.Container(
                            padding=20, alignment=ft.Alignment.CENTER,
                            content=ft.Text("No matching members found.", italic=True, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        )
                    ] if checks else [ft.Text("All org members are already enrolled.", italic=True, size=11)]
                    page.update()

                def select_all_eligible(ev=None):
                    if ev and getattr(ev, "control", None):
                        for chk in checks:
                            chk.value = ev.control.value
                        page.update()

                mem_search_f = ft.TextField(
                    hint_text="Search candidates by name or email...",
                    prefix_icon=ft.Icons.SEARCH_ROUNDED,
                    height=40, text_size=12,
                    content_padding=ft.Padding.symmetric(horizontal=10, vertical=0),
                    border_radius=8,
                    on_change=filter_members,
                )
                all_chk_toggle = ft.Checkbox(label="Select All", value=False, on_change=select_all_eligible)
                filter_members()

                async def do_add(e=None):
                    selected = [chk.data for chk in checks if chk.value]
                    if not selected:
                        show_snack("Select at least one member.", is_error=True)
                        return
                    res = await add_cohort_members(token, org_id, c_id, selected)
                    if "error" in res:
                        show_snack(res["error"], is_error=True)
                    else:
                        if hasattr(page, "pop_dialog"):
                            page.pop_dialog()
                        show_snack("Members enrolled into cohort successfully.")
                        await open_cohort_details(c_id)

                dlg = ft.AlertDialog(
                    modal=True,
                    title=ft.Row([
                        ft.Icon(ft.Icons.PERSON_ADD_ROUNDED, color=theme_color, size=20),
                        ft.Text("Enroll Members into Cohort", weight=ft.FontWeight.BOLD, size=15),
                    ], spacing=8),
                    content=ft.Container(
                        width=420, height=340,
                        content=ft.Column([
                            mem_search_f,
                            ft.Row([all_chk_toggle], alignment=ft.MainAxisAlignment.END),
                            ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                            ft.Container(content=members_col, expand=True),
                        ], spacing=6),
                    ),
                    actions=[
                        ft.TextButton("Cancel", on_click=lambda _: page.pop_dialog()),
                        ft.FilledButton("Enroll Selected", on_click=lambda _: page.run_task(do_add), style=ft.ButtonStyle(bgcolor=theme_color)) if checks else ft.Container(),
                    ],
                )
                page.show_dialog(dlg)

            return ft.Column([
                ft.Row([
                    ft.Text(f"Cohort Roster ({len(members_list)})", size=13, weight=ft.FontWeight.BOLD),
                    ft.FilledButton(
                        content=ft.Row([ft.Icon(ft.Icons.PERSON_ADD_ROUNDED, size=14), ft.Text("Add Members", size=11, weight=ft.FontWeight.BOLD)], tight=True, spacing=4),
                        style=ft.ButtonStyle(bgcolor=theme_color, padding=ft.Padding.symmetric(horizontal=10, vertical=6)),
                        on_click=open_add_members_dlg,
                        visible=is_admin,
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Column(member_rows, spacing=8) if member_rows else ft.Container(
                    alignment=ft.Alignment.CENTER, padding=30,
                    content=ft.Text("No candidates enrolled in this cohort yet.", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ),
            ], spacing=10)

        # ── SUB TAB: EXAMS ───────────────────────────────────────────────
        def render_sub_exams():
            exams_list = data.get("exams", [])
            exam_cards = []

            for ex in exams_list:
                ex_id = str(ex["id"])
                ex_title = ex.get("title", "Exam")
                ex_dur = ex.get("duration_minutes", 60)
                ex_pass = ex.get("pass_percentage", 70.0)
                ex_q_count = ex.get("question_count", 0)
                ex_status = get_effective_exam_status(ex)
                o_time = format_date_str(ex.get("opens_at"))
                c_time = format_date_str(ex.get("closes_at"))
                user_sub = ex.get("user_submission")

                if ex_status == "OPEN_NOW":
                    status_badge = ft.Container(
                        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                        border_radius=6, bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.GREEN_600),
                        content=ft.Row([
                            ft.Container(width=6, height=6, border_radius=3, bgcolor=ft.Colors.GREEN_600),
                            ft.Text("OPEN NOW", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_700),
                        ], spacing=4, tight=True),
                    )
                elif ex_status == "CLOSED":
                    status_badge = ft.Container(
                        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                        border_radius=6, bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.GREY_600),
                        content=ft.Text("CLOSED", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_700),
                    )
                else:
                    status_badge = ft.Container(
                        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                        border_radius=6, bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.BLUE_600),
                        content=ft.Text("SCHEDULED", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_700),
                    )

                # Candidate Take Exam Handler
                def make_take_handler(target_ex_id):
                    async def _do(_):
                        container.content = ft.Container(
                            alignment=ft.Alignment.CENTER,
                            padding=40,
                            content=ft.Column([
                                ft.ProgressRing(color=theme_color, width=32, height=32),
                                ft.Text("Setting up your assessment environment...", size=13),
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True, spacing=12),
                        )
                        page.update()

                        exam_run_payload = await start_cohort_exam(token, org_id, c_id, target_ex_id)
                        if "error" in exam_run_payload:
                            err_msg = exam_run_payload["error"]
                            container.content = ft.Container(
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
                                            "Return to Cohort",
                                            icon=ft.Icons.ARROW_BACK_ROUNDED,
                                            on_click=lambda _: page.run_task(open_cohort_details, c_id),
                                            style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=24, vertical=12)),
                                        ),
                                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                                ),
                            )
                            page.update()
                            return

                        exam_view = build_cohort_exam_view(
                            page=page,
                            exam_payload=exam_run_payload,
                            org_id=org_id,
                            cohort_id=c_id,
                            exam_id=target_ex_id,
                            token=token,
                            on_exit=lambda *_: page.run_task(open_cohort_details, c_id),
                        )
                        container.content = exam_view
                        page.update()
                    return _do

                # Admin Actions
                def open_q_bank(target_ex_id):
                    return lambda _: page.run_task(show_question_bank_modal, target_ex_id)

                def open_grades(target_ex_id):
                    return lambda _: page.run_task(show_gradebook_modal, target_ex_id)

                def delete_ex(target_ex_id, target_title):
                    async def _do():
                        res = await delete_cohort_exam(token, org_id, c_id, target_ex_id)
                        if "error" in res:
                            show_snack(res["error"], is_error=True)
                        else:
                            show_snack("Exam deleted.")
                            await open_cohort_details(c_id)
                    return lambda _: show_confirm_dialog(
                        "Delete Assessment",
                        f"Are you sure you want to delete exam '{target_title}' and all its candidate submissions?",
                        "Delete Exam",
                        _do,
                        is_destructive=True,
                    )

                # Candidate CTA Button
                if user_sub and user_sub.get("status") in ("submitted", "graded"):
                    cta_btn = ft.Container(
                        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                        border_radius=8, bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.GREEN_600 if user_sub.get("passed") else ft.Colors.RED_500),
                        content=ft.Text(f"Completed · {user_sub.get('percentage')}% ({'PASSED' if user_sub.get('passed') else 'FAILED'})",
                                        size=11, weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.GREEN_700 if user_sub.get("passed") else ft.Colors.RED_700),
                    )
                elif ex_status == "OPEN_NOW":
                    cta_btn = ft.FilledButton(
                        "Take Exam",
                        icon=ft.Icons.PLAY_ARROW_ROUNDED,
                        style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, padding=ft.Padding.symmetric(horizontal=12, vertical=6)),
                        on_click=make_take_handler(ex_id),
                    )
                else:
                    cta_btn = ft.Text(f"Available: {o_time}", size=11, color=ft.Colors.ON_SURFACE_VARIANT, italic=True)

                card = ft.Container(
                    padding=16, border_radius=14,
                    bgcolor=ft.Colors.SURFACE,
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                    content=ft.Column([
                        ft.Row([
                            status_badge,
                            ft.Row([
                                ft.Icon(ft.Icons.TIMER_OUTLINED, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(f"{ex_dur} mins · {ex_q_count} Questions", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                            ], spacing=4, tight=True),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Text(ex_title, size=15, weight=ft.FontWeight.BOLD),
                        ft.Text(f"Schedule Window: {o_time} to {c_time} · Pass mark: {ex_pass}%", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                        ft.Row([
                            cta_btn,
                            ft.Row([
                                ft.OutlinedButton(
                                    content=ft.Row([ft.Icon(ft.Icons.QUIZ_ROUNDED, size=13), ft.Text("Questions", size=11)], tight=True, spacing=4),
                                    on_click=open_q_bank(ex_id),
                                    style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=10, vertical=6)),
                                    visible=is_admin,
                                ),
                                ft.FilledButton(
                                    content=ft.Row([ft.Icon(ft.Icons.ANALYTICS_ROUNDED, size=13), ft.Text("Gradebook", size=11)], tight=True, spacing=4),
                                    on_click=open_grades(ex_id),
                                    style=ft.ButtonStyle(bgcolor=theme_color, padding=ft.Padding.symmetric(horizontal=10, vertical=6)),
                                    visible=is_admin,
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.EDIT_OUTLINED,
                                    icon_color=theme_color,
                                    icon_size=18,
                                    tooltip="Edit Exam",
                                    on_click=lambda _, x=ex: open_edit_exam_dialog(x),
                                    visible=is_admin,
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                    icon_color=ft.Colors.RED_500,
                                    icon_size=18,
                                    tooltip="Delete Exam",
                                    on_click=delete_ex(ex_id, ex_title),
                                    visible=is_admin,
                                ),
                            ], spacing=4, wrap=True, tight=True),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER, wrap=True),
                    ], spacing=10),
                )
                exam_cards.append(card)

            # Schedule New Exam Dialog with Exact Date & Time Picker
            def open_schedule_exam_dlg(e=None):
                title_field = ft.TextField(
                    label="Exam Title *",
                    hint_text="e.g. Mid-Term Assessment / Final Certification Exam",
                    **_INPUT,
                )
                inst_field = ft.TextField(
                    label="Candidate Instructions & Rules",
                    hint_text="Explain allowed attempts, time limit, proctoring warnings...",
                    multiline=True,
                    min_lines=2,
                    max_lines=4,
                    **_INPUT,
                )

                dur_field = ft.TextField(
                    label="Duration (Minutes) *",
                    value="60",
                    keyboard_type=ft.KeyboardType.NUMBER,
                    **_INPUT,
                )
                pass_field = ft.TextField(
                    label="Pass Mark (%) *",
                    value="70",
                    keyboard_type=ft.KeyboardType.NUMBER,
                    **_INPUT,
                )
                attempts_field = ft.TextField(
                    label="Max Allowed Attempts *",
                    value="1",
                    keyboard_type=ft.KeyboardType.NUMBER,
                    **_INPUT,
                )


                # State variables for exact Date and Time
                now_ex_dt = datetime.now()
                later_ex_dt = now_ex_dt + timedelta(days=7)

                open_date_val = [now_ex_dt.date()]
                open_time_val = [time(hour=9, minute=0)]
                close_date_val = [later_ex_dt.date()]
                close_time_val = [time(hour=17, minute=0)]

                open_date_btn_text = ft.Text(open_date_val[0].strftime("%b %d, %Y"), size=12, weight=ft.FontWeight.W_600)
                open_time_btn_text = ft.Text(open_time_val[0].strftime("%I:%M %p"), size=12, weight=ft.FontWeight.W_600)
                close_date_btn_text = ft.Text(close_date_val[0].strftime("%b %d, %Y"), size=12, weight=ft.FontWeight.W_600)
                close_time_btn_text = ft.Text(close_time_val[0].strftime("%I:%M %p"), size=12, weight=ft.FontWeight.W_600)

                def on_open_date_change(e=None):
                    if e and getattr(e, "control", None) and e.control.value:
                        val = e.control.value
                        open_date_val[0] = val.date() if isinstance(val, datetime) else val
                        open_date_btn_text.value = open_date_val[0].strftime("%b %d, %Y")
                        page.update()

                def on_open_time_change(e=None):
                    if e and getattr(e, "control", None) and e.control.value:
                        open_time_val[0] = e.control.value
                        open_time_btn_text.value = open_time_val[0].strftime("%I:%M %p")
                        page.update()

                def on_close_date_change(e=None):
                    if e and getattr(e, "control", None) and e.control.value:
                        val = e.control.value
                        close_date_val[0] = val.date() if isinstance(val, datetime) else val
                        close_date_btn_text.value = close_date_val[0].strftime("%b %d, %Y")
                        page.update()

                def on_close_time_change(e=None):
                    if e and getattr(e, "control", None) and e.control.value:
                        close_time_val[0] = e.control.value
                        close_time_btn_text.value = close_time_val[0].strftime("%I:%M %p")
                        page.update()

                open_date_picker = ft.DatePicker(
                    value=now_ex_dt,
                    first_date=now_ex_dt - timedelta(days=365),
                    last_date=now_ex_dt + timedelta(days=365 * 5),
                    on_change=on_open_date_change,
                )
                open_time_picker = ft.TimePicker(
                    value=open_time_val[0],
                    help_text="Select Exam Opening Time",
                    on_change=on_open_time_change,
                )
                close_date_picker = ft.DatePicker(
                    value=later_ex_dt,
                    first_date=now_ex_dt - timedelta(days=365),
                    last_date=now_ex_dt + timedelta(days=365 * 5),
                    on_change=on_close_date_change,
                )
                close_time_picker = ft.TimePicker(
                    value=close_time_val[0],
                    help_text="Select Exam Closing Time",
                    on_change=on_close_time_change,
                )
                page.overlay.extend([open_date_picker, open_time_picker, close_date_picker, close_time_picker])

                def open_start_date_dlg(_=None):
                    open_date_picker.open = True
                    page.update()

                def open_start_time_dlg(_=None):
                    open_time_picker.open = True
                    page.update()

                def open_close_date_dlg(_=None):
                    close_date_picker.open = True
                    page.update()

                def open_close_time_dlg(_=None):
                    close_time_picker.open = True
                    page.update()

                # Card for Assessment Window: Opens At
                opens_card = ft.Container(
                    padding=12,
                    border_radius=12,
                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.GREEN_700),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.GREEN_700)),
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(ft.Icons.LOCK_OPEN_ROUNDED, size=16, color=ft.Colors.GREEN_700),
                            ft.Text("Exam Window Opens", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_800),
                        ], spacing=6),
                        ft.Row([
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                                border_radius=8,
                                border=ft.Border.all(1, ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE)),
                                bgcolor=ft.Colors.SURFACE,
                                ink=True,
                                on_click=open_start_date_dlg,
                                expand=3,
                                content=ft.Row([
                                    ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, size=16, color=theme_color),
                                    ft.Column([
                                        ft.Text("Date", size=9, color=ft.Colors.ON_SURFACE_VARIANT),
                                        open_date_btn_text,
                                    ], spacing=1, expand=True),
                                ], spacing=6),
                            ),
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                                border_radius=8,
                                border=ft.Border.all(1, ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE)),
                                bgcolor=ft.Colors.SURFACE,
                                ink=True,
                                on_click=open_start_time_dlg,
                                expand=2,
                                content=ft.Row([
                                    ft.Icon(ft.Icons.ACCESS_TIME_ROUNDED, size=16, color=theme_color),
                                    ft.Column([
                                        ft.Text("Time", size=9, color=ft.Colors.ON_SURFACE_VARIANT),
                                        open_time_btn_text,
                                    ], spacing=1, expand=True),
                                ], spacing=6),
                            ),
                        ], spacing=8),
                    ], spacing=8),
                )

                # Card for Assessment Window: Closes At
                closes_card = ft.Container(
                    padding=12,
                    border_radius=12,
                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.RED_700),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.RED_700)),
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(ft.Icons.LOCK_CLOCK_ROUNDED, size=16, color=ft.Colors.RED_700),
                            ft.Text("Exam Window Closes", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_800),
                        ], spacing=6),
                        ft.Row([
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                                border_radius=8,
                                border=ft.Border.all(1, ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE)),
                                bgcolor=ft.Colors.SURFACE,
                                ink=True,
                                on_click=open_close_date_dlg,
                                expand=3,
                                content=ft.Row([
                                    ft.Icon(ft.Icons.EVENT_BUSY_ROUNDED, size=16, color=theme_color),
                                    ft.Column([
                                        ft.Text("Date", size=9, color=ft.Colors.ON_SURFACE_VARIANT),
                                        close_date_btn_text,
                                    ], spacing=1, expand=True),
                                ], spacing=6),
                            ),
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                                border_radius=8,
                                border=ft.Border.all(1, ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE)),
                                bgcolor=ft.Colors.SURFACE,
                                ink=True,
                                on_click=open_close_time_dlg,
                                expand=2,
                                content=ft.Row([
                                    ft.Icon(ft.Icons.ACCESS_TIME_ROUNDED, size=16, color=theme_color),
                                    ft.Column([
                                        ft.Text("Time", size=9, color=ft.Colors.ON_SURFACE_VARIANT),
                                        close_time_btn_text,
                                    ], spacing=1, expand=True),
                                ], spacing=6),
                            ),
                        ], spacing=8),
                    ], spacing=8),
                )

                security_dd = ft.Dropdown(
                    label="Anti-Cheat Security Policy *",
                    options=[
                        ft.dropdown.Option("monitored", "🛡️ Monitored Mode (2 Warnings before auto-submit)"),
                        ft.dropdown.Option("strict", "🔒 Strict Mode (Immediate auto-submit on app/window switch)"),
                        ft.dropdown.Option("relaxed", "🟢 Relaxed Mode (Practice / no auto-submit)"),
                    ],
                    value="monitored",
                    border_radius=10,
                )
                calc_dd = ft.Dropdown(
                    label="Permitted In-Exam Calculator *",
                    options=[
                        ft.dropdown.Option("none", "🚫 No Calculator (Calculations not permitted)"),
                        ft.dropdown.Option("basic", "🔢 Basic Calculator (+, −, ×, ÷, %)"),
                        ft.dropdown.Option("scientific", "🧪 Scientific Calculator (Trig, Sqrt, Powers, Log)"),
                    ],
                    value="none",
                )
                review_mode_chk = ft.Checkbox(
                    value=True,
                    scale=0.9,
                )
                review_mode_card = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                    content=ft.Row([
                        review_mode_chk,
                        ft.Column([
                            ft.Text("Confidential Grading Protocol", size=11, weight=ft.FontWeight.BOLD),
                            ft.Text("Release score and solutions only after instructor audit (no instant score reveal).", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                        ], spacing=1, expand=True),
                    ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                )

                async def do_schedule(e=None):
                    if not title_field.value or not title_field.value.strip():
                        show_snack("Exam title is required.", is_error=True)
                        return

                    o_dt = datetime.combine(open_date_val[0], open_time_val[0]).replace(tzinfo=timezone.utc)
                    c_dt = datetime.combine(close_date_val[0], close_time_val[0]).replace(tzinfo=timezone.utc)

                    if c_dt <= o_dt:
                        show_snack("Closing date and time must be after opening date and time.", is_error=True)
                        return

                    payload = {
                        "title": title_field.value.strip(),
                        "instructions": inst_field.value.strip() if inst_field.value else None,
                        "opens_at": o_dt.isoformat(),
                        "closes_at": c_dt.isoformat(),
                        "duration_minutes": int(dur_field.value or 60),
                        "pass_percentage": float(pass_field.value or 70),
                        "max_attempts": int(attempts_field.value or 1),
                        "security_mode": security_dd.value or "monitored",
                        "shuffle_questions": True,
                        "show_immediate_results": not review_mode_chk.value,
                        "calculator_type": calc_dd.value or "none",
                    }

                    res = await create_cohort_exam(token, org_id, c_id, payload)
                    if "error" in res:
                        show_snack(res["error"], is_error=True)
                    else:
                        if hasattr(page, "pop_dialog"):
                            page.pop_dialog()
                        show_snack("Exam scheduled successfully.")
                        await open_cohort_details(c_id)

                dlg = ft.AlertDialog(
                    modal=True,
                    title=ft.Row([
                        ft.Container(
                            padding=8,
                            border_radius=10,
                            bgcolor=ft.Colors.with_opacity(0.12, theme_color),
                            content=ft.Icon(ft.Icons.TIMER_ROUNDED, color=theme_color, size=22),
                        ),
                        ft.Column([
                            ft.Text("Schedule Timed Assessment", weight=ft.FontWeight.BOLD, size=16),
                            ft.Text("Configure exact assessment window, duration & proctoring", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ], spacing=1),
                    ], spacing=10),
                    content=ft.Container(
                        width=min(getattr(page, "width", 800) - 24, 560),
                        height=500,
                        content=ft.Column([
                            title_field,
                            inst_field,
                            opens_card,
                            closes_card,
                            ft.Container(height=4),
                            ft.Text("Test Parameters", size=12, weight=ft.FontWeight.BOLD),
                            ft.Row([
                                ft.Container(dur_field, expand=2),
                                ft.Container(pass_field, expand=2),
                                ft.Container(attempts_field, expand=1),
                            ], spacing=8),
                            ft.Container(height=4),
                            ft.Text("Tools & Policies", size=12, weight=ft.FontWeight.BOLD),
                            calc_dd,
                            security_dd,
                            review_mode_card,
                        ], scroll=ft.ScrollMode.AUTO, spacing=10),
                    ),
                    actions=[
                        ft.TextButton("Cancel", on_click=lambda _: page.pop_dialog()),
                        ft.FilledButton(
                            "Schedule Assessment",
                            icon=ft.Icons.CHECK_ROUNDED,
                            on_click=lambda _: page.run_task(do_schedule),
                            style=ft.ButtonStyle(bgcolor=theme_color, padding=ft.Padding.symmetric(horizontal=18, vertical=12)),
                        ),
                    ],
                )
                page.show_dialog(dlg)

            # Edit Existing Exam Dialog
            def open_edit_exam_dialog(target_ex):
                edit_ex_id = str(target_ex["id"])
                edit_title_f = ft.TextField(label="Exam Title *", value=target_ex.get("title", ""), **_INPUT)
                edit_inst_f = ft.TextField(label="Candidate Instructions & Rules", value=target_ex.get("instructions") or "", multiline=True, min_lines=2, max_lines=4, **_INPUT)
                edit_dur_f = ft.TextField(label="Duration (Minutes) *", value=str(target_ex.get("duration_minutes", 60)), keyboard_type=ft.KeyboardType.NUMBER, **_INPUT)
                edit_pass_f = ft.TextField(label="Pass Mark (%) *", value=str(target_ex.get("pass_percentage", 70.0)), keyboard_type=ft.KeyboardType.NUMBER, **_INPUT)
                edit_att_f = ft.TextField(label="Max Allowed Attempts *", value=str(target_ex.get("max_attempts", 1)), keyboard_type=ft.KeyboardType.NUMBER, **_INPUT)

                o_raw = target_ex.get("opens_at")
                c_raw = target_ex.get("closes_at")
                try:
                    init_o = datetime.fromisoformat(str(o_raw).replace("Z", "+00:00")) if o_raw else datetime.now()
                except Exception:
                    init_o = datetime.now()
                try:
                    init_c = datetime.fromisoformat(str(c_raw).replace("Z", "+00:00")) if c_raw else (init_o + timedelta(days=7))
                except Exception:
                    init_c = init_o + timedelta(days=7)

                edit_open_date = [init_o.date() if isinstance(init_o, datetime) else init_o]
                edit_open_time = [init_o.time() if isinstance(init_o, datetime) else time(9, 0)]
                edit_close_date = [init_c.date() if isinstance(init_c, datetime) else init_c]
                edit_close_time = [init_c.time() if isinstance(init_c, datetime) else time(17, 0)]

                e_o_date_txt = ft.Text(edit_open_date[0].strftime("%b %d, %Y"), size=12, weight=ft.FontWeight.W_600)
                e_o_time_txt = ft.Text(edit_open_time[0].strftime("%I:%M %p"), size=12, weight=ft.FontWeight.W_600)
                e_c_date_txt = ft.Text(edit_close_date[0].strftime("%b %d, %Y"), size=12, weight=ft.FontWeight.W_600)
                e_c_time_txt = ft.Text(edit_close_time[0].strftime("%I:%M %p"), size=12, weight=ft.FontWeight.W_600)

                def on_e_o_d(e=None):
                    if e and getattr(e, "control", None) and e.control.value:
                        v = e.control.value
                        edit_open_date[0] = v.date() if isinstance(v, datetime) else v
                        e_o_date_txt.value = edit_open_date[0].strftime("%b %d, %Y")
                        page.update()

                def on_e_o_t(e=None):
                    if e and getattr(e, "control", None) and e.control.value:
                        edit_open_time[0] = e.control.value
                        e_o_time_txt.value = edit_open_time[0].strftime("%I:%M %p")
                        page.update()

                def on_e_c_d(e=None):
                    if e and getattr(e, "control", None) and e.control.value:
                        v = e.control.value
                        edit_close_date[0] = v.date() if isinstance(v, datetime) else v
                        e_c_date_txt.value = edit_close_date[0].strftime("%b %d, %Y")
                        page.update()

                def on_e_c_t(e=None):
                    if e and getattr(e, "control", None) and e.control.value:
                        edit_close_time[0] = e.control.value
                        e_c_time_txt.value = edit_close_time[0].strftime("%I:%M %p")
                        page.update()

                ed_od_picker = ft.DatePicker(value=init_o, first_date=datetime.now() - timedelta(days=365 * 2), last_date=datetime.now() + timedelta(days=365 * 5), on_change=on_e_o_d)
                ed_ot_picker = ft.TimePicker(value=edit_open_time[0], help_text="Select Exam Opening Time", on_change=on_e_o_t)
                ed_cd_picker = ft.DatePicker(value=init_c, first_date=datetime.now() - timedelta(days=365 * 2), last_date=datetime.now() + timedelta(days=365 * 5), on_change=on_e_c_d)
                ed_ct_picker = ft.TimePicker(value=edit_close_time[0], help_text="Select Exam Closing Time", on_change=on_e_c_t)
                page.overlay.extend([ed_od_picker, ed_ot_picker, ed_cd_picker, ed_ct_picker])

                e_opens_card = ft.Container(
                    padding=12, border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.GREEN_700),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.15, ft.Colors.GREEN_700)),
                    expand=True,
                    content=ft.Column([
                        ft.Row([ft.Icon(ft.Icons.LOCK_OPEN_ROUNDED, size=15, color=ft.Colors.GREEN_700), ft.Text("Window Opens", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_800)], spacing=5),
                        ft.Row([
                            ft.Container(padding=ft.Padding.symmetric(horizontal=8, vertical=6), border_radius=6, border=ft.Border.all(1, ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE)), bgcolor=ft.Colors.SURFACE, ink=True, on_click=lambda _: setattr(ed_od_picker, "open", True) or page.update(), expand=3, content=ft.Row([ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, size=14, color=theme_color), ft.Column([ft.Text("Date", size=8, color=ft.Colors.ON_SURFACE_VARIANT), e_o_date_txt], spacing=0, expand=True)], spacing=5)),
                            ft.Container(padding=ft.Padding.symmetric(horizontal=8, vertical=6), border_radius=6, border=ft.Border.all(1, ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE)), bgcolor=ft.Colors.SURFACE, ink=True, on_click=lambda _: setattr(ed_ot_picker, "open", True) or page.update(), expand=2, content=ft.Row([ft.Icon(ft.Icons.ACCESS_TIME_ROUNDED, size=14, color=theme_color), ft.Column([ft.Text("Time", size=8, color=ft.Colors.ON_SURFACE_VARIANT), e_o_time_txt], spacing=0, expand=True)], spacing=5)),
                        ], spacing=6),
                    ], spacing=6),
                )
                e_closes_card = ft.Container(
                    padding=12, border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.RED_700),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.15, ft.Colors.RED_700)),
                    expand=True,
                    content=ft.Column([
                        ft.Row([ft.Icon(ft.Icons.LOCK_CLOCK_ROUNDED, size=15, color=ft.Colors.RED_700), ft.Text("Window Closes", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_800)], spacing=5),
                        ft.Row([
                            ft.Container(padding=ft.Padding.symmetric(horizontal=8, vertical=6), border_radius=6, border=ft.Border.all(1, ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE)), bgcolor=ft.Colors.SURFACE, ink=True, on_click=lambda _: setattr(ed_cd_picker, "open", True) or page.update(), expand=3, content=ft.Row([ft.Icon(ft.Icons.EVENT_BUSY_ROUNDED, size=14, color=theme_color), ft.Column([ft.Text("Date", size=8, color=ft.Colors.ON_SURFACE_VARIANT), e_c_date_txt], spacing=0, expand=True)], spacing=5)),
                            ft.Container(padding=ft.Padding.symmetric(horizontal=8, vertical=6), border_radius=6, border=ft.Border.all(1, ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE)), bgcolor=ft.Colors.SURFACE, ink=True, on_click=lambda _: setattr(ed_ct_picker, "open", True) or page.update(), expand=2, content=ft.Row([ft.Icon(ft.Icons.ACCESS_TIME_ROUNDED, size=14, color=theme_color), ft.Column([ft.Text("Time", size=8, color=ft.Colors.ON_SURFACE_VARIANT), e_c_time_txt], spacing=0, expand=True)], spacing=5)),
                        ], spacing=6),
                    ], spacing=6),
                )
                e_sec_dd = ft.Dropdown(
                    label="Anti-Cheat Security Mode",
                    options=[
                        ft.dropdown.Option("monitored", "Monitored Mode (2 Warnings before auto-submit)"),
                        ft.dropdown.Option("strict", "Strict Mode (Immediate auto-submit on app switch)"),
                        ft.dropdown.Option("relaxed", "Relaxed Mode (Practice session / no auto-submit)"),
                    ],
                    value=target_ex.get("security_mode") or "monitored",
                    border_radius=8,
                    dense=True,
                )
                e_calc_dd = ft.Dropdown(
                    label="Permitted In-Exam Calculator",
                    options=[
                        ft.dropdown.Option("none", "Closed Book (No calculator allowed)"),
                        ft.dropdown.Option("basic", "Basic Calculator (+, −, ×, ÷, %)"),
                        ft.dropdown.Option("scientific", "Scientific Calculator (Trig, Powers, Logs, Sqrt)"),
                    ],
                    value=target_ex.get("calculator_type") or "none",
                    border_radius=8,
                    dense=True,
                )
                e_review_mode_chk = ft.Checkbox(
                    value=not target_ex.get("show_immediate_results", False),
                    scale=0.9,
                )
                e_review_card = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                    content=ft.Row([
                        e_review_mode_chk,
                        ft.Column([
                            ft.Text("Confidential Grading Protocol", size=11, weight=ft.FontWeight.BOLD),
                            ft.Text("Release exam score and feedback only after instructor review (no instant score reveal).", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                        ], spacing=1, expand=True),
                    ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                )

                async def do_save_exam(e=None):
                    if not edit_title_f.value or not edit_title_f.value.strip():
                        show_snack("Exam title is required.", is_error=True)
                        return
                    o_dt = datetime.combine(edit_open_date[0], edit_open_time[0]).replace(tzinfo=timezone.utc)
                    c_dt = datetime.combine(edit_close_date[0], edit_close_time[0]).replace(tzinfo=timezone.utc)
                    if c_dt <= o_dt:
                        show_snack("Closing date and time must be after opening date and time.", is_error=True)
                        return

                    payload = {
                        "title": edit_title_f.value.strip(),
                        "instructions": edit_inst_f.value.strip() if edit_inst_f.value else None,
                        "opens_at": o_dt.isoformat(),
                        "closes_at": c_dt.isoformat(),
                        "duration_minutes": int(edit_dur_f.value or 60),
                        "pass_percentage": float(edit_pass_f.value or 70),
                        "max_attempts": int(edit_att_f.value or 1),
                        "security_mode": e_sec_dd.value or "monitored",
                        "shuffle_questions": True,
                        "show_immediate_results": not e_review_mode_chk.value,
                        "calculator_type": e_calc_dd.value or "none",
                    }
                    res = await update_cohort_exam(token, org_id, c_id, edit_ex_id, payload)
                    if "error" in res:
                        show_snack(res["error"], is_error=True)
                    else:
                        if hasattr(page, "pop_dialog"):
                            page.pop_dialog()
                        show_snack("Exam updated successfully.")
                        await open_cohort_details(c_id)

                # Modern Minimalist Grouped Cards
                card_basic_info = ft.Container(
                    padding=14, border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    content=ft.Column([
                        ft.Row([ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, size=15, color=theme_color), ft.Text("Basic Information", size=12, weight=ft.FontWeight.BOLD)], spacing=6),
                        edit_title_f,
                        edit_inst_f,
                    ], spacing=10),
                )

                card_schedule = ft.Container(
                    padding=14, border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    content=ft.Column([
                        ft.Row([ft.Icon(ft.Icons.DATE_RANGE_ROUNDED, size=15, color=theme_color), ft.Text("Availability Window", size=12, weight=ft.FontWeight.BOLD)], spacing=6),
                        ft.Row([e_opens_card, e_closes_card], spacing=8),
                    ], spacing=10),
                )

                card_parameters = ft.Container(
                    padding=14, border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    content=ft.Column([
                        ft.Row([ft.Icon(ft.Icons.SPEED_ROUNDED, size=15, color=theme_color), ft.Text("Timing & Scoring Benchmark", size=12, weight=ft.FontWeight.BOLD)], spacing=6),
                        ft.Row([
                            ft.Container(edit_dur_f, expand=2),
                            ft.Container(edit_pass_f, expand=2),
                            ft.Container(edit_att_f, expand=1),
                        ], spacing=8),
                    ], spacing=10),
                )

                card_tools_security = ft.Container(
                    padding=14, border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    content=ft.Column([
                        ft.Row([ft.Icon(ft.Icons.SECURITY_ROUNDED, size=15, color=theme_color), ft.Text("Security Policy & Candidate Tools", size=12, weight=ft.FontWeight.BOLD)], spacing=6),
                        ft.Row([
                            ft.Container(e_calc_dd, expand=1),
                            ft.Container(e_sec_dd, expand=1),
                        ], spacing=8),
                        ft.Divider(height=1, color=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
                        e_review_card,
                    ], spacing=10),
                )

                ed_dlg = ft.AlertDialog(
                    modal=True,
                    title=ft.Row([
                        ft.Row([
                            ft.Container(
                                width=32, height=32, border_radius=8,
                                bgcolor=ft.Colors.with_opacity(0.1, theme_color),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.EDIT_ROUNDED, color=theme_color, size=18),
                            ),
                            ft.Column([
                                ft.Text("Edit Assessment Configuration", weight=ft.FontWeight.BOLD, size=15),
                                ft.Text("Configure schedule, security rules, and candidate tools.", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                            ], spacing=1),
                        ], spacing=10, tight=True),
                        ft.IconButton(ft.Icons.CLOSE_ROUNDED, icon_size=18, tooltip="Close", on_click=lambda _: page.pop_dialog()),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    content=ft.Container(
                        width=min(getattr(page, "width", 800) - 24, 600),
                        height=500,
                        content=ft.Column([
                            card_basic_info,
                            card_schedule,
                            card_parameters,
                            card_tools_security,
                        ], scroll=ft.ScrollMode.AUTO, spacing=12),
                    ),
                    actions=[
                        ft.TextButton("Cancel", on_click=lambda _: page.pop_dialog()),
                        ft.FilledButton(
                            "Save Assessment",
                            icon=ft.Icons.CHECK_ROUNDED,
                            on_click=lambda _: page.run_task(do_save_exam),
                            style=ft.ButtonStyle(bgcolor=theme_color, padding=ft.Padding.symmetric(horizontal=20, vertical=12)),
                        ),
                    ],
                )
                page.show_dialog(ed_dlg)

            return ft.Column([
                ft.Row([
                    ft.Text(f"Scheduled Assessments ({len(exams_list)})", size=13, weight=ft.FontWeight.BOLD),
                    ft.FilledButton(
                        content=ft.Row([ft.Icon(ft.Icons.ADD_ROUNDED, size=14), ft.Text("Schedule Exam", size=11, weight=ft.FontWeight.BOLD)], tight=True, spacing=4),
                        style=ft.ButtonStyle(bgcolor=theme_color, padding=ft.Padding.symmetric(horizontal=10, vertical=6)),
                        on_click=open_schedule_exam_dlg,
                        visible=is_admin,
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Column(exam_cards, spacing=10) if exam_cards else ft.Container(
                    alignment=ft.Alignment.CENTER, padding=30,
                    content=ft.Text("No scheduled assessments for this cohort yet.", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ),
            ], spacing=10)

        # ── QUESTION BANK MANAGER MODAL ──────────────────────────────────
        async def show_question_bank_modal(ex_id: str):
            exam_data = await get_cohort_exam(token, org_id, c_id, ex_id)
            if "error" in exam_data:
                show_snack("Could not load exam questions.", is_error=True)
                return

            q_list = list(exam_data.get("questions", []))
            ex_title = exam_data.get("title", "Assessment")

            title_text = ft.Text(f"Question Bank ({len(q_list)})", weight=ft.FontWeight.BOLD, size=15)

            upload_status = ft.Container(
                visible=False,
                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.1, theme_color),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.25, theme_color)),
                content=ft.Row([
                    ft.ProgressRing(width=16, height=16, stroke_width=2, color=theme_color),
                    ft.Text("Uploading and parsing questions spreadsheet...", size=12, color=theme_color, weight=ft.FontWeight.W_500),
                ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            )

            questions_list_view = ft.ListView(expand=True, spacing=10)
            search_query = [""]

            def build_question_cards():
                cards = []
                q_text_match = search_query[0].lower().strip()
                filtered = [
                    q for q in q_list
                    if not q_text_match or (
                        q_text_match in q.get("question_text", "").lower()
                        or q_text_match in (q.get("scenario_text") or "").lower()
                        or any(q_text_match in str(opt).lower() for opt in q.get("options", []))
                    )
                ]

                if not filtered:
                    empty_msg = "No questions in bank yet. Upload a CSV or add questions below." if not q_list else "No questions match your search."
                    return [
                        ft.Container(
                            alignment=ft.Alignment.CENTER,
                            padding=30,
                            content=ft.Column([
                                ft.Icon(ft.Icons.QUIZ_OUTLINED, size=38, color=ft.Colors.GREY_400),
                                ft.Text(empty_msg, italic=True, size=12, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER),
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                        )
                    ]

                _opt_letters = ["A", "B", "C", "D", "E", "F"]
                for idx, q in enumerate(filtered):
                    q_id = str(q.get("id"))
                    prompt = q.get("question_text", "")
                    opts = q.get("options", [])
                    c_idx = q.get("correct_index", 0)
                    pts = q.get("points", 1.0)
                    expl = q.get("explanation")

                    option_rows = []
                    for o_i, opt_text in enumerate(opts):
                        is_correct = (o_i == c_idx)
                        let = _opt_letters[o_i] if o_i < len(_opt_letters) else str(o_i + 1)
                        if is_correct:
                            bg_col = ft.Colors.with_opacity(0.12, ft.Colors.GREEN_600)
                            border_col = ft.Colors.with_opacity(0.4, ft.Colors.GREEN_600)
                            text_col = ft.Colors.GREEN_700
                            icon_prefix = ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=14, color=ft.Colors.GREEN_600)
                        else:
                            bg_col = ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE)
                            border_col = ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)
                            text_col = ft.Colors.ON_SURFACE
                            icon_prefix = ft.Container(
                                width=18, height=18, border_radius=9,
                                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Text(let, size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                            )

                        option_rows.append(
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                                border_radius=8,
                                bgcolor=bg_col,
                                border=ft.Border.all(1, border_col),
                                content=ft.Row([
                                    icon_prefix,
                                    ft.Text(f"{let}. {opt_text}", size=12, color=text_col, weight=ft.FontWeight.W_600 if is_correct else ft.FontWeight.NORMAL, expand=True),
                                    ft.Container(
                                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                        border_radius=4,
                                        bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.GREEN_600),
                                        content=ft.Text("CORRECT", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_800),
                                        visible=is_correct,
                                    ),
                                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                            )
                        )

                    expl_block = ft.Container(
                        visible=bool(expl),
                        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                        border_radius=8,
                        bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.BLUE_600),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.BLUE_600)),
                        content=ft.Row([
                            ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, size=14, color=ft.Colors.BLUE_600),
                            ft.Text(f"Explanation: {expl or ''}", size=11, color=ft.Colors.BLUE_800, expand=True),
                        ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    )

                    scen_text = (q.get("scenario_text") or "").strip()
                    scen_block = ft.Container(
                        visible=bool(scen_text),
                        padding=ft.Padding.all(8),
                        border_radius=6,
                        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.PRIMARY),
                        border=ft.Border(left=ft.BorderSide(3, ft.Colors.PRIMARY)),
                        content=ft.Column([
                            ft.Row([
                                ft.Icon(ft.Icons.MENU_BOOK_ROUNDED, size=12, color=ft.Colors.PRIMARY),
                                ft.Text("Scenario / Case Context", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                            ], spacing=4),
                            ft.Text(scen_text, size=11, color=ft.Colors.ON_SURFACE_VARIANT, italic=True),
                        ], spacing=4),
                    )

                    def make_edit_handler(target_q):
                        return lambda _: open_edit_q(target_q)

                    def make_delete_handler(target_qid):
                        return lambda _: page.run_task(delete_q, target_qid)

                    card = ft.Container(
                        padding=12,
                        border_radius=10,
                        bgcolor=ft.Colors.SURFACE,
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                        content=ft.Column([
                            ft.Row([
                                ft.Row([
                                    ft.Container(
                                        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                        border_radius=6,
                                        bgcolor=ft.Colors.with_opacity(0.12, theme_color),
                                        content=ft.Text(f"#{idx + 1}", size=11, weight=ft.FontWeight.BOLD, color=theme_color),
                                    ),
                                    ft.Container(
                                        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                        border_radius=6,
                                        bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                                        content=ft.Text(f"{pts} pt{'s' if pts != 1 else ''}", size=11, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ),
                                    ft.Container(
                                        visible=bool(scen_text),
                                        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                        border_radius=6,
                                        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY),
                                        content=ft.Row([
                                            ft.Icon(ft.Icons.MENU_BOOK_ROUNDED, size=11, color=ft.Colors.PRIMARY),
                                            ft.Text("Scenario", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                                        ], spacing=4, tight=True),
                                    ),
                                ], spacing=6, tight=True),
                                ft.Row([
                                    ft.IconButton(
                                        icon=ft.Icons.EDIT_OUTLINED,
                                        icon_size=17,
                                        tooltip="Edit Question",
                                        on_click=make_edit_handler(q),
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                        icon_size=17,
                                        icon_color=ft.Colors.RED_500,
                                        tooltip="Delete Question",
                                        on_click=make_delete_handler(q_id),
                                    ),
                                ], spacing=2, tight=True),
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            scen_block,
                            ft.Text(prompt, size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                            ft.Column(option_rows, spacing=4),
                            expl_block,
                        ], spacing=8),
                    )
                    cards.append(card)
                return cards

            def sync_exam_question_count():
                for e_item in data.get("exams", []):
                    if str(e_item.get("id")) == str(ex_id):
                        e_item["question_count"] = len(q_list)
                        break

            def refresh_ui():
                sync_exam_question_count()
                questions_list_view.controls = build_question_cards()
                title_text.value = f"Question Bank ({len(q_list)})"
                page.update()

            refresh_ui()

            def on_search(e=None):
                if e and getattr(e, "control", None) and e.control.value is not None:
                    search_query[0] = e.control.value.strip()
                    refresh_ui()

            search_bar = ft.TextField(
                hint_text="Search questions...",
                prefix_icon=ft.Icons.SEARCH_ROUNDED,
                height=38,
                text_size=12,
                content_padding=ft.Padding.symmetric(horizontal=10, vertical=0),
                border_radius=8,
                border_color=ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE),
                on_change=on_search,
            )

            async def _do_delete_q(target_qid):
                res = await delete_exam_question(token, org_id, c_id, ex_id, target_qid)
                if "error" in res:
                    show_snack(res["error"], is_error=True)
                else:
                    nonlocal q_list
                    q_list = [item for item in q_list if str(item.get("id")) != target_qid]
                    refresh_ui()
                    show_snack("Question deleted.")

            def delete_q(target_qid):
                show_confirm_dialog(
                    "Delete Question",
                    "Are you sure you want to delete this question from the bank?",
                    "Delete Question",
                    lambda: _do_delete_q(target_qid),
                    is_destructive=True,
                )

            def open_edit_q(target_q):
                target_qid = str(target_q.get("id"))
                opts = list(target_q.get("options", []))
                scenario_input = ft.TextField(
                    label="Scenario / Case Context (optional)",
                    value=target_q.get("scenario_text") or "",
                    multiline=True,
                    min_lines=2,
                    hint_text="Background context, clinical vignette, passage, or case details...",
                    **_INPUT,
                )
                prompt_input = ft.TextField(label="Question Prompt *", value=target_q.get("question_text", ""), multiline=True, min_lines=2, **_INPUT)
                opt_a_in = ft.TextField(label="Option A *", value=opts[0] if len(opts) > 0 else "", **_INPUT)
                opt_b_in = ft.TextField(label="Option B *", value=opts[1] if len(opts) > 1 else "", **_INPUT)
                opt_c_in = ft.TextField(label="Option C (optional)", value=opts[2] if len(opts) > 2 else "", **_INPUT)
                opt_d_in = ft.TextField(label="Option D (optional)", value=opts[3] if len(opts) > 3 else "", **_INPUT)

                curr_c_idx = str(target_q.get("correct_index", 0))
                ans_dropdown = ft.Dropdown(
                    label="Correct Option *",
                    options=[
                        ft.dropdown.Option("0", "Option A"),
                        ft.dropdown.Option("1", "Option B"),
                        ft.dropdown.Option("2", "Option C"),
                        ft.dropdown.Option("3", "Option D"),
                    ],
                    value=curr_c_idx,
                    border_radius=10,
                )
                points_input = ft.TextField(label="Points", value=str(target_q.get("points", 1.0)), keyboard_type=ft.KeyboardType.NUMBER, **_INPUT)
                expl_input = ft.TextField(label="Explanation (optional)", value=target_q.get("explanation") or "", multiline=True, **_INPUT)

                async def do_save_edit(e=None):
                    if not prompt_input.value or not opt_a_in.value or not opt_b_in.value:
                        show_snack("Question and at least Options A and B are required.", is_error=True)
                        return
                    new_opts = [opt_a_in.value.strip(), opt_b_in.value.strip()]
                    if opt_c_in.value and opt_c_in.value.strip():
                        new_opts.append(opt_c_in.value.strip())
                    if opt_d_in.value and opt_d_in.value.strip():
                        new_opts.append(opt_d_in.value.strip())

                    c_val = int(ans_dropdown.value or 0)
                    if c_val >= len(new_opts):
                        show_snack("Selected correct answer does not correspond to an available option.", is_error=True)
                        return

                    payload = {
                        "scenario_text": scenario_input.value.strip() if scenario_input.value and scenario_input.value.strip() else None,
                        "question_text": prompt_input.value.strip(),
                        "options": new_opts,
                        "correct_index": c_val,
                        "explanation": expl_input.value.strip() if expl_input.value else None,
                        "points": float(points_input.value or 1.0),
                    }
                    res = await update_exam_question(token, org_id, c_id, ex_id, target_qid, payload)
                    if "error" in res:
                        show_snack(res["error"], is_error=True)
                    else:
                        page.pop_dialog()
                        for item in q_list:
                            if str(item.get("id")) == target_qid:
                                item["scenario_text"] = payload["scenario_text"]
                                item["question_text"] = payload["question_text"]
                                item["options"] = payload["options"]
                                item["correct_index"] = payload["correct_index"]
                                item["explanation"] = payload["explanation"]
                                item["points"] = payload["points"]
                                break
                        refresh_ui()
                        show_snack("Question updated successfully.")

                edit_dlg = ft.AlertDialog(
                    modal=True,
                    title=ft.Row([
                        ft.Icon(ft.Icons.EDIT_ROUNDED, color=theme_color, size=20),
                        ft.Text("Edit Question", weight=ft.FontWeight.BOLD, size=15),
                    ], spacing=8),
                    content=ft.Container(
                        width=460, height=440,
                        content=ft.Column([
                            scenario_input,
                            prompt_input,
                            opt_a_in,
                            opt_b_in,
                            opt_c_in,
                            opt_d_in,
                            ans_dropdown,
                            points_input,
                            expl_input,
                        ], scroll=ft.ScrollMode.AUTO, spacing=8),
                    ),
                    actions=[
                        ft.TextButton("Cancel", on_click=lambda _: page.pop_dialog()),
                        ft.FilledButton("Save Changes", on_click=lambda _: page.run_task(do_save_edit), style=ft.ButtonStyle(bgcolor=theme_color)),
                    ],
                )
                page.show_dialog(edit_dlg)

            def open_add_single_q(e=None):
                scenario_f = ft.TextField(
                    label="Scenario / Case Context (optional)",
                    multiline=True,
                    min_lines=2,
                    hint_text="Background context, clinical vignette, passage, or case details...",
                    **_INPUT,
                )
                q_text = ft.TextField(label="Question Prompt *", multiline=True, min_lines=2, **_INPUT)
                opt_a = ft.TextField(label="Option A *", **_INPUT)
                opt_b = ft.TextField(label="Option B *", **_INPUT)
                opt_c = ft.TextField(label="Option C (optional)", **_INPUT)
                opt_d = ft.TextField(label="Option D (optional)", **_INPUT)
                ans_dd = ft.Dropdown(
                    label="Correct Option *",
                    options=[ft.dropdown.Option("0", "Option A"), ft.dropdown.Option("1", "Option B"),
                             ft.dropdown.Option("2", "Option C"), ft.dropdown.Option("3", "Option D")],
                    value="0",
                    border_radius=10,
                )
                points_f = ft.TextField(label="Points", value="1.0", keyboard_type=ft.KeyboardType.NUMBER, **_INPUT)
                expl_field = ft.TextField(label="Explanation (optional)", multiline=True, **_INPUT)

                async def do_save_q(e=None):
                    if not q_text.value or not opt_a.value or not opt_b.value:
                        show_snack("Question and at least Options A and B are required.", is_error=True)
                        return
                    opts = [opt_a.value.strip(), opt_b.value.strip()]
                    if opt_c.value and opt_c.value.strip(): opts.append(opt_c.value.strip())
                    if opt_d.value and opt_d.value.strip(): opts.append(opt_d.value.strip())

                    payload = {
                        "scenario_text": scenario_f.value.strip() if scenario_f.value and scenario_f.value.strip() else None,
                        "question_text": q_text.value.strip(),
                        "options": opts,
                        "correct_index": int(ans_dd.value or 0),
                        "explanation": expl_field.value.strip() if expl_field.value else None,
                        "points": float(points_f.value or 1.0),
                    }
                    res = await add_exam_question(token, org_id, c_id, ex_id, payload)
                    if "error" in res:
                        show_snack(res["error"], is_error=True)
                    else:
                        page.pop_dialog()
                        fresh = await get_cohort_exam(token, org_id, c_id, ex_id)
                        if "questions" in fresh:
                            nonlocal q_list
                            q_list = list(fresh["questions"])
                        refresh_ui()
                        show_snack("Question added!")

                add_dlg = ft.AlertDialog(
                    modal=True,
                    title=ft.Row([
                        ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE_ROUNDED, color=theme_color, size=20),
                        ft.Text("Add Single Question", weight=ft.FontWeight.BOLD, size=15),
                    ], spacing=8),
                    content=ft.Container(
                        width=460, height=440,
                        content=ft.Column([scenario_f, q_text, opt_a, opt_b, opt_c, opt_d, ans_dd, points_f, expl_field], scroll=ft.ScrollMode.AUTO, spacing=8),
                    ),
                    actions=[
                        ft.TextButton("Cancel", on_click=lambda _: page.pop_dialog()),
                        ft.FilledButton("Save Question", on_click=lambda _: page.run_task(do_save_q), style=ft.ButtonStyle(bgcolor=theme_color)),
                    ],
                )
                page.show_dialog(add_dlg)

            async def pick_excel_file(e=None):
                try:
                    files = await ft.FilePicker().pick_files(
                        dialog_title="Select Questions Spreadsheet (.xlsx or .csv)",
                        file_type=ft.FilePickerFileType.CUSTOM,
                        allowed_extensions=["xlsx", "xls", "csv"],
                        allow_multiple=False,
                        with_data=True,
                    )
                except Exception as picker_err:
                    show_snack(f"File picker error: {picker_err}", is_error=True)
                    return
                if files:
                    picked = files[0]
                    b_data = None
                    file_path = getattr(picked, "path", None)
                    if file_path:
                        try:
                            with open(file_path, "rb") as f:
                                b_data = f.read()
                        except Exception as ex:
                            show_snack(f"File read error: {ex}", is_error=True)
                            return
                    if not b_data and hasattr(picked, "bytes") and picked.bytes:
                        b_data = picked.bytes

                    if b_data:
                        upload_status.visible = True
                        page.update()

                        up_res = await upload_exam_questions_file(token, org_id, c_id, ex_id, b_data, picked.name)
                        upload_status.visible = False

                        if "error" in up_res:
                            page.update()
                            show_snack(up_res["error"], is_error=True)
                        else:
                            fresh = await get_cohort_exam(token, org_id, c_id, ex_id)
                            if "questions" in fresh:
                                nonlocal q_list
                                q_list = list(fresh["questions"])
                            refresh_ui()
                            imported_count = up_res.get("imported_count", len(q_list))
                            show_snack(f"Successfully imported {imported_count} questions into bank!")
                    else:
                        show_snack("No file data could be read.", is_error=True)

            async def do_download_template(e=None):
                csv_text = await get_exam_question_template_csv(token, org_id, c_id)
                if not csv_text or not csv_text.strip():
                    show_snack("Could not fetch template from server.", is_error=True)
                    return

                saved_to_disk = False
                try:
                    import os
                    dl_dir = os.path.join(os.path.expanduser("~"), "Downloads")
                    if os.path.exists(dl_dir):
                        target_file = os.path.join(dl_dir, "exam_questions_template.csv")
                        with open(target_file, "w", encoding="utf-8") as f:
                            f.write(csv_text)
                        saved_to_disk = True
                except Exception:
                    pass

                try:
                    if hasattr(page, "set_clipboard"):
                        await page.set_clipboard(csv_text)
                    elif hasattr(page, "clipboard"):
                        await page.clipboard.set(csv_text)
                except Exception:
                    pass

                if saved_to_disk:
                    show_snack("Template saved to Downloads/exam_questions_template.csv & copied to clipboard!")
                else:
                    show_snack("Template CSV copied to clipboard!")

            q_bank_dlg = ft.AlertDialog(
                modal=True,
                title=ft.Row([
                    ft.Icon(ft.Icons.QUIZ_ROUNDED, color=theme_color, size=22),
                    ft.Column([
                        title_text,
                        ft.Text(f"Exam: {ex_title}", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], spacing=1, expand=True),
                ], spacing=10),
                content=ft.Container(
                    width=min(getattr(page, "width", 800) - 24, 620),
                    height=520,
                    content=ft.Column([
                        ft.Row([
                            ft.OutlinedButton("Download Template", icon=ft.Icons.DOWNLOAD_ROUNDED, on_click=lambda e: page.run_task(do_download_template, e)),
                            ft.FilledButton(
                                "Bulk Upload Excel/CSV",
                                icon=ft.Icons.UPLOAD_FILE_ROUNDED,
                                style=ft.ButtonStyle(bgcolor=ft.Colors.DEEP_PURPLE_500),
                                on_click=lambda e: page.run_task(pick_excel_file, e),
                            ),
                            ft.FilledButton(
                                "+ Add Question",
                                icon=ft.Icons.ADD_ROUNDED,
                                style=ft.ButtonStyle(bgcolor=theme_color),
                                on_click=open_add_single_q,
                            ),
                        ], spacing=8, scroll=ft.ScrollMode.AUTO),
                        upload_status,
                        search_bar,
                        ft.Divider(height=1),
                        questions_list_view,
                    ], spacing=10, expand=True),
                ),
            )

            def on_close_q_bank(_=None):
                sync_exam_question_count()
                if hasattr(page, "pop_dialog"):
                    page.pop_dialog()
                if sub_tab["key"] == "exams":
                    sub_tab_container.content = render_sub_exams()
                    page.update()

            q_bank_dlg.actions = [
                ft.TextButton("Close", on_click=on_close_q_bank),
            ]
            page.show_dialog(q_bank_dlg)

        # ── GRADEBOOK & RESULTS MODAL ────────────────────────────────────
        async def show_gradebook_modal(ex_id: str):
            gradebook = await get_exam_gradebook(token, org_id, c_id, ex_id)
            if "error" in gradebook:
                show_snack("Could not load gradebook.", is_error=True)
                return

            roster = gradebook.get("roster", [])
            total_cand = gradebook.get("total_candidates", 0)
            avg_sc = gradebook.get("average_score", 0.0)
            pass_rt = gradebook.get("pass_rate", 0.0)
            top_sc = gradebook.get("top_score", 0.0)

            async def do_export(e=None):
                csv_str = await export_exam_gradebook_csv(token, org_id, c_id, ex_id)
                if not csv_str or not csv_str.strip():
                    show_snack("No gradebook data to export.", is_error=True)
                    return

                saved_to_disk = False
                try:
                    import os
                    dl_dir = os.path.join(os.path.expanduser("~"), "Downloads")
                    if os.path.exists(dl_dir):
                        clean_ex_id = str(ex_id)[:8]
                        target_file = os.path.join(dl_dir, f"gradebook_exam_{clean_ex_id}.csv")
                        with open(target_file, "w", encoding="utf-8") as f:
                            f.write(csv_str)
                        saved_to_disk = True
                except Exception:
                    pass

                try:
                    if hasattr(page, "set_clipboard"):
                        await page.set_clipboard(csv_str)
                    elif hasattr(page, "clipboard"):
                        await page.clipboard.set(csv_str)
                except Exception:
                    pass

                if saved_to_disk:
                    show_snack(f"Gradebook exported to Downloads/gradebook_exam_{str(ex_id)[:8]}.csv & copied to clipboard!")
                else:
                    show_snack("Gradebook CSV copied to clipboard!")

            gb_search_q = [""]
            rows_col = ft.Column(scroll=ft.ScrollMode.AUTO, spacing=6)

            def rebuild_gradebook_rows():
                q = gb_search_q[0].lower().strip()
                matched_rows = []
                for r in roster:
                    cand_name = (r.get("name") or "").lower()
                    cand_email = (r.get("email") or "").lower()
                    if q and (q not in cand_name and q not in cand_email):
                        continue
                    st = r.get("status", "NOT_ATTEMPTED")
                    if st == "PASSED":
                        col = ft.Colors.GREEN_700
                    elif st == "FAILED":
                        col = ft.Colors.RED_700
                    elif st == "IN_PROGRESS":
                        col = ft.Colors.AMBER_800
                    else:
                        col = ft.Colors.GREY_600

                    sc_str = f"{r.get('percentage')}%" if r.get('percentage') is not None else "—"
                    dur_min = round(r["duration_seconds"] / 60, 1) if r.get("duration_seconds") else "—"
                    v_count = r.get("violations_count", 0)

                    status_widgets = [
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                            border_radius=6, bgcolor=ft.Colors.with_opacity(0.1, col),
                            content=ft.Text(st, size=10, weight=ft.FontWeight.BOLD, color=col),
                        )
                    ]
                    if v_count > 0:
                        status_widgets.append(
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                border_radius=4,
                                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.RED_700),
                                content=ft.Row([
                                    ft.Icon(ft.Icons.SECURITY_ROUNDED, size=11, color=ft.Colors.RED_700),
                                    ft.Text(f"{v_count} strikes", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_700),
                                ], spacing=2, tight=True),
                            )
                        )

                    matched_rows.append(
                        ft.Container(
                            padding=10, border_radius=8, bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                            content=ft.Row([
                                ft.Text(f"#{r.get('rank', '-')}", size=12, weight=ft.FontWeight.BOLD, width=28),
                                ft.Column([
                                    ft.Text(r.get("name", ""), size=12, weight=ft.FontWeight.BOLD),
                                    ft.Text(r.get("email", ""), size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                                ], spacing=1, expand=True),
                                ft.Row(status_widgets, spacing=4, tight=True),
                                ft.Text(sc_str, size=12, weight=ft.FontWeight.BOLD, width=45, text_align=ft.TextAlign.RIGHT),
                                ft.Text(f"{dur_min}m" if dur_min != "—" else "—", size=10, color=ft.Colors.ON_SURFACE_VARIANT, width=35, text_align=ft.TextAlign.RIGHT),
                            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        )
                    )
                rows_col.controls = matched_rows if matched_rows else [
                    ft.Container(
                        alignment=ft.Alignment.CENTER,
                        padding=20,
                        content=ft.Text("No matching candidates found.", italic=True, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    )
                ] if roster else [ft.Text("No candidates enrolled.", italic=True, size=12)]
                page.update()

            def on_gb_search(ev):
                if ev and getattr(ev, "control", None):
                    gb_search_q[0] = ev.control.value or ""
                    rebuild_gradebook_rows()

            gb_search_f = ft.TextField(
                hint_text="Search candidate by name or email...",
                prefix_icon=ft.Icons.SEARCH_ROUNDED,
                height=38, text_size=12,
                content_padding=ft.Padding.symmetric(horizontal=10, vertical=0),
                border_radius=8,
                on_change=on_gb_search,
                expand=True,
            )
            rebuild_gradebook_rows()

            gb_dlg = ft.AlertDialog(
                modal=True,
                title=ft.Row([
                    ft.Icon(ft.Icons.ANALYTICS_ROUNDED, color=theme_color, size=20),
                    ft.Text(f"Gradebook: {gradebook.get('exam_title', 'Exam')}", weight=ft.FontWeight.BOLD, size=15),
                ], spacing=8),
                content=ft.Container(
                    width=min(getattr(page, "width", 800) - 32, 580),
                    height=460,
                    content=ft.Column([
                        ft.Row([
                            ft.Container(
                                padding=8, border_radius=8, bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.PRIMARY), expand=True,
                                content=ft.Column([ft.Text("Candidates", size=10), ft.Text(str(total_cand), size=14, weight=ft.FontWeight.BOLD)], spacing=1),
                            ),
                            ft.Container(
                                padding=8, border_radius=8, bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.GREEN_600), expand=True,
                                content=ft.Column([ft.Text("Pass Rate", size=10), ft.Text(f"{pass_rt}%", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_700)], spacing=1),
                            ),
                            ft.Container(
                                padding=8, border_radius=8, bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.BLUE_600), expand=True,
                                content=ft.Column([ft.Text("Avg Score", size=10), ft.Text(f"{avg_sc}%", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_700)], spacing=1),
                            ),
                            ft.Container(
                                padding=8, border_radius=8, bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.AMBER_600), expand=True,
                                content=ft.Column([ft.Text("Top Score", size=10), ft.Text(f"{top_sc}%", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_800)], spacing=1),
                            ),
                        ], spacing=6),
                        ft.Row([
                            gb_search_f,
                            ft.FilledButton("Export CSV", icon=ft.Icons.DOWNLOAD_ROUNDED,
                                            style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, padding=ft.Padding.symmetric(horizontal=10, vertical=4)),
                                            on_click=lambda e: page.run_task(do_export, e)),
                        ], spacing=8),
                        ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                        ft.Container(content=rows_col, expand=True),
                    ], spacing=10),
                ),
                actions=[ft.TextButton("Close", on_click=lambda _: page.pop_dialog())],
            )
            page.show_dialog(gb_dlg)

        # ── SUB TAB SWITCHER ─────────────────────────────────────────────
        def switch_sub_tab(key: str):
            sub_tab["key"] = key
            refresh_sub_tabs()
            if key == "overview":
                sub_tab_container.content = render_sub_overview()
            elif key == "courses":
                sub_tab_container.content = render_sub_courses()
            elif key == "members":
                sub_tab_container.content = render_sub_members()
            elif key == "exams":
                sub_tab_container.content = render_sub_exams()
            page.update()

        sub_tab_row = ft.Row(spacing=4, scroll=ft.ScrollMode.AUTO)
        sub_tab_buttons = ft.Container(
            padding=4,
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
            content=sub_tab_row,
        )

        def refresh_sub_tabs():
            def sub_btn(label: str, key: str, icon_name):
                is_sel = sub_tab["key"] == key
                return ft.Container(
                    padding=ft.Padding.symmetric(horizontal=14, vertical=7),
                    border_radius=10,
                    bgcolor=ft.Colors.SURFACE if is_sel else ft.Colors.TRANSPARENT,
                    shadow=ft.BoxShadow(blur_radius=4, color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK)) if is_sel else None,
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)) if is_sel else None,
                    ink=True,
                    on_click=lambda _, k=key: switch_sub_tab(k),
                    content=ft.Row([
                        ft.Icon(icon_name, size=14, color=theme_color if is_sel else ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(label, size=11, weight=ft.FontWeight.BOLD if is_sel else ft.FontWeight.W_500,
                                color=theme_color if is_sel else ft.Colors.ON_SURFACE),
                    ], spacing=5, tight=True),
                )

            sub_tab_row.controls = [
                sub_btn("Overview", "overview", ft.Icons.INFO_OUTLINE_ROUNDED),
                sub_btn("Courses", "courses", ft.Icons.AUTO_STORIES_ROUNDED),
                sub_btn("Members", "members", ft.Icons.PEOPLE_ROUNDED),
                sub_btn("Assessments", "exams", ft.Icons.TIMER_ROUNDED),
            ]

        refresh_sub_tabs()
        sub_tab_container.content = render_sub_overview()

        # Edit cohort dialog
        def open_edit_cohort_dialog(e=None):
            edit_name_field = ft.TextField(label="Cohort Name *", value=data.get("name", ""), **_INPUT)
            edit_desc_field = ft.TextField(label="Description", value=data.get("description") or "", multiline=True, min_lines=2, max_lines=3, **_INPUT)

            s_iso = data.get("start_date")
            e_iso = data.get("end_date")
            try:
                init_s = datetime.fromisoformat(str(s_iso).replace("Z", "+00:00")) if s_iso else datetime.now()
            except Exception:
                init_s = datetime.now()
            try:
                init_e = datetime.fromisoformat(str(e_iso).replace("Z", "+00:00")) if e_iso else (init_s + timedelta(days=90))
            except Exception:
                init_e = init_s + timedelta(days=90)

            edit_start_val = [init_s.date() if isinstance(init_s, datetime) else init_s]
            edit_end_val = [init_e.date() if isinstance(init_e, datetime) else init_e]

            edit_start_btn_text = ft.Text(edit_start_val[0].strftime("%b %d, %Y"), size=13, weight=ft.FontWeight.W_600)
            edit_end_btn_text = ft.Text(edit_end_val[0].strftime("%b %d, %Y"), size=13, weight=ft.FontWeight.W_600)

            def on_edit_s_change(ev=None):
                if ev and getattr(ev, "control", None) and ev.control.value:
                    val = ev.control.value
                    edit_start_val[0] = val.date() if isinstance(val, datetime) else val
                    edit_start_btn_text.value = edit_start_val[0].strftime("%b %d, %Y")
                    page.update()

            def on_edit_e_change(ev=None):
                if ev and getattr(ev, "control", None) and ev.control.value:
                    val = ev.control.value
                    edit_end_val[0] = val.date() if isinstance(val, datetime) else val
                    edit_end_btn_text.value = edit_end_val[0].strftime("%b %d, %Y")
                    page.update()

            edit_s_picker = ft.DatePicker(
                value=init_s if isinstance(init_s, datetime) else datetime.combine(init_s, datetime.min.time()),
                first_date=datetime.now() - timedelta(days=365 * 3),
                last_date=datetime.now() + timedelta(days=365 * 5),
                on_change=on_edit_s_change,
            )
            edit_e_picker = ft.DatePicker(
                value=init_e if isinstance(init_e, datetime) else datetime.combine(init_e, datetime.max.time()),
                first_date=datetime.now() - timedelta(days=365 * 3),
                last_date=datetime.now() + timedelta(days=365 * 5),
                on_change=on_edit_e_change,
            )
            page.overlay.extend([edit_s_picker, edit_e_picker])

            edit_start_btn = ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                border_radius=10,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE)),
                bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                ink=True,
                on_click=lambda _: setattr(edit_s_picker, "open", True) or page.update(),
                content=ft.Row([
                    ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, size=18, color=theme_color),
                    ft.Column([
                        ft.Text("Start Date", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                        edit_start_btn_text,
                    ], spacing=1, expand=True),
                ], spacing=8),
            )

            edit_end_btn = ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                border_radius=10,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE)),
                bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                ink=True,
                on_click=lambda _: setattr(edit_e_picker, "open", True) or page.update(),
                content=ft.Row([
                    ft.Icon(ft.Icons.EVENT_REPEAT_ROUNDED, size=18, color=theme_color),
                    ft.Column([
                        ft.Text("End Date", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                        edit_end_btn_text,
                    ], spacing=1, expand=True),
                ], spacing=8),
            )

            async def do_save_cohort(ev=None):
                if not edit_name_field.value or not edit_name_field.value.strip():
                    show_snack("Cohort name is required.", is_error=True)
                    return
                s_dt = datetime.combine(edit_start_val[0], datetime.min.time()).replace(tzinfo=timezone.utc)
                e_dt = datetime.combine(edit_end_val[0], datetime.max.time()).replace(tzinfo=timezone.utc)
                if e_dt <= s_dt:
                    show_snack("End date must be after start date.", is_error=True)
                    return

                payload = {
                    "name": edit_name_field.value.strip(),
                    "description": edit_desc_field.value.strip() if edit_desc_field.value else None,
                    "start_date": s_dt.isoformat(),
                    "end_date": e_dt.isoformat(),
                }
                res = await update_cohort(token, org_id, c_id, payload)
                if "error" in res:
                    show_snack(f"Failed to update cohort: {res['error']}", is_error=True)
                else:
                    if hasattr(page, "pop_dialog"):
                        page.pop_dialog()
                    show_snack("Cohort updated successfully!")
                    await open_cohort_details(c_id)

            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Row([
                    ft.Icon(ft.Icons.EDIT_ROUNDED, color=theme_color, size=22),
                    ft.Text("Edit Cohort Details", weight=ft.FontWeight.BOLD, size=16),
                ], spacing=8),
                content=ft.Container(
                    width=min(getattr(page, "width", 800) - 32, 500),
                    height=300,
                    content=ft.Column([
                        edit_name_field,
                        edit_desc_field,
                        ft.Row([
                            ft.Container(content=edit_start_btn, expand=True),
                            ft.Container(content=edit_end_btn, expand=True),
                        ], spacing=10),
                    ], scroll=ft.ScrollMode.AUTO, spacing=12),
                ),
                actions=[
                    ft.TextButton("Cancel", on_click=lambda _: page.pop_dialog()),
                    ft.FilledButton("Save Changes", on_click=lambda _: page.run_task(do_save_cohort), style=ft.ButtonStyle(bgcolor=theme_color)),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.show_dialog(dlg)

        # Delete cohort with confirmation
        def confirm_delete_cohort(e=None):
            async def _do():
                res = await delete_cohort(token, org_id, c_id)
                if "error" in res:
                    show_snack(res["error"], is_error=True)
                else:
                    show_snack("Cohort deleted.")
                    await load_cohorts_data()

            show_confirm_dialog(
                "Delete Cohort",
                f"Are you sure you want to delete cohort '{c_name}'? All candidate records, exam schedules, and question banks will be permanently removed.",
                "Delete Cohort",
                _do,
                is_destructive=True,
            )

        top_header = ft.Container(
            padding=ft.Padding.symmetric(horizontal=16, vertical=12),
            bgcolor=ft.Colors.SURFACE,
            border_radius=14,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK)),
            content=ft.Row([
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK_ROUNDED,
                    tooltip="Back to all cohorts",
                    on_click=lambda _: render_main_cohorts_view() or page.update(),
                ),
                ft.Column([
                    ft.Row([
                        ft.Text("Cohorts", size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
                        ft.Text("/", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(c_name, size=16, weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=4, tight=True),
                    ft.Row([
                        ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(f"{s_date} – {e_date} · {c_status}", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], spacing=4, tight=True),
                ], spacing=2, expand=True),
                ft.Row([
                    ft.IconButton(
                        icon=ft.Icons.EDIT_OUTLINED,
                        icon_color=theme_color,
                        tooltip="Edit cohort details",
                        on_click=open_edit_cohort_dialog,
                        visible=is_admin,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                        icon_color=ft.Colors.RED_500,
                        tooltip="Delete cohort",
                        on_click=confirm_delete_cohort,
                        visible=is_admin,
                    ),
                ], spacing=4, tight=True),
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        container.content = ft.Column([
            top_header,
            sub_tab_buttons,
            sub_tab_container,
        ], spacing=12, scroll=ft.ScrollMode.AUTO)

    page.run_task(load_cohorts_data)
    return container
