"""
shimmer_skeletons.py
──────────────────────────────────────────────────────────────────────────────
High-fidelity 1-to-1 accurate shimmer skeleton screens for all routed pages
in Nu-Age LMS.

Requirements:
- Strict neutral grey color palette (no greens, blues, purples, or chromatic tints).
- Excludes top app bars (skeletons render only page body beneath the navigation bar).
- Responsive: adapts cleanly to mobile (< 900px/1024px) and desktop viewports.
- Fully compatible with Flet 0.86.5 (ft.BorderRadius.all/only, no page.window_width).
──────────────────────────────────────────────────────────────────────────────
"""

import flet as ft

# ─────────────────────────────────────────────────────────────────────────────
# GREY DESIGN TOKENS
# ─────────────────────────────────────────────────────────────────────────────
GREY_BOX_COLOR = ft.Colors.with_opacity(0.18, ft.Colors.GREY)
GREY_BOX_LIGHT = ft.Colors.with_opacity(0.12, ft.Colors.GREY)
GREY_BOX_DARK = ft.Colors.with_opacity(0.26, ft.Colors.GREY)

GREY_CARD_BG = ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE)
GREY_CARD_BG_ALT = ft.Colors.with_opacity(0.025, ft.Colors.ON_SURFACE)
GREY_BORDER = ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)
GREY_BORDER_SUBTLE = ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)
GREY_DIVIDER = ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)


# ─────────────────────────────────────────────────────────────────────────────
# CORE BUILDING BLOCKS
# ─────────────────────────────────────────────────────────────────────────────
def shimmer_box(
    radius: int | float | ft.BorderRadius = 8,
    height: int | float | None = None,
    width: int | float | None = None,
    expand: bool = False,
    darker: bool = False,
) -> ft.Container:
    """A single grey placeholder box animated by the shimmer loop."""
    border_rad = (
        radius
        if isinstance(radius, (int, float, ft.BorderRadius))
        else ft.BorderRadius.all(8)
    )
    box = ft.Container(
        expand=True if ((height is None and width is None) or expand) else None,
        height=height,
        width=width,
        border_radius=border_rad,
        bgcolor=GREY_BOX_DARK if darker else GREY_BOX_COLOR,
        animate_opacity=ft.Animation(500, ft.AnimationCurve.EASE_IN_OUT),
        opacity=0.35,
    )
    box.data = "shimmer_box"
    return box


def grey_card(
    content: ft.Control,
    padding: int | ft.Padding = 16,
    radius: int | ft.BorderRadius = 14,
    border: bool = True,
    col: dict | None = None,
    expand: bool = False,
) -> ft.Container:
    """Standardized grey container wrapping skeleton blocks."""
    pad = ft.Padding.all(padding) if isinstance(padding, int) else padding
    rad = ft.BorderRadius.all(radius) if isinstance(radius, int) else radius
    return ft.Container(
        content=content,
        padding=pad,
        border_radius=rad,
        bgcolor=GREY_CARD_BG,
        border=ft.Border.all(1, GREY_BORDER) if border else None,
        col=col,
        expand=expand,
    )


def is_desktop_mode(page: ft.Page | None = None, breakpoint: int = 900) -> bool:
    """Safely checks if page width meets the desktop breakpoint."""
    if page is None:
        return True
    w = getattr(page, "width", None)
    if w is None and hasattr(page, "window") and page.window:
        w = getattr(page.window, "width", None)
    return (w or 0) >= breakpoint


def collect_shimmer_boxes(control: ft.Control) -> list[ft.Container]:
    """Walks the control tree and extracts all shimmer_box instances."""
    boxes: list[ft.Container] = []

    def walk(c: ft.Control | None):
        if c is None:
            return
        if isinstance(c, ft.Container):
            if getattr(c, "data", None) == "shimmer_box":
                boxes.append(c)
            if c.content is not None:
                walk(c.content)
        elif isinstance(c, (ft.Row, ft.Column, ft.ResponsiveRow, ft.ListView)):
            for child in c.controls or []:
                walk(child)
        elif isinstance(c, ft.Stack):
            for child in c.controls or []:
                walk(child)

    walk(control)
    return boxes


