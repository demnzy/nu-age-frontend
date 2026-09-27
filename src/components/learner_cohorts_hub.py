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
        return lambda _: page.go(f"/cohorts/{cohort_id}/exams/{exam_id}?org_id={org_id}")


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

        # ── Branded Cohort Hero Showcase ──────────────────────────────────────
        header_tags = [
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                border_radius=6,
                bgcolor=ft.Colors.with_opacity(0.22, ft.Colors.BLACK),
                content=ft.Row([
                    ft.Container(width=6, height=6, border_radius=3, bgcolor=ft.Colors.WHITE),
                    ft.Text(c_status, size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ], spacing=4, tight=True),
            )
        ]
        if c_org:
            header_tags.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=6,
                    bgcolor=ft.Colors.with_opacity(0.22, ft.Colors.BLACK),
                    content=ft.Row([
                        ft.Icon(ft.Icons.BUSINESS_ROUNDED, size=11, color=ft.Colors.WHITE),
                        ft.Text(c_org, size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    ], spacing=4, tight=True),
                )
            )

        hero_banner = ft.Container(
            padding=18,
            border_radius=16,
            gradient=ft.LinearGradient(
                colors=[theme_color, ft.Colors.SECONDARY],
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
            ),
            shadow=ft.BoxShadow(
                blur_radius=14,
                color=ft.Colors.with_opacity(0.18, theme_color),
                offset=ft.Offset(0, 5),
            ),
            content=ft.Column([
                ft.Row([
                    ft.Row(header_tags, spacing=6, tight=True),
                    ft.Row([
                        ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, size=12, color=ft.Colors.WHITE),
                        ft.Text(f"{s_date} – {e_date}", size=11, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                    ], spacing=4, tight=True) if (s_date or e_date) else ft.Container(),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Text(c_name, size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ft.Text(c_desc, size=12, color=ft.Colors.with_opacity(0.92, ft.Colors.WHITE)) if c_desc else ft.Container(),
                ft.Container(height=4),
                # Overall Curriculum Progress Ribbon
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                    border_radius=12,
                    bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.BLACK),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.18, ft.Colors.WHITE)),
                    content=ft.Row([
                        ft.Column([
                            ft.Row([
                                ft.Text("Curriculum Track Completion", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                ft.Text(f"{avg_prog}%", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.ProgressBar(value=avg_prog / 100.0, color=ft.Colors.WHITE, bgcolor=ft.Colors.with_opacity(0.28, ft.Colors.WHITE), height=6, border_radius=3),
                        ], spacing=4, expand=True),
                        ft.Container(width=16),
                        ft.Row([
                            ft.Column([
                                ft.Text("Courses", size=10, color=ft.Colors.with_opacity(0.85, ft.Colors.WHITE)),
                                ft.Text(str(len(c_courses)), size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
                            ft.Container(width=1, height=24, bgcolor=ft.Colors.with_opacity(0.25, ft.Colors.WHITE)),
                            ft.Column([
                                ft.Text("Assessments", size=10, color=ft.Colors.with_opacity(0.85, ft.Colors.WHITE)),
                                ft.Text(str(len(c_exams)), size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
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
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
            content=ft.Row([
                ft.Container(
                    expand=True,
                    padding=ft.Padding.symmetric(vertical=8),
                    border_radius=8,
                    bgcolor=theme_color if curriculum_active else ft.Colors.TRANSPARENT,
                    shadow=ft.BoxShadow(blur_radius=4, color=ft.Colors.with_opacity(0.2, theme_color), offset=ft.Offset(0, 1)) if curriculum_active else None,
                    alignment=ft.Alignment.CENTER,
                    ink=True,
                    on_click=lambda _: set_subtab("curriculum"),
                    content=ft.Row([
                        ft.Icon(
                            ft.Icons.AUTO_STORIES_ROUNDED,
                            size=15,
                            color=ft.Colors.WHITE if curriculum_active else ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Text(
                            f"Curriculum Track ({len(c_courses)})",
                            size=12,
                            weight=ft.FontWeight.BOLD if curriculum_active else ft.FontWeight.W_500,
                            color=ft.Colors.WHITE if curriculum_active else ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ], tight=True, spacing=6),
                ),
                ft.Container(
                    expand=True,
                    padding=ft.Padding.symmetric(vertical=8),
                    border_radius=8,
                    bgcolor=theme_color if assessments_active else ft.Colors.TRANSPARENT,
                    shadow=ft.BoxShadow(blur_radius=4, color=ft.Colors.with_opacity(0.2, theme_color), offset=ft.Offset(0, 1)) if assessments_active else None,
                    alignment=ft.Alignment.CENTER,
                    ink=True,
                    on_click=lambda _: set_subtab("assessments"),
                    content=ft.Row([
                        ft.Icon(
                            ft.Icons.TIMER_ROUNDED,
                            size=15,
                            color=ft.Colors.WHITE if assessments_active else ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Text(
                            f"Assessments & Exams ({len(c_exams)})",
                            size=12,
                            weight=ft.FontWeight.BOLD if assessments_active else ft.FontWeight.W_500,
                            color=ft.Colors.WHITE if assessments_active else ft.Colors.ON_SURFACE_VARIANT,
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
            crs_img = crs.get("image_url")
            crs_desc = crs.get("description")

            thumb = ft.Image(
                src=crs_img,
                width=44,
                height=44,
                fit=ft.BoxFit.COVER,
                border_radius=ft.BorderRadius.all(10),
                error_content=ft.Container(
                    width=44, height=44, border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.12, theme_color),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.AUTO_STORIES_ROUNDED, size=22, color=theme_color),
                ),
            ) if crs_img else ft.Container(
                width=44, height=44, border_radius=10,
                bgcolor=ft.Colors.with_opacity(0.10, theme_color),
                alignment=ft.Alignment.CENTER,
                content=ft.Icon(ft.Icons.AUTO_STORIES_ROUNDED, size=22, color=theme_color),
            )

            desc_control = ft.Text(crs_desc, size=11, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS) if crs_desc else ft.Container()

            card = ft.Container(
                padding=14,
                border_radius=12,
                bgcolor=ft.Colors.SURFACE,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                shadow=ft.BoxShadow(blur_radius=6, color=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE), offset=ft.Offset(0, 2)),
                ink=True,
                on_click=lambda _, cid=crs_id: page.go(f"/courses/{cid}"),
                content=ft.Row([
                    thumb,
                    ft.Column([
                        ft.Text(crs_name, size=13, weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        desc_control,
                        ft.Row([
                            ft.Text(f"{crs_prog}% Completed", size=11, weight=ft.FontWeight.W_600, color=theme_color),
                        ], spacing=4),
                        ft.ProgressBar(
                            value=crs_prog / 100.0,
                            color=theme_color,
                            bgcolor=ft.Colors.with_opacity(0.12, theme_color),
                            height=4,
                            border_radius=2,
                        ),
                    ], spacing=3, expand=True),
                    ft.FilledButton(
                        "Resume" if crs_prog > 0 else "Study",
                        icon=ft.Icons.PLAY_ARROW_ROUNDED,
                        style=ft.ButtonStyle(bgcolor=theme_color, color=ft.Colors.ON_PRIMARY, shape=ft.RoundedRectangleBorder(radius=8), padding=ft.Padding.symmetric(horizontal=12, vertical=6)),
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
            completed_attempts = ex.get("completed_attempts")
            user_sub = ex.get("user_submission") or ex.get("submission")
            if completed_attempts is None:
                completed_attempts = 1 if user_sub and user_sub.get("status") in ("submitted", "graded", "flagged_violation", "timed_out") else 0
            attempts_left = ex.get("attempts_left")
            if attempts_left is None:
                attempts_left = max(0, ex_max_attempts - completed_attempts)
            can_retry = (completed_attempts < ex_max_attempts) and (attempts_left > 0)
            ex_status = _get_effective_exam_status(ex)
            o_time = _format_datetime(ex.get("opens_at"))
            c_time = _format_datetime(ex.get("closes_at"))
            is_active_attempt = bool(ex.get("is_in_progress") or (user_sub and user_sub.get("status") == "in_progress") or ex.get("in_progress_submission"))

            # Status pill
            if is_active_attempt:
                ex_badge = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=6, bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.AMBER_700),
                    content=ft.Row([
                        ft.Icon(ft.Icons.TIMER_ROUNDED, size=12, color=ft.Colors.AMBER_800),
                        ft.Text("IN PROGRESS · RESUME", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_900),
                    ], spacing=4, tight=True),
                )
            elif completed_attempts == 0:
                if ex_status == "OPEN_NOW":
                    ex_badge = ft.Container(
                        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                        border_radius=6, bgcolor=ft.Colors.with_opacity(0.12, theme_color),
                        content=ft.Row([
                            ft.Container(width=6, height=6, border_radius=3, bgcolor=theme_color),
                            ft.Text("NOT STARTED · OPEN", size=10, weight=ft.FontWeight.BOLD, color=theme_color),
                        ], spacing=4, tight=True),
                    )
                elif ex_status == "SCHEDULED":
                    ex_badge = ft.Container(
                        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                        border_radius=6, bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                        content=ft.Row([
                            ft.Icon(ft.Icons.LOCK_CLOCK_ROUNDED, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text("NOT STARTED · SCHEDULED", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                        ], spacing=4, tight=True),
                    )
                else:
                    ex_badge = ft.Container(
                        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                        border_radius=6, bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                        content=ft.Text("NOT STARTED · CLOSED", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                    )
            elif completed_attempts > 0 and can_retry and ex_status == "OPEN_NOW":
                ex_badge = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=6, bgcolor=ft.Colors.with_opacity(0.12, theme_color),
                    content=ft.Row([
                        ft.Icon(ft.Icons.REFRESH_ROUNDED, size=11, color=theme_color),
                        ft.Text(f"ATTEMPT {completed_attempts + 1} AVAILABLE", size=10, weight=ft.FontWeight.BOLD, color=theme_color),
                    ], spacing=4, tight=True),
                )
            elif completed_attempts >= ex_max_attempts:
                ex_badge = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=6, bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                    content=ft.Text("COMPLETED", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                )
            elif ex_status == "CLOSED":
                ex_badge = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=6, bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                    content=ft.Text("CLOSED", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                )
            else:
                ex_badge = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=6, bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                    content=ft.Text("SCHEDULED", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                )

            # Submission and CTA handling
            if is_active_attempt:
                action_btn = ft.FilledButton(
                    "Resume Assessment",
                    icon=ft.Icons.PLAY_ARROW_ROUNDED,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.AMBER_700, color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=8), padding=ft.Padding.symmetric(horizontal=14, vertical=8)),
                    on_click=launch_candidate_exam(c_org_id, c_id, ex_id),
                )
            elif user_sub and user_sub.get("status") in ("submitted", "graded", "flagged_violation", "timed_out"):
                passed = user_sub.get("passed", False)
                score = user_sub.get("percentage", 0.0)
                sub_pill = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.12, theme_color if passed else ft.Colors.RED_600),
                    content=ft.Row([
                        ft.Icon(
                            ft.Icons.CHECK_CIRCLE_ROUNDED if passed else ft.Icons.CANCEL_ROUNDED,
                            size=14,
                            color=theme_color if passed else ft.Colors.RED_700,
                        ),
                        ft.Text(
                            f"Score: {score}% ({'PASSED' if passed else 'FAILED'})",
                            size=11, weight=ft.FontWeight.BOLD,
                            color=theme_color if passed else ft.Colors.RED_700,
                        ),
                    ], spacing=5, tight=True),
                )
                if can_retry and ex_status == "OPEN_NOW":
                    action_btn = ft.Row([
                        sub_pill,
                        ft.FilledButton(
                            f"Retake ({completed_attempts + 1}/{ex_max_attempts})",
                            icon=ft.Icons.REFRESH_ROUNDED,
                            style=ft.ButtonStyle(bgcolor=theme_color, color=ft.Colors.ON_PRIMARY, shape=ft.RoundedRectangleBorder(radius=8), padding=ft.Padding.symmetric(horizontal=12, vertical=8)),
                            on_click=launch_candidate_exam(c_org_id, c_id, ex_id),
                        ),
                    ], spacing=8, tight=True)
                elif completed_attempts >= ex_max_attempts:
                    action_btn = ft.Row([
                        sub_pill,
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                            border_radius=6,
                            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                            content=ft.Text(f"All {ex_max_attempts} attempts used", size=10, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
                        ),
                    ], spacing=6, tight=True)
                else:
                    action_btn = sub_pill
            elif ex_status == "OPEN_NOW":
                action_btn = ft.FilledButton(
                    "Start Assessment",
                    icon=ft.Icons.PLAY_ARROW_ROUNDED,
                    style=ft.ButtonStyle(bgcolor=theme_color, color=ft.Colors.ON_PRIMARY, shape=ft.RoundedRectangleBorder(radius=8), padding=ft.Padding.symmetric(horizontal=14, vertical=8)),
                    on_click=launch_candidate_exam(c_org_id, c_id, ex_id),
                )
            elif ex_status == "SCHEDULED":
                action_btn = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.06, theme_color),
                    content=ft.Row([
                        ft.Icon(ft.Icons.LOCK_CLOCK_ROUNDED, size=13, color=theme_color),
                        ft.Text(f"Opens: {o_time}", size=11, color=theme_color, weight=ft.FontWeight.W_500),
                    ], spacing=5, tight=True),
                )
            else:
                action_btn = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                    content=ft.Text("Exam Window Closed", size=11, color=ft.Colors.ON_SURFACE_VARIANT, italic=True),
                )

            # Metadata capsules
            meta_chips = [
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                    border_radius=6, bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                    content=ft.Text(f"Pass Mark: {ex_pass}%", size=10, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE_VARIANT),
                ),
            ]
            if ex_max_attempts > 1:
                meta_chips.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                        border_radius=6, bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                        content=ft.Text(f"Attempts: {completed_attempts}/{ex_max_attempts} Used", size=10, weight=ft.FontWeight.W_600, color=theme_color if can_retry else ft.Colors.ON_SURFACE_VARIANT),
                    )
                )

            q_label = f" · {ex_q_count} Questions" if ex_q_count > 0 else ""

            card = ft.Container(
                padding=16,
                border_radius=12,
                bgcolor=ft.Colors.SURFACE,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                shadow=ft.BoxShadow(blur_radius=6, color=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE), offset=ft.Offset(0, 2)),
                content=ft.Column([
                    ft.Row([
                        ex_badge,
                        ft.Row([
                            ft.Icon(ft.Icons.TIMER_OUTLINED, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(f"{ex_dur} Mins{q_label}", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ], spacing=4, tight=True),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Text(ex_title, size=15, weight=ft.FontWeight.BOLD),
                    ft.Row([
                        ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(f"Active Window: {o_time} to {c_time}", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], spacing=4, tight=True),
                    ft.Row(meta_chips, spacing=6),
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
        top_appbar = ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            content=ft.Row([
                ft.Row([
                    ft.IconButton(
                        icon=ft.Icons.ARROW_BACK_ROUNDED,
                        icon_size=20,
                        tooltip="Back to Dashboard",
                        on_click=lambda _: on_back() if on_back else page.go("/dashboard"),
                    ),
                    ft.Column([
                        ft.Row([
                            ft.Text("Cohorts", size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
                            ft.Text("·", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(c_org if c_org else "Training Hub", size=11, color=theme_color, weight=ft.FontWeight.BOLD),
                        ], spacing=4, tight=True),
                        ft.Text(c_name, size=18, weight=ft.FontWeight.BOLD),
                    ], spacing=1, tight=True),
                ], spacing=6, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.IconButton(
                    icon=ft.Icons.REFRESH_ROUNDED,
                    icon_size=18,
                    tooltip="Refresh Data",
                    on_click=lambda _: page.run_task(load_data),
                ),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        pw = getattr(page, "width", None)
        content_max_w = min(pw - 32, 1000) if pw and pw > 720 else None
        h_pad = 12 if is_mobile() else 20

        inner_layout = ft.Container(
            content=ft.Column([
                top_appbar,
                ft.Row(cohort_switcher_chips, spacing=6, scroll=ft.ScrollMode.AUTO) if cohort_switcher_chips else ft.Container(),
                hero_banner,
                subtab_switcher,
                active_tab_body,
                ft.Container(height=20),
            ], spacing=14, scroll=ft.ScrollMode.AUTO),
            width=content_max_w,
            alignment=ft.Alignment.TOP_CENTER,
            padding=ft.Padding.symmetric(horizontal=h_pad, vertical=16),
            expand=True,
        )

        root_container.content = ft.Container(
            content=inner_layout,
            alignment=ft.Alignment.TOP_CENTER,
            expand=True,
        )

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
        content_padding=ft.Padding.all(12),
        content=ft.Container(
            width=min(w_val - 24, 860),
            height=min(h_val - 60, 720),
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
