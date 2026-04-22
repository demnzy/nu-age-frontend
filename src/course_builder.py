import flet as ft
from src.components.bottom_appbar import get_bottom_appbar
from src.requests.Courses import (
    upload_asset_background,
    upload_video_background,
    save_bulk_curriculum,
    get_courses,
    get_course_curriculum,
)

# =========================================================
# CONFIG / SCHEMA
# =========================================================

UI_ACCENT = ft.Colors.PRIMARY
DESKTOP_BREAKPOINT = 900
EDITOR_WIDTH_DESKTOP = 460
EDITOR_MOBILE_MARGIN = 24
LESSON_TYPES = {
    "video": "Video",
    "audio": "Audio",
    "document": "Document",
    "text": "Text",
    "cards": "Flashcards",
    "assessment": "Assessment",
    "scenario": "Decision Matrix",
    "assignment": "Assignment",
}

LESSON_TYPE_ICONS = {
    "video": ft.Icons.PLAY_CIRCLE_FILL_ROUNDED,
    "audio": ft.Icons.AUDIOTRACK_ROUNDED,
    "document": ft.Icons.DESCRIPTION_ROUNDED,
    "text": ft.Icons.NOTES_ROUNDED,
    "cards": ft.Icons.VIEW_CAROUSEL_ROUNDED,
    "assessment": ft.Icons.QUIZ_ROUNDED,
    "scenario": ft.Icons.CALL_SPLIT_ROUNDED,
    "assignment": ft.Icons.ASSIGNMENT_ROUNDED,
}

LESSON_TYPE_COLORS = {
    "video": ft.Colors.BLUE_500,
    "audio": ft.Colors.PINK_500,
    "document": ft.Colors.TEAL_500,
    "text": ft.Colors.BROWN_500,
    "cards": ft.Colors.PURPLE_500,
    "assessment": ft.Colors.ORANGE_500,
    "scenario": ft.Colors.TEAL_600,
    "assignment": ft.Colors.DEEP_PURPLE_600,
}

# Strict allowed keys per lesson type (API structure unchanged)
LESSON_CONTENT_SCHEMA = {
    "video": ["file_name", "video_url", "accompanying_text"],
    "audio": ["file_name", "audio_path", "accompanying_text"],
    "document": ["file_name", "document_url", "accompanying_text"],
    "text": ["text"],
    "cards": ["cards"],
    "assessment": ["questions"],
    "scenario": ["scenario", "choices"],
    "assignment": ["prompt_text"],
}

# Required keys for validation
REQUIRED_KEYS = {
    "video": ["video_url"],
    "audio": ["audio_path"],
    "document": ["document_url"],
    "text": ["text"],
    "cards": ["cards"],
    "assessment": ["questions"],
    "scenario": ["scenario", "choices"],
    "assignment": ["prompt_text"],
}

# Optional blocks that can be toggled on/off
OPTIONAL_KEYS = {
    "video": ["accompanying_text"],
    "audio": ["accompanying_text"],
    "document": ["accompanying_text"],
    "text": [],
    "cards": [],
    "assessment": [],
    "scenario": [],
    "assignment": [],
}

DEFAULTS = {
    "file_name": "",
    "video_url": "",
    "audio_path": "",
    "document_url": "",
    "accompanying_text": "",
    "text": "",
    "cards": [],
    "questions": [],
    "scenario": "",
    "choices": [],
    "prompt_text": "",
}

# =========================================================
# MOCK FALLBACK (API call remains; mock only for testing)
# =========================================================


# =========================================================
# HELPERS
# =========================================================

def reorder_list(lst, old_index, new_index):
    if old_index < 0 or old_index >= len(lst):
        return
    if new_index < 0 or new_index >= len(lst):
        return
    item = lst.pop(old_index)
    lst.insert(new_index, item)


def ensure_lesson_shape(lesson: dict):
    lesson.setdefault("id", "new")
    lesson.setdefault("title", "Untitled Lesson")
    lesson.setdefault("type", "text")
    lesson.setdefault("content", {})

    allowed = LESSON_CONTENT_SCHEMA.get(lesson["type"], [])
    content = lesson["content"]

    # Remove keys not allowed
    for k in list(content.keys()):
        if k not in allowed:
            content.pop(k, None)

    # Ensure defaults for required keys
    for k in allowed:
        if k in content:
            continue
        if k in REQUIRED_KEYS.get(lesson["type"], []) or k == "file_name":
            dv = DEFAULTS.get(k, "")
            content[k] = dv.copy() if isinstance(dv, list) else dv

    return lesson


def ensure_module_shape(module: dict):
    module.setdefault("id", "new_module")
    module.setdefault("title", "Untitled Module")
    module.setdefault("lessons", [])
    module["lessons"] = [ensure_lesson_shape(l) for l in module.get("lessons", [])]
    return module


def is_mobile(page: ft.Page):
    w = page.width or page.window_width or 400
    return w < DESKTOP_BREAKPOINT


def drawer_width(page: ft.Page):
    w = page.width or page.window_width or 400
    if is_mobile(page):
        return w
    return EDITOR_WIDTH_DESKTOP


