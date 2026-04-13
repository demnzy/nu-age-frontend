import flet as ft

def get_bottom_appbar(page: ft.Page):
    # Identify current route for the feedback loop
    current_route = page.route
    
    # Safely extract user data and force uppercase for the role check
    user_data = page.session.store.get("current_user") or {}
    role = user_data.get("role", "STUDENT").upper()

    # --- 1. THE HELPER FUNCTION ---
    def nav_item(icon_name, route, is_active, is_rotated=False):
        
        # Clean up the route string for the label (e.g., "/nu-chat" -> "Nu-chat")
        label_text = route.strip("/").capitalize()
        if label_text == "Dashboard" or not label_text:
            label_text = "Home"

        return ft.Column(
            spacing=0, # Keeps Icon and Text tightly packed
            tight=True, 
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                # 1. The Animated Pill
                ft.Container(
                    width=20, 
                    height=3, 
                    bgcolor=ft.Colors.PRIMARY,
                    border_radius=10, 
                    margin=ft.margin.only(bottom=0), # Reduced margin to save space
                    opacity=1 if is_active else 0,
                    scale=1 if is_active else 0.5,
                    animate_opacity=300, 
                    animate_scale=300,
                ),
                # 2. The Icon Button
                ft.IconButton(
                    icon=icon_name, 
                    icon_color=ft.Colors.PRIMARY,
                    icon_size=25,
                    rotate=ft.Rotate(angle=-0.5) if is_rotated else None,
                    on_click=lambda e, r=route: page.go(r) 
                ),
                # 3. The Text Label (Flattened into the main column)
                ft.Text(
                    label_text, 
                    size=10, 
                    # UX touch: Highlight text if active
                    color=ft.Colors.PRIMARY if is_active else ft.Colors.ON_SURFACE_VARIANT,
                    weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.NORMAL
                )
            ]
        )

    # --- 2. BUILD THE LIST OF ICONS ---
    nav_controls = [
        nav_item(ft.Icons.HOME_ROUNDED, "/dashboard", current_route == "/dashboard"),
        nav_item(ft.Icons.SEND_ROUNDED, "/nu-chat", current_route == "/nu-chat", is_rotated=True),
        nav_item(ft.Icons.LIBRARY_BOOKS_ROUNDED, "/courses", current_route == "/courses" or current_route.startswith("/courses/")),
    ]

    if role in ["ADMIN", "TEACHER"]:
        nav_controls.append(
            nav_item(ft.Icons.BUSINESS_SHARP, "/organisations", current_route == "/organisations" or current_route.startswith("/organisations/"))
        )

    nav_controls.append(
        nav_item(ft.Icons.ACCOUNT_CIRCLE, "/profile", current_route == "/profile")
    )

    # --- 3. RETURN THE APP BAR ---
    return ft.BottomAppBar(
        bgcolor=ft.Colors.SURFACE, 
        padding=0, 
        # THE FIX: Increased height from 63 to 75 to comfortably fit the text
        height=75, 
        border_radius=ft.border_radius.only(top_left=10, top_right=10),
        shadow_color=ft.Colors.BLACK26,
        content=ft.Container(
            height=75, 
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_AROUND,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                intrinsic_height=True, 
                controls=nav_controls
            )
        )
    )