import flet as ft

def get_landing_appbar(page: ft.Page):
    return ft.AppBar(
        # Adding the logo back as the leading control
        leading=ft.Container(
            content=ft.Image(
                src="logo.png", 
                width=100, 
                height=100, 
                fit="contain"
            ),
            padding=ft.Padding(left=15, top=5, bottom=5, right=0)
        ),
        leading_width=60,
        actions=[
            ft.TextButton("Login",
                icon=ft.Icons.LOGIN,
                style=ft.ButtonStyle(color=ft.Colors.PRIMARY), # Themed equivalent of #009787
                on_click=lambda e: page.go("/")
            ),
            ft.Button("Sign Up",
                icon=ft.Icons.PERSON_ADD_ALT_1,
                color=ft.Colors.ON_PRIMARY, # Themed equivalent of WHITE
                bgcolor=ft.Colors.PRIMARY, # Themed equivalent of #009787
                on_click=lambda e: page.go("/signup")
            ),
            ft.Container(width=10) 
        ],
        bgcolor=ft.Colors.SURFACE, # Themed equivalent of white
        toolbar_opacity=0.5,
        elevation=1, 
        toolbar_height=50
    )