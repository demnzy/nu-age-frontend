import asyncio
import random
import flet as ft
from flet_video import Video, VideoMedia
from src.components.adaptive_video_player import AdaptiveVideoPlayer
from src.components.bottom_appbar import get_bottom_appbar
from src.requests.Courses import (
    upload_asset_background,
    upload_video_background,
    save_bulk_curriculum,
    get_courses,
    get_course_curriculum,
    generate_course_draft,
)
from src.utils.file_opener import open_or_download_asset

# =========================================================
# CONFIG / SCHEMA
# =========================================================

UI_ACCENT = ft.Colors.PRIMARY
DESKTOP_BREAKPOINT = 1024

LESSON_TYPES = {
    "video": "Video",
    "audio": "Audio",
    "document": "Document",
    "text": "Text",
    "cards": "Flashcards",
    "assessment": "Assessment",
    "scenario": "Decision Matrix",
}

LESSON_TYPE_ICONS = {
    "video": ft.Icons.PLAY_CIRCLE_FILL_ROUNDED,
    "audio": ft.Icons.AUDIOTRACK_ROUNDED,
    "document": ft.Icons.DESCRIPTION_ROUNDED,
    "text": ft.Icons.NOTES_ROUNDED,
    "cards": ft.Icons.VIEW_CAROUSEL_ROUNDED,
    "assessment": ft.Icons.QUIZ_ROUNDED,
    "scenario": ft.Icons.CALL_SPLIT_ROUNDED,
}

LESSON_TYPE_COLORS = {
    "video": ft.Colors.BLUE_500,
    "audio": ft.Colors.PINK_500,
    "document": ft.Colors.TEAL_500,
    "text": ft.Colors.AMBER_700,
    "cards": ft.Colors.PURPLE_500,
    "assessment": ft.Colors.ORANGE_500,
    "scenario": ft.Colors.EMERALD_600 if hasattr(ft.Colors, "EMERALD_600") else ft.Colors.TEAL_600,
}

LESSON_CONTENT_SCHEMA = {
    "video": ["file_name", "video_url", "accompanying_text"],
    "audio": ["file_name", "audio_path", "accompanying_text"],
    "document": ["file_name", "document_url", "accompanying_text"],
    "text": ["text"],
    "cards": ["cards"],
    "assessment": ["questions"],
    "scenario": ["scenario", "choices"],
}

REQUIRED_KEYS = {
    "video": ["video_url"],
    "audio": ["audio_path"],
    "document": ["document_url"],
    "text": ["text"],
    "cards": ["cards"],
    "assessment": ["questions"],
    "scenario": ["scenario", "choices"],
}

OPTIONAL_KEYS = {
    "video": ["accompanying_text"],
    "audio": ["accompanying_text"],
    "document": ["accompanying_text"],
    "text": [],
    "cards": [],
    "assessment": [],
    "scenario": [],
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
}

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

    for k in list(content.keys()):
        if k not in allowed:
            content.pop(k, None)

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


def lesson_color(t: str):
    return LESSON_TYPE_COLORS.get(t, ft.Colors.GREY_500)


def lesson_icon(t: str):
    return LESSON_TYPE_ICONS.get(t, ft.Icons.INSERT_DRIVE_FILE_ROUNDED)


