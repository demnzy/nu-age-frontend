import flet as ft

def get_bottom_appbar(page: ft.Page):  
    # Identify current route for the feedback loop
    current_route = page.route

    return(ft.BottomAppBar(
        bgcolor=ft.Colors.SURFACE, # Themed equivalent of "white"
        padding=0, 
        height=63, 
        border_radius=ft.border_radius.only(top_left=10, top_right=10), # Rounded top corners
        shadow_color="grey",
        content=ft.Container(
            height=58, 
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_AROUND,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                intrinsic_height=True, 
                controls=[
                    # 1. Home
                    ft.Column(
                        spacing=0,
                        tight=True, 
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(
                                width=20,
                                height=4,
                                bgcolor=ft.Colors.PRIMARY, # Themed equivalent of "#009787"
                                border_radius=10,
                                margin=ft.margin.only(bottom=5),
                                # Transition: Fades and scales the pill
                                opacity=1 if current_route == "/dashboard" else 0,
                                scale=1 if current_route == "/dashboard" else 0.5,
                                animate_opacity=300,
                                animate_scale=300,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.HOME_ROUNDED, 
                                icon_color=ft.Colors.PRIMARY, # Themed equivalent of "#009787"
                                icon_size=31,
                                on_click=lambda e: page.go("/dashboard")
                            ),
                        ]
                    ),
                    # 2. Nu-Chat
                    ft.Column(
                        spacing=0,
                        tight=True, 
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(
                                width=20,
                                height=4,
                                bgcolor=ft.Colors.PRIMARY, # Themed equivalent of "#009787"
                                border_radius=10,
                                margin=ft.margin.only(bottom=5),
                                opacity=1 if current_route == "/nu-chat" else 0,
                                scale=1 if current_route == "/nu-chat" else 0.5,
                                animate_opacity=300,
                                animate_scale=300,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.SEND_ROUNDED, 
                                icon_color=ft.Colors.PRIMARY, # Themed equivalent of "#009787"
                                icon_size=31,
                                rotate=ft.Rotate(angle=-0.5),
                                on_click=lambda e: page.go("/nu-chat")
                            ),
                        ]
                    ),
                    # 3. Library/Courses
                    ft.Column(
                        spacing=0,
                        tight=True, 
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(
                                width=20,
                                height=4,
                                bgcolor=ft.Colors.PRIMARY, # Themed equivalent of "#009787"
                                border_radius=10,
                                margin=ft.margin.only(bottom=5),
                                opacity=1 if (current_route == "/courses" or current_route.startswith("/courses/")) else 0,
                                scale=1 if (current_route == "/courses" or current_route.startswith("/courses/")) else 0.5,
                                animate_opacity=300,
                                animate_scale=300,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.LIBRARY_BOOKS_ROUNDED, 
                                icon_color=ft.Colors.PRIMARY, # Themed equivalent of "#009787"
                                icon_size=31,
                                on_click=lambda e: page.go("/courses")
                            ),
                        ]
                    ),
                    # 4. Profile
                    ft.Column(
                        spacing=0,
                        tight=True, 
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(
                                width=20,
                                height=4,
                                bgcolor=ft.Colors.PRIMARY, # Themed equivalent of "#009787"
                                border_radius=10,
                                margin=ft.margin.only(bottom=5),
                                opacity=1 if current_route == "/profile" else 0,
                                scale=1 if current_route == "/profile" else 0.5,
                                animate_opacity=300,
                                animate_scale=300,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.ACCOUNT_CIRCLE, 
                                icon_color=ft.Colors.PRIMARY, # Themed equivalent of "#009787"
                                icon_size=31,
                                on_click= lambda e: page.go("/profile")
                            ),
                        ]
                    ),
                ]
            ),
        ),
    ))