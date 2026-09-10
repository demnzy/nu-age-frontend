import flet as ft

def get_landing_appbar(page: ft.Page, active_page: str = "login"):
    """
    Sleek, standard app bar for pre-login views (Login, Signup).
    Features Nu-Age brand identity on the left, an explicit 'Offline Courses'
    downloads action, and a contextual auth switch button on the right.
    """
    brand_logo = ft.Container(
        content=ft.Row(
            [
                ft.Image(
                    src="icon.png",
                    width=28,
                    height=28,
                    fit=ft.BoxFit.CONTAIN,
                ),
                ft.Text(
                    "Nu Age",
                    size=18,
                    weight=ft.FontWeight.W_800,
                    color=ft.Colors.PRIMARY,
                ),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        ink=True,
        on_click=lambda e: page.go("/"),
        padding=ft.Padding.only(left=16),
    )


    if active_page == "signup":
        auth_btn = ft.ElevatedButton(
            "Sign In",
            icon=ft.Icons.LOGIN_ROUNDED,
            color=ft.Colors.ON_PRIMARY,
            bgcolor=ft.Colors.PRIMARY,
            height=36,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            on_click=lambda e: page.go("/"),
        )
    else:
        auth_btn = ft.ElevatedButton(
            "Sign Up",
            icon=ft.Icons.PERSON_ADD_ALT_1_ROUNDED,
            color=ft.Colors.ON_PRIMARY,
            bgcolor=ft.Colors.PRIMARY,
            height=36,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            on_click=lambda e: page.go("/signup"),
        )

    return ft.AppBar(
        leading=brand_logo,
        leading_width=150,
        actions=[
            auth_btn,
            ft.Container(width=12),  # Right margin spacer
        ],
        bgcolor=ft.Colors.SURFACE,
        toolbar_height=56,
        elevation=0,
    )