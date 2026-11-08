import asyncio
import base64
from typing import Callable, Optional

import flet as ft
from src.course_builder import render_lesson_preview
from src.requests.Courses import (
    create_course,
    generate_course_draft,
    get_categories,
)
from src.requests.organisations import get_organisation_members
from src.utils.dropdown_theme import apply_dropdown_theme, get_dropdown_menu_style
from src.utils.file_opener import show_page_snackbar

DEFAULT_ORG_ID = "584b537e-6521-4852-a7e4-18f6c095126d"

LESSON_TYPE_INFO = {
    "text": ("Reading", ft.Icons.NOTES_ROUNDED, ft.Colors.BLUE_600, "Interactive reading material with rich Markdown and callouts"),
    "video": ("Video", ft.Icons.PLAY_CIRCLE_FILL_ROUNDED, ft.Colors.RED_600, "Video lecture or demonstration walkthrough"),
    "assessment": ("Assessment", ft.Icons.QUIZ_ROUNDED, ft.Colors.PURPLE_600, "Multiple-choice exam, module quiz, or capstone test"),
    "code_lab": ("Code Lab", ft.Icons.CODE_ROUNDED, ft.Colors.AMBER_700, "Hands-on browser code playground with test cases"),
    "cards": ("Flashcards", ft.Icons.VIEW_CAROUSEL_ROUNDED, ft.Colors.GREEN_600, "Active recall flashcard deck with flip animation"),
    "sequencer": ("Sequencer", ft.Icons.FORMAT_LIST_NUMBERED_ROUNDED, ft.Colors.TEAL_600, "Step sequence ordering challenge"),
    "scenario": ("Scenario", ft.Icons.CALL_SPLIT_ROUNDED, ft.Colors.ORANGE_600, "Branching real-world decision dilemma"),
    "document": ("Document", ft.Icons.DESCRIPTION_ROUNDED, ft.Colors.BLUE_GREY_600, "Reference PDF, slides, or syllabus download"),
    "audio": ("Audio", ft.Icons.AUDIOTRACK_ROUNDED, ft.Colors.PINK_600, "Audio recording, podcast, or spoken explanation"),
}


