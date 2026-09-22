"""
Learner Cohorts & Training Hub:
  * Dedicated high-polish hub for learners to view enrolled cohorts.
  * Curriculum track with course progress, lessons count, and direct study access.
  * Scheduled assessments deck with live status, timer window, and direct exam runner launch.
  * Responsive, glassmorphic layout adhering to modern design principles and Flet 0.86.5 conventions.
"""

import asyncio
from datetime import datetime, timezone
import flet as ft

from src.requests.Cohorts import get_learner_cohorts, start_cohort_exam
from src.components.cohort_exam_runner import build_cohort_exam_view


def _format_date(dt_str) -> str:
    if not dt_str:
        return "TBD"
    try:
        dt = datetime.fromisoformat(str(dt_str).replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y")
    except Exception:
        return str(dt_str)[:10]


def _format_datetime(dt_str) -> str:
    if not dt_str:
        return "TBD"
    try:
        dt = datetime.fromisoformat(str(dt_str).replace("Z", "+00:00"))
        return dt.strftime("%b %d, %I:%M %p")
    except Exception:
        return str(dt_str)[:16]


def _get_effective_cohort_status(cohort: dict) -> str:
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


def _get_effective_exam_status(exam: dict) -> str:
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


def build_learner_cohorts_view(
    page: ft.Page,
    token: str,
    on_back=None,
    initial_cohort_id: str = None,
    theme_color=ft.Colors.PRIMARY,
) -> ft.Container:
    """Returns a full-featured container rendering the learner's cohorts and curriculum."""
    root_container = ft.Container(expand=True)

    state = {
        "cohorts": [],
        "active_urgent_exams": [],
        "selected_cohort_id": initial_cohort_id,
        "active_subtab": "curriculum",  # "curriculum" or "assessments"
        "loading": True,
    }

    def is_mobile() -> bool:
        w = page.width or (getattr(page.window, "width", 1000))
        return w < 720

    def show_snack(text: str, is_error: bool = False):
        snack = ft.SnackBar(
            content=ft.Text(text, size=13, color=ft.Colors.WHITE),
            bgcolor=ft.Colors.RED_700 if is_error else ft.Colors.GREEN_700,
            duration=3000,
            behavior=ft.SnackBarBehavior.FLOATING,
        )
        try:
            page.overlay.append(snack)
            snack.open = True
            page.update()
        except Exception:
            pass

    async def load_data():
        state["loading"] = True
        render_ui()
        page.update()

        res = await get_learner_cohorts(token)
        cohorts = res.get("cohorts", [])
        state["cohorts"] = cohorts
        state["active_urgent_exams"] = res.get("active_urgent_exams", [])
        state["loading"] = False

        # If an initial_cohort_id was specified, pick that, otherwise pick the first cohort
        if cohorts:
            found = False
            if state["selected_cohort_id"]:
                for c in cohorts:
                    if str(c.get("id")) == str(state["selected_cohort_id"]):
                        found = True
                        break
            if not found:
                state["selected_cohort_id"] = str(cohorts[0].get("id"))

        render_ui()
        page.update()

    # ── Candidate Take Exam Launcher ──────────────────────────────────────────
    def launch_candidate_exam(org_id: str, cohort_id: str, exam_id: str):
        async def _do(_):
            root_container.content = ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=40,
                content=ft.Column([
                    ft.ProgressRing(color=theme_color, width=36, height=36),
                    ft.Text("Preparing your secure assessment session...", size=13, weight=ft.FontWeight.W_500),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True, spacing=14),
            )
            page.update()

            exam_payload = await start_cohort_exam(token, str(org_id), str(cohort_id), str(exam_id))
            if "error" in exam_payload:
                err_msg = exam_payload["error"]
                root_container.content = ft.Container(
                    expand=True,
                    alignment=ft.Alignment.CENTER,
                    padding=24,
                    content=ft.Container(
                        width=460,
                        padding=28,
                        border_radius=18,
                        bgcolor=ft.Colors.SURFACE,
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                        shadow=ft.BoxShadow(blur_radius=20, color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK)),
                        content=ft.Column([
                            ft.Container(
                                width=52, height=52, border_radius=26,
                                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_700),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.LOCK_CLOCK_ROUNDED, size=26, color=ft.Colors.AMBER_700),
                            ),
                            ft.Text("Assessment Unavailable", size=17, weight=ft.FontWeight.BOLD),
                            ft.Text(err_msg, size=13, color=ft.Colors.ON_SURFACE, text_align=ft.TextAlign.CENTER),
                            ft.Text(
                                "If you need an additional attempt or have questions about eligibility, please reach out to your instructor or cohort administrator.",
                                size=11, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Container(height=8),
                            ft.FilledButton(
                                "Return to Cohort",
                                icon=ft.Icons.ARROW_BACK_ROUNDED,
                                on_click=lambda _: render_ui() or page.update(),
                                style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=20, vertical=10)),
                            ),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                    ),
                )
                page.update()
                return

            def on_exit_exam(*_):
                page.run_task(load_data)

            exam_view = build_cohort_exam_view(
                page=page,
                exam_payload=exam_payload,
                org_id=str(org_id),
                cohort_id=str(cohort_id),
                exam_id=str(exam_id),
                token=token,
                on_exit=on_exit_exam,
            )
            root_container.content = exam_view
            page.update()

        return _do

    # ── Main Render UI ────────────────────────────────────────────────────────
    def render_ui():
        if state["loading"]:
            root_container.content = ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=60,
                content=ft.Column([
                    ft.ProgressRing(color=theme_color, width=36, height=36),
                    ft.Text("Loading Your Training Cohorts...", size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True, spacing=12),
            )
            return

        cohorts = state["cohorts"]
        if not cohorts:
            # Empty state: learner is not enrolled in any cohorts
            root_container.content = ft.Container(
                expand=True,
                padding=24,
                content=ft.Column([
                    # Top bar
                    ft.Row([
                        ft.IconButton(
                            icon=ft.Icons.ARROW_BACK_ROUNDED,
                            tooltip="Go Back",
                            on_click=lambda _: on_back() if on_back else page.go("/dashboard"),
                        ),
                        ft.Text("My Training Cohorts", size=18, weight=ft.FontWeight.BOLD),
                    ], spacing=8),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Column([
                            ft.Container(
                                width=72, height=72, border_radius=36,
                                bgcolor=ft.Colors.with_opacity(0.08, theme_color),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.GROUPS_ROUNDED, size=36, color=theme_color),
                            ),
                            ft.Text("No Enrolled Cohorts Yet", size=17, weight=ft.FontWeight.BOLD),
                            ft.Container(
                                width=400,
                                content=ft.Text(
                                    "You have not been assigned to any organization training cohorts yet. When your institution or company enrolls you, your structured curriculum and scheduled assessments will appear right here.",
                                    size=12, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER,
                                ),
                            ),
                            ft.Container(height=10),
                            ft.FilledButton(
                                "Explore Course Catalog",
                                icon=ft.Icons.AUTO_STORIES_ROUNDED,
                                on_click=lambda _: page.go("/courses"),
                                style=ft.ButtonStyle(bgcolor=theme_color, padding=ft.Padding.symmetric(horizontal=18, vertical=12)),
                            ),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                    ),
                ], spacing=16),
            )
            return

        # Locate selected cohort
        selected_c = None
        for c in cohorts:
            if str(c.get("id")) == str(state["selected_cohort_id"]):
                selected_c = c
                break
        if not selected_c:
            selected_c = cohorts[0]
            state["selected_cohort_id"] = str(selected_c.get("id"))

        c_id = str(selected_c.get("id"))
        c_name = selected_c.get("name", "Untitled Cohort")
        c_org = selected_c.get("organisation_name", "Organisation")
        c_org_id = str(selected_c.get("organisation_id", ""))
        c_desc = selected_c.get("description") or ""
        c_status = _get_effective_cohort_status(selected_c)
        s_date = _format_date(selected_c.get("start_date"))
        e_date = _format_date(selected_c.get("end_date"))
        c_courses = selected_c.get("courses", [])
        c_exams = selected_c.get("exams", [])

        # Calculate overall curriculum progress
        avg_prog = 0
        if c_courses:
            avg_prog = round(sum(crs.get("progress", 0) for crs in c_courses) / len(c_courses))

        # Status badge styling
        if c_status == "ACTIVE":
            st_bg, st_fg = ft.Colors.with_opacity(0.12, ft.Colors.GREEN_600), ft.Colors.GREEN_700
            dot_color = ft.Colors.GREEN_600
        elif c_status == "COMPLETED":
            st_bg, st_fg = ft.Colors.with_opacity(0.10, ft.Colors.GREY_600), ft.Colors.GREY_700
            dot_color = ft.Colors.GREY_600
        else:
            st_bg, st_fg = ft.Colors.with_opacity(0.12, ft.Colors.BLUE_600), ft.Colors.BLUE_700
            dot_color = ft.Colors.BLUE_600

        # Cohort switcher chips (if learner belongs to multiple cohorts)
        cohort_switcher_chips = []
        if len(cohorts) > 1:
            for ch in cohorts:
                ch_id = str(ch.get("id"))
                is_selected = ch_id == c_id
                ch_name = ch.get("name", "Cohort")

                def make_select_fn(target_id):
                    def _sel(_):
                        state["selected_cohort_id"] = target_id
                        render_ui()
                        page.update()
                    return _sel

                cohort_switcher_chips.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                        border_radius=20,
                        bgcolor=theme_color if is_selected else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                        border=ft.Border.all(1, theme_color if is_selected else ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
                        ink=True,
                        on_click=make_select_fn(ch_id),
                        content=ft.Row([
                            ft.Icon(
                                ft.Icons.SCHOOL_ROUNDED,
                                size=13,
                                color=ft.Colors.WHITE if is_selected else ft.Colors.ON_SURFACE_VARIANT,
                            ),
                            ft.Text(
                                ch_name,
                                size=11,
                                weight=ft.FontWeight.BOLD if is_selected else ft.FontWeight.W_500,
                                color=ft.Colors.WHITE if is_selected else ft.Colors.ON_SURFACE,
                            ),
                        ], spacing=5, tight=True),
                    )
                )

        # ── Hero Cohort Banner ────────────────────────────────────────────────
        hero_banner = ft.Container(
            padding=20,
            border_radius=18,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)),
            shadow=ft.BoxShadow(blur_radius=16, color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK)),
            content=ft.Column([
                ft.Row([
                    ft.Row([
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                            border_radius=12,
                            bgcolor=st_bg,
                            content=ft.Row([
                                ft.Container(width=6, height=6, border_radius=3, bgcolor=dot_color),
                                ft.Text(c_status, size=10, weight=ft.FontWeight.BOLD, color=st_fg),
                            ], spacing=4, tight=True),
                        ),
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                            border_radius=12,
                            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                            content=ft.Row([
                                ft.Icon(ft.Icons.BUSINESS_ROUNDED, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(c_org, size=10, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                            ], spacing=4, tight=True),
                        ),
                    ], spacing=6, tight=True),
                    ft.Row([
                        ft.Icon(ft.Icons.DATE_RANGE_ROUNDED, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(f"{s_date} – {e_date}", size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
                    ], spacing=4, tight=True),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Text(c_name, size=20, weight=ft.FontWeight.BOLD),
                ft.Text(c_desc if c_desc else "Comprehensive training track organized for cohort members.", size=12, color=ft.Colors.ON_SURFACE_VARIANT) if c_desc else ft.Container(),
                ft.Container(height=4),
                # Overall Curriculum Progress Ribbon
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                    border_radius=12,
                    bgcolor=ft.Colors.with_opacity(0.04, theme_color),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.10, theme_color)),
                    content=ft.Row([
                        ft.Column([
                            ft.Row([
                                ft.Text("Curriculum Track Completion", size=11, weight=ft.FontWeight.W_600, color=theme_color),
                                ft.Text(f"{avg_prog}%", size=12, weight=ft.FontWeight.BOLD, color=theme_color),
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.ProgressBar(value=avg_prog / 100.0, color=theme_color, bgcolor=ft.Colors.with_opacity(0.12, theme_color), height=6, border_radius=3),
                        ], spacing=4, expand=True),
                        ft.Container(width=16),
                        ft.Row([
                            ft.Column([
                                ft.Text("Courses", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(str(len(c_courses)), size=14, weight=ft.FontWeight.BOLD),
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
                            ft.Container(width=1, height=24, bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
                            ft.Column([
                                ft.Text("Assessments", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(str(len(c_exams)), size=14, weight=ft.FontWeight.BOLD),
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
                        ], spacing=10),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ),
            ], spacing=10),
        )

        # ── Segmented Sub-Tab Switcher (Curriculum vs Assessments) ────────────
        def set_subtab(tab_key: str):
            state["active_subtab"] = tab_key
            render_ui()
            page.update()

        curriculum_active = state["active_subtab"] == "curriculum"
        assessments_active = state["active_subtab"] == "assessments"

        subtab_switcher = ft.Container(
            padding=3,
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
            content=ft.Row([
                ft.Container(
                    expand=True,
                    padding=ft.Padding.symmetric(vertical=8),
                    border_radius=10,
                    bgcolor=ft.Colors.SURFACE if curriculum_active else ft.Colors.TRANSPARENT,
                    shadow=ft.BoxShadow(blur_radius=4, color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK)) if curriculum_active else None,
                    alignment=ft.Alignment.CENTER,
                    ink=True,
                    on_click=lambda _: set_subtab("curriculum"),
                    content=ft.Row([
                        ft.Icon(
                            ft.Icons.AUTO_STORIES_ROUNDED,
                            size=15,
                            color=theme_color if curriculum_active else ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Text(
                            f"Curriculum Track ({len(c_courses)})",
                            size=12,
                            weight=ft.FontWeight.BOLD if curriculum_active else ft.FontWeight.W_500,
                            color=ft.Colors.ON_SURFACE if curriculum_active else ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ], tight=True, spacing=6),
                ),
                ft.Container(
                    expand=True,
                    padding=ft.Padding.symmetric(vertical=8),
                    border_radius=10,
                    bgcolor=ft.Colors.SURFACE if assessments_active else ft.Colors.TRANSPARENT,
                    shadow=ft.BoxShadow(blur_radius=4, color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK)) if assessments_active else None,
                    alignment=ft.Alignment.CENTER,
                    ink=True,
                    on_click=lambda _: set_subtab("assessments"),
                    content=ft.Row([
                        ft.Icon(
                            ft.Icons.TIMER_ROUNDED,
                            size=15,
                            color=theme_color if assessments_active else ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Text(
                            f"Assessments & Certifications ({len(c_exams)})",
                            size=12,
                            weight=ft.FontWeight.BOLD if assessments_active else ft.FontWeight.W_500,
                            color=ft.Colors.ON_SURFACE if assessments_active else ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ], tight=True, spacing=6),
                ),
            ], spacing=4),
        )

        # ── TAB 1: CURRICULUM COURSES ─────────────────────────────────────────
        course_cards = []
        for crs in c_courses:
            crs_id = str(crs.get("id"))
            crs_name = crs.get("name", "Untitled Course")
            crs_prog = crs.get("progress", 0)
            crs_lessons = crs.get("total_lessons", 0)

            card = ft.Container(
                padding=14,
                border_radius=14,
                bgcolor=ft.Colors.SURFACE,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)),
                ink=True,
                on_click=lambda _, cid=crs_id: page.go(f"/courses/{cid}"),
                content=ft.Row([
                    ft.Container(
                        width=42, height=42, border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.10, theme_color),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(ft.Icons.AUTO_STORIES_ROUNDED, size=22, color=theme_color),
                    ),
                    ft.Column([
                        ft.Text(crs_name, size=13, weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Row([
                            ft.Text(f"{crs_lessons} Lessons", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text("·", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(f"{crs_prog}% Completed", size=11, weight=ft.FontWeight.W_600, color=theme_color),
                        ], spacing=4),
                        ft.ProgressBar(
                            value=crs_prog / 100.0,
                            color=theme_color,
                            bgcolor=ft.Colors.with_opacity(0.10, theme_color),
                            height=4,
                            border_radius=2,
                        ),
                    ], spacing=4, expand=True),
                    ft.FilledButton(
                        "Resume" if crs_prog > 0 else "Study",
                        icon=ft.Icons.PLAY_ARROW_ROUNDED,
                        style=ft.ButtonStyle(bgcolor=theme_color, padding=ft.Padding.symmetric(horizontal=12, vertical=6)),
                        on_click=lambda _, cid=crs_id: page.go(f"/courses/{cid}"),
                    ),
                ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            )
            course_cards.append(card)

        curriculum_content = ft.Column(
            course_cards if course_cards else [
                ft.Container(
                    alignment=ft.Alignment.CENTER,
                    padding=40,
                    content=ft.Column([
                        ft.Icon(ft.Icons.AUTO_STORIES_OUTLINED, size=40, color=ft.Colors.GREY_400),
                        ft.Text("No Courses Assigned Yet", size=14, weight=ft.FontWeight.BOLD),
                        ft.Text("Your instructors have not mapped any courses to this cohort curriculum yet.", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                )
            ],
            spacing=10,
        )

        # ── TAB 2: ASSESSMENTS DECK ───────────────────────────────────────────
        exam_cards = []
        for ex in c_exams:
            ex_id = str(ex.get("id"))
            ex_title = ex.get("title", "Exam")
            ex_dur = ex.get("duration_minutes", 60)
            ex_pass = ex.get("pass_percentage", 70.0)
            ex_q_count = ex.get("question_count", 0)
            ex_max_attempts = ex.get("max_attempts", 1)
            ex_status = _get_effective_exam_status(ex)
            o_time = _format_datetime(ex.get("opens_at"))
            c_time = _format_datetime(ex.get("closes_at"))
            user_sub = ex.get("user_submission")

            # Status pill
            if ex_status == "OPEN_NOW":
                ex_badge = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=6, bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.GREEN_600),
                    content=ft.Row([
                        ft.Container(width=6, height=6, border_radius=3, bgcolor=ft.Colors.GREEN_600),
                        ft.Text("OPEN NOW", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_700),
                    ], spacing=4, tight=True),
                )
            elif ex_status == "CLOSED":
                ex_badge = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=6, bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.GREY_600),
                    content=ft.Text("CLOSED", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_700),
                )
            else:
                ex_badge = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=6, bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.BLUE_600),
                    content=ft.Text("SCHEDULED", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_700),
                )

            # Submission and CTA handling
            if user_sub and user_sub.get("status") in ("submitted", "graded"):
                passed = user_sub.get("passed", False)
                score = user_sub.get("percentage", 0.0)
                sub_pill = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.GREEN_600 if passed else ft.Colors.RED_600),
                    content=ft.Row([
                        ft.Icon(
                            ft.Icons.CHECK_CIRCLE_ROUNDED if passed else ft.Icons.CANCEL_ROUNDED,
                            size=14,
                            color=ft.Colors.GREEN_700 if passed else ft.Colors.RED_700,
                        ),
                        ft.Text(
                            f"Completed · {score}% ({'PASSED' if passed else 'FAILED'})",
                            size=11, weight=ft.FontWeight.BOLD,
                            color=ft.Colors.GREEN_700 if passed else ft.Colors.RED_700,
                        ),
                    ], spacing=5, tight=True),
                )
                action_btn = sub_pill
            elif ex_status == "OPEN_NOW":
                action_btn = ft.FilledButton(
                    "Take Assessment",
                    icon=ft.Icons.PLAY_ARROW_ROUNDED,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, padding=ft.Padding.symmetric(horizontal=14, vertical=8)),
                    on_click=launch_candidate_exam(c_org_id, c_id, ex_id),
                )
            elif ex_status == "SCHEDULED":
                action_btn = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.BLUE_600),
                    content=ft.Row([
                        ft.Icon(ft.Icons.LOCK_CLOCK_ROUNDED, size=13, color=ft.Colors.BLUE_700),
                        ft.Text(f"Opens: {o_time}", size=11, color=ft.Colors.BLUE_700, weight=ft.FontWeight.W_500),
                    ], spacing=5, tight=True),
                )
            else:
                action_btn = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.GREY_600),
                    content=ft.Text("Exam Window Closed", size=11, color=ft.Colors.GREY_700, italic=True),
                )

            card = ft.Container(
                padding=16,
                border_radius=14,
                bgcolor=ft.Colors.SURFACE,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)),
                content=ft.Column([
                    ft.Row([
                        ex_badge,
                        ft.Row([
                            ft.Icon(ft.Icons.TIMER_OUTLINED, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(f"{ex_dur} Mins · {ex_q_count} Questions", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ], spacing=4, tight=True),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Text(ex_title, size=15, weight=ft.FontWeight.BOLD),
                    ft.Row([
                        ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(f"Active Window: {o_time} to {c_time}", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], spacing=4, tight=True),
                    ft.Row([
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                            border_radius=6, bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                            content=ft.Text(f"Pass Mark: {ex_pass}%", size=10, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE_VARIANT),
                        ),
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                            border_radius=6, bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                            content=ft.Text(f"Max Attempts: {ex_max_attempts}", size=10, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE_VARIANT),
                        ),
                    ], spacing=6),
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    ft.Row([
                        action_btn,
                    ], alignment=ft.MainAxisAlignment.END),
                ], spacing=10),
            )
            exam_cards.append(card)

        assessments_content = ft.Column(
            exam_cards if exam_cards else [
                ft.Container(
                    alignment=ft.Alignment.CENTER,
                    padding=40,
                    content=ft.Column([
                        ft.Icon(ft.Icons.TIMER_OFF_OUTLINED, size=40, color=ft.Colors.GREY_400),
                        ft.Text("No Scheduled Assessments", size=14, weight=ft.FontWeight.BOLD),
                        ft.Text("There are no exams currently scheduled for this training cohort.", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                )
            ],
            spacing=10,
        )

        active_tab_body = curriculum_content if curriculum_active else assessments_content

        # ── Assemble Overall Layout ───────────────────────────────────────────
        top_appbar = ft.Row([
            ft.IconButton(
                icon=ft.Icons.ARROW_BACK_ROUNDED,
                tooltip="Back to Dashboard",
                on_click=lambda _: on_back() if on_back else page.go("/dashboard"),
            ),
            ft.Column([
                ft.Text("Training Cohort Hub", size=16, weight=ft.FontWeight.BOLD),
                ft.Text("Curriculum, progress tracking & assessments", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
            ], spacing=1, expand=True),
            ft.IconButton(
                icon=ft.Icons.REFRESH_ROUNDED,
                tooltip="Refresh Data",
                on_click=lambda _: page.run_task(load_data),
            ),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

        root_container.content = ft.Column([
            top_appbar,
            ft.Row(cohort_switcher_chips, spacing=6, scroll=ft.ScrollMode.AUTO) if cohort_switcher_chips else ft.Container(),
            hero_banner,
            subtab_switcher,
            active_tab_body,
        ], spacing=14, scroll=ft.ScrollMode.AUTO)

    page.run_task(load_data)
    return root_container


def open_learner_cohorts_modal(page: ft.Page, token: str, initial_cohort_id: str = None):
    """Convenience helper to display the Learner Cohort Hub inside an overlay modal dialog."""
    hub = build_learner_cohorts_view(
        page=page,
        token=token,
        on_back=lambda: page.pop_dialog() if hasattr(page, "pop_dialog") else None,
        initial_cohort_id=initial_cohort_id,
    )
    pw = getattr(page, "width", None)
    w_val = pw if isinstance(pw, (int, float)) and pw > 0 else 1000
    ph = getattr(page, "height", None)
    h_val = ph if isinstance(ph, (int, float)) and ph > 0 else 800

    dlg = ft.AlertDialog(
        modal=True,
        content=ft.Container(
            width=min(w_val - 24, 760),
            height=min(h_val - 60, 680),
            content=hub,
        ),
        actions=[],
    )
    if hasattr(page, "show_dialog"):
        page.show_dialog(dlg)
    else:
        page.dialog = dlg
        dlg.open = True
        page.update()