# ─────────────────────────────────────────────────────────────────────────────
# 1. DASHBOARD SKELETON (/dashboard)
# ─────────────────────────────────────────────────────────────────────────────
def build_dashboard_skeleton(page: ft.Page) -> ft.Control:
    is_desk = is_desktop_mode(page, 800)

    # Hero Greeting Banner
    hero_banner = grey_card(
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Column(
                    spacing=6,
                    expand=True,
                    controls=[
                        shimmer_box(radius=4, height=12, width=110),
                        shimmer_box(radius=6, height=22, width=220),
                        shimmer_box(radius=4, height=11, width=260),
                        ft.Container(height=4),
                        shimmer_box(radius=999, height=24, width=130),
                    ],
                ),
                shimmer_box(radius=999, width=64, height=64),
            ],
        ),
        padding=18,
        radius=16,
    )

    # Dual Trackers (Activity Bar Chart + Donut Learning Focus Chart)
    activity_box = grey_card(
        content=ft.Column(
            spacing=10,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        shimmer_box(radius=4, height=13, width=120),
                        shimmer_box(radius=4, height=11, width=80),
                    ],
                ),
                shimmer_box(radius=8, height=140, expand=True),
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        shimmer_box(radius=4, height=10, width=90),
                        shimmer_box(radius=4, height=10, width=70),
                    ],
                ),
            ],
        ),
        padding=16,
        col={"xs": 12, "md": 7} if is_desk else None,
    )

    focus_box = grey_card(
        content=ft.Column(
            spacing=10,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        shimmer_box(radius=4, height=13, width=100),
                        shimmer_box(radius=4, height=11, width=50),
                    ],
                ),
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_EVENLY,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        shimmer_box(radius=999, width=110, height=110),
                        ft.Column(
                            spacing=6,
                            controls=[
                                shimmer_box(radius=4, height=11, width=90),
                                shimmer_box(radius=4, height=11, width=80),
                                shimmer_box(radius=4, height=11, width=70),
                            ],
                        ),
                    ],
                ),
            ],
        ),
        padding=16,
        col={"xs": 12, "md": 5} if is_desk else None,
    )

    if is_desk:
        trackers_section = ft.ResponsiveRow(
            spacing=16,
            run_spacing=16,
            controls=[activity_box, focus_box],
        )
    else:
        trackers_section = ft.Column(
            spacing=14,
            controls=[activity_box, focus_box],
        )

    # Self-Study Hub Card
    self_study_card = grey_card(
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(
                    spacing=12,
                    controls=[
                        shimmer_box(radius=10, width=44, height=44),
                        ft.Column(
                            spacing=4,
                            controls=[
                                shimmer_box(radius=4, height=14, width=130),
                                shimmer_box(radius=4, height=11, width=210),
                            ],
                        ),
                    ],
                ),
                shimmer_box(radius=10, height=36, width=110),
            ],
        ),
        padding=16,
    )

    # Student Network Showcase Card
    network_card = grey_card(
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(
                    spacing=12,
                    controls=[
                        shimmer_box(radius=999, width=44, height=44),
                        ft.Column(
                            spacing=4,
                            controls=[
                                shimmer_box(radius=4, height=14, width=150),
                                shimmer_box(radius=4, height=11, width=180),
                            ],
                        ),
                    ],
                ),
                shimmer_box(radius=10, height=36, width=110),
            ],
        ),
        padding=16,
    )

    # Continue Learning Cards (Horizontal List)
    def continue_card():
        return grey_card(
            content=ft.Column(
                spacing=8,
                controls=[
                    shimmer_box(radius=10, height=100, width=240),
                    shimmer_box(radius=4, height=14, width=180),
                    shimmer_box(radius=3, height=4, width=240),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            shimmer_box(radius=4, height=10, width=70),
                            shimmer_box(radius=8, height=26, width=70),
                        ],
                    ),
                ],
            ),
            padding=12,
            radius=14,
        )

    continue_row = ft.Row(
        scroll=ft.ScrollMode.HIDDEN,
        spacing=14,
        controls=[continue_card() for _ in range(3)],
    )

    continue_section = ft.Column(
        spacing=10,
        controls=[
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    shimmer_box(radius=4, height=14, width=130),
                    shimmer_box(radius=4, height=11, width=50),
                ],
            ),
            continue_row,
        ],
    )

    return ft.ListView(
        expand=True,
        padding=ft.Padding.symmetric(horizontal=16, vertical=16),
        controls=[
            hero_banner,
            ft.Container(height=14),
            trackers_section,
            ft.Container(height=14),
            self_study_card,
            ft.Container(height=14),
            network_card,
            ft.Container(height=14),
            continue_section,
            ft.Container(height=24),
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. COURSES / LEARN SKELETON (/courses)
# ─────────────────────────────────────────────────────────────────────────────
def build_courses_skeleton(page: ft.Page) -> ft.Control:
    # Header: "Learn" title + subtitle + tab pills
    header = ft.Container(
        padding=ft.Padding.only(left=16, right=16, top=14, bottom=12),
        border=ft.Border(bottom=ft.BorderSide(1, GREY_DIVIDER)),
        content=ft.Column(
            spacing=12,
            controls=[
                ft.Column(
                    spacing=4,
                    controls=[
                        shimmer_box(radius=6, height=24, width=90),
                        shimmer_box(radius=4, height=12, width=240),
                    ],
                ),
                ft.Row(
                    spacing=8,
                    scroll=ft.ScrollMode.AUTO,
                    controls=[
                        shimmer_box(radius=8, height=30, width=95),
                        shimmer_box(radius=8, height=30, width=80),
                        shimmer_box(radius=8, height=30, width=85),
                        shimmer_box(radius=8, height=30, width=95),
                        shimmer_box(radius=8, height=30, width=105),
                    ],
                ),
            ],
        ),
    )

    # Search Bar & Filter Chips
    search_filter = ft.Container(
        padding=ft.Padding.only(left=16, right=16, top=10, bottom=8),
        content=ft.Column(
            spacing=8,
            controls=[
                shimmer_box(radius=10, height=42, expand=True),
                ft.Row(
                    spacing=8,
                    controls=[
                        shimmer_box(radius=8, height=28, width=95),
                        shimmer_box(radius=8, height=28, width=105),
                        shimmer_box(radius=8, height=28, width=115),
                    ],
                ),
            ],
        ),
    )

    # Course Card Skeleton (Modern Horizontal Layout)
    def course_card_skel():
        top_row = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.START,
            controls=[
                ft.Column(
                    expand=True,
                    spacing=6,
                    controls=[
                        shimmer_box(radius=6, height=16, width=65),
                        shimmer_box(radius=6, height=15, width=140),
                        shimmer_box(radius=4, height=10, expand=True),
                        shimmer_box(radius=4, height=10, width=120),
                        ft.Row(
                            spacing=6,
                            controls=[
                                shimmer_box(radius=4, height=10, width=50),
                                shimmer_box(radius=4, height=10, width=40),
                            ],
                        ),
                    ],
                ),
                ft.Container(width=12),
                shimmer_box(radius=16, width=76, height=76),
            ],
        )
        progress_strip = ft.Column(
            spacing=4,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        shimmer_box(radius=3, height=10, width=45),
                        shimmer_box(radius=3, height=10, width=25),
                    ],
                ),
                shimmer_box(radius=2, height=4, expand=True),
            ],
        )
        footer = ft.Container(
            padding=ft.Padding.symmetric(horizontal=14, vertical=8),
            border=ft.Border(top=ft.BorderSide(1, GREY_BORDER_SUBTLE)),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    shimmer_box(radius=4, height=11, width=95),
                    shimmer_box(radius=14, height=26, width=75),
                ],
            ),
        )
        return ft.Container(
            col={"xs": 12, "sm": 6},
            border_radius=ft.BorderRadius.all(18),
            bgcolor=GREY_CARD_BG,
            border=ft.Border.all(1, GREY_BORDER),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=ft.Column(
                spacing=0,
                controls=[
                    ft.Container(
                        padding=ft.Padding.all(14),
                        content=ft.Column([top_row, progress_strip], spacing=10),
                    ),
                    footer,
                ],
            ),
        )

    cards_grid = ft.ResponsiveRow(
        spacing=14,
        run_spacing=14,
        controls=[course_card_skel() for _ in range(4)],
    )

    return ft.Column(
        spacing=0,
        expand=True,
        controls=[
            header,
            search_filter,
            ft.ListView(
                expand=True,
                padding=ft.Padding.symmetric(horizontal=16, vertical=6),
                controls=[cards_grid, ft.Container(height=20)],
            ),
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. COURSE LEARNER / READER SKELETON (/courses/:id/view, /courses/:id/offline)
#    (EXCLUDES TOP APP BAR)
# ─────────────────────────────────────────────────────────────────────────────
def build_course_learner_skeleton(page: ft.Page) -> ft.Control:
    is_desk = is_desktop_mode(page, 1024)

    # Lesson Header Card (module pill, lesson type tag, lesson title, progress bar)
    lesson_header_card = grey_card(
        content=ft.Column(
            spacing=8,
            controls=[
                ft.Row(
                    spacing=8,
                    controls=[
                        shimmer_box(radius=4, height=12, width=90),
                        shimmer_box(radius=999, height=18, width=75),
                        shimmer_box(radius=4, height=11, width=65),
                    ],
                ),
                shimmer_box(radius=6, height=22, width=280),
                shimmer_box(radius=2, height=3.5, expand=True),
            ],
        ),
        padding=16,
        radius=12,
    )

    # Lesson Media / Video Card
    media_block = shimmer_box(radius=12, height=200, expand=True)

    # Lesson Reading Body & Key Takeaway Box
    reading_card = grey_card(
        content=ft.Column(
            spacing=10,
            controls=[
                shimmer_box(radius=5, height=16, width=180),
                shimmer_box(radius=4, height=11, expand=True),
                shimmer_box(radius=4, height=11, expand=True),
                shimmer_box(radius=4, height=11, width=320),
                ft.Container(height=4),
                # Takeaway Callout Card
                grey_card(
                    content=ft.Column(
                        spacing=6,
                        controls=[
                            shimmer_box(radius=4, height=12, width=110),
                            shimmer_box(radius=4, height=10, expand=True),
                        ],
                    ),
                    padding=12,
                    radius=8,
                ),
                ft.Container(height=4),
                shimmer_box(radius=4, height=11, expand=True),
                shimmer_box(radius=4, height=11, width=260),
            ],
        ),
        padding=18,
        radius=12,
    )

    # Action Footer
    action_footer = ft.Container(
        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
        border=ft.Border(top=ft.BorderSide(1, GREY_DIVIDER)),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                shimmer_box(radius=8, height=42, width=110),
                shimmer_box(radius=8, height=42, width=160),
            ],
        ),
    )

    main_scroll = ft.ListView(
        expand=True,
        padding=ft.Padding.symmetric(horizontal=16, vertical=14),
        controls=[
            lesson_header_card,
            ft.Container(height=14),
            media_block,
            ft.Container(height=14),
            reading_card,
            ft.Container(height=14),
        ],
    )

    main_content_area = ft.Column(
        expand=True,
        spacing=0,
        controls=[
            main_scroll,
            action_footer,
        ],
    )

    if is_desk:
        # Desktop Syllabus Sidebar (width 340)
        sidebar = ft.Container(
            width=340,
            padding=ft.Padding.all(16),
            border=ft.Border(right=ft.BorderSide(1, GREY_DIVIDER)),
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            shimmer_box(radius=4, height=14, width=120),
                            shimmer_box(radius=4, height=14, width=40),
                        ],
                    ),
                    shimmer_box(radius=2, height=4, expand=True),
                    ft.Divider(height=1, color=GREY_DIVIDER),
                    # Module 1
                    grey_card(
                        content=ft.Column(
                            spacing=6,
                            controls=[
                                shimmer_box(radius=4, height=13, width=140),
                                shimmer_box(radius=4, height=10, width=180),
                                shimmer_box(radius=4, height=10, width=160),
                            ],
                        ),
                        padding=10,
                        radius=8,
                    ),
                    # Module 2
                    grey_card(
                        content=ft.Column(
                            spacing=6,
                            controls=[
                                shimmer_box(radius=4, height=13, width=130),
                                shimmer_box(radius=4, height=10, width=170),
                            ],
                        ),
                        padding=10,
                        radius=8,
                    ),
                    # Module 3
                    grey_card(
                        content=ft.Column(
                            spacing=6,
                            controls=[
                                shimmer_box(radius=4, height=13, width=150),
                                shimmer_box(radius=4, height=10, width=160),
                            ],
                        ),
                        padding=10,
                        radius=8,
                    ),
                ],
            ),
        )
        return ft.Row(
            expand=True,
            spacing=0,
            controls=[
                sidebar,
                main_content_area,
            ],
        )

    return main_content_area


