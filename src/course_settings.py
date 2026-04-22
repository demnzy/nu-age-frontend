import flet as ft
import asyncio

from src.components.bottom_appbar import get_bottom_appbar 
from src.requests.Courses import get_categories,get_courses,update_course_settings,delete_course
from src.requests.organisations import get_organisation_members
from src.requests.enrollments import bulk_enrol_students, bulk_unenrol_students,get_enrolled_students

# =========================================================
# SECTION 1: API ENDPOINTS (Replace with real imports)
# =========================================================



# =========================================================
# SECTION 2: MAIN VIEW FUNCTION
# =========================================================
async def course_settings_view(page: ft.Page, course_id: str, org_id: str) -> ft.View:
    token = await page.shared_preferences.get("auth_token")
    
    async def mock_get_categories():
        categories = await get_categories(token, None) or []
        return categories

    async def mock_get_teachers():
        teachers = await get_organisation_members(token, id=org_id, teachers=True) or []
        return teachers
    
    async def mock_get_org_students():
        students = await get_organisation_members(token, id=org_id, students=True) or []
        return students

    async def mock_save_setting(setting_name, value):
        res= await update_course_settings(token, course_id, {setting_name: value})
        print(res)
        return True if res else False

    async def mock_enroll_students(student_ids):
        await bulk_enrol_students(token, course_id, payload = {"student_ids": student_ids}, params = {})
        return True, f"Enrolled {len(student_ids)}"

    async def mock_unenroll_students(student_ids):
        await bulk_unenrol_students(token, course_id, payload = {"student_ids": student_ids}, params={})
        return True, f"Unenrolled {len(student_ids)}"

    course_data = course_data = await get_courses(token, params={"id": course_id})
    course_data = course_data[0] if course_data else None
    if not course_data:
        return ft.View(
            route=f"/courses/{course_id}/settings",
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            controls=[
                ft.Container(
                    expand=True,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text("Course not found.", color=ft.Colors.ERROR, size=20)
                )
            ]
        )
            # --- 2A. Theme & Initialization ---
    NU_DARK = ft.Colors.PRIMARY
    bottom_bar = get_bottom_appbar(page)

    # --- 2B. The Lazy Load Socket ---
    content_socket = ft.Container(
        expand=True, 
        alignment=ft.Alignment.CENTER, 
        content=ft.ProgressRing(color=NU_DARK)
    )

    # --- 2C. Shared UI Helpers ---
    def show_toast(message, color=ft.Colors.GREEN_700):
        page.snack_bar = ft.SnackBar(content=ft.Text(message), bgcolor=color, duration=3000)
        page.snack_bar.open = True
        page.update()

    def create_section(title: str, description: str, content: ft.Control, is_danger=False):
        return ft.Container(
            bgcolor=ft.Colors.SURFACE,
            border_radius=15,
            padding=20,
            border=ft.border.all(1, ft.Colors.RED_200 if is_danger else ft.Colors.OUTLINE_VARIANT),
            content=ft.Column(
                spacing=15,
                controls=[
                    ft.Column(
                        spacing=4,
                        controls=[
                            ft.Text(title, size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_700 if is_danger else ft.Colors.ON_SURFACE),
                            ft.Text(description, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                        ]
                    ),
                    ft.Divider(height=10, color=ft.Colors.OUTLINE_VARIANT),
                    content
                ]
            )
        )

    # Shared Input Style
    input_style = {"border_color": ft.Colors.OUTLINE_VARIANT, "focused_border_color": NU_DARK, "border_radius": 8}


    # =========================================================
    # SECTION 3: GENERAL SETTINGS
    # =========================================================
    name_input = ft.TextField(value=course_data["name"], label="Course Name", expand=True, **input_style)
    category_dropdown = ft.Dropdown(label="Category", value=course_data["category"]["name"], expand=True, **input_style)

    async def save_name(e):
        e.control.disabled = True
        e.control.content = ft.ProgressRing(width=16, height=16, color=ft.Colors.ON_PRIMARY)
        page.update()
        await mock_save_setting("name", name_input.value)
        show_toast("Course name updated.")
        e.control.disabled = False
        e.control.content = ft.Text("Save", color=ft.Colors.ON_PRIMARY, weight=ft.FontWeight.BOLD)
        page.update()

    async def save_category(e):
        e.control.disabled = True
        e.control.content = ft.ProgressRing(width=16, height=16, color=ft.Colors.ON_PRIMARY)
        page.update()
        await mock_save_setting("category", category_dropdown.value)
        show_toast("Course category updated.")
        e.control.disabled = False
        e.control.content = ft.Text("Save", color=ft.Colors.ON_PRIMARY, weight=ft.FontWeight.BOLD)
        page.update()

    general_section = create_section(
        title="General Information",
        description="Update the foundational details of this curriculum.",
        content=ft.Column(
            spacing=15,
            controls=[
                ft.Row([name_input, ft.ElevatedButton(content=ft.Text("Save", color=ft.Colors.ON_PRIMARY, weight=ft.FontWeight.BOLD), bgcolor=NU_DARK, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)), on_click=lambda e: page.run_task(save_name, e))]),
                ft.Row([category_dropdown, ft.ElevatedButton(content=ft.Text("Save", color=ft.Colors.ON_PRIMARY, weight=ft.FontWeight.BOLD), bgcolor=NU_DARK, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)), on_click=lambda e: page.run_task(save_category, e))]),
            ]
        )
    )


    # =========================================================
    # SECTION 4: ACCESS CONTROLS
    # =========================================================
    public_radio = ft.RadioGroup(
        value=course_data["public"],
        content=ft.Row([
            ft.Radio(value=False, label="Private", fill_color=NU_DARK), 
            ft.Radio(value="organization", label="Organization", fill_color=NU_DARK),
            ft.Radio(value=True, label="Public", fill_color=NU_DARK),
        ], wrap=True)
    )
    
    teacher_dropdown = ft.Dropdown(label="Assigned Instructor", value=course_data["teacher_id"], expand=True, **input_style)

    async def save_public(e):
        e.control.disabled = True
        e.control.content = ft.ProgressRing(width=16, height=16, color=ft.Colors.ON_PRIMARY)
        page.update()
        await mock_save_setting("public", public_radio.value)
        show_toast("status updated.")
        e.control.disabled = False
        e.control.content = ft.Text("Save", color=ft.Colors.ON_PRIMARY, weight=ft.FontWeight.BOLD)
        page.update()

    async def save_teacher(e):
        e.control.disabled = True
        e.control.content = ft.ProgressRing(width=16, height=16, color=ft.Colors.ON_PRIMARY)
        page.update()
        await mock_save_setting("teacher_id", teacher_dropdown.value)
        show_toast("Instructor reassigned.")
        e.control.disabled = False
        e.control.content = ft.Text("Save", color=ft.Colors.ON_PRIMARY, weight=ft.FontWeight.BOLD)
        page.update()

    access_section = create_section(
        title="Access & Instructors",
        description="Control who can view this course and who is managing it.",
        content=ft.Column(
            spacing=20,
            controls=[
                ft.Row([
                    ft.Column([ft.Text("Course public", weight=ft.FontWeight.W_600), public_radio], expand=True),
                    ft.ElevatedButton(content=ft.Text("Save", color=ft.Colors.ON_PRIMARY, weight=ft.FontWeight.BOLD), bgcolor=NU_DARK, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)), on_click=lambda e: page.run_task(save_public, e))
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                
                ft.Row([
                    teacher_dropdown,
                    ft.ElevatedButton(content=ft.Text("Save", color=ft.Colors.ON_PRIMARY, weight=ft.FontWeight.BOLD), bgcolor=NU_DARK, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)), on_click=lambda e: page.run_task(save_teacher, e))
                ])
            ]
        )
    )


    # =========================================================
    # SECTION 5: ENROLLMENT MANAGER
    # =========================================================
    def open_enrollment_manager(e):
        enrollment_list_view = ft.ListView(spacing=5, expand=True)
        student_checkboxes = {} 
        initial_states = {} 
        
        def toggle_all(e):
            for cb in student_checkboxes.values():
                cb.value = master_checkbox.value
            page.update()
            
        master_checkbox = ft.Checkbox(
            label="Select / Deselect All", 
            fill_color={"selected": NU_DARK, "": ft.Colors.WHITE},
            check_color=ft.Colors.WHITE,
            on_change=toggle_all
        )
        
        action_btn = ft.ElevatedButton("Save Changes", bgcolor=NU_DARK, color=ft.Colors.WHITE, disabled=True)
        loading_ring = ft.Container(content=ft.ProgressRing(color=NU_DARK), alignment=ft.Alignment.CENTER, expand=True, padding=20)
        content_wrapper = ft.Column([master_checkbox, ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT), enrollment_list_view], expand=True, visible=False)

        def close_modal(e=None):
            dlg.open = False
            page.update()

        async def execute_enrollment(e):
            e.control.disabled = True
            e.control.text = "Saving..."
            page.update()
            
            to_enroll = []
            to_unenroll = []
            
            for s_id, cb in student_checkboxes.items():
                was_enrolled = initial_states[s_id]
                is_enrolled_now = cb.value
                
                if is_enrolled_now and not was_enrolled:
                    to_enroll.append(s_id)
                elif not is_enrolled_now and was_enrolled:
                    to_unenroll.append(s_id)
            
            msgs = []
            if to_enroll:
                success, msg = await mock_enroll_students(to_enroll)
                if success: msgs.append(f"Added {len(to_enroll)}")
            if to_unenroll:
                success, msg = await mock_unenroll_students(to_unenroll)
                if success: msgs.append(f"Removed {len(to_unenroll)}")
                
            if not to_enroll and not to_unenroll:
                msgs.append("No changes made.")
                
            show_toast(" | ".join(msgs))
            close_modal()

        dlg = ft.AlertDialog(
            modal=True,
            bgcolor=ft.Colors.SURFACE,
            title=ft.Row([
                ft.Text("Manage Enrollments", weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE, size=18, expand=True),
                ft.IconButton(ft.Icons.CLOSE, on_click=close_modal)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            content=ft.Container(
                width=340, 
                height=400, 
                content=ft.Column([loading_ring, content_wrapper], expand=True)
            ),
            actions=[ft.TextButton("Cancel", on_click=close_modal), action_btn],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        page.overlay.append(dlg)
        dlg.open = True
        page.update()
        
        async def fetch_and_populate():
            students = await get_enrolled_students(token, course_id, params={})
            
            loading_ring.visible = False 
            content_wrapper.visible = True 
            print(students)
            for student in students:
                is_enrolled = student.get("is_enrolled", False)
                initial_states[student['id']] = is_enrolled
                
                # Checkbox explicit state styling
                cb = ft.Checkbox(
                    value=is_enrolled, 
                    fill_color={"selected": NU_DARK, "": ft.Colors.WHITE},
                    check_color=ft.Colors.WHITE
                )
                student_checkboxes[student['id']] = cb
                
                student_row = ft.Container(
                    padding=ft.padding.symmetric(vertical=4),
                    content=ft.Row([
                        cb,
                        ft.Column([
                            ft.Text(f'{student["name"]}', size=14, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                            ft.Text(student['email'], size=12, color=ft.Colors.ON_SURFACE_VARIANT)
                        ], expand=True, spacing=2) 
                    ])
                )
                enrollment_list_view.controls.append(student_row)
                
            action_btn.disabled = False
            action_btn.on_click = execute_enrollment
            page.update()

        page.run_task(fetch_and_populate)

    enrollment_section = create_section(
        title="Student Enrollments",
        description="Manually batch enroll or remove students from your organization.",
        content=ft.ElevatedButton(
            "Open Enrollment Manager", 
            width=float("inf"),
            icon=ft.Icons.PEOPLE_ALT_ROUNDED,
            icon_color=ft.Colors.ON_SURFACE,
            color=ft.Colors.ON_SURFACE,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            on_click=open_enrollment_manager 
        )
    )


    # =========================================================
    # SECTION 6: DANGER ZONE
    # =========================================================
    def open_delete_modal(e):
        def close_delete_modal(e=None):
            dlg_delete.open = False
            page.update()

        async def confirm_delete(e):
            res=await delete_course(token, course_id)
            print(res)
            close_delete_modal()
            show_toast("Course deleted successfully.", ft.Colors.RED_700)
            page.go("/organisations")

        dlg_delete = ft.AlertDialog(
            modal=True,
            bgcolor=ft.Colors.SURFACE,
            title=ft.Row([
                ft.Text("Delete Course", color=ft.Colors.RED_700, weight=ft.FontWeight.BOLD, expand=True),
                ft.IconButton(ft.Icons.CLOSE, on_click=close_delete_modal)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            content=ft.Container(
                width=340,
                content=ft.Text("Are you absolutely sure? This action cannot be undone and all associated question banks and modules will be wiped.", color=ft.Colors.ON_SURFACE)
            ),
            actions=[
                ft.TextButton("Cancel", on_click=close_delete_modal),
                ft.ElevatedButton("Yes, Delete Everything", bgcolor=ft.Colors.RED_700, color=ft.Colors.WHITE, on_click=confirm_delete)
            ]
        )
        page.overlay.append(dlg_delete)
        dlg_delete.open = True
        page.update()

    danger_section = create_section(
        title="Danger Zone",
        description="Irreversible actions regarding this course.",
        is_danger=True,
        content=ft.Button("Delete Course", bgcolor=ft.Colors.RED_50, color=ft.Colors.RED_700, width=float("inf"), style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)), on_click=open_delete_modal)
    )


    # =========================================================
    # SECTION 7: DATA FETCH & LAYOUT ASSEMBLY
    # =========================================================
    async def load_initial_data():
        # Fetch options
        categories = await mock_get_categories()
        teachers = await mock_get_teachers()
        
        category_dropdown.options = [ft.dropdown.Option(c["name"]) for c in categories]
        teacher_dropdown.options = [ft.dropdown.Option(key=t["id"], text=f"{t['first_name']} {t['last_name']}".capitalize()) for t in teachers]
        teacher_dropdown.options.insert(0, ft.dropdown.Option(key="none", text="None (Unassigned)"))
        
        # Build the final layout
        header_container = ft.Container(
            bgcolor=NU_DARK,
            height=85, # Reduced height
            border_radius=ft.BorderRadius.only(bottom_left=30, bottom_right=30),
            padding=ft.Padding(top=10, left=15, right=25, bottom=15),
            content=ft.Row([
                ft.IconButton(ft.Icons.ARROW_BACK_ROUNDED, icon_color=ft.Colors.WHITE, on_click=lambda _: page.go("/organisations")),
                ft.Text("Course Settings", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ft.Container(width=40) 
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        )

        final_layout = ft.Column(
            expand=True,
            spacing=0,
            controls=[
                header_container,
                ft.Container(
                    expand=True,
                    padding=20,
                    content=ft.Column(
                        scroll=ft.ScrollMode.AUTO,
                        spacing=25,
                        controls=[
                            general_section,
                            access_section,
                            enrollment_section,
                            danger_section,
                            ft.Container(height=20) 
                        ]
                    )
                )
            ]
        )

        # Hot-swap the loading socket with the real UI
        content_socket.alignment = None
        content_socket.content = final_layout
        page.update()

    # Trigger background load
    page.run_task(load_initial_data)

    # Return the View immediately with the spinning content_socket
    return ft.View(
        route=f"/organisations/{org_id}/courses/{course_id}/settings",
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        padding=0, 
        bottom_appbar=bottom_bar, 
        controls=[
            ft.SafeArea(
                expand=True,
                content=content_socket
            )
        ]
    )