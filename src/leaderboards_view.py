"""
src/leaderboards_view.py
──────────────────────────────────────────────────────────────────────────────
Dedicated Full-Screen View for Campus Leaderboards, Prelim Objectives,
Nu-Coins Wallet, and Duo Duel History.
Accessible directly from Home Dashboard Action Card and Study Duo Cockpit.
──────────────────────────────────────────────────────────────────────────────
"""

import asyncio
from datetime import datetime, timezone
import flet as ft

from src.components.bottom_appbar import PersistentBottomAppBar
from src.requests.objectives import (
    get_platform_objectives_api,
    claim_objective_reward_api,
    get_coin_wallet_ledger_api,
    DEFAULT_PRELIM_OBJECTIVES,
)
from src.requests.study_partners import (
    get_study_leaderboard_api,
    get_active_partnership,
    get_challenge_history_api,
)
from src.components.partner_challenge_modal import show_duel_results_dialog
from src.utils.file_opener import show_page_snackbar


async def leaderboards_view(
    page: ft.Page,
    initial_tab: str = "objectives",
    back_target: str = "/dashboard"
) -> ft.View:
    current_tab = initial_tab or "objectives"
    token_box = [None]
    partnership_id_box = [None]
    partner_box = [{}]
    coins_balance_box = [0]

    content_area = ft.Container(
        expand=True,
        opacity=1,
        offset=ft.Offset(0, 0),
        animate_opacity=ft.Animation(360, ft.AnimationCurve.DECELERATE),
        animate_offset=ft.Animation(360, ft.AnimationCurve.DECELERATE),
    )

    async def _swap_content_smoothly(new_content, is_initial: bool = False):
        if is_initial:
            content_area.content = new_content
            content_area.opacity = 1
            content_area.offset = ft.Offset(0, 0)
            return

        content_area.opacity = 0
        content_area.offset = ft.Offset(0, 0.04)
        page.update()
        await asyncio.sleep(0.06)
        content_area.content = new_content
        content_area.opacity = 1
        content_area.offset = ft.Offset(0, 0)
        page.update()

    coins_badge_text = ft.Text("... 🪙", size=12, weight=ft.FontWeight.W_800, color=ft.Colors.AMBER_900)

    # ── Helper to retrieve current token reliably ────────────────────────────
    async def _get_auth_token():
        if token_box[0]:
            return token_box[0]
        tok = None
        if hasattr(page, "session") and hasattr(page.session, "store"):
            tok = page.session.store.get("session_auth_token") or page.session.store.get("auth_token")
        if not tok and hasattr(page, "shared_preferences"):
            tok = await page.shared_preferences.get("auth_token")
        token_box[0] = tok
        return tok

    coins_badge = ft.Container(
        padding=ft.Padding.symmetric(horizontal=10, vertical=5),
        border_radius=ft.BorderRadius.all(12),
        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.AMBER_700)),
        content=ft.Row(
            spacing=4,
            tight=True,
            controls=[
                ft.Icon(ft.Icons.MONETIZATION_ON_ROUNDED, size=15, color=ft.Colors.AMBER_800),
                coins_badge_text,
            ],
        ),
        ink=True,
        on_click=lambda _: _open_ledger_dialog(),
    )

    tab_buttons_row = ft.Row(spacing=8, tight=True)

    def _open_ledger_dialog(e=None):
        ledger_dlg = [None]
        def _close_dlg(e=None):
            if ledger_dlg[0]:
                ledger_dlg[0].open = False
                page.update()

        ledger_col = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, height=340)

        async def _load_txs():
            tok = await _get_auth_token()
            if not tok:
                return
            res = await get_coin_wallet_ledger_api(tok)
            ledger_col.controls.clear()
            txs = res.get("transactions", [])
            if not txs:
                ledger_col.controls.append(
                    ft.Container(
                        padding=30,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Text("No coin transactions yet. Complete duels and objectives!", size=12, color=ft.Colors.GREY_500),
                    )
                )
            else:
                for tx in txs:
                    amt = tx.get("amount", 0)
                    is_gain = amt >= 0
                    cat = tx.get("category", "reward").replace("_", " ").title()
                    desc = tx.get("description") or cat
                    created = (tx.get("created_at") or "")[:10]
                    ledger_col.controls.append(
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                            border_radius=ft.BorderRadius.all(10),
                            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Column(
                                        spacing=2,
                                        tight=True,
                                        controls=[
                                            ft.Text(desc, size=12, weight=ft.FontWeight.W_700),
                                            ft.Text(f"{cat} • {created}", size=10, color=ft.Colors.GREY_500),
                                        ],
                                    ),
                                    ft.Text(
                                        f"+{amt} 🪙" if is_gain else f"{amt} 🪙",
                                        size=13,
                                        weight=ft.FontWeight.W_800,
                                        color=ft.Colors.GREEN_700 if is_gain else ft.Colors.RED_600,
                                    ),
                                ],
                            ),
                        )
                    )
            page.update()

        ledger_dlg[0] = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=18),
            bgcolor=ft.Colors.SURFACE,
            title=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row(
                        spacing=8,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED, color=ft.Colors.AMBER_800, size=22),
                            ft.Text("Nu-Coins Transaction Ledger", size=15, weight=ft.FontWeight.W_800),
                        ],
                    ),
                    ft.IconButton(ft.Icons.CLOSE_ROUNDED, icon_size=18, on_click=_close_dlg),
                ],
            ),
            content=ft.Container(width=460, content=ledger_col),
            actions=[ft.TextButton("Close", on_click=_close_dlg)],
        )
        page.overlay.append(ledger_dlg[0])
        ledger_dlg[0].open = True
        page.update()
        page.run_task(_load_txs)

    # ─────────────────────────────────────────────────────────────────────────
    # 1. TAB: PRELIM OBJECTIVES
    # ─────────────────────────────────────────────────────────────────────────
    async def _render_objectives_tab(is_initial: bool = False):
        if not is_initial:
            content_area.content = ft.Container(
                padding=40,
                alignment=ft.Alignment.CENTER,
                content=ft.ProgressRing(width=28, height=28, stroke_width=2.5, color=ft.Colors.PRIMARY),
            )
            page.update()

        tok = await _get_auth_token()
        res = await get_platform_objectives_api(tok) if tok else {}
        objectives = res.get("objectives", []) or DEFAULT_PRELIM_OBJECTIVES
        bal = res.get("coins_balance", 0)
        coins_balance_box[0] = bal
        coins_badge_text.value = f"{bal} 🪙"

        obj_list = ft.ListView(spacing=8, expand=True, padding=ft.Padding.symmetric(horizontal=16, vertical=8))

        # Overview banner
        obj_list.controls.append(
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                border_radius=ft.BorderRadius.all(12),
                bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.PRIMARY),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.15, ft.Colors.PRIMARY)),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Row(
                            spacing=10,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=ft.Colors.PRIMARY, size=20),
                                ft.Column(
                                    spacing=2,
                                    tight=True,
                                    controls=[
                                        ft.Text("Platform Learning Objectives", size=13, weight=ft.FontWeight.W_800),
                                        ft.Text("Hit core study milestones to unlock instant Nu-Coins.", size=11, color=ft.Colors.GREY_600),
                                    ],
                                ),
                            ],
                        ),
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                            border_radius=ft.BorderRadius.all(8),
                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER),
                            content=ft.Text(f"Balance: {bal} 🪙", size=11, weight=ft.FontWeight.W_800, color=ft.Colors.AMBER_900),
                        ),
                    ],
                ),
            )
        )

        for obj in objectives:
            code = obj.get("code")
            title = obj.get("title", "Objective")
            desc = obj.get("description", "")
            reward = obj.get("coin_reward") or obj.get("reward_coins", 20)
            cur = obj.get("current_value", 0)
            tgt = max(obj.get("target_value", 1), 1)
            is_comp = obj.get("is_completed", False)
            is_clm = obj.get("is_claimed", False)
            can_claim = is_comp and not is_clm

            ratio = min(cur / tgt, 1.0)
            prog_bar = ft.ProgressBar(value=ratio, height=5, color=ft.Colors.PRIMARY, bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY), border_radius=3)

            # Right action control — ZERO disabled gray boxes!
            if is_clm:
                right_ctrl = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                    border_radius=ft.BorderRadius.all(8),
                    bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.GREEN),
                    content=ft.Text("✓ Claimed", size=11, weight=ft.FontWeight.W_800, color=ft.Colors.GREEN_700),
                )
            elif can_claim:
                async def _do_claim(c_code=code, r_coins=reward):
                    c_res = await claim_objective_reward_api(tok, c_code)
                    if c_res.get("status") == "success":
                        show_page_snackbar(page, f"🎉 Claimed +{r_coins} Nu-Coins!")
                        page.run_task(_render_objectives_tab)
                    else:
                        show_page_snackbar(page, c_res.get("message") or c_res.get("error", "Error claiming reward."))

                right_ctrl = ft.ElevatedButton(
                    content=ft.Text(f"Claim +{reward} 🪙", size=11, weight=ft.FontWeight.W_800),
                    bgcolor=ft.Colors.AMBER_800,
                    color=ft.Colors.WHITE,
                    height=30,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), elevation=0),
                    on_click=(lambda c=code, r=reward: lambda _: page.run_task(_do_claim, c, r))(),
                )
            else:
                right_ctrl = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=ft.BorderRadius.all(6),
                    bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                    content=ft.Text(f"{cur}/{tgt}", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.GREY_600),
                )

            obj_list.controls.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                    border_radius=ft.BorderRadius.all(12),
                    bgcolor=ft.Colors.SURFACE,
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Column(
                                spacing=4,
                                tight=True,
                                expand=True,
                                controls=[
                                    ft.Row(
                                        spacing=6,
                                        tight=True,
                                        controls=[
                                            ft.Text(title, size=13, weight=ft.FontWeight.W_800),
                                            ft.Container(
                                                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                                border_radius=ft.BorderRadius.all(6),
                                                bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.AMBER),
                                                content=ft.Text(f"+{reward} 🪙", size=10, weight=ft.FontWeight.W_800, color=ft.Colors.AMBER_900),
                                            ),
                                        ],
                                    ),
                                    ft.Text(desc, size=11, color=ft.Colors.GREY_600),
                                    ft.Container(width=220, content=prog_bar),
                                ],
                            ),
                            right_ctrl,
                        ],
                    ),
                )
            )

        await _swap_content_smoothly(obj_list, is_initial=is_initial)

    # ─────────────────────────────────────────────────────────────────────────
    # 2. TAB: CAMPUS LEADERBOARDS
    # ─────────────────────────────────────────────────────────────────────────
    async def _render_leaderboards_tab(filter_type: str = "duo_streaks", is_initial: bool = False):
        if not is_initial:
            content_area.content = ft.Container(
                padding=40,
                alignment=ft.Alignment.CENTER,
                content=ft.ProgressRing(width=28, height=28, stroke_width=2.5, color=ft.Colors.PRIMARY),
            )
            page.update()

        tok = await _get_auth_token()
        board_data = await get_study_leaderboard_api(tok, filter_type=filter_type) if tok else []

        # If user has an active duo and remote list has no entries yet, display their real duo
        if filter_type == "duo_streaks" and not board_data and tok:
            try:
                p_res = await get_active_partnership(tok)
                if p_res and p_res.get("has_partnership"):
                    p_info = p_res.get("partnership", {})
                    p_partner = p_info.get("partner", {})
                    curr_u = (page.session.store.get("current_user") or {}) if hasattr(page, "session") and hasattr(page.session, "store") else {}
                    board_data = [{
                        "rank": 1,
                        "partnership_id": p_info.get("id"),
                        "duo_streak": p_info.get("duo_streak", 0),
                        "best_duo_streak": p_info.get("best_duo_streak", 0),
                        "target_exam": p_info.get("target_exam") or "Study Duo",
                        "partner_a": {"first_name": curr_u.get("first_name", "You"), "university": curr_u.get("university")},
                        "partner_b": {"first_name": p_partner.get("first_name", "Partner"), "university": p_partner.get("university")},
                        "is_my_duo": True,
                    }]
            except Exception:
                pass

        filters = [
            ("duo_streaks", "🔥 Duo Streaks"),
            ("today", "⏱ Today's Focus"),
            ("weekly", "⚡ Solo Streaks"),
        ]

        filter_row = ft.Row(
            spacing=8,
            controls=[
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                    border_radius=ft.BorderRadius.all(10),
                    bgcolor=ft.Colors.PRIMARY if f_id == filter_type else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                    ink=True,
                    on_click=(lambda fid=f_id: lambda _: page.run_task(_render_leaderboards_tab, fid, False))(),
                    content=ft.Text(
                        f_label,
                        size=11.5,
                        weight=ft.FontWeight.W_800 if f_id == filter_type else ft.FontWeight.W_600,
                        color=ft.Colors.WHITE if f_id == filter_type else ft.Colors.ON_SURFACE,
                    ),
                )
                for f_id, f_label in filters
            ],
        )

        board_list = ft.ListView(spacing=8, expand=True, padding=ft.Padding.symmetric(horizontal=16, vertical=8))
        board_list.controls.append(ft.Container(padding=ft.Padding.only(bottom=6), content=filter_row))

        if not board_data:
            empty_msg = "No active Duo Streaks recorded yet." if filter_type == "duo_streaks" else ("No study sessions logged today." if filter_type == "today" else "No active solo study streaks recorded yet.")
            empty_hint = "Study together daily with your accountability partner to claim the #1 spot!" if filter_type == "duo_streaks" else "Complete a quiz or exam simulation in the Self-Study Hub to appear on today's leaderboard!"
            board_list.controls.append(
                ft.Container(
                    padding=40,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                        controls=[
                            ft.Icon(ft.Icons.LEADERBOARD_ROUNDED, size=36, color=ft.Colors.GREY_400),
                            ft.Text(empty_msg, size=13, weight=ft.FontWeight.W_700),
                            ft.Text(empty_hint, size=11, color=ft.Colors.GREY_500, text_align=ft.TextAlign.CENTER),
                        ],
                    ),
                )
            )
        else:
            for item in board_data:
                rk = item.get("rank", 1)
                medals = {1: "🥇", 2: "🥈", 3: "🥉"}
                rank_str = medals.get(rk, f"#{rk}")

                if filter_type == "duo_streaks":
                    p_a = item.get("partner_a") or {}
                    p_b = item.get("partner_b") or {}
                    name = f"{p_a.get('first_name', 'Peer')} & {p_b.get('first_name', 'Peer')}"
                    uni = item.get("target_exam") or p_a.get("university") or "Campus Duo"
                    score_val = item.get("duo_streak", 0)
                    score_label = f"{score_val}d Streak 🔥"
                elif filter_type == "today":
                    fn = item.get("first_name", "")
                    ln = item.get("last_name", "")
                    name = f"{fn} {ln}".strip() or item.get("username", "Learner")
                    uni = item.get("university") or "Campus Peer"
                    score_val = item.get("study_minutes", 0)
                    score_label = f"{score_val} Mins ⏱"
                else: # weekly
                    fn = item.get("first_name", "")
                    ln = item.get("last_name", "")
                    name = f"{fn} {ln}".strip() or item.get("username", "Learner")
                    uni = item.get("university") or "Campus Peer"
                    score_val = item.get("streak", 0)
                    score_label = f"{score_val}d Streak ⚡"

                board_list.controls.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                        border_radius=ft.BorderRadius.all(12),
                        bgcolor=ft.Colors.SURFACE,
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Row(
                                    spacing=10,
                                    tight=True,
                                    controls=[
                                        ft.Text(rank_str, size=15, weight=ft.FontWeight.W_900),
                                        ft.Column(
                                            spacing=2,
                                            tight=True,
                                            controls=[
                                                ft.Text(name, size=13, weight=ft.FontWeight.W_800),
                                                ft.Text(uni, size=10.5, color=ft.Colors.GREY_500),
                                            ],
                                        ),
                                    ],
                                ),
                                ft.Text(score_label, size=12.5, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY),
                            ],
                        ),
                    )
                )

        await _swap_content_smoothly(board_list, is_initial=is_initial)

    # ─────────────────────────────────────────────────────────────────────────
    # 3. TAB: DUEL HISTORY
    # ─────────────────────────────────────────────────────────────────────────
    async def _render_duel_history_tab(is_initial: bool = False):
        if not is_initial:
            content_area.content = ft.Container(
                padding=40,
                alignment=ft.Alignment.CENTER,
                content=ft.ProgressRing(width=28, height=28, stroke_width=2.5, color=ft.Colors.PRIMARY),
            )
            page.update()

        tok = await _get_auth_token()
        p_res = None
        if tok:
            try:
                p_res = await get_active_partnership(tok)
                if p_res and isinstance(p_res, dict) and p_res.get("has_partnership"):
                    all_ps = p_res.get("partnerships") or ([p_res.get("partnership")] if p_res.get("partnership") else [])
                    if all_ps:
                        p_info = all_ps[0] or {}
                        p_id = p_info.get("id")
                        partnership_id_box[0] = p_id
                        partner_box[0] = p_info.get("partner", {})
            except Exception:
                pass

        p_id = partnership_id_box[0]
        history = []
        if tok:
            try:
                history = await get_challenge_history_api(tok, p_id)
            except Exception:
                history = []

        # Fallback: extract from partnership's recent_challenges across any active partnership
        if not history and p_res and isinstance(p_res, dict) and p_res.get("has_partnership"):
            all_ps = p_res.get("partnerships") or ([p_res.get("partnership")] if p_res.get("partnership") else [])
            curr_uid = str((page.session.store.get("current_user") or {}).get("id") or "") if hasattr(page, "session") and hasattr(page.session, "store") else ""
            for p_item in all_ps:
                p_partner = (p_item or {}).get("partner", {})
                p_name = p_partner.get("first_name", "Partner")
                raw_chs = (p_item or {}).get("recent_challenges", [])
                for ch in raw_chs:
                    is_mine = (str(ch.get("challenger_id")) == curr_uid) or ch.get("is_challenger", True)
                    w_id = ch.get("winner_id")
                    outcome = "tie"
                    if ch.get("status") == "challenger_done":
                        outcome = "pending" if is_mine else "needs_action"
                    elif w_id:
                        outcome = "won" if str(w_id) == curr_uid else "lost"
                    
                    my_s = ch.get("my_score") if ch.get("my_score") is not None else (ch.get("challenger_score") if is_mine else ch.get("challenged_score"))
                    p_s = ch.get("partner_score") if ch.get("partner_score") is not None else (ch.get("challenged_score") if is_mine else ch.get("challenger_score"))

                    history.append({
                        "id": ch.get("id"),
                        "title": ch.get("title", "15-Q Quickfire Duel"),
                        "partner_name": p_name,
                        "outcome": outcome,
                        "status": ch.get("status"),
                        "my_score": my_s,
                        "partner_score": p_s,
                        "total_questions": ch.get("total_questions", 15),
                        "completed_at": ch.get("created_at", ""),
                        "coins_awarded": ch.get("coins_awarded", 35 if outcome == "won" else (20 if outcome == "tie" else (10 if outcome == "lost" else 0))),
                        "challenge": ch,
                    })

        hist_list = ft.ListView(spacing=8, expand=True, padding=ft.Padding.symmetric(horizontal=16, vertical=8))

        if not history:
            hist_list.controls.append(
                ft.Container(
                    padding=40,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                        controls=[
                            ft.Icon(ft.Icons.MILITARY_TECH_ROUNDED, size=36, color=ft.Colors.GREY_400),
                            ft.Text("No duel history yet.", size=13, weight=ft.FontWeight.W_700),
                            ft.Text("Challenge your duo partner to a 15-question showdown to populate your history!", size=11, color=ft.Colors.GREY_500, text_align=ft.TextAlign.CENTER),
                        ],
                    ),
                )
            )
        else:
            for duel in history:
                d_id = duel.get("id")
                title = duel.get("title", "15-Q Quickfire Duel")
                p_name = duel.get("partner_name", "Partner")
                outcome = duel.get("outcome", "tie")
                my_s = duel.get("my_score")
                p_s = duel.get("partner_score")
                tot_q = duel.get("total_questions", 15)
                comp_at = (duel.get("completed_at") or "")[:10]

                if outcome == "won":
                    badge_color = ft.Colors.GREEN_700
                    badge_bg = ft.Colors.with_opacity(0.12, ft.Colors.GREEN)
                    badge_label = "🏆 Won"
                elif outcome == "lost":
                    badge_color = ft.Colors.BLUE_700
                    badge_bg = ft.Colors.with_opacity(0.12, ft.Colors.BLUE)
                    badge_label = "🥈 Runner-up"
                elif outcome == "pending":
                    badge_color = ft.Colors.ORANGE_800
                    badge_bg = ft.Colors.with_opacity(0.12, ft.Colors.ORANGE)
                    badge_label = "⏳ Awaiting Partner"
                elif outcome == "needs_action":
                    badge_color = ft.Colors.PRIMARY
                    badge_bg = ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY)
                    badge_label = "⚔️ Your Turn!"
                else:
                    badge_color = ft.Colors.AMBER_800
                    badge_bg = ft.Colors.with_opacity(0.12, ft.Colors.AMBER)
                    badge_label = "🤝 Tied"

                async def _view_duel_diag(d_item=duel):
                    c_obj = d_item.get("challenge") or d_item
                    u_data = page.session.store.get("current_user") or {} if hasattr(page, "session") and hasattr(page.session, "store") else {}
                    show_duel_results_dialog(
                        page=page,
                        challenge=c_obj,
                        current_user_id=str(u_data.get("id") or ""),
                        token=tok,
                        partnership_id=partnership_id_box[0],
                    )

                my_score_str = f"You: {my_s}/{tot_q}" if my_s is not None else "You: Waiting..."
                partner_score_str = f"{p_name}: {p_s}/{tot_q}" if p_s is not None else f"{p_name}: Waiting..."

                hist_list.controls.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                        border_radius=ft.BorderRadius.all(12),
                        bgcolor=ft.Colors.SURFACE,
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                        ink=True,
                        on_click=(lambda d=duel: lambda _: page.run_task(_view_duel_diag, d))(),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Column(
                                    spacing=3,
                                    tight=True,
                                    controls=[
                                        ft.Row(
                                            spacing=6,
                                            tight=True,
                                            controls=[
                                                ft.Text(title, size=13, weight=ft.FontWeight.W_800),
                                                ft.Container(
                                                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                                    border_radius=ft.BorderRadius.all(6),
                                                    bgcolor=badge_bg,
                                                    content=ft.Text(badge_label, size=10, weight=ft.FontWeight.W_800, color=badge_color),
                                                ),
                                            ],
                                        ),
                                        ft.Text(f"vs {p_name} • {comp_at}", size=11, color=ft.Colors.GREY_500),
                                    ],
                                ),
                                ft.Row(
                                    spacing=8,
                                    tight=True,
                                    controls=[
                                        ft.Column(
                                            spacing=1,
                                            horizontal_alignment=ft.CrossAxisAlignment.END,
                                            tight=True,
                                            controls=[
                                                ft.Text(my_score_str, size=12, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY),
                                                ft.Text(partner_score_str, size=11, color=ft.Colors.GREY_600),
                                            ],
                                        ),
                                        ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, size=16, color=ft.Colors.GREY_400),
                                    ],
                                ),
                            ],
                        ),
                    )
                )

        await _swap_content_smoothly(hist_list, is_initial=is_initial)

    # ─────────────────────────────────────────────────────────────────────────
    # TAB CONTROLLER
    # ─────────────────────────────────────────────────────────────────────────
    def _switch_tab(tab_name: str):
        nonlocal current_tab
        current_tab = tab_name
        _render_tab_header()
        content_area.content = ft.Container(
            padding=50,
            alignment=ft.Alignment.CENTER,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
                controls=[
                    ft.ProgressRing(width=20, height=20, stroke_width=2.5, color=ft.Colors.PRIMARY),
                    ft.Text("Loading…", size=12, color=ft.Colors.GREY_500),
                ],
            ),
        )
        page.update()
        if tab_name == "objectives":
            page.run_task(_render_objectives_tab, False)
        elif tab_name == "leaderboards":
            page.run_task(_render_leaderboards_tab, "duo_streaks", False)
        elif tab_name == "history":
            page.run_task(_render_duel_history_tab, False)

    def _render_tab_header():
        tab_buttons_row.controls.clear()
        tabs = [
            ("objectives", "🪙 Objectives"),
            ("leaderboards", "🏆 Leaderboards"),
            ("history", "⚔️ Duel History"),
        ]
        for t_id, t_lbl in tabs:
            is_active = (t_id == current_tab)
            btn = ft.Container(
                padding=ft.Padding.symmetric(horizontal=14, vertical=8),
                border_radius=ft.BorderRadius.all(10),
                bgcolor=ft.Colors.PRIMARY if is_active else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                ink=True,
                on_click=(lambda tid=t_id: lambda _: _switch_tab(tid))(),
                content=ft.Text(
                    t_lbl,
                    size=10,
                    weight=ft.FontWeight.W_800 if is_active else ft.FontWeight.W_600,
                    color=ft.Colors.WHITE if is_active else ft.Colors.ON_SURFACE,
                ),
            )
            tab_buttons_row.controls.append(btn)

    async def _init_load():
        tok = await _get_auth_token()

        # 1. Immediately read coins from session if available
        if hasattr(page, "session") and hasattr(page.session, "store"):
            u_obj = page.session.store.get("current_user") or {}
            c_bal = u_obj.get("coins_balance", 0)
            if c_bal is not None:
                coins_balance_box[0] = c_bal
                coins_badge_text.value = f"{c_bal} 🪙"

        # 2. Fetch live balance from objectives API so it's always accurate right away
        if tok:
            try:
                res_obj = await get_platform_objectives_api(tok)
                if res_obj and "coins_balance" in res_obj:
                    live_bal = res_obj.get("coins_balance", 0)
                    coins_balance_box[0] = live_bal
                    coins_badge_text.value = f"{live_bal} 🪙"
            except Exception:
                pass

        if tok:
            try:
                p_res = await get_active_partnership(tok)
                if p_res and p_res.get("has_partnership"):
                    partnership_id_box[0] = p_res.get("partnership", {}).get("id")
                    partner_box[0] = p_res.get("partnership", {}).get("partner", {})
            except Exception:
                pass
        
        # Render initial tab directly before view is returned
        if current_tab == "objectives":
            await _render_objectives_tab(is_initial=True)
        elif current_tab == "leaderboards":
            await _render_leaderboards_tab(filter_type="duo_streaks", is_initial=True)
        elif current_tab == "history":
            await _render_duel_history_tab(is_initial=True)

    _render_tab_header()
    await _init_load()

    header_bar = ft.Container(
        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(
                    spacing=6,
                    tight=True,
                    controls=[
                        ft.IconButton(ft.Icons.ARROW_BACK_ROUNDED, icon_size=20, on_click=lambda _: page.go(back_target)),
                        ft.Text("Leaderboards & Objectives", size=14, weight=ft.FontWeight.W_800),
                    ],
                ),
                coins_badge,
            ],
        ),
    )

    tab_bar_container = ft.Container(
        padding=ft.Padding.symmetric(horizontal=16, vertical=4),
        content=tab_buttons_row,
    )

    bar_instance = PersistentBottomAppBar(page)

    return ft.View(
        route="/leaderboards",
        padding=0,
        controls=[
            ft.SafeArea(
                expand=True,
                content=ft.Column(
                    spacing=0,
                    expand=True,
                    controls=[
                        header_bar,
                        tab_bar_container,
                        ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                        content_area,
                    ],
                ),
            )
        ],
        bottom_appbar=bar_instance.bar,
    )
