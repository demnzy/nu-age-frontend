"""
src/components/chat_commands.py

Expandable Chat Slash Commands Engine for Nu Chat.
Provides an extensible registry of commands (/duel, /duo, /help),
autocomplete suggestions above the input composer, and action dispatchers.
"""

import re
import asyncio
from dataclasses import dataclass
from typing import Callable, Optional, List, Dict, Any
import flet as ft

from src.utils.file_opener import show_page_snackbar
from src.requests.study_partners import get_active_partnership, invite_study_partner


@dataclass
class ChatSlashCommand:
    name: str               # e.g. "duel"
    syntax: str             # e.g. "/duel"
    title: str              # e.g. "Quickfire Duel"
    description: str        # e.g. "Challenge duo buddy to a duel (or send duo request)"
    badge: str              # e.g. "15-Q Duel"
    icon: str               # ft.Icons.FLASH_ON_ROUNDED
    color: str              # ft.Colors.ORANGE_500


# Centralized, expandable registry of all supported chat commands
COMMAND_REGISTRY: List[ChatSlashCommand] = [
    ChatSlashCommand(
        name="ai",
        syntax="/ai <question>",
        title="Ask Nu Study AI",
        description="Ask an academic question or clear doubts directly in chat",
        badge="✨ AI Assistant",
        icon=ft.Icons.AUTO_AWESOME_ROUNDED,
        color=ft.Colors.PURPLE_500,
    ),
    ChatSlashCommand(
        name="poll",
        syntax="/poll",
        title="Create In-Chat Poll",
        description="Launch an interactive single or multi-choice poll",
        badge="📊 Poll",
        icon=ft.Icons.POLL_ROUNDED,
        color=ft.Colors.CYAN_400,
    ),
    ChatSlashCommand(
        name="code",
        syntax="/code",
        title="Insert Code Snippet",
        description="Insert syntax-highlighted code block",
        badge="💻 Code",
        icon=ft.Icons.CODE_ROUNDED,
        color=ft.Colors.AMBER_400,
    ),
    ChatSlashCommand(
        name="duel",
        syntax="/duel",
        title="Quickfire Duel",
        description="Challenge duo partner to a 15-Q duel (or send duo request)",
        badge="⚔️ Duel",
        icon=ft.Icons.FLASH_ON_ROUNDED,
        color=ft.Colors.ORANGE_500,
    ),
    ChatSlashCommand(
        name="duo",
        syntax="/duo",
        title="Duo Buddy Invite",
        description="Send a Duo Buddy accountability partnership request",
        badge="🤝 Duo",
        icon=ft.Icons.PEOPLE_ROUNDED,
        color=ft.Colors.GREEN_600,
    ),
    ChatSlashCommand(
        name="help",
        syntax="/help",
        title="Chat Commands Guide",
        description="View available slash commands, shortcuts and formatting tips",
        badge="💡 Info",
        icon=ft.Icons.HELP_OUTLINE_ROUNDED,
        color=ft.Colors.BLUE_500,
    ),
]


def get_matching_commands(query: str) -> List[ChatSlashCommand]:
    """
    Returns registered slash commands matching the query (case-insensitive).
    query can be empty (just '/'), or partial like 'd', 'due', 'duo'.
    """
    q = (query or "").lstrip("/").strip().lower()
    if not q:
        return list(COMMAND_REGISTRY)
    return [
        cmd for cmd in COMMAND_REGISTRY
        if q in cmd.name.lower() or q in cmd.title.lower() or q in cmd.description.lower()
    ]


