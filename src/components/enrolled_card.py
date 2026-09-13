import flet as ft
import asyncio
from src.download_manager import download_course, is_course_downloaded, DownloadProgress
from src.components.course_card_theme import (
    get_card_palette,
    get_course_module_meta,
    build_course_avatar,
)


def get_enrolled_card(
    page: ft.Page,
    course_id: str,
    course_title: str,
    course_category: str,
    course_author: str,
    image_url: str | None = None,
    progress: float = 0.0,
    rating: float = 0.0,
    description: str | None = None,
    modules: list | int | None = None,
    course_dict: dict | None = None,
):
    c_dict = course_dict or {}
    percentage = max(0, min(int(round(progress or 0.0)), 100))

    # Category name resolution
    if course_category:
        category_name = course_category
    elif isinstance(c_dict.get("category"), dict):
        category_name = c_dict.get("category", {}).get("name") or "Student"
    elif isinstance(c_dict.get("category"), str):
        category_name = c_dict.get("category")
    else:
        category_name = "Student"

    # Description resolution
    desc = description or c_dict.get("description")
    if not desc:
        objs = c_dict.get("objectives")
        if isinstance(objs, list) and objs:
            desc = objs[0]
    if not desc or not isinstance(desc, str) or not desc.strip():
        desc = f"Master core {category_name.lower()} skills with guided interactive modules."
    else:
        desc = desc.strip()

    # Image URL
    img_url = image_url or c_dict.get("image_url")

    # Author
    auth_name = course_author or "Nu-age Instructor"

    # Modules and estimated time calculation
    modules_data = modules if modules is not None else c_dict.get("modules")
    total_modules, completed_modules, time_str = get_course_module_meta(
        modules_data, seed_key=course_id or course_title, progress=progress
    )

    # Theme mode & Palette selection
    is_dark = getattr(page, "theme_mode", None) == ft.ThemeMode.DARK if page else False
    palette = get_card_palette(category_name, course_title, is_dark=is_dark)

    # ── Download Manager & Offline Support ────────────────────────────────────
    is_web = getattr(page, "web", False)
    already_downloaded = False if is_web else is_course_downloaded(page, course_id)

    def _get_downloaded_size_label() -> str:
        if is_web:
            return ""
        from src.local_db import get_local_db
        db = get_local_db(page)
        row = db.execute(
            "SELECT total_size_bytes FROM downloaded_courses WHERE id = ?", (course_id,)
        ).fetchone()
        if not row or not row[0]:
            return "Saved for offline"
        size_bytes = row[0]
        mb = size_bytes / (1024 * 1024)
        size_str = f"{mb:.1f} MB" if mb >= 1 else f"{size_bytes // 1024} KB"
        return f"Saved · {size_str}"

    def _build_idle_visual():
        return ft.Row(
            spacing=3,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.ARROW_CIRCLE_DOWN_ROUNDED, size=14, color=palette["accent"]),
                ft.Text("Save", size=10, weight=ft.FontWeight.W_700, color=palette["accent"]),
            ],
        )

    def _build_progress_visual(percent: int | None):
        if percent is not None:
            return ft.Row(
                spacing=4,
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.ProgressRing(
                        value=percent / 100.0,
                        width=11,
                        height=11,
                        stroke_width=2.0,
                        color=palette["accent"],
                        bgcolor=ft.Colors.with_opacity(0.2, palette["accent"]),
                    ),
                    ft.Text(f"{percent}%", size=9.5, weight=ft.FontWeight.W_800, color=palette["accent"]),
                ],
            )
        else:
            return ft.Row(
                spacing=4,
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.ProgressRing(
                        width=11,
                        height=11,
                        stroke_width=2.0,
                        color=palette["accent"],
                    ),
                    ft.Text("···", size=9.5, weight=ft.FontWeight.W_800, color=palette["accent"]),
                ],
            )

    def _build_downloaded_visual():
        return ft.Row(
            spacing=3,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=13, color=ft.Colors.GREEN_600),
                ft.Text("Saved", size=10, weight=ft.FontWeight.W_700, color=ft.Colors.GREEN_600),
            ],
        )

    def _build_error_visual():
        return ft.Row(
            spacing=3,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.REFRESH_ROUNDED, size=13, color=ft.Colors.RED_500),
                ft.Text("Retry", size=10, weight=ft.FontWeight.W_700, color=ft.Colors.RED_500),
            ],
        )

    download_visual = ft.Container(
        content=_build_downloaded_visual() if already_downloaded else _build_idle_visual(),
        alignment=ft.Alignment.CENTER,
    )

    download_icon_button = ft.Container(
        padding=ft.Padding.symmetric(horizontal=8, vertical=5),
        border_radius=ft.BorderRadius.all(12),
        bgcolor=ft.Colors.with_opacity(0.08, palette["accent"]),
        border=ft.Border.all(
            1,
            ft.Colors.with_opacity(0.25, ft.Colors.GREEN_600 if already_downloaded else palette["accent"]),
        ),
        alignment=ft.Alignment.CENTER,
        ink=True,
        visible=not is_web,
        tooltip=_get_downloaded_size_label() if already_downloaded else "Save for offline learning",
        content=download_visual,
    )

    STATUS_LABELS = {
        "pending": "Starting...",
        "fetching": "Fetching course...",
        "downloading_assets": "Downloading files...",
        "writing_db": "Saving...",
    }

    async def poll_progress_ring(download_progress: DownloadProgress):
        while download_progress.status not in ("done", "error"):
            if download_progress.total_assets > 0:
                percent = int(
                    (download_progress.completed_assets / download_progress.total_assets) * 100
                )
                download_visual.content = _build_progress_visual(percent)
            else:
                download_visual.content = _build_progress_visual(None)

            download_icon_button.tooltip = STATUS_LABELS.get(download_progress.status, "Downloading...")

            if download_icon_button.page:
                page.update()

            await asyncio.sleep(0.15)

    async def handle_download_click(e):
        if already_downloaded:
            return

        download_icon_button.disabled = True
        download_icon_button.border = ft.Border.all(1, ft.Colors.with_opacity(0.5, palette["accent"]))
        download_visual.content = _build_progress_visual(0)
        page.update()

        result = DownloadProgress()
        poll_task = page.run_task(poll_progress_ring, result)

        success = await download_course(page, course_id, result)

        poll_task.cancel()
        download_icon_button.disabled = False

        if success:
            download_visual.content = _build_downloaded_visual()
            download_icon_button.border = ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.GREEN_600))
            download_icon_button.tooltip = _get_downloaded_size_label()
            download_icon_button.on_click = None
            if result.error_message:
                page.show_dialog(ft.SnackBar(ft.Text(result.error_message)))
        else:
            download_visual.content = _build_error_visual()
            download_icon_button.border = ft.Border.all(1, ft.Colors.with_opacity(0.4, ft.Colors.RED_500))
            download_icon_button.tooltip = "Download failed — tap to retry"
            page.show_dialog(ft.SnackBar(ft.Text(result.error_message or "Download failed.")))

        page.update()

    download_icon_button.on_click = lambda e: page.run_task(handle_download_click, e)

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
                        f"{percentage}%",
                        size=10.5,
                        weight=ft.FontWeight.W_700,
                        color=ft.Colors.ON_SURFACE,
                    ),
                ],
            ),
            ft.ProgressBar(
                value=percentage / 100.0,
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
    action_label = "Review" if percentage >= 100 else "Continue"
    continue_btn = ft.Container(
        padding=ft.Padding.symmetric(horizontal=16, vertical=7),
        bgcolor=palette["btn_bg"],
        border_radius=ft.BorderRadius.all(20),
        ink=True,
        on_click=lambda e: page.go(f"/courses/{course_id}/view"),
        content=ft.Text(
            action_label,
            size=11.5,
            weight=ft.FontWeight.W_700,
            color=palette["btn_text"],
        ),
    )

    # Footer actions row
    actions_row = ft.Row(
        spacing=8,
        tight=True,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            download_icon_button,
            continue_btn,
        ],
    )

    # ── Bottom White / Surface Footer ─────────────────────────────────────────
    # Left shows "Modules: 12/16" matching the user's reference image
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
                    f"Modules: {completed_modules}/{total_modules}",
                    size=12,
                    weight=ft.FontWeight.W_700,
                    color=ft.Colors.ON_SURFACE,
                ),
                actions_row,
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
        tooltip=f"Tap to continue {course_title}",
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