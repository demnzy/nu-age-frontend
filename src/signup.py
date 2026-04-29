from arrow import get
import flet as ft
from src.requests.auth import signup_request, get_universities
from src.components.landing_navbar import get_landing_appbar
import re


def Signup_view(page: ft.Page):
    is_processing = False
    page.theme_mode = ft.ThemeMode.LIGHT

    # ── shared state ──────────────────────────────────────────────
    custom_message  = ft.Text("", size=12)
    validation_error = ft.Text(
        "",
        color=ft.Colors.RED_700,
        size=12,
        weight=ft.FontWeight.W_500,
    )

    # ── responsive width ─────────────────────────────────────────
    def get_container_width():
        return min(page.width * 0.95, 480) if page.width > 0 else 440

    def on_page_resize(e):
        Signup_form.width = get_container_width()
        page.update()

    page.on_resize = on_page_resize

    # ── validation ───────────────────────────────────────────────
    def validate_inputs(e):
        required = [
            first_name.value, last_name.value,
            email.value, username.value,
            password.value, confirm_password.value,
        ]
        all_filled      = all(f and f.strip() for f in required)
        passwords_match = password.value == confirm_password.value
        terms_accepted  = terms_checkbox.value
        email_ok        = bool(re.match(
            r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
            email.value or ""
        ))

        if not all_filled:
            validation_error.value = "All required fields must be completed."
        elif not email_ok:
            validation_error.value = "Please enter a valid email address."
        elif not passwords_match:
            validation_error.value = "Passwords do not match."
        elif not terms_accepted:
            validation_error.value = "You must accept the Terms & Privacy Policy."
        else:
            validation_error.value = ""

        Submit.disabled = not (all_filled and passwords_match and terms_accepted and email_ok)
        page.update()

    # ── dialog helpers ────────────────────────────────────────────
    def handle_action_click(e):
        page.pop_dialog()
        page.go("/")

    # ── signup handler ────────────────────────────────────────────
    async def handle_signup(e):
        nonlocal is_processing
        if is_processing:
            return

        is_processing    = True
        Submit.disabled  = True
        Submit.text      = "Creating account…"
        page.update()

        try:
            payload = dict(
                email      = email.value,
                username   = username.value,
                password   = password.value,
                first_name = first_name.value,
                last_name  = last_name.value,
                gender     = gender_selection.value,
                role       = role_selection.value,
                university = University.value if University.value else None,  # Handle empty selection
            )
            # Include organisation_id only when provided
            org_val = organisation_id.value.strip() if organisation_id.value else ""
            if org_val:
                payload["organisation_id"] = org_val

            status, data = await signup_request(**payload)

            if status == 200:
                page.show_dialog(success_dialog)
            elif status == 409:
                detail = data.get("detail", "")
                validation_error.value = (
                    "Username already taken."
                    if "Username" in detail
                    else "Email already registered."
                )
                page.update()
            else:
                custom_message.value = f"Error {status}: {data}"
                page.show_dialog(error_dialog)

        finally:
            is_processing   = False
            Submit.disabled = False
            Submit.text     = "Create Account"
            page.update()

    # ── dialogs ───────────────────────────────────────────────────
    success_dialog = ft.AlertDialog(
        title=ft.Row(controls=[
            ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, color=ft.Colors.PRIMARY, size=22),
            ft.Text("Account Created!", size=18, weight=ft.FontWeight.W_600),
        ], spacing=8),
        content=ft.Text("Your account is ready. Please log in to continue.", size=14),
        actions=[
            ft.TextButton(
                "Go to Login",
                on_click=handle_action_click,
                style=ft.ButtonStyle(color=ft.Colors.PRIMARY),
            )
        ],
    )

    error_dialog = ft.AlertDialog(
        title=ft.Row(controls=[
            ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, color=ft.Colors.RED_600, size=22),
            ft.Text("Signup Failed", size=18, weight=ft.FontWeight.W_600),
        ], spacing=8),
        content=custom_message,
        actions=[
            ft.TextButton(
                "Dismiss",
                on_click=lambda e: page.pop_dialog(),
                style=ft.ButtonStyle(color=ft.Colors.PRIMARY),
            )
        ],
    )

    # ── helper: section label ─────────────────────────────────────
    def section_label(text: str) -> ft.Text:
        return ft.Text(
            text,
            size=11,
            weight=ft.FontWeight.W_600,
            color=ft.Colors.GREY_600,
        )

    # ── field style factory ───────────────────────────────────────
    def field(**kwargs) -> ft.TextField:
        return ft.TextField(
            height=44,
            text_size=13,
            border_radius=8,
            border_color=ft.Colors.GREY_300,
            focused_border_color=ft.Colors.PRIMARY,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=10),
            on_change=validate_inputs,
            **kwargs,
        )

    # ── fields ────────────────────────────────────────────────────
    first_name       = field(label="First Name",        expand=1)
    last_name        = field(label="Last Name",         expand=1)
    email            = field(label="Email Address",     expand=True, keyboard_type=ft.KeyboardType.EMAIL)
    username         = field(label="Username",          expand=True)
    password         = field(label="Password",          expand=True, password=True, can_reveal_password=True)
    confirm_password = field(label="Confirm Password",  expand=True, password=True, can_reveal_password=True)

    # Optional organisation field (no on_change validation needed — it's optional)
    organisation_id = ft.TextField(
        label="Organisation ID",
        hint_text="Optional – enter your organisation ID",
        height=44,
        text_size=13,
        border_radius=8,
        border_color=ft.Colors.GREY_300,
        focused_border_color=ft.Colors.PRIMARY,
        content_padding=ft.padding.symmetric(horizontal=14, vertical=10),
        expand=True,
    )

    University = ft.Dropdown(
        enable_search=True,
        enable_filter=True,
        editable=True,         
        menu_height=250,
        label="University",
        height=44,
        text_size=13,
        border_radius=8,
        border_color=ft.Colors.GREY_300,
        focused_border_color=ft.Colors.PRIMARY,
        content_padding=ft.padding.symmetric(horizontal=14, vertical=10),
        expand=True,
        options=[],
        disabled=True,
        menu_width=get_container_width() - 32,  # match form width minus horizontal padding
        menu_style=ft.MenuStyle(bgcolor=ft.Colors.PRIMARY)
)

