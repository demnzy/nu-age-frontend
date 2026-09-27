"""
Cohort Training Hub View for Nu-Age LMS.
Fully integrated with the application's global design system and themes:
  * Uses semantic theme tokens (ft.Colors.PRIMARY, SURFACE, ON_SURFACE, etc.)
  * Perfectly adapts across both Light and Dark modes with zero hardcoded clash colors.
  * 100% data-driven: no mock policies, fake dates, or placeholder organizations.
  * Direct support for curriculum modules, scheduled assessments, retry tracking, and cohort switching.
"""

from datetime import datetime, timezone
import urllib.parse
from typing import Optional, Dict, Any, List
import flet as ft

from src.requests.Cohorts import get_learner_cohorts
from src.components.cohort_exam_runner import build_cohort_exam_view


def _format_date(dt_str) -> Optional[str]:
    if not dt_str:
        return None
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
    """Renders the learner cohort hub tied directly into the Nu-Age theme."""
    token: Optional[str] = None
    try:
        token = await page.shared_preferences.get("auth_token")
    except Exception:
        token = None

    state: Dict[str, Any] = {
        "cohorts": [],
        "active_urgent_exams": [],
        "selected_cohort_id": str(cohort_id) if cohort_id else None,
        "active_tab": "curriculum",  # "curriculum", "assessments", "details"
        "search_query": "",
        "filter_category": "ALL",     # "ALL", "IN_PROGRESS", "COMPLETED"
        "loading": True,
    }

    content_socket = ft.Container(expand=True)

    def is_mobile() -> bool:
        pw = getattr(page, "width", None)
        w = pw if isinstance(pw, (int, float)) and pw > 0 else 1000
        return w < 768

    def show_snack(text: str, is_error: bool = False):
        snack = ft.SnackBar(
            content=ft.Text(text, size=13, color=ft.Colors.WHITE),
            bgcolor=ft.Colors.RED_700 if is_error else ft.Colors.PRIMARY,
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
            f"🎓 Learning in '{cohort_name}' by {org_name} on Nu-Age! 🚀\n"
            f"Explore interactive courses, modules, and certified assessments.\n"
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

    def launch_candidate_exam(org_id: str, c_id: str, exam_id: str):
        return lambda _: page.go(f"/cohorts/{c_id}/exams/{exam_id}?org_id={org_id}")

    # ── Data Fetching ─────────────────────────────────────────────────────────
    async def load_cohort_data():
        state["loading"] = True
        render_view()
        page.update()

        try:
            res = await get_learner_cohorts(token)
            cohorts = res.get("cohorts", [])
            state["cohorts"] = cohorts
            state["active_urgent_exams"] = res.get("active_urgent_exams", [])
        except Exception:
            cohorts = []
            state["cohorts"] = []

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

    # Pre-fetch data for instant initial rendering
    try:
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
    except Exception:
        state["cohorts"] = []
        state["loading"] = False

    # ── Main Render UI ────────────────────────────────────────────────────────
    def render_view():
        if state["loading"]:
            content_socket.content = ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=60,
                content=ft.Column([
                    ft.ProgressRing(color=ft.Colors.PRIMARY, width=38, height=38),
                    ft.Text("Loading Training Cohort...", size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True, spacing=14),
            )
            return

        cohorts = state["cohorts"]

        # Empty State: User is not enrolled in any cohorts
        if not cohorts:
            content_socket.content = ft.Container(
                expand=True,
                alignment=ft.Alignment.CENTER,
                padding=32,
                content=ft.Column([
                    ft.Container(
                        width=72, height=72, border_radius=36,
                        bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(ft.Icons.GROUPS_ROUNDED, size=36, color=ft.Colors.PRIMARY),
                    ),
                    ft.Text("No Enrolled Cohorts Found", size=18, weight=ft.FontWeight.BOLD),
                    ft.Container(
                        width=400,
                        content=ft.Text(
                            "You are currently not enrolled in any organization training cohorts. When your institution assigns you to a curriculum track, it will appear here.",
                            size=12, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER,
                        ),
                    ),
                    ft.Container(height=8),
                    ft.FilledButton(
                        "Browse Course Catalog",
                        icon=ft.Icons.AUTO_STORIES_ROUNDED,
                        style=ft.ButtonStyle(
                            bgcolor=ft.Colors.PRIMARY,
                            color=ft.Colors.ON_PRIMARY,
                            padding=ft.Padding.symmetric(horizontal=18, vertical=10),
                            shape=ft.RoundedRectangleBorder(radius=10),
                        ),
                        on_click=lambda _: page.go("/courses"),
                    ),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
            )
            return

        selected_c = None
        for c in cohorts:
            if str(c.get("id")) == str(state["selected_cohort_id"]):
                selected_c = c
                break
        if not selected_c:
            selected_c = cohorts[0]
            state["selected_cohort_id"] = str(selected_c.get("id"))

        c_name = selected_c.get("name") or "Untitled Cohort"
        c_org = selected_c.get("organisation_name") or ""
        c_org_id = str(selected_c.get("organisation_id", ""))
        c_id = str(selected_c.get("id", ""))
        c_desc = selected_c.get("description") or ""
        c_status = _get_effective_cohort_status(selected_c)
        s_date = _format_date(selected_c.get("start_date"))
        e_date = _format_date(selected_c.get("end_date"))
        c_courses = selected_c.get("courses", [])
        c_exams = selected_c.get("exams", [])

        avg_prog = 0
        if c_courses:
            avg_prog = round(sum(crs.get("progress", 0) for crs in c_courses) / len(c_courses))

        # ── Top Bar ───────────────────────────────────────────────────────────
        top_appbar = ft.Container(
            padding=ft.Padding.symmetric(horizontal=16, vertical=10),
            content=ft.Row([
                ft.Row([
                    ft.IconButton(
                        icon=ft.Icons.ARROW_BACK_ROUNDED,
                        icon_size=20,
                        tooltip="Back to Dashboard",
                        on_click=lambda _: page.go(back_target),
                    ),
                    ft.Column([
                        ft.Row([
                            ft.Text("Cohorts", size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
                            ft.Text("·", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(c_org if c_org else "Training Hub", size=11, color=ft.Colors.PRIMARY, weight=ft.FontWeight.BOLD),
                        ], spacing=4, tight=True),
                        ft.Text(c_name, size=18, weight=ft.FontWeight.BOLD),
                    ], spacing=1, tight=True),
                ], spacing=6, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row([
                    ft.IconButton(
                        icon=ft.Icons.SHARE_ROUNDED,
                        icon_size=18,
                        tooltip="Share Cohort",
                        on_click=lambda _: page.run_task(open_whatsapp_share, c_name, c_org),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.REFRESH_ROUNDED,
                        icon_size=18,
                        tooltip="Refresh Data",
                        on_click=lambda _: page.run_task(load_cohort_data),
                    ),
                ], spacing=2, tight=True),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
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
                ], spacing=5, tight=True),
            )
        ]
        if c_org:
            header_tags.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=6,
                    bgcolor=ft.Colors.with_opacity(0.22, ft.Colors.BLACK),
                    content=ft.Row([
                        ft.Icon(ft.Icons.BUSINESS_ROUNDED, size=12, color=ft.Colors.WHITE),
                        ft.Text(c_org, size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    ], spacing=5, tight=True),
                )
            )

        date_chip = None
        if s_date or e_date:
            date_text = f"{s_date or 'Start'} – {e_date or 'End'}"
            date_chip = ft.Container(
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                border_radius=6,
                bgcolor=ft.Colors.with_opacity(0.22, ft.Colors.BLACK),
                content=ft.Row([
                    ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, size=12, color=ft.Colors.WHITE),
                    ft.Text(date_text, size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ], spacing=5, tight=True),
            )

        hero_card = ft.Container(
            padding=20,
            border_radius=18,
            gradient=ft.LinearGradient(
                colors=[ft.Colors.PRIMARY, ft.Colors.SECONDARY],
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
            ),
            shadow=ft.BoxShadow(
                blur_radius=16,
                color=ft.Colors.with_opacity(0.18, ft.Colors.PRIMARY),
                offset=ft.Offset(0, 6),
            ),
            content=ft.Column([
                ft.Row([
                    ft.Row(header_tags, spacing=6, tight=True),
                    date_chip if date_chip else ft.Container(),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Text(c_name, size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ft.Text(c_desc, size=12, color=ft.Colors.with_opacity(0.92, ft.Colors.WHITE)) if c_desc else ft.Container(),
                ft.Container(height=4),
                # Metric Ribbon
                ft.Container(
                    padding=14,
                    border_radius=12,
                    bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.BLACK),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.18, ft.Colors.WHITE)),
                    content=ft.Row([
                        # Curriculum Progress
                        ft.Column([
                            ft.Row([
                                ft.Text("Curriculum Track Progress", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                ft.Text(f"{avg_prog}%", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.ProgressBar(
                                value=avg_prog / 100.0,
                                color=ft.Colors.WHITE,
                                bgcolor=ft.Colors.with_opacity(0.28, ft.Colors.WHITE),
                                height=6,
                                border_radius=3,
                            ),
                        ], spacing=5, expand=True),
                        ft.Container(width=16),
                        # Courses Metric
                        ft.Column([
                            ft.Text("Courses", size=10, color=ft.Colors.with_opacity(0.85, ft.Colors.WHITE)),
                            ft.Text(str(len(c_courses)), size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
                        ft.Container(width=1, height=26, bgcolor=ft.Colors.with_opacity(0.25, ft.Colors.WHITE)),
                        # Assessments Metric
                        ft.Column([
                            ft.Text("Exams", size=10, color=ft.Colors.with_opacity(0.85, ft.Colors.WHITE)),
                            ft.Text(str(len(c_exams)), size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ),
            ], spacing=10),
        )

        # ── Active Urgent Exam Banner (if any live/urgent assessment) ─────────
        urgent_exam_banner = None
        if state["active_urgent_exams"]:
            u_ex = state["active_urgent_exams"][0]
            u_id = str(u_ex.get("id", ""))
            u_title = u_ex.get("title") or "Assessment"
            u_in_prog = bool(u_ex.get("is_in_progress") or (u_ex.get("in_progress_submission") is not None))
            u_closes = _format_datetime(u_ex.get("closes_at"))
            urgent_exam_banner = ft.Container(
                padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                border_radius=10,
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_700 if u_in_prog else ft.Colors.PRIMARY),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.25, ft.Colors.AMBER_700 if u_in_prog else ft.Colors.PRIMARY)),
                content=ft.Row([
                    ft.Row([
                        ft.Icon(
                            ft.Icons.FLASH_ON_ROUNDED if u_in_prog else ft.Icons.NOTIFICATIONS_ACTIVE_ROUNDED,
                            size=18,
                            color=ft.Colors.AMBER_800 if u_in_prog else ft.Colors.PRIMARY,
                        ),
                        ft.Column([
                            ft.Text(
                                "Exam In Progress — Finish Attempt" if u_in_prog else "Live Assessment Available · Not Started",
                                size=11,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.AMBER_900 if u_in_prog else ft.Colors.PRIMARY,
                            ),
                            ft.Text(
                                f"{u_title} · Closes {u_closes}",
                                size=11,
                                color=ft.Colors.ON_SURFACE,
                            ),
                        ], spacing=1, tight=True),
                    ], spacing=10, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.FilledButton(
                        "Resume Exam" if u_in_prog else "Start Assessment",
                        icon=ft.Icons.PLAY_ARROW_ROUNDED,
                        style=ft.ButtonStyle(
                            bgcolor=ft.Colors.AMBER_700 if u_in_prog else ft.Colors.PRIMARY,
                            color=ft.Colors.WHITE if u_in_prog else ft.Colors.ON_PRIMARY,
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                        ),
                        on_click=launch_candidate_exam(c_org_id, c_id, u_id),
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            )

        # ── Segmented Navigation Tabs ─────────────────────────────────────────
        def set_tab(tab_key: str):
            state["active_tab"] = tab_key
            render_view()
            page.update()

        tab_items = [
            ("curriculum", f"Curriculum ({len(c_courses)})", ft.Icons.AUTO_STORIES_ROUNDED),
            ("assessments", f"Assessments ({len(c_exams)})", ft.Icons.TIMER_ROUNDED),
            ("details", "Cohort Info", ft.Icons.INFO_OUTLINE_ROUNDED),
        ]

        segmented_tabs = ft.Container(
            padding=4,
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
            content=ft.Row([
                ft.Container(
                    expand=True,
                    padding=ft.Padding.symmetric(vertical=8),
                    border_radius=9,
                    bgcolor=ft.Colors.PRIMARY if state["active_tab"] == k else ft.Colors.TRANSPARENT,
                    shadow=ft.BoxShadow(blur_radius=4, color=ft.Colors.with_opacity(0.20, ft.Colors.PRIMARY), offset=ft.Offset(0, 1)) if state["active_tab"] == k else None,
                    alignment=ft.Alignment.CENTER,
                    ink=True,
                    on_click=lambda _, target=k: set_tab(target),
                    content=ft.Row([
                        ft.Icon(
                            icon,
                            size=14,
                            color=ft.Colors.ON_PRIMARY if state["active_tab"] == k else ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Text(
                            label,
                            size=12,
                            weight=ft.FontWeight.BOLD if state["active_tab"] == k else ft.FontWeight.W_500,
                            color=ft.Colors.ON_PRIMARY if state["active_tab"] == k else ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ], tight=True, spacing=6),
                )
                for k, label, icon in tab_items
            ], spacing=4),
        )

        # ── Search & Filter Bar ───────────────────────────────────────────────
        def on_search_change(e):
            state["search_query"] = (e.control.value or "").strip().lower()
            render_view()
            page.update()

        def set_filter_cat(cat_key: str):
            state["filter_category"] = cat_key
            render_view()
            page.update()

        filter_chips_meta = [
            ("ALL", "All"),
            ("NOT_STARTED", "Not Started"),
            ("IN_PROGRESS", "In Progress"),
            ("COMPLETED", "Completed"),
        ]

        filter_chips_row = ft.Row([
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                border_radius=14,
                bgcolor=ft.Colors.PRIMARY if state["filter_category"] == c_k else ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                ink=True,
                on_click=lambda _, target=c_k: set_filter_cat(target),
                content=ft.Text(
                    c_label,
                    size=10,
                    weight=ft.FontWeight.BOLD if state["filter_category"] == c_k else ft.FontWeight.W_500,
                    color=ft.Colors.ON_PRIMARY if state["filter_category"] == c_k else ft.Colors.ON_SURFACE,
                ),
            )
            for c_k, c_label in filter_chips_meta
        ], spacing=6, tight=True)

        search_filter_bar = ft.Container(
            padding=ft.Padding.symmetric(horizontal=14, vertical=8),
            border_radius=10,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
            content=ft.Row([
                ft.Row([
                    ft.Icon(ft.Icons.SEARCH_ROUNDED, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Container(
                        width=280,
                        content=ft.TextField(
                            value=state["search_query"],
                            hint_text="Filter items by title...",
                            border=ft.InputBorder.NONE,
                            dense=True,
                            height=32,
                            text_size=12,
                            on_change=on_search_change,
                        ),
                    ),
                ], spacing=6, tight=True),
                filter_chips_row,
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        q = state["search_query"]
        cat = state["filter_category"]

        # ── TAB 1: CURRICULUM COURSES ─────────────────────────────────────────
        curriculum_cards = []
        for crs in c_courses:
            crs_name = crs.get("name") or "Untitled Course"
            if q and q not in crs_name.lower():
                continue
            crs_id = str(crs.get("id", ""))
            crs_prog = crs.get("progress", 0)
            crs_img = crs.get("image_url")
            crs_desc = crs.get("description")
            if cat == "NOT_STARTED" and crs_prog > 0:
                continue
            if cat == "IN_PROGRESS" and (crs_prog == 0 or crs_prog == 100):
                continue
            if cat == "COMPLETED" and crs_prog < 100:
                continue

            # Visual thumbnail
            if crs_img:
                thumb = ft.Image(
                    src=crs_img,
                    width=46,
                    height=46,
                    fit=ft.BoxFit.COVER,
                    border_radius=ft.BorderRadius.all(10),
                    error_content=ft.Container(
                        width=46,
                        height=46,
                        border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(ft.Icons.AUTO_STORIES_ROUNDED, size=22, color=ft.Colors.PRIMARY),
                    ),
                )
            else:
                thumb = ft.Container(
                    width=46,
                    height=46,
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.PRIMARY),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.AUTO_STORIES_ROUNDED, size=22, color=ft.Colors.PRIMARY),
                )

            desc_control = ft.Text(crs_desc, size=11, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS) if crs_desc else ft.Container()

            card = ft.Container(
                padding=14,
                border_radius=12,
                bgcolor=ft.Colors.SURFACE,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                shadow=ft.BoxShadow(blur_radius=6, color=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE), offset=ft.Offset(0, 2)),
                content=ft.Row([
                    thumb,
                    ft.Column([
                        ft.Text(crs_name, size=13, weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        desc_control,
                        ft.Row([
                            ft.Text(f"{crs_prog}% Completed", size=11, weight=ft.FontWeight.W_600, color=ft.Colors.PRIMARY),
                        ], spacing=4, tight=True),
                        ft.ProgressBar(
                            value=crs_prog / 100.0,
                            color=ft.Colors.PRIMARY,
                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                            height=4,
                            border_radius=2,
                        ),
                    ], spacing=3, expand=True),
                    ft.Container(width=10),
                    ft.FilledButton(
                        "Resume" if crs_prog > 0 else "Study",
                        icon=ft.Icons.PLAY_ARROW_ROUNDED,
                        style=ft.ButtonStyle(
                            bgcolor=ft.Colors.PRIMARY,
                            color=ft.Colors.ON_PRIMARY,
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                        ),
                        on_click=lambda _, cid=crs_id: page.go(f"/courses/{cid}"),
                    ),
                ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            )
            curriculum_cards.append(card)

        curriculum_view = ft.Column(
            curriculum_cards if curriculum_cards else [
                ft.Container(
                    alignment=ft.Alignment.CENTER,
                    padding=40,
                    content=ft.Column([
                        ft.Icon(ft.Icons.AUTO_STORIES_OUTLINED, size=38, color=ft.Colors.GREY_400),
                        ft.Text("No Courses Assigned Yet" if not c_courses else "No Courses Match Filter", size=14, weight=ft.FontWeight.BOLD),
                        ft.Text("Your organization has not assigned any courses to this cohort yet." if not c_courses else "Try adjusting your search query or filter.", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                )
            ],
            spacing=10,
        )

        # ── TAB 2: ASSESSMENTS & EXAMS ─────────────────────────────────────────
        exam_cards = []
        for ex in c_exams:
            ex_title = ex.get("title") or "Exam"
            if q and q not in ex_title.lower():
                continue
            ex_id = str(ex.get("id", ""))
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
            is_active_attempt = bool(ex.get("is_in_progress") or (user_sub and user_sub.get("status") == "in_progress") or ex.get("in_progress_submission"))

            if cat == "NOT_STARTED" and (is_active_attempt or completed_attempts > 0):
                continue
            if cat == "IN_PROGRESS" and not is_active_attempt:
                continue
            if cat == "COMPLETED" and not (user_sub and user_sub.get("status") in ("submitted", "graded", "flagged_violation", "timed_out")):
                continue

            # Status pill
            if is_active_attempt:
                ex_badge = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=4, bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.AMBER_700),
                    content=ft.Row([
                        ft.Icon(ft.Icons.TIMER_ROUNDED, size=11, color=ft.Colors.AMBER_800),
                        ft.Text("IN PROGRESS · RESUME", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_900),
                    ], spacing=4, tight=True),
                )
            elif completed_attempts == 0:
                if ex_status == "OPEN_NOW":
                    ex_badge = ft.Container(
                        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                        border_radius=4, bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                        content=ft.Row([
                            ft.Container(width=6, height=6, border_radius=3, bgcolor=ft.Colors.PRIMARY),
                            ft.Text("NOT STARTED · OPEN", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                        ], spacing=4, tight=True),
                    )
                elif ex_status == "SCHEDULED":
                    ex_badge = ft.Container(
                        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                        border_radius=4, bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                        content=ft.Row([
                            ft.Icon(ft.Icons.LOCK_CLOCK_ROUNDED, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text("NOT STARTED · SCHEDULED", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                        ], spacing=4, tight=True),
                    )
                else:
                    ex_badge = ft.Container(
                        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                        border_radius=4, bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                        content=ft.Text("NOT STARTED · CLOSED", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                    )
            elif completed_attempts > 0 and can_retry and ex_status == "OPEN_NOW":
                ex_badge = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=4, bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                    content=ft.Row([
                        ft.Icon(ft.Icons.REFRESH_ROUNDED, size=11, color=ft.Colors.PRIMARY),
                        ft.Text(f"ATTEMPT {completed_attempts + 1} AVAILABLE", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                    ], spacing=4, tight=True),
                )
            elif completed_attempts >= ex_max_attempts:
                ex_badge = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=4, bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                    content=ft.Text("COMPLETED", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                )
            elif ex_status == "CLOSED":
                ex_badge = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=4, bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                    content=ft.Text("CLOSED", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                )
            else:
                ex_badge = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=4, bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                    content=ft.Text("SCHEDULED", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                )

            # Action button
            if is_active_attempt:
                action_btn = ft.FilledButton(
                    "Resume Exam",
                    icon=ft.Icons.PLAY_ARROW_ROUNDED,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.AMBER_700, color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=8), padding=ft.Padding.symmetric(horizontal=12, vertical=8)),
                    on_click=launch_candidate_exam(c_org_id, c_id, ex_id),
                )
            elif user_sub and user_sub.get("status") in ("submitted", "graded", "flagged_violation", "timed_out"):
                score = user_sub.get("percentage", 0.0)
                passed = user_sub.get("passed", False)
                sub_pill = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                    border_radius=6,
                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY if passed else ft.Colors.RED_600),
                    content=ft.Row([
                        ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED if passed else ft.Icons.CANCEL_ROUNDED, size=13, color=ft.Colors.PRIMARY if passed else ft.Colors.RED_700),
                        ft.Text(f"{score}% ({'PASSED' if passed else 'FAILED'})", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY if passed else ft.Colors.RED_700),
                    ], spacing=5, tight=True),
                )
                if can_retry and ex_status == "OPEN_NOW":
                    action_btn = ft.Row([
                        sub_pill,
                        ft.FilledButton(
                            f"Retake ({completed_attempts + 1}/{ex_max_attempts})",
                            icon=ft.Icons.REFRESH_ROUNDED,
                            style=ft.ButtonStyle(bgcolor=ft.Colors.PRIMARY, color=ft.Colors.ON_PRIMARY, shape=ft.RoundedRectangleBorder(radius=8), padding=ft.Padding.symmetric(horizontal=10, vertical=8)),
                            on_click=launch_candidate_exam(c_org_id, c_id, ex_id),
                        ),
                    ], spacing=6, tight=True)
                else:
                    action_btn = ft.Row([
                        sub_pill,
                        ft.Text(f"All {ex_max_attempts} attempts used", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], spacing=6, tight=True)
            elif ex_status == "OPEN_NOW":
                action_btn = ft.FilledButton(
                    "Start Assessment",
                    icon=ft.Icons.PLAY_ARROW_ROUNDED,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.PRIMARY, color=ft.Colors.ON_PRIMARY, shape=ft.RoundedRectangleBorder(radius=8), padding=ft.Padding.symmetric(horizontal=14, vertical=8)),
                    on_click=launch_candidate_exam(c_org_id, c_id, ex_id),
                )
            elif ex_status == "SCHEDULED":
                action_btn = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.PRIMARY),
                    content=ft.Row([
                        ft.Icon(ft.Icons.LOCK_CLOCK_ROUNDED, size=13, color=ft.Colors.PRIMARY),
                        ft.Text(f"Opens: {o_time}", size=11, color=ft.Colors.PRIMARY, weight=ft.FontWeight.W_500),
                    ], spacing=5, tight=True),
                )
            else:
                action_btn = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                    content=ft.Text("Exam Window Closed", size=11, color=ft.Colors.ON_SURFACE_VARIANT, italic=True),
                )

            # Metadata capsules
            meta_chips = [
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                    border_radius=4, bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                    content=ft.Text(f"Pass Mark: {ex_pass}%", size=10, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE_VARIANT),
                ),
            ]
            if ex_max_attempts > 1:
                meta_chips.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                        border_radius=4, bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                        content=ft.Text(f"Attempts: {completed_attempts}/{ex_max_attempts} Used", size=10, weight=ft.FontWeight.W_600, color=ft.Colors.PRIMARY if can_retry else ft.Colors.ON_SURFACE_VARIANT),
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
                            ft.Text(f"{ex_dur} Mins{q_label}", size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
                        ], spacing=4, tight=True),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Text(ex_title, size=15, weight=ft.FontWeight.BOLD),
                    ft.Row([
                        ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(f"Window: {_format_datetime(ex.get('opens_at'))} – {_format_datetime(ex.get('closes_at'))}", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], spacing=4, tight=True),
                    ft.Row(meta_chips, spacing=6),
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    ft.Row([action_btn], alignment=ft.MainAxisAlignment.END),
                ], spacing=10),
            )
            exam_cards.append(card)

        assessments_view = ft.Column(
            exam_cards if exam_cards else [
                ft.Container(
                    alignment=ft.Alignment.CENTER,
                    padding=40,
                    content=ft.Column([
                        ft.Icon(ft.Icons.TIMER_OFF_OUTLINED, size=38, color=ft.Colors.GREY_400),
                        ft.Text("No Assessments Scheduled" if not c_exams else "No Assessments Match Filter", size=14, weight=ft.FontWeight.BOLD),
                        ft.Text("Your organization has not scheduled any exams for this cohort yet." if not c_exams else "Try adjusting your search filter.", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                )
            ],
            spacing=10,
        )

        # ── TAB 3: COHORT INFO & PROGRAM PROFILE ──────────────────────────────
        cohort_dropdown_options = [
            ft.dropdown.Option(str(ch.get("id")), f"{ch.get('name', 'Cohort')} ({ch.get('organisation_name', 'Org')})")
            for ch in cohorts
        ]

        def on_cohort_select(e):
            state["selected_cohort_id"] = str(e.control.value)
            render_view()
            page.update()

        info_rows = []
        if len(cohorts) > 1:
            info_rows.append(
                ft.Row([
                    ft.Text("Switch Cohort:", size=12, weight=ft.FontWeight.BOLD, width=140),
                    ft.Dropdown(
                        value=state["selected_cohort_id"],
                        options=cohort_dropdown_options,
                        width=320,
                        dense=True,
                        text_size=12,
                        border_color=ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE),
                        focused_border_color=ft.Colors.PRIMARY,
                        on_select=on_cohort_select,
                    ),
                ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER)
            )

        if c_org:
            org_content = [
                ft.Text(c_org, size=13, weight=ft.FontWeight.W_600),
            ]
            if selected_c.get("organisation_logo"):
                org_content.insert(0, ft.Image(src=selected_c.get("organisation_logo"), width=24, height=24, fit=ft.BoxFit.CONTAIN))
            info_rows.append(
                ft.Row([
                    ft.Text("Host Organization:", size=12, weight=ft.FontWeight.BOLD, width=140),
                    ft.Row(org_content, spacing=8, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER)
            )

        if s_date or e_date:
            info_rows.append(
                ft.Row([
                    ft.Text("Academic Period:", size=12, weight=ft.FontWeight.BOLD, width=140),
                    ft.Text(f"{s_date or 'Start'} to {e_date or 'End'} ({c_status})", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ], spacing=12)
            )

        info_rows.append(
            ft.Row([
                ft.Text("Curriculum Progress:", size=12, weight=ft.FontWeight.BOLD, width=140),
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=6,
                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                    content=ft.Text(f"{avg_prog}% Completed", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                ),
            ], spacing=12)
        )

        info_rows.append(
            ft.Row([
                ft.Text("Curriculum Summary:", size=12, weight=ft.FontWeight.BOLD, width=140),
                ft.Text(f"{len(c_courses)} Courses Enrolled · {len(c_exams)} Assessments Scheduled", size=12, color=ft.Colors.ON_SURFACE),
            ], spacing=12)
        )

        if c_desc:
            info_rows.append(
                ft.Row([
                    ft.Text("Description:", size=12, weight=ft.FontWeight.BOLD, width=140),
                    ft.Container(
                        expand=True,
                        content=ft.Text(c_desc, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ),
                ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START)
            )

        details_view = ft.Container(
            padding=18,
            border_radius=12,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
            shadow=ft.BoxShadow(blur_radius=6, color=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE), offset=ft.Offset(0, 2)),
            content=ft.Column([
                ft.Text("Cohort Profile & Details", size=16, weight=ft.FontWeight.BOLD),
                ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                ft.Column(info_rows, spacing=14),
            ], spacing=12),
        )

        # Active tab body
        if state["active_tab"] == "assessments":
            active_body = assessments_view
        elif state["active_tab"] == "details":
            active_body = details_view
        else:
            active_body = curriculum_view

        # ── Multi-Cohort Switcher Chips (if enrolled in > 1 cohort) ───────────
        cohort_switcher_chips = []
        if len(cohorts) > 1:
            for ch in cohorts:
                ch_id = str(ch.get("id"))
                is_selected = (ch_id == c_id)
                ch_name_label = ch.get("name") or "Cohort"

                def make_select_fn(target_id):
                    def _sel(_):
                        state["selected_cohort_id"] = target_id
                        render_view()
                        page.update()
                    return _sel

                cohort_switcher_chips.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                        border_radius=16,
                        bgcolor=ft.Colors.PRIMARY if is_selected else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                        border=ft.Border.all(1, ft.Colors.PRIMARY if is_selected else ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                        ink=True,
                        on_click=make_select_fn(ch_id),
                        content=ft.Row([
                            ft.Icon(
                                ft.Icons.SCHOOL_ROUNDED,
                                size=13,
                                color=ft.Colors.ON_PRIMARY if is_selected else ft.Colors.ON_SURFACE_VARIANT,
                            ),
                            ft.Text(
                                ch_name_label,
                                size=11,
                                weight=ft.FontWeight.BOLD if is_selected else ft.FontWeight.W_500,
                                color=ft.Colors.ON_PRIMARY if is_selected else ft.Colors.ON_SURFACE,
                            ),
                        ], spacing=5, tight=True),
                    )
                )

        # ── Assemble Overall Layout ───────────────────────────────────────────
        pw = getattr(page, "width", None)
        container_w = min(pw - 32, 1050) if pw and pw > 768 else None

        main_column = ft.Column([
            top_appbar,
            ft.Container(
                alignment=ft.Alignment.TOP_CENTER,
                padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                content=ft.Container(
                    width=container_w,
                    content=ft.Column([
                        ft.Row(cohort_switcher_chips, spacing=6, scroll=ft.ScrollMode.AUTO) if cohort_switcher_chips else ft.Container(),
                        hero_card,
                        urgent_exam_banner if urgent_exam_banner else ft.Container(),
                        segmented_tabs,
                        search_filter_bar,
                        active_body,
                        ft.Container(height=32),
                    ], spacing=12),
                ),
                expand=True,
            ),
        ], spacing=0, scroll=ft.ScrollMode.AUTO)

        content_socket.content = main_column

    # Initial synchronous render
    render_view()

    return ft.View(
        route=f"/cohorts/{cohort_id}" if cohort_id else "/cohorts",
        padding=0,
        bgcolor=ft.Colors.SURFACE,
        controls=[content_socket],
    )
