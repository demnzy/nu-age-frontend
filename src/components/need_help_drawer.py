"""
src/components/need_help_drawer.py

Contextual, floating, draggable, and Socratic AI Study Companion (Nu-AI Tutor).
Grounds doubts in the currently active lesson/module with:
- Square-rounded card aesthetics matching modern reference UI.
- Top model pill badge ([ ✨ Nu-AI Tutor ] / [ 🛡️ Assessment Mode ]).
- Non-blocking, draggable overlay on desktop via GestureDetector.
- Adaptive collapsible bottom dock on mobile with 1-tap minimize pill.
- Session-wide chat history persistence across drawer toggles & navigation.
- Dynamic real-time module/lesson context switching without reopening.
- Strict Socratic assessment guardrails (anti-cheating hints and guidance).
- Assistant message action bar (Copy, Regenerate, Thumbs-up).
- Uncropped input composer with inline rounded send button.
"""

import asyncio
import flet as ft
from typing import Dict, Any, Optional, Callable, List
from src.requests.chats import ask_ai_tutor_api
from src.services.ai_tutor_session import (
    get_course_history,
    append_course_message,
    clear_course_history,
)
from src.utils.file_opener import show_page_snackbar, safe_set_clipboard


async def _get_auth_token(page: ft.Page) -> Optional[str]:
    """Retrieve auth token safely without deprecation warnings."""
    try:
        if hasattr(page, "session") and hasattr(page.session, "store"):
            tok = page.session.store.get("token") or page.session.store.get("auth_token")
            if tok:
                return str(tok)
    except Exception:
        pass
    try:
        sp = ft.SharedPreferences()
        tok = await sp.get("auth_token")
        if tok:
            return str(tok)
    except Exception:
        pass
    try:
        if hasattr(page, "shared_preferences"):
            tok = await page.shared_preferences.get("auth_token")
            if tok:
                return str(tok)
    except Exception:
        pass
    return None


class NeedHelpController:
    """Controller reference to allow external updates (e.g. module switching)."""

    def __init__(self):
        self.update_module_context: Optional[Callable] = None
        self.toggle_minimized: Optional[Callable] = None


