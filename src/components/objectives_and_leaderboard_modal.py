"""
objectives_and_leaderboard_modal.py
──────────────────────────────────────────────────────────────────────────────
Interactive Modal for:
- Platform Prelim Objectives & Nu-Coins Wallet Ledger
- Shared Study Packs between Duo Partners
- Real-time Study & Duo Streak Leaderboards
──────────────────────────────────────────────────────────────────────────────
"""

import asyncio
import flet as ft
from typing import Optional, Callable

from src.utils.file_opener import show_page_snackbar
from src.requests.objectives import (
    get_platform_objectives_api,
    claim_objective_reward_api,
    get_coin_wallet_ledger_api,
)
from src.requests.study_partners import (
    get_shared_study_packs_api,
    accept_shared_study_pack_api,
    get_study_leaderboard_api,
    generate_quickfire_from_pack_api,
)
from src.components.partner_challenge_modal import start_quickfire_duel_flow


def show_objectives_and_leaderboard_dialog(
    page: ft.Page,
    token: str,
    partnership_id: Optional[str] = None,
    partner: Optional[dict] = None,
    initial_tab: str = "objectives",
    on_coins_changed: Optional[Callable] = None,
):
    """
    Renders the unified modal for Objectives, Nu-Coins Ledger, Shared Packs, and Leaderboard.
    """
    current_tab = initial_tab
    p_name = partner.get("first_name", "Partner") if partner else "Partner"

    tab_header = ft.Row(
        alignment=ft.MainAxisAlignment.START,
        spacing=8,
    )

    body_container = ft.Container(
        expand=True,
        height=480,
    )

    dlg = ft.AlertDialog(
        modal=True,
        shape=ft.RoundedRectangleBorder(radius=20),
        bgcolor=ft.Colors.SURFACE,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(
                    spacing=8,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.WORKSPACE_PREMIUM_ROUNDED, color=ft.Colors.PRIMARY, size=24),
                        ft.Text("Nu-Coins & Study Milestones", size=16, weight=ft.FontWeight.W_800),
                    ],
                ),
                ft.IconButton(
                    icon=ft.Icons.CLOSE_ROUNDED,
                    icon_size=20,
                    on_click=lambda _: _close(),
                ),
            ],
        ),
        content=ft.Container(
            width=540,
            content=ft.Column(
                tight=True,
                spacing=12,
                controls=[
                    tab_header,
                    body_container,
                ],
            ),
        ),
        actions=[
            ft.TextButton("Close", on_click=lambda _: _close()),
        ],
    )

    def _close():
        dlg.open = False
        page.update()

    def _switch_tab(tab_key: str):
        nonlocal current_tab
        current_tab = tab_key
        _rebuild_tabs()
        if tab_key == "objectives":
            page.run_task(_load_objectives_tab)
        elif tab_key == "shared_packs":
            page.run_task(_load_shared_packs_tab)
        elif tab_key == "leaderboard":
            page.run_task(_load_leaderboard_tab, "duo_streaks" if partnership_id else "today")

    def _rebuild_tabs():
        tab_header.controls.clear()
        tabs = [
            ("objectives", "🪙 Objectives & Coins", ft.Icons.TOKEN_ROUNDED),
            ("shared_packs", "📚 Shared Packs", ft.Icons.FOLDER_SHARED_ROUNDED),
            ("leaderboard", "🏆 Leaderboards", ft.Icons.LEADERBOARD_ROUNDED),
        ]
        for key, label, icon in tabs:
            is_active = (key == current_tab)
            btn = ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                border_radius=ft.BorderRadius.all(10),
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if is_active else ft.Colors.TRANSPARENT,
                ink=True,
                on_click=(lambda k=key: lambda _: _switch_tab(k))(),
                content=ft.Row(
                    spacing=6,
                    tight=True,
                    controls=[
                        ft.Icon(icon, size=15, color=ft.Colors.PRIMARY if is_active else ft.Colors.GREY_500),
                        ft.Text(label, size=11.5, weight=ft.FontWeight.W_700 if is_active else ft.FontWeight.W_500, color=ft.Colors.PRIMARY if is_active else ft.Colors.ON_SURFACE),
                    ],
                ),
            )
            tab_header.controls.append(btn)
        page.update()

    # ─────────────────────────────────────────────────────────────────────────
    # 1. OBJECTIVES TAB
    # ─────────────────────────────────────────────────────────────────────────
    async def _load_objectives_tab():
        body_container.content = ft.Container(
            alignment=ft.Alignment.CENTER,
            content=ft.ProgressRing(width=28, height=28, stroke_width=2.5, color=ft.Colors.PRIMARY),
        )
        page.update()

        data = await get_platform_objectives_api(token)
        objs = data.get("objectives", [])
        coins_bal = data.get("coins_balance", 0)

        # Header Wallet Card
        wallet_card = ft.Container(
            padding=ft.Padding.symmetric(horizontal=16, vertical=12),
            border_radius=ft.BorderRadius.all(14),
            gradient=ft.LinearGradient(
                colors=[ft.Colors.AMBER_700, ft.Colors.ORANGE_800],
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
            ),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Column(
                        spacing=2,
                        tight=True,
                        controls=[
                            ft.Text("Nu-Coins Balance", size=11, color=ft.Colors.with_opacity(0.85, ft.Colors.WHITE), weight=ft.FontWeight.W_600),
                            ft.Row(
                                spacing=6,
                                tight=True,
                                controls=[
                                    ft.Icon(ft.Icons.MONETIZATION_ON_ROUNDED, color=ft.Colors.WHITE, size=24),
                                    ft.Text(f"{coins_bal} Coins", size=22, weight=ft.FontWeight.W_900, color=ft.Colors.WHITE),
                                ],
                            ),
                        ],
                    ),
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                        border_radius=ft.BorderRadius.all(8),
                        bgcolor=ft.Colors.with_opacity(0.20, ft.Colors.BLACK),
                        content=ft.Text("Earn via Duels & Streaks", size=10.5, color=ft.Colors.WHITE, weight=ft.FontWeight.W_700),
                    ),
                ],
            ),
        )

        obj_list = ft.ListView(spacing=10, expand=True)
        if not objs:
            obj_list.controls.append(ft.Container(padding=20, alignment=ft.Alignment.CENTER, content=ft.Text("No active objectives found.", color=ft.Colors.GREY_500)))
        else:
            for item in objs:
                code = item.get("code")
                title = item.get("title")
                desc = item.get("description")
                reward = item.get("reward_coins", 0)
                curr = item.get("current_value", 0)
                tgt = max(1, item.get("target_value", 1))
                can_claim = item.get("can_claim", False)
                is_completed = item.get("is_completed", False)
                progress_val = min(1.0, curr / tgt)

                claim_btn = ft.ElevatedButton(
                    content=ft.Text(f"Claim +{reward}" if not is_completed else "Claimed ✓", size=11, weight=ft.FontWeight.W_700),
                    bgcolor=ft.Colors.PRIMARY if can_claim else ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE),
                    color=ft.Colors.WHITE if can_claim else ft.Colors.GREY_500,
                    disabled=(not can_claim),
                    height=32,
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
                        await _load_objectives_tab()
                    else:
                        show_page_snackbar(page, res.get("message", "Error claiming reward."))
                        btn.disabled = False
                        page.update()

                claim_btn.on_click = (lambda c=code, b=claim_btn: lambda _: page.run_task(_claim, c, b))()

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
                                    ft.Text(desc, size=11, color=ft.Colors.GREY_500),
                                    ft.Row(
                                        spacing=8,
                                        tight=True,
                                        controls=[
                                            ft.Container(
                                                width=160,
                                                content=ft.ProgressBar(value=progress_val, color=ft.Colors.PRIMARY, bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY), height=5),
                                            ),
                                            ft.Text(f"{curr} / {tgt}", size=10, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_600),
                                        ],
                                    ),
                                ],
                            ),
                            claim_btn,
                        ],
                    ),
                )
                obj_list.controls.append(card)

        body_container.content = ft.Column(
            tight=True,
            spacing=10,
            expand=True,
            controls=[
                wallet_card,
                ft.Text("Platform Learning Objectives", size=12, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                ft.Container(content=obj_list, expand=True),
            ],
        )
        page.update()

    # ─────────────────────────────────────────────────────────────────────────
    # 2. SHARED STUDY PACKS TAB
    # ─────────────────────────────────────────────────────────────────────────
    async def _load_shared_packs_tab():
        if not partnership_id:
            body_container.content = ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=20,
                content=ft.Text("Pair up with an accountability partner to share study packs!", color=ft.Colors.GREY_500),
            )
            page.update()
            return

        body_container.content = ft.Container(
            alignment=ft.Alignment.CENTER,
            content=ft.ProgressRing(width=28, height=28, stroke_width=2.5, color=ft.Colors.PRIMARY),
        )
        page.update()

        shares = await get_shared_study_packs_api(token, partnership_id)
        pack_list = ft.ListView(spacing=10, expand=True)

        if not shares:
            pack_list.controls.append(
                ft.Container(
                    padding=30,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                        controls=[
                            ft.Icon(ft.Icons.FOLDER_OFF_ROUNDED, size=32, color=ft.Colors.GREY_400),
                            ft.Text("No shared packs yet", size=13, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                            ft.Text("Share any study pack from your Self-Study Hub with your partner to duel on it!", size=11, color=ft.Colors.GREY_500, text_align=ft.TextAlign.CENTER),
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
                fc_count = s.get("flashcards_count", 0)
                is_mine = s.get("is_sent_by_me", False)
                status = s.get("status", "pending")
                sender_name = s.get("sender_name", "Partner")

                action_controls = []
                if not is_mine and status == "pending":
                    accept_btn = ft.ElevatedButton(
                        content=ft.Text("Accept & Download", size=11, weight=ft.FontWeight.W_700),
                        bgcolor=ft.Colors.PRIMARY,
                        color=ft.Colors.WHITE,
                        height=32,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), elevation=0),
                    )

                    async def _accept_pack(sid=share_id, btn=accept_btn):
                        btn.disabled = True
                        page.update()
                        res = await accept_shared_study_pack_api(token, partnership_id, sid)
                        if not res.get("error"):
                            show_page_snackbar(page, f"Study pack accepted! Added to your collection 📚")
                            await _load_shared_packs_tab()
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
                                ft.Icon(ft.Icons.FLASH_ON_ROUNDED, size=14, color=ft.Colors.WHITE),
                                ft.Text("Duel on Pack", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                            ],
                        ),
                        bgcolor=ft.Colors.ORANGE_800,
                        height=32,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), elevation=0),
                    )

                    async def _start_pack_duel(pid=pack_id, p_title=title):
                        _close()
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
                                spacing=2,
                                tight=True,
                                expand=True,
                                controls=[
                                    ft.Row(
                                        spacing=6,
                                        tight=True,
                                        controls=[
                                            ft.Text(title, size=13, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                            ft.Container(
                                                padding=ft.Padding.symmetric(horizontal=6, vertical=1.5),
                                                border_radius=ft.BorderRadius.all(6),
                                                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                                                content=ft.Text(category, size=9.5, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY),
                                            ),
                                        ],
                                    ),
                                    ft.Text(f"{q_count} Questions • {fc_count} Flashcards • Shared by {'You' if is_mine else sender_name}", size=11, color=ft.Colors.GREY_500),
                                ],
                            ),
                            ft.Row(spacing=6, controls=action_controls),
                        ],
                    ),
                )
                pack_list.controls.append(card)

        body_container.content = pack_list
        page.update()

    # ─────────────────────────────────────────────────────────────────────────
    # 3. LEADERBOARDS TAB
    # ─────────────────────────────────────────────────────────────────────────
    async def _load_leaderboard_tab(filter_type: str = "duo_streaks"):
        body_container.content = ft.Container(
            alignment=ft.Alignment.CENTER,
            content=ft.ProgressRing(width=28, height=28, stroke_width=2.5, color=ft.Colors.PRIMARY),
        )
        page.update()

        leaders = await get_study_leaderboard_api(token, filter_type=filter_type)
        board_list = ft.ListView(spacing=8, expand=True)

        # Filter toggle row
        def _set_board_filter(f_type: str):
            page.run_task(_load_leaderboard_tab, f_type)

        filter_row = ft.Row(
            spacing=8,
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
                    content=ft.Text("⏱ Study Time (Today)", size=11, weight=ft.FontWeight.W_700 if filter_type == "today" else ft.FontWeight.W_500, color=ft.Colors.PRIMARY if filter_type == "today" else ft.Colors.ON_SURFACE),
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
            board_list.controls.append(ft.Container(padding=20, alignment=ft.Alignment.CENTER, content=ft.Text("No leaderboard entries yet. Be the first!", color=ft.Colors.GREY_500)))
        else:
            for item in leaders:
                rank = item.get("rank", 1)
                is_mine = item.get("is_my_duo", False) or item.get("is_me", False)

                medal_icon = None
                if rank == 1:
                    rank_badge = ft.Text("🥇", size=16)
                elif rank == 2:
                    rank_badge = ft.Text("🥈", size=16)
                elif rank == 3:
                    rank_badge = ft.Text("🥉", size=16)
                else:
                    rank_badge = ft.Text(f"#{rank}", size=12, weight=ft.FontWeight.W_800, color=ft.Colors.GREY_500)

                if filter_type == "duo_streaks":
                    p_a = item.get("partner_a", {})
                    p_b = item.get("partner_b", {})
                    duo_name = f"{p_a.get('first_name', 'Learner')} & {p_b.get('first_name', 'Partner')}"
                    metric_str = f"🔥 {item.get('duo_streak', 0)} Days Duo Streak"
                else:
                    u_name = f"{item.get('first_name', '')} {item.get('last_name', '')}".strip() or item.get("username", "Learner")
                    metric_str = f"🔥 {item.get('streak', 0)}d • 🪙 {item.get('coins_balance', 0)} coins"
                    duo_name = u_name

                row_card = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                    border_radius=ft.BorderRadius.all(10),
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY) if is_mine else ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.20, ft.Colors.PRIMARY) if is_mine else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(
                                spacing=10,
                                tight=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Container(width=30, alignment=ft.Alignment.CENTER, content=rank_badge),
                                    ft.Column(
                                        spacing=1,
                                        tight=True,
                                        controls=[
                                            ft.Row(
                                                spacing=6,
                                                tight=True,
                                                controls=[
                                                    ft.Text(duo_name, size=12.5, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY if is_mine else ft.Colors.ON_SURFACE),
                                                    ft.Container(
                                                        visible=is_mine,
                                                        padding=ft.Padding.symmetric(horizontal=5, vertical=1),
                                                        border_radius=ft.BorderRadius.all(4),
                                                        bgcolor=ft.Colors.PRIMARY,
                                                        content=ft.Text("YOU", size=8, weight=ft.FontWeight.W_900, color=ft.Colors.WHITE),
                                                    ),
                                                ],
                                            ),
                                            ft.Text(metric_str, size=11, color=ft.Colors.GREY_600),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                )
                board_list.controls.append(row_card)

        body_container.content = ft.Column(
            tight=True,
            spacing=10,
            expand=True,
            controls=[
                filter_row,
                ft.Container(content=board_list, expand=True),
            ],
        )
        page.update()

    # Initial view
    _rebuild_tabs()
    _switch_tab(initial_tab)

    page.overlay.append(dlg)
    dlg.open = True
    page.update()
