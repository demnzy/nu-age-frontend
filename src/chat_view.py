import flet as ft
from datetime import datetime, timezone
import asyncio
import json
import re
from typing import Optional, List, Dict, Any

# ==========================================
# BACKEND & UTILITY IMPORTS
# ==========================================
from src.components.bottom_appbar import get_bottom_appbar
from src.requests.auth import get_current_user_request
from src.requests.chats import (
    get_user_channels,
    get_channel_messages,
    create_group_channel,
    start_direct_message,
    get_all_users,
    ChatWebSocketClient,
    add_group_members,
    get_group_members,
    delete_chat_channel,
    leave_group_channel
)
from src.local_db import (
    get_cached_chat_channels,
    upsert_chat_channels,
    get_cached_messages,
    upsert_chat_messages
)
from src.components.notifications_drawer import NotificationManager
from src.services.notification_service import sync_learner_notifications
from src.utils.file_opener import show_page_snackbar
from src.components.shimmer_skeletons import shimmer_box, collect_shimmer_boxes

def build_whatsapp_spans(text: str, default_color: str, palette_map: dict, on_mention_click=None, is_me: bool = False):
    if not text:
        return [ft.TextSpan("")]

    pattern = re.compile(
        r'(https?://[^\s]+)|'
        r'(@[a-zA-Z0-9_.-]+)|'
        r'(\*[^\*\n]+\*)|'
        r'(_[^_\n]+_)|'
        r'(~[^~\n]+~)|'
        r'(`[^`\n]+`)'
    )

    spans = []
    last_idx = 0
    for match in pattern.finditer(text):
        start, end = match.span()
        if start > last_idx:
            spans.append(ft.TextSpan(text[last_idx:start], style=ft.TextStyle(color=default_color, size=14)))

        m_str = match.group(0)
        if match.group(1):  # URL
            link_col = palette_map.get("bubble_out_link", "#C8E6C9") if is_me else palette_map.get("accent", "#4CAF50")
            spans.append(
                ft.TextSpan(
                    m_str,
                    style=ft.TextStyle(
                        color=link_col,
                        decoration=ft.TextDecoration.UNDERLINE,
                        size=14
                    ),
                    url=m_str
                )
            )
        elif match.group(2):  # Mention (@username, @admin, or @all)
            uname = m_str
            clean_tag = uname.lower()
            is_admin_tag = (clean_tag == "@admin")
            is_all_tag = (clean_tag == "@all")
            if is_all_tag:
                mention_color = ft.Colors.AMBER_300 if is_me else ft.Colors.AMBER_400
            elif is_admin_tag:
                mention_color = ft.Colors.AMBER_300 if is_me else ft.Colors.AMBER_500
            else:
                mention_color = palette_map.get("bubble_out_link", "#C8E6C9") if is_me else palette_map.get("accent", "#4CAF50")
            spans.append(
                ft.TextSpan(
                    uname,
                    style=ft.TextStyle(
                        color=mention_color,
                        weight=ft.FontWeight.BOLD,
                        size=14
                    ),
                    on_click=lambda e, u=uname: on_mention_click(u) if on_mention_click else None
                )
            )
        elif match.group(3):  # Bold
            inner = m_str[1:-1]
            spans.append(
                ft.TextSpan(
                    inner,
                    style=ft.TextStyle(
                        color=default_color,
                        weight=ft.FontWeight.BOLD,
                        size=14
                    )
                )
            )
        elif match.group(4):  # Italic
            inner = m_str[1:-1]
            spans.append(
                ft.TextSpan(
                    inner,
                    style=ft.TextStyle(
                        color=default_color,
                        italic=True,
                        size=14
                    )
                )
            )
        elif match.group(5):  # Strikethrough
            inner = m_str[1:-1]
            spans.append(
                ft.TextSpan(
                    inner,
                    style=ft.TextStyle(
                        color=default_color,
                        decoration=ft.TextDecoration.LINE_THROUGH,
                        size=14
                    )
                )
            )
        elif match.group(6):  # Inline Code
            inner = m_str[1:-1]
            code_col = palette_map.get("bubble_out_link", "#C8E6C9") if is_me else palette_map.get("accent", "#4CAF50")
            spans.append(
                ft.TextSpan(
                    inner,
                    style=ft.TextStyle(
                        color=code_col,
                        font_family="monospace",
                        size=13
                    )
                )
            )
        last_idx = end

    if last_idx < len(text):
        spans.append(ft.TextSpan(text[last_idx:], style=ft.TextStyle(color=default_color, size=14)))

    return spans


