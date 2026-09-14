"""
Modern Completed Course Card for Nu-Age LMS.
Displays finished curriculum achievements with 100% progress indicator,
course thumbnail/avatar, verified completion badges, and dual actions
(Review Course and My Stats/Certificate), matching the modern card design system.
"""

from typing import Any, Callable, Dict, Optional
import flet as ft
from src.components.course_card_theme import (
    get_card_palette,
    get_course_module_meta,
    build_course_avatar,
)


def get_completed_card(
    course_name: str,
    course_id: str,
    on_review_click: Callable[[str], Any],
    on_stats_click: Callable[[str], Any],
    page: Optional[ft.Page] = None,
    image_url: Optional[str] = None,
    category: Optional[str] = None,
    author: Optional[str] = None,
    rating: Optional[float] = None,
    completed_at: Optional[str] = None,
    course_dict: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> ft.Container:
    """
    Renders a modern, responsive card for completed courses with full theme adaptability.
    Supports both legacy arguments and modern rich course metadata.
    """
    c_dict = course_dict or {}
    c_img = image_url or c_dict.get("image_url")
    c_cat = category or (c_dict.get("category", {}) if isinstance(c_dict.get("category"), dict) else {}).get("name") or "Course"
    
    # Author resolution
    if not author:
        admin = c_dict.get("admin") or {}
        if isinstance(admin, dict):
            first = admin.get("first_name", "")
            last = admin.get("last_name", "")
            author = f"{first} {last}".strip() or "Course Instructor"
        else:
            author = "Course Instructor"

    # Theme and palette
    is_dark = getattr(page, "theme_mode", None) == ft.ThemeMode.DARK if page else False
    palette = get_card_palette(c_cat, course_name, is_dark=is_dark)

    # Modules metadata
    modules_data = c_dict.get("modules")
    total_modules, _, time_str = get_course_module_meta(
        modules_data, seed_key=course_id or course_name, progress=100.0
    )

    # ── 1. Top Badges Row ─────────────────────────────────────────────────────
    completion_badge = ft.Container(
        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        border_radius=ft.BorderRadius.all(12),
        bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.GREEN_600 if not is_dark else ft.Colors.GREEN_400),
        content=ft.Row(
            spacing=4,
            tight=True,
            controls=[
                ft.Icon(
                    ft.Icons.CHECK_CIRCLE_ROUNDED,
                    size=12,
                    color=ft.Colors.GREEN_700 if not is_dark else ft.Colors.GREEN_400,
                ),
                ft.Text(
                    "100% Completed",
                    size=10,
                    weight=ft.FontWeight.W_800,
                    color=ft.Colors.GREEN_700 if not is_dark else ft.Colors.GREEN_400,
                ),
            ],
        ),
    )

    category_pill = ft.Container(
        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        border_radius=ft.BorderRadius.all(12),
        bgcolor=palette["badge_bg"],
        content=ft.Text(
            c_cat.upper(),
            size=9.5,
            weight=ft.FontWeight.W_800,
            color=palette["accent"],
        ),
    )

    badge_row = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[category_pill, completion_badge],
    )

    # ── 2. Header Content (Title + Avatar) ────────────────────────────────────
    avatar_widget = build_course_avatar(c_img, palette, size=74)

    left_info = ft.Column(
        expand=True,
        spacing=6,
        controls=[
            badge_row,
            ft.Text(
                course_name,
                size=15,
                weight=ft.FontWeight.W_800,
                color=ft.Colors.ON_SURFACE,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
            ft.Row(
                spacing=5,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.PERSON_OUTLINED, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text(
                        author,
                        size=11,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        weight=ft.FontWeight.W_500,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                ],
            ),
        ],
    )

    top_content = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.START,
        spacing=12,
        controls=[
            left_info,
            avatar_widget,
        ],
    )

    # ── 3. Meta and Progress Section ──────────────────────────────────────────
    meta_row = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Row(
                spacing=4,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.AUTO_STORIES_ROUNDED, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text(
                        f"{total_modules} modules · {time_str}",
                        size=11,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        weight=ft.FontWeight.W_500,
                    ),
                ],
            ),
            ft.Row(
                spacing=4,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.EMOJI_EVENTS_ROUNDED, size=13, color=ft.Colors.AMBER_600),
                    ft.Text(
                        "Certified",
                        size=11,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.AMBER_700 if not is_dark else ft.Colors.AMBER_400,
                    ),
                ],
            ),
        ],
    )

    progress_bar = ft.ProgressBar(
        value=1.0,
        height=5,
        color=ft.Colors.GREEN_600 if not is_dark else ft.Colors.GREEN_400,
        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE),
        border_radius=ft.BorderRadius.all(2.5),
    )

    # ── 4. Action Buttons ─────────────────────────────────────────────────────
    def _call_handler(fn):
        if not fn:
            return
        try:
            fn(course_id)
        except TypeError:
            try:
                fn(None, course_id)
            except TypeError:
                try:
                    fn(None)
                except TypeError:
                    fn()

    review_button = ft.ElevatedButton(
        content=ft.Row(
            spacing=6,
            tight=True,
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, size=16, color=ft.Colors.ON_PRIMARY),
                ft.Text("Review Course", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_PRIMARY),
            ],
        ),
        bgcolor=ft.Colors.PRIMARY,
        height=36,
        expand=True,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=9),
            elevation=0,
        ),
        on_click=lambda e: _call_handler(on_review_click),
    )

    stats_button = ft.OutlinedButton(
        content=ft.Row(
            spacing=6,
            tight=True,
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.INSIGHTS_ROUNDED, size=15, color=ft.Colors.PRIMARY),
                ft.Text("My Stats", size=12, weight=ft.FontWeight.W_600, color=ft.Colors.PRIMARY),
            ],
        ),
        height=36,
        expand=True,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=9),
            side=ft.BorderSide(1, ft.Colors.with_opacity(0.25, ft.Colors.PRIMARY)),
        ),
        on_click=lambda e: _call_handler(on_stats_click),
    )

    actions_row = ft.Row(
        spacing=8,
        controls=[review_button, stats_button],
    )

    # ── 5. Hover Handlers & Card Container ────────────────────────────────────
    def handle_hover(e):
        is_hovering = e.data == "true"
        card.scale = 1.02 if is_hovering else 1.0
        card.shadow = ft.BoxShadow(
            blur_radius=18 if is_hovering else 8,
            color=ft.Colors.with_opacity(0.12 if is_hovering else 0.05, ft.Colors.BLACK),
            offset=ft.Offset(0, 6 if is_hovering else 2),
        )
        card.update()

    card = ft.Container(
        bgcolor=ft.Colors.SURFACE,
        border_radius=ft.BorderRadius.all(18),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
        padding=ft.Padding.all(16),
        shadow=ft.BoxShadow(
            blur_radius=8,
            color=ft.Colors.with_opacity(0.05, ft.Colors.BLACK),
            offset=ft.Offset(0, 2),
        ),
        scale=1.0,
        animate_scale=ft.Animation(250, ft.AnimationCurve.DECELERATE),
        on_hover=handle_hover,
        content=ft.Column(
            spacing=14,
            controls=[
                top_content,
                meta_row,
                progress_bar,
                actions_row,
            ],
        ),
    )

    return card