def validate_lesson(lesson: dict):
    errors = []
    t = lesson.get("type", "text")
    c = lesson.get("content", {})

    if not str(lesson.get("title", "")).strip():
        errors.append("Lesson title is required.")

    for k in REQUIRED_KEYS.get(t, []):
        v = c.get(k)
        if isinstance(v, str) and not v.strip():
            errors.append(f"Missing required content: {k}")
        elif isinstance(v, list) and len(v) == 0:
            errors.append(f"Missing required content: {k}")
    if t == "scenario":
        if not str(c.get("scenario", "")).strip():
            errors.append("Scenario prompt text is required.")
        choices = c.get("choices", [])
        if len(choices) < 2:
            errors.append("Provide at least 2 choices for the scenario.")
        for i, ch in enumerate(choices):
            if not str(ch.get("text", "")).strip():
                errors.append(f"Choice {i+1} needs text.")
            if not str(ch.get("consequence", "")).strip():
                errors.append(f"Choice {i+1} needs a consequence.")

    if t == "assignment":
        if not str(c.get("prompt_text", "")).strip():
            errors.append("Assignment instructions cannot be empty.")

    if t == "assessment":
        qs = c.get("questions", [])
        if not qs:
            errors.append("Assessment needs at least one question.")
        else:
            for i, q in enumerate(qs, start=1):
                if not str(q.get("text", "")).strip():
                    errors.append(f"Question {i} needs text.")
                opts = q.get("options", [])
                if len(opts) < 2:
                    errors.append(f"Question {i} needs at least 2 options.")
                if not any(o.get("is_correct") for o in opts):
                    errors.append(f"Question {i} needs at least 1 correct option.")

    if t == "cards":
        cards = c.get("cards", [])
        if not any(str(x).strip() for x in cards):
            errors.append("Flashcards must contain at least one non-empty card.")

    if t == "text":
        if not str(c.get("text", "")).strip():
            errors.append("Text lesson cannot be empty.")

    return errors


# =========================================================
# VIEW
# =========================================================

