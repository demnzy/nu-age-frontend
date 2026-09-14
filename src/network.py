"""
network_view.py
──────────────────────────────────────────────────────────────────────────────
Nu-age Network  —  My Network · Requests · Discover
Clean iOS-inspired friends cards, horizontal active friends row,
pill actions, and modern underline tab switching.
──────────────────────────────────────────────────────────────────────────────
"""

import asyncio
import flet as ft
from src.components.bottom_appbar import get_bottom_appbar
from src.requests.networks import (
    get_friends, get_incoming_requests, get_sent_requests,
    get_discover_peers, get_discover_org, get_discover_trending,
    send_request, accept_request, decline_request, cancel_outgoing_request, remove_friend
)


# ─────────────────────────────────────────────────────────────────────────────
# SHARED HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _is_mounted(control: ft.Control) -> bool:
    """
    Safe replacement for `control.page` truthy-checks.
    Swallows RuntimeError("Control must be added to the page first") and reports False.
    """
    try:
        return control.page is not None
    except RuntimeError:
        return False


_AVATAR_COLORS = [
    "#EBF4FF", "#E6FFFA", "#F3E8FF",
    "#FFEDD5", "#DCFCE7", "#FCE7F3",
]
_AVATAR_TEXT_COLORS = [
    "#2563EB", "#0D9488", "#7C3AED",
    "#EA580C", "#16A34A", "#DB2777",
]

def _initials(first: str, last: str) -> str:
    return f"{(first or '?')[:1]}{(last or '?')[:1]}".upper()

def _avatar_color(name: str) -> str:
    return _AVATAR_COLORS[hash(name) % len(_AVATAR_COLORS)]

def _avatar_text_color(name: str) -> str:
    return _AVATAR_TEXT_COLORS[hash(name) % len(_AVATAR_TEXT_COLORS)]

def _avatar(user: dict, radius: int = 24) -> ft.CircleAvatar:
    first = user.get("first_name") or "?"
    last  = user.get("last_name")  or "?"
    name  = f"{first} {last}".strip()
    img_url = (
        user.get("avatar") or
        user.get("profile_picture") or
        user.get("picture") or
        user.get("photo") or
        user.get("image") or
        user.get("profile_image")
    )
    if img_url and isinstance(img_url, str) and img_url.startswith("http"):
        return ft.CircleAvatar(
            foreground_image_src=img_url,
            radius=radius,
            bgcolor=_avatar_color(name),
        )
    return ft.CircleAvatar(
        content=ft.Text(
            _initials(first, last),
            size=radius * 0.55,
            weight=ft.FontWeight.W_700,
            color=_avatar_text_color(name),
        ),
        bgcolor=_avatar_color(name),
        radius=radius,
    )

def _org_pill(label: str) -> ft.Container:
    return ft.Container(
        visible=bool(label),
        padding=ft.Padding.symmetric(horizontal=8, vertical=2),
        bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
        border_radius=99,
        content=ft.Text(
            label if label else "",
            size=9.5,
            color=ft.Colors.PRIMARY,
            weight=ft.FontWeight.W_600,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        ),
    )

def _section_label(text: str) -> ft.Container:
    return ft.Container(
        margin=ft.Margin.only(bottom=2),
        content=ft.Row(
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=3,
                    height=14,
                    border_radius=2,
                    bgcolor=ft.Colors.PRIMARY,
                ),
                ft.Text(
                    text,
                    size=13,
                    weight=ft.FontWeight.W_700,
                    color=ft.Colors.ON_SURFACE,
                ),
            ],
        ),
    )

def _empty_state(icon, title: str, subtitle: str,
                 action_label: str = None, on_action=None) -> ft.Container:
    controls = [
        ft.Container(
            width=64,
            height=64,
            border_radius=32,
            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.PRIMARY),
            alignment=ft.Alignment.CENTER,
            content=ft.Icon(icon, size=32, color=ft.Colors.PRIMARY),
        ),
        ft.Container(height=4),
        ft.Text(title, size=16, weight=ft.FontWeight.W_700,
                color=ft.Colors.ON_SURFACE, text_align=ft.TextAlign.CENTER),
        ft.Text(subtitle, size=12.5, color=ft.Colors.GREY_500,
                text_align=ft.TextAlign.CENTER),
    ]
    if action_label and on_action:
        controls += [
            ft.Container(height=6),
            ft.ElevatedButton(
                action_label,
                bgcolor=ft.Colors.PRIMARY,
                color=ft.Colors.ON_PRIMARY,
                height=36,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=20),
                    elevation=0,
                ),
                on_click=lambda _: on_action(),
            ),
        ]
    return ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        padding=32,
        content=ft.Column(
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
            controls=controls,
        ),
    )

