"""
src/components/course_tabs.py

4-Tab Focused Architecture for Nu-Age Course Player:
1. Learn:    Primary active lesson player & media viewer.
2. Practice: Course/Module assessments, quizzes, flashcards, and labs.
3. Discuss:  Module & Course discussion channel powered by Nu-Chat backend.
4. Progress: Comprehensive visual mastery breakdown, module checkmarks, certificate.
"""

import asyncio
import uuid
import flet as ft
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone
from src.requests.chats import (
    get_user_channels,
    get_channel_messages,
    send_channel_message_api,
)
from src.requests.discussions import (
    get_course_discussions_api,
    create_course_discussion_api,
    get_discussion_details_api,
    create_discussion_reply_api,
    toggle_discussion_upvote_api,
    toggle_reply_upvote_api,
    toggle_resolve_discussion_api,
    report_discussion_api,
)
from src.requests.Courses import generate_course_certificate
from src.utils.file_opener import show_page_snackbar


async def _get_auth_token(page: ft.Page) -> Optional[str]:
    """Retrieve auth token safely and without deprecation warnings."""
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


def build_course_tab_bar(
    active_tab_index: int,
    on_tab_change: Callable[[int], None],
    on_open_ai_assistant: Optional[Callable] = None,
    is_dark: bool = False,
    page_width: Optional[float] = None,
) -> ft.Container:
    """Renders the top 4-tab bar navigation + AI Tutor launcher for the course player."""
    accent = ft.Colors.PRIMARY
    card_bg = ft.Colors.SURFACE if is_dark else "#FFFFFF"

    tabs_def = [
        ("Learn", ft.Icons.AUTO_STORIES_ROUNDED, 0),
        ("Practice", ft.Icons.PSYCHOLOGY_ROUNDED, 1),
        ("Discuss", ft.Icons.FORUM_ROUNDED, 2),
    ]

    is_narrow = (page_width or 800) < 500
    tab_padding = ft.Padding.symmetric(horizontal=9 if is_narrow else 12, vertical=7 if is_narrow else 8)

    buttons = []
    for label, icon, idx in tabs_def:
        is_selected = idx == active_tab_index
        def _make_click(i):
            return lambda _: on_tab_change(i)

        buttons.append(
            ft.Container(
                padding=tab_padding,
                border_radius=ft.BorderRadius.all(12),
                bgcolor=ft.Colors.with_opacity(0.12 if is_selected else 0.0, accent),
                border=ft.Border.all(
                    1.2,
                    accent if is_selected else ft.Colors.TRANSPARENT,
                ),
                ink=True,
                on_click=_make_click(idx),
                content=ft.Row(
                    spacing=5 if is_narrow else 6,
                    tight=True,
                    controls=[
                        ft.Icon(
                            icon,
                            size=14 if is_narrow else 15,
                            color=accent if is_selected else ft.Colors.GREY_500,
                        ),
                        ft.Text(
                            label,
                            size=11.5 if is_narrow else 12,
                            weight=ft.FontWeight.W_800 if is_selected else ft.FontWeight.W_600,
                            color=accent if is_selected else ft.Colors.ON_SURFACE,
                        ),
                    ],
                ),
            )
        )

    if callable(on_open_ai_assistant):
        def _on_ai_click(e):
            if callable(on_open_ai_assistant):
                try:
                    on_open_ai_assistant(e)
                except TypeError:
                    on_open_ai_assistant()

        ai_color = ft.Colors.DEEP_PURPLE_500 if not is_dark else ft.Colors.DEEP_PURPLE_300
        ai_btn = ft.Container(
            padding=tab_padding,
            border_radius=ft.BorderRadius.all(12),
            bgcolor=ft.Colors.with_opacity(0.10, ai_color),
            border=ft.Border.all(
                1.2,
                ft.Colors.with_opacity(0.30, ai_color),
            ),
            ink=True,
            on_click=_on_ai_click,
            tooltip="Open AI Doubt Assistant",
            content=ft.Row(
                spacing=5 if is_narrow else 6,
                tight=True,
                controls=[
                    ft.Icon(
                        ft.Icons.AUTO_AWESOME_ROUNDED,
                        size=14 if is_narrow else 15,
                        color=ai_color,
                    ),
                    ft.Text(
                        "AI Tutor" if (page_width or 800) >= 500 else "AI",
                        size=11.5 if is_narrow else 12,
                        weight=ft.FontWeight.W_700,
                        color=ai_color,
                    ),
                ],
            ),
        )
        buttons.append(ai_btn)

    return ft.Container(
        bgcolor=card_bg,
        border_radius=ft.BorderRadius.all(14),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
        padding=ft.Padding.symmetric(horizontal=8, vertical=6),
        content=ft.Row(
            spacing=5 if is_narrow else 6,
            alignment=ft.MainAxisAlignment.START,
            wrap=True,
            controls=buttons,
        ),
    )


