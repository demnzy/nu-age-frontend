import flet as ft

def get_course_card(
    course_title: str, 
    course_category: str, 
    course_author: str, 
    image_url: str | None = None, 
    created_at: str | None = None,
    on_enroll_click = None
):
    

    # =========================================================
    # UI Construction
    # =========================================================
    if image_url:
        card_top = ft.Container(
            height=150,
            expand=True,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            border_radius=ft.border_radius.only(top_left=10, top_right=10),
            content=ft.Image(
                src=image_url,
                fit=ft.BoxFit.COVER,
                width=float("inf"),
                placeholder_src="/placeholder.png",
                placeholder_fit=ft.BoxFit.COVER,
                placeholder_fade_out_animation=ft.Animation(
                    duration=ft.Duration(milliseconds=900),
                    curve=ft.AnimationCurve.EASE_OUT,
                ),
                fade_in_animation=ft.Animation(
                    duration=ft.Duration(milliseconds=700),
                    curve=ft.AnimationCurve.EASE_IN_OUT,
                ),
            ),
        )
    else:
        card_top = ft.Container(
            height=150, 
            bgcolor="#37BF14", 
            border_radius=ft.border_radius.only(top_left=10, top_right=10),
            content=ft.Icon(ft.Icons.MENU_BOOK, size=50, color=ft.Colors.ON_PRIMARY), 
        )
        
    return ft.Container(
        offset=ft.Offset(0, 0.1), 
        animate_offset=ft.Animation(400, ft.AnimationCurve.DECELERATE),
        opacity=0,
        animate_opacity=300,
        bgcolor=ft.Colors.SURFACE, 
        border_radius=10,
        height=310, 
        width=100,
        shadow=ft.BoxShadow(blur_radius=2, color=ft.Colors.BLACK_12, offset=ft.Offset(0, 2)),
        ink=True,
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            spacing=0, 
            controls=[
                card_top,
                ft.Container(
                    padding=ft.padding.all(10),
                    content=ft.Column(
                        spacing=8,
                        controls=[
                            ft.Text(
                                course_title, 
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.PRIMARY, 
                                size=15,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS 
                            ),
                            ft.Text(
                                spans=[
                                    ft.TextSpan("Author: ", ft.TextStyle(weight=ft.FontWeight.BOLD, size=12, color=ft.Colors.ON_SURFACE)),
                                    ft.TextSpan(f"{course_author}\n", ft.TextStyle(size=12, color=ft.Colors.ON_SURFACE)), 
                                    ft.TextSpan("Category: ", ft.TextStyle(weight=ft.FontWeight.BOLD, size=12, color=ft.Colors.ON_SURFACE)),
                                    ft.TextSpan(f"{course_category}\n", ft.TextStyle(size=12, color=ft.Colors.ON_SURFACE)),
                                    ft.TextSpan("Created at: ", ft.TextStyle(weight=ft.FontWeight.BOLD, size=12, color=ft.Colors.ON_SURFACE)),
                                    ft.TextSpan(f"{created_at}", ft.TextStyle(size=12, color=ft.Colors.ON_SURFACE)),
                                ],
                                color=ft.Colors.ON_SURFACE_VARIANT, 
                                size=18,
                                no_wrap=False,
                                max_lines=3,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            # Square Enroll Button
                            ft.Button(
                                content=ft.Text("Enroll", weight=ft.FontWeight.BOLD),
                                width= float("inf"),
                                bgcolor=ft.Colors.PRIMARY,
                                color=ft.Colors.WHITE,
                                height=40,
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=4)
                                ),
                                on_click=on_enroll_click # Enrollment handled internally
                            )
                        ]
                    )
                )
            ],
        ),
    )