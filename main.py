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
from src.org_view import organisations_view
from src.create_course import create_courses_view
from src.course_builder import course_builder_view
from src.course_settings import course_settings_view
from src.course_page import course_learner_view
from src.chat_view import chat_view
from src.self_study import self_study_view
from src.network import network_view
from src.member_profile import member_profile_view
from src.course_stats import course_stats_view

async def main(page: ft.Page):
    # --- 1. THE UNIVERSAL SOURCE OF TRUTH ---
    # We define the ColorScheme AND Transitions in ONE object so they don't overwrite each other.
    page.window.icon = "icon.ico"
    def view_pop(view):
        # Prevent crashing if there's only one page left
        if len(page.views) > 1:
            page.views.pop()             # Remove the current view from the stack
            top_view = page.views[-1]    # Look at the view underneath it
            page.go(top_view.route)      # Navigate to that route
            
    # 2. Attach it to the page event
    page.on_view_pop = view_pop
    page.fonts = {
        "inter": "/fonts/Inter_28pt-Regular.ttf",# Local path in /assets/
        "roboto": "/fonts/Roboto_SemiCondensed-Regular.ttf",
        "montserrat": "/fonts/Montserrat-Regular.ttf"
    }
    page.theme = ft.Theme(
        font_family="montserrat",
        color_scheme=ft.ColorScheme(
            primary="#035800",  
            secondary="#37BF14",       # Refactored modules use ft.Colors.PRIMARY
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
        src="Nu age new logo.png",
        width=400, height=600, fit="contain",
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
        
        # Initialize TemplateRoute for pattern matching
        troute = ft.TemplateRoute(page.route)
        
        # --- GLOBAL AUTH CHECK ---
        # Only bypass the auth check if they are explicitly on the login or signup pages
        if page.route not in ["/", "/signup"]:
            token = await page.shared_preferences.get("auth_token")
            if not token:
                page.route = "/"
                await route_change(None)
                return

            status, user_data = await get_current_user_request(token)
            if status == 200:
                page.session.store.set("current_user", user_data)
            else:
                await page.shared_preferences.remove("auth_token")
                page.route = "/"
                await route_change(None)
                return
        
        # --- VIEW MAPPING ---
        if page.route == "/dashboard":
            page.views.append(await dashboard_view(page))
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
        elif page.route == "/organisations":
            page.views.append(await organisations_view(page))
        elif page.route == "/network":
            page.views.append(await network_view(page))
        elif page.route == "/nu-chat":
            page.views.append(await chat_view(page))
        elif troute.match("/courses/:id/stats"):
            page.views.append(await course_stats_view(page,troute.id))
        elif page.route == "/self-study":
            page.views.append(await self_study_view(page))
        # --- NEW: Dynamic Organization Courses Route ---
        elif troute.match("/organisations/:org_id/courses"):
            # Extracts the ID from the URL and passes it to the view
            page.views.append(await create_courses_view(page, troute.org_id))
        elif troute.match("/courses/:course_id/manage"):
            # Extracts the ID from the URL and passes it to the view
            page.views.append(await course_builder_view(page, troute.course_id))
        elif troute.match("/courses/:course_id/view"):
            # Extracts the ID from the URL and passes it to the view
            page.views.append(await course_learner_view(page, troute.course_id))
        elif troute.match("/member/:user_id"):
            # Extracts the ID from the URL and passes it to the view
            page.views.append(await member_profile_view(page, troute.user_id))
        elif troute.match("/organisations/:org_id/courses/:course_id/settings"):
            # Extracts the ID from the URL and passes it to the view
            page.views.append(await course_settings_view(page, troute.course_id, troute.org_id))
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

#app ft.run(main, assets_dir="assets")

import flet.fastapi as flet_fastapi
from fastapi import FastAPI, Request


# 1. Initialize a FastAPI app
app = FastAPI()

# 2. The Magic Middleware: This intercepts the outgoing web page and changes the security lock
@app.middleware("http")
async def apply_credentialless_coep(request: Request, call_next):
    response = await call_next(request)
    # Overwrite Flet's default strict header with the browser's suggested bypass
    if "Cross-Origin-Embedder-Policy" in response.headers:
        response.headers["Cross-Origin-Embedder-Policy"] = "credentialless"
    return response

# 3. Mount your Flet app inside FastAPI
flet_app = flet_fastapi.app(main, assets_dir="assets")
app.mount("/", flet_app)
