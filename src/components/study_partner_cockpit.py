"""
study_partner_cockpit.py
──────────────────────────────────────────────────────────────────────────────
Accountability Partner Cockpit component for the Self-Study Hub.
Displays dual daily study progress, Duo streak, quick accountability nudges,
and head-to-head CBT / Quiz duel challenges.
──────────────────────────────────────────────────────────────────────────────
"""

import asyncio
import flet as ft
from typing import Optional, Callable
from src.components.nu_coin_icon import nu_coin_icon

from src.utils.file_opener import show_page_snackbar
from src.requests.study_partners import (
    get_active_partnership,
    nudge_study_partner,
    share_study_pack_api,
)
from src.components.partner_challenge_modal import (
    show_create_duel_dialog,
    show_duel_results_dialog,
)
from src.components.objectives_and_leaderboard_modal import (
    show_objectives_and_leaderboard_dialog,
)


def _initials(first: str, last: str) -> str:
    return f"{(first or '?')[:1]}{(last or '?')[:1]}".upper()


def build_study_partner_cockpit(
    page: ft.Page,
    token: str,
    available_materials: list = None,
    on_refresh: Optional[Callable] = None,
) -> ft.Container:
    """
    Builds the interactive Study Partner Cockpit widget.
    Loads active partnership asynchronously and renders the corresponding cockpit card.
    """
    def _build_skeleton_card() -> ft.Container:
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=16, vertical=14),
            border_radius=ft.BorderRadius.all(16),
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            shadow=ft.BoxShadow(
                blur_radius=10,
                color=ft.Colors.with_opacity(0.03, ft.Colors.BLACK),
                offset=ft.Offset(0, 2),
            ),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        spacing=12,
                        expand=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(
                                width=40,
                                height=40,
                                border_radius=ft.BorderRadius.all(12),
                                gradient=ft.LinearGradient(
                                    colors=[ft.Colors.AMBER_600, ft.Colors.ORANGE_600],
                                    begin=ft.Alignment.TOP_LEFT,
                                    end=ft.Alignment.BOTTOM_RIGHT,
                                ),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED, color=ft.Colors.WHITE, size=20),
                            ),
                            ft.Column(
                                spacing=3,
                                tight=True,
                                expand=True,
                                controls=[
                                    ft.Row(
                                        spacing=6,
                                        tight=True,
                                        controls=[
                                            ft.Text("Syncing Duo Streak…", size=13, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                            ft.ProgressRing(width=12, height=12, stroke_width=2, color=ft.Colors.AMBER_700),
                                        ],
                                    ),
                                    ft.Text("Connecting to accountability partner & daily goals", size=11, color=ft.Colors.GREY_500, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                ],
                            ),
                        ],
                    ),
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                        border_radius=ft.BorderRadius.all(8),
                        bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                        content=ft.Text("Syncing…", size=11, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_400),
                    ),
                ],
            ),
        )

    card_container = ft.Container(
        margin=ft.Margin.only(bottom=12),
        content=_build_skeleton_card(),
        opacity=0.9,
        offset=ft.Offset(0, 0),
        animate_opacity=ft.Animation(450, ft.AnimationCurve.DECELERATE),
        animate_offset=ft.Animation(450, ft.AnimationCurve.DECELERATE),
        visible=bool(token),
    )

    active_partnerships_list = []
    selected_p_idx = 0
    is_offline_state = False

    async def _load_partner_state():
        nonlocal active_partnerships_list, selected_p_idx, is_offline_state
        if not token:
            card_container.visible = False
            page.update()
            return

        res = await get_active_partnership(token)
        if not res or not isinstance(res, dict):
            res = {}
        has_p = bool(res.get("has_partnership"))
        is_offline_state = bool(res.get("is_offline"))
        active_partnerships_list = res.get("partnerships") or ([res.get("partnership")] if res.get("partnership") else [])
        if selected_p_idx >= len(active_partnerships_list):
            selected_p_idx = 0

        target_card = _build_active_card(active_partnerships_list[selected_p_idx]) if (has_p and active_partnerships_list) else _build_invite_card()

        # Smooth crossfade transition into the live loaded card
        card_container.opacity = 0
        card_container.offset = ft.Offset(0, 0.04)
        page.update()
        await asyncio.sleep(0.08)
        card_container.content = target_card
        card_container.opacity = 1
        card_container.offset = ft.Offset(0, 0)
        page.update()

    def _build_invite_card() -> ft.Container:
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=16, vertical=14),
            border_radius=ft.BorderRadius.all(16),
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY)),
            shadow=ft.BoxShadow(
                blur_radius=10,
                color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                offset=ft.Offset(0, 3),
            ),
            # ResponsiveRow: side-by-side on wide screens, stacked on phones
            content=ft.ResponsiveRow(
                spacing=12,
                run_spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        col={"xs": 12, "md": 9},
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(
                                width=42,
                                height=42,
                                border_radius=ft.BorderRadius.all(12),
                                gradient=ft.LinearGradient(
                                    colors=[ft.Colors.AMBER_600, ft.Colors.ORANGE_600],
                                    begin=ft.Alignment.TOP_LEFT,
                                    end=ft.Alignment.BOTTOM_RIGHT,
                                ),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED, color=ft.Colors.WHITE, size=22),
                            ),
                            ft.Column(
                                spacing=2,
                                tight=True,
                                expand=True,
                                controls=[
                                    ft.Text("Accountability Duo", size=13, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                    ft.Text(
                                        "Pair up with a study partner to maintain daily streaks & challenge each other in Duels.",
                                        size=11.5,
                                        color=ft.Colors.GREY_500,
                                        max_lines=3,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                ],
                            ),
                        ],
                    ),
                    ft.Container(
                        col={"xs": 12, "md": 3},
                        alignment=ft.Alignment.CENTER_RIGHT,
                        content=ft.ElevatedButton(
                            content=ft.Row(
                                tight=True,
                                spacing=6,
                                controls=[
                                    ft.Icon(ft.Icons.PERSON_ADD_ALT_1_ROUNDED, size=15, color=ft.Colors.WHITE),
                                    ft.Text("Find Partner", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE, no_wrap=True),
                                ],
                            ),
                            bgcolor=ft.Colors.PRIMARY,
                            height=40,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=10),
                                elevation=0,
                                padding=ft.Padding.symmetric(horizontal=14),
                            ),
                            on_click=lambda _: page.go("/network?tab=partners"),
                        ),
                    ),
                ],
            ),
        )

    def _build_active_card(p_data: dict) -> ft.Container:
        partner = p_data.get("partner") or {}
        p_id = p_data.get("id")
        p_first = partner.get("first_name", "Partner")
        p_last = partner.get("last_name", "")
        p_name = f"{p_first} {p_last}".strip()
        p_uni = partner.get("university") or "Campus Peer"
        p_pic = partner.get("profile_picture_url")

        p_username = partner.get("username")
        p_display_name = f"{p_name} (@{p_username})" if p_username else p_name

        duo_streak = p_data.get("duo_streak", 0)
        daily_mins_target = p_data.get("daily_target_minutes", 45)
        user_mins = p_data.get("user_today_minutes", 0)
        partner_mins = p_data.get("partner_today_minutes", 0)
        user_done = p_data.get("user_studied_today", False)
        partner_done = p_data.get("partner_studied_today", False)
        can_nudge = p_data.get("can_nudge", True)

        def _on_switch_partner(target_idx: int):
            nonlocal selected_p_idx
            selected_p_idx = target_idx
            card_container.content = _build_active_card(active_partnerships_list[target_idx])
            page.update()

        switcher_row = None
        if len(active_partnerships_list) > 1:
            p_chips = []
            for idx, p_item in enumerate(active_partnerships_list):
                is_sel = (idx == selected_p_idx)
                p_item_partner = p_item.get("partner") or {}
                p_item_first = p_item_partner.get("first_name", f"Partner {idx+1}")
                p_item_last = p_item_partner.get("last_name", "")
                p_item_uname = p_item_partner.get("username")
                p_item_pic = p_item_partner.get("profile_picture_url")
                p_item_streak = p_item.get("duo_streak", 0)
                p_item_label = f"@{p_item_uname}" if p_item_uname else p_item_first

                avatar_widget = ft.CircleAvatar(
                    foreground_image_src=p_item_pic if (p_item_pic and str(p_item_pic).startswith("http")) else None,
                    content=ft.Text(
                        (p_item_first or "?")[:1].upper(),
                        size=9,
                        weight=ft.FontWeight.W_800,
                        color=ft.Colors.WHITE if is_sel else ft.Colors.PRIMARY,
                    ) if not (p_item_pic and str(p_item_pic).startswith("http")) else None,
                    radius=10,
                    bgcolor=ft.Colors.with_opacity(0.35, ft.Colors.WHITE) if is_sel else ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                )

                p_chips.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                        border_radius=ft.BorderRadius.all(10),
                        bgcolor=ft.Colors.PRIMARY if is_sel else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                        border=ft.Border.all(1.2, ft.Colors.PRIMARY if is_sel else ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                        ink=not is_sel,
                        on_click=(lambda i=idx: lambda _: _on_switch_partner(i))() if not is_sel else None,
                        content=ft.Row(
                            spacing=6,
                            tight=True,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                avatar_widget,
                                ft.Text(
                                    f"🔥 {p_item_label}",
                                    size=11,
                                    weight=ft.FontWeight.W_800 if is_sel else ft.FontWeight.W_600,
                                    color=ft.Colors.WHITE if is_sel else ft.Colors.ON_SURFACE,
                                    no_wrap=True,
                                ),
                                ft.Text(
                                    f"{p_item_streak}d",
                                    size=10.5,
                                    weight=ft.FontWeight.W_700 if is_sel else ft.FontWeight.W_500,
                                    color=ft.Colors.WHITE70 if is_sel else ft.Colors.GREY_500,
                                    no_wrap=True,
                                ),
                            ],
                        ),
                    )
                )
            switcher_row = ft.Container(
                content=ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Row(
                            spacing=4,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.PEOPLE_ALT_ROUNDED, size=13, color=ft.Colors.PRIMARY),
                                ft.Text(f"Duos ({len(active_partnerships_list)}):", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.GREY_600, no_wrap=True),
                            ],
                        ),
                        ft.Row(
                            spacing=6,
                            scroll=ft.ScrollMode.HIDDEN,
                            expand=True,
                            controls=p_chips,
                        ),
                    ],
                ),
                padding=ft.Padding.only(bottom=4),
            )

        offline_badge = ft.Container(
            padding=ft.Padding.symmetric(horizontal=7, vertical=2.5),
            border_radius=ft.BorderRadius.all(6),
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER),
            content=ft.Row(
                spacing=3,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.WIFI_OFF_ROUNDED, size=11, color=ft.Colors.AMBER_800),
                    ft.Text("Offline (Cached)", size=10.5, weight=ft.FontWeight.W_700, color=ft.Colors.AMBER_900),
                ],
            ),
        ) if is_offline_state else ft.Container()

        # Duo Streak Milestones
        milestones = [(3, 30), (5, 60), (7, 100), (14, 250), (30, 600)]
        next_m = next((m for m in milestones if m[0] > duo_streak), None)
        next_m_label = f"Next: {next_m[0]}d (+{next_m[1]}🪙)" if next_m else "Max Milestone! 🌟"

        recent_challenges = p_data.get("recent_challenges", [])
        pending_challenge = next((c for c in recent_challenges if c.get("needs_my_response")), None)

        # Avatar
        if p_pic and str(p_pic).startswith("http"):
            avatar = ft.CircleAvatar(
                foreground_image_src=p_pic,
                radius=18,
                bgcolor=ft.Colors.PRIMARY_CONTAINER,
            )
        else:
            avatar = ft.CircleAvatar(
                content=ft.Text(_initials(p_first, p_last), size=12, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY),
                bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.PRIMARY),
                radius=18,
            )

        # Progress calculation
        user_frac = min(user_mins / max(daily_mins_target, 1), 1.0)
        partner_frac = min(partner_mins / max(daily_mins_target, 1), 1.0)

        # Nudge button logic
        nudge_spinner = ft.ProgressRing(width=14, height=14, stroke_width=2, color=ft.Colors.PRIMARY, visible=False)
        nudge_btn_content = ft.Row(
            tight=True,
            spacing=4,
            controls=[
                ft.Icon(ft.Icons.NOTIFICATIONS_ACTIVE_ROUNDED, size=13, color=ft.Colors.PRIMARY if can_nudge else ft.Colors.GREY_400),
                ft.Text("Nudge" if can_nudge else "Nudged", size=11.5, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY if can_nudge else ft.Colors.GREY_500),
                nudge_spinner,
            ],
        )

        is_nudging = False

        async def _handle_nudge(e=None):
            nonlocal is_nudging
            if is_offline_state:
                show_page_snackbar(page, "You are currently offline. Connect to the internet to nudge your partner!")
                return
            if is_nudging or not can_nudge:
                if not can_nudge:
                    show_page_snackbar(page, f"You recently nudged {p_first}. Please wait before nudging again.")
                return
            is_nudging = True
            nudge_spinner.visible = True
            nudge_btn.on_click = None
            nudge_btn.ink = False
            page.update()
            try:
                res = await nudge_study_partner(token, p_id)
                if res and not res.get("error"):
                    show_page_snackbar(page, f"Nudge sent to {p_first}! 🔥")
                    nudge_btn.content.controls[1].value = "Nudged"
                    nudge_btn.content.controls[0].color = ft.Colors.GREY_400
                else:
                    show_page_snackbar(page, res.get("error", "Could not send nudge."))
                    if can_nudge:
                        nudge_btn.on_click = lambda _: page.run_task(_handle_nudge)
                        nudge_btn.ink = True
            except Exception as ex:
                show_page_snackbar(page, f"Error: {ex}")
                if can_nudge:
                    nudge_btn.on_click = lambda _: page.run_task(_handle_nudge)
                    nudge_btn.ink = True
            finally:
                nudge_spinner.visible = False
                is_nudging = False
                page.update()

        nudge_btn = ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            height=38,
            alignment=ft.Alignment.CENTER,
            border_radius=ft.BorderRadius.all(10),
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY) if can_nudge else ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
            ink=can_nudge,
            on_click=(lambda _: page.run_task(_handle_nudge)) if can_nudge else None,
            content=nudge_btn_content,
        )

        my_user_id = p_data.get("current_user_id")

        def _open_share_pack_dialog():
            if is_offline_state:
                show_page_snackbar(page, "You are currently offline. Connect to the internet to share study packs!")
                return

            share_dlg = [None]

            # Inline feedback inside the dialog (a snackbar can render behind a modal on mobile).
            status_txt = ft.Text("", size=11, weight=ft.FontWeight.W_600, visible=False)

            def _set_status(msg: str, is_error: bool = True):
                status_txt.value = msg
                status_txt.color = ft.Colors.ERROR if is_error else ft.Colors.GREEN_700
                status_txt.visible = bool(msg)
                status_txt.update()

            def _close_share(e=None):
                dlg = share_dlg[0]
                if not dlg:
                    return
                # Close this specific dialog. page.pop_dialog() closes whichever dialog is
                # topmost, which can be a SnackBar rather than this dialog.
                dlg.open = False
                try:
                    dlg.update()
                except Exception:
                    page.update()

            # --- Responsive sizing ---
            page_w = page.width or 360
            page_h = page.height or 640
            dlg_w = max(240, min(480, page_w - 64))               # 16px inset + 16px content padding each side
            max_list_h = min(360, int(page_h * 0.5))    # never taller than half the screen

            content_col = ft.Column(spacing=8, tight=True, scroll=ft.ScrollMode.AUTO)
            materials = available_materials or []

            if not materials:
                content_col.controls.append(
                    ft.Container(
                        padding=20,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=6,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.FOLDER_OFF_ROUNDED, size=32, color=ft.Colors.GREY_400),
                                ft.Text("No Study Materials in Vault", size=13, weight=ft.FontWeight.W_700),
                                ft.Text(
                                    "Create flashcards, notes, or import past papers in the Self-Study Hub first!",
                                    size=11,
                                    color=ft.Colors.GREY_500,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                            ],
                        ),
                    )
                )
                list_height = None
            else:
                for mat in materials:
                    m_id = str(mat.get("id") or mat.get("pack_id") or "")
                    m_title = mat.get("title") or "Study Material"
                    m_type = (mat.get("source_type") or "text").upper()

                    btn = ft.ElevatedButton(
                        content=ft.Text("Share", size=12, weight=ft.FontWeight.W_700, no_wrap=True),
                        bgcolor=ft.Colors.PRIMARY,
                        color=ft.Colors.WHITE,
                        height=36,  # bigger tap target than 30
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=8),
                            elevation=0,
                            padding=ft.Padding.symmetric(horizontal=14),
                        ),
                    )

                    def _make_share_handler(pack_id, pack_title, s_btn):
                        async def _on_share(e=None):
                            if s_btn.disabled:
                                return
                            s_btn.disabled = True
                            s_btn.content = ft.ProgressRing(width=14, height=14, stroke_width=2, color=ft.Colors.WHITE)
                            _set_status("")
                            s_btn.update()
                            try:
                                res = await share_study_pack_api(token, p_id, pack_id)
                            except Exception as ex:
                                res = {"error": f"Couldn't share: {ex}"}
                            if not isinstance(res, dict):
                                res = {}
                            if res.get("status") == "success":
                                _close_share()
                                show_page_snackbar(page, f"Shared '{pack_title[:24]}' with {p_first}! 🎉 Ready for study duels.")
                                page.run_task(_load_partner_state)
                            else:
                                s_btn.content = ft.Text("Share", size=12, weight=ft.FontWeight.W_700, no_wrap=True)
                                s_btn.disabled = False
                                s_btn.update()
                                _set_status(res.get("error") or "Error sharing study pack.")
                        return _on_share

                    btn.on_click = _make_share_handler(m_id, m_title, btn)

                    content_col.controls.append(
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                            border_radius=ft.BorderRadius.all(10),
                            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                            content=ft.Row(
                                spacing=8,
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Column(
                                        spacing=2,
                                        tight=True,
                                        expand=True,
                                        controls=[
                                            ft.Text(m_title, size=12.5, weight=ft.FontWeight.W_700,
                                                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                            ft.Text(f"Type: {m_type}", size=11, color=ft.Colors.GREY_500,
                                                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                        ],
                                    ),
                                    btn,
                                ],
                            ),
                        )
                    )

                # ~58px per row + 8px spacing; short lists stay compact, long ones scroll
                list_height = min(max_list_h, len(materials) * 66)

            share_dlg[0] = ft.AlertDialog(
                modal=True,
                shape=ft.RoundedRectangleBorder(radius=18),
                bgcolor=ft.Colors.SURFACE,
                inset_padding=ft.Padding.symmetric(horizontal=16, vertical=24),
                title_padding=ft.Padding.only(left=16, right=16, top=16, bottom=4),
                content_padding=ft.Padding.symmetric(horizontal=16, vertical=8),
                actions_padding=ft.Padding.only(left=16, right=16, bottom=12),
                title=ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.FOLDER_SHARED_ROUNDED, color=ft.Colors.PRIMARY, size=22),
                        ft.Text(
                            f"Share Study Pack with {p_first}",
                            size=14,
                            weight=ft.FontWeight.W_800,
                            expand=True,                      # lets the text shrink instead of overflowing
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                ),
                content=ft.Column(
                    tight=True,
                    spacing=6,
                    controls=[
                        status_txt,
                        ft.Container(width=dlg_w, height=list_height, content=content_col),
                    ],
                ),
                actions=[ft.TextButton("Cancel", on_click=_close_share)],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            if hasattr(page, "show_dialog"):
                page.show_dialog(share_dlg[0])      # Flet >= 1.0
            else:
                page.overlay.append(share_dlg[0])   # legacy Flet
                share_dlg[0].open = True
                page.update()

        share_pack_btn = ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            height=38,
            alignment=ft.Alignment.CENTER,
            border_radius=ft.BorderRadius.all(10),
            bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.PRIMARY),
            ink=True,
            on_click=lambda _: _open_share_pack_dialog(),
            content=ft.Row(
                tight=True,
                spacing=4,
                controls=[
                    ft.Icon(ft.Icons.FOLDER_SHARED_ROUNDED, size=13, color=ft.Colors.PRIMARY),
                    ft.Text("Share Pack", size=11.5, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY),
                ],
            ),
        )

        duel_btn = ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            height=38,
            alignment=ft.Alignment.CENTER,
            border_radius=ft.BorderRadius.all(10),
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.ORANGE),
            ink=True,
            on_click=(
                (lambda _: show_page_snackbar(page, "You are currently offline. Connect to the internet to play CBT Duels!"))
                if is_offline_state
                else (lambda _: show_create_duel_dialog(
                    page=page,
                    token=token,
                    partnership_id=p_id,
                    partner=partner,
                    available_materials=available_materials or [],
                    on_duel_created=lambda: page.run_task(_load_partner_state),
                ))
            ),
            content=ft.Row(
                tight=True,
                spacing=4,
                controls=[
                    ft.Icon(ft.Icons.FLASH_ON_ROUNDED, size=13, color=ft.Colors.ORANGE_700),
                    ft.Text("15-Q Duel", size=11.5, weight=ft.FontWeight.W_800, color=ft.Colors.ORANGE_800),
                ],
            ),
        )

        def _link_btn(icon, icon_color, label, label_color, on_click):
            return ft.TextButton(
                height=36,
                content=ft.Row(
                    spacing=3,
                    tight=True,
                    controls=[
                        icon if isinstance(icon, ft.Control) else ft.Icon(icon, size=14, color=icon_color),
                        ft.Text(label, size=11.5, weight=ft.FontWeight.W_700, color=label_color, no_wrap=True),
                    ],
                ),
                style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=8, vertical=4)),
                on_click=on_click,
            )

        # Pending challenge callout banner
        # Pending challenge callout banner — ONLY show if there is an active actionable challenge
        pending_banner = ft.Container()
        active_challenge = next((c for c in (p_data.get("recent_challenges") or []) if c.get("needs_my_response") and c.get("status") == "challenger_done"), None)
        if active_challenge:
            c_id = active_challenge.get("id")
            pending_banner = ft.Container(
                margin=ft.Margin.only(top=8),
                padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                border_radius=ft.BorderRadius.all(10),
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.ORANGE),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.ORANGE_700)),
                content=ft.ResponsiveRow(
                    spacing=8,
                    run_spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Row(
                            col={"xs": 12, "sm": 8},
                            spacing=6,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(ft.Icons.FLASH_ON_ROUNDED, size=16, color=ft.Colors.ORANGE_700),
                                ft.Text(
                                    f"⚔️ {p_first} challenged you to a 15-Q Duel!",
                                    size=12,
                                    weight=ft.FontWeight.W_700,
                                    color=ft.Colors.ORANGE_800,
                                    expand=True,   # wraps to multiple lines instead of overflowing
                                ),
                            ],
                        ),
                        ft.Container(
                            col={"xs": 12, "sm": 4},
                            alignment=ft.Alignment.CENTER_RIGHT,
                            content=ft.ElevatedButton(
                                content=ft.Row(
                                    tight=True,
                                    spacing=4,
                                    controls=[
                                        ft.Icon(ft.Icons.FLASH_ON_ROUNDED, size=14, color=ft.Colors.WHITE),
                                        ft.Text("Play Duel Now", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE, no_wrap=True),
                                    ],
                                ),
                                bgcolor=ft.Colors.ORANGE_800,
                                height=38,
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=8),
                                    elevation=0,
                                    padding=ft.Padding.symmetric(horizontal=12),
                                ),
                                on_click=lambda _: show_duel_results_dialog(
                                    page=page,
                                    challenge=active_challenge,
                                    current_user_id=my_user_id,
                                    token=token,
                                    partnership_id=p_id,
                                    on_duel_updated=lambda: page.run_task(_load_partner_state),
                                ),
                            ),
                        ),
                    ],
                ),
            )

        is_desktop = (page.width or 800) >= 768

        streak_threshold = p_data.get("streak_threshold_minutes", 10)
        user_streak_qualified = p_data.get("user_streak_qualified", user_mins >= streak_threshold)
        partner_streak_qualified = p_data.get("partner_streak_qualified", partner_mins >= streak_threshold)
        duo_streak_locked_today = p_data.get("duo_streak_locked_today", False)

        if duo_streak_locked_today or (user_streak_qualified and partner_streak_qualified):
            streak_status_msg = "🔥 Duo Streak secured for today!"
            streak_status_color = ft.Colors.GREEN_600
            streak_status_icon = ft.Icons.CHECK_CIRCLE_ROUNDED
        elif user_streak_qualified and not partner_streak_qualified:
            streak_status_msg = f"You're qualified ({user_mins}m)! Waiting for {p_first} ({partner_mins}/{streak_threshold}m)"
            streak_status_color = ft.Colors.AMBER_700
            streak_status_icon = ft.Icons.HOURGLASS_TOP_ROUNDED
        elif not user_streak_qualified and partner_streak_qualified:
            rem = max(1, streak_threshold - user_mins)
            streak_status_msg = f"⚡ {p_first} completed their part! Study {rem}m more to save your {duo_streak}d Duo Streak" if duo_streak > 0 else f"{p_first} is ready! Study {rem}m more to lock Duo Streak"
            streak_status_color = ft.Colors.ORANGE_700
            streak_status_icon = ft.Icons.ELECTRIC_BOLT_ROUNDED
        elif duo_streak >= 1 and not user_streak_qualified and not partner_streak_qualified:
            streak_status_msg = f"🔥 {duo_streak}d Duo Streak at risk! Both partners need {streak_threshold}m before midnight"
            streak_status_color = ft.Colors.AMBER_800
            streak_status_icon = ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED
        else:
            streak_status_msg = f"Both study {streak_threshold}m daily to grow Duo Streak (You: {user_mins}m, {p_first}: {partner_mins}m)"
            streak_status_color = ft.Colors.GREY_500
            streak_status_icon = ft.Icons.INFO_OUTLINE_ROUNDED

        # Desktop pill buttons
        duel_pill = ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            border_radius=ft.BorderRadius.all(16),
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.ORANGE),
            ink=True,
            on_click=(
                (lambda _: show_page_snackbar(page, "You are currently offline. Connect to the internet to play CBT Duels!"))
                if is_offline_state
                else (lambda _: show_create_duel_dialog(
                    page=page,
                    token=token,
                    partnership_id=p_id,
                    partner=partner,
                    available_materials=available_materials or [],
                    on_duel_created=lambda: page.run_task(_load_partner_state),
                ))
            ),
            content=ft.Row(
                tight=True,
                spacing=5,
                controls=[
                    ft.Icon(ft.Icons.FLASH_ON_ROUNDED, size=13, color=ft.Colors.ORANGE_700),
                    ft.Text("15-Q Duel", size=11.5, weight=ft.FontWeight.W_700, color=ft.Colors.ORANGE_800),
                ],
            ),
        )

        nudge_pill = ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            border_radius=ft.BorderRadius.all(16),
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY) if can_nudge else ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
            ink=can_nudge,
            on_click=(lambda _: page.run_task(_handle_nudge)) if can_nudge else None,
            content=nudge_btn_content,
        )

        share_pill = ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            border_radius=ft.BorderRadius.all(16),
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
            ink=True,
            on_click=lambda _: _open_share_pack_dialog(),
            content=ft.Row(
                tight=True,
                spacing=5,
                controls=[
                    ft.Icon(ft.Icons.FOLDER_SHARED_ROUNDED, size=13, color=ft.Colors.PRIMARY),
                    ft.Text("Share Pack", size=11.5, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY),
                ],
            ),
        )

        objectives_pill = ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            border_radius=ft.BorderRadius.all(16),
            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.AMBER),
            ink=True,
            on_click=lambda _: page.go("/leaderboards?tab=objectives"),
            content=ft.Row(
                tight=True,
                spacing=4,
                controls=[
                    nu_coin_icon(size=14),
                    ft.Text("Objectives", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.AMBER_900),
                ],
            ),
        )

        packs_pill = ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            border_radius=ft.BorderRadius.all(16),
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
            ink=True,
            on_click=lambda _: show_objectives_and_leaderboard_dialog(page, token, p_id, partner, "shared_packs", on_coins_changed=lambda: page.run_task(_load_partner_state)),
            content=ft.Row(
                tight=True,
                spacing=4,
                controls=[
                    ft.Icon(ft.Icons.FOLDER_SHARED_ROUNDED, size=13, color=ft.Colors.PRIMARY),
                    ft.Text("Packs", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                ],
            ),
        )

        ranks_pill = ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            border_radius=ft.BorderRadius.all(16),
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
            ink=True,
            on_click=lambda _: page.go("/leaderboards?tab=leaderboards"),
            content=ft.Row(
                tight=True,
                spacing=4,
                controls=[
                    ft.Icon(ft.Icons.LEADERBOARD_ROUNDED, size=13, color=ft.Colors.PRIMARY),
                    ft.Text("Ranks", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                ],
            ),
        )

        history_pill = ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            border_radius=ft.BorderRadius.all(16),
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
            ink=True,
            on_click=lambda _: page.go("/leaderboards?tab=history"),
            content=ft.Row(
                tight=True,
                spacing=4,
                controls=[
                    ft.Icon(ft.Icons.HISTORY_ROUNDED, size=13, color=ft.Colors.BLUE_700),
                    ft.Text("History", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.BLUE_800),
                ],
            ),
        )

        # ─── DESKTOP COCKPIT (Sleek 2-Row Horizontal Bar with Pill Buttons) ───
        if is_desktop:
            return ft.Container(
                padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                border_radius=ft.BorderRadius.all(16),
                bgcolor=ft.Colors.SURFACE,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY)),
                shadow=ft.BoxShadow(
                    blur_radius=10,
                    color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                    offset=ft.Offset(0, 2),
                ),
                content=ft.Column(
                    tight=True,
                    spacing=8,
                    controls=([switcher_row] if switcher_row else []) + [
                        # Row 1: Partner Info + Streak Flame Pill + Core Partner Action Pills
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            wrap=True,
                            run_spacing=8,
                            controls=[
                                # Left: Partner Info + Duo Streak Flame pill
                                ft.Row(
                                    spacing=8,
                                    tight=True,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        avatar,
                                        ft.Text(p_display_name, size=13.5, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                        ft.Container(
                                            width=7,
                                            height=7,
                                            border_radius=4,
                                            bgcolor=ft.Colors.GREEN if partner_done else ft.Colors.GREY_400,
                                        ),
                                        ft.Text(
                                            "Studied today" if partner_done else "Not yet today",
                                            size=11,
                                            color=ft.Colors.GREY_500,
                                        ),
                                        ft.Container(
                                            padding=ft.Padding.symmetric(horizontal=9, vertical=4),
                                            border_radius=ft.BorderRadius.all(14),
                                            gradient=ft.LinearGradient(
                                                colors=[ft.Colors.AMBER_600, ft.Colors.ORANGE_600],
                                                begin=ft.Alignment.TOP_LEFT,
                                                end=ft.Alignment.BOTTOM_RIGHT,
                                            ),
                                            content=ft.Row(
                                                spacing=4,
                                                tight=True,
                                                controls=[
                                                    ft.Icon(ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED, size=13, color=ft.Colors.WHITE),
                                                    ft.Text(f"{duo_streak}d Duo Streak", size=11, weight=ft.FontWeight.W_800, color=ft.Colors.WHITE, no_wrap=True),
                                                ],
                                            ),
                                        ),
                                    ],
                                ),
                                # Right: Core Action Pills
                                ft.Row(
                                    spacing=6,
                                    tight=True,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=([offline_badge] if is_offline_state else []) + [
                                        duel_pill,
                                        nudge_pill,
                                        share_pill,
                                    ],
                                ),
                            ],
                        ),
                        # Row 2: Streak Qualification Status + Secondary Navigation Pills
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            wrap=True,
                            run_spacing=6,
                            controls=[
                                # Left: Streak qualification status feedback
                                ft.Row(
                                    spacing=5,
                                    tight=True,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.Icon(streak_status_icon, size=13, color=streak_status_color),
                                        ft.Text(streak_status_msg, size=11, weight=ft.FontWeight.W_600, color=streak_status_color),
                                    ],
                                ),
                                # Right: Navigation pills
                                ft.Row(
                                    spacing=6,
                                    tight=True,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        objectives_pill,
                                        packs_pill,
                                        ranks_pill,
                                        history_pill,
                                    ],
                                ),
                            ],
                        ),
                        pending_banner,
                    ],
                ),
            )

        # ─── MOBILE COCKPIT (Rich Card Layout preserved as requested) ───
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=16, vertical=14),
            border_radius=ft.BorderRadius.all(18),
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY)),
            shadow=ft.BoxShadow(
                blur_radius=12,
                color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                offset=ft.Offset(0, 3),
            ),
            content=ft.Column(
                tight=True,
                spacing=10,
                controls=([switcher_row] if switcher_row else []) + [
                    # Header row 1: partner profile + Duo streak pill (always fits on one line)
                    ft.Row(
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            avatar,
                            ft.Column(
                                spacing=1,
                                tight=True,
                                expand=True,
                                controls=[
                                    ft.Text(p_display_name, size=13, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE,
                                            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                    ft.Row(
                                        spacing=5,
                                        tight=True,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                        controls=[
                                            ft.Container(
                                                width=7,
                                                height=7,
                                                border_radius=4,
                                                bgcolor=ft.Colors.GREEN if partner_done else ft.Colors.GREY_400,
                                            ),
                                            ft.Text(
                                                "Studied today" if partner_done else "Not yet today",
                                                size=11,
                                                color=ft.Colors.GREY_500,
                                                max_lines=1,
                                                overflow=ft.TextOverflow.ELLIPSIS,
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=9, vertical=4),
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
                                        ft.Icon(ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED, size=13, color=ft.Colors.WHITE),
                                        ft.Text(f"{duo_streak}d Duo Streak", size=11, weight=ft.FontWeight.W_800,
                                                color=ft.Colors.WHITE, no_wrap=True),
                                    ],
                                ),
                            ),
                        ],
                    ),
                    # Header row 2: action buttons
                    ft.Row(
                        spacing=8,
                        run_spacing=8,
                        wrap=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=([offline_badge] if is_offline_state else []) + [
                            nudge_btn,
                            duel_btn,
                            share_pack_btn,
                        ],
                    ),
                    # Dual Progress Meters
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                        border_radius=ft.BorderRadius.all(12),
                        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                        content=ft.Column(
                            tight=True,
                            spacing=6,
                            controls=[
                                # You row
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Row(
                                            spacing=4,
                                            tight=True,
                                            controls=[
                                                ft.Icon(
                                                    ft.Icons.CHECK_CIRCLE_ROUNDED if user_done else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED,
                                                    size=13,
                                                    color=ft.Colors.GREEN_600 if user_done else ft.Colors.GREY_500,
                                                ),
                                                ft.Text("You", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                                            ],
                                        ),
                                        ft.Text(f"{user_mins} / {daily_mins_target} mins", size=11.5, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_600),
                                    ],
                                ),
                                ft.ProgressBar(value=user_frac, color=ft.Colors.PRIMARY, bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY), height=5),
                                # Partner row
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Row(
                                            spacing=4,
                                            tight=True,
                                            controls=[
                                                ft.Icon(
                                                    ft.Icons.CHECK_CIRCLE_ROUNDED if partner_done else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED,
                                                    size=13,
                                                    color=ft.Colors.GREEN_600 if partner_done else ft.Colors.GREY_500,
                                                ),
                                                ft.Text(f"{p_first} (@{p_username})" if p_username else p_first, size=11, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                                            ],
                                        ),
                                        ft.Text(f"{partner_mins} / {daily_mins_target} mins", size=11.5, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_600),
                                    ],
                                ),
                                ft.ProgressBar(value=partner_frac, color=ft.Colors.TEAL_600, bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.TEAL), height=5),
                            ],
                        ),
                    ),
                    # Streak qualification status banner
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                        border_radius=ft.BorderRadius.all(8),
                        bgcolor=ft.Colors.with_opacity(0.06, streak_status_color),
                        content=ft.Row(
                            spacing=6,
                            tight=True,
                            controls=[
                                ft.Icon(streak_status_icon, size=13, color=streak_status_color),
                                ft.Text(streak_status_msg, size=11, weight=ft.FontWeight.W_700, color=streak_status_color, expand=True),
                            ],
                        ),
                    ),
                    # Action & Milestone Toolbar (wraps on narrow screens)
                    ft.Row(
                        spacing=6,
                        run_spacing=4,
                        wrap=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=8, vertical=5),
                                border_radius=ft.BorderRadius.all(8),
                                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.AMBER),
                                content=ft.Row(
                                    spacing=4,
                                    tight=True,
                                    controls=[
                                        ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=12, color=ft.Colors.AMBER_800),
                                        ft.Text(next_m_label, size=11, weight=ft.FontWeight.W_700, color=ft.Colors.AMBER_900, no_wrap=True),
                                    ],
                                ),
                            ),
                            _link_btn(nu_coin_icon(size=14), ft.Colors.AMBER_800, "Objectives", ft.Colors.AMBER_900,
                                      lambda _: page.go("/leaderboards?tab=objectives")),
                            _link_btn(ft.Icons.FOLDER_SHARED_ROUNDED, ft.Colors.PRIMARY, "Packs", ft.Colors.PRIMARY,
                                      lambda _: show_objectives_and_leaderboard_dialog(page, token, p_id, partner, "shared_packs", on_coins_changed=lambda: page.run_task(_load_partner_state))),
                            _link_btn(ft.Icons.LEADERBOARD_ROUNDED, ft.Colors.PRIMARY, "Ranks", ft.Colors.PRIMARY,
                                      lambda _: page.go("/leaderboards?tab=leaderboards")),
                            _link_btn(ft.Icons.HISTORY_ROUNDED, ft.Colors.BLUE_700, "History", ft.Colors.BLUE_800,
                                      lambda _: page.go("/leaderboards?tab=history")),
                        ],
                    ),
                    pending_banner,
                ],
            ),
        )

    # Responsive resize handling to dynamically adapt between desktop pill buttons and mobile card
    last_is_desktop = [(page.width or 800) >= 768]

    def _on_page_resize(e=None):
        if getattr(card_container, "_page", None) is None:
            return
        try:
            current_is_desktop = (page.width or 800) >= 768
            if current_is_desktop != last_is_desktop[0]:
                last_is_desktop[0] = current_is_desktop
                if active_partnerships_list and selected_p_idx < len(active_partnerships_list):
                    card_container.content = _build_active_card(active_partnerships_list[selected_p_idx])
                    if getattr(card_container, "_page", None) is not None:
                        card_container.update()
        except Exception:
            pass

    prev_resize = getattr(page, "on_resize", None)
    def _chained_resize(e):
        if callable(prev_resize):
            try:
                prev_resize(e)
            except Exception:
                pass
        try:
            _on_page_resize(e)
        except Exception:
            pass

    try:
        page.on_resize = _chained_resize
    except Exception:
        pass

    # Launch initial async load
    page.run_task(_load_partner_state)

    return card_container