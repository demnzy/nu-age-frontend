import asyncio
import sqlite3
from datetime import datetime, timedelta

import flet as ft
import flet_charts as fch  # pyright: ignore[reportMissingImports]

from src.components.bottom_appbar import get_bottom_appbar
from src.components.dashboard_card import get_continue_learning_card
from src.requests.enrollments import get_enrollments
from src.utils.db_manager import get_weekly_activity
from src.requests.chats import get_all_users

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _section_label(text: str) -> ft.Text:
    return ft.Text(text, size=11, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_500)


def _card(content, padding=18) -> ft.Container:
    return ft.Container(
        bgcolor=ft.Colors.SURFACE,
        border_radius=16,
        border=ft.border.all(1, ft.Colors.GREY_200),
        padding=padding,
        shadow=ft.BoxShadow(
            blur_radius=8,
            color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK),
            offset=ft.Offset(0, 3),
        ),
        content=content,
    )


# ─────────────────────────────────────────────────────────────────────────────
# VIEW
# ─────────────────────────────────────────────────────────────────────────────
async def dashboard_view(page: ft.Page):
    app_bar = get_bottom_appbar(page)

    # ── greeting text (mutated after data loads) ──────────────────────────────
    greeting_name = ft.Text(
        "Hello, there!",
        size=21, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE,
    )
    greeting_sub = ft.Text(
        "Welcome back to your dashboard.",
        size=13, color=ft.Colors.with_opacity(0.85, ft.Colors.WHITE),
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 1. HEADER
    # ─────────────────────────────────────────────────────────────────────────
    header = ft.Container(
        gradient=ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
            colors=[ft.Colors.PRIMARY, ft.Colors.SECONDARY],
        ),
        border_radius=ft.BorderRadius.only(bottom_left=28, bottom_right=28),
        padding=ft.padding.only(left=22, right=22, top=14, bottom=22),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Column(
                    spacing=4,
                    expand=True,
                    controls=[greeting_name, greeting_sub],
                ),
            ],
        ),
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 2. QUICK-ACTION TILES
    # ─────────────────────────────────────────────────────────────────────────
    def quick_tile(icon, label, sublabel, bg, fg, route):
        return ft.Container(
            expand=True,
            bgcolor=bg,
            border_radius=14,
            padding=ft.padding.symmetric(horizontal=14, vertical=14),
            ink=True,
            on_click=lambda _, r=route: page.go(r),
            shadow=ft.BoxShadow(
                blur_radius=6,
                color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
                offset=ft.Offset(0, 3),
            ),
            content=ft.Column(
                spacing=6,
                controls=[
                    ft.Container(
                        width=38, height=38,
                        bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.WHITE),
                        border_radius=10,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(icon, color=ft.Colors.WHITE, size=20),
                    ),
                    ft.Text(label, size=13, weight=ft.FontWeight.W_700,
                            color=ft.Colors.WHITE),
                    ft.Text(sublabel, size=10,
                            color=ft.Colors.with_opacity(0.8, ft.Colors.WHITE)),
                ],
            ),
        )

    quick_actions = ft.Row(
        spacing=12,
        controls=[
            quick_tile(
                ft.Icons.LIBRARY_BOOKS_ROUNDED,
                "Courses", "Browse library",
                ft.Colors.INDIGO_400, ft.Colors.WHITE,
                "/courses",
            ),
            quick_tile(
                ft.Icons.PEOPLE_ALT_ROUNDED,
                "Network", "Connect & study",
                ft.Colors.TEAL_500, ft.Colors.WHITE,
                "/network",
            ),
        ],
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 3. FRIENDS SECTION
    # ─────────────────────────────────────────────────────────────────────────
    def friend_avatar(name: str, ):
        initials = "".join(p[0].upper() for p in name.split()[:2])
        return ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
            controls=[
                ft.Stack(
                    controls=[
                        ft.CircleAvatar(
                            content=ft.Text(initials, size=13,
                                            weight=ft.FontWeight.W_700),
                            bgcolor=ft.Colors.PRIMARY_CONTAINER,
                            color=ft.Colors.ON_PRIMARY_CONTAINER,
                            radius=24,
                        )
                    ],
                ),
                ft.Text(name.split()[0], size=10, color=ft.Colors.GREY_600,
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ],
        )

    # placeholder friends — replace with real API data
    token = await page.shared_preferences.get("auth_token")
    friends = await get_all_users(token)

    friends_row = ft.Row(
        scroll=ft.ScrollMode.AUTO,
        spacing=16,
        controls=[
            # Add-friend button
            ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
                controls=[
                    ft.Container(
                        width=48, height=48,
                        bgcolor=ft.Colors.GREY_100,
                        border_radius=24,
                        border=ft.border.all(1, ft.Colors.GREY_300),
                        alignment=ft.Alignment.CENTER,
                        ink=True,
                        on_click=lambda _: page.go("/network"),
                        content=ft.Icon(ft.Icons.PERSON_ADD_ALT_1_ROUNDED,
                                        color=ft.Colors.PRIMARY, size=20),
                    ),
                    ft.Text("Add", size=10, color=ft.Colors.PRIMARY),
                ],
            ),
            *[friend_avatar(friend["name"]) for friend in friends],
        ],
    )

    friends_card = _card(
        ft.Column(
            spacing=12,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(spacing=8, controls=[
                            ft.Icon(ft.Icons.PEOPLE_ALT_ROUNDED,
                                    color=ft.Colors.TEAL_500, size=18),
                            ft.Text("Friends", size=16,
                                    weight=ft.FontWeight.W_700,
                                    color=ft.Colors.ON_SURFACE),
                        ]),
                        ft.TextButton(
                            "See All",
                            on_click=lambda _: page.go("/network"),
                            style=ft.ButtonStyle(
                                color=ft.Colors.PRIMARY,
                                padding=ft.padding.all(0),
                            ),
                        ),
                    ],
                ),
                friends_row,
            ],
        )
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 4. SELF-STUDY SECTION
    # ─────────────────────────────────────────────────────────────────────────
    def study_mode_tile(icon, title, desc, route, bg, fg):
        return ft.Container(
            expand=True,
            bgcolor=bg,
            border_radius=14,
            padding=ft.padding.symmetric(horizontal=14, vertical=14),
            ink=True,
            on_click=lambda _, r=route: page.go(r),
            border=ft.border.all(1, ft.Colors.GREY_200),
            content=ft.Column(
                spacing=6,
                controls=[
                    ft.Container(
                        width=36, height=36,
                        bgcolor=fg,
                        border_radius=10,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(icon, size=18, color=ft.Colors.WHITE),
                    ),
                    ft.Text(title, size=11, weight=ft.FontWeight.W_700,
                            color=ft.Colors.ON_SURFACE),
                    ft.Text(desc, size=10, color=ft.Colors.GREY_500,
                            max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                ],
            ),
        )

    self_study_card = _card(
        ft.Column(
            spacing=12,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(spacing=8, controls=[
                            ft.Icon(ft.Icons.SELF_IMPROVEMENT_ROUNDED,
                                    color=ft.Colors.PURPLE_400, size=18),
                            ft.Text("Self-Study", size=16,
                                    weight=ft.FontWeight.W_700,
                                    color=ft.Colors.ON_SURFACE),
                        ]),
                        ft.TextButton(
                            "Explore",
                            on_click=lambda _: page.go("/self-study"),
                            style=ft.ButtonStyle(
                                color=ft.Colors.PRIMARY,
                                padding=ft.padding.all(0),
                            ),
                        ),
                    ],
                ),
                ft.Row(
                    spacing=10,
                    controls=[
                        study_mode_tile(
                            ft.Icons.QUIZ_ROUNDED,
                            "Quick Quiz",
                            "Test what you know",
                            "/self-study",
                            ft.Colors.PURPLE_50,
                            ft.Colors.PURPLE_400,
                        ),
                        study_mode_tile(
                            ft.Icons.HISTORY_EDU_ROUNDED,
                            "Exam Prep",
                            "Revise & practice",
                            "/self-study",
                            ft.Colors.ORANGE_50,
                            ft.Colors.ORANGE_400,
                        ),
                        study_mode_tile(
                            ft.Icons.LIGHTBULB_OUTLINE_ROUNDED,
                            "Flashcards",
                            "Spaced repetition",
                            "/self-study",
                            ft.Colors.TEAL_50,
                            ft.Colors.TEAL_500,
                        ),
                    ],
                ),
            ],
        )
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 5. ACTIVITY CHART
    # ─────────────────────────────────────────────────────────────────────────
    chart_holder = ft.Container(
        height=180,
        alignment=ft.Alignment.CENTER,
        content=ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=8,
            controls=[
                ft.ProgressRing(color=ft.Colors.PRIMARY, width=20, height=20),
                ft.Text("Syncing activity…", size=13, color=ft.Colors.GREY_400),
            ],
        ),
    )

    activity_card = _card(
        ft.Column(
            spacing=10,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(spacing=8, controls=[
                            ft.Icon(ft.Icons.ANALYTICS_OUTLINED,
                                    color=ft.Colors.PRIMARY, size=18),
                            ft.Text("Weekly Activity", size=16,
                                    weight=ft.FontWeight.W_700,
                                    color=ft.Colors.ON_SURFACE),
                        ]),
                    ],
                ),
                chart_holder,
            ],
        )
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 6. CONTINUE LEARNING
    # ─────────────────────────────────────────────────────────────────────────
    continue_learning_section = ft.Container(width=float("inf"))   # swapped in after data loads

    # ─────────────────────────────────────────────────────────────────────────
    # 8. DATA FETCHER
    # ─────────────────────────────────────────────────────────────────────────
    async def fetch_dashboard_data():
        # ── user greeting ─────────────────────────────────────────────────────
        user_data  = page.session.store.get("current_user") or {}
        first_name = user_data.get("first_name", "there")
        greeting_name.value = f"Hello, {first_name}!"

        token = await page.shared_preferences.get("auth_token")

        # ── enrollments (non-fatal on failure) ────────────────────────────────
        try:
            enrolled_list = await asyncio.wait_for(
                get_enrollments(token, None), timeout=15
            )
            if not isinstance(enrolled_list, list):
                enrolled_list = []
        except (asyncio.TimeoutError, Exception):
            enrolled_list = []

        # ── build continue-learning cards ─────────────────────────────────────
        enrolled_cards = []
        for course in enrolled_list:
            if course.get("progress", 0) < 100:
                course_id   = course.get("id")
                course_name = course.get("name", "Untitled Course")
                progress    = course.get("progress", 0.0)
                card        = get_continue_learning_card(course_name, progress, course_id, page)
                card.on_click = lambda e, cid=course_id: page.go(f"/courses/{cid}/view")
                enrolled_cards.append(card)

        if enrolled_cards:
            continue_learning_section.content = ft.Column(
                spacing=10,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(spacing=8, controls=[
                                ft.Icon(ft.Icons.PLAY_CIRCLE_OUTLINE_ROUNDED,
                                        color=ft.Colors.PRIMARY, size=18),
                                ft.Text("Continue Learning", size=16,
                                        weight=ft.FontWeight.W_700,
                                        color=ft.Colors.ON_SURFACE),
                            ]),
                            ft.TextButton(
                                "View All",
                                on_click=lambda _: page.go("/courses"),
                                style=ft.ButtonStyle(color=ft.Colors.PRIMARY,
                                                     padding=ft.padding.all(0)),
                            ),
                        ],
                    ),
                    ft.Row(
                        scroll=ft.ScrollMode.AUTO,
                        spacing=14,
                        controls=enrolled_cards,
                    ),
                ],
            )
        else:
            continue_learning_section.content = _card(
                ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                    controls=[
                        ft.Icon(ft.Icons.SCHOOL_OUTLINED, size=36,
                                color=ft.Colors.GREY_300),
                        ft.Text("No courses in progress.",
                                size=13, color=ft.Colors.GREY_400),
                        ft.TextButton(
                            "Find a course →",
                            on_click=lambda _: page.go("/courses"),
                            style=ft.ButtonStyle(color=ft.Colors.PRIMARY),
                        ),
                    ],
                )
            )

        # ── weekly activity chart ─────────────────────────────────────────────
        try:
            today  = datetime.now()
            monday = today - timedelta(days=today.weekday())

            week_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            week_labels[today.weekday()] = "Today"

            activity_data = []
            conn = sqlite3.connect("lms_local.db")
            cur  = conn.cursor()
            for i in range(7):
                target = monday + timedelta(days=i)
                if target.date() > today.date():
                    activity_data.append(0)
                else:
                    cur.execute(
                        "SELECT activity_count FROM daily_activity WHERE date = ?",
                        (target.strftime("%Y-%m-%d"),),
                    )
                    res = cur.fetchone()
                    activity_data.append(res[0] if res else 0)
            conn.close()

            chart_max_y = max(activity_data) + 2 if max(activity_data) > 0 else 10

            weekly_chart = fch.BarChart(
                max_y=chart_max_y,
                groups=[
                    fch.BarChartGroup(
                        x=i,
                        rods=[
                            fch.BarChartRod(
                                from_y=0, to_y=val,
                                color=ft.Colors.PRIMARY if week_labels[i] != "Today"
                                      else ft.Colors.SECONDARY,
                                width=18,
                                border_radius=6,
                            )
                        ],
                    )
                    for i, val in enumerate(activity_data)
                ],
                bottom_axis=fch.ChartAxis(
                    labels=[
                        fch.ChartAxisLabel(
                            value=i,
                            label=ft.Text(
                                week_labels[i], size=10,
                                color=ft.Colors.PRIMARY
                                      if week_labels[i] == "Today"
                                      else ft.Colors.GREY_400,
                                weight=ft.FontWeight.W_700
                                       if week_labels[i] == "Today"
                                       else ft.FontWeight.NORMAL,
                            ),
                        )
                        for i in range(7)
                    ]
                ),
                horizontal_grid_lines=fch.ChartGridLines(
                    color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                    width=1,
                    dash_pattern=[4, 4],
                ),
                tooltip=fch.BarChartTooltip(
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST
                ),
                interactive=True,
                expand=True,
            )
            chart_holder.content = weekly_chart

        except Exception:
            # Chart failure is non-fatal — show a quiet fallback
            chart_holder.content = ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.BAR_CHART_ROUNDED,
                            size=32, color=ft.Colors.GREY_300),
                    ft.Text("Activity data unavailable.",
                            size=12, color=ft.Colors.GREY_400),
                ],
            )

        page.update()

    page.run_task(fetch_dashboard_data)

    # ─────────────────────────────────────────────────────────────────────────
    # VIEW
    # ─────────────────────────────────────────────────────────────────────────
    return ft.View(
        route="/dashboard",
        bottom_appbar=app_bar,
        bgcolor=ft.Colors.GREY_50,
        padding=0,
        controls=[
            ft.SafeArea(
                expand=True,
                content=ft.Column(
                    expand=True,
                    spacing=0,
                    controls=[
                        header,
                        ft.Column(
                            expand=True,
                            scroll=ft.ScrollMode.AUTO,
                            spacing=0,
                            controls=[
                                ft.Container(
                                    padding=ft.padding.symmetric(
                                        horizontal=16, vertical=16
                                    ),
                                    content=ft.Column(
                                        spacing=16,
                                        controls=[
                                            # Quick action tiles
                                            quick_actions,
                                            friends_card,
                                            
                                            #browse activity
                                            activity_card,
                                            # Continue learning
                                            continue_learning_section,

                                            # Self-study
                                            self_study_card,
                                            

                                            

                                            ft.Container(height=16),
                                        ],
                                    ),
                                )
                            ],
                        ),
                    ],
                ),
            )
        ],
    )