# ─────────────────────────────────────────────────────────────────────────────
# 4. COURSE DETAILS SKELETON (/courses/:id)
#    (EXCLUDES TOP APP BAR)
# ─────────────────────────────────────────────────────────────────────────────
def build_course_details_skeleton(page: ft.Page) -> ft.Control:
    # Hero Card (Badges, Title, Desc, Stats Strip, Right Thumbnail)
    badges = ft.Row(
        spacing=8,
        controls=[
            shimmer_box(radius=8, height=22, width=70),
            shimmer_box(radius=8, height=22, width=85),
            shimmer_box(radius=8, height=22, width=60),
        ],
    )
    hero_stats = ft.Row(
        spacing=8,
        controls=[
            shimmer_box(radius=10, height=30, width=80),
            shimmer_box(radius=10, height=30, width=90),
            shimmer_box(radius=10, height=30, width=85),
        ],
    )
    hero_left = ft.Column(
        spacing=12,
        controls=[
            badges,
            shimmer_box(radius=6, height=26, width=260),
            shimmer_box(radius=4, height=12, expand=True),
            shimmer_box(radius=4, height=12, width=200),
            hero_stats,
        ],
    )
    hero_thumb = shimmer_box(radius=16, height=170, expand=True)

    hero_card = grey_card(
        content=ft.ResponsiveRow(
            columns=12,
            spacing=16,
            controls=[
                ft.Container(content=hero_left, col={"xs": 12, "md": 7}),
                ft.Container(content=hero_thumb, col={"xs": 12, "md": 5}),
            ],
        ),
        padding=18,
        radius=18,
    )

    # Left Column: Outcomes + Curriculum Accordions + Instructor
    outcomes_card = grey_card(
        content=ft.Column(
            spacing=10,
            controls=[
                shimmer_box(radius=4, height=16, width=140),
                ft.Row(
                    [
                        shimmer_box(radius=8, height=32, expand=True),
                        shimmer_box(radius=8, height=32, expand=True),
                    ],
                    spacing=10,
                ),
                ft.Row(
                    [
                        shimmer_box(radius=8, height=32, expand=True),
                        shimmer_box(radius=8, height=32, expand=True),
                    ],
                    spacing=10,
                ),
            ],
        ),
        padding=16,
    )

    def mod_tile():
        return grey_card(
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row(
                        spacing=10,
                        controls=[
                            shimmer_box(radius=6, width=26, height=26),
                            ft.Column(
                                spacing=3,
                                controls=[
                                    shimmer_box(radius=4, height=12, width=140),
                                    shimmer_box(radius=4, height=10, width=60),
                                ],
                            ),
                        ],
                    ),
                    shimmer_box(radius=4, width=16, height=16),
                ],
            ),
            padding=12,
            radius=10,
        )

    curriculum_card = grey_card(
        content=ft.Column(
            spacing=8,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        shimmer_box(radius=4, height=16, width=130),
                        shimmer_box(radius=4, height=12, width=100),
                    ],
                ),
                mod_tile(),
                mod_tile(),
                mod_tile(),
            ],
        ),
        padding=16,
    )

    left_body = ft.Column(
        spacing=16,
        controls=[outcomes_card, curriculum_card],
    )

    # Right Column: Sticky Enrollment Card
    sidebar_card = grey_card(
        content=ft.Column(
            spacing=12,
            controls=[
                shimmer_box(radius=8, height=34, expand=True),
                shimmer_box(radius=10, height=44, expand=True),
                ft.Divider(height=1, color=GREY_DIVIDER),
                shimmer_box(radius=4, height=12, width=120),
                shimmer_box(radius=4, height=10, expand=True),
                shimmer_box(radius=4, height=10, expand=True),
                shimmer_box(radius=4, height=10, expand=True),
                shimmer_box(radius=4, height=10, width=140),
            ],
        ),
        padding=18,
        radius=16,
    )

    body_grid = ft.ResponsiveRow(
        columns=12,
        spacing=16,
        run_spacing=16,
        controls=[
            ft.Container(content=left_body, col={"xs": 12, "md": 7, "lg": 8}),
            ft.Container(content=sidebar_card, col={"xs": 12, "md": 5, "lg": 4}),
        ],
    )

    return ft.ListView(
        expand=True,
        padding=ft.Padding.symmetric(horizontal=16, vertical=16),
        controls=[
            hero_card,
            ft.Container(height=16),
            body_grid,
            ft.Container(height=24),
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5. COURSE BUILDER SKELETON (/courses/:course_id/manage)
# ─────────────────────────────────────────────────────────────────────────────
def build_course_builder_skeleton(page: ft.Page) -> ft.Control:
    is_desk = is_desktop_mode(page, 900)

    # Header Card (Back + Title + Status chip + Summary Metrics)
    header_card = grey_card(
        content=ft.Column(
            spacing=10,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            spacing=10,
                            controls=[
                                shimmer_box(radius=6, width=24, height=24),
                                shimmer_box(radius=6, height=18, width=180),
                            ],
                        ),
                        shimmer_box(radius=999, height=24, width=100),
                    ],
                ),
                ft.Divider(height=1, color=GREY_DIVIDER),
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            spacing=6,
                            controls=[
                                shimmer_box(radius=6, height=22, width=70),
                                shimmer_box(radius=6, height=22, width=65),
                                shimmer_box(radius=6, height=22, width=65),
                            ],
                        ),
                        shimmer_box(radius=6, height=32, width=130),
                    ],
                ),
            ],
        ),
        padding=14,
        radius=14,
    )

    # Actions Card (Add Module, AI Draft, Preview, Publish buttons)
    actions_card = grey_card(
        content=ft.Row(
            spacing=10,
            controls=[
                shimmer_box(radius=8, height=36, width=100),
                shimmer_box(radius=8, height=36, width=90),
                shimmer_box(radius=8, height=36, width=80),
                shimmer_box(radius=8, height=36, width=110),
            ],
        ),
        padding=12,
        radius=14,
    )

    # Module Blocks
    def module_block():
        return grey_card(
            content=ft.Column(
                spacing=8,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            shimmer_box(radius=4, height=14, width=150),
                            ft.Row(
                                spacing=6,
                                controls=[
                                    shimmer_box(radius=4, width=18, height=18),
                                    shimmer_box(radius=4, width=18, height=18),
                                ],
                            ),
                        ],
                    ),
                    # Lesson rows
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(
                                spacing=8,
                                controls=[
                                    shimmer_box(radius=6, width=24, height=24),
                                    shimmer_box(radius=4, height=12, width=140),
                                    shimmer_box(radius=999, height=16, width=50),
                                ],
                            ),
                            shimmer_box(radius=4, width=16, height=16),
                        ],
                    ),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(
                                spacing=8,
                                controls=[
                                    shimmer_box(radius=6, width=24, height=24),
                                    shimmer_box(radius=4, height=12, width=120),
                                    shimmer_box(radius=999, height=16, width=50),
                                ],
                            ),
                            shimmer_box(radius=4, width=16, height=16),
                        ],
                    ),
                ],
            ),
            padding=12,
            radius=12,
        )

    curriculum_list = ft.ListView(
        expand=True,
        spacing=10,
        controls=[
            header_card,
            actions_card,
            module_block(),
            module_block(),
            module_block(),
        ],
    )

    if is_desk:
        # Desktop Split Outline (width 460) + Central Editor Panel (expand=True)
        editor_panel = grey_card(
            content=ft.Column(
                spacing=14,
                controls=[
                    shimmer_box(radius=6, height=20, width=200),
                    shimmer_box(radius=8, height=48, expand=True),
                    shimmer_box(radius=8, height=48, expand=True),
                    shimmer_box(radius=10, height=200, expand=True),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.END,
                        controls=[
                            shimmer_box(radius=8, height=36, width=100),
                        ],
                    ),
                ],
            ),
            padding=20,
            radius=14,
            expand=True,
        )
        return ft.Row(
            expand=True,
            spacing=16,
            controls=[
                ft.Container(width=460, content=curriculum_list),
                editor_panel,
            ],
        )

    return ft.Container(padding=12, content=curriculum_list, expand=True)