def build_command_autocomplete_tile(
    cmd: ChatSlashCommand,
    palette: dict,
    on_click_callback: Callable,
) -> ft.Container:
    """
    Renders an elegant, theme-compliant command suggestion tile for the autocomplete card.
    """
    return ft.Container(
        ink=True,
        border_radius=8,
        padding=ft.Padding.symmetric(horizontal=10, vertical=7),
        on_click=on_click_callback,
        content=ft.Row([
            ft.Container(
                width=28,
                height=28,
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.14, cmd.color),
                alignment=ft.Alignment.CENTER,
                content=ft.Icon(cmd.icon, size=16, color=cmd.color),
            ),
            ft.Column([
                ft.Row([
                    ft.Text(cmd.syntax, size=13, weight=ft.FontWeight.BOLD, color=palette.get("text", ft.Colors.ON_SURFACE)),
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                        border_radius=4,
                        bgcolor=ft.Colors.with_opacity(0.12, cmd.color),
                        content=ft.Text(cmd.badge, size=9.5, weight=ft.FontWeight.W_700, color=cmd.color),
                    ),
                ], spacing=6, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Text(
                    cmd.description,
                    size=11,
                    color=palette.get("text_muted", ft.Colors.ON_SURFACE_VARIANT),
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS
                ),
            ], spacing=2, tight=True, expand=True),
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
    )


async def execute_slash_command(
    page: ft.Page,
    token: str,
    raw_text: str,
    active_chat_info: dict,
    active_channel_members: list,
    all_users_cache: list,
    on_post_message: Optional[Callable[[str], Any]] = None,
) -> bool:
    """
    Parses and executes a slash command. Returns True if handled, False otherwise.
    """
    text = (raw_text or "").strip()
    if not text.startswith("/"):
        return False

    parts = text.split(maxsplit=1)
    cmd_name = parts[0].lstrip("/").lower()
    arg_str = parts[1].strip() if len(parts) > 1 else ""

    chat_type = active_chat_info.get("type", "direct")
    is_dm = (chat_type == "direct")

    # Helper to resolve target user in current chat or by @mention
    def _resolve_target_user() -> tuple[Optional[str], Optional[str]]:
        """Returns (target_user_id, target_name)"""
        if is_dm:
            t_id = active_chat_info.get("other_user_id")
            t_name = active_chat_info.get("name") or "User"
            return (str(t_id) if t_id else None, t_name)

        if arg_str:
            clean_arg = arg_str.lstrip("@").strip().lower()
            # 1. Search channel members
            for m in active_channel_members:
                m_uid = str(m.get("id") or m.get("user_id", "")).strip()
                uname = (m.get("username") or "").strip().lower()
                fname = (m.get("first_name") or "").strip().lower()
                m_name = (m.get("name") or m.get("full_name") or uname or "User").strip()
                if clean_arg in (uname, fname, m_name.lower()) or (uname and clean_arg in uname):
                    return (m_uid, m_name)
            # 2. Search all users cache
            for u in all_users_cache:
                u_id = str(u.get("id") or u.get("user_id", "")).strip()
                uname = (u.get("username") or "").strip().lower()
                u_name = (u.get("name") or u.get("full_name") or uname or "User").strip()
                if clean_arg in (uname, u_name.lower()):
                    return (u_id, u_name)

        return (None, None)

    def _find_active_partnership(p_data: dict, t_uid: str) -> tuple[Optional[dict], Optional[dict]]:
        """
        Returns (matched_partnership_dict, matched_partner_dict) if target_uid has an active partnership.
        Supports both single 'partnership' and multiple 'partnerships' structures.
        """
        if not p_data or not p_data.get("has_partnership"):
            return None, None

        target_clean = str(t_uid or "").strip().lower()
        if not target_clean:
            return None, None

        # Check in partnerships list
        plist = p_data.get("partnerships") or []
        if not plist and p_data.get("partnership"):
            plist = [p_data["partnership"]]

        for p in plist:
            if not isinstance(p, dict):
                continue
            p_obj = p.get("partner") or {}
            p_uid = str(p_obj.get("id") or p.get("partner_id") or "").strip().lower()
            if p_uid == target_clean:
                return p, p_obj

        # Fallback check top-level partnership
        single_p = p_data.get("partnership")
        if isinstance(single_p, dict):
            p_obj = single_p.get("partner") or {}
            p_uid = str(p_obj.get("id") or single_p.get("partner_id") or "").strip().lower()
            if p_uid == target_clean:
                return single_p, p_obj

        return None, None

    async def _emit_system_msg(content: str, is_system: bool = True, local_only: bool = False):
        if not on_post_message:
            return
        try:
            if asyncio.iscoroutinefunction(on_post_message):
                try:
                    await on_post_message(content, is_system=is_system, local_only=local_only)
                except TypeError:
                    await on_post_message(content)
            else:
                try:
                    on_post_message(content, is_system=is_system, local_only=local_only)
                except TypeError:
                    on_post_message(content)
        except Exception as ex:
            print(f"[ChatCommands] emit error: {ex}")

    # ─────────────────────────────────────────────────────────────────────────
    # 0. /ai COMMAND — Pass through to WebSocket for academic synthesis
    # ─────────────────────────────────────────────────────────────────────────
    if cmd_name == "ai":
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # 1. /duel COMMAND
    # ─────────────────────────────────────────────────────────────────────────
    if cmd_name == "duel":
        target_uid, target_name = _resolve_target_user()

        if not target_uid:
            err_msg = "Specify a group member to duel: /duel @username" if not is_dm else "Could not identify recipient in this chat."
            show_page_snackbar(page, err_msg)
            await _emit_system_msg(f"⚠️ {err_msg}", is_system=True, local_only=True)
            return True

        # Check active partnership status
        partnership_data = await get_active_partnership(token)
        matched_p, matched_partner = _find_active_partnership(partnership_data, target_uid)
        is_my_duo_buddy = bool(matched_p is not None)

        if is_my_duo_buddy:
            # Recipient is our Duo Buddy -> Open duel creation flow directly
            p_id_str = str(matched_p.get("id") or "")
            from src.components.partner_challenge_modal import show_create_duel_dialog
            show_page_snackbar(page, f"⚔️ Preparing Quickfire Duel against {target_name}...")
            await _emit_system_msg(f"⚔️ Quickfire Duel initiated against {target_name}!", is_system=True, local_only=False)
            show_create_duel_dialog(
                page=page,
                token=token,
                partnership_id=p_id_str,
                partner=matched_partner or {},
                available_materials=[],
                on_duel_created=None,
            )
        else:
            # Recipient is NOT our Duo Buddy -> Send partnership invitation
            res = await invite_study_partner(token, target_user_id=target_uid)
            if res.get("error"):
                show_page_snackbar(page, f"Duo Notice: {res.get('error')}")
                await _emit_system_msg(f"ℹ️ Duo Notice for {target_name}: {res.get('error')}", is_system=True, local_only=True)
            else:
                show_page_snackbar(page, f"Sent Duo Buddy request to {target_name}! Once accepted, you can duel each other.")
                await _emit_system_msg(
                    f"⚔️ Sent Duo Buddy request to {target_name}! Once accepted in Network/Study, Quickfire Duels will unlock.",
                    is_system=True,
                    local_only=False,
                )
        return True

    # ─────────────────────────────────────────────────────────────────────────
    # 2. /duo COMMAND
    # ─────────────────────────────────────────────────────────────────────────
    if cmd_name == "duo":
        target_uid, target_name = _resolve_target_user()

        if not target_uid:
            err_msg = "Specify a group member for duo invite: /duo @username" if not is_dm else "Could not identify recipient in this chat."
            show_page_snackbar(page, err_msg)
            await _emit_system_msg(f"⚠️ {err_msg}", is_system=True, local_only=True)
            return True

        # Check if already active duo buddies
        partnership_data = await get_active_partnership(token)
        matched_p, matched_partner = _find_active_partnership(partnership_data, target_uid)

        if matched_p is not None:
            show_page_snackbar(page, f"You and {target_name} are already Duo Buddies!")
            await _emit_system_msg(f"🤝 You and {target_name} are already active Duo Buddies!", is_system=True, local_only=True)
            return True

        res = await invite_study_partner(token, target_user_id=target_uid)
        if res.get("error"):
            show_page_snackbar(page, f"Duo Notice: {res.get('error')}")
            await _emit_system_msg(f"ℹ️ Duo Notice for {target_name}: {res.get('error')}", is_system=True, local_only=True)
        else:
            show_page_snackbar(page, f"Sent Duo Buddy partnership request to {target_name}!")
            await _emit_system_msg(
                f"🤝 Sent a Duo Buddy accountability request to {target_name}!",
                is_system=True,
                local_only=False,
            )
        return True

    # ─────────────────────────────────────────────────────────────────────────
    # 3. /help COMMAND
    # ─────────────────────────────────────────────────────────────────────────
    if cmd_name == "help":
        help_text = (
            "💡 Available Nu Chat Commands:\n"
            "• /ai <question>: Ask Nu Study AI doubts & questions\n"
            "• /duel [@user]: 15-Q Quickfire Duel with Duo Buddy\n"
            "• /duo [@user]: Send Duo Buddy partnership invite\n"
            "• /help: Show command guide"
        )
        show_page_snackbar(page, help_text)
        await _emit_system_msg(help_text, is_system=True, local_only=True)
        return True

    # Unrecognized slash command
    unk_msg = f"⚠️ Unknown command: /{cmd_name}. Type /help for available commands."
    show_page_snackbar(page, unk_msg)
    await _emit_system_msg(unk_msg, is_system=True, local_only=True)
    return True
