import flet as ft

def get_bottom_appbar(page: ft.Page):  
    return(ft.BottomAppBar(
        bgcolor="white",
        padding=0, # Removes default vertical space
        height=50, # Slim height for the bottom bar
        border_radius=ft.border_radius.only(top_left=10, top_right=10), # Rounded top corners
        content=ft.Container(
            height=30, # Your desired slim height
            content=ft.Row(
                # Space Around ensures the icons are distributed evenly
                alignment=ft.MainAxisAlignment.SPACE_AROUND,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                intrinsic_height=True, # Ensures the Row takes only the necessary height
                controls=[
# 1. Home
            ft.IconButton(
                icon=ft.Icons.HOME_ROUNDED, 
                icon_color="#009787", 
                icon_size=28,
                on_click=lambda e: page.go("/dashboard")
            ),
            # 2. Paper Plane (Angled)
            ft.IconButton(
                icon=ft.Icons.SEND_ROUNDED, # Standard paper plane
                icon_color="#009787", 
                icon_size=28,
                rotate=ft.Rotate(angle=-0.5) # Tilts it slightly for that "angled" look
            ),
            # 3. Library/Books
            ft.IconButton(
                icon=ft.Icons.LIBRARY_BOOKS_ROUNDED, 
                icon_color="#009787", 
                icon_size=28,
                on_click=lambda e: page.go("/courses") # Example navigation to courses
            ),
            # 4. Profile
            ft.IconButton(
                icon=ft.Icons.ACCOUNT_CIRCLE, 
                icon_color="#009787", 
                icon_size=28)
                ],
            ),
        ),
    ))