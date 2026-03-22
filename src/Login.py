import flet as ft
from src.requests.auth import login_request
from src.components.landing_navbar import get_landing_appbar

def login_view(page: ft.Page):
    is_processing = False
    custom_message = ft.Text("")
    # Error signals usually stay red/amber even in dark mode for urgency
    validation_error = ft.Text("", color=ft.Colors.RED_700, size=12, weight=ft.FontWeight.W_500)
    
    def handle_action_click(e: ft.Event[ft.CupertinoDialogAction]):
        page.pop_dialog()
        page.go("/dashboard")
        
    def validate_inputs(e):
        fields = [
            email.value, password.value
        ]
        all_filled = all(f and f.strip() for f in fields)
        if not all_filled:
            validation_error.value = "         All fields are required."
        else:
            validation_error.value = ""

        Submit.disabled = not (all_filled)
        page.update()

    cupertino_alert_dialog = ft.AlertDialog(
        title=ft.Row(
            controls=[
                ft.Text("Login Successful!"),
                ft.Icon(ft.Icons.CHECK, color=ft.Colors.PRIMARY) # Use PRIMARY instead of #009787
            ],
            alignment=ft.MainAxisAlignment.START,
        ),
        content=ft.Text("Welcome back to Nu-age."),
        
        actions=[
            ft.TextButton(
                content=ft.Text("Ok", color=ft.Colors.PRIMARY, weight=ft.FontWeight.BOLD),
                on_click=handle_action_click,
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    
    User_Not_found = ft.AlertDialog(
        title=ft.Row(
            controls=[
                ft.Text("Login Failed!"), 
                ft.Icon(ft.Icons.CLOSE, color=ft.Colors.RED_700) 
            ],
            alignment=ft.MainAxisAlignment.START,
        ),
        content=custom_message,
        actions=[
            ft.TextButton(
                content=ft.Text("Ok", color=ft.Colors.PRIMARY),
                on_click=lambda e: page.pop_dialog(), 
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    async def handle_submit(e):
        nonlocal is_processing
        Submit.disabled = True
        page.update()
        if is_processing:
            return
            
        is_processing = True
        Submit.disabled = True
        # Using ON_SURFACE or a static color for the ring inside the button
        Submit.content = ft.ProgressRing(width=16, height=16, color=ft.Colors.ON_PRIMARY) 
        page.update()
        try:
            status, data = await login_request(email.value, password.value)   
            if status == 200:
                token = data.get("access_token")
                await page.shared_preferences.set("auth_token", token)
                Submit.bgcolor = ft.Colors.PRIMARY 
                page.show_dialog(cupertino_alert_dialog)

            elif status == 404:
                custom_message.value = "This account does not exist. Please check your email and try again."
                page.update()
                page.show_dialog(User_Not_found)
                Submit.disabled = False
                page.update()

            elif status == 403:
                Submit.bgcolor = ft.Colors.PRIMARY 
                page.update()
                custom_message.value = "Incorrect Password. Please try again"
                page.show_dialog(User_Not_found)
                Submit.disabled = False
                page.update()
        finally:
            is_processing = False
            Submit.content = "Login"
            page.update()
            
    email = ft.TextField(
        label="Email/Username", 
        width=270, height=40, text_size=15, 
        on_change=validate_inputs,
        border_color=ft.Colors.OUTLINE # Themed border
    )
    password = ft.TextField(
        label="Password", password=True, can_reveal_password=True, 
        width=270, height=40, text_size=15, 
        on_change=validate_inputs,
        border_color=ft.Colors.OUTLINE
    )
    Submit = ft.Button(
        "Login", width=320, 
        color=ft.Colors.ON_PRIMARY, # White text in light, Off-white in dark
        bgcolor=ft.Colors.PRIMARY, 
        height=40, disabled=True, on_click=handle_submit
    )
    
    login_card = ft.Container(
        width=350,
        padding=20,
        bgcolor=ft.Colors.SURFACE, # Swaps White <-> Deep Charcoal
        border_radius=15,
        height=530,
        
        shadow=ft.BoxShadow(
            blur_radius=15,
            color=ft.Colors.SHADOW, # Uses themed shadow color
            offset=ft.Offset(0, 5)
        ),

        content=ft.Column(
            [
                ft.Icon(ft.Icons.ACCOUNT_CIRCLE, 
                color=ft.Colors.PRIMARY, 
                size=100
            ),
                ft.Text("Welcome Back!", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                ft.Row(controls=[
                    ft.Icon(ft.Icons.MAIL_OUTLINE, 
                        color=ft.Colors.PRIMARY, 
                        width=20, height=40
                    ),
                email]),
                ft.Row(controls=[
                    ft.Icon(ft.Icons.VPN_KEY, 
                        color=ft.Colors.PRIMARY, 
                        width=20, height=40
                    ),
                password]),
                ft.Row(controls=[ft.Text("  "),
                        ft.TextButton(content=ft.Text("Forgot Password", color=ft.Colors.PRIMARY)),
                        ft.TextButton(content=ft.Text("Create an Account", color=ft.Colors.PRIMARY), on_click=lambda _: page.go("/signup")),
                 ]),
                Submit
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=30,
            tight=True
        )
    )

    return ft.View(
        bgcolor="#379289",
        route="/",
        controls=[login_card],
        vertical_alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        appbar=get_landing_appbar(page)
    )