import flet as ft
from src.requests.auth  import reset_request

async def edit_profile_view(page: ft.Page):
    # 1. Retrieve current data
    user_data = page.session.store.get("current_user")
    token = await page.shared_preferences.get("auth_token")
    
    # 2. Form Controllers
    first_name_input = ft.TextField(
        label="First Name", 
        value=user_data.get("first_name"), 
        border_color=ft.Colors.PRIMARY, # Universal Pass
        text_size=14
    )
    last_name_input = ft.TextField(
        label="Last Name", 
        value=user_data.get("last_name"), 
        border_color=ft.Colors.PRIMARY, # Universal Pass
        text_size=14
    )
    username_input = ft.TextField(
        label="Username", 
        value=user_data.get("username"), 
        border_color=ft.Colors.PRIMARY, # Universal Pass
        text_size=14
    )
    
    error_text = ft.Text("", color=ft.Colors.RED_700, size=12, italic=True)

    async def handle_save(e):
        error_text.value = ""
        updated_data = {}
        
        # Map inputs to their corresponding database keys
        fields_to_check = {
            "first_name": first_name_input.value,
            "last_name": last_name_input.value,
            "username": username_input.value,
        }

        for key, current_value in fields_to_check.items():
            # Only add to dictionary if the value is different from session data
            if current_value != user_data.get(key):
                updated_data[key] = current_value

        # 2. Check if anything actually changed
        if not updated_data:
            error_text.value = "No changes detected."
            page.update()
            return

        # 3. Proceed with request if data exists
        save_btn.disabled = True
        save_btn.content = ft.ProgressRing(width=16, height=16, color=ft.Colors.ON_PRIMARY)
        page.update()

        try:
            status, data = await reset_request(token, updated_data)
            
            if status == 200:
                print(f"Updated fields: {list(updated_data.keys())}")
                user_data.update(updated_data)
                page.session.store.set("current_user", user_data)
                
                page.go("/profile")
            else:
                error_text.value = "Failed to update profile. Please try again."
                
        except Exception as ex:
            error_text.value = f"Update failed: {str(ex)}"
        finally:
            save_btn.disabled = False
            save_btn.content = ft.Text("Save Changes")
            page.update()

    save_btn = ft.Button(
        content=ft.Text("Save Changes"),
        bgcolor=ft.Colors.PRIMARY, # Universal Pass
        color=ft.Colors.ON_PRIMARY, # Universal Pass
        height=50,
        width=float("inf"),
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
        on_click=handle_save
    )

    return ft.View(
        route="/edit-profile",
        padding=0,
        bgcolor=ft.Colors.SURFACE, # Set background to follow theme
        controls=[
            ft.SafeArea(content=ft.Column(
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                spacing=0,
                controls=[
                    # Header with "Back" and Profile Image Upload
                    ft.Container(
                        bgcolor=ft.Colors.PRIMARY, # Universal Pass
                        padding=ft.Padding(top=10, bottom=30, left=20, right=20),
                        border_radius=ft.BorderRadius.only(bottom_left=30, bottom_right=30),
                        content=ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Row([
                                    ft.IconButton(
                                        ft.Icons.ARROW_BACK_IOS_NEW, 
                                        icon_color=ft.Colors.ON_PRIMARY, # Universal Pass
                                        on_click=lambda _: page.go("/profile")
                                    ),
                                    ft.Text("Edit Profile", color=ft.Colors.ON_PRIMARY, size=18, weight="bold"),
                                    ft.Container(width=40) # Balancer
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                
                                ft.Stack([
                                    ft.CircleAvatar(
                                        radius=50,
                                        bgcolor=ft.Colors.SURFACE, # Universal Pass
                                        content=ft.Icon(ft.Icons.PERSON, size=40, color=ft.Colors.PRIMARY)
                                    ),
                                    ft.Container(
                                        content=ft.IconButton(
                                            icon=ft.Icons.CAMERA_ALT,
                                            icon_color=ft.Colors.ON_PRIMARY, # Universal Pass
                                            bgcolor=ft.Colors.PRIMARY, # Universal Pass
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
                                
                                # Error Text Indented
                                ft.Container(
                                    padding=ft.padding.only(left=10), 
                                    content=error_text
                                ),
                                
                                ft.Container(height=10),
                                ft.Column(
                                    controls=[save_btn],
                                    horizontal_alignment=ft.CrossAxisAlignment.END 
                                ),
                            ]
                        )
                    )
                ]
            ))
        ]
    )