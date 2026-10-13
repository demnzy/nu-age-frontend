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


AI_TUTOR_MOBILE_WIDTH = 400


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

    win_width = min(360, max(280, page_w - 24)) if is_mobile else AI_TUTOR_MOBILE_WIDTH
    win_height = max(240, min(int(page_h * 0.49), 420)) if is_mobile else 540

    # Scrollable message list with auto-scroll
    messages_col = ft.Column(
        spacing=8,
        scroll=ft.ScrollMode.AUTO,
        auto_scroll=True,
        expand=True,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    # Context subtitle header label (module · lesson with ellipsis truncation)
    initial_sub = (
        f"{current_context['module_title']} · {current_context['lesson_title']}"
        if current_context.get("module_title")
        else current_context["lesson_title"]
    )
    header_subtitle_text = ft.Text(
        initial_sub,
        size=11,
        color=ft.Colors.ON_SURFACE_VARIANT,
        no_wrap=True,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
        tooltip=initial_sub,
        expand=True,
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

    def _get_max_user_bubble_width() -> float:
        w = getattr(page, "width", None) or 360
        if is_mobile:
            return max(180, min(int(w * 0.80), int(w - 56)))
        return 320

    # Message bubble renderer matching reference image aesthetics
    def _bubble(text: str, is_user: bool, can_retry: bool = False, query_for_retry: str = "") -> ft.Control:
        if is_user:
            is_long = len(text.strip()) > 28 or "\n" in text
            user_bubble_width = _get_max_user_bubble_width() if is_long else None
            return ft.Row(
                alignment=ft.MainAxisAlignment.END,
                controls=[
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                        border_radius=ft.BorderRadius.all(12),
                        bgcolor=accent,
                        width=user_bubble_width,
                        content=ft.Text(
                            text,
                            size=12.5,
                            color=ft.Colors.WHITE,
                            selectable=True,
                            no_wrap=False,
                        ),
                    ),
                ],
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
                )
            ],
        )

        return ft.Column(
            spacing=3,
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
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
                ),
                action_row,
            ],
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
        hint_text="Ask a doubt about this lesson...",
        text_size=12.5,
        border_radius=ft.BorderRadius.all(20),
        content_padding=ft.Padding.symmetric(horizontal=14, vertical=10),
        autofocus=not is_mobile,
        shift_enter=True,
        min_lines=1,
        max_lines=3,
        filled=False,
        border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
        focused_border_color=accent,
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
        try:
            await messages_col.scroll_to(offset=-1, duration=200)
        except Exception:
            pass

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

        async def _scroll_down_reply():
            await asyncio.sleep(0.05)
            try:
                await messages_col.scroll_to(offset=-1, duration=250)
            except Exception:
                pass
        asyncio.create_task(_scroll_down_reply())

    def send_query(text: str):
        clean_text = text.strip()
        if not clean_text or current_context["is_generating"]:
            return

        # Persist user turn to session
        append_course_message(course_id, "user", clean_text, current_context["lesson_title"])
        messages_col.controls.append(_bubble(clean_text, is_user=True))
        input_field.value = ""
        page.update()

        async def _scroll_down():
            await asyncio.sleep(0.05)
            try:
                await messages_col.scroll_to(offset=-1, duration=250)
            except Exception:
                pass
        asyncio.create_task(_scroll_down())

        page.run_task(_respond, clean_text)

    def on_send_click(e):
        send_query(input_field.value)

    input_field.on_submit = on_send_click

    send_btn = ft.IconButton(
        icon=ft.Icons.SEND_ROUNDED,
        icon_color=accent,
        icon_size=18,
        tooltip="Send Question",
        style=ft.ButtonStyle(padding=ft.Padding.all(6)),
        on_click=on_send_click,
    )

    # Suggestion prompt chips container (swaps in assessment mode)
    chips_col = ft.Column(spacing=6)

    def _refresh_chips():
        chips_col.controls.clear()
        is_as = current_context["is_assessment"]

        def make_chip(label: str, query: str):
            chip_color = ft.Colors.GREEN_700 if not is_dark else accent
            return ft.Container(
                padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                border_radius=ft.BorderRadius.all(12),
                bgcolor=ft.Colors.with_opacity(0.08, chip_color),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.20, chip_color)),
                ink=True,
                on_click=lambda _: send_query(query),
                content=ft.Text(label, size=11, weight=ft.FontWeight.W_600, color=chip_color),
            )

        if is_as:
            chips_col.controls.extend([
                ft.Row(
                    spacing=6,
                    scroll=ft.ScrollMode.AUTO,
                    controls=[
                        make_chip("💡 Explain concept", "Explain the concept behind this assessment question"),
                        make_chip("🔍 Similar example", "Walk through a similar example illustrating this principle"),
                    ],
                ),
                ft.Row(
                    spacing=6,
                    scroll=ft.ScrollMode.AUTO,
                    controls=[
                        make_chip("📖 Key rules", "What are the key rules to remember for this question?"),
                        make_chip("🤔 How to approach?", "How should I structure my reasoning for this problem?"),
                    ],
                ),
            ])
        else:
            chips_col.controls.extend([
                ft.Row(
                    spacing=6,
                    scroll=ft.ScrollMode.AUTO,
                    controls=[
                        make_chip("💡 Explain simply", "Explain this simply"),
                        make_chip("🔍 Real-world analogy", "Give me a real-world example"),
                    ],
                ),
                ft.Row(
                    spacing=6,
                    scroll=ft.ScrollMode.AUTO,
                    controls=[
                        make_chip("📝 Key takeaways", "Summarize key takeaways"),
                        make_chip("❓ Quiz me", "Quiz me on this lesson"),
                    ],
                ),
            ])

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

        sub_title = f"{new_module_title} · {new_title}" if new_module_title else new_title
        header_subtitle_text.value = sub_title
        header_subtitle_text.tooltip = sub_title
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
            if is_mobile:
                container.top = None
                container.bottom = 10
                container.left = 10
                container.right = 10
                container_col.expand = False
                container_col.tight = True
        else:
            is_fs = current_context.get("is_fullscreen", False)
            if is_mobile:
                if is_fs:
                    container.top = 8
                    container.bottom = 8
                    container.left = 8
                    container.right = 8
                    container_col.expand = True
                    container_col.tight = False
                    main_window.height = None
                    main_window.expand = True
                else:
                    container.top = None
                    container.bottom = 10
                    container.left = 10
                    container.right = 10
                    container_col.expand = False
                    container_col.tight = True
                    main_window.expand = False
                    main_window.height = win_height
            main_window.visible = True
            minimized_pill.visible = False
        page.update()

    minimized_pill.on_click = toggle_minimize

    fullscreen_btn = ft.IconButton(
        icon=ft.Icons.FULLSCREEN_ROUNDED,
        icon_size=18,
        icon_color=ft.Colors.GREY_600,
        tooltip="Full Screen",
        style=ft.ButtonStyle(padding=ft.Padding.all(4)),
        visible=is_mobile,
    )

    def toggle_fullscreen(e=None):
        current_context["is_fullscreen"] = not current_context.get("is_fullscreen", False)
        is_fs = current_context["is_fullscreen"]
        fullscreen_btn.icon = ft.Icons.FULLSCREEN_EXIT_ROUNDED if is_fs else ft.Icons.FULLSCREEN_ROUNDED
        fullscreen_btn.tooltip = "Exit Full Screen" if is_fs else "Full Screen"

        if is_mobile:
            if is_fs:
                # Grow and fill the entire screen as an overlay within visible screen bounds
                container.top = 8
                container.bottom = 8
                container.left = 8
                container.right = 8
                container_col.expand = True
                container_col.tight = False
                main_window.height = None
                main_window.expand = True
                main_window.border_radius = ft.BorderRadius.all(16)
            else:
                # Easily minimise back to the normal half-screen size
                container.top = None
                container.bottom = 10
                container.left = 10
                container.right = 10
                container_col.expand = False
                container_col.tight = True
                main_window.expand = False
                main_window.height = win_height
                main_window.border_radius = ft.BorderRadius.all(16)
        page.update()

    fullscreen_btn.on_click = toggle_fullscreen

    def handle_close(e=None):
        current_context["is_fullscreen"] = False
        fullscreen_btn.icon = ft.Icons.FULLSCREEN_ROUNDED
        fullscreen_btn.tooltip = "Full Screen"
        if is_mobile:
            container.top = None
            container.bottom = 10
            container.left = 10
            container.right = 10
            container_col.expand = False
            container_col.tight = True
            main_window.expand = False
            main_window.height = win_height
            main_window.border_radius = ft.BorderRadius.all(16)
        if callable(on_close):
            try:
                on_close(e)
            except TypeError:
                on_close()

    container = target_container if target_container is not None else ft.Container()

    # Header Bar matching reference image
    header_content = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Row(
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
                controls=[
                    # Green rounded sparkle icon box matching screenshot
                    ft.Container(
                        padding=ft.Padding.all(6),
                        border_radius=ft.BorderRadius.all(8),
                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.GREEN),
                        content=ft.Icon(
                            ft.Icons.AUTO_AWESOME_ROUNDED,
                            size=16,
                            color=ft.Colors.GREEN_700 if not is_dark else ft.Colors.GREEN,
                        ),
                    ),
                    ft.Column(
                        spacing=2,
                        tight=True,
                        expand=True,
                        controls=[
                            ft.Row(
                                spacing=6,
                                tight=True,
                                controls=[
                                    ft.Text(
                                        "Course AI Assistant",
                                        size=13.5,
                                        weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.ON_SURFACE,
                                    ),
                                ],
                            ),
                            ft.Row(
                                controls=[header_subtitle_text],
                            ),
                        ],
                    ),
                ],
            ),
            ft.Row(
                spacing=2,
                tight=True,
                controls=[
                    fullscreen_btn,
                    ft.IconButton(
                        icon=ft.Icons.CLOSE_ROUNDED,
                        icon_size=18,
                        icon_color=ft.Colors.GREY_600,
                        tooltip="Close",
                        style=ft.ButtonStyle(padding=ft.Padding.all(4)),
                        on_click=handle_close,
                    ),
                ],
            ),
        ],
    )

    if not is_mobile:
        # =========================================================
        # DESKTOP: Sleek Raised Right-Hand Companion Sidebar / Dock
        # =========================================================
        container.width = AI_TUTOR_MOBILE_WIDTH
        container.expand = False
        container.bgcolor = card_bg
        container.clip_behavior = ft.ClipBehavior.ANTI_ALIAS
        container.border_radius = ft.BorderRadius.all(16)
        container.border = ft.Border.all(
            1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)
        )
        container.shadow = ft.BoxShadow(
            blur_radius=20,
            spread_radius=0,
            color=ft.Colors.with_opacity(0.14, ft.Colors.BLACK),
            offset=ft.Offset(0, 4),
        )
        container.animate = ft.Animation(duration=280, curve=ft.AnimationCurve.EASE_OUT_CUBIC)
        container.animate_opacity = ft.Animation(duration=220, curve=ft.AnimationCurve.EASE_IN_OUT)
        container.padding = 0
        container.margin = ft.Padding.only(right=12, top=6, bottom=12)
        container.left = None
        container.right = None
        container.top = None
        container.bottom = None
        container.alignment = None

        container.content = ft.Column(
            spacing=0,
            expand=True,
            controls=[
                # Top header with lesson context matching screenshot
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                    border=ft.Border.only(
                        bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE))
                    ),
                    content=header_content,
                ),
                # Quick prompt chips
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                    content=chips_col,
                ),
                # Message list
                ft.Container(
                    expand=True,
                    padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                    content=messages_col,
                ),
                # Typing indicator
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=2),
                    content=typing_indicator,
                ),
                # Input composer footer
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                    border=ft.Border.only(
                        top=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE))
                    ),
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
            animate=ft.Animation(duration=280, curve=ft.AnimationCurve.EASE_OUT_CUBIC),
            content=ft.Column(
                spacing=6,
                expand=True,
                controls=[
                    header_content,
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

        container_col = ft.Column(
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.END,
            controls=[
                minimized_pill,
                main_window,
            ],
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
        container.animate_position = ft.Animation(duration=280, curve=ft.AnimationCurve.EASE_OUT_CUBIC)
        container.content = container_col

    return container
