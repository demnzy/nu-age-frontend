import flet as ft
import flet_charts as fch # pyright: ignore[reportMissingImports]
from src.components.bottom_appbar import get_bottom_appbar
from src.components.dashboard_card import get_continue_learning_card
from src.requests.enrollments import get_enrollments

async def dashboard_view(page: ft.Page):
    app_bar = get_bottom_appbar(page)
    enrolled_cards=[]
    # Use ON_PRIMARY because this text sits on the Teal header
    name = ft.Text(value="Hello, User!", size=23, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_PRIMARY)
    continue_learning_section = ft.Column()
    activity_data = [0, 0, 0, 0, 0, 0, 0] 
    
    # The "Socket" for the optimistic UI
    chart_holder = ft.Container(
        content=ft.Row(
            [
                ft.ProgressRing(color=ft.Colors.PRIMARY), 
                ft.Text(" Syncing activity...", color=ft.Colors.ON_SURFACE_VARIANT)
            ],
            alignment=ft.MainAxisAlignment.CENTER
        ),
        height=200,
    )

    # --- 2. HEADER SECTION ---
    header_container = ft.Container(
        bgcolor=ft.Colors.PRIMARY, # Dynamic Teal
        height=85, 
        border_radius=ft.BorderRadius.only(bottom_left=30, bottom_right=30),
        padding=ft.Padding(top=10, left=25, right=25, bottom=20),
        content=ft.Column(
            controls=[
                name,
                ft.Text(value="Welcome back to your dashboard", size=13, color=ft.Colors.ON_PRIMARY),
            ],
            spacing=5,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
    )

    # --- 3. ACTIVITY CHART CONTAINER ---
    activity_chart = ft.Container(
        padding=15,
        bgcolor=ft.Colors.SURFACE, # Adapts White <-> Charcoal
        border_radius=20,
        width=950, # Changed to None for better responsiveness
        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
        content=ft.Column(
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text("Weekly Activity", weight="bold", size=16, color="black"),
                        ft.Icon(ft.Icons.ANALYTICS_OUTLINED, color=ft.Colors.PRIMARY, size=20),
                    ]
                ),
                chart_holder 
            ],
            spacing=6,
        ),
    )
    no_courses= ft.Text("You have no enrolled courses")
    # --- 4. NAVIGATION PILL ---
    goto_course = ft.Container(
        bgcolor=ft.Colors.SURFACE,
        border_radius=30, 
        padding=ft.Padding(left=20, right=5, top=5, bottom=5),
        margin=ft.Margin(left=10, right=10, top=0, bottom=0),
        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT), 
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Text("Available Courses", size=16, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE),
                ft.IconButton(
                    icon=ft.Icons.ARROW_FORWARD_ROUNDED,
                    icon_color=ft.Colors.ON_PRIMARY,
                    bgcolor=ft.Colors.PRIMARY,
                    icon_size=20,
                    style=ft.ButtonStyle(shape=ft.CircleBorder(), padding=10),
                    on_click=lambda e: page.go('/courses')
                ),
            ],
        ),
    )

    # --- 5. BACKGROUND DATA TASK ---
    async def fetch_activity_stats():
        user_data = page.session.store.get("current_user")
        first_name = user_data.get("first_name", "User") 
        first_name = f'{first_name}! ' if first_name else "User!"
        name.value = f"Hello, {first_name}"
        
        token = await page.shared_preferences.get("auth_token")
        enrolled_list = await get_enrollments(token, None)
        
        enrolled_cards.clear() # Clear existing to avoid duplicates on re-sync
        for course in enrolled_list:
            course_name = course.get("name", "Untitled Course")
            progress = course.get("progress", 0.0)
            course_id = course.get("id")
            
            card = get_continue_learning_card(course_name, progress, course_id, page)
            # Correctly latched lambda
            card.on_click = lambda e, c_id=course_id: page.go(f"/courses/{c_id}/view")
            enrolled_cards.append(card)

        # FIX: Clear and update the section
        continue_learning_section.controls.clear()
        continue_learning_section.controls.append(
        ft.Container(
        padding=ft.padding.only(left=20, right=20, top=10, bottom=10),
        content=ft.Column([
            # Section Header
            ft.Row([
                ft.Text("Get Back to Learning", size=18, weight="bold", color=ft.Colors.ON_SURFACE),
                ft.TextButton("View All", on_click=lambda _: page.go("/courses"))
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            
            # The Horizontal Scroll Engine
            ft.Row(
                # Use HIDDEN for a sleek mobile look, or AUTO for a visible scrollbar
                scroll=ft.ScrollMode.AUTO, 
                spacing=20,
                # Pass the list of get_continue_learning_card objects directly
                controls=enrolled_cards if enrolled_cards else no_courses
            )
        ])
    )
)
        
        # ... your existing Chart logic below (unchanged) ...
        page.update()
        new_activity_data = [4, 7, 4, 9, 6, 6, 5]
        
        chart_points = [
            fch.LineChartDataPoint(i, val) for i, val in enumerate(new_activity_data)
        ]
        
        chart_holder.content = fch.LineChart(
            data_series=[
                fch.LineChartData(
                    points=chart_points,
                    color=ft.Colors.PRIMARY, # Chart line follows primary color
                    stroke_width=4,
                    curved=True,
                ),
            ],
            min_x=0, max_x=6,
            max_y=max(new_activity_data) + 2,
            bottom_axis=fch.ChartAxis(
                labels=[
                    fch.ChartAxisLabel(value=0, label=ft.Text("Sun", size=10, color=ft.Colors.ON_SURFACE_VARIANT)),
                    fch.ChartAxisLabel(value=1, label=ft.Text("Mon", size=10, color=ft.Colors.ON_SURFACE_VARIANT)),
                    fch.ChartAxisLabel(value=2, label=ft.Text("Tue", size=10, color=ft.Colors.ON_SURFACE_VARIANT)),
                    fch.ChartAxisLabel(value=3, label=ft.Text("Wed", size=10, color=ft.Colors.ON_SURFACE_VARIANT)),
                    fch.ChartAxisLabel(value=4, label=ft.Text("Thu", size=10, color=ft.Colors.ON_SURFACE_VARIANT)),
                    fch.ChartAxisLabel(value=5, label=ft.Text("Fri", size=10, color=ft.Colors.ON_SURFACE_VARIANT)),
                    fch.ChartAxisLabel(value=6, label=ft.Text("Sat", size=10, color=ft.Colors.ON_SURFACE_VARIANT)),
                ],
            ),
            horizontal_grid_lines=fch.ChartGridLines(width=0.5, color=ft.Colors.OUTLINE_VARIANT),
            vertical_grid_lines=fch.ChartGridLines(width=0),
        )
        page.update()

    page.run_task(fetch_activity_stats)

    return ft.View(
        route="/dashboard",
        bottom_appbar=app_bar,
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        padding=0,
        # 1. Add scroll to the View level to ensure the whole page can move
        controls=[
            ft.SafeArea(
                # 2. Remove expand=True from the Column so it can grow naturally
                expand=True,
                content=ft.Column(
                    expand=True,
                    controls=[
                        header_container,
                        ft.Column( scroll=ft.ScrollMode.AUTO, expand=True,controls=[ft.Container(height=10),
                        goto_course,
                        ft.Container(height=10),
                        ft.Container(
                            padding=ft.Padding(left=10, right=10, top=0, bottom=0), 
                            content=activity_chart
                        ),
                        ft.Container(height=10),
                        continue_learning_section
                    ],)],
                    
                )
            )
        ]
    )