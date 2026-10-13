"""
src/components/next_best_action_card.py

Dynamic "Next-Best Action" cockpit card for Nu-Age Dashboard.
Based on the 29 September 2026 UX & Platform Implementation Blueprint:
- Displays the single most relevant learning task front and center.
- Provides immediate 1-tap continuation into active module.
- Shows offline readiness status badge (SQLite local_db).
- Offers intelligent academic fallback (diagnostic/discovery) when no courses are active.
"""

import flet as ft
from typing import List, Dict, Any, Optional
from src.local_db import is_course_downloaded


def get_next_best_action_card(
    enrolled_courses: List[Dict[str, Any]],
    page: ft.Page,
    streak: int = 0,
) -> ft.Container:
    """
    Constructs the dynamic Next-Best Action Hero Cockpit card.
    Prioritizes:
    1. Active in-progress course (0% < progress < 100%)
    2. Most recently enrolled course (progress == 0%)
    3. Academic starter launchpad (diagnostic / discover) if empty or finished.
    """
    is_dark = getattr(page, "theme_mode", None) == ft.ThemeMode.DARK
    card_bg = ft.Colors.SURFACE if is_dark else "#FFFFFF"
    border_clr = ft.Colors.with_opacity(0.12, ft.Colors.WHITE) if is_dark else ft.Colors.GREY_200

    # 1. Determine active course
    active_course: Optional[Dict[str, Any]] = None
    
    # Priority 1: In-progress courses (progress between 1 and 99)
    for c in enrolled_courses:
        prog = float(c.get("progress", 0.0) or 0.0)
        if 0 < prog < 100:
            active_course = c
            break

    # Priority 2: Unstarted enrolled courses (progress == 0)
    if not active_course and enrolled_courses:
        for c in enrolled_courses:
            if float(c.get("progress", 0.0) or 0.0) < 100:
                active_course = c
                break

    # ── CASE A: Active Course In-Progress ─────────────────────────────────────
    if active_course:
        c_id = str(active_course.get("id", ""))
        c_name = active_course.get("name") or active_course.get("title") or "Current Course"
        c_prog = max(0.0, min(float(active_course.get("progress", 0.0) or 0.0), 100.0))
        is_downloaded = is_course_downloaded(c_id, page)

        eyebrow_pills = [
            ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=12, color=ft.Colors.PRIMARY),
                        ft.Text("NEXT BEST ACTION", size=10, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY),
                    ],
                    spacing=4,
                    tight=True,
                ),
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                border_radius=ft.BorderRadius.all(6),
            )
        ]

        if is_downloaded:
            eyebrow_pills.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.OFFLINE_PIN_ROUNDED, size=12, color=ft.Colors.GREEN_400),
                            ft.Text("Downloaded for offline study", size=10, weight=ft.FontWeight.W_600, color=ft.Colors.GREEN_400),
                        ],
                        spacing=4,
                        tight=True,
                    ),
                    bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.GREEN_400),
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=ft.BorderRadius.all(6),
                )
            )

        resume_btn = ft.FilledButton(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, size=18, color=ft.Colors.ON_PRIMARY),
                    ft.Text("Resume Learning", size=13, weight=ft.FontWeight.W_700, color=ft.Colors.ON_PRIMARY),
                ],
                tight=True,
                spacing=6,
            ),
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.PRIMARY,
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=ft.Padding.symmetric(horizontal=16, vertical=10),
            ),
            on_click=lambda _: page.go(f"/courses/{c_id}/view"),
        )

        return ft.Container(
            bgcolor=card_bg,
            border_radius=ft.BorderRadius.all(18),
            border=ft.Border.all(1.2, ft.Colors.with_opacity(0.18, ft.Colors.PRIMARY)),
            padding=ft.Padding.all(18),
            shadow=ft.BoxShadow(
                blur_radius=14,
                color=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                offset=ft.Offset(0, 4),
            ),
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Row(eyebrow_pills, spacing=8, wrap=True),
                    ft.Column(
                        spacing=3,
                        controls=[
                            ft.Text(
                                c_name,
                                size=17,
                                weight=ft.FontWeight.W_800,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                color=ft.Colors.ON_SURFACE,
                            ),
                            ft.Text(
                                "Pick up right where you left off and keep your momentum going.",
                                size=12,
                                color=ft.Colors.GREY_500,
                            ),
                        ],
                    ),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Column(
                                expand=True,
                                spacing=4,
                                controls=[
                                    ft.ProgressBar(
                                        value=c_prog / 100.0,
                                        color=ft.Colors.PRIMARY,
                                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                                        height=7,
                                        border_radius=ft.BorderRadius.all(3.5),
                                    ),
                                    ft.Row(
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        controls=[
                                            ft.Text(f"{int(c_prog)}% Completed", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY),
                                            ft.Text(f"🔥 {streak}d Streak" if streak > 0 else "Daily Pace", size=11, color=ft.Colors.GREY_500),
                                        ],
                                    ),
                                ],
                            ),
                            ft.Container(width=16),
                            resume_btn,
                        ],
                    ),
                ],
            ),
        )

    # ── CASE B: All Completed or Empty — Starter Academic Launchpad ───────────
    all_completed = bool(enrolled_courses and all(float(c.get("progress", 0.0) or 0.0) >= 100 for c in enrolled_courses))
    
    launch_title = "All caught up! Time to level up." if all_completed else "Start your learning sprint today."
    launch_desc = (
        "You've completed all enrolled courses! Test your recall with a quiz or begin a new specialization."
        if all_completed
        else "Take a 5-minute diagnostic quiz or explore starter courses to get your first academic milestone."
    )

    return ft.Container(
        bgcolor=card_bg,
        border_radius=ft.BorderRadius.all(18),
        border=ft.Border.all(1.2, ft.Colors.with_opacity(0.25, ft.Colors.AMBER_400 if is_dark else ft.Colors.INDIGO_400)),
        padding=ft.Padding.all(18),
        shadow=ft.BoxShadow(
            blur_radius=12,
            color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK),
            offset=ft.Offset(0, 4),
        ),
        content=ft.Column(
            spacing=12,
            controls=[
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Row(
                                [
                                    ft.Icon(ft.Icons.ROCKET_LAUNCH_ROUNDED, size=13, color=ft.Colors.AMBER_500 if is_dark else ft.Colors.INDIGO_600),
                                    ft.Text("ACADEMIC LAUNCHPAD", size=10, weight=ft.FontWeight.W_800, color=ft.Colors.AMBER_500 if is_dark else ft.Colors.INDIGO_600),
                                ],
                                spacing=4,
                                tight=True,
                            ),
                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_500 if is_dark else ft.Colors.INDIGO_600),
                            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                            border_radius=ft.BorderRadius.all(6),
                        ),
                    ],
                ),
                ft.Column(
                    spacing=3,
                    controls=[
                        ft.Text(
                            launch_title,
                            size=17,
                            weight=ft.FontWeight.W_800,
                            color=ft.Colors.ON_SURFACE,
                        ),
                        ft.Text(
                            launch_desc,
                            size=12,
                            color=ft.Colors.GREY_500,
                        ),
                    ],
                ),
                ft.Row(
                    spacing=10,
                    wrap=True,
                    controls=[
                        ft.FilledButton(
                            content=ft.Row(
                                [
                                    ft.Icon(ft.Icons.QUIZ_ROUNDED, size=16),
                                    ft.Text("Take Quick Diagnostic", size=12.5, weight=ft.FontWeight.W_700),
                                ],
                                tight=True,
                                spacing=6,
                            ),
                            style=ft.ButtonStyle(
                                bgcolor=ft.Colors.PRIMARY,
                                color=ft.Colors.ON_PRIMARY,
                                shape=ft.RoundedRectangleBorder(radius=10),
                                padding=ft.Padding.symmetric(horizontal=14, vertical=8),
                            ),
                            on_click=lambda _: page.go("/self-study"),
                        ),
                        ft.OutlinedButton(
                            content=ft.Row(
                                [
                                    ft.Icon(ft.Icons.EXPLORE_ROUNDED, size=16),
                                    ft.Text("Explore Courses", size=12.5, weight=ft.FontWeight.W_700),
                                ],
                                tight=True,
                                spacing=6,
                            ),
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=10),
                                padding=ft.Padding.symmetric(horizontal=14, vertical=8),
                            ),
                            on_click=lambda _: page.go("/courses"),
                        ),
                    ],
                ),
            ],
        ),
    )
