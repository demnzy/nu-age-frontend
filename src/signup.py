import flet as ft
from src.requests.auth import signup_request
from src.components.landing_navbar import get_landing_appbar
import re

def Signup_view(page: ft.Page):
    is_processing = False
    page.theme_mode = ft.ThemeMode.LIGHT # Fixes the dark mode text inversion
    custom_message = ft.Text("", size=12)
    validation_error = ft.Text("", color=ft.Colors.RED_700, size=12, weight=ft.FontWeight.W_500)

    def get_container_width():
        return min(page.width * 0.95, 450) if page.width > 0 else 400

    def on_page_resize(e):
        Signup_form.width = get_container_width()
        page.update()

    page.on_resize = on_page_resize

    def validate_inputs(e):
        fields = [
            first_name.value, last_name.value, email.value, 
            username.value, password.value, confirm_password.value
        ]
        all_filled = all(f and f.strip() for f in fields)
        passwords_match = password.value == confirm_password.value
        terms_accepted = terms_checkbox.value
        email_check=re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email.value)

        if not all_filled:
            validation_error.value = "All fields are required."
        elif not email_check:
            validation_error.value = "Please enter a valid email address."
        elif not passwords_match:
            validation_error.value = "Passwords do not match."
        elif not terms_accepted:
            validation_error.value = "You must accept the terms to continue."
        else:
            validation_error.value = ""

        Submit.disabled = not (all_filled and passwords_match and terms_accepted and email_check)
        page.update()
        
    def handle_action_click(e: ft.Event[ft.CupertinoDialogAction]):
        page.pop_dialog()
        page.go("/") 

    async def handle_signup(e):
        nonlocal is_processing
        if is_processing:
            return
            
        is_processing = True
        Submit.disabled = True
        Submit.text = "Signing up..." 
        page.update()
        try:
            status, data = await signup_request(
                email=email.value,
                username=username.value,
                password=password.value,
                first_name=first_name.value,
                last_name=last_name.value,
                gender=gender_selection.value,
                role=role_selection.value
            )
            
            if status == 200:
                page.show_dialog(cupertino_alert_dialog)
            elif status == 409:
                detail = data.get("detail", "")
                if "Username" in detail:
                    validation_error.value = "Username already taken."
                else:
                    validation_error.value = "Email already registered."
                page.update()
            else:
                custom_message.value = f"Error {status}: {data}"
                page.show_dialog(custom_error)
        finally:
            is_processing = False
            Submit.disabled = False
            Submit.text = "Sign Up"
            page.update()

    # Define Dialogs
    cupertino_alert_dialog = ft.AlertDialog(
        title=ft.Row(controls=[ft.Text("Signup Successful!", size=20), ft.Icon(ft.Icons.CHECK, color="#009787")]),
        content=ft.Text("Please proceed to login.", size=14),
        actions=[
            ft.TextButton("Ok", on_click=handle_action_click, style=ft.ButtonStyle(color="#009787"))
        ],
    )
       
    custom_error = ft.AlertDialog(
        title=ft.Row(controls=[ft.Text("Signup Failed", size=20), ft.Icon(ft.Icons.CLOSE, color="#009787")]),
        content=custom_message,
        actions=[
            ft.TextButton("Ok", on_click=lambda e: page.pop_dialog(), style=ft.ButtonStyle(color="#009787"))
        ],
    )

    first_name = ft.TextField(label="First Name", expand=1, height=40, text_size=13, on_change=validate_inputs)
    last_name = ft.TextField(label="Last Name", expand=1, height=40, text_size=13, on_change=validate_inputs)
    
    email = ft.TextField(label="Email", expand=True, height=40, text_size=13, on_change=validate_inputs)
    username = ft.TextField(label="Username", expand=True, height=40, text_size=13, on_change=validate_inputs)
    password = ft.TextField(label="Password", password=True, can_reveal_password=True, expand=True, height=40, text_size=13, on_change=validate_inputs)
    confirm_password = ft.TextField(label="Confirm Password", password=True, can_reveal_password=True, expand=True, height=40, text_size=13, on_change=validate_inputs)
    
    terms_checkbox = ft.Checkbox(label="I accept the Terms & Privacy Policy", value=False, on_change=validate_inputs)
    Submit = ft.ElevatedButton("Sign Up", width=350, color=ft.Colors.WHITE, bgcolor="#009787", height=45, disabled=True, on_click=handle_signup)

    role_selection = ft.RadioGroup(
        content=ft.Row([
            ft.Radio(value="Student", label="Student"),
            ft.Radio(value="Teacher", label="Instructor"),
        ], scroll=ft.ScrollMode.AUTO),
        value="Student"
    )
    
    gender_selection = ft.RadioGroup(
        content=ft.Row([
            ft.Radio(value="Male", label="Male"),
            ft.Radio(value="Female", label="Female"),
        ]),
        value="Male"
    )

    Signup_form = ft.Container(
        width=get_container_width(),
        padding=30,
        bgcolor=ft.Colors.WHITE,
        border_radius=15,
        shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.BLACK12),
        content=ft.Column(
            controls=[
                ft.Text(value="Welcome to ", size=25, spans=[
                    ft.TextSpan(text="Nu-age", style=ft.TextStyle(italic=True, size=25, color="#009787", weight=ft.FontWeight.BOLD))
                ]),
                ft.Text("Create an account to get started.", size=14),
                ft.Divider(),
                ft.Row(controls=[first_name, last_name], spacing=10),
                ft.Row(controls=[ft.Text("Role:", size=14, ), role_selection]),
                ft.Row(controls=[ft.Text("Gender:", size=14, ), gender_selection]),
                ft.Row(controls=[email]),
                ft.Row(controls=[username]),
                ft.Row(controls=[password]),
                ft.Row(controls=[confirm_password]),
                ft.Row(controls=[validation_error]),
                ft.Row(controls=[terms_checkbox]),
                ft.Container(height=10), # Spacer
                Submit
            ],
            spacing=10,
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
            )

    return ft.View(
        route="/signup",
        bgcolor="#009787",
        # 1. Centers the form in the remaining space beneath the AppBar
        vertical_alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        padding=20,
        scroll=ft.ScrollMode.AUTO,
        controls=[
            # 2. Simplified controls list: just the form
            Signup_form,
        ],
        appbar=get_landing_appbar(page)
    )