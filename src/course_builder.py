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
import os
import tempfile
import re
from src.utils.code_runner import execute_python, execute_sql, execute_remote_code, execute_html, run_code_lab_tests, parse_cloze_text, sanitize_javascript_code

# =========================================================
# CONFIG / SCHEMA
# =========================================================

UI_ACCENT = ft.Colors.PRIMARY
DESKTOP_BREAKPOINT = 900
SIDEBAR_WIDTH = 460
LESSON_TYPES = {
    "video": "Video",
    "audio": "Audio",
    "document": "Document",
    "text": "Text",
    "cards": "Flashcards",
    "assessment": "Assessment",
    "scenario": "Decision Matrix",
    "stepper": "Walkthrough",
    "sequencer": "Order Challenge",
    "cloze": "Fill in the Blanks",
    "code_lab": "Code Lab",
}

LESSON_TYPE_ICONS = {
    "video": ft.Icons.PLAY_CIRCLE_FILL_ROUNDED,
    "audio": ft.Icons.AUDIOTRACK_ROUNDED,
    "document": ft.Icons.DESCRIPTION_ROUNDED,
    "text": ft.Icons.NOTES_ROUNDED,
    "cards": ft.Icons.VIEW_CAROUSEL_ROUNDED,
    "assessment": ft.Icons.QUIZ_ROUNDED,
    "scenario": ft.Icons.CALL_SPLIT_ROUNDED,
    "stepper": ft.Icons.LINEAR_SCALE_ROUNDED,
    "sequencer": ft.Icons.REORDER_ROUNDED,
    "cloze": ft.Icons.EDIT_NOTE_ROUNDED,
    "code_lab": ft.Icons.CODE_ROUNDED,
}

LESSON_TYPE_COLORS = {
    "video": ft.Colors.BLUE_500,
    "audio": ft.Colors.PINK_500,
    "document": ft.Colors.TEAL_500,
    "text": ft.Colors.BROWN_500,
    "cards": ft.Colors.PURPLE_500,
    "assessment": ft.Colors.ORANGE_500,
    "scenario": ft.Colors.TEAL_600,
    "stepper": ft.Colors.CYAN_600,
    "sequencer": ft.Colors.AMBER_600,
    "cloze": ft.Colors.GREEN_600,
    "code_lab": ft.Colors.DEEP_PURPLE_400,
}

LESSON_TYPE_DESCRIPTIONS = {
    "video":      "Upload or link a video lecture",
    "audio":      "Upload an audio recording",
    "document":   "Upload a PDF, doc, or slides",
    "text":       "Rich markdown reading content",
    "cards":      "Interactive flashcard deck",
    "assessment": "Graded quiz with scored options",
    "scenario":   "Branching decision matrix",
    "stepper":    "Phased multi-step conceptual walkthrough",
    "sequencer":  "Timeline & process ordering challenge",
    "cloze":      "Active recall reading with fill-in-the-blanks",
    "code_lab":   "Interactive code playground & SQLite console",
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
    "stepper": ["title", "intro", "steps"],
    "sequencer": ["prompt", "items"],
    "cloze": ["text", "distractors", "explanation"],
    "code_lab": ["language", "instructions", "starter_code", "solution_code", "setup_sql", "test_cases"],
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
    "stepper": ["steps"],
    "sequencer": ["prompt", "items"],
    "cloze": ["text"],
    "code_lab": ["instructions", "starter_code"],
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
    "stepper": ["title", "intro"],
    "sequencer": [],
    "cloze": ["distractors", "explanation"],
    "code_lab": ["language", "solution_code", "setup_sql", "test_cases"],
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
    "steps": [],
    "prompt": "",
    "items": [],
    "distractors": [],
    "explanation": "",
    "language": "python",
    "instructions": "",
    "starter_code": "",
    "solution_code": "",
    "setup_sql": "",
    "test_cases": [],
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
    if not isinstance(lesson, dict):
        lesson = {}
    if not lesson.get("id"):
        lesson["id"] = "new"
    if not lesson.get("title"):
        lesson["title"] = "Untitled Lesson"
    if not lesson.get("type"):
        lesson["type"] = "text"
    if not isinstance(lesson.get("content"), dict):
        lesson["content"] = {}

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

    # Sanitize code_lab JavaScript/Service Worker code from AI drafts to eliminate import syntax errors
    if lesson["type"] == "code_lab":
        code_lang = (content.get("language") or "javascript").lower().strip()
        if code_lang in ("javascript", "js", "typescript", "ts"):
            if content.get("starter_code"):
                content["starter_code"] = sanitize_javascript_code(content["starter_code"])
            if content.get("solution_code"):
                content["solution_code"] = sanitize_javascript_code(content["solution_code"])

    return lesson


def ensure_module_shape(module: dict):
    if not isinstance(module, dict):
        module = {}
    if not module.get("id"):
        module["id"] = "new_module"
    if not module.get("title"):
        module["title"] = "Untitled Module"
    if not isinstance(module.get("lessons"), list):
        module["lessons"] = []
    module["lessons"] = [ensure_lesson_shape(l) for l in module.get("lessons", [])]
    return module


def is_mobile(page: ft.Page):
    if not page:
        return False
    w = getattr(page, "width", None)
    if w is None and hasattr(page, "window") and page.window:
        w = getattr(page.window, "width", None)
    return (w or 400) < DESKTOP_BREAKPOINT





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

    if t == "stepper":
        steps = c.get("steps", [])
        if not steps:
            errors.append("Walkthrough requires at least one step.")
        else:
            for i, s in enumerate(steps, start=1):
                if not str(s.get("headline", "")).strip():
                    errors.append(f"Step {i} requires a headline.")
                if not str(s.get("content", "")).strip():
                    errors.append(f"Step {i} requires explanation content.")

    if t == "sequencer":
        if not str(c.get("prompt", "")).strip():
            errors.append("Sequence challenge requires a prompt instruction.")
        items = c.get("items", [])
        if not items or len(items) < 2:
            errors.append("Sequence challenge requires at least 2 steps to arrange.")
        else:
            for i, it in enumerate(items, start=1):
                if not str(it.get("label", "")).strip():
                    errors.append(f"Sequence item {i} requires a label/description.")

    if t == "cloze":
        text = str(c.get("text", "")).strip()
        if not text:
            errors.append("Cloze lesson requires text content.")
        elif "[[" not in text or "]]" not in text:
            errors.append("Cloze text must include at least one [[blank]] or [[blank|hint]].")

    if t == "code_lab":
        if not str(c.get("instructions", "")).strip():
            errors.append("Code Lab requires instructions.")
        if not str(c.get("starter_code", "")).strip():
            errors.append("Code Lab requires starter code.")

    return errors


# =========================================================
# LESSON PREVIEW RENDERERS
# (Mirrors the student-facing renderers, but reads straight off the
#  in-memory lesson dict being edited — no DB fetch, no publish needed.)
# =========================================================

def preview_placeholder(message: str, icon):
    return ft.Container(
        padding=40,
        border_radius=14,
        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
        bgcolor=ft.Colors.SURFACE,
        content=ft.Column(
            [
                ft.Icon(icon, size=44, color=ft.Colors.OUTLINE),
                ft.Text(message, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
        ),
    )


def render_preview_video_block(value, lesson):
    if not str(value or "").strip():
        return preview_placeholder("No video uploaded yet.", ft.Icons.VIDEOCAM_OFF_ROUNDED)

    file_title = (
        lesson.get("content", {}).get("file_name", "Video Lesson")
        if isinstance(lesson.get("content"), dict)
        else (lesson.get("title") or "Video Lesson")
    )

    player = AdaptiveVideoPlayer(
        media_url=value,
        title=file_title,
        autoplay=False,
    )

    return ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        content=player,
    )


def render_preview_notes_block(value, lesson):
    async def handle_link_tap(e):
        await e.page.launch_url(e.data)

    display_value = str(value or "").strip() or "_No notes added yet._"

    return ft.Container(
        padding=20,
        border_radius=12,
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.LIGHTBULB_OUTLINE_ROUNDED, size=18, color=ft.Colors.AMBER_400),
                        ft.Text("Lesson Notes & Key Takeaways", weight=ft.FontWeight.BOLD, size=14, color=ft.Colors.ON_SURFACE),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Markdown(
                    display_value,
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
                        code_text_style=ft.TextStyle(
                            size=13.5,
                            font_family="Roboto Mono, monospace",
                            color=ft.Colors.ON_SURFACE,
                            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                        ),
                    ),
                ),
            ],
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.START,
        ),
    )


def render_preview_document_block(value, lesson):
    if not str(value or "").strip():
        return preview_placeholder("No document uploaded yet.", ft.Icons.DESCRIPTION_OUTLINED)

    file_name = (
        lesson.get("content", {}).get("file_name", "Course Document")
        if isinstance(lesson.get("content"), dict)
        else "Course Document"
    )

    async def handle_download(e):
        target_page = lesson.get("_page") or e.page
        await open_or_download_asset(target_page, value, file_name)

    target_page = lesson.get("_page")
    mobile_mode = is_mobile(target_page) if target_page else False

    doc_icon = ft.Container(
        width=48,
        height=48,
        border_radius=10,
        bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.RED_500),
        alignment=ft.Alignment.CENTER,
        content=ft.Icon(ft.Icons.PICTURE_AS_PDF_ROUNDED, size=26, color=ft.Colors.RED_500),
    )
    doc_details = ft.Column(
        [
            ft.Text(file_name, weight=ft.FontWeight.BOLD, size=14, color=ft.Colors.ON_SURFACE, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
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
                tight=True,
            ),
        ],
        expand=True,
        spacing=4,
    )
    download_btn = ft.FilledButton(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.DOWNLOAD_ROUNDED, size=16, color=ft.Colors.SURFACE),
                ft.Text("Download", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.SURFACE),
            ],
            tight=True,
            spacing=6,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        style=ft.ButtonStyle(
            bgcolor=UI_ACCENT,
            shape=ft.RoundedRectangleBorder(radius=8),
            padding=ft.Padding.symmetric(horizontal=16, vertical=10),
        ),
        on_click=handle_download,
    )

    if mobile_mode:
        card_content = ft.Column(
            [
                ft.Row([doc_icon, doc_details], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                download_btn,
            ],
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
    else:
        card_content = ft.Row(
            [doc_icon, doc_details, download_btn],
            spacing=16,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    return ft.Container(
        padding=16 if mobile_mode else 20,
        border_radius=12,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
        bgcolor=ft.Colors.SURFACE,
        content=card_content,
    )


def render_preview_text_block(value, lesson):
    if not str(value or "").strip():
        return preview_placeholder("No text added yet.", ft.Icons.NOTES_ROUNDED)

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
                    size=13.5,
                    font_family="Roboto Mono, monospace",
                    color=ft.Colors.ON_SURFACE,
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                ),
                blockquote_decoration=ft.BoxDecoration(
                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                    border=ft.Border.only(left=ft.BorderSide(3.5, ft.Colors.AMBER_500)),
                    border_radius=ft.BorderRadius.all(6),
                ),
                blockquote_text_style=ft.TextStyle(
                    size=14.5,
                    italic=True,
                    color=ft.Colors.ON_SURFACE,
                    height=1.5,
                ),
                blockquote_padding=ft.Padding.symmetric(horizontal=16, vertical=10),
            ),
        ),
    )


