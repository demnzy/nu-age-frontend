import flet as ft
from src.requests.Courses import get_courses
from src.requests.enrollments import get_enrollments, enrol_user

async def course_details_view(page: ft.Page, course_id: str, course_name: str):
    
    # 1. INITIAL LOADING STATE (Centered Shell)
    loading = ft.Container(padding=ft.Padding(top=10),
                content=ft.Row(
                    [ft.ProgressRing(color=ft.Colors.PRIMARY), ft.Text(" Getting Course Details..", color=ft.Colors.ON_SURFACE)],
                    alignment=ft.MainAxisAlignment.CENTER
                )
            )
    print(course_name)
    # Placeholder AppBar (Blank initially or just with a back button)
    initial_app_bar = ft.AppBar(
        bgcolor=ft.Colors.PRIMARY,
        title = ft.Text(course_name, color=ft.Colors.ON_PRIMARY, weight=ft.FontWeight.BOLD),
        leading=ft.IconButton(
            icon=ft.Icons.ARROW_BACK,
            icon_color=ft.Colors.ON_PRIMARY,
            on_click=lambda _: page.go("/courses")
        ),
    )

    async def handle_enrol_click(e):
        token = await page.shared_preferences.get("auth_token")
        if e.control.disabled:
            return
        
        e.control.disabled = True
        # Using ON_PRIMARY for the ring inside the button
        e.control.content = ft.ProgressRing(width=16, height=16, color=ft.Colors.ON_PRIMARY)
        is_enrolling = True
        page.update()
        
        try:
            if is_enrolling:
                status, data = await enrol_user(token, course_id, None)
            else:
                pass # Unenroll logic here
            
            if status == 200:
                page.show_dialog(enroll_success_dialog)
            else:
                e.control.disabled = False
                e.control.text = "Enroll Now" if is_enrolling else "Unenroll"
                page.update()
        except Exception:
            e.control.disabled = False
            page.update()

    # --- DATA LOADING TASK ---
    async def load_course_info(course_id):
        token = await page.shared_preferences.get("auth_token")
        course_data = await get_courses(token, params={"id": course_id})
        
        if not course_data:
            loading.content = ft.Text("Course not found", color=ft.Colors.ERROR)
            page.update()
            return

        course_data = course_data[0]
        course_name = course_data.get("name", "Untitled Course")
        
        # UPDATE THE APP BAR TITLE DYNAMICALLY
        view.appbar.title = ft.Text(course_name, color=ft.Colors.ON_PRIMARY, weight=ft.FontWeight.BOLD)

        enrolled_count = len(course_data.get("Students", []))
        image_url = course_data.get("image_url")
        course_id = course_data.get("id")
        first_name = course_data.get("admin", {}).get("first_name", "Unknown")
        last_name = course_data.get("admin", {}).get("last_name", "Instructor")
        course_author = f'{first_name} {last_name}'
        category = course_data.get("category", {}).get("name")
        course_desc = course_data.get("description", "")
        course_objectives = course_data.get("objectives", [])
        
        enrolled_list = await get_enrollments(token, None)
        enrolled_id = [course.get("id") for course in enrolled_list]
        is_already_enrolled = course_id in enrolled_id
        
        def bullet_item(text: str):
            return ft.Row(
        controls=[
            # The Bullet
            ft.Container(
                width=6,
                height=6,
                bgcolor=ft.Colors.PRIMARY,
                border_radius=3, # Makes it a circle
            ),
            # The Text
            ft.Text(text, size=14, color=ft.Colors.ON_SURFACE, expand=True),
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=10,
    )
        obj_list = ft.Column(controls=[])
        if not course_objectives:
            obj_list.controls.append(bullet_item(f"Gain Knowledge in {course_name} course"))
        else:
            for objective in course_objectives:
                obj_list.controls.append(bullet_item(f'{objective}'))
                
        if image_url:
            image = ft.Image(
                src=image_url,
                fit=ft.BoxFit.COVER,
                width=float("inf"),
                placeholder_fade_out_animation=ft.Animation(900, ft.AnimationCurve.EASE_OUT),
                fade_in_animation=ft.Animation(700, ft.AnimationCurve.EASE_IN_OUT),
            )
        else:
            image = ft.Container(
                bgcolor=ft.Colors.PRIMARY,
                content=ft.Icon(ft.Icons.MENU_BOOK, size=50, color=ft.Colors.ON_PRIMARY),
            )

        enrol_btn = ft.Button(content="Unenroll" if is_already_enrolled else "Enroll Now",
            bgcolor=ft.Colors.ERROR if is_already_enrolled else ft.Colors.PRIMARY,
            color=ft.Colors.ON_PRIMARY,
            height=40,
            on_click=handle_enrol_click,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
        )
        def info_card(title, value):
            return ft.Container(
                padding=15,
                bgcolor=ft.Colors.SURFACE,
                border_radius=10,
                # SET WIDTH TO INFINITY TO FILL SCREEN
                width=float("inf"), 
                content=ft.Column([
                    ft.Text(
                        title, 
                        size=18, 
                        color="black",
                        weight=ft.FontWeight.BOLD,
                    ),
                    value
                ], 
                # Ensure the column doesn't shrink-wrap its content
                horizontal_alignment=ft.CrossAxisAlignment.START,
                expand=True
            ))
            
            
        # REPLACING SPINNER WITH REAL CONTENT
        real_content = ft.Column(controls=[
            ft.Container(
                width=float("inf"),
                height=200,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                margin=ft.margin.only(left=5, right=5, top=10),
                border_radius=14,
                content=image,
            ),
            ft.Container(
                padding=ft.padding.only(left=15, top=10),
                content=ft.Column(controls=[
                    ft.Text(spans=[
                        ft.TextSpan("Author: ", ft.TextStyle(weight="bold", color=ft.Colors.ON_SURFACE)),
                        ft.TextSpan(course_author, ft.TextStyle(color=ft.Colors.ON_SURFACE))
                    ]),
                    ft.Text(spans=[
                        ft.TextSpan("Category: ", ft.TextStyle(weight="bold", color=ft.Colors.ON_SURFACE)),
                        ft.TextSpan(category, ft.TextStyle(color=ft.Colors.ON_SURFACE))
                    ]),
                    ft.Row([
                        ft.Icon(ft.Icons.PERSON_OUTLINE_ROUNDED, color=ft.Colors.PRIMARY, size=20),
                        ft.Text(value=str(enrolled_count), size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], tight=True)
                ])
            ),
            ft.Container(height=20),
            ft.Text("   Course Description", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
            ft.Container(
                padding=ft.padding.only(left=15, right=15),
                content=ft.Text(value=course_desc, size=14, color=ft.Colors.ON_SURFACE),

            ),
            ft.Container(height=20),
            info_card("What you will learn:",obj_list),
            ft.Container(
                padding=20,
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.END,
                    controls=[enrol_btn]
                )
            )
        ])

        loading.content = real_content
        page.update()
        
    enroll_success_dialog = ft.AlertDialog(
        title=ft.Row(
            controls=[
                ft.Text("Enrollment Successful!"), 
                ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, color=ft.Colors.PRIMARY)
            ],
            tight=True,
            spacing=10
        ),
        content=ft.Text("You have successfully joined the course."),
        actions=[
            ft.TextButton(
                "Ok", 
                on_click=lambda e: page.go("/courses"), 
                style=ft.ButtonStyle(color=ft.Colors.PRIMARY)
            )
        ],
    )    

    # TRIGGER THE TASK
    page.run_task(load_course_info, course_id)

    # THE VIEW
    view = ft.View(
        route=f"/courses/{course_id}",
        padding=0,
        bgcolor=ft.Colors.SURFACE,
        appbar=initial_app_bar,
        scroll=ft.ScrollMode.ALWAYS,
        controls=[loading
        ]
    )
    return view