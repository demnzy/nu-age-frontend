"""
src/components/quick_hub.py

High-utility Quick Launch Hub for Nu-Age Dashboard.
Preserves quick-linking value for 1-tap navigation to core platform utilities:
- Self-Study Hub (/self-study)
- Student Network (/network)
- Nu-Chat (/nu-chat)
- Course Discovery (/courses)
"""

import flet as ft


def get_quick_hub(page: ft.Page) -> ft.Container:
    """Builds a responsive 4-item Quick Hub for fast platform navigation."""
    is_dark = getattr(page, "theme_mode", None) == ft.ThemeMode.DARK
    card_bg = ft.Colors.SURFACE if is_dark else "#FFFFFF"
    border_clr = ft.Colors.with_opacity(0.12, ft.Colors.WHITE) if is_dark else ft.Colors.GREY_200

    items = [
        {
            "title": "Study Hub",
            "desc": "AI Quiz & Cards",
            "icon": ft.Icons.STYLE_ROUNDED,
            "color": ft.Colors.PURPLE_400,
            "route": "/self-study",
        },
        {
            "title": "Network",
            "desc": "Peers & Squads",
            "icon": ft.Icons.PEOPLE_ALT_ROUNDED,
            "color": ft.Colors.TEAL_400,
            "route": "/network",
        },
        {
            "title": "Nu-Chat",
            "desc": "Courses & DMs",
            "icon": ft.Icons.FORUM_ROUNDED,
            "color": ft.Colors.LIGHT_BLUE_400,
            "route": "/nu-chat",
        },
        {
            "title": "Courses",
            "desc": "Explore Catalog",
            "icon": ft.Icons.EXPLORE_ROUNDED,
            "color": ft.Colors.INDIGO_400,
            "route": "/courses",
        },
    ]

    def _make_tile(item: dict) -> ft.Container:
        icon_box = ft.Container(
            width=36,
            height=36,
            border_radius=ft.BorderRadius.all(10),
            bgcolor=ft.Colors.with_opacity(0.12, item["color"]),
            alignment=ft.Alignment.CENTER,
            content=ft.Icon(item["icon"], color=item["color"], size=18),
        )

        return ft.Container(
            expand=True,
            bgcolor=card_bg,
            border_radius=ft.BorderRadius.all(14),
            border=ft.Border.all(1, border_clr),
            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            shadow=ft.BoxShadow(
                blur_radius=6,
                color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                offset=ft.Offset(0, 2),
            ),
            ink=True,
            on_click=lambda _: page.go(item["route"]),
            content=ft.Row(
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    icon_box,
                    ft.Column(
                        spacing=1,
                        alignment=ft.MainAxisAlignment.CENTER,
                        controls=[
                            ft.Text(item["title"], size=12.5, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                            ft.Text(item["desc"], size=10.5, color=ft.Colors.GREY_500),
                        ],
                    ),
                ],
            ),
        )

    tiles = [_make_tile(it) for it in items]

    is_desktop = (page.width or 400) >= 700

    if is_desktop:
        grid_content = ft.Row(
            spacing=12,
            controls=tiles,
        )
    else:
        grid_content = ft.Column(
            spacing=10,
            controls=[
                ft.Row(spacing=10, controls=[tiles[0], tiles[1]]),
                ft.Row(spacing=10, controls=[tiles[2], tiles[3]]),
            ],
        )

    return ft.Container(
        content=ft.Column(
            spacing=8,
            controls=[
                ft.Row(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.GRID_VIEW_ROUNDED, size=14, color=ft.Colors.PRIMARY),
                                ft.Text("QUICK LAUNCH HUB", size=11, weight=ft.FontWeight.W_800, color=ft.Colors.GREY_500),
                            ],
                            spacing=6,
                            tight=True,
                        ),
                    ],
                ),
                grid_content,
            ],
        ),
    )
