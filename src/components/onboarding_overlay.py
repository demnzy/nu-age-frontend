"""Sleek, adaptive onboarding carousel for Nu Age LMS.

Supports responsive multi-device layouts:
  - Laptop / Desktop (>= 880px): Spacious split-screen presentation deck
      Left: 1-to-1 MacBook App Frame with clean tab title bar and floating BottomAppBar (Slides 1-3)
            Dedicated Interactive Learning Setup Card (Slide 4 - No screenshot/nav bar)
      Right: Tour Guide, Scannable Highlights, Action CTAs & Progress Indicators
  - Mobile & Tablet (< 880px): Single-column vertical stack with touch swipe gestures
  - 1-to-1 Authenticity matching user's live screenshots:
      1. Dashboard & Self-Study Hub: Exact dashboard header, real Self-Study card & Home active tab
      2. Learn Tab: 1-to-1 replica of the live Learn screen (Image 1): Header, 6 squircle tabs, 2x2 course cards & Learn active tab
      3. Nu Chat: 1-to-1 replica of the live Nu Chat screen (Image 2): Pure mock user names, compose FAB, right empty state & Chat active tab
      4. Goals & Features: Interactive daily pace selector (15m/30m/60m), focus topic chips, and feature showcase (Streaks, In-Course AI, Screen Reader, Study Duels)
"""

import os
import asyncio
import flet as ft

# ─────────────────────────────────────────────────────────────────────────────
# 4 ONBOARDING SCREENS CONFIGURATION (Concise, Jargon-Free & Human-Readable)
# ─────────────────────────────────────────────────────────────────────────────
ONBOARDING_SCREENS = [
    {
        "step_label": "Self-Study Hub",
        "tab_name": "Dashboard",
        "route_key": "/dashboard",
        "title": "Your Notes, Supercharged",
        "desc": "Turn PDFs and notes into active-recall flashcards, quizzes, and timed CBT exam simulators in seconds.",
        "bullets": [
            ("Smart active-recall flashcards", ft.Icons.STYLE_ROUNDED),
            ("Instant-hint practice quizzes", ft.Icons.QUIZ_ROUNDED),
            ("Timed CBT exam simulations", ft.Icons.TIMER_ROUNDED),
            ("1-tap launch from dashboard", ft.Icons.TOUCH_APP_ROUNDED),
        ],
        "gif": "onboarding_self_study.gif",
        "image": "onboarding_self_study.png",
        "accent": ft.Colors.PRIMARY,
        "badge_bg": "#E8F8F2",
        "btn_text": "Explore Courses →",
    },
    {
        "step_label": "Courses & Spaces",
        "tab_name": "Learn",
        "route_key": "/courses",
        "title": "Courses for Real Progress",
        "desc": "Follow module tracks, save lessons for zero-data offline reading, and collaborate in Course Spaces.",
        "bullets": [
            ("Clear progress tracking per module", ft.Icons.CHECK_CIRCLE_ROUNDED),
            ("Download lessons for offline study", ft.Icons.WIFI_OFF_ROUNDED),
            ("Interactive topic drills & mastery", ft.Icons.BOLT_ROUNDED),
            ("Course Spaces with live class links", ft.Icons.GROUPS_ROUNDED),
        ],
        "gif": "onboarding_courses.gif",
        "image": "onboarding_courses.png",
        "accent": ft.Colors.BLUE_600,
        "badge_bg": "#EFF6FF",
        "btn_text": "Discover Nu Chat →",
    },
    {
        "step_label": "Nu Chat & AI",
        "tab_name": "Nu Chat",
        "route_key": "/nu-chat",
        "title": "Study Together & Ask Nu AI",
        "desc": "Chat with classmates, swap notes, and get instant 24/7 homework help from your Nu Owl AI tutor.",
        "bullets": [
            ("Class channels & direct messaging", ft.Icons.CHAT_BUBBLE_ROUNDED),
            ("24/7 Nu Owl AI homework help", ft.Icons.SMART_TOY_ROUNDED),
            ("Share notes, code & voice memos", ft.Icons.ATTACH_FILE_ROUNDED),
            ("Delivered & read message receipts", ft.Icons.DONE_ALL_ROUNDED),
        ],
        "gif": "onboarding_chat.gif",
        "image": "onboarding_chat.png",
        "accent": ft.Colors.INDIGO_600,
        "badge_bg": "#EEF2FF",
        "btn_text": "Next: Set Your Goals →",
    },
    {
        "step_label": "Personalize Goals",
        "tab_name": "Setup",
        "route_key": "/profile",
        "title": "Set Your Daily Study Pace",
        "desc": "Pick your target study time. We'll tailor your daily goals, streak rewards, and practice schedule.",
        "bullets": [
            ("Daily streaks & streak freeze shields", ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED),
            ("In-lesson AI study companion", ft.Icons.AUTO_AWESOME_ROUNDED),
            ("Hands-free screen reader audio", ft.Icons.HEADPHONES_ROUNDED),
            ("Classmate study duels & leaderboards", ft.Icons.SPORTS_ESPORTS_ROUNDED),
        ],
        "gif": "",
        "image": "",
        "accent": ft.Colors.AMBER_700,
        "badge_bg": "#FFFBEB",
        "btn_text": "Launch Nu Age 🚀",
    },
]


