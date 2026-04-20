from calendar import c

import flet as ft
from src.components.bottom_appbar import get_bottom_appbar
from src.requests.organisations import create_organisation, get_my_organisation, get_organisation_members, get_organisation_courses
import base64

async def organisations_view(page: ft.Page):
    app_bar = get_bottom_appbar(page)
    token = await page.shared_preferences.get("auth_token")
    
    # Safely get the user role
    user_data = page.session.store.get("current_user") or {}
    role = user_data.get("role", "STUDENT").upper()

    # 1. Setup the main container that will swap between screens
    # --- THE FIX: Replaced AnimatedSwitcher with a standard Container ---
    content_socket = ft.Container(
        expand=True, 
        alignment=ft.Alignment.CENTER, 
        content=ft.ProgressRing(color=ft.Colors.PRIMARY)
    )

    # 2. Define the UI for the Main Dashboard
    async def build_dashboard_view(org_data: dict):
        org_name = org_data.get("name", "My Workspace")
        org_id = org_data.get("id", "")
        org_email = org_data.get("email", "admin@org.com")
        org_phone = org_data.get("number", "+000 0000 0000")
        
        # --- NEW: Extract Theme Color from DB (Defaults to PRIMARY if none exists) ---
        theme_color = org_data.get("theme_color") or ft.Colors.PRIMARY
        
        stats = {
            "members": org_data.get("members", 0),
            "courses": org_data.get("courses", 0),
            "staff": org_data.get("staff", 0),
            "plan": org_data.get("plan",{}).get("name", "Free"), # Or "Premium (Ends 12/26)",\
            "students": org_data.get("students", 0)
        }
        
        # Await the API call and fix the ID lookup
        members = await get_organisation_members(token, org_id)
        recent_members = [member for member in members]

        courses = await get_organisation_courses(token, org_id)
        recent_courses = [course for course in courses]
        # --- HELPER: Stat Card Generator (Image 2 Style) ---
        def stat_card(icon_name, title, value, bg_color):
            return ft.Container(
                bgcolor=bg_color,
                padding=20,
                border_radius=15,
                # Responsive: Takes up 50% width on mobile (xs=6), 25% on desktop (sm=3)
                col={"xs": 6, "sm": 2.4}, 
                content=ft.Row([
                    ft.Column([
                        ft.Text(str(value), size=24, weight=ft.FontWeight.BOLD, color="white"),
                        ft.Text(title, size=12, color="white70", weight=ft.FontWeight.W_500)
                    ], spacing=0, expand=True),
                    
                    # Circular icon container
                    ft.Container(
                        padding=10,
                        bgcolor=ft.Colors.with_opacity(0.2, "white"),
                        shape=ft.BoxShape.CIRCLE,
                        content=ft.Icon(icon_name, color="white", size=24)
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            )

        # --- HELPER: Rich Member Row ---
        def build_member_row(member: dict):
            member_role = member.get("role", "STUDENT").upper()
            
            if member_role == "ADMIN":
                badge_bg = ft.Colors.BLUE_100
                badge_text = ft.Colors.BLUE_900
            elif member_role == "TEACHER":
                badge_bg = ft.Colors.ORANGE_100
                badge_text = ft.Colors.ORANGE_900
            else:
                badge_bg = ft.Colors.GREY_200
                badge_text = ft.Colors.GREY_800

            initials = f'{member["first_name"][0]}{member["last_name"][0]}'.upper()

            return ft.Container(
                padding=ft.padding.symmetric(vertical=10, horizontal=5),
                border_radius=8,
                content=ft.Row([
                    ft.Row([
                        ft.CircleAvatar(
                            content=ft.Text(initials, size=14, weight=ft.FontWeight.BOLD), 
                            bgcolor=ft.Colors.PRIMARY_CONTAINER,
                            color=ft.Colors.ON_PRIMARY_CONTAINER,
                            radius=20
                        ),
                        ft.Column([
                            ft.Text(f'{member["first_name"]} {member["last_name"]}', size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                            ft.Text(member["email"], size=13, color=ft.Colors.ON_SURFACE_VARIANT)
                        ], spacing=2)
                    ], expand=True),
                    
                    ft.Row([
                        ft.Container(
                            padding=ft.padding.symmetric(horizontal=10, vertical=4),
                            bgcolor=badge_bg,
                            border_radius=12,
                            content=ft.Text(member_role, size=8, color=badge_text, weight=ft.FontWeight.BOLD)
                        ),
                        ft.PopupMenuButton(
                            icon=ft.Icons.MORE_VERT_ROUNDED,
                            icon_color=ft.Colors.ON_SURFACE_VARIANT,
                            items=[
                                ft.PopupMenuItem(content=ft.Text("View Profile"), icon=ft.Icons.PERSON_SEARCH_ROUNDED),
                                ft.PopupMenuItem(content=ft.Text("Change Role"), icon=ft.Icons.MANAGE_ACCOUNTS_ROUNDED),
                                ft.PopupMenuItem(content=ft.Text("Remove Member"), icon=ft.Icons.DELETE_OUTLINE_ROUNDED),
                            ]
                        )
                    ], spacing=10)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            )
        # --- HELPER: Rich Course Row (Based on uploaded design) ---
        def build_course_row(course: dict):
            # Extract data with safe fallbacks
            title = course.get("name", "Untitled Course")
            desc = course.get("description", "No description available.") # You can pull this from relational data later
            image_url = course.get("image_url")
            course_id = course.get("id", "")
            course_status = course.get("public")
            
            # --- Badges ---
            # 1. Level/Status Badge (Green)
            level_badge = ft.Container(
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                bgcolor=ft.Colors.GREEN_50 if course_status else "grey",
                border_radius=12,
                content=ft.Text("Public" if course_status else "draft", size=8, color=ft.Colors.GREEN_700 if course_status else "black", weight=ft.FontWeight.W_600)
            )

            # 2. Enrollment Badge (Blue)
            enroll_badge = ft.Container(
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                bgcolor=ft.Colors.BLUE_50,
                border_radius=12,
                content=ft.Text("160 Enrolled", size=8, color=ft.Colors.BLUE_700, weight=ft.FontWeight.W_600)
            )

            return ft.Container(
                shadow=ft.BoxShadow(blur_radius=5, color=ft.Colors.BLACK_12, offset=ft.Offset(0, 2)),
                bgcolor=ft.Colors.SURFACE,
                ink=True,
                border_radius=12,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS, # Ensures the image corners respect the border radius
                content=ft.Row(
                    spacing=0, # Keep the image flush against the left wall
                    controls=[
                        # --- LEFT: The Thumbnail Image ---
                        ft.Container(
                            width=100, # Fixed width for uniform thumbnails
                            height=140, # Forces a standard 16:9ish ratio
                            bgcolor="white", # Placeholder bg color
                            content=ft.Image(
                                src=image_url or "placeholder.png",
                                fit=ft.BoxFit.COVER
                            )
                        ),
                        
                        # --- RIGHT: The Course Content ---
                        ft.Container(
                            expand=True, # Takes up all remaining horizontal space
                            padding=15,
                            content=ft.Column(
                                spacing=4,
                                controls=[
                                    # Title
                                    ft.Row(
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN, 
                                        controls=[
                                            ft.Text(title, size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS), 
                                            # THE FIX: Wrapped the string in an actual ft.Icon control
                                            ft.IconButton(ft.Icons.EDIT, icon_color=theme_color, on_click=lambda e, c_id=course_id: page.go(f"/courses/{course_id}/settings")) # <--- THE FIX: Dynamic Theme Color and proper routing
                                        ]
                                    ),
                                    # Description
                                    ft.Text(desc, size=12, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                    
                                    ft.Container(height=2), # Tiny spacer
                                     # Teacher
                                    
                                    ft.Container(height=4), # Spacer pushing the bottom row down
                                    
                                    # Bottom Row: Badges & Action Button
                                    ft.Row(
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        controls=[
                                            ft.Row([level_badge, enroll_badge], spacing=10, wrap=True), # Wrap prevents overflow on tiny screens
                                        ]
                                    )
                                ]
                            )
                        ),
                        ft.Container(height=20)
                    ]
                )
            )

        # --- HELPER: Section Container Generator (Side-by-Side Responsive) ---
        def dashboard_section(title, list_content, manage_route, action_icon=ft.Icons.ADD):
            return ft.Container(
                col={"xs": 12, "md": 6}, # Desktop: 50% width, Mobile: 100% width
                bgcolor=ft.Colors.SURFACE,
                padding=20,
                border_radius=15,
                border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                content=ft.Column(scroll=ft.ScrollMode.AUTO, controls=[
                    ft.Row(spacing=20, controls=[
                        ft.Text(title, size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                        ft.IconButton(
                            icon=action_icon, 
                            icon_color=ft.Colors.WHITE,
                            bgcolor=theme_color, # <--- THE FIX: Matched action buttons to the theme color too
                            icon_size=20,
                            on_click=lambda e, r=manage_route: page.go(r) 
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Divider(height=20, color=ft.Colors.OUTLINE_VARIANT),
                    list_content
                ])
            )

        # --- THE MAIN LAYOUT ---
        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO, 
            controls=[
                # 1. The Header Card (Image 1 Style - Purple Banner with Overlapping Logo)
                # 1. The Header Card (Image 1 Style - Purple Banner with Overlapping Logo)
                ft.Container(
                    margin=ft.margin.symmetric(horizontal=20, vertical=10),
                    bgcolor=ft.Colors.SURFACE,
                    border_radius=15,
                    border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                    content=ft.Column(spacing=0, controls=[
                        # Top Purple Banner (No fixed height, uses bottom padding for overlap space)
                        ft.Container(
                            bgcolor=theme_color, # <--- THE FIX: Dynamic Theme Color
                            border_radius=ft.BorderRadius.only(top_left=15, top_right=15),
                            padding=ft.padding.only(top=5, right=5, bottom=45, left=15),
                            alignment=ft.Alignment.TOP_RIGHT,
                            content=ft.IconButton(
                                ft.Icons.MORE_HORIZ, 
                                icon_color=ft.Colors.WHITE, 
                                on_click=lambda _: page.go("/organisations/settings")
                            )
                        ),
                        # Bottom Info Area with Overlap Avatar (No fixed height, tightened padding)
                        ft.Container(
                                padding=ft.padding.only(left=20, right=20, bottom=15),
                                content=ft.Column(spacing=5, controls=[
                                    # The Avatar pulled up over the banner
                                    ft.Container(
                                        margin=ft.margin.only(top=-50), 
                                        content=ft.CircleAvatar(
                                            radius=50, 
                                            bgcolor=ft.Colors.WHITE, 
                                            # THE SHORTCUT: Let Flet handle the image masking
                                            content=ft.CircleAvatar(
                                                radius=46, 
                                                bgcolor=ft.Colors.BLUE_GREY_100, 
                                                background_image_src=org_data.get("logo") or "placeholder.png"
                                            )
                                        )
                                    ),
                                # Organization Name & Contacts Row (Tightened text spacing)
                                ft.Row(wrap=True, alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                                    ft.Column(spacing=2, controls=[
                                        ft.Text(org_name, size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                                        ft.Text("Admin Dashboard", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
                                    ]),
                                    # Contact details (Phone & Email)
                                    ft.Row(spacing=20, wrap=True, controls=[
                                        ft.Column(spacing=0, controls=[
                                            ft.Text("Phone", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                                            ft.Row(spacing=5, controls=[
                                                ft.Icon(ft.Icons.PHONE_ROUNDED, size=13, color=theme_color), # <--- THE FIX: Dynamic Theme Color
                                                ft.Text(org_phone, size=12, weight=ft.FontWeight.W_500)
                                            ])
                                        ]),
                                        ft.Column(spacing=0, controls=[
                                            ft.Text("Email", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                                            ft.Row(spacing=5, controls=[
                                                ft.Icon(ft.Icons.EMAIL_ROUNDED, size=13, color=theme_color), # <--- THE FIX: Dynamic Theme Color
                                                ft.Text(org_email, size=12, weight=ft.FontWeight.W_500)
                                            ])
                                        ])
                                    ])
                                ])
                            ])
                        )
                    ])
                ),
                
                # 2. The Dashboard Body (Stats & Side-by-Side Sections)
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=20),
                    content=ft.Column(
                        spacing=20, 
                        controls=[
                            # A. Stat Cards
                            ft.ResponsiveRow(
                                run_spacing=15,
                                controls=[
                                    stat_card(ft.Icons.GROUPS_ROUNDED, "Members", stats["members"], ft.Colors.ORANGE_400),
                                    stat_card(ft.Icons.LIBRARY_BOOKS_ROUNDED, "Courses", stats["courses"], ft.Colors.INDIGO_400),
                                    stat_card(ft.Icons.BADGE_ROUNDED, "Staff", stats["staff"], ft.Colors.CYAN_400),
                                    stat_card(ft.Icons.SCHOOL_OUTLINED, "Students", stats["students"], ft.Colors.BLUE_ACCENT_400),
                                    stat_card(ft.Icons.WORKSPACE_PREMIUM_ROUNDED, "Plan", stats["plan"], ft.Colors.PURPLE_400),
                                ]
                            ),
                            
                            # B. Side-by-Side Sections (Contacts and Courses)
                            ft.ResponsiveRow(
                                run_spacing=20,
                                controls=[
                                    dashboard_section(
                                        title="Members", 
                                        list_content=ft.Column(
                                            controls=[build_member_row(m) for m in recent_members] if recent_members else [ft.Text("No members have joined yet.", color=ft.Colors.ON_SURFACE_VARIANT)],
                                            spacing=5
                                        ), 
                                        manage_route="/organisations/members"
                                    ),
                                    
                                    dashboard_section(
                                        title="Courses", 
                                        list_content=ft.Column(
                                            controls=[build_course_row(c) for c in recent_courses] if recent_courses else [ft.Text("No active courses published.", color=ft.Colors.ON_SURFACE_VARIANT)],
                                            spacing=5
                                        ), 
                                        manage_route=f"/organisations/{org_id}/courses",
                                        action_icon=ft.Icons.LOCAL_LIBRARY_OUTLINED
                                    )
                                ]
                            ),
                            
                            ft.Container(height=30) 
                        ]
                    )
                )
            ]
        )
    # 3. Define the UI for the Creation Form
    def build_create_form_view():
        input_style = {
            "border_color": ft.Colors.OUTLINE_VARIANT,
            "focused_border_color": ft.Colors.PRIMARY,
            "cursor_color": ft.Colors.PRIMARY,
            "border_radius": 8,
            "width": float("inf")
        }

        name_input = ft.TextField(label="Organization Name *", **input_style)
        email_input = ft.TextField(label="Contact Email *", keyboard_type=ft.KeyboardType.EMAIL, **input_style)
        number_input = ft.TextField(label="Phone Number *", keyboard_type=ft.KeyboardType.PHONE, **input_style)
        website_input = ft.TextField(label="Website (Optional)", keyboard_type=ft.KeyboardType.URL, **input_style)
        address_input = ft.TextField(label="Physical Address *", multiline=True, min_lines=2, max_lines=4, **input_style)
        error_text = ft.Text("", color=ft.Colors.ERROR, size=12, visible=False)

        # --- NEW: Logo State & UI Elements ---
        selected_logo_bytes = None
        selected_logo_name = None
        
        logo_icon = ft.Icon(ft.Icons.CLOUD_UPLOAD_OUTLINED, color=ft.Colors.PRIMARY, size=30)
        logo_text = ft.Text("Upload Logo (Optional)", color=ft.Colors.ON_SURFACE_VARIANT)

        # --- NEW: Theme Color State & UI ---
        curated_themes = [
            ft.Colors.PRIMARY, ft.Colors.BLUE_500, ft.Colors.TEAL_500, 
            ft.Colors.GREEN_500, ft.Colors.ORANGE_500, ft.Colors.RED_500, ft.Colors.PURPLE_500
        ]
        selected_theme_color = curated_themes[0] # Default

        def handle_color_select(e):
            nonlocal selected_theme_color
            selected_theme_color = e.control.data
            for swatch in color_swatches_row.controls:
                swatch.border = ft.border.all(3, ft.Colors.ON_SURFACE) if swatch.data == selected_theme_color else None
            page.update()

        color_swatches_row = ft.Row(
            spacing=10, 
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=35, height=35, border_radius=20, bgcolor=color,
                    data=color, ink=True, on_click=handle_color_select,
                    border=ft.border.all(3, ft.Colors.ON_SURFACE) if color == selected_theme_color else None
                ) for color in curated_themes
            ]
        )
        
        theme_picker_container = ft.Container(
            width=float("inf"), padding=15, border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT), border_radius=8,
            content=ft.Column([
                ft.Text("Select Brand Color", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                color_swatches_row
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        )

        async def handle_logo_pick(e):
            nonlocal selected_logo_bytes, selected_logo_name
            
            # Open native file explorer, restricted to Images, and read the raw bytes
            files = await ft.FilePicker().pick_files(
                allow_multiple=False,
                file_type=ft.FilePickerFileType.IMAGE,
                with_data=True # CRITICAL: This grabs the actual image data for Bunny.net
            )
            
            if files:
                selected = files[0]
                selected_logo_bytes = selected.bytes
                selected_logo_name = selected.name
                
                # Update UI to show success
                logo_icon.name = ft.Icons.CHECK_CIRCLE_ROUNDED
                logo_icon.color = ft.Colors.GREEN
                logo_text.value = f"Selected: {selected_logo_name}"
                logo_text.color = ft.Colors.GREEN
                page.update()

        async def handle_submit(e):
            if not all([name_input.value, email_input.value, number_input.value, address_input.value]):
                error_text.value = "Please fill in all required fields (*)."
                error_text.visible = True
                page.update()
                return

            error_text.visible = False
            e.control.disabled = True
            e.control.content = ft.Row([
                ft.ProgressRing(width=16, height=16, color=ft.Colors.ON_PRIMARY, stroke_width=2),
                ft.Text("Creating...", weight=ft.FontWeight.BOLD, color=ft.Colors.ON_PRIMARY)
            ], alignment=ft.MainAxisAlignment.CENTER)
            page.update()

            # --- THE FIX: Convert bytes to Base64 String ---
            logo_b64 = None
            if selected_logo_bytes:
                logo_b64 = base64.b64encode(selected_logo_bytes).decode('utf-8')

            # --- Payload Preparation ---
            payload = {
                "name": name_input.value.strip(),
                "email": email_input.value.strip(),
                "number": number_input.value.strip(),
                "website": f"https://{website_input.value.strip()}" if website_input.value else None,
                "address": address_input.value.strip(),
                "logo_bytes": logo_b64,              # Pass the string, not the raw bytes!
                "logo_filename": selected_logo_name,
                "theme_color": selected_theme_color  # <--- THE FIX: Included chosen color in payload
            }
            
            token = await page.shared_preferences.get("auth_token") # Note the client_storage change here!
            new_org_data = await create_organisation(token, payload)
            
            # Optional but highly recommended: Safely check if the API actually succeeded
            if isinstance(new_org_data, dict):
                await show_dashboard(new_org_data)
            else:
                # Handle API failure visually so the UI doesn't freeze or crash
                e.control.disabled = False
                e.control.content = ft.Text("Create Organization", size=16, weight=ft.FontWeight.BOLD)
                error_text.value = "Failed to create organization. Please try again."
                error_text.visible = True
                page.update()
                
        submit_btn = ft.Button(
            content=ft.Text("Create Organization", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_PRIMARY),
            bgcolor=ft.Colors.PRIMARY,
            height=50,
            width=float("inf"),
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            on_click=handle_submit
        )

        return ft.Container(
            expand=True,
            padding=20,
            bgcolor=ft.Colors.SURFACE,
            content=ft.Column(
                scroll=ft.ScrollMode.AUTO,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row([
                        ft.IconButton(ft.Icons.ARROW_BACK_ROUNDED, on_click=lambda _: show_promo_view()),
                        ft.Text("New Organization", size=20, weight=ft.FontWeight.BOLD),
                        ft.Container(width=40) 
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Divider(height=20, color=ft.Colors.OUTLINE_VARIANT),
                    name_input, email_input, number_input, website_input, address_input,
                    
                    # --- NEW: The Interactive Logo Container ---
                    ft.Container(
                        width=float("inf"), 
                        padding=20, 
                        border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT), 
                        border_radius=8,
                        content=ft.Column([
                            logo_icon,
                            logo_text
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        ink=True, 
                        on_click=handle_logo_pick # Triggers the picker
                    ),
                    
                    ft.Container(height=10),
                    
                    # --- NEW: Add the Theme Picker to the UI ---
                    theme_picker_container,
                    
                    ft.Container(height=10),
                    error_text, submit_btn, ft.Container(height=20),
                ]
            )
        )

    # 4. Define the UI for the Promotional screen (Zero State)
    def build_promo_view():
        return ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            padding=30,
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    ft.Container(
                        width=120, height=120, bgcolor=ft.Colors.PRIMARY, border_radius=60, alignment=ft.Alignment.CENTER,
                        content=ft.Icon(ft.Icons.BUSINESS_SHARP, size=60, color=ft.Colors.ON_PRIMARY)
                    ),
                    ft.Container(height=20),
                    ft.Text("Scale Your Teaching", size=28, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Text(
                        "Create a centralized hub to manage your instructors, publish courses, and monitor student progress.",
                        size=16, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=30),
                    ft.ElevatedButton(
                        content=ft.Row([
                            ft.Icon(ft.Icons.ADD_ROUNDED, color=ft.Colors.ON_PRIMARY),
                            ft.Text("Create Organization", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_PRIMARY)
                        ], alignment=ft.MainAxisAlignment.CENTER, tight=True),
                        bgcolor=ft.Colors.PRIMARY, height=50, width=float("inf"),
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
                        on_click=lambda _: show_create_form()
                    )
                ]
            )
        )

    # ==========================================
    # 5. Define the UI for the Teacher Dashboard
    # ==========================================
    def build_teacher_view():
        # MOCK DATA: List of orgs this teacher belongs to
        mock_orgs = [
            {"id": "org_1", "name": "BuildHub Academy", "role": "Lead Tutor", "students": 142},
            {"id": "org_2", "name": "FUTMinna Engineering", "role": "Guest Instructor", "students": 85}
        ]

        # Card generator for each organization
        def org_card(org):
            return ft.Container(
                bgcolor=ft.Colors.SURFACE,
                padding=20,
                border_radius=14,
                border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                ink=True,
                on_click=lambda e, o_id=org["id"]: page.go(f"/organisations/{o_id}"),
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.BUSINESS_CENTER, color=ft.Colors.PRIMARY, size=30),
                        ft.Column([
                            ft.Text(org["name"], size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                            ft.Text(org["role"], size=12, color=ft.Colors.ON_SURFACE_VARIANT)
                        ], spacing=0)
                    ], alignment=ft.MainAxisAlignment.START),
                    ft.Divider(height=20, color=ft.Colors.OUTLINE_VARIANT),
                    ft.Row([
                        ft.Icon(ft.Icons.PEOPLE_ALT_ROUNDED, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(f"{org['students']} Students Enrolled", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
                    ])
                ])
            )

        my_orgs_content = ft.ListView(
            expand=True,
            spacing=15,
            padding=20,
            controls=[org_card(org) for org in mock_orgs]
        )

        freelance_content = ft.Container(
            padding=20,
            expand=True,
            content=ft.Column([
                ft.Row([
                    ft.Text("My Freelance Courses", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.FilledTonalButton(
                        content=ft.Text("Upload New +"), 
                        height=35,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                        on_click=lambda _: print("Route to Freelance Upload")
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(height=20, color=ft.Colors.OUTLINE_VARIANT),
                ft.Text("You haven't uploaded any freelance courses yet.", color=ft.Colors.ON_SURFACE_VARIANT)
            ])
        )

        return ft.Column(
            expand=True,
            controls=[
                # Header for Teacher Dashboard
                ft.Container(
                    bgcolor=ft.Colors.PRIMARY,
                    height=100, 
                    border_radius=ft.BorderRadius.only(bottom_left=25, bottom_right=25),
                    padding=ft.Padding(top=10, left=25, right=25, bottom=20),
                    content=ft.Row([
                        ft.Text("Instructor Dashboard", size=25, weight=ft.FontWeight.BOLD, color="white"),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                ),
                ft.Container(height=5),
                
                # Tabs for Teacher: My Orgs vs Freelance
                ft.Tabs(
                    length=2,
                    expand=True,
                    selected_index=0,
                    content=ft.Column(
                        expand=True,
                        controls=[
                            ft.TabBar(
                                tab_alignment=ft.TabAlignment.CENTER,
                                indicator_color=ft.Colors.PRIMARY,
                                label_color=ft.Colors.PRIMARY,
                                unselected_label_color=ft.Colors.ON_SURFACE_VARIANT,
                                tabs=[
                                    ft.Tab(label="My Orgs", icon=ft.Icons.BUSINESS_SHARP),
                                    ft.Tab(label="Freelance", icon=ft.Icons.MIC_EXTERNAL_ON_ROUNDED),
                                ]
                            ),
                            ft.TabBarView(
                                expand=True, 
                                controls=[
                                    my_orgs_content,
                                    freelance_content
                                ]
                            )
                        ]
                    )
                )
            ]
        )

    # 6. Screen Navigation Handlers
    
    # Made async so we can await the dashboard builder
    async def show_dashboard(org_data):
        content_socket.content = await build_dashboard_view(org_data)
        page.update()

    def show_create_form():
        content_socket.content = build_create_form_view()
        page.update()

    def show_promo_view():
        content_socket.content = build_promo_view()
        page.update()

    def show_teacher_view():
        content_socket.content = build_teacher_view()
        page.update()

    # 7. Check database on initial load
    async def fetch_org_status():
        # Logic Gate: Direct to Teacher View if role is TEACHER
        if role == "TEACHER" or role == "INSTRUCTOR":
            show_teacher_view()
        else:
            # Fallback to Admin Flow
            org_data = await get_my_organisation(token)
            
            if org_data:
                await show_dashboard(org_data) # Added await here
            else:
                show_promo_view()

    # Trigger the check
    page.run_task(fetch_org_status)

    # 8. Return the final view layout
    return ft.View(
        route="/organisations",
        bottom_appbar=app_bar,
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        padding=0,
        controls=[
            ft.SafeArea(
                expand=True,
                content=content_socket 
            )
        ]
    )