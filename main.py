import asyncio
import flet as ft
from src.Login import login_view
from src.signup import Signup_view
from src.dashboard import dashboard_view
from src.requests.auth import get_current_user_request 
from src.courses import courses_view

async def main(page: ft.Page):
    page.bgcolor = "#C7F8F3" 
    page.theme_mode = ft.ThemeMode.LIGHT #
    page.appbar = None 
    
    splash_logo = ft.Image(
        src="logo.png",
        width=200,
        height=200,
        fit="contain",
        opacity=1.0,
        scale=1.0,

    )
    
    splash_container = ft.Container(
        content=splash_logo,
        alignment=ft.Alignment(0, 0),
        expand=True,
        bgcolor="#C7F8F3"  
    )
    
    page.add(splash_container)
    page.update()
    
    await asyncio.sleep(2.0)
    
    steps = 15
    for i in range(steps, -1, -1):
        splash_logo.opacity = i / steps
        splash_logo.scale = 0.8 + (0.2 * (i / steps))
        page.update() 
        await asyncio.sleep(0.04)


    page.remove(splash_container) 
    page.update()

    page.theme_mode = ft.ThemeMode.LIGHT
    page.title = "Nu-age"
    page.window_width = 400
    page.window_height = 650
    page.theme = ft.Theme(
        page_transitions=ft.PageTransitionsTheme(
            android="fadeUpwards",
            ios="cupertino"
        )
    )

    async def route_change(e):
        page.views.clear()
        if page.route == "/dashboard":
            token = await page.shared_preferences.get("auth_token")
    
            if not token:
                page.route = "/"
                page.update()
                await route_change(None) 
                return

            status, user_data = await get_current_user_request(token)
            
            if status == 200:
                
                page.session.store.set("current_user", user_data)
                page.views.append(dashboard_view(page))
            else:

                await page.shared_preferences.remove("auth_token")
                page.route = "/"
                await route_change(None)
                return
        
        if page.route == "/":
            page.views.append(login_view(page))
        elif page.route == "/signup":
            page.views.append(Signup_view(page))
        elif page.route == "/courses":
            view= await courses_view(page)
            page.views.append(view)

        page.update()

    page.on_route_change = route_change
    page.route = "/dashboard" 
    await route_change(None)
    
ft.run(main, assets_dir="assets")