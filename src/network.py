"""
network_view.py
──────────────────────────────────────────────────────────────────────────────
Nu-age Network  —  My Network · Requests · Discover
Social + LMS standard implementation.
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
_AVATAR_COLORS = [
    ft.Colors.BLUE_200, ft.Colors.TEAL_200, ft.Colors.PURPLE_200,
    ft.Colors.ORANGE_200, ft.Colors.GREEN_200, ft.Colors.PINK_200,
]

def _initials(first: str, last: str) -> str:
    return f"{(first or '?')[:1]}{(last or '?')[:1]}".upper()

def _avatar_color(name: str) -> str:
    return _AVATAR_COLORS[hash(name) % len(_AVATAR_COLORS)]

def _avatar(user: dict, radius: int = 24) -> ft.CircleAvatar:
    first = user.get("first_name") or "?"
    last  = user.get("last_name")  or "?"
    name  = f"{first} {last}"
    return ft.CircleAvatar(
        content=ft.Text(
            _initials(first, last),
            size=radius * 0.55,
            weight=ft.FontWeight.W_700,
            color=ft.Colors.GREY_800,
        ),
        bgcolor=_avatar_color(name),
        radius=radius,
    )

def _org_pill(label: str) -> ft.Container:
    return ft.Container(
        visible=bool(label), # THE MAGIC: Completely collapses if label is None or empty
        padding=ft.padding.symmetric(horizontal=8, vertical=3),
        bgcolor=ft.Colors.PRIMARY_CONTAINER,
        border_radius=99,
        content=ft.Text(
            label if label else "", size=9, color=ft.Colors.PRIMARY,
            weight=ft.FontWeight.W_600,
            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
        ),
    )

def _section_label(text: str) -> ft.Container:
    return ft.Container(
        margin=ft.margin.only(bottom=4),
        content=ft.Row(
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=3,
                    height=16,
                    border_radius=2,
                    gradient=ft.LinearGradient(
                        begin=ft.Alignment(0, -1),
                        end=ft.Alignment(0, 1),
                        colors=[ft.Colors.PRIMARY, ft.Colors.with_opacity(0.4, ft.Colors.PRIMARY)],
                    ),
                ),
                ft.Text(
                    text,
                    size=14,
                    weight=ft.FontWeight.W_700,
                    color=ft.Colors.PRIMARY,
                ),
            ],
        ),
    )

def _empty_state(icon, title: str, subtitle: str,
                 action_label: str = None, on_action=None) -> ft.Container:
    controls = [
        ft.Icon(icon, size=56, color=ft.Colors.GREY_300),
        ft.Text(title, size=17, weight=ft.FontWeight.W_700,
                color=ft.Colors.GREY_700, text_align=ft.TextAlign.CENTER),
        ft.Text(subtitle, size=13, color=ft.Colors.GREY_400,
                text_align=ft.TextAlign.CENTER),
    ]
    if action_label and on_action:
        controls += [
            ft.Container(height=4),
            ft.ElevatedButton(
                action_label, bgcolor=ft.Colors.PRIMARY,
                color=ft.Colors.WHITE, height=42,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
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
            spacing=10,
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
        # Accumulates user dicts for requests successfully sent in Discover.
        # show_requests() drains this and renders them.
        "pending_sent": [],
    }

    # ── appbar ────────────────────────────────────────────────────────────────
    app_bar = ft.AppBar(
        bgcolor=ft.Colors.PRIMARY,
        title=ft.Text("Network", color=ft.Colors.WHITE,
                      weight=ft.FontWeight.W_700, size=17),
        leading=ft.IconButton(
            icon=ft.Icons.ARROW_BACK_ROUNDED,
            icon_color=ft.Colors.WHITE,
            on_click=lambda _: page.go("/dashboard"),
        ),
        elevation=0,
    )

    # ── segmented control ─────────────────────────────────────────────────────
    seg_labels = ["My Network", "Requests", "Discover"]

    seg_row = ft.Container(
        margin=ft.margin.symmetric(horizontal=16, vertical=10),
        bgcolor=ft.Colors.GREY_100,
        border_radius=12,
        padding=ft.padding.all(4),
        content=ft.Row(spacing=0, controls=[]),
    )

    def _rebuild_seg(do_update: bool = True):
        """Rebuild the tab pills. Only calls .update() when the control is on-page."""
        def _pill(label: str, idx: int) -> ft.Container:
            is_active = active_tab["index"] == idx
            return ft.Container(
                expand=True, height=36, border_radius=10,
                bgcolor=ft.Colors.PRIMARY if is_active else ft.Colors.TRANSPARENT,
                ink=True,
                # Always use page.run_task — switch_tab is a coroutine
                on_click=lambda _, i=idx: page.run_task(switch_tab, i),
                shadow=(
                    ft.BoxShadow(
                        blur_radius=6,
                        color=ft.Colors.with_opacity(0.18, ft.Colors.PRIMARY),
                        offset=ft.Offset(0, 2),
                    ) if is_active else None
                ),
                alignment=ft.Alignment.CENTER,
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=6, tight=True,
                    controls=[
                        ft.Text(
                            label, size=13,
                            weight=ft.FontWeight.W_600 if is_active else ft.FontWeight.W_500,
                            color=ft.Colors.WHITE if is_active else ft.Colors.GREY_500,
                        ),
                        ft.Container(
                            width=7, height=7,
                            bgcolor=ft.Colors.ERROR,
                            border_radius=4,
                            visible=(idx == 1 and state["pending_count"] > 0 and not is_active),
                        ),
                    ],
                ),
            )

        seg_row.content.controls = [_pill(l, i) for i, l in enumerate(seg_labels)]
        # Only push an update if the control is already mounted on the page
        if do_update and seg_row.page:
            seg_row.update()

    # ── tab switcher ──────────────────────────────────────────────────────────
    async def switch_tab(idx: int):
        active_tab["index"] = idx
        _rebuild_seg()

        # Show spinner immediately — yield so Flet can repaint before we await
        content_socket.content = _loading_spinner("Syncing network…")
        if content_socket.page:
            content_socket.update()
        await asyncio.sleep(0)          # ← critical: let the event loop flush the paint

        if idx == 0:
            await show_network()
        elif idx == 1:
            await show_requests()
        elif idx == 2:
            await show_discover()

        # Final repaint after content is set
        if page.views and content_socket.page:
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

        grid = ft.ResponsiveRow(spacing=12, run_spacing=12)

        def _friend_card(user: dict) -> ft.Container:
            first  = user.get("first_name") or "Unknown"
            last   = user.get("last_name")  or ""
            university = user.get("university")     or "Student"
            org    = user.get("org")        # <-- Removed fallback
            uid    = user.get("id", "")
            # THE LOGIC: Handles the background API call and UI refresh
            card_ref = ft.Ref[ft.Container]()
            
            async def do_remove_friend(uid_to_remove):
                try:
                    await remove_friend(token, uid_to_remove)
                    # Surgically remove this specific card from the grid
                    if card_ref.current in grid.controls:
                        grid.controls.remove(card_ref.current)
                        if page.views:
                            page.update()
                except Exception as ex:
                    print(f"Failed to remove friend: {ex}")


    # 2. Return the complete UI tree in one clean block
            return ft.Container(
            ref=card_ref,
            col={"xs": 6, "sm": 4, "md": 3},
            bgcolor=ft.Colors.SURFACE,
            border_radius=14,
            border=ft.border.all(1, ft.Colors.GREY_200),
            shadow=ft.BoxShadow(
                blur_radius=12,
                color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
                offset=ft.Offset(0, 3),
            ),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=ft.Column(
                spacing=0,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    # gradient banner
                    ft.Container(
                        height=56,
                        gradient=ft.LinearGradient(
                            begin=ft.Alignment(-1, -1),
                            end=ft.Alignment(1, 1),
                            colors=["#6B5EE4", "#A78BFA", "#F0ABFC"],
                        ),
                    ),
                    # avatar overlapping banner
                    ft.Container(
                        content=ft.Container(
                            content=_avatar(user, radius=26),
                            border=ft.border.all(3, ft.Colors.WHITE),
                            border_radius=32,
                        ),
                        margin=ft.margin.only(top=-30),
                    ),
                    # name + university + pill
                    ft.Container(
                        padding=ft.padding.symmetric(horizontal=10, vertical=8),
                        content=ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=3,
                            controls=[
                                ft.Text(
                                    f"{first} {last}".strip(),
                                    size=13, weight=ft.FontWeight.W_700,
                                    color=ft.Colors.ON_SURFACE,
                                    text_align=ft.TextAlign.CENTER,
                                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(
                                    university,
                                    size=11, color=ft.Colors.GREY_500,
                                    text_align=ft.TextAlign.CENTER,
                                    max_lines=2, overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Container(height=2),
                                _org_pill(org),
                            ],
                        ),
                    ),
                    ft.Divider(height=1, color=ft.Colors.GREY_100),
                    # actions
                    ft.Container(
                        padding=ft.padding.symmetric(vertical=4),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=4,
                            controls=[
                                ft.IconButton(
                                    ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED,
                                    icon_color=ft.Colors.PRIMARY,
                                    icon_size=18,
                                    tooltip="Message",
                                    on_click=lambda _, u=uid: page.go("/nu-chat"),
                                ),
                                ft.IconButton(
                                    ft.Icons.INSIGHTS_ROUNDED,
                                    icon_color=ft.Colors.PRIMARY,
                                    icon_size=18,
                                    tooltip="View Stats",
                                    on_click=lambda _, u=uid: page.go(f"/member/{u}"),
                                ),
                                ft.PopupMenuButton(
                                    icon=ft.Icons.MORE_VERT_ROUNDED,
                                    icon_color=ft.Colors.BLACK,
                                    icon_size=18,
                                    tooltip="More options",
                                    items=[
                                        ft.PopupMenuItem(
                                            height=30,
                                            content="Remove Connection",
                                            icon=ft.Icons.PERSON_REMOVE_ROUNDED,
                                            on_click=lambda e, u=uid: page.run_task(do_remove_friend, u),
                                        )
                                    ],
                                ),
                            ],
                        ),
                    ),
                ],
            ),
        )

        def rebuild_grid(friends: list):
            grid.controls = [_friend_card(f) for f in friends]
            try:
                if page.views:
                    page.update()
            except Exception:
                pass

        def on_search(e):
            q = (e.control.value or "").strip().lower()
            if not q:
                rebuild_grid(all_friends)
                return
            rebuild_grid([
                f for f in all_friends
                if q in (f.get("first_name") or "").lower()
                or q in (f.get("last_name")  or "").lower()
                or q in (f.get("university")     or "").lower()
                or q in (f.get("org")        or "").lower()
            ])

        if not all_friends:
            content_socket.content = _empty_state(
                ft.Icons.PEOPLE_OUTLINE_ROUNDED,
                "Your network is a blank canvas",
                "Connect with peers and start building your circle.",
                action_label="Find Peers",
                # Fix: must use page.run_task because switch_tab is async
                on_action=lambda: page.run_task(switch_tab, 2),
            )
            return

        search = ft.TextField(
            hint_text="Search your network…",
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            border_radius=10,
            border_color=ft.Colors.GREY_300,
            focused_border_color=ft.Colors.PRIMARY,
            fill_color=ft.Colors.GREY_50,
            filled=True,
            expand=True,
            height=44,
            text_size=13,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=10),
            on_change=on_search,
        )

        content_socket.content = ft.Column(
            expand=True,
            spacing=0,
            controls=[
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=16),
                    content=ft.Row(controls=[search]),
                ),
                ft.Container(height=8),
                ft.Container(
                    expand=True,
                    content=ft.Column(
                        expand=True,
                        scroll=ft.ScrollMode.AUTO,
                        controls=[
                            ft.Container(
                                padding=ft.padding.symmetric(horizontal=16, vertical=4),
                                content=grid,
                            ),
                            ft.Container(height=20),
                        ],
                    ),
                ),
            ],
        )

        # grid is now mounted; safe to populate and repaint
        rebuild_grid(all_friends)

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

            # Merge any locally-queued sent requests (from Discover tab)
            pending = state.pop("pending_sent", [])  # drain the queue
            state["pending_sent"] = []
            for user in pending:
                # Avoid duplicates
                existing_ids = {r["user"]["id"] for r in sent_data if "user" in r}
                uid = user.get("id", "")
                if uid and uid not in existing_ids:
                    sent_data.append({
                        "id":   f"local_{uid}",
                        "user": user,
                    })

            state["pending_count"] = len(incoming_data)
            _rebuild_seg()

        except Exception as ex:
            print(f"Failed to fetch requests: {ex}")
            incoming_data, sent_data = [], []

        def _incoming_card(req: dict) -> ft.Container:
            user    = req.get("user") or {}
            card    = ft.Ref[ft.Container]()
            buttons = ft.Ref[ft.Row]()
            confirm = ft.Ref[ft.Row]()

            first  = user.get("first_name") or "Unknown"
            last   = user.get("last_name")  or ""
            university = user.get("university")     or "Student"
            org    = user.get("org")      

            async def on_accept(e):
                buttons.current.visible = False
                confirm.current.visible = True
                if page.views:
                    page.update()
                try:
                    await accept_request(token, req["id"])
                    await asyncio.sleep(0.6)
                    if card.current in incoming_col.controls:
                        incoming_col.controls.remove(card.current)
                        state["pending_count"] = max(0, state["pending_count"] - 1)
                        _rebuild_seg()
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
                        if page.views:
                            page.update()
                except Exception:
                    pass

            return ft.Container(
    ref=card,
    bgcolor=ft.Colors.SURFACE,
    border_radius=16,
    border=ft.border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY)),
    padding=ft.padding.all(0),
    shadow=ft.BoxShadow(
        blur_radius=16,
        spread_radius=0,
        color=ft.Colors.with_opacity(0.07, ft.Colors.PRIMARY),
        offset=ft.Offset(0, 4),
    ),
    content=ft.Column(
        spacing=0,
        controls=[
            # Primary gradient top bar
            ft.Container(
                height=3,
                border_radius=ft.border_radius.only(top_left=16, top_right=16),
                gradient=ft.LinearGradient(
                    begin=ft.Alignment(-1, 0),
                    end=ft.Alignment(1, 0),
                    colors=[ft.Colors.PRIMARY, ft.Colors.with_opacity(0.3, ft.Colors.PRIMARY)],
                ),
            ),
            ft.Container(
                padding=ft.padding.symmetric(horizontal=14, vertical=12),
                content=ft.Row(
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        # Avatar with primary glow ring
                        ft.Container(
                            padding=ft.padding.all(2),
                            border_radius=99,
                            gradient=ft.LinearGradient(
                                begin=ft.Alignment(-1, -1),
                                end=ft.Alignment(1, 1),
                                colors=[ft.Colors.PRIMARY, ft.Colors.with_opacity(0.3, ft.Colors.PRIMARY)],
                            ),
                            content=ft.Container(
                                padding=ft.padding.all(2),
                                bgcolor=ft.Colors.SURFACE,
                                border_radius=99,
                                content=_avatar(user, radius=22),
                            ),
                        ),
                        ft.Column(
                            spacing=3, expand=True,
                            controls=[
                                ft.Text(
                                    f"{first} {last}".strip(),
                                    size=14, weight=ft.FontWeight.W_700,
                                    color=ft.Colors.ON_SURFACE,
                                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                                    expand=True, # Added to ensure name shrinks safely
                                ),
                                ft.Row(
                                    spacing=6,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.Icon(ft.Icons.SCHOOL_ROUNDED,
                                                size=11, color=ft.Colors.GREY_400),
                                        # THE FIX: expand=True added to the university text
                                        ft.Text(university, size=11, color=ft.Colors.GREY_500,
                                                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, 
                                                expand=True), 
                                    ],
                                ),
                                _org_pill(org),
                            ],
                        ),
                        ft.Column(
                            spacing=6,
                            horizontal_alignment=ft.CrossAxisAlignment.END,
                            controls=[
                                ft.Row(
                                    ref=buttons, spacing=8,
                                    controls=[
                                        ft.OutlinedButton(
                                            "Decline", height=34,
                                            style=ft.ButtonStyle(
                                                shape=ft.RoundedRectangleBorder(radius=10),
                                                side=ft.BorderSide(1, ft.Colors.GREY_200),
                                                color=ft.Colors.GREY_400,
                                                padding=ft.padding.symmetric(horizontal=12, vertical=0),
                                            ),
                                            on_click=lambda e: page.run_task(on_decline, e),
                                        ),
                                        ft.Container(
                                            height=34,
                                            border_radius=10,
                                            gradient=ft.LinearGradient(
                                                begin=ft.Alignment(-1, 0),
                                                end=ft.Alignment(1, 0),
                                                colors=[ft.Colors.PRIMARY,
                                                        ft.Colors.with_opacity(0.75, ft.Colors.PRIMARY)],
                                            ),
                                            shadow=ft.BoxShadow(
                                                blur_radius=8,
                                                color=ft.Colors.with_opacity(0.25, ft.Colors.PRIMARY),
                                                offset=ft.Offset(0, 3),
                                            ),
                                            content=ft.ElevatedButton(
                                                "Accept",
                                                bgcolor=ft.Colors.TRANSPARENT,
                                                color=ft.Colors.WHITE,
                                                style=ft.ButtonStyle(
                                                    shape=ft.RoundedRectangleBorder(radius=10),
                                                    elevation=0,
                                                    shadow_color=ft.Colors.TRANSPARENT,
                                                    padding=ft.padding.symmetric(horizontal=12, vertical=0),
                                                    overlay_color=ft.Colors.with_opacity(0.1, ft.Colors.WHITE),
                                                ),
                                                on_click=lambda e: page.run_task(on_accept, e),
                                            ),
                                        ),
                                    ],
                                ),
                                ft.Row(
                                    ref=confirm, visible=False, spacing=6,
                                    controls=[
                                        ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED,
                                                color=ft.Colors.GREEN_500, size=18),
                                        ft.Text("Added!", size=12,
                                                color=ft.Colors.GREEN_600,
                                                weight=ft.FontWeight.W_600),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            ),
        ],
    ))
        
        def _sent_card(req: dict) -> ft.Container:
            user    = req.get("user") or {}
            row     = ft.Ref[ft.Container]()
            btn_ref = ft.Ref[ft.TextButton]()

            first = user.get("first_name") or "Unknown"
            last  = user.get("last_name")  or ""
            org   = user.get("org")       

            async def on_cancel(e):
                btn_ref.current.disabled = True
                btn_ref.current.text = "Canceling…"
                if btn_ref.current.page:
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
                    if btn_ref.current.page:
                        btn_ref.current.update()

            return ft.Container(
    ref=row,
    bgcolor=ft.Colors.SURFACE,
    border_radius=14,
    border=ft.border.all(1, ft.Colors.with_opacity(0.07, ft.Colors.PRIMARY)),
    padding=ft.padding.all(0),
    shadow=ft.BoxShadow(
        blur_radius=10,
        spread_radius=0,
        color=ft.Colors.with_opacity(0.04, ft.Colors.PRIMARY),
        offset=ft.Offset(0, 3),
    ),
    content=ft.Column(
        spacing=0,
        controls=[
            ft.Container(
                height=2,
                border_radius=ft.border_radius.only(top_left=14, top_right=14),
                gradient=ft.LinearGradient(
                    begin=ft.Alignment(-1, 0),
                    end=ft.Alignment(1, 0),
                    colors=[ft.Colors.PURPLE_300, ft.Colors.with_opacity(0.2, ft.Colors.INDIGO_200)],
                ),
            ),
            ft.Container(
                padding=ft.padding.symmetric(horizontal=14, vertical=10),
                content=ft.Row(
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            padding=ft.padding.all(2),
                            border_radius=101,
                            content=ft.Container(
                                padding=ft.padding.all(2),
                                bgcolor=ft.Colors.SURFACE,
                                border_radius=99,
                                content=_avatar(user, radius=18),
                            ),
                        ),
                        ft.Column(
                            spacing=2, expand=True,
                            controls=[
                                ft.Text(
                                    f"{first} {last}".strip(),
                                    size=13, weight=ft.FontWeight.W_600,
                                    color=ft.Colors.ON_SURFACE,
                                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Row(
                                    spacing=5,
                                    visible=bool(org),
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.Icon(ft.Icons.BUSINESS_ROUNDED,
                                                size=10, color=ft.Colors.GREY_400),
                                        ft.Text(org or "", size=11, color=ft.Colors.GREY_400,
                                                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                    ],
                                ),
                            ],
                        ),
                        ft.Container(
                            border_radius=8,
                            height= 30,
                            border=ft.border.all(1, ft.Colors.GREY_200),
                            padding=ft.padding.symmetric(horizontal=10, vertical=5),
                            content=ft.TextButton(
                                ref=btn_ref,
                                content=ft.Text("Cancel", size=11,
                                                weight=ft.FontWeight.W_500,
                                                color=ft.Colors.BLACK_12),
                                style=ft.ButtonStyle(
                                    overlay_color=ft.Colors.with_opacity(0.005, ft.Colors.GREY_400),
                                ),
                                on_click=lambda e: page.run_task(on_cancel, e),
                            ),
                        ),
                    ],
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
                expand=True, scroll=ft.ScrollMode.AUTO,
                controls=[
                    ft.Container(
                        padding=ft.padding.symmetric(horizontal=16, vertical=14),
                        content=ft.Column(
                            spacing=16,
                            controls=[
                                # Incoming header + badge
                                ft.Row(
                                    spacing=8,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        _section_label("Incoming Requests"),
                                        ft.Container(
                                            padding=ft.padding.symmetric(horizontal=7, vertical=2),
                                            bgcolor=ft.Colors.ERROR_CONTAINER,
                                            border_radius=99,
                                            visible=len(incoming_data) > 0,
                                            content=ft.Text(
                                                str(len(incoming_data)), size=10,
                                                color=ft.Colors.ERROR,
                                                weight=ft.FontWeight.W_700,
                                            ),
                                        ),
                                    ],
                                ),
                                incoming_col if incoming_data else ft.Container(
                                    padding=ft.padding.symmetric(vertical=16),
                                    content=ft.Text("No pending requests.",
                                                    size=13, color=ft.Colors.GREY_400),
                                ),
                                ft.Divider(height=1, color=ft.Colors.GREY_100),
                                _section_label("Sent Requests"),
                                sent_col if sent_data else ft.Container(
                                    padding=ft.padding.symmetric(vertical=16),
                                    content=ft.Text("No sent requests.",
                                                    size=13, color=ft.Colors.GREY_400),
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
        except Exception as ex:
            print(f"Failed to load discover: {ex}")
            peers_data, org_data, trending_data = [], [], []

        def _discover_card(user: dict) -> ft.Container:
            btn_text  = ft.Ref[ft.Text]()
            btn       = ft.Ref[ft.ElevatedButton]()
            requested = {"v": False}

            first  = user.get("first_name") or "Unknown"
            last   = user.get("last_name")  or ""
            university = user.get("university")     or "Student"
            org    = user.get("org")   
            streak = user.get("streak", 0) or 0
            uid    = user.get("id", "")

            async def on_add(e):
                if requested["v"]:
                    return
                # Optimistic UI update
                requested["v"]         = True
                btn.current.bgcolor    = ft.Colors.GREY_200
                btn_text.current.value = "Requested"
                btn_text.current.color = ft.Colors.GREY_500
                if page.views:
                    page.update()
                try:
                    await asyncio.wait_for(send_request(token, uid), timeout=10)
                    # Queue the user so the Requests tab shows it when opened
                    state["pending_sent"].append(user)
                except Exception as ex:
                    print(f"Request failed: {ex}")
                    # Revert on error
                    requested["v"]         = False
                    btn.current.bgcolor    = ft.Colors.PRIMARY
                    btn_text.current.value = "Add Friend"
                    btn_text.current.color = ft.Colors.WHITE
                    if page.views:
                        page.update()

            return ft.Container(
    width=160,
    bgcolor=ft.Colors.SURFACE,
    border_radius=14,
    border=ft.border.all(1, ft.Colors.GREY_200),
    shadow=ft.BoxShadow(
        blur_radius=12,
        color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
        offset=ft.Offset(0, 3),
    ),
    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
    content=ft.Column(
        spacing=0,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            # gradient banner
            ft.Container(
                height=52,
                gradient=ft.LinearGradient(
                    begin=ft.Alignment(-1, -1),
                    end=ft.Alignment(1, 1),
                    colors=["#3B82F6", "#818CF8", "#C084FC"],
                ),
            ),
            # floating avatar
            ft.Container(
                content=ft.Container(
                    content=_avatar(user, radius=26),
                    border=ft.border.all(3, ft.Colors.SURFACE),
                    border_radius=30,
                ),
                margin=ft.margin.only(top=-26),
            ),
            # body
            ft.Container(
                padding=ft.padding.only(left=10, right=10, top=6, bottom=12),
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                    controls=[
                        ft.Text(
                            f"{first} {last}".strip(),
                            size=13, weight=ft.FontWeight.W_700,
                            color=ft.Colors.ON_SURFACE,
                            text_align=ft.TextAlign.CENTER,
                            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Text(
                            university, size=10, color=ft.Colors.GREY_500,
                            text_align=ft.TextAlign.CENTER,
                            max_lines=2, overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Container(height=2),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=4,
                            controls=[
                                _org_pill(org),
                                ft.Container(
                                    padding=ft.padding.symmetric(horizontal=6, vertical=3),
                                    bgcolor=ft.Colors.ORANGE_50 if streak > 0 else ft.Colors.GREY_100,
                                    border_radius=99,
                                    content=ft.Row(
                                        tight=True, spacing=3,
                                        controls=[
                                            ft.Icon(ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED,
                                                    size=10,
                                                    color=ft.Colors.ORANGE_500 if streak > 0 else ft.Colors.BLUE_100),
                                            ft.Text(str(streak), size=9,
                                                    color=ft.Colors.ORANGE_700 if streak > 0 else ft.Colors.BLUE_200,
                                                    weight=ft.FontWeight.W_700),
                                        ],
                                    ),
                                ),
                            ],
                        ),
                        ft.Container(height=2),
                        ft.ElevatedButton(
                            ref=btn,
                            content=ft.Text(ref=btn_text, value="Add Friend",
                                            size=11, color=ft.Colors.WHITE,
                                            weight=ft.FontWeight.W_600),
                            bgcolor=ft.Colors.PRIMARY,
                            expand=True,
                            height=30,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=8),
                                elevation=0,
                            ),
                            on_click=lambda e: page.run_task(on_add, e),
                        ),
                    ],
                ),
            ),
        ],
    ),
)

        def _horizontal_row(title: str, users: list, subtitle: str = "") -> ft.Container:
            if not users:
                body = ft.Container(
                    padding=ft.padding.symmetric(vertical=12),
                    content=ft.Text("Nothing to show here yet.",
                                    size=13, color=ft.Colors.GREY_400),
                )
            else:
                body = ft.Row(
                    scroll=ft.ScrollMode.AUTO,
                    spacing=12,
                    controls=[_discover_card(u) for u in users],
                )
            return ft.Container(
                content=ft.Column(
                    spacing=10,
                    controls=[
                        ft.Column(
                            spacing=2,
                            controls=[
                                _section_label(title),
                                ft.Text(subtitle, size=12, color=ft.Colors.GREY_400)
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
                        padding=ft.padding.symmetric(horizontal=16, vertical=14),
                        content=ft.Column(
                            spacing=20,
                            controls=[
                                _horizontal_row(
                                    "Peers at your university",
                                    peers_data,
                                    "Connect with your Schoolmates",
                                ),
                                ft.Divider(height=1, color=ft.Colors.GREY_100),
                                _horizontal_row(
                                    "People at your organisation",
                                    org_data,
                                    "Teamwork makes the dream work",
                                ),
                                ft.Divider(height=1, color=ft.Colors.GREY_100),
                                _horizontal_row(
                                    "Trending Learners",
                                    trending_data,
                                    "Its hot in here! Connect with High-streak active learners this week",
                                ),
                                ft.Container(height=20),
                            ],
                        ),
                    )
                ],
            ),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # BOOT
    # ─────────────────────────────────────────────────────────────────────────
    # Build seg pills without triggering .update() (view not on page yet)
    _rebuild_seg(do_update=False)

    # Set initial spinner so the view renders immediately with something visible
    content_socket.content = _loading_spinner("Loading your network…")

    view = ft.View(
        route="/network",
        appbar=app_bar,
        bottom_appbar=app_bar_bottom,
        bgcolor=ft.Colors.GREY_50,
        padding=0,
        controls=[
            ft.SafeArea(
                expand=True,
                content=ft.Column(
                    expand=True,
                    spacing=0,
                    controls=[
                        seg_row,
                        ft.Container(expand=True, content=content_socket),
                    ],
                ),
            )
        ],
    )

    # Kick off data load AFTER the view is appended to page.views by the caller.
    # A single sleep(0) yields control so route_change can finish appending the
    # view before switch_tab tries to call page.update() on mounted controls.
    async def _boot():
        await asyncio.sleep(0)
        await switch_tab(0)

    page.run_task(_boot)

    return view