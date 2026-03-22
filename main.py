import asyncio
import flet as ft
from src.Login import login_view
from src.signup import Signup_view
from src.dashboard import dashboard_view
from src.requests.auth import get_current_user_request 
from src.courses import courses_view
from src.course_view import course_details_view 
from src.profile import profile_view
from src.edit_profile import edit_profile_view

async def main(page: ft.Page):
    # --- 1. THE UNIVERSAL SOURCE OF TRUTH ---
    # We define the ColorScheme AND Transitions in ONE object so they don't overwrite each other.
    page.theme = ft.Theme(
        color_scheme=ft.ColorScheme(
            primary="#037166",          # Refactored modules use ft.Colors.PRIMARY
            on_primary=ft.Colors.WHITE, 
            surface="#FAFAFA",          # Refactored modules use ft.Colors.SURFACE
            on_surface="#1A1A1A",       
            outline="#E0E0E0",          
        ),
        page_transitions=ft.PageTransitionsTheme(
            android="fadeUpwards",
            ios="cupertino"
        )
    )

    # --- 2. FORCE LIGHT MODE ---
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = ft.Colors.SURFACE # Use the alias so it matches the theme
    
    page.title = "Nu-age"
    page.window_width = 400
    page.window_height = 650
    page.appbar = None 
    
    # --- 3. SPLASH SCREEN ---
    splash_logo = ft.Image(
        src="logo.png",
        width=200, height=200, fit="contain",
    )
    
    splash_container = ft.Container(
        content=splash_logo,
        alignment=ft.Alignment(0,0),
        expand=True,
        bgcolor=ft.Colors.SURFACE # Use the alias for consistency
    )
    
    page.add(splash_container)
    page.update()
    
    await asyncio.sleep(2.0)
    
    # Fade Out Animation
    steps = 15
    for i in range(steps, -1, -1):
        splash_logo.opacity = i / steps
        splash_logo.scale = 0.8 + (0.2 * (i / steps))
        page.update() 
        await asyncio.sleep(0.04)

    page.remove(splash_container) 
    page.update()

    # --- 4. ROUTING LOGIC ---
    async def route_change(e):
        page.views.clear()
        
        # Dashboard Logic
        if page.route == "/dashboard":
            token = await page.shared_preferences.get("auth_token")
            if not token:
                page.route = "/"
                await route_change(None)
                return

            status, user_data = await get_current_user_request(token)
            if status == 200:
                page.session.store.set("current_user", user_data)
                page.views.append(await dashboard_view(page))
            else:
                await page.shared_preferences.remove("auth_token")
                page.route = "/"
                await route_change(None)
                return
        
        # Static Routes
        elif page.route == "/":
            page.views.append(login_view(page))
        elif page.route == "/signup":
            page.views.append(Signup_view(page))
        elif page.route == "/profile":
            page.views.append(await profile_view(page))
        elif page.route == "/courses":
            page.views.append(await courses_view(page))
        elif page.route == "/edit-profile":
            page.views.append(await edit_profile_view(page))

        # Dynamic Course Details
        elif page.route.startswith("/courses/"):
            route_parts = page.route.split("/")
            # Check if we have at least: / , courses , id
            if len(route_parts) > 2:
                course_id = route_parts[2]
                
                # Check if the name exists at index 3, else use None
                course_name = route_parts[3] if len(route_parts) > 3 else None
                
                # Pass both to your view function
                page.views.append(await course_details_view(page, course_id, course_name))
            
        page.update()

    page.on_route_change = route_change
    # Trigger initial route
    page.route = "/dashboard" if await page.shared_preferences.get("auth_token") else "/"
    await route_change(None)
    
ft.run(main, assets_dir="assets")