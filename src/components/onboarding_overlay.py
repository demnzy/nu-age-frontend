"""Sleek, 3-screen mobile-first onboarding flow for Nu-Age.

Designed directly to match the best-practice EdTech UX pattern:
  - Arch/curved illustration container at the top
  - Bold punchy headline
  - Brief overview (2 lines max)
  - Big prominent full-width action button ("Continue →" / "Get Started →")
  - 3 clean horizontal dash segments centered beneath the button
  - Skip option at top right
  - Touch/drag swipe gesture support
"""

import asyncio
import flet as ft

# ─────────────────────────────────────────────────────────────────────────────
# 3 ONBOARDING SCREENS CONFIG
# ─────────────────────────────────────────────────────────────────────────────
ONBOARDING_SCREENS = [
    {
        "title": "All your learning in one place.",
        "desc": "Track course chapters, download lessons for offline study, and pick up right where you left off.",
        "image": "onboarding_1.png",
        "fallback_icon": ft.Icons.LOCAL_LIBRARY_ROUNDED,
        "arch_bg": "#D5E0FC",  # Exact background color of picture 1
        "btn_color": ft.Colors.PRIMARY,
        "btn_text": "Continue →",
    },
    {
        "title": "Learn faster with your AI tutor.",
        "desc": "Ask doubts 24/7, generate smart study flashcards, and master exam topics with instant feedback.",
        "image": "onboarding_2.png",
        "fallback_icon": ft.Icons.PSYCHOLOGY_ROUNDED,
        "arch_bg": "#E8F0FB",  # Exact background color of picture 2
        "btn_color": ft.Colors.PRIMARY,
        "btn_text": "Continue →",
    },
    {
        "title": "Study together, achieve more.",
        "desc": "Connect with classmates, join live study rooms, and celebrate your daily learning milestones.",
        "image": "onboarding_3.png",
        "fallback_icon": ft.Icons.GROUPS_ROUNDED,
        "arch_bg": "#FFD5BF",  # Exact background color of picture 3
        "btn_color": ft.Colors.PRIMARY,
        "btn_text": "Next: Set Your Goal →",
    },
    {
        "title": "Set your learning pace.",
        "desc": "Personalize your daily study commitment and focus topic.",
        "image": "",
        "fallback_icon": ft.Icons.FLAG_ROUNDED,
        "arch_bg": "#E0E7FF",
        "btn_color": ft.Colors.PRIMARY,
        "btn_text": "Launch Nu-Age 🚀",
    },
]


