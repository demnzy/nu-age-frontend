"""
src/components/chat_message_actions.py

Nu-Age Themed Message Action Components.
Provides:
1. `build_themed_bubble_menu`: Configures a sleek, fully-themed PopupMenuButton
   adhering to Nu-Age theme tokens (soft rounded container, tinted icon squares,
   brand green primary accents, and active state indicators).
2. `open_message_actions_sheet`: Full responsive Nu-Age action sheet modal (for
   long-press and mobile view), featuring the 7-emoji quick reaction bar,
   message snippet preview, and rich action tiles.

Strictly adheres to Flet 0.86.5 conventions and zero hardcoded foreign colors.
"""

from typing import Callable, Dict, Any, Optional, List
import flet as ft
from src.utils.file_opener import safe_set_clipboard, show_page_snackbar
from src.components.chat_reactions import POPULAR_EMOJIS


def _build_action_item_content(
    icon: str,
    label: str,
    icon_color: str,
    palette: Dict[str, Any],
    is_active: bool = False,
    is_destructive: bool = False,
) -> ft.Container:
    """
    Renders a unified Nu-Age styled menu row with a tinted icon square,
    typography, and optional active checkmark badge.
    """
    t_color = (
        ft.Colors.RED_400
        if is_destructive
        else palette.get("text", ft.Colors.ON_SURFACE)
    )

    badge = None
    if is_active:
        badge = ft.Container(
            content=ft.Text(
                "Active",
                size=9,
                weight=ft.FontWeight.BOLD,
                color=palette.get("accent", ft.Colors.PRIMARY),
            ),
            bgcolor=ft.Colors.with_opacity(0.12, palette.get("accent", ft.Colors.PRIMARY)),
            border_radius=4,
            padding=ft.Padding.symmetric(horizontal=5, vertical=2),
        )

    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=6, vertical=4),
        border_radius=8,
        content=ft.Row([
            ft.Container(
                width=28,
                height=28,
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.12, icon_color),
                alignment=ft.Alignment.CENTER,
                content=ft.Icon(icon, size=15, color=icon_color),
            ),
            ft.Text(
                label,
                size=12.5,
                weight=ft.FontWeight.W_500,
                color=t_color,
                expand=True,
            ),
            badge if badge else ft.Container(width=0, height=0),
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
    )


def _build_emoji_item_content(
    emoji_char: str,
    label: str,
    palette: Dict[str, Any],
    is_active: bool = False,
) -> ft.Container:
    """
    Renders an emoji reaction menu row with active indicator.
    """
    active_color = palette.get("accent", ft.Colors.PRIMARY)
    text_color = (
        active_color if is_active else palette.get("text", ft.Colors.ON_SURFACE)
    )

    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=6, vertical=3),
        border_radius=8,
        content=ft.Row([
            ft.Container(
                width=28,
                height=28,
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.12, active_color) if is_active else palette.get("input_bg", ft.Colors.SURFACE_CONTAINER_HIGHEST),
                border=ft.Border.all(1.2, active_color) if is_active else None,
                alignment=ft.Alignment.CENTER,
                content=ft.Text(emoji_char, size=16),
            ),
            ft.Text(
                f"{label} (Remove)" if is_active else label,
                size=12.5,
                weight=ft.FontWeight.W_600 if is_active else ft.FontWeight.W_500,
                color=text_color,
                expand=True,
            ),
            ft.Icon(
                ft.Icons.CHECK_ROUNDED,
                size=14,
                color=active_color,
                visible=is_active,
            ) if is_active else ft.Container(width=0, height=0),
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
    )


