import flet as ft


def get_enrolled_card(
    course_title: str,
    course_category: str,
    course_author: str,
    image_url: str | None = None,
    progress: float = 0.0,
):
    percentage = int(progress)

    # ── progress colour: green when done, primary otherwise ──────────────────
    progress_color = ft.Colors.GREEN_500 if percentage >= 100 else ft.Colors.RED if (percentage >= 0 and percentage <= 30) else ft.Colors.AMBER_600 if (percentage > 30 and percentage <= 70) else ft.Colors.PRIMARY if percentage > 70 else ft.Colors.GREY_400

    # ── cover ─────────────────────────────────────────────────────────────────
    if image_url:
        cover = ft.Container(
            height=120,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            border_radius=ft.BorderRadius.only(top_left=12, top_right=12),
            content=ft.Image(
                src=image_url,
                fit=ft.BoxFit.COVER,
                width=float("inf"),
                placeholder_src="/placeholder.png",
                placeholder_fit=ft.BoxFit.COVER,
                placeholder_fade_out_animation=ft.Animation(900, ft.AnimationCurve.EASE_OUT),
                fade_in_animation=ft.Animation(700, ft.AnimationCurve.EASE_IN_OUT),
            ),
        )
    else:
        cover = ft.Container(
            height=140,
            bgcolor=ft.Colors.INDIGO_300,
            gradient=ft.LinearGradient(
                        begin=ft.Alignment.TOP_LEFT,
                        end=ft.Alignment.BOTTOM_RIGHT,
                        colors=[ft.Colors.PURPLE_200, ft.Colors.INDIGO_200]
                    ),
            border_radius=ft.BorderRadius.only(top_left=12, top_right=12),
            alignment=ft.Alignment.CENTER,
            content=ft.Icon(ft.Icons.MENU_BOOK_ROUNDED, size=44,
                            color=ft.Colors.WHITE),
        )

    # ── meta row helper ───────────────────────────────────────────────────────
    def _meta(icon, value: str):
        return ft.Row(
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(icon, size=12, color=ft.Colors.GREY_400),
                ft.Text(value, size=11, color=ft.Colors.GREY_500,
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
            ],
        )

    # ── progress section ──────────────────────────────────────────────────────
    progress_section = ft.Column(
        spacing=4,
        controls=[
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Text("Progress", size=10,
                            color=ft.Colors.BLACK, weight=ft.FontWeight.W_500),
                    ft.Text(
                        "Completed ✓" if percentage >= 100 else f"{percentage}%",
                        size=11,
                        weight=ft.FontWeight.W_700,
                        color=progress_color if percentage >= 100 else ft.Colors.BLACK,
                    ),
                ],
            ),
            ft.ProgressBar(
                value=progress / 100,
                color=progress_color,
                bgcolor=ft.Colors.GREY_100,
                height=6,
                border_radius=4,
                expand=True,
            ),
        ],
    )

    # ── card ──────────────────────────────────────────────────────────────────
    return ft.Container(
        # preserve original animation contract
        offset=ft.Offset(0, 0.1),
        animate_offset=ft.Animation(400, ft.AnimationCurve.DECELERATE),
        opacity=0,
        animate_opacity=300,
        bgcolor=ft.Colors.SURFACE,
        border_radius=12,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        shadow=ft.BoxShadow(
            blur_radius=8,
            color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
            offset=ft.Offset(0, 3),
        ),
        ink=True,
        content=ft.Column(
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[
                # Cover
                cover,

                # Body
                ft.Container(
                    padding=ft.padding.only(left=12, right=12, top=10, bottom=12),
                    content=ft.Column(
                        spacing=8,
                        controls=[
                            # Category pill
                            ft.Container(
                            padding=ft.padding.symmetric(horizontal=8, vertical=3),
                            bgcolor=ft.Colors.GREY_100,
                            border_radius=10,
                            content=ft.Text(
                                course_category or "General",
                                size=10,
                                weight=ft.FontWeight.W_600,
                                color=ft.Colors.PRIMARY,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                            ),

                            # Title
                            ft.Text(
                                course_title,
                                size=13,
                                weight=ft.FontWeight.W_700,
                                color=ft.Colors.ON_SURFACE,
                                max_lines=2,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),

                            # Author
                            _meta(ft.Icons.PERSON_OUTLINE_ROUNDED, course_author),

                            ft.Divider(height=1, color=ft.Colors.GREY_100),

                            # Progress
                            progress_section,
                        ],
                    ),
                ),
            ],
        ),
    )