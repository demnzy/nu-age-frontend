"""
dashboard_duo_section.py
──────────────────────────────────────────────────────────────────────────────
Premier Dashboard Section for the Self-Study Hub:
- Platform Prelim Objectives & Nu-Coins Engine (clean progress, zero gray boxes).
- Campus Study Leaderboards (Duo Streaks, Today's Focus Minutes, Solo Streaks).
- Duo Shared Study Packs Tray (Accept & Study, Duel on Pack, Share New Pack).
──────────────────────────────────────────────────────────────────────────────
"""

import asyncio
import flet as ft
from typing import Optional, Callable, Dict, Any, List

from src.utils.file_opener import show_page_snackbar
from src.requests.objectives import (
    get_platform_objectives_api,
    claim_objective_reward_api,
)
from src.requests.study_partners import (
    get_active_partnership,
    get_shared_study_packs_api,
    accept_shared_study_pack_api,
    get_study_leaderboard_api,
    generate_quickfire_from_pack_api,
    preview_shared_study_pack_api,
)
from src.components.partner_challenge_modal import (
    start_quickfire_duel_flow,
    show_flashcard_preview_dialog,
)


def build_dashboard_duo_section(
    page: ft.Page,
    token: str,
    partnership_id: Optional[str] = None,
    partner: Optional[dict] = None,
    on_coins_changed: Optional[Callable] = None,
    on_open_share_dialog: Optional[Callable] = None,
) -> ft.Container:
    """
    Renders an integrated dashboard section directly beneath the Study Partner Cockpit.
    Seamlessly switches between Objectives, Campus Leaderboards, and Shared Packs.
    """
    current_tab = "objectives"
    p_name = f"{partner.get('first_name', 'Partner')} {partner.get('last_name', '')}".strip() if partner else "Partner"

    # Tab Buttons Row
    tab_buttons_row = ft.Row(spacing=6, tight=True)
    body_container = ft.Container(
        expand=True,
        opacity=1,
        offset=ft.Offset(0, 0),
        animate_opacity=ft.Animation(360, ft.AnimationCurve.DECELERATE),
        animate_offset=ft.Animation(360, ft.AnimationCurve.DECELERATE),
    )

    async def _swap_body_smoothly(new_content):
        body_container.opacity = 0
        body_container.offset = ft.Offset(0, 0.04)
        page.update()
        await asyncio.sleep(0.06)
        body_container.content = new_content
        body_container.opacity = 1
        body_container.offset = ft.Offset(0, 0)
        page.update()

    def _switch_tab(tab_key: str):
        nonlocal current_tab
        current_tab = tab_key
        _render_tab_headers()
        if tab_key == "objectives":
            page.run_task(_load_objectives)
        elif tab_key == "leaderboard":
            page.run_task(_load_leaderboard, "duo_streaks" if partnership_id else "today")
        elif tab_key == "shared_packs":
            page.run_task(_load_shared_packs)

    def _render_tab_headers():
        tab_buttons_row.controls.clear()
        tabs = [
            ("objectives", "🪙 Prelim Objectives", ft.Icons.TOKEN_ROUNDED),
            ("leaderboard", "🏆 Campus Leaderboard", ft.Icons.LEADERBOARD_ROUNDED),
            ("shared_packs", "📚 Duo Shared Packs", ft.Icons.FOLDER_SHARED_ROUNDED),
        ]
        for key, label, icon in tabs:
            is_active = (key == current_tab)
            btn = ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                border_radius=ft.BorderRadius.all(10),
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if is_active else ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                ink=True,
                on_click=(lambda k=key: lambda _: _switch_tab(k))(),
                content=ft.Row(
                    spacing=6,
                    tight=True,
                    controls=[
                        ft.Icon(icon, size=15, color=ft.Colors.PRIMARY if is_active else ft.Colors.GREY_500),
                        ft.Text(
                            label,
                            size=12,
                            weight=ft.FontWeight.W_700 if is_active else ft.FontWeight.W_500,
                            color=ft.Colors.PRIMARY if is_active else ft.Colors.ON_SURFACE,
                        ),
                    ],
                ),
            )
            tab_buttons_row.controls.append(btn)
        page.update()

    # ─────────────────────────────────────────────────────────────────────────
    # 1. OBJECTIVES TAB (ZERO GRAY BOXES)
    # ─────────────────────────────────────────────────────────────────────────
    async def _load_objectives():
        body_container.content = ft.Container(
            padding=30,
            alignment=ft.Alignment.CENTER,
            content=ft.ProgressRing(width=26, height=26, stroke_width=2.5, color=ft.Colors.PRIMARY),
        )
        page.update()

        data = await get_platform_objectives_api(token)
        objs = data.get("objectives", [])
        coins_bal = data.get("coins_balance", 0)

        # Header with Coins balance
        coins_pill = ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=4),
            border_radius=ft.BorderRadius.all(12),
            gradient=ft.LinearGradient(
                colors=[ft.Colors.AMBER_600, ft.Colors.ORANGE_600],
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
            ),
            content=ft.Row(
                spacing=4,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.TOKEN_ROUNDED, size=14, color=ft.Colors.WHITE),
                    ft.Text(f"{coins_bal} Nu-Coins", size=11, weight=ft.FontWeight.W_800, color=ft.Colors.WHITE),
                ],
            ),
        )

        obj_list = ft.ListView(spacing=8, expand=True)

        for obj in objs:
            code = obj.get("code")
            title = obj.get("title", "Objective")
            desc = obj.get("description", "")
            reward = obj.get("reward_coins", 50)
            target = obj.get("target_value", 1)
            current = obj.get("current_value", 0)
            is_completed = obj.get("is_completed", False)
            can_claim = obj.get("can_claim", False)

            frac = min(current / max(target, 1), 1.0)

            # Trailing action widget:
            # - If can_claim: vibrant Claim button.
            # - If already claimed: clean ✓ Claimed badge.
            # - If in progress: clean ratio pill (e.g. 2/5). ZERO GRAY BOXES!
            if can_claim:
                claim_btn = ft.ElevatedButton(
                    content=ft.Text(f"Claim +{reward} 🪙", size=11, weight=ft.FontWeight.W_700),
                    bgcolor=ft.Colors.PRIMARY,
                    color=ft.Colors.WHITE,
                    height=30,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), elevation=0),
                )

                async def _claim(c_code=code, btn=claim_btn):
                    btn.disabled = True
                    page.update()
                    res = await claim_objective_reward_api(token, c_code)
                    if res.get("status") == "success":
                        show_page_snackbar(page, f"Reward claimed! +{res.get('reward_coins')} Nu-Coins! 🎉")
                        if on_coins_changed:
                            on_coins_changed()
                        await _load_objectives()
                    else:
                        show_page_snackbar(page, res.get("message", "Error claiming reward."))
                        btn.disabled = False
                        page.update()

                claim_btn.on_click = (lambda c=code, b=claim_btn: lambda _: page.run_task(_claim, c, b))()
                trailing_widget = claim_btn
            elif is_completed:
                trailing_widget = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=ft.BorderRadius.all(8),
                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.GREEN),
                    content=ft.Row(
                        spacing=3,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=13, color=ft.Colors.GREEN_700),
                            ft.Text("Claimed", size=10.5, weight=ft.FontWeight.W_700, color=ft.Colors.GREEN_800),
                        ],
                    ),
                )
            else:
                # In progress: sleek ratio pill, NO disabled gray button
                trailing_widget = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=ft.BorderRadius.all(8),
                    bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                    content=ft.Text(f"{current}/{target}", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.GREY_600),
                )

            card = ft.Container(
                padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                border_radius=ft.BorderRadius.all(12),
                bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Column(
                            spacing=3,
                            tight=True,
                            expand=True,
                            controls=[
                                ft.Row(
                                    spacing=6,
                                    tight=True,
                                    controls=[
                                        ft.Text(title, size=12.5, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                        ft.Container(
                                            padding=ft.Padding.symmetric(horizontal=6, vertical=1.5),
                                            border_radius=ft.BorderRadius.all(6),
                                            bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.AMBER),
                                            content=ft.Text(f"+{reward}🪙", size=9.5, weight=ft.FontWeight.W_800, color=ft.Colors.AMBER_900),
                                        ),
                                    ],
                                ),
                                ft.Text(desc, size=11, color=ft.Colors.GREY_500, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                ft.ProgressBar(
                                    value=frac,
                                    color=ft.Colors.PRIMARY if not is_completed else ft.Colors.GREEN,
                                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                                    height=3.5,
                                ),
                            ],
                        ),
                        trailing_widget,
                    ],
                ),
            )
            obj_list.controls.append(card)

        await _swap_body_smoothly(
            ft.Column(
                tight=True,
                spacing=8,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Text("Platform Prelim Objectives", size=12.5, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                            coins_pill,
                        ],
                    ),
                    ft.Container(content=obj_list, height=320),
                ],
            )
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 2. CAMPUS LEADERBOARDS TAB
    # ─────────────────────────────────────────────────────────────────────────
    async def _load_leaderboard(filter_type: str = "duo_streaks"):
        body_container.content = ft.Container(
            padding=30,
            alignment=ft.Alignment.CENTER,
            content=ft.ProgressRing(width=26, height=26, stroke_width=2.5, color=ft.Colors.PRIMARY),
        )
        page.update()

        leaders = await get_study_leaderboard_api(token, filter_type=filter_type)
        board_list = ft.ListView(spacing=6, expand=True)

        def _set_board_filter(f_type: str):
            page.run_task(_load_leaderboard, f_type)

        filter_row = ft.Row(
            spacing=6,
            controls=[
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                    border_radius=ft.BorderRadius.all(8),
                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if filter_type == "duo_streaks" else ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                    ink=True,
                    on_click=lambda _: _set_board_filter("duo_streaks"),
                    content=ft.Text("🔥 Duo Streaks", size=11, weight=ft.FontWeight.W_700 if filter_type == "duo_streaks" else ft.FontWeight.W_500, color=ft.Colors.PRIMARY if filter_type == "duo_streaks" else ft.Colors.ON_SURFACE),
                ),
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                    border_radius=ft.BorderRadius.all(8),
                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if filter_type == "today" else ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                    ink=True,
                    on_click=lambda _: _set_board_filter("today"),
                    content=ft.Text("⏱ Today's Focus", size=11, weight=ft.FontWeight.W_700 if filter_type == "today" else ft.FontWeight.W_500, color=ft.Colors.PRIMARY if filter_type == "today" else ft.Colors.ON_SURFACE),
                ),
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                    border_radius=ft.BorderRadius.all(8),
                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if filter_type == "weekly" else ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                    ink=True,
                    on_click=lambda _: _set_board_filter("weekly"),
                    content=ft.Text("⚡ Solo Streaks", size=11, weight=ft.FontWeight.W_700 if filter_type == "weekly" else ft.FontWeight.W_500, color=ft.Colors.PRIMARY if filter_type == "weekly" else ft.Colors.ON_SURFACE),
                ),
            ],
        )

        if not leaders:
            board_list.controls.append(
                ft.Container(
                    padding=24,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text("No leaderboard entries recorded yet. Be the first!", size=11.5, color=ft.Colors.GREY_500),
                )
            )
        else:
            for item in leaders:
                rank = item.get("rank", 1)
                medal = "🥇" if rank == 1 else ("🥈" if rank == 2 else ("🥉" if rank == 3 else f"#{rank}"))

                if filter_type == "duo_streaks":
                    p_a = item.get("partner_a", {})
                    p_b = item.get("partner_b", {})
                    name_a = f"{p_a.get('first_name', 'Student')} {p_a.get('last_name', '')}".strip()
                    name_b = f"{p_b.get('first_name', 'Partner')} {p_b.get('last_name', '')}".strip()
                    d_streak = item.get("duo_streak", 0)
                    is_my_duo = item.get("is_my_duo", False)

                    p_a_uni = p_a.get("university") or p_b.get("university")
                    raw_target = str(item.get("target_exam") or "").strip()
                    clean_target = raw_target if (raw_target and not any(term in raw_target.upper() for term in ["JAMB", "UTME", "GENERAL"])) else None
                    sub_label = p_a_uni or (f"{clean_target} Focus" if clean_target else "Campus Duos")

                    row_content = ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(
                                spacing=8,
                                tight=True,
                                controls=[
                                    ft.Text(medal, size=14, weight=ft.FontWeight.W_800),
                                    ft.Column(
                                        spacing=1,
                                        tight=True,
                                        controls=[
                                            ft.Text(f"{name_a} & {name_b}", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY if is_my_duo else ft.Colors.ON_SURFACE),
                                            ft.Text(sub_label, size=10, color=ft.Colors.GREY_500),
                                        ],
                                    ),
                                ],
                            ),
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                                border_radius=ft.BorderRadius.all(6),
                                bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.AMBER),
                                content=ft.Text(f"🔥 {d_streak}d Duo", size=11, weight=ft.FontWeight.W_800, color=ft.Colors.AMBER_900),
                            ),
                        ],
                    )
                else:
                    first = item.get("first_name") or item.get("username") or "Student"
                    last = item.get("last_name") or ""
                    full_n = f"{first} {last}".strip()
                    uni = item.get("university") or "Campus Peer"
                    study_mins = item.get("study_minutes", 0)
                    streak = item.get("streak", 0)
                    is_me = item.get("is_me", False)

                    metric_str = f"⏱ {study_mins} mins" if filter_type == "today" and study_mins > 0 else f"🔥 {streak}d streak"

                    row_content = ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(
                                spacing=8,
                                tight=True,
                                controls=[
                                    ft.Text(medal, size=14, weight=ft.FontWeight.W_800),
                                    ft.Column(
                                        spacing=1,
                                        tight=True,
                                        controls=[
                                            ft.Row(
                                                spacing=4,
                                                tight=True,
                                                controls=[
                                                    ft.Text(full_n, size=12, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY if is_me else ft.Colors.ON_SURFACE),
                                                    ft.Text("(You)" if is_me else "", size=10, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY),
                                                ],
                                            ),
                                            ft.Text(uni, size=10, color=ft.Colors.GREY_500),
                                        ],
                                    ),
                                ],
                            ),
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                                border_radius=ft.BorderRadius.all(6),
                                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                                content=ft.Text(metric_str, size=11, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY),
                            ),
                        ],
                    )

                board_list.controls.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                        border_radius=ft.BorderRadius.all(10),
                        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                        content=row_content,
                    )
                )

        await _swap_body_smoothly(
            ft.Column(
                tight=True,
                spacing=8,
                controls=[
                    filter_row,
                    ft.Container(content=board_list, height=320),
                ],
            )
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 3. SHARED PACKS TAB
    # ─────────────────────────────────────────────────────────────────────────
    async def _load_shared_packs():
        body_container.content = ft.Container(
            padding=30,
            alignment=ft.Alignment.CENTER,
            content=ft.ProgressRing(width=26, height=26, stroke_width=2.5, color=ft.Colors.PRIMARY),
        )
        page.update()

        nonlocal partnership_id, partner, p_name
        if not partnership_id:
            p_res = await get_active_partnership(token)
            if p_res and p_res.get("has_partnership"):
                p_obj = p_res.get("partnership", {})
                partnership_id = p_obj.get("id")
                partner = p_obj.get("partner")
                if partner:
                    p_name = f"{partner.get('first_name', 'Partner')} {partner.get('last_name', '')}".strip()

        shares = []
        if partnership_id:
            shares = await get_shared_study_packs_api(token, partnership_id)

        pack_list = ft.ListView(spacing=8, expand=True)

        if not shares:
            pack_list.controls.append(
                ft.Container(
                    padding=24,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                        controls=[
                            ft.Icon(ft.Icons.FOLDER_OFF_ROUNDED, size=28, color=ft.Colors.GREY_400),
                            ft.Text("No shared packs yet", size=12.5, weight=ft.FontWeight.W_700),
                            ft.Text("Share materials with your partner using the 'Share Pack' button to study together!", size=11, color=ft.Colors.GREY_500, text_align=ft.TextAlign.CENTER),
                        ],
                    ),
                )
            )
        else:
            for s in shares:
                share_id = s.get("id")
                pack_id = s.get("pack_id")
                title = s.get("title", "Study Pack")
                category = s.get("category", "General")
                q_count = s.get("questions_count", 0)
                is_mine = s.get("is_sent_by_me", False)
                status = s.get("status", "pending")
                sender_name = s.get("sender_name", "Partner")

                action_controls = []
                if not is_mine and status == "pending":
                    accept_btn = ft.ElevatedButton(
                        content=ft.Text("Accept & Download", size=11, weight=ft.FontWeight.W_700),
                        bgcolor=ft.Colors.PRIMARY,
                        color=ft.Colors.WHITE,
                        height=30,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), elevation=0),
                    )

                    async def _accept_pack(sid=share_id, btn=accept_btn):
                        btn.disabled = True
                        page.update()
                        res = await accept_shared_study_pack_api(token, partnership_id, sid)
                        if not res.get("error"):
                            show_page_snackbar(page, "Study pack accepted! Added to your vault 📚")
                            await _load_shared_packs()
                        else:
                            show_page_snackbar(page, res.get("error", "Error accepting pack."))
                            btn.disabled = False
                            page.update()

                    accept_btn.on_click = (lambda sid=share_id, b=accept_btn: lambda _: page.run_task(_accept_pack, sid, b))()
                    action_controls.append(accept_btn)
                else:
                    duel_btn = ft.ElevatedButton(
                        content=ft.Row(
                            tight=True,
                            spacing=4,
                            controls=[
                                ft.Icon(ft.Icons.FLASH_ON_ROUNDED, size=13, color=ft.Colors.WHITE),
                                ft.Text("Duel on Pack", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                            ],
                        ),
                        bgcolor=ft.Colors.ORANGE_800,
                        height=30,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), elevation=0),
                    )

                    async def _start_pack_duel(pid=pack_id, p_title=title):
                        res = await generate_quickfire_from_pack_api(token, partnership_id, pid)
                        if res.get("status") == "success":
                            questions = res.get("questions", [])
                            start_quickfire_duel_flow(
                                page=page,
                                token=token,
                                partnership_id=partnership_id,
                                pack_id=pid,
                                pack_title=p_title,
                                partner_name=p_name,
                                is_accepting_challenge=False,
                                seeded_questions=questions,
                                on_completed=on_coins_changed,
                            )
                        else:
                            show_page_snackbar(page, "Error preparing pack duel.")

                    duel_btn.on_click = (lambda pid=pack_id, pt=title: lambda _: page.run_task(_start_pack_duel, pid, pt))()
                    action_controls.append(duel_btn)

                async def _preview_pack(pid=pack_id, p_title=title):
                    p_res = await preview_shared_study_pack_api(token, partnership_id, pid)
                    if p_res and not p_res.get("error"):
                        fcs = p_res.get("flashcards", [])
                        show_flashcard_preview_dialog(
                            page=page,
                            token=token,
                            partnership_id=partnership_id,
                            pack_id=pid,
                            pack_title=p_title,
                            partner_name=p_name,
                            flashcards=fcs,
                            on_duel_start=on_coins_changed,
                        )
                    else:
                        show_page_snackbar(page, p_res.get("error", "Error loading pack preview."))

                preview_btn = ft.OutlinedButton(
                    content=ft.Row(
                        tight=True,
                        spacing=3,
                        controls=[
                            ft.Icon(ft.Icons.STYLE_ROUNDED, size=13, color=ft.Colors.PRIMARY),
                            ft.Text("Preview", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY),
                        ],
                    ),
                    height=30,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                    on_click=(lambda pid=pack_id, pt=title: lambda _: page.run_task(_preview_pack, pid, pt))(),
                )
                action_controls.append(preview_btn)

                card = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                    border_radius=ft.BorderRadius.all(10),
                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Column(
                                spacing=2,
                                tight=True,
                                expand=True,
                                controls=[
                                    ft.Text(title, size=12.5, weight=ft.FontWeight.W_700, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                    ft.Text(f"{q_count} Questions • Shared by {'You' if is_mine else sender_name}", size=10.5, color=ft.Colors.GREY_500),
                                ],
                            ),
                            ft.Row(spacing=4, controls=action_controls),
                        ],
                    ),
                )
                pack_list.controls.append(card)

        # Header with Share Pack CTA button
        share_cta = ft.ElevatedButton(
            content=ft.Row(
                tight=True,
                spacing=4,
                controls=[
                    ft.Icon(ft.Icons.ADD_ROUNDED, size=14, color=ft.Colors.WHITE),
                    ft.Text("Share Pack", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                ],
            ),
            bgcolor=ft.Colors.PRIMARY,
            height=30,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), elevation=0),
            on_click=lambda _: on_open_share_dialog() if on_open_share_dialog else None,
        )

        await _swap_body_smoothly(
            ft.Column(
                tight=True,
                spacing=8,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Text("Shared Study Packs Tray", size=12.5, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                            share_cta if on_open_share_dialog else ft.Container(),
                        ],
                    ),
                    ft.Container(content=pack_list, height=320),
                ],
            )
        )

    # Initial Render
    _render_tab_headers()
    _switch_tab(current_tab)

    return ft.Container(
        margin=ft.Margin.only(bottom=16),
        padding=ft.Padding.symmetric(horizontal=16, vertical=14),
        border_radius=ft.BorderRadius.all(18),
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.10, ft.Colors.PRIMARY)),
        shadow=ft.BoxShadow(
            blur_radius=12,
            color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
            offset=ft.Offset(0, 3),
        ),
        content=ft.Column(
            tight=True,
            spacing=10,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        tab_buttons_row,
                    ],
                ),
                body_container,
            ],
        ),
    )
