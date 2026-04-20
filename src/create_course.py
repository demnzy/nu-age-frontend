
import flet as ft
from src.components.bottom_appbar import get_bottom_appbar
from src.requests.Courses import create_course,get_categories,get_courses
from src.requests.organisations import get_my_organisation, get_organisation_members
# MOCK API FUNCTIONS (Replace these with your actual backend requests)

async def create_courses_view(page: ft.Page, org_id: str = None):
    app_bar = get_bottom_appbar(page)
    token = await page.shared_preferences.get("auth_token")
    
    # 1. Placeholders for State Management
    categories_options = []
    teachers_options = []
    theme_color = ft.Colors.PRIMARY
    current_courses = []

    # --- NEW: The Lazy Load Container ---
    content_socket = ft.Container(
        expand=True, 
        alignment=ft.Alignment.CENTER, 
        content=ft.ProgressRing(color=ft.Colors.PRIMARY)
    )
    
    # --- HELPER 1: The Reusable Course Card (Reused from Org Card Design) ---
    def build_course_card(course: dict):
            # Extract data with safe fallbacks
            title = course.get("name", "Untitled Course")
            desc = course.get("description", "No description available.")
            image_url = course.get("image_url")
            course_id = course.get("id")
            
            # --- Badges (Adapted to the soft-pill mockup style) ---
            # 1. Status Badge
            is_public = course.get("public")
            status_badge = ft.Container(
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                bgcolor=ft.Colors.GREEN_50 if is_public else ft.Colors.GREY_100,
                border_radius=12,
                content=ft.Text("Public" if is_public else "Draft", 
                                size=11, color=ft.Colors.GREEN_700 if is_public else ft.Colors.GREY_700, weight=ft.FontWeight.W_600)
            )

            # 2. Type Badge
            is_supervised = course.get("supervised")
            type_badge = ft.Container(
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                bgcolor=ft.Colors.BLUE_50 if is_supervised else ft.Colors.PURPLE_50,
                border_radius=12,
                content=ft.Text("Instructor-Led" if is_supervised else "Automated", 
                                size=11, color=ft.Colors.BLUE_700 if is_supervised else ft.Colors.PURPLE_700, weight=ft.FontWeight.W_600)
            )

            return ft.Container(
                col={"xs": 12, "sm": 6, "md": 4, "lg": 3}, # Keeps it responsive in the grid
                bgcolor=ft.Colors.SURFACE,
                border_radius=12,
                border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS, # Critical: Keeps the top image corners rounded
                ink=True,
                content=ft.Column(
                    spacing=0, 
                    controls=[
                        # --- TOP: The Cover Image ---
                        ft.Container(
                            width=float("inf"),
                            height=130, # Creates a nice square-ish top half
                            bgcolor=ft.Colors.PRIMARY_CONTAINER,
                            content=ft.Image(
                                src=image_url or "https://nu-age-cdn.b-cdn.net/logos/placeholder%202.png",
                                fit=ft.BoxFit.COVER
                            )
                        ),
                        
                        # --- BOTTOM: The Course Content ---
                        ft.Container(
                            padding=15,
                            content=ft.Column(
                                spacing=8,
                                controls=[
                                    # Badges
                                    ft.Row([status_badge, type_badge], spacing=10, wrap=True),
                                    
                                    # Text
                                    ft.Text(title, size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                    ft.Text(desc, size=12, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                    
                                    ft.Container(height=5), # Spacer pushing the button down
                                    
                                    # Action Button (Matches the mockup's Deep Orange)
                                    ft.ElevatedButton(
                                        "Manage", 
                                        bgcolor= ft.Colors.PRIMARY,
                                        color= "white",
                                        width=float("inf"), # Makes it span the full card width for a solid base
                                        style=ft.ButtonStyle(
                                            shape=ft.RoundedRectangleBorder(radius=6),
                                            padding=ft.padding.symmetric(vertical=0)
                                        ),
                                        height=32,
                                        # Button click specifically for routing (though the card itself is also clickable)
                                        on_click=lambda e: page.go(f"/courses/{course_id}/manage")
                                    )
                                ]
                            )
                        )
                    ]
                )
            )
            
    # --- HELPER 2: The Grid Container ---
    courses_grid = ft.ResponsiveRow(run_spacing=15)
    
    def refresh_grid(initial_load=False):
        courses_grid.controls.clear()
        if not current_courses:
            courses_grid.controls.append(
                ft.Container(
                    col=12, padding=50, alignment=ft.Alignment.CENTER,
                    content=ft.Text("No courses created yet. Click 'New Course' to begin.", color=ft.Colors.ON_SURFACE_VARIANT)
                )
            )
        else:
            for course in current_courses:
                courses_grid.controls.append(build_course_card(course))
                
        # Only call page.update() if this is triggered AFTER the view is mounted (like from the modal)
        if not initial_load:
            page.update()

    # --- HELPER 3: The Creation Modal (Pop-up Form) ---
    def open_create_modal(e):
        input_style = {"border_color": ft.Colors.OUTLINE_VARIANT, "focused_border_color": ft.Colors.PRIMARY, "border_radius": 8}

        name_input = ft.TextField(label="Course Title *", **input_style)
        desc_input = ft.TextField(label="Short Description", multiline=True, min_lines=2, max_lines=3, **input_style)
        
        category_dropdown = ft.Dropdown(label="Category", options=categories_options, **input_style)
        teacher_dropdown = ft.Dropdown(label="Teacher (Optional)", options=teachers_options, **input_style)
        objectives_list = []
        objectives_chips = ft.Row(wrap=True, spacing=5)
        selected_logo_bytes = None
        selected_logo_name = None
        
        logo_icon = ft.Icon(ft.Icons.CLOUD_UPLOAD_OUTLINED, color=ft.Colors.PRIMARY, size=30)
        logo_text = ft.Text("Upload Logo (Optional)", color=ft.Colors.ON_SURFACE_VARIANT)
        
        async def handle_logo_pick(e):
            nonlocal selected_logo_bytes, selected_logo_name
            
            files = await ft.FilePicker().pick_files(
                allow_multiple=False,
                file_type=ft.FilePickerFileType.IMAGE,
                with_data=True 
            )
            
            if files:
                selected = files[0]
                selected_logo_bytes = selected.bytes
                selected_logo_name = selected.name
                
                logo_icon.name = ft.Icons.CHECK_CIRCLE_ROUNDED
                logo_icon.color = ft.Colors.GREEN
                logo_text.value = f"Selected: {selected_logo_name}"
                logo_text.color = ft.Colors.GREEN
                page.update()
                
        def add_objective(e):
            val = obj_input.value.strip()
            if val and val not in objectives_list:
                objectives_list.append(val)
                
                def remove_chip(e_delete):
                    chip_to_remove = e_delete.control
                    objectives_list.remove(chip_to_remove.data)
                    objectives_chips.controls.remove(chip_to_remove)
                    page.update()

                new_chip = ft.Chip(
                    label=ft.Text(val, size=12), 
                    data=val,
                    delete_icon=ft.Icon(ft.Icons.CANCEL),
                    on_delete=remove_chip
                )
                objectives_chips.controls.append(new_chip)
                obj_input.value = ""
                page.update()

        obj_input = ft.TextField(
            label="Type an objective and press Enter", 
            on_submit=add_objective,
            **input_style
        )

        image_picker_btn =  ft.Container(
                        padding=20, 
                        border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT), 
                        border_radius=8,
                        content=ft.Column([
                            logo_icon,
                            logo_text
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        ink=True, 
                        on_click=handle_logo_pick 
                    )

        error_text = ft.Text("", color=ft.Colors.ERROR, size=12, visible=False)

        def close_modal(e=None):
            modal.open = False
            page.update()
        
        async def submit_course(e):
            if not name_input.value:
                error_text.value = "Course Title is required."
                error_text.visible = True
                page.update()
                return
                
            logo_b64 = None
            if selected_logo_bytes:
                import base64
                logo_b64 = base64.b64encode(selected_logo_bytes).decode('utf-8')
                
            payload = {
                "name": name_input.value,
                "category_id": category_dropdown.value,
                "description": desc_input.value or name_input.value,
                "public": False,
                "objectives": objectives_list,
                "image_bytes": logo_b64,              
                "image_filename": selected_logo_name,
                "org_id": org_id,
                "teacher_id": teacher_dropdown.value or None
            }
            new_course_data = await create_course(token, payload)
            close_modal()
            current_courses.insert(0, new_course_data)
            refresh_grid()

        modal = ft.AlertDialog(
            modal=True,
            bgcolor=ft.Colors.SURFACE, 
            title=ft.Row([
                ft.Text("Create New Course", weight=ft.FontWeight.BOLD),
                ft.IconButton(ft.Icons.CLOSE, on_click=close_modal)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            content=ft.Container(
                width=500,
                height=450,
                content=ft.Column(
                    scroll=ft.ScrollMode.AUTO,
                    spacing=20,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH, # <--- THE FIX: Forces everything to full width
                    controls=[
                        name_input,
                        desc_input,
                        category_dropdown,
                        teacher_dropdown,
                        image_picker_btn,
                        ft.Divider(height=1),
                        ft.Text("Course Objectives", weight=ft.FontWeight.BOLD, size=14),
                        obj_input,
                        objectives_chips,
                        ft.Divider(height=1),
                        error_text
                    ]
                )
            ),
            actions=[
                ft.TextButton("Cancel", on_click=close_modal),
                ft.ElevatedButton("Create Course", bgcolor=ft.Colors.PRIMARY, color=ft.Colors.ON_PRIMARY, on_click=submit_course)
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        page.overlay.append(modal)
        modal.open = True
        page.update()

    # --- BACKGROUND DATA FETCHER ---
    async def fetch_initial_data():
        nonlocal categories_options, theme_color, current_courses, teachers_options
        
        # 1. Await all the data
        categories = await get_categories(token, None) or []
        categories_options = [ft.dropdown.Option(key=cat['id'], text=cat['name']) for cat in categories]
        
        teachers = await get_organisation_members(token, id=org_id, teachers=True) or []
        teachers_options = [ft.dropdown.Option(key=teacher['id'], text=f"{teacher['first_name']} {teacher['last_name']}".capitalize()) for teacher in teachers]
        org_data = await get_my_organisation(token)
        if org_data:
            theme_color = org_data.get("theme_color", ft.Colors.PRIMARY)
            
        current_courses = await get_courses(token, params={'org': org_id}) or []
        
        # 2. Populate the grid now that we have the data
        refresh_grid(initial_load=True)
        
        # 3. Swap out the spinner for the actual Layout
        content_socket.alignment = None
        content_socket.content = ft.Column([
            ft.Container(
                bgcolor=ft.Colors.PRIMARY,
                height=100,
                padding=ft.padding.symmetric(horizontal=20, vertical=15),
                border=ft.border.only(bottom=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
                border_radius=ft.BorderRadius.only(bottom_left=30, bottom_right=30),
                content=ft.Row([
                    ft.Text("Course Library", size=24, weight=ft.FontWeight.BOLD, color="white"),
                    ft.FilledButton(
                        content=ft.Text("New Course", color=ft.Colors.PRIMARY, weight=ft.FontWeight.BOLD),   
                        bgcolor= "white",
                        icon=ft.Icons.ADD, 
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12), color=ft.Colors.PRIMARY, padding=ft.padding.symmetric(horizontal=20, vertical=10)),
                        on_click=open_create_modal
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            ),
            ft.Container(
                expand=True,
                padding=20,
                content=ft.Column([courses_grid], scroll=ft.ScrollMode.AUTO, expand=True)
            )
        ])
        page.update()

    # Trigger the background task
    page.run_task(fetch_initial_data)

    # Return the View immediately with the spinning content_socket
    return ft.View(
        route=f"/organisations/{org_id}/courses" if org_id else "/courses",
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