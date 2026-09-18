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
from datetime import datetime, timezone
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
            duration=3500,
        )
        if hasattr(page, "open"):
            page.open(snack)
        else:
            page.overlay.append(snack)
            snack.open = True
            page.update()

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

        now_str = datetime.now().strftime("%Y-%m-%d")
        three_months_str = (datetime.now().replace(month=(datetime.now().month % 12) + 1)).strftime("%Y-%m-%d")
        start_field = ft.TextField(label="Start Date (YYYY-MM-DD) *", value=now_str, hint_text="2026-09-01", **_INPUT)
        end_field = ft.TextField(label="End Date (YYYY-MM-DD) *", value=three_months_str, hint_text="2026-12-01", **_INPUT)

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

        def select_all_members(e):
            for chk in member_checks:
                chk.value = e.control.value
            page.update()

        all_members_toggle = ft.Checkbox(label="Select All Members", value=False, on_change=select_all_members)

        async def do_create(e):
            if not name_field.value or not name_field.value.strip():
                show_snack("Cohort name is required.", is_error=True)
                return

            try:
                s_dt = datetime.strptime(start_field.value.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
                e_dt = datetime.strptime(end_field.value.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except Exception:
                show_snack("Dates must be formatted as YYYY-MM-DD.", is_error=True)
                return

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
                show_snack("Cohort created successfully!")
                if hasattr(page, "pop_dialog"):
                    page.pop_dialog()
                await load_cohorts_data()

        dialog_content = ft.Container(
            width=min(getattr(page, "width", 800) - 32, 540),
            height=460,
            content=ft.Column([
                name_field,
                desc_field,
                ft.Row([
                    ft.Container(content=start_field, expand=True),
                    ft.Container(content=end_field, expand=True),
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
            st = (c.get("status") or "upcoming").upper()
            if state["filter"] != "ALL" and st != state["filter"]:
                continue
            if state["search"]:
                q = state["search"].lower()
                if q not in c.get("name", "").lower() and q not in (c.get("description") or "").lower():
                    continue
            filtered.append(c)

        # KPI Counter Cards
        active_count = sum(1 for c in all_cohorts if (c.get("status") or "").upper() == "ACTIVE")
        upcoming_count = sum(1 for c in all_cohorts if (c.get("status") or "").upper() == "UPCOMING")
        completed_count = sum(1 for c in all_cohorts if (c.get("status") or "").upper() == "COMPLETED")

        def kpi_card(label: str, count: int, icon_name, color):
            return ft.Container(
                expand=True,
                padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                border_radius=12,
                bgcolor=ft.Colors.with_opacity(0.06, color),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.15, color)),
                content=ft.Row([
                    ft.Container(
                        padding=8, border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.15, color),
                        content=ft.Icon(icon_name, size=18, color=color),
                    ),
                    ft.Column([
                        ft.Text(str(count), size=18, weight=ft.FontWeight.BOLD, color=color),
                        ft.Text(label, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], spacing=1),
                ], spacing=10),
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
                padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                border_radius=20,
                bgcolor=theme_color if is_sel else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
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
        def on_search_change(e):
            state["search"] = e.control.value.strip()
            render_main_cohorts_view()
            page.update()

        search_input = ft.TextField(
            hint_text="Search cohort name or topic...",
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            border_radius=10,
            text_size=12,
            height=40,
            content_padding=ft.Padding.symmetric(horizontal=10, vertical=0),
            border_color=ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE),
            on_change=on_search_change,
            expand=True,
        )

        create_btn = ft.FilledButton(
            content=ft.Row([
                ft.Icon(ft.Icons.ADD_ROUNDED, size=16, color=ft.Colors.WHITE),
                ft.Text("New Cohort", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
            ], tight=True, spacing=6),
            style=ft.ButtonStyle(bgcolor=theme_color, padding=ft.Padding.symmetric(horizontal=14, vertical=10)),
            on_click=open_create_cohort_dialog,
        )

        # Cohort Cards
        cohort_cards = []
        for c in filtered:
            c_id = str(c["id"])
            c_name = c.get("name", "Untitled Cohort")
            c_desc = c.get("description") or "No description provided."
            c_status = (c.get("status") or "upcoming").upper()
            s_date = format_date_str(c.get("start_date"))
            e_date = format_date_str(c.get("end_date"))
            m_count = c.get("members_count", 0)
            crs_count = c.get("courses_count", 0)
            ex_count = c.get("exams_count", 0)

            if c_status == "ACTIVE":
                badge_bg, badge_fg = ft.Colors.with_opacity(0.12, ft.Colors.GREEN_600), ft.Colors.GREEN_700
            elif c_status == "COMPLETED":
                badge_bg, badge_fg = ft.Colors.with_opacity(0.12, ft.Colors.GREY_600), ft.Colors.GREY_700
            else:
                badge_bg, badge_fg = ft.Colors.with_opacity(0.12, ft.Colors.BLUE_600), ft.Colors.BLUE_700

            def make_open_handler(target_id):
                return lambda _: page.run_task(open_cohort_details, target_id)

            card = ft.Container(
                padding=16,
                border_radius=14,
                bgcolor=ft.Colors.SURFACE,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)),
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
                        ft.Row([
                            ft.Icon(ft.Icons.PEOPLE_ROUNDED, size=14, color=theme_color),
                            ft.Text(f"{m_count} Members", size=11, weight=ft.FontWeight.W_600),
                        ], spacing=4, tight=True),
                        ft.Row([
                            ft.Icon(ft.Icons.AUTO_STORIES_ROUNDED, size=14, color=theme_color),
                            ft.Text(f"{crs_count} Courses", size=11, weight=ft.FontWeight.W_600),
                        ], spacing=4, tight=True),
                        ft.Row([
                            ft.Icon(ft.Icons.TIMER_ROUNDED, size=14, color=theme_color),
                            ft.Text(f"{ex_count} Exams", size=11, weight=ft.FontWeight.W_600),
                        ], spacing=4, tight=True),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
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
        c_status = (data.get("status") or "upcoming").upper()

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

                def remove_crs(c_target):
                    async def _do(_):
                        res = await remove_cohort_course(token, org_id, c_id, c_target)
                        if "error" in res:
                            show_snack(res["error"], is_error=True)
                        else:
                            show_snack("Course removed from cohort.")
                            await open_cohort_details(c_id)
                    return _do

                cards.append(
                    ft.Container(
                        padding=12, border_radius=12,
                        bgcolor=ft.Colors.SURFACE,
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
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
                                icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                icon_color=ft.Colors.RED_500,
                                icon_size=18,
                                tooltip="Remove from cohort",
                                on_click=remove_crs(crs_id),
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

                async def do_add(e):
                    selected = [chk.data for chk in checks if chk.value]
                    if not selected:
                        show_snack("Select at least one course.", is_error=True)
                        return
                    res = await add_cohort_courses(token, org_id, c_id, selected)
                    if "error" in res:
                        show_snack(res["error"], is_error=True)
                    else:
                        show_snack("Courses added to cohort successfully.")
                        page.pop_dialog()
                        await open_cohort_details(c_id)

                dlg = ft.AlertDialog(
                    modal=True,
                    title=ft.Text("Add Courses to Cohort", weight=ft.FontWeight.BOLD, size=15),
                    content=ft.Container(
                        width=380, height=260,
                        content=ft.Column(checks if checks else [ft.Text("All org courses are already registered.")], scroll=ft.ScrollMode.AUTO),
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

                def remove_mem(u_target):
                    async def _do(_):
                        res = await remove_cohort_member(token, org_id, c_id, u_target)
                        if "error" in res:
                            show_snack(res["error"], is_error=True)
                        else:
                            show_snack("Member removed from cohort.")
                            await open_cohort_details(c_id)
                    return _do

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
                                on_click=remove_mem(m_uid),
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

                async def do_add(e):
                    selected = [chk.data for chk in checks if chk.value]
                    if not selected:
                        show_snack("Select at least one member.", is_error=True)
                        return
                    res = await add_cohort_members(token, org_id, c_id, selected)
                    if "error" in res:
                        show_snack(res["error"], is_error=True)
                    else:
                        show_snack("Members enrolled into cohort successfully.")
                        page.pop_dialog()
                        await open_cohort_details(c_id)

                dlg = ft.AlertDialog(
                    modal=True,
                    title=ft.Text("Enroll Members into Cohort", weight=ft.FontWeight.BOLD, size=15),
                    content=ft.Container(
                        width=380, height=280,
                        content=ft.Column(checks if checks else [ft.Text("All org members are already enrolled.")], scroll=ft.ScrollMode.AUTO),
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
                ex_status = ex.get("status", "SCHEDULED")
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
                            show_snack(exam_run_payload["error"], is_error=True)
                            await open_cohort_details(c_id)
                            return

                        exam_view = build_cohort_exam_view(
                            page=page,
                            exam_payload=exam_run_payload,
                            org_id=org_id,
                            cohort_id=c_id,
                            exam_id=target_ex_id,
                            token=token,
                            on_exit=lambda _: page.run_task(open_cohort_details, c_id),
                        )
                        container.content = exam_view
                        page.update()
                    return _do

                # Admin Actions
                def open_q_bank(target_ex_id):
                    return lambda _: page.run_task(show_question_bank_modal, target_ex_id)

                def open_grades(target_ex_id):
                    return lambda _: page.run_task(show_gradebook_modal, target_ex_id)

                def delete_ex(target_ex_id):
                    async def _do(_):
                        res = await delete_cohort_exam(token, org_id, c_id, target_ex_id)
                        if "error" in res:
                            show_snack(res["error"], is_error=True)
                        else:
                            show_snack("Exam deleted.")
                            await open_cohort_details(c_id)
                    return _do

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
                                ft.OutlinedButton("Questions", icon=ft.Icons.QUIZ_ROUNDED, on_click=open_q_bank(ex_id), visible=is_admin),
                                ft.FilledButton("Gradebook", icon=ft.Icons.ANALYTICS_ROUNDED, on_click=open_grades(ex_id),
                                                style=ft.ButtonStyle(bgcolor=theme_color), visible=is_admin),
                                ft.IconButton(ft.Icons.DELETE_OUTLINE_ROUNDED, icon_color=ft.Colors.RED_500, icon_size=18,
                                              on_click=delete_ex(ex_id), visible=is_admin),
                            ], spacing=6, tight=True),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ], spacing=10),
                )
                exam_cards.append(card)

            # Schedule New Exam Dialog
            def open_schedule_exam_dlg(e=None):
                title_field = ft.TextField(label="Exam Title *", hint_text="e.g. Mid-term Assessment", **_INPUT)
                inst_field = ft.TextField(label="Candidate Instructions", hint_text="Rules, prohibited materials, single attempt warning...", multiline=True, min_lines=2, **_INPUT)
                dur_field = ft.TextField(label="Duration (Minutes) *", value="60", **_INPUT)
                pass_field = ft.TextField(label="Pass Mark (%) *", value="70", **_INPUT)

                now_iso = datetime.now().strftime("%Y-%m-%d %H:%M")
                later_iso = (datetime.now().replace(day=datetime.now().day + 7)).strftime("%Y-%m-%d %H:%M")
                open_field = ft.TextField(label="Opens At (YYYY-MM-DD HH:MM) *", value=now_iso, **_INPUT)
                close_field = ft.TextField(label="Closes At (YYYY-MM-DD HH:MM) *", value=later_iso, **_INPUT)

                attempts_field = ft.TextField(label="Max Attempts", value="1", **_INPUT)
                security_dd = ft.Dropdown(
                    label="Anti-Cheat Security Policy *",
                    options=[
                        ft.dropdown.Option("monitored", "Monitored Mode (2 Warnings before auto-submit)"),
                        ft.dropdown.Option("strict", "Strict Mode (Immediate auto-submit on app/window switch)"),
                        ft.dropdown.Option("relaxed", "Relaxed Mode (Practice / no auto-submit)"),
                    ],
                    value="monitored",
                    border_radius=10,
                )
                shuffle_chk = ft.Checkbox(label="Shuffle Question Order", value=True)
                immediate_chk = ft.Checkbox(label="Show Immediate Results to Candidate", value=True)

                async def do_schedule(e):
                    if not title_field.value or not title_field.value.strip():
                        show_snack("Exam title is required.", is_error=True)
                        return
                    try:
                        o_dt = datetime.strptime(open_field.value.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
                        c_dt = datetime.strptime(close_field.value.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
                    except Exception:
                        show_snack("Dates must be formatted as YYYY-MM-DD HH:MM.", is_error=True)
                        return

                    if c_dt <= o_dt:
                        show_snack("Close date must be after open date.", is_error=True)
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
                        "shuffle_questions": shuffle_chk.value,
                        "show_immediate_results": immediate_chk.value,
                    }

                    res = await create_cohort_exam(token, org_id, c_id, payload)
                    if "error" in res:
                        show_snack(res["error"], is_error=True)
                    else:
                        show_snack("Exam scheduled successfully.")
                        page.pop_dialog()
                        await open_cohort_details(c_id)

                dlg = ft.AlertDialog(
                    modal=True,
                    title=ft.Row([ft.Icon(ft.Icons.TIMER_ROUNDED, color=theme_color, size=22), ft.Text("Schedule Timed Exam", weight=ft.FontWeight.BOLD, size=15)], spacing=8),
                    content=ft.Container(
                        width=min(getattr(page, "width", 800) - 32, 500),
                        height=420,
                        content=ft.Column([
                            title_field,
                            inst_field,
                            ft.Row([
                                ft.Container(open_field, expand=True),
                                ft.Container(close_field, expand=True),
                            ], spacing=10),
                            ft.Row([
                                ft.Container(dur_field, expand=True),
                                ft.Container(pass_field, expand=True),
                                ft.Container(attempts_field, expand=True),
                            ], spacing=10),
                            security_dd,
                            shuffle_chk,
                            immediate_chk,
                        ], scroll=ft.ScrollMode.AUTO, spacing=10),
                    ),
                    actions=[
                        ft.TextButton("Cancel", on_click=lambda _: page.pop_dialog()),
                        ft.FilledButton("Schedule Exam", on_click=lambda _: page.run_task(do_schedule), style=ft.ButtonStyle(bgcolor=theme_color)),
                    ],
                )
                page.show_dialog(dlg)

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

            q_list = exam_data.get("questions", [])

            # File upload via FilePicker service
            async def pick_excel_file(e):
                file_picker = ft.FilePicker()
                result = await file_picker.pick_files(
                    dialog_title="Select Questions Spreadsheet (.xlsx or .csv)",
                    file_type=ft.FilePickerFileType.CUSTOM,
                    allowed_extensions=["xlsx", "xls", "csv"],
                )
                if result and result.files:
                    picked = result.files[0]
                    file_path = picked.path
                    if file_path:
                        try:
                            with open(file_path, "rb") as f:
                                b_data = f.read()
                            show_snack("Uploading and parsing question sheet...")
                            up_res = await upload_exam_questions_file(token, org_id, c_id, ex_id, b_data, picked.name)
                            if "error" in up_res:
                                show_snack(up_res["error"], is_error=True)
                            else:
                                show_snack(f"Imported {up_res.get('imported_count', 0)} questions!")
                                page.pop_dialog()
                                await show_question_bank_modal(ex_id)
                        except Exception as ex:
                            show_snack(f"File read error: {ex}", is_error=True)

            # Manual question add
            def open_add_single_q(e=None):
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
                expl_field = ft.TextField(label="Explanation (optional)", multiline=True, **_INPUT)

                async def do_save_q(e):
                    if not q_text.value or not opt_a.value or not opt_b.value:
                        show_snack("Question and at least Options A and B are required.", is_error=True)
                        return
                    opts = [opt_a.value.strip(), opt_b.value.strip()]
                    if opt_c.value and opt_c.value.strip(): opts.append(opt_c.value.strip())
                    if opt_d.value and opt_d.value.strip(): opts.append(opt_d.value.strip())

                    payload = {
                        "question_text": q_text.value.strip(),
                        "options": opts,
                        "correct_index": int(ans_dd.value or 0),
                        "explanation": expl_field.value.strip() if expl_field.value else None,
                        "points": 1.0,
                    }
                    res = await add_exam_question(token, org_id, c_id, ex_id, payload)
                    if "error" in res:
                        show_snack(res["error"], is_error=True)
                    else:
                        show_snack("Question added!")
                        page.pop_dialog()
                        await show_question_bank_modal(ex_id)

                add_dlg = ft.AlertDialog(
                    modal=True,
                    title=ft.Text("Add Single Question", weight=ft.FontWeight.BOLD, size=15),
                    content=ft.Container(
                        width=420, height=380,
                        content=ft.Column([q_text, opt_a, opt_b, opt_c, opt_d, ans_dd, expl_field], scroll=ft.ScrollMode.AUTO, spacing=8),
                    ),
                    actions=[
                        ft.TextButton("Cancel", on_click=lambda _: page.pop_dialog()),
                        ft.FilledButton("Save Question", on_click=lambda _: page.run_task(do_save_q), style=ft.ButtonStyle(bgcolor=theme_color)),
                    ],
                )
                page.show_dialog(add_dlg)

            # Template download
            async def do_download_template(e):
                csv_text = await get_exam_question_template_csv(token, org_id, c_id)
                if csv_text:
                    show_snack("Template copied / downloaded.")
                else:
                    show_snack("Could not fetch template.", is_error=True)

            q_tiles = []
            for idx, q in enumerate(q_list):
                q_id = str(q["id"])
                c_idx = q.get("correct_index", 0)
                opts = q.get("options", [])
                correct_str = opts[c_idx] if c_idx < len(opts) else "—"

                def delete_q(target_qid):
                    async def _do(_):
                        await delete_exam_question(token, org_id, c_id, ex_id, target_qid)
                        page.pop_dialog()
                        await show_question_bank_modal(ex_id)
                    return _do

                q_tiles.append(
                    ft.Container(
                        padding=10, border_radius=8, bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                        content=ft.Row([
                            ft.Column([
                                ft.Text(f"Q{idx + 1}: {q.get('question_text')}", size=12, weight=ft.FontWeight.BOLD),
                                ft.Text(f"Correct: {correct_str} · ({len(opts)} options)", size=11, color=ft.Colors.GREEN_700),
                            ], spacing=2, expand=True),
                            ft.IconButton(ft.Icons.DELETE_OUTLINE_ROUNDED, icon_size=16, icon_color=ft.Colors.RED_500, on_click=delete_q(q_id)),
                        ], spacing=8),
                    )
                )

            q_bank_dlg = ft.AlertDialog(
                modal=True,
                title=ft.Row([
                    ft.Icon(ft.Icons.QUIZ_ROUNDED, color=theme_color, size=20),
                    ft.Text(f"Question Bank ({len(q_list)})", weight=ft.FontWeight.BOLD, size=15),
                ], spacing=8),
                content=ft.Container(
                    width=min(getattr(page, "width", 800) - 32, 520),
                    height=440,
                    content=ft.Column([
                        ft.Row([
                            ft.OutlinedButton("Download Template", icon=ft.Icons.DOWNLOAD_ROUNDED, on_click=lambda e: page.run_task(do_download_template, e)),
                            ft.FilledButton("Bulk Upload Excel/CSV", icon=ft.Icons.UPLOAD_FILE_ROUNDED,
                                            style=ft.ButtonStyle(bgcolor=ft.Colors.DEEP_PURPLE_500),
                                            on_click=lambda e: page.run_task(pick_excel_file, e)),
                        ], spacing=8),
                        ft.FilledButton("+ Add Single Question", icon=ft.Icons.ADD_ROUNDED,
                                        style=ft.ButtonStyle(bgcolor=theme_color),
                                        on_click=open_add_single_q),
                        ft.Divider(height=1),
                        ft.Column(q_tiles if q_tiles else [ft.Text("No questions in bank yet.", italic=True, size=12)], scroll=ft.ScrollMode.AUTO),
                    ], spacing=10),
                ),
                actions=[
                    ft.TextButton("Close", on_click=lambda _: page.pop_dialog()),
                ],
            )
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

            async def do_export(e):
                csv_str = await export_exam_gradebook_csv(token, org_id, c_id, ex_id)
                show_snack("Gradebook exported successfully.")

            rows = []
            for r in roster:
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

                rows.append(
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

            gb_dlg = ft.AlertDialog(
                modal=True,
                title=ft.Row([
                    ft.Icon(ft.Icons.ANALYTICS_ROUNDED, color=theme_color, size=20),
                    ft.Text(f"Gradebook: {gradebook.get('exam_title', 'Exam')}", weight=ft.FontWeight.BOLD, size=15),
                ], spacing=8),
                content=ft.Container(
                    width=min(getattr(page, "width", 800) - 32, 540),
                    height=440,
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
                            ft.Text("Candidate Results", size=12, weight=ft.FontWeight.BOLD),
                            ft.FilledButton("Export CSV", icon=ft.Icons.DOWNLOAD_ROUNDED,
                                            style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, padding=ft.Padding.symmetric(horizontal=10, vertical=4)),
                                            on_click=lambda e: page.run_task(do_export, e)),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Divider(height=1),
                        ft.Column(rows if rows else [ft.Text("No candidates enrolled.", italic=True, size=12)], scroll=ft.ScrollMode.AUTO),
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

        sub_tab_buttons = ft.Row(spacing=6, scroll=ft.ScrollMode.AUTO)

        def refresh_sub_tabs():
            def sub_btn(label: str, key: str, icon_name):
                is_sel = sub_tab["key"] == key
                return ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                    border_radius=8,
                    bgcolor=theme_color if is_sel else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                    ink=True,
                    on_click=lambda _, k=key: switch_sub_tab(k),
                    content=ft.Row([
                        ft.Icon(icon_name, size=14, color=ft.Colors.WHITE if is_sel else ft.Colors.ON_SURFACE),
                        ft.Text(label, size=11, weight=ft.FontWeight.BOLD if is_sel else ft.FontWeight.W_500,
                                color=ft.Colors.WHITE if is_sel else ft.Colors.ON_SURFACE),
                    ], spacing=4, tight=True),
                )

            sub_tab_buttons.controls = [
                sub_btn("Overview", "overview", ft.Icons.INFO_OUTLINE_ROUNDED),
                sub_btn("Courses", "courses", ft.Icons.AUTO_STORIES_ROUNDED),
                sub_btn("Members", "members", ft.Icons.PEOPLE_ROUNDED),
                sub_btn("Assessments", "exams", ft.Icons.TIMER_ROUNDED),
            ]

        refresh_sub_tabs()
        sub_tab_container.content = render_sub_overview()

        # Delete cohort
        async def do_delete_cohort(_):
            res = await delete_cohort(token, org_id, c_id)
            if "error" in res:
                show_snack(res["error"], is_error=True)
            else:
                show_snack("Cohort deleted.")
                await load_cohorts_data()

        top_header = ft.Container(
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            bgcolor=ft.Colors.SURFACE,
            border_radius=12,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
            content=ft.Row([
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK_ROUNDED,
                    tooltip="Back to all cohorts",
                    on_click=lambda _: render_main_cohorts_view() or page.update(),
                ),
                ft.Column([
                    ft.Text(c_name, size=15, weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(f"{s_date} – {e_date} · {c_status}", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                ], spacing=1, expand=True),
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                    icon_color=ft.Colors.RED_500,
                    tooltip="Delete cohort",
                    on_click=lambda e: page.run_task(do_delete_cohort, e),
                    visible=is_admin,
                ),
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        container.content = ft.Column([
            top_header,
            sub_tab_buttons,
            sub_tab_container,
        ], spacing=12, scroll=ft.ScrollMode.AUTO)

    page.run_task(load_cohorts_data)
    return container
