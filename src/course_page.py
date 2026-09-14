import random

import flet_charts as fch 
import flet as ft
from flet_video import Video, VideoMedia
import asyncio
from src.requests.Courses import get_course_curriculum, mark_complete, generate_course_certificate, rate_course
from src.utils.file_opener import open_or_download_asset
import re
from src.utils.code_runner import execute_python, execute_sql, run_code_lab_tests, parse_cloze_text


async def course_learner_view(
    page: ft.Page,
    course_id: str,
    # NEW: optional injected data/save layer. Defaults preserve the exact
    # existing online behavior — nothing changes for the online path.
    # The offline entrypoint (src/offline_course_page.py) passes its own
    # SQLite-backed versions of these two instead, and everything below
    # this point (locking, rendering, sidebar, assessments, flashcards,
    # etc) runs completely unmodified either way, since it only ever reads
    # from the `course_data` dict — it has no idea whether that dict came
    # from the network or from disk.
    fetch_course_data=None,
    save_progress=None,
    # Where the back arrow should actually go. Defaults to "/courses" to
    # preserve prior behavior for any caller that doesn't pass this
    # explicitly. main.py's route_change computes the real value from
    # wherever the user actually navigated from (e.g. "/offline" if they
    # opened this course from the downloaded-courses list) — see the
    # back_target comment at that call site for why this matters: a
    # hardcoded "/courses" sent offline users to a protected route that
    # bounced them straight to login, since /courses requires a token.
    back_target: str = "/courses",
):
    token = None

    # =========================================================
    # 0. THEME / LAYOUT CONFIG
    # =========================================================

    UI_ACCENT = ft.Colors.PRIMARY
    SIDEBAR_WIDTH = 340
    DESKTOP_BREAKPOINT = 1024
    ACTION_BUTTON_HEIGHT = 42          # Ergonomic touch target (LMS standard)
    HEADER_RADIUS = 12
    CONTENT_CARD_RADIUS = 12

    def is_desktop_layout():
        w = getattr(page, "width", None)
        if w is None and hasattr(page, "window") and page.window:
            w = getattr(page.window, "width", None)
        return (w or 0) >= DESKTOP_BREAKPOINT

    def get_lesson_type_label(lesson_type: str):
        labels = {
            "video": "VIDEO LESSON",
            "audio": "AUDIO LESSON",
            "text": "READING",
            "document": "DOCUMENT",
            "cards": "FLASHCARDS",
            "assessment": "ASSESSMENT",
            "scenario": "SCENARIO",
            "stepper": "WALKTHROUGH",
            "sequencer": "ORDER MATCH",
            "cloze": "FILL IN BLANKS",
            "code_lab": "CODE LAB",
        }
        return labels.get(lesson_type, "LESSON")

    def get_lesson_type_icon(lesson_type: str):
        icons = {
            "video": ft.Icons.PLAY_CIRCLE_OUTLINE_ROUNDED,
            "audio": ft.Icons.HEADPHONES_ROUNDED,
            "text": ft.Icons.MENU_BOOK_ROUNDED,
            "document": ft.Icons.PICTURE_AS_PDF_ROUNDED,
            "cards": ft.Icons.STYLE_ROUNDED,
            "assessment": ft.Icons.QUIZ_ROUNDED,
            "scenario": ft.Icons.CALL_SPLIT_ROUNDED,
            "stepper": ft.Icons.LINEAR_SCALE_ROUNDED,
            "sequencer": ft.Icons.REORDER_ROUNDED,
            "cloze": ft.Icons.EDIT_NOTE_ROUNDED,
            "code_lab": ft.Icons.CODE_ROUNDED,
        }
        return icons.get(lesson_type, ft.Icons.ARTICLE_ROUNDED)

    # =========================================================
    # 1. API LAYER
    # =========================================================

    async def api_fetch_course_data(c_id: str):
        if fetch_course_data is not None:
            return await fetch_course_data(c_id)
        course_data = await get_course_curriculum(token, course_id)
        return course_data

    async def api_save_progress(course_id: str, lesson_id: str):
        if save_progress is not None:
            return await save_progress(course_id, lesson_id)
        res = await mark_complete(token, course_id, lesson_id)
        return res

    async def api_verify_module_completion(module_id: str):
        return True
    # =========================================================
    # 2. STATE MANAGEMENT
    # =========================================================

    course_data = None
    current_module_idx = 0
    current_lesson_idx = 0
    sidebar_visible = False
    current_assessment_state = {}
    module_expanded_state = {}

    # --- THE LOCK ENGINE ---
    def recalculate_locks():
        if not course_data or "modules" not in course_data:
            return
        previous_lesson_done = True
        for mod in course_data["modules"]:
            mod_is_done = True
            for les in mod.get("lessons", []):
                is_done = les.get("is_done", False)
                les["is_unlocked"] = is_done or previous_lesson_done
                previous_lesson_done = is_done
                if not is_done:
                    mod_is_done = False
            mod["is_done"] = mod_is_done

    # --- THE LAZY LOAD SOCKET ---
    content_socket = ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            [
                ft.ProgressRing(color=UI_ACCENT, stroke_width=3, width=32, height=32),
                ft.Container(height=12),
                ft.Text(
                    "Loading your course...",
                    color=ft.Colors.ON_SURFACE_VARIANT,
                    weight=ft.FontWeight.W_500,
                    size=14,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
    )

    # =========================================================
    # 3. CORE UI CONTAINERS
    # =========================================================

    sidebar_column = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=0)
    lesson_body_scroll = ft.Container(expand=True)
    action_footer_container = ft.Container()
    main_content_area = ft.Container()
    body_host = ft.Container(expand=True)

    def toggle_sidebar(e):
        nonlocal sidebar_visible
        sidebar_visible = not sidebar_visible
        refresh_layout_shell()
        page.update()

    close_sidebar_button = ft.IconButton(
        icon=ft.Icons.CLOSE_ROUNDED,
        icon_size=18,
        icon_color=ft.Colors.ON_SURFACE_VARIANT,
        tooltip="Close Syllabus",
        on_click=toggle_sidebar,
    )

    menu_button = ft.Container(
        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
        border_radius=8,
        ink=True,
        on_click=toggle_sidebar,
        bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
        content=ft.Row(
            [
                ft.Icon(ft.Icons.MENU, size=16, color=ft.Colors.ON_SURFACE),
                ft.Text("Syllabus", size=12, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
            ],
            tight=True,
            spacing=6,
        ),
        tooltip="Toggle Course Syllabus",
    )

    sidebar_course_title = ft.Text(
        "Loading...",
        color=ft.Colors.ON_SURFACE,
        weight=ft.FontWeight.BOLD,
        size=13,
        expand=True,
    )

    # --- Course progress bar (inside sidebar header) ---
    sidebar_progress_bar = ft.ProgressBar(
        value=0,
        color=UI_ACCENT,
        bgcolor=ft.Colors.with_opacity(0.12, UI_ACCENT),
        height=5,
        border_radius=3,
    )
    sidebar_progress_label = ft.Text("0% complete", color=UI_ACCENT, size=11, weight=ft.FontWeight.BOLD)

    top_progress_ring = ft.ProgressRing(width=13, height=13, stroke_width=2.5, color=UI_ACCENT, value=0)
    top_progress_text = ft.Text("0%", size=11, weight=ft.FontWeight.BOLD, color=UI_ACCENT)
    top_progress_pill = ft.Container(
        padding=ft.Padding.symmetric(horizontal=10, vertical=5),
        border_radius=999,
        bgcolor=ft.Colors.with_opacity(0.08, UI_ACCENT),
        content=ft.Row(
            [
                top_progress_ring,
                top_progress_text,
            ],
            tight=True,
            spacing=6,
        ),
    )

    def compute_progress():
        """Returns 0.0 – 1.0 completion ratio."""
        if not course_data or "modules" not in course_data:
            return 0.0
        total = done = 0
        for mod in course_data["modules"]:
            for les in mod.get("lessons", []):
                total += 1
                if les.get("is_done", False):
                    done += 1
        return (done / total) if total else 0.0

    def refresh_progress_header():
        pct = compute_progress()
        sidebar_progress_bar.value = pct
        sidebar_progress_label.value = f"{int(pct * 100)}% complete"
        top_progress_ring.value = pct
        top_progress_text.value = f"{int(pct * 100)}%"

    sidebar_container = ft.Container(
        width=SIDEBAR_WIDTH,
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.only(
            right=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE))
        ),
        shadow=ft.BoxShadow(
            blur_radius=12,
            color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK),
            offset=ft.Offset(2, 0),
        ),
        visible=sidebar_visible,
        content=ft.Column(
            spacing=0,
            expand=True,
            controls=[
                # --- Sidebar header bar ---
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                    border=ft.Border.only(
                        bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE))
                    ),
                    bgcolor=ft.Colors.SURFACE,
                    content=ft.Row(
                        [
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.SCHOOL_SHARP, size=17, color=UI_ACCENT),
                                    ft.Text(
                                        "Course Content",
                                        weight=ft.FontWeight.BOLD,
                                        size=14,
                                        color=ft.Colors.ON_SURFACE,
                                    ),
                                ],
                                spacing=8,
                                tight=True,
                            ),
                            close_sidebar_button,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ),
                # --- Course identity + progress strip ---
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                    border=ft.Border.only(
                        bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE))
                    ),
                    bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(
                                        "COURSE PROGRESS",
                                        size=10,
                                        weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                    ),
                                    sidebar_progress_label,
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Container(height=4),
                            sidebar_progress_bar,
                        ],
                        spacing=2,
                    ),
                ),
                ft.Container(
                    expand=True,
                    bgcolor=ft.Colors.SURFACE,
                    content=sidebar_column,
                ),
            ],
        ),
    )

    # Dynamic App Bar Title & Subtitle
    appbar_course_title = ft.Text(
        "Loading Course...",
        size=15,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.ON_SURFACE,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )
    appbar_title = appbar_course_title  # Alias so existing references work transparently
    appbar_lesson_subtitle = ft.Text(
        "",
        size=11,
        weight=ft.FontWeight.W_500,
        color=ft.Colors.ON_SURFACE_VARIANT,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )

    page_appbar = ft.AppBar(
        leading=ft.IconButton(
            ft.Icons.ARROW_BACK_ROUNDED,
            icon_color=ft.Colors.ON_SURFACE,
            tooltip="Back",
            on_click=lambda _: page.go(back_target),
        ),
        title=ft.Column(
            [
                appbar_course_title,
                appbar_lesson_subtitle,
            ],
            spacing=1,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        center_title=False,
        bgcolor=ft.Colors.SURFACE,
        elevation=0,
        actions=[
            top_progress_pill,
            ft.Container(width=4),
            menu_button,
            ft.Container(width=8),
        ],
    )

    # =========================================================
    # 4. LAYOUT SHELL HELPERS
    # =========================================================

    def refresh_layout_shell():
        desktop_mode = is_desktop_layout()

        menu_button.visible = True
        close_sidebar_button.visible = True

        if desktop_mode:
            sidebar_container.visible = sidebar_visible
            sidebar_container.left = None
            sidebar_container.top = None
            sidebar_container.bottom = None
            sidebar_container.right = None
            sidebar_container.width = SIDEBAR_WIDTH

            desktop_controls = []
            if sidebar_visible:
                desktop_controls.append(sidebar_container)
                desktop_controls.append(
                    ft.VerticalDivider(
                        width=1,
                        thickness=1,
                        color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                    )
                )

            desktop_controls.append(
                ft.Container(
                    expand=True,
                    alignment=ft.Alignment.TOP_CENTER,
                    padding=ft.Padding.symmetric(horizontal=24, vertical=16),
                    content=main_content_area,
                )
            )

            body_host.expand = True
            body_host.content = ft.Row(
                desktop_controls,
                spacing=0,
                expand=True,
            )
        else:
            current_width = getattr(page, "width", None)
            if current_width is None and hasattr(page, "window") and page.window:
                current_width = getattr(page.window, "width", None)
            mobile_w = current_width or 360
            drawer_width = min(SIDEBAR_WIDTH, int(mobile_w * 0.85))

            sidebar_container.visible = sidebar_visible
            sidebar_container.left = 0
            sidebar_container.top = 0
            sidebar_container.bottom = 0
            sidebar_container.right = None
            sidebar_container.width = drawer_width

            if not sidebar_visible:
                body_host.expand = True
                body_host.content = ft.Container(
                    expand=True,
                    padding=ft.Padding.all(12),
                    content=main_content_area,
                )
            else:
                body_host.expand = True
                body_host.content = ft.Stack(
                    [
                        ft.Container(
                            left=0,
                            top=0,
                            right=0,
                            bottom=0,
                            padding=ft.Padding.all(12),
                            content=main_content_area,
                        ),
                        ft.Container(
                            left=0,
                            top=0,
                            right=0,
                            bottom=0,
                            bgcolor=ft.Colors.with_opacity(0.45, ft.Colors.BLACK),
                            on_click=toggle_sidebar,
                        ),
                        sidebar_container,
                    ],
                    expand=True,
                )

    def on_course_page_resized(e=None):
        refresh_layout_shell()
        page.update()

    page.on_resize = on_course_page_resized
    page.on_resized = on_course_page_resized

    # =========================================================
    # CONTENT UI RENDERERS
    # =========================================================

    CONTENT_RENDERERS = {}

    def register_content_renderer(key: str):
        def decorator(fn):
            CONTENT_RENDERERS[key] = fn
            return fn
        return decorator

    import flet_video as ftv
    from src.components.adaptive_video_player import AdaptiveVideoPlayer


    import logging
    import os
    from pathlib import Path
    from urllib.parse import urlparse

    logger = logging.getLogger("video_renderer")


    def _resolve_media_uri(value: str) -> str:
        """Guarantee the player gets something with a real URI scheme —
        an http(s) URL untouched, or a local http://127.0.0.1 URI for local files,
        so it behaves exactly like the online case (especially important for HLS)."""
        scheme = urlparse(value).scheme
        # Normal remote streaming cases bypass local handling
        if scheme in ("http", "https"):
            return value

        # Handle local files (either passed as raw paths or file:// URIs)
        if scheme == "file":
            import urllib.request
            path_str = urllib.request.url2pathname(urlparse(value).path)
        else:
            path_str = value

        path = Path(path_str).resolve()
        if not path.exists():
            logger.error("Video asset missing on disk: %s", path)

        try:
            from src.local_media_server import asset_url
            return asset_url(str(path))
        except Exception as e:
            logger.error("local_media_server failed: %s. Falling back to file://", e)
            return path.as_uri()


    @register_content_renderer("video_url")
    def render_video_block(value, lesson):
        try:
            media_uri = _resolve_media_uri(value)
        except Exception:
            logger.exception("Failed to resolve media URI for lesson %s, value=%r",
                            lesson.get("id"), value)
            media_uri = value  # fall back, let on_error report it

        def _on_error(e):
            logger.error(
                "Video playback error — lesson=%s value=%r resolved=%r data=%r",
                lesson.get("id"), value, media_uri, getattr(e, "data", None),
            )

        def _on_load(e):
            logger.info("Video loaded OK — lesson=%s resolved=%r", lesson.get("id"), media_uri)

        lesson_title = lesson.get("title") or lesson.get("name") or "Lesson Video"

        player = AdaptiveVideoPlayer(
            media_url=media_uri,
            title=lesson_title,
            autoplay=True,
            on_error=_on_error,
            on_load=_on_load,
        )

        return ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            content=ft.Container(width=1000, content=player),
        )
        
    @register_content_renderer("accompanying_text")
    def render_notes_block(value, lesson):
        async def handle_link_tap(e):
            await e.page.launch_url(e.data)

        return ft.Container(
            padding=20,
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.03, UI_ACCENT),
            border=ft.Border.only(
                left=ft.BorderSide(3.5, UI_ACCENT),
                top=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                right=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            ),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.LIGHTBULB_OUTLINE_ROUNDED, size=18, color=UI_ACCENT),
                            ft.Text("Lesson Notes & Key Takeaways", weight=ft.FontWeight.BOLD, size=14, color=UI_ACCENT),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Markdown(
                        value,
                        selectable=True,
                        extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
                        on_tap_link=handle_link_tap,
                        md_style_sheet=ft.MarkdownStyleSheet(
                            p_text_style=ft.TextStyle(
                                size=14.5,
                                weight=ft.FontWeight.W_400,
                                color=ft.Colors.ON_SURFACE,
                                height=1.5,
                            ),
                        ),
                    ),
                ],
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.START,
            ),
        )
        
    @register_content_renderer("document_url")
    def render_document_block(value, lesson):
        file_name = lesson["content"].get("file_name", "Course Document")

        async def handle_download(e):
            target_page = lesson.get("_page") or page
            await open_or_download_asset(target_page, value, file_name)

        return ft.Container(
            padding=24,
            border_radius=12,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            bgcolor=ft.Colors.SURFACE,
            content=ft.Row(
                [
                    ft.Container(
                        width=52,
                        height=52,
                        border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.RED_500),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(ft.Icons.PICTURE_AS_PDF_ROUNDED, size=28, color=ft.Colors.RED_500),
                    ),
                    ft.Column(
                        [
                            ft.Text(file_name, weight=ft.FontWeight.BOLD, size=15, color=ft.Colors.ON_SURFACE),
                            ft.Row(
                                [
                                    ft.Container(
                                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                        border_radius=4,
                                        bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                                        content=ft.Text("PDF / RESOURCE", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ),
                                    ft.Text("Attached reading material", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                                spacing=6,
                            ),
                        ],
                        expand=True,
                        spacing=4,
                    ),
                    ft.FilledButton(
                        content=ft.Row(
                            [
                                ft.Icon(ft.Icons.DOWNLOAD_ROUNDED, size=16, color=ft.Colors.SURFACE),
                                ft.Text("Download", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.SURFACE),
                            ],
                            tight=True,
                            spacing=6,
                        ),
                        style=ft.ButtonStyle(
                            bgcolor=UI_ACCENT,
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=ft.Padding.symmetric(horizontal=16, vertical=10),
                        ),
                        on_click=handle_download,
                    ),
                ],
                spacing=16,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )
        
    @register_content_renderer("text")
    def render_text_block(value, lesson):
        async def handle_link_tap(e):
            await e.page.launch_url(e.data)

        return ft.Container(
            padding=28,
            border_radius=12,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            content=ft.Markdown(
                value,
                selectable=True,
                extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                code_theme=ft.MarkdownCodeTheme.ATELIER_LAKESIDE_DARK,
                code_style_sheet=ft.MarkdownStyleSheet(
                    code_text_style=ft.TextStyle(font_family="Roboto Mono, monospace", size=14, color="#E2E8F0"),
                    codeblock_decoration=ft.BoxDecoration(
                        bgcolor="#16191F",
                        border_radius=ft.BorderRadius.all(8),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                    ),
                ),
                on_tap_link=handle_link_tap,
                md_style_sheet=ft.MarkdownStyleSheet(
                    text_alignment=ft.TextAlign.START,
                    p_text_style=ft.TextStyle(
                        size=15,
                        weight=ft.FontWeight.W_400,
                        color=ft.Colors.ON_SURFACE,
                        height=1.6,
                    ),
                    h1_text_style=ft.TextStyle(
                        size=22,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.ON_SURFACE,
                    ),
                    h2_text_style=ft.TextStyle(
                        size=18,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.ON_SURFACE,
                    ),
                    h3_text_style=ft.TextStyle(
                        size=16,
                        weight=ft.FontWeight.W_600,
                        color=ft.Colors.ON_SURFACE,
                    ),
                    code_text_style=ft.TextStyle(
                        size=14,
                        font_family="Roboto Mono, monospace",
                        color=UI_ACCENT,
                        bgcolor=ft.Colors.with_opacity(0.08, UI_ACCENT),
                    ),
                ),
            ),
        )

    @register_content_renderer("audio_path")
    def render_audio_block(value, lesson):
        file_name = lesson["content"].get("file_name", "Audio Lesson")

        async def handle_download(e):
            target_page = lesson.get("_page") or page
            await open_or_download_asset(target_page, value, file_name)

        return ft.Container(
            padding=24,
            border_radius=12,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            content=ft.Row(
                [
                    ft.Container(
                        width=52,
                        height=52,
                        border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.10, UI_ACCENT),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(ft.Icons.HEADPHONES_ROUNDED, size=28, color=UI_ACCENT),
                    ),
                    ft.Column(
                        [
                            ft.Text(file_name, weight=ft.FontWeight.BOLD, size=15, color=ft.Colors.ON_SURFACE),
                            ft.Row(
                                [
                                    ft.Container(
                                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                        border_radius=4,
                                        bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                                        content=ft.Text("AUDIO LESSON", size=9, weight=ft.FontWeight.BOLD, color=UI_ACCENT),
                                    ),
                                    ft.Text("Audio recording & lecture", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                                spacing=6,
                            ),
                        ],
                        expand=True,
                        spacing=4,
                    ),
                    ft.FilledButton(
                        content=ft.Row(
                            [
                                ft.Icon(ft.Icons.DOWNLOAD_ROUNDED, size=16, color=ft.Colors.SURFACE),
                                ft.Text("Download Audio", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.SURFACE),
                            ],
                            tight=True,
                            spacing=6,
                        ),
                        style=ft.ButtonStyle(
                            bgcolor=UI_ACCENT,
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=ft.Padding.symmetric(horizontal=16, vertical=10),
                        ),
                        on_click=handle_download,
                    ),
                ],
                spacing=16,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )
    
    @register_content_renderer("cards")
    def render_cards_block(value, lesson):
        cards_list = value or []
        card_idx = [0]
        is_animating = [False]

        total_cards = len(cards_list) if cards_list else 1

        def parse_card(raw):
            if isinstance(raw, dict):
                if "text" in raw:
                    return str(raw["text"]).strip()
                if "content" in raw:
                    return str(raw["content"]).strip()
                f = raw.get("front") or raw.get("question") or ""
                b = raw.get("back") or raw.get("answer") or ""
                if f and b:
                    return f"{f}\n\n---\n\n{b}".strip()
                return str(f or b or "").strip()
            return str(raw or "").strip()

        init_text = parse_card(cards_list[0] if cards_list else "No cards available.")

        counter_badge = ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=4),
            border_radius=999,
            bgcolor=ft.Colors.with_opacity(0.08, UI_ACCENT),
            content=ft.Text(
                f"Card 1 of {total_cards}",
                color=UI_ACCENT,
                weight=ft.FontWeight.BOLD,
                size=12,
            ),
        )

        progress_track = ft.ProgressBar(
            value=1.0 / max(total_cards, 1),
            color=UI_ACCENT,
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
            height=4,
            border_radius=2,
        )

        card_md = ft.Markdown(
            value=init_text,
            selectable=False,
            extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
            md_style_sheet=ft.MarkdownStyleSheet(
                text_alignment=ft.TextAlign.CENTER,
                p_text_style=ft.TextStyle(
                    size=18,
                    weight=ft.FontWeight.W_600,
                    color=ft.Colors.ON_SURFACE,
                    height=1.5,
                ),
            ),
        )

        card_surface = ft.Container(
            padding=ft.Padding.symmetric(horizontal=28, vertical=36),
            height=260,
            border_radius=16,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)),
            shadow=ft.BoxShadow(
                blur_radius=18,
                color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK),
                offset=ft.Offset(0, 6),
            ),
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                [
                    card_md,
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
            ),
            offset=ft.Offset(0, 0),
            animate_offset=ft.Animation(220, ft.AnimationCurve.EASE_OUT_CUBIC),
            opacity=1.0,
            animate_opacity=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
            scale=1.0,
            animate_scale=ft.Animation(220, ft.AnimationCurve.EASE_OUT_BACK),
            ink=True,
            on_click=lambda e: lesson["_page"].run_task(go_forward),
        )

        async def go_forward(e=None):
            if card_idx[0] >= total_cards - 1 or is_animating[0]:
                return
            is_animating[0] = True

            # Phase 1: Slide out to the left & fade
            card_surface.offset = ft.Offset(-0.35, 0)
            card_surface.opacity = 0.0
            card_surface.scale = 0.95
            lesson["_page"].update()
            await asyncio.sleep(0.16)

            # Phase 2: Update content & advance
            card_idx[0] += 1
            card_md.value = parse_card(cards_list[card_idx[0]])
            counter_badge.content.value = f"Card {card_idx[0] + 1} of {total_cards}"
            progress_track.value = (card_idx[0] + 1) / max(total_cards, 1)
            prev_btn.disabled = card_idx[0] == 0
            next_btn.disabled = card_idx[0] == total_cards - 1

            # Pre-position on right side
            card_surface.offset = ft.Offset(0.35, 0)
            lesson["_page"].update()
            await asyncio.sleep(0.02)

            # Phase 3: Slide into center from right
            card_surface.offset = ft.Offset(0, 0)
            card_surface.opacity = 1.0
            card_surface.scale = 1.0
            lesson["_page"].update()
            is_animating[0] = False

        async def go_back(e=None):
            if card_idx[0] <= 0 or is_animating[0]:
                return
            is_animating[0] = True

            # Phase 1: Slide out to the right & fade
            card_surface.offset = ft.Offset(0.35, 0)
            card_surface.opacity = 0.0
            card_surface.scale = 0.95
            lesson["_page"].update()
            await asyncio.sleep(0.16)

            # Phase 2: Update content & decrement
            card_idx[0] -= 1
            card_md.value = parse_card(cards_list[card_idx[0]])
            counter_badge.content.value = f"Card {card_idx[0] + 1} of {total_cards}"
            progress_track.value = (card_idx[0] + 1) / max(total_cards, 1)
            prev_btn.disabled = card_idx[0] == 0
            next_btn.disabled = card_idx[0] == total_cards - 1

            # Pre-position on left side
            card_surface.offset = ft.Offset(-0.35, 0)
            lesson["_page"].update()
            await asyncio.sleep(0.02)

            # Phase 3: Slide into center from left
            card_surface.offset = ft.Offset(0, 0)
            card_surface.opacity = 1.0
            card_surface.scale = 1.0
            lesson["_page"].update()
            is_animating[0] = False

        prev_btn = ft.OutlinedButton(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.ARROW_BACK_ROUNDED, size=15, color=ft.Colors.ON_SURFACE),
                    ft.Text("Previous", size=12.5, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                ],
                tight=True,
                spacing=6,
            ),
            on_click=lambda e: lesson["_page"].run_task(go_back),
            disabled=True,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding.symmetric(horizontal=16, vertical=10),
            ),
        )

        next_btn = ft.FilledButton(
            content=ft.Row(
                [
                    ft.Text("Next", size=12.5, weight=ft.FontWeight.BOLD, color=ft.Colors.SURFACE),
                    ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=15, color=ft.Colors.SURFACE),
                ],
                tight=True,
                spacing=6,
            ),
            on_click=lambda e: lesson["_page"].run_task(go_forward),
            disabled=total_cards <= 1,
            style=ft.ButtonStyle(
                bgcolor=UI_ACCENT,
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding.symmetric(horizontal=18, vertical=10),
                elevation=0,
            ),
        )

        return ft.Container(
            padding=24,
            border_radius=16,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK), offset=ft.Offset(0, 2)),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Row([ft.Icon(ft.Icons.STYLE_ROUNDED, size=16, color=UI_ACCENT), ft.Text("Interactive Flashcards", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE)], spacing=6),
                            counter_badge,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    progress_track,
                    ft.Container(height=6),
                    card_surface,
                    ft.Container(height=6),
                    ft.Row(
                        [
                            prev_btn,
                            next_btn,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        )

    # =========================================================
    # 5. LESSON TYPE RENDERERS
    # =========================================================
    def render_scenario_ui(lesson: dict):
        async def handle_link_tap(e):
            await e.page.launch_url(e.data)

        content = lesson.get("content", {})
        scenario_text = content.get("scenario", "")
        choices = content.get("choices", [])

        consequence_box = ft.Container(
            padding=18,
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.04, UI_ACCENT),
            border=ft.Border.only(
                left=ft.BorderSide(3.5, UI_ACCENT),
                top=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                right=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            ),
            visible=False,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.LIGHTBULB_CIRCLE_ROUNDED, color=UI_ACCENT, size=20),
                            ft.Text("Scenario Outcome & Analysis", weight=ft.FontWeight.BOLD, color=UI_ACCENT, size=14),
                        ],
                        spacing=8,
                    ),
                    ft.Markdown(
                        "",
                        selectable=False,
                        extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
                        md_style_sheet=ft.MarkdownStyleSheet(
                            p_text_style=ft.TextStyle(color=ft.Colors.ON_SURFACE, size=14, height=1.5),
                        ),
                    ),
                ],
                spacing=8,
            ),
        )

        buttons_col = ft.Column(spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

        def make_button_style(selected: bool):
            if selected:
                return ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=8),
                    padding=ft.Padding.symmetric(horizontal=16, vertical=14),
                    bgcolor={
                        ft.ControlState.DEFAULT: UI_ACCENT,
                        ft.ControlState.HOVERED: UI_ACCENT,
                        ft.ControlState.PRESSED: UI_ACCENT,
                    },
                    color={
                        ft.ControlState.DEFAULT: ft.Colors.SURFACE,
                        ft.ControlState.HOVERED: ft.Colors.SURFACE,
                        ft.ControlState.PRESSED: ft.Colors.SURFACE,
                    },
                    side={
                        ft.ControlState.DEFAULT: ft.BorderSide(1.5, UI_ACCENT),
                    },
                )
            else:
                return ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=8),
                    padding=ft.Padding.symmetric(horizontal=16, vertical=14),
                    bgcolor={
                        ft.ControlState.DEFAULT: ft.Colors.TRANSPARENT,
                        ft.ControlState.HOVERED: ft.Colors.with_opacity(0.05, UI_ACCENT),
                        ft.ControlState.PRESSED: ft.Colors.with_opacity(0.10, UI_ACCENT),
                    },
                    color={
                        ft.ControlState.DEFAULT: ft.Colors.ON_SURFACE,
                    },
                    side={
                        ft.ControlState.DEFAULT: ft.BorderSide(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                    },
                )

        def handle_choice(idx, cons_text):
            for i, btn in enumerate(buttons_col.controls):
                btn.style = make_button_style(selected=(i == idx))

            consequence_box.content.controls[1].value = cons_text
            consequence_box.visible = True
            lesson["_page"].update()

        for idx, ch in enumerate(choices):
            btn = ft.OutlinedButton(
                content=ft.Row(
                    [
                        ft.Container(
                            width=24,
                            height=24,
                            border_radius=999,
                            bgcolor=ft.Colors.with_opacity(0.08, UI_ACCENT),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Text(chr(65 + idx), size=11, weight=ft.FontWeight.BOLD, color=UI_ACCENT),
                        ),
                        ft.Text(ch.get("text", f"Option {idx+1}"), size=13, weight=ft.FontWeight.W_500, expand=True),
                    ],
                    spacing=10,
                ),
                style=make_button_style(selected=False),
                on_click=lambda e, i=idx, c_t=ch.get("consequence", ""): handle_choice(i, c_t),
            )
            buttons_col.controls.append(btn)

        return ft.Container(
            padding=24,
            border_radius=12,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.CALL_SPLIT_ROUNDED, color=UI_ACCENT, size=22),
                            ft.Text("Decision Scenario", weight=ft.FontWeight.BOLD, size=16, color=ft.Colors.ON_SURFACE),
                        ],
                        spacing=8,
                    ),
                    ft.Markdown(
                        scenario_text,
                        selectable=True,
                        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                        on_tap_link=handle_link_tap,
                        md_style_sheet=ft.MarkdownStyleSheet(
                            text_alignment=ft.TextAlign.START,
                            p_text_style=ft.TextStyle(size=15, weight=ft.FontWeight.W_400, color=ft.Colors.ON_SURFACE, height=1.5),
                        ),
                    ),
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
                    ft.Text("Choose how you would proceed:", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                    buttons_col,
                    consequence_box,
                ],
                spacing=14,
            ),
        )

    def render_assessment_ui(lesson: dict):
        content = lesson.get("content", {})
        questions = content.get("questions", [])
        
        # --- CHECK COMPLETION STATE ---
        is_completed = lesson.get("is_done", False)

        current_assessment_state.clear()
        question_cards = []
        
        text_color = ft.Colors.ON_SURFACE_VARIANT if is_completed else ft.Colors.ON_SURFACE
        accent_color = ft.Colors.GREY_400 if is_completed else UI_ACCENT

        for q_idx, q in enumerate(questions):
            options_data = q.get("options", [])
            correct_count = sum(1 for opt in options_data if opt.get("is_correct"))
            is_multi_select = correct_count > 1

            type_tag = ft.Container(
                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                border_radius=4,
                bgcolor=ft.Colors.with_opacity(0.08, UI_ACCENT) if not is_completed else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                content=ft.Text(
                    "MULTIPLE CHOICE" if is_multi_select else "SINGLE CHOICE",
                    size=9,
                    weight=ft.FontWeight.BOLD,
                    color=UI_ACCENT if not is_completed else ft.Colors.ON_SURFACE_VARIANT,
                ),
            )

            q_text = ft.Markdown(
                value=q.get("text", ""),
                selectable=True,
                extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
                md_style_sheet=ft.MarkdownStyleSheet(
                    p_text_style=ft.TextStyle(size=15, color=ft.Colors.ON_SURFACE, weight=ft.FontWeight.W_600, height=1.4),
                ),
            )

            if is_multi_select:
                checkboxes = []
                options_rows = []
                for opt in options_data:
                    opt_text = opt.get("text", "")
                    cb = ft.Checkbox(
                        value=False, 
                        data=opt_text, 
                        fill_color={ft.ControlState.SELECTED: accent_color},
                        check_color=ft.Colors.SURFACE,
                        disabled=is_completed,
                    )
                    checkboxes.append(cb)
                    options_rows.append(
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                            border_radius=8,
                            bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
                            border=ft.Border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
                            content=ft.Row(
                                [cb, ft.Text(opt_text, expand=True, size=13.5, color=text_color)],
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=8,
                            ),
                        )
                    )
                options_ui = ft.Column(options_rows, spacing=8)
                current_assessment_state[f"question_{q_idx + 1}"] = {"type": "multi", "controls": checkboxes}
            else:
                radio_options = []
                for opt in options_data:
                    opt_text = opt.get("text", "")
                    radio_options.append(
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                            border_radius=8,
                            bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
                            border=ft.Border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
                            content=ft.Row(
                                [
                                    ft.Radio(value=opt_text, fill_color={ft.ControlState.SELECTED: accent_color}, disabled=is_completed),
                                    ft.Text(opt_text, expand=True, size=13.5, color=text_color),
                                ],
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=8,
                            ),
                        )
                    )
                options_group = ft.RadioGroup(content=ft.Column(radio_options, spacing=8))
                options_ui = options_group
                current_assessment_state[f"question_{q_idx + 1}"] = {"type": "single", "controls": options_group}

            question_cards.append(
                ft.Container(
                    padding=22,
                    border_radius=12,
                    bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE) if is_completed else ft.Colors.SURFACE,
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Row(
                                        [
                                            ft.Container(
                                                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                                border_radius=4,
                                                bgcolor=UI_ACCENT if not is_completed else ft.Colors.GREY_500,
                                                content=ft.Text(f"Q{q_idx + 1}", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.SURFACE),
                                            ),
                                            type_tag,
                                        ],
                                        spacing=8,
                                    ),
                                    ft.Icon(ft.Icons.LOCK_ROUNDED, color=ft.Colors.GREY_400, size=16) if is_completed else ft.Container(),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Container(content=q_text),
                            ft.Divider(height=1, color=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
                            options_ui,
                        ],
                        spacing=12,
                    ),
                )
            )

        banner = []
        if is_completed:
            banner = [
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.GREEN_600),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.20, ft.Colors.GREEN_600)),
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.VERIFIED_ROUNDED, color=ft.Colors.GREEN_600, size=20),
                            ft.Text("You have already passed and completed this assessment.", weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_700, size=12.5),
                        ],
                        spacing=10,
                    ),
                )
            ]

        return ft.Container(
            padding=0,
            content=ft.Column(banner + question_cards, spacing=16, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
        )

    def render_stepper_ui(lesson: dict):
        content = lesson.get("content", {})
        steps = content.get("steps", [])
        valid_steps = [s for s in steps if str(s.get("headline", "")).strip() or str(s.get("content", "")).strip()]

        if not valid_steps:
            return ft.Container(
                padding=30,
                border_radius=12,
                bgcolor=ft.Colors.SURFACE,
                content=ft.Text("This walkthrough has no steps yet.", color=ft.Colors.ON_SURFACE_VARIANT),
            )

        current_step_idx = [0]

        title_text = content.get("title", "")
        intro_text = content.get("intro", "")

        header_elements = []
        if title_text:
            header_elements.append(ft.Text(title_text, size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE))
        if intro_text:
            header_elements.append(
                ft.Markdown(
                    intro_text,
                    extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                    md_style_sheet=ft.MarkdownStyleSheet(
                        p_text_style=ft.TextStyle(size=14, color=ft.Colors.ON_SURFACE_VARIANT, height=1.5)
                    ),
                )
            )

        progress_bar = ft.ProgressBar(value=1.0 / len(valid_steps), color=ft.Colors.CYAN_600, bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE))
        counter_label = ft.Text(f"Phase 1 of {len(valid_steps)}", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_600)

        tag_chip = ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=4),
            border_radius=6,
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.CYAN_600),
            content=ft.Text(valid_steps[0].get("tag", "Step 1"), size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_600),
        )
        headline_text = ft.Text(valid_steps[0].get("headline", ""), size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE)
        content_md = ft.Markdown(
            valid_steps[0].get("content", ""),
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
            selectable=True,
            md_style_sheet=ft.MarkdownStyleSheet(
                p_text_style=ft.TextStyle(size=15, height=1.6, color=ft.Colors.ON_SURFACE),
                code_text_style=ft.TextStyle(font_family="monospace", size=13, color=ft.Colors.CYAN_300),
            ),
        )
        takeaway_col = ft.Container(
            padding=16,
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.CYAN_600),
            border=ft.Border.only(left=ft.BorderSide(4, ft.Colors.CYAN_600)),
            visible=bool(valid_steps[0].get("takeaway", "").strip()),
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.LIGHTBULB_OUTLINE_ROUNDED, color=ft.Colors.CYAN_600, size=22),
                    ft.Column(
                        [
                            ft.Text("Key Takeaway", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_600),
                            ft.Text(valid_steps[0].get("takeaway", ""), size=14, color=ft.Colors.ON_SURFACE),
                        ],
                        spacing=4,
                        expand=True,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
        )

        prev_btn = ft.OutlinedButton(
            content=ft.Row([ft.Icon(ft.Icons.ARROW_BACK_ROUNDED, size=15), ft.Text("Previous Phase", size=13, weight=ft.FontWeight.BOLD)], tight=True, spacing=6),
            disabled=True,
        )
        next_btn = ft.FilledButton(
            content=ft.Row([ft.Text("Next Phase", size=13, weight=ft.FontWeight.BOLD), ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=15)], tight=True, spacing=6),
            style=ft.ButtonStyle(bgcolor=ft.Colors.CYAN_600, color=ft.Colors.WHITE),
        )

        def update_step_view(idx):
            current_step_idx[0] = idx
            st = valid_steps[idx]
            progress_bar.value = (idx + 1) / len(valid_steps)
            counter_label.value = f"Phase {idx + 1} of {len(valid_steps)}"
            tag_chip.content.value = st.get("tag", f"Step {idx + 1}")
            headline_text.value = st.get("headline", "")
            content_md.value = st.get("content", "")

            tw = st.get("takeaway", "").strip()
            if tw:
                takeaway_col.content.controls[1].controls[1].value = tw
                takeaway_col.visible = True
            else:
                takeaway_col.visible = False

            prev_btn.disabled = (idx == 0)
            is_last = (idx == len(valid_steps) - 1)
            if is_last:
                next_btn.content.controls[0].value = "Completed ✓"
                next_btn.content.controls[1].icon = ft.Icons.CHECK_ROUNDED
                next_btn.style.bgcolor = ft.Colors.GREEN_600
                lesson["is_done"] = True
                recalculate_locks()
            else:
                next_btn.content.controls[0].value = "Next Phase"
                next_btn.content.controls[1].icon = ft.Icons.ARROW_FORWARD_ROUNDED
                next_btn.style.bgcolor = ft.Colors.CYAN_600
            page.update()

        def on_prev(e):
            if current_step_idx[0] > 0:
                update_step_view(current_step_idx[0] - 1)

        def on_next(e):
            if current_step_idx[0] < len(valid_steps) - 1:
                update_step_view(current_step_idx[0] + 1)

        prev_btn.on_click = on_prev
        next_btn.on_click = on_next

        return ft.Container(
            padding=24,
            border_radius=14,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            content=ft.Column(
                header_elements + [
                    ft.Row([counter_label, progress_bar], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    tag_chip,
                    headline_text,
                    content_md,
                    takeaway_col,
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    ft.Row([prev_btn, next_btn], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ],
                spacing=14,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        )

    def render_sequencer_ui(lesson: dict):
        content = lesson.get("content", {})
        prompt = content.get("prompt", "")
        items = content.get("items", [])
        valid_items = [it for it in items if str(it.get("label", "")).strip()]

        if len(valid_items) < 2:
            return ft.Container(
                padding=30,
                border_radius=12,
                bgcolor=ft.Colors.SURFACE,
                content=ft.Text("This sequence challenge requires at least 2 items.", color=ft.Colors.ON_SURFACE_VARIANT),
            )

        def get_scrambled_items(items_list):
            scrambled = list(items_list)
            if len(scrambled) < 2:
                return scrambled
            correct_ids = [it.get("id") for it in items_list]
            for _ in range(50):
                random.shuffle(scrambled)
                if [it.get("id") for it in scrambled] != correct_ids:
                    return scrambled
            scrambled[0], scrambled[1] = scrambled[1], scrambled[0]
            return scrambled

        current_items = get_scrambled_items(valid_items)

        feedback_banner = ft.Container(visible=False, padding=14, border_radius=10)
        items_column = ft.Column(spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

        def render_items_list(status_map=None):
            items_column.controls.clear()
            for idx, it in enumerate(current_items):
                is_correct_pos = status_map.get(it.get("id")) if status_map else None

                if is_correct_pos is True:
                    border_color = ft.Colors.GREEN_600
                    bg_color = ft.Colors.with_opacity(0.08, ft.Colors.GREEN_600)
                    status_icon = ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.GREEN_600, size=20)
                elif is_correct_pos is False:
                    border_color = ft.Colors.AMBER_600
                    bg_color = ft.Colors.with_opacity(0.08, ft.Colors.AMBER_600)
                    status_icon = ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, color=ft.Colors.AMBER_600, size=20)
                else:
                    border_color = ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)
                    bg_color = ft.Colors.SURFACE
                    status_icon = ft.Container()

                def move_up(i):
                    def handler(e):
                        if i > 0:
                            current_items[i], current_items[i - 1] = current_items[i - 1], current_items[i]
                            render_items_list(None)
                            feedback_banner.visible = False
                            page.update()
                    return handler

                def move_down(i):
                    def handler(e):
                        if i < len(current_items) - 1:
                            current_items[i], current_items[i + 1] = current_items[i + 1], current_items[i]
                            render_items_list(None)
                            feedback_banner.visible = False
                            page.update()
                    return handler

                explanation_ui = ft.Container()
                if is_correct_pos is True and it.get("explanation", "").strip():
                    explanation_ui = ft.Container(
                        padding=10,
                        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
                        border_radius=8,
                        content=ft.Row(
                            [
                                ft.Icon(ft.Icons.LIGHTBULB_ROUNDED, color=ft.Colors.AMBER_500, size=16),
                                ft.Text(it.get("explanation"), size=13, color=ft.Colors.ON_SURFACE, expand=True),
                            ],
                            spacing=8,
                        ),
                    )

                item_card = ft.Container(
                    padding=14,
                    border_radius=10,
                    border=ft.Border.all(1, border_color),
                    bgcolor=bg_color,
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Container(
                                        width=28,
                                        height=28,
                                        border_radius=999,
                                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_600),
                                        alignment=ft.Alignment.CENTER,
                                        content=ft.Text(f"{idx + 1}", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_600),
                                    ),
                                    ft.Text(it.get("label", ""), size=14, weight=ft.FontWeight.W_500, expand=True, color=ft.Colors.ON_SURFACE),
                                    status_icon,
                                    ft.Row(
                                        [
                                            ft.IconButton(ft.Icons.KEYBOARD_ARROW_UP_ROUNDED, icon_size=20, disabled=(idx == 0), on_click=move_up(idx)),
                                            ft.IconButton(ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED, icon_size=20, disabled=(idx == len(current_items) - 1), on_click=move_down(idx)),
                                        ],
                                        spacing=0,
                                    ),
                                ],
                                spacing=12,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            explanation_ui,
                        ],
                        spacing=8,
                    ),
                )
                items_column.controls.append(item_card)

        def check_sequence(e):
            correct_order = [it.get("id") for it in valid_items]
            current_order = [it.get("id") for it in current_items]
            status_map = {}
            correct_count = 0

            for idx, target_id in enumerate(correct_order):
                is_match = (idx < len(current_order) and current_order[idx] == target_id)
                status_map[current_order[idx]] = is_match
                if is_match:
                    correct_count += 1

            is_perfect = (correct_count == len(valid_items))

            if is_perfect:
                feedback_banner.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.GREEN_600)
                feedback_banner.border = ft.Border.all(1, ft.Colors.GREEN_600)
                feedback_banner.content = ft.Row([
                    ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.GREEN_600, size=24),
                    ft.Text("Outstanding! Everything is in the perfect order!", weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_600, size=14),
                ], spacing=10)
                lesson["is_done"] = True
                recalculate_locks()
            else:
                feedback_banner.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.AMBER_600)
                feedback_banner.border = ft.Border.all(1, ft.Colors.AMBER_600)
                feedback_banner.content = ft.Row([
                    ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, color=ft.Colors.AMBER_600, size=22),
                    ft.Text(f"{correct_count} of {len(valid_items)} steps are in position. Check the highlighted items and try again!", weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_600, size=13),
                ], spacing=10)

            feedback_banner.visible = True
            render_items_list(status_map)
            page.update()

        def reset_shuffle(e):
            nonlocal current_items
            current_items = get_scrambled_items(valid_items)
            feedback_banner.visible = False
            render_items_list(None)
            page.update()

        render_items_list(None)

        return ft.Container(
            padding=24,
            border_radius=14,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.REORDER_ROUNDED, color=ft.Colors.AMBER_600, size=22),
                            ft.Text("Sequence Challenge", weight=ft.FontWeight.BOLD, size=16, color=ft.Colors.ON_SURFACE),
                        ],
                        spacing=8,
                    ),
                    ft.Markdown(
                        prompt or "Arrange the following steps into their correct sequence:",
                        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                        selectable=True,
                        md_style_sheet=ft.MarkdownStyleSheet(
                            p_text_style=ft.TextStyle(size=14, color=ft.Colors.ON_SURFACE, height=1.5)
                        ),
                    ),
                    feedback_banner,
                    items_column,
                    ft.Row(
                        [
                            ft.OutlinedButton("Shuffle / Reset", icon=ft.Icons.REFRESH_ROUNDED, on_click=reset_shuffle),
                            ft.FilledButton(
                                "Verify Sequence",
                                icon=ft.Icons.CHECK_ROUNDED,
                                style=ft.ButtonStyle(bgcolor=ft.Colors.AMBER_600, color=ft.Colors.WHITE),
                                on_click=check_sequence,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ],
                spacing=16,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        )

    def render_cloze_ui(lesson: dict):
        content = lesson.get("content", {})
        raw_text = content.get("text", "")
        distractors = content.get("distractors", [])
        explanation = content.get("explanation", "")

        segments, blanks = parse_cloze_text(raw_text)
        if not blanks:
            return ft.Container(
                padding=24,
                border_radius=12,
                bgcolor=ft.Colors.SURFACE,
                content=ft.Text("This cloze exercise has no blanks configured.", color=ft.Colors.ON_SURFACE_VARIANT),
            )

        all_words = list(set([b["answer"] for b in blanks] + [d for d in distractors if d.strip()]))
        random.shuffle(all_words)

        user_answers = {b["index"]: "" for b in blanks}
        validation_state = {}

        feedback_banner = ft.Container(visible=False, padding=14, border_radius=10)
        explanation_box = ft.Container(
            padding=16,
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.GREEN_600),
            border=ft.Border.only(left=ft.BorderSide(4, ft.Colors.GREEN_600)),
            visible=False,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.LIGHTBULB_ROUNDED, color=ft.Colors.GREEN_600, size=20),
                            ft.Text("Pedagogical Summary & Takeaway", weight=ft.FontWeight.BOLD, size=14, color=ft.Colors.GREEN_600),
                        ],
                        spacing=8,
                    ),
                    ft.Markdown(
                        explanation,
                        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                        selectable=True,
                        md_style_sheet=ft.MarkdownStyleSheet(
                            p_text_style=ft.TextStyle(size=14, color=ft.Colors.ON_SURFACE, height=1.5)
                        ),
                    ),
                ],
                spacing=8,
            ),
        )

        text_flow_row = ft.Row(wrap=True, spacing=6, run_spacing=8)
        word_bank_row = ft.Row(wrap=True, spacing=8, run_spacing=8)

        def rebuild_ui():
            text_flow_row.controls.clear()
            for seg in segments:
                if seg["type"] == "text":
                    text_flow_row.controls.append(
                        ft.Text(seg["content"], size=15, color=ft.Colors.ON_SURFACE)
                    )
                else:
                    b_info = seg["info"]
                    b_idx = b_info["index"]
                    ans_val = user_answers.get(b_idx, "")
                    is_correct = validation_state.get(b_idx)

                    if is_correct is True:
                        border_c = ft.Colors.GREEN_600
                        bg_c = ft.Colors.with_opacity(0.12, ft.Colors.GREEN_600)
                        text_c = ft.Colors.GREEN_600
                    elif is_correct is False:
                        border_c = ft.Colors.AMBER_600
                        bg_c = ft.Colors.with_opacity(0.12, ft.Colors.AMBER_600)
                        text_c = ft.Colors.AMBER_600
                    else:
                        border_c = ft.Colors.CYAN_600 if not ans_val else UI_ACCENT
                        bg_c = ft.Colors.with_opacity(0.08, border_c)
                        text_c = ft.Colors.ON_SURFACE

                    display_label = ans_val or (f"[{b_info['hint']}]" if b_info["hint"] else "[ blank ]")

                    def clear_blank(bi):
                        def handler(e):
                            if user_answers.get(bi):
                                user_answers[bi] = ""
                                validation_state.pop(bi, None)
                                feedback_banner.visible = False
                                rebuild_ui()
                                page.update()
                        return handler

                    text_flow_row.controls.append(
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=12, vertical=5),
                            border_radius=8,
                            border=ft.Border.all(1.5, border_c),
                            bgcolor=bg_c,
                            content=ft.Text(display_label, size=14, weight=ft.FontWeight.BOLD, color=text_c),
                            tooltip="Click to remove word" if ans_val else (b_info["hint"] or "Blank"),
                            on_click=clear_blank(b_idx),
                        )
                    )

            word_bank_row.controls.clear()
            used_words = [w for w in user_answers.values() if w]
            for w in all_words:
                is_used = w in used_words
                def pick_word(word):
                    def handler(e):
                        for b in blanks:
                            if not user_answers.get(b["index"]):
                                user_answers[b["index"]] = word
                                validation_state.pop(b["index"], None)
                                break
                        rebuild_ui()
                        page.update()
                    return handler

                word_bank_row.controls.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=14, vertical=7),
                        border_radius=999,
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE) if not is_used else ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE)),
                        bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE) if not is_used else ft.Colors.TRANSPARENT,
                        content=ft.Text(w, size=13, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE if not is_used else ft.Colors.with_opacity(0.25, ft.Colors.ON_SURFACE)),
                        opacity=0.35 if is_used else 1.0,
                        on_click=pick_word(w) if not is_used else None,
                    )
                )

        def check_answers(e):
            all_correct = True
            correct_count = 0
            for b in blanks:
                b_idx = b["index"]
                user_val = user_answers.get(b_idx, "").strip().lower()
                expected = b["answer"].strip().lower()
                match = (user_val == expected)
                validation_state[b_idx] = match
                if match:
                    correct_count += 1
                else:
                    all_correct = False

            if all_correct:
                feedback_banner.bgcolor = ft.Colors.with_opacity(0.15, ft.Colors.GREEN_600)
                feedback_banner.border = ft.Border.all(1, ft.Colors.GREEN_600)
                feedback_banner.content = ft.Row([
                    ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.GREEN_600, size=22),
                    ft.Text("All blanks filled with 100% accuracy! Well done.", weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_600, size=14),
                ], spacing=10)
                if explanation:
                    explanation_box.visible = True
                lesson["is_done"] = True
                recalculate_locks()
            else:
                feedback_banner.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.AMBER_600)
                feedback_banner.border = ft.Border.all(1, ft.Colors.AMBER_600)
                feedback_banner.content = ft.Row([
                    ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, color=ft.Colors.AMBER_600, size=22),
                    ft.Text(f"{correct_count} of {len(blanks)} correct. Tap highlighted blanks to swap words.", weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_600, size=13),
                ], spacing=10)

            feedback_banner.visible = True
            rebuild_ui()
            page.update()

        def reset_blanks(e):
            for b in blanks:
                user_answers[b["index"]] = ""
            validation_state.clear()
            feedback_banner.visible = False
            explanation_box.visible = False
            rebuild_ui()
            page.update()

        rebuild_ui()

        return ft.Container(
            padding=24,
            border_radius=14,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.EDIT_NOTE_ROUNDED, color=ft.Colors.GREEN_600, size=22),
                            ft.Text("Fill in the Blanks Reading", weight=ft.FontWeight.BOLD, size=16, color=ft.Colors.ON_SURFACE),
                        ],
                        spacing=8,
                    ),
                    text_flow_row,
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    ft.Text("Word Bank (Tap word to place into the next blank):", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                    word_bank_row,
                    feedback_banner,
                    explanation_box,
                    ft.Row(
                        [
                            ft.OutlinedButton("Clear All", icon=ft.Icons.CLEAR_ALL_ROUNDED, on_click=reset_blanks),
                            ft.FilledButton("Check Blanks", icon=ft.Icons.CHECK_ROUNDED, style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_600, color=ft.Colors.WHITE), on_click=check_answers),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ],
                spacing=16,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        )

    def render_code_lab_ui(lesson: dict):
        content = lesson.get("content", {})
        language = content.get("language", "python").lower()
        instructions = content.get("instructions", "")
        starter_code = content.get("starter_code", "")
        setup_sql = content.get("setup_sql", "")
        test_cases = content.get("test_cases", [])

        is_sql = "sql" in language
        lang_display = "SQLite In-Memory" if is_sql else "Python 3.12"
        lang_color = ft.Colors.TEAL_400 if is_sql else ft.Colors.BLUE_400

        code_input = ft.TextField(
            value=starter_code,
            multiline=True,
            min_lines=8,
            max_lines=20,
            border_radius=8,
            bgcolor=ft.Colors.BLACK,
            text_style=ft.TextStyle(font_family="monospace", size=13, color=ft.Colors.GREEN_300),
        )

        stdin_field = ft.TextField(
            label="Program Input (stdin)",
            hint_text="Input text to pass to input() calls (optional)...",
            dense=True,
            border_radius=8,
            visible=(not is_sql),
            text_style=ft.TextStyle(font_family="monospace", size=12),
        )

        console_output = ft.Text("Click 'Run Code' to execute in sandbox...", font_family="monospace", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        test_results_col = ft.Column(spacing=6, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

        console_container = ft.Container(
            padding=14,
            border_radius=8,
            bgcolor=ft.Colors.BLACK,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE)),
            content=console_output,
        )

        status_banner = ft.Container(visible=False, padding=12, border_radius=8)

        def run_code(e):
            user_code = code_input.value
            results = run_code_lab_tests(language, user_code, setup_sql, test_cases)

            if is_sql:
                res = execute_sql(user_code, setup_sql)
                if res["success"]:
                    cols = " | ".join(res["columns"])
                    rows_text = "\n".join([" | ".join([str(v) for v in r]) for r in res["rows"][:25]])
                    console_output.value = f"COLUMNS: {cols}\n" + ("-" * 45) + f"\n{rows_text or '(0 rows returned)'}"
                    console_output.color = ft.Colors.GREEN_300
                else:
                    console_output.value = f"SQL ERROR:\n{res['error']}"
                    console_output.color = ft.Colors.RED_400
            else:
                passed_stdin = stdin_field.value if stdin_field.value else (test_cases[0].get("input", "") if test_cases else "")
                res = execute_python(user_code, test_input=passed_stdin)
                if res["success"]:
                    console_output.value = res["output"] or "(Code executed successfully with no stdout)"
                    console_output.color = ft.Colors.GREEN_300
                else:
                    console_output.value = f"RUNTIME ERROR:\n{res['error']}"
                    console_output.color = ft.Colors.RED_400

            test_results_col.controls.clear()
            all_passed = True
            for tr in results:
                if not tr["passed"]:
                    all_passed = False
                test_results_col.controls.append(
                    ft.Container(
                        padding=10,
                        border_radius=8,
                        bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.GREEN_600 if tr["passed"] else ft.Colors.RED_500),
                        border=ft.Border.all(1, ft.Colors.GREEN_600 if tr["passed"] else ft.Colors.RED_500),
                        content=ft.Row(
                            [
                                ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED if tr["passed"] else ft.Icons.CANCEL_ROUNDED, color=ft.Colors.GREEN_600 if tr["passed"] else ft.Colors.RED_500, size=18),
                                ft.Text(tr["description"], size=13, weight=ft.FontWeight.W_500, expand=True, color=ft.Colors.ON_SURFACE),
                                ft.Text("PASSED" if tr["passed"] else "FAILED", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_600 if tr["passed"] else ft.Colors.RED_500),
                            ],
                            spacing=10,
                        ),
                    )
                )

            if test_cases:
                if all_passed:
                    status_banner.bgcolor = ft.Colors.with_opacity(0.15, ft.Colors.GREEN_600)
                    status_banner.border = ft.Border.all(1, ft.Colors.GREEN_600)
                    status_banner.content = ft.Row([
                        ft.Icon(ft.Icons.VERIFIED_ROUNDED, color=ft.Colors.GREEN_600, size=20),
                        ft.Text("All verification tests passed successfully! Challenge complete.", weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_600, size=13),
                    ], spacing=8)
                    lesson["is_done"] = True
                    recalculate_locks()
                else:
                    status_banner.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.AMBER_600)
                    status_banner.border = ft.Border.all(1, ft.Colors.AMBER_600)
                    status_banner.content = ft.Row([
                        ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, color=ft.Colors.AMBER_600, size=20),
                        ft.Text("Some test cases failed. Inspect the console output and try again.", weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_600, size=13),
                    ], spacing=8)
                status_banner.visible = True
            else:
                status_banner.visible = False

            page.update()

        def reset_code(e):
            code_input.value = starter_code
            stdin_field.value = ""
            console_output.value = "Code reset to starter template."
            console_output.color = ft.Colors.ON_SURFACE_VARIANT
            test_results_col.controls.clear()
            status_banner.visible = False
            page.update()

        return ft.Container(
            padding=24,
            border_radius=14,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.CODE_ROUNDED, color=ft.Colors.DEEP_PURPLE_400, size=22),
                                    ft.Text("Interactive Code Lab", weight=ft.FontWeight.BOLD, size=16, color=ft.Colors.ON_SURFACE),
                                ],
                                spacing=8,
                            ),
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                                border_radius=6,
                                bgcolor=ft.Colors.with_opacity(0.12, lang_color),
                                content=ft.Text(lang_display, size=11, weight=ft.FontWeight.BOLD, color=lang_color),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Markdown(
                        instructions or "Write your solution in the code editor below:",
                        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                        selectable=True,
                        md_style_sheet=ft.MarkdownStyleSheet(
                            p_text_style=ft.TextStyle(size=14, color=ft.Colors.ON_SURFACE, height=1.5)
                        ),
                    ),
                    code_input,
                    stdin_field,
                    ft.Row(
                        [
                            ft.OutlinedButton("Reset Code", icon=ft.Icons.REFRESH_ROUNDED, on_click=reset_code),
                            ft.FilledButton("Run Code", icon=ft.Icons.PLAY_ARROW_ROUNDED, style=ft.ButtonStyle(bgcolor=ft.Colors.DEEP_PURPLE_400, color=ft.Colors.WHITE), on_click=run_code),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Text("Execution Console Output:", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                    console_container,
                    status_banner,
                    test_results_col,
                ],
                spacing=16,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        )

    def render_lesson_ui(lesson: dict):
        content = lesson.get("content", {})
        blocks = []
        lesson["_page"] = page

        for key, value in content.items():
            if lesson.get("type") == "cloze" and key == "text":
                continue
            if key in ["questions", "scenario", "choices", "prompt_text", "steps", "items", "title", "intro", "prompt", "distractors", "explanation", "starter_code", "solution_code", "setup_sql", "test_cases", "language", "instructions"]:
                continue

            renderer = CONTENT_RENDERERS.get(key)
            if renderer:
                blocks.append(renderer(value, lesson))

        if lesson["type"] == "assessment":
            blocks.append(render_assessment_ui(lesson))
        elif lesson["type"] == "scenario":
            blocks.append(render_scenario_ui(lesson))
        elif lesson["type"] == "stepper":
            blocks.append(render_stepper_ui(lesson))
        elif lesson["type"] == "sequencer":
            blocks.append(render_sequencer_ui(lesson))
        elif lesson["type"] == "cloze":
            blocks.append(render_cloze_ui(lesson))
        elif lesson["type"] == "code_lab":
            blocks.append(render_code_lab_ui(lesson))

        return ft.Column(blocks, spacing=20, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)


    # =========================================================
    # 6. SIDEBAR HELPERS
    # =========================================================

    def build_sidebar_lesson_row(les, m_idx, l_idx, is_active_lesson):
        is_done = les.get("is_done", False)
        is_unlocked = les.get("is_unlocked", False)

        if is_done:
            lesson_icon = ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=15, color=ft.Colors.GREEN_600)
            text_color = UI_ACCENT if is_active_lesson else ft.Colors.ON_SURFACE
        elif not is_unlocked:
            lesson_icon = ft.Icon(ft.Icons.LOCK_OUTLINE_ROUNDED, size=14, color=ft.Colors.with_opacity(0.4, ft.Colors.ON_SURFACE))
            text_color = ft.Colors.with_opacity(0.4, ft.Colors.ON_SURFACE)
        elif is_active_lesson:
            lesson_icon = ft.Icon(ft.Icons.PLAY_CIRCLE_FILL_ROUNDED, size=15, color=UI_ACCENT)
            text_color = UI_ACCENT
        else:
            lesson_icon = ft.Icon(ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED, size=14, color=ft.Colors.with_opacity(0.4, ft.Colors.ON_SURFACE))
            text_color = ft.Colors.ON_SURFACE

        lesson_type = les.get("type", "")
        type_badge = ft.Container(
            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
            border_radius=4,
            bgcolor=ft.Colors.with_opacity(0.08, UI_ACCENT) if is_active_lesson else ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
            content=ft.Row(
                [
                    ft.Icon(get_lesson_type_icon(lesson_type), size=10, color=UI_ACCENT if is_active_lesson else ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text(
                        get_lesson_type_label(lesson_type),
                        size=8.5,
                        weight=ft.FontWeight.BOLD,
                        color=UI_ACCENT if is_active_lesson else ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                tight=True,
                spacing=3,
            ),
        ) if not is_done else ft.Container()

        def handle_click(e):
            if is_unlocked:
                jump_to_lesson(m_idx, l_idx)

        return ft.Container(
            ink=is_unlocked,
            on_click=handle_click if is_unlocked else None,
            bgcolor=ft.Colors.with_opacity(0.08, UI_ACCENT) if is_active_lesson else ft.Colors.TRANSPARENT,
            border=ft.Border.only(
                left=ft.BorderSide(3.5, UI_ACCENT if is_active_lesson else ft.Colors.TRANSPARENT),
                bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE)),
            ),
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Container(
                                width=20,
                                alignment=ft.Alignment.CENTER,
                                content=lesson_icon,
                            ),
                            ft.Text(
                                les["title"],
                                size=12.5,
                                weight=ft.FontWeight.BOLD if is_active_lesson else ft.FontWeight.W_400,
                                color=text_color,
                                expand=True,
                            ),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        [ft.Container(width=28), type_badge],
                        spacing=0,
                    ) if not is_done else ft.Container(),
                ],
                spacing=3,
            ),
        )

    def handle_module_tile_change(e, module_id):
        module_expanded_state[module_id] = e.data == "true"
        page.update()

    def sync_expanded_module_state(active_module_index: int):
        for mod in course_data["modules"]:
            module_expanded_state[mod["id"]] = False
        module_expanded_state[course_data["modules"][active_module_index]["id"]] = True

    # =========================================================
    # 7. NAVIGATION & API LOGIC
    # =========================================================

    async def advance_to_next_lesson():
        nonlocal current_module_idx, current_lesson_idx

        active_mod = course_data["modules"][current_module_idx]
        active_les = active_mod["lessons"][current_lesson_idx]

        # 1. Save Progress & Unlock
        if not active_les.get("is_done", False):
            result = await api_save_progress(course_id, active_les["id"])
            active_les["is_done"] = True
            recalculate_locks()

        is_last_lesson = current_lesson_idx >= len(active_mod["lessons"]) - 1

        if is_last_lesson:
            if await api_verify_module_completion(active_mod["id"]):
                active_mod["is_done"] = True

                if current_module_idx >= len(course_data["modules"]) - 1:
                    # ============================================================
                    # COMPLETION OVERLAY — Certificate generation + display
                    # ============================================================
                    token = await page.shared_preferences.get("auth_token")

                    cert_loading_indicator = ft.Container(
                        padding=ft.Padding.symmetric(vertical=14, horizontal=16),
                        border_radius=12,
                        bgcolor=ft.Colors.with_opacity(0.04, UI_ACCENT),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.12, UI_ACCENT)),
                        content=ft.Row(
                            [
                                ft.ProgressRing(width=22, height=22, color=UI_ACCENT, stroke_width=2.5),
                                ft.Column(
                                    [
                                        ft.Text("Generating Verified Certificate...", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                                        ft.Text("Minting your cryptographic credential...", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ],
                                    spacing=2,
                                    expand=True,
                                ),
                            ],
                            spacing=12,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    )

                    cert_action_container = ft.Container(
                        content=cert_loading_indicator,
                        padding=ft.Padding.symmetric(vertical=4),
                    )

                    rating_stars = ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=6)
                    rating_descriptor = ft.Text("Tap a star to rate", size=12, color=ft.Colors.ON_SURFACE_VARIANT, italic=True)

                    for i in range(1, 6):
                        rating_stars.controls.append(
                            ft.IconButton(
                                icon=ft.Icons.STAR_BORDER_ROUNDED,
                                icon_color=ft.Colors.AMBER_400,
                                icon_size=26,
                                data=i,
                                tooltip=f"{i} Star{'s' if i > 1 else ''}",
                                on_click=lambda e: page.run_task(submit_rating, e.control.data),
                            )
                        )

                    rating_content_column = ft.Column(
                        [
                            ft.Text("How was your learning experience?", size=13.5, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE, text_align=ft.TextAlign.CENTER),
                            rating_stars,
                            rating_descriptor,
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        tight=True,
                        spacing=6,
                    )

                    rating_action_container = ft.Container(
                        padding=16,
                        border_radius=12,
                        bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                        content=rating_content_column,
                    )

                    def reset_rating_stars(e=None):
                        for star in rating_stars.controls:
                            star.disabled = False
                            star.icon = ft.Icons.STAR_BORDER_ROUNDED
                            star.icon_color = ft.Colors.AMBER_400
                        rating_descriptor.value = "Tap a star to rate"
                        rating_descriptor.italic = True
                        rating_descriptor.weight = ft.FontWeight.NORMAL
                        rating_action_container.content = rating_content_column
                        page.update()
                    
                    async def submit_rating(rating_val):
                        for idx, star in enumerate(rating_stars.controls):
                            star.disabled = True
                            if idx < rating_val:
                                star.icon = ft.Icons.STAR_ROUNDED
                                star.icon_color = ft.Colors.AMBER_400
                            else:
                                star.icon = ft.Icons.STAR_BORDER_ROUNDED
                                star.icon_color = ft.Colors.with_opacity(0.25, ft.Colors.ON_SURFACE)
                        descriptors = {
                            1: "1/5 · Needs Improvement",
                            2: "2/5 · Fair",
                            3: "3/5 · Good",
                            4: "4/5 · Very Good",
                            5: "5/5 · Outstanding!",
                        }
                        rating_descriptor.value = descriptors.get(rating_val, f"{rating_val}/5 stars")
                        rating_descriptor.italic = False
                        rating_descriptor.weight = ft.FontWeight.BOLD
                        page.update()
                        
                        res = await rate_course(token, course_id, float(rating_val))
                        if "error" not in res:
                            rating_action_container.content = ft.Container(
                                padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                                border_radius=10,
                                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.GREEN_600),
                                border=ft.Border.all(1, ft.Colors.with_opacity(0.18, ft.Colors.GREEN_600)),
                                content=ft.Row(
                                    [
                                        ft.Icon(ft.Icons.FAVORITE_ROUNDED, color=ft.Colors.PINK_400, size=20),
                                        ft.Column(
                                            [
                                                ft.Text("Thank you for your rating!", color=ft.Colors.GREEN_700, size=13, weight=ft.FontWeight.BOLD),
                                                ft.Text("Your feedback helps us continuously improve the course curriculum.", color=ft.Colors.ON_SURFACE_VARIANT, size=11),
                                            ],
                                            spacing=2,
                                            expand=True,
                                        ),
                                    ],
                                    spacing=10,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                            )
                        else:
                            err_msg = res.get("error", "Failed to submit rating. Please try again.")
                            print(f"[Rating] Failed to rate course {course_id}: {res}")
                            rating_action_container.content = ft.Container(
                                padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                                border_radius=10,
                                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.RED_600),
                                border=ft.Border.all(1, ft.Colors.with_opacity(0.18, ft.Colors.RED_600)),
                                content=ft.Column(
                                    [
                                        ft.Text(f"Rating submission failed: {err_msg}", color=ft.Colors.RED_700, size=12, weight=ft.FontWeight.W_500, text_align=ft.TextAlign.CENTER),
                                        ft.TextButton(
                                            "Tap to try again",
                                            on_click=reset_rating_stars,
                                            style=ft.ButtonStyle(color=ft.Colors.RED_700),
                                        ),
                                    ],
                                    spacing=4,
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                    tight=True,
                                ),
                            )
                        page.update()

                    def close_dialog_and_go(e=None):
                        page.pop_dialog()
                        page.go(back_target)

                    is_offline = back_target == "/offline"

                    def close_dialog_and_go_stats(e=None):
                        page.pop_dialog()
                        page.go(f"/courses/{course_id}/stats")

                    if not is_offline:
                        stats_action_container = ft.FilledButton(
                            content=ft.Row(
                                [
                                    ft.Icon(ft.Icons.QUERY_STATS_ROUNDED, size=16, color=ft.Colors.SURFACE),
                                    ft.Text("View My Course Stats", weight=ft.FontWeight.BOLD, size=13, color=ft.Colors.SURFACE),
                                ],
                                tight=True,
                                spacing=8,
                                alignment=ft.MainAxisAlignment.CENTER,
                            ),
                            style=ft.ButtonStyle(
                                bgcolor=UI_ACCENT,
                                shape=ft.RoundedRectangleBorder(radius=8),
                                padding=ft.Padding.symmetric(horizontal=20, vertical=12),
                                elevation=0,
                            ),
                            on_click=close_dialog_and_go_stats,
                        )
                    else:
                        stats_action_container = ft.Container() # Omitted offline

                    dialog = ft.AlertDialog(
                        modal=True,
                        shape=ft.RoundedRectangleBorder(radius=20),
                        content_padding=0,
                        bgcolor=ft.Colors.TRANSPARENT,
                        content=ft.Container(
                            width=480,
                            height=620,
                            bgcolor=ft.Colors.SURFACE,
                            border_radius=20,
                            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                            content=ft.Column(
                                [
                                    ft.Container(
                                        width=480,
                                        alignment=ft.Alignment.CENTER,
                                        padding=ft.Padding.symmetric(horizontal=24, vertical=20),
                                        border_radius=ft.BorderRadius.only(top_left=20, top_right=20),
                                        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                                        gradient=ft.LinearGradient(
                                            begin=ft.Alignment.TOP_LEFT,
                                            end=ft.Alignment.BOTTOM_RIGHT,
                                            colors=[ft.Colors.AMBER_600, ft.Colors.ORANGE_600, ft.Colors.DEEP_ORANGE_500],
                                        ),
                                        content=ft.Column(
                                            [
                                                ft.Container(
                                                    bgcolor=ft.Colors.with_opacity(0.22, ft.Colors.SURFACE),
                                                    border_radius=50,
                                                    padding=12,
                                                    alignment=ft.Alignment.CENTER,
                                                    width=64,
                                                    height=64,
                                                    content=ft.Icon(ft.Icons.WORKSPACE_PREMIUM_ROUNDED, size=36, color=ft.Colors.SURFACE),
                                                ),
                                                ft.Container(
                                                    padding=ft.Padding.symmetric(horizontal=10, vertical=3),
                                                    border_radius=999,
                                                    bgcolor=ft.Colors.with_opacity(0.20, ft.Colors.SURFACE),
                                                    content=ft.Text("🎉 100% COMPLETED · CURRICULUM MASTERED", size=9.5, weight=ft.FontWeight.BOLD, color=ft.Colors.SURFACE),
                                                ),
                                                ft.Text("Congratulations!", size=22, weight=ft.FontWeight.W_900, color=ft.Colors.SURFACE, text_align=ft.TextAlign.CENTER),
                                                ft.Text(f"You've completed {course_data.get('course_title', 'the course')}!", size=13, color=ft.Colors.with_opacity(0.90, ft.Colors.SURFACE), text_align=ft.TextAlign.CENTER),
                                            ],
                                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                            tight=True,
                                            spacing=6,
                                        ),
                                    ),
                                    ft.Container(
                                        padding=ft.Padding.symmetric(horizontal=20, vertical=12),
                                        expand=True,
                                        content=ft.Column(
                                            (
                                                [
                                                    cert_action_container,
                                                    ft.Divider(height=12, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                                                    rating_action_container,
                                                ]
                                                if course_data.get('auto_certificate', True) else 
                                                [
                                                    rating_action_container,
                                                ]
                                            ),
                                            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                                            scroll=ft.ScrollMode.AUTO,
                                            spacing=12,
                                        ),
                                    ),
                                    ft.Container(
                                        padding=ft.Padding.symmetric(horizontal=20, vertical=14),
                                        border=ft.Border.only(top=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE))),
                                        content=ft.Column(
                                            [
                                                stats_action_container,
                                                ft.OutlinedButton(
                                                    "Return to Courses" if back_target == "/courses" else "Return to Dashboard",
                                                    icon=ft.Icons.ARROW_BACK_ROUNDED,
                                                    style=ft.ButtonStyle(
                                                        shape=ft.RoundedRectangleBorder(radius=8),
                                                        padding=ft.Padding.symmetric(horizontal=18, vertical=10),
                                                        side=ft.BorderSide(1, ft.Colors.with_opacity(0.16, ft.Colors.ON_SURFACE)),
                                                    ),
                                                    on_click=close_dialog_and_go,
                                                ),
                                            ],
                                            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                                            spacing=8,
                                            tight=True,
                                        ),
                                    ),
                                ],
                                spacing=0,
                                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                            ),
                        ),
                    )

                    # 1. Version-safe dialog mounting
                    if hasattr(page, "open"): 
                        page.open(dialog)
                    else: 
                        page.overlay.append(dialog)
                        dialog.open = True
                        page.update()

                    # 2. Recursive retry function
                    async def attempt_cert_generation(e=None):
                        await asyncio.sleep(0.1)
                        
                        if not dialog.open: return

                        cert_action_container.content = cert_loading_indicator
                        if cert_action_container.page: cert_action_container.update()

                        res = await generate_course_certificate(token, course_id)
                        
                        if not dialog.open: return
                        
                        if "error" in res:
                            cert_action_container.content = ft.Container(
                                padding=ft.Padding.symmetric(vertical=10, horizontal=14),
                                border_radius=10,
                                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.RED_600),
                                border=ft.Border.all(1, ft.Colors.with_opacity(0.18, ft.Colors.RED_600)),
                                content=ft.Column(
                                    spacing=8, 
                                    controls=[
                                        ft.Row([
                                            ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, color=ft.Colors.RED_600, size=18),
                                            ft.Text("Could not generate certificate. Please try again.", color=ft.Colors.RED_700, size=12.5, expand=True),
                                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                                        ft.OutlinedButton(
                                            content="Retry Certificate Generation",
                                            style=ft.ButtonStyle(
                                                shape=ft.RoundedRectangleBorder(radius=8),
                                                side=ft.BorderSide(1, ft.Colors.RED_400),
                                            ),
                                            on_click=lambda e: page.run_task(attempt_cert_generation),
                                        ),
                                    ],
                                ),
                            )
                            if cert_action_container.page: cert_action_container.update()
                        else:
                            cert_url = res.get("url", "")
                            cred_id = res.get("credential_id", "")

                            async def handle_cert_download(e):
                                if cert_url: await page.launch_url(cert_url)

                            cert_action_container.content = ft.Container(
                                padding=14,
                                border_radius=12,
                                bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.GREEN_600),
                                border=ft.Border.all(1, ft.Colors.with_opacity(0.20, ft.Colors.GREEN_600)),
                                content=ft.Column(
                                    [
                                        ft.Row(
                                            [
                                                ft.Icon(ft.Icons.WORKSPACE_PREMIUM_ROUNDED, color=ft.Colors.AMBER_500, size=22),
                                                ft.Text("Official Certificate of Completion", weight=ft.FontWeight.BOLD, size=13.5, color=ft.Colors.ON_SURFACE, expand=True),
                                                ft.Container(
                                                    padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                                                    border_radius=999,
                                                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.GREEN_600),
                                                    content=ft.Text("VERIFIED", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_600),
                                                ),
                                            ],
                                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                            spacing=8,
                                        ),
                                        ft.Container(
                                            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                                            border_radius=6,
                                            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
                                            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                                            content=ft.Row(
                                                [
                                                    ft.Icon(ft.Icons.FINGERPRINT_ROUNDED, size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                                                    ft.Text("Credential ID: ", size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
                                                    ft.Text(str(cred_id), size=11, color=ft.Colors.ON_SURFACE, weight=ft.FontWeight.BOLD, selectable=True),
                                                ],
                                                spacing=4,
                                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                                wrap=True,
                                            ),
                                        ),
                                        ft.FilledButton(
                                            content=ft.Row(
                                                [
                                                    ft.Icon(ft.Icons.DOWNLOAD_ROUNDED, color=ft.Colors.SURFACE, size=18),
                                                    ft.Text("Download Certificate", color=ft.Colors.SURFACE, weight=ft.FontWeight.BOLD, size=13),
                                                ],
                                                tight=True,
                                                spacing=8,
                                                alignment=ft.MainAxisAlignment.CENTER,
                                            ),
                                            style=ft.ButtonStyle(
                                                bgcolor=UI_ACCENT,
                                                shape=ft.RoundedRectangleBorder(radius=8),
                                                padding=ft.Padding.symmetric(horizontal=18, vertical=10),
                                                elevation=0,
                                            ),
                                            on_click=handle_cert_download,
                                            expand=True,
                                        ),
                                    ],
                                    spacing=10,
                                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                                ),
                            )
                            if cert_action_container.page: cert_action_container.update()

                    # 3. Kick off the generation
                    if course_data.get('auto_certificate', True):
                        page.run_task(attempt_cert_generation)
                    return


                else:
                    current_module_idx += 1
                    current_lesson_idx = 0
        else:
            current_lesson_idx += 1

        sync_expanded_module_state(current_module_idx)
        refresh_ui()

    async def go_to_previous_lesson():
        nonlocal current_module_idx, current_lesson_idx

        is_first_overall = current_module_idx == 0 and current_lesson_idx == 0
        if is_first_overall:
            return

        if current_lesson_idx > 0:
            current_lesson_idx -= 1
        else:
            current_module_idx -= 1
            previous_module = course_data["modules"][current_module_idx]
            current_lesson_idx = len(previous_module["lessons"]) - 1

        sync_expanded_module_state(current_module_idx)
        refresh_ui()

    def handle_assessment_success(result_data, dialog):
        dialog.open = False
        page.update()
        page.run_task(advance_to_next_lesson)

    def jump_to_lesson(m_idx, l_idx):
        nonlocal current_module_idx, current_lesson_idx, sidebar_visible

        current_module_idx = m_idx
        current_lesson_idx = l_idx
        sync_expanded_module_state(m_idx)

        if not is_desktop_layout():
            sidebar_visible = False

        refresh_ui()

    # =========================================================
    # 8. UI REFRESH & ASSEMBLY
    # =========================================================

    previous_button = ft.Button(
        bgcolor=ft.Colors.TRANSPARENT,
        color=ft.Colors.ON_SURFACE,
        height=ACTION_BUTTON_HEIGHT,
        expand=True,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=8),
            side=ft.BorderSide(1, ft.Colors.with_opacity(0.16, ft.Colors.ON_SURFACE)),
            elevation=0,
        ),
        visible=False,
    )

    action_button = ft.Button(
        bgcolor=UI_ACCENT,
        color=ft.Colors.SURFACE,
        height=ACTION_BUTTON_HEIGHT,
        expand=True,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=8),
            elevation=0,
        ),
    )

    def refresh_ui():
        sidebar_column.controls.clear()
        refresh_progress_header()

        # ---------- Sidebar ----------
        for m_idx, mod in enumerate(course_data["modules"]):
            is_active_module = m_idx == current_module_idx

            lesson_controls = []
            for l_idx, les in enumerate(mod.get("lessons", [])):
                is_active_lesson = is_active_module and (l_idx == current_lesson_idx)
                lesson_controls.append(build_sidebar_lesson_row(les, m_idx, l_idx, is_active_lesson))

            mod_done = mod.get("is_done", False)
            mod_lessons = mod.get("lessons", [])
            completed_in_mod = sum(1 for les in mod_lessons if les.get("is_done", False))
            total_in_mod = len(mod_lessons)

            module_title_row = ft.Row(
                [
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(
                                        f"MODULE {m_idx + 1}".upper(),
                                        size=9.5,
                                        weight=ft.FontWeight.BOLD,
                                        color=UI_ACCENT if is_active_module else ft.Colors.ON_SURFACE_VARIANT,
                                    ),
                                    ft.Text("·", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ft.Text(
                                        f"{completed_in_mod}/{total_in_mod}",
                                        size=9.5,
                                        weight=ft.FontWeight.W_600,
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                    ),
                                ],
                                spacing=4,
                            ),
                            ft.Text(
                                mod["title"],
                                weight=ft.FontWeight.BOLD if is_active_module else ft.FontWeight.W_600,
                                size=12.5,
                                color=ft.Colors.ON_SURFACE,
                                max_lines=2,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=15, color=ft.Colors.GREEN_600) if mod_done else ft.Container(),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

            sidebar_column.controls.append(
                ft.ExpansionTile(
                    title=module_title_row,
                    expanded=module_expanded_state.get(mod["id"], False),
                    on_change=lambda e, module_id=mod["id"]: handle_module_tile_change(e, module_id),
                    maintain_state=True,
                    tile_padding=ft.Padding.symmetric(horizontal=14, vertical=6),
                    controls_padding=ft.Padding.only(left=0, right=0, bottom=0),
                    collapsed_bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                    collapsed_text_color=ft.Colors.ON_SURFACE,
                    text_color=ft.Colors.ON_SURFACE,
                    collapsed_icon_color=ft.Colors.ON_SURFACE_VARIANT,
                    icon_color=ft.Colors.ON_SURFACE_VARIANT,
                    shape=ft.RoundedRectangleBorder(radius=0),
                    collapsed_shape=ft.RoundedRectangleBorder(radius=0),
                    controls=[
                        ft.Container(
                            bgcolor=ft.Colors.SURFACE,
                            content=ft.Column(lesson_controls, spacing=0),
                        )
                    ],
                )
            )

        # ---------- Main Content ----------
        active_mod = course_data["modules"][current_module_idx]
        active_les = active_mod["lessons"][current_lesson_idx]

        is_first_overall = current_module_idx == 0 and current_lesson_idx == 0
        is_last_overall = (
            current_module_idx == len(course_data["modules"]) - 1
            and current_lesson_idx == len(active_mod["lessons"]) - 1
        )

        is_completed = active_les.get("is_done", False)

        # =========================================================
        # 1. SNAPSHOT INDICES TO DETECT QUEUED SPAM-CLICKS
        # =========================================================
        captured_module_idx = current_module_idx
        captured_lesson_idx = current_lesson_idx

        if active_les["type"] == "assessment":
            if is_completed:
                next_btn_text = "Assessment Completed ✓"
                action_button.bgcolor = ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)
                action_button.color = ft.Colors.ON_SURFACE_VARIANT
                action_button.disabled = True
            else:
                next_btn_text = "Submit & Finish Course" if is_last_overall else "Submit Assessment"
                action_button.bgcolor = UI_ACCENT
                action_button.color = ft.Colors.SURFACE
                action_button.disabled = False
        else:
            next_btn_text = "Finish Course" if is_last_overall else "Next Lesson"
            action_button.bgcolor = UI_ACCENT
            action_button.color = ft.Colors.SURFACE
            action_button.disabled = False

        previous_button.content = ft.Row(
            [ft.Icon(ft.Icons.ARROW_BACK_ROUNDED, size=15, color=ft.Colors.ON_SURFACE), ft.Text("Previous", weight=ft.FontWeight.BOLD, size=13)],
            tight=True, spacing=6, alignment=ft.MainAxisAlignment.CENTER,
        )
        previous_button.visible = not is_first_overall
        previous_button.disabled = False
        
        action_button.content = ft.Row(
            [ft.Text(next_btn_text, weight=ft.FontWeight.BOLD, size=13), ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=15, color=ft.Colors.SURFACE if not (active_les["type"] == "assessment" and is_completed) else ft.Colors.ON_SURFACE_VARIANT)],
            tight=True, spacing=6, alignment=ft.MainAxisAlignment.CENTER,
        ) if not (active_les["type"] == "assessment" and is_completed) else ft.Text(next_btn_text, weight=ft.FontWeight.BOLD, size=13)

        # =========================================================
        # 2. ROBUST STALE-CLOSURE & DOUBLE-TAP GUARDS
        # =========================================================
        spinner = ft.ProgressRing(width=16, height=16, stroke_width=2, color="WHITE")
        async def on_previous_click(e):
            if captured_module_idx != current_module_idx or captured_lesson_idx != current_lesson_idx:
                return
            if previous_button.disabled: return

            previous_button.disabled = True
            action_button.disabled = True
            page.update()
            await go_to_previous_lesson()

        async def on_action_click(e):
            action_button.content=spinner
            if captured_module_idx != current_module_idx or captured_lesson_idx != current_lesson_idx:
                return
            if action_button.disabled: return

            action_button.disabled = True
            previous_button.disabled = True
            page.update()

            if active_les["type"] == "assessment":
                payload = {}
                is_incomplete = False

                for q_key, state_data in current_assessment_state.items():
                    if state_data["type"] == "single":
                        ans = state_data["controls"].value
                        if ans is None:
                            is_incomplete = True
                        payload[q_key] = ans
                    else:
                        selected_answers = [cb.data for cb in state_data["controls"] if cb.value]
                        if len(selected_answers) == 0:
                            is_incomplete = True
                        payload[q_key] = selected_answers

                if is_incomplete:
                    action_button.content = ft.Text(next_btn_text, weight=ft.FontWeight.BOLD, size=14)
                    snack = ft.SnackBar(
                        content=ft.Text("Please answer all questions before submitting!"),
                        bgcolor=ft.Colors.ERROR,
                    )
                    page.overlay.append(snack)
                    snack.open = True
                    action_button.disabled = False
                    previous_button.disabled = False
                    page.update()
                    return
                
                action_button.content = ft.Text(next_btn_text, weight=ft.FontWeight.BOLD, size=14)
                questions = active_les.get("content", {}).get("questions", [])
                total_q = len(questions)
                correct_count = 0
                results_breakdown = []

                for q_idx, q in enumerate(questions):
                    q_key = f"question_{q_idx + 1}"
                    user_answer = payload.get(q_key)
                    correct_opts = [opt.get("text") for opt in q.get("options", []) if opt.get("is_correct")]

                    if isinstance(user_answer, list):
                        is_correct = set(user_answer) == set(correct_opts)
                        user_ans_str = ", ".join(user_answer)
                    else:
                        is_correct = user_answer in correct_opts and len(correct_opts) == 1
                        user_ans_str = str(user_answer)

                    correct_ans_str = ", ".join(correct_opts) if correct_opts else "N/A"

                    if is_correct:
                        correct_count += 1

                    results_breakdown.append(
                        {
                            "question": q.get("text", f"Question {q_idx + 1}"),
                            "user_answer": user_ans_str,
                            "correct_answer": correct_ans_str,
                            "is_correct": is_correct,
                        }
                    )

                score_percentage = int((correct_count / total_q) * 100) if total_q > 0 else 0
                passed = score_percentage >= 70
                incorrect_count = total_q - correct_count

                banner_gradient = (
                    [ft.Colors.GREEN_700, ft.Colors.TEAL_700]
                    if passed
                    else [ft.Colors.DEEP_ORANGE_600, ft.Colors.AMBER_800]
                )
                header_icon = ft.Icons.EMOJI_EVENTS_ROUNDED if passed else ft.Icons.AUTO_FIX_HIGH_ROUNDED
                status_chip_text = "PASSED · MASTERY ACHIEVED" if passed else "NEEDS REVIEW · PASSING IS 70%"
                headline_text = "Assessment Passed!" if passed else "Assessment Incomplete"
                subtitle_text = (
                    "Outstanding work! You have successfully mastered this material."
                    if passed
                    else "You didn't reach the passing threshold this time. Review below and try again!"
                )

                chart_sections = []
                if correct_count > 0:
                    chart_sections.append(fch.PieChartSection(value=correct_count, color=ft.Colors.GREEN_500, radius=20, title=" "))
                if incorrect_count > 0:
                    chart_sections.append(fch.PieChartSection(value=incorrect_count, color=ft.Colors.RED_400, radius=20, title=" "))

                stat_box_score = ft.Container(
                    expand=True,
                    padding=ft.Padding.symmetric(vertical=10, horizontal=8),
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    content=ft.Column(
                        [
                            ft.Text("SCORE", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(f"{score_percentage}%", size=18, weight=ft.FontWeight.W_900, color=ft.Colors.GREEN_600 if passed else ft.Colors.RED_500),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=2,
                    ),
                )
                stat_box_correct = ft.Container(
                    expand=True,
                    padding=ft.Padding.symmetric(vertical=10, horizontal=8),
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    content=ft.Column(
                        [
                            ft.Text("CORRECT", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(f"{correct_count}/{total_q}", size=18, weight=ft.FontWeight.W_900, color=ft.Colors.ON_SURFACE),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=2,
                    ),
                )
                stat_box_target = ft.Container(
                    expand=True,
                    padding=ft.Padding.symmetric(vertical=10, horizontal=8),
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    content=ft.Column(
                        [
                            ft.Text("PASSING", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text("70%", size=18, weight=ft.FontWeight.W_900, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=2,
                    ),
                )

                analytics_chart_ui = ft.Container(
                    padding=ft.Padding.symmetric(vertical=10),
                    content=ft.Column(
                        [
                            ft.Row([stat_box_score, stat_box_correct, stat_box_target], spacing=10),
                            ft.Container(height=4),
                            ft.Row(
                                [
                                    ft.Container(
                                        width=64, height=64,
                                        content=fch.PieChart(sections=chart_sections, sections_space=2, center_space_radius=22),
                                    ),
                                    ft.Column(
                                        [
                                            ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=13, color=ft.Colors.GREEN_500), ft.Text(f"{correct_count} correct answers", size=12.5, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE)]),
                                            ft.Row([ft.Icon(ft.Icons.CANCEL_ROUNDED, size=13, color=ft.Colors.RED_400), ft.Text(f"{incorrect_count} incorrect answers", size=12.5, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE)]),
                                        ],
                                        spacing=6,
                                        alignment=ft.MainAxisAlignment.CENTER,
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.CENTER,
                                spacing=20,
                            ),
                        ],
                        spacing=10,
                    ),
                )

                breakdown_controls = []
                for q_idx, res in enumerate(results_breakdown):
                    is_correct = res["is_correct"]
                    card_tint = ft.Colors.GREEN_600 if is_correct else ft.Colors.RED_500

                    user_ans_row = ft.Row(
                        [
                            ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED if is_correct else ft.Icons.CANCEL_ROUNDED, color=card_tint, size=15),
                            ft.Text(f"Your answer: {res['user_answer']}", color=card_tint, size=12.5, weight=ft.FontWeight.W_600, expand=True),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.START,
                        spacing=6,
                    )

                    correct_ans_row = ft.Container()
                    if not is_correct:
                        correct_ans_row = ft.Row(
                            [
                                ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=15, color=ft.Colors.GREEN_600),
                                ft.Text(f"Correct: {res['correct_answer']}", color=ft.Colors.GREEN_700, size=12.5, weight=ft.FontWeight.BOLD, expand=True),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.START,
                            spacing=6,
                        )

                    breakdown_controls.append(
                        ft.Container(
                            padding=14,
                            border_radius=10,
                            bgcolor=ft.Colors.with_opacity(0.04, card_tint),
                            border=ft.Border.all(1, ft.Colors.with_opacity(0.16, card_tint)),
                            content=ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Container(
                                                padding=ft.Padding.symmetric(horizontal=7, vertical=2),
                                                border_radius=4,
                                                bgcolor=ft.Colors.with_opacity(0.12, card_tint),
                                                content=ft.Text(f"Q{q_idx + 1}", size=10, weight=ft.FontWeight.BOLD, color=card_tint),
                                            ),
                                            ft.Container(
                                                padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                                                border_radius=999,
                                                bgcolor=ft.Colors.with_opacity(0.10, card_tint),
                                                content=ft.Text("CORRECT" if is_correct else "INCORRECT", size=9, weight=ft.FontWeight.BOLD, color=card_tint),
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                    ft.Text(res["question"], weight=ft.FontWeight.BOLD, size=13, color=ft.Colors.ON_SURFACE),
                                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
                                    user_ans_row,
                                    correct_ans_row,
                                ],
                                spacing=6,
                            ),
                        )
                    )

                def close_and_retry(e):
                    if e.control.disabled: return
                    e.control.disabled = True
                    result_dialog.open = False
                    action_button.disabled = False
                    previous_button.disabled = False
                    page.update()

                def close_and_continue(e):
                    if e.control.disabled: return
                    e.control.disabled = True
                    result_dialog.open = False
                    page.update()
                    page.run_task(advance_to_next_lesson)

                result_dialog = ft.AlertDialog(
                    modal=True,
                    shape=ft.RoundedRectangleBorder(radius=20),
                    content_padding=0,
                    bgcolor=ft.Colors.TRANSPARENT,
                    content=ft.Container(
                        width=480, height=660, bgcolor=ft.Colors.SURFACE, border_radius=20,
                        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                        content=ft.Column(
                            [
                                ft.Container(
                                    width=480,
                                    alignment=ft.Alignment.CENTER,
                                    padding=ft.Padding.symmetric(horizontal=24, vertical=22),
                                    border_radius=ft.BorderRadius.only(top_left=20, top_right=20),
                                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                                    gradient=ft.LinearGradient(
                                        begin=ft.Alignment.TOP_LEFT,
                                        end=ft.Alignment.BOTTOM_RIGHT,
                                        colors=banner_gradient,
                                    ),
                                    content=ft.Column(
                                        [
                                            ft.Container(
                                                bgcolor=ft.Colors.with_opacity(0.22, ft.Colors.SURFACE),
                                                border_radius=50,
                                                padding=12,
                                                alignment=ft.Alignment.CENTER,
                                                width=64,
                                                height=64,
                                                content=ft.Icon(header_icon, size=36, color=ft.Colors.SURFACE),
                                            ),
                                            ft.Container(
                                                padding=ft.Padding.symmetric(horizontal=10, vertical=3),
                                                border_radius=999,
                                                bgcolor=ft.Colors.with_opacity(0.20, ft.Colors.SURFACE),
                                                content=ft.Text(status_chip_text, size=9.5, weight=ft.FontWeight.BOLD, color=ft.Colors.SURFACE),
                                            ),
                                            ft.Text(headline_text, size=22, weight=ft.FontWeight.W_900, color=ft.Colors.SURFACE, text_align=ft.TextAlign.CENTER),
                                            ft.Text(subtitle_text, size=12.5, color=ft.Colors.with_opacity(0.90, ft.Colors.SURFACE), text_align=ft.TextAlign.CENTER),
                                        ],
                                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                        tight=True,
                                        spacing=6,
                                    ),
                                ),
                                ft.Container(
                                    padding=ft.Padding.symmetric(horizontal=20),
                                    expand=True,
                                    content=ft.Column(
                                        controls=[
                                            analytics_chart_ui,
                                            ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                                            ft.Row(
                                                [
                                                    ft.Icon(ft.Icons.RULE_ROUNDED, size=16, color=UI_ACCENT),
                                                    ft.Text("Detailed Question Review", weight=ft.FontWeight.BOLD, size=14, color=ft.Colors.ON_SURFACE),
                                                ],
                                                spacing=6,
                                            ),
                                        ] + breakdown_controls + [ft.Container(height=10)],
                                        scroll=ft.ScrollMode.AUTO,
                                        spacing=10,
                                    ),
                                ),
                                ft.Container(
                                    width=480,
                                    padding=ft.Padding.symmetric(horizontal=20, vertical=14),
                                    border=ft.Border.only(top=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE))),
                                    content=ft.Row(
                                        [
                                            ft.OutlinedButton(
                                                "Dismiss",
                                                icon=ft.Icons.CLOSE_ROUNDED,
                                                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), padding=ft.Padding.symmetric(horizontal=16, vertical=10)),
                                                on_click=close_and_retry,
                                            ) if not passed else ft.Container(),
                                            ft.FilledButton(
                                                "Retry Assessment",
                                                icon=ft.Icons.REPLAY_ROUNDED,
                                                style=ft.ButtonStyle(
                                                    bgcolor=UI_ACCENT,
                                                    shape=ft.RoundedRectangleBorder(radius=8),
                                                    padding=ft.Padding.symmetric(horizontal=18, vertical=10),
                                                ),
                                                on_click=close_and_retry,
                                            ) if not passed else ft.FilledButton(
                                                "Continue Course",
                                                icon=ft.Icons.ARROW_FORWARD_ROUNDED,
                                                style=ft.ButtonStyle(
                                                    bgcolor=UI_ACCENT,
                                                    color=ft.Colors.SURFACE,
                                                    shape=ft.RoundedRectangleBorder(radius=8),
                                                    padding=ft.Padding.symmetric(horizontal=22, vertical=10),
                                                ),
                                                on_click=close_and_continue,
                                                expand=True,
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.END if passed else ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                ),
                            ],
                            spacing=0,
                            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                        ),
                    ),
                )

                if hasattr(page, "open"):
                    page.open(result_dialog)
                else:
                    page.overlay.append(result_dialog)
                    result_dialog.open = True
                    page.update()

            else:
                await advance_to_next_lesson()

        previous_button.on_click = on_previous_click
        action_button.on_click = on_action_click

        # ---- Lesson Header ----
        lesson_number = current_lesson_idx + 1
        total_lessons = len(active_mod["lessons"])
        mod_progress_val = (lesson_number - 1) / max(total_lessons - 1, 1)

        appbar_lesson_subtitle.value = f"Module {current_module_idx + 1} · {active_les.get('title', '')}"

        header_container = ft.Container(
            padding=ft.Padding.symmetric(horizontal=20, vertical=16),
            border_radius=HEADER_RADIUS,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(
                                f"MODULE {current_module_idx + 1}: {active_mod['title']}".upper(),
                                size=11,
                                weight=ft.FontWeight.BOLD,
                                color=UI_ACCENT,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            ft.Text("·", color=ft.Colors.ON_SURFACE_VARIANT, size=11),
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                border_radius=999,
                                bgcolor=ft.Colors.with_opacity(0.08, UI_ACCENT),
                                content=ft.Row(
                                    [
                                        ft.Icon(get_lesson_type_icon(active_les["type"]), size=11, color=UI_ACCENT),
                                        ft.Text(get_lesson_type_label(active_les["type"]), size=9.5, weight=ft.FontWeight.BOLD, color=UI_ACCENT),
                                    ],
                                    spacing=4,
                                    tight=True,
                                ),
                            ),
                            ft.Text(
                                f"Lesson {lesson_number} of {total_lessons}",
                                size=11,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                weight=ft.FontWeight.W_500,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.START,
                        spacing=6,
                        wrap=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Text(
                        active_les["title"],
                        size=22,
                        weight=ft.FontWeight.W_800,
                        color=ft.Colors.ON_SURFACE,
                        text_align=ft.TextAlign.LEFT,
                    ),
                    ft.Container(
                        content=ft.ProgressBar(
                            value=mod_progress_val,
                            color=UI_ACCENT,
                            bgcolor=ft.Colors.with_opacity(0.10, UI_ACCENT),
                            height=3.5,
                            border_radius=2,
                        ),
                    ),
                ],
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.START,
            ),
        )

        lesson_body_scroll.content = ft.Column(
            [
                header_container,
                ft.Container(height=14),
                render_lesson_ui(active_les),
                ft.Container(height=24),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

        is_assessment = active_les["type"] == "assessment"
        action_footer_controls = []

        if is_assessment:
            action_footer_controls.append(ft.Row([action_button], spacing=0))
        else:
            if not is_first_overall:
                action_footer_controls.append(
                    ft.Row(
                        [
                            previous_button,
                            ft.Container(width=12),
                            action_button,
                        ],
                        spacing=0,
                    )
                )
            else:
                action_footer_controls.append(ft.Row([action_button], spacing=0))

        action_footer_container.content = ft.Container(
            padding=ft.Padding.symmetric(vertical=12),
            border=ft.Border.only(
                top=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE))
            ),
            content=ft.Column(
                action_footer_controls,
                spacing=8,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        )

        main_content_area.content = ft.Container(
            width=980 if is_desktop_layout() else None,
            expand=True,
            content=ft.Column(
                [lesson_body_scroll, action_footer_container],
                expand=True,
                spacing=0,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        )

        refresh_layout_shell()
        page.update()
    # =========================================================
    # 9. ASYNC BACKGROUND DATA FETCHER
    # =========================================================

    async def fetch_initial_data():
        nonlocal course_data, current_module_idx, current_lesson_idx, module_expanded_state, token
        token = await page.shared_preferences.get("auth_token")

        course_data = await api_fetch_course_data(course_id)

        if not course_data or "modules" not in course_data:
            content_socket.alignment = ft.Alignment.CENTER
            content_socket.content = ft.Column(
                [
                    ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, size=40, color=ft.Colors.ERROR),
                    ft.Text(
                        "Failed to load course data.",
                        color=ft.Colors.ERROR,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Text(
                        "Please go back and try again.",
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        size=13,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
            )
            page.update()
            return

        completed_ids = course_data.get("completed_lesson_ids", [])
        for mod in course_data["modules"]:
            for les in mod.get("lessons", []):
                les["is_done"] = les.get("id") in completed_ids

        recalculate_locks()

        found_bookmark = False
        for m_idx, mod in enumerate(course_data["modules"]):
            for l_idx, les in enumerate(mod.get("lessons", [])):
                if not les.get("is_done", False) and les.get("is_unlocked", True):
                    current_module_idx = m_idx
                    current_lesson_idx = l_idx
                    found_bookmark = True
                    break
            if found_bookmark:
                break

        module_expanded_state = {
            mod["id"]: (idx == current_module_idx)
            for idx, mod in enumerate(course_data["modules"])
        }

        appbar_title.value = course_data.get("course_title", "Course")
        sidebar_course_title.value = course_data.get("course_title", "Course")

        refresh_ui()

        content_socket.alignment = None
        content_socket.content = body_host
        page.update()

    page.run_task(fetch_initial_data)

    # =========================================================
    # 10. VIEW RETURN (Immediate)
    # =========================================================

    return ft.View(
        route=f"/courses/{course_id}/view",
        bgcolor=ft.Colors.SURFACE,
        padding=0,
        appbar=page_appbar,
        controls=[
            ft.SafeArea(
                expand=True,
                content=content_socket,
            )
        ],
    )