def lesson_badge(t: str):
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        border_radius=999,
        bgcolor=ft.Colors.with_opacity(0.12, lesson_color(t)),
        content=ft.Row(
            [
                ft.Icon(lesson_icon(t), size=13, color=lesson_color(t)),
                ft.Text(
                    LESSON_TYPES.get(t, t).upper(),
                    size=10,
                    weight=ft.FontWeight.BOLD,
                    color=lesson_color(t),
                ),
            ],
            spacing=5,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def validate_lesson(lesson: dict):
    errors = []
    t = lesson.get("type", "text")
    c = lesson.get("content", {})

    if not str(lesson.get("title", "")).strip():
        errors.append("Lesson title is required.")

    for k in REQUIRED_KEYS.get(t, []):
        v = c.get(k)
        if isinstance(v, str) and not v.strip():
            errors.append(f"Missing required content: {k.replace('_', ' ').title()}")
        elif isinstance(v, list) and len(v) == 0:
            errors.append(f"Missing required content: {k.replace('_', ' ').title()}")

    if t == "scenario":
        if not str(c.get("scenario", "")).strip():
            errors.append("Scenario prompt text is required.")
        choices = c.get("choices", [])
        if len(choices) < 2:
            errors.append("Provide at least 2 choices for the scenario.")
        for i, ch in enumerate(choices):
            if not str(ch.get("text", "")).strip():
                errors.append(f"Choice {i+1} needs an option label.")
            if not str(ch.get("consequence", "")).strip():
                errors.append(f"Choice {i+1} needs a consequence description.")

    if t == "assessment":
        qs = c.get("questions", [])
        if not qs:
            errors.append("Assessment needs at least one question.")
        else:
            for i, q in enumerate(qs, start=1):
                if not str(q.get("text", "")).strip():
                    errors.append(f"Question {i} needs prompt text.")
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
# LESSON PREVIEW RENDERERS
# =========================================================

def preview_placeholder(message: str, icon):
    return ft.Container(
        padding=32,
        border_radius=14,
        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
        bgcolor=ft.Colors.SURFACE,
        alignment=ft.Alignment(0, 0),
        content=ft.Column(
            [
                ft.Icon(icon, size=40, color=ft.Colors.OUTLINE),
                ft.Text(message, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER, size=13),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
        ),
    )


def render_preview_video_block(value, lesson):
    if not str(value or "").strip():
        return preview_placeholder("No video uploaded yet.", ft.Icons.VIDEOCAM_OFF_ROUNDED)

    file_title = (
        lesson["content"].get("file_name", "Video Lesson")
        if isinstance(lesson.get("content"), dict)
        else "Video Lesson"
    )

    player = AdaptiveVideoPlayer(
        media_url=value,
        title=file_title,
        autoplay=False,
    )

    return ft.Container(
        border_radius=14,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=ft.ResponsiveRow(
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    col={"xs": 12, "md": 12, "lg": 10},
                    content=player,
                )
            ],
        ),
    )


def render_preview_notes_block(value, lesson):
    async def handle_link_tap(e):
        await e.page.launch_url(e.data)

    display_value = str(value or "").strip() or "_No instructor notes added yet._"

    return ft.Container(
        padding=18,
        border_radius=12,
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_PRIMARY)),
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.STICKY_NOTE_2_OUTLINED, size=18, color=UI_ACCENT),
                        ft.Text("Instructor Notes & Takeaways", weight=ft.FontWeight.BOLD, size=14),
                    ],
                    spacing=8,
                ),
                ft.Markdown(
                    display_value,
                    selectable=False,
                    extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
                    on_tap_link=handle_link_tap,
                ),
            ],
            spacing=10,
            horizontal_alignment=ft.CrossAxisAlignment.START,
        ),
    )


def render_preview_document_block(value, lesson):
    if not str(value or "").strip():
        return preview_placeholder("No document uploaded yet.", ft.Icons.DESCRIPTION_OUTLINED)

    file_name = lesson["content"].get("file_name", "Document")

    async def handle_download(e):
        target_page = lesson.get("_page") or e.page
        await open_or_download_asset(target_page, value, file_name)

    return ft.Container(
        padding=32,
        border_radius=14,
        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
        bgcolor=ft.Colors.SURFACE,
        alignment=ft.Alignment(0, 0),
        content=ft.Column(
            [
                ft.Container(
                    padding=16,
                    border_radius=16,
                    bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.RED_500),
                    content=ft.Icon(ft.Icons.PICTURE_AS_PDF_ROUNDED, size=48, color=ft.Colors.RED_500),
                ),
                ft.Text(file_name, weight=ft.FontWeight.BOLD, size=16, text_align=ft.TextAlign.CENTER),
                ft.ElevatedButton(
                    content=ft.Row([ft.Icon(ft.Icons.DOWNLOAD_ROUNDED, size=18), ft.Text("Download Document")], spacing=6),
                    on_click=handle_download,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
        ),
    )


def render_preview_text_block(value, lesson):
    if not str(value or "").strip():
        return preview_placeholder("No reading text written yet.", ft.Icons.NOTES_ROUNDED)

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
                code_text_style=ft.TextStyle(
                    size=14,
                    weight=ft.FontWeight.NORMAL,
                    font_family="monospace",
                    color=ft.Colors.ON_SURFACE_VARIANT,
                    bgcolor=ft.Colors.SCRIM,
                ),
            ),
        ),
    )


def render_preview_audio_block(value, lesson):
    if not str(value or "").strip():
        return preview_placeholder("No audio uploaded yet.", ft.Icons.AUDIO_FILE_ROUNDED)

    file_name = lesson["content"].get("file_name", "Audio Lesson")

    async def handle_download(e):
        target_page = lesson.get("_page") or e.page
        await open_or_download_asset(target_page, value, file_name)

    return ft.Container(
        padding=32,
        border_radius=14,
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_PRIMARY)),
        alignment=ft.Alignment(0, 0),
        content=ft.Column(
            [
                ft.Container(
                    padding=16,
                    border_radius=16,
                    bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.PINK_500),
                    content=ft.Icon(ft.Icons.AUDIO_FILE_ROUNDED, size=48, color=ft.Colors.PINK_500),
                ),
                ft.Text(file_name, weight=ft.FontWeight.BOLD, size=16, text_align=ft.TextAlign.CENTER),
                ft.ElevatedButton(
                    content=ft.Row([ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, size=18), ft.Text("Open / Listen Audio")], spacing=6),
                    on_click=handle_download,
                ),
            ],
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


