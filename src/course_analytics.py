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
# WHAT IS REAL vs MOCK
# ═══════════════════════════════════════════════════════════════════════════════
#
#  ✅ REAL:
#    - Course metadata           → get_courses(token, params={"org": org_id})
#    - Enrolled students + progress → get_enrolled_students(token, course_id, None)
#      Each row expected shape (from Enrollment + User join on the backend):
#        { "id", "first_name", "last_name", "email", "progress": 0.0–1.0,
#          "final_score", "enrolled_at", "completed_at" }
#    - Module / lesson counts    → get_course_curriculum(token, course_id)
#    - Org theme colour          → get_my_organisation(token)
#    - Message student           → start_direct_message(token, student_id)
#      Always routes to /nu-chat; channel is created server-side regardless.
#
#  🟡 MOCK (endpoint not in supplied files):
#    - Completion Rate    → GET /courses/{id}/completion-stats
#    - Certificates Issued→ GET /courses/{id}/certificates
#    - Weekly Activity    → GET /courses/{id}/activity?period=weekly
#      Shape: [{"week": "W23", "views": int, "participations": int}]
#
# ═══════════════════════════════════════════════════════════════════════════════


def _pill(label: str, bg, fg) -> ft.Container:
    return ft.Container(
        padding=ft.padding.symmetric(horizontal=8, vertical=3),
        bgcolor=bg,
        border_radius=10,
        content=ft.Text(label, size=10, color=fg, weight=ft.FontWeight.W_600),
    )


def _section_label(text: str) -> ft.Text:
    return ft.Text(text, size=11, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_500)


def _progress_color(pct: float):
    if pct >= 0.75:
        return ft.Colors.GREEN_600
    if pct >= 0.4:
        return ft.Colors.AMBER_700
    return ft.Colors.RED_400


