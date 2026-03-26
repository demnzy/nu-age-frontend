import flet as ft
from src.components.bottom_appbar import get_bottom_appbar

async def profile_view(page: ft.Page):

    # --- 1. Logout Logic with Confirmation ---
    async def execute_logout(e):
        # This runs only if they click "Yes"
        await page.shared_preferences.remove("auth_token")
        page.go("/")
        page.update()

    async def handle_logout(e):
        # Trigger the dialog
        page.show_dialog(logout_confirmation_dialog)
        page.update()

    # --- 2. The Confirmation Dialog ---
    app_bar = get_bottom_appbar(page)
    user_data=page.session.store.get("current_user")
    first_name =  user_data.get("first_name")
    last_name = user_data.get("last_name")
    full_name = f'{first_name} {last_name}'
    email= user_data.get("email")
    username = user_data.get("username")
    gender = user_data.get("gender")
    role=user_data.get("role")
    logout_confirmation_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Confirm Logout"),
        content=ft.Text("Are you sure you want to log out of Nu-age?"),
        actions=[
            ft.TextButton("Yes", on_click=execute_logout, style=ft.ButtonStyle(color=ft.Colors.PRIMARY)),
            ft.TextButton("No", on_click=lambda e: page.pop_dialog()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    return ft.View(
        route="/profile",
        bottom_appbar=app_bar,
        padding=0,
        controls=[ft.SafeArea (content=
            ft.Column(
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                spacing=0,
                controls=[
                    # 1. Header Stack
                    ft.Stack([
                        ft.Container(
                            bgcolor=ft.Colors.PRIMARY,
                            padding=ft.Padding(top=35, bottom=25, left=20, right=20),
                            border_radius=ft.BorderRadius.only(bottom_left=30, bottom_right=30),
                            width=float("inf"),
                            content=ft.Column(
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=5,
                                controls=[
                                    ft.CircleAvatar(
                                        content=ft.Icon(ft.Icons.PERSON, size=25, color=ft.Colors.PRIMARY),
                                        radius=40,
                                        bgcolor=ft.Colors.ON_PRIMARY,
                                    ),
                                    ft.Text(full_name, size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_PRIMARY),
                                    ft.Text("Mechatronics Student @ FUTMinna", size=12, color=ft.Colors.ON_PRIMARY),
                                ]
                            )
                        ),
                        
                        # Logout Button (Top-Left)
                        ft.Container(
                            content=ft.IconButton(
                                icon=ft.Icons.LOGOUT_ROUNDED,
                                icon_color=ft.Colors.ON_PRIMARY,
                                icon_size=25,
                                tooltip="Logout",
                                on_click=handle_logout,
                            ),
                            top=10,
                            left=10,
                        ),

                        # Edit Button (Top-Right)
                        ft.Container(
                            content=ft.IconButton(
                                icon=ft.Icons.EDIT_ROUNDED,
                                icon_color=ft.Colors.ON_PRIMARY,
                                icon_size=25,
                                tooltip="Edit Profile",
                                on_click=lambda _: page.go("/edit-profile"),
                                style=ft.ButtonStyle(
                                    bgcolor={"": ft.Colors.WHITE24}, 
                                ),
                            ),
                            top=10,
                            right=10,
                        ),
                    ]),
                    
                    # 2. Information Cards Section
                    ft.Container(
                        padding=20,
                        content=ft.Column(
                            spacing=15,
                            scroll=ft.ScrollMode.AUTO,
                            controls=[
                                profile_info_card("Email", email, ft.Icons.ALTERNATE_EMAIL),
                                profile_info_card("Username", username, ft.Icons.VERIFIED_USER_OUTLINED),
                                profile_info_card("Gender", gender, ft.Icons.MALE if gender=="male" else ft.Icons.FEMALE),
                                profile_info_card("Role", role, ft.Icons.ATTRIBUTION),
                            ]
                        )
                    ),
                    ft.Container(height=20)
                ]
            ))
        ])

def profile_info_card(title, value, icon):
    return ft.Container(
        border=ft.Border.all(1, ft.Colors.PRIMARY),
        padding=15,
        bgcolor="#FFFFFF",
        border_radius=10,
        content=ft.Row([
            ft.Icon(icon, color=ft.Colors.PRIMARY, size=20),
            ft.Column([
                ft.Text(title, size=11, color="black"),
                ft.Text(value, size=14, weight=ft.FontWeight.BOLD, color="black"),
            ], spacing=2)
        ], alignment=ft.MainAxisAlignment.START)
    )