import flet as ft


def get_playlist_card(
    playlist_title: str,
    playlist_author: str,
    image_url: str | None = None,
    created_at: str | None = None,
    on_enroll_click=None
):
    # ── stacked background ────────────────────────────────────────────────────
    # Creates the "multiple courses" visual effect
    bg_card_2 = ft.Container(
        height=130,
        bgcolor=ft.Colors.with_opacity(0.3, ft.Colors.PRIMARY),
        border_radius=ft.BorderRadius.only(top_left=16, top_right=16),
        margin=ft.Margin.only(left=20, right=20, top=0),
    )
    
    bg_card_1 = ft.Container(
        height=135,
        bgcolor=ft.Colors.with_opacity(0.6, ft.Colors.PRIMARY),
        border_radius=ft.BorderRadius.only(top_left=14, top_right=14),
        margin=ft.Margin.only(left=10, right=10, top=5),
    )

    # ── cover ─────────────────────────────────────────────────────────────────
    if image_url:
        cover = ft.Container(
            height=140,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            border_radius=ft.BorderRadius.only(top_left=12, top_right=12),
            content=ft.Stack([
                ft.Image(
                    src=image_url,
                    fit=ft.BoxFit.COVER,
                    width=float("inf"),
                    height=float("inf"),
                    placeholder_src="/placeholder.png",
                    placeholder_fit=ft.BoxFit.COVER,
                ),
                # Gradient overlay for text readability
                ft.Container(
                    gradient=ft.LinearGradient(
                        begin=ft.Alignment.TOP_CENTER,
                        end=ft.Alignment.BOTTOM_CENTER,
                        colors=[ft.Colors.TRANSPARENT, ft.Colors.BLACK54]
                    ),
                    expand=True,
                ),
                # Playlist icon overlay
                ft.Container(
                    alignment=ft.Alignment.BOTTOM_RIGHT,
                    padding=8,
                    content=ft.Icon(ft.Icons.PLAYLIST_PLAY_ROUNDED, color=ft.Colors.WHITE, size=32)
                )
            ]),
        )
    else:
        cover = ft.Container(
            height=140,
            bgcolor=ft.Colors.INDIGO_300,
            gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
                colors=[ft.Colors.PRIMARY, ft.Colors.SECONDARY]
            ),
            border_radius=ft.BorderRadius.only(top_left=12, top_right=12),
            alignment=ft.Alignment.CENTER,
            content=ft.Stack([
                ft.Container(
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.FORMAT_LIST_BULLETED_ROUNDED, size=48, color=ft.Colors.ON_PRIMARY)
                ),
                ft.Container(
                    alignment=ft.Alignment.BOTTOM_RIGHT,
                    padding=8,
                    content=ft.Icon(ft.Icons.PLAYLIST_PLAY_ROUNDED, color=ft.Colors.WHITE, size=32)
                )
            ]),
        )

    # ── category pill ─────────────────────────────────────────────────────────
    category_pill = ft.Container(
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY),
        border_radius=10,
        content=ft.Text(
            "Learning Path",
            size=10,
            weight=ft.FontWeight.W_600,
            color=ft.Colors.PRIMARY,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        ),
    )

    # ── meta row ──────────────────────────────────────────────────────────────
    def _meta(icon, value: str):
        return ft.Row(
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(icon, size=12, color=ft.Colors.GREY_400),
                ft.Text(value, size=11, color=ft.Colors.GREY_500,
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                        expand=True),
            ],
        )

    # ── action button ─────────────────────────────────────────────────────────
    action_btn = ft.ElevatedButton(
        content=ft.Text("View Playlist", size=13,
                        color=ft.Colors.ON_PRIMARY, weight=ft.FontWeight.W_600),
        bgcolor=ft.Colors.PRIMARY,
        expand=True,
        height=40,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=8),
            elevation=0,
        ),
        on_click=on_enroll_click,
    )

    # ── main card content ─────────────────────────────────────────────────────
    main_card = ft.Container(
        bgcolor=ft.Colors.SURFACE,
        border_radius=12,
        margin=ft.Margin.only(top=10),
        shadow=ft.BoxShadow(
            blur_radius=8,
            color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
            offset=ft.Offset(0, 3),
        ),
        ink=True,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=ft.Column(
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[
                cover,
                ft.Container(
                    padding=ft.Padding.only(left=12, right=12, top=10, bottom=12),
                    content=ft.Column(
                        spacing=8,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    category_pill,
                                    ft.Text(
                                        created_at or "",
                                        size=10,
                                        color=ft.Colors.GREY_400,
                                    ),
                                ],
                            ),
                            ft.Text(
                                playlist_title,
                                size=15,
                                weight=ft.FontWeight.W_700,
                                color=ft.Colors.ON_SURFACE,
                                max_lines=2,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            _meta(ft.Icons.BUSINESS_ROUNDED, playlist_author),
                            ft.Divider(height=1, color=ft.Colors.GREY_100),
                            ft.Row(controls=[action_btn]),
                        ],
                    ),
                ),
            ],
        ),
    )

    def handle_hover(e):
        e.control.scale = 1.05 if e.data == "true" else 1.0
        e.control.update()

    # Return stack with offset cards behind
    return ft.Container(
        offset=ft.Offset(0, 0.1),
        animate_offset=ft.Animation(400, ft.AnimationCurve.DECELERATE),
        scale=1.0,
        animate_scale=ft.Animation(300, ft.AnimationCurve.DECELERATE),
        on_hover=handle_hover,
        tooltip="Tap to view this playlist",
        opacity=0,
        animate_opacity=300,
        content=ft.Stack([
            bg_card_2,
            bg_card_1,
            main_card
        ])
    )
