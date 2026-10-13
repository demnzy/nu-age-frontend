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

from src.utils.file_opener import show_page_snackbar
from src.requests.study_partners import (
    get_active_partnership,
    nudge_study_partner,
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
    card_container = ft.Container(
        margin=ft.Margin.only(bottom=12),
        visible=False, # Hidden until data is fetched to prevent UI jitter
    )

    async def _load_partner_state():
        if not token:
            return

        res = await get_active_partnership(token)
        if not res or not res.get("has_partnership"):
            # Render Empty / Promotional Invite Card
            card_container.content = _build_invite_card()
            card_container.visible = True
            page.update()
            return

        p_data = res.get("partnership", {})
        card_container.content = _build_active_card(p_data)
        card_container.visible = True
        page.update()

    def _build_invite_card() -> ft.Container:
        is_mobile = bool(page.width and page.width < 768)
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
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        spacing=12,
                        tight=True,
                        expand=True,
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
                                    ft.Row(
                                        spacing=6,
                                        tight=True,
                                        controls=[
                                            ft.Text("Accountability Duo", size=13, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                            ft.Container(
                                                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                                border_radius=ft.BorderRadius.all(6),
                                                bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.PRIMARY),
                                                content=ft.Text("NEW", size=8.5, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY),
                                            ),
                                        ],
                                    ),
                                    ft.Text(
                                        "Pair up with a study partner to maintain daily streaks & challenge each other in CBT Duels.",
                                        size=11,
                                        color=ft.Colors.GREY_500,
                                        max_lines=2,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                ],
                            ),
                        ],
                    ),
                    ft.Row(
                        spacing=8,
                        tight=True,
                        controls=[
                            ft.OutlinedButton(
                                content=ft.Row(
                                    tight=True,
                                    spacing=4,
                                    controls=[
                                        ft.Icon(ft.Icons.MONETIZATION_ON_ROUNDED, size=14, color=ft.Colors.AMBER_800),
                                        ft.Text("Nu-Coins", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.AMBER_900),
                                    ],
                                ),
                                height=36,
                                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), padding=ft.Padding.symmetric(horizontal=10)),
                                on_click=lambda _: show_objectives_and_leaderboard_dialog(page, token, initial_tab="objectives"),
                            ),
                            ft.ElevatedButton(
                                content=ft.Row(
                                    tight=True,
                                    spacing=6,
                                    controls=[
                                        ft.Icon(ft.Icons.PERSON_ADD_ALT_1_ROUNDED, size=15, color=ft.Colors.WHITE),
                                        ft.Text("Find Partner", size=11.5, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                                    ],
                                ),
                                bgcolor=ft.Colors.PRIMARY,
                                height=36,
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=10),
                                    elevation=0,
                                    padding=ft.Padding.symmetric(horizontal=12),
                                ),
                                on_click=lambda _: page.go("/network?tab=partners"),
                            ),
                        ],
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

        duo_streak = p_data.get("duo_streak", 0)
        daily_mins_target = p_data.get("daily_target_minutes", 45)
        user_mins = p_data.get("user_today_minutes", 0)
        partner_mins = p_data.get("partner_today_minutes", 0)
        user_done = p_data.get("user_studied_today", False)
        partner_done = p_data.get("partner_studied_today", False)
        can_nudge = p_data.get("can_nudge", True)

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
                ft.Text("Nudge" if can_nudge else "Nudged", size=10.5, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY if can_nudge else ft.Colors.GREY_500),
                nudge_spinner,
            ],
        )

        is_nudging = False

        async def _handle_nudge(e=None):
            nonlocal is_nudging
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
            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            border_radius=ft.BorderRadius.all(8),
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY) if can_nudge else ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
            ink=can_nudge,
            on_click=(lambda _: page.run_task(_handle_nudge)) if can_nudge else None,
            content=nudge_btn_content,
        )

        duel_btn = ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            border_radius=ft.BorderRadius.all(8),
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.ORANGE),
            ink=True,
            on_click=lambda _: show_create_duel_dialog(
                page=page,
                token=token,
                partnership_id=p_id,
                partner=partner,
                available_materials=available_materials or [],
                on_duel_created=lambda: page.run_task(_load_partner_state),
            ),
            content=ft.Row(
                tight=True,
                spacing=4,
                controls=[
                    ft.Icon(ft.Icons.FLASH_ON_ROUNDED, size=13, color=ft.Colors.ORANGE_700),
                    ft.Text("15-Q Duel", size=10.5, weight=ft.FontWeight.W_800, color=ft.Colors.ORANGE_800),
                ],
            ),
        )

        # Pending challenge callout banner
        pending_banner = ft.Container()
        if pending_challenge:
            c_id = pending_challenge.get("id")
            pending_banner = ft.Container(
                margin=ft.Margin.only(top=8),
                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                border_radius=ft.BorderRadius.all(10),
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.ORANGE),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.ORANGE_700)),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Row(
                            spacing=6,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.FLASH_ON_ROUNDED, size=15, color=ft.Colors.ORANGE_700),
                                ft.Text(f"{p_first} challenged you to a 15-Q Duel!", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.ORANGE_800),
                            ],
                        ),
                        ft.TextButton(
                            "View & Play",
                            style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=8, vertical=2)),
                            on_click=lambda _: show_duel_results_dialog(
                                page=page,
                                challenge=pending_challenge,
                                current_user_id=partner.get("id"),
                                token=token,
                                partnership_id=p_id,
                                on_duel_updated=lambda: page.run_task(_load_partner_state),
                            ),
                        ),
                    ],
                ),
            )

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
                controls=[
                    # Header: Partner Profile & Duo Streak Pill
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(
                                spacing=10,
                                tight=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    avatar,
                                    ft.Column(
                                        spacing=1,
                                        tight=True,
                                        controls=[
                                            ft.Row(
                                                spacing=4,
                                                tight=True,
                                                controls=[
                                                    ft.Text(p_name, size=13, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                                    ft.Container(
                                                        width=6,
                                                        height=6,
                                                        border_radius=3,
                                                        bgcolor=ft.Colors.GREEN if partner_done else ft.Colors.GREY_400,
                                                    ),
                                                ],
                                            ),
                                            ft.Text(p_uni, size=10.5, color=ft.Colors.GREY_500),
                                        ],
                                    ),
                                ],
                            ),
                            ft.Row(
                                spacing=6,
                                tight=True,
                                controls=[
                                    # Duo Streak Badge
                                    ft.Container(
                                        padding=ft.Padding.symmetric(horizontal=9, vertical=3.5),
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
                                                ft.Text(f"{duo_streak}d Duo Streak", size=10.5, weight=ft.FontWeight.W_800, color=ft.Colors.WHITE),
                                            ],
                                        ),
                                    ),
                                    nudge_btn,
                                    duel_btn,
                                ],
                            ),
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
                                        ft.Text(f"{user_mins} / {daily_mins_target} mins", size=10.5, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_600),
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
                                                ft.Text(p_first, size=11, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                                            ],
                                        ),
                                        ft.Text(f"{partner_mins} / {daily_mins_target} mins", size=10.5, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_600),
                                    ],
                                ),
                                ft.ProgressBar(value=partner_frac, color=ft.Colors.TEAL_600, bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.TEAL), height=5),
                            ],
                        ),
                    ),
                    # Action & Milestone Toolbar
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=8, vertical=3.5),
                                border_radius=ft.BorderRadius.all(8),
                                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.AMBER),
                                content=ft.Row(
                                    spacing=4,
                                    tight=True,
                                    controls=[
                                        ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=12, color=ft.Colors.AMBER_800),
                                        ft.Text(next_m_label, size=10, weight=ft.FontWeight.W_700, color=ft.Colors.AMBER_900),
                                    ],
                                ),
                            ),
                            ft.Row(
                                spacing=4,
                                tight=True,
                                controls=[
                                    ft.TextButton(
                                        content=ft.Row(
                                            spacing=3,
                                            tight=True,
                                            controls=[
                                                ft.Icon(ft.Icons.MONETIZATION_ON_ROUNDED, size=13, color=ft.Colors.AMBER_800),
                                                ft.Text("Nu-Coins", size=10.5, weight=ft.FontWeight.W_700, color=ft.Colors.AMBER_900),
                                            ],
                                        ),
                                        style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=6, vertical=2)),
                                        on_click=lambda _: show_objectives_and_leaderboard_dialog(page, token, p_id, partner, "objectives", on_coins_changed=lambda: page.run_task(_load_partner_state)),
                                    ),
                                    ft.TextButton(
                                        content=ft.Row(
                                            spacing=3,
                                            tight=True,
                                            controls=[
                                                ft.Icon(ft.Icons.FOLDER_SHARED_ROUNDED, size=13, color=ft.Colors.PRIMARY),
                                                ft.Text("Packs", size=10.5, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY),
                                            ],
                                        ),
                                        style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=6, vertical=2)),
                                        on_click=lambda _: show_objectives_and_leaderboard_dialog(page, token, p_id, partner, "shared_packs", on_coins_changed=lambda: page.run_task(_load_partner_state)),
                                    ),
                                    ft.TextButton(
                                        content=ft.Row(
                                            spacing=3,
                                            tight=True,
                                            controls=[
                                                ft.Icon(ft.Icons.LEADERBOARD_ROUNDED, size=13, color=ft.Colors.PRIMARY),
                                                ft.Text("Ranks", size=10.5, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY),
                                            ],
                                        ),
                                        style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=6, vertical=2)),
                                        on_click=lambda _: show_objectives_and_leaderboard_dialog(page, token, p_id, partner, "leaderboard"),
                                    ),
                                ],
                            ),
                        ],
                    ),
                    pending_banner,
                ],
            ),
        )

    # Launch initial async load
    page.run_task(_load_partner_state)

    return card_container
