import flet as ft
import flet_charts as fch # pyright: ignore[reportMissingImports]
from src.components.bottom_appbar import get_bottom_appbar

def dashboard_view(page: ft.Page):
    user_data = page.session.store.get("current_user")
    first_name = user_data.get("first_name", "User") 
    first_name = f'{first_name}! ' if first_name else "User!"
    App_bar = get_bottom_appbar(page)
    activity_data = [0, 0, 0, 0, 0, 0, 0] 
    chart_points = [
        fch.LineChartDataPoint(i, val) for i, val in enumerate(activity_data)
    ]
    activity_chart=ft.Container(
        width=1000,
        height=270,
        padding=20,
        bgcolor=ft.Colors.WHITE,
        border_radius=20,
        border=ft.border.all(1, ft.Colors.BLACK12),
        content=ft.Column(
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text("Weekly Activity", weight="bold", size=16, color="#009787"),
                        ft.Icon(ft.Icons.ANALYTICS_OUTLINED, color="#009787", size=20),
                    ]
                ),
                ft.Container(
                    height=200,
                    width=1000,
                    content=fch.LineChart(
                        data_series=[
                            fch.LineChartData(
                                points=chart_points,
                                color="#009787",
                                stroke_width=4,
                                curved=True,
                            ),
                        ],
                        min_x=0,  # Starts at Sunday
                        max_x=6,  # Ends at Saturday
                        # If data is all 0, we set max_y to 100 so the chart has "room"
                        max_y=max(activity_data) + 20 if max(activity_data) > 0 else 100,
                        
                        bottom_axis=fch.ChartAxis(
                            labels=[
                                fch.ChartAxisLabel(value=0, label=ft.Text("Sun", size=10)),
                                fch.ChartAxisLabel(value=1, label=ft.Text("Mon", size=10)),
                                fch.ChartAxisLabel(value=2, label=ft.Text("Tue", size=10)),
                                fch.ChartAxisLabel(value=3, label=ft.Text("Wed", size=10)),
                                fch.ChartAxisLabel(value=4, label=ft.Text("Thu", size=10)),
                                fch.ChartAxisLabel(value=5, label=ft.Text("Fri", size=10)),
                                fch.ChartAxisLabel(value=6, label=ft.Text("Sat", size=10)),
                            ],
                        ),
                        horizontal_grid_lines=fch.ChartGridLines(width=0.5, color=ft.Colors.BLACK12),
                        vertical_grid_lines=fch.ChartGridLines(width=0),
                    ),
                ),
            ],
            spacing=10,
        ),
    )
    
    header_container = ft.Container(
    bgcolor="#009787",

    height=85, 

    border_radius=ft.border_radius.only(bottom_left=30, bottom_right=30),
    padding=ft.padding.only(top=10, left=25, right=25, bottom=20),
    content=ft.Column(
        controls=[
            ft.Text(
                value=f"Hello, {first_name}",
                size=23,
                weight=ft.FontWeight.BOLD,
                color="white",
            ),
            ft.Text(
                value="Welcome back to your dashboard",
                size=13,
                color="white70"
            ),
        ],
        spacing=5,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    ),
)    
    


    Goto_course = ft.Container(
    # Your white background
    bgcolor=ft.Colors.WHITE,
    # High border_radius creates the pill shape
    border_radius=30, 
    padding=ft.padding.only(left=20, right=5, top=5, bottom=5),
    width=1000,
    # Subtle border to define it against a white page
    border=ft.border.all(1, ft.Colors.BLACK12), 
    
    content=ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            ft.Text(
                "Available Courses", 
                size=16, 
                weight=ft.FontWeight.W_500,
                color=ft.Colors.BLACK
            ),
            ft.IconButton(
                icon=ft.Icons.ARROW_FORWARD_ROUNDED,
                icon_color="white",
                bgcolor="#009787", # Your specific teal
                icon_size=20,
                style=ft.ButtonStyle(
                    shape=ft.CircleBorder(),
                    padding=10,
                ),
                on_click=lambda e: print("Navigate to courses")
            ),
        ],
    ),
)
    return ft.View(
        route="/dashboard",
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        bottom_appbar=App_bar,
        controls=[
            ft.SafeArea(
                content=ft.Column(
                    controls=[
                        header_container,
                        Goto_course,
                        activity_chart,
                    ],
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                )
            )
        ]
    )