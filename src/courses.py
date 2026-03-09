import flet as ft
from src.components.course_card import get_course_card
from src.components.bottom_appbar import get_bottom_appbar
from src.requests.Courses import get_courses
async def courses_view(page: ft.Page):
    
    token = await page.shared_preferences.get("auth_token")
    course_list = await get_courses(token)
    course_cards = []
    print(course_cards)
    
    for course in course_list:
        course_name = course.get("name", "Untitled Course")
        course_id = course.get("id")
        card = get_course_card(course_name)
        card.on_click = lambda e, c_id=course_id: page.go(f"/courses/{c_id}")
        card.col = {"xs": 12, "sm": 6}
        course_cards.append(card)

    App_bar = get_bottom_appbar(page)
    course_container=ft.Container(
                        content=ft.ResponsiveRow(
                            spacing=20,          # Horizontal space between cards
                            run_spacing=20,
                            controls=course_cards, # Blank for now
                        ),
                        padding=20)
    
    header_container = ft.Container(
    bgcolor="#009787",

    height=85, 

    border_radius=ft.border_radius.only(bottom_left=30, bottom_right=30),
    padding=ft.padding.only(top=10, left=25, right=25, bottom=20),
    content=ft.Column(
        controls=[
            ft.Text(
                value="What are we learning",
                size=23,
                weight=ft.FontWeight.BOLD,
                color="white",
            ),
             ft.Text(
                value="Today? ",
                size=23,
                color="white",
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
                indicator_color="#009787",
                label_color="#009787",
                unselected_label_color=ft.Colors.BLACK,
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
                    course_container,
                    # Content for My Courses
                    ft.Container(
                        content=ft.Column(
                            controls=[], # Blank for now
                            scroll=ft.ScrollMode.AUTO,
                        ),
                        padding=20,
                    ),
                ],
            ),
        ],
    ),
)
    # 2. Return the View
    return ft.View(
        route="/courses",
        bottom_appbar=App_bar,
        controls=[ft.SafeArea(
            content=ft.Column(controls=[header_container,
            ft.Column(
                controls=[tabs],
                expand=True,
            )]))
        ],
    )