async def chat_view(
    page: ft.Page,
    target_dm_user_id: Optional[str] = None,
    target_channel_id: Optional[str] = None
) -> ft.View:
    """
    Modern, WhatsApp/Telegram-grade messaging suite for Nu-Age.
    Features:
      - Full dark/light mode palette harmonization (zero illegible white-on-white text).
      - Clustered message bubbles (grouped by sender and time window).
      - Auto-expanding multiline composer (1-5 lines) with Shift+Enter support.
      - In-chat Interactive Polls (live voting & real-time percentage broadcasts).
      - Formatted Code Block rendering with 1-click copy action.
      - Message delivery telemetry & copy-to-clipboard interactions.
      - Real-time read receipts & presence synchronization.
      - Deep linking from user profiles and network directory (?dm=<id>).
    """

    # ==========================================
    # 1. THEME & PALETTE ENGINE
    # ==========================================
    is_dark = page.theme_mode == ft.ThemeMode.DARK if hasattr(page, "theme_mode") else True

    # Mode-cognizant design strictly aligned with Nu-Age DARK_THEME / LIGHT_THEME in main.py
    if is_dark:
        primary = "#4CAF50"          # Official Nu-Age dark primary green (main.py)
        secondary = "#37BF14"        # Official Nu-Age vibrant accent green (main.py)
        surface = "#1E1E1E"          # Nu-Age dark surface
        surface_variant = "#262626"  # Nu-Age dark surface variant / inputs
        card_bg = "#1E1E1E"          # Nu-Age dark card
        border = "#2C2C2C"           # Nu-Age dark outline (main.py)
        border_subtle = "#222222"
        text = "#E8E8E8"             # Nu-Age dark text (soft white - main.py)
        text_muted = "#9E9E9E"       # Nu-Age muted text
        text_subtle = "#757575"
        chat_wall = "#121212"        # Nu-Age dark page background (#121212)
        bubble_out_bg = "#2E7D32"    # Nu-Age dark outgoing bubble (rich forest green)
        active_chat_bg = "#262626"   # WhatsApp-style sleek neutral active chat selection
    else:
        primary = "#035800"          # Official Nu-Age light primary green (main.py)
        secondary = "#37BF14"        # Official Nu-Age vibrant accent green (main.py)
        surface = "#FFFFFF"          # Nu-Age light surface (crisp white)
        surface_variant = "#F5F5F5"  # Nu-Age light surface variant / inputs
        card_bg = "#FFFFFF"          # Nu-Age light card
        border = "#E0E0E0"           # Nu-Age light outline (main.py)
        border_subtle = "#EEEEEE"
        text = "#1A1A1A"             # Nu-Age light text (main.py)
        text_muted = "#666666"       # Nu-Age light muted text
        text_subtle = "#9E9E9E"
        chat_wall = "#FAFAFA"        # Nu-Age light page background (#FAFAFA)
        bubble_out_bg = "#035800"    # Nu-Age light outgoing bubble (flagship primary green)
        active_chat_bg = "#F0F2F5"   # WhatsApp-style sleek neutral active chat selection

    palette = {
        "bg": chat_wall,
        "surface": surface,
        "surface_variant": surface_variant,
        "card_bg": card_bg,
        "border": border,
        "border_subtle": border_subtle,
        "accent": primary,
        "accent_glow": primary if not is_dark else "#388E3C",
        "secondary": secondary,
        "text": text,
        "text_muted": text_muted,
        "text_subtle": text_subtle,
        # Chat-specific surfaces:
        "chat_wall": chat_wall,
        "list_bg": surface,
        "header_bg": surface,
        "input_bar_bg": surface,
        "input_bg": surface_variant,
        "active_chat_bg": active_chat_bg,
        "bubble_in_bg": "#222222" if is_dark else "#FFFFFF",
        "bubble_in_border": border,
        "bubble_in_text": text,
        "bubble_in_ts": text_muted,
        "bubble_out_bg": bubble_out_bg,
        "bubble_out_text": "#FFFFFF",
        "bubble_out_ts": "rgba(255,255,255,0.75)",
        "bubble_out_link": "#C8E6C9",
        "pill_bg": surface_variant if is_dark else "#E6FAE5",
        "pill_text": text_muted if is_dark else primary,
        "system_bg": surface_variant if is_dark else "#F5F5F5",
        "system_text": text_muted,
        "online_dot": secondary,
        "unread_badge": primary,
        "bar_other": text_subtle,
        "code_bg": "#181818" if is_dark else "#1E1E1E",
        "code_border": "#2C2C2C" if is_dark else "#333333",
        "code_text": "#E8E8E8",
    }

    token = await page.shared_preferences.get("auth_token") or "dummy_token"

    # State variables
    DESKTOP_BREAKPOINT = 800
    current_chat_id = [None]
    active_chat_info = [{}]
    active_channel_members = []
    active_channel_admin_id = [None]
    active_channel_role = [None]
    is_desktop = [page.width >= DESKTOP_BREAKPOINT if hasattr(page, "width") and page.width else False]
    ws_client_ref = [None]
    channels_list = []
    is_loading_channels = [True]
    shimmer_loop_running = [False]
    all_users_cache = []
    fab_open = [False]
    search_query = [""]
    seen_msg_ids = set()
    chat_load_lock = [False]
    last_typing_time = [0]
    typing_tokens = {}

    cached_uid = await page.shared_preferences.get("user_id")
    current_user_id = [str(cached_uid).strip().lower() if cached_uid else "unknown_user_id"]
    current_user_handles = set()
    selected_mention_map = {}

    async def _load_users_if_needed():
        nonlocal all_users_cache
        if not all_users_cache:
            try:
                res = await get_all_users(token)
                if isinstance(res, list):
                    all_users_cache = res
            except Exception:
                pass

    autocomplete_list = ft.ListView(spacing=2)
    autocomplete_card = ft.Container(
        visible=False,
        bgcolor=palette["surface"],
        border=ft.Border.all(1, palette["border"]),
        border_radius=12,
        height=180,
        margin=ft.Margin(left=12, right=12, bottom=4, top=4),
        padding=ft.Padding.symmetric(horizontal=6, vertical=4),
        shadow=ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.12, ft.Colors.BLACK), offset=ft.Offset(0, -2)),
        content=autocomplete_list
    )

    # ==========================================
    # 2. PANELS & STRUCTURAL CONTAINERS
    # ==========================================
    chat_list_panel = ft.Container(
        expand=1,
        border=ft.Border.only(right=ft.BorderSide(1, palette["border"])),
        bgcolor=palette["list_bg"],
    )
    active_chat_panel = ft.Container(expand=2, bgcolor=palette["chat_wall"])
    active_chat_header = ft.Row(spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    messages_listview = ft.ListView(
        expand=True,
        spacing=4,
        auto_scroll=False,
        padding=ft.Padding.symmetric(horizontal=8 if not is_desktop[0] else 12, vertical=8 if not is_desktop[0] else 10)
    )

    def _scroll_to_bottom(animate: bool = False):
        try:
            page.run_task(messages_listview.scroll_to, offset=-1, duration=200 if animate else 0)
        except Exception:
            pass

    # ==========================================
    # 3. DATE & TIME FORMATTERS
    # ==========================================
    def format_message_time(iso_string: str) -> str:
        if not iso_string:
            return ""
        try:
            dt = datetime.fromisoformat(str(iso_string).replace("Z", "+00:00"))
            return dt.strftime("%I:%M %p").lstrip("0")
        except Exception:
            return ""

    def get_day_label(iso_string: str) -> str:
        if not iso_string:
            return ""
        try:
            dt = datetime.fromisoformat(str(iso_string).replace("Z", "+00:00"))
            now = datetime.now(dt.tzinfo)
            diff = (now.date() - dt.date()).days
            if diff == 0:
                return "Today"
            elif diff == 1:
                return "Yesterday"
            elif diff < 7:
                return dt.strftime("%A")
            else:
                return dt.strftime("%B %d, %Y")
        except Exception:
            return ""

    def parse_iso_timestamp(iso_string: str) -> float:
        if not iso_string:
            return 0.0
        try:
            dt = datetime.fromisoformat(str(iso_string).replace("Z", "+00:00"))
            return dt.timestamp()
        except Exception:
            return 0.0

    # ==========================================
    # 4. ACTION CONTROLLERS & SENDING
    # ==========================================
    send_btn_icon = ft.Icon(ft.Icons.SEND_ROUNDED, color=ft.Colors.WHITE, size=18)
    send_btn_container = ft.Container(
        width=42,
        height=42,
        bgcolor=palette["accent_glow"],
        border_radius=21,
        alignment=ft.Alignment.CENTER,
        content=send_btn_icon,
        ink=True,
        tooltip="Send Message"
    )

    async def send_text_message(e=None):
        text = (msg_input.value or "").strip()
        if not text or not current_chat_id[0]:
            return
        if not ws_client_ref[0]:
            show_page_snackbar(page, ft.SnackBar(content=ft.Text("Connecting to chat server, please wait..."), duration=2000))
            return

        autocomplete_card.visible = False
        msg_input.value = ""
        _update_send_btn_state()
        page.update()

        # Parse mentions (@username / @admin)
        mentions = re.findall(r'@([a-zA-Z0-9_.-]+)', text)
        extra_meta = {}
        if mentions:
            extra_meta["mentions"] = mentions
            mention_ids = []
            candidates = active_channel_members if active_channel_members else all_users_cache
            for m in mentions:
                m_clean = m.lower()
                if m_clean in selected_mention_map:
                    mention_ids.append(selected_mention_map[m_clean])
                else:
                    for u in candidates:
                        uid_cand = str(u.get("id") or u.get("user_id", "")).strip().lower()
                        uname = (u.get("username") or "").strip().lower()
                        fname = (u.get("first_name") or "").strip().lower()
                        lname = (u.get("last_name") or "").strip().lower()
                        name_cand = (u.get("name") or u.get("full_name") or "").strip().lower()
                        name_cand_under = name_cand.replace(" ", "_")
                        if m_clean in (uname, fname, name_cand, name_cand_under) or (uname and m_clean in uname) or (fname and m_clean in fname):
                            mention_ids.append(uid_cand)
                            break
            if mention_ids:
                extra_meta["mention_ids"] = list(set(mention_ids))
            selected_mention_map.clear()

        # Fire message dispatch over WebSocket
        if extra_meta:
            page.run_task(ws_client_ref[0].send_message, current_chat_id[0], text, "text", metadata_payload=extra_meta)
        else:
            page.run_task(ws_client_ref[0].send_message, current_chat_id[0], text, "text")

    def _update_send_btn_state():
        has_text = bool(msg_input.value and msg_input.value.strip())
        send_btn_container.bgcolor = palette["accent_glow"] if has_text else palette["surface_variant"]
        send_btn_icon.color = ft.Colors.WHITE if has_text else palette["text_muted"]

    def on_input_change(e):
        _update_send_btn_state()
        now = datetime.now().timestamp()
        if now - last_typing_time[0] > 2.5:
            if ws_client_ref[0] and current_chat_id[0]:
                page.run_task(ws_client_ref[0].send_message, current_chat_id[0], "typing", "typing")
            last_typing_time[0] = now

        # Tagging is ONLY usable in group chats (disabled in direct messages)
        active_type = active_chat_info[0].get("type", "direct")
        if active_type == "direct":
            if autocomplete_card.visible:
                autocomplete_card.visible = False
                page.update()
            return

        val = msg_input.value or ""
        match = re.search(r'(@)([a-zA-Z0-9_.-]*)$', val)
        if match:
            query = match.group(2).lower()
            autocomplete_list.controls.clear()

            my_uid = str(current_user_id[0]).strip().lower()
            admin_id_val = str(active_channel_admin_id[0]).strip().lower() if active_channel_admin_id[0] else ""
            user_session_data = page.session.store.get("current_user") or {} if hasattr(page, "session") and hasattr(page.session, "store") else {}
            platform_role = str(user_session_data.get("role", "")).upper()
            is_group_admin = (
                my_uid == admin_id_val or
                active_channel_role[0] == "admin" or
                platform_role in ("ADMIN", "OWNER", "SUPERADMIN")
            )

            # 1. Specialized @all tag (Admins Only)
            if is_group_admin and ("all".startswith(query) or query in "all"):
                def _select_all(ev):
                    msg_input.value = re.sub(r'@[a-zA-Z0-9_.-]*$', '@all ', msg_input.value or '')
                    autocomplete_card.visible = False
                    _update_send_btn_state()
                    page.update()

                all_tile = ft.Container(
                    ink=True,
                    border_radius=8,
                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                    on_click=_select_all,
                    content=ft.Row([
                        ft.Container(
                            width=24,
                            height=24,
                            border_radius=12,
                            bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.AMBER_500),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(ft.Icons.CAMPAIGN_ROUNDED, size=15, color=ft.Colors.AMBER_500)
                        ),
                        ft.Text("@all", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_500),
                        ft.Text("Notify entire group", size=11, color=palette["text_muted"]),
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=5, vertical=1.5),
                            border_radius=4,
                            bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.AMBER_500),
                            content=ft.Text("Admin Only", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_500)
                        )
                    ], spacing=8, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER)
                )
                autocomplete_list.controls.append(all_tile)

            # 2. Specialized @admin tag (Course Instructor / Group Admin)
            if "admin".startswith(query) or query in "admin":
                def _select_admin(ev):
                    msg_input.value = re.sub(r'@[a-zA-Z0-9_.-]*$', '@admin ', msg_input.value or '')
                    autocomplete_card.visible = False
                    _update_send_btn_state()
                    page.update()

                admin_tile = ft.Container(
                    ink=True,
                    border_radius=8,
                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                    on_click=_select_admin,
                    content=ft.Row([
                        ft.Container(
                            width=24,
                            height=24,
                            border_radius=12,
                            bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.AMBER_500),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(ft.Icons.WORKSPACE_PREMIUM_ROUNDED, size=15, color=ft.Colors.AMBER_500)
                        ),
                        ft.Text("@admin", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_500),
                        ft.Text("Group Admin / Instructor", size=11, color=palette["text_muted"])
                    ], spacing=8, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER)
                )
                autocomplete_list.controls.append(admin_tile)

            # 2. Group members alone
            candidate_members = active_channel_members if active_channel_members else all_users_cache
            my_uid = str(current_user_id[0]).strip().lower()
            admin_id_val = str(active_channel_admin_id[0]).strip().lower() if active_channel_admin_id[0] else ""

            matches = [
                m for m in candidate_members
                if str(m.get("id") or m.get("user_id", "")).strip().lower() != my_uid and (
                    query in (m.get("username") or "").lower() or
                    query in (m.get("name") or m.get("full_name") or "").lower()
                )
            ][:5]

            for u in matches:
                u_id_str = str(u.get("id") or u.get("user_id", "")).strip().lower()
                raw_uname = (u.get("username") or u.get("name") or "user").strip()
                handle = raw_uname.replace(" ", "_")
                dname = (u.get("name") or u.get("full_name") or raw_uname).strip()
                is_admin_member = (u.get("is_admin", False) or u.get("role") == "admin" or u_id_str == admin_id_val)

                def _select_m(ev, tag_h=handle, uid=u_id_str):
                    selected_mention_map[tag_h.lower()] = uid
                    msg_input.value = re.sub(r'@[a-zA-Z0-9_.-]*$', f'@{tag_h} ', msg_input.value or '')
                    autocomplete_card.visible = False
                    _update_send_btn_state()
                    page.update()

                tile = ft.Container(
                    ink=True,
                    border_radius=8,
                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                    on_click=_select_m,
                    content=ft.Row([
                        get_avatar(dname, "direct", is_online=False, radius=13, avatar_url=u.get("profile_picture_url")),
                        ft.Text(f"@{handle}", size=13, weight=ft.FontWeight.BOLD, color=palette["accent"]),
                        ft.Text(dname, size=11, color=palette["text_muted"]),
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=5, vertical=1.5),
                            border_radius=4,
                            bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.AMBER_500),
                            content=ft.Text("Admin", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_500)
                        ) if is_admin_member else ft.Container()
                    ], spacing=8, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER)
                )
                autocomplete_list.controls.append(tile)

            autocomplete_card.visible = (len(autocomplete_list.controls) > 0)
        else:
            autocomplete_card.visible = False

        page.update()

    msg_input = ft.TextField(
        hint_text="Type a message...",
        expand=True,
        multiline=True,
        min_lines=1,
        max_lines=5,
        border_radius=20,
        filled=True,
        bgcolor=palette["input_bg"],
        border_color=ft.Colors.TRANSPARENT,
        focused_border_color=palette["accent"],
        content_padding=ft.Padding.symmetric(horizontal=16, vertical=10),
        text_size=14,
        text_style=ft.TextStyle(color=palette["text"], size=14),
        hint_style=ft.TextStyle(color=palette["text_muted"], size=14),
        shift_enter=True,
        on_change=on_input_change,
        on_submit=send_text_message
    )

    send_btn_container.on_click = send_text_message

    def on_search_changed(e):
        search_query[0] = (e.control.value or "").lower().strip()
        render_chat_list()

    search_field = ft.TextField(
        prefix_icon=ft.Icons.SEARCH_ROUNDED,
        hint_text="Search conversations...",
        border_radius=10,
        height=40,
        expand=True,
        content_padding=ft.Padding.symmetric(horizontal=10, vertical=0),
        filled=True,
        bgcolor=palette["surface_variant"],
        border_color=ft.Colors.TRANSPARENT,
        focused_border_color=palette["accent"],
        text_size=13,
        text_style=ft.TextStyle(color=palette["text"], size=13),
        hint_style=ft.TextStyle(color=palette["text_muted"], size=13),
        on_change=on_search_changed,
        on_submit=lambda e: render_chat_list()
    )

    # ==========================================
    # 5. AVATAR BUILDER
    # ==========================================
    def get_avatar(name: str, channel_type: str, is_online: bool = False, radius: int = 20, avatar_url: str | None = None):
        tokens = [t for t in (name or "").split() if t]
        initials = "".join([t[0] for t in tokens[:2]]).upper() if tokens else "?"
        is_group = channel_type != "direct"
        has_img = bool(avatar_url and isinstance(avatar_url, str) and (avatar_url.startswith("http") or avatar_url.startswith("data:")))

        if is_group:
            if has_img:
                base_avatar = ft.CircleAvatar(
                    foreground_image_src=avatar_url,
                    content=ft.Text(initials, size=radius * 0.58, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    bgcolor=palette["accent"],
                    radius=radius,
                )
            else:
                base_avatar = ft.CircleAvatar(
                    content=ft.Icon(ft.Icons.GROUPS_ROUNDED, color=ft.Colors.WHITE, size=radius - 3),
                    bgcolor=palette["accent"],
                    radius=radius,
                )
        elif has_img:
            base_avatar = ft.CircleAvatar(
                foreground_image_src=avatar_url,
                content=ft.Text(initials, size=radius * 0.58, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                bgcolor=ft.Colors.with_opacity(0.85, palette["accent_glow"]),
                radius=radius
            )
        else:
            base_avatar = ft.CircleAvatar(
                content=ft.Text(initials, size=radius * 0.58, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                bgcolor=palette["accent"] if is_group else ft.Colors.with_opacity(0.85, palette["accent_glow"]),
                radius=radius
            )

        if channel_type == "direct":
            dot_size = max(10, radius // 2)
            status_dot = ft.Container(
                width=dot_size,
                height=dot_size,
                bgcolor=palette["online_dot"] if is_online else palette["border"],
                border=ft.Border.all(2, palette["surface"]),
                shape=ft.BoxShape.CIRCLE
            )
            return ft.Stack(
                controls=[
                    base_avatar,
                    ft.Container(content=status_dot, alignment=ft.Alignment(1.0, 1.0))
                ],
                width=radius * 2,
                height=radius * 2
            )
        return base_avatar

    # ==========================================
    # 6. SPEED DIAL FAB & CHAT LIST RENDERER
    # ==========================================
    def _speed_dial_item(icon, label, on_click_fn):
        return ft.Row(
            controls=[
                ft.Container(
                    content=ft.Text(label, size=12, weight=ft.FontWeight.W_500, color=palette["text"]),
                    bgcolor=palette["card_bg"],
                    border=ft.Border.all(1, palette["border"]),
                    border_radius=8,
                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                    shadow=ft.BoxShadow(blur_radius=6, color=ft.Colors.with_opacity(0.12, ft.Colors.BLACK), offset=ft.Offset(0, 2))
                ),
                ft.FloatingActionButton(
                    content=ft.Icon(icon, color=ft.Colors.WHITE, size=18),
                    bgcolor=palette["accent_glow"],
                    width=40, height=40,
                    on_click=on_click_fn,
                    mini=True
                )
            ],
            alignment=ft.MainAxisAlignment.END, spacing=8
        )

    def _build_speed_dial():
        mini_items = ft.Column(
            controls=[
                _speed_dial_item(ft.Icons.GROUPS_ROUNDED, "New Group", lambda e: _speed_dial_action(open_create_channel_modal, e)),
                _speed_dial_item(ft.Icons.PERSON_ADD_ROUNDED, "Direct Message", lambda e: _speed_dial_action(open_users_modal, e)),
            ],
            spacing=8,
            visible=fab_open[0],
            horizontal_alignment=ft.CrossAxisAlignment.END
        )
        main_fab = ft.FloatingActionButton(
            content=ft.Icon(
                ft.Icons.CLOSE if fab_open[0] else ft.Icons.EDIT_ROUNDED,
                color=ft.Colors.WHITE, size=20
            ),
            bgcolor=palette["accent_glow"],
            on_click=toggle_fab,
            elevation=3
        )
        return ft.Column(
            controls=[mini_items, main_fab],
            spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.END,
            alignment=ft.MainAxisAlignment.END
        )

    def toggle_fab(e):
        fab_open[0] = not fab_open[0]
        render_chat_list()

    def _speed_dial_action(fn, e):
        fab_open[0] = False
        render_chat_list()
        fn(e)

    chat_list_scroll_col = ft.ListView(expand=True, spacing=0)
    speed_dial_container = ft.Container(bottom=20, right=16, content=_build_speed_dial())

    chat_list_ui = ft.Column(
        expand=True,
        controls=[
            # Top Header Bar
            ft.Container(
                bgcolor=palette["header_bg"],
                padding=ft.Padding.symmetric(horizontal=16, vertical=14),
                border=ft.Border.only(bottom=ft.BorderSide(1, palette["border"])),
                content=ft.Column([
                    ft.Row([
                        ft.Row([
                            ft.Icon(ft.Icons.FORUM_ROUNDED, size=20, color=palette["accent"]),
                            ft.Text("Nu Chat", size=18, weight=ft.FontWeight.BOLD, color=palette["text"]),
                        ], spacing=8, tight=True),
                        ft.IconButton(
                            icon=ft.Icons.ADD_COMMENT_ROUNDED,
                            icon_color=palette["accent"],
                            icon_size=20,
                            tooltip="New Message or Group",
                            on_click=lambda e: toggle_fab(e)
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Container(height=6),
                    ft.Row([search_field])
                ], spacing=0)
            ),
            chat_list_scroll_col
        ],
        spacing=0
    )

    chat_list_panel.content = ft.Stack(
        expand=True,
        controls=[
            chat_list_ui,
            speed_dial_container
        ]
    )

    def _clear_search(e=None):
        search_field.value = ""
        search_query[0] = ""
        try:
            search_field.update()
        except Exception:
            pass
        render_chat_list()

    def make_whatsapp_chat_skeleton(idx: int = 0) -> ft.Container:
        name_widths = [120, 145, 100, 135, 110, 130]
        msg_widths = [190, 160, 220, 175, 140, 200]
        nw = name_widths[idx % len(name_widths)]
        mw = msg_widths[idx % len(msg_widths)]

        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            margin=ft.Margin.symmetric(horizontal=8, vertical=2),
            border_radius=10,
            content=ft.Row([
                shimmer_box(radius=22, width=44, height=44),
                ft.Container(width=10),
                ft.Column([
                    ft.Row([
                        shimmer_box(radius=5, width=nw, height=13),
                        shimmer_box(radius=4, width=38, height=10),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Container(height=2),
                    ft.Row([
                        shimmer_box(radius=5, width=mw, height=11),
                    ]),
                ], expand=True, spacing=4, tight=True)
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=0)
        )

    def _start_shimmer_loop(boxes):
        if shimmer_loop_running[0] or not boxes:
            return
        shimmer_loop_running[0] = True

        async def _shimmer_pulse():
            phase = 0
            while is_loading_channels[0]:
                try:
                    for i, b in enumerate(boxes):
                        on = (i + phase) % 3 == 0
                        b.opacity = 0.55 if on else 0.22
                    if not is_loading_channels[0]:
                        break
                    chat_list_scroll_col.update()
                    phase += 1
                    await asyncio.sleep(0.35)
                except Exception:
                    break
            shimmer_loop_running[0] = False

        page.run_task(_shimmer_pulse)

    def render_chat_list():
        if is_loading_channels[0]:
            skeleton_items = [make_whatsapp_chat_skeleton(i) for i in range(7)]
            chat_list_scroll_col.controls = skeleton_items
            speed_dial_container.content = _build_speed_dial()
            try:
                chat_list_scroll_col.update()
                speed_dial_container.update()
            except Exception:
                page.update()
            boxes = []
            for item in skeleton_items:
                boxes.extend(collect_shimmer_boxes(item))
            _start_shimmer_loop(boxes)
            return

        q = search_query[0]
        filtered = [c for c in channels_list if q in c.get("name", "").lower()] if q else channels_list

        list_controls = []

        if not filtered:
            if q:
                list_controls.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=24, vertical=48),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Column([
                            ft.Container(
                                width=56,
                                height=56,
                                border_radius=28,
                                bgcolor=palette["surface_variant"],
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.SEARCH_OFF_ROUNDED, size=28, color=palette["text_muted"])
                            ),
                            ft.Container(height=6),
                            ft.Text("No chats found", color=palette["text"], weight=ft.FontWeight.W_600, size=15),
                            ft.Text(f'No conversations match "{q}".', size=12, color=palette["text_muted"], text_align=ft.TextAlign.CENTER),
                            ft.Container(height=6),
                            ft.TextButton(
                                "Clear search",
                                on_click=_clear_search,
                                style=ft.ButtonStyle(color=palette["accent"])
                            )
                        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4)
                    )
                )
            else:
                list_controls.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=24, vertical=56),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Column([
                            ft.Container(
                                width=64,
                                height=64,
                                border_radius=32,
                                bgcolor=palette["surface_variant"],
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED, size=32, color=palette["text_muted"])
                            ),
                            ft.Container(height=8),
                            ft.Text("No chats yet", color=palette["text"], weight=ft.FontWeight.W_600, size=16),
                            ft.Text(
                                "Start connecting with course groups, fellow students, or instructors.",
                                size=12,
                                color=palette["text_muted"],
                                text_align=ft.TextAlign.CENTER
                            ),
                            ft.Container(height=12),
                            ft.Container(
                                content=ft.Row([
                                    ft.Icon(ft.Icons.ADD_COMMENT_ROUNDED, size=16, color=ft.Colors.WHITE),
                                    ft.Text("Start a Chat", size=13, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE),
                                ], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
                                bgcolor=palette["accent"],
                                border_radius=20,
                                padding=ft.Padding.symmetric(horizontal=18, vertical=10),
                                ink=True,
                                on_click=open_users_modal,
                            )
                        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4)
                    )
                )
        else:
            for idx, chat in enumerate(filtered):
                cid = chat.get("channel_id") or chat.get("id")
                is_active = bool(current_chat_id[0] and cid == current_chat_id[0])
                unread = chat.get("unread", 0)
                has_unread_mention = chat.get("has_unread_mention", False)
                is_highlighted = (unread > 0 or has_unread_mention)
                is_online = chat.get("is_online", False)
                chat_name = chat.get("name", "Chat")

                unread_badge = ft.Container()
                if has_unread_mention:
                    unread_badge = ft.Container(
                        content=ft.Text(
                            "@",
                            size=12, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD
                        ),
                        bgcolor=palette["accent_glow"],
                        border_radius=11,
                        width=22,
                        height=22,
                        alignment=ft.Alignment.CENTER,
                        tooltip="You were tagged in this chat"
                    )
                elif unread > 0:
                    unread_badge = ft.Container(
                        content=ft.Text(
                            str(unread) if unread < 100 else "99+",
                            size=10, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD
                        ),
                        bgcolor=palette["accent_glow"],
                        border_radius=10,
                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                        alignment=ft.Alignment.CENTER
                    )

                if chat.get("is_typing"):
                    preview_ui = ft.Text(
                        "typing…",
                        size=12, color=palette["online_dot"], expand=True,
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, italic=True
                    )
                else:
                    preview_ui = ft.Text(
                        chat.get("last_msg", ""),
                        size=12, color=palette["text_muted"], expand=True,
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS
                    )

                time_txt = ft.Text(
                    format_message_time(chat.get("time", "")),
                    size=11,
                    color=palette["accent"] if is_highlighted else palette["text_muted"],
                    weight=ft.FontWeight.BOLD if is_highlighted else ft.FontWeight.NORMAL
                )

                tile = ft.Container(
                    ink=True,
                    border_radius=10,
                    margin=ft.Margin.symmetric(horizontal=8, vertical=2),
                    on_click=lambda e, c_id=cid: page.run_task(load_active_chat, c_id),
                    on_long_press=lambda e, c_id=cid, c_name=chat_name: open_delete_modal(c_id, c_name),
                    bgcolor=palette["active_chat_bg"] if is_active else ft.Colors.TRANSPARENT,
                    border=None,
                    padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                    content=ft.Row([
                        get_avatar(chat_name, chat.get("type", "dm"), is_online, radius=22, avatar_url=chat.get("avatar_url") or chat.get("other_user_avatar")),
                        ft.Container(width=10),
                        ft.Column([
                            ft.Row([
                                ft.Text(
                                    chat_name,
                                    weight=ft.FontWeight.BOLD if is_highlighted else ft.FontWeight.W_600,
                                    size=14, expand=True,
                                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                                    color=palette["text"]
                                ),
                                time_txt
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.Row([preview_ui, unread_badge],
                                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                   vertical_alignment=ft.CrossAxisAlignment.CENTER)
                        ], expand=True, spacing=3, tight=True)
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=0)
                )

                list_controls.append(tile)

        chat_list_scroll_col.controls = list_controls
        speed_dial_container.content = _build_speed_dial()
        try:
            chat_list_scroll_col.update()
            speed_dial_container.update()
        except Exception:
            page.update()

    # ==========================================
    # 8. MESSAGE BUBBLE RENDERER
    # ==========================================

    def render_message_bubble(msg: dict, prev_msg: Optional[dict] = None, next_msg: Optional[dict] = None):
        msg_type = msg.get("type", "text")

        # ── A. System Announcement Pill ───────────────────────────────────────
        if msg_type == "system":
            return ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, size=12, color=palette["system_text"]),
                            ft.Text(msg.get("content", ""), size=11, color=palette["system_text"], weight=ft.FontWeight.W_500),
                        ], spacing=6, tight=True),
                        bgcolor=palette["system_bg"],
                        border=ft.Border.all(1, palette["border"]),
                        padding=ft.Padding.symmetric(horizontal=12, vertical=5),
                        border_radius=12,
                        margin=ft.Margin.symmetric(vertical=4),
                    )
                ]
            )

        # ── B. Identify Sender & Clustering ───────────────────────────────────
        sender_info = msg.get("sender", {})
        my_id = str(current_user_id[0]).strip().lower()
        sender_id = str(sender_info.get("id", msg.get("sender_id", "unknown"))).strip().lower()
        sender_name = str(sender_info.get("name", msg.get("sender_name", "Unknown"))).strip() or "Unknown"
        is_me = (sender_id == my_id) or msg.get("is_me", False)

        curr_ts = parse_iso_timestamp(msg.get("created_at", ""))

        # Check if previous message was from the same sender within 180 seconds
        prev_is_same = False
        if prev_msg and prev_msg.get("type") not in ("system", "presence", "typing"):
            p_sender = str((prev_msg.get("sender") or {}).get("id", prev_msg.get("sender_id", ""))).strip().lower()
            p_ts = parse_iso_timestamp(prev_msg.get("created_at", ""))
            if p_sender == sender_id and abs(curr_ts - p_ts) < 180:
                prev_is_same = True

        # Check if next message is from the same sender within 180 seconds
        next_is_same = False
        if next_msg and next_msg.get("type") not in ("system", "presence", "typing"):
            n_sender = str((next_msg.get("sender") or {}).get("id", next_msg.get("sender_id", ""))).strip().lower()
            n_ts = parse_iso_timestamp(next_msg.get("created_at", ""))
            if n_sender == sender_id and abs(n_ts - curr_ts) < 180:
                next_is_same = True

        raw_content = msg.get("content", "")
        raw_ts = msg.get("created_at", "")
        ts_label = format_message_time(raw_ts)

        meta = msg.get("metadata_payload") or msg.get("metadata") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        meta = meta or {}

        is_poll = (msg_type in ("poll", "poll_update") or "options" in meta or ("|||" in raw_content and msg_type != "code"))

        # ── C. Bubble Radius Styling (Continuous Clustered Edges) ────────────
        if is_poll:
            radius = 16
            bg = palette["card_bg"]
            text_color = palette["text"]
            ts_color = palette["text_muted"]
            border = ft.Border.all(1.5, palette["accent"] if is_me else palette["border"])
        elif is_me:
            radius = ft.BorderRadius.only(
                top_left=14,
                top_right=4 if prev_is_same else 14,
                bottom_left=14,
                bottom_right=4 if next_is_same else 2
            )
            bg = palette["bubble_out_bg"]
            text_color = palette["bubble_out_text"]
            ts_color = palette["bubble_out_ts"]
            border = None
        else:
            radius = ft.BorderRadius.only(
                top_left=4 if prev_is_same else 14,
                top_right=14,
                bottom_left=4 if next_is_same else 2,
                bottom_right=14
            )
            bg = palette["bubble_in_bg"]
            text_color = palette["bubble_in_text"]
            ts_color = palette["bubble_in_ts"]
            border = ft.Border.all(1, palette["bubble_in_border"])

        # ── D. Delivery Tick Telemetry ─────────────────────────────────────────
        status_tick = ft.Container()
        if is_me:
            status_tick = ft.Icon(
                ft.Icons.DONE_ALL_ROUNDED,
                size=12,
                color=palette["accent"] if is_poll else ft.Colors.with_opacity(0.85, ft.Colors.WHITE)
            )

        ts_row = ft.Row(
            [
                ft.Text(ts_label, size=10, color=ts_color),
                status_tick
            ],
            spacing=4,
            tight=True,
            alignment=ft.MainAxisAlignment.END
        )

        # ── E. Body Content (Poll vs Code vs Standard Text) ───────────────────
        body_controls = []

        # 1. Sender Name Header (Show only on first message of cluster in group chats)
        if not is_me and not prev_is_same:
            active_info = next((c for c in channels_list if c.get("channel_id") == current_chat_id[0]), {})
            if active_info.get("type") != "direct":
                body_controls.append(
                    ft.Text(sender_name, size=11, weight=ft.FontWeight.BOLD, color=palette["accent"])
                )

        # 2. Interactive Poll Rendering (Clean, lightweight design mirroring reference image)
        if is_poll:
            poll_id = str(msg.get("id", ""))
            poll_title = (meta.get("question") if meta.get("question") else raw_content) or "In-Chat Poll"
            if poll_title.strip().lower() == "poll" and meta.get("question"):
                poll_title = meta.get("question")

            # Robust options extraction
            options = meta.get("options") or meta.get("poll_options") or meta.get("choices") or []
            if isinstance(options, str):
                try:
                    options = json.loads(options)
                except Exception:
                    if "|||" in options:
                        options = options.split("|||")
                    else:
                        options = [o.strip() for o in options.split(",") if o.strip()]

            if isinstance(options, dict):
                options = list(options.values())

            # Fallback for ||| format in content (e.g. "Question?|||Opt1|||Opt2")
            if not options and "|||" in raw_content:
                parts = [p.strip() for p in raw_content.split("|||") if p.strip()]
                if len(parts) >= 2:
                    poll_title = parts[0]
                    options = parts[1:]
            elif "|||" in raw_content:
                poll_title = raw_content.split("|||")[0].strip()

            clean_options = []
            for o in options:
                if isinstance(o, dict):
                    clean_options.append(str(o.get("text") or o.get("option") or o.get("label") or o.get("value") or o))
                else:
                    clean_options.append(str(o))
            options = clean_options

            if not options:
                options = ["Option 1", "Option 2"]

            # Votes extraction
            votes = meta.get("votes") or {}
            if isinstance(votes, str):
                try:
                    votes = json.loads(votes)
                except Exception:
                    votes = {}
            if not isinstance(votes, dict):
                votes = {}

            # Identify if current user voted
            my_vote = None
            for uid_k, u_vote in votes.items():
                if str(uid_k).strip().lower() == my_id:
                    my_vote = u_vote
                    break

            total_votes = len(votes)
            opt_counts = {}
            for user_vote in votes.values():
                selected = user_vote if isinstance(user_vote, list) else [user_vote]
                for o in selected:
                    o_str = str(o).strip().lower()
                    opt_counts[o_str] = opt_counts.get(o_str, 0) + 1

            # Voter name lookup helper for mini avatar badges
            def _get_voter_initials(uid_str):
                if uid_str == my_id:
                    return "ME"
                for u in all_users_cache:
                    if str(u.get("id") or u.get("user_id", "")).strip().lower() == uid_str:
                        name = (u.get("name") or u.get("full_name") or u.get("username") or "").strip()
                        parts = name.split()
                        if len(parts) >= 2:
                            return (parts[0][0] + parts[1][0]).upper()
                        elif parts:
                            return parts[0][:2].upper()
                return "U"

            is_multi = meta.get("is_multi_select", False)
            poll_options_col = []
            for opt in options:
                opt_str = str(opt).strip()
                count = opt_counts.get(opt_str.lower(), 0)
                pct = (count / total_votes) if total_votes > 0 else 0.0

                if isinstance(my_vote, list):
                    has_voted_this = any(str(v).strip().lower() == opt_str.lower() for v in my_vote)
                elif my_vote is not None:
                    has_voted_this = (str(my_vote).strip().lower() == opt_str.lower())
                else:
                    has_voted_this = False

                # Radio (single-choice) vs Checkbox (multi-choice) indicator
                if is_multi:
                    radio_icon = ft.Icon(
                        ft.Icons.CHECK_BOX_ROUNDED if has_voted_this else ft.Icons.CHECK_BOX_OUTLINE_BLANK_ROUNDED,
                        size=18,
                        color=palette["accent"] if has_voted_this else palette["text_muted"]
                    )
                else:
                    radio_icon = ft.Icon(
                        ft.Icons.RADIO_BUTTON_CHECKED_ROUNDED if has_voted_this else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED,
                        size=18,
                        color=palette["accent"] if has_voted_this else palette["text_muted"]
                    )

                async def _cast_vote_async(target_opt, p_id):
                    if ws_client_ref[0] and current_chat_id[0]:
                        sent = await ws_client_ref[0].send_message(
                            current_chat_id[0],
                            target_opt,
                            "poll_vote",
                            poll_id=p_id
                        )
                        if not sent:
                            show_page_snackbar(page, ft.SnackBar(content=ft.Text("Vote failed to send. Check connection."), bgcolor=ft.Colors.AMBER_800))
                    else:
                        show_page_snackbar(page, ft.SnackBar(content=ft.Text("Not connected to chat room."), duration=2000))

                def _cast_vote(e, target_opt=opt_str, p_id=poll_id):
                    # 1. OPTIMISTIC IN-MEMORY UPDATE (0ms visual latency)
                    try:
                        v_dict = meta.get("votes") or {}
                        if isinstance(v_dict, str):
                            try: v_dict = json.loads(v_dict)
                            except: v_dict = {}
                        if not isinstance(v_dict, dict):
                            v_dict = {}

                        if is_multi:
                            u_v = v_dict.get(my_id, [])
                            if isinstance(u_v, str): u_v = [u_v]
                            else: u_v = list(u_v)
                            if target_opt in u_v:
                                u_v.remove(target_opt)
                            else:
                                u_v.append(target_opt)
                            if not u_v:
                                v_dict.pop(my_id, None)
                            else:
                                v_dict[my_id] = u_v
                        else:
                            if v_dict.get(my_id) == target_opt:
                                v_dict.pop(my_id, None)
                            else:
                                v_dict[my_id] = target_opt

                        meta["votes"] = v_dict
                        msg["metadata_payload"] = meta

                        # Instantly re-render this bubble in messages_listview
                        for idx, ctrl in enumerate(messages_listview.controls):
                            if hasattr(ctrl, "data") and str(ctrl.data).strip().lower() == str(p_id).strip().lower():
                                messages_listview.controls[idx] = render_message_bubble(msg)
                                page.update()
                                break
                    except Exception as opt_err:
                        print(f"[NuChat] Optimistic vote render error: {opt_err}")

                    page.run_task(_cast_vote_async, target_opt, p_id)

                # Identify users who voted for this option
                opt_voters = []
                for uid_k, u_vote in votes.items():
                    selected = u_vote if isinstance(u_vote, list) else [u_vote]
                    if any(str(v).strip().lower() == opt_str.lower() for v in selected):
                        opt_voters.append(str(uid_k).strip().lower())

                # Build mini avatar stack matching reference image
                voter_avatars_list = []
                if opt_voters:
                    for v_uid in opt_voters[:2]:
                        inits = _get_voter_initials(v_uid)
                        voter_avatars_list.append(
                            ft.Container(
                                width=18,
                                height=18,
                                border_radius=9,
                                bgcolor=palette["accent"] if v_uid == my_id else palette["accent_glow"],
                                border=ft.Border.all(1.5, bg),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Text(inits, size=8, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
                            )
                        )
                    if len(opt_voters) > 2:
                        voter_avatars_list.append(
                            ft.Container(
                                height=18,
                                padding=ft.Padding.symmetric(horizontal=4),
                                border_radius=9,
                                bgcolor=palette["surface_variant"],
                                border=ft.Border.all(1.5, bg),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Text(f"+{len(opt_voters) - 2}", size=8, weight=ft.FontWeight.BOLD, color=palette["text_muted"])
                            )
                        )
                voter_avatars_widget = ft.Row(voter_avatars_list, spacing=-4, tight=True) if voter_avatars_list else ft.Container()

                vote_label = f"{count} vote{'s' if count != 1 else ''}"
                if total_votes > 0:
                    vote_label += f" • {int(pct * 100)}%"

                # Option tile row: [Radio] [Label] ... [Count • %]
                opt_tile = ft.Container(
                    ink=True,
                    on_click=_cast_vote,
                    border_radius=8,
                    padding=ft.Padding.symmetric(horizontal=6, vertical=5),
                    content=ft.Column([
                        ft.Row([
                            ft.Row([
                                radio_icon,
                                ft.Container(
                                    expand=True,
                                    content=ft.Text(
                                        opt_str,
                                        size=13,
                                        weight=ft.FontWeight.BOLD if has_voted_this else ft.FontWeight.W_500,
                                        color=palette["accent"] if has_voted_this else text_color,
                                        no_wrap=False
                                    )
                                ),
                            ], spacing=8, expand=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                            ft.Text(
                                vote_label,
                                size=11,
                                weight=ft.FontWeight.BOLD if has_voted_this else ft.FontWeight.W_500,
                                color=palette["accent"] if has_voted_this else palette["text_muted"]
                            )
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.Row([
                            ft.Container(
                                expand=True,
                                content=ft.ProgressBar(
                                    value=pct,
                                    color=palette["accent"] if has_voted_this else palette["bar_other"],
                                    bgcolor=palette["surface_variant"],
                                    height=5,
                                    border_radius=3
                                )
                            ),
                            voter_avatars_widget
                        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)
                    ], spacing=4)
                )
                poll_options_col.append(opt_tile)

            # Minimalist card body: title + options + subtle votes count with "View votes" link + timestamp
            poll_card = ft.Column([
                ft.Text(poll_title, size=15, weight=ft.FontWeight.BOLD, color=text_color),
                ft.Container(height=4),
                *poll_options_col,
                ft.Container(height=6),
                ft.Row([
                    ft.Row([
                        ft.Text(
                            f"{total_votes} vote{'s' if total_votes != 1 else ''}",
                            size=11,
                            color=palette["text_muted"],
                            weight=ft.FontWeight.W_500
                        ),
                        ft.Container(
                            ink=True,
                            on_click=lambda e, m=msg: open_poll_breakdown_modal(m),
                            content=ft.Text("• View votes", size=11, color=palette["accent"], weight=ft.FontWeight.BOLD)
                        ) if total_votes > 0 else ft.Container()
                    ], spacing=6, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ts_row
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)
            ], spacing=6, tight=True)
            body_controls.append(poll_card)

        # 3. Formatted Code Snippet Block
        elif raw_content.startswith("```") and raw_content.endswith("```"):
            code_body = raw_content[3:-3].strip()
            first_line = code_body.split("\n", 1)[0].strip()
            lang = "CODE"
            if len(first_line) < 12 and "\n" in code_body:
                lang = first_line.upper()
                code_body = code_body.split("\n", 1)[1]

            def _copy_code(e, text_to_copy=code_body):
                try:
                    page.set_clipboard(text_to_copy)
                    show_page_snackbar(page, ft.SnackBar(content=ft.Text("Code snippet copied to clipboard!"), duration=2000))
                except Exception:
                    pass

            code_card = ft.Container(
                bgcolor=palette["code_bg"],
                border=ft.Border.all(1, palette["code_border"]),
                border_radius=8,
                padding=10,
                content=ft.Column([
                    ft.Row([
                        ft.Text(lang, size=10, weight=ft.FontWeight.BOLD, color=palette["text_muted"]),
                        ft.IconButton(
                            icon=ft.Icons.CONTENT_COPY_ROUNDED,
                            icon_size=13,
                            icon_color=palette["text_muted"],
                            tooltip="Copy Code",
                            on_click=_copy_code,
                            style=ft.ButtonStyle(padding=0)
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Text(
                        code_body,
                        font_family="monospace",
                        size=12,
                        color=palette["code_text"],
                        selectable=True
                    )
                ], spacing=4)
            )
            body_controls.append(code_card)

        # 4. Standard Text Bubble (WhatsApp Rich Text Formatting)
        else:
            def _on_mention_click(u):
                clean_click = str(u).lower().strip()
                if clean_click == "@all":
                    show_page_snackbar(page, ft.SnackBar(content=ft.Text("📢 Mentioned all members in this group"), duration=1500))
                    return
                if clean_click == "@admin":
                    show_page_snackbar(page, ft.SnackBar(content=ft.Text("Tagged Group Admin / Course Instructor"), duration=1500))
                    return
                target_u = str(u).lstrip("@").lower().replace("_", " ")
                matched_uid = None
                for member in active_channel_members:
                    m_uname = (member.get("username") or "").lower()
                    m_name = (member.get("name") or member.get("full_name") or "").lower()
                    if target_u in (m_uname, m_name) or target_u == m_uname.replace(" ", "_"):
                        matched_uid = str(member.get("id") or member.get("user_id", "")).strip().lower()
                        break
                if not matched_uid:
                    for usr in all_users_cache:
                        u_uname = (usr.get("username") or "").lower()
                        u_name = (usr.get("name") or usr.get("full_name") or "").lower()
                        if target_u in (u_uname, u_name) or target_u == u_uname.replace(" ", "_"):
                            matched_uid = str(usr.get("id") or usr.get("user_id", "")).strip().lower()
                            break
                if matched_uid:
                    if matched_uid == my_id:
                        page.go("/profile")
                    else:
                        page.go(f"/member/{matched_uid}")
                else:
                    show_page_snackbar(page, ft.SnackBar(content=ft.Text(f"Mentioned {u}"), duration=1500))

            body_controls.append(
                ft.Text(
                    spans=build_whatsapp_spans(raw_content, text_color, palette, _on_mention_click, is_me=is_me),
                    size=14,
                    selectable=True
                )
            )

        # Timestamp row (already embedded inside poll_card for polls)
        if not is_poll:
            body_controls.append(ts_row)

        def _copy_bubble_text(e):
            try:
                page.set_clipboard(raw_content)
                show_page_snackbar(page, ft.SnackBar(content=ft.Text("Message text copied"), duration=1500))
            except Exception:
                pass

        cur_w = page.width if (hasattr(page, "width") and page.width) else 380
        is_mob = not is_desktop[0]

        if is_poll:
            poll_width = 310 if not is_mob else min(270, int(cur_w - 86))
        else:
            poll_width = None

        bubble = ft.Container(
            width=poll_width,
            expand=False if is_poll else True,
            expand_loose=False if is_poll else True,
            bgcolor=bg,
            border=border,
            border_radius=radius,
            padding=ft.Padding.symmetric(horizontal=14 if is_poll else 12, vertical=12 if is_poll else 8),
            on_long_press=_copy_bubble_text,
            shadow=ft.BoxShadow(
                blur_radius=4 if is_poll else 3,
                color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
                offset=ft.Offset(0, 1)
            ),
            content=ft.Column(
                body_controls,
                tight=True,
                spacing=3,
                horizontal_alignment=ft.CrossAxisAlignment.END if is_me else ft.CrossAxisAlignment.START
            )
        )

        # Natural margin: tighter spacing inside clusters
        v_margin = 1 if prev_is_same else 4

        # Responsive horizontal margins to ensure bubbles never bleed off screen
        # and stay cleanly padded on both mobile and desktop
        if is_mob:
            out_left_margin = 12 if is_poll else 32
            out_right_margin = 2
            in_left_margin = 2
            in_right_margin = 12 if is_poll else 32
        else:
            out_left_margin = 16 if is_poll else 120
            out_right_margin = 6
            in_left_margin = 6
            in_right_margin = 16 if is_poll else 120

        if is_me:
            c = ft.Container(
                content=ft.Row([bubble], alignment=ft.MainAxisAlignment.END),
                margin=ft.Margin(top=v_margin, bottom=v_margin, left=out_left_margin, right=out_right_margin)
            )
            c.data = str(msg.get("id"))
            return c
        else:
            # Show avatar only on last message of cluster (or single message)
            if not next_is_same:
                sender_initials = "".join([t[0] for t in sender_name.split()[:2]]).upper() or "?"
                sender_avatar_url = (msg.get("sender") or {}).get("profile_picture_url")
                has_s_img = bool(sender_avatar_url and isinstance(sender_avatar_url, str) and (sender_avatar_url.startswith("http") or sender_avatar_url.startswith("data:")))
                avatar_ctrl = ft.CircleAvatar(
                    foreground_image_src=sender_avatar_url if has_s_img else None,
                    content=ft.Text(sender_initials, size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    bgcolor=ft.Colors.with_opacity(0.85, palette["accent_glow"]),
                    radius=14
                )
                def _open_sender_profile(ev, sid=sender_id):
                    if sid:
                        if sid == my_id:
                            page.go("/profile")
                        else:
                            page.go(f"/member/{sid}")

                avatar_widget = ft.Container(
                    content=avatar_ctrl,
                    width=28,
                    height=28,
                    alignment=ft.Alignment.CENTER,
                    clip_behavior=ft.ClipBehavior.HARD_EDGE,
                    ink=True,
                    border_radius=14,
                    tooltip=f"View {sender_name}'s profile",
                    on_click=_open_sender_profile
                )
            else:
                # Invisible placeholder to keep bubbles indented consistently
                avatar_widget = ft.Container(width=28, height=28)

            c = ft.Container(
                content=ft.Row(
                    [avatar_widget, bubble],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.END,
                    spacing=6
                ),
                margin=ft.Margin(top=v_margin, bottom=v_margin, left=in_left_margin, right=in_right_margin)
            )
            c.data = str(msg.get("id"))
            return c

    # ==========================================
    # 9. TYPING INDICATORS
    # ==========================================
    def show_typing_indicator(channel_id: str, sender_name: str):
        tok = datetime.now().timestamp()
        typing_tokens[channel_id] = tok

        # 1. Update left list state
        for chat in channels_list:
            if chat.get("channel_id") == channel_id:
                chat["is_typing"] = True
                chat["typing_name"] = sender_name
                break
        render_chat_list()

        # 2. Update active chat header subtitle
        if channel_id == current_chat_id[0] and len(active_chat_header.controls) >= 3:
            status_col = active_chat_header.controls[2]
            if len(status_col.controls) >= 2:
                status_col.controls[1].value = "typing..."
                status_col.controls[1].color = palette["online_dot"]
                page.update()

        async def clear_typing(t):
            await asyncio.sleep(3.2)
            if typing_tokens.get(channel_id) != t:
                return
            for c in channels_list:
                if c.get("channel_id") == channel_id:
                    c.pop("is_typing", None)
                    c.pop("typing_name", None)
                    break
            render_chat_list()

            if current_chat_id[0] == channel_id and len(active_chat_header.controls) >= 3:
                status_col = active_chat_header.controls[2]
                if len(status_col.controls) >= 2:
                    chat_info = next((c for c in channels_list if c.get("channel_id") == channel_id), {})
                    is_online = chat_info.get("is_online", False)
                    chat_type = chat_info.get("type", "direct")
                    if chat_type == "direct":
                        status_col.controls[1].value = "online" if is_online else "Offline"
                        status_col.controls[1].color = palette["online_dot"] if is_online else palette["text_muted"]
                    else:
                        status_col.controls[1].value = ""
                    page.update()

        page.run_task(clear_typing, tok)

    # ==========================================
    # 10. ACTIVE CHAT LOADER & SYNC
    # ==========================================
    async def load_active_chat(chat_id: str):
        if chat_load_lock[0]:
            return
        chat_load_lock[0] = True

        try:
            current_chat_id[0] = chat_id
            chat_info = next((c for c in channels_list if c.get("channel_id") == chat_id), {"name": "Chat", "type": "direct"})
            chat_info["unread"] = 0
            chat_info["has_unread_mention"] = False
            active_chat_info[0] = chat_info
            render_chat_list()

            # Cleanly disconnect prior room socket if needed
            if ws_client_ref[0]:
                await ws_client_ref[0].disconnect()
                ws_client_ref[0] = None

            back_btn = ft.IconButton(
                ft.Icons.ARROW_BACK_ROUNDED,
                icon_color=palette["text"],
                icon_size=20,
                on_click=lambda e: page.run_task(close_chat_mobile),
                visible=not is_desktop[0],
                tooltip="Back to Chats"
            )

            _chat_name = chat_info.get("name") or "Chat"
            _chat_type = chat_info.get("type", "direct")
            _chat_online = chat_info.get("is_online", False)
            _is_course = bool(chat_info.get("course_id") or _chat_type == "course")
            _other_uid = chat_info.get("other_user_id")

            # Load group members if this is a group/course chat
            active_channel_members.clear()
            if _chat_type != "direct":
                active_channel_role[0] = chat_info.get("role")
                active_channel_admin_id[0] = chat_info.get("created_by_id") or chat_info.get("admin_id")
                async def _fetch_group_members_task(c_id=chat_id):
                    try:
                        m_res = await get_group_members(token, c_id)
                        if isinstance(m_res, dict):
                            active_channel_members.clear()
                            active_channel_members.extend(m_res.get("members", []))
                            if m_res.get("admin_id"):
                                active_channel_admin_id[0] = m_res.get("admin_id")
                            my_uid_str = str(current_user_id[0]).strip().lower()
                            for mb in m_res.get("members", []):
                                if str(mb.get("id") or mb.get("user_id", "")).strip().lower() == my_uid_str:
                                    if mb.get("role") == "admin" or mb.get("is_admin"):
                                        active_channel_role[0] = "admin"
                                    break
                        elif isinstance(m_res, list):
                            active_channel_members.clear()
                            active_channel_members.extend(m_res)
                    except Exception as e:
                        print(f"[NuChat] Error fetching channel members: {e}")
                page.run_task(_fetch_group_members_task)

            header_actions = []

            if _chat_type != "direct":
                if not _is_course:
                    header_actions.append(
                        ft.IconButton(
                            ft.Icons.PERSON_ADD_ALT_1_ROUNDED,
                            icon_color=palette["text"],
                            icon_size=20,
                            tooltip="Add members",
                            on_click=lambda e: open_add_member_modal(chat_id)
                        )
                    )
                header_actions.append(
                    ft.PopupMenuButton(
                        icon=ft.Icons.MORE_VERT_ROUNDED,
                        icon_color=palette["text"],
                        items=[
                            ft.PopupMenuItem(
                                content="Leave Group",
                                icon=ft.Icons.EXIT_TO_APP_ROUNDED,
                                on_click=lambda e: confirm_leave_group(chat_id, _chat_name)
                            )
                        ]
                    )
                )

            # Profile navigation helper for DM chat header
            def _nav_to_dm_profile(e):
                target_uid = _other_uid
                if not target_uid:
                    for u in all_users_cache:
                        n = (u.get("name") or u.get("full_name") or u.get("username") or "").strip()
                        if n.lower() == _chat_name.lower():
                            target_uid = str(u.get("id") or u.get("user_id", "")).strip().lower()
                            break
                if target_uid:
                    if target_uid == current_user_id[0]:
                        page.go("/profile")
                    else:
                        page.go(f"/member/{target_uid}")

            raw_avatar = get_avatar(_chat_name, _chat_type, _chat_online, radius=20, avatar_url=chat_info.get("avatar_url") or chat_info.get("other_user_avatar"))
            if _chat_type == "direct":
                header_avatar = ft.Container(
                    content=raw_avatar,
                    ink=True,
                    border_radius=20,
                    tooltip=f"View {_chat_name}'s profile",
                    on_click=_nav_to_dm_profile
                )
            else:
                header_avatar = raw_avatar

            title_txt = ft.Text(
                _chat_name,
                weight=ft.FontWeight.BOLD,
                size=15,
                color=palette["text"],
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
                no_wrap=True
            )
            if _chat_type == "direct":
                title_widget = ft.Container(
                    content=title_txt,
                    ink=True,
                    border_radius=4,
                    on_click=_nav_to_dm_profile,
                    tooltip=f"View {_chat_name}'s profile"
                )
            else:
                title_widget = title_txt

            status_txt = ft.Text("Connecting...", size=11, color=palette["text_muted"])

            active_chat_header.controls = [
                back_btn,
                header_avatar,
                ft.Column([
                    title_widget,
                    status_txt
                ], spacing=1, expand=True),
                *header_actions
            ]

            # Spinner during message load
            messages_listview.controls = [
                ft.Row([ft.ProgressRing(color=palette["accent"], width=24, height=24, stroke_width=2)],
                       alignment=ft.MainAxisAlignment.CENTER)
            ]

            # Mount Active Chat Panel
            active_chat_panel.content = ft.Column([
                # Top Room Header
                ft.Container(
                    bgcolor=palette["header_bg"],
                    border=ft.Border.only(bottom=ft.BorderSide(1, palette["border"])),
                    padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                    content=active_chat_header
                ),
                # Message History View
                ft.Container(
                    content=messages_listview,
                    expand=True,
                    bgcolor=palette["chat_wall"]
                ),
                # Bottom Input Composer with Autocomplete Overlay
                ft.Column([
                    autocomplete_card,
                    ft.Container(
                        bgcolor=palette["input_bar_bg"],
                        border=ft.Border.only(top=ft.BorderSide(1, palette["border"])),
                        padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                        content=ft.Row([
                            # Action Trigger Button (+)
                            ft.IconButton(
                                icon=ft.Icons.ADD_CIRCLE_OUTLINE_ROUNDED,
                                icon_color=palette["accent"],
                                icon_size=24,
                                tooltip="Chat Actions",
                                on_click=lambda e: open_attachment_actions_modal(e)
                            ),
                            # Multiline Auto-expanding Input
                            ft.Container(expand=True, content=msg_input),
                            ft.Container(width=6),
                            # Dynamic Send Button
                            send_btn_container
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=0)
                    )
                ], spacing=0, tight=True)
            ], spacing=0, expand=True)

            update_responsive_layout()
            page.update()

            # --- 1. RENDER FROM LOCAL SQLITE CACHE ---
            def _render_history(hist_list: list):
                messages_listview.controls.clear()
                seen_msg_ids.clear()

                clean_msgs = [m for m in hist_list if m.get("type") not in ("typing", "presence")]
                if not clean_msgs:
                    messages_listview.controls.append(
                        ft.Container(
                            expand=True,
                            alignment=ft.Alignment.CENTER,
                            padding=40,
                            content=ft.Column([
                                ft.Icon(ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED, size=40, color=palette["text_muted"]),
                                ft.Container(height=4),
                                ft.Text("No messages yet", size=14, weight=ft.FontWeight.W_600, color=palette["text"]),
                                ft.Text("Send a message or launch a poll below!", size=12, color=palette["text_muted"])
                            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
                        )
                    )
                    page.update()
                    return

                current_date_label = None
                for i, m in enumerate(clean_msgs):
                    mid = str(m.get("id"))
                    if mid:
                        seen_msg_ids.add(mid)

                    m_date = get_day_label(m.get("created_at"))
                    if m_date and m_date != current_date_label:
                        date_pill = ft.Container(
                            content=ft.Row([
                                ft.Icon(ft.Icons.CALENDAR_TODAY_ROUNDED, size=11, color=palette["pill_text"]),
                                ft.Text(m_date, size=11, color=palette["pill_text"], weight=ft.FontWeight.W_600)
                            ], spacing=4, tight=True),
                            bgcolor=palette["pill_bg"],
                            border=ft.Border.all(1, palette["border"]),
                            padding=ft.Padding.symmetric(horizontal=12, vertical=4),
                            border_radius=12,
                            margin=ft.Margin.symmetric(vertical=6)
                        )
                        messages_listview.controls.append(
                            ft.Row([date_pill], alignment=ft.MainAxisAlignment.CENTER)
                        )
                        current_date_label = m_date

                    prev_item = clean_msgs[i - 1] if i > 0 else None
                    next_item = clean_msgs[i + 1] if i < len(clean_msgs) - 1 else None
                    messages_listview.controls.append(render_message_bubble(m, prev_msg=prev_item, next_msg=next_item))

                page.update()
                _scroll_to_bottom(animate=False)

            cached_history = get_cached_messages(page, chat_id)
            if cached_history:
                _render_history(cached_history)

            # --- 2. NETWORK FETCH & SQLITE REFRESH ---
            history = await get_channel_messages(token, chat_id)
            if isinstance(history, list):
                # Reverse to chronological order (API returns newest first)
                chronological = list(reversed(history))

                formatted_msgs = []
                for m in chronological:
                    sdata = m.get("sender") or {}
                    formatted_msgs.append({
                        "id": str(m.get("id")),
                        "channel_id": str(chat_id),
                        "sender_id": str(sdata.get("id", m.get("sender_id", ""))),
                        "sender_name": str(sdata.get("name") or "Unknown").strip() or "Unknown",
                        "type": m.get("type", "text"),
                        "content": m.get("content", ""),
                        "metadata_payload": json.dumps(m.get("metadata_payload")) if m.get("metadata_payload") else None,
                        "created_at": str(m.get("created_at", "")),
                        "status": "sent"
                    })

                if formatted_msgs:
                    upsert_chat_messages(page, formatted_msgs)

                _render_history(chronological)

            # Update Online Status in Header
            if len(active_chat_header.controls) >= 3:
                status_col = active_chat_header.controls[2]
                if len(status_col.controls) >= 2:
                    _is_online = chat_info.get("is_online", False)
                    _chat_type = chat_info.get("type", "direct")
                    if _chat_type == "direct":
                        status_col.controls[1].value = "online" if _is_online else "Offline"
                        status_col.controls[1].color = palette["online_dot"] if _is_online else palette["text_muted"]
                    else:
                        status_col.controls[1].value = ""
            page.update()

            # --- 3. CONNECT LIVE WEBSOCKET & EMIT READ RECEIPT ---
            ws_client_ref[0] = ChatWebSocketClient(token)
            connected = await ws_client_ref[0].connect(handle_incoming_message)
            if connected:
                # Mark room read on backend
                page.run_task(ws_client_ref[0].send_message, chat_id, "", "read_receipt")

        except Exception as ex:
            print(f"[NuChat] Error loading active chat {chat_id}: {ex}")
        finally:
            chat_load_lock[0] = False

    # ==========================================
    # 11. WEBSOCKET MESSAGE DISPATCHER
    # ==========================================
    def handle_incoming_message(msg_dict: dict):
        incoming_channel_id = msg_dict.get("channel_id")
        msg_type = msg_dict.get("type", "text")

        # ── Presence Updates ──────────────────────────────────────────────────
        if msg_type == "presence":
            is_online = msg_dict.get("is_online", False)
            for chat in channels_list:
                if chat.get("channel_id") == incoming_channel_id:
                    chat["is_online"] = is_online
                    break
            render_chat_list()

            if incoming_channel_id == current_chat_id[0] and len(active_chat_header.controls) >= 3:
                status_col = active_chat_header.controls[2]
                if len(status_col.controls) >= 2:
                    status_col.controls[1].value = "online" if is_online else "Offline"
                    status_col.controls[1].color = palette["online_dot"] if is_online else palette["text_muted"]
                    page.update()
            return

        # ── Typing Indicator ──────────────────────────────────────────────────
        if msg_type == "typing":
            sender_id = str((msg_dict.get("sender") or {}).get("id", "")).strip().lower()
            if sender_id != str(current_user_id[0]).strip().lower():
                show_typing_indicator(incoming_channel_id, (msg_dict.get("sender") or {}).get("name", "Someone"))
            return

        # ── Poll Update (Vote cast) ───────────────────────────────────────────
        if msg_type == "poll_update":
            poll_id = str(msg_dict.get("id", "")).strip().lower()
            incoming_cid = str(incoming_channel_id or "").strip().lower()
            curr_cid = str(current_chat_id[0] or "").strip().lower()
            if incoming_cid and curr_cid and incoming_cid == curr_cid:
                for idx, ctrl in enumerate(messages_listview.controls):
                    if hasattr(ctrl, "data") and str(ctrl.data).strip().lower() == poll_id:
                        messages_listview.controls[idx] = render_message_bubble(msg_dict)
                        page.update()
                        break
            try:
                upsert_chat_messages(page, [msg_dict])
            except Exception:
                pass
            return

        # ── Normal Message / Poll Creation ────────────────────────────────────
        msg_id = msg_dict.get("id")
        if not msg_id:
            return
        msg_id_str = str(msg_id)
        if msg_id_str in seen_msg_ids:
            return
        seen_msg_ids.add(msg_id_str)

        # Check if incoming message tagged the current user
        is_tagged_incoming = False
        meta_payload = msg_dict.get("metadata_payload") or msg_dict.get("metadata") or {}
        if isinstance(meta_payload, str):
            try: meta_payload = json.loads(meta_payload)
            except: meta_payload = {}
        msg_mentions = meta_payload.get("mentions", []) if isinstance(meta_payload, dict) else []
        msg_mention_ids = meta_payload.get("mention_ids", []) if isinstance(meta_payload, dict) else []
        msg_content = msg_dict.get("content", "") or ""
        all_mentions = set([str(m).lstrip("@").strip().lower() for m in msg_mentions] + [str(m).strip().lower() for m in re.findall(r'@([a-zA-Z0-9_.-]+)', msg_content)])
        all_ids = set([str(m).strip().lower() for m in msg_mention_ids])

        sender_id_str = str((msg_dict.get("sender") or {}).get("id") or msg_dict.get("sender_id", "")).strip().lower()
        if sender_id_str != current_user_id[0]:
            if current_user_id[0] in all_ids:
                is_tagged_incoming = True
            elif any(h in all_mentions for h in current_user_handles):
                is_tagged_incoming = True
            elif "all" in all_mentions:
                is_tagged_incoming = True
            elif "admin" in all_mentions:
                for ch in channels_list:
                    if ch.get("channel_id") == incoming_channel_id:
                        if ch.get("role") == "admin" or str(ch.get("created_by_id", "")).lower() == current_user_id[0]:
                            is_tagged_incoming = True
                        break

        # Update channels list order and unread counts
        for chat in channels_list:
            if chat.get("channel_id") == incoming_channel_id:
                if incoming_channel_id != current_chat_id[0]:
                    chat["unread"] = chat.get("unread", 0) + 1
                    if is_tagged_incoming:
                        chat["has_unread_mention"] = True
                chat["last_msg"] = msg_dict.get("content", "")
                chat["time"] = msg_dict.get("created_at", "")
                channels_list.remove(chat)
                channels_list.insert(0, chat)
                break

        if is_tagged_incoming and incoming_channel_id != current_chat_id[0]:
            try:
                s_name = (msg_dict.get("sender") or {}).get("name", "Someone")
                c_name = next((c.get("name") for c in channels_list if c.get("channel_id") == incoming_channel_id), "Group")
                NotificationManager.upsert(
                    notif_id=f"chat_tag_{msg_id_str}",
                    title=f"{s_name} tagged you in {c_name}",
                    body=msg_content[:120],
                    category="chat",
                    icon=ft.Icons.CHAT_BUBBLE_ROUNDED,
                    action_label="Open",
                    on_action=lambda e, cid=incoming_channel_id: page.go(f"/nu-chat?channel={cid}")
                )
                page.run_task(sync_learner_notifications, page, True)
            except Exception:
                pass

        render_chat_list()

        # Append to active room if viewing
        if incoming_channel_id == current_chat_id[0]:
            prev_ctrl = None
            if messages_listview.controls:
                last_ctrl = messages_listview.controls[-1]
                if hasattr(last_ctrl, "data"):
                    prev_ctrl = {"sender_id": msg_dict.get("sender_id"), "created_at": msg_dict.get("created_at")}

            bubble_w = render_message_bubble(msg_dict, prev_msg=prev_ctrl)
            messages_listview.controls.append(bubble_w)
            page.update()
            _scroll_to_bottom(animate=True)

            # Mark read immediately since user is actively in room
            if ws_client_ref[0]:
                page.run_task(ws_client_ref[0].send_message, incoming_channel_id, "", "read_receipt")

    # ==========================================
    # 12. COMPOSER ACTIONS & MODALS HELPER
    # ==========================================
    def _open_modal(control):
        try:
            if hasattr(page, "show_dialog"):
                page.show_dialog(control)
                return
        except Exception:
            pass
        if hasattr(page, "overlay"):
            if control not in page.overlay:
                page.overlay.append(control)
        control.open = True
        try:
            control.update()
        except Exception:
            page.update()

    def _close_modal(control=None):
        try:
            if hasattr(page, "pop_dialog"):
                popped = page.pop_dialog()
                if popped:
                    return
        except Exception:
            pass
        if control:
            control.open = False
            try:
                control.update()
            except Exception:
                page.update()

    def open_attachment_actions_modal(e=None):
        def _launch_poll_creator(ev):
            _close_modal(action_dlg)
            open_poll_modal()

        action_dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=16),
            bgcolor=palette["surface"],
            title=ft.Row([
                ft.Row([
                    ft.Icon(ft.Icons.ADD_CIRCLE_ROUNDED, color=palette["accent"], size=22),
                    ft.Text("Chat Actions", weight=ft.FontWeight.BOLD, size=16, color=palette["text"]),
                ], spacing=8),
                ft.IconButton(
                    icon=ft.Icons.CLOSE_ROUNDED,
                    icon_size=18,
                    icon_color=palette["text_muted"],
                    on_click=lambda _: _close_modal(action_dlg)
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            content=ft.Container(
                width=340,
                content=ft.Column([
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.POLL_ROUNDED, color=palette["accent"]),
                        title=ft.Text("Create In-Chat Poll", weight=ft.FontWeight.W_600, color=palette["text"]),
                        subtitle=ft.Text("Ask peers a question and collect instant live votes", size=12, color=palette["text_muted"]),
                        on_click=_launch_poll_creator
                    ),
                ], tight=True, spacing=4)
            )
        )
        _open_modal(action_dlg)

    # ── Poll Creator Dialog ───────────────────────────────────────────────────
    def open_poll_modal():
        q_input = ft.TextField(
            label="Poll Question *",
            hint_text="e.g., Which framework should we use?",
            border_radius=8,
            bgcolor=palette["input_bg"],
            border_color=palette["border"],
            focused_border_color=palette["accent"],
            text_size=13,
            text_style=ft.TextStyle(color=palette["text"], size=13),
            hint_style=ft.TextStyle(color=palette["text_muted"], size=13)
        )
        opt_1 = ft.TextField(
            label="Option 1 *",
            hint_text="e.g., FastAPI + Flet",
            border_radius=8,
            bgcolor=palette["input_bg"],
            border_color=palette["border"],
            focused_border_color=palette["accent"],
            text_size=13,
            text_style=ft.TextStyle(color=palette["text"], size=13),
            hint_style=ft.TextStyle(color=palette["text_muted"], size=13)
        )
        opt_2 = ft.TextField(
            label="Option 2 *",
            hint_text="e.g., Django + React",
            border_radius=8,
            bgcolor=palette["input_bg"],
            border_color=palette["border"],
            focused_border_color=palette["accent"],
            text_size=13,
            text_style=ft.TextStyle(color=palette["text"], size=13),
            hint_style=ft.TextStyle(color=palette["text_muted"], size=13)
        )
        opt_3 = ft.TextField(
            label="Option 3 (Optional)",
            border_radius=8,
            bgcolor=palette["input_bg"],
            border_color=palette["border"],
            focused_border_color=palette["accent"],
            text_size=13,
            text_style=ft.TextStyle(color=palette["text"], size=13),
            hint_style=ft.TextStyle(color=palette["text_muted"], size=13)
        )
        opt_4 = ft.TextField(
            label="Option 4 (Optional)",
            border_radius=8,
            bgcolor=palette["input_bg"],
            border_color=palette["border"],
            focused_border_color=palette["accent"],
            text_size=13,
            text_style=ft.TextStyle(color=palette["text"], size=13),
            hint_style=ft.TextStyle(color=palette["text_muted"], size=13)
        )

        multi_switch = ft.Switch(
            label="Allow multiple answers",
            value=False,
            active_color=palette["accent"]
        )

        async def _submit_poll(ev):
            question = (q_input.value or "").strip()
            o1 = (opt_1.value or "").strip()
            o2 = (opt_2.value or "").strip()
            o3 = (opt_3.value or "").strip()
            o4 = (opt_4.value or "").strip()
            if not question or not o1 or not o2:
                show_page_snackbar(page, ft.SnackBar(content=ft.Text("Please enter a question and at least 2 options."), bgcolor=ft.Colors.AMBER_800))
                return

            opts = [o1, o2]
            if o3:
                opts.append(o3)
            if o4:
                opts.append(o4)

            if not ws_client_ref[0] or not current_chat_id[0]:
                show_page_snackbar(page, ft.SnackBar(content=ft.Text("Not connected to active chat room."), bgcolor=ft.Colors.RED_700))
                return

            meta = {"question": question, "options": opts, "votes": {}, "is_multi_select": bool(multi_switch.value)}
            success = await ws_client_ref[0].send_message(
                current_chat_id[0],
                question,
                "poll",
                metadata_payload=meta
            )
            if success:
                _close_modal(dlg)
            else:
                show_page_snackbar(page, ft.SnackBar(content=ft.Text("Failed to send poll. Connection lost."), bgcolor=ft.Colors.RED_700))

        dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=14),
            bgcolor=palette["surface"],
            title=ft.Row([
                ft.Icon(ft.Icons.POLL_ROUNDED, color=palette["accent"], size=20),
                ft.Text("Launch In-Chat Poll", weight=ft.FontWeight.BOLD, size=16, color=palette["text"])
            ], spacing=8),
            content=ft.Container(
                width=340,
                content=ft.Column([q_input, opt_1, opt_2, opt_3, opt_4, multi_switch], spacing=10, tight=True)
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: _close_modal(dlg)),
                ft.FilledButton(
                    "Post Poll",
                    style=ft.ButtonStyle(
                        bgcolor=palette["accent_glow"],
                        color=ft.Colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=8)
                    ),
                    on_click=lambda ev: page.run_task(_submit_poll, ev)
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        _open_modal(dlg)

    # ── Poll Voter Breakdown Dialog ──────────────────────────────────────────
    def open_poll_breakdown_modal(poll_msg: dict):
        p_meta = poll_msg.get("metadata_payload") or poll_msg.get("metadata") or {}
        if isinstance(p_meta, str):
            try:
                p_meta = json.loads(p_meta)
            except Exception:
                p_meta = {}
        p_question = p_meta.get("question") or poll_msg.get("content") or "Poll Results"
        p_opts = p_meta.get("options") or []
        p_votes = p_meta.get("votes") or {}
        if isinstance(p_votes, str):
            try:
                p_votes = json.loads(p_votes)
            except Exception:
                p_votes = {}
        if not isinstance(p_votes, dict):
            p_votes = {}

        my_id = str(current_user_id[0]).strip().lower()

        breakdown_rows = []
        for opt in p_opts:
            opt_str = str(opt).strip()
            voters = []
            for u_id, u_v in p_votes.items():
                sel = u_v if isinstance(u_v, list) else [u_v]
                if any(str(v).strip().lower() == opt_str.lower() for v in sel):
                    voters.append(str(u_id).strip().lower())

            voter_tiles = []
            if voters:
                for v_id in voters:
                    v_name = "User"
                    if v_id == my_id:
                        v_name = "You"
                    else:
                        for u in all_users_cache:
                            if str(u.get("id") or u.get("user_id", "")).strip().lower() == v_id:
                                v_name = (u.get("name") or u.get("full_name") or u.get("username") or "User").strip()
                                break

                    def _nav_to_voter(ev, uid=v_id):
                        _close_modal(dlg)
                        if uid == my_id:
                            page.go("/profile")
                        else:
                            page.go(f"/member/{uid}")

                    voter_tiles.append(
                        ft.Container(
                            ink=True,
                            border_radius=8,
                            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                            on_click=_nav_to_voter,
                            tooltip=f"View {v_name}'s profile",
                            content=ft.Row([
                                get_avatar(v_name, "direct", is_online=False, radius=13),
                                ft.Text(
                                    v_name,
                                    size=13,
                                    weight=ft.FontWeight.W_600 if v_id == my_id else ft.FontWeight.NORMAL,
                                    color=palette["accent"] if v_id == my_id else palette["text"]
                                )
                            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)
                        )
                    )
            else:
                voter_tiles.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                        content=ft.Text("No votes yet", size=12, italic=True, color=palette["text_muted"])
                    )
                )

            breakdown_rows.append(
                ft.Container(
                    bgcolor=palette["surface_variant"],
                    border_radius=8,
                    padding=10,
                    content=ft.Column([
                        ft.Row([
                            ft.Text(opt_str, size=13, weight=ft.FontWeight.BOLD, color=palette["text"], expand=True),
                            ft.Container(
                                bgcolor=palette["accent_glow"],
                                border_radius=10,
                                padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                                content=ft.Text(
                                    f"{len(voters)} vote{'s' if len(voters) != 1 else ''}",
                                    size=11,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.WHITE
                                )
                            )
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Container(height=4),
                        *voter_tiles
                    ], spacing=2, tight=True)
                )
            )

        dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=16),
            bgcolor=palette["surface"],
            title=ft.Row([
                ft.Icon(ft.Icons.HOW_TO_VOTE_ROUNDED, color=palette["accent"], size=22),
                ft.Text("Poll Votes", weight=ft.FontWeight.BOLD, size=16, color=palette["text"]),
            ], spacing=8),
            content=ft.Container(
                width=360,
                content=ft.Column([
                    ft.Text(p_question, size=14, weight=ft.FontWeight.W_600, color=palette["text"]),
                    ft.Text(f"Total: {len(p_votes)} voter{'s' if len(p_votes) != 1 else ''}", size=12, color=palette["text_muted"]),
                    ft.Divider(height=1, color=palette["border"]),
                    ft.Container(
                        height=280,
                        content=ft.ListView(controls=breakdown_rows, spacing=8)
                    )
                ], spacing=8, tight=True)
            ),
            actions=[
                ft.TextButton("Close", on_click=lambda _: _close_modal(dlg))
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        _open_modal(dlg)


    # ==========================================
    # 13. USER PICKER, GROUPS & MODALS
    # ==========================================
    async def _load_users_if_needed():
        nonlocal all_users_cache
        if not all_users_cache:
            res = await get_all_users(token)
            if isinstance(res, list):
                all_users_cache = res

    # ── User Picker (Direct Message) ──────────────────────────────────────────
    def open_users_modal(e):
        user_search = ft.TextField(
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            hint_text="Search members...",
            border_radius=8,
            filled=True,
            bgcolor=palette["input_bg"],
            border_color=ft.Colors.TRANSPARENT,
            focused_border_color=palette["accent"],
            content_padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            text_size=13,
            text_style=ft.TextStyle(color=palette["text"], size=13),
            hint_style=ft.TextStyle(color=palette["text_muted"], size=13)
        )
        user_list_col = ft.Column(tight=True, scroll=ft.ScrollMode.AUTO, spacing=2)
        loading_ring = ft.Row([ft.ProgressRing(color=palette["accent"], width=22, height=22, stroke_width=2)], alignment=ft.MainAxisAlignment.CENTER)

        def _render_user_tiles(query=""):
            q = query.lower().strip()
            user_list_col.controls.clear()
            filtered = [
                u for u in all_users_cache
                if q in (u.get("name") or u.get("full_name") or u.get("username") or "").lower()
            ] if q else all_users_cache

            if not filtered:
                user_list_col.controls.append(
                    ft.Container(
                        padding=20, alignment=ft.Alignment.CENTER,
                        content=ft.Text("No members found.", color=palette["text_muted"], size=13)
                    )
                )
            else:
                for idx, u in enumerate(filtered):
                    dname = u.get("name") or u.get("full_name") or u.get("username") or "User"
                    uid = u.get("id") or u.get("user_id")

                    tile = ft.Container(
                        ink=True,
                        border_radius=8,
                        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                        on_click=lambda e, fid=uid: handle_user_dm(fid, dlg),
                        content=ft.Row([
                            get_avatar(dname, "direct", is_online=False, radius=18, avatar_url=u.get("profile_picture_url")),
                            ft.Container(width=10),
                            ft.Column([
                                ft.Text(dname, weight=ft.FontWeight.W_600, size=13, color=palette["text"]),
                                ft.Text(u.get("email", ""), size=11, color=palette["text_muted"])
                            ], spacing=1, tight=True, expand=True)
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)
                    )
                    user_list_col.controls.append(tile)
            page.update()

        user_search.on_change = lambda e: _render_user_tiles(e.control.value)

        dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=14),
            bgcolor=palette["surface"],
            title=ft.Text("New Direct Message", weight=ft.FontWeight.BOLD, size=16, color=palette["text"]),
            content=ft.Container(
                width=360,
                height=380,
                content=ft.Column([
                    user_search,
                    loading_ring,
                    ft.Container(expand=True, content=ft.ListView(controls=[user_list_col], expand=True, spacing=0))
                ], spacing=8, tight=True)
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: _close_modal(dlg))
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        _open_modal(dlg)

        async def _boot():
            await _load_users_if_needed()
            loading_ring.visible = False
            _render_user_tiles()
        page.run_task(_boot)

    def handle_user_dm(target_id: str, dlg: ft.AlertDialog):
        _close_modal(dlg)

        async def init_dm():
            res = await start_direct_message(token, str(target_id))
            if res and "error" not in res:
                await fetch_initial_data()
                channel_id = res.get("channel_id")
                if channel_id:
                    await load_active_chat(channel_id)

        page.run_task(init_dm)

    # ── Create Group Modal ────────────────────────────────────────────────────
    def open_create_channel_modal(e):
        name_input = ft.TextField(
            label="Group Name *",
            border_radius=8,
            bgcolor=palette["input_bg"],
            border_color=palette["border"],
            focused_border_color=palette["accent"],
            text_size=13,
            text_style=ft.TextStyle(color=palette["text"], size=13)
        )
        users_listview = ft.ListView(expand=True, spacing=0)
        checkboxes = []

        async def _load_group_picker():
            await _load_users_if_needed()
            if all_users_cache:
                for u in all_users_cache:
                    dname = u.get("name") or u.get("full_name") or u.get("username") or "User"
                    uid = u.get("id") or u.get("user_id")
                    if str(uid).strip().lower() != current_user_id[0]:
                        cb = ft.Checkbox(data=str(uid), fill_color=palette["accent"])
                        checkboxes.append(cb)

                        def toggle_row(e, checkbox=cb):
                            checkbox.value = not checkbox.value
                            page.update()

                        row = ft.Container(
                            ink=True,
                            on_click=toggle_row,
                            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                            content=ft.Row([
                                get_avatar(dname, "direct", radius=16, avatar_url=u.get("profile_picture_url")),
                                ft.Container(width=8),
                                ft.Text(dname, size=13, weight=ft.FontWeight.W_500, color=palette["text"], expand=True),
                                cb
                            ], vertical_alignment=ft.CrossAxisAlignment.CENTER)
                        )
                        users_listview.controls.append(row)
            page.update()

        async def handle_create(ev):
            group_name = (name_input.value or "").strip()
            if not group_name:
                name_input.error_text = "Group name is required."
                page.update()
                return

            selected_ids = [cb.data for cb in checkboxes if cb.value]
            try:
                res = await create_group_channel(
                    token=token,
                    name=group_name,
                    channel_type="custom",
                    org_id=None,
                    member_ids=selected_ids
                )
                if res and "error" not in res:
                    _close_modal(dialog)
                    await fetch_initial_data()
                    cid = res.get("channel_id")
                    if cid:
                        await load_active_chat(cid)
            except Exception as ex:
                show_page_snackbar(page, ft.SnackBar(content=ft.Text(f"Failed to create group: {ex}"), bgcolor=ft.Colors.RED_800))

        dialog = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=14),
            bgcolor=palette["surface"],
            title=ft.Row([
                ft.Icon(ft.Icons.GROUPS_ROUNDED, color=palette["accent"], size=20),
                ft.Text("New Group Chat", weight=ft.FontWeight.BOLD, size=16, color=palette["text"])
            ], spacing=8),
            content=ft.Container(
                width=360,
                height=360,
                content=ft.Column([
                    name_input,
                    ft.Text("Select participants:", size=12, color=palette["text_muted"], weight=ft.FontWeight.W_600),
                    ft.Container(expand=True, border=ft.Border.all(1, palette["border"]), border_radius=8, content=users_listview)
                ], spacing=8, tight=True)
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: _close_modal(dialog)),
                ft.FilledButton("Create Group", style=ft.ButtonStyle(bgcolor=palette["accent_glow"], color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=8)), on_click=handle_create)
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        _open_modal(dialog)
        page.run_task(_load_group_picker)

    # ── Add Members Modal ─────────────────────────────────────────────────────
    def open_add_member_modal(channel_id: str):
        users_listview = ft.ListView(expand=True, spacing=0)
        checkboxes = []

        async def _load_candidates():
            await _load_users_if_needed()
            existing = await get_group_members(token, channel_id)
            for u in all_users_cache:
                uid = str(u.get("id") or u.get("user_id")).strip()
                if uid not in existing:
                    dname = u.get("name") or u.get("full_name") or u.get("username") or "User"
                    cb = ft.Checkbox(data=uid, fill_color=palette["accent"])
                    checkboxes.append(cb)

                    def toggle_row(e, checkbox=cb):
                        checkbox.value = not checkbox.value
                        page.update()

                    row = ft.Container(
                        ink=True,
                        on_click=toggle_row,
                        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                        content=ft.Row([
                            get_avatar(dname, "direct", radius=16, avatar_url=u.get("profile_picture_url")),
                            ft.Container(width=8),
                            ft.Text(dname, size=13, weight=ft.FontWeight.W_500, color=palette["text"], expand=True),
                            cb
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)
                    )
                    users_listview.controls.append(row)
            if not users_listview.controls:
                users_listview.controls.append(
                    ft.Container(padding=20, alignment=ft.Alignment.CENTER, content=ft.Text("All available members are in this chat.", size=12, color=palette["text_muted"]))
                )
            page.update()

        async def _handle_add(ev):
            selected = [cb.data for cb in checkboxes if cb.value]
            if not selected:
                return
            await add_group_members(token, channel_id, selected)
            _close_modal(dlg)
            show_page_snackbar(page, ft.SnackBar(content=ft.Text(f"Added {len(selected)} members to group."), bgcolor=palette["accent_glow"]))

        dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=14),
            bgcolor=palette["surface"],
            title=ft.Text("Add Members", weight=ft.FontWeight.BOLD, size=16, color=palette["text"]),
            content=ft.Container(
                width=340,
                height=320,
                content=ft.Container(expand=True, border=ft.Border.all(1, palette["border"]), border_radius=8, content=users_listview)
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: _close_modal(dlg)),
                ft.FilledButton("Add to Group", style=ft.ButtonStyle(bgcolor=palette["accent_glow"], color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=8)), on_click=_handle_add)
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        _open_modal(dlg)
        page.run_task(_load_candidates)

    # ── Leave Group Modal ─────────────────────────────────────────────────────
    def confirm_leave_group(channel_id: str, group_name: str):
        c_info = next((c for c in channels_list if c.get("channel_id") == channel_id), {})
        is_course = bool(c_info.get("course_id") or c_info.get("type") == "course")

        if is_course:
            dlg = ft.AlertDialog(
                modal=True,
                shape=ft.RoundedRectangleBorder(radius=14),
                bgcolor=palette["surface"],
                title=ft.Row([
                    ft.Icon(ft.Icons.SCHOOL_ROUNDED, color=ft.Colors.AMBER_500, size=22),
                    ft.Text("Course Group", weight=ft.FontWeight.BOLD, size=16, color=palette["text"])
                ], spacing=8),
                content=ft.Text(
                    f"'{group_name}' is a course discussion group.\n\nYou cannot leave this group directly while enrolled in the course. To leave, please unenroll from the course in your Course Settings.",
                    size=13,
                    color=palette["text_muted"]
                ),
                actions=[
                    ft.FilledButton(
                        "Understood",
                        style=ft.ButtonStyle(bgcolor=palette["accent_glow"], color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=8)),
                        on_click=lambda _: _close_modal(dlg)
                    )
                ],
                actions_alignment=ft.MainAxisAlignment.END
            )
            _open_modal(dlg)
            return

        async def _execute_leave(ev):
            nonlocal channels_list
            if ws_client_ref[0]:
                await ws_client_ref[0].send_message(channel_id, "A member has left the chat.", "system")
                await asyncio.sleep(0.1)

            try:
                res = await leave_group_channel(token, channel_id)
                if isinstance(res, dict) and "error" in res:
                    show_page_snackbar(page, ft.SnackBar(content=ft.Text(res["error"]), bgcolor=ft.Colors.RED_800))
                    _close_modal(dlg)
                    return
            except Exception as ex:
                show_page_snackbar(page, ft.SnackBar(content=ft.Text(f"Failed to leave: {ex}"), bgcolor=ft.Colors.RED_800))
                _close_modal(dlg)
                return

            channels_list = [c for c in channels_list if c.get("channel_id") != channel_id]
            _close_modal(dlg)
            await close_chat_mobile()

        dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=14),
            bgcolor=palette["surface"],
            title=ft.Text(f"Leave '{group_name}'?", weight=ft.FontWeight.BOLD, size=16, color=palette["text"]),
            content=ft.Text("You will no longer receive messages from this group.", size=13, color=palette["text_muted"]),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: _close_modal(dlg)),
                ft.FilledButton("Leave Group", style=ft.ButtonStyle(bgcolor=ft.Colors.RED_700, color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=8)), on_click=_execute_leave)
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        _open_modal(dlg)

    # ── Delete Conversation Modal ─────────────────────────────────────────────
    def open_delete_modal(chat_id: str, chat_name: str):
        async def _execute_delete(ev):
            nonlocal channels_list
            await delete_chat_channel(token, chat_id)
            channels_list = [c for c in channels_list if c.get("channel_id") != chat_id]
            _close_modal(dlg)
            if current_chat_id[0] == chat_id:
                await close_chat_mobile()
            else:
                render_chat_list()

        dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=14),
            bgcolor=palette["surface"],
            title=ft.Text(f"Delete '{chat_name}'?", weight=ft.FontWeight.BOLD, size=16, color=palette["text"]),
            content=ft.Text("This will permanently remove this chat from your history.", size=13, color=palette["text_muted"]),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: _close_modal(dlg)),
                ft.FilledButton("Delete", style=ft.ButtonStyle(bgcolor=ft.Colors.RED_700, color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=8)), on_click=_execute_delete)
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        _open_modal(dlg)

    # ==========================================
    # 14. LIFECYCLE & DEEP LINK HANDLING
    # ==========================================
    async def fetch_initial_data():
        nonlocal channels_list, target_dm_user_id, target_channel_id
        try:
            udata = await get_current_user_request(token)
            if isinstance(udata, tuple) and len(udata) > 1:
                udata = udata[1]
            uid = udata.get("id") or udata.get("user_id") if isinstance(udata, dict) else None
            if uid:
                current_user_id[0] = str(uid).strip().lower()
                current_user_handles.add(current_user_id[0])
                await page.shared_preferences.set("user_id", current_user_id[0])
            if isinstance(udata, dict):
                un = udata.get("username")
                if un: current_user_handles.add(str(un).strip().lower())
                fn = udata.get("first_name")
                if fn: current_user_handles.add(str(fn).strip().lower())
                ln = udata.get("last_name")
                if ln: current_user_handles.add(str(ln).strip().lower())
                nm = udata.get("name") or udata.get("full_name")
                if nm:
                    current_user_handles.add(str(nm).strip().lower())
                    current_user_handles.add(str(nm).strip().lower().replace(" ", "_"))
        except Exception:
            pass

        # Pre-warm member directory cache for instantaneous @ autocomplete
        page.run_task(_load_users_if_needed)

        # Load cached channels first for instant cold start
        cached = get_cached_chat_channels(page)
        if cached:
            normalized_cached = []
            for ch in cached:
                item = dict(ch)
                if not item.get("channel_id") and item.get("id"):
                    item["channel_id"] = item["id"]
                if not item.get("last_msg") and item.get("last_message_snippet"):
                    item["last_msg"] = item["last_message_snippet"]
                normalized_cached.append(item)
            channels_list = normalized_cached
            is_loading_channels[0] = False
            render_chat_list()

        # Network sync
        try:
            res = await get_user_channels(token)
            if isinstance(res, list):
                for ch in res:
                    if not ch.get("channel_id") and ch.get("id"):
                        ch["channel_id"] = ch["id"]
                channels_list = res
        finally:
            is_loading_channels[0] = False
            render_chat_list()

        # Handle Deep Link Handoff: ?dm=<user_id>
        if target_dm_user_id:
            dm_target = target_dm_user_id
            target_dm_user_id = None
            res_dm = await start_direct_message(token, str(dm_target))
            if res_dm and "error" not in res_dm:
                cid = res_dm.get("channel_id")
                if cid:
                    refreshed = await get_user_channels(token)
                    if isinstance(refreshed, list):
                        channels_list = refreshed
                        render_chat_list()
                    await load_active_chat(cid)
                    return

        # Handle Deep Link Handoff: ?channel=<id>
        if target_channel_id:
            c_target = target_channel_id
            target_channel_id = None
            await load_active_chat(c_target)

    async def close_chat_mobile():
        if ws_client_ref[0]:
            await ws_client_ref[0].disconnect()
            ws_client_ref[0] = None
        current_chat_id[0] = None
        render_chat_list()
        update_responsive_layout()
        page.update()

    def build_empty_state():
        return ft.Container(
            expand=True,
            bgcolor=palette["chat_wall"],
            content=ft.Column([
                ft.Icon(ft.Icons.FORUM_OUTLINED, size=64, color=palette["text_muted"]),
                ft.Container(height=8),
                ft.Text("Nu Chat", size=22, weight=ft.FontWeight.BOLD, color=palette["text"]),
                ft.Text("Select a conversation from the left to start messaging.", size=13, color=palette["text_muted"]),
                ft.Container(height=12),
                ft.Row([
                    ft.Icon(ft.Icons.LOCK_OUTLINE_ROUNDED, size=13, color=palette["text_muted"]),
                    ft.Text("End-to-end encrypted messaging inside Nu-Age.", size=11, color=palette["text_muted"])
                ], spacing=6, alignment=ft.MainAxisAlignment.CENTER)
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        )

    def update_responsive_layout(e=None):
        is_desktop[0] = page.width >= DESKTOP_BREAKPOINT if hasattr(page, "width") and page.width else False
        messages_listview.padding = ft.Padding.symmetric(horizontal=8 if not is_desktop[0] else 12, vertical=8 if not is_desktop[0] else 10)
        if is_desktop[0]:
            chat_list_panel.visible = True
            active_chat_panel.visible = True
            chat_list_panel.expand = 1
            active_chat_panel.expand = 2
            if not current_chat_id[0]:
                active_chat_panel.content = build_empty_state()
            if active_chat_header.controls:
                active_chat_header.controls[0].visible = False
        else:
            chat_list_panel.expand = True
            active_chat_panel.expand = True
            if current_chat_id[0]:
                chat_list_panel.visible = False
                active_chat_panel.visible = True
                if active_chat_header.controls:
                    active_chat_header.controls[0].visible = True
            else:
                chat_list_panel.visible = True
                active_chat_panel.visible = False
        page.update()

    # Initial Setup
    render_chat_list()
    active_chat_panel.content = build_empty_state()
    page.on_resize = update_responsive_layout
    update_responsive_layout()
    page.run_task(fetch_initial_data)

    return ft.View(
        route="/nu-chat",
        padding=0,
        bgcolor=palette["chat_wall"],
        bottom_appbar=get_bottom_appbar(page),
        controls=[
            ft.SafeArea(
                expand=True,
                content=ft.Row([chat_list_panel, active_chat_panel], spacing=0, expand=True)
            )
        ]
    )