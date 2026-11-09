import flet as ft
from datetime import datetime, timezone
import asyncio
import json
import re
import uuid
from typing import Optional, List, Dict, Any

# ==========================================
# BACKEND & UTILITY IMPORTS
# ==========================================
from src.components.bottom_appbar import get_bottom_appbar
from src.requests.auth import get_current_user_request
from src.requests.chats import (
    get_user_channels,
    get_channel_messages,
    send_channel_message_api,
    create_group_channel,
    start_direct_message,
    get_all_users,
    ChatWebSocketClient,
    add_group_members,
    get_group_members,
    delete_chat_channel,
    leave_group_channel,
    delete_channel_message_api,
    vote_poll_message_api
)
from src.local_db import (
    get_cached_chat_channels,
    upsert_chat_channels,
    get_cached_messages,
    upsert_chat_messages,
    mark_cached_message_deleted
)
from src.components.notifications_drawer import NotificationManager
from src.services.notification_service import sync_learner_notifications
from src.utils.file_opener import (
    show_page_snackbar,
    safe_set_clipboard,
    safe_open_dialog,
    safe_close_dialog,
    is_modal_open,
    debounced_click,
)
from src.components.shimmer_skeletons import shimmer_box, collect_shimmer_boxes
from src.components.badge_pill import build_glossy_badge_pill
from src.components.chat_reply_bar import build_chat_reply_bar
from src.components.chat_reactions import build_reaction_pills_row
from src.components.chat_attachment_sheet import open_chat_actions_sheet
from src.components.chat_quota_modal import open_chat_quota_modal
from src.components.chat_message_actions import open_message_actions_sheet
from src.requests.chats import get_pinned_chat_message
from src.utils.theme_bridge import get_theme_palette, THEME_PALETTES

_WHATSAPP_PATTERN = re.compile(
    r'(\[[^\]]+\]\(https?://[^\s\)]+\))|'
    r'(https?://[^\s]+)|'
    r'((?<!\w)@[\w.-]+)|'
    r'(\*\*[^\*\n]+\*\*)|'
    r'(__[^_\n]+__)|'
    r'(\*[^\*\n]+\*)|'
    r'(_[^_\n]+_)|'
    r'(~~[^~\n]+~~|~[^~\n]+~)|'
    r'(`[^`\n]+`)'
)

_BLOCK_MD_PATTERN = re.compile(
    r"(^#{1,6}\s+)|"
    r"(^\s*[-*+]\s+)|"
    r"(^\s*\d+\.\s+)|"
    r"(^\s*>\s+)|"
    r"(```)|"
    r"(^\s*\|.+\|\s*$)|"
    r"(^\s*(?:---|\*\*\*|___)\s*$)",
    re.MULTILINE,
)

_MENTION_OUTSIDE_CODE_RE = re.compile(r"(`+[^`]*`+)|((?<!\w)@[\w.-]+)")


def _unfreeze_control(ctrl: Any) -> Any:
    """Safely clears Flet 1.1.2 _frozen marker so dynamic controls can be mutated."""
    if ctrl is None:
        return ctrl
    if hasattr(ctrl, "_frozen"):
        try:
            del ctrl._frozen
        except Exception:
            try:
                object.__delattr__(ctrl, "_frozen")
            except Exception:
                pass
    if hasattr(ctrl, "content") and ctrl.content is not None:
        _unfreeze_control(ctrl.content)
    if hasattr(ctrl, "controls") and isinstance(ctrl.controls, list):
        for ch in ctrl.controls:
            _unfreeze_control(ch)
    return ctrl


def has_block_markdown(text: str) -> bool:
    """Detects whether a chat message uses block-level or multi-line Markdown syntax."""
    if not text:
        return False
    if "```" in text:
        return True
    if any(tok in text for tok in ("#", "- ", "* ", "+ ", "> ", "|", "1. ", "2. ", "---")):
        return bool(_BLOCK_MD_PATTERN.search(text))
    return False


def _inject_markdown_mentions(text: str) -> str:
    """Converts @username mentions outside code spans into clickable Markdown links."""
    if "@" not in text:
        return text

    def _repl(m: re.Match) -> str:
        if m.group(1):
            return m.group(1)
        uname = m.group(2)
        return f"[**{uname}**](mention:{uname})"

    return _MENTION_OUTSIDE_CODE_RE.sub(_repl, text)


def build_chat_markdown(
    text: str,
    default_color: str,
    palette_map: dict,
    on_mention_click=None,
    is_me: bool = False,
    page: Optional[ft.Page] = None,
) -> ft.Control:
    """Renders a chat message bubble with full GitHub-flavored Markdown, themed code blocks, and clickable @mentions."""
    link_col = palette_map.get("bubble_out_link", "#C8E6C9") if is_me else palette_map.get("accent", "#4CAF50")
    code_col = "#E8F5E9" if is_me else palette_map.get("code_text", default_color)
    code_span_bg = (
        ft.Colors.with_opacity(0.22, ft.Colors.BLACK)
        if is_me
        else palette_map.get("code_bg", ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE))
    )
    quote_bg = (
        ft.Colors.with_opacity(0.16, ft.Colors.BLACK)
        if is_me
        else ft.Colors.with_opacity(0.08, palette_map.get("accent", "#4CAF50"))
    )

    md_text = _inject_markdown_mentions(text)

    def _on_tap_link(e):
        url = (getattr(e, "data", None) or "").strip()
        if not url:
            return
        if url.startswith("mention:"):
            uname = url[len("mention:") :]
            if on_mention_click:
                on_mention_click(uname)
            return
        if page and hasattr(page, "launch_url"):
            try:
                res = page.launch_url(url)
                if asyncio.iscoroutine(res):
                    page.run_task(page.launch_url, url)
            except Exception:
                pass

    style_sheet = ft.MarkdownStyleSheet(
        p_text_style=ft.TextStyle(color=default_color, size=14),
        h1_text_style=ft.TextStyle(color=default_color, size=18, weight=ft.FontWeight.BOLD),
        h2_text_style=ft.TextStyle(color=default_color, size=16.5, weight=ft.FontWeight.BOLD),
        h3_text_style=ft.TextStyle(color=default_color, size=15, weight=ft.FontWeight.BOLD),
        h4_text_style=ft.TextStyle(color=default_color, size=14, weight=ft.FontWeight.BOLD),
        strong_text_style=ft.TextStyle(color=default_color, size=14, weight=ft.FontWeight.BOLD),
        em_text_style=ft.TextStyle(color=default_color, size=14, italic=True),
        del_text_style=ft.TextStyle(color=default_color, size=14, decoration=ft.TextDecoration.LINE_THROUGH),
        a_text_style=ft.TextStyle(
            color=link_col,
            size=14,
            weight=ft.FontWeight.W_600,
            decoration=ft.TextDecoration.UNDERLINE,
        ),
        list_bullet_text_style=ft.TextStyle(color=default_color, size=14),
        table_head_text_style=ft.TextStyle(color=default_color, size=13, weight=ft.FontWeight.BOLD),
        table_body_text_style=ft.TextStyle(color=default_color, size=13),
        code_text_style=ft.TextStyle(
            color=code_col,
            bgcolor=code_span_bg,
            font_family="monospace",
            size=12.5,
        ),
        blockquote_text_style=ft.TextStyle(color=default_color, size=13.5, italic=True),
        blockquote_padding=ft.Padding.symmetric(horizontal=10, vertical=6),
        blockquote_decoration=ft.BoxDecoration(
            bgcolor=quote_bg,
            border_radius=6,
            border=ft.Border.only(left=ft.BorderSide(3, link_col)),
        ),
        codeblock_padding=ft.Padding.all(10),
        codeblock_decoration=ft.BoxDecoration(
            bgcolor=palette_map.get("code_bg", "#161616"),
            border_radius=8,
            border=ft.Border.all(1, palette_map.get("code_border", "#2C2C2C")),
        ),
    )

    md_ctrl = ft.Markdown(
        value=md_text,
        selectable=True,
        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
        code_theme=ft.MarkdownCodeTheme.ATOM_ONE_DARK,
        md_style_sheet=style_sheet,
        auto_follow_links=False,
        on_tap_link=_on_tap_link,
    )
    return ft.SelectionArea(content=md_ctrl)


