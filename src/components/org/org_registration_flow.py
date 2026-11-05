import asyncio
import base64
import flet as ft
from src.requests.organisations import create_organisation, get_my_organisation
from src.utils.file_opener import show_page_snackbar


def _input_style() -> dict:
    return {
        "border_color": ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
        "focused_border_color": ft.Colors.PRIMARY,
        "border_radius": 10,
        "dense": True,
        "text_size": 13,
        "label_style": ft.TextStyle(size=12, color=ft.Colors.ON_SURFACE_VARIANT),
        "content_padding": ft.Padding.symmetric(horizontal=14, vertical=10),
    }


def _section_label(text: str) -> ft.Text:
    return ft.Text(
        text,
        size=10.5,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.ON_SURFACE_VARIANT,
    )


def build_promo_view(on_create_click=None) -> ft.Container:
    """
    Renders the zero-state promotional screen for users who do not own an organization.
    """
    return ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        padding=30,
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=0,
            controls=[
                ft.Container(
                    width=100,
                    height=100,
                    bgcolor=ft.Colors.PRIMARY,
                    border_radius=50,
                    alignment=ft.Alignment.CENTER,
                    shadow=ft.BoxShadow(
                        blur_radius=16,
                        color=ft.Colors.with_opacity(0.25, ft.Colors.PRIMARY),
                        offset=ft.Offset(0, 6),
                    ),
                    content=ft.Icon(ft.Icons.BUSINESS_ROUNDED, size=48, color=ft.Colors.WHITE),
                ),
                ft.Container(height=24),
                ft.Text(
                    "Scale Your Teaching",
                    size=24,
                    weight=ft.FontWeight.W_700,
                    color=ft.Colors.ON_SURFACE,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=8),
                ft.Text(
                    "Create a centralised hub to manage your instructors,\npublish courses, and monitor student progress.",
                    size=13,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=28),
                ft.FilledButton(
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        tight=True,
                        spacing=8,
                        controls=[
                            ft.Icon(ft.Icons.ADD_ROUNDED, color=ft.Colors.WHITE, size=18),
                            ft.Text("Create Organisation", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600, size=14),
                        ],
                    ),
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.PRIMARY,
                        shape=ft.RoundedRectangleBorder(radius=12),
                        padding=ft.Padding.symmetric(horizontal=24, vertical=12),
                    ),
                    on_click=lambda _: on_create_click() if on_create_click else None,
                ),
            ],
        ),
    )


def build_create_form_view(
    page: ft.Page,
    token: str,
    on_org_created=None,
    on_back=None,
) -> ft.Container:
    """
    Renders the modern organization onboarding wizard.
    Validates form data, supports logo upload via FilePicker service,
    and returns full organization details upon creation.
    """
    inp_style = _input_style()
    name_input = ft.TextField(label="Organisation Name *", **inp_style)
    email_input = ft.TextField(label="Contact Email *", keyboard_type=ft.KeyboardType.EMAIL, **inp_style)
    number_input = ft.TextField(label="Phone Number *", keyboard_type=ft.KeyboardType.PHONE, **inp_style)
    website_input = ft.TextField(label="Website (Optional)", keyboard_type=ft.KeyboardType.URL, **inp_style)
    address_input = ft.TextField(label="Physical Address *", multiline=True, min_lines=2, max_lines=4, **inp_style)
    error_text = ft.Text("", color=ft.Colors.RED_600, size=12, visible=False, weight=ft.FontWeight.W_500)

    selected_logo_bytes = None
    selected_logo_name = None

    logo_icon = ft.Icon(ft.Icons.CLOUD_UPLOAD_OUTLINED, color=ft.Colors.PRIMARY, size=26)
    logo_text = ft.Text("Upload Logo (Optional)", color=ft.Colors.ON_SURFACE_VARIANT, size=12)

    curated_themes = [
        ft.Colors.PRIMARY,
        ft.Colors.BLUE_600,
        ft.Colors.TEAL_600,
        ft.Colors.GREEN_600,
        ft.Colors.ORANGE_600,
        ft.Colors.PURPLE_600,
        ft.Colors.INDIGO_600,
    ]
    selected_theme_color = curated_themes[0]

    def _select_color(color_val):
        nonlocal selected_theme_color
        selected_theme_color = color_val
        for swatch in color_row.controls:
            swatch.border = (
                ft.Border.all(3, ft.Colors.ON_SURFACE)
                if swatch.data == selected_theme_color
                else None
            )
        page.update()

    color_row = ft.Row(
        spacing=10,
        alignment=ft.MainAxisAlignment.CENTER,
        controls=[
            ft.Container(
                width=32,
                height=32,
                border_radius=16,
                bgcolor=c,
                data=c,
                ink=True,
                on_click=lambda _, val=c: _select_color(val),
                border=ft.Border.all(3, ft.Colors.ON_SURFACE) if c == selected_theme_color else None,
            )
            for c in curated_themes
        ],
    )

    async def _pick_logo(e=None):
        nonlocal selected_logo_bytes, selected_logo_name
        try:
            files = await ft.FilePicker().pick_files(
                allow_multiple=False,
                file_type=ft.FilePickerFileType.IMAGE,
                with_data=True,
            )
            if files and len(files) > 0:
                selected = files[0]
                selected_logo_bytes = selected.bytes
                selected_logo_name = selected.name
                logo_icon.name = ft.Icons.CHECK_CIRCLE_ROUNDED
                logo_icon.color = ft.Colors.GREEN_600
                logo_text.value = f"Selected: {selected_logo_name}"
                logo_text.color = ft.Colors.GREEN_600
                page.update()
        except Exception as ex:
            print(f"[org_registration] file picker error: {ex}")

    async def _handle_submit(e=None):
        nonlocal selected_logo_bytes, selected_logo_name
        n_val = name_input.value.strip() if name_input.value else ""
        em_val = email_input.value.strip() if email_input.value else ""
        num_val = number_input.value.strip() if number_input.value else ""
        addr_val = address_input.value.strip() if address_input.value else ""

        if not all([n_val, em_val, num_val, addr_val]):
            error_text.value = "Please fill in all required fields (*)."
            error_text.visible = True
            page.update()
            return

        error_text.visible = False
        submit_btn.disabled = True
        submit_btn.content = ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            tight=True,
            spacing=8,
            controls=[
                ft.ProgressRing(width=16, height=16, color=ft.Colors.WHITE, stroke_width=2),
                ft.Text("Creating Workspace…", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600, size=13),
            ],
        )
        page.update()

        try:
            logo_b64 = (
                base64.b64encode(selected_logo_bytes).decode("utf-8")
                if selected_logo_bytes else None
            )
            web_val = website_input.value.strip() if website_input.value else ""
            if web_val and not web_val.startswith("http"):
                web_val = f"https://{web_val}"

            payload = {
                "name": n_val,
                "email": em_val,
                "number": num_val,
                "website": web_val or None,
                "address": addr_val,
                "logo_bytes": logo_b64,
                "logo_filename": selected_logo_name,
                "theme_color": selected_theme_color,
            }

            tok = token or await page.shared_preferences.get("auth_token")
            new_org = await asyncio.wait_for(create_organisation(tok, payload), timeout=25)

            if not isinstance(new_org, dict) or not new_org.get("id"):
                err = new_org.get("error") if isinstance(new_org, dict) else "Unknown server error"
                raise ValueError(err or f"Unexpected response: {new_org}")

            # Fetch full org data from /me
            full_data = await asyncio.wait_for(get_my_organisation(tok), timeout=15)
            if not full_data or not isinstance(full_data, dict) or full_data.get("error"):
                full_data = new_org

            if on_org_created:
                await on_org_created(full_data)

        except asyncio.TimeoutError:
            error_text.value = "Request timed out. Please check your network and retry."
            error_text.visible = True
            submit_btn.disabled = False
            submit_btn.content = ft.Text("Create Organisation", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600, size=14)
            page.update()
        except Exception as ex:
            error_text.value = f"Could not create organisation: {ex}"
            error_text.visible = True
            submit_btn.disabled = False
            submit_btn.content = ft.Text("Create Organisation", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600, size=14)
            page.update()

    submit_btn = ft.FilledButton(
        content=ft.Text("Create Organisation", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600, size=14),
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.PRIMARY,
            shape=ft.RoundedRectangleBorder(radius=10),
        ),
        height=46,
        on_click=lambda _: page.run_task(_handle_submit),
    )

    return ft.Container(
        expand=True,
        bgcolor=ft.Colors.SURFACE,
        content=ft.Column(
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[
                # Top header bar
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.IconButton(
                                ft.Icons.ARROW_BACK_ROUNDED,
                                icon_color=ft.Colors.ON_SURFACE,
                                on_click=lambda _: on_back() if on_back else None,
                            ),
                            ft.Text("New Organisation", size=17, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                            ft.Container(width=40),
                        ],
                    ),
                ),
                ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                # Form body
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=20, vertical=16),
                    content=ft.Column(
                        spacing=12,
                        controls=[
                            _section_label("BASIC INFORMATION"),
                            name_input,
                            email_input,
                            number_input,
                            website_input,
                            _section_label("ADDRESS"),
                            address_input,
                            _section_label("WORKSPACE LOGO"),
                            ft.Container(
                                width=float("inf"),
                                padding=ft.Padding.symmetric(vertical=16, horizontal=12),
                                border=ft.Border.all(1, ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE)),
                                border_radius=10,
                                ink=True,
                                on_click=lambda _: page.run_task(_pick_logo),
                                content=ft.Column(
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                    spacing=6,
                                    controls=[logo_icon, logo_text],
                                ),
                            ),
                            _section_label("BRAND ACCENT"),
                            ft.Container(
                                width=float("inf"),
                                padding=ft.Padding.symmetric(vertical=12, horizontal=12),
                                border=ft.Border.all(1, ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE)),
                                border_radius=10,
                                content=ft.Column(
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                    spacing=8,
                                    controls=[
                                        ft.Text("Select a brand color for your academy", size=11.5, color=ft.Colors.ON_SURFACE_VARIANT),
                                        color_row,
                                    ],
                                ),
                            ),
                            error_text,
                            ft.Container(height=4),
                            ft.Row(controls=[ft.Container(expand=True, content=submit_btn)]),
                            ft.Container(height=20),
                        ],
                    ),
                ),
            ],
        ),
    )

