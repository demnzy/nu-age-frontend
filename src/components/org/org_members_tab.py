import asyncio
import flet as ft
from src.components.org.org_member_role_modal import open_change_role_modal
from src.requests.organisations import (
    get_pending_invitations,
    remove_organisation_member,
    revoke_invitation,
)
from src.utils.file_opener import safe_set_clipboard, show_page_snackbar


def build_org_members_tab(
    page: ft.Page,
    org_id: str,
    org_name: str,
    owner_id: str,
    members: list,
    theme_color: str,
    token: str,
    on_member_removed=None,
    on_member_role_updated=None,
) -> ft.Column:
    """
    Renders the Members & Faculty tab for organization administrators.
    Provides live search, role filtering, role promotion/demotion,
    pending invite tracking & revocation, and member removal.
    """
    search_query = ""
    filter_role = "all"  # all, staff, students, invites
    pending_invites: list[dict] = []
    invites_loaded = False

    content_holder = ft.Column(spacing=8)

    def _get_filtered():
        res = list(members)
        if search_query.strip():
            q = search_query.strip().lower()
            res = [
                m for m in res
                if q in f"{m.get('first_name', '')} {m.get('last_name', '')}".lower()
                or q in str(m.get("email", "")).lower()
            ]

        if filter_role == "staff":
            res = [m for m in res if str(m.get("role", "")).upper() in ("TEACHER", "STAFF", "ADMIN", "OWNER", "INSTRUCTOR")]
        elif filter_role == "students":
            res = [m for m in res if str(m.get("role", "")).upper() == "STUDENT"]
        return res

    def _reset_filters(e=None):
        nonlocal search_query, filter_role
        search_query = ""
        filter_role = "all"
        search_box.value = ""
        _update_filter_bar()
        _rebuild_cards()
        page.update()

    def _role_badge(role_str: str) -> ft.Container:
        r = role_str.upper()
        if r in ("OWNER", "CREATOR"):
            bg = ft.Colors.with_opacity(0.12, ft.Colors.INDIGO_600)
            fg = ft.Colors.INDIGO_600
        elif r == "ADMIN":
            bg = ft.Colors.with_opacity(0.12, ft.Colors.BLUE_600)
            fg = ft.Colors.BLUE_600
        elif r in ("TEACHER", "INSTRUCTOR", "STAFF"):
            bg = ft.Colors.with_opacity(0.12, ft.Colors.AMBER_600)
            fg = ft.Colors.AMBER_700
        else:
            bg = ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE_VARIANT)
            fg = ft.Colors.ON_SURFACE_VARIANT

        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=2.5),
            border_radius=8,
            bgcolor=bg,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.2, fg)),
            content=ft.Text(r, size=9.5, weight=ft.FontWeight.BOLD, color=fg),
        )

    def _confirm_remove(uid: str, name: str, email: str):
        def _close_dialog(ev=None):
            dialog.open = False
            page.update()

        async def _do_remove(ev=None):
            confirm_btn.disabled = True
            confirm_btn.content = ft.Row([
                ft.ProgressRing(width=14, height=14, color=ft.Colors.RED_600, stroke_width=2),
                ft.Text("Removing…", size=12, color=ft.Colors.RED_600),
            ], tight=True, spacing=6)
            page.update()

            try:
                auth_tok = token or await page.shared_preferences.get("auth_token")
                res = await remove_organisation_member(auth_tok, org_id, uid)
            except Exception as ex:
                res = {"error": str(ex)}
            finally:
                _close_dialog()

            if isinstance(res, dict) and "error" in res:
                err_msg = res["error"]
                show_page_snackbar(page, f"Could not remove member: {err_msg}")
            else:
                nonlocal members
                members[:] = [m for m in members if str(m.get("id", "")) != uid]
                _rebuild_cards()
                _update_filter_bar()
                if on_member_removed:
                    on_member_removed(uid, name)
                show_page_snackbar(page, f"{name} was removed from {org_name}.")

        confirm_btn = ft.TextButton("Remove", style=ft.ButtonStyle(color=ft.Colors.RED_600), on_click=_do_remove)
        cancel_btn = ft.TextButton("Cancel", on_click=_close_dialog)

        dialog = ft.AlertDialog(
            modal=True,
            bgcolor=ft.Colors.SURFACE,
            shape=ft.RoundedRectangleBorder(radius=16),
            title=ft.Row([
                ft.Icon(ft.Icons.WARNING_ROUNDED, color=ft.Colors.RED_500, size=22),
                ft.Text("Remove Member", weight=ft.FontWeight.W_700, size=16),
            ], spacing=8),
            content=ft.Container(
                width=360,
                content=ft.Column([
                    ft.Text(f"Are you sure you want to remove {name} from {org_name}?", size=13, color=ft.Colors.ON_SURFACE),
                    ft.Text(f"Email: {email}", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Container(height=4),
                    ft.Text(
                        "They will immediately lose access to all courses and private resources in this organization.",
                        size=12,
                        color=ft.Colors.RED_700,
                    ),
                ], tight=True, spacing=6),
            ),
            actions=[cancel_btn, confirm_btn],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        page.overlay.append(dialog)
        dialog.open = True
        page.update()

    async def _copy_email(email_str: str):
        try:
            await safe_set_clipboard(page, email_str)
            show_page_snackbar(page, "Email copied to clipboard!")
        except Exception as ex:
            print(f"[org_members_tab] copy email error: {ex}")

    def _on_role_updated(uid: str, new_role: str):
        for m in members:
            if str(m.get("id", "")) == uid:
                m["role"] = new_role
                break
        _update_filter_bar()
        _rebuild_cards()
        if on_member_role_updated:
            on_member_role_updated(uid, new_role)
        page.update()

    def _build_member_row(m: dict) -> ft.Container:
        uid = str(m.get("id", ""))
        first_name = m.get("first_name", "")
        last_name = m.get("last_name", "")
        full_name = f"{first_name} {last_name}".strip() or "Academy Member"
        email = m.get("email", "")
        is_owner = (uid == owner_id)
        role_str = "OWNER" if is_owner else m.get("role", "STUDENT").upper()
        initials = f"{first_name[0] if first_name else '?'}{last_name[0] if last_name else ''}".upper()

        menu_items = [
            ft.PopupMenuItem(
                content=ft.Text("View Profile", size=13),
                icon=ft.Icons.PERSON_SEARCH_ROUNDED,
                on_click=lambda _, u=uid: page.navigate(f"/member/{u}"),
            ),
            ft.PopupMenuItem(
                content=ft.Text("Copy Email", size=13),
                icon=ft.Icons.CONTENT_COPY_ROUNDED,
                on_click=lambda _, em=email: page.run_task(_copy_email, em),
            ),
        ]
        if not is_owner:
            menu_items.extend([
                ft.PopupMenuItem(
                    content=ft.Text("Change Role", size=13),
                    icon=ft.Icons.MANAGE_ACCOUNTS_ROUNDED,
                    on_click=lambda _, m_data=m: open_change_role_modal(
                        page=page,
                        org_id=org_id,
                        member_data=m_data,
                        theme_color=theme_color,
                        token=token,
                        on_role_changed=_on_role_updated,
                    ),
                ),
                ft.PopupMenuItem(
                    content=ft.Text("Remove Member", size=13, color=ft.Colors.RED_600),
                    icon=ft.Icons.PERSON_REMOVE_OUTLINED,
                    on_click=lambda _, u=uid, n=full_name, em=email: _confirm_remove(u, n, em),
                ),
            ])

        avatar_url = m.get("profile_picture_url")
        has_avatar = avatar_url and str(avatar_url).startswith("http")

        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=14, vertical=12),
            bgcolor=ft.Colors.SURFACE,
            border_radius=12,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            content=ft.Row([
                ft.Row([
                    ft.CircleAvatar(
                        foreground_image_src=avatar_url if has_avatar else None,
                        content=ft.Text(initials, size=13, weight=ft.FontWeight.BOLD) if not has_avatar else None,
                        bgcolor=ft.Colors.with_opacity(0.12, theme_color),
                        color=theme_color,
                        radius=20,
                    ),
                    ft.Column([
                        ft.Row([
                            ft.Text(
                                full_name,
                                size=13.5,
                                weight=ft.FontWeight.W_600,
                                color=ft.Colors.ON_SURFACE,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            _role_badge(role_str),
                        ], spacing=8, tight=True),
                        ft.Text(
                            email,
                            size=11.5,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ], spacing=2, expand=True),
                ], spacing=12, expand=True),
                ft.PopupMenuButton(
                    icon=ft.Icons.MORE_VERT_ROUNDED,
                    icon_color=ft.Colors.ON_SURFACE_VARIANT,
                    items=menu_items,
                ),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        )

    # ── Pending Invitations List ─────────────────────────────────────────────
    async def _revoke_invite(invite_id: str, email_label: str):
        auth_tok = token or await page.shared_preferences.get("auth_token")
        res = await revoke_invitation(auth_tok, invite_id)
        if isinstance(res, dict) and not res.get("error"):
            nonlocal pending_invites
            pending_invites[:] = [inv for inv in pending_invites if str(inv.get("id")) != invite_id]
            _update_filter_bar()
            _rebuild_cards()
            show_page_snackbar(page, f"Invitation for {email_label} was revoked.")
        else:
            err = res.get("error", "Failed to revoke.") if isinstance(res, dict) else "Error"
            show_page_snackbar(page, f"Could not revoke: {err}")

    def _build_invite_row(inv: dict) -> ft.Container:
        inv_id = str(inv.get("id", ""))
        em = inv.get("email", "Invitation Link")
        r = str(inv.get("role", "STUDENT")).upper()

        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=14, vertical=12),
            bgcolor=ft.Colors.SURFACE,
            border_radius=12,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            content=ft.Row([
                ft.Row([
                    ft.Container(
                        width=38,
                        height=38,
                        border_radius=19,
                        bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.AMBER_600),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(ft.Icons.MAIL_OUTLINE_ROUNDED, size=18, color=ft.Colors.AMBER_700),
                    ),
                    ft.Column([
                        ft.Row([
                            ft.Text(em, size=13.5, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                            _role_badge(r),
                        ], spacing=8, tight=True),
                        ft.Text("Invitation Pending Acceptance", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], spacing=2, expand=True),
                ], spacing=12, expand=True),
                ft.OutlinedButton(
                    "Revoke",
                    icon=ft.Icons.CANCEL_OUTLINED,
                    style=ft.ButtonStyle(
                        color=ft.Colors.RED_600,
                        side=ft.BorderSide(1, ft.Colors.with_opacity(0.25, ft.Colors.RED_600)),
                        shape=ft.RoundedRectangleBorder(radius=8),
                        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                    ),
                    on_click=lambda _, i_id=inv_id, eml=em: page.run_task(_revoke_invite, i_id, eml),
                ),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        )

    def _rebuild_cards():
        if filter_role == "invites":
            if pending_invites:
                content_holder.controls = [_build_invite_row(inv) for inv in pending_invites]
            else:
                content_holder.controls = [
                    ft.Container(
                        padding=ft.Padding.symmetric(vertical=48, horizontal=24),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=10,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.MARK_EMAIL_READ_OUTLINED, size=46, color=ft.Colors.with_opacity(0.3, ft.Colors.ON_SURFACE)),
                                ft.Text("No pending invitations", size=14, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                                ft.Text("All sent invites have been claimed or expired.", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Container(height=6),
                                ft.FilledButton(
                                    "Send New Invite",
                                    icon=ft.Icons.PERSON_ADD_ROUNDED,
                                    style=ft.ButtonStyle(bgcolor=theme_color, shape=ft.RoundedRectangleBorder(radius=10)),
                                    on_click=lambda _: page.navigate(f"/organisations/{org_id}/invite-members"),
                                ),
                            ],
                        ),
                    )
                ]
            return

        filtered = _get_filtered()
        if filtered:
            cards = [_build_member_row(m) for m in filtered]
            content_holder.controls = cards
        else:
            has_filter = bool(search_query.strip()) or filter_role != "all"
            if has_filter:
                content_holder.controls = [
                    ft.Container(
                        padding=ft.Padding.symmetric(vertical=48, horizontal=24),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=10,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.PERSON_SEARCH_ROUNDED, size=46, color=ft.Colors.with_opacity(0.3, ft.Colors.ON_SURFACE)),
                                ft.Text(
                                    "No members match your search criteria.",
                                    size=14,
                                    weight=ft.FontWeight.W_600,
                                    color=ft.Colors.ON_SURFACE,
                                ),
                                ft.Text(
                                    "Try clearing the query or toggling role filters.",
                                    size=12,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                                ft.Container(height=6),
                                ft.OutlinedButton(
                                    "Reset Filters",
                                    icon=ft.Icons.REFRESH_ROUNDED,
                                    on_click=_reset_filters,
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=10),
                                        side=ft.BorderSide(1, ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE)),
                                    ),
                                ),
                            ],
                        ),
                    )
                ]
            else:
                content_holder.controls = [
                    ft.Container(
                        padding=ft.Padding.symmetric(vertical=48, horizontal=24),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=10,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.GROUPS_ROUNDED, size=46, color=ft.Colors.with_opacity(0.3, ft.Colors.ON_SURFACE)),
                                ft.Text(
                                    "No members enrolled yet.",
                                    size=14,
                                    weight=ft.FontWeight.W_600,
                                    color=ft.Colors.ON_SURFACE,
                                ),
                                ft.Text(
                                    "Invite instructors and students to build your workspace community.",
                                    size=12,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                                ft.Container(height=6),
                                ft.FilledButton(
                                    "Invite Members",
                                    icon=ft.Icons.PERSON_ADD_ROUNDED,
                                    style=ft.ButtonStyle(
                                        bgcolor=theme_color,
                                        shape=ft.RoundedRectangleBorder(radius=10),
                                    ),
                                    on_click=lambda _: page.navigate(f"/organisations/{org_id}/invite-members"),
                                ),
                            ],
                        ),
                    )
                ]

    def _on_search(e):
        nonlocal search_query
        search_query = e.control.value or ""
        _rebuild_cards()
        page.update()

    search_box = ft.TextField(
        hint_text="Search members by name or email…",
        prefix_icon=ft.Icons.SEARCH_ROUNDED,
        border_radius=10,
        dense=True,
        content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        on_change=_on_search,
        border_color=ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE),
        focused_border_color=theme_color,
        expand=True,
    )

    def _set_role(role_key: str):
        nonlocal filter_role
        filter_role = role_key
        _update_filter_bar()
        _rebuild_cards()
        page.update()

    def _role_chip(label: str, key: str) -> ft.Container:
        is_active = (filter_role == key)
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            border_radius=18,
            bgcolor=theme_color if is_active else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
            ink=True,
            on_click=lambda _: _set_role(key),
            content=ft.Text(
                label,
                size=11,
                weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.NORMAL,
                color=ft.Colors.WHITE if is_active else ft.Colors.ON_SURFACE,
            ),
        )

    filter_row = ft.Row(spacing=8, scroll=ft.ScrollMode.AUTO)

    def _update_filter_bar():
        staff_cnt = sum(
            1 for m in members
            if str(m.get("role", "")).upper() in ("TEACHER", "STAFF", "ADMIN", "OWNER", "INSTRUCTOR")
        )
        students_cnt = sum(
            1 for m in members
            if str(m.get("role", "")).upper() == "STUDENT"
        )
        invites_tag = f" ({len(pending_invites)})" if pending_invites else ""
        filter_row.controls = [
            _role_chip(f"All ({len(members)})", "all"),
            _role_chip(f"Faculty & Staff ({staff_cnt})", "staff"),
            _role_chip(f"Students ({students_cnt})", "students"),
            _role_chip(f"Pending Invites{invites_tag}", "invites"),
        ]

    async def _fetch_invites():
        nonlocal pending_invites, invites_loaded
        if not invites_loaded:
            try:
                auth_tok = token or await page.shared_preferences.get("auth_token")
                inv_list = await get_pending_invitations(auth_tok, org_id)
                if isinstance(inv_list, list):
                    pending_invites = inv_list
                    invites_loaded = True
                    _update_filter_bar()
                    if filter_role == "invites":
                        _rebuild_cards()
                    page.update()
            except Exception as ex:
                print(f"[org_members_tab] fetch invites error: {ex}")

    # Initial setup
    _update_filter_bar()
    _rebuild_cards()
    page.run_task(_fetch_invites)

    # Header Row
    header_row = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Column(
                spacing=1,
                expand=True,
                controls=[
                    ft.Text(
                        "Members & Faculty",
                        size=16,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.ON_SURFACE,
                        no_wrap=True,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Text(
                        f"{len(members)} total community members enrolled",
                        size=11,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        no_wrap=True,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                ],
            ),
            ft.FilledButton(
                "Invite Member",
                icon=ft.Icons.PERSON_ADD_ROUNDED,
                style=ft.ButtonStyle(
                    bgcolor=theme_color,
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                ),
                on_click=lambda _: page.navigate(f"/organisations/{org_id}/invite-members"),
            ),
        ],
    )

    return ft.Column(
        spacing=14,
        controls=[
            header_row,
            search_box,
            filter_row,
            content_holder,
        ],
    )