def build_themed_bubble_menu(
    msg: dict,
    palette: Dict[str, Any],
    current_user_id: Optional[str],
    is_admin: bool,
    pinned_msg_target_id: List[Optional[str]],
    on_set_reply: Callable[[dict], None],
    on_send_reaction: Callable[[str, str], None],
    on_send_pin: Callable[[str], None],
    on_send_unpin: Callable[[str], None],
    on_send_delete: Callable[[str], None],
    on_copy_text: Callable[[], None],
    on_open_full_sheet: Optional[Callable[[], None]] = None,
    is_me: bool = False,
) -> ft.PopupMenuButton:
    """
    Builds a complete, Nu-Age themed PopupMenuButton for message bubbles.
    """
    msg_id_str = str(msg.get("id") or "")
    meta = msg.get("metadata_payload") or {}
    if isinstance(meta, str):
        try:
            import json
            meta = json.loads(meta)
        except Exception:
            meta = {}
    if not isinstance(meta, dict):
        meta = {}

    reactions_dict = meta.get("reactions") or {}
    if not isinstance(reactions_dict, dict):
        reactions_dict = {}

    my_uid_str = str(current_user_id or "").strip().lower()
    user_reacted_emojis = [
        em for em, u_ids in reactions_dict.items()
        if isinstance(u_ids, list) and any(str(u).strip().lower() == my_uid_str for u in u_ids)
    ]

    items = []

    # 1. Quick Reply
    items.append(
        ft.PopupMenuItem(
            content=_build_action_item_content(
                ft.Icons.REPLY_ROUNDED,
                "Reply",
                palette.get("accent", ft.Colors.PRIMARY),
                palette,
            ),
            on_click=lambda e, m=msg: on_set_reply(m),
        )
    )

    # 2. Popular Emoji Quick Reactions
    for em_sym, em_lbl in [("👍", "Like"), ("❤️", "Love"), ("🔥", "Fire")]:
        is_act = em_sym in user_reacted_emojis
        items.append(
            ft.PopupMenuItem(
                content=_build_emoji_item_content(em_sym, em_lbl, palette, is_active=is_act),
                on_click=lambda e, mid=msg_id_str, em=em_sym: on_send_reaction(mid, em),
            )
        )

    # If user has reacted with other emojis (e.g. from sheet/picker), offer removal
    for other_em in user_reacted_emojis:
        if other_em not in ("👍", "❤️", "🔥"):
            items.append(
                ft.PopupMenuItem(
                    content=_build_emoji_item_content(other_em, "Remove Reaction", palette, is_active=True),
                    on_click=lambda e, mid=msg_id_str, em=other_em: on_send_reaction(mid, em),
                )
            )

    # Divider
    items.append(
        ft.PopupMenuItem(
            content=ft.Divider(height=1, thickness=0.8, color=palette.get("border", ft.Colors.OUTLINE_VARIANT)),
            disabled=True,
        )
    )

    # 3. Pin / Unpin
    if is_admin:
        is_pinned = bool(meta.get("is_pinned")) or (pinned_msg_target_id[0] == msg_id_str)
        if is_pinned:
            items.append(
                ft.PopupMenuItem(
                    content=_build_action_item_content(
                        ft.Icons.PUSH_PIN_OUTLINED,
                        "Unpin Message",
                        ft.Colors.AMBER_400,
                        palette,
                        is_active=True,
                    ),
                    on_click=lambda e, mid=msg_id_str: on_send_unpin(mid),
                )
            )
        else:
            items.append(
                ft.PopupMenuItem(
                    content=_build_action_item_content(
                        ft.Icons.PUSH_PIN_ROUNDED,
                        "Pin Message",
                        palette.get("accent", ft.Colors.PRIMARY),
                        palette,
                    ),
                    on_click=lambda e, mid=msg_id_str: on_send_pin(mid),
                )
            )

    # 4. Copy Text
    items.append(
        ft.PopupMenuItem(
            content=_build_action_item_content(
                ft.Icons.CONTENT_COPY_ROUNDED,
                "Copy Text",
                palette.get("text_muted", ft.Colors.ON_SURFACE_VARIANT),
                palette,
            ),
            on_click=lambda e: on_copy_text(),
        )
    )

    # 5. More Actions / Full Reactions modal (optional)
    if on_open_full_sheet:
        items.append(
            ft.PopupMenuItem(
                content=_build_action_item_content(
                    ft.Icons.ADD_REACTION_OUTLINED,
                    "More Reactions...",
                    palette.get("accent", ft.Colors.PRIMARY),
                    palette,
                ),
                on_click=lambda e: on_open_full_sheet(),
            )
        )

    # 6. Delete for Everyone (Sender or Admin)
    sender_id_str = str((msg.get("sender") or {}).get("id") or msg.get("sender_id") or "").strip().lower()
    is_sender = (sender_id_str == my_uid_str) or is_me
    if is_sender or is_admin:
        items.append(
            ft.PopupMenuItem(
                content=_build_action_item_content(
                    ft.Icons.DELETE_OUTLINE_ROUNDED,
                    "Delete for Everyone",
                    ft.Colors.RED_400,
                    palette,
                    is_destructive=True,
                ),
                on_click=lambda e, mid=msg_id_str: on_send_delete(mid),
            )
        )

    return ft.PopupMenuButton(
        icon=ft.Icons.MORE_HORIZ_ROUNDED,
        icon_color=ft.Colors.WHITE54 if is_me else palette.get("text_muted", ft.Colors.ON_SURFACE_VARIANT),
        icon_size=15,
        tooltip="Message actions",
        bgcolor=palette.get("card_bg", ft.Colors.SURFACE),
        shape=ft.RoundedRectangleBorder(radius=14),
        elevation=12,
        shadow_color=ft.Colors.with_opacity(0.35, ft.Colors.BLACK),
        menu_padding=ft.Padding.symmetric(vertical=6, horizontal=4),
        items=items,
    )