def _loading_spinner(message: str = "Loading...") -> ft.Container:
    return ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
            controls=[
                ft.ProgressRing(color=ft.Colors.PRIMARY, width=28, height=28, stroke_width=3),
                ft.Text(message, size=13, color=ft.Colors.GREY_400),
            ],
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# VIEW
# ─────────────────────────────────────────────────────────────────────────────
async def network_view(page: ft.Page):
    app_bar_bottom = get_bottom_appbar(page)
    token          = await page.shared_preferences.get("auth_token")

    content_socket = ft.Container(expand=True)
    active_tab     = {"index": 0}

    # Shared mutable state — safe to read/write across tabs
    state = {
        "pending_count": 0,
        "pending_sent": [],
        "friends_count": 0,
    }

    header_subtitle_ref = ft.Ref[ft.Text]()

    # ── segmented control (clean underline/pill style matching reference) ──────
    seg_labels = ["My Network", "Requests", "Discover"]

    seg_row = ft.Container(
        margin=ft.Margin.only(top=4, bottom=4),
        content=ft.Row(
            spacing=16,
            alignment=ft.MainAxisAlignment.START,
            controls=[],
        ),
    )

    def _rebuild_seg(do_update: bool = True):
        """Rebuild the tab text buttons with underline active indicator."""
        def _tab_pill(label: str, idx: int) -> ft.Container:
            is_active = active_tab["index"] == idx
            return ft.Container(
                padding=ft.Padding.only(left=2, right=2, top=4, bottom=4),
                ink=True,
                on_click=lambda _, i=idx: page.run_task(switch_tab, i),
                content=ft.Column(
                    spacing=5,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Row(
                            spacing=6,
                            tight=True,
                            alignment=ft.MainAxisAlignment.CENTER,
                            controls=[
                                ft.Text(
                                    label,
                                    size=13.5,
                                    weight=ft.FontWeight.W_700 if is_active else ft.FontWeight.W_500,
                                    color=ft.Colors.ON_SURFACE if is_active else ft.Colors.GREY_400,
                                ),
                                ft.Container(
                                    width=7,
                                    height=7,
                                    bgcolor=ft.Colors.ERROR,
                                    border_radius=4,
                                    visible=(idx == 1 and state["pending_count"] > 0 and not is_active),
                                ),
                            ],
                        ),
                        # Blue underline bar matching reference UI
                        ft.Container(
                            height=3,
                            width=32 if is_active else 0,
                            border_radius=2,
                            bgcolor=ft.Colors.PRIMARY if is_active else ft.Colors.TRANSPARENT,
                        ),
                    ],
                ),
            )

        seg_row.content.controls = [_tab_pill(l, i) for i, l in enumerate(seg_labels)]
        if do_update and _is_mounted(seg_row):
            seg_row.update()

    # ── tab switcher ──────────────────────────────────────────────────────────
    async def switch_tab(idx: int):
        active_tab["index"] = idx
        _rebuild_seg()

        # Show spinner immediately — yield so Flet can repaint before we await
        content_socket.content = _loading_spinner("Syncing network…")
        if _is_mounted(content_socket):
            content_socket.update()
        await asyncio.sleep(0)

        if idx == 0:
            await show_network()
        elif idx == 1:
            await show_requests()
        elif idx == 2:
            await show_discover()

        if page.views and _is_mounted(content_socket):
            page.update()

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 1 — MY NETWORK
    # ─────────────────────────────────────────────────────────────────────────
    async def show_network():
        try:
            all_friends = await get_friends(token) or []
        except Exception as ex:
            print(f"Failed to load friends: {ex}")
            all_friends = []

        state["friends_count"] = len(all_friends)
        if header_subtitle_ref.current and _is_mounted(header_subtitle_ref.current):
            header_subtitle_ref.current.value = f"{len(all_friends)} Friends"
            header_subtitle_ref.current.update()

        friends_list_col = ft.Column(spacing=10)
        section_count_ref = ft.Ref[ft.Text]()

        def _avatar_bubble(user: dict) -> ft.Container:
            first = user.get("first_name") or "Friend"
            uid   = user.get("id", "")
            return ft.Container(
                ink=True,
                border_radius=12,
                padding=ft.Padding.symmetric(horizontal=4, vertical=2),
                tooltip=f"View {first}'s profile",
                on_click=lambda _, u=uid: page.go(f"/member/{u}"),
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                    tight=True,
                    controls=[
                        ft.Container(
                            padding=ft.Padding.all(2),
                            border=ft.Border.all(2, ft.Colors.PRIMARY),
                            border_radius=30,
                            content=_avatar(user, radius=24),
                        ),
                        ft.Text(
                            first,
                            size=11,
                            weight=ft.FontWeight.W_600,
                            color=ft.Colors.ON_SURFACE,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                ),
            )

        def _friend_card(user: dict) -> ft.Container:
            first      = user.get("first_name") or "Unknown"
            last       = user.get("last_name")  or ""
            university = user.get("university") or "Student"
            org        = user.get("org")
            uid        = user.get("id", "")
            card_ref   = ft.Ref[ft.Container]()

            async def do_remove_friend(uid_to_remove):
                try:
                    await remove_friend(token, uid_to_remove)
                    if card_ref.current in friends_list_col.controls:
                        friends_list_col.controls.remove(card_ref.current)
                        state["friends_count"] = max(0, state["friends_count"] - 1)
                        if header_subtitle_ref.current and _is_mounted(header_subtitle_ref.current):
                            header_subtitle_ref.current.value = f"{state['friends_count']} Friends"
                            header_subtitle_ref.current.update()
                        if section_count_ref.current and _is_mounted(section_count_ref.current):
                            section_count_ref.current.value = f"All Friends ({state['friends_count']})"
                            section_count_ref.current.update()
                        if page.views:
                            page.update()
                except Exception as ex:
                    print(f"Failed to remove friend: {ex}")

            return ft.Container(
                ref=card_ref,
                bgcolor=ft.Colors.SURFACE,
                border_radius=14,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                shadow=ft.BoxShadow(
                    blur_radius=8,
                    color=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
                    offset=ft.Offset(0, 2),
                ),
                content=ft.Row(
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        # Avatar (clicking navigates to profile)
                        ft.Container(
                            content=_avatar(user, radius=22),
                            ink=True,
                            on_click=lambda _, u=uid: page.go(f"/member/{u}"),
                        ),
                        # Middle: Name, University, Org Pill (clicking navigates to profile)
                        ft.Container(
                            expand=True,
                            ink=True,
                            on_click=lambda _, u=uid: page.go(f"/member/{u}"),
                            content=ft.Column(
                                spacing=2,
                                tight=True,
                                controls=[
                                    ft.Text(
                                        f"{first} {last}".strip(),
                                        size=14,
                                        weight=ft.FontWeight.W_700,
                                        color=ft.Colors.ON_SURFACE,
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                    ft.Text(
                                        university,
                                        size=11.5,
                                        color=ft.Colors.GREY_500,
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                    _org_pill(org),
                                ],
                            ),
                        ),
                        # Right: Actions (Pill Message button + 3-dots Menu)
                        ft.Row(
                            spacing=4,
                            tight=True,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                # "Message" solid pill button
                                ft.Container(
                                    height=32,
                                    border_radius=20,
                                    bgcolor=ft.Colors.PRIMARY,
                                    padding=ft.Padding.symmetric(horizontal=12, vertical=0),
                                    alignment=ft.Alignment.CENTER,
                                    ink=True,
                                    on_click=lambda _, u=uid: page.go("/nu-chat"),
                                    content=ft.Row(
                                        tight=True,
                                        spacing=5,
                                        controls=[
                                            ft.Icon(
                                                ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED,
                                                size=13,
                                                color=ft.Colors.ON_PRIMARY,
                                            ),
                                            ft.Text(
                                                "Message",
                                                size=11.5,
                                                weight=ft.FontWeight.W_600,
                                                color=ft.Colors.ON_PRIMARY,
                                            ),
                                        ],
                                    ),
                                ),
                                # 3-dots popup menu
                                ft.PopupMenuButton(
                                    icon=ft.Icons.MORE_VERT_ROUNDED,
                                    icon_color=ft.Colors.GREY_400,
                                    icon_size=18,
                                    tooltip="More options",
                                    items=[
                                        ft.PopupMenuItem(
                                            content="View Profile",
                                            icon=ft.Icons.PERSON_OUTLINE_ROUNDED,
                                            on_click=lambda _, u=uid: page.go(f"/member/{u}"),
                                        ),
                                        ft.PopupMenuItem(
                                            content="Remove Connection",
                                            icon=ft.Icons.PERSON_REMOVE_ROUNDED,
                                            on_click=lambda _, u=uid: page.run_task(do_remove_friend, u),
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            )

        def rebuild_list(friends: list):
            friends_list_col.controls = [_friend_card(f) for f in friends]
            if section_count_ref.current and _is_mounted(section_count_ref.current):
                section_count_ref.current.value = f"All Friends ({len(friends)})"
                section_count_ref.current.update()
            try:
                if page.views:
                    page.update()
            except Exception:
                pass

        def on_search(e):
            q = (e.control.value or "").strip().lower()
            if not q:
                rebuild_list(all_friends)
                return
            rebuild_list([
                f for f in all_friends
                if q in (f.get("first_name") or "").lower()
                or q in (f.get("last_name")  or "").lower()
                or q in (f.get("university") or "").lower()
                or q in (f.get("org")        or "").lower()
            ])

        if not all_friends:
            content_socket.content = _empty_state(
                ft.Icons.PEOPLE_OUTLINE_ROUNDED,
                "Your network is a blank canvas",
                "Connect with peers and start building your circle.",
                action_label="Find Peers",
                on_action=lambda: page.run_task(switch_tab, 2),
            )
            return

        search = ft.TextField(
            hint_text="Search your friends…",
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            border_radius=14,
            border_color=ft.Colors.GREY_200,
            focused_border_color=ft.Colors.PRIMARY,
            fill_color=ft.Colors.SURFACE,
            filled=True,
            expand=True,
            height=44,
            text_size=13,
            content_padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            on_change=on_search,
        )

        # Horizontal carousel of active friend bubbles matching reference UI
        bubbles_row = ft.Container(
            padding=ft.Padding.only(bottom=8),
            content=ft.Row(
                scroll=ft.ScrollMode.AUTO,
                spacing=12,
                controls=[_avatar_bubble(f) for f in all_friends[:15]],
            ),
        )

        content_socket.content = ft.Column(
            expand=True,
            spacing=0,
            controls=[
                # Top controls (Bubbles carousel + Search input)
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=16, vertical=4),
                    content=ft.Column(
                        spacing=10,
                        controls=[
                            bubbles_row,
                            ft.Row(controls=[search]),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Text(
                                        ref=section_count_ref,
                                        value=f"All Friends ({len(all_friends)})",
                                        size=13,
                                        weight=ft.FontWeight.W_700,
                                        color=ft.Colors.GREY_700,
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                ft.Container(height=4),
                # Vertical list of friend rows
                ft.Container(
                    expand=True,
                    content=ft.Column(
                        expand=True,
                        scroll=ft.ScrollMode.AUTO,
                        controls=[
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=16, vertical=4),
                                content=friends_list_col,
                            ),
                            ft.Container(height=20),
                        ],
                    ),
                ),
            ],
        )

        rebuild_list(all_friends)

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 2 — REQUESTS
    # ─────────────────────────────────────────────────────────────────────────
    async def show_requests():
        incoming_col = ft.Column(spacing=10)
        sent_col     = ft.Column(spacing=8)

        try:
            incoming_data, sent_data = await asyncio.gather(
                get_incoming_requests(token),
                get_sent_requests(token),
            )
            incoming_data = incoming_data or []
            sent_data     = sent_data     or []

            # Merge locally-queued sent requests from Discover
            pending = state.pop("pending_sent", [])
            state["pending_sent"] = []
            for user in pending:
                existing_ids = {r["user"]["id"] for r in sent_data if "user" in r}
                uid = user.get("id", "")
                if uid and uid not in existing_ids:
                    sent_data.append({
                        "id":   f"local_{uid}",
                        "user": user,
                    })

            state["pending_count"] = len(incoming_data)
            _rebuild_seg()

            if header_subtitle_ref.current and _is_mounted(header_subtitle_ref.current):
                header_subtitle_ref.current.value = f"{len(incoming_data)} Incoming · {len(sent_data)} Sent"
                header_subtitle_ref.current.update()

        except Exception as ex:
            print(f"Failed to fetch requests: {ex}")
            incoming_data, sent_data = [], []

        def _incoming_card(req: dict) -> ft.Container:
            user    = req.get("user") or {}
            card    = ft.Ref[ft.Container]()
            buttons = ft.Ref[ft.Row]()
            confirm = ft.Ref[ft.Row]()

            first      = user.get("first_name") or "Unknown"
            last       = user.get("last_name")  or ""
            university = user.get("university") or "Student"
            org        = user.get("org")

            async def on_accept(e):
                buttons.current.visible = False
                confirm.current.visible = True
                if page.views:
                    page.update()
                try:
                    await accept_request(token, req["id"])
                    await asyncio.sleep(0.5)
                    if card.current in incoming_col.controls:
                        incoming_col.controls.remove(card.current)
                        state["pending_count"] = max(0, state["pending_count"] - 1)
                        _rebuild_seg()
                        if header_subtitle_ref.current and _is_mounted(header_subtitle_ref.current):
                            header_subtitle_ref.current.value = f"{state['pending_count']} Incoming · {len(sent_col.controls)} Sent"
                            header_subtitle_ref.current.update()
                        if page.views:
                            page.update()
                except Exception:
                    buttons.current.visible = True
                    confirm.current.visible = False
                    if page.views:
                        page.update()

            async def on_decline(e):
                try:
                    await decline_request(token, req["id"])
                    if card.current in incoming_col.controls:
                        incoming_col.controls.remove(card.current)
                        state["pending_count"] = max(0, state["pending_count"] - 1)
                        _rebuild_seg()
                        if header_subtitle_ref.current and _is_mounted(header_subtitle_ref.current):
                            header_subtitle_ref.current.value = f"{state['pending_count']} Incoming · {len(sent_col.controls)} Sent"
                            header_subtitle_ref.current.update()
                        if page.views:
                            page.update()
                except Exception:
                    pass

            return ft.Container(
                ref=card,
                bgcolor=ft.Colors.SURFACE,
                border_radius=14,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY)),
                padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                shadow=ft.BoxShadow(
                    blur_radius=8,
                    color=ft.Colors.with_opacity(0.03, ft.Colors.PRIMARY),
                    offset=ft.Offset(0, 2),
                ),
                content=ft.Row(
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        # Avatar with ring
                        ft.Container(
                            padding=ft.Padding.all(2),
                            border_radius=30,
                            border=ft.Border.all(1.5, ft.Colors.PRIMARY),
                            content=_avatar(user, radius=20),
                        ),
                        # Middle info
                        ft.Column(
                            spacing=2,
                            expand=True,
                            tight=True,
                            controls=[
                                ft.Text(
                                    f"{first} {last}".strip(),
                                    size=13.5,
                                    weight=ft.FontWeight.W_700,
                                    color=ft.Colors.ON_SURFACE,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(
                                    university,
                                    size=11,
                                    color=ft.Colors.GREY_500,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                _org_pill(org),
                            ],
                        ),
                        # Actions
                        ft.Column(
                            tight=True,
                            horizontal_alignment=ft.CrossAxisAlignment.END,
                            controls=[
                                ft.Row(
                                    ref=buttons,
                                    spacing=6,
                                    tight=True,
                                    controls=[
                                        # Outlined Decline pill
                                        ft.Container(
                                            height=30,
                                            border_radius=20,
                                            border=ft.Border.all(1, ft.Colors.GREY_300),
                                            padding=ft.Padding.symmetric(horizontal=10, vertical=0),
                                            alignment=ft.Alignment.CENTER,
                                            ink=True,
                                            on_click=lambda e: page.run_task(on_decline, e),
                                            content=ft.Text(
                                                "Decline",
                                                size=11.5,
                                                weight=ft.FontWeight.W_500,
                                                color=ft.Colors.GREY_600,
                                            ),
                                        ),
                                        # Solid Accept pill
                                        ft.Container(
                                            height=30,
                                            border_radius=20,
                                            bgcolor=ft.Colors.PRIMARY,
                                            padding=ft.Padding.symmetric(horizontal=12, vertical=0),
                                            alignment=ft.Alignment.CENTER,
                                            ink=True,
                                            on_click=lambda e: page.run_task(on_accept, e),
                                            content=ft.Text(
                                                "Accept",
                                                size=11.5,
                                                weight=ft.FontWeight.W_600,
                                                color=ft.Colors.ON_PRIMARY,
                                            ),
                                        ),
                                    ],
                                ),
                                ft.Row(
                                    ref=confirm,
                                    visible=False,
                                    spacing=4,
                                    tight=True,
                                    controls=[
                                        ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.GREEN_500, size=16),
                                        ft.Text("Added!", size=11.5, color=ft.Colors.GREEN_600, weight=ft.FontWeight.W_600),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            )

        def _sent_card(req: dict) -> ft.Container:
            user    = req.get("user") or {}
            row     = ft.Ref[ft.Container]()
            btn_ref = ft.Ref[ft.TextButton]()

            first = user.get("first_name") or "Unknown"
            last  = user.get("last_name")  or ""
            org   = user.get("org")

            async def on_cancel(e):
                btn_ref.current.disabled = True
                btn_ref.current.text = ft.Text("Canceling…", size=8)
                if _is_mounted(btn_ref.current):
                    btn_ref.current.update()
                try:
                    await cancel_outgoing_request(token, req["id"])
                    if row.current in sent_col.controls:
                        sent_col.controls.remove(row.current)
                        if page.views:
                            page.update()
                except Exception:
                    btn_ref.current.disabled = False
                    btn_ref.current.text = "Cancel"
                    if _is_mounted(btn_ref.current):
                        btn_ref.current.update()

            return ft.Container(
                ref=row,
                bgcolor=ft.Colors.SURFACE,
                border_radius=14,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
                padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                content=ft.Row(
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        _avatar(user, radius=18),
                        ft.Column(
                            spacing=2,
                            expand=True,
                            tight=True,
                            controls=[
                                ft.Text(
                                    f"{first} {last}".strip(),
                                    size=13,
                                    weight=ft.FontWeight.W_600,
                                    color=ft.Colors.ON_SURFACE,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(
                                    org or "Pending response",
                                    size=11,
                                    color=ft.Colors.GREY_400,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                            ],
                        ),
                        ft.Container(
                            height=28,
                            border_radius=20,
                            border=ft.Border.all(1, ft.Colors.GREY_300),
                            padding=ft.Padding.symmetric(horizontal=6, vertical=0),
                            content=ft.TextButton(
                                ref=btn_ref,
                                content=ft.Text("Cancel", size=8, weight=ft.FontWeight.W_500, color=ft.Colors.GREY_600),
                                on_click=lambda e: page.run_task(on_cancel, e),
                            ),
                        ),
                    ],
                ),
            )

        for req in incoming_data:
            incoming_col.controls.append(_incoming_card(req))
        for req in sent_data:
            sent_col.controls.append(_sent_card(req))

        content_socket.content = ft.Container(
            expand=True,
            content=ft.Column(
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                        content=ft.Column(
                            spacing=14,
                            controls=[
                                # Incoming header
                                ft.Row(
                                    spacing=8,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        _section_label("Incoming Requests"),
                                        ft.Container(
                                            padding=ft.Padding.symmetric(horizontal=7, vertical=2),
                                            bgcolor=ft.Colors.ERROR_CONTAINER,
                                            border_radius=99,
                                            visible=len(incoming_data) > 0,
                                            content=ft.Text(
                                                str(len(incoming_data)),
                                                size=10,
                                                color=ft.Colors.ERROR,
                                                weight=ft.FontWeight.W_700,
                                            ),
                                        ),
                                    ],
                                ),
                                incoming_col if incoming_data else ft.Container(
                                    padding=ft.Padding.symmetric(vertical=12),
                                    content=ft.Text("No incoming requests at the moment.",
                                                    size=12.5, color=ft.Colors.GREY_400),
                                ),
                                ft.Divider(height=1, color=ft.Colors.GREY_100),
                                _section_label("Sent Requests"),
                                sent_col if sent_data else ft.Container(
                                    padding=ft.Padding.symmetric(vertical=12),
                                    content=ft.Text("No pending sent requests.",
                                                    size=12.5, color=ft.Colors.GREY_400),
                                ),
                                ft.Container(height=20),
                            ],
                        ),
                    )
                ],
            ),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 3 — DISCOVER
    # ─────────────────────────────────────────────────────────────────────────
    async def show_discover():
        try:
            peers_data, org_data, trending_data = await asyncio.gather(
                get_discover_peers(token),
                get_discover_org(token),
                get_discover_trending(token),
            )
            peers_data    = peers_data    or []
            org_data      = org_data      or []
            trending_data = trending_data or []

            if header_subtitle_ref.current and _is_mounted(header_subtitle_ref.current):
                header_subtitle_ref.current.value = "Connect & Expand"
                header_subtitle_ref.current.update()

        except Exception as ex:
            print(f"Failed to load discover: {ex}")
            peers_data, org_data, trending_data = [], [], []

        def _discover_row_card(user: dict) -> ft.Container:
            btn_container = ft.Ref[ft.Container]()
            btn_text      = ft.Ref[ft.Text]()
            requested     = {"v": False}

            first      = user.get("first_name") or "Unknown"
            last       = user.get("last_name")  or ""
            university = user.get("university") or "Student"
            org        = user.get("org")
            streak     = user.get("streak", 0) or 0
            uid        = user.get("id", "")

            async def on_add(e):
                if requested["v"]:
                    return
                # Optimistic UI update: transitions to outlined "Added" pill matching reference Screen 2
                requested["v"] = True
                btn_container.current.bgcolor = ft.Colors.TRANSPARENT
                btn_container.current.border = ft.Border.all(1, ft.Colors.PRIMARY)
                btn_text.current.value = "Added"
                btn_text.current.color = ft.Colors.PRIMARY
                if page.views:
                    page.update()
                try:
                    await asyncio.wait_for(send_request(token, uid), timeout=10)
                    state["pending_sent"].append(user)
                except Exception as ex:
                    print(f"Request failed: {ex}")
                    # Revert on error
                    requested["v"] = False
                    btn_container.current.bgcolor = ft.Colors.PRIMARY
                    btn_container.current.border = None
                    btn_text.current.value = "Add"
                    btn_text.current.color = ft.Colors.ON_PRIMARY
                    if page.views:
                        page.update()

            return ft.Container(
                bgcolor=ft.Colors.SURFACE,
                border_radius=14,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                shadow=ft.BoxShadow(
                    blur_radius=8,
                    color=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
                    offset=ft.Offset(0, 2),
                ),
                content=ft.Row(
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        # Avatar
                        ft.Container(
                            content=_avatar(user, radius=22),
                            ink=True,
                            on_click=lambda _, u=uid: page.go(f"/member/{u}"),
                        ),
                        # User info
                        ft.Container(
                            expand=True,
                            ink=True,
                            on_click=lambda _, u=uid: page.go(f"/member/{u}"),
                            content=ft.Column(
                                spacing=2,
                                tight=True,
                                controls=[
                                    ft.Row(
                                        spacing=6,
                                        tight=True,
                                        controls=[
                                            ft.Text(
                                                f"{first} {last}".strip(),
                                                size=14,
                                                weight=ft.FontWeight.W_700,
                                                color=ft.Colors.ON_SURFACE,
                                                max_lines=1,
                                                overflow=ft.TextOverflow.ELLIPSIS,
                                            ),
                                            # Streak badge if active
                                            ft.Container(
                                                visible=streak > 0,
                                                padding=ft.Padding.symmetric(horizontal=5, vertical=1),
                                                bgcolor=ft.Colors.ORANGE_50,
                                                border_radius=99,
                                                content=ft.Row(
                                                    tight=True,
                                                    spacing=2,
                                                    controls=[
                                                        ft.Icon(ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED, size=10, color=ft.Colors.ORANGE_500),
                                                        ft.Text(str(streak), size=9.5, color=ft.Colors.ORANGE_700, weight=ft.FontWeight.W_700),
                                                    ],
                                                ),
                                            ),
                                        ],
                                    ),
                                    ft.Text(
                                        university,
                                        size=11.5,
                                        color=ft.Colors.GREY_500,
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                    _org_pill(org),
                                ],
                            ),
                        ),
                        # Solid "Add" pill -> Outlined "Added" pill (directly matches reference UI)
                        ft.Container(
                            ref=btn_container,
                            height=32,
                            border_radius=20,
                            bgcolor=ft.Colors.PRIMARY,
                            padding=ft.Padding.symmetric(horizontal=16, vertical=0),
                            alignment=ft.Alignment.CENTER,
                            ink=True,
                            on_click=lambda e: page.run_task(on_add, e),
                            content=ft.Text(
                                ref=btn_text,
                                value="Add",
                                size=12,
                                weight=ft.FontWeight.W_600,
                                color=ft.Colors.ON_PRIMARY,
                            ),
                        ),
                    ],
                ),
            )

        def _category_section(title: str, users: list, subtitle: str = "") -> ft.Container:
            if not users:
                body = ft.Container(
                    padding=ft.Padding.symmetric(vertical=8),
                    content=ft.Text("No suggestions available right now.",
                                    size=12, color=ft.Colors.GREY_400),
                )
            else:
                body = ft.Column(
                    spacing=8,
                    controls=[_discover_row_card(u) for u in users],
                )
            return ft.Container(
                content=ft.Column(
                    spacing=8,
                    controls=[
                        ft.Column(
                            spacing=1,
                            controls=[
                                _section_label(title),
                                ft.Text(subtitle, size=11.5, color=ft.Colors.GREY_400)
                                if subtitle else ft.Container(),
                            ],
                        ),
                        body,
                    ],
                ),
            )

        content_socket.content = ft.Container(
            expand=True,
            content=ft.Column(
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                        content=ft.Column(
                            spacing=18,
                            controls=[
                                _category_section(
                                    "Peers at your university",
                                    peers_data,
                                    "Connect with your Schoolmates",
                                ),
                                ft.Divider(height=1, color=ft.Colors.GREY_100),
                                _category_section(
                                    "People at your organisation",
                                    org_data,
                                    "Teamwork makes the dream work",
                                ),
                                ft.Divider(height=1, color=ft.Colors.GREY_100),
                                _category_section(
                                    "Trending Learners",
                                    trending_data,
                                    "High-streak active learners this week",
                                ),
                                ft.Container(height=20),
                            ],
                        ),
                    )
                ],
            ),
        )

    # ── Top Header matching reference UI (Clean, Minimalist, No Hero) ────────
    header_title = ft.Text(
        "Your Friends",
        size=24,
        weight=ft.FontWeight.W_800,
        color=ft.Colors.ON_SURFACE,
    )
    header_subtitle = ft.Text(
        ref=header_subtitle_ref,
        value="Loading…",
        size=12.5,
        weight=ft.FontWeight.W_500,
        color=ft.Colors.GREY_400,
    )

    top_nav_row = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.IconButton(
                icon=ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED,
                icon_size=18,
                icon_color=ft.Colors.ON_SURFACE,
                tooltip="Back to Dashboard",
                on_click=lambda _: page.go("/dashboard"),
            ),
            ft.Container(
                padding=ft.Padding.all(2),
                border=ft.Border.all(1.5, ft.Colors.PRIMARY),
                border_radius=20,
                ink=True,
                on_click=lambda _: page.go("/profile"),
                tooltip="Your Profile",
                content=ft.CircleAvatar(
                    radius=14,
                    bgcolor=ft.Colors.PRIMARY_CONTAINER,
                    content=ft.Icon(ft.Icons.PERSON_ROUNDED, size=16, color=ft.Colors.PRIMARY),
                ),
            ),
        ],
    )

    header_container = ft.Container(
        padding=ft.Padding.only(left=16, right=16, top=10, bottom=4),
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border(bottom=ft.BorderSide(1, ft.Colors.GREY_100)),
        content=ft.Column(
            spacing=8,
            controls=[
                top_nav_row,
                ft.Column(
                    spacing=2,
                    controls=[
                        header_title,
                        header_subtitle,
                    ],
                ),
                seg_row,
            ],
        ),
    )

    # ─────────────────────────────────────────────────────────────────────────
    # BOOT
    # ─────────────────────────────────────────────────────────────────────────
    _rebuild_seg(do_update=False)
    content_socket.content = _loading_spinner("Loading your network…")

    view = ft.View(
        route="/network",
        bottom_appbar=app_bar_bottom,
        bgcolor=ft.Colors.SURFACE,
        padding=0,
        controls=[
            ft.SafeArea(
                expand=True,
                content=ft.Column(
                    expand=True,
                    spacing=0,
                    controls=[
                        header_container,
                        ft.Container(expand=True, content=content_socket),
                    ],
                ),
            )
        ],
    )

    async def _boot():
        for _ in range(200):
            if _is_mounted(seg_row):
                break
            await asyncio.sleep(0.01)
        await switch_tab(0)

    page.run_task(_boot)

    return view