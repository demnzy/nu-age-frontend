import flet as ft
from datetime import datetime

# ==========================================
# REAL BACKEND IMPORTS
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


async def chat_view(page: ft.Page) -> ft.View:
    # ==========================================
    # 1. THEME & CONSTANTS  — WhatsApp-grade palette
    # ==========================================
    UI_ACCENT        = ft.Colors.PRIMARY          # brand primary (your colour)
    HEADER_BG        = ft.Colors.PRIMARY          # panel top-bar background
    CHAT_WALL_BG     = "#ECE5DD"                  # WA-style warm parchment wallpaper
    BUBBLE_IN_BG     = ft.Colors.WHITE            # incoming bubble
    BUBBLE_OUT_BG    = UI_ACCENT                  # outgoing bubble = brand colour
    LIST_BG          = ft.Colors.WHITE
    INPUT_BAR_BG     = ft.Colors.WHITE
    DIVIDER_COLOR    = "#E0E0E0"
    ONLINE_DOT       = "#25D366"                  # WhatsApp green online dot
    UNREAD_BADGE_BG  = "#25D366"
    SYSTEM_BUBBLE_BG = "#D9FDD3"
    DESKTOP_BREAKPOINT = 800

    token = await page.shared_preferences.get("auth_token") or "dummy_token"

    # State
    current_chat_id   = [None]
    is_desktop        = [page.width >= DESKTOP_BREAKPOINT]
    ws_client_ref     = [None]
    channels_list     = []
    all_users_cache   = []
    fab_open          = [False]
    search_query      = [""]
    seen_msg_ids      = set()
    chat_load_lock    = [False]
    showing_placeholder = [False]  # True only while the "Say Hello!" empty-state is displayed
    last_typing_time  = [0]
    typing_tokens     = {}

    cached_uid = await page.shared_preferences.get("user_id")
    current_user_id = [str(cached_uid).strip().lower() if cached_uid else "unknown_user_id"]

    # ==========================================
    # 2. SHARED UI COMPONENTS
    # ==========================================
    chat_list_panel   = ft.Container(
        expand=1,
        border=ft.border.only(right=ft.BorderSide(1, DIVIDER_COLOR)),
        bgcolor=LIST_BG
    )
    active_chat_panel = ft.Container(expand=2, bgcolor=CHAT_WALL_BG)
    active_chat_header = ft.Row(spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    messages_listview = ft.Column(
        expand=True,
        spacing=2,
        scroll=ft.ScrollMode.AUTO,
        auto_scroll=True
    )

    # ==========================================
    # SESSION EXPIRED DIALOG
    # ==========================================
    def trigger_session_expired():
        dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=16),
            title=ft.Row([
                ft.Icon(ft.Icons.LOCK_OUTLINE_ROUNDED, color=ft.Colors.RED_400, size=22),
                ft.Text("Session Expired", weight=ft.FontWeight.BOLD, size=16)
            ], spacing=10),
            content=ft.Text(
                "Your security token has expired.\nPlease log out and sign back in to continue.",
                size=14,
                color=ft.Colors.ON_SURFACE_VARIANT
            ),
            actions=[
                ft.TextButton(
                    "Dismiss",
                    style=ft.ButtonStyle(color=UI_ACCENT),
                    on_click=lambda e: (setattr(dlg, "open", False), page.update())
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    # ==========================================
    # 3. DATE & TIME FORMATTERS
    # ==========================================
    def format_message_time(iso_string):
        if not iso_string: return ""
        try:
            dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
            return dt.strftime("%I:%M %p").lstrip("0")
        except Exception:
            return ""

    def get_day_label(iso_string):
        if not iso_string: return ""
        try:
            dt  = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
            now = datetime.now(dt.tzinfo)
            diff = (now.date() - dt.date()).days
            if diff == 0:   return "Today"
            elif diff == 1: return "Yesterday"
            elif diff < 7:  return dt.strftime("%A")
            else:           return dt.strftime("%B %d, %Y")
        except Exception:
            return ""

    # ==========================================
    # 4. ACTION CONTROLLERS
    # ==========================================
    async def send_text_message(e=None):
        text = (msg_input.value or "").strip()
        if not text or not current_chat_id[0]: return
        if not ws_client_ref[0]:
            msg_input.hint_text = "Still connecting, try again..."
            page.update()
            return
            
        print(f"[DEBUG] Dispatching text to websocket: {text}")
        
        msg_input.value = ""
        msg_input.hint_text = "Message"
        
        # THE FIX: Wrap focus in try/except so Flet UI bugs don't crash the send logic
        try:
            res = msg_input.focus()
            if asyncio.iscoroutine(res):
                await res
        except Exception as ex:
            print(f"[DEBUG] Non-fatal focus error: {ex}")
            
        page.update()
        page.run_task(ws_client_ref[0].send_message, current_chat_id[0], text, "text")

    def on_input_change(e):
        now = datetime.now().timestamp()
        if now - last_typing_time[0] > 2:
            if ws_client_ref[0] and current_chat_id[0]:
                page.run_task(ws_client_ref[0].send_message, current_chat_id[0], "typing", "typing")
            last_typing_time[0] = now

    msg_input = ft.TextField(
        hint_text="Message",
        expand=True,
        border_radius=24,
        filled=True,
        bgcolor=ft.Colors.WHITE,
        border_color=ft.Colors.TRANSPARENT,
        focused_border_color=ft.Colors.TRANSPARENT,
        content_padding=ft.Padding(left=18, right=18, top=10, bottom=10),
        text_size=15,
        hint_style=ft.TextStyle(color=ft.Colors.BLACK38, size=15),
        shift_enter=True,
        on_change=on_input_change,
        on_submit=send_text_message
    )

    def on_search_changed(e):
        search_query[0] = (e.control.value or "").lower().strip()
        render_chat_list()

    search_field = ft.TextField(
        prefix_icon=ft.Icons.SEARCH_ROUNDED,
        hint_text="Search or start new chat",
        border_radius=10,
        height=42,
        expand=True,
        content_padding=ft.Padding(left=10, right=10, top=0, bottom=0),
        filled=True,
        bgcolor="#F0F2F5",
        border_color=ft.Colors.TRANSPARENT,
        focused_border_color=ft.Colors.TRANSPARENT,
        text_size=14,
        hint_style=ft.TextStyle(color=ft.Colors.BLACK38, size=14),
        on_change=on_search_changed,
        on_submit=lambda e: render_chat_list()
    )

    # ==========================================
    # 5. AVATAR HELPER
    # ==========================================
    def get_avatar(name: str, channel_type: str, is_online: bool = False, radius: int = 20):
        tokens   = [t for t in (name or "").split() if t]
        initials = "".join([t[0] for t in tokens[:2]]).upper() if tokens else "?"

        is_group = channel_type in ("group", "org", "organisation", "custom")

        base_avatar = ft.CircleAvatar(
            content=(
                ft.Icon(ft.Icons.GROUP_ROUNDED, color=ft.Colors.WHITE, size=radius - 4)
                if is_group
                else ft.Text(initials, size=radius * 0.55, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
            ),
            bgcolor=UI_ACCENT if is_group else ft.Colors.with_opacity(0.7, UI_ACCENT),
            radius=radius
        )

        if channel_type == "direct":
            dot_size  = max(10, radius // 2)
            status_dot = ft.Container(
                width=dot_size, height=dot_size,
                bgcolor=ONLINE_DOT if is_online else ft.Colors.GREY_400,
                border=ft.border.all(2, ft.Colors.WHITE),
                shape=ft.BoxShape.CIRCLE
            )
            return ft.Stack(
                controls=[base_avatar, ft.Container(content=status_dot, alignment=ft.Alignment(1.0, 1.0))],
                width=radius * 2, height=radius * 2
            )
        return base_avatar

    # ==========================================
    # 6. CHAT LIST RENDERER
    # ==========================================
    def render_chat_list():
        q        = search_query[0]
        filtered = [c for c in channels_list if q in c.get("name", "").lower()] if q else channels_list

        list_controls = []

        if not filtered:
            empty_label = "No results." if q else "No chats yet"
            empty_sub   = f'No chats matching "{q}".' if q else "Tap  ✎  to start a conversation"
            list_controls.append(
                ft.Container(
                    padding=ft.Padding(left=30, right=30, top=60, bottom=40),
                    alignment=ft.Alignment(0, 0),
                    content=ft.Column([
                        ft.Icon(ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED, size=52, color=ft.Colors.BLACK12),
                        ft.Container(height=8),
                        ft.Text(empty_label, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_600, size=15),
                        ft.Text(empty_sub, size=12, color=ft.Colors.BLACK38, text_align=ft.TextAlign.CENTER),
                    ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
                )
            )
        else:
            for idx, chat in enumerate(filtered):
                cid       = chat.get("channel_id")
                is_active = cid == current_chat_id[0]
                unread    = chat.get("unread", 0)
                is_online = chat.get("is_online", False)
                chat_name = chat.get("name", "Chat")

                unread_badge = ft.Container()
                if unread > 0:
                    unread_badge = ft.Container(
                        content=ft.Text(
                            str(unread) if unread < 100 else "99+",
                            size=11, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD
                        ),
                        bgcolor=UNREAD_BADGE_BG,
                        border_radius=12,
                        width=22 if unread < 10 else (28 if unread < 100 else 36),
                        height=22,
                        alignment=ft.Alignment(0, 0),
                        padding=ft.Padding(left=2, right=2, top=0, bottom=0)
                    )

                if chat.get("is_typing"):
                    preview_ui = ft.Text(
                        "typing…",
                        size=13, color=ONLINE_DOT, expand=True,
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, italic=True
                    )
                else:
                    # REMOVED: [SYSTEM] tag replacing. Backend uses pure text now.
                    preview_ui = ft.Text(
                        chat.get("last_msg", ""),
                        size=13, color=ft.Colors.BLACK54, expand=True,
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS
                    )

                time_txt = ft.Text(
                    format_message_time(chat.get("time", "")),
                    size=11,
                    color=UNREAD_BADGE_BG if unread > 0 else ft.Colors.BLACK38,
                    weight=ft.FontWeight.W_600 if unread > 0 else ft.FontWeight.NORMAL
                )

                tile = ft.Container(
                    ink=True,
                    on_click=lambda e, c_id=cid: page.run_task(load_active_chat, c_id),
                    on_long_press=lambda e, c_id=cid, c_name=chat_name: open_delete_modal(c_id, c_name),
                    bgcolor=ft.Colors.with_opacity(0.06, UI_ACCENT) if is_active else ft.Colors.TRANSPARENT,
                    padding=ft.Padding(left=16, right=16, top=10, bottom=10),
                    content=ft.Row([
                        get_avatar(chat_name, chat.get("type", "dm"), is_online, radius=22),
                        ft.Container(width=12),
                        ft.Column([
                            ft.Row([
                                ft.Text(
                                    chat_name,
                                    weight=ft.FontWeight.W_600,
                                    size=15, expand=True,
                                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                                    color=ft.Colors.ON_SURFACE
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
                if idx < len(filtered) - 1:
                    list_controls.append(
                        ft.Container(
                            content=ft.Divider(height=1, color=DIVIDER_COLOR),
                            padding=ft.Padding(left=70, right=0, top=0, bottom=0)
                        )
                    )

        chat_list_ui = ft.Column(
            expand=True,
            controls=[
                ft.Container(
                    bgcolor=HEADER_BG,
                    padding=ft.Padding(top=14, left=20, right=16, bottom=14),
                    gradient=ft.LinearGradient(
                        begin=ft.Alignment.TOP_LEFT,
                        end=ft.Alignment.BOTTOM_RIGHT,
                        colors=[ft.Colors.PRIMARY, ft.Colors.SECONDARY]
                    ),
                    content=ft.Column([
                        ft.Row([
                            ft.Text("Nu Chat", size=22, weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.WHITE, expand=True),
                        ]),
                        ft.Container(height=10),
                        ft.Row([
                            ft.Container(
                                expand=True,
                                bgcolor="#FFFFFF",
                                border_radius=10,
                                content=search_field
                            )
                        ])
                    ], spacing=0)
                ),
                ft.ListView(expand=True, controls=list_controls, spacing=0)
            ],
            spacing=0
        )

        speed_dial = _build_speed_dial()
        chat_list_panel.content = ft.Stack(
            expand=True,
            controls=[chat_list_ui, ft.Container(bottom=24, right=20, content=speed_dial)]
        )
        page.update()

    # ==========================================
    # 7. DELETE MODAL
    # ==========================================
    def open_delete_modal(chat_id, chat_name):
        async def execute_delete(e):
            nonlocal channels_list
            await delete_chat_channel(token, chat_id)
            channels_list = [c for c in channels_list if c.get("channel_id") != chat_id]
            if current_chat_id[0] == chat_id:
                page.run_task(close_chat_mobile)
            else:
                render_chat_list()
            dlg.open = False
            page.update()

        dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=16),
            title=ft.Text("Delete conversation?", weight=ft.FontWeight.BOLD, size=16),
            content=ft.Column([
                ft.Container(height=4),
                ft.Text(
                    "This will permanently remove this chat from your list. Messages cannot be recovered.",
                    size=13, color=ft.Colors.ON_SURFACE_VARIANT
                )
            ], tight=True, spacing=0),
            actions=[
                ft.TextButton(
                    "Cancel",
                    style=ft.ButtonStyle(color=ft.Colors.ON_SURFACE_VARIANT),
                    on_click=lambda e: (setattr(dlg, "open", False), page.update())
                ),
                ft.FilledButton(
                    "Delete",
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.RED_400,
                        color=ft.Colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=8)
                    ),
                    on_click=execute_delete
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            actions_padding=ft.Padding(left=16, right=16, top=0, bottom=16)
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    # ==========================================
    # 8. SPEED DIAL FAB
    # ==========================================
    def _speed_dial_item(icon, label, on_click_fn):
        return ft.Row(
            controls=[
                ft.Container(
                    content=ft.Text(label, size=12, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE),
                    bgcolor=ft.Colors.WHITE,
                    border_radius=8,
                    padding=ft.Padding(left=12, right=12, top=6, bottom=6),
                    shadow=ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.18, ft.Colors.BLACK), offset=ft.Offset(0, 2))
                ),
                ft.FloatingActionButton(
                    content=ft.Icon(icon, color=ft.Colors.WHITE, size=18),
                    bgcolor=UI_ACCENT,
                    width=42, height=42,
                    on_click=on_click_fn,
                    mini=True
                )
            ],
            alignment=ft.MainAxisAlignment.END, spacing=10
        )

    def _build_speed_dial():
        mini_items = ft.Column(
            controls=[
                _speed_dial_item(ft.Icons.GROUP_ADD_ROUNDED,  "New Group",       lambda e: _speed_dial_action(open_create_channel_modal, e)),
                _speed_dial_item(ft.Icons.PERSON_ADD_ROUNDED, "Message a Person", lambda e: _speed_dial_action(open_users_modal, e)),
            ],
            spacing=10,
            visible=fab_open[0],
            horizontal_alignment=ft.CrossAxisAlignment.END
        )
        main_fab = ft.FloatingActionButton(
            content=ft.Icon(
                ft.Icons.CLOSE if fab_open[0] else ft.Icons.EDIT_ROUNDED,
                color=ft.Colors.WHITE, size=22
            ),
            bgcolor=UI_ACCENT,
            on_click=toggle_fab,
            elevation=4
        )
        return ft.Column(
            controls=[mini_items, main_fab],
            spacing=10,
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

    # ==========================================
    # 9. MESSAGE BUBBLE RENDERER
    # ==========================================
    def render_message_bubble(msg):
        # THE FIX: Pure 'type' check since backend Postgres Enum now supports "system" natively.
        if msg.get("type") == "system":
            return ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    ft.Container(
                        content=ft.Text(msg.get("content", ""), size=11, color=ft.Colors.BLACK54, weight=ft.FontWeight.W_500),
                        bgcolor=SYSTEM_BUBBLE_BG,
                        padding=ft.Padding(14, 5, 14, 5),
                        border_radius=10,
                        margin=ft.Margin(top=6, bottom=6, left=0, right=0),
                        shadow=ft.BoxShadow(blur_radius=2, color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK), offset=ft.Offset(0, 1))
                    )
                ]
            )

        sender_info = msg.get("sender", {})
        my_id       = str(current_user_id[0]).strip().lower()
        sender_id   = str(sender_info.get("id", "unknown")).strip().lower()
        sender_name = str(sender_info.get("name", "Unknown"))
        is_me       = (sender_id == my_id) or msg.get("is_me", False)

        if is_me:
            radius = ft.BorderRadius(top_left=12, top_right=12, bottom_left=12, bottom_right=2)
            bg         = BUBBLE_OUT_BG
            text_color = ft.Colors.WHITE
            ts_color   = ft.Colors.with_opacity(0.7, ft.Colors.WHITE)
        else:
            radius = ft.BorderRadius(top_left=2, top_right=12, bottom_left=12, bottom_right=12)
            bg         = BUBBLE_IN_BG
            text_color = ft.Colors.ON_SURFACE
            ts_color   = ft.Colors.BLACK38

        raw_content = msg.get("content", "")
        raw_ts      = msg.get("created_at", "")
        ts_label    = format_message_time(raw_ts)

        max_w       = int(page.width * 0.42) if is_desktop[0] else int(page.width * 0.72)
        char_limit  = max_w // 8
        dynamic_w   = max_w if len(raw_content) >= char_limit else None

        sender_label = ft.Container(height=0)
        if not is_me:
            sender_label = ft.Text(sender_name, size=12, weight=ft.FontWeight.BOLD, color=UI_ACCENT)

        ts_row = ft.Row(
            [ft.Text(ts_label, size=10, color=ts_color)],
            alignment=ft.MainAxisAlignment.END
        )

        bubble = ft.Container(
            width=dynamic_w,
            bgcolor=bg,
            border_radius=radius,
            padding=ft.Padding(left=12, right=12, top=8, bottom=6),
            shadow=ft.BoxShadow(
                blur_radius=4,
                color=ft.Colors.with_opacity(0.10, ft.Colors.BLACK),
                offset=ft.Offset(0, 1)
            ),
            content=ft.Column([
                sender_label,
                ft.Text(raw_content, size=14, color=text_color, selectable=True),
                ts_row
            ], tight=True, spacing=2,
               horizontal_alignment=ft.CrossAxisAlignment.END if is_me else ft.CrossAxisAlignment.START)
        )

        margin = ft.Margin(top=1, bottom=1, left=60 if is_me else 8, right=8 if is_me else 60)

        if is_me:
            return ft.Container(
                content=ft.Row([bubble], alignment=ft.MainAxisAlignment.END),
                margin=margin
            )
        else:
            sender_initials = "".join([t[0] for t in sender_name.split()[:2]]).upper()
            sender_avatar   = ft.CircleAvatar(
                content=ft.Text(sender_initials, size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                bgcolor=ft.Colors.with_opacity(0.75, UI_ACCENT),
                radius=14
            )
            return ft.Container(
                content=ft.Row(
                    [sender_avatar, bubble],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.END,
                    spacing=6
                ),
                margin=margin
            )

    # ==========================================
    # 10. TYPING INDICATOR
    # ==========================================
    def show_typing_indicator(channel_id, sender_name):
        tok = datetime.now().timestamp()
        typing_tokens[channel_id] = tok

        # 1. Always update the channel list state so the list tile shows
        #    "typing..." regardless of which panel is currently visible.
        for chat in channels_list:
            if chat.get("channel_id") == channel_id:
                chat["is_typing"]   = True
                chat["typing_name"] = sender_name
                break
        render_chat_list()

        # 2. If this channel is currently open, also update the chat header.
        if channel_id == current_chat_id[0]:
            if len(active_chat_header.controls) >= 3:
                status_col  = active_chat_header.controls[2]
                status_text = status_col.controls[1]
                status_text.value = "typing..."
                status_text.color = ONLINE_DOT
                page.update()

        # 3. Single clear task that resets BOTH list state and header.
        async def clear_typing(t):
            await asyncio.sleep(3)
            if typing_tokens.get(channel_id) != t:
                return
            # Clear list state.
            for c in channels_list:
                if c.get("channel_id") == channel_id:
                    c.pop("is_typing", None)
                    c.pop("typing_name", None)
                    break
            render_chat_list()
            # Clear header only if this channel is still the open one.
            if current_chat_id[0] == channel_id and len(active_chat_header.controls) >= 3:
                status_col  = active_chat_header.controls[2]
                status_text = status_col.controls[1]
                chat_info   = next((c for c in channels_list if c.get("channel_id") == channel_id), {})
                is_online   = chat_info.get("is_online", False)
                chat_type   = chat_info.get("type", "direct")
                if chat_type == "direct":
                    status_text.value = "online" if is_online else "Offline"
                    status_text.color = ONLINE_DOT if is_online else ft.Colors.with_opacity(0.6, ft.Colors.WHITE)
                else:
                    status_text.value = ""
                page.update()

        page.run_task(clear_typing, tok)

    # ==========================================
    # 11. LIFECYCLE — REST + WebSocket
    # ==========================================
    async def fetch_initial_data():
        nonlocal channels_list
        try:
            user_data = await get_current_user_request(token)
            if isinstance(user_data, tuple) and len(user_data) > 1: user_data = user_data[1]
            uid = user_data.get("id") or user_data.get("user_id") or user_data.get("sub") if isinstance(user_data, dict) else getattr(user_data, "id", None)
            if uid:
                current_user_id[0] = str(uid).strip().lower()
                await page.shared_preferences.set("user_id", current_user_id[0])
        except Exception:
            pass

        res = await get_user_channels(token)
        if isinstance(res, dict) and ("401" in str(res) or "unauthorized" in str(res).lower() or "error" in res):
            trigger_session_expired()
            return
        if isinstance(res, list):
            channels_list = res
        render_chat_list()

    async def load_active_chat(chat_id):
        if chat_load_lock[0]: return
        chat_load_lock[0] = True

        try:
            current_chat_id[0] = chat_id
            chat_info = next((c for c in channels_list if c.get("channel_id") == chat_id), {"name": "Chat", "type": "direct"})
            chat_info["unread"] = 0
            render_chat_list()

            if ws_client_ref[0]:
                await ws_client_ref[0].disconnect()
                ws_client_ref[0] = None

            back_btn = ft.IconButton(
                ft.Icons.ARROW_BACK_ROUNDED,
                icon_color=ft.Colors.WHITE,
                icon_size=22,
                on_click=lambda e: page.run_task(close_chat_mobile),
                visible=not is_desktop[0],
                tooltip="Back"
            )

            _chat_name     = chat_info.get("name") or "Chat"
            _chat_type     = chat_info.get("type", "direct")
            _chat_online   = chat_info.get("is_online", False)
            header_actions = []

            if _chat_type in ("group", "custom", "organisation"):
                header_actions.append(
                    ft.IconButton(
                        ft.Icons.PERSON_ADD_ALT_1_ROUNDED,
                        icon_color=ft.Colors.WHITE,
                        icon_size=22,
                        tooltip="Add members",
                        on_click=lambda e: open_add_member_modal(chat_id)
                    )
                )
                # THE FIX: Add a 3-dot menu with the Leave Group action
                header_actions.append(
                    ft.PopupMenuButton(
                        icon=ft.Icons.MORE_VERT_ROUNDED,
                        icon_color=ft.Colors.WHITE,
                        items=[
                            ft.PopupMenuItem(
                                content="Leave Group",
                                icon=ft.Icons.EXIT_TO_APP_ROUNDED,
                                on_click=lambda e: confirm_leave_group(chat_id, _chat_name)
                            )
                        ]
                    )
                )

            active_chat_header.controls = [
                back_btn,
                get_avatar(_chat_name, _chat_type, _chat_online, radius=20),
                ft.Column([
                    ft.Text(_chat_name, weight=ft.FontWeight.BOLD, size=15, color=ft.Colors.WHITE),
                    ft.Text("Connecting…", size=11, color=ft.Colors.with_opacity(0.8, ft.Colors.WHITE))
                ], spacing=1, expand=True),
                *header_actions
            ]

            messages_listview.controls = [
                ft.Row([ft.ProgressRing(color=UI_ACCENT, width=28, height=28, stroke_width=2.5)],
                       alignment=ft.MainAxisAlignment.CENTER)
            ]

            active_chat_panel.content = ft.Column([
                ft.Container(
                    bgcolor=HEADER_BG,
                    gradient=ft.LinearGradient(
                        begin=ft.Alignment.TOP_LEFT,
                        end=ft.Alignment.BOTTOM_RIGHT,
                        colors=[ft.Colors.PRIMARY, ft.Colors.SECONDARY]
                    ),
                    padding=ft.Padding(left=6, right=12, top=8, bottom=8),
                    shadow=ft.BoxShadow(
                        blur_radius=6,
                        color=ft.Colors.with_opacity(0.2, ft.Colors.BLACK),
                        offset=ft.Offset(0, 2)
                    ),
                    content=active_chat_header
                ),
                ft.Container(
                    content=messages_listview,
                    padding=ft.Padding(left=8, right=8, top=10, bottom=10),
                    expand=True,
                    bgcolor=CHAT_WALL_BG
                ),
                ft.Container(
                    bgcolor=INPUT_BAR_BG,
                    padding=ft.Padding(left=8, right=8, top=8, bottom=8),
                    border=ft.border.only(top=ft.BorderSide(1, DIVIDER_COLOR)),
                    content=ft.Row([
                        ft.Container(
                            expand=True,
                            bgcolor=ft.Colors.WHITE,
                            border_radius=24,
                            border=ft.border.all(1, DIVIDER_COLOR),
                            padding=ft.Padding(left=4, right=4, top=2, bottom=2),
                            content=msg_input
                        ),
                        ft.Container(width=6),
                        ft.Container(
                            width=46, height=46,
                            bgcolor=UI_ACCENT,
                            border_radius=23,
                            alignment=ft.Alignment(0, 0),
                            shadow=ft.BoxShadow(
                                blur_radius=4,
                                color=ft.Colors.with_opacity(0.25, ft.Colors.BLACK),
                                offset=ft.Offset(0, 2)
                            ),
                            content=ft.IconButton(
                                icon=ft.Icons.SEND_ROUNDED,
                                icon_color=ft.Colors.WHITE,
                                icon_size=20,
                                on_click=send_text_message,
                                style=ft.ButtonStyle(padding=0)
                            )
                        )
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=0)
                )
            ], spacing=0, expand=True)

            update_responsive_layout()
            page.update()

            history = await get_channel_messages(token, chat_id)

            if isinstance(history, dict) and ("401" in str(history) or "unauthorized" in str(history).lower() or "error" in history):
                trigger_session_expired()
                return

            messages_listview.controls.clear()
            seen_msg_ids.clear()
            showing_placeholder[0] = False

            if isinstance(history, list) and len(history) > 0:
                current_date_label = None
                for msg in reversed(history):
                    if msg.get("type") in ("typing", "presence"): continue
                    
                    msg_id = str(msg.get("id"))
                    if msg_id: seen_msg_ids.add(msg_id)

                    msg_date = get_day_label(msg.get("created_at"))
                    if msg_date and msg_date != current_date_label:
                        date_pill = ft.Container(
                            content=ft.Text(msg_date, size=11, color=ft.Colors.BLACK54,
                                            weight=ft.FontWeight.W_500),
                            bgcolor="#D1F2EA",
                            padding=ft.Padding(14, 5, 14, 5),
                            border_radius=10,
                            margin=ft.Margin(top=8, bottom=8, left=0, right=0),
                            shadow=ft.BoxShadow(blur_radius=2, color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK), offset=ft.Offset(0, 1))
                        )
                        messages_listview.controls.append(
                            ft.Row([date_pill], alignment=ft.MainAxisAlignment.CENTER)
                        )
                        current_date_label = msg_date

                    messages_listview.controls.append(render_message_bubble(msg))
            else:
                showing_placeholder[0] = True
                messages_listview.controls = [
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Column([
                            ft.Container(
                                content=ft.Text("Say Hello!", size=14,
                                                color=ft.Colors.BLACK54, weight=ft.FontWeight.W_500),
                                bgcolor="#D1F2EA",
                                padding=ft.Padding(18, 8, 18, 8),
                                border_radius=12
                            )
                        ], alignment=ft.MainAxisAlignment.CENTER,
                           horizontal_alignment=ft.CrossAxisAlignment.CENTER)
                    )
                ]

            if len(active_chat_header.controls) >= 3:
                status_col = active_chat_header.controls[2]
                if len(status_col.controls) >= 2:
                    _is_online  = chat_info.get("is_online", False)
                    _chat_type  = chat_info.get("type", "direct")
                    if _chat_type == "direct":
                        online_text  = "online" if _is_online else "Offline"
                        online_color = ONLINE_DOT if _is_online else ft.Colors.with_opacity(0.6, ft.Colors.WHITE)
                    else:
                        online_text  = ""
                        online_color = ft.Colors.with_opacity(0.6, ft.Colors.WHITE)
                    status_col.controls[1].value = online_text
                    status_col.controls[1].color = online_color
            page.update()

            ws_client_ref[0] = ChatWebSocketClient(token)
            await ws_client_ref[0].connect(handle_incoming_message)

        finally:
            chat_load_lock[0] = False

    def handle_incoming_message(msg_dict):
        incoming_channel_id = msg_dict.get("channel_id")
        msg_type = msg_dict.get("type", "text")

        if msg_type == "presence":
            is_online = msg_dict.get("is_online", False)
            for chat in channels_list:
                if chat.get("channel_id") == incoming_channel_id:
                    chat["is_online"] = is_online
                    break
            render_chat_list()
            
            if incoming_channel_id == current_chat_id[0]:
                chat_info = next((c for c in channels_list if c.get("channel_id") == incoming_channel_id), {})
                if len(active_chat_header.controls) > 1:
                    active_chat_header.controls[1] = get_avatar(chat_info.get("name", "Chat"), chat_info.get("type", "direct"), is_online, radius=20)
                    if len(active_chat_header.controls) >= 3:
                        status_col = active_chat_header.controls[2]
                        if len(status_col.controls) >= 2:
                            _chat_type = chat_info.get("type", "direct")
                            if _chat_type == "direct":
                                online_text  = "online" if is_online else "Offline"
                                online_color = ONLINE_DOT if is_online else ft.Colors.with_opacity(0.6, ft.Colors.WHITE)
                            else:
                                online_text  = ""
                                online_color = ft.Colors.with_opacity(0.6, ft.Colors.WHITE)
                            status_col.controls[1].value = online_text
                            status_col.controls[1].color = online_color
                    page.update()
            return

        if msg_type == "typing":
            sender_id = str(msg_dict.get("sender", {}).get("id", "unknown")).strip().lower()
            my_id     = str(current_user_id[0]).strip().lower()
            if sender_id != my_id:
                show_typing_indicator(incoming_channel_id, msg_dict.get("sender", {}).get("name", "Someone"))
            return

        msg_id = msg_dict.get("id")
        if not msg_id: 
            print(f"[DEBUG] Dropping malformed incoming message (No ID): {msg_dict}")
            return
            
        msg_id_str = str(msg_id)
        if msg_id_str in seen_msg_ids: return
        seen_msg_ids.add(msg_id_str)

        for chat in channels_list:
            if chat.get("channel_id") == incoming_channel_id:
                if incoming_channel_id != current_chat_id[0]:
                    chat["unread"] = chat.get("unread", 0) + 1
                chat["last_msg"] = msg_dict.get("content", "")
                chat["time"]     = msg_dict.get("created_at", "")
                channels_list.remove(chat)
                channels_list.insert(0, chat)
                break

        render_chat_list()

        if incoming_channel_id == current_chat_id[0]:
            if showing_placeholder[0]:
                messages_listview.controls.clear()
                showing_placeholder[0] = False
            messages_listview.controls.append(render_message_bubble(msg_dict))
            page.update()

    # ==========================================
    # 12. MODALS — refined WhatsApp-style sheets
    # ==========================================

    async def _load_users_if_needed():
        nonlocal all_users_cache
        if not all_users_cache:
            res = await get_all_users(token)
            if isinstance(res, list): all_users_cache = res

    # ── User picker (DM) ─────────────────────────────────────────────────────
    # ── Leave Group modal ────────────────────────────────────────────────────
    def confirm_leave_group(channel_id, group_name):
        async def execute_leave(e):
            nonlocal channels_list
            
            # 1. Broadcast the system message to the group BEFORE leaving
            if ws_client_ref[0]:
                page.run_task(
                    ws_client_ref[0].send_message, 
                    channel_id, 
                    "A member has left the chat.", 
                    "system"
                )
                
                # Brief yield to ensure the socket fires before we disconnect
                await asyncio.sleep(0.2) 

            # 2. Hit the backend to sever the connection
            try:
                await leave_group_channel(token, channel_id)
            except Exception as ex:
                print(f"Failed to leave group: {ex}")
            
            # 3. Clean up the UI state
            channels_list = [c for c in channels_list if c.get("channel_id") != channel_id]
            
            # Close dialog safely
            if hasattr(page, "close"): page.close(dlg)
            else: dlg.open = False; page.update()

            # 4. Route the user away from the deleted chat
            if current_chat_id[0] == channel_id:
                await close_chat_mobile()
            else:
                render_chat_list()

        # The Confirmation Dialog UI
        dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=16),
            title=ft.Text(f"Leave '{group_name}'?", weight=ft.FontWeight.BOLD, size=16),
            content=ft.Column([
                ft.Container(height=4),
                ft.Text("You will no longer receive messages from this group.", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
            ], tight=True, spacing=0),
            actions=[
                ft.TextButton("Cancel", style=ft.ButtonStyle(color=ft.Colors.ON_SURFACE_VARIANT),
                              on_click=lambda e: (setattr(dlg, "open", False), page.update())),
                ft.FilledButton("Leave", style=ft.ButtonStyle(bgcolor=ft.Colors.RED_400, color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=8)),
                                on_click=execute_leave)
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            actions_padding=ft.Padding(left=16, right=16, top=0, bottom=16)
        )
        
        # Version-safe dialog mounting
        if hasattr(page, "open"): page.open(dlg)
        else: page.overlay.append(dlg); dlg.open = True; page.update()

    def open_users_modal(e):
        user_search = ft.TextField(
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            hint_text="Search people…",
            border_radius=10,
            filled=True,
            bgcolor="#F0F2F5",
            border_color=ft.Colors.TRANSPARENT,
            focused_border_color=ft.Colors.TRANSPARENT,
            content_padding=ft.Padding(left=10, right=10, top=8, bottom=8),
            text_size=14
        )
        user_list_col = ft.Column(tight=True, scroll=ft.ScrollMode.AUTO, spacing=0)
        loading_ring  = ft.Row(
            [ft.ProgressRing(color=UI_ACCENT, width=24, height=24, stroke_width=2.5)],
            alignment=ft.MainAxisAlignment.CENTER
        )

        def _render_user_tiles(query=""):
            q        = query.lower().strip()
            user_list_col.controls.clear()
            filtered = [
                u for u in all_users_cache
                if q in (u.get("name") or u.get("full_name") or "").lower()
            ] if q else all_users_cache

            if not filtered:
                user_list_col.controls.append(
                    ft.Container(
                        padding=20, alignment=ft.Alignment(0, 0),
                        content=ft.Text("No users found. Head over to the friends tab to Make some friends!", color=ft.Colors.ON_SURFACE_VARIANT)
                    )
                )
            else:
                for idx, u in enumerate(filtered):
                    display_name = u.get("name") or u.get("full_name") or u.get("username") or "User"
                    uid          = u.get("id") or u.get("user_id")
                    initials     = "".join([n[0] for n in display_name.split()[:2]]).upper()

                    tile = ft.Container(
                        ink=True,
                        padding=ft.Padding(left=16, right=16, top=10, bottom=10),
                        on_click=lambda e, fid=uid: handle_user_dm(fid, dlg),
                        content=ft.Row([
                            ft.CircleAvatar(
                                content=ft.Text(initials, size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                bgcolor=UI_ACCENT, radius=20
                            ),
                            ft.Container(width=12),
                            ft.Column([
                                ft.Text(display_name, weight=ft.FontWeight.W_600, size=14),
                                ft.Text(u.get("email", ""), size=12, color=ft.Colors.BLACK38)
                            ], spacing=2, tight=True, expand=True)
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=0)
                    )
                    user_list_col.controls.append(tile)
                    if idx < len(filtered) - 1:
                        user_list_col.controls.append(
                            ft.Container(content=ft.Divider(height=1, color=DIVIDER_COLOR),
                                         padding=ft.Padding(left=60, right=0, top=0, bottom=0))
                        )
            page.update()

        user_search.on_submit = lambda e: _render_user_tiles(e.control.value)
        user_search.on_change = lambda e: _render_user_tiles(e.control.value)

        dlg = ft.AlertDialog(
    modal=True,
    shape=ft.RoundedRectangleBorder(radius=16),
    title=ft.Text("New Message", weight=ft.FontWeight.BOLD, size=17),
    title_padding=ft.Padding(left=20, right=20, top=20, bottom=12),
    content_padding=ft.Padding(left=0, right=0, top=0, bottom=0),
    content=ft.Container(
        width=380,
        height=480,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,  # ← clips children to bounds
        content=ft.Column(
            spacing=0,
            tight=True,
            controls=[
                # Search bar — pinned, never scrolls
                ft.Container(
                    content=user_search,
                    width=float("inf"),
                    padding=ft.Padding(left=16, right=16, top=0, bottom=8),
                ),

                loading_ring,

                # User list — fills remaining height and scrolls internally
                ft.Container(
                    expand=True,
                    height=380,        # absorbs whatever space is left
                    content=ft.ListView(
                        controls=[user_list_col],
                        expand=True,
                        spacing=0,
                        padding=ft.padding.symmetric(horizontal=16),
                    ),
                ),
            ],
        ),
    ),
    actions=[
        ft.TextButton(
            "Cancel",
            style=ft.ButtonStyle(color=ft.Colors.ON_SURFACE_VARIANT),
            on_click=lambda e: (setattr(dlg, "open", False), page.update()),
        )
    ],
    actions_padding=ft.Padding(left=16, right=16, top=0, bottom=12),
)
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

        async def _boot():
            await _load_users_if_needed()
            loading_ring.visible = False
            _render_user_tiles()
        page.run_task(_boot)

    def handle_user_dm(target_id, dlg):
        dlg.open = False
        page.update()
        async def init_dm():
            res = await start_direct_message(token, target_id)
            if res and "error" not in res:
                await fetch_initial_data()
                channel_id = res.get("channel_id")
                if channel_id: await load_active_chat(channel_id)
        page.run_task(init_dm)

    # ── Add Members modal ────────────────────────────────────────────────────
    def open_add_member_modal(channel_id):
        users_listview  = ft.ListView(expand=True, spacing=0)
        users_container = ft.Container(
            content=users_listview,
            height=260,
            border=ft.border.all(1, DIVIDER_COLOR),
            border_radius=10,
            clip_behavior=ft.ClipBehavior.HARD_EDGE
        )
        loading_ring = ft.Container(
            content=ft.ProgressRing(color=UI_ACCENT, width=22, height=22, stroke_width=2.5),
            alignment=ft.Alignment(0, 0),
            padding=24
        )
        checkboxes = []

        async def _load_filterable_users():
            await _load_users_if_needed()
            existing_members = await get_group_members(token, channel_id)
            loading_ring.visible = False

            for u in all_users_cache:
                uid = str(u.get("id") or u.get("user_id")).strip()
                if uid not in existing_members:
                    display_name = u.get("name") or u.get("full_name") or u.get("username") or "User"
                    cb           = ft.Checkbox(data=uid, fill_color=UI_ACCENT)
                    checkboxes.append(cb)

                    def toggle_row(e, checkbox=cb):
                        checkbox.value = not checkbox.value
                        page.update()

                    initials = "".join([t[0] for t in display_name.split()[:2]]).upper()
                    avatar   = ft.CircleAvatar(
                        content=ft.Text(initials, size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        bgcolor=UI_ACCENT, radius=16
                    )
                    row = ft.Container(
                        padding=ft.Padding(left=12, right=12, top=10, bottom=10),
                        border=ft.border.only(bottom=ft.BorderSide(1, DIVIDER_COLOR)),
                        ink=True, on_click=toggle_row,
                        content=ft.Row([avatar, ft.Container(width=10),
                                        ft.Text(display_name, expand=True, size=14, weight=ft.FontWeight.W_500),
                                        cb], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=0)
                    )
                    users_listview.controls.append(row)

            if not users_listview.controls:
                users_listview.controls.append(
                    ft.Container(
                        padding=24, alignment=ft.Alignment(0, 0),
                        content=ft.Text("Everyone is already in this chat",
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                        text_align=ft.TextAlign.CENTER)
                    )
                )
            page.update()

        add_btn = ft.FilledButton(
            "Add to Group",
            style=ft.ButtonStyle(
                bgcolor=UI_ACCENT,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=8)
            )
        )

        async def handle_add(e):
            selected_ids = [cb.data for cb in checkboxes if cb.value]
            if not selected_ids: return
            add_btn.disabled = True
            add_btn.content  = ft.ProgressRing(width=16, height=16, color=ft.Colors.WHITE, stroke_width=2)
            page.update()
            try:
                await add_group_members(token, channel_id, selected_ids)
                dialog.open = False
            finally:
                add_btn.disabled = False
                add_btn.content     = "Add to Group"
                page.update()

        add_btn.on_click = handle_add

        dialog = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=16),
            title=ft.Text("Add Members", weight=ft.FontWeight.BOLD, size=17),
            title_padding=ft.Padding(left=20, right=20, top=20, bottom=10),
            content_padding=ft.Padding(left=16, right=16, top=0, bottom=8),
            content=ft.Container(
                width=360,
                content=ft.Column([loading_ring, users_container], tight=True, spacing=10)
            ),
            actions=[
                ft.TextButton("Cancel", style=ft.ButtonStyle(color=ft.Colors.ON_SURFACE_VARIANT),
                              on_click=lambda e: (setattr(dialog, "open", False), page.update())),
                add_btn
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            actions_padding=ft.Padding(left=0, right=16, top=0, bottom=16)
        )
        page.overlay.append(dialog)
        dialog.open = True
        page.update()
        page.run_task(_load_filterable_users)

    # ── Create Group modal ────────────────────────────────────────────────────
    def open_create_channel_modal(e):
        name_input = ft.TextField(
            label="Group name",
            width=float("inf"),
            border_radius=10,
            filled=True,
            bgcolor="#F0F2F5",
            border_color=ft.Colors.TRANSPARENT,
            focused_border_color=UI_ACCENT,
            content_padding=ft.Padding(left=14, right=14, top=14, bottom=14),
            text_size=14
        )
        
        users_listview  = ft.ListView(expand=True, spacing=0)
        users_container = ft.Container(
            content=users_listview, height=200,
            border=ft.border.all(1, DIVIDER_COLOR),
            border_radius=10,
            clip_behavior=ft.ClipBehavior.HARD_EDGE
        )
        loading_ring = ft.Container(
            content=ft.ProgressRing(color=UI_ACCENT, width=22, height=22, stroke_width=2.5),
            alignment=ft.Alignment(0, 0), padding=20
        )
        checkboxes = []

        async def _load_users():
            await _load_users_if_needed()
            loading_ring.visible = False
            if all_users_cache:
                for u in all_users_cache:
                    display_name = u.get("name") or u.get("full_name") or u.get("username") or "User"
                    uid          = u.get("id") or u.get("user_id")
                    if str(uid).strip().lower() != current_user_id[0]:
                        cb = ft.Checkbox(data=uid, fill_color=ft.Colors.PRIMARY)
                        checkboxes.append(cb)

                        def toggle_row(e, checkbox=cb):
                            checkbox.value = not checkbox.value
                            page.update()

                        initials = "".join([t[0] for t in display_name.split()[:2]]).upper()
                        avatar   = ft.CircleAvatar(
                            content=ft.Text(initials, size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            bgcolor=UI_ACCENT, radius=16
                        )
                        row = ft.Container(
                            padding=ft.Padding(left=12, right=12, top=10, bottom=10),
                            border=ft.border.only(bottom=ft.BorderSide(1, DIVIDER_COLOR)),
                            ink=True, on_click=toggle_row,
                            content=ft.Row([avatar, ft.Container(width=10),
                                            ft.Text(display_name, expand=True, size=14, weight=ft.FontWeight.W_500),
                                            cb], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=0)
                        )
                        users_listview.controls.append(row)
            else:
                users_listview.controls.append(ft.Text("Go make some friends first!"))
            page.update()

        create_btn = ft.FilledButton(
            "Create Group",
            style=ft.ButtonStyle(
                bgcolor=UI_ACCENT,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=8)
            )
        )

        async def handle_create(e):
            if not name_input.value.strip():
                name_input.error_text = "Group name is required"
                page.update()
                return
            selected_ids       = [cb.data for cb in checkboxes if cb.value]
            create_btn.disabled = True
            create_btn.content  = ft.ProgressRing(width=16, height=16, color=ft.Colors.WHITE, stroke_width=2)
            page.update()
            try:
                res = await create_group_channel(
                    token=token,
                    name=name_input.value.strip(),
                    channel_type="custom",
                    org_id=None,
                    member_ids=selected_ids
                )
                if res and "error" not in res:
                    await fetch_initial_data()
                    channel_id = res.get("channel_id")
                    if channel_id: await load_active_chat(channel_id)
                dialog.open = False
            except Exception:
                pass
            finally:
                create_btn.disabled = False
                create_btn.content  = "Create Group"
                page.update()

        create_btn.on_click = handle_create

        dialog = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=16),
            title=ft.Text("New Group", weight=ft.FontWeight.BOLD, size=17),
            title_padding=ft.Padding(left=20, right=20, top=20, bottom=10),
            content_padding=ft.Padding(left=16, right=16, top=0, bottom=8),
            content=ft.Container(
                width=360,
                content=ft.Column([
                    name_input,
                    ft.Container(height=4),
                    ft.Text("Add participants", size=12, weight=ft.FontWeight.W_600,
                            color=ft.Colors.ON_SURFACE_VARIANT),
                    loading_ring,
                    users_container
                ], tight=True, spacing=10)
            ),
            actions=[
                ft.TextButton("Cancel", style=ft.ButtonStyle(color=ft.Colors.ON_SURFACE_VARIANT),
                              on_click=lambda e: (setattr(dialog, "open", False), page.update())),
                create_btn
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            actions_padding=ft.Padding(left=0, right=16, top=0, bottom=16)
        )
        page.overlay.append(dialog)
        dialog.open = True
        page.update()
        page.run_task(_load_users)

    # ==========================================
    # 13. ROUTING & CLEANUP
    # ==========================================
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
            bgcolor=CHAT_WALL_BG,
            content=ft.Column([
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.FORUM_OUTLINED, size=72, color=ft.Colors.with_opacity(0.18, ft.Colors.BLACK)),
                        ft.Container(height=12),
                        ft.Text("Nu Chat", size=26, weight=ft.FontWeight.BOLD,
                                color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE)),
                        ft.Container(height=4),
                        ft.Text("Select a conversation to start messaging.",
                                size=13, color=ft.Colors.BLACK38, text_align=ft.TextAlign.CENTER),
                        ft.Container(height=20),
                        ft.Container(
                            content=ft.Row([
                                ft.Icon(ft.Icons.LOCK_OUTLINE_ROUNDED, size=12, color=ft.Colors.BLACK26),
                                ft.Text("Secured", size=11, color=ft.Colors.BLACK38)
                            ], spacing=4, alignment=ft.MainAxisAlignment.CENTER)
                        )
                    ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
                )
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        )

    def update_responsive_layout(e=None):
        is_desktop[0] = page.width >= DESKTOP_BREAKPOINT
        if is_desktop[0]:
            chat_list_panel.visible  = True
            active_chat_panel.visible = True
            chat_list_panel.expand   = 1
            active_chat_panel.expand = 2
            if not current_chat_id[0]:
                active_chat_panel.content = build_empty_state()
            if active_chat_header.controls:
                active_chat_header.controls[0].visible = False
        else:
            chat_list_panel.expand   = True
            active_chat_panel.expand = True
            if current_chat_id[0]:
                chat_list_panel.visible  = False
                active_chat_panel.visible = True
                if active_chat_header.controls:
                    active_chat_header.controls[0].visible = True
            else:
                chat_list_panel.visible  = True
                active_chat_panel.visible = False
        page.update()

    # ==========================================
    # 14. INITIALISATION
    # ==========================================
    render_chat_list()
    active_chat_panel.content = build_empty_state()
    page.on_resize = update_responsive_layout
    update_responsive_layout()
    page.run_task(fetch_initial_data)

    return ft.View(
        route="/nu-chat",
        padding=0,
        bgcolor=CHAT_WALL_BG,
        bottom_appbar=get_bottom_appbar(page),
        controls=[
            ft.SafeArea(
                expand=True,
                content=ft.Row([chat_list_panel, active_chat_panel], spacing=0, expand=True)
            )
        ]
    )