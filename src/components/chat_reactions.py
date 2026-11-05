"""
src/components/chat_reactions.py

Interactive Live Emoji Reaction Components for Nu Chat.
Provides the quick emoji reaction picker and real-time reaction pills beneath message bubbles.
Strictly follows Flet 0.86.5 conventions and theme tokens.
"""

from typing import Callable, Optional, Dict, List, Any
import flet as ft

POPULAR_EMOJIS = ["👍", "❤️", "🔥", "😂", "😮", "👏", "💡"]


def build_reaction_picker_row(
    on_emoji_selected: Callable[[str], None],
    palette: Dict[str, Any],
) -> ft.Container:
    """
    Renders a sleek, elevated emoji reaction bar for picking an emoji on a message bubble.
    """
    emoji_buttons = []
    for em in POPULAR_EMOJIS:
        def _make_handler(emoji_val=em):
            return lambda e: on_emoji_selected(emoji_val)

        emoji_buttons.append(
            ft.Container(
                content=ft.Text(em, size=18),
                padding=ft.Padding.symmetric(horizontal=6, vertical=4),
                border_radius=8,
                ink=True,
                tooltip=f"React with {em}",
                on_click=_make_handler(),
            )
        )

    return ft.Container(
        content=ft.Row(emoji_buttons, spacing=2, tight=True),
        bgcolor=palette.get("card_bg", ft.Colors.SURFACE),
        border=ft.Border.all(1, palette.get("border", ft.Colors.OUTLINE_VARIANT)),
        border_radius=18,
        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
        shadow=ft.BoxShadow(
            blur_radius=10,
            color=ft.Colors.with_opacity(0.18, ft.Colors.BLACK),
            offset=ft.Offset(0, 3),
        ),
    )


def build_reaction_pills_row(
    reactions: Optional[Dict[str, List[str]]],
    current_user_id: Optional[str],
    on_toggle_emoji: Callable[[str], None],
    palette: Dict[str, Any],
) -> ft.Container:
    """
    Renders the row of active reaction chips/pills attached beneath a message bubble.
    Each chip shows the emoji and voter count, highlighted if the current user reacted.
    """
    if not reactions or not isinstance(reactions, dict):
        return ft.Container(visible=False, height=0)

    pills = []
    current_uid_str = str(current_user_id or "").strip().lower()

    for emoji_char, voter_ids in reactions.items():
        if not voter_ids or not isinstance(voter_ids, list):
            continue

        count = len(voter_ids)
        if count == 0:
            continue

        has_user_reacted = any(str(v_id).strip().lower() == current_uid_str for v_id in voter_ids)

        def _make_toggle(em=emoji_char):
            return lambda e: on_toggle_emoji(em)

        chip_bg = (
            ft.Colors.with_opacity(0.15, palette.get("accent", ft.Colors.PRIMARY))
            if has_user_reacted
            else palette.get("card_bg", ft.Colors.SURFACE)
        )
        chip_border = (
            ft.Border.all(1.2, palette.get("accent", ft.Colors.PRIMARY))
            if has_user_reacted
            else ft.Border.all(1, palette.get("border", ft.Colors.OUTLINE_VARIANT))
        )
        text_color = (
            palette.get("accent", ft.Colors.PRIMARY)
            if has_user_reacted
            else palette.get("text", ft.Colors.ON_SURFACE)
        )

        pills.append(
            ft.Container(
                content=ft.Row([
                    ft.Text(emoji_char, size=13),
                    ft.Text(str(count), size=11, weight=ft.FontWeight.W_600, color=text_color),
                ], spacing=4, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                bgcolor=chip_bg,
                border=chip_border,
                border_radius=12,
                padding=ft.Padding.symmetric(horizontal=7, vertical=3),
                ink=True,
                tooltip=f"{count} {'reaction' if count == 1 else 'reactions'}",
                on_click=_make_toggle(),
            )
        )

    if not pills:
        return ft.Container(visible=False, height=0)

    return ft.Container(
        content=ft.Row(pills, spacing=4, wrap=True),
        margin=ft.Margin.only(top=3),
    )