def build_onboarding_overlay(page: ft.Page, on_dismiss=None) -> ft.Container:
    """Builds the 4-screen visual onboarding overlay with role-aware goal capture.

    Args:
        page: Active Flet page.
        on_dismiss: Callback invoked when user finishes or skips.
    """
    user_data = page.session.store.get("current_user") or {}
    user_role = (user_data.get("role") or "student").lower()

    state = {
        "index": 0,
        "dismissed": False,
        "goal_minutes": 30,
        "study_focus": "Software & Tech",
    }
    total_screens = len(ONBOARDING_SCREENS)

    # ── Sizing calculations ───────────────────────────────────────────────────
    # Card is compact and mobile-first (~380px wide, ~560px high)
    CARD_MAX_WIDTH = 400
    CARD_MIN_WIDTH = 300
    CARD_MAX_HEIGHT = 580
    CARD_MIN_HEIGHT = 480

    def get_card_width() -> float:
        w = page.width or 390
        return max(CARD_MIN_WIDTH, min(CARD_MAX_WIDTH, w - 28))

    def get_card_height() -> float:
        h = page.height or 640
        return max(CARD_MIN_HEIGHT, min(CARD_MAX_HEIGHT, h - 36))

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
            await page.shared_preferences.set("has_seen_onboarding", True)
            await page.shared_preferences.set("study_goal_minutes", state["goal_minutes"])
            await page.shared_preferences.set("study_focus", state["study_focus"])
        except Exception as ex:
            print(f"[Onboarding] shared_preferences error: {ex}")

        try:
            user_data = page.session.store.get("current_user") or {}
            user_data["has_seen_onboarding"] = True
            user_data["study_goal_minutes"] = state["goal_minutes"]
            user_data["study_focus"] = state["study_focus"]
            page.session.store.set("current_user", user_data)
        except Exception as ex:
            print(f"[Onboarding] session.store error: {ex}")

        if callable(on_dismiss):
            on_dismiss({"skipped": skipped, "goal_minutes": state["goal_minutes"], "study_focus": state["study_focus"]})

    def handle_skip(e):
        page.run_task(_dismiss_async, True)

    def handle_next(e):
        if state["index"] == total_screens - 1:
            page.run_task(_dismiss_async, False)
        else:
            go_to(state["index"] + 1)

    # ── Skip Button (Top Right) ───────────────────────────────────────────────
    skip_btn = ft.TextButton(
        content=ft.Text(
            "Skip",
            size=13,
            weight=ft.FontWeight.W_600,
            color=ft.Colors.GREY_500,
        ),
        style=ft.ButtonStyle(
            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        ),
        on_click=handle_skip,
    )

    # ── Big Action Button ─────────────────────────────────────────────────────
    action_btn_text = ft.Text(
        ONBOARDING_SCREENS[0]["btn_text"],
        size=15.5,
        weight=ft.FontWeight.W_700,
        color=ft.Colors.SURFACE,
    )

    action_btn = ft.Container(
        height=52,
        border_radius=ft.BorderRadius.all(26),
        bgcolor=ONBOARDING_SCREENS[0]["btn_color"],
        alignment=ft.Alignment.CENTER,
        ink=True,
        on_click=handle_next,
        content=action_btn_text,
    )

    # ── 4 Segments (Pill / Dash Indicators) ───────────────────────────────────
    segment_controls = []
    for i in range(total_screens):
        is_active = i == 0
        seg = ft.Container(
            width=26 if is_active else 12,
            height=4,
            border_radius=ft.BorderRadius.all(2),
            bgcolor=ft.Colors.PRIMARY if is_active else ft.Colors.GREY_300,
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )
        segment_controls.append(seg)

    segments_row = ft.Row(
        spacing=6,
        alignment=ft.MainAxisAlignment.CENTER,
        controls=segment_controls,
    )

    def update_segments(active_idx: int):
        for i, seg in enumerate(segment_controls):
            active = i == active_idx
            seg.width = 28 if active else 12
            seg.bgcolor = ft.Colors.PRIMARY if active else ft.Colors.GREY_300

    # ── Screen Content Builder ────────────────────────────────────────────────
    def build_screen_content(idx: int) -> ft.Control:
        data = ONBOARDING_SCREENS[idx]

        # Screen 3: Personalized Goal Capture (Student) or Launch Checklist (Tutor)
        if idx == 3:
            if user_role in ("tutor", "instructor", "admin"):
                checklist_items = [
                    ("Course Outline", "Structure your syllabus and units", ft.Icons.CHECK_CIRCLE_ROUNDED, ft.Colors.PRIMARY),
                    ("Upload Content", "Add lecture slides, links, or videos", ft.Icons.RADIO_BUTTON_CHECKED_ROUNDED, ft.Colors.PRIMARY),
                    ("Invite Students", "Create cohort link or invite by email", ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED, ft.Colors.GREY_400),
                ]
                cl_controls = []
                for cl_title, cl_sub, cl_ico, cl_col in checklist_items:
                    cl_controls.append(
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                            border_radius=ft.BorderRadius.all(12),
                            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.PRIMARY),
                            content=ft.Row(
                                spacing=10,
                                controls=[
                                    ft.Icon(cl_ico, color=cl_col, size=20),
                                    ft.Column(
                                        spacing=1,
                                        controls=[
                                            ft.Text(cl_title, size=12.5, weight=ft.FontWeight.W_700),
                                            ft.Text(cl_sub, size=10.5, color=ft.Colors.GREY_600),
                                        ],
                                    ),
                                ],
                            ),
                        )
                    )

                return ft.Column(
                    key="step_3_tutor",
                    spacing=12,
                    controls=[
                        ft.Container(
                            height=120,
                            border_radius=ft.BorderRadius.all(20),
                            bgcolor="#E0E7FF",
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(ft.Icons.CO_PRESENT_ROUNDED, size=54, color=ft.Colors.PRIMARY),
                        ),
                        ft.Column(
                            spacing=4,
                            controls=[
                                ft.Text("Instructor Setup", size=20, weight=ft.FontWeight.W_800),
                                ft.Text("Complete these quick steps to launch your cohort.", size=12.5, color=ft.Colors.GREY_600),
                            ],
                        ),
                        ft.Column(spacing=8, controls=cl_controls),
                    ],
                )

            # Default Student Goal Capture
            goal_chips = []
            durations = [(15, "15 min", "Casual"), (30, "30 min", "Steady"), (60, "60 min", "Sprint")]
            for mins, lbl, sub in durations:
                selected = state["goal_minutes"] == mins
                def make_select_goal(m):
                    def _sel(e):
                        state["goal_minutes"] = m
                        switcher.content = build_screen_content(3)
                        safe_page_update()
                    return _sel

                goal_chips.append(
                    ft.Container(
                        expand=True,
                        padding=ft.Padding.symmetric(vertical=8, horizontal=6),
                        border_radius=ft.BorderRadius.all(10),
                        bgcolor=ft.Colors.PRIMARY if selected else ft.Colors.with_opacity(0.06, ft.Colors.PRIMARY),
                        border=ft.Border.all(1.5, ft.Colors.PRIMARY if selected else ft.Colors.GREY_300),
                        alignment=ft.Alignment.CENTER,
                        ink=True,
                        on_click=make_select_goal(mins),
                        content=ft.Column(
                            spacing=1,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Text(lbl, size=12, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE if selected else ft.Colors.ON_SURFACE),
                                ft.Text(sub, size=9.5, color=ft.Colors.WHITE if selected else ft.Colors.GREY_500),
                            ],
                        ),
                    )
                )

            focus_chips = []
            topics = ["Software & Tech", "Business", "Sciences", "General"]
            for top in topics:
                selected_top = state["study_focus"] == top
                def make_select_top(t):
                    def _sel(e):
                        state["study_focus"] = t
                        switcher.content = build_screen_content(3)
                        safe_page_update()
                    return _sel

                focus_chips.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(vertical=6, horizontal=10),
                        border_radius=ft.BorderRadius.all(16),
                        bgcolor=ft.Colors.with_opacity(0.12 if selected_top else 0.04, ft.Colors.PRIMARY),
                        border=ft.Border.all(1.2, ft.Colors.PRIMARY if selected_top else ft.Colors.GREY_300),
                        ink=True,
                        on_click=make_select_top(top),
                        content=ft.Text(
                            top,
                            size=11,
                            weight=ft.FontWeight.W_700 if selected_top else ft.FontWeight.W_500,
                            color=ft.Colors.PRIMARY if selected_top else ft.Colors.ON_SURFACE,
                        ),
                    )
                )

            return ft.Column(
                key="step_3_student",
                spacing=10,
                controls=[
                    ft.Container(
                        height=95,
                        border_radius=ft.BorderRadius.all(16),
                        bgcolor="#E0E7FF",
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(ft.Icons.TRACK_CHANGES_ROUNDED, size=46, color=ft.Colors.PRIMARY),
                    ),
                    ft.Column(
                        spacing=2,
                        controls=[
                            ft.Text("Personalize Your Goals", size=18, weight=ft.FontWeight.W_800),
                            ft.Text("Nu-Age tailors your study pacing and reminders.", size=11.5, color=ft.Colors.GREY_600),
                        ],
                    ),
                    ft.Text("Daily Study Target", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.GREY_700),
                    ft.Row(spacing=8, controls=goal_chips),
                    ft.Text("Primary Study Focus", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.GREY_700),
                    ft.Row(spacing=6, wrap=True, controls=focus_chips),
                ],
            )

        # Screens 0, 1, 2: Illustrated intro screens
        try:
            art_image = ft.Image(
                src=data["image"],
                width=210,
                height=190,
                fit=ft.BoxFit.CONTAIN,
            )
        except Exception:
            art_image = ft.Icon(data["fallback_icon"], size=80, color=ft.Colors.PRIMARY)

        illustration_arch = ft.Container(
            height=205,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            border_radius=ft.BorderRadius.only(
                bottom_left=110,
                bottom_right=110,
                top_left=24,
                top_right=24,
            ),
            bgcolor=data["arch_bg"],
            alignment=ft.Alignment.CENTER,
            content=art_image,
        )

        title_text = ft.Text(
            data["title"],
            size=21.5,
            weight=ft.FontWeight.W_800,
            color=ft.Colors.ON_SURFACE,
        )

        desc_text = ft.Text(
            data["desc"],
            size=13.5,
            color=ft.Colors.GREY_600,
            max_lines=3,
        )

        return ft.Column(
            key=str(idx),
            spacing=16,
            controls=[
                illustration_arch,
                ft.Column(
                    spacing=8,
                    controls=[
                        title_text,
                        desc_text,
                    ],
                ),
            ],
        )

    switcher = ft.AnimatedSwitcher(
        content=build_screen_content(0),
        transition=ft.AnimatedSwitcherTransition.FADE,
        duration=220,
    )

    # ── Swipe Gesture Support ─────────────────────────────────────────────────
    def handle_drag_end(e):
        velocity = getattr(e, "primary_velocity", 0) or 0
        if velocity < -200:  # Swipe left -> advance
            if state["index"] < total_screens - 1:
                go_to(state["index"] + 1)
        elif velocity > 200:  # Swipe right -> go back
            if state["index"] > 0:
                go_to(state["index"] - 1)

    gesture_detector = ft.GestureDetector(
        content=switcher,
        on_horizontal_drag_end=handle_drag_end,
    )

    def go_to(index: int):
        index = max(0, min(total_screens - 1, index))
        state["index"] = index
        screen_data = ONBOARDING_SCREENS[index]

        switcher.content = build_screen_content(index)
        action_btn_text.value = screen_data["btn_text"]
        action_btn.bgcolor = screen_data["btn_color"]
        update_segments(index)
        safe_page_update()

    # ── Card Container ────────────────────────────────────────────────────────
    card_content = ft.Container(
        bgcolor=ft.Colors.SURFACE,
        border_radius=ft.BorderRadius.all(28),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=36,
            color=ft.Colors.with_opacity(0.20, ft.Colors.BLACK),
            offset=ft.Offset(0, 10),
        ),
        padding=ft.Padding.only(left=22, right=22, top=14, bottom=20),
        content=ft.Column(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                # Top header with Skip
                ft.Row(
                    alignment=ft.MainAxisAlignment.END,
                    controls=[skip_btn],
                ),
                # Middle illustration and copy
                gesture_detector,
                # Bottom controls: BIG BUTTON + 3 SEGMENTS
                ft.Column(
                    spacing=12,
                    controls=[
                        action_btn,
                        segments_row,
                    ],
                ),
            ],
        ),
    )

    card_container = ft.Container(
        width=get_card_width(),
        height=get_card_height(),
        content=card_content,
        animate=ft.Animation(200, ft.AnimationCurve.DECELERATE),
    )

    # ── Responsive resize handler ─────────────────────────────────────────────
    previous_on_resized = page.on_resize

    def handle_resize(e=None):
        card_container.width = get_card_width()
        card_container.height = get_card_height()
        safe_page_update()
        if callable(previous_on_resized):
            previous_on_resized(e)

    page.on_resized = handle_resize

    # Full overlay
    overlay = ft.Container(
        expand=True,
        bgcolor=ft.Colors.with_opacity(0.65, ft.Colors.BLACK),
        alignment=ft.Alignment.CENTER,
        padding=ft.Padding.all(16),
        content=card_container,
    )

    return overlay
