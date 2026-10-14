"""
objectives_and_leaderboard_modal.py
──────────────────────────────────────────────────────────────────────────────
Interactive Modal for:
- Platform Prelim Objectives & Nu-Coins Wallet Ledger
- Shared Study Packs between Duo Partners
- Real-time Study & Duo Streak Leaderboards

Mobile notes
  • Dialog width/height are derived from the page size (no fixed 540 / 480).
  • Every row that can overflow is a wrapping Row, or has an expanding text.
  • Phones (< 600 px) stack card content vertically and use taller tap targets.
  • Feedback is shown inline in the dialog while it's open (a snackbar can render
    behind a modal on mobile); the snackbar is used once the dialog is closed.
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
    preview_shared_study_pack_api,
)
from src.components.partner_challenge_modal import (
    start_quickfire_duel_flow,
    show_flashcard_preview_dialog,
)

PHONE_BREAKPOINT = 600


def _as_dict(x) -> dict:
    return x if isinstance(x, dict) else {}


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
    # ── Responsive sizing ────────────────────────────────────────────────────
    page_w = page.width or 360
    page_h = page.height or 640
    phone = page_w < PHONE_BREAKPOINT
    dlg_w = max(240, min(540, int(page_w - 64)))        # 16px inset + 16px content padding per side
    body_h = max(240, min(480, int(page_h * 0.55)))     # leave room for title, tabs and actions
    btn_h = 38 if phone else 32                         # comfortable tap target on phones

    current_tab = initial_tab
    p_name = partner.get("first_name", "Partner") if partner else "Partner"

    # Wrapping tab strip: tabs drop to a second line instead of overflowing.
    tab_header = ft.Row(
        alignment=ft.MainAxisAlignment.START,
        spacing=6,
        run_spacing=6,
        wrap=True,
    )

    status_txt = ft.Text("", size=11, weight=ft.FontWeight.W_600, visible=False)

    # Fixed, bounded height (the old `expand=True` + height=480 combo is fragile
    # inside a dialog and far too tall for phones).
    body_container = ft.Container(height=body_h)

    def _notify(msg: str, error: bool = True):
        """Inline feedback while the dialog is open; snackbar once it's closed."""
        if dlg.open:
            status_txt.value = msg
            status_txt.color = ft.Colors.ERROR if error else ft.Colors.GREEN_700
            status_txt.visible = bool(msg)
            status_txt.update()
        elif msg:
            show_page_snackbar(page, msg)

    def _clear_status():
        status_txt.value = ""
        status_txt.visible = False

    def _close():
        dlg.open = False
        try:
            dlg.update()
        except Exception:
            page.update()

    def _spinner() -> ft.Container:
        return ft.Container(
            alignment=ft.Alignment.CENTER,
            content=ft.ProgressRing(width=28, height=28, stroke_width=2.5, color=ft.Colors.PRIMARY),
        )

    dlg = ft.AlertDialog(
        modal=True,
        shape=ft.RoundedRectangleBorder(radius=20),
        bgcolor=ft.Colors.SURFACE,
        inset_padding=ft.Padding.symmetric(horizontal=16, vertical=24),
        title_padding=ft.Padding.only(left=16, right=16, top=16, bottom=4),
        content_padding=ft.Padding.symmetric(horizontal=16, vertical=8),
        actions_padding=ft.Padding.only(left=16, right=16, bottom=12),
        title=ft.Row(
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.WORKSPACE_PREMIUM_ROUNDED, color=ft.Colors.PRIMARY, size=24),
                ft.Text(
                    "Nu-Coins & Study Milestones",
                    size=15 if phone else 16,
                    weight=ft.FontWeight.W_800,
                    expand=True,                       # shrink/wrap instead of overflowing
                    max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
            ],
        ),
        content=ft.Container(
            width=dlg_w,
            content=ft.Column(
                tight=True,
                spacing=10,
                controls=[tab_header, status_txt, body_container],
            ),
        ),
        actions=[ft.TextButton("Close", on_click=lambda _: _close())],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    def _switch_tab(tab_key: str):
        nonlocal current_tab
        current_tab = tab_key
        _clear_status()
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
            ("objectives", "Objectives" if phone else "🪙 Objectives & Coins", ft.Icons.TOKEN_ROUNDED),
            ("shared_packs", "Packs" if phone else "📚 Shared Packs", ft.Icons.FOLDER_SHARED_ROUNDED),
            ("leaderboard", "Ranks" if phone else "🏆 Leaderboards", ft.Icons.LEADERBOARD_ROUNDED),
        ]
        for key, label, icon in tabs:
            is_active = (key == current_tab)
            tab_header.controls.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=9 if phone else 6),
                    border_radius=ft.BorderRadius.all(10),
                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if is_active else ft.Colors.TRANSPARENT,
                    ink=True,
                    on_click=(lambda k=key: lambda _: _switch_tab(k))(),
                    content=ft.Row(
                        spacing=6,
                        tight=True,
                        controls=[
                            ft.Icon(icon, size=15, color=ft.Colors.PRIMARY if is_active else ft.Colors.GREY_500),
                            ft.Text(
                                label,
                                size=11.5,
                                no_wrap=True,
                                weight=ft.FontWeight.W_700 if is_active else ft.FontWeight.W_500,
                                color=ft.Colors.PRIMARY if is_active else ft.Colors.ON_SURFACE,
                            ),
                        ],
                    ),
                )
            )
        page.update()

    # ─────────────────────────────────────────────────────────────────────────
    # 1. OBJECTIVES TAB
    # ─────────────────────────────────────────────────────────────────────────
    async def _load_objectives_tab():
        body_container.content = _spinner()
        page.update()

        try:
            data = _as_dict(await get_platform_objectives_api(token))
        except Exception as ex:
            body_container.content = ft.Container(
                alignment=ft.Alignment.CENTER, padding=20,
                content=ft.Text(f"Couldn't load objectives: {ex}", color=ft.Colors.GREY_500, text_align=ft.TextAlign.CENTER),
            )
            page.update()
            return

        objs = data.get("objectives") or []
        coins_bal = data.get("coins_balance", 0)

        # Wallet card: wraps instead of overflowing; the helper chip is hidden on phones.
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
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
                run_spacing=8,
                wrap=True,
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
                                    ft.Text(f"{coins_bal} Coins", size=22, weight=ft.FontWeight.W_900, color=ft.Colors.WHITE, no_wrap=True),
                                ],
                            ),
                        ],
                    ),
                    ft.Container(
                        visible=not phone,
                        padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                        border_radius=ft.BorderRadius.all(8),
                        bgcolor=ft.Colors.with_opacity(0.20, ft.Colors.BLACK),
                        content=ft.Text("Earn via Duels & Streaks", size=10.5, color=ft.Colors.WHITE, weight=ft.FontWeight.W_700, no_wrap=True),
                    ),
                ],
            ),
        )

        def _make_claim(c_code, btn):
            async def _on_claim(e=None):
                if btn.disabled:
                    return
                btn.disabled = True
                btn.update()
                try:
                    res = _as_dict(await claim_objective_reward_api(token, c_code))
                except Exception as ex:
                    res = {"message": f"Couldn't claim: {ex}"}
                if res.get("status") == "success":
                    if on_coins_changed:
                        on_coins_changed()
                    await _load_objectives_tab()
                    _notify(f"Reward claimed! +{res.get('reward_coins')} Nu-Coins! 🎉", error=False)
                else:
                    btn.disabled = False
                    btn.update()
                    _notify(res.get("message") or "Error claiming reward.")
            return _on_claim

        obj_list = ft.ListView(spacing=10, expand=True)
        if not objs:
            obj_list.controls.append(ft.Container(padding=20, alignment=ft.Alignment.CENTER, content=ft.Text("No active objectives found.", color=ft.Colors.GREY_500)))
        else:
            for item in objs:
                code = item.get("code")
                title = item.get("title") or "Objective"
                desc = item.get("description") or ""
                reward = item.get("reward_coins", 0)
                curr = item.get("current_value", 0)
                tgt = max(1, item.get("target_value", 1))
                can_claim = item.get("can_claim", False)
                is_completed = item.get("is_completed", False)
                progress_val = min(1.0, curr / tgt)

                if can_claim:
                    claim_btn = ft.ElevatedButton(
                        content=ft.Text(f"Claim +{reward} 🪙", size=11.5, weight=ft.FontWeight.W_700, no_wrap=True),
                        bgcolor=ft.Colors.PRIMARY,
                        color=ft.Colors.WHITE,
                        height=btn_h,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=8),
                            elevation=0,
                            padding=ft.Padding.symmetric(horizontal=14),
                        ),
                    )
                    claim_btn.on_click = _make_claim(code, claim_btn)
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
                                ft.Text("Claimed", size=10.5, weight=ft.FontWeight.W_700, color=ft.Colors.GREEN_800, no_wrap=True),
                            ],
                        ),
                    )
                else:
                    trailing_widget = ft.Container(
                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                        border_radius=ft.BorderRadius.all(8),
                        bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                        content=ft.Text(f"{curr}/{tgt}", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.GREY_600, no_wrap=True),
                    )

                info = ft.Column(
                    spacing=3,
                    tight=True,
                    controls=[
                        # Wrapping row: long titles drop the reward chip to the next line.
                        ft.Row(
                            spacing=6,
                            run_spacing=2,
                            wrap=True,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Text(title, size=12.5, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                ft.Container(
                                    padding=ft.Padding.symmetric(horizontal=6, vertical=1.5),
                                    border_radius=ft.BorderRadius.all(6),
                                    bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.AMBER),
                                    content=ft.Text(f"+{reward}🪙", size=9.5, weight=ft.FontWeight.W_800, color=ft.Colors.AMBER_900, no_wrap=True),
                                ),
                            ],
                        ),
                        ft.Text(desc, size=11, color=ft.Colors.GREY_500),
                        # Progress bar fills the available width (was a fixed 160px that overflowed).
                        ft.Row(
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.ProgressBar(value=progress_val, color=ft.Colors.PRIMARY, bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY), height=5, expand=True),
                                ft.Text(f"{curr} / {tgt}", size=10, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_600, no_wrap=True),
                            ],
                        ),
                    ],
                )

                if phone:
                    # Stack: info on top, claim/status aligned to the right underneath.
                    card_body = ft.Column(
                        spacing=8,
                        tight=True,
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                        controls=[
                            info,
                            ft.Row(alignment=ft.MainAxisAlignment.END, controls=[trailing_widget]),
                        ],
                    )
                else:
                    info.expand = True
                    card_body = ft.Row(
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[info, trailing_widget],
                    )

                obj_list.controls.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                        border_radius=ft.BorderRadius.all(12),
                        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                        content=card_body,
                    )
                )

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
                content=ft.Text("Pair up with an accountability partner to share study packs!", color=ft.Colors.GREY_500, text_align=ft.TextAlign.CENTER),
            )
            page.update()
            return

        body_container.content = _spinner()
        page.update()

        try:
            shares = await get_shared_study_packs_api(token, partnership_id)
        except Exception as ex:
            body_container.content = ft.Container(
                alignment=ft.Alignment.CENTER, padding=20,
                content=ft.Text(f"Couldn't load shared packs: {ex}", color=ft.Colors.GREY_500, text_align=ft.TextAlign.CENTER),
            )
            page.update()
            return
        shares = shares or []

        def _make_accept(sid, btn):
            async def _on_accept(e=None):
                if btn.disabled:
                    return
                btn.disabled = True
                btn.update()
                try:
                    res = _as_dict(await accept_shared_study_pack_api(token, partnership_id, sid))
                except Exception as ex:
                    res = {"error": f"Couldn't accept: {ex}"}
                if not res.get("error"):
                    await _load_shared_packs_tab()
                    _notify("Study pack accepted! Added to your collection 📚", error=False)
                else:
                    btn.disabled = False
                    btn.update()
                    _notify(res.get("error") or "Error accepting pack.")
            return _on_accept

        def _make_duel(pid, p_title):
            async def _on_duel(e=None):
                _close()
                try:
                    res = _as_dict(await generate_quickfire_from_pack_api(token, partnership_id, pid))
                except Exception as ex:
                    res = {"error": str(ex)}
                if res.get("status") == "success":
                    start_quickfire_duel_flow(
                        page=page,
                        token=token,
                        partnership_id=partnership_id,
                        pack_id=pid,
                        pack_title=p_title,
                        partner_name=p_name,
                        is_accepting_challenge=False,
                        seeded_questions=res.get("questions", []),
                        on_completed=on_coins_changed,
                    )
                else:
                    show_page_snackbar(page, res.get("error") or "Error preparing pack duel.")
            return _on_duel

        def _make_preview(pid, p_title):
            async def _on_preview(e=None):
                _close()
                try:
                    p_res = _as_dict(await preview_shared_study_pack_api(token, partnership_id, pid))
                except Exception as ex:
                    p_res = {"error": str(ex)}
                if p_res and not p_res.get("error"):
                    show_flashcard_preview_dialog(
                        page=page,
                        token=token,
                        partnership_id=partnership_id,
                        pack_id=pid,
                        pack_title=p_title,
                        partner_name=p_name,
                        flashcards=p_res.get("flashcards", []),
                        on_duel_start=on_coins_changed,
                    )
                else:
                    show_page_snackbar(page, p_res.get("error") or "Error loading pack preview.")
            return _on_preview

        pack_list = ft.ListView(spacing=10, expand=True)

        if not shares:
            pack_list.controls.append(
                ft.Container(
                    padding=30,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                        tight=True,
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
                        content=ft.Text("Accept & Download", size=11.5, weight=ft.FontWeight.W_700, no_wrap=True),
                        bgcolor=ft.Colors.PRIMARY,
                        color=ft.Colors.WHITE,
                        height=btn_h,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), elevation=0, padding=ft.Padding.symmetric(horizontal=14)),
                    )
                    accept_btn.on_click = _make_accept(share_id, accept_btn)
                    action_controls.append(accept_btn)
                else:
                    preview_btn = ft.OutlinedButton(
                        content=ft.Row(
                            tight=True,
                            spacing=3,
                            controls=[
                                ft.Icon(ft.Icons.STYLE_ROUNDED, size=13, color=ft.Colors.PRIMARY),
                                ft.Text("Preview Cards", size=11.5, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY, no_wrap=True),
                            ],
                        ),
                        height=btn_h,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), padding=ft.Padding.symmetric(horizontal=12)),
                    )
                    preview_btn.on_click = _make_preview(pack_id, title)

                    duel_btn = ft.ElevatedButton(
                        content=ft.Row(
                            tight=True,
                            spacing=4,
                            controls=[
                                ft.Icon(ft.Icons.FLASH_ON_ROUNDED, size=14, color=ft.Colors.WHITE),
                                ft.Text("Duel on Pack", size=11.5, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE, no_wrap=True),
                            ],
                        ),
                        bgcolor=ft.Colors.ORANGE_800,
                        height=btn_h,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), elevation=0, padding=ft.Padding.symmetric(horizontal=12)),
                    )
                    # BUG FIX: this button previously had no on_click, so tapping it did nothing.
                    duel_btn.on_click = _make_duel(pack_id, title)

                    action_controls += [preview_btn, duel_btn]

                info = ft.Column(
                    spacing=3,
                    tight=True,
                    controls=[
                        ft.Row(
                            spacing=6,
                            run_spacing=2,
                            wrap=True,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Text(title, size=13, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                ft.Container(
                                    padding=ft.Padding.symmetric(horizontal=6, vertical=1.5),
                                    border_radius=ft.BorderRadius.all(6),
                                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                                    content=ft.Text(category, size=9.5, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY, no_wrap=True),
                                ),
                            ],
                        ),
                        ft.Text(
                            f"{q_count} Questions • {fc_count} Flashcards • Shared by {'You' if is_mine else sender_name}",
                            size=11,
                            color=ft.Colors.GREY_500,
                        ),
                    ],
                )
                actions = ft.Row(spacing=8, run_spacing=8, wrap=True, controls=action_controls)

                if phone:
                    card_body = ft.Column(
                        spacing=10,
                        tight=True,
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                        controls=[info, actions],
                    )
                else:
                    info.expand = True
                    card_body = ft.Row(
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[info, actions],
                    )

                pack_list.controls.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                        border_radius=ft.BorderRadius.all(12),
                        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                        content=card_body,
                    )
                )

        body_container.content = pack_list
        page.update()

    # ─────────────────────────────────────────────────────────────────────────
    # 3. LEADERBOARDS TAB
    # ─────────────────────────────────────────────────────────────────────────
    async def _load_leaderboard_tab(filter_type: str = "duo_streaks"):
        body_container.content = _spinner()
        page.update()

        try:
            leaders = await get_study_leaderboard_api(token, filter_type=filter_type)
        except Exception as ex:
            body_container.content = ft.Container(
                alignment=ft.Alignment.CENTER, padding=20,
                content=ft.Text(f"Couldn't load leaderboard: {ex}", color=ft.Colors.GREY_500, text_align=ft.TextAlign.CENTER),
            )
            page.update()
            return
        leaders = leaders or []
        board_list = ft.ListView(spacing=8, expand=True)

        def _set_board_filter(f_type: str):
            page.run_task(_load_leaderboard_tab, f_type)

        def _filter_chip(key: str, label: str) -> ft.Container:
            active = (filter_type == key)
            return ft.Container(
                padding=ft.Padding.symmetric(horizontal=10, vertical=8 if phone else 4),
                border_radius=ft.BorderRadius.all(8),
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if active else ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                ink=True,
                on_click=lambda _: _set_board_filter(key),
                content=ft.Text(
                    label,
                    size=11,
                    no_wrap=True,
                    weight=ft.FontWeight.W_700 if active else ft.FontWeight.W_500,
                    color=ft.Colors.PRIMARY if active else ft.Colors.ON_SURFACE,
                ),
            )

        # Wrapping filter row: three chips don't fit side by side on a phone.
        filter_row = ft.Row(
            spacing=8,
            run_spacing=8,
            wrap=True,
            controls=[
                _filter_chip("duo_streaks", "🔥 Duo Streaks"),
                _filter_chip("today", "⏱ Study Time (Today)"),
                _filter_chip("weekly", "⚡ Solo Streaks"),
            ],
        )

        if not leaders:
            board_list.controls.append(ft.Container(padding=20, alignment=ft.Alignment.CENTER, content=ft.Text("No leaderboard entries yet. Be the first!", color=ft.Colors.GREY_500)))
        else:
            for item in leaders:
                rank = item.get("rank", 1)
                is_mine = item.get("is_my_duo", False) or item.get("is_me", False)

                if rank == 1:
                    rank_badge = ft.Text("🥇", size=16)
                elif rank == 2:
                    rank_badge = ft.Text("🥈", size=16)
                elif rank == 3:
                    rank_badge = ft.Text("🥉", size=16)
                else:
                    rank_badge = ft.Text(f"#{rank}", size=12, weight=ft.FontWeight.W_800, color=ft.Colors.GREY_500)

                if filter_type == "duo_streaks":
                    p_a = item.get("partner_a") or {}
                    p_b = item.get("partner_b") or {}
                    duo_name = f"{p_a.get('first_name', 'Learner')} & {p_b.get('first_name', 'Partner')}"
                    metric_str = f"🔥 {item.get('duo_streak', 0)} Days Duo Streak"
                else:
                    u_name = f"{item.get('first_name', '')} {item.get('last_name', '')}".strip() or item.get("username", "Learner")
                    metric_str = f"🔥 {item.get('streak', 0)}d • 🪙 {item.get('coins_balance', 0)} coins"
                    duo_name = u_name

                name_row_controls = [
                    ft.Text(duo_name, size=12.5, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY if is_mine else ft.Colors.ON_SURFACE),
                ]
                if is_mine:
                    name_row_controls.append(
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=5, vertical=1),
                            border_radius=ft.BorderRadius.all(4),
                            bgcolor=ft.Colors.PRIMARY,
                            content=ft.Text("YOU", size=8, weight=ft.FontWeight.W_900, color=ft.Colors.WHITE),
                        )
                    )

                board_list.controls.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                        border_radius=ft.BorderRadius.all(10),
                        bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY) if is_mine else ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.20, ft.Colors.PRIMARY) if is_mine else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
                        content=ft.Row(
                            spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Container(width=30, alignment=ft.Alignment.CENTER, content=rank_badge),
                                ft.Column(
                                    spacing=1,
                                    tight=True,
                                    expand=True,   # long names wrap inside the row instead of overflowing
                                    controls=[
                                        ft.Row(spacing=6, run_spacing=2, wrap=True, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=name_row_controls),
                                        ft.Text(metric_str, size=11, color=ft.Colors.GREY_600, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                    ],
                                ),
                            ],
                        ),
                    )
                )

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

    # ── Show: dialog first, then kick off the tab load ────────────────────────
    _rebuild_tabs()
    if hasattr(page, "show_dialog"):
        page.show_dialog(dlg)               # Flet >= 0.80 / 1.0
    else:
        page.overlay.append(dlg)            # legacy Flet
        dlg.open = True
        page.update()
    _switch_tab(initial_tab)