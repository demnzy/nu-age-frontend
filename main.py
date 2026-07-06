import asyncio
import flet as ft
import uvicorn
from src.Login import login_view
from src.course_analytics import course_analytics_view
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
from src.member_invite_view import member_invite_view
from src.invite_members import invite_members_view
import os
async def main(page: ft.Page):
    async def keep_alive():
        while True:
            await asyncio.sleep(30) # Wait 30 seconds
            try:
                # Silently update an invisible text or just ping the page
                page.update() 
            except Exception:
                # If the page is truly dead, break the loop
                break

    # Start the heartbeat in the background as soon as the user logs in
    page.run_task(keep_alive)
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
    LIGHT_THEME = ft.Theme(
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
    DARK_THEME = ft.Theme(
    font_family="montserrat",
    color_scheme=ft.ColorScheme(
        primary="#4CAF50",        # Lighter green — readable on dark bg
        secondary="#37BF14",      # Stays the same — pops on dark
        on_primary="#1A1717",     # Dark text on lighter green button
        surface="#252424",        # True dark surface
        on_surface="#E8E8E8",     # Soft white text
        outline="#2C2C2C",        # Subtle borders
    ),
    page_transitions=ft.PageTransitionsTheme(
        android="fadeUpwards",
        ios="cupertino"
    )
)
    splash_logo = ft.Image(
        src="Nu age new logo.png",
        width=400, height=600, fit="contain",
    )
    
    # --- 2. FORCE LIGHT MODE ---

    # ─────────────────────────────────────────────
    # DARK MODE TOGGLE — the only new function
    # ─────────────────────────────────────────────

    async def apply_theme(is_dark: bool):
        """Apply the correct theme and persist the preference."""
        if is_dark:
            page.theme_mode = ft.ThemeMode.DARK
            page.theme = LIGHT_THEME       # used as fallback base
            page.dark_theme = DARK_THEME   # Flet uses dark_theme in dark mode
            page.bgcolor = "#121212"
            
            # Set to Dark Mode Logo
            splash_logo.src = "nu_age_black_2-removebg-preview.png"  
            splash_logo.width = 300
            splash_logo.height = 500
        else:
            page.theme_mode = ft.ThemeMode.LIGHT
            page.theme = LIGHT_THEME
            page.bgcolor = ft.Colors.SURFACE
            
            # THE FIX: Explicitly reset to Light Mode Logo
            splash_logo.src = "Nu age new logo.png" 
            splash_logo.width = 400
            splash_logo.height = 600
            
        page.update()

    async def toggle_dark_mode():
        """
        Call this from anywhere in your app:
            await page.session.store.get("toggle_dark_mode")()
        Or expose it via page.data for global access.
        """
        current = await page.shared_preferences.get("dark_mode")
        is_dark = not (current == "true")
        await page.shared_preferences.set("dark_mode", "true" if is_dark else "false")
        await apply_theme(is_dark)

    # Store the toggle function so any view can access it
    page.data = {"toggle_dark_mode": toggle_dark_mode}

    # ─────────────────────────────────────────────
    # LOAD PERSISTED THEME PREFERENCE ON STARTUP
    # ─────────────────────────────────────────────

    saved_mode = await page.shared_preferences.get("dark_mode")
    is_dark_on_start = saved_mode == "true"
    await apply_theme(is_dark_on_start)

    
    page.title = "Nu-age"
    page.window_width = 400
    page.window_height = 650
    page.appbar = None 
    
    # --- 3. SPLASH SCREEN ---
    
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
        troute = ft.TemplateRoute(page.route)

        def is_public_route(route):
            return route in ["/", "/signup"] or route.startswith("/accept-invite/")

        async def show_session_expired_dialog(
            message: str,
            auto_redirect_seconds: int = 4,
            title: str = "Session expired",
        ):
            """Sleek dialog shown instead of silently kicking the user to login."""

            def go_to_login(e=None):
                page.close(dlg)
                page.go("/")

            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Row(
                    [ft.Icon(ft.Icons.LOCK_CLOCK, color=ft.Colors.PRIMARY), ft.Text(title)],
                    spacing=8,
                ),
                content=ft.Text(message),
                actions=[
                    ft.FilledButton("Log in again", on_click=go_to_login),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.open(dlg)

            # Auto-redirect after a few seconds if they don't tap the button
            await asyncio.sleep(auto_redirect_seconds)
            if dlg.open:
                go_to_login()

        if not is_public_route(page.route):
            # Fast local check first — no network call needed to know
            # whether a token even exists.
            token = await page.shared_preferences.get("auth_token")

            if not token:
                await show_session_expired_dialog(
                    "Please log in to continue.",
                    auto_redirect_seconds=3,
                    title="Login required",
                )
                return

            status, user_data = await get_current_user_request(token)
            if status == 200:
                page.session.store.set("current_user", user_data)
            else:
                await page.shared_preferences.remove("auth_token")
                await show_session_expired_dialog(
                    "Your session has ended. Please log in again to continue."
                )
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
        elif troute.match("/accept-invite/:token"):
            # Safely extract the token natively and mount the invite view.
            # member_invite_view is a regular (non-async) function that
            # returns a View directly, so no `await` here.
            page.views.append(member_invite_view(page, token=troute.token))
        
        elif troute.match("/organisations/:org_id/invite-members"):
        # Safely extract the query parameter ('3839') natively
                # Mount your view and hand off the token cleanly
                page.views.append(await invite_members_view(page, org_id=troute.org_id)) 
        elif troute.match("/organisations/:org_id/courses/:course_id/analytics"):
            page.views.append(
                await course_analytics_view(page, org_id=troute.org_id, course_id=troute.course_id)
            )
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

    # --- THE FIX ---
    # Previously this unconditionally overwrote page.route with "/dashboard"
    # or "/", which destroyed real deep links (e.g. /accept-invite/<uuid>
    # from an email) before route_change ever saw them. Now we only apply
    # that default when there's no real route to honor (fresh load with no
    # path, or bare "/").
    if not page.route or page.route == "/":
        page.route = "/dashboard" if await page.shared_preferences.get("auth_token") else "/"

    await route_change(None)

#ft.run(main, assets_dir="assets")

###WEB CONFIG
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

current_dir = os.path.dirname(os.path.abspath(__file__))

# 2. Join that path with the "assets" folder name
absolute_assets_path = os.path.join(current_dir, "assets")

# 3. Feed the absolute path into Flet
flet_app = flet_fastapi.app(main, assets_dir=absolute_assets_path, session_timeout_seconds=86400)
app.mount("/", flet_app)
if __name__ == "__main__":
    # Grab Coolify's hidden port variable, or default to 8000 locally
    port = int(os.environ.get("PORT", 8000))
    
    # Start the server directly from Python, hiding it from Coolify's UI restrictions
    uvicorn.run(app, host="0.0.0.0", port=port)