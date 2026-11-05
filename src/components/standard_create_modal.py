import asyncio
import base64
from typing import Callable, Optional

import flet as ft
from src.requests.Courses import create_course, get_categories
from src.requests.organisations import get_organisation_members
from src.utils.dropdown_theme import apply_dropdown_theme
from src.utils.file_opener import show_page_snackbar

DEFAULT_ORG_ID = "584b537e-6521-4852-a7e4-18f6c095126d"


def open_standard_create_modal(
    page: ft.Page,
    org_id: Optional[str] = None,
    on_course_created: Optional[Callable[[dict], None]] = None,
):
    """
    Path 1: Standard Sequential Course Creation Precedence.
    Captures all course metadata attributes and writes the course record to the database,
    then automatically navigates the creator into the full-page Curriculum Builder.
    """
    user_data = {}
    if hasattr(page, "session") and hasattr(page.session, "store"):
        user_data = page.session.store.get("current_user") or {}
    elif hasattr(page, "session") and hasattr(page.session, "get"):
        user_data = page.session.get("current_user") or {}

    current_user_id = user_data.get("id") if isinstance(user_data, dict) else None
    current_user_role = user_data.get("role") if isinstance(user_data, dict) else None
    is_freelance = (not org_id) or (current_user_role != "Admin")
    effective_org_id = org_id or DEFAULT_ORG_ID

    w_val = getattr(page, "width", None)
    screen_w = int(w_val) if isinstance(w_val, (int, float)) and w_val > 0 else 800
    modal_w = min(screen_w - 32, 540)

    # --- Form Inputs ---
    name_field = ft.TextField(
        label="Course Title *",
        hint_text="e.g. Distributed Systems Architecture",
        border_radius=10,
        text_size=13,
        border_color=ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE),
        focused_border_color=ft.Colors.PRIMARY,
    )

    desc_field = ft.TextField(
        label="Short Description / Overview",
        hint_text="Summary of topics, learning outcomes, and expectations…",
        multiline=True,
        min_lines=2,
        max_lines=3,
        border_radius=10,
        text_size=13,
        border_color=ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE),
        focused_border_color=ft.Colors.PRIMARY,
    )

    category_dropdown = apply_dropdown_theme(
        ft.Dropdown(
            label="Category *",
            options=[],
            border_radius=10,
            dense=True,
            text_size=13,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        ),
        menu_height=260,
    )

    visibility_dropdown = apply_dropdown_theme(
        ft.Dropdown(
            label="Visibility",
            value="false",
            options=[
                ft.dropdown.Option("false", "Draft (Private to Teachers)"),
                ft.dropdown.Option("organisation", "Organisation Members Only"),
                ft.dropdown.Option("true", "Public Marketplace Catalog"),
            ],
            border_radius=10,
            dense=True,
            text_size=13,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        ),
        menu_height=260,
    )

    teacher_dropdown = apply_dropdown_theme(
        ft.Dropdown(
            label="Assign Lead Instructor",
            options=[],
            border_radius=10,
            dense=True,
            text_size=13,
            visible=not is_freelance,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        ),
        menu_height=260,
    )

    auto_cert_switch = ft.Switch(
        label="Issue Completion Certificate Automatically",
        value=True,
        active_color=ft.Colors.GREEN_600,
    )

    supervised_switch = ft.Switch(
        label="Cohort-Based / Instructor-Led Format",
        value=False,
        active_color=ft.Colors.PRIMARY,
    )

    # --- Objectives Chips ---
    objectives_list = []
    objectives_wrap = ft.Row(wrap=True, spacing=6, run_spacing=6)

    def _render_objectives():
        objectives_wrap.controls.clear()
        for idx, obj in enumerate(objectives_list):
            def _remove(e, target_idx=idx):
                if 0 <= target_idx < len(objectives_list):
                    objectives_list.pop(target_idx)
                    _render_objectives()
                    page.update()

            objectives_wrap.controls.append(
                ft.Chip(
                    label=ft.Text(obj, size=11),
                    delete_icon=ft.Icon(ft.Icons.CLOSE_ROUNDED, size=12),
                    on_delete=_remove,
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                    shape=ft.RoundedRectangleBorder(radius=8),
                )
            )

    def _add_objective(e=None):
        val = (obj_input.value or "").strip()
        if val and val not in objectives_list:
            objectives_list.append(val)
            obj_input.value = ""
            _render_objectives()
            page.update()

    obj_input = ft.TextField(
        label="Type learning objective and press Enter",
        text_size=12,
        border_radius=8,
        content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        border_color=ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE),
        focused_border_color=ft.Colors.PRIMARY,
        on_submit=_add_objective,
        suffix=ft.IconButton(
            ft.Icons.ADD_CIRCLE_OUTLINE_ROUNDED,
            icon_size=18,
            icon_color=ft.Colors.PRIMARY,
            on_click=_add_objective,
        ),
    )

    # --- Custom Cover Image (NO synthetic auto-generation) ---
    selected_image_bytes = None
    selected_image_name = None
    cover_icon = ft.Icon(ft.Icons.ADD_PHOTO_ALTERNATE_OUTLINED, color=ft.Colors.PRIMARY, size=24)
    cover_label = ft.Text("Upload Cover Image (Optional)", size=12, color=ft.Colors.ON_SURFACE_VARIANT)

    async def _pick_cover(e=None):
        nonlocal selected_image_bytes, selected_image_name
        try:
            files = await ft.FilePicker().pick_files(
                allow_multiple=False,
                file_type=ft.FilePickerFileType.IMAGE,
                with_data=True,
            )
            if files and len(files) > 0:
                selected_image_bytes = files[0].bytes
                selected_image_name = files[0].name
                cover_icon.name = ft.Icons.CHECK_CIRCLE_ROUNDED
                cover_icon.color = ft.Colors.GREEN_600
                cover_label.value = f"Selected: {selected_image_name}"
                cover_label.color = ft.Colors.GREEN_700
                page.update()
        except Exception:
            pass

    cover_container = ft.Container(
        padding=12,
        border_radius=10,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE)),
        bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
        ink=True,
        on_click=_pick_cover,
        content=ft.Row([
            cover_icon,
            cover_label,
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
    )

    error_label = ft.Text("", color=ft.Colors.RED_600, size=12, visible=False, weight=ft.FontWeight.W_500)

    def _close_modal(e=None):
        modal.open = False
        page.update()

    async def _submit(e=None):
        name_val = (name_field.value or "").strip()
        cat_val = category_dropdown.value

        if not name_val:
            error_label.value = "Course Title is required."
            error_label.visible = True
            page.update()
            return

        if not cat_val:
            error_label.value = "Please select a Category."
            error_label.visible = True
            page.update()
            return

        error_label.visible = False
        submit_btn.disabled = True
        submit_btn.content = ft.Row([
            ft.ProgressRing(width=14, height=14, color=ft.Colors.WHITE, stroke_width=2),
            ft.Text("Creating Course…", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
        ], tight=True, spacing=6)
        page.update()

        auth_tok = await page.shared_preferences.get("auth_token")
        logo_b64 = base64.b64encode(selected_image_bytes).decode("utf-8") if selected_image_bytes else None

        payload = {
            "name": name_val,
            "description": (desc_field.value or name_val).strip(),
            "category_id": cat_val,
            "objectives": objectives_list,
            "image_bytes": logo_b64,
            "image_filename": selected_image_name,
            "public": visibility_dropdown.value or "false",
            "auto_certificate": auto_cert_switch.value,
            "supervised": supervised_switch.value,
            "is_freelance": is_freelance,
            "teacher_id": current_user_id if is_freelance else (teacher_dropdown.value or None),
            "org_id": effective_org_id,
        }

        try:
            res = await asyncio.wait_for(create_course(auth_tok, payload), timeout=45)
            if isinstance(res, dict) and "id" in res:
                _close_modal()
                show_page_snackbar(page, f"Course '{name_val}' created! Entering Curriculum Builder…")
                if on_course_created:
                    on_course_created(res)
                # Seamless transition straight into the full-page Curriculum Builder!
                try:
                    page.go(f"/courses/{res['id']}/manage")
                except Exception:
                    pass
            else:
                err_msg = res.get("error", "Failed to create course") if isinstance(res, dict) else "Server error"
                error_label.value = f"Could not create course: {err_msg}"
                error_label.visible = True
                submit_btn.disabled = False
                submit_btn.content = ft.Text("Create & Enter Builder", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
                page.update()
        except Exception as ex:
            error_label.value = f"Error creating course: {ex}"
            error_label.visible = True
            submit_btn.disabled = False
            submit_btn.content = ft.Text("Create & Enter Builder", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
            page.update()

    submit_btn = ft.FilledButton(
        content=ft.Text("Create & Enter Builder", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
        style=ft.ButtonStyle(bgcolor=ft.Colors.PRIMARY, shape=ft.RoundedRectangleBorder(radius=10)),
        on_click=lambda _: page.run_task(_submit),
    )

    async def _load_options():
        auth_tok = await page.shared_preferences.get("auth_token")
        try:
            cats = await get_categories(auth_tok)
            if isinstance(cats, list):
                category_dropdown.options = [
                    ft.dropdown.Option(str(c.get("id")), str(c.get("name", "Category")))
                    for c in cats
                ]
                if cats and not category_dropdown.value:
                    category_dropdown.value = str(cats[0].get("id"))
        except Exception:
            pass

        if not is_freelance:
            try:
                mems = await get_organisation_members(auth_tok, effective_org_id)
                if isinstance(mems, list):
                    teacher_dropdown.options = [
                        ft.dropdown.Option(str(m.get("user_id")), f"{m.get('first_name', '')} {m.get('last_name', '')} ({m.get('role', 'Member')})")
                        for m in mems
                    ]
            except Exception:
                pass
        page.update()

    modal = ft.AlertDialog(
        modal=True,
        bgcolor=ft.Colors.SURFACE,
        shape=ft.RoundedRectangleBorder(radius=16),
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row([
                    ft.Icon(ft.Icons.AUTO_STORIES_ROUNDED, color=ft.Colors.PRIMARY, size=22),
                    ft.Text("Create New Course", weight=ft.FontWeight.BOLD, size=16),
                ], spacing=8),
                ft.IconButton(ft.Icons.CLOSE_ROUNDED, icon_size=20, on_click=_close_modal),
            ],
        ),
        content=ft.Container(
            width=modal_w,
            content=ft.Column(
                tight=True,
                spacing=12,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    name_field,
                    desc_field,
                    category_dropdown,
                    visibility_dropdown,
                    ft.Column([
                        ft.Text("Learning Objectives", size=12, weight=ft.FontWeight.W_600),
                        objectives_wrap,
                        obj_input,
                    ], spacing=6),
                    cover_container,
                    ft.Row([auto_cert_switch, supervised_switch], wrap=True, spacing=12),
                    teacher_dropdown,
                    error_label,
                ],
            ),
        ),
        actions=[
            ft.TextButton("Cancel", on_click=_close_modal),
            submit_btn,
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    page.overlay.append(modal)
    modal.open = True
    page.update()
    page.run_task(_load_options)

