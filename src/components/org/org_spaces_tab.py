"""
Organisation Course Spaces Tab Component.

Provides organization admins, tutors, and learners with a centralized
hub to manage and access living, asynchronous Course Spaces:
- Overview of all Course Spaces created for this organization.
- Live search bar and All / Open / Invite-Only filter chips.
- Creation & editing wizards linking spaces to organization courses.
- Admin quick-actions (Edit settings, Manage linked courses, Regenerate code, Delete space).
- Smart entry / auto-enrollment into the Space Hub (/spaces/{id}).
- 1-tap invite code copying with visual confirmation.
"""

from typing import Optional, Dict, Any, List
import flet as ft

from src.requests.course_spaces import (
    get_organisation_spaces,
    create_course_space,
    update_course_space,
    delete_course_space,
    regenerate_space_code,
    add_courses_to_space,
    remove_course_from_space,
    join_course_space,
    invite_space_members,
)
from src.utils.file_opener import show_page_snackbar, safe_set_clipboard
from src.utils.dropdown_theme import apply_dropdown_theme


def build_org_spaces_tab(
    page: ft.Page,
    org_id: str,
    org_data: dict,
    token: str,
    is_admin: bool,
    org_courses: list,
    org_members: list,
    theme_color=ft.Colors.PRIMARY,
    on_refresh_parent=None,
) -> ft.Column:
    """Constructs the Course Spaces tab for the Organization view."""
    state = {
        "spaces": [],
        "loading": True,
        "search": "",
        "filter": "ALL",  # "ALL", "OPEN", "PRIVATE"
    }

    content_holder = ft.Column(spacing=16)

    def _screen_w() -> int:
        try:
            w = page.width or getattr(page.window, "width", None) or 1024
            return int(w)
        except Exception:
            return 1024

    def _close_dialog(dlg: ft.AlertDialog):
        dlg.open = False
        page.update()

    # ── 1. Fetch Organization Spaces ──────────────────────────────────────────
    async def _fetch_spaces():
        state["loading"] = True
        _render()
        page.update()

        try:
            res = await get_organisation_spaces(token=token, org_id=org_id)
            raw_spaces = res.get("spaces", []) if isinstance(res, dict) else []
            state["spaces"] = raw_spaces
        except Exception as ex:
            print(f"[OrgSpacesTab] Error loading spaces: {ex}")
            state["spaces"] = []
        finally:
            state["loading"] = False

        if on_refresh_parent:
            try:
                on_refresh_parent()
            except Exception:
                pass

        _render()
        page.update()

    # ── 2. Create / Edit Space Modal (Decluttered, Modern Studio) ───────────────
    def _open_create_modal(e=None, existing_space: Optional[dict] = None):
        sw = _screen_w()
        modal_w = min(500, max(280, int(sw * 0.92)))
        is_edit = existing_space is not None

        name_tf = ft.TextField(
            label="Space Name *",
            hint_text="e.g. Operating Systems Cohort & CBT Studio",
            value=(existing_space or {}).get("name", ""),
            dense=True,
            autofocus=True,
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
            focused_border_color=theme_color,
            text_size=13,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=11),
        )
        desc_tf = ft.TextField(
            label="Description (Optional)",
            hint_text="Briefly describe what learners will study, practice, and discuss.",
            value=(existing_space or {}).get("description", "") or "",
            multiline=True,
            min_lines=2,
            max_lines=3,
            dense=True,
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
            focused_border_color=theme_color,
            text_size=12.5,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        )

        is_open_val = bool((existing_space or {}).get("is_open", False))
        access_state = {"is_open": is_open_val}

        def _update_access_ui():
            is_op = access_state["is_open"]
            access_card.border = ft.Border.all(
                1.5,
                theme_color if not is_op else ft.Colors.with_opacity(0.3, theme_color),
            )
            access_icon.name = ft.Icons.PUBLIC_ROUNDED if is_op else ft.Icons.LOCK_ROUNDED
            access_icon.color = theme_color if is_op else ft.Colors.SECONDARY
            access_title.value = "Open Access (Discoverable)" if is_op else "Invite Only (Code Required)"
            access_sub.value = (
                "Anyone in the organization can discover and join this space."
                if is_op
                else "Learners must enter the secret invite code to unlock and join."
            )
            access_switch.value = is_op
            page.update()

        access_icon = ft.Icon(
            ft.Icons.PUBLIC_ROUNDED if is_open_val else ft.Icons.LOCK_ROUNDED,
            color=theme_color if is_open_val else ft.Colors.SECONDARY,
            size=20,
        )
        access_title = ft.Text(
            "Open Access (Discoverable)" if is_open_val else "Invite Only (Code Required)",
            weight=ft.FontWeight.BOLD,
            size=12.5,
        )
        access_sub = ft.Text(
            "Anyone in the organization can discover and join this space."
            if is_open_val
            else "Learners must enter the secret invite code to unlock and join.",
            size=11,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        access_switch = ft.Switch(
            value=is_open_val,
            active_color=theme_color,
            scale=0.85,
        )

        def _toggle_access(ev):
            access_state["is_open"] = bool(access_switch.value)
            _update_access_ui()

        access_switch.on_change = _toggle_access

        access_card = ft.Container(
            padding=ft.Padding.all(12),
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
            content=ft.Row(
                [
                    ft.Row(
                        [
                            ft.Container(
                                width=34,
                                height=34,
                                border_radius=8,
                                bgcolor=ft.Colors.with_opacity(0.1, theme_color),
                                alignment=ft.Alignment.CENTER,
                                content=access_icon,
                            ),
                            ft.Column([access_title, access_sub], spacing=2, expand=True),
                        ],
                        spacing=10,
                        expand=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    access_switch,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

        existing_course_ids = {
            str(c.get("id")) for c in ((existing_space or {}).get("courses") or []) if c.get("id")
        }
        selected_cids = set(existing_course_ids)
        course_checks = []

        counter_pill = ft.Text(
            f"{len(selected_cids)} linked",
            size=11,
            weight=ft.FontWeight.W_600,
            color=theme_color,
        )

        def _update_counter():
            counter_pill.value = f"{len(selected_cids)} linked"
            page.update()

        if org_courses:
            for c in org_courses:
                cid = str(c.get("id"))
                ctitle = c.get("name") or c.get("title", "Course")

                def _toggle(ev, target_cid=cid):
                    if ev.control.value:
                        selected_cids.add(target_cid)
                    else:
                        selected_cids.discard(target_cid)
                    _update_counter()

                course_checks.append(
                    ft.Checkbox(
                        label=ctitle,
                        value=(cid in selected_cids),
                        on_change=_toggle,
                        active_color=theme_color,
                    )
                )

        btn_save = ft.ElevatedButton(
            "Save Changes" if is_edit else "Create Space",
            icon=ft.Icons.CHECK_ROUNDED,
            style=ft.ButtonStyle(
                bgcolor=theme_color,
                color=ft.Colors.ON_PRIMARY,
                shape=ft.RoundedRectangleBorder(radius=10),
            ),
        )

        async def _do_save(ev):
            name_val = name_tf.value.strip() if name_tf.value else ""
            if not name_val:
                show_page_snackbar(page, "Please enter a name for the Course Space.")
                return

            btn_save.disabled = True
            btn_save.content = ft.ProgressRing(width=16, height=16, stroke_width=2, color=ft.Colors.ON_PRIMARY)
            page.update()

            if is_edit:
                sp_id = str(existing_space.get("id"))
                res = await update_course_space(
                    token=token,
                    space_id=sp_id,
                    payload={
                        "name": name_val,
                        "description": desc_tf.value.strip() if desc_tf.value else "",
                        "is_open": access_state["is_open"],
                    },
                )
                to_add = list(selected_cids - existing_course_ids)
                to_remove = list(existing_course_ids - selected_cids)
                if to_add:
                    await add_courses_to_space(token=token, space_id=sp_id, course_ids=to_add)
                for rem_cid in to_remove:
                    await remove_course_from_space(token=token, space_id=sp_id, course_id=rem_cid)

                if res.get("status") == "success":
                    show_page_snackbar(page, f"Course Space '{name_val}' updated!")
                    _close_dialog(dlg)
                    await _fetch_spaces()
                else:
                    show_page_snackbar(page, res.get("message", "Failed to update space."))
                    btn_save.disabled = False
                    btn_save.content = None
                    btn_save.text = "Save Changes"
                    page.update()
            else:
                payload = {
                    "name": name_val,
                    "description": desc_tf.value.strip() if desc_tf.value else "",
                    "organisation_id": org_id,
                    "is_open": access_state["is_open"],
                    "course_ids": list(selected_cids),
                }
                res = await create_course_space(token=token, payload=payload)
                if res.get("status") == "success":
                    show_page_snackbar(page, f"Course Space '{name_val}' created successfully!")
                    _close_dialog(dlg)
                    await _fetch_spaces()
                else:
                    show_page_snackbar(page, res.get("message", "Failed to create space."))
                    btn_save.disabled = False
                    btn_save.content = None
                    btn_save.text = "Create Space"
                    page.update()

        btn_save.on_click = lambda ev: page.run_task(_do_save, ev)

        list_h = min(116, max(44, len(course_checks) * 36)) if course_checks else 0
        courses_selection_block = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(
                            "Link Organization Courses",
                            weight=ft.FontWeight.BOLD,
                            size=12,
                        ),
                        counter_pill,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Container(
                    content=ft.Column(
                        course_checks,
                        spacing=2,
                        scroll=ft.ScrollMode.AUTO if len(course_checks) > 3 else None,
                    ),
                    height=list_h,
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                    border_radius=8,
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                )
                if course_checks
                else ft.Text(
                    "No organization courses available to link yet.",
                    size=11.5,
                    italic=True,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
            ],
            spacing=4,
            tight=True,
        )

        dlg = ft.AlertDialog(
            shape=ft.RoundedRectangleBorder(radius=16),
            title_padding=ft.Padding.only(left=20, right=20, top=18, bottom=6),
            content_padding=ft.Padding.symmetric(horizontal=20, vertical=8),
            actions_padding=ft.Padding.only(left=20, right=20, top=6, bottom=16),
            title=ft.Row(
                [
                    ft.Row(
                        [
                            ft.Container(
                                width=36,
                                height=36,
                                border_radius=10,
                                bgcolor=ft.Colors.with_opacity(0.12, theme_color),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(
                                    ft.Icons.EDIT_ROUNDED if is_edit else ft.Icons.AUTO_AWESOME_ROUNDED,
                                    color=theme_color,
                                    size=18,
                                ),
                            ),
                            ft.Column(
                                [
                                    ft.Text(
                                        "Edit Course Space" if is_edit else "Create Course Space",
                                        weight=ft.FontWeight.BOLD,
                                        size=16,
                                    ),
                                    ft.Text(
                                        "Cohort hub for syllabus, drills & live classes",
                                        size=11,
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                    ),
                                ],
                                spacing=1,
                            ),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.IconButton(
                        ft.Icons.CLOSE_ROUNDED,
                        icon_size=18,
                        tooltip="Close",
                        on_click=lambda _: _close_dialog(dlg),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            content=ft.Container(
                width=modal_w,
                content=ft.Column(
                    [
                        name_tf,
                        desc_tf,
                        access_card,
                        courses_selection_block,
                    ],
                    spacing=12,
                    tight=True,
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: _close_dialog(dlg)),
                btn_save,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    # ── 3. Join with Code Modal (Decluttered) ─────────────────────────────────
    def _open_join_modal(e=None):
        sw = _screen_w()
        modal_w = min(420, max(280, int(sw * 0.88)))

        code_tf = ft.TextField(
            label="Space Invite Code",
            hint_text="e.g. SPACE-8X9L2K",
            capitalization=ft.TextCapitalization.CHARACTERS,
            dense=True,
            autofocus=True,
            prefix_icon=ft.Icons.VPN_KEY_ROUNDED,
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
            focused_border_color=theme_color,
            text_size=13,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=11),
        )
        btn_join = ft.ElevatedButton(
            "Join Space",
            icon=ft.Icons.LOGIN_ROUNDED,
            style=ft.ButtonStyle(
                bgcolor=theme_color,
                color=ft.Colors.ON_PRIMARY,
                shape=ft.RoundedRectangleBorder(radius=10),
            ),
        )

        async def _do_join(ev):
            code_val = code_tf.value.strip().upper() if code_tf.value else ""
            if not code_val:
                show_page_snackbar(page, "Please enter an invite code.")
                return

            btn_join.disabled = True
            btn_join.content = ft.ProgressRing(width=16, height=16, stroke_width=2, color=ft.Colors.ON_PRIMARY)
            page.update()

            res = await join_course_space(token=token, code=code_val)
            if res.get("status") == "success":
                show_page_snackbar(page, "Enrolled in Course Space successfully!")
                _close_dialog(join_dlg)
                sp_id = res.get("space_id") or (res.get("space") or {}).get("id")
                if sp_id:
                    page.go(f"/spaces/{sp_id}")
                else:
                    await _fetch_spaces()
            else:
                show_page_snackbar(page, res.get("message", "Failed to join space."))
                btn_join.disabled = False
                btn_join.content = None
                btn_join.text = "Join Space"
                page.update()

        btn_join.on_click = lambda ev: page.run_task(_do_join, ev)
        code_tf.on_submit = lambda ev: page.run_task(_do_join, ev)

        join_dlg = ft.AlertDialog(
            shape=ft.RoundedRectangleBorder(radius=16),
            title_padding=ft.Padding.only(left=20, right=20, top=18, bottom=6),
            content_padding=ft.Padding.symmetric(horizontal=20, vertical=8),
            actions_padding=ft.Padding.only(left=20, right=20, top=6, bottom=16),
            title=ft.Row(
                [
                    ft.Row(
                        [
                            ft.Container(
                                width=36,
                                height=36,
                                border_radius=10,
                                bgcolor=ft.Colors.with_opacity(0.12, theme_color),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.VPN_KEY_ROUNDED, color=theme_color, size=18),
                            ),
                            ft.Column(
                                [
                                    ft.Text("Join Course Space", weight=ft.FontWeight.BOLD, size=16),
                                    ft.Text("Enter secret cohort invite code", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                                spacing=1,
                            ),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.IconButton(
                        ft.Icons.CLOSE_ROUNDED,
                        icon_size=18,
                        tooltip="Close",
                        on_click=lambda _: _close_dialog(join_dlg),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            content=ft.Container(
                width=modal_w,
                content=ft.Column(
                    [
                        ft.Text(
                            "Enter the invite code shared by the course instructor to gain access to materials, live sessions, and topic drills.",
                            size=12.5,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        code_tf,
                    ],
                    spacing=14,
                    tight=True,
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: _close_dialog(join_dlg)),
                btn_join,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        btn_join.on_click = lambda ev: page.run_task(_do_join, ev)
        code_tf.on_submit = lambda ev: page.run_task(_do_join, ev)

        page.overlay.append(join_dlg)
        join_dlg.open = True
        page.update()

    # ── 3b. Invite Members Modal ──────────────────────────────────────────────
    def _open_invite_modal(sp: dict):
        sw = _screen_w()
        modal_w = min(480, max(280, int(sw * 0.90)))
        sid = str(sp.get("id", ""))
        code_str = str(sp.get("code") or "")
        sname = str(sp.get("name") or "Course Space")

        ident_tf = ft.TextField(
            label="Learner Email or Username *",
            hint_text="e.g. learner@example.com or @username",
            dense=True,
            border_radius=10,
            text_size=13,
            border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
            focused_border_color=theme_color,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=11),
        )

        role_dropdown = apply_dropdown_theme(
            ft.Dropdown(
                label="Cohort Role",
                dense=True,
                options=[
                    ft.dropdown.Option("student", "Student / Cohort Learner"),
                    ft.dropdown.Option("tutor", "Co-Tutor / Assistant"),
                ],
                value="student",
                width=170,
            )
        )

        btn_send = ft.ElevatedButton(
            "Enroll & Send Invite",
            icon=ft.Icons.SEND_ROUNDED,
            style=ft.ButtonStyle(
                bgcolor=theme_color,
                color=ft.Colors.ON_PRIMARY,
                shape=ft.RoundedRectangleBorder(radius=10),
            ),
        )

        dlg = None

        async def _do_send_invite(ev):
            val = (ident_tf.value or "").strip()
            if not val:
                show_page_snackbar(page, "Please enter an email or username.")
                return

            btn_send.disabled = True
            btn_send.content = ft.ProgressRing(width=16, height=16, stroke_width=2, color=ft.Colors.ON_PRIMARY)
            page.update()

            res = await invite_space_members(
                token=token,
                space_id=sid,
                user_identifiers=[val],
                role=role_dropdown.value or "student"
            )

            if res.get("status") == "success" and res.get("added_count", 0) > 0:
                show_page_snackbar(page, f"Enrolled {val} and delivered in-app notification!")
                _close_dialog(dlg)
                await _fetch_spaces()
            elif res.get("already_members"):
                show_page_snackbar(page, f"{val} is already a member of this space.")
                btn_send.disabled = False
                btn_send.content = None
                btn_send.text = "Enroll & Send Invite"
                page.update()
            elif res.get("not_found"):
                show_page_snackbar(page, f"User '{val}' not found. Verify email or username.")
                btn_send.disabled = False
                btn_send.content = None
                btn_send.text = "Enroll & Send Invite"
                page.update()
            else:
                show_page_snackbar(page, res.get("message", "Could not send invitation."))
                btn_send.disabled = False
                btn_send.content = None
                btn_send.text = "Enroll & Send Invite"
                page.update()

        btn_send.on_click = lambda ev: page.run_task(_do_send_invite, ev)
        ident_tf.on_submit = lambda ev: page.run_task(_do_send_invite, ev)

        code_card = ft.Container(
            padding=ft.Padding.all(12),
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.06, theme_color),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.18, theme_color)),
            content=ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text("Space Invite Code", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(code_str, size=15, weight=ft.FontWeight.BOLD, color=theme_color),
                        ],
                        spacing=1,
                    ),
                    ft.ElevatedButton(
                        "Copy Code",
                        icon=ft.Icons.COPY_ALL_ROUNDED,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                        on_click=lambda ev: page.run_task(safe_set_clipboard, page, code_str),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

        dlg = ft.AlertDialog(
            shape=ft.RoundedRectangleBorder(radius=16),
            title_padding=ft.Padding.only(left=20, right=20, top=18, bottom=6),
            content_padding=ft.Padding.symmetric(horizontal=20, vertical=8),
            actions_padding=ft.Padding.only(left=20, right=20, top=6, bottom=16),
            title=ft.Row(
                [
                    ft.Row(
                        [
                            ft.Container(
                                width=36,
                                height=36,
                                border_radius=10,
                                bgcolor=ft.Colors.with_opacity(0.12, theme_color),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.PERSON_ADD_ROUNDED, color=theme_color, size=18),
                            ),
                            ft.Column(
                                [
                                    ft.Text("Invite Learners", weight=ft.FontWeight.BOLD, size=16),
                                    ft.Text(sname, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                                spacing=1,
                            ),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.IconButton(
                        ft.Icons.CLOSE_ROUNDED,
                        icon_size=18,
                        tooltip="Close",
                        on_click=lambda _: _close_dialog(dlg),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            content=ft.Container(
                width=modal_w,
                content=ft.Column(
                    [
                        code_card,
                        ft.Text(
                            "Directly enroll registered learners by email or username, or share the invite code above:",
                            size=12,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ident_tf,
                        role_dropdown,
                    ],
                    spacing=14,
                    tight=True,
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: _close_dialog(dlg)),
                btn_send,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    # ── 4. Space Card Builder ─────────────────────────────────────────────────
    def _build_space_card(sp: dict) -> ft.Container:
        sp_id = str(sp.get("id", ""))
        name = sp.get("name", "Untitled Space")
        desc = sp.get("description", "Asynchronous Course Hub & Resource Vault")
        code = sp.get("code", "")
        is_open = bool(sp.get("is_open", False))
        m_count = sp.get("material_count", 0)
        q_count = sp.get("quiz_count", 0)
        s_count = sp.get("upcoming_session_count", 0)
        mem_count = sp.get("member_count", 0)
        courses_list = sp.get("courses", [])
        c_count = len(courses_list) if courses_list else sp.get("course_count", 0)
        can_manage = bool(is_admin or sp.get("can_manage") or sp.get("is_creator"))
        is_enrolled = bool(sp.get("is_enrolled") or can_manage)

        async def _copy_code_click(ev, scode=code):
            if scode:
                await safe_set_clipboard(page, scode)
                show_page_snackbar(page, f"Space Code '{scode}' copied to clipboard!")

        async def _regen_code(ev, sid=sp_id):
            res = await regenerate_space_code(token=token, space_id=sid)
            if res.get("status") == "success":
                new_c = res.get("code", "")
                show_page_snackbar(page, f"New invite code generated: {new_c}")
                await _fetch_spaces()
            else:
                show_page_snackbar(page, res.get("message", "Could not regenerate code."))

        async def _delete_space(ev, sid=sp_id, sname=name):
            res = await delete_course_space(token=token, space_id=sid)
            if res.get("status") == "success":
                show_page_snackbar(page, f"Space '{sname}' deleted.")
                await _fetch_spaces()
            else:
                show_page_snackbar(page, res.get("message", "Could not delete space."))

        code_chip = ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            border_radius=8,
            bgcolor=ft.Colors.with_opacity(0.1, theme_color),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.25, theme_color)),
            tooltip="Click to copy invite code",
            on_click=lambda ev, sc=code: page.run_task(_copy_code_click, ev, sc),
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.COPY_ALL_ROUNDED, size=13, color=theme_color),
                    ft.Text(code, size=11.5, weight=ft.FontWeight.BOLD, color=theme_color),
                ],
                spacing=4,
                tight=True,
            ),
        ) if (code and (is_enrolled or can_manage or is_open)) else ft.Text(
            f"📅 {s_count} live class{'es' if s_count != 1 else ''}" if s_count > 0 else "Invite code required",
            size=11.5,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )

        badge_pill = ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            border_radius=6,
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY if is_open else ft.Colors.SECONDARY),
            content=ft.Text(
                "OPEN ACCESS" if is_open else "INVITE ONLY",
                size=10,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.PRIMARY if is_open else ft.Colors.SECONDARY,
            ),
        )

        target_base = f"/spaces/{sp_id}/manage" if can_manage else f"/spaces/{sp_id}"

        admin_menu = None
        if can_manage:
            admin_menu = ft.PopupMenuButton(
                icon=ft.Icons.MORE_VERT_ROUNDED,
                icon_size=18,
                tooltip="Manage Space & Sub-Hubs",
                items=[
                    ft.PopupMenuItem(
                        icon=ft.Icons.PERSON_ADD_ROUNDED,
                        content="Invite Learners",
                        on_click=lambda ev, s=sp: _open_invite_modal(s),
                    ),
                    ft.PopupMenuItem(
                        icon=ft.Icons.CLOUD_UPLOAD_ROUNDED,
                        content="Upload / Manage Materials",
                        on_click=lambda ev, tb=target_base: page.go(f"{tb}?tab=materials"),
                    ),
                    ft.PopupMenuItem(
                        icon=ft.Icons.AUTO_AWESOME_ROUNDED,
                        content="Create / Manage CBT Drills",
                        on_click=lambda ev, tb=target_base: page.go(f"{tb}?tab=drills"),
                    ),
                    ft.PopupMenuItem(
                        icon=ft.Icons.VIDEO_CALL_ROUNDED,
                        content="Schedule Live Classes",
                        on_click=lambda ev, tb=target_base: page.go(f"{tb}?tab=sessions"),
                    ),
                    ft.PopupMenuItem(
                        icon=ft.Icons.PEOPLE_ALT_ROUNDED,
                        content="Manage Members & Co-Tutors",
                        on_click=lambda ev, tb=target_base: page.go(f"{tb}?tab=members"),
                    ),
                    ft.PopupMenuItem(
                        icon=ft.Icons.EDIT_ROUNDED,
                        content="Edit Space & Courses",
                        on_click=lambda ev, s=sp: _open_create_modal(existing_space=s),
                    ),
                    ft.PopupMenuItem(
                        icon=ft.Icons.REFRESH_ROUNDED,
                        content="Regenerate Invite Code",
                        on_click=lambda ev, sid=sp_id: page.run_task(_regen_code, ev, sid),
                    ),
                    ft.PopupMenuItem(
                        icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                        content="Delete Space",
                        on_click=lambda ev, sid=sp_id, sn=name: page.run_task(_delete_space, ev, sid, sn),
                    ),
                ],
            )

        primary_btn = ft.ElevatedButton(
            "Configure Space" if can_manage else ("Open Space" if is_enrolled else ("Join & Enter" if is_open else "Unlock with Code")),
            icon=ft.Icons.TUNE_ROUNDED if can_manage else (ft.Icons.ARROW_FORWARD_ROUNDED if is_enrolled else (ft.Icons.LOGIN_ROUNDED if is_open else ft.Icons.VPN_KEY_ROUNDED)),
            style=ft.ButtonStyle(
                bgcolor=theme_color,
                color=ft.Colors.ON_PRIMARY,
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
        )

        async def _on_primary_click(ev):
            if can_manage or is_enrolled:
                page.go(target_base)
                return
            if not is_open:
                _open_join_modal()
                return

            primary_btn.disabled = True
            primary_btn.content = ft.ProgressRing(width=16, height=16, stroke_width=2, color=ft.Colors.ON_PRIMARY)
            page.update()

            j_res = await join_course_space(token=token, space_id=sp_id)
            if j_res.get("status") == "success":
                show_page_snackbar(page, f"Joined {name}!")
                page.go(target_base)
            else:
                show_page_snackbar(page, j_res.get("message", "Could not join space."))
                primary_btn.disabled = False
                primary_btn.content = None
                primary_btn.text = "Join & Enter"
                page.update()

        primary_btn.on_click = lambda ev: page.run_task(_on_primary_click, ev)

        course_pills = []
        for c_item in courses_list[:2]:
            c_title = c_item.get("title", "Course")
            course_pills.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=6,
                    bgcolor=ft.Colors.with_opacity(0.08, theme_color),
                    content=ft.Text(
                        c_title,
                        size=10.5,
                        weight=ft.FontWeight.W_600,
                        color=theme_color,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                )
            )
        if len(courses_list) > 2:
            course_pills.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=7, vertical=3),
                    border_radius=6,
                    bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                    content=ft.Text(f"+{len(courses_list) - 2} more", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                )
            )

        card_children = [
            ft.Row(
                [
                    ft.Row(
                        [
                            ft.Container(
                                width=40,
                                height=40,
                                border_radius=10,
                                bgcolor=ft.Colors.with_opacity(0.12, theme_color),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.CLASS_OUTLINED, color=theme_color, size=20),
                            ),
                            ft.Column(
                                [
                                    ft.Text(name, size=15, weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                    ft.Text(f"{mem_count} Members • By {sp.get('creator_name', 'Instructor')}", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                        ],
                        spacing=10,
                        expand=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        [
                            badge_pill,
                            *([admin_menu] if admin_menu else []),
                        ],
                        spacing=4,
                        tight=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Text(
                desc or "No description provided.",
                size=12,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
        ]

        if course_pills:
            card_children.append(ft.Row(course_pills, spacing=6, wrap=True))

        is_mob = _screen_w() < 600

        invite_btn = ft.OutlinedButton(
            "Invite",
            icon=ft.Icons.PERSON_ADD_ROUNDED,
            style=ft.ButtonStyle(
                color=theme_color,
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            ),
            on_click=lambda ev, s=sp: _open_invite_modal(s),
        )

        if can_manage:
            primary_btn.expand = True
            footer_row = ft.Column(
                [
                    ft.Row(
                        [
                            code_chip,
                            invite_btn,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row([primary_btn]),
                ],
                spacing=8,
            )
        elif is_mob:
            primary_btn.expand = True
            footer_row = ft.Column(
                [
                    ft.Row([code_chip], alignment=ft.MainAxisAlignment.START),
                    ft.Row([primary_btn]),
                ],
                spacing=8,
            )
        else:
            primary_btn.expand = False
            footer_row = ft.Row(
                [
                    code_chip,
                    primary_btn,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

        card_children.extend(
            [
                ft.Divider(height=1),
                ft.Row(
                    [
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                            border_radius=6,
                            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                            ink=is_enrolled,
                            tooltip="Manage Linked Courses" if can_manage else ("Open Linked Courses" if is_enrolled else None),
                            on_click=(lambda ev, tb=target_base: page.go(f"{tb}?tab=courses")) if is_enrolled else None,
                            content=ft.Text(f"📚 {c_count} Courses", size=11, weight=ft.FontWeight.W_600),
                        ),
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                            border_radius=6,
                            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                            ink=is_enrolled,
                            tooltip="Manage Materials Vault" if can_manage else ("Open Materials Vault" if is_enrolled else None),
                            on_click=(lambda ev, tb=target_base: page.go(f"{tb}?tab=materials")) if is_enrolled else None,
                            content=ft.Text(f"📁 {m_count} Resources", size=11, weight=ft.FontWeight.W_600),
                        ),
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                            border_radius=6,
                            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                            ink=is_enrolled,
                            tooltip="Manage CBT Drills & Exams" if can_manage else ("Open CBT Drills & Exams" if is_enrolled else None),
                            on_click=(lambda ev, tb=target_base: page.go(f"{tb}?tab=drills")) if is_enrolled else None,
                            content=ft.Text(f"⚡ {q_count} CBT Drills", size=11, weight=ft.FontWeight.W_600),
                        ),
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                            border_radius=6,
                            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                            ink=is_enrolled,
                            tooltip="Schedule Live Classes" if can_manage else ("Open Live Classes & Meetings" if is_enrolled else None),
                            on_click=(lambda ev, tb=target_base: page.go(f"{tb}?tab=sessions")) if is_enrolled else None,
                            content=ft.Text(f"🎥 {s_count} Live", size=11, weight=ft.FontWeight.W_600),
                        ),
                    ],
                    spacing=6,
                    wrap=True,
                ),
                footer_row,
            ]
        )

        card = ft.Container(
            padding=16,
            border_radius=14,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            content=ft.Column(card_children, spacing=11),
        )
        card.col = {"xs": 12, "sm": 12, "md": 6, "lg": 4}
        return card

    # ── 5. Main View Render ───────────────────────────────────────────────────
    search_tf = ft.TextField(
        hint_text="Search organization spaces by name, course, or code...",
        prefix_icon=ft.Icons.SEARCH_ROUNDED,
        dense=True,
        border_radius=10,
        text_size=13,
        expand=True,
    )

    def _on_search(ev):
        state["search"] = (ev.control.value or "").strip()
        _render()
        page.update()

    search_tf.on_change = _on_search

    def _set_filter(f_val: str):
        state["filter"] = f_val
        _render()
        page.update()

    def _render():
        content_holder.controls.clear()
        cur_w = _screen_w()
        is_mob = cur_w < 768

        title_col = ft.Column(
            [
                ft.Text("Course Spaces & Async Hubs", size=20, weight=ft.FontWeight.BOLD),
                ft.Text(
                    "Asynchronous study hubs where faculty drop lecture materials, AI CBT drills, and live classes.",
                    size=13,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
            ],
            spacing=2,
        )

        btn_controls = [
            ft.OutlinedButton(
                "Join with Code",
                icon=ft.Icons.VPN_KEY_ROUNDED,
                on_click=_open_join_modal,
            ),
        ]
        if is_admin:
            btn_controls.append(
                ft.ElevatedButton(
                    "+ Create Space",
                    icon=ft.Icons.ADD_ROUNDED,
                    style=ft.ButtonStyle(bgcolor=theme_color, color=ft.Colors.ON_PRIMARY),
                    on_click=lambda ev: _open_create_modal(),
                )
            )

        buttons_row = ft.Row(btn_controls, spacing=8, tight=True, wrap=True)

        if is_mob:
            header_bar = ft.Column([title_col, buttons_row], spacing=10)
        else:
            header_bar = ft.Row(
                [title_col, buttons_row],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

        content_holder.controls.append(header_bar)

        # Search & Filter Chips Bar
        filter_row = ft.Row(
            [
                ft.Chip(
                    label=ft.Text("All Spaces", size=12),
                    selected=state["filter"] == "ALL",
                    on_select=lambda _: _set_filter("ALL"),
                ),
                ft.Chip(
                    label=ft.Text("Open Access", size=12),
                    selected=state["filter"] == "OPEN",
                    on_select=lambda _: _set_filter("OPEN"),
                ),
                ft.Chip(
                    label=ft.Text("Invite Only", size=12),
                    selected=state["filter"] == "PRIVATE",
                    on_select=lambda _: _set_filter("PRIVATE"),
                ),
            ],
            spacing=6,
            wrap=True,
        )

        if is_mob:
            content_holder.controls.append(ft.Column([ft.Row([search_tf]), filter_row], spacing=8))
        else:
            content_holder.controls.append(
                ft.Row([search_tf, filter_row], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER)
            )

        if state["loading"]:
            from src.components.shimmer_skeletons import build_course_spaces_skeleton
            content_holder.controls.append(build_course_spaces_skeleton(page))
            return

        raw_spaces = state["spaces"]
        q_low = (state["search"] or "").strip().lower()
        f_mode = state["filter"]

        filtered_spaces = []
        for sp in raw_spaces:
            if f_mode == "OPEN" and not sp.get("is_open"):
                continue
            if f_mode == "PRIVATE" and sp.get("is_open"):
                continue
            if q_low:
                haystack = " ".join([
                    str(sp.get("name") or ""),
                    str(sp.get("description") or ""),
                    str(sp.get("code") or ""),
                    " ".join(str(c.get("title") or "") for c in (sp.get("courses") or [])),
                ]).lower()
                if q_low not in haystack:
                    continue
            filtered_spaces.append(sp)

        if not filtered_spaces:
            has_filters = bool(q_low or f_mode != "ALL")
            zero_w = min(520, max(240, int(cur_w * 0.85)))

            zero_actions = [
                ft.OutlinedButton(
                    "Clear Filters" if has_filters else "Join with Invite Code",
                    icon=ft.Icons.FILTER_ALT_OFF_ROUNDED if has_filters else ft.Icons.VPN_KEY_ROUNDED,
                    on_click=(
                        (lambda _: (
                            setattr(search_tf, "value", ""),
                            state.update({"search": "", "filter": "ALL"}),
                            _render(),
                            page.update(),
                        ))
                        if has_filters
                        else _open_join_modal
                    ),
                )
            ]
            if is_admin and not has_filters:
                zero_actions.insert(
                    0,
                    ft.ElevatedButton(
                        "+ Create Your First Course Space",
                        icon=ft.Icons.ADD_ROUNDED,
                        style=ft.ButtonStyle(bgcolor=theme_color, color=ft.Colors.ON_PRIMARY),
                        on_click=lambda ev: _open_create_modal(),
                    ),
                )

            zero_state = ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=36 if is_mob else 50,
                border_radius=14,
                bgcolor=ft.Colors.SURFACE,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                content=ft.Column(
                    [
                        ft.Container(
                            width=64,
                            height=64,
                            border_radius=32,
                            bgcolor=ft.Colors.with_opacity(0.12, theme_color),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(ft.Icons.HUB_ROUNDED, size=32, color=theme_color),
                        ),
                        ft.Text(
                            "No Matching Spaces Found" if has_filters else "No Course Spaces Created Yet",
                            weight=ft.FontWeight.BOLD,
                            size=18,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Container(
                            width=zero_w,
                            content=ft.Text(
                                "No spaces matched your current search or access filter."
                                if has_filters
                                else "Create interactive study spaces to share lecture notes, practice drills, and live sessions with your cohorts.",
                                size=13,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ),
                        (
                            ft.Column(
                                zero_actions,
                                spacing=10,
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            )
                            if is_mob
                            else ft.Row(
                                zero_actions,
                                spacing=12,
                                alignment=ft.MainAxisAlignment.CENTER,
                            )
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=14,
                ),
            )
            content_holder.controls.append(zero_state)
            return

        cards_row = ft.ResponsiveRow(spacing=16, run_spacing=16)
        for sp in filtered_spaces:
            cards_row.controls.append(_build_space_card(sp))

        content_holder.controls.append(cards_row)

    # Initial fetch
    page.run_task(_fetch_spaces)

    return ft.Column(
        controls=[content_holder],
        spacing=16,
    )
