"""
src/components/chat_attachment_sheet.py

Action Sheet Modal for Nu Chat Composer.
Provides lightweight options: Share Image, Voice Note, Create Poll, Ask Nu AI, and Study Duel.
Strictly enforces zero generic file uploads (no document dumping) and adheres to Flet 0.86.5 conventions.
"""

from typing import Callable, Dict, Any, Optional
import flet as ft
from src.utils.modal_guard import safe_open_dialog, safe_close_dialog


def open_chat_actions_sheet(
    page: ft.Page,
    palette: Dict[str, Any],
    on_open_poll: Callable,
    on_trigger_ai: Callable,
    on_trigger_duel: Callable,
    on_pick_image: Optional[Callable] = None,
    on_pick_voice_note: Optional[Callable] = None,
    on_close_callback: Optional[Callable] = None,
):
    """
    Opens a responsive bottom sheet / dialog with modern action tiles.
    """
    def _on_dismiss(e=None):
        if on_close_callback:
            try:
                on_close_callback()
            except Exception:
                pass

    dlg = ft.AlertDialog(
        modal=True,
        shape=ft.RoundedRectangleBorder(radius=16),
        bgcolor=palette.get("card_bg", ft.Colors.SURFACE),
        on_dismiss=_on_dismiss,
        title=ft.Row([
            ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=palette.get("accent", ft.Colors.PRIMARY), size=20),
            ft.Text("Chat Actions", size=16, weight=ft.FontWeight.BOLD, color=palette.get("text", ft.Colors.ON_SURFACE)),
        ], spacing=8),
    )

    def _close(e=None):
        safe_close_dialog(page, dlg)

    def _handle_action(callback: Callable):
        _close()

        async def _run_after_dismiss():
            import asyncio
            import inspect
            await asyncio.sleep(0.06)
            try:
                res = callback()
                if inspect.isawaitable(res):
                    await res
            except Exception as ex:
                print(f"[chat_actions] Callback error: {ex}")

        try:
            page.run_task(_run_after_dismiss)
        except Exception:
            try:
                callback()
            except Exception as ex:
                print(f"[chat_actions] Callback error: {ex}")

    def _action_tile(icon, title: str, subtitle: str, color, on_click_fn):
        return ft.Container(
            ink=True,
            border_radius=10,
            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            on_click=lambda e: _handle_action(on_click_fn),
            content=ft.Row([
                ft.Container(
                    width=38,
                    height=38,
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.12, color),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(icon, size=20, color=color),
                ),
                ft.Column([
                    ft.Text(title, size=13, weight=ft.FontWeight.BOLD, color=palette.get("text", ft.Colors.ON_SURFACE)),
                    ft.Text(subtitle, size=11, color=palette.get("text_muted", ft.Colors.ON_SURFACE_VARIANT)),
                ], spacing=2, expand=True),
                ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, size=18, color=palette.get("text_muted", ft.Colors.ON_SURFACE_VARIANT)),
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

    tiles = []
    if on_pick_image:
        tiles.append(
            _action_tile(
                ft.Icons.IMAGE_OUTLINED,
                "Share Image",
                "Send photos, diagrams, or textbook screenshots",
                ft.Colors.BLUE_500,
                on_pick_image,
            )
        )
    tiles.extend([
        _action_tile(
            ft.Icons.POLL_ROUNDED,
            "Create Poll",
            "Ask questions with live single or multi-option voting",
            ft.Colors.GREEN_600,
            on_open_poll,
        ),
        _action_tile(
            ft.Icons.PSYCHOLOGY_ROUNDED,
            "Ask Nu Study AI",
            "Summon the AI doubt clearing assistant directly in chat (/ai)",
            ft.Colors.PURPLE_500,
            on_trigger_ai,
        ),
        _action_tile(
            ft.Icons.FLASH_ON_ROUNDED,
            "Quickfire Duel",
            "Challenge chat partners to a 15-question fast quiz (/duel)",
            ft.Colors.ORANGE_500,
            on_trigger_duel,
        ),
    ])

    dlg.content = ft.Container(
        width=420,
        content=ft.Column(tiles, spacing=4, tight=True),
    )
    dlg.actions = [
        ft.TextButton(
            "Close",
            style=ft.ButtonStyle(color=palette.get("text_muted", ft.Colors.ON_SURFACE_VARIANT)),
            on_click=_close,
        )
    ]

    safe_open_dialog(page, dlg, tag="chat_actions_sheet")

