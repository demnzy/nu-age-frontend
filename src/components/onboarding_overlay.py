"""Sleek, adaptive onboarding carousel for Nu Age LMS.

Supports responsive multi-device layouts:
  - Laptop / Desktop (>= 880px): Spacious presentation deck
      - Top Bar: Nu-Age logo (assets/icon.png) pinned to the absolute top-left, step badge & skip on top-right.
      - Slides 1-3: MacBook App Frame on left + Scannable Highlights & CTAs on right.
      - Slide 4: Dedicated, graphically beautiful interactive setup form (Pace cards, focus chips, habit boosters).
  - Mobile & Tablet (< 880px): Centered single-column vertical deck with touch swipe gestures.
"""

import os
import asyncio
import flet as ft

# ─────────────────────────────────────────────────────────────────────────────
# 4 ONBOARDING SCREENS CONFIGURATION (Punchy, Concise & Scannable)
# ─────────────────────────────────────────────────────────────────────────────
ONBOARDING_SCREENS = [
    {
        "step_label": "Self-Study Hub",
        "tab_name": "Dashboard",
        "route_key": "/dashboard",
        "title": "Notes to Decks & Quizzes",
        "desc": "Turn lecture notes and PDFs into active-recall flashcards and timed mock exams in seconds.",
        "bullets": [
            ("Active Recall Decks", ft.Icons.STYLE_ROUNDED),
            ("Practice Quizzes", ft.Icons.QUIZ_ROUNDED),
            ("Timed CBT Exams", ft.Icons.TIMER_ROUNDED),
            ("1-Tap Dashboard Launch", ft.Icons.TOUCH_APP_ROUNDED),
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
        "title": "Course Tracks & Offline Access",
        "desc": "Structured syllabus roadmaps with zero-data offline reading and cohort study spaces.",
        "bullets": [
            ("Tracked Modules", ft.Icons.CHECK_CIRCLE_ROUNDED),
            ("Zero-Data Offline", ft.Icons.WIFI_OFF_ROUNDED),
            ("Course Spaces", ft.Icons.GROUPS_ROUNDED),
            ("Interactive Drills", ft.Icons.BOLT_ROUNDED),
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
        "title": "Peer Chat & Nu Owl AI",
        "desc": "Study in course channels and get 24/7 instant homework explanations from Nu Owl AI.",
        "bullets": [
            ("Classmate Channels", ft.Icons.CHAT_BUBBLE_ROUNDED),
            ("24/7 AI Homework Tutor", ft.Icons.SMART_TOY_ROUNDED),
            ("Encrypted Messaging", ft.Icons.LOCK_ROUNDED),
            ("Notes & Code Sharing", ft.Icons.ATTACH_FILE_ROUNDED),
        ],
        "gif": "onboarding_chat.gif",
        "image": "onboarding_chat.png",
        "accent": ft.Colors.INDIGO_600,
        "badge_bg": "#EEF2FF",
        "btn_text": "Set Your Practice →",
    },
    {
        "step_label": "Personalize Goals",
        "tab_name": "Daily Habit",
        "route_key": "/profile",
        "title": "Set Your Daily Practice",
        "desc": "Pick your target study pace to personalize streak rewards and smart practice reminders.",
        "bullets": [
            ("Daily Streak Shields", ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED),
            ("Nu Owl Study Copilot", ft.Icons.AUTO_AWESOME_ROUNDED),
            ("Audio Screen Reader", ft.Icons.HEADPHONES_ROUNDED),
            ("Study Duels & Quests", ft.Icons.SPORTS_ESPORTS_ROUNDED),
        ],
        "gif": "",
        "image": "",
        "accent": ft.Colors.AMBER_700,
        "badge_bg": "#FFFBEB",
        "btn_text": "Launch Nu-Age 🚀",
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
            return min(940.0, max(800.0, w * 0.72))
        elif w >= 600:
            return min(540.0, max(460.0, w * 0.86))
        else:
            return min(440.0, max(300.0, w - 24.0))

    def safe_page_update():
        try:
            page.update()
        except Exception:
            pass

    async def _dismiss_async(skipped: bool = False):
        if state["dismissed"]:
            return
        state["dismissed"] = True

        # Unset dev force flag so it doesn't immediately bounce back
        try:
            import src.onboarding as ob_module
            ob_module.FORCE_SHOW_ONBOARDING = False
        except Exception:
            pass

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
            try:
                res = on_dismiss({"skipped": skipped, "goal_minutes": state["goal_minutes"], "study_focus": state["study_focus"]})
                if asyncio.iscoroutine(res):
                    await res
            except Exception as ex:
                print(f"[Onboarding] on_dismiss error: {ex}")

        has_token = None
        try:
            if hasattr(page, "shared_preferences"):
                has_token = await page.shared_preferences.get("auth_token")
        except Exception:
            has_token = None

        target = "/dashboard" if has_token else "/login"
        page.route = target
        try:
            await page.push_route(target)
        except Exception:
            page.navigate(target)

        try:
            if hasattr(page, "on_route_change") and callable(page.on_route_change):
                await page.on_route_change(None)
            page.update()
        except Exception as ex:
            print(f"[Onboarding] route navigation error: {ex}")

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
                    padding=ft.Padding.symmetric(horizontal=12, vertical=4),
                    border_radius=ft.BorderRadius.all(16),
                    bgcolor=ft.Colors.with_opacity(0.14, ft.Colors.PRIMARY),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.30, ft.Colors.PRIMARY)),
                    content=ft.Row(
                        spacing=5,
                        tight=True,
                        controls=[
                            ft.Icon(icon_c, size=14, color=ft.Colors.PRIMARY),
                            ft.Text(label_c, size=10.5, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                        ],
                    ),
                )
            else:
                item_content = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=ft.BorderRadius.all(16),
                    content=ft.Icon(icon_c, size=15, color=ft.Colors.ON_SURFACE_VARIANT),
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
            padding=ft.Padding.only(top=3 if not is_desk else 5, bottom=2),
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

    skip_btn = ft.Container(
        padding=ft.Padding.symmetric(horizontal=10, vertical=5),
        border_radius=ft.BorderRadius.all(8),
        bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
        ink=True,
        on_click=handle_skip,
        content=ft.Text(
            "Skip Tour",
            size=12,
            weight=ft.FontWeight.W_700,
            color=ft.Colors.ON_SURFACE_VARIANT,
        ),
    )

    # ── Primary Action Button ─────────────────────────────────────────────────
    action_btn_text = ft.Text(
        ONBOARDING_SCREENS[0]["btn_text"],
        size=13.5 if is_desktop() else 13,
        weight=ft.FontWeight.W_800,
        color=ft.Colors.ON_PRIMARY,
    )

    action_btn = ft.Container(
        height=46 if is_desktop() else 42,
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
            width=30 if is_active else 10,
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
            seg.width = 30 if active else 10
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
            width=70 if not is_desk else 90,
            height=55 if not is_desk else 70,
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

    # ── SLIDE 2 REAL VIEW: Spacious Learn Screen (Un-cramped on Laptop) ──────
    def _build_courses_view() -> ft.Control:
        """Spacious Learn Tab representation with clear hierarchy and generous breathing room."""
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
                    [ft.Text("Continue syllabus modules & offline library", size=10, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)]
                    if is_desk else []
                ),
            ],
        )

        offline_lib_chip = ft.Container(
            padding=ft.Padding.symmetric(horizontal=7 if not is_desk else 8, vertical=2.5 if not is_desk else 3.5),
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
                        padding=ft.Padding.symmetric(horizontal=5, vertical=1),
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

        # Clean 3-tab selector on desktop avoiding crowded cramming
        tab_strip = ft.Row(
            spacing=6,
            controls=[
                _learn_tab("My Courses", "12", active=True, icon=ft.Icons.AUTO_STORIES_ROUNDED),
                _learn_tab("Explore", "4", icon=ft.Icons.EXPLORE_ROUNDED),
                _learn_tab("Completed", "8", icon=ft.Icons.CHECK_CIRCLE_ROUNDED),
            ],
        )

        def _make_spacious_course_card(
            category: str,
            title: str,
            subtitle: str,
            modules_meta: str,
            progress_pct: int,
            modules_ratio: str,
            accent_c: str,
            art_icon: str,
        ) -> ft.Container:
            is_dark = page.theme_mode == ft.ThemeMode.DARK

            cat_pill = ft.Container(
                padding=ft.Padding.symmetric(horizontal=7, vertical=2),
                border_radius=ft.BorderRadius.all(8),
                bgcolor=ft.Colors.with_opacity(0.12, accent_c),
                content=ft.Text(category, size=8.5, weight=ft.FontWeight.W_700, color=accent_c),
            )

            art_thumb = ft.Container(
                width=38 if not is_desk else 44,
                height=38 if not is_desk else 44,
                border_radius=ft.BorderRadius.all(10),
                bgcolor=ft.Colors.with_opacity(0.12, accent_c),
                alignment=ft.Alignment.CENTER,
                content=ft.Icon(art_icon, size=20 if not is_desk else 24, color=accent_c),
            )

            progress_bar = ft.ProgressBar(
                value=progress_pct / 100.0,
                height=4,
                color=ft.Colors.PRIMARY if is_dark else accent_c,
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE),
                border_radius=ft.BorderRadius.all(2),
            )

            btn_continue = ft.Container(
                padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                border_radius=ft.BorderRadius.all(8),
                bgcolor=ft.Colors.PRIMARY,
                content=ft.Row(
                    spacing=3,
                    tight=True,
                    controls=[
                        ft.Text("Continue", size=9.5, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_PRIMARY),
                        ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=11, color=ft.Colors.ON_PRIMARY),
                    ],
                ),
            )

            return ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=9),
                border_radius=ft.BorderRadius.all(12),
                bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
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
                                    spacing=2,
                                    controls=[
                                        cat_pill,
                                        ft.Text(title, size=12 if is_desk else 11, weight=ft.FontWeight.W_800, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                        ft.Text(subtitle, size=9 if is_desk else 8.5, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                    ],
                                ),
                                art_thumb,
                            ],
                        ),
                        progress_bar,
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Text(f"{modules_meta} · {progress_pct}% completed ({modules_ratio})", size=8.5 if not is_desk else 9, color=ft.Colors.ON_SURFACE_VARIANT),
                                btn_continue,
                            ],
                        ),
                    ],
                ),
            )

        card_1 = _make_spacious_course_card(
            category="Programming & Tech",
            title="Frontend Development with React",
            subtitle="Component architecture, hooks, and responsive UX design",
            modules_meta="📖 6 modules",
            progress_pct=65,
            modules_ratio="4/6",
            accent_c=ft.Colors.PRIMARY,
            art_icon=ft.Icons.DEVELOPER_MODE_ROUNDED,
        )

        card_2 = _make_spacious_course_card(
            category="Academic Foundations",
            title="Project and Research Writing",
            subtitle="Formulate research problems, literature review, and citations",
            modules_meta="📖 5 modules",
            progress_pct=20,
            modules_ratio="1/5",
            accent_c=ft.Colors.AMBER_700,
            art_icon=ft.Icons.EDIT_NOTE_ROUNDED,
        )

        if is_desk:
            # Laptop: 2 spacious, clean course cards stacked vertically with generous breathing room
            course_cards_view = ft.Column(
                spacing=8,
                tight=True,
                controls=[card_1, card_2],
            )
        else:
            # Mobile: 1 hero course card so no scrolling or cramping occurs
            course_cards_view = ft.Column(
                spacing=6,
                tight=True,
                controls=[card_1],
            )

        return ft.Column(
            spacing=8,
            controls=[
                learn_header,
                tab_strip,
                course_cards_view,
            ],
        )

    # ── SLIDE 3 REAL VIEW: Exact Nu Chat View (Pure Mock Names) ──────────────
    def _build_chat_view() -> ft.Control:
        """1-to-1 recreation of Nu Chat Left Channel List with MOCK names & Empty State."""
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

        chat_items = [
            _make_chat_item("Machine Learning Study Group", "In AI, a baseline is a reference point...", "6:21 PM", "#0F2B48", icon=ft.Icons.AUTO_AWESOME_ROUNDED),
            _make_chat_item("Algorithms & Data Structures", "Anyone reviewing dynamic programming?", "4:25 PM", "#1B5E20", icon=ft.Icons.GROUPS_ROUNDED),
            _make_chat_item("Public Speaking Skills Cohort", "Slides uploaded for next week's presentation!", "2:39 PM", "#C2410C", icon=ft.Icons.RECORD_VOICE_OVER_ROUNDED),
            _make_chat_item("Sarah Jenkins", "Ready for a Study Duel? Let's test our knowledge!", "5:21 PM", "#0D5C75", letter="SJ", is_online=True),
            _make_chat_item("David Chen", "Sounds great, let's review after class!", "11:55 AM", "#1E3A1E", letter="DC", is_online=True),
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
            # Mobile Nu Chat: Full-width clean channel list
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
            width=200,
            padding=ft.Padding.only(right=8),
            border=ft.Border.only(right=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE))),
            content=ft.Stack(
                controls=[
                    ft.Column(
                        spacing=5,
                        controls=[
                            chat_header,
                            search_box,
                            ft.Column(chat_items[:4], spacing=2),
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
                spacing=6,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED, size=36, color=ft.Colors.with_opacity(0.35, ft.Colors.ON_SURFACE)),
                    ft.Text("Nu Chat", size=16, weight=ft.FontWeight.W_800),
                    ft.Text(
                        "Select a conversation to start messaging.",
                        size=10,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=2),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=4,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.LOCK_ROUNDED, size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text("End-to-end encrypted messaging inside Nu Age.", size=9, color=ft.Colors.ON_SURFACE_VARIANT),
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
                ft.Container(height=250, content=chat_split),
            ],
        )

    # ── SLIDE 4 REAL VIEW: GRAPHICALLY BEAUTIFUL INTERACTIVE FORM ─────────────
    def _build_interactive_goals_form() -> ft.Control:
        """Graphically beautiful, interactive setup form with rich pace cards & focus chips."""
        is_desk = is_desktop()

        # 1. Study Pace Option Cards
        pace_options = [
            {
                "mins": 15,
                "label": "15 min/day",
                "tag": "CASUAL",
                "sub": "Bite-sized daily drills",
                "icon": ft.Icons.BOLT_ROUNDED,
            },
            {
                "mins": 30,
                "label": "30 min/day",
                "tag": "RECOMMENDED",
                "sub": "Steady retention pace",
                "icon": ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED,
            },
            {
                "mins": 60,
                "label": "60 min/day",
                "tag": "INTENSE",
                "sub": "Exam mastery sprint",
                "icon": ft.Icons.EMOJI_EVENTS_ROUNDED,
            },
        ]

        def _make_pace_card(opt: dict) -> ft.Container:
            mins = opt["mins"]
            is_sel = (state["goal_minutes"] == mins)
            border_c = ft.Colors.PRIMARY if is_sel else ft.Colors.with_opacity(0.14, ft.Colors.ON_SURFACE)
            bg_c = ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if is_sel else ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE)

            def on_pick(e):
                state["goal_minutes"] = mins
                slide_box.content = build_slide_content(3)
                safe_page_update()

            check_icon = ft.Icon(
                ft.Icons.CHECK_CIRCLE_ROUNDED if is_sel else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED,
                size=15 if is_desk else 14,
                color=ft.Colors.PRIMARY if is_sel else ft.Colors.with_opacity(0.35, ft.Colors.ON_SURFACE),
            )

            tag_badge = ft.Container(
                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                border_radius=ft.BorderRadius.all(6),
                bgcolor=ft.Colors.PRIMARY if is_sel else ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                content=ft.Text(
                    opt["tag"],
                    size=8,
                    weight=ft.FontWeight.W_800,
                    color=ft.Colors.ON_PRIMARY if is_sel else ft.Colors.ON_SURFACE_VARIANT,
                ),
            )

            return ft.Container(
                expand=True,
                padding=ft.Padding.symmetric(horizontal=10 if is_desk else 8, vertical=10 if is_desk else 8),
                border_radius=ft.BorderRadius.all(12),
                bgcolor=bg_c,
                border=ft.Border.all(2 if is_sel else 1, border_c),
                ink=True,
                on_click=on_pick,
                content=ft.Column(
                    spacing=4 if is_desk else 3,
                    tight=True,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[tag_badge, check_icon],
                        ),
                        ft.Row(
                            spacing=6,
                            tight=True,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(opt["icon"], size=18 if is_desk else 16, color=ft.Colors.PRIMARY if is_sel else ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(opt["label"], size=12 if is_desk else 10.5, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY if is_sel else ft.Colors.ON_SURFACE),
                            ],
                        ),
                        ft.Text(opt["sub"], size=9 if is_desk else 8, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ],
                ),
            )

        pace_cards = [_make_pace_card(opt) for opt in pace_options]

        # 2. Field of Study Interactive Chips
        fields_list = [
            ("Software & Tech", ft.Icons.LAPTOP_MAC_ROUNDED),
            ("Medicine & Health", ft.Icons.LOCAL_HOSPITAL_ROUNDED),
            ("Engineering & Math", ft.Icons.SQUARE_FOOT_ROUNDED),
            ("Business & Finance", ft.Icons.TRENDING_UP_ROUNDED),
            ("Law & Humanities", ft.Icons.GAVEL_ROUNDED),
            ("Natural Sciences", ft.Icons.SCIENCE_ROUNDED),
        ] if is_desk else [
            ("Software & Tech", ft.Icons.LAPTOP_MAC_ROUNDED),
            ("Medicine & Health", ft.Icons.LOCAL_HOSPITAL_ROUNDED),
            ("Engineering & Math", ft.Icons.SQUARE_FOOT_ROUNDED),
            ("Business & Finance", ft.Icons.TRENDING_UP_ROUNDED),
        ]

        def _make_focus_chip(name: str, icon_c) -> ft.Container:
            is_sel = (state["study_focus"] == name)
            bg = ft.Colors.with_opacity(0.16, ft.Colors.PRIMARY) if is_sel else ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE)
            border_c = ft.Colors.PRIMARY if is_sel else ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)
            fg = ft.Colors.PRIMARY if is_sel else ft.Colors.ON_SURFACE

            def on_pick(e):
                state["study_focus"] = name
                slide_box.content = build_slide_content(3)
                safe_page_update()

            return ft.Container(
                padding=ft.Padding.symmetric(horizontal=8 if is_desk else 7, vertical=4 if is_desk else 3),
                border_radius=ft.BorderRadius.all(8),
                bgcolor=bg,
                border=ft.Border.all(1.2 if is_sel else 1, border_c),
                ink=True,
                on_click=on_pick,
                content=ft.Row(
                    spacing=4,
                    tight=True,
                    controls=[
                        ft.Icon(icon_c, size=12 if is_desk else 11, color=fg),
                        ft.Text(name, size=10 if is_desk else 9, weight=ft.FontWeight.W_700 if is_sel else ft.FontWeight.W_500, color=fg),
                    ],
                ),
            )

        focus_chips = [_make_focus_chip(n, ic) for n, ic in fields_list]

        # 3. Habit Accelerators
        def _acc_tile(icon, title, desc, icon_color):
            return ft.Container(
                expand=True,
                padding=ft.Padding.symmetric(horizontal=10, vertical=7 if is_desk else 6),
                border_radius=ft.BorderRadius.all(10),
                bgcolor=ft.Colors.with_opacity(0.06, icon_color),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.15, icon_color)),
                content=ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(icon, size=18 if is_desk else 16, color=icon_color),
                        ft.Column(
                            spacing=1,
                            tight=True,
                            expand=True,
                            controls=[
                                ft.Text(title, size=10.5 if is_desk else 10, weight=ft.FontWeight.W_800),
                                ft.Text(desc, size=9 if is_desk else 8.5, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ],
                        ),
                    ],
                ),
            )

        tile_streak = _acc_tile(
            ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED,
            "Daily Streak Shields",
            "Auto freeze protection on busy exam days",
            ft.Colors.AMBER_700,
        )
        tile_ai = _acc_tile(
            ft.Icons.AUTO_AWESOME_ROUNDED,
            "Nu Owl Study Copilot",
            "24/7 instant lesson explanations & hints",
            ft.Colors.PRIMARY,
        )

        accelerators_row = ft.Row(
            spacing=8,
            controls=[tile_streak, tile_ai],
        )

        # Form Header
        form_header = ft.Column(
            spacing=2,
            tight=True,
            controls=[
                ft.Text("Set Your Daily Practice", size=18 if is_desk else 15, weight=ft.FontWeight.W_800),
                ft.Text(
                    "Choose your daily study target to personalize streak rewards and smart practice reminders.",
                    size=11 if is_desk else 9.5,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
            ],
        )

        return ft.Column(
            spacing=10 if is_desk else 8,
            tight=True,
            controls=[
                form_header,
                ft.Text("1. Target Study Pace", size=11 if is_desk else 10, weight=ft.FontWeight.BOLD),
                ft.Row(spacing=8 if is_desk else 6, controls=pace_cards),
                ft.Text("2. Primary Field of Study", size=11 if is_desk else 10, weight=ft.FontWeight.BOLD),
                ft.Row(spacing=5, wrap=True, controls=focus_chips),
                ft.Text("3. Built-in Study Accelerators", size=11 if is_desk else 10, weight=ft.FontWeight.BOLD),
                accelerators_row,
            ],
        )

    # ── SLEEK MACBOOK FRAME (SLIDES 1-3) ─────────────────────────────────────
    def _render_stage_frame(idx: int) -> ft.Control:
        data = ONBOARDING_SCREENS[idx]
        gif_file = data.get("gif", "")
        img_file = data.get("image", "")

        has_gif = gif_file and os.path.exists(os.path.join("assets", gif_file))
        has_img = img_file and os.path.exists(os.path.join("assets", img_file))

        is_desk = is_desktop()
        stage_width = 480 if is_desk else None

        if has_gif:
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

        # Window header with 3 dots and clean tab title
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
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
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

        # Stage frame has the floating bottom app bar docked at the bottom
        stage_body = ft.Stack(
            controls=[
                ft.Container(
                    content=component_content,
                    padding=ft.Padding.only(
                        left=8 if not is_desk else 10,
                        right=8 if not is_desk else 10,
                        top=6 if not is_desk else 8,
                        bottom=44,
                    ),
                ),
                ft.Container(
                    content=_build_frame_bottom_nav(data["route_key"]),
                    bottom=2,
                    left=0,
                    right=0,
                    alignment=ft.Alignment.BOTTOM_CENTER,
                ),
            ],
        )

        return ft.Container(
            width=stage_width,
            border_radius=ft.BorderRadius.all(14),
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1.2, ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE)),
            shadow=ft.BoxShadow(
                blur_radius=18,
                color=ft.Colors.with_opacity(0.10, ft.Colors.BLACK),
                offset=ft.Offset(0, 4),
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

    # ── SLIDE CONTENT BUILDER (TOP-LEFT LOGO ALIGNED & MOBILE CENTERED) ───────
    def build_slide_content(idx: int) -> ft.Control:
        data = ONBOARDING_SCREENS[idx]
        is_desk = is_desktop()

        # Top-left app logo requested by user: assets\icon.png
        app_logo = ft.Image(
            src="icon.png",
            width=26 if not is_desk else 28,
            height=26 if not is_desk else 28,
            fit=ft.BoxFit.CONTAIN,
            border_radius=ft.BorderRadius.all(6),
        )
        logo_brand = ft.Row(
            spacing=8,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                app_logo,
                ft.Text("Nu-Age", size=14 if not is_desk else 16, weight=ft.FontWeight.W_800),
            ],
        )

        # Top Header Bar: Logo on extreme left, tour badge & skip on extreme right
        step_header = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                logo_brand,
                ft.Row([tour_badge, skip_btn], spacing=4, tight=True),
            ],
        )

        back_btn = ft.Container(
            height=46 if is_desk else 42,
            padding=ft.Padding.symmetric(horizontal=14),
            border_radius=ft.BorderRadius.all(12),
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
            alignment=ft.Alignment.CENTER,
            ink=True,
            on_click=lambda e: go_to(state["index"] - 1),
            content=ft.Row(
                spacing=5,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.ARROW_BACK_ROUNDED, size=15, color=ft.Colors.ON_SURFACE),
                    ft.Text("Back", size=13 if is_desk else 12, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                ],
            ),
        )

        buttons_row = (
            ft.Row(
                spacing=8,
                controls=[
                    back_btn,
                    ft.Container(expand=True, content=action_btn),
                ],
            )
            if idx > 0
            else action_btn
        )

        bottom_controls = ft.Column(
            spacing=6 if not is_desk else 8,
            tight=True,
            controls=[
                buttons_row,
                segments_row,
            ],
        )

        if idx == 3:
            # ── SLIDE 4: GRAPHICALLY BEAUTIFUL INTERACTIVE SETUP FORM ────────
            interactive_form = _build_interactive_goals_form()

            if is_desk:
                return ft.Column(
                    key=f"desk_{idx}",
                    spacing=16,
                    tight=True,
                    controls=[
                        step_header,
                        interactive_form,
                        bottom_controls,
                    ],
                )
            else:
                return ft.Column(
                    key=f"mob_{idx}",
                    spacing=10,
                    tight=True,
                    controls=[
                        step_header,
                        interactive_form,
                        bottom_controls,
                    ],
                )

        # ── SLIDES 1-3: SHOWCASE WITH SCREENSHOT/MOCKUP ──────────────────────
        stage_frame = _render_stage_frame(idx)

        headline_text = ft.Text(
            data["title"],
            size=19 if is_desk else 15,
            weight=ft.FontWeight.W_800,
            color=ft.Colors.ON_SURFACE,
            max_lines=2,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        desc_text = ft.Text(
            data["desc"],
            size=11.5 if is_desk else 10,
            color=ft.Colors.ON_SURFACE_VARIANT,
            max_lines=2 if not is_desk else 3,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        # Concise bullet highlights (3 on desktop, 2 on mobile for height safety)
        bullet_rows = []
        active_bullets = data["bullets"][:3] if is_desk else data["bullets"][:2]
        for b_text, b_icon in active_bullets:
            bullet_rows.append(
                ft.Row(
                    spacing=6 if not is_desk else 8,
                    tight=True,
                    controls=[
                        ft.Icon(b_icon, size=13 if not is_desk else 15, color=ft.Colors.PRIMARY),
                        ft.Text(b_text, size=10.5 if not is_desk else 11.5, weight=ft.FontWeight.W_500),
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

        if is_desk:
            # Laptop & Desktop: Top header (Logo on top left), then Left Mockup + Right Guide & CTA
            slide_body = ft.Row(
                spacing=22,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    stage_frame,
                    ft.Container(
                        expand=True,
                        content=ft.Column(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            spacing=16,
                            tight=True,
                            controls=[
                                guide_col,
                                bottom_controls,
                            ],
                        ),
                    ),
                ],
            )
            return ft.Column(
                key=f"desk_{idx}",
                spacing=16,
                tight=True,
                controls=[
                    step_header,
                    slide_body,
                ],
            )
        else:
            # Mobile: Centered Single-Screen Deck
            return ft.Column(
                key=f"mob_{idx}",
                spacing=8,
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

    # ── Horizontal Swipe & Drag Gesture Detection ────────────────────────────
    drag_state = {"dx": 0.0, "dy": 0.0}

    def handle_drag_start(e):
        drag_state["dx"] = 0.0
        drag_state["dy"] = 0.0

    def handle_drag_update(e):
        p_delta = getattr(e, "primary_delta", None)
        if p_delta is not None:
            drag_state["dx"] += p_delta
        else:
            ld = getattr(e, "local_delta", None)
            if ld:
                drag_state["dx"] += (getattr(ld, "x", 0.0) or 0.0)
                drag_state["dy"] += (getattr(ld, "y", 0.0) or 0.0)
            else:
                gd = getattr(e, "global_delta", None)
                if gd:
                    drag_state["dx"] += (getattr(gd, "x", 0.0) or 0.0)
                    drag_state["dy"] += (getattr(gd, "y", 0.0) or 0.0)

    def handle_drag_end(e):
        velocity = getattr(e, "primary_velocity", 0.0) or 0.0
        dx = drag_state["dx"]
        drag_state["dx"] = 0.0
        drag_state["dy"] = 0.0

        # Sensitive, natural swipe thresholds:
        # Distance > 30px OR quick flick velocity > 60
        if dx < -30 or velocity < -60:
            if state["index"] < total_screens - 1:
                go_to(state["index"] + 1)
        elif dx > 30 or velocity > 60:
            if state["index"] > 0:
                go_to(state["index"] - 1)

    gesture_detector = ft.GestureDetector(
        content=slide_box,
        drag_interval=10,
        on_horizontal_drag_start=handle_drag_start,
        on_horizontal_drag_update=handle_drag_update,
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
            # 1. Smoothly fade out outgoing slide
            slide_box.opacity = 0.0
            safe_page_update()
            await asyncio.sleep(0.14)

            # 2. Swap content
            state["index"] = target_idx
            screen_data = ONBOARDING_SCREENS[target_idx]
            slide_box.content = build_slide_content(target_idx)
            action_btn_text.value = screen_data["btn_text"]
            update_segments(target_idx)
            safe_page_update()

            # 3. Smoothly fade in new slide
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
            horizontal=22 if is_desktop() else 14,
            vertical=16 if is_desktop() else 12,
        ),
        content=gesture_detector,
        animate=ft.Animation(200, ft.AnimationCurve.DECELERATE),
    )

    # Responsive resize handler
    previous_on_resized = page.on_resize

    def handle_resize(e=None):
        card_container.width = get_card_width()
        card_container.padding = ft.Padding.symmetric(
            horizontal=22 if is_desktop() else 14,
            vertical=16 if is_desktop() else 12,
        )
        card_container.border_radius = ft.BorderRadius.all(22 if is_desktop() else 18)
        slide_box.content = build_slide_content(state["index"])
        safe_page_update()
        if callable(previous_on_resized):
            previous_on_resized(e)

    page.on_resized = handle_resize

    # Full overlay clamped nicely and centered vertically + horizontally
    overlay = ft.Container(
        expand=True,
        bgcolor=ft.Colors.with_opacity(0.68, ft.Colors.BLACK),
        alignment=ft.Alignment.CENTER,
        padding=ft.Padding.symmetric(horizontal=12, vertical=12),
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
            controls=[card_container],
        ),
    )

    return overlay


def build_onboarding_view(page: ft.Page, on_dismiss=None) -> ft.View:
    """Builds a full-page view onboarding carousel for first app launch after install."""
    cur_key = page.data.get("current_theme_key", "dark") if hasattr(page, "data") and isinstance(page.data, dict) else "dark"
    from src.utils.theme_bridge import get_theme_palette
    p = get_theme_palette(cur_key)

    deck_overlay = build_onboarding_overlay(page, on_dismiss=on_dismiss)
    # The inner card container
    card_ctrl = deck_overlay.content

    w = int(page.width or getattr(page.window, "width", None) or 800)
    is_desk = w >= 880

    return ft.View(
        route="/onboarding",
        padding=0,
        bgcolor=p["surface"],
        vertical_alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.SafeArea(
                expand=True,
                content=ft.Container(
                    expand=True,
                    alignment=ft.Alignment.CENTER,
                    bgcolor=p["surface"],
                    padding=ft.Padding.symmetric(
                        horizontal=8 if not is_desk else 24,
                        vertical=8 if not is_desk else 16,
                    ),
                    content=card_ctrl,
                ),
            ),
        ],
    )