# ─────────────────────────────────────────────────────────────────────────────
# 6. ORGANISATIONS SKELETON (/organisations)
# ─────────────────────────────────────────────────────────────────────────────
def build_organisations_skeleton(page: ft.Page) -> ft.Control:
    # Hero Card: Top Banner + Overlapping Logo + Org Title + Contact Meta
    logo_circle = ft.Container(
        width=76,
        height=76,
        border_radius=ft.BorderRadius.all(38),
        bgcolor=GREY_CARD_BG,
        border=ft.Border.all(3, GREY_CARD_BG),
        margin=ft.Margin.only(top=-38),
        content=shimmer_box(radius=999, width=70, height=70, darker=True),
    )

    hero_card = grey_card(
        content=ft.Column(
            spacing=0,
            controls=[
                # Banner strip
                ft.Container(
                    height=70,
                    bgcolor=GREY_BOX_COLOR,
                    padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            shimmer_box(radius=4, height=14, width=120),
                            shimmer_box(radius=4, height=14, width=60),
                        ],
                    ),
                ),
                # Identity area
                ft.Container(
                    padding=ft.Padding.only(left=18, right=18, bottom=14),
                    content=ft.Column(
                        spacing=6,
                        controls=[
                            logo_circle,
                            ft.Row(
                                spacing=8,
                                controls=[
                                    shimmer_box(radius=5, height=20, width=170),
                                    shimmer_box(radius=999, height=20, width=70),
                                ],
                            ),
                            ft.Row(
                                spacing=12,
                                controls=[
                                    shimmer_box(radius=4, height=11, width=110),
                                    shimmer_box(radius=4, height=11, width=90),
                                ],
                            ),
                        ],
                    ),
                ),
            ],
        ),
        padding=0,
        radius=16,
    )

    # 4 Bento Stat Cards
    def bento_stat():
        return grey_card(
            col={"xs": 6, "md": 3},
            content=ft.Column(
                spacing=4,
                controls=[
                    shimmer_box(radius=6, width=24, height=24),
                    shimmer_box(radius=6, height=20, width=60),
                    shimmer_box(radius=4, height=10, width=85),
                ],
            ),
            padding=14,
            radius=12,
        )

    bento_row = ft.ResponsiveRow(
        spacing=12,
        run_spacing=12,
        controls=[bento_stat() for _ in range(4)],
    )

    # Tabs Row
    tabs_row = ft.Row(
        spacing=8,
        scroll=ft.ScrollMode.AUTO,
        controls=[
            shimmer_box(radius=8, height=32, width=95),
            shimmer_box(radius=8, height=32, width=90),
            shimmer_box(radius=8, height=32, width=115),
            shimmer_box(radius=8, height=32, width=130),
        ],
    )

    # Cards Grid
    def org_content_card():
        return grey_card(
            col={"xs": 12, "sm": 6, "lg": 4},
            content=ft.Column(
                spacing=8,
                controls=[
                    shimmer_box(radius=8, height=95, expand=True),
                    shimmer_box(radius=4, height=14, width=140),
                    shimmer_box(radius=4, height=11, expand=True),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            shimmer_box(radius=4, height=10, width=60),
                            shimmer_box(radius=6, height=24, width=70),
                        ],
                    ),
                ],
            ),
            padding=12,
            radius=12,
        )

    cards_grid = ft.ResponsiveRow(
        spacing=12,
        run_spacing=12,
        controls=[org_content_card() for _ in range(3)],
    )

    return ft.ListView(
        expand=True,
        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
        controls=[
            hero_card,
            ft.Container(height=12),
            bento_row,
            ft.Container(height=12),
            tabs_row,
            ft.Container(height=12),
            cards_grid,
            ft.Container(height=20),
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# 7. NETWORK SKELETON (/network)
# ─────────────────────────────────────────────────────────────────────────────
def build_network_skeleton(page: ft.Page) -> ft.Control:
    # Header: Top Nav + "Your Friends" title + Tab pills
    header = ft.Container(
        padding=ft.Padding.only(left=16, right=16, top=10, bottom=8),
        border=ft.Border(bottom=ft.BorderSide(1, GREY_DIVIDER)),
        content=ft.Column(
            spacing=8,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        shimmer_box(radius=6, width=22, height=22),
                        shimmer_box(radius=999, width=28, height=28),
                    ],
                ),
                ft.Column(
                    spacing=2,
                    controls=[
                        shimmer_box(radius=6, height=22, width=140),
                        shimmer_box(radius=4, height=12, width=90),
                    ],
                ),
                ft.Row(
                    spacing=8,
                    controls=[
                        shimmer_box(radius=8, height=30, width=80),
                        shimmer_box(radius=8, height=30, width=80),
                        shimmer_box(radius=8, height=30, width=80),
                    ],
                ),
            ],
        ),
    )

    # Active Friends Story Strip
    def friend_avatar():
        return ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
            controls=[
                shimmer_box(radius=999, width=48, height=48),
                shimmer_box(radius=3, height=9, width=40),
            ],
        )

    story_strip = ft.Container(
        padding=ft.Padding.symmetric(horizontal=16, vertical=8),
        content=ft.Row(
            spacing=12,
            scroll=ft.ScrollMode.HIDDEN,
            controls=[friend_avatar() for _ in range(6)],
        ),
    )

    # Search Bar
    search_bar = ft.Container(
        padding=ft.Padding.symmetric(horizontal=16, vertical=6),
        content=shimmer_box(radius=10, height=40, expand=True),
    )

    # User Row Tile
    def user_tile():
        return grey_card(
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        spacing=12,
                        controls=[
                            shimmer_box(radius=999, width=44, height=44),
                            ft.Column(
                                spacing=4,
                                controls=[
                                    shimmer_box(radius=4, height=14, width=120),
                                    shimmer_box(radius=4, height=10, width=80),
                                ],
                            ),
                        ],
                    ),
                    ft.Row(
                        spacing=6,
                        controls=[
                            shimmer_box(radius=8, height=32, width=70),
                            shimmer_box(radius=8, width=24, height=24),
                        ],
                    ),
                ],
            ),
            padding=12,
            radius=12,
        )

    users_list = ft.ListView(
        expand=True,
        padding=ft.Padding.symmetric(horizontal=16, vertical=8),
        controls=[
            story_strip,
            search_bar,
            ft.Container(height=4),
            user_tile(),
            ft.Container(height=8),
            user_tile(),
            ft.Container(height=8),
            user_tile(),
            ft.Container(height=8),
            user_tile(),
            ft.Container(height=20),
        ],
    )

    return ft.Column(
        spacing=0,
        expand=True,
        controls=[header, users_list],
    )


