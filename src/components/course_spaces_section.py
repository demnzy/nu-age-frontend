"""
Course Spaces Section Component for the Learn view (src/courses.py).

Provides:
- Tab navigation between "My Spaces" (enrolled) and "Explore Open Spaces" (discoverable).
- Live search bar and access/live-session filter pills with category-cognizant zero states.
- "Join with Code" modal supporting 1-tap cascading course enrollment.
- Sleek responsive space cards with course tags, tutor info, copyable invite codes, and metrics.
(Course Space creation is strictly managed by Organisations in the Org Spaces view.)
"""

import asyncio
from typing import Optional, Dict, Any, List
import flet as ft

from src.requests.course_spaces import (
    get_my_spaces,
    get_explore_spaces,
    join_course_space,
)
from src.utils.file_opener import show_page_snackbar, safe_set_clipboard
from src.components.shimmer_skeletons import build_course_spaces_skeleton
from src.utils.theme_bridge import build_shad_badge, LucideIcons


def build_course_spaces_section(
    page: ft.Page,
    token: str,
    user_data: dict,
    on_count_updated=None
) -> ft.Container:
    """Constructs the responsive Spaces section within the Learn view."""
    state = {
        "sub_tab": "my_spaces",  # "my_spaces" or "explore"
        "my_spaces": [],
        "explore_spaces": [],
        "loading": True,
        "search_query": "",
        "role_filter": "ALL",  # "ALL", "OPEN_ONLY", "WITH_LIVE"
        "token": token or "",
    }

    cards_row = ft.ResponsiveRow(spacing=16, run_spacing=16)
    content_holder = ft.Column(spacing=16, expand=False)

    async def _resolve_token() -> str:
        if state["token"]:
            return state["token"]
        try:
            if hasattr(page, "session") and hasattr(page.session, "store"):
                s_tok = page.session.store.get("session_auth_token")
                if s_tok:
                    state["token"] = s_tok
                    return s_tok
            if hasattr(page, "shared_preferences"):
                sp_tok = await page.shared_preferences.get("auth_token")
                if sp_tok:
                    state["token"] = sp_tok
                    return sp_tok
        except Exception:
            pass
        return state["token"]

    def _screen_w() -> int:
        try:
            w = page.width or getattr(page.window, "width", None) or 1024
            return int(w)
        except Exception:
            return 1024

    def _close_dialog(dlg: ft.AlertDialog):
        dlg.open = False
        page.update()

    # ── 1. Fetch Spaces Data ───────────────────────────────────────────────
    async def _refresh_spaces(e=None):
        state["loading"] = True
        _render_cards()
        page.update()

        tok = await _resolve_token()
        if tok and str(tok).strip() and str(tok).strip() not in ("None", "null", "undefined"):
            my_res, exp_res = await asyncio.gather(
                get_my_spaces(token=tok),
                get_explore_spaces(token=tok, query=state["search_query"]),
                return_exceptions=True,
            )
        else:
            my_res = {"spaces": []}
            try:
                exp_res = await get_explore_spaces(token="", query=state["search_query"])
            except Exception:
                exp_res = {"spaces": []}
        state["my_spaces"] = my_res.get("spaces", []) if isinstance(my_res, dict) else []
        state["explore_spaces"] = exp_res.get("spaces", []) if isinstance(exp_res, dict) else []

        state["loading"] = False
        if on_count_updated:
            try:
                on_count_updated(len(state["my_spaces"]))
            except Exception:
                pass

        _render_cards()
        page.update()

    # ── 2. Join Space Modal ────────────────────────────────────────────────
    def _open_join_modal(e=None, prefill_code: str = "", target_space: Optional[dict] = None):
        sw = _screen_w()
        modal_w = min(420, max(280, int(sw * 0.90)))

        space_title = target_space.get("name") if target_space else None

        code_tf = ft.TextField(
            label="Space Invite Code *",
            hint_text="e.g. SPACE-8X9L2K",
            value=prefill_code,
            capitalization=ft.TextCapitalization.CHARACTERS,
            autofocus=True,
            dense=True,
            prefix_icon=ft.Icons.VPN_KEY_ROUNDED,
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
            focused_border_color=ft.Colors.PRIMARY,
            text_size=13,
        )
        join_btn = ft.Button(
            "Unlock Space" if space_title else "Join Space",
            icon=ft.Icons.LOCK_OPEN_ROUNDED if space_title else ft.Icons.LOGIN_ROUNDED,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.PRIMARY,
                color=ft.Colors.ON_PRIMARY,
                shape=ft.RoundedRectangleBorder(radius=10),
            ),
        )

        async def _do_join(ev):
            val = (code_tf.value or "").strip().upper()
            if not val:
                show_page_snackbar(page, "Please enter a valid Space invite code.")
                return

            join_btn.disabled = True
            join_btn.content = ft.ProgressRing(width=16, height=16, stroke_width=2, color=ft.Colors.ON_PRIMARY)
            page.update()

            tok = await _resolve_token()
            res = await join_course_space(token=tok, code=val)
            if res.get("status") == "success":
                courses_enrolled = res.get("courses_auto_enrolled", 0)
                msg = f"Joined {res.get('name', 'Space')}!"
                if courses_enrolled > 0:
                    msg += f" ({courses_enrolled} linked course{'s' if courses_enrolled != 1 else ''} unlocked)"
                show_page_snackbar(page, msg)
                _close_dialog(dlg)
                sp_id = res.get("space_id")
                if sp_id:
                    page.navigate(f"/spaces/{sp_id}")
                else:
                    await _refresh_spaces()
            else:
                show_page_snackbar(page, res.get("message", "Could not join Space. Check the code and try again."))
                join_btn.disabled = False
                join_btn.content = None
                join_btn.text = "Unlock Space" if space_title else "Join Space"
                page.update()

        join_btn.on_click = lambda ev: page.run_task(_do_join, ev)
        code_tf.on_submit = lambda ev: page.run_task(_do_join, ev)

        dlg = ft.AlertDialog(
            shape=ft.RoundedRectangleBorder(radius=16),
            title=ft.Row(
                [
                    ft.Row(
                        [
                            ft.Container(
                                width=36,
                                height=36,
                                border_radius=10,
                                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.VPN_KEY_ROUNDED, color=ft.Colors.PRIMARY, size=18),
                            ),
                            ft.Column(
                                [
                                    ft.Text(f"Unlock {space_title}" if space_title else "Unlock Course Space", weight=ft.FontWeight.BOLD, size=16),
                                    ft.Text("Enter secret invite code", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                                spacing=1,
                            ),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.IconButton(
                        ft.Icons.CLOSE_ROUNDED,
                        icon_size=18,
                        tooltip="Close",
                        on_click=lambda ev: _close_dialog(dlg),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            content=ft.Container(
                width=modal_w,
                content=ft.Column(
                    [
                        ft.Text(
                            f"Enter the invite code for '{space_title}' to join your cohort."
                            if space_title
                            else "Enter the invite code shared by your instructor to join your cohort.",
                            size=12.5,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        code_tf,
                    ],
                    spacing=14,
                    tight=True,
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda ev: _close_dialog(dlg)),
                join_btn,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    # ── 3. Card Renderer ───────────────────────────────────────────────────
    def _build_space_card(sp: dict, is_explore: bool = False) -> ft.Container:
        sp_id = str(sp.get("id", ""))
        name = sp.get("name", "Course Space")
        desc = sp.get("description", "")
        creator = sp.get("creator_name", "Instructor")
        code = sp.get("code", "")
        c_count = sp.get("course_count", 0)
        m_count = sp.get("material_count", 0)
        q_count = sp.get("quiz_count", 0)
        s_count = sp.get("upcoming_session_count", 0)
        mem_count = sp.get("member_count", 0)
        is_open = bool(sp.get("is_open", False))
        can_manage = bool(sp.get("can_manage", False) or sp.get("is_creator", False) or sp.get("role") in ("tutor", "manager", "creator"))
        # On the student Learn tab, enrolled status requires real student enrollment.
        # Private spaces must never be entered without the invite code.
        is_enrolled = bool(sp.get("is_student", False) or sp.get("is_enrolled", False) or can_manage)
        courses_list = sp.get("courses") or []

        access_pill = build_shad_badge(
            text="Open Hub" if is_open else "Invite Only",
            variant="primary" if is_open else "outline",
            icon=LucideIcons.GLOBE if is_open else LucideIcons.LOCK,
        )

        # Linked courses preview pills
        course_pills = []
        for c_item in courses_list[:2]:
            c_title = c_item.get("title", "Course")
            course_pills.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=6,
                    bgcolor=ft.Colors.with_opacity(0.07, ft.Colors.PRIMARY),
                    content=ft.Text(
                        c_title,
                        size=10.5,
                        weight=ft.FontWeight.W_600,
                        color=ft.Colors.PRIMARY,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                )
            )
        if len(courses_list) > 2:
            course_pills.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=7, vertical=3),
                    border_radius=6,
                    bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                    content=ft.Text(f"+{len(courses_list) - 2} more", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                )
            )

        action_btn = ft.Button(
            "Enter Space" if is_enrolled else ("Join Space" if is_open else "Unlock with Code"),
            icon=ft.Icons.ARROW_FORWARD_ROUNDED if is_enrolled else (ft.Icons.ADD_ROUNDED if is_open else ft.Icons.VPN_KEY_ROUNDED),
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.PRIMARY,
                color=ft.Colors.ON_PRIMARY,
                shape=ft.RoundedRectangleBorder(radius=10),
            ),
        )

        async def _enter_or_join(ev):
            if is_enrolled:
                page.navigate(f"/spaces/{sp_id}")
                return
            if not is_open:
                _open_join_modal(target_space=sp)
                return

            action_btn.disabled = True
            action_btn.content = ft.ProgressRing(width=16, height=16, stroke_width=2, color=ft.Colors.ON_PRIMARY)
            page.update()

            tok = await _resolve_token()
            join_res = await join_course_space(token=tok, space_id=sp_id)
            if join_res.get("status") == "success":
                show_page_snackbar(page, f"Enrolled in {name}!")
                page.navigate(f"/spaces/{sp_id}")
            else:
                show_page_snackbar(page, join_res.get("message", "Enrollment failed."))
                action_btn.disabled = False
                action_btn.content = None
                action_btn.text = "Join Space"
                page.update()

        action_btn.on_click = lambda ev: page.run_task(_enter_or_join, ev)

        footer_left = ft.Text(
            f"📅 {s_count} live class{'es' if s_count != 1 else ''}" if s_count > 0 else f"👥 {mem_count} member{'s' if mem_count != 1 else ''}",
            size=11.5,
            weight=ft.FontWeight.W_600 if s_count > 0 else ft.FontWeight.NORMAL,
            color=ft.Colors.PRIMARY if s_count > 0 else ft.Colors.ON_SURFACE_VARIANT,
        )

        card_controls = [
            ft.Row(
                [
                    ft.Container(
                        width=44,
                        height=44,
                        border_radius=12,
                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(ft.Icons.HUB_ROUNDED, color=ft.Colors.PRIMARY, size=23),
                    ),
                    ft.Column(
                        [
                            ft.Text(
                                name,
                                weight=ft.FontWeight.BOLD,
                                size=15.5,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            ft.Text(
                                f"By {creator} • {mem_count} member{'s' if mem_count != 1 else ''}",
                                size=11.5,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    access_pill,
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            ),
            ft.Text(
                desc or "Asynchronous learning hub for shared lecture notes, CBT topic drills, and scheduled live classes.",
                size=12.5,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
        ]

        if course_pills:
            card_controls.append(ft.Row(course_pills, spacing=6, wrap=True))

        card_controls.extend(
            [
                ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                ft.Row(
                    [
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                            border_radius=6,
                            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                            content=ft.Text(f"📚 {c_count} Courses", size=11, weight=ft.FontWeight.W_600),
                        ),
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                            border_radius=6,
                            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                            content=ft.Text(f"📁 {m_count} Resources", size=11, weight=ft.FontWeight.W_600),
                        ),
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                            border_radius=6,
                            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                            content=ft.Text(f"⚡ {q_count} CBT Drills", size=11, weight=ft.FontWeight.W_600),
                        ),
                    ],
                    spacing=6,
                    wrap=True,
                ),
                (
                    ft.Column(
                        [
                            ft.Row([footer_left], alignment=ft.MainAxisAlignment.START),
                            ft.Row([ft.Container(action_btn, expand=1)]),
                        ],
                        spacing=8,
                    )
                    if _screen_w() < 680
                    else ft.Row(
                        [
                            footer_left,
                            action_btn,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                ),
            ]
        )

        card = ft.Container(
            padding=18,
            border_radius=14,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.09, ft.Colors.ON_SURFACE)),
            content=ft.Column(card_controls, spacing=11),
            ink=True,
            on_click=lambda ev: page.run_task(_enter_or_join, ev),
        )
        card.col = {"xs": 12, "sm": 12, "md": 6, "lg": 4}
        return card

    # ── 5. Main Card List & Zero State ─────────────────────────────────────
    search_input = ft.TextField(
        hint_text="Search spaces by name, course, or invite code...",
        prefix_icon=ft.Icons.SEARCH_ROUNDED,
        dense=True,
        border_radius=10,
        text_size=13,
        expand=True,
    )

    async def _on_search_submit(ev=None):
        state["search_query"] = (search_input.value or "").strip()
        if state["sub_tab"] == "explore":
            await _refresh_spaces()
        else:
            _render_cards()
            page.update()

    def _on_search_change(ev):
        state["search_query"] = (ev.control.value or "").strip()
        if state["sub_tab"] == "my_spaces":
            _render_cards()
            page.update()

    search_input.on_change = _on_search_change
    search_input.on_submit = lambda ev: page.run_task(_on_search_submit, ev)

    def _set_role_filter(f_val: str):
        state["role_filter"] = f_val
        _render_cards()
        page.update()

    def _render_cards():
        cards_row.controls.clear()
        content_holder.controls.clear()
        sw = _screen_w()
        is_mob = sw < 768

        # Action buttons (Learners join via code; Course Spaces are created by Organisations)
        action_btns = [
            ft.Button(
                "Join with Code",
                icon=ft.Icons.VPN_KEY_ROUNDED,
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.PRIMARY,
                    color=ft.Colors.ON_PRIMARY,
                    shape=ft.RoundedRectangleBorder(radius=10),
                ),
                on_click=_open_join_modal,
            ),
        ]

        tabs_row = ft.Row(
            [
                ft.Chip(
                    label=ft.Text(f"My Spaces ({len(state['my_spaces'])})"),
                    selected=state["sub_tab"] == "my_spaces",
                    on_select=lambda ev: _set_sub_tab("my_spaces"),
                ),
                ft.Chip(
                    label=ft.Text(f"Explore Open Spaces ({len(state['explore_spaces'])})"),
                    selected=state["sub_tab"] == "explore",
                    on_select=lambda ev: _set_sub_tab("explore"),
                ),
            ],
            spacing=8,
            wrap=True,
        )

        if is_mob:
            top_bar = ft.Column(
                [
                    tabs_row,
                    ft.Row(action_btns, spacing=8, wrap=True),
                ],
                spacing=10,
            )
        else:
            top_bar = ft.Row(
                [
                    tabs_row,
                    ft.Row(action_btns, spacing=8),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        content_holder.controls.append(top_bar)

        # Search & Quick Filters Row
        filter_chips = ft.Row(
            [
                ft.Chip(
                    label=ft.Text("All", size=12),
                    selected=state["role_filter"] == "ALL",
                    on_select=lambda _: _set_role_filter("ALL"),
                ),
                ft.Chip(
                    label=ft.Text("Upcoming Live Class", size=12),
                    selected=state["role_filter"] == "WITH_LIVE",
                    on_select=lambda _: _set_role_filter("WITH_LIVE"),
                ),
            ],
            spacing=6,
            wrap=True,
        )

        if is_mob:
            content_holder.controls.append(ft.Column([ft.Row([search_input]), filter_chips], spacing=8))
        else:
            content_holder.controls.append(
                ft.Row(
                    [search_input, filter_chips],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )

        if state["loading"]:
            from src.components.shimmer_skeletons import grey_card, shimmer_box, GREY_BOX_COLOR
            def _skel_space_card():
                return grey_card(
                    padding=16,
                    radius=14,
                    col={"xs": 12, "sm": 12, "md": 6, "lg": 4},
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Row(
                                        [
                                            shimmer_box(radius=12, height=44, width=44),
                                            ft.Column(
                                                [
                                                    shimmer_box(radius=4, height=15, width=130),
                                                    shimmer_box(radius=4, height=11, width=90),
                                                ],
                                                spacing=4,
                                            ),
                                        ],
                                        spacing=10,
                                        tight=True,
                                    ),
                                    shimmer_box(radius=8, height=22, width=70),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Column(
                                [
                                    shimmer_box(radius=4, height=12, expand=True),
                                    shimmer_box(radius=4, height=12, width=170),
                                ],
                                spacing=4,
                            ),
                            ft.Row(
                                [
                                    shimmer_box(radius=6, height=20, width=75),
                                    shimmer_box(radius=6, height=20, width=85),
                                ],
                                spacing=6,
                            ),
                            ft.Container(height=1, bgcolor=GREY_BOX_COLOR, opacity=0.3),
                            ft.Row(
                                [
                                    shimmer_box(radius=4, height=13, width=80),
                                    shimmer_box(radius=10, height=32, width=105),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        ],
                        spacing=12,
                    ),
                )

            content_holder.controls.append(
                ft.ResponsiveRow(
                    spacing=14,
                    run_spacing=14,
                    controls=[_skel_space_card() for _ in range(6)],
                )
            )
            return

        raw_list = state["my_spaces"] if state["sub_tab"] == "my_spaces" else state["explore_spaces"]
        q_low = (state["search_query"] or "").strip().lower()
        rf = state["role_filter"]

        active_list = []
        for sp in raw_list:
            if rf == "WITH_LIVE" and int(sp.get("upcoming_session_count") or 0) <= 0:
                continue
            if q_low:
                haystack = " ".join([
                    str(sp.get("name") or ""),
                    str(sp.get("description") or ""),
                    str(sp.get("code") or ""),
                    str(sp.get("creator_name") or ""),
                    " ".join(str(c.get("title") or "") for c in (sp.get("courses") or [])),
                ]).lower()
                if q_low not in haystack:
                    continue
            active_list.append(sp)

        if not active_list:
            is_my = state["sub_tab"] == "my_spaces"
            has_filters = bool(q_low or rf != "ALL")
            zero_w = min(480, max(240, int(sw * 0.85)))

            if has_filters:
                zero_title = "No Matching Spaces Found"
                zero_desc = "No spaces matched your search. Try adjusting your query or clearing filters."
            elif is_my:
                zero_title = "You Haven't Joined Any Spaces Yet"
                zero_desc = "Join your study cohort to access shared materials, practice drills, and live classes."
            else:
                zero_title = "No Open Spaces Available"
                zero_desc = "No public spaces are listed right now. Use an invite code to join a private group."

            zero_actions = (
                [
                    ft.OutlinedButton(
                        "Clear Filters",
                        icon=ft.Icons.FILTER_ALT_OFF_ROUNDED,
                        on_click=lambda _: (
                            setattr(search_input, "value", ""),
                            state.update({"search_query": "", "role_filter": "ALL"}),
                            _render_cards(),
                            page.update(),
                        ),
                    ),
                    ft.Button(
                        "Join with Code",
                        icon=ft.Icons.VPN_KEY_ROUNDED,
                        style=ft.ButtonStyle(bgcolor=ft.Colors.PRIMARY, color=ft.Colors.ON_PRIMARY),
                        on_click=_open_join_modal,
                    ),
                ]
                if has_filters
                else [
                    ft.Button(
                        "Join with Code",
                        icon=ft.Icons.VPN_KEY_ROUNDED,
                        style=ft.ButtonStyle(bgcolor=ft.Colors.PRIMARY, color=ft.Colors.ON_PRIMARY),
                        on_click=_open_join_modal,
                    ),
                    ft.OutlinedButton(
                        "Browse Open Public Spaces" if is_my else "View My Spaces",
                        icon=ft.Icons.EXPLORE_ROUNDED if is_my else ft.Icons.MEETING_ROOM_ROUNDED,
                        on_click=lambda _: _set_sub_tab("explore" if is_my else "my_spaces"),
                    ),
                ]
            )

            zero_state = ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=36 if is_mob else 48,
                border_radius=14,
                bgcolor=ft.Colors.SURFACE,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                content=ft.Column(
                    [
                        ft.Container(
                            width=60,
                            height=60,
                            border_radius=30,
                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(ft.Icons.HUB_ROUNDED, size=30, color=ft.Colors.PRIMARY),
                        ),
                        ft.Text(zero_title, weight=ft.FontWeight.BOLD, size=17, text_align=ft.TextAlign.CENTER),
                        ft.Container(
                            width=zero_w,
                            content=ft.Text(
                                zero_desc,
                                size=13,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ),
                        (
                            ft.Column(
                                zero_actions,
                                spacing=10,
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            )
                            if is_mob
                            else ft.Row(
                                zero_actions,
                                spacing=10,
                                alignment=ft.MainAxisAlignment.CENTER,
                            )
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                ),
            )
            content_holder.controls.append(zero_state)
            return

        for sp in active_list:
            cards_row.controls.append(_build_space_card(sp, is_explore=(state["sub_tab"] == "explore")))

        content_holder.controls.append(cards_row)

    def _set_sub_tab(tab_name: str):
        state["sub_tab"] = tab_name
        _render_cards()
        page.update()

    # Trigger initial load
    page.run_task(_refresh_spaces)

    return ft.Container(
        content=ft.ListView(
            controls=[
                ft.Container(
                    content=content_holder,
                    padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                )
            ],
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        ),
        expand=True,
    )
