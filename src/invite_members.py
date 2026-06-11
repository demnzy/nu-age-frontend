

import asyncio
from datetime import datetime, timedelta, timezone

from certifi import contents
import flet as ft
from src.components.bottom_appbar import get_bottom_appbar
from src.requests.organisations import revoke_invitation, get_pending_invitations, send_org_invite, get_my_organisation

# ── shared field style (mirrors org_view.py) ─────────────────────────────────
_INPUT = {
    "border_color": ft.Colors.GREY_300,
    "focused_border_color": ft.Colors.PRIMARY,
    "cursor_color": ft.Colors.PRIMARY,
    "border_radius": 10,
    "width": float("inf"),
    "text_size": 13,
    "content_padding": ft.padding.symmetric(horizontal=14, vertical=12),
}

# ── section label helper ──────────────────────────────────────────────────────
def _section_label(text: str) -> ft.Text:
    return ft.Text(text, size=11, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_600)


# ── mock pending invites ──────────────────────────────────────────────────────
# Replace this list with a real API response when ready.
_now = datetime.now(tz=timezone.utc)

# ── mock send (swap this for your real implementation) ────────────────────────
async def _send_invite_mock(token: str, org_id: str, email: str, role: str) -> dict:
    return await send_org_invite(token, org_id, email, role)


# ── mock revoke (swap this too) ───────────────────────────────────────────────
async def _revoke_invite_mock(token: str, invite_id: str) -> bool:
    return await revoke_invitation(token, invite_id) 