# 2. Create a background task to fetch and populate the options
    async def load_universities():
        try:
            universities = await get_universities()
            
            # Populate options using 'key', not 'value'
            University.options = [
                ft.dropdown.Option(content=ft.Text(uni["name"], color="white"), key=uni["name"]) 
                for uni in universities
            ]
            
            # Unlock the dropdown and update the hint
            University.hint_text = "Optional – enter your university name"
            University.disabled = False
            
        except Exception as e:
            print(f"Failed to load universities: {e}")
            University.hint_text = "Failed to load universities"
            
        # Push the changes to the UI
        University.update()

    # 3. Trigger the fetch in the background without freezing the screen

    page.run_task(load_universities)
    # ── role radio group ──────────────────────────────────────────
    role_selection = ft.RadioGroup(
        content=ft.Row([
            ft.Radio(value="Student",  label="Student"),
            ft.Radio(value="Teacher",  label="Instructor"),
        ], spacing=16),
        value="Student",
    )

    # ── gender radio group ────────────────────────────────────────
    gender_selection = ft.RadioGroup(
        content=ft.Row([
            ft.Radio(value="Male",   label="Male"),
            ft.Radio(value="Female", label="Female"),
        ], spacing=16),
        value="Male",
    )

    # ── terms checkbox ────────────────────────────────────────────
    terms_checkbox = ft.Checkbox(
        label="I accept the Terms of Service & Privacy Policy",
        value=False,
        on_change=validate_inputs,
        active_color=ft.Colors.PRIMARY,
        label_style=ft.TextStyle(size=12, color=ft.Colors.GREY_700),
    )

    # ── submit button ─────────────────────────────────────────────
    Submit = ft.ElevatedButton(
        "Create Account",
        width=float("inf"),   # fills parent
        expand=True,
        color=ft.Colors.WHITE,
        bgcolor=ft.Colors.PRIMARY,
        height=46,
        disabled=True,
        on_click=handle_signup,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=10),
            elevation=0,
        ),
    )

    # ── divider row ───────────────────────────────────────────────
    def thin_divider(label=""):
        return ft.Row(
            controls=[
                ft.Divider(thickness=1, color=ft.Colors.GREY_200),
            ],
            expand=True,
        )

    # ── card content ──────────────────────────────────────────────
    card_content = ft.Column(
        controls=[
            # ── Header ──────────────────────────────────────────
            ft.Column(
                controls=[
                    ft.Text(
                        "Create your account",
                        size=22,
                        weight=ft.FontWeight.W_700,
                        color=ft.Colors.GREY_900,
                    ),
                    ft.Text(
                        "Join Nu-age and start learning today.",
                        size=13,
                        color=ft.Colors.GREY_500,
                    ),
                ],
                spacing=4,
            ),

            ft.Divider(height=1, color=ft.Colors.GREY_100),

            # ── Personal info ────────────────────────────────────
            section_label("PERSONAL INFORMATION"),
            ft.Row(controls=[first_name, last_name], spacing=10),
            email,

            # ── Account details ──────────────────────────────────
            section_label("ACCOUNT DETAILS"),
            username,
            password,
            confirm_password,

            # ── Role ─────────────────────────────────────────────
            section_label("ROLE"),
            ft.Container(
                content=role_selection,
                bgcolor=ft.Colors.GREY_50,
                border_radius=8,
                padding=ft.padding.symmetric(horizontal=10, vertical=6),
                border=ft.border.all(1, ft.Colors.GREY_200),
            ),

            # ── Gender ───────────────────────────────────────────
            section_label("GENDER"),
            ft.Container(
                content=gender_selection,
                bgcolor=ft.Colors.GREY_50,
                border_radius=8,
                padding=ft.padding.symmetric(horizontal=10, vertical=6),
                border=ft.border.all(1, ft.Colors.GREY_200),
            ),

            # ── Organisation (optional) ───────────────────────────
            ft.Row(
                controls=[
                    section_label("ORGANISATION"),
                    ft.Container(width=4),
                    ft.Container(
                        content=ft.Text(
                            "OPTIONAL",
                            size=9,
                            weight=ft.FontWeight.W_700,
                            color=ft.Colors.WHITE,
                        ),
                        bgcolor=ft.Colors.GREY_400,
                        border_radius=4,
                        padding=ft.padding.symmetric(horizontal=5, vertical=2),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0,
            ),
            organisation_id,

            # ── University (optional) ───────────────────────────
            ft.Row(
                controls=[
                    section_label("UNIVERSITY"),
                    ft.Container(width=4),
                    ft.Container(
                        content=ft.Text(
                            "OPTIONAL",
                            size=9,
                            weight=ft.FontWeight.W_700,
                            color=ft.Colors.WHITE,
                        ),
                        bgcolor=ft.Colors.GREY_400,
                        border_radius=4,
                        padding=ft.padding.symmetric(horizontal=5, vertical=2),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0,
            ),
            University,

            # ── Validation error ──────────────────────────────────
            ft.Container(
                content=validation_error,
                visible=True,
                padding=ft.padding.only(top=2),
            ),

            # ── Terms ─────────────────────────────────────────────
            terms_checkbox,

            # ── Submit ────────────────────────────────────────────
            ft.Row(controls=[Submit], expand=True),

            # ── Login link ────────────────────────────────────────
            ft.Row(
                controls=[
                    ft.Text("Already have an account?", size=12, color=ft.Colors.GREY_500),
                    ft.TextButton(
                        "Log in",
                        on_click=lambda e: page.go("/login"),
                        style=ft.ButtonStyle(
                            color=ft.Colors.PRIMARY,
                            padding=ft.padding.only(left=4),
                        ),
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=0,
            ),
        ],
        spacing=12,
        tight=True,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    # ── form card ─────────────────────────────────────────────────
    Signup_form = ft.Container(
        width=get_container_width(),
        padding=ft.padding.symmetric(horizontal=32, vertical=28),
        bgcolor=ft.Colors.WHITE,
        border_radius=16,
        shadow=ft.BoxShadow(
            blur_radius=24,
            spread_radius=0,
            color=ft.Colors.with_opacity(0.10, ft.Colors.BLACK),
            offset=ft.Offset(0, 6),
        ),
        content=card_content,
    )

    return ft.View(
        route="/signup",
        bgcolor=ft.Colors.GREY_100,
        vertical_alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        padding=ft.padding.symmetric(horizontal=8),
        scroll=ft.ScrollMode.AUTO,
        controls=[Signup_form],
        appbar=get_landing_appbar(page),
    )