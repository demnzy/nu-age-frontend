import flet as ft
from src.components.course_card_theme import (
    get_card_palette,
    get_course_module_meta,
    build_course_avatar,
)


def get_org_course_card(
    course_name: str,
    category: str | None = None,
    org_name: str | None = "Organisation",
    image_url: str | None = None,
    created_at: str | None = None,
    on_view_click=None,
    description: str | None = None,
    modules: list | int | None = None,
    course_dict: dict | None = None,
    page: ft.Page | None = None,
) -> ft.Container:
    """
    Returns a sleek, modern card for an organisation-exclusive course,
    matching the high-production design system of the Learn course cards.
    """
    c_dict = course_dict or {}

    # Category name resolution
    if category:
        category_name = category
    elif isinstance(c_dict.get("category"), dict):
        category_name = c_dict.get("category", {}).get("name") or "General"
    elif isinstance(c_dict.get("category"), str):
        category_name = c_dict.get("category")
    else:
        category_name = "General"

    # Organisation name resolution
    resolved_org = (
        org_name
        or (c_dict.get("organisation", {}).get("name") if isinstance(c_dict.get("organisation"), dict) else None)
        or c_dict.get("organisation")
        or "Organisation"
    )

    # Description resolution
    desc = description or c_dict.get("description")
    if not desc:
        objs = c_dict.get("objectives")
        if isinstance(objs, list) and objs:
            desc = objs[0]
    if not desc or not isinstance(desc, str) or not desc.strip():
        desc = f"Exclusive {category_name.lower()} curriculum curated for members of {resolved_org}."
    else:
        desc = desc.strip()

    # Image URL
    img_url = image_url or c_dict.get("image_url")

    # Author
    instructor_obj = c_dict.get("instructor") or {}
    auth_name = (
        (f"{instructor_obj.get('first_name', '')} {instructor_obj.get('last_name', '')}").strip()
        if isinstance(instructor_obj, dict)
        else str(instructor_obj)
    ) or c_dict.get("author") or f"{resolved_org} Faculty"

    # Modules & Time estimation
    modules_data = modules if modules is not None else c_dict.get("modules")
    total_modules, _, time_str = get_course_module_meta(
        modules_data, seed_key=c_dict.get("id") or course_name, progress=0.0
    )

    # Palette selection (Pastel theme matching the reference design system)
    is_dark = getattr(page, "theme_mode", None) == ft.ThemeMode.DARK if page else False
    palette = get_card_palette(category_name, course_name, is_dark=is_dark)

    # ── Category Pill (Top-Left) ──────────────────────────────────────────────
    category_pill = ft.Container(
        padding=ft.Padding.symmetric(horizontal=8, vertical=3.5),
        bgcolor=palette["badge_bg"],
        border_radius=ft.BorderRadius.all(10),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.18, palette["accent"])),
        content=ft.Text(
            category_name,
            size=10,
            weight=ft.FontWeight.W_700,
            color=palette["accent"],
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        ),
    )

    # ── Organisation Exclusive Badge (Beside Category) ────────────────────────
    org_badge = ft.Container(
        padding=ft.Padding.symmetric(horizontal=8, vertical=3.5),
        bgcolor=ft.Colors.with_opacity(0.10, palette["accent"]),
        border_radius=ft.BorderRadius.all(10),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.22, palette["accent"])),
        content=ft.Row(
            spacing=4,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.BUSINESS_ROUNDED, size=11, color=palette["accent"]),
                ft.Text(
                    resolved_org,
                    size=10,
                    weight=ft.FontWeight.W_700,
                    color=palette["accent"],
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
            ],
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

    # ── Organisation Membership Benefit Banner ────────────────────────────────
    org_status_strip = ft.Container(
        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
        border_radius=ft.BorderRadius.all(8),
        bgcolor=ft.Colors.with_opacity(0.06, palette["accent"] if not is_dark else ft.Colors.WHITE),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.12, palette["accent"] if not is_dark else ft.Colors.WHITE)),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(
                    spacing=6,
                    tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.WORKSPACE_PREMIUM_ROUNDED, size=13, color=palette["accent"]),
                        ft.Text(
                            "Organisation Exclusive",
                            size=10.5,
                            weight=ft.FontWeight.W_700,
                            color=palette["accent"],
                        ),
                    ],
                ),
                ft.Row(
                    spacing=4,
                    tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.VERIFIED_ROUNDED, size=11, color=palette["accent"]),
                        ft.Text(
                            "Member Access",
                            size=10,
                            weight=ft.FontWeight.W_600,
                            color=ft.Colors.GREY_600 if not is_dark else ft.Colors.GREY_400,
                        ),
                    ],
                ),
            ],
        ),
    )

    # ── Vertical Divider ──────────────────────────────────────────────────────
    vertical_divider = ft.Container(
        width=1,
        height=78,
        bgcolor=ft.Colors.with_opacity(0.12, palette["accent"] if not is_dark else ft.Colors.WHITE),
        margin=ft.Margin.symmetric(horizontal=6),
    )

    # ── Top Pastel Body ───────────────────────────────────────────────────────
    top_body = ft.Container(
        padding=ft.Padding.only(left=16, right=16, top=14, bottom=12),
        bgcolor=palette["bg"],
        content=ft.Column(
            spacing=10,
            controls=[
                # Top badges row (Category + Organisation)
                ft.Row(
                    spacing=6,
                    wrap=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        category_pill,
                        org_badge,
                    ],
                ),
                # Row containing: Left (Content) + Divider + Right (Image)
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    controls=[
                        # Left content column
                        ft.Column(
                            expand=True,
                            spacing=5,
                            controls=[
                                ft.Text(
                                    course_name,
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
                # Exclusive membership status strip
                org_status_strip,
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
        content=ft.Row(
            spacing=4,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Text(
                    "View Course",
                    size=11.5,
                    weight=ft.FontWeight.W_700,
                    color=palette["btn_text"],
                ),
                ft.Icon(
                    ft.Icons.ARROW_FORWARD_ROUNDED,
                    size=13,
                    color=palette["btn_text"],
                ),
            ],
        ),
    )

    # ── Bottom White / Surface Footer ─────────────────────────────────────────
    footer_text = f"Added {created_at}" if created_at else f"By {auth_name}"
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
                ft.Row(
                    spacing=5,
                    tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(
                            ft.Icons.CALENDAR_TODAY_ROUNDED if created_at else ft.Icons.PERSON_ROUNDED,
                            size=12,
                            color=ft.Colors.GREY_500,
                        ),
                        ft.Text(
                            footer_text,
                            size=11,
                            weight=ft.FontWeight.W_600,
                            color=ft.Colors.GREY_600 if not is_dark else ft.Colors.GREY_400,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
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

    # ── Main Card Container ───────────────────────────────────────────────────
    card = ft.Container(
        border_radius=ft.BorderRadius.all(24),
        border=ft.Border.all(1, palette["border"]),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        shadow=ft.BoxShadow(
            blur_radius=10,
            color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK),
            offset=ft.Offset(0, 3),
        ),
        animate_scale=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
        animate_offset=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
        on_hover=handle_hover,
        ink=True,
        on_click=on_view_click,
        col={"xs": 12, "sm": 6, "md": 6, "lg": 4},
        content=ft.Column(
            spacing=0,
            controls=[
                top_body,
                footer_bar,
            ],
        ),
    )

    return card