def build_whatsapp_spans(text: str, default_color: str, palette_map: dict, on_mention_click=None, is_me: bool = False):
    if not text:
        return [ft.TextSpan("")]

    # Blazing fast-path for plain text without markdown or mentions (avoids regex overhead for ~90% of messages)
    if not any(c in text for c in ("http", "@", "*", "_", "~", "`", "[")):
        return [ft.TextSpan(text, style=ft.TextStyle(color=default_color, size=14))]

    spans = []
    last_idx = 0
    for match in _WHATSAPP_PATTERN.finditer(text):
        start, end = match.span()
        if start > last_idx:
            spans.append(ft.TextSpan(text[last_idx:start], style=ft.TextStyle(color=default_color, size=14)))

        m_str = match.group(0)
        if match.group(1):  # Markdown Link [label](url)
            close_bracket = m_str.find("](")
            label = m_str[1:close_bracket]
            url = m_str[close_bracket + 2 : -1]
            link_col = palette_map.get("bubble_out_link", "#C8E6C9") if is_me else palette_map.get("accent", "#4CAF50")
            spans.append(
                ft.TextSpan(
                    label,
                    style=ft.TextStyle(
                        color=link_col,
                        weight=ft.FontWeight.W_600,
                        decoration=ft.TextDecoration.UNDERLINE,
                        size=14,
                    ),
                    url=url,
                )
            )
        elif match.group(2):  # Raw URL
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
        elif match.group(3):  # Mention (@username, @admin, or @all)
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
        elif match.group(4) or match.group(5):  # Standard Markdown **Bold** or __Bold__
            inner = m_str[2:-2]
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
        elif match.group(6):  # Single *Bold*
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
        elif match.group(7):  # Italic _italic_
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
        elif match.group(8):  # Strikethrough ~~strike~~ or ~strike~
            inner = m_str[2:-2] if m_str.startswith("~~") else m_str[1:-1]
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
        elif match.group(9):  # Inline Code `code`
            inner = m_str[1:-1]
            code_col = palette_map.get("bubble_out_link", "#C8E6C9") if is_me else palette_map.get("accent", "#4CAF50")
            code_bg = (
                ft.Colors.with_opacity(0.20, ft.Colors.BLACK)
                if is_me
                else ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)
            )
            spans.append(
                ft.TextSpan(
                    f" {inner} ",
                    style=ft.TextStyle(
                        color=code_col,
                        bgcolor=code_bg,
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
    cur_theme_key = page.data.get("current_theme_key") if hasattr(page, "data") and isinstance(page.data, dict) else None
    if not cur_theme_key or cur_theme_key not in THEME_PALETTES:
        cur_theme_key = "dark" if (hasattr(page, "theme_mode") and page.theme_mode == ft.ThemeMode.DARK) else "light"

    tp = get_theme_palette(cur_theme_key)
    is_dark = tp["is_dark"]
    primary = tp["primary"]
    secondary = tp["secondary"]
    surface = tp["surface"]
    card_bg = tp["card_bg"]
    border = tp["outline"]
    text = tp["on_surface"]
    text_muted = tp["muted"]

    if cur_theme_key == "midnight":
        chat_wall = "#000000"
        surface = "#000000"
        surface_variant = "#0D0D0D"
        card_bg = "#0A0A0A"
        border = "#1F1F1F"
        border_subtle = "#141414"
        text_subtle = "#666666"
        bubble_in_bg = "#0D0D0D"
        bubble_out_bg = "#047857"  # Dark emerald, perfectly tuned for white text on AMOLED
        active_chat_bg = "#141414"
        accent_glow = "#047857"
        code_bg = "#0A0A0A"
        code_border = "#1F1F1F"
        pill_bg = "#141414"
        pill_text = "#00E676"
        system_bg = "#0D0D0D"
    elif cur_theme_key == "slate":
        chat_wall = "#0B0F19"
        surface = "#0B0F19"
        surface_variant = "#1E293B"
        card_bg = "#111827"
        border = "#1F2937"
        border_subtle = "#162032"
        text_subtle = "#6B7280"
        bubble_in_bg = "#1E293B"
        bubble_out_bg = "#065F46"
        active_chat_bg = "#1E293B"
        accent_glow = "#10B981"
        code_bg = "#111827"
        code_border = "#1F2937"
        pill_bg = "#1E293B"
        pill_text = "#10B981"
        system_bg = "#131D31"
    elif cur_theme_key == "sepia":
        chat_wall = "#F8F5EE"
        surface = "#F8F5EE"
        surface_variant = "#EDE6D6"
        card_bg = "#FFFDF9"
        border = "#E6DEC8"
        border_subtle = "#EFE8D6"
        text_subtle = "#8D8276"
        bubble_in_bg = "#FFFDF9"
        bubble_out_bg = "#1B4332"  # Deep forest olive, crisp with white text
        active_chat_bg = "#EDE6D6"
        accent_glow = "#1B4332"
        code_bg = "#F4EFE6"
        code_border = "#E6DEC8"
        pill_bg = "#EDE6D6"
        pill_text = "#1B4332"
        system_bg = "#EDE6D6"
    elif is_dark:
        surface = "#1E1E1E"
        surface_variant = "#262626"
        card_bg = "#1E1E1E"
        border = "#2C2C2C"
        border_subtle = "#222222"
        text_subtle = "#757575"
        chat_wall = "#121212"
        bubble_in_bg = "#222222"
        bubble_out_bg = "#2E7D32"
        active_chat_bg = "#262626"
        accent_glow = "#388E3C"
        code_bg = "#181818"
        code_border = "#2C2C2C"
        pill_bg = "#262626"
        pill_text = text_muted
        system_bg = "#262626"
    else:
        surface = "#FFFFFF"
        surface_variant = "#F5F5F5"
        card_bg = "#FFFFFF"
        border = "#E0E0E0"
        border_subtle = "#EEEEEE"
        text_subtle = "#9E9E9E"
        chat_wall = "#FAFAFA"
        bubble_in_bg = "#FFFFFF"
        bubble_out_bg = "#035800"
        active_chat_bg = "#F0F2F5"
        accent_glow = primary
        code_bg = "#1E1E1E"
        code_border = "#333333"
        pill_bg = "#E6FAE5"
        pill_text = primary
        system_bg = "#F5F5F5"

    palette = {
        "bg": chat_wall,
        "surface": surface,
        "surface_variant": surface_variant,
        "card_bg": card_bg,
        "border": border,
        "border_subtle": border_subtle,
        "accent": primary,
        "accent_glow": accent_glow,
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
        "bubble_in_bg": bubble_in_bg,
        "bubble_in_border": border,
        "bubble_in_text": text,
        "bubble_in_ts": text_muted,
        "bubble_out_bg": bubble_out_bg,
        "bubble_out_text": "#FFFFFF",
        "bubble_out_ts": "rgba(255,255,255,0.75)",
        "bubble_out_link": "#C8E6C9" if (is_dark or cur_theme_key == "sepia") else "#A5D6A7",
        "pill_bg": pill_bg,
        "pill_text": pill_text,
        "system_bg": system_bg,
        "system_text": text_muted,
        "online_dot": secondary,
        "unread_badge": primary,
        "bar_other": text_subtle,
        "code_bg": code_bg,
        "code_border": code_border,
        "code_text": "#E8E8E8" if is_dark else text,
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
    all_users_dict = {}
    fab_open = [False]
    search_query = [""]
    seen_msg_ids = set()
    chat_load_lock = [False]
    chat_load_seq = [0]
    last_typing_time = [0]
    typing_tokens = {}
    active_reply_state = [None]
    pinned_msg_target_id = [None]
    in_room_search_open = [False]
    active_channel_members = []
    active_channel_role = [None]
    active_channel_admin_id = [None]

    def _is_current_user_admin() -> bool:
        my_uid = str(current_user_id[0] or "").strip().lower()
        if not my_uid:
            return False
        active_info = active_chat_info[0] if active_chat_info else {}
        chat_type = active_info.get("type", "direct")
        if chat_type == "direct":
            return True
        creator_id = str(active_info.get("created_by_id") or active_info.get("admin_id") or "").strip().lower()
        channel_admin_id = str(active_channel_admin_id[0] or "").strip().lower()
        role_val = str(active_channel_role[0] or active_info.get("role") or "").strip().lower()
        return bool(role_val == "admin" or (creator_id and creator_id == my_uid) or (channel_admin_id and channel_admin_id == my_uid))

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
                    all_users_dict.clear()
                    for u in res:
                        u_id = str(u.get("id") or u.get("user_id", "")).strip().lower()
                        if u_id:
                            all_users_dict[u_id] = u
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
    active_chat_status_txt = ft.Text("", size=11, color=palette["text_muted"])
    active_chat_header = ft.Row(spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    # ── Room Search & Pinned Notice Controls ──────────────────────────────
    def _jump_to_message(target_id: str):
        if not target_id:
            return
        t_id = str(target_id).strip().lower()
        for idx, ctrl in enumerate(messages_listview.controls):
            if hasattr(ctrl, "data") and str(ctrl.data).strip().lower() == t_id:
                try:
                    page.run_task(messages_listview.scroll_to, scroll_key=str(ctrl.data), duration=300)
                except Exception:
                    pass
                try:
                    b_ref = getattr(ctrl, "bubble_ref", None)
                    if b_ref:
                        orig_bg = b_ref.bgcolor
                        b_ref.bgcolor = palette.get("accent_glow", ft.Colors.PRIMARY_CONTAINER)
                        try:
                            b_ref.update()
                        except Exception:
                            page.update()
                        async def _restore_b(b=b_ref, ob=orig_bg):
                            await asyncio.sleep(1.2)
                            b.bgcolor = ob
                            try:
                                b.update()
                            except Exception:
                                page.update()
                        page.run_task(_restore_b)
                except Exception as j_err:
                    print(f"[chat] Jump error: {j_err}")
                break

    def _scroll_to_pinned(e=None):
        if pinned_msg_target_id[0]:
            _jump_to_message(pinned_msg_target_id[0])

    def _unpin_pinned_msg(e=None):
        mid = pinned_msg_target_id[0]
        _send_ws_unpin(mid or "")
        pinned_notice_bar.visible = False
        pinned_msg_target_id[0] = None
        try:
            pinned_notice_bar.update()
        except Exception:
            page.update()

    def _safe_set_visible(ctrl, visible: bool):
        if hasattr(ctrl, "_frozen"):
            try:
                del ctrl._frozen
            except Exception:
                pass
        try:
            ctrl.visible = visible
        except Exception:
            pass

    def _on_search_query_change(e):
        sq = (in_room_search_in.value or "").strip().lower()
        if not sq:
            search_match_count_text.value = ""
            for ctrl in messages_listview.controls:
                _safe_set_visible(ctrl, True)
            page.update()
            return
        matches = 0
        for ctrl in messages_listview.controls:
            m_data = getattr(ctrl, "msg_data", {})
            c_txt = str(m_data.get("content") or "").lower()
            if sq in c_txt:
                _safe_set_visible(ctrl, True)
                matches += 1
            else:
                _safe_set_visible(ctrl, False)
        search_match_count_text.value = f"{matches} found"
        page.update()

    def _close_in_room_search(e=None, do_update: bool = True):
        was_open = in_room_search_open[0] or in_room_search_container.visible or bool(in_room_search_in.value)
        in_room_search_open[0] = False
        in_room_search_container.visible = False
        in_room_search_in.value = ""
        search_match_count_text.value = ""
        if was_open:
            for ctrl in messages_listview.controls:
                _safe_set_visible(ctrl, True)
        if do_update and was_open:
            page.update()
            _restore_scroll_anchor()

    async def _safe_focus(control=None):
        ctrl = control or msg_input
        try:
            try:
                p = getattr(ctrl, "page", None)
            except RuntimeError:
                p = None
            if p is not None:
                await ctrl.focus()
        except Exception:
            pass

    def _toggle_in_room_search(e=None):
        in_room_search_open[0] = not in_room_search_open[0]
        in_room_search_container.visible = in_room_search_open[0]
        if in_room_search_open[0]:
            page.update()
            _restore_scroll_anchor()
            page.run_task(_safe_focus, in_room_search_in)
        else:
            _close_in_room_search(do_update=True)

    in_room_search_in = ft.TextField(
        hint_text="Search messages in this chat...",
        hint_style=ft.TextStyle(size=12, color=palette["text_muted"]),
        text_size=12,
        text_style=ft.TextStyle(size=12, color=palette["text"]),
        text_input_action=ft.TextInputAction.SEARCH,
        border_radius=8,
        bgcolor=palette["input_bg"],
        border_color=palette["border"],
        focused_border_color=palette["accent"],
        content_padding=ft.Padding.symmetric(horizontal=10, vertical=6),
        expand=True,
        on_change=_on_search_query_change,
    )
    search_match_count_text = ft.Text("", size=11, color=palette["text_muted"])
    in_room_search_container = ft.Container(
        visible=False,
        padding=ft.Padding.only(top=4),
        content=ft.Row([
            in_room_search_in,
            search_match_count_text,
            ft.IconButton(icon=ft.Icons.CLOSE_ROUNDED, icon_size=16, icon_color=palette["text_muted"], on_click=_close_in_room_search),
        ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
    )

    search_header_btn = ft.IconButton(
        icon=ft.Icons.SEARCH_ROUNDED,
        icon_color=palette["text_muted"],
        icon_size=20,
        tooltip="Search in conversation",
        on_click=_toggle_in_room_search
    )

    pinned_notice_text = ft.Text(
        "",
        size=11,
        weight=ft.FontWeight.W_500,
        color=palette["text"],
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
        no_wrap=True,
        expand=True,
    )

    unpin_btn = ft.IconButton(
        icon=ft.Icons.CLOSE_ROUNDED,
        icon_size=14,
        icon_color=palette["text_muted"],
        tooltip="Unpin notice",
        on_click=_unpin_pinned_msg,
        visible=False,
    )

    pinned_notice_bar = ft.Container(
        visible=False,
        bgcolor=ft.Colors.with_opacity(0.12, palette["accent"]),
        border_radius=8,
        padding=ft.Padding.symmetric(horizontal=10, vertical=5),
        ink=True,
        on_click=_scroll_to_pinned,
        content=ft.Row([
            ft.Icon(ft.Icons.PUSH_PIN_ROUNDED, size=15, color=palette["accent"]),
            pinned_notice_text,
            unpin_btn,
        ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
    )

    def _cancel_reply(e=None, do_update: bool = True):
        had_reply = active_reply_state[0] is not None
        active_reply_state[0] = None
        reply_bar_container.content = ft.Container(visible=False, height=0)
        if do_update and had_reply:
            try:
                reply_bar_container.update()
            except Exception:
                page.update()
            _restore_scroll_anchor()

    reply_bar_container = ft.Container(
        content=ft.Container(visible=False, height=0),
        animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT)
    )

    def _set_reply(msg_to_reply: dict):
        s_name = (msg_to_reply.get("sender") or {}).get("name") or msg_to_reply.get("sender_name") or "User"
        s_id = str((msg_to_reply.get("sender") or {}).get("id") or msg_to_reply.get("sender_id", "")).strip().lower()
        c_txt = msg_to_reply.get("content") or "Message"
        is_target_ai = (
            s_id == "ai_assistant"
            or s_name.strip().lower() in ("nu owl", "nu study ai", "ai assistant")
        )
        active_reply_state[0] = {
            "message_id": str(msg_to_reply.get("id") or ""),
            "sender_id": "ai_assistant" if is_target_ai else s_id,
            "sender_name": "Nu Owl" if is_target_ai else s_name,
            "snippet": c_txt[:80] + ("..." if len(c_txt) > 80 else ""),
            "type": "ai_response" if is_target_ai else "text",
            "is_ai": is_target_ai,
        }
        reply_bar_container.content = build_chat_reply_bar(active_reply_state[0], palette, _cancel_reply)
        try:
            reply_bar_container.update()
        except Exception:
            page.update()
        _restore_scroll_anchor()
        page.run_task(_safe_focus, msg_input)

    def _update_bubble_reactions_in_place(
        target_msg_id: str,
        new_reactions: Optional[dict] = None,
        toggle_emoji: Optional[str] = None,
    ):
        t_mid = str(target_msg_id or "").strip().lower()
        if not t_mid:
            return
        my_uid = str(current_user_id[0] or "").strip().lower()
        for ctrl in messages_listview.controls:
            if hasattr(ctrl, "data") and str(ctrl.data).strip().lower() == t_mid:
                m_d = getattr(ctrl, "msg_data", None)
                if not isinstance(m_d, dict):
                    break
                meta = m_d.get("metadata_payload") or {}
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except Exception:
                        meta = {}
                if not isinstance(meta, dict):
                    meta = {}

                if new_reactions is not None and isinstance(new_reactions, dict):
                    reactions_map = dict(new_reactions)
                else:
                    reactions_map = dict(meta.get("reactions") or {})
                    if toggle_emoji:
                        voters = [str(u).strip().lower() for u in (reactions_map.get(toggle_emoji) or [])]
                        if my_uid in voters:
                            voters = [u for u in voters if u != my_uid]
                        else:
                            voters.append(my_uid)
                        if voters:
                            reactions_map[toggle_emoji] = voters
                        else:
                            reactions_map.pop(toggle_emoji, None)

                meta["reactions"] = reactions_map
                m_d["metadata_payload"] = meta
                ctrl.msg_data = m_d

                r_holder = getattr(ctrl, "reactions_holder", None)
                if r_holder is not None:
                    r_holder.content = build_reaction_pills_row(
                        reactions_map,
                        current_user_id[0],
                        lambda emoji_val, mid=str(m_d.get("id") or ""): _send_ws_reaction(mid, emoji_val),
                        palette,
                    )
                    if getattr(r_holder, "page", None) is not None:
                        try:
                            r_holder.update()
                            return
                        except Exception:
                            pass
                if getattr(ctrl, "page", None) is not None:
                    try:
                        ctrl.update()
                    except Exception:
                        pass
                break

    def _send_ws_reaction(target_msg_id: str, emoji_char: str):
        # 1. Instant 0ms optimistic reaction toggle on the target bubble's reaction holder
        _update_bubble_reactions_in_place(target_msg_id, toggle_emoji=emoji_char)
        # 2. Dispatch async WebSocket frame
        cid = current_chat_id[0]
        if cid and ws_client_ref[0]:
            page.run_task(
                ws_client_ref[0].send_message,
                cid,
                "",
                "reaction",
                message_id=target_msg_id,
                emoji=emoji_char
            )

    def _send_ws_pin(target_msg_id: str):
        # Optimistically show pinned bar immediately
        t_mid = str(target_msg_id or "").strip().lower()
        for ctrl in messages_listview.controls:
            if hasattr(ctrl, "data") and str(ctrl.data).strip().lower() == t_mid:
                m_d = getattr(ctrl, "msg_data", {})
                if isinstance(m_d, dict):
                    pinned_msg_target_id[0] = m_d.get("id")
                    p_snip = m_d.get("content") or "Pinned notice"
                    pinned_notice_text.value = f"📌 Pinned: {p_snip[:60]}"
                    pinned_notice_bar.visible = True
                    unpin_btn.visible = _is_current_user_admin()
                    if getattr(pinned_notice_bar, "page", None) is not None:
                        try:
                            pinned_notice_bar.update()
                        except Exception:
                            pass
                break
        cid = current_chat_id[0]
        if cid and ws_client_ref[0]:
            page.run_task(
                ws_client_ref[0].send_message,
                cid,
                "",
                "pin_message",
                message_id=target_msg_id
            )

    def _send_ws_unpin(target_msg_id: str = ""):
        pinned_msg_target_id[0] = None
        if pinned_notice_bar.visible:
            pinned_notice_bar.visible = False
            if getattr(pinned_notice_bar, "page", None) is not None:
                try:
                    pinned_notice_bar.update()
                except Exception:
                    pass
        cid = current_chat_id[0]
        if cid and ws_client_ref[0]:
            page.run_task(
                ws_client_ref[0].send_message,
                cid,
                "",
                "unpin_message",
                message_id=target_msg_id or ""
            )

    def _send_ws_delete(target_msg_id: str):
        t_mid = str(target_msg_id or "").strip().lower()
        if not t_mid:
            return
        # 1. Update in-memory bubble instantly with optimistic deletion
        for idx, ctrl in enumerate(messages_listview.controls):
            c_data = str(getattr(ctrl, "data", "") or "").strip().lower()
            c_cid = str(getattr(ctrl, "client_msg_id", "") or "").strip().lower()
            m_d = getattr(ctrl, "msg_data", {})
            m_id = str(m_d.get("id") or "").strip().lower() if isinstance(m_d, dict) else ""
            m_cid = str(m_d.get("client_msg_id") or "").strip().lower() if isinstance(m_d, dict) else ""

            if t_mid in (c_data, c_cid, m_id, m_cid):
                if isinstance(m_d, dict):
                    m_d["content"] = "This message was deleted"
                    m_d["type"] = "text"
                    m_d["is_deleted"] = True
                    meta = m_d.get("metadata_payload") or {}
                    if isinstance(meta, str):
                        try:
                            meta = json.loads(meta)
                        except Exception:
                            meta = {}
                    if not isinstance(meta, dict):
                        meta = {}
                    meta["is_deleted"] = True
                    meta.pop("options", None)
                    meta.pop("poll_options", None)
                    meta.pop("votes", None)
                    m_d["metadata_payload"] = meta
                    _replace_bubble_in_place(idx, m_d, do_update=True)
                break

        # 2. Mark in local SQLite database
        mark_cached_message_deleted(page, target_msg_id)

        # 3. Network dispatch: WebSocket with automatic REST fallback
        cid = current_chat_id[0]
        async def _dispatch_delete_task():
            sent = False
            if cid and ws_client_ref[0] and getattr(ws_client_ref[0], "websocket", None):
                try:
                    sent = await ws_client_ref[0].send_message(
                        cid,
                        "",
                        "delete_message",
                        message_id=target_msg_id
                    )
                except Exception as ws_err:
                    print(f"[NuChat] Delete WS error: {ws_err}")
            if not sent and cid and token:
                try:
                    await delete_channel_message_api(token, cid, target_msg_id)
                except Exception as rest_err:
                    print(f"[NuChat] Delete REST fallback error: {rest_err}")

        page.run_task(_dispatch_delete_task)

    # Track live scroll state so modals/actions never reset scroll to the top (0.0)
    last_scroll_pixels = [0.0]
    last_max_scroll = [0.0]
    is_near_bottom = [True]
    last_scroll_time = [0.0]

    def _on_messages_scroll(e):
        now = datetime.now().timestamp()
        if now - last_scroll_time[0] < 0.08:
            return
        last_scroll_time[0] = now
        try:
            px = float(getattr(e, "pixels", 0.0) or 0.0)
            mx = float(getattr(e, "max_scroll_extent", 0.0) or 0.0)
            if mx > 0:
                last_max_scroll[0] = mx
                last_scroll_pixels[0] = px
                is_near_bottom[0] = (mx - px) <= 95.0
        except Exception:
            pass

    messages_listview = ft.ListView(
        expand=True,
        spacing=4,
        auto_scroll=False,
        build_controls_on_demand=True,
        cache_extent=500,
        on_scroll=_on_messages_scroll,
        padding=ft.Padding.symmetric(horizontal=8 if not is_desktop[0] else 12, vertical=8 if not is_desktop[0] else 10)
    )

    async def _on_refresh_active_messages(e=None):
        cid = current_chat_id[0]
        if not cid:
            return
        try:
            history = await get_channel_messages(token, cid)
            if isinstance(history, list):
                chronological = list(reversed(history))
                new_deltas = [m for m in chronological if str(m.get("id")) not in seen_msg_ids]
                if new_deltas:
                    for m in new_deltas:
                        mid = str(m.get("id"))
                        if mid:
                            seen_msg_ids.add(mid)
                        prev_item = messages_listview.controls[-1].msg_data if (messages_listview.controls and hasattr(messages_listview.controls[-1], "msg_data")) else None
                        messages_listview.controls.append(render_message_bubble(m, prev_msg=prev_item, animate_entrance=False))
                    if getattr(messages_listview, "page", None) is not None:
                        messages_listview.update()
        except Exception as ex:
            print(f"[NuChat] Pull-to-refresh messages error: {ex}")

    messages_refresh_indicator = ft.RefreshIndicator(
        content=messages_listview,
        on_refresh=_on_refresh_active_messages,
        color=palette["accent"],
        bgcolor=palette["surface"],
        expand=True,
    )

    messages_anim_container = ft.Container(
        content=messages_refresh_indicator,
        expand=True,
        bgcolor=palette["chat_wall"],
        opacity=1.0,
        offset=ft.Offset(0, 0),
        animate_opacity=ft.Animation(280, ft.AnimationCurve.DECELERATE),
        animate_offset=ft.Animation(280, ft.AnimationCurve.DECELERATE),
    )

    async def _async_scroll_to_bottom(animate: bool = True):
        try:
            is_near_bottom[0] = True
            await asyncio.sleep(0.05)
            await messages_listview.scroll_to(offset=-1, duration=200 if animate else 0)
            if not animate:
                await asyncio.sleep(0.10)
                await messages_listview.scroll_to(offset=-1, duration=0)
        except Exception:
            pass

    def _scroll_to_bottom(animate: bool = False):
        try:
            is_near_bottom[0] = True
            page.run_task(_async_scroll_to_bottom, animate)
        except Exception:
            pass

    async def _async_restore_scroll_anchor(saved_near_bottom: bool, saved_pixels: float):
        try:
            await asyncio.sleep(0.02)
            if saved_near_bottom:
                await messages_listview.scroll_to(offset=-1, duration=0)
            elif saved_pixels > 0:
                await messages_listview.scroll_to(offset=saved_pixels, duration=0)
        except Exception:
            pass

    def _restore_scroll_anchor():
        try:
            page.run_task(_async_restore_scroll_anchor, is_near_bottom[0], last_scroll_pixels[0])
        except Exception:
            pass

    async def _animate_bubble_entrance(bubble_w):
        if not bubble_w:
            return
        inner_b = getattr(bubble_w, "bubble_ref", None) or bubble_w
        is_me = getattr(bubble_w, "is_me_bubble", False)
        # Yield brief moment for Flutter control tree to mount
        await asyncio.sleep(0.04)
        _unfreeze_control(inner_b)
        align = ft.Alignment.BOTTOM_RIGHT if is_me else (ft.Alignment.CENTER if isinstance(bubble_w, ft.Row) else ft.Alignment.BOTTOM_LEFT)
        inner_b.scale = ft.Scale(1.0, alignment=align)
        inner_b.opacity = 1.0
        inner_b.offset = ft.Offset(0, 0)
        try:
            inner_b.update()
        except Exception:
            try:
                page.update()
            except Exception:
                pass

    async def _animate_history_bubbles(controls_list):
        # Optimization: History messages mount with instant crisp visibility (no async sleep loops)
        return

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

    def update_bubble_status(ctrl, new_status: str):
        if not ctrl:
            return
        tick_holder = getattr(ctrl, "status_tick", None)
        mdata = getattr(ctrl, "msg_data", None)
        if isinstance(mdata, dict):
            mdata["status"] = new_status
        if not tick_holder:
            return

        st = str(new_status or "delivered").lower()
        is_overlay_tick = getattr(tick_holder, "is_image_overlay_tick", False)
        ts_color = ft.Colors.WHITE if is_overlay_tick else palette.get("bubble_out_ts", palette.get("text_muted"))

        target_icon = ft.Icons.DONE_ALL_ROUNDED
        target_size = 12
        is_poll_msg = bool(mdata and (mdata.get("type") in ("poll", "poll_update") or "options" in (mdata.get("metadata_payload") or {})))
        target_color = palette.get("accent", ft.Colors.with_opacity(0.85, ts_color)) if is_poll_msg else (ft.Colors.WHITE if is_overlay_tick else ft.Colors.with_opacity(0.85, ts_color))

        if st == "pending":
            target_icon = ft.Icons.ACCESS_TIME_ROUNDED
            target_size = 10.5
            target_color = ft.Colors.WHITE_70 if is_overlay_tick else ft.Colors.with_opacity(0.75, ts_color)
        elif st == "sent":
            target_icon = ft.Icons.CHECK_ROUNDED
            target_size = 12
            target_color = ft.Colors.WHITE if is_overlay_tick else ft.Colors.with_opacity(0.85, ts_color)
        elif st == "read":
            target_icon = ft.Icons.DONE_ALL_ROUNDED
            target_size = 12
            target_color = ft.Colors.CYAN_300 if (is_dark or is_overlay_tick) else ft.Colors.BLUE_600
        elif st == "failed":
            target_icon = ft.Icons.ERROR_OUTLINE_ROUNDED
            target_size = 11
            target_color = ft.Colors.RED_400

        try:
            new_icon_ctrl = ft.Icon(target_icon, size=target_size, color=target_color)
            if isinstance(tick_holder, ft.Container):
                tick_holder.content = new_icon_ctrl
            elif isinstance(tick_holder, ft.Icon):
                setattr(tick_holder, "icon", target_icon)
                setattr(tick_holder, "size", target_size)
                setattr(tick_holder, "color", target_color)
        except Exception as ex:
            print(f"[Chat] update_bubble_status error: {ex}")

    async def send_text_message(
        e=None,
        custom_text: Optional[str] = None,
        msg_type: str = "text",
        local_only: bool = False,
        extra_metadata: Optional[dict] = None,
    ):
        text = custom_text if custom_text is not None else (msg_input.value or "").strip()
        if not text or not current_chat_id[0]:
            return

        autocomplete_card.visible = False
        if custom_text is None:
            msg_input.value = ""
        _update_send_btn_state()

        # Parse mentions (@username / @admin)
        mentions = re.findall(r'@([\w.-]+)', text)
        extra_meta = dict(extra_metadata or {})
        if active_reply_state[0]:
            extra_meta["reply_to"] = active_reply_state[0]
            _cancel_reply()
        if mentions:
            extra_meta["mentions"] = mentions
            mention_ids = []
            candidates = active_channel_members
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

        # Intercept /help slash command locally (opens rich guide, never transmits dummy prompt)
        if text.strip().lower() == "/help":
            if custom_text is None:
                msg_input.value = ""
            _update_send_btn_state()
            open_chat_help_dialog()
            return

        # Intercept /duel or /duo slash commands
        if text.strip().lower().startswith("/duel") or text.strip().lower().startswith("/duo"):
            from src.components.chat_commands import execute_slash_command
            handled = await execute_slash_command(
                page=page,
                token=token,
                raw_text=text,
                active_chat_info=active_chat_info[0],
                active_channel_members=active_channel_members,
                all_users_cache=all_users_cache,
                on_post_message=lambda c, is_system=True, local_only=False: send_text_message(custom_text=c, msg_type="system" if is_system else "text", local_only=local_only)
            )
            if handled:
                if custom_text is None:
                    msg_input.value = ""
                _update_send_btn_state()
                return

        # 1. Generate unique client temporary ID for optimistic bubble tracking
        client_temp_id = f"client_{uuid.uuid4().hex}"
        extra_meta["client_msg_id"] = client_temp_id

        my_id_str = str(current_user_id[0]).strip().lower()
        my_name = "You"
        for u in all_users_cache:
            if str(u.get("id") or u.get("user_id", "")).strip().lower() == my_id_str:
                my_name = (u.get("name") or u.get("full_name") or u.get("username") or "You").strip()
                break
        if my_name == "You" and hasattr(page, "session") and hasattr(page.session, "store"):
            cu = page.session.store.get("current_user") or {}
            if isinstance(cu, dict):
                f = cu.get("first_name", "")
                l = cu.get("last_name", "")
                my_name = f"{f} {l}".strip() or cu.get("username", "You")

        now_iso = datetime.now(timezone.utc).isoformat()
        optimistic_dict = {
            "id": client_temp_id,
            "client_msg_id": client_temp_id,
            "channel_id": current_chat_id[0],
            "content": text,
            "type": msg_type,
            "metadata_payload": extra_meta,
            "created_at": now_iso,
            "sender": {
                "id": my_id_str,
                "name": my_name,
            },
            "sender_id": my_id_str,
            "is_me": True,
            "status": "pending",  # In-flight state: 🕒 Clock icon
        }

        # 2. Zero-latency instant UI render (appears immediately, never lost in the void)
        if len(messages_listview.controls) == 1 and not hasattr(messages_listview.controls[0], "data"):
            messages_listview.controls.clear()

        prev_ctrl = None
        if messages_listview.controls:
            last_ctrl = messages_listview.controls[-1]
            if hasattr(last_ctrl, "data"):
                prev_ctrl = {"sender_id": my_id_str, "created_at": now_iso}

        bubble_w = render_message_bubble(optimistic_dict, prev_msg=prev_ctrl, animate_entrance=True)
        bubble_w.data = client_temp_id
        bubble_w.client_msg_id = client_temp_id
        bubble_w.msg_data = optimistic_dict
        messages_listview.controls.append(bubble_w)
        try:
            messages_listview.update()
            if custom_text is None:
                msg_input.update()
        except Exception:
            page.update()
        page.run_task(_animate_bubble_entrance, bubble_w)
        _scroll_to_bottom(animate=True)

        # 3. Resilient background dispatch (WebSocket with automatic REST API fallback)
        async def _dispatch_msg_task(cid, m_text, m_meta, temp_id, opt_dict):
            nonlocal token
            sent_ok = False
            curr_token = token or (await page.shared_preferences.get("auth_token"))

            def _get_target_bubble(tid):
                for ctrl in messages_listview.controls:
                    ctrl_id = getattr(ctrl, "client_msg_id", None) or getattr(ctrl, "data", None)
                    if ctrl_id and str(ctrl_id) == str(tid):
                        return ctrl
                return bubble_w

            # Step A: Attempt primary WebSocket transmission
            if ws_client_ref[0] and getattr(ws_client_ref[0], "websocket", None):
                try:
                    sent_ok = await ws_client_ref[0].send_message(
                        cid, m_text, msg_type,
                        client_msg_id=temp_id,
                        metadata_payload=m_meta
                    )
                except Exception as ws_ex:
                    print(f"[Chat] WebSocket dispatch error: {ws_ex}")
                    sent_ok = False

            # Step B: Resilient Fallback to REST API if WebSocket failed or is reconnecting
            if not sent_ok and curr_token:
                try:
                    rest_res = await send_channel_message_api(
                        curr_token, cid, m_text, msg_type,
                        metadata_payload=m_meta
                    )
                    if isinstance(rest_res, dict) and "id" in rest_res:
                        sent_ok = True
                        target_b = _get_target_bubble(temp_id)
                        if target_b:
                            real_id = str(rest_res["id"])
                            target_b.data = real_id
                            seen_msg_ids.add(real_id)
                            update_bubble_status(target_b, "delivered")
                            page.update()
                except Exception as rest_ex:
                    print(f"[Chat] REST fallback error: {rest_ex}")
                    sent_ok = False

            if sent_ok:
                target_b = _get_target_bubble(temp_id)
                if target_b:
                    if getattr(target_b, "msg_data", {}).get("status") == "pending":
                        update_bubble_status(target_b, "sent")
                        page.update()
            else:
                target_b = _get_target_bubble(temp_id)
                if target_b:
                    update_bubble_status(target_b, "failed")
                    page.update()

        page.run_task(_dispatch_msg_task, current_chat_id[0], text, extra_meta, client_temp_id, optimistic_dict)

    send_btn_has_text = [False]

    def _update_send_btn_state(do_update: bool = False):
        has_text = bool(msg_input.value and msg_input.value.strip())
        target_bg = palette["accent_glow"] if has_text else palette["surface_variant"]
        target_col = ft.Colors.WHITE if has_text else palette["text_muted"]
        changed = (send_btn_has_text[0] != has_text) or (send_btn_container.bgcolor != target_bg) or (send_btn_icon.color != target_col)
        send_btn_has_text[0] = has_text
        send_btn_container.bgcolor = target_bg
        send_btn_icon.color = target_col
        if do_update and changed:
            try:
                send_btn_container.update()
            except Exception:
                pass

    autocomplete_debounce_token = [0]

    def _process_autocomplete(val: str):
        active_type = active_chat_info[0].get("type", "direct")
        match_slash = re.search(r'(^|\s)(/)([\w.-]*)$', val)
        match_mention = re.search(r'(@)([\w.-]*)$', val) if active_type != "direct" else None

        if match_slash:
            s_query = match_slash.group(3).lower()
            autocomplete_list.controls.clear()

            slash_commands = [
                {
                    "cmd": "/ai",
                    "label": "/ai <prompt>",
                    "desc": "Ask Nu Study AI an academic question",
                    "icon": ft.Icons.AUTO_AWESOME_ROUNDED,
                    "color": palette["accent"],
                    "action": "ai"
                },
                {
                    "cmd": "/poll",
                    "label": "/poll",
                    "desc": "Create an in-chat interactive poll",
                    "icon": ft.Icons.POLL_ROUNDED,
                    "color": ft.Colors.CYAN_400,
                    "action": "poll"
                },
                {
                    "cmd": "/code",
                    "label": "/code",
                    "desc": "Insert syntax-highlighted code block",
                    "icon": ft.Icons.CODE_ROUNDED,
                    "color": ft.Colors.AMBER_400,
                    "action": "code"
                },
                {
                    "cmd": "/duel",
                    "label": "/duel [@user]",
                    "desc": "Challenge partner to a 15-Q Quickfire Duel",
                    "icon": ft.Icons.FLASH_ON_ROUNDED,
                    "color": ft.Colors.ORANGE_500,
                    "action": "duel"
                },
                {
                    "cmd": "/duo",
                    "label": "/duo [@user]",
                    "desc": "Send Duo Buddy accountability request",
                    "icon": ft.Icons.PEOPLE_ROUNDED,
                    "color": ft.Colors.GREEN_600,
                    "action": "duo"
                },
                {
                    "cmd": "/help",
                    "label": "/help",
                    "desc": "View commands guide & formatting tips",
                    "icon": ft.Icons.HELP_OUTLINE_ROUNDED,
                    "color": ft.Colors.BLUE_500,
                    "action": "help"
                },
            ]

            filtered = [sc for sc in slash_commands if (s_query in sc["cmd"] or s_query in sc["label"] or not s_query)]
            for item in filtered:
                def _select_cmd(ev, action_type=item["action"]):
                    autocomplete_card.visible = False
                    if action_type == "ai":
                        msg_input.value = re.sub(r'(/)[\w.-]*$', '/ai ', msg_input.value or '')
                        page.run_task(_safe_focus, msg_input)
                    elif action_type == "poll":
                        msg_input.value = re.sub(r'(/)[\w.-]*$', '', msg_input.value or '')
                        open_poll_modal()
                    elif action_type == "code":
                        msg_input.value = re.sub(r'(/)[\w.-]*$', '```python\n# Code\n```', msg_input.value or '')
                        page.run_task(_safe_focus, msg_input)
                    elif action_type == "duel":
                        msg_input.value = re.sub(r'(/)[\w.-]*$', '/duel ', msg_input.value or '')
                        page.run_task(_safe_focus, msg_input)
                    elif action_type == "duo":
                        msg_input.value = re.sub(r'(/)[\w.-]*$', '/duo ', msg_input.value or '')
                        page.run_task(_safe_focus, msg_input)
                    elif action_type == "help":
                        msg_input.value = re.sub(r'(/)[\w.-]*$', '', msg_input.value or '')
                        open_chat_help_dialog()
                    _update_send_btn_state(do_update=True)
                    try:
                        autocomplete_card.update()
                        msg_input.update()
                    except Exception:
                        pass
                    _restore_scroll_anchor()

                tile = ft.Container(
                    ink=True,
                    border_radius=8,
                    padding=ft.Padding.symmetric(horizontal=10, vertical=7),
                    on_click=_select_cmd,
                    content=ft.Row([
                        ft.Container(
                            width=28,
                            height=28,
                            border_radius=14,
                            bgcolor=ft.Colors.with_opacity(0.14, item["color"]),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(item["icon"], size=16, color=item["color"])
                        ),
                        ft.Column([
                            ft.Text(item["label"], size=13, weight=ft.FontWeight.BOLD, color=palette["text"]),
                            ft.Text(item["desc"], size=11, color=palette["text_muted"]),
                        ], spacing=1, expand=True),
                    ], spacing=10, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER)
                )
                autocomplete_list.controls.append(tile)

            autocomplete_card.visible = (len(autocomplete_list.controls) > 0)
            try:
                autocomplete_card.update()
            except Exception:
                pass
            return

        match = match_mention
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
                    msg_input.value = re.sub(r'@[\w.-]*$', '@all ', msg_input.value or '')
                    autocomplete_card.visible = False
                    _update_send_btn_state(do_update=True)
                    try:
                        autocomplete_card.update()
                        msg_input.update()
                    except Exception:
                        pass

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
                    msg_input.value = re.sub(r'@[\w.-]*$', '@admin ', msg_input.value or '')
                    autocomplete_card.visible = False
                    _update_send_btn_state(do_update=True)
                    try:
                        autocomplete_card.update()
                        msg_input.update()
                    except Exception:
                        pass

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

            # 3. Group members alone (strictly channel members; up to 8 max matches to keep typing fast)
            candidate_members = active_channel_members
            my_uid = str(current_user_id[0]).strip().lower()
            admin_id_val = str(active_channel_admin_id[0]).strip().lower() if active_channel_admin_id[0] else ""

            matches = [
                m for m in candidate_members
                if str(m.get("id") or m.get("user_id", "")).strip().lower() != my_uid and (
                    query in (m.get("username") or "").lower() or
                    query in (m.get("name") or m.get("full_name") or "").lower()
                )
            ][:8]

            for u in matches:
                u_id_str = str(u.get("id") or u.get("user_id", "")).strip().lower()
                raw_uname = (u.get("username") or u.get("name") or "user").strip()
                handle = raw_uname.replace(" ", "_")
                dname = (u.get("name") or u.get("full_name") or raw_uname).strip()
                is_admin_member = (u.get("is_admin", False) or u.get("role") == "admin" or u_id_str == admin_id_val)

                def _select_m(ev, tag_h=handle, uid=u_id_str):
                    selected_mention_map[tag_h.lower()] = uid
                    msg_input.value = re.sub(r'@[\w.-]*$', f'@{tag_h} ', msg_input.value or '')
                    autocomplete_card.visible = False
                    _update_send_btn_state(do_update=True)
                    try:
                        autocomplete_card.update()
                        msg_input.update()
                    except Exception:
                        pass

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
            try:
                autocomplete_card.update()
            except Exception:
                pass
        else:
            if autocomplete_card.visible:
                autocomplete_card.visible = False
                try:
                    autocomplete_card.update()
                except Exception:
                    pass

    def on_input_change(e):
        val = msg_input.value or ""
        # 1. Fast state transition check: only touch controls if text transitioned from empty <-> non-empty
        has_text = bool(val and val.strip())
        if send_btn_has_text[0] != has_text:
            _update_send_btn_state(do_update=True)

        now = datetime.now().timestamp()
        if now - last_typing_time[0] > 3.0:
            last_typing_time[0] = now
            if ws_client_ref[0] and getattr(ws_client_ref[0], "websocket", None) and current_chat_id[0]:
                page.run_task(ws_client_ref[0].send_message, current_chat_id[0], "typing", "typing")

        # ── FAST-PATH: If neither '/' nor '@' is typed, immediately close autocomplete and exit! ──
        if "/" not in val and "@" not in val:
            if autocomplete_card.visible:
                autocomplete_card.visible = False
                try:
                    autocomplete_card.update()
                except Exception:
                    pass
            return

        # Debounce autocomplete processing by 150ms so rapid typing is buttery smooth
        autocomplete_debounce_token[0] += 1
        tok = autocomplete_debounce_token[0]

        async def _debounced_autocomplete():
            await asyncio.sleep(0.15)
            if autocomplete_debounce_token[0] != tok:
                return
            _process_autocomplete(val)

        page.run_task(_debounced_autocomplete)

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
        text_input_action=ft.TextInputAction.SEND,
        shift_enter=True,
        on_change=on_input_change,
        on_submit=send_text_message
    )

    send_btn_container.on_click = send_text_message

    _chat_search_seq = [0]

    def on_search_changed(e):
        search_query[0] = (e.control.value or "").lower().strip()
        _chat_search_seq[0] += 1
        seq = _chat_search_seq[0]

        async def _debounced_chat_search():
            await asyncio.sleep(0.14)
            if seq != _chat_search_seq[0]:
                return
            render_chat_list()

        page.run_task(_debounced_chat_search)

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
        text_input_action=ft.TextInputAction.SEARCH,
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

    async def _on_refresh_channels(e=None):
        nonlocal channels_list
        try:
            res = await get_user_channels(token)
            if isinstance(res, list):
                for ch in res:
                    if not ch.get("channel_id") and ch.get("id"):
                        ch["channel_id"] = ch["id"]
                channels_list = res
                render_chat_list()
        except Exception as ex:
            print(f"[NuChat] Pull-to-refresh channels error: {ex}")

    chat_list_refresh_indicator = ft.RefreshIndicator(
        content=chat_list_scroll_col,
        on_refresh=_on_refresh_channels,
        color=palette["accent"],
        bgcolor=palette["surface"],
        expand=True,
    )
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
            chat_list_refresh_indicator
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

    def render_message_bubble(msg: dict, prev_msg: Optional[dict] = None, next_msg: Optional[dict] = None, animate_entrance: bool = False):
        is_mob = not is_desktop[0]
        msg_type = msg.get("type", "text")

        # ── A. System Announcement Pill ───────────────────────────────────────
        if msg_type == "system":
            sys_pill = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, size=12, color=palette["system_text"]),
                    ft.Text(msg.get("content", ""), size=11, color=palette["system_text"], weight=ft.FontWeight.W_500),
                ], spacing=6, tight=True),
                bgcolor=palette["system_bg"],
                border=ft.Border.all(1, palette["border"]),
                padding=ft.Padding.symmetric(horizontal=12, vertical=5),
                border_radius=12,
                margin=ft.Margin.symmetric(vertical=4),
                scale=ft.Scale(0.85, alignment=ft.Alignment.CENTER) if animate_entrance else 1.0,
                opacity=0.0 if animate_entrance else 1.0,
                offset=ft.Offset(0, 0.10) if animate_entrance else ft.Offset(0, 0),
                animate_scale=ft.Animation(230, ft.AnimationCurve.EASE_OUT_BACK) if animate_entrance else None,
                animate_opacity=ft.Animation(160, ft.AnimationCurve.EASE_OUT) if animate_entrance else None,
                animate_offset=ft.Animation(230, ft.AnimationCurve.EASE_OUT_BACK) if animate_entrance else None,
            )
            row = ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[sys_pill]
            )
            row.bubble_ref = sys_pill
            row.is_me_bubble = False
            return row

        # ── B. Identify Sender & Clustering ───────────────────────────────────
        sender_info = msg.get("sender", {})
        my_id = str(current_user_id[0]).strip().lower()
        sender_id = str(sender_info.get("id", msg.get("sender_id", "unknown"))).strip().lower()
        sender_name = str(sender_info.get("name", msg.get("sender_name", "Unknown"))).strip() or "Unknown"
        meta_chk = msg.get("metadata_payload") or msg.get("metadata") or {}
        if isinstance(meta_chk, str):
            try: meta_chk = json.loads(meta_chk)
            except: meta_chk = {}
        is_ai = (
            (sender_id == "ai_assistant")
            or (sender_name.lower() in ("nu owl", "nu study ai", "ai assistant", "nu ai"))
            or (str(msg.get("sender", {}).get("name") or "").lower() in ("nu owl", "nu study ai", "ai assistant"))
            or (msg_type == "ai_response" and sender_id in ("ai_assistant", "unknown", ""))
        )
        is_me = ((sender_id == my_id) or msg.get("is_me", False)) and not is_ai
        if is_ai:
            sender_name = "Nu Study AI"
            sender_id = "ai_assistant"
            sender_info = {"id": "ai_assistant", "name": "Nu Study AI"}

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

        is_deleted = bool(
            meta.get("is_deleted")
            or msg.get("is_deleted")
            or raw_content == "This message was deleted"
            or str(msg.get("content") or "").strip() == "This message was deleted"
        )

        is_poll = False if is_deleted else (msg_type in ("poll", "poll_update") or "options" in meta or ("|||" in raw_content and msg_type != "code"))

        # ── C. Bubble Radius Styling (Continuous Clustered Edges) ────────────
        if is_deleted:
            radius = 12
            bg = ft.Colors.with_opacity(0.04, palette["border"])
            text_color = palette["text_muted"]
            ts_color = palette["text_muted"]
            border = ft.Border.all(1, ft.Colors.with_opacity(0.12, palette["border"]))
        elif is_poll:
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

        # Media URL detection for lightweight link representation (no heavy ft.Image rasterization)
        media_url = meta.get("media_url") or (raw_content if (raw_content.startswith("http") and any(raw_content.lower().split("?")[0].endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"])) else None)

        # ── D. Delivery Tick Telemetry (WhatsApp-style States) ──────────────────
        status_tick = ft.Container()
        if is_me:
            msg_status = str(msg.get("status") or "delivered").lower()
            if msg_status == "pending":
                # In-flight / pending connection: 🕒 Clock
                tick_icon = ft.Icon(
                    ft.Icons.ACCESS_TIME_ROUNDED,
                    size=10.5,
                    color=ft.Colors.with_opacity(0.75, ts_color)
                )
            elif msg_status == "sent":
                # Single check: ✓ Sent to server
                tick_icon = ft.Icon(
                    ft.Icons.CHECK_ROUNDED,
                    size=12,
                    color=ft.Colors.with_opacity(0.85, ts_color)
                )
            elif msg_status == "read":
                # Double check: ✓✓ Blue / Cyan read receipt
                tick_icon = ft.Icon(
                    ft.Icons.DONE_ALL_ROUNDED,
                    size=12,
                    color=ft.Colors.CYAN_300 if is_dark else ft.Colors.BLUE_600
                )
            elif msg_status == "failed":
                # Failed dispatch: ⚠️ Alert
                tick_icon = ft.Icon(
                    ft.Icons.ERROR_OUTLINE_ROUNDED,
                    size=11,
                    color=ft.Colors.RED_400
                )
            else:
                # Double check: ✓✓ Delivered to server/recipients (grey)
                tick_icon = ft.Icon(
                    ft.Icons.DONE_ALL_ROUNDED,
                    size=12,
                    color=palette["accent"] if is_poll else ft.Colors.with_opacity(0.85, ts_color)
                )
            status_tick = ft.Container(content=tick_icon)

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
        top_header_controls = []

        if is_deleted:
            body_controls.append(
                ft.Row([
                    ft.Icon(ft.Icons.BLOCK_ROUNDED, size=14, color=palette["text_muted"]),
                    ft.Text(
                        "This message was deleted",
                        size=13,
                        italic=True,
                        color=palette["text_muted"],
                    ),
                ], spacing=6, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER)
            )
            body_controls.append(ts_row)

        # 0.0 AI Assistant Header Badge
        if not is_deleted and is_ai and not is_me:
            sender_name = "Nu Study AI"
            top_header_controls.append(
                ft.Container(
                    padding=ft.Padding.only(bottom=4),
                    content=ft.Row([
                        ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=13, color=palette["accent"]),
                        ft.Text("Nu Study AI", size=11, weight=ft.FontWeight.BOLD, color=palette["accent"]),
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=6, vertical=1),
                            border_radius=6,
                            bgcolor=ft.Colors.with_opacity(0.12, palette["accent"]),
                            content=ft.Text("ASSISTANT", size=8.5, weight=ft.FontWeight.BOLD, color=palette["accent"])
                        )
                    ], spacing=5, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER)
                )
            )

        # 1. Sender Name Header (Show only on first message of cluster in group chats for human members)
        if not is_deleted and not is_me and not is_ai and not prev_is_same:
            active_info = next((c for c in channels_list if c.get("channel_id") == current_chat_id[0]), {})
            if active_info.get("type") != "direct":
                sender_hdr_controls = [
                    ft.Text(sender_name, size=11, weight=ft.FontWeight.BOLD, color=palette["accent"])
                ]
                s_badge = sender_info.get("primary_badge")
                if not s_badge:
                    for mem in active_channel_members:
                        if str(mem.get("id") or mem.get("user_id", "")).strip().lower() == sender_id:
                            s_badge = mem.get("primary_badge")
                            break
                if s_badge and isinstance(s_badge, dict):
                    sender_hdr_controls.append(build_glossy_badge_pill(s_badge, is_mobile=not is_desktop[0], max_width=110))
                top_header_controls.append(
                    ft.Row(sender_hdr_controls, spacing=6, wrap=True, vertical_alignment=ft.CrossAxisAlignment.CENTER)
                )

        # 0. Pinned indicator badge
        if not is_deleted and meta.get("is_pinned"):
            top_header_controls.append(
                ft.Container(
                    padding=ft.Padding.only(bottom=2),
                    content=ft.Row([
                        ft.Icon(ft.Icons.PUSH_PIN_ROUNDED, size=11, color=palette["accent"]),
                        ft.Text("Pinned", size=10, weight=ft.FontWeight.BOLD, color=palette["accent"]),
                    ], spacing=4, tight=True)
                )
            )

        # 0.1 Quoted Reply Preview inside bubble
        reply_meta = meta.get("reply_to") if not is_deleted else None
        if reply_meta and isinstance(reply_meta, dict):
            r_sender = reply_meta.get("sender_name") or "User"
            r_snip = reply_meta.get("snippet") or "Quoted text"
            r_mid = reply_meta.get("message_id")
            top_header_controls.append(
                ft.Container(
                    ink=True,
                    on_click=lambda e, t_mid=r_mid: _jump_to_message(t_mid),
                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.BLACK if not is_me else ft.Colors.WHITE),
                    border=ft.Border.only(left=ft.BorderSide(3, palette["accent"] if not is_me else ft.Colors.WHITE_70)),
                    border_radius=6,
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    margin=ft.Margin.only(bottom=4),
                    content=ft.Column([
                        ft.Text(r_sender, size=11, weight=ft.FontWeight.BOLD, color=palette["accent"] if not is_me else ft.Colors.WHITE),
                        ft.Text(r_snip, size=11, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS, color=ts_color),
                    ], spacing=2, tight=True)
                )
            )

        has_top_headers = bool(top_header_controls) and not is_deleted
        if has_top_headers:
            body_controls.extend(top_header_controls)

        # 0.2 Lightweight media attachment link (native Flutter URL launch, zero UI thread lag)
        if media_url and not is_deleted:
            f_name = meta.get("filename") or "Media Attachment"
            f_size = meta.get("file_size")
            attach_label = f"{f_name} ({f_size})" if f_size else f_name

            body_controls.append(
                ft.Container(
                    url=media_url,
                    padding=ft.Padding.symmetric(horizontal=10, vertical=7),
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.14, palette["accent"] if not is_me else ft.Colors.WHITE),
                    ink=True,
                    tooltip="Open in browser",
                    content=ft.Row([
                        ft.Icon(ft.Icons.ATTACH_FILE_ROUNDED, size=16, color=palette["accent"] if not is_me else ft.Colors.WHITE),
                        ft.Column([
                            ft.Text(
                                attach_label,
                                size=12,
                                weight=ft.FontWeight.W_600,
                                color=palette["accent"] if not is_me else ft.Colors.WHITE,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            ft.Text(
                                "Open in browser",
                                size=10,
                                color=palette["accent"] if not is_me else ft.Colors.WHITE_70,
                            ),
                        ], spacing=1, expand=True, tight=True),
                        ft.Icon(ft.Icons.OPEN_IN_NEW_ROUNDED, size=14, color=palette["accent"] if not is_me else ft.Colors.WHITE_70),
                    ], spacing=8, tight=False, vertical_alignment=ft.CrossAxisAlignment.CENTER)
                )
            )
        elif (meta.get("media_type") == "voice_note" or meta.get("type") == "voice_note") and not is_deleted:
            body_controls.append(
                ft.Container(
                    margin=ft.Margin.only(bottom=6),
                    padding=ft.Padding.symmetric(horizontal=8, vertical=6),
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.BLACK),
                    content=ft.Row([
                        ft.Icon(ft.Icons.PLAY_CIRCLE_FILLED_ROUNDED, size=24, color=palette["accent"]),
                        ft.Text("Voice Note", size=12, weight=ft.FontWeight.W_600, color=text_color),
                        ft.Container(expand=True),
                        ft.Icon(ft.Icons.GRAPHIC_EQ_ROUNDED, size=18, color=ts_color),
                    ], spacing=6, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER)
                )
            )

        # 2. Interactive Poll Rendering (Clean, lightweight design mirroring reference image)
        poll_updater_fn = [None]
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

            # Voter profile photo and name lookup helper for mini avatar badges
            def _get_voter_avatar_info(uid_str):
                uid_clean = str(uid_str or "").strip().lower()
                if uid_clean == my_id:
                    cu = {}
                    if hasattr(page, "session") and hasattr(page.session, "store"):
                        cu = page.session.store.get("current_user") or {}
                    img_url = cu.get("profile_picture_url") or cu.get("avatar_url")
                    my_name = f"{cu.get('first_name', '')} {cu.get('last_name', '')}".strip() or cu.get("username", "You")
                    if not img_url:
                        for u in all_users_cache:
                            if str(u.get("id") or u.get("user_id", "")).strip().lower() == my_id:
                                img_url = u.get("profile_picture_url") or u.get("avatar_url")
                                if not my_name or my_name == "You":
                                    my_name = (u.get("name") or u.get("full_name") or u.get("username") or "You").strip()
                                break
                    tokens = [t for t in my_name.split() if t]
                    if len(tokens) >= 2:
                        inits = (tokens[0][0] + tokens[1][0]).upper()
                    elif tokens and len(tokens[0]) >= 2:
                        inits = tokens[0][:2].upper()
                    elif tokens:
                        inits = tokens[0][0].upper()
                    else:
                        inits = "U"
                    has_img = bool(img_url and isinstance(img_url, str) and (img_url.startswith("http") or img_url.startswith("data:")))
                    return (img_url if has_img else None, inits, my_name)

                u = all_users_dict.get(uid_clean)
                if u:
                    name = (u.get("name") or u.get("full_name") or u.get("username") or "User").strip()
                    img_url = u.get("profile_picture_url") or u.get("avatar_url")
                    tokens = [t for t in name.split() if t]
                    if len(tokens) >= 2:
                        inits = (tokens[0][0] + tokens[1][0]).upper()
                    elif tokens and len(tokens[0]) >= 2:
                        inits = tokens[0][:2].upper()
                    elif tokens:
                        inits = tokens[0][0].upper()
                    else:
                        inits = "U"
                    has_img = bool(img_url and isinstance(img_url, str) and (img_url.startswith("http") or img_url.startswith("data:")))
                    return (img_url if has_img else None, inits, name)

                return (None, "U", "User")

            is_multi = meta.get("is_multi_select", False)
            opt_ui_map = {}
            poll_options_col = []

            def _build_voter_avatars(opt_voters_list):
                voter_avatars_list = []
                if opt_voters_list:
                    for v_uid in opt_voters_list[:3]:
                        v_img, v_inits, v_name = _get_voter_avatar_info(v_uid)
                        is_me_voter = (v_uid == my_id)

                        if v_img:
                            avatar_content = ft.CircleAvatar(
                                foreground_image_src=v_img,
                                radius=9,
                            )
                        else:
                            avatar_content = ft.Text(
                                v_inits,
                                size=7.5,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.WHITE
                            )

                        voter_avatars_list.append(
                            ft.Container(
                                width=18,
                                height=18,
                                border_radius=9,
                                clip_behavior=ft.ClipBehavior.HARD_EDGE,
                                bgcolor=palette["accent"] if is_me_voter else palette["accent_glow"],
                                border=ft.Border.all(1.5, bg),
                                alignment=ft.Alignment.CENTER,
                                tooltip=v_name,
                                content=avatar_content
                            )
                        )
                    if len(opt_voters_list) > 3:
                        voter_avatars_list.append(
                            ft.Container(
                                height=18,
                                padding=ft.Padding.symmetric(horizontal=4),
                                border_radius=9,
                                bgcolor=palette["surface_variant"],
                                border=ft.Border.all(1.5, bg),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Text(f"+{len(opt_voters_list) - 3}", size=8, weight=ft.FontWeight.BOLD, color=palette["text_muted"])
                            )
                        )
                return ft.Row(voter_avatars_list, spacing=-4, tight=True) if voter_avatars_list else ft.Container()

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

                async def _cast_vote_async(target_opt, p_id):
                    # If poll ID is temporary client ID, wait briefly for server UUID reconciliation
                    if str(p_id or "").startswith("client_"):
                        for _ in range(15):
                            await asyncio.sleep(0.1)
                            for ctrl in messages_listview.controls:
                                c_msg = getattr(ctrl, "msg_data", None)
                                if c_msg is msg or getattr(ctrl, "client_msg_id", None) == str(p_id):
                                    real_d = str(getattr(ctrl, "data", "") or "")
                                    if real_d and not real_d.startswith("client_"):
                                        p_id = real_d
                                        msg["id"] = real_d
                                        break
                            if not str(p_id or "").startswith("client_"):
                                break

                    sent = False
                    if ws_client_ref[0] and current_chat_id[0] and getattr(ws_client_ref[0], "websocket", None):
                        try:
                            sent = await ws_client_ref[0].send_message(
                                current_chat_id[0],
                                target_opt,
                                "poll_vote",
                                poll_id=p_id
                            )
                        except Exception as ws_err:
                            print(f"[NuChat] Poll vote WS error: {ws_err}")
                            sent = False

                    if not sent and current_chat_id[0]:
                        curr_token = token or (await page.shared_preferences.get("auth_token"))
                        if curr_token:
                            try:
                                rest_res = await vote_poll_message_api(curr_token, current_chat_id[0], p_id, target_opt)
                                if rest_res and "metadata_payload" in rest_res:
                                    sent = True
                            except Exception as rest_err:
                                print(f"[NuChat] Poll vote REST fallback error: {rest_err}")

                    if not sent:
                        show_page_snackbar(page, ft.SnackBar(content=ft.Text("Vote failed to send. Check connection."), bgcolor=ft.Colors.AMBER_800))

                def _cast_vote(e, target_opt=opt_str):
                    # 1. OPTIMISTIC IN-MEMORY UPDATE (Instant 0ms visual latency)
                    active_poll_id = str(msg.get("id") or poll_id)
                    try:
                        v_dict = meta.get("votes") or {}
                        if isinstance(v_dict, str):
                            try: v_dict = json.loads(v_dict)
                            except Exception: v_dict = {}
                        if not isinstance(v_dict, dict):
                            v_dict = {}

                        # Find and pop any existing vote for current user case-insensitively
                        existing_user_key = next((k for k in list(v_dict.keys()) if str(k).strip().lower() == my_id), None)
                        current_val = v_dict.pop(existing_user_key) if existing_user_key is not None else None

                        if is_multi:
                            u_v = current_val if isinstance(current_val, list) else ([current_val] if current_val else [])
                            match_idx = next((i for i, x in enumerate(u_v) if str(x).strip().lower() == target_opt.lower()), None)
                            if match_idx is not None:
                                u_v.pop(match_idx)
                            else:
                                u_v.append(target_opt)
                            if u_v:
                                v_dict[my_id] = u_v
                        else:
                            # Single-choice: toggle off if tapping identical choice, otherwise switch choice to new option!
                            if current_val and str(current_val).strip().lower() == target_opt.lower():
                                pass
                            else:
                                v_dict[my_id] = target_opt

                        meta["votes"] = v_dict
                        msg["metadata_payload"] = meta

                        # Tactile micro-bounce on clicked option tile
                        target_ui = opt_ui_map.get(target_opt.lower())
                        if target_ui and target_ui.get("tile"):
                            target_ui["tile"].scale = 0.95

                        # Smooth in-place animated update without destroying the bubble
                        if poll_updater_fn[0] is not None:
                            poll_updater_fn[0](meta)
                        else:
                            target_idx = None
                            for idx, ctrl in enumerate(messages_listview.controls):
                                c_msg = getattr(ctrl, "msg_data", None)
                                if c_msg is msg:
                                    target_idx = idx
                                    c_d = str(getattr(ctrl, "data", "") or "")
                                    if c_d and not c_d.startswith("client_"):
                                        active_poll_id = c_d
                                        msg["id"] = c_d
                                    break
                                c_d = str(getattr(ctrl, "data", "") or "")
                                c_cid = str(getattr(ctrl, "client_msg_id", "") or "")
                                if (c_d and c_d == active_poll_id) or (c_cid and c_cid == active_poll_id):
                                    target_idx = idx
                                    if c_d and not c_d.startswith("client_"):
                                        active_poll_id = c_d
                                        msg["id"] = c_d
                                    break

                            if target_idx is not None:
                                _replace_bubble_in_place(target_idx, msg, do_update=True)
                    except Exception as opt_err:
                        print(f"[NuChat] Optimistic vote render error: {opt_err}")

                    # 2. Resilient background dispatch (WebSocket + REST fallback)
                    page.run_task(_cast_vote_async, target_opt, active_poll_id)

                # Identify users who voted for this option
                opt_voters = []
                for uid_k, u_vote in votes.items():
                    selected = u_vote if isinstance(u_vote, list) else [u_vote]
                    if any(str(v).strip().lower() == opt_str.lower() for v in selected):
                        opt_voters.append(str(uid_k).strip().lower())

                voter_avatars_widget = ft.Container(
                    content=_build_voter_avatars(opt_voters)
                )

                vote_label = f"{count} vote{'s' if count != 1 else ''}"
                if total_votes > 0:
                    vote_label += f" • {int(pct * 100)}%"

                opt_title_text = ft.Text(
                    opt_str,
                    size=13,
                    weight=ft.FontWeight.BOLD if has_voted_this else ft.FontWeight.W_500,
                    color=palette["accent"] if has_voted_this else text_color,
                    no_wrap=False
                )
                vote_label_text = ft.Text(
                    vote_label,
                    size=11,
                    weight=ft.FontWeight.BOLD if has_voted_this else ft.FontWeight.W_500,
                    color=palette["accent"] if has_voted_this else palette["text_muted"]
                )
                prog_bar = ft.ProgressBar(
                    value=pct,
                    color=palette["accent"] if has_voted_this else palette["bar_other"],
                    bgcolor=palette["surface_variant"],
                    height=6,
                    border_radius=3
                )

                # Option tile row: [Radio] [Label] ... [Count • %]
                opt_tile = ft.Container(
                    ink=True,
                    on_click=_cast_vote,
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.12, palette["accent"]) if has_voted_this else ft.Colors.TRANSPARENT,
                    border=ft.Border.all(1.2, ft.Colors.with_opacity(0.5, palette["accent"])) if has_voted_this else ft.Border.all(1, ft.Colors.with_opacity(0.08, palette["text"])),
                    padding=ft.Padding.symmetric(horizontal=8, vertical=6),
                    scale=1.0,
                    animate_scale=ft.Animation(180, ft.AnimationCurve.EASE_OUT_BACK),
                    animate=ft.Animation(220, ft.AnimationCurve.EASE_OUT_CUBIC),
                    content=ft.Column([
                        ft.Row([
                            ft.Container(
                                expand=True,
                                content=opt_title_text
                            ),
                            vote_label_text
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.Row([
                            ft.Container(
                                expand=True,
                                content=prog_bar
                            ),
                            voter_avatars_widget
                        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)
                    ], spacing=5)
                )
                poll_options_col.append(opt_tile)
                opt_ui_map[opt_str.lower()] = {
                    "tile": opt_tile,
                    "title": opt_title_text,
                    "label": vote_label_text,
                    "bar": prog_bar,
                    "voters_holder": voter_avatars_widget,
                    "opt_str": opt_str
                }

            total_votes_text = ft.Text(
                f"{total_votes} vote{'s' if total_votes != 1 else ''}",
                size=11,
                color=palette["text_muted"],
                weight=ft.FontWeight.W_500
            )
            view_votes_link = ft.Container(
                ink=True,
                visible=(total_votes > 0),
                on_click=lambda e, m=msg: open_poll_breakdown_modal(m),
                content=ft.Text("• View votes", size=11, color=palette["accent"], weight=ft.FontWeight.BOLD)
            )

            # Clear differentiator for single-choice vs multi-choice voting
            poll_mode_indicator = ft.Row([
                ft.Icon(
                    ft.Icons.CHECKLIST_ROUNDED if is_multi else ft.Icons.RADIO_BUTTON_CHECKED_ROUNDED,
                    size=12,
                    color=palette["accent"]
                ),
                ft.Text(
                    "Select one or more" if is_multi else "Select one",
                    size=11,
                    color=palette["text_muted"],
                    weight=ft.FontWeight.W_500
                ),
            ], spacing=4, tight=True)

            # Minimalist card body: title + voting mode + options + subtle votes count with "View votes" link + timestamp
            poll_card = ft.Column([
                ft.Text(poll_title, size=15, weight=ft.FontWeight.BOLD, color=text_color),
                poll_mode_indicator,
                ft.Container(height=2),
                *poll_options_col,
                ft.Container(height=6),
                ft.Row([
                    ft.Row([
                        total_votes_text,
                        view_votes_link
                    ], spacing=6, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ts_row
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)
            ], spacing=5, tight=True)
            body_controls.append(poll_card)

            def _apply_poll_update(new_meta):
                _unfreeze_control(poll_card)
                u_votes = new_meta.get("votes") or {}
                if isinstance(u_votes, str):
                    try: u_votes = json.loads(u_votes)
                    except Exception: u_votes = {}
                if not isinstance(u_votes, dict):
                    u_votes = {}

                u_total = len(u_votes)
                u_opt_counts = {}
                u_opt_voters = {}
                for uid_k, v_val in u_votes.items():
                    uid_clean = str(uid_k).strip().lower()
                    sel = v_val if isinstance(v_val, list) else [v_val]
                    for s_item in sel:
                        s_k = str(s_item).strip().lower()
                        u_opt_counts[s_k] = u_opt_counts.get(s_k, 0) + 1
                        if s_k not in u_opt_voters:
                            u_opt_voters[s_k] = []
                        u_opt_voters[s_k].append(uid_clean)

                u_my_vote = None
                for u_k, u_v in u_votes.items():
                    if str(u_k).strip().lower() == my_id:
                        u_my_vote = u_v
                        break

                for opt_k, ui in opt_ui_map.items():
                    c_cnt = u_opt_counts.get(opt_k, 0)
                    c_pct = (c_cnt / u_total) if u_total > 0 else 0.0

                    if isinstance(u_my_vote, list):
                        c_voted = any(str(v).strip().lower() == opt_k for v in u_my_vote)
                    elif u_my_vote is not None:
                        c_voted = (str(u_my_vote).strip().lower() == opt_k)
                    else:
                        c_voted = False

                    _unfreeze_control(ui["tile"])
                    ui["tile"].scale = 1.0
                    ui["tile"].bgcolor = ft.Colors.with_opacity(0.12, palette["accent"]) if c_voted else ft.Colors.TRANSPARENT
                    ui["tile"].border = ft.Border.all(1.2, ft.Colors.with_opacity(0.5, palette["accent"])) if c_voted else ft.Border.all(1, ft.Colors.with_opacity(0.08, palette["text"]))

                    _unfreeze_control(ui["title"])
                    ui["title"].weight = ft.FontWeight.BOLD if c_voted else ft.FontWeight.W_500
                    ui["title"].color = palette["accent"] if c_voted else text_color

                    _unfreeze_control(ui["label"])
                    vl = f"{c_cnt} vote{'s' if c_cnt != 1 else ''}"
                    if u_total > 0:
                        vl += f" • {int(c_pct * 100)}%"
                    ui["label"].value = vl
                    ui["label"].weight = ft.FontWeight.BOLD if c_voted else ft.FontWeight.W_500
                    ui["label"].color = palette["accent"] if c_voted else palette["text_muted"]

                    _unfreeze_control(ui["bar"])
                    ui["bar"].value = c_pct
                    ui["bar"].color = palette["accent"] if c_voted else palette["bar_other"]

                    if ui.get("voters_holder"):
                        _unfreeze_control(ui["voters_holder"])
                        ui["voters_holder"].content = _build_voter_avatars(u_opt_voters.get(opt_k, []))

                _unfreeze_control(total_votes_text)
                total_votes_text.value = f"{u_total} vote{'s' if u_total != 1 else ''}"
                _unfreeze_control(view_votes_link)
                view_votes_link.visible = (u_total > 0)

                # Push patches for every modified child control to client
                dirty_controls = [poll_card]
                for ui in opt_ui_map.values():
                    dirty_controls.extend([ui["tile"], ui["title"], ui["label"], ui["bar"]])
                    if ui.get("voters_holder"):
                        dirty_controls.append(ui["voters_holder"])
                dirty_controls.extend([total_votes_text, view_votes_link])

                try:
                    page.update(*dirty_controls)
                except Exception:
                    try:
                        page.update()
                    except Exception:
                        pass

            poll_updater_fn[0] = _apply_poll_update

        # 3. Formatted Code Snippet Block
        elif not is_deleted and raw_content.startswith("```") and raw_content.endswith("```"):
            code_body = raw_content[3:-3].strip()
            first_line = code_body.split("\n", 1)[0].strip()
            lang = "CODE"
            if len(first_line) < 12 and "\n" in code_body:
                lang = first_line.upper()
                code_body = code_body.split("\n", 1)[1]

            def _copy_code(e, text_to_copy=code_body):
                try:
                    asyncio.create_task(safe_set_clipboard(page, text_to_copy))
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

        # 4. AI Response or Markdown-Formatted Chat Bubble
        elif not is_deleted:
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
                if matched_uid:
                    if matched_uid == my_id:
                        page.navigate("/profile")
                    else:
                        page.navigate(f"/member/{matched_uid}")
                else:
                    show_page_snackbar(page, ft.SnackBar(content=ft.Text(f"Mentioned {u}"), duration=1500))

            clean_text = (raw_content or "").strip()
            is_dummy_image_caption = bool(media_url and (not clean_text or clean_text.lower() == "shared an image" or clean_text == media_url))
            if not is_dummy_image_caption and clean_text:
                if is_ai or has_block_markdown(clean_text):
                    body_controls.append(
                        build_chat_markdown(
                            clean_text,
                            text_color,
                            palette,
                            on_mention_click=_on_mention_click,
                            is_me=is_me,
                            page=page,
                        )
                    )
                else:
                    body_controls.append(
                        ft.Text(
                            spans=build_whatsapp_spans(clean_text, text_color, palette, _on_mention_click, is_me=is_me),
                            size=14,
                            selectable=True
                        )
                    )

        # Timestamp row (already embedded inside poll_card for polls)
        if not is_poll and not is_deleted:
            body_controls.append(ts_row)

        def _copy_bubble_text(e=None):
            if raw_content:
                asyncio.create_task(safe_set_clipboard(page, raw_content))
                show_page_snackbar(page, ft.SnackBar(content=ft.Text("Message text copied"), duration=1500))

        def _open_actions_sheet(e=None):
            open_message_actions_sheet(
                page=page,
                msg=msg,
                palette=palette,
                current_user_id=current_user_id[0],
                is_admin=_is_current_user_admin(),
                on_set_reply=_set_reply,
                on_send_reaction=_send_ws_reaction,
                on_send_pin=_send_ws_pin,
                on_send_unpin=_send_ws_unpin,
                on_send_delete=_send_ws_delete,
                on_copy_text=_copy_bubble_text,
                pinned_msg_target_id=pinned_msg_target_id,
                is_me=is_me,
                on_close_callback=None,
            )

        _guarded_actions_click = debounced_click(_open_actions_sheet, min_interval_ms=400)

        cur_w = page.width if (hasattr(page, "width") and page.width) else 380
        max_bubble_width = min(540, max(220, int(cur_w * 0.72))) if not is_mob else max(180, int(cur_w - 104))
        bubble_width = min(320, max_bubble_width) if is_poll else None

        bubble = ft.Container(
            width=bubble_width,
            max_width=max_bubble_width,
            bgcolor=bg,
            border=border,
            border_radius=radius,
            padding=ft.Padding.symmetric(horizontal=12, vertical=8) if is_deleted else ft.Padding.symmetric(horizontal=14 if is_poll else 12, vertical=12 if is_poll else 8),
            on_long_press=_guarded_actions_click if not is_deleted else None,
            shadow=ft.BoxShadow(
                blur_radius=4 if is_poll else 3,
                color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
                offset=ft.Offset(0, 1)
            ),
            scale=ft.Scale(0.82, alignment=ft.Alignment.BOTTOM_RIGHT if is_me else ft.Alignment.BOTTOM_LEFT) if animate_entrance else 1.0,
            opacity=0.0 if animate_entrance else 1.0,
            offset=ft.Offset(0.04, 0.10) if (animate_entrance and is_me) else (ft.Offset(-0.04, 0.10) if animate_entrance else ft.Offset(0, 0)),
            animate_scale=ft.Animation(230, ft.AnimationCurve.EASE_OUT_BACK) if animate_entrance else None,
            animate_opacity=ft.Animation(160, ft.AnimationCurve.EASE_OUT) if animate_entrance else None,
            animate_offset=ft.Animation(230, ft.AnimationCurve.EASE_OUT_BACK) if animate_entrance else None,
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

        msg_id_str = str(msg.get("id") or "")
        reactions_row = build_reaction_pills_row(
            meta.get("reactions"),
            current_user_id[0],
            lambda emoji_val, mid=msg_id_str: _send_ws_reaction(mid, emoji_val),
            palette
        )
        reactions_holder = ft.Container(content=reactions_row)

        # Message options (3-dots) visible across all form factors (both mobile and desktop)
        bubble_options_btn = ft.IconButton(
            icon=ft.Icons.MORE_HORIZ_ROUNDED,
            icon_color=palette["text_muted"],
            icon_size=18,
            tooltip="Message options",
            on_click=_guarded_actions_click,
            style=ft.ButtonStyle(padding=2)
        )

        # ── WhatsApp-Style Swipe-to-Reply with 50% Hard Clamping Wall ─────────
        # When is_me: bubble is on the RIGHT -> user MUST swipe LEFT (dx < 0).
        # When other: bubble is on the LEFT  -> user MUST swipe RIGHT (dx > 0).
        # Swiping in the wrong direction is strictly ignored (0 movement).
        # Movement is hard-clamped at exactly 50% (the wall) so it NEVER leaves the screen.
        reply_badge_icon = ft.Icon(
            ft.Icons.REPLY_ROUNDED,
            size=18,
            color=palette["accent"]
        )
        reply_badge = ft.Container(
            width=36,
            height=36,
            border_radius=18,
            bgcolor=palette["accent_glow"],
            alignment=ft.Alignment.CENTER,
            scale=ft.Scale(0.0),
            opacity=0.0,
            animate_scale=ft.Animation(150, ft.AnimationCurve.EASE_OUT_BACK),
            animate_opacity=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
            shadow=ft.BoxShadow(
                blur_radius=6,
                color=ft.Colors.with_opacity(0.25, ft.Colors.BLACK),
                offset=ft.Offset(0, 2)
            ),
            content=reply_badge_icon,
        )

        badge_holder = ft.Container(
            content=reply_badge,
            top=0,
            bottom=0,
            right=6 if is_me else None,
            left=6 if not is_me else None,
            alignment=ft.Alignment.CENTER,
        )

        swipe_state = {
            "dx": 0.0,
            "triggered": False,
            "active": False,
        }

        # Reference width for computing fractional translation:
        # Clamped at 50% (0.50) of the bubble's extent.
        ref_extent = float(bubble_width or max_bubble_width or 240)

        def _extract_drag_dx(e) -> float:
            p_delta = getattr(e, "primary_delta", None)
            if p_delta is not None:
                try:
                    return float(p_delta)
                except Exception:
                    pass
            ld = getattr(e, "local_delta", None)
            if ld and hasattr(ld, "x"):
                try:
                    return float(getattr(ld, "x", 0.0) or 0.0)
                except Exception:
                    pass
            gd = getattr(e, "global_delta", None)
            if gd and hasattr(gd, "x"):
                try:
                    return float(getattr(gd, "x", 0.0) or 0.0)
                except Exception:
                    pass
            return float(getattr(e, "delta_x", 0.0) or 0.0)

        def _on_swipe_start(e):
            _unfreeze_control(bubble)
            _unfreeze_control(reply_badge)
            _unfreeze_control(reply_badge_icon)
            swipe_state["dx"] = 0.0
            swipe_state["triggered"] = False
            swipe_state["active"] = True
            bubble.animate_offset = None

        def _on_swipe_update(e):
            if not swipe_state["active"]:
                return
            delta_val = _extract_drag_dx(e)
            swipe_state["dx"] += delta_val
            raw_dx = swipe_state["dx"]

            # DIRECTION ENFORCEMENT:
            # is_me: MUST swipe LEFT (raw_dx < 0). Swiping right (raw_dx > 0) is strictly forbidden.
            # not is_me: MUST swipe RIGHT (raw_dx > 0). Swiping left (raw_dx < 0) is strictly forbidden.
            if is_me:
                if raw_dx > 0.0:
                    raw_dx = 0.0
                    swipe_state["dx"] = 0.0
            else:
                if raw_dx < 0.0:
                    raw_dx = 0.0
                    swipe_state["dx"] = 0.0

            # Compute fraction relative to bubble extent
            raw_frac = raw_dx / max(120.0, ref_extent)

            # HARD CLAMPING AT 50% WALL:
            # If is_me: clamp strictly between -0.50 and 0.0
            # If not is_me: clamp strictly between 0.0 and +0.50
            if is_me:
                clamped_frac = max(-0.50, min(0.0, raw_frac))
            else:
                clamped_frac = min(0.50, max(0.0, raw_frac))

            _unfreeze_control(bubble)
            _unfreeze_control(reply_badge)
            _unfreeze_control(reply_badge_icon)
            bubble.animate_offset = None
            bubble.offset = ft.Offset(clamped_frac, 0)

            abs_frac = abs(clamped_frac)
            abs_px = abs(raw_dx)

            if abs_px > 4.0:
                reply_badge.opacity = min(1.0, abs_px / 22.0)
                reply_badge.scale = ft.Scale(min(1.0, abs_px / 32.0))
                # Threshold reached when dragged >= 35% or >= 40px
                if abs_frac >= 0.35 or abs_px >= 40.0:
                    swipe_state["triggered"] = True
                    reply_badge.bgcolor = palette["accent"]
                    reply_badge_icon.color = ft.Colors.WHITE
                else:
                    swipe_state["triggered"] = False
                    reply_badge.bgcolor = palette["accent_glow"]
                    reply_badge_icon.color = palette["accent"]
            else:
                reply_badge.opacity = 0.0
                reply_badge.scale = ft.Scale(0.0)

            try:
                bubble.update()
                reply_badge.update()
            except Exception:
                pass

        def _on_swipe_end(e):
            if not swipe_state["active"]:
                return
            swipe_state["active"] = False
            velocity = getattr(e, "primary_velocity", 0.0) or 0.0
            swipe_state["dx"] = 0.0

            # Velocity-based flick recognition in valid direction
            if is_me and velocity <= -280.0:
                swipe_state["triggered"] = True
            elif (not is_me) and velocity >= 280.0:
                swipe_state["triggered"] = True

            was_triggered = swipe_state["triggered"]
            swipe_state["triggered"] = False

            _unfreeze_control(bubble)
            _unfreeze_control(reply_badge)
            _unfreeze_control(reply_badge_icon)
            # Spring bounce back to 0 (origin)
            bubble.animate_offset = ft.Animation(240, ft.AnimationCurve.EASE_OUT_BACK)
            bubble.offset = ft.Offset(0, 0)

            reply_badge.scale = ft.Scale(0.0)
            reply_badge.opacity = 0.0
            reply_badge.bgcolor = palette["accent_glow"]
            reply_badge_icon.color = palette["accent"]

            try:
                bubble.update()
                reply_badge.update()
            except Exception:
                pass

            if was_triggered:
                _set_reply(msg)

        def _on_swipe_cancel(e=None):
            if not swipe_state["active"]:
                return
            swipe_state["active"] = False
            swipe_state["dx"] = 0.0
            swipe_state["triggered"] = False
            _unfreeze_control(bubble)
            _unfreeze_control(reply_badge)
            _unfreeze_control(reply_badge_icon)
            bubble.animate_offset = ft.Animation(240, ft.AnimationCurve.EASE_OUT_BACK)
            bubble.offset = ft.Offset(0, 0)
            reply_badge.scale = ft.Scale(0.0)
            reply_badge.opacity = 0.0
            try:
                bubble.update()
                reply_badge.update()
            except Exception:
                pass

        if is_deleted:
            bubble_options_btn.visible = False
            bubble_swipe_stack = bubble
            row_items = [bubble]
            reactions_holder.visible = False
        else:
            bubble_gesture = ft.GestureDetector(
                content=bubble,
                drag_interval=20,
                on_horizontal_drag_start=_on_swipe_start,
                on_horizontal_drag_update=_on_swipe_update,
                on_horizontal_drag_end=_on_swipe_end,
                on_horizontal_drag_cancel=_on_swipe_cancel,
                on_long_press=_guarded_actions_click,
            )

            bubble_swipe_stack = ft.Stack(
                controls=[
                    badge_holder,
                    bubble_gesture,
                ]
            )

            bubble_options_btn.visible = True
            row_items = [bubble_options_btn, bubble_swipe_stack] if is_me else [bubble_swipe_stack, bubble_options_btn]

        bubble_col = ft.Column(
            [
                ft.Row(
                    row_items,
                    spacing=2,
                    tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),
                reactions_holder,
            ],
            tight=True,
            spacing=1,
            horizontal_alignment=ft.CrossAxisAlignment.END if is_me else ft.CrossAxisAlignment.START
        )

        stable_key = str(msg.get("id") or msg.get("client_msg_id") or "")
        if is_me:
            c = ft.Container(
                key=ft.ScrollKey(stable_key) if stable_key else None,
                content=ft.Row([bubble_col], alignment=ft.MainAxisAlignment.END),
                margin=ft.Margin(top=v_margin, bottom=v_margin, left=out_left_margin, right=out_right_margin)
            )
            c.data = str(msg.get("id"))
            c.client_msg_id = str(msg.get("client_msg_id") or "")
            c.msg_data = msg
            c.status_tick = status_tick
            c.bubble_ref = bubble
            c.reactions_holder = reactions_holder
            c.is_me_bubble = True
            if poll_updater_fn[0] is not None:
                c.update_poll_state = poll_updater_fn[0]
            return c
        else:
            # Show avatar only on last message of cluster (or single message)
            if not next_is_same:
                sender_initials = "".join([t[0] for t in sender_name.split()[:2]]).upper() or "?"
                sender_avatar_url = (msg.get("sender") or {}).get("profile_picture_url")
                has_s_img = bool(sender_avatar_url and isinstance(sender_avatar_url, str) and (sender_avatar_url.startswith("http") or sender_avatar_url.startswith("data:")))
                if is_ai:
                    avatar_ctrl = ft.Container(
                        width=28,
                        height=28,
                        border_radius=14,
                        bgcolor=ft.Colors.with_opacity(0.18, palette["accent"]),
                        border=ft.Border.all(1.5, palette["accent"]),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=14, color=palette["accent"])
                    )
                else:
                    avatar_ctrl = ft.CircleAvatar(
                        foreground_image_src=sender_avatar_url if has_s_img else None,
                        content=ft.Text(sender_initials, size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        bgcolor=ft.Colors.with_opacity(0.85, palette["accent_glow"]),
                        radius=14
                    )
                if is_ai:
                    avatar_widget = ft.Container(
                        content=avatar_ctrl,
                        width=28,
                        height=28,
                        alignment=ft.Alignment.CENTER,
                        clip_behavior=ft.ClipBehavior.HARD_EDGE,
                        border_radius=14,
                        tooltip="Nu Study AI Assistant",
                        ink=False,
                    )
                else:
                    def _open_sender_profile(ev, sid=sender_id):
                        if sid:
                            if sid == my_id:
                                page.navigate("/profile")
                            else:
                                page.navigate(f"/member/{sid}")

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
                key=ft.ScrollKey(stable_key) if stable_key else None,
                content=ft.Row(
                    [avatar_widget, bubble_col],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.END,
                    spacing=6
                ),
                margin=ft.Margin(top=v_margin, bottom=v_margin, left=in_left_margin, right=in_right_margin)
            )
            c.data = str(msg.get("id"))
            c.client_msg_id = str(msg.get("client_msg_id") or "")
            c.msg_data = msg
            c.bubble_ref = bubble
            c.reactions_holder = reactions_holder
            c.is_me_bubble = False
            if poll_updater_fn[0] is not None:
                c.update_poll_state = poll_updater_fn[0]
            return c

    def _replace_bubble_in_place(idx: int, updated_msg: dict, do_update: bool = True):
        """
        Replaces a single message bubble in `messages_listview.controls` while
        preserving neighbor clustering (`prev_msg` / `next_msg`), `ScrollKey`,
        and current scroll position so the chat never jumps to the top.
        """
        if idx < 0 or idx >= len(messages_listview.controls):
            return
        prev_m = None
        for p_idx in range(idx - 1, -1, -1):
            pm = getattr(messages_listview.controls[p_idx], "msg_data", None)
            if isinstance(pm, dict):
                prev_m = pm
                break
        next_m = None
        for n_idx in range(idx + 1, len(messages_listview.controls)):
            nm = getattr(messages_listview.controls[n_idx], "msg_data", None)
            if isinstance(nm, dict):
                next_m = nm
                break
        new_ctrl = render_message_bubble(updated_msg, prev_msg=prev_m, next_msg=next_m, animate_entrance=False)
        messages_listview.controls[idx] = new_ctrl
        if do_update:
            try:
                messages_listview.update()
            except Exception:
                page.update()
            _restore_scroll_anchor()

    # ==========================================
    # 9. TYPING INDICATORS
    # ==========================================
    def show_typing_indicator(channel_id: str, sender_name: str):
        tok = datetime.now().timestamp()
        typing_tokens[channel_id] = tok

        # 1. Update left list state in-memory
        for chat in channels_list:
            if chat.get("channel_id") == channel_id:
                chat["is_typing"] = True
                chat["typing_name"] = sender_name
                break

        # 2. Update active chat header subtitle directly (zero sidebar re-render lag)
        if channel_id == current_chat_id[0]:
            active_chat_status_txt.value = f"{sender_name} is typing..." if sender_name and sender_name != "Someone" else "typing..."
            active_chat_status_txt.color = palette["online_dot"]
            try:
                active_chat_status_txt.update()
            except Exception:
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

            if current_chat_id[0] == channel_id:
                chat_info = next((c for c in channels_list if c.get("channel_id") == channel_id), {})
                is_online = chat_info.get("is_online", False)
                chat_type = chat_info.get("type", "direct")
                if chat_type == "direct":
                    active_chat_status_txt.value = "online" if is_online else "Offline"
                    active_chat_status_txt.color = palette["online_dot"] if is_online else palette["text_muted"]
                else:
                    active_chat_status_txt.value = f"{len(active_channel_members)} members" if active_channel_members else ""
                    active_chat_status_txt.color = palette["text_muted"]
                try:
                    active_chat_status_txt.update()
                except Exception:
                    page.update()

        page.run_task(clear_typing, tok)

    # ==========================================
    # 10. ACTIVE CHAT LOADER & SYNC
    # ==========================================
    async def load_active_chat(chat_id: str):
        chat_load_seq[0] += 1
        my_load_seq = chat_load_seq[0]
        chat_load_lock[0] = True

        try:
            current_chat_id[0] = chat_id
            chat_info = next((c for c in channels_list if c.get("channel_id") == chat_id), {"name": "Chat", "type": "direct"})
            chat_info["unread"] = 0
            chat_info["has_unread_mention"] = False
            active_chat_info[0] = chat_info
            render_chat_list()

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

            active_chat_status_txt.value = "Connecting..." if _chat_type == "direct" else "Loading members..."
            active_chat_status_txt.color = palette["text_muted"]

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

                        # Refresh header status and tagging candidate list immediately
                        if _chat_type != "direct" and current_chat_id[0] == c_id:
                            active_chat_status_txt.value = f"{len(active_channel_members)} members"
                            active_chat_status_txt.color = palette["text_muted"]
                            if getattr(active_chat_status_txt, "page", None):
                                active_chat_status_txt.update()
                    except Exception as e:
                        print(f"[NuChat] Error fetching channel members: {e}")
                page.run_task(_fetch_group_members_task)

            header_actions = [
                search_header_btn
            ]

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
                        page.navigate("/profile")
                    else:
                        page.navigate(f"/member/{target_uid}")

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
                no_wrap=True,
                expand=True,
            )
            if _chat_type == "direct":
                title_widget = ft.Container(
                    content=title_txt,
                    ink=True,
                    border_radius=4,
                    on_click=_nav_to_dm_profile,
                    tooltip=f"View {_chat_name}'s profile",
                    expand=True,
                )
            else:
                title_widget = title_txt

            title_row_controls = [title_widget]
            if _chat_type == "direct":
                other_badge = chat_info.get("primary_badge") or chat_info.get("other_user_badge")
                if not other_badge:
                    u = all_users_dict.get(str(_other_uid or "").strip().lower())
                    if u:
                        other_badge = u.get("primary_badge")
                if other_badge and isinstance(other_badge, dict):
                    title_row_controls.append(build_glossy_badge_pill(other_badge, is_mobile=not is_desktop[0], max_width=120))

            active_chat_header.controls = [
                back_btn,
                header_avatar,
                ft.Column([
                    ft.Row(title_row_controls, spacing=6, expand=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    active_chat_status_txt
                ], spacing=1, expand=True),
                *header_actions
            ]

            # Spinner during message load
            messages_listview.controls = [
                ft.Row([ft.ProgressRing(color=palette["accent"], width=24, height=24, stroke_width=2)],
                       alignment=ft.MainAxisAlignment.CENTER)
            ]

            # Reset search & pinned notice state for active chat
            last_scroll_pixels[0] = 0.0
            last_max_scroll[0] = 0.0
            is_near_bottom[0] = True
            _close_in_room_search(do_update=False)
            pinned_notice_bar.visible = False
            pinned_notice_text.value = ""
            pinned_msg_target_id[0] = None
            _cancel_reply(do_update=False)

            # Mount Active Chat Panel
            active_chat_panel.content = ft.Column([
                # Top Room Header with Search & Pinned Bar
                ft.Container(
                    bgcolor=palette["header_bg"],
                    border=ft.Border.only(bottom=ft.BorderSide(1, palette["border"])),
                    padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                    content=ft.Column([
                        active_chat_header,
                        in_room_search_container,
                        pinned_notice_bar,
                    ], spacing=4, tight=True)
                ),
                # Message History View with Upward Fade Animation
                messages_anim_container,
                # Bottom Input Composer with Autocomplete Overlay and Reply Bar
                ft.Column([
                    autocomplete_card,
                    reply_bar_container,
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
                                on_click=debounced_click(lambda e: open_attachment_actions_modal(e), min_interval_ms=400)
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

            has_animated_room = [False]

            # --- 1. RENDER FROM LOCAL SQLITE CACHE ---
            def _render_history(hist_list: list):
                messages_anim_container.opacity = 1.0
                messages_anim_container.offset = ft.Offset(0, 0)
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
                            margin=ft.Margin.symmetric(vertical=6),
                        )
                        date_row = ft.Row([date_pill], alignment=ft.MainAxisAlignment.CENTER)
                        date_row.bubble_ref = date_pill
                        date_row.is_me_bubble = False
                        messages_listview.controls.append(date_row)
                        current_date_label = m_date

                    prev_item = clean_msgs[i - 1] if i > 0 else None
                    next_item = clean_msgs[i + 1] if i < len(clean_msgs) - 1 else None
                    messages_listview.controls.append(render_message_bubble(m, prev_msg=prev_item, next_msg=next_item, animate_entrance=False))

                try:
                    messages_listview.update()
                except Exception:
                    page.update()
                _scroll_to_bottom(animate=False)

            cached_history = get_cached_messages(page, chat_id)
            cached_ids = []
            if cached_history:
                cached_ids = [str(m.get("id")) for m in cached_history if m.get("id")]
                _render_history(cached_history)

            # --- 2. NETWORK FETCH & SQLITE REFRESH ---
            history = await get_channel_messages(token, chat_id)
            if chat_load_seq[0] != my_load_seq or current_chat_id[0] != chat_id:
                return
            if isinstance(history, list):
                # Reverse to chronological order (API returns newest first)
                chronological = list(reversed(history))
                network_ids = [str(m.get("id")) for m in chronological if m.get("id")]

                formatted_msgs = []
                for m in chronological:
                    sdata = m.get("sender") or {}
                    m_type = m.get("type", "text")
                    meta_p = m.get("metadata_payload") or {}
                    if isinstance(meta_p, str):
                        try: meta_p = json.loads(meta_p)
                        except: meta_p = {}
                    is_m_ai = (
                        str(sdata.get("id", "")).lower() == "ai_assistant"
                        or str(sdata.get("name", "")).lower() in ("nu owl", "nu study ai", "ai assistant")
                        or (m_type == "ai_response" and str(sdata.get("id", "")).lower() in ("ai_assistant", "unknown", ""))
                    )
                    formatted_msgs.append({
                        "id": str(m.get("id")),
                        "channel_id": str(chat_id),
                        "sender_id": "ai_assistant" if is_m_ai else str(sdata.get("id", m.get("sender_id", ""))),
                        "sender_name": "Nu Owl" if is_m_ai else (str(sdata.get("name") or "Unknown").strip() or "Unknown"),
                        "type": "ai_response" if is_m_ai else m_type,
                        "content": m.get("content", ""),
                        "metadata_payload": json.dumps(meta_p) if meta_p else None,
                        "created_at": str(m.get("created_at", "")),
                        "status": str(m.get("status") or "sent")
                    })

                if formatted_msgs:
                    upsert_chat_messages(page, formatted_msgs)

                # Avoid wiping and re-rendering if cached messages already matched the server response
                if not cached_history:
                    _render_history(chronological)
                elif cached_ids and network_ids != cached_ids:
                    # Incremental append of new delta messages instead of full wipe & re-render
                    new_deltas = [m for m in chronological if str(m.get("id")) not in seen_msg_ids]
                    if new_deltas:
                        for m in new_deltas:
                            mid = str(m.get("id"))
                            if mid:
                                seen_msg_ids.add(mid)
                            prev_item = messages_listview.controls[-1].msg_data if (messages_listview.controls and hasattr(messages_listview.controls[-1], "msg_data")) else None
                            bubble_ctrl = render_message_bubble(m, prev_msg=prev_item, animate_entrance=False)
                            messages_listview.controls.append(bubble_ctrl)
                        try:
                            messages_listview.update()
                        except Exception:
                            page.update()
                        _scroll_to_bottom(animate=False)
                    elif len(network_ids) != len(cached_ids):
                        _render_history(chronological)

            # Update Online Status in Header
            _is_online = chat_info.get("is_online", False)
            _chat_type = chat_info.get("type", "direct")
            if _chat_type == "direct":
                active_chat_status_txt.value = "online" if _is_online else "Offline"
                active_chat_status_txt.color = palette["online_dot"] if _is_online else palette["text_muted"]
            else:
                active_chat_status_txt.value = f"{len(active_channel_members)} members" if active_channel_members else ""
                active_chat_status_txt.color = palette["text_muted"]
            try:
                active_chat_status_txt.update()
            except Exception:
                page.update()

            # --- 3. FETCH PINNED MESSAGE CONCURRENTLY IN BACKGROUND ---
            async def _fetch_pinned_note(c_id=chat_id):
                try:
                    p_data = await get_pinned_chat_message(token, c_id)
                    if current_chat_id[0] != c_id:
                        return
                    if p_data and isinstance(p_data, dict) and p_data.get("id"):
                        pinned_msg_target_id[0] = p_data.get("id")
                        p_snip = p_data.get("content") or "Pinned notice"
                        pinned_notice_text.value = f"📌 Pinned: {p_snip[:60]}"
                        pinned_notice_bar.visible = True
                        unpin_btn.visible = _is_current_user_admin()
                        try:
                            pinned_notice_bar.update()
                        except Exception:
                            page.update()
                    else:
                        pinned_msg_target_id[0] = None
                        if pinned_notice_bar.visible:
                            pinned_notice_bar.visible = False
                            try:
                                pinned_notice_bar.update()
                            except Exception:
                                page.update()
                except Exception as p_err:
                    print(f"[NuChat] Error fetching pinned message: {p_err}")

            page.run_task(_fetch_pinned_note, chat_id)

            # --- 4. CONNECT LIVE WEBSOCKET IN BACKGROUND (0ms UI BLOCK) ---
            async def _bg_connect_and_read(c_id=chat_id):
                try:
                    if not ws_client_ref[0] or not getattr(ws_client_ref[0], "websocket", None):
                        if not ws_client_ref[0]:
                            ws_client_ref[0] = ChatWebSocketClient(token)
                        connected = await ws_client_ref[0].connect(handle_incoming_message)
                    else:
                        connected = True
                    if connected and current_chat_id[0] == c_id:
                        await ws_client_ref[0].send_message(c_id, "", "read_receipt")
                except Exception as conn_err:
                    print(f"[NuChat] Background websocket connect notice: {conn_err}")

            page.run_task(_bg_connect_and_read, chat_id)

        except Exception as ex:
            print(f"[NuChat] Error loading active chat {chat_id}: {ex}")
        finally:
            if chat_load_seq[0] == my_load_seq:
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

            if incoming_channel_id == current_chat_id[0]:
                active_chat_status_txt.value = "online" if is_online else "Offline"
                active_chat_status_txt.color = palette["online_dot"] if is_online else palette["text_muted"]
                try:
                    active_chat_status_txt.update()
                except Exception:
                    page.update()
            return

        # ── Reaction Update ──────────────────────────────────────────────────
        if msg_type == "reaction_update":
            target_mid = str(msg_dict.get("message_id") or "").strip().lower()
            new_reactions = msg_dict.get("reactions", {})
            curr_cid = str(current_chat_id[0] or "").strip().lower()
            incoming_cid = str(incoming_channel_id or "").strip().lower()
            if incoming_cid == curr_cid:
                _update_bubble_reactions_in_place(target_mid, new_reactions=new_reactions if isinstance(new_reactions, dict) else {})
            return

        # ── Pin Update ────────────────────────────────────────────────────────
        if msg_type == "pin_update":
            curr_cid = str(current_chat_id[0] or "").strip().lower()
            incoming_cid = str(incoming_channel_id or "").strip().lower()
            if incoming_cid == curr_cid:
                p_msg = msg_dict.get("pinned_message")
                if p_msg and isinstance(p_msg, dict):
                    pinned_msg_target_id[0] = p_msg.get("id")
                    p_snip = p_msg.get("content") or "Pinned notice"
                    pinned_notice_text.value = f"📌 Pinned: {p_snip[:60]}"
                    pinned_notice_bar.visible = True
                    unpin_btn.visible = _is_current_user_admin()
                else:
                    pinned_msg_target_id[0] = None
                    pinned_notice_bar.visible = False

                target_pin_str = str(pinned_msg_target_id[0]) if pinned_msg_target_id[0] else ""
                for idx, ctrl in enumerate(messages_listview.controls):
                    m_d = getattr(ctrl, "msg_data", {})
                    if isinstance(m_d, dict) and m_d.get("id"):
                        meta = m_d.get("metadata_payload") or {}
                        if isinstance(meta, str):
                            try: meta = json.loads(meta)
                            except: meta = {}
                        was_pinned = bool(meta.get("is_pinned"))
                        should_be_pinned = bool(target_pin_str and str(m_d.get("id")) == target_pin_str)
                        if was_pinned != should_be_pinned:
                            if should_be_pinned:
                                meta["is_pinned"] = True
                            else:
                                meta.pop("is_pinned", None)
                            m_d["metadata_payload"] = meta
                            ctrl.msg_data = m_d
                            _replace_bubble_in_place(idx, m_d, do_update=False)
                page.update()
                _restore_scroll_anchor()
            return

        # ── Message Deleted ───────────────────────────────────────────────────
        if msg_type == "message_deleted":
            target_mid = str(msg_dict.get("message_id") or msg_dict.get("id") or "").strip().lower()
            curr_cid = str(current_chat_id[0] or "").strip().lower()
            incoming_cid = str(incoming_channel_id or "").strip().lower()
            if incoming_cid == curr_cid:
                for idx, ctrl in enumerate(messages_listview.controls):
                    c_data = str(getattr(ctrl, "data", "") or "").strip().lower()
                    c_cid = str(getattr(ctrl, "client_msg_id", "") or "").strip().lower()
                    c_m = getattr(ctrl, "msg_data", {}) or {}
                    c_mid = str(c_m.get("id", "") or "").strip().lower() if isinstance(c_m, dict) else ""
                    c_cmid = str(c_m.get("client_msg_id", "") or "").strip().lower() if isinstance(c_m, dict) else ""
                    if target_mid and target_mid in (c_data, c_cid, c_mid, c_cmid):
                        m_d = getattr(ctrl, "msg_data", {})
                        if isinstance(m_d, dict):
                            m_d["content"] = "This message was deleted"
                            m_d["type"] = "text"
                            m_d["is_deleted"] = True
                            meta = m_d.get("metadata_payload") or {}
                            if isinstance(meta, str):
                                try: meta = json.loads(meta)
                                except Exception: meta = {}
                            if not isinstance(meta, dict):
                                meta = {}
                            meta["is_deleted"] = True
                            meta.pop("options", None)
                            meta.pop("poll_options", None)
                            meta.pop("votes", None)
                            m_d["metadata_payload"] = meta
                            _replace_bubble_in_place(idx, m_d, do_update=True)
                            break
            mark_cached_message_deleted(page, target_mid)
            return

        # ── AI Quota Exceeded System Error ───────────────────────────────────
        if msg_type == "system_error" and msg_dict.get("id") == "ai_quota_exceeded":
            open_chat_quota_modal(page, {"used": 15, "limit": 15})
            return

        # ── Typing Indicator ──────────────────────────────────────────────────
        if msg_type == "typing":
            sender_id = str((msg_dict.get("sender") or {}).get("id", "")).strip().lower()
            if sender_id != str(current_user_id[0]).strip().lower():
                show_typing_indicator(incoming_channel_id, (msg_dict.get("sender") or {}).get("name", "Someone"))
            return

        # ── Poll Update (Vote cast) ───────────────────────────────────────────
        if msg_type == "poll_update":
            poll_id = str(msg_dict.get("id", "") or "").strip().lower()
            incoming_cid = str(incoming_channel_id or "").strip().lower()
            curr_cid = str(current_chat_id[0] or "").strip().lower()
            if incoming_cid and curr_cid and incoming_cid == curr_cid:
                for idx, ctrl in enumerate(messages_listview.controls):
                    c_d = str(getattr(ctrl, "data", "") or "").strip().lower()
                    c_cid = str(getattr(ctrl, "client_msg_id", "") or "").strip().lower()
                    c_m = getattr(ctrl, "msg_data", {}) or {}
                    c_mid = str(c_m.get("id", "") or "").strip().lower() if isinstance(c_m, dict) else ""
                    if poll_id in (c_d, c_cid, c_mid):
                        p_meta = msg_dict.get("metadata_payload")
                        if isinstance(p_meta, str):
                            try: p_meta = json.loads(p_meta)
                            except: p_meta = None
                        if hasattr(ctrl, "update_poll_state") and callable(ctrl.update_poll_state) and isinstance(p_meta, dict):
                            ctrl.update_poll_state(p_meta)
                        else:
                            _replace_bubble_in_place(idx, msg_dict, do_update=True)
                        break
            try:
                upsert_chat_messages(page, [msg_dict])
            except Exception:
                pass
            return

        # ── Read Receipt (Double Cyan/Blue Ticks) ────────────────────────────
        if msg_type == "read_receipt":
            incoming_cid = str(incoming_channel_id or "").strip().lower()
            curr_cid = str(current_chat_id[0] or "").strip().lower()
            if incoming_cid and curr_cid and incoming_cid == curr_cid:
                reader_id = str((msg_dict.get("sender") or {}).get("id") or msg_dict.get("sender_id", "")).strip().lower()
                my_id_str = str(current_user_id[0]).strip().lower()
                if reader_id != my_id_str:
                    updated_any = False
                    for ctrl in messages_listview.controls:
                        mdata = getattr(ctrl, "msg_data", None)
                        if mdata and mdata.get("is_me"):
                            if mdata.get("status") != "read":
                                update_bubble_status(ctrl, "read")
                                updated_any = True
                    if updated_any:
                        page.update()
            return

        # ── Normal Message / Poll Creation ────────────────────────────────────
        msg_id = msg_dict.get("id")
        if not msg_id:
            return
        msg_id_str = str(msg_id)

        meta_payload = msg_dict.get("metadata_payload") or msg_dict.get("metadata") or {}
        if isinstance(meta_payload, str):
            try: meta_payload = json.loads(meta_payload)
            except: meta_payload = {}
        if not isinstance(meta_payload, dict):
            meta_payload = {}

        incoming_client_id = msg_dict.get("client_msg_id") or meta_payload.get("client_msg_id")
        sender_id_str = str((msg_dict.get("sender") or {}).get("id") or msg_dict.get("sender_id", "")).strip().lower()
        my_id_str = str(current_user_id[0]).strip().lower()
        is_own_message = (sender_id_str == my_id_str) or msg_dict.get("is_me", False)

        # Reconcile optimistic bubble if this is a server acknowledgment/broadcast of our in-flight message
        if incoming_client_id or is_own_message:
            for ctrl in messages_listview.controls:
                c_mid = getattr(ctrl, "client_msg_id", None) or getattr(ctrl, "data", None)
                c_data = getattr(ctrl, "msg_data", None) or {}
                matched = False
                if incoming_client_id and c_mid and str(c_mid) == str(incoming_client_id):
                    matched = True
                elif is_own_message and c_data.get("is_me"):
                    if str(c_mid).startswith("client_") and c_data.get("content") == msg_dict.get("content"):
                        matched = True
                    elif str(getattr(ctrl, "data", "")) == msg_id_str:
                        matched = True

                if matched:
                    seen_msg_ids.add(msg_id_str)
                    ctrl.data = msg_id_str
                    ctrl.client_msg_id = msg_id_str
                    if hasattr(ctrl, "msg_data") and isinstance(ctrl.msg_data, dict):
                        ctrl.msg_data["id"] = msg_id_str
                        ctrl.msg_data["status"] = "delivered"
                    # If this was a poll, re-render in place so the poll ID is updated to the real server UUID
                    if c_data.get("type") in ("poll", "poll_update") or "options" in (c_data.get("metadata_payload") or {}):
                        try:
                            m_idx = messages_listview.controls.index(ctrl)
                            _replace_bubble_in_place(m_idx, ctrl.msg_data, do_update=True)
                        except Exception:
                            pass
                    else:
                        update_bubble_status(ctrl, msg_dict.get("status") or "delivered")
                        s_tick = getattr(ctrl, "status_tick", None)
                        if s_tick and getattr(s_tick, "page", None):
                            try:
                                s_tick.update()
                            except Exception:
                                page.update()
                        else:
                            try:
                                ctrl.update()
                            except Exception:
                                page.update()
                    return

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
        all_mentions = set([str(m).lstrip("@").strip().lower() for m in msg_mentions] + [str(m).strip().lower() for m in re.findall(r'@([\w.-]+)', msg_content)])
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
                    on_action=lambda e, cid=incoming_channel_id: page.navigate(f"/nu-chat?channel={cid}")
                )
                page.run_task(sync_learner_notifications, page, True)
            except Exception:
                pass

        render_chat_list()

        # Append to active room if viewing
        if incoming_channel_id == current_chat_id[0]:
            if is_own_message:
                # Never duplicate our own sent message in the active room
                return

            if len(messages_listview.controls) == 1 and not hasattr(messages_listview.controls[0], "data"):
                messages_listview.controls.clear()

            prev_ctrl = None
            if messages_listview.controls:
                last_ctrl = messages_listview.controls[-1]
                if hasattr(last_ctrl, "data"):
                    prev_ctrl = {"sender_id": msg_dict.get("sender_id"), "created_at": msg_dict.get("created_at")}

            bubble_w = render_message_bubble(msg_dict, prev_msg=prev_ctrl, animate_entrance=True)
            messages_listview.controls.append(bubble_w)
            try:
                messages_listview.update()
            except Exception:
                page.update()
            page.run_task(_animate_bubble_entrance, bubble_w)
            _scroll_to_bottom(animate=True)

            # Mark read immediately since user is actively in room
            if ws_client_ref[0]:
                page.run_task(ws_client_ref[0].send_message, incoming_channel_id, "", "read_receipt")

    # ==========================================
    # 12. COMPOSER ACTIONS & MODALS HELPER
    # ==========================================
    def _open_modal(control, tag=None):
        safe_open_dialog(page, control, tag=tag or "chat_modal")
        _restore_scroll_anchor()

    def _close_modal(control=None):
        safe_close_dialog(page, control)
        _restore_scroll_anchor()


    def open_chat_help_dialog():
        def _close_help(ev=None):
            safe_close_dialog(page, dlg)
            _restore_scroll_anchor()

        commands_info = [
            (ft.Icons.AUTO_AWESOME_ROUNDED, palette["accent"], "/ai <prompt>", "Ask Nu Study AI academic questions & clear doubts in chat."),
            (ft.Icons.POLL_ROUNDED, ft.Colors.CYAN_400, "/poll", "Create interactive single or multiple-choice polls."),
            (ft.Icons.CODE_ROUNDED, ft.Colors.AMBER_400, "/code", "Insert syntax-highlighted code blocks with language support."),
            (ft.Icons.FLASH_ON_ROUNDED, ft.Colors.ORANGE_500, "/duel [@user]", "Challenge your Duo Buddy to a 15-question Quickfire knowledge duel."),
            (ft.Icons.PEOPLE_ROUNDED, ft.Colors.GREEN_600, "/duo [@user]", "Send a Duo Buddy accountability partnership request."),
            (ft.Icons.HELP_OUTLINE_ROUNDED, ft.Colors.BLUE_500, "/help", "Open this commands guide and text formatting tips."),
        ]

        cmd_rows = []
        for icon_name, icon_col, syntax, desc in commands_info:
            cmd_rows.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.04, palette["text"]),
                    content=ft.Row([
                        ft.Container(
                            width=32,
                            height=32,
                            border_radius=8,
                            bgcolor=ft.Colors.with_opacity(0.12, icon_col),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(icon_name, size=18, color=icon_col)
                        ),
                        ft.Column([
                            ft.Text(syntax, size=13, weight=ft.FontWeight.BOLD, color=palette["text"]),
                            ft.Text(desc, size=11.5, color=palette["text_muted"]),
                        ], spacing=2, expand=True),
                    ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER)
                )
            )

        formatting_tips = [
            ("*bold*", "**bold**"),
            ("_italic_", "_italic_"),
            ("~strike~", "~~strikethrough~~"),
            ("`code`", "`monospace`"),
            ("@user", "mention member (groups)"),
        ]
        tip_chips = []
        for raw_fmt, label_txt in formatting_tips:
            tip_chips.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=6,
                    bgcolor=ft.Colors.with_opacity(0.08, palette["accent"]),
                    content=ft.Row([
                        ft.Text(raw_fmt, size=11, font_family="Roboto Mono, monospace", weight=ft.FontWeight.BOLD, color=palette["accent"]),
                        ft.Text(f"→ {label_txt}", size=11, color=palette["text"]),
                    ], spacing=4, tight=True)
                )
            )

        cur_w = getattr(page, "width", None) or 500
        dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=16),
            bgcolor=palette["surface"],
            title=ft.Row([
                ft.Icon(ft.Icons.HELP_OUTLINE_ROUNDED, color=palette["accent"], size=22),
                ft.Text("Nu Chat Commands & Tips", size=16, weight=ft.FontWeight.BOLD, color=palette["text"]),
            ], spacing=8),
            content=ft.Container(
                width=min(cur_w - 32, 500),
                content=ft.Column([
                    ft.Text("SLASH COMMANDS", size=11, weight=ft.FontWeight.BOLD, color=palette["text_muted"]),
                    ft.Column(cmd_rows, spacing=6),
                    ft.Container(height=4),
                    ft.Text("TEXT FORMATTING SHORTCUTS", size=11, weight=ft.FontWeight.BOLD, color=palette["text_muted"]),
                    ft.Row(tip_chips, wrap=True, spacing=6),
                ], spacing=8, tight=True, scroll=ft.ScrollMode.AUTO),
            ),
            actions=[
                ft.TextButton("Got it", on_click=_close_help),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        safe_open_dialog(page, dlg, tag="chat_help_dialog")

    async def _safe_focus_input():
        await _safe_focus(msg_input)

    def _trigger_ai_prompt():
        msg_input.value = "/ai "
        _update_send_btn_state(do_update=True)
        try:
            msg_input.update()
        except Exception:
            page.update()
        page.run_task(_safe_focus_input)

    def _trigger_study_duel():
        msg_input.value = "/duel "
        _update_send_btn_state(do_update=True)
        try:
            msg_input.update()
        except Exception:
            page.update()
        page.run_task(_safe_focus_input)

    def open_attachment_actions_modal(e=None):
        if is_modal_open(page, tag="chat_actions_sheet"):
            return
        open_chat_actions_sheet(
            page=page,
            palette=palette,
            on_open_poll=open_poll_modal,
            on_trigger_ai=_trigger_ai_prompt,
            on_trigger_duel=_trigger_study_duel,
            on_close_callback=None,
        )

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

        async def _submit_poll(ev=None):
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

            cid = current_chat_id[0]
            if not cid:
                show_page_snackbar(page, ft.SnackBar(content=ft.Text("Not connected to active chat room."), bgcolor=ft.Colors.RED_700))
                return

            # 1. Close dialog immediately for instant snappy feedback
            _close_modal(dlg)
            page.update()

            # 2. Build optimistic poll message
            client_temp_id = f"client_poll_{uuid.uuid4().hex}"
            my_id_str = str(current_user_id[0]).strip().lower()
            my_uname = str(getattr(page, "user_name", "") or "Me").strip()
            my_fname = str(getattr(page, "full_name", "") or my_uname).strip()
            now_iso = datetime.now(timezone.utc).isoformat()
            meta = {
                "question": question,
                "options": opts,
                "votes": {},
                "is_multi_select": bool(multi_switch.value),
                "client_msg_id": client_temp_id,
            }
            optimistic_poll = {
                "id": client_temp_id,
                "client_msg_id": client_temp_id,
                "channel_id": cid,
                "content": question,
                "type": "poll",
                "metadata_payload": meta,
                "sender_id": my_id_str,
                "is_me": True,
                "sender": {
                    "id": my_id_str,
                    "username": my_uname,
                    "full_name": my_fname,
                    "avatar_url": getattr(page, "user_avatar", None),
                },
                "status": "pending",
                "created_at": now_iso,
                "reactions": [],
            }

            # 3. Render optimistic bubble with entrance animation
            prev_ctrl = None
            if messages_listview.controls:
                last_c = messages_listview.controls[-1]
                prev_ctrl = getattr(last_c, "msg_data", None)

            bubble_w = render_message_bubble(optimistic_poll, prev_msg=prev_ctrl, animate_entrance=True)
            bubble_w.data = client_temp_id
            bubble_w.client_msg_id = client_temp_id
            bubble_w.msg_data = optimistic_poll
            messages_listview.controls.append(bubble_w)
            try:
                messages_listview.update()
            except Exception:
                page.update()

            page.run_task(_animate_bubble_entrance, bubble_w)
            _scroll_to_bottom(animate=True)

            # 4. Resilient background dispatch (WebSocket + REST fallback)
            async def _dispatch_poll_task():
                sent_ok = False
                curr_token = token or (await page.shared_preferences.get("auth_token"))

                def _get_target_bubble(tid):
                    for ctrl in messages_listview.controls:
                        ctrl_id = getattr(ctrl, "client_msg_id", None) or getattr(ctrl, "data", None)
                        if ctrl_id and str(ctrl_id) == str(tid):
                            return ctrl
                    return bubble_w

                if ws_client_ref[0] and getattr(ws_client_ref[0], "websocket", None):
                    try:
                        sent_ok = await ws_client_ref[0].send_message(
                            cid,
                            question,
                            "poll",
                            client_msg_id=client_temp_id,
                            metadata_payload=meta
                        )
                    except Exception as ws_err:
                        print(f"[NuChat] Poll WS dispatch error: {ws_err}")
                        sent_ok = False

                if not sent_ok and curr_token:
                    try:
                        rest_res = await send_channel_message_api(
                            curr_token, cid, question, "poll",
                            metadata_payload=meta
                        )
                        if isinstance(rest_res, dict) and "id" in rest_res:
                            sent_ok = True
                            target_b = _get_target_bubble(client_temp_id)
                            if target_b:
                                real_id = str(rest_res["id"])
                                target_b.data = real_id
                                seen_msg_ids.add(real_id)
                                update_bubble_status(target_b, "delivered")
                                page.update()
                    except Exception as rest_err:
                        print(f"[NuChat] Poll REST fallback error: {rest_err}")
                        sent_ok = False

                if sent_ok:
                    target_b = _get_target_bubble(client_temp_id)
                    if target_b:
                        update_bubble_status(target_b, "delivered")
                else:
                    target_b = _get_target_bubble(client_temp_id)
                    if target_b:
                        update_bubble_status(target_b, "failed")
                    show_page_snackbar(page, ft.SnackBar(content=ft.Text("Failed to send poll. Connection lost."), bgcolor=ft.Colors.RED_700))

            page.run_task(_dispatch_poll_task)

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
                    on_click=_submit_poll
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
                            page.navigate("/profile")
                        else:
                            page.navigate(f"/member/{uid}")

                    v_avatar_url = None
                    if v_id == my_id:
                        if hasattr(page, "session") and hasattr(page.session, "store"):
                            cu = page.session.store.get("current_user") or {}
                            v_avatar_url = cu.get("profile_picture_url") or cu.get("avatar_url")
                    if not v_avatar_url:
                        for u in all_users_cache:
                            if str(u.get("id") or u.get("user_id", "")).strip().lower() == v_id:
                                v_avatar_url = u.get("profile_picture_url") or u.get("avatar_url")
                                break

                    voter_tiles.append(
                        ft.Container(
                            ink=True,
                            border_radius=8,
                            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                            on_click=_nav_to_voter,
                            tooltip=f"View {v_name}'s profile",
                            content=ft.Row([
                                get_avatar(v_name, "direct", is_online=False, radius=13, avatar_url=v_avatar_url),
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
                for idx, u in enumerate(filtered[:45]):
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
            try:
                user_list_col.update()
            except Exception:
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
            try:
                loading_ring.update()
            except Exception:
                pass
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
                for u in all_users_cache[:60]:
                    dname = u.get("name") or u.get("full_name") or u.get("username") or "User"
                    uid = u.get("id") or u.get("user_id")
                    if str(uid).strip().lower() != current_user_id[0]:
                        cb = ft.Checkbox(data=str(uid), fill_color=palette["accent"])
                        checkboxes.append(cb)

                        def toggle_row(e, checkbox=cb):
                            checkbox.value = not checkbox.value
                            try:
                                checkbox.update()
                            except Exception:
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
            try:
                users_listview.update()
            except Exception:
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
            for u in all_users_cache[:60]:
                uid = str(u.get("id") or u.get("user_id")).strip()
                if uid not in existing:
                    dname = u.get("name") or u.get("full_name") or u.get("username") or "User"
                    cb = ft.Checkbox(data=uid, fill_color=palette["accent"])
                    checkboxes.append(cb)

                    def toggle_row(e, checkbox=cb):
                        checkbox.value = not checkbox.value
                        try:
                            checkbox.update()
                        except Exception:
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
            try:
                users_listview.update()
            except Exception:
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

    last_responsive_state = [None]

    def update_responsive_layout(e=None):
        new_is_desktop = page.width >= DESKTOP_BREAKPOINT if hasattr(page, "width") and page.width else False
        desktop_changed = (new_is_desktop != is_desktop[0]) or (last_responsive_state[0] is None)
        is_desktop[0] = new_is_desktop
        state_tuple = (new_is_desktop, bool(current_chat_id[0]))

        # When triggered by page.on_resize (e is not None) and breakpoint hasn't changed,
        # avoid dirtying messages_listview.padding or re-mounting panels, which can reset scroll
        if e is not None and state_tuple == last_responsive_state[0]:
            _restore_scroll_anchor()
            return

        last_responsive_state[0] = state_tuple
        if desktop_changed:
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
        if current_chat_id[0]:
            _restore_scroll_anchor()

    # Initial Setup
    render_chat_list()
    active_chat_panel.content = build_empty_state()
    page.on_resize = update_responsive_layout
    update_responsive_layout()
    page.run_task(fetch_initial_data)

    page._active_chat_id = lambda: current_chat_id[0]
    def _safe_close_active_chat():
        page.run_task(close_chat_mobile)
    page._close_active_chat_handler = _safe_close_active_chat

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