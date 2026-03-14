import flet as ft
from src.requests.Courses import get_courses
from src.requests.enrollments import get_enrollments, enrol_user

async def course_details_view(page: ft.Page, course_id: str):
    token = await page.shared_preferences.get("auth_token")
    course_data = await get_courses(token, params={"id":course_id})
    course_data = course_data[0]
    
    course_name = course_data.get("name", "Untitled Course")
    enrolled_count = len(course_data.get("Students", []))
    image_url = course_data.get("image_url")
    course_id = course_data.get("id")
    first_name = course_data.get("admin", {}).get("first_name","Unknown")
    last_name = course_data.get("admin", {}).get("last_name","Instructor")
    course_author = f'{first_name} {last_name}'
    category = course_data.get("category",{}).get("name")
    course_desc = course_data.get("description", "")
    
    enrolled_list = await get_enrollments(token, None)
    enrolled_id = [course.get("id") for course in enrolled_list]
    is_already_enrolled = course_id in enrolled_id

    # --- HANDLER DEFINITION ---
    async def handle_enrol_click(e):
        if e.control.disabled:
            return
        
        e.control.disabled = True
        # Logic check based on current text
        is_enrolling = e.control.content == "Enroll Now"
        page.update()
        
        try:
            if is_enrolling:
                status, data = await enrol_user(token, course_id, None)
                print(status)
            else:
                # Placeholder for unenroll logic
                pass
            
            if status == 200:
                print("I was successful")
                page.show_dialog(enroll_success_dialog)# Refresh view
            else:
                e.control.disabled = False
                e.control.content = "Enroll Now" if is_enrolling else "Unenroll"
                page.update()
        except Exception:
            e.control.disabled = False
            page.update()

    # --- IMAGE SETUP ---
    if image_url:
        image = ft.Image(
            src=image_url,
            fit=ft.BoxFit.COVER,
            width=float("inf"),
            placeholder_src="/placeholder.png",
            placeholder_fit=ft.BoxFit.COVER,
            placeholder_fade_out_animation=ft.Animation(900, ft.AnimationCurve.EASE_OUT),
            fade_in_animation=ft.Animation(700, ft.AnimationCurve.EASE_IN_OUT),
        )
    else:
        image = ft.Container(
            bgcolor="#009787",
            border_radius=ft.BorderRadius.only(top_left=10, top_right=10),
            content=ft.Icon(ft.Icons.MENU_BOOK, size=50, color="white"),
        )
        
    enroll_success_dialog = ft.AlertDialog(
        title=ft.Row(
            controls=[
                ft.Text("Enrollment Successful!", size=20, weight=ft.FontWeight.BOLD), 
                ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, color="#009787")
            ],
            tight=True,
            spacing=10
        ),
        content=ft.Text("You have successfully joined the course. You can now access all learning materials.", size=14),
        actions=[
            ft.TextButton(
                "Ok", 
                on_click=lambda e: page.go("/courses"), 
                style=ft.ButtonStyle(color="#009787")
            )
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )    
    # --- BUTTON SETUP ---
    enrol_btn = ft.Button(
        content="Unenroll" if is_already_enrolled else "Enroll Now",
        bgcolor="#F30909" if is_already_enrolled else "#009787",
        color=ft.Colors.WHITE,
        height=40,
        width=120,
        on_click=handle_enrol_click,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
    )

    return ft.View(
        route=f"/courses/{course_id}",
        padding=0,
        controls=[
            ft.AppBar(
                leading=ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    icon_color=ft.Colors.WHITE,
                    on_click=lambda _: page.go("/courses")
                ),
                title=ft.Text(course_name, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                bgcolor="#009787",
            ),
            ft.Column(
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    ft.Container(
                        width=float("inf"),
                        height=200,
                        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                        margin=ft.margin.only(left=5, right=5),
                        border_radius=14,
                        content=image,
                    ),
                    ft.Container(height=10),
                    ft.Container(
                        padding=ft.padding.only(left=15),
                        content=ft.Column(controls=[
                            ft.Text(spans=[
                                ft.TextSpan("Author: ", ft.TextStyle(weight="bold", color="black")),
                                ft.TextSpan(course_author, ft.TextStyle(color="black"))
                            ]),
                            ft.Text(spans=[
                                ft.TextSpan("Category: ", ft.TextStyle(weight="bold", color="black")),
                                ft.TextSpan(category, ft.TextStyle(color="black"))
                            ]),
                            ft.Container(
                                content=ft.Row([
                                    ft.Icon(ft.Icons.PERSON_OUTLINE_ROUNDED, color="#009787", size=20),
                                    ft.Text(value=str(enrolled_count), size=14, color=ft.Colors.BLACK_54),
                                ], tight=True)
                            )
                        ])
                    ),
                    ft.Container(height=20),
                    ft.Text("   Course Description", size=18, weight=ft.FontWeight.BOLD),
                    ft.ResponsiveRow(
                        controls=[
                            ft.Container(
                                col={"xs": 12},
                                padding=ft.padding.only(left=15, right=15),
                                content=ft.Text(value=course_desc, size=14, color=ft.Colors.BLACK_87)
                            )
                        ]
                    ),
                    ft.Container(
                        padding=20,
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.END,
                            controls=[enrol_btn]
                        )
                    )
                ]
            )
        ]
    )