def render_preview_audio_block(value, lesson):
    if not str(value or "").strip():
        return preview_placeholder("No audio uploaded yet.", ft.Icons.AUDIO_FILE_ROUNDED)

    file_name = (
        lesson.get("content", {}).get("file_name", "Audio Lesson")
        if isinstance(lesson.get("content"), dict)
        else "Audio Lesson"
    )

    async def handle_download(e):
        target_page = lesson.get("_page") or e.page
        await open_or_download_asset(target_page, value, file_name)

    target_page = lesson.get("_page")
    mobile_mode = is_mobile(target_page) if target_page else False

    audio_icon = ft.Container(
        width=48,
        height=48,
        border_radius=10,
        bgcolor=ft.Colors.with_opacity(0.10, UI_ACCENT),
        alignment=ft.Alignment.CENTER,
        content=ft.Icon(ft.Icons.HEADPHONES_ROUNDED, size=26, color=UI_ACCENT),
    )
    audio_details = ft.Column(
        [
            ft.Text(file_name, weight=ft.FontWeight.BOLD, size=14, color=ft.Colors.ON_SURFACE, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
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
                tight=True,
            ),
        ],
        expand=True,
        spacing=4,
    )
    download_btn = ft.FilledButton(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.DOWNLOAD_ROUNDED, size=16, color=ft.Colors.SURFACE),
                ft.Text("Download Audio", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.SURFACE),
            ],
            tight=True,
            spacing=6,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        style=ft.ButtonStyle(
            bgcolor=UI_ACCENT,
            shape=ft.RoundedRectangleBorder(radius=8),
            padding=ft.Padding.symmetric(horizontal=16, vertical=10),
        ),
        on_click=handle_download,
    )

    if mobile_mode:
        card_content = ft.Column(
            [
                ft.Row([audio_icon, audio_details], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                download_btn,
            ],
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
    else:
        card_content = ft.Row(
            [audio_icon, audio_details, download_btn],
            spacing=16,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    return ft.Container(
        padding=16 if mobile_mode else 20,
        border_radius=12,
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
        content=card_content,
    )


def render_preview_cards_block(value, lesson):
    cards_list = [c for c in (value or []) if c]
    if not cards_list:
        return preview_placeholder("Add at least one flashcard to preview.", ft.Icons.STYLE_ROUNDED)

    card_idx = [0]
    is_animating = [False]
    total_cards = len(cards_list)

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

    init_text = parse_card(cards_list[0])

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

    async def go_forward(e=None):
        if card_idx[0] >= total_cards - 1 or is_animating[0]:
            return
        is_animating[0] = True
        card_idx[0] += 1
        card_md.value = parse_card(cards_list[card_idx[0]])
        counter_badge.content.value = f"Card {card_idx[0] + 1} of {total_cards}"
        progress_track.value = (card_idx[0] + 1) / max(total_cards, 1)
        prev_btn.disabled = card_idx[0] == 0
        next_btn.disabled = card_idx[0] == total_cards - 1
        is_animating[0] = False
        p = lesson.get("_page")
        if p:
            p.update()

    async def go_back(e=None):
        if card_idx[0] <= 0 or is_animating[0]:
            return
        is_animating[0] = True
        card_idx[0] -= 1
        card_md.value = parse_card(cards_list[card_idx[0]])
        counter_badge.content.value = f"Card {card_idx[0] + 1} of {total_cards}"
        progress_track.value = (card_idx[0] + 1) / max(total_cards, 1)
        prev_btn.disabled = card_idx[0] == 0
        next_btn.disabled = card_idx[0] == total_cards - 1
        is_animating[0] = False
        p = lesson.get("_page")
        if p:
            p.update()

    def on_card_tap(e):
        p = lesson.get("_page") or e.page
        if p:
            p.run_task(go_forward)

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
            [card_md],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
        ),
        ink=True,
        on_click=on_card_tap,
    )

    prev_btn = ft.OutlinedButton(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.ARROW_BACK_ROUNDED, size=15, color=ft.Colors.ON_SURFACE),
                ft.Text("Previous", size=12.5, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
            ],
            tight=True,
            spacing=6,
        ),
        on_click=lambda e: (lesson.get("_page") or e.page).run_task(go_back),
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
        on_click=lambda e: (lesson.get("_page") or e.page).run_task(go_forward),
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
                        ft.Container(
                            expand=True,
                            alignment=ft.Alignment.CENTER,
                            content=ft.Text(
                                "Tap card or arrows",
                                size=11,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                italic=True,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ),
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
            "Add scenario text and at least two choices to preview.", ft.Icons.CALL_SPLIT_ROUNDED
        )

    consequence_box = ft.Container(
        padding=18,
        border_radius=10,
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
        visible=False,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.LIGHTBULB_CIRCLE_ROUNDED, color=ft.Colors.AMBER_400, size=20),
                        ft.Text("Scenario Outcome & Analysis", weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE, size=14),
                    ],
                    spacing=8,
                ),
                ft.Markdown(
                    "",
                    selectable=False,
                    extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
                    md_style_sheet=ft.MarkdownStyleSheet(
                        p_text_style=ft.TextStyle(color=ft.Colors.ON_SURFACE, size=14, height=1.5),
                        code_text_style=ft.TextStyle(
                            size=13.5,
                            font_family="Roboto Mono, monospace",
                            color=ft.Colors.ON_SURFACE,
                            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                        ),
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
        p = lesson.get("_page")
        if p:
            p.update()

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
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
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

        type_tag = ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            border_radius=4,
            bgcolor=ft.Colors.with_opacity(0.08, UI_ACCENT),
            content=ft.Text(
                "MULTIPLE CHOICE" if is_multi_select else "SINGLE CHOICE",
                size=9,
                weight=ft.FontWeight.BOLD,
                color=UI_ACCENT,
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
            options_rows = []
            for opt in options_data:
                opt_text = opt.get("text", "")
                cb = ft.Checkbox(
                    value=False,
                    data=opt_text,
                    fill_color={ft.ControlState.SELECTED: UI_ACCENT},
                    check_color=ft.Colors.SURFACE,
                )
                options_rows.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                        border_radius=8,
                        bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
                        content=ft.Row(
                            [cb, ft.Text(opt_text, expand=True, size=13.5, color=ft.Colors.ON_SURFACE)],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=8,
                        ),
                    )
                )
            options_ui = ft.Column(options_rows, spacing=8)
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
                                ft.Radio(value=opt_text, fill_color={ft.ControlState.SELECTED: UI_ACCENT}),
                                ft.Text(opt_text, expand=True, size=13.5, color=ft.Colors.ON_SURFACE),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=8,
                        ),
                    )
                )
            options_ui = ft.RadioGroup(content=ft.Column(radio_options, spacing=8))

        question_cards.append(
            ft.Container(
                padding=22,
                border_radius=12,
                bgcolor=ft.Colors.SURFACE,
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
                                            bgcolor=UI_ACCENT,
                                            content=ft.Text(f"Q{q_idx + 1}", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.SURFACE),
                                        ),
                                        type_tag,
                                    ],
                                    spacing=8,
                                ),
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

    return ft.Container(
        padding=0,
        content=ft.Column(question_cards, spacing=16, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
    )


def render_preview_stepper_ui(lesson: dict):
    content = lesson.get("content", {})
    steps = content.get("steps", [])
    valid_steps = [s for s in steps if str(s.get("headline", "")).strip() or str(s.get("content", "")).strip()]

    if not valid_steps:
        return preview_placeholder("Add at least one step to preview walkthrough.", ft.Icons.LINEAR_SCALE_ROUNDED)

    current_step_idx = [0]

    title_text = content.get("title", "")
    intro_text = content.get("intro", "")

    header_elements = []
    if title_text:
        header_elements.append(ft.Text(title_text, size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE))
    if intro_text:
        header_elements.append(ft.Markdown(intro_text, md_style_sheet=ft.MarkdownStyleSheet(p_text_style=ft.TextStyle(size=13, color=ft.Colors.ON_SURFACE_VARIANT))))

    progress_bar = ft.ProgressBar(value=1.0 / len(valid_steps), color=ft.Colors.CYAN_600, bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE))
    counter_label = ft.Text(f"Phase 1 of {len(valid_steps)}", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_600)

    tag_chip = ft.Container(
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
        border_radius=6,
        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.CYAN_600),
        content=ft.Text(valid_steps[0].get("tag", "Step 1"), size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_600),
    )
    headline_text = ft.Text(valid_steps[0].get("headline", ""), size=17, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE)
    content_md = ft.Markdown(
        valid_steps[0].get("content", ""),
        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
        md_style_sheet=ft.MarkdownStyleSheet(p_text_style=ft.TextStyle(size=14, height=1.5, color=ft.Colors.ON_SURFACE)),
    )
    takeaway_col = ft.Container(
        padding=14,
        border_radius=8,
        bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.CYAN_600),
        border=ft.Border.only(left=ft.BorderSide(3.5, ft.Colors.CYAN_600)),
        visible=bool(valid_steps[0].get("takeaway", "").strip()),
        content=ft.Row(
            [
                ft.Icon(ft.Icons.LIGHTBULB_OUTLINE_ROUNDED, color=ft.Colors.CYAN_600, size=20),
                ft.Column(
                    [
                        ft.Text("Key Takeaway", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_600),
                        ft.Text(valid_steps[0].get("takeaway", ""), size=13, color=ft.Colors.ON_SURFACE),
                    ],
                    spacing=2,
                    expand=True,
                ),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.START,
        ),
    )

    prev_btn = ft.OutlinedButton(
        content=ft.Row([ft.Icon(ft.Icons.ARROW_BACK_ROUNDED, size=14), ft.Text("Previous", size=12, weight=ft.FontWeight.BOLD)], tight=True, spacing=4),
        disabled=True,
    )
    next_btn = ft.FilledButton(
        content=ft.Row([ft.Text("Next Phase", size=12, weight=ft.FontWeight.BOLD), ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=14)], tight=True, spacing=4),
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
            next_btn.content.controls[0].value = "Completed"
            next_btn.content.controls[1].icon = ft.Icons.CHECK_ROUNDED
            next_btn.style.bgcolor = ft.Colors.GREEN_600
        else:
            next_btn.content.controls[0].value = "Next Phase"
            next_btn.content.controls[1].icon = ft.Icons.ARROW_FORWARD_ROUNDED
            next_btn.style.bgcolor = ft.Colors.CYAN_600
        lesson["_page"].update()

    def on_prev(e):
        if current_step_idx[0] > 0:
            update_step_view(current_step_idx[0] - 1)

    def on_next(e):
        if current_step_idx[0] < len(valid_steps) - 1:
            update_step_view(current_step_idx[0] + 1)

    prev_btn.on_click = on_prev
    next_btn.on_click = on_next

    return ft.Container(
        padding=20,
        border_radius=12,
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
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
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
    )