def open_course_creation_studio(
    page: ft.Page,
    org_id: Optional[str] = None,
    on_course_created: Optional[Callable[[dict], None]] = None,
):
    """
    Parallel AI Course Creation Studio (Path 2).
    A high-productivity side-by-side workspace:
    - Left Pane: Complete Course Metadata (Title, Category with smart match, Description, Objectives,
      Target Audience, Visibility, Delivery mode, Auto-Certificates, Instructor, and Cover Photo with
      AI recommendation, URL link, or local device upload).
    - Right Pane: Full-Fledged Curriculum Builder (Modules management, Lesson creation across 9 types,
      rich Content Editor for each lesson type, and Live Student Preview via render_lesson_preview).
    - AI Drafter: Synthesizes course metadata, multi-module curriculum, and capstone exam simultaneously
      from attached PDFs, Markdown notes, and study photos.
    - 1-Click Atomic Publish: Saves course record and full curriculum in one single transaction.
    """
    user_data = {}
    if hasattr(page, "session") and hasattr(page.session, "store"):
        user_data = page.session.store.get("current_user") or {}
    elif hasattr(page, "session") and hasattr(page.session, "get"):
        user_data = page.session.get("current_user") or {}

    current_user_id = user_data.get("id") if isinstance(user_data, dict) else None
    current_user_role = user_data.get("role") if isinstance(user_data, dict) else None
    is_freelance = (not org_id) or (current_user_role != "Admin")
    effective_org_id = org_id or DEFAULT_ORG_ID

    # --- State ---
    modules_state = []
    objectives_list = []
    is_studio_open = [True]
    is_synthesizing_active = [False]

    # --- Live Non-Blocking Generation Progress Banner ---
    generation_stage_text = ft.Text(
        "Initializing AI synthesis...",
        size=12,
        weight=ft.FontWeight.W_500,
        color=ft.Colors.PURPLE_900,
    )
    generation_timer_text = ft.Text("0s elapsed", size=11, color=ft.Colors.PURPLE_700)
    generation_progress_bar = ft.ProgressBar(
        value=None,
        color=ft.Colors.PURPLE_600,
        bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.PURPLE_600),
        height=4,
        border_radius=ft.BorderRadius.all(2),
    )
    generation_progress_banner = ft.Container(
        visible=False,
        padding=ft.Padding.symmetric(horizontal=16, vertical=10),
        border_radius=12,
        bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.PURPLE_600),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.25, ft.Colors.PURPLE_600)),
        content=ft.Column([
            ft.Row([
                ft.Row([
                    ft.ProgressRing(width=16, height=16, color=ft.Colors.PURPLE_700, stroke_width=2),
                    ft.Text("AI Studio Synthesizer Active", size=12.5, weight=ft.FontWeight.BOLD, color=ft.Colors.PURPLE_900),
                ], spacing=8, tight=True),
                ft.Row([
                    generation_timer_text,
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                        border_radius=6,
                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PURPLE_800),
                        content=ft.Text("Non-Blocking / Background Polling", size=10, weight=ft.FontWeight.W_600, color=ft.Colors.PURPLE_900),
                    ),
                ], spacing=8, tight=True),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            generation_progress_bar,
            generation_stage_text,
        ], spacing=6),
    )

    def _clean_modules_for_save(raw_mods):
        clean_mods = []
        for mi, mod in enumerate(raw_mods or []):
            if not isinstance(mod, dict):
                continue
            clean_lessons = []
            for li, les in enumerate(mod.get("lessons", [])):
                if not isinstance(les, dict):
                    continue
                clean_content = les.get("content", {})
                if isinstance(clean_content, dict):
                    clean_content = {str(k): v for k, v in clean_content.items() if not str(k).startswith("_")}
                clean_lessons.append({
                    "id": les.get("id"),
                    "title": les.get("title", f"Lesson {li+1}"),
                    "type": les.get("type", "text"),
                    "order_index": li,
                    "content": clean_content if isinstance(clean_content, dict) else {},
                })
            clean_mods.append({
                "id": mod.get("id"),
                "title": mod.get("title", f"Module {mi+1}"),
                "order_index": mi,
                "lessons": clean_lessons,
            })
        return clean_mods
    categories_list = []
    selected_image_bytes = None
    selected_image_name = None
    custom_image_url = None
    is_mobile_tab_active = 0  # 0: Course Metadata, 1: Curriculum Builder

    w_val = getattr(page, "width", None)
    screen_w = int(w_val) if isinstance(w_val, (int, float)) and w_val > 0 else 1000
    h_val = getattr(page, "height", None)
    screen_h = int(h_val) if isinstance(h_val, (int, float)) and h_val > 0 else 720
    is_desktop = screen_w >= 920
    studio_w = min(screen_w - 24, 1260)
    studio_h = min(screen_h - 40, 800)

    # ─────────────────────────────────────────────────────────────────────────
    # LEFT PANE CONTROLS (COMPLETE COURSE METADATA)
    # ─────────────────────────────────────────────────────────────────────────
    title_field = ft.TextField(
        label="Course Title *",
        hint_text="e.g. Modern Full-Stack Web Engineering",
        border_radius=10,
        text_size=13,
        border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
        focused_border_color=ft.Colors.PRIMARY,
    )

    desc_field = ft.TextField(
        label="Course Overview & Summary",
        hint_text="Comprehensive summary of course scope and outcomes…",
        multiline=True,
        min_lines=3,
        max_lines=4,
        border_radius=10,
        text_size=12.5,
        border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
        focused_border_color=ft.Colors.PRIMARY,
    )

    audience_field = ft.TextField(
        label="Target Audience & Prerequisites (Optional)",
        hint_text="e.g. Undergraduate CS students with Python fundamentals",
        multiline=True,
        min_lines=1,
        max_lines=2,
        border_radius=10,
        text_size=12,
        border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
        focused_border_color=ft.Colors.PRIMARY,
    )

    category_dropdown = apply_dropdown_theme(
        ft.Dropdown(
            label="Category *",
            options=[],
            border_radius=10,
            text_size=13,
            dense=True,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        ),
        menu_height=260,
    )

    visibility_dropdown = apply_dropdown_theme(
        ft.Dropdown(
            label="Catalog Visibility",
            value="false",
            options=[
                ft.dropdown.Option("false", "Draft (Private)"),
                ft.dropdown.Option("organisation", "Organisation Members"),
                ft.dropdown.Option("true", "Public Catalog"),
            ],
            border_radius=10,
            text_size=12.5,
            dense=True,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        ),
        menu_height=260,
    )

    teacher_dropdown = apply_dropdown_theme(
        ft.Dropdown(
            label="Assign Instructor",
            options=[],
            border_radius=10,
            text_size=12.5,
            dense=True,
            visible=not is_freelance,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        ),
        menu_height=260,
    )

    auto_cert_switch = ft.Switch(
        label="Auto-Issue Certificate",
        value=True,
        active_color=ft.Colors.GREEN_600,
    )

    supervised_switch = ft.Switch(
        label="Instructor-Led Cohort",
        value=False,
        active_color=ft.Colors.PRIMARY,
    )

    # --- Learning Objectives Chips ---
    objectives_wrap = ft.Row(wrap=True, spacing=6, run_spacing=6)

    def _render_objectives():
        objectives_wrap.controls.clear()
        for idx, obj in enumerate(objectives_list):
            def _remove(e, target_idx=idx):
                if 0 <= target_idx < len(objectives_list):
                    objectives_list.pop(target_idx)
                    _render_objectives()
                    page.update()

            objectives_wrap.controls.append(
                ft.Chip(
                    label=ft.Text(obj, size=11),
                    delete_icon=ft.Icon(ft.Icons.CLOSE_ROUNDED, size=12),
                    on_delete=_remove,
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                    shape=ft.RoundedRectangleBorder(radius=8),
                )
            )

    def _add_objective(e=None):
        val = (obj_input.value or "").strip()
        if val and val not in objectives_list:
            objectives_list.append(val)
            obj_input.value = ""
            _render_objectives()
            page.update()

    obj_input = ft.TextField(
        label="Add learning outcome & press Enter",
        text_size=12,
        border_radius=8,
        content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
        focused_border_color=ft.Colors.PRIMARY,
        on_submit=_add_objective,
        suffix=ft.IconButton(
            ft.Icons.ADD_CIRCLE_OUTLINE_ROUNDED,
            icon_size=18,
            icon_color=ft.Colors.PRIMARY,
            on_click=_add_objective,
        ),
    )

    # --- Cover Image Management (AI Recommendation, Custom URL, or Local Upload) ---
    cover_preview_img = ft.Image(src="", width=80, height=52, fit=ft.BoxFit.COVER, border_radius=8, visible=False)
    cover_icon = ft.Icon(ft.Icons.ADD_PHOTO_ALTERNATE_OUTLINED, color=ft.Colors.PRIMARY, size=24)
    cover_title = ft.Text("Course Cover Photo", size=12.5, weight=ft.FontWeight.W_600)
    cover_sub = ft.Text("Upload local image, accept AI recommendation, or paste URL", size=10.5, color=ft.Colors.ON_SURFACE_VARIANT)
    custom_url_input = ft.TextField(
        label="Or paste Image URL",
        hint_text="https://images.unsplash.com/...",
        text_size=11.5,
        dense=True,
        border_radius=8,
        content_padding=ft.Padding.symmetric(horizontal=10, vertical=6),
        border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
        focused_border_color=ft.Colors.PRIMARY,
        visible=False,
    )

    def _on_custom_url_change(e):
        nonlocal custom_image_url, selected_image_bytes, selected_image_name
        val = (custom_url_input.value or "").strip()
        if val:
            custom_image_url = val
            selected_image_bytes = None
            selected_image_name = None
            cover_preview_img.src = val
            cover_preview_img.visible = True
            cover_icon.visible = False
            cover_sub.value = "Custom Image URL active"
            cover_sub.color = ft.Colors.GREEN_700
        else:
            custom_image_url = None
            cover_preview_img.visible = False
            cover_icon.visible = True
        page.update()

    custom_url_input.on_change = _on_custom_url_change

    async def _pick_local_cover(e=None):
        nonlocal selected_image_bytes, selected_image_name, custom_image_url
        try:
            files = await ft.FilePicker().pick_files(
                allow_multiple=False,
                file_type=ft.FilePickerFileType.IMAGE,
                with_data=True,
            )
            if files and len(files) > 0:
                selected_image_bytes = files[0].bytes
                selected_image_name = files[0].name
                custom_image_url = None
                custom_url_input.value = ""
                cover_preview_img.src = f"data:image/jpeg;base64,{base64.b64encode(selected_image_bytes).decode('utf-8')}"
                cover_preview_img.visible = True
                cover_icon.visible = False
                cover_sub.value = f"Selected local file: {selected_image_name}"
                cover_sub.color = ft.Colors.GREEN_700
                page.update()
        except Exception as ex:
            cover_sub.value = f"Pick error: {ex}"
            cover_sub.color = ft.Colors.RED_600
            page.update()

    def _toggle_url_field(e=None):
        custom_url_input.visible = not custom_url_input.visible
        page.update()

    def _clear_cover(e=None):
        nonlocal selected_image_bytes, selected_image_name, custom_image_url
        selected_image_bytes = None
        selected_image_name = None
        custom_image_url = None
        custom_url_input.value = ""
        cover_preview_img.visible = False
        cover_preview_img.src = None
        cover_preview_img.src = None
        cover_icon.visible = True
        cover_sub.value = "Upload local image, accept AI recommendation, or paste URL"
        cover_sub.color = ft.Colors.ON_SURFACE_VARIANT
        page.update()

    cover_container = ft.Container(
        padding=12,
        border_radius=10,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE)),
        bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
        content=ft.Column([
            ft.Row([
                cover_preview_img,
                cover_icon,
                ft.Column([cover_title, cover_sub], spacing=2, expand=True),
                ft.PopupMenuButton(
                    icon=ft.Icons.MORE_VERT_ROUNDED,
                    tooltip="Cover Options",
                    items=[
                        ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.FILE_UPLOAD_OUTLINED, size=16), ft.Text("Upload from Local Device", size=12)], spacing=6), on_click=_pick_local_cover),
                        ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.LINK_ROUNDED, size=16), ft.Text("Enter Custom Image URL", size=12)], spacing=6), on_click=_toggle_url_field),
                        ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.DELETE_OUTLINE_ROUNDED, size=16, color=ft.Colors.RED_600), ft.Text("Clear Cover Photo", size=12, color=ft.Colors.RED_600)], spacing=6), on_click=_clear_cover),
                    ],
                ),
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            custom_url_input,
        ], spacing=8),
    )

    # ─────────────────────────────────────────────────────────────────────────
    # RIGHT PANE CONTROLS (FULL-FLEDGED CURRICULUM BUILDER)
    # ─────────────────────────────────────────────────────────────────────────
    curriculum_col = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO)
    stats_badge = ft.Text("0 Modules • 0 Lessons", size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_600)

    # --- Live Student Preview Modal (invoking render_lesson_preview) ---
    def open_lesson_preview_modal(lesson: dict):
        preview_content = render_lesson_preview(lesson, page)
        preview_content.scroll = ft.ScrollMode.AUTO
        preview_content.expand = True

        def _close_prev(e=None):
            prev_dlg.open = False
            page.update()

        l_type = lesson.get("type", "text")
        type_name, icon_name, color_tok, _ = LESSON_TYPE_INFO.get(l_type, ("Lesson", ft.Icons.NOTES_ROUNDED, ft.Colors.PRIMARY, ""))

        prev_dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=16),
            bgcolor=ft.Colors.SURFACE,
            title=ft.Row([
                ft.Icon(icon_name, color=color_tok, size=20),
                ft.Text(f"Student Preview: {lesson.get('title', 'Untitled')}", size=15, weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Container(
                width=min(screen_w - 40, 720),
                height=min(screen_h - 100, 560),
                content=preview_content,
            ),
            actions=[ft.TextButton("Close Preview", on_click=_close_prev)],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(prev_dlg)
        prev_dlg.open = True
        page.update()

    # --- Full Lesson Content Editor Modal (rich editing for all 9 types) ---
    def open_lesson_content_editor(lesson: dict, module: dict):
        l_type = lesson.get("type", "text")
        content = lesson.setdefault("content", {})
        type_name, icon_name, color_tok, _ = LESSON_TYPE_INFO.get(l_type, ("Lesson", ft.Icons.NOTES_ROUNDED, ft.Colors.PRIMARY, ""))

        les_title_field = ft.TextField(
            label="Lesson Title",
            value=lesson.get("title", ""),
            border_radius=8,
            dense=True,
            text_size=13,
            border_color=ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE),
        )

        editor_fields = [les_title_field]

        if l_type == "text":
            text_body = ft.TextField(
                label="Interactive Markdown Content",
                value=content.get("text") or content.get("notes") or "",
                multiline=True,
                min_lines=8,
                max_lines=16,
                border_radius=8,
                text_size=12,
                border_color=ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE),
            )
            editor_fields.append(text_body)

            def _save_text():
                content["text"] = text_body.value
                content["notes"] = text_body.value

            save_fn = _save_text

        elif l_type == "video":
            video_url = ft.TextField(
                label="Video URL (YouTube or Direct MP4)",
                value=content.get("url", ""),
                border_radius=8,
                dense=True,
                text_size=12.5,
                border_color=ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE),
            )
            editor_fields.append(video_url)

            def _save_video():
                content["url"] = video_url.value

            save_fn = _save_video

        elif l_type == "assessment":
            questions_list = content.setdefault("questions", [])
            questions_col = ft.Column(spacing=8)

            def _render_questions_editor():
                questions_col.controls.clear()
                for q_i, q_item in enumerate(questions_list):
                    q_stem_field = ft.TextField(
                        label=f"Question {q_i + 1} Stem",
                        value=q_item.get("question", ""),
                        border_radius=8,
                        dense=True,
                        text_size=12,
                    )
                    q_ans_field = ft.TextField(
                        label="Correct Answer",
                        value=q_item.get("answer", ""),
                        border_radius=8,
                        dense=True,
                        text_size=12,
                    )
                    q_exp_field = ft.TextField(
                        label="Explanation",
                        value=q_item.get("explanation", ""),
                        border_radius=8,
                        dense=True,
                        text_size=11.5,
                    )

                    def _del_q(e, target_q_i=q_i):
                        if 0 <= target_q_i < len(questions_list):
                            questions_list.pop(target_q_i)
                            _render_questions_editor()
                            page.update()

                    def _sync_stem(e, target_q=q_item, tf=q_stem_field):
                        target_q["question"] = tf.value

                    def _sync_ans(e, target_q=q_item, tf=q_ans_field):
                        target_q["answer"] = tf.value

                    def _sync_exp(e, target_q=q_item, tf=q_exp_field):
                        target_q["explanation"] = tf.value

                    q_stem_field.on_change = _sync_stem
                    q_ans_field.on_change = _sync_ans
                    q_exp_field.on_change = _sync_exp

                    card = ft.Container(
                        padding=10,
                        border_radius=8,
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                        bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
                        content=ft.Column([
                            ft.Row([
                                ft.Text(f"Question {q_i + 1}", weight=ft.FontWeight.BOLD, size=12),
                                ft.IconButton(ft.Icons.DELETE_OUTLINE_ROUNDED, icon_size=16, on_click=_del_q),
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            q_stem_field,
                            q_ans_field,
                            q_exp_field,
                        ], spacing=6),
                    )
                    questions_col.controls.append(card)

            def _add_new_question(e):
                questions_list.append({
                    "question": "New Question",
                    "options": ["Option A", "Option B", "Option C", "Option D"],
                    "answer": "Option A",
                    "explanation": "Explanation for this answer.",
                })
                _render_questions_editor()
                page.update()

            _render_questions_editor()
            editor_fields.extend([
                ft.Row([
                    ft.Text("Exam / Quiz Questions", weight=ft.FontWeight.BOLD, size=13),
                    ft.TextButton("Add Question", icon=ft.Icons.ADD_ROUNDED, on_click=_add_new_question),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                questions_col,
            ])

            def _save_assessment():
                content["questions"] = questions_list

            save_fn = _save_assessment

        elif l_type == "code_lab":
            lang_field = apply_dropdown_theme(
                ft.Dropdown(
                    label="Language",
                    value=content.get("language", "python"),
                    options=[
                        ft.dropdown.Option("python", "Python"),
                        ft.dropdown.Option("javascript", "JavaScript"),
                        ft.dropdown.Option("sql", "SQL"),
                        ft.dropdown.Option("html", "HTML / CSS"),
                    ],
                    border_radius=8,
                    dense=True,
                    text_size=12,
                ),
                menu_height=200,
                border_radius=8,
            )
            starter_code_field = ft.TextField(
                label="Starter Code",
                value=content.get("starter_code", ""),
                multiline=True,
                min_lines=6,
                max_lines=10,
                border_radius=8,
                text_size=12,
            )
            solution_code_field = ft.TextField(
                label="Solution Code",
                value=content.get("solution_code", ""),
                multiline=True,
                min_lines=4,
                max_lines=8,
                border_radius=8,
                text_size=12,
            )
            editor_fields.extend([lang_field, starter_code_field, solution_code_field])

            def _save_codelab():
                content["language"] = lang_field.value
                content["starter_code"] = starter_code_field.value
                content["solution_code"] = solution_code_field.value

            save_fn = _save_codelab

        elif l_type == "cards":
            cards_list = content.setdefault("cards", [])
            cards_col = ft.Column(spacing=6)

            def _render_cards_editor():
                cards_col.controls.clear()
                for c_i, c_item in enumerate(cards_list):
                    front_field = ft.TextField(label="Front (Prompt)", value=c_item.get("front", ""), dense=True, text_size=11.5)
                    back_field = ft.TextField(label="Back (Recall)", value=c_item.get("back", ""), dense=True, text_size=11.5)

                    def _sync_front(e, target_c=c_item, tf=front_field):
                        target_c["front"] = tf.value

                    def _sync_back(e, target_c=c_item, tf=back_field):
                        target_c["back"] = tf.value

                    front_field.on_change = _sync_front
                    back_field.on_change = _sync_back

                    cards_col.controls.append(ft.Row([
                        ft.Container(expand=1, content=front_field),
                        ft.Container(expand=1, content=back_field),
                    ], spacing=6))

            def _add_new_card(e):
                cards_list.append({"front": "Term", "back": "Definition"})
                _render_cards_editor()
                page.update()

            _render_cards_editor()
            editor_fields.extend([
                ft.Row([
                    ft.Text(f"Flashcards ({len(cards_list)} cards)", weight=ft.FontWeight.BOLD, size=13),
                    ft.TextButton("Add Card", icon=ft.Icons.ADD_ROUNDED, on_click=_add_new_card),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                cards_col,
            ])

            def _save_cards():
                content["cards"] = cards_list

            save_fn = _save_cards
        else:
            save_fn = lambda: None

        def _close_ed(e=None):
            ed_dlg.open = False
            page.update()

        def _do_save_lesson(e=None):
            lesson["title"] = les_title_field.value or "Untitled Lesson"
            save_fn()
            _close_ed()
            _render_curriculum()
            page.update()
            show_page_snackbar(page, f"Lesson '{lesson['title']}' saved!")

        ed_dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=16),
            bgcolor=ft.Colors.SURFACE,
            title=ft.Row([
                ft.Icon(icon_name, color=color_tok, size=20),
                ft.Text(f"Edit {type_name} Lesson", size=15, weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Container(
                width=560,
                content=ft.Column(editor_fields, spacing=10, tight=True, scroll=ft.ScrollMode.AUTO),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=_close_ed),
                ft.FilledButton("Save Lesson Content", style=ft.ButtonStyle(bgcolor=color_tok), on_click=_do_save_lesson),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(ed_dlg)
        ed_dlg.open = True
        page.update()

    # --- Lesson Type Picker Dialog ---
    def open_lesson_type_picker(module: dict):
        def _close_picker(e=None):
            picker_dlg.open = False
            page.update()

        def _select_type(selected_t: str):
            _close_picker()
            new_les = {
                "id": "new",
                "title": f"New {LESSON_TYPE_INFO.get(selected_t, ('Lesson',))[0]}",
                "type": selected_t,
                "content": {},
            }
            module.setdefault("lessons", []).append(new_les)
            _render_curriculum()
            page.update()
            # Open content editor immediately for newly chosen lesson!
            open_lesson_content_editor(new_les, module)

        picker_options = []
        for type_key, (name, icon_n, col_tok, desc) in LESSON_TYPE_INFO.items():
            btn = ft.Container(
                padding=10,
                border_radius=10,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
                ink=True,
                on_click=lambda _, tk=type_key: _select_type(tk),
                content=ft.Row([
                    ft.Container(padding=6, border_radius=8, bgcolor=ft.Colors.with_opacity(0.12, col_tok), content=ft.Icon(icon_n, color=col_tok, size=20)),
                    ft.Column([
                        ft.Text(name, size=13, weight=ft.FontWeight.BOLD),
                        ft.Text(desc, size=10.5, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], spacing=2, expand=True),
                    ft.Icon(ft.Icons.ARROW_FORWARD_IOS_ROUNDED, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ], spacing=10),
            )
            picker_options.append(btn)

        picker_dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=16),
            bgcolor=ft.Colors.SURFACE,
            title=ft.Row([
                ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE_ROUNDED, color=ft.Colors.PRIMARY, size=22),
                ft.Text("Select Lesson Format", size=16, weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Container(
                width=460,
                content=ft.Column(picker_options, spacing=8, tight=True, scroll=ft.ScrollMode.AUTO),
            ),
            actions=[ft.TextButton("Cancel", on_click=_close_picker)],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(picker_dlg)
        picker_dlg.open = True
        page.update()

    # --- Add / Rename Module Modals ---
    def open_module_modal(module_to_edit: Optional[dict] = None):
        is_edit = module_to_edit is not None
        title_in = ft.TextField(
            label="Module Title",
            value=module_to_edit.get("title", "") if is_edit else f"Module {len(modules_state) + 1}",
            border_radius=8,
            autofocus=True,
            dense=True,
        )

        def _close_mod(e=None):
            mod_dlg.open = False
            page.update()

        def _save_mod(e=None):
            val = (title_in.value or "").strip()
            if not val:
                return
            if is_edit:
                module_to_edit["title"] = val
            else:
                modules_state.append({"title": val, "lessons": []})
            _close_mod()
            _render_curriculum()
            page.update()

        mod_dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=14),
            bgcolor=ft.Colors.SURFACE,
            title=ft.Text("Rename Module" if is_edit else "Add New Module", size=15, weight=ft.FontWeight.BOLD),
            content=ft.Container(width=360, content=title_in),
            actions=[
                ft.TextButton("Cancel", on_click=_close_mod),
                ft.FilledButton("Save", on_click=_save_mod),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(mod_dlg)
        mod_dlg.open = True
        page.update()

    # --- Render Curriculum Tree with Full Builder Actions ---
    def _render_curriculum():
        curriculum_col.controls.clear()
        total_modules = len(modules_state)
        total_lessons = sum(len(m.get("lessons", [])) for m in modules_state)
        stats_badge.value = f"{total_modules} Modules • {total_lessons} Lessons"

        if is_synthesizing_active[0] and not modules_state:
            curriculum_col.controls.append(
                ft.Container(
                    padding=36,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=10,
                        controls=[
                            ft.ProgressRing(width=36, height=36, color=ft.Colors.PURPLE_600, stroke_width=3),
                            ft.Text("AI Authoring Curriculum in Background...", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.PURPLE_900),
                            ft.Text(
                                "Your multi-module curriculum, lessons, assessments, and active-recall flashcards are being generated. You can continue editing course identity on the left.",
                                size=11.5,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ],
                    ),
                )
            )
            return

        if not modules_state:
            curriculum_col.controls.append(
                ft.Container(
                    padding=36,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=10,
                        controls=[
                            ft.Icon(ft.Icons.SCHEMA_OUTLINED, size=44, color=ft.Colors.with_opacity(0.35, ft.Colors.PRIMARY)),
                            ft.Text("No Curriculum Scaffolded Yet", size=15, weight=ft.FontWeight.BOLD),
                            ft.Text(
                                "Supply course materials (PDFs, notes, photos) to the AI Drafter above, or manually add modules and author lessons with the full-fledged builder below.",
                                size=11.5,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.FilledButton("Add First Module", icon=ft.Icons.ADD_ROUNDED, on_click=lambda _: open_module_modal(None)),
                        ],
                    ),
                )
            )
            return

        for m_idx, mod in enumerate(modules_state):
            m_title = mod.get("title", f"Module {m_idx + 1}")
            lessons = mod.setdefault("lessons", [])

            lesson_rows = []
            for l_idx, les in enumerate(lessons):
                l_title = les.get("title", f"Lesson {l_idx + 1}")
                l_type = les.get("type", "text")
                type_name, icon_n, col_tok, _ = LESSON_TYPE_INFO.get(l_type, ("Lesson", ft.Icons.NOTES_ROUNDED, ft.Colors.PRIMARY, ""))

                def _move_les_up(e, m_i=m_idx, l_i=l_idx):
                    if l_i > 0:
                        modules_state[m_i]["lessons"][l_i - 1], modules_state[m_i]["lessons"][l_i] = (
                            modules_state[m_i]["lessons"][l_i],
                            modules_state[m_i]["lessons"][l_i - 1],
                        )
                        _render_curriculum()
                        page.update()

                def _move_les_down(e, m_i=m_idx, l_i=l_idx):
                    if l_i < len(modules_state[m_i]["lessons"]) - 1:
                        modules_state[m_i]["lessons"][l_i], modules_state[m_i]["lessons"][l_i + 1] = (
                            modules_state[m_i]["lessons"][l_i + 1],
                            modules_state[m_i]["lessons"][l_i],
                        )
                        _render_curriculum()
                        page.update()

                def _delete_les(e, m_i=m_idx, l_i=l_idx):
                    if 0 <= m_i < len(modules_state) and 0 <= l_i < len(modules_state[m_i]["lessons"]):
                        modules_state[m_i]["lessons"].pop(l_i)
                        _render_curriculum()
                        page.update()

                row_card = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(
                                spacing=8,
                                expand=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Container(
                                        padding=4,
                                        border_radius=6,
                                        bgcolor=ft.Colors.with_opacity(0.12, col_tok),
                                        content=ft.Icon(icon_n, size=14, color=col_tok),
                                    ),
                                    ft.Container(
                                        expand=True,
                                        content=ft.Text(
                                            l_title,
                                            size=12,
                                            weight=ft.FontWeight.W_500,
                                            no_wrap=True,
                                            max_lines=1,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                        ),
                                    ),
                                ],
                            ),
                            ft.Row(
                                spacing=2,
                                tight=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Container(
                                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                        border_radius=6,
                                        bgcolor=ft.Colors.with_opacity(0.08, col_tok),
                                        content=ft.Text(
                                            type_name,
                                            size=9.5,
                                            color=col_tok,
                                            weight=ft.FontWeight.BOLD,
                                            no_wrap=True,
                                        ),
                                    ),
                                    ft.IconButton(
                                        ft.Icons.PLAY_ARROW_ROUNDED,
                                        icon_size=15,
                                        tooltip="Live Student Preview",
                                        visual_density=ft.VisualDensity.COMPACT,
                                        on_click=lambda _, tles=les: open_lesson_preview_modal(tles),
                                    ),
                                    ft.IconButton(
                                        ft.Icons.EDIT_OUTLINED,
                                        icon_size=14,
                                        tooltip="Edit Content",
                                        visual_density=ft.VisualDensity.COMPACT,
                                        on_click=lambda _, tles=les, tmod=mod: open_lesson_content_editor(tles, tmod),
                                    ),
                                    ft.IconButton(
                                        ft.Icons.ARROW_UPWARD_ROUNDED,
                                        icon_size=13,
                                        tooltip="Move Up",
                                        disabled=(l_idx == 0),
                                        visual_density=ft.VisualDensity.COMPACT,
                                        on_click=_move_les_up,
                                    ),
                                    ft.IconButton(
                                        ft.Icons.ARROW_DOWNWARD_ROUNDED,
                                        icon_size=13,
                                        tooltip="Move Down",
                                        disabled=(l_idx == len(lessons) - 1),
                                        visual_density=ft.VisualDensity.COMPACT,
                                        on_click=_move_les_down,
                                    ),
                                    ft.IconButton(
                                        ft.Icons.DELETE_OUTLINE_ROUNDED,
                                        icon_size=14,
                                        tooltip="Delete Lesson",
                                        visual_density=ft.VisualDensity.COMPACT,
                                        on_click=_delete_les,
                                    ),
                                ],
                            ),
                        ],
                    ),
                )
                lesson_rows.append(row_card)

            def _move_mod_up(e, target_m=m_idx):
                if target_m > 0:
                    modules_state[target_m - 1], modules_state[target_m] = modules_state[target_m], modules_state[target_m - 1]
                    _render_curriculum()
                    page.update()

            def _move_mod_down(e, target_m=m_idx):
                if target_m < len(modules_state) - 1:
                    modules_state[target_m], modules_state[target_m + 1] = modules_state[target_m + 1], modules_state[target_m]
                    _render_curriculum()
                    page.update()

            def _del_mod(e, target_m=m_idx):
                if 0 <= target_m < len(modules_state):
                    modules_state.pop(target_m)
                    _render_curriculum()
                    page.update()

            mod_container = ft.Container(
                padding=12,
                border_radius=12,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                bgcolor=ft.Colors.SURFACE,
                content=ft.Column([
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row([
                                ft.Container(padding=ft.Padding.symmetric(horizontal=7, vertical=3), border_radius=6, bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY), content=ft.Text(f"M{m_idx + 1}", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY)),
                                ft.Container(expand=True, content=ft.Text(m_title, size=13, weight=ft.FontWeight.BOLD, no_wrap=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)),
                                ft.IconButton(ft.Icons.DRIVE_FILE_RENAME_OUTLINE_ROUNDED, icon_size=14, tooltip="Rename Module", visual_density=ft.VisualDensity.COMPACT, on_click=lambda _, tmod=mod: open_module_modal(tmod)),
                            ], spacing=6, expand=True),
                            ft.Row([
                                ft.Text(f"{len(lessons)} lessons", size=10.5, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.IconButton(ft.Icons.ARROW_UPWARD_ROUNDED, icon_size=14, tooltip="Move Module Up", disabled=(m_idx == 0), visual_density=ft.VisualDensity.COMPACT, on_click=_move_mod_up),
                                ft.IconButton(ft.Icons.ARROW_DOWNWARD_ROUNDED, icon_size=14, tooltip="Move Module Down", disabled=(m_idx == len(modules_state) - 1), visual_density=ft.VisualDensity.COMPACT, on_click=_move_mod_down),
                                ft.IconButton(ft.Icons.DELETE_SWEEP_OUTLINED, icon_size=16, tooltip="Delete Module", visual_density=ft.VisualDensity.COMPACT, on_click=_del_mod),
                            ], spacing=2, tight=True),
                        ],
                    ),
                    ft.Column(spacing=4, controls=lesson_rows),
                    ft.Row([
                        ft.OutlinedButton(
                            "Add Lesson to Module",
                            icon=ft.Icons.ADD_ROUNDED,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                            on_click=lambda _, tmod=mod: open_lesson_type_picker(tmod),
                        ),
                    ], alignment=ft.MainAxisAlignment.END),
                ], spacing=8),
            )
            curriculum_col.controls.append(mod_container)

        # Bottom Add Module CTA
        curriculum_col.controls.append(
            ft.Row([
                ft.FilledButton(
                    "Add Another Module",
                    icon=ft.Icons.ADD_ROUNDED,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY), color=ft.Colors.PRIMARY, shape=ft.RoundedRectangleBorder(radius=8)),
                    on_click=lambda _: open_module_modal(None),
                ),
            ], alignment=ft.MainAxisAlignment.CENTER)
        )

    # ─────────────────────────────────────────────────────────────────────────
    # AI COURSE DRAFTER (WITH MULTI-MATERIAL & STUDY PHOTO SUPPORT)
    # ─────────────────────────────────────────────────────────────────────────
    def open_upgrade_required_dialog(org_info: dict, is_expired: bool = False):
        def _close_up(e=None):
            up_dlg.open = False
            page.update()

        def _go_to_plans(e=None):
            _close_up()
            from src.components.org.org_plan_modal import open_org_plan_modal
            auth_tok = getattr(page, "_active_auth_token", None) or ""
            open_org_plan_modal(
                page=page,
                org_data=org_info,
                theme_color=ft.Colors.PRIMARY,
                token=auth_tok,
            )

        title_text = "Academy Plan Expired" if is_expired else "Pro Academy Plan Required"
        body_text = (
            "Your organization's subscription has expired. Please renew your plan to continue using the AI Course Drafter."
            if is_expired
            else "AI Course Drafting is available on the Pro Academy and Enterprise plans. Upgrade your workspace to instantly synthesize multi-week curricula, quizzes, and flashcards from study materials."
        )

        up_dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=16),
            title=ft.Row([
                ft.Icon(ft.Icons.WORKSPACE_PREMIUM_ROUNDED, color=ft.Colors.PRIMARY, size=24),
                ft.Text(title_text, size=16, weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Container(
                width=420,
                content=ft.Column([
                    ft.Text(body_text, size=13, color=ft.Colors.ON_SURFACE),
                    ft.Container(height=6),
                    ft.Container(
                        padding=12,
                        border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.PRIMARY),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.18, ft.Colors.PRIMARY)),
                        content=ft.Column([
                            ft.Text("Pro Academy Perks:", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                            ft.Text("• AI Course & Assessment Synthesizer", size=11),
                            ft.Text("• Up to 100 Members & 25 Published Courses", size=11),
                            ft.Text("• Automated Completion Certificates", size=11),
                        ], spacing=3),
                    ),
                ], tight=True, spacing=10),
            ),
            actions=[
                ft.TextButton("Maybe Later", on_click=_close_up),
                ft.FilledButton(
                    "Renew Plan" if is_expired else "View Academy Plans",
                    style=ft.ButtonStyle(bgcolor=ft.Colors.PRIMARY, shape=ft.RoundedRectangleBorder(radius=8)),
                    on_click=_go_to_plans,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(up_dlg)
        up_dlg.open = True
        page.update()

    def open_ai_drafter_dialog(e=None):
        current_org = getattr(page, "_current_active_org", None)
        if current_org and isinstance(current_org, dict):
            p_features = current_org.get("plan", {}).get("features", []) if isinstance(current_org.get("plan"), dict) else []
            has_perk = any("ai" in str(f).lower() and "draft" in str(f).lower() for f in p_features)
            is_exp = current_org.get("is_expired") or current_org.get("subscription_status") == "expired"
            if not has_perk or is_exp:
                open_upgrade_required_dialog(current_org, is_expired=is_exp)
                return
        topic_in = ft.TextField(
            label="Course Topic or Subject",
            hint_text="e.g. Distributed Consensus Algorithms with Raft and Paxos",
            autofocus=True,
            multiline=True,
            min_lines=1,
            max_lines=3,
            border_radius=10,
            text_size=13,
        )

        ctx_in = ft.TextField(
            label="Target Audience & Context Guidance (Optional)",
            hint_text="e.g. Focus on practical Go implementations and fault recovery",
            multiline=True,
            min_lines=1,
            max_lines=2,
            border_radius=10,
            text_size=12.5,
        )

        selected_files = []
        selected_photo_payloads = []
        chips_row = ft.Row(wrap=True, spacing=5, run_spacing=5)
        status_txt = ft.Text("", size=11.5, color=ft.Colors.ON_SURFACE_VARIANT)

        def _refresh_chips():
            chips_row.controls.clear()
            for s_f in selected_files:
                def _rm(ev, target_name=s_f["name"]):
                    nonlocal selected_files, selected_photo_payloads
                    selected_files = [x for x in selected_files if x["name"] != target_name]
                    selected_photo_payloads = [p for p in selected_photo_payloads if p.get("name") != target_name]
                    _refresh_chips()
                    page.update()

                is_img = any(s_f["name"].lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp"))
                chips_row.controls.append(
                    ft.Chip(
                        leading=ft.Icon(ft.Icons.IMAGE_OUTLINED if is_img else ft.Icons.DESCRIPTION_OUTLINED, size=14, color=ft.Colors.PRIMARY),
                        label=ft.Text(s_f["name"], size=11),
                        delete_icon=ft.Icon(ft.Icons.CLOSE_ROUNDED, size=12),
                        on_delete=_rm,
                        bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                    )
                )

        async def _pick_materials(ev):
            try:
                picked = await ft.FilePicker().pick_files(
                    allow_multiple=True,
                    allowed_extensions=["pdf", "md", "txt", "png", "jpg", "jpeg", "webp"],
                    with_data=True,
                )
                if picked:
                    for f in picked:
                        if any(x["name"] == f.name for x in selected_files):
                            continue
                        f_name_lower = (f.name or "").lower()
                        # --- Images / Study Photos (Notes, Slides, Whiteboards) ---
                        if any(f_name_lower.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp")):
                            raw_bytes = f.bytes
                            if not raw_bytes and getattr(f, "path", None):
                                try:
                                    with open(f.path, "rb") as bf:
                                        raw_bytes = bf.read()
                                except Exception:
                                    pass
                            if raw_bytes:
                                mime = "image/png" if f_name_lower.endswith(".png") else "image/jpeg"
                                b64 = base64.b64encode(raw_bytes).decode("utf-8")
                                selected_photo_payloads.append({
                                    "name": f.name,
                                    "bytes": b64,
                                    "mime_type": mime,
                                })
                                selected_files.append({"name": f.name, "content": f"[Photo: {f.name}]"})
                        # --- PDF Documents (extract text up to 35 pages via PyMuPDF) ---
                        elif f_name_lower.endswith(".pdf"):
                            f_text = ""
                            try:
                                import fitz
                                doc = fitz.open(f.path) if getattr(f, "path", None) else (fitz.open(stream=f.bytes, filetype="pdf") if getattr(f, "bytes", None) else None)
                                if doc:
                                    pages = [doc[i].get_text().strip() for i in range(min(len(doc), 35)) if doc[i].get_text()]
                                    doc.close()
                                    f_text = "\n\n".join(pages).strip()
                            except Exception as px:
                                f_text = f"[PDF Error: {px}]"
                            selected_files.append({"name": f.name, "content": f_text})
                        # --- Markdown & Plain Text ---
                        else:
                            f_text = ""
                            if getattr(f, "path", None):
                                try:
                                    with open(f.path, "r", encoding="utf-8", errors="replace") as fo:
                                        f_text = fo.read()
                                except Exception:
                                    pass
                            elif getattr(f, "bytes", None):
                                f_text = f.bytes.decode("utf-8", errors="replace")
                            selected_files.append({"name": f.name, "content": f_text})

                    _refresh_chips()
                    page.update()
            except Exception as p_err:
                status_txt.value = f"Pick error: {p_err}"
                status_txt.color = ft.Colors.RED_600
                page.update()

        attach_btn = ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            border_radius=8,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.PURPLE_600)),
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.PURPLE_600),
            ink=True,
            on_click=_pick_materials,
            content=ft.Row([
                ft.Icon(ft.Icons.ATTACH_FILE_ROUNDED, size=18, color=ft.Colors.PURPLE_700),
                ft.Text("Attach Study Materials (.pdf, .md, .txt) & Notes Photos (.png, .jpg)", size=12, weight=ft.FontWeight.W_600),
            ], spacing=8),
        )

        def _close_draft_dlg(e=None):
            draft_dlg.open = False
            page.update()

        async def _run_background_synthesis(topic_val: str, final_context: str, photo_payloads: list):
            auth_tok = await page.shared_preferences.get("auth_token")

            def _on_poll_tick(elapsed: float):
                if not is_studio_open[0]:
                    return
                el_int = int(elapsed)
                generation_timer_text.value = f"{el_int}s elapsed"
                if el_int < 10:
                    generation_stage_text.value = "Analyzing topic, syllabus, and transcribing reference documents…"
                elif el_int < 25:
                    generation_stage_text.value = "Synthesizing multi-module curriculum, interactive lessons, and code labs…"
                elif el_int < 45:
                    generation_stage_text.value = "Formulating quiz assessments, active-recall flashcards, and study exercises…"
                else:
                    generation_stage_text.value = "Finalizing course blueprint, learning outcomes, and recommended cover…"
                page.update()

            res = await generate_course_draft(
                token=auth_tok,
                topic=topic_val or "Comprehensive Course",
                context=final_context,
                images=photo_payloads if photo_payloads else None,
                on_poll=_on_poll_tick,
            )

            is_synthesizing_active[0] = False

            # Check for plan gating error
            if not isinstance(res, dict) or res.get("error") or res.get("status") != "success":
                err = res.get("error", "AI generation encountered an issue") if isinstance(res, dict) else "Error"
                if is_studio_open[0]:
                    generation_progress_banner.visible = False
                    _render_curriculum()
                    page.update()
                    if err in ("plan_required", "plan_expired"):
                        open_upgrade_required_dialog(getattr(page, "_current_active_org", {}) or {}, is_expired=(err == "plan_expired"))
                        return
                    generation_progress_banner.visible = True
                    generation_progress_banner.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.RED_600)
                    generation_stage_text.value = f"AI Synthesis failed: {err}"
                    generation_stage_text.color = ft.Colors.RED_700
                    page.update()
                    show_page_snackbar(page, f"AI generation issue: {err}")
                return

            draft_data = res.get("data", {})
            new_mods = draft_data.get("modules", [])
            clean_new_mods = _clean_modules_for_save(new_mods)

            if is_studio_open[0]:
                # Studio is open! Populate live across both panes
                generation_progress_banner.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.GREEN_600)
                generation_stage_text.value = "✓ Course blueprint and curriculum synthesized successfully! Studio populated."
                generation_stage_text.color = ft.Colors.GREEN_700
                generation_progress_bar.value = 1.0
                generation_progress_bar.color = ft.Colors.GREEN_600

                # 1. Left Side: Title, Description, Objectives, and Category
                if draft_data.get("course_name"):
                    title_field.value = draft_data.get("course_name")
                if draft_data.get("description"):
                    desc_field.value = draft_data.get("description")
                if draft_data.get("objectives"):
                    objectives_list.clear()
                    objectives_list.extend(draft_data.get("objectives", []))
                    _render_objectives()

                # Smart Category Auto-Match
                best_cat = None
                title_lower = (title_field.value or "").lower()
                for cat in categories_list:
                    c_name = cat.get("name", "").lower()
                    if c_name and (c_name in title_lower or any(word in c_name for word in title_lower.split())):
                        best_cat = str(cat.get("id"))
                        break
                if best_cat:
                    category_dropdown.value = best_cat

                # Cover image
                rec_cover = draft_data.get("recommended_cover_image")
                if rec_cover:
                    nonlocal custom_image_url
                    custom_image_url = rec_cover
                    custom_url_input.value = rec_cover
                    cover_preview_img.src = rec_cover
                    cover_preview_img.visible = True
                    cover_icon.visible = False
                    cover_sub.value = "AI Recommended Cover Photo active"
                    cover_sub.color = ft.Colors.PURPLE_700

                # 2. Right Side: Multi-Module Curriculum
                if new_mods:
                    modules_state.clear()
                    modules_state.extend(new_mods)
                    _render_curriculum()

                page.update()
                show_page_snackbar(page, f"Synthesized '{title_field.value}' with {len(modules_state)} modules!")

                # Fade out progress banner after 3 seconds
                await asyncio.sleep(3.0)
                if is_studio_open[0]:
                    generation_progress_banner.visible = False
                    page.update()
            else:
                # User left or closed studio before completion!
                # Auto-draft and save course in background per user requirement
                try:
                    auto_course_name = draft_data.get("course_name") or topic_val or "AI Synthesized Course"
                    auto_desc = draft_data.get("description") or f"Synthesized from topic: {topic_val}"
                    auto_objs = draft_data.get("objectives", [])
                    auto_cover = draft_data.get("recommended_cover_image")
                    auto_cat_id = str(categories_list[0].get("id")) if categories_list else None

                    auto_payload = {
                        "name": auto_course_name,
                        "description": auto_desc,
                        "category_id": auto_cat_id,
                        "objectives": auto_objs,
                        "image_url": auto_cover,
                        "public": "false",
                        "auto_certificate": False,
                        "supervised": False,
                        "is_freelance": is_freelance,
                        "teacher_id": current_user_id if is_freelance else None,
                        "org_id": effective_org_id,
                        "curriculum": clean_new_mods,
                    }
                    saved_course = await create_course(auth_tok, auto_payload)
                    if isinstance(saved_course, dict) and "id" in saved_course:
                        show_page_snackbar(
                            page,
                            f"AI Course '{auto_course_name}' completed in background and saved as draft in your courses!",
                            duration=6000,
                        )
                        if on_course_created:
                            on_course_created(saved_course)
                except Exception as auto_ex:
                    print(f"[course_studio] Background auto-save note: {auto_ex}")

        def _execute_generation(ev=None):
            topic_val = (topic_in.value or "").strip()
            ctx_val = (ctx_in.value or "").strip()

            if not topic_val and not selected_files:
                status_txt.value = "Please provide a course topic or attach study materials/photos."
                status_txt.color = ft.Colors.RED_600
                page.update()
                return

            final_context = ctx_val
            for sf in selected_files:
                if not sf["name"].lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                    final_context += f"\n\n--- Reference: {sf['name']} ---\n{sf['content']}\n"

            photo_payloads = list(selected_photo_payloads) if selected_photo_payloads else None

            # 1. Immediately close the AI drafter dialog
            _close_draft_dlg()

            # 2. Activate non-blocking banner & curriculum placeholder
            is_synthesizing_active[0] = True
            generation_progress_banner.visible = True
            generation_progress_banner.bgcolor = ft.Colors.with_opacity(0.10, ft.Colors.PURPLE_600)
            generation_stage_text.value = "Analyzing materials, notes, and architecting multi-module curriculum…"
            generation_stage_text.color = ft.Colors.PURPLE_900
            generation_progress_bar.value = None
            generation_progress_bar.color = ft.Colors.PURPLE_600
            generation_timer_text.value = "0s elapsed"

            _render_curriculum()
            page.update()

            show_page_snackbar(page, "AI Synthesis running in background. You can continue editing course details!")

            # 3. Launch background generation task
            page.run_task(_run_background_synthesis, topic_val, final_context, photo_payloads)

        gen_btn = ft.FilledButton(
            "Synthesize Course",
            style=ft.ButtonStyle(bgcolor=ft.Colors.PURPLE_600, shape=ft.RoundedRectangleBorder(radius=8)),
            on_click=_execute_generation,
        )

        draft_dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=16),
            bgcolor=ft.Colors.SURFACE,
            title=ft.Row([
                ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=ft.Colors.PURPLE_600, size=22),
                ft.Text("AI Course & Curriculum Drafter", size=16, weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Container(
                width=500,
                content=ft.Column([
                    ft.Text(
                        "Supply study notes, textbook slides, photos, or syllabus.",
                        size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    topic_in,
                    ctx_in,
                    attach_btn,
                    chips_row,
                    status_txt,
                ], spacing=10, tight=True),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=_close_draft_dlg),
                gen_btn,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(draft_dlg)
        draft_dlg.open = True
        page.update()

    # ─────────────────────────────────────────────────────────────────────────
    # 1-CLICK ATOMIC PUBLISH ACTION (METADATA + FULL CURRICULUM TRANSACTION)
    # ─────────────────────────────────────────────────────────────────────────
    async def _publish_atomic(e=None):
        name_val = (title_field.value or "").strip()
        cat_val = category_dropdown.value

        if not name_val:
            error_banner.value = "Course Title is required."
            error_banner.visible = True
            page.update()
            return

        if not cat_val:
            error_banner.value = "Please select a Course Category."
            error_banner.visible = True
            page.update()
            return

        error_banner.visible = False
        publish_btn.disabled = True
        publish_btn.content = ft.Row([
            ft.ProgressRing(width=14, height=14, color=ft.Colors.WHITE, stroke_width=2),
            ft.Text("Publishing Complete Course…", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
        ], tight=True, spacing=6)
        page.update()

        auth_tok = await page.shared_preferences.get("auth_token")
        logo_b64 = base64.b64encode(selected_image_bytes).decode("utf-8") if selected_image_bytes else None

        # Sanitize curriculum to strip internal UI keys (e.g. _page attached during preview)
        clean_curriculum = []
        for mi, mod in enumerate(modules_state or []):
            if not isinstance(mod, dict):
                continue
            clean_lessons = []
            for li, les in enumerate(mod.get("lessons", [])):
                if not isinstance(les, dict):
                    continue
                clean_content = les.get("content", {})
                if isinstance(clean_content, dict):
                    clean_content = {str(k): v for k, v in clean_content.items() if not str(k).startswith("_")}
                clean_lessons.append({
                    "id": les.get("id"),
                    "title": les.get("title", f"Lesson {li+1}"),
                    "type": les.get("type", "text"),
                    "order_index": li,
                    "content": clean_content if isinstance(clean_content, dict) else {},
                })
            clean_curriculum.append({
                "id": mod.get("id"),
                "title": mod.get("title", f"Module {mi+1}"),
                "order_index": mi,
                "lessons": clean_lessons,
            })

        payload = {
            "name": name_val,
            "description": (desc_field.value or name_val).strip(),
            "category_id": cat_val,
            "objectives": objectives_list,
            "image_bytes": logo_b64,
            "image_filename": selected_image_name,
            "image_url": custom_image_url,
            "public": visibility_dropdown.value or "false",
            "auto_certificate": auto_cert_switch.value,
            "supervised": supervised_switch.value,
            "is_freelance": is_freelance,
            "teacher_id": current_user_id if is_freelance else (teacher_dropdown.value or None),
            "org_id": effective_org_id,
            "curriculum": clean_curriculum,  # Entire sanitized curriculum sent atomically!
        }

        try:
            res = await asyncio.wait_for(create_course(auth_tok, payload), timeout=50)
            if isinstance(res, dict) and "id" in res:
                _close_studio()
                show_page_snackbar(page, f"Course '{name_val}' and curriculum created successfully!")
                if on_course_created:
                    on_course_created(res)
                try:
                    page.navigate(f"/courses/{res['id']}")
                except Exception:
                    pass
            else:
                err_msg = res.get("error", "Failed to create course") if isinstance(res, dict) else "Server error"
                error_banner.value = f"Could not create course: {err_msg}"
                error_banner.visible = True
                publish_btn.disabled = False
                publish_btn.content = ft.Row([
                    ft.Icon(ft.Icons.ROCKET_LAUNCH_ROUNDED, size=16, color=ft.Colors.WHITE),
                    ft.Text("Publish Everything", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ], tight=True, spacing=6)
                page.update()
        except Exception as ex:
            error_banner.value = f"Creation error: {ex}"
            error_banner.visible = True
            publish_btn.disabled = False
            publish_btn.content = ft.Row([
                ft.Icon(ft.Icons.ROCKET_LAUNCH_ROUNDED, size=16, color=ft.Colors.WHITE),
                ft.Text("Publish Everything", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
            ], tight=True, spacing=6)
            page.update()

    publish_btn = ft.FilledButton(
        content=ft.Row([
            ft.Icon(ft.Icons.ROCKET_LAUNCH_ROUNDED, size=16, color=ft.Colors.WHITE),
            ft.Text("Publish Everything", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
        ], tight=True, spacing=6),
        style=ft.ButtonStyle(bgcolor=ft.Colors.PRIMARY, shape=ft.RoundedRectangleBorder(radius=10)),
        on_click=lambda _: page.run_task(_publish_atomic),
    )

    error_banner = ft.Text("", color=ft.Colors.RED_600, size=12, visible=False, weight=ft.FontWeight.W_500)

    # --- Fetch Initial Options ---
    async def _fetch_categories_and_teachers():
        auth_tok = await page.shared_preferences.get("auth_token")
        try:
            cats = await get_categories(auth_tok)
            if isinstance(cats, list):
                categories_list.clear()
                categories_list.extend(cats)
                category_dropdown.options = [
                    ft.dropdown.Option(str(c.get("id")), str(c.get("name", "Category")))
                    for c in cats
                ]
                if cats and not category_dropdown.value:
                    category_dropdown.value = str(cats[0].get("id"))
        except Exception:
            pass

        if not is_freelance:
            try:
                mems = await get_organisation_members(auth_tok, effective_org_id)
                if isinstance(mems, list):
                    teacher_dropdown.options = [
                        ft.dropdown.Option(str(m.get("user_id")), f"{m.get('first_name', '')} {m.get('last_name', '')} ({m.get('role', 'Member')})")
                        for m in mems
                    ]
            except Exception:
                pass
        page.update()

    def _close_studio(e=None):
        is_studio_open[0] = False
        studio_dlg.open = False
        page.update()

    # --- Layout Panes ---
    left_pane = ft.Container(
        padding=16,
        border_radius=14,
        bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
        content=ft.Column(
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.Row([
                    ft.Icon(ft.Icons.BADGE_ROUNDED, size=18, color=ft.Colors.PRIMARY),
                    ft.Text("Course Identity & Profile", weight=ft.FontWeight.BOLD, size=14),
                ], spacing=6),
                cover_container,
                title_field,
                category_dropdown,
                desc_field,
                audience_field,
                ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.LIGHTBULB_OUTLINE_ROUNDED, size=16, color=ft.Colors.PRIMARY),
                        ft.Text("Learning Objectives", size=12.5, weight=ft.FontWeight.W_600),
                    ], spacing=6),
                    objectives_wrap,
                    obj_input,
                ], spacing=6),
                visibility_dropdown,
                ft.Row([auto_cert_switch, supervised_switch], wrap=True, spacing=16),
                teacher_dropdown,
            ],
        ),
    )

    right_pane = ft.Container(
        padding=16,
        border_radius=14,
        bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
        content=ft.Column(
            spacing=10,
            expand=True,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row([
                            ft.Icon(ft.Icons.ACCOUNT_TREE_ROUNDED, size=18, color=ft.Colors.PURPLE_600),
                            ft.Text("Curriculum & Interactive Content", weight=ft.FontWeight.BOLD, size=14),
                        ], spacing=6),
                        stats_badge,
                    ],
                ),
                ft.Container(expand=True, content=curriculum_col),
            ],
        ),
    )

    _render_objectives()
    _render_curriculum()

    # --- Mobile Tabs ---
    mobile_tabs_bar = ft.Container()
    body_container = ft.Container(expand=True)

    def _sync_layout():
        if is_desktop:
            left_pane.expand = 5
            right_pane.expand = 7
            body_container.content = ft.Row([left_pane, right_pane], spacing=14, expand=True)
            mobile_tabs_bar.visible = False
        else:
            mobile_tabs_bar.visible = True
            left_pane.expand = True
            right_pane.expand = True
            body_container.content = left_pane if is_mobile_tab_active == 0 else right_pane
        page.update()

    def _set_mobile_tab(idx: int):
        nonlocal is_mobile_tab_active
        is_mobile_tab_active = idx
        btn_details.style = ft.ButtonStyle(bgcolor=ft.Colors.PRIMARY if idx == 0 else ft.Colors.TRANSPARENT)
        btn_details.content.color = ft.Colors.WHITE if idx == 0 else ft.Colors.ON_SURFACE
        btn_curric.style = ft.ButtonStyle(bgcolor=ft.Colors.PRIMARY if idx == 1 else ft.Colors.TRANSPARENT)
        btn_curric.content.color = ft.Colors.WHITE if idx == 1 else ft.Colors.ON_SURFACE
        _sync_layout()

    btn_details = ft.TextButton(
        content=ft.Text("Course Details", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
        style=ft.ButtonStyle(bgcolor=ft.Colors.PRIMARY, shape=ft.RoundedRectangleBorder(radius=8)),
        on_click=lambda _: _set_mobile_tab(0),
    )
    btn_curric = ft.TextButton(
        content=ft.Text("Curriculum Builder", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
        style=ft.ButtonStyle(bgcolor=ft.Colors.TRANSPARENT, shape=ft.RoundedRectangleBorder(radius=8)),
        on_click=lambda _: _set_mobile_tab(1),
    )

    mobile_tabs_bar = ft.Container(
        padding=4,
        border_radius=10,
        bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
        visible=not is_desktop,
        content=ft.Row([
            ft.Container(expand=True, content=btn_details),
            ft.Container(expand=True, content=btn_curric),
        ], spacing=4),
    )

    _sync_layout()

    studio_dlg = ft.AlertDialog(
        modal=True,
        bgcolor=ft.Colors.SURFACE,
        shape=ft.RoundedRectangleBorder(radius=18),
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row([
                    ft.Container(
                        padding=6,
                        border_radius=8,
                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PURPLE_600),
                        content=ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=ft.Colors.PURPLE_600, size=20),
                    ),
                    ft.Column([
                        ft.Text("AI Course Studio", weight=ft.FontWeight.BOLD, size=16),
                        ft.Text("Parallel Architect & Full-Fledged Curriculum Builder", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], spacing=1),
                ], spacing=10),
                ft.Row([
                    ft.FilledButton(
                        content=ft.Row([
                            ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=15, color=ft.Colors.PURPLE_700),
                            ft.Text("Generate with AI Drafter", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.PURPLE_900),
                        ], tight=True, spacing=6),
                        style=ft.ButtonStyle(
                            bgcolor=ft.Colors.PURPLE_100,
                            shape=ft.RoundedRectangleBorder(radius=8),
                        ),
                        on_click=open_ai_drafter_dialog,
                    ),
                    ft.IconButton(ft.Icons.CLOSE_ROUNDED, icon_size=20, on_click=_close_studio),
                ], spacing=8),
            ],
        ),
        content=ft.Container(
            width=studio_w,
            height=studio_h,
            content=ft.Column([
                mobile_tabs_bar,
                error_banner,
                generation_progress_banner,
                body_container,
                ft.Row(
                    alignment=ft.MainAxisAlignment.END,
                    controls=[
                        ft.TextButton("Cancel", on_click=_close_studio),
                        publish_btn,
                    ],
                    spacing=10,
                ),
            ], spacing=10, expand=True),
        ),
    )

    page.overlay.append(studio_dlg)
    studio_dlg.open = True
    page.update()
    page.run_task(_fetch_categories_and_teachers)
