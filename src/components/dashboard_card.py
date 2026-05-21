import flet as ft


def get_continue_learning_card(course_name, progress, course_id, page: ft.Page):
    """
    LMS-standard 'Continue Learning' course card.

    Visual design:
    - Clean white surface with a subtle top accent strip coloured by progress
    - Pill-shaped progress badge (colour-coded)
    - Smooth EASE_OUT scale + shadow lift on hover
    - Book icon centred in a tinted circle
    - Consistent 200 × 160 footprint
    """

    # ── Colour helpers ──────────────────────────────────────────────────────
    def _progress_color(p: float) -> str:
        if p >= 100:
            return ft.Colors.GREEN_600
        if p >= 70:
            return ft.Colors.PRIMARY
        if p > 30:
            return ft.Colors.AMBER_600
        return ft.Colors.RED_500

    bar_color   = _progress_color(progress)
    is_complete = progress >= 100

    # ── Accent strip (top of card) ───────────────────────────────────────────
    accent_strip = ft.Container(
        height=4,
        border_radius=ft.BorderRadius(top_left=12, top_right=12,
                                      bottom_left=0, bottom_right=0),
        bgcolor=bar_color,
    )

    # ── Icon badge ───────────────────────────────────────────────────────────
    icon_badge = ft.Container(
        width=42,
        height=42,
        border_radius=21,
        bgcolor=ft.Colors.with_opacity(0.10, bar_color),
        content=ft.Icon(
            ft.Icons.MENU_BOOK_ROUNDED,
            size=22,
            color=bar_color,
        ),
        alignment=ft.Alignment.CENTER,
    )

    # ── Progress pill ────────────────────────────────────────────────────────
    label = "Complete" if is_complete else f"{int(progress)}%"
    progress_pill = ft.Container(
        padding=ft.Padding(left=8, right=8, top=3, bottom=3),
        border_radius=20,
        bgcolor=ft.Colors.with_opacity(0.12, bar_color),
        content=ft.Text(
            label,
            size=10,
            weight=ft.FontWeight.W_700,
            color=bar_color,
        ),
    )

    # ── Progress bar ─────────────────────────────────────────────────────────
    progress_bar = ft.ProgressBar(
        value=min(progress / 100, 1.0),
        color=bar_color,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        height=5,
        border_radius=3,
    )

    # ── Header row: icon  +  pill ─────────────────────────────────────────
    header_row = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[icon_badge, progress_pill],
    )

    # ── Course name ───────────────────────────────────────────────────────────
    course_label = ft.Text(
        course_name,
        size=13,
        weight=ft.FontWeight.W_600,
        max_lines=2,
        overflow=ft.TextOverflow.ELLIPSIS,
        color=ft.Colors.ON_SURFACE,
    )

    # ── Progress section ─────────────────────────────────────────────────────
    progress_section = ft.Column(
        spacing=5,
        controls=[
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Text(
                        "Progress",
                        size=10,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        weight=ft.FontWeight.W_500,
                    ),
                    ft.Text(
                        f"{min(int(progress), 100)}%",
                        size=10,
                        weight=ft.FontWeight.W_700,
                        color=ft.Colors.ON_SURFACE,
                    ),
                ],
            ),
            progress_bar,
        ],
    )

    # ── Card body ─────────────────────────────────────────────────────────────
    card_body = ft.Container(
        padding=ft.Padding(left=14, right=14, top=12, bottom=14),
        content=ft.Column(
            spacing=10,
            controls=[
                header_row,
                course_label,
                ft.Container(expand=True),   # pushes progress to bottom
                progress_section,
            ],
        ),
    )

    # ── Outer card ───────────────────────────────────────────────────────────
    card = ft.Container(
        width=200,
        height=160,
        bgcolor=ft.Colors.ON_PRIMARY,
        border_radius=12,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        scale=1,
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=6,
            color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
            offset=ft.Offset(0, 2),
        ),
        animate_scale=ft.Animation(
            duration=350,
            curve=ft.AnimationCurve.EASE_OUT,
        ),
        on_click=lambda _: page.go(
            f"/courses/{course_id}/{course_name.replace(' ', '-').lower()}"
        ),
        content=ft.Column(
            spacing=0,
            controls=[
                accent_strip,
                card_body,
            ],
        ),
    )

    # ── Hover: lift scale + deepen shadow ────────────────────────────────────
    def _on_hover(e: ft.HoverEvent):
        is_hovering = e.data == "true"
        card.scale = 1.04 if is_hovering else 1
        card.shadow = ft.BoxShadow(
            spread_radius=0,
            blur_radius=18 if is_hovering else 6,
            color=ft.Colors.with_opacity(
                0.16 if is_hovering else 0.08, ft.Colors.BLACK
            ),
            offset=ft.Offset(0, 6 if is_hovering else 2),
        )
        card.update()

    card.on_hover = _on_hover

    return card