def render_preview_sequencer_ui(lesson: dict):
    content = lesson.get("content", {})
    prompt = content.get("prompt", "")
    items = content.get("items", [])
    valid_items = [it for it in items if str(it.get("label", "")).strip()]

    if len(valid_items) < 2:
        return preview_placeholder("Add at least 2 sequence items with labels to preview challenge.", ft.Icons.REORDER_ROUNDED)

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

    feedback_banner = ft.Container(visible=False, padding=12, border_radius=8)
    items_column = ft.Column(spacing=8, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    def render_items_list(status_map=None):
        items_column.controls.clear()
        for idx, it in enumerate(current_items):
            is_correct_pos = status_map.get(it.get("id")) if status_map else None

            if is_correct_pos is True:
                border_color = ft.Colors.GREEN_600
                bg_color = ft.Colors.with_opacity(0.08, ft.Colors.GREEN_600)
                status_icon = ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.GREEN_600, size=18)
            elif is_correct_pos is False:
                border_color = ft.Colors.AMBER_600
                bg_color = ft.Colors.with_opacity(0.08, ft.Colors.AMBER_600)
                status_icon = ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, color=ft.Colors.AMBER_600, size=18)
            else:
                border_color = ft.Colors.OUTLINE_VARIANT
                bg_color = ft.Colors.SURFACE
                status_icon = ft.Container()

            def move_up(i):
                def handler(e):
                    if i > 0:
                        current_items[i], current_items[i - 1] = current_items[i - 1], current_items[i]
                        render_items_list(None)
                        feedback_banner.visible = False
                        lesson["_page"].update()
                return handler

            def move_down(i):
                def handler(e):
                    if i < len(current_items) - 1:
                        current_items[i], current_items[i + 1] = current_items[i + 1], current_items[i]
                        render_items_list(None)
                        feedback_banner.visible = False
                        lesson["_page"].update()
                return handler

            explanation_ui = ft.Container()
            if is_correct_pos is True and it.get("explanation", "").strip():
                explanation_ui = ft.Container(
                    padding=8,
                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                    border_radius=6,
                    content=ft.Text(f"💡 {it.get('explanation')}", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                )

            item_card = ft.Container(
                padding=12,
                border_radius=10,
                border=ft.Border.all(1, border_color),
                bgcolor=bg_color,
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Container(
                                    width=26,
                                    height=26,
                                    border_radius=999,
                                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_600),
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.Text(f"{idx + 1}", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_600),
                                ),
                                ft.Text(it.get("label", ""), size=14, weight=ft.FontWeight.W_500, expand=True),
                                status_icon,
                                ft.Row(
                                    [
                                        ft.IconButton(ft.Icons.KEYBOARD_ARROW_UP_ROUNDED, icon_size=18, disabled=(idx == 0), on_click=move_up(idx)),
                                        ft.IconButton(ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED, icon_size=18, disabled=(idx == len(current_items) - 1), on_click=move_down(idx)),
                                    ],
                                    spacing=0,
                                ),
                            ],
                            spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        explanation_ui,
                    ],
                    spacing=6,
                ),
            )
            items_column.controls.append(item_card)

    def check_sequence(e):
        correct_order_ids = [it.get("id") for it in valid_items]
        current_ids = [it.get("id") for it in current_items]

        status_map = {}
        all_correct = True
        correct_count = 0
        for i, it_id in enumerate(current_ids):
            is_match = (it_id == correct_order_ids[i])
            status_map[it_id] = is_match
            if is_match:
                correct_count += 1
            else:
                all_correct = False

        if all_correct:
            feedback_banner.bgcolor = ft.Colors.with_opacity(0.15, ft.Colors.GREEN_600)
            feedback_banner.border = ft.Border.all(1, ft.Colors.GREEN_600)
            feedback_banner.content = ft.Row([
                ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.GREEN_600),
                ft.Text("Sequence is 100% correct! Excellent work.", weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_600),
            ], spacing=8)
        else:
            feedback_banner.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.AMBER_600)
            feedback_banner.border = ft.Border.all(1, ft.Colors.AMBER_600)
            feedback_banner.content = ft.Row([
                ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, color=ft.Colors.AMBER_600),
                ft.Text(f"{correct_count} of {len(valid_items)} steps in correct position. Adjust the highlighted steps.", weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_600),
            ], spacing=8)
        feedback_banner.visible = True
        render_items_list(status_map)
        lesson["_page"].update()

    def reset_shuffle(e):
        nonlocal current_items
        current_items = get_scrambled_items(valid_items)
        feedback_banner.visible = False
        render_items_list(None)
        lesson["_page"].update()

    render_items_list(None)

    return ft.Container(
        padding=20,
        border_radius=12,
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.REORDER_ROUNDED, color=ft.Colors.AMBER_600, size=22),
                        ft.Text("Process Order Challenge", weight=ft.FontWeight.BOLD, size=16, color=ft.Colors.ON_SURFACE),
                    ],
                    spacing=8,
                ),
                ft.Markdown(
                    prompt or "Arrange the following steps in the correct order:",
                    extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                    md_style_sheet=ft.MarkdownStyleSheet(p_text_style=ft.TextStyle(size=14, color=ft.Colors.ON_SURFACE)),
                ),
                feedback_banner,
                items_column,
                ft.Row(
                    [
                        ft.OutlinedButton("Shuffle / Reset", icon=ft.Icons.REFRESH_ROUNDED, on_click=reset_shuffle),
                        ft.FilledButton(
                            "Check Order",
                            icon=ft.Icons.CHECK_ROUNDED,
                            style=ft.ButtonStyle(bgcolor=ft.Colors.AMBER_600, color=ft.Colors.WHITE),
                            on_click=check_sequence,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            ],
            spacing=14,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
    )


def render_preview_cloze_ui(lesson: dict):
    content = lesson.get("content", {})
    raw_text = content.get("text", "")
    distractors = content.get("distractors", [])
    explanation = content.get("explanation", "")

    segments, blanks = parse_cloze_text(raw_text)
    if not blanks:
        return preview_placeholder("Add text with [[blank]] or [[blank|hint]] to preview fill-in-the-blanks.", ft.Icons.EDIT_NOTE_ROUNDED)

    all_words = list(set([b["answer"] for b in blanks] + [d for d in distractors if d.strip()]))
    random.seed(42)
    random.shuffle(all_words)

    user_answers = {b["index"]: "" for b in blanks}
    validation_state = {}

    feedback_banner = ft.Container(visible=False, padding=12, border_radius=8)
    explanation_box = ft.Container(
        padding=14,
        border_radius=8,
        bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.GREEN_600),
        border=ft.Border.only(left=ft.BorderSide(3.5, ft.Colors.GREEN_600)),
        visible=False,
        content=ft.Column(
            [
                ft.Row([ft.Icon(ft.Icons.LIGHTBULB_ROUNDED, color=ft.Colors.GREEN_600, size=18), ft.Text("Pedagogical Summary", weight=ft.FontWeight.BOLD, size=13, color=ft.Colors.GREEN_600)], spacing=6),
                ft.Markdown(explanation, md_style_sheet=ft.MarkdownStyleSheet(p_text_style=ft.TextStyle(size=13, color=ft.Colors.ON_SURFACE))),
            ],
            spacing=6,
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
                    border_c = ft.Colors.CYAN_600 if not ans_val else ft.Colors.PRIMARY
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
                            lesson["_page"].update()
                    return handler

                text_flow_row.controls.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                        border_radius=6,
                        border=ft.Border.all(1.5, border_c),
                        bgcolor=bg_c,
                        content=ft.Text(display_label, size=13, weight=ft.FontWeight.BOLD, color=text_c),
                        tooltip="Click to clear" if ans_val else (b_info["hint"] or "Blank"),
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
                    lesson["_page"].update()
                return handler

            word_bank_row.controls.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                    border_radius=999,
                    border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT if not is_used else ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE)),
                    bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE) if not is_used else ft.Colors.TRANSPARENT,
                    content=ft.Text(w, size=12, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE if not is_used else ft.Colors.with_opacity(0.3, ft.Colors.ON_SURFACE)),
                    opacity=0.4 if is_used else 1.0,
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
                ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.GREEN_600),
                ft.Text("All blanks filled with 100% accuracy!", weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_600, expand=True),
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)
            if explanation:
                explanation_box.visible = True
        else:
            feedback_banner.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.AMBER_600)
            feedback_banner.border = ft.Border.all(1, ft.Colors.AMBER_600)
            feedback_banner.content = ft.Row([
                ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, color=ft.Colors.AMBER_600),
                ft.Text(f"{correct_count} of {len(blanks)} correct. Tap highlighted blanks to swap words.", weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_600, expand=True),
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        feedback_banner.visible = True
        rebuild_ui()
        lesson["_page"].update()

    def reset_blanks(e):
        for b in blanks:
            user_answers[b["index"]] = ""
        validation_state.clear()
        feedback_banner.visible = False
        explanation_box.visible = False
        rebuild_ui()
        lesson["_page"].update()

    rebuild_ui()

    return ft.Container(
        padding=20,
        border_radius=12,
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
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
                ft.Text("Word Bank (Tap word to place in next blank):", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
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
            spacing=14,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
    )


def render_preview_code_lab_ui(lesson: dict):
    content = lesson.get("content", {})
    language = content.get("language", "python").lower().strip()
    instructions = content.get("instructions", "")
    starter_code = content.get("starter_code", "")
    setup_sql = content.get("setup_sql", "")
    test_cases = content.get("test_cases", [])

    if not instructions and not starter_code:
        return preview_placeholder("Add instructions and starter code to preview Code Lab.", ft.Icons.CODE_ROUNDED)

    is_sql = "sql" in language
    is_python = language in ("python", "py", "python3")
    is_html = language in ("html", "web", "html5", "htm")
    is_cpp = language in ("cpp", "c++", "cplusplus")
    is_js = language in ("javascript", "js")
    is_ts = language in ("typescript", "ts")
    is_java = "java" in language
    is_c = (language == "c")

    if is_sql:
        lang_display = "SQLite In-Memory (Offline)"
        lang_color = ft.Colors.TEAL_400
    elif is_python:
        lang_display = "Python 3.12 (Offline)"
        lang_color = ft.Colors.BLUE_400
    elif is_html:
        lang_display = "HTML5 / Web (Live Sandbox Preview)"
        lang_color = ft.Colors.DEEP_ORANGE_400
    elif is_cpp:
        lang_display = "C++ (GCC 9.2)"
        lang_color = ft.Colors.CYAN_400
    elif is_js:
        lang_display = "JavaScript (Node.js)"
        lang_color = ft.Colors.AMBER_400
    elif is_ts:
        lang_display = "TypeScript"
        lang_color = ft.Colors.LIGHT_BLUE_400
    elif is_java:
        lang_display = "Java (OpenJDK)"
        lang_color = ft.Colors.ORANGE_400
    elif is_c:
        lang_display = "C (GCC 9.2)"
        lang_color = ft.Colors.BLUE_GREY_400
    else:
        lang_display = f"{language.upper()}"
        lang_color = ft.Colors.PURPLE_400

    code_input = ft.TextField(
        value=starter_code,
        multiline=True,
        min_lines=6,
        max_lines=16,
        border_radius=8,
        bgcolor=ft.Colors.BLACK,
        text_style=ft.TextStyle(font_family="monospace", size=13, color=ft.Colors.GREEN_300),
    )

    stdin_field = ft.TextField(
        label="Program Input (stdin)",
        hint_text="Input text to pass to stdin calls (optional)...",
        dense=True,
        border_radius=8,
        visible=(not is_sql and not is_html),
        text_style=ft.TextStyle(font_family="monospace", size=12),
    )

    console_output = ft.Text("Click 'Run Code' to execute in sandbox...", font_family="monospace", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
    test_results_col = ft.Column(spacing=6, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    console_container = ft.Container(
        padding=12,
        border_radius=8,
        bgcolor=ft.Colors.BLACK,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE)),
        content=console_output,
    )

    status_banner = ft.Container(visible=False, padding=10, border_radius=8)

    run_btn_icon = ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, color=ft.Colors.WHITE, size=16)
    run_btn_spinner = ft.ProgressRing(width=14, height=14, stroke_width=2, color=ft.Colors.WHITE, visible=False)
    run_btn_text = ft.Text("Run Code", color=ft.Colors.WHITE, size=12, weight=ft.FontWeight.W_600)

    run_btn = ft.FilledButton(
        content=ft.Row(
            [run_btn_icon, run_btn_spinner, run_btn_text],
            tight=True,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=6,
        ),
        style=ft.ButtonStyle(bgcolor=ft.Colors.DEEP_PURPLE_400, color=ft.Colors.WHITE),
        on_click=lambda e: lesson["_page"].run_task(execute_and_update, e),
    )

    async def execute_and_update(e):
        run_btn.disabled = True
        run_btn_icon.visible = False
        run_btn_spinner.visible = True
        run_btn_text.value = "Running…"
        console_output.value = "Executing in sandbox…"
        console_output.color = ft.Colors.ON_SURFACE_VARIANT
        lesson["_page"].update()

        try:
            user_code = code_input.value
            results = await asyncio.to_thread(run_code_lab_tests, language, user_code, setup_sql, test_cases)
            has_offline_blocked = any(tr.get("offline_blocked") for tr in results)

            if is_sql:
                res = await asyncio.to_thread(execute_sql, user_code, setup_sql)
                if res["success"]:
                    cols = " | ".join(res["columns"])
                    rows_text = "\n".join([" | ".join([str(v) for v in r]) for r in res["rows"][:20]])
                    console_output.value = f"COLUMNS: {cols}\n" + ("-" * 40) + f"\n{rows_text or '(0 rows returned)'}"
                    console_output.color = ft.Colors.GREEN_300
                else:
                    console_output.value = f"SQL ERROR:\n{res['error']}"
                    console_output.color = ft.Colors.RED_400
            elif is_python:
                passed_stdin = stdin_field.value if stdin_field.value else (test_cases[0].get("input", "") if test_cases else "")
                res = await asyncio.to_thread(execute_python, user_code, test_input=passed_stdin)
                if res["success"]:
                    console_output.value = res["output"] or "(Executed with no stdout output)"
                    console_output.color = ft.Colors.GREEN_300
                else:
                    console_output.value = f"RUNTIME ERROR:\n{res['error']}"
                    console_output.color = ft.Colors.RED_400
            elif is_html:
                res = await asyncio.to_thread(execute_html, user_code)
                if res["success"]:
                    console_output.value = (
                        f"HTML/WEB SANDBOX VALIDATION:\n"
                        f"{res['output']}\n\n"
                        f"💡 Tip: Click 'Preview in Browser' to render and interact with your webpage and scripts live."
                    )
                    console_output.color = ft.Colors.GREEN_300
                else:
                    console_output.value = f"HTML VALIDATION ERROR:\n{res['error']}"
                    console_output.color = ft.Colors.RED_400
            else:
                passed_stdin = stdin_field.value if stdin_field.value else (test_cases[0].get("input", "") if test_cases else "")
                res = await asyncio.to_thread(execute_remote_code, language, user_code, test_input=passed_stdin)
                if res.get("offline_blocked"):
                    has_offline_blocked = True
                    console_output.value = f"OFFLINE NOTICE:\n{res['error']}"
                    console_output.color = ft.Colors.AMBER_400
                elif res["success"]:
                    console_output.value = res["output"] or "(Code compiled and executed with no stdout)"
                    console_output.color = ft.Colors.GREEN_300
                else:
                    console_output.value = f"COMPILATION / RUNTIME ERROR:\n{res['error']}"
                    console_output.color = ft.Colors.RED_400

            test_results_col.controls.clear()
            all_passed = True
            for tr in results:
                if not tr["passed"]:
                    all_passed = False
                
                is_off = tr.get("offline_blocked", False)
                item_color = ft.Colors.AMBER_500 if is_off else (ft.Colors.GREEN_600 if tr["passed"] else ft.Colors.RED_500)
                item_icon = ft.Icons.WIFI_OFF_ROUNDED if is_off else (ft.Icons.CHECK_CIRCLE_ROUNDED if tr["passed"] else ft.Icons.CANCEL_ROUNDED)
                item_status = "OFFLINE" if is_off else ("PASSED" if tr["passed"] else "FAILED")

                test_results_col.controls.append(
                    ft.Container(
                        padding=8,
                        border_radius=6,
                        bgcolor=ft.Colors.with_opacity(0.06, item_color),
                        border=ft.Border.all(1, item_color),
                        content=ft.Row(
                            [
                                ft.Icon(item_icon, color=item_color, size=16),
                                ft.Text(tr["description"], size=12, weight=ft.FontWeight.W_500, expand=True),
                                ft.Text(item_status, size=11, weight=ft.FontWeight.BOLD, color=item_color),
                            ],
                            spacing=8,
                        ),
                    )
                )

            if test_cases:
                if has_offline_blocked:
                    status_banner.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.AMBER_600)
                    status_banner.border = ft.Border.all(1, ft.Colors.AMBER_600)
                    status_banner.content = ft.Text("Internet required to compile this language.", weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_600, size=12)
                elif all_passed:
                    status_banner.bgcolor = ft.Colors.with_opacity(0.15, ft.Colors.GREEN_600)
                    status_banner.border = ft.Border.all(1, ft.Colors.GREEN_600)
                    status_banner.content = ft.Text("All test cases passed successfully!", weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_600)
                else:
                    status_banner.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.RED_500)
                    status_banner.border = ft.Border.all(1, ft.Colors.RED_500)
                    status_banner.content = ft.Text("Some tests failed. Review the results above.", weight=ft.FontWeight.BOLD, color=ft.Colors.RED_500)
                status_banner.visible = True
            else:
                status_banner.visible = False

        finally:
            run_btn.disabled = False
            run_btn_icon.visible = True
            run_btn_spinner.visible = False
            run_btn_text.value = "Run Code"
            lesson["_page"].update()

    def reset_code(e):
        code_input.value = starter_code
        stdin_field.value = ""
        console_output.value = "Code reset to starter template."
        console_output.color = ft.Colors.ON_SURFACE_VARIANT
        test_results_col.controls.clear()
        status_banner.visible = False
        lesson["_page"].update()

    async def launch_browser_preview(e):
        current_html = code_input.value or "<h1>Empty HTML Document</h1>"
        tmp_dir = tempfile.gettempdir()
        tmp_path = os.path.join(tmp_dir, f"nu_lab_preview_{lesson.get('id', 'temp')}.html")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(current_html)
        file_url = f"file:///{tmp_path.replace(os.sep, '/')}"
        res = lesson["_page"].launch_url(file_url)
        if asyncio.iscoroutine(res):
            await res

    action_buttons = [
        ft.OutlinedButton("Reset Code", icon=ft.Icons.REFRESH_ROUNDED, on_click=reset_code),
    ]
    if is_html:
        action_buttons.append(
            ft.FilledButton(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.OPEN_IN_BROWSER_ROUNDED, color=ft.Colors.WHITE, size=16),
                        ft.Text("Preview in Browser", color=ft.Colors.WHITE, size=12, weight=ft.FontWeight.W_600),
                    ],
                    tight=True,
                    spacing=6,
                ),
                style=ft.ButtonStyle(bgcolor=ft.Colors.DEEP_ORANGE_500, color=ft.Colors.WHITE),
                tooltip="Open live rendering of this HTML/PWA in your browser",
                on_click=lambda e: lesson["_page"].run_task(launch_browser_preview, e),
            )
        )
    action_buttons.append(run_btn)

    return ft.Container(
        padding=20,
        border_radius=12,
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
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
                            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
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
                    md_style_sheet=ft.MarkdownStyleSheet(p_text_style=ft.TextStyle(size=14, color=ft.Colors.ON_SURFACE)),
                ),
                code_input,
                stdin_field,
                ft.Row(
                    action_buttons,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Text("Execution Console Output:", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                console_container,
                status_banner,
                test_results_col,
            ],
            spacing=14,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
    )