def build_need_help_drawer(
    page: ft.Page,
    lesson_data: Dict[str, Any],
    module_title: str,
    course_title: str,
    on_close: Optional[Callable] = None,
    course_id: Optional[str] = "default",
    is_assessment: bool = False,
    controller: Optional[NeedHelpController] = None,
    target_container: Optional[ft.Container] = None,
) -> ft.Control:
    """
    Constructs the floating, draggable, square-rounded conversational AI Study Assistant.
    """
    is_dark = getattr(page, "theme_mode", None) == ft.ThemeMode.DARK
    card_bg = ft.Colors.SURFACE if is_dark else "#FFFFFF"
    accent = ft.Colors.PRIMARY

    # Mutable state for active learning context
    current_context = {
        "lesson_data": lesson_data or {},
        "lesson_title": (lesson_data or {}).get("title", "Current Lesson"),
        "module_title": module_title or "Module",
        "course_title": course_title or "Course",
        "is_assessment": is_assessment,
        "is_generating": False,
        "is_minimized": False,
    }

    def _get_lesson_content() -> str:
        ld = current_context["lesson_data"]
        return str(ld.get("content") or ld.get("description") or "")[:1400]

    # Mobile breakpoint check
    page_w = getattr(page, "width", None) or 1024
    page_h = getattr(page, "height", None) or 768
    is_mobile = page_w < 768

    win_width = min(390, max(300, page_w - 24)) if is_mobile else 380
    win_height = min(500, max(360, int(page_h * 0.65))) if is_mobile else 540

    # Scrollable message list
    messages_col = ft.Column(
        spacing=12,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    # Context subtitle header label
    header_subtitle_text = ft.Text(
        current_context["lesson_title"],
        size=11,
        color=ft.Colors.ON_SURFACE_VARIANT,
        no_wrap=True,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )

    # Assessment badge pill
    assessment_badge = ft.Container(
        visible=current_context["is_assessment"],
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
        border_radius=ft.BorderRadius.all(6),
        bgcolor=ft.Colors.with_opacity(0.14, ft.Colors.AMBER_600),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.AMBER_600)),
        content=ft.Row(
            spacing=4,
            tight=True,
            controls=[
                ft.Icon(ft.Icons.SHIELD_ROUNDED, size=12, color=ft.Colors.AMBER_600),
                ft.Text("Assessment Mode", size=10, weight=ft.FontWeight.W_700, color=ft.Colors.AMBER_600),
            ],
        ),
    )

    # Copy / feedback helper
    def _copy_to_clipboard(text: str):
        async def _do_copy():
            await safe_set_clipboard(page, text)
            show_page_snackbar(
                page,
                ft.SnackBar(
                    content=ft.Text("Copied explanation to clipboard!"),
                    duration=2000,
                    behavior=ft.SnackBarBehavior.FLOATING,
                ),
            )
        asyncio.create_task(_do_copy())

    def _thumbs_up(btn: ft.IconButton):
        btn.icon = ft.Icons.THUMB_UP_ROUNDED
        btn.icon_color = ft.Colors.GREEN_600
        btn.tooltip = "Thanks for your feedback!"
        page.update()

    # Message bubble renderer matching reference image aesthetics
    def _bubble(text: str, is_user: bool, can_retry: bool = False, query_for_retry: str = "") -> ft.Control:
        max_bubble_w = 330 if not is_mobile else min(320, max(220, win_width - 50))

        if is_user:
            return ft.Container(
                alignment=ft.Alignment.CENTER_RIGHT,
                content=ft.Container(
                    padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                    border_radius=ft.BorderRadius.all(12),
                    bgcolor=accent,
                    content=ft.Text(
                        text,
                        size=13,
                        color=ft.Colors.WHITE,
                        selectable=True,
                    ),
                    width=max_bubble_w,
                ),
            )

        # Assistant bubble (Panel 1 & Panel 2 from reference image)
        assistant_card_bg = ft.Colors.SURFACE_CONTAINER_HIGHEST if is_dark else "#F8FAFC"
        assistant_border = ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE))

        action_row = ft.Row(
            spacing=4,
            tight=True,
            controls=[
                ft.IconButton(
                    icon=ft.Icons.CONTENT_COPY_ROUNDED,
                    icon_size=14,
                    icon_color=ft.Colors.GREY_500,
                    tooltip="Copy explanation",
                    style=ft.ButtonStyle(padding=ft.Padding.all(4)),
                    on_click=lambda _: _copy_to_clipboard(text),
                ),
                ft.IconButton(
                    icon=ft.Icons.REFRESH_ROUNDED,
                    icon_size=14,
                    icon_color=ft.Colors.GREY_500,
                    tooltip="Regenerate response",
                    style=ft.ButtonStyle(padding=ft.Padding.all(4)),
                    visible=can_retry and bool(query_for_retry),
                    on_click=lambda _: send_query(query_for_retry),
                ),
                ft.IconButton(
                    icon=ft.Icons.THUMB_UP_OUTLINED,
                    icon_size=14,
                    icon_color=ft.Colors.GREY_500,
                    tooltip="Helpful",
                    style=ft.ButtonStyle(padding=ft.Padding.all(4)),
                    on_click=lambda e: _thumbs_up(e.control),
                ),
            ],
        )

        return ft.Container(
            alignment=ft.Alignment.CENTER_LEFT,
            content=ft.Column(
                spacing=3,
                tight=True,
                controls=[
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=14, vertical=11),
                        border_radius=ft.BorderRadius.all(12),
                        bgcolor=assistant_card_bg,
                        border=assistant_border,
                        content=ft.Markdown(
                            text,
                            selectable=True,
                            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                        ),
                        width=max_bubble_w,
                    ),
                    action_row,
                ],
            ),
        )

    def _render_context_switch_pill(label: str) -> ft.Container:
        return ft.Container(
            alignment=ft.Alignment.CENTER,
            padding=ft.Padding.symmetric(vertical=4),
            content=ft.Container(
                padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                border_radius=ft.BorderRadius.all(10),
                bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                content=ft.Text(
                    f"── {label} ──",
                    size=10,
                    color=ft.Colors.GREY_500,
                    weight=ft.FontWeight.W_600,
                ),
            ),
        )

    # Initialize from Session History or show initial Welcome message
    session_history = get_course_history(course_id)
    if session_history:
        for turn in session_history:
            is_u = turn.get("role") == "user" or turn.get("is_user", False)
            content = turn.get("content", "")
            messages_col.controls.append(_bubble(content, is_user=is_u))
    else:
        # Initial Welcome message matching reference
        welcome_text = (
            f"👋 Hi! I'm your **Nu-AI Study Companion** for **{current_context['lesson_title']}**.\n\n"
            f"Stuck on a formula, concept, or practical problem? "
            f"Ask me anything or tap one of the quick prompts below."
        )
        messages_col.controls.append(_bubble(welcome_text, is_user=False))

    # Input composer
    input_field = ft.TextField(
        hint_text="Ask a question or explain a doubt...",
        text_size=13.5,
        border_radius=ft.BorderRadius.all(12),
        content_padding=ft.Padding.symmetric(horizontal=14, vertical=12),
        autofocus=not is_mobile,
        shift_enter=True,
        min_lines=1,
        max_lines=4,
        filled=True,
        expand=True,
    )

    typing_indicator = ft.Row(
        visible=False,
        spacing=8,
        controls=[
            ft.ProgressRing(width=14, height=14, stroke_width=2, color=accent),
            ft.Text("Nu-AI thinking...", size=11, color=ft.Colors.GREY_500, italic=True),
        ],
    )

    # Socratic & standard offline fallback generator
    def _generate_fallback_response(user_query: str) -> str:
        les_title = current_context["lesson_title"]
        mod_title = current_context["module_title"]
        is_as = current_context["is_assessment"]
        q_lower = user_query.lower()

        if is_as:
            # Socratic Assessment Anti-Cheating Response
            if any(w in q_lower for w in ["answer", "option", "solution", "which one", "a, b, or c"]):
                return (
                    f"🛡️ **Assessment Mode Active**:\n\n"
                    f"I cannot provide the direct answer, option letter, or solution code for graded questions.\n\n"
                    f"💡 **How to approach this problem in {mod_title}**:\n"
                    f"1. Break down the core rule or definition introduced in this lesson.\n"
                    f"2. Eliminate options that contradict fundamental principles.\n"
                    f"3. Ask yourself: *What is the relationship between the inputs and expected output?*\n\n"
                    f"Would you like me to explain the theoretical concept behind this question?"
                )
            return (
                f"🧠 **Socratic Concept Hint for {les_title}**:\n\n"
                f"In this assessment, remember the guiding principle from **{mod_title}**: "
                f"evaluate each step systematically and verify your constraints before choosing your final response.\n\n"
                f"👉 *Hint*: Reflect on how edge cases or exceptions are handled in this topic."
            )

        # Standard study doubt response
        if "simply" in q_lower or "simple" in q_lower:
            return (
                f"💡 **Plain English Explanation of {les_title}**:\n\n"
                f"Think of this topic as a practical building block in **{mod_title}**. "
                f"Rather than getting lost in technical jargon, focus on the fundamental objective: "
                f"it provides a structured method to achieve the goal reliably.\n\n"
                f"👉 **Rule of thumb**: Identify your inputs, apply the core principle step-by-step, "
                f"and test your expected outcome against a basic example."
            )
        elif "example" in q_lower or "analogy" in q_lower:
            return (
                f"🔍 **Real-World Analogy for {les_title}**:\n\n"
                f"Imagine you are running a kitchen:\n"
                f"- The input ingredients represent your raw problem data.\n"
                f"- The recipe represents the step-by-step method shown in **{les_title}**.\n"
                f"- The final dish is your verified result.\n\n"
                f"If you skip a step in the recipe, the dish won't turn out right! "
                f"That's why paying attention to each phase ensures consistent success."
            )
        elif "takeaway" in q_lower or "summary" in q_lower:
            return (
                f"📝 **Key Takeaways for {les_title}**:\n\n"
                f"1. **Core Principle**: Essential foundation within **{mod_title}**.\n"
                f"2. **Application**: Applied directly during assessments and hands-on exercises.\n"
                f"3. **Pro-Tip**: Review the practice cards linked to this module to reinforce long-term recall."
            )
        elif "quiz" in q_lower:
            return (
                f"❓ **Quick Concept Check on {les_title}**:\n\n"
                f"*Question*: What is the primary purpose of this topic inside {mod_title}?\n\n"
                f"A) To establish fundamental understanding\n"
                f"B) To bypass all earlier prerequisites\n"
                f"C) To guess without verification\n\n"
                f"*(Hint: Think about how this builds upon earlier modules!)*"
            )
        else:
            return (
                f"🎯 **Concerning '{user_query}' in {les_title}**:\n\n"
                f"In the context of **{mod_title}**, this concept works by ensuring "
                f"clarity, correctness, and reliable execution.\n\n"
                f"Review the accompanying reading notes or test out an exercise in the **Practice** tab to reinforce it!"
            )

    async def _respond(user_text: str):
        current_context["is_generating"] = True
        typing_indicator.visible = True
        send_btn.disabled = True
        page.update()

        reply = None

        # 1. Attempt OpenAI API pipeline with assessment guardrail
        try:
            token = await _get_auth_token(page)
            if token:
                conv_history = get_course_history(course_id)
                api_res = await ask_ai_tutor_api(
                    token=token,
                    query=user_text,
                    course_title=current_context["course_title"],
                    module_title=current_context["module_title"],
                    lesson_title=current_context["lesson_title"],
                    lesson_content=_get_lesson_content(),
                    conversation_history=conv_history,
                    is_assessment=current_context["is_assessment"],
                )
                if isinstance(api_res, dict) and "reply" in api_res:
                    reply = api_res["reply"]
        except Exception as ex:
            print(f"[AI Tutor API Notice] falling back to local Socratic engine: {ex}")

        # 2. Resilient pedagogical fallback
        if not reply:
            await asyncio.sleep(0.35)
            reply = _generate_fallback_response(user_text)

        # Persist assistant turn to session
        append_course_message(course_id, "assistant", reply, current_context["lesson_title"])

        typing_indicator.visible = False
        current_context["is_generating"] = False
        send_btn.disabled = False
        messages_col.controls.append(_bubble(reply, is_user=False, can_retry=True, query_for_retry=user_text))
        page.update()

    def send_query(text: str):
        clean_text = text.strip()
        if not clean_text or current_context["is_generating"]:
            return

        # Persist user turn to session
        append_course_message(course_id, "user", clean_text, current_context["lesson_title"])
        messages_col.controls.append(_bubble(clean_text, is_user=True))
        input_field.value = ""
        page.update()
        page.run_task(_respond, clean_text)

    def on_send_click(e):
        send_query(input_field.value)

    input_field.on_submit = on_send_click

    send_btn = ft.Container(
        content=ft.IconButton(
            icon=ft.Icons.ARROW_UPWARD_ROUNDED,
            icon_color=ft.Colors.WHITE,
            icon_size=18,
            style=ft.ButtonStyle(
                bgcolor=accent,
                shape=ft.CircleBorder(),
                padding=ft.Padding.all(8),
            ),
            tooltip="Send Question",
            on_click=on_send_click,
        ),
    )

    # Suggestion prompt chips container (swaps in assessment mode)
    chips_col = ft.Column(spacing=6)

    def _refresh_chips():
        chips_col.controls.clear()
        is_as = current_context["is_assessment"]

        def make_chip(label: str, query: str):
            return ft.Container(
                padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                border_radius=ft.BorderRadius.all(12),
                bgcolor=ft.Colors.with_opacity(0.08, accent),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.18, accent)),
                ink=True,
                on_click=lambda _: send_query(query),
                content=ft.Text(label, size=11, weight=ft.FontWeight.W_600, color=accent),
            )

        if is_as:
            chips_col.controls.append(
                ft.Row(
                    spacing=6,
                    wrap=True,
                    controls=[
                        make_chip("💡 Explain concept", "Explain the concept behind this assessment question"),
                        make_chip("🔍 Similar example", "Walk through a similar example illustrating this principle"),
                        make_chip("📖 Key rules", "What are the key rules to remember for this question?"),
                        make_chip("🤔 How to approach?", "How should I structure my reasoning for this problem?"),
                    ],
                )
            )
        else:
            chips_col.controls.append(
                ft.Row(
                    spacing=6,
                    wrap=True,
                    controls=[
                        make_chip("💡 Explain simply", "Explain this simply"),
                        make_chip("🔍 Real-world analogy", "Give me a real-world example"),
                        make_chip("📝 Key takeaways", "Summarize key takeaways"),
                        make_chip("❓ Quiz me", "Quiz me on this lesson"),
                    ],
                )
            )

    _refresh_chips()

    def clear_chat(e=None):
        clear_course_history(course_id)
        messages_col.controls.clear()
        welcome_text = (
            f"✨ Chat history cleared.\n\n"
            f"How can I help you master **{current_context['lesson_title']}** today?"
        )
        messages_col.controls.append(_bubble(welcome_text, is_user=False))
        page.update()

    # Dynamic Module Context Updater Hook (called when learner switches lessons in course_page)
    def update_module_context(new_lesson_data: Dict[str, Any], new_module_title: str, new_is_assessment: bool):
        current_context["lesson_data"] = new_lesson_data or {}
        new_title = (new_lesson_data or {}).get("title", "Current Lesson")
        current_context["lesson_title"] = new_title
        current_context["module_title"] = new_module_title or "Module"
        current_context["is_assessment"] = new_is_assessment

        header_subtitle_text.value = new_title
        assessment_badge.visible = new_is_assessment
        _refresh_chips()

        # Add unobtrusive context switch badge to chat flow
        mode_str = " (Assessment Mode)" if new_is_assessment else ""
        messages_col.controls.append(
            _render_context_switch_pill(f"Context: {new_title}{mode_str}")
        )
        page.update()

    if controller:
        controller.update_module_context = update_module_context

    # Collapsible / Minimized dock state for Mobile
    minimized_pill = ft.Container(
        visible=False,
        bgcolor=accent,
        border_radius=ft.BorderRadius.all(24),
        padding=ft.Padding.symmetric(horizontal=16, vertical=10),
        shadow=ft.BoxShadow(blur_radius=12, color=ft.Colors.with_opacity(0.25, ft.Colors.BLACK), offset=ft.Offset(0, 4)),
        content=ft.Row(
            spacing=8,
            tight=True,
            controls=[
                ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=16, color=ft.Colors.WHITE),
                ft.Text("Nu-AI Tutor · Tap to expand", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
            ],
        ),
        ink=True,
    )

    def toggle_minimize(e=None):
        current_context["is_minimized"] = not current_context["is_minimized"]
        if current_context["is_minimized"]:
            main_window.visible = False
            minimized_pill.visible = True
        else:
            main_window.visible = True
            minimized_pill.visible = False
        page.update()

    minimized_pill.on_click = toggle_minimize

    container = target_container if target_container is not None else ft.Container()

    # Header Bar matching reference aesthetics (Model Pill Badge + Socratic status)
    header_content = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Row(
                spacing=8,
                tight=True,
                controls=[
                    # Model pill badge
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                        border_radius=ft.BorderRadius.all(12),
                        bgcolor=ft.Colors.with_opacity(0.10, accent),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.20, accent)),
                        content=ft.Row(
                            spacing=5,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=13, color=accent),
                                ft.Text("Nu-AI Tutor", size=11.5, weight=ft.FontWeight.W_800, color=accent),
                            ],
                        ),
                    ),
                    assessment_badge,
                ],
            ),
            ft.Row(
                spacing=0,
                tight=True,
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.DELETE_SWEEP_OUTLINED,
                        icon_size=17,
                        icon_color=ft.Colors.GREY_500,
                        tooltip="Clear conversation",
                        style=ft.ButtonStyle(padding=ft.Padding.all(4)),
                        on_click=clear_chat,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED,
                        icon_size=18,
                        icon_color=ft.Colors.GREY_500,
                        tooltip="Minimize",
                        visible=is_mobile,
                        style=ft.ButtonStyle(padding=ft.Padding.all(4)),
                        on_click=toggle_minimize,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE_ROUNDED,
                        icon_size=18,
                        icon_color=ft.Colors.GREY_500,
                        tooltip="Close AI Tutor",
                        style=ft.ButtonStyle(padding=ft.Padding.all(4)),
                        on_click=on_close,
                    ),
                ],
            ),
        ],
    )

    if not is_mobile:
        # =========================================================
        # DESKTOP: Sleek Right-Hand Companion Sidebar / Dock
        # =========================================================
        container.width = 380
        container.expand = True
        container.bgcolor = card_bg
        container.border = ft.Border.only(
            left=ft.BorderSide(1, ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE))
        )
        container.padding = 0
        container.margin = 0
        container.shadow = None
        container.left = None
        container.right = None
        container.top = None
        container.bottom = None
        container.alignment = None

        container.content = ft.Column(
            spacing=0,
            expand=True,
            controls=[
                # Top header with lesson context
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                    bgcolor=card_bg,
                    border=ft.Border.only(
                        bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE))
                    ),
                    content=ft.Column(
                        spacing=6,
                        tight=True,
                        controls=[
                            header_content,
                            ft.Row(
                                spacing=6,
                                tight=True,
                                controls=[
                                    ft.Icon(ft.Icons.AUTO_STORIES_ROUNDED, size=13, color=accent),
                                    header_subtitle_text,
                                ],
                            ),
                        ],
                    ),
                ),
                # Quick prompt chips
                ft.Container(
                    padding=ft.Padding.only(left=14, right=14, top=10, bottom=6),
                    content=chips_col,
                ),
                # Message list
                ft.Container(
                    expand=True,
                    padding=ft.Padding.symmetric(horizontal=14, vertical=6),
                    content=messages_col,
                ),
                # Typing indicator
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=16, vertical=4),
                    content=typing_indicator,
                ),
                # Input composer footer
                ft.Container(
                    padding=ft.Padding.all(12),
                    border=ft.Border.only(
                        top=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE))
                    ),
                    bgcolor=card_bg,
                    content=ft.Row(
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            input_field,
                            send_btn,
                        ],
                    ),
                ),
            ],
        )

    else:
        # =========================================================
        # MOBILE: Non-intrusive Collapsible Bottom Sheet / Dock
        # =========================================================
        main_window = ft.Container(
            height=win_height,
            bgcolor=card_bg,
            border_radius=ft.BorderRadius.all(16),
            border=ft.Border.all(1.2, ft.Colors.with_opacity(0.18, accent)),
            padding=ft.Padding.all(12),
            shadow=ft.BoxShadow(
                blur_radius=28,
                color=ft.Colors.with_opacity(0.25, ft.Colors.BLACK),
                offset=ft.Offset(0, 8),
            ),
            content=ft.Column(
                spacing=6,
                expand=True,
                controls=[
                    ft.Column(
                        spacing=4,
                        tight=True,
                        controls=[
                            header_content,
                            ft.Row(
                                spacing=6,
                                tight=True,
                                controls=[
                                    ft.Icon(ft.Icons.AUTO_STORIES_ROUNDED, size=13, color=accent),
                                    header_subtitle_text,
                                ],
                            ),
                        ],
                    ),
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    chips_col,
                    ft.Container(
                        expand=True,
                        content=messages_col,
                    ),
                    typing_indicator,
                    ft.Row(
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            input_field,
                            send_btn,
                        ],
                    ),
                ],
            ),
        )

        container.left = 10
        container.right = 10
        container.bottom = 10
        container.top = None
        container.width = None
        container.expand = False
        container.alignment = None
        container.shadow = None
        container.border = None
        container.content = ft.Column(
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.END,
            controls=[
                minimized_pill,
                main_window,
            ],
        )

    return container