def open_message_actions_sheet(
    page: ft.Page,
    msg: dict,
    palette: Dict[str, Any],
    current_user_id: Optional[str],
    is_admin: bool,
    on_set_reply: Callable[[dict], None],
    on_send_reaction: Callable[[str, str], None],
    on_send_pin: Callable[[str], None],
    on_send_unpin: Callable[[str], None],
    on_send_delete: Callable[[str], None],
    on_copy_text: Callable[[], None],
    pinned_msg_target_id: List[Optional[str]],
    is_me: bool = False,
    on_close_callback: Optional[Callable[[], None]] = None,
):
    """
    Opens an interactive, beautifully themed Nu-Age modal sheet for a message.
    Includes the 7-emoji quick reaction pill bar and rich action tiles.
    """
    msg_id_str = str(msg.get("id") or "")
    raw_content = str(msg.get("content") or "")
    meta = msg.get("metadata_payload") or {}
    if isinstance(meta, str):
        try:
            import json
            meta = json.loads(meta)
        except Exception:
            meta = {}
    if not isinstance(meta, dict):
        meta = {}

    sender_name = (msg.get("sender") or {}).get("name") or msg.get("sender_name") or ("You" if is_me else "User")
    sender_id_str = str((msg.get("sender") or {}).get("id") or msg.get("sender_id") or "").strip().lower()
    my_uid_str = str(current_user_id or "").strip().lower()
    is_sender = (sender_id_str == my_uid_str) or is_me
    is_pinned = bool(meta.get("is_pinned")) or (pinned_msg_target_id[0] == msg_id_str)

    reactions_dict = meta.get("reactions") or {}
    if not isinstance(reactions_dict, dict):
        reactions_dict = {}

    user_reacted_emojis = [
        em for em, u_ids in reactions_dict.items()
        if isinstance(u_ids, list) and any(str(u).strip().lower() == my_uid_str for u in u_ids)
    ]

    def _on_dismiss(e=None):
        if on_close_callback:
            try:
                on_close_callback()
            except Exception:
                pass

    dlg = ft.AlertDialog(
        modal=True,
        shape=ft.RoundedRectangleBorder(radius=18),
        bgcolor=palette.get("card_bg", ft.Colors.SURFACE),
        content_padding=ft.Padding.symmetric(horizontal=18, vertical=16),
        on_dismiss=_on_dismiss,
    )

    def _close(e=None):
        dlg.open = False
        page.update()
        _on_dismiss()

    # 1. Emoji Reaction Bar
    emoji_pills = []
    for em in POPULAR_EMOJIS:
        has_voted = em in user_reacted_emojis
        bg_col = (
            ft.Colors.with_opacity(0.20, palette.get("accent", ft.Colors.PRIMARY))
            if has_voted
            else palette.get("input_bg", ft.Colors.SURFACE_CONTAINER_HIGHEST)
        )
        b_col = (
            ft.Border.all(1.5, palette.get("accent", ft.Colors.PRIMARY))
            if has_voted
            else ft.Border.all(1, palette.get("border", ft.Colors.OUTLINE_VARIANT))
        )

        def _make_react_fn(char=em):
            def _fn(e):
                _close()
                on_send_reaction(msg_id_str, char)
            return _fn

        emoji_pills.append(
            ft.Container(
                content=ft.Text(em, size=19),
                bgcolor=bg_col,
                border=b_col,
                border_radius=12,
                padding=ft.Padding.symmetric(horizontal=8, vertical=6),
                ink=True,
                tooltip=f"React with {em}" if not has_voted else f"Remove {em}",
                on_click=_make_react_fn(),
            )
        )

    reaction_bar = ft.Container(
        padding=ft.Padding.symmetric(horizontal=4, vertical=6),
        border_radius=14,
        bgcolor=ft.Colors.with_opacity(0.06, palette.get("accent", ft.Colors.PRIMARY)),
        border=ft.Border.all(1, palette.get("border", ft.Colors.OUTLINE_VARIANT)),
        content=ft.Row(
            emoji_pills,
            spacing=6,
            alignment=ft.MainAxisAlignment.SPACE_EVENLY,
        ),
    )

    # 2. Snippet Preview
    snippet_box = ft.Container(
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        border_radius=10,
        bgcolor=ft.Colors.with_opacity(0.08, palette.get("text_muted", ft.Colors.ON_SURFACE_VARIANT)),
        border=ft.Border.only(left=ft.BorderSide(3, palette.get("accent", ft.Colors.PRIMARY))),
        content=ft.Column([
            ft.Row([
                ft.Text(sender_name, size=11, weight=ft.FontWeight.BOLD, color=palette.get("accent", ft.Colors.PRIMARY)),
                ft.Text(" • Message", size=10, color=palette.get("text_muted", ft.Colors.ON_SURFACE_VARIANT)),
            ], spacing=4),
            ft.Text(
                raw_content[:100] + ("..." if len(raw_content) > 100 else ""),
                size=12,
                color=palette.get("text", ft.Colors.ON_SURFACE),
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
        ], spacing=2, tight=True),
    )

    # 3. Action Tiles Helper
    def _action_tile(icon, title: str, subtitle: str, color, on_click_action, is_destructive: bool = False):
        def _act(e):
            _close()
            on_click_action()

        return ft.Container(
            ink=True,
            border_radius=10,
            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            on_click=_act,
            content=ft.Row([
                ft.Container(
                    width=36,
                    height=36,
                    border_radius=9,
                    bgcolor=ft.Colors.with_opacity(0.12, color),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(icon, color=color, size=18),
                ),
                ft.Column([
                    ft.Text(
                        title,
                        size=13,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.RED_400 if is_destructive else palette.get("text", ft.Colors.ON_SURFACE),
                    ),
                    ft.Text(
                        subtitle,
                        size=11,
                        color=palette.get("text_muted", ft.Colors.ON_SURFACE_VARIANT),
                    ),
                ], spacing=1, expand=True),
                ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, size=16, color=palette.get("text_muted", ft.Colors.ON_SURFACE_VARIANT)),
            ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

    action_tiles = [
        _action_tile(
            ft.Icons.REPLY_ROUNDED,
            "Reply to Message",
            "Quote this message directly in the composer",
            palette.get("accent", ft.Colors.PRIMARY),
            lambda: on_set_reply(msg),
        ),
        _action_tile(
            ft.Icons.CONTENT_COPY_ROUNDED,
            "Copy Text",
            "Copy message text to clipboard",
            palette.get("text_muted", ft.Colors.ON_SURFACE_VARIANT),
            on_copy_text,
        ),
    ]

    media_url = meta.get("media_url") or (raw_content if (raw_content.startswith("http") and any(raw_content.lower().split("?")[0].endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"])) else None)
    if media_url:
        def _copy_media_link():
            import asyncio
            asyncio.create_task(safe_set_clipboard(page, media_url))
            show_page_snackbar(page, "Attachment link copied to clipboard")

        def _open_media_external():
            import asyncio
            asyncio.create_task(page.launch_url(media_url))

        action_tiles.append(
            _action_tile(
                ft.Icons.OPEN_IN_NEW_ROUNDED,
                "Open Attachment",
                "Open file in browser or system viewer",
                palette.get("accent", ft.Colors.PRIMARY),
                _open_media_external,
            )
        )
        action_tiles.append(
            _action_tile(
                ft.Icons.LINK_ROUNDED,
                "Copy Attachment Link",
                "Copy direct CDN link to clipboard",
                palette.get("text_muted", ft.Colors.ON_SURFACE_VARIANT),
                _copy_media_link,
            )
        )

    if is_admin:
        if is_pinned:
            action_tiles.append(
                _action_tile(
                    ft.Icons.PUSH_PIN_OUTLINED,
                    "Unpin Message",
                    "Remove this message from room pinned notice",
                    ft.Colors.AMBER_400,
                    lambda: on_send_unpin(msg_id_str),
                )
            )
        else:
            action_tiles.append(
                _action_tile(
                    ft.Icons.PUSH_PIN_ROUNDED,
                    "Pin Message",
                    "Pin to the top header for all participants",
                    palette.get("accent", ft.Colors.PRIMARY),
                    lambda: on_send_pin(msg_id_str),
                )
            )

    if is_sender or is_admin:
        action_tiles.append(
            _action_tile(
                ft.Icons.DELETE_OUTLINE_ROUNDED,
                "Delete for Everyone",
                "Permanently remove this message from the channel",
                ft.Colors.RED_400,
                lambda: on_send_delete(msg_id_str),
                is_destructive=True,
            )
        )

    page_w = page.width or 800
    sheet_width = min(420, int(page_w * 0.90))

    dlg.content = ft.Container(
        width=sheet_width,
        content=ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.TUNE_ROUNDED, color=palette.get("accent", ft.Colors.PRIMARY), size=18),
                ft.Text("Message Actions", size=15, weight=ft.FontWeight.BOLD, color=palette.get("text", ft.Colors.ON_SURFACE)),
                ft.Container(expand=True),
                ft.IconButton(ft.Icons.CLOSE_ROUNDED, icon_size=16, icon_color=palette.get("text_muted", ft.Colors.ON_SURFACE_VARIANT), on_click=_close),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            reaction_bar,
            snippet_box,
            ft.Divider(height=1, thickness=0.8, color=palette.get("border", ft.Colors.OUTLINE_VARIANT)),
            ft.Column(action_tiles, spacing=4, tight=True),
        ], spacing=10, tight=True),
    )

    if hasattr(page, "overlay"):
        if dlg not in page.overlay:
            page.overlay.append(dlg)
    dlg.open = True
    page.update()