def build_practice_tab_view(
    course_data: Dict[str, Any],
    page: ft.Page,
    on_jump_to_lesson: Callable[[int, int], None],
) -> ft.Container:
    """Builds the Practice Hub: assessments, quizzes, flashcards across modules."""
    is_dark = getattr(page, "theme_mode", None) == ft.ThemeMode.DARK
    accent = ft.Colors.PRIMARY

    practice_tiles = []
    modules = course_data.get("modules", [])

    for m_idx, mod in enumerate(modules):
        mod_title = mod.get("title", f"Module {m_idx + 1}")
        for l_idx, les in enumerate(mod.get("lessons", [])):
            l_type = les.get("type", "")
            if l_type in ("assessment", "cards", "cloze", "sequencer", "code_lab", "scenario"):
                is_done = les.get("is_done", False)
                is_unlocked = les.get("is_unlocked", True)

                def _jump(mi=m_idx, li=l_idx):
                    return lambda _: on_jump_to_lesson(mi, li)

                type_label = {
                    "assessment": "Quiz / Exam",
                    "cards": "Flashcards Deck",
                    "cloze": "Fill In Blanks",
                    "code_lab": "Coding Lab",
                    "sequencer": "Order Sequencer",
                    "scenario": "Scenario Exercise",
                }.get(l_type, "Interactive Lab")

                practice_tiles.append(
                    ft.Container(
                        padding=ft.Padding.all(12),
                        border_radius=ft.BorderRadius.all(14),
                        bgcolor=ft.Colors.SURFACE,
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                        ink=is_unlocked,
                        on_click=_jump() if is_unlocked else None,
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=8,
                            controls=[
                                ft.Row(
                                    spacing=10,
                                    expand=True,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.Container(
                                            padding=ft.Padding.all(8),
                                            border_radius=ft.BorderRadius.all(10),
                                            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.GREEN_400 if is_done else accent),
                                            content=ft.Icon(
                                                ft.Icons.CHECK_CIRCLE_ROUNDED if is_done else ft.Icons.FITNESS_CENTER_ROUNDED,
                                                color=ft.Colors.GREEN_400 if is_done else accent,
                                                size=18,
                                            ),
                                        ),
                                        ft.Column(
                                            spacing=2,
                                            expand=True,
                                            controls=[
                                                ft.Text(
                                                    les.get("title", "Practice Exercise"),
                                                    size=13,
                                                    weight=ft.FontWeight.W_700,
                                                    max_lines=2,
                                                    overflow=ft.TextOverflow.ELLIPSIS,
                                                ),
                                                ft.Text(
                                                    f"{mod_title} · {type_label}",
                                                    size=10.5,
                                                    color=ft.Colors.GREY_500,
                                                    max_lines=1,
                                                    overflow=ft.TextOverflow.ELLIPSIS,
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                ft.FilledButton(
                                    content=ft.Text("Review" if is_done else "Practice", size=11.5, weight=ft.FontWeight.W_700),
                                    disabled=not is_unlocked,
                                    on_click=_jump() if is_unlocked else None,
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=8),
                                        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                                    ),
                                ),
                            ],
                        ),
                    )
                )

    if not practice_tiles:
        practice_tiles.append(
            ft.Container(
                padding=ft.Padding.all(24),
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=6,
                    controls=[
                        ft.Icon(ft.Icons.EMOJI_EVENTS_ROUNDED, size=40, color=ft.Colors.GREY_400),
                        ft.Text("No assessments or flashcards in this course yet.", size=14, weight=ft.FontWeight.W_700, text_align=ft.TextAlign.CENTER),
                        ft.Text("Complete the reading and video lessons in the Learn tab!", size=12, color=ft.Colors.GREY_500, text_align=ft.TextAlign.CENTER),
                    ],
                ),
            )
        )

    return ft.Container(
        padding=ft.Padding.symmetric(vertical=8),
        content=ft.Column(
            spacing=12,
            controls=[
                ft.Row(
                    [
                        ft.Icon(ft.Icons.FITNESS_CENTER_ROUNDED, size=16, color=accent),
                        ft.Text(
                            "Course Practice & Knowledge Checks",
                            size=14.5,
                            weight=ft.FontWeight.W_800,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            expand=True,
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Column(spacing=10, controls=practice_tiles),
            ],
        ),
    )


def build_discuss_tab_view(
    course_id: str,
    course_title: str,
    page: ft.Page,
    modules: Optional[List[Dict[str, Any]]] = None,
    current_module_id: Optional[str] = None,
    is_offline: bool = False,
) -> ft.Container:
    """
    Builds the Course Discussion Board & Q&A Forum:
    Structured course-level threads, module-anchored filtering, search,
    category filtering, upvoting, reporting, threaded replies with instructor
    endorsements, and contextual topic composers.
    """
    is_dark = getattr(page, "theme_mode", None) == ft.ThemeMode.DARK
    accent = ft.Colors.PRIMARY
    current_user = (
        (hasattr(page, "session") and hasattr(page.session, "store") and (page.session.store.get("current_user") or page.session.store.get("user")))
        or {}
    )
    my_user_id = str(current_user.get("id") or current_user.get("user_id") or "").strip().lower()
    my_role = str(current_user.get("role", "student")).lower()
    is_instructor = my_role in ("teacher", "admin", "platform_admin")

    module_list = [m for m in (modules or []) if isinstance(m, dict)]
    mod_titles = {str(m.get("id")): m.get("title", f"Module {i+1}") for i, m in enumerate(module_list) if m.get("id")}

    # State
    state = {
        "active_category": "all",
        "active_module_id": "all",
        "search_query": "",
        "discussions": [],
        "selected_discussion": None,
        "is_composer_open": False,
        "is_loading": True,
        "is_publishing": False,
        "is_submitting_reply": False,
        "selected_new_category": "question",
        "selected_new_module_id": current_module_id or "all",
    }

    # Main dynamic container socket
    content_socket = ft.Column(spacing=12, expand=True)

    def _format_date(dt_str: Optional[str]) -> str:
        if not dt_str:
            return ""
        if "Just now" in dt_str or "ago" in dt_str:
            return dt_str
        try:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            return dt.strftime("%b %d, %H:%M")
        except Exception:
            return dt_str[:10] if len(dt_str) >= 10 else dt_str

    def _get_category_badge(cat: str, is_resolved: bool = False) -> ft.Row:
        cat_lower = (cat or "question").lower()
        if is_resolved:
            return ft.Row(
                spacing=4,
                tight=True,
                controls=[
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                        border_radius=ft.BorderRadius.all(10),
                        bgcolor=ft.Colors.with_opacity(0.14, ft.Colors.GREEN),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.GREEN)),
                        content=ft.Row(
                            spacing=4,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=12, color=ft.Colors.GREEN_700),
                                ft.Text("SOLVED", size=10, weight=ft.FontWeight.W_800, color=ft.Colors.GREEN_700),
                            ],
                        ),
                    )
                ],
            )

        cat_styles = {
            "question": (ft.Icons.HELP_OUTLINE_ROUNDED, "QUESTION", ft.Colors.BLUE_600),
            "idea": (ft.Icons.LIGHTBULB_ROUNDED, "IDEA", ft.Colors.AMBER_800),
            "discussion": (ft.Icons.FORUM_ROUNDED, "DISCUSSION", ft.Colors.DEEP_PURPLE_500),
            "resource": (ft.Icons.MENU_BOOK_ROUNDED, "RESOURCE", ft.Colors.TEAL_600),
        }
        icon, label, color = cat_styles.get(cat_lower, (ft.Icons.FORUM_ROUNDED, cat_lower.upper(), accent))

        return ft.Row(
            spacing=4,
            tight=True,
            controls=[
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=ft.BorderRadius.all(10),
                    bgcolor=ft.Colors.with_opacity(0.12, color),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.25, color)),
                    content=ft.Row(
                        spacing=4,
                        tight=True,
                        controls=[
                            ft.Icon(icon, size=12, color=color),
                            ft.Text(label, size=10, weight=ft.FontWeight.W_800, color=color),
                        ],
                    ),
                )
            ],
        )

    def _render_author_chip(author: Dict[str, Any]) -> ft.Row:
        author_name = author.get("name") or "Student"
        role = str(author.get("role") or "student").lower()
        is_staff = role in ("teacher", "admin", "platform_admin")
        initial = (author_name[0] if author_name else "S").upper()

        return ft.Row(
            spacing=6,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=22,
                    height=22,
                    border_radius=ft.BorderRadius.all(11),
                    bgcolor=ft.Colors.with_opacity(0.15, accent),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text(initial, size=10, weight=ft.FontWeight.W_800, color=accent),
                ),
                ft.Text(author_name, size=11.5, weight=ft.FontWeight.W_700, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                ft.Container(
                    visible=is_staff,
                    padding=ft.Padding.symmetric(horizontal=5, vertical=1),
                    border_radius=ft.BorderRadius.all(6),
                    bgcolor=ft.Colors.with_opacity(0.15, accent),
                    content=ft.Text("Instructor", size=9, weight=ft.FontWeight.W_800, color=accent),
                ),
            ],
        )

    async def _load_discussions():
        state["is_loading"] = True
        _render_view()
        token = await _get_auth_token(page) or ""
        target_mod_id = state["active_module_id"] if state["active_module_id"] != "all" else None
        res = await get_course_discussions_api(
            token=token,
            course_id=course_id,
            module_id=target_mod_id,
            category=state["active_category"],
            search=state["search_query"],
        )
        state["discussions"] = res.get("discussions", []) if isinstance(res, dict) else []
        state["is_loading"] = False
        _render_view()

    async def _on_upvote_post(disc_item: Dict[str, Any], e=None):
        token = await _get_auth_token(page) or ""
        # Optimistic update
        has_upvoted = disc_item.get("has_upvoted", False)
        disc_item["has_upvoted"] = not has_upvoted
        disc_item["upvotes_count"] = max(0, disc_item.get("upvotes_count", 0) + (-1 if has_upvoted else 1))
        _render_view()
        await toggle_discussion_upvote_api(token, disc_item["id"])

    async def _on_upvote_reply(reply_item: Dict[str, Any], e=None):
        token = await _get_auth_token(page) or ""
        has_upvoted = reply_item.get("has_upvoted", False)
        reply_item["has_upvoted"] = not has_upvoted
        reply_item["upvotes_count"] = max(0, reply_item.get("upvotes_count", 0) + (-1 if has_upvoted else 1))
        _render_view()
        await toggle_reply_upvote_api(token, reply_item["id"])

    async def _on_toggle_resolve(disc_item: Dict[str, Any], e=None):
        token = await _get_auth_token(page) or ""
        disc_item["is_resolved"] = not disc_item.get("is_resolved", False)
        _render_view()
        await toggle_resolve_discussion_api(token, disc_item["id"])

    def _open_report_dialog(d: Dict[str, Any]):
        selected_reason = {"val": "Inappropriate content"}
        reasons = [
            "Inappropriate content",
            "Spam or promotion",
            "Off-topic or irrelevant",
            "Harassment or abusive language",
        ]
        
        reason_radios = []
        for r in reasons:
            def _make_choose(val):
                return lambda e: _set_reason(val)
            reason_radios.append(
                ft.ListTile(
                    title=ft.Text(r, size=12.5),
                    leading=ft.Radio(value=r),
                    content_padding=ft.Padding.symmetric(horizontal=4, vertical=0),
                    on_click=_make_choose(r),
                )
            )

        rg = ft.RadioGroup(
            value=selected_reason["val"],
            content=ft.Column(spacing=2, tight=True, controls=reason_radios),
            on_change=lambda e: _set_reason(e.control.value),
        )

        def _set_reason(v):
            selected_reason["val"] = v
            rg.value = v
            page.update()

        dlg_ref = [None]

        async def _submit_report(_):
            token = await _get_auth_token(page) or ""
            if dlg_ref[0]:
                dlg_ref[0].open = False
                page.update()
            success = await report_discussion_api(token, d["id"], selected_reason["val"])
            if success:
                show_page_snackbar(
                    page,
                    ft.SnackBar(
                        content=ft.Text("Post reported. Our moderation team has been notified.", color=ft.Colors.WHITE),
                        bgcolor=ft.Colors.GREEN_700,
                    ),
                )
            else:
                show_page_snackbar(
                    page,
                    ft.SnackBar(
                        content=ft.Text("Unable to submit report. Please try again later.", color=ft.Colors.WHITE),
                        bgcolor=ft.Colors.RED_700,
                    ),
                )

        def _close_report_dialog():
            if dlg_ref[0]:
                dlg_ref[0].open = False
                page.update()

        dlg = ft.AlertDialog(
            shape=ft.RoundedRectangleBorder(radius=14),
            title=ft.Row(
                spacing=8,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.REPORT_PROBLEM_OUTLINED, color=ft.Colors.RED_500, size=20),
                    ft.Text("Report Topic", size=15, weight=ft.FontWeight.W_700),
                ],
            ),
            content=ft.Container(
                width=min(360, max(240, int(page.width - 40))) if page.width else 340,
                content=ft.Column(
                    spacing=10,
                    tight=True,
                    controls=[
                        ft.Text(
                            "Why are you reporting this discussion topic?",
                            size=12,
                            color=ft.Colors.GREY_600,
                        ),
                        rg,
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: _close_report_dialog()),
                ft.ElevatedButton(
                    "Submit Report",
                    bgcolor=ft.Colors.RED_600,
                    color=ft.Colors.WHITE,
                    on_click=lambda e: page.run_task(_submit_report),
                ),
            ],
        )
        dlg_ref[0] = dlg
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    async def _submit_new_topic(title: str, content: str, cat: str, mod_id: Optional[str] = None):
        try:
            if not title.strip() or not content.strip():
                return
            token = await _get_auth_token(page) or ""
            target_mod_id = None if (not mod_id or mod_id == "all") else mod_id
            res = await create_course_discussion_api(
                token=token,
                course_id=course_id,
                title=title.strip(),
                content=content.strip(),
                category=cat,
                module_id=target_mod_id,
            )
            if res:
                existing_ids = {str(d.get("id")) for d in state["discussions"] if d.get("id")}
                if str(res.get("id")) not in existing_ids:
                    state["discussions"].insert(0, res)
            state["is_composer_open"] = False
        finally:
            state["is_publishing"] = False
            _render_view()
            try:
                from src.services.notification_service import sync_learner_notifications
                page.run_task(sync_learner_notifications, page, True)
            except Exception:
                pass

    async def _submit_reply(disc_item: Dict[str, Any], text: str, temp_id: Optional[str] = None):
        try:
            if not text.strip():
                return
            token = await _get_auth_token(page) or ""
            rep = await create_discussion_reply_api(token, disc_item["id"], text.strip(), course_id=course_id)
            if rep:
                replies = list(disc_item.get("replies", []))
                replaced = False
                if temp_id:
                    for idx, r in enumerate(replies):
                        if r.get("id") == temp_id:
                            replies[idx] = rep
                            replaced = True
                            break
                if not replaced:
                    if not any(r.get("id") == rep.get("id") for r in replies):
                        replies.append(rep)

                # Strict deduplication pass
                deduped = []
                seen_ids = set()
                for r in replies:
                    rid = str(r.get("id") or "")
                    if rid and rid in seen_ids:
                        continue
                    if rid:
                        seen_ids.add(rid)
                    deduped.append(r)

                disc_item["replies"] = deduped
                disc_item["replies_count"] = len(deduped)
        finally:
            state["is_submitting_reply"] = False
            _render_view()
            target_col = state.get("thread_replies_col")
            if target_col:
                try:
                    await target_col.scroll_to(offset=-1, duration=250)
                except Exception:
                    pass
            try:
                from src.services.notification_service import sync_learner_notifications
                page.run_task(sync_learner_notifications, page, True)
            except Exception:
                pass

    async def _open_thread_detail(disc_item: Dict[str, Any]):
        state["selected_discussion"] = disc_item
        _render_view()
        token = await _get_auth_token(page) or ""
        full_detail = await get_discussion_details_api(token, disc_item["id"], course_id=course_id)
        if full_detail:
            state["selected_discussion"] = full_detail
            _render_view()

    def _render_thread_card(d: Dict[str, Any]) -> ft.Container:
        is_solved = d.get("is_resolved", False)
        upvoted = d.get("has_upvoted", False)
        upvotes = d.get("upvotes_count", 0)
        replies_count = d.get("replies_count", 0)
        cat_lower = (d.get("category") or "question").lower()

        # Tailored theme accent and semantic indicators per discussion type
        if is_solved:
            theme_color = ft.Colors.GREEN_600
            left_border = ft.BorderSide(4.5, ft.Colors.GREEN_600)
            card_border = ft.Border(
                left=left_border,
                top=ft.BorderSide(1, ft.Colors.with_opacity(0.20, ft.Colors.GREEN_600)),
                right=ft.BorderSide(1, ft.Colors.with_opacity(0.12, ft.Colors.GREEN_600)),
                bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.12, ft.Colors.GREEN_600)),
            )
            card_bg = ft.Colors.with_opacity(0.04, ft.Colors.GREEN_600) if not is_dark else ft.Colors.with_opacity(0.06, ft.Colors.GREEN_900)
            cta_text = "View Solution"
            cta_icon = ft.Icons.CHECK_CIRCLE_ROUNDED
            upvote_label = f"{upvotes} helpful"
            replies_badge = ft.Container(
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                border_radius=ft.BorderRadius.all(8),
                bgcolor=ft.Colors.with_opacity(0.14, ft.Colors.GREEN_600),
                content=ft.Row(
                    spacing=4,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=13, color=ft.Colors.GREEN_700),
                        ft.Text(f"{replies_count} answers • Solved", size=11, weight=ft.FontWeight.W_800, color=ft.Colors.GREEN_700),
                    ],
                ),
            )
        elif cat_lower == "question":
            theme_color = ft.Colors.BLUE_600
            left_border = ft.BorderSide(4.5, ft.Colors.BLUE_600)
            card_border = ft.Border(
                left=left_border,
                top=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                right=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            )
            card_bg = ft.Colors.SURFACE if is_dark else "#FFFFFF"
            cta_text = "Answer Question" if replies_count == 0 else "View Answers"
            cta_icon = ft.Icons.QUESTION_ANSWER_ROUNDED
            upvote_label = f"{upvotes} upvotes"
            if replies_count == 0:
                replies_badge = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=ft.BorderRadius.all(8),
                    bgcolor=ft.Colors.with_opacity(0.14, ft.Colors.ORANGE_800),
                    content=ft.Row(
                        spacing=4,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.HELP_OUTLINE_ROUNDED, size=13, color=ft.Colors.ORANGE_800),
                            ft.Text("Needs Answer", size=11, weight=ft.FontWeight.W_800, color=ft.Colors.ORANGE_800),
                        ],
                    ),
                )
            else:
                replies_badge = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=ft.BorderRadius.all(8),
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.BLUE_600),
                    content=ft.Row(
                        spacing=4,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.QUESTION_ANSWER_OUTLINED, size=13, color=ft.Colors.BLUE_600),
                            ft.Text(f"{replies_count} answers", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.BLUE_600),
                        ],
                    ),
                )
        elif cat_lower == "idea":
            theme_color = ft.Colors.AMBER_800
            left_border = ft.BorderSide(4.5, ft.Colors.AMBER_700)
            card_border = ft.Border(
                left=left_border,
                top=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                right=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            )
            card_bg = ft.Colors.with_opacity(0.02, ft.Colors.AMBER_600) if not is_dark else ft.Colors.SURFACE
            cta_text = "Discuss Idea"
            cta_icon = ft.Icons.LIGHTBULB_OUTLINE_ROUNDED
            upvote_label = f"{upvotes} votes"
            replies_badge = ft.Container(
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                border_radius=ft.BorderRadius.all(8),
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.AMBER_800),
                content=ft.Row(
                    spacing=4,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.FORUM_OUTLINED, size=13, color=ft.Colors.AMBER_900),
                        ft.Text(f"{replies_count} thoughts", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.AMBER_900),
                    ],
                ),
            )
        else: # discussion or resource
            theme_color = ft.Colors.DEEP_PURPLE_500
            left_border = ft.BorderSide(4.5, ft.Colors.DEEP_PURPLE_500)
            card_border = ft.Border(
                left=left_border,
                top=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                right=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            )
            card_bg = ft.Colors.with_opacity(0.02, ft.Colors.DEEP_PURPLE_600) if not is_dark else ft.Colors.SURFACE
            cta_text = "Join Discussion"
            cta_icon = ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED
            upvote_label = f"{upvotes} likes"
            replies_badge = ft.Container(
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                border_radius=ft.BorderRadius.all(8),
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.DEEP_PURPLE_500),
                content=ft.Row(
                    spacing=4,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED, size=13, color=ft.Colors.DEEP_PURPLE_600),
                        ft.Text(f"{replies_count} replies", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.DEEP_PURPLE_600),
                    ],
                ),
            )

        return ft.Container(
            bgcolor=card_bg,
            border_radius=ft.BorderRadius.all(12),
            border=card_border,
            padding=ft.Padding.all(14),
            content=ft.Column(
                spacing=8,
                controls=[
                    # Header: Author & Category & Module Badge
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                        controls=[
                            _render_author_chip(d.get("author") or {}),
                            ft.Row(
                                spacing=6,
                                tight=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Text(_format_date(d.get("created_at")), size=10.5, color=ft.Colors.GREY_500),
                                    *(
                                        [
                                            ft.Container(
                                                padding=ft.Padding.symmetric(horizontal=7, vertical=2),
                                                border_radius=ft.BorderRadius.all(6),
                                                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.TEAL),
                                                content=ft.Row(
                                                    spacing=3,
                                                    tight=True,
                                                    controls=[
                                                        ft.Icon(ft.Icons.VIEW_MODULE_ROUNDED, size=11, color=ft.Colors.TEAL),
                                                        ft.Text(d.get("module_title", "Module"), size=10, weight=ft.FontWeight.W_700, color=ft.Colors.TEAL),
                                                    ],
                                                ),
                                            )
                                        ]
                                        if d.get("module_title")
                                        else []
                                    ),
                                    _get_category_badge(d.get("category", "question"), is_solved),
                                    ft.PopupMenuButton(
                                        icon=ft.Icons.MORE_HORIZ_ROUNDED,
                                        icon_size=16,
                                        tooltip="Options",
                                        items=[
                                            ft.PopupMenuItem(
                                                content=ft.Row(
                                                    spacing=6,
                                                    tight=True,
                                                    controls=[
                                                        ft.Icon(ft.Icons.FLAG_OUTLINED, size=13, color=ft.Colors.RED_400),
                                                        ft.Text("Report Post", size=11.5, color=ft.Colors.RED_400),
                                                    ],
                                                ),
                                                on_click=lambda e, item=d: _open_report_dialog(item),
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                    # Title with contextual accent
                    ft.Text(
                        d.get("title", "Untitled Question"),
                        size=14,
                        weight=ft.FontWeight.W_800,
                        color=theme_color if is_solved else ft.Colors.ON_SURFACE,
                        max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    # Content preview
                    ft.Text(
                        d.get("content", ""),
                        size=12.5,
                        color=ft.Colors.with_opacity(0.85, ft.Colors.ON_SURFACE),
                        max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE)),
                    # Footer actions
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                        controls=[
                            ft.Row(
                                spacing=8,
                                tight=True,
                                controls=[
                                    # Upvote chip
                                    ft.Container(
                                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                                        border_radius=ft.BorderRadius.all(8),
                                        bgcolor=ft.Colors.with_opacity(0.14 if upvoted else 0.05, theme_color if upvoted else ft.Colors.GREY_500),
                                        ink=True,
                                        on_click=lambda e, item=d: page.run_task(_on_upvote_post, item),
                                        content=ft.Row(
                                            spacing=4,
                                            tight=True,
                                            controls=[
                                                ft.Icon(
                                                    ft.Icons.THUMB_UP_ALT_ROUNDED if upvoted else ft.Icons.THUMB_UP_OUTLINED,
                                                    size=13,
                                                    color=theme_color if upvoted else ft.Colors.GREY_500,
                                                ),
                                                ft.Text(
                                                    upvote_label,
                                                    size=11,
                                                    weight=ft.FontWeight.W_700,
                                                    color=theme_color if upvoted else ft.Colors.GREY_500,
                                                ),
                                            ],
                                        ),
                                    ),
                                    # Purpose-specific replies pill
                                    replies_badge,
                                ],
                            ),
                            # Contextual Action CTA
                            ft.TextButton(
                                content=ft.Row(
                                    spacing=4,
                                    tight=True,
                                    controls=[
                                        ft.Text(cta_text, size=11, weight=ft.FontWeight.W_700, color=theme_color),
                                        ft.Icon(cta_icon, size=13, color=theme_color),
                                    ],
                                ),
                                style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=8, vertical=4)),
                                on_click=lambda e, item=d: page.run_task(_open_thread_detail, item),
                            ),
                        ],
                    ),
                ],
            ),
        )

    def _render_composer_card() -> ft.Container:
        cur_cat = state.get("selected_new_category", "question")
        cat_configs = {
            "question": {
                "title": "Ask a Question",
                "subtitle": "Get help from classmates and instructors on course concepts or exercises",
                "icon": ft.Icons.HELP_OUTLINE_ROUNDED,
                "color": ft.Colors.BLUE_600,
                "title_label": "Question",
                "title_hint": "e.g. How does backpropagation calculate weight updates?",
                "content_label": "Details & Context",
                "content_hint": "Explain what you're trying to understand, what you've tried so far, or where you're stuck...",
                "btn_label": "Publish Question",
                "btn_icon": ft.Icons.HELP_OUTLINE_ROUNDED,
            },
            "idea": {
                "title": "Share an Idea & Proposal",
                "subtitle": "Propose study sprints, project collaborations, or curriculum improvements",
                "icon": ft.Icons.LIGHTBULB_ROUNDED,
                "color": ft.Colors.AMBER_800,
                "title_label": "Idea Title",
                "title_hint": "e.g. Weekend study sprint for Module 3 final assignment",
                "content_label": "Proposal & Next Steps",
                "content_hint": "Outline your idea, how peers can participate or benefit, and expected outcomes...",
                "btn_label": "Share Idea",
                "btn_icon": ft.Icons.LIGHTBULB_ROUNDED,
            },
            "discussion": {
                "title": "Start a Discussion",
                "subtitle": "Explore perspectives, debate approaches, or open a conversation topic",
                "icon": ft.Icons.FORUM_ROUNDED,
                "color": ft.Colors.DEEP_PURPLE_500,
                "title_label": "Discussion Topic",
                "title_hint": "e.g. Architectural trade-offs between REST and gRPC in production",
                "content_label": "Topic Overview & Discussion Prompt",
                "content_hint": "Share your thoughts and kick off a conversation with the cohort...",
                "btn_label": "Start Discussion",
                "btn_icon": ft.Icons.FORUM_ROUNDED,
            },
        }
        active_cat_config = cat_configs.get(cur_cat, cat_configs["question"])
        active_theme_col = active_cat_config["color"]

        title_in = ft.TextField(
            label=active_cat_config["title_label"],
            hint_text=active_cat_config["title_hint"],
            text_size=13.5,
            border_radius=ft.BorderRadius.all(8),
            content_padding=ft.Padding.symmetric(horizontal=14, vertical=12),
            border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
            focused_border_color=active_theme_col,
        )
        content_in = ft.TextField(
            label=active_cat_config["content_label"],
            hint_text=active_cat_config["content_hint"],
            text_size=13,
            multiline=True,
            min_lines=4,
            max_lines=8,
            border_radius=ft.BorderRadius.all(8),
            content_padding=ft.Padding.symmetric(horizontal=14, vertical=12),
            border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
            focused_border_color=active_theme_col,
        )

        cat_pills = []
        for cat_val in ("question", "idea", "discussion"):
            cfg = cat_configs[cat_val]
            is_c_sel = (cur_cat == cat_val)
            def _choose_cat(c):
                return lambda _: _set_composer_cat(c)

            cat_pills.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                    border_radius=ft.BorderRadius.all(10),
                    bgcolor=ft.Colors.with_opacity(0.14 if is_c_sel else 0.04, cfg["color"]),
                    border=ft.Border.all(
                        1.5 if is_c_sel else 1.0,
                        cfg["color"] if is_c_sel else ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE),
                    ),
                    ink=True,
                    on_click=_choose_cat(cat_val),
                    content=ft.Row(
                        spacing=6,
                        tight=True,
                        controls=[
                            ft.Icon(cfg["icon"], size=14, color=cfg["color"] if is_c_sel else ft.Colors.GREY_600),
                            ft.Text(
                                "Question" if cat_val == "question" else ("Idea" if cat_val == "idea" else "Discussion"),
                                size=12,
                                weight=ft.FontWeight.W_800 if is_c_sel else ft.FontWeight.W_600,
                                color=cfg["color"] if is_c_sel else ft.Colors.ON_SURFACE,
                            ),
                        ],
                    ),
                )
            )

        def _set_composer_cat(c):
            state["selected_new_category"] = c
            _render_view()

        mod_choices = [("all", "🌐 Entire Course")] + [
            (str(m.get("id")), f"Mod {i+1}: {m.get('title', 'Module')[:18]}")
            for i, m in enumerate(module_list)
            if m.get("id")
        ]
        mod_pills = []
        for m_id, m_label in mod_choices:
            is_m_sel = (state["selected_new_module_id"] == m_id)
            def _choose_mod(mid):
                return lambda _: _set_composer_mod(mid)
            mod_pills.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                    border_radius=ft.BorderRadius.all(6),
                    bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.TEAL) if is_m_sel else (ft.Colors.SURFACE_CONTAINER_HIGHEST if is_dark else "#F1F5F9"),
                    border=ft.Border.all(
                        1.5 if is_m_sel else 1.0,
                        ft.Colors.TEAL if is_m_sel else ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE),
                    ),
                    ink=True,
                    on_click=_choose_mod(m_id),
                    content=ft.Text(
                        m_label,
                        size=11,
                        weight=ft.FontWeight.W_800 if is_m_sel else ft.FontWeight.W_600,
                        color=ft.Colors.TEAL if is_m_sel else ft.Colors.ON_SURFACE,
                    ),
                )
            )

        def _set_composer_mod(mid):
            state["selected_new_module_id"] = mid
            _render_view()

        def _on_publish(e):
            if state.get("is_publishing"):
                return
            if not title_in.value or not title_in.value.strip() or not content_in.value or not content_in.value.strip():
                return
            state["is_publishing"] = True
            _render_view()
            page.run_task(
                _submit_new_topic,
                title_in.value,
                content_in.value,
                state["selected_new_category"],
                state["selected_new_module_id"],
            )

        def _on_cancel(e):
            state["is_composer_open"] = False
            state["is_publishing"] = False
            _render_view()

        if state.get("is_publishing"):
            publish_btn = ft.Container(
                padding=ft.Padding.symmetric(horizontal=18, vertical=10),
                border_radius=ft.BorderRadius.all(8),
                bgcolor=ft.Colors.with_opacity(0.5, active_theme_col),
                content=ft.Row(
                    spacing=8,
                    tight=True,
                    controls=[
                        ft.ProgressRing(width=16, height=16, stroke_width=2.2, color=ft.Colors.WHITE),
                        ft.Text("Publishing...", size=12.5, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                    ],
                ),
            )
        else:
            publish_btn = ft.Container(
                padding=ft.Padding.symmetric(horizontal=18, vertical=10),
                border_radius=ft.BorderRadius.all(8),
                bgcolor=active_theme_col,
                ink=True,
                on_click=_on_publish,
                content=ft.Row(
                    spacing=6,
                    tight=True,
                    controls=[
                        ft.Icon(active_cat_config["btn_icon"], size=16, color=ft.Colors.WHITE),
                        ft.Text(active_cat_config["btn_label"], size=12.5, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                    ],
                ),
            )

        return ft.Container(
            expand=True,
            bgcolor=ft.Colors.SURFACE if is_dark else "#FFFFFF",
            border_radius=ft.BorderRadius.all(12),
            border=ft.Border(
                left=ft.BorderSide(4.5, active_theme_col),
                top=ft.BorderSide(1.2, ft.Colors.with_opacity(0.18, active_theme_col)),
                right=ft.BorderSide(1.2, ft.Colors.with_opacity(0.18, active_theme_col)),
                bottom=ft.BorderSide(1.2, ft.Colors.with_opacity(0.18, active_theme_col)),
            ),
            padding=ft.Padding.symmetric(horizontal=18, vertical=16),
            content=ft.Column(
                spacing=12,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                        controls=[
                            ft.Row(
                                spacing=8,
                                expand=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Container(
                                        padding=ft.Padding.all(8),
                                        border_radius=ft.BorderRadius.all(8),
                                        bgcolor=ft.Colors.with_opacity(0.14, active_theme_col),
                                        content=ft.Icon(active_cat_config["icon"], size=18, color=active_theme_col),
                                    ),
                                    ft.Column(
                                        spacing=1,
                                        expand=True,
                                        controls=[
                                            ft.Text(active_cat_config["title"], size=14, weight=ft.FontWeight.W_800),
                                            ft.Text(active_cat_config["subtitle"], size=11, color=ft.Colors.GREY_500, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                        ],
                                    ),
                                ],
                            ),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE_ROUNDED,
                                tooltip="Cancel & Close",
                                icon_size=18,
                                on_click=_on_cancel,
                            ),
                        ],
                    ),
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    ft.Text("Select Purpose & Category:", size=11.5, weight=ft.FontWeight.W_700, color=ft.Colors.GREY_500),
                    ft.Row(spacing=8, wrap=True, controls=cat_pills),
                    *(
                        [
                            ft.Text("Anchor to Curriculum:", size=11.5, weight=ft.FontWeight.W_700, color=ft.Colors.GREY_500),
                            ft.Row(spacing=6, scroll=ft.ScrollMode.HIDDEN, controls=mod_pills),
                        ]
                        if module_list
                        else []
                    ),
                    title_in,
                    content_in,
                    ft.Row(
                        alignment=ft.MainAxisAlignment.END,
                        spacing=10,
                        controls=[
                            ft.OutlinedButton(
                                "Cancel",
                                style=ft.ButtonStyle(
                                    padding=ft.Padding.symmetric(horizontal=16, vertical=10),
                                    shape=ft.RoundedRectangleBorder(radius=8),
                                ),
                                on_click=_on_cancel,
                            ),
                            publish_btn,
                        ],
                    ),
                    ft.Container(height=24),
                ],
            ),
        )

    def _render_thread_drilldown() -> ft.Container:
        d = state["selected_discussion"]
        if not d:
            return ft.Container()

        is_solved = d.get("is_resolved", False)
        upvoted = d.get("has_upvoted", False)
        upvotes = d.get("upvotes_count", 0)
        # Strictly the author who posted the question can mark it solved
        author_id = str((d.get("author") or {}).get("id") or d.get("user_id") or "").strip().lower()
        is_owner = bool(author_id and my_user_id and author_id == my_user_id)
        replies = d.get("replies", [])

        cat_key = str(d.get("category") or "question").lower().strip()
        if is_solved:
            drill_theme = ft.Colors.GREEN_600
            section_title = f"Solutions & Discussion ({len(replies)})"
            section_icon = ft.Icons.CHECK_CIRCLE_ROUNDED
            reply_hint = "Add additional perspective or follow-up note..."
            reply_btn_text = "Add Follow-up"
            reply_btn_icon = ft.Icons.REPLY_ROUNDED
            empty_text = "No follow-up replies yet."
        elif cat_key == "question":
            drill_theme = ft.Colors.BLUE_600
            section_title = f"Answers & Solutions ({len(replies)})"
            section_icon = ft.Icons.HELP_CENTER_ROUNDED
            reply_hint = "Write a clear answer or step-by-step solution..."
            reply_btn_text = "Post Answer"
            reply_btn_icon = ft.Icons.CHECK_ROUNDED
            empty_text = "No answers yet. Share your knowledge and help a classmate solve this!"
        elif cat_key == "idea":
            drill_theme = ft.Colors.AMBER_800
            section_title = f"Community Feedback & Insights ({len(replies)})"
            section_icon = ft.Icons.LIGHTBULB_ROUNDED
            reply_hint = "Share your thoughts, suggestions, or critique on this idea..."
            reply_btn_text = "Share Thought"
            reply_btn_icon = ft.Icons.COMMENT_ROUNDED
            empty_text = "No feedback yet. Be the first to share your thoughts on this idea!"
        elif cat_key == "resource":
            drill_theme = ft.Colors.TEAL_600
            section_title = f"Reviews & Additions ({len(replies)})"
            section_icon = ft.Icons.BOOKMARK_ROUNDED
            reply_hint = "Leave feedback, alternative references, or discussion..."
            reply_btn_text = "Contribute"
            reply_btn_icon = ft.Icons.ADD_COMMENT_ROUNDED
            empty_text = "No comments yet. Share your thoughts or complementary resources!"
        else:
            drill_theme = ft.Colors.DEEP_PURPLE_500
            section_title = f"Discussion Thread ({len(replies)})"
            section_icon = ft.Icons.FORUM_ROUNDED
            reply_hint = "Contribute your thoughts or join the conversation..."
            reply_btn_text = "Join Discussion"
            reply_btn_icon = ft.Icons.SEND_ROUNDED
            empty_text = "No replies yet. Start the conversation with your perspective!"

        reply_in = ft.TextField(
            hint_text=reply_hint,
            text_size=13,
            multiline=True,
            min_lines=2,
            max_lines=5,
            expand=True,
            border_radius=ft.BorderRadius.all(8),
            content_padding=ft.Padding.symmetric(horizontal=14, vertical=12),
            border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
            focused_border_color=drill_theme,
            disabled=is_offline,
        )

        def _on_submit_reply(e):
            if state.get("is_submitting_reply"):
                return
            text_val = reply_in.value
            if not text_val or not text_val.strip():
                return
            clean_text = text_val.strip()
            reply_in.value = ""
            state["is_submitting_reply"] = True

            # Immediate Optimistic Update: Append reply to UI right away!
            temp_id = f"temp_{uuid.uuid4().hex[:8]}"
            user_display_name = current_user.get("name") or current_user.get("full_name") or "You"
            opt_reply = {
                "id": temp_id,
                "content": clean_text,
                "author": {
                    "id": my_user_id,
                    "name": user_display_name,
                    "role": my_role,
                },
                "created_at": "Just now",
                "upvotes_count": 0,
                "has_upvoted": False,
                "is_endorsed": False,
            }
            d.setdefault("replies", []).append(opt_reply)
            d["replies_count"] = len(d["replies"])
            _render_view()

            async def _scroll_to_new_reply():
                await asyncio.sleep(0.08)
                target = state.get("thread_replies_col")
                if target:
                    try:
                        await target.scroll_to(offset=-1, duration=250)
                    except Exception:
                        pass
            asyncio.create_task(_scroll_to_new_reply())

            page.run_task(_submit_reply, d, clean_text, temp_id)

        reply_cards = []
        replies_col = ft.Column(
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
            auto_scroll=True,
            expand=True,
            controls=reply_cards,
        )
        state["thread_replies_col"] = replies_col

        for r in replies:
            r_upvoted = r.get("has_upvoted", False)
            r_upvotes = r.get("upvotes_count", 0)
            is_endorsed = r.get("is_endorsed", False)

            reply_cards.append(
                ft.Container(
                    bgcolor=ft.Colors.SURFACE if is_dark else "#FFFFFF",
                    border_radius=ft.BorderRadius.all(12),
                    border=ft.Border.all(
                        1,
                        ft.Colors.with_opacity(0.24, ft.Colors.AMBER) if is_endorsed else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                    ),
                    padding=ft.Padding.all(12),
                    content=ft.Column(
                        spacing=6,
                        controls=[
                            ft.Container(
                                visible=is_endorsed,
                                padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                                border_radius=ft.BorderRadius.all(6),
                                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER),
                                content=ft.Row(
                                    spacing=4,
                                    tight=True,
                                    controls=[
                                        ft.Icon(ft.Icons.VERIFIED_ROUNDED, size=12, color=ft.Colors.AMBER),
                                        ft.Text("Instructor-Verified Answer", size=10, weight=ft.FontWeight.W_800, color=ft.Colors.AMBER),
                                    ],
                                ),
                            ),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    _render_author_chip(r.get("author") or {}),
                                    ft.Text(_format_date(r.get("created_at")), size=10, color=ft.Colors.GREY_500),
                                ],
                            ),
                            ft.Text(r.get("content", ""), size=12.5, selectable=True),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.END,
                                controls=[
                                    ft.Container(
                                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                        border_radius=ft.BorderRadius.all(6),
                                        bgcolor=ft.Colors.with_opacity(0.10 if r_upvoted else 0.04, accent if r_upvoted else ft.Colors.GREY_500),
                                        ink=True,
                                        on_click=lambda e, item=r: page.run_task(_on_upvote_reply, item),
                                        content=ft.Row(
                                            spacing=3,
                                            tight=True,
                                            controls=[
                                                ft.Icon(
                                                    ft.Icons.THUMB_UP_ALT_ROUNDED if r_upvoted else ft.Icons.THUMB_UP_OUTLINED,
                                                    size=11,
                                                    color=accent if r_upvoted else ft.Colors.GREY_500,
                                                ),
                                                ft.Text(str(r_upvotes), size=10.5, color=accent if r_upvoted else ft.Colors.GREY_500),
                                            ],
                                        ),
                                    )
                                ],
                            ),
                        ],
                    ),
                )
            )

        if not reply_cards:
            reply_cards.append(
                ft.Container(
                    padding=ft.Padding.all(16),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text(empty_text, size=12, color=ft.Colors.GREY_500),
                )
            )

        return ft.Container(
            expand=True,
            content=ft.Column(
                spacing=10,
                expand=True,
                controls=[
                    # Back nav button + Status Badge & Module Badge
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                        controls=[
                            ft.TextButton(
                                content=ft.Row(
                                    spacing=4,
                                    tight=True,
                                    controls=[
                                        ft.Icon(ft.Icons.ARROW_BACK_ROUNDED, size=14),
                                        ft.Text("Back to Discussions", size=12, weight=ft.FontWeight.W_700),
                                    ],
                                ),
                                on_click=lambda _: _back_to_list(),
                            ),
                            ft.Row(
                                spacing=6,
                                tight=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    *(
                                        [
                                            ft.Container(
                                                padding=ft.Padding.symmetric(horizontal=7, vertical=2),
                                                border_radius=ft.BorderRadius.all(6),
                                                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.TEAL),
                                                content=ft.Row(
                                                    spacing=3,
                                                    tight=True,
                                                    controls=[
                                                        ft.Icon(ft.Icons.VIEW_MODULE_ROUNDED, size=11, color=ft.Colors.TEAL),
                                                        ft.Text(d.get("module_title", "Module"), size=10, weight=ft.FontWeight.W_700, color=ft.Colors.TEAL,max_lines=1,                        # Limit text to a single line
                overflow=ft.TextOverflow.ELLIPSIS  ),
                                                    ],
                                                ),
                                            )
                                        ]
                                        if d.get("module_title")
                                        else []
                                    ),
                                    _get_category_badge(d.get("category", "question"), is_solved),
                                ],
                            ),
                        ],
                    ),
                    # Original Post Full Card with Left-Accent Border
                    ft.Container(
                        bgcolor=ft.Colors.SURFACE if is_dark else "#FFFFFF",
                        border_radius=ft.BorderRadius.all(14),
                        border=ft.Border(
                            left=ft.BorderSide(4.5, drill_theme),
                            top=ft.BorderSide(1, ft.Colors.with_opacity(0.18, drill_theme) if is_dark else ft.Colors.with_opacity(0.12, drill_theme)),
                            right=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                            bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                        ),
                        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                        content=ft.Column(
                            spacing=6,
                            tight=True,
                            controls=[
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    spacing=6,
                                    controls=[
                                        _render_author_chip(d.get("author") or {}),
                                        ft.Row(
                                            spacing=6,
                                            tight=True,
                                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                            controls=[
                                                ft.Text(_format_date(d.get("created_at")), size=10.5, color=ft.Colors.GREY_500),
                                                ft.PopupMenuButton(
                                                    icon=ft.Icons.MORE_HORIZ_ROUNDED,
                                                    icon_size=16,
                                                    tooltip="Options",
                                                    items=[
                                                        ft.PopupMenuItem(
                                                            content=ft.Row(
                                                                spacing=6,
                                                                tight=True,
                                                                controls=[
                                                                    ft.Icon(ft.Icons.FLAG_OUTLINED, size=13, color=ft.Colors.RED_400),
                                                                    ft.Text("Report Post", size=11.5, color=ft.Colors.RED_400),
                                                                ],
                                                            ),
                                                            on_click=lambda e, item=d: _open_report_dialog(item),
                                                        ),
                                                    ],
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                ft.Text(d.get("title", ""), size=15, weight=ft.FontWeight.W_800, max_lines=3, overflow=ft.TextOverflow.ELLIPSIS),
                                ft.Container(
                                    content=ft.Text(d.get("content", ""), size=12.5, selectable=True),
                                ),
                                ft.Divider(height=1, color=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE)),
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    spacing=8,
                                    controls=[
                                        ft.Container(
                                            padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                                            border_radius=ft.BorderRadius.all(8),
                                            bgcolor=ft.Colors.with_opacity(0.12 if upvoted else 0.05, accent if upvoted else ft.Colors.GREY_500),
                                            ink=True,
                                            on_click=lambda e: page.run_task(_on_upvote_post, d),
                                            content=ft.Row(
                                                spacing=4,
                                                tight=True,
                                                controls=[
                                                    ft.Icon(
                                                        ft.Icons.THUMB_UP_ALT_ROUNDED if upvoted else ft.Icons.THUMB_UP_OUTLINED,
                                                        size=13,
                                                        color=accent if upvoted else ft.Colors.GREY_500,
                                                    ),
                                                    ft.Text(f"{upvotes} Upvotes", size=11, weight=ft.FontWeight.W_700, color=accent if upvoted else ft.Colors.GREY_500),
                                                ],
                                            ),
                                        ),
                                        ft.TextButton(
                                            visible=is_owner,
                                            content=ft.Row(
                                                spacing=4,
                                                tight=True,
                                                controls=[
                                                    ft.Icon(ft.Icons.CHECK_ROUNDED if not is_solved else ft.Icons.REPLAY_ROUNDED, size=13),
                                                    ft.Text("Mark as Solved" if not is_solved else "Reopen Topic", size=11, weight=ft.FontWeight.W_700),
                                                ],
                                            ),
                                            on_click=lambda e: page.run_task(_on_toggle_resolve, d),
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ),
                    # Dynamic Category Section Title
                    ft.Row(
                        [
                            ft.Icon(section_icon, size=15, color=drill_theme),
                            ft.Text(section_title, size=13.5, weight=ft.FontWeight.W_800),
                        ],
                        spacing=6,
                        tight=True,
                    ),
                    # Dedicated Independently Scrollable Answers List
                    ft.Container(
                        expand=True,
                        content=replies_col,
                    ),
                    # Reply Composer Docked at Bottom with Category Accent
                    ft.Container(
                        padding=ft.Padding.only(top=6, bottom=2),
                        content=(
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                                border_radius=ft.BorderRadius.all(10),
                                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ORANGE),
                                border=ft.Border.all(1, ft.Colors.with_opacity(0.25, ft.Colors.ORANGE)),
                                content=ft.Row(
                                    spacing=8,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.Icon(ft.Icons.WIFI_OFF_ROUNDED, size=16, color=ft.Colors.ORANGE_700),
                                        ft.Text(
                                            "Replies require an internet connection",
                                            size=12,
                                            color=ft.Colors.ORANGE_700,
                                            weight=ft.FontWeight.W_600,
                                            expand=True,
                                        ),
                                    ],
                                ),
                            )
                            if is_offline
                            else ft.Row(
                                spacing=10,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    reply_in,
                                    (
                                        ft.Container(
                                            padding=ft.Padding.all(10),
                                            content=ft.ProgressRing(width=20, height=20, stroke_width=2.5, color=drill_theme),
                                        )
                                        if state.get("is_submitting_reply")
                                        else ft.Container(
                                            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                                            border_radius=ft.BorderRadius.all(8),
                                            bgcolor=drill_theme,
                                            ink=True,
                                            on_click=_on_submit_reply,
                                            content=ft.Row(
                                                spacing=6,
                                                tight=True,
                                                controls=[
                                                    ft.Icon(reply_btn_icon, size=16, color=ft.Colors.WHITE),
                                                    ft.Text(reply_btn_text, size=12, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                                                ],
                                            ),
                                        )
                                    ),
                                ],
                            )
                        ),
                    ),
                ],
            ),
        )

    def _back_to_list():
        state["selected_discussion"] = None
        _render_view()

    def _render_view():
        content_socket.controls.clear()

        # Drilldown view if thread selected
        if state["selected_discussion"]:
            content_socket.controls.append(_render_thread_drilldown())
            page.update()
            return

        # Dedicated scrollable creation view if composer is open
        if state["is_composer_open"]:
            content_socket.controls.append(_render_composer_card())
            page.update()
            return

        # 1. Header & Controls

        search_tf = ft.TextField(
            hint_text="Search questions, topics or ideas...",
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            text_size=13,
            expand=True,
            border_radius=ft.BorderRadius.all(12),
            content_padding=ft.Padding.symmetric(horizontal=16, vertical=12),
            border_color=ft.Colors.with_opacity(0.16, ft.Colors.ON_SURFACE),
            focused_border_color=accent,
            on_submit=lambda e: _on_search(e.control.value),
        )

        categories = [
            ("all", "🌐 All", accent),
            ("question", "❓ Questions", ft.Colors.BLUE_600),
            ("idea", "💡 Ideas", ft.Colors.AMBER_800),
            ("discussion", "💬 Discussions", ft.Colors.DEEP_PURPLE_500),
            ("solved", "✅ Solved", ft.Colors.GREEN_700),
        ]
        cat_chips = []
        for cat_key, cat_label, cat_color in categories:
            is_active = (state["active_category"] == cat_key)
            def _filter_cat(k):
                return lambda _: _on_category_select(k)

            cat_chips.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=13, vertical=8),
                    border_radius=ft.BorderRadius.all(12),
                    bgcolor=ft.Colors.with_opacity(0.18, cat_color) if is_active else (ft.Colors.SURFACE_CONTAINER_HIGHEST if is_dark else "#F1F5F9"),
                    border=ft.Border.all(
                        1.5 if is_active else 1.0,
                        cat_color if is_active else ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE),
                    ),
                    ink=True,
                    on_click=_filter_cat(cat_key),
                    content=ft.Text(
                        cat_label,
                        size=11.5,
                        weight=ft.FontWeight.W_800 if is_active else ft.FontWeight.W_600,
                        color=cat_color if is_active else ft.Colors.ON_SURFACE,
                    ),
                )
            )

        # Module filter chips
        mod_filter_chips = []
        is_all_mod = (state["active_module_id"] == "all")
        def _filter_mod_all(e):
            return _on_module_filter("all")

        mod_filter_chips.append(
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=11, vertical=6),
                border_radius=ft.BorderRadius.all(10),
                bgcolor=ft.Colors.with_opacity(0.16, accent) if is_all_mod else (ft.Colors.SURFACE_CONTAINER_HIGHEST if is_dark else "#F1F5F9"),
                border=ft.Border.all(1.2 if is_all_mod else 1.0, accent if is_all_mod else ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                ink=True,
                on_click=_filter_mod_all,
                content=ft.Text(
                    "All Modules",
                    size=11,
                    weight=ft.FontWeight.W_800 if is_all_mod else ft.FontWeight.W_600,
                    color=accent if is_all_mod else ft.Colors.ON_SURFACE,
                ),
            )
        )

        if current_module_id:
            cur_title = mod_titles.get(current_module_id, "Current Module")
            is_cur = (state["active_module_id"] == current_module_id)
            def _filter_mod_cur(e, mid=current_module_id):
                return _on_module_filter(mid)

            mod_filter_chips.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=11, vertical=6),
                    border_radius=ft.BorderRadius.all(10),
                    bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.TEAL) if is_cur else (ft.Colors.SURFACE_CONTAINER_HIGHEST if is_dark else "#F1F5F9"),
                    border=ft.Border.all(1.2 if is_cur else 1.0, ft.Colors.TEAL if is_cur else ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                    ink=True,
                    on_click=_filter_mod_cur,
                    content=ft.Row(
                        spacing=4,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.LOCATION_ON_ROUNDED, size=12, color=ft.Colors.TEAL),
                            ft.Text(
                                f"Current: {cur_title[:16]}",
                                size=11,
                                weight=ft.FontWeight.W_800 if is_cur else ft.FontWeight.W_600,
                                color=ft.Colors.TEAL if is_cur else ft.Colors.ON_SURFACE,
                            ),
                        ],
                    ),
                )
            )

        for idx, mod in enumerate(module_list):
            m_id = str(mod.get("id"))
            if not m_id or m_id == current_module_id:
                continue
            m_name = mod.get("title", f"Module {idx+1}")
            is_m_act = (state["active_module_id"] == m_id)
            def _make_mod_clk(mid):
                return lambda _: _on_module_filter(mid)
            mod_filter_chips.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=11, vertical=6),
                    border_radius=ft.BorderRadius.all(10),
                    bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.BLUE_GREY) if is_m_act else (ft.Colors.SURFACE_CONTAINER_HIGHEST if is_dark else "#F1F5F9"),
                    border=ft.Border.all(1.2 if is_m_act else 1.0, ft.Colors.BLUE_GREY if is_m_act else ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                    ink=True,
                    on_click=_make_mod_clk(m_id),
                    content=ft.Text(
                        f"Mod {idx+1}: {m_name[:14]}",
                        size=11,
                        weight=ft.FontWeight.W_800 if is_m_act else ft.FontWeight.W_600,
                        color=ft.Colors.BLUE_GREY if is_m_act else ft.Colors.ON_SURFACE,
                    ),
                )
            )

        header_block = ft.Column(
            spacing=10,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                    controls=[
                        ft.Row(
                            spacing=8,
                            expand=True,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(ft.Icons.FORUM_ROUNDED, size=18, color=accent),
                                ft.Column(
                                    spacing=2,
                                    expand=True,
                                    controls=[
                                        ft.Text("Course Discussion Board", size=14, weight=ft.FontWeight.W_800, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                        ft.Text("Post questions & collaborate", size=11, color=ft.Colors.GREY_500, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                    ],
                                ),
                            ],
                        ),
                        (
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                                border_radius=ft.BorderRadius.all(12),
                                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ORANGE),
                                border=ft.Border.all(1, ft.Colors.with_opacity(0.25, ft.Colors.ORANGE)),
                                tooltip="You are currently offline. Connect to the internet to post discussions.",
                                content=ft.Row(
                                    spacing=6,
                                    tight=True,
                                    controls=[
                                        ft.Icon(ft.Icons.WIFI_OFF_ROUNDED, size=14, color=ft.Colors.ORANGE_700),
                                        ft.Text(
                                            "Offline",
                                            size=11.5,
                                            weight=ft.FontWeight.W_800,
                                            color=ft.Colors.ORANGE_700,
                                        ),
                                    ],
                                ),
                            )
                            if is_offline
                            else ft.Container(
                                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                                border_radius=ft.BorderRadius.all(12),
                                bgcolor=accent,
                                ink=True,
                                on_click=lambda _: _toggle_composer(),
                                content=ft.Row(
                                    spacing=4,
                                    tight=True,
                                    controls=[
                                        ft.Icon(ft.Icons.ADD_ROUNDED, size=15, color=ft.Colors.WHITE),
                                        ft.Text(
                                            "+ Start Discussion" if (getattr(page, "width", 800) or 800) >= 550 else "Post",
                                            size=11.5,
                                            weight=ft.FontWeight.W_800,
                                            color=ft.Colors.WHITE,
                                        ),
                                    ],
                                ),
                            )
                        ),
                    ],
                ),
                ft.Row(
                    spacing=8,
                    controls=[
                        search_tf,
                    ],
                ),
                *(
                    [
                        ft.Row(
                            spacing=6,
                            scroll=ft.ScrollMode.HIDDEN,
                            controls=mod_filter_chips,
                        )
                    ]
                    if module_list
                    else []
                ),
                ft.Row(
                    spacing=6,
                    scroll=ft.ScrollMode.HIDDEN,
                    controls=cat_chips,
                ),
            ],
        )
        content_socket.controls.append(header_block)

        # Offline notice banner
        if is_offline:
            content_socket.controls.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                    border_radius=ft.BorderRadius.all(10),
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ORANGE),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.25, ft.Colors.ORANGE)),
                    content=ft.Row(
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.WIFI_OFF_ROUNDED, size=18, color=ft.Colors.ORANGE_700),
                            ft.Column(
                                spacing=2,
                                expand=True,
                                controls=[
                                    ft.Text(
                                        "You're viewing this course offline",
                                        size=12.5,
                                        weight=ft.FontWeight.W_700,
                                        color=ft.Colors.ORANGE_700,
                                    ),
                                    ft.Text(
                                        "Discussions are read-only. Connect to the internet to post questions, share ideas, or reply to threads.",
                                        size=11,
                                        color=ft.Colors.ORANGE_800,
                                    ),
                                ],
                            ),
                        ],
                    ),
                )
            )

        # 2. Feed Cards
        if state["is_loading"]:
            content_socket.controls.append(
                ft.Container(
                    alignment=ft.Alignment.CENTER,
                    padding=ft.Padding.all(32),
                    content=ft.Column(
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                        controls=[
                            ft.ProgressRing(width=24, height=24, stroke_width=2.5, color=accent),
                            ft.Text("Loading discussion board...", size=12, color=ft.Colors.GREY_500),
                        ],
                    ),
                )
            )
        elif not state["discussions"]:
            active_cat = state.get("active_category", "all").lower()
            search_q = state.get("search_query", "").strip()

            if search_q:
                z_icon = ft.Icons.SEARCH_OFF_ROUNDED
                z_color = ft.Colors.GREY_500
                z_title = f"No results for '{search_q}'"
                z_subtitle = "Try adjusting your search terms or clearing the filter."
                z_btn_text = "Clear Search"
                def _z_action(_):
                    state["search_query"] = ""
                    page.run_task(_load_discussions)
            elif active_cat == "solved":
                z_icon = ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED
                z_color = ft.Colors.GREEN_600
                z_title = "No solved questions yet"
                z_subtitle = "When a question receives a verified or accepted answer, it will appear here as a helpful reference."
                z_btn_text = "Browse Open Questions"
                def _z_action(_):
                    _on_category_select("question")
            elif active_cat == "question":
                z_icon = ft.Icons.HELP_OUTLINE_ROUNDED
                z_color = ft.Colors.BLUE_600
                z_title = "No open questions yet"
                z_subtitle = "Stuck on a concept, assignment, or video? Ask a question and your classmates or instructor will help."
                z_btn_text = "+ Ask a Question"
                def _z_action(_):
                    state["selected_new_category"] = "question"
                    state["is_composer_open"] = True
                    _render_view()
            elif active_cat == "idea":
                z_icon = ft.Icons.LIGHTBULB_OUTLINE_ROUNDED
                z_color = ft.Colors.AMBER_800
                z_title = "No ideas shared yet"
                z_subtitle = "Have a creative perspective, study strategy, or project concept? Share your ideas with the cohort!"
                z_btn_text = "+ Share an Idea"
                def _z_action(_):
                    state["selected_new_category"] = "idea"
                    state["is_composer_open"] = True
                    _render_view()
            elif active_cat == "discussion":
                z_icon = ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED
                z_color = ft.Colors.DEEP_PURPLE_500
                z_title = "No general discussions in this thread"
                z_subtitle = "Start a topic to chat about lecture topics, study sessions, or industry applications."
                z_btn_text = "+ Start Discussion"
                def _z_action(_):
                    state["selected_new_category"] = "discussion"
                    state["is_composer_open"] = True
                    _render_view()
            else:
                z_icon = ft.Icons.FORUM_ROUNDED
                z_color = accent
                z_title = "No topics posted yet in this course"
                z_subtitle = "Be the first to start a conversation, ask a question, or share insights with your cohort!"
                z_btn_text = "+ Start the First Topic"
                def _z_action(_):
                    state["is_composer_open"] = True
                    _render_view()

            content_socket.controls.append(
                ft.Container(
                    padding=ft.Padding.all(36),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=10,
                        controls=[
                            ft.Container(
                                width=64,
                                height=64,
                                border_radius=ft.BorderRadius.all(32),
                                bgcolor=ft.Colors.with_opacity(0.12, z_color),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(z_icon, size=32, color=z_color),
                            ),
                            ft.Text(z_title, size=15, weight=ft.FontWeight.W_800),
                            ft.Container(
                                content=ft.Text(
                                    z_subtitle,
                                    size=12,
                                    color=ft.Colors.GREY_500,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                            ),
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=18, vertical=10),
                                border_radius=ft.BorderRadius.all(12),
                                bgcolor=accent,
                                ink=True,
                                on_click=_z_action,
                                content=ft.Row(
                                    spacing=6,
                                    tight=True,
                                    controls=[
                                        ft.Icon(
                                            ft.Icons.ADD_ROUNDED if "+" in z_btn_text else ft.Icons.ARROW_FORWARD_ROUNDED,
                                            size=15,
                                            color=ft.Colors.WHITE,
                                        ),
                                        ft.Text(z_btn_text, size=12.5, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                                    ],
                                ),
                            ),
                        ],
                    ),
                )
            )
        else:
            cards = [_render_thread_card(d) for d in state["discussions"]]
            content_socket.controls.append(
                ft.Column(
                    spacing=10,
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                    controls=cards,
                )
            )

        page.update()

    def _toggle_composer():
        if is_offline:
            return
        state["is_composer_open"] = not state["is_composer_open"]
        _render_view()

    def _on_category_select(cat: str):
        state["active_category"] = cat
        page.run_task(_load_discussions)

    def _on_module_filter(mid: str):
        state["active_module_id"] = mid
        page.run_task(_load_discussions)

    def _on_search(q: str):
        state["search_query"] = q.strip()
        page.run_task(_load_discussions)

    # Initial render + async data load
    _render_view()
    page.run_task(_load_discussions)

    return ft.Container(
        expand=True,
        padding=ft.Padding.symmetric(vertical=6),
        content=content_socket,
    )



