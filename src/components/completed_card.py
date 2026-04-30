import flet as ft

def get_completed_card(course_name,course_id, on_review_click, on_stats_click):

    # ── Palette (uses your PRIMARY throughout) ────────────────────────────────
    CARD_BG      = ft.Colors.WHITE
    BORDER_COLOR = ft.Colors.with_opacity(0.09, ft.Colors.BLACK)
    BADGE_BG     = ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY)
    TITLE_COLOR  = "#1A1D23"

    # ── Hover animation ───────────────────────────────────────────────────────
    def on_hover(e):
        is_hovering = e.data == "true"
        card.scale  = 1.03 if is_hovering else 1.0
        card.shadow = ft.BoxShadow(
            blur_radius   = 22 if is_hovering else 8,
            spread_radius = 0,
            color         = ft.Colors.with_opacity(
                0.14 if is_hovering else 0.07, ft.Colors.BLACK
            ),
            offset=ft.Offset(0, 8 if is_hovering else 2),
        )
        card.update()

    # ── Accent strip (top edge, primary colour) ───────────────────────────────
    accent_strip = ft.Container(
        height=4,
        bgcolor=ft.Colors.PRIMARY,
        border_radius=ft.BorderRadius(
            top_left=14, top_right=14, bottom_left=0, bottom_right=0
        ),
    )

    # ── Trophy icon badge (Udemy / Coursera convention for completed) ─────────
    icon_badge = ft.Container(
        width=42,
        height=42,
        border_radius=21,
        bgcolor=BADGE_BG,
        content=ft.Icon(
            ft.Icons.EMOJI_EVENTS_ROUNDED,   # trophy — universal "completed" signal
            size=22,
            color=ft.Colors.PRIMARY,
        ),
        alignment=ft.Alignment(0, 0),
    )

    # ── Completion badge (CHECK_CIRCLE — LMS industry standard) ───────────────
    completion_badge = ft.Container(
        padding=ft.padding.symmetric(horizontal=9, vertical=4),
        bgcolor=BADGE_BG,
        border_radius=20,
        content=ft.Row(
            spacing=5,
            tight=True,
            controls=[
                ft.Icon(
                    ft.Icons.CHECK_CIRCLE_ROUNDED,
                    size=11,
                    color=ft.Colors.PRIMARY,
                ),
                ft.Text(
                    "Completed",
                    size=10,
                    weight=ft.FontWeight.W_700,
                    color=ft.Colors.PRIMARY,
                ),
            ],
        ),
    )

    # ── Header row ────────────────────────────────────────────────────────────
    header_row = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[icon_badge, completion_badge],
    )

    # ── Course title ──────────────────────────────────────────────────────────
    title = ft.Text(
        course_name,
        size=13,
        weight=ft.FontWeight.W_700,
        max_lines=2,
        overflow=ft.TextOverflow.ELLIPSIS,
        color=TITLE_COLOR,
    )

    # ── Full progress bar (100 %) ─────────────────────────────────────────────
    progress_bar = ft.ProgressBar(
        value=1.0,
        color=ft.Colors.PRIMARY,
        bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.BLACK),
        height=5,
        border_radius=3,
    )

    # ── CTA 1: Review Course — filled primary ─────────────────────────────────
    review_btn = ft.Container(
        height=34,
        border_radius=8,
        bgcolor=ft.Colors.PRIMARY,
        alignment=ft.Alignment(0, 0),
        on_click=lambda e: on_review_click(course_id),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=6,
            controls=[
                ft.Icon(ft.Icons.PLAY_CIRCLE_OUTLINE_ROUNDED, size=15, color=ft.Colors.WHITE),
                ft.Text(
                    "Review Course",
                    size=12,
                    weight=ft.FontWeight.W_600,
                    color=ft.Colors.WHITE,
                ),
            ],
        ),
    )

    # ── CTA 2: My Stats — ghost outlined ─────────────────────────────────────
    stats_btn = ft.Container(
        height=34,
        border_radius=8,
        border=ft.border.all(1.5, ft.Colors.PRIMARY),
        alignment=ft.Alignment(0, 0),
        on_click=lambda e: on_stats_click(course_id),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=6,
            controls=[
                ft.Icon(ft.Icons.INSIGHTS_ROUNDED, size=15, color=ft.Colors.PRIMARY),
                ft.Text(
                    "My Stats",
                    size=12,
                    weight=ft.FontWeight.W_600,
                    color=ft.Colors.PRIMARY,
                ),
            ],
        ),
    )

    # ── Footer ────────────────────────────────────────────────────────────────
    footer = ft.Column(
        spacing=8,
        controls=[progress_bar, review_btn, stats_btn],
    )

    # ── Card body ─────────────────────────────────────────────────────────────
    card_body = ft.Container(
        padding=ft.padding.only(left=14, right=14, top=12, bottom=14),
        content=ft.Column(
            spacing=10,
            controls=[
                header_row,
                title,
                ft.Container(expand=True),
                footer,
            ],
        ),
    )

    # ── Outer card ────────────────────────────────────────────────────────────
    card = ft.Container(
        width=200,
        height=230,
        bgcolor=CARD_BG,
        border_radius=14,
        scale=1.0,
        animate_scale=ft.Animation(300, ft.AnimationCurve.EASE_OUT),
        border=ft.border.all(1, BORDER_COLOR),
        shadow=ft.BoxShadow(
            blur_radius=8,
            spread_radius=0,
            color=ft.Colors.with_opacity(0.07, ft.Colors.BLACK),
            offset=ft.Offset(0, 2),
        ),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        on_hover=on_hover,
        content=ft.Column(
            spacing=0,
            controls=[accent_strip, card_body],
        ),
    )

    return card