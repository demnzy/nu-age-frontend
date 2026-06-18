import asyncio
import base64

import flet as ft
from src.components.bottom_appbar import get_bottom_appbar
from src.requests.organisations import (
    create_organisation,
    get_my_organisation,
    get_organisation_members,
    get_joined_organisations,  
    get_organisation_courses,
)


# ── shared field style ────────────────────────────────────────────────────────
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


async def organisations_view(page: ft.Page):
    app_bar = get_bottom_appbar(page)
    token = await page.shared_preferences.get("auth_token")

    user_data = page.session.store.get("current_user") or {}
    role = user_data.get("role", "STUDENT").upper()

    # ── content socket ────────────────────────────────────────────────────────
    content_socket = ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.ProgressRing(color=ft.Colors.PRIMARY, width=36, height=36),
                ft.Text("Loading…", size=13, color=ft.Colors.GREY_500),
            ],
        ),
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 1. ADMIN DASHBOARD
    # ─────────────────────────────────────────────────────────────────────────
    async def build_dashboard_view(org_data: dict):
        org_name  = org_data.get("name", "My Workspace")
        org_id    = org_data.get("id", "")
        org_email = org_data.get("email", "admin@org.com")
        org_phone = org_data.get("number", "+000 0000 0000")
        theme_color = org_data.get("theme_color") or ft.Colors.PRIMARY

        # Guard: crash early with a clear message rather than sending "" to the server
        if not org_id:
            raise ValueError(
                "build_dashboard_view received org_data with no valid 'id'. "
                f"Keys present: {list(org_data.keys())}"
            )

        stats = {
            "members":  org_data.get("members", 0),
            "courses":  org_data.get("courses", 0),
            "staff":    org_data.get("staff", 0),
            "plan":     org_data.get("plan", {}).get("name", "Free") if org_data.get("plan") else "Free",
            "students": org_data.get("students", 0),
        }

        try:
            members = await asyncio.wait_for(
                get_organisation_members(token, org_id), timeout=15
            )
        except asyncio.TimeoutError:
            members = []
        except Exception as ex:
            print(f"Warning: could not load members: {type(ex).__name__}: {ex}")
            members = []

        try:
            courses = await asyncio.wait_for(
                get_organisation_courses(token, org_id), timeout=15
            )
        except asyncio.TimeoutError:
            courses = []
        except Exception as ex:
            print(f"Warning: could not load courses: {type(ex).__name__}: {ex}")
            courses = []

        # ── stat card ─────────────────────────────────────────────────────────
        def stat_card(icon_name, title, value, bg_color):
            return ft.Container(
                bgcolor=bg_color,
                padding=ft.padding.symmetric(horizontal=16, vertical=14),
                border_radius=14,
                col={"xs": 6, "sm": 2.4},
                shadow=ft.BoxShadow(
                    blur_radius=8,
                    color=ft.Colors.with_opacity(0.12, ft.Colors.BLACK),
                    offset=ft.Offset(0, 3),
                ),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(
                            spacing=2,
                            expand=True,
                            controls=[
                                ft.Text(str(value), size=22, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                                ft.Text(title, size=11, color=ft.Colors.with_opacity(0.85, ft.Colors.WHITE), weight=ft.FontWeight.W_500),
                            ],
                        ),
                        ft.Container(
                            padding=10,
                            bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.WHITE),
                            shape=ft.BoxShape.CIRCLE,
                            content=ft.Icon(icon_name, color=ft.Colors.WHITE, size=22),
                        ),
                    ],
                ),
            )

        # ── member row ────────────────────────────────────────────────────────
        def build_member_row(member: dict):
            member_role = member.get("role", "STUDENT").upper()
            badge_map = {
                "ADMIN":   (ft.Colors.BLUE_50,   ft.Colors.BLUE_800),
                "TEACHER": (ft.Colors.ORANGE_50, ft.Colors.ORANGE_800),
            }
            badge_bg, badge_fg = badge_map.get(member_role, (ft.Colors.GREY_100, ft.Colors.GREY_800))
            initials = f'{member.get("first_name","?")[0]}{member.get("last_name","?")[0]}'.upper()

            return ft.Container(
                padding=ft.padding.symmetric(vertical=8, horizontal=4),
                border_radius=8,
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            expand=True,
                            spacing=10,
                            controls=[
                                ft.CircleAvatar(
                                    content=ft.Text(initials, size=13, weight=ft.FontWeight.W_700),
                                    bgcolor=ft.Colors.PRIMARY_CONTAINER,
                                    color=ft.Colors.ON_PRIMARY_CONTAINER,
                                    radius=19,
                                ),
                                ft.Column(
                                    spacing=1,
                                    controls=[
                                        ft.Text(
                                            f'{member.get("first_name","")} {member.get("last_name","")}',
                                            size=14, weight=ft.FontWeight.W_600,
                                            color=ft.Colors.ON_SURFACE,
                                        ),
                                        ft.Text(member.get("email", ""), size=12, color=ft.Colors.GREY_500),
                                    ],
                                ),
                            ],
                        ),
                        ft.Row(
                            spacing=6,
                            controls=[
                                ft.Container(
                                    padding=ft.padding.symmetric(horizontal=9, vertical=3),
                                    bgcolor=badge_bg,
                                    border_radius=10,
                                    content=ft.Text(member_role, size=9, color=badge_fg, weight=ft.FontWeight.W_700),
                                ),
                                ft.PopupMenuButton(
                                    icon=ft.Icons.MORE_VERT_ROUNDED,
                                    icon_color=ft.Colors.GREY_400,
                                    items=[
                                        ft.PopupMenuItem(content=ft.Text("View Profile", size=13), icon=ft.Icons.PERSON_SEARCH_ROUNDED),
                                        ft.PopupMenuItem(content=ft.Text("Change Role", size=13), icon=ft.Icons.MANAGE_ACCOUNTS_ROUNDED),
                                        ft.PopupMenuItem(content=ft.Text("Remove Member", size=13), icon=ft.Icons.PERSON_REMOVE_OUTLINED),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            )

        # ── course row ────────────────────────────────────────────────────────
        def build_course_row(course: dict):
            title         = course.get("name", "Untitled Course")
            desc          = course.get("description", "No description available.")
            image_url     = course.get("image_url")
            course_id     = course.get("id", "")
            course_status = course.get("public")
            course_students = course.get("total_students", 0)

            def badge(label, bg, fg):
                return ft.Container(
                    padding=ft.padding.symmetric(horizontal=8, vertical=3),
                    bgcolor=bg, border_radius=10,
                    content=ft.Text(label, size=9, color=fg, weight=ft.FontWeight.W_600),
                )

            return ft.Container(
                shadow=ft.BoxShadow(blur_radius=6, color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK), offset=ft.Offset(0, 2)),
                bgcolor=ft.Colors.SURFACE,
                border_radius=12,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                margin=ft.margin.only(bottom=2),
                content=ft.Row(
                    spacing=0,
                    controls=[
                        ft.Container(
                            width=90, height=130,
                            bgcolor=ft.Colors.GREY_100,
                            content=ft.Image(src=image_url or "placeholder.png", fit=ft.BoxFit.COVER),
                        ),
                        ft.Container(
                            expand=True,
                            padding=ft.padding.symmetric(horizontal=12, vertical=10),
                            content=ft.Column(
                                spacing=4,
                                controls=[
                                    ft.Row(
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        controls=[
                                            ft.Text(title, size=14, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
                                            ft.IconButton(
                                                ft.Icons.SETTINGS_OUTLINED,
                                                icon_color=theme_color,
                                                icon_size=18,
                                                on_click=lambda e, oid=org_id, cid=course_id: page.go(f"/organisations/{oid}/courses/{cid}/settings"),
                                            ),
                                        ],
                                    ),
                                    ft.Text(desc, size=12, color=ft.Colors.GREY_500, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                    ft.Container(height=4),
                                    ft.Row(
                                        spacing=6,
                                        controls=[
                                            badge(
                                                "Public" if course_status else "Draft",
                                                ft.Colors.GREEN_50 if course_status else ft.Colors.GREY_100,
                                                ft.Colors.GREEN_700 if course_status else ft.Colors.GREY_700,
                                            ),
                                            badge(f"{course_students} Enrolled", ft.Colors.BLUE_50, ft.Colors.BLUE_700),
                                        ],
                                    ),
                                ],
                            ),
                        ),
                    ],
                ),
            )

        # ── section container ─────────────────────────────────────────────────
        def dashboard_section(title, list_content, manage_route, action_icon=ft.Icons.ADD_ROUNDED):
            list_content.scroll = ft.ScrollMode.AUTO
            return ft.Container(
                col={"xs": 12, "md": 6},
                bgcolor=ft.Colors.SURFACE,
                padding=18,
                border_radius=14,
                border=ft.border.all(1, ft.Colors.GREY_200),
                shadow=ft.BoxShadow(blur_radius=6, color=ft.Colors.with_opacity(0.05, ft.Colors.BLACK), offset=ft.Offset(0, 2)),
                content=ft.Column(
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text(title, size=16, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                                ft.Container(
                                    width=32, height=32,
                                    bgcolor=theme_color,
                                    border_radius=8,
                                    alignment=ft.Alignment.CENTER,
                                    ink=True,
                                    on_click=lambda e, r=manage_route: page.go(r),
                                    content=ft.Icon(action_icon, color=ft.Colors.WHITE, size=18),
                                ),
                            ],
                        ),
                        ft.Divider(height=1, color=ft.Colors.GREY_100),
                        ft.Container(height=300, content=list_content),
                    ],
                ),
            )

        # ── header card ───────────────────────────────────────────────────────
        header_card = ft.Container(
            margin=ft.margin.symmetric(horizontal=16, vertical=10),
            bgcolor=ft.Colors.SURFACE,
            border_radius=16,
            border=ft.border.all(1, ft.Colors.GREY_200),
            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.07, ft.Colors.BLACK), offset=ft.Offset(0, 3)),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=ft.Column(
                spacing=0,
                controls=[
                    # Banner
                    ft.Container(
                        bgcolor=theme_color,
                        border_radius=ft.BorderRadius.only(top_left=16, top_right=16),
                        padding=ft.padding.only(top=6, right=6, bottom=48, left=16),
                        alignment=ft.Alignment.TOP_RIGHT,
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text("Admin Dashboard", size=13, color=ft.Colors.with_opacity(0.85, ft.Colors.WHITE), weight=ft.FontWeight.W_500),
                                ft.Container(
                                    border_radius=8,
                                    bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.WHITE),
                                    content=ft.IconButton(
                                        ft.Icons.SETTINGS_OUTLINED,
                                        icon_color=ft.Colors.WHITE,
                                        icon_size=18,
                                        on_click=lambda _: page.go("/organisations/settings"),
                                    ),
                                ),
                            ],
                        ),
                    ),
                    # Info area
                    ft.Container(
                        padding=ft.padding.only(left=20, right=20, bottom=16),
                        content=ft.Column(
                            spacing=8,
                            controls=[
                                ft.Container(
                                    margin=ft.margin.only(top=-40),
                                    content=ft.CircleAvatar(
                                        radius=42,
                                        bgcolor=ft.Colors.WHITE,
                                        content=ft.CircleAvatar(
                                            radius=38,
                                            bgcolor=ft.Colors.GREY_100,
                                            background_image_src=org_data.get("logo") or "placeholder.png",
                                        ),
                                    ),
                                ),
                                ft.Row(
                                    wrap=True,
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    vertical_alignment=ft.CrossAxisAlignment.START,
                                    controls=[
                                        ft.Column(
                                            spacing=2,
                                            controls=[
                                                ft.Text(org_name, size=19, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                                                ft.Text("Organisation", size=12, color=ft.Colors.GREY_500),
                                            ],
                                        ),
                                        ft.Row(
                                            spacing=20,
                                            wrap=True,
                                            controls=[
                                                ft.Column(spacing=1, controls=[
                                                    ft.Text("Phone", size=10, color=ft.Colors.GREY_400),
                                                    ft.Row(spacing=4, controls=[
                                                        ft.Icon(ft.Icons.PHONE_ROUNDED, size=12, color=theme_color),
                                                        ft.Text(org_phone, size=12, weight=ft.FontWeight.W_500),
                                                    ]),
                                                ]),
                                                ft.Column(spacing=1, controls=[
                                                    ft.Text("Email", size=10, color=ft.Colors.GREY_400),
                                                    ft.Row(spacing=4, controls=[
                                                        ft.Icon(ft.Icons.EMAIL_OUTLINED, size=12, color=theme_color),
                                                        ft.Text(org_email, size=12, weight=ft.FontWeight.W_500),
                                                    ]),
                                                ]),
                                            ],
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ),
                ],
            ),
        )

        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                header_card,
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=16),
                    content=ft.Column(
                        spacing=16,
                        controls=[
                            # Stat cards
                            ft.ResponsiveRow(
                                run_spacing=12,
                                controls=[
                                    stat_card(ft.Icons.GROUPS_ROUNDED,          "Members",  stats["members"],  ft.Colors.ORANGE_400),
                                    stat_card(ft.Icons.LIBRARY_BOOKS_ROUNDED,   "Courses",  stats["courses"],  ft.Colors.INDIGO_400),
                                    stat_card(ft.Icons.BADGE_ROUNDED,           "Staff",    stats["staff"],    ft.Colors.CYAN_500),
                                    stat_card(ft.Icons.SCHOOL_OUTLINED,         "Students", stats["students"], ft.Colors.BLUE_ACCENT_400),
                                    stat_card(ft.Icons.WORKSPACE_PREMIUM_ROUNDED,"Plan",    stats["plan"],     ft.Colors.PURPLE_400),
                                ],
                            ),
                            # Members & Courses side by side
                            ft.ResponsiveRow(
                                run_spacing=16,
                                controls=[
                                    dashboard_section(
                                        title="Members",
                                        list_content=ft.Column(
                                            spacing=4,
                                            controls=[build_member_row(m) for m in members]
                                            if members
                                            else [ft.Text("No members yet.", color=ft.Colors.GREY_400, size=13)],
                                        ),
                                        manage_route=f"organisations/{org_id}/invite-members",
                                    ),
                                    dashboard_section(
                                        title="Courses",
                                        list_content=ft.Column(
                                            spacing=6,
                                            controls=[build_course_row(c) for c in courses]
                                            if courses
                                            else [ft.Text("No courses published yet.", color=ft.Colors.GREY_400, size=13)],
                                        ),
                                        manage_route=f"/organisations/{org_id}/courses",
                                        action_icon=ft.Icons.ADD_ROUNDED,
                                    ),
                                ],
                            ),
                            ft.Container(height=24),
                        ],
                    ),
                ),
            ],
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 2. CREATE FORM
    # ─────────────────────────────────────────────────────────────────────────
    def build_create_form_view():
        name_input    = ft.TextField(label="Organisation Name *",  **_INPUT)
        email_input   = ft.TextField(label="Contact Email *",      keyboard_type=ft.KeyboardType.EMAIL,  **_INPUT)
        number_input  = ft.TextField(label="Phone Number *",       keyboard_type=ft.KeyboardType.PHONE,  **_INPUT)
        website_input = ft.TextField(label="Website (Optional)",   keyboard_type=ft.KeyboardType.URL,    **_INPUT)
        address_input = ft.TextField(label="Physical Address *",   multiline=True, min_lines=2, max_lines=4, **_INPUT)
        error_text    = ft.Text("", color=ft.Colors.RED_700, size=12, visible=False, weight=ft.FontWeight.W_500)

        selected_logo_bytes = None
        selected_logo_name  = None

        logo_icon = ft.Icon(ft.Icons.CLOUD_UPLOAD_OUTLINED, color=ft.Colors.PRIMARY, size=28)
        logo_text = ft.Text("Upload Logo (Optional)", color=ft.Colors.GREY_500, size=13)

        curated_themes = [
            ft.Colors.PRIMARY, ft.Colors.BLUE_500, ft.Colors.TEAL_500,
            ft.Colors.GREEN_500, ft.Colors.ORANGE_500, ft.Colors.RED_500, ft.Colors.PURPLE_500,
        ]
        selected_theme_color = curated_themes[0]

        def handle_color_select(e):
            nonlocal selected_theme_color
            selected_theme_color = e.control.data
            for swatch in color_swatches_row.controls:
                swatch.border = (
                    ft.border.all(3, ft.Colors.ON_SURFACE)
                    if swatch.data == selected_theme_color
                    else None
                )
            page.update()

        color_swatches_row = ft.Row(
            spacing=10,
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=32, height=32, border_radius=16,
                    bgcolor=color, data=color, ink=True,
                    on_click=handle_color_select,
                    border=ft.border.all(3, ft.Colors.ON_SURFACE) if color == selected_theme_color else None,
                )
                for color in curated_themes
            ],
        )

        # ==========================================
