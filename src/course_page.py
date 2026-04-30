import flet_charts as fch 
import flet as ft
from flet_video import Video, VideoMedia
import asyncio
from src.components.bottom_appbar import get_bottom_appbar
from src.requests.Courses import get_course_curriculum, mark_complete, generate_course_certificate


async def course_learner_view(page: ft.Page, course_id: str):
    token = await page.shared_preferences.get("auth_token")
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
        course_data = await get_course_curriculum(token, course_id)
        return course_data

    async def api_save_progress(course_id: str, lesson_id: str):
        res = await mark_complete(token, course_id, lesson_id)
        return res

    async def api_verify_module_completion(module_id: str):
        return True

    async def api_submit_assessment(lesson_id: str, answers: dict):
        await asyncio.sleep(1.5)
        return {"passed": True, "score": 100}

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
        if is_desktop_layout():
            return
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
        icon_color=ft.Colors.WHITE,
        on_click=toggle_sidebar,
        tooltip="Course Menu",
        visible=False,
    )

    sidebar_course_title = ft.Text(
        "Loading...",
        color=ft.Colors.WHITE,
        weight=ft.FontWeight.BOLD,
        size=13,
        expand=True,
    )

    # --- Course progress bar (inside sidebar header) ---
    sidebar_progress_bar = ft.ProgressBar(
        value=0,
        color=ft.Colors.WHITE,
        bgcolor=ft.Colors.with_opacity(0.30, ft.Colors.WHITE),
        height=4,
        border_radius=2,
    )
    sidebar_progress_label = ft.Text("0% complete", color=ft.Colors.WHITE70, size=11)

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
        bgcolor=ft.Colors.WHITE,
        border=ft.border.only(
            right=ft.border.BorderSide(1, ft.Colors.with_opacity(0.10, ft.Colors.BLACK))
        ),
        shadow=ft.BoxShadow(
            blur_radius=10,
            color=ft.Colors.with_opacity(0.10, ft.Colors.BLACK),
            offset=ft.Offset(2, 0),
        ),
        visible=sidebar_visible,
        content=ft.Column(
            spacing=0,
            expand=True,
            controls=[
                # --- Sidebar header bar ---
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=12, vertical=10),
                    border=ft.border.only(
                        bottom=ft.border.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.BLACK))
                    ),
                    bgcolor=ft.Colors.WHITE,
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
                    padding=ft.padding.only(left=14, right=14, top=14, bottom=10),
                    bgcolor=UI_ACCENT,
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.MENU_BOOK_ROUNDED, color=ft.Colors.WHITE, size=16),
                                    sidebar_course_title,
                                ],
                                spacing=8,
                            ),
                            ft.Container(height=8),
                            sidebar_progress_bar,
                            ft.Container(height=4),
                            sidebar_progress_label,
                        ],
                        spacing=0,
                    ),
                ),
                ft.Container(
                    expand=True,
                    bgcolor=ft.Colors.WHITE,
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
        color=ft.Colors.WHITE,
    )

    page_appbar = ft.AppBar(
        leading=ft.IconButton(
            ft.Icons.ARROW_BACK_ROUNDED,
            icon_color=ft.Colors.WHITE,
            on_click=lambda _: page.go("/courses"),
        ),
        title=appbar_title,
        center_title=False,
        bgcolor=UI_ACCENT,
        actions=[menu_button],
    )

    # =========================================================
    # 4. LAYOUT SHELL HELPERS
    # =========================================================

    def refresh_layout_shell():
        desktop_mode = is_desktop_layout()

        menu_button.visible = not desktop_mode
        close_sidebar_button.visible = not desktop_mode

        if desktop_mode:
            sidebar_container.visible = True
            sidebar_container.left = None
            sidebar_container.top = None
            sidebar_container.bottom = None

            body_host.content = ft.Row(
                [
                    sidebar_container,
                    ft.VerticalDivider(
                        width=1, thickness=1,
                        color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK),
                    ),
                    ft.Container(
                        expand=True,
                        padding=ft.padding.all(20),
                        content=main_content_area,
                    ),
                ],
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
                        padding=ft.padding.all(12),
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

    @register_content_renderer("video_url")
    def render_video_block(value, lesson):
        player = Video(
            expand=True,
            playlist=[VideoMedia(value)],
            autoplay=False,
            volume=100,
            show_controls=True,
        )

        return ft.Container(
            aspect_ratio=16 / 9,
            border_radius=12,
            bgcolor=ft.Colors.BLACK,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            content=ft.Stack(
                [
                    player,
                    ft.Container(
                        content=ft.Text(
                            lesson["content"].get("file_name", "Video Lesson"),
                            color=ft.Colors.WHITE,
                            weight=ft.FontWeight.BOLD,
                            size=16,
                        ),
                        padding=ft.padding.symmetric(horizontal=15, vertical=10),
                        gradient=ft.LinearGradient(
                            begin=ft.Alignment.TOP_CENTER,
                            end=ft.Alignment.BOTTOM_CENTER,
                            colors=[ft.Colors.BLACK87, ft.Colors.TRANSPARENT],
                        ),
                        left=0, right=0, top=0, height=60,
                    ),
                ],
                expand=True,
            ),
        )
        
    @register_content_renderer("accompanying_text")
    def render_notes_block(value, lesson):
        async def handle_link_tap(e):
            await e.page.launch_url(e.data)

        return ft.Container(
            padding=18,
            border_radius=12,
            bgcolor=ft.Colors.WHITE,
            border=ft.border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.BLACK)),
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
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            bgcolor=ft.Colors.WHITE,
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
            bgcolor=ft.Colors.WHITE,
            border=ft.border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.BLACK)),
            content=ft.Markdown(
                value,
                selectable=False, 
                extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
                on_tap_link=handle_link_tap 
            ),
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
            bgcolor=ft.Colors.WHITE,
            border=ft.border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.BLACK)),
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
    def render_cards_block(value, lesson):
        cards_list = value
        card_idx = [0]

        card_text = ft.Text(
            cards_list[0] if cards_list else "No cards",
            size=22, weight=ft.FontWeight.W_600, text_align=ft.TextAlign.CENTER,
        )

        counter_text = ft.Text(
            f"1 / {len(cards_list)}",
            color=ft.Colors.ON_SURFACE_VARIANT,
            weight=ft.FontWeight.BOLD,
        )

        def update():
            card_text.value = cards_list[card_idx[0]]
            counter_text.value = f"{card_idx[0] + 1} / {len(cards_list)}"
            lesson["_page"].update()

        return ft.Container(
            padding=40,
            border_radius=16,
            bgcolor=ft.Colors.BLUE_50,
            content=ft.Column(
                [
                    ft.Container(card_text, expand=True, alignment=ft.Alignment(0, 0)),
                    ft.Row(
                        [
                            ft.IconButton(ft.Icons.ARROW_BACK_IOS_ROUNDED, on_click=lambda e: (card_idx.__setitem__(0, max(card_idx[0] - 1, 0)), update())),
                            counter_text,
                            ft.IconButton(ft.Icons.ARROW_FORWARD_IOS_ROUNDED, on_click=lambda e: (card_idx.__setitem__(0, min(card_idx[0] + 1, len(cards_list) - 1)), update())),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ]
            ),
        )

    # =========================================================
    # 5. LESSON TYPE RENDERERS
    # =========================================================
    def render_scenario_ui(lesson: dict):
        content = lesson.get("content", {})
        scenario_text = content.get("scenario", "")
        choices = content.get("choices", [])
        
        consequence_box = ft.Container(
            padding=20,
            border_radius=12,
            bgcolor=ft.Colors.BLUE_50,
            border=ft.border.all(1, ft.Colors.BLUE_200),
            visible=False, 
            content=ft.Column([
                ft.Row([ft.Icon(ft.Icons.LIGHTBULB_CIRCLE, color=ft.Colors.BLUE_700), ft.Text("Result", weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900)]),
                ft.Markdown("", selectable=False, extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED)
            ])
        )

        buttons_col = ft.Column(spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        
        def handle_choice(idx, cons_text):
            for i, btn in enumerate(buttons_col.controls):
                if i == idx:
                    btn.bgcolor = UI_ACCENT
                    btn.color = ft.Colors.WHITE
                else:
                    btn.bgcolor = ft.Colors.TRANSPARENT
                    btn.color = UI_ACCENT
            
            consequence_box.content.controls[1].value = cons_text
            consequence_box.visible = True
            lesson["_page"].update()

        for idx, ch in enumerate(choices):
            btn = ft.OutlinedButton(
                content=ch.get("text", f"Option {idx+1}"),
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), padding=20),
                on_click=lambda e, i=idx, c_t=ch.get("consequence", ""): handle_choice(i, c_t)
            )
            buttons_col.controls.append(btn)

        return ft.Container(
            padding=25,
            border_radius=16,
            bgcolor=ft.Colors.WHITE,
            border=ft.border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.BLACK)),
            content=ft.Column(
                [
                    ft.Row([
                        ft.Icon(ft.Icons.CALL_SPLIT_ROUNDED, color=UI_ACCENT, size=28),
                        ft.Text("Decision Matrix", weight=ft.FontWeight.BOLD, size=18, color=UI_ACCENT)
                    ]),
                    ft.Text(scenario_text, size=16, color=ft.Colors.ON_SURFACE),
                    ft.Divider(height=10, color=ft.Colors.OUTLINE_VARIANT),
                    ft.Text("What is the best course of action?", weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE_VARIANT),
                    buttons_col,
                    ft.Container(height=5),
                    consequence_box
                ],
                spacing=10,
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
                
            q_text = ft.Text(q_text_str, weight=ft.FontWeight.BOLD, size=16, color=text_color)

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
                        check_color=ft.Colors.WHITE if is_completed else UI_ACCENT,
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
                    bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.BLACK) if is_completed else ft.Colors.WHITE,
                    border=ft.border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.BLACK)),
                    content=ft.Column([
                        ft.Row([q_text, ft.Icon(ft.Icons.LOCK_ROUNDED, color=ft.Colors.GREY_400, size=18) if is_completed else ft.Container()], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
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
                    padding=15, border_radius=12, bgcolor=ft.Colors.GREEN_50, border=ft.border.all(1, ft.Colors.GREEN_200),
                    content=ft.Row([
                        ft.Icon(ft.Icons.VERIFIED_ROUNDED, color=ft.Colors.GREEN_600),
                        ft.Text("You have already passed this assessment.", weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_800)
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
            padding=ft.padding.symmetric(horizontal=6, vertical=2),
            border_radius=4,
            bgcolor=ft.Colors.with_opacity(0.08, UI_ACCENT) if is_active_lesson else ft.Colors.with_opacity(0.05, ft.Colors.BLACK),
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
            bgcolor=ft.Colors.with_opacity(0.06, UI_ACCENT) if is_active_lesson else ft.Colors.WHITE,
            border=ft.border.only(
                left=ft.border.BorderSide(3, UI_ACCENT if is_active_lesson else ft.Colors.TRANSPARENT),
                bottom=ft.border.BorderSide(1, ft.Colors.with_opacity(0.05, ft.Colors.BLACK)),
            ),
            padding=ft.padding.symmetric(horizontal=14, vertical=11),
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
                        padding=ft.padding.symmetric(vertical=10),
                    )

                    def close_dialog_and_go(e=None):
                        dialog.open = False
                        page.go("/dashboard")
                        page.update()

                    dialog = ft.AlertDialog(
                        modal=True,
                        shape=ft.RoundedRectangleBorder(radius=20),
                        content_padding=0,
                        content=ft.Container(
                            width=460,
                            bgcolor=ft.Colors.WHITE,
                            border_radius=20,
                            clip_behavior=ft.ClipBehavior.HARD_EDGE,
                            content=ft.Column(
                                [
                                    ft.Container(
                                        padding=ft.padding.symmetric(horizontal=30, vertical=28),
                                        gradient=ft.LinearGradient(
                                            begin=ft.Alignment.TOP_LEFT,
                                            end=ft.Alignment.BOTTOM_RIGHT,
                                            colors=[ft.Colors.AMBER_400, ft.Colors.ORANGE_400],
                                        ),
                                        content=ft.Column(
                                            [
                                                ft.Container(
                                                    bgcolor=ft.Colors.with_opacity(0.25, ft.Colors.WHITE),
                                                    border_radius=50, padding=16, alignment=ft.Alignment(0, 0),
                                                    width=80, height=80,
                                                    content=ft.Icon(ft.Icons.WORKSPACE_PREMIUM_ROUNDED, size=44, color=ft.Colors.WHITE),
                                                ),
                                                ft.Container(height=14),
                                                ft.Text("Congratulations!", size=26, weight=ft.FontWeight.W_900, color=ft.Colors.WHITE, text_align=ft.TextAlign.CENTER),
                                                ft.Text(f"You've completed {course_data.get('course_title', 'the course')}!", size=14, color=ft.Colors.with_opacity(0.88, ft.Colors.WHITE), text_align=ft.TextAlign.CENTER),
                                            ],
                                            horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True, spacing=0,
                                        ),
                                    ),
                                    ft.Container(
                                        padding=ft.padding.symmetric(horizontal=28, vertical=18),
                                        content=ft.Column(
                                            [
                                                ft.Container(height=18),
                                                cert_action_container,
                                            ],
                                            horizontal_alignment=ft.CrossAxisAlignment.STRETCH, spacing=0,
                                        ),
                                    ),
                                    ft.Container(
                                        padding=ft.padding.only(left=28, right=28, bottom=24),
                                        content=ft.TextButton("Return to Dashboard", style=ft.ButtonStyle(color=ft.Colors.ON_SURFACE_VARIANT), on_click=close_dialog_and_go),
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
                                padding=ft.padding.symmetric(vertical=8, horizontal=12),
                                border_radius=10, bgcolor=ft.Colors.RED_50, border=ft.border.all(1, ft.Colors.RED_200),
                                content=ft.Column(
                                    spacing=10, 
                                    controls=[
                                        ft.Row([
                                            ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, color=ft.Colors.RED_600, size=20),
                                            ft.Text("Could not generate certificate. Please try again later.", color=ft.Colors.RED_700, size=13, expand=True),
                                        ], vertical_alignment=ft.CrossAxisAlignment.START),
                                        ft.ElevatedButton(
                                            content="Retry", color=ft.Colors.WHITE, bgcolor=ft.Colors.RED, align=ft.Alignment.CENTER,
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
                                                ft.Icon(ft.Icons.DOWNLOAD_ROUNDED, color=ft.Colors.WHITE, size=18),
                                                ft.Text("Download Certificate", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD, size=14),
                                            ], tight=True, spacing=8, alignment=ft.MainAxisAlignment.CENTER,
                                        ),
                                        style=ft.ButtonStyle(bgcolor=UI_ACCENT, shape=ft.RoundedRectangleBorder(radius=10), padding=ft.Padding(24, 14, 24, 14), elevation=0),
                                        on_click=handle_cert_download, expand=True,
                                    ),
                                    ft.Container(
                                        padding=ft.padding.symmetric(horizontal=12, vertical=8), border_radius=8,
                                        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.BLACK), border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
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
        color=ft.Colors.WHITE,
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
                    tile_padding=ft.padding.symmetric(horizontal=14, vertical=4),
                    controls_padding=ft.padding.only(left=0, right=0, bottom=0),
                    collapsed_bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.BLACK),
                    bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.BLACK),
                    collapsed_text_color=ft.Colors.ON_SURFACE,
                    text_color=ft.Colors.ON_SURFACE,
                    collapsed_icon_color=ft.Colors.ON_SURFACE_VARIANT,
                    icon_color=ft.Colors.ON_SURFACE_VARIANT,
                    shape=ft.RoundedRectangleBorder(radius=0),
                    collapsed_shape=ft.RoundedRectangleBorder(radius=0),
                    controls=[
                        ft.Container(
                            bgcolor=ft.Colors.WHITE,
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
                action_button.color = ft.Colors.WHITE
                action_button.disabled = False
        else:
            next_btn_text = "Finish Course 🎓" if is_last_overall else "Next Lesson →"
            action_button.bgcolor = UI_ACCENT
            action_button.color = ft.Colors.WHITE
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
        async def on_previous_click(e):
            if captured_module_idx != current_module_idx or captured_lesson_idx != current_lesson_idx:
                return
            if previous_button.disabled: return

            previous_button.disabled = True
            action_button.disabled = True
            page.update()
            await go_to_previous_lesson()

        async def on_action_click(e):
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
                    padding=ft.padding.symmetric(vertical=14),
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
                            padding=12, border_radius=8, bgcolor=ft.Colors.with_opacity(0.05, color), border=ft.border.all(1, ft.Colors.with_opacity(0.20, color)),
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
                        width=450, height=650, bgcolor=ft.Colors.WHITE, border_radius=12,
                        content=ft.Column(
                            [
                                ft.Container(
                                    padding=20, bgcolor=score_color, border_radius=ft.border_radius.only(top_left=12, top_right=12),
                                    content=ft.Column(
                                        [
                                            ft.Row([ft.Icon(status_icon, color=ft.Colors.WHITE, size=28), ft.Text(f"Assessment {status_text}", weight=ft.FontWeight.BOLD, size=20, color=ft.Colors.WHITE)], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
                                            ft.Text(f"You scored {score_percentage}%", color=ft.Colors.WHITE, size=17, weight=ft.FontWeight.W_500, text_align=ft.TextAlign.CENTER),
                                        ],
                                        horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6,
                                    ),
                                ),
                                ft.Container(
                                    padding=ft.padding.symmetric(horizontal=20), expand=True,
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
                                    padding=ft.padding.symmetric(horizontal=20, vertical=16), border=ft.border.only(top=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
                                    content=ft.Row(
                                        [
                                            ft.OutlinedButton("Retry Assessment", icon=ft.Icons.REPLAY_ROUNDED, on_click=close_and_retry) if not passed else ft.Container(),
                                            ft.Button("Continue Course", icon=ft.Icons.ARROW_FORWARD_ROUNDED, bgcolor=UI_ACCENT, color=ft.Colors.WHITE, align=ft.Alignment.CENTER, on_click=close_and_continue) if passed else ft.Container(),
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
            padding=ft.padding.symmetric(horizontal=20, vertical=18),
            border_radius=HEADER_RADIUS,
            bgcolor=ft.Colors.WHITE,
            border=ft.border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.BLACK)),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(active_mod["title"].upper(), size=11, weight=ft.FontWeight.BOLD, color=UI_ACCENT),
                            ft.Text("·", color=ft.Colors.ON_SURFACE_VARIANT, size=11),
                            ft.Container(
                                padding=ft.padding.symmetric(horizontal=8, vertical=4), border_radius=999, bgcolor=ft.Colors.with_opacity(0.10, UI_ACCENT),
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
                ft.Container(height=16),
                render_lesson_ui(active_les),
                ft.Container(height=24),
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
            padding=ft.padding.only(top=16), border=ft.border.only(top=ft.border.BorderSide(1, ft.Colors.with_opacity(0.06, ft.Colors.BLACK))),
            content=ft.Column(action_footer_controls, spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
        )

        main_content_area.content = ft.Container(
            padding=ft.padding.all(16), border_radius=16, bgcolor=ft.Colors.SURFACE,
            shadow=ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.05, ft.Colors.BLACK), offset=ft.Offset(0, 2)),
            content=ft.Column([lesson_body_scroll, action_footer_container], expand=True, spacing=0, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
        )

        refresh_layout_shell()
        page.update()
    # =========================================================
    # 9. ASYNC BACKGROUND DATA FETCHER
    # =========================================================

    async def fetch_initial_data():
        nonlocal course_data, current_module_idx, current_lesson_idx, module_expanded_state

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
        route=f"/courses/{course_id}/learn",
        bottom_appbar=app_bar,
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
        padding=0,
        appbar=page_appbar,
        controls=[
            ft.SafeArea(
                expand=True,
                content=content_socket,
            )
        ],
    )