# ── time-ago helper ───────────────────────────────────────────────────────────
def _time_ago(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        diff = datetime.now(tz=timezone.utc) - dt
        s = int(diff.total_seconds())
        if s < 60:
            return "just now"
        if s < 3600:
            return f"{s // 60}m ago"
        if s < 86400:
            return f"{s // 3600}h ago"
        return f"{s // 86400}d ago"
    except Exception:
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# VIEW ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
async def invite_members_view(page: ft.Page, org_id: str):
    app_bar = get_bottom_appbar(page)
    token   = await page.shared_preferences.get("auth_token")
    org_data = await get_my_organisation(token)  # Fetch org data for theming and display
    theme_color = org_data.get("theme_color") or ft.Colors.PRIMARY

    # live list of pending invites (starts from mock; updated on send/revoke)
    pending =  await get_pending_invitations(token, org_id)


    # ── form fields ───────────────────────────────────────────────────────────
    email_field = ft.TextField(
        label="Email address",
        hint_text="colleague@example.com",
        keyboard_type=ft.KeyboardType.EMAIL,
        autofocus=True,
        prefix_icon=ft.Icons.ALTERNATE_EMAIL_ROUNDED,
        **_INPUT,
    )

    role_dropdown = ft.Dropdown(
        label="Role",
        border_color=ft.Colors.GREY_300,
        focused_border_color=ft.Colors.PRIMARY,
        border_radius=10,
        text_size=13,
        content_padding=ft.padding.symmetric(horizontal=14, vertical=12),
        width=float("inf"),
        options=[
            ft.DropdownOption(key="STUDENT", text="Student"),
            ft.DropdownOption(key="TEACHER", text="Teacher"),
        ],
        value="STUDENT",
    )

    error_text = ft.Text(
        "", color=ft.Colors.RED_700, size=12, visible=False,
        weight=ft.FontWeight.W_500,
    )

    invite_btn = ft.Button(
        content="Send Invite",
        icon=ft.Icons.SEND_ROUNDED,
        height=46,
        expand=True,
        color=ft.Colors.WHITE,
        bgcolor=theme_color,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=10),
            elevation=0,
        ),
    )

    # ── pending list container (rebuilt on each change) ───────────────────────
    pending_list = ft.Column(spacing=8)

    def _badge(role: str):
        cfg = {
            "TEACHER": (ft.Colors.ORANGE_50,  ft.Colors.ORANGE_800),
            "STUDENT": (ft.Colors.BLUE_50,    ft.Colors.BLUE_800),
        }
        bg, fg = cfg.get(role.upper(), (ft.Colors.GREY_100, ft.Colors.GREY_800))
        return ft.Container(
            padding=ft.padding.symmetric(horizontal=9, vertical=3),
            bgcolor=bg,
            border_radius=10,
            content=ft.Text(
                role.capitalize(), size=9,
                color=fg, weight=ft.FontWeight.W_700,
            ),
        )

    def _rebuild_pending():
        """Re-renders the pending list from the `pending` array."""
        pending_list.controls.clear()

        if not pending:
            pending_list.controls.append(
                ft.Container(
                    padding=ft.padding.symmetric(vertical=24),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                        controls=[
                            ft.Icon(ft.Icons.MARK_EMAIL_UNREAD_OUTLINED,
                                    size=36, color=ft.Colors.GREY_300),
                            ft.Text("No pending invites",
                                    size=13, color=ft.Colors.GREY_400),
                        ],
                    ),
                )
            )
            return

        for inv in pending:
            print(pending)
            invite_id = inv["id"]

            async def on_revoke(e, iid=invite_id):
                ok = await _revoke_invite_mock(token, iid)   # ← swap here too
                if ok:
                    pending[:] = [i for i in pending if i["id"] != iid]
                    _rebuild_pending()
                    page.update()

            row = ft.Container(
                bgcolor=ft.Colors.SURFACE,
                border_radius=12,
                border=ft.border.all(1, ft.Colors.GREY_100),
                padding=ft.padding.symmetric(horizontal=14, vertical=10),
                shadow=ft.BoxShadow(
                    blur_radius=4,
                    color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK),
                    offset=ft.Offset(0, 2),
                ),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        # Avatar + details
                        ft.Row(
                            expand=True,
                            spacing=12,
                            controls=[
                                ft.Container(
                                    width=40, height=40,
                                    border_radius=20,
                                    bgcolor=ft.Colors.PRIMARY_CONTAINER,
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.Icon(
                                        ft.Icons.EMAIL_OUTLINED,
                                        size=18,
                                        color=ft.Colors.ON_PRIMARY_CONTAINER,
                                    ),
                                ),
                                ft.Column(
                                    spacing=2,
                                    expand=True,
                                    controls=[
                                        ft.Text(
                                            inv["email"],
                                            size=13,
                                            weight=ft.FontWeight.W_600,
                                            color=ft.Colors.ON_SURFACE,
                                            max_lines=1,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                        ),
                                        ft.Row(
                                            spacing=6,
                                            controls=[
                                                _badge(inv["role"]),
                                                ft.Text(
                                                    f"Sent {_time_ago(inv['sent_at'])}",
                                                    size=10,
                                                    color=ft.Colors.GREY_400,
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        # Revoke button
                        ft.IconButton(
                                icon=ft.Icons.CANCEL_OUTLINED,
                                icon_color=ft.Colors.RED_400,
                                icon_size=18,
                                on_click=on_revoke,
                                tooltip=ft.Tooltip(
                                    message="Revoke invite"
                                ),
                        ),
                    ],
                ),
            )
            pending_list.controls.append(row)

    _rebuild_pending()

    # ── send handler ──────────────────────────────────────────────────────────
    async def on_send_invite(_e):
        email = email_field.value.strip() if email_field.value else ""
        role  = role_dropdown.value or "STUDENT"

        # basic client-side validation
        error_text.visible = False
        if not email or "@" not in email:
            error_text.value   = "Please enter a valid email address."
            error_text.visible = True
            page.update()
            return

        # check duplicate
        if any(i["email"].lower() == email.lower() for i in pending):
            error_text.value   = "An invite has already been sent to this address."
            error_text.visible = True
            page.update()
            return

        # loading state
        invite_btn.disabled = True
        invite_btn.text     = "Sending…"
        page.update()

        try:
            new_invite = await _send_invite_mock(token, org_id, email, role)
            pending.insert(0, new_invite)
            email_field.value  = ""
            role_dropdown.value = "STUDENT"
            error_text.visible  = False
            _rebuild_pending()

            # success snackbar
            page.open(ft.SnackBar(
                content=ft.Row(
                    spacing=8,
                    controls=[
                        ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED,
                                color=ft.Colors.WHITE, size=18),
                        ft.Text(
                            f"Invite sent to {email}",
                            color=ft.Colors.WHITE, size=13,
                        ),
                    ],
                ),
                bgcolor=ft.Colors.GREEN_600,
                duration=3000,
            ))

        except new_invite.get("error") as ex:
            error_text.value   = f"Error: {str(ex)}"
            error_text.visible = True

        finally:
            invite_btn.disabled = False
            invite_btn.text     = "Send Invite"
            invite_btn.icon     = ft.Icons.SEND_ROUNDED
            page.update()

    invite_btn.on_click = on_send_invite

    # ── page layout ───────────────────────────────────────────────────────────
    return ft.View(
        route=f"organisations/{org_id}/invite-members",
        bottom_appbar=app_bar,
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        padding=0,
        scroll=ft.ScrollMode.AUTO,
        controls=[
            ft.SafeArea(
                expand=True,
                content=ft.Column(
                    spacing=0,
                    controls=[

                        # ── header bar ─────────────────────────────────────
                        ft.Container(
                            bgcolor=theme_color,
                            border_radius=ft.BorderRadius.only(
                                bottom_left=20, bottom_right=20,
                            ),
                            padding=ft.padding.only(
                                top=16, left=8, right=16, bottom=20,
                            ),
                            content=ft.Row(
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.IconButton(
                                        ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED,
                                        icon_color=ft.Colors.WHITE,
                                        icon_size=20,
                                        on_click=lambda _: page.go("/organisations"),
                                    ),
                                    ft.Column(
                                        spacing=2,
                                        expand=True,
                                        controls=[
                                            ft.Text(
                                                "Invite Member",
                                                size=19,
                                                weight=ft.FontWeight.W_700,
                                                color=ft.Colors.WHITE,
                                            ),
                                            ft.Text(
                                                org_data.get("name", "Your Organisation"),
                                                size=12,
                                                color=ft.Colors.with_opacity(
                                                    0.8, ft.Colors.WHITE,
                                                ),
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ),

                        ft.Container(height=20),

                        # ── invite form card ───────────────────────────────
                        ft.Container(
                            margin=ft.margin.symmetric(horizontal=16),
                            bgcolor=ft.Colors.SURFACE,
                            border_radius=14,
                            border=ft.border.all(1, ft.Colors.GREY_200),
                            shadow=ft.BoxShadow(
                                blur_radius=8,
                                color=ft.Colors.with_opacity(
                                    0.07, ft.Colors.BLACK,
                                ),
                                offset=ft.Offset(0, 3),
                            ),
                            padding=ft.padding.all(20),
                            content=ft.Column(
                                spacing=14,
                                controls=[
                                    # card title
                                    ft.Row(
                                        spacing=8,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                        controls=[
                                            ft.Container(
                                                width=34, height=34,
                                                border_radius=10,
                                                bgcolor=ft.Colors.PRIMARY_CONTAINER,
                                                alignment=ft.Alignment.CENTER,
                                                content=ft.Icon(
                                                    ft.Icons.PERSON_ADD_ROUNDED,
                                                    color=ft.Colors.ON_PRIMARY_CONTAINER,
                                                    size=18,
                                                ),
                                            ),
                                            ft.Column(
                                                spacing=1,
                                                controls=[
                                                    ft.Text(
                                                        "Send an Invite",
                                                        size=15,
                                                        weight=ft.FontWeight.W_700,
                                                        color=ft.Colors.ON_SURFACE,
                                                    ),
                                                    ft.Text(
                                                        "The recipient will receive a join link by email.",
                                                        size=11,
                                                        color=ft.Colors.GREY_500,
                                                    ),
                                                ],
                                            ),
                                        ],
                                    ),

                                    ft.Divider(height=1, color=ft.Colors.GREY_100),

                                    _section_label("EMAIL ADDRESS"),
                                    email_field,

                                    _section_label("ROLE"),
                                    role_dropdown,

                                    error_text,

                                    ft.Row(controls=[invite_btn]),
                                ],
                            ),
                        ),

                        ft.Container(height=24),

                        # ── pending invites section ────────────────────────
                        ft.Container(
                            margin=ft.margin.symmetric(horizontal=16),
                            bgcolor=ft.Colors.SURFACE,
                            border_radius=14,
                            border=ft.border.all(1, ft.Colors.GREY_200),
                            shadow=ft.BoxShadow(
                                blur_radius=6,
                                color=ft.Colors.with_opacity(
                                    0.05, ft.Colors.BLACK,
                                ),
                                offset=ft.Offset(0, 2),
                            ),
                            padding=ft.padding.all(18),
                            content=ft.Column(
                                spacing=12,
                                controls=[
                                    # section header
                                    ft.Row(
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        controls=[
                                            ft.Row(
                                                spacing=8,
                                                controls=[
                                                    ft.Icon(
                                                        ft.Icons.MARK_EMAIL_READ_OUTLINED,
                                                        size=18,
                                                        color=theme_color,
                                                    ),
                                                    ft.Text(
                                                        "Pending Invites",
                                                        size=15,
                                                        weight=ft.FontWeight.W_700,
                                                        color=ft.Colors.ON_SURFACE,
                                                    ),
                                                ],
                                            ),
                                            # live count badge
                                            ft.Container(
                                                padding=ft.padding.symmetric(
                                                    horizontal=10, vertical=3,
                                                ),
                                                bgcolor=ft.Colors.ORANGE_50,
                                                border_radius=20,
                                                content=ft.Text(
                                                    str(len(pending)),
                                                    size=11,
                                                    color=ft.Colors.ORANGE_800,
                                                    weight=ft.FontWeight.W_700,
                                                ),
                                            ),
                                        ],
                                    ),
                                    ft.Divider(height=1, color=ft.Colors.GREY_100),
                                    pending_list,
                                    ft.Container(height=4),
                                ],
                            ),
                        ),

                        ft.Container(height=32),
                    ],
                ),
            ),
        ],
    )