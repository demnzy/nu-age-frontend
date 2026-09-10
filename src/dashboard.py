import asyncio
import sqlite3
from datetime import datetime, timedelta

import flet as ft
import flet_charts as fch  # pyright: ignore[reportMissingImports]

from src.components import bottom_appbar
from src.components.bottom_appbar import get_bottom_appbar
from src.components.dashboard_card import get_continue_learning_card
from src.requests.enrollments import get_enrollments
from src.requests.chats import get_all_users
from src.utils.quotes import get_random_quote, get_random_greeting, get_random_tip
from src.utils.db_manager import get_weekly_activity, log_daily_activity

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _section_label(text: str) -> ft.Text:
    return ft.Text(text, size=11, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_500)


def _card(content, padding=18) -> ft.Container:
    return ft.Container(
        bgcolor=ft.Colors.SURFACE,
        border_radius=16,
        border=ft.Border.all(1, ft.Colors.GREY_200),
        padding=padding,
        shadow=ft.BoxShadow(
            blur_radius=8,
            color=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
            offset=ft.Offset(0, 3),
        ),
        content=content,
        opacity=0,
        offset=ft.Offset(0, 0.2),
        animate_opacity=ft.Animation(400, ft.AnimationCurve.DECELERATE),
        animate_offset=ft.Animation(400, ft.AnimationCurve.DECELERATE),
    )


# ─────────────────────────────────────────────────────────────────────────────
# ONBOARDING — first-login setup wizard
# ─────────────────────────────────────────────────────────────────────────────
from src.components.onboarding_overlay import build_onboarding_overlay

# DEV MOCK TOGGLE ------------------------------------------------------------
# Force-show or force-hide the onboarding overlay for testing:
#   True  -> always show it (handy while designing/testing)
#   False -> never show it
#   None  -> use check_is_first_login()'s result (the "real" behavior)
FORCE_SHOW_ONBOARDING = None


async def check_is_first_login(page: ft.Page) -> bool:
    """Check if the user is logging in for the first time."""
    user_data = page.session.store.get("current_user") or {}
    streak = user_data.get("streak", 0)
    seen = streak > 2
    return not seen


async def mark_onboarding_seen(page: ft.Page, data: dict = None) -> None:
    """Save onboarding completion and user preferences."""
    await page.shared_preferences.set("has_seen_onboarding", True)
    if data:
        try:
            if "role" in data:
                await page.shared_preferences.set("user_role", str(data["role"]))
            if "interests" in data and isinstance(data["interests"], list):
                await page.shared_preferences.set("user_interests", ",".join(data["interests"]))
            if "daily_goal" in data:
                await page.shared_preferences.set("daily_study_goal", str(data["daily_goal"]))
        except Exception as ex:
            print(f"[Onboarding] Preferences save warning: {ex}")


