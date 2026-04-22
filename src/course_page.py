import flet as ft
from flet_video import Video, VideoMedia
import asyncio
from src.components.bottom_appbar import get_bottom_appbar
from src.requests.Courses import get_course_curriculum

async def course_learner_view(page: ft.Page, course_id: str):
    token = await page.shared_preferences.get("auth_token")
    app_bar = get_bottom_appbar(page)

    # =========================================================
    # 0. THEME / LAYOUT CONFIG
    # =========================================================

    UI_ACCENT = ft.Colors.PRIMARY
    SIDEBAR_WIDTH = 320
    DESKTOP_BREAKPOINT = 1024
    ACTION_BUTTON_HEIGHT = 35
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
            "assignment": "ASSIGNMENT",
        }
        return labels.get(lesson_type, "LESSON")

    # =========================================================
    # 1. API LAYER
    # =========================================================
    async def api_submit_assignment(lesson_id: str, file_name: str, file_bytes: bytes):
        # Calculate size just to prove the bytes arrived successfully
        size_kb = len(file_bytes) / 1024 if file_bytes else 0
        print(f"API: Uploading '{file_name}' ({size_kb:.2f} KB) for lesson {lesson_id}")
        
        return {
            "success": True, 
            "message": "Assignment submitted successfully! Your instructor will review it and email your results."
        }

    async def api_fetch_course_data(c_id: str):
        course_data = await get_course_curriculum(token, course_id)
        return course_data

    async def api_save_progress(lesson_id: str):
        print(f"API: Saving progress... Lesson {lesson_id} marked as done.")
        return True

    async def api_verify_module_completion(module_id: str):
        return True

    async def api_submit_assessment(lesson_id: str, answers: dict):
        print(f"API: Grading Assessment {lesson_id} with payload: {answers}")
        await asyncio.sleep(1.5)  # Simulated backend processing time
        return {"passed": True, "score": 100}

    # =========================================================
    # 2. STATE MANAGEMENT (Initialized Empty)
    # =========================================================
    
    course_data = None
    current_module_idx = 0
    current_lesson_idx = 0
    sidebar_visible = False
    current_assessment_state = {}
    module_expanded_state = {}

    # --- THE LAZY LOAD SOCKET ---
    content_socket = ft.Container(
        expand=True, 
        alignment=ft.Alignment.CENTER, 
        content=ft.Row([
            ft.ProgressRing(color=UI_ACCENT, stroke_width=3),
            ft.Text(" Loading curriculum...", color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500)
        ], alignment=ft.MainAxisAlignment.CENTER)
    )

    # =========================================================
    # 3. CORE UI CONTAINERS
    # =========================================================

    sidebar_column = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=0)
    lesson_body_scroll = ft.Container(expand=True)
    action_footer_container = ft.Container()
    main_content_area = ft.Container(expand=True, padding=0)
    body_host = ft.Container(expand=True)

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
        icon=ft.Icons.MENU,
        icon_color=ft.Colors.WHITE,
        on_click=toggle_sidebar,
        tooltip="Course Menu",
        visible=False # Hidden initially
    )

    # Dynamic Course Title for Sidebar (Updated after fetch)
    sidebar_course_title = ft.Text(
        "Loading...",
        color=ft.Colors.WHITE,
        weight=ft.FontWeight.BOLD,
        size=13,
        expand=True,
    )

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
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=12, vertical=10),
                    border=ft.border.only(
                        bottom=ft.border.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.BLACK))
                    ),
                    bgcolor=ft.Colors.WHITE,
                    content=ft.Row(
                        [
                            ft.Text("Course Menu", weight=ft.FontWeight.BOLD, size=14, color=ft.Colors.ON_SURFACE),
                            close_sidebar_button,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ),
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=14, vertical=12),
                    bgcolor=UI_ACCENT,
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.MENU_BOOK_ROUNDED, color=ft.Colors.WHITE, size=16),
                            sidebar_course_title,
                        ],
                        spacing=8,
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

    # Dynamic App Bar Title (Updated after fetch)
    appbar_title = ft.Text(
        "Loading Course...",
        size=18,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.WHITE,
    )

    page_appbar = ft.AppBar(
        leading=ft.IconButton(ft.Icons.ARROW_BACK_ROUNDED, icon_color=ft.Colors.WHITE, on_click=lambda _: page.go("/courses")),
        title=appbar_title,
        center_title=False,
        bgcolor=UI_ACCENT,
        actions=[menu_button]
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
                    ft.VerticalDivider(width=1, thickness=1, color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK)),
                    ft.Container(expand=True, padding=ft.padding.all(16), content=main_content_area),
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
                    ft.Container(expand=True, padding=ft.padding.all(12), content=main_content_area),
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
    @register_content_renderer("prompt_text")
    def render_assignment_ui(lesson: dict):
        prompt = lesson.get("content", {}).get("prompt_text", "")
        status_text = ft.Text("No file selected", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        
        selected_file = [{"name": None, "bytes": None}] 

        submit_btn = ft.ElevatedButton(
            "Submit Assignment",
            icon=ft.Icons.SEND_ROUNDED,
            bgcolor=UI_ACCENT,
            color=ft.Colors.WHITE,
            disabled=True, 
        )

        async def handle_upload(e):
            files = await ft.FilePicker().pick_files(
                allow_multiple=False,
                with_data=True 
            )
            
            if files:
                f = files[0]
                file_bytes = getattr(f, "bytes", None)

                if not file_bytes and getattr(f, "path", None):
                    try:
                        with open(f.path, "rb") as fp:
                            file_bytes = fp.read()
                    except Exception:
                        file_bytes = None

                if file_bytes:
                    selected_file[0] = {"name": f.name, "bytes": file_bytes}
                    status_text.value = f"Selected: {f.name}"
                    status_text.color = ft.Colors.GREEN_700
                    submit_btn.disabled = False 
                else:
                    status_text.value = "Failed to read file data."
                    status_text.color = ft.Colors.RED_700
                    submit_btn.disabled = True
                    
                lesson["_page"].update()

        async def handle_submit(e):
            if not selected_file[0]["bytes"]:
                return

            # Trigger Loading State
            submit_btn.disabled = True
            submit_btn.content = ft.Row([
                ft.ProgressRing(width=16, height=16, color=ft.Colors.WHITE, stroke_width=2),
                ft.Text("Uploading...", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
            ], alignment=ft.MainAxisAlignment.CENTER)
            lesson["_page"].update()

            # Pass the actual file bytes to the API
            result = await api_submit_assignment(
                lesson["id"], 
                selected_file[0]["name"], 
                selected_file[0]["bytes"]
            )

            if result.get("success"):
                # Lock the button into a "Success" state
                submit_btn.content = ft.Text("Submitted for Grading", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
                submit_btn.icon = ft.Icons.CHECK_CIRCLE
                submit_btn.bgcolor = ft.Colors.GREEN_600
                
                # Show the non-blocking toast
                snack = ft.SnackBar(content=ft.Text(result["message"]), bgcolor=ft.Colors.GREEN_700)
                lesson["_page"].overlay.append(snack)
                snack.open = True
            else:
                # Reset if upload fails
                submit_btn.content = ft.Text("Submit Assignment", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
                submit_btn.disabled = False
                
                snack = ft.SnackBar(content=ft.Text("Upload failed. Try again."), bgcolor=ft.Colors.RED_700)
                lesson["_page"].overlay.append(snack)
                snack.open = True
                
            lesson["_page"].update()

        submit_btn.on_click = handle_submit

        return ft.Container(
            padding=25,
            border_radius=16,
            bgcolor=ft.Colors.WHITE,
            border=ft.border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.BLACK)),
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.ASSIGNMENT_ROUNDED, color=UI_ACCENT, size=28),
                    ft.Text("Project Assignment", weight=ft.FontWeight.BOLD, size=18, color=UI_ACCENT)
                ]),
                ft.Markdown(prompt, selectable=False, extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED),
                ft.Divider(height=10, color=ft.Colors.OUTLINE_VARIANT),
                ft.Row([
                    ft.OutlinedButton("Select File", icon=ft.Icons.ATTACH_FILE_ROUNDED, on_click=handle_upload),
                    status_text
                ]),
                ft.Container(height=10),
                submit_btn 
            ], spacing=15)
        )
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

        current_assessment_state.clear()
        question_cards = []

        for q_idx, q in enumerate(questions):
            q_text = ft.Text(f"Q{q_idx + 1}: {q.get('text', '')}", weight=ft.FontWeight.BOLD, size=16)

            options_group = ft.RadioGroup(
                content=ft.Column(
                    [
                        ft.Row(
                            [ft.Radio(value=opt.get("text")), ft.Text(opt.get("text"), expand=True)],
                            vertical_alignment=ft.CrossAxisAlignment.START,
                        )
                        for opt in q.get("options", [])
                    ],
                    spacing=10,
                )
            )

            current_assessment_state[f"question_{q_idx + 1}"] = options_group

            question_cards.append(
                ft.Container(
                    padding=25,
                    border_radius=16,
                    bgcolor=ft.Colors.WHITE,
                    border=ft.border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.BLACK)),
                    content=ft.Column([q_text, ft.Divider(height=1), options_group], spacing=15),
                )
            )

        return ft.Container(
            width=None,
            padding=0,
            content=ft.Column(question_cards, spacing=20, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
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
        elif lesson["type"] == "assignment":
            blocks.append(render_assignment_ui(lesson))

        return ft.Column(blocks, spacing=20, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    # =========================================================
    # 6. SIDEBAR HELPERS
    # =========================================================

    def build_sidebar_lesson_row(les, m_idx, l_idx, is_active_lesson):
        is_done = les.get("is_done", False)

        if is_done:
            lesson_icon = ft.Icon(ft.Icons.CHECK_CIRCLE, size=14, color=ft.Colors.GREEN)
        elif is_active_lesson:
            lesson_icon = ft.Icon(ft.Icons.PLAY_CIRCLE_FILL_ROUNDED, size=14, color=UI_ACCENT)
        else:
            lesson_icon = ft.Icon(ft.Icons.CIRCLE_OUTLINED, size=12, color=ft.Colors.GREY_500)

        return ft.Container(
            ink=True,
            on_click=lambda e, m=m_idx, l=l_idx: jump_to_lesson(m, l),
            bgcolor=ft.Colors.with_opacity(0.06, UI_ACCENT) if is_active_lesson else ft.Colors.WHITE,
            border=ft.border.only(
                left=ft.border.BorderSide(4, UI_ACCENT if is_active_lesson else ft.Colors.TRANSPARENT),
                bottom=ft.border.BorderSide(1, ft.Colors.with_opacity(0.05, ft.Colors.BLACK)),
            ),
            padding=ft.padding.symmetric(horizontal=12, vertical=10),
            content=ft.Row(
                [
                    ft.Container(width=18, alignment=ft.Alignment(0, 0), content=lesson_icon),
                    ft.Text(
                        les["title"],
                        size=12.5,
                        weight=ft.FontWeight.BOLD if is_active_lesson else ft.FontWeight.NORMAL,
                        color=UI_ACCENT if is_active_lesson else ft.Colors.ON_SURFACE,
                        expand=True,
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
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

        if not active_les.get("is_done", False):
            await api_save_progress(active_les["id"])
            active_les["is_done"] = True

        is_last_lesson = current_lesson_idx >= len(active_mod["lessons"]) - 1

        if is_last_lesson:
            if await api_verify_module_completion(active_mod["id"]):
                active_mod["is_done"] = True

                if current_module_idx >= len(course_data["modules"]) - 1:
                    dialog = ft.AlertDialog(
                        title=ft.Text("🎉 Course Completed!", weight=ft.FontWeight.BOLD, size=24),
                        content=ft.Text(f"You have fully mastered {course_data['course_title']}."),
                        actions=[
                            ft.ElevatedButton(
                                content=ft.Text("Return to Dashboard"),
                                bgcolor=UI_ACCENT,
                                color=ft.Colors.WHITE,
                                on_click=lambda e: page.go("/dashboard"),
                            )
                        ],
                        actions_alignment=ft.MainAxisAlignment.CENTER,
                    )
                    page.overlay.append(dialog)
                    dialog.open = True
                    page.update()
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
        bgcolor=ft.Colors.WHITE,
        color=UI_ACCENT,
        height=ACTION_BUTTON_HEIGHT,
        expand=True,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=6),
            side=ft.BorderSide(1, UI_ACCENT),
        ),
        visible=False,
    )

    action_button = ft.Button(
        bgcolor=UI_ACCENT,
        color=ft.Colors.WHITE,
        height=ACTION_BUTTON_HEIGHT,
        expand=True,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6)),
    )

    def refresh_ui():
        sidebar_column.controls.clear()

        # ---------- Sidebar ----------
        for m_idx, mod in enumerate(course_data["modules"]):
            is_active_module = m_idx == current_module_idx

            lesson_controls = []
            for l_idx, les in enumerate(mod.get("lessons", [])):
                is_active_lesson = is_active_module and (l_idx == current_lesson_idx)
                lesson_controls.append(build_sidebar_lesson_row(les, m_idx, l_idx, is_active_lesson))

            sidebar_column.controls.append(
                ft.ExpansionTile(
                    title=ft.Text(mod["title"], weight=ft.FontWeight.BOLD, size=12.5),
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
                    controls=[ft.Container(bgcolor=ft.Colors.WHITE, content=ft.Column(lesson_controls, spacing=0))],
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

        if active_les["type"] == "assessment":
            next_btn_text = "Submit & Finish Course" if is_last_overall else "Submit Assessment"
        else:
            next_btn_text = "Finish Course" if is_last_overall else "Next Lesson"

        previous_button.content = ft.Text("Previous Lesson", weight=ft.FontWeight.BOLD)
        previous_button.visible = not is_first_overall
        previous_button.disabled = False

        action_button.content = ft.Text(next_btn_text, weight=ft.FontWeight.BOLD)
        action_button.disabled = False

        async def on_previous_click(e):
            await go_to_previous_lesson()

        async def on_action_click(e):
            if active_les["type"] == "assessment":
                payload = {q_key: rg.value for q_key, rg in current_assessment_state.items()}

                if None in payload.values():
                    snack = ft.SnackBar(content=ft.Text("Please answer all questions before submitting!"), bgcolor=ft.Colors.ERROR)
                    page.overlay.append(snack)
                    snack.open = True
                    page.update()
                    return

                action_button.content = ft.Row(
                    [ft.ProgressRing(width=20, height=20, color=ft.Colors.WHITE, stroke_width=2), ft.Text("Grading...", weight=ft.FontWeight.BOLD)],
                    alignment=ft.MainAxisAlignment.CENTER,
                )
                action_button.disabled = True
                previous_button.disabled = True
                page.update()

                result = await api_submit_assessment(active_les["id"], payload)

                action_button.content = ft.Text(next_btn_text, weight=ft.FontWeight.BOLD)
                action_button.disabled = False
                previous_button.disabled = False
                page.update()

                if result.get("passed"):
                    result_dialog = ft.AlertDialog(
                        title=ft.Row([ft.Icon(ft.Icons.VERIFIED_ROUNDED, color=ft.Colors.GREEN, size=30), ft.Text("Assessment Passed!")]),
                        content=ft.Text(f"Great job! You scored {result['score']}% on this section."),
                        actions=[ft.ElevatedButton(content=ft.Text("Continue"), bgcolor=UI_ACCENT, color=ft.Colors.WHITE, on_click=lambda e: handle_assessment_success(result, result_dialog))],
                        actions_alignment=ft.MainAxisAlignment.CENTER,
                    )
                    page.overlay.append(result_dialog)
                    result_dialog.open = True
                    page.update()
                else:
                    snack = ft.SnackBar(content=ft.Text("Submission failed. Try again."), bgcolor=ft.Colors.ERROR)
                    page.overlay.append(snack)
                    snack.open = True
                    page.update()
            else:
                await advance_to_next_lesson()

        previous_button.on_click = on_previous_click
        action_button.on_click = on_action_click

        header_container = ft.Container(
            padding=ft.padding.symmetric(horizontal=20, vertical=18),
            border_radius=HEADER_RADIUS,
            bgcolor=ft.Colors.WHITE,
            border=ft.border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.BLACK)),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(active_mod["title"].upper(), size=12, weight=ft.FontWeight.BOLD, color=UI_ACCENT),
                            ft.Container(
                                padding=ft.padding.symmetric(horizontal=10, vertical=6),
                                border_radius=999,
                                bgcolor=ft.Colors.with_opacity(0.10, UI_ACCENT),
                                content=ft.Text(get_lesson_type_label(active_les["type"]), size=11, weight=ft.FontWeight.BOLD, color=UI_ACCENT),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.START, spacing=10, wrap=True,
                    ),
                    ft.Text(active_les["title"], size=28, weight=ft.FontWeight.W_900, color=ft.Colors.ON_SURFACE, text_align=ft.TextAlign.LEFT),
                ],
                spacing=12, horizontal_alignment=ft.CrossAxisAlignment.START,
            ),
        )

        lesson_body_scroll.content = ft.Column(
            [
                header_container,
                ft.Container(height=18),
                render_lesson_ui(active_les),
                ft.Container(height=24),
            ],
            scroll=ft.ScrollMode.AUTO, expand=True, spacing=0, horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

        # ---------------- FOOTER ----------------
        is_assessment = active_les["type"] == "assessment"
        action_footer_controls = []

        if is_assessment:
            action_footer_controls.append(ft.Row([action_button], spacing=0))
        else:
            if not is_first_overall:
                action_footer_controls.append(ft.Row([previous_button], spacing=0))
            action_footer_controls.append(ft.Row([action_button], spacing=0))

        action_footer_container.content = ft.Container(
            padding=ft.padding.only(top=14),
            border=ft.border.only(top=ft.border.BorderSide(1, ft.Colors.with_opacity(0.06, ft.Colors.BLACK))),
            content=ft.Column(action_footer_controls, spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
        )
            
        main_content_area.content = ft.Container(
            padding=ft.padding.all(16),
            border_radius=16,
            bgcolor=ft.Colors.SURFACE,
            content=ft.Column(
                [lesson_body_scroll, action_footer_container],
                expand=True, spacing=0, horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        )

        refresh_layout_shell()
        page.update()

    # =========================================================
    # 9. ASYNC BACKGROUND DATA FETCHER
    # =========================================================

    async def fetch_initial_data():
        nonlocal course_data, current_module_idx, current_lesson_idx, module_expanded_state
        
        # Await the API call in the background
        course_data = await api_fetch_course_data(course_id)
        
        if not course_data or "modules" not in course_data:
            content_socket.alignment = ft.Alignment.CENTER
            content_socket.content = ft.Text("Failed to load course data.", color=ft.Colors.ERROR)
            page.update()
            return

        # Scan course payload to jump to the current active lesson
        for m_idx, mod in enumerate(course_data["modules"]):
            if not mod.get("is_done", False):
                current_module_idx = m_idx
                for l_idx, les in enumerate(mod.get("lessons", [])):
                    if not les.get("is_done", False):
                        current_lesson_idx = l_idx
                        break
                break

        # Setup sidebar expansion state
        module_expanded_state = {
            mod["id"]: (idx == current_module_idx)
            for idx, mod in enumerate(course_data["modules"])
        }

        # Update dynamic App Bar and Sidebar titles
        appbar_title.value = course_data["course_title"]
        sidebar_course_title.value = course_data["course_title"]

        # Render the initial UI
        refresh_ui()

        # Swap the loading ring out for the actual body host
        content_socket.alignment = None
        content_socket.content = body_host
        page.update()

    # Trigger the background fetch task
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