async def course_builder_view(page: ft.Page, course_id: str):
    token = await page.shared_preferences.get("auth_token")
    app_bar = get_bottom_appbar(page)

    # -----------------------------------------------------
    # Load course name
    # -----------------------------------------------------
    course_data = await get_courses(token=token, params={"id": course_id})
    course_name = (
        course_data[0].get("name", "Untitled Course")
        if isinstance(course_data, list) and len(course_data) > 0
        else "Course"
    )

    # -----------------------------------------------------
    # Curriculum API (kept). Mock fallback for testing only.
    # -----------------------------------------------------
    modules = None
    try:
        curriculum = await get_course_curriculum(token, course_id)
        modules = curriculum.get("modules") if curriculum else None
    except Exception:
        modules = None

    if not modules:
        modules = {}

    modules = [ensure_module_shape(m) for m in modules]

    # -----------------------------------------------------
    # Local state (LOCAL until publish)
    # -----------------------------------------------------
    active_module = None
    active_lesson = None

    editor_content = ft.Column(
        spacing=16,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )
    curriculum_column = ft.Column(
        spacing=16,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )

    # Drawer + scrim for mobile
    def close_editor(e=None):
        nonlocal active_lesson, active_module
        active_lesson = None
        active_module = None
        editor_drawer.offset = ft.Offset(1, 0)
        scrim.visible = False
        refresh_curriculum()
        page.update()

    scrim = ft.Container(
        expand=True,
        bgcolor=ft.Colors.with_opacity(0.35, ft.Colors.BLACK),
        visible=False,
        on_click=close_editor,
    )

    editor_drawer = ft.Container(
        width=drawer_width(page),
        right=0,
        top=0,
        bottom=0,
        offset=ft.Offset(1, 0),
        animate_offset=ft.Animation(280, ft.AnimationCurve.DECELERATE),
        bgcolor=ft.Colors.SURFACE,
        border=ft.border.only(left=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
        shadow=ft.BoxShadow(
            blur_radius=18,
            color=ft.Colors.with_opacity(0.18, ft.Colors.BLACK),
        ),
        content=ft.Column(
            [
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=16, vertical=12),
                    border=ft.border.only(bottom=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
                    content=ft.Row(
                        [
                            ft.Text("Edit Lesson", size=18, weight=ft.FontWeight.BOLD),
                            ft.IconButton(ft.Icons.CLOSE, on_click=close_editor),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ),
                ft.Container(
                    expand=True,
                    padding=12 if is_mobile(page) else 16,
                    content=editor_content,
                ),
            ],
            spacing=0,
            expand=True,
        ),
    )

    def on_resize(e):
        editor_drawer.width = drawer_width(page)
        if active_lesson:
            scrim.visible = is_mobile(page)
        page.update()

    page.on_resize = on_resize

    # -----------------------------------------------------
    # UI helpers
    # -----------------------------------------------------
    def lesson_color(t: str):
        return LESSON_TYPE_COLORS.get(t, ft.Colors.GREY_500)

    def lesson_icon(t: str):
        return LESSON_TYPE_ICONS.get(t, ft.Icons.INSERT_DRIVE_FILE_ROUNDED)

    def lesson_badge(t: str):
        return ft.Container(
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
            border_radius=999,
            bgcolor=ft.Colors.with_opacity(0.10, lesson_color(t)),
            content=ft.Text(
                LESSON_TYPES.get(t, t).upper(),
                size=10,
                weight=ft.FontWeight.BOLD,
                color=lesson_color(t),
            ),
        )

    def action_button_width():
        w = page.width or page.window_width or 400
        return max(180, w - 64)

    def adaptive_action_button(control: ft.Control):
        if is_mobile(page):
            control.width = action_button_width()
        return control

    def show_dialog(title: str, message: str, success: bool):
        def close(e=None):
            dlg.open = False
            page.update()
            if success:
                page.go("/organisations")

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(title, weight=ft.FontWeight.BOLD),
            content=ft.Container(width=520, content=ft.Text(message)),
            actions=[
                ft.ElevatedButton(
                    "OK",
                    bgcolor=UI_ACCENT if success else ft.Colors.ERROR,
                    color=ft.Colors.WHITE,
                    on_click=close,
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    # -----------------------------------------------------
    # Editor open/close
    # -----------------------------------------------------
    def open_editor(lesson: dict, module: dict):
        nonlocal active_lesson, active_module
        active_lesson = ensure_lesson_shape(lesson)
        active_module = module

        editor_drawer.width = drawer_width(page)
        build_editor()
        editor_drawer.offset = ft.Offset(0, 0)

        scrim.visible = is_mobile(page)
        page.update()

    # =========================================================
    # File upload blocks
    # =========================================================

    async def pick_and_upload_video(content: dict, status: ft.Text, url_input: ft.TextField, name_input: ft.TextField,e):
        e.control.disabled=True 
        page.update()
        files = await ft.FilePicker().pick_files(
            allow_multiple=False,
            file_type=ft.FilePickerFileType.VIDEO,
            with_data=True,
        )

        if not files:
            status.value = "Cancelled."
            status.color = ft.Colors.ON_SURFACE_VARIANT
            status.update()
            e.control.disabled=False
            page.update()
            return

        f = files[0]
        file_bytes = getattr(f, "bytes", None)

        if not file_bytes and getattr(f, "path", None):
            try:
                with open(f.path, "rb") as fp:
                    file_bytes = fp.read()
            except Exception:
                file_bytes = None

        if not file_bytes:
            status.value = "No file bytes received."
            status.color = ft.Colors.ERROR
            
            content["video_url"] = ""
            url_input.value = ""
            
            status.update()
            url_input.update()
            return

        status.value = f"Uploading {f.name}..."
        status.color = ft.Colors.ORANGE_700
        status.update()

        try:
            res = await upload_video_background(token, file_name=f.name, file_bytes=file_bytes)
            print(res)
            url = res.get("url", "")
            content["video_url"] = url
            url_input.value = content["video_url"]
            status.value = "Uploaded successfully."
            status.color = ft.Colors.GREEN_700
            status.update()
            url_input.update()
            e.control.disabled=True 
            page.update()
            
            if not content.get("file_name") and not res.get("error"):
                content["file_name"] = f.name
                name_input.value = f.name
                name_input.update()
                page.update()
            if res.get("error"):
                name_input.value = ""
                name_input.update()
                status.value = "Upload Failed"
                status.color = ft.Colors.RED_700
                e.control.disabled=False 
                page.update()
                return

            
            
            
        except Exception as ex:
            status.value = f"Upload failed: {ex}"
            status.color = ft.Colors.ERROR
            
            content["video_url"] = ""
            url_input.value = ""
            
            status.update()
            url_input.update()
            e.control.disabled=False
        
    async def pick_and_upload_asset(asset_type: str, content: dict, status: ft.Text, name_input: ft.TextField, allowed_ext=None, file_type=None, e=None):
        e.control.disabled = True
        files = await ft.FilePicker().pick_files(
            allow_multiple=False,
            with_data=True,
            file_type=file_type or ft.FilePickerFileType.ANY,
            allowed_extensions=allowed_ext,
        )
        if not files:
            status.value = "Cancelled."
            status.color = ft.Colors.ON_SURFACE_VARIANT
            status.update()
            e.control.disabled = False
            page.update()
            return

        f = files[0]
        file_bytes = getattr(f, "bytes", None)

        if not file_bytes and getattr(f, "path", None):
            try:
                with open(f.path, "rb") as fp:
                    file_bytes = fp.read()
            except Exception:
                file_bytes = None

        if not file_bytes:
            status.value = "No file bytes received."
            status.color = ft.Colors.ERROR
            
            if asset_type == "audio":
                content["audio_path"] = ""
            else:
                content["document_url"] = ""
            
            status.update()
            return

        status.value = f"Uploading {f.name}..."
        status.color = ft.Colors.ORANGE_700
        status.update()

        try:
            res = await upload_asset_background(
                token,
                course_id=course_id,
                asset_type=asset_type,
                file_name=f.name,
                file_bytes=file_bytes,
            )
            print(res)
            path = res.get("download_url", "")

            if asset_type == "audio":
                content["audio_path"] = path
            else:
                content["document_url"] = path

            if not content.get("file_name") and not res.get("error"):
                content["file_name"] = f.name
                name_input.value = f.name
                name_input.update()
            if res.get("error"):
                name_input.value = ""
                name_input.update()
                status.value = "Upload Failed."
                status.color = ft.Colors.RED_700
                e.control.disabled = False
                page.update()
                return
            status.value = "Uploaded successfully."
            status.color = ft.Colors.GREEN_700
            
            status.update()
            
        except Exception as ex:
            status.value = f"Upload failed: {ex}"
            status.color = ft.Colors.ERROR
            
            if asset_type == "audio":
                content["audio_path"] = ""
            else:
                content["document_url"] = ""
            e.control.disabled = False
            status.update()
            page.update()
        
    # =========================================================
    # Editor content blocks
    # =========================================================

    def block_card(title: str, child: ft.Control, tint: str = None):
        return ft.Container(
            padding=16,
            border_radius=12,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            bgcolor=tint if tint else ft.Colors.WHITE,
            content=ft.Column([ft.Text(title, weight=ft.FontWeight.BOLD), child], spacing=10),
        )

    def file_name_block(content: dict):
        return ft.TextField(
            label="Display name (what learners see)",
            value=content.get("file_name", ""),
            on_change=lambda e: content.__setitem__("file_name", e.control.value),
        )

    def notes_block(content: dict):
        return ft.TextField(
            label="Instructor Notes",
            value=content.get("accompanying_text", ""),
            multiline=True,
            min_lines=3,
            on_change=lambda e: content.__setitem__("accompanying_text", e.control.value),
        )

    def video_block(content: dict):
        status = ft.Text("No video uploaded", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        name_input = file_name_block(content)
        url_input = ft.TextField(
            label="Or paste external video URL",
            value=content.get("video_url", ""),
            on_change=lambda e: content.__setitem__("video_url", e.control.value.strip()),
        )

        return ft.Column(
            [
                name_input,
                ft.ElevatedButton(
                    content=ft.Text("Upload video"),
                    icon=ft.Icons.UPLOAD_FILE,
                    on_click=lambda e: page.run_task(
                        pick_and_upload_video,
                        content,
                        status,
                        url_input,
                        name_input,
                        e
                    ),
                ),
                status,
                url_input,
            ],
            spacing=10,
        )

    def audio_block(content: dict):
        status = ft.Text("No audio uploaded", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        name_input = file_name_block(content)
        
        return ft.Column(
            [
                name_input,
                ft.ElevatedButton(
                    content=ft.Text("Upload audio"),
                    icon=ft.Icons.UPLOAD_FILE,
                    on_click=lambda e: page.run_task(
                        pick_and_upload_asset,
                        "audio",
                        content,
                        status,
                        name_input,
                        None,
                        ft.FilePickerFileType.AUDIO,
                        e
                    ),
                ),
                status,
            ],
            spacing=10,
        )

    def document_block(content: dict):
        status = ft.Text("No document uploaded", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        name_input = file_name_block(content)
        
        return ft.Column(
            [
                name_input,
                ft.ElevatedButton(
                    content=ft.Text("Upload document"),
                    icon=ft.Icons.UPLOAD_FILE,
                    on_click=lambda e: page.run_task(
                        pick_and_upload_asset,
                        "document",
                        content,
                        status,
                        name_input,
                        ["pdf", "doc", "docx", "ppt", "txt"],
                        ft.FilePickerFileType.CUSTOM,
                        e
                    ),
                ),
                status,
            ],
            spacing=10,
        )

    def text_block(content: dict):
        text_input = ft.TextField(
            label="Lesson Text (Markdown)",
            value=content.get("text", ""),
            multiline=True,
            min_lines=10,
            on_change=lambda e: content.__setitem__("text", e.control.value),
        )

        status_text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT)

        async def upload_and_insert_image(e):
            e.control.disabled = True
            status_text.value = "Selecting..."
            status_text.color = ft.Colors.ON_SURFACE_VARIANT
            page.update()

            files = await ft.FilePicker().pick_files(
                allow_multiple=False,
                file_type=ft.FilePickerFileType.IMAGE,
                with_data=True,
            )

            if not files:
                status_text.value = "Cancelled."
                e.control.disabled = False
                page.update()
                return

            f = files[0]
            file_bytes = getattr(f, "bytes", None)
            
            if not file_bytes and getattr(f, "path", None):
                try:
                    with open(f.path, "rb") as fp:
                        file_bytes = fp.read()
                except Exception:
                    file_bytes = None

            if not file_bytes:
                status_text.value = "Failed to read image."
                status_text.color = ft.Colors.ERROR
                e.control.disabled = False
                page.update()
                return

            status_text.value = f"Uploading {f.name}..."
            status_text.color = ft.Colors.ORANGE_700
            page.update()

            try:
                # THE FIX: Disguise the image as a "document" to pass backend validation
                res = await upload_asset_background(
                    token,
                    course_id=course_id,
                    asset_type="document", 
                    file_name=f.name,
                    file_bytes=file_bytes,
                )
                
                img_url = res.get("view_url", "") or res.get("url", "")
                
                if res.get("error") or not img_url:
                    status_text.value = "Upload failed."
                    status_text.color = ft.Colors.RED_700
                else:
                    # Inject the generated CDN URL into standard markdown
                    markdown_image = f"\n![{f.name}]({img_url})\n"
                    
                    current_text = text_input.value or ""
                    new_text = current_text + markdown_image
                    
                    text_input.value = new_text
                    content["text"] = new_text
                    
                    status_text.value = "Image inserted!"
                    status_text.color = ft.Colors.GREEN_700

            except Exception as ex:
                status_text.value = f"Error: {ex}"
                status_text.color = ft.Colors.ERROR

            e.control.disabled = False
            page.update()

        insert_img_btn = ft.TextButton(
            "Insert Image",
            icon=ft.Icons.ADD_PHOTO_ALTERNATE_OUTLINED,
            icon_color=UI_ACCENT,
            on_click=lambda e: page.run_task(upload_and_insert_image, e)
        )

        return ft.Column(
            controls=[
                ft.Row(
                    [insert_img_btn, status_text], 
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                ),
                text_input
            ],
            spacing=5
        )

    def cards_block(content: dict):
        cards = content.setdefault("cards", [])
        cards_col = ft.Column(spacing=10)

        def rebuild():
            cards_col.controls.clear()
            for idx, txt in enumerate(cards):
                def del_card(i):
                    def handler(e):
                        cards.pop(i)
                        build_editor()
                        page.update()
                    return handler

                def on_change(i):
                    def handler(e):
                        cards[i] = e.control.value
                    return handler

                cards_col.controls.append(
                    ft.Container(
                        padding=12,
                        border_radius=10,
                        border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                        bgcolor=ft.Colors.WHITE,
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Text(f"Card {idx + 1}", weight=ft.FontWeight.BOLD, expand=True),
                                        ft.IconButton(
                                            ft.Icons.DELETE,
                                            icon_color=ft.Colors.RED_500,
                                            on_click=del_card(idx),
                                        ),
                                    ]
                                ),
                                ft.TextField(
                                    value=txt,
                                    multiline=True,
                                    min_lines=2,
                                    on_change=on_change(idx),
                                ),
                            ],
                            spacing=8,
                        ),
                    )
                )

        def add_card(e):
            cards.append("")
            build_editor()
            page.update()

        rebuild()
        return ft.Column(
            [
                cards_col,
                ft.TextButton("Add Card +", icon=ft.Icons.ADD, on_click=add_card),
            ],
            spacing=10,
        )
    def assignment_block(content: dict):
        return ft.TextField(
            label="Assignment Prompt / Instructions (Markdown supported)",
            value=content.get("prompt_text", ""),
            multiline=True,
            min_lines=4,
            on_change=lambda e: content.__setitem__("prompt_text", e.control.value),
        )

    def scenario_block(content: dict):
        content.setdefault("scenario", "")
        choices = content.setdefault("choices", [])
        
        scenario_input = ft.TextField(
            label="The Scenario (Prompt)",
            value=content["scenario"],
            multiline=True,
            min_lines=2,
            on_change=lambda e: content.__setitem__("scenario", e.control.value),
        )

        choices_col = ft.Column(spacing=10)

        def rebuild():
            choices_col.controls.clear()
            for idx, ch in enumerate(choices):
                ch.setdefault("text", "")
                ch.setdefault("consequence", "")

                def del_choice(i):
                    def handler(e):
                        choices.pop(i)
                        build_editor()
                        page.update()
                    return handler

                def text_change(i):
                    def handler(e):
                        choices[i]["text"] = e.control.value
                    return handler

                def cons_change(i):
                    def handler(e):
                        choices[i]["consequence"] = e.control.value
                    return handler

                choices_col.controls.append(
                    ft.Container(
                        padding=12,
                        border_radius=8,
                        border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                        content=ft.Column([
                            ft.Row([
                                ft.Text(f"Choice {idx + 1}", weight=ft.FontWeight.BOLD, expand=True),
                                ft.IconButton(ft.Icons.DELETE, icon_color=ft.Colors.RED_500, on_click=del_choice(idx))
                            ]),
                            ft.TextField(label="User Option (e.g., 'Restart Server')", value=ch["text"], on_change=text_change(idx)),
                            ft.TextField(label="Consequence (Markdown supported)", value=ch["consequence"], multiline=True, on_change=cons_change(idx))
                        ])
                    )
                )

        def add_choice(e):
            choices.append({"text": "", "consequence": ""})
            build_editor()
            page.update()

        rebuild()
        return ft.Column([
            scenario_input,
            ft.Text("Choices & Consequences", weight=ft.FontWeight.BOLD),
            choices_col,
            ft.TextButton("Add Choice +", icon=ft.Icons.ADD, on_click=add_choice)
        ], spacing=15)
    def assessment_block(content: dict):
        questions = content.setdefault("questions", [])
        q_col = ft.Column(spacing=12)

        def rebuild():
            q_col.controls.clear()
            for q_idx, q in enumerate(questions):
                q.setdefault("text", "")
                q.setdefault(
                    "options",
                    [{"text": "", "is_correct": False}, {"text": "", "is_correct": False}],
                )

                def del_q(i):
                    def handler(e):
                        questions.pop(i)
                        build_editor()
                        page.update()
                    return handler

                def q_change(i):
                    def handler(e):
                        questions[i]["text"] = e.control.value
                    return handler

                opts_col = ft.Column(spacing=8)

                for o_idx, opt in enumerate(q["options"]):
                    opt.setdefault("text", "")
                    opt.setdefault("is_correct", False)

                    def opt_text(qi, oi):
                        def handler(e):
                            questions[qi]["options"][oi]["text"] = e.control.value
                        return handler

                    def opt_correct(qi, oi):
                        def handler(e):
                            questions[qi]["options"][oi]["is_correct"] = e.control.value
                        return handler

                    def del_opt(qi, oi):
                        def handler(e):
                            questions[qi]["options"].pop(oi)
                            build_editor()
                            page.update()
                        return handler

                    if is_mobile(page):
                        option_row = ft.Column(
                            [
                                ft.Checkbox(
                                    label="Correct",
                                    value=opt["is_correct"],
                                    on_change=opt_correct(q_idx, o_idx),
                                ),
                                ft.TextField(
                                    value=opt["text"],
                                    on_change=opt_text(q_idx, o_idx),
                                ),
                                ft.Row(
                                    [
                                        ft.IconButton(
                                            ft.Icons.DELETE,
                                            icon_color=ft.Colors.RED_500,
                                            on_click=del_opt(q_idx, o_idx),
                                        )
                                    ],
                                    alignment=ft.MainAxisAlignment.END,
                                ),
                            ],
                            spacing=8,
                        )
                    else:
                        option_row = ft.Row(
                            [
                                ft.Checkbox(
                                    value=opt["is_correct"],
                                    on_change=opt_correct(q_idx, o_idx),
                                ),
                                ft.TextField(
                                    value=opt["text"],
                                    expand=True,
                                    on_change=opt_text(q_idx, o_idx),
                                ),
                                ft.IconButton(
                                    ft.Icons.DELETE,
                                    icon_color=ft.Colors.RED_500,
                                    on_click=del_opt(q_idx, o_idx),
                                ),
                            ]
                        )

                    opts_col.controls.append(option_row)

                def add_opt(i):
                    def handler(e):
                        questions[i]["options"].append({"text": "", "is_correct": False})
                        build_editor()
                        page.update()
                    return handler

                q_col.controls.append(
                    ft.Container(
                        padding=12,
                        border_radius=12,
                        border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                        bgcolor=ft.Colors.WHITE,
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Text(f"Question {q_idx + 1}", weight=ft.FontWeight.BOLD, expand=True),
                                        ft.IconButton(
                                            ft.Icons.DELETE,
                                            icon_color=ft.Colors.RED_500,
                                            on_click=del_q(q_idx),
                                        ),
                                    ]
                                ),
                                ft.TextField(
                                    label="Question text",
                                    value=q["text"],
                                    multiline=True,
                                    min_lines=2,
                                    on_change=q_change(q_idx),
                                ),
                                ft.Text("Options", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                opts_col,
                                ft.TextButton(
                                    "Add Option +",
                                    icon=ft.Icons.ADD,
                                    on_click=add_opt(q_idx),
                                ),
                            ],
                            spacing=10,
                        ),
                    )
                )

        def add_q(e):
            questions.append(
                {
                    "text": "",
                    "options": [
                        {"text": "", "is_correct": False},
                        {"text": "", "is_correct": False},
                    ],
                }
            )
            build_editor()
            page.update()

        rebuild()
        return ft.Column(
            [
                q_col,
                ft.TextButton("Add Question +", icon=ft.Icons.ADD, on_click=add_q),
            ],
            spacing=10,
        )

    # =========================================================
    # Editor builder
    # =========================================================

    def build_editor():
        editor_content.controls.clear()
        if not active_lesson:
            page.update()
            return

        lesson = active_lesson
        content = lesson["content"]
        t = lesson["type"]

        editor_content.controls.append(
            ft.TextField(
                label="Lesson Title",
                value=lesson["title"],
                on_change=lambda e: lesson.__setitem__("title", e.control.value),
            )
        )

        editor_content.controls.append(
            ft.Row(
                [lesson_badge(t)],
                alignment=ft.MainAxisAlignment.START,
            )
        )

        # Strict by type
        if t == "video":
            editor_content.controls.append(block_card("Video", video_block(content), tint=ft.Colors.BLUE_50))
            if "accompanying_text" in content:
                editor_content.controls.append(block_card("Notes", notes_block(content)))
        elif t == "audio":
            editor_content.controls.append(block_card("Audio", audio_block(content), tint=ft.Colors.PINK_50))
            if "accompanying_text" in content:
                editor_content.controls.append(block_card("Notes", notes_block(content)))
        elif t == "document":
            editor_content.controls.append(block_card("Document", document_block(content), tint=ft.Colors.TEAL_50))
            if "accompanying_text" in content:
                editor_content.controls.append(block_card("Notes", notes_block(content)))
        elif t == "text":
            editor_content.controls.append(block_card("Text", text_block(content)))
        elif t == "cards":
            editor_content.controls.append(block_card("Flashcards", cards_block(content), tint=ft.Colors.PURPLE_50))
        elif t == "assessment":
            editor_content.controls.append(block_card("Assessment", assessment_block(content), tint=ft.Colors.ORANGE_50))
        elif t == "scenario":
            editor_content.controls.append(block_card("Decision Matrix", scenario_block(content), tint=ft.Colors.TEAL_50))
        elif t == "assignment":
            editor_content.controls.append(block_card("Assignment", assignment_block(content), tint=ft.Colors.DEEP_PURPLE_50))
        # Optional blocks menu
        missing_optional = [k for k in OPTIONAL_KEYS.get(t, []) if k not in content]
        if missing_optional:
            def add_optional_factory(k):
                def handler(e):
                    default_value = DEFAULTS[k]
                    content[k] = default_value.copy() if isinstance(default_value, list) else default_value
                    build_editor()
                    page.update()
                return handler

            editor_content.controls.append(
                ft.PopupMenuButton(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE_ROUNDED, color=UI_ACCENT),
                            ft.Text("Add content block", weight=ft.FontWeight.BOLD, color=UI_ACCENT),
                        ],
                        spacing=8,
                    ),
                    items=[
                        ft.PopupMenuItem(
                            content=ft.Text(k.replace("_", " ").title()),
                            on_click=add_optional_factory(k),
                        )
                        for k in missing_optional
                    ],
                )
            )

        editor_content.controls.append(
            ft.ElevatedButton(
                "Done",
                bgcolor=UI_ACCENT,
                color=ft.Colors.WHITE,
                height=48,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
                on_click=close_editor,
            )
        )

        page.update()

    # =========================================================
    # MODULE CREATION (LOCAL UNTIL PUBLISH)
    # =========================================================

    def add_new_module(title: str):
        new_id = f"module_{len(modules) + 1}"
        modules.append(
            ensure_module_shape(
                {
                    "id": new_id,
                    "title": title.strip() if title.strip() else f"Module {len(modules) + 1}",
                    "lessons": [],
                }
            )
        )
        refresh_curriculum()

    def open_add_module_modal(e=None):
        title_field = ft.TextField(label="Module Title", autofocus=True)

        def close_modal(ev=None):
            dialog.open = False
            page.update()

        def create_module(ev=None):
            if not title_field.value.strip():
                return
            add_new_module(title_field.value)
            close_modal()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Add New Module", weight=ft.FontWeight.BOLD),
            content=title_field,
            actions=[
                ft.TextButton("Cancel", on_click=close_modal),
                ft.ElevatedButton("Add", bgcolor=UI_ACCENT, color=ft.Colors.WHITE, on_click=create_module),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(dialog)
        dialog.open = True
        page.update()

    # =========================================================
    # CURRICULUM UI + Actions (LOCAL)
    # =========================================================

    def create_new_lesson(lesson_type: str, module: dict):
        new_lesson = ensure_lesson_shape(
            {
                "id": "new",
                "title": f"New {LESSON_TYPES.get(lesson_type, lesson_type)} Lesson",
                "type": lesson_type,
                "content": {},
            }
        )
        module["lessons"].append(new_lesson)
        refresh_curriculum()
        open_editor(new_lesson, module)

    def build_add_lesson_menu(module):
        return ft.PopupMenuButton(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE_ROUNDED, size=18, color=UI_ACCENT),
                    ft.Text("Add Lesson", weight=ft.FontWeight.BOLD, color=UI_ACCENT),
                ],
                spacing=8,
            ),
            items=[
                ft.PopupMenuItem(
                    content=ft.Row(
                        [
                            ft.Icon(LESSON_TYPE_ICONS[lt], color=LESSON_TYPE_COLORS[lt]),
                            ft.Text(f"Add {LESSON_TYPES[lt]}"),
                        ],
                        spacing=10,
                    ),
                    on_click=lambda e, t=lt: create_new_lesson(t, module),
                )
                for lt in LESSON_TYPES.keys()
            ],
        )

    def build_lesson_row(lesson, module):
        t = lesson["type"]

        def delete_lesson(e):
            if lesson in module["lessons"]:
                module["lessons"].remove(lesson)
                refresh_curriculum()

        action_buttons = ft.Row(
            [
                ft.IconButton(
                    ft.Icons.EDIT_ROUNDED,
                    icon_size=18,
                    tooltip="Edit lesson",
                    on_click=lambda e: open_editor(lesson, module),
                ),
                ft.IconButton(
                    ft.Icons.DELETE_ROUNDED,
                    icon_size=18,
                    icon_color=ft.Colors.RED_500,
                    tooltip="Delete lesson",
                    on_click=delete_lesson,
                ),
            ],
            spacing=0,
            tight=True,
        )

        lesson_info = ft.Column(
            [
                ft.Text(
                    lesson["title"],
                    size=14,
                    weight=ft.FontWeight.W_600,
                    max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                lesson_badge(t),
            ],
            spacing=6,
            expand=True,
        )

        if is_mobile(page):
            content = ft.Column(
                [
                    ft.Row(
                        [
                            ft.Container(
                                padding=8,
                                border_radius=10,
                                bgcolor=ft.Colors.with_opacity(0.10, lesson_color(t)),
                                content=ft.Icon(lesson_icon(t), color=lesson_color(t), size=18),
                            ),
                            lesson_info,
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                    ft.Row(
                        [action_buttons],
                        alignment=ft.MainAxisAlignment.END,
                    ),
                ],
                spacing=10,
            )
        else:
            content = ft.Row(
                [
                    ft.Container(
                        padding=8,
                        border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.10, lesson_color(t)),
                        content=ft.Icon(lesson_icon(t), color=lesson_color(t), size=18),
                    ),
                    lesson_info,
                    action_buttons,
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.START,
            )

        return ft.Container(
            padding=ft.padding.symmetric(horizontal=12, vertical=10),
            border_radius=12,
            bgcolor=ft.Colors.WHITE,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            content=content,
        )

    def build_module_block(module, idx):
        def move_up(e):
            reorder_list(modules, idx, idx - 1)
            refresh_curriculum()

        def move_down(e):
            reorder_list(modules, idx, idx + 1)
            refresh_curriculum()

        def delete_mod(e):
            modules.pop(idx)
            refresh_curriculum()

        def rename_mod(e):
            title_field = ft.TextField(label="Module Title", value=module["title"], autofocus=True)

            def close_modal(ev=None):
                dlg.open = False
                page.update()

            def save(ev=None):
                module["title"] = title_field.value.strip() or module["title"]
                close_modal()
                refresh_curriculum()

            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text("Rename Module", weight=ft.FontWeight.BOLD),
                content=title_field,
                actions=[
                    ft.TextButton("Cancel", on_click=close_modal),
                    ft.ElevatedButton("Save", bgcolor=UI_ACCENT, color=ft.Colors.WHITE, on_click=save),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.overlay.append(dlg)
            dlg.open = True
            page.update()

        action_bar = ft.Row(
            [
                ft.IconButton(ft.Icons.ARROW_UPWARD, icon_size=18, tooltip="Move up", on_click=move_up),
                ft.IconButton(ft.Icons.ARROW_DOWNWARD, icon_size=18, tooltip="Move down", on_click=move_down),
                ft.IconButton(ft.Icons.EDIT, icon_size=18, tooltip="Rename module", on_click=rename_mod),
                ft.IconButton(ft.Icons.DELETE, icon_size=18, icon_color=ft.Colors.RED_500, tooltip="Delete module", on_click=delete_mod),
            ],
            spacing=0,
            tight=True,
            wrap=True,
        )

        if is_mobile(page):
            header = ft.Column(
                [
                    ft.Text(module["title"], size=18, weight=ft.FontWeight.BOLD),
                    action_bar,
                ],
                spacing=8,
            )
        else:
            header = ft.Row(
                [
                    ft.Text(module["title"], size=18, weight=ft.FontWeight.BOLD, expand=True),
                    action_bar,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )

        return ft.Container(
            padding=14 if is_mobile(page) else 18,
            border_radius=14,
            bgcolor=ft.Colors.SURFACE,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            content=ft.Column(
                [
                    header,
                    ft.Column([build_lesson_row(l, module) for l in module.get("lessons", [])], spacing=10),
                    build_add_lesson_menu(module),
                ],
                spacing=14,
            ),
        )

    # =========================================================
    # PUBLISH (LOCAL -> BACKEND PAYLOAD)
    # =========================================================

    async def publish_course(e=None):
        errors = []
        for m in modules:
            if not m.get("lessons"):
                errors.append(f"Module '{m['title']}' has no lessons.")
            for l in m.get("lessons", []):
                for err in validate_lesson(l):
                    errors.append(f"{l['title']}: {err}")

        if errors:
            show_dialog("Cannot publish yet", "\n".join(errors), success=False)
            return

        payload = {
            "modules": [
                {
                    "title": m["title"],
                    "order_index": mi,
                    "lessons": [
                        {
                            "title": l["title"],
                            "type": l["type"],
                            "order_index": li,
                            "content": l.get("content", {}),
                        }
                        for li, l in enumerate(m.get("lessons", []))
                    ],
                }
                for mi, m in enumerate(modules)
            ]
        }

        try:
            await save_bulk_curriculum(token, course_id=course_id, payload=payload)
            show_dialog("Publish successful", "Course curriculum saved successfully.", success=True)
        except Exception as ex:
            show_dialog("Publish failed", str(ex), success=False)

    def build_publish_button():
        return ft.ElevatedButton(
            "Publish Course",
            icon=ft.Icons.ROCKET_LAUNCH_ROUNDED,
            bgcolor=UI_ACCENT,
            color=ft.Colors.WHITE,
            height=44,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
            on_click=lambda e: page.run_task(publish_course),
        )

    # =========================================================
    # Render curriculum
    # =========================================================

    def refresh_curriculum():
        curriculum_column.controls.clear()

        back_and_title = ft.Row(
            [
                ft.IconButton(ft.Icons.ARROW_BACK_ROUNDED, on_click=lambda e: page.go("/dashboard")),
                ft.Column(
                    [
                        ft.Text("Course Builder", size=20, weight=ft.FontWeight.BOLD),
                        ft.Text(course_name, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ],
                    spacing=2,
                    expand=True,
                ),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        add_module_btn = ft.OutlinedButton(
            "Add Module",
            icon=ft.Icons.ADD,
            on_click=open_add_module_modal,
        )

        publish_btn = build_publish_button()

        if is_mobile(page):
            header_content = ft.Column(
                [
                    back_and_title,
                    ft.Column(
                        [
                            adaptive_action_button(add_module_btn),
                            adaptive_action_button(publish_btn),
                        ],
                        spacing=10,
                    ),
                ],
                spacing=12,
            )
        else:
            header_content = ft.Row(
                [
                    ft.Container(content=back_and_title, expand=True),
                    ft.Row(
                        [
                            add_module_btn,
                            publish_btn,
                        ],
                        spacing=10,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

        curriculum_column.controls.append(
            ft.Container(
                padding=ft.padding.symmetric(horizontal=16, vertical=14),
                border_radius=12,
                bgcolor=ft.Colors.SURFACE,
                border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                content=header_content,
            )
        )

        for idx, m in enumerate(modules):
            curriculum_column.controls.append(build_module_block(m, idx))

        page.update()

    refresh_curriculum()

    return ft.View(
        route=f"/courses/{course_id}/build",
        bottom_appbar=app_bar,
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        padding=0,
        controls=[
            ft.SafeArea(
                expand=True,
                content=ft.Stack(
                    [
                        ft.Container(expand=True, padding=16, content=curriculum_column),
                        scrim,
                        editor_drawer,
                    ],
                    expand=True,
                ),
            )
        ],
    )