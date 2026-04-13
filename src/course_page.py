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
        }
        return labels.get(lesson_type, "LESSON")

    # =========================================================
    # 1. API LAYER (EASY TO REPLACE)
    # =========================================================
    # Replace only the functions in this section when connecting
    # to your real backend/API. Everything below consumes this
    # layer and should not need structural changes.
    # =========================================================

    async def api_fetch_course_data(c_id: str):
        # Initial load simulated API: Returns user's persisted progress via 'is_done'
        course_data = await get_course_curriculum(token,course_id)
        print(course_data)
        return course_data

    async def api_save_progress(lesson_id: str):
        # Fires to the backend every time a lesson is completed
        print(f"API: Saving progress... Lesson {lesson_id} marked as done.")
        return True

    async def api_verify_module_completion(module_id: str):
        return True

    async def api_submit_assessment(lesson_id: str, answers: dict):
        print(f"API: Grading Assessment {lesson_id} with payload: {answers}")
        await asyncio.sleep(1.5)  # Simulated backend processing time
        return {"passed": True, "score": 100}

    # =========================================================
    # 2. STATE MANAGEMENT
    # =========================================================

    course_data = await api_fetch_course_data(course_id)

    current_module_idx = 0
    current_lesson_idx = 0
    sidebar_visible = False
    current_assessment_state = {}

    # Automatically scan course payload on load to jump to the current active lesson
    for m_idx, mod in enumerate(course_data["modules"]):
        if not mod.get("is_done", False):
            current_module_idx = m_idx
            for l_idx, les in enumerate(mod.get("lessons", [])):
                if not les.get("is_done", False):
                    current_lesson_idx = l_idx
                    break
            break

    # Sidebar-only expansion state
    module_expanded_state = {
        mod["id"]: (idx == current_module_idx)
        for idx, mod in enumerate(course_data["modules"])
    }

    # =========================================================
    # 3. CORE UI CONTAINERS
    # =========================================================

    sidebar_column = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=0)
    lesson_body_scroll = ft.Container(expand=True)
    action_footer_container = ft.Container()
    main_content_area = ft.Container(expand=True, padding=0)
    body_host = ft.Container(expand=True)

    close_sidebar_button = ft.IconButton(
        ft.Icons.CLOSE,
        icon_size=18,
        on_click=lambda e: toggle_sidebar(e),
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
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=14, vertical=12),
                    bgcolor=UI_ACCENT,
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.MENU_BOOK_ROUNDED, color=ft.Colors.WHITE, size=16),
                            ft.Text(
                                course_data["course_title"],
                                color=ft.Colors.WHITE,
                                weight=ft.FontWeight.BOLD,
                                size=13,
                                expand=True,
                            ),
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

    menu_button = ft.IconButton(
        icon=ft.Icons.MENU,
        icon_color=ft.Colors.WHITE,
        on_click=lambda e: toggle_sidebar(e),
        tooltip="Course Menu",
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
                        width=1,
                        thickness=1,
                        color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK),
                    ),
                    ft.Container(
                        expand=True,
                        padding=ft.padding.all(16),
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

    def toggle_sidebar(e):
        nonlocal sidebar_visible

        if is_desktop_layout():
            return

        sidebar_visible = not sidebar_visible
        refresh_layout_shell()
        page.update()
        # =========================================================
    # CONTENT UI RENDERERS (KEY-DRIVEN, ORDER-PRESERVING)
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
                        left=0,
                        right=0,
                        top=0,
                        height=60,
                    ),
                ],
                expand=True,
            ),
        )
        
    @register_content_renderer("accompanying_text")
    def render_notes_block(value, lesson):
        return ft.Container(
            padding=18,
            border_radius=12,
            bgcolor=ft.Colors.WHITE,
            border=ft.border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.BLACK)),
            content=ft.Column(
                [
                    ft.Text("Instructor Notes", weight=ft.FontWeight.BOLD, size=15),
                    ft.Text(value, size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.START,
            ),
        )
        
    @register_content_renderer("document_url")
    def render_document_block(value, lesson):
        file_name = lesson["content"].get("file_name", "Document")

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
                        on_click=lambda e: lesson["_page"].launch_url(value),
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=14,
            ),
        )
        
    @register_content_renderer("text")
    def render_text_block(value, lesson):
        return ft.Container(
            padding=24,
            border_radius=14,
            bgcolor=ft.Colors.WHITE,
            border=ft.border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.BLACK)),
            content=ft.Markdown(
                value,
                selectable=True,
                extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
            ),
        )
    @register_content_renderer("audio_path")
    def render_audio_block(value, lesson):
        file_name = lesson["content"].get("file_name", "Audio Lesson")

        return ft.Container(
            padding=40,
            border_radius=14,
            bgcolor=ft.Colors.WHITE,
            border=ft.border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.BLACK)),
            alignment=ft.Alignment(0, 0),
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.AUDIO_FILE_ROUNDED, size=56, color=ft.Colors.PRIMARY),
                    ft.Text(
                        file_name,
                        weight=ft.FontWeight.BOLD,
                        size=18,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.ElevatedButton(
                        "Download Audio",
                        icon=ft.Icons.DOWNLOAD,
                        on_click=lambda e: lesson["_page"].launch_url(value),
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
            size=22,
            weight=ft.FontWeight.W_600,
            text_align=ft.TextAlign.CENTER,
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
                            ft.IconButton(
                                ft.Icons.ARROW_BACK_IOS_ROUNDED,
                                on_click=lambda e: (
                                    card_idx.__setitem__(0, max(card_idx[0] - 1, 0)),
                                    update(),
                                ),
                            ),
                            counter_text,
                            ft.IconButton(
                                ft.Icons.ARROW_FORWARD_IOS_ROUNDED,
                                on_click=lambda e: (
                                    card_idx.__setitem__(0, min(card_idx[0] + 1, len(cards_list) - 1)),
                                    update(),
                                ),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ]
            ),
        )

    # =========================================================
    # 5. LESSON TYPE RENDERERS
    # =========================================================
    def render_assessment_ui(lesson: dict):
        content = lesson.get("content", {})
        questions = content.get("questions", [])

        current_assessment_state.clear()
        question_cards = []

        for q_idx, q in enumerate(questions):
            q_text = ft.Text(
                f"Q{q_idx + 1}: {q.get('text', '')}",
                weight=ft.FontWeight.BOLD,
                size=16,
            )

            options_group = ft.RadioGroup(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Radio(value=opt.get("text")),
                                ft.Text(opt.get("text"), expand=True),
                            ],
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
                    content=ft.Column(
                        [
                            q_text,
                            ft.Divider(height=1),
                            options_group,
                        ],
                        spacing=15,
                    ),
                )
            )

        return ft.Container(
            width=None,              # full width
            padding=0,
            content=ft.Column(
                question_cards,
                spacing=20,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        )


    def render_lesson_ui(lesson: dict):
        content = lesson.get("content", {})
        blocks = []

        # Inject page reference for blocks that need it
        lesson["_page"] = page

        for key, value in content.items():
            # Skip assessment questions (handled separately)
            if key == "questions":
                continue

            renderer = CONTENT_RENDERERS.get(key)
            if renderer:
                blocks.append(renderer(value, lesson))

        # Assessment remains special
        if lesson["type"] == "assessment":
            blocks.append(render_assessment_ui(lesson))

        return ft.Column(
            blocks,
            spacing=20,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    # =========================================================
    # 6. SIDEBAR HELPERS
    # =========================================================

    def build_sidebar_lesson_row(les, m_idx, l_idx, is_active_lesson):
        is_done = les.get("is_done", False)

        if is_done:
            lesson_icon = ft.Icon(ft.Icons.CHECK_CIRCLE, size=14, color=ft.Colors.GREEN)
        elif is_active_lesson:
            lesson_icon = ft.Icon(
                ft.Icons.PLAY_CIRCLE_FILL_ROUNDED,
                size=14,
                color=UI_ACCENT,
            )
        else:
            lesson_icon = ft.Icon(
                ft.Icons.CIRCLE_OUTLINED,
                size=12,
                color=ft.Colors.GREY_500,
            )

        return ft.Container(
            ink=True,
            on_click=lambda e, m=m_idx, l=l_idx: jump_to_lesson(m, l),
            bgcolor=ft.Colors.with_opacity(0.06, UI_ACCENT) if is_active_lesson else ft.Colors.WHITE,
            border=ft.border.only(
                left=ft.border.BorderSide(
                    4,
                    UI_ACCENT if is_active_lesson else ft.Colors.TRANSPARENT,
                ),
                bottom=ft.border.BorderSide(
                    1,
                    ft.Colors.with_opacity(0.05, ft.Colors.BLACK),
                ),
            ),
            padding=ft.padding.symmetric(horizontal=12, vertical=10),
            content=ft.Row(
                [
                    ft.Container(
                        width=18,
                        alignment=ft.Alignment(0, 0),
                        content=lesson_icon,
                    ),
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
                        title=ft.Text(
                            "🎉 Course Completed!",
                            weight=ft.FontWeight.BOLD,
                            size=24,
                        ),
                        content=ft.Text(
                            f"You have fully mastered {course_data['course_title']}."
                        ),
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
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=6),
        ),
    )

    def refresh_ui():
        sidebar_column.controls.clear()

        # ---------- Sidebar ----------
        for m_idx, mod in enumerate(course_data["modules"]):
            is_active_module = m_idx == current_module_idx

            lesson_controls = []
            for l_idx, les in enumerate(mod.get("lessons", [])):
                is_active_lesson = is_active_module and (l_idx == current_lesson_idx)
                lesson_controls.append(
                    build_sidebar_lesson_row(les, m_idx, l_idx, is_active_lesson)
                )

            sidebar_column.controls.append(
                ft.ExpansionTile(
                    title=ft.Text(
                        mod["title"],
                        weight=ft.FontWeight.BOLD,
                        size=12.5,
                    ),
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
                    snack = ft.SnackBar(
                        content=ft.Text("Please answer all questions before submitting!"),
                        bgcolor=ft.Colors.ERROR,
                    )
                    page.overlay.append(snack)
                    snack.open = True
                    page.update()
                    return

                action_button.content = ft.Row(
                    [
                        ft.ProgressRing(width=20, height=20, color=ft.Colors.WHITE, stroke_width=2),
                        ft.Text("Grading...", weight=ft.FontWeight.BOLD),
                    ],
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
                        title=ft.Row(
                            [
                                ft.Icon(ft.Icons.VERIFIED_ROUNDED, color=ft.Colors.GREEN, size=30),
                                ft.Text("Assessment Passed!"),
                            ]
                        ),
                        content=ft.Text(f"Great job! You scored {result['score']}% on this section."),
                        actions=[
                            ft.ElevatedButton(
                                content=ft.Text("Continue"),
                                bgcolor=UI_ACCENT,
                                color=ft.Colors.WHITE,
                                on_click=lambda e: handle_assessment_success(result, result_dialog),
                            )
                        ],
                        actions_alignment=ft.MainAxisAlignment.CENTER,
                    )
                    page.overlay.append(result_dialog)
                    result_dialog.open = True
                    page.update()
                else:
                    snack = ft.SnackBar(
                        content=ft.Text("Submission failed. Try again."),
                        bgcolor=ft.Colors.ERROR,
                    )
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
                            ft.Text(
                                active_mod["title"].upper(),
                                size=12,
                                weight=ft.FontWeight.BOLD,
                                color=UI_ACCENT,
                            ),
                            ft.Container(
                                padding=ft.padding.symmetric(horizontal=10, vertical=6),
                                border_radius=999,
                                bgcolor=ft.Colors.with_opacity(0.10, UI_ACCENT),
                                content=ft.Text(
                                    get_lesson_type_label(active_les["type"]),
                                    size=11,
                                    weight=ft.FontWeight.BOLD,
                                    color=UI_ACCENT,
                                ),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.START,
                        spacing=10,
                        wrap=True,
                    ),
                    ft.Text(
                        active_les["title"],
                        size=28,
                        weight=ft.FontWeight.W_900,
                        color=ft.Colors.ON_SURFACE,
                        text_align=ft.TextAlign.LEFT,
                    ),
                ],
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.START,
            ),
        )

        lesson_body_scroll.content = ft.Column(
            [
                header_container,
                ft.Container(height=18),
                render_lesson_ui(active_les),
                ft.Container(height=24),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

        # ---------------- FOOTER (EXACT PLACEMENT) ----------------

        is_assessment = active_les["type"] == "assessment"

        action_footer_controls = []

        if is_assessment:
            # ✅ Assessment: SUBMIT ONLY
            action_footer_controls.append(
                ft.Row([action_button], spacing=0)
            )
        else:
            # ✅ Normal lesson navigation
            if not is_first_overall:
                action_footer_controls.append(
                    ft.Row([previous_button], spacing=0)
                )

            action_footer_controls.append(
                ft.Row([action_button], spacing=0)
            )

        action_footer_container.content = ft.Container(
            padding=ft.padding.only(top=14),
            border=ft.border.only(
                top=ft.border.BorderSide(
                    1, ft.Colors.with_opacity(0.06, ft.Colors.BLACK)
                )
            ),
            content=ft.Column(
                action_footer_controls,
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        )

# ----------------------------------------------------------
            
        main_content_area.content = ft.Container(
            padding=ft.padding.all(16),
            border_radius=16,
            bgcolor=ft.Colors.SURFACE,
            content=ft.Column(
                [
                    lesson_body_scroll,
                    action_footer_container,
                ],
                expand=True,
                spacing=0,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        )

        refresh_layout_shell()
        page.update()

    # =========================================================
    # 9. INITIAL RENDER
    # =========================================================

    refresh_ui()

    # =========================================================
    # 10. VIEW RETURN
    # =========================================================

    return ft.View(
        route=f"/courses/{course_id}/learn",
        bottom_appbar=app_bar,
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
        padding=0,
        appbar=ft.AppBar(
            leading=menu_button,
            title=ft.Text(
                course_data["course_title"],
                size=18,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.WHITE,
            ),
            center_title=False,
            bgcolor=UI_ACCENT,
        ),
        controls=[
            ft.SafeArea(
                expand=True,
                content=body_host,
            )
        ],
    )