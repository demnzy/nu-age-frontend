import flet as ft
from src.components.course_card_theme import (
    get_card_palette,
    get_course_module_meta,
    build_course_avatar,
)


def get_course_card(
    course_title: str,
    course_category: str | None = None,
    course_author: str | None = None,
    image_url: str | None = None,
    created_at: str | None = None,
    on_view_click=None,
    description: str | None = None,
    modules: list | int | None = None,
    course_dict: dict | None = None,
    page: ft.Page | None = None,
):
    c_dict = course_dict or {}

    # Category name resolution
    if course_category:
        category_name = course_category
    elif isinstance(c_dict.get("category"), dict):
        category_name = c_dict.get("category", {}).get("name") or "General"
    elif isinstance(c_dict.get("category"), str):
        category_name = c_dict.get("category")
    else:
        category_name = "General"

    # Description resolution
    desc = description or c_dict.get("description")
    if not desc:
        objs = c_dict.get("objectives")
        if isinstance(objs, list) and objs:
            desc = objs[0]
    if not desc or not isinstance(desc, str) or not desc.strip():
        desc = f"Master core {category_name.lower()} concepts and advance your skills with guided interactive modules."
    else:
        desc = desc.strip()

    # Image URL
    img_url = image_url or c_dict.get("image_url")

    # Author
    auth_name = course_author or "Nu-age Instructor"

    # Module & Time estimation
    modules_data = modules if modules is not None else c_dict.get("modules")
    total_modules, _, time_str = get_course_module_meta(modules_data, course_title, progress=0.0)

    # Palette selection (Pastel theme matching the reference design)
    is_dark = getattr(page, "theme_mode", None) == ft.ThemeMode.DARK if page else False
    palette = get_card_palette(category_name, course_title, is_dark=is_dark)

    # ── Category Pill (Top-Left) ──────────────────────────────────────────────
    category_pill = ft.Container(
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        bgcolor=palette["badge_bg"],
        border_radius=ft.BorderRadius.all(12),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.18, palette["accent"])),
        content=ft.Text(
            category_name,
            size=10.5,
            weight=ft.FontWeight.W_700,
            color=palette["accent"],
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        ),
    )

    # ── Avatar / Illustration (Right Side) ────────────────────────────────────
    avatar_widget = build_course_avatar(img_url, palette, size=82)

    # ── Meta Chips Row (Modules & Time) ───────────────────────────────────────
    meta_row = ft.Row(
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Row(
                spacing=4,
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.AUTO_STORIES_ROUNDED, size=12, color=ft.Colors.GREY_500),
                    ft.Text(
                        f"{total_modules} modules",
                        size=10.5,
                        weight=ft.FontWeight.W_600,
                        color=ft.Colors.GREY_600 if not is_dark else ft.Colors.GREY_300,
                    ),
                ],
            ),
            ft.Container(
                width=3,
                height=3,
                border_radius=ft.BorderRadius.all(1.5),
                bgcolor=ft.Colors.GREY_400,
            ),
            ft.Row(
                spacing=4,
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.SCHEDULE_ROUNDED, size=12, color=ft.Colors.GREY_500),
                    ft.Text(
                        f"~{time_str}",
                        size=10.5,
                        weight=ft.FontWeight.W_600,
                        color=ft.Colors.GREY_600 if not is_dark else ft.Colors.GREY_300,
                    ),
                ],
            ),
        ],
    )

    # ── Progress Section (Progress label down) ────────────────────────────────
    progress_section = ft.Column(
        spacing=4,
        controls=[
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Text(
                        "Progress",
                        size=10.5,
                        weight=ft.FontWeight.W_600,
                        color=ft.Colors.GREY_500 if not is_dark else ft.Colors.GREY_400,
                    ),
                    ft.Text(
                        "0%",
                        size=10.5,
                        weight=ft.FontWeight.W_700,
                        color=ft.Colors.ON_SURFACE,
                    ),
                ],
            ),
            ft.ProgressBar(
                value=0.0,
                height=4,
                color=palette["progress"],
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE),
                border_radius=ft.BorderRadius.all(2),
            ),
        ],
    )

    # ── Vertical Divider ──────────────────────────────────────────────────────
    vertical_divider = ft.Container(
        width=1,
        height=75,
        bgcolor=ft.Colors.with_opacity(0.12, palette["accent"] if not is_dark else ft.Colors.WHITE),
        margin=ft.Margin.symmetric(horizontal=8),
    )

    # ── Top Pastel Body ───────────────────────────────────────────────────────
    top_body = ft.Container(
        padding=ft.Padding.only(left=16, right=16, top=14, bottom=12),
        bgcolor=palette["bg"],
        content=ft.Column(
            spacing=10,
            controls=[
                # Row containing: Left (Content) + Divider + Right (Image)
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    controls=[
                        # Left content column
                        ft.Column(
                            expand=True,
                            spacing=6,
                            controls=[
                                category_pill,
                                ft.Text(
                                    course_title,
                                    size=15,
                                    weight=ft.FontWeight.W_800,
                                    color=ft.Colors.ON_SURFACE,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(
                                    desc,
                                    size=11,
                                    color=ft.Colors.GREY_600 if not is_dark else ft.Colors.GREY_400,
                                    max_lines=2,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                meta_row,
                            ],
                        ),
                        vertical_divider,
                        avatar_widget,
                    ],
                ),
                # Progress Section (down)
                progress_section,
            ],
        ),
    )

    # ── Action Pill Button ────────────────────────────────────────────────────
    view_btn = ft.Container(
        padding=ft.Padding.symmetric(horizontal=16, vertical=7),
        bgcolor=palette["btn_bg"],
        border_radius=ft.BorderRadius.all(20),
        ink=True,
        on_click=on_view_click,
        content=ft.Text(
            "View Course",
            size=11.5,
            weight=ft.FontWeight.W_700,
            color=palette["btn_text"],
        ),
    )

    # ── Bottom White / Surface Footer ─────────────────────────────────────────
    footer_bar = ft.Container(
        padding=ft.Padding.symmetric(horizontal=16, vertical=10),
        bgcolor=palette["footer_bg"],
        border_radius=ft.BorderRadius.only(bottom_left=22, bottom_right=22),
        border=ft.Border.only(
            top=ft.BorderSide(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE))
        ),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Text(
                    f"Est. {time_str} · Self-paced",
                    size=11,
                    weight=ft.FontWeight.W_600,
                    color=ft.Colors.GREY_600 if not is_dark else ft.Colors.GREY_400,
                ),
                view_btn,
            ],
        ),
    )

    # ── Hover Interaction ─────────────────────────────────────────────────────
    def handle_hover(e):
        is_h = e.data == "true"
        e.control.scale = 1.02 if is_h else 1.0
        e.control.shadow = ft.BoxShadow(
            blur_radius=18 if is_h else 10,
            color=ft.Colors.with_opacity(0.12 if is_h else 0.06, ft.Colors.BLACK),
            offset=ft.Offset(0, 6 if is_h else 3),
        )
        e.control.update()

    # ── Master Card Container ─────────────────────────────────────────────────
    return ft.Container(
        offset=ft.Offset(0, 0.08),
        animate_offset=ft.Animation(400, ft.AnimationCurve.DECELERATE),
        scale=1.0,
        animate_scale=ft.Animation(250, ft.AnimationCurve.DECELERATE),
        on_hover=handle_hover,
        tooltip=f"Tap to view {course_title}",
        opacity=0,
        animate_opacity=300,
        bgcolor=palette["bg"],
        border_radius=ft.BorderRadius.all(22),
        border=ft.Border.all(1, palette["border"]),
        shadow=ft.BoxShadow(
            blur_radius=10,
            color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK),
            offset=ft.Offset(0, 3),
        ),
        ink=True,
        on_click=on_view_click,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=ft.Column(
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[
                top_body,
                footer_bar,
            ],
        ),
    )