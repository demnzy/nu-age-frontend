import flet as ft

def get_continue_learning_card(course_name, progress, course_id, page: ft.Page):
    
    def animate(e):
        card.scale = 1.1 if card.scale == 1 else 1
        e.control.update()

    card= ft.Container(
        width=200,             
        height=130,
        bgcolor="white",
        border_radius=12,
        padding=15,
        offset=ft.Offset(0, 0),
        scale=1,
        shadow=ft.BoxShadow(
            spread_radius=0, 
            blur_radius=4, 
            color=ft.Colors.BLACK12, 
            offset=ft.Offset(0, 2)
        ),
            animate_scale=ft.Animation(
                duration=600,
                curve=ft.AnimationCurve.BOUNCE_OUT,
            ),
        on_hover=animate,
        on_click=lambda _: page.go(f"/courses/{course_id}/{course_name.replace(' ', '-').lower()}"),
        
        content=ft.Column(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Container(
                content=ft.Icon(ft.Icons.MENU_BOOK, 
                size=30, 
                color=ft.Colors.PRIMARY # Contrasting color (usually White)
                    )
                ),
                ft.Text(
                    course_name, 
                    size=14, 
                    weight=ft.FontWeight.BOLD, 
                    max_lines=2, 
                    overflow=ft.TextOverflow.ELLIPSIS,
                    color="black"
                ),
                ft.Column(
                    spacing=4,
                    controls=[
                        ft.Row([
                            ft.Text("Progress", size=10, color="black"),
                            ft.Text(
                                f"{int(progress*100)}%", 
                                size=10, 
                                weight=ft.FontWeight.BOLD, 
                                color=ft.Colors.PRIMARY
                            ),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        
                        ft.ProgressBar(
                            value=progress,
                            color=ft.Colors.PRIMARY,
                            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                            height=6,
                            border_radius=3,
                        )
                    ]
                )
            ]
        )
    )
    return card