# ─────────────────────────────────────────────────────────────────────────────
# VIEW
# ─────────────────────────────────────────────────────────────────────────────
async def dashboard_view(page: ft.Page):
    app_bar = get_bottom_appbar(page)

    content_socket = ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        content=ft.ProgressRing(color=ft.Colors.PRIMARY, stroke_width=3)
    )

    # ── onboarding overlay (lives inside the View's body via a Stack, so it
    # only covers the main page content — the bottom app bar is a separate
    # Scaffold slot and sits outside this Stack, so it's never covered) ─────
    onboarding_slot = ft.Container(
        expand=True,
        visible=False,
        opacity=0,
        scale=0.96,
        animate_opacity=ft.Animation(400, ft.AnimationCurve.EASE_OUT),
        animate_scale=ft.Animation(400, ft.AnimationCurve.EASE_OUT),
        data="onboarding_overlay",
    )

    async def hide_onboarding_async(data=None):
        # fade + shrink out, then actually remove it once the animation's done
        bottom_appbar.opacity = 1
        onboarding_slot.opacity = 0
        onboarding_slot.scale = 0.96
        page.update()
        await asyncio.sleep(0.4)
        onboarding_slot.visible = False
        onboarding_slot.content = None
        page.update()

    def hide_onboarding(data=None):
        page.run_task(hide_onboarding_async, data)

    async def maybe_show_onboarding():
        # FORCE_SHOW_ONBOARDING (defined near ONBOARDING_SLIDES above) wins
        # when set to True/False, for quick manual testing. Set it to None
        # to fall back to the real/mock check_is_first_login() result.
        seen = await page.shared_preferences.get('has_seen_onboarding')
        print(seen)
        if FORCE_SHOW_ONBOARDING is not None:
            should_show = FORCE_SHOW_ONBOARDING
        elif not seen:
            should_show = await check_is_first_login(page) 
        else:
            return

        if not should_show:
            return

        # let the dashboard render and settle first — this is what makes the
        # overlay feel like it eases in over an already-loaded page instead
        # of slamming in before anything underneath is visible
        await asyncio.sleep(1.5)
        bottom_appbar.opacity= 0.5
        page.update()
        onboarding_slot.content = build_onboarding_overlay(
            page, on_dismiss=hide_onboarding
        )
        onboarding_slot.visible = True
        page.update()
        await asyncio.sleep(0.03)  # let the 0-opacity/0.96-scale frame render first
        onboarding_slot.opacity = 1
        onboarding_slot.scale = 1
        page.update()

    page.run_task(maybe_show_onboarding)

    # ── greeting text (mutated after data loads) ──────────────────────────────
    greeting_name = ft.Text(
        "",
        size=24, weight=ft.FontWeight.W_900, color=ft.Colors.WHITE,
    )
    greeting_sub = ft.Text(
        get_random_quote(),
        size=12, color=ft.Colors.with_opacity(0.9, ft.Colors.WHITE),
        italic=True,
        opacity=0,
        offset=ft.Offset(0, 0.3),
        animate_opacity=ft.Animation(800, ft.AnimationCurve.EASE_OUT),
        animate_offset=ft.Animation(800, ft.AnimationCurve.EASE_OUT),
    )
    
    # ── tips text ─────────────────────────────────────────────────────────────
    tip_container = ft.Container(
        bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.BLACK),
        border_radius=ft.BorderRadius.all(12),
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        opacity=0,
        animate_opacity=ft.Animation(800, ft.AnimationCurve.EASE_OUT),
        content=ft.Row(
            wrap=True,
            spacing=8,
            controls=[
                ft.Text(
                    f'💡{get_random_tip()}',
                    size=11, color=ft.Colors.WHITE
                )
            ]
        )
    )

    # ── stats variables (mutated after data loads) ────────────────────────────
    stat_enrolled = ft.Text("-", size=20, weight=ft.FontWeight.W_800, color=ft.Colors.SURFACE)
    stat_finished = ft.Text("-", size=20, weight=ft.FontWeight.W_800, color=ft.Colors.SURFACE)
    stat_streak = ft.Text("-", size=20, weight=ft.FontWeight.W_800, color=ft.Colors.SURFACE)

    # ─────────────────────────────────────────────────────────────────────────
    # 1. HEADER / HERO (Redesigned matching EduLearn & mobile inspo)
    # ─────────────────────────────────────────────────────────────────────────
    hero_art = ft.Container(
        width=250,
        height=170,
        border_radius=ft.BorderRadius.all(16),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        alignment=ft.Alignment.CENTER,
        content=ft.Image(
            src="hero_graduation.png",
            fit=ft.BoxFit.CONTAIN,
        ),
    )

    def build_hero_content():
        is_desktop = (page.width or 400) >= 720
        if is_desktop:
            return ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Column(
                        expand=True,
                        spacing=12,
                        controls=[
                            greeting_name,
                            greeting_sub,
                            tip_container,
                        ],
                    ),
                    hero_art,
                ],
            )
        else:
            return ft.Column(
                spacing=12,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Column(
                                expand=True,
                                spacing=4,
                                controls=[
                                    greeting_name,
                                ],
                            ),
                            ft.Container(
                                width=105,
                                height=85,
                                border_radius=ft.BorderRadius.all(12),
                                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                                content=ft.Image(
                                    src="hero_graduation.png",
                                    fit=ft.BoxFit.CONTAIN,
                                ),
                            ),
                        ],
                    ),
                    greeting_sub,
                    tip_container,
                ],
            )

    header = ft.Container(
        bgcolor=ft.Colors.SECONDARY,  # Matches theme secondary color (#37BF14) & hero_graduation.png background
        width=float("inf"),
        border_radius=20,
        padding=ft.Padding.all(20),
        margin=ft.Padding.only(left=16, right=16, top=12, bottom=16),
        shadow=ft.BoxShadow(
            blur_radius=16,
            color=ft.Colors.with_opacity(0.15, ft.Colors.BLACK),
            offset=ft.Offset(0, 6),
        ),
        opacity=0,
        offset=ft.Offset(0, 0.2),
        animate_opacity=ft.Animation(400, ft.AnimationCurve.DECELERATE),
        animate_offset=ft.Animation(400, ft.AnimationCurve.DECELERATE),
        content=build_hero_content(),
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 2. QUICK-ACTION TILES
    # ─────────────────────────────────────────────────────────────────────────
    def quick_tile(icon, label, sublabel, bg, fg, route):
        return ft.Container(
            expand=True,
            bgcolor=bg,
            border_radius=14,
            padding=ft.Padding.symmetric(horizontal=14, vertical=14),
            ink=True,
            on_click=lambda _, r=route: page.go(r),
            shadow=ft.BoxShadow(
                blur_radius=6,
                color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                offset=ft.Offset(0, 3),
            ),
            content=ft.Column(
                spacing=6,
                controls=[
                    ft.Container(
                        width=38, height=38,
                        bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.SURFACE),
                        border_radius=10,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(icon, color=ft.Colors.SURFACE, size=20),
                    ),
                    ft.Text(label, size=13, weight=ft.FontWeight.W_700,
                            color=ft.Colors.SURFACE),
                    ft.Text(sublabel, size=10,
                            color=ft.Colors.with_opacity(0.8, ft.Colors.SURFACE)),
                ],
            ),
        )

    quick_actions = ft.Row(
        spacing=12,
        opacity=0,
        offset=ft.Offset(0, 0.2),
        animate_opacity=ft.Animation(400, ft.AnimationCurve.DECELERATE),
        animate_offset=ft.Animation(400, ft.AnimationCurve.DECELERATE),
        controls=[
            quick_tile(
                ft.Icons.LIBRARY_BOOKS_ROUNDED,
                "Courses", "Browse library",
                ft.Colors.INDIGO_300, ft.Colors.SURFACE,
                "/courses",
            ),
            quick_tile(
                ft.Icons.PEOPLE_ALT_ROUNDED,
                "Network", "Connect & study",
                ft.Colors.TEAL_400, ft.Colors.SURFACE,
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
                        bgcolor=ft.Colors.SURFACE,
                        border_radius=24,
                        border=ft.Border.all(1, ft.Colors.GREY_300),
                        alignment=ft.Alignment.CENTER,
                        ink=True,
                        on_click=lambda _: page.go("/network"),
                        content=ft.Icon(ft.Icons.PERSON_ADD_ALT_1_ROUNDED,
                                        color=ft.Colors.PRIMARY, size=20),
                    ),
                    ft.Text("Add", size=10, color=ft.Colors.PRIMARY),
                ],
            ),
            *[
                friend_avatar(friend.get("name") if isinstance(friend, dict) and isinstance(friend.get("name"), str) else "Learner")
                for friend in (friends if isinstance(friends, list) else [])
            ],
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
                                padding=ft.Padding.all(0),
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
            padding=ft.Padding.symmetric(horizontal=14, vertical=14),
            ink=True,
            on_click=lambda _, r=route: page.go(r),
            border=ft.Border.all(1, ft.Colors.OUTLINE),
            content=ft.Column(
                spacing=6,
                controls=[
                    ft.Container(
                        width=36, height=36,
                        bgcolor=fg,
                        border_radius=10,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(icon, size=18, color=ft.Colors.SURFACE),
                    ),
                    ft.Text(title, size=11, weight=ft.FontWeight.W_700,
                            color=ft.Colors.SURFACE),
                    ft.Text(desc, size=10, color=ft.Colors.SURFACE,
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
                                padding=ft.Padding.all(0),
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
                            ft.Colors.PURPLE_400,
                            ft.Colors.PURPLE_300,
                        ),
                        study_mode_tile(
                            ft.Icons.HISTORY_EDU_ROUNDED,
                            "Exam Prep",
                            "Revise & practice",
                            "/self-study",
                            ft.Colors.ORANGE_400,
                            ft.Colors.ORANGE_300,
                        ),
                        study_mode_tile(
                            ft.Icons.LIGHTBULB_OUTLINE_ROUNDED,
                            "Flashcards",
                            "Spaced repetition",
                            "/self-study",
                            ft.Colors.TEAL_400,
                            ft.Colors.TEAL_300,
                        ),
                    ],
                ),
            ],
        )
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 5. DUAL RESPONSIVE TRACKERS: ACTIVITY THREAD & LEARNING FOCUS BY CATEGORY
    # ─────────────────────────────────────────────────────────────────────────
    # Tracker 1: Activity Thread (Line Chart)
    activity_holder = ft.Container(
        height=180,
        alignment=ft.Alignment.CENTER,
        content=ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=8,
            controls=[
                ft.ProgressRing(color=ft.Colors.PRIMARY, width=18, height=18, stroke_width=2.5),
                ft.Text("Loading activity thread…", size=12.5, color=ft.Colors.GREY_400),
            ],
        ),
    )

    activity_badge_text = ft.Text("Weekly Pace", size=11, weight=ft.FontWeight.W_600, color=ft.Colors.PRIMARY)

    activity_badge = ft.Container(
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        border_radius=ft.BorderRadius.all(10),
        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY),
        content=ft.Row(
            spacing=4,
            tight=True,
            controls=[
                ft.Icon(ft.Icons.TIMELINE_ROUNDED, size=12, color=ft.Colors.PRIMARY),
                activity_badge_text,
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
                            ft.Icon(ft.Icons.SHOW_CHART_ROUNDED,
                                    color=ft.Colors.PRIMARY, size=20),
                            ft.Column(
                                spacing=0,
                                controls=[
                                    ft.Text("Activity Thread", size=15,
                                            weight=ft.FontWeight.W_700,
                                            color=ft.Colors.ON_SURFACE),
                                    ft.Text("Weekly Learning Velocity", size=10,
                                            weight=ft.FontWeight.W_500,
                                            color=ft.Colors.GREY_500),
                                ],
                            ),
                        ]),
                        activity_badge,
                    ],
                ),
                activity_holder,
            ],
        )
    )

    # Tracker 2: Learning Focus by Category (Donut Chart)
    focus_holder = ft.Container(
        height=180,
        alignment=ft.Alignment.CENTER,
        content=ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=8,
            controls=[
                ft.ProgressRing(color=ft.Colors.SECONDARY, width=18, height=18, stroke_width=2.5),
                ft.Text("Analyzing categories…", size=12.5, color=ft.Colors.GREY_400),
            ],
        ),
    )

    focus_count_text = ft.Text("-- Courses", size=11, weight=ft.FontWeight.W_600, color=ft.Colors.SECONDARY)

    focus_badge = ft.Container(
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        border_radius=ft.BorderRadius.all(10),
        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.SECONDARY),
        content=ft.Row(
            spacing=4,
            tight=True,
            controls=[
                ft.Icon(ft.Icons.CATEGORY_ROUNDED, size=12, color=ft.Colors.SECONDARY),
                focus_count_text,
            ],
        ),
    )

    focus_card = _card(
        ft.Column(
            spacing=10,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(spacing=8, controls=[
                            ft.Icon(ft.Icons.PIE_CHART_OUTLINE_ROUNDED,
                                    color=ft.Colors.SECONDARY, size=18),
                            ft.Column(
                                spacing=0,
                                controls=[
                                    ft.Text("Learning Focus", size=15,
                                            weight=ft.FontWeight.W_700,
                                            color=ft.Colors.ON_SURFACE),
                                    ft.Text("By Category", size=10,
                                            weight=ft.FontWeight.W_600,
                                            color=ft.Colors.GREY_500),
                                ],
                            ),
                        ]),
                        focus_badge,
                    ],
                ),
                focus_holder,
            ],
        )
    )

    def build_trackers_layout(is_desktop: bool):
        if is_desktop:
            return ft.Row(
                spacing=16,
                vertical_alignment=ft.CrossAxisAlignment.START,
                controls=[
                    ft.Container(expand=1, content=activity_card),
                    ft.Container(expand=1, content=focus_card),
                ],
            )
        else:
            return ft.Column(
                spacing=16,
                controls=[activity_card, focus_card],
            )

    trackers_container = ft.Container(
        content=build_trackers_layout((page.width or 400) >= 800),
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 6. CONTINUE LEARNING
    # ─────────────────────────────────────────────────────────────────────────
    continue_learning_section = ft.Container(
        width=float("inf"),
        opacity=0,
        offset=ft.Offset(0, 0.2),
        animate_opacity=ft.Animation(400, ft.AnimationCurve.DECELERATE),
        animate_offset=ft.Animation(400, ft.AnimationCurve.DECELERATE),
    )   # swapped in after data loads

    # ─────────────────────────────────────────────────────────────────────────
    # 8. DATA FETCHER
    # ─────────────────────────────────────────────────────────────────────────
    async def fetch_dashboard_data():
        # ── user greeting & stats ─────────────────────────────────────────────
        user_data  = page.session.store.get("current_user") or {}
        first_name = user_data.get("first_name", "there")
        target_greeting = f"{get_random_greeting()} {first_name}!"

        # Trigger fade animations immediately
        greeting_sub.opacity = 1
        greeting_sub.offset = ft.Offset(0, 0)
        tip_container.opacity = 1
        page.update()

        # Typing animation
        async def type_greeting(target_text: str):
            current_text = ""
            for char in target_text:
                current_text += char
                greeting_name.value = current_text + "|"
                page.update()
                await asyncio.sleep(0.04)
            
            # Blink the cursor a few times
            for _ in range(3):
                greeting_name.value = current_text + " "
                page.update()
                await asyncio.sleep(0.4)
                greeting_name.value = current_text + "|"
                page.update()
                await asyncio.sleep(0.4)
                
            # Remove cursor
            greeting_name.value = current_text
            page.update()

        page.run_task(type_greeting, target_greeting)
        
        streak = user_data.get("streak", 0)

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
            
        active_count = len(enrolled_list)
        finished_count = sum(1 for c in enrolled_list if c.get("progress", 0.0) >= 100)
        
        # ── stat animation ────────────────────────────────────────────────────
        async def animate_stats(target_act: int, target_fin: int, target_str: int):
            # Find the max so we know how many steps to take if we want to run together
            max_val = max(target_act, target_fin, target_str)
            if max_val == 0:
                stat_enrolled.value = "0"
                stat_finished.value = "0"
                stat_streak.value = "0"
                page.update()
                return

            # Animate in ~20 steps or max_val steps, whichever is smaller, over ~600ms
            steps = min(max_val, 15)
            delay = 0.3 / steps

            for step in range(1, steps + 1):
                cur_act = int((target_act / steps) * step)
                cur_fin = int((target_fin / steps) * step)
                cur_str = int((target_str / steps) * step)
                
                stat_enrolled.value = str(cur_act)
                stat_finished.value = str(cur_fin)
                stat_streak.value = str(cur_str)
                page.update()
                await asyncio.sleep(delay)
                
            # Final snap to exact values
            stat_enrolled.value = str(target_act)
            stat_finished.value = str(target_fin)
            stat_streak.value = str(target_str)
            page.update()

        page.run_task(animate_stats, active_count, finished_count, streak)

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
                                                     padding=ft.Padding.all(0)),
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
            continue_learning_section.content = ft.Container(
                bgcolor=ft.Colors.SURFACE,
                border_radius=16,
                border=ft.Border.all(1, ft.Colors.GREY_200),
                padding=18,
                shadow=ft.BoxShadow(
                    blur_radius=8,
                    color=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                    offset=ft.Offset(0, 3),
                ),
                content=ft.Column(
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

        # ── 1. POPULATE ACTIVITY THREAD & LEARNING FOCUS TRACKERS ────────────
        total_courses = len(enrolled_list)
        finished_count = sum(1 for c in enrolled_list if c.get("progress", 0.0) >= 100)
        in_progress_count = sum(1 for c in enrolled_list if 0 < c.get("progress", 0.0) < 100)

        # Log today's active visit
        try:
            log_daily_activity()
        except Exception:
            pass

        # Query weekly activity from local db
        try:
            raw_weekly = get_weekly_activity()
        except Exception:
            raw_weekly = [0] * 7

        if not raw_weekly or len(raw_weekly) != 7:
            raw_weekly = [0] * 7

        activity_values = list(raw_weekly)
        # Ensure today's count reflects active engagement
        if activity_values[-1] == 0:
            activity_values[-1] = max(1, in_progress_count)

        # Reflect streak days in the activity trend
        for s in range(1, min(streak, 7)):
            idx = 6 - s
            if idx >= 0 and activity_values[idx] == 0:
                activity_values[idx] = max(1, (in_progress_count * 2) - s)

        total_actions = sum(activity_values)
        avg_daily = total_actions / 7.0

        if streak > 0:
            activity_badge_text.value = f"🔥 {streak}d Streak"
        else:
            activity_badge_text.value = f"{total_actions} Actions"

        focus_count_text.value = f"{total_courses} Course{'s' if total_courses != 1 else ''}"

        # ── Tracker 1: Activity Thread Line Chart ─────────────────────────────
        today = datetime.now()
        day_labels = [(today - timedelta(days=i)).strftime("%a") if i > 0 else "Today" for i in range(6, -1, -1)]

        points = []
        axis_labels = []
        max_act = max(activity_values) if activity_values else 8
        top_y = max(max_act * 1.3, 8)

        for idx, (lbl, val) in enumerate(zip(day_labels, activity_values)):
            points.append(
                fch.LineChartDataPoint(
                    x=idx,
                    y=val,
                    tooltip=f"{lbl}: {val} actions",
                )
            )
            axis_labels.append(
                fch.ChartAxisLabel(
                    value=idx,
                    label=ft.Text(lbl, size=10, color=ft.Colors.GREY_500, weight=ft.FontWeight.W_600),
                )
            )

        activity_series = fch.LineChartData(
            points=points,
            curved=True,
            curve_smoothness=0.35,
            stroke_width=3,
            color=ft.Colors.PRIMARY,
            point=fch.ChartCirclePoint(
                radius=4,
                color=ft.Colors.PRIMARY,
            ),
            below_line_bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
            prevent_curve_over_shooting=True,
        )

        activity_chart = fch.LineChart(
            data_series=[activity_series],
            min_y=0,
            max_y=top_y,
            min_x=0,
            max_x=6,
            bottom_axis=fch.ChartAxis(labels=axis_labels),
            horizontal_grid_lines=fch.ChartGridLines(
                color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                dash_pattern=[4, 4],
                width=1,
            ),
            tooltip=fch.LineChartTooltip(bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST),
            interactive=True,
            expand=True,
        )

        activity_footer = ft.Row(
            spacing=16,
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ft.Row(
                    spacing=5,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.INSIGHTS_ROUNDED, size=13, color=ft.Colors.PRIMARY),
                        ft.Text(f"{total_actions} actions this week", size=10.5, color=ft.Colors.GREY_500),
                    ],
                ),
                ft.Row(
                    spacing=5,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.TRENDING_UP_ROUNDED, size=13, color=ft.Colors.TEAL_400),
                        ft.Text(f"{avg_daily:.1f}/day pace", size=10.5, color=ft.Colors.GREY_500),
                    ],
                ),
            ],
        )

        activity_holder.content = ft.Column(
            spacing=6,
            controls=[
                ft.Container(height=145, content=activity_chart),
                activity_footer,
            ],
        )

        # ── Tracker 2: Learning Focus Donut Chart ─────────────────────────────
        if total_courses == 0:
            focus_holder.content = ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=6,
                controls=[
                    ft.Icon(ft.Icons.PIE_CHART_OUTLINE_ROUNDED, size=32, color=ft.Colors.GREY_300),
                    ft.Text("Categorize your study paths.", size=12, color=ft.Colors.GREY_400),
                    ft.TextButton(
                        "Browse Catalog →",
                        on_click=lambda _: page.go("/courses"),
                        style=ft.ButtonStyle(color=ft.Colors.SECONDARY, padding=ft.Padding.all(0)),
                    ),
                ],
            )
        else:
            cat_counts = {}
            for c in enrolled_list:
                cat_name = (c.get("category") or {}).get("name") or "General"
                cat_counts[cat_name] = cat_counts.get(cat_name, 0) + 1

            palette = [
                ft.Colors.PRIMARY,
                ft.Colors.SECONDARY,
                ft.Colors.TEAL_400,
                ft.Colors.AMBER_500,
                ft.Colors.PURPLE_400,
                ft.Colors.BLUE_400,
                ft.Colors.PINK_400,
                ft.Colors.INDIGO_400,
                ft.Colors.ORANGE_400,
            ]
            sections = []
            legend_items = []
            for i, (cat_name, count) in enumerate(cat_counts.items()):
                color = palette[i % len(palette)]
                pct = (count / total_courses) * 100
                sections.append(
                    fch.PieChartSection(
                        value=count,
                        color=color,
                        radius=16,
                        title="",
                    )
                )
                legend_items.append(
                    ft.Row(
                        spacing=6,
                        tight=True,
                        controls=[
                            ft.Container(width=8, height=8, border_radius=4, bgcolor=color),
                            ft.Text(cat_name[:12] + ".." if len(cat_name) > 13 else cat_name, size=10.5, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE),
                            ft.Text(f"{pct:.0f}%", size=9.5, color=ft.Colors.GREY_400),
                        ],
                    )
                )

            donut_stack = ft.Stack(
                width=115,
                height=115,
                alignment=ft.Alignment.CENTER,
                controls=[
                    fch.PieChart(
                        sections=sections,
                        center_space_radius=36,
                        sections_space=2.5,
                        width=115,
                        height=115,
                    ),
                    ft.Column(
                        spacing=0,
                        tight=True,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                        controls=[
                            ft.Text(str(total_courses), size=18, weight=ft.FontWeight.W_900, color=ft.Colors.PRIMARY),
                            ft.Text("Courses", size=9, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_500),
                        ],
                    ),
                ],
            )

            focus_holder.content = ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_EVENLY,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
                controls=[
                    donut_stack,
                    ft.Container(
                        height=150,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Column(
                            spacing=4,
                            tight=True,
                            scroll=ft.ScrollMode.AUTO,
                            alignment=ft.MainAxisAlignment.CENTER,
                            controls=legend_items,
                        ),
                    ),
                ],
            )

        content_socket.content = ft.Column(
            expand=True,
            spacing=0,
            controls=[
                ft.Column(
                    expand=True,
                    scroll=ft.ScrollMode.AUTO,
                    spacing=0,
                    controls=[
                        header,
                        ft.Container(
                            padding=ft.Padding.symmetric(
                                horizontal=16, vertical=16
                            ),
                            content=ft.Column(
                                spacing=16,
                                controls=[
                                    trackers_container,         # 1. Dual Course Mastery & Learning Focus Trackers!
                                    self_study_card,            # 3. Self-Study Hub
                                    continue_learning_section,  # 2. Continue Learning
                                    friends_card,               # 4. Friends / study network
                                    quick_actions,              # 5. Quick shortcuts
                                    ft.Container(height=24),
                                ],
                            ),
                        )
                    ],
                ),
            ],
        )
        page.update()
        
        # Trigger staggered fade-up animations for main dashboard sections
        sections_to_animate = [
            header,
            activity_card,
            focus_card,
            continue_learning_section, 
            self_study_card,
            friends_card, 
            quick_actions,
        ]
        
        for idx, section in enumerate(sections_to_animate):
            async def animate_section(s, i):
                await asyncio.sleep(i * 0.1)
                s.opacity = 1
                s.offset = ft.Offset(0, 0)
                page.update()
            
            page.run_task(animate_section, section, idx)

    page.run_task(fetch_dashboard_data)

    def on_dashboard_resize(e):
        is_desk = (page.width or 400) >= 800
        trackers_container.content = build_trackers_layout(is_desk)
        header.content = build_hero_content()
        page.update()

    page.on_resize = on_dashboard_resize

    # ─────────────────────────────────────────────────────────────────────────
    # VIEW
    # ─────────────────────────────────────────────────────────────────────────
    return ft.View(
        route="/dashboard",
        bottom_appbar=app_bar,
        bgcolor=ft.Colors.ON_PRIMARY,
        padding=0,
        controls=[
            ft.Stack(
                expand=True,
                controls=[
                    ft.SafeArea(
                        expand=True,
                        content=content_socket,
                    ),
                    # Onboarding sits on top of the page content only —
                    # the bottom app bar is a separate Scaffold slot outside
                    # this Stack, so it's never covered by the overlay.
                    onboarding_slot,
                ],
            ),
        ],
    )