def build_progress_tab_view(
    course_data: Dict[str, Any],
    page: ft.Page,
) -> ft.Container:
    """Builds the Progress Tab: completion ring, module checklists, certificate generation."""
    accent = ft.Colors.PRIMARY
    modules = course_data.get("modules", [])

    total_lessons = sum(len(m.get("lessons", [])) for m in modules)
    done_lessons = sum(sum(1 for l in m.get("lessons", []) if l.get("is_done", False)) for m in modules)
    pct = round((done_lessons / max(total_lessons, 1)) * 100)

    module_progress_rows = []
    for idx, mod in enumerate(modules):
        m_title = mod.get("title", f"Module {idx + 1}")
        m_les = mod.get("lessons", [])
        m_done = sum(1 for l in m_les if l.get("is_done", False))
        m_pct = round((m_done / max(len(m_les), 1)) * 100)

        module_progress_rows.append(
            ft.Container(
                padding=ft.Padding.all(12),
                border_radius=ft.BorderRadius.all(12),
                bgcolor=ft.Colors.SURFACE,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            spacing=10,
                            controls=[
                                ft.Icon(
                                    ft.Icons.CHECK_CIRCLE_ROUNDED if m_pct == 100 else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED,
                                    size=18,
                                    color=ft.Colors.GREEN_400 if m_pct == 100 else ft.Colors.GREY_400,
                                ),
                                ft.Text(m_title, size=13, weight=ft.FontWeight.W_700),
                            ],
                        ),
                        ft.Text(f"{m_done}/{len(m_les)} ({m_pct}%)", size=12, color=ft.Colors.GREY_500),
                    ],
                ),
            )
        )

    cert_btn = ft.FilledButton(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.WORKSPACE_PREMIUM_ROUNDED, size=16),
                ft.Text("Download Certificate of Completion", size=12.5, weight=ft.FontWeight.W_700),
            ],
            tight=True,
            spacing=6,
        ),
        disabled=pct < 100,
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.AMBER_600,
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=ft.Padding.symmetric(horizontal=16, vertical=10),
        ),
        on_click=lambda _: page.run_task(generate_course_certificate, page, str(course_data.get("id", ""))),
    )

    return ft.Container(
        padding=ft.Padding.symmetric(vertical=8),
        content=ft.Column(
            spacing=14,
            controls=[
                # Top summary card
                ft.Container(
                    padding=ft.Padding.all(18),
                    border_radius=ft.BorderRadius.all(16),
                    bgcolor=ft.Colors.with_opacity(0.08, accent),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Column(
                                spacing=4,
                                controls=[
                                    ft.Text(f"{pct}% Completed", size=22, weight=ft.FontWeight.W_900, color=accent),
                                    ft.Text(f"{done_lessons} of {total_lessons} lessons mastered", size=12, color=ft.Colors.GREY_600),
                                ],
                            ),
                            ft.Container(
                                width=56,
                                height=56,
                                content=ft.ProgressRing(value=pct / 100.0, stroke_width=6, color=accent),
                            ),
                        ],
                    ),
                ),
                ft.Row(
                    [
                        ft.Icon(ft.Icons.CHECKLIST_ROUNDED, size=16, color=accent),
                        ft.Text("Module Progress Breakdown", size=14, weight=ft.FontWeight.W_800),
                    ],
                    spacing=6,
                ),
                ft.Column(spacing=8, controls=module_progress_rows),
                ft.Container(height=8),
                cert_btn,
            ],
        ),
    )