CARD_PREVIEW_COLORS = [
    ft.Colors.BLUE_50, ft.Colors.RED_50, ft.Colors.GREEN_50,
    ft.Colors.AMBER_50, ft.Colors.PURPLE_50, ft.Colors.TEAL_50,
]


def render_preview_cards_block(value, lesson):
    cards_list = [c for c in (value or []) if str(c).strip()]
    if not cards_list:
        return preview_placeholder("Add at least one flashcard to preview.", ft.Icons.VIEW_CAROUSEL_ROUNDED)

    card_idx = [0]
    card_bg_color = random.choice(CARD_PREVIEW_COLORS)

    card_text = ft.Container(
        alignment=ft.Alignment(0, 0),
        bgcolor=card_bg_color,
        padding=30,
        border_radius=12,
        content=ft.Markdown(
            value=cards_list[0],
            selectable=False,
            extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
            md_style_sheet=ft.MarkdownStyleSheet(
                text_alignment=ft.TextAlign.CENTER,
                p_text_style=ft.TextStyle(size=20, weight=ft.FontWeight.W_600, color=ft.Colors.BLACK),
            ),
        ),
    )
    counter_text = ft.Text(f"1 / {len(cards_list)}", color=ft.Colors.BLACK, weight=ft.FontWeight.BOLD)

    card_container = ft.Container(padding=32, border_radius=16, bgcolor=card_bg_color)

    def update():
        card_text.content.value = cards_list[card_idx[0]]
        counter_text.value = f"{card_idx[0] + 1} / {len(cards_list)}"
        card_container.bgcolor = random.choice(CARD_PREVIEW_COLORS)
        card_text.bgcolor = card_container.bgcolor
        if lesson.get("_page"):
            lesson["_page"].update()

    def go_back(e):
        if card_idx[0] > 0:
            card_idx[0] -= 1
            update()

    def go_forward(e):
        if card_idx[0] < len(cards_list) - 1:
            card_idx[0] += 1
            update()

    card_container.content = ft.Column(
        [
            ft.Container(card_text, min_height=140, alignment=ft.Alignment(0, 0)),
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
    return card_container


PREVIEW_CONTENT_RENDERERS = {
    "video_url": render_preview_video_block,
    "accompanying_text": render_preview_notes_block,
    "document_url": render_preview_document_block,
    "text": render_preview_text_block,
    "audio_path": render_preview_audio_block,
    "cards": render_preview_cards_block,
}


def render_preview_scenario_ui(lesson: dict):
    async def handle_link_tap(e):
        await e.page.launch_url(e.data)

    content = lesson.get("content", {})
    scenario_text = str(content.get("scenario", "")).strip()
    choices = [c for c in content.get("choices", []) if str(c.get("text", "")).strip()]

    if not scenario_text or len(choices) < 2:
        return preview_placeholder(
            "Add scenario prompt and at least two choices to preview.", ft.Icons.CALL_SPLIT_ROUNDED
        )

    consequence_box = ft.Container(
        padding=18,
        border_radius=12,
        bgcolor=ft.Colors.with_opacity(0.10, UI_ACCENT),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.35, UI_ACCENT)),
        visible=False,
        content=ft.Column([
            ft.Row([ft.Icon(ft.Icons.LIGHTBULB_CIRCLE, color=UI_ACCENT), ft.Text("Consequence & Outcome", weight=ft.FontWeight.BOLD, color=UI_ACCENT)]),
            ft.Markdown("", selectable=False, extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED, md_style_sheet=ft.MarkdownStyleSheet(
                p_text_style=ft.TextStyle(color=ft.Colors.ON_SURFACE),
            ))
        ])
    )

    buttons_col = ft.Column(spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    def handle_choice(idx, cons_text):
        for i, btn in enumerate(buttons_col.controls):
            if i == idx:
                btn.bgcolor = UI_ACCENT
                btn.color = ft.Colors.SURFACE
            else:
                btn.bgcolor = ft.Colors.TRANSPARENT
                btn.color = UI_ACCENT
        consequence_box.content.controls[1].value = cons_text
        consequence_box.visible = True
        if lesson.get("_page"):
            lesson["_page"].update()

    for idx, ch in enumerate(choices):
        btn = ft.OutlinedButton(
            content=ft.Text(ch.get("text", f"Option {idx+1}"), weight=ft.FontWeight.W_600),
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), padding=16),
            on_click=lambda e, i=idx, c_t=ch.get("consequence", ""): handle_choice(i, c_t),
        )
        buttons_col.controls.append(btn)

    return ft.Container(
        padding=24,
        border_radius=16,
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_PRIMARY)),
        content=ft.Column(
            [
                ft.Row([
                    ft.Icon(ft.Icons.CALL_SPLIT_ROUNDED, color=UI_ACCENT, size=24),
                    ft.Text("Decision Matrix Scenario", weight=ft.FontWeight.BOLD, size=17, color=UI_ACCENT)
                ]),
                ft.Markdown(
                    scenario_text,
                    selectable=True,
                    extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                    on_tap_link=handle_link_tap,
                    md_style_sheet=ft.MarkdownStyleSheet(
                        p_text_style=ft.TextStyle(size=15, weight=ft.FontWeight.W_400, color=ft.Colors.ON_SURFACE),
                    ),
                ),
                ft.Divider(height=10, color=ft.Colors.OUTLINE_VARIANT),
                ft.Text("What is the best course of action?", weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE_VARIANT),
                buttons_col,
                consequence_box,
            ],
            spacing=12,
        ),
    )


