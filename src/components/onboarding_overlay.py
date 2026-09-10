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
        "btn_text": "Get Started →",
    },
]


def build_onboarding_overlay(page: ft.Page, on_dismiss=None) -> ft.Container:
    """Builds the 3-screen visual onboarding overlay based on the inspo design.

    Args:
        page: Active Flet page.
        on_dismiss: Callback invoked when user finishes or skips.
    """
    state = {"index": 0, "dismissed": False}
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
        except Exception as ex:
            print(f"[Onboarding] shared_preferences error: {ex}")

        try:
            user_data = page.session.store.get("current_user") or {}
            user_data["has_seen_onboarding"] = True
            page.session.store.set("current_user", user_data)
        except Exception as ex:
            print(f"[Onboarding] session.store error: {ex}")

        if callable(on_dismiss):
            on_dismiss({"skipped": skipped})

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

    # ── 3 Segments (Pill / Dash Indicators) ───────────────────────────────────
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

        # Top arch illustration container matching reference image:
        # Semicircular arch with rounded bottom
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
