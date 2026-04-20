import flet as ft
from src import course_view
from src.components.course_card import get_course_card
from src.components.enrolled_card import get_enrolled_card
from src.components.bottom_appbar import get_bottom_appbar
from src.requests.Courses import get_courses
from src.requests.enrollments import get_enrollments, enrol_user
from datetime import datetime
async def courses_view(page: ft.Page):
    course_cards = []
    enroll_cards = []

    async def clear_search(e):
        if e.control.value == "":
            await handle_change(e)
        else:
            pass
        
    async def handle_enrol_click(e,course_id:str):
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
                e.control.content= ft.Text("Fetching Course Contents...")
                page.update()
                page.go(f"/courses/{course_id}/view")
            else:
                e.control.disabled = False
                e.control.content = ft.Text("Enroll") 
                page.update()
        except Exception:
            e.control.disabled = False
            page.update()
        
            
    async def handle_change(e):
        new_token = await page.shared_preferences.get("auth_token")
        course_list = await get_courses(new_token, params={"name": e.control.value, "is_public": True})
        if isinstance(course_list, list): 
            course_cards.clear()
            for course in course_list:
                course_name = course.get("name", "Untitled Course")
                first_name = course.get("admin", {}).get("first_name","Unknown")
                last_name = course.get("admin", {}).get("last_name","Instructor")
                full_name = f'{first_name} {last_name}'
                category = course.get("category",{}).get("name")
                image_url = course.get("image_url",None)
                course_id = course.get("id")
                created_at = course.get("created_at","")
                created_at = datetime.fromisoformat(created_at)
                # 2. Format to Day/Month/Year
                created_at = created_at.strftime("%d/%m/%Y")
                card = get_course_card(course_name,category,full_name, image_url,created_at)
                card.on_click = lambda e, c_id=course_id: page.go(f"/courses/{c_id}")
                card.col = {"xs": 12, "sm": 6}
                course_cards.append(card)
            course_container.content.controls = course_cards if course_cards else ft.Container(
                        padding=40,
                        content=ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(ft.Icons.SEARCH_OFF_ROUNDED, size=50, color=ft.Colors.BLACK_12),
                                ft.Text(
                                    "Try a different Search",
                                    size=16,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                    weight=ft.FontWeight.W_500,
                                    text_align=ft.TextAlign.CENTER
                                )]))
            page.update()
            if isinstance(course_container.content.controls, list):
                for card in course_container.content.controls :
                    card.offset = ft.Offset(0, 0) # Move to original position
                    card.opacity = 1
        else:
            pass
        page.update()

    # 2. The UI Control
    search_anchor = ft.SearchBar(
        bar_bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, # Themed equivalent of White
        bar_hint_text="Search courses or categories...",
        bar_leading=ft.Icon(ft.Icons.SEARCH, color=ft.Colors.PRIMARY), # Themed equivalent of #009787
        
        # Style the dropdown view to match Nu-age
        view_bgcolor=ft.Colors.SURFACE,
        view_hint_text="Type to find a course...",
        
        # Behavior
        on_submit=handle_change,
        on_change=clear_search,
    
        # UI Polish
        bar_elevation=1,
        bar_padding=ft.Padding(left=15, right=15, top=0, bottom=0),
        expand=True
    )
    App_bar = get_bottom_appbar(page)
    course_container=ft.Container(
                        content=ft.ResponsiveRow(
                            spacing=20,          # Horizontal space between cards
                            run_spacing=20,
                            controls=course_cards, # Blank for now
                        ),
                        padding=20)
    enroll_container=ft.Container(
                        content=ft.ResponsiveRow(
                            spacing=20,          # Horizontal space between cards
                            run_spacing=20,
                            controls=enroll_cards, # Blank for now
                        ),
                        padding=20)
    header_container = ft.Container(
    bgcolor=ft.Colors.PRIMARY, # Themed equivalent of #009787

    height=85, 

    border_radius=ft.border_radius.only(bottom_left=30, bottom_right=30),
    padding=ft.padding.only(top=10, left=25, right=25, bottom=20),
    content=ft.Column(
        controls=[
            ft.Text(
                value="What are we learning",
                size=23,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.ON_PRIMARY, # Themed equivalent of white on primary
            ),
             ft.Text(
                value="Today? ",
                size=23,
                color=ft.Colors.ON_PRIMARY, # Themed equivalent of white on primary
                weight=ft.FontWeight.BOLD,
                )
        ],
        spacing=2,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    ),
)
    tabs = ft.Tabs(
        selected_index=0,
        length=2,
        expand=True,
        content=ft.Column(
            expand=True,
            controls=[
                ft.TabBar(
                    indicator_color=ft.Colors.PRIMARY, # Themed equivalent of #009787
                    label_color=ft.Colors.PRIMARY, # Themed equivalent of #009787
                    unselected_label_color=ft.Colors.ON_SURFACE_VARIANT,
                    # This ensures the tabs are equally spaced across the screen
                    tab_alignment=ft.TabAlignment.CENTER,
                    tabs=[
                        ft.Tab(label="Available Courses"),
                        ft.Tab(label="My Courses"),
                    ]
                ),
                ft.TabBarView(
                    expand=True,
                    controls=[
                        ft.Container(
                            expand=True,
                            padding=20,
                            content=ft.Column(
                                expand=True,
                                controls=[
                        # A: STATIC SEARCH SECTION
                        ft.Container(
                            content=ft.Row([search_anchor]),
                            # No expand=True here, we want it to stay at its natural height
                        ),
                        
                        # B: SCROLLABLE SECTION
                        ft.ListView(
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    # Check if we actually have cards to show
                    ft.Container(
                content=ft.Row(
                    [ft.ProgressRing(color=ft.Colors.PRIMARY), ft.Text(" Getting available courses...", color=ft.Colors.ON_SURFACE)],
                    alignment=ft.MainAxisAlignment.CENTER
                ),
                height=200,
            )
                ],
            )
                    ]
                )
            ),
                        ft.Container(
                            content=ft.Column(
                                alignment=ft.MainAxisAlignment.CENTER, # Center loading ring
                                controls=[
                                    ft.Container(
                content=ft.Row(
                    [ft.ProgressRing(color=ft.Colors.PRIMARY), ft.Text(" Fetching your courses...", color=ft.Colors.ON_SURFACE)],
                    alignment=ft.MainAxisAlignment.CENTER
                ),
                height=200,
            )
                                    # Replace this with your 'my_courses_container' later
                                ], 
                                scroll=ft.ScrollMode.AUTO,
                                expand=True
                            ),
                            padding=20,
                        )
                    ],
                ),
            ],
        ),
    )
    async def populate_tabs():
        token = await page.shared_preferences.get("auth_token")
        course_list = await get_courses(token, {"is_public": True})
        enrolled_list = await get_enrollments(token,None)
        enrolled_ids = {course.get("id") for course in enrolled_list}

        for course in course_list:
            course_name = course.get("name", "Untitled Course")
            image_url = course.get("image_url", "")
            course_id = course.get("id")
            if course_id not in enrolled_ids: 
                first_name = course.get("admin", {}).get("first_name","Unknown")
                last_name = course.get("admin", {}).get("last_name","Instructor")
                full_name = f'{first_name} {last_name}'
                category = course.get("category",{}).get("name")
                created_at = course.get("created_at","")
                created_at = datetime.fromisoformat(created_at)
                # 2. Format to Day/Month/Year
                created_at = created_at.strftime("%d/%m/%Y")
                card = get_course_card(course_name,category,full_name,image_url,created_at,on_enroll_click=lambda e, c_id=course_id: e.page.run_task(handle_enrol_click, e, c_id))
                card.on_click = lambda e, c_id=course_id, c_name=course_name: page.go(f"/courses/{c_id}/{c_name}")
                card.col = {"xs": 12, "sm": 6}
                course_cards.append(card)
                card.opacity = 1
                card.offset = ft.Offset(0, 0)
        if isinstance(enrolled_list, list):  
            for course in enrolled_list:
                course_name = course.get("name", "Untitled Course")
                image_url = course.get("image_url", "")
                progress = course.get("progress", 0.0)
                course_id = course.get("id")
                first_name = course.get("admin", {}).get("first_name","Unknown")
                last_name = course.get("admin", {}).get("last_name","Instructor")
                full_name = f'{first_name} {last_name}'
                category = course.get("category",{}).get("name")
                card = get_enrolled_card(course_name,category,full_name,image_url,progress)
                card.on_click = lambda e, c_id=course_id,c_name=course_name: page.go(f"/courses/{c_id}/view")
                card.col = {"xs": 12, "sm": 6}
                enroll_cards.append(card)
                card.opacity = 1
                card.offset = ft.Offset(0, 0)
        else:
            print(enrolled_list)
            enrolled_list.clear()
        real_content = ft.Column(
            expand=True,
            controls=[
                ft.TabBar(
                    indicator_color=ft.Colors.PRIMARY,
                    label_color=ft.Colors.PRIMARY,
                    unselected_label_color=ft.Colors.ON_SURFACE_VARIANT,
                    # This ensures the tabs are equally spaced across the screen
                    tab_alignment=ft.TabAlignment.CENTER,
                    tabs=[
                        ft.Tab(label="Available Courses"),
                        ft.Tab(label="My Courses"),
                    ]
                ),
                ft.TabBarView(
                    expand=True,
                    controls=[
                        ft.Container(
                            expand=True,
                            padding=20,
                            content=ft.Column(
                                expand=True,
                                controls=[
                        # A: STATIC SEARCH SECTION
                        ft.Container(
                            content=ft.Row([search_anchor]),
                            # No expand=True here, we want it to stay at its natural height
                        ),
                        
                        # B: SCROLLABLE SECTION
                        ft.ListView(
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    # Check if we actually have cards to show
                    course_container if course_cards else ft.Container(
                        padding=40,
                        content=ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(ft.Icons.SEARCH_OFF_ROUNDED, size=50, color=ft.Colors.BLACK_12),
                                ft.Text(
                                    "No available courses found",
                                    size=16,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                    weight=ft.FontWeight.W_500,
                                    text_align=ft.TextAlign.CENTER
                                ),
                            ]
                        )
                    )
                ],
            )
                    ]
                )
            ),
                        ft.Container(
                            content=ft.Column(
                                controls=[
                                    ft.ListView(
                        expand=True, # THIS IS VITAL - it fills the remaining space
                        controls=[
                # Ternary: [RESULT_IF_TRUE] if [CONDITION] else [RESULT_IF_FALSE]
                enroll_container if enrolled_list else ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        ft.Text(
                            "You have no enrolled courses", 
                            size=16, 
                            color=ft.Colors.ON_SURFACE_VARIANT,
                            weight=ft.FontWeight.W_500
                        )
                    ]
                )
            ],
                        scroll=ft.ScrollMode.AUTO,
                    )
                                    # Replace this with your 'my_courses_container' later
                                ], 
                                scroll=ft.ScrollMode.AUTO,
                                expand=True
                            ),
                            padding=20,
                        )
                    ],
                ),
            ],
        )
        tabs.content = real_content
        page.update()
        
    # 2. Return the View
    page.run_task(populate_tabs)
    return ft.View(
        route="/courses",
        bottom_appbar=App_bar,
        # 1. Important: Ensure the view padding doesn't interfere
        padding=0, 

        controls=[
            ft.SafeArea(
                # 2. This Column must fill the screen height
                expand=True, 
                content=ft.Column(
                    expand=True, # 3. Force this to be exactly the screen height
                    spacing=0,
                    controls=[
                        header_container,
                        # 4. Wrap tabs in a container that takes the REMAINING space
                        ft.Container(
                            content=tabs,
                            expand=True, # This is the "Wall" for the scrollbar
                        )
                    ]
                )
            )
        ],
    )