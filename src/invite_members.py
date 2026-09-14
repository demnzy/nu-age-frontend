from datetime import datetime, timezone
import flet as ft
from src.components.bottom_appbar import get_bottom_appbar
from src.requests.organisations import (
    revoke_invitation,
    get_pending_invitations,
    send_org_invite,
    get_my_organisation,
)


def _get_palette(is_dark: bool, theme_accent: str | None = None) -> dict:
    accent = theme_accent or ft.Colors.PRIMARY
    return {
        "card_bg": "#181B24" if is_dark else "#FFFFFF",
        "card_bg_subtle": "#222736" if is_dark else "#F8FAFC",
        "border": ft.Colors.with_opacity(0.12, ft.Colors.WHITE) if is_dark else ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
        "border_focus": accent,
        "text_primary": "#F8FAFC" if is_dark else "#0F172A",
        "text_secondary": "#94A3B8" if is_dark else "#64748B",
        "text_tertiary": "#64748B" if is_dark else "#94A3B8",
        "input_bg": "#1E2230" if is_dark else "#F8FAFC",
        "accent": accent,
        "accent_light": ft.Colors.with_opacity(0.12, accent),
    }


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


async def invite_members_view(page: ft.Page, org_id: str):
    app_bar = get_bottom_appbar(page)
    is_dark = page.theme_mode == ft.ThemeMode.DARK

    # ── Initial Loading Socket ────────────────────────────────────────────────
    content_socket = ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        content=ft.ProgressRing(color=ft.Colors.PRIMARY, stroke_width=3, width=36, height=36),
    )

    # ── Async Data Fetcher & Renderer ─────────────────────────────────────────
    async def load_invite_data():
        token = await page.shared_preferences.get("auth_token")
        org_data = await get_my_organisation(token) or {}
        theme_accent = org_data.get("theme_color") or ft.Colors.PRIMARY
        p = _get_palette(page.theme_mode == ft.ThemeMode.DARK, theme_accent)

        # Pending invites
        pending = await get_pending_invitations(token, org_id)
        if not isinstance(pending, list):
            pending = []

        # ── Role Selection State ──────────────────────────────────────────────
        selected_role = ["STUDENT"]

        # ── Form Fields ───────────────────────────────────────────────────────
        email_field = ft.TextField(
            hint_text="colleague@university.edu",
            keyboard_type=ft.KeyboardType.EMAIL,
            autofocus=True,
            text_size=13,
            color=p["text_primary"],
            bgcolor=p["input_bg"],
            border_radius=12,
            border_color=p["border"],
            focused_border_color=p["accent"],
            cursor_color=p["accent"],
            prefix_icon=ft.Icons.ALTERNATE_EMAIL_ROUNDED,
            content_padding=ft.Padding.symmetric(horizontal=16, vertical=14),
            expand=True,
        )

        error_banner = ft.Container(
            visible=False,
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.RED_400),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.25, ft.Colors.RED_400)),
            content=ft.Row(
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, color=ft.Colors.RED_400, size=16),
                    ft.Text("", color=ft.Colors.RED_400, size=12, weight=ft.FontWeight.W_500, expand=True),
                ],
            ),
        )

        # Role Selector Pill Buttons
        def build_role_pill(role_key: str, label: str, icon_name):
            is_active = selected_role[0] == role_key
            
            def on_select_role(e):
                selected_role[0] = role_key
                update_role_pills()
                page.update()

            return ft.Container(
                ink=True,
                on_click=on_select_role,
                expand=True,
                padding=ft.Padding.symmetric(vertical=10),
                border_radius=10,
                border=ft.Border.all(
                    1.5 if is_active else 1,
                    p["accent"] if is_active else p["border"]
                ),
                bgcolor=p["accent_light"] if is_active else p["input_bg"],
                animate=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=6,
                    controls=[
                        ft.Icon(
                            icon_name,
                            size=15,
                            color=p["accent"] if is_active else p["text_secondary"]
                        ),
                        ft.Text(
                            label,
                            size=12,
                            weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.W_600,
                            color=p["accent"] if is_active else p["text_secondary"]
                        ),
                    ],
                ),
            )

        role_row = ft.Row(spacing=10)

        def update_role_pills():
            role_row.controls = [
                build_role_pill("STUDENT", "Student Member", ft.Icons.SCHOOL_ROUNDED),
                build_role_pill("TEACHER", "Teacher / Instructor", ft.Icons.CO_PRESENT_ROUNDED),
            ]

        update_role_pills()

        invite_btn = ft.FilledButton(
            "Send Invitation",
            icon=ft.Icons.SEND_ROUNDED,
            height=46,
            style=ft.ButtonStyle(
                bgcolor=p["accent"],
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=12),
                elevation=0,
                padding=ft.Padding.symmetric(horizontal=24, vertical=12),
            ),
        )

        # ── Pending List & Count ──────────────────────────────────────────────
        pending_list = ft.Column(spacing=8)
        count_badge = ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=3),
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_500),
            border_radius=20,
            content=ft.Text(
                str(len(pending)),
                size=11,
                color=ft.Colors.AMBER_500,
                weight=ft.FontWeight.BOLD,
            ),
        )

        def _role_tag(role: str):
            is_teacher = role.upper() == "TEACHER"
            bg_color = ft.Colors.with_opacity(0.12, ft.Colors.PURPLE_400 if is_teacher else ft.Colors.INDIGO_400)
            fg_color = ft.Colors.PURPLE_400 if is_teacher else ft.Colors.INDIGO_400
            return ft.Container(
                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                bgcolor=bg_color,
                border_radius=8,
                content=ft.Text(
                    role.capitalize(),
                    size=10,
                    color=fg_color,
                    weight=ft.FontWeight.BOLD,
                ),
            )

        def _rebuild_pending():
            pending_list.controls.clear()
            count_badge.content.value = str(len(pending))

            if not pending:
                pending_list.controls.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(vertical=32),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=8,
                            controls=[
                                ft.Container(
                                    width=44,
                                    height=44,
                                    border_radius=22,
                                    bgcolor=p["card_bg_subtle"],
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.Icon(
                                        ft.Icons.OUTBOX_ROUNDED,
                                        size=22,
                                        color=p["text_tertiary"],
                                    ),
                                ),
                                ft.Text(
                                    "No Pending Invitations",
                                    size=13,
                                    weight=ft.FontWeight.BOLD,
                                    color=p["text_primary"],
                                ),
                                ft.Text(
                                    "All team members and students have accepted their invites.",
                                    size=11,
                                    color=p["text_secondary"],
                                    text_align=ft.TextAlign.CENTER,
                                ),
                            ],
                        ),
                    )
                )
                return

            for inv in pending:
                invite_id = inv.get("id", "")

                async def on_revoke(e, iid=invite_id):
                    ok = await revoke_invitation(token, iid)
                    if ok:
                        pending[:] = [i for i in pending if i.get("id") != iid]
                        _rebuild_pending()
                        page.update()

                row = ft.Container(
                    bgcolor=p["card_bg"],
                    border_radius=14,
                    border=ft.Border.all(1, p["border"]),
                    padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                    shadow=ft.BoxShadow(
                        blur_radius=8,
                        color=ft.Colors.with_opacity(0.03, ft.Colors.BLACK),
                        offset=ft.Offset(0, 2),
                    ),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(
                                expand=True,
                                spacing=12,
                                controls=[
                                    ft.Container(
                                        width=38,
                                        height=38,
                                        border_radius=19,
                                        bgcolor=p["accent_light"],
                                        alignment=ft.Alignment.CENTER,
                                        content=ft.Icon(
                                            ft.Icons.MAIL_OUTLINED,
                                            size=18,
                                            color=p["accent"],
                                        ),
                                    ),
                                    ft.Column(
                                        spacing=3,
                                        expand=True,
                                        controls=[
                                            ft.Text(
                                                inv.get("email", "Unknown"),
                                                size=13,
                                                weight=ft.FontWeight.BOLD,
                                                color=p["text_primary"],
                                                max_lines=1,
                                                overflow=ft.TextOverflow.ELLIPSIS,
                                            ),
                                            ft.Row(
                                                spacing=8,
                                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                                controls=[
                                                    _role_tag(inv.get("role", "STUDENT")),
                                                    ft.Text(
                                                        f"Sent {_time_ago(inv.get('sent_at', ''))}",
                                                        size=10,
                                                        color=p["text_secondary"],
                                                    ),
                                                ],
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE_ROUNDED,
                                icon_color=ft.Colors.RED_400,
                                icon_size=17,
                                tooltip="Revoke invite",
                                style=ft.ButtonStyle(
                                    bgcolor={"": ft.Colors.with_opacity(0.08, ft.Colors.RED_400)},
                                    shape=ft.CircleBorder(),
                                ),
                                on_click=on_revoke,
                            ),
                        ],
                    ),
                )
                pending_list.controls.append(row)

        _rebuild_pending()

        # ── Send Invite Handler ───────────────────────────────────────────────
        async def on_send_invite(_e):
            email = (email_field.value or "").strip()
            role = selected_role[0]

            error_banner.visible = False
            if not email or "@" not in email:
                error_banner.content.controls[1].value = "Please enter a valid email address."
                error_banner.visible = True
                page.update()
                return

            org_email = (org_data.get("email") or "").strip().lower()
            if org_email and email.lower() == org_email:
                error_banner.content.controls[1].value = "You cannot invite the organization's own primary email address."
                error_banner.visible = True
                page.update()
                return

            if any(i.get("email", "").lower() == email.lower() for i in pending):
                error_banner.content.controls[1].value = "An active invitation has already been sent to this email."
                error_banner.visible = True
                page.update()
                return

            invite_btn.disabled = True
            invite_btn.text = "Sending Invitation…"
            page.update()

            try:
                raw_response = await send_org_invite(token, org_id, email, role)
                new_invite = raw_response[0] if isinstance(raw_response, list) and len(raw_response) > 0 else raw_response
                if isinstance(new_invite, dict) and "error" in new_invite:
                    raise Exception(new_invite["error"])

                pending_item = {
                    "id": new_invite.get("token", ""),
                    "email": email,
                    "role": role,
                    "sent_at": datetime.now(tz=timezone.utc).isoformat(),
                }
                pending.insert(0, pending_item)
                email_field.value = ""
                error_banner.visible = False
                _rebuild_pending()

                snack = ft.SnackBar(
                    content=ft.Row(
                        spacing=10,
                        controls=[
                            ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.WHITE, size=18),
                            ft.Text(f"Invitation successfully dispatched to {email}", color=ft.Colors.WHITE, size=13),
                        ],
                    ),
                    bgcolor=ft.Colors.GREEN_600,
                    behavior=ft.SnackBarBehavior.FLOATING,
                    shape=ft.RoundedRectangleBorder(radius=10),
                    margin=ft.Margin.all(16),
                )
                page.show_dialog(snack)

            except Exception as ex:
                err_str = str(ex).strip()
                if err_str.startswith("Error:"):
                    err_str = err_str[6:].strip()
                error_banner.content.controls[1].value = err_str
                error_banner.visible = True

            finally:
                invite_btn.disabled = False
                invite_btn.text = "Send Invitation"
                page.update()

        invite_btn.on_click = on_send_invite

        # ── Header Banner ─────────────────────────────────────────────────────
        header_banner = ft.Container(
            gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
                colors=[
                    p["accent"],
                    ft.Colors.with_opacity(0.85, p["accent"]),
                ],
            ),
            border_radius=ft.BorderRadius.only(bottom_left=28, bottom_right=28),
            padding=ft.Padding(left=16, right=20, top=20, bottom=24),
            shadow=ft.BoxShadow(
                blur_radius=20,
                color=ft.Colors.with_opacity(0.18, p["accent"]),
                offset=ft.Offset(0, 6),
            ),
            content=ft.Row(
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED,
                        icon_color=ft.Colors.WHITE,
                        icon_size=18,
                        tooltip="Back to Organizations",
                        style=ft.ButtonStyle(
                            bgcolor={"": ft.Colors.with_opacity(0.18, ft.Colors.WHITE)},
                            shape=ft.CircleBorder(),
                        ),
                        on_click=lambda _: page.go("/organisations"),
                    ),
                    ft.Column(
                        spacing=2,
                        expand=True,
                        controls=[
                            ft.Text(
                                "Invite New Members",
                                size=18,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.WHITE,
                            ),
                            ft.Row(
                                spacing=6,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Icon(ft.Icons.BUSINESS_ROUNDED, size=13, color=ft.Colors.with_opacity(0.85, ft.Colors.WHITE)),
                                    ft.Text(
                                        org_data.get("name", "Your Organisation"),
                                        size=11,
                                        weight=ft.FontWeight.W_500,
                                        color=ft.Colors.with_opacity(0.9, ft.Colors.WHITE),
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        )

        # ── Form Card ─────────────────────────────────────────────────────────
        form_card = ft.Container(
            bgcolor=p["card_bg"],
            border_radius=18,
            border=ft.Border.all(1, p["border"]),
            padding=ft.Padding.all(20),
            shadow=ft.BoxShadow(
                blur_radius=12,
                color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                offset=ft.Offset(0, 3),
            ),
            content=ft.Column(
                spacing=14,
                controls=[
                    ft.Row(
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(
                                width=36,
                                height=36,
                                border_radius=10,
                                bgcolor=p["accent_light"],
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.PERSON_ADD_ROUNDED, color=p["accent"], size=18),
                            ),
                            ft.Column(
                                spacing=1,
                                controls=[
                                    ft.Text("Direct Email Invitation", size=14, weight=ft.FontWeight.BOLD, color=p["text_primary"]),
                                    ft.Text("The recipient will receive an onboarding join link.", size=11, color=p["text_secondary"]),
                                ],
                            ),
                        ],
                    ),
                    ft.Divider(height=1, color=p["border"]),
                    ft.Text("RECIPIENT EMAIL", size=10, weight=ft.FontWeight.BOLD, color=p["text_secondary"]),
                    email_field,
                    ft.Text("ORGANISATION ROLE", size=10, weight=ft.FontWeight.BOLD, color=p["text_secondary"]),
                    role_row,
                    error_banner,
                    ft.Container(height=4),
                    ft.Row([invite_btn], alignment=ft.MainAxisAlignment.END),
                ],
            ),
        )

        # ── Pending Section Card ──────────────────────────────────────────────
        pending_card = ft.Container(
            bgcolor=p["card_bg"],
            border_radius=18,
            border=ft.Border.all(1, p["border"]),
            padding=ft.Padding.all(20),
            shadow=ft.BoxShadow(
                blur_radius=12,
                color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                offset=ft.Offset(0, 3),
            ),
            content=ft.Column(
                spacing=14,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Icon(ft.Icons.SCHEDULE_ROUNDED, size=18, color=p["accent"]),
                                    ft.Text("Pending Invitations", size=14, weight=ft.FontWeight.BOLD, color=p["text_primary"]),
                                ],
                            ),
                            count_badge,
                        ],
                    ),
                    ft.Divider(height=1, color=p["border"]),
                    pending_list,
                ],
            ),
        )

        # ── Assembly ──────────────────────────────────────────────────────────
        main_body = ft.Container(
            alignment=ft.Alignment.TOP_CENTER,
            content=ft.Container(
                width=min(page.width or 800, 680),
                padding=ft.Padding.symmetric(horizontal=16, vertical=16),
                content=ft.Column(
                    spacing=16,
                    controls=[
                        form_card,
                        pending_card,
                        ft.Container(height=24),
                    ],
                ),
            ),
        )

        content_socket.content = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=0,
            controls=[
                header_banner,
                main_body,
            ],
        )
        content_socket.alignment = None
        page.update()

    page.run_task(load_invite_data)

    return ft.View(
        route=f"/organisations/{org_id}/invite-members",
        bottom_appbar=app_bar,
        bgcolor=ft.Colors.SURFACE,
        padding=0,
        controls=[
            ft.SafeArea(
                expand=True,
                content=content_socket,
            ),
        ],
    )