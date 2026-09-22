"""
Modern Dedicated Cohort View for Nu-Age LMS.
Provides a comprehensive full-page learning hub for cohort-enrolled candidates:
  * Dynamic hero ribbon with progress gauge, schedule timeline, and institution badge.
  * Multi-cohort switcher ribbon for learners enrolled across multiple training programs.
  * Segmented dual-track view: Sequential Curriculum Track and Assessments & Certifications Deck.
  * Direct launch of secure examination runner with proctoring enforcement.
  * Cohort academic integrity rules and proctoring policy briefings.
"""

import asyncio
from datetime import datetime, timezone
import urllib.parse
from typing import Optional, Dict, Any, List
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


async def cohort_page_view(
    page: ft.Page,
    cohort_id: Optional[str] = None,
    back_target: str = "/dashboard",
) -> ft.View:
    """Renders the dedicated full-page Cohort View for the learner."""
    theme_color = ft.Colors.PRIMARY

    # Resolve token safely
    token: Optional[str] = None
    try:
        token = await page.shared_preferences.get("auth_token")
    except Exception:
        token = None

    state: Dict[str, Any] = {
        "cohorts": [],
        "active_urgent_exams": [],
        "selected_cohort_id": str(cohort_id) if cohort_id else None,
        "active_subtab": "curriculum",  # "curriculum", "assessments", "policies"
        "loading": True,
        "exam_running": False,
    }

    content_socket = ft.Container(expand=True)

    def is_mobile() -> bool:
        pw = getattr(page, "width", None)
        w = pw if isinstance(pw, (int, float)) and pw > 0 else 1000
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

    async def open_whatsapp_share(cohort_name: str, org_name: str):
        message = (
            f"🎓 Learning in the '{cohort_name}' cohort by {org_name} on Nu-Age! 🚀\n"
            f"Explore interactive courses, assignments, and certified assessments.\n"
            f"Learn more at: https://nu-age.name.ng"
        )
        encoded_message = urllib.parse.quote(message)
        try:
            await page.launch_url(f"https://wa.me/?text={encoded_message}")
        except Exception:
            try:
                if hasattr(page, "set_clipboard"):
                    await page.set_clipboard(f"https://nu-age.name.ng/cohorts/{state['selected_cohort_id']}")
                show_snack("Cohort link copied to clipboard!")
            except Exception:
                pass

    # ── Candidate Take Exam Launcher ──────────────────────────────────────────
    def launch_candidate_exam(org_id: str, c_id: str, exam_id: str):
        async def _do(_):
            content_socket.content = ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=60,
                content=ft.Column([
                    ft.ProgressRing(color=theme_color, width=40, height=40),
                    ft.Text("Preparing your secure assessment environment...", size=14, weight=ft.FontWeight.W_500),
                    ft.Text("Verifying eligibility and setting up proctoring monitors.", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True, spacing=14),
            )
            page.update()

            exam_payload = await start_cohort_exam(token, str(org_id), str(c_id), str(exam_id))
            if "error" in exam_payload:
                err_msg = exam_payload["error"]
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
                        shadow=ft.BoxShadow(blur_radius=24, color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK)),
                        content=ft.Column([
                            ft.Container(
                                width=56, height=56, border_radius=28,
                                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_700),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.LOCK_CLOCK_ROUNDED, size=28, color=ft.Colors.AMBER_700),
                            ),
                            ft.Text("Assessment Unavailable", size=18, weight=ft.FontWeight.BOLD),
                            ft.Text(err_msg, size=13, color=ft.Colors.ON_SURFACE, text_align=ft.TextAlign.CENTER),
                            ft.Text(
                                "If you need an additional attempt or have questions about your assessment window, please reach out to your instructor or cohort administrator.",
                                size=11, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Container(height=10),
                            ft.FilledButton(
                                "Return to Cohort",
                                icon=ft.Icons.ARROW_BACK_ROUNDED,
                                on_click=lambda _: render_view() or page.update(),
                                style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=22, vertical=12)),
                            ),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
                    ),
                )
                page.update()
                return

            def on_exit_exam(*_):
                state["exam_running"] = False
                page.run_task(load_cohort_data)

            exam_view = build_cohort_exam_view(
                page=page,
                exam_payload=exam_payload,
                org_id=str(org_id),
                cohort_id=str(c_id),
                exam_id=str(exam_id),
                token=token,
                on_exit=on_exit_exam,
            )
            content_socket.content = exam_view
            page.update()

        return _do

    # ── Load Cohort Data ──────────────────────────────────────────────────────
    async def load_cohort_data():
        state["loading"] = True
        render_view()
        page.update()

        res = await get_learner_cohorts(token)
        cohorts = res.get("cohorts", [])
        state["cohorts"] = cohorts
        state["active_urgent_exams"] = res.get("active_urgent_exams", [])
        state["loading"] = False

        if cohorts:
            matched = False
            if state["selected_cohort_id"]:
                for c in cohorts:
                    if str(c.get("id")) == str(state["selected_cohort_id"]):
                        matched = True
                        break
            if not matched:
                state["selected_cohort_id"] = str(cohorts[0].get("id"))

        render_view()
        page.update()

    # ── Render Full Cohort Page ───────────────────────────────────────────────
    def render_view():
        if state["loading"]:
            content_socket.content = ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=60,
                content=ft.Column([
                    ft.ProgressRing(color=theme_color, width=38, height=38),
                    ft.Text("Loading Training Cohort...", size=14, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True, spacing=14),
            )
            return

        cohorts = state["cohorts"]
        if not cohorts:
            # Empty state
            content_socket.content = ft.Container(
                expand=True,
                alignment=ft.Alignment.CENTER,
                padding=32,
                content=ft.Column([
                    ft.Container(
                        width=80, height=80, border_radius=40,
                        bgcolor=ft.Colors.with_opacity(0.08, theme_color),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(ft.Icons.GROUPS_ROUNDED, size=40, color=theme_color),
                    ),
                    ft.Text("No Enrolled Cohorts Found", size=18, weight=ft.FontWeight.BOLD),
                    ft.Container(
                        width=420,
                        content=ft.Text(
                            "You are currently not enrolled in any organization training cohorts. When your institution or company assigns you to a curriculum track, it will automatically appear here.",
                            size=12, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER,
                        ),
                    ),
                    ft.Container(height=8),
                    ft.FilledButton(
                        "Return to Dashboard",
                        icon=ft.Icons.ARROW_BACK_ROUNDED,
                        on_click=lambda _: page.go(back_target),
                        style=ft.ButtonStyle(bgcolor=theme_color, padding=ft.Padding.symmetric(horizontal=20, vertical=12)),
                    ),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
            )
            return

        # Find selected cohort
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

        # Progress calculation
        avg_prog = 0
        if c_courses:
            avg_prog = round(sum(crs.get("progress", 0) for crs in c_courses) / len(c_courses))

        # Status styling
        if c_status == "ACTIVE":
            st_bg, st_fg = ft.Colors.with_opacity(0.12, ft.Colors.GREEN_600), ft.Colors.GREEN_700
            dot_color = ft.Colors.GREEN_600
        elif c_status == "COMPLETED":
            st_bg, st_fg = ft.Colors.with_opacity(0.10, ft.Colors.GREY_600), ft.Colors.GREY_700
            dot_color = ft.Colors.GREY_600
        else:
            st_bg, st_fg = ft.Colors.with_opacity(0.12, ft.Colors.BLUE_600), ft.Colors.BLUE_700
            dot_color = ft.Colors.BLUE_600

        # Cohort Switcher Ribbon (when enrolled in multiple cohorts)
        cohort_switcher_chips = []
        if len(cohorts) > 1:
            for ch in cohorts:
                ch_id = str(ch.get("id"))
                is_sel = ch_id == c_id
                ch_name = ch.get("name", "Cohort")

                def make_switch_fn(target_id):
                    def _sw(_):
                        state["selected_cohort_id"] = target_id
                        render_view()
                        page.update()
                    return _sw

                cohort_switcher_chips.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=14, vertical=7),
                        border_radius=20,
                        bgcolor=theme_color if is_sel else ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
                        border=ft.Border.all(1, theme_color if is_sel else ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)),
                        shadow=ft.BoxShadow(blur_radius=6, color=ft.Colors.with_opacity(0.2, theme_color)) if is_sel else None,
                        ink=True,
                        on_click=make_switch_fn(ch_id),
                        content=ft.Row([
                            ft.Icon(ft.Icons.SCHOOL_ROUNDED, size=13, color=ft.Colors.WHITE if is_sel else ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(
                                ch_name,
                                size=11,
                                weight=ft.FontWeight.BOLD if is_sel else ft.FontWeight.W_500,
                                color=ft.Colors.WHITE if is_sel else ft.Colors.ON_SURFACE,
                            ),
                        ], spacing=5, tight=True),
                    )
                )

        # ── Hero Cohort Card ──────────────────────────────────────────────────
        passed_exams_count = sum(
            1 for ex in c_exams
            if ex.get("user_submission") and ex["user_submission"].get("passed")
        )

        hero_cohort_card = ft.Container(
            padding=22,
            border_radius=18,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
            shadow=ft.BoxShadow(blur_radius=16, color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK), offset=ft.Offset(0, 3)),
            content=ft.Column([
                # Top metadata line
                ft.Row([
                    ft.Row([
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                            border_radius=12,
                            bgcolor=st_bg,
                            content=ft.Row([
                                ft.Container(width=6, height=6, border_radius=3, bgcolor=dot_color),
                                ft.Text(c_status, size=10, weight=ft.FontWeight.BOLD, color=st_fg),
                            ], spacing=5, tight=True),
                        ),
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                            border_radius=12,
                            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                            content=ft.Row([
                                ft.Icon(ft.Icons.BUSINESS_ROUNDED, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(c_org, size=10, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                            ], spacing=4, tight=True),
                        ),
                    ], spacing=6, tight=True),
                    ft.Row([
                        ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(f"{s_date} – {e_date}", size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
                    ], spacing=4, tight=True),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True),

                # Title & description
                ft.Text(c_name, size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                ft.Text(
                    c_desc if c_desc else "Comprehensive training track organized for cohort members.",
                    size=13, color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                ft.Container(height=4),

                # Overall Curriculum Completion Gauge Ribbon
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                    border_radius=14,
                    bgcolor=ft.Colors.with_opacity(0.05, theme_color),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.12, theme_color)),
                    content=ft.Row([
                        ft.Column([
                            ft.Row([
                                ft.Text("Curriculum Track Progress", size=12, weight=ft.FontWeight.W_600, color=theme_color),
                                ft.Text(f"{avg_prog}%", size=13, weight=ft.FontWeight.BOLD, color=theme_color),
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.ProgressBar(
                                value=avg_prog / 100.0,
                                color=theme_color,
                                bgcolor=ft.Colors.with_opacity(0.12, theme_color),
                                height=7,
                                border_radius=3,
                            ),
                        ], spacing=5, expand=True),
                        ft.Container(width=16),
                        ft.Row([
                            ft.Column([
                                ft.Text("Courses", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(str(len(c_courses)), size=15, weight=ft.FontWeight.BOLD),
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
                            ft.Container(width=1, height=26, bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                            ft.Column([
                                ft.Text("Assessments", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(str(len(c_exams)), size=15, weight=ft.FontWeight.BOLD),
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
                            ft.Container(width=1, height=26, bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                            ft.Column([
                                ft.Text("Passed", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(str(passed_exams_count), size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_700),
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
                        ], spacing=10),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ),
            ], spacing=12),
        )

        # ── Segmented Sub-Tab Switcher ────────────────────────────────────────
        def set_subtab(key: str):
            state["active_subtab"] = key
            render_view()
            page.update()

        active_tab = state["active_subtab"]

        def subtab_btn(key: str, label: str, icon_name: str, count: int = None):
            is_sel = active_tab == key
            count_label = f" ({count})" if count is not None else ""
            return ft.Container(
                expand=True,
                padding=ft.Padding.symmetric(vertical=9),
                border_radius=10,
                bgcolor=ft.Colors.SURFACE if is_sel else ft.Colors.TRANSPARENT,
                shadow=ft.BoxShadow(blur_radius=4, color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK)) if is_sel else None,
                alignment=ft.Alignment.CENTER,
                ink=True,
                on_click=lambda _, k=key: set_subtab(k),
                content=ft.Row([
                    ft.Icon(
                        icon_name,
                        size=15,
                        color=theme_color if is_sel else ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    ft.Text(
                        f"{label}{count_label}",
                        size=12,
                        weight=ft.FontWeight.BOLD if is_sel else ft.FontWeight.W_500,
                        color=ft.Colors.ON_SURFACE if is_sel else ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ], tight=True, spacing=6),
            )

        subtab_switcher = ft.Container(
            padding=4,
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
            content=ft.Row([
                subtab_btn("curriculum", "Curriculum Track", ft.Icons.AUTO_STORIES_ROUNDED, len(c_courses)),
                subtab_btn("assessments", "Assessments & Exams", ft.Icons.TIMER_ROUNDED, len(c_exams)),
                subtab_btn("policies", "Policies & Rules", ft.Icons.SECURITY_ROUNDED),
            ], spacing=4),
        )

        # ── TAB 1: CURRICULUM TRACK ───────────────────────────────────────────
        course_cards = []
        for idx, crs in enumerate(c_courses, start=1):
            crs_id = str(crs.get("id"))
            crs_name = crs.get("name", "Untitled Course")
            crs_prog = crs.get("progress", 0)
            crs_lessons = crs.get("total_lessons", 0)

            card = ft.Container(
                padding=16,
                border_radius=14,
                bgcolor=ft.Colors.SURFACE,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)),
                shadow=ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.03, ft.Colors.BLACK), offset=ft.Offset(0, 2)),
                ink=True,
                on_click=lambda _, cid=crs_id: page.go(f"/courses/{cid}"),
                content=ft.Row([
                    ft.Container(
                        width=46, height=46, border_radius=12,
                        bgcolor=ft.Colors.with_opacity(0.10, theme_color),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(ft.Icons.AUTO_STORIES_ROUNDED, size=24, color=theme_color),
                    ),
                    ft.Column([
                        ft.Row([
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                border_radius=6, bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                                content=ft.Text(f"Module {idx}", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                            ),
                            ft.Text(f"{crs_lessons} Lessons", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text("·", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(f"{crs_prog}% Completed", size=11, weight=ft.FontWeight.W_600, color=theme_color),
                        ], spacing=6, tight=True),
                        ft.Text(crs_name, size=14, weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.ProgressBar(
                            value=crs_prog / 100.0,
                            color=theme_color,
                            bgcolor=ft.Colors.with_opacity(0.10, theme_color),
                            height=5,
                            border_radius=2,
                        ),
                    ], spacing=4, expand=True),
                    ft.FilledButton(
                        "Resume Learning" if crs_prog > 0 else "Start Course",
                        icon=ft.Icons.PLAY_ARROW_ROUNDED,
                        style=ft.ButtonStyle(bgcolor=theme_color, padding=ft.Padding.symmetric(horizontal=14, vertical=8)),
                        on_click=lambda _, cid=crs_id: page.go(f"/courses/{cid}"),
                    ),
                ], spacing=14, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            )
            course_cards.append(card)

        curriculum_content = ft.Column(
            course_cards if course_cards else [
                ft.Container(
                    alignment=ft.Alignment.CENTER,
                    padding=50,
                    content=ft.Column([
                        ft.Icon(ft.Icons.AUTO_STORIES_OUTLINED, size=44, color=ft.Colors.GREY_400),
                        ft.Text("No Courses Assigned Yet", size=15, weight=ft.FontWeight.BOLD),
                        ft.Text("Your cohort administrators have not mapped any courses to this curriculum yet.", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
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

            # CTA / Submission result
            if user_sub and user_sub.get("status") in ("submitted", "graded"):
                passed = user_sub.get("passed", False)
                score = user_sub.get("percentage", 0.0)
                action_btn = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=6),
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
                    ], spacing=6, tight=True),
                )
            elif ex_status == "OPEN_NOW":
                action_btn = ft.FilledButton(
                    "Take Assessment",
                    icon=ft.Icons.PLAY_ARROW_ROUNDED,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, padding=ft.Padding.symmetric(horizontal=16, vertical=9)),
                    on_click=launch_candidate_exam(c_org_id, c_id, ex_id),
                )
            elif ex_status == "SCHEDULED":
                action_btn = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.BLUE_600),
                    content=ft.Row([
                        ft.Icon(ft.Icons.LOCK_CLOCK_ROUNDED, size=13, color=ft.Colors.BLUE_700),
                        ft.Text(f"Opens: {o_time}", size=11, color=ft.Colors.BLUE_700, weight=ft.FontWeight.W_500),
                    ], spacing=5, tight=True),
                )
            else:
                action_btn = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.GREY_600),
                    content=ft.Text("Assessment Window Ended", size=11, color=ft.Colors.GREY_700, italic=True),
                )

            card = ft.Container(
                padding=18,
                border_radius=14,
                bgcolor=ft.Colors.SURFACE,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                shadow=ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.03, ft.Colors.BLACK), offset=ft.Offset(0, 2)),
                content=ft.Column([
                    ft.Row([
                        ex_badge,
                        ft.Row([
                            ft.Icon(ft.Icons.TIMER_OUTLINED, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(f"{ex_dur} Mins · {ex_q_count} Questions", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ], spacing=4, tight=True),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Text(ex_title, size=16, weight=ft.FontWeight.BOLD),
                    ft.Row([
                        ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(f"Availability Window: {o_time} to {c_time}", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], spacing=5, tight=True),
                    ft.Row([
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                            border_radius=6, bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                            content=ft.Text(f"Pass Mark: {ex_pass}%", size=10, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE_VARIANT),
                        ),
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
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
                    padding=50,
                    content=ft.Column([
                        ft.Icon(ft.Icons.TIMER_OFF_OUTLINED, size=44, color=ft.Colors.GREY_400),
                        ft.Text("No Scheduled Assessments", size=15, weight=ft.FontWeight.BOLD),
                        ft.Text("There are no exams currently scheduled for this training cohort.", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                )
            ],
            spacing=10,
        )

        # ── TAB 3: POLICIES & ACADEMIC INTEGRITY ───────────────────────────────
        def policy_bullet(icon_name: str, title_str: str, desc_str: str, color_val=theme_color):
            return ft.Container(
                padding=14,
                border_radius=12,
                bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                content=ft.Row([
                    ft.Container(
                        width=36, height=36, border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.12, color_val),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(icon_name, size=18, color=color_val),
                    ),
                    ft.Column([
                        ft.Text(title_str, size=12, weight=ft.FontWeight.BOLD),
                        ft.Text(desc_str, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], spacing=2, expand=True),
                ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            )

        policies_content = ft.Column([
            ft.Text("Academic Integrity & Examination Policies", size=14, weight=ft.FontWeight.BOLD),
            policy_bullet(
                ft.Icons.SECURITY_ROUNDED,
                "Automated Proctoring & Strike Enforcement",
                "Full-screen lock and tab-switching monitors are strictly enforced during exams. Unpermitted tab exits or app minimization accrue strikes and may invalidate your attempt.",
                ft.Colors.RED_700,
            ),
            policy_bullet(
                ft.Icons.LOCK_ROUNDED,
                "Confidential Grading Protocol",
                "Some examinations may not reveal scores or solution breakdowns instantly. Verified official grades will be released following instructor audit and moderation.",
                ft.Colors.AMBER_800,
            ),
            policy_bullet(
                ft.Icons.SUPPORT_AGENT_ROUNDED,
                "Instructor & Support Access",
                "Need assistance or an emergency attempt reset? Contact your cohort coordinator or enterprise training lead via your organization's support desk.",
                theme_color,
            ),
        ], spacing=10)

        # Tab Selection
        if active_tab == "curriculum":
            active_body = curriculum_content
        elif active_tab == "assessments":
            active_body = assessments_content
        else:
            active_body = policies_content

        # ── Assembled Page Layout ─────────────────────────────────────────────
        content_socket.content = ft.Column([
            ft.Row(cohort_switcher_chips, spacing=6, scroll=ft.ScrollMode.AUTO) if cohort_switcher_chips else ft.Container(),
            hero_cohort_card,
            subtab_switcher,
            active_body,
        ], spacing=16, scroll=ft.ScrollMode.AUTO)

    # ── Top AppBar ────────────────────────────────────────────────────────────
    app_bar = ft.AppBar(
        bgcolor=ft.Colors.SURFACE,
        leading=ft.IconButton(
            icon=ft.Icons.ARROW_BACK_ROUNDED,
            tooltip="Back to Dashboard",
            on_click=lambda _: page.go(back_target),
        ),
        title=ft.Row([
            ft.Text("Cohorts", size=13, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
            ft.Text("/", size=13, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Text(
                "Training Hub",
                color=ft.Colors.ON_SURFACE,
                weight=ft.FontWeight.BOLD,
                size=16,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
        ], spacing=5, tight=True),
        actions=[
            ft.IconButton(
                icon=ft.Icons.SHARE_ROUNDED,
                tooltip="Share Cohort",
                on_click=lambda _: page.run_task(open_whatsapp_share, "Cohort", "Nu-Age"),
            ),
            ft.IconButton(
                icon=ft.Icons.REFRESH_ROUNDED,
                tooltip="Refresh Data",
                on_click=lambda _: page.run_task(load_cohort_data),
            ),
        ],
    )

    page.run_task(load_cohort_data)

    return ft.View(
        route=f"/cohorts/{cohort_id}" if cohort_id else "/cohorts",
        appbar=app_bar,
        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
        bgcolor=ft.Colors.SURFACE,
        controls=[content_socket],
    )