def build_onboarding_overlay(page: ft.Page, on_dismiss=None) -> ft.Container:
    """Builds an adaptive onboarding carousel matching the live app views and bottom nav bar 1-to-1."""
    state = {
        "index": 0,
        "dismissed": False,
        "goal_minutes": 30,
        "study_focus": "Software & Tech",
        "is_animating": False,
    }
    total_screens = len(ONBOARDING_SCREENS)

    def _screen_w() -> int:
        return int(page.width or getattr(page.window, "width", None) or 1000)

    def _screen_h() -> int:
        return int(page.height or getattr(page.window, "height", None) or 720)

    def is_desktop() -> bool:
        return _screen_w() >= 880

    def get_card_width() -> float:
        w = _screen_w()
        if w >= 880:
            return min(920.0, max(780.0, w * 0.70))
        elif w >= 600:
            return min(540.0, max(460.0, w * 0.85))
        else:
            return max(290.0, min(360.0, w - 24.0))

    def safe_page_update():
        try:
            page.update()
        except Exception:
            pass

    async def _dismiss_async(skipped: bool = False):
        if state["dismissed"]:
            return
        state["dismissed"] = True

        try:
            if hasattr(page, "shared_preferences"):
                await page.shared_preferences.set("app_onboarding_shown_v1", True)
                await page.shared_preferences.set("has_seen_onboarding", True)
                await page.shared_preferences.set("study_goal_minutes", state["goal_minutes"])
                await page.shared_preferences.set("study_focus", state["study_focus"])
        except Exception as ex:
            print(f"[Onboarding] shared_preferences error: {ex}")

        # Persistent disk marker fallback for compiled app installs
        try:
            import json
            app_dir = os.path.join(os.environ.get("APPDATA") or os.environ.get("HOME") or os.path.expanduser("~"), ".nu_age")
            os.makedirs(app_dir, exist_ok=True)
            state_file = os.path.join(app_dir, "client_state.json")
            data = {}
            if os.path.exists(state_file):
                try:
                    with open(state_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    data = {}
            data["onboarding_shown"] = True
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception as ex:
            print(f"[Onboarding] Disk marker error: {ex}")

        try:
            if hasattr(page, "session") and hasattr(page.session, "store"):
                u = page.session.store.get("current_user") or {}
                u["has_seen_onboarding"] = True
                u["study_goal_minutes"] = state["goal_minutes"]
                u["study_focus"] = state["study_focus"]
                page.session.store.set("current_user", u)
        except Exception as ex:
            print(f"[Onboarding] session.store error: {ex}")

        if callable(on_dismiss):
            on_dismiss({"skipped": skipped, "goal_minutes": state["goal_minutes"], "study_focus": state["study_focus"]})

    def handle_skip(e=None):
        page.run_task(_dismiss_async, True)

    def handle_next(e=None):
        if state.get("is_animating"):
            return
        if state["index"] == total_screens - 1:
            page.run_task(_dismiss_async, False)
        else:
            go_to(state["index"] + 1)

    # ── 1-TO-1 FLOATING BOTTOM APP BAR MOCKUP (SLIDES 1-3 ONLY) ──────────────
    def _build_frame_bottom_nav(active_route: str) -> ft.Container:
        """1-to-1 replica of the app's persistent floating island capsule with exact active tab."""
        nav_specs = [
            (ft.Icons.HOME_ROUNDED, "/dashboard", "Home"),
            (ft.Icons.CHAT_BUBBLE_ROUNDED, "/nu-chat", "Chat"),
            (ft.Icons.SCHOOL_ROUNDED, "/courses", "Learn"),
            (ft.Icons.NOTIFICATIONS_ROUNDED, "/notifications", "Alerts"),
            (ft.Icons.PERSON_ROUNDED, "/profile", "Profile"),
        ]

        nav_items = []
        for icon_c, route_c, label_c in nav_specs:
            is_active = (active_route == route_c)
            if is_active:
                item_content = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=5),
                    border_radius=ft.BorderRadius.all(16),
                    bgcolor=ft.Colors.with_opacity(0.14, ft.Colors.PRIMARY),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.30, ft.Colors.PRIMARY)),
                    content=ft.Row(
                        spacing=5,
                        tight=True,
                        controls=[
                            ft.Icon(icon_c, size=15, color=ft.Colors.PRIMARY),
                            ft.Text(label_c, size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                        ],
                    ),
                )
            else:
                item_content = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=5),
                    border_radius=ft.BorderRadius.all(16),
                    content=ft.Icon(icon_c, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                )
            nav_items.append(item_content)

        is_desk = is_desktop()
        capsule = ft.Container(
            padding=ft.Padding.symmetric(horizontal=8 if not is_desk else 10, vertical=2.5 if not is_desk else 3),
            border_radius=ft.BorderRadius.all(24),
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.14, ft.Colors.ON_SURFACE)),
            shadow=ft.BoxShadow(
                blur_radius=12,
                color=ft.Colors.with_opacity(0.10, ft.Colors.BLACK),
                offset=ft.Offset(0, 3),
            ),
            content=ft.Row(
                spacing=5 if not is_desk else 6,
                tight=True,
                alignment=ft.MainAxisAlignment.CENTER,
                controls=nav_items,
            ),
        )

        return ft.Container(
            alignment=ft.Alignment.CENTER,
            padding=ft.Padding.only(top=3 if not is_desk else 6, bottom=2),
            content=capsule,
        )

    # ── Top Navigation Bar: Nu Age Tour Pill + Step Badge + Skip ──────────────
    step_indicator_txt = ft.Text(
        f"1 of {total_screens}",
        size=11.5,
        weight=ft.FontWeight.W_700,
        color=ft.Colors.PRIMARY,
    )

    tour_badge = ft.Container(
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        border_radius=ft.BorderRadius.all(8),
        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
        content=ft.Row(
            spacing=5,
            tight=True,
            controls=[
                ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=13, color=ft.Colors.PRIMARY),
                step_indicator_txt,
            ],
        ),
    )

    skip_btn = ft.TextButton(
        content=ft.Text(
            "Skip Tour",
            size=13,
            weight=ft.FontWeight.W_700,
            color=ft.Colors.ON_SURFACE_VARIANT,
        ),
        style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=10, vertical=4)),
        on_click=handle_skip,
    )

    # ── Primary Action Button ─────────────────────────────────────────────────
    action_btn_text = ft.Text(
        ONBOARDING_SCREENS[0]["btn_text"],
        size=14 if is_desktop() else 13,
        weight=ft.FontWeight.W_800,
        color=ft.Colors.ON_PRIMARY,
    )

    action_btn = ft.Container(
        height=48 if is_desktop() else 42,
        border_radius=ft.BorderRadius.all(12),
        bgcolor=ft.Colors.PRIMARY,
        alignment=ft.Alignment.CENTER,
        ink=True,
        on_click=handle_next,
        content=action_btn_text,
    )

    # ── Expanding Segmented Pill Indicators ───────────────────────────────────
    segment_controls = []
    for i in range(total_screens):
        is_active = (i == 0)
        seg = ft.Container(
            width=32 if is_active else 10,
            height=5,
            border_radius=ft.BorderRadius.all(2.5),
            bgcolor=ft.Colors.PRIMARY if is_active else ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
            animate=ft.Animation(260, ft.AnimationCurve.EASE_OUT_CUBIC),
            ink=True,
            on_click=lambda e, idx=i: go_to(idx),
        )
        segment_controls.append(seg)

    segments_row = ft.Row(
        spacing=6,
        alignment=ft.MainAxisAlignment.CENTER,
        controls=segment_controls,
    )

    def update_segments(active_idx: int):
        step_indicator_txt.value = f"{active_idx + 1} of {total_screens}"
        for i, seg in enumerate(segment_controls):
            active = (i == active_idx)
            seg.width = 32 if active else 10
            seg.bgcolor = ft.Colors.PRIMARY if active else ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE)

    slide_box = ft.Container(
        opacity=1.0,
        animate_opacity=ft.Animation(140, ft.AnimationCurve.EASE_OUT),
    )

    # ── SLIDE 1 REAL VIEW: Dashboard & Self-Study Hub Component ───────────────
    def _build_self_study_view() -> ft.Control:
        """1-to-1 representation of the Dashboard featuring the Self-Study Hub card."""
        is_desk = is_desktop()
        dash_header = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Column(
                    spacing=2,
                    tight=True,
                    controls=[
                        ft.Text("Welcome back, Scholar 👋", size=13 if not is_desk else 14, weight=ft.FontWeight.BOLD),
                        ft.Text("Here's your learning overview for today", size=9.5 if not is_desk else 10, color=ft.Colors.ON_SURFACE_VARIANT),
                    ],
                ),
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=ft.BorderRadius.all(8),
                    bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.AMBER_700),
                    content=ft.Row(
                        spacing=4,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED, size=13, color=ft.Colors.AMBER_700),
                            ft.Text("5 Days Streak", size=9.5 if not is_desk else 10, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_700),
                        ],
                    ),
                ),
            ],
        )

        def _pill(icon, label):
            return ft.Container(
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                border_radius=ft.BorderRadius.all(6),
                bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                content=ft.Row(
                    spacing=4,
                    tight=True,
                    controls=[
                        ft.Icon(icon, size=12, color=ft.Colors.PRIMARY),
                        ft.Text(label, size=9.5 if not is_desk else 10, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                    ],
                ),
            )

        card_art = ft.Container(
            width=70 if not is_desk else 95,
            height=55 if not is_desk else 75,
            alignment=ft.Alignment.CENTER,
            content=ft.Image(src="study_hub.png", fit=ft.BoxFit.CONTAIN),
        )

        hub_card = ft.Container(
            padding=10 if not is_desk else 13,
            border_radius=ft.BorderRadius.all(14),
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
            shadow=ft.BoxShadow(blur_radius=12, color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK), offset=ft.Offset(0, 3)),
            content=ft.Column(
                spacing=7,
                tight=True,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Column(
                                expand=True,
                                spacing=2,
                                controls=[
                                    ft.Row(
                                        spacing=5,
                                        tight=True,
                                        controls=[
                                            ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=14, color=ft.Colors.PRIMARY),
                                            ft.Text("Self-Study Hub", size=13.5 if not is_desk else 14.5, weight=ft.FontWeight.W_800),
                                        ],
                                    ),
                                    ft.Text(
                                        "Turn materials into flashcards, adaptive quizzes & timed exam simulators.",
                                        size=9.5 if not is_desk else 10,
                                        color=ft.Colors.GREY_600,
                                        max_lines=2,
                                    ),
                                ],
                            ),
                            card_art,
                        ],
                    ),
                    ft.Row(
                        spacing=5,
                        wrap=True,
                        controls=[
                            _pill(ft.Icons.STYLE_ROUNDED, "Flashcards"),
                            _pill(ft.Icons.QUIZ_ROUNDED, "Quick Quiz"),
                            _pill(ft.Icons.TIMER_ROUNDED, "Exam Sim"),
                            _pill(ft.Icons.PSYCHOLOGY_ROUNDED, "AI Notes"),
                        ],
                    ),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=7, vertical=2),
                                border_radius=ft.BorderRadius.all(6),
                                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                                content=ft.Row(
                                    spacing=4,
                                    tight=True,
                                    controls=[
                                        ft.Icon(ft.Icons.TOUCH_APP_ROUNDED, size=11, color=ft.Colors.PRIMARY),
                                        ft.Text("1-Tap to /self-study", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                                    ],
                                ),
                            ),
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                                border_radius=ft.BorderRadius.all(8),
                                bgcolor=ft.Colors.PRIMARY,
                                content=ft.Row(
                                    spacing=4,
                                    tight=True,
                                    controls=[
                                        ft.Text("Launch Study Hub", size=10.5, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_PRIMARY),
                                        ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=12, color=ft.Colors.ON_PRIMARY),
                                    ],
                                ),
                            ),
                        ],
                    ),
                ],
            ),
        )

        return ft.Column(
            spacing=8,
            controls=[
                dash_header,
                hub_card,
            ],
        )

    # ── SLIDE 2 REAL VIEW: Exact Learn Screen matching User's Image 1 ─────────
    def _build_courses_view() -> ft.Control:
        """1-to-1 recreation of Image 1 (Learn Tab, 6 Squircles, 2x2 Grid on desktop, Single-column on mobile)."""
        is_desk = is_desktop()
        learn_title_col = ft.Column(
            spacing=1,
            tight=True,
            expand=True,
            controls=[
                ft.Row(
                    spacing=5 if not is_desk else 7,
                    tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.SCHOOL_ROUNDED, size=16 if not is_desk else 19, color=ft.Colors.PRIMARY),
                        ft.Text("Learn", size=15 if not is_desk else 17, weight=ft.FontWeight.W_800),
                    ],
                ),
                *(
                    [ft.Text("Continue your ongoing courses & offline library", size=10, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)]
                    if is_desk else []
                ),
            ],
        )

        offline_lib_chip = ft.Container(
            padding=ft.Padding.symmetric(horizontal=6 if not is_desk else 8, vertical=2.5 if not is_desk else 3.5),
            border_radius=ft.BorderRadius.all(8),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.GREEN_600)),
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.GREEN_600),
            content=ft.Row(
                spacing=3 if not is_desk else 4,
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=10 if not is_desk else 11, color=ft.Colors.GREEN_600),
                    ft.Text(
                        "Offline" if not is_desk else "Offline Library",
                        size=9 if not is_desk else 9.5,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.GREEN_600,
                        no_wrap=True,
                    ),
                ],
            ),
        )

        learn_header = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                learn_title_col,
                offline_lib_chip,
            ],
        )

        def _learn_tab(label: str, count: str = None, active: bool = False, icon=None):
            bg = ft.Colors.PRIMARY if active else ft.Colors.TRANSPARENT
            border_c = ft.Colors.PRIMARY if active else ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE)
            text_c = ft.Colors.ON_PRIMARY if active else ft.Colors.ON_SURFACE
            icon_c = ft.Colors.ON_PRIMARY if active else ft.Colors.ON_SURFACE_VARIANT

            controls = []
            if icon:
                controls.append(ft.Icon(icon, size=11, color=icon_c))
            controls.append(ft.Text(label, size=9.5, weight=ft.FontWeight.BOLD if active else ft.FontWeight.W_600, color=text_c))
            if count:
                controls.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=4, vertical=0.5),
                        border_radius=ft.BorderRadius.all(6),
                        bgcolor=ft.Colors.with_opacity(0.20, ft.Colors.WHITE) if active else ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                        content=ft.Text(count, size=8, weight=ft.FontWeight.BOLD, color=text_c),
                    )
                )

            return ft.Container(
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                border_radius=ft.BorderRadius.all(8),
                bgcolor=bg,
                border=ft.Border.all(1, border_c),
                content=ft.Row(spacing=3, tight=True, controls=controls),
            )

        tab_strip = ft.Row(
            spacing=5,
            scroll=ft.ScrollMode.HIDDEN,
            controls=[
                _learn_tab("My Courses", "22", active=True, icon=ft.Icons.AUTO_STORIES_ROUNDED),
                _learn_tab("Explore", "4", icon=ft.Icons.EXPLORE_ROUNDED),
                _learn_tab("Playground", icon=ft.Icons.TERMINAL_ROUNDED),
                _learn_tab("Playlists", "2", icon=ft.Icons.PLAYLIST_PLAY_ROUNDED),
                _learn_tab("Completed", "8", icon=ft.Icons.CHECK_CIRCLE_ROUNDED),
                _learn_tab("Spaces", "1", icon=ft.Icons.HUB_ROUNDED),
            ],
        )

        def _make_exact_course_card(
            category: str,
            title: str,
            subtitle: str,
            modules_meta: str,
            progress_pct: int,
            modules_ratio: str,
            card_bg: str,
            badge_bg: str,
            accent_c: str,
            art_icon: str,
        ) -> ft.Container:
            is_dark = page.theme_mode == ft.ThemeMode.DARK
            effective_bg = card_bg if not is_dark else ft.Colors.with_opacity(0.08, accent_c)

            cat_pill = ft.Container(
                padding=ft.Padding.symmetric(horizontal=7, vertical=2),
                border_radius=ft.BorderRadius.all(10),
                bgcolor=badge_bg if not is_dark else ft.Colors.with_opacity(0.16, accent_c),
                content=ft.Text(category, size=8.5, weight=ft.FontWeight.W_700, color=accent_c),
            )

            art_thumb = ft.Container(
                width=42,
                height=42,
                border_radius=ft.BorderRadius.all(8),
                bgcolor=ft.Colors.with_opacity(0.12, accent_c),
                alignment=ft.Alignment.CENTER,
                content=ft.Icon(art_icon, size=22, color=accent_c),
            )

            progress_bar = ft.ProgressBar(
                value=progress_pct / 100.0,
                height=3.5,
                color=ft.Colors.BLACK87 if not is_dark else accent_c,
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE),
                border_radius=ft.BorderRadius.all(2),
            )

            btn_save = ft.Container(
                padding=ft.Padding.symmetric(horizontal=7, vertical=2),
                border_radius=ft.BorderRadius.all(10),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.28, accent_c)),
                content=ft.Row(
                    spacing=2,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.BOOKMARK_BORDER_ROUNDED, size=10, color=accent_c),
                        ft.Text("Save", size=9, weight=ft.FontWeight.W_600, color=accent_c),
                    ],
                ),
            )

            btn_continue = ft.Container(
                padding=ft.Padding.symmetric(horizontal=10, vertical=3.5),
                border_radius=ft.BorderRadius.all(10),
                bgcolor=ft.Colors.BLACK if not is_dark else ft.Colors.PRIMARY,
                content=ft.Text("Continue", size=9.5, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
            )

            return ft.Container(
                expand=is_desk,
                padding=10,
                border_radius=ft.BorderRadius.all(12),
                bgcolor=effective_bg,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)),
                content=ft.Column(
                    spacing=5,
                    tight=True,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.START,
                            controls=[
                                ft.Column(
                                    expand=True,
                                    spacing=3,
                                    controls=[
                                        cat_pill,
                                        ft.Text(title, size=11, weight=ft.FontWeight.W_800, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                        ft.Text(subtitle, size=8.5, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                        ft.Text(modules_meta, size=8.5, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ],
                                ),
                                art_thumb,
                            ],
                        ),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text("Progress", size=8.5, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(f"{progress_pct}%", size=8.5, weight=ft.FontWeight.BOLD),
                            ],
                        ),
                        progress_bar,
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Text(f"Modules: {modules_ratio}", size=9, weight=ft.FontWeight.W_600),
                                ft.Row(spacing=5, tight=True, controls=[btn_save, btn_continue]),
                            ],
                        ),
                    ],
                ),
            )

        card_1 = _make_exact_course_card(
            category="Focus & Academic Hacks",
            title="Project and Research Writing for Beginners",
            subtitle="Identify and Formulate a clear research problem, gap in the literature...",
            modules_meta="📖 5 modules · 🕒 ~7.5 hrs",
            progress_pct=50,
            modules_ratio="2/5",
            card_bg="#FFFBEB",
            badge_bg="#FEF3C7",
            accent_c="#D97706",
            art_icon=ft.Icons.EDIT_NOTE_ROUNDED,
        )

        card_2 = _make_exact_course_card(
            category="Survival & Life Skills",
            title="Stay Safe Online: Cybersecurity Awareness",
            subtitle="Create and manage strong, unique passwords with a password manager.",
            modules_meta="📖 7 modules · 🕒 ~10.5 hrs",
            progress_pct=18,
            modules_ratio="1/7",
            card_bg="#EFF6FF",
            badge_bg="#DBEAFE",
            accent_c="#2563EB",
            art_icon=ft.Icons.SECURITY_ROUNDED,
        )

        card_3 = _make_exact_course_card(
            category="Programming",
            title="Frontend Development with React",
            subtitle="Explain component-based architecture and why React uses it.",
            modules_meta="📖 5 modules · 🕒 ~7.5 hrs",
            progress_pct=15,
            modules_ratio="1/5",
            card_bg="#F0FDF4",
            badge_bg="#DCFCE7",
            accent_c="#16A34A",
            art_icon=ft.Icons.DEVELOPER_MODE_ROUNDED,
        )

        card_4 = _make_exact_course_card(
            category="Programming",
            title="Web Development Foundations",
            subtitle="Explain how the internet, browsers, and HTTP requests work together.",
            modules_meta="📖 4 modules · 🕒 ~6 hrs",
            progress_pct=14,
            modules_ratio="1/4",
            card_bg="#F0FDF4",
            badge_bg="#DCFCE7",
            accent_c="#16A34A",
            art_icon=ft.Icons.WEB_ROUNDED,
        )

        if is_desk:
            grid_view = ft.Column(
                spacing=6,
                controls=[
                    ft.Row(spacing=6, controls=[card_1, card_2]),
                    ft.Row(spacing=6, controls=[card_3, card_4]),
                ],
            )
        else:
            # Mobile: 1 prominent full-width course card so no scrolling is needed
            grid_view = ft.Column(
                spacing=6,
                tight=True,
                controls=[card_1],
            )

        return ft.Column(
            spacing=8,
            controls=[
                learn_header,
                tab_strip,
                grid_view,
            ],
        )

    # ── SLIDE 3 REAL VIEW: Exact Nu Chat View (Pure Mock Names) ──────────────
    def _build_chat_view() -> ft.Control:
        """1-to-1 recreation of Image 2 (Nu Chat Left Channel List with MOCK names & Empty State)."""
        chat_header = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(
                    spacing=6,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.CHAT_BUBBLE_ROUNDED, size=16, color=ft.Colors.PRIMARY),
                        ft.Text("Nu Chat", size=14, weight=ft.FontWeight.W_800),
                    ],
                ),
                ft.Container(
                    width=22,
                    height=22,
                    border_radius=ft.BorderRadius.all(6),
                    bgcolor=ft.Colors.PRIMARY,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.ADD_ROUNDED, size=15, color=ft.Colors.WHITE),
                ),
            ],
        )

        search_box = ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=5),
            border_radius=ft.BorderRadius.all(8),
            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
            content=ft.Row(
                spacing=6,
                controls=[
                    ft.Icon(ft.Icons.SEARCH_ROUNDED, size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text("Search conversations...", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
            ),
        )

        def _make_chat_item(title: str, snippet: str, time_str: str, avatar_c: str, letter: str = None, icon=None, is_online=False):
            avatar_content = ft.Text(letter, size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE) if letter else ft.Icon(icon, size=14, color=ft.Colors.WHITE)
            avatar_box = ft.Stack(
                controls=[
                    ft.CircleAvatar(radius=14, bgcolor=avatar_c, content=avatar_content),
                    *(
                        [ft.Container(
                            width=7,
                            height=7,
                            border_radius=ft.BorderRadius.all(3.5),
                            bgcolor=ft.Colors.GREEN_500,
                            border=ft.Border.all(1, ft.Colors.SURFACE),
                            right=0,
                            bottom=0,
                        )] if is_online else []
                    ),
                ],
            )

            return ft.Container(
                padding=ft.Padding.symmetric(horizontal=4, vertical=4),
                border_radius=ft.BorderRadius.all(8),
                content=ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        avatar_box,
                        ft.Column(
                            expand=True,
                            spacing=1,
                            tight=True,
                            controls=[
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Text(title, size=10.5, weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                        ft.Text(time_str, size=8.5, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ],
                                ),
                                ft.Text(snippet, size=9, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ],
                        ),
                    ],
                ),
            )

        # 100% Mock names (Zero actual database names!)
        chat_items = [
            _make_chat_item("Machine Learning Study Group", "In AI, a baseline is a reference point...", "6:21 PM", "#0F2B48", icon=ft.Icons.AUTO_AWESOME_ROUNDED),
            _make_chat_item("Algorithms & Data Structures", "Anyone reviewing dynamic programming?", "4:25 PM", "#1B5E20", icon=ft.Icons.GROUPS_ROUNDED),
            _make_chat_item("Public Speaking Skills Cohort", "Slides uploaded for next week's presentation!", "2:39 PM", "#C2410C", icon=ft.Icons.RECORD_VOICE_OVER_ROUNDED),
            _make_chat_item("Sarah Jenkins", "⚔️ Ready for a Study Duel? Let's test our knowledge!", "5:21 PM", "#0D5C75", letter="SJ", is_online=True),
            _make_chat_item("David Chen", "Sounds great, let's review after class!", "11:55 AM", "#1E3A1E", letter="DC", is_online=True),
            _make_chat_item("Circuit Analysis Lab Group", "@all how is lab exercise 3 going?", "5:28 PM", "#1E1B4B", icon=ft.Icons.DEVELOPER_BOARD_ROUNDED),
        ]

        chat_fab = ft.Container(
            width=28,
            height=28,
            border_radius=ft.BorderRadius.all(14),
            bgcolor=ft.Colors.PRIMARY,
            alignment=ft.Alignment.CENTER,
            shadow=ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.20, ft.Colors.BLACK), offset=ft.Offset(0, 2)),
            content=ft.Icon(ft.Icons.EDIT_ROUNDED, size=14, color=ft.Colors.WHITE),
        )

        is_desk = is_desktop()

        if not is_desk:
            # 1-to-1 Mobile Nu Chat behavior (Full-width conversation list, no squeezed side-by-side empty state)
            mobile_chat_container = ft.Container(
                height=185,
                content=ft.Stack(
                    controls=[
                        ft.Column(
                            spacing=4,
                            controls=[
                                chat_header,
                                search_box,
                                ft.Column(chat_items[:3], spacing=2),
                            ],
                        ),
                        ft.Container(
                            right=2,
                            bottom=2,
                            content=chat_fab,
                        ),
                    ],
                ),
            )
            return ft.Column(
                spacing=6,
                tight=True,
                controls=[mobile_chat_container],
            )

        left_chat_column = ft.Container(
            width=210,
            padding=ft.Padding.only(right=8),
            border=ft.Border.only(right=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE))),
            content=ft.Stack(
                controls=[
                    ft.Column(
                        spacing=5,
                        controls=[
                            chat_header,
                            search_box,
                            ft.Column(chat_items, spacing=2),
                        ],
                    ),
                    ft.Container(
                        right=2,
                        bottom=2,
                        content=chat_fab,
                    ),
                ],
            ),
        )

        empty_state_panel = ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            padding=ft.Padding.symmetric(horizontal=10, vertical=16),
            content=ft.Column(
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED, size=42, color=ft.Colors.with_opacity(0.35, ft.Colors.ON_SURFACE)),
                    ft.Text("Nu Chat", size=17, weight=ft.FontWeight.W_800),
                    ft.Text(
                        "Select a conversation from the left to start messaging.",
                        size=10.5,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=4),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=4,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.LOCK_ROUNDED, size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text("End-to-end encrypted messaging inside Nu Age.", size=9.5, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                    ),
                ],
            ),
        )

        chat_split = ft.Row(
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[
                left_chat_column,
                empty_state_panel,
            ],
        )

        return ft.Column(
            spacing=6,
            tight=True,
            controls=[
                ft.Container(height=265, content=chat_split),
            ],
        )

    # ── SLIDE 4 REAL VIEW: Interactive Setup & Powerhouse Features Showcase ──
    def _build_goals_view() -> ft.Control:
        """Dedicated interactive setup card highlighting Streaks, In-Course AI, Audio & Duels."""
        is_desk = is_desktop()
        goal_options = [
            (15, "15 min/day", "Steady Target"),
            (30, "30 min/day", "Recommended"),
            (60, "60 min/day", "Mastery Pace"),
        ]

        def _make_goal_pill(mins: int, label: str, subtitle: str):
            selected = (state["goal_minutes"] == mins)
            bg = ft.Colors.PRIMARY if selected else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)
            fg = ft.Colors.ON_PRIMARY if selected else ft.Colors.ON_SURFACE
            sub_fg = ft.Colors.ON_PRIMARY if selected else ft.Colors.ON_SURFACE_VARIANT

            def on_pick(e):
                state["goal_minutes"] = mins
                slide_box.content = build_slide_content(3)
                safe_page_update()

            return ft.Container(
                expand=True,
                padding=ft.Padding.symmetric(horizontal=6, vertical=7 if not is_desk else 9),
                border_radius=ft.BorderRadius.all(10),
                bgcolor=bg,
                alignment=ft.Alignment.CENTER,
                ink=True,
                on_click=on_pick,
                content=ft.Column(
                    spacing=1,
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text(label, size=10.5 if not is_desk else 11.5, weight=ft.FontWeight.W_800, color=fg),
                        ft.Text(subtitle, size=8 if not is_desk else 8.5, weight=ft.FontWeight.W_600, color=sub_fg),
                    ],
                ),
            )

        goal_chips = [_make_goal_pill(m, l, s) for m, l, s in goal_options]

        focus_list = [
            "Software & Tech",
            "Health & Med",
            "Engineering & Math",
            "Business & Finance",
        ] if not is_desk else [
            "Software & Tech",
            "Medicine & Health",
            "Engineering & Math",
            "Business & Finance",
            "Law & Humanities",
            "Natural Sciences",
        ]

        def _make_focus_chip(name: str):
            selected = (state["study_focus"] == name)
            bg = ft.Colors.with_opacity(0.18, ft.Colors.PRIMARY) if selected else ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE)
            border_c = ft.Colors.PRIMARY if selected else ft.Colors.TRANSPARENT
            fg = ft.Colors.PRIMARY if selected else ft.Colors.ON_SURFACE

            def on_pick(e):
                state["study_focus"] = name
                slide_box.content = build_slide_content(3)
                safe_page_update()

            return ft.Container(
                padding=ft.Padding.symmetric(horizontal=7 if not is_desk else 8, vertical=3.5 if not is_desk else 4.5),
                border_radius=ft.BorderRadius.all(8),
                bgcolor=bg,
                border=ft.Border.all(1.2, border_c),
                ink=True,
                on_click=on_pick,
                content=ft.Text(name, size=9.5 if not is_desk else 10, weight=ft.FontWeight.W_700 if selected else ft.FontWeight.W_500, color=fg),
            )

        focus_chips = [_make_focus_chip(n) for n in focus_list]

        # Powerhouse Features Highlight Grid
        def _feature_tile(icon, title, desc, icon_color, bg_color):
            return ft.Container(
                expand=True,
                padding=ft.Padding.symmetric(horizontal=8, vertical=6 if not is_desk else 7),
                border_radius=ft.BorderRadius.all(10),
                bgcolor=bg_color,
                content=ft.Row(
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(icon, size=16 if not is_desk else 18, color=icon_color),
                        ft.Column(
                            spacing=1,
                            tight=True,
                            expand=True,
                            controls=[
                                ft.Text(title, size=10 if not is_desk else 10.5, weight=ft.FontWeight.W_800),
                                ft.Text(desc, size=8.5 if not is_desk else 9, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ],
                        ),
                    ],
                ),
            )

        tile_1 = _feature_tile(ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED, "Daily Streaks", "Earn Quest Coins", ft.Colors.AMBER_700, ft.Colors.with_opacity(0.08, ft.Colors.AMBER_700))
        tile_2 = _feature_tile(ft.Icons.AUTO_AWESOME_ROUNDED, "In-Course AI", "24/7 Lesson Tutor", ft.Colors.PRIMARY, ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY))
        tile_3 = _feature_tile(ft.Icons.HEADPHONES_ROUNDED, "Screen Reader", "Hands-free audio narration", ft.Colors.BLUE_600, ft.Colors.with_opacity(0.08, ft.Colors.BLUE_600))
        tile_4 = _feature_tile(ft.Icons.SPORTS_ESPORTS_ROUNDED, "Study Duels", "Challenge classmates", ft.Colors.PURPLE_600, ft.Colors.with_opacity(0.08, ft.Colors.PURPLE_600))

        if is_desk:
            features_grid = ft.Column(
                spacing=6,
                controls=[
                    ft.Row(spacing=6, controls=[tile_1, tile_2]),
                    ft.Row(spacing=6, controls=[tile_3, tile_4]),
                ],
            )
        else:
            # Mobile: 2 compact accelerators side-by-side (saving 60px vertical height)
            features_grid = ft.Row(
                spacing=6,
                controls=[tile_1, tile_2],
            )

        return ft.Column(
            spacing=7 if not is_desk else 9,
            tight=True,
            controls=[
                ft.Text("1. Choose Daily Target", size=10.5 if not is_desk else 11.5, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                ft.Row(spacing=5, controls=goal_chips),
                ft.Text("2. Primary Focus Area", size=10.5 if not is_desk else 11.5, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                ft.Row(spacing=4 if not is_desk else 5, wrap=True, controls=focus_chips),
                ft.Container(height=1),
                ft.Text("3. Built-in Study Accelerators", size=10.5 if not is_desk else 11.5, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                features_grid,
            ],
        )

    # ── SLEEK MACBOOK FRAME (SLIDES 1-3) & INTERACTIVE CARD (SLIDE 4) ────────
    def _render_stage_frame(idx: int) -> ft.Control:
        data = ONBOARDING_SCREENS[idx]
        gif_file = data.get("gif", "")
        img_file = data.get("image", "")

        has_gif = gif_file and os.path.exists(os.path.join("assets", gif_file))
        has_img = img_file and os.path.exists(os.path.join("assets", img_file))

        is_desk = is_desktop()
        stage_width = 495 if is_desk else None

        if idx == 3:
            # ── SLIDE 4: DEDICATED INTERACTIVE SETUP CARD (NO SCREENSHOT, NO BOTTOM NAVBAR) ──
            return ft.Container(
                width=stage_width,
                border_radius=ft.BorderRadius.all(16),
                bgcolor=ft.Colors.SURFACE,
                border=ft.Border.all(1.2, ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE)),
                shadow=ft.BoxShadow(
                    blur_radius=20,
                    color=ft.Colors.with_opacity(0.12, ft.Colors.BLACK),
                    offset=ft.Offset(0, 5),
                ),
                padding=14 if not is_desk else 16,
                content=_build_goals_view(),
            )
        elif has_gif:
            component_content = ft.Image(src=gif_file, fit=ft.BoxFit.CONTAIN, expand=True)
        elif has_img:
            component_content = ft.Image(src=img_file, fit=ft.BoxFit.CONTAIN, expand=True)
        else:
            if idx == 0:
                component_content = _build_self_study_view()
            elif idx == 1:
                component_content = _build_courses_view()
            else:
                component_content = _build_chat_view()

        # Window header with 3 dots and CLEAN TAB NAME (No long file paths!)
        window_dots = ft.Row(
            spacing=5,
            tight=True,
            controls=[
                ft.Container(width=8, height=8, border_radius=ft.BorderRadius.all(4), bgcolor="#FF5F56"),
                ft.Container(width=8, height=8, border_radius=ft.BorderRadius.all(4), bgcolor="#FFBD2E"),
                ft.Container(width=8, height=8, border_radius=ft.BorderRadius.all(4), bgcolor="#27C93F"),
            ],
        )

        window_title_bar = ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=7),
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
            border=ft.Border.only(bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE))),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    window_dots,
                    ft.Text(
                        data["tab_name"],
                        size=11,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.ON_SURFACE,
                    ),
                    ft.Container(width=28),
                ],
            ),
        )

        # Slides 1-3 have the window frame with the floating bottom app bar docked at the bottom
        stage_body = ft.Stack(
            controls=[
                ft.Container(
                    content=component_content,
                    padding=ft.Padding.only(
                        left=8 if not is_desk else 10,
                        right=8 if not is_desk else 10,
                        top=6 if not is_desk else 8,
                        bottom=46,
                    ),
                ),
                ft.Container(
                    content=_build_frame_bottom_nav(data["route_key"]),
                    bottom=3,
                    left=0,
                    right=0,
                    alignment=ft.Alignment.BOTTOM_CENTER,
                ),
            ],
        )

        return ft.Container(
            width=stage_width,
            border_radius=ft.BorderRadius.all(16),
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1.2, ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE)),
            shadow=ft.BoxShadow(
                blur_radius=20,
                color=ft.Colors.with_opacity(0.12, ft.Colors.BLACK),
                offset=ft.Offset(0, 5),
            ),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=ft.Column(
                spacing=0,
                tight=True,
                controls=[
                    window_title_bar,
                    stage_body,
                ],
            ),
        )

    # ── SLIDE CONTENT BUILDER (DESKTOP SPLIT vs MOBILE STACK) ─────────────────
    def build_slide_content(idx: int) -> ft.Control:
        data = ONBOARDING_SCREENS[idx]
        is_desk = is_desktop()

        stage_frame = _render_stage_frame(idx)

        # Guide panel elements
        step_header = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                tour_badge,
                skip_btn,
            ],
        )

        headline_text = ft.Text(
            data["title"],
            size=20 if is_desk else 15,
            weight=ft.FontWeight.W_800,
            color=ft.Colors.ON_SURFACE,
            max_lines=1 if not is_desk else 2,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        desc_text = ft.Text(
            data["desc"],
            size=12 if is_desk else 10.5,
            color=ft.Colors.ON_SURFACE_VARIANT,
            max_lines=2 if not is_desk else 3,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        # Bullets: On desktop, show all 4; on mobile, show 2 concise highlights to keep height strictly within mobile viewports
        bullet_rows = []
        active_bullets = data["bullets"] if is_desk else data["bullets"][:2]
        for b_text, b_icon in active_bullets:
            bullet_rows.append(
                ft.Row(
                    spacing=6 if not is_desk else 8,
                    tight=True,
                    controls=[
                        ft.Icon(b_icon, size=13 if not is_desk else 15, color=ft.Colors.PRIMARY),
                        ft.Text(b_text, size=10.5 if not is_desk else 12, weight=ft.FontWeight.W_500),
                    ],
                )
            )

        guide_col = ft.Column(
            spacing=4 if not is_desk else 8,
            tight=True,
            controls=[
                headline_text,
                desc_text,
                ft.Column(bullet_rows, spacing=3 if not is_desk else 5, tight=True),
            ],
        )

        bottom_controls = ft.Column(
            spacing=5 if not is_desk else 8,
            tight=True,
            controls=[
                action_btn,
                segments_row,
            ],
        )

        if is_desk:
            # Laptop & Desktop: Fitted Stage Frame on Left + Flexible Guide Deck on Right
            return ft.Row(
                key=f"desk_{idx}",
                spacing=22,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    # Fitted stage frame (exact 495px width with slight border)
                    stage_frame,
                    # Flexible Guide & Action CTAs
                    ft.Container(
                        expand=True,
                        content=ft.Column(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            spacing=14,
                            controls=[
                                step_header,
                                guide_col,
                                bottom_controls,
                            ],
                        ),
                    ),
                ],
            )
        else:
            # Mobile: Snug Single-Screen Deck (Zero scrolling required!)
            return ft.Column(
                key=f"mob_{idx}",
                spacing=7,
                tight=True,
                controls=[
                    step_header,
                    stage_frame,
                    guide_col,
                    bottom_controls,
                ],
            )

    # Populate initial content into slide container
    slide_box.content = build_slide_content(0)

    # ── Horizontal Swipe Gesture Detection ────────────────────────────────────
    def handle_drag_end(e):
        velocity = getattr(e, "primary_velocity", 0) or 0
        if velocity < -200:
            if state["index"] < total_screens - 1:
                go_to(state["index"] + 1)
        elif velocity > 200:
            if state["index"] > 0:
                go_to(state["index"] - 1)

    gesture_detector = ft.GestureDetector(
        content=slide_box,
        on_horizontal_drag_end=handle_drag_end,
    )

    async def _transition_to(target_idx: int):
        if state.get("is_animating"):
            return
        if target_idx == state["index"]:
            return
        target_idx = max(0, min(total_screens - 1, target_idx))
        state["is_animating"] = True
        try:
            # 1. Smoothly fade out the outgoing slide completely (zero text overlap!)
            slide_box.opacity = 0.0
            safe_page_update()
            await asyncio.sleep(0.14)

            # 2. Swap content while 100% transparent
            state["index"] = target_idx
            screen_data = ONBOARDING_SCREENS[target_idx]
            slide_box.content = build_slide_content(target_idx)
            action_btn_text.value = screen_data["btn_text"]
            update_segments(target_idx)
            safe_page_update()

            # 3. Smoothly fade in the new slide
            slide_box.opacity = 1.0
            safe_page_update()
            await asyncio.sleep(0.14)
        finally:
            state["is_animating"] = False

    def go_to(index: int):
        page.run_task(_transition_to, index)

    # ── Main Card Container ───────────────────────────────────────────────────
    card_container = ft.Container(
        width=get_card_width(),
        bgcolor=ft.Colors.SURFACE,
        border_radius=ft.BorderRadius.all(22 if is_desktop() else 18),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=32,
            color=ft.Colors.with_opacity(0.28, ft.Colors.BLACK),
            offset=ft.Offset(0, 8),
        ),
        padding=ft.Padding.symmetric(
            horizontal=20 if is_desktop() else 14,
            vertical=16 if is_desktop() else 10,
        ),
        content=gesture_detector,
        animate=ft.Animation(200, ft.AnimationCurve.DECELERATE),
    )

    # Responsive resize handler
    previous_on_resized = page.on_resize

    def handle_resize(e=None):
        card_container.width = get_card_width()
        card_container.padding = ft.Padding.symmetric(
            horizontal=20 if is_desktop() else 14,
            vertical=16 if is_desktop() else 10,
        )
        card_container.border_radius = ft.BorderRadius.all(22 if is_desktop() else 18)
        slide_box.content = build_slide_content(state["index"])
        safe_page_update()
        if callable(previous_on_resized):
            previous_on_resized(e)

    page.on_resized = handle_resize

    # Full overlay clamped nicely within viewport
    overlay = ft.Container(
        expand=True,
        bgcolor=ft.Colors.with_opacity(0.68, ft.Colors.BLACK),
        alignment=ft.Alignment.CENTER,
        padding=ft.Padding.symmetric(horizontal=16, vertical=16),
        content=card_container,
    )

    return overlay
