import flet as ft

def get_enrolled_card(course_title: str, course_category: str, course_author: str, image_url: str|None=None, progress: float=0.0):
    # Determine the percentage string (e.g., 0.65 -> "65%")
    percentage_text = f"{int(progress)}%"
    
    if image_url:
        card_top = ft.Container(
            height=110, 
            expand=True,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            border_radius=ft.BorderRadius.only(top_left=10, top_right=10),
            content=ft.Image(
                src=image_url,
                fit=ft.BoxFit.COVER,
                width=float("inf"),
                placeholder_src="/placeholder.png",
                placeholder_fit=ft.BoxFit.COVER,
                placeholder_fade_out_animation=ft.Animation(900, ft.AnimationCurve.EASE_OUT),
                fade_in_animation=ft.Animation(700, ft.AnimationCurve.EASE_IN_OUT),
            ),
        )
    else:
        card_top = ft.Container(
            height=110,
            bgcolor=ft.Colors.PRIMARY, # Themed equivalent of #009787
            border_radius=ft.BorderRadius.only(top_left=10, top_right=10),
            content=ft.Icon(ft.Icons.MENU_BOOK, size=40, color=ft.Colors.ON_PRIMARY), # Themed white
        )
        
    return ft.Container(
        offset=ft.Offset(0, 0.1), 
        animate_offset=ft.Animation(400, ft.AnimationCurve.DECELERATE),
        opacity=0,
        animate_opacity=300,
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            spacing=5, 
            controls=[
                card_top,
                ft.Container(
                    padding=ft.Padding(10, 0, 10, 5),
                    content=ft.Column(
                        spacing=3,
                        controls=[
                            ft.Text(
                                course_title, 
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.PRIMARY, # Themed equivalent of #009787
                                size=13,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS 
                            ),
                            ft.Text(
                                spans=[
                                    ft.TextSpan("Author: ", ft.TextStyle(weight=ft.FontWeight.BOLD, size=11, color=ft.Colors.ON_SURFACE)),
                                    ft.TextSpan(f"{course_author}\n", ft.TextStyle(size=11, color=ft.Colors.ON_SURFACE)),
                                    ft.TextSpan("Category: ", ft.TextStyle(weight=ft.FontWeight.BOLD, size=11, color=ft.Colors.ON_SURFACE)),
                                    ft.TextSpan(f"{course_category}", ft.TextStyle(size=11, color=ft.Colors.ON_SURFACE)),
                                ],
                                color=ft.Colors.ON_SURFACE_VARIANT, # Themed equivalent of BLACK_54
                                no_wrap=False,
                                max_lines=2,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            # --- PROGRESS SECTION ---
                            ft.Container(height=5), # Spacer
                            ft.Row(
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=10,
                                controls=[
                                    ft.ProgressBar(
                                        value=progress/100, 
                                        color=ft.Colors.PRIMARY, # Themed equivalent of #009787
                                        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, # Themed equivalent of #EEEEEE
                                        height=8,
                                        border_radius=5,
                                        expand=True 
                                    ),
                                    ft.Text(
                                        percentage_text, 
                                        size=11, 
                                        weight=ft.FontWeight.BOLD, 
                                        color=ft.Colors.PRIMARY # Themed equivalent of #009787
                                    ),
                                ]
                            )
                        ]
                    )
                )
            ],
        ),
        bgcolor=ft.Colors.SURFACE, # Themed equivalent of "white"
        border_radius=10,
        height=210, 
        width=100,
        on_click=lambda e: print(f"Clicked on {course_title} card"),
        shadow=ft.BoxShadow(blur_radius=2, color=ft.Colors.BLACK_12, offset=ft.Offset(0, 2)),
    )