def render_lesson_preview(lesson: dict, page: ft.Page):
    lesson["_page"] = page
    content = lesson.get("content", {})
    blocks = []

    for key, value in content.items():
        if lesson.get("type") == "cloze" and key == "text":
            continue
        if key in ["questions", "scenario", "choices", "prompt_text", "file_name", "steps", "items", "prompt", "distractors", "explanation", "starter_code", "solution_code", "setup_sql", "test_cases", "language", "instructions", "title", "intro"]:
            continue
        renderer = PREVIEW_CONTENT_RENDERERS.get(key)
        if renderer:
            blocks.append(renderer(value, lesson))

    if lesson.get("type") == "assessment":
        blocks.append(render_preview_assessment_ui(lesson))
    elif lesson.get("type") == "scenario":
        blocks.append(render_preview_scenario_ui(lesson))
    elif lesson.get("type") == "stepper":
        blocks.append(render_preview_stepper_ui(lesson))
    elif lesson.get("type") == "sequencer":
        blocks.append(render_preview_sequencer_ui(lesson))
    elif lesson.get("type") == "cloze":
        blocks.append(render_preview_cloze_ui(lesson))
    elif lesson.get("type") == "code_lab":
        blocks.append(render_preview_code_lab_ui(lesson))

    if not blocks:
        blocks.append(preview_placeholder("Nothing to preview yet — add some content first.", ft.Icons.INFO_OUTLINE_ROUNDED))

    return ft.Column(blocks, spacing=20, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)


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
    # Curriculum API
    # -----------------------------------------------------
    modules = None
    try:
        curriculum = await get_course_curriculum(token, course_id)
        modules = curriculum.get("modules") if curriculum else None
    except Exception:
        modules = None

    if not modules:
        modules = []

    modules = [ensure_module_shape(m) for m in modules]
    has_existing_materials = [bool(modules and any(len(m.get("lessons", [])) > 0 for m in modules))]

    # -----------------------------------------------------
    # Local state (LOCAL until publish)
    # -----------------------------------------------------
    active_module = None
    active_lesson = None
    editor_visible = [False]  # tracks whether editor panel is shown on mobile
    search_query = [""]
    collapsed_modules = set()
    summary_layout_updater = [None]

    editor_content = ft.Column(
        spacing=16,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )
    curriculum_column = ft.Column(
        spacing=16,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    # ----------------------------------------------------- 
    # Sidebar panel / Authoring Canvas
    # -----------------------------------------------------
    editor_panel_header_label = ft.Text(
        "Edit Lesson",
        size=15,
        weight=ft.FontWeight.BOLD,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )

    def close_editor(e=None):
        nonlocal active_lesson, active_module
        active_lesson = None
        active_module = None
        editor_content.controls.clear()
        editor_visible[0] = False
        curriculum_container.visible = True
        curriculum_container.width = None
        curriculum_container.expand = True
        editor_panel.visible = False
        refresh_curriculum()
        page.update()

    def open_single_lesson_preview(e=None):
        if not active_lesson:
            return
        t = active_lesson.get("type", "text")
        pw = getattr(page, "width", None)
        if pw is None and hasattr(page, "window") and page.window:
            pw = getattr(page.window, "width", None)
        pw = pw or 800

        ph = getattr(page, "height", None)
        if ph is None and hasattr(page, "window") and page.window:
            ph = getattr(page.window, "height", None)
        ph = ph or 700

        dlg_width = min(720, max(280, pw - 48))
        dlg_height = min(540, max(260, ph - 160))
        lesson_title = str(active_lesson.get("title") or "Lesson")

        preview_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(lesson_icon(t), color=lesson_color(t), size=20),
                    ft.Container(
                        expand=True,
                        content=ft.Text(
                            f"Preview: {lesson_title}",
                            weight=ft.FontWeight.BOLD,
                            size=16,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            content=ft.Container(
                width=dlg_width,
                height=dlg_height,
                content=ft.Column([render_lesson_preview(active_lesson, page)], scroll=ft.ScrollMode.AUTO),
            ),
            actions=[ft.TextButton("Close", on_click=lambda ev: close_single_preview(preview_dlg))],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(preview_dlg)
        preview_dlg.open = True
        page.update()

    def close_single_preview(dlg):
        dlg.open = False
        page.update()

    editor_panel_preview_btn = ft.OutlinedButton(
        "Preview",
        icon=ft.Icons.VISIBILITY_ROUNDED,
        height=34,
        style=ft.ButtonStyle(
            padding=ft.Padding.symmetric(horizontal=10, vertical=0),
            shape=ft.RoundedRectangleBorder(radius=8),
        ),
        on_click=open_single_lesson_preview,
    )

    editor_panel_preview_icon_btn = ft.IconButton(
        ft.Icons.VISIBILITY_ROUNDED,
        icon_size=18,
        tooltip="Preview lesson",
        on_click=open_single_lesson_preview,
    )

    editor_panel_actions_container = ft.Container(
        content=editor_panel_preview_icon_btn if is_mobile(page) else editor_panel_preview_btn
    )

    editor_panel_header_row = ft.Row(
        [
            ft.IconButton(
                ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED,
                icon_size=16,
                tooltip="Back to Outline",
                on_click=close_editor,
            ),
            ft.Container(
                expand=True,
                content=editor_panel_header_label,
            ),
            editor_panel_actions_container,
            ft.IconButton(
                ft.Icons.CLOSE_ROUNDED,
                icon_size=18,
                tooltip="Close editor",
                on_click=close_editor,
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=4,
    )

    editor_panel = ft.Container(
        visible=False,
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.only(left=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
        content=ft.Column(
            [
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12 if is_mobile(page) else 16, vertical=10),
                    bgcolor=ft.Colors.SURFACE,
                    border=ft.Border.only(bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
                    content=editor_panel_header_row,
                ),
                ft.Container(
                    expand=True,
                    padding=ft.Padding.symmetric(horizontal=12 if is_mobile(page) else 18, vertical=16),
                    content=editor_content,
                ),
            ],
            spacing=0,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
    )

    curriculum_container = ft.Container(
        expand=True,
        padding=ft.Padding.symmetric(horizontal=16, vertical=16),
        content=curriculum_column,
    )

    def on_resize(e=None):
        if summary_layout_updater[0]:
            summary_layout_updater[0]()
        if not is_mobile(page):
            editor_panel_actions_container.content = editor_panel_preview_btn
            curriculum_container.visible = True
            if active_lesson:
                curriculum_container.width = 380
                curriculum_container.expand = False
                editor_panel.visible = True
                editor_panel.width = None
                editor_panel.expand = True
            else:
                curriculum_container.width = None
                curriculum_container.expand = True
                editor_panel.visible = False
        else:
            editor_panel_actions_container.content = editor_panel_preview_icon_btn
            if editor_visible[0]:
                curriculum_container.visible = False
                curriculum_container.width = None
                curriculum_container.expand = False
                editor_panel.visible = True
                editor_panel.width = None
                editor_panel.expand = True
            else:
                curriculum_container.visible = True
                curriculum_container.width = None
                curriculum_container.expand = True
                editor_panel.visible = False
        page.update()

    page.on_resize = on_resize
    page.on_resized = on_resize

    # -----------------------------------------------------
    # Full-screen course preview
    # -----------------------------------------------------
    preview_title_text = ft.Text(
        "Course Preview",
        size=18,
        weight=ft.FontWeight.BOLD,
        max_lines=2,
    )
    preview_subtitle_text = ft.Text(
        "",
        size=12,
        color=ft.Colors.ON_SURFACE_VARIANT,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )
    preview_body_column = ft.Column([], spacing=20, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    preview_loading_socket = ft.Container(
        padding=60,
        alignment=ft.Alignment(0, 0),
        content=ft.Column(
            [
                ft.ProgressRing(color=UI_ACCENT, width=32, height=32, stroke_width=3),
                ft.Text("Loading preview…", color=ft.Colors.ON_SURFACE_VARIANT),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=14,
        ),
    )

    def close_preview(e=None):
        preview_overlay.visible = False
        page.update()

    def build_course_preview_content():
        blocks = []
        total_lessons = sum(len(m.get("lessons", [])) for m in modules)

        if not modules or total_lessons == 0:
            blocks.append(
                preview_placeholder(
                    "Add a module and some lessons to see a course preview.",
                    ft.Icons.MENU_BOOK_ROUNDED,
                )
            )
            return blocks, total_lessons

        for m_idx, m in enumerate(modules):
            blocks.append(
                ft.Row(
                    [
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                            border_radius=999,
                            bgcolor=ft.Colors.with_opacity(0.10, UI_ACCENT),
                            content=ft.Text(f"Module {m_idx + 1}", size=11, weight=ft.FontWeight.BOLD, color=UI_ACCENT),
                        ),
                        ft.Text(
                            m.get("title", "Untitled Module"),
                            size=18,
                            weight=ft.FontWeight.BOLD,
                            expand=True,
                        ),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )

            lessons = m.get("lessons", [])
            if not lessons:
                blocks.append(preview_placeholder("This module has no lessons yet.", ft.Icons.PLAYLIST_ADD_ROUNDED))
                continue

            for l in lessons:
                blocks.append(
                    ft.Row(
                        [
                            ft.Icon(lesson_icon(l["type"]), color=lesson_color(l["type"]), size=18),
                            ft.Text(
                                l.get("title", "Untitled Lesson"),
                                size=15,
                                weight=ft.FontWeight.W_600,
                                expand=True,
                            ),
                            lesson_badge(l["type"]),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                )
                blocks.append(render_lesson_preview(l, page))
                blocks.append(ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT))

        return blocks, total_lessons

    async def open_preview(e=None):
        preview_title_text.value = f"Preview: {course_name}"
        preview_subtitle_text.value = "Live draft preview (mirrors learner view)"

        preview_body_column.controls.clear()
        preview_body_column.controls.append(preview_loading_socket)
        preview_overlay.visible = True
        page.update()

        await asyncio.sleep(0.05)

        blocks, total_lessons = build_course_preview_content()

        total_quizzes = sum(
            1 for m in modules for l in m.get("lessons", []) if l.get("type") == "assessment"
        )
        preview_subtitle_text.value = (
            f"{len(modules)} module{'s' if len(modules) != 1 else ''} • "
            f"{total_lessons} lesson{'s' if total_lessons != 1 else ''} • "
            f"{total_quizzes} assessment{'s' if total_quizzes != 1 else ''}"
        )

        preview_body_column.controls.clear()
        preview_body_column.controls.extend(blocks)
        page.update()

    close_btn_label = "Close" if is_mobile(page) else "Close Preview"
    preview_overlay = ft.Container(
        visible=False,
        top=0,
        left=0,
        right=0,
        bottom=0,
        expand=True,
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        content=ft.Column(
            [
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=16 if is_mobile(page) else 24, vertical=12),
                    bgcolor=ft.Colors.SURFACE,
                    border=ft.Border.only(bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
                    content=ft.Row(
                        [
                            ft.Row(
                                [
                                    ft.IconButton(
                                        ft.Icons.ARROW_BACK_ROUNDED,
                                        tooltip="Back to Builder",
                                        on_click=close_preview,
                                    ),
                                    ft.Container(
                                        expand=True,
                                        content=ft.Column(
                                            [preview_title_text, preview_subtitle_text],
                                            spacing=2,
                                            tight=True,
                                        ),
                                    ),
                                ],
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                expand=True,
                            ),
                            ft.OutlinedButton(
                                close_btn_label,
                                icon=ft.Icons.CLOSE_ROUNDED,
                                height=36,
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=8),
                                    padding=ft.Padding.symmetric(horizontal=12 if not is_mobile(page) else 8, vertical=0),
                                ),
                                on_click=close_preview,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=12,
                    ),
                ),
                ft.Container(
                    expand=True,
                    padding=ft.Padding.symmetric(
                        horizontal=16 if is_mobile(page) else 36,
                        vertical=20,
                    ),
                    content=ft.Column(
                        [
                            preview_body_column,
                        ],
                        expand=True,
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                ),
            ],
            spacing=0,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
    )

    def lesson_color(t: str):
        return LESSON_TYPE_COLORS.get(t, ft.Colors.GREY_500)

    def lesson_icon(t: str):
        return LESSON_TYPE_ICONS.get(t, ft.Icons.INSERT_DRIVE_FILE_ROUNDED)

    def lesson_badge(t: str):
        c = lesson_color(t)
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            border_radius=999,
            bgcolor=ft.Colors.with_opacity(0.12, c),
            content=ft.Row(
                [
                    ft.Icon(lesson_icon(t), size=12, color=c),
                    ft.Text(
                        LESSON_TYPES.get(t, t).upper(),
                        size=10,
                        weight=ft.FontWeight.BOLD,
                        color=c,
                    ),
                ],
                spacing=4,
                tight=True,
            ),
        )

    def show_dialog(title: str, message: str, success: bool):
        def close(e=None):
            dlg.open = False
            page.update()

        pw = getattr(page, "width", None) or 800
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(title, weight=ft.FontWeight.BOLD),
            content=ft.Container(width=min(480, max(260, pw - 48)), content=ft.Text(message)),
            actions=[
                ft.ElevatedButton(
                    "OK",
                    bgcolor=UI_ACCENT if success else ft.Colors.ERROR,
                    color=ft.Colors.ON_PRIMARY,
                    on_click=close,
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    # =========================================================
    # Editor open helper
    # =========================================================
    def open_editor(lesson: dict, module: dict):
        nonlocal active_lesson, active_module
        active_lesson = ensure_lesson_shape(lesson)
        active_module = module
        editor_visible[0] = True
        lesson_name = LESSON_TYPES.get(lesson.get("type", ""), "Lesson")
        editor_panel_header_label.value = f"Edit {lesson_name} Lesson"
        build_editor()
        if is_mobile(page):
            curriculum_container.visible = False
            curriculum_container.width = None
            curriculum_container.expand = False
            editor_panel.visible = True
            editor_panel.width = None
            editor_panel.expand = True
        else:
            curriculum_container.visible = True
            curriculum_container.width = 380
            curriculum_container.expand = False
            editor_panel.visible = True
            editor_panel.width = None
            editor_panel.expand = True
        refresh_curriculum()
        page.update()

    async def pick_and_upload_video(content: dict, status: ft.Text, url_input: ft.TextField, name_input: ft.TextField, e):
        e.control.disabled = True 
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
            content["video_url"] = ""
            url_input.value = ""
            status.update()
            url_input.update()
            e.control.disabled = False
            page.update()
            return

        status.value = f"Uploading {f.name}..."
        status.color = ft.Colors.ORANGE_700
        status.update()

        try:
            res = await upload_video_background(token, file_name=f.name, file_bytes=file_bytes)
            url = res.get("url", "")
            content["video_url"] = url
            url_input.value = content["video_url"]
            status.value = "Uploaded successfully."
            status.color = ft.Colors.GREEN_700
            status.update()
            url_input.update()
            e.control.disabled = True 
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
                e.control.disabled = False 
                page.update()
                return
        except Exception as ex:
            status.value = f"Upload failed: {ex}"
            status.color = ft.Colors.ERROR
            content["video_url"] = ""
            url_input.value = ""
            status.update()
            url_input.update()
            e.control.disabled = False
            page.update()

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
            e.control.disabled = False
            page.update()
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
            url = res.get("url", "")
            if asset_type == "audio":
                content["audio_path"] = url
            else:
                content["document_url"] = url
            status.value = "Uploaded successfully."
            status.color = ft.Colors.GREEN_700

            if not content.get("file_name"):
                content["file_name"] = f.name
                name_input.value = f.name
                name_input.update()

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

    def editor_section(title: str, icon, child: ft.Control, accent_color=None):
        color = accent_color or UI_ACCENT
        return ft.Container(
            padding=16,
            border_radius=14,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            bgcolor=ft.Colors.SURFACE,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Container(
                                padding=6,
                                border_radius=8,
                                bgcolor=ft.Colors.with_opacity(0.12, color),
                                content=ft.Icon(icon, size=16, color=color),
                            ),
                            ft.Text(title, weight=ft.FontWeight.BOLD, size=13),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    child,
                ],
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        )

    def block_card(title: str, child: ft.Control, tint: str = None):
        return editor_section(title, ft.Icons.EDIT_ROUNDED, child)

    def build_sleek_upload_card(title: str, subtitle: str, icon, status_text: ft.Text, on_pick_handler, accent_color=None):
        color = accent_color or UI_ACCENT
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=16, vertical=16),
            border_radius=12,
            border=ft.Border.all(1.5, ft.Colors.with_opacity(0.35, color)),
            bgcolor=ft.Colors.with_opacity(0.04, color),
            ink=True,
            on_click=on_pick_handler,
            content=ft.Row(
                [
                    ft.Container(
                        width=44, height=44,
                        border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.12, color),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(icon, size=22, color=color),
                    ),
                    ft.Container(
                        expand=True,
                        content=ft.Column(
                            [
                                ft.Text(title, size=13, weight=ft.FontWeight.BOLD),
                                ft.Text(subtitle, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                status_text,
                            ],
                            spacing=3,
                            tight=True,
                        ),
                    ),
                    ft.OutlinedButton(
                        "Browse",
                        icon=ft.Icons.FOLDER_OPEN_ROUNDED,
                        height=36,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=ft.Padding.symmetric(horizontal=12, vertical=0),
                        ),
                        on_click=on_pick_handler,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def file_name_block(content: dict):
        return ft.TextField(
            label="Display name (what learners see)",
            value=content.get("file_name", ""),
            border_radius=10,
            on_change=lambda e: content.__setitem__("file_name", e.control.value),
        )

    def notes_block(content: dict):
        return ft.TextField(
            label="Instructor Notes & Resources",
            value=content.get("accompanying_text", ""),
            multiline=True,
            min_lines=3,
            border_radius=10,
            on_change=lambda e: content.__setitem__("accompanying_text", e.control.value),
        )

    def video_block(content: dict):
        has_file = bool(content.get("video_url") or content.get("file_name"))
        status = ft.Text(
            f"Attached: {content.get('file_name', 'Video file')}" if has_file else "No video uploaded yet",
            size=11,
            color=ft.Colors.GREEN_700 if has_file else ft.Colors.ON_SURFACE_VARIANT,
            weight=ft.FontWeight.W_500 if has_file else None,
        )
        name_input = file_name_block(content)
        url_input = ft.TextField(
            label="External Video URL (YouTube, Vimeo, or direct MP4)",
            hint_text="https://youtube.com/watch?v=... or https://...",
            prefix_icon=ft.Icons.LINK_ROUNDED,
            value=content.get("video_url", ""),
            border_radius=10,
            on_change=lambda e: content.__setitem__("video_url", e.control.value.strip()),
        )

        upload_card = build_sleek_upload_card(
            title="Upload Video File",
            subtitle="Supported: MP4, WebM, MOV, AVI (up to 500MB)",
            icon=ft.Icons.CLOUD_UPLOAD_ROUNDED,
            status_text=status,
            on_pick_handler=lambda e: page.run_task(
                pick_and_upload_video,
                content,
                status,
                url_input,
                name_input,
                e,
            ),
            accent_color=LESSON_TYPE_COLORS.get("video"),
        )

        return ft.Column(
            [
                name_input,
                upload_card,
                ft.Row(
                    [
                        ft.Divider(expand=True, color=ft.Colors.OUTLINE_VARIANT),
                        ft.Text("OR STREAMING LINK", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Divider(expand=True, color=ft.Colors.OUTLINE_VARIANT),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                url_input,
            ],
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def audio_block(content: dict):
        has_file = bool(content.get("audio_path") or content.get("file_name"))
        status = ft.Text(
            f"Attached: {content.get('file_name', 'Audio file')}" if has_file else "No audio uploaded yet",
            size=11,
            color=ft.Colors.GREEN_700 if has_file else ft.Colors.ON_SURFACE_VARIANT,
            weight=ft.FontWeight.W_500 if has_file else None,
        )
        name_input = file_name_block(content)

        upload_card = build_sleek_upload_card(
            title="Upload Audio File",
            subtitle="Supported: MP3, WAV, AAC, M4A, OGG",
            icon=ft.Icons.AUDIOTRACK_ROUNDED,
            status_text=status,
            on_pick_handler=lambda e: page.run_task(
                pick_and_upload_asset,
                "audio",
                content,
                status,
                name_input,
                None,
                ft.FilePickerFileType.AUDIO,
                e,
            ),
            accent_color=LESSON_TYPE_COLORS.get("audio"),
        )

        return ft.Column(
            [
                name_input,
                upload_card,
            ],
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def document_block(content: dict):
        has_file = bool(content.get("document_url") or content.get("file_name"))
        status = ft.Text(
            f"Attached: {content.get('file_name', 'Document')}" if has_file else "No document uploaded yet",
            size=11,
            color=ft.Colors.GREEN_700 if has_file else ft.Colors.ON_SURFACE_VARIANT,
            weight=ft.FontWeight.W_500 if has_file else None,
        )
        name_input = file_name_block(content)

        upload_card = build_sleek_upload_card(
            title="Upload Document or Slides",
            subtitle="Supported: PDF, DOCX, DOC, PPTX, TXT",
            icon=ft.Icons.DESCRIPTION_ROUNDED,
            status_text=status,
            on_pick_handler=lambda e: page.run_task(
                pick_and_upload_asset,
                "document",
                content,
                status,
                name_input,
                ["pdf", "doc", "docx", "ppt", "pptx", "txt"],
                ft.FilePickerFileType.CUSTOM,
                e,
            ),
            accent_color=LESSON_TYPE_COLORS.get("document"),
        )

        return ft.Column(
            [
                name_input,
                upload_card,
            ],
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def text_block(content: dict):
        text_val = content.get("text", "")
        status_text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        selection_state = {"start": len(text_val), "end": len(text_val), "text": ""}

        def on_selection(e):
            sel = getattr(e, "selection", None)
            if sel is not None:
                b = getattr(sel, "base_offset", 0)
                ext = getattr(sel, "extent_offset", 0)
                selection_state["start"] = min(b, ext)
                selection_state["end"] = max(b, ext)
            selection_state["text"] = getattr(e, "selected_text", "") or ""

        def on_text_changed(e):
            val = e.control.value or ""
            content["text"] = val
            selection_state["start"] = len(val)
            selection_state["end"] = len(val)
            update_preview_content()

        text_input = ft.TextField(
            label="Lesson Text (Markdown)",
            value=text_val,
            multiline=True,
            min_lines=12,
            border_radius=10,
            on_change=on_text_changed,
            on_selection_change=on_selection,
        )

        markdown_display = ft.Markdown(
            value=text_val or "*No content written yet. Switch to Edit mode to write markdown.*",
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
            md_style_sheet=ft.MarkdownStyleSheet(
                text_alignment=ft.TextAlign.START,
                p_text_style=ft.TextStyle(size=15, weight=ft.FontWeight.W_400, color=ft.Colors.ON_SURFACE, height=1.6),
                h1_text_style=ft.TextStyle(size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                h2_text_style=ft.TextStyle(size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                h3_text_style=ft.TextStyle(size=16, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                code_text_style=ft.TextStyle(
                    size=13.5,
                    font_family="Roboto Mono, monospace",
                    color=ft.Colors.ON_SURFACE,
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                ),
                blockquote_decoration=ft.BoxDecoration(
                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                    border=ft.Border.only(left=ft.BorderSide(3.5, ft.Colors.AMBER_500)),
                    border_radius=ft.BorderRadius.all(6),
                ),
                blockquote_text_style=ft.TextStyle(
                    size=14.5,
                    italic=True,
                    color=ft.Colors.ON_SURFACE,
                    height=1.5,
                ),
                blockquote_padding=ft.Padding.symmetric(horizontal=16, vertical=10),
            ),
        )

        preview_box = ft.Container(
            visible=False,
            padding=24,
            border_radius=12,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            content=markdown_display,
        )

        def update_preview_content():
            markdown_display.value = text_input.value or "*No content written yet. Switch to Edit mode to write markdown.*"

        def set_mode(is_preview: bool):
            text_input.visible = not is_preview
            preview_box.visible = is_preview
            update_preview_content()
            edit_tab.bgcolor = None if is_preview else ft.Colors.with_opacity(0.12, UI_ACCENT)
            edit_tab.color = ft.Colors.ON_SURFACE if is_preview else UI_ACCENT
            prev_tab.bgcolor = ft.Colors.with_opacity(0.12, UI_ACCENT) if is_preview else None
            prev_tab.color = UI_ACCENT if is_preview else ft.Colors.ON_SURFACE
            page.update()

        edit_tab = ft.TextButton("Edit", icon=ft.Icons.EDIT_NOTE_ROUNDED, on_click=lambda e: set_mode(False))
        prev_tab = ft.TextButton("Live Preview", icon=ft.Icons.PREVIEW_ROUNDED, on_click=lambda e: set_mode(True))
        edit_tab.bgcolor = ft.Colors.with_opacity(0.12, UI_ACCENT)
        edit_tab.color = UI_ACCENT

        def insert_syntax(prefix, suffix="", label="formatting"):
            curr = text_input.value or ""
            s = selection_state.get("start", 0)
            end = selection_state.get("end", 0)
            sel = selection_state.get("text", "")

            # If user has an active text selection within bounds
            if 0 <= s < end <= len(curr) and sel:
                target_text = curr[s:end]
                replacement = f"{prefix}{target_text}{suffix}"
                new_val = curr[:s] + replacement + curr[end:]
                feedback = f"Formatted '{target_text[:15]}' with {label}"
            elif 0 <= s <= len(curr) and s > 0:
                replacement = f"{prefix}text{suffix}"
                new_val = curr[:s] + replacement + curr[s:]
                feedback = f"Inserted {label} at cursor"
            else:
                sep = "\n" if curr and not curr.endswith("\n") else ""
                new_val = curr + f"{sep}{prefix}text{suffix}\n"
                feedback = f"Added {label}"

            text_input.value = new_val
            content["text"] = new_val
            update_preview_content()
            status_text.value = feedback
            status_text.color = ft.Colors.GREEN_600
            try:
                text_input.update()
                status_text.update()
                markdown_display.update()
            except Exception:
                page.update()

        async def upload_and_insert_image(e):
            e.control.disabled = True
            status_text.value = "Selecting image..."
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
                    markdown_image = f"\n![{f.name}]({img_url})\n"
                    current_text = text_input.value or ""
                    new_text = current_text + markdown_image
                    text_input.value = new_text
                    content["text"] = new_text
                    update_preview_content()
                    status_text.value = "Image inserted!"
                    status_text.color = ft.Colors.GREEN_700
            except Exception as ex:
                status_text.value = f"Error: {ex}"
                status_text.color = ft.Colors.ERROR

            e.control.disabled = False
            page.update()

        formatting_icons = [
            ft.IconButton(ft.Icons.TITLE_ROUNDED, icon_size=17, tooltip="Heading (T)", on_click=lambda e: insert_syntax("# ", "", "heading")),
            ft.IconButton(ft.Icons.FORMAT_BOLD_ROUNDED, icon_size=17, tooltip="Bold (B)", on_click=lambda e: insert_syntax("**", "**", "bold")),
            ft.IconButton(ft.Icons.FORMAT_ITALIC_ROUNDED, icon_size=17, tooltip="Italic (I)", on_click=lambda e: insert_syntax("*", "*", "italic")),
            ft.IconButton(ft.Icons.FORMAT_UNDERLINED_ROUNDED, icon_size=17, tooltip="Underline (U)", on_click=lambda e: insert_syntax("<u>", "</u>", "underline")),
            ft.IconButton(ft.Icons.FORMAT_LIST_NUMBERED_ROUNDED, icon_size=17, tooltip="Numbered List (n)", on_click=lambda e: insert_syntax("1. ", "", "numbered list")),
            ft.IconButton(ft.Icons.FORMAT_LIST_BULLETED_ROUNDED, icon_size=17, tooltip="Bullet List", on_click=lambda e: insert_syntax("- ", "", "bullet list")),
            ft.IconButton(ft.Icons.CODE_ROUNDED, icon_size=17, tooltip="Code", on_click=lambda e: insert_syntax("`", "`", "code")),
            ft.IconButton(ft.Icons.FORMAT_QUOTE_ROUNDED, icon_size=17, tooltip="Quote", on_click=lambda e: insert_syntax("> ", "", "quote")),
            ft.IconButton(ft.Icons.LINK_ROUNDED, icon_size=17, tooltip="Insert Link", on_click=lambda e: insert_syntax("[", "](https://)", "link")),
            ft.IconButton(ft.Icons.ADD_PHOTO_ALTERNATE_OUTLINED, icon_size=17, icon_color=UI_ACCENT, tooltip="Insert Image", on_click=lambda e: page.run_task(upload_and_insert_image, e)),
        ]

        if is_mobile(page):
            formatting_bar = ft.Column(
                [
                    ft.Row([edit_tab, prev_tab], spacing=4, tight=True),
                    ft.Row(
                        formatting_icons,
                        spacing=2,
                        wrap=True,
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.START,
            )
        else:
            formatting_bar = ft.Row(
                [
                    ft.Row([edit_tab, prev_tab], spacing=4, tight=True),
                    ft.Row(
                        formatting_icons,
                        spacing=2,
                        tight=True,
                        wrap=True,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                wrap=True,
            )

        return ft.Column(
            controls=[
                formatting_bar,
                status_text,
                text_input,
                preview_box,
            ],
            spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def cards_block(content: dict):
        cards = content.setdefault("cards", [])
        cards_col = ft.Column(spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

        def rebuild():
            cards_col.controls.clear()
            for idx, item in enumerate(cards):
                def del_card(i):
                    def handler(e):
                        cards.pop(i)
                        build_editor()
                        page.update()
                    return handler

                def on_change(i):
                    def handler(e):
                        if isinstance(cards[i], dict):
                            cards[i]["front"] = e.control.value
                        else:
                            cards[i] = e.control.value
                    return handler

                card_val = item.get("front", "") if isinstance(item, dict) else str(item)

                cards_col.controls.append(
                    ft.Container(
                        padding=12,
                        border_radius=10,
                        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                        bgcolor=ft.Colors.SURFACE,
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Container(
                                            padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                                            border_radius=6,
                                            bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.PURPLE_500),
                                            content=ft.Text(f"Card {idx + 1} of {len(cards)}", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.PURPLE_500),
                                        ),
                                        ft.IconButton(
                                            ft.Icons.DELETE_OUTLINE_ROUNDED,
                                            icon_size=18,
                                            icon_color=ft.Colors.RED_500,
                                            tooltip="Delete card",
                                            on_click=del_card(idx),
                                        ),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                                ft.TextField(
                                    label="Card Content (Front prompt / note)",
                                    value=card_val,
                                    multiline=True,
                                    min_lines=2,
                                    border_radius=8,
                                    on_change=on_change(idx),
                                ),
                            ],
                            spacing=8,
                            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
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
                ft.TextButton("Add Flashcard +", icon=ft.Icons.ADD_ROUNDED, on_click=add_card),
            ],
            spacing=10,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def scenario_block(content: dict):
        content.setdefault("scenario", "")
        choices = content.setdefault("choices", [])
        
        scenario_input = ft.TextField(
            label="The Scenario (Prompt text for learners)",
            value=content["scenario"],
            multiline=True,
            min_lines=3,
            border_radius=10,
            on_change=lambda e: content.__setitem__("scenario", e.control.value),
        )

        choices_col = ft.Column(spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

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
                        padding=14,
                        border_radius=10,
                        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                        bgcolor=ft.Colors.SURFACE,
                        content=ft.Column([
                            ft.Row([
                                ft.Container(
                                    padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                                    border_radius=6,
                                    bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.TEAL_600),
                                    content=ft.Text(f"Choice {idx + 1}", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_600),
                                ),
                                ft.IconButton(ft.Icons.DELETE_OUTLINE_ROUNDED, icon_size=18, icon_color=ft.Colors.RED_500, on_click=del_choice(idx))
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.TextField(label="User Option (e.g. 'Restart the application server')", value=ch["text"], border_radius=8, on_change=text_change(idx)),
                            ft.TextField(label="Consequence & Explanation (Markdown supported)", value=ch["consequence"], multiline=True, min_lines=2, border_radius=8, on_change=cons_change(idx))
                        ], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
                    )
                )

        def add_choice(e):
            choices.append({"text": "", "consequence": ""})
            build_editor()
            page.update()

        rebuild()
        return ft.Column([
            scenario_input,
            ft.Text("Branching Choices & Consequences", weight=ft.FontWeight.BOLD, size=13),
            choices_col,
            ft.TextButton("Add Choice", icon=ft.Icons.ADD_ROUNDED, on_click=add_choice)
        ], spacing=14, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    def assessment_block(content: dict):
        questions = content.setdefault("questions", [])
        q_col = ft.Column(spacing=14, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

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

                opts_col = ft.Column(spacing=8, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

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
                                    label="Correct Answer",
                                    value=opt["is_correct"],
                                    on_change=opt_correct(q_idx, o_idx),
                                ),
                                ft.TextField(
                                    value=opt["text"],
                                    border_radius=8,
                                    on_change=opt_text(q_idx, o_idx),
                                ),
                                ft.Row(
                                    [
                                        ft.IconButton(
                                            ft.Icons.DELETE_OUTLINE_ROUNDED,
                                            icon_size=18,
                                            icon_color=ft.Colors.RED_500,
                                            on_click=del_opt(q_idx, o_idx),
                                        )
                                    ],
                                    alignment=ft.MainAxisAlignment.END,
                                ),
                            ],
                            spacing=8,
                            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                        )
                    else:
                        option_row = ft.Row(
                            [
                                ft.Checkbox(
                                    value=opt["is_correct"],
                                    tooltip="Mark as correct answer",
                                    on_change=opt_correct(q_idx, o_idx),
                                ),
                                ft.TextField(
                                    value=opt["text"],
                                    hint_text="Option text",
                                    expand=True,
                                    border_radius=8,
                                    on_change=opt_text(q_idx, o_idx),
                                ),
                                ft.IconButton(
                                    ft.Icons.DELETE_OUTLINE_ROUNDED,
                                    icon_size=18,
                                    icon_color=ft.Colors.RED_500,
                                    tooltip="Delete option",
                                    on_click=del_opt(q_idx, o_idx),
                                ),
                            ],
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
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
                        padding=14,
                        border_radius=12,
                        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                        bgcolor=ft.Colors.SURFACE,
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Container(
                                            padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                                            border_radius=6,
                                            bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.ORANGE_500),
                                            content=ft.Text(f"Question {q_idx + 1}", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.ORANGE_500),
                                        ),
                                        ft.IconButton(
                                            ft.Icons.DELETE_OUTLINE_ROUNDED,
                                            icon_size=18,
                                            icon_color=ft.Colors.RED_500,
                                            tooltip="Delete question",
                                            on_click=del_q(q_idx),
                                        ),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                                ft.TextField(
                                    label="Question Prompt",
                                    value=q["text"],
                                    multiline=True,
                                    min_lines=2,
                                    border_radius=8,
                                    on_change=q_change(q_idx),
                                ),
                                ft.Text("Answer Options (check the box next to correct answer)", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                opts_col,
                                ft.TextButton(
                                    "Add Option",
                                    icon=ft.Icons.ADD_ROUNDED,
                                    on_click=add_opt(q_idx),
                                ),
                            ],
                            spacing=10,
                            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
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
                ft.TextButton("Add Question", icon=ft.Icons.ADD_ROUNDED, on_click=add_q),
            ],
            spacing=10,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def stepper_block(content: dict):
        steps = content.setdefault("steps", [])
        title_input = ft.TextField(
            label="Walkthrough Title / Summary (Optional)",
            value=content.get("title", ""),
            border_radius=8,
            on_change=lambda e: content.__setitem__("title", e.control.value),
        )
        intro_input = ft.TextField(
            label="Introduction / Overview (Optional)",
            value=content.get("intro", ""),
            multiline=True,
            min_lines=2,
            border_radius=8,
            on_change=lambda e: content.__setitem__("intro", e.control.value),
        )

        steps_col = ft.Column(spacing=12, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

        def rebuild():
            steps_col.controls.clear()
            for idx, s in enumerate(steps):
                s.setdefault("headline", "")
                s.setdefault("tag", f"Step {idx + 1}")
                s.setdefault("content", "")
                s.setdefault("takeaway", "")

                def del_step(i):
                    def handler(e):
                        steps.pop(i)
                        build_editor()
                        page.update()
                    return handler

                def move_step(i, delta):
                    def handler(e):
                        target = i + delta
                        if 0 <= target < len(steps):
                            steps[i], steps[target] = steps[target], steps[i]
                            build_editor()
                            page.update()
                    return handler

                def s_change(i, field):
                    def handler(e):
                        steps[i][field] = e.control.value
                    return handler

                steps_col.controls.append(
                    ft.Container(
                        padding=14,
                        border_radius=10,
                        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                        bgcolor=ft.Colors.SURFACE,
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Container(
                                            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                            border_radius=6,
                                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.CYAN_600),
                                            content=ft.Text(f"Phase / Step {idx + 1}", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_600),
                                        ),
                                        ft.Row(
                                            [
                                                ft.IconButton(
                                                    ft.Icons.ARROW_UPWARD_ROUNDED,
                                                    icon_size=18,
                                                    tooltip="Move Up",
                                                    disabled=(idx == 0),
                                                    on_click=move_step(idx, -1),
                                                ),
                                                ft.IconButton(
                                                    ft.Icons.ARROW_DOWNWARD_ROUNDED,
                                                    icon_size=18,
                                                    tooltip="Move Down",
                                                    disabled=(idx == len(steps) - 1),
                                                    on_click=move_step(idx, 1),
                                                ),
                                                ft.IconButton(
                                                    ft.Icons.DELETE_OUTLINE_ROUNDED,
                                                    icon_size=18,
                                                    icon_color=ft.Colors.RED_500,
                                                    tooltip="Delete Step",
                                                    on_click=del_step(idx),
                                                ),
                                            ],
                                            spacing=2,
                                        ),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                                ft.Row(
                                    [
                                        ft.TextField(
                                            label="Step Tag (e.g. 'Setup', 'Phase 1')",
                                            value=s["tag"],
                                            border_radius=8,
                                            expand=1,
                                            on_change=s_change(idx, "tag"),
                                        ),
                                        ft.TextField(
                                            label="Step Headline",
                                            value=s["headline"],
                                            border_radius=8,
                                            expand=2,
                                            on_change=s_change(idx, "headline"),
                                        ),
                                    ],
                                    spacing=10,
                                ),
                                ft.TextField(
                                    label="Step Explanation (Markdown supported)",
                                    value=s["content"],
                                    multiline=True,
                                    min_lines=3,
                                    border_radius=8,
                                    on_change=s_change(idx, "content"),
                                ),
                                ft.TextField(
                                    label="Key Takeaway / Highlight Box (Optional)",
                                    value=s["takeaway"],
                                    multiline=True,
                                    min_lines=1,
                                    border_radius=8,
                                    on_change=s_change(idx, "takeaway"),
                                ),
                            ],
                            spacing=10,
                            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                        ),
                    )
                )

        def add_step(e):
            steps.append({
                "headline": "",
                "tag": f"Step {len(steps) + 1}",
                "content": "",
                "takeaway": "",
            })
            build_editor()
            page.update()

        rebuild()
        return ft.Column(
            [
                title_input,
                intro_input,
                ft.Text("Sequential Steps", weight=ft.FontWeight.BOLD, size=13),
                steps_col,
                ft.TextButton("Add Step", icon=ft.Icons.ADD_ROUNDED, on_click=add_step),
            ],
            spacing=14,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def sequencer_block(content: dict):
        content.setdefault("prompt", "")
        items = content.setdefault("items", [])

        prompt_input = ft.TextField(
            label="Challenge Prompt / Instructions (e.g. 'Arrange the sequence of events:')",
            value=content["prompt"],
            multiline=True,
            min_lines=2,
            border_radius=8,
            on_change=lambda e: content.__setitem__("prompt", e.control.value),
        )

        items_col = ft.Column(spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

        def rebuild():
            items_col.controls.clear()
            for idx, it in enumerate(items):
                it.setdefault("id", f"item_{idx + 1}")
                it.setdefault("label", "")
                it["correct_order"] = idx
                it.setdefault("explanation", "")

                def del_item(i):
                    def handler(e):
                        items.pop(i)
                        build_editor()
                        page.update()
                    return handler

                def move_item(i, delta):
                    def handler(e):
                        target = i + delta
                        if 0 <= target < len(items):
                            items[i], items[target] = items[target], items[i]
                            build_editor()
                            page.update()
                    return handler

                def item_change(i, field):
                    def handler(e):
                        items[i][field] = e.control.value
                    return handler

                items_col.controls.append(
                    ft.Container(
                        padding=14,
                        border_radius=10,
                        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                        bgcolor=ft.Colors.SURFACE,
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Row(
                                            [
                                                ft.Container(
                                                    width=24,
                                                    height=24,
                                                    border_radius=999,
                                                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_600),
                                                    alignment=ft.Alignment.CENTER,
                                                    content=ft.Text(f"{idx + 1}", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_600),
                                                ),
                                                ft.Text(f"Target Position #{idx + 1}", size=12, weight=ft.FontWeight.BOLD),
                                            ],
                                            spacing=8,
                                        ),
                                        ft.Row(
                                            [
                                                ft.IconButton(
                                                    ft.Icons.ARROW_UPWARD_ROUNDED,
                                                    icon_size=18,
                                                    tooltip="Move Up",
                                                    disabled=(idx == 0),
                                                    on_click=move_item(idx, -1),
                                                ),
                                                ft.IconButton(
                                                    ft.Icons.ARROW_DOWNWARD_ROUNDED,
                                                    icon_size=18,
                                                    tooltip="Move Down",
                                                    disabled=(idx == len(items) - 1),
                                                    on_click=move_item(idx, 1),
                                                ),
                                                ft.IconButton(
                                                    ft.Icons.DELETE_OUTLINE_ROUNDED,
                                                    icon_size=18,
                                                    icon_color=ft.Colors.RED_500,
                                                    tooltip="Delete Item",
                                                    on_click=del_item(idx),
                                                ),
                                            ],
                                            spacing=2,
                                        ),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                                ft.TextField(
                                    label="Step Description (What learner sees on the card)",
                                    value=it["label"],
                                    border_radius=8,
                                    on_change=item_change(idx, "label"),
                                ),
                                ft.TextField(
                                    label="Pedagogical Explanation / Takeaway (Shown upon solving)",
                                    value=it["explanation"],
                                    multiline=True,
                                    min_lines=1,
                                    border_radius=8,
                                    on_change=item_change(idx, "explanation"),
                                ),
                            ],
                            spacing=10,
                            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                        ),
                    )
                )

        def add_item(e):
            new_idx = len(items)
            items.append({
                "id": f"item_{new_idx + 1}_{random.randint(100, 999)}",
                "label": "",
                "correct_order": new_idx,
                "explanation": "",
            })
            build_editor()
            page.update()

        rebuild()
        return ft.Column(
            [
                prompt_input,
                ft.Text("Sequence Items (Ordered from first to last)", weight=ft.FontWeight.BOLD, size=13),
                ft.Text("Specify items in their correct chronological or logical order. Learners will see them shuffled.", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                items_col,
                ft.TextButton("Add Sequence Item", icon=ft.Icons.ADD_ROUNDED, on_click=add_item),
            ],
            spacing=14,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def cloze_block(content: dict):
        content.setdefault("text", "")
        distractors = content.setdefault("distractors", [])
        content.setdefault("explanation", "")

        detected_chips_row = ft.Row(wrap=True, spacing=6)

        def update_detected_chips():
            detected_chips_row.controls.clear()
            _, blanks = parse_cloze_text(content.get("text", ""))
            if not blanks:
                detected_chips_row.controls.append(
                    ft.Text("No blanks detected yet. Use [[answer]] or [[answer|hint]].", size=12, color=ft.Colors.AMBER_500)
                )
            else:
                for b in blanks:
                    hint_part = f" ({b['hint']})" if b['hint'] else ""
                    detected_chips_row.controls.append(
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                            border_radius=6,
                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.GREEN_600),
                            content=ft.Text(f"#{b['index']+1}: {b['answer']}{hint_part}", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_600),
                        )
                    )

        def on_text_change(e):
            content["text"] = e.control.value
            update_detected_chips()
            page.update()

        text_input = ft.TextField(
            label="Cloze Passage (with [[blank]] or [[blank|hint]])",
            value=content["text"],
            multiline=True,
            min_lines=4,
            border_radius=8,
            helper="Example: 'The [[mitochondria|organelle]] is the [[powerhouse]] of the cell.'",
            on_change=on_text_change,
        )

        distractors_input = ft.TextField(
            label="Word Bank Distractors (comma-separated decoy words)",
            value=", ".join(distractors),
            border_radius=8,
            helper="Optional decoys that appear in the word bank to challenge learners.",
            on_change=lambda e: content.__setitem__("distractors", [w.strip() for w in e.control.value.split(",") if w.strip()]),
        )

        explanation_input = ft.TextField(
            label="Pedagogical Explanation / Key Takeaways (Shown after solving)",
            value=content.get("explanation", ""),
            multiline=True,
            min_lines=2,
            border_radius=8,
            on_change=lambda e: content.__setitem__("explanation", e.control.value),
        )

        update_detected_chips()

        return ft.Column(
            [
                text_input,
                ft.Text("Detected Interactive Blanks:", size=12, weight=ft.FontWeight.BOLD),
                detected_chips_row,
                distractors_input,
                explanation_input,
            ],
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def code_lab_block(content: dict):
        content.setdefault("instructions", "")
        content.setdefault("starter_code", "")
        content.setdefault("solution_code", "")
        content.setdefault("setup_sql", "")
        test_cases = content.setdefault("test_cases", [])

        # Supported languages
        available_languages = [
            ("python", "Python 3.12 (Offline Sandbox)", ft.Icons.TERMINAL_ROUNDED, ft.Colors.BLUE_600),
            ("sql", "SQLite 3 (Offline In-Memory)", ft.Icons.STORAGE_ROUNDED, ft.Colors.TEAL_600),
            ("html", "HTML5 / Web (Live Sandbox Preview)", ft.Icons.HTML_ROUNDED, ft.Colors.DEEP_ORANGE_600),
            ("cpp", "C++ (GCC 9.2 Container)", ft.Icons.CODE_ROUNDED, ft.Colors.CYAN_700),
            ("javascript", "JavaScript (Node.js Container)", ft.Icons.JAVASCRIPT_ROUNDED, ft.Colors.AMBER_700),
            ("typescript", "TypeScript (Container)", ft.Icons.DATA_OBJECT_ROUNDED, ft.Colors.LIGHT_BLUE_700),
            ("java", "Java (OpenJDK Container)", ft.Icons.COFFEE_ROUNDED, ft.Colors.ORANGE_700),
            ("c", "C (GCC 9.2 Container)", ft.Icons.MEMORY_ROUNDED, ft.Colors.BLUE_GREY_700),
        ]

        curr_lang = str(content.get("language", "python")).lower().strip()
        matched_lang = next((l[0] for l in available_languages if l[0] == curr_lang or (l[0] == "sql" and "sql" in curr_lang) or (l[0] == "cpp" and "c++" in curr_lang)), "python")
        content["language"] = matched_lang
        is_sql = (matched_lang == "sql")

        def on_lang_change(e):
            content["language"] = e.control.value
            build_editor()
            page.update()

        lang_dropdown = ft.Dropdown(
            label="Programming Language / Runtime Environment",
            value=matched_lang,
            options=[
                ft.dropdown.Option(key=key, text=label)
                for key, label, _, _ in available_languages
            ],
            border_radius=8,
            border_color=ft.Colors.with_opacity(0.20, ft.Colors.ON_SURFACE),
            focused_border_color=ft.Colors.PRIMARY,
            menu_height=280,
            menu_style=ft.MenuStyle(
                bgcolor=ft.Colors.SURFACE,
                elevation=8,
                shape=ft.RoundedRectangleBorder(radius=10),
                side=ft.BorderSide(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
            ),
            on_select=on_lang_change,
        )

        if is_sql:
            lang_banner = ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.TEAL_400),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.TEAL_400)),
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.STORAGE_ROUNDED, color=ft.Colors.TEAL_400, size=20),
                        ft.Text(
                            "SQLite Mode: Learners run queries locally against an ephemeral in-memory database. Works 100% offline.",
                            size=12,
                            weight=ft.FontWeight.W_500,
                            color=ft.Colors.ON_SURFACE,
                            expand=True,
                        ),
                    ],
                    spacing=10,
                ),
            )
            setup_sql_field = ft.TextField(
                label="Database Schema & Seed Data (Runs before each query)",
                value=content.get("setup_sql", ""),
                multiline=True,
                min_lines=4,
                border_radius=8,
                text_style=ft.TextStyle(font_family="monospace", size=12),
                helper="e.g. CREATE TABLE users (id INT, name TEXT); INSERT INTO users VALUES (1, 'Alice');",
                on_change=lambda e: content.__setitem__("setup_sql", e.control.value),
            )
        elif matched_lang == "python":
            lang_banner = ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.BLUE_400),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.BLUE_400)),
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.TERMINAL_ROUNDED, color=ft.Colors.BLUE_400, size=20),
                        ft.Text(
                            "Python Mode: Safe sandboxed execution with captured stdout and support for standard input via input(). Works 100% offline.",
                            size=12,
                            weight=ft.FontWeight.W_500,
                            color=ft.Colors.ON_SURFACE,
                            expand=True,
                        ),
                    ],
                    spacing=10,
                ),
            )
            setup_sql_field = None
        else:
            lang_label = next((l[1] for l in available_languages if l[0] == matched_lang), matched_lang.upper())
            lang_banner = ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.CYAN_400),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.CYAN_400)),
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.CLOUD_DONE_ROUNDED, color=ft.Colors.CYAN_400, size=20),
                        ft.Text(
                            f"{lang_label}: Compiles and executes student code in a sandboxed container. When offline, learners can view test cases and solutions.",
                            size=12,
                            weight=ft.FontWeight.W_500,
                            color=ft.Colors.ON_SURFACE,
                            expand=True,
                        ),
                    ],
                    spacing=10,
                ),
            )
            setup_sql_field = None

        instructions_input = ft.TextField(
            label="SQL Challenge Instructions" if is_sql else "Problem Description & Instructions (Markdown supported)",
            value=content["instructions"],
            multiline=True,
            min_lines=3,
            border_radius=8,
            on_change=lambda e: content.__setitem__("instructions", e.control.value),
        )

        starter_code_input = ft.TextField(
            label="Starter SQL Query" if is_sql else "Starter Code (Initial code in student's editor)",
            value=content["starter_code"],
            multiline=True,
            min_lines=5,
            border_radius=8,
            text_style=ft.TextStyle(font_family="monospace", size=13),
            helper="e.g. SELECT * FROM users;" if is_sql else "Initial template code for the student to build upon",
            on_change=lambda e: content.__setitem__("starter_code", e.control.value),
        )

        solution_code_input = ft.TextField(
            label="Reference SQL Solution" if is_sql else "Reference Solution (Author's reference code)",
            value=content.get("solution_code", ""),
            multiline=True,
            min_lines=3,
            border_radius=8,
            text_style=ft.TextStyle(font_family="monospace", size=13),
            on_change=lambda e: content.__setitem__("solution_code", e.control.value),
        )

        test_cases_col = ft.Column(spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

        def rebuild_test_cases():
            test_cases_col.controls.clear()
            for idx, tc in enumerate(test_cases):
                tc.setdefault("description", f"Test Case {idx + 1}")
                tc.setdefault("input", "")
                tc.setdefault("expected_output", "")

                def del_tc(i):
                    def handler(e):
                        test_cases.pop(i)
                        rebuild_test_cases()
                        page.update()
                    return handler

                def tc_change(i, field):
                    def handler(e):
                        test_cases[i][field] = e.control.value
                    return handler

                test_cases_col.controls.append(
                    ft.Container(
                        padding=12,
                        border_radius=8,
                        bgcolor=ft.Colors.SURFACE,
                        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Text(f"Test Case #{idx + 1}", weight=ft.FontWeight.BOLD, size=12),
                                        ft.IconButton(ft.Icons.DELETE_OUTLINE_ROUNDED, icon_size=18, icon_color=ft.Colors.RED_500, on_click=del_tc(idx)),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                                ft.TextField(label="Test Description", value=tc["description"], border_radius=6, on_change=tc_change(idx, "description")),
                                ft.TextField(label="Test Stdin Input (Optional)", value=tc["input"], border_radius=6, visible=(not is_sql), on_change=tc_change(idx, "input")),
                                ft.TextField(label="Expected Output / Substring", value=tc["expected_output"], border_radius=6, on_change=tc_change(idx, "expected_output")),
                            ],
                            spacing=8,
                        ),
                    )
                )

        def add_tc(e):
            test_cases.append({"description": f"Test Case {len(test_cases) + 1}", "input": "", "expected_output": ""})
            rebuild_test_cases()
            page.update()

        rebuild_test_cases()

        controls = [
            lang_dropdown,
            lang_banner,
        ]
        if setup_sql_field:
            controls.append(setup_sql_field)
        controls.extend([
            instructions_input,
            starter_code_input,
            solution_code_input,
            ft.Row(
                [
                    ft.Text("Verification Test Cases", weight=ft.FontWeight.BOLD, size=13),
                    ft.TextButton("Add Test Case", icon=ft.Icons.ADD_ROUNDED, on_click=add_tc),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            test_cases_col,
        ])

        return ft.Column(
            controls,
            spacing=14,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
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
        lc = lesson_color(t)
        li = lesson_icon(t)

        mod_title = active_module.get("title", "Module") if active_module else "Module"
        editor_content.controls.append(
            ft.Row(
                [
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                        border_radius=999,
                        bgcolor=ft.Colors.with_opacity(0.12, lc),
                        content=ft.Row(
                            [
                                ft.Icon(li, size=14, color=lc),
                                ft.Text(
                                    LESSON_TYPES.get(t, t),
                                    size=12,
                                    weight=ft.FontWeight.BOLD,
                                    color=lc,
                                ),
                            ],
                            spacing=6,
                            tight=True,
                        ),
                    ),
                    ft.Text(f"in {mod_title}", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )

        editor_content.controls.append(
            editor_section(
                "Lesson Title",
                ft.Icons.TITLE_ROUNDED,
                ft.TextField(
                    label="Title",
                    value=lesson["title"],
                    border_radius=10,
                    text_size=16,
                    text_style=ft.TextStyle(weight=ft.FontWeight.W_600),
                    on_change=lambda e: lesson.__setitem__("title", e.control.value),
                ),
            )
        )

        if t == "video":
            editor_content.controls.append(
                editor_section("Video Lecture", ft.Icons.PLAY_CIRCLE_FILL_ROUNDED, video_block(content), accent_color=lc)
            )
            if "accompanying_text" in content:
                editor_content.controls.append(
                    editor_section("Instructor Notes", ft.Icons.NOTES_ROUNDED, notes_block(content))
                )
        elif t == "audio":
            editor_content.controls.append(
                editor_section("Audio Lecture", ft.Icons.AUDIOTRACK_ROUNDED, audio_block(content), accent_color=lc)
            )
            if "accompanying_text" in content:
                editor_content.controls.append(
                    editor_section("Instructor Notes", ft.Icons.NOTES_ROUNDED, notes_block(content))
                )
        elif t == "document":
            editor_content.controls.append(
                editor_section("Document & Slides", ft.Icons.DESCRIPTION_ROUNDED, document_block(content), accent_color=lc)
            )
            if "accompanying_text" in content:
                editor_content.controls.append(
                    editor_section("Instructor Notes", ft.Icons.NOTES_ROUNDED, notes_block(content))
                )
        elif t == "text":
            editor_content.controls.append(
                editor_section("Markdown Article", ft.Icons.NOTES_ROUNDED, text_block(content), accent_color=lc)
            )
        elif t == "cards":
            editor_content.controls.append(
                editor_section("Flashcards Deck", ft.Icons.VIEW_CAROUSEL_ROUNDED, cards_block(content), accent_color=lc)
            )
        elif t == "assessment":
            editor_content.controls.append(
                editor_section("Assessment & Quiz", ft.Icons.QUIZ_ROUNDED, assessment_block(content), accent_color=lc)
            )
        elif t == "scenario":
            editor_content.controls.append(
                editor_section("Decision Matrix", ft.Icons.CALL_SPLIT_ROUNDED, scenario_block(content), accent_color=lc)
            )
        elif t == "stepper":
            editor_content.controls.append(
                editor_section("Walkthrough Steps", ft.Icons.LINEAR_SCALE_ROUNDED, stepper_block(content), accent_color=lc)
            )
        elif t == "sequencer":
            editor_content.controls.append(
                editor_section("Order Challenge", ft.Icons.REORDER_ROUNDED, sequencer_block(content), accent_color=lc)
            )
        elif t == "cloze":
            editor_content.controls.append(
                editor_section("Fill in the Blanks", ft.Icons.EDIT_NOTE_ROUNDED, cloze_block(content), accent_color=lc)
            )
        elif t == "code_lab":
            editor_content.controls.append(
                editor_section("Code Lab", ft.Icons.CODE_ROUNDED, code_lab_block(content), accent_color=lc)
            )

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

        mod_lessons = active_module.get("lessons", []) if active_module else []
        if len(mod_lessons) > 1 and lesson in mod_lessons:
            curr_idx = mod_lessons.index(lesson)
            def step_lesson(offset):
                target_idx = curr_idx + offset
                if 0 <= target_idx < len(mod_lessons):
                    open_editor(mod_lessons[target_idx], active_module)

            prev_label = "Prev" if is_mobile(page) else "Previous Lesson"
            next_label = "Next" if is_mobile(page) else "Next Lesson"
            nav_row = ft.Row(
                [
                    ft.OutlinedButton(
                        prev_label,
                        icon=ft.Icons.ARROW_BACK_ROUNDED,
                        disabled=(curr_idx <= 0),
                        on_click=lambda e: step_lesson(-1),
                    ),
                    ft.OutlinedButton(
                        next_label,
                        icon=ft.Icons.ARROW_FORWARD_ROUNDED,
                        disabled=(curr_idx >= len(mod_lessons) - 1),
                        on_click=lambda e: step_lesson(1),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
            editor_content.controls.append(nav_row)

        editor_content.controls.append(
            ft.ElevatedButton(
                "Save & Close",
                bgcolor=UI_ACCENT,
                color=ft.Colors.ON_PRIMARY,
                height=48,
                width=float("inf"),
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
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
        title_field = ft.TextField(label="Module Title", autofocus=True, border_radius=10)
        pw = getattr(page, "width", None) or 800

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
            title=ft.Row([ft.Icon(ft.Icons.CREATE_NEW_FOLDER_ROUNDED, color=UI_ACCENT), ft.Text("Add New Module", weight=ft.FontWeight.BOLD)], spacing=8),
            content=ft.Container(width=min(460, max(260, pw - 48)), content=title_field),
            actions=[
                ft.TextButton("Cancel", on_click=close_modal),
                ft.ElevatedButton("Add Module", bgcolor=UI_ACCENT, color=ft.Colors.ON_PRIMARY, on_click=create_module),
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

    def open_lesson_type_picker(module):
        pw = getattr(page, "width", None) or 800

        def dismiss(e=None):
            picker_dialog.open = False
            page.update()

        type_cards = []
        for lt, label in LESSON_TYPES.items():
            lc = LESSON_TYPE_COLORS.get(lt, ft.Colors.GREY_500)
            li = LESSON_TYPE_ICONS.get(lt, ft.Icons.INSERT_DRIVE_FILE_ROUNDED)
            desc = LESSON_TYPE_DESCRIPTIONS.get(lt, "")

            def make_handler(lesson_type, mod):
                def handler(e):
                    dismiss()
                    create_new_lesson(lesson_type, mod)
                return handler

            type_cards.append(
                ft.Container(
                    border_radius=14,
                    border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                    padding=16,
                    on_click=make_handler(lt, module),
                    ink=True,
                    content=ft.Row(
                        [
                            ft.Container(
                                width=44, height=44,
                                border_radius=12,
                                bgcolor=ft.Colors.with_opacity(0.12, lc),
                                alignment=ft.Alignment(0, 0),
                                content=ft.Icon(li, color=lc, size=22),
                            ),
                            ft.Column(
                                [
                                    ft.Text(label, weight=ft.FontWeight.BOLD, size=14),
                                    ft.Text(desc, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, color=ft.Colors.ON_SURFACE_VARIANT, size=18),
                        ],
                        spacing=14,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                )
            )

        picker_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.ADD_CIRCLE_ROUNDED, color=UI_ACCENT),
                    ft.Text("Choose Lesson Type", weight=ft.FontWeight.BOLD),
                ],
                spacing=10,
            ),
            content=ft.Container(
                width=min(480, max(260, pw - 48)),
                content=ft.Column(type_cards, spacing=10, scroll=ft.ScrollMode.AUTO),
            ),
            actions=[ft.TextButton("Cancel", on_click=dismiss)],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(picker_dialog)
        picker_dialog.open = True
        page.update()

    def build_add_lesson_button(module):
        return ft.OutlinedButton(
            "Add Lesson",
            icon=ft.Icons.ADD_ROUNDED,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                side=ft.BorderSide(1, ft.Colors.with_opacity(0.4, UI_ACCENT)),
                padding=ft.Padding.symmetric(horizontal=16, vertical=10),
            ),
            on_click=lambda e: open_lesson_type_picker(module),
        )

    def build_lesson_row(lesson, module):
        t = lesson.get("type", "text")
        is_active = (active_lesson is not None and active_lesson is lesson)
        val_errors = validate_lesson(lesson)
        is_valid = (len(val_errors) == 0)

        def delete_lesson(e):
            if lesson in module.get("lessons", []):
                module["lessons"].remove(lesson)
                if active_lesson is lesson:
                    close_editor()
                else:
                    refresh_curriculum()

        status_indicator = (
            ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=14, color=ft.Colors.GREEN_600, tooltip="Complete")
            if is_valid
            else ft.Icon(ft.Icons.WARNING_ROUNDED, size=14, color=ft.Colors.AMBER_600, tooltip="Incomplete: " + "; ".join(val_errors))
        )

        action_buttons = ft.Row(
            [
                status_indicator,
                ft.IconButton(
                    ft.Icons.EDIT_ROUNDED,
                    icon_size=18,
                    icon_color=UI_ACCENT if is_active else None,
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
            spacing=2,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        lesson_info = ft.Column(
            [
                ft.Text(
                    str(lesson.get("title") or "Untitled Lesson"),
                    size=14,
                    weight=ft.FontWeight.W_600,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                lesson_badge(t),
            ],
            spacing=4,
            tight=True,
        )

        type_icon_container = ft.Container(
            width=34, height=34,
            border_radius=8,
            bgcolor=ft.Colors.with_opacity(0.10, lesson_color(t)),
            alignment=ft.Alignment.CENTER,
            content=ft.Icon(lesson_icon(t), color=lesson_color(t), size=18),
        )

        if is_mobile(page):
            content = ft.Column(
                [
                    ft.Row(
                        [
                            type_icon_container,
                            ft.Container(expand=True, content=lesson_info),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        [action_buttons],
                        alignment=ft.MainAxisAlignment.END,
                    ),
                ],
                spacing=6,
            )
        else:
            content = ft.Row(
                [
                    type_icon_container,
                    ft.Container(expand=True, content=lesson_info),
                    action_buttons,
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

        row_border = (
            ft.Border(
                left=ft.BorderSide(3, UI_ACCENT),
                top=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                right=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
            )
            if is_active
            else ft.Border.all(1, ft.Colors.OUTLINE_VARIANT)
        )
        row_bg = (
            ft.Colors.with_opacity(0.06, UI_ACCENT)
            if is_active
            else ft.Colors.SURFACE
        )

        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            border_radius=12,
            bgcolor=row_bg,
            border=row_border,
            ink=True,
            on_click=lambda e: open_editor(lesson, module),
            content=content,
        )

    def build_module_block(module, idx):
        mod_id = module.get("id", f"mod_{idx}")
        is_collapsed = mod_id in collapsed_modules

        def toggle_collapse(e=None):
            if mod_id in collapsed_modules:
                collapsed_modules.remove(mod_id)
            else:
                collapsed_modules.add(mod_id)
            refresh_curriculum()

        def move_up(e):
            reorder_list(modules, idx, idx - 1)
            refresh_curriculum()

        def move_down(e):
            reorder_list(modules, idx, idx + 1)
            refresh_curriculum()

        def delete_mod(e):
            if active_module is module:
                close_editor()
            modules.pop(idx)
            refresh_curriculum()

        def rename_mod(e):
            title_field = ft.TextField(
                label="Module Title",
                value=str(module.get("title") or "Untitled Module"),
                autofocus=True,
                border_radius=10,
            )

            def close_modal(ev=None):
                dlg.open = False
                page.update()

            def save(ev=None):
                val = title_field.value.strip() if title_field.value else ""
                module["title"] = val or module.get("title", "Untitled Module")
                close_modal()
                refresh_curriculum()

            pw = getattr(page, "width", None) or 800
            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Row([ft.Icon(ft.Icons.EDIT_ROUNDED, color=UI_ACCENT), ft.Text("Rename Module", weight=ft.FontWeight.BOLD)], spacing=8),
                content=ft.Container(width=min(460, max(260, pw - 48)), content=title_field),
                actions=[
                    ft.TextButton("Cancel", on_click=close_modal),
                    ft.ElevatedButton("Save", bgcolor=UI_ACCENT, color=ft.Colors.ON_PRIMARY, on_click=save),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.overlay.append(dlg)
            dlg.open = True
            page.update()

        more_menu = ft.PopupMenuButton(
            icon=ft.Icons.MORE_HORIZ_ROUNDED,
            tooltip="Module options",
            items=[
                ft.PopupMenuItem(content=ft.Text("Rename Module", size=13), icon=ft.Icons.EDIT_ROUNDED, on_click=rename_mod),
                ft.PopupMenuItem(content=ft.Text("Move Up", size=13), icon=ft.Icons.ARROW_UPWARD_ROUNDED, on_click=move_up),
                ft.PopupMenuItem(content=ft.Text("Move Down", size=13), icon=ft.Icons.ARROW_DOWNWARD_ROUNDED, on_click=move_down),
                ft.PopupMenuItem(content=ft.Text("Delete Module", size=13), icon=ft.Icons.DELETE_OUTLINE_ROUNDED, on_click=delete_mod),
            ],
        )

        mod_lessons = module.get("lessons", [])
        q = search_query[0].lower().strip()
        filtered_lessons = [
            l for l in mod_lessons 
            if not q or q in str(l.get("title", "")).lower() or q in str(module.get("title", "")).lower()
        ]

        if q and not filtered_lessons and (q not in str(module.get("title", "")).lower()):
            return ft.Container(visible=False)

        chevron_icon = ft.Icons.KEYBOARD_ARROW_RIGHT_ROUNDED if is_collapsed else ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED

        header = ft.Row(
            [
                ft.IconButton(
                    chevron_icon,
                    icon_size=20,
                    tooltip="Collapse / Expand",
                    on_click=toggle_collapse,
                ),
                ft.Container(
                    width=28, height=28,
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.12, UI_ACCENT),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text(f"{idx + 1:02d}", size=12, weight=ft.FontWeight.BOLD, color=UI_ACCENT),
                ),
                ft.Container(
                    expand=True,
                    content=ft.Text(
                        str(module.get("title") or "Untitled Module"),
                        size=16,
                        weight=ft.FontWeight.BOLD,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                ),
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=999,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                    content=ft.Text(
                        f"{len(mod_lessons)} lesson{'s' if len(mod_lessons) != 1 else ''}",
                        size=11,
                        weight=ft.FontWeight.W_500,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ),
                more_menu,
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        lessons_col = ft.Column(
            [build_lesson_row(l, module) for l in filtered_lessons],
            spacing=8,
            visible=not is_collapsed,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        add_lesson_btn = build_add_lesson_button(module)
        add_lesson_btn.visible = not is_collapsed

        return ft.Container(
            padding=14 if is_mobile(page) else 16,
            border_radius=14,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            content=ft.Column(
                [
                    header,
                    lessons_col,
                    add_lesson_btn,
                ],
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
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

        action_name = "Update" if has_existing_materials[0] else "Publish"

        if errors:
            show_dialog(f"Cannot {action_name.lower()} yet", "\n".join(errors), success=False)
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
            has_existing_materials[0] = True
            publish_btn.text = "Update Course"
            publish_btn.icon = ft.Icons.CHECK_CIRCLE_ROUNDED
            page.update()
            show_dialog(f"{action_name} successful", f"Course curriculum saved and {action_name.lower()}ed successfully.", success=True)
        except Exception as ex:
            show_dialog(f"{action_name} failed", str(ex), success=False)

    def build_publish_button():
        return ft.ElevatedButton(
            "Update Course" if has_existing_materials[0] else "Publish Course",
            icon=ft.Icons.CHECK_CIRCLE_ROUNDED if has_existing_materials[0] else ft.Icons.ROCKET_LAUNCH_ROUNDED,
            bgcolor=UI_ACCENT,
            color=ft.Colors.ON_PRIMARY,
            height=36,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding.symmetric(horizontal=14, vertical=0),
            ),
            on_click=lambda e: page.run_task(publish_course),
        )

    # =========================================================
    # AI COURSE DRAFT
    # =========================================================

    def open_ai_draft_dialog(e=None):
        topic_field = ft.TextField(
            label="Course Topic",
            hint_text="e.g. Modern Full-Stack Development with React and Python",
            autofocus=True,
            width=float("inf"),
            multiline=True,
            min_lines=1,
            max_lines=3,
            border_radius=10,
        )
        context_field = ft.TextField(
            label="Target Audience & Context",
            hint_text="e.g. Undergraduate students transitioning from basic scripts to production applications",
            width=float("inf"),
            multiline=True,
            min_lines=1,
            max_lines=3,
            border_radius=10,
        )
        
        status_text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        selected_reference_files = []
        files_chips = ft.Row(wrap=True, spacing=5, run_spacing=5)
        
        def render_file_chips():
            files_chips.controls.clear()
            for f in selected_reference_files:
                files_chips.controls.append(
                    ft.Chip(
                        label=ft.Text(f["name"], size=12),
                        on_delete=lambda e, fname=f["name"]: remove_file(fname),
                        bgcolor=ft.Colors.ON_INVERSE_SURFACE
                    )
                )
            attach_btn.disabled = (len(selected_reference_files) >= 15)
            page.update()

        def remove_file(name):
            nonlocal selected_reference_files
            selected_reference_files = [f for f in selected_reference_files if f["name"] != name]
            render_file_chips()

        async def pick_files_handler(ev):
            if len(selected_reference_files) >= 15:
                return
            ev.control.disabled = True
            page.update()
            try:
                files = await ft.FilePicker().pick_files(
                    allow_multiple=True,
                    allowed_extensions=["pdf", "md", "txt"]
                )
                if files:
                    for f in files:
                        if len(selected_reference_files) >= 15:
                            break
                        if not any(existing["name"] == f.name for existing in selected_reference_files):
                            content = ""
                            fname_lower = (f.name or "").lower()

                            # --- PDF Text Extraction via PyMuPDF (fitz) ---
                            if fname_lower.endswith(".pdf"):
                                try:
                                    import fitz  # PyMuPDF
                                    doc = None
                                    if getattr(f, "path", None):
                                        doc = fitz.open(f.path)
                                    elif getattr(f, "bytes", None):
                                        doc = fitz.open(stream=f.bytes, filetype="pdf")

                                    if doc:
                                        pages_text = []
                                        # Cap at first 35 pages to stay safely within optimal context bounds
                                        max_pages = min(len(doc), 35)
                                        for p_idx in range(max_pages):
                                            txt = doc[p_idx].get_text()
                                            if txt and txt.strip():
                                                pages_text.append(txt.strip())
                                        doc.close()
                                        content = "\n\n".join(pages_text).strip()
                                        if not content:
                                            content = "[PDF scanned or contains no extractable text]"
                                except Exception as e:
                                    content = f"[Error reading PDF: {e}]"
                            else:
                                # Markdown / Plain text
                                if getattr(f, "path", None):
                                    try:
                                        with open(f.path, 'r', encoding='utf-8', errors='replace') as file_obj:
                                            content = file_obj.read()
                                    except Exception as e:
                                        content = f"[Could not read file: {e}]"
                                elif getattr(f, "bytes", None):
                                    content = f.bytes.decode("utf-8", errors="replace")

                            selected_reference_files.append({
                                "name": f.name,
                                "content": content
                            })
                render_file_chips()
            except Exception as ex:
                status_text.value = f"Error picking files: {ex}"
                status_text.color = ft.Colors.ERROR
                page.update()
            finally:
                ev.control.disabled = False
                page.update()

        attach_btn = ft.Container(
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            border_radius=10,
            border=ft.Border.all(1.5, ft.Colors.with_opacity(0.3, UI_ACCENT)),
            bgcolor=ft.Colors.with_opacity(0.04, UI_ACCENT),
            ink=True,
            on_click=lambda e: page.run_task(pick_files_handler, e),
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.ATTACH_FILE_ROUNDED, color=UI_ACCENT, size=20),
                    ft.Column(
                        [
                            ft.Text("Attach Reference Files (.pdf, .md, .txt)", size=13, weight=ft.FontWeight.W_600),
                            ft.Text("Optional syllabus, slides, or notes for AI to structure", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.Icon(ft.Icons.ADD_ROUNDED, color=UI_ACCENT, size=18),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

        generate_btn = ft.ElevatedButton(
            "Generate Curriculum",
            icon=ft.Icons.AUTO_AWESOME_ROUNDED,
            bgcolor=UI_ACCENT,
            color=ft.Colors.ON_PRIMARY,
        )

        def close_dialog(ev=None):
            dlg.open = False
            page.update()

        async def on_generate(ev):
            topic = topic_field.value.strip()
            context = context_field.value.strip()

            if not topic:
                status_text.value = "Topic is required."
                status_text.color = ft.Colors.ERROR
                page.update()
                return
            if not context and not selected_reference_files:
                status_text.value = "Context or attached files are required."
                status_text.color = ft.Colors.ERROR
                page.update()
                return

            generate_btn.disabled = True
            status_text.value = "Generating multi-format curriculum with AI… please wait."
            status_text.color = ft.Colors.ORANGE_700
            page.update()

            final_context = context
            if selected_reference_files:
                final_context += "\n\n=== ATTACHED REFERENCE FILES ===\n"
                for f in selected_reference_files:
                    final_context += f"\n--- {f['name']} ---\n{f['content']}\n"

            result = await generate_course_draft(token=token, topic=topic, context=final_context)

            if result.get("error") == "forbidden":
                status_text.value = "You don't have permission to generate courses."
                status_text.color = ft.Colors.ERROR
                generate_btn.disabled = False
                page.update()
                return

            if result.get("error") == "plan_required":
                status_text.value = "Your organisation plan doesn't include AI generation."
                status_text.color = ft.Colors.ERROR
                generate_btn.disabled = False
                page.update()
                return

            if result.get("error") or result.get("status") != "success":
                status_text.value = "Generation failed. Please try again."
                status_text.color = ft.Colors.ERROR
                generate_btn.disabled = False
                page.update()
                return

            draft = result.get("data", {})
            new_modules = draft.get("modules", [])
            if new_modules:
                modules.clear()
                modules.extend([ensure_module_shape(m) for m in new_modules])

            close_dialog()
            refresh_curriculum()

        generate_btn.on_click = lambda ev: page.run_task(on_generate, ev)

        pw = getattr(page, "width", None) or 800
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=UI_ACCENT),
                    ft.Text("Generate Curriculum with AI", weight=ft.FontWeight.BOLD),
                ],
                spacing=8,
            ),
            content=ft.Container(
                width=min(540, max(260, pw - 48)),
                content=ft.Column(
                    [
                        ft.Text(
                            "Describe your course topic, target audience, and optional reference files. AI will craft a structured curriculum for you to customize.",
                            size=13,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        topic_field,
                        context_field,
                        attach_btn,
                        files_chips,
                        status_text,
                    ],
                    spacing=14,
                    tight=True,
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=close_dialog),
                generate_btn,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def build_ai_draft_button():
        return ft.OutlinedButton(
            "AI Draft",
            icon=ft.Icons.AUTO_AWESOME_ROUNDED,
            height=36,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding.symmetric(horizontal=12, vertical=0),
            ),
            on_click=open_ai_draft_dialog,
        )

    # =========================================================
    # Render curriculum
    # =========================================================

    status_icon = ft.Icon(ft.Icons.WARNING_ROUNDED, size=13, color=ft.Colors.AMBER_600)
    status_text = ft.Text("Drafting", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_700)
    status_chip_container = ft.Container(
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        border_radius=999,
        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_600),
        content=ft.Row([status_icon, status_text], spacing=4, tight=True),
    )

    metrics_modules_text = ft.Text(f"{len(modules)} Modules", size=11, weight=ft.FontWeight.W_600)
    metrics_lessons_text = ft.Text("0 Lessons", size=11, weight=ft.FontWeight.W_600)
    metrics_quizzes_text = ft.Text("0 Quizzes", size=11, weight=ft.FontWeight.W_600)

    metrics_chips = ft.Row(
        [
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                border_radius=8,
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                content=ft.Row([ft.Icon(ft.Icons.FOLDER_SPECIAL_ROUNDED, size=13, color=UI_ACCENT), metrics_modules_text], spacing=4, tight=True),
            ),
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                border_radius=8,
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                content=ft.Row([ft.Icon(ft.Icons.ARTICLE_ROUNDED, size=13, color=ft.Colors.BLUE_500), metrics_lessons_text], spacing=4, tight=True),
            ),
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                border_radius=8,
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                content=ft.Row([ft.Icon(ft.Icons.QUIZ_ROUNDED, size=13, color=ft.Colors.ORANGE_500), metrics_quizzes_text], spacing=4, tight=True),
            ),
        ],
        spacing=6,
        tight=True,
        wrap=True,
    )

    publish_btn = build_publish_button()

    add_module_btn = ft.OutlinedButton(
        "Add Module",
        icon=ft.Icons.CREATE_NEW_FOLDER_ROUNDED,
        height=36,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=8),
            padding=ft.Padding.symmetric(horizontal=12, vertical=0),
        ),
        on_click=open_add_module_modal,
    )

    ai_draft_btn = build_ai_draft_button()
    preview_btn = ft.OutlinedButton(
        "Preview",
        icon=ft.Icons.VISIBILITY_ROUNDED,
        height=36,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=8),
            padding=ft.Padding.symmetric(horizontal=12, vertical=0),
        ),
        on_click=lambda e: page.run_task(open_preview, e),
    )

    def on_filter_change(e):
        search_query[0] = e.control.value
        clear_search_btn.visible = bool(e.control.value)
        render_modules_list()
        page.update()

    def clear_search_click(e):
        search_query[0] = ""
        filter_field.value = ""
        clear_search_btn.visible = False
        render_modules_list()
        page.update()

    clear_search_btn = ft.IconButton(
        ft.Icons.CLEAR_ROUNDED,
        icon_size=16,
        tooltip="Clear search",
        visible=bool(search_query[0]),
        on_click=clear_search_click,
    )

    filter_field = ft.TextField(
        hint_text="Search modules, lessons, topics...",
        prefix_icon=ft.Icons.SEARCH_ROUNDED,
        suffix=clear_search_btn,
        height=40,
        text_size=13,
        content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        border_radius=10,
        value=search_query[0],
        on_change=on_filter_change,
    )

    filter_container = ft.Container(
        content=filter_field,
    )

    course_title_text = ft.Text(
        course_name if course_name else "Curriculum Studio",
        size=15 if is_mobile(page) else 18,
        weight=ft.FontWeight.BOLD,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )

    back_and_title = ft.Row(
        [
            ft.IconButton(
                ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED,
                icon_size=16 if is_mobile(page) else 18,
                tooltip="Return to Courses",
                on_click=lambda e: page.go("/dashboard"),
            ),
            ft.Container(
                expand=True,
                content=course_title_text,
            ),
            status_chip_container,
        ],
        spacing=6 if is_mobile(page) else 8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    header_card = ft.Container(
        padding=ft.Padding.symmetric(
            horizontal=12 if is_mobile(page) else 16,
            vertical=12
        ),
        border_radius=14,
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
        content=ft.Column(
            [
                back_and_title,
                metrics_chips,
                ft.Divider(height=1, color=ft.Colors.with_opacity(0.12, ft.Colors.OUTLINE)),
                filter_container,
            ],
            spacing=10,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
    )

    def update_summary_bar_layout():
        mob = is_mobile(page)
        course_title_text.size = 15 if mob else 18
        header_card.padding = ft.Padding.symmetric(horizontal=12 if mob else 16, vertical=12)
        curriculum_container.padding = ft.Padding.symmetric(horizontal=10 if mob else 16, vertical=12)
        actions_card.padding = ft.Padding.symmetric(horizontal=12 if mob else 16, vertical=10)

    summary_layout_updater[0] = update_summary_bar_layout

    actions_tile_row = ft.Row(
        [
            add_module_btn,
            ai_draft_btn,
            preview_btn,
            publish_btn,
        ],
        spacing=10,
        run_spacing=8,
        wrap=True,
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    actions_card = ft.Container(
        padding=ft.Padding.symmetric(horizontal=16, vertical=10),
        border_radius=14,
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
        content=actions_tile_row,
    )

    def render_modules_list():
        q = search_query[0].lower().strip()
        new_blocks = []
        for idx, m in enumerate(modules):
            block = build_module_block(m, idx)
            if getattr(block, "visible", True) is not False:
                new_blocks.append(block)

        if not new_blocks and modules:
            new_blocks.append(
                ft.Container(
                    padding=30,
                    border_radius=14,
                    bgcolor=ft.Colors.SURFACE,
                    border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.SEARCH_OFF_ROUNDED, size=32, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(f"No modules or lessons matching '{q}'", size=13, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                    ),
                )
            )
        elif not modules:
            new_blocks.append(
                ft.Container(
                    padding=40,
                    border_radius=14,
                    bgcolor=ft.Colors.SURFACE,
                    border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.MENU_BOOK_ROUNDED, size=44, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text("No modules yet in this course.", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                            ft.Text("Click 'Add Module' or 'AI Draft' above to build your curriculum.", size=13, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                    ),
                )
            )

        curriculum_column.controls = [header_card, actions_card] + new_blocks

    def refresh_curriculum():
        total_lessons = sum(len(m.get("lessons", [])) for m in modules)
        total_quizzes = sum(
            1 for m in modules for l in m.get("lessons", []) if l.get("type") == "assessment"
        )
        val_errors = []
        for m in modules:
            for l in m.get("lessons", []):
                val_errors.extend(validate_lesson(l))

        is_ready = (len(modules) > 0 and all(len(m.get("lessons", [])) > 0 for m in modules) and len(val_errors) == 0)

        if is_ready:
            status_chip_container.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.GREEN_600)
            status_icon.name = ft.Icons.CHECK_CIRCLE_ROUNDED
            status_icon.color = ft.Colors.GREEN_600
            status_text.value = "Ready to Publish"
            status_text.color = ft.Colors.GREEN_700
        else:
            status_chip_container.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.AMBER_600)
            status_icon.name = ft.Icons.WARNING_ROUNDED
            status_icon.color = ft.Colors.AMBER_600
            status_text.value = f"{len(val_errors)} Incomplete" if val_errors else "Drafting"
            status_text.color = ft.Colors.AMBER_700

        metrics_modules_text.value = f"{len(modules)} Modules"
        metrics_lessons_text.value = f"{total_lessons} Lessons"
        metrics_quizzes_text.value = f"{total_quizzes} Quizzes"

        publish_btn.text = "Update Course" if has_existing_materials[0] else "Publish Course"
        publish_btn.icon = ft.Icons.CHECK_CIRCLE_ROUNDED if has_existing_materials[0] else ft.Icons.ROCKET_LAUNCH_ROUNDED

        render_modules_list()
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
                        ft.Row(
                            [
                                curriculum_container,
                                editor_panel,
                            ],
                            expand=True,
                            spacing=0,
                            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                        ),
                        preview_overlay,
                    ],
                    expand=True,
                    fit=ft.StackFit.EXPAND,
                ),
            )
        ],
    )