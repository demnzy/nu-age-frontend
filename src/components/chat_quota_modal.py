"""
Reusable AI Chat Quota Paywall Modal.
Presented when a free-tier learner reaches the 15 queries/day cap in the AI Doubt Assistant
or Course Journal Notebook Tutor.
Strictly follows Flet 0.86.5 conventions and theme token rules.
"""
import flet as ft
from src.components import study_ui as ui


def open_chat_quota_modal(page: ft.Page, quota_info: dict = None, on_upgrade: callable = None):
    """
    Opens an informative, non-intrusive modal notifying the user that their free
    daily AI chat quota (15/15) has been reached and resets at 00:00 UTC.
    """
    quota_info = quota_info or {}
    used_count = quota_info.get("used", 15)
    limit_count = quota_info.get("limit", 15)
    reset_time = quota_info.get("reset_at", "00:00 UTC")

    # Responsive width
    page_w = page.width or 800
    is_mobile = page_w < 600
    modal_width = min(460, int(page_w * 0.92))

    dlg = ft.AlertDialog(
        modal=True,
        shape=ft.RoundedRectangleBorder(radius=20),
        bgcolor=ft.Colors.SURFACE,
        content_padding=ft.Padding.all(22),
    )

    def _close(e=None):
        dlg.open = False
        page.update()

    def _handle_upgrade(e=None):
        dlg.open = False
        page.update()
        if on_upgrade:
            try:
                on_upgrade()
            except Exception:
                page.go("/store")
        else:
            page.go("/store")

    perk_items = [
        ("✨ Unlimited AI Queries", "Ask unlimited questions across all notebooks and materials without daily caps."),
        ("⚡ Grounded Context & Recall", "Full synthesis across multi-module course journals and lecture notes."),
        ("📚 45 Study Materials", "Expand from 10 to 45 materials with priority mock exam synthesis."),
    ]

    perks_col = ft.Column(
        spacing=10,
        controls=[
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                border_radius=ft.BorderRadius.all(12),
                bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.PRIMARY),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY)),
                content=ft.Row(
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    spacing=10,
                    controls=[
                        ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=18, color=ft.Colors.PRIMARY),
                        ft.Column(
                            spacing=2,
                            expand=True,
                            controls=[
                                ft.Text(title, size=12.5, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                                ft.Text(desc, size=11, color=ft.Colors.GREY_500),
                            ],
                        ),
                    ],
                ),
            )
            for title, desc in perk_items
        ],
    )

    action_buttons = (
        ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            spacing=8,
            controls=[
                ft.ElevatedButton(
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=6,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.BOLT_ROUNDED, size=16, color=ft.Colors.ON_PRIMARY),
                            ft.Text("Upgrade to Pro Scholar", size=13, weight=ft.FontWeight.W_700, color=ft.Colors.ON_PRIMARY),
                        ],
                    ),
                    bgcolor=ft.Colors.PRIMARY,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=12),
                        padding=ft.Padding.symmetric(vertical=14),
                    ),
                    on_click=_handle_upgrade,
                ),
                ft.TextButton(
                    content=ft.Text("I'll wait until tomorrow", size=12, color=ft.Colors.GREY_500),
                    on_click=_close,
                ),
            ],
        )
        if is_mobile
        else ft.Row(
            alignment=ft.MainAxisAlignment.END,
            spacing=10,
            controls=[
                ft.TextButton(
                    content=ft.Text("I'll wait until tomorrow", size=12, color=ft.Colors.GREY_500),
                    on_click=_close,
                ),
                ft.ElevatedButton(
                    content=ft.Row(
                        spacing=6,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.BOLT_ROUNDED, size=16, color=ft.Colors.ON_PRIMARY),
                            ft.Text("Upgrade to Pro (₦3,000/mo)", size=12.5, weight=ft.FontWeight.W_700, color=ft.Colors.ON_PRIMARY),
                        ],
                    ),
                    bgcolor=ft.Colors.PRIMARY,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=12),
                        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                    ),
                    on_click=_handle_upgrade,
                ),
            ],
        )
    )

    dlg.content = ft.Container(
        width=modal_width,
        content=ft.Column(
            tight=True,
            spacing=16,
            controls=[
                # Header Badge & Icon
                ft.Row(
                    spacing=12,
                    controls=[
                        ft.Container(
                            width=44,
                            height=44,
                            border_radius=ft.BorderRadius.all(22),
                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_600),
                            alignment=ft.Alignment(0, 0),
                            content=ft.Icon(ft.Icons.LOCK_CLOCK_ROUNDED, size=24, color=ft.Colors.AMBER_600),
                        ),
                        ft.Column(
                            spacing=2,
                            expand=True,
                            controls=[
                                ft.Text("Daily AI Limit Reached", size=16, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                ft.Text(f"{used_count}/{limit_count} free queries used today", size=12, color=ft.Colors.AMBER_600, weight=ft.FontWeight.W_600),
                            ],
                        ),
                        ft.IconButton(
                            icon=ft.Icons.CLOSE_ROUNDED,
                            icon_size=18,
                            icon_color=ft.Colors.GREY_500,
                            tooltip="Dismiss",
                            on_click=_close,
                        ),
                    ],
                ),
                # Reset Explanatory Card
                ft.Container(
                    padding=ft.Padding.all(12),
                    border_radius=ft.BorderRadius.all(12),
                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                    border=ft.Border.all(1, ui.hairline()),
                    content=ft.Row(
                        spacing=8,
                        controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, size=16, color=ft.Colors.GREY_500),
                            ft.Text(
                                f"Free tier learners receive {limit_count} queries each day. Your quota resets every night at {reset_time}.",
                                size=11.5,
                                color=ft.Colors.ON_SURFACE,
                                expand=True,
                            ),
                        ],
                    ),
                ),
                # Pro Perks List
                perks_col,
                # Action Buttons
                ft.Container(
                    padding=ft.Padding.only(top=8),
                    content=action_buttons,
                ),
            ],
        ),
    )

    page.overlay.append(dlg)
    dlg.open = True
    page.update()