def render_preview_assessment_ui(lesson: dict):
    content = lesson.get("content", {})
    questions = [
        q for q in content.get("questions", [])
        if str(q.get("text", "")).strip() and len(q.get("options", [])) >= 2
    ]

    if not questions:
        return preview_placeholder("Add at least one question (with 2+ options) to preview.", ft.Icons.QUIZ_ROUNDED)

    question_cards = []
    for q_idx, q in enumerate(questions):
        options_data = q.get("options", [])
        correct_count = sum(1 for opt in options_data if opt.get("is_correct"))
        is_multi_select = correct_count > 1

        q_text_str = f"Q{q_idx + 1}: {q.get('text', '')}"
        if is_multi_select:
            q_text_str += " (Select all that apply)"

        q_text = ft.Markdown(
            value=q_text_str,
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
            md_style_sheet=ft.MarkdownStyleSheet(
                p_text_style=ft.TextStyle(size=15, color=ft.Colors.ON_SURFACE, weight=ft.FontWeight.W_500),
            ),
        )

        if is_multi_select:
            options_rows = [
                ft.Row(
                    [ft.Checkbox(value=False, data=opt.get("text", ""), fill_color="white", check_color=UI_ACCENT),
                     ft.Text(opt.get("text", ""), expand=True, color=ft.Colors.ON_SURFACE)],
                    vertical_alignment=ft.CrossAxisAlignment.START,
                )
                for opt in options_data
            ]
            options_ui = ft.Column(options_rows, spacing=8)
        else:
            options_ui = ft.RadioGroup(
                content=ft.Column(
                    [
                        ft.Row(
                            [ft.Radio(value=opt.get("text"), fill_color=UI_ACCENT),
                             ft.Text(opt.get("text"), expand=True, color=ft.Colors.ON_SURFACE)],
                            vertical_alignment=ft.CrossAxisAlignment.START,
                        )
                        for opt in options_data
                    ],
                    spacing=8,
                )
            )

        question_cards.append(
            ft.Container(
                padding=20,
                border_radius=14,
                bgcolor=ft.Colors.SURFACE,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_PRIMARY)),
                content=ft.Column([
                    ft.Container(content=q_text),
                    ft.Divider(height=1),
                    options_ui,
                ], spacing=12),
            )
        )

    return ft.Container(
        padding=0,
        content=ft.Column(question_cards, spacing=16, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
    )


def render_lesson_preview(lesson: dict, page: ft.Page):
    lesson["_page"] = page
    content = lesson.get("content", {})
    blocks = []

    for key, value in content.items():
        if key in ["questions", "scenario", "choices", "prompt_text", "file_name"]:
            continue
        renderer = PREVIEW_CONTENT_RENDERERS.get(key)
        if renderer:
            blocks.append(renderer(value, lesson))

    if lesson["type"] == "assessment":
        blocks.append(render_preview_assessment_ui(lesson))
    elif lesson["type"] == "scenario":
        blocks.append(render_preview_scenario_ui(lesson))

    if not blocks:
        blocks.append(preview_placeholder("Nothing to preview yet — add content in the editor.", ft.Icons.INFO_OUTLINE_ROUNDED))

    return ft.Column(blocks, spacing=16, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
