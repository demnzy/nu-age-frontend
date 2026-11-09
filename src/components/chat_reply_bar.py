"""
src/components/chat_reply_bar.py

Contextual Quoted Reply Preview Bar for Nu Chat.
Docks directly above the chat input composer when a user chooses to reply to a message.
Follows Flet 0.86.5 conventions and theme tokens strictly.
"""

from typing import Callable, Optional, Dict, Any
import flet as ft


def build_chat_reply_bar(
    reply_data: Optional[Dict[str, Any]],
    palette: Dict[str, Any],
    on_cancel: Callable,
) -> ft.Container:
    """
    Renders an elegant, non-intrusive preview banner for the message being replied to.
    """
    if not reply_data:
        return ft.Container(visible=False, height=0)

    sender_name = reply_data.get("sender_name") or "User"
    snippet = reply_data.get("snippet") or "Quoted message"
    # An AI badge should strictly only appear when replying to Nu Owl / Nu Study AI, never a human peer
    is_ai = bool(
        str(reply_data.get("sender_id", "")).strip().lower() == "ai_assistant"
        or sender_name.strip().lower() in ("nu owl", "nu study ai", "ai assistant")
        or (reply_data.get("type") == "ai_response" and sender_name.strip().lower() in ("nu owl", "nu study ai", "ai assistant"))
    )

    accent_color = ft.Colors.PURPLE_400 if is_ai else palette.get("accent", ft.Colors.PRIMARY)

    return ft.Container(
        visible=True,
        bgcolor=ft.Colors.with_opacity(0.08, accent_color),
        border=ft.Border.only(
            top=ft.BorderSide(1, palette.get("border", ft.Colors.OUTLINE_VARIANT)),
            left=ft.BorderSide(3, accent_color),
        ),
        padding=ft.Padding.only(left=12, right=8, top=6, bottom=6),
        animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        content=ft.Row([
            ft.Icon(
                ft.Icons.AUTO_AWESOME_ROUNDED if is_ai else ft.Icons.REPLY_ROUNDED,
                size=18,
                color=accent_color,
            ),
            ft.Column([
                ft.Row([
                    ft.Text(
                        f"Replying to {sender_name}",
                        size=12,
                        weight=ft.FontWeight.BOLD,
                        color=accent_color,
                    ),
                    ft.Container(
                        visible=is_ai,
                        padding=ft.Padding.symmetric(horizontal=5, vertical=1),
                        border_radius=4,
                        bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.PURPLE_500),
                        content=ft.Text("AI", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.PURPLE_300),
                    ),
                ], spacing=6, tight=True),
                ft.Text(
                    snippet,
                    size=11,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    no_wrap=True,
                    color=palette.get("text_muted", ft.Colors.ON_SURFACE_VARIANT),
                ),
            ], spacing=2, expand=True, tight=True),
            ft.IconButton(
                icon=ft.Icons.CLOSE_ROUNDED,
                icon_size=16,
                icon_color=palette.get("text_muted", ft.Colors.ON_SURFACE_VARIANT),
                tooltip="Cancel reply",
                on_click=on_cancel,
            ),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
    )