# ─────────────────────────────────────────────────────────────────────────────
# VIEW
# ─────────────────────────────────────────────────────────────────────────────
async def course_analytics_view(page: ft.Page, org_id: str, course_id: str):
    app_bar = get_bottom_appbar(page)
    token   = await page.shared_preferences.get("auth_token")

    def _go_back(e):
        if len(page.views) > 1:
            page.views.pop()
        page.update()

    theme_color  = ft.Colors.PRIMARY
    course_data: dict = {}
    students:    list = []   # each item is enrollment+user dict from the backend
    curriculum:  dict = {}
    
    # NEW LIVE DATA STATE
    completion_stats: dict = {}
    certificates_data: dict = {}
    weekly_activity: list = []
    content_socket = ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.ProgressRing(color=ft.Colors.PRIMARY, width=36, height=36),
                ft.Text("Loading analytics…", size=13, color=ft.Colors.GREY_500),
            ],
        ),
    )

    # ─────────────────────────────────────────────────────────────────────────
    # STAT CARD — real data
    # ─────────────────────────────────────────────────────────────────────────
    def stat_card(icon, value, label, color, col=None):
        return ft.Container(
            col=col or {"xs": 6, "sm": 4},
            bgcolor=ft.Colors.SURFACE,
            border_radius=14,
            border=ft.border.all(1, ft.Colors.GREY_200),
            padding=ft.padding.symmetric(horizontal=14, vertical=14),
            shadow=ft.BoxShadow(
                blur_radius=8,
                color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK),
                offset=ft.Offset(0, 2),
            ),
            content=ft.Row(
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(
                        width=40, height=40,
                        border_radius=12,
                        bgcolor=ft.Colors.with_opacity(0.12, color),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(icon, size=20, color=color),
                    ),
                    ft.Column(
                        spacing=2,
                        expand=True,
                        controls=[
                            ft.Text(str(value), size=22, weight=ft.FontWeight.W_700,
                                    color=ft.Colors.ON_SURFACE),
                            ft.Text(label, size=11, color=ft.Colors.GREY_500),
                        ],
                    ),
                ],
            ),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # INSIGHT CARD — mock, no invented numbers
    # ─────────────────────────────────────────────────────────────────────────
    # ─────────────────────────────────────────────────────────────────────────
    # INSIGHT CARD (LIVE)
    # ─────────────────────────────────────────────────────────────────────────
    def insight_card(icon, label, value_str: str, col=None):
        return ft.Container(
            col=col or {"xs": 12, "sm": 6},
            bgcolor=ft.Colors.SURFACE,
            border_radius=14,
            border=ft.border.all(1, ft.Colors.GREY_200),
            padding=ft.padding.symmetric(horizontal=14, vertical=14),
            content=ft.Row(
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(
                        width=40, height=40,
                        border_radius=12,
                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.GREEN_600),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(icon, size=20, color=ft.Colors.GREEN_600),
                    ),
                    ft.Column(
                        spacing=3,
                        expand=True,
                        controls=[
                            ft.Text(label, size=13, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_600),
                            ft.Text(value_str, size=18, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                        ],
                    ),
                    ft.Container(
                        padding=ft.padding.symmetric(horizontal=8, vertical=4),
                        bgcolor=ft.Colors.GREEN_50,
                        border_radius=8,
                        content=ft.Text("Live", size=10, color=ft.Colors.GREEN_700, weight=ft.FontWeight.W_600),
                    ),
                ],
            ),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # WEEKLY ACTIVITY PANEL (LIVE)
    # ─────────────────────────────────────────────────────────────────────────
    def activity_panel(data: list):
        if not data:
            return ft.Container(
                bgcolor=ft.Colors.SURFACE, border_radius=14, border=ft.border.all(1, ft.Colors.GREY_200),
                padding=14, content=ft.Text("No activity data available yet.", size=12, color=ft.Colors.GREY_500)
            )

        # Base scale on participations; ensure max_val isn't 0 to avoid division errors
        max_val = max((d.get("participations", 0) for d in data), default=0)
        max_val = max(max_val, 1) 
        
        max_h = 56
        bars = []
        for i, item in enumerate(data):
            week_label = str(item.get("week", f"W{i+1}"))
            val = float(item.get("participations", 0))
            ratio = val / max_val
            bar_h = max(8, int(max_h * ratio))
            is_last = i == len(data) - 1

            bars.append(
                ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                    controls=[
                        ft.Container(
                            width=22, height=bar_h,
                            border_radius=ft.BorderRadius.only(top_left=5, top_right=5),
                            bgcolor=ft.Colors.with_opacity(0.85 if is_last else 0.35, theme_color),
                            tooltip=f"{week_label}: {int(val)} participations"
                        ),
                        ft.Text(week_label, size=9, color=ft.Colors.GREY_400),
                    ],
                )
            )

        return ft.Container(
            bgcolor=ft.Colors.SURFACE,
            border_radius=14,
            border=ft.border.all(1, ft.Colors.GREY_200),
            padding=ft.padding.all(14),
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Text("Weekly Activity (Participations)", size=13, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.END,
                        controls=bars,
                    ),
                ],
            ),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # STUDENT TABLE ROW
    # ✅ REAL: name, email, progress (from Enrollment.progress)
    # ✅ REAL: message button → start_direct_message, then go to /nu-chat
    # ─────────────────────────────────────────────────────────────────────────
    # ─────────────────────────────────────────────────────────────────────────
    # STUDENT TABLE ROW
    # ─────────────────────────────────────────────────────────────────────────
    def student_table_row(student: dict, index: int):
        first     = (student.get("first_name") or "").strip()
        last      = (student.get("last_name") or "").strip()
        email     = (student.get("email") or "").strip()
        user_id   = student.get("id") or student.get("student_id") or ""
        full_name = f"{first} {last}".strip().title() or "Unnamed Student"

        init_chars = [c for c in [first[:1], last[:1]] if c.isalpha()]
        initials   = "".join(init_chars).upper() or full_name[:2].upper()

        # Progress is given as a float out of 100 (e.g., 98.5)
        raw_progress = student.get("progress", 0.0) or 0.0
        try:
            progress_val = float(raw_progress)
        except (TypeError, ValueError):
            progress_val = 0.0
            
        # Clamp between 0 and 100
        progress_val = max(0.0, min(100.0, progress_val))
        
        # Convert to 0.0 - 1.0 ratio strictly for drawing the UI bar and color
        progress_ratio = progress_val / 100.0
        
        display_pct  = f"{int(progress_val)}%"
        prog_color   = _progress_color(progress_ratio)
        is_even      = index % 2 == 0

        async def _message(e, uid=user_id):
            result = await start_direct_message(token, str(uid))
            if result and "error" in result:
                print(f"DM create failed for {uid}: {result}")
            page.go("/nu-chat")

        return ft.Container(
            bgcolor=ft.Colors.GREY_50 if is_even else ft.Colors.SURFACE,
            padding=ft.padding.symmetric(horizontal=12, vertical=10),
            border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.GREY_100)),
            content=ft.Row(
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(
                        width=36, height=36,
                        border_radius=18,
                        bgcolor=ft.Colors.with_opacity(0.14, theme_color),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Text(initials, size=12, weight=ft.FontWeight.W_700, color=theme_color),
                    ),
                    ft.Column(
                        spacing=1,
                        expand=True,
                        controls=[
                            ft.Text(full_name, size=13, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(email, size=11, color=ft.Colors.GREY_500, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ],
                    ),
                    ft.Column(
                        spacing=3,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Text(display_pct, size=12, weight=ft.FontWeight.W_700, color=prog_color),
                            ft.Container(
                                width=48, height=4, border_radius=2, bgcolor=ft.Colors.GREY_200,
                                content=ft.Container(
                                    width=48 * progress_ratio, # Draw the bar using the ratio
                                    height=4, border_radius=2, bgcolor=prog_color,
                                ),
                            ),
                        ],
                    ),
                    ft.IconButton(
                        ft.Icons.SEND_ROUNDED, icon_size=16, icon_color=theme_color,
                        tooltip=f"Message {full_name}",
                        on_click=lambda e, uid=user_id: page.run_task(_message, e, uid),
                    ),
                ],
            ),
        )
    # ─────────────────────────────────────────────────────────────────────────
    # AVG PROGRESS STAT — computed from real enrollment progress values
    # ─────────────────────────────────────────────────────────────────────────
    # ─────────────────────────────────────────────────────────────────────────
    # AVG PROGRESS STAT
    # ─────────────────────────────────────────────────────────────────────────
    def avg_progress_display(student_list: list) -> str:
        if not student_list:
            return "—"
        values = []
        for s in student_list:
            try:
                # Values are 0-100 floats
                values.append(float(s.get("progress", 0.0) or 0.0))
            except (TypeError, ValueError):
                values.append(0.0)
        avg = sum(values) / len(values)
        
        # Simply convert the average directly to an int
        return f"{int(avg)}%"

    # ─────────────────────────────────────────────────────────────────────────
    # MAIN LAYOUT
    # ─────────────────────────────────────────────────────────────────────────
    def build_main_layout():
        title         = course_data.get("name", "Untitled Course")
        is_public     = course_data.get("public", False)
        is_supervised = course_data.get("supervised", False)
        category      = (course_data.get("category") or {}).get("name", "Uncategorized") \
                        if isinstance(course_data.get("category"), dict) else "Uncategorized"

        total_students = len(students)
        modules        = curriculum.get("modules", []) if isinstance(curriculum, dict) else []
        module_count   = len(modules)
        lesson_count   = sum(len(m.get("lessons", [])) for m in modules) if modules else 0
        avg_prog       = avg_progress_display(students)

        status_badge   = _pill(
            "Public" if is_public else "Draft",
            ft.Colors.GREEN_50 if is_public else ft.Colors.GREY_100,
            ft.Colors.GREEN_700 if is_public else ft.Colors.GREY_600,
        )
        type_badge     = _pill(
            "Instructor-Led" if is_supervised else "Automated",
            ft.Colors.BLUE_50 if is_supervised else ft.Colors.PURPLE_50,
            ft.Colors.BLUE_700 if is_supervised else ft.Colors.PURPLE_700,
        )
        category_badge = _pill(category, ft.Colors.GREY_100, ft.Colors.GREY_600)

        student_table = (
            ft.Column(
                spacing=0,
                controls=[
                    # Table header
                    ft.Container(
                        bgcolor=ft.Colors.GREY_50,
                        padding=ft.padding.symmetric(horizontal=12, vertical=8),
                        border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.GREY_200)),
                        content=ft.Row(
                            controls=[
                                ft.Text("Student", size=10, weight=ft.FontWeight.W_700,
                                        color=ft.Colors.GREY_500, expand=True),
                                ft.Text("Progress", size=10, weight=ft.FontWeight.W_700,
                                        color=ft.Colors.GREY_500),
                                ft.Container(width=44),
                            ],
                        ),
                    ),
                    *[student_table_row(s, i) for i, s in enumerate(students)],
                ],
            )
            if students
            else ft.Container(
                padding=ft.padding.symmetric(vertical=36),
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                    controls=[
                        ft.Icon(ft.Icons.PEOPLE_OUTLINE_ROUNDED,
                                size=38, color=ft.Colors.GREY_300),
                        ft.Text("No students enrolled yet", size=13,
                                weight=ft.FontWeight.W_600, color=ft.Colors.GREY_500),
                    ],
                ),
            )
        )

        return ft.Column(
            expand=True,
            controls=[
                # ── Header ────────────────────────────────────────────────────
                ft.Container(
                    bgcolor=theme_color,
                    border_radius=ft.BorderRadius.only(bottom_left=20, bottom_right=20),
                    padding=ft.padding.only(left=8, right=16, top=8, bottom=16),
                    content=ft.Column(
                        spacing=6,
                        controls=[
                            # Back + title on one tight row
                            ft.Row(
                                spacing=4,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.IconButton(
                                        ft.Icons.ARROW_BACK_ROUNDED,
                                        icon_color=ft.Colors.ON_PRIMARY,
                                        icon_size=20,
                                        on_click=_go_back,
                                    ),
                                    ft.Text(
                                        title,
                                        size=16,
                                        weight=ft.FontWeight.W_700,
                                        color=ft.Colors.ON_PRIMARY,
                                        expand=True,
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                ],
                            ),
                            # Tags flush below
                            ft.Container(
                                padding=ft.padding.only(left=12),
                                content=ft.Row(
                                    spacing=6,
                                    wrap=True,
                                    controls=[status_badge, type_badge, category_badge],
                                ),
                            ),
                        ],
                    ),
                ),

                # ── Scrollable body ────────────────────────────────────────────
                ft.Container(
                    expand=True,
                    padding=ft.padding.symmetric(horizontal=16, vertical=14),
                    content=ft.Column(
                        expand=True,
                        scroll=ft.ScrollMode.AUTO,
                        spacing=16,
                        controls=[

                            # ── Real overview stats ────────────────────────────
                            _section_label("OVERVIEW"),
                            ft.ResponsiveRow(
                                run_spacing=10, spacing=10,
                                controls=[
                                    stat_card(ft.Icons.PEOPLE_ALT_ROUNDED,
                                              total_students, "Enrolled",
                                              ft.Colors.BLUE_500),
                                    stat_card(ft.Icons.VIEW_MODULE_ROUNDED,
                                              module_count, "Modules",
                                              ft.Colors.PURPLE_500),
                                    stat_card(ft.Icons.PLAY_LESSON_ROUNDED,
                                              lesson_count, "Lessons",
                                              theme_color),
                                    # ✅ REAL — computed from Enrollment.progress
                                    stat_card(ft.Icons.TRENDING_UP_ROUNDED,
                                              avg_prog, "Avg. Progress",
                                              ft.Colors.GREEN_600),
                                ],
                            ),

                            # ── Real insight cards ─────────────────────────────
                            _section_label("INSIGHTS"),
                            ft.ResponsiveRow(
                                run_spacing=10, spacing=10,
                                controls=[
                                    insight_card(
                                        ft.Icons.CHECK_CIRCLE_ROUNDED, 
                                        "Completion Rate", 
                                        f"{int(completion_stats.get('completion_rate', 0.0) * 100)}%"
                                    ),
                                    insight_card(
                                        ft.Icons.WORKSPACE_PREMIUM_ROUNDED, 
                                        "Certificates Issued", 
                                        str(certificates_data.get("total_issued", 0))
                                    ),
                                ],
                            ),

                            # ── Weekly activity (Real) ─────────────────────────
                            _section_label("ACTIVITY"),
                            activity_panel(weekly_activity),

                            # ── Student roster ─────────────────────────────────
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    _section_label(f"STUDENTS ({total_students})"),
                                    ft.Text("Progress is live",
                                            size=9, color=ft.Colors.GREEN_600,
                                            italic=True),
                                ],
                            ),
                            ft.Container(
                                bgcolor=ft.Colors.SURFACE,
                                border_radius=14,
                                border=ft.border.all(1, ft.Colors.GREY_200),
                                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                                content=student_table,
                            ),

                            ft.Container(height=24),
                        ],
                    ),
                ),
            ],
        )

    # ─────────────────────────────────────────────────────────────────────────
    # DATA FETCHER
    # ─────────────────────────────────────────────────────────────────────────
    # ─────────────────────────────────────────────────────────────────────────
    # DATA FETCHER (UPDATED)
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

            # Theme
            if isinstance(org_data, dict):
                theme_color = org_data.get("theme_color") or ft.Colors.PRIMARY

            # NEW: Completion Stats
            if isinstance(comp_stats, dict) and "error" not in comp_stats:
                completion_stats = comp_stats

            # NEW: Certificates
            if isinstance(certs, dict) and "error" not in certs:
                certificates_data = certs

            # NEW: Weekly Activity
            if isinstance(activity, list):
                weekly_activity = activity

            content_socket.alignment = None
            content_socket.content   = build_main_layout()
            page.update()

        except asyncio.TimeoutError:
            _show_load_error("Connection timed out.", ft.Icons.WIFI_OFF_ROUNDED, ft.Colors.ORANGE_400)
        except Exception as ex:
            _show_load_error(
                f"Failed to load analytics ({type(ex).__name__}).",
                ft.Icons.ERROR_OUTLINE_ROUNDED, ft.Colors.RED_400,
            )

    def _show_load_error(message: str, icon, color):
        content_socket.alignment = ft.Alignment.CENTER
        content_socket.content = ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            controls=[
                ft.Icon(icon, size=48, color=color),
                ft.Text("Could not load analytics", size=16,
                        weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                ft.Text(message, size=13, color=ft.Colors.GREY_500,
                        text_align=ft.TextAlign.CENTER),
                ft.Container(height=4),
                ft.ElevatedButton(
                    "Retry",
                    bgcolor=ft.Colors.PRIMARY,
                    color=ft.Colors.ON_PRIMARY,
                    height=42,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=10), elevation=0,
                    ),
                    on_click=lambda _: page.run_task(fetch_analytics_data),
                ),
            ],
        )
        page.update()

    page.run_task(fetch_analytics_data)

    return ft.View(
        route=f"/organisations/{org_id}/courses/{course_id}/analytics",
        bottom_appbar=app_bar,
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        padding=0,
        controls=[ft.SafeArea(expand=True, content=content_socket)],
    )