# ─────────────────────────────────────────────────────────────────────────────
# 8. CHAT SKELETON (/nu-chat)
# ─────────────────────────────────────────────────────────────────────────────
def build_chat_skeleton(page: ft.Page) -> ft.Control:
    is_desk = is_desktop_mode(page, 800)

    # Conversation List Header (Nu Chat title + Search + filter pills)
    list_header = ft.Container(
        padding=ft.Padding.symmetric(horizontal=14, vertical=10),
        border=ft.Border(bottom=ft.BorderSide(1, GREY_DIVIDER)),
        content=ft.Column(
            spacing=8,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        shimmer_box(radius=5, height=20, width=90),
                        shimmer_box(radius=6, width=22, height=22),
                    ],
                ),
                shimmer_box(radius=8, height=36, expand=True),
                ft.Row(
                    spacing=6,
                    controls=[
                        shimmer_box(radius=6, height=24, width=45),
                        shimmer_box(radius=6, height=24, width=65),
                        shimmer_box(radius=6, height=24, width=60),
                    ],
                ),
            ],
        ),
    )

    # Conversation Item Tile
    def convo_tile():
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            border=ft.Border(bottom=ft.BorderSide(1, GREY_BORDER_SUBTLE)),
            content=ft.Row(
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    shimmer_box(radius=999, width=44, height=44),
                    ft.Column(
                        expand=True,
                        spacing=4,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    shimmer_box(radius=4, height=13, width=110),
                                    shimmer_box(radius=3, height=9, width=35),
                                ],
                            ),
                            shimmer_box(radius=3, height=10, width=160),
                        ],
                    ),
                ],
            ),
        )

    convo_list = ft.ListView(
        expand=True,
        controls=[convo_tile() for _ in range(6)],
    )

    chat_list_panel = ft.Column(
        spacing=0,
        expand=1 if is_desk else True,
        controls=[list_header, convo_list],
    )

    if is_desk:
        # Desktop Active Chat Panel (Thread Top Bar + Bubbles Canvas + Input Strip)
        thread_header = ft.Container(
            padding=ft.Padding.symmetric(horizontal=16, vertical=10),
            border=ft.Border(bottom=ft.BorderSide(1, GREY_DIVIDER)),
            content=ft.Row(
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    shimmer_box(radius=999, width=38, height=38),
                    ft.Column(
                        spacing=3,
                        controls=[
                            shimmer_box(radius=4, height=13, width=110),
                            shimmer_box(radius=3, height=9, width=60),
                        ],
                    ),
                ],
            ),
        )

        def bubble_left():
            return ft.Row(
                alignment=ft.MainAxisAlignment.START,
                controls=[
                    grey_card(
                        content=ft.Column(
                            spacing=4,
                            controls=[
                                shimmer_box(radius=4, height=11, width=140),
                                shimmer_box(radius=4, height=11, width=100),
                            ],
                        ),
                        padding=10,
                        radius=12,
                    )
                ],
            )

        def bubble_right():
            return ft.Row(
                alignment=ft.MainAxisAlignment.END,
                controls=[
                    ft.Container(
                        padding=ft.Padding.all(10),
                        border_radius=ft.BorderRadius.all(12),
                        bgcolor=GREY_BOX_COLOR,
                        content=ft.Column(
                            spacing=4,
                            controls=[
                                shimmer_box(radius=4, height=11, width=160, darker=True),
                                shimmer_box(radius=4, height=11, width=80, darker=True),
                            ],
                        ),
                    )
                ],
            )

        thread_messages = ft.ListView(
            expand=True,
            padding=ft.Padding.all(16),
            controls=[
                bubble_left(),
                ft.Container(height=8),
                bubble_right(),
                ft.Container(height=8),
                bubble_left(),
                ft.Container(height=8),
                bubble_right(),
            ],
        )

        thread_input = ft.Container(
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            border=ft.Border(top=ft.BorderSide(1, GREY_DIVIDER)),
            content=ft.Row(
                spacing=10,
                controls=[
                    shimmer_box(radius=999, width=32, height=32),
                    shimmer_box(radius=8, height=38, expand=True),
                    shimmer_box(radius=999, width=36, height=36),
                ],
            ),
        )

        active_chat_panel = ft.Container(
            expand=2,
            border=ft.Border(left=ft.BorderSide(1, GREY_DIVIDER)),
            content=ft.Column(
                spacing=0,
                expand=True,
                controls=[
                    thread_header,
                    thread_messages,
                    thread_input,
                ],
            ),
        )

        return ft.Row(
            expand=True,
            spacing=0,
            controls=[chat_list_panel, active_chat_panel],
        )

    return chat_list_panel


# ─────────────────────────────────────────────────────────────────────────────
# 9. PROFILE & MEMBER PROFILE SKELETON (/profile, /member/:id)
# ─────────────────────────────────────────────────────────────────────────────
def build_profile_skeleton(page: ft.Page, is_member: bool = False) -> ft.Control:
    # Hero Banner with Centered Circular Avatar
    hero_banner = grey_card(
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            controls=[
                shimmer_box(radius=999, width=88, height=88, darker=True),
                shimmer_box(radius=6, height=18, width=150),
                shimmer_box(radius=999, height=22, width=80),
                shimmer_box(radius=4, height=11, width=180),
                ft.Container(height=4),
                shimmer_box(radius=8, height=34, width=130),
            ],
        ),
        padding=20,
        radius=16,
    )

    # Learning Momentum (4 Bento Stats)
    def momentum_card():
        return grey_card(
            col={"xs": 6, "sm": 3},
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
                controls=[
                    shimmer_box(radius=999, width=26, height=26),
                    shimmer_box(radius=5, height=18, width=50),
                    shimmer_box(radius=3, height=9, width=65),
                ],
            ),
            padding=12,
            radius=12,
        )

    momentum_row = ft.ResponsiveRow(
        spacing=10,
        run_spacing=10,
        controls=[momentum_card() for _ in range(4)],
    )

    # Shortcuts / Study Hub Card
    shortcuts_grid = ft.Row(
        spacing=10,
        controls=[
            grey_card(
                content=ft.Row(
                    spacing=8,
                    controls=[
                        shimmer_box(radius=6, width=24, height=24),
                        shimmer_box(radius=4, height=13, width=90),
                    ],
                ),
                padding=12,
                radius=10,
                expand=True,
            ),
            grey_card(
                content=ft.Row(
                    spacing=8,
                    controls=[
                        shimmer_box(radius=6, width=24, height=24),
                        shimmer_box(radius=4, height=13, width=90),
                    ],
                ),
                padding=12,
                radius=10,
                expand=True,
            ),
        ],
    )

    # Account Details Card
    def detail_tile():
        return ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                shimmer_box(radius=4, height=11, width=70),
                shimmer_box(radius=4, height=12, width=120),
            ],
        )

    account_card = grey_card(
        content=ft.Column(
            spacing=10,
            controls=[
                shimmer_box(radius=4, height=13, width=130),
                detail_tile(),
                detail_tile(),
                detail_tile(),
            ],
        ),
        padding=16,
        radius=14,
    )

    # System Settings Card (Theme Toggle & Logout)
    settings_card = grey_card(
        content=ft.Column(
            spacing=10,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        shimmer_box(radius=4, height=13, width=90),
                        shimmer_box(radius=999, height=22, width=44),
                    ],
                ),
                ft.Divider(height=1, color=GREY_DIVIDER),
                shimmer_box(radius=8, height=36, expand=True),
            ],
        ),
        padding=16,
        radius=14,
    )

    return ft.ListView(
        expand=True,
        padding=ft.Padding.symmetric(horizontal=16, vertical=16),
        controls=[
            hero_banner,
            ft.Container(height=14),
            momentum_row,
            ft.Container(height=14),
            shortcuts_grid,
            ft.Container(height=14),
            account_card,
            ft.Container(height=14),
            settings_card,
            ft.Container(height=24),
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# 10. EDIT PROFILE SKELETON (/edit-profile)
# ─────────────────────────────────────────────────────────────────────────────
def build_edit_profile_skeleton(page: ft.Page) -> ft.Control:
    # Header: Back arrow + Title + Subtitle
    header = ft.Container(
        padding=ft.Padding.only(left=16, right=16, top=12, bottom=8),
        content=ft.Row(
            spacing=12,
            controls=[
                shimmer_box(radius=6, width=24, height=24),
                ft.Column(
                    spacing=2,
                    controls=[
                        shimmer_box(radius=5, height=18, width=130),
                        shimmer_box(radius=4, height=11, width=180),
                    ],
                ),
            ],
        ),
    )

    # Form Cards (Personal, Academic, Account)
    def form_card(num_fields: int = 2):
        return grey_card(
            content=ft.Column(
                spacing=12,
                controls=[
                    shimmer_box(radius=4, height=14, width=120),
                    *[shimmer_box(radius=8, height=44, expand=True) for _ in range(num_fields)],
                ],
            ),
            padding=16,
            radius=14,
        )

    action_buttons = ft.Row(
        spacing=12,
        controls=[
            shimmer_box(radius=8, height=42, expand=True),
            shimmer_box(radius=8, height=42, expand=True),
        ],
    )

    return ft.ListView(
        expand=True,
        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
        controls=[
            header,
            ft.Container(height=8),
            form_card(2),
            ft.Container(height=12),
            form_card(2),
            ft.Container(height=12),
            form_card(1),
            ft.Container(height=16),
            action_buttons,
            ft.Container(height=24),
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# 11. SELF STUDY SKELETON (/self-study)
#     (EXCLUDES TOP APP BAR)
# ─────────────────────────────────────────────────────────────────────────────
def build_self_study_skeleton(page: ft.Page) -> ft.Control:
    # Command Center Hero Banner
    hero_banner = grey_card(
        content=ft.ResponsiveRow(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
            controls=[
                ft.Container(
                    col={"xs": 12, "md": 8},
                    content=ft.Column(
                        spacing=6,
                        controls=[
                            ft.Row(
                                spacing=6,
                                controls=[
                                    shimmer_box(radius=999, height=20, width=80),
                                    shimmer_box(radius=999, height=20, width=100),
                                ],
                            ),
                            shimmer_box(radius=6, height=22, width=220),
                            shimmer_box(radius=4, height=12, width=260),
                            ft.Container(height=4),
                            shimmer_box(radius=8, height=36, width=140),
                        ],
                    ),
                ),
                ft.Container(
                    col={"xs": 12, "md": 4},
                    alignment=ft.Alignment.CENTER_RIGHT,
                    content=grey_card(
                        content=ft.Row(
                            spacing=10,
                            controls=[
                                shimmer_box(radius=999, width=40, height=40),
                                ft.Column(
                                    spacing=3,
                                    controls=[
                                        shimmer_box(radius=4, height=12, width=70),
                                        shimmer_box(radius=4, height=10, width=90),
                                    ],
                                ),
                            ],
                        ),
                        padding=12,
                        radius=10,
                    ),
                ),
            ],
        ),
        padding=18,
        radius=16,
    )

    # Scope Filter Bar
    scope_bar = grey_card(
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                shimmer_box(radius=4, height=13, width=180),
                shimmer_box(radius=6, height=26, width=80),
            ],
        ),
        padding=12,
        radius=10,
    )

    # 3 Bento Study Modes (Flashcards, Quiz, Exam Simulator)
    def bento_mode_card():
        return grey_card(
            col={"xs": 12, "sm": 6, "md": 4},
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            shimmer_box(radius=8, width=38, height=38),
                            shimmer_box(radius=999, height=18, width=50),
                        ],
                    ),
                    shimmer_box(radius=5, height=16, width=110),
                    shimmer_box(radius=4, height=11, expand=True),
                    shimmer_box(radius=4, height=11, width=140),
                    ft.Divider(height=1, color=GREY_DIVIDER),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            shimmer_box(radius=4, height=11, width=65),
                            shimmer_box(radius=4, width=14, height=14),
                        ],
                    ),
                ],
            ),
            padding=16,
            radius=14,
        )

    modes_row = ft.ResponsiveRow(
        spacing=12,
        run_spacing=12,
        controls=[bento_mode_card() for _ in range(3)],
    )

    # Creative Studio Card
    studio_card = grey_card(
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(
                    spacing=12,
                    controls=[
                        shimmer_box(radius=8, width=40, height=40),
                        ft.Column(
                            spacing=4,
                            controls=[
                                shimmer_box(radius=4, height=14, width=160),
                                shimmer_box(radius=4, height=10, width=210),
                            ],
                        ),
                    ],
                ),
                shimmer_box(radius=8, height=34, width=120),
            ],
        ),
        padding=14,
        radius=12,
    )

    return ft.ListView(
        expand=True,
        padding=ft.Padding.symmetric(horizontal=16, vertical=14),
        controls=[
            hero_banner,
            ft.Container(height=12),
            scope_bar,
            ft.Container(height=12),
            modes_row,
            ft.Container(height=12),
            studio_card,
            ft.Container(height=24),
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# 12. COURSE STATS SKELETON (/courses/:id/stats)
#     (EXCLUDES TOP APP BAR)
# ─────────────────────────────────────────────────────────────────────────────
def build_course_stats_skeleton(page: ft.Page) -> ft.Control:
    # Celebratory Hero Banner
    hero_banner = grey_card(
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
            controls=[
                shimmer_box(radius=999, width=56, height=56, darker=True),
                shimmer_box(radius=999, height=22, width=130),
                shimmer_box(radius=6, height=22, width=220),
                shimmer_box(radius=4, height=11, width=160),
                ft.Container(height=4),
                shimmer_box(radius=8, height=34, width=110),
            ],
        ),
        padding=18,
        radius=16,
    )

    # Verified Certificate Card
    cert_card = grey_card(
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(
                    spacing=10,
                    controls=[
                        shimmer_box(radius=8, width=36, height=36),
                        ft.Column(
                            spacing=3,
                            controls=[
                                shimmer_box(radius=4, height=13, width=150),
                                shimmer_box(radius=4, height=10, width=100),
                            ],
                        ),
                    ],
                ),
                shimmer_box(radius=8, height=32, width=95),
            ],
        ),
        padding=14,
        radius=12,
    )

    # Bento Stats Row (4 cards)
    def stat_box():
        return grey_card(
            col={"xs": 6, "md": 3},
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
                controls=[
                    shimmer_box(radius=999, width=24, height=24),
                    shimmer_box(radius=6, height=18, width=50),
                    shimmer_box(radius=3, height=9, width=65),
                ],
            ),
            padding=12,
            radius=12,
        )

    bento_stats = ft.ResponsiveRow(
        spacing=10,
        run_spacing=10,
        controls=[stat_box() for _ in range(4)],
    )

    # 2-Column Analytics Charts Row
    def chart_card():
        return grey_card(
            col={"xs": 12, "lg": 6},
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            shimmer_box(radius=4, height=13, width=120),
                            shimmer_box(radius=4, height=10, width=80),
                        ],
                    ),
                    shimmer_box(radius=8, height=130, expand=True),
                ],
            ),
            padding=14,
            radius=14,
        )

    charts_row = ft.ResponsiveRow(
        spacing=12,
        run_spacing=12,
        controls=[chart_card(), chart_card()],
    )

    return ft.ListView(
        expand=True,
        padding=ft.Padding.symmetric(horizontal=16, vertical=14),
        controls=[
            hero_banner,
            ft.Container(height=12),
            cert_card,
            ft.Container(height=12),
            bento_stats,
            ft.Container(height=12),
            charts_row,
            ft.Container(height=24),
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# 13. ANALYTICS SKELETON (/courses/:id/analytics, /playlists/:id/analytics)
# ─────────────────────────────────────────────────────────────────────────────
def build_analytics_skeleton(page: ft.Page) -> ft.Control:
    # Hero Card with Title & Badges
    hero_card = grey_card(
        content=ft.Column(
            spacing=8,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            spacing=8,
                            controls=[
                                shimmer_box(radius=6, width=22, height=22),
                                shimmer_box(radius=4, height=13, width=140),
                            ],
                        ),
                        shimmer_box(radius=4, height=13, width=70),
                    ],
                ),
                ft.Divider(height=1, color=GREY_DIVIDER),
                shimmer_box(radius=6, height=20, width=200),
                shimmer_box(radius=4, height=11, width=240),
                ft.Row(
                    spacing=6,
                    controls=[
                        shimmer_box(radius=999, height=18, width=60),
                        shimmer_box(radius=999, height=18, width=70),
                        shimmer_box(radius=999, height=18, width=80),
                    ],
                ),
            ],
        ),
        padding=16,
        radius=14,
    )

    # Tabs Row
    tabs_row = ft.Row(
        spacing=8,
        controls=[
            shimmer_box(radius=8, height=32, width=130),
            shimmer_box(radius=8, height=32, width=140),
            shimmer_box(radius=8, height=32, width=120),
        ],
    )

    # 4 Bento KPI Metric Cards
    def kpi_box():
        return grey_card(
            col={"xs": 6, "md": 3},
            content=ft.Column(
                spacing=4,
                controls=[
                    shimmer_box(radius=6, width=22, height=22),
                    shimmer_box(radius=6, height=18, width=50),
                    shimmer_box(radius=3, height=9, width=75),
                ],
            ),
            padding=12,
            radius=12,
        )

    kpi_row = ft.ResponsiveRow(
        spacing=10,
        run_spacing=10,
        controls=[kpi_box() for _ in range(4)],
    )

    # Completion Funnel & Weekly Activity Chart
    chart_block1 = grey_card(
        content=ft.Column(
            spacing=10,
            controls=[
                shimmer_box(radius=4, height=13, width=150),
                shimmer_box(radius=6, height=60, expand=True),
            ],
        ),
        padding=14,
        radius=14,
    )

    chart_block2 = grey_card(
        content=ft.Column(
            spacing=10,
            controls=[
                shimmer_box(radius=4, height=13, width=170),
                shimmer_box(radius=8, height=140, expand=True),
            ],
        ),
        padding=14,
        radius=14,
    )

    return ft.ListView(
        expand=True,
        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
        controls=[
            hero_card,
            ft.Container(height=12),
            tabs_row,
            ft.Container(height=12),
            kpi_row,
            ft.Container(height=12),
            chart_block1,
            ft.Container(height=12),
            chart_block2,
            ft.Container(height=24),
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# 14. PLAYLIST VIEW SKELETON (/playlists/:id)
#     (EXCLUDES TOP APP BAR)
# ─────────────────────────────────────────────────────────────────────────────
def build_playlist_view_skeleton(page: ft.Page) -> ft.Control:
    # Hero Card (Thumb + Title + Desc + Stats)
    hero_card = grey_card(
        content=ft.ResponsiveRow(
            columns=12,
            spacing=16,
            controls=[
                ft.Container(
                    col={"xs": 12, "md": 5},
                    content=shimmer_box(radius=14, height=160, expand=True),
                ),
                ft.Container(
                    col={"xs": 12, "md": 7},
                    content=ft.Column(
                        spacing=8,
                        controls=[
                            shimmer_box(radius=999, height=20, width=90),
                            shimmer_box(radius=6, height=22, width=220),
                            shimmer_box(radius=4, height=11, expand=True),
                            shimmer_box(radius=4, height=11, width=180),
                            ft.Row(
                                spacing=8,
                                controls=[
                                    shimmer_box(radius=6, height=26, width=70),
                                    shimmer_box(radius=6, height=26, width=75),
                                ],
                            ),
                        ],
                    ),
                ),
            ],
        ),
        padding=16,
        radius=16,
    )

    # Sequential Roadmap Cards (Left Column)
    def roadmap_item(step: int):
        return grey_card(
            content=ft.Row(
                spacing=12,
                controls=[
                    shimmer_box(radius=999, width=28, height=28, darker=True),
                    ft.Column(
                        expand=True,
                        spacing=4,
                        controls=[
                            shimmer_box(radius=4, height=13, width=150),
                            shimmer_box(radius=4, height=10, width=90),
                        ],
                    ),
                    shimmer_box(radius=6, height=26, width=65),
                ],
            ),
            padding=12,
            radius=12,
        )

    timeline_column = ft.Column(
        spacing=10,
        controls=[roadmap_item(1), roadmap_item(2), roadmap_item(3)],
    )

    # Sticky Enrollment Card (Right Column)
    enrollment_card = grey_card(
        content=ft.Column(
            spacing=12,
            controls=[
                shimmer_box(radius=8, height=36, expand=True),
                shimmer_box(radius=10, height=44, expand=True),
                ft.Divider(height=1, color=GREY_DIVIDER),
                shimmer_box(radius=4, height=12, width=110),
                shimmer_box(radius=4, height=10, expand=True),
                shimmer_box(radius=4, height=10, expand=True),
            ],
        ),
        padding=16,
        radius=14,
    )

    body_grid = ft.ResponsiveRow(
        columns=12,
        spacing=16,
        run_spacing=16,
        controls=[
            ft.Container(content=timeline_column, col={"xs": 12, "md": 7, "lg": 8}),
            ft.Container(content=enrollment_card, col={"xs": 12, "md": 5, "lg": 4}),
        ],
    )

    return ft.ListView(
        expand=True,
        padding=ft.Padding.symmetric(horizontal=16, vertical=14),
        controls=[
            hero_card,
            ft.Container(height=14),
            body_grid,
            ft.Container(height=24),
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# 15. PLAYLIST BUILDER SKELETON (/playlists/:id/build)
# ─────────────────────────────────────────────────────────────────────────────
def build_playlist_builder_skeleton(page: ft.Page) -> ft.Control:
    # Top Action Bar
    top_bar = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            ft.Row(
                spacing=10,
                controls=[
                    shimmer_box(radius=6, width=24, height=24),
                    shimmer_box(radius=6, height=22, width=160),
                ],
            ),
            shimmer_box(radius=8, height=36, width=110),
        ],
    )

    # Reorderable Course List Items
    def reorder_item():
        return grey_card(
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row(
                        spacing=10,
                        controls=[
                            shimmer_box(radius=999, width=28, height=28),
                            shimmer_box(radius=4, height=14, width=180),
                        ],
                    ),
                    ft.Row(
                        spacing=6,
                        controls=[
                            shimmer_box(radius=4, width=20, height=20),
                            shimmer_box(radius=4, width=20, height=20),
                            shimmer_box(radius=4, width=20, height=20),
                        ],
                    ),
                ],
            ),
            padding=12,
            radius=10,
        )

    items = [reorder_item() for _ in range(4)]
    add_btn = shimmer_box(radius=8, height=40, width=120)

    return ft.ListView(
        expand=True,
        padding=ft.Padding.symmetric(horizontal=16, vertical=16),
        controls=[
            top_bar,
            ft.Container(height=16),
            *items,
            ft.Container(height=12),
            add_btn,
            ft.Container(height=24),
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# 16. LIBRARY GRID SKELETON (/create-course, /organisations/:id/courses, /playlists)
# ─────────────────────────────────────────────────────────────────────────────
def build_library_grid_skeleton(page: ft.Page) -> ft.Control:
    # Library Banner Header
    banner = grey_card(
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Column(
                    spacing=4,
                    controls=[
                        shimmer_box(radius=5, height=20, width=160),
                        shimmer_box(radius=4, height=11, width=80),
                    ],
                ),
                shimmer_box(radius=8, height=36, width=120),
            ],
        ),
        padding=16,
        radius=14,
    )

    search_bar = shimmer_box(radius=10, height=40, expand=True)

    def lib_card():
        return grey_card(
            col={"xs": 12, "sm": 6},
            content=ft.Column(
                spacing=8,
                controls=[
                    shimmer_box(radius=10, height=110, expand=True),
                    ft.Row(
                        spacing=6,
                        controls=[
                            shimmer_box(radius=999, height=18, width=55),
                            shimmer_box(radius=999, height=18, width=70),
                        ],
                    ),
                    shimmer_box(radius=5, height=15, width=160),
                    shimmer_box(radius=4, height=10, expand=True),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            shimmer_box(radius=6, height=28, width=85),
                            shimmer_box(radius=6, height=28, width=85),
                        ],
                    ),
                ],
            ),
            padding=12,
            radius=14,
        )

    grid = ft.ResponsiveRow(
        spacing=14,
        run_spacing=14,
        controls=[lib_card() for _ in range(4)],
    )

    return ft.ListView(
        expand=True,
        padding=ft.Padding.symmetric(horizontal=16, vertical=14),
        controls=[
            banner,
            ft.Container(height=12),
            search_bar,
            ft.Container(height=12),
            grid,
            ft.Container(height=24),
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# 17. SETTINGS SKELETON (/organisations/:id/courses/:id/settings, /playlists/:id/settings)
# ─────────────────────────────────────────────────────────────────────────────
def build_settings_skeleton(page: ft.Page) -> ft.Control:
    # Header Card
    header_card = grey_card(
        content=ft.Row(
            spacing=10,
            controls=[
                shimmer_box(radius=6, width=24, height=24),
                ft.Column(
                    spacing=2,
                    controls=[
                        shimmer_box(radius=5, height=18, width=160),
                        shimmer_box(radius=4, height=11, width=110),
                    ],
                ),
            ],
        ),
        padding=14,
        radius=12,
    )

    # General Settings Card
    general_card = grey_card(
        content=ft.Column(
            spacing=12,
            controls=[
                shimmer_box(radius=4, height=14, width=120),
                shimmer_box(radius=8, height=44, expand=True),
                shimmer_box(radius=8, height=44, expand=True),
                shimmer_box(radius=8, height=44, expand=True),
                ft.Row(
                    alignment=ft.MainAxisAlignment.END,
                    controls=[shimmer_box(radius=8, height=36, width=100)],
                ),
            ],
        ),
        padding=16,
        radius=14,
    )

    # Danger Zone Card
    danger_card = grey_card(
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Column(
                    spacing=2,
                    controls=[
                        shimmer_box(radius=4, height=13, width=90),
                        shimmer_box(radius=3, height=10, width=180),
                    ],
                ),
                shimmer_box(radius=8, height=34, width=100),
            ],
        ),
        padding=16,
        radius=14,
    )

    return ft.ListView(
        expand=True,
        padding=ft.Padding.symmetric(horizontal=16, vertical=14),
        controls=[
            header_card,
            ft.Container(height=12),
            general_card,
            ft.Container(height=12),
            danger_card,
            ft.Container(height=24),
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# 18. INVITE MEMBERS SKELETON (/organisations/:id/invite-members)
# ─────────────────────────────────────────────────────────────────────────────
def build_invite_members_skeleton(page: ft.Page) -> ft.Control:
    header = ft.Container(
        padding=ft.Padding.only(left=16, right=16, top=12, bottom=8),
        content=ft.Row(
            spacing=10,
            controls=[
                shimmer_box(radius=6, width=22, height=22),
                ft.Column(
                    spacing=2,
                    controls=[
                        shimmer_box(radius=5, height=18, width=180),
                        shimmer_box(radius=4, height=11, width=210),
                    ],
                ),
            ],
        ),
    )

    invite_form = grey_card(
        content=ft.Column(
            spacing=12,
            controls=[
                shimmer_box(radius=4, height=13, width=130),
                shimmer_box(radius=8, height=44, expand=True),
                shimmer_box(radius=8, height=44, expand=True),
                shimmer_box(radius=8, height=42, expand=True),
            ],
        ),
        padding=16,
        radius=14,
    )

    def pending_tile():
        return ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Column(
                    spacing=3,
                    controls=[
                        shimmer_box(radius=4, height=13, width=150),
                        shimmer_box(radius=999, height=16, width=60),
                    ],
                ),
                shimmer_box(radius=6, height=28, width=70),
            ],
        )

    pending_card = grey_card(
        content=ft.Column(
            spacing=10,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        shimmer_box(radius=4, height=14, width=110),
                        shimmer_box(radius=999, height=18, width=30),
                    ],
                ),
                ft.Divider(height=1, color=GREY_DIVIDER),
                pending_tile(),
                pending_tile(),
            ],
        ),
        padding=16,
        radius=14,
    )

    return ft.ListView(
        expand=True,
        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
        controls=[
            header,
            ft.Container(height=8),
            invite_form,
            ft.Container(height=12),
            pending_card,
            ft.Container(height=24),
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# 19. OFFLINE COURSES SKELETON (/offline)
#     (EXCLUDES TOP APP BAR)
# ─────────────────────────────────────────────────────────────────────────────
def build_offline_skeleton(page: ft.Page) -> ft.Control:
    sync_bar = ft.Container(
        padding=ft.Padding.symmetric(horizontal=16, vertical=10),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                shimmer_box(radius=4, height=12, width=130),
                shimmer_box(radius=6, height=26, width=80),
            ],
        ),
    )

    def offline_card():
        return grey_card(
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Column(
                        spacing=4,
                        expand=True,
                        controls=[
                            shimmer_box(radius=5, height=16, width=170),
                            shimmer_box(radius=4, height=11, width=110),
                        ],
                    ),
                    shimmer_box(radius=8, width=28, height=28),
                ],
            ),
            padding=14,
            radius=12,
        )

    return ft.ListView(
        expand=True,
        padding=ft.Padding.symmetric(horizontal=16, vertical=10),
        controls=[
            sync_bar,
            ft.Divider(height=1, color=GREY_DIVIDER),
            ft.Container(height=8),
            offline_card(),
            ft.Container(height=8),
            offline_card(),
            ft.Container(height=8),
            offline_card(),
            ft.Container(height=24),
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE RESOLVER & SKELETON VIEW FACTORY
# ─────────────────────────────────────────────────────────────────────────────
def build_skeleton_view(route: str, page: ft.Page | None = None) -> ft.View:
    """Produces the exact 1-to-1 grey shimmer skeleton for the specified route,

    with top app bars strictly excluded.
    """
    clean_route = (route or "").split("?")[0]
    troute = ft.TemplateRoute(clean_route)

    # 1. Exact route matches
    if clean_route == "/dashboard":
        body = build_dashboard_skeleton(page)
    elif clean_route == "/courses":
        body = build_courses_skeleton(page)
    elif clean_route == "/network":
        body = build_network_skeleton(page)
    elif clean_route == "/nu-chat":
        body = build_chat_skeleton(page)
    elif clean_route == "/organisations":
        body = build_organisations_skeleton(page)
    elif clean_route == "/profile":
        body = build_profile_skeleton(page, is_member=False)
    elif clean_route == "/edit-profile":
        body = build_edit_profile_skeleton(page)
    elif clean_route == "/self-study":
        body = build_self_study_skeleton(page)
    elif clean_route == "/offline":
        body = build_offline_skeleton(page)

    # 2. Parametrized route matches (most specific first)
    elif troute.match("/courses/:id/stats"):
        body = build_course_stats_skeleton(page)
    elif troute.match("/courses/:id/view") or troute.match("/courses/:id/offline"):
        body = build_course_learner_skeleton(page)
    elif troute.match("/courses/:id/manage"):
        body = build_course_builder_skeleton(page)
    elif troute.match("/organisations/:org_id/courses/:id/settings"):
        body = build_settings_skeleton(page)
    elif troute.match("/courses/:id/settings"):
        body = build_settings_skeleton(page)
    elif troute.match("/organisations/:org_id/courses/:id/analytics"):
        body = build_analytics_skeleton(page)
    elif troute.match("/organisations/:org_id/playlists/:id/analytics"):
        body = build_analytics_skeleton(page)
    elif troute.match("/organisations/:org_id/invite-members"):
        body = build_invite_members_skeleton(page)
    elif troute.match("/organisations/:org_id/courses") or clean_route == "/create-course":
        body = build_library_grid_skeleton(page)
    elif troute.match("/organisations/:org_id/playlists"):
        body = build_library_grid_skeleton(page)
    elif troute.match("/playlists/:id/build"):
        body = build_playlist_builder_skeleton(page)
    elif troute.match("/playlists/:id/settings"):
        body = build_settings_skeleton(page)
    elif troute.match("/playlists/:id/analytics"):
        body = build_analytics_skeleton(page)
    elif troute.match("/playlists/:id"):
        body = build_playlist_view_skeleton(page)
    elif troute.match("/member/:id"):
        body = build_profile_skeleton(page, is_member=True)
    elif troute.match("/courses/:id"):
        body = build_course_details_skeleton(page)
    else:
        # Fallback to general list skeleton
        body = ft.ListView(
            expand=True,
            padding=ft.Padding.all(16),
            controls=[
                shimmer_box(radius=8, height=48, expand=True) for _ in range(5)
            ],
        )

    # Assemble View with NO appbar
    view = ft.View(
        route=route,
        appbar=None,
        padding=0,
        bgcolor=ft.Colors.SURFACE,
        controls=[
            ft.SafeArea(
                expand=True,
                content=body,
            )
        ],
    )
    view.data = collect_shimmer_boxes(body)
    return view
