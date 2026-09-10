import random

import flet_charts as fch 
import flet as ft
from flet_video import Video, VideoMedia
import asyncio
from src.components.bottom_appbar import get_bottom_appbar
from src.requests.Courses import get_course_curriculum, mark_complete, generate_course_certificate, rate_course


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
    app_bar = get_bottom_appbar(page)

    # =========================================================
    # 0. THEME / LAYOUT CONFIG
    # =========================================================

    UI_ACCENT = ft.Colors.PRIMARY
    SIDEBAR_WIDTH = 320
    DESKTOP_BREAKPOINT = 1024
    ACTION_BUTTON_HEIGHT = 30          # Taller → easier tap target
    HEADER_RADIUS = 14
    CONTENT_CARD_RADIUS = 14

    def is_desktop_layout():
        return (page.width or 0) >= DESKTOP_BREAKPOINT

    def get_lesson_type_label(lesson_type: str):
        labels = {
            "video": "VIDEO LESSON",
            "audio": "AUDIO LESSON",
            "text": "READING",
            "document": "DOCUMENT",
            "cards": "FLASHCARDS",
            "assessment": "ASSESSMENT",
            "scenario": "SCENARIO",
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
    body_host = ft.Container(content=content_socket)

    def toggle_sidebar(e):
        nonlocal sidebar_visible
        # THE FIX: Removed the desktop block so toggling works everywhere!
        sidebar_visible = not sidebar_visible
        refresh_layout_shell()
        page.update()

    close_sidebar_button = ft.IconButton(
        ft.Icons.CLOSE,
        icon_size=18,
        on_click=toggle_sidebar,
    )

    menu_button = ft.IconButton(
        icon=ft.Icons.MENU_ROUNDED,
        icon_color=ft.Colors.PRIMARY,
        on_click=toggle_sidebar,
        tooltip="Course Menu",
        visible=False,
    )

    sidebar_course_title = ft.Text(
        "Loading...",
        color=ft.Colors.SURFACE,
        weight=ft.FontWeight.BOLD,
        size=13,
        expand=True,
    )

    # --- Course progress bar (inside sidebar header) ---
    sidebar_progress_bar = ft.ProgressBar(
        value=0,
        color=ft.Colors.SURFACE,
        bgcolor=ft.Colors.with_opacity(0.30, ft.Colors.SURFACE),
        height=4,
        border_radius=2,
    )
    sidebar_progress_label = ft.Text("0% complete", color=ft.Colors.SURFACE, size=11)

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

    sidebar_container = ft.Container(
        width=SIDEBAR_WIDTH,
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.only(
            right=ft.BorderSide(1, ft.Colors.with_opacity(0.10, ft.Colors.ON_PRIMARY))
        ),
        shadow=ft.BoxShadow(
            blur_radius=10,
            color=ft.Colors.with_opacity(0.10, ft.Colors.ON_PRIMARY),
            offset=ft.Offset(2, 0),
        ),
        visible=sidebar_visible,
        content=ft.Column(
            spacing=0,
            expand=True,
            controls=[
                # --- Sidebar header bar ---
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                    border=ft.Border.only(
                        bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_PRIMARY))
                    ),
                    bgcolor=ft.Colors.SURFACE,
                    content=ft.Row(
                        [
                            ft.Text(
                                "Course Menu",
                                weight=ft.FontWeight.BOLD,
                                size=14,
                                color=ft.Colors.ON_SURFACE,
                            ),
                            close_sidebar_button,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ),
                # --- Course identity + progress strip ---
                ft.Container(
                    padding=ft.Padding.only(left=14, right=14, top=14, bottom=10),
                    bgcolor=UI_ACCENT,
                    content=ft.Column(
                        [
                            sidebar_progress_bar,
                            sidebar_progress_label,
                        ],
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

    # Dynamic App Bar Title
    appbar_title = ft.Text(
        "Loading Course...",
        size=18,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.PRIMARY,
    )

    page_appbar = ft.AppBar(
        leading=ft.IconButton(
            ft.Icons.ARROW_BACK_ROUNDED,
            icon_color=ft.Colors.PRIMARY,
            on_click=lambda _: page.go(back_target),
        ),
        title=appbar_title,
        center_title=False,
        bgcolor=ft.Colors.ON_PRIMARY,
        actions=[menu_button],
    )

    # =========================================================
    # 4. LAYOUT SHELL HELPERS
    # =========================================================

    def refresh_layout_shell():
        desktop_mode = is_desktop_layout()

        # THE FIX: Make the buttons ALWAYS visible so desktop users can toggle
        menu_button.visible = True
        close_sidebar_button.visible = True

        if desktop_mode:
            # Respect the state instead of forcing True
            sidebar_container.visible = sidebar_visible
            sidebar_container.left = None
            sidebar_container.top = None
            sidebar_container.bottom = None

            # Dynamically build the Row so the divider disappears when closed
            desktop_controls = []
            if sidebar_visible:
                desktop_controls.append(sidebar_container)
                desktop_controls.append(
                    ft.VerticalDivider(
                        width=1, thickness=1,
                        color=ft.Colors.with_opacity(0.06, ft.Colors.ON_PRIMARY),
                    )
                )
                
            desktop_controls.append(
                ft.Container(
                    expand=True,
                    padding=ft.Padding.all(20),
                    content=main_content_area,
                )
            )

            body_host.content = ft.Row(
                desktop_controls,
                spacing=0,
                expand=True,
            )
        else:
            sidebar_container.visible = sidebar_visible
            sidebar_container.left = 0
            sidebar_container.top = 0
            sidebar_container.bottom = 0

            body_host.content = ft.Stack(
                [
                    ft.Container(
                        expand=True,
                        padding=ft.Padding.all(12),
                        content=main_content_area,
                    ),
                    sidebar_container,
                ],
                expand=True,
            )

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

        player = Video(
            expand=True,
            playlist=[VideoMedia(media_uri)],
            autoplay=True,
            volume=100,
            on_error=_on_error,
            on_load=_on_load,
            controls=ftv.MaterialDesktopVideoControls(
                visible_on_mount=True,
                display_seek_bar=True,
                play_and_pause_on_tap=True,
                modify_volume_on_scroll=True,
                toggle_fullscreen_on_double_press=True,
            ),
        )

        video_container = ft.Container(
            aspect_ratio=16 / 9,
            border_radius=12,
            bgcolor=ft.Colors.ON_PRIMARY,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            content=player,
        )

        return ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            content=ft.Container(width=1000, content=video_container),
        )
        
    @register_content_renderer("accompanying_text")
    def render_notes_block(value, lesson):
        async def handle_link_tap(e):
            await e.page.launch_url(e.data)

        return ft.Container(
            padding=18,
            border_radius=12,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_PRIMARY)),
            content=ft.Column(
                [
                    ft.Text("Instructor Notes", weight=ft.FontWeight.BOLD, size=15),
                    ft.Markdown(
                        value,
                        selectable=False, 
                        extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
                        on_tap_link=handle_link_tap 
                    ),
                ],
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.START,
            ),
        )
        
    @register_content_renderer("document_url")
    def render_document_block(value, lesson):
        file_name = lesson["content"].get("file_name", "Document")

        # THE FIX: Wrap the URL launcher in an async function so it gets awaited
        async def handle_download(e):
            await lesson["_page"].launch_url(value)

        return ft.Container(
            padding=40,
            border_radius=14,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            bgcolor=ft.Colors.SURFACE,
            alignment=ft.Alignment(0, 0),
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.PICTURE_AS_PDF_ROUNDED, size=60, color=ft.Colors.RED_500),
                    ft.Text(file_name, weight=ft.FontWeight.BOLD, size=18),
                    ft.ElevatedButton(
                        content=ft.Text("Download Document"),
                        icon=ft.Icons.DOWNLOAD,
                        on_click=handle_download, # <--- Pass the async function here
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=14,
            ),
        )
        
    @register_content_renderer("text")
    def render_text_block(value, lesson):
        async def handle_link_tap(e):
            await e.page.launch_url(e.data)
        return ft.Container(
            padding=24,
            border_radius=14,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_PRIMARY)),
            content=ft.Markdown(
                value,
                selectable=True, 
                extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,  # supports HTML passthrough
                code_theme=ft.MarkdownCodeTheme.ATELIER_LAKESIDE_DARK, 
                code_style_sheet=ft.MarkdownStyleSheet(
        code_text_style=ft.TextStyle(font_family="Roboto Mono", size=15),
        codeblock_decoration=ft.BoxDecoration(     # correct field name, fixes the light-mode bg bug
            bgcolor="#0662AD",
            border_radius=ft.BorderRadius.all(8),
        ),
    ),
                  # light background, default Flet uses
                
                on_tap_link=handle_link_tap ,
                md_style_sheet=ft.MarkdownStyleSheet(
        text_alignment=ft.TextAlign.START,
        p_text_style=ft.TextStyle(
            size=15,
            weight=ft.FontWeight.W_400,
            color=ft.Colors.ON_SURFACE,
        ),
    code_text_style=ft.TextStyle(
        size=15,
        weight=ft.FontWeight.NORMAL,
        font_family="monospace",
        color=ft.Colors.ON_SURFACE_VARIANT,
        bgcolor=ft.Colors.SCRIM,
    ),
),
            )
        )

    @register_content_renderer("audio_path")
    def render_audio_block(value, lesson):
        file_name = lesson["content"].get("file_name", "Audio Lesson")

        # THE FIX: Wrap the URL launcher in an async function so it gets awaited
        async def handle_download(e):
            await lesson["_page"].launch_url(value)

        return ft.Container(
            padding=40,
            border_radius=14,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_PRIMARY)),
            alignment=ft.Alignment(0, 0),
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.AUDIO_FILE_ROUNDED, size=56, color=ft.Colors.PRIMARY),
                    ft.Text(file_name, weight=ft.FontWeight.BOLD, size=18, text_align=ft.TextAlign.CENTER),
                    ft.ElevatedButton(
                        "Download Audio", 
                        icon=ft.Icons.DOWNLOAD, 
                        on_click=handle_download # <--- Pass the async function here
                    ),
                ],
                spacing=14,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )
    
    @register_content_renderer("cards")
