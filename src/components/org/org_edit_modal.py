import asyncio
import base64
import flet as ft
from src.requests.organisations import update_organisation
from src.utils.file_opener import show_page_snackbar


def open_org_edit_modal(
    page: ft.Page,
    org_data: dict,
    theme_color: str,
    token: str,
    on_updated=None,
):
    """
    Renders an executive, responsive modal dialog allowing organization owners
    to update workspace branding, contact information, campus address, and logo.
    """
    org_id = str(org_data.get("id", ""))
    initial_name = org_data.get("name", "")
    initial_phone = org_data.get("number", "")
    initial_website = org_data.get("website", "")
    initial_address = org_data.get("address", "")
    initial_logo = org_data.get("logo")
    initial_theme = org_data.get("theme_color") or theme_color

    inp_style = {
        "border_color": ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
        "focused_border_color": theme_color,
        "border_radius": 10,
        "dense": True,
        "text_size": 13,
        "label_style": ft.TextStyle(size=12, color=ft.Colors.ON_SURFACE_VARIANT),
        "content_padding": ft.Padding.symmetric(horizontal=14, vertical=10),
    }

    name_input = ft.TextField(
        label="Organization Name *",
        value=initial_name,
        prefix_icon=ft.Icons.BUSINESS_ROUNDED,
        **inp_style,
    )
    phone_input = ft.TextField(
        label="Contact Phone *",
        value=initial_phone,
        prefix_icon=ft.Icons.PHONE_ROUNDED,
        keyboard_type=ft.KeyboardType.PHONE,
        **inp_style,
    )
    website_input = ft.TextField(
        label="Official Website (Optional)",
        value=initial_website or "",
        prefix_icon=ft.Icons.LANGUAGE_ROUNDED,
        keyboard_type=ft.KeyboardType.URL,
        **inp_style,
    )
    address_input = ft.TextField(
        label="Campus / Physical Address *",
        value=initial_address,
        prefix_icon=ft.Icons.LOCATION_ON_ROUNDED,
        multiline=True,
        min_lines=2,
        max_lines=3,
        **inp_style,
    )

    error_label = ft.Text("", color=ft.Colors.RED_600, size=12, visible=False, weight=ft.FontWeight.W_500)

    # Brand color swatches
    curated_themes = [
        theme_color,
        ft.Colors.PRIMARY,
        ft.Colors.BLUE_600,
        ft.Colors.TEAL_600,
        ft.Colors.GREEN_600,
        ft.Colors.ORANGE_600,
        ft.Colors.PURPLE_600,
        ft.Colors.INDIGO_600,
    ]
    # Remove duplicates preserving order
    seen_c = set()
    unique_themes = []
    for c in curated_themes:
        if c not in seen_c:
            seen_c.add(c)
            unique_themes.append(c)

    selected_color = initial_theme

    def _select_color(col):
        nonlocal selected_color
        selected_color = col
        for swatch in swatches_row.controls:
            swatch.border = (
                ft.Border.all(3, ft.Colors.ON_SURFACE)
                if swatch.data == selected_color
                else None
            )
        page.update()

    swatches_row = ft.Row(
        spacing=8,
        alignment=ft.MainAxisAlignment.CENTER,
        controls=[
            ft.Container(
                width=30,
                height=30,
                border_radius=15,
                bgcolor=c,
                data=c,
                ink=True,
                on_click=lambda _, v=c: _select_color(v),
                border=ft.Border.all(3, ft.Colors.ON_SURFACE) if c == selected_color else None,
            )
            for c in unique_themes
        ],
    )

    # Logo upload handling
    selected_bytes = None
    selected_name = None

    logo_preview = ft.CircleAvatar(
        radius=28,
        background_image_src=initial_logo if initial_logo else None,
        bgcolor=ft.Colors.with_opacity(0.12, theme_color),
        content=ft.Icon(ft.Icons.BUSINESS_ROUNDED, size=24, color=theme_color) if not initial_logo else None,
    )
    logo_status_text = ft.Text(
        "Upload new logo to replace current brand icon" if initial_logo else "Upload workspace logo (Optional)",
        size=11.5,
        color=ft.Colors.ON_SURFACE_VARIANT,
    )

    async def _pick_logo(ev=None):
        nonlocal selected_bytes, selected_name
        try:
            files = await ft.FilePicker().pick_files(
                allow_multiple=False,
                file_type=ft.FilePickerFileType.IMAGE,
                with_data=True,
            )
            if files and len(files) > 0:
                sel = files[0]
                selected_bytes = sel.bytes
                selected_name = sel.name
                logo_status_text.value = f"Selected: {selected_name}"
                logo_status_text.color = ft.Colors.GREEN_600
                logo_status_text.weight = ft.FontWeight.W_600
                page.update()
        except Exception as ex:
            print(f"[org_edit_modal] pick error: {ex}")

    logo_box = ft.Container(
        padding=ft.Padding.symmetric(horizontal=14, vertical=12),
        border_radius=12,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE)),
        bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
        ink=True,
        on_click=lambda _: page.run_task(_pick_logo),
        content=ft.Row(
            spacing=14,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                logo_preview,
                ft.Column(
                    spacing=3,
                    expand=True,
                    controls=[
                        ft.Row(
                            spacing=6,
                            controls=[
                                ft.Icon(ft.Icons.CLOUD_UPLOAD_OUTLINED, size=16, color=theme_color),
                                ft.Text("Workspace Logo", size=13, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                            ],
                        ),
                        logo_status_text,
                    ],
                ),
                ft.OutlinedButton(
                    "Browse",
                    icon=ft.Icons.FOLDER_OPEN_ROUNDED,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                    on_click=lambda _: page.run_task(_pick_logo),
                ),
            ],
        ),
    )

    def _close_modal(ev=None):
        edit_dialog.open = False
        page.update()

    async def _handle_save(ev=None):
        nonlocal selected_bytes, selected_name
        n_val = name_input.value.strip() if name_input.value else ""
        p_val = phone_input.value.strip() if phone_input.value else ""
        a_val = address_input.value.strip() if address_input.value else ""
        w_val = website_input.value.strip() if website_input.value else ""

        if not n_val or not p_val or not a_val:
            error_label.value = "Organization Name, Phone, and Address are required."
            error_label.visible = True
            page.update()
            return

        error_label.visible = False
        save_btn.disabled = True
        save_btn.content = ft.Row([
            ft.ProgressRing(width=14, height=14, color=ft.Colors.WHITE, stroke_width=2),
            ft.Text("Saving Changes…", color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.W_600),
        ], tight=True, spacing=8)
        page.update()

        try:
            if w_val and not w_val.startswith("http"):
                w_val = f"https://{w_val}"

            logo_b64 = (
                base64.b64encode(selected_bytes).decode("utf-8")
                if selected_bytes else None
            )

            payload = {
                "name": n_val,
                "number": p_val,
                "website": w_val or None,
                "address": a_val,
                "theme_color": selected_color,
                "logo_bytes": logo_b64,
                "logo_filename": selected_name,
            }

            auth_tok = token or await page.shared_preferences.get("auth_token")
            res = await asyncio.wait_for(update_organisation(auth_tok, org_id, payload), timeout=25)

            if isinstance(res, dict) and not res.get("error"):
                _close_modal()
                show_page_snackbar(page, "Workspace details updated successfully!")
                if on_updated:
                    on_updated(res)
            else:
                err_msg = res.get("error", "Failed to update organization.") if isinstance(res, dict) else "Unknown error"
                error_label.value = f"Could not save: {err_msg}"
                error_label.visible = True
                save_btn.disabled = False
                save_btn.content = ft.Text("Save Changes", color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.BOLD)
                page.update()

        except asyncio.TimeoutError:
            error_label.value = "Request timed out. Please check your network and retry."
            error_label.visible = True
            save_btn.disabled = False
            save_btn.content = ft.Text("Save Changes", color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.BOLD)
            page.update()
        except Exception as ex:
            error_label.value = f"Error: {ex}"
            error_label.visible = True
            save_btn.disabled = False
            save_btn.content = ft.Text("Save Changes", color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.BOLD)
            page.update()

    save_btn = ft.FilledButton(
        "Save Changes",
        icon=ft.Icons.CHECK_ROUNDED,
        style=ft.ButtonStyle(
            bgcolor=theme_color,
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=ft.Padding.symmetric(horizontal=16, vertical=10),
        ),
        on_click=lambda _: page.run_task(_handle_save),
    )
    cancel_btn = ft.TextButton("Cancel", on_click=_close_modal)

    w_val = getattr(page, "width", None)
    screen_w = int(w_val) if isinstance(w_val, (int, float)) and w_val > 0 else 540
    dialog_w = min(screen_w - 32, 520)

    edit_dialog = ft.AlertDialog(
        modal=True,
        bgcolor=ft.Colors.SURFACE,
        shape=ft.RoundedRectangleBorder(radius=18),
        title=ft.Row([
            ft.Container(
                padding=6,
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.12, theme_color),
                content=ft.Icon(ft.Icons.EDIT_ROUNDED, color=theme_color, size=18),
            ),
            ft.Text("Edit Workspace Details", weight=ft.FontWeight.BOLD, size=16),
        ], spacing=10),
        content=ft.Container(
            width=dialog_w,
            content=ft.Column([
                name_input,
                phone_input,
                website_input,
                address_input,
                ft.Container(height=2),
                logo_box,
                ft.Container(height=2),
                ft.Column(
                    spacing=6,
                    controls=[
                        ft.Text("Brand Accent Color", size=11.5, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                        swatches_row,
                    ],
                ),
                error_label,
            ], tight=True, spacing=10, scroll=ft.ScrollMode.AUTO),
        ),
        actions=[cancel_btn, save_btn],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    page.overlay.append(edit_dialog)
    edit_dialog.open = True
    page.update()
