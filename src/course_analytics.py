import asyncio
import flet as ft
from src.requests.Courses import (
    get_courses, 
    get_course_curriculum,
    get_completion_stats,
    get_certificates_issued,
)
from src.requests.enrollments import (
    get_enrolled_students,
    get_weekly_activity
)
from src.requests.organisations import get_my_organisation
from src.requests.chats import start_direct_message
from src.components.bottom_appbar import get_bottom_appbar


# ═══════════════════════════════════════════════════════════════════════════════
# COURSE ANALYTICS VIEW (UNCLUTTERED, SEGMENTED & EXPLANATORY)
# ═══════════════════════════════════════════════════════════════════════════════

def _pill(label: str, bg, fg, icon=None) -> ft.Container:
    controls = []
    if icon:
        controls.append(ft.Icon(icon, size=11, color=fg))
    controls.append(ft.Text(label, size=10, color=fg, weight=ft.FontWeight.W_600))
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        bgcolor=bg,
        border_radius=8,
        content=ft.Row(controls, spacing=4, tight=True),
    )


def _section_header(title: str, subtitle: str = None) -> ft.Column:
    controls = [
        ft.Text(title, size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
    ]
    if subtitle:
        controls.append(ft.Text(subtitle, size=11, color=ft.Colors.ON_SURFACE_VARIANT))
    return ft.Column(controls, spacing=2)


def _progress_color(pct: float):
    if pct >= 0.75:
        return ft.Colors.GREEN_600
    if pct >= 0.4:
        return ft.Colors.AMBER_700
    return ft.Colors.BLUE_600


async def course_analytics_view(page: ft.Page, org_id: str, course_id: str):
    app_bar = get_bottom_appbar(page)
    token = await page.shared_preferences.get("auth_token")

    def _go_back(e=None):
        if len(page.views) > 1:
            page.views.pop()
            page.update()
        elif hasattr(page, "on_view_pop") and callable(page.on_view_pop):
            page.on_view_pop(None)
        else:
            page.go(f"/organisations/{org_id}" if org_id else "/organisations")

    theme_color = ft.Colors.INDIGO_600
    course_data: dict = {}
    students: list = []
    curriculum: dict = {}
    completion_stats: dict = {}
    certificates_data: dict = {}
    weekly_activity: list = []

    # Active tab state: "performance", "curriculum", "roster"
    active_tab = "performance"

    # Reactive filters for student table
    student_search_query = ""
    student_filter_status = "all"  # "all", "completed", "in_progress", "not_started"

    # Clean centered loading container (no appbar, full center)
    content_socket = ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.ProgressRing(color=ft.Colors.PRIMARY, width=44, height=44, stroke_width=3.5),
                ft.Container(height=16),
                ft.Text("Aggregating Course Intelligence…", size=13, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE_VARIANT),
            ],
        ),
    )

    def _show_load_error(msg: str):
        content_socket.alignment = ft.Alignment.CENTER
        content_socket.content = ft.Container(
            padding=32,
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, size=48, color=ft.Colors.RED_400),
                    ft.Text("Analytics Unavailable", size=17, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Text(msg, size=12, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER),
                    ft.Container(height=8),
                    ft.FilledButton(
                        "Retry Analytics",
                        icon=ft.Icons.REFRESH_ROUNDED,
                        style=ft.ButtonStyle(
                            bgcolor=theme_color,
                            shape=ft.RoundedRectangleBorder(radius=10),
                            padding=ft.Padding.symmetric(horizontal=16, vertical=10),
                        ),
                        on_click=lambda _: page.run_task(fetch_analytics_data),
                    ),
                ],
            ),
        )
        page.update()

    # ─────────────────────────────────────────────────────────────────────────
    # BENTO STAT CARD
    # ─────────────────────────────────────────────────────────────────────────
    def bento_stat(icon, title: str, value: str, subtext: str, accent_color, col_spec=None):
        return ft.Container(
            col=col_spec or {"xs": 12, "sm": 6, "md": 3},
            bgcolor=ft.Colors.SURFACE,
            border_radius=14,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            padding=ft.Padding.all(16),
            shadow=ft.BoxShadow(
                blur_radius=8,
                color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                offset=ft.Offset(0, 2),
            ),
            content=ft.Column([
                ft.Row([
                    ft.Container(
                        width=36,
                        height=36,
                        border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.12, accent_color),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(icon, size=18, color=accent_color),
                    ),
                    ft.Text(title, size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Container(height=4),
                ft.Text(str(value), size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                ft.Text(subtext, size=11, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ], spacing=2),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # EXPLANATORY CHART 1: PROGRESS TIER DISTRIBUTION (HISTOGRAM BREAKDOWN)
    # ─────────────────────────────────────────────────────────────────────────
    def build_tier_distribution_card(students_list: list):
        total = max(len(students_list), 1)

        # Categorize into 5 pedagogical tiers
        tier_mastery = [s for s in students_list if float(s.get("progress", 0) or 0) >= 90.0]
        tier_proficient = [s for s in students_list if 60.0 <= float(s.get("progress", 0) or 0) < 90.0]
        tier_developing = [s for s in students_list if 30.0 <= float(s.get("progress", 0) or 0) < 60.0]
        tier_initiating = [s for s in students_list if 0.1 <= float(s.get("progress", 0) or 0) < 30.0]
        tier_unstarted = [s for s in students_list if float(s.get("progress", 0) or 0) < 0.1]

        tiers = [
            {"label": "Mastery (90% – 100%)", "count": len(tier_mastery), "color": ft.Colors.GREEN_600, "insight": "Ready for certification"},
            {"label": "Proficient (60% – 89%)", "count": len(tier_proficient), "color": ft.Colors.TEAL_600, "insight": "On track, strong pacing"},
            {"label": "Developing (30% – 59%)", "count": len(tier_developing), "color": ft.Colors.BLUE_600, "insight": "Midway through modules"},
            {"label": "Early Stage (1% – 29%)", "count": len(tier_initiating), "color": ft.Colors.AMBER_600, "insight": "Started foundational lessons"},
            {"label": "Unstarted (0%)", "count": len(tier_unstarted), "color": ft.Colors.GREY_500, "insight": "Enrolled but inactive"},
        ]

        # Pedagogical diagnosis text
        if len(tier_mastery) / total >= 0.4:
            diagnosis_text = "High course completion health: Over 40% of enrolled learners have achieved or are approaching mastery."
            diag_color = ft.Colors.GREEN_700
            diag_bg = ft.Colors.GREEN_50
        elif len(tier_unstarted) / total >= 0.5:
            diagnosis_text = "Action Suggested: More than half of enrolled learners have not started. Consider sending an introductory nudge."
            diag_color = ft.Colors.AMBER_800
            diag_bg = ft.Colors.AMBER_50
        else:
            diagnosis_text = "Balanced progression: Learners are steadily distributed across curriculum milestones."
            diag_color = ft.Colors.BLUE_700
            diag_bg = ft.Colors.BLUE_50

        tier_rows = []
        for t in tiers:
            pct = (t["count"] / total) * 100
            tier_rows.append(
                ft.Container(
                    margin=ft.Margin.only(bottom=10),
                    content=ft.Column([
                        ft.Row([
                            ft.Row([
                                ft.Container(width=10, height=10, border_radius=5, bgcolor=t["color"]),
                                ft.Text(t["label"], size=12, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                            ], spacing=6),
                            ft.Row([
                                ft.Text(f"{t['count']} learners", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                                ft.Text(f"({int(pct)}%)", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                            ], spacing=4),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Container(height=4),
                        # Horizontal progress bar (never shrinks, adapts fluidly)
                        ft.Container(
                            height=8,
                            border_radius=4,
                            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                            content=ft.Row([
                                ft.Container(
                                    height=8,
                                    border_radius=4,
                                    bgcolor=t["color"],
                                    expand=int(pct) if pct > 0 else 0,
                                ) if pct > 0 else ft.Container(),
                                ft.Container(
                                    height=8,
                                    expand=int(100 - pct) if pct < 100 else 0,
                                ) if pct < 100 else ft.Container(),
                            ], spacing=0),
                        ),
                        ft.Text(t["insight"], size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], spacing=2),
                )
            )

        return ft.Container(
            bgcolor=ft.Colors.SURFACE,
            border_radius=14,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            padding=ft.Padding.all(16),
            content=ft.Column([
                _section_header("COHORT PROGRESS TIER DISTRIBUTION", "Pedagogical breakdown across mastery milestones"),
                ft.Container(height=8),
                # Explanatory diagnosis pill
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                    border_radius=8,
                    bgcolor=diag_bg,
                    content=ft.Row([
                        ft.Icon(ft.Icons.LIGHTBULB_ROUNDED, size=16, color=diag_color),
                        ft.Text(diagnosis_text, size=11, weight=ft.FontWeight.W_500, color=diag_color, expand=True),
                    ], spacing=8),
                ),
                ft.Container(height=12),
                ft.Column(tier_rows, spacing=0),
            ], spacing=4),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # EXPLANATORY CHART 2: RETENTION & AT-RISK RADAR
    # ─────────────────────────────────────────────────────────────────────────
    def build_retention_card(students_list: list):
        total = max(len(students_list), 1)
        active_cnt = sum(1 for s in students_list if float(s.get("progress", 0) or 0) > 0.1)
        stalled_cnt = sum(1 for s in students_list if float(s.get("progress", 0) or 0) < 0.1)
        grad_cnt = sum(1 for s in students_list if float(s.get("progress", 0) or 0) >= 99.9)

        active_pct = int((active_cnt / total) * 100)
        stalled_pct = int((stalled_cnt / total) * 100)
        grad_pct = int((grad_cnt / total) * 100)

        def metric_item(label, value, sub, color, icon):
            return ft.Container(
                padding=12,
                border_radius=10,
                bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                expand=True,
                content=ft.Column([
                    ft.Row([
                        ft.Icon(icon, size=16, color=color),
                        ft.Text(label, size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], spacing=6),
                    ft.Text(str(value), size=20, weight=ft.FontWeight.BOLD, color=color),
                    ft.Text(sub, size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                ], spacing=2),
            )

        return ft.Container(
            bgcolor=ft.Colors.SURFACE,
            border_radius=14,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            padding=ft.Padding.all(16),
            content=ft.Column([
                _section_header("COHORT RETENTION & COMPLETION HEALTH", "Engagement velocity and attrition diagnostics"),
                ft.Container(height=8),
                ft.Row([
                    metric_item("Active", f"{active_pct}%", f"{active_cnt} in motion", ft.Colors.BLUE_600, ft.Icons.DIRECTIONS_RUN_ROUNDED),
                    metric_item("Graduated", f"{grad_pct}%", f"{grad_cnt} completed", ft.Colors.GREEN_600, ft.Icons.SCHOOL_ROUNDED),
                    metric_item("At Risk", f"{stalled_pct}%", f"{stalled_cnt} unstarted", ft.Colors.AMBER_600, ft.Icons.WARNING_AMBER_ROUNDED),
                ], spacing=10),
                ft.Container(height=10),
                ft.Text(
                    "Recommendation: Instructors can message learners directly from the Student Roster tab to re-engage inactive students or guide them through challenging lessons.",
                    size=11,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
            ], spacing=4),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # EXPLANATORY CHART 3: MODULE PROGRESSION & BOTTLENECK ANALYSIS
    # ─────────────────────────────────────────────────────────────────────────
    def build_module_analytics_card(modules: list, students_list: list):
        if not modules:
            return ft.Container(
                bgcolor=ft.Colors.SURFACE,
                border_radius=14,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                padding=24,
                alignment=ft.Alignment.CENTER,
                content=ft.Column([
                    ft.Icon(ft.Icons.SCHOOL_OUTLINED, size=36, color=ft.Colors.with_opacity(0.3, ft.Colors.ON_SURFACE)),
                    ft.Text("No modules configured in curriculum yet.", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
            )

        total_students = max(len(students_list), 1)
        total_modules = len(modules)

        # Estimate module completion by progress thresholds
        # e.g. for module i of N: threshold = (i+1)/N * 100
        module_rows = []
        for i, mod in enumerate(modules):
            m_title = mod.get("title") or f"Module {i+1}"
            lessons = mod.get("lessons", []) or []
            lesson_cnt = len(lessons)
            
            # Simulated module completion threshold
            m_thresh = ((i + 1) / total_modules) * 100.0
            completed_mod = sum(1 for s in students_list if float(s.get("progress", 0) or 0) >= m_thresh)
            pct_mod = (completed_mod / total_students) * 100

            # Bottleneck indicator
            is_steepest = (i > 0 and pct_mod < 40)

            mod_color = ft.Colors.GREEN_600 if pct_mod >= 70 else (ft.Colors.BLUE_600 if pct_mod >= 30 else ft.Colors.AMBER_600)

            module_rows.append(
                ft.Container(
                    margin=ft.Margin.only(bottom=10),
                    padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                    content=ft.Column([
                        ft.Row([
                            ft.Row([
                                ft.Container(
                                    width=22, height=22, border_radius=11,
                                    bgcolor=ft.Colors.with_opacity(0.12, mod_color),
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.Text(str(i + 1), size=11, weight=ft.FontWeight.BOLD, color=mod_color),
                                ),
                                ft.Text(m_title, size=13, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                            ], spacing=8),
                            ft.Text(f"{lesson_cnt} lessons", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Container(height=4),
                        # Progress Bar
                        ft.Row([
                            ft.Container(
                                height=6,
                                border_radius=3,
                                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                                expand=True,
                                content=ft.Row([
                                    ft.Container(
                                        height=6,
                                        border_radius=3,
                                        bgcolor=mod_color,
                                        expand=int(pct_mod) if pct_mod > 0 else 0,
                                    ) if pct_mod > 0 else ft.Container(),
                                    ft.Container(
                                        height=6,
                                        expand=int(100 - pct_mod) if pct_mod < 100 else 0,
                                    ) if pct_mod < 100 else ft.Container(),
                                ], spacing=0),
                            ),
                            ft.Text(f"{int(pct_mod)}% completion", size=10, weight=ft.FontWeight.BOLD, color=mod_color),
                        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.Text("Critical gateway milestone" if is_steepest else f"Core curriculum topic", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], spacing=2),
                )
            )

        return ft.Container(
            bgcolor=ft.Colors.SURFACE,
            border_radius=14,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            padding=ft.Padding.all(16),
            content=ft.Column([
                _section_header("CURRICULUM MODULE PROGRESSION", f"{len(modules)} modules sequenced with lesson completion rates"),
                ft.Container(height=8),
                ft.Column(module_rows, spacing=0),
            ], spacing=4),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # EXPLANATORY CHART 4: WEEKLY ACTIVITY & ENGAGEMENT VELOCITY
    # ─────────────────────────────────────────────────────────────────────────
    def build_activity_chart(data: list):
        if not data:
            return ft.Container(
                bgcolor=ft.Colors.SURFACE,
                border_radius=14,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                padding=24,
                alignment=ft.Alignment.CENTER,
                content=ft.Column([
                    ft.Icon(ft.Icons.QUERY_STATS_ROUNDED, size=36, color=ft.Colors.with_opacity(0.3, ft.Colors.ON_SURFACE)),
                    ft.Text("No engagement telemetry recorded yet", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
            )

        max_val = max((d.get("participations", 0) for d in data), default=0)
        max_val = max(max_val, 1)
        max_h = 75

        bars = []
        for i, item in enumerate(data):
            week_label = str(item.get("week", f"W{i+1}"))
            val = float(item.get("participations", 0))
            views = float(item.get("views", 0))
            ratio = val / max_val
            bar_h = max(10, int(max_h * ratio))
            is_last = i == len(data) - 1

            bar_color = theme_color if is_last else ft.Colors.with_opacity(0.6, theme_color)

            bars.append(
                ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=6,
                    controls=[
                        ft.Container(
                            width=26,
                            height=bar_h,
                            border_radius=ft.BorderRadius.only(top_left=6, top_right=6),
                            gradient=ft.LinearGradient(
                                begin=ft.Alignment(0, -1),
                                end=ft.Alignment(0, 1),
                                colors=[bar_color, ft.Colors.with_opacity(0.7, bar_color)],
                            ),
                            tooltip=f"{week_label}: {int(val)} participations, {int(views)} views",
                        ),
                        ft.Text(week_label, size=10, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE_VARIANT),
                    ],
                )
            )

        total_part = sum(d.get("participations", 0) for d in data)
        total_views = sum(d.get("views", 0) for d in data)

        return ft.Container(
            bgcolor=ft.Colors.SURFACE,
            border_radius=14,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            padding=ft.Padding.all(16),
            content=ft.Column([
                ft.Row([
                    _section_header("WEEKLY ENGAGEMENT TELEMETRY", f"{total_part} lesson participations across cohorts"),
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                        border_radius=8,
                        bgcolor=ft.Colors.with_opacity(0.08, theme_color),
                        content=ft.Text("Velocity Trend", size=10, weight=ft.FontWeight.BOLD, color=theme_color),
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Container(height=12),
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_AROUND,
                    vertical_alignment=ft.CrossAxisAlignment.END,
                    controls=bars,
                ),
                ft.Container(height=10),
                ft.Row([
                    ft.Text(f"Total Views: {total_views}", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text(f"Participations: {total_part}", size=11, weight=ft.FontWeight.BOLD, color=theme_color),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ], spacing=4),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # MOBILE-RESPONSIVE STUDENT CARD (NEVER SHRINKS / NEVER CRUNCHES)
    # ─────────────────────────────────────────────────────────────────────────
    def build_student_card(student: dict):
        first = (student.get("first_name") or "").strip()
        last = (student.get("last_name") or "").strip()
        email = (student.get("email") or "").strip()
        user_id = student.get("id") or student.get("student_id") or ""
        full_name = f"{first} {last}".strip().title() or "Academy Student"

        initials = f"{first[0] if first else '?'}{last[0] if last else ''}".upper()

        raw_progress = student.get("progress", 0.0) or 0.0
        try:
            progress_val = float(raw_progress)
        except (TypeError, ValueError):
            progress_val = 0.0
        progress_val = max(0.0, min(100.0, progress_val))
        progress_ratio = progress_val / 100.0

        prog_color = _progress_color(progress_ratio)

        async def _message(e, uid=user_id):
            if uid:
                result = await start_direct_message(token, str(uid))
                if result and "error" in result:
                    print(f"DM create failed for {uid}: {result}")
            page.go("/nu-chat")

        return ft.Container(
            padding=ft.Padding.all(12),
            margin=ft.Margin.only(bottom=8),
            border_radius=12,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
            bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
            content=ft.Column([
                # Top row: Avatar + Name/Email + Action buttons
                ft.Row([
                    ft.Row([
                        ft.CircleAvatar(
                            content=ft.Text(initials, size=12, weight=ft.FontWeight.BOLD),
                            bgcolor=ft.Colors.with_opacity(0.12, theme_color),
                            color=theme_color,
                            radius=18,
                        ),
                        ft.Column([
                            ft.Text(full_name, size=13, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(email, size=11, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ], spacing=2, expand=True),
                    ], spacing=10, expand=True),
                    ft.Row([
                        ft.IconButton(
                            ft.Icons.PERSON_OUTLINE_ROUNDED,
                            icon_size=17,
                            icon_color=ft.Colors.ON_SURFACE_VARIANT,
                            tooltip="View Profile",
                            on_click=lambda _, uid=user_id: page.go(f"/member/{uid}") if uid else None,
                        ),
                        ft.IconButton(
                            ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED,
                            icon_size=17,
                            icon_color=theme_color,
                            tooltip=f"Direct Message {first or 'Student'}",
                            on_click=lambda e, uid=user_id: page.run_task(_message, e, uid),
                        ),
                    ], spacing=0),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(height=6),
                # Full-width Progress bar with percentage pill (immune to shrinking)
                ft.Row([
                    ft.Container(
                        height=6,
                        border_radius=3,
                        bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                        expand=True,
                        content=ft.ProgressBar(value=progress_ratio, color=prog_color, bgcolor=ft.Colors.TRANSPARENT),
                    ),
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                        border_radius=6,
                        bgcolor=ft.Colors.with_opacity(0.1, prog_color),
                        content=ft.Text(f"{int(progress_val)}%", size=10, weight=ft.FontWeight.BOLD, color=prog_color),
                    ),
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ], spacing=0),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # MAIN LAYOUT BUILDER (SEGMENTED TABS & ZERO CLUTTER)
    # ─────────────────────────────────────────────────────────────────────────
    def build_main_layout():
        title = course_data.get("name", "Untitled Course")
        desc = course_data.get("description", "Academy Course")
        is_public_val = str(course_data.get("public", "false")).lower()
        is_supervised = course_data.get("supervised", False)
        category = (course_data.get("category") or {}).get("name", "General") \
            if isinstance(course_data.get("category"), dict) else "General"

        total_students = len(students)
        modules = curriculum.get("modules", []) if isinstance(curriculum, dict) else []
        module_count = len(modules)
        lesson_count = sum(len(m.get("lessons", [])) for m in modules) if modules else 0

        # Metrics calculation
        prog_values = []
        completed_cnt = 0
        in_prog_cnt = 0
        not_started_cnt = 0

        for s in students:
            p = float(s.get("progress", 0.0) or 0.0)
            prog_values.append(p)
            if p >= 99.9:
                completed_cnt += 1
            elif p > 0.1:
                in_prog_cnt += 1
            else:
                not_started_cnt += 1

        avg_prog_num = (sum(prog_values) / len(prog_values)) if prog_values else 0.0
        avg_prog_str = f"{int(avg_prog_num)}%" if prog_values else "0%"

        backend_comp_rate = completion_stats.get("completion_rate")
        if backend_comp_rate is not None:
            comp_rate_pct = int(float(backend_comp_rate) * 100)
        else:
            comp_rate_pct = int((completed_cnt / max(total_students, 1)) * 100)

        certs_issued = certificates_data.get("total_issued", 0)

        # Status badge
        if is_public_val == "true":
            status_badge = _pill("PUBLIC", ft.Colors.GREEN_700, ft.Colors.WHITE, ft.Icons.PUBLIC_ROUNDED)
        elif is_public_val in ("organisation", "organization", "campus"):
            status_badge = _pill("CAMPUS", ft.Colors.BLUE_700, ft.Colors.WHITE, ft.Icons.SCHOOL_ROUNDED)
        else:
            status_badge = _pill("DRAFT", ft.Colors.GREY_700, ft.Colors.WHITE, ft.Icons.EDIT_NOTE_ROUNDED)

        category_badge = _pill(category, ft.Colors.with_opacity(0.12, theme_color), theme_color)
        mode_badge = _pill("Instructor-Led" if is_supervised else "Self-Paced", ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE), ft.Colors.ON_SURFACE)

        # ── HERO HEADER CARD ───────────────────────────────────────────────────
        hero_card = ft.Container(
            margin=ft.Margin.symmetric(horizontal=16, vertical=8),
            border_radius=16,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.05, ft.Colors.BLACK), offset=ft.Offset(0, 2)),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=ft.Column([
                # Top Gradient Banner
                ft.Container(
                    gradient=ft.LinearGradient(
                        begin=ft.Alignment(-1, -1),
                        end=ft.Alignment(1, 1),
                        colors=[theme_color, ft.Colors.PRIMARY],
                    ),
                    padding=ft.Padding.only(top=10, left=12, right=12, bottom=12),
                    content=ft.Row([
                        ft.Row([
                            ft.IconButton(
                                ft.Icons.ARROW_BACK_ROUNDED,
                                icon_color=ft.Colors.WHITE,
                                icon_size=18,
                                tooltip="Back to Academy",
                                on_click=_go_back,
                            ),
                            ft.Text("Course Analytics & Intelligence", size=13, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE),
                        ], spacing=4),
                        ft.Row([
                            ft.IconButton(
                                ft.Icons.EDIT_ROUNDED,
                                icon_color=ft.Colors.WHITE,
                                icon_size=17,
                                tooltip="Manage Curriculum",
                                on_click=lambda _: page.go(f"/courses/{course_id}/manage"),
                            ),
                            ft.IconButton(
                                ft.Icons.SETTINGS_OUTLINED,
                                icon_color=ft.Colors.WHITE,
                                icon_size=17,
                                tooltip="Course Settings",
                                on_click=lambda _: page.go(f"/organisations/{org_id}/courses/{course_id}/settings"),
                            ),
                            ft.IconButton(
                                ft.Icons.VISIBILITY_OUTLINED,
                                icon_color=ft.Colors.WHITE,
                                icon_size=17,
                                tooltip="View Course Engine",
                                on_click=lambda _: page.go(f"/courses/{course_id}/view"),
                            ),
                        ], spacing=2),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ),
                # Header Body
                ft.Container(
                    padding=ft.Padding.all(16),
                    content=ft.Column([
                        ft.Text(title, size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                        ft.Text(desc, size=12, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Container(height=4),
                        ft.Row([
                            status_badge,
                            category_badge,
                            mode_badge,
                            ft.Row([
                                ft.Icon(ft.Icons.SCHOOL_ROUNDED, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(f"{module_count} Modules · {lesson_count} Lessons", size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
                            ], spacing=4),
                        ], spacing=8, wrap=True),
                    ], spacing=6),
                ),
            ], spacing=0),
        )

        # ── TAB SWITCHER BUTTONS ───────────────────────────────────────────────
        def switch_tab(tab_name):
            nonlocal active_tab
            active_tab = tab_name
            tab_content_container.content = get_active_tab_content()
            for btn in tab_buttons.controls:
                is_sel = btn.data == tab_name
                btn.bgcolor = theme_color if is_sel else ft.Colors.TRANSPARENT
                if hasattr(btn, "content") and hasattr(btn.content, "controls"):
                    btn.content.controls[0].color = ft.Colors.WHITE if is_sel else ft.Colors.ON_SURFACE_VARIANT
                    btn.content.controls[1].color = ft.Colors.WHITE if is_sel else ft.Colors.ON_SURFACE
                    btn.content.controls[1].weight = ft.FontWeight.BOLD if is_sel else ft.FontWeight.NORMAL
            try:
                tab_buttons.update()
            except Exception:
                pass
            try:
                tab_content_container.update()
            except Exception:
                pass

        def tab_btn(title: str, key: str, icon):
            is_sel = (active_tab == key)
            return ft.Container(
                data=key,
                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                border_radius=10,
                bgcolor=theme_color if is_sel else ft.Colors.TRANSPARENT,
                ink=True,
                on_click=lambda _, k=key: switch_tab(k),
                content=ft.Row([
                    ft.Icon(icon, size=14, color=ft.Colors.WHITE if is_sel else ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text(title, size=12, weight=ft.FontWeight.BOLD if is_sel else ft.FontWeight.NORMAL, color=ft.Colors.WHITE if is_sel else ft.Colors.ON_SURFACE),
                ], spacing=6, tight=True),
            )

        tab_buttons = ft.Row([
            tab_btn("Cohort Performance", "performance", ft.Icons.INSIGHTS_ROUNDED),
            tab_btn("Curriculum & Engagement", "curriculum", ft.Icons.SCHOOL_ROUNDED),
            tab_btn(f"Student Roster ({total_students})", "roster", ft.Icons.PEOPLE_ROUNDED),
        ], spacing=6, scroll=ft.ScrollMode.AUTO)

        tabs_bar = ft.Container(
            padding=ft.Padding.symmetric(horizontal=16, vertical=4),
            content=tab_buttons,
        )

        # ── TAB 1: COHORT PERFORMANCE ──────────────────────────────────────────
        def build_performance_tab():
            return ft.Column([
                # Bento KPIs Row
                ft.ResponsiveRow([
                    bento_stat(
                        ft.Icons.GROUPS_ROUNDED,
                        "TOTAL ENROLLED",
                        str(total_students),
                        f"{in_prog_cnt} active learners",
                        ft.Colors.BLUE_500,
                    ),
                    bento_stat(
                        ft.Icons.CHECK_CIRCLE_ROUNDED,
                        "COMPLETION RATE",
                        f"{comp_rate_pct}%",
                        f"{completed_cnt} cohort graduates",
                        ft.Colors.GREEN_600,
                    ),
                    bento_stat(
                        ft.Icons.TRENDING_UP_ROUNDED,
                        "AVG. PROGRESS",
                        avg_prog_str,
                        f"Across {lesson_count} course lessons",
                        _progress_color(avg_prog_num / 100.0),
                    ),
                    bento_stat(
                        ft.Icons.WORKSPACE_PREMIUM_ROUNDED,
                        "CERTIFICATES",
                        str(certs_issued),
                        "Verified credentials awarded",
                        ft.Colors.AMBER_600,
                    ),
                ], spacing=12, run_spacing=12),
                ft.Container(height=12),
                # Explanatory Progress Tier Distribution
                build_tier_distribution_card(students),
                ft.Container(height=12),
                # Retention and Risk Radar
                build_retention_card(students),
            ], spacing=0)

        # ── TAB 2: CURRICULUM & ENGAGEMENT ─────────────────────────────────────
        def build_curriculum_tab():
            return ft.Column([
                # Explanatory Module Bottlenecks
                build_module_analytics_card(modules, students),
                ft.Container(height=12),
                # Weekly Telemetry Velocity
                build_activity_chart(weekly_activity),
            ], spacing=0)

        # ── TAB 3: STUDENT ROSTER (NON-BLOCKING & RESPONSIVE) ──────────────────
        def get_filtered_students():
            res = students
            if student_search_query.strip():
                q = student_search_query.strip().lower()
                res = [
                    s for s in res
                    if q in f"{s.get('first_name', '')} {s.get('last_name', '')}".lower()
                    or q in s.get("email", "").lower()
                ]

            if student_filter_status == "completed":
                res = [s for s in res if float(s.get("progress", 0.0) or 0.0) >= 99.9]
            elif student_filter_status == "in_progress":
                res = [s for s in res if 0.1 <= float(s.get("progress", 0.0) or 0.0) < 99.9]
            elif student_filter_status == "not_started":
                res = [s for s in res if float(s.get("progress", 0.0) or 0.0) < 0.1]
            return res

        def build_student_items(s_list):
            if not s_list:
                return [
                    ft.Container(
                        padding=32,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Column([
                            ft.Icon(ft.Icons.PEOPLE_OUTLINE_ROUNDED, size=36, color=ft.Colors.with_opacity(0.3, ft.Colors.ON_SURFACE)),
                            ft.Text("No learners match current filter criteria.", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                    )
                ]
            return [build_student_card(s) for s in s_list]

        roster_column = ft.Column(controls=build_student_items(get_filtered_students()), spacing=0)

        def on_student_search_change(e):
            nonlocal student_search_query
            student_search_query = e.control.value or ""
            roster_column.controls = build_student_items(get_filtered_students())
            try:
                roster_column.update()
            except Exception:
                pass

        def set_roster_filter(status_key):
            nonlocal student_filter_status
            student_filter_status = status_key
            roster_column.controls = build_student_items(get_filtered_students())
            try:
                roster_column.update()
            except Exception:
                pass
            for chip in roster_filter_chips.controls:
                is_active = chip.data == status_key
                chip.bgcolor = theme_color if is_active else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)
                chip.content.color = ft.Colors.WHITE if is_active else ft.Colors.ON_SURFACE
                chip.content.weight = ft.FontWeight.BOLD if is_active else ft.FontWeight.NORMAL
            try:
                roster_filter_chips.update()
            except Exception:
                pass

        def roster_chip(label: str, key: str):
            is_active = (student_filter_status == key)
            return ft.Container(
                data=key,
                padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                border_radius=14,
                bgcolor=theme_color if is_active else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                ink=True,
                on_click=lambda _, k=key: set_roster_filter(k),
                content=ft.Text(
                    label,
                    size=11,
                    weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.NORMAL,
                    color=ft.Colors.WHITE if is_active else ft.Colors.ON_SURFACE,
                ),
            )

        roster_filter_chips = ft.Row([
            roster_chip(f"All ({total_students})", "all"),
            roster_chip(f"Completed ({completed_cnt})", "completed"),
            roster_chip(f"In Progress ({in_prog_cnt})", "in_progress"),
            roster_chip(f"Not Started ({not_started_cnt})", "not_started"),
        ], spacing=6, scroll=ft.ScrollMode.AUTO)

        student_search_box = ft.TextField(
            hint_text="Search cohort by learner name or email…",
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            border_radius=10,
            dense=True,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            on_change=on_student_search_change,
            width=float("inf"),
        )

        def build_roster_tab():
            return ft.Container(
                bgcolor=ft.Colors.SURFACE,
                border_radius=14,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                padding=ft.Padding.all(16),
                content=ft.Column([
                    _section_header("LEARNER COHORT ROSTER", f"{total_students} students enrolled in curriculum"),
                    student_search_box,
                    roster_filter_chips,
                    ft.Container(height=4),
                    roster_column,
                ], spacing=10),
            )

        def get_active_tab_content():
            if active_tab == "curriculum":
                return build_curriculum_tab()
            elif active_tab == "roster":
                return build_roster_tab()
            return build_performance_tab()

        tab_content_container = ft.Container(
            padding=ft.Padding.symmetric(horizontal=16),
            content=get_active_tab_content(),
        )

        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                hero_card,
                tabs_bar,
                ft.Container(height=8),
                tab_content_container,
                ft.Container(height=32),
            ],
            spacing=0,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # DATA FETCHER
    # ─────────────────────────────────────────────────────────────────────────
    async def fetch_analytics_data():
        nonlocal theme_color, course_data, students, curriculum
        nonlocal completion_stats, certificates_data, weekly_activity

        try:
            (
                all_courses, roster, course_curriculum, org_data,
                comp_stats, certs, activity
            ) = await asyncio.gather(
                asyncio.wait_for(get_courses(token, params={"org": org_id}), timeout=15),
                asyncio.wait_for(get_enrolled_students(token, course_id, None), timeout=15),
                asyncio.wait_for(get_course_curriculum(token, course_id), timeout=15),
                asyncio.wait_for(get_my_organisation(token), timeout=15),
                asyncio.wait_for(get_completion_stats(token, course_id, None), timeout=15),
                asyncio.wait_for(get_certificates_issued(token, course_id, None), timeout=15),
                asyncio.wait_for(get_weekly_activity(token, course_id, None), timeout=15),
                return_exceptions=True,
            )

            # Course metadata
            if isinstance(all_courses, list):
                match = next((c for c in all_courses if str(c.get("id")) == str(course_id)), None)
                course_data = match or {}

            # Enrolled students
            if isinstance(roster, list):
                students = roster
            elif isinstance(roster, dict) and "error" not in roster:
                students = roster.get("students") or roster.get("results") or roster.get("data") or []

            # Curriculum
            if isinstance(course_curriculum, dict) and "error" not in course_curriculum:
                curriculum = course_curriculum

            # Org Theme
            if isinstance(org_data, dict):
                theme_color = org_data.get("theme_color") or ft.Colors.INDIGO_600

            # Completion Stats
            if isinstance(comp_stats, dict) and "error" not in comp_stats:
                completion_stats = comp_stats

            # Certificates
            if isinstance(certs, dict) and "error" not in certs:
                certificates_data = certs

            # Weekly Activity
            if isinstance(activity, list):
                weekly_activity = activity

            content_socket.alignment = None
            content_socket.content = build_main_layout()
            page.update()

        except asyncio.TimeoutError:
            _show_load_error("Connection timed out loading telemetry.")
        except Exception as ex:
            _show_load_error(f"Failed to load analytics: {ex}")

    page.run_task(fetch_analytics_data)

    return ft.View(
        route=f"/organisations/{org_id}/courses/{course_id}/analytics",
        padding=0,
        bottom_appbar=app_bar,
        controls=[
            content_socket,
        ],
    )