# Define a palette of nice, soft background colors for your flashcards
    def render_cards_block(value, lesson):
        CARD_COLORS = [
        ft.Colors.BLUE_50, ft.Colors.RED_50, ft.Colors.GREEN_50, 
        ft.Colors.AMBER_50, ft.Colors.PURPLE_50, ft.Colors.TEAL_50
    ]
        cards_list = value
        card_idx = [0]
        
        # 1. Safely extract the raw markdown string
        raw_markdown_string = cards_list[0] if cards_list else "No cards"
        
        # 2. Pick a random color for this specific card
        card_bg_color =     random.choice(CARD_COLORS)

        # 3. Wrap it in a Container for the background, and style the Markdown perfectly
        card_text = ft.Container(
            alignment=ft.Alignment(0, 0), 
            bgcolor=card_bg_color,      # Applies your random background color
            padding=30,                 # Gives the text breathing room inside the colored box
            border_radius=12,           # Rounds the corners of the card
            content=ft.Markdown(
                value=raw_markdown_string,
                selectable=False, 
                extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
                
                # THE FIX: Force the markdown to center align and use your custom font size
                md_style_sheet=ft.MarkdownStyleSheet(
                    text_alignment=ft.TextAlign.CENTER,
                    p_text_style=ft.TextStyle(
                        size=22, 
                        weight=ft.FontWeight.W_600,
                        color=ft.Colors.BLACK
                    ),
                )
            ),
        )
        counter_text = ft.Text(
            f"1 / {len(cards_list)}",
            color=ft.Colors.BLACK,
            weight=ft.FontWeight.BOLD,
        )

        card_container = ft.Container(
            padding=40,
            border_radius=16,
            bgcolor=card_bg_color, # Initial random color
        )

        # 2. The proper update function (no arguments needed!)
        def update():
            # Update the text content
            card_text.content.value = cards_list[card_idx[0]]
            counter_text.value = f"{card_idx[0] + 1} / {len(cards_list)}"
            
            # THE FIX: Directly target the container's background color property
            card_container.bgcolor = random.choice(CARD_COLORS)
            card_text.bgcolor = card_container.bgcolor  # Sync the inner text background with the container
            
            lesson["_page"].update()

        # 3. Clean navigation handlers instead of messy lambdas
        def go_back(e):
            if card_idx[0] > 0:
                card_idx[0] -= 1
                update()

        def go_forward(e):
            if card_idx[0] < len(cards_list) - 1:
                card_idx[0] += 1
                update()

        # 4. Attach the inner content to the container
        card_container.content = ft.Column(
            [
                ft.Container(card_text, expand=True, alignment=ft.Alignment(0, 0)),
                ft.Row(
                    [
                        ft.IconButton(ft.Icons.ARROW_BACK_IOS_ROUNDED, on_click=go_back, icon_color="BLACK"),
                        counter_text,
                        ft.IconButton(ft.Icons.ARROW_FORWARD_IOS_ROUNDED, on_click=go_forward, icon_color="BLACK"),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            ]
        )

        # 5. Return the fully assembled, state-aware container
        return card_container

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
            padding=20,
            border_radius=12,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.BLUE_200),
            visible=False,
            content=ft.Column([
                ft.Row([ft.Icon(ft.Icons.LIGHTBULB_CIRCLE, color=ft.Colors.BLUE_700), ft.Text("Result", weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900)]),
                ft.Markdown("", selectable=False, extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED, md_style_sheet=ft.MarkdownStyleSheet(
                    p_text_style=ft.TextStyle(
                        color=ft.Colors.ON_SURFACE
                    ),
                ))
            ])
        )

        buttons_col = ft.Column(spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

        def make_button_style(selected: bool):
            if selected:
                return ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=8),
                    padding=20,
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
                        ft.ControlState.DEFAULT: ft.BorderSide(1, UI_ACCENT),
                    },
                )
            else:
                return ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=8),
                    padding=20,
                    bgcolor={
                        ft.ControlState.DEFAULT: ft.Colors.TRANSPARENT,
                        ft.ControlState.HOVERED: ft.Colors.with_opacity(0.08, UI_ACCENT),
                        ft.ControlState.PRESSED: ft.Colors.with_opacity(0.15, UI_ACCENT),
                    },
                    color={
                        ft.ControlState.DEFAULT: UI_ACCENT,
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
                content=ch.get("text", f"Option {idx+1}"),
                style=make_button_style(selected=False),
                on_click=lambda e, i=idx, c_t=ch.get("consequence", ""): handle_choice(i, c_t)
            )
            buttons_col.controls.append(btn)

        return ft.Container(
            padding=25,
            border_radius=16,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_PRIMARY)),
            content=ft.Column(
                [
                    ft.Row([
                        ft.Icon(ft.Icons.CALL_SPLIT_ROUNDED, color=UI_ACCENT, size=28),
                        ft.Text("Decision Matrix", weight=ft.FontWeight.BOLD, size=18, color=UI_ACCENT)
                    ]),
                    ft.Markdown(
                        scenario_text,
                        selectable=True,
                        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                        code_theme=ft.MarkdownCodeTheme.ATELIER_LAKESIDE_DARK,
                        code_style_sheet=ft.MarkdownStyleSheet(
                            code_text_style=ft.TextStyle(font_family="Roboto Mono", size=15),
                            codeblock_decoration=ft.BoxDecoration(
                                bgcolor="#0662AD",
                                border_radius=ft.BorderRadius.all(8),
                            ),
                        ),
                        on_tap_link=handle_link_tap,
                        md_style_sheet=ft.MarkdownStyleSheet(
                            text_alignment=ft.TextAlign.START,
                            p_text_style=ft.TextStyle(
                                size=15,
                                weight=ft.FontWeight.W_400,
                                color=ft.Colors.ON_SURFACE,
                            ),
                        ),
                    ),
                    buttons_col,
                    consequence_box,
                ],
                spacing=15,
            ),
        )
    def render_assessment_ui(lesson: dict):
        content = lesson.get("content", {})
        questions = content.get("questions", [])
        
        # --- CHECK COMPLETION STATE ---
        is_completed = lesson.get("is_done", False)

        current_assessment_state.clear()
        question_cards = []
        
        # Setup muted colors for the locked state
        text_color = ft.Colors.ON_SURFACE_VARIANT if is_completed else ft.Colors.ON_SURFACE
        accent_color = ft.Colors.GREY_400 if is_completed else UI_ACCENT

        for q_idx, q in enumerate(questions):
            options_data = q.get("options", [])
            
            # Count correct options to determine if it's multiple choice
            correct_count = sum(1 for opt in options_data if opt.get("is_correct"))
            is_multi_select = correct_count > 1

            # Build Question Text
            q_text_str = f"Q{q_idx + 1}: {q.get('text', '')}"
            if is_multi_select:
                q_text_str += " (Select all that apply)"
                
            # Assuming 'question_string' holds your markdown text from the database/backend
            q_text = ft.Markdown(
                value=q_text_str,
                selectable=True,
                # GITHUB_FLAVORED adds support for tables, strikethrough, and task lists
                extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
                
                # Optional: You can style the paragraph text so it matches your old font sizes
                md_style_sheet=ft.MarkdownStyleSheet(
                    p_text_style=ft.TextStyle(size=15, color=ft.Colors.ON_SURFACE, weight=ft.FontWeight.W_500),
                )
            )

            # Build Options UI dynamically
            if is_multi_select:
                checkboxes = []
                options_rows = []
                for opt in options_data:
                    opt_text = opt.get("text", "")
                    
                    # Apply disabled flag and dynamic colors based on completion
                    cb = ft.Checkbox(
                        value=False, 
                        data=opt_text, 
                        fill_color=accent_color if is_completed else "white", 
                        check_color=ft.Colors.SURFACE if is_completed else UI_ACCENT,
                        disabled=is_completed
                    )
                    checkboxes.append(cb)
                    options_rows.append(
                        ft.Row(
                            [cb, ft.Text(opt_text, expand=True, color=text_color)],
                            vertical_alignment=ft.CrossAxisAlignment.START,
                        )
                    )
                
                options_ui = ft.Column(options_rows, spacing=10)
                current_assessment_state[f"question_{q_idx + 1}"] = {"type": "multi", "controls": checkboxes}
            
            else:
                options_group = ft.RadioGroup(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Radio(value=opt.get("text"), fill_color=accent_color, disabled=is_completed), 
                                    ft.Text(opt.get("text"), expand=True, color=text_color)
                                ],
                                vertical_alignment=ft.CrossAxisAlignment.START,
                            )
                            for opt in options_data
                        ],
                        spacing=10,
                    )
                )
                options_ui = options_group
                current_assessment_state[f"question_{q_idx + 1}"] = {"type": "single", "controls": options_group}

            question_cards.append(
    ft.Container(
        padding=25,
        border_radius=16,
        # Slightly grey out the background of the card if completed
        bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.ON_PRIMARY) if is_completed else ft.Colors.SURFACE,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_PRIMARY)),
        content=ft.Column([
            ft.Row(
                controls=[
                    # THE FIX: Wrap q_text with expand=True so it respects screen bounds and wraps
                    ft.Container(content=q_text, expand=True), 
                    
                    ft.Icon(ft.Icons.LOCK_ROUNDED, color=ft.Colors.GREY_400, size=18) if is_completed else ft.Container()
                ], 
                # alignment=ft.MainAxisAlignment.SPACE_BETWEEN is no longer needed since expand=True pushes the icon perfectly to the right edge
            ),
            ft.Divider(height=1), 
            options_ui
        ], spacing=15),
    )
)

        # Add a success banner at the top if they already finished it
        banner = []
        if is_completed:
            banner = [
                ft.Container(
                    padding=15, border_radius=12, bgcolor=ft.Colors.GREEN_50, border=ft.Border.all(1, ft.Colors.GREEN_200),
                    content=ft.Row([
                        ft.Icon(ft.Icons.VERIFIED_ROUNDED, color=ft.Colors.GREEN_600),
                        ft.Text("You have already passed this assessment.", weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_800, size=11)
                    ])
                )
            ]

        return ft.Container(
            width=None,
            padding=0,
            content=ft.Column(banner + question_cards, spacing=20, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
        )

    def render_lesson_ui(lesson: dict):
        content = lesson.get("content", {})
        blocks = []
        lesson["_page"] = page

        for key, value in content.items():
            # Add the new keys to the skip list
            if key in ["questions", "scenario", "choices", "prompt_text"]:
                continue

            renderer = CONTENT_RENDERERS.get(key)
            if renderer:
                blocks.append(renderer(value, lesson))

        if lesson["type"] == "assessment":
            blocks.append(render_assessment_ui(lesson))
        elif lesson["type"] == "scenario":
            blocks.append(render_scenario_ui(lesson))

        return ft.Column(blocks, spacing=20, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)


    # =========================================================
    # 6. SIDEBAR HELPERS
    # =========================================================

    def build_sidebar_lesson_row(les, m_idx, l_idx, is_active_lesson):
        is_done = les.get("is_done", False)
        is_unlocked = les.get("is_unlocked", False)

        if is_done:
            lesson_icon = ft.Icon(ft.Icons.CHECK_CIRCLE, size=14, color=ft.Colors.GREEN_600)
            text_color = UI_ACCENT if is_active_lesson else ft.Colors.ON_SURFACE
        elif not is_unlocked:
            lesson_icon = ft.Icon(ft.Icons.LOCK_ROUNDED, size=13, color=ft.Colors.GREY_400)
            text_color = ft.Colors.GREY_400
        elif is_active_lesson:
            lesson_icon = ft.Icon(ft.Icons.PLAY_CIRCLE_FILL_ROUNDED, size=14, color=UI_ACCENT)
            text_color = UI_ACCENT
        else:
            lesson_icon = ft.Icon(ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED, size=13, color=ft.Colors.GREY_500)
            text_color = ft.Colors.ON_SURFACE

        lesson_type = les.get("type", "")
        type_badge = ft.Container(
            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
            border_radius=4,
            bgcolor=ft.Colors.with_opacity(0.08, UI_ACCENT) if is_active_lesson else ft.Colors.with_opacity(0.05, ft.Colors.ON_PRIMARY),
            content=ft.Text(
                get_lesson_type_label(lesson_type),
                size=9,
                weight=ft.FontWeight.BOLD,
                color=UI_ACCENT if is_active_lesson else ft.Colors.GREY_500,
            ),
        ) if not is_done else ft.Container()

        def handle_click(e):
            if is_unlocked:
                jump_to_lesson(m_idx, l_idx)

        return ft.Container(
            ink=is_unlocked,
            on_click=handle_click if is_unlocked else None,
            bgcolor=ft.Colors.with_opacity(0.06, UI_ACCENT) if is_active_lesson else ft.Colors.SURFACE,
            border=ft.Border.only(
                left=ft.BorderSide(3, UI_ACCENT if is_active_lesson else ft.Colors.TRANSPARENT),
                bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.05, ft.Colors.ON_PRIMARY)),
            ),
            padding=ft.Padding.symmetric(horizontal=14, vertical=11),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Container(
                                width=18,
                                alignment=ft.Alignment(0, 0),
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
                        [ft.Container(width=26), type_badge],
                        spacing=0,
                    ) if not is_done else ft.Container(),
                ],
                spacing=4,
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

                    cert_loading_indicator = ft.Column(
                        [
                            ft.ProgressRing(width=28, height=28, color=UI_ACCENT, stroke_width=3),
                            ft.Text(
                                "Generating your verifiable certificate...",
                                size=13, color=ft.Colors.ON_SURFACE_VARIANT, italic=True, text_align=ft.TextAlign.CENTER,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10, tight=True,
                    )

                    cert_action_container = ft.Container(
                        content=cert_loading_indicator,
                        padding=ft.Padding.symmetric(vertical=10),
                    )

                    rating_stars = ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=4)
                    for i in range(1, 6):
                        rating_stars.controls.append(ft.IconButton(
                            icon=ft.Icons.STAR_BORDER_ROUNDED,
                            icon_color=ft.Colors.AMBER_400,
                            data=i,
                            on_click=lambda e: page.run_task(submit_rating, e.control.data)
                        ))
                    rating_action_container = ft.Container(
                        content=ft.Column(
                            [
                                ft.Text("Rate this course:", size=14, weight=ft.FontWeight.W_600),
                                rating_stars
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True, spacing=4
                        ),
                        padding=ft.Padding.symmetric(vertical=10),
                    )
                    
                    async def submit_rating(rating_val):
                        for idx, star in enumerate(rating_stars.controls):
                            star.disabled = True
                            if idx < rating_val:
                                star.icon = ft.Icons.STAR_ROUNDED
                        page.update()
                        
                        res = await rate_course(token, course_id, rating_val)
                        if "error" not in res:
                            rating_action_container.content = ft.Text("Thank you for your feedback!", color=ft.Colors.GREEN, size=13, weight=ft.FontWeight.W_500, text_align=ft.TextAlign.CENTER)
                        else:
                            rating_action_container.content = ft.Text("Failed to submit rating.", color=ft.Colors.RED, size=13, text_align=ft.TextAlign.CENTER)
                        page.update()

                    def close_dialog_and_go(e=None):
                        # Was: dialog.open = False (stale API — should be
                        # page.pop_dialog()) followed by a hardcoded
                        # page.go("/dashboard"). Two problems: the stale
                        # close call meant the dialog might not have
                        # actually dismissed cleanly, and /dashboard is a
                        # protected route requiring a live connection —
                        # if certificate generation just failed (its own
                        # error path already implies degraded/no
                        # connectivity), this hardcoded navigation was
                        # near-guaranteed to fail too, which is what froze
                        # the course page UI: a failed protected
                        # navigation with a dialog left in an inconsistent
                        # state on top of it.
                        #
                        # Fixed: proper dialog close, and navigate to
                        # back_target instead of a hardcoded route —
                        # back_target is always somewhere this session
                        # already successfully reached (either /courses or
                        # /offline), so it can't fail the same way an
                        # unrelated, unverified /dashboard hop can.
                        page.pop_dialog()
                        page.go(back_target)

                    is_offline = back_target == "/offline"

                    def close_dialog_and_go_stats(e=None):
                        page.pop_dialog()
                        page.go(f"/courses/{course_id}/stats")

                    if not is_offline:
                        stats_action_container = ft.ElevatedButton(
                            content="View My Stats",
                            icon=ft.Icons.QUERY_STATS,
                            style=ft.ButtonStyle(bgcolor=UI_ACCENT, color=ft.Colors.SURFACE, shape=ft.RoundedRectangleBorder(radius=10), padding=ft.Padding(24, 14, 24, 14)),
                            on_click=close_dialog_and_go_stats
                        )
                    else:
                        stats_action_container = ft.Container() # Omitted offline

                    dialog = ft.AlertDialog(
                        modal=True,
                        shape=ft.RoundedRectangleBorder(radius=20),
                        content_padding=0,
                        content=ft.Container(
                            width=460,
                            bgcolor=ft.Colors.SURFACE,
                            border_radius=20,
                            clip_behavior=ft.ClipBehavior.HARD_EDGE,
                            content=ft.Column(
                                [
                                    ft.Container(
                                        padding=ft.Padding.symmetric(horizontal=30, vertical=28),
                                        gradient=ft.LinearGradient(
                                            begin=ft.Alignment.TOP_LEFT,
                                            end=ft.Alignment.BOTTOM_RIGHT,
                                            colors=[ft.Colors.AMBER_400, ft.Colors.ORANGE_400],
                                        ),
                                        content=ft.Column(
                                            [
                                                ft.Container(
                                                    bgcolor=ft.Colors.with_opacity(0.25, ft.Colors.SURFACE),
                                                    border_radius=50, padding=16, alignment=ft.Alignment(0, 0),
                                                    width=80, height=80,
                                                    content=ft.Icon(ft.Icons.WORKSPACE_PREMIUM_ROUNDED, size=44, color=ft.Colors.SURFACE),
                                                ),
                                                ft.Container(height=14),
                                                ft.Text("Congratulations!", size=26, weight=ft.FontWeight.W_900, color=ft.Colors.SURFACE, text_align=ft.TextAlign.CENTER),
                                                ft.Text(f"You've completed {course_data.get('course_title', 'the course')}!", size=14, color=ft.Colors.with_opacity(0.88, ft.Colors.SURFACE), text_align=ft.TextAlign.CENTER),
                                            ],
                                            horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True, spacing=0,
                                        ),
                                    ),
                                    ft.Container(
                                        padding=ft.Padding.symmetric(horizontal=28, vertical=18),
                                        content=ft.Column(
                                            (
                                                [
                                                    ft.Container(height=18),
                                                    cert_action_container,
                                                    ft.Divider(height=24, color=ft.Colors.OUTLINE_VARIANT),
                                                    rating_action_container,
                                                ]
                                                if course_data.get('auto_certificate', True) else 
                                                [
                                                    ft.Container(height=18),
                                                    rating_action_container,
                                                ]
                                            ),
                                            horizontal_alignment=ft.CrossAxisAlignment.STRETCH, spacing=0,
                                        ),
                                    ),
                                    ft.Container(
                                        padding=ft.Padding.only(left=28, right=28, bottom=24),
                                        content=ft.Column([
                                            stats_action_container,
                                            ft.TextButton("Return to Dashboard", style=ft.ButtonStyle(color=ft.Colors.ON_SURFACE_VARIANT), on_click=close_dialog_and_go),
                                        ], horizontal_alignment=ft.CrossAxisAlignment.STRETCH, spacing=8)
                                    ),
                                ],
                                spacing=0, tight=True,
                            ),
                        ),
                    )

                    # 1. THE FIX: Version-safe dialog mounting so it actually shows up!
                    if hasattr(page, "open"): 
                        page.open(dialog)
                    else: 
                        page.overlay.append(dialog)
                        dialog.open = True
                        page.update()

                    # 2. THE RECURSIVE RETRY FUNCTION
                    async def attempt_cert_generation(e=None):
                        # Crucial: Give Flet 100ms to mount the dialog in the DOM before updating children
                        await asyncio.sleep(0.1)
                        
                        if not dialog.open: return

                        # Reset to loading spinner
                        cert_action_container.content = cert_loading_indicator
                        if cert_action_container.page: cert_action_container.update()

                        # Fire API
                        res = await generate_course_certificate(token, course_id)
                        
                        if not dialog.open: return
                        
                        if "error" in res:
                            cert_action_container.content = ft.Container(
                                padding=ft.Padding.symmetric(vertical=8, horizontal=12),
                                border_radius=10, bgcolor=ft.Colors.RED_50, border=ft.Border.all(1, ft.Colors.RED_200),
                                content=ft.Column(
                                    spacing=10, 
                                    controls=[
                                        ft.Row([
                                            ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, color=ft.Colors.RED_600, size=20),
                                            ft.Text("Could not generate certificate. Please try again later.", color=ft.Colors.RED_700, size=13, expand=True),
                                        ], vertical_alignment=ft.CrossAxisAlignment.START),
                                        ft.ElevatedButton(
                                            content="Retry", color=ft.Colors.SURFACE, bgcolor=ft.Colors.RED, align=ft.Alignment.CENTER,
                                            on_click=lambda e: page.run_task(attempt_cert_generation) 
                                        )
                                    ]
                                )
                            )
                            if cert_action_container.page: cert_action_container.update()
                        else:
                            cert_url = res.get("url", "")
                            cred_id = res.get("credential_id", "")

                            async def handle_cert_download(e):
                                if cert_url: await page.launch_url(cert_url)

                            cert_action_container.content = ft.Column(
                                [
                                    ft.FilledButton(
                                        content=ft.Row(
                                            [
                                                ft.Icon(ft.Icons.DOWNLOAD_ROUNDED, color=ft.Colors.SURFACE, size=18),
                                                ft.Text("Download Certificate", color=ft.Colors.SURFACE, weight=ft.FontWeight.BOLD, size=14),
                                            ], tight=True, spacing=8, alignment=ft.MainAxisAlignment.CENTER,
                                        ),
                                        style=ft.ButtonStyle(bgcolor=UI_ACCENT, shape=ft.RoundedRectangleBorder(radius=10), padding=ft.Padding(24, 14, 24, 14), elevation=0),
                                        on_click=handle_cert_download, expand=True,
                                    ),
                                    ft.Container(
                                        padding=ft.Padding.symmetric(horizontal=12, vertical=8), border_radius=8,
                                        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_PRIMARY), border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                                        content=ft.Row(
                                            [
                                                ft.Icon(ft.Icons.FINGERPRINT_ROUNDED, size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                                                ft.Text("Credential ID: ", size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
                                                ft.Text(str(cred_id), size=11, color=ft.Colors.ON_SURFACE, weight=ft.FontWeight.BOLD, selectable=True),
                                            ], spacing=4, alignment=ft.MainAxisAlignment.CENTER, wrap=True,
                                        ),
                                    ),
                                ], horizontal_alignment=ft.CrossAxisAlignment.STRETCH, spacing=10,
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
        bgcolor=ft.Colors.SURFACE,
        color=UI_ACCENT,
        height=ACTION_BUTTON_HEIGHT,
        expand=True,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=10),
            side=ft.BorderSide(1.5, UI_ACCENT),
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
            shape=ft.RoundedRectangleBorder(radius=10),
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
            module_title_row = ft.Row(
                [
                    ft.Text(mod["title"], weight=ft.FontWeight.BOLD, size=12.5, expand=True),
                    ft.Icon(ft.Icons.CHECK_CIRCLE, size=14, color=ft.Colors.GREEN_600) if mod_done else ft.Container(),
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
                    tile_padding=ft.Padding.symmetric(horizontal=14, vertical=4),
                    controls_padding=ft.Padding.only(left=0, right=0, bottom=0),
                    collapsed_bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_PRIMARY),
                    bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_PRIMARY),
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
                action_button.bgcolor = ft.Colors.GREY_300
                action_button.color = ft.Colors.GREY_600
                action_button.disabled = True
            else:
                next_btn_text = "Submit & Finish Course" if is_last_overall else "Submit Assessment"
                action_button.bgcolor = UI_ACCENT
                action_button.color = ft.Colors.SURFACE
                action_button.disabled = False
        else:
            next_btn_text = "Finish Course" if is_last_overall else "Next Lesson →"
            action_button.bgcolor = UI_ACCENT
            action_button.color = ft.Colors.SURFACE
            action_button.disabled = False

        previous_button.content = ft.Row(
            [ft.Icon(ft.Icons.ARROW_BACK_ROUNDED, size=16, color=UI_ACCENT), ft.Text("Previous", weight=ft.FontWeight.BOLD)],
            tight=True, spacing=6, alignment=ft.MainAxisAlignment.CENTER,
        )
        previous_button.visible = not is_first_overall
        previous_button.disabled = False
        
        action_button.content = ft.Text(next_btn_text, weight=ft.FontWeight.BOLD, size=14)

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

                score_color = ft.Colors.GREEN_600 if passed else ft.Colors.RED_600
                status_icon = ft.Icons.VERIFIED_ROUNDED if passed else ft.Icons.CANCEL_ROUNDED
                status_text = "PASSED" if passed else "FAILED"

                chart_sections = []
                if correct_count > 0:
                    chart_sections.append(fch.PieChartSection(value=correct_count, color=ft.Colors.GREEN_500, radius=22, title=" "))
                if incorrect_count > 0:
                    chart_sections.append(fch.PieChartSection(value=incorrect_count, color=ft.Colors.RED_500, radius=22, title=" "))

                analytics_chart_ui = ft.Container(
                    padding=ft.Padding.symmetric(vertical=14),
                    content=ft.Row(
                        [
                            ft.Container(
                                width=70, height=70,
                                content=fch.PieChart(sections=chart_sections, sections_space=2, center_space_radius=22),
                            ),
                            ft.Column(
                                [
                                    ft.Row([ft.Icon(ft.Icons.CIRCLE, size=10, color=ft.Colors.GREEN_500), ft.Text(f"Correct: {correct_count}", size=13, weight=ft.FontWeight.BOLD)]),
                                    ft.Row([ft.Icon(ft.Icons.CIRCLE, size=10, color=ft.Colors.RED_500), ft.Text(f"Incorrect: {incorrect_count}", size=13, weight=ft.FontWeight.BOLD)]),
                                ],
                                spacing=6, alignment=ft.MainAxisAlignment.CENTER,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER, spacing=24,
                    ),
                )

                breakdown_controls = []
                for res in results_breakdown:
                    icon = ft.Icons.CHECK_CIRCLE if res["is_correct"] else ft.Icons.CANCEL
                    color = ft.Colors.GREEN_600 if res["is_correct"] else ft.Colors.RED_600

                    correct_answer_ui = ft.Container()
                    if not res["is_correct"]:
                        correct_answer_ui = ft.Row(
                            [
                                ft.Icon(ft.Icons.SUBDIRECTORY_ARROW_RIGHT_ROUNDED, size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(f"Correct: {res['correct_answer']}", color=ft.Colors.ON_SURFACE_VARIANT, size=12, expand=True),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.START,
                        )

                    breakdown_controls.append(
                        ft.Container(
                            padding=12, border_radius=8, bgcolor=ft.Colors.with_opacity(0.05, color), border=ft.Border.all(1, ft.Colors.with_opacity(0.20, color)),
                            content=ft.Column(
                                [
                                    ft.Text(res["question"], weight=ft.FontWeight.W_600, size=13),
                                    ft.Row(
                                        [
                                            ft.Icon(icon, color=color, size=15),
                                            ft.Text(f"Your answer: {res['user_answer']}", color=color, size=12, weight=ft.FontWeight.W_500, expand=True),
                                        ],
                                        vertical_alignment=ft.CrossAxisAlignment.START,
                                    ),
                                    correct_answer_ui,
                                ],
                                spacing=5,
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
                    shape=ft.RoundedRectangleBorder(radius=16),
                    content_padding=0,
                    content=ft.Container(
                        width=450, height=650, bgcolor=ft.Colors.SURFACE, border_radius=12,
                        content=ft.Column(
                            [
                                ft.Container(
                                    padding=20, bgcolor=score_color, border_radius=ft.BorderRadius.only(top_left=12, top_right=12),
                                    content=ft.Column(
                                        [
                                            ft.Row([ft.Icon(status_icon, color=ft.Colors.SURFACE, size=28), ft.Text(f"Assessment {status_text}", weight=ft.FontWeight.BOLD, size=20, color=ft.Colors.SURFACE)], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
                                            ft.Text(f"You scored {score_percentage}%", color=ft.Colors.SURFACE, size=17, weight=ft.FontWeight.W_500, text_align=ft.TextAlign.CENTER),
                                        ],
                                        horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6,
                                    ),
                                ),
                                ft.Container(
                                    padding=ft.Padding.symmetric(horizontal=20), expand=True,
                                    content=ft.Column(
                                        controls=[
                                            analytics_chart_ui,
                                            ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT),
                                            ft.Text("Detailed Breakdown", weight=ft.FontWeight.BOLD, size=15),
                                        ] + breakdown_controls + [ft.Container(height=10)],
                                        scroll=ft.ScrollMode.AUTO, spacing=12,
                                    ),
                                ),
                                ft.Container(
                                    padding=ft.Padding.symmetric(horizontal=20, vertical=16), border=ft.Border.only(top=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
                                    content=ft.Row(
                                        [
                                            ft.OutlinedButton("Retry Assessment", icon=ft.Icons.REPLAY_ROUNDED, on_click=close_and_retry) if not passed else ft.Container(),
                                            ft.Button("Continue Course", icon=ft.Icons.ARROW_FORWARD_ROUNDED, bgcolor=UI_ACCENT, color=ft.Colors.SURFACE, align=ft.Alignment.CENTER, on_click=close_and_continue) if passed else ft.Container(),
                                        ],
                                        alignment=ft.MainAxisAlignment.END if passed else ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                ),
                            ],
                            spacing=0,
                        ),
                    ),
                )

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

        header_container = ft.Container(
            padding=ft.Padding.symmetric(horizontal=20, vertical=18),
            border_radius=HEADER_RADIUS,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_PRIMARY)),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(active_mod["title"].upper(), size=11, weight=ft.FontWeight.BOLD, color=UI_ACCENT),
                            ft.Text("·", color=ft.Colors.ON_SURFACE_VARIANT, size=11),
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=8, vertical=4), border_radius=999, bgcolor=ft.Colors.with_opacity(0.10, UI_ACCENT),
                                content=ft.Row([ft.Icon(get_lesson_type_icon(active_les["type"]), size=11, color=UI_ACCENT), ft.Text(get_lesson_type_label(active_les["type"]), size=10, weight=ft.FontWeight.BOLD, color=UI_ACCENT)], spacing=4, tight=True),
                            ),
                            ft.Text(f"{lesson_number} of {total_lessons}", size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
                        ],
                        alignment=ft.MainAxisAlignment.START, spacing=6, wrap=True, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Text(active_les["title"], size=26, weight=ft.FontWeight.W_900, color=ft.Colors.ON_SURFACE, text_align=ft.TextAlign.LEFT),
                    ft.Container(content=ft.ProgressBar(value=(lesson_number - 1) / max(total_lessons - 1, 1), color=UI_ACCENT, bgcolor=ft.Colors.with_opacity(0.12, UI_ACCENT), height=3, border_radius=2)),
                ],
                spacing=10, horizontal_alignment=ft.CrossAxisAlignment.START,
            ),
        )

        lesson_body_scroll.content = ft.Column(
            [
                header_container,
                ft.Container(height=7),
                render_lesson_ui(active_les),
                ft.Container(height=8),
            ],
            scroll=ft.ScrollMode.AUTO, expand=True, spacing=0, horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

        is_assessment = active_les["type"] == "assessment"
        action_footer_controls = []

        if is_assessment:
            action_footer_controls.append(ft.Row([action_button], spacing=0))
        else:
            if not is_first_overall:
                action_footer_controls.append(ft.Row([previous_button, ft.Container(width=10), action_button], spacing=0))
            else:
                action_footer_controls.append(ft.Row([action_button], spacing=0))

        action_footer_container.content = ft.Container(
            padding=ft.Padding.only(top=10), border=ft.Border.only(top=ft.BorderSide(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_PRIMARY))),
            content=ft.Column(action_footer_controls, spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
        )

        main_content_area.content = ft.Container(
            padding=ft.Padding.all(10), border_radius=16, bgcolor=ft.Colors.SURFACE,
            shadow=ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.05, ft.Colors.ON_PRIMARY), offset=ft.Offset(0, 2)),
            content=ft.Column([lesson_body_scroll, action_footer_container], expand=True, spacing=0, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
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
        bgcolor=ft.Colors.ON_PRIMARY,
        padding=0,
        appbar=page_appbar,
        controls=[
            ft.SafeArea(
                expand=True,
                content=content_socket,
            )
        ],
    )