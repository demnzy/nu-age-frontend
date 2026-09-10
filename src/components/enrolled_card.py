import flet as ft
import asyncio
import random
from src.download_manager import download_course, is_course_downloaded, DownloadProgress


def get_enrolled_card(
    page: ft.Page,
    course_id: str,
    course_title: str,
    course_category: str,
    course_author: str,
    image_url: str | None = None,
    progress: float = 0.0,
    rating: float = 0.0,
):
    percentage = int(progress)

    # ── use provided rating or fallback ────────────────────────
    # The rating is now passed from the API response
    display_rating = round(rating,1)if rating > 0 else 5.0

    # ── progress colour: green when done, primary otherwise ──────────────────
    progress_color = ft.Colors.GREEN_500 if percentage >= 100 else ft.Colors.RED if (percentage >= 0 and percentage <= 30) else ft.Colors.AMBER_600 if (percentage > 30 and percentage <= 70) else ft.Colors.PRIMARY if percentage > 70 else ft.Colors.GREY_400

    # ── download state ────────────────────────────────────────────────────
    # NOTE: is_course_downloaded() reads directly from downloaded_courses in
    # SQLite — not a cached/in-memory flag — so this reflects real DB state
    # at the moment the card is built. Correct even if a download for this
    # exact course finished from a different screen (e.g. offline_courses_view)
    # since the last time this card was rendered.
    is_web = getattr(page, "web", False)
    already_downloaded = False if is_web else is_course_downloaded(page, course_id)

    def _get_downloaded_size_label() -> str:
        # Pulls the real total_size_bytes column written by download_manager
        # at the end of a successful download — surfaced here so the DB
        # isn't just a yes/no flag, the actual stored size is visible too.
        if is_web:
            return ""
        from src.local_db import get_local_db
        db = get_local_db(page)
        row = db.execute(
            "SELECT total_size_bytes FROM downloaded_courses WHERE id = ?", (course_id,)
        ).fetchone()
        if not row or not row[0]:
            return "Downloaded for offline"
        size_bytes = row[0]
        mb = size_bytes / (1024 * 1024)
        size_str = f"{mb:.1f} MB" if mb >= 1 else f"{size_bytes // 1024} KB"
        return f"Downloaded · {size_str}"

    # A container-based button rather than IconButton: IconButton requires
    # either `icon` or `content` to be set at all times (never both empty),
    # which is exactly what bit us before — clearing `icon` to show a
    # progress ring left a one-frame window with neither set. Using a
    # Container with a single `content` slot we just keep swapping sidesteps
    # that constraint entirely, and it also lets us go bigger / non-circular.
    def _download_visual_icon(icon, color=ft.Colors.WHITE):
        return ft.Icon(icon, color=color, size=20)

    def _download_visual_text(label: str):
        return ft.Text(label, size=12, weight=ft.FontWeight.W_800, color=ft.Colors.WHITE)

    download_visual = ft.Container(
        content=_download_visual_icon(
            ft.Icons.DOWNLOAD_DONE_ROUNDED if already_downloaded else ft.Icons.DOWNLOAD_ROUNDED
        ),
        alignment=ft.Alignment.CENTER,
    )

    # Bigger, rounded-square, primary-coloured chip instead of the old
    # semi-transparent black circle — reads as a real action affordance
    # against the cover art rather than a faint utility icon.
    download_icon_button = ft.Container(
        width=38,
        height=38,
        border_radius=10,
        bgcolor=ft.Colors.PRIMARY,
        alignment=ft.Alignment.CENTER,
        ink=True,
        visible=not is_web,
        shadow=ft.BoxShadow(
            blur_radius=6,
            spread_radius=0.5,
            color=ft.Colors.with_opacity(0.35, ft.Colors.BLACK),
            offset=ft.Offset(0, 2),
        ),
        tooltip=_get_downloaded_size_label() if already_downloaded else "Download for offline",
        content=download_visual,
    )

    STATUS_LABELS = {
        "pending": "Starting...",
        "fetching": "Fetching course...",
        "downloading_assets": "Downloading files...",
        "writing_db": "Saving...",
    }

    async def poll_progress_ring(download_progress: DownloadProgress):
        """
        Runs alongside download_course() as a separate background task,
        polling the SAME DownloadProgress object download_course() is
        mutating in place — this is why DownloadProgress exists as a
        mutable holder rather than a return value: it lets a caller watch
        it update live instead of only seeing the final result.

        Renders a real determinate ring once asset downloads start
        (total_assets becomes known), and an indeterminate ring before
        that (during the initial course-tree fetch, when there's nothing
        to compute a percentage of yet).
        """
        while download_progress.status not in ("done", "error"):
            if download_progress.total_assets > 0:
                percent = int(
                    (download_progress.completed_assets / download_progress.total_assets) * 100
                )
                download_visual.content = _download_visual_text(f"{percent}%")
            else:
                # total not known yet (still fetching course tree) — nothing
                # to compute a percentage of yet, so show a placeholder
                # rather than a spinner.
                download_visual.content = _download_visual_text("···")

            download_icon_button.tooltip = STATUS_LABELS.get(download_progress.status, "Downloading...")

            if download_icon_button.page:
                page.update()

            await asyncio.sleep(0.15)

    async def handle_download_click(e):
        # This button's own on_click fires before any parent Container's,
        # so this never also triggers the card's own "open course"
        # navigation — no explicit stop-propagation needed.
        if already_downloaded:
            return  # already downloaded, nothing to do — icon is inert

        download_icon_button.disabled = True
        download_visual.content = _download_visual_text("0%")
        page.update()

        result = DownloadProgress()
        poll_task = page.run_task(poll_progress_ring, result)

        success = await download_course(page, course_id, result)

        poll_task.cancel()  # stop polling the instant the real result is in,
                             # rather than waiting for its next 0.15s tick

        download_icon_button.disabled = False

        if success:
            download_visual.content = _download_visual_icon(ft.Icons.DOWNLOAD_DONE_ROUNDED)
            download_icon_button.tooltip = _get_downloaded_size_label()
            download_icon_button.on_click = None  # nothing to do once downloaded
            if result.error_message:
                page.open(ft.SnackBar(ft.Text(result.error_message)))
        else:
            download_visual.content = _download_visual_icon(ft.Icons.ERROR_OUTLINE_ROUNDED)
            download_icon_button.tooltip = "Download failed — tap to retry"
            page.open(ft.SnackBar(ft.Text(result.error_message or "Download failed.")))

        page.update()

    download_icon_button.on_click = lambda e: page.run_task(handle_download_click, e)

    # ── cover ─────────────────────────────────────────────────────────────────
    if image_url:
        cover_image = ft.Container(
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
        cover_image = ft.Container(
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
                            color=ft.Colors.ON_PRIMARY),
        )

    # Download icon overlaid top-right on the cover — common placement for
    # a secondary action that shouldn't compete visually with the title,
    # per course-card patterns (rating/status badges live inline near
    # metadata, while save/download affordances sit as a small icon
    # chip on the cover itself).
    cover = ft.Stack(
        controls=[
            cover_image,
            ft.Container(
                top=6,
                right=6,
                visible=not is_web,
                content=download_icon_button,
            ),
        ],
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

    # ── rating chip ───────────────────────────────────────────────────────────
    rating_chip = ft.Row(
        spacing=2,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Icon(ft.Icons.STAR_ROUNDED, size=13, color=ft.Colors.AMBER_600),
            ft.Text(f"{display_rating}", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
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
                            color=ft.Colors.ON_SURFACE, weight=ft.FontWeight.W_500),
                    ft.Text(
                        "Completed ✓" if percentage >= 100 else f"{percentage}%",
                        size=11,
                        weight=ft.FontWeight.W_700,
                        color=progress_color if percentage >= 100 else ft.Colors.ON_SURFACE,
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

    def handle_hover(e):
        e.control.scale = 1.05 if e.data == "true" else 1.0
        e.control.shadow = ft.BoxShadow(
            blur_radius=16 if e.data == "true" else 8,
            color=ft.Colors.with_opacity(0.12 if e.data == "true" else 0.08, ft.Colors.ON_SURFACE),
            offset=ft.Offset(0, 8) if e.data == "true" else ft.Offset(0, 3),
        )
        e.control.update()

    # ── card ──────────────────────────────────────────────────────────────────
    return ft.Container(
        # preserve original animation contract
        offset=ft.Offset(0, 0.1),
        animate_offset=ft.Animation(400, ft.AnimationCurve.DECELERATE),
        scale=1.0,
        animate_scale=ft.Animation(300, ft.AnimationCurve.DECELERATE),
        on_hover=handle_hover,
        opacity=0,
        animate_opacity=300,
        bgcolor=ft.Colors.SURFACE,
        border_radius=12,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        shadow=ft.BoxShadow(
            blur_radius=8,
            color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
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
                    padding=ft.Padding.only(left=12, right=12, top=10, bottom=12),
                    content=ft.Column(
                        spacing=8,
                        controls=[
                            # Category pill + rating, same row
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Container(
                                        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                        bgcolor=ft.Colors.SURFACE,
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
                                    rating_chip,
                                ],
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