import asyncio
import flet as ft
from src.requests.organisations import update_org_member_role
from src.utils.file_opener import show_page_snackbar


def open_change_role_modal(
    page: ft.Page,
    org_id: str,
    member_data: dict,
    theme_color: str,
    token: str,
    on_role_changed=None,
):
    """
    Renders an executive, responsive Role Switcher Dialog for organization administrators.
    Allows promoting or demoting members between Student, Faculty, and Staff.
    """
    uid = str(member_data.get("id", ""))
    first_name = member_data.get("first_name", "")
    last_name = member_data.get("last_name", "")
    full_name = f"{first_name} {last_name}".strip() or member_data.get("email", "Member")
    initial_role = str(member_data.get("role", "STUDENT")).upper()

    # Map role values
    if initial_role in ("TEACHER", "INSTRUCTOR"):
        selected_role = "TEACHER"
    elif initial_role == "STAFF":
        selected_role = "STAFF"
    else:
        selected_role = "STUDENT"

    roles_definition = [
        {
            "key": "STUDENT",
            "title": "Student / Learner",
            "description": "Enrolls in courses, attends cohorts, takes exams, and tracks personal progress.",
            "icon": ft.Icons.SCHOOL_OUTLINED,
            "badge_color": ft.Colors.ON_SURFACE_VARIANT,
        },
        {
            "key": "TEACHER",
            "title": "Faculty & Instructor",
            "description": "Can create courses, author curricula, inspect student grades, and lead live sessions.",
            "icon": ft.Icons.CAST_FOR_EDUCATION_ROUNDED,
            "badge_color": ft.Colors.AMBER_600,
        },
        {
            "key": "STAFF",
            "title": "Operations & Staff",
            "description": "Can manage invitations, monitor student enrollments, and coordinate schedules.",
            "icon": ft.Icons.BADGE_ROUNDED,
            "badge_color": ft.Colors.BLUE_600,
        },
    ]

    cards_holder = ft.Column(spacing=8)

    def _select_role(role_key: str):
        nonlocal selected_role
        selected_role = role_key
        _render_role_cards()
        page.update()

    def _render_role_cards():
        cards = []
        for r in roles_definition:
            k = r["key"]
            is_active = (selected_role == k)

            card = ft.Container(
                padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                border_radius=12,
                bgcolor=ft.Colors.with_opacity(0.08, theme_color) if is_active else ft.Colors.SURFACE,
                border=ft.Border.all(
                    1.5 if is_active else 1,
                    theme_color if is_active else ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE),
                ),
                ink=True,
                on_click=lambda _, val=k: _select_role(val),
                content=ft.Row(
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            padding=8,
                            border_radius=10,
                            bgcolor=ft.Colors.with_opacity(0.12, r["badge_color"]),
                            content=ft.Icon(r["icon"], size=18, color=r["badge_color"]),
                        ),
                        ft.Column(
                            spacing=2,
                            expand=True,
                            controls=[
                                ft.Text(r["title"], size=13.5, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                                ft.Text(r["description"], size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                            ],
                        ),
                        ft.Icon(
                            ft.Icons.RADIO_BUTTON_CHECKED_ROUNDED if is_active else ft.Icons.RADIO_BUTTON_OFF_ROUNDED,
                            size=18,
                            color=theme_color if is_active else ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ],
                ),
            )
            cards.append(card)
        cards_holder.controls = cards

    _render_role_cards()

    error_label = ft.Text("", color=ft.Colors.RED_600, size=12, visible=False)

    def _close_dialog(e=None):
        role_dlg.open = False
        page.update()

    async def _handle_save(e=None):
        error_label.visible = False
        save_btn.disabled = True
        save_btn.content = ft.Row([
            ft.ProgressRing(width=14, height=14, color=ft.Colors.WHITE, stroke_width=2),
            ft.Text("Updating Role…", size=12, color=ft.Colors.WHITE),
        ], tight=True, spacing=6)
        page.update()

        try:
            auth_tok = token or await page.shared_preferences.get("auth_token")
            res = await asyncio.wait_for(
                update_org_member_role(auth_tok, org_id, uid, selected_role.lower()),
                timeout=15,
            )

            if isinstance(res, dict) and not res.get("error"):
                _close_dialog()
                show_page_snackbar(page, f"Role updated to {selected_role.capitalize()} for {full_name}.")
                if on_role_changed:
                    on_role_changed(uid, selected_role)
            else:
                err = res.get("error", "Failed to update role.") if isinstance(res, dict) else "Error"
                error_label.value = f"Could not update: {err}"
                error_label.visible = True
                save_btn.disabled = False
                save_btn.content = ft.Text("Save Role", color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.BOLD)
                page.update()

        except Exception as ex:
            error_label.value = f"Error: {ex}"
            error_label.visible = True
            save_btn.disabled = False
            save_btn.content = ft.Text("Save Role", color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.BOLD)
            page.update()

    save_btn = ft.FilledButton(
        "Save Role",
        style=ft.ButtonStyle(bgcolor=theme_color, shape=ft.RoundedRectangleBorder(radius=10)),
        on_click=lambda _: page.run_task(_handle_save),
    )
    cancel_btn = ft.TextButton("Cancel", on_click=_close_dialog)

    w_val = getattr(page, "width", None)
    screen_w = int(w_val) if isinstance(w_val, (int, float)) and w_val > 0 else 480
    dialog_w = min(screen_w - 32, 440)

    role_dlg = ft.AlertDialog(
        modal=True,
        bgcolor=ft.Colors.SURFACE,
        shape=ft.RoundedRectangleBorder(radius=16),
        title=ft.Row([
            ft.Container(
                padding=6,
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.12, theme_color),
                content=ft.Icon(ft.Icons.MANAGE_ACCOUNTS_ROUNDED, color=theme_color, size=20),
            ),
            ft.Text(f"Change Role: {full_name}", weight=ft.FontWeight.BOLD, size=15),
        ], spacing=10),
        content=ft.Container(
            width=dialog_w,
            content=ft.Column([
                ft.Text("Select a permission level within this workspace:", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Container(height=4),
                cards_holder,
                error_label,
            ], tight=True, spacing=6),
        ),
        actions=[cancel_btn, save_btn],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    page.overlay.append(role_dlg)
    role_dlg.open = True
    page.update()
