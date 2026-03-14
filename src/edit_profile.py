import flet as ft

async def edit_profile_view(page: ft.Page):
    # 1. Retrieve current data
    user_data = page.session.store.get("current_user")
    
    # 2. Form Controllers
    first_name_input = ft.TextField(label="First Name", value=user_data.get("first_name"), border_color="#009787", text_size=14)
    last_name_input = ft.TextField(label="Last Name", value=user_data.get("last_name"), border_color="#009787", text_size=14)
    username_input = ft.TextField(label="Username", value=user_data.get("username"), border_color="#009787", text_size=14)
    email_input = ft.TextField(label="Email", value=user_data.get("email"), border_color="#009787", text_size=14)
    
    error_text = ft.Text("", color=ft.Colors.RED_700, size=12, italic=True)

    async def handle_save(e):
        # Reset error
        error_text.value = ""
        
        # Simple Validation Example
        if not email_input.value.contains("@"):
            error_text.value = "Please enter a valid academic email."
            page.update()
            return

        # Start loading state
        save_btn.disabled = True
        save_btn.content = ft.ProgressRing(width=16, height=16, color="white")
        page.update()

        try:
            # Here you would call your update_profile_request(token, data)
            print("Saving changes to backend...")
            page.go("/profile")
        except Exception as ex:
            error_text.value = f"Update failed: {str(ex)}"
        finally:
            save_btn.disabled = False
            save_btn.content = ft.Text("Save Changes")
            page.update()

    save_btn = ft.Button(
        content=ft.Text("Save Changes"),
        bgcolor="#009787",
        color="white",
        height=50,
        width=float("inf"),
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
        on_click=handle_save
    )

    return ft.View(
        route="/edit-profile",
        padding=0,
        controls=[
            ft.SafeArea(content=ft.Column(
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    # Header with "Back" and Profile Image Upload
                    ft.Container(
                        bgcolor="#009787",
                        padding=ft.Padding(top=10, bottom=30, left=20, right=20),
                        border_radius=ft.BorderRadius.only(bottom_left=30, bottom_right=30),
                        content=ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Row([
                                    ft.IconButton(ft.Icons.ARROW_BACK_IOS_NEW, icon_color="white", on_click=lambda _: page.go("/profile")),
                                    ft.Text("Edit Profile", color="white", size=18, weight="bold"),
                                    ft.Container(width=40) # Balancer
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                
                                ft.Stack([
                                    ft.CircleAvatar(
                                        radius=50,
                                        bgcolor=ft.Colors.WHITE,
                                        content=ft.Icon(ft.Icons.PERSON, size=40, color="#009787")
                                    ),
                                    ft.Container(
                                        content=ft.IconButton(
                                            icon=ft.Icons.CAMERA_ALT,
                                            icon_color="white",
                                            bgcolor="#009787",
                                        ),
                                        bottom=0,
                                        right=0,
                                    )
                                ])
                            ]
                        )
                    ),

                    # Form Section
                    ft.Container(
                        padding=20,
                        expand=True,
                        content=ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                            spacing=15,
                            controls=[
                                first_name_input,
                                last_name_input,
                                username_input,
                                email_input,
                                
                                # Error Text Indented
                                ft.Container(padding=ft.padding.only(left=10), content=error_text),
                                
                                ft.Container(height=10),
                                save_btn
                            ]
                        )
                    )
                ]
            ))
        ]
    )