# 1. THE SETUP (Put this in your main page setup, NOT inside the button click)
# ==========================================

# This function automatically wakes up when the user finishes picking an image
# Do NOT append anything to page.overlay

        async def handle_logo_pick(e):
            nonlocal selected_logo_bytes, selected_logo_name
            try:
                # 1. Instantiate the Service natively inside the function
                file_picker = ft.FilePicker()
                
                # 2. Await it directly! This pauses execution until the user selects an image.
                # In 0.84.0, this returns a list of FilePickerFile objects directly.
                files = await file_picker.pick_files(
                    allow_multiple=False,
                    file_type=ft.FilePickerFileType.IMAGE,
                    with_data=True, 
                )
                
                # 3. Process the files 
                if files and len(files) > 0:
                    selected = files[0] # Notice it is just files[0], not files.files
                    
                    # Because you used with_data=True, the raw bytes are already here!
                    selected_logo_bytes = selected.bytes 
                    selected_logo_name  = selected.name
                    
                    # Update UI
                    logo_icon.name  = ft.Icons.CHECK_CIRCLE_ROUNDED
                    logo_icon.color = ft.Colors.GREEN_600
                    logo_text.value = f"Selected: {selected_logo_name}"
                    logo_text.color = ft.Colors.GREEN_600
                    page.update()
                    
            except Exception as ex:
                print(f"FilePicker error: {type(ex).__name__}: {ex}")
                logo_text.value = "Could not open file picker. Try again."
                logo_text.color = ft.Colors.RED_700
                page.update()
        async def handle_submit(e):
            nonlocal selected_logo_bytes, selected_logo_name
            if not all([name_input.value, email_input.value, number_input.value, address_input.value]):
                error_text.value   = "Please fill in all required fields (*)."
                error_text.visible = True
                page.update()
                return

            error_text.visible = False
            submit_btn.disabled = True
            submit_btn.content = ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    ft.ProgressRing(width=16, height=16, color=ft.Colors.WHITE, stroke_width=2),
                    ft.Text("Creating…", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600, size=14),
                ],
            )
            page.update()

            try:
                logo_b64 = (
                    base64.b64encode(selected_logo_bytes).decode("utf-8")
                    if selected_logo_bytes else None
                )
                payload = {
                    "name":          name_input.value.strip(),
                    "email":         email_input.value.strip(),
                    "number":        number_input.value.strip(),
                    "website":       f"https://{website_input.value.strip()}" if website_input.value else None,
                    "address":       address_input.value.strip(),
                    "logo_bytes":    logo_b64,
                    "logo_filename": selected_logo_name,
                    "theme_color":   selected_theme_color,
                }

                tok = await page.shared_preferences.get("auth_token")

                # Step 1: Create the org
                new_org = await asyncio.wait_for(
                    create_organisation(tok, payload), timeout=20
                )

                if not isinstance(new_org, dict) or not new_org.get("id"):
                    raise ValueError(f"Unexpected response from server: {new_org}")

                # Step 2: Fetch full org data from /me (includes stats, plan, members, courses)
                full_org_data = await asyncio.wait_for(
                    get_my_organisation(tok), timeout=15
                )

                if not full_org_data:
                    raise ValueError("Organisation created but could not load dashboard data.")

                await show_dashboard(full_org_data)

            except asyncio.TimeoutError:
                error_text.value   = "Request timed out. Please check your connection and try again."
                error_text.visible = True
                submit_btn.disabled = False
                submit_btn.content = ft.Text("Create Organisation", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600, size=14)
                page.update()

            except Exception as ex:
                error_text.value   = f"Something went wrong: {type(ex).__name__}: {str(ex)}"
                error_text.visible = True
                submit_btn.disabled = False
                submit_btn.content = ft.Text("Create Organisation", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600, size=14)
                page.update()

        submit_btn = ft.ElevatedButton(
            content=ft.Text("Create Organisation", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600, size=14),
            bgcolor=ft.Colors.PRIMARY,
            height=48,
            expand=True,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                elevation=0,
            ),
            on_click=handle_submit,
        )

        return ft.Container(
            expand=True,
            bgcolor=ft.Colors.SURFACE,
            content=ft.Column(
                scroll=ft.ScrollMode.AUTO,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[
                    # ── Top bar ───────────────────────────────────────────────
                    ft.Container(
                        padding=ft.padding.symmetric(horizontal=8, vertical=4),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.IconButton(
                                    ft.Icons.ARROW_BACK_ROUNDED,
                                    icon_color=ft.Colors.ON_SURFACE,
                                    on_click=lambda _: show_promo_view(),
                                ),
                                ft.Text("New Organisation", size=18, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                                ft.Container(width=40),
                            ],
                        ),
                    ),
                    ft.Divider(height=1, color=ft.Colors.GREY_100),

                    # ── Form fields ───────────────────────────────────────────
                    ft.Container(
                        padding=ft.padding.symmetric(horizontal=20, vertical=16),
                        content=ft.Column(
                            spacing=14,
                            controls=[
                                _section_label("BASIC INFORMATION"),
                                name_input, email_input, number_input,
                                website_input,

                                _section_label("ADDRESS"),
                                address_input,

                                _section_label("LOGO"),
                                ft.Container(
                                    width=float("inf"),
                                    padding=ft.padding.symmetric(vertical=18, horizontal=12),
                                    border=ft.border.all(1, ft.Colors.GREY_300),
                                    border_radius=10,
                                    ink=True,
                                    on_click=handle_logo_pick,
                                    content=ft.Column(
                                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                        spacing=6,
                                        controls=[logo_icon, logo_text],
                                    ),
                                ),

                                _section_label("BRAND COLOUR"),
                                ft.Container(
                                    width=float("inf"),
                                    padding=ft.padding.symmetric(vertical=14, horizontal=12),
                                    border=ft.border.all(1, ft.Colors.GREY_300),
                                    border_radius=10,
                                    content=ft.Column(
                                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                        spacing=10,
                                        controls=[
                                            ft.Text("Select a colour for your workspace", size=12, color=ft.Colors.GREY_500),
                                            color_swatches_row,
                                        ],
                                    ),
                                ),

                                error_text,
                                ft.Row(controls=[submit_btn]),
                                ft.Container(height=24),
                            ],
                        ),
                    ),
                ],
            ),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 3. PROMO / ZERO STATE
    # ─────────────────────────────────────────────────────────────────────────
    def build_promo_view():
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
                        width=110, height=110,
                        bgcolor=ft.Colors.PRIMARY,
                        border_radius=55,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(ft.Icons.BUSINESS_ROUNDED, size=52, color=ft.Colors.WHITE),
                    ),
                    ft.Container(height=24),
                    ft.Text(
                        "Scale Your Teaching",
                        size=26, weight=ft.FontWeight.W_700,
                        color=ft.Colors.ON_SURFACE,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=10),
                    ft.Text(
                        "Create a centralised hub to manage your instructors,\npublish courses, and monitor student progress.",
                        size=14, color=ft.Colors.GREY_500,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=32),
                    ft.ElevatedButton(
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.CENTER,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.ADD_ROUNDED, color=ft.Colors.WHITE, size=20),
                                ft.Text("Create Organisation", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600, size=15),
                            ],
                        ),
                        bgcolor=ft.Colors.PRIMARY,
                        height=50,
                        width=float("inf"),
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=12),
                            elevation=0,
                        ),
                        on_click=lambda _: show_create_form(),
                    ),
                ],
            ),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 4. TEACHER / INSTRUCTOR VIEW
    # ─────────────────────────────────────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════════════════════════
# SURGICAL DROP-IN REPLACEMENT
# Replace the entire `build_teacher_view` function (lines 749–865) in org_view.py.
# Also update `fetch_org_status` to pass org memberships into it (see bottom).
#
# ── WHAT IS REAL vs MOCK ───────────────────────────────────────────────────────
#
#  ✅ REAL (live data, real navigation):
#    - Teacher's org list                → fetched via get_my_organisation() + member list
#    - Per-org course list               → fetched via get_organisation_courses()
#    - Org card click → org course view  → real navigation to per-org course detail
#    - Freelance tab "Create Free Course"→ navigates to real /create-course route
#
#  🟡 MOCK (wired UI, no backend yet):
#    - "Create Course for Org" button inside org course view  → page.go() stub
#    - Freelance course library list     → empty state (no freelance courses API yet)
#    - Course card click inside org view → page.go() stub (settings route exists)
#
# ── REQUIRED: add this import at the top of org_view.py if not already present ─
#   from src.requests.organisations import get_my_organisation, get_organisation_courses
#
# ── REQUIRED: update fetch_org_status (lines 889–955) ─────────────────────────
#   Change the TEACHER branch from:
#       show_teacher_view()
#   To:
#       memberships = await asyncio.wait_for(get_my_organisation(token), timeout=15)
#       show_teacher_view(memberships or [])
#
#   If get_my_organisation returns a single dict (admin view), wrap it in a list:
#       raw = await asyncio.wait_for(get_my_organisation(token), timeout=15)
#       memberships = raw if isinstance(raw, list) else ([raw] if raw else [])
#       show_teacher_view(memberships)
#
#   Then update show_teacher_view (lines 882–884) to:
#       def show_teacher_view(memberships=None):
#           content_socket.content = build_teacher_view(memberships or [])
#           page.update()
# ═══════════════════════════════════════════════════════════════════════════════


    # ─────────────────────────────────────────────────────────────────────────
    # 4. TEACHER / INSTRUCTOR VIEW
    # ─────────────────────────────────────────────────────────────────────────
    async def build_teacher_view(memberships: list):
        """
        memberships: list of org dicts the teacher belongs to.
        Each dict expected shape (from your existing API):
          { "id", "name", "role", "logo", "theme_color",
            "students", "courses", "members" }
        """

        # ── Per-org course cache ──────────────────────────────────────────────
        # Keyed by org_id, populated lazily when the teacher taps an org card.
        org_courses_cache: dict[str, list] = {}

        # ── State: which org is currently expanded (None = list view) ─────────
        selected_org: dict | None = None

        # ─────────────────────────────────────────────────────────────────────
        # Helpers
        # ─────────────────────────────────────────────────────────────────────
        def role_badge(role_label: str):
            colour_map = {
                "ADMIN":             (ft.Colors.BLUE_50,    ft.Colors.BLUE_800),
                "TEACHER":           (ft.Colors.ORANGE_50,  ft.Colors.ORANGE_800),
                "LEAD TUTOR":        (ft.Colors.PURPLE_50,  ft.Colors.PURPLE_800),
                "GUEST INSTRUCTOR":  (ft.Colors.TEAL_50,    ft.Colors.TEAL_800),
                "INSTRUCTOR":        (ft.Colors.AMBER_50,   ft.Colors.AMBER_900),
            }
            bg, fg = colour_map.get(role_label.upper(), (ft.Colors.GREY_100, ft.Colors.GREY_700))
            return ft.Container(
                padding=ft.padding.symmetric(horizontal=9, vertical=3),
                bgcolor=bg,
                border_radius=20,
                content=ft.Text(role_label, size=10, color=fg, weight=ft.FontWeight.W_600),
            )

        def mini_stat(icon, value, label, color):
            return ft.Row(
                spacing=5,
                controls=[
                    ft.Container(
                        bgcolor=ft.Colors.with_opacity(0.12, color),
                        border_radius=6,
                        padding=5,
                        content=ft.Icon(icon, size=14, color=color),
                    ),
                    ft.Column(
                        spacing=0,
                        controls=[
                            ft.Text(str(value), size=13, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                            ft.Text(label,       size=10, color=ft.Colors.GREY_500),
                        ],
                    ),
                ],
            )

        # ─────────────────────────────────────────────────────────────────────
        # Tab 1 — My Orgs
        # ─────────────────────────────────────────────────────────────────────

        # Mutable socket so we can swap between list ↔ org-detail in-place
        orgs_socket = ft.Column(expand=True)

        async def load_org_detail(org: dict):
            nonlocal selected_org
            selected_org = org
            org_id        = org.get("id", "")
            org_name      = org.get("name", "Organisation")
            theme_color   = org.get("theme_color") or ft.Colors.PRIMARY
            teacher_role  = org.get("role", "Instructor")

            # Fetch courses if not cached  ── REAL ──
            if org_id not in org_courses_cache:
                try:
                    courses = await asyncio.wait_for(
                        get_organisation_courses(token, org_id), timeout=15
                    )
                    org_courses_cache[org_id] = courses or []
                except Exception as ex:
                    print(f"[teacher_view] courses fetch failed: {ex}")
                    org_courses_cache[org_id] = []

            courses = org_courses_cache[org_id]

            # ── Course card inside org detail ────────────────────────────────
            def org_course_card(course: dict):
                title    = course.get("name", "Untitled Course")
                desc     = course.get("description", "")
                enrolled = course.get("total_students", 0)
                public   = course.get("public", False)
                cid      = course.get("id", "")

                status_bg  = ft.Colors.GREEN_50 if public else ft.Colors.GREY_100
                status_fg  = ft.Colors.GREEN_700 if public else ft.Colors.GREY_600
                status_lbl = "Published" if public else "Draft"

                return ft.Container(
                    bgcolor=ft.Colors.SURFACE,
                    border_radius=12,
                    border=ft.border.all(1, ft.Colors.GREY_200),
                    shadow=ft.BoxShadow(
                        blur_radius=6,
                        color=ft.Colors.with_opacity(0.07, ft.Colors.BLACK),
                        offset=ft.Offset(0, 2),
                    ),
                    margin=ft.margin.only(bottom=2),
                    ink=True,
                    # 🟡 MOCK: navigates to course settings; swap for real course detail when ready
                    on_click=lambda e, oid=org_id, cid=cid: page.go(
                        f"/organisations/{oid}/courses/{cid}/settings"
                    ),
                    content=ft.Row(
                        spacing=0,
                        controls=[
                            # Left accent stripe using org theme colour
                            ft.Container(
                                width=4,
                                bgcolor=theme_color,
                                border_radius=ft.BorderRadius.only(top_left=12, bottom_left=12),
                            ),
                            ft.Container(
                                expand=True,
                                padding=ft.padding.symmetric(horizontal=14, vertical=12),
                                content=ft.Column(
                                    spacing=6,
                                    controls=[
                                        ft.Row(
                                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                            controls=[
                                                ft.Text(
                                                    title, size=14,
                                                    weight=ft.FontWeight.W_600,
                                                    color=ft.Colors.ON_SURFACE,
                                                    expand=True,
                                                    max_lines=1,
                                                    overflow=ft.TextOverflow.ELLIPSIS,
                                                ),
                                                ft.Container(
                                                    padding=ft.padding.symmetric(horizontal=8, vertical=3),
                                                    bgcolor=status_bg,
                                                    border_radius=10,
                                                    content=ft.Text(
                                                        status_lbl, size=9,
                                                        color=status_fg,
                                                        weight=ft.FontWeight.W_600,
                                                    ),
                                                ),
                                            ],
                                        ),
                                        ft.Text(
                                            desc, size=12, color=ft.Colors.GREY_500,
                                            max_lines=2, overflow=ft.TextOverflow.ELLIPSIS,
                                        ),
                                        ft.Row(
                                            spacing=12,
                                            controls=[
                                                ft.Row(
                                                    spacing=4,
                                                    controls=[
                                                        ft.Icon(ft.Icons.PEOPLE_ALT_ROUNDED, size=13, color=ft.Colors.GREY_400),
                                                        ft.Text(f"{enrolled} enrolled", size=11, color=ft.Colors.GREY_500),
                                                    ],
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                            ),
                        ],
                    ),
                )

            # ── Org detail screen ────────────────────────────────────────────
            course_list = (
                ft.Column(
                    spacing=10,
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                    controls=[org_course_card(c) for c in courses],
                )
                if courses
                else ft.Column(
                    expand=True,
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(height=24),
                        ft.Icon(ft.Icons.LIBRARY_BOOKS_OUTLINED, size=44, color=ft.Colors.GREY_300),
                        ft.Container(height=10),
                        ft.Text("No courses yet", size=15, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_500),
                        ft.Text(
                            "Create your first course for this organisation.",
                            size=12, color=ft.Colors.GREY_400,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                )
            )

            orgs_socket.controls = [
                ft.Column(
                    expand=True,
                    controls=[
                        # ── Org detail header banner ─────────────────────────
                        ft.Container(
                            bgcolor=theme_color,
                            border_radius=ft.BorderRadius.only(bottom_left=20, bottom_right=20),
                            padding=ft.padding.only(top=8, left=8, right=16, bottom=20),
                            content=ft.Column(
                                spacing=6,
                                controls=[
                                    ft.Row(
                                        controls=[
                                            ft.IconButton(
                                                ft.Icons.ARROW_BACK_ROUNDED,
                                                icon_color=ft.Colors.WHITE,
                                                icon_size=22,
                                                on_click=lambda _: page.run_task(show_org_list),
                                            ),ft.Container(
                                        padding=ft.padding.only(left=16),
                                        content=ft.Column(
                                            spacing=4,
                                            controls=[
                                                ft.Text(
                                                    org_name, size=20,
                                                    weight=ft.FontWeight.W_700,
                                                    color=ft.Colors.WHITE,
                                                ),
                                                role_badge(teacher_role),
                                            ],
                                        ),
                                    ),
                                        ],
                                    ),
                                ],
                            ),
                        ),
                        # ── Courses section ──────────────────────────────────
                        ft.Container(
                            expand=True,
                            padding=ft.padding.symmetric(horizontal=16, vertical=14),
                            content=ft.Column(
                                expand=True,
                                spacing=12,
                                controls=[
                                    ft.Row(
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        controls=[
                                            ft.Text(
                                                "Courses",
                                                size=16,
                                                weight=ft.FontWeight.W_700,
                                                color=ft.Colors.ON_SURFACE,
                                            ),
                                            # 🟡 MOCK: route stub — wire to real create-course flow
                                            ft.ElevatedButton(
                                                content=ft.Row(
                                                    tight=True,
                                                    spacing=4,
                                                    controls=[
                                                        ft.Icon(ft.Icons.ADD_ROUNDED, color=ft.Colors.WHITE, size=16),
                                                        ft.Text("Create Course", color=ft.Colors.WHITE, size=12, weight=ft.FontWeight.W_600),
                                                    ],
                                                ),
                                                bgcolor=theme_color,
                                                height=34,
                                                style=ft.ButtonStyle(
                                                    shape=ft.RoundedRectangleBorder(radius=8),
                                                    elevation=0,
                                                ),
                                                on_click=lambda _: page.go(
                                                    f"/organisations/{org_id}/create-course"  # 🟡 MOCK stub
                                                ),
                                            ),
                                        ],
                                    ),
                                    ft.Divider(height=1, color=ft.Colors.GREY_100),
                                    course_list,
                                ],
                            ),
                        ),
                    ],
                )
            ]
            page.update()

        async def show_org_list():
            nonlocal selected_org
            selected_org = None
            orgs_socket.controls = [build_org_list()]
            page.update()

        # ── Org card (list view) ─────────────────────────────────────────────
        def org_card(org: dict):
            theme_color  = org.get("theme_color") or ft.Colors.PRIMARY
            teacher_role = org.get("role", "Instructor")
            students     = org.get("students", 0)
            courses      = org.get("courses", 0)
            logo_url     = org.get("logo")

            avatar = (
                ft.CircleAvatar(
                    radius=21,
                    bgcolor=ft.Colors.GREY_100,
                    background_image_src=logo_url,
                )
                if logo_url
                else ft.Container(
                    width=42, height=42,
                    bgcolor=ft.Colors.with_opacity(0.15, theme_color),
                    border_radius=12,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text(
                        org.get("name", "?")[0].upper(),
                        size=18, weight=ft.FontWeight.W_700, color=theme_color,
                    ),
                )
            )

            return ft.Container(
                bgcolor=ft.Colors.SURFACE,
                border_radius=14,
                border=ft.border.all(1, ft.Colors.GREY_200),
                shadow=ft.BoxShadow(
                    blur_radius=8,
                    color=ft.Colors.with_opacity(0.07, ft.Colors.BLACK),
                    offset=ft.Offset(0, 3),
                ),
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                ink=True,
                on_click=lambda e, o=org: page.run_task(load_org_detail, o),
                content=ft.Column(
                    spacing=0,
                    controls=[
                        # Coloured top stripe
                        ft.Container(
                            height=4,
                            bgcolor=theme_color,
                        ),
                        ft.Container(
                            padding=ft.padding.symmetric(horizontal=16, vertical=14),
                            content=ft.Column(
                                spacing=12,
                                controls=[
                                    ft.Row(
                                        spacing=12,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                        controls=[
                                            avatar,
                                            ft.Column(
                                                spacing=4,
                                                expand=True,
                                                controls=[
                                                    ft.Text(
                                                        org.get("name", "Organisation"),
                                                        size=15,
                                                        weight=ft.FontWeight.W_700,
                                                        color=ft.Colors.ON_SURFACE,
                                                        max_lines=1,
                                                        overflow=ft.TextOverflow.ELLIPSIS,
                                                    ),
                                                    role_badge(teacher_role),
                                                ],
                                            ),
                                            ft.Icon(
                                                ft.Icons.CHEVRON_RIGHT_ROUNDED,
                                                color=ft.Colors.GREY_400,
                                                size=20,
                                            ),
                                        ],
                                    ),
                                    ft.Divider(height=1, color=ft.Colors.GREY_100),
                                    ft.Row(
                                        spacing=20,
                                        controls=[
                                            mini_stat(ft.Icons.LIBRARY_BOOKS_ROUNDED, courses, "Courses", theme_color),
                                            mini_stat(ft.Icons.PEOPLE_ALT_ROUNDED,   students, "Students", ft.Colors.BLUE_400),
                                        ],
                                    ),
                                ],
                            ),
                        ),
                    ],
                ),
            )

        def build_org_list():
            if not memberships:
                # Empty state — real, shows when teacher has no orgs
                return ft.Container(
                    expand=True,
                    alignment=ft.Alignment.CENTER,
                    padding=40,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=10,
                        controls=[
                            ft.Icon(ft.Icons.BUSINESS_OUTLINED, size=52, color=ft.Colors.GREY_300),
                            ft.Container(height=6),
                            ft.Text("No organisations yet", size=16, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_500),
                            ft.Text(
                                "You haven't been added to any organisation.",
                                size=13, color=ft.Colors.GREY_400,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ],
                    ),
                )

            return ft.ListView(
                expand=True,
                spacing=12,
                padding=ft.padding.symmetric(horizontal=16, vertical=16),
                controls=[org_card(org) for org in memberships],
            )

        # Seed the socket with the org list
        orgs_socket.controls = [build_org_list()]

        # ─────────────────────────────────────────────────────────────────────
        # Tab 2 — Freelance Course Library
        # ─────────────────────────────────────────────────────────────────────
        # 🟡 MOCK: No freelance courses API yet — shows empty state + CTA that
        #          navigates to the real /create-course route.
        freelance_content = ft.Container(
            expand=True,
            padding=ft.padding.symmetric(horizontal=16, vertical=16),
            content=ft.Column(
                expand=True,
                spacing=0,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Column(
                                spacing=2,
                                controls=[
                                    ft.Text(
                                        "Freelance Courses",
                                        size=16, weight=ft.FontWeight.W_700,
                                        color=ft.Colors.ON_SURFACE,
                                    ),
                                    ft.Text(
                                        "Courses you own outside any organisation.",
                                        size=11, color=ft.Colors.GREY_500,
                                    ),
                                ],
                            ),
                            # ✅ REAL navigation to create-course
                            ft.ElevatedButton(
                                content=ft.Row(
                                    tight=True,
                                    spacing=4,
                                    controls=[
                                        ft.Icon(ft.Icons.ADD_ROUNDED, color=ft.Colors.WHITE, size=16),
                                        ft.Text("Create Free", color=ft.Colors.WHITE, size=12, weight=ft.FontWeight.W_600),
                                    ],
                                ),
                                bgcolor=ft.Colors.PRIMARY,
                                height=34,
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=8),
                                    elevation=0,
                                ),
                                on_click=lambda _: page.go("/create-course"),
                            ),
                        ],
                    ),
                    ft.Divider(height=20, color=ft.Colors.GREY_100),
                    # Empty state — will be replaced when freelance course API is live
                    ft.Column(
                            expand=True,
                            alignment=ft.MainAxisAlignment.CENTER,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Container(
                                    width=80, height=80,
                                    bgcolor=ft.Colors.PRIMARY_CONTAINER,
                                    border_radius=40,
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.Icon(
                                        ft.Icons.MIC_EXTERNAL_ON_ROUNDED,
                                        size=38, color=ft.Colors.PRIMARY,
                                    ),
                                ),
                                ft.Container(height=16),
                                ft.Text(
                                    "No freelance courses yet",
                                    size=16, weight=ft.FontWeight.W_600,
                                    color=ft.Colors.ON_SURFACE,
                                ),
                                ft.Container(height=6),
                                ft.Text(
                                    "Publish a course independently — no organisation needed.",
                                    size=12, color=ft.Colors.GREY_500,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                                ft.Container(height=24),
                                ft.OutlinedButton(
                                    content=ft.Row(
                                        tight=True,
                                        spacing=6,
                                        controls=[
                                            ft.Icon(ft.Icons.ADD_ROUNDED, size=16, color=ft.Colors.PRIMARY),
                                            ft.Text("Create Your First Course", size=13, color=ft.Colors.PRIMARY, weight=ft.FontWeight.W_600),
                                        ],
                                    ),
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=10),
                                        side=ft.BorderSide(1.5, ft.Colors.PRIMARY),
                                    ),
                                    height=44,
                                    on_click=lambda _: page.go("/create-course"),
                                ),
                            ],
                        ),
                ],
            ),
        )

        # ─────────────────────────────────────────────────────────────────────
        # Outer shell
        # ─────────────────────────────────────────────────────────────────────
        # ── REPLACE lines 826–865 (the return ft.Column at the bottom of build_teacher_view) ──

        # ── REPLACE the final return ft.Column(...) block inside build_teacher_view ──
# (the one that starts at line 826 in the original, containing the header banner + ft.Tabs)

        # ── Identity card: instructor profile strip ───────────────────────────
        first_name  = user_data.get("first_name", "Instructor")
        last_name   = user_data.get("last_name", "")
        initials    = f"{first_name[0]}{last_name[0]}".upper() if last_name else first_name[:2].upper()
        org_count   = len(memberships)

        identity_card = ft.Container(
            # Subtle gradient: PRIMARY at top-left fading to a deeper tint bottom-right
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=[ft.Colors.PRIMARY, ft.Colors.with_opacity(0.78, ft.Colors.PRIMARY)],
            ),
            padding=ft.padding.only(left=20, right=20, top=18, bottom=16),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        spacing=14,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            # Avatar with white ring
                            ft.Container(
                                width=46, height=46,
                                border_radius=23,
                                bgcolor=ft.Colors.with_opacity(0.22, ft.Colors.WHITE),
                                border=ft.border.all(2, ft.Colors.with_opacity(0.5, ft.Colors.WHITE)),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Text(
                                    initials,
                                    size=16,
                                    weight=ft.FontWeight.W_700,
                                    color=ft.Colors.WHITE,
                                ),
                            ),
                            ft.Column(
                                spacing=2,
                                controls=[
                                    ft.Text(
                                        f"Hey, {first_name}, Ready to teach?",
                                        size=18,
                                        weight=ft.FontWeight.W_700,
                                        color=ft.Colors.WHITE,
                                    ),
                                    ft.Text(
                                        "Instructor",
                                        size=11,
                                        color=ft.Colors.with_opacity(0.75, ft.Colors.WHITE),
                                        weight=ft.FontWeight.W_500,
                                    ),
                                ],
                            ),
                        ],
                    ),
                    # Org count chip
                    ft.Container(
                        padding=ft.padding.symmetric(horizontal=12, vertical=6),
                        bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.WHITE),
                        border_radius=20,
                        border=ft.border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.WHITE)),
                        content=ft.Row(
                            tight=True,
                            spacing=5,
                            controls=[
                                ft.Icon(ft.Icons.BUSINESS_ROUNDED, size=12, color=ft.Colors.WHITE),
                                ft.Text(
                                    f"{org_count} Org{'s' if org_count != 1 else ''}",
                                    size=11,
                                    weight=ft.FontWeight.W_600,
                                    color=ft.Colors.WHITE,
                                ),
                            ],
                        ),
                    ),
                ],
            ),
        )

        return ft.Column(
            expand=True,
            spacing=0,
            controls=[
                identity_card,
                # ── Tab bar ───────────────────────────────────────────────────
                ft.Tabs(
                    length=2,
                    expand=True,
                    selected_index=0,
                    content=ft.Column(
                        expand=True,
                        controls=[
                            ft.TabBar(
                                tab_alignment=ft.TabAlignment.START,
                                indicator_color=ft.Colors.PRIMARY,
                                indicator_size=2,
                                label_color=ft.Colors.PRIMARY,
                                label_text_style=ft.TextStyle(size=12, weight=ft.FontWeight.W_600),
                                unselected_label_color=ft.Colors.GREY_400,
                                unselected_label_text_style=ft.TextStyle(size=12),
                                divider_color=ft.Colors.GREY_100,
                                tabs=[
                                    ft.Tab(label="My Orgs",   icon=ft.Icons.BUSINESS_ROUNDED),
                                    ft.Tab(label="Freelance", icon=ft.Icons.MIC_EXTERNAL_ON_ROUNDED),
                                ],
                            ),
                            ft.TabBarView(
                                expand=True,
                                controls=[
                                    orgs_socket,
                                    freelance_content,
                                ],
                            ),
                        ],
                    ),
                ),
            ],
        )
    # ─────────────────────────────────────────────────────────────────────────
    # 5. NAVIGATION HANDLERS
    # ─────────────────────────────────────────────────────────────────────────
    async def _load_teacher_view(memberships):
        content_socket.content = await build_teacher_view(memberships)
        page.update()
    async def show_dashboard(org_data):
        content_socket.content = await build_dashboard_view(org_data)
        page.update()

    def show_create_form():
        content_socket.content = build_create_form_view()
        page.update()

    def show_promo_view():
        content_socket.content = build_promo_view()
        page.update()

    def show_teacher_view(memberships=None):
        page.run_task(_load_teacher_view, memberships or [])




    # ─────────────────────────────────────────────────────────────────────────
    # 6. INITIAL LOAD  (with full error safety)
    # ─────────────────────────────────────────────────────────────────────────
    async def fetch_org_status():
        if role in ("TEACHER", "INSTRUCTOR"):
            try:
                memberships = await asyncio.wait_for(
                    get_joined_organisations(token), timeout=15
                )
            except Exception:
                memberships = []
            show_teacher_view(memberships)
            return

        try:
            org_data = await asyncio.wait_for(
                get_my_organisation(token), timeout=15
            )
            if org_data:
                await show_dashboard(org_data)
            else:
                show_promo_view()

        except asyncio.TimeoutError:
            content_socket.content = ft.Container(
                expand=True,
                alignment=ft.Alignment.CENTER,
                padding=30,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=10,
                    controls=[
                        ft.Icon(ft.Icons.WIFI_OFF_ROUNDED, size=48, color=ft.Colors.ORANGE_400),
                        ft.Text("Connection timed out", size=17, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                        ft.Text("Please check your internet connection\nand try again.", size=13, color=ft.Colors.GREY_500, text_align=ft.TextAlign.CENTER),
                        ft.Container(height=8),
                        ft.ElevatedButton(
                            "Retry",
                            bgcolor=ft.Colors.PRIMARY,
                            color=ft.Colors.WHITE,
                            height=42,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
                            on_click=lambda _: page.run_task(fetch_org_status),
                        ),
                    ],
                ),
            )
            page.update()

        except Exception as ex:
            content_socket.content = ft.Container(
                expand=True,
                alignment=ft.Alignment.CENTER,
                padding=30,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=10,
                    controls=[
                        ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, size=48, color=ft.Colors.RED_400),
                        ft.Text("Something went wrong", size=17, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                        ft.Text(f"{type(ex).__name__}: unable to load your organisation.", size=13, color=ft.Colors.GREY_500, text_align=ft.TextAlign.CENTER),
                        ft.Container(height=8),
                        ft.ElevatedButton(
                            "Retry",
                            bgcolor=ft.Colors.PRIMARY,
                            color=ft.Colors.WHITE,
                            height=42,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
                            on_click=lambda _: page.run_task(fetch_org_status),
                        ),
                    ],
                ),
            )
            page.update()

    page.run_task(fetch_org_status)

    # ─────────────────────────────────────────────────────────────────────────
    # 7. VIEW
    # ─────────────────────────────────────────────────────────────────────────
    return ft.View(
        route="/organisations",
        bottom_appbar=app_bar,
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        padding=0,
        controls=[
            ft.SafeArea(expand=True